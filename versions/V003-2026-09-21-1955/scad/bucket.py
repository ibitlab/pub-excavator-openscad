#!/usr/bin/env python3
"""
bucket.py — ківш міні-екскаватора: профіль, місткість, маса, робочі кути, 2D-перевірка зіткнень на всьому ході
циліндра ковша, міцність вух і пальців. Python-двійник блоку «Ківш» у scad/excavator_boom.scad.

Система ковша: початок — вісь E (рукоять–ківш), x̂ — до вістря зуба, ŷ — зовнішній бік (де вушко тяги Q).
Кут ковша omega: 0 = вісь ковша продовжує рукоять, + = підкручування (закривання).

Запуск (потрібен shapely → через venv):  tools/.venv/bin/python tools/bucket.py [--png файл.png] [--set ключ=знач ...]
"""
import math, sys, argparse
import kinematics as K
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely import affinity

# ----------------------------------------------------------------------------
# Параметри ковша (ті самі назви, що й у SCAD). Лінійні — мм, кути — градуси.
# ----------------------------------------------------------------------------
BUCKET = dict(
    width=300,          # зовнішня ширина (по боковинах)
    side_t=6,           # боковини
    shell_t=5,          # обичайка (дно–спинка–верх однією смугою)
    top_t=8,            # накладка під вуха на верхній полиці
    top_x=76,           # відстань від осі E до зовнішньої поверхні накладки (висота вух)
    lip_y=16,           # передня кромка верху (губа) по ŷ
    top_len=170,        # довжина прямої верхньої полиці
    back_r=60,          # радіус переходу верх → спинка (зовнішній)
    back_turn=45,       # кут цього переходу
    heel_r=120,         # радіус п'яти (спинка → дно), зовнішній
    floor_angle=50,     # кут між лінією «зуб → E» і дном
    edge_w=100,         # ніж: ширина смуги
    edge_t=12,          # ніж: товщина
    tooth_out=70,       # виліт зуба за ніж
    tooth_len=160,      # повна довжина зуба
    tooth_w=40,         # ширина зуба
    tooth_n=3,
    ear_t=12,           # вуха
    ear_r_E=40,         # радіус вуха довкола E
    ear_r_Q=35,         # радіус вуха довкола Q
    boss_E_od=60,       # зовнішня бобишка вуха на осі E (довжина boss_E_len)
    boss_E_len=10,
    lip_rib=(40, 8),    # ребро губи: смуга на ребро під передньою кромкою верху
    wear_n=2,           # смуги зносу на п'яті
    wear=(40, 6),
)
# Рукоять біля осі E (з SCAD): виступ труби за E, фаска кутів торця, пів висоти труби, пакет рукояті
STICK = dict(tip_ext=50, tip_chamfer=25, h2=50, pack_w=80, tip_plate_back=152 + 120, r_tip_R=34.5, r_bush_R=22.5,
             rocker_r_R=37, rocker_r_J=32.5, link_r=32.5, j_boss_r=20.5, eye_r=26.5, rod_r=12.5, body_r=30, plate_boss=10)
RHO = 7.85e-6  # кг/мм³

def rot(p, a):
    return K.rot(p, a)

# ----------------------------------------------------------------------------
# Профіль (зовнішня поверхня обичайки): верх → дуга → спинка → дуга п'яти → дно → ніж
# ----------------------------------------------------------------------------
def _arc(P, heading, r, turn, n=24):
    """Дуга за годинниковою стрілкою: з точки P, напрямок heading (°), радіус r, кут turn. → (точки, новий напрямок)."""
    nr = lambda h: (math.sin(math.radians(h)), -math.cos(math.radians(h)))     # права нормаль
    C = (P[0] + r * nr(heading)[0], P[1] + r * nr(heading)[1])
    pts = []
    for i in range(1, n + 1):
        h = heading - turn * i / n
        pts.append((C[0] - r * nr(h)[0], C[1] - r * nr(h)[1]))
    return pts, heading - turn

