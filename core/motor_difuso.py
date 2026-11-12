"""Motor Mamdani del Grupo 5 (PG2): S1 (urgencia del pedido), S2/S3 (afinidad con margen y solape) y S4 (prioridad).
AND = MIN, OR = MAX, NO = 1 - mu, implicacion MIN, agregacion MAX, defuzzificacion por centroide (1001 puntos).
Los parametros son los de los PI3 de cada submodulo; las funciones de S3 v0.2 se conservan para recalcular
casos viejos (las de cercania, experiencia y afinidad global estan reconstruidas desde valores publicados en el PI2 de S3).

PG3: este archivo se trae SIN CAMBIOS desde el PG2. Es la unica fuente de las inferencias difusas
del sistema integrado; ni los submodulos ni el LLM recalculan nada por su cuenta.
Ejecutar `python -m core.motor_difuso` imprime la verificacion contra los valores publicados.
"""
import math
import numpy as np


# ------------------------------------------------------------------ funciones de pertenencia
def g(x, c, s, lado=None):
    """Gaussiana; lado='izq' (hombro izquierdo): 1 si x<=c; lado='der' (hombro derecho): 1 si x>=c."""
    if lado == 'izq' and x <= c:
        return 1.0
    if lado == 'der' and x >= c:
        return 1.0
    return math.exp(-1.0 * (x - c) ** 2 / (2.0 * s ** 2))


def g2(x, c1, s1, c2, s2):
    """Gaussiana de dos lados con meseta entre c1 y c2 (PI3 de S2)."""
    if x < c1:
        return math.exp(-1.0 * (x - c1) ** 2 / (2.0 * s1 ** 2))
    if x > c2:
        return math.exp(-1.0 * (x - c2) ** 2 / (2.0 * s2 ** 2))
    return 1.0


def trap(x, a, b, c, d):
    if x < a or x > d:
        return 0.0
    if b <= x <= c:
        return 1.0
    return (x - a) / (b - a) if x < b else (d - x) / (d - c)


def centroide_conjunto(altura, forma, n=1001):
    """altura: {termino: nivel de recorte}; forma: {termino: funcion(y)}. Devuelve el centroide sobre [0, 1]."""
    ys = np.linspace(0, 1, n)
    mu = np.array([max(min(altura[t], forma[t](y)) for t in altura) for y in ys])
    return float((ys * mu).sum() / mu.sum()) if mu.sum() > 0 else None


# ------------------------------------------------------------------ S1: urgencia del pedido (PI3 de S1)
def s1_plazo(p):
    return {'inmediato': g(p, 12, 22, 'izq'), 'corto': g(p, 62, 20), 'amplio': g(p, 112, 22, 'der')}


def s1_premura(m):
    return {'leve': g(m, 2, 1.3, 'izq'), 'moderada': g(m, 5, 1.3), 'fuerte': g(m, 8, 1.3, 'der')}


S1_SAL = {
    'baja': lambda y: g(y, 0.10, 0.17, 'izq'),
    'media': lambda y: g(y, 0.50, 0.17),
    'alta': lambda y: g(y, 0.90, 0.17, 'der'),
}


def s1_reglas(p=None, m=None):
    P = s1_plazo(p) if p is not None else None
    M = s1_premura(m) if m is not None else None
    if P and M:
        return 'S1-GA', {
            'S1-F01': (P['inmediato'], 'alta'),
            'S1-F02': (min(P['corto'], M['fuerte']), 'alta'),
            'S1-F03': (max(min(P['corto'], M['moderada']), min(P['amplio'], M['fuerte'])), 'media'),
            'S1-F04': (min(max(P['amplio'], P['corto']), M['leve']), 'baja'),
            'S1-F05': (min(P['amplio'], M['moderada']), 'baja'),
        }
    if P:
        return 'S1-GB', {
            'S1-F01': (P['inmediato'], 'alta'),
            'S1-F06': (P['corto'], 'media'),
            'S1-F07': (P['amplio'], 'baja'),
        }
    if M:
        return 'S1-GC', {
            'S1-F08': (M['fuerte'], 'alta'),
            'S1-F09': (M['moderada'], 'media'),
            'S1-F10': (M['leve'], 'baja'),
        }
    return None, {}


