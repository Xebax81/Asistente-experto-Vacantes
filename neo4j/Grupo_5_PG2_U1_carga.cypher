// Grupo 5 - 5K10 - PG2 - Base de conocimiento en Neo4j (carga completa, borrador)
// Asistente Experto para Recomendacion de Personal en Cobertura de Vacantes Internas
// Ejecutar en Neo4j Browser (Neo4j 5.x o superior). Cada sentencia termina en ';'.
// Datos de casos SIMULADOS. Todos los parametros son provisionales (sin validar con RR. HH.).

// ==============================================================================
// 0. LIMPIEZA INICIAL
// ==============================================================================
MATCH (n) DETACH DELETE n;

// ==============================================================================
// 1. RESTRICCIONES DE UNICIDAD
// ==============================================================================
CREATE CONSTRAINT c_empleado IF NOT EXISTS FOR (n:Empleado) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_puesto_vacante IF NOT EXISTS FOR (n:Puesto_Vacante) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_pedido_cobertura IF NOT EXISTS FOR (n:Pedido_Cobertura) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_servicio IF NOT EXISTS FOR (n:Servicio) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_tipo_servicio IF NOT EXISTS FOR (n:Tipo_Servicio) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_aptitud IF NOT EXISTS FOR (n:Aptitud) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_zona IF NOT EXISTS FOR (n:Zona) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_turno IF NOT EXISTS FOR (n:Turno) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_nivel_urgencia IF NOT EXISTS FOR (n:Nivel_Urgencia) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_evaluacionempleadopuesto IF NOT EXISTS FOR (n:EvaluacionEmpleadoPuesto) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_ranking IF NOT EXISTS FOR (n:Ranking) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_marcacalidaddato IF NOT EXISTS FOR (n:MarcaCalidadDato) REQUIRE n.codigo IS UNIQUE;
CREATE CONSTRAINT c_termino_linguistico IF NOT EXISTS FOR (n:Termino_Linguistico) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_funcion_pertenencia IF NOT EXISTS FOR (n:Funcion_Pertenencia) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_regla_difusa IF NOT EXISTS FOR (n:Regla_Difusa) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_regla_crisp IF NOT EXISTS FOR (n:Regla_Crisp) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_variable_linguistica IF NOT EXISTS FOR (n:Variable_Linguistica) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_frame IF NOT EXISTS FOR (n:Frame) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_version_modelo_difuso IF NOT EXISTS FOR (n:Version_Modelo_Difuso) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_categoria IF NOT EXISTS FOR (n:Categoria) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT c_listado_final IF NOT EXISTS FOR (n:Listado_Final) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_evidencia IF NOT EXISTS FOR (n:Evidencia) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_evaluacion_desempeno IF NOT EXISTS FOR (n:Evaluacion_Desempeno) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_traslado IF NOT EXISTS FOR (n:Traslado) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_expresion_urgencia IF NOT EXISTS FOR (n:Expresion_Urgencia) REQUIRE n.texto IS UNIQUE;
CREATE CONSTRAINT c_grupo_reglas IF NOT EXISTS FOR (n:Grupo_Reglas) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT c_actor IF NOT EXISTS FOR (n:Actor) REQUIRE n.id IS UNIQUE;

// ==============================================================================
// 2. FRAMES (clases del modelo). Cada instancia se enlaza con INSTANCIA_DE al final del script
// ==============================================================================
UNWIND [
  {nombre: 'Actor', tipo: 'abstracta', hereda: null, modulo: 'S1', slots: ['nombre', 'rol']},
  {nombre: 'Pedido_Cobertura', tipo: 'concreta', hereda: null, modulo: 'S1', slots: ['canal', 'texto_original', 'estado', 'campos_faltantes', 'urgencia_textual']},
  {nombre: 'Puesto_Vacante', tipo: 'concreta', hereda: null, modulo: 'S1', slots: ['turno', 'radio_extendido', 'fecha_evaluacion', 'urgencia_categoria', 'urgencia_estado', 'grado_urgencia_*', 'urgencia_valor']},
  {nombre: 'Servicio', tipo: 'concreta', hereda: null, modulo: 'S1', slots: ['nombre', 'alias', 'alias_estado_validacion']},
  {nombre: 'Tipo_Servicio', tipo: 'referencia', hereda: null, modulo: 'S2', slots: ['nombre']},
  {nombre: 'Aptitud', tipo: 'catalogo', hereda: null, modulo: 'S1', slots: ['nombre', 'tipo', 'vence', 'sinonimos']},
  {nombre: 'Zona', tipo: 'referencia', hereda: null, modulo: 'S1', slots: ['nombre']},
  {nombre: 'Turno', tipo: 'referencia', hereda: null, modulo: 'S1', slots: ['nombre', 'horario_inicio', 'horario_fin']},
  {nombre: 'Traslado', tipo: 'concreta', hereda: null, modulo: 'S3', slots: ['minutos', 'estado', 'fuente']},
  {nombre: 'Empleado', tipo: 'concreta', hereda: null, modulo: 'S2', slots: ['id', 'nombre', 'antiguedad_meses']},
  {nombre: 'Evaluacion_Desempeno', tipo: 'concreta', hereda: null, modulo: 'S3', slots: ['fecha', 'puntaje']},
  {nombre: 'EvaluacionEmpleadoPuesto', tipo: 'concreta', hereda: null, modulo: 'S2-S4', slots: ['estado_S2', 'motivos_descarte', 'deseables_faltantes', 'deseables_estado', 'cerc_*', 'exp_*', 'des_*', 'margen_vigencia_dias', 'solape_horario', 'solape_estado', 'grado_afinidad_min', 'grado_afinidad_max', 'termino_dominante', 'afinidad_central', 'confiabilidad', 'prioridad_recomendacion', 'regla_dominante', 'marca_transicion', 'regla_corte', 'advertencias', 'advertencias_estado', 'aptitudes_deseables_estado']},
  {nombre: 'Ranking', tipo: 'concreta', hereda: null, modulo: 'S3', slots: ['puesto', 'candidatos', 'estado_orden']},
  {nombre: 'MarcaCalidadDato', tipo: 'catalogo', hereda: null, modulo: 'S3', slots: ['codigo', 'uso_S4']},
  {nombre: 'Expresion_Urgencia', tipo: 'concreta', hereda: null, modulo: 'S1', slots: ['texto', 'tipo', 'valor', 'unidad', 'fuente', 'estado_validacion']},
  {nombre: 'Nivel_Urgencia', tipo: 'referencia', hereda: null, modulo: 'S1', slots: ['nombre', 'orden']},
  {nombre: 'Version_Modelo_Difuso', tipo: 'parametro', hereda: null, modulo: 'S1-S4', slots: ['id', 'modelo', 'version', 'fecha_desde', 'fecha_hasta', 'vigente', 'estado', 'validado_por', 'umbral_ref_recomendado', 'umbral_ref_reservas', 'corte_recomendado', 'corte_reservas', 'delta_transicion']},
  {nombre: 'Categoria', tipo: 'referencia', hereda: null, modulo: 'S4', slots: ['nombre', 'orden_prioridad']},
  {nombre: 'Listado_Final', tipo: 'concreta', hereda: null, modulo: 'S4', slots: ['puesto', 'criterio_orden', 'criterio_desempate', 'n_candidatos_validos', 'n_descartados', 'motivo_critico']},
  {nombre: 'Evidencia', tipo: 'concreta', hereda: null, modulo: 'S4', slots: ['tipo', 'detalle', 'valor', 'fuente']},
  {nombre: 'Variable_Linguistica', tipo: 'abstracta', hereda: null, modulo: 'S1-S3', slots: ['nombre', 'universo_min', 'universo_max', 'unidad']},
  {nombre: 'Termino_Linguistico', tipo: 'concreta', hereda: null, modulo: 'S1-S3', slots: ['nombre', 'variable']},
  {nombre: 'Funcion_Pertenencia', tipo: 'concreta', hereda: null, modulo: 'S1-S3', slots: ['forma', 'centro', 'sigma', 'hombro', 'c1', 's1', 'c2', 's2', 'a', 'b', 'c', 'd', 'version', 'vigente', 'estado', 'fuente']},
  {nombre: 'Regla_Difusa', tipo: 'concreta', hereda: null, modulo: 'S1-S3', slots: ['id', 'grupo', 'antecedente', 'consecuente', 'peso']},
  {nombre: 'Regla_Crisp', tipo: 'concreta', hereda: null, modulo: 'S1-S4', slots: ['id', 'modulo', 'enunciado', 'tipo']},
  {nombre: 'Grupo_Reglas', tipo: 'concreta', hereda: null, modulo: 'S1-S4', slots: ['id', 'aplica_si', 'implicacion', 'agregacion']}
] AS f
MERGE (n:Frame {nombre: f.nombre})
SET n.tipo = f.tipo, n.hereda_de = f.hereda, n.submodulo = f.modulo, n.slots = f.slots;

// ==============================================================================
// 3. CATALOGOS COMPARTIDOS (Zona, Turno, Tipo_Servicio, Aptitud, Nivel_Urgencia, Umbral, MarcaCalidadDato)
// ==============================================================================
UNWIND ['Capital','Godoy Cruz','Guaymallén','Las Heras','Luján de Cuyo','Maipú'] AS z MERGE (:Zona {nombre: z});
UNWIND [{n:'mañana',i:time('06:00'),f:time('14:00')},{n:'tarde',i:time('14:00'),f:time('22:00')},{n:'noche',i:time('22:00'),f:time('06:00')}] AS t MERGE (x:Turno {nombre: t.n}) SET x.horario_inicio = t.i, x.horario_fin = t.f;
UNWIND ['hospitalario','industrial','comercial','oficinas'] AS t MERGE (:Tipo_Servicio {nombre: t});
UNWIND [{n:'baja',o:1},{n:'media',o:2},{n:'alta',o:3}] AS x MERGE (:Nivel_Urgencia {nombre: x.n, orden: x.o});
UNWIND [
  {n: 'limpieza_hospitalaria', t: 'certificacion', v: true},
  {n: 'manejo_residuos_patogenicos', t: 'certificacion', v: true},
  {n: 'manejo_maquinaria_industrial', t: 'habilidad', v: false},
  {n: 'trabajo_en_altura', t: 'certificacion', v: true}
] AS a
MERGE (x:Aptitud {nombre: a.n}) SET x.tipo = a.t, x.vence = a.v;
UNWIND [{n:'Recomendado',o:1},{n:'Recomendado_con_reservas',o:2},{n:'Baja_prioridad',o:3}] AS c MERGE (x:Categoria {nombre: c.n}) SET x.orden_prioridad = c.o, x.submodulo = 'S4';
UNWIND [
  {id: 'S1-v0.1', modelo: 'S1', version: '0.1', desde: null, hasta: null, vigente: true, estado: 'provisional', fuente: 'PI3 S1 (Arguello)'},
  {id: 'S2-v0.1', modelo: 'S2', version: '0.1', desde: null, hasta: null, vigente: true, estado: 'provisional', fuente: 'PI3 S2 (Cayo)'},
  {id: 'S3-v0.2', modelo: 'S3', version: '0.2', desde: null, hasta: date('2026-10-05'), vigente: false, estado: 'reemplazada', fuente: 'PI1/PI2 S3 (Gallardo): trapecios de urgencia y desempeño'},
  {id: 'S3-v0.3', modelo: 'S3', version: '0.3', desde: date('2026-10-05'), hasta: null, vigente: true, estado: 'provisional', fuente: 'PI3 S3 (Gallardo): gaussianas con sigma derivado de fronteras con mu = 0,5'},
  {id: 'S4-FZ-v1', modelo: 'S4', version: '1', desde: date('2026-10-05'), hasta: null, vigente: true, estado: 'politica_candidata', fuente: 'PI3 S4 (León)'}
] AS v
MERGE (x:Version_Modelo_Difuso {id: v.id}) SET x.modelo = v.modelo, x.version = v.version, x.fecha_desde = v.desde, x.fecha_hasta = v.hasta, x.vigente = v.vigente, x.estado = v.estado, x.fuente = v.fuente, x.validado_por = null, x.fechas_simuladas = true;
MATCH (n:Version_Modelo_Difuso {id: 'S3-v0.3'}), (a:Version_Modelo_Difuso {id: 'S3-v0.2'}) MERGE (n)-[:REEMPLAZA]->(a);
MATCH (x:Version_Modelo_Difuso {id: 'S4-FZ-v1'}) SET x.umbral_ref_recomendado = 0.70, x.umbral_ref_reservas = 0.40, x.corte_recomendado = 0.610, x.corte_reservas = 0.367, x.delta_transicion = 0.20, x.calibracion = 'calibrar_cortes() de motor_difuso.py: prioridad(afinidad 0,70 / 0,40; confiabilidad 1; sin advertencias)';
UNWIND [
  {c: 'URGENCIA_ESTIMADA', u: 'informativa', r: 'S3-R06'},
  {c: 'URGENCIA_DESCONOCIDA', u: 'pedir_dato', r: 'S3-R02'},
  {c: 'TRASLADO_ESTIMADO', u: 'informativa', r: 'S3-R07'},
  {c: 'TRASLADO_DESCONOCIDO', u: 'advertencia', r: 'S3-R08'},
  {c: 'DESEMPEÑO_DESCONOCIDO', u: 'advertencia', r: 'S3-R09'},
  {c: 'DESEMPEÑO_BAJO_RECIENTE', u: 'advertencia', r: 'S3-R04'},
  {c: 'SERVICIO_FUERA_DE_MATRIZ', u: 'pedir_dato', r: 'S3-R11'},
  {c: 'HORARIO_DESCONOCIDO', u: 'advertencia', r: 'S2-R10'},
  {c: 'ORDEN_NO_DETERMINADO', u: 'pedir_dato', r: 'S3-R10'},
  {c: 'EMPATE_TECNICO', u: 'informativa', r: 'S3-R03'},
  {c: 'AFINIDAD_EN_TRANSICION', u: 'informativa', r: 'S4-FZ'},
  {c: 'SIN_CANDIDATO_PLENO', u: 'informativa', r: 'S3-R05'}
] AS m
MERGE (x:MarcaCalidadDato {codigo: m.c}) SET x.uso_S4 = m.u, x.regla_origen = m.r, x.submodulo = CASE WHEN m.c = 'AFINIDAD_EN_TRANSICION' THEN 'S4' ELSE 'S3' END;

