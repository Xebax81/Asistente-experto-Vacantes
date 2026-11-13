// Grupo 5 – 5K10 · PG3 · Catálogo de consultas Cypher del asistente integrado
// Generado el 13/11/2026 desde core/consultas.py (fuente única: el asistente ejecuta exactamente estas sentencias).
// Son plantillas parametrizadas: los valores llegan como parámetros ($nombre) desde Python;
// el modelo de lenguaje no escribe Cypher. Las de LECTURA se verifican sin cláusulas de escritura al arrancar.
// Para probar una en Neo4j Browser: definir antes los parámetros, p. ej.  :param puesto => "pv_001"

// ==============================================================================
// LECTURA (40 sentencias)
// ==============================================================================

// ---- S1-Q0-catalogos
MATCH (a:Aptitud)
WITH collect(DISTINCT {nombre: a.nombre, tipo: a.tipo, vence: a.vence,
                       sinonimos: coalesce(a.sinonimos, [])}) AS aptitudes
MATCH (t:Turno)
WITH aptitudes, collect(DISTINCT {nombre: t.nombre, inicio: toString(t.horario_inicio),
                                  fin: toString(t.horario_fin)}) AS turnos
OPTIONAL MATCH (e:Expresion_Urgencia)
WITH aptitudes, turnos,
     collect(DISTINCT {texto: e.texto, tipo: e.tipo, valor: e.valor, unidad: e.unidad,
                       fuente: e.fuente, estado_validacion: e.estado_validacion}) AS expresiones
MATCH (s:Servicio)
OPTIONAL MATCH (s)-[:EN_ZONA]->(z:Zona)
WITH aptitudes, turnos, expresiones,
     collect(DISTINCT {nombre: s.nombre, alias: coalesce(s.alias, []), zona: z.nombre}) AS servicios
MATCH (zz:Zona)
RETURN aptitudes, turnos, expresiones, servicios,
       collect(DISTINCT zz.nombre) AS zonas;

// ---- S1-Q1-funciones
MATCH (v:Variable_Linguistica)-[:TIENE_TERMINO]->(t:Termino)-[:DEFINIDO_POR]->(f:Funcion_Pertenencia)
WHERE v.submodulo = 'S1' OR v.nombre IN ['plazo_cobertura', 'premura_expresada', 'urgencia_pedido']
RETURN v.nombre AS variable, t.nombre AS termino, f.forma AS forma,
       f.centro AS centro, f.sigma AS sigma, f.version AS version,
       f.estado_validacion AS estado
ORDER BY variable, termino;

// ---- S1-Q1b-reglas
MATCH (r:Regla_Difusa) WHERE r.submodulo = 'S1'
OPTIONAL MATCH (r)-[:INTEGRA]->(gr:Grupo_Reglas)
RETURN r.id AS id, r.antecedente AS antecedente, r.consecuente AS consecuente,
       r.operadores AS operadores, collect(DISTINCT gr.id) AS grupos
ORDER BY id;

// ---- S1-Q2-servicio
UNWIND $servicios AS st
MATCH (s:Servicio)
OPTIONAL MATCH (s)-[:EN_ZONA]->(z:Zona)
OPTIONAL MATCH (s)-[:ES_DE_TIPO]->(ts:Tipo_Servicio)
WITH st, s, z, ts,
     reduce(x = toLower(s.nombre), p IN $mapa | replace(x, p[0], p[1])) AS nombre_n,
     [al IN coalesce(s.alias, []) | reduce(x = toLower(al), p IN $mapa | replace(x, p[0], p[1]))] AS alias_n
WITH st, s, z, ts, nombre_n, alias_n,
     CASE
       // Por palabras completas: «el supermercado sur» no contiene el alias «el super».
       WHEN st.norm = nombre_n OR (' ' + st.norm + ' ') CONTAINS (' ' + nombre_n + ' ') THEN 'exacta'
       WHEN any(al IN alias_n WHERE st.norm = al OR (' ' + st.norm + ' ') CONTAINS (' ' + al + ' ')) THEN 'por_alias'
       WHEN any(w IN split(nombre_n, ' ') WHERE size(w) >= 4 AND (' ' + st.norm + ' ') CONTAINS (' ' + w + ' ')) THEN 'parcial'
     END AS coincidencia
WITH st, collect(CASE WHEN coincidencia IS NOT NULL THEN
       {nombre: s.nombre, coincidencia: coincidencia, zona: z.nombre, tipo: ts.nombre,
        alias_estado: s.alias_estado_validacion} END) AS candidatos
WITH st, candidatos, [c IN candidatos WHERE c.coincidencia IN ['exacta', 'por_alias']] AS fuertes
RETURN st.texto AS texto,
       CASE WHEN size(fuertes) = 1 THEN fuertes[0].coincidencia
            WHEN size(fuertes) > 1 THEN 'ambiguo' ELSE 'no_reconocido' END AS resolucion,
       CASE WHEN size(fuertes) = 1 THEN fuertes[0] END AS servicio,
       [c IN fuertes | c.nombre] AS coincidencias,
       [c IN candidatos WHERE c.coincidencia = 'parcial' | c.nombre] AS sugerencias;

// ---- S1-Q3-zona
OPTIONAL MATCH (s:Servicio {nombre: $servicio})-[:EN_ZONA]->(zs:Zona)
MATCH (z:Zona)
WITH zs, z, reduce(x = toLower(z.nombre), p IN $mapa | replace(x, p[0], p[1])) AS zn
WITH zs,
     collect(CASE WHEN $zona IS NOT NULL AND ($zona.norm = zn OR $zona.norm CONTAINS zn) THEN z.nombre END) AS reconocidas,
     collect(CASE WHEN $zona IS NOT NULL AND any(w IN split(zn, ' ') WHERE size(w) >= 4 AND $zona.norm CONTAINS w)
             THEN z.nombre END) AS parciales
