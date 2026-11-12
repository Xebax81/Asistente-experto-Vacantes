"""Pasarela unica al modelo de lenguaje.

En el PI4 cada submodulo hablaba con un proveedor distinto (Groq en S1 y S2,
DeepSeek en S3, Ollama local en S4). Aca hay una sola interfaz y el proveedor se
elige en el .env. Asi el sistema integrado tiene un unico punto de configuracion,
un unico lugar donde se cuentan las llamadas y un unico formato de salida (JSON).

No usa LangChain a proposito: solo HTTP con la biblioteca estandar, para que el
ZIP del PG3 se pueda levantar sin resolver versiones de dependencias.
"""
import json
import re
import time
import urllib.error
import urllib.request

from core import config


class ErrorLLM(RuntimeError):
    pass


class SinCupo(ErrorLLM):
    """El modelo existe pero no tiene cupo gratuito para esta clave (429, limit: 0)."""


class Sobrecargado(ErrorLLM):
    """El proveedor esta saturado (503) o pide esperar (429 por ritmo). Es transitorio."""


class RespuestaLLM:
    def __init__(self, texto, datos, segundos, intentos, proveedor, modelo,
                 motivos=None, truncada=False):
        self.texto = texto
        self.datos = datos          # dict ya parseado, o None si no era JSON valido
        self.segundos = segundos
        self.intentos = intentos
        self.proveedor = proveedor
        self.modelo = modelo
        # Motivos del ultimo rechazo (del parseo o del validador). Si datos es None,
        # explican por que el submodulo entrego su texto de respaldo (regla A6).
        self.motivos = list(motivos or [])
        self.truncada = truncada    # el proveedor corto la salida por max_tokens

    def como_dict(self):
        d = {
            'proveedor': self.proveedor, 'modelo': self.modelo,
            'segundos': round(self.segundos, 2), 'intentos': self.intentos,
            'datos': self.datos,
        }
        if self.motivos:
            d['motivos_rechazo'] = self.motivos
        if self.truncada:
            d['salida_truncada'] = True
        if self.datos is None and self.texto:
            # Lo que devolvio el modelo, recortado, para poder auditar el rechazo.
            d['texto_rechazado'] = str(self.texto)[:1500]
        return d


def _post(url, cuerpo, cabeceras=None, timeout=180):
    datos = json.dumps(cuerpo).encode('utf-8')
    cab = {'Content-Type': 'application/json'}
    cab.update(cabeceras or {})
    pedido = urllib.request.Request(url, data=datos, headers=cab, method='POST')
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode('utf-8', 'replace')[:400]
        if e.code == 429 and 'limit: 0' in detalle:
            raise SinCupo(f'sin cupo gratuito: {detalle[:200]}') from e
        if e.code in (429, 500, 502, 503, 504):
            raise Sobrecargado(f'{e.code}: {detalle[:200]}') from e
        raise ErrorLLM(f'{e.code} del proveedor {config.LLM_PROVEEDOR}: {detalle}') from e
    except urllib.error.URLError as e:
        raise ErrorLLM(f'No se pudo contactar al proveedor {config.LLM_PROVEEDOR}: {e.reason}') from e


# ------------------------------------------------------------------ proveedores
GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta'
_modelo_gemini = None
# Si la ultima respuesta del proveedor fue cortada por max_tokens. Sirve para que el
# motivo de rechazo diga "salida truncada" en vez de "JSON invalido" a secas.
_ultima_truncada = [False]


def listar_modelos_gemini():
    """Pregunta a la API qué modelos habilita ESTA clave.

    Es la única fuente confiable: los nombres de modelo de Gemini rotan y los
    listados de internet envejecen. Devuelve los que sirven para generar texto.
    """
    if not config.LLM_CLAVE:
        raise ErrorLLM('Falta LLM_CLAVE para consultar los modelos de Gemini.')
    url = f'{GEMINI_BASE}/models?key={config.LLM_CLAVE}&pageSize=200'
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            datos = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise ErrorLLM(f'{e.code} al listar modelos: '
                       f'{e.read().decode("utf-8", "replace")[:300]}') from e
    except urllib.error.URLError as e:
        raise ErrorLLM(f'No se pudo contactar a Gemini: {e.reason}') from e

    salida = []
    for m in datos.get('models', []):
        if 'generateContent' not in (m.get('supportedGenerationMethods') or []):
            continue
        salida.append({
            'nombre': (m.get('name') or '').replace('models/', ''),
            'descripcion': m.get('displayName') or '',
            'entrada': m.get('inputTokenLimit'),
            'salida': m.get('outputTokenLimit'),
        })
    return salida


