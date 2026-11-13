"""Submodulo S4 — Generacion de Explicacion y Consolidacion del Listado Final (Leon).

Recupera del grafo la ficha ya calculada (consultas E, C, 1, 5 del PG2 + auxiliares)
y la verbaliza. No recalcula nada.

Router deterministico, como en el PI4:
  0 candidatos validos        -> consulta 5 y mensaje fijo, SIN LLM (regla A3)
  pregunta por el listado     -> consulta E
  candidato en el listado     -> consulta E filtrada + consulta C
  candidato que no figura     -> consulta 1 (motivos de descarte)
"""
import json
import re

from core import config, prompts
from core.prompts import PromptFaltante
from core.grafo import normalizar
from core.llm import ErrorLLM, pedir_json
from core.validador import validar_explicacion, validar_s4

INTENCIONES = ('consultar_listado', 'consultar_candidato', 'fuera_de_dominio')


def _esquema_ok(d):
    if not isinstance(d, dict):
        return ['La respuesta no es un objeto JSON.']
    if d.get('intencion') not in INTENCIONES:
        return [f'"intencion" tiene que ser una de: {", ".join(INTENCIONES)}.']
    return []


def extraer(texto):
    sistema = prompts.cargar('s4_extraccion')
    return pedir_json(sistema, f'Consulta: "{texto}"', validador=_esquema_ok)


def resolver_puesto(grafo, puesto_id, servicio, turno):
    filas = grafo.leer('S2-Q2-puesto', puesto_id=puesto_id,
                       servicio=normalizar(servicio) if servicio else None,
                       turno=turno)
    if puesto_id:
        # Si el id vino explícito (p. ej. desde la cadena), manda sobre el nombre.
        exactos = [f for f in filas if f['puesto'] == puesto_id]
        if len(exactos) == 1:
            return exactos[0], None
    if len(filas) == 1:
        return filas[0], None
    if len(filas) > 1:
        return None, ('¿A cuál de estas vacantes te referís? ' +
                      ', '.join(f"{f['servicio']} turno {f['turno']} ({f['puesto']})" for f in filas))
    registrados = grafo.leer('S2-Q2b-puestos-registrados')
    if not registrados:
        return None, 'Todavía no hay vacantes registradas en la base de conocimiento.'
    return None, ('No reconocemos esa vacante. Puestos registrados: ' +
                  '; '.join(f"{f['puesto']} ({f['servicio']}, turno {f['turno']})"
                            for f in registrados) + '. ¿Para cuál es la consulta?')