RETURN zs.nombre AS zona_servicio, reconocidas,
       [q IN parciales WHERE NOT q IN reconocidas] AS sugerencias,
       CASE WHEN $zona IS NULL AND zs IS NOT NULL THEN 'heredada'
            WHEN $zona IS NULL THEN 'sin_dato'
            WHEN size(reconocidas) = 1 THEN 'declarada'
            ELSE 'no_reconocida' END AS resolucion;

// ---- S1-Q4-turno
UNWIND $turnos AS tt
MATCH (t:Turno)
WITH tt, t, reduce(x = toLower(t.nombre), p IN $mapa | replace(x, p[0], p[1])) AS tn
WITH tt, collect(CASE WHEN tt.norm CONTAINS tn THEN
       {nombre: t.nombre, inicio: toString(t.horario_inicio), fin: toString(t.horario_fin)} END) AS c
RETURN tt.texto AS texto, [x IN c WHERE x IS NOT NULL] AS coincidencias;

// ---- S1-Q5-aptitudes
UNWIND $aptitudes AS at
MATCH (a:Aptitud)
WITH at, a,
     reduce(x = toLower(a.nombre), p IN $mapa | replace(x, p[0], p[1])) AS nombre_n,
     [sn IN coalesce(a.sinonimos, []) | reduce(x = toLower(sn), p IN $mapa | replace(x, p[0], p[1]))] AS sin_n
WITH at, a, nombre_n,
     CASE WHEN at.norm CONTAINS replace(nombre_n, '_', ' ') OR at.norm CONTAINS nombre_n THEN 'exacta'
          WHEN any(sn IN sin_n WHERE at.norm CONTAINS sn) THEN 'sinonimo' END AS coincidencia
WITH at, collect(CASE WHEN coincidencia IS NOT NULL THEN
       {nombre: a.nombre, tipo: a.tipo, vence: a.vence, resolucion: coincidencia} END) AS c
RETURN at.texto AS texto, at.marcador AS marcador, at.candidato AS candidato,
       [x IN c WHERE x IS NOT NULL] AS coincidencias;

// ---- S1-Q5b-marcadores
MATCH (r:Regla_Crisp) WHERE r.id = 'S1-R02'
RETURN coalesce(r.marcadores, []) AS marcadores, r.enunciado AS enunciado;

// ---- S1-Q6-urgencia
UNWIND $expresiones AS et
MATCH (e:Expresion_Urgencia)
WITH et, e, reduce(x = toLower(e.texto), p IN $mapa | replace(x, p[0], p[1])) AS en
WITH et, collect(CASE WHEN et.norm = en OR et.norm CONTAINS en THEN
       {texto: e.texto, tipo: e.tipo, valor: e.valor, unidad: e.unidad,
        fuente: e.fuente, estado_validacion: e.estado_validacion} END) AS c
RETURN et.texto AS texto, [x IN c WHERE x IS NOT NULL] AS coincidencias;

// ---- S1-Q7-puestos-existentes
UNWIND $vacantes AS v
OPTIONAL MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio {nombre: v.servicio})
OPTIONAL MATCH (p)-[:EN_TURNO]->(t:Turno {nombre: v.turno})
OPTIONAL MATCH (ped:Pedido_Cobertura)-[:GENERA]->(p)
WITH v, p, t, ped WHERE p IS NOT NULL AND t IS NOT NULL
RETURN v.servicio AS servicio, v.turno AS turno,
       collect({puesto: p.id, pedido: ped.id, urgencia: p.urgencia_categoria}) AS existentes;

// ---- S2-Q2-puesto
MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (p)-[:EN_TURNO]->(t:Turno)
OPTIONAL MATCH (p)-[:EN_ZONA]->(z:Zona)
OPTIONAL MATCH (s)-[:ES_DE_TIPO]->(ts:Tipo_Servicio)
WITH p, s, t, z, ts,
     reduce(x = toLower(s.nombre), q IN $mapa | replace(x, q[0], q[1])) AS nombre_n,
     [al IN coalesce(s.alias, []) | reduce(x = toLower(al), q IN $mapa | replace(x, q[0], q[1]))] AS alias_n
WHERE ($puesto_id IS NOT NULL AND p.id = $puesto_id)
   OR ($servicio IS NOT NULL AND ($servicio = nombre_n OR $servicio CONTAINS nombre_n
                                  OR any(al IN alias_n WHERE $servicio CONTAINS al)))
WITH p, s, t, z, ts WHERE $turno IS NULL OR t.nombre = $turno
RETURN p.id AS puesto, s.nombre AS servicio, ts.nombre AS tipo_servicio,
       t.nombre AS turno, toString(t.horario_inicio) AS inicio, toString(t.horario_fin) AS fin,
       z.nombre AS zona, p.urgencia_categoria AS urgencia, p.urgencia_estado AS urgencia_estado,
       p.grado_urgencia_baja AS u_baja, p.grado_urgencia_media AS u_media, p.grado_urgencia_alta AS u_alta,
       toString(p.fecha_evaluacion) AS fecha_evaluacion
ORDER BY puesto;

// ---- S2-Q2b-puestos-registrados
MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (p)-[:EN_TURNO]->(t:Turno)
RETURN p.id AS puesto, s.nombre AS servicio, t.nombre AS turno
ORDER BY puesto;

// ---- S2-Q3-empleado
MATCH (e:Empleado)
WITH e, reduce(x = toLower(e.nombre), p IN $mapa | replace(x, p[0], p[1])) AS nombre_n
WITH e, nombre_n,
     CASE WHEN toLower(e.id) = $texto THEN 'legajo'
          WHEN nombre_n = $texto THEN 'exacta'
          WHEN nombre_n CONTAINS $texto OR $texto CONTAINS nombre_n THEN 'parcial'
          WHEN any(w IN split($texto, ' ') WHERE size(w) >= 3 AND nombre_n CONTAINS w) THEN 'parcial'
     END AS coincidencia
WITH collect(CASE WHEN coincidencia IS NOT NULL THEN
       {legajo: e.id, nombre: e.nombre, coincidencia: coincidencia} END) AS c