DESCARTAR = ('preview', 'exp-', 'image', 'vision', 'tts', 'audio', 'live', 'dialog',
             'embedding', 'robotics', 'thinking', 'learnlm', 'aqa')
# Familias que no suelen tener cupo gratuito: se dejan al final de la lista.
POSTERGAR = ('pro', 'ultra', 'omni', 'argon', 'max')


def _puntuar(nombre):
    """Ordena los candidatos. Mayor puntaje = se prueba antes.

    Los nombres de modelo rotan, así que en vez de fijar uno se puntúa la forma
    del nombre: la familia 'flash' estable de versión más alta primero, y las
    familias caras al final. Cuál tiene cupo gratuito la API no lo dice en el
    listado, así que si la elegida devuelve 429 se pasa a la siguiente.
    """
    n = nombre.lower()
    puntaje = 0.0
    if 'flash' in n:
        puntaje += 100
    if 'lite' in n:
        puntaje += 20          # las lite casi siempre tienen cupo gratuito
    if 'gemma' in n:
        puntaje += 10          # modelo abierto, sirve de último recurso
    for p in POSTERGAR:
        if p in n.split('-'):
            puntaje -= 60
    # Un nombre canónico tipo "gemini-2.5-flash" vale más que uno con apellidos.
    if re.fullmatch(r'gemini-\d+(?:\.\d+)?-flash(?:-lite)?', n):
        puntaje += 50
    version = re.search(r'(\d+(?:\.\d+)?)', n)
    if version:
        puntaje += min(float(version.group(1)), 20)   # versión más alta, antes
    return puntaje


def _candidatos_gemini():
    disponibles = [m['nombre'] for m in listar_modelos_gemini()]
    limpios = [n for n in disponibles if not any(p in n.lower() for p in DESCARTAR)]
    return sorted(limpios or disponibles, key=_puntuar, reverse=True)


def _elegir_modelo_gemini():
    """Primer candidato. El que realmente se use se confirma al primer pedido."""
    global _modelo_gemini
    if _modelo_gemini:
        return _modelo_gemini
    candidatos = _candidatos_gemini()
    if not candidatos:
        raise ErrorLLM('La clave no habilita ningún modelo con generateContent.')
    return candidatos[0]


ESPERAS = (2, 6, 15)   # segundos entre reintentos ante una saturacion transitoria


def _con_espera(hacer):
    """Reintenta una llamada ante 503/429 por ritmo, con esperas crecientes.

    Un 503 es "el modelo esta ocupado", no un error de la consulta: insistir un
    par de veces resuelve la mayoria de los casos y evita tirar a la basura el
    trabajo que la cadena ya hizo.
    """
    for i, espera in enumerate((0,) + ESPERAS):
        if espera:
            time.sleep(espera)
        try:
            return hacer()
        except Sobrecargado:
            if i == len(ESPERAS):
                raise
    raise Sobrecargado('sin reintentos disponibles')