// ==============================================================================
// 4. RELACIONES ENTRE CATALOGOS (CERCANA_A, LINDA_CON, EXIGE, SIMILAR_A)
// ==============================================================================
UNWIND [['Capital','Guaymallén'],['Capital','Godoy Cruz'],['Godoy Cruz','Luján de Cuyo'],['Luján de Cuyo','Maipú']] AS p
MATCH (a:Zona {nombre: p[0]}), (b:Zona {nombre: p[1]})
MERGE (a)-[r:CERCANA_A]->(b) SET r.fuente = 'PI2 S2 (casos de uso)', r.estado_validacion = 'provisional', r.submodulo = 'S2';
UNWIND [['Capital','Godoy Cruz'],['Capital','Guaymallén'],['Luján de Cuyo','Maipú']] AS p
MATCH (a:Zona {nombre: p[0]}), (b:Zona {nombre: p[1]})
MERGE (a)-[r:LINDA_CON]->(b) SET r.fuente = 'PI2 S3 (casos de uso)', r.estado_validacion = 'provisional', r.submodulo = 'S3';
UNWIND [['hospitalario','limpieza_hospitalaria'],['industrial','manejo_maquinaria_industrial']] AS p
MATCH (t:Tipo_Servicio {nombre: p[0]}), (a:Aptitud {nombre: p[1]})
MERGE (t)-[r:EXIGE]->(a) SET r.origen = 'catalogo a confirmar con manual de perfiles', r.estado_validacion = 'provisional', r.submodulo = 'S2';
UNWIND [{o:'industrial',d:'hospitalario',v:0.5},{o:'comercial',d:'hospitalario',v:0.4},{o:'hospitalario',d:'oficinas',v:0.6},{o:'oficinas',d:'hospitalario',v:0.3}] AS s
MATCH (a:Tipo_Servicio {nombre: s.o}), (b:Tipo_Servicio {nombre: s.d})
MERGE (a)-[r:SIMILAR_A]->(b) SET r.valor = s.v, r.fuente = 'PI2 S3 (valores publicados; completar matriz de PI1)', r.estado_validacion = 'provisional', r.submodulo = 'S3';

// ==============================================================================
// 5. SERVICIOS Y TRASLADOS
// ==============================================================================
UNWIND [
  {n: 'Hospital Central', t: 'hospitalario', z: 'Capital', al: ['hospital central', 'hosp central']},
  {n: 'Clínica Luján', t: 'hospitalario', z: 'Luján de Cuyo', al: ['la clinica']},
  {n: 'Fábrica Sur', t: 'industrial', z: 'Maipú', al: ['la fabrica']},
  {n: 'Supermercado Norte', t: 'comercial', z: 'Godoy Cruz', al: ['el super']}
] AS s
MATCH (t:Tipo_Servicio {nombre: s.t}), (z:Zona {nombre: s.z})
MERGE (x:Servicio {nombre: s.n}) SET x.alias = s.al, x.alias_estado_validacion = 'provisional'
MERGE (x)-[:ES_DE_TIPO]->(t)
MERGE (x)-[:EN_ZONA]->(z);
UNWIND [{id:'TR-01',z:'Guaymallén',s:'Hospital Central',m:30},{id:'TR-02',z:'Capital',s:'Hospital Central',m:10},{id:'TR-03',z:'Luján de Cuyo',s:'Clínica Luján',m:12}] AS t
MATCH (z:Zona {nombre: t.z}), (s:Servicio {nombre: t.s})
MERGE (x:Traslado {id: t.id}) SET x.minutos = t.m, x.estado = 'OBSERVADO', x.fuente = 'simulado'
MERGE (z)-[:ORIGEN_DE]->(x) MERGE (x)-[:HACIA]->(s);

// ==============================================================================
// 6. EMPLEADOS, APTITUDES, DISPONIBILIDAD, SERVICIOS PREVIOS Y EVALUACIONES (datos simulados)
// ==============================================================================
UNWIND [
  {id: 'E101', n: 'Ana Pérez', a: 18},
  {id: 'E102', n: 'Bruno Gómez', a: 30},
  {id: 'E103', n: 'Carla Díaz', a: 12},
  {id: 'E104', n: 'Diego Ruiz', a: 40},
  {id: 'E401', n: 'Valeria Núñez', a: 4},
  {id: 'E402', n: 'Tomás Aguirre', a: 30},
  {id: 'E105', n: 'Elena Sosa', a: 10}
] AS e
MERGE (x:Empleado {id: e.id}) SET x.nombre = e.n, x.antiguedad_meses = e.a;
UNWIND [
  {e: 'E101', a: 'limpieza_hospitalaria', v: date('2027-03-31')},
  {e: 'E102', a: 'limpieza_hospitalaria', v: date('2026-09-28')},
  {e: 'E103', a: 'manejo_maquinaria_industrial', v: null},
  {e: 'E104', a: 'limpieza_hospitalaria', v: date('2027-06-30')},
  {e: 'E104', a: 'manejo_residuos_patogenicos', v: date('2026-08-15')},
  {e: 'E401', a: 'limpieza_hospitalaria', v: date('2027-05-31')},
  {e: 'E402', a: 'limpieza_hospitalaria', v: date('2027-02-28')},
  {e: 'E105', a: 'limpieza_hospitalaria', v: date('2026-11-19')}
] AS p
MATCH (e:Empleado {id: p.e}), (a:Aptitud {nombre: p.a})
MERGE (e)-[r:POSEE]->(a) SET r.vencimiento = p.v;
UNWIND [
  {e: 'E101', t: 'tarde', h: true, d: null, f: null},
  {e: 'E102', t: 'tarde', h: true, d: null, f: null},
  {e: 'E103', t: 'noche', h: true, d: null, f: null},
  {e: 'E104', t: 'mañana', h: true, d: null, f: null},
  {e: 'E104', t: 'tarde', h: false, d: time('14:00'), f: time('20:00')},
  {e: 'E105', t: 'tarde', h: false, d: time('14:00'), f: time('20:00')},
  {e: 'E401', t: 'noche', h: false, d: null, f: null},
  {e: 'E402', t: 'noche', h: true, d: null, f: null}
] AS d
MATCH (e:Empleado {id: d.e}), (t:Turno {nombre: d.t})
MERGE (e)-[r:TIENE_DISPONIBILIDAD_EN]->(t) SET r.habitual = d.h, r.desde = d.d, r.hasta = d.f;
UNWIND [
  {e: 'E105', z: 'Capital', h: true},
  {e: 'E101', z: 'Guaymallén', h: true},
  {e: 'E102', z: 'Capital', h: true},
  {e: 'E103', z: 'Godoy Cruz', h: true},
  {e: 'E104', z: 'Luján de Cuyo', h: true},
  {e: 'E104', z: 'Capital', h: false},
  {e: 'E401', z: 'Maipú', h: true},
  {e: 'E402', z: 'Luján de Cuyo', h: true}
] AS d
MATCH (e:Empleado {id: d.e}), (z:Zona {nombre: d.z})
MERGE (e)-[r:TIENE_DISPONIBILIDAD_EN]->(z) SET r.habitual = d.h;
UNWIND [
  {e: 'E101', s: 'Hospital Central', m: 2},
  {e: 'E101', s: 'Fábrica Sur', m: 14},
  {e: 'E104', s: 'Hospital Central', m: 20},
  {e: 'E401', s: 'Fábrica Sur', m: 24},
  {e: 'E105', s: 'Hospital Central', m: 12},
  {e: 'E402', s: 'Clínica Luján', m: 6},
  {e: 'E402', s: 'Supermercado Norte', m: 10}
] AS t
MATCH (e:Empleado {id: t.e}), (s:Servicio {nombre: t.s})
MERGE (e)-[r:TRABAJO_EN]->(s) SET r.meses = t.m;
UNWIND [
  {id: 'ED-01', e: 'E101', f: date('2026-07-15'), p: 7},
  {id: 'ED-02', e: 'E101', f: date('2026-09-02'), p: 8},
  {id: 'ED-03', e: 'E104', f: date('2026-08-12'), p: 6},
  {id: 'ED-04', e: 'E104', f: date('2026-09-20'), p: 3},
  {id: 'ED-05', e: 'E402', f: date('2026-03-10'), p: 8},
  {id: 'ED-06', e: 'E402', f: date('2026-08-25'), p: 7},
  {id: 'ED-07', e: 'E105', f: date('2026-08-20'), p: 8}
] AS d
MATCH (e:Empleado {id: d.e})
MERGE (x:Evaluacion_Desempeno {id: d.id}) SET x.fecha = d.f, x.puntaje = d.p
MERGE (e)-[:FUE_EVALUADO_EN]->(x);