def s1_urgencia(p=None, m=None):
    """Devuelve grados por termino, centroide (urgencia_valor) y categoria por grado dominante (empate: mayor urgencia)."""
    grupo, r = s1_reglas(p, m)
    if not r:
        return None
    h = {'baja': 0.0, 'media': 0.0, 'alta': 0.0}
    for w, t in r.values():
        h[t] = max(h[t], w)
    # max() conserva el primero ante empate: alta > media > baja
    cat = max(['alta', 'media', 'baja'], key=lambda t: h[t])
    return {'grupo': grupo, 'grados': h, 'valor': centroide_conjunto(h, S1_SAL), 'categoria': cat, 'reglas': r}


# ------------------------------------------------------------------ S2/S3: afinidad (PI2/PI3 de S3 y PI3 de S2)
SU, SD = 20.38, 1.274


def urgencia(h, ver='0.3'):
    if ver == '0.2':
        return {'alta': trap(h, 0, 0, 24, 48), 'media': trap(h, 24, 60, 60, 96), 'baja': trap(h, 72, 120, 168, 168)}
    return {'alta': g(h, 12, SU, 'izq'), 'media': g(h, 60, SU), 'baja': g(h, 108, SU, 'der')}


def desempeno(d, ver='0.3'):
    if ver == '0.2':
        return {'bajo': trap(d, 1, 1, 4, 6), 'medio': trap(d, 4.5, 6.5, 6.5, 8.5), 'alto': trap(d, 7, 8.5, 10, 10)}
    return {'bajo': g(d, 3.5, SD, 'izq'), 'medio': g(d, 6.5, SD), 'alto': g(d, 9.5, SD, 'der')}


def cercania(m):
    return {'misma_zona': trap(m, 0, 0, 10, 25), 'cercana': trap(m, 15, 35, 35, 55), 'lejana': trap(m, 45, 65, 90, 90)}


def experiencia(m):
    return {'baja': trap(m, 0, 0, 5, 8), 'media': trap(m, 6, 12, 12, 20), 'alta': trap(m, 15, 24, 36, 36)}


def margen(dias):
    return {'critico': g2(dias, 0, 6, 7, 6), 'por_vencer': g(dias, 35, 12), 'holgado': g2(dias, 75, 12, 120, 12)}


def solape(f):
    return {'insuficiente': g2(f, 0, 0.08, 0.3, 0.08), 'parcial': g(f, 0.6, 0.1), 'total': g2(f, 0.85, 0.06, 1.0, 0.06)}


AFIN = {'baja': (0, 0, 0, 0.5), 'media': (0.3, 0.5, 0.5, 0.7), 'alta': (0.5, 1, 1, 1)}


def reglas(u, e, d, z, mg=120, so=1.0):
    M = margen(mg)
    O = solape(so)
    A = max(u['baja'], u['media'])
    B = u['alta']
    return {
        'S3-FA1': (min(A, e['alta'], d['alto']), 'alta'),
        'S3-FA2': (min(A, e['media'], d['alto']), 'media'),
        'S3-FA3': (min(A, e['alta'], d['medio']), 'media'),
        'S3-FA4': (min(A, e['media'], d['medio']), 'media'),
        'S3-FA5': (min(A, e['baja']), 'baja'),
        'S3-FA6': (min(A, d['bajo']), 'baja'),
        'S3-FA7': (min(A, z['lejana']), 'baja'),
        'S3-FB1': (min(B, z['misma_zona'], e['media']), 'alta'),
        'S3-FB2': (min(B, z['misma_zona'], e['alta']), 'alta'),
        'S3-FB3': (min(B, z['cercana'], e['alta']), 'alta'),
        'S3-FB4': (min(B, z['cercana'], e['media']), 'media'),
        'S3-FB5': (min(B, z['misma_zona'], e['baja']), 'media'),
        'S3-FB6': (min(B, z['cercana'], e['baja']), 'baja'),
        'S3-FB7': (min(B, z['lejana']), 'baja'),
        'S3-FB8': (min(B, d['bajo']), 'media'),
        'S2-V1': (max(M['critico'], O['insuficiente']), 'baja'),
        'S2-V2': (min(1 - M['holgado'], 1 - O['total']), 'baja'),
        'S2-V3': (0.2 * max(1 - M['holgado'], 1 - O['total']), 'baja'),
    }


def centroide(r):
    h = {'baja': 0.0, 'media': 0.0, 'alta': 0.0}
    for w, t in r.values():
        h[t] = max(h[t], w)
    ys = np.linspace(0, 1, 1001)
    mu = np.array([max(min(h[t], trap(y, *AFIN[t])) for t in h) for y in ys])
    return float((ys * mu).sum() / mu.sum()), h


