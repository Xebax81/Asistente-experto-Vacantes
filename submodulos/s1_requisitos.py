"""Submodulo S1 — Extraccion y Estructuracion de Requisitos de Vacante (Arguello).

Flujo del PI4, sin cambios de criterio: texto -> extraccion con LLM -> consultas
Cypher fijas -> reglas S1-R01..R10 + inferencia difusa de urgencia -> ficha S1 ->
explicacion con LLM -> validacion de fidelidad.

Novedad del PG3: `registrar()` escribe el Pedido_Cobertura y el Puesto_Vacante en
el grafo (lo que en el PI4 era la opcion --registrar), porque es el punto de
entrada de la cadena S1 -> S2 -> S3 -> S4.
"""
import re
from datetime import date, datetime, timedelta

from core import config, prompts
from core.prompts import PromptFaltante
from core.grafo import normalizar
from core.llm import ErrorLLM, pedir_json
from core.motor_difuso import s1_urgencia
from core.validador import validar_explicacion, validar_urgencia_s1, validar_zona_s1

# Devolución de la cátedra al PI4 de S1: el texto mezclaba los estados de la zona
# («no se reconoció ni se informó»). Cada estado tiene ahora su frase, y el validador
# comprueba que la explicación use la del estado correcto.
FRASES_ZONA = {
    'declarada': 'indicada en el pedido',
    'heredada': 'tomada del servicio porque el pedido no la indica',
    'no_reconocida': 'no está en el catálogo de zonas',
    'sin_dato': 'se determinará cuando se indique el servicio',
}

# ---------------------------------------------------------------------------
# Piezas del PI4 de S1 (s1_orquestador.py) que se habían perdido al integrar.
# Sin ellas, el caso C2 del PI4 («sí o sí … dentro de 5 días») daba otro resultado
# que en el PI4: la aptitud no quedaba excluyente y el plazo no se reconocía.

# Marcadores de exigencia de S1-R02 (provisionales). Se usan los del grafo
# (Regla_Crisp S1-R02.marcadores, ver neo4j/S1_PI4_complemento.cypher); si el
# grafo no los tiene, estos. Antes, sin el complemento, la lista quedaba vacía y
# ningún marcador podía volver excluyente una aptitud.
MARCADORES_DEFECTO = ['excluyente', 'indispensable', 'obligatorio', 'obligatoria', 'imprescindible',
                      'si o si', 'tiene que tener', 'debe tener', 'es requisito', 'sin excepcion']

# El diccionario de urgencia está escrito en palabras («dentro de cinco días»).
NUMEROS = {'1': 'un', '2': 'dos', '3': 'tres', '4': 'cuatro', '5': 'cinco', '6': 'seis',
           '7': 'siete', '8': 'ocho', '9': 'nueve', '10': 'diez'}
RELLENO_URGENCIA = ['lo necesito ', 'lo necesitamos ', 'necesito ', 'necesitamos ', 'que sea ',
                    'a mas tardar ', 'como maximo ', 'es ', 'muy ', 'y ', 'o ']


def _norm_signos(texto):
    """normalizar() + sin signos de puntuación y con espacios simples."""
    import re
    t = normalizar(texto)
    if t is None:
        return None
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def nucleo_urgencia(texto):
    """Como en el PI4: dígitos 1..10 en palabras y sin muletillas iniciales.
    'Es urgente, dentro de 5 días' -> 'urgente dentro de cinco dias'."""
    t = _norm_signos(texto)
    if t is None:
        return None
    t = ' '.join(NUMEROS.get(w, w) for w in t.split())
    cambio = True
    while cambio:
        cambio = False
        for r in RELLENO_URGENCIA:
            if t.startswith(r):
                t, cambio = t[len(r):], True
    return t.strip()


PREGUNTAS = {
    'servicio': '¿Para qué servicio o sede es la cobertura?',
    'turno': '¿En qué turno?',
    'zona': '¿En qué zona o departamento es?',
    # PG3 (pruebas 13/11, B01): sin urgencia S3 no puede calcular la afinidad.
    'plazo': ('¿Para cuándo se necesita cubrir la vacante? Por ejemplo: hoy, para mañana, '
              'dentro de tres días o la semana que viene.'),
}