// ==============================================================================
// 7. BASE DE CONOCIMIENTO DIFUSO: variables, terminos, funciones de pertenencia (parametros como propiedades)
// ==============================================================================
UNWIND [
  {n: 'urgencia', rol: 'Variable_Entrada', mn: 0, mx: 168, u: 'h', m: 'S3'},
  {n: 'desempeno_reciente', rol: 'Variable_Entrada', mn: 1, mx: 10, u: 'puntos', m: 'S3'},
  {n: 'cercania', rol: 'Variable_Entrada', mn: 0, mx: 90, u: 'min', m: 'S3'},
  {n: 'experiencia_equivalente', rol: 'Variable_Entrada', mn: 0, mx: 36, u: 'meses', m: 'S3'},
  {n: 'afinidad_global', rol: 'Variable_Salida', mn: 0, mx: 1, u: 'grado', m: 'S3'},
  {n: 'margen_vigencia', rol: 'Variable_Entrada', mn: 0, mx: 120, u: 'dias', m: 'S2'},
  {n: 'solape_horario', rol: 'Variable_Entrada', mn: 0, mx: 1, u: 'fraccion', m: 'S2'},
  {n: 'plazo_cobertura', rol: 'Variable_Entrada', mn: 0, mx: 168, u: 'h', m: 'S1'},
  {n: 'premura_expresada', rol: 'Variable_Entrada', mn: 0, mx: 10, u: 'puntaje', m: 'S1'},
  {n: 'urgencia_pedido', rol: 'Variable_Salida', mn: 0, mx: 1, u: 'grado', m: 'S1'}
] AS v
MERGE (x:Variable_Linguistica {nombre: v.n}) SET x.universo_min = v.mn, x.universo_max = v.mx, x.unidad = v.u, x.submodulo = v.m, x.estado_validacion = 'provisional'
FOREACH (_ IN CASE WHEN v.rol = 'Variable_Entrada' THEN [1] ELSE [] END | SET x:Variable_Entrada)
FOREACH (_ IN CASE WHEN v.rol = 'Variable_Salida' THEN [1] ELSE [] END | SET x:Variable_Salida);
UNWIND [
  {v: 'urgencia', t: 'alta', forma: 'gauss_hombro_izq', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 12.0, sigma: 20.38},
  {v: 'urgencia', t: 'media', forma: 'gauss', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 60.0, sigma: 20.38},
  {v: 'urgencia', t: 'baja', forma: 'gauss_hombro_der', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 108.0, sigma: 20.38},
  {v: 'desempeno_reciente', t: 'bajo', forma: 'gauss_hombro_izq', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 3.5, sigma: 1.274},
  {v: 'desempeno_reciente', t: 'medio', forma: 'gauss', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 6.5, sigma: 1.274},
  {v: 'desempeno_reciente', t: 'alto', forma: 'gauss_hombro_der', ver: '0.3', m: 'S3', vm: ['S3-v0.3'], centro: 9.5, sigma: 1.274},
  {v: 'cercania', t: 'misma_zona', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 0.0, b: 0.0, c: 10.0, d: 25.0},
  {v: 'cercania', t: 'cercana', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 15.0, b: 35.0, c: 35.0, d: 55.0},
  {v: 'cercania', t: 'lejana', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 45.0, b: 65.0, c: 90.0, d: 90.0},
  {v: 'experiencia_equivalente', t: 'baja', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 0.0, b: 0.0, c: 5.0, d: 8.0},
  {v: 'experiencia_equivalente', t: 'media', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 6.0, b: 12.0, c: 12.0, d: 20.0},
  {v: 'experiencia_equivalente', t: 'alta', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 15.0, b: 24.0, c: 36.0, d: 36.0},
  {v: 'afinidad_global', t: 'baja', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 0.0, b: 0.0, c: 0.0, d: 0.5},
  {v: 'afinidad_global', t: 'media', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 0.3, b: 0.5, c: 0.5, d: 0.7},
  {v: 'afinidad_global', t: 'alta', forma: 'trapecio', ver: '0.2', m: 'S3', vm: ['S3-v0.2', 'S3-v0.3'], a: 0.5, b: 1.0, c: 1.0, d: 1.0},
  {v: 'margen_vigencia', t: 'critico', forma: 'gauss2', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], c1: 0.0, s1: 6.0, c2: 7.0, s2: 6.0},
  {v: 'margen_vigencia', t: 'por_vencer', forma: 'gauss', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], centro: 35.0, sigma: 12.0},
  {v: 'margen_vigencia', t: 'holgado', forma: 'gauss2', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], c1: 75.0, s1: 12.0, c2: 120.0, s2: 12.0},
  {v: 'solape_horario', t: 'insuficiente', forma: 'gauss2', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], c1: 0.0, s1: 0.08, c2: 0.3, s2: 0.08},
  {v: 'solape_horario', t: 'parcial', forma: 'gauss', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], centro: 0.6, sigma: 0.1},
  {v: 'solape_horario', t: 'total', forma: 'gauss2', ver: '0.1', m: 'S2', vm: ['S2-v0.1'], c1: 0.85, s1: 0.06, c2: 1.0, s2: 0.06},
  {v: 'plazo_cobertura', t: 'inmediato', forma: 'gauss_hombro_izq', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 12.0, sigma: 22.0},
  {v: 'plazo_cobertura', t: 'corto', forma: 'gauss', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 62.0, sigma: 20.0},
  {v: 'plazo_cobertura', t: 'amplio', forma: 'gauss_hombro_der', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 112.0, sigma: 22.0},
  {v: 'premura_expresada', t: 'leve', forma: 'gauss_hombro_izq', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 2.0, sigma: 1.3},
  {v: 'premura_expresada', t: 'moderada', forma: 'gauss', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 5.0, sigma: 1.3},
  {v: 'premura_expresada', t: 'fuerte', forma: 'gauss_hombro_der', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 8.0, sigma: 1.3},
  {v: 'urgencia_pedido', t: 'baja', forma: 'gauss_hombro_izq', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 0.1, sigma: 0.17},
  {v: 'urgencia_pedido', t: 'media', forma: 'gauss', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 0.5, sigma: 0.17},
  {v: 'urgencia_pedido', t: 'alta', forma: 'gauss_hombro_der', ver: '0.1', m: 'S1', vm: ['S1-v0.1'], centro: 0.9, sigma: 0.17}
] AS t
MATCH (v:Variable_Linguistica {nombre: t.v})
MERGE (x:Termino_Linguistico {id: t.v + '.' + t.t}) SET x.nombre = t.t, x.variable = t.v, x.submodulo = t.m
MERGE (v)-[:TIENE_TERMINO]->(x)
MERGE (f:Funcion_Pertenencia {id: 'fp.' + t.v + '.' + t.t})
SET f.forma = t.forma, f.centro = t.centro, f.sigma = t.sigma, f.c1 = t.c1, f.s1 = t.s1, f.c2 = t.c2, f.s2 = t.s2, f.a = t.a, f.b = t.b, f.c = t.c, f.d = t.d,
    f.version = t.ver, f.vigente = true, f.estado = 'provisional', f.definido_por = 'ingeniero de conocimiento', f.submodulo = t.m,
    f.fuente = CASE WHEN t.forma = 'trapecio' THEN 'PI1 Tabla 1 (S3), reconstruida desde valores publicados en PI2' WHEN t.m = 'S2' THEN 'PI3 S2 (Cayo), tabla c.2' ELSE 'PI3 (fronteras con mu = 0,5)' END
MERGE (x)-[:DEFINIDO_POR]->(f)
WITH f, t
UNWIND t.vm AS vid
MATCH (vm:Version_Modelo_Difuso {id: vid}) MERGE (f)-[:PERTENECE_A_VERSION]->(vm);
UNWIND [
  {v: 'urgencia', t: 'alta', a: 0.0, b: 0.0, c: 24.0, d: 48.0},
  {v: 'urgencia', t: 'media', a: 24.0, b: 60.0, c: 60.0, d: 96.0},
  {v: 'urgencia', t: 'baja', a: 72.0, b: 120.0, c: 168.0, d: 168.0},
  {v: 'desempeno_reciente', t: 'bajo', a: 1.0, b: 1.0, c: 4.0, d: 6.0},
  {v: 'desempeno_reciente', t: 'medio', a: 4.5, b: 6.5, c: 6.5, d: 8.5},
  {v: 'desempeno_reciente', t: 'alto', a: 7.0, b: 8.5, c: 10.0, d: 10.0}
] AS t
MATCH (x:Termino_Linguistico {id: t.v + '.' + t.t}), (nuevo:Funcion_Pertenencia {id: 'fp.' + t.v + '.' + t.t}), (vm:Version_Modelo_Difuso {id: 'S3-v0.2'})
MERGE (f:Funcion_Pertenencia {id: 'fp.' + t.v + '.' + t.t + '.v0.2'})
SET f.forma = 'trapecio', f.a = t.a, f.b = t.b, f.c = t.c, f.d = t.d, f.version = '0.2', f.vigente = false, f.estado = 'reemplazada', f.submodulo = 'S3', f.fuente = 'PI1 Tabla 1 (S3), reconstruida desde valores publicados en PI2'
MERGE (x)-[:DEFINIDO_POR]->(f)
MERGE (f)-[:PERTENECE_A_VERSION]->(vm)
MERGE (nuevo)-[:REEMPLAZA]->(f);
UNWIND ['baja','media','alta'] AS n
MATCH (nv:Nivel_Urgencia {nombre: n})
MATCH (a:Termino_Linguistico {id: 'urgencia.' + n}), (b:Termino_Linguistico {id: 'urgencia_pedido.' + n})
MERGE (a)-[:CORRESPONDE_A]->(nv) MERGE (b)-[:CORRESPONDE_A]->(nv);
UNWIND [['cercania','Traslado'],['desempeno_reciente','Evaluacion_Desempeno'],['experiencia_equivalente','Servicio'],['urgencia','Puesto_Vacante'],['margen_vigencia','Puesto_Vacante'],['solape_horario','Turno'],['plazo_cobertura','Expresion_Urgencia'],['premura_expresada','Expresion_Urgencia']] AS p
MATCH (v:Variable_Linguistica {nombre: p[0]}), (f:Frame {nombre: p[1]})
MERGE (v)-[:SE_OBTIENE_DE]->(f);
UNWIND ['A','B'] AS g MERGE (x:Grupo_Reglas {id: 'S3-' + g}) SET x.aplica_si = CASE g WHEN 'A' THEN 'urgencia baja o media' ELSE 'urgencia alta' END, x.submodulo = 'S3';
MERGE (x:Grupo_Reglas {id: 'S2-V'}) SET x.aplica_si = 'cualquier urgencia', x.submodulo = 'S2';
UNWIND [['S1-GA','plazo y premura informados'],['S1-GB','solo plazo informado'],['S1-GC','solo premura informada']] AS g MERGE (x:Grupo_Reglas {id: g[0]}) SET x.aplica_si = g[1], x.submodulo = 'S1';
UNWIND [
  {id: 'S3-FA1', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'experiencia_equivalente.alta', 'desempeno_reciente.alto'], c: 'alta', p: 'Con tiempo, premiar al mas preparado'},
  {id: 'S3-FA2', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'experiencia_equivalente.media', 'desempeno_reciente.alto'], c: 'media', p: 'Buen desempeno compensa parte de la experiencia'},
  {id: 'S3-FA3', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'experiencia_equivalente.alta', 'desempeno_reciente.medio'], c: 'media', p: 'Experiencia sin desempeno destacado'},
  {id: 'S3-FA4', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'experiencia_equivalente.media', 'desempeno_reciente.medio'], c: 'media', p: 'Candidato correcto, sin diferencial'},
  {id: 'S3-FA5', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'experiencia_equivalente.baja'], c: 'baja', p: 'Con tiempo, no se arriesga sin experiencia'},
  {id: 'S3-FA6', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'desempeno_reciente.bajo'], c: 'baja', p: 'Con tiempo, no se elige a alguien mal evaluado'},
  {id: 'S3-FA7', g: 'A', ant: ['urgencia.baja|U', 'urgencia.media|U', 'cercania.lejana'], c: 'baja', p: 'La lejania es un costo aun sin apuro'},
  {id: 'S3-FB1', g: 'B', ant: ['urgencia.alta', 'cercania.misma_zona', 'experiencia_equivalente.media'], c: 'alta', p: 'Para ya, cerca y con experiencia suficiente'},
  {id: 'S3-FB2', g: 'B', ant: ['urgencia.alta', 'cercania.misma_zona', 'experiencia_equivalente.alta'], c: 'alta', p: 'El mejor caso con urgencia'},
  {id: 'S3-FB3', g: 'B', ant: ['urgencia.alta', 'cercania.cercana', 'experiencia_equivalente.alta'], c: 'alta', p: 'Algo mas lejos, pero experto'},
  {id: 'S3-FB4', g: 'B', ant: ['urgencia.alta', 'cercania.cercana', 'experiencia_equivalente.media'], c: 'media', p: 'Opcion aceptable'},
  {id: 'S3-FB5', g: 'B', ant: ['urgencia.alta', 'cercania.misma_zona', 'experiencia_equivalente.baja'], c: 'media', p: 'Disponible ya, aunque con poca experiencia'},
  {id: 'S3-FB6', g: 'B', ant: ['urgencia.alta', 'cercania.cercana', 'experiencia_equivalente.baja'], c: 'baja', p: 'Ni cerca ni preparado'},
  {id: 'S3-FB7', g: 'B', ant: ['urgencia.alta', 'cercania.lejana'], c: 'baja', p: 'Con urgencia, la distancia pesa mas que todo'},
  {id: 'S3-FB8', g: 'B', ant: ['urgencia.alta', 'desempeno_reciente.bajo'], c: 'media', p: 'Una mala evaluacion no descarta: baja a media y advierte'}
] AS r
MERGE (x:Regla_Difusa {id: r.id}) SET x.grupo = r.g, x.consecuente = 'afinidad_global:' + r.c, x.proposito = r.p, x.operador_y = 'MIN', x.operador_o = 'MAX', x.submodulo = 'S3', x.estado_validacion = 'provisional', x.origen = 'PI1 Tabla 3 / PG1 g.3'
WITH x, r
MATCH (g:Grupo_Reglas {id: 'S3-' + r.g}) MERGE (x)-[:INTEGRA]->(g)
WITH x, r
MATCH (tc:Termino_Linguistico {id: 'afinidad_global.' + r.c}) MERGE (x)-[:CONCLUYE]->(tc)
WITH x, r
UNWIND r.ant AS a
WITH x, split(a, '|') AS parts
MATCH (ta:Termino_Linguistico {id: parts[0]})
MERGE (x)-[ra:TIENE_ANTECEDENTE]->(ta)
FOREACH (_ IN CASE WHEN size(parts) > 1 THEN [1] ELSE [] END | SET ra.grupo_or = 'urgencia');
UNWIND [
  {id: 'S2-V1', peso: 1.0, p: 'Debilidad severa: la cobertura no se sostiene', ant: [{t: 'margen_vigencia.critico', neg: false, o: 'v1'}, {t: 'solape_horario.insuficiente', neg: false, o: 'v1'}]},
  {id: 'S2-V2', peso: 1.0, p: 'Dos debilidades moderadas juntas equivalen a una severa', ant: [{t: 'margen_vigencia.holgado', neg: true, o: null}, {t: 'solape_horario.total', neg: true, o: null}]},
  {id: 'S2-V3', peso: 0.2, p: 'Una debilidad moderada resta poco', ant: [{t: 'margen_vigencia.holgado', neg: true, o: 'v3'}, {t: 'solape_horario.total', neg: true, o: 'v3'}]}
] AS r
MERGE (x:Regla_Difusa {id: r.id}) SET x.grupo = 'V', x.consecuente = 'afinidad_global:baja', x.proposito = r.p, x.peso = r.peso, x.operador_y = 'MIN', x.operador_o = 'MAX', x.operador_no = '1 - mu', x.submodulo = 'S2', x.estado_validacion = 'provisional', x.origen = 'PI3 S2 (Cayo), d.2'
WITH x, r
MATCH (g:Grupo_Reglas {id: 'S2-V'}) MERGE (x)-[:INTEGRA]->(g)
WITH x, r
MATCH (tc:Termino_Linguistico {id: 'afinidad_global.baja'}) MERGE (x)-[:CONCLUYE]->(tc)
WITH x, r
UNWIND r.ant AS a
MATCH (ta:Termino_Linguistico {id: a.t})
MERGE (x)-[ra:TIENE_ANTECEDENTE]->(ta) SET ra.negado = a.neg, ra.grupo_or = a.o;
UNWIND [
  {id: 'S1-F01', a: 'plazo ES inmediato', c: 'alta', gs: ['S1-GA', 'S1-GB']},
  {id: 'S1-F02', a: 'plazo ES corto Y premura ES fuerte', c: 'alta', gs: ['S1-GA']},
  {id: 'S1-F03', a: '(plazo ES corto Y premura ES moderada) O (plazo ES amplio Y premura ES fuerte)', c: 'media', gs: ['S1-GA']},
  {id: 'S1-F04', a: '(plazo ES amplio O plazo ES corto) Y premura ES leve', c: 'baja', gs: ['S1-GA']},
  {id: 'S1-F05', a: 'plazo ES amplio Y premura ES moderada', c: 'baja', gs: ['S1-GA']},
  {id: 'S1-F06', a: 'plazo ES corto', c: 'media', gs: ['S1-GB']},
  {id: 'S1-F07', a: 'plazo ES amplio', c: 'baja', gs: ['S1-GB']},
  {id: 'S1-F08', a: 'premura ES fuerte', c: 'alta', gs: ['S1-GC']},
  {id: 'S1-F09', a: 'premura ES moderada', c: 'media', gs: ['S1-GC']},
  {id: 'S1-F10', a: 'premura ES leve', c: 'baja', gs: ['S1-GC']}
] AS r
MERGE (x:Regla_Difusa {id: r.id}) SET x.antecedente = r.a, x.consecuente = 'urgencia_pedido:' + r.c, x.operador_y = 'MIN', x.operador_o = 'MAX', x.submodulo = 'S1', x.estado_validacion = 'provisional', x.origen = 'PI3 S1 tabla 9'
WITH x, r
MATCH (tc:Termino_Linguistico {id: 'urgencia_pedido.' + split(r.c, ':')[0]}) MERGE (x)-[:CONCLUYE]->(tc)
WITH x, r
UNWIND r.gs AS gid
MATCH (g:Grupo_Reglas {id: gid}) MERGE (x)-[:INTEGRA]->(g);