WITH [x IN c WHERE x IS NOT NULL] AS candidatos
RETURN candidatos,
       [x IN candidatos WHERE x.coincidencia IN ['legajo', 'exacta']] AS fuertes;

// ---- S2-Q4-requisitos
MATCH (p:Puesto_Vacante {id: $puesto})
OPTIONAL MATCH (p)-[rq:REQUIERE]->(a:Aptitud)
WITH p, collect(DISTINCT {aptitud: a.nombre, excluyente: rq.excluyente, origen: 'pedido',
                          regla: rq.regla, estado_validacion: rq.estado_validacion}) AS del_pedido
OPTIONAL MATCH (p)-[:PERTENECE_A]->(:Servicio)-[:ES_DE_TIPO]->(ts:Tipo_Servicio)-[ex:EXIGE]->(a2:Aptitud)
WITH del_pedido, collect(DISTINCT {aptitud: a2.nombre, excluyente: true, origen: 'catalogo',
                                   regla: 'S2-R01', estado_validacion: ex.estado_validacion}) AS del_catalogo
RETURN [x IN del_pedido WHERE x.aptitud IS NOT NULL] AS del_pedido,
       [x IN del_catalogo WHERE x.aptitud IS NOT NULL] AS del_catalogo;

// ---- S2-Q5-perfiles
MATCH (p:Puesto_Vacante {id: $puesto})-[:EN_ZONA]->(zp:Zona)
MATCH (p)-[:EN_TURNO]->(tp:Turno)
MATCH (e:Empleado) WHERE size($legajos) = 0 OR e.id IN $legajos
RETURN e.id AS legajo, e.nombre AS nombre,
       [(e)-[po:POSEE]->(a:Aptitud) | {aptitud: a.nombre, vencimiento: toString(po.vencimiento)}] AS aptitudes,
       [(e)-[d:TIENE_DISPONIBILIDAD_EN]->(t:Turno) | {turno: t.nombre, habitual: d.habitual,
            desde: substring(toString(d.desde), 0, 5), hasta: substring(toString(d.hasta), 0, 5)}] AS turnos,
       [(e)-[d:TIENE_DISPONIBILIDAD_EN]->(z:Zona) | {zona: z.nombre, habitual: d.habitual}] AS zonas,
       [(e)-[:TIENE_DISPONIBILIDAD_EN {habitual: true}]->(z:Zona)-[:CERCANA_A]-(zp) | z.nombre] AS zonas_cercanas_al_puesto,
       tp.nombre AS turno_puesto, zp.nombre AS zona_puesto,
       substring(toString(tp.horario_inicio), 0, 5) AS turno_inicio,
       substring(toString(tp.horario_fin), 0, 5) AS turno_fin,
       e.experiencia_meses AS experiencia_meses,
       e.desempeno_reciente AS desempeno_reciente,
       e.entradas_estado_validacion AS entradas_estado
ORDER BY legajo;

// ---- S2-Q6-aptitud-vigente
MATCH (e:Empleado)-[po:POSEE]->(a:Aptitud {nombre: $aptitud})
RETURN e.id AS legajo, e.nombre AS nombre, a.nombre AS aptitud,
       toString(po.vencimiento) AS vencimiento, a.vence AS vence
ORDER BY legajo;

// ---- S3-catalogo
MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p), (ev)-[:REFIERE_A]->(e:Empleado)
WITH p, s, collect({legajo: e.id, nombre: e.nombre, estado_S2: ev.estado_S2, evaluacion: ev.id}) AS evs
RETURN p.id AS puesto, s.nombre AS servicio, s.alias AS alias_servicio,
       [x IN evs WHERE x.legajo IS NOT NULL] AS evaluaciones
ORDER BY puesto;

// ---- S3-ranking
MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p:Puesto_Vacante {id: $puesto})-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (lf)-[inc:INCLUYE]->(ev:EvaluacionEmpleadoPuesto)-[:REFIERE_A]->(e:Empleado)
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(c:Categoria)
OPTIONAL MATCH (ev)-[pr:PRECEDE_A]->(sig:EvaluacionEmpleadoPuesto)-[:REFIERE_A]->(es:Empleado)
OPTIONAL MATCH (ev)-[:TIENE_MARCA]->(m:MarcaCalidadDato)
WITH lf, p, s, inc, ev, e, c, tc, pr, es, collect(DISTINCT m.codigo) AS marcas
OPTIONAL MATCH (ev)-[:RESPALDADO_POR]->(x:Evidencia)
WITH lf, p, s, inc, ev, e, c, tc, pr, es, marcas,
     collect(DISTINCT x {.id, .tipo, .valor, .valor_min, .valor_max, .detalle}) AS evidencias
ORDER BY inc.posicion_afinidad
WITH lf, p, s, collect(CASE WHEN ev IS NULL THEN null ELSE {
       legajo: e.id, empleado: e.nombre, evaluacion: ev.id,
       afinidad: [ev.grado_afinidad_min, ev.grado_afinidad_max], confiabilidad: ev.confiabilidad,
       posicion_por_afinidad: inc.posicion_afinidad, posicion_por_prioridad: inc.posicion_prioridad,
       siguiente_por_prioridad: es.id, estado_orden_con_siguiente: pr.estado_orden,
       categoria_S4: c.nombre, prioridad_S4: tc.prioridad,
       marca_transicion: ev.marca_transicion, marcas: marcas, evidencias: evidencias
     } END) AS candidatos
RETURN {
  puesto: p.id, servicio: s.nombre, urgencia: p.urgencia_categoria,
  urgencia_estado: p.urgencia_estado, criterio_orden: lf.criterio_orden,
  criterio_desempate: lf.criterio_desempate, n_candidatos_validos: lf.n_candidatos_validos,
  n_descartados: lf.n_descartados, conteo_motivos: lf.conteo_motivos,
  motivo_critico: lf.motivo_critico, candidatos: candidatos
} AS ranking;