# PG3 (pruebas 13/11, B08): plazos que el diccionario del grafo no tiene. Se calculan en
# código, de forma determinística, y quedan marcados con su fuente para la trazabilidad.
DIAS_SEMANA = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
CANTIDADES = {'un': 1, 'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
              'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'quince': 15}


def _fecha_ref():
    if config.FECHA_EVALUACION:
        return date.fromisoformat(config.FECHA_EVALUACION)
    return date.today()


def _expresion_calendario(texto, hoy=None):
    """Interpreta un plazo que no está en el diccionario de urgencia del grafo.

    Devuelve una entrada con la misma forma que las del diccionario (tipo, valor,
    unidad) o None. Cubre: «para ayer» (premura máxima, como «de inmediato»), días de
    la semana («para el lunes»), «dentro de / en N días|horas|semanas» y fechas dd/mm.
    """
    t = _norm_signos(texto or '')
    if not t:
        return None
    hoy = hoy or _fecha_ref()
    base = {'fuente': 'calendario_PG3', 'estado_validacion': 'provisional'}

    if re.search(r'\b(para )?ayer\b', t):
        return {**base, 'texto': 'para ayer', 'tipo': 'premura', 'valor': 10, 'unidad': 'puntos'}

    m = re.search(r'\b(?:dentro de|en|en los proximos|en las proximas)\s+(\d+|' +
                  '|'.join(CANTIDADES) + r')\s+(hora|horas|dia|dias|semana|semanas)\b', t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else CANTIDADES[m.group(1)]
        unidad = m.group(2)
        horas = n * (1 if unidad.startswith('hora') else 24 if unidad.startswith('dia') else 168)
        return {**base, 'texto': m.group(0), 'tipo': 'plazo', 'valor': horas, 'unidad': 'h'}

    m = re.search(r'\b(' + '|'.join(DIAS_SEMANA) + r')\b', t)
    if m:
        dias = (DIAS_SEMANA.index(m.group(1)) - hoy.weekday()) % 7 or 7
        return {**base, 'texto': m.group(0), 'tipo': 'plazo', 'valor': dias * 24, 'unidad': 'h'}

    m = re.search(r'\b(\d{1,2})\s+(\d{1,2})(?:\s+(\d{2,4}))?\b', t) if '/' in (texto or '') else None
    if m:
        try:
            anio = int(m.group(3)) if m.group(3) else hoy.year
            anio = anio + 2000 if anio < 100 else anio
            f = date(anio, int(m.group(2)), int(m.group(1)))
            if not m.group(3) and f < hoy - timedelta(days=1):
                f = date(anio + 1, f.month, f.day)
            horas = max((f - hoy).days, 0) * 24 or 8      # vencida o para hoy: como «hoy»
            return {**base, 'texto': m.group(0).replace(' ', '/'), 'tipo': 'plazo',
                    'valor': horas, 'unidad': 'h'}
        except ValueError:
            return None
    return None


def _con_opciones(pregunta, opciones, maximo=8):
    """Una pregunta de aclaración sin opciones obliga a adivinar. Se listan las
    que el grafo tiene cargadas, que es la única respuesta que el sistema acepta."""
    opciones = [o for o in (opciones or []) if o]
    if not opciones:
        return pregunta
    visibles = opciones[:maximo]
    cola = '' if len(opciones) <= maximo else f' (y {len(opciones) - maximo} más)'
    return f"{pregunta} Las opciones registradas son: {', '.join(visibles)}{cola}."



def _esquema_ok(d):
    motivos = []
    if not isinstance(d, dict):
        return ['La respuesta no es un objeto JSON.']
    if not isinstance(d.get('es_pedido_cobertura'), bool):
        motivos.append('Falta "es_pedido_cobertura" (true o false).')
    if not isinstance(d.get('vacantes'), list):
        motivos.append('Falta la lista "vacantes".')
    for clave in ('aptitudes', 'expresiones_urgencia', 'texto_no_interpretado'):
        if not isinstance(d.get(clave, []), list):
            motivos.append(f'"{clave}" tiene que ser una lista.')
    return motivos


def catalogos(grafo):
    fila = grafo.una('S1-Q0-catalogos') or {}
    apt = ', '.join(a['nombre'] for a in fila.get('aptitudes', []))
    exp = ', '.join(f"{e['texto']} ({e['tipo']} {e['valor']} {e.get('unidad') or ''})".strip()
                    for e in fila.get('expresiones', []) if e.get('texto'))
    tur = ', '.join(f"{t['nombre']} {t.get('inicio','')}-{t.get('fin','')}" for t in fila.get('turnos', []))
    ser = ', '.join(s['nombre'] for s in fila.get('servicios', []))
    return {'aptitudes': apt, 'expresiones': exp, 'turnos': tur, 'servicios': ser,
            'zonas_lista': sorted(fila.get('zonas') or []),
            'servicios_lista': sorted(s['nombre'] for s in fila.get('servicios', []) if s.get('nombre')),
            'turnos_lista': [t['nombre'] for t in fila.get('turnos', []) if t.get('nombre')],
            'aptitudes_lista': sorted(a['nombre'] for a in fila.get('aptitudes', []) if a.get('nombre')),
            }, fila


def extraer(grafo, texto):
    cat, crudo = catalogos(grafo)
    sistema = prompts.cargar('s1_extraccion', aptitudes=cat['aptitudes'],
                             expresiones=cat['expresiones'], turnos=cat['turnos'])
    r = pedir_json(sistema, f'Pedido: "{texto}"', validador=_esquema_ok)
    if r.datos is None:
        return None, r, cat

    # Anclaje al texto: todo fragmento tiene que figurar en el pedido original.
    plano = normalizar(texto)
    advertencias = []

    def anclado(fragmento):
        if not fragmento:
            return None
        if normalizar(fragmento) in plano:
            return fragmento
        advertencias.append(f'El modelo devolvió «{fragmento}», que no figura en el pedido: se descarta.')
        return None

    d = r.datos
    for v in d.get('vacantes', []):
        v['servicio_texto'] = anclado(v.get('servicio_texto'))
        v['turno_texto'] = anclado(v.get('turno_texto'))
    d['zona_texto'] = anclado(d.get('zona_texto'))
    d['relajacion_zona_texto'] = anclado(d.get('relajacion_zona_texto'))
    d['aptitudes'] = [a for a in d.get('aptitudes', []) if anclado(a.get('texto'))]
    d['expresiones_urgencia'] = [e for e in d.get('expresiones_urgencia', []) if anclado(e.get('texto'))]
    d['_advertencias'] = advertencias
    return d, r, cat


def construir_ficha(grafo, texto, extraido, catalogo=None):
    """Aplica S1-R01 a S1-R10 y la inferencia de urgencia. Devuelve la ficha S1."""
    advertencias = list(extraido.get('_advertencias', []))
    ficha = {'texto_original': texto, 'pedido': {}, 'vacantes': [], 'aptitudes': [],
             'urgencia': {}, 'advertencias': advertencias,
             'texto_no_interpretado': extraido.get('texto_no_interpretado', [])}

    if not extraido.get('es_pedido_cobertura'):
        ficha['pedido'] = {'estado': 'no_es_pedido', 'campos_faltantes': [],
                           'preguntas_aclaracion': [], 'regla': 'S1-R01'}
        return ficha

    # ---------------------------------------------------- servicio, turno, zona
    vacantes = extraido.get('vacantes') or [{'servicio_texto': None, 'turno_texto': None}]
    servicios = [{'texto': v['servicio_texto'], 'norm': normalizar(v['servicio_texto'])}
                 for v in vacantes if v.get('servicio_texto')]
    res_serv = {f['texto']: f for f in grafo.leer('S1-Q2-servicio', servicios=servicios)} if servicios else {}

    turnos = [{'texto': v['turno_texto'], 'norm': normalizar(v['turno_texto'])}
              for v in vacantes if v.get('turno_texto')]
    res_turno = {f['texto']: f for f in grafo.leer('S1-Q4-turno', turnos=turnos)} if turnos else {}

    zona_txt = extraido.get('zona_texto')
    zona_param = {'texto': zona_txt, 'norm': normalizar(zona_txt)} if zona_txt else None

    faltantes, vistas = set(), set()
    for v in vacantes:
        serv = res_serv.get(v.get('servicio_texto'), {})
        nombre_serv = (serv.get('servicio') or {}).get('nombre') if serv.get('servicio') else None
        turno = res_turno.get(v.get('turno_texto'), {})
        coinc = turno.get('coincidencias') or []
        nombre_turno = coinc[0]['nombre'] if len(coinc) == 1 else None

        # S1-R07: zona no informada -> se hereda del servicio; informada y no reconocida -> aclaracion.
        zfila = grafo.una('S1-Q3-zona', servicio=nombre_serv, zona=zona_param) or {}
        resolucion = zfila.get('resolucion')
        if resolucion == 'heredada':
            zona = {'nombre': zfila.get('zona_servicio'), 'origen': 'inferido',
                    'resolucion': 'heredada', 'regla': 'S1-R07',
                    'frase': FRASES_ZONA['heredada'], 'texto_informado': None}
        elif resolucion == 'declarada':
            zona = {'nombre': (zfila.get('reconocidas') or [None])[0], 'origen': 'declarado',
                    'resolucion': 'declarada', 'regla': 'S1-R07',
                    'frase': FRASES_ZONA['declarada'], 'texto_informado': zona_txt}
        elif resolucion == 'no_reconocida':
            # No se reemplaza por la del servicio: se pide aclaración (S1-R07 corregida).
            zona = {'nombre': None, 'origen': None, 'resolucion': 'no_reconocida',
                    'regla': 'S1-R07', 'texto_informado': zona_txt,
                    'frase': f'«{zona_txt}» {FRASES_ZONA["no_reconocida"]}',
                    'sugerencias': zfila.get('sugerencias') or []}
        else:
            zona = {'nombre': None, 'origen': None, 'resolucion': 'sin_dato',
                    'regla': 'S1-R07', 'texto_informado': None,
                    'frase': FRASES_ZONA['sin_dato'],
                    'sugerencias': zfila.get('sugerencias') or []}

        completa = bool(nombre_serv and nombre_turno and zona['nombre'])
        if not nombre_serv:
            faltantes.add('servicio')
        if not nombre_turno:
            faltantes.add('turno')
        if not zona['nombre']:
            faltantes.add('zona')

        clave = (nombre_serv, nombre_turno)
        if clave in vistas and nombre_serv:
            advertencias.append(f'El pedido repite la combinación {nombre_serv} / {nombre_turno}.')
        vistas.add(clave)

        ficha['vacantes'].append({
            'servicio': {'texto': v.get('servicio_texto'), 'nombre': nombre_serv,
                         # PG3 (B05): «no indicado» y «no reconocido» son estados distintos.
                         'frase': (None if nombre_serv else
                                   'no está en el catálogo de servicios' if v.get('servicio_texto')
                                   else 'no se indicó en el pedido'),
                         'resolucion': serv.get('resolucion'), 'tipo': (serv.get('servicio') or {}).get('tipo'),
                         'sugerencias': serv.get('sugerencias') or [], 'regla': 'S1-R06'},
            'turno': {'texto': v.get('turno_texto'), 'nombre': nombre_turno,
                      'horario': f"{coinc[0]['inicio']}-{coinc[0]['fin']}" if len(coinc) == 1 else None},
            'zona': zona, 'completa': completa,
        })

    # S1-R05: desdoblamiento
    if len(ficha['vacantes']) > 1:
        advertencias.append(f"El pedido se desdobla en {len(ficha['vacantes'])} puestos, "
                            'uno por combinación servicio/turno (S1-R05).')

    # ---------------------------------------------------- aptitudes (R02, R03, R08)
    marcadores = []
    fila_m = grafo.una('S1-Q5b-marcadores')
    if fila_m:
        marcadores = [_norm_signos(m) for m in (fila_m.get('marcadores') or [])]
    if not marcadores:
        marcadores = list(MARCADORES_DEFECTO)
    entradas = [{'texto': a['texto'], 'norm': normalizar(a['texto']),
                 'marcador': a.get('marcador'), 'candidato': a.get('candidato_catalogo')}
                for a in extraido.get('aptitudes', [])]
    if entradas:
        for fila in grafo.leer('S1-Q5-aptitudes', aptitudes=entradas):
            coinc = fila.get('coincidencias') or []
            elegida = coinc[0] if coinc else None
            marcador = fila.get('marcador')
            excluyente = bool(marcador and _norm_signos(marcador) in marcadores)
            inferido = 'declarado'
            if not elegida and fila.get('candidato'):
                elegida = {'nombre': fila['candidato'], 'resolucion': 'sugerida_llm'}
                inferido = 'inferido'
                advertencias.append(f"«{fila['texto']}» se asoció a {fila['candidato']} por "
                                    'sugerencia del modelo: confirmar.')
            ficha['aptitudes'].append({
                'texto': fila['texto'], 'nombre': (elegida or {}).get('nombre'),
                'excluyente': excluyente, 'marcador': marcador,
                'regla': 'S1-R02' if excluyente else 'S1-R03',
                'resolucion': (elegida or {}).get('resolucion'),
                'fue_inferido_o_declarado': inferido,
                'estado_validacion': 'provisional', 'fuente': 'pedido',
            })

    # ---------------------------------------------------- urgencia (R04 + S1-F01..F10)
    expresiones = [{'texto': e['texto'], 'norm': nucleo_urgencia(e['texto'])}
                   for e in extraido.get('expresiones_urgencia', [])]
    plazo_h, premura, reconocidas, no_reconocidas = None, None, [], []
    if expresiones:
        for fila in grafo.leer('S1-Q6-urgencia', expresiones=expresiones):
            coinc = fila.get('coincidencias') or []
            if not coinc:
                no_reconocidas.append(fila['texto'])
                continue
            e = coinc[0]
            reconocidas.append(e)
            if e['tipo'] == 'plazo':
                plazo_h = float(e['valor']) if plazo_h is None else min(plazo_h, float(e['valor']))
            else:
                premura = float(e['valor']) if premura is None else max(premura, float(e['valor']))

    if plazo_h is None and premura is None:
        # PG3 (B08): primero las expresiones que el LLM extrajo y el grafo no reconoció;
        # si no hay, el texto completo del pedido (el fragmento queda anclado al texto).
        for fuente in list(no_reconocidas) + [texto]:
            e = _expresion_calendario(fuente)
            if e:
                reconocidas.append(e)
                if e['texto'] in no_reconocidas:
                    no_reconocidas.remove(e['texto'])
                no_reconocidas = [x for x in no_reconocidas if x != fuente]
                if e['tipo'] == 'plazo':
                    plazo_h = float(e['valor'])
                else:
                    premura = float(e['valor'])
                break

    u = s1_urgencia(plazo_h, premura)
    if u:
        # Devolución de la cátedra al PI4: hay TRES números distintos y el texto los
        # mezclaba. Cada uno lleva su nombre en la ficha para que no se confundan:
        #   indice      -> el centroide, el índice de urgencia del pedido (0 a 1)
        #   pertenencia -> cuánto pertenece a cada término (baja / media / alta)
        #   activacion  -> con cuánta fuerza se disparó cada regla difusa
        ficha['urgencia'] = {
            'expresiones_reconocidas': reconocidas, 'expresiones_no_reconocidas': no_reconocidas,
            'plazo_h': plazo_h, 'premura': premura, 'grupo_reglas': u['grupo'],
            'categoria': u['categoria'],
            'indice': round(u['valor'], 3),
            'pertenencia': {k: round(v, 3) for k, v in u['grados'].items()},
            'reglas_activadas': [{'regla': k, 'activacion': round(w, 3)}
                                 for k, (w, _) in u['reglas'].items() if w > 0.001],
            'regla_dominante': max(((k, w) for k, (w, _) in u['reglas'].items()),
                                   key=lambda x: x[1])[0] if u['reglas'] else None,
            'estado': 'OBSERVADO', 'version_modelo': 'S1-v0.1',
        }
    else:
        ficha['urgencia'] = {'expresiones_reconocidas': [], 'expresiones_no_reconocidas': no_reconocidas,
                             'categoria': None, 'indice': None, 'estado': 'DESCONOCIDO',
                             'pertenencia': {}, 'reglas_activadas': [], 'regla_dominante': None}
        if no_reconocidas:
            advertencias.append('No se reconoció ninguna expresión de urgencia: queda sin determinar.')

    # ---------------------------------------------------- R09, R10
    if extraido.get('relajacion_zona_texto'):
        ficha['radio_extendido'] = {'valor': True, 'texto': extraido['relajacion_zona_texto'],
                                    'regla': 'S1-R09'}
    exp = extraido.get('experiencia_minima')
    if exp and exp.get('cantidad') is not None:
        meses = float(exp['cantidad']) * (12 if exp.get('unidad') == 'años' else 1)
        ficha['experiencia_minima'] = {'cantidad': exp['cantidad'], 'unidad': exp.get('unidad'),
                                       'meses': meses, 'texto': exp.get('texto'), 'regla': 'S1-R10'}

    # ---------------------------------------------------- R01: estado del pedido
    # PG3 (B01): S3 necesita la urgencia para calcular la afinidad. Si ni el grafo ni el
    # calendario reconocieron un plazo, el pedido queda en espera y se pregunta.
    if not faltantes and ficha['urgencia'].get('categoria') is None:
        faltantes.add('plazo')
    if faltantes:
        ficha['pedido'] = {
            'estado': 'en_espera', 'campos_faltantes': sorted(faltantes), 'regla': 'S1-R01',
            'preguntas_aclaracion': [q for q in (_pregunta(c, ficha, catalogo or {})
                                                 for c in sorted(faltantes)) if q],
        }
    else:
        ficha['pedido'] = {'estado': 'completo', 'campos_faltantes': [],
                           'preguntas_aclaracion': [], 'regla': 'S1-R01'}

    # S1-R05: aviso de puesto ya existente
    pares = [{'servicio': v['servicio']['nombre'], 'turno': v['turno']['nombre']}
             for v in ficha['vacantes'] if v['completa']]
    if pares:
        for fila in grafo.leer('S1-Q7-puestos-existentes', vacantes=pares):
            for ex in fila.get('existentes') or []:
                advertencias.append(f"Ya hay un puesto registrado para {fila['servicio']}, turno "
                                    f"{fila['turno']} ({ex['puesto']}): verificar que no sea el mismo pedido.")
    ficha['advertencias'] = advertencias
    return ficha


def _pregunta(campo, ficha, catalogo=None):
    catalogo = catalogo or {}
    if campo == 'zona':
        for v in ficha['vacantes']:
            sug = v['zona'].get('sugerencias') or []
            if v['zona'].get('resolucion') == 'no_reconocida':
                # Se nombra lo que escribió el usuario y no se reemplaza por la zona del servicio.
                txt = v['zona'].get('texto_informado')
                cual = f"la zona «{txt}»" if txt else 'la zona indicada'
                if sug:
                    return f"No reconocemos {cual}. ¿Quisiste decir {', '.join(sug)}?"
                return _con_opciones(f'No reconocemos {cual}: ¿en qué zona o '
                                     'departamento es?', catalogo.get('zonas_lista'))
        # PG3 (B05): si la zona no se informó y falta el servicio, se va a heredar del
        # servicio (S1-R07). Preguntarla contradecía «se determinará cuando se indique el
        # servicio». Sigue figurando en campos_faltantes, como en el PG2.
        if all(v['zona'].get('resolucion') == 'sin_dato' for v in ficha['vacantes']):
            return None
        return _con_opciones(PREGUNTAS['zona'], catalogo.get('zonas_lista'))
    if campo == 'servicio':
        for v in ficha['vacantes']:
            sug = v['servicio'].get('sugerencias') or []
            if sug:
                escrito = v['servicio'].get('texto')
                cual = f'«{escrito}»' if escrito else 'ese servicio'
                return (f"No reconocemos {cual}: no está en el catálogo de servicios. "
                        f"¿Es alguno de estos: {', '.join(sug)}?")
        return _con_opciones(PREGUNTAS['servicio'], catalogo.get('servicios_lista'))
    if campo == 'turno':
        return _con_opciones(PREGUNTAS['turno'], catalogo.get('turnos_lista'))
    return PREGUNTAS[campo]


def explicar(grafo, ficha):
    try:
        sistema = prompts.cargar('s1_explicacion')
    except PromptFaltante:
        # Sin el prompt del autor, se entrega el texto determinístico (regla A6).
        return respaldo(ficha), None, False
    import json
    exigencias = {'sin_juicio_personas': True}

    def validador(d):
        motivos = validar_explicacion(d, ficha, exigencias)
        texto = (d or {}).get('texto') or ''
        if texto:
            # Controles que pidió la cátedra en la devolución del PI4.
            motivos += validar_urgencia_s1(texto, ficha)
            motivos += validar_zona_s1(texto, ficha)
        return motivos
    try:
        r = pedir_json(sistema, 'FICHA S1: ' + json.dumps(ficha, ensure_ascii=False, default=str),
                       temperatura=config.TEMP_EXPLICACION,
                       max_tokens=config.MAX_TOKENS_EXPLICACION,
                       reintentos=config.MAX_INTENTOS - 1, validador=validador)
    except ErrorLLM:
        # El proveedor no responde: se entrega la explicación armada con la ficha.
        return respaldo(ficha), None, False
    if r.datos and r.datos.get('texto'):
        return r.datos['texto'], r, True
    return respaldo(ficha), r, False


def respaldo(ficha):
    """Regla A6: texto determinístico armado solo con la ficha, si el LLM no logra una
    explicación fiel."""
    p = ficha['pedido']
    if p['estado'] == 'no_es_pedido':
        return ('El mensaje no corresponde a un pedido de cobertura. Para registrar uno hace falta '
                'indicar el servicio o la sede, el turno y, si corresponde, la zona, las aptitudes '
                'requeridas y para cuándo se necesita.')
    partes = []
    for v in ficha['vacantes']:
        z = v['zona']
        zona = (f", zona {z['nombre']} ({z.get('frase')})" if z['nombre']
                else f", zona: {z.get('frase')}")
        partes.append(f"{v['servicio']['nombre'] or 'servicio sin reconocer'} / "
                      f"{v['turno']['nombre'] or 'turno sin reconocer'}{zona}")
    texto = 'Se entendió: ' + '; '.join(partes) + '. '
    if ficha['aptitudes']:
        texto += 'Aptitudes: ' + ', '.join(
            f"{a['nombre'] or a['texto']} ({'excluyente' if a['excluyente'] else 'deseable'})"
            for a in ficha['aptitudes']) + '. '
    u = ficha.get('urgencia') or {}
    if u.get('categoria'):
        texto += f"Urgencia {u['categoria']}, con un índice de {u.get('indice')}. "
        dom = u.get('regla_dominante')
        if dom:
            act = next((r['activacion'] for r in u.get('reglas_activadas', [])
                        if r['regla'] == dom), None)
            texto += f"La regla que más pesó fue {dom}, activada con fuerza {act}. "
    else:
        texto += 'La urgencia no se pudo determinar. '
    if p['estado'] == 'completo':
        texto += 'El pedido está completo y pasa a la evaluación de aptitud y disponibilidad (S2). '
    else:
        texto += ('El pedido queda en espera porque faltan: ' + ', '.join(p['campos_faltantes']) +
                  '. ' + ' '.join(p['preguntas_aclaracion']) + ' ')
    if ficha['advertencias']:
        texto += 'Advertencias: ' + ' '.join(ficha['advertencias'])
    return texto.strip()


def registrar(grafo, ficha):
    """Escribe el pedido y los puestos en el grafo. Devuelve los ids de los puestos."""
    if ficha['pedido']['estado'] != 'completo':
        return []
    ahora = datetime.now().astimezone()
    # PG3 (pruebas 13/11, B13): con resolución de segundos, dos pedidos registrados en el
    # mismo segundo daban el mismo id y el MERGE de W-S1-puesto mezclaba los dos puestos.
    # Se agregan los milisegundos (el formato sigue siendo pv_<fecha y hora>_<n>).
    pedido_id = 'ped_' + ahora.strftime('%Y%m%d%H%M%S') + f'{ahora.microsecond // 1000:03d}'
    grafo.escribir('W-S1-pedido', pedido_id=pedido_id, texto=ficha['texto_original'],
                   estado=ficha['pedido']['estado'], fecha=ahora.isoformat(),
                   campos_faltantes=ficha['pedido']['campos_faltantes'])
    u = ficha.get('urgencia') or {}
    grados = u.get('pertenencia') or {}
    puestos = []
    for i, v in enumerate(ficha['vacantes'], 1):
        if not v['completa']:
            continue
        puesto_id = f'{pedido_id.replace("ped_", "pv_")}_{i}'
        grafo.escribir(
            'W-S1-puesto', pedido_id=pedido_id, puesto_id=puesto_id,
            servicio=v['servicio']['nombre'], turno=v['turno']['nombre'], zona=v['zona']['nombre'],
            urgencia_categoria=u.get('categoria'), urgencia_valor=u.get('centroide'),
            urgencia_estado=u.get('estado'), u_baja=grados.get('baja', 0.0),
            u_media=grados.get('media', 0.0), u_alta=grados.get('alta', 0.0),
            version_urgencia=u.get('version_modelo', 'S1-v0.1'),
            radio_extendido=bool(ficha.get('radio_extendido')),
            experiencia_meses=(ficha.get('experiencia_minima') or {}).get('meses'),
            zona_origen=v['zona']['origen'],
            zona_resolucion=v['zona'].get('resolucion'),
            fecha_evaluacion=(config.FECHA_EVALUACION or date.today().isoformat()))
        for a in ficha['aptitudes']:
            if not a['nombre']:
                continue
            grafo.escribir('W-S1-requisito', puesto_id=puesto_id, aptitud=a['nombre'],
                           excluyente=a['excluyente'], marcador=a['marcador'], regla=a['regla'],
                           fuente=a['fuente'], estado_validacion=a['estado_validacion'],
                           fue_inferido_o_declarado=a['fue_inferido_o_declarado'])
        puestos.append(puesto_id)
    ficha['puestos_registrados'] = puestos
    ficha['pedido']['id'] = pedido_id
    return puestos


def responder(grafo, texto, registrar_en_grafo=True):
    extraido, r_ext, catalogo = extraer(grafo, texto)
    if extraido is None:
        return {'submodulo': 'S1', 'error': 'No se pudo interpretar el pedido. ¿Podés reformularlo?',
                'llm_extraccion': r_ext.como_dict()}
    grafo.traza.agregar('extraccion', {'submodulo': 'S1', **r_ext.como_dict()})
    ficha = construir_ficha(grafo, texto, extraido, catalogo)
    puestos = registrar(grafo, ficha) if (registrar_en_grafo and config.ESCRITURA_HABILITADA) else []
    texto_resp, r_exp, fiel = explicar(grafo, ficha)
    grafo.traza.agregar('explicacion', {'submodulo': 'S1', 'fidelidad': 'OK' if fiel else 'respaldo',
                                        **(r_exp.como_dict() if r_exp else {'segundos': 0, 'intentos': 0})})
    return {'submodulo': 'S1', 'ficha': ficha, 'respuesta': texto_resp,
            'puestos_registrados': puestos, 'fidelidad': 'OK' if fiel else 'respaldo (A6)'}
