"""Carga de los system prompts desde prompts/.

Los prompts de cada submodulo son los de su PI4, sin retipear: se leen del archivo
que entrego cada autor. Si falta alguno, el sistema lo informa en el --check en
lugar de inventar un reemplazo.
"""
from core import config

DIR = config.RAIZ / 'prompts'

ARCHIVOS = {
    'maestro': ['s0_maestro.md'],
    's1_extraccion': ['s1_extraccion.txt', 'prompt_extraccion_S1.txt'],
    's1_explicacion': ['s1_explicacion.txt', 'prompt_explicacion_S1.txt'],
    's2_extraccion': ['s2_extraccion.txt', 'prompt_extraccion_S2.txt'],
    's2_explicacion': ['s2_explicacion.txt', 'prompt_explicacion_S2.txt'],
    's3_extraccion': ['s3_extraccion.md', 'extraccion.md'],
    's3_explicacion': ['s3_explicacion.md', 'explicacion.md'],
    's4_extraccion': ['s4_extraccion.txt', 'prompt_extraccion.txt'],
    's4_explicacion': ['s4_explicacion.txt', 'prompt_explicacion.txt'],
    's4_reintento': ['s4_reintento.txt', 'prompt_reintento.txt'],
}

_cache = {}


class PromptFaltante(FileNotFoundError):
    pass


def cargar(clave, **marcadores):
    """Devuelve el texto del prompt con los marcadores reemplazados.

    Los marcadores son los catalogos leidos del grafo: {aptitudes}, {expresiones},
    {turnos}, {servicios}. Se reemplazan por nombre y no con str.format(), porque
    los prompts contienen llaves de los esquemas JSON que no hay que tocar.
    """
    if clave not in _cache:
        for nombre in ARCHIVOS.get(clave, []):
            ruta = DIR / nombre
            if ruta.exists():
                _cache[clave] = ruta.read_text(encoding='utf-8')
                break
        else:
            raise PromptFaltante(
                f'Falta el prompt "{clave}". Copiá {ARCHIVOS.get(clave, [clave])[0]} '
                f'a la carpeta prompts/ (ver prompts/README.md).')
    texto = _cache[clave]
    for nombre, valor in marcadores.items():
        texto = texto.replace('{' + nombre + '}', valor)
    return texto


def faltantes():
    """Lista de prompts que todavia no estan en la carpeta."""
    salida = []
    for clave, nombres in ARCHIVOS.items():
        if not any((DIR / n).exists() for n in nombres):
            salida.append((clave, nombres[0]))
    return salida
