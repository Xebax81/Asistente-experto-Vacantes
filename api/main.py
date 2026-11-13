"""API y servidor web del asistente integrado (PG3).

Entrada unica del usuario (lo que pide la consigna: "API o interfaz: entrada unica
para el usuario"). Sirve tambien la interfaz web estatica de web/.

  python -m api.main            levanta el servidor en http://localhost:8000
  python -m api.main --check    verifica grafo, prompts, LLM y motor difuso
  python -m api.main --casos [E2E-1 ...] [--pausa 20]   corre las pruebas E2E de pruebas/casos_e2e.py
  python -m api.main -q "..."   una consulta por linea de comandos
  python -m api.main --recalcular pv_001              corre S3+S4 y PERSISTE
  python -m api.main --recalcular pv_001 --simular    solo compara, no escribe
  python -m api.main --modelos  lista los modelos que habilita tu clave de Gemini
  python -m api.main --cargar neo4j/Grupo_5_PG2_U1_carga.cypher   instala el grafo del PG2
  python -m api.main --conteos  cuenta los nodos por etiqueta
  python -m api.main --esquema  vuelca etiquetas, relaciones y propiedades del grafo
  python -m api.main --limpiar  borra las vacantes de prueba que creó el asistente
  python -m api.main --catalogos  muestra servicios, zonas, turnos y aptitudes cargados
  python -m api.main --depurar          revisión del punto 1 (muestra, no escribe)
  python -m api.main --depurar --aplicar  aplica las correcciones
  python -m api.main --exportar  exporta el grafo a neo4j/Grupo_5_PG3_export.cypher y .json
"""
import json
import sys

from core import config, prompts
from core.grafo import ErrorGrafo, Grafo
from orquestador import asistente
from submodulos import inferencia

WEB = config.RAIZ / 'web'

# FastAPI solo hace falta para levantar el servidor. Los comandos de diagnostico
# (--check, --modelos, -q, --casos, --recalcular) tienen que funcionar aunque
# todavia no se hayan instalado las dependencias web.
try:
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    HAY_FASTAPI = True
except ImportError:
    HAY_FASTAPI = False
    BaseModel = object

if HAY_FASTAPI:
    app = FastAPI(title='Asistente Experto — Cobertura de Vacantes Internas (Grupo 5, PG3)',
                  version=config.VERSION_SISTEMA)
else:
    class _SinFastAPI:
        """Sustituto inerte: deja que el modulo se importe y los decoradores no hagan nada."""
        def __getattr__(self, _):
            return lambda *a, **k: (lambda f: f)
    app = _SinFastAPI()


class Consulta(BaseModel):
    texto: str
    sesion: str = 'web'


@app.post('/api/consulta')
def api_consulta(c: Consulta):
    if not (c.texto or '').strip():
        return JSONResponse({'respuesta': 'Escribí una consulta.'}, status_code=400)
    return asistente.responder(c.texto.strip(), sesion=c.sesion or 'web')


@app.post('/api/reiniciar')
def api_reiniciar(c: Consulta):
    """Olvida el pedido en espera (el botón de empezar de nuevo en la interfaz)."""
    asistente.olvidar_pendiente(c.sesion or 'web')
    return {'ok': True}


@app.get('/api/puestos')
def api_puestos():
    try:
        with Grafo() as g:
            return {'puestos': g.leer('S2-Q2b-puestos-registrados')}
    except ErrorGrafo as e:
        return JSONResponse({'error': str(e)}, status_code=503)


@app.post('/api/recalcular/{puesto}')
def api_recalcular(puesto: str):
    """Corre S3 + S4 sobre un puesto y persiste el resultado."""
    with Grafo() as g:
        return inferencia.recalcular_puesto(g, puesto, persistir=config.ESCRITURA_HABILITADA)


