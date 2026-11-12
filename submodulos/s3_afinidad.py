"""Submodulo S3 — Calculo de Afinidad y Priorizacion con Logica Difusa (Gallardo).

Lee del grafo lo que submodulos/inferencia.py ya calculo y persistio, y lo explica.
Las simulaciones hipoteticas se calculan en el momento con el motor difuso y NO se
guardan, igual que en el PI4.

Intenciones: ranking_afinidad, detalle_afinidad, comparar_candidatos,
datos_faltantes, simular_afinidad, fuera_de_dominio.
"""
import json

from core import config, prompts
from core.prompts import PromptFaltante
from core.grafo import normalizar
from core.llm import ErrorLLM, pedir_json
from core.validador import validar_explicacion
from submodulos import inferencia

INTENCIONES = ('ranking_afinidad', 'detalle_afinidad', 'comparar_candidatos',
               'datos_faltantes', 'simular_afinidad', 'fuera_de_dominio')

RANGOS = {'desempeno': (1, 10, 'El desempeño va de 1 a 10'),
          'cercania_min': (0, 10000, 'La cercanía en minutos no puede ser negativa'),
          'experiencia_meses': (0, 1000, 'La experiencia en meses no puede ser negativa')}


def _esquema_ok(d):
    if not isinstance(d, dict):
        return ['La respuesta no es un objeto JSON.']
    if d.get('intencion') not in INTENCIONES:
        return [f'"intencion" tiene que ser una de: {", ".join(INTENCIONES)}.']
    return []


def extraer(texto):
    sistema = prompts.cargar('s3_extraccion')
    return pedir_json(sistema, f'Pregunta: {texto}', validador=_esquema_ok)


def validar_simulacion(sim):
    """Determinista, en codigo: el prompt tiene prohibido corregir valores fuera de rango."""
    if not sim or not any(v is not None for v in sim.values()):
        return '¿Qué dato querés simular: la cercanía en minutos, la experiencia en meses o el desempeño?'
    for clave, valor in sim.items():
        if valor is None:
            continue
        if not isinstance(valor, (int, float)):
            return f'No entendí el valor «{valor}». ¿Me lo decís con un número?'
        bajo, alto, mensaje = RANGOS.get(clave, (None, None, ''))
        if bajo is not None and not (bajo <= valor <= alto):
            return f'{mensaje} y pediste {valor:g}. ¿Qué valor querés simular?'
    return None


_VACIAS = {'el', 'la', 'los', 'las', 'de', 'del', 'en', 'para', 'al'}


def _palabras(texto):
    import re
    return {w for w in re.findall(r'\w+', normalizar(texto or '')) if w not in _VACIAS}


def resolver_puesto(grafo, puesto_ref, servicio_ref):
    catalogo = grafo.leer('S3-catalogo')
    if puesto_ref:
        for p in catalogo:
            if p['puesto'].lower() == str(puesto_ref).lower():
                return p, None
    if servicio_ref:
        # Tolerante como en el PI4 de S3: «Clínica de Luján» -> Clínica Luján. Se compara
        # por palabras, sin artículos ni preposiciones, en lugar de por subcadena.
        ref = _palabras(servicio_ref)

        def coincide(p):
            nom = _palabras(p['servicio'])
            if nom and (nom <= ref or (ref and ref <= nom)):
                return True
            return any(_palabras(a) and _palabras(a) <= ref for a in (p.get('alias_servicio') or []))
        fuertes = [p for p in catalogo if coincide(p)]
        if len(fuertes) == 1:
            return fuertes[0], None
        if len(fuertes) > 1:
            return None, ('¿A cuál te referís? ' + ', '.join(f"{p['servicio']} ({p['puesto']})"
                                                             for p in fuertes))
    opciones = ', '.join(sorted({p['servicio'] for p in catalogo}))
    return None, f'No encontré ese puesto. Opciones: {opciones}'