def _gemini(sistema, usuario, temperatura, max_tokens):
    """Pide a Gemini. Si el modelo elegido no tiene cupo gratuito, pasa al siguiente.

    El listado de modelos no dice cuáles son gratis, así que la única forma de
    saberlo es pedirlo: un 429 con "limit: 0" significa que ese modelo no tiene
    cupo para esta clave. Se recuerda el primero que funciona.
    """
    global _modelo_gemini
    if not config.LLM_CLAVE:
        raise ErrorLLM('Falta LLM_CLAVE para Gemini (Google AI Studio, tier gratuito).')

    cuerpo = {
        'systemInstruction': {'parts': [{'text': sistema}]},
        'contents': [{'role': 'user', 'parts': [{'text': usuario}]}],
        'generationConfig': {
            'temperature': temperatura,
            'maxOutputTokens': max_tokens,
            'responseMimeType': 'application/json',
        },
    }

    if config.LLM_MODELO:
        candidatos = [config.LLM_MODELO]        # fijado a mano: no se busca otro
    elif _modelo_gemini:
        # El que ya funciono primero; si justo esta saturado (503), se prueban los demas
        # en vez de caer al respaldo por un corte transitorio.
        try:
            otros = [m for m in _candidatos_gemini()[:6] if m != _modelo_gemini]
        except ErrorLLM:
            otros = []
        candidatos = [_modelo_gemini] + otros
    else:
        candidatos = _candidatos_gemini()[:6]

    sin_cupo, saturados = [], []
    for modelo in candidatos:
        url = f'{GEMINI_BASE}/models/{modelo}:generateContent?key={config.LLM_CLAVE}'
        try:
            r = _con_espera(lambda: _post(url, cuerpo))
        except SinCupo:
            sin_cupo.append(modelo)
            continue
        except Sobrecargado:
            # El modelo esta saturado ahora mismo: se prueba el siguiente candidato.
            saturados.append(modelo)
            continue
        _modelo_gemini = modelo
        try:
            cand = r['candidates'][0]
            texto = cand['content']['parts'][0]['text']
        except (KeyError, IndexError):
            raise ErrorLLM(f'Respuesta inesperada de Gemini: {json.dumps(r)[:300]}')
        _ultima_truncada[0] = (cand.get('finishReason') == 'MAX_TOKENS')
        return texto

    if saturados and not sin_cupo:
        raise Sobrecargado(
            'Gemini está saturado en este momento (503) en los modelos probados: '
            + ', '.join(saturados) + '. Es transitorio: volvé a intentar en un rato, '
            'o cambiá LLM_PROVEEDOR a groq u ollama en el .env.')

    raise SinCupo(
        'Ninguno de los modelos probados tiene cupo gratuito para esta clave: '
        + ', '.join(sin_cupo) +
        '. Mirá cuáles son gratis en https://ai.google.dev/gemini-api/docs/pricing '
        'y poné uno en LLM_MODELO del .env, o cambiá LLM_PROVEEDOR a groq u ollama.')


def _compatible_openai(base, sistema, usuario, temperatura, max_tokens):
    """Groq y DeepSeek exponen la API compatible con OpenAI."""
    if not config.LLM_CLAVE:
        raise ErrorLLM(f'Falta LLM_CLAVE para {config.LLM_PROVEEDOR}.')
    cuerpo = {
        'model': config.modelo(),
        'messages': [{'role': 'system', 'content': sistema},
                     {'role': 'user', 'content': usuario}],
        'temperature': temperatura,
        'max_tokens': max_tokens,
        'response_format': {'type': 'json_object'},
    }
    r = _con_espera(lambda: _post(f'{base}/chat/completions', cuerpo,
                                  {'Authorization': f'Bearer {config.LLM_CLAVE}'}))
    try:
        _ultima_truncada[0] = (r['choices'][0].get('finish_reason') == 'length')
        return r['choices'][0]['message']['content']
    except (KeyError, IndexError):
        raise ErrorLLM(f'Respuesta inesperada: {json.dumps(r)[:300]}')


def _ollama(sistema, usuario, temperatura, max_tokens, esquema=None):
    cuerpo = {
        'model': config.modelo(),
        'messages': [{'role': 'system', 'content': sistema},
                     {'role': 'user', 'content': usuario}],
        'stream': False,
        'format': esquema if esquema else 'json',
        'options': {'temperature': temperatura, 'num_predict': max_tokens, 'seed': 7},
    }
    r = _con_espera(lambda: _post(f'{config.OLLAMA_URL}/api/chat', cuerpo, timeout=600))
    try:
        _ultima_truncada[0] = (r.get('done_reason') == 'length')
        return r['message']['content']
    except KeyError:
        raise ErrorLLM(f'Respuesta inesperada de Ollama: {json.dumps(r)[:300]}')


# ------------------------------------------------------------------ API publica
contador = {'llamadas': 0, 'segundos': 0.0}


