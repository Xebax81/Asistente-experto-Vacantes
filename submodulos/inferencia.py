"""PG3 — Cierre de la cadena: calculo y persistencia de S3 (afinidad) y S4 (categoria y listado).

POR QUE EXISTE ESTE ARCHIVO
---------------------------
En el PI4, S3 y S4 solo LEEN el grafo. El motor difuso de S3 se usaba unicamente
para simulaciones hipoteticas ("no cambia la categoria ni escribe en el grafo") y
S4 "no recalcula nada, solo recupera y verbaliza". Las afinidades, categorias,
prioridades y los nodos Listado_Final de los tres puestos del PG2 estaban cargados
a mano en Grupo_5_PG2_U1_carga.cypher.

Eso alcanzaba para los PI4 individuales, pero rompe el PG3: un pedido nuevo que
entra por S1 y se evalua en S2 no tiene afinidad que leer ni listado que explicar.
Este modulo es el eslabon que faltaba. No inventa conocimiento: usa el mismo
core/motor_difuso.py del PG2 —verificado contra los valores publicados en los PI3—
y escribe sus resultados en el grafo con las plantillas de core/consultas.py.

QUE ESCRIBE
-----------
  S3 : grado_afinidad_min/max, confiabilidad, termino_dominante, ACTIVA{fuerza}
       hacia cada Regla_Difusa que se disparo, CALCULADO_CON -> Version_Modelo_Difuso
  S4 : prioridad_recomendacion, regla_dominante, marca_transicion,
       TIENE_CATEGORIA{prioridad, regla_corte} -> Categoria, CLASIFICADO_CON,
       nodos Evidencia (RESPALDADO_POR), MarcaCalidadDato (TIENE_MARCA),
       Listado_Final con INCLUYE{posicion_afinidad, posicion_prioridad} y PRECEDE_A{estado_orden}

El LLM no interviene en ningun punto de este archivo.
"""
from datetime import datetime

from core import config
from core.motor_difuso import (
    CORTE_RECOMENDADO, CORTE_RESERVAS, centroide, evaluar, intervalo, reglas,
    cercania, desempeno, experiencia, s4_clasificar,
)

VERSION_S3 = 'S3-v0.3'
VERSION_S4 = 'S4-FZ-v1'
UMBRAL_EMPATE = 0.05          # S3-R15: diferencia por debajo de la cual el orden es empate tecnico
CRITERIO_ORDEN = 'PROVISIONAL'  # D22/M8 del PG2: todavia no validado con RR. HH.

# Rangos de referencia cuando un dato es DESCONOCIDO (los mismos del PG2).
RANGO_DESEMPENO = (1.0, 10.0)
RANGO_CERCANIA = (0.0, 90.0)
RANGO_SOLAPE = (0.0, 1.0)
RANGO_EXPERIENCIA = (0.0, 36.0)
MARGEN_SIN_DATO = 120.0


def _rango(minimo, maximo, estado, defecto):
    """Devuelve (min, max) para una entrada del motor.
    DESCONOCIDO -> rango de referencia completo; ESTIMADO -> el rango guardado;
    OBSERVADO -> el valor puntual."""
    if estado == 'DESCONOCIDO' or (minimo is None and maximo is None):
        return defecto
    if minimo is None:
        minimo = maximo
    if maximo is None:
        maximo = minimo
    return (float(minimo), float(maximo))


def _afinidad(ug, exp, des, cerc, mg, sol):
    """Afinidad como intervalo [min, max]. Si todo es puntual, min = max.

    motor_difuso.intervalo() barre desempeno, cercania, margen y solape, pero toma
    la experiencia como escalar; cuando la experiencia tambien es un rango se evalua
    en sus dos extremos y se combina, que es equivalente porque el motor es monotono
    por tramos en esa variable.
    """
    puntual = all(a == b for a, b in (exp, des, cerc, mg, sol))
    if puntual:
        c, h, r = evaluar(ug, exp[0], des[0], cerc[0], mg[0], sol[0])
        return c, c, h, r

    extremos = {exp[0], exp[1]}
    minimos, maximos = [], []
    for e in extremos:
        a, b = intervalo(ug, e, des, cerc, mg, sol)
        minimos.append(a)
        maximos.append(b)
    amin, amax = min(minimos), max(maximos)

    # Los grados y las reglas se reportan en el punto medio de cada entrada:
    # es el escenario que S4 usa para clasificar.
    medio = lambda t: (t[0] + t[1]) / 2.0
    _, h, r = evaluar(ug, medio(exp), medio(des), medio(cerc), medio(mg), medio(sol))
    return amin, amax, h, r


