"""Submodulo S2 — Evaluacion de Aptitud y Disponibilidad (Cayo).

Reglas S2-R01 a S2-R10 aplicadas en Python con los hechos leidos del grafo, mas la
fuzzificacion del margen de vigencia y del solape horario, que S3 consume.

El LLM no decide: elige la intencion y copia fragmentos; el resto es codigo.

Novedad del PG3: `evaluar_puesto()` puede correr sin LLM (lo que en el PI4 era
--puesto pv_001) y `registrar()` escribe un EvaluacionEmpleadoPuesto por empleado,
que es lo que despues toma submodulos/inferencia.py para calcular la afinidad.
"""
import json
from datetime import date, datetime

from core import config, prompts
from core.prompts import PromptFaltante
from core.grafo import normalizar
from core.llm import ErrorLLM, pedir_json
from core.motor_difuso import margen as fz_margen, solape as fz_solape
from core.validador import validar_explicacion, validar_s2

INTENCIONES = ('candidatos_puesto', 'situacion_empleado', 'aptitud_vigente',
               'requisitos_puesto', 'fuera_de_alcance')



def _nombre(aptitud):
    """Nombre legible de una aptitud del catálogo (manejo_residuos_patogenicos ->
    manejo de residuos patogénicos), el mismo que usa S4."""
    from submodulos.s4_explicacion import legible
    return legible(aptitud)

def _fecha_ref(puesto=None):
    if puesto and puesto.get('fecha_evaluacion'):
        return date.fromisoformat(str(puesto['fecha_evaluacion'])[:10])
    if config.FECHA_EVALUACION:
        return date.fromisoformat(config.FECHA_EVALUACION)
    return date.today()


def _fmt(d):
    """'2026-09-28' -> '28/09/2026' (como se lo lee el reclutador)."""
    t = str(d)[:10]
    try:
        return date.fromisoformat(t).strftime('%d/%m/%Y')
    except ValueError:
        return t


# Devolución de la cátedra al PI4 de S2: una certificación vencida no es una aptitud
# inexistente, y un descartado no puede quedar insinuado en el ranking. Por eso cada
# motivo lleva un tipo y una frase fija, y cada registro dice qué pasa con S3.
PASO_VALIDO = ('pasa a S3: el margen de vigencia y el solape horario se usan en el cálculo '
               'de afinidad')
PASO_DESCARTADO = ('no pasa a S3: no participa del cálculo de afinidad ni del orden de '
                   'candidatos')


def _minutos(hhmm):
    h, m = str(hhmm)[:5].split(':')
    return int(h) * 60 + int(m)


def _solape(turno_ini, turno_fin, desde, hasta):
    """Fraccion del turno cubierta por la disponibilidad declarada.
    Maneja turnos que cruzan la medianoche (22:00-06:00)."""
    try:
        ti, tf = _minutos(turno_ini), _minutos(turno_fin)
        di, df = _minutos(desde), _minutos(hasta)
    except (ValueError, AttributeError, TypeError):
        return None
    if tf <= ti:
        tf += 24 * 60
    if df <= di:
        df += 24 * 60
    total = tf - ti
    if total <= 0:
        return None
    cubierto = max(0, min(tf, df) - max(ti, di))
    if cubierto == 0 and df > 24 * 60:  # reintento desplazando la disponibilidad
        cubierto = max(0, min(tf, df - 24 * 60) - max(ti, di - 24 * 60))
    return round(min(1.0, cubierto / total), 4)