// ---- S3-detalle
MATCH (p:Puesto_Vacante {id: $puesto})-[:PERTENECE_A]->(s:Servicio), (e:Empleado {id: $legajo})
OPTIONAL MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p), (ev)-[:REFIERE_A]->(e)
OPTIONAL MATCH (ev)-[a:ACTIVA]->(r:Regla_Difusa) WHERE r.submodulo IN ['S2', 'S3']
WITH p, s, e, ev, collect(DISTINCT CASE WHEN r IS NULL THEN null ELSE
       {regla: r.id, consecuente: r.consecuente, proposito: r.proposito, fuerza: a.fuerza} END) AS reglas
OPTIONAL MATCH (ev)-[:TIENE_MARCA]->(m:MarcaCalidadDato)
WITH p, s, e, ev, reglas, collect(DISTINCT CASE WHEN m IS NULL THEN null ELSE
       {codigo: m.codigo, uso_S4: m.uso_S4, regla_origen: m.regla_origen} END) AS marcas
OPTIONAL MATCH (ev)-[:CALCULADO_CON]->(v:Version_Modelo_Difuso)
WITH p, s, e, ev, reglas, marcas, collect(DISTINCT v.id) AS versiones
OPTIONAL MATCH (ev)-[:RESPALDADO_POR]->(x:Evidencia)
WITH p, s, e, ev, reglas, marcas, versiones,
     collect(DISTINCT x {.id, .tipo, .valor, .valor_min, .valor_max, .detalle}) AS evidencias
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(c:Categoria)
RETURN {
  puesto: p.id, servicio: s.nombre, urgencia: p.urgencia_categoria, urgencia_estado: p.urgencia_estado,
  grados_urgencia: {baja: p.grado_urgencia_baja, media: p.grado_urgencia_media, alta: p.grado_urgencia_alta},
  legajo: e.id, empleado: e.nombre, evaluacion: ev.id, estado_S2: ev.estado_S2,
  motivos_descarte: ev.motivos_descarte,
  entradas: {
    cercania: {min: ev.cerc_min, max: ev.cerc_max, estado: ev.cerc_estado, unidad: 'min'},
    experiencia: {min: ev.exp_min, max: ev.exp_max, estado: ev.exp_estado, unidad: 'meses'},
    desempeno: {min: ev.des_min, max: ev.des_max, estado: ev.des_estado, unidad: 'puntaje 1-10'}
  },
  margen_vigencia_dias: ev.margen_vigencia_dias, solape_horario: ev.solape_horario,
  solape_estado: ev.solape_estado,
  afinidad: [ev.grado_afinidad_min, ev.grado_afinidad_max], confiabilidad: ev.confiabilidad,
  termino_dominante: ev.termino_dominante, marca_transicion: ev.marca_transicion,
  categoria_S4: c.nombre, prioridad_S4: ev.prioridad_recomendacion,
  reglas_activadas: reglas, marcas: marcas, versiones: versiones, evidencias: evidencias
} AS detalle;

// ---- S3-comparar
UNWIND $legajos AS legajo
MATCH (p:Puesto_Vacante {id: $puesto}), (e:Empleado {id: legajo})
OPTIONAL MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p), (ev)-[:REFIERE_A]->(e)
OPTIONAL MATCH (:Listado_Final)-[inc:INCLUYE]->(ev)
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(cat:Categoria)
OPTIONAL MATCH (ev)-[:TIENE_MARCA]->(m:MarcaCalidadDato)
WITH p, e, ev, inc, cat, tc, collect(DISTINCT m.codigo) AS marcas
OPTIONAL MATCH (ev)-[:RESPALDADO_POR]->(x:Evidencia)
WITH p, e, ev, inc, cat, tc, marcas,
     collect(DISTINCT x {.id, .tipo, .valor, .valor_min, .valor_max, .detalle}) AS evidencias
WITH p, collect({
       legajo: e.id, empleado: e.nombre, evaluacion: ev.id, estado_S2: ev.estado_S2,
       motivos_descarte: ev.motivos_descarte, categoria_S4: cat.nombre, prioridad_S4: tc.prioridad,
       afinidad: [ev.grado_afinidad_min, ev.grado_afinidad_max], confiabilidad: ev.confiabilidad,
       posicion_por_afinidad: inc.posicion_afinidad, posicion_por_prioridad: inc.posicion_prioridad,
       marcas: marcas, evidencias: evidencias }) AS candidatos
OPTIONAL MATCH camino = (a:EvaluacionEmpleadoPuesto)-[:PRECEDE_A*1..5]->(b:EvaluacionEmpleadoPuesto)
WHERE a.id IN [c IN candidatos | c.evaluacion] AND b.id IN [c IN candidatos | c.evaluacion]
RETURN {
  puesto: p.id, urgencia_estado: p.urgencia_estado, candidatos: candidatos,
  precede: CASE WHEN camino IS NULL THEN null ELSE nodes(camino)[0].id END,
  estados_camino: CASE WHEN camino IS NULL THEN [] ELSE [r IN relationships(camino) | r.estado_orden] END
} AS comparacion;

// ---- S4-E-fichas
MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p:Puesto_Vacante {id: $puesto})-[:PERTENECE_A]->(s:Servicio)
MATCH (lf)-[inc:INCLUYE]->(ev:EvaluacionEmpleadoPuesto)-[:REFIERE_A]->(e:Empleado)
WHERE ($legajo IS NULL OR e.id = $legajo)
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(c:Categoria)
WITH lf, p, s, inc, ev, e, c, tc
WHERE ($categoria IS NULL OR c.nombre = $categoria)
  AND ($solo_con_advertencias = false OR size(coalesce(ev.advertencias, [])) > 0)
OPTIONAL MATCH (ev)-[a:ACTIVA]->(r:Regla_Difusa) WHERE r.submodulo = 'S4'
WITH lf, p, s, inc, ev, e, c, tc,
     collect(DISTINCT {regla: r.id, fuerza: a.fuerza}) AS reglas_fz