def resolver_empleado(puesto, referencia):
    n = normalizar(referencia)
    evs = puesto.get('evaluaciones') or []
    exactos = [e for e in evs if normalizar(e['legajo']) == n or normalizar(e['nombre']) == n]
    if len(exactos) == 1:
        return exactos[0], None
    parciales = [e for e in evs if n and n in normalizar(e['nombre'])]
    if len(parciales) == 1:
        return parciales[0], None
    if len(parciales) > 1:
        return None, ('¿A cuál te referís? ' + ', '.join(f"{e['nombre']} ({e['legajo']})"
                                                         for e in parciales))
    return None, f"No encontré a {referencia} en {puesto['servicio']}."


def citables_de(datos):
    """Diccionario clave -> valor con las unicas evidencias que el LLM puede citar."""
    c = {}

    def recorrer(obj):
        if isinstance(obj, dict):
            for e in obj.get('evidencias') or []:
                if not isinstance(e, dict) or not e.get('id'):
                    continue
                if e.get('tipo') == 'afinidad':
                    c[e['id']] = [e.get('valor_min'), e.get('valor_max')]
                elif e.get('valor') is not None:
                    c[e['id']] = e['valor']
            if obj.get('evaluacion'):
                for campo in ('categoria_S4', 'prioridad_S4', 'confiabilidad', 'margen_vigencia_dias',
                              'solape_horario'):
                    if obj.get(campo) is not None:
                        c[f"{obj['evaluacion']}.{campo}"] = obj[campo]
            for v in obj.values():
                recorrer(v)
        elif isinstance(obj, list):
            for v in obj:
                recorrer(v)

    recorrer(datos)
    return c