@app.get('/api/estado')
def api_estado():
    estado = {'config': config.resumen(), 'prompts_faltantes': prompts.faltantes()}
    try:
        with Grafo() as g:
            ok, informe = g.verificar()
            estado['grafo'] = {'ok': ok, 'informe': informe}
    except ErrorGrafo as e:
        estado['grafo'] = {'ok': False, 'informe': [str(e)]}
    return estado


@app.get('/')
def inicio():
    return FileResponse(WEB / 'index.html')


if HAY_FASTAPI and WEB.exists():
    app.mount('/web', StaticFiles(directory=str(WEB)), name='web')


# ==================================================================== CLI
def check():
    print('=' * 70)
    print('VERIFICACION DEL ASISTENTE INTEGRADO —', config.VERSION_SISTEMA)
    print('=' * 70)
    for k, v in config.resumen().items():
        print(f'  {k}: {v}')

    print('\n[0] Dependencias')
    faltan_deps = []
    for modulo, paquete in (('neo4j', 'neo4j'), ('numpy', 'numpy'),
                            ('fastapi', 'fastapi'), ('uvicorn', 'uvicorn')):
        try:
            __import__(modulo)
        except ImportError:
            faltan_deps.append(paquete)
    if faltan_deps:
        print(f'  XX faltan: {", ".join(faltan_deps)}')
        print('     instalalas con:  pip install -r requirements.txt')
        print(f'     (Python en uso: {sys.executable})')
    else:
        print('  OK están instaladas las cuatro dependencias')

    print('\n[1] Prompts')
    faltan = prompts.faltantes()
    if faltan:
        for clave, archivo in faltan:
            print(f'  XX falta {archivo}  (prompt "{clave}") — ver prompts/README.md')
    else:
        print('  OK los 10 prompts están en prompts/')

    print('\n[2] Motor difuso (parámetros de los PI3)')
    import subprocess
    r = subprocess.run([sys.executable, '-m', 'core.motor_difuso'],
                       capture_output=True, text=True, cwd=str(config.RAIZ))
    ultima = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or ['sin salida']
    print('  ' + ultima[0])

    print('\n[3] Base de conocimiento (Neo4j)')
    if 'databases.neo4j.io' in config.NEO4J_URI:
        print(f'  .. Aura detectada. NEO4J_BASE = "{config.NEO4J_BASE}", '
              f'NEO4J_USUARIO = "{config.NEO4J_USUARIO}"')
        print('     Estos dos valores NO son iguales en todas las instancias: según el')
        print('     tipo de instancia pueden ser "neo4j" o el id (p. ej. "62da1c6d").')
        print('     El archivo de credenciales que Aura te hace descargar al crearla manda:')
        print('     copiá NEO4J_DATABASE -> NEO4J_BASE y NEO4J_USERNAME -> NEO4J_USUARIO.')
    try:
        with Grafo() as g:
            ok, informe = g.verificar()
            for linea in informe:
                print('  ' + linea)
            print('  ' + ('OK el grafo responde a todas las consultas del catálogo'
                          if ok else 'XX hay consultas que no responden: revisar arriba'))
    except ErrorGrafo as e:
        print(f'  XX no se pudo conectar: {e}')

    print('\n[4] Modelo de lenguaje')
    from core.llm import disponible, modelo_en_uso
    print(f'  modelo en uso: {modelo_en_uso()}')
    ok, error = disponible()
    if ok:
        print(f'  OK responde y devuelve JSON (modelo confirmado: {modelo_en_uso()})')
    else:
        print(f'  XX {error}')
    print('=' * 70)


