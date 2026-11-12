"""PG3 — Punto 1 de la consigna: revisión y depuración final de la base de conocimiento.

La integración dejó a la vista tres inconsistencias entre lo que los PI4 documentan
y lo que el PG2 realmente cargó en Neo4j. Este módulo las corrige, y cada corrección
es verificable: ninguna inventa conocimiento nuevo.

  1. PARÁMETROS DIFUSOS INCOMPLETOS
     El grafo no tiene los nodos Termino que unen cada Variable_Linguistica con sus
     Funcion_Pertenencia, así que los parámetros publicados en los PI3 no se podían
     recuperar desde la base. Se escriben tomándolos de core/motor_difuso.py, que es
     la implementación verificada contra las tablas de los PI3.

  2. CONOCIMIENTO DUPLICADO SIN CONTROL
     Los parámetros viven en el código y en el grafo. Mientras el motor siga usando
     los del código (decisión deliberada: son los verificados), hace falta garantizar
     que no se separen. `comparar_parametros()` los contrasta y el --check lo informa.

  3. ENTRADAS DE S3 EN EL LUGAR EQUIVOCADO
     La experiencia y el desempeño estaban como propiedades de cada
     EvaluacionEmpleadoPuesto, cargadas a mano por el PG2. Son atributos del EMPLEADO,
     no de una evaluación puntual: por eso un puesto nuevo no los heredaba y su
     afinidad salía como intervalo con confiabilidad baja. Se promueven al Empleado
     tomándolos de las evaluaciones existentes; no se inventa ningún valor.
"""
from core import motor_difuso as md

# --------------------------------------------------------------- 1. parámetros difusos
# Declarados tal como están en el motor. La forma 'gaussiana' con lado 'izq'/'der'
# es un hombro: vale 1 a partir del centro hacia ese lado.
PARAMETROS = [
    # (variable, submodulo, unidad, universo, [(termino, centro, sigma, lado, centro2, sigma2)])
    # lado 'izq'/'der' = hombro: vale 1 de ese lado del centro.
    # centro2/sigma2 != None = gaussiana de dos lados con meseta entre centro y centro2.
    ('plazo_cobertura', 'S1', 'horas', (0, 168), [
        ('inmediato', 12, 22, 'izq', None, None),
        ('corto', 62, 20, None, None, None),
        ('amplio', 112, 22, 'der', None, None)]),
    ('premura_expresada', 'S1', 'puntaje 1-10', (1, 10), [
        ('leve', 2, 1.3, 'izq', None, None),
        ('moderada', 5, 1.3, None, None, None),
        ('fuerte', 8, 1.3, 'der', None, None)]),
    ('urgencia_pedido', 'S1', 'grado 0-1', (0, 1), [
        ('baja', 0.10, 0.17, 'izq', None, None),
        ('media', 0.50, 0.17, None, None, None),
        ('alta', 0.90, 0.17, 'der', None, None)]),
    ('urgencia', 'S3', 'horas', (0, 168), [
        ('alta', 12, md.SU, 'izq', None, None),
        ('media', 60, md.SU, None, None, None),
        ('baja', 108, md.SU, 'der', None, None)]),
    # Nombre del PG2: desempeno_reciente (no "desempeno").
    ('desempeno_reciente', 'S3', 'puntaje 1-10', (1, 10), [
        ('bajo', 3.5, md.SD, 'izq', None, None),
        ('medio', 6.5, md.SD, None, None, None),
        ('alto', 9.5, md.SD, 'der', None, None)]),
    ('cercania', 'S3', 'minutos', (0, 90), [
        ('misma_zona', 0, 0, None, None, None),
        ('cercana', 35, 0, None, None, None),
        ('lejana', 90, 0, None, None, None)]),
    ('experiencia_equivalente', 'S3', 'meses', (0, 36), [
        ('baja', 0, 0, None, None, None),
        ('media', 12, 0, None, None, None),
        ('alta', 36, 0, None, None, None)]),
    # Penalizaciones del grupo V de S2 (S2-R10). Gaussianas de dos lados.
    ('margen_vigencia', 'S2', 'dias', (0, 180), [
        ('critico', 0, 6, None, 7, 6),
        ('por_vencer', 35, 12, None, None, None),
        ('holgado', 75, 12, None, 120, 12)]),
    ('solape_horario', 'S2', 'fraccion 0-1', (0, 1), [
        ('insuficiente', 0, 0.08, None, 0.3, 0.08),
        ('parcial', 0.6, 0.1, None, None, None),
        ('total', 0.85, 0.06, None, 1.0, 0.06)]),
    # Nombre del PG2: afinidad (no "afinidad_S4"). Es la ENTRADA de S4.
    ('afinidad', 'S4', 'grado 0-1', (0, 1), [
        ('baja', 0.00, 0.340, None, None, None),
        ('intermedia', 0.55, 0.127, None, None, None),
        ('alta', 1.00, 0.255, None, None, None)]),
    ('confiabilidad', 'S4', 'grado 0-1', (0, 1), [
        ('baja', 0.55, 0.127, 'izq', None, None),
        ('media', 0.80, 0.085, None, None, None),
        ('alta', 1.00, 0.085, None, None, None)]),
    ('prioridad_recomendacion', 'S4', 'grado 0-1', (0, 1), [
        ('Baja_prioridad', 0.15, 0.10, None, None, None),
        ('Recomendado_con_reservas', 0.50, 0.10, None, None, None),
        ('Recomendado', 0.85, 0.10, None, None, None)]),
]

