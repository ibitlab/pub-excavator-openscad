#!/usr/bin/env python3
"""
kinematics.py — планарна кінематика робочого обладнання міні-екскаватора
(стріла + рукоять + важільна система ковша) і підбір положень кріплень циліндрів.

Система координат (вид збоку): X — вперед (до ковша), Y — вгору.
Вісь повороту стріли A = (0, 0). Довжини у мм, кути у градусах.

Кути (первинні параметри моделі):
  theta_b  — кут хорди стріли A→B до горизонту (+ вгору)
  psi      — внутрішній кут між рукояттю (B→E) і стрілою (B→A):  ~45° складено, ~165° розкрито
  omega    — кут ковша відносно рукояті (0 = вісь ковша E→зуб продовжує вісь рукояті), + = закривання (підкручування)

Використання:
  python3 kinematics.py                 # звіт для геометрії за замовчуванням (GEOM)
  python3 kinematics.py --search        # випадковий пошук положень кріплень
  python3 kinematics.py --json          # JSON з усіма точками/діапазонами (для перевірки SCAD)
"""
import math, json, argparse, random, sys

# ----------------------------------------------------------------------------
# Закуплені циліндри (дані з паспорта виробника). closed = міжосьова довжина у зведеному стані.
# ----------------------------------------------------------------------------
CYL = {
    'boom':   dict(name='ГЦ 63.40.500.700 (ШС-30)',      bore=63, rod=40, stroke=500, closed=700, pin=30),
    'stick':  dict(name='ГЦ ЦС50.25.400.600 (ШС-25)',    bore=50, rod=25, stroke=400, closed=600, pin=25),
    'bucket': dict(name='ГЦ ЦС50.25.300.510 (ШС-25)',    bore=50, rod=25, stroke=300, closed=510, pin=25),
}
for c in CYL.values():
    c['open'] = c['closed'] + c['stroke']
    c['A_push'] = math.pi / 4 * c['bore'] ** 2                       # мм²
    c['A_pull'] = math.pi / 4 * (c['bore'] ** 2 - c['rod'] ** 2)     # мм²

P_NOM = 16.0   # МПа (160 бар) робочий
P_MAX = 20.0   # МПа (200 бар) макс. по паспорту циліндра / запобіжний клапан

def cyl_force(key, p_mpa, push=True):
    """Сила циліндра, кН."""
    c = CYL[key]
    return p_mpa * (c['A_push'] if push else c['A_pull']) / 1000.0

# ----------------------------------------------------------------------------
# Геометрія (проєктні змінні). Значення за замовчуванням = обраний варіант.
# ----------------------------------------------------------------------------
GEOM = dict(
    # --- стріла: два прямих сегменти труби з переломом (deflection) між ними
    L1=900,         # довжина 1-го сегмента (від осі A до точки перелому K), мм
    L2=700,         # довжина 2-го сегмента (від K до осі B), мм
    bend=35.0,      # кут перелому між сегментами, град (0 = пряма стріла)
    # --- циліндр стріли: база C на поворотній колоні (відн. A), шток на кронштейні D під стрілою
    Cx=150, Cy=-300,
    sD=1050,        # відстань від A до D вздовж осі стріли (ламаної A→K→B); > L1 → одразу за переломом на 2-му сегменті
    eD=120,         # зміщення D від осі сегмента вниз (півширини труби + кронштейн)
    # --- рукоять
    Ls=950,         # довжина рукояті: вісь B → вісь ковша E
    # --- циліндр рукояті: база F на верхній полиці стріли, шток на п'яті G рукояті
    sF=715,         # відстань від B назад вздовж осі стріли (ламаної) до F (> L2 → на 1-му сегменті перед переломом)
    eF=158,         # зміщення F над віссю сегмента
    hx=215,         # п'ята: відстань від B назад вздовж осі рукояті
    hy=132,         # п'ята: зміщення до верхньої (зовнішньої) сторони рукояті
    # --- циліндр ковша: база H на верхній полиці рукояті, шток у точці J (шарнір коромисла/тяги)
    sH=246,         # відстань від B вперед вздовж рукояті до H
    eH=120,         # зміщення H над віссю рукояті
    rx=152,         # вісь коромисла R: відстань від E назад вздовж рукояті
    ry=75,          # зміщення R над віссю рукояті (над верхньою полицею труби)
    Lr=289,         # довжина коромисла R→J
    Ll=327,         # довжина тяги J→Q
    qx=27, qy=121,   # вушко ковша Q у системі ковша (початок E, x вздовж осі ковша до зуба, y = зовнішній бік)
    tip=480,        # відстань від осі E до різальної кромки (зуба) ковша
    # --- база машини
    A_height=650,   # висота осі A над землею
    A_setback=0,    # (не використовується у 2D)
)