def evaluar(ug, e_m, d_p, c_m, mg=120, so=1.0, ver='0.3'):
    """ug: dict de grados de urgencia (S1) o horas (float, solo para recalcular con v0.2/v0.3)."""
    u = urgencia(ug, ver) if not isinstance(ug, dict) else ug
    r = reglas(u, experiencia(e_m), desempeno(d_p, ver), cercania(c_m), mg, so)
    c, h = centroide(r)
    return c, h, r


def intervalo(ug, e_m, d_rng, c_rng, mg_rng=(120, 120), so_rng=(1.0, 1.0), ver='0.3'):
    """Minimo y maximo de afinidad cuando algun dato es un rango (DESCONOCIDO); se barre cada rango."""
    def rng(r, n):
        return np.linspace(r[0], r[1], n) if r[0] != r[1] else [r[0]]

    vals = [
        evaluar(ug, e_m, d, c, mg, so, ver)[0]
        for d in rng(d_rng, 19)
        for c in rng(c_rng, 41)
        for mg in rng(mg_rng, 5)
        for so in rng(so_rng, 21)
    ]
    return min(vals), max(vals)


# ------------------------------------------------------------------ S4: prioridad de recomendacion (PI3 de S4, version S4-FZ-v1)
S4_PARAM = {
    'afinidad': {'baja': (0.00, 0.340, None), 'intermedia': (0.55, 0.127, None), 'alta': (1.00, 0.255, None)},
    'confiabilidad': {'baja': (0.55, 0.127, 'izq'), 'media': (0.80, 0.085, None), 'alta': (1.00, 0.085, None)},
}
S4_SAL = {'Baja_prioridad': (0.15, 0.10), 'Recomendado_con_reservas': (0.50, 0.10), 'Recomendado': (0.85, 0.10)}
S4_FORMA = {k: (lambda y, c=c, s=s: g(y, c, s)) for k, (c, s) in S4_SAL.items()}
DELTA_TRANSICION = 0.20


def s4_grados(var, x):
    return {t: g(x, c, s, l) for t, (c, s, l) in S4_PARAM[var].items()}


def s4_reglas(a, c, adv):
    """a: afinidad central; c: confiabilidad; adv in {'ninguna','con_advertencia','sin_dato'} (antecedente crisp: 0 o 1)."""
    A = s4_grados('afinidad', a)
    C = s4_grados('confiabilidad', c)
    ning, con, sin_ = (1.0 if adv == k else 0.0 for k in ('ninguna', 'con_advertencia', 'sin_dato'))
    return {
        'FZ1': (min(A['alta'], C['alta'], ning), 'Recomendado'),
        'FZ2': (min(A['alta'], max(C['media'], C['baja'])), 'Recomendado_con_reservas'),
        'FZ3': (min(A['alta'], max(con, sin_)), 'Recomendado_con_reservas'),
        'FZ4': (A['intermedia'], 'Recomendado_con_reservas'),
        'FZ5': (min(A['baja'], max(C['alta'], C['media'])), 'Baja_prioridad'),
        'FZ6': (min(A['baja'], C['baja']), 'Recomendado_con_reservas'),
    }


def s4_prioridad(a, c, adv):
    r = s4_reglas(a, c, adv)
    h = {t: 0.0 for t in S4_SAL}
    for w, t in r.values():
        h[t] = max(h[t], w)
    return centroide_conjunto(h, S4_FORMA), r


def calibrar_cortes():
    """Cortes de la regla FZ-C: prioridad con dato preciso y sin advertencias en afinidad 0,40 y 0,70."""
    return s4_prioridad(0.40, 1.0, 'ninguna')[0], s4_prioridad(0.70, 1.0, 'ninguna')[0]


# valores publicados en el PI3 de S4 (c.5); calibrar_cortes() los recalcula
CORTE_RESERVAS, CORTE_RECOMENDADO = 0.367, 0.610


def s4_categoria(prioridad):
    if prioridad >= CORTE_RECOMENDADO:
        return 'Recomendado'
    if prioridad >= CORTE_RESERVAS:
        return 'Recomendado_con_reservas'
    return 'Baja_prioridad'


def s4_clasificar(amin, amax, adv):
    a = (amin + amax) / 2.0
    c = 1.0 - (amax - amin)
    pr, r = s4_prioridad(a, c, adv)
    cat = s4_categoria(pr)
    A = sorted(s4_grados('afinidad', a).values(), reverse=True)
    trans = (A[0] - A[1]) < DELTA_TRANSICION
    cand = {k: w for k, (w, t) in r.items() if t == cat} or {k: w for k, (w, t) in r.items()}
    dom = max(cand, key=cand.get)
    return {'a': a, 'c': c, 'prioridad': pr, 'categoria': cat, 'transicion': trans, 'dominante': dom, 'reglas': r}