# ==================================================================== reglas
def requisitos_efectivos(grafo, puesto_id):
    """S2-R01: los requisitos son los del pedido mas los que exige el tipo de servicio.
    Una aptitud deseable en el pedido que el catalogo exige queda promovida a excluyente."""
    fila = grafo.una('S2-Q4-requisitos', puesto=puesto_id) or {'del_pedido': [], 'del_catalogo': []}
    efectivos, vistas = [], {}
    for r in fila.get('del_pedido', []):
        vistas[r['aptitud']] = dict(r, promovida=False)
    for r in fila.get('del_catalogo', []):
        if r['aptitud'] in vistas:
            previa = vistas[r['aptitud']]
            if not previa.get('excluyente'):
                previa.update(excluyente=True, origen='catalogo', regla='S2-R01', promovida=True)
        else:
            vistas[r['aptitud']] = dict(r, promovida=False)
    efectivos = list(vistas.values())
    return {
        'excluyentes': [r for r in efectivos if r.get('excluyente')],
        'deseables': [r for r in efectivos if not r.get('excluyente')],
        'todas': efectivos,
    }


def evaluar_puesto(grafo, puesto_id, legajos=None):
    """Corre S2-R01..R10 sobre todos los empleados. Devuelve la ficha S2."""
    cab = next((p for p in grafo.leer('S2-Q2-puesto', puesto_id=puesto_id, servicio=None, turno=None)
                if p['puesto'] == puesto_id), None)
    if not cab:
        return None
    req = requisitos_efectivos(grafo, puesto_id)
    excluyentes = {r['aptitud'] for r in req['excluyentes']}
    deseables = {r['aptitud'] for r in req['deseables']}
    ref = _fecha_ref(cab)

    perfiles = grafo.leer('S2-Q5-perfiles', puesto=puesto_id, legajos=legajos or [])
    validos, descartados, conteo = [], [], {}

    for p in perfiles:
        motivos, controles = [], []
        poseidas = {a['aptitud']: a.get('vencimiento') for a in p.get('aptitudes') or []}

        # S2-R02: aptitud excluyente faltante
        faltan = sorted(excluyentes - set(poseidas))
        controles.append({'control': 'S2-R02', 'descripcion': 'posee las aptitudes excluyentes',
                          'cumple': not faltan, 'detalle': faltan})
        for a in faltan:
            motivos.append({'motivo': f'aptitud faltante: {a}', 'regla': 'S2-R02',
                            'tipo': 'APTITUD_INEXISTENTE', 'aptitud': a,
                            'frase': f'no tiene registrada la aptitud {_nombre(a)}'})

        # S2-R03: vigencia de las excluyentes que vencen
        margen_dias, vencidas = None, []
        for a in excluyentes & set(poseidas):
            v = poseidas[a]
            if not v:
                continue
            dias = (date.fromisoformat(str(v)[:10]) - ref).days
            margen_dias = dias if margen_dias is None else min(margen_dias, dias)
            if dias < 0:
                vencidas.append((a, v))
        controles.append({'control': 'S2-R03', 'descripcion': 'certificaciones vigentes',
                          'cumple': not vencidas,
                          'detalle': [f'{a} venció el {v}' for a, v in vencidas]})
        for a, v in vencidas:
            motivos.append({'motivo': f'certificación vencida: {a}', 'regla': 'S2-R03',
                            'tipo': 'CERTIFICACION_VENCIDA', 'aptitud': a,
                            'vencimiento': str(v)[:10],
                            'detalle': f'venció el {v}, antes de la fecha de evaluación {ref}',
                            # Sin «pero» al comienzo: el LLM la encadena después de «cumple
                            # con…, pero» y salía «…, pero tiene la aptitud X, pero…» (E2E-7).
                            'frase': (f'tiene registrada la aptitud {_nombre(a)} con la certificación '
                                      f'vencida el {_fmt(v)}, antes de la fecha de evaluación {_fmt(ref)}')})

        # S2-R04: disponibilidad de turno
        turnos = {t['turno']: t for t in p.get('turnos') or []}
        tiene_turno = p['turno_puesto'] in turnos
        controles.append({'control': 'S2-R04', 'descripcion': 'disponibilidad en el turno',
                          'cumple': tiene_turno, 'detalle': sorted(turnos)})
        if not tiene_turno:
            motivos.append({'motivo': 'turno incompatible', 'regla': 'S2-R04', 'tipo': 'TURNO',
                            'frase': f"no tiene disponibilidad en el turno {p['turno_puesto']}"})

        # S2-R05: zona (propia o cercana)
        zonas = {z['zona'] for z in p.get('zonas') or []}
        cercanas = set(p.get('zonas_cercanas_al_puesto') or [])
        en_zona = p['zona_puesto'] in zonas
        zona_ok = en_zona or bool(cercanas)
        controles.append({'control': 'S2-R05', 'descripcion': 'zona compatible o cercana',
                          'cumple': zona_ok, 'detalle': sorted(zonas)})
        if not zona_ok:
            motivos.append({'motivo': 'zona incompatible', 'regla': 'S2-R05', 'tipo': 'ZONA',
                            'frase': (f"no tiene disponibilidad en la zona {p['zona_puesto']} "
                                      'ni en una zona cercana')})

        # S2-R10: margen de vigencia y solape horario (entradas difusas para S3)
        solape_valor, solape_estado = None, 'DESCONOCIDO'
        if tiene_turno:
            t = turnos[p['turno_puesto']]
            if t.get('desde') and t.get('hasta'):
                solape_valor = _solape(p['turno_inicio'], p['turno_fin'], t['desde'], t['hasta'])
                solape_estado = 'OBSERVADO' if solape_valor is not None else 'DESCONOCIDO'
            elif t.get('habitual'):
                solape_valor, solape_estado = 1.0, 'OBSERVADO'

        # Cercania estimada a partir de la zona (TRASLADO_ESTIMADO del PG2)
        if en_zona:
            cerc, cerc_estado = (0.0, 25.0), 'ESTIMADO'
        elif cercanas:
            cerc, cerc_estado = (15.0, 55.0), 'ESTIMADO'
        else:
            cerc, cerc_estado = (45.0, 90.0), 'ESTIMADO'

        # Entradas de S3 que ahora viven en el Empleado (depuración del PG3).
        # Si no están, quedan DESCONOCIDO y S3 devuelve la afinidad como intervalo.
        exp_val = p.get('experiencia_meses')
        des_val = p.get('desempeno_reciente')
        exp = ((float(exp_val), float(exp_val), 'OBSERVADO') if exp_val is not None
               else (None, None, 'DESCONOCIDO'))
        des = ((float(des_val), float(des_val), 'OBSERVADO') if des_val is not None
               else (None, None, 'DESCONOCIDO'))

        faltan_deseables = sorted(deseables - set(poseidas))
        # Un deseable vencido NO es un deseable faltante: la persona lo tiene, pero vencido.
        deseables_vencidos = [
            {'aptitud': a, 'vencimiento': str(poseidas[a])[:10],
             'frase': f'tiene la aptitud deseable {_nombre(a)}, vencida el {_fmt(poseidas[a])}'}
            for a in sorted(deseables & set(poseidas))
            if poseidas[a] and date.fromisoformat(str(poseidas[a])[:10]) < ref]
        estado = 'valido' if not motivos else 'descartado'
        advertencias = []
        if margen_dias is not None and margen_dias < 60:
            advertencias.append('MARGEN_CORTO')
        if solape_valor is not None and solape_valor < 1.0:
            advertencias.append('SOLAPE_PARCIAL')
        if exp[2] == 'DESCONOCIDO' or des[2] == 'DESCONOCIDO':
            advertencias.append('ENTRADAS_INCOMPLETAS')

        registro = {
            'legajo': p['legajo'], 'nombre': p['nombre'], 'estado_S2': estado,
            'motivos': motivos, 'controles': controles,
            'deseables_faltantes': faltan_deseables,
            'deseables_vencidos': deseables_vencidos,
            'deseables_estado': 'EVALUADAS' if estado == 'valido' else 'SIN_DATO',
            'margen_vigencia': {
                'dias': margen_dias,
                'grados': {k: round(v, 3) for k, v in fz_margen(margen_dias).items()} if margen_dias is not None else {},
                'dominante': max(fz_margen(margen_dias), key=fz_margen(margen_dias).get) if margen_dias is not None else None,
            },
            'solape_horario': {
                'fraccion': solape_valor, 'estado': solape_estado,
                'grados': {k: round(v, 3) for k, v in fz_solape(solape_valor).items()} if solape_valor is not None else {},
                'dominante': max(fz_solape(solape_valor), key=fz_solape(solape_valor).get) if solape_valor is not None else None,
            },
            'cercania_estimada': {'min': cerc[0], 'max': cerc[1], 'estado': cerc_estado},
            'experiencia': {'min': exp[0], 'max': exp[1], 'estado': exp[2]},
            'desempeno': {'min': des[0], 'max': des[1], 'estado': des[2]},
            'advertencias': advertencias,
            'entrega_a_S3': estado == 'valido',
            'siguiente_paso': PASO_VALIDO if estado == 'valido' else PASO_DESCARTADO,
        }
        if estado == 'valido':
            validos.append(registro)
        else:
            descartados.append(registro)
            for m in motivos:
                conteo[m['motivo']] = conteo.get(m['motivo'], 0) + 1

    motivo_critico = max(conteo, key=conteo.get) if conteo else None
    if legajos:
        # Se evaluó solo a las personas consultadas: los conteos, la derivación y el
        # «no hay candidatos válidos» no describen el puesto y no se informan.
        ficha = {
            'puesto': {k: cab[k] for k in ('puesto', 'servicio', 'tipo_servicio', 'turno', 'zona',
                                           'inicio', 'fin', 'urgencia', 'urgencia_estado')},
            'fecha_evaluacion': ref.isoformat(),
            'requisitos': req,
            'evaluacion': {'alcance': 'empleados_consultados',
                           'nota_alcance': ('Se evaluó solo a la persona consultada; no se '
                                            'informa cuántos candidatos válidos tiene el puesto.'),
                           'validos': validos, 'descartados': descartados},
            'advertencias': [],
        }
        if len(validos) + len(descartados) == 1:
            ficha['empleado'] = (validos + descartados)[0]
        return ficha
    return {
        'puesto': {k: cab[k] for k in ('puesto', 'servicio', 'tipo_servicio', 'turno', 'zona',
                                       'inicio', 'fin', 'urgencia', 'urgencia_estado')},
        'fecha_evaluacion': ref.isoformat(),
        'requisitos': req,
        'evaluacion': {
            'validos': validos, 'descartados': descartados,
            'n_validos': len(validos), 'n_descartados': len(descartados),
            'conteo_motivos': conteo, 'motivo_critico': motivo_critico,
            'derivacion': 'S3' if validos else 'S4', 'regla_derivacion': 'S2-R09',
        },
        'advertencias': ([] if validos else
                         [f'No hay candidatos válidos: el motivo que más descartes concentra es '
                          f'«{motivo_critico}» (S2-R09).']),
    }