def responder(grafo, texto, extraido=None):
    r_ext = None
    if extraido is None:
        r_ext = extraer(texto)
        if r_ext.datos is None:
            return {'submodulo': 'S3', 'respuesta': 'No pude interpretar la pregunta. ¿Podés reformularla?'}
        grafo.traza.agregar('extraccion', {'submodulo': 'S3', **r_ext.como_dict()})
        extraido = r_ext.datos

    intencion = extraido.get('intencion')
    if intencion == 'fuera_de_dominio':
        if extraido.get('motivo') == 'cambio_de_decision':
            return {'submodulo': 'S3', 'intencion': intencion,
                    'respuesta': 'No puedo cambiar categorías, prioridades ni el orden: los asigna '
                                 'la base de conocimiento (S4). Sí puedo explicarte en qué se apoyan.'}
        return {'submodulo': 'S3', 'intencion': intencion,
                'respuesta': 'Solo puedo responder sobre la afinidad de los candidatos de una vacante.'}

    puesto, aclaracion = resolver_puesto(grafo, extraido.get('puesto_ref'), extraido.get('servicio_ref'))
    if aclaracion:
        return {'submodulo': 'S3', 'intencion': intencion, 'respuesta': aclaracion, 'aclaracion': True}

    legajos, refs = [], extraido.get('empleados_ref') or []
    for ref in refs:
        emp, aclaracion = resolver_empleado(puesto, ref)
        if aclaracion:
            return {'submodulo': 'S3', 'intencion': intencion, 'respuesta': aclaracion, 'aclaracion': True}
        legajos.append(emp['legajo'])

    # ---------------------------------------------------- recuperacion
    exigencias = {'citas_obligatorias': True}
    if intencion == 'ranking_afinidad':
        fila = grafo.una('S3-ranking', puesto=puesto['puesto'])
        datos = (fila or {}).get('ranking')
        if not datos or not [c for c in (datos.get('candidatos') or []) if c]:
            return {'submodulo': 'S3', 'intencion': intencion,
                    'respuesta': f"El puesto {puesto['puesto']} todavía no tiene un listado calculado. "
                                 'Corré la evaluación (S2) y el cálculo de afinidad (S3) primero.'}
        datos['candidatos'] = [c for c in datos['candidatos'] if c]
        exigencias['orden_provisional'] = datos.get('criterio_orden') == 'PROVISIONAL'
        exigencias['sin_ganador'] = any(
            c.get('estado_orden_con_siguiente') in ('empate tecnico', 'no determinado')
            for c in datos['candidatos'])
        exigencias['incertidumbre'] = any((c.get('confiabilidad') or 1) < 1 for c in datos['candidatos'])

    elif intencion in ('detalle_afinidad', 'datos_faltantes', 'simular_afinidad'):
        if not legajos:
            return {'submodulo': 'S3', 'intencion': intencion,
                    'respuesta': '¿Sobre qué persona querés que te explique?', 'aclaracion': True}
        fila = grafo.una('S3-detalle', puesto=puesto['puesto'], legajo=legajos[0])
        datos = (fila or {}).get('detalle') or {}
        if (datos.get('estado_S2') or '') == 'descartado':
            # A un descartado solo se le envian identidad y motivos: no hay afinidad que citar.
            datos = {k: datos.get(k) for k in ('puesto', 'servicio', 'legajo', 'empleado',
                                               'evaluacion', 'estado_S2', 'motivos_descarte')}
            exigencias = {'descartado': True}
        else:
            exigencias['incertidumbre'] = (datos.get('confiabilidad') or 1) < 1
            exigencias['sin_dato'] = any(
                (v or {}).get('estado') in ('DESCONOCIDO', 'ESTIMADO')
                for v in (datos.get('entradas') or {}).values())
            if intencion == 'simular_afinidad':
                problema = validar_simulacion(extraido.get('simulacion'))
                if problema:
                    return {'submodulo': 'S3', 'intencion': intencion, 'respuesta': problema,
                            'aclaracion': True}
                datos = _simular(datos, extraido['simulacion'])
                exigencias = {'hipotetico': True, 'citas_obligatorias': False}

    elif intencion == 'comparar_candidatos':
        if len(legajos) < 2:
            return {'submodulo': 'S3', 'intencion': intencion,
                    'respuesta': '¿A qué dos personas querés comparar?', 'aclaracion': True}
        fila = grafo.una('S3-comparar', puesto=puesto['puesto'], legajos=legajos)
        datos = (fila or {}).get('comparacion') or {}
        estados = datos.get('estados_camino') or []
        exigencias['sin_ganador'] = (not estados) or any(
            e in ('empate tecnico', 'no determinado') for e in estados)
        exigencias['incertidumbre'] = any((c.get('confiabilidad') or 1) < 1
                                          for c in datos.get('candidatos') or [])
    else:
        return {'submodulo': 'S3', 'respuesta': 'No pude interpretar la pregunta.'}

    citables = citables_de(datos)
    try:
        sistema = prompts.cargar('s3_explicacion')
    except PromptFaltante:
        return {'submodulo': 'S3', 'intencion': intencion, 'datos': datos, 'citables': citables,
                'respuesta': respaldo(datos, intencion), 'fidelidad': 'respaldo (falta el prompt de S3)'}
    mensaje = ('PREGUNTA: ' + texto + '\nRESULTADO: ' +
               json.dumps({'intencion': intencion, 'datos': datos, 'citables': citables},
                          ensure_ascii=False, default=str))
    validador = lambda d: validar_explicacion(d, {'datos': datos, 'citables': citables}, exigencias)
    try:
        r = pedir_json(sistema, mensaje, temperatura=config.TEMP_EXPLICACION,
                       max_tokens=config.MAX_TOKENS_EXPLICACION,
                       reintentos=config.MAX_INTENTOS - 1, validador=validador)
    except ErrorLLM as e:
        return {'submodulo': 'S3', 'intencion': intencion, 'datos': datos, 'citables': citables,
                'respuesta': respaldo(datos, intencion),
                'fidelidad': f'respaldo (A6): el modelo no respondió — {str(e)[:120]}'}
    grafo.traza.agregar('explicacion', {'submodulo': 'S3', 'citables': len(citables),
                                        'fidelidad': 'OK' if (r.datos and r.datos.get('texto')) else 'respaldo',
                                        **r.como_dict()})
    if r.datos and r.datos.get('texto'):
        return {'submodulo': 'S3', 'intencion': intencion, 'datos': datos,
                'citables': citables, 'respuesta': r.datos['texto'], 'fidelidad': 'OK'}
    return {'submodulo': 'S3', 'intencion': intencion, 'datos': datos, 'citables': citables,
            'respuesta': respaldo(datos, intencion), 'fidelidad': 'respaldo (A6)'}


