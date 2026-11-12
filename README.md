# Asistente Experto para Recomendación de Personal en Cobertura de Vacantes Internas

**Grupo 5 – 5K10 · Cátedra de Inteligencia Artificial · UTN FRM · Actividad PG3 (Unidad 4)**

Integración de los cuatro submódulos desarrollados en los PI4 en un único asistente
inteligente, con punto de entrada común, prompt maestro de enrutamiento e interfaz web.

---

## 1. Qué hace

Un supervisor o un reclutador escribe en lenguaje natural. Un **prompt maestro**
decide a qué submódulo corresponde la consulta y el orquestador la resuelve
contra la base de conocimiento en Neo4j:

| Submódulo | Autor (PI4) | Qué resuelve |
|---|---|---|
| **S1** Requisitos de vacante | Arguello | Interpreta el pedido, calcula la urgencia difusa y registra el `Puesto_Vacante` |
| **S2** Aptitud y disponibilidad | Cayo | Aplica S2-R01..R10: quién puede cubrirlo y por qué alguien queda afuera |
| **S3** Afinidad y priorización | Gallardo | Calcula la afinidad difusa, con intervalo cuando hay datos desconocidos |
| **S4** Explicación y listado final | León | Clasifica, arma el listado y explica con la evidencia del grafo |

Si el mensaje pide cubrir una vacante **y** pregunta a quién asignar, se recorre la
**cadena completa S1 → S2 → S3 → S4** en una sola consulta. Esa es la prueba de
integración: la respuesta cruza los cuatro submódulos.

### La Regla de Oro se mantiene

El modelo de lenguaje interviene en tres lugares y en ninguno decide:

1. **Enrutar** (prompt maestro): dice "esto es para S2". No dice quién es apto.
2. **Extraer**: copia fragmentos del texto del usuario a un JSON. No resuelve alias
   ni identificadores: eso lo hace el grafo.
3. **Redactar**: explica una ficha ya calculada. Lo que escribe se verifica contra
   esa ficha antes de mostrarlo.

El LLM **nunca escribe Cypher**. Todas las sentencias están fijas y parametrizadas
en `core/consultas.py`, y al arrancar el sistema verifica que ninguna consulta del
catálogo de lectura contenga cláusulas de escritura.

---

## 2. Qué agrega el PG3 respecto de los PI4

Los cuatro PI4 funcionaban, pero eran cuatro programas independientes: cuatro
proveedores de LLM (Groq, Groq, DeepSeek, Ollama), dos formas de hablar con Neo4j
y dos instancias distintas. Además había un corte real en la cadena.

**El corte.** En los PI4, S3 y S4 solo leen. El motor difuso de S3 se usaba
únicamente para simulaciones hipotéticas y S4 "no recalcula nada, solo recupera y
verbaliza". Las afinidades, categorías y listados de los tres puestos del PG2
estaban **cargados a mano** en `Grupo_5_PG2_U1_carga.cypher`. Por eso un pedido
nuevo llegaba hasta S2 y ahí se terminaba: no había afinidad que leer ni listado
que explicar.

**Lo que se agregó:**

| Pieza | Archivo | Qué resuelve |
|---|---|---|
| Cierre de la cadena | `submodulos/inferencia.py` | Calcula y **persiste** la afinidad de S3 y la categoría, prioridad y `Listado_Final` de S4 para puestos nuevos |
| Prompt maestro | `prompts/s0_maestro.md` | Enrutamiento al submódulo correspondiente |
| Orquestador | `orquestador/asistente.py` | Entrada única `responder()` y la cadena E2E |
| Pasarela de LLM | `core/llm.py` | Un solo proveedor configurable, en vez de cuatro |
| Acceso al grafo | `core/grafo.py` | Un solo driver, catálogo de consultas, traza de todo lo ejecutado |
| Validación de fidelidad | `core/validador.py` | Los controles de los cuatro PI4 unificados, más las tres mejoras que el PI4 de S4 dejó propuestas |
| API + interfaz web | `api/main.py`, `web/` | Entrada única y panel de trazabilidad |