def profile(b, g):
    """Повертає dict з ключовими точками та ламаними зовнішньої/внутрішньої поверхні."""
    phi = b['floor_angle']; T = (g['tip'], 0.0)
    hd = (math.cos(math.radians(-phi)), math.sin(math.radians(-phi)))           # напрямок дна (до зуба)
    n_out = (-hd[1], hd[0])                                                      # зовнішня нормаль дна
    T_under = (T[0] + b['edge_t'] / 2 * n_out[0], T[1] + b['edge_t'] / 2 * n_out[1])   # низ дна: вістря — у серединній площині ножа
    x_sh = b['top_x'] + b['top_t']                                               # зовнішня поверхня обичайки на верхній полиці
    S0 = (x_sh, b['lip_y']); S1 = (x_sh, b['lip_y'] + b['top_len'])
    a1, h1 = _arc(S1, 90.0, b['back_r'], b['back_turn'])
    turn2 = 90.0 + phi - b['back_turn']
    d_b = (math.cos(math.radians(h1)), math.sin(math.radians(h1)))
    a2_0, _ = _arc(a1[-1], h1, b['heel_r'], turn2)
    # довжина спинки: кінець дуги п'яти має лягти на лінію низу дна
    num = (a2_0[-1][0] - T_under[0]) * n_out[0] + (a2_0[-1][1] - T_under[1]) * n_out[1]
    den = d_b[0] * n_out[0] + d_b[1] * n_out[1]
    Lb = -num / den
    if Lb < 0: raise ValueError(f'спинка від’ємної довжини ({Lb:.0f}) — зменште радіуси або top_len')
    Pb = (a1[-1][0] + Lb * d_b[0], a1[-1][1] + Lb * d_b[1])
    a2, _ = _arc(Pb, h1, b['heel_r'], turn2)
    edge_front = (T_under[0] - b['tooth_out'] * hd[0], T_under[1] - b['tooth_out'] * hd[1])
    edge_back = (edge_front[0] - b['edge_w'] * hd[0], edge_front[1] - b['edge_w'] * hd[1])
    floor_len = (edge_back[0] - a2[-1][0]) * hd[0] + (edge_back[1] - a2[-1][1]) * hd[1]
    if floor_len < 0: raise ValueError('ніж заходить на дугу п’яти — зменште heel_r або edge_w')
    outer = [S0, S1] + a1 + [Pb] + a2 + [edge_back]
    path = LineString(outer)
    shell = path.buffer(-b['shell_t'], single_sided=True, cap_style='flat', join_style='mitre')   # всередину (праворуч від ходу)
    inner = list(LineString(outer).parallel_offset(b['shell_t'], 'right', join_style=2).coords)
    if Point(inner[0]).distance(Point(S0)) > Point(inner[-1]).distance(Point(S0)): inner = inner[::-1]
    n_in = (-n_out[0], -n_out[1])
    bev = 1.5 * b['edge_t']                                                      # фаска ножа зверху
    blade_top_front = (edge_front[0] - bev * hd[0] + b['edge_t'] * n_in[0], edge_front[1] - bev * hd[1] + b['edge_t'] * n_in[1])
    blade = Polygon([edge_back, edge_front, blade_top_front,
                     (edge_back[0] + b['edge_t'] * n_in[0], edge_back[1] + b['edge_t'] * n_in[1])])
    doubler = Polygon([(b['top_x'], b['lip_y']), (x_sh, b['lip_y']), (x_sh, b['lip_y'] + b['top_len']), (b['top_x'], b['lip_y'] + b['top_len'])])
    rib = Polygon([(x_sh + b['shell_t'], b['lip_y']), (x_sh + b['shell_t'] + b['lip_rib'][0], b['lip_y']),
                   (x_sh + b['shell_t'] + b['lip_rib'][0], b['lip_y'] + b['lip_rib'][1]), (x_sh + b['shell_t'], b['lip_y'] + b['lip_rib'][1])])
    # боковина: зовнішній контур обичайки + ніж, замкнений лінією «губа → передня кромка ножа»
    side = Polygon(outer + [edge_front, blade_top_front, S0])
    # смуга заповнення «врівень»: внутрішня поверхня + лінія від внутрішньої кромки губи до верху ножа
    lip_in = (x_sh + b['shell_t'], b['lip_y'])
    struck = Polygon(inner + [(edge_back[0] + b['edge_t'] * n_in[0], edge_back[1] + b['edge_t'] * n_in[1]), blade_top_front, lip_in])
    if not struck.is_valid: struck = struck.buffer(0)
    dev_len = b['top_len'] + math.radians(b['back_turn']) * (b['back_r'] - b['shell_t'] / 2) + Lb \
        + math.radians(turn2) * (b['heel_r'] - b['shell_t'] / 2) + floor_len
    tooth = Polygon([T, (T[0] - b['tooth_len'] * hd[0] + 18 * n_in[0], T[1] - b['tooth_len'] * hd[1] + 18 * n_in[1]),
                     (T[0] - b['tooth_len'] * hd[0] - 18 * n_in[0], T[1] - b['tooth_len'] * hd[1] - 18 * n_in[1])])
    return dict(outer=outer, inner=inner, shell=shell, blade=blade, doubler=doubler, rib=rib, side=side, struck=struck, tooth=tooth,
                Lb=Lb, floor_len=floor_len, turn2=turn2, dev_len=dev_len, S0=S0, S1=S1, Pb=Pb, heel_end=a2[-1], edge_back=edge_back,
                edge_front=edge_front, T=T, hd=hd, n_out=n_out, open_len=math.dist(lip_in, blade_top_front))