def _simular(detalle, sim):
    """Recalculo hipotetico con el motor difuso. No escribe en el grafo."""
    ent = detalle.get('entradas') or {}
    medio = lambda d, defecto: (((d or {}).get('min') if (d or {}).get('min') is not None else defecto)
                                + ((d or {}).get('max') if (d or {}).get('max') is not None else defecto)) / 2.0
    base_cer = medio(ent.get('cercania'), 45.0)
    base_exp = medio(ent.get('experiencia'), 12.0)
    base_des = medio(ent.get('desempeno'), 5.5)
    g = detalle.get('grados_urgencia') or {}
    ug = {'baja': g.get('baja') or 0.0, 'media': g.get('media') or 0.0, 'alta': g.get('alta') or 0.0}
    cer = sim.get('cercania_min') if sim.get('cercania_min') is not None else base_cer
    exp = sim.get('experiencia_meses') if sim.get('experiencia_meses') is not None else base_exp
    des = sim.get('desempeno') if sim.get('desempeno') is not None else base_des
    antes = inferencia.simular(ug, base_exp, base_des, base_cer,
                               detalle.get('margen_vigencia_dias'), detalle.get('solape_horario'))
    despues = inferencia.simular(ug, exp, des, cer,
                                 detalle.get('margen_vigencia_dias'), detalle.get('solape_horario'))
    cambian = []
    for regla in set(antes['reglas']) | set(despues['reglas']):
        a, b = antes['reglas'].get(regla, 0.0), despues['reglas'].get(regla, 0.0)
        if abs(a - b) > 0.05:
            cambian.append({'regla': regla, 'antes': a, 'despues': b})
    cambian.sort(key=lambda x: abs(x['despues'] - x['antes']), reverse=True)
    return {
        'hipotetico': True, 'empleado': detalle.get('empleado'), 'legajo': detalle.get('legajo'),
        'puesto': detalle.get('puesto'), 'servicio': detalle.get('servicio'),
        'evaluacion': detalle.get('evaluacion'),
        'base_grafo': detalle.get('afinidad'), 'simulada': [despues['afinidad'], despues['afinidad']],
        'categoria_S4': detalle.get('categoria_S4'),
        'entrada_grafo': {'cercania_min': base_cer, 'experiencia_meses': base_exp, 'desempeno': base_des},
        'entrada_simulada': {k: v for k, v in sim.items() if v is not None},
        'reglas_que_cambian': cambian[:3], 'version': despues['version'],
    }


def respaldo(datos, intencion):
    if datos.get('hipotetico'):
        return (f"Simulación hipotética: la afinidad pasaría de {datos['base_grafo']} a "
                f"{datos['simulada'][0]}. No se guarda y la categoría no cambia "
                f"({datos.get('categoria_S4')}).")
    if datos.get('motivos_descarte'):
        return (f"{datos.get('empleado')} quedó descartado en la preselección (S2): " +
                '; '.join(datos['motivos_descarte']) + '. No hay afinidad que explicar.')
    if intencion == 'ranking_afinidad':
        filas = '; '.join(f"{c['empleado']} ({c['legajo']}) afinidad {c['afinidad']}, "
                          f"categoría {c.get('categoria_S4')}" for c in datos.get('candidatos', []))
        return (f"Listado de {datos.get('servicio')}: {filas}. El criterio de orden es "
                f"{datos.get('criterio_orden')} y todavía no fue validado por RR. HH.")
    return ('No se pudo redactar una explicación verificada. Datos del grafo: ' +
            json.dumps(datos, ensure_ascii=False, default=str)[:600])