def mensaje_listado_vacio(grafo, puesto, evaluados=None):
    """Regla A3: se arma con la consulta 5, sin invocar al LLM.

    PG3 (pruebas 13/11, B07): si el Listado_Final no llegó a escribirse, n_descartados
    viene nulo y el texto decía «Se evaluaron 0 empleados». La cadena pasa ahora el
    conteo de S2 (evaluados) para usarlo en ese caso.
    """
    f = grafo.una('S4-5-listado-vacio', puesto=puesto) or {}
    n = f.get('descartados')
    if n is None:
        n = evaluados if evaluados is not None else 0
    lineas = [f"No hay candidatos válidos para la vacante {f.get('puesto')} "
              f"({f.get('servicio')}, turno y zona del pedido). Se evaluaron "
              f"{n} empleados y ninguno superó los controles "
              f"excluyentes de S2.", '']

    # S2-R01: una misma aptitud puede venir del pedido y del catálogo. Si viene de
    # los dos, no son dos requisitos: es uno solo que el catálogo promovió.
    del_pedido = {r['aptitud']: r for r in (f.get('del_pedido') or []) if r.get('aptitud')}
    del_catalogo = {r['aptitud']: r for r in (f.get('del_catalogo') or []) if r.get('aptitud')}

    lineas.append('Requisitos que se aplicaron:')
    if not del_pedido and not del_catalogo:
        lineas.append('  · ninguno registrado')
    for aptitud in sorted(set(del_pedido) | set(del_catalogo)):
        en_pedido, en_catalogo = del_pedido.get(aptitud), del_catalogo.get(aptitud)
        if en_pedido and en_catalogo:
            if en_pedido.get('excluyente'):
                detalle = ('excluyente — la pidió el pedido y además la exige el '
                           f"{en_catalogo.get('origen')}")
            else:
                detalle = (f"excluyente — el pedido la pidió como deseable ({en_pedido.get('regla')}) "
                           f"y el {en_catalogo.get('origen')} la promueve a excluyente (S2-R01)")
        elif en_catalogo:
            detalle = (f"excluyente — no la pidió el pedido: la exige el "
                       f"{en_catalogo.get('origen')} (S2-R01)")
        else:
            marca = 'excluyente' if en_pedido.get('excluyente') else 'deseable'
            detalle = f"{marca} — la pidió el pedido ({en_pedido.get('regla')})"
        lineas.append(f'  · {legible(aptitud)} — {detalle}')
    if not del_pedido and del_catalogo:
        lineas.append('  (el pedido no especificó ninguna aptitud por su cuenta)')
    lineas.append('')

    conteo = f.get('conteo_motivos') or []
    if conteo:
        lineas.append('Por qué quedó afuera cada uno:')
        for c in conteo:
            lineas.append(f'  · {_legible_en_frase(c)}')
        lineas.append('')
    if f.get('motivo_critico'):
        lineas.append('El motivo que más descartes concentra es: '
                      f"{_legible_en_frase(f['motivo_critico'])} (S2-R09).")
    # PG3 (B07): sin «None (DESCONOCIDO)» ni códigos de estado en el texto.
    if f.get('urgencia'):
        lineas.append(f"Urgencia registrada: {f.get('urgencia')}.")
    else:
        lineas.append('Urgencia registrada: no determinada.')
    lineas.append('El sistema no propone candidatos que no cumplen los requisitos excluyentes '
                  '(regla A3); cómo cubrir la vacante queda a criterio de RR. HH.')
    return '\n'.join(lineas)


# ==================================================================== devolución del PI4 de S4
# La cátedra pidió que la validación controle el significado de lo que se afirma:
#   CP1: un deseable faltante presentado como advertencia;
#   CP2: una cifra (0,601, la afinidad) atribuida a una evidencia de advertencia, que no
#        tiene valor; y la posición explicada sin comparar las prioridades;
#   CP3: SIN_DATO leído como «no se encontraron deseables faltantes».
# Para eso el código le entrega al LLM la lectura ya hecha (frases fijas) y la comparación
# del orden ya armada, y validar_s4() verifica el texto contra esos datos.

PREGUNTA_ORDEN = re.compile(
    r'orden|ranking|posici|lugar|primer|segund|tercer|[uú]ltim|antes|despu[eé]s|arriba|abajo|'
    r'por qu[eé] .*(m[aá]s|menos|mejor|peor)', re.I)


def pregunta_por_orden(texto, extraido):
    return 'orden' in ((extraido or {}).get('aspectos') or []) or bool(PREGUNTA_ORDEN.search(texto or ''))