def registrar(grafo, ficha):
    """Escribe un EvaluacionEmpleadoPuesto por empleado (lo que S3 necesita)."""
    puesto = ficha['puesto']['puesto']
    ids = []
    for r in ficha['evaluacion']['validos'] + ficha['evaluacion']['descartados']:
        eid = f"EV-{r['legajo']}-{puesto}"
        grafo.escribir(
            'W-S2-evaluacion', evaluacion=eid, puesto=puesto, legajo=r['legajo'],
            estado_S2=r['estado_S2'],
            motivos_descarte=[m['motivo'] for m in r['motivos']],
            deseables_faltantes=r['deseables_faltantes'],
            deseables_vencidos=[d['aptitud'] for d in r.get('deseables_vencidos') or []],
            deseables_estado=r['deseables_estado'],
            margen_vigencia_dias=r['margen_vigencia']['dias'],
            solape_horario=r['solape_horario']['fraccion'],
            solape_estado=r['solape_horario']['estado'],
            cerc_min=r['cercania_estimada']['min'], cerc_max=r['cercania_estimada']['max'],
            cerc_estado=r['cercania_estimada']['estado'],
            exp_min=r['experiencia']['min'], exp_max=r['experiencia']['max'],
            exp_estado=r['experiencia']['estado'],
            des_min=r['desempeno']['min'], des_max=r['desempeno']['max'],
            des_estado=r['desempeno']['estado'],
            advertencias=r['advertencias'],
            advertencias_estado='con_dato' if r['estado_S2'] == 'valido' else 'sin_dato',
            fecha_evaluacion=ficha['fecha_evaluacion'])
        ids.append(eid)
    return ids


