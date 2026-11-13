# CAMBIOS — PG3, registro de correcciones (desde el 12/11/2026)

Bitácora para quien siga trabajando sobre `pg3_asistente` (persona o modelo). El plan
completo con el análisis está en el Proyecto de Claude: `claude/PG3_plan_correcciones.md`;
el estado general del prototipo, en `claude/PG3_estado_del_prototipo.md`. Entrega: 15/11/2026.

**Revisión contra la consigna (13/11)** con lo que falta y el mapa del informe: Proyecto de Claude, `claude/PG3_revision_consigna.md`.

**Respaldo:** `proyecto_anterior/` es la copia exacta del código antes de estos cambios
(todo menos `.venv`). No entra al ZIP.

**Reglas que no se tocan:** el LLM solo enruta, extrae y redacta (nunca decide ni escribe
Cypher); todo el Cypher vive en `core/consultas.py`; el motor difuso (`core/motor_difuso.py`)
es el del PG2 y se autoverifica contra los PI3; las devoluciones de los PI4 (S1, S2, S3, S4)
ya están aplicadas y no hay que deshacerlas.

**Cómo verificar sin Neo4j ni LLM:** `python -m pruebas.prueba_devolucion_S2` (18) y
`python -m pruebas.prueba_devolucion_S4` (15). Contra Aura + Gemini: `--limpiar --si` y
después `--casos <IDs> --pausa 10` (genera `pruebas/salida_e2e.md`).

---

## Plan (10 pasos) y estado

| # | Paso | Estado |
|---|---|---|
| 1 | Registrar en la traza los motivos por los que una explicación cae al respaldo (A6) | HECHO 12/11 |
| 2 | Arreglar la caída de S4 al respaldo en la cadena completa (E2E-1, E2E-2) | HECHO en código (tres rondas); verificación contra Aura en curso |
| 3 | Sin valores técnicos en las respuestas de S4 (SOLAPE_PARCIAL, Baja_prioridad, [x, y]…) | HECHO 12/11 |
| 4 | Correr `--depurar --aplicar` en Aura (entradas de S3 por empleado; parámetros difusos en el grafo) y `--recalcular pv_001 --simular` | PENDIENTE (lo corre Sebastián) |
| 5 | Web: ejemplos de S2/S3/S4/simulación/manipulación, id de sesión, botón «Empezar de nuevo», Cypher en el panel, lista de puestos (`/api/puestos`), aviso de duración de la cadena | HECHO 13/11 |
| 6 | Confianza baja del prompt maestro: preguntar en vez de ejecutar + caso ERR-5 | HECHO 13/11 (falta correr ERR-5 contra Aura) |
| 7 | Redacción menor: E2E-7 «pero…, pero», ERR-4 «el Supermercado Sur», cifras con tres decimales | HECHO 13/11 |
| 8 | README y `neo4j/LEEME.txt` desactualizados (casos, memoria mínima, comandos completos, sin dump) | HECHO 13/11 |
| 9 | Corrida final completa limpia → `salida_e2e.md` para el informe | PENDIENTE |
| 9b | Comando `--exportar` (exportación de Neo4j para el ZIP) | HECHO 13/11 en código; lo corre Sebastián |
| 10 | `armar_zip.py` y entregable (excluir respaldos, `.venv`, `.env`, trazas; agregar consultas.cypher, export de Aura, diagrama, informe PDF, video/infografía) | PENDIENTE |

Decisiones del grupo, no de código: representación S3 → S4, parámetros difusos en código vs.
grafo, validación con RR. HH. Si no se resuelven, se declaran como límites con su efecto medido.

---

## Cambios aplicados (detalle por archivo)

### 12/11 — Pasos 1, 2 y 3

**`core/llm.py`**
- `RespuestaLLM` tiene `motivos` (último rechazo del parseo o del validador) y `truncada`;
  `como_dict()` agrega `motivos_rechazo`, `salida_truncada` y `texto_rechazado` (recortado a
  1500 caracteres) cuando `datos` es `None`. Antes esos motivos se descartaban y la traza
  solo decía «respaldo».
