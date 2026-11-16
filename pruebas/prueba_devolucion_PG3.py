"""Prueba sin Neo4j ni LLM de la devolución de la cátedra al PG3 (16/11/2026).

1. PARÁMETROS DIFUSOS: «sería conveniente que el grafo fuera la fuente efectiva de esos
   parámetros y que el motor los recuperara desde allí».
   - Se arman las filas de la consulta PG3-parametros-motor a partir de la exportación de
     Aura del 13/11 (neo4j/Grupo_5_PG3_export.json), recorriendo el mismo camino
     Variable_Linguistica -> Termino -> Funcion_Pertenencia.
   - Con esas filas el motor pasa a usar los valores del grafo y los resultados publicados
     en los PI3 siguen dando igual.
   - Si se cambia un valor en el grafo, el resultado cambia: el grafo es la fuente efectiva.
   - Si al grafo le falta una función o tiene una inválida o repetida, el motor usa las del
     código y lo informa (no mezcla las dos fuentes).
   - La conexión (core/grafo.py) hace la lectura y la deja en la traza.
2. EXPLICACIONES: «aparecen nombres técnicos de categorías o se confunden aptitudes faltantes
   con vencidas».
   - La deseable vencida que el PG2 guardó como faltante con sufijo se separa al leer.
   - El validador de S4 rechaza el texto real de E2E-9 y acepta la redacción correcta.
   - El control CP1 ya no rechaza «no tiene advertencias pero no tiene la aptitud deseable X».
   - El texto real de E2E-10 (código técnico de categoría) se rechaza.
   - Los respaldos de S3 ya no muestran códigos ni corchetes.

Uso:  python -m pruebas.prueba_devolucion_PG3
"""
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import motor_difuso as md  # noqa: E402
from core.grafo import Grafo, Traza, separar_deseables_vencidos  # noqa: E402
from core.validador import _formato_tecnico, validar_explicacion, validar_s4  # noqa: E402
from submodulos.s3_afinidad import respaldo as respaldo_s3  # noqa: E402

resultados = []


def chk(nombre, condicion, detalle=''):
    resultados.append(bool(condicion))
    print(f"  {'OK ' if condicion else 'XX '}{nombre}" + (f'  [{detalle}]' if detalle else ''))


def filas_desde_export():
    """Lo que devolvería PG3-parametros-motor sobre el grafo exportado de Aura."""
    d = json.loads((RAIZ / 'neo4j' / 'Grupo_5_PG3_export.json').read_text(encoding='utf-8'))
    nodos = {n['id']: n for n in d['nodos']}
    rel = {}
    for r in d['relaciones']:
        rel.setdefault((r['desde'], r['tipo']), []).append(r['hasta'])
    filas = []
    for n in d['nodos']:
        if 'Variable_Linguistica' not in n['etiquetas']:
            continue
        for t in rel.get((n['id'], 'TIENE_TERMINO'), []):
            if 'Termino' not in nodos[t]['etiquetas']:
                continue
            for f in rel.get((t, 'DEFINIDO_POR'), []):
                p = nodos[f]['propiedades']
                if 'Funcion_Pertenencia' not in nodos[f]['etiquetas'] or \
                        p.get('centro') is None or p.get('sigma') is None:
                    continue
                filas.append({'variable': n['propiedades']['nombre'],
                              'termino': nodos[t]['propiedades']['nombre'],
                              'forma': p.get('forma'), 'centro': p.get('centro'),
                              'sigma': p.get('sigma'), 'lado': p.get('lado'),
                              'centro2': p.get('centro2'), 'sigma2': p.get('sigma2'),
                              'version': p.get('version')})
    return filas


def corrida():
    """Valores de referencia de los PI3 (los mismos que verifica core/motor_difuso.py)."""
    return {
        'S1 C2 (120 h, premura 8)': md.s1_urgencia(120, 8)['valor'],
        'S1 E1 (24 h)': md.s1_urgencia(24, None)['valor'],
        'S3 v0.3 20 h E2': md.evaluar(20, 20, 4.5, 10)[0],
        'S2 margen 30 d, solape 0,6': md.evaluar({'baja': 0, 'media': 0.16, 'alta': 0.86}, 9, 7.5, 30, 30, 0.6)[0],
        'S4 Emp_102': md.s4_clasificar(0.74, 0.74, 'con_advertencia')['prioridad'],
        'S4 Emp_304': md.s4_clasificar(0.62, 0.86, 'ninguna')['prioridad'],
    }


