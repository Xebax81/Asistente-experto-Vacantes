"""Prueba sin Neo4j ni LLM de la devolución de la cátedra al PI4 de S4 (León).

Usa las fichas del PG2 para pv_001 (las mismas que el PI4 de S4) y verifica que la
validación de fidelidad controle el significado de las afirmaciones:
  1. Rechaza las respuestas reales del PI4 que la cátedra señaló (CP1, CP2, CP3) y una
     cifra atribuida a otro candidato.
  2. Acepta redacciones correctas, incluida la «salida esperada» del propio PI4.
  3. La lectura en frases fijas y la comparación del orden salen bien armadas.

Uso:  python -m pruebas.prueba_devolucion_S4
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.validador import validar_explicacion, validar_s4  # noqa: E402
from submodulos.s4_explicacion import comparacion_orden, lectura, pregunta_por_orden  # noqa: E402


def ficha(leg, nombre, pos_p, pos_a, prioridad, afinidad, deseables, advertencias, estado_orden,
          reglas):
    ev = f'EV-{leg}-pv_001'
    evid = [{'id': f'Ev_afinidad_{ev}', 'tipo': 'afinidad', 'valor': None,
             'valor_min': afinidad, 'valor_max': afinidad, 'tiene_valor': True},
            {'id': f'Ev_fz_{ev}', 'tipo': 'inferencia_difusa', 'valor': prioridad, 'tiene_valor': True}]
    evid += [{'id': f'Ev_deseable_{d}_{ev}', 'tipo': 'deseable_faltante', 'valor': None,
              'tiene_valor': False} for d in deseables]
    evid += [{'id': f'Ev_adv_{a}_{ev}', 'tipo': 'advertencia', 'valor': None, 'tiene_valor': False}
             for a in advertencias]
    f = {'evaluacion': ev, 'puesto': 'pv_001', 'servicio': 'Hospital Central', 'urgencia': 'alta',
         'criterio_orden': 'PROVISIONAL', 'posicion_por_prioridad': pos_p,
         'posicion_por_afinidad': pos_a, 'empleado': nombre, 'legajo': leg,
         'categoria': 'Recomendado_con_reservas', 'regla_corte': 'FZ-C', 'regla_dominante': 'S4-FZ4',
         'reglas_activadas': reglas, 'prioridad': prioridad, 'afinidad': [afinidad, afinidad],
         'confiabilidad': 1.0, 'deseables_faltantes': deseables, 'deseables_vencidos': [],
         'deseables_estado': 'EVALUADAS', 'advertencias': advertencias,
         'advertencias_estado': 'con_dato', 'estado_orden_con_siguiente': estado_orden,
         'evidencias': evid}
    f['lectura'] = lectura(f)
    return f


E105 = ficha('E105', 'Elena Sosa', 1, 2, 0.453, 0.51, ['manejo_residuos_patogenicos'], [],
             'empate tecnico', [{'regla': 'S4-FZ4', 'fuerza': 0.952}])
E101 = ficha('E101', 'Ana Pérez', 2, 3, 0.442, 0.495, ['manejo_residuos_patogenicos'], [],
             'determinado', [{'regla': 'S4-FZ4', 'fuerza': 0.91}])
E104 = ficha('E104', 'Diego Ruiz', 3, 1, 0.431, 0.601, [], ['DESEMPEÑO_BAJO_RECIENTE'],
             None, [{'regla': 'S4-FZ3', 'fuerza': 0.8}, {'regla': 'S4-FZ4', 'fuerza': 0.923}])
LISTADO = [E105, E101, E104]

# ---------------------------------------------------------------- datos de cada consulta
DATOS_CP1 = {'fichas': LISTADO}
EXIG_CP1 = {'legajos': ['E105', 'E101', 'E104'], 'categorias': ['Recomendado_con_reservas'] * 3,
            'orden_provisional': True}

PREG_CP2 = ('¿Por qué Diego Ruiz quedó último en el listado del Hospital Central si es el que tiene '
            'mayor afinidad?')
DATOS_CP2 = {'fichas': [E104], 'otros_candidatos_del_listado': [E105, E101],
             'comparacion_orden': comparacion_orden('E104', LISTADO),
             'traza_categoria': {'evaluaciones': [{'fecha': '2026-08-12', 'puntaje': 6},
                                                  {'fecha': '2026-09-20', 'puntaje': 3}]}}
vec = DATOS_CP2['comparacion_orden']['vecinos']
EXIG_CP2 = {'citas_obligatorias': True, 'categorias': ['Recomendado_con_reservas'],
            'legajos': ['E104'], 'orden_provisional': True,
            'comparar_orden': {'legajos': [v['legajo'] for v in vec],
                               'prioridades': {'E104': 0.431, **{v['legajo']: v['prioridad'] for v in vec}}}}

E102 = {'legajo': 'E102', 'empleado': 'Bruno Gómez', 'evaluacion': 'EV-E102-pv_001',
        'estado_S2': 'descartado', 'motivos_descarte': ['certificación vencida: limpieza_hospitalaria'],
        'deseables_estado': 'SIN_DATO', 'categoria': 'Baja_prioridad', 'regla_corte': 'S4-R01'}
E102['lectura'] = lectura(E102, descartado=True)
DATOS_CP3 = {'descartes': [E102]}
EXIG_CP3 = {'descartado': True, 'sin_dato': True}

# ---------------------------------------------------------------- textos reales del PI4
PI4_CP1 = {'texto': (
    "Para cubrir el turno tarde del Hospital Central, el sistema experto recomienda a los siguientes "
    "candidatos con la categoría 'Recomendado_con_reservas': 1. Elena Sosa (E105) con una afinidad de "
    "0.51, un solape horario del 75% y una prioridad de 0.453. 2. Ana Pérez (E101) con una afinidad de "
    "0.495 y una prioridad de 0.442. 3. Diego Ruiz (E104) con una afinidad de 0.601 y una prioridad de "
    "0.431. Todas las categorías son 'Recomendado_con_reservas' y el orden es provisional. Las "
    "advertencias sobre el manejo de residuos patógenos y el desempeño bajo reciente son consideradas, "
    "pero no son suficientes para rechazarlos."), 'citas': []}
PI4_CP2 = {'texto': (
    "Diego Ruiz quedó último en el listado del Hospital Central, a pesar de tener la mayor afinidad, "
    "debido a una advertencia de desempeño bajo recientemente. La regla S4-FZ3, que considera una "
    "afinidad alta con advertencia, le asignó la categoría de 'Recomendado_con_reservas'. La evidencia "
    "de desempeño bajo reciente con un valor de 0.601, indica que su desempeño bajo recientemente "
    "influye en su prioridad. El criterio de orden es provisional y aún no es un criterio validado por "
    "RR. HH."),
    'citas': [{'evaluacion': 'EV-E104-pv_001',
               'evidencia': 'Ev_adv_DESEMPEÑO_BAJO_RECIENTE_EV-E104-pv_001', 'valor': 0.601}]}
PI4_CP3 = {'texto': (
    "Bruno Gómez fue descartado para la vacante del Hospital Central debido a que su certificación de "
    "limpieza hospitalaria está vencida. Según la regla S4-R01 esto lo clasifica como un descarte de baja "
    "prioridad. No se encontraron deseados faltantes ni evidencias de afinidad en su perfil."),
    'citas': []}
OTRO_CANDIDATO = {'texto': (
    "Ana Pérez (E101) quedó en la categoría Recomendado con reservas, con una afinidad de 0,601. El orden "
    "es provisional."), 'citas': []}

CODIGOS_TECNICOS = {'texto': (
    "Diego Ruiz (E104) quedó en Recomendado_con_reservas con una afinidad de [0.601, 0.601] y prioridad "
    "0,431. Presenta la advertencia DESEMPEÑO_BAJO_RECIENTE y el estado de advertencias es con dato. "
    "Ana Pérez (E101), que queda antes, tiene prioridad 0,442. El orden es provisional."),
    'citas': [{'evaluacion': 'EV-E104-pv_001', 'evidencia': 'Ev_afinidad_EV-E104-pv_001', 'valor': 0.601}]}

# ---------------------------------------------------------------- redacciones correctas
BIEN_CP2 = {'texto': (   # «salida esperada» del PI4 de S4, sección d.2
    "Diego Ruiz (E104) quedó en la categoría Recomendado con reservas, con una prioridad de 0,431. Es "
    "cierto que tiene la mayor afinidad del listado (0,601, un dato preciso, con confiabilidad 1), pero "
    "su legajo registra una advertencia por desempeño bajo reciente: evaluaciones del 12/08/2026 con 6 y "
    "del 20/09/2026 con 3. Por eso se activa la regla que lleva a reservas a un candidato con "
    "advertencias (S4-FZ3). Ana Pérez (E101), que queda justo antes, tiene una prioridad de 0,442. Así, "
    "por prioridad queda tercero aunque por afinidad sería primero. Este criterio de orden es "
    "provisional y todavía no fue validado por RR. HH.; la decisión final queda en sus manos."),
    'citas': [{'evaluacion': 'EV-E104-pv_001', 'evidencia': 'Ev_afinidad_EV-E104-pv_001', 'valor': 0.601},
              {'evaluacion': 'EV-E104-pv_001', 'evidencia': 'Ev_fz_EV-E104-pv_001', 'valor': 0.431},
              {'evaluacion': 'EV-E104-pv_001',
               'evidencia': 'Ev_adv_DESEMPEÑO_BAJO_RECIENTE_EV-E104-pv_001', 'valor': None}]}
BIEN_CP3 = {'texto': (
    "Bruno Gómez (E102) fue descartado para la vacante del Hospital Central porque su certificación de "
    "limpieza hospitalaria está vencida. Su categoría registrada es Baja prioridad (S4-R01). Como quedó "
    "descartado, sus aptitudes deseables no se evaluaron."),
    'citas': [{'evaluacion': 'EV-E102-pv_001',
               'evidencia': 'certificación vencida: limpieza_hospitalaria', 'valor': None}]}
BIEN_CP1 = {'texto': (
    "Para el turno tarde del Hospital Central hay tres candidatos, los tres en la categoría Recomendado "
    "con reservas. Elena Sosa (E105) tiene prioridad 0,453 y afinidad 0,51; no tiene la aptitud deseable "
    "manejo de residuos patogénicos. Ana Pérez (E101) tiene prioridad 0,442 y afinidad 0,495; tampoco tiene "
    "esa aptitud deseable. Diego Ruiz (E104) tiene la afinidad más alta, 0,601, pero prioridad 0,431, "
    "porque tiene la advertencia de desempeño bajo reciente. El orden es provisional y no fue validado "
    "por RR. HH."), 'citas': []}


def main():
    ok = True

    def chequeo(nombre, cond, detalle=''):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'OK ' if cond else 'FALLA'}] {nombre}" + (f' — {detalle}' if detalle and not cond else ''))

    print('== 1. Datos que recibe el LLM')
    chequeo('Lectura de E105: el deseable faltante dice que no es una advertencia',
            'no una advertencia' in E105['lectura']['aptitudes_deseables'], E105['lectura'])
    chequeo('Lectura de E104: la advertencia va aparte',
            E104['lectura']['advertencias'].startswith('tiene la advertencia'), E104['lectura'])
    chequeo('Lectura de un descartado: deseables «no se evaluaron»',
            'no se evaluaron' in E102['lectura']['aptitudes_deseables'])
    chequeo('Comparación del orden de E104: vecino E101 con diferencia 0,011',
            [(v['legajo'], v['diferencia_de_prioridad']) for v in vec] == [('E101', 0.011)], vec)
    chequeo('Detecta que la pregunta de CP2 es por la posición', pregunta_por_orden(PREG_CP2, {}))
    chequeo('Lectura de E104 sin códigos: categoría, afinidad y advertencia con palabras',
            E104['lectura']['categoria'] == 'Recomendado con reservas'
            and E104['lectura']['afinidad'] == 'afinidad 0,601'
            and 'desempeño bajo reciente' in E104['lectura']['advertencias']
            and '_' not in ' '.join(E104['lectura'].values()), E104['lectura'])

    print('\n== 2. Tiene que RECHAZAR')
    for nombre, d, datos, exig in [
            ('PI4 CP1: deseable faltante llamado «advertencia»', PI4_CP1, DATOS_CP1, EXIG_CP1),
            ('PI4 CP2: 0,601 atribuido a la advertencia; orden sin comparar prioridades',
             PI4_CP2, DATOS_CP2, EXIG_CP2),
            ('PI4 CP3: SIN_DATO leído como «no se encontraron deseables faltantes»',
             PI4_CP3, DATOS_CP3, EXIG_CP3),
            ('Cifra de otro candidato (0,601 de E104 atribuido a E101)', OTRO_CANDIDATO, DATOS_CP1, {}),
            ('Códigos técnicos en el texto (Recomendado_con_reservas, [0.601, 0.601], '
             'DESEMPEÑO_BAJO_RECIENTE, «con dato»)', CODIGOS_TECNICOS, DATOS_CP2, EXIG_CP2)]:
        motivos = validar_s4(d, datos, exig)
        chequeo(nombre, motivos)
        for m in motivos:
            print('        -', m)

    print('\n== 3. Tiene que ACEPTAR')
    for nombre, d, datos, exig in [('CP2: salida esperada del PI4 de S4', BIEN_CP2, DATOS_CP2, EXIG_CP2),
                                   ('CP3 bien redactado', BIEN_CP3, DATOS_CP3, EXIG_CP3),
                                   ('CP1 bien redactado', BIEN_CP1, DATOS_CP1, EXIG_CP1)]:
        motivos = validar_s4(d, datos, exig) + validar_explicacion(d, datos, exig)
        chequeo(nombre, not motivos, motivos)

    print('\nRESULTADO:', 'todas las verificaciones pasan' if ok else 'hay verificaciones que fallan')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