def recalcular(puesto, simular=False):
    """Corre S3 + S4 sobre un puesto y compara con lo que ya hay en el grafo.

    Con --simular no escribe nada: sirve para verificar que el pipeline reproduce
    los valores que el PG2 cargó a mano, que es la prueba de regresión del PG3.
    """
    with Grafo() as g:
        antes = {f['legajo']: f for f in g.leer('PG3-estado-actual', puesto=puesto)}
        inf = inferencia.recalcular_puesto(g, puesto, persistir=not simular)

        if inf.get('error'):
            print(f"XX {inf['error']}")
            return

        modo = 'SIMULACION (no se escribió nada)' if simular else 'RECALCULADO Y GUARDADO'
        print(f"{puesto} — {modo}")
        print(f"  {inf['n_validos']} válidos, {inf['n_descartados']} descartados, "
              f"criterio de orden {inf['criterio_orden']}\n")

        enc = f"  {'legajo':7}{'empleado':16}{'afinidad':>20}{'prioridad':>22}  categoría"
        print(enc)
        print('  ' + '-' * (len(enc) - 2))
        iguales = distintos = 0
        for c in inf['candidatos']:
            a = antes.get(c['legajo'], {})
            viejo_af = (f"{a.get('amin'):.3f}" if a.get('amin') is not None else '—')
            if a.get('amin') is not None and a.get('amax') != a.get('amin'):
                viejo_af += f"..{a['amax']:.3f}"
            nuevo_af = f"{c['amin']:.3f}" + (f"..{c['amax']:.3f}" if c['amax'] != c['amin'] else '')
            viejo_pr = f"{a.get('prioridad'):.3f}" if a.get('prioridad') is not None else '—'

            coincide = (a.get('amin') is not None
                        and abs(a['amin'] - c['amin']) < 0.002
                        and abs((a.get('prioridad') or -9) - c['prioridad']) < 0.002
                        and a.get('categoria') == c['categoria'])
            marca = 'OK' if coincide else ('..' if a.get('amin') is None else 'XX')
            if a.get('amin') is not None:
                iguales += 1 if coincide else 0
                distintos += 0 if coincide else 1
            print(f"{marca} {c['legajo']:7}{c['empleado'][:15]:16}"
                  f"{viejo_af:>9} -> {nuevo_af:<8}"
                  f"{viejo_pr:>10} -> {c['prioridad']:<8.3f}  {c['categoria']}")

        for t_ in inf['orden']:
            print(f"     orden {t_['anterior']} -> {t_['siguiente']}: "
                  f"{t_['estado_orden']} (diferencia {t_['diferencia']})")

        if iguales or distintos:
            print(f"\n  {iguales} coinciden con lo que ya había en el grafo, {distintos} difieren.")
            if distintos:
                print('  Las diferencias son esperables si el PG2 cargó entradas (experiencia,')
                print('  desempeño, cercanía) que hoy el grafo no tiene por evaluación.')
        if simular:
            print('\n  Nada de esto se guardó. Sacá --simular para persistirlo.')


def depurar(aplicar=False):
    """Punto 1 de la consigna: revisión y depuración final.

    Sin --aplicar solo informa. Con --aplicar corrige.
    """
    from core import depuracion

    modo = 'APLICANDO CORRECCIONES' if aplicar else 'REVISIÓN (no se escribe nada)'
    print('=' * 70)
    print(f'DEPURACIÓN DE LA BASE DE CONOCIMIENTO — {modo}')
    print('=' * 70)

    with Grafo() as g:
        print('\n[1] Parámetros difusos en el grafo')
        ok, informe = depuracion.comparar_parametros(g)
        for linea in informe:
            print('  ' + linea)
        if aplicar:
            print('\n  Escribiendo los parámetros del motor verificado:')
            n = depuracion.escribir_parametros(g)
            print(f'  {n} funciones de pertenencia escritas.')
            d = depuracion.borrar_duplicadas(g)
            if d:
                print(f'  {d} variables duplicadas eliminadas.')
            ok2, informe2 = depuracion.comparar_parametros(g)
            for linea in informe2:
                print('  ' + linea)
        elif not ok:
            print('  --> con --aplicar se escriben tomándolos de core/motor_difuso.py')

        print('\n[2] Entradas de S3 a nivel de empleado')
        print('  (experiencia y desempeño: el PG2 los dejó por evaluación, no por empleado)')
        n = depuracion.normalizar_empleados(g, persistir=aplicar)
        if not aplicar and n:
            print(f'\n  --> con --aplicar se promueven {n} empleados al nivel correcto')

        print('\n[3] Estado del grafo')
        fila = g.una('PG3-esquema')
        presentes = set((fila or {}).get('etiquetas') or [])
        for etiqueta in ('Termino', 'Funcion_Pertenencia', 'Variable_Linguistica'):
            print(f"  {'OK' if etiqueta in presentes else 'XX'} {etiqueta}")

    print('\n' + '=' * 70)
    if aplicar:
        print('Correcciones aplicadas. Documentalas en el punto 1 del informe.')
        print('Para ver el efecto:  python -m api.main --recalcular pv_001 --simular')
    else:
        print('Nada se modificó. Para corregir:  python -m api.main --depurar --aplicar')