OPTIONAL MATCH (ev)-[:TIENE_MARCA]->(m:MarcaCalidadDato)
WITH lf, p, s, inc, ev, e, c, tc, reglas_fz, collect(DISTINCT m.codigo) AS marcas
OPTIONAL MATCH (ev)-[:CLASIFICADO_CON]->(v:Version_Modelo_Difuso)
WITH lf, p, s, inc, ev, e, c, tc, reglas_fz, marcas,
     collect(DISTINCT v.id) AS versiones
OPTIONAL MATCH (ev)-[:RESPALDADO_POR]->(x:Evidencia)
WITH lf, p, s, inc, ev, e, c, tc, reglas_fz, marcas, versiones,
     collect(DISTINCT x.id) AS evidencias
OPTIONAL MATCH (ev)-[pr:PRECEDE_A]->(:EvaluacionEmpleadoPuesto)
WITH lf, p, s, inc, ev, e, c, tc, reglas_fz, marcas, versiones, evidencias,
     collect(DISTINCT pr.estado_orden) AS estados_orden
RETURN {
  evaluacion: ev.id, puesto: p.id, servicio: s.nombre, urgencia: p.urgencia_categoria,
  urgencia_indice: p.urgencia_valor,
  zona_origen: p.zona_origen, zona_resolucion: p.zona_resolucion,
  criterio_orden: lf.criterio_orden,
  posicion_por_prioridad: inc.posicion_prioridad, posicion_por_afinidad: inc.posicion_afinidad,
  empleado: e.nombre, legajo: e.id, categoria: c.nombre, regla_corte: tc.regla_corte,
  regla_dominante: ev.regla_dominante,
  reglas_activadas: [q IN reglas_fz WHERE q.regla IS NOT NULL],
  prioridad: tc.prioridad, version_modelo: versiones[0],
  afinidad: [ev.grado_afinidad_min, ev.grado_afinidad_max], confiabilidad: ev.confiabilidad,
  margen_vigencia_dias: ev.margen_vigencia_dias, solape_horario: ev.solape_horario,
  deseables_faltantes: coalesce(ev.deseables_faltantes, []), deseables_estado: ev.deseables_estado,
  deseables_vencidos: coalesce(ev.deseables_vencidos, []),
  advertencias: coalesce(ev.advertencias, []), advertencias_estado: ev.advertencias_estado,
  marca_transicion: ev.marca_transicion, marcas: marcas,
  estado_orden_con_siguiente: estados_orden[0],
  evidencias_disponibles: evidencias
} AS ficha
ORDER BY ficha.posicion_por_prioridad;

// ---- S4-C-traza
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})-[:REFIERE_A]->(e:Empleado)
OPTIONAL MATCH (e)-[:TIENE_EVALUACION]->(ed:Evaluacion_Desempeno)
WITH ev, e, collect(DISTINCT {fecha: toString(ed.fecha), puntaje: ed.puntaje}) AS evaluaciones
RETURN {
  evaluacion: ev.id, legajo: e.id, empleado: e.nombre,
  evaluaciones: [q IN evaluaciones WHERE q.fecha IS NOT NULL],
  traslado: {min: ev.cerc_min, max: ev.cerc_max, estado: ev.cerc_estado},
  experiencia: {min: ev.exp_min, max: ev.exp_max, estado: ev.exp_estado},
  desempeno: {min: ev.des_min, max: ev.des_max, estado: ev.des_estado}
} AS traza;

// ---- S4-1-descartes
MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p:Puesto_Vacante {id: $puesto})
MATCH (ev)-[:REFIERE_A]->(e:Empleado)
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(c:Categoria)
RETURN ev.id AS evaluacion, e.id AS legajo, e.nombre AS empleado,
       ev.estado_S2 AS estado_S2, coalesce(ev.motivos_descarte, []) AS motivos_descarte,
       coalesce(ev.deseables_faltantes, []) AS deseables_faltantes,
       ev.deseables_estado AS deseables_estado,
       c.nombre AS categoria, tc.regla_corte AS regla_corte
ORDER BY legajo;

// ---- S4-5-listado-vacio
MATCH (p:Puesto_Vacante {id: $puesto})-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p)
OPTIONAL MATCH (s)-[:ES_DE_TIPO]->(ts:Tipo_Servicio)
OPTIONAL MATCH (p)-[rq:REQUIERE]->(a:Aptitud)
WITH p, s, lf, ts, collect(DISTINCT CASE WHEN a IS NULL THEN null ELSE
       {aptitud: a.nombre, excluyente: rq.excluyente, origen: 'pedido',
        regla: coalesce(rq.regla, 'S1-R02')} END) AS del_pedido
OPTIONAL MATCH (ts)-[:EXIGE]->(a2:Aptitud)
WITH p, s, lf, ts, del_pedido, collect(DISTINCT CASE WHEN a2 IS NULL THEN null ELSE
       {aptitud: a2.nombre, excluyente: true, origen: 'catálogo del tipo de servicio ' + ts.nombre,
        regla: 'S2-R01'} END) AS del_catalogo
RETURN p.id AS puesto, s.nombre AS servicio, ts.nombre AS tipo_servicio,
       lf.n_candidatos_validos AS validos, lf.n_descartados AS descartados,
       lf.conteo_motivos AS conteo_motivos, lf.motivo_critico AS motivo_critico,
       [q IN del_pedido WHERE q IS NOT NULL] AS del_pedido,
       [q IN del_catalogo WHERE q IS NOT NULL] AS del_catalogo,
       p.urgencia_categoria AS urgencia, p.urgencia_estado AS urgencia_estado;

// ---- S4-F-fidelidad
UNWIND $citadas AS c
OPTIONAL MATCH (:EvaluacionEmpleadoPuesto {id: $evaluacion})-[:RESPALDADO_POR]->(e:Evidencia {id: c.evidencia})
RETURN c.evidencia AS evidencia_citada, e IS NOT NULL AS pertenece_al_candidato,
       CASE WHEN e IS NULL THEN null
            WHEN e.tipo = 'afinidad' THEN abs((e.valor_min + e.valor_max) / 2.0 - c.valor) < 0.0005
            WHEN e.valor IS NULL AND c.valor IS NOT NULL THEN false
            WHEN e.valor IS NULL THEN null
            ELSE abs(e.valor - c.valor) < 0.0005 END AS valor_coincide;

