"""Pruebas de las correcciones del 13/11 (informe de pruebas, B01 a B20), sin Neo4j ni LLM.

    python -m pruebas.prueba_correcciones_13nov

El grafo y el LLM se reemplazan por dobles mínimos: solo se prueba la lógica que se
cambió (plazos de calendario, pedido en espera del plazo, memoria de la aclaración,
cadena con error de S3, mensaje de listado vacío y controles de formato).
"""
from datetime import date

from core import validador
from orquestador import asistente
from submodulos import s1_requisitos as s1
from submodulos import s4_explicacion as s4

FALLAS = []


def chequeo(nombre, ok, detalle=''):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}" + ('' if ok else f' — {detalle}'))
    if not ok:
        FALLAS.append(nombre)


# ------------------------------------------------------------------ B08 calendario
VIERNES = date(2026, 11, 13)          # viernes
casos = [
    ('para ayer', ('premura', 10)),
    ('Necesito cubrir el turno mañana en el Supermercado Norte para ayer.', ('premura', 10)),
    ('para el lunes', ('plazo', 72)),
    ('el viernes', ('plazo', 168)),
    ('dentro de 3 días', ('plazo', 72)),
    ('dentro de tres dias', ('plazo', 72)),
    ('en 2 horas', ('plazo', 2)),
    ('en una semana', ('plazo', 168)),
    ('para el 20/11', ('plazo', 168)),
    ('para el 13/11', ('plazo', 8)),
    ('turno mañana en el Hospital Central', None),
    ('urgente', None),
]
print('== B08: plazos que no están en el diccionario del grafo')
for texto, esperado in casos:
    e = s1._expresion_calendario(texto, VIERNES)
    obtenido = (e['tipo'], e['valor']) if e else None
    chequeo(f'«{texto}» -> {esperado}', obtenido == esperado, obtenido)


# ------------------------------------------------------------------ dobles del grafo
class GrafoFalso:
    """Responde a las consultas que usa construir_ficha con datos fijos."""
    def __init__(self, urgencia_reconocida=None):
        self.urg = urgencia_reconocida or []

    def leer(self, nombre, **p):
        if nombre == 'S1-Q2-servicio':
            return [{'texto': x['texto'], 'servicio': {'nombre': 'Supermercado Norte', 'tipo': 'comercial'},
                     'resolucion': 'exacta'} for x in p['servicios']]
        if nombre == 'S1-Q4-turno':
            return [{'texto': x['texto'], 'coincidencias': [{'nombre': 'mañana', 'inicio': '06:00', 'fin': '14:00'}]}
                    for x in p['turnos']]
        if nombre == 'S1-Q6-urgencia':
            return [{'texto': x['texto'], 'coincidencias': self.urg} for x in p['expresiones']]
        return []

    def una(self, nombre, **p):
        if nombre == 'S1-Q3-zona':
            if p.get('servicio'):
                return {'resolucion': 'heredada', 'zona_servicio': 'Godoy Cruz'}
            return {'resolucion': None}
        return None


def extraido(servicio='el Supermercado Norte', turno='el turno mañana', exp=None):
    return {'es_pedido_cobertura': True,
            'vacantes': [{'servicio_texto': servicio, 'turno_texto': turno}],
            'zona_texto': None, 'aptitudes': [],
            'expresiones_urgencia': [{'texto': t} for t in (exp or [])],
            'texto_no_interpretado': []}


print('\n== B01: sin plazo el pedido queda en espera y pregunta para cuándo')
f = s1.construir_ficha(GrafoFalso(), 'Necesito cubrir el turno mañana en el Supermercado Norte.',
                       extraido())
chequeo('estado en_espera', f['pedido']['estado'] == 'en_espera', f['pedido'])
chequeo('falta solo el plazo', f['pedido']['campos_faltantes'] == ['plazo'], f['pedido']['campos_faltantes'])
chequeo('pregunta por el plazo', any('Para cuándo' in q for q in f['pedido']['preguntas_aclaracion']),
        f['pedido']['preguntas_aclaracion'])

f = s1.construir_ficha(GrafoFalso(), 'Necesito cubrir el turno mañana en el Supermercado Norte para ayer.',
                       extraido(exp=['para ayer']))
chequeo('«para ayer» completa el pedido', f['pedido']['estado'] == 'completo', f['pedido'])
chequeo('«para ayer» da urgencia alta', f['urgencia'].get('categoria') == 'alta', f['urgencia'].get('categoria'))
chequeo('la expresión queda con su fuente',
        any(e.get('fuente') == 'calendario_PG3' for e in f['urgencia']['expresiones_reconocidas']),
        f['urgencia']['expresiones_reconocidas'])

print('\n== B05: pedido sin servicio')
f = s1.construir_ficha(GrafoFalso(), 'Necesito cubrir un turno, urgente.',
                       extraido(servicio=None, turno=None, exp=['urgente']))
chequeo('campos faltantes iguales al PG2', f['pedido']['campos_faltantes'] == ['servicio', 'turno', 'zona'],
        f['pedido']['campos_faltantes'])
chequeo('no pregunta la zona (se hereda del servicio)',
        not any('zona' in q.lower() for q in f['pedido']['preguntas_aclaracion']),
        f['pedido']['preguntas_aclaracion'])
chequeo('frase «no se indicó en el pedido»', f['vacantes'][0]['servicio']['frase'] == 'no se indicó en el pedido',
        f['vacantes'][0]['servicio'].get('frase'))