def ver_catalogos():
    """Qué conoce el sistema: es lo único que puede reconocer en un pedido."""
    from submodulos import s1_requisitos
    with Grafo() as g:
        cat, crudo = s1_requisitos.catalogos(g)

        print('SERVICIOS (con sus alias y su zona)')
        for s in sorted(crudo.get('servicios', []), key=lambda x: x['nombre'] or ''):
            alias = ', '.join(s.get('alias') or []) or '—'
            print(f"  {s['nombre']:26} zona: {str(s.get('zona')):18} alias: {alias}")

        print('\nZONAS')
        print('  ' + ', '.join(cat['zonas_lista']))

        print('\nTURNOS')
        for t_ in crudo.get('turnos', []):
            print(f"  {t_['nombre']:10} {t_.get('inicio')} - {t_.get('fin')}")

        print('\nAPTITUDES')
        for a in sorted(crudo.get('aptitudes', []), key=lambda x: x['nombre'] or ''):
            vence = 'vence' if a.get('vence') else 'no vence'
            sin = ', '.join(a.get('sinonimos') or []) or '—'
            print(f"  {a['nombre']:34} {str(a.get('tipo')):14} {vence:9} sinónimos: {sin}")

        print('\nEXPRESIONES DE URGENCIA')
        for e in sorted(crudo.get('expresiones', []), key=lambda x: (x.get('tipo') or '', x.get('valor') or 0)):
            if not e.get('texto'):
                continue
            print(f"  {e['texto']:26} {str(e.get('tipo')):8} {e.get('valor')} {e.get('unidad') or ''}")

        print('\nPUESTOS REGISTRADOS')
        for f in g.leer('S2-Q2b-puestos-registrados'):
            print(f"  {f['puesto']:26} {f['servicio']:22} turno {f['turno']}")


def limpiar_pruebas(confirmado=False):
    """Borra las vacantes creadas por el asistente, para dejar el grafo como el PG2.

    Solo toca nodos con origen = 'PG3'. Los tres puestos del PG2 y sus evaluaciones
    no llevan esa marca y quedan intactos.
    """
    with Grafo() as g:
        filas = g.leer('PG3-datos-de-prueba')
        if not filas:
            print('No hay vacantes de prueba: el grafo está como lo dejó el PG2.')
            return
        print(f'Vacantes creadas por el asistente ({len(filas)}):')
        for f in filas:
            print(f"  {f['puesto']:26} pedido {str(f['pedido']):26} "
                  f"{f['evaluaciones']} evaluaciones, {f['listados']} listado(s)")
        if not confirmado:
            print('\nEsto borra esas vacantes con sus pedidos, evaluaciones, evidencias')
            print('y listados. Los datos del PG2 no se tocan.')
            print('Para hacerlo:  python -m api.main --limpiar --si')
            return
        g.escribir('W-PG3-borrar-pruebas')
        print(f'\nBorradas. Estado del grafo:')
        for f in g.leer('PG3-conteos'):
            print(f"  {f['etiqueta']:32} {f['cantidad']:>6}")