def ear_polygon(b, g):
    Q = (g['qx'], g['qy'])
    base0 = (b['top_x'], b['lip_y'] + 4); base1 = (b['top_x'], min(b['lip_y'] + b['top_len'] - 4, Q[1] + 75))
    parts = [Point(0, 0).buffer(b['ear_r_E'], 48), Point(Q).buffer(b['ear_r_Q'], 48), LineString([base0, base1]).buffer(0.5)]
    return unary_union(parts).convex_hull.difference(Polygon([(b['top_x'], -500), (900, -500), (900, 900), (b['top_x'], 900)]))

# ----------------------------------------------------------------------------
# Рухомі деталі рукояті в системі ковша при куті omega
# ----------------------------------------------------------------------------
def stick_side(g, om):
    """Деталі в системі ковша: пакет рукояті, коромисло, тяга, вузол J (бобишки/вушко/шток)."""
    s = STICK
    bp = K.boom_points(g, 0.0); sp = K.stick_points(g, bp, 120.0)
    fw = K.bucket_points_fwd(g, sp, om)
    if fw is None: return None
    E, us, top = sp['E'], sp['us'], sp['top']
    def to_stick(P): return ((P[0] - E[0]) * us[0] + (P[1] - E[1]) * us[1], (P[0] - E[0]) * top[0] + (P[1] - E[1]) * top[1])
    def to_b(p): return rot(p, om)
    R = to_stick(sp['R']); J = to_stick(fw['J']); H = to_stick(sp['H']); Q = to_stick(fw['Q'])
    e, c, h2 = s['tip_ext'], s['tip_chamfer'], s['h2']
    tube = Polygon([(-700, -h2), (e - c, -h2), (e, -h2 + c), (e, h2 - c), (e - c, h2), (-700, h2)])
    tipR = unary_union([Polygon([(-s['tip_plate_back'], -h2), (e - c, -h2), (e, -h2 + c), (e, h2 - c), (e - c, h2), (-s['tip_plate_back'], h2)]),
                        Point(R).buffer(s['r_tip_R'], 32)]).convex_hull
    pack = unary_union([tube, tipR])
    rocker = unary_union([Point(R).buffer(s['rocker_r_R'], 32), Point(J).buffer(s['rocker_r_J'], 32)]).convex_hull
    link = unary_union([Point(J).buffer(s['link_r'], 32), Point(Q).buffer(s['link_r'], 32)]).convex_hull
    uHJ = K.unit(K.sub(J, H)); Lc = K.dist(J, H)
    rod = LineString([K.add(H, K.mul(uHJ, 420)), J]).buffer(s['rod_r'])
    body = LineString([H, K.add(H, K.mul(uHJ, min(Lc - 60, 450)))]).buffer(s['body_r'])
    jnode = unary_union([Point(J).buffer(s['eye_r'], 32), rod, body])
    f = lambda geom: affinity.rotate(geom, om, origin=(0, 0))
    return dict(pack=f(pack), rocker=f(rocker), link=f(link), jnode=f(jnode), Lc=Lc, J=to_b(J), R=to_b(R), Q=to_b(Q))