# ------------------------------------------------------------------ validador
print('\n== B04 y B09: controles de formato')
ficha = {'pedido': {'estado': 'en_espera'}}
for nombre, texto, rechaza in [
    ('ruta de campo', 'El pedido queda en espera porque faltan los campos de pedido.campos_faltantes.', True),
    ('código DESCONOCIDO', 'El desempeño tiene un estado DESCONOCIDO.', True),
    ('campo con guion bajo', 'El solape_estado no se conoce.', True),
    ('intervalo entre corchetes', 'Su afinidad está en [0,166, 0,5].', True),
    ('PROVISIONAL en mayúsculas', 'El criterio de orden es PROVISIONAL.', True),
    ('texto correcto', 'El pedido queda en espera porque faltan el servicio y el turno del pv_001.', False),
]:
    m = validador._formato_tecnico(texto)
    chequeo(f"{'rechaza' if rechaza else 'acepta'}: {nombre}", bool(m) == rechaza, m)
chequeo('S2 puede nombrar aptitudes por su código',
        not validador._formato_tecnico('Tiene limpieza_hospitalaria vencida.', codigos=False))

print('\n== B10: simulación')
base = {'texto': 'Es una simulación hipotética. La afinidad baja de 0,601 a 0,307. '}
for nombre, extra, rechaza in [
    ('«la categoría registrada no cambia»', 'La categoría registrada no cambia.', False),
    ('«la categoría no cambia»', 'La categoría no cambia.', False),
    ('«se mantiene»', 'La categoría no cambia, manteniéndose como Recomendado con reservas.', True),
]:
    m = validador.validar_explicacion({'texto': base['texto'] + extra}, {'v': [0.601, 0.307]},
                                      {'hipotetico': True})
    chequeo(f"{'rechaza' if rechaza else 'acepta'} {nombre}", bool(m) == rechaza, m)


# ------------------------------------------------------------------ B02 memoria de aclaración
print('\n== B02: respuesta a la aclaración de S2/S3/S4')
chequeo('«pv_001» parece respuesta', asistente._parece_respuesta('pv_001'))
chequeo('una pregunta nueva no', not asistente._parece_respuesta('¿Quién puede cubrir el turno noche de la Clínica Luján?'))
t = asistente._consulta_completada({'texto': '¿Por qué quedó afuera Bruno Gómez para el Hospital Central?'},
                                   'el pv_001')
chequeo('la consulta se completa con el id', 'pv_001' in t and 'Bruno Gómez' in t, t)


# ------------------------------------------------------------------ B07 listado vacío
print('\n== B07: mensaje de listado vacío sin Listado_Final')


class GrafoListado:
    def una(self, nombre, **p):
        return {'puesto': 'pv_x', 'servicio': 'Fábrica Sur', 'descartados': None,
                'del_pedido': [], 'del_catalogo': [], 'conteo_motivos': [],
                'urgencia': None, 'urgencia_estado': 'DESCONOCIDO'}


txt = s4.mensaje_listado_vacio(GrafoListado(), 'pv_x', evaluados=7)
chequeo('usa el conteo de S2', 'Se evaluaron 7 empleados' in txt, txt[:120])
chequeo('sin «None» ni DESCONOCIDO', 'None' not in txt and 'DESCONOCIDO' not in txt, txt[-80:])


# ------------------------------------------------------------------ B01 cadena con error de S3
print('\n== B01: la cadena no oculta a los válidos si S3 falla')


class GrafoCadena:
    class traza:
        @staticmethod
        def agregar(*a, **k):
            pass


orig = (s1.responder, asistente.s2_aptitud.evaluar_puesto, asistente.s2_aptitud.registrar,
        asistente.inferencia.recalcular_puesto)
try:
    s1.responder = lambda g, t, registrar_en_grafo=True: {
        'ficha': {'pedido': {'estado': 'completo'}}, 'respuesta': 'S1 ok', 'puestos_registrados': ['pv_x'],
        'fidelidad': 'OK'}
    asistente.s1_requisitos.responder = s1.responder
    asistente.s2_aptitud.evaluar_puesto = lambda g, p, l=None: {
        'evaluacion': {'n_validos': 1, 'n_descartados': 6, 'motivo_critico': None,
                       'validos': [{'legajo': 'E104', 'nombre': 'Diego Ruiz'}], 'descartados': [],
                       'conteo_motivos': {}},
        'requisitos': {'excluyentes': []}}
    asistente.s2_aptitud.registrar = lambda g, f: None
    asistente.inferencia.recalcular_puesto = lambda g, p, persistir=True: {
        'puesto': p, 'error': 'El puesto no tiene grados de urgencia (los calcula S1).'}
    r = asistente.cadena_completa(GrafoCadena(), 'pedido')
    chequeo('nombra a Diego Ruiz', 'Diego Ruiz' in r['respuesta'], r['respuesta'])
    chequeo('no dice «No hay candidatos válidos»', 'No hay candidatos' not in r['respuesta'], r['respuesta'])
    chequeo('la etapa S3 registra el error', any(e.get('error') for e in r['etapas'] if e['submodulo'] == 'S3'),
            r['etapas'])
finally:
    (s1.responder, asistente.s2_aptitud.evaluar_puesto, asistente.s2_aptitud.registrar,
     asistente.inferencia.recalcular_puesto) = orig
    asistente.s1_requisitos.responder = orig[0]

print('\nRESULTADO: ' + ('todas las verificaciones pasan' if not FALLAS else f'{len(FALLAS)} fallan'))