// ==============================================================================
// 7b. S1-S4: reglas difusas vinculadas a la version del modelo
// ==============================================================================
MATCH (r:Regla_Difusa) WHERE r.submodulo = 'S1' MATCH (v:Version_Modelo_Difuso {id: 'S1-v0.1'}) MERGE (r)-[:PERTENECE_A_VERSION]->(v);
MATCH (r:Regla_Difusa) WHERE r.submodulo = 'S2' MATCH (v:Version_Modelo_Difuso {id: 'S2-v0.1'}) MERGE (r)-[:PERTENECE_A_VERSION]->(v);
MATCH (r:Regla_Difusa) WHERE r.submodulo = 'S3' MATCH (v:Version_Modelo_Difuso) WHERE v.id IN ['S3-v0.2','S3-v0.3'] MERGE (r)-[:PERTENECE_A_VERSION]->(v);

// ==============================================================================
// 7c. S4 - VARIABLES, TERMINOS, FUNCIONES (gaussianas) Y REGLAS FZ1-FZ6 (PI3 de S4)
// ==============================================================================
UNWIND [{n:'afinidad',rol:'Variable_Entrada',u:'grado'},{n:'confiabilidad',rol:'Variable_Entrada',u:'grado'},{n:'prioridad_recomendacion',rol:'Variable_Salida',u:'grado'}] AS v
MERGE (x:Variable_Linguistica {nombre: v.n}) SET x.universo_min = 0.0, x.universo_max = 1.0, x.unidad = v.u, x.submodulo = 'S4', x.estado_validacion = 'provisional'
FOREACH (_ IN CASE WHEN v.rol = 'Variable_Entrada' THEN [1] ELSE [] END | SET x:Variable_Entrada)
FOREACH (_ IN CASE WHEN v.rol = 'Variable_Salida' THEN [1] ELSE [] END | SET x:Variable_Salida);
UNWIND [
  {v: 'afinidad', t: 'baja', c: 0.0, s: 0.34, h: null},
  {v: 'afinidad', t: 'intermedia', c: 0.55, s: 0.127, h: null},
  {v: 'afinidad', t: 'alta', c: 1.0, s: 0.255, h: null},
  {v: 'confiabilidad', t: 'baja', c: 0.55, s: 0.127, h: 'izq'},
  {v: 'confiabilidad', t: 'media', c: 0.8, s: 0.085, h: null},
  {v: 'confiabilidad', t: 'alta', c: 1.0, s: 0.085, h: null},
  {v: 'prioridad_recomendacion', t: 'Baja_prioridad', c: 0.15, s: 0.1, h: null},
  {v: 'prioridad_recomendacion', t: 'Recomendado_con_reservas', c: 0.5, s: 0.1, h: null},
  {v: 'prioridad_recomendacion', t: 'Recomendado', c: 0.85, s: 0.1, h: null}
] AS t
MATCH (v:Variable_Linguistica {nombre: t.v}), (vm:Version_Modelo_Difuso {id: 'S4-FZ-v1'})
MERGE (x:Termino_Linguistico {id: t.v + '.' + t.t}) SET x.nombre = t.t, x.variable = t.v, x.submodulo = 'S4'
MERGE (v)-[:TIENE_TERMINO]->(x)
MERGE (f:Funcion_Pertenencia {id: 'fp.' + t.v + '.' + t.t})
SET f.forma = 'gaussiana', f.centro = t.c, f.sigma = t.s, f.hombro = t.h, f.version = '1', f.vigente = true, f.estado = 'politica_candidata', f.definido_por = 'ingeniero de conocimiento', f.submodulo = 'S4', f.fuente = 'PI3 S4 (León), tabla c.2'
MERGE (x)-[:DEFINIDO_POR]->(f)
MERGE (f)-[:PERTENECE_A_VERSION]->(vm);
UNWIND ['Recomendado','Recomendado_con_reservas','Baja_prioridad'] AS n
MATCH (t:Termino_Linguistico {id: 'prioridad_recomendacion.' + n}), (c:Categoria {nombre: n}) MERGE (t)-[:CORRESPONDE_A]->(c);
MATCH (a:Variable_Linguistica {nombre: 'afinidad_global'}), (b:Variable_Linguistica {nombre: 'afinidad'}) MERGE (a)-[r:ALIMENTA]->(b) SET r.nota = 'S4 re-particiona la afinidad de S3 (baja/intermedia/alta con otros centros); usa el punto medio del intervalo', r.estado_validacion = 'a reconciliar con S3';
MERGE (g:Grupo_Reglas {id: 'S4-FZ'}) SET g.aplica_si = 'candidato valido (estado_S2 = valido) con afinidad recibida de S3', g.implicacion = 'MIN', g.agregacion = 'MAX', g.submodulo = 'S4';
UNWIND [
  {id: 'S4-FZ1', c: 'Recomendado', ant: ['afinidad.alta', 'confiabilidad.alta'], adv: 'ninguna', p: 'Afinidad alta, dato preciso y sin advertencias'},
  {id: 'S4-FZ2', c: 'Recomendado_con_reservas', ant: ['afinidad.alta', 'confiabilidad.media|C', 'confiabilidad.baja|C'], adv: null, p: 'Afinidad alta pero dato impreciso: reservas'},
  {id: 'S4-FZ3', c: 'Recomendado_con_reservas', ant: ['afinidad.alta'], adv: 'con_advertencia o sin_dato', p: 'Afinidad alta con advertencia (o sin dato de advertencias): reservas'},
  {id: 'S4-FZ4', c: 'Recomendado_con_reservas', ant: ['afinidad.intermedia'], adv: null, p: 'Afinidad intermedia: reservas'},
  {id: 'S4-FZ5', c: 'Baja_prioridad', ant: ['afinidad.baja', 'confiabilidad.alta|C', 'confiabilidad.media|C'], adv: null, p: 'Afinidad baja con dato razonablemente preciso: baja prioridad'},
  {id: 'S4-FZ6', c: 'Recomendado_con_reservas', ant: ['afinidad.baja', 'confiabilidad.baja'], adv: null, p: 'Afinidad baja por falta de datos: no se relega, se revisa (POLITICA A VALIDAR)'}
] AS r
MATCH (g:Grupo_Reglas {id: 'S4-FZ'}), (tc:Termino_Linguistico {id: 'prioridad_recomendacion.' + r.c}), (vm:Version_Modelo_Difuso {id: 'S4-FZ-v1'})
MERGE (x:Regla_Difusa {id: r.id}) SET x.grupo = 'S4-FZ', x.consecuente = 'prioridad_recomendacion:' + r.c, x.proposito = r.p, x.condicion_advertencias = r.adv, x.operador_y = 'MIN', x.operador_o = 'MAX', x.submodulo = 'S4', x.estado_validacion = 'politica_candidata', x.origen = 'PI3 S4 (León)'
MERGE (x)-[:INTEGRA]->(g) MERGE (x)-[:CONCLUYE]->(tc) MERGE (x)-[:PERTENECE_A_VERSION]->(vm)
WITH x, r
UNWIND r.ant AS a
WITH x, split(a, '|') AS parts
MATCH (ta:Termino_Linguistico {id: parts[0]})
MERGE (x)-[ra:TIENE_ANTECEDENTE]->(ta)
FOREACH (_ IN CASE WHEN size(parts) > 1 THEN [1] ELSE [] END | SET ra.grupo_or = parts[1]);

