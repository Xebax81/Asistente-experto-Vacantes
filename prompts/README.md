# Prompts del asistente integrado (PG3)

El PG3 **no reescribe** los prompts de los PI4 individuales: los carga desde esta
carpeta tal como los entregó cada autor. Lo único nuevo es `s0_maestro.md`, el
prompt maestro que pide la consigna ("un System Prompt maestro que enrute la
consulta del usuario hacia el submódulo correspondiente").

## Archivos esperados

| Archivo | Autor | De dónde sale |
|---|---|---|
| `s0_maestro.md` | grupo (PG3) | nuevo, incluido |
| `s1_extraccion.txt` | Arguello (S1) | `prompts/prompt_extraccion_S1.txt` de su PI4 — incluido |
| `s1_explicacion.txt` | Arguello (S1) | `prompts/prompt_explicacion_S1.txt` de su PI4 — incluido |
| `s2_extraccion.txt` | Cayo (S2) | `prompts/prompt_extraccion_S2.txt` de su carpeta de PI4 |
| `s2_explicacion.txt` | Cayo (S2) | `prompts/prompt_explicacion_S2.txt` |
| `s3_extraccion.md` | Gallardo (S3) | `Prompts/extraccion.md` de su carpeta de PI4 |
| `s3_explicacion.md` | Gallardo (S3) | `Prompts/explicacion.md` |
| `s4_extraccion.txt` | León (S4) | `prompts/prompt_extraccion.txt` de su carpeta de PI4 |
| `s4_explicacion.txt` | León (S4) | `prompts/prompt_explicacion.txt` |
| `s4_reintento.txt` | León (S4) | `prompts/prompt_reintento.txt` |

Los de S1 vienen incluidos. **Los seis de S2, S3 y S4 hay que copiarlos de la
carpeta de Drive de cada integrante**, sin retipearlos: así el informe del PG3
puede afirmar que el sistema integrado usa los mismos prompts que se evaluaron en
los PI4, sin diferencias de transcripción.

`python -m api.main --check` avisa cuál falta.

## Marcadores que se reemplazan en tiempo de ejecución

Los prompts de extracción traen marcadores que el orquestador completa con lo que
lee del grafo (consulta `S1-Q0-catalogos`), para que los catálogos crezcan con la
base sin tocar el texto:

- `{aptitudes}` — nombres del catálogo de aptitudes
- `{expresiones}` — diccionario de urgencia (plazos y premuras)
- `{turnos}` — turnos con su horario
- `{servicios}` — servicios con sus alias (solo S2 y S4)

## Un apunte sobre el reintento

Los cuatro PI4 usan el mismo mecanismo: si la validación de fidelidad rechaza la
explicación, se vuelve a pedir indicando los motivos, y tras `MAX_INTENTOS`
rechazos se entrega un texto determinístico armado solo con la ficha. En el PG3
ese comportamiento está centralizado en `core/llm.py` (`pedir_json`, parámetro
`validador`) y en `core/validador.py`, en lugar de estar repetido cuatro veces.