// ---- S4-EV-evidencias
MATCH (ev:EvaluacionEmpleadoPuesto)-[:RESPALDADO_POR]->(x:Evidencia)
WHERE ev.id IN $evaluaciones
RETURN ev.id AS evaluacion, x {.id, .tipo, .valor, .valor_min, .valor_max, .detalle} AS evidencia;

// ---- S4-G-glosario
MATCH (n) WHERE (n:Regla_Difusa OR n:Regla_Crisp OR n:MarcaCalidadDato)
  AND coalesce(n.id, n.codigo) IN $ids
RETURN coalesce(n.id, n.codigo) AS id, labels(n)[0] AS tipo,
       {enunciado: n.enunciado, antecedente: n.antecedente, consecuente: n.consecuente,
        proposito: n.proposito, descripcion: n.descripcion, uso_S4: n.uso_S4,
        regla_origen: n.regla_origen} AS propiedades;

// ---- PG3-evaluaciones-del-puesto
MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p:Puesto_Vacante {id: $puesto})
MATCH (ev)-[:REFIERE_A]->(e:Empleado)
RETURN ev.id AS evaluacion, e.id AS legajo, e.nombre AS empleado,
       ev.estado_S2 AS estado_S2, coalesce(ev.motivos_descarte, []) AS motivos_descarte,
       ev.cerc_min AS cerc_min, ev.cerc_max AS cerc_max, ev.cerc_estado AS cerc_estado,
       ev.exp_min AS exp_min, ev.exp_max AS exp_max, ev.exp_estado AS exp_estado,
       ev.des_min AS des_min, ev.des_max AS des_max, ev.des_estado AS des_estado,
       ev.margen_vigencia_dias AS margen_vigencia_dias,
       ev.solape_horario AS solape_horario, ev.solape_estado AS solape_estado,
       coalesce(ev.advertencias, []) AS advertencias, ev.advertencias_estado AS advertencias_estado,
       coalesce(ev.deseables_faltantes, []) AS deseables_faltantes,
       coalesce(ev.deseables_vencidos, []) AS deseables_vencidos,
       p.grado_urgencia_baja AS u_baja, p.grado_urgencia_media AS u_media,
       p.grado_urgencia_alta AS u_alta, p.urgencia_categoria AS urgencia
ORDER BY legajo;

// ---- PG3-esquema
CALL db.labels() YIELD label
RETURN collect(label) AS etiquetas;

// ---- PG3-esquema-rel
CALL db.relationshipTypes() YIELD relationshipType
RETURN collect(relationshipType) AS relaciones;

// ---- PG3-entradas-por-empleado
MATCH (ev:EvaluacionEmpleadoPuesto)-[:REFIERE_A]->(e:Empleado)
WHERE ev.origen IS NULL OR ev.origen <> 'PG3'
WITH e,
     collect(DISTINCT CASE WHEN ev.exp_estado = 'OBSERVADO' THEN ev.exp_min END) AS exp,
     collect(DISTINCT CASE WHEN ev.des_estado = 'OBSERVADO' THEN ev.des_min END) AS des,
     collect(DISTINCT ev.exp_estado) AS exp_estados,
     collect(DISTINCT ev.des_estado) AS des_estados
RETURN e.id AS legajo, e.nombre AS nombre,
       e.experiencia_meses AS experiencia_ya_en_empleado,
       e.desempeno_reciente AS desempeno_ya_en_empleado,
       [x IN exp WHERE x IS NOT NULL] AS experiencias,
       [x IN des WHERE x IS NOT NULL] AS desempenos,
       [x IN exp_estados WHERE x IS NOT NULL] AS exp_estados,
       [x IN des_estados WHERE x IS NOT NULL] AS des_estados
ORDER BY legajo;

// ---- PG3-export-nodos
MATCH (n)
RETURN elementId(n) AS id, labels(n) AS etiquetas, properties(n) AS props
ORDER BY etiquetas[0], id;

// ---- PG3-export-relaciones
MATCH (a)-[r]->(b)
RETURN elementId(a) AS desde, elementId(b) AS hasta, type(r) AS tipo, properties(r) AS props
ORDER BY tipo;

// ---- PG3-parametros-difusos
MATCH (v:Variable_Linguistica)
OPTIONAL MATCH (v)-[:TIENE_TERMINO]->(t)
OPTIONAL MATCH (t)-[:DEFINIDO_POR]->(f:Funcion_Pertenencia)
RETURN v.nombre AS variable, v.submodulo AS submodulo,
       collect(DISTINCT {termino: t.nombre, forma: f.forma, centro: f.centro,
                         sigma: f.sigma, lado: f.lado, version: f.version}) AS terminos
ORDER BY variable;

// ---- PG3-datos-de-prueba
MATCH (p:Puesto_Vacante) WHERE p.origen = 'PG3'
OPTIONAL MATCH (ped:Pedido_Cobertura)-[:GENERA]->(p)
OPTIONAL MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p)
OPTIONAL MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p)
RETURN p.id AS puesto, ped.id AS pedido, toString(p.fecha_evaluacion) AS fecha,
       count(DISTINCT ev) AS evaluaciones, count(DISTINCT lf) AS listados
ORDER BY puesto;

// ---- PG3-estado-actual
MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p:Puesto_Vacante {id: $puesto})
MATCH (ev)-[:REFIERE_A]->(e:Empleado)
OPTIONAL MATCH (ev)-[tc:TIENE_CATEGORIA]->(c:Categoria)
OPTIONAL MATCH (:Listado_Final)-[inc:INCLUYE]->(ev)
RETURN e.id AS legajo, e.nombre AS empleado, ev.id AS evaluacion,
       ev.estado_S2 AS estado_S2,
       ev.grado_afinidad_min AS amin, ev.grado_afinidad_max AS amax,
       ev.confiabilidad AS confiabilidad,
       coalesce(tc.prioridad, ev.prioridad_recomendacion) AS prioridad,
       c.nombre AS categoria, ev.regla_dominante AS regla_dominante,
       inc.posicion_prioridad AS posicion
