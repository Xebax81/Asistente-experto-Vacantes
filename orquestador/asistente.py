"""Orquestador del asistente integrado (PG3).

Es el "punto de entrada comun" que pide la consigna: una sola funcion responder()
que recibe el texto del usuario, lo enruta con el PROMPT MAESTRO al submodulo que
corresponde y devuelve la respuesta junto con la traza completa.

La cadena completa (S1 -> S2 -> S3 -> S4) es lo que convierte al PG3 en un sistema
y no en cuatro scripts: un pedido escrito por un supervisor se interpreta, se
registra, se evaluan los empleados, se calcula la afinidad, se clasifica y se
explica el listado, todo en una sola consulta del usuario.

El enrutamiento lo decide el LLM con el prompt maestro, pero NINGUNA decision del
dominio pasa por el: el LLM solo dice "esto es para S2"; que haya o no candidatos,
quien queda afuera y con que prioridad lo deciden las reglas y el grafo.
"""
import json
import re
from datetime import datetime

from core import config, prompts
from core.grafo import ErrorGrafo, Grafo, Traza
from core.llm import ErrorLLM, pedir_json
from submodulos import inferencia, s1_requisitos, s2_aptitud, s3_afinidad, s4_explicacion

# 'pedido_cobertura' es la intencion vigente; 'S1_requisitos' y 'cadena_completa'
# se aceptan por compatibilidad con prompts maestros anteriores y van al mismo lugar.
SUBMODULOS = ('pedido_cobertura', 'continuacion_pedido', 'S2_aptitud', 'S3_afinidad',
              'S4_explicacion', 'S1_requisitos', 'cadena_completa', 'fuera_de_dominio')
PEDIDO = ('pedido_cobertura', 'S1_requisitos', 'cadena_completa')

# Memoria minima de la conversacion: el ultimo pedido que quedo en espera.
# Sin esto el sistema hace una pregunta de aclaracion y no puede recibir la respuesta,
# porque cada consulta se procesa aislada. Solo se recuerda un pedido pendiente por
# sesion; cuando se completa o el usuario cambia de tema, se olvida.
_pendiente = {}


def pedido_pendiente(sesion='web'):
    return _pendiente.get(sesion)


def recordar_pendiente(sesion, texto, preguntas, rechazados=None):
    _pendiente[sesion] = {'texto': texto, 'preguntas': list(preguntas or []),
                          'rechazados': list(rechazados or [])}


def _fragmentos_rechazados(ficha):
    """Fragmentos que el usuario escribió y S1 no pudo resolver (p. ej. la zona «Chacras»).

    Se guardan para reemplazarlos por la respuesta de aclaración: si solo se agregara
    la respuesta al final, el texto seguiría diciendo «Chacras» y S1 volvería a rechazarla.
    """
    frags = []
    for v in (ficha or {}).get('vacantes', []):
        z = v.get('zona') or {}
        if z.get('resolucion') == 'no_reconocida' and z.get('texto_informado'):
            frags.append(z['texto_informado'])
        for campo in ('servicio', 'turno'):
            d = v.get(campo) or {}
            if not d.get('nombre') and d.get('texto'):
                frags.append(d['texto'])
    return list(dict.fromkeys(frags))


_PREFIJOS_RESPUESTA = re.compile(
    r'^(?:(?:es|en|para|sería|seria)\s+)*(?:(?:la|el)\s+)?(?:(?:zona|servicio|sede|turno)\s+)?(?:(?:de|es|en)\s+)*',
    re.IGNORECASE)


def _texto_completado(pendiente, respuesta):
    """Une el pedido en espera con la respuesta de aclaración.

    Si había un único fragmento rechazado y la respuesta es corta, se reemplaza ese
    fragmento por la respuesta («zona de Chacras» -> «zona de Godoy Cruz»). En otro caso
    (faltaba un dato que el pedido no mencionaba) se agrega la respuesta al final.
    """
    original = pendiente['texto']
    rechazados = pendiente.get('rechazados') or []
    dato = _PREFIJOS_RESPUESTA.sub('', respuesta.strip()).strip(' .,;')
    if len(rechazados) == 1 and dato and len(dato.split()) <= 6 and rechazados[0] in original:
        return original.replace(rechazados[0], dato, 1)
    return f'{original} {respuesta}'