// ==============================================================================
// 8. REGLAS CRISP DOCUMENTADAS (43 reglas: 39 de PG1 + S2-R10 de PI3 de S2 + S3-R15, S4-R07 y S4-R08 de PG2; ids con prefijo de modulo)
// ==============================================================================
UNWIND [
  {id: 'S1-R01', m: 'S1', t: 'Determinística', e: 'Sin servicio unico, turno o zona (o zona informada no reconocida): pedido en_espera con campos_faltantes y sin puesto'},
  {id: 'S1-R02', m: 'S1', t: 'Heurística', e: 'Aptitud con marcador de exigencia: excluyente'},
  {id: 'S1-R03', m: 'S1', t: 'Heurística', e: 'Aptitud sin marcador: deseable'},
  {id: 'S1-R04', m: 'S1', t: 'Heurística', e: 'Expresion de urgencia del diccionario: plazo o premura; la urgencia se obtiene con las reglas difusas S1-F01 a F10 (grados y centroide; categoria por grado dominante)'},
  {id: 'S1-R05', m: 'S1', t: 'Determinística', e: 'Mas de una combinacion turno/servicio: un puesto por combinacion'},
  {id: 'S1-R06', m: 'S1', t: 'Determinística', e: 'Servicio por nombre oficial o alias unico (exacta, por_alias, no_reconocido, ambiguo)'},
  {id: 'S1-R07', m: 'S1', t: 'Determinística', e: 'Zona heredada del servicio si no se informa; informada y no reconocida: en espera'},
  {id: 'S1-R08', m: 'S1', t: 'Determinística', e: 'Aptitud normalizada contra el catalogo; si no, aptitudes_no_reconocidas'},
  {id: 'S1-R09', m: 'S1', t: 'Heurística', e: 'Relajacion explicita de zona: radio_extendido = si'},
  {id: 'S1-R10', m: 'S1', t: 'Determinística', e: 'Experiencia minima numerica: meses'},
  {id: 'S2-R01', m: 'S2', t: 'Inferencial', e: 'Si el servicio o su tipo EXIGE una aptitud: REQUIERE excluyente aunque el pedido la marque deseable'},
  {id: 'S2-R02', m: 'S2', t: 'Determinística', e: 'Excluyente efectiva no poseida: motivo aptitud faltante'},
  {id: 'S2-R03', m: 'S2', t: 'Determinística', e: 'Certificacion con vencimiento anterior a la fecha de evaluacion: no poseida (vence ese dia: vigente)'},
  {id: 'S2-R04', m: 'S2', t: 'Determinística', e: 'Sin disponibilidad hacia el turno del puesto: motivo turno incompatible'},
  {id: 'S2-R05', m: 'S2', t: 'Heurística', e: 'Zona lejana sin radio_extendido: motivo zona incompatible'},
  {id: 'S2-R06', m: 'S2', t: 'Determinística', e: 'Sin motivos: estado_S2 valido; si no, descartado con todos los motivos'},
  {id: 'S2-R07', m: 'S2', t: 'Determinística', e: 'Valido con deseable efectiva no vigente: deseables_faltantes'},
  {id: 'S2-R08', m: 'S2', t: 'Determinística', e: 'Con validos: a S3; sin validos: a S4 con conteo por motivo'},
  {id: 'S2-R09', m: 'S2', t: 'Inferencial', e: 'Sin validos: motivo_critico = motivo(s) de maximo conteo'},
  {id: 'S2-R10', m: 'S2', t: 'Determinística', e: 'Valido: registra margen_vigencia_dias (minimo de dias a vencer de las excluyentes, saturado en 120) y solape_horario (fraccion del turno cubierta; sin horario: DESCONOCIDO). No modifica estado_S2'},
  {id: 'S3-R01', m: 'S3', t: 'Determinística', e: 'Lista de validos vacia: sin candidatos validos (guarda de S2-R08)'},
  {id: 'S3-R02', m: 'S3', t: 'Determinística', e: 'Sin urgencia: rango 0-168 h, DESCONOCIDO, URGENCIA_DESCONOCIDA'},
  {id: 'S3-R03', m: 'S3', t: 'Heurística', e: 'Orden determinado y diferencia < 0,05: desempate por desempeno y antiguedad; EMPATE_TECNICO'},
  {id: 'S3-R04', m: 'S3', t: 'Heurística', e: 'Desempeno observado con mu(bajo) > 0,5: DESEMPEÑO_BAJO_RECIENTE, sin descarte'},
  {id: 'S3-R05', m: 'S3', t: 'Heurística', e: 'Todas las afinidades con termino dominante baja: SIN_CANDIDATO_PLENO'},
  {id: 'S3-R06', m: 'S3', t: 'Determinística', e: 'Urgencia solo categoria: rango de horas ESTIMADO (propuesta PG2: grados de S1)'},
  {id: 'S3-R07', m: 'S3', t: 'Determinística', e: 'Sin traslado y zona misma o lindera: rango del termino, ESTIMADO'},
  {id: 'S3-R08', m: 'S3', t: 'Determinística', e: 'Sin traslado ni adyacencia: 0-90 min, DESCONOCIDO'},
  {id: 'S3-R09', m: 'S3', t: 'Determinística', e: 'Sin evaluaciones en la ventana: 1-10, DESCONOCIDO'},
  {id: 'S3-R10', m: 'S3', t: 'Inferencial', e: 'Orden de un par que puede invertirse: ORDEN_NO_DETERMINADO'},
  {id: 'S3-R15', m: 'S3', t: 'Heurística', e: 'Empate (< 0,05) con urgencia no OBSERVADA: orden no determinado, sin desempate automatico (devolucion PI3 S3)'},
  {id: 'S3-R11', m: 'S3', t: 'Determinística', e: 'Servicio previo sin similitud: rango 0-1, SERVICIO_FUERA_DE_MATRIZ'},
  {id: 'S3-R12', m: 'S3', t: 'Inferencial', e: 'Experiencia equivalente = meses x similitud'},
  {id: 'S3-R13', m: 'S3', t: 'Determinística', e: 'Ventana de desempeno de 12 meses'},
  {id: 'S3-R14', m: 'S3', t: 'Determinística', e: 'Un solo valido: ranking de un elemento'},
  {id: 'S4-R01', m: 'S4', t: 'Determinística', e: 'Descartado por S2: Baja prioridad, sin afinidad'},
  {id: 'S4-R02', m: 'S4', t: 'Heurística', e: 'Categoria por prioridad difusa (FZ1 a FZ6) y regla de corte FZ-C con cortes calibrados 0,610 y 0,367 de la version vigente; reemplaza el corte nitido 0,70 / 0,40 de PG1 (que queda como referencia de calibracion)'},
  {id: 'S4-R03', m: 'S4', t: 'Heurística', e: 'Dos o mas advertencias: nunca Recomendado'},
  {id: 'S4-R04', m: 'S4', t: 'Heurística', e: 'Marcas con uso advertencia generan advertencia sin descartar'},
  {id: 'S4-R07', m: 'S4', t: 'Heurística', e: 'Criterio de orden del listado: PROVISIONAL (M8). Se registran la posicion por afinidad y la posicion por prioridad difusa; no se presenta como criterio de RR. HH.'},
  {id: 'S4-R08', m: 'S4', t: 'Determinística', e: 'aptitudes_deseables_estado: EVALUADAS (lista vacia = no falta ninguna) o SIN_DATO (lista vacia = todavia no se sabe)'},
  {id: 'S4-R05', m: 'S4', t: 'Determinística', e: 'La justificacion solo cita datos presentes en los slots'},
  {id: 'S4-R06', m: 'S4', t: 'Contextual', e: 'Sin validos: conteo y motivo critico; orden no determinado: presentar ambos'}
] AS r
MERGE (x:Regla_Crisp {id: r.id}) SET x.modulo = r.m, x.tipo = r.t, x.enunciado = r.e, x.estado_validacion = 'provisional', x.submodulo = r.m;

// ==============================================================================
// 9. S1 - EXPRESIONES DE URGENCIA, ACTORES, PEDIDOS Y PUESTOS
// ==============================================================================
UNWIND [
  {t: 'hoy', tipo: 'plazo', v: 8, u: 'h', n: 'alta'},
  {t: 'para mañana', tipo: 'plazo', v: 24, u: 'h', n: 'alta'},
  {t: 'pasado mañana', tipo: 'plazo', v: 48, u: 'h', n: 'media'},
  {t: 'dentro de cinco días', tipo: 'plazo', v: 120, u: 'h', n: 'baja'},
  {t: 'en unos días', tipo: 'plazo', v: 72, u: 'h', n: 'media'},
  {t: 'para esta semana', tipo: 'plazo', v: 84, u: 'h', n: 'media'},
  {t: 'la semana que viene', tipo: 'plazo', v: 144, u: 'h', n: 'baja'},
  {t: 'cuando se pueda', tipo: 'premura', v: 1, u: 'puntos', n: 'baja'},
  {t: 'sin apuro', tipo: 'premura', v: 1, u: 'puntos', n: 'baja'},
  {t: 'con tiempo', tipo: 'premura', v: 2, u: 'puntos', n: 'baja'},
  {t: 'pronto', tipo: 'premura', v: 5, u: 'puntos', n: 'media'},
  {t: 'con prioridad', tipo: 'premura', v: 6, u: 'puntos', n: 'media'},
  {t: 'urgente', tipo: 'premura', v: 8, u: 'puntos', n: 'alta'},
  {t: 'lo antes posible', tipo: 'premura', v: 9, u: 'puntos', n: 'alta'},
  {t: 'de inmediato', tipo: 'premura', v: 10, u: 'puntos', n: 'alta'}
] AS x
MATCH (v:Variable_Linguistica {nombre: CASE x.tipo WHEN 'plazo' THEN 'plazo_cobertura' ELSE 'premura_expresada' END}), (n:Nivel_Urgencia {nombre: x.n})
MERGE (e:Expresion_Urgencia {texto: x.t}) SET e.tipo = x.tipo, e.valor = x.v, e.unidad = x.u, e.fuente = 'diseno_del_grupo', e.estado_validacion = 'provisional'
MERGE (e)-[:EXPRESA {valor: x.v, unidad: x.u}]->(v)
MERGE (e)-[:EQUIVALE_A {fuente: 'diseno_del_grupo', estado_validacion: 'provisional'}]->(n);
UNWIND [{id:'sup_hospital_central',n:'Supervisor Hospital Central',r:'solicitante'},{id:'sup_clinica_lujan',n:'Supervisor Clínica Luján',r:'solicitante'},{id:'sup_003',n:'Supervisor sin identificar',r:'solicitante'},{id:'sup_fabrica_sur',n:'Supervisor Fábrica Sur',r:'solicitante'},{id:'rec_01',n:'Analista de RR. HH.',r:'reclutador'}] AS a
MERGE (x:Actor {id: a.id}) SET x.nombre = a.n, x.rol = a.r
FOREACH (_ IN CASE WHEN a.r = 'solicitante' THEN [1] ELSE [] END | SET x:Solicitante)
FOREACH (_ IN CASE WHEN a.r = 'reclutador' THEN [1] ELSE [] END | SET x:Reclutador);
UNWIND [
  {id:'ped_001', s:'sup_hospital_central', canal:'texto_libre', estado:'completo', falt:[], ut:'para mañana', uts:['para mañana'], txt:'Necesito un reemplazo para el turno tarde en el Hospital Central, con limpieza hospitalaria y, preferentemente, manejo de residuos patogénicos, para mañana.'},
  {id:'ped_002', s:'sup_clinica_lujan', canal:'texto_libre', estado:'completo', falt:[], ut:'la semana que viene', uts:['la semana que viene'], txt:'Necesito cubrir el turno noche en la Clínica Luján, con limpieza hospitalaria, para la semana que viene.'},
  {id:'ped_003', s:'sup_003', canal:'texto_libre', estado:'en_espera', falt:['servicio','turno','zona'], ut:'urgente', uts:['urgente'], txt:'Necesito cubrir un turno, urgente.'},
  {id:'ped_004', s:'sup_fabrica_sur', canal:'texto_libre', estado:'completo', falt:[], ut:'urgente, dentro de cinco días', uts:['urgente','dentro de cinco días'], txt:'Necesito cubrir el turno noche en la Fábrica Sur, urgente, dentro de cinco días.'}
] AS p
MATCH (a:Actor {id: p.s})
MERGE (x:Pedido_Cobertura {id: p.id}) SET x.canal = p.canal, x.estado = p.estado, x.campos_faltantes = p.falt, x.urgencia_textual = p.ut, x.texto_original = p.txt
MERGE (a)-[:ENVIA]->(x)
WITH x, p
UNWIND p.uts AS u
MATCH (e:Expresion_Urgencia {texto: u}) MERGE (x)-[:CONTIENE]->(e);
UNWIND [{p:'ped_001', s:'Hospital Central', t:'Hospital Central'},{p:'ped_002', s:'Clínica Luján', t:'Clínica Luján'},{p:'ped_004', s:'Fábrica Sur', t:'la Fábrica Sur'}] AS m
MATCH (p:Pedido_Cobertura {id: m.p}), (s:Servicio {nombre: m.s}) MERGE (p)-[r:MENCIONA]->(s) SET r.texto_literal = m.t;
UNWIND [{p:'ped_001', a:'limpieza_hospitalaria'},{p:'ped_001', a:'manejo_residuos_patogenicos'},{p:'ped_002', a:'limpieza_hospitalaria'}] AS m
MATCH (p:Pedido_Cobertura {id: m.p}), (a:Aptitud {nombre: m.a}) MERGE (p)-[r:MENCIONA]->(a) SET r.marcador_importancia = null;
UNWIND [
  {id: 'pv_001', ped: 'ped_001', s: 'Hospital Central', z: 'Capital', t: 'tarde', cat: 'alta', gb: 0.0, gm: 0.164, ga: 0.862, val: 0.723, gr: 'S1-GB', ue: 'OBSERVADO', apt: ['limpieza_hospitalaria', 'manejo_residuos_patogenicos']},
  {id: 'pv_002', ped: 'ped_002', s: 'Clínica Luján', z: 'Luján de Cuyo', t: 'noche', cat: 'baja', gb: 1.0, gm: 0.0, ga: 0.0, val: 0.176, gr: 'S1-GB', ue: 'OBSERVADO', apt: ['limpieza_hospitalaria']},
  {id: 'pv_003', ped: 'ped_004', s: 'Fábrica Sur', z: 'Maipú', t: 'noche', cat: 'media', gb: 0.07, gm: 1.0, ga: 0.015, val: 0.496, gr: 'S1-GA', ue: 'OBSERVADO', apt: []}
] AS v
MATCH (ped:Pedido_Cobertura {id: v.ped}), (s:Servicio {nombre: v.s}), (z:Zona {nombre: v.z}), (t:Turno {nombre: v.t}), (n:Nivel_Urgencia {nombre: v.cat}), (vm:Version_Modelo_Difuso {id: 'S1-v0.1'})
MERGE (p:Puesto_Vacante {id: v.id})
SET p.radio_extendido = false, p.experiencia_minima_meses = null, p.fecha_evaluacion = date('2026-10-05'),
    p.urgencia_categoria = v.cat, p.urgencia_estado = v.ue, p.grado_urgencia_baja = v.gb, p.grado_urgencia_media = v.gm, p.grado_urgencia_alta = v.ga, p.urgencia_valor = v.val
