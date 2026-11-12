"""Prueba sin Neo4j ni LLM de la devolución de la cátedra al PI4 de S2 (Cayo).

Arma las fichas de S2 con los datos del PG2 (puesto pv_001, fecha 05/10/2026) y verifica:
  1. Las reglas: vencida e inexistente quedan distinguidas (también en los deseables) y
     evaluar a una sola persona no produce conteos ni «no hay candidatos válidos».
  2. El validador: rechaza las respuestas reales del PI4 y del PG3 que tenían el problema
     y acepta redacciones correctas.

Uso:  python -m pruebas.prueba_devolucion_S2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.validador import validar_explicacion, validar_s2  # noqa: E402
from submodulos import s2_aptitud  # noqa: E402

CAB = {'puesto': 'pv_001', 'servicio': 'Hospital Central', 'tipo_servicio': 'hospitalario',
       'turno': 'tarde', 'inicio': '14:00', 'fin': '22:00', 'zona': 'Capital',
       'urgencia': 'alta', 'urgencia_estado': 'OBSERVADO', 'fecha_evaluacion': '2026-10-05'}
REQ = {'del_pedido': [{'aptitud': 'limpieza_hospitalaria', 'excluyente': False, 'origen': 'pedido'},
                      {'aptitud': 'manejo_residuos_patogenicos', 'excluyente': False,
                       'origen': 'pedido', 'regla': 'S1-R03'}],
       'del_catalogo': [{'aptitud': 'limpieza_hospitalaria', 'excluyente': True,
                         'origen': 'catalogo', 'regla': 'S2-R01'}]}


def _emp(legajo, nombre, aptitudes, turnos, zonas, cercanas):
    return {'legajo': legajo, 'nombre': nombre,
            'aptitudes': [{'aptitud': a, 'vencimiento': v} for a, v in aptitudes],
            'turnos': turnos, 'zonas': [{'zona': z, 'habitual': h} for z, h in zonas],
            'zonas_cercanas_al_puesto': cercanas, 'turno_puesto': 'tarde', 'zona_puesto': 'Capital',
            'turno_inicio': '14:00', 'turno_fin': '22:00',
            'experiencia_meses': None, 'desempeno_reciente': None}


TH = {'turno': 'tarde', 'habitual': True, 'desde': None, 'hasta': None}
TP = {'turno': 'tarde', 'habitual': False, 'desde': '14:00', 'hasta': '20:00'}
PERFILES = [
    _emp('E101', 'Ana Pérez', [('limpieza_hospitalaria', '2027-03-31')], [TH], [('Guaymallén', True)], ['Guaymallén']),
    _emp('E102', 'Bruno Gómez', [('limpieza_hospitalaria', '2026-09-28')], [TH], [('Capital', True)], []),
    _emp('E103', 'Carla Díaz', [('manejo_maquinaria_industrial', None)],
         [{'turno': 'noche', 'habitual': True}], [('Godoy Cruz', True)], ['Godoy Cruz']),
    _emp('E104', 'Diego Ruiz', [('limpieza_hospitalaria', '2027-06-30'),
                                ('manejo_residuos_patogenicos', '2026-08-15')],
         [{'turno': 'mañana', 'habitual': True}, TP], [('Luján de Cuyo', True), ('Capital', False)], []),
    _emp('E401', 'Valeria Núñez', [('limpieza_hospitalaria', '2027-05-31')],
         [{'turno': 'noche', 'habitual': False}], [('Maipú', True)], []),
    _emp('E402', 'Tomás Aguirre', [('limpieza_hospitalaria', '2027-02-28')],
         [{'turno': 'noche', 'habitual': True}], [('Luján de Cuyo', True)], []),
    _emp('E105', 'Elena Sosa', [('limpieza_hospitalaria', '2026-11-19')], [TP], [('Capital', True)], []),
]


class GrafoFalso:
    def leer(self, nombre, **p):
        if nombre == 'S2-Q2-puesto':
            return [CAB]
        if nombre == 'S2-Q5-perfiles':
            leg = p.get('legajos') or []
            return [x for x in PERFILES if not leg or x['legajo'] in leg]
        raise KeyError(nombre)

    def una(self, nombre, **p):
        if nombre == 'S2-Q4-requisitos':
            return REQ
        raise KeyError(nombre)


def ficha(legajos=None, intencion='candidatos_puesto'):
    f = s2_aptitud.evaluar_puesto(GrafoFalso(), 'pv_001', legajos)
    f['consulta'] = {'estado': 'resuelta', 'intencion': intencion, 'filtro_estado': None,
                     'pide_orden_o_recomendacion': False}
    return s2_aptitud.ficha_para_explicar(f), f


# ------------------------------------------------------------------ textos a evaluar
PI4_C1 = ("El puesto pv_001 (Hospital Central, turno tarde, zona Capital) requiere la aptitud excluyente "
          "limpieza_hospitalaria (catálogo del tipo hospitalario, regla S2-R01). Pueden cubrirlo tres "
          "empleados: Ana Pérez (legajo E101) con margen de vigencia holgado (120 días), aunque le falta el "
          "deseable; Diego Ruiz (E104) con margen holgado (120 días) y solape parcial (6 h), le falta el "
          "deseable vencido; y Elena Sosa (E105) con margen por vencer (45 días). Quedan descartados cuatro "
          "candidatos: Bruno Gómez (E102) por certificación vencida de limpieza_hospitalaria (S2-R03); "
          "Carla Díaz (E103) por aptitud faltante de limpieza_hospitalaria (S2-R02) y turno incompatible "
          "(S2-R04); Valeria Núñez (E401) y Tomás Aguirre (E402) por turno incompatible (S2-R04) y zona "
          "incompatible (S2-R05). Los válidos pasarán a la siguiente fase S3 para el cálculo de afinidad.")
PI4_C2 = ("Bruno Gómez (legajo E102) no puede cubrir el puesto de Hospital Central (turno tarde, zona Capital) "
          "porque fue descartado. El motivo del descarte es que su certificación de limpieza_hospitalaria está "
          "vencida (venció el 2026-09-28, antes de la fecha de evaluación 2026-10-05), según la regla S2-R03. "
          "Además, su disponibilidad para el turno tarde y la zona Capital sí cumplen (controles S2-R04 y "
          "S2-R05). En la siguiente fase S3 se usará el margen de vigencia y el solape horario para calcular "
          "la afinidad, aunque en este caso el empleado ya está descartado.")
PG3_E2E7 = ("Para el puesto pv_001 en el Hospital Central, turno tarde en Capital, el empleado Bruno Gómez "
            "(legajo E102) quedó descartado. No cumple con las certificaciones vigentes (regla S2-R03) porque "
            "su aptitud de limpieza_hospitalaria venció el 2026-09-28, antes de la fecha de evaluación "
            "2026-10-05. Respecto a sus deseables, el estado de los mismos se encuentra SIN_DATO, y tanto su "
            "experiencia como su desempeño figuran en estado DESCONOCIDO. Al no haber candidatos válidos, la "
            "derivación es S4 según la regla S2-R09.")
INVENTO_INEXISTENTE = ("Bruno Gómez (E102) quedó descartado para el puesto pv_001 porque no tiene la aptitud "
                       "limpieza_hospitalaria (S2-R03). Por eso no pasa a S3.")
INVENTO_VENCIDA = ("Carla Díaz (E103) quedó descartada para el puesto pv_001 porque su limpieza_hospitalaria "
                   "está vencida (S2-R02) y no tiene disponibilidad en el turno tarde (S2-R04).")

BIEN_C2 = ("Bruno Gómez (E102) quedó descartado para el puesto pv_001 (Hospital Central, turno tarde). Tiene "
           "la aptitud limpieza_hospitalaria, pero su certificación venció el 28/09/2026, antes de la fecha de "
           "evaluación 05/10/2026 (S2-R03). El turno y la zona sí cumplen (S2-R04 y S2-R05). Por eso no pasa "
           "a S3: no participa del cálculo de afinidad ni del orden de candidatos.")
BIEN_C1 = ("El puesto pv_001 (Hospital Central, turno tarde, zona Capital) exige la aptitud limpieza_hospitalaria "
           "(S2-R01). Pueden cubrirlo Ana Pérez (E101), Diego Ruiz (E104) y Elena Sosa (E105). Diego Ruiz (E104) "
           "tiene la aptitud deseable manejo_residuos_patogenicos, pero venció el 15/08/2026. Ana Pérez (E101) y "
           "Elena Sosa (E105) no tienen ese deseable. Quedaron descartadas cuatro personas: Bruno Gómez (E102) "
           "tiene la aptitud limpieza_hospitalaria, pero su certificación venció el 28/09/2026 (S2-R03); Carla "
           "Díaz (E103) no tiene registrada la aptitud limpieza_hospitalaria (S2-R02) ni disponibilidad en el "
           "turno tarde (S2-R04); Valeria Núñez (E401) y Tomás Aguirre (E402) no tienen disponibilidad en el "
           "turno tarde (S2-R04) ni en la zona Capital o una cercana (S2-R05). Solo los válidos pasan al cálculo "
           "de afinidad (S3); las personas descartadas no participan del orden.")


def main():
    ok = True

    def chequeo(nombre, cond, detalle=''):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'OK ' if cond else 'FALLA'}] {nombre}" + (f' — {detalle}' if detalle and not cond else ''))

    print('== 1. Reglas (ficha S2)')
    _, completa = ficha()
    regs = {r['legajo']: r for r in completa['evaluacion']['validos'] + completa['evaluacion']['descartados']}
    chequeo('Válidos E101, E104, E105', sorted(r['legajo'] for r in completa['evaluacion']['validos'])
            == ['E101', 'E104', 'E105'])
    m102 = regs['E102']['motivos'][0]
    chequeo('E102: motivo de tipo CERTIFICACION_VENCIDA con fecha',
            m102['tipo'] == 'CERTIFICACION_VENCIDA' and '28/09/2026' in m102['frase'], m102)
    m103 = next(m for m in regs['E103']['motivos'] if m['regla'] == 'S2-R02')
    chequeo('E103: motivo de tipo APTITUD_INEXISTENTE', m103['tipo'] == 'APTITUD_INEXISTENTE', m103)
    chequeo('E104: el deseable vencido figura como vencido, no como faltante',
            [d['aptitud'] for d in regs['E104']['deseables_vencidos']] == ['manejo_residuos_patogenicos']
            and 'manejo_residuos_patogenicos' not in regs['E104']['deseables_faltantes'])
    chequeo('E101: el deseable que no tiene figura como faltante',
            regs['E101']['deseables_faltantes'] == ['manejo_residuos_patogenicos'])
    chequeo('Descartados: siguiente paso «no pasa a S3»',
            all(r['siguiente_paso'].startswith('no pasa a S3') for r in completa['evaluacion']['descartados']))
    chequeo('Solo los válidos se entregan a S3',
            all(r['entrega_a_S3'] == (r['estado_S2'] == 'valido') for r in regs.values()))
    llm_uno, uno = ficha(['E102'], 'situacion_empleado')
    chequeo('Una sola persona: sin conteos, sin derivación y sin «no hay candidatos válidos»',
            'n_validos' not in uno['evaluacion'] and 'derivacion' not in uno['evaluacion']
            and not uno['advertencias'] and uno['empleado']['legajo'] == 'E102')
    chequeo('Al LLM no le llegan margen, solape ni deseables de un descartado',
            set(llm_uno['empleado']) <= set(s2_aptitud.CAMPOS_DESCARTADO))
    resp = s2_aptitud.respaldo(uno)
    chequeo('Texto de respaldo de un descartado: vencida + no pasa a S3',
            'venció el 28/09/2026' in resp and 'no pasa a S3' in resp
            and not validar_s2(resp, llm_uno), resp)
    apt = s2_aptitud.ficha_aptitud(
        [{'legajo': 'E102', 'nombre': 'Bruno Gómez', 'vencimiento': '2026-09-28'},
         {'legajo': 'E101', 'nombre': 'Ana Pérez', 'vencimiento': '2027-03-31'}],
        'limpieza_hospitalaria', s2_aptitud.date(2026, 10, 5))
    chequeo('aptitud_vigente: el código separa vigentes y vencidas',
            [x['legajo'] for x in apt['vigentes']] == ['E101']
            and [x['legajo'] for x in apt['vencidas']] == ['E102'])

    print('\n== 2. Validador: tiene que RECHAZAR')
    llm_full, _ = ficha()
    for nombre, texto, f in [('PI4 C1 (deseable vencido como faltante; descartados como candidatos)', PI4_C1, llm_full),
                             ('PI4 C2 (descartado asociado a S3 y la afinidad)', PI4_C2, llm_uno),
                             ('PG3 E2E-7 (SIN_DATO, «no hay candidatos válidos» con una sola persona)', PG3_E2E7, llm_uno),
                             ('Vencida presentada como inexistente', INVENTO_INEXISTENTE, llm_uno),
                             ('Inexistente presentada como vencida', INVENTO_VENCIDA, llm_full)]:
        motivos = validar_s2(texto, f)
        chequeo(nombre, motivos)
        for m in motivos:
            print('        -', m)

    print('\n== 3. Validador: tiene que ACEPTAR')
    for nombre, texto, f, exig in [('C2 bien redactado', BIEN_C2, llm_uno, {}),
                                   ('C1 bien redactado', BIEN_C1, llm_full,
                                    {'legajos': ['E101', 'E104', 'E105']})]:
        motivos = validar_s2(texto, f) + validar_explicacion({'texto': texto}, f, exig)
        chequeo(nombre, not motivos, motivos)

    print('\nRESULTADO:', 'todas las verificaciones pasan' if ok else 'hay verificaciones que fallan')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
