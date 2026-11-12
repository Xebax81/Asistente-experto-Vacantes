"""Carga de un script .cypher en Neo4j (el grafo del PG2).

Por que existe: Aura no tiene el comando :source del Neo4j Browser de escritorio,
y pegar 74 KB de Cypher en el editor web es incomodo y no informa bien los errores.
Este modulo lee el archivo, lo parte en sentencias y las ejecuta una por una con el
driver que el proyecto ya usa, informando cual falla si algo sale mal.

AVISO sobre la Regla de Oro: este es el unico lugar del sistema que ejecuta Cypher
que no esta en el catalogo de core/consultas.py. Es una herramienta de instalacion
que corre el usuario a mano desde la linea de comandos; el asistente no la puede
invocar y el LLM no la alcanza por ningun camino.
"""
import re
import time

COMENTARIO_LINEA = re.compile(r'//[^\n]*')


def dividir_sentencias(texto):
    """Parte un script Cypher en sentencias, respetando cadenas y comentarios.

    No usa un simple split(';') porque un punto y coma dentro de una cadena
    ('a; b') o de un comentario partiria la sentencia al medio.
    """
    sentencias, actual = [], []
    comilla = None          # ' " o ` mientras estamos dentro de una cadena
    i, n = 0, len(texto)

    while i < n:
        c = texto[i]

        if comilla:
            actual.append(c)
            if c == '\\' and i + 1 < n:         # escape dentro de la cadena
                actual.append(texto[i + 1])
                i += 2
                continue
            if c == comilla:
                comilla = None
            i += 1
            continue

        # comentario de bloque /* ... */
        if c == '/' and texto.startswith('/*', i):
            fin = texto.find('*/', i + 2)
            i = n if fin == -1 else fin + 2
            continue

        # comentario de linea //
        if c == '/' and texto.startswith('//', i):
            fin = texto.find('\n', i)
            i = n if fin == -1 else fin
            continue

        if c in ('"', "'", '`'):
            comilla = c
            actual.append(c)
            i += 1
            continue

        if c == ';':
            sentencias.append(''.join(actual))
            actual = []
            i += 1
            continue

        actual.append(c)
        i += 1

    sentencias.append(''.join(actual))

    limpias = []
    for s in sentencias:
        # Se descartan las lineas de cypher-shell (:begin, :commit, :param)
        lineas = [l for l in s.splitlines() if not l.strip().startswith(':')]
        s = '\n'.join(lineas).strip()
        if s:
            limpias.append(s)
    return limpias


def cargar(grafo, ruta, mostrar=print, detenerse_en_error=True):
    """Ejecuta el script. Devuelve (ok, ejecutadas, errores)."""
    texto = ruta.read_text(encoding='utf-8')
    sentencias = dividir_sentencias(texto)
    mostrar(f'{ruta.name}: {len(sentencias)} sentencias, {len(texto) // 1024} KB')

    ejecutadas, errores = 0, []
    inicio = time.time()
    for i, s in enumerate(sentencias, 1):
        etiqueta = ' '.join(s.split())[:70]
        try:
            grafo.ejecutar_crudo(s)
            ejecutadas += 1
            if i % 25 == 0 or i == len(sentencias):
                mostrar(f'  {i}/{len(sentencias)} sentencias…')
        except Exception as e:
            errores.append((i, etiqueta, str(e)[:300]))
            mostrar(f'  XX sentencia {i}: {etiqueta}')
            mostrar(f'     {str(e)[:300]}')
            if detenerse_en_error:
                break

    mostrar(f'\n{ejecutadas}/{len(sentencias)} sentencias ejecutadas '
            f'en {time.time() - inicio:.1f} s')
    if errores:
        mostrar(f'{len(errores)} con error.')
    return not errores, ejecutadas, errores