def olvidar_pendiente(sesion='web'):
    _pendiente.pop(sesion, None)


def reiniciar_sesion(sesion='web'):
    """Botón «Empezar de nuevo»: olvida el pedido y la consulta en espera (PG3, B02)."""
    _pendiente.pop(sesion, None)
    _consulta_pendiente.pop(sesion, None)


# PG3 (pruebas 13/11, B02): S2, S3 y S4 preguntan «¿A cuál te referís?» cuando hay varias
# vacantes del mismo servicio, pero la respuesta («pv_001») llegaba sin la pregunta
# original y el prompt maestro no sabía qué hacer con ella. Se recuerda la consulta que
# quedó esperando la elección y, si el mensaje siguiente parece la respuesta, se vuelve
# a correr la misma consulta con el dato agregado. Igual que con los pedidos, solo una
# por sesión y se olvida apenas se usa o se cambia de tema.
_consulta_pendiente = {}
DESTINOS_CONSULTA = ('S2_aptitud', 'S3_afinidad', 'S4_explicacion')
_ID_PUESTO = re.compile(r'\bpv_\w+', re.IGNORECASE)


def _parece_respuesta(texto):
    """Un id de puesto, o un mensaje corto que no es una pregunta nueva."""
    t = texto.strip()
    return bool(_ID_PUESTO.search(t)) or (len(t.split()) <= 6 and '?' not in t)


def _consulta_completada(pendiente, respuesta):
    ids = _ID_PUESTO.findall(respuesta)
    dato = f'el puesto {ids[0]}' if ids else respuesta.strip().rstrip('.')
    return f"{pendiente['texto'].rstrip(' ?¿.')} (en {dato})?"


def _esquema_ok(d):
    if not isinstance(d, dict):
        return ['La respuesta no es un objeto JSON.']
    if d.get('submodulo') not in SUBMODULOS:
        return [f'"submodulo" tiene que ser uno de: {", ".join(SUBMODULOS)}.']
    return []


def enrutar(grafo, texto, pendiente=None):
    """Prompt maestro: decide a que submodulo va la consulta.

    Si hay un pedido en espera se lo cuenta, para que pueda reconocer que el
    mensaje contesta la pregunta de aclaracion en lugar de ser un tema nuevo.
    """
    sistema = prompts.cargar('maestro')
    mensaje = f'Mensaje: "{texto}"'
    if pendiente:
        preguntas = ' '.join(pendiente.get('preguntas') or []) or 'un dato que falta'
        mensaje = (f'CONTEXTO: hay un pedido de cobertura en espera. '
                   f'El sistema preguntó: «{preguntas}»\n{mensaje}')
    r = pedir_json(sistema, mensaje, validador=_esquema_ok)
    grafo.traza.agregar('enrutamiento', {'submodulo': 'maestro', **r.como_dict()})
    if r.datos is None:
        return {'submodulo': 'fuera_de_dominio', 'confianza': 'baja', 'motivo': None,
                'enrutamiento_fallido': True,   # PG3 (B11)
                'servicio_texto': None, 'turno_texto': None, 'puesto_id_texto': None,
                'empleados_texto': [], 'texto_no_interpretado': [texto]}
    return r.datos