# ----------------------------------------------------------------------------
# Векторна математика
# ----------------------------------------------------------------------------
def rot(v, a):
    r = math.radians(a); c, s = math.cos(r), math.sin(r)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def mul(a, k): return (a[0] * k, a[1] * k)
def norm(a): return math.hypot(a[0], a[1])
def dist(a, b): return norm(sub(a, b))
def unit(a): n = norm(a); return (a[0] / n, a[1] / n)
def cross(a, b): return a[0] * b[1] - a[1] * b[0]
def ang(v): return math.degrees(math.atan2(v[1], v[0]))

def circle_intersect(p0, r0, p1, r1, side=+1):
    """Перетин двох кіл; side=+1 — точка ліворуч від напрямку p0→p1 (CCW), −1 — праворуч."""
    d = dist(p0, p1)
    if d < 1e-9 or d > r0 + r1 + 1e-9 or d < abs(r0 - r1) - 1e-9:
        return None
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h2 = r0 * r0 - a * a
    h = math.sqrt(max(h2, 0.0))
    u = unit(sub(p1, p0))
    m = add(p0, mul(u, a))
    n = (-u[1], u[0])
    return add(m, mul(n, side * h))

# ----------------------------------------------------------------------------
# Похідна геометрія стріли
# ----------------------------------------------------------------------------
def boom_shape(g):
    """Кут 1-го сегмента над хордою alpha1 і довжина хорди Lb."""
    b = math.radians(g['bend'])
    alpha1 = math.degrees(math.atan2(g['L2'] * math.sin(b), g['L1'] + g['L2'] * math.cos(b)))
    Lb = math.sqrt(g['L1'] ** 2 + g['L2'] ** 2 + 2 * g['L1'] * g['L2'] * math.cos(b))
    return alpha1, Lb

def boom_axis_pt(g, s, A, K, u1, n1, u2, n2):
    """Точка на осі стріли (ламана A→K→B) на відстані s від A та ліва нормаль ("верх") у цій точці."""
    if s <= g['L1']:
        return add(A, mul(u1, s)), n1
    return add(K, mul(u2, s - g['L1'])), n2

def boom_points(g, theta_b):
    """Точки стріли у світових координатах при куті хорди theta_b."""
    alpha1, Lb = boom_shape(g)
    A = (0.0, 0.0)
    a1 = theta_b + alpha1            # напрямок 1-го сегмента
    a2 = a1 - g['bend']              # напрямок 2-го сегмента
    u1, u2 = rot((1, 0), a1), rot((1, 0), a2)
    n1, n2 = rot((0, 1), a1), rot((0, 1), a2)
    K = add(A, mul(u1, g['L1']))
    B = add(K, mul(u2, g['L2']))
    pD, nD = boom_axis_pt(g, g['sD'], A, K, u1, n1, u2, n2)
    D = add(pD, mul(nD, -g['eD']))                                   # під стрілою
    pF, nF = boom_axis_pt(g, g['L1'] + g['L2'] - g['sF'], A, K, u1, n1, u2, n2)
    F = add(pF, mul(nF, g['eF']))                                    # над стрілою
    C = (g['Cx'], g['Cy'])
    return dict(A=A, K=K, B=B, C=C, D=D, F=F, a1=a1, a2=a2, Lb=Lb, alpha1=alpha1)

def stick_points(g, bp, psi):
    """Точки рукояті при внутрішньому куті psi (між B→A і B→E)."""
    B = bp['B']
    dir_BA = ang(sub(bp['A'], B))
    a_s = dir_BA + psi               # напрямок B→E (CCW від B→A на psi, тобто "вниз" при psi<180)
    # Примітка: для стріли, що дивиться вправо, B→A ≈ 180°; psi=90 → 270° = вниз. Вірно.
    us, ns = rot((1, 0), a_s), rot((0, 1), a_s)
    # ns (ліва нормаль) при psi=180 (рукоять вперед) дивиться ВГОРУ, при psi=90 (рукоять вниз) — вперед.
    # "Верхня/зовнішня" сторона рукояті (де п'ята і циліндр ковша) = ns.
    top = ns
    E = add(B, mul(us, g['Ls']))
    G = add(add(B, mul(us, -g['hx'])), mul(top, g['hy']))
    H = add(add(B, mul(us, g['sH'])), mul(top, g['eH']))
    R = add(add(E, mul(us, -g['rx'])), mul(top, g['ry']))
    return dict(E=E, G=G, H=H, R=R, us=us, top=top, a_s=a_s)