# Nombres legibles de los códigos del grafo. El reclutador no tiene por qué leer
# SOLAPE_PARCIAL o manejo_residuos_patogenicos: la devolución del PI4 de S2 ya llevó a
# sacar los valores técnicos de las respuestas de S2; acá se hace lo mismo para S4.
# Si un código no está en la tabla, se escribe en minúsculas y con espacios.
LEGIBLE = {
    'MARGEN_CORTO': 'margen de vigencia corto (una certificación vence pronto)',
    'SOLAPE_PARCIAL': 'solape parcial de horario con el turno pedido',
    'ENTRADAS_INCOMPLETAS': 'entradas incompletas para calcular la afinidad',
    'TRASLADO_ESTIMADO': 'traslado estimado por zona, no medido',
    'TRASLADO_DESCONOCIDO': 'traslado desconocido',
    'HORARIO_DESCONOCIDO': 'horario de disponibilidad desconocido',
    'DESEMPENO_DESCONOCIDO': 'desempeño reciente desconocido',
    'DESEMPEÑO_DESCONOCIDO': 'desempeño reciente desconocido',
    'DESEMPENO_BAJO_RECIENTE': 'desempeño bajo reciente',
    'DESEMPEÑO_BAJO_RECIENTE': 'desempeño bajo reciente',
    'EXPERIENCIA_DESCONOCIDA': 'experiencia equivalente desconocida',
    'AFINIDAD_IMPRECISA': 'afinidad imprecisa (intervalo ancho)',
    'AFINIDAD_EN_TRANSICION': 'afinidad en el límite entre dos categorías',
    'URGENCIA_ESTIMADA': 'urgencia estimada',
    'URGENCIA_DESCONOCIDA': 'urgencia desconocida',
    'MARGEN_SIN_DATO': 'margen de vigencia sin dato',
    'SERVICIO_FUERA_DE_MATRIZ': 'servicio fuera de la matriz de cercanía',
    'ORDEN_NO_DETERMINADO': 'orden no determinado con el siguiente',
    'EMPATE_TECNICO': 'empate técnico con el siguiente',
    'SIN_CANDIDATO_PLENO': 'ningún candidato cumple plenamente',
    'SIN_DATO': 'sin dato',
    'DESCONOCIDO': 'desconocido',
    # aptitudes del catálogo del PG2 (las nuevas se escriben con espacios)
    'limpieza_hospitalaria': 'limpieza hospitalaria',
    'manejo_residuos_patogenicos': 'manejo de residuos patogénicos',
    'manejo_maquinaria_industrial': 'manejo de maquinaria industrial',
    'trabajo_en_altura': 'trabajo en altura',
    'Recomendado': 'Recomendado',
    'Recomendado_con_reservas': 'Recomendado con reservas',
    'Baja_prioridad': 'Baja prioridad',
}


def legible(codigo):
    """Traduce un código del grafo a texto para el reclutador."""
    if codigo is None:
        return ''
    c = str(codigo)
    # El PG2 cargó algunos faltantes con sufijo: «manejo_residuos_patogenicos (vencida)».
    m = re.match(r'^(\S+)\s+(\(.*\))$', c)
    if m:
        return f'{legible(m.group(1))} {m.group(2)}'
    if c in LEGIBLE:
        return LEGIBLE[c]
    return c.replace('_', ' ').lower()


def _num(x, dec=3):
    """Cifras con coma decimal y tres decimales, como en los informes del grupo."""
    if x is None:
        return 'sin dato'
    return f'{float(x):.{dec}f}'.replace('.', ',')


def afinidad_texto(ficha):
    a = ficha.get('afinidad') or [None, None]
    if a[0] is None:
        return 'afinidad sin dato'
    if a[0] == a[1]:
        return f'afinidad {_num(a[0])}'
    conf = ficha.get('confiabilidad')
    return (f'afinidad entre {_num(a[0])} y {_num(a[1])} (dato impreciso: alguna entrada no se '
            f'observó; confiabilidad {_num(conf)})')


def normalizar_texto(texto):
    """Reemplaza en la redacción del LLM los códigos del grafo que tienen un nombre legible
    conocido (Recomendado_con_reservas -> Recomendado con reservas). Es un cambio de forma,
    no de contenido: la validación corre después, sobre el texto ya normalizado, y lo que no
    está en la tabla sigue siendo rechazado."""
    if not isinstance(texto, str):
        return texto
    for codigo in sorted((k for k in LEGIBLE if '_' in k), key=len, reverse=True):
        texto = re.sub(r'(?<![\w])' + re.escape(codigo) + r'(?![\w])', LEGIBLE[codigo], texto)
    return texto


def _lista(x):
    return ', '.join(legible(i) for i in x)


_CODIGO = re.compile(r'\b[A-Za-zÁ-úñÑ]+(?:_[A-Za-zÁ-úñÑ0-9]+)+\b')