**Importante:** `inferencia.py` no inventa conocimiento. Usa el mismo
`core/motor_difuso.py` del PG2 —que se autoverifica contra los valores publicados
en los PI3— y escribe sus resultados con plantillas fijas. Corriéndolo sobre los
puestos del PG2 reproduce los valores que estaban cargados a mano (por ejemplo,
Diego Ruiz: afinidad 0,601 → prioridad 0,431 → Recomendado con reservas, regla FZ4),
lo que sirve como prueba de regresión.

---

## 3. Instalación

Requiere **Python 3.9+**, **Neo4j** (Docker local o Aura) y una clave de LLM.

```bash
cd pg3_asistente
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

### Base de conocimiento

Cargar el grafo del PG2 en Neo4j y, después, el complemento de S1 (una sola vez):

```bash
python -m api.main --cargar neo4j/Grupo_5_PG2_U1_carga.cypher
python -m api.main --cargar neo4j/S1_PI4_complemento.cypher
```

El complemento viene del PI4 de S1: agrega los sinónimos de aptitudes y los
marcadores de exigencia de la regla S1-R02 («indispensable», «sí o sí»…). Si no se
carga, S1 usa una lista de marcadores por defecto, pero las aptitudes escritas de
otra forma («manejo de maquinaria industrial») no se reconocen.

### Configuración

```bash
copy .env.ejemplo .env          # Windows   (cp en Linux/macOS)
```

y completar:

```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_USUARIO=neo4j
NEO4J_CLAVE=tu_clave