MERGE (ped)-[:GENERA]->(p)
MERGE (p)-[:PERTENECE_A]->(s)
MERGE (p)-[ez:EN_ZONA]->(z) SET ez.origen = 'inferido'
MERGE (p)-[:EN_TURNO]->(t)
MERGE (p)-[tu:TIENE_URGENCIA]->(n) SET tu.origen = 'inferido', tu.grado_baja = v.gb, tu.grado_media = v.gm, tu.grado_alta = v.ga, tu.valor = v.val, tu.grupo_reglas = v.gr, tu.estado_validacion = 'provisional'
MERGE (p)-[:CALCULADO_CON]->(vm)
WITH p, v
UNWIND v.apt AS an
MATCH (a:Aptitud {nombre: an})
MERGE (p)-[r:REQUIERE]->(a) SET r.excluyente = false, r.origen = 'declarado', r.regla = 'S1-R03';

// ==============================================================================
// 10. S2 - INFERENCIA CRISP: R01 (aptitudes efectivas), evaluacion de cada par empleado-puesto (R02 a R07) y R10 (margen y solape)
// ==============================================================================
// S2-R01 por tipo de servicio
MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(:Servicio)-[:ES_DE_TIPO]->(:Tipo_Servicio)-[:EXIGE]->(a:Aptitud)
MERGE (p)-[r:REQUIERE]->(a)
ON CREATE SET r.origen = 'inferido', r.excluyente = true, r.regla = 'S2-R01', r.promovida_por_catalogo = false
ON MATCH SET r.promovida_por_catalogo = coalesce(r.promovida_por_catalogo, false) OR (r.excluyente = false), r.excluyente = true, r.regla = 'S2-R01';
// S2-R01 por exigencias propias de la sede
MATCH (p:Puesto_Vacante)-[:PERTENECE_A]->(:Servicio)-[:EXIGE]->(a:Aptitud)
MERGE (p)-[r:REQUIERE]->(a)
ON CREATE SET r.origen = 'inferido', r.excluyente = true, r.regla = 'S2-R01', r.promovida_por_catalogo = false
ON MATCH SET r.promovida_por_catalogo = coalesce(r.promovida_por_catalogo, false) OR (r.excluyente = false), r.excluyente = true, r.regla = 'S2-R01';
// S2-R02 a R06: un EvaluacionEmpleadoPuesto por cada par empleado-puesto
MATCH (p:Puesto_Vacante), (e:Empleado)
OPTIONAL MATCH (p)-[r:REQUIERE]->(a:Aptitud) WHERE r.excluyente = true
OPTIONAL MATCH (e)-[po:POSEE]->(a)
WITH p, e, collect(
  CASE
    WHEN a IS NULL THEN null
    WHEN po IS NULL THEN 'aptitud faltante: ' + a.nombre
    WHEN po.vencimiento IS NOT NULL AND po.vencimiento < p.fecha_evaluacion THEN 'certificación vencida: ' + a.nombre
  END) AS m_aptitud
WITH p, e, m_aptitud,
  CASE WHEN EXISTS { (e)-[:TIENE_DISPONIBILIDAD_EN]->(:Turno)<-[:EN_TURNO]-(p) } THEN [] ELSE ['turno incompatible'] END AS m_turno,
  CASE WHEN p.radio_extendido = true
         OR EXISTS { (e)-[:TIENE_DISPONIBILIDAD_EN]->(:Zona)<-[:EN_ZONA]-(p) }
         OR EXISTS { (e)-[:TIENE_DISPONIBILIDAD_EN {habitual: true}]->(:Zona)-[:CERCANA_A]-(:Zona)<-[:EN_ZONA]-(p) }
       THEN [] ELSE ['zona incompatible'] END AS m_zona
WITH p, e, m_aptitud + m_turno + m_zona AS motivos
MERGE (ev:EvaluacionEmpleadoPuesto {id: 'EV-' + e.id + '-' + p.id})
SET ev.estado_S2 = CASE WHEN size(motivos) = 0 THEN 'valido' ELSE 'descartado' END,
    ev.motivos_descarte = motivos, ev.submodulo = 'S2'
MERGE (ev)-[:REFIERE_A]->(e)
MERGE (ev)-[:PARA]->(p);
// S2-R07: deseables faltantes de los validos
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(p:Puesto_Vacante)
OPTIONAL MATCH (p)-[rd:REQUIERE]->(ad:Aptitud) WHERE rd.excluyente = false
OPTIONAL MATCH (e)-[pd:POSEE]->(ad)
WITH ev, collect(
  CASE
    WHEN ad IS NULL THEN null
    WHEN pd IS NULL THEN ad.nombre
    WHEN pd.vencimiento IS NOT NULL AND pd.vencimiento < p.fecha_evaluacion THEN ad.nombre + ' (vencida)'
  END) AS faltantes
SET ev.deseables_faltantes = faltantes, ev.deseables_estado = 'EVALUADAS';
// S4-R08: el descartado no se evalua en deseables: no hay dato (distinto de 'no falta ninguna')
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'descartado'})
SET ev.deseables_faltantes = null, ev.deseables_estado = 'SIN_DATO';
// S2-R10 (margen): dias hasta el vencimiento mas proximo de las excluyentes efectivas, saturado en 120
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(p:Puesto_Vacante)
OPTIONAL MATCH (p)-[:REQUIERE {excluyente: true}]->(a:Aptitud)<-[po:POSEE]-(e) WHERE po.vencimiento IS NOT NULL
WITH ev, collect(duration.inDays(p.fecha_evaluacion, po.vencimiento).days) AS dias
WITH ev, CASE WHEN size(dias) = 0 THEN 120 ELSE reduce(m = dias[0], x IN dias | CASE WHEN x < m THEN x ELSE m END) END AS minimo
SET ev.margen_vigencia_dias = CASE WHEN minimo > 120 THEN 120 ELSE minimo END;
// S2-R10 (solape): fraccion del turno cubierta por la disponibilidad; habitual = 1; sin desde/hasta = DESCONOCIDO
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(:Puesto_Vacante)-[:EN_TURNO]->(t:Turno)
OPTIONAL MATCH (e)-[d:TIENE_DISPONIBILIDAD_EN]->(t)
WITH ev, d, t.horario_inicio.hour AS ti,
     CASE WHEN t.horario_fin.hour <= t.horario_inicio.hour THEN t.horario_fin.hour + 24 ELSE t.horario_fin.hour END AS tf,
     CASE WHEN d.desde IS NULL OR d.hasta IS NULL THEN null ELSE d.desde.hour END AS di,
     CASE WHEN d.desde IS NULL OR d.hasta IS NULL THEN null
          WHEN d.hasta.hour <= d.desde.hour THEN d.hasta.hour + 24 ELSE d.hasta.hour END AS df
WITH ev, d, ti, tf, (CASE WHEN tf < df THEN tf ELSE df END) - (CASE WHEN ti > di THEN ti ELSE di END) AS ov
SET ev.solape_horario = CASE WHEN d.habitual = true THEN 1.0 WHEN ov IS NULL THEN null WHEN ov < 0 THEN 0.0 ELSE toFloat(ov) / (tf - ti) END,
    ev.solape_estado = CASE WHEN d.habitual = true OR ov IS NOT NULL THEN 'OBSERVADO' ELSE 'DESCONOCIDO' END;

// ==============================================================================
// 11. S3 - DATOS DE VALORACION (estado del dato, rangos y marcas). Zonas del empleado = disponibilidades (H10)
// ==============================================================================
// Cercania observada: menor traslado registrado entre las zonas del empleado y la zona del servicio
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio)
OPTIONAL MATCH (e)-[:TIENE_DISPONIBILIDAD_EN]->(:Zona)-[:ORIGEN_DE]->(tr:Traslado {estado: 'OBSERVADO'})-[:HACIA]->(s)
WITH ev, collect(tr.minutos) AS obs
WHERE size(obs) > 0
SET ev.cerc_min = toFloat(reduce(m = obs[0], x IN obs | CASE WHEN x < m THEN x ELSE m END)),
    ev.cerc_max = toFloat(reduce(m = obs[0], x IN obs | CASE WHEN x < m THEN x ELSE m END)),
    ev.cerc_estado = 'OBSERVADO';
// Cercania estimada o desconocida (S3-R07 y S3-R08)
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(:Puesto_Vacante)-[:PERTENECE_A]->(s:Servicio)-[:EN_ZONA]->(zs:Zona)
WHERE ev.cerc_estado IS NULL
OPTIONAL MATCH (e)-[:TIENE_DISPONIBILIDAD_EN]->(zm:Zona) WHERE zm = zs
WITH ev, e, zs, count(zm) AS n_misma
OPTIONAL MATCH (e)-[:TIENE_DISPONIBILIDAD_EN]->(zl:Zona)-[:LINDA_CON]-(zs)
WITH ev, e, zs, n_misma, count(zl) AS n_lind
OPTIONAL MATCH (e)-[:TIENE_DISPONIBILIDAD_EN]->(za:Zona)-[:LINDA_CON]-(:Zona)
WITH ev, n_misma, n_lind, count(za) AS n_ady
SET ev.cerc_min = CASE WHEN n_misma > 0 THEN 0.0 WHEN n_lind > 0 THEN 15.0 WHEN n_ady > 0 THEN 45.0 ELSE 0.0 END,
    ev.cerc_max = CASE WHEN n_misma > 0 THEN 25.0 WHEN n_lind > 0 THEN 55.0 ELSE 90.0 END,
    ev.cerc_estado = CASE WHEN n_misma > 0 OR n_lind > 0 OR n_ady > 0 THEN 'ESTIMADO' ELSE 'DESCONOCIDO' END;
// Experiencia equivalente (S3-R12 y S3-R11)
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(:Puesto_Vacante)-[:PERTENECE_A]->(:Servicio)-[:ES_DE_TIPO]->(tp:Tipo_Servicio)
OPTIONAL MATCH (e)-[tw:TRABAJO_EN]->(:Servicio)-[:ES_DE_TIPO]->(ts:Tipo_Servicio)
OPTIONAL MATCH (ts)-[sim:SIMILAR_A]->(tp)
WITH ev, tw, ts,
  CASE WHEN ts IS NULL THEN null WHEN ts = tp THEN 1.0 WHEN sim IS NOT NULL THEN sim.valor ELSE null END AS s
WITH ev,
  sum(CASE WHEN ts IS NOT NULL AND s IS NOT NULL THEN tw.meses * s ELSE 0.0 END) AS base,
  sum(CASE WHEN ts IS NOT NULL AND s IS NULL THEN toFloat(tw.meses) ELSE 0.0 END) AS sin_par