def bucket_solve(g, sp, Lc, prev=None):
    """Положення J (шток/коромисло/тяга), Q (вушко ковша) і кут ковша omega за довжиною циліндра Lc.
    Гілки обираються за неперервністю відносно prev=(J,Q); без prev — "зовнішня" гілка (J над лінією H→R,
    Q з боку top). None якщо положення недосяжне (мертва точка / розрив ланцюга).
    Система ковша: початок E, x̂ вздовж осі ковша до зуба, ŷ = ліва нормаль. omega = кут осі ковша відносно осі
    рукояті, додатній = підкручування (закривання): x̂_k = rot(us, -omega)."""
    H, R, E = sp['H'], sp['R'], sp['E']
    LQ = math.hypot(g['qx'], g['qy'])
    candJ = [c for c in (circle_intersect(H, Lc, R, g['Lr'], s) for s in (+1, -1)) if c is not None]
    if not candJ: return None
    if prev is None:
        J = max(candJ, key=lambda c: cross(sub(R, H), sub(c, H)))          # ліворуч від H→R (бік top)
    else:
        J = min(candJ, key=lambda c: dist(c, prev[0]))
    candQ = [c for c in (circle_intersect(J, g['Ll'], E, LQ, s) for s in (+1, -1)) if c is not None]
    if not candQ: return None
    if prev is None:
        Q = max(candQ, key=lambda c: c[0] * sp['top'][0] + c[1] * sp['top'][1])
    else:
        Q = min(candQ, key=lambda c: dist(c, prev[1]))
    if prev is not None and (dist(J, prev[0]) > 60 or dist(Q, prev[1]) > 60):
        return None   # стрибок гілки = мертва точка
    axis_world = ang(sub(Q, E)) - ang((g['qx'], g['qy']))
    omega = norm_ang(sp['a_s'] - axis_world)
    # сили: F_link = F_cyl * arm_cyl(R) / arm_link(R); T_bucket = F_link * arm_link(E)
    arm_cyl_R = moment_arm(R, J, H)
    uJQ = unit(sub(Q, J))
    arm_link_R = abs(cross(sub(J, R), uJQ))
    arm_link_E = abs(cross(sub(Q, E), uJQ))
    ratio = (arm_cyl_R / arm_link_R * arm_link_E) if arm_link_R > 1e-6 else 0.0   # T_bucket / F_cyl, мм
    return dict(J=J, Q=Q, omega=omega, arm_cyl_R=arm_cyl_R, arm_link_R=arm_link_R, arm_link_E=arm_link_E, ratio=ratio)

def bucket_sweep(g, sp, n=61):
    """Обхід усього ходу циліндра ковша від середини в обидва боки за неперервністю.
    Повертає список (Lc, sol|None) за зростанням Lc."""
    c = CYL['bucket']
    Ls = [c['closed'] + c['stroke'] * i / (n - 1) for i in range(n)]
    mid = n // 2
    out = [None] * n
    s0 = bucket_solve(g, sp, Ls[mid])
    out[mid] = s0
    if s0 is None: return list(zip(Ls, out))
    prev = (s0['J'], s0['Q'])
    for i in range(mid + 1, n):
        s = bucket_solve(g, sp, Ls[i], prev)
        if s is None: break
        out[i] = s; prev = (s['J'], s['Q'])
    prev = (s0['J'], s0['Q'])
    for i in range(mid - 1, -1, -1):
        s = bucket_solve(g, sp, Ls[i], prev)
        if s is None: break
        out[i] = s; prev = (s['J'], s['Q'])
    return list(zip(Ls, out))

def norm_ang(a):
    while a > 180: a -= 360
    while a <= -180: a += 360
    return a