def _legible_en_frase(frase):
    """Reemplaza los códigos con guion bajo dentro de una frase («aptitud faltante:
    manejo_maquinaria_industrial» -> «aptitud faltante: manejo de maquinaria industrial»)."""
    return _CODIGO.sub(lambda m: legible(m.group(0)), str(frase or ''))


def lectura(ficha, descartado=False):
    """Cómo se lee cada bloque de la ficha, en frases fijas. Deseables y advertencias van
    separados y con nombre propio para que el LLM no los mezcle (mejora 5 del PI4)."""
    if descartado:
        return {'aptitudes_deseables': ('no se evaluaron porque la persona quedó descartada en S2: '
                                        'no se sabe si le falta alguna'),
                'advertencias': 'no se evaluaron porque la persona quedó descartada en S2'}
    faltan = ficha.get('deseables_faltantes') or []
    vencidas = ficha.get('deseables_vencidos') or []
    if ficha.get('deseables_estado') == 'SIN_DATO':
        des = 'no se evaluaron (sin dato): no se sabe si le falta alguna'
    else:
        partes = []
        if faltan:
            partes.append('no tiene la aptitud deseable ' + _lista(faltan))
        if vencidas:
            partes.append('tiene la aptitud deseable ' + _lista(vencidas) + ', pero vencida')
        des = '; '.join(partes) if partes else 'tiene todas las aptitudes deseables del puesto'
        if partes:
            des += ' (es una aptitud deseable, no una advertencia)'
    adv = ficha.get('advertencias') or []
    if ficha.get('advertencias_estado') == 'sin_dato':
        adv_t = 'no hay dato de advertencias: no se evaluaron'
    elif adv:
        adv_t = 'tiene la advertencia ' + _lista(adv)
    else:
        adv_t = 'no tiene advertencias registradas'
    salida = {'aptitudes_deseables': des, 'advertencias': adv_t,
              'categoria': legible(ficha.get('categoria')),
              'afinidad': afinidad_texto(ficha),
              'prioridad': f"prioridad {_num(ficha.get('prioridad'))}"}
    if ficha.get('marcas'):
        salida['marcas'] = 'marcas de calidad del dato: ' + _lista(ficha['marcas'])
    return salida


def comparacion_orden(objetivo, todas):
    """Posición del candidato frente a los que quedaron justo antes y justo después.
    Las diferencias las calcula Python; el LLM solo las cita."""
    filas = sorted(todas, key=lambda f: f.get('posicion_por_prioridad') or 99)
    tabla = [{'posicion_por_prioridad': f.get('posicion_por_prioridad'),
              'posicion_por_afinidad': f.get('posicion_por_afinidad'),
              'empleado': f.get('empleado'), 'legajo': f.get('legajo'),
              'prioridad': f.get('prioridad'), 'afinidad': f.get('afinidad'),
              'categoria': f.get('categoria'), 'advertencias': f.get('advertencias') or []}
             for f in filas]
    i = next((k for k, f in enumerate(filas) if f.get('legajo') == objetivo), None)
    if i is None:
        return None
    vecinos = []
    for j, rel in ((i - 1, 'queda antes'), (i + 1, 'queda después')):
        if 0 <= j < len(filas):
            o = filas[j]
            dif = (round(abs((filas[i].get('prioridad') or 0) - (o.get('prioridad') or 0)), 3)
                   if o.get('prioridad') is not None and filas[i].get('prioridad') is not None else None)
            vecinos.append({'legajo': o.get('legajo'), 'empleado': o.get('empleado'), 'relacion': rel,
                            'prioridad': o.get('prioridad'), 'diferencia_de_prioridad': dif})
    # PG3 (B09): en minúscula; el validador rechaza ahora «PROVISIONAL» en el texto.
    return {'criterio': 'el listado se ordena por prioridad (criterio provisional)',
            'candidato': objetivo, 'listado_por_prioridad': tabla, 'vecinos': vecinos}


