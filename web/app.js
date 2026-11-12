'use strict';

const $ = (s) => document.querySelector(s);
const mensajes = $('#mensajes');
const traza = $('#traza');
const formulario = $('#formulario');
const campo = $('#texto');
const boton = $('#enviar');

// Casos precargados. Los cuatro primeros son los casos de inferencia del PG2
// (sección d.3), con el texto exacto de ped_001 a ped_004 del script de carga:
// así la defensa muestra que el integrado recalcula lo que el PG2 tenía cargado.
// El control de completitud de S1 queda probado por dos casos del PI4: C3 (igual al caso 3
// del PG2: faltan servicio y turno, S1-R01) y C4 (zona informada y no reconocida, S1-R07).
const EJEMPLOS = [
  { origen: 'PG2 · caso 1 · S1→S4', texto: 'Necesito un reemplazo para el turno tarde en el Hospital Central, con limpieza hospitalaria y, preferentemente, manejo de residuos patogénicos, para mañana.' },
  { origen: 'PG2 · caso 2 · datos no observados', texto: 'Necesito cubrir el turno noche en la Clínica Luján, con limpieza hospitalaria, para la semana que viene.' },
  { origen: 'PG2 · caso 3 = PI4 · S1 · C3 · pedido incompleto', texto: 'Necesito cubrir un turno, urgente.' },
  { origen: 'PG2 · caso 4 · listado vacío', texto: 'Necesito cubrir el turno noche en la Fábrica Sur, urgente, dentro de cinco días.' },
  { origen: 'PI4 · S1 · C4 · zona no reconocida', texto: 'Necesito una persona para el Supermercado Norte en el turno mañana, en la zona de Chacras, pasado mañana.' },
];

const NOMBRES = {
  S1_requisitos: 'S1 · Requisitos de vacante',
  S2_aptitud: 'S2 · Aptitud y disponibilidad',
  S3_afinidad: 'S3 · Afinidad y priorización',
  S4_explicacion: 'S4 · Explicación y listado final',
  S1: 'S1 · Requisitos de vacante',
  S2: 'S2 · Aptitud y disponibilidad',
  S3: 'S3 · Afinidad y priorización',
  S4: 'S4 · Explicación y listado final',
  cadena_completa: 'Cadena completa S1 → S2 → S3 → S4',
  fuera_de_dominio: 'Fuera de dominio',
  error: 'Error',
};

const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// --------------------------------------------------------------- mensajes
function agregar(clase, html) {
  const d = document.createElement('div');
  d.className = 'msg ' + clase;
  d.innerHTML = html;
  mensajes.appendChild(d);
  mensajes.scrollTop = mensajes.scrollHeight;
  return d;
}

// --------------------------------------------------------------- ranking
function fichasDe(r) {
  // El listado puede venir de S4 directo o de cada puesto de la cadena completa.
  if (r.listados && r.listados.length) return r.listados;
  const f = r.datos && r.datos.fichas;
  if (f && f.length) return [{ puesto: f[0].puesto, servicio: f[0].servicio, fichas: f }];
  return [];
}

function afinidadTexto(f) {
  const a = f.afinidad || [];
  if (a[0] === null || a[0] === undefined) return '—';
  if (a[0] === a[1]) return a[0].toFixed(3);
  return `${a[0].toFixed(3)} – ${a[1].toFixed(3)}`;
}

function claseCategoria(c) {
  if (c === 'Recomendado') return 'cat-alta';
  if (c === 'Baja_prioridad') return 'cat-baja';
  return 'cat-media';
}