# Variables que esta depuración creó con un nombre equivocado antes de alinearlos
# con los del PG2. Se borran para no dejar dos nombres del mismo concepto.
DUPLICADAS = ('afinidad_S4', 'desempeno')

# La cercanía y la experiencia de S3 son trapezoidales, no gaussianas: los cuatro
# vértices no entran en el esquema centro/sigma del grafo. Se marcan como pendientes
# en lugar de escribirlas mal.
TRAPEZOIDALES = {'cercania', 'experiencia_equivalente'}

VERSIONES = {'S1': 'S1-v0.1', 'S3': 'S3-v0.3', 'S4': 'S4-FZ-v1'}


def escribir_parametros(grafo, mostrar=print):
    """Vuelca al grafo los parámetros del motor verificado. Devuelve cuántos escribió."""
    escritos = 0
    for variable, submodulo, unidad, (umin, umax), terminos in PARAMETROS:
        if variable in TRAPEZOIDALES:
            mostrar(f'  {variable:26} ({submodulo}) trapezoidal: no se escribe '
                    '(el grafo guarda centro/sigma)')
            continue
        for termino, centro, sigma, lado, centro2, sigma2 in terminos:
            forma = 'gaussiana_doble' if centro2 is not None else 'gaussiana'
            grafo.escribir('W-PG3-funcion-pertenencia', variable=variable,
                           submodulo=submodulo, unidad=unidad, umin=umin, umax=umax,
                           termino=termino, forma=forma, centro=float(centro),
                           sigma=float(sigma), lado=lado,
                           centro2=None if centro2 is None else float(centro2),
                           sigma2=None if sigma2 is None else float(sigma2),
                           version=VERSIONES.get(submodulo, 'PG3'))
            escritos += 1
        mostrar(f'  {variable:26} ({submodulo}) {len(terminos)} términos')
    return escritos


def borrar_duplicadas(grafo, mostrar=print):
    """Elimina las variables que esta depuración creó con un nombre que el PG2 ya
    usaba con otro. Solo borra funciones marcadas como escritas por la depuración."""
    borradas = 0
    for variable in DUPLICADAS:
        filas = grafo.escribir('W-PG3-borrar-variable', variable=variable)
        if filas:
            mostrar(f'  borrada la variable duplicada «{variable}»')
            borradas += 1
    return borradas