def _limpiar(texto):
    """Algunos modelos envuelven el JSON en un bloque markdown pese al pedido."""
    t = (texto or '').strip()
    if t.startswith('```'):
        t = t.split('\n', 1)[-1]
        if t.rstrip().endswith('```'):
            t = t.rstrip()[:-3]
    return t.strip()


def pedir_json(sistema, usuario, temperatura=None, max_tokens=None, esquema=None,
               reintentos=1, validador=None):
    """Pide al LLM una respuesta JSON y la devuelve parseada.

    validador: funcion(datos) -> lista de motivos de rechazo (vacia si esta bien).
    Si el JSON es invalido o el validador rechaza, se reintenta una vez indicando
    el motivo, que es el mecanismo que usaban los cuatro PI4.
    """
    temperatura = config.TEMP_EXTRACCION if temperatura is None else temperatura
    max_tokens = max_tokens or config.MAX_TOKENS_EXTRACCION
    inicio = time.time()
    motivos, mensaje, ultimo, truncada = [], usuario, None, False

    for intento in range(1, reintentos + 2):
        _ultima_truncada[0] = False
        if config.LLM_PROVEEDOR == 'gemini':
            crudo = _gemini(sistema, mensaje, temperatura, max_tokens)
        elif config.LLM_PROVEEDOR == 'groq':
            crudo = _compatible_openai('https://api.groq.com/openai/v1', sistema, mensaje,
                                       temperatura, max_tokens)
        elif config.LLM_PROVEEDOR == 'deepseek':
            crudo = _compatible_openai('https://api.deepseek.com/v1', sistema, mensaje,
                                       temperatura, max_tokens)
        elif config.LLM_PROVEEDOR == 'ollama':
            crudo = _ollama(sistema, mensaje, temperatura, max_tokens, esquema)
        else:
            raise ErrorLLM(f'Proveedor desconocido: {config.LLM_PROVEEDOR}')

        contador['llamadas'] += 1
        ultimo = crudo
        truncada = bool(_ultima_truncada[0])
        try:
            datos = json.loads(_limpiar(crudo))
        except json.JSONDecodeError as e:
            if truncada:
                motivos = [f'La salida quedo cortada por el limite de {max_tokens} tokens y el '
                           f'JSON llego incompleto ({e}). Respondé mas breve.']
            else:
                motivos = [f'La respuesta no es JSON valido ({e}).']
        else:
            motivos = list(validador(datos)) if validador else []
            if not motivos:
                seg = time.time() - inicio
                contador['segundos'] += seg
                return RespuestaLLM(crudo, datos, seg, intento,
                                    config.LLM_PROVEEDOR, modelo_en_uso())

        mensaje = (f'{usuario}\n\nATENCION: tu respuesta anterior fue RECHAZADA por estos '
                   f'motivos:\n- ' + '\n- '.join(motivos) +
                   '\nRespondé de nuevo SOLO con el objeto JSON, corrigiendo eso.')

    seg = time.time() - inicio
    contador['segundos'] += seg
    # Se devuelven los motivos del ultimo rechazo: quedan en la traza y explican el
    # texto de respaldo (A6) en lugar de un "respaldo" sin causa.
    return RespuestaLLM(ultimo, None, seg, reintentos + 1,
                        config.LLM_PROVEEDOR, modelo_en_uso(), motivos, truncada)


def modelo_en_uso():
    """Modelo que se va a usar. Con gemini y LLM_MODELO vacio es el primer
    candidato: si no tiene cupo gratuito, en la primera llamada se pasa al siguiente."""
    if config.LLM_PROVEEDOR == 'gemini' and not config.LLM_MODELO:
        if _modelo_gemini:
            return _modelo_gemini
        try:
            return _elegir_modelo_gemini() + ' (a confirmar en la primera llamada)'
        except ErrorLLM:
            return '(sin determinar: falta la clave o no hay conexión)'
    return config.modelo()


def disponible():
    """Comprobacion rapida para el --check, sin gastar una llamada larga."""
    try:
        r = pedir_json('Respondé solo con JSON.', 'Devolvé {"ok": true}', max_tokens=40)
        return bool(r.datos), None
    except ErrorLLM as e:
        return False, str(e)
