"""Configuracion unica del asistente integrado (PG3).

Todo se lee de variables de entorno (.env). No hay claves ni URIs en el codigo.
Cada submodulo del PI4 usaba su propio proveedor de LLM y su propia forma de
conectarse a Neo4j; aca hay una sola de cada cosa.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env():
    """Lector minimo de .env (sin dependencias). Las variables ya definidas en el
    entorno tienen prioridad sobre el archivo."""
    archivo = RAIZ / '.env'
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, valor = linea.split('=', 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave, valor)


_cargar_env()


def _bool(nombre, defecto=False):
    return os.getenv(nombre, str(defecto)).strip().lower() in ('1', 'true', 'si', 'sí', 'yes')


# ---------------------------------------------------------------- Neo4j
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USUARIO = os.getenv('NEO4J_USUARIO', 'neo4j')
NEO4J_CLAVE = os.getenv('NEO4J_CLAVE', 'neo4j')
NEO4J_BASE = os.getenv('NEO4J_BASE', 'neo4j')

# ---------------------------------------------------------------- LLM
# proveedor: gemini | groq | ollama | deepseek
LLM_PROVEEDOR = os.getenv('LLM_PROVEEDOR', 'gemini').strip().lower()
LLM_MODELO = os.getenv('LLM_MODELO', '').strip()
LLM_CLAVE = os.getenv('LLM_CLAVE', '').strip()
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')

# Para gemini se deja vacio a proposito: los nombres de modelo rotan, asi que el
# sistema le pregunta a la API cual habilita la clave (core.llm.listar_modelos_gemini).
# Para los demas proveedores se deja el modelo que uso cada PI4.
MODELO_POR_DEFECTO = {
    'gemini': '',
    'groq': 'openai/gpt-oss-120b',
    'deepseek': 'deepseek-chat',
    'ollama': 'qwen2.5:3b',
}

# Temperaturas: 0 para extraer (reproducible), algo mas alta para redactar.
TEMP_EXTRACCION = float(os.getenv('TEMP_EXTRACCION', '0'))
TEMP_EXPLICACION = float(os.getenv('TEMP_EXPLICACION', '0.2'))
MAX_TOKENS_EXTRACCION = int(os.getenv('MAX_TOKENS_EXTRACCION', '900'))
MAX_TOKENS_EXPLICACION = int(os.getenv('MAX_TOKENS_EXPLICACION', '1100'))
# Un listado con varios candidatos (cadena completa) necesita mas salida que un candidato.
MAX_TOKENS_LISTADO = int(os.getenv('MAX_TOKENS_LISTADO', '2200'))

# ---------------------------------------------------------------- Comportamiento
MAX_INTENTOS = int(os.getenv('MAX_INTENTOS', '2'))
FECHA_EVALUACION = os.getenv('FECHA_EVALUACION', '').strip() or None  # ISO; si no, hoy
ESCRITURA_HABILITADA = _bool('ESCRITURA_HABILITADA', True)
GUARDAR_TRAZAS = _bool('GUARDAR_TRAZAS', True)
DIR_TRAZAS = RAIZ / 'trazas'

VERSION_SISTEMA = 'PG3-v1'


def modelo():
    """Modelo configurado. Vacio con gemini significa 'el que elija core.llm'."""
    return LLM_MODELO or MODELO_POR_DEFECTO.get(LLM_PROVEEDOR, '')


def resumen():
    return {
        'neo4j_uri': NEO4J_URI,
        'neo4j_base': NEO4J_BASE,
        'llm_proveedor': LLM_PROVEEDOR,
        'llm_modelo': modelo(),
        'escritura_habilitada': ESCRITURA_HABILITADA,
        'version_sistema': VERSION_SISTEMA,
    }
