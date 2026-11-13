"""Acceso unico a la base de conocimiento (Neo4j).

Un solo driver para los cuatro submodulos. Dos puertas separadas:
  leer()    -> solo consultas del catalogo CONSULTAS (verificadas sin clausulas de escritura)
  escribir() -> solo plantillas del catalogo ESCRITURAS

Cada ejecucion queda registrada en la traza (nombre, parametros, filas, milisegundos),
que es lo que la interfaz web muestra en el panel de trazabilidad y lo que cubre el
punto 7 de la consigna del PG3.
"""
import time
import unicodedata

from core import config
from core.consultas import CONSULTAS, ESCRITURAS, MAPA_NORM, verificar_solo_lectura


def normalizar(texto):
    """Minusculas, sin tildes ni ñ. Mismo criterio que el mapa que se pasa a Cypher."""
    if texto is None:
        return None
    t = unicodedata.normalize('NFD', str(texto).lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


class ErrorGrafo(RuntimeError):
    pass


class Traza:
    """Registro de todo lo que paso al responder una consulta."""

    def __init__(self):
        self.pasos = []

    def agregar(self, etapa, detalle):
        self.pasos.append({'etapa': etapa, **detalle})

    def consultas(self):
        return [p for p in self.pasos if p['etapa'] in ('cypher', 'cypher_escritura')]

    def como_dict(self):
        return self.pasos


class Grafo:
    def __init__(self, traza=None):
        malas = verificar_solo_lectura()
        if malas:
            raise ErrorGrafo('Hay consultas de lectura con clausulas de escritura: ' + '; '.join(malas))
        # Import diferido: asi los comandos de diagnostico corren y avisan que
        # falta instalar la dependencia, en lugar de fallar al importar el modulo.
        try:
            from neo4j import GraphDatabase
            try:
                from neo4j.exceptions import ConfigurationError
            except ImportError:
                ConfigurationError = ValueError
        except ImportError as e:
            raise ErrorGrafo(
                'Falta el paquete neo4j. Instalá las dependencias con:  '
                'pip install -r requirements.txt') from e
        # Las notificaciones del servidor (propiedad inexistente, etiqueta sin usar)
        # son avisos, no errores, y ensucian la salida. Se bajan a WARNING o se apagan
        # segun lo soporte la version del driver instalada.
        opciones = {'auth': (config.NEO4J_USUARIO, config.NEO4J_CLAVE)}
        try:
            self._driver = GraphDatabase.driver(
                config.NEO4J_URI, notifications_min_severity='OFF', **opciones)
        except (TypeError, ValueError, ConfigurationError):
            self._driver = GraphDatabase.driver(config.NEO4J_URI, **opciones)
        self.traza = traza or Traza()
        # Se comprueba la conexion al abrir: si Aura esta pausada, el driver reintenta
        # durante 30 s con «Unable to retrieve routing information» y despues falla con
        # un traceback largo. Mejor un mensaje claro de entrada.
        try:
            self._driver.verify_connectivity()
        except Exception as e:
            self._driver.close()
            raise ErrorGrafo(_mensaje_conexion(e)) from e

    def cerrar(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()

    # ------------------------------------------------------------ ejecucion
    def _ejecutar(self, texto, parametros, etiqueta, etapa):
        inicio = time.time()
        try:
            # Los parametros van en el diccionario parameters_ del driver, no como
            # kwargs: asi un nombre de parametro nunca choca con una opcion del driver.
            registros, _, _ = self._driver.execute_query(
                texto, parameters_=parametros, database_=config.NEO4J_BASE)
        except Exception as e:
            if 'DatabaseNotFound' in str(e) or 'does not exist' in str(e):
                raise ErrorGrafo(
                    f'La base de datos "{config.NEO4J_BASE}" no existe en esa instancia. '
                    'Mirá el archivo de credenciales que descargaste al crear la instancia '
                    'de Aura y copiá el valor de NEO4J_DATABASE en NEO4J_BASE del .env '
                    '(según el tipo de instancia puede ser "neo4j" o el id de la instancia).'
                ) from e
            if 'routing information' in str(e) or 'ServiceUnavailable' in type(e).__name__:
                raise ErrorGrafo(_mensaje_conexion(e)) from e
            raise ErrorGrafo(f'Error en {etiqueta}: {e}') from e
        ms = int((time.time() - inicio) * 1000)
        filas = [r.data() for r in registros]
        self.traza.agregar(etapa, {
            'consulta': etiqueta,
            'parametros': _recortar(parametros),
            'filas': len(filas),
            'ms': ms,
            'cypher': texto.strip(),
        })
        return filas

    def leer(self, nombre, **parametros):
        if nombre not in CONSULTAS:
            raise ErrorGrafo(f'Consulta no registrada: {nombre}')
        parametros.setdefault('mapa', MAPA_NORM)
        texto = CONSULTAS[nombre]
        if '$mapa' not in texto:
            parametros.pop('mapa', None)
        return self._ejecutar(texto, parametros, nombre, 'cypher')

    def escribir(self, nombre, **parametros):
        if not config.ESCRITURA_HABILITADA:
            raise ErrorGrafo('La escritura esta deshabilitada (ESCRITURA_HABILITADA=false).')
        if nombre not in ESCRITURAS:
            raise ErrorGrafo(f'Plantilla de escritura no registrada: {nombre}')
        return self._ejecutar(ESCRITURAS[nombre], parametros, nombre, 'cypher_escritura')

    def una(self, nombre, **parametros):
        filas = self.leer(nombre, **parametros)
        return filas[0] if filas else None

    def ejecutar_crudo(self, sentencia):
        """Ejecuta Cypher que NO esta en el catalogo.

        Unico uso previsto: `python -m api.main --cargar <archivo.cypher>`, para
        instalar el grafo del PG2. No lo llama ningun submodulo ni el orquestador,
        y el LLM no tiene forma de llegar aca: la Regla de Oro sigue en pie.
        """
        inicio = time.time()
        registros, _, _ = self._driver.execute_query(
            sentencia, database_=config.NEO4J_BASE)
        self.traza.agregar('cypher_carga', {
            'consulta': 'script de carga', 'parametros': {},
            'filas': len(registros), 'ms': int((time.time() - inicio) * 1000),
            'cypher': sentencia[:200]})
        return [r.data() for r in registros]

    # ------------------------------------------------------------ verificacion
    def verificar(self):
        """Comprueba que el grafo del PG2 este cargado y que el esquema sea el esperado.
        Devuelve (ok, informe)."""
        informe, ok = [], True

        # Sin estas el asistente no puede funcionar.
        esenciales = {
            'Servicio', 'Zona', 'Turno', 'Aptitud', 'Empleado', 'Puesto_Vacante',
            'EvaluacionEmpleadoPuesto', 'Listado_Final', 'Categoria', 'Evidencia',
        }
        # Estas enriquecen las respuestas (glosario, trazabilidad, parametros difusos)
        # pero su ausencia no rompe nada: el motor difuso tiene sus propios parametros.
        opcionales = {
            'Tipo_Servicio', 'Pedido_Cobertura', 'MarcaCalidadDato', 'Regla_Crisp',
            'Regla_Difusa', 'Variable_Linguistica', 'Termino', 'Funcion_Pertenencia',
            'Expresion_Urgencia', 'Version_Modelo_Difuso', 'Grupo_Reglas',
        }
        fila = self.una('PG3-esquema')
        presentes = set(fila['etiquetas']) if fila else set()
        faltan = esenciales - presentes
        if faltan:
            ok = False
            informe.append(f'XX Faltan etiquetas esenciales: {", ".join(sorted(faltan))}')
        else:
            informe.append(f'OK Etiquetas esenciales: estan las {len(esenciales)}')
        faltan_opt = opcionales - presentes
        if faltan_opt:
            informe.append(f'.. Sin estas etiquetas (opcionales): {", ".join(sorted(faltan_opt))}')
            informe.append('   El sistema funciona igual; lo que se pierde es parte del')
            informe.append('   glosario y de los parametros difusos leidos del grafo.')

        esperadas_rel = {
            'EN_ZONA', 'ES_DE_TIPO', 'PERTENECE_A', 'EN_TURNO', 'REQUIERE', 'POSEE',
            'TIENE_DISPONIBILIDAD_EN', 'CERCANA_A', 'GENERA', 'PARA', 'REFIERE_A',
            'TIENE_CATEGORIA', 'INCLUYE', 'REFERIDO_A', 'RESPALDADO_POR', 'ACTIVA',
        }
        fila = self.una('PG3-esquema-rel')
        presentes_rel = set(fila['relaciones']) if fila else set()
        faltan_rel = esperadas_rel - presentes_rel
        if faltan_rel:
            ok = False
            informe.append(f'XX Faltan relaciones: {", ".join(sorted(faltan_rel))}')
        else:
            informe.append(f'OK Relaciones: estan las {len(esperadas_rel)} esperadas')

        for fila in self.leer('PG3-conteos'):
            if fila['etiqueta'] in ('Empleado', 'Puesto_Vacante', 'EvaluacionEmpleadoPuesto',
                                   'Listado_Final', 'Evidencia', 'Aptitud', 'Servicio'):
                informe.append(f"   {fila['etiqueta']}: {fila['cantidad']}")

        # Cada consulta del catalogo se prueba contra el grafo con parametros vacios
        # o de ejemplo, para detectar nombres de propiedad que cambiaron.
        informe.append('Prueba de las consultas del catalogo:')
        muestra = self.leer('S2-Q2b-puestos-registrados')
        puesto = muestra[0]['puesto'] if muestra else None
        pruebas = {
            'S1-Q0-catalogos': {},
            'S1-Q1-funciones': {},
            'S1-Q1b-reglas': {},
            'S1-Q2-servicio': {'servicios': [{'texto': 'x', 'norm': 'x'}]},
            'S1-Q3-zona': {'servicio': None, 'zona': None},
            'S1-Q4-turno': {'turnos': [{'texto': 'x', 'norm': 'x'}]},
            'S1-Q5-aptitudes': {'aptitudes': [{'texto': 'x', 'norm': 'x', 'marcador': None, 'candidato': None}]},
            'S1-Q6-urgencia': {'expresiones': [{'texto': 'x', 'norm': 'x'}]},
            'S2-Q3-empleado': {'texto': 'x'},
            'S3-catalogo': {},
        }
        if puesto:
            pruebas.update({
                'S2-Q4-requisitos': {'puesto': puesto},
                'S2-Q5-perfiles': {'puesto': puesto, 'legajos': []},
                'S3-ranking': {'puesto': puesto},
                'S4-5-listado-vacio': {'puesto': puesto},
                'S4-1-descartes': {'puesto': puesto},
                'S4-E-fichas': {'puesto': puesto, 'legajo': None, 'categoria': None,
                                'solo_con_advertencias': False},
                'PG3-evaluaciones-del-puesto': {'puesto': puesto},
            })
        for nombre, params in pruebas.items():
            try:
                self.leer(nombre, **params)
                informe.append(f'   OK {nombre}')
            except ErrorGrafo as e:
                ok = False
                informe.append(f'   XX {nombre}: {str(e)[:160]}')

        return ok, informe


def _mensaje_conexion(e):
    texto = str(e)
    if 'databases.neo4j.io' in config.NEO4J_URI:
        return ('No se pudo conectar con Neo4j Aura. Lo más probable es que la instancia esté '
                'PAUSADA (las gratuitas se pausan solas por inactividad): entrá a '
                'https://console.neo4j.io, buscá la instancia y apretá «Resume»; tarda uno o dos '
                'minutos en quedar «Running». Si ya está en marcha, revisá la conexión a internet '
                f'y NEO4J_URI en el .env. Detalle: {texto[:160]}')
    return (f'No se pudo conectar con Neo4j en {config.NEO4J_URI}: ¿está levantado el '
            f'contenedor o el servicio? Detalle: {texto[:160]}')


def _recortar(parametros, largo=160):
    """Los parametros con listas largas se recortan para que la traza sea legible."""
    salida = {}
    for k, v in parametros.items():
        if k == 'mapa':
            continue
        texto = repr(v)
        salida[k] = texto if len(texto) <= largo else texto[:largo] + '…'
    return salida