print('1. Parámetros difusos: el grafo como fuente efectiva')
md.usar_parametros_del_codigo('referencia')
ref = corrida()
filas = filas_desde_export()
chk('la exportación de Aura tiene las 30 funciones gaussianas del motor',
    len({(f['variable'], f['termino']) for f in filas} & set(md.PARAMETROS_CODIGO)) == 30,
    f'{len(filas)} filas')

o = md.usar_parametros_del_grafo(filas)
chk('el motor toma los parámetros del grafo', o['fuente'] == 'grafo', o['detalle'])
chk('hoy el grafo y el respaldo del código coinciden', not o['diferencias'], o['diferencias'])
con_grafo = corrida()
chk('con los parámetros del grafo, los resultados de los PI3 no cambian',
    all(abs(con_grafo[k] - ref[k]) < 1e-12 for k in ref))

mod = copy.deepcopy(filas)
for f in mod:
    if (f['variable'], f['termino']) == ('plazo_cobertura', 'corto'):
        f['centro'] = 90.0
o = md.usar_parametros_del_grafo(mod)
nuevo = md.s1_urgencia(120, 8)['valor']
chk('si se cambia un centro en el grafo, cambia la urgencia calculada (el grafo manda)',
    o['fuente'] == 'grafo' and abs(nuevo - ref['S1 C2 (120 h, premura 8)']) > 1e-3,
    f"plazo corto con centro 90 h: índice 0,496 -> {nuevo:.3f}".replace('.', ','))
chk('la diferencia con el código queda informada', any('plazo_cobertura/corto' in d for d in o['diferencias']))

o = md.usar_parametros_del_grafo([f for f in filas if f['termino'] != 'por_vencer'])
chk('si falta una función en el grafo, usa las del código y lo dice',
    o['fuente'] == 'codigo (respaldo)' and 'faltan 1' in o['detalle'], o['detalle'])
chk('…y calcula con el respaldo completo, no con una mezcla', corrida() == ref)

malas = copy.deepcopy(filas)
malas[0]['sigma'] = 0
o = md.usar_parametros_del_grafo(malas)
chk('una sigma inválida en el grafo no se usa', o['fuente'] == 'codigo (respaldo)', o['detalle'][:70])

dup = filas + [dict(filas[0], centro=float(filas[0]['centro']) + 1)]
o = md.usar_parametros_del_grafo(dup)
chk('dos funciones distintas para el mismo término no se usan', o['fuente'] == 'codigo (respaldo)',
    o['detalle'][:70])


class GrafoFalso(Grafo):
    """Grafo sin driver: leer() devuelve las filas de la exportación."""

    def __init__(self, filas_motor):
        self.traza = Traza()
        self._filas = filas_motor
        self.parametros_difusos = self._cargar_parametros_difusos()

    def leer(self, nombre, **_):
        assert nombre == 'PG3-parametros-motor'
        self.traza.agregar('cypher', {'consulta': nombre, 'filas': len(self._filas)})
        return self._filas


g = GrafoFalso(filas)
paso = [p for p in g.traza.pasos if p['etapa'] == 'parametros_difusos']
chk('al conectarse, la lectura se hace con PG3-parametros-motor y queda en la traza',
    g.traza.pasos[0].get('consulta') == 'PG3-parametros-motor' and paso and paso[0]['fuente'] == 'grafo')
md.usar_parametros_del_codigo('fin de la prueba 1')

print('\n2. Explicaciones: vencida no es faltante y sin códigos técnicos')
# Ficha de Diego Ruiz en pv_001 tal como la cargó el PG2 (exportación de Aura).
ficha = {'legajo': 'E104', 'empleado': 'Diego Ruiz', 'evaluacion': 'EV-E104-pv_001',
         'categoria': 'Recomendado_con_reservas', 'prioridad': 0.4314, 'afinidad': [0.6009, 0.6009],
         'confiabilidad': 1.0, 'advertencias': ['DESEMPEÑO_BAJO_RECIENTE'],
         'advertencias_estado': 'con_dato', 'deseables_estado': 'EVALUADAS',
         'deseables_faltantes': ['manejo_residuos_patogenicos (vencida)'], 'deseables_vencidos': [],
         'evidencias': [{'id': 'Ev_deseable_manejo_residuos_patogenicos (vencida)_EV-E104-pv_001',
                         'tipo': 'deseable_faltante', 'valor': None,
                         'detalle': 'El empleado no posee la aptitud deseable manejo_residuos_patogenicos (vencida).'}]}