def collisions(b, g, om_min, om_max, step=1.0, over=0.0):
    """Мінімальні зазори (мм, від’ємний = перетин на таку глибину приблизно) для пар деталей на всьому ході."""
    pr = profile(b, g); Q = (g['qx'], g['qy'])
    cross = unary_union([pr['shell'], pr['doubler'], pr['rib'], pr['blade']])         # на всю ширину ковша
    spacer = Point(Q).buffer(STICK['r_bush_R'], 32)                                   # розпірна втулка Q між вухами (|y| < 41)
    ear = ear_polygon(b, g)
    bossE = Point(0, 0).buffer(b['boss_E_od'] / 2, 32)
    pairs = {'верх/обичайка ↔ рукоять': ('cross', 'pack'), 'верх/обичайка ↔ коромисло': ('cross', 'rocker'),
             'верх/обичайка ↔ тяга': ('cross', 'link'), 'верх/обичайка ↔ циліндр ковша': ('cross', 'jnode'),
             'втулка Q ↔ рукоять': ('spacer', 'pack'), 'втулка Q ↔ циліндр ковша': ('spacer', 'jnode'),
             'вуха ↔ коромисло': ('ear', 'rocker'), 'бобишка E ↔ тяга': ('bossE', 'link')}
    mine = dict(cross=cross, spacer=spacer, ear=ear, bossE=bossE)
    res = {k: (1e9, None) for k in pairs}
    om = om_min - over
    while om <= om_max + over + 1e-9:
        ss = stick_side(g, om)
        if ss is not None:
            for k, (a, c) in pairs.items():
                A, C = mine[a], ss[c]
                d = A.distance(C)
                if d == 0: d = -math.sqrt(A.intersection(C).area)
                if d < res[k][0]: res[k] = (d, om)
        om += step
    return res

def capacity(b, g):
    pr = profile(b, g)
    w_in = b['width'] - 2 * b['side_t']
    A = pr['struck'].area
    struck = A * w_in / 1e6                                   # л
    L = pr['open_len']; W = w_in
    heap = (W * W * L / 4 - W ** 3 / 12) / 1e6 if L >= W else (L * L * W / 4 - L ** 3 / 12) / 1e6   # насип 1:1 (ISO 7451)
    return dict(area=A, w_in=w_in, struck=struck, heaped=struck + heap, open_len=L)

def masses(b, g):
    pr = profile(b, g); w_in = b['width'] - 2 * b['side_t']
    ear = ear_polygon(b, g)
    m = {
        'боковини 2 шт': 2 * pr['side'].area * b['side_t'] * RHO,
        'обичайка': pr['dev_len'] * w_in * b['shell_t'] * RHO,
        'ніж': b['edge_w'] * b['edge_t'] * b['width'] * RHO,
        'зуби': b['tooth_n'] * 0.5 * b['tooth_len'] * 36 * b['tooth_w'] * RHO,
        'накладка під вуха': b['top_len'] * b['width'] * b['top_t'] * RHO,
        'ребро губи': b['lip_rib'][0] * b['lip_rib'][1] * w_in * RHO,
        'вуха 2 шт': 2 * ear.area * b['ear_t'] * RHO,
        'бобишки, втулка Q': (2 * math.pi / 4 * (b['boss_E_od'] ** 2 - 30 ** 2) * b['boss_E_len'] + math.pi / 4 * (45 ** 2 - 25 ** 2) * 82) * RHO,
        'смуги зносу': b['wear_n'] * b['wear'][0] * b['wear'][1] * (math.radians(pr['turn2']) * b['heel_r'] + 80) * RHO,
    }
    return m

# ----------------------------------------------------------------------------
# Міцність: вуха, пальці E і Q, шов вух, ніж, бокове навантаження
# ----------------------------------------------------------------------------
F_SIDE = 3.0     # кН — бокова сила на зубі (поворот колони з ковшем у ґрунті); уточнити на етапі поворотного механізму