ORDER BY coalesce(inc.posicion_prioridad, 99), legajo;

// ---- PG3-propiedades
CALL db.propertyKeys() YIELD propertyKey
RETURN collect(propertyKey) AS propiedades;

// ---- PG3-propiedades-de
MATCH (n) WHERE $etiqueta IN labels(n)
WITH keys(n) AS ks LIMIT 200
UNWIND ks AS k
RETURN collect(DISTINCT k) AS propiedades;

// ---- PG3-relaciones-de
MATCH (a)-[r]->(b)
RETURN labels(a)[0] AS origen, type(r) AS relacion, labels(b)[0] AS destino,
       count(*) AS cantidad
ORDER BY origen, relacion, destino;

// ---- PG3-conteos
MATCH (n) UNWIND labels(n) AS l
RETURN l AS etiqueta, count(*) AS cantidad ORDER BY etiqueta;

// ==============================================================================
// ESCRITURA (plantillas fijas: registran pedido, puesto, evaluaciones, afinidad, categoría, evidencias y listado) (18 sentencias)
// ==============================================================================

// ---- W-S1-pedido
MERGE (ped:Pedido_Cobertura {id: $pedido_id})
SET ped.texto = $texto, ped.estado = $estado, ped.fecha = datetime($fecha),
    ped.campos_faltantes = $campos_faltantes, ped.origen = 'PG3'
RETURN ped.id AS pedido;

// ---- W-S1-puesto
MATCH (ped:Pedido_Cobertura {id: $pedido_id})
MATCH (s:Servicio {nombre: $servicio})
MATCH (t:Turno {nombre: $turno})
MATCH (z:Zona {nombre: $zona})
MERGE (p:Puesto_Vacante {id: $puesto_id})
SET p.urgencia_categoria = $urgencia_categoria,
    p.urgencia_valor = $urgencia_valor,
    p.urgencia_estado = $urgencia_estado,
    p.grado_urgencia_baja = $u_baja,
    p.grado_urgencia_media = $u_media,
    p.grado_urgencia_alta = $u_alta,
    p.version_modelo_urgencia = $version_urgencia,
    p.radio_extendido = $radio_extendido,
    p.experiencia_minima_meses = $experiencia_meses,
    p.zona_origen = $zona_origen,
    p.zona_resolucion = $zona_resolucion,
    p.zona_regla = 'S1-R07',
    p.fecha_evaluacion = date($fecha_evaluacion),
    p.origen = 'PG3'
MERGE (ped)-[:GENERA]->(p)
MERGE (p)-[:PERTENECE_A]->(s)
MERGE (p)-[:EN_TURNO]->(t)
MERGE (p)-[:EN_ZONA]->(z)
RETURN p.id AS puesto;

// ---- W-S1-requisito
MATCH (p:Puesto_Vacante {id: $puesto_id})
MATCH (a:Aptitud {nombre: $aptitud})
MERGE (p)-[r:REQUIERE]->(a)
SET r.excluyente = $excluyente, r.marcador = $marcador, r.regla = $regla,
    r.origen = 'pedido', r.fuente = $fuente,
    r.estado_validacion = $estado_validacion,
    r.fue_inferido_o_declarado = $fue_inferido_o_declarado
RETURN a.nombre AS aptitud;

// ---- W-S2-evaluacion
MATCH (p:Puesto_Vacante {id: $puesto})
MATCH (e:Empleado {id: $legajo})
MERGE (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
SET ev.estado_S2 = $estado_S2,
    ev.motivos_descarte = $motivos_descarte,
    ev.deseables_faltantes = $deseables_faltantes,
    ev.deseables_vencidos = $deseables_vencidos,
    ev.deseables_estado = $deseables_estado,
    ev.margen_vigencia_dias = $margen_vigencia_dias,
    ev.solape_horario = $solape_horario,
    ev.solape_estado = $solape_estado,
    ev.cerc_min = $cerc_min, ev.cerc_max = $cerc_max, ev.cerc_estado = $cerc_estado,
    ev.exp_min = $exp_min, ev.exp_max = $exp_max, ev.exp_estado = $exp_estado,
    ev.des_min = $des_min, ev.des_max = $des_max, ev.des_estado = $des_estado,
    ev.advertencias = $advertencias, ev.advertencias_estado = $advertencias_estado,
    ev.fecha_evaluacion = date($fecha_evaluacion),
    ev.origen = 'PG3'
MERGE (ev)-[:PARA]->(p)
MERGE (ev)-[:REFIERE_A]->(e)
RETURN ev.id AS evaluacion;

// ---- W-S3-afinidad
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
SET ev.grado_afinidad_min = $afinidad_min,
    ev.grado_afinidad_max = $afinidad_max,
    ev.confiabilidad = $confiabilidad,
    ev.termino_dominante = $termino_dominante
WITH ev
MERGE (v:Version_Modelo_Difuso {id: $version})
MERGE (ev)-[:CALCULADO_CON]->(v)
RETURN ev.id AS evaluacion;

// ---- W-S3-reglas-activadas
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
UNWIND $reglas AS fila
OPTIONAL MATCH (r:Regla_Difusa {id: fila.regla})
FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END |
  MERGE (ev)-[a:ACTIVA]->(r) SET a.fuerza = fila.fuerza)
RETURN count(r) AS vinculadas;

// ---- W-S4-categoria
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
SET ev.prioridad_recomendacion = $prioridad,
    ev.regla_dominante = $regla_dominante,
    ev.marca_transicion = $marca_transicion