function tablaCandidatos(r) {
  const listados = fichasDe(r);
  if (!listados.length) return '';

  return listados.map((l) => {
    const filas = l.fichas.map((f) => {
      const notas = [];
      if (f.deseables_faltantes && f.deseables_faltantes.length) {
        notas.push('le falta ' + f.deseables_faltantes.join(', '));
      } else if (f.deseables_estado === 'SIN_DATO') {
        notas.push('deseables no evaluadas');
      }
      if (f.advertencias && f.advertencias.length) notas.push(f.advertencias.join(', '));
      if ((f.confiabilidad ?? 1) < 1) notas.push(`confiabilidad ${f.confiabilidad}`);
      if (['empate tecnico', 'no determinado'].includes(f.estado_orden_con_siguiente)) {
        notas.push(`${f.estado_orden_con_siguiente} con el siguiente: no hay un ganador`);
      }
      const empatado = ['empate tecnico', 'no determinado']
        .includes(f.estado_orden_con_siguiente);
      const posicion = f.posicion_por_prioridad ?? '–';
      // Indicación de la cátedra para el PG3: el orden conserva su carácter
      // provisional. Si el sistema no determinó el orden con el siguiente, la
      // posición se marca como empatada en vez de mostrarse como un puesto ganado.
      return `<tr class="${empatado ? 'empatado' : ''}">
        <td class="pos">${posicion}${empatado
          ? '<span class="empate" title="El sistema no determinó el orden con el siguiente candidato">=</span>'
          : ''}</td>
        <td><b>${esc(f.empleado)}</b><span class="leg">${esc(f.legajo)}</span></td>
        <td><span class="cat ${claseCategoria(f.categoria)}">${esc(
          String(f.categoria || '').replace(/_/g, ' '))}</span></td>
        <td class="num">${f.prioridad ?? '–'}</td>
        <td class="num">${afinidadTexto(f)}</td>
        <td class="notas">${esc(notas.join(' · '))}</td>
      </tr>`;
    }).join('');

    return `<div class="ranking">
      <div class="ranking-cab">Candidatos · ${esc(l.servicio || '')} <span>${esc(l.puesto || '')}</span></div>
      <table>
        <thead><tr><th>#</th><th>Candidato</th><th>Categoría</th>
          <th class="num">Prioridad</th><th class="num">Afinidad</th><th>Observaciones</th></tr></thead>
        <tbody>${filas}</tbody>
      </table>
      <div class="ranking-pie">El orden es <b>provisional</b>: lo calcula el sistema y
        todavía no responde a un criterio validado por RR. HH. Las posiciones marcadas
        con «=» están empatadas o sin orden determinado; el sistema no desempata.
        La decisión final es del reclutador.</div>
    </div>`;
  }).join('');
}

function avisoSimulacion(r) {
  // Indicación de la cátedra para el PG3: mantener separada la simulación de la
  // evaluación original. Se marca de forma visible y se muestran los dos valores.
  const d = r.datos;
  if (!d || !d.hipotetico) return '';
  const base = Array.isArray(d.base_grafo) ? d.base_grafo[0] : d.base_grafo;
  const sim = Array.isArray(d.simulada) ? d.simulada[0] : d.simulada;
  const cambios = Object.entries(d.entrada_simulada || {})
    .map(([k, v]) => `${esc(k.replace(/_/g, ' '))}: ${esc(v)}`).join(' · ');
  return `<div class="simulacion">
    <div class="simulacion-cab">Simulación hipotética — no se guarda en la base</div>
    <div class="simulacion-cuerpo">
      <div><b>${esc(d.empleado || '')}</b> ${esc(d.legajo ? '(' + d.legajo + ')' : '')}</div>
      ${cambios ? `<div class="campo-sim">Se cambió: ${cambios}</div>` : ''}
      <div class="comparacion">
        <span><em>registrada</em><b>${base ?? '–'}</b></span>
        <span class="flecha">→</span>
        <span><em>simulada</em><b>${sim ?? '–'}</b></span>
      </div>
      <div class="campo-sim">La evaluación registrada y la categoría
        «${esc(String(d.categoria_S4 || '').replace(/_/g, ' '))}» no cambian.</div>
    </div></div>`;
}

function pie(r) {
  const partes = [];
  const nombre = NOMBRES[r.submodulo] || r.submodulo || '—';
  partes.push(`<span class="etq">${esc(nombre)}</span>`);
  if (r.fidelidad && typeof r.fidelidad === 'object') {
    // Cadena completa: una validación por submódulo que explicó (S1 y S4).
    Object.entries(r.fidelidad).forEach(([sub, v]) => {
      [].concat(v).filter(Boolean).forEach((x) => {
        const ok = String(x).startsWith('OK') || String(x).startsWith('sin LLM');
        partes.push(`<span class="etq ${ok ? 'ok' : 'alerta'}">${esc(sub)} fidelidad: ${esc(x)}</span>`);
      });
    });
  } else if (r.fidelidad) {
    const ok = String(r.fidelidad).startsWith('OK');
    partes.push(`<span class="etq ${ok ? 'ok' : 'alerta'}">fidelidad: ${esc(r.fidelidad)}</span>`);
  }
  if (r.aclaracion) partes.push('<span class="etq alerta">pide aclaración</span>');
  if (r.esperando_dato && r.esperando_dato.length) {
    partes.push(`<span class="etq alerta">esperando: ${esc(r.esperando_dato.join(', '))}</span>`);
  }
  const consultas = (r.traza || []).filter((p) => p.etapa === 'cypher').length;
  const escrituras = (r.traza || []).filter((p) => p.etapa === 'cypher_escritura').length;
  if (consultas) partes.push(`<span>${consultas} consulta${consultas > 1 ? 's' : ''} a Neo4j</span>`);
  if (escrituras) partes.push(`<span>${escrituras} escritura${escrituras > 1 ? 's' : ''}</span>`);
  if (r.segundos) partes.push(`<span>${r.segundos}s</span>`);
  return `<div class="pie">${partes.join('')}</div>`;
}