def _evidencias(grafo, fichas):
    """Consulta EV del PI4: el LLM ve qué evidencias tienen cifra y cuáles no."""
    if not fichas:
        return
    por = {}
    for fila in grafo.leer('S4-EV-evidencias', evaluaciones=[f['evaluacion'] for f in fichas]):
        e = dict(fila['evidencia'])
        e['tiene_valor'] = (e.get('valor') is not None or e.get('valor_min') is not None)
        por.setdefault(fila['evaluacion'], []).append(e)
    for f in fichas:
        f['evidencias'] = por.get(f['evaluacion'], [])


def _glosario(grafo, fichas):
    ids = set()
    for f in fichas:
        ids.update(r['regla'] for r in f.get('reglas_activadas') or [] if r.get('regla'))
        ids.update(f.get('marcas') or [])
        if f.get('regla_dominante'):
            ids.add(f['regla_dominante'])
    if not ids:
        return {}
    return {fila['id']: fila['propiedades']
            for fila in grafo.leer('S4-G-glosario', ids=sorted(ids))}


def responder(grafo, texto, extraido=None):
    if extraido is None:
        r = extraer(texto)
        if r.datos is None:
            return {'submodulo': 'S4', 'respuesta': 'No pude interpretar la consulta. ¿Podés reformularla?'}
        grafo.traza.agregar('extraccion', {'submodulo': 'S4', **r.como_dict()})
        extraido = r.datos

    if extraido.get('intencion') == 'fuera_de_dominio':
        return {'submodulo': 'S4', 'intencion': 'fuera_de_dominio',
                'respuesta': 'Tu consulta no parece referirse a la cobertura de vacantes internas. '
                             'Puedo explicarte el listado de candidatos de una vacante, por qué '
                             'alguien quedó en determinada posición o por qué fue descartado.'}

    puesto, aclaracion = resolver_puesto(grafo, extraido.get('puesto_id'),
                                         extraido.get('servicio'), extraido.get('turno'))
    if aclaracion:
        return {'submodulo': 'S4', 'respuesta': aclaracion, 'aclaracion': True}

    filtros = extraido.get('filtros') or {}
    legajo = extraido.get('legajo')
    if not legajo and extraido.get('empleado'):
        fila = grafo.una('S2-Q3-empleado', texto=normalizar(extraido['empleado']))
        fuertes = (fila or {}).get('fuertes') or []
        candidatos = (fila or {}).get('candidatos') or []
        if len(fuertes) == 1:
            legajo = fuertes[0]['legajo']
        elif len(candidatos) == 1:
            legajo = candidatos[0]['legajo']
        elif len(candidatos) > 1:
            return {'submodulo': 'S4', 'aclaracion': True,
                    'respuesta': '¿A cuál te referís? ' + ', '.join(
                        f"{c['nombre']} ({c['legajo']})" for c in candidatos)}
        else:
            return {'submodulo': 'S4', 'aclaracion': True,
                    'respuesta': f"«{extraido['empleado']}» no figura entre los empleados de la "
                                 'base de conocimiento, así que no hay una evaluación que explicar.'}

    # ---------------------------------------------------- regla A3: listado vacio
    fila_vacio = grafo.una('S4-5-listado-vacio', puesto=puesto['puesto'])
    if fila_vacio and not (fila_vacio.get('validos') or 0):
        return {'submodulo': 'S4', 'intencion': extraido.get('intencion'), 'regla': 'A3',
                'datos': fila_vacio, 'respuesta': mensaje_listado_vacio(grafo, puesto['puesto']),
                'fidelidad': 'sin LLM (A3)'}

    fichas = [f['ficha'] for f in grafo.leer(
        'S4-E-fichas', puesto=puesto['puesto'], legajo=legajo,
        categoria=filtros.get('categoria'),
        solo_con_advertencias=bool(filtros.get('solo_con_advertencias')))]

    tipo = 'listado'
    if legajo and not fichas:
        tipo = 'descarte'
        descartes = [d for d in grafo.leer('S4-1-descartes', puesto=puesto['puesto'])
                     if d['legajo'] == legajo]
        if not descartes:
            return {'submodulo': 'S4', 'aclaracion': True,
                    'respuesta': f'No hay una evaluación de {legajo} para {puesto["servicio"]}.'}
        for d in descartes:
            d['lectura'] = lectura(d, descartado=True)
        datos = {'puesto': puesto, 'descartes': descartes}
        exigencias = {'descartado': True, 'citas_obligatorias': True}
        if any(d.get('deseables_estado') == 'SIN_DATO' for d in descartes):
            exigencias['sin_dato'] = True
    else:
        if not fichas:
            return {'submodulo': 'S4', 'aclaracion': True,
                    'respuesta': 'No hay candidatos que cumplan ese filtro en esta vacante.'}
        _evidencias(grafo, fichas)
        for f in fichas:
            f['lectura'] = lectura(f)
        if legajo:
            tipo = 'candidato'
            traza = grafo.una('S4-C-traza', evaluacion=fichas[0]['evaluacion'])
            otros = [f['ficha'] for f in grafo.leer(
                'S4-E-fichas', puesto=puesto['puesto'], legajo=None, categoria=None,
                solo_con_advertencias=False)]
            datos = {'fichas': fichas, 'traza_categoria': (traza or {}).get('traza'),
                     'otros_candidatos_del_listado': [o for o in otros if o['legajo'] != legajo],
                     'comparacion_orden': comparacion_orden(legajo, fichas + [
                         o for o in otros if o['legajo'] != legajo])}
        else:
            datos = {'fichas': fichas}
        exigencias = {
            'citas_obligatorias': True,
            'categorias': [f['categoria'] for f in fichas if f.get('categoria')],
            'legajos': [f['legajo'] for f in fichas],
            'orden_provisional': any(f.get('criterio_orden') == 'PROVISIONAL' for f in fichas),
            'sin_ganador': any(f.get('estado_orden_con_siguiente') in ('empate tecnico', 'no determinado')
                               for f in fichas),
            'incertidumbre': any((f.get('confiabilidad') or 1) < 1 or
                                 (f.get('afinidad') or [0, 0])[0] != (f.get('afinidad') or [0, 0])[1]
                                 for f in fichas),
            'sin_dato': any(f.get('deseables_estado') == 'SIN_DATO' or
                            f.get('advertencias_estado') == 'sin_dato' for f in fichas),
        }
        # Si la pregunta es por la posición, el texto tiene que comparar prioridades.
        if pregunta_por_orden(texto, extraido):
            if tipo == 'candidato' and datos.get('comparacion_orden'):
                c = datos['comparacion_orden']
                f0 = fichas[0]
                exigencias['comparar_orden'] = {
                    'legajos': [v['legajo'] for v in c['vecinos']],
                    'prioridades': {**{f0['legajo']: f0.get('prioridad')},
                                    **{v['legajo']: v['prioridad'] for v in c['vecinos']}}}
            elif tipo == 'listado' and len(fichas) > 1:
                exigencias['comparar_orden'] = {
                    'legajos': [], 'prioridades': {f['legajo']: f.get('prioridad') for f in fichas}}

    glosario = _glosario(grafo, fichas)
    mensaje = json.dumps({'pregunta': texto, 'tipo': tipo, 'datos_neo4j': datos,
                          'glosario_grafo': glosario}, ensure_ascii=False, default=str)

    evaluaciones = {}
    for f in fichas:
        evaluaciones.setdefault(f['evaluacion'], [])

    def validador(d):
        if isinstance(d, dict):
            d['texto'] = normalizar_texto(d.get('texto'))
        citas = d.get('citas') or []
        porev = {}
        for c in citas if isinstance(citas, list) else []:
            if isinstance(c, dict) and c.get('evaluacion') and c.get('evidencia'):
                porev.setdefault(c['evaluacion'], []).append(
                    {'evidencia': c['evidencia'], 'valor': c.get('valor')})
        return (validar_explicacion(d, datos, exigencias, grafo=grafo if porev else None,
                                    evaluaciones=porev) +
                validar_s4(d, datos, exigencias))

    try:
        sistema = prompts.cargar('s4_explicacion')
    except PromptFaltante:
        return {'submodulo': 'S4', 'tipo': tipo, 'datos': datos,
                'respuesta': respaldo(datos, tipo), 'fidelidad': 'respaldo (falta el prompt de S4)'}
    try:
        # Un listado con varios candidatos necesita más salida que la explicación de uno
        # solo: con el tope de un candidato el JSON llegaba cortado y S4 caía al respaldo.
        tope = (config.MAX_TOKENS_LISTADO if tipo == 'listado' and len(fichas) > 1
                else config.MAX_TOKENS_EXPLICACION)
        r = pedir_json(sistema, mensaje, temperatura=config.TEMP_EXPLICACION,
                       max_tokens=tope,
                       reintentos=config.MAX_INTENTOS - 1, validador=validador)
    except ErrorLLM as e:
        # Regla A6: el trabajo del grafo no se pierde porque el proveedor falle.
        return {'submodulo': 'S4', 'tipo': tipo, 'datos': datos,
                'respuesta': respaldo(datos, tipo),
                'fidelidad': f'respaldo (A6): el modelo no respondió — {str(e)[:120]}'}
    grafo.traza.agregar('explicacion', {'submodulo': 'S4', 'tipo': tipo,
                                        'fidelidad': 'OK' if (r.datos and r.datos.get('texto')) else 'respaldo',
                                        **r.como_dict()})
    if r.datos and r.datos.get('texto'):
        return {'submodulo': 'S4', 'tipo': tipo, 'datos': datos, 'respuesta': r.datos['texto'],
                'citas': r.datos.get('citas') or [], 'fidelidad': 'OK'}
    return {'submodulo': 'S4', 'tipo': tipo, 'datos': datos,
            'respuesta': respaldo(datos, tipo), 'fidelidad': 'respaldo (A6)',
            'motivos_respaldo': r.motivos}