def _termino_dominante(h):
    return max(h, key=h.get)


def _marcas_de(fila, confiabilidad):
    """Marcas de calidad del dato, con el uso que S4 les da (informativa / advertencia / pedir dato)."""
    marcas = []
    if fila.get('des_estado') == 'DESCONOCIDO':
        marcas.append(('DESEMPENO_DESCONOCIDO', 'pedir dato',
                       'No hay evaluaciones de desempeno recientes para este empleado.', 'S3-R12'))
    if fila.get('solape_estado') == 'DESCONOCIDO':
        marcas.append(('HORARIO_DESCONOCIDO', 'pedir dato',
                       'No se conoce la franja horaria declarada del empleado.', 'S2-R10'))
    if fila.get('cerc_estado') == 'ESTIMADO':
        marcas.append(('TRASLADO_ESTIMADO', 'advertencia',
                       'El tiempo de traslado es una estimacion por zona, no un dato medido.', 'S3-R11'))
    if confiabilidad < 1.0:
        marcas.append(('AFINIDAD_IMPRECISA', 'advertencia',
                       'La afinidad es un intervalo porque alguna entrada no es observada.', 'S3-R13'))
    return marcas


def _evidencias_de(evaluacion, amin, amax, prioridad, fila, reglas_activadas):
    """Nodos Evidencia con la convencion de nombres del PG2."""
    ev = [
        {'id': f'Ev_afinidad_{evaluacion}', 'tipo': 'afinidad', 'valor': None,
         'valor_min': round(amin, 4), 'valor_max': round(amax, 4),
         'detalle': f'Afinidad calculada por el motor difuso de S3 ({VERSION_S3}).'},
        {'id': f'Ev_fz_{evaluacion}', 'tipo': 'prioridad', 'valor': round(prioridad, 4),
         'valor_min': None, 'valor_max': None,
         'detalle': f'Prioridad de recomendacion de S4 ({VERSION_S4}).'},
    ]
    if fila.get('margen_vigencia_dias') is not None:
        ev.append({'id': f'Ev_margen_{evaluacion}', 'tipo': 'margen_vigencia',
                   'valor': float(fila['margen_vigencia_dias']), 'valor_min': None, 'valor_max': None,
                   'detalle': 'Dias hasta el vencimiento de la certificacion excluyente (S2-R10).'})
    if fila.get('solape_horario') is not None and fila.get('solape_estado') != 'DESCONOCIDO':
        ev.append({'id': f'Ev_solape_{evaluacion}', 'tipo': 'solape_horario',
                   'valor': float(fila['solape_horario']), 'valor_min': None, 'valor_max': None,
                   'detalle': 'Fraccion del turno cubierta por la disponibilidad declarada (S2-R10).'})
    for apt in fila.get('deseables_faltantes') or []:
        ev.append({'id': f'Ev_deseable_{apt}_{evaluacion}', 'tipo': 'deseable_faltante',
                   'valor': None, 'valor_min': None, 'valor_max': None,
                   'detalle': f'El empleado no posee la aptitud deseable {apt}.'})
    for apt in fila.get('deseables_vencidos') or []:
        ev.append({'id': f'Ev_deseable_vencido_{apt}_{evaluacion}', 'tipo': 'deseable_vencido',
                   'valor': None, 'valor_min': None, 'valor_max': None,
                   'detalle': f'El empleado tiene la aptitud deseable {apt}, pero vencida.'})
    for adv in fila.get('advertencias') or []:
        ev.append({'id': f'Ev_adv_{adv}_{evaluacion}', 'tipo': 'advertencia',
                   'valor': None, 'valor_min': None, 'valor_max': None,
                   'detalle': f'Advertencia registrada: {adv}.'})
    for regla, fuerza in reglas_activadas:
        if fuerza >= 0.999:
            ev.append({'id': f'Ev_regla_{regla}_{evaluacion}', 'tipo': 'regla',
                       'valor': round(fuerza, 4), 'valor_min': None, 'valor_max': None,
                       'detalle': f'La regla {regla} se disparo con fuerza plena.'})
    return ev


def _estado_orden(a, b):
    """Orden entre dos candidatos consecutivos por prioridad.

    - no determinado : alguno tiene afinidad imprecisa y los intervalos se superponen
    - empate tecnico : diferencia de prioridad por debajo del umbral S3-R15
    - determinado    : el resto
    """
    dif = abs(a['prioridad'] - b['prioridad'])
    superpuestos = not (a['amax'] < b['amin'] or b['amax'] < a['amin'])
    impreciso = a['confiabilidad'] < 1.0 or b['confiabilidad'] < 1.0
    if impreciso and superpuestos:
        return 'no determinado', dif
    if dif < UMBRAL_EMPATE:
        return 'empate tecnico', dif
    return 'determinado', dif


