"""Diagnóstico de la conexión con Neo4j (Aura).

Prueba la misma instancia del .env con cuatro esquemas de conexión y anota el error real
de cada uno, para separar las causas posibles:
  neo4j+s   el que usa el sistema (con enrutamiento y TLS verificado)
  bolt+s    directo, SIN enrutamiento: si este anda y neo4j+s no, el problema es la tabla de rutas
  neo4j+ssc TLS sin verificar el certificado: si este anda, algo intercepta el TLS (antivirus)
  bolt+ssc  directo y sin verificar el certificado

Uso:  python -m pruebas.diagnostico_neo4j
Deja el detalle del driver en pruebas/diagnostico_neo4j.log
"""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402

LOG = Path(__file__).with_name('diagnostico_neo4j.log')


def main():
    from neo4j import GraphDatabase
    import neo4j
    manejador = logging.FileHandler(LOG, mode='w', encoding='utf-8')
    manejador.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    log = logging.getLogger('neo4j')
    log.setLevel(logging.DEBUG)
    log.addHandler(manejador)

    host = config.NEO4J_URI.split('://', 1)[-1]
    print(f'Driver neo4j {neo4j.__version__} · Python {sys.version.split()[0]}')
    print(f'Host: {host} · usuario: {config.NEO4J_USUARIO} · base: {config.NEO4J_BASE}\n')

    for esquema in ('neo4j+s', 'bolt+s', 'neo4j+ssc', 'bolt+ssc'):
        uri = f'{esquema}://{host}'
        inicio = time.time()
        try:
            with GraphDatabase.driver(uri, auth=(config.NEO4J_USUARIO, config.NEO4J_CLAVE),
                                      connection_timeout=15, max_transaction_retry_time=5) as d:
                d.verify_connectivity()
                filas, _, _ = d.execute_query('RETURN 1 AS ok', database_=config.NEO4J_BASE)
                print(f'  OK  {esquema:10} conecta y responde ({time.time() - inicio:.1f} s)')
        except Exception as e:
            causa = e.__cause__ or e.__context__
            print(f'  XX  {esquema:10} {type(e).__name__}: {str(e)[:150]}')
            if causa:
                print(f'                 causa: {type(causa).__name__}: {str(causa)[:150]}')
    print(f'\nDetalle completo en {LOG}')


if __name__ == '__main__':
    main()