# ==================================================================== LLM
def _esquema_ok(d):
    if not isinstance(d, dict):
        return ['La respuesta no es un objeto JSON.']
    if d.get('intencion') not in INTENCIONES:
        return [f'"intencion" tiene que ser una de: {", ".join(INTENCIONES)}.']
    return []


def extraer(grafo, texto, catalogo):
    sistema = prompts.cargar('s2_extraccion', aptitudes=catalogo['aptitudes'],
                             turnos=catalogo['turnos'], servicios=catalogo['servicios'])
    return pedir_json(sistema, f'Consulta: "{texto}"', validador=_esquema_ok)


def explicar(grafo, ficha, intencion):
    try:
        sistema = prompts.cargar('s2_explicacion')
    except PromptFaltante:
        return respaldo(ficha), None, False
    ficha_llm = ficha_para_explicar(ficha)
    exigencias = {'sin_juicio_personas': False}
    if intencion == 'candidatos_puesto' and (ficha.get('consulta') or {}).get('filtro_estado') != 'descartados':
        exigencias['legajos'] = [r['legajo'] for r in ficha.get('evaluacion', {}).get('validos', [])]
    # Ya no se exige mencionar SIN_DATO de los descartados: a un descartado no se le evalúan
    # los deseables ni las entradas de S3, y no hay que hablar de eso (devolución del PI4).
    validador = lambda d: (validar_explicacion(d, ficha_llm, exigencias) +
                           (validar_s2(d.get('texto'), ficha_llm) if isinstance(d, dict) else []))
    try:
        r = pedir_json(sistema, 'FICHA S2: ' + json.dumps(ficha_llm, ensure_ascii=False, default=str),
                       temperatura=config.TEMP_EXPLICACION, max_tokens=config.MAX_TOKENS_EXPLICACION,
                       reintentos=config.MAX_INTENTOS - 1, validador=validador)
    except ErrorLLM:
        return respaldo(ficha), None, False
    if r.datos and r.datos.get('texto'):
        return r.datos['texto'], r, True
    return respaldo(ficha), r, False