# ==================================================================== cadena E2E
def cadena_completa(grafo, texto):
    """S1 -> S2 -> S3 -> S4 en una sola pasada. Es la prueba de integracion
    que pide la consigna ("deben cruzar informacion de varios submodulos")."""
    etapas = []

    # --- S1 : interpretar el pedido y registrar el puesto
    r1 = s1_requisitos.responder(grafo, texto, registrar_en_grafo=True)
    if 'ficha' not in r1:
        # S1 no pudo interpretar el pedido (JSON inválido tras el reintento): se corta acá.
        etapas.append({'submodulo': 'S1', 'estado': 'sin_interpretar'})
        return {'submodulo': 'cadena_completa', 'etapas': etapas, 'corte': 'S1',
                'respuesta': r1.get('error') or 'No se pudo interpretar el pedido.',
                'motivo_corte': 'S1 no pudo interpretar el pedido'}
    fidelidad = {'S1': r1.get('fidelidad')}
    etapas.append({'submodulo': 'S1', 'estado': r1['ficha']['pedido']['estado'],
                   'faltantes': r1['ficha']['pedido'].get('campos_faltantes', []),
                   'puestos': r1.get('puestos_registrados', [])})
    if r1['ficha']['pedido']['estado'] != 'completo':
        # PG3 (B14): se devuelve la validación de S1 para que la interfaz la muestre.
        return {'submodulo': 'cadena_completa', 'etapas': etapas, 'respuesta': r1['respuesta'],
                'ficha_s1': r1['ficha'], 'corte': 'S1', 'fidelidad': fidelidad,
                'motivo_corte': 'el pedido quedó en espera de datos'}
    puestos = r1.get('puestos_registrados') or []
    if not puestos:
        return {'submodulo': 'cadena_completa', 'etapas': etapas, 'respuesta': r1['respuesta'],
                'ficha_s1': r1['ficha'], 'corte': 'S1',
                'motivo_corte': 'no se registró ningún puesto'}

    partes, listados = [r1['respuesta']], []
    for puesto in puestos:
        # --- S2 : aptitud y disponibilidad
        f2 = s2_aptitud.evaluar_puesto(grafo, puesto)
        if f2 is None:
            # El puesto se registró pero no se pudo releer: no se sigue en silencio.
            etapas.append({'submodulo': 'S2', 'puesto': puesto, 'error': 'no se pudo leer el puesto'})
            partes.append(f'El puesto {puesto} quedó registrado, pero no se pudo recuperar para '
                          'evaluarlo. Revisá la conexión con Neo4j y volvé a consultarlo.')
            continue
        if config.ESCRITURA_HABILITADA:
            s2_aptitud.registrar(grafo, f2)
        etapas.append({'submodulo': 'S2', 'puesto': puesto,
                       'validos': f2['evaluacion']['n_validos'],
                       'descartados': f2['evaluacion']['n_descartados'],
                       'motivo_critico': f2['evaluacion']['motivo_critico'],
                       # Detalle para la trazabilidad y para las pruebas E2E.
                       'validos_legajos': [r['legajo'] for r in f2['evaluacion']['validos']],
                       'descartes': [{'legajo': r['legajo'],
                                      'motivos': [{'motivo': m['motivo'], 'regla': m['regla']}
                                                  for m in r['motivos']]}
                                     for r in f2['evaluacion']['descartados']],
                       'conteo_motivos': f2['evaluacion']['conteo_motivos']})

        evaluados = f2['evaluacion']['n_validos'] + f2['evaluacion']['n_descartados']
        if not f2['evaluacion']['n_validos']:
            # S2-R09 + regla A3: no hay nadie; S4 informa el listado vacío sin LLM.
            inferencia.recalcular_puesto(grafo, puesto, persistir=config.ESCRITURA_HABILITADA)
            etapas.append({'submodulo': 'S4', 'puesto': puesto, 'regla': 'A3'})
            partes.append(s4_explicacion.mensaje_listado_vacio(grafo, puesto, evaluados=evaluados))
            fidelidad.setdefault('S4', []).append('sin LLM (A3)')
            continue

        # PG3 (pruebas 13/11, B06): S1 informa las aptitudes tal como las pidió el pedido;
        # S2 agrega las que exige el tipo de servicio (S2-R01). Se avisa para que la
        # aptitud «deseable» de S1 no parezca contradecir los descartes de S2.
        promovidas = [r for r in (f2.get('requisitos') or {}).get('excluyentes', [])
                      if r.get('origen') == 'catalogo' or r.get('promovida')]
        if promovidas:
            nombres = ', '.join(s4_explicacion.legible(r['aptitud']) for r in promovidas)
            partes.append(f'Requisito del tipo de servicio (S2-R01): {nombres} es excluyente '
                          'para este puesto aunque el pedido no la haya pedido así, por eso '
                          'S2 descarta a quien no la tiene vigente.')

        # --- S3 + S4 : afinidad, categoria y listado final
        inf = inferencia.recalcular_puesto(grafo, puesto, persistir=config.ESCRITURA_HABILITADA)
        if inf.get('error'):
            # PG3 (pruebas 13/11, B01): antes el error se ignoraba y S4 terminaba diciendo
            # «No hay candidatos válidos… Se evaluaron 0 empleados», aunque S2 sí los tenía.
            validos = ', '.join(f"{r.get('nombre') or r['legajo']} ({r['legajo']})"
                                for r in f2['evaluacion']['validos'])
            etapas.append({'submodulo': 'S3', 'puesto': puesto, 'error': inf['error']})
            partes.append(f'Para el puesto {puesto}, S2 dejó como válidos a: {validos}. '
                          f"No se pudo calcular la afinidad ni el orden: {inf['error']}")
            continue
        etapas.append({'submodulo': 'S3', 'puesto': puesto, 'n_validos': inf.get('n_validos'),
                       'version': inf.get('version_s3')})
        etapas.append({'submodulo': 'S4', 'puesto': puesto, 'listado': inf.get('listado'),
                       'criterio_orden': inf.get('criterio_orden'), 'version': inf.get('version_s4')})

        # --- S4 : explicar el listado recien calculado
        r4 = s4_explicacion.responder(grafo, f'¿A quién me recomiendan para {puesto}?',
                                      extraido={'intencion': 'consultar_listado',
                                                'puesto_id': puesto, 'servicio': None, 'turno': None,
                                                'empleado': None, 'legajo': None,
                                                'filtros': {'categoria': None,
                                                            'solo_con_advertencias': False},
                                                'aspectos': ['orden']})
        partes.append(r4['respuesta'])
        fidelidad.setdefault('S4', []).append(r4.get('fidelidad'))
        fichas = ((r4.get('datos') or {}).get('fichas')) or []
        if fichas:
            listados.append({'puesto': puesto, 'servicio': fichas[0].get('servicio'),
                             'fichas': fichas})

    return {'submodulo': 'cadena_completa', 'etapas': etapas, 'puestos': puestos,
            'listados': listados, 'ficha_s1': r1['ficha'], 'fidelidad': fidelidad,
            'respuesta': '\n\n'.join(partes)}