// --------------------------------------------------------------- trazabilidad
function bloque(titulo, numero, cuerpo, clase) {
  return `<details class="etapa ${clase || ''}" ${clase === 'abierta' ? 'open' : ''}>
    <summary>${esc(titulo)}${numero ? `<span class="num">${esc(numero)}</span>` : ''}</summary>
    <div class="cuerpo">${cuerpo}</div></details>`;
}

function pintarTraza(r) {
  const pasos = r.traza || [];
  if (!pasos.length) {
    traza.className = 'traza-vacia';
    traza.textContent = 'Esta respuesta no consultó la base de conocimiento.';
    return;
  }
  traza.className = '';
  let html = '';

  // 1. enrutamiento
  const ruta = pasos.find((p) => p.etapa === 'enrutamiento');
  if (ruta) {
    const d = ruta.datos || {};
    html += bloque('1 · Prompt maestro — enrutamiento', `${ruta.segundos}s`,
      `<div class="campo"><b>Submódulo:</b> ${esc(NOMBRES[d.submodulo] || d.submodulo)}</div>
       <div class="campo"><b>Confianza:</b> ${esc(d.confianza || '—')}</div>
       <pre>${esc(JSON.stringify(d, null, 2))}</pre>`, 'abierta');
  }

  // 2. extracción por submódulo
  pasos.filter((p) => p.etapa === 'extraccion').forEach((p, i) => {
    html += bloque(`2.${i + 1} · Extracción con LLM — ${p.submodulo}`,
      `${p.segundos}s · ${p.intentos} intento${p.intentos > 1 ? 's' : ''}`,
      `<pre>${esc(JSON.stringify(p.datos, null, 2))}</pre>`);
  });

  // 3. consultas Cypher
  const lecturas = pasos.filter((p) => p.etapa === 'cypher');
  if (lecturas.length) {
    const filas = lecturas.map((p) => `
      <div class="campo"><b class="cypher">${esc(p.consulta)}</b> · ${p.filas} fila(s) · ${p.ms} ms
      <pre>${esc(JSON.stringify(p.parametros, null, 2))}</pre></div>`).join('');
    html += bloque('3 · Consultas a Neo4j (solo lectura, parametrizadas)',
      `${lecturas.length}`, filas, 'abierta');
  }

  // 4. escrituras
  const escrituras = pasos.filter((p) => p.etapa === 'cypher_escritura');
  if (escrituras.length) {
    const cuenta = {};
    escrituras.forEach((p) => { cuenta[p.consulta] = (cuenta[p.consulta] || 0) + 1; });
    const filas = Object.entries(cuenta).map(([n, c]) =>
      `<div class="campo"><b class="cypher">${esc(n)}</b> · ${c} vez/veces</div>`).join('');
    html += bloque('4 · Escrituras en el grafo', `${escrituras.length}`,
      filas + '<div class="campo">El pedido, el puesto, las evaluaciones, la afinidad, ' +
      'la categoría y el listado final quedan guardados y son auditables desde Neo4j.</div>',
      'escritura');
  }

  // 5. explicación y fidelidad
  pasos.filter((p) => p.etapa === 'explicacion').forEach((p, i) => {
    const ok = p.fidelidad === 'OK';
    // Si la explicación cayó al texto de respaldo (regla A6), acá se ve POR QUÉ: los
    // motivos del último rechazo del validador y lo que había escrito el modelo.
    const motivos = (p.motivos_rechazo || []).map((m) => `<li>${esc(m)}</li>`).join('');
    html += bloque(`5.${i + 1} · Explicación con LLM — ${p.submodulo}`,
      `${p.segundos}s · ${p.intentos} intento${p.intentos > 1 ? 's' : ''}`,
      `<div class="campo"><b>Validación de fidelidad:</b>
         <span class="etq ${ok ? 'ok' : 'alerta'}">${esc(p.fidelidad)}</span>
         ${p.salida_truncada ? '<span class="etq alerta">salida cortada por max_tokens</span>' : ''}</div>
       ${motivos ? `<div class="campo"><b>${ok ? 'Rechazos antes de aceptar' : 'Por qué se rechazó (se entregó el respaldo A6)'}:</b><ul class="motivos">${motivos}</ul></div>` : ''}
       ${p.texto_rechazado ? `<details class="rechazado"><summary>Texto rechazado del modelo</summary><pre>${esc(p.texto_rechazado)}</pre></details>` : ''}
       ${p.citables !== undefined ? `<div class="campo"><b>Evidencias citables:</b> ${p.citables}</div>` : ''}
       ${p.datos && p.datos.citas ? `<pre>${esc(JSON.stringify(p.datos.citas, null, 2))}</pre>` : ''}`,
      ok ? '' : 'abierta');
  });

  // 6. etapas de la cadena
  if (r.etapas && r.etapas.length) {
    const filas = r.etapas.map((e) =>
      `<div class="campo"><b>${esc(NOMBRES[e.submodulo] || e.submodulo)}</b> — ${esc(
        Object.entries(e).filter(([k]) => k !== 'submodulo' && k !== 'respuesta')
          .map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(' · '))}</div>`).join('');
    html += bloque('6 · Cadena recorrida', `${r.etapas.length} etapas`, filas, 'abierta');
  }

  traza.innerHTML = html;
}