def volcar_esquema():
    """Vuelca el esquema real del grafo. Sirve para alinear el catálogo de
    consultas con lo que el PG2 cargó de verdad."""
    with Grafo() as g:
        print('ETIQUETAS')
        for f in g.leer('PG3-conteos'):
            print(f"  {f['etiqueta']:32} {f['cantidad']:>6} nodos")

        print('\nRELACIONES (origen -> relacion -> destino)')
        for f in g.leer('PG3-relaciones-de'):
            print(f"  {str(f['origen']):28} -{f['relacion']}-> "
                  f"{str(f['destino']):28} {f['cantidad']:>5}")

        print('\nPROPIEDADES POR ETIQUETA')
        for f in g.leer('PG3-conteos'):
            etiqueta = f['etiqueta']
            fila = g.una('PG3-propiedades-de', etiqueta=etiqueta)
            props = sorted((fila or {}).get('propiedades') or [])
            print(f'  {etiqueta}:')
            print('     ' + (', '.join(props) if props else '(sin propiedades)'))


def cargar_script(ruta, continuar=False):
    """Instala un archivo .cypher en la base configurada en el .env."""
    from pathlib import Path
    from core.carga import cargar

    archivo = Path(ruta)
    if not archivo.is_absolute():
        archivo = config.RAIZ / ruta
    if not archivo.exists():
        print(f'No encontré el archivo: {archivo}')
        print('Copiá Grupo_5_PG2_U1_carga.cypher a la carpeta neo4j/ del proyecto.')
        return

    print(f'Base de destino: {config.NEO4J_BASE} en {config.NEO4J_URI}\n')
    try:
        with Grafo() as g:
            previos = {f['etiqueta']: f['cantidad'] for f in g.leer('PG3-conteos')}
            if previos:
                total = sum(previos.values())
                print(f'AVISO: la base ya tiene {total} nodos. El script del PG2 usa MERGE,')
                print('así que volver a correrlo actualiza en lugar de duplicar, pero si')
                print('querés partir de cero, borrá la base antes desde la consola de Aura.\n')
            ok, ejecutadas, errores = cargar(g, archivo, detenerse_en_error=not continuar)
            print()
            for f in g.leer('PG3-conteos'):
                print(f"  {f['etiqueta']:32} {f['cantidad']:>6}")
        if not ok:
            print('\nQuedaron sentencias con error. Para seguir de largo e ir anotando')
            print('todos los fallos en vez de parar en el primero, agregá --continuar')
    except ErrorGrafo as e:
        print(f'No se pudo conectar: {e}')


def exportar_grafo():
    """Ítem i del ZIP: exportación de la base de conocimiento."""
    from core.exportar import exportar
    with Grafo() as g:
        previas = g.leer('PG3-datos-de-prueba')
        if previas:
            print(f'AVISO: hay {len(previas)} vacante(s) de prueba creadas por el asistente '
                  '(origen = PG3). Si querés exportar el grafo limpio, corré antes:')
            print('    python -m api.main --limpiar --si\n')
        r = exportar(g)
    print(f"Exportados {r['nodos']} nodos y {r['relaciones']} relaciones.")
    for etiqueta, n in sorted(r['por_etiqueta'].items()):
        print(f'  {etiqueta:32} {n:>6}')
    print(f"\n  {r['cypher']}\n  {r['json']}")
    print('\nPara reconstruir el grafo en una base vacía:')
    print('    python -m api.main --cargar neo4j/Grupo_5_PG3_export.cypher')


