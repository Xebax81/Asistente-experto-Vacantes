// PI4 - S1 - Complemento sobre el grafo del PG2 (Grupo_5_PG2_U1_carga.cypher)
// Copia del archivo entregado en el PI4 de S1. En el PG3 deja de ser opcional:
// sin él, la regla S1-R02 no tiene marcadores de exigencia en el grafo y las
// aptitudes escritas de otra forma («manejo de maquinaria industrial») no se
// reconocen. Se carga una vez, después del script del PG2:
//     python -m api.main --cargar neo4j/S1_PI4_complemento.cypher
// No crea etiquetas ni relaciones nuevas: completa slots que el Frame ya declaraba
// (Aptitud.sinonimos) y guarda en la regla S1-R02 la lista de marcadores de exigencia.
// Todo queda como provisional, con fuente y estado de validación, hasta la entrevista con el reclutador.

// 1. Sinónimos de aptitudes (slot 'sinonimos' del Frame Aptitud)
UNWIND [
  {n: 'limpieza_hospitalaria',       s: ['limpieza de hospitales', 'limpieza sanitaria', 'limpieza de clinicas']},
  {n: 'manejo_residuos_patogenicos', s: ['residuos patogenicos', 'residuos hospitalarios', 'residuos peligrosos']},
  {n: 'manejo_maquinaria_industrial',s: ['maquinaria industrial', 'maquinas industriales', 'maquinaria pesada']},
  {n: 'trabajo_en_altura',           s: ['trabajo en alturas', 'altura', 'curso de altura']}
] AS x
MATCH (a:Aptitud {nombre: x.n})
SET a.sinonimos = x.s, a.sinonimos_fuente = 'diseno_del_grupo (PI4 S1)', a.sinonimos_estado_validacion = 'provisional';

// 2. Marcadores de exigencia de la regla S1-R02 (antes estaban solo en el texto del PI2)
MATCH (r:Regla_Crisp {id: 'S1-R02'})
SET r.marcadores = ['excluyente', 'indispensable', 'obligatorio', 'obligatoria', 'imprescindible',
                    'si o si', 'tiene que tener', 'debe tener', 'es requisito', 'sin excepcion'],
    r.marcadores_fuente = 'PI2 S1 (R2) + diseno_del_grupo', r.marcadores_estado_validacion = 'provisional';

// 3. Verificación
MATCH (a:Aptitud) RETURN a.nombre AS aptitud, a.sinonimos AS sinonimos;