WITH ev
MATCH (c:Categoria {nombre: $categoria})
MERGE (ev)-[tc:TIENE_CATEGORIA]->(c)
SET tc.prioridad = $prioridad, tc.regla_corte = $regla_corte
WITH ev
MERGE (v:Version_Modelo_Difuso {id: $version})
MERGE (ev)-[:CLASIFICADO_CON]->(v)
RETURN ev.id AS evaluacion;

// ---- W-S4-marcas
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
UNWIND $marcas AS fila
MERGE (m:MarcaCalidadDato {codigo: fila.codigo})
ON CREATE SET m.uso_S4 = fila.uso_S4, m.descripcion = fila.descripcion,
              m.regla_origen = fila.regla_origen
MERGE (ev)-[:TIENE_MARCA]->(m)
RETURN count(m) AS marcas;

// ---- W-S4-evidencias
MATCH (ev:EvaluacionEmpleadoPuesto {id: $evaluacion})
UNWIND $evidencias AS fila
MERGE (x:Evidencia {id: fila.id})
SET x.tipo = fila.tipo, x.valor = fila.valor, x.valor_min = fila.valor_min,
    x.valor_max = fila.valor_max, x.detalle = fila.detalle
MERGE (ev)-[:RESPALDADO_POR]->(x)
RETURN count(x) AS evidencias;

// ---- W-S4-listado
MATCH (p:Puesto_Vacante {id: $puesto})
MERGE (lf:Listado_Final {id: $listado})
SET lf.criterio_orden = $criterio_orden,
    lf.criterio_desempate = $criterio_desempate,
    lf.n_candidatos_validos = $n_validos,
    lf.n_descartados = $n_descartados,
    lf.conteo_motivos = $conteo_motivos,
    lf.motivo_critico = $motivo_critico,
    lf.version_modelo = $version,
    lf.fecha = datetime($fecha)
MERGE (lf)-[:REFERIDO_A]->(p)
RETURN lf.id AS listado;

// ---- W-S4-incluye
MATCH (lf:Listado_Final {id: $listado})
UNWIND $posiciones AS fila
MATCH (ev:EvaluacionEmpleadoPuesto {id: fila.evaluacion})
MERGE (lf)-[i:INCLUYE]->(ev)
SET i.posicion_afinidad = fila.posicion_afinidad, i.posicion_prioridad = fila.posicion_prioridad
RETURN count(ev) AS incluidos;

// ---- W-S4-precede
MATCH (a:EvaluacionEmpleadoPuesto {id: $anterior})
MATCH (b:EvaluacionEmpleadoPuesto {id: $siguiente})
MERGE (a)-[r:PRECEDE_A]->(b)
SET r.estado_orden = $estado_orden, r.diferencia = $diferencia
RETURN r.estado_orden AS estado_orden;

// ---- W-PG3-limpiar-listado
MATCH (lf:Listado_Final)-[:REFERIDO_A]->(:Puesto_Vacante {id: $puesto})
OPTIONAL MATCH (lf)-[i:INCLUYE]->(ev:EvaluacionEmpleadoPuesto)
OPTIONAL MATCH (ev)-[pr:PRECEDE_A]->(:EvaluacionEmpleadoPuesto)
DELETE i, pr
RETURN count(lf) AS listados;

// ---- W-PG3-borrar-pruebas
MATCH (p:Puesto_Vacante) WHERE p.origen = 'PG3'
OPTIONAL MATCH (ped:Pedido_Cobertura)-[:GENERA]->(p)
OPTIONAL MATCH (ev:EvaluacionEmpleadoPuesto)-[:PARA]->(p)
OPTIONAL MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p)
OPTIONAL MATCH (ev)-[:RESPALDADO_POR]->(x:Evidencia)
DETACH DELETE x, ev, lf, p, ped
RETURN count(*) AS borrados;

// ---- W-PG3-normalizar-empleado
MATCH (e:Empleado {id: $legajo})
SET e.experiencia_meses = $experiencia,
    e.desempeno_reciente = $desempeno,
    e.entradas_origen = 'promovidas desde las evaluaciones del PG2 (PG3)',
    e.entradas_estado_validacion = 'provisional'
RETURN e.id AS legajo;

// ---- W-PG3-funcion-pertenencia
MERGE (v:Variable_Linguistica {nombre: $variable})
SET v.submodulo = $submodulo, v.universo_min = $umin, v.universo_max = $umax,
    v.unidad = $unidad
MERGE (t:Termino {id: $variable + ':' + $termino})
SET t.nombre = $termino
MERGE (v)-[:TIENE_TERMINO]->(t)
MERGE (f:Funcion_Pertenencia {id: $variable + ':' + $termino + ':' + $version})
SET f.forma = $forma, f.centro = $centro, f.sigma = $sigma, f.lado = $lado,
    f.centro2 = $centro2, f.sigma2 = $sigma2,
    f.version = $version, f.estado_validacion = 'provisional',
    f.fuente = 'motor_difuso.py del PG2, verificado contra los PI3'
MERGE (t)-[:DEFINIDO_POR]->(f)
RETURN t.nombre AS termino;

// ---- W-PG3-borrar-variable
MATCH (v:Variable_Linguistica {nombre: $variable})-[:TIENE_TERMINO]->(t:Termino)
MATCH (t)-[:DEFINIDO_POR]->(f:Funcion_Pertenencia)
WHERE f.fuente = 'motor_difuso.py del PG2, verificado contra los PI3'
WITH v, collect(DISTINCT t) AS terminos, collect(DISTINCT f) AS funciones
FOREACH (x IN funciones | DETACH DELETE x)
FOREACH (x IN terminos | DETACH DELETE x)
WITH v WHERE NOT (v)-[:TIENE_TERMINO]->()
DETACH DELETE v
RETURN count(*) AS borradas;

// ---- W-PG3-categorias-base
UNWIND ['Recomendado', 'Recomendado_con_reservas', 'Baja_prioridad'] AS nombre
MERGE (c:Categoria {nombre: nombre})
RETURN collect(c.nombre) AS categorias;