def strength_report(b, g, out=sys.stdout):
    import strength as S
    p = lambda *a: print(*a, file=out)
    fy = S.MAT[S.PLATE_MAT]['fy']; fy_pin = S.MAT[S.PIN_MAT]['fy']
    rows = []
    for label, pm, k, sf in (('160 бар × 1.25 (робота)', K.P_NOM, S.DYN, S.SF_NOM), ('250 бар (замкнений циліндр)', S.P_LOCK, 1.0, S.SF_LOCK)):
        res = S.run_cases(g, pm)
        FE = max(K.norm(r['sol']['bucket']['E']) for r in res) * k
        FQ = max(K.norm(r['sol']['bucket']['Q']) for r in res) * k
        # шов вух: зовнішня сила на зубі, перенесена в центр шва (система ковша)
        Mw = 0.0; Ft = 0.0
        cw = (b['top_x'], b['lip_y'] + 4 + (min(b['lip_y'] + b['top_len'] - 4, g['qy'] + 75) - b['lip_y'] - 4) / 2)
        for r in res:
            sp = r['sol']['sp']; ax = sp['a_s'] - r['om']
            Fb = K.rot(r['sol']['bucket']['T'], -ax)                        # сила на зубі в системі ковша
            Mw = max(Mw, abs(K.cross(K.sub((g['tip'], 0.0), cw), Fb)) * k); Ft = max(Ft, K.norm(Fb) * k)
        rows.append((label, sf, FE, FQ, Ft, Mw))
    p("## Міцність ковша")
    p(f"Матеріал вух, накладки, боковин, обичайки — {S.PLATE_MAT} (fy = {fy} МПа); пальці — {S.PIN_MAT}. Сили — з tools/strength.py (ті самі розрахункові випадки).")
    p()
    p("| Випадок | F на осі E, кН | F у тязі (вісь Q), кН | F на зубі, кН | M на шві вух, кН·м |"); p("|---|---|---|---|---|")
    for label, sf, FE, FQ, Ft, Mw in rows: p(f"| {label} | {FE:.1f} | {FQ:.1f} | {Ft:.1f} | {Mw / 1000:.2f} |")
    p()
    dE, dQ, t = 30.0, 25.0, b['ear_t']
    base = min(b['lip_y'] + b['top_len'] - 4, g['qy'] + 75) - b['lip_y'] - 4
    p("| Перевірка | 160 бар × 1.25: σ/τ, МПа → запас (потрібно ≥ 1.5) | 250 бар: σ/τ, МПа → запас (потрібно ≥ 1.0) |"); p("|---|---|---|")
    def line(name, fn, lim):
        cells = []
        for label, sf, FE, FQ, Ft, Mw in rows:
            v = fn(FE * 1000, FQ * 1000, Ft * 1000, Mw * 1000); cells.append(f"{v:.0f} → {lim / v:.2f}{'' if lim / v >= sf else ' ⚠'}")
        p(f"| {name} | {cells[0]} | {cells[1]} |")
    line(f"Вухо, вісь Q Ø25: зминання отвору (t = {t}, допустиме 1.5·fy)", lambda FE, FQ, Ft, Mw: FQ / 2 / (dQ * t), 1.5 * fy)
    line(f"Вухо, вісь Q: виривання перемички (R{b['ear_r_Q']}, зріз по двох площинах, 0.58·fy)", lambda FE, FQ, Ft, Mw: FQ / 2 / (2 * (b['ear_r_Q'] - dQ / 2) * t), 0.58 * fy)
    line(f"Вухо, вісь E Ø30: зминання (вухо {t} + бобишка {b['boss_E_len']})", lambda FE, FQ, Ft, Mw: FE / 2 / (dE * (t + b['boss_E_len'])), 1.5 * fy)
    line(f"Вухо, вісь E: виривання перемички (R{b['ear_r_E']})", lambda FE, FQ, Ft, Mw: FE / 2 / (2 * (b['ear_r_E'] - dE / 2) * t), 0.58 * fy)
    a_w = 0.7 * 6; Lw = base; Aw = 4 * a_w * Lw; Ww = 4 * a_w * Lw ** 2 / 6
    line(f"Шов вух до накладки: 2 вуха × 2 боки × {Lw:.0f} мм, катет 6 (τ допустиме 150·1.5 = 225 при 250 бар)",
         lambda FE, FQ, Ft, Mw: math.hypot(Mw / Ww, Ft / Aw), 225.0)
    line("Палець Q Ø25: згин між тягою (10) і вухом (12), зазор 1 мм", lambda FE, FQ, Ft, Mw: (FQ / 2 * (5 + 1 + t / 2)) / (math.pi * dQ ** 3 / 32), fy_pin)
    line("Палець Q Ø25: зріз (одна площина на бік)", lambda FE, FQ, Ft, Mw: FQ / 2 / (math.pi * dQ ** 2 / 4), 0.58 * fy_pin)
    line("Палець E Ø30: згин (бобишка рукояті 80 між вухами, зазор 1 мм)", lambda FE, FQ, Ft, Mw: FE * (80 + 4 + 2 * t) / 8 / (math.pi * dE ** 3 / 32), fy_pin)
    line(f"Ніж {b['edge_w']}×{b['edge_t']}: згин у своїй площині від сили на середньому зубі (балка між боковинами; для Ст3 — fy)",
         lambda FE, FQ, Ft, Mw: Ft * (b['width'] - 2 * b['side_t']) / 4 / (b['edge_t'] * b['edge_w'] ** 2 / 6), fy)
    p()
    Ms = F_SIDE * 1000 * (g['tip'] - b['top_x']); Fpp = Ms / (g['stick_pack'] + 2 + t) if 'stick_pack' in g else Ms / (82 + t)
    s_pp = Fpp / (base * t); s_b = (F_SIDE * 1000 / 2 * b['top_x']) / (base * t ** 2 / 6)
    p(f"Бокова сила {F_SIDE:.0f} кН на зубі (припущення до етапу поворотного механізму): пара сил у вухах ±{Fpp / 1000:.1f} кН → {s_pp:.0f} МПа у перерізі вуха; "
      f"згин вуха з площини {s_b:.0f} МПа — несуттєво. Розпірна втулка Q, приварена до обох вух, робить пару вух жорсткою рамою.")
    p()
    p("Товщини без розрахунку (за практикою ковшів 300 мм для машин 1–1.5 т): боковини 6 мм, обичайка 5 мм, накладка 8 мм. "
      "Сталь Ст3 тут працює за міцністю, але стирається: ніж і зуби — лише зносостійкі; на п'яту — смуги зносу, які міняються.")