- `_ultima_truncada`: Gemini (`finishReason == MAX_TOKENS`), Groq/DeepSeek
  (`finish_reason == length`) y Ollama (`done_reason == length`) informan si la salida se
  cortó; el motivo dice «salida cortada por el límite de N tokens».
- El fallback de `pedir_json()` usa `modelo_en_uso()` (antes quedaba `modelo: ""`).
- Gemini: si el modelo recordado devuelve 503, se prueban los demás candidatos en vez de
  caer al respaldo (E2E-9 del 12/11 falló solo por eso).

**`core/config.py`, `.env`, `.env.ejemplo`**
- `MAX_TOKENS_LISTADO=2200`: tope de salida para listados con más de un candidato
  (`MAX_TOKENS_EXPLICACION=1100` sigue para un candidato o un descarte).

**`submodulos/s4_explicacion.py`**
- `LEGIBLE`, `legible()`, `_legible_en_frase()`, `_num()` (tres decimales, coma) y
  `afinidad_texto()`: traducen códigos del grafo a texto para el reclutador (advertencias,
  marcas, categorías y las cuatro aptitudes del PG2).
- `lectura()` suma `categoria`, `afinidad`, `prioridad` y `marcas` ya escritas con palabras.
- `respaldo()` y `mensaje_listado_vacio()` sin códigos, con tres decimales; muestran
  también los deseables vencidos.
- Usa `MAX_TOKENS_LISTADO` cuando `tipo == 'listado'` y hay más de una ficha.
- Cuando cae al respaldo devuelve `motivos_respaldo`.

**`prompts/prompt_explicacion.txt`** (S4)
- Regla 3: cifras con tres decimales y coma. Regla 14 (nueva): sin códigos técnicos, usar
  las frases de `lectura`, nada de corchetes para la afinidad; `pv_…` sí se puede escribir.

**`core/validador.py`**
- `validar_s4()` punto 6: rechaza palabras con guion bajo (salvo `pv_…`, `ev_…`), los
  estados `SIN_DATO`/`DESCONOCIDO`/`OBSERVADO`/`ESTIMADO`, la afinidad como par entre
  corchetes y «es/estado … con dato» (no la frase del glosario «con dato razonablemente
  preciso», regla FZ5).
- Frases prohibidas («contratá», «asigne a»…) se comparan por palabra completa:
  «contratación» ya no dispara (falso positivo que tiraba E2E-1 al respaldo el 12/11).
- El control de cifras ignora los ids de puesto `pv_<fecha>_<n>`.

**`pruebas/casos_e2e.py`**
- `v_fidelidad_s4()` (obligatoria en E2E-1 y E2E-2): la explicación del listado tiene que
  salir del LLM y pasar la validación; si cae al respaldo el caso falla y muestra los motivos.
- `v_sin_tecnicos()` en E2E-1, E2E-2, E2E-4 y E2E-9.

**`pruebas/prueba_devolucion_S4.py`**
- Las redacciones «correctas» ya no usan códigos; verificación nueva de `lectura` sin códigos
  y un texto con códigos técnicos que tiene que ser rechazado. 15/15 pasan.

**`web/app.js`, `web/estilo.css`**
- Bloque 5 del panel de trazabilidad: motivos del rechazo, aviso de salida truncada y el
  texto rechazado del modelo (plegado); el bloque se abre solo cuando hubo respaldo.

**`.gitignore`**: `proyecto_anterior/`.

### Corridas contra Aura del 12/11
- 16:05, E2E-1 y E2E-9 (antes de los dos arreglos del validador): E2E-1 15/16 — el LLM
  redactó bien y sin códigos, rechazado por «contratación» y «con dato razonablemente
  preciso» (falsos positivos, corregidos); E2E-9 8/9 — Gemini 503 en el único modelo
  recordado (corregido en `llm.py`).