def listar_modelos():
    """Muestra los modelos que habilita la clave configurada."""
    from core.llm import ErrorLLM, _elegir_modelo_gemini, listar_modelos_gemini
    if config.LLM_PROVEEDOR != 'gemini':
        print(f'Este comando es para Gemini. LLM_PROVEEDOR está en "{config.LLM_PROVEEDOR}".')
        print('  groq     -> https://console.groq.com/docs/models')
        print('  deepseek -> https://api-docs.deepseek.com/quick_start/pricing')
        print('  ollama   -> ollama list')
        return
    try:
        modelos = listar_modelos_gemini()
    except ErrorLLM as e:
        print(f'No se pudieron listar los modelos: {e}')
        return
    print(f'Modelos de texto que habilita tu clave ({len(modelos)}):\n')
    for m in sorted(modelos, key=lambda x: x['nombre']):
        print(f"  {m['nombre']:46} {m['descripcion']}")
    print(f"\nElegido automáticamente (LLM_MODELO vacío): {_elegir_modelo_gemini()}")
    print('Para fijar otro, poné su nombre exacto en LLM_MODELO del .env.')
    print('Cuáles son gratis: https://ai.google.dev/gemini-api/docs/pricing')


def main():
    args = sys.argv[1:]
    if '--check' in args:
        check()
        return
    if '--cargar' in args:
        cargar_script(args[args.index('--cargar') + 1],
                      continuar='--continuar' in args)
        return
    if '--depurar' in args:
        depurar(aplicar='--aplicar' in args)
        return
    if '--exportar' in args:
        exportar_grafo()
        return
    if '--catalogos' in args:
        ver_catalogos()
        return
    if '--limpiar' in args:
        limpiar_pruebas(confirmado='--si' in args)
        return
    if '--esquema' in args:
        volcar_esquema()
        return
    if '--conteos' in args:
        with Grafo() as g:
            filas = g.leer('PG3-conteos')
        if not filas:
            print('El grafo está vacío.')
        for f in filas:
            print(f"  {f['etiqueta']:32} {f['cantidad']:>6}")
        return
    if '--modelos' in args:
        listar_modelos()
        return
    if '--recalcular' in args:
        recalcular(args[args.index('--recalcular') + 1], simular='--simular' in args)
        return
    if '--casos' in args:
        from pruebas.casos_e2e import correr
        pausa = 0
        if '--pausa' in args:
            pausa = float(args[args.index('--pausa') + 1])
        ids = [a for a in args[args.index('--casos') + 1:]
               if not a.startswith('--') and a != str(args[args.index('--pausa') + 1] if '--pausa' in args else '')]
        correr(ids, pausa=pausa)
        return
    if '-q' in args:
        r = asistente.responder(args[args.index('-q') + 1])
        print('\n' + '-' * 70)
        print(f"[enrutado a] {r.get('submodulo')}")
        for p in r.get('traza', []):
            if p['etapa'] in ('cypher', 'cypher_escritura'):
                print(f"  {p['etapa']:17} {p['consulta']:28} filas={p['filas']:<3} {p['ms']} ms")
        print('-' * 70)
        print(r.get('respuesta'))
        print('-' * 70)
        return

    if not HAY_FASTAPI:
        print('Para levantar el servidor web faltan dependencias. Instalalas con:\n')
        print('    pip install -r requirements.txt\n')
        print('Asegurate de estar en el entorno virtual del proyecto (el prompt tiene que')
        print('empezar con "(.venv)"). Si no lo creaste todavía:\n')
        print('    python -m venv .venv')
        print('    .venv\\Scripts\\activate          (Windows)')
        print('    pip install -r requirements.txt\n')
        print('Mientras tanto, estos comandos sí funcionan sin FastAPI:')
        print('    python -m api.main --check')
        print('    python -m api.main --modelos')
        print('    python -m api.main -q "tu consulta"')
        sys.exit(1)

    import uvicorn
    from core.llm import modelo_en_uso
    print(f'Asistente en http://localhost:8000   (proveedor LLM: {config.LLM_PROVEEDOR}, '
          f'modelo: {modelo_en_uso()})')
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning')


if __name__ == '__main__':
    try:
        main()
    except ErrorGrafo as e:
        # Sin traceback: el mensaje ya dice qué hacer (p. ej. reanudar Aura).
        print(f'\nXX {e}')
        sys.exit(2)
