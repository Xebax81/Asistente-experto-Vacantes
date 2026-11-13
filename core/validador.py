"""Validacion de fidelidad comun a los cuatro submodulos.

En los PI4 cada submodulo tenia su propio validador, con controles muy parecidos.
Aca estan una sola vez, parametrizados por submodulo. Los controles son los que
los cuatro informes describen, mas las tres mejoras que el PI4 de S4 dejo
propuestas en su seccion i (marcadas con MEJORA).

La validacion es determinista y corre en Python: no depende de que el LLM "se
acuerde" de una regla. Si falla, se reintenta indicando los motivos; si vuelve a
fallar se entrega un texto de respaldo armado solo con la ficha (regla A6).
"""
import re
import unicodedata

NUMERO = re.compile(r'-?\d+(?:[.,]\d+)?')

FRASES_PROHIBIDAS = (
    'el mejor candidato', 'la mejor candidata', 'es el mejor', 'es la mejor',
    'contrate', 'contratá', 'contrata a', 'asigne a', 'asigná a',
)
FRASES_AUSENCIA = (
    'no se encontraron', 'no le falta', 'sin advertencias', 'no tiene advertencias',
    'no hay advertencias', 'no faltan',
)


def _sin_tildes(t):
    t = unicodedata.normalize('NFD', (t or '').lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def _numeros(texto):
    return {n.replace(',', '.') for n in NUMERO.findall(texto or '')}


def _valores_numericos(obj, acum=None):
    """Todos los numeros que aparecen en la ficha, en varias formas de redondeo."""
    acum = acum if acum is not None else set()
    if isinstance(obj, dict):
        for v in obj.values():
            _valores_numericos(v, acum)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _valores_numericos(v, acum)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        acum.add(f'{obj:g}')
        for d in (1, 2, 3):
            acum.add(f'{round(float(obj), d):g}')
        acum.add(f'{round(float(obj) * 100):g}')  # porcentajes
    elif isinstance(obj, str):
        acum |= _numeros(obj)
        # Fechas ISO del grafo (2026-08-12): el texto puede escribirlas 12/08/2026.
        acum |= {f'{int(x):g}' for x in re.findall(r'\d+', obj)}
    return acum


def _textos(obj, acum=None):
    acum = acum if acum is not None else set()
    if isinstance(obj, dict):
        for v in obj.values():
            _textos(v, acum)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _textos(v, acum)
    elif isinstance(obj, str):
        acum.add(_sin_tildes(obj))
    return acum


def validar_explicacion(datos, ficha, exigencias=None, grafo=None, evaluaciones=None):
    """Devuelve la lista de motivos de rechazo (vacia si la explicacion es fiel).

    datos      : JSON devuelto por el LLM; debe tener "texto" y las citas.
    ficha      : el resultado estructurado que se le paso (unica fuente de verdad).
    exigencias : dict con menciones obligatorias, p. ej.
                 {'orden_provisional': True, 'incertidumbre': True, 'sin_ganador': True,
                  'categorias': ['Recomendado_con_reservas'], 'legajos': ['E101','E104'],
                  'sin_dato': True, 'hipotetico': True}
    grafo      : si se pasa, se ejecuta la consulta F contra Neo4j (regla A2).
    """
    exigencias = exigencias or {}
    motivos = []

    if not isinstance(datos, dict):
        return ['La respuesta no es un objeto JSON.']
    texto = datos.get('texto')
    if not isinstance(texto, str) or not texto.strip():
        return ['Falta el campo "texto" con la explicación.']
    plano = _sin_tildes(texto)

    # ---------------------------------------------------- 1. cifras sin respaldo
    permitidos = _valores_numericos(ficha)
    # Numeros de identificadores (pv_001, E104, S4-FZ3, S1-R07) no cuentan como cifras.
    limpio = re.sub(r'\bpv_\w+', ' ', texto)   # ids de puesto del PG3: pv_20261112160723_1
    limpio = re.sub(r'\b[A-Za-zÁ-úñÑ]+[_\-]?\d+\b', ' ', limpio)
    limpio = re.sub(r'\bS\d-[A-Z]+\d*\b', ' ', limpio)
    for n in _numeros(limpio):
        try:
            v = float(n)
        except ValueError:
            continue
        if f'{v:g}' in permitidos:
            continue
        if any(abs(v - float(p)) < 0.005 for p in permitidos
               if _es_num(p)):
            continue
        motivos.append(f'La explicación menciona la cifra {n}, que no está en los datos recuperados.')

    # ---------------------------------------------------- 2. nombres y categorias
    for cat in exigencias.get('categorias') or []:
        if _sin_tildes(cat.replace('_', ' ')) not in plano and _sin_tildes(cat) not in plano:
            motivos.append(f'No nombra la categoría registrada "{cat}" (regla A1).')
    for legajo in exigencias.get('legajos') or []:
        if _sin_tildes(legajo) not in plano:
            motivos.append(f'No nombra al candidato {legajo}, que está en el resultado.')

    # ---------------------------------------------------- 3. menciones obligatorias
    if exigencias.get('incertidumbre') and not any(
            p in plano for p in ('intervalo', 'rango', 'confiabilidad', 'imprecis', 'entre ')):
        motivos.append('La afinidad es imprecisa (intervalo o confiabilidad menor que 1) '
                       'y el texto no lo menciona.')
    if exigencias.get('orden_provisional') and 'provisional' not in plano:
        motivos.append('El criterio de orden es PROVISIONAL y el texto no lo aclara.')
    if exigencias.get('sin_ganador') and not any(
            p in plano for p in ('no hay un ganador', 'empate', 'no determinado', 'no se puede')):
        motivos.append('Hay un empate técnico u orden no determinado y el texto no dice '
                       'que no hay un ganador.')
    if exigencias.get('sin_dato') and not any(
            p in plano for p in ('no hay dato', 'no se evaluo', 'no se evaluaron', 'sin dato',
                                 'desconocido', 'no se conoce')):
        motivos.append('Hay datos en estado SIN_DATO o DESCONOCIDO y el texto no lo dice.')
    if exigencias.get('hipotetico'):
        if 'simulacion' not in plano and 'hipotet' not in plano:
            motivos.append('Es una simulación hipotética y el texto no lo aclara.')
        if 'categoria no cambia' not in plano and 'no cambia la categoria' not in plano:
            motivos.append('En una simulación hay que aclarar que la categoría no cambia.')
    if exigencias.get('descartado') and 'descartad' not in plano:
        motivos.append('El candidato está descartado y el texto no lo dice.')

    # MEJORA (i.1 del PI4 de S4): si un estado es SIN_DATO, no se puede afirmar ausencia.
    if exigencias.get('sin_dato'):
        for frase in FRASES_AUSENCIA:
            if frase in plano:
                motivos.append(f'Dice «{frase}» cuando el dato figura como no evaluado (regla A5).')
                break

    # MEJORA (i.1 del PI4 de S4): no repetir la seccion de citas ni los IDs dentro del texto.
    if 'citas:' in plano or 'ev_' in plano:
        motivos.append('El texto incluye la sección de citas o identificadores de evidencia; '
                       'eso va en el campo de citas, no en la explicación.')

    # ---------------------------------------------------- 4. frases prohibidas
    for frase in FRASES_PROHIBIDAS:
        # Palabra completa: «contratá» no tiene que disparar con «contratación» (la
        # frase «la decisión sobre la contratación es del reclutador» es correcta).
        if re.search(r'\b' + re.escape(_sin_tildes(frase)) + r'\b', plano):
            motivos.append(f'Usa la frase «{frase}»: el sistema no elige ni recomienda a una persona.')
            break
    if exigencias.get('sin_juicio_personas') and any(
            p in plano for p in (' es apta', ' es apto', 'son aptos', 'son aptas')):
        motivos.append('Este submódulo no evalúa personas y el texto dice que alguien es apto.')

    # ---------------------------------------------------- 5. citas (regla A2)
    citas = datos.get('citas') or datos.get('datos_citados') or datos.get('valores_citados') or []
    if exigencias.get('citas_obligatorias') and not citas:
        motivos.append('Falta al menos una cita que respalde la explicación.')

    textos_ficha = _textos(ficha)
    for cita in citas if isinstance(citas, list) else []:
        if not isinstance(cita, dict):
            continue
        valor = cita.get('valor')
        campo = cita.get('campo') or cita.get('evidencia') or ''
        if valor is None:
            continue
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if f'{valor:g}' not in permitidos and not any(
                    _es_num(p) and abs(float(valor) - float(p)) < 0.005 for p in permitidos):
                motivos.append(f'La cita {campo} declara el valor {valor}, que no figura en los datos.')
        elif isinstance(valor, str) and _sin_tildes(valor) not in textos_ficha:
            motivos.append(f'La cita {campo} declara «{valor}», que no figura en los datos.')

    # Consulta F contra Neo4j: la evidencia citada pertenece al candidato y el valor coincide.
    if grafo is not None and evaluaciones:
        for evaluacion, citadas in evaluaciones.items():
            if not citadas:
                continue
            for fila in grafo.leer('S4-F-fidelidad', evaluacion=evaluacion, citadas=citadas):
                if not fila['pertenece_al_candidato']:
                    motivos.append(f"La evidencia {fila['evidencia_citada']} no pertenece a "
                                   f'la evaluación {evaluacion}.')
                elif fila['valor_coincide'] is False:
                    motivos.append(f"El valor citado para {fila['evidencia_citada']} no coincide "
                                   'con el del grafo.')

    return motivos


def _es_num(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


# ====================================================================
# Controles específicos de S1 (devolución de la cátedra al PI4)
# ====================================================================
# La cátedra señaló dos confusiones en las explicaciones del PI4 de S1:
#   URGENCIA: se presentaba una pertenencia o una activación como si fuera el nivel
#             de urgencia («urgencia media con un grado de 1,0» cuando el índice
#             era 0,496). Ocurrió en C1, C2, C4 y C5.
#   ZONA:     se mezclaban estados distintos («no se reconoció ni se informó»).
# El prompt ya lo pide; acá se verifica, que es lo que evita que vuelva a pasar.

CONFLACION_ZONA = (
    'no se reconocio ni se informo', 'no se informo ni se reconocio',
    'no se reconocio o no se informo', 'no se informo o no se reconocio',
)


def _numeros_de(mapa):
    salida = set()
    for v in (mapa or {}).values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            for d in (1, 2, 3):
                salida.add(f'{round(float(v), d):g}')
    return salida


def validar_urgencia_s1(texto, ficha):
    """La categoría va con el índice; pertenencias y activaciones van nombradas."""
    motivos = []
    u = (ficha or {}).get('urgencia') or {}
    categoria = u.get('categoria')
    plano = _sin_tildes(texto)

    if not categoria:
        if any(p in plano for p in ('urgencia alta', 'urgencia media', 'urgencia baja')):
            motivos.append('La urgencia no se pudo determinar y el texto le asigna una categoría.')
        return motivos

    if _sin_tildes(categoria) not in plano:
        return motivos  # no habla de la urgencia: no hay nada que controlar

    indice = u.get('indice')
    nums = _numeros(texto)
    if indice is not None:
        formas = {f'{round(float(indice), d):g}' for d in (1, 2, 3)}
        if not (formas & nums):
            motivos.append(
                f'Menciona la urgencia {categoria} pero no cita el índice de urgencia '
                f'({indice}). La categoría se informa junto con su índice, no sola.')

    pertenencias = _numeros_de(u.get('pertenencia'))
    activaciones = _numeros_de({r['regla']: r.get('activacion')
                                for r in u.get('reglas_activadas') or []})
    formas_indice = ({f'{round(float(indice), d):g}' for d in (1, 2, 3)}
                     if indice is not None else set())
    ajenos = (pertenencias | activaciones) - formas_indice
    nombrados = 'pertenencia' in plano or 'activacion' in plano or 'activada' in plano
    if (ajenos & nums) and not nombrados:
        cita = sorted(ajenos & nums)[0]
        motivos.append(
            f'Cita el número {cita}, que es un valor de pertenencia o la activación de una '
            'regla, sin decir que lo es. Un valor de pertenencia o una activación no son el '
            'nivel de urgencia: nombralos con las palabras «pertenencia» o «activación».')
    return motivos


def validar_zona_s1(texto, ficha):
    """Cada vacante tiene UN estado de zona y el texto tiene que usar el suyo."""
    motivos = []
    plano = _sin_tildes(texto)

    for frase in CONFLACION_ZONA:
        if frase in plano:
            motivos.append('Mezcla dos estados distintos de la zona («no se reconoció ni se '
                           'informó»): solo uno es el verdadero, decí cuál.')
            break

    for v in (ficha or {}).get('vacantes', []):
        z = v.get('zona') or {}
        estado = z.get('resolucion')

        if estado == 'heredada':
            if z.get('nombre') and _sin_tildes(z['nombre']) in plano and not any(
                    p in plano for p in ('del servicio', 'de la sede', 'segun el servicio')):
                motivos.append(f"La zona {z['nombre']} se tomó del servicio (S1-R07) y el texto "
                               'no lo aclara.')
        elif estado == 'no_reconocida':
            informado = z.get('texto_informado')
            if informado and _sin_tildes(informado) not in plano:
                motivos.append(f'El pedido indicó la zona «{informado}», que no está en el '
                               'catálogo. El texto tiene que decir cuál fue esa zona y preguntar, '
                               'sin reemplazarla por la del servicio.')
        elif estado == 'sin_dato':
            if 'no se reconocio' in plano and 'no se informo' not in plano:
                motivos.append('El pedido no informó ninguna zona: decir que «no se reconoció» '
                               'es incorrecto, no había nada que reconocer.')
    return motivos


# ====================================================================
# Controles específicos de S2 (devolución de la cátedra al PI4 de Cayo)
# ====================================================================
# La cátedra pidió reforzar el control de las explicaciones de S2 para que:
#   VENCIDA:  una certificación vencida no se confunda con una aptitud inexistente
#             (en el PI4, C1 decía «le falta el deseable vencido» de Diego Ruiz);
#   RANKING:  un descartado no termine considerado en el ranking por una redacción
#             ambigua (C2 decía «en la siguiente fase S3 se usará el margen ... aunque
#             el empleado ya está descartado»; C1 llamaba «candidatos» a los descartados).
# La ficha ya trae un tipo y una frase fija por motivo; acá se verifica el texto.

PALABRAS_FALTA = ('falta', 'faltante', 'no tiene', 'no posee', 'no cuenta con', 'carece',
                  'sin la aptitud', 'inexistente', 'no la tiene')
PALABRAS_RANKING = ('afinidad', 's3', 'ranking', 'orden de candidatos', 'prioridad',
                    'listado final', 'recomendad', 'siguiente fase', 'proxima fase')
NEGACION_PASO = ('no pasa', 'no participa', 'no entra', 'no se calcula', 'no se le calcula',
                 'queda fuera', 'quedan fuera', 'no avanza', 'no sigue', 'no continua',
                 'no se considera', 'no forma parte')
SUJETO_VALIDOS = ('los validos', 'las validas', 'personas validas', 'candidatos validos',
                  'quienes pueden cubrir', 'los que pueden cubrir', 'quienes cumplen',
                  'los que cumplen')
TECNICOS_S2 = ('SIN_DATO', 'DESCONOCIDO', 'OBSERVADO', 'ESTIMADO', 'n_validos', 'n_descartados',
               'estado_S2', 'por_vencer', 'entrega_a_S3', 'derivacion', 'deseables_estado',
               'motivo_critico')
MEZCLA_FALTA_VENCIDA = re.compile(
    r'\b(falta\w*|no tiene|no posee|carece\w*)\b[^.;:]{0,40}\bvenc')
DESCARTADOS_COMO_CANDIDATOS = re.compile(
    r'descartad\w*\s+(?:\w+\s+){0,2}candidat|candidat\w*\s+(?:\w+\s+){0,2}descartad')


def _registros_s2(ficha):
    ev = (ficha or {}).get('evaluacion') or {}
    regs = list(ev.get('validos') or []) + list(ev.get('descartados') or [])
    if (ficha or {}).get('empleado'):
        regs.append(ficha['empleado'])
    return {r['legajo']: r for r in regs if r.get('legajo')}


def _segmentos(plano, legajos):
    """Para cada legajo, el texto que va desde su mención hasta la mención de otra persona."""
    pos = sorted((m.start(), l) for l in legajos
                 for m in re.finditer(r'\b' + re.escape(_sin_tildes(l)) + r'\b', plano))
    segs = {}
    for i, (ini, l) in enumerate(pos):
        fin = next((p for p, otro in pos[i + 1:] if otro != l), len(plano))
        segs.setdefault(l, []).append(plano[ini:fin])
    return {l: ' '.join(v) for l, v in segs.items()}


def _oraciones(t):
    return [o for o in re.split(r'(?<=[.;!?])\s+', t) if o.strip()]


def _menciones(seg, aptitud):
    formas = {_sin_tildes(aptitud), _sin_tildes(aptitud.replace('_', ' '))}
    pos = {m.start() for f in formas for m in re.finditer(re.escape(f), seg)}
    # También en prosa: «manejo de residuos patogénicos» por manejo_residuos_patogenicos.
    pos |= set(_mencion_aptitud(seg, aptitud))
    return sorted(pos)


def validar_s2(texto, ficha):
    """Devuelve los motivos de rechazo propios de S2 (lista vacía si el texto es fiel)."""
    motivos = []
    if not isinstance(texto, str) or not texto.strip():
        return motivos
    plano = _sin_tildes(texto)

    # ------------------------------------------------ valores técnicos en el texto
    for tok in TECNICOS_S2:
        if re.search(r'\b' + re.escape(tok) + r'\b', texto):
            motivos.append(f'El texto usa el valor técnico «{tok}»: decilo con palabras.')
            break

    # ------------------------------------------------ VENCIDA no es INEXISTENTE
    if MEZCLA_FALTA_VENCIDA.search(plano):
        motivos.append('Mezcla «falta» con «vencida»: una aptitud vencida la persona la tiene, '
                       'pero vencida; una faltante no la tiene. Usá la frase del motivo.')

    regs = _registros_s2(ficha)
    segs = _segmentos(plano, regs)
    for legajo, seg in segs.items():
        r = regs[legajo]
        vencidas = {m['aptitud'] for m in r.get('motivos') or []
                    if m.get('tipo') == 'CERTIFICACION_VENCIDA'}
        vencidas |= {d['aptitud'] for d in r.get('deseables_vencidos') or []}
        inexistentes = {m['aptitud'] for m in r.get('motivos') or []
                        if m.get('tipo') == 'APTITUD_INEXISTENTE'}
        inexistentes |= set(r.get('deseables_faltantes') or [])

        for a in vencidas:
            for i in _menciones(seg, a):
                antes = seg[max(0, i - 45):i]
                cerca = seg[max(0, i - 80):i + len(a) + 80]
                if any(p in antes for p in PALABRAS_FALTA):
                    motivos.append(f'{legajo}: presenta {a} como faltante, pero la tiene vencida.')
                    break
                if 'venc' not in cerca:
                    motivos.append(f'{legajo}: nombra {a} sin decir que está vencida.')
                    break
        if r.get('estado_S2') == 'descartado' and any(
                m.get('tipo') == 'CERTIFICACION_VENCIDA' for m in r.get('motivos') or []) \
                and 'venc' not in seg:
            motivos.append(f'{legajo} quedó descartado por certificación vencida (S2-R03) y el '
                           'texto no dice que está vencida.')
        if not vencidas:
            for a in inexistentes:
                for i in _menciones(seg, a):
                    if 'venc' in seg[max(0, i - 40):i + len(a) + 40]:
                        motivos.append(f'{legajo}: presenta {a} como vencida, pero no la tiene '
                                       'registrada (S2-R02).')
                        break

        # -------------------------------------------- DESCARTADO fuera del ranking
        if r.get('estado_S2') == 'descartado':
            for o in _oraciones(seg):
                if any(p in o for p in PALABRAS_RANKING) and \
                        not any(n in o for n in NEGACION_PASO) and \
                        not any(v in o for v in SUJETO_VALIDOS):
                    motivos.append(f'{legajo} está descartado y el texto lo relaciona con la '
                                   'afinidad, S3 o el orden sin aclarar que no participa: '
                                   f'«{o.strip()[:90]}».')
                    break
            if 'deseable' in seg and 'no se evalu' not in seg:
                motivos.append(f'{legajo} está descartado: sus deseables no se evaluaron y no '
                               'hay que presentarlos como faltantes ni cumplidos.')

    # Una oración que manda a S3 no puede nombrar a un descartado sin negarlo.
    descartados = [l for l, r in regs.items() if r.get('estado_S2') == 'descartado']
    for o in _oraciones(plano):
        if any(p in o for p in PALABRAS_RANKING) and not any(n in o for n in NEGACION_PASO):
            nombrados = [l for l in descartados if re.search(r'\b' + _sin_tildes(l) + r'\b', o)]
            if nombrados:
                motivos.append(f'La oración que habla de S3, la afinidad o el orden incluye a '
                               f'{", ".join(nombrados)}, que quedó descartado.')
                break

    if DESCARTADOS_COMO_CANDIDATOS.search(plano):
        motivos.append('Llama «candidatos» a los descartados: decí «empleados» o «personas»; '
                       'candidatos son solo quienes pueden cubrir el puesto.')

    if ((ficha or {}).get('evaluacion') or {}).get('alcance') == 'empleados_consultados' and \
            any(p in plano for p in ('no hay candidatos validos', 'no hay ningun candidato',
                                     'no haber candidatos validos', 'sin candidatos validos')):
        motivos.append('Se evaluó solo a la persona consultada: no se puede decir que el puesto '
                       'no tiene candidatos válidos.')

    # Sin duplicados, en el orden en que aparecieron.
    return list(dict.fromkeys(motivos))


# ====================================================================
# Controles específicos de S4 (devolución de la cátedra al PI4 de León)
# ====================================================================
# «La mejora prioritaria es que la validación de fidelidad controle también el
# significado de las afirmaciones, no solamente la presencia de cifras y referencias.»
# Errores del PI4 que pasaron la validación (tabla g.2):
#   CP1: «Las advertencias sobre el manejo de residuos patógenos…» (es un deseable faltante).
#   CP2: «La evidencia Ev_adv_… con un valor de 0.601» (la advertencia no tiene valor; 0,601
#        es la afinidad) y la posición explicada sin comparar prioridades.
#   CP3: «No se encontraron deseados faltantes» con deseables_estado = SIN_DATO.

DECIMAL = re.compile(r'(?<![\d/])\d+[.,]\d+(?![\d/])')
# Códigos del grafo escritos tal cual: palabras unidas por guion bajo (SOLAPE_PARCIAL,
# Baja_prioridad, manejo_residuos_patogenicos) o siglas de estado en mayúsculas.
TECNICO = re.compile(r'\b[A-Za-zÁ-úñÑ]+(?:_[A-Za-zÁ-úñÑ0-9]+)+\b|\b(?:SIN_DATO|DESCONOCIDO|OBSERVADO|ESTIMADO)\b')
METRICAS = ('afinidad', 'prioridad', 'fuerza', 'confiabilidad', 'solape', 'indice', 'margen',
            'activacion', 'grado', 'pertenencia', 'urgencia')
AUSENCIA = re.compile(
    r'(no se (encontr|registr|detect|observ)\w*|no (le )?falta\w*|no tiene|no presenta|no posee|'
    r'\bsin\b|ningun\w*|ninguna|cumple (con )?(todas )?(las )?)'
    r'\s*(?:\w+\s+){0,3}?(deseabl\w*|desead\w*|advertenc\w*)')


def _fichas_s4(datos):
    regs = list((datos or {}).get('fichas') or []) + list((datos or {}).get('descartes') or [])
    return {r['legajo']: r for r in regs if r.get('legajo')}


def _valores_propios(f):
    """Cifras decimales que pertenecen a ESTE candidato (no al puesto)."""
    vals = []
    for k in ('prioridad', 'confiabilidad', 'solape_horario'):
        if isinstance(f.get(k), (int, float)) and not isinstance(f.get(k), bool):
            vals.append(float(f[k]))
    a = f.get('afinidad') or []
    nums = [float(x) for x in a if isinstance(x, (int, float))]
    vals += nums
    if len(nums) == 2:
        vals.append((nums[0] + nums[1]) / 2)
    for r in f.get('reglas_activadas') or []:
        if isinstance(r, dict) and isinstance(r.get('fuerza'), (int, float)):
            vals.append(float(r['fuerza']))
    for e in f.get('evidencias') or []:
        for k in ('valor', 'valor_min', 'valor_max'):
            if isinstance(e.get(k), (int, float)) and not isinstance(e.get(k), bool):
                vals.append(float(e[k]))
    return vals


def _coincide(texto_num, valor):
    t = texto_num.replace(',', '.')
    dec = len(t.split('.')[1]) if '.' in t else 0
    try:
        return round(float(valor), dec) == round(float(t), dec) or abs(float(valor) - float(t)) < 1e-9
    except ValueError:
        return False


def _mencion_aptitud(plano, nombre):
    """Posiciones donde se nombra una aptitud o advertencia, aunque esté escrita en prosa
    («manejo de residuos patógenos» por manejo_residuos_patogenicos)."""
    raices = [t[:6] for t in re.split(r'[_\s]+', _sin_tildes(nombre)) if len(t) >= 4]
    if not raices:
        return []
    pos = []
    for m in re.finditer(re.escape(raices[0]), plano):
        ventana = plano[m.start():m.start() + 80]
        if all(r in ventana for r in raices):
            pos.append(m.start())
    return pos


def _clausula_previa(plano, i, largo):
    """Lo que está antes de la posición i dentro de la MISMA cláusula (corta en . ; , :).
    «no tiene advertencias registradas, no tiene la aptitud deseable X» no presenta a X
    como advertencia; «las advertencias sobre el manejo de residuos» sí (CP1 del PI4)."""
    previo = plano[max(0, i - largo):i]
    corte = max(previo.rfind(c) for c in '.;,:')
    return previo[corte + 1:] if corte >= 0 else previo


def _nombrado(plano, ficha):
    return (re.search(r'\b' + re.escape(_sin_tildes(ficha['legajo'])) + r'\b', plano) or
            (ficha.get('empleado') and _sin_tildes(ficha['empleado']) in plano))


def validar_s4(datos_llm, datos, exigencias=None):
    """Motivos de rechazo propios de S4 (lista vacía si el texto es fiel)."""
    exigencias = exigencias or {}
    if not isinstance(datos_llm, dict) or not isinstance(datos_llm.get('texto'), str):
        return []
    texto = datos_llm['texto']
    plano = _sin_tildes(texto)
    fichas = _fichas_s4(datos)
    motivos = []

    # ---------------------------------------- 1. CP2: cifra atribuida a una evidencia sin valor
    evid = {}
    for f in fichas.values():
        for e in f.get('evidencias') or []:
            evid[e['id']] = (f['evaluacion'], e)
    citas = datos_llm.get('citas') or []
    for c in citas if isinstance(citas, list) else []:
        if not isinstance(c, dict) or c.get('evidencia') not in evid:
            continue
        evaluacion, e = evid[c['evidencia']]
        if c.get('evaluacion') and c['evaluacion'] != evaluacion:
            motivos.append(f"La evidencia {c['evidencia']} es de {evaluacion}, no de {c['evaluacion']}.")
        if c.get('valor') is not None and not e.get('tiene_valor', True):
            motivos.append(f"Le atribuye la cifra {c['valor']} a la evidencia {c['evidencia']} "
                           f"({e.get('tipo')}), que no tiene ningún valor numérico.")
    # En el texto: una oración que habla de una advertencia o un deseable y da una cifra
    # sin decir de qué métrica es.
    sin_valor = [x for f in fichas.values()
                 for x in (f.get('advertencias') or []) + (f.get('deseables_faltantes') or [])
                 + (f.get('deseables_vencidos') or [])]
    for o in _oraciones(plano):
        habla = (re.search(r'advertenc|deseabl|ev_adv|ev_deseable', o) or
                 any(_mencion_aptitud(o, x) for x in sin_valor))
        if not habla:
            continue
        for m in DECIMAL.finditer(o):
            if not any(k in o[max(0, m.start() - 45):m.start()] for k in METRICAS):
                motivos.append('Atribuye la cifra ' + m.group(0) + ' a una advertencia o a una aptitud '
                               'deseable, que no tienen valor numérico: «' + o.strip()[:90] +
                               '». Decí de qué métrica es la cifra.')
                break
        else:
            continue
        break

    # ---------------------------------------- 2. cifras de otro candidato
    propios = {l: _valores_propios(f) for l, f in fichas.items()}
    segs = _segmentos(plano, list(fichas))
    duenio_de = {}
    for l, seg in segs.items():
        for o in _oraciones(seg):
            duenio_de.setdefault(o, l)
    for o in _oraciones(plano):
        nombrados = {l for l, f in fichas.items() if _nombrado(o, f)}
        contexto = nombrados | ({duenio_de[o]} if o in duenio_de else set())
        if not contexto:
            continue
        for n in DECIMAL.findall(o):
            duenios = {l for l, vals in propios.items() if any(_coincide(n, v) for v in vals)}
            if duenios and not (duenios & contexto):
                otros = ', '.join(sorted(duenios))
                motivos.append(f'Menciona {n} al hablar de {", ".join(sorted(contexto))}, pero esa '
                               f'cifra es de {otros}.')
                break

    # ---------------------------------------- 3. CP3: SIN_DATO no es «no le falta nada»
    for l, f in fichas.items():
        sin_des = f.get('deseables_estado') == 'SIN_DATO' or f.get('estado_S2') == 'descartado'
        sin_adv = f.get('advertencias_estado') == 'sin_dato'
        if not (sin_des or sin_adv):
            continue
        zona = segs.get(l) or (plano if len(fichas) == 1 else '')
        for m in AUSENCIA.finditer(zona):
            frag = m.group(0)
            if any(p in frag for p in ('dato', 'evalu', 'informaci')):
                continue
            es_des = frag.endswith(('deseable', 'deseables')) or 'desead' in frag or 'deseabl' in frag
            if (es_des and sin_des) or ('advertenc' in frag and sin_adv):
                motivos.append(f'{l}: dice «{frag}», pero ese dato está sin evaluar (SIN_DATO): '
                               'no significa que no le falte nada; decí que no se evaluó.')
                break

    # ---------------------------------------- 4. CP1: deseable presentado como advertencia
    todas_adv = {a for f in fichas.values() for a in f.get('advertencias') or []}
    for l, f in fichas.items():
        for d in (f.get('deseables_faltantes') or []) + (f.get('deseables_vencidos') or []):
            if d in todas_adv:
                continue
            for i in _mencion_aptitud(plano, d):
                if 'advertenc' in _clausula_previa(plano, i, 60):
                    motivos.append(f'Presenta {d} como una advertencia, pero es una aptitud '
                                   f'deseable que le falta a {l}.')
                    break
        for a in f.get('advertencias') or []:
            for i in _mencion_aptitud(plano, a):
                if re.search(r'deseabl', _clausula_previa(plano, i, 40)):
                    motivos.append(f'Presenta la advertencia {a} como una aptitud deseable.')
                    break

    # ---------------------------------------- 5. CP2: explicar el orden comparando prioridades
    co = exigencias.get('comparar_orden')
    if co:
        for l in co.get('legajos') or []:
            f = fichas.get(l) or next((x for x in (datos.get('otros_candidatos_del_listado') or [])
                                       if x.get('legajo') == l), {'legajo': l})
            if not _nombrado(plano, f):
                motivos.append(f'La pregunta es por la posición y el texto no nombra a {l}, que '
                               'queda inmediatamente antes o después (comparacion_orden).')
        nums = DECIMAL.findall(plano)
        for l, p in (co.get('prioridades') or {}).items():
            if p is None:
                continue
            if not any(_coincide(n, p) for n in nums):
                motivos.append(f'Para explicar el orden hay que comparar prioridades: falta la '
                               f'prioridad de {l} ({p}).')

    # ---------------------------------------- 6. valores técnicos en el texto
    # Misma exigencia que en S2 (devolución del PI4 de S2): el reclutador no tiene por qué
    # leer SOLAPE_PARCIAL, Baja_prioridad o [0.4958, 0.4958]. El prompt recibe la "lectura"
    # con los nombres legibles; acá se controla que los haya usado.
    for m in TECNICO.finditer(texto):
        tok = m.group(0)
        if tok.lower().startswith(('pv_', 'ev_', 'ev-')):
            continue       # ids de puesto y de evidencia: se aceptan (los de evidencia los
                           # rechaza validar_explicacion por su cuenta)
        motivos.append(f'Usa el código técnico «{tok}»: escribilo con palabras, como viene en '
                       '"lectura" (por ejemplo «solape parcial de horario», «Baja prioridad»).')
        break
    if re.search(r'\[\s*\d+[.,]\d+\s*[,;]\s*\d+[.,]\d+\s*\]', texto):
        motivos.append('Escribe la afinidad como un par entre corchetes: decí «afinidad entre X e Y» '
                       'o, si los dos valores son iguales, «afinidad X».')
    # «con dato» como estado interno («el estado de advertencias es con dato»), no la
    # frase del glosario «afinidad baja con dato razonablemente preciso» (regla FZ5).
    if re.search(r'\b(es|estado[^.]{0,25}) con dato\b(?!\s+(razonablemente|preciso|impreciso))', plano):
        motivos.append('La frase «con dato» es un estado interno: decí qué se observó o no digas nada.')

    return list(dict.fromkeys(motivos))