def comparar_parametros(grafo):
    """Contrasta lo que hay en el grafo con lo que usa el motor.

    Devuelve (coinciden, informe). Es el control que evita que el conocimiento
    del grafo y el del código se separen sin que nadie se entere.
    """
    esperado = {}
    for variable, _, _, _, terminos in PARAMETROS:
        if variable in TRAPEZOIDALES:
            continue
        for termino, centro, sigma, _, _, _ in terminos:
            esperado[(variable, termino)] = (round(float(centro), 6), round(float(sigma), 6))

    hallado, informe, ok = {}, [], True
    for fila in grafo.leer('PG3-parametros-difusos'):
        for t in fila.get('terminos') or []:
            if t.get('termino') and t.get('centro') is not None:
                hallado[(fila['variable'], t['termino'])] = (
                    round(float(t['centro']), 6), round(float(t.get('sigma') or 0), 6))

    faltan = sorted(set(esperado) - set(hallado))
    sobran = sorted(set(hallado) - set(esperado))
    difieren = [k for k in set(esperado) & set(hallado) if esperado[k] != hallado[k]]

    if faltan:
        ok = False
        informe.append(f'XX {len(faltan)} funciones del motor no están en el grafo: '
                       + ', '.join(f'{v}/{t}' for v, t in faltan[:6])
                       + ('…' if len(faltan) > 6 else ''))
    if difieren:
        ok = False
        for v, t in sorted(difieren)[:6]:
            informe.append(f'XX {v}/{t}: grafo {hallado[(v, t)]} vs motor {esperado[(v, t)]}')
    if sobran:
        informe.append(f'.. {len(sobran)} funciones en el grafo que el motor no usa:')
        porvar = {}
        for v, term in sobran:
            porvar.setdefault(v, []).append(term)
        for v, terms in sorted(porvar.items()):
            valores = ', '.join(f'{term} (c={hallado[(v, term)][0]}, s={hallado[(v, term)][1]})'
                                for term in sorted(terms))
            informe.append(f'     {v}: {valores}')
        informe.append('     Si alguna es la misma variable con otro nombre, hay que unificar:')
        informe.append('     dos nombres para el mismo concepto es justo lo que el punto 1')
        informe.append('     de la consigna llama inconsistencia terminológica.')
    if ok and not sobran:
        informe.append(f'OK las {len(esperado)} funciones de pertenencia del grafo '
                       'coinciden con las del motor verificado')
    return ok, informe


# --------------------------------------------------------------- 3. entradas por empleado
def _consenso(valores):
    """Un solo valor a partir de lo que dicen las evaluaciones del PG2.

    Si todas coinciden, ese valor. Si difieren, el más frecuente, informando el
    conflicto: la experiencia y el desempeño no deberían cambiar según el puesto.
    """
    valores = [v for v in valores if v is not None]
    if not valores:
        return None, 'sin dato en ninguna evaluación'
    unicos = sorted(set(float(v) for v in valores))
    if len(unicos) == 1:
        return unicos[0], 'coherente en todas las evaluaciones'
    frecuencias = {u: sum(1 for v in valores if float(v) == u) for u in unicos}
    elegido = max(frecuencias, key=frecuencias.get)
    return elegido, f'valores distintos entre evaluaciones ({unicos}): se toma {elegido}'


def normalizar_empleados(grafo, persistir=False, mostrar=print):
    """Promueve experiencia y desempeño desde las evaluaciones al Empleado."""
    filas = grafo.leer('PG3-entradas-por-empleado')
    if not filas:
        mostrar('  No hay evaluaciones del PG2 de las cuales tomar los datos.')
        return 0

    promovidos, sin_dato = 0, []
    for f in filas:
        exp, nota_exp = _consenso(f.get('experiencias'))
        des, nota_des = _consenso(f.get('desempenos'))
        ya = (f.get('experiencia_ya_en_empleado'), f.get('desempeno_ya_en_empleado'))

        if exp is None and des is None:
            sin_dato.append(f"{f['legajo']} {f['nombre']}")
            mostrar(f"  .. {f['legajo']:6} {f['nombre'][:18]:19} sin datos observados "
                    f"(estados: exp {f.get('exp_estados')}, des {f.get('des_estados')})")
            continue

        marca = '->' if persistir else '  '
        previo = '' if ya == (None, None) else f'  (ya tenía {ya[0]}, {ya[1]})'
        mostrar(f"  {marca} {f['legajo']:6} {f['nombre'][:18]:19} "
                f"experiencia {str(exp):>6} meses · desempeño {str(des):>5}{previo}")
        if nota_exp.startswith('valores distintos'):
            mostrar(f"       experiencia: {nota_exp}")
        if nota_des.startswith('valores distintos'):
            mostrar(f"       desempeño: {nota_des}")

        if persistir:
            grafo.escribir('W-PG3-normalizar-empleado', legajo=f['legajo'],
                           experiencia=exp, desempeno=des)
        promovidos += 1

    if sin_dato:
        mostrar(f"\n  {len(sin_dato)} empleados sin datos observados en el PG2: "
                + ', '.join(sin_dato))
        mostrar('  Para ellos la afinidad va a seguir saliendo como intervalo, que es')
        mostrar('  el comportamiento correcto: el sistema dice que no sabe lo suficiente.')
    return promovidos