CAMPOS_DESCARTADO = ('legajo', 'nombre', 'estado_S2', 'motivos', 'controles', 'siguiente_paso')


def ficha_para_explicar(ficha):
    """Copia de la ficha para el LLM. A los descartados se les quitan margen, solape,
    cercanía, experiencia, desempeño y deseables: son entradas de S3 y, si el modelo las
    ve, tiende a hablar de la afinidad de alguien que no va a tener afinidad."""
    if 'evaluacion' not in ficha:
        return ficha
    f = json.loads(json.dumps(ficha, ensure_ascii=False, default=str))

    def recorte(r):
        return ({k: r[k] for k in CAMPOS_DESCARTADO if k in r}
                if r.get('estado_S2') == 'descartado' else r)
    f['evaluacion']['descartados'] = [recorte(r) for r in f['evaluacion'].get('descartados', [])]
    if f.get('empleado'):
        f['empleado'] = recorte(f['empleado'])
    return f


def ficha_aptitud(filas, aptitud, ref=None):
    """Intención aptitud_vigente: el estado de cada certificación lo decide el código,
    no el LLM (vigente, vencida o sin vencimiento)."""
    ref = ref or _fecha_ref()
    vigentes, vencidas, sin_venc = [], [], []
    for f in filas:
        v = f.get('vencimiento')
        fila = {'legajo': f['legajo'], 'nombre': f['nombre']}
        if not v:
            sin_venc.append(dict(fila, estado='sin vencimiento registrado'))
        elif date.fromisoformat(str(v)[:10]) < ref:
            vencidas.append(dict(fila, estado='vencida', vencimiento=_fmt(v),
                                 frase=f'tiene la aptitud {_nombre(aptitud)}, vencida el {_fmt(v)}'))
        else:
            vigentes.append(dict(fila, estado='vigente', vencimiento=_fmt(v)))
    return {'aptitud': aptitud, 'fecha_referencia': _fmt(ref),
            'vigentes': vigentes, 'vencidas': vencidas, 'sin_vencimiento': sin_venc,
            'nota': ('Quien no figura en ninguna lista no tiene registrada la aptitud; '
                     'no es lo mismo que tenerla vencida.')}