SET ev.exp_min = base, ev.exp_max = base + sin_par,
    ev.exp_estado = CASE WHEN sin_par > 0 THEN 'DESCONOCIDO' ELSE 'OBSERVADO' END;
// Desempeno reciente (S3-R13 y S3-R09)
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:REFIERE_A]->(e:Empleado), (ev)-[:PARA]->(p:Puesto_Vacante)
OPTIONAL MATCH (e)-[:FUE_EVALUADO_EN]->(d:Evaluacion_Desempeno) WHERE d.fecha >= p.fecha_evaluacion - duration({months: 12})
WITH ev, count(d) AS n, avg(d.puntaje) AS prom
SET ev.des_min = CASE WHEN n > 0 THEN toFloat(prom) ELSE 1.0 END,
    ev.des_max = CASE WHEN n > 0 THEN toFloat(prom) ELSE 10.0 END,
    ev.des_estado = CASE WHEN n > 0 THEN 'OBSERVADO' ELSE 'DESCONOCIDO' END,
    ev.des_n_evaluaciones = n;
// Marcas de calidad del dato (S3-R04, R06 a R09)
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:PARA]->(p:Puesto_Vacante)
WHERE p.urgencia_estado = 'ESTIMADO'
MATCH (m:MarcaCalidadDato {codigo: 'URGENCIA_ESTIMADA'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:PARA]->(p:Puesto_Vacante {urgencia_estado: 'DESCONOCIDO'}), (m:MarcaCalidadDato {codigo: 'URGENCIA_DESCONOCIDA'})
MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {cerc_estado: 'ESTIMADO'}), (m:MarcaCalidadDato {codigo: 'TRASLADO_ESTIMADO'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {cerc_estado: 'DESCONOCIDO'}), (m:MarcaCalidadDato {codigo: 'TRASLADO_DESCONOCIDO'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {des_estado: 'DESCONOCIDO'}), (m:MarcaCalidadDato {codigo: 'DESEMPEÑO_DESCONOCIDO'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {solape_estado: 'DESCONOCIDO'}), (m:MarcaCalidadDato {codigo: 'HORARIO_DESCONOCIDO'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {exp_estado: 'DESCONOCIDO'}), (m:MarcaCalidadDato {codigo: 'SERVICIO_FUERA_DE_MATRIZ'}) MERGE (ev)-[:TIENE_MARCA]->(m);
MATCH (ev:EvaluacionEmpleadoPuesto {des_estado: 'OBSERVADO'}), (f:Funcion_Pertenencia {id: 'fp.desempeno_reciente.bajo', vigente: true}), (m:MarcaCalidadDato {codigo: 'DESEMPEÑO_BAJO_RECIENTE'})
WITH ev, f, m, CASE WHEN ev.des_min <= f.centro THEN 1.0 ELSE exp(-1.0 * (ev.des_min - f.centro)^2 / (2.0 * f.sigma^2)) END AS mu_bajo
WHERE mu_bajo > 0.5
MERGE (ev)-[:TIENE_MARCA]->(m);

// ==============================================================================
// 12. S3 - RESULTADO DEL MOTOR DE INFERENCIA EXTERNO (motor_difuso.py): afinidad como intervalo, reglas activadas, ranking y orden
// ==============================================================================
UNWIND [
  {id: 'EV-E101-pv_001', mn: 0.495, mx: 0.495, td: ['media']},
  {id: 'EV-E104-pv_001', mn: 0.601, mx: 0.601, td: ['media']},
  {id: 'EV-E105-pv_001', mn: 0.51, mx: 0.51, td: ['alta']},
  {id: 'EV-E402-pv_002', mn: 0.496, mx: 0.496, td: ['media']},
  {id: 'EV-E401-pv_002', mn: 0.166, mx: 0.5, td: ['baja', 'media']}
] AS a
MATCH (ev:EvaluacionEmpleadoPuesto {id: a.id}), (v3:Version_Modelo_Difuso {id: 'S3-v0.3'}), (v2:Version_Modelo_Difuso {id: 'S2-v0.1'})
SET ev.grado_afinidad_min = a.mn, ev.grado_afinidad_max = a.mx, ev.termino_dominante = a.td,
    ev.metodo = 'Mamdani; Y = MIN, O = MAX, NO = 1 - mu; peso por regla; centroide', ev.submodulo = 'S3'
MERGE (ev)-[c3:CALCULADO_CON]->(v3) SET c3.fecha_calculo = date('2026-10-05')
MERGE (ev)-[c2:CALCULADO_CON]->(v2) SET c2.fecha_calculo = date('2026-10-05');
// Reglas activadas con su fuerza (solo casos puntuales; para el intervalo de E401 se guardan los extremos, no las fuerzas)
UNWIND [
  {ev: 'EV-E101-pv_001', r: 'S3-FA2', f: 0.164},
  {ev: 'EV-E101-pv_001', r: 'S3-FA4', f: 0.164},
  {ev: 'EV-E101-pv_001', r: 'S3-FA6', f: 0.007},
  {ev: 'EV-E101-pv_001', r: 'S3-FB4', f: 0.5},
  {ev: 'EV-E101-pv_001', r: 'S3-FB8', f: 0.007},
  {ev: 'EV-E104-pv_001', r: 'S3-FA3', f: 0.164},
  {ev: 'EV-E104-pv_001', r: 'S3-FA6', f: 0.164},
  {ev: 'EV-E104-pv_001', r: 'S3-FB2', f: 0.556},
  {ev: 'EV-E104-pv_001', r: 'S3-FB8', f: 0.735},
  {ev: 'EV-E104-pv_001', r: 'S2-V3', f: 0.15},
  {ev: 'EV-E105-pv_001', r: 'S3-FA2', f: 0.164},
  {ev: 'EV-E105-pv_001', r: 'S3-FA4', f: 0.164},
  {ev: 'EV-E105-pv_001', r: 'S3-FA6', f: 0.002},
  {ev: 'EV-E105-pv_001', r: 'S3-FB1', f: 0.862},
  {ev: 'EV-E105-pv_001', r: 'S3-FB8', f: 0.002},
  {ev: 'EV-E105-pv_001', r: 'S2-V2', f: 0.751},
  {ev: 'EV-E105-pv_001', r: 'S2-V3', f: 0.191},
  {ev: 'EV-E402-pv_002', r: 'S3-FA2', f: 0.292},
  {ev: 'EV-E402-pv_002', r: 'S3-FA4', f: 0.667},
  {ev: 'EV-E402-pv_002', r: 'S3-FA6', f: 0.007}
] AS a
MATCH (ev:EvaluacionEmpleadoPuesto {id: a.ev}), (r:Regla_Difusa {id: a.r})
MERGE (ev)-[x:ACTIVA]->(r) SET x.fuerza = a.f, x.fecha = date('2026-10-05');
// Ranking por punto medio del intervalo y estado del orden entre pares consecutivos (S3-R10)
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'})-[:PARA]->(p:Puesto_Vacante)
WITH p, ev ORDER BY (ev.grado_afinidad_min + ev.grado_afinidad_max) / 2.0 DESC
WITH p, collect(ev) AS evs
MERGE (rk:Ranking {id: 'RK-' + p.id}) SET rk.submodulo = 'S3'
MERGE (rk)-[:REFERIDO_A]->(p)
WITH rk, evs
UNWIND range(0, size(evs) - 1) AS i
WITH rk, evs[i] AS ev, i
MERGE (rk)-[o:ORDENA]->(ev) SET o.posicion = i + 1;
// S3-R10 y S3-R15: un empate con urgencia no OBSERVADA no es un empate real (faltan las horas): orden no determinado
MATCH (rk:Ranking)-[:REFERIDO_A]->(p:Puesto_Vacante), (rk)-[o1:ORDENA]->(a:EvaluacionEmpleadoPuesto), (rk)-[o2:ORDENA]->(b:EvaluacionEmpleadoPuesto)
WHERE o2.posicion = o1.posicion + 1
WITH p, a, b, a.grado_afinidad_min - b.grado_afinidad_max AS dif_min, a.grado_afinidad_max - b.grado_afinidad_min AS dif_max
MERGE (a)-[pr:PRECEDE_A]->(b)
SET pr.estado_orden = CASE
      WHEN dif_min >= 0.05 OR dif_max <= -0.05 THEN 'determinado'
      WHEN dif_min > -0.05 AND dif_max < 0.05 AND p.urgencia_estado = 'OBSERVADO' THEN 'empate tecnico'
      ELSE 'no determinado' END;
MATCH (a:EvaluacionEmpleadoPuesto)-[:PRECEDE_A {estado_orden: 'no determinado'}]->(b:EvaluacionEmpleadoPuesto), (m:MarcaCalidadDato {codigo: 'ORDEN_NO_DETERMINADO'})
MERGE (a)-[:TIENE_MARCA]->(m) MERGE (b)-[:TIENE_MARCA]->(m);
MATCH (a:EvaluacionEmpleadoPuesto)-[:PRECEDE_A {estado_orden: 'empate tecnico'}]->(b:EvaluacionEmpleadoPuesto), (m:MarcaCalidadDato {codigo: 'EMPATE_TECNICO'})
MERGE (a)-[:TIENE_MARCA]->(m) MERGE (b)-[:TIENE_MARCA]->(m);

// ==============================================================================
// 13. S4 - PRIORIDAD DE RECOMENDACION Y CATEGORIA (PI3 de S4: FZ1-FZ6, regla de corte FZ-C, version S4-FZ-v1)
// ==============================================================================
// 13.1 Advertencias (dato crisp: sin_dato <> sin advertencia), confiabilidad y afinidad central
MATCH (ev:EvaluacionEmpleadoPuesto)
OPTIONAL MATCH (ev)-[:TIENE_MARCA]->(m:MarcaCalidadDato {uso_S4: 'advertencia'})
WITH ev, collect(m.codigo) AS adv
SET ev.advertencias = adv,
    ev.advertencias_estado = CASE WHEN ev.estado_S2 = 'descartado' THEN 'no_aplica'
                                  WHEN ev.grado_afinidad_min IS NULL THEN 'sin_dato' ELSE 'con_dato' END,
    ev.afinidad_central = CASE WHEN ev.grado_afinidad_min IS NULL THEN null ELSE (ev.grado_afinidad_min + ev.grado_afinidad_max) / 2.0 END,
    ev.confiabilidad = CASE WHEN ev.grado_afinidad_min IS NULL THEN null ELSE 1.0 - (ev.grado_afinidad_max - ev.grado_afinidad_min) END;
// 13.2 Fuzzificacion (Cypher): grados de afinidad y confiabilidad con la version vigente del modelo S4
MATCH (ev:EvaluacionEmpleadoPuesto) WHERE ev.afinidad_central IS NOT NULL
MATCH (vm:Version_Modelo_Difuso {id: 'S4-FZ-v1', vigente: true})
MATCH (:Variable_Entrada {submodulo: 'S4'})-[:TIENE_TERMINO]->(t:Termino_Linguistico)-[:DEFINIDO_POR]->(f:Funcion_Pertenencia)-[:PERTENECE_A_VERSION]->(vm)
WITH ev, vm, t, f, CASE t.variable WHEN 'afinidad' THEN ev.afinidad_central ELSE ev.confiabilidad END AS x
WITH ev, vm, t,
  CASE WHEN f.hombro = 'izq' AND x <= f.centro THEN 1.0
       WHEN f.hombro = 'der' AND x >= f.centro THEN 1.0
       ELSE exp(-1.0 * (x - f.centro)^2 / (2.0 * f.sigma^2)) END AS mu
MERGE (ev)-[g:TIENE_GRADO_EN]->(t) SET g.mu = mu
MERGE (ev)-[k:CLASIFICADO_CON]->(vm) SET k.fecha_clasificacion = date('2026-10-05');
// 13.3 Marca de transicion: los dos mayores grados de afinidad difieren en menos de delta_transicion
MATCH (ev:EvaluacionEmpleadoPuesto) WHERE ev.afinidad_central IS NOT NULL SET ev.marca_transicion = false;
MATCH (ev:EvaluacionEmpleadoPuesto)-[g:TIENE_GRADO_EN]->(:Termino_Linguistico {variable: 'afinidad'}), (vm:Version_Modelo_Difuso {id: 'S4-FZ-v1'})
WITH ev, vm, g.mu AS mu ORDER BY mu DESC
WITH ev, vm, collect(mu) AS mus
WHERE mus[0] - mus[1] < vm.delta_transicion
MATCH (m:MarcaCalidadDato {codigo: 'AFINIDAD_EN_TRANSICION'})
MERGE (ev)-[:TIENE_MARCA]->(m)
SET ev.marca_transicion = true;
// 13.4 Resultado del motor externo (agregacion MAX y centroide sobre 1001 puntos): prioridad y regla dominante.
//      Los valores son literales calculados por motor_difuso.py (s4_clasificar) con los mismos grados que se calcularon en 13.2.
UNWIND [
  {id: 'EV-E101-pv_001', p: 0.442, rd: 'S4-FZ4', fd: 0.91},
  {id: 'EV-E104-pv_001', p: 0.431, rd: 'S4-FZ4', fd: 0.923},
  {id: 'EV-E105-pv_001', p: 0.453, rd: 'S4-FZ4', fd: 0.952},
  {id: 'EV-E402-pv_002', p: 0.443, rd: 'S4-FZ4', fd: 0.914},
  {id: 'EV-E401-pv_002', p: 0.397, rd: 'S4-FZ6', fd: 0.619}
] AS a
MATCH (ev:EvaluacionEmpleadoPuesto {id: a.id})
SET ev.prioridad_recomendacion = a.p, ev.regla_dominante = a.rd, ev.fuerza_dominante = a.fd;
UNWIND [
  {ev: 'EV-E101-pv_001', r: 'S4-FZ1', f: 0.141},
  {ev: 'EV-E101-pv_001', r: 'S4-FZ2', f: 0.063},
  {ev: 'EV-E101-pv_001', r: 'S4-FZ4', f: 0.91},
  {ev: 'EV-E101-pv_001', r: 'S4-FZ5', f: 0.347},
  {ev: 'EV-E101-pv_001', r: 'S4-FZ6', f: 0.002},
  {ev: 'EV-E104-pv_001', r: 'S4-FZ2', f: 0.063},
  {ev: 'EV-E104-pv_001', r: 'S4-FZ3', f: 0.294},
  {ev: 'EV-E104-pv_001', r: 'S4-FZ4', f: 0.923},
  {ev: 'EV-E104-pv_001', r: 'S4-FZ5', f: 0.21},
  {ev: 'EV-E104-pv_001', r: 'S4-FZ6', f: 0.002},
  {ev: 'EV-E105-pv_001', r: 'S4-FZ1', f: 0.158},
  {ev: 'EV-E105-pv_001', r: 'S4-FZ2', f: 0.063},
  {ev: 'EV-E105-pv_001', r: 'S4-FZ4', f: 0.952},
  {ev: 'EV-E105-pv_001', r: 'S4-FZ5', f: 0.325},
  {ev: 'EV-E105-pv_001', r: 'S4-FZ6', f: 0.002},
  {ev: 'EV-E402-pv_002', r: 'S4-FZ1', f: 0.142},
  {ev: 'EV-E402-pv_002', r: 'S4-FZ2', f: 0.063},
  {ev: 'EV-E402-pv_002', r: 'S4-FZ4', f: 0.914},
  {ev: 'EV-E402-pv_002', r: 'S4-FZ5', f: 0.345},
  {ev: 'EV-E402-pv_002', r: 'S4-FZ6', f: 0.002},
  {ev: 'EV-E401-pv_002', r: 'S4-FZ2', f: 0.033},
  {ev: 'EV-E401-pv_002', r: 'S4-FZ3', f: 0.033},
  {ev: 'EV-E401-pv_002', r: 'S4-FZ4', f: 0.232},
  {ev: 'EV-E401-pv_002', r: 'S4-FZ5', f: 0.289},
  {ev: 'EV-E401-pv_002', r: 'S4-FZ6', f: 0.619}
] AS a
MATCH (ev:EvaluacionEmpleadoPuesto {id: a.ev}), (r:Regla_Difusa {id: a.r})
MERGE (ev)-[x:ACTIVA]->(r) SET x.fuerza = a.f, x.fecha = date('2026-10-05');
// 13.5 Regla de corte FZ-C: la prioridad se traduce a la categoria canonica con los cortes de la version vigente
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'}) WHERE ev.prioridad_recomendacion IS NOT NULL
MATCH (vm:Version_Modelo_Difuso {id: 'S4-FZ-v1'})
WITH ev, vm, CASE WHEN ev.prioridad_recomendacion >= vm.corte_recomendado THEN 'Recomendado'
                  WHEN ev.prioridad_recomendacion >= vm.corte_reservas THEN 'Recomendado_con_reservas'
                  ELSE 'Baja_prioridad' END AS cn
MATCH (c:Categoria {nombre: cn})
MERGE (ev)-[tc:TIENE_CATEGORIA]->(c)
SET tc.regla_corte = 'FZ-C', tc.prioridad = ev.prioridad_recomendacion, tc.version = vm.id,
    tc.corte_recomendado = vm.corte_recomendado, tc.corte_reservas = vm.corte_reservas,
    ev.regla_aplicada = 'FZ-C (dominante ' + ev.regla_dominante + ')',
    ev.umbrales_utilizados = vm.id + ': corte_recomendado ' + toString(vm.corte_recomendado) + ', corte_reservas ' + toString(vm.corte_reservas);
// S4-R01: el descartado por S2 es Baja prioridad, sin afinidad ni prioridad difusa
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'descartado'}), (c:Categoria {nombre: 'Baja_prioridad'})
MERGE (ev)-[tc:TIENE_CATEGORIA]->(c)
SET tc.regla_corte = 'S4-R01', tc.prioridad = null, ev.regla_aplicada = 'S4-R01';
// S4-A4: valido sin afinidad recibida (faltante, erronea o fuera de rango): no se clasifica ni se redacta
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'}) WHERE NOT (ev)-[:TIENE_CATEGORIA]->(:Categoria)
SET ev.estado_clasificacion = 'NO_CLASIFICADO_AFINIDAD_NO_VALIDA';

// ==============================================================================
// 13b. S4 - EVIDENCIAS (inferencia_difusa incluida) PARA LA JUSTIFICACION DEL LLM
// ==============================================================================
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'}) WHERE ev.prioridad_recomendacion IS NOT NULL
MERGE (e1:Evidencia {id: 'Ev_afinidad_' + ev.id}) SET e1.tipo = 'afinidad', e1.detalle = 'grado de afinidad recibido de S3', e1.valor_min = ev.grado_afinidad_min, e1.valor_max = ev.grado_afinidad_max, e1.fuente = 'S3'
MERGE (ev)-[:RESPALDADO_POR]->(e1)
MERGE (e2:Evidencia {id: 'Ev_fz_' + ev.id}) SET e2.tipo = 'inferencia_difusa', e2.detalle = 'regla dominante ' + ev.regla_dominante + ', fuerza ' + toString(ev.fuerza_dominante), e2.valor = ev.prioridad_recomendacion, e2.fuente = 'modulo_difuso_S4'
MERGE (ev)-[:RESPALDADO_POR]->(e2);
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'}) WHERE ev.prioridad_recomendacion IS NOT NULL
UNWIND ev.advertencias AS a
MERGE (e:Evidencia {id: 'Ev_adv_' + a + '_' + ev.id}) SET e.tipo = 'advertencia', e.detalle = a, e.fuente = 'S3'
MERGE (ev)-[:RESPALDADO_POR]->(e);
MATCH (ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido', deseables_estado: 'EVALUADAS'})
UNWIND ev.deseables_faltantes AS d
MERGE (e:Evidencia {id: 'Ev_deseable_' + d + '_' + ev.id}) SET e.tipo = 'aptitud_deseable_faltante', e.detalle = d, e.fuente = 'S2'
MERGE (ev)-[:RESPALDADO_POR]->(e);

// ==============================================================================
// 13c. S4 - LISTADO FINAL (criterio de orden PROVISIONAL: M8 pendiente de RR. HH.)
// ==============================================================================
MATCH (p:Puesto_Vacante)
OPTIONAL MATCH (p)<-[:PARA]-(ev:EvaluacionEmpleadoPuesto)
WITH p, count(CASE WHEN ev.estado_S2 = 'valido' THEN 1 END) AS nv, count(CASE WHEN ev.estado_S2 = 'descartado' THEN 1 END) AS nd
MERGE (lf:Listado_Final {id: 'LF-' + p.id})
SET lf.criterio_orden = 'PROVISIONAL', lf.criterio_orden_candidato = 'prioridad_recomendacion descendente',
    lf.criterio_desempate = 'sin definir', lf.n_candidatos_validos = nv, lf.n_descartados = nd, lf.submodulo = 'S4'
MERGE (lf)-[:REFERIDO_A]->(p);
MATCH (lf:Listado_Final)-[:REFERIDO_A]->(p:Puesto_Vacante)<-[:PARA]-(ev:EvaluacionEmpleadoPuesto {estado_S2: 'valido'}) WHERE ev.prioridad_recomendacion IS NOT NULL
WITH lf, ev ORDER BY ev.prioridad_recomendacion DESC
WITH lf, collect(ev) AS evs
UNWIND range(0, size(evs) - 1) AS i
WITH lf, evs[i] AS ev, i
MERGE (lf)-[inc:INCLUYE]->(ev) SET inc.posicion_prioridad = i + 1;
MATCH (lf:Listado_Final)-[inc:INCLUYE]->(ev:EvaluacionEmpleadoPuesto), (:Ranking)-[o:ORDENA]->(ev)
SET inc.posicion_afinidad = o.posicion, inc.coinciden_ambos_ordenes = (o.posicion = inc.posicion_prioridad);
// S2-R09 / S4-R06: sin validos, el listado queda vacio y se informa el conteo por motivo y el motivo critico
MATCH (lf:Listado_Final {n_candidatos_validos: 0})-[:REFERIDO_A]->(p:Puesto_Vacante)<-[:PARA]-(ev:EvaluacionEmpleadoPuesto)
UNWIND ev.motivos_descarte AS m
WITH lf, m, count(*) AS n ORDER BY n DESC
WITH lf, collect({m: m, n: n}) AS cs
SET lf.conteo_motivos = [x IN cs | x.m + ': ' + toString(x.n)],
    lf.motivo_critico = [x IN cs WHERE x.n = cs[0].n | x.m];

// ==============================================================================
// 14. INSTANCIA_DE: enlace de cada nodo con su frame
// ==============================================================================
MATCH (n:Pedido_Cobertura), (f:Frame {nombre: 'Pedido_Cobertura'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Puesto_Vacante), (f:Frame {nombre: 'Puesto_Vacante'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Servicio), (f:Frame {nombre: 'Servicio'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Tipo_Servicio), (f:Frame {nombre: 'Tipo_Servicio'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Aptitud), (f:Frame {nombre: 'Aptitud'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Zona), (f:Frame {nombre: 'Zona'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Turno), (f:Frame {nombre: 'Turno'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Traslado), (f:Frame {nombre: 'Traslado'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Empleado), (f:Frame {nombre: 'Empleado'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Evaluacion_Desempeno), (f:Frame {nombre: 'Evaluacion_Desempeno'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:EvaluacionEmpleadoPuesto), (f:Frame {nombre: 'EvaluacionEmpleadoPuesto'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Ranking), (f:Frame {nombre: 'Ranking'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:MarcaCalidadDato), (f:Frame {nombre: 'MarcaCalidadDato'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Expresion_Urgencia), (f:Frame {nombre: 'Expresion_Urgencia'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Nivel_Urgencia), (f:Frame {nombre: 'Nivel_Urgencia'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Version_Modelo_Difuso), (f:Frame {nombre: 'Version_Modelo_Difuso'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Categoria), (f:Frame {nombre: 'Categoria'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Listado_Final), (f:Frame {nombre: 'Listado_Final'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Evidencia), (f:Frame {nombre: 'Evidencia'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Variable_Linguistica), (f:Frame {nombre: 'Variable_Linguistica'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Termino_Linguistico), (f:Frame {nombre: 'Termino_Linguistico'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Funcion_Pertenencia), (f:Frame {nombre: 'Funcion_Pertenencia'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Regla_Difusa), (f:Frame {nombre: 'Regla_Difusa'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Regla_Crisp), (f:Frame {nombre: 'Regla_Crisp'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Grupo_Reglas), (f:Frame {nombre: 'Grupo_Reglas'}) MERGE (n)-[:INSTANCIA_DE]->(f);
MATCH (n:Actor), (f:Frame {nombre: 'Actor'}) MERGE (n)-[:INSTANCIA_DE]->(f);