# ==================================================================== entrada unica
def responder(texto, grafo=None, traza=None, sesion='web'):
    """Punto de entrada unico del asistente. Devuelve dict con respuesta + traza."""
    propio = grafo is None
    traza = traza or Traza()
    if grafo is None:
        try:
            grafo = Grafo(traza)
        except ErrorGrafo as e:
            # Sin base de conocimiento no se responde nada del dominio: se avisa por qué.
            return {'submodulo': 'error', 'respuesta': str(e), 'traza': traza.como_dict(),
                    'pregunta': texto, 'segundos': 0}
    inicio = datetime.now()
    pendiente = pedido_pendiente(sesion)
    consulta_previa = _consulta_pendiente.pop(sesion, None)
    texto_efectivo = texto
    try:
        if consulta_previa and _parece_respuesta(texto):
            # B02: se responde la aclaración pendiente sin volver a enrutar.
            texto_efectivo = _consulta_completada(consulta_previa, texto)
            ruta = {'submodulo': consulta_previa['destino'], 'confianza': 'alta',
                    'motivo': 'respuesta_a_aclaracion'}
            traza.agregar('continuacion', {
                'submodulo': 'maestro', 'consulta_original': consulta_previa['texto'],
                'dato_aportado': texto, 'texto_reinterpretado': texto_efectivo})
        else:
            ruta = enrutar(grafo, texto, pendiente)
        destino = ruta['submodulo']

        if destino == 'continuacion_pedido':
            if not pendiente:
                destino = 'fuera_de_dominio'
            else:
                # Se reinterpreta el pedido original junto con el dato nuevo: asi
                # S1 vuelve a aplicar sus reglas sobre el texto completo y no hay
                # que mantener un estado parcial de la ficha.
                texto_efectivo = _texto_completado(pendiente, texto)
                destino = 'pedido_cobertura'
                traza.agregar('continuacion', {
                    'submodulo': 'maestro',
                    'pedido_original': pendiente['texto'],
                    'dato_aportado': texto,
                    'texto_reinterpretado': texto_efectivo})

        if destino == 'fuera_de_dominio':
            if ruta.get('enrutamiento_fallido'):
                # B11: el prompt maestro no devolvió un JSON válido; no es culpa del usuario.
                respuesta = ('No pude interpretar la consulta. ¿Podés reformularla en una o dos '
                             'oraciones? Por ejemplo: «Necesito cubrir el turno tarde en el Hospital '
                             'Central para mañana» o «¿Por qué quedó afuera Bruno Gómez en pv_001?».')
            elif ruta.get('submodulo') == 'continuacion_pedido':
                # B18: parecía la respuesta a una pregunta, pero no hay pedido esperando.
                respuesta = ('No hay ningún pedido esperando un dato. Si querés registrar uno, '
                             'escribí el pedido completo: servicio, turno y para cuándo.')
            elif ruta.get('motivo') == 'cambio_de_decision':
                respuesta = ('No puedo cambiar categorías, prioridades ni el orden: los asigna la '
                             'base de conocimiento. Sí puedo explicarte en qué se apoya cada '
                             'decisión registrada.')
            else:
                respuesta = ('Tu consulta no parece referirse a la cobertura de vacantes internas. '
                             'Puedo registrar un pedido de cobertura, decirte quién puede cubrir un '
                             'puesto, explicar la afinidad de un candidato o el listado final.')
            resultado = {'submodulo': 'fuera_de_dominio', 'respuesta': respuesta}

        elif (ruta.get('confianza') == 'baja'
              and destino in ('S2_aptitud', 'S3_afinidad', 'S4_explicacion')):
            # El prompt maestro dudó entre submódulos de consulta. En lugar de elegir uno
            # y contestar otra cosa, se pregunta: es lo que el prompt maestro promete
            # («con confianza baja el sistema puede pedir una aclaración»). Los pedidos de
            # cobertura no entran acá: S1 ya pide los datos que falten.
            resultado = {
                'submodulo': 'aclaracion', 'aclaracion': True, 'confianza_baja': True,
                'destino_probable': destino,
                'respuesta': ('No estoy seguro de qué querés saber. ¿Es sobre quién puede cubrir '
                              'la vacante y por qué alguien quedó afuera (aptitud y disponibilidad), '
                              'sobre la afinidad de un candidato o el orden entre candidatos, o sobre '
                              'la recomendación final y su explicación? Si podés, nombrá también '
                              'el servicio o el puesto.')}
        elif destino in PEDIDO:
            # Todo pedido de cobertura recorre la cadena y termina en candidatos.
            # Si S1 lo deja en espera, la cadena se corta sola y devuelve las preguntas.
            resultado = cadena_completa(grafo, texto_efectivo)
        elif destino == 'S2_aptitud':
            resultado = _responder_s2(grafo, texto_efectivo)
        elif destino == 'S3_afinidad':
            resultado = s3_afinidad.responder(grafo, texto_efectivo)
        else:
            resultado = s4_explicacion.responder(grafo, texto_efectivo)

        # B02: si un submódulo de consulta pidió elegir el puesto o la persona, se
        # recuerda la consulta para completar la próxima respuesta.
        if resultado.get('aclaracion') and destino in DESTINOS_CONSULTA:
            _consulta_pendiente[sesion] = {'texto': texto_efectivo, 'destino': destino}

        resultado['enrutamiento'] = ruta

        # Se recuerda el pedido solo mientras siga faltando un dato.
        espera = next((e for e in resultado.get('etapas', [])
                       if e.get('submodulo') == 'S1' and e.get('estado') == 'en_espera'), None)
        if espera:
            ficha = (resultado.get('ficha_s1') or {}).get('pedido', {})
            recordar_pendiente(sesion, texto_efectivo, ficha.get('preguntas_aclaracion'),
                               _fragmentos_rechazados(resultado.get('ficha_s1')))
            resultado['esperando_dato'] = ficha.get('campos_faltantes')
        elif destino != 'fuera_de_dominio':
            olvidar_pendiente(sesion)
    except ErrorLLM as e:
        resultado = {'submodulo': 'error', 'respuesta': f'No se pudo contactar al modelo de lenguaje: {e}'}
    except Exception as e:
        resultado = {'submodulo': 'error', 'respuesta': f'Error del sistema: {e}'}
    finally:
        if propio:
            grafo.cerrar()

    resultado['traza'] = traza.como_dict()
    resultado['segundos'] = round((datetime.now() - inicio).total_seconds(), 2)
    resultado['pregunta'] = texto
    if config.GUARDAR_TRAZAS:
        _guardar(resultado)
    return resultado