# ------------------------------------------------------------------ verificacion contra los valores publicados
if __name__ == '__main__':
    ok = True

    def chk(nombre, obtenido, publicado, tol):
        global ok
        bien = abs(obtenido - publicado) <= tol
        ok &= bien
        print(f"  {'OK ' if bien else 'XX '}{nombre}: obtenido {obtenido:.3f} | publicado {publicado}")

    print('S1 - PI3 de S1, tabla 10 (grados baja/media/alta y centroide)')
    for nm, (p, m, gr, cv, cat) in {
        'E1': (24, None, (0, 0.16, 0.86), 0.723, 'alta'),
        'E2': (None, 9, (0, 0.01, 1.0), 0.818, 'alta'),
        'E3': (120, 8, (0.07, 1.0, 0.01), 0.496, 'media'),
        'E4': (144, 1, (1.0, 0, 0), 0.176, 'baja'),
        'E5': (84, None, (0.44, 0.55, 0), 0.418, 'media'),
        'E6': (48, 5, (0.07, 0.78, 0.26), 0.532, 'media'),
        'E7': (8, 1, (0.03, 0.01, 1.0), 0.804, 'alta'),
    }.items():
        s = s1_urgencia(p, m)
        chk(f'{nm} centroide', s['valor'], cv, 0.0015)
        chk(f'{nm} grados',
            abs(s['grados']['baja'] - gr[0]) + abs(s['grados']['media'] - gr[1]) + abs(s['grados']['alta'] - gr[2]),
            0, 0.02)
        ok &= (s['categoria'] == cat)

    print('S3 - PI3 de S3, tabla 12 (E1 / E2 con urgencia en horas): v0.2 y v0.3')
    pub = {('0.2', 20): (0.50, 0.67), ('0.2', 36): (0.50, 0.54), ('0.2', 120): (0.50, 0.18),
           ('0.3', 20): (0.495, 0.61), ('0.3', 36): (0.495, 0.50), ('0.3', 120): (0.495, 0.26)}
    for (ver, h), (p1, p2) in pub.items():
        chk(f'v{ver} {h} h E1', evaluar(h, 9, 7.5, 30, ver=ver)[0], p1, 0.006)
        chk(f'v{ver} {h} h E2', evaluar(h, 20, 4.5, 10, ver=ver)[0], p2, 0.006)

    print('S2 - grupo V: sin debilidad no cambia la afinidad')
    U1 = {'baja': 0.0, 'media': 0.16, 'alta': 0.86}
    chk('E1 con y sin V', evaluar(U1, 9, 7.5, 30, 120, 1.0)[0], evaluar(U1, 9, 7.5, 30)[0], 1e-9)

    print('S4 - PI3 de S4, tabla d.3 (prioridad)')
    for nm, (amin, amax, adv, pub_p, cat) in {
        'Emp_101': (0.78, 0.78, 'ninguna', 0.700, 'Recomendado'),
        'Emp_102': (0.74, 0.74, 'con_advertencia', 0.461, 'Recomendado_con_reservas'),
        'Emp_203': (0.58, 0.58, 'ninguna', 0.507, 'Recomendado_con_reservas'),
        'Emp_207': (0.33, 0.33, 'ninguna', 0.293, 'Baja_prioridad'),
        'Emp_301': (0.69, 0.69, 'ninguna', 0.600, 'Recomendado_con_reservas'),
        'Emp_302': (0.71, 0.71, 'ninguna', 0.620, 'Recomendado'),
        'Emp_303': (0.90, 0.90, 'ninguna', 0.782, 'Recomendado'),
        'Emp_304': (0.62, 0.86, 'ninguna', 0.468, 'Recomendado_con_reservas'),
        'Emp_305': (0.10, 0.60, 'ninguna', 0.499, 'Recomendado_con_reservas'),
        'Emp_306': (0.85, 0.85, 'sin_dato', 0.485, 'Recomendado_con_reservas'),
    }.items():
        s = s4_clasificar(amin, amax, adv)
        chk(f'{nm} prioridad', s['prioridad'], pub_p, 0.0015)
        ok &= (s['categoria'] == cat)
    cr, cc = calibrar_cortes()
    chk('corte reservas', cr, 0.367, 0.0015)
    chk('corte recomendado', cc, 0.610, 0.0015)
    print('TODO COINCIDE CON LO PUBLICADO' if ok else 'HAY DIFERENCIAS')