# ====================================================================
def recalcular_puesto(grafo, puesto, persistir=True):
    """Corre S3 y S4 sobre todas las evaluaciones de un puesto y, si persistir,
    escribe el resultado en el grafo. Devuelve un informe para la traza."""
    filas = grafo.leer('PG3-evaluaciones-del-puesto', puesto=puesto)
    if not filas:
        return {'puesto': puesto, 'error': 'El puesto no tiene evaluaciones de S2.'}

    ug = {
        'baja': float(filas[0].get('u_baja') or 0.0),
        'media': float(filas[0].get('u_media') or 0.0),
        'alta': float(filas[0].get('u_alta') or 0.0),
    }
    if sum(ug.values()) == 0:
        return {'puesto': puesto,
                'error': 'El puesto no tiene grados de urgencia (los calcula S1). '
                         'Registre el pedido con S1 antes de correr S3.'}

    if persistir:
        grafo.escribir('W-PG3-categorias-base')
        grafo.escribir('W-PG3-limpiar-listado', puesto=puesto)

    validos, descartados, conteo = [], [], {}

    for fila in filas:
        if (fila.get('estado_S2') or '').lower() != 'valido':
            descartados.append(fila)
            for motivo in fila.get('motivos_descarte') or []:
                conteo[motivo] = conteo.get(motivo, 0) + 1
            continue

        exp = _rango(fila.get('exp_min'), fila.get('exp_max'), fila.get('exp_estado'), RANGO_EXPERIENCIA)
        des = _rango(fila.get('des_min'), fila.get('des_max'), fila.get('des_estado'), RANGO_DESEMPENO)
        cer = _rango(fila.get('cerc_min'), fila.get('cerc_max'), fila.get('cerc_estado'), RANGO_CERCANIA)
        mgv = fila.get('margen_vigencia_dias')
        mg = (float(mgv), float(mgv)) if mgv is not None else (MARGEN_SIN_DATO, MARGEN_SIN_DATO)
        sol = _rango(fila.get('solape_horario'), fila.get('solape_horario'),
                     fila.get('solape_estado'), RANGO_SOLAPE)

        amin, amax, h, r = _afinidad(ug, exp, des, cer, mg, sol)
        confiabilidad = round(1.0 - (amax - amin), 4)

        advertencias = fila.get('advertencias') or []
        estado_adv = fila.get('advertencias_estado')
        adv = ('sin_dato' if estado_adv in ('sin_dato', 'SIN_DATO')
               else 'con_advertencia' if advertencias else 'ninguna')
        s4 = s4_clasificar(amin, amax, adv)

        activadas = [(k, v[0]) for k, v in r.items() if v[0] > 0.001]
        activadas_s4 = [(f'S4-{k}', v[0]) for k, v in s4['reglas'].items() if v[0] > 0.001]

        candidato = {
            'evaluacion': fila['evaluacion'], 'legajo': fila['legajo'], 'empleado': fila['empleado'],
            'amin': round(amin, 4), 'amax': round(amax, 4), 'confiabilidad': confiabilidad,
            'termino_dominante': _termino_dominante(h),
            'prioridad': round(s4['prioridad'], 4), 'categoria': s4['categoria'],
            'regla_dominante': f"S4-{s4['dominante']}", 'marca_transicion': bool(s4['transicion']),
            'reglas': activadas + activadas_s4, 'fila': fila,
        }
        validos.append(candidato)

        if not persistir:
            continue

        grafo.escribir('W-S3-afinidad', evaluacion=candidato['evaluacion'],
                       afinidad_min=candidato['amin'], afinidad_max=candidato['amax'],
                       confiabilidad=confiabilidad, termino_dominante=candidato['termino_dominante'],
                       version=VERSION_S3)
        grafo.escribir('W-S3-reglas-activadas', evaluacion=candidato['evaluacion'],
                       reglas=[{'regla': r, 'fuerza': round(float(f), 4)}
                               for r, f in candidato['reglas']])
        grafo.escribir('W-S4-categoria', evaluacion=candidato['evaluacion'],
                       prioridad=candidato['prioridad'], categoria=candidato['categoria'],
                       regla_corte='FZ-C', regla_dominante=candidato['regla_dominante'],
                       marca_transicion=candidato['marca_transicion'], version=VERSION_S4)
        marcas = [{'codigo': c, 'uso_S4': u, 'descripcion': d, 'regla_origen': o}
                  for c, u, d, o in _marcas_de(fila, confiabilidad)]
        if marcas:
            grafo.escribir('W-S4-marcas', evaluacion=candidato['evaluacion'], marcas=marcas)
        grafo.escribir('W-S4-evidencias', evaluacion=candidato['evaluacion'],
                       evidencias=_evidencias_de(candidato['evaluacion'], amin, amax,
                                                 s4['prioridad'], fila, candidato['reglas']))

    # ------------------------------------------------ Listado_Final y orden
    por_prioridad = sorted(validos, key=lambda c: c['prioridad'], reverse=True)
    por_afinidad = sorted(validos, key=lambda c: (c['amin'] + c['amax']) / 2.0, reverse=True)
    pos_afinidad = {c['evaluacion']: i + 1 for i, c in enumerate(por_afinidad)}

    motivo_critico = max(conteo, key=conteo.get) if conteo else None
    listado = f'lf_{puesto}'
    tramos = []

    if persistir:
        grafo.escribir('W-S4-listado', puesto=puesto, listado=listado,
                       criterio_orden=CRITERIO_ORDEN, criterio_desempate='sin definir',
                       n_validos=len(validos), n_descartados=len(descartados),
                       conteo_motivos=[f'{k}: {v}' for k, v in sorted(conteo.items())],
                       motivo_critico=motivo_critico, version=config.VERSION_SISTEMA,
                       fecha=datetime.now().astimezone().isoformat())
        if por_prioridad:
            grafo.escribir('W-S4-incluye', listado=listado, posiciones=[
                {'evaluacion': c['evaluacion'],
                 'posicion_afinidad': pos_afinidad[c['evaluacion']],
                 'posicion_prioridad': i + 1}
                for i, c in enumerate(por_prioridad)])

    for a, b in zip(por_prioridad, por_prioridad[1:]):
        estado, dif = _estado_orden(a, b)
        tramos.append({'anterior': a['legajo'], 'siguiente': b['legajo'],
                       'estado_orden': estado, 'diferencia': round(dif, 4)})
        if persistir:
            grafo.escribir('W-S4-precede', anterior=a['evaluacion'], siguiente=b['evaluacion'],
                           estado_orden=estado, diferencia=round(dif, 4))
            marca = None
            if estado == 'empate tecnico':
                marca = {'codigo': 'EMPATE_TECNICO', 'uso_S4': 'informativa',
                         'regla_origen': 'S3-R15',
                         'descripcion': 'La diferencia de prioridad con el siguiente esta por '
                                        'debajo del umbral: no hay un ganador.'}
            elif estado == 'no determinado':
                marca = {'codigo': 'ORDEN_NO_DETERMINADO', 'uso_S4': 'pedir dato',
                         'regla_origen': 'S3-R15',
                         'descripcion': 'Los intervalos de afinidad se superponen: no se puede '
                                        'establecer el orden con los datos actuales.'}
            if marca:
                for c in (a, b):
                    grafo.escribir('W-S4-marcas', evaluacion=c['evaluacion'], marcas=[marca])

    return {
        'puesto': puesto, 'listado': listado, 'persistido': persistir,
        'n_validos': len(validos), 'n_descartados': len(descartados),
        'conteo_motivos': conteo, 'motivo_critico': motivo_critico,
        'criterio_orden': CRITERIO_ORDEN, 'version_s3': VERSION_S3, 'version_s4': VERSION_S4,
        'candidatos': [
            {k: c[k] for k in ('legajo', 'empleado', 'evaluacion', 'amin', 'amax',
                               'confiabilidad', 'prioridad', 'categoria', 'regla_dominante',
                               'marca_transicion', 'termino_dominante')}
            for c in por_prioridad
        ],
        'orden': tramos,
    }


def simular(ug, exp, des, cer, mg=None, sol=None):
    """Recalculo hipotetico (lo que ya hacia S3 en el PI4): no toca el grafo.
    Devuelve afinidad y las reglas con su fuerza, para explicar que cambio."""
    mg = mg if mg is not None else MARGEN_SIN_DATO
    sol = sol if sol is not None else 1.0
    c, h, r = evaluar(ug, exp, des, cer, mg, sol)
    return {'afinidad': round(c, 4), 'grados': {k: round(v, 4) for k, v in h.items()},
            'reglas': {k: round(v[0], 4) for k, v in r.items() if v[0] > 0.001},
            'hipotetico': True, 'version': VERSION_S3}