def bucket_points_fwd(g, sp, omega):
    """Пряма задача (як у SCAD): за кутом ковша omega → Q, J, довжина циліндра. Гілка: J ліворуч від R→Q."""
    E, R, H = sp['E'], sp['R'], sp['H']
    axis = sp['a_s'] - omega
    Q = add(E, rot((g['qx'], g['qy']), axis))
    J = circle_intersect(R, g['Lr'], Q, g['Ll'], +1)
    if J is None: return None
    return dict(Q=Q, J=J, L=dist(H, J))

def check_bucket_fwd(g, psi=120.0, out=sys.stdout):
    """Перехресна перевірка: пряма задача L(omega) проти оберненої (sweep). Друкує макс. розбіжність."""
    bp = boom_points(g, 0.0); sp = stick_points(g, bp, psi)
    res = bucket_sweep(g, sp, 61)
    worst = 0.0; n = 0
    for Lc, s in res:
        if s is None: continue
        f = bucket_points_fwd(g, sp, s['omega'])
        if f is None:
            print(f"  omega={s['omega']:.1f}: пряма задача не має розв'язку!", file=out); worst = 1e9; continue
        d = abs(f['L'] - Lc) + dist(f['J'], s['J']); worst = max(worst, d); n += 1
    print(f"  перевірка гілки ковша: {n} точок, макс. розбіжність {worst:.3f} мм", file=out)
    return worst

# ----------------------------------------------------------------------------
# Довжини циліндрів ↔ кути
# ----------------------------------------------------------------------------
def boom_cyl_len(g, theta_b):
    bp = boom_points(g, theta_b); return dist(bp['C'], bp['D'])

def stick_cyl_len(g, psi, theta_b=0.0):
    bp = boom_points(g, theta_b); sp = stick_points(g, bp, psi); return dist(bp['F'], sp['G'])

def solve_monotone(f, target, lo, hi, tol=1e-6):
    """Бісекція для монотонної f на [lo, hi]."""
    flo, fhi = f(lo), f(hi)
    if (flo - target) * (fhi - target) > 0: return None
    for _ in range(80):
        mid = 0.5 * (lo + hi); fm = f(mid)
        if (fm - target) * (flo - target) <= 0: hi, fhi = mid, fm
        else: lo, flo = mid, fm
        if abs(hi - lo) < tol: break
    return 0.5 * (lo + hi)

def boom_range(g):
    c = CYL['boom']
    # Довжина CD монотонно зростає з theta_b на робочому інтервалі
    th_min = solve_monotone(lambda t: boom_cyl_len(g, t), c['closed'], -90, 120)
    th_max = solve_monotone(lambda t: boom_cyl_len(g, t), c['open'], -90, 120)
    return th_min, th_max

def stick_range(g):
    c = CYL['stick']
    # Довжина FG монотонно СПАДАЄ зі зростанням psi (розкриття → циліндр коротший)
    psi_max = solve_monotone(lambda p: stick_cyl_len(g, p), c['closed'], 10, 179)
    psi_min = solve_monotone(lambda p: stick_cyl_len(g, p), c['open'], 10, 179)
    return psi_min, psi_max

def bucket_range(g, psi=120.0, n=61):
    """(список (Lc, sol), omega_min, omega_max, увесь_хід_досяжний). Не залежить від psi/theta (відносна геометрія)."""
    bp = boom_points(g, 0.0); sp = stick_points(g, bp, psi)
    res = bucket_sweep(g, sp, n)
    valid = [s['omega'] for _, s in res if s is not None]
    return res, (min(valid) if valid else None), (max(valid) if valid else None), len(valid) == n

def moment_arm(joint, rod_end, base):
    """Плече сили циліндра відносно шарніра joint (мм)."""
    u = unit(sub(rod_end, base))
    return abs(cross(sub(rod_end, joint), u))

def transmission_angle(joint, rod_end, base):
    """Кут між важелем (joint→rod_end) і віссю циліндра, град (90 = ідеально)."""
    a = unit(sub(rod_end, joint)); b = unit(sub(rod_end, base))
    return math.degrees(math.acos(max(-1, min(1, abs(a[0] * b[0] + a[1] * b[1])))))