def respaldo(datos, tipo):
    """Regla A6: categoria y evidencia estructurada, sin redaccion del LLM."""
    if tipo == 'descarte':
        d = datos['descartes'][0]
        return (f"{d['empleado']} ({d['legajo']}) fue descartado. Motivos registrados: " +
                '; '.join(legible(m) for m in (d.get('motivos_descarte') or [])) +
                f". Categoría registrada: {legible(d.get('categoria'))} (regla {d.get('regla_corte')}). "
                'No se logró una explicación verificada, así que se entregan los datos del grafo.')
    fichas = datos.get('fichas', [])
    if not fichas:
        return 'No hay datos que explicar para esta consulta.'

    cab = fichas[0]
    lineas = [f"Candidatos para {cab.get('servicio')} ({cab.get('puesto')}), "
              f"urgencia {cab.get('urgencia')}:", '']
    for f in fichas:
        lineas.append(f"{f.get('posicion_por_prioridad')}. {f.get('empleado')} "
                      f"({f.get('legajo')}) — {legible(f.get('categoria'))}")
        lineas.append(f"   prioridad {_num(f.get('prioridad'))} · {afinidad_texto(f)}")
        detalles = []
        if f.get('deseables_faltantes'):
            detalles.append('le falta la aptitud deseable ' + _lista(f['deseables_faltantes']))
        if f.get('deseables_vencidos'):
            detalles.append('tiene vencida la aptitud deseable ' + _lista(f['deseables_vencidos']))
        if not f.get('deseables_faltantes') and f.get('deseables_estado') == 'SIN_DATO':
            detalles.append('las aptitudes deseables no se evaluaron')
        if f.get('advertencias'):
            detalles.append('advertencias: ' + _lista(f['advertencias']))
        if f.get('estado_orden_con_siguiente') in ('empate tecnico', 'no determinado'):
            detalles.append(f"orden con el siguiente: {f['estado_orden_con_siguiente'].replace('tecnico', 'técnico')}, "
                            'no hay un ganador')
        if detalles:
            lineas.append('   ' + '; '.join(detalles))
        lineas.append('')
    lineas.append('El criterio de orden es provisional y todavía no fue validado por RR. HH. '
                  'La decisión final es del reclutador.')
    return '\n'.join(lineas)