LLM_PROVEEDOR=gemini            # gemini | groq | deepseek | ollama
LLM_CLAVE=tu_clave_de_ai_studio
```

**No hace falta saber el nombre del modelo.** `LLM_MODELO` se deja vacío: el
sistema le pregunta a la API de Gemini cuáles habilita tu clave y elige uno
estable de la familia *flash*. Para verlos y fijar otro a mano:

```bash
python -m api.main --modelos
```

El proveedor por defecto es **Gemini** (Google AI Studio, tier gratuito, sin
tarjeta). Se puede cambiar a Groq, DeepSeek u Ollama local sin tocar código.
Ollama funciona pero es lento sin GPU: cada consulta hace 2 o 3 llamadas al
modelo, así que para la interfaz web conviene un proveedor remoto.

### Prompts de los compañeros

Los prompts de S1 vienen incluidos. Hay que copiar los seis de S2, S3 y S4 desde la
carpeta de Drive de cada integrante a `prompts/` — ver `prompts/README.md`. No hay
que retipearlos: así el informe puede afirmar que el sistema integrado usa los
mismos prompts evaluados en los PI4.

Si falta alguno, el sistema no se cae: ese submódulo entrega su texto
determinístico de respaldo (regla A6) y el `--check` avisa cuál falta.

---

## 4. Uso

```bash
python -m api.main --check                  # verifica grafo, prompts, LLM y motor difuso
python -m api.main                          # servidor en http://localhost:8000
python -m api.main -q "¿Quién puede cubrir el turno tarde del Hospital Central?"
python -m api.main --casos                  # pruebas E2E -> pruebas/salida_e2e.md
python -m api.main --recalcular pv_001      # corre S3 + S4 sobre un puesto y persiste
python -m api.main --modelos                # lista los modelos que habilita tu clave
python -m core.motor_difuso                 # verifica el motor contra los PI3
```

### La interfaz web

A la izquierda, la conversación. A la derecha, el **panel de trazabilidad**, que
para cada respuesta muestra:

1. el enrutamiento del prompt maestro, con su nivel de confianza;
2. qué extrajo el LLM de cada submódulo (el JSON completo);
3. **cada consulta Cypher ejecutada**, con sus parámetros, filas y milisegundos;
4. las escrituras en el grafo, si las hubo;
5. el resultado de la **validación de fidelidad** y las evidencias citadas;
6. las etapas recorridas, cuando fue la cadena completa.

Eso es el punto 7 de la consigna —trazabilidad del conocimiento— hecho visible en
pantalla: fuente, regla, evidencia, consulta ejecutada y explicación generada.

Cada interacción se guarda además en `trazas/` como JSON, para poder auditarla
después o citarla en el informe.

---

## 5. Estructura

```
pg3_asistente/
├─ core/
│  ├─ config.py          configuración única (.env)
│  ├─ llm.py             pasarela al LLM (gemini | groq | deepseek | ollama)
│  ├─ grafo.py           driver de Neo4j, traza, verificación de esquema
│  ├─ consultas.py       TODO el Cypher del sistema (lectura y escritura separadas)
│  ├─ motor_difuso.py    motor Mamdani del PG2, sin cambios
│  ├─ validador.py       validación de fidelidad unificada
│  └─ prompts.py         carga de los prompts de cada autor
├─ submodulos/
│  ├─ s1_requisitos.py   S1 (Arguello)
│  ├─ s2_aptitud.py      S2 (Cayo)
│  ├─ s3_afinidad.py     S3 (Gallardo)
│  ├─ s4_explicacion.py  S4 (León)
│  └─ inferencia.py      NUEVO: cálculo y persistencia de S3 y S4
├─ orquestador/
│  └─ asistente.py       prompt maestro, enrutamiento y cadena E2E
├─ prompts/              los system prompts (ver prompts/README.md)
├─ api/main.py           FastAPI + CLI
├─ web/                  interfaz (HTML + CSS + JS, sin build)
├─ pruebas/casos_e2e.py  5 casos integrados + 4 de error
└─ neo4j/                script de carga del PG2 y dump
```

---

## 6. Cómo cubre la consigna

| Punto del PG3 | Dónde está |
|---|---|
| 1. Revisión y depuración final | `--check` verifica etiquetas, relaciones y las 20 consultas del catálogo contra el grafo |
| 2. Integración del asistente | Base en Neo4j, reglas crisp en los submódulos, componentes difusos en `motor_difuso.py`, LLM como interfaz, interfaz web |
| 3. Arquitectura final | Sección 2 de este README y el panel de trazabilidad |
| 4. Casos de uso integrados | `pruebas/casos_e2e.py`: 5 casos que cruzan submódulos |
| 5. Pruebas funcionales | `--casos` genera `pruebas/salida_e2e.md` con esperado vs. obtenido |
| 6. Evaluación del sistema | Sección 7 |
| 7. Trazabilidad | Panel de trazabilidad + `trazas/*.json` + nodos `Evidencia` en el grafo |
| 8. Reflexión metodológica | Para el informe |
| Prompt maestro | `prompts/s0_maestro.md` |
| API o interfaz | `api/main.py` + `web/` |
| Pruebas E2E | E2E-1 a E2E-5 |

---

## 7. Límites conocidos

Van al informe, en la sección de evaluación crítica:

- **Conocimiento sin validar.** Alias, marcadores, diccionario de urgencia, cortes
  0,610 / 0,367 y el criterio de orden siguen siendo diseño del grupo: falta la
  entrevista con el reclutador. El sistema explica bien una política que todavía es
  candidata.
- **Dos urgencias.** S1 produce `urgencia_pedido` y S3 tiene su propia variable
  `urgencia` (hallazgo D1 del PG2). La integración usa los grados de S1 como entrada
  de S3, que es la reconciliación que pidió la cátedra, pero el modelo conceptual
  todavía tiene las dos representaciones.
- **Entradas de S3 en puestos nuevos.** Para una vacante recién creada no hay
  experiencia equivalente ni desempeño registrados: quedan `DESCONOCIDO` y la
  afinidad sale como intervalo con confiabilidad baja. Es el comportamiento correcto
  del modelo de incertidumbre, y el sistema lo dice, pero conviene cargar esos datos
  por empleado para que el listado sea útil.
- **La cercanía es estimada por zona**, no medida: misma zona, zona cercana o lejana.
  Queda marcada como `TRASLADO_ESTIMADO`.
- **La validación de fidelidad controla datos, no matices.** Verifica cifras, citas,
  categorías y menciones obligatorias; no detecta un error de interpretación que no
  use números.
- **Sin memoria de conversación.** Cada consulta es independiente: "¿y la otra
  candidata?" no se resuelve con el contexto anterior.
- **Coincidencia por subcadena**: no tolera errores de tipeo en nombres de servicios
  ni de personas.