# ----------------------------------------------------------------------------
def om_range(g):
    res, a, c, ok = K.bucket_range(g, n=61)
    oms = []; prev = None
    for _, s in res:
        if s is None: continue
        o = s['omega']
        if prev is not None:
            while o - prev > 180: o -= 360
            while o - prev < -180: o += 360
        prev = o; oms.append(o)
    if oms and oms[0] > 100: oms = [o - 360 for o in oms]
    return oms[0], oms[-1], ok, res

def report(b, g, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    pr = profile(b, g); cap = capacity(b, g); m = masses(b, g)
    om0, om1, ok, res = om_range(g)
    Q = (g['qx'], g['qy'])
    p(f"# Ківш {b['width']} мм: профіль, місткість, робочі кути, зазори")
    p()
    p("## Профіль (система ковша: E = 0, x̂ → вістря зуба, ŷ → зовнішній бік)")
    p(f"- радіус копання E → вістря зуба: **{g['tip']} мм**; вушко тяги Q = ({g['qx']}, {g['qy']}), |EQ| = {math.hypot(*Q):.0f} мм")
    p(f"- верх: накладка {b['top_t']} мм на відстані {b['top_x']} мм від осі E, губа на ŷ = {b['lip_y']}, пряма полиця {b['top_len']} мм")
    p(f"- перехід у спинку R{b['back_r']} на {b['back_turn']}°, спинка {pr['Lb']:.0f} мм, п'ята R{b['heel_r']} на {pr['turn2']:.0f}°, дно {pr['floor_len']:.0f} мм + ніж {b['edge_w']}×{b['edge_t']}")
    p(f"- кут дна до лінії «зуб → E»: {b['floor_angle']}° (задній кут різання відносно дотичної до траєкторії зуба: {90 - b['floor_angle']}°)")
    rmax = max(math.hypot(*q) for q in pr['outer'])
    p(f"- найвіддаленіша від E точка обичайки: {rmax:.0f} мм (< {g['tip']} → п'ята не треться об вибій, запас {g['tip'] - rmax:.0f} мм)")
    p(f"- розгортка обичайки: **{pr['dev_len']:.0f} × {cap['w_in']} мм**, t = {b['shell_t']}")
    p()
    p("## Місткість")
    p(f"- площа профілю (по внутрішній поверхні): {cap['area'] / 100:.0f} см², внутрішня ширина {cap['w_in']} мм, отвір {cap['open_len']:.0f} мм")
    p(f"- **врівень: {cap['struck']:.1f} л; з «шапкою» 1:1 (ISO 7451): {cap['heaped']:.1f} л**")
    p(f"- вантаж: ≈{cap['heaped'] * 1.8:.0f} кг мокрої глини (1.8 т/м³)")
    p()
    p("## Маса")
    p("| Деталь | кг |"); p("|---|---|")
    for k, v in m.items(): p(f"| {k} | {v:.1f} |")
    p(f"| **Разом** | **{sum(m.values()):.1f}** |")
    p()
    p(f"## Робочі кути (хід циліндра {K.CYL['bucket']['closed']}…{K.CYL['bucket']['open']} → omega ∈ [{om0:.1f}°, {om1:.1f}°], діапазон {om1 - om0:.0f}°)")
    p("Отвір ковша дивиться у бік −ŷ. Ківш тримає ґрунт, коли площина отвору горизонтальна або нахилена назад;")
    p("висипає, коли дно нахилене вниз крутіше за ≈45° (липка глина — 55–60°).")
    p("| напрямок рукояті (від горизонту вниз) | нахил отвору при повному підкручуванні (+ = назад, тримає) | кут дна вниз при повному розкритті |")
    p("|---|---|---|")
    for sd in (90, 60, 45, 30):
        # напрямок осі ковша у світі = −sd − omega; отвір горизонтальний, коли вісь дивиться на 180° (до машини)
        tilt_back = (-sd - om1) - (-180.0)          # <0 → нахил назад
        floor_dump = -(-sd - om0 - b['floor_angle'])
        p(f"| {sd}° | {-tilt_back:+.0f}° | {floor_dump:.0f}° |")
    p()
    p("## Зазори рухомих пар на всьому ході (вид збоку, з урахуванням шарів по ширині)")
    col = collisions(b, g, om0, om1)
    p("| Пара | мін. зазор, мм | при omega |"); p("|---|---|---|")
    bad = 0
    for k, (d, o) in col.items():
        flag = '' if d >= 5 else (' ⚠ малий' if d >= 0 else ' ✗ ЗІТКНЕННЯ')
        bad += d < 0
        p(f"| {k} | {d:.0f}{flag} | {o:.0f}° |")
    col2 = collisions(b, g, om0, om1, over=4.0)
    worst = min(col2.values(), key=lambda t: t[0])
    p()
    p(f"Запас на неточність довжини циліндра: при виході за межі ходу на ±4° найменший зазор {worst[0]:.0f} мм (omega = {worst[1]:.0f}°).")
    return bad

def plot(b, g, fn):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pr = profile(b, g); om0, om1, ok, _ = om_range(g)
    ear = ear_polygon(b, g)
    oms = [om0, om0 + (om1 - om0) / 3, om0 + 2 * (om1 - om0) / 3, om1]
    fig, axs = plt.subplots(1, 4, figsize=(22, 7))
    for ax, om in zip(axs, oms):
        ss = stick_side(g, om)
        def draw(geom, **kw):
            for gg in (geom.geoms if hasattr(geom, 'geoms') else [geom]):
                x, y = gg.exterior.xy; ax.fill(x, y, **kw)
        draw(pr['side'], fc='#e8e2b0', ec='#8a8440', alpha=0.6)
        for k in ('shell', 'doubler', 'rib', 'blade', 'tooth'): draw(pr[k], fc='#7a7430', ec='k', lw=0.4)
        draw(ear, fc='#c9a227', ec='k', alpha=0.7, lw=0.5)
        draw(ss['pack'], fc='#d98c2b', ec='k', alpha=0.55, lw=0.5)
        draw(ss['rocker'], fc='#5b8a72', ec='k', alpha=0.6, lw=0.5)
        draw(ss['link'], fc='#5b6f9a', ec='k', alpha=0.6, lw=0.5)
        draw(ss['jnode'], fc='#3b4f8a', ec='k', alpha=0.5, lw=0.5)
        ax.plot(*zip((0, 0), (g['qx'], g['qy'])), 'k.', ms=6)
        ax.set_aspect('equal'); ax.set_title(f'omega = {om:.0f}°, L цил. = {ss["Lc"]:.0f}'); ax.grid(alpha=0.3)
        ax.set_xlim(-520, 560); ax.set_ylim(-420, 560)
    fig.tight_layout(); fig.savefig(fn, dpi=70)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--png'); ap.add_argument('--set', nargs='*', default=[])
    a = ap.parse_args()
    b = dict(BUCKET); g = dict(K.GEOM)
    for kv in a.set:
        k, v = kv.split('='); tgt = b if k in b else g
        tgt[k] = float(v) if '.' in v else int(v)
    bad = report(b, g)
    print(); strength_report(b, g)
    if a.png: plot(b, g, a.png)
    sys.exit(1 if bad else 0)