- 16:13, E2E-1 y E2E-9: las dos redacciones del LLM eran buenas y se rechazaron.
  E2E-9 por escribir «Recomendado_con_reservas» (dos intentos); E2E-1 por el control CP1
  (deseable vs. advertencia), que miraba 60 caracteres hacia atrás sin respetar comas:
  «no tiene advertencias registradas, no tiene la aptitud deseable manejo de residuos…» se
  leía como «advertencia de manejo de residuos». Arreglos:
  - `s4_explicacion.normalizar_texto()`: antes de validar, reemplaza en el texto del LLM los
    códigos que tienen nombre legible conocido (categorías, advertencias, aptitudes del PG2).
    Es un cambio de forma; lo que no está en la tabla sigue rechazándose.
  - `validador._clausula_previa()`: los controles CP1 (deseable presentado como advertencia
    y al revés) miran solo dentro de la misma cláusula (cortan en . ; , :). El texto real de
    CP1 del PI4 sigue rechazado (prueba_devolucion_S4 15/15).
  - `legible()` acepta el sufijo del PG2 «manejo_residuos_patogenicos (vencida)».
  - Re-validados offline los dos textos rechazados: ahora pasan.

### 13/11 — Paso 1 de la revisión contra la consigna (pasos 5 a 8 del plan + exportación)

**`web/index.html`, `web/app.js`, `web/estilo.css`**
- 10 casos de prueba precargados: los 5 pedidos de antes + S2 (descarte de Bruno Gómez),
  S3 (datos faltantes de Valeria Núñez), S3 (simulación de Diego Ruiz), S4 (posición de
  Diego Ruiz) y el intento de manipulación. Son los textos de E2E-7 a E2E-10 y ERR-2.
- Sesión propia por pestaña (`sessionStorage` + `crypto.randomUUID`) enviada en cada
  consulta: el pedido en espera ya no se comparte entre navegadores.
- Botón «Empezar de nuevo» → `/api/reiniciar` (existía el endpoint, faltaba el botón).
- Lista de vacantes registradas (`/api/puestos`), que se actualiza cuando un pedido crea una.
- Panel: cada consulta y cada plantilla de escritura muestra la sentencia Cypher desplegable.
- Aviso a los 8 s de espera: la cadena completa puede tardar hasta dos minutos.
- Etiqueta en el pie cuando el enrutamiento fue dudoso y no se ejecutó.

**`orquestador/asistente.py` + `prompts/s0_maestro.md` + `pruebas/casos_e2e.py`**
- Si el prompt maestro devuelve `confianza: baja` y el destino es S2, S3 o S4, no se ejecuta:
  se responde una pregunta de aclaración (`submodulo: 'aclaracion'`, `confianza_baja: True`).
  Los pedidos de cobertura no cambian (S1 pide lo que falte).
- Regla 6 del prompt maestro: «baja» cuando se nombra a una persona o vacante sin decir qué se
  quiere saber; ese mensaje es del dominio, no `fuera_de_dominio`. Ejemplo nuevo («¿Qué pasa
  con Ana Pérez?»).
- Caso ERR-5 («¿Y Diego?»): sin error, sin escrituras y con pedido de aclaración. Va antes de
  los pedidos en `ORDEN`. Total: 15 casos.

**Redacción**
- `submodulos/s2_aptitud.py`: frases fijas sin «pero» al comienzo («tiene registrada la aptitud
  limpieza hospitalaria con la certificación vencida el 28/09/2026, antes de la fecha de
  evaluación 05/10/2026») y con el nombre legible de la aptitud (`_nombre()` usa `legible()` de S4).
  Antes salía «…, pero tiene la aptitud limpieza_hospitalaria, pero su certificación venció…».
- `core/validador._menciones()` reconoce también la aptitud escrita en prosa
  («manejo de residuos patogénicos»), para que los controles de S2 sigan funcionando.
- `submodulos/s1_requisitos.py` y `prompts/s1_explicacion.txt`: un servicio no reconocido se
  nombra como texto escrito que no está en el catálogo, no como «el servicio X» (ERR-4).
- `pruebas/prueba_devolucion_S2.py`: ajustada a la frase nueva (18/18).