// --------------------------------------------------------------- envío
let ocupado = false;

async function enviar(texto) {
  if (ocupado || !texto.trim()) return;
  ocupado = true;
  boton.disabled = true;
  agregar('usuario', esc(texto));
  campo.value = '';
  const esperando = agregar('asistente pensando', 'Consultando la base de conocimiento…');

  try {
    const res = await fetch('/api/consulta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto }),
    });
    const r = await res.json();
    esperando.remove();
    const clase = r.submodulo === 'error' ? 'asistente error' : 'asistente';
    agregar(clase, esc(r.respuesta || 'Sin respuesta.') + avisoSimulacion(r) +
            tablaCandidatos(r) + pie(r));
    // Si el pedido quedó en espera, se avisa que la próxima respuesta lo completa.
    if (r.esperando_dato && r.esperando_dato.length) {
      campo.placeholder = `Respondé con ${r.esperando_dato.join(' y ')}… (o escribí otra consulta)`;
    } else {
      campo.placeholder = 'Escribí tu consulta…  (Enter envía, Shift+Enter hace salto de línea)';
    }
    pintarTraza(r);
  } catch (e) {
    esperando.remove();
    agregar('asistente error', 'No se pudo contactar al servidor: ' + esc(e.message));
  } finally {
    ocupado = false;
    boton.disabled = false;
    campo.focus();
  }
}

formulario.addEventListener('submit', (e) => { e.preventDefault(); enviar(campo.value); });
campo.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(campo.value); }
});

// --------------------------------------------------------------- arranque
const cajaEjemplos = $('#ejemplos');
const botonEjemplos = $('#verEjemplos');
function mostrarEjemplos(abrir) {
  cajaEjemplos.hidden = !abrir;
  botonEjemplos.setAttribute('aria-expanded', String(abrir));
  botonEjemplos.textContent = (abrir ? '− Ocultar casos de prueba' : `+ Casos de prueba (${EJEMPLOS.length})`);
}
botonEjemplos.onclick = () => mostrarEjemplos(cajaEjemplos.hidden);
EJEMPLOS.forEach((e) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.title = e.texto;
  const o = document.createElement('span');
  o.className = 'origen';
  o.textContent = e.origen;
  const t = document.createElement('span');
  t.className = 'texto-ej';
  t.textContent = e.texto;
  b.append(o, t);
  b.onclick = () => { mostrarEjemplos(false); enviar(e.texto); };
  cajaEjemplos.appendChild(b);
});
mostrarEjemplos(false);

fetch('/api/estado').then((r) => r.json()).then((e) => {
  const el = $('#estado');
  const grafoOk = e.grafo && e.grafo.ok;
  const faltan = (e.prompts_faltantes || []).length;
  el.className = 'estado ' + (grafoOk && !faltan ? 'ok' : 'mal');
  el.textContent = `${e.config.llm_proveedor} · ${e.config.llm_modelo} · ` +
    (grafoOk ? 'Neo4j OK' : 'Neo4j con problemas') +
    (faltan ? ` · faltan ${faltan} prompts` : '');
  el.title = (e.grafo.informe || []).join('\n') +
    (faltan ? '\n\nFaltan: ' + e.prompts_faltantes.map((p) => p[1]).join(', ') : '');
}).catch(() => { $('#estado').textContent = 'servidor sin responder'; });

campo.focus();