def _frase_motivos(r):
    return '; '.join(f"{m.get('frase') or m['motivo']} ({m['regla']})" for m in r['motivos'])


def respaldo(ficha):
    if 'evaluacion' not in ficha:  # aptitud_vigente
        t = f"Aptitud {ficha.get('aptitud')} al {ficha.get('fecha_referencia')}. "
        if ficha.get('vigentes'):
            t += 'Vigente: ' + '; '.join(f"{x['nombre']} ({x['legajo']}), vence el {x['vencimiento']}"
                                         for x in ficha['vigentes']) + '. '
        if ficha.get('vencidas'):
            t += 'Vencida: ' + '; '.join(f"{x['nombre']} ({x['legajo']}), venció el {x['vencimiento']}"
                                         for x in ficha['vencidas']) + '. '
        return t + 'Quien no figura no tiene registrada la aptitud.'
    p, e = ficha['puesto'], ficha['evaluacion']
    if e.get('alcance') == 'empleados_consultados':
        partes = []
        for r in e['validos']:
            partes.append(f"{r['nombre']} ({r['legajo']}) puede cubrir el puesto {p['puesto']} "
                          f"({p['servicio']}, turno {p['turno']}): {r['siguiente_paso']}.")
        for r in e['descartados']:
            partes.append(f"{r['nombre']} ({r['legajo']}) quedó descartado para el puesto "
                          f"{p['puesto']} ({p['servicio']}, turno {p['turno']}) porque "
                          f"{_frase_motivos(r)}. Por eso {r['siguiente_paso']}.")
        return ' '.join(partes)
    exc = ', '.join(r['aptitud'] for r in ficha['requisitos']['excluyentes']) or 'ninguna'
    t = (f"Puesto {p['puesto']} ({p['servicio']}, turno {p['turno']}, zona {p['zona']}). "
         f"Aptitudes excluyentes: {exc}. ")
    if e['n_validos']:
        t += 'Pueden cubrirlo: ' + '; '.join(
            f"{r['nombre']} ({r['legajo']})" for r in e['validos']) + '. '
    else:
        t += (f"No hay candidatos válidos. Motivo crítico: {e['motivo_critico']} (S2-R09). ")
    if e['descartados']:
        t += 'Descartados: ' + '; '.join(
            f"{r['nombre']} ({r['legajo']}): {_frase_motivos(r)}"
            for r in e['descartados']) + '. '
    t += ('Solo las personas que pueden cubrirlo pasan al cálculo de afinidad (S3); '
          'las descartadas no participan del orden.' if e['n_validos']
          else 'Se informa el listado vacío (S4).')
    return t