def _responder_s2(grafo, texto):
    """S2 con su propio prompt de extraccion (intenciones del PI4 de Cayo)."""
    catalogo, _ = s1_requisitos.catalogos(grafo)
    r = s2_aptitud.extraer(grafo, texto, catalogo)
    if r.datos is None:
        return {'submodulo': 'S2', 'respuesta': 'No pude interpretar la consulta. ¿Podés reformularla?'}
    grafo.traza.agregar('extraccion', {'submodulo': 'S2', **r.como_dict()})
    d = r.datos
    if d['intencion'] == 'fuera_de_alcance':
        return {'submodulo': 'S2', 'intencion': d['intencion'],
                'respuesta': 'La consulta no corresponde a la evaluación de aptitud y disponibilidad. '
                             'En este módulo puedo responder quién puede cubrir un puesto, por qué '
                             'alguien quedó afuera, si una certificación está vigente o qué exige un puesto.'}

    if d['intencion'] == 'aptitud_vigente' and d.get('aptitud_candidato_catalogo'):
        filas = grafo.leer('S2-Q6-aptitud-vigente', aptitud=d['aptitud_candidato_catalogo'])
        ficha = s2_aptitud.ficha_aptitud(filas, d['aptitud_candidato_catalogo'])
        texto_resp, r2, fiel = s2_aptitud.explicar(grafo, ficha, d['intencion'])
        return {'submodulo': 'S2', 'intencion': d['intencion'], 'ficha': ficha,
                'respuesta': texto_resp, 'fidelidad': 'OK' if fiel else 'respaldo (A6)'}

    puesto, aclaracion = s4_explicacion.resolver_puesto(
        grafo, d.get('puesto_id_texto'), d.get('servicio_texto'), None)
    if aclaracion:
        return {'submodulo': 'S2', 'respuesta': aclaracion, 'aclaracion': True}

    legajos = None
    if d.get('empleado_texto'):
        fila = grafo.una('S2-Q3-empleado',
                         texto=s2_aptitud.normalizar(d['empleado_texto']))
        cands = (fila or {}).get('fuertes') or (fila or {}).get('candidatos') or []
        if len(cands) == 1:
            legajos = [cands[0]['legajo']]
        elif len(cands) > 1:
            return {'submodulo': 'S2', 'aclaracion': True,
                    'respuesta': '¿A cuál te referís? ' + ', '.join(
                        f"{c['nombre']} ({c['legajo']})" for c in cands)}
        else:
            return {'submodulo': 'S2', 'aclaracion': True,
                    'respuesta': f"No encontré a «{d['empleado_texto']}» entre los empleados."}

    ficha = s2_aptitud.evaluar_puesto(grafo, puesto['puesto'], legajos)
    if ficha is None:
        return {'submodulo': 'S2', 'respuesta': 'No se pudo evaluar el puesto.'}
    ficha['consulta'] = {'estado': 'resuelta', 'intencion': d['intencion'],
                         'filtro_estado': d.get('filtro_estado'),
                         'pide_orden_o_recomendacion': d.get('pide_orden_o_recomendacion', False)}
    texto_resp, r2, fiel = s2_aptitud.explicar(grafo, ficha, d['intencion'])
    grafo.traza.agregar('explicacion', {'submodulo': 'S2',
                                        'fidelidad': 'OK' if fiel else 'respaldo', **r2.como_dict()})
    return {'submodulo': 'S2', 'intencion': d['intencion'], 'ficha': ficha,
            'respuesta': texto_resp, 'fidelidad': 'OK' if fiel else 'respaldo (A6)'}


def _guardar(resultado):
    try:
        config.DIR_TRAZAS.mkdir(exist_ok=True)
        # PG3 (B13): con microsegundos; antes dos consultas en el mismo segundo se pisaban.
        nombre = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
        (config.DIR_TRAZAS / nombre).write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    except OSError:
        pass