# ----------------------------------------------------------------------------
# Звіт
# ----------------------------------------------------------------------------
def report(g, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    alpha1, Lb = boom_shape(g)
    p(f"# Кінематика (геометрія: L1={g['L1']}, L2={g['L2']}, bend={g['bend']}°, хорда стріли Lb={Lb:.0f} мм, alpha1={alpha1:.1f}°)")
    p()
    p("## Циліндри")
    p("| Циліндр | Паспорт | Зведений | Розкритий | Push @160 бар | Pull @160 бар | Push @200 | Pull @200 |")
    p("|---|---|---|---|---|---|---|---|")
    for k in ('boom', 'stick', 'bucket'):
        c = CYL[k]
        p(f"| {k} | {c['name']} | {c['closed']} | {c['open']} | {cyl_force(k, P_NOM):.1f} кН | {cyl_force(k, P_NOM, False):.1f} кН | {cyl_force(k, P_MAX):.1f} кН | {cyl_force(k, P_MAX, False):.1f} кН |")
    p()
    th_min, th_max = boom_range(g)
    if th_min is None or th_max is None:
        p(f"## Стріла: ДІАПАЗОН НЕ РОЗВ'ЯЗУЄТЬСЯ (L_cyl при -90°={boom_cyl_len(g,-90):.0f}, при +120°={boom_cyl_len(g,120):.0f}; потрібно 700..1200)")
        th_min, th_max = -20.0, 60.0
    p(f"## Стріла: кут хорди theta_b ∈ [{th_min:.1f}°, {th_max:.1f}°]  (діапазон {th_max - th_min:.1f}°)")
    p(f"   база C=({g['Cx']},{g['Cy']}), кронштейн D: sD={g['sD']} eD={g['eD']} → |AD|={dist((0,0), boom_points(g,0)['D']):.0f}, |AC|={norm((g['Cx'],g['Cy'])):.0f}")
    p("| theta_b | L_cyl | плече, мм | кут передачі | M@160бар push, кНм | тягове зусилля на кінці стріли @160, кН |")
    p("|---|---|---|---|---|---|")
    for t in frange(th_min, th_max, 7):
        bp = boom_points(g, t); L = dist(bp['C'], bp['D'])
        arm = moment_arm(bp['A'], bp['D'], bp['C']); ta = transmission_angle(bp['A'], bp['D'], bp['C'])
        M = cyl_force('boom', P_NOM) * arm / 1000
        p(f"| {t:6.1f} | {L:6.0f} | {arm:5.0f} | {ta:4.0f}° | {M:5.1f} | {M / (Lb / 1000):5.1f} |")
    p()
    ps_min, ps_max = stick_range(g)
    if ps_min is None or ps_max is None:
        p(f"## Рукоять: ДІАПАЗОН НЕ РОЗВ'ЯЗУЄТЬСЯ (L_cyl при psi=10°={stick_cyl_len(g,10):.0f}, при 179°={stick_cyl_len(g,179):.0f}; потрібно 600..1000)")
        ps_min, ps_max = 50.0, 160.0
    p(f"## Рукоять: внутрішній кут psi ∈ [{ps_min:.1f}°, {ps_max:.1f}°]  (діапазон {ps_max - ps_min:.1f}°)")
    p(f"   база F: sF={g['sF']} eF={g['eF']}; п'ята G: hx={g['hx']} hy={g['hy']} → |BG|={math.hypot(g['hx'],g['hy']):.0f}, |BF|={dist(boom_points(g,0)['B'], boom_points(g,0)['F']):.0f}")
    p("| psi | L_cyl | плече, мм | кут передачі | M@160бар, кНм | зусилля на осі ковша E @160, кН |")
    p("|---|---|---|---|---|---|")
    for s in frange(ps_min, ps_max, 7):
        bp = boom_points(g, 0); sp = stick_points(g, bp, s); L = dist(bp['F'], sp['G'])
        arm = moment_arm(bp['B'], sp['G'], bp['F']); ta = transmission_angle(bp['B'], sp['G'], bp['F'])
        push = L > (CYL['stick']['closed'] + CYL['stick']['open']) / 2  # умовно
        M = cyl_force('stick', P_NOM) * arm / 1000
        p(f"| {s:6.1f} | {L:6.0f} | {arm:5.0f} | {ta:4.0f}° | {M:5.1f} | {M / (g['Ls'] / 1000):5.1f} |")
    p()
    res, om_min, om_max, ok = bucket_range(g)
    p(f"## Ківш: omega ∈ [{om_min if om_min is None else round(om_min,1)}°, {om_max if om_max is None else round(om_max,1)}°]"
      f"  (діапазон {'' if om_min is None else round(om_max - om_min,1)}°, вся довжина ходу досяжна: {ok})")
    p(f"   база H: sH={g['sH']} eH={g['eH']}; коромисло R: rx={g['rx']} ry={g['ry']}, Lr={g['Lr']}, тяга Ll={g['Ll']}, вушко Q=({g['qx']},{g['qy']}), радіус зуба tip={g['tip']}")
    p("| L_cyl | omega | плече цил. на коромислі, мм | плече тяги на коромислі | плече тяги на осі E | T_ковша/F_цил, мм | зусилля на зубі @160 бар push, кН |")
    p("|---|---|---|---|---|---|---|")
    for Lc, s in res[::6]:
        if s is None:
            p(f"| {Lc:5.0f} | — | — | — | — | — | — |"); continue
        Ftip = cyl_force('bucket', P_NOM) * s['ratio'] / g['tip']
        p(f"| {Lc:5.0f} | {s['omega']:6.1f} | {s['arm_cyl_R']:5.0f} | {s['arm_link_R']:5.0f} | {s['arm_link_E']:5.0f} | {s['ratio']:5.0f} | {Ftip:5.1f} |")
    p()
    p("## Робоча зона (від осі A; земля на {0} мм нижче A)".format(g['A_height']))
    env = envelope(g)
    for k, v in env.items():
        p(f"- {k}: {v:.0f} мм")
    return dict(theta=(th_min, th_max), psi=(ps_min, ps_max), omega=(om_min, om_max), envelope=env)

def frange(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]

def envelope(g):
    th_min, th_max = boom_range(g); ps_min, ps_max = stick_range(g)
    _, om_min, om_max, _ = bucket_range(g)
    if th_min is None or th_max is None: th_min, th_max = -20.0, 60.0
    if ps_min is None or ps_max is None: ps_min, ps_max = 50.0, 160.0
    if om_min is None or om_max is None: om_min, om_max = -20.0, 140.0
    ground = -g['A_height']
    max_reach_ground = -1e9; max_depth = 1e9; max_height = -1e9; max_reach = -1e9
    for t in frange(th_min, th_max, 61):
        bp = boom_points(g, t)
        for s in frange(ps_min, ps_max, 61):
            sp = stick_points(g, bp, s)
            # Ківш обходиться на ВСЬОМУ ходу свого циліндра. Два умовні напрямки
            # ("по осі рукояті" і "прямовисно вниз") занижували виліт і висоту:
            # глибина від них не залежить, а от вістря вище за все саме при
            # розкритому ковші, якого серед тих двох напрямків не було.
            for o in frange(om_min, om_max, 31):
                T = add(sp['E'], rot((g['tip'], 0), sp['a_s'] - o))
                max_reach = max(max_reach, T[0])
                max_depth = min(max_depth, T[1])
                max_height = max(max_height, T[1])
                if abs(T[1] - ground) < 25: max_reach_ground = max(max_reach_ground, T[0])
    return {
        'макс. виліт зуба (будь-яка висота)': max_reach,
        'виліт зуба на рівні землі': max_reach_ground,
        'глибина копання (нижче землі)': ground - max_depth,
        'макс. висота зуба над землею': max_height - ground,
        'макс. висота осі ковша E над землею': max((stick_points(g, boom_points(g, th_max), s)['E'][1] for s in frange(ps_min, ps_max, 41))) - ground,
    }

# ----------------------------------------------------------------------------
# Пошук геометрії кріплень
# ----------------------------------------------------------------------------
def search(g0, n=20000, seed=1):
    rnd = random.Random(seed)
    print("### Пошук: циліндр стріли (ціль: theta ∈ ~[-35, +60], макс. мін. плече)")
    best = []
    for _ in range(n):
        g = dict(g0)
        g['Cx'] = rnd.randint(50, 300); g['Cy'] = -rnd.randint(200, 420)
        g['sD'] = rnd.randint(500, g['L1'] + g['L2'] - 150)
        r = boom_range(g)
        if None in r: continue
        th_min, th_max = r
        arms = [moment_arm(boom_points(g, t)['A'], boom_points(g, t)['D'], boom_points(g, t)['C']) for t in frange(th_min, th_max, 9)]
        # ціль: theta_min ≤ −40, діапазон ≥ 95°, theta_max ≥ 55, мін. плече якнайбільше (кут передачі на кінцях ≥ ~15°)
        score = min(arms) - 6 * max(0, th_min + 40) - 6 * max(0, 95 - (th_max - th_min)) - 3 * max(0, 55 - th_max)
        best.append((score, th_min, th_max, min(arms), max(arms), g['Cx'], g['Cy'], g['sD']))
    best.sort(reverse=True)
    for b in best[:8]:
        print(f"score={b[0]:7.1f} theta=[{b[1]:6.1f},{b[2]:6.1f}] arm=[{b[3]:4.0f},{b[4]:4.0f}] Cx={b[5]} Cy={b[6]} sD={b[7]}")
    print("### Пошук: циліндр рукояті (ціль: psi ∈ ~[45, 165], макс. мін. плече)")
    best = []
    for _ in range(n):
        g = dict(g0)
        g['sF'] = rnd.randint(350, g['L1'] + g['L2'] - 150); g['hx'] = rnd.randint(140, 320); g['hy'] = rnd.randint(0, 260)
        r = stick_range(g)
        if None in r: continue
        ps_min, ps_max = r
        bp = boom_points(g, 0)
        arms = [moment_arm(bp['B'], stick_points(g, bp, s)['G'], bp['F']) for s in frange(ps_min, ps_max, 9)]
        # ціль: psi_min ≤ 45, psi_max ≥ 160, мін. плече якнайбільше
        score = min(arms) - 5 * max(0, ps_min - 45) - 5 * max(0, 160 - ps_max)
        best.append((score, ps_min, ps_max, min(arms), max(arms), g['sF'], g['hx'], g['hy']))
    best.sort(reverse=True)
    for b in best[:8]:
        print(f"score={b[0]:7.1f} psi=[{b[1]:6.1f},{b[2]:6.1f}] arm=[{b[3]:4.0f},{b[4]:4.0f}] sF={b[5]} hx={b[6]} hy={b[7]}")
    print("### Пошук: важільна система ковша (ціль: діапазон omega ≥ 160°, увесь хід досяжний, макс. мін. плече)")
    best = []
    for _ in range(n):
        g = dict(g0)
        g['sH'] = rnd.randint(120, 320); g['rx'] = rnd.randint(130, 260); g['Lr'] = rnd.randint(150, 320)
        g['Ll'] = rnd.randint(150, 340); g['qx'] = rnd.randint(-80, 60); g['qy'] = rnd.randint(100, 200)
        res, om_min, om_max, ok = bucket_range(g, n=31)
        if not ok: continue
        ratios = [s['ratio'] for _, s in res]
        span = om_max - om_min
        # ціль: діапазон 160..185°, om_max (повне підкручування) ≈ +120..+135°, макс. мін. передавальне плече
        score = min(ratios) - 2 * max(0, 160 - span) - 1 * max(0, span - 185) - 1 * abs(om_max - 125)
        best.append((score, om_min, om_max, min(ratios), max(ratios), g['sH'], g['rx'], g['Lr'], g['Ll'], g['qx'], g['qy']))
    best.sort(reverse=True)
    for b in best[:8]:
        print(f"score={b[0]:7.1f} omega=[{b[1]:6.1f},{b[2]:6.1f}] T/F=[{b[3]:4.0f},{b[4]:4.0f}] sH={b[5]} rx={b[6]} Lr={b[7]} Ll={b[8]} q=({b[9]},{b[10]})")

def dump_json(g):
    th = boom_range(g); ps = stick_range(g); res, om_min, om_max, ok = bucket_range(g)
    out = dict(geom=g, cyl=CYL, theta=th, psi=ps, omega=(om_min, om_max),
               samples=[])
    for t in frange(th[0], th[1], 5):
        bp = boom_points(g, t)
        for s in frange(ps[0], ps[1], 5):
            sp = stick_points(g, bp, s)
            out['samples'].append(dict(theta=t, psi=s, Lboom=dist(bp['C'], bp['D']), Lstick=dist(bp['F'], sp['G']),
                                       B=bp['B'], D=bp['D'], F=bp['F'], G=sp['G'], E=sp['E']))
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--search', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check', action='store_true', help='перехресна перевірка прямої/оберненої задачі ковша')
    ap.add_argument('--set', nargs='*', default=[], help='override GEOM, напр. --set L1=1000 bend=30')
    a = ap.parse_args()
    g = dict(GEOM)
    for kv in a.set:
        k, v = kv.split('='); g[k] = float(v) if '.' in v or '-' in v else int(v)
    if a.search: search(g)
    elif a.json: dump_json(g)
    elif a.check: check_bucket_fwd(g)
    else: report(g)
