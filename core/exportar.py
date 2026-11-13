"""Exportación de la base de conocimiento (ítem i del ZIP del PG3).

Aura Free no siempre permite descargar el dump, así que el grafo se exporta desde
Python con dos consultas de solo lectura del catálogo (PG3-export-nodos y
PG3-export-relaciones). Se generan dos archivos en neo4j/:

  Grupo_5_PG3_export.cypher  script que reconstruye el grafo en una base VACÍA:
                             python -m api.main --cargar neo4j/Grupo_5_PG3_export.cypher
  Grupo_5_PG3_export.json    los mismos nodos y relaciones, para revisar o graficar

Las restricciones e índices no se exportan: si se quieren, correr antes el bloque 1
de Grupo_5_PG2_U1_carga.cypher.
"""
import json
from datetime import datetime

from core import config

AUX = '_ExportPG3'      # etiqueta y propiedad temporales para unir las relaciones


def _cadena(s):
    return "'" + str(s).replace('\\', '\\\\').replace("'", "\\'") + "'"


def _literal(v):
    """Valor de Python (o tipo temporal del driver) como literal Cypher."""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(_literal(x) for x in v) + ']'
    nombre = type(v).__name__
    if nombre == 'Date':
        return f"date('{v.iso_format()}')"
    if nombre == 'DateTime':
        return f"datetime('{v.iso_format()}')"
    if nombre == 'LocalDateTime':
        return f"localdatetime('{v.iso_format()}')"
    if nombre in ('Time', 'LocalTime'):
        return f"{'time' if nombre == 'Time' else 'localtime'}('{v.iso_format()}')"
    if nombre == 'Duration':
        return f"duration('{v.iso_format()}')"
    return _cadena(v)


def _mapa(props):
    if not props:
        return ''
    partes = []
    for k, v in props.items():
        clave = k if k.replace('_', '').isalnum() and not k[0].isdigit() else f'`{k}`'
        partes.append(f'{clave}: {_literal(v)}')
    return '{' + ', '.join(partes) + '}'


def _etiquetas(lista):
    return ''.join(f':`{e}`' for e in lista)


def _json(v):
    if hasattr(v, 'iso_format'):
        return v.iso_format()
    raise TypeError(type(v).__name__)


def exportar(grafo, carpeta=None):
    carpeta = carpeta or (config.RAIZ / 'neo4j')
    nodos = grafo.leer('PG3-export-nodos')
    rels = grafo.leer('PG3-export-relaciones')
    ids = {n['id']: i for i, n in enumerate(nodos)}

    fecha = datetime.now().strftime('%d/%m/%Y %H:%M')
    lineas = [
        '// Grupo 5 – 5K10 · PG3 · Exportación de la base de conocimiento',
        f'// Generado el {fecha} con: python -m api.main --exportar',
        f'// {len(nodos)} nodos y {len(rels)} relaciones. Cargar en una base vacía:',
        '//   python -m api.main --cargar neo4j/Grupo_5_PG3_export.cypher',
        '',
        f'CREATE INDEX export_pg3 IF NOT EXISTS FOR (n:{AUX}) ON (n.{AUX});',
        '',
        '// ---------------------------------------------------------------- nodos',
    ]
    for n in nodos:
        props = dict(n['props'] or {})
        props[AUX] = ids[n['id']]
        lineas.append(f"CREATE (n{_etiquetas(n['etiquetas'] + [AUX])} {_mapa(props)});")

    lineas += ['', '// ---------------------------------------------------------------- relaciones']
    for r in rels:
        props = _mapa(r['props'])
        lineas.append(
            f"MATCH (a:{AUX} {{{AUX}: {ids[r['desde']]}}}), (b:{AUX} {{{AUX}: {ids[r['hasta']]}}}) "
            f"CREATE (a)-[:`{r['tipo']}`{(' ' + props) if props else ''}]->(b);")

    lineas += ['', '// ---------------------------------------------------------------- limpieza',
               f'MATCH (n:{AUX}) REMOVE n:{AUX}, n.{AUX};',
               'DROP INDEX export_pg3 IF EXISTS;', '']

    ruta_cypher = carpeta / 'Grupo_5_PG3_export.cypher'
    ruta_cypher.write_text('\n'.join(lineas), encoding='utf-8')

    ruta_json = carpeta / 'Grupo_5_PG3_export.json'
    ruta_json.write_text(json.dumps({
        'generado': fecha,
        'nodos': [{'id': ids[n['id']], 'etiquetas': n['etiquetas'], 'propiedades': n['props']}
                  for n in nodos],
        'relaciones': [{'desde': ids[r['desde']], 'hasta': ids[r['hasta']], 'tipo': r['tipo'],
                        'propiedades': r['props']} for r in rels],
    }, ensure_ascii=False, indent=1, default=_json), encoding='utf-8')

    conteo = {}
    for n in nodos:
        for e in n['etiquetas']:
            conteo[e] = conteo.get(e, 0) + 1
    return {'nodos': len(nodos), 'relaciones': len(rels), 'por_etiqueta': conteo,
            'cypher': ruta_cypher, 'json': ruta_json}