separar_deseables_vencidos(ficha)
chk('la deseable vencida del PG2 deja de figurar como faltante',
    ficha['deseables_faltantes'] == [] and ficha['deseables_vencidos'] == ['manejo_residuos_patogenicos'])
chk('su evidencia pasa a «deseable_vencido» con el detalle correcto',
    ficha['evidencias'][0]['tipo'] == 'deseable_vencido' and 'pero vencida' in ficha['evidencias'][0]['detalle'])
from submodulos.s4_explicacion import lectura  # noqa: E402
chk('la lectura que recibe el LLM dice «tiene … pero vencida»',
    'pero vencida' in lectura(ficha)['aptitudes_deseables']
    and 'no tiene' not in lectura(ficha)['aptitudes_deseables'], lectura(ficha)['aptitudes_deseables'])

datos = {'fichas': [ficha]}
e2e9 = ('Diego Ruiz (legajo E104) tiene la categoría Recomendado con reservas, con afinidad 0,601 y '
        'prioridad 0,431. Quedó en la posición 3, sumado a que registra la advertencia desempeño '
        'bajo reciente y no tiene la aptitud deseable manejo de residuos patogénicos (vencida).')
m = validar_s4({'texto': e2e9}, datos)
chk('rechaza el texto real de E2E-9 (faltante con «vencida»)', any('vencida' in x for x in m), m[:1])
bien = ('Diego Ruiz (legajo E104) tiene la categoría Recomendado con reservas, con prioridad 0,431. '
        'Tiene la aptitud deseable manejo de residuos patogénicos, pero vencida, y registra la '
        'advertencia desempeño bajo reciente.')
chk('acepta la redacción correcta', validar_s4({'texto': bien}, datos) == [],
    validar_s4({'texto': bien}, datos))
falt = {'fichas': [dict(ficha, deseables_faltantes=['manejo_residuos_patogenicos'], deseables_vencidos=[])]}
m = validar_s4({'texto': 'Diego Ruiz (legajo E104) tiene vencida la aptitud deseable manejo de '
                         'residuos patogénicos.'}, falt)
chk('rechaza presentar como vencida una aptitud que no tiene', any('no la tiene' in x for x in m), m[:1])

# E2E-1 del 16/11: redacción correcta que el control CP1 rechazaba por error.
dos = {'fichas': [dict(ficha, legajo='E101', empleado='Ana Pérez', advertencias=[],
                       deseables_faltantes=['manejo_residuos_patogenicos'], deseables_vencidos=[])]}
t = ('Ana Pérez (legajo E101) tiene prioridad 0,431; no tiene advertencias pero no tiene la '
     'aptitud deseable manejo de residuos patogénicos.')
chk('acepta «no tiene advertencias pero no tiene la aptitud deseable X» (E2E-1)',
    validar_s4({'texto': t}, dos) == [], validar_s4({'texto': t}, dos))
t = 'Ana Pérez (legajo E101) tiene prioridad 0,431. Las advertencias sobre el manejo de residuos patogénicos pesan.'
chk('sigue rechazando presentar la deseable como advertencia (CP1 del PI4 de S4)',
    any('como una advertencia' in x for x in validar_s4({'texto': t}, dos)))

e2e10 = ('Esta es una simulación hipotética calculada por el motor difuso para Diego Ruiz, que no se '
         'guarda y donde la categoría no cambia, manteniéndose como Recomendado_con_reservas.')
m = validar_explicacion({'texto': e2e10}, {'datos': {}}, {'hipotetico': True})
chk('rechaza el texto real de E2E-10 (código técnico de categoría)',
    any('Recomendado_con_reservas' in x for x in m), m[-1:])

t = respaldo_s3({'hipotetico': True, 'base_grafo': [0.601, 0.601], 'simulada': [0.3066, 0.3066],
                 'categoria_S4': 'Recomendado_con_reservas'}, 'simular_afinidad')
chk('el respaldo de la simulación de S3 no tiene códigos ni corchetes', not _formato_tecnico(t), t)
t = respaldo_s3({'servicio': 'Hospital Central', 'criterio_orden': 'PROVISIONAL',
                 'candidatos': [{'empleado': 'Elena Sosa', 'legajo': 'E105', 'afinidad': 0.5,
                                 'categoria_S4': 'Baja_prioridad'}]}, 'ranking_afinidad')
chk('el respaldo del ranking de S3 no tiene códigos', not _formato_tecnico(t), t)

print('\nRESULTADO: ' + ('todas las verificaciones pasan' if all(resultados)
                         else f'{resultados.count(False)} verificaciones fallan'))
sys.exit(0 if all(resultados) else 1)