**Exportación de Neo4j** (`core/exportar.py`, `core/consultas.py`, `api/main.py`)
- `python -m api.main --exportar`: dos consultas de solo lectura nuevas del catálogo
  (`PG3-export-nodos`, `PG3-export-relaciones`) y escritura de
  `neo4j/Grupo_5_PG3_export.cypher` (reconstruye el grafo en una base vacía con `--cargar`) y
  `neo4j/Grupo_5_PG3_export.json`. Fechas como `date('…')`; avisa si hay vacantes de prueba.

**Documentación**
- `README.md`: tabla completa de comandos, «Cómo reproducir las pruebas», interfaz web nueva,
  estructura con los módulos nuevos, 15 casos, límites corregidos (memoria mínima, palabras
  completas, parámetros difusos en el código, validación por reglas), enlace a GitHub.
- `neo4j/LEEME.txt` reescrito (instalación desde cero o desde la exportación).

**Verificado sin Aura:** compila todo; `prueba_devolucion_S2` 18/18; `prueba_devolucion_S4`
15/15; `core.motor_difuso` coincide con los PI3; `app.js` sin errores de sintaxis; orquestador
con enrutamiento simulado de confianza baja devuelve la aclaración sin consultar el grafo.

### 13/11 — Conexión con Aura pausada
- `core/grafo.py`: `Grafo()` verifica la conexión al abrir (`verify_connectivity`). Si Aura está
  pausada («Unable to retrieve routing information») da un mensaje claro (reanudar la instancia
  en console.neo4j.io) en vez de reintentar 30 s y cortar con traceback.
- `api/main.py`: los comandos de consola muestran ese mensaje sin traceback.
- `orquestador/asistente.py`: la web recibe el mismo mensaje como respuesta en lugar de un error 500.
- Causa real del 13/11: `pruebas/diagnostico_neo4j.py` (nuevo) mostró `SSLCertVerificationError`
  con `neo4j+s` y `bolt+s`, y conexión OK con `neo4j+ssc`. En esa PC/red algo presenta un
  certificado que Python no valida (antivirus que inspecciona TLS, red con inspección o almacén
  de certificados). Se cambió el `.env` a `neo4j+ssc://` (cifrado sin verificar el certificado) y
  se documentó en `.env.ejemplo`. Límite a declarar: en un despliegue real se usaría `neo4j+s`.

### 13/11 — Corrida completa contra Aura (15:43) y depuración aplicada
- `--depurar --aplicar` (salida guardada por Sebastián en `salidaDepurar.txt`): se escribieron en
  el grafo las 30 funciones de pertenencia del motor (faltaban margen_vigencia/critico y holgado,
  solape_horario/insuficiente y total), se borraron las variables duplicadas `afinidad_S4` y
  `desempeno` (mismo concepto que `afinidad` y `desempeno_reciente`) y ahora grafo y motor
  coinciden en las 30. Las entradas de S3 ya estaban en el Empleado (E102 y E103 sin datos
  observados). Las trapezoidales de S3 (cercanía, experiencia) no se escriben: límite conocido.
- `--recalcular pv_001 --simular`: los tres candidatos del PG2 coinciden (0,453 / 0,442 / 0,431).
- `--casos --pausa 10`: 14/15. E2E-1 y E2E-2 con la explicación de S4 redactada por el LLM y
  validada (antes caían al respaldo). Única falla: E2E-2, «Sin códigos técnicos», por
  «afinidad baja con dato razonablemente preciso» (enunciado de la regla FZ5): falso positivo de
  la verificación de la prueba, no del sistema (el validador ya la aceptaba). Corregido en
  `PATRON_TECNICO`.
- Diferencias con el PG2 en puestos nuevos (contraste, no falla): la afinidad sale como intervalo
  porque la cercanía se estima por zona (TRASLADO_ESTIMADO) en lugar del traslado medido del PG2;
  E401 Valeria Núñez Baja prioridad (0,290) vs. Recomendado con reservas (0,397) por la
  representación S3→S4 (punto medio y confiabilidad).
- `--exportar`: 406 nodos y 1052 relaciones en `neo4j/Grupo_5_PG3_export.cypher` y `.json`.
