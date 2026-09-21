#!/usr/bin/env python3
"""
strength.py — розрахунок міцності стріли та рукояті міні-екскаватора (плоска статика + опір матеріалів).

Використовує геометрію з kinematics.py (GEOM, CYL). Для кожного розрахункового випадку:
  1) знаходить зусилля в усіх шарнірах послідовним рівноважним розрахунком ланок
     (ківш → тяга/коромисло → рукоять → стріла), зовнішнє навантаження на зубі ковша
     обмежене граничним зусиллям відповідного циліндра;
  2) будує епюри N, V, M уздовж осі стріли (ламана) і рукояті;
  3) перевіряє напруження у перерізах труби (з підсиленням накладками там, де вони є),
     тиск у втулках, згин/зріз пальців, зварні шви кронштейнів;
  4) видає рекомендації: профіль, накладки (розмір, товщина, марка сталі), катети швів.

Запуск:  python3 strength.py            — звіт (Markdown) у stdout
         python3 strength.py --sections — таблиця перерізів-кандидатів
"""
import math, sys, argparse
import kinematics as K
from kinematics import add, sub, mul, norm, dist, unit, cross, rot, ang

# ----------------------------------------------------------------------------
# Матеріали (МПа). Джерела: ДСТУ 2651/ГОСТ 380 (Ст3), ГОСТ 19281 (09Г2С), ГОСТ 1050 (сталь 45), ГОСТ 4543 (40Х)
# ----------------------------------------------------------------------------
MAT = {
    'Ст3сп (S235JR) — труба профільна':      dict(fy=235, fu=360),
    'S235JR (Ст3сп) — лист/смуга':           dict(fy=235, fu=360),   # те, що реально є у звичайному сортаменті металобаз
    '09Г2С (S355) — лист 8–20 мм':           dict(fy=325, fu=470),   # t ≤ 10: 345; 10–20: 325 (рідше буває в наявності — шукати окремо)
    'Сталь 45 нормалізована — палець':       dict(fy=355, fu=600),
    '40Х покращена — палець':                dict(fy=785, fu=980),
    'Шкворінь 45Х ТВЧ 50–54 HRC (Газель/ГАЗ-53)': dict(fy=600, fu=900),  # оцінка: серцевина нормалізована, поверхня гартована
    'Сталь 20 труба — втулка (без ТО)':      dict(fy=245, fu=410),
}
TUBE_MAT = 'Ст3сп (S235JR) — труба профільна'
PLATE_MAT = 'S235JR (Ст3сп) — лист/смуга'
PIN_MAT = 'Шкворінь 45Х ТВЧ 50–54 HRC (Газель/ГАЗ-53)'
PIN_MAT_ALT = '40Х покращена — палець'

# Допустимі напруження: коефіцієнт запасу по границі текучості
SF_NOM  = 1.5    # при робочому тиску 160 бар (звичайна робота, багатократно) → σ ≤ fy/1.5
SF_PEAK = 1.15   # при 200 бар (запобіжний клапан) → σ ≤ fy/1.15
SF_LOCK = 1.0    # 250 бар — замкнений циліндр, зовнішнє навантаження (стрибок тиску) → σ ≤ fy
P_LOCK = 25.0    # МПа
DYN = 1.25       # динамічний коефіцієнт (удар при копанні) до зусиль від гідравліки у випадку NOM
# Межа стійкості машини: вертикальна сила на зубі (підйом вантажу / притискання) не може перевищити те, що дозволяє
# маса машини на аутригерах (РД 22-158-86, P0(4)). Для причіпного екскаватора ~600–800 кг оцінка ≈ 8–10 кН (близький виліт).
# Параметр! Уточнити за масою/базою машини. Копальні випадки (відрив/підтягування) НЕ обмежуємо — консервативно.
F_STAB = 15.0    # кН (припущення; без обмеження циліндр стріли на близькому вильоті дає до ~22 кН — задайте --fstab 99)
P_BEAR_STEEL = 30.0   # МПа, сталь/сталь для ГРАНИЧНОГО випадку 250 бар (Roloff/Matek: 30 статично / 24 у русі; при 160 бар тиск ×0.64)
P_BEAR_HARD  = 50.0   # МПа, втулка сталь 45 гартована / бронза БрАЖ9-4
TAU_WELD = 0.6        # [τ_w] = 0.6·fy електрод/дріт (Св-08Г2С, Э50А) ≈ 150 МПа при SF≈1.5 → беремо 150 МПа

# ----------------------------------------------------------------------------
# Перерізи: прямокутні профільні труби (h — у площині згину, w — ширина, t — стінка)
# Список — популярні розміри звичайного сортаменту. Маса — по ДСТУ 8940 / ГОСТ 8645 (з заокругленням кутів r≈1.5t).
# ----------------------------------------------------------------------------
TUBES = [
    (100, 50, 4), (100, 50, 5), (100, 60, 4), (100, 60, 5), (100, 80, 4), (100, 80, 5),
    (100, 100, 4), (100, 100, 5), (120, 60, 4), (120, 60, 5), (120, 80, 4), (120, 80, 5), (120, 80, 6),
    (120, 120, 4), (120, 120, 5), (140, 80, 4), (140, 80, 5), (140, 100, 5), (150, 100, 4), (150, 100, 5), (150, 100, 6),
    (160, 80, 5), (160, 120, 5),
]

def rhs_props(h, w, t, r_out=None):
    """Геометричні характеристики прямокутної труби відносно сильної осі (згин у площині h)."""
    r_out = 1.5 * t if r_out is None else r_out
    r_in = max(r_out - t, 0.0)
    def rect_with_corners(H, W, r):
        # площа і момент інерції прямокутника H×W з заокругленими кутами радіуса r (відносно горизонтальної осі через центр)
        A = H * W - (4 - math.pi) * r * r
        I = W * H ** 3 / 12 - 4 * ((1 - math.pi / 4) * r ** 4 / 3 - 0.0 ) # спрощено: поправка кутів мала; далі точніше
        # точніша поправка: вирізаний кутовий "квадрат мінус чверть кола" площею (1-π/4)r² з центром ~ (H/2 - 0.223r)
        c = H / 2 - 0.2234 * r
        I = W * H ** 3 / 12 - 4 * ((1 - math.pi / 4) * r * r * c * c)
        return A, I
    A_o, I_o = rect_with_corners(h, w, r_out)
    A_i, I_i = rect_with_corners(h - 2 * t, w - 2 * t, r_in)
    A = A_o - A_i; I = I_o - I_i
    # слабка вісь
    A_o2, I_o2 = rect_with_corners(w, h, r_out); A_i2, I_i2 = rect_with_corners(w - 2 * t, h - 2 * t, r_in)
    I_w = I_o2 - I_i2
    return dict(A=A, I=I, W=I / (h / 2), I_w=I_w, W_w=I_w / (w / 2), mass=A * 7.85e-6 * 1000)  # кг/м

def section_with_plates(tube, plates):
    """Складений переріз: труба + бокові пластини (t_p × h_p кожна, центровані по осі труби)."""
    h, w, t = tube
    p = rhs_props(h, w, t)
    I = p['I']; A = p['A']; hmax = h / 2
    for (tp, hp, n) in plates:      # n — кількість пластин
        I += n * tp * hp ** 3 / 12; A += n * tp * hp; hmax = max(hmax, hp / 2)
    return dict(A=A, I=I, W=I / hmax)

# ----------------------------------------------------------------------------
# Статика ланок
# ----------------------------------------------------------------------------
def solve_forces(g, th, psi, om, F_tip, p_mpa):
    """Зусилля у шарнірах для зовнішньої сили F_tip (кН, вектор у світі) на зубі ковша.
    Повертає dict сил (кН, вектори), що діють НА кожну ланку в кожному шарнірі, та зусилля циліндрів (кН, + = стиск/push)."""
    bp = K.boom_points(g, th); sp = K.stick_points(g, bp, psi)
    fw = K.bucket_points_fwd(g, sp, om)
    if fw is None: return None
    A, B, C, D, F = bp['A'], bp['B'], bp['C'], bp['D'], bp['F']
    E, G, H, R = sp['E'], sp['G'], sp['H'], sp['R']
    J, Q = fw['J'], fw['Q']
    T = add(E, rot((g['tip'], 0), sp['a_s'] - om))
    def moment(p, f, about): return cross(sub(p, about), f)
    # --- ківш: F_tip у T, сила тяги у Q (вздовж J→Q), реакція у E
    u_link = unit(sub(J, Q))                      # напрямок дії тяги на ківш: до J (розтяг) якщо S>0
    S_link = -moment(T, F_tip, E) / cross(sub(Q, E), u_link)   # ΣM_E = 0
    F_link_on_bucket = mul(u_link, S_link)
    F_E_on_bucket = mul(add(F_tip, F_link_on_bucket), -1)
    # --- коромисло: у J діє тяга (−F_link_on_bucket) і циліндр ковша (вздовж H→J, стиск = push)
    F_link_on_rocker = mul(F_link_on_bucket, -1)
    u_bc = unit(sub(J, H))                        # push циліндра діє на J у напрямку H→J
    S_bc = -moment(J, F_link_on_rocker, R) / cross(sub(J, R), u_bc)
    F_bc_on_rocker = mul(u_bc, S_bc)
    F_R_on_rocker = mul(add(F_link_on_rocker, F_bc_on_rocker), -1)
    # --- рукоять: у E (−F_E_on_bucket), у R (−F_R_on_rocker), у H (−F_bc_on_rocker: реакція бази циліндра),
    #     у G циліндр рукояті (push діє на G у напрямку F→G), у B реакція
    F_E_on_stick = mul(F_E_on_bucket, -1)
    F_R_on_stick = mul(F_R_on_rocker, -1)
    F_H_on_stick = mul(F_bc_on_rocker, -1)
    u_sc = unit(sub(G, F))
    M_B = moment(E, F_E_on_stick, B) + moment(R, F_R_on_stick, B) + moment(H, F_H_on_stick, B)
    S_sc = -M_B / cross(sub(G, B), u_sc)
    F_G_on_stick = mul(u_sc, S_sc)
    F_B_on_stick = mul(add(add(F_E_on_stick, F_R_on_stick), add(F_H_on_stick, F_G_on_stick)), -1)
    # --- стріла: у B (−F_B_on_stick), у F (−F_G_on_stick), у D циліндр стріли (push діє на D у напрямку C→D), у A реакція
    F_B_on_boom = mul(F_B_on_stick, -1)
    F_F_on_boom = mul(F_G_on_stick, -1)
    u_bo = unit(sub(D, C))
    M_A = moment(B, F_B_on_boom, A) + moment(F, F_F_on_boom, A)
    S_bo = -M_A / cross(sub(D, A), u_bo)
    F_D_on_boom = mul(u_bo, S_bo)
    F_A_on_boom = mul(add(add(F_B_on_boom, F_F_on_boom), F_D_on_boom), -1)
    # --- самоперевірка рівноваги кожної ланки (ΣF = 0 вже за побудовою; перевіряємо ΣM відносно довільної точки)
    def resid(pairs, about=(123.0, -456.0)):
        return abs(sum(moment(pt, f, about) for pt, f in pairs)) / max(1.0, sum(norm(f) for _, f in pairs) * 1000.0)
    checks = [resid([(T, F_tip), (Q, F_link_on_bucket), (E, F_E_on_bucket)]),
              resid([(J, F_link_on_rocker), (J, F_bc_on_rocker), (R, F_R_on_rocker)]),
              resid([(E, F_E_on_stick), (R, F_R_on_stick), (H, F_H_on_stick), (G, F_G_on_stick), (B, F_B_on_stick)]),
              resid([(B, F_B_on_boom), (F, F_F_on_boom), (D, F_D_on_boom), (A, F_A_on_boom)])]
    assert max(checks) < 1e-6, f"рівновага порушена: {checks}"
    return dict(points=dict(A=A, B=B, C=C, D=D, F=F, E=E, G=G, H=H, R=R, J=J, Q=Q, T=T),
                cyl=dict(boom=S_bo, stick=S_sc, bucket=S_bc, link=S_link),
                boom=dict(A=F_A_on_boom, B=F_B_on_boom, F=F_F_on_boom, D=F_D_on_boom),
                stick=dict(B=F_B_on_stick, E=F_E_on_stick, R=F_R_on_stick, H=F_H_on_stick, G=F_G_on_stick),
                rocker=dict(R=F_R_on_rocker, J_link=F_link_on_rocker, J_cyl=F_bc_on_rocker),
                bucket=dict(E=F_E_on_bucket, Q=F_link_on_bucket, T=F_tip), bp=bp, sp=sp)

def cyl_limit(key, p_mpa, push):
    return K.cyl_force(key, p_mpa, push)

def scale_to_limit(g, th, psi, om, dir_tip, limiter, p_mpa):
    """Масштабує одиничну силу на зубі у напрямку dir_tip так, щоб циліндр limiter досяг граничного зусилля
    (push якщо S>0, pull якщо S<0 — беремо відповідну межу). Повертає (F_tip вектор, розв'язок)."""
    sol = solve_forces(g, th, psi, om, dir_tip, p_mpa)
    if sol is None: return None, None
    S = sol['cyl'][limiter]
    if abs(S) < 1e-9: return None, None
    lim = cyl_limit(limiter, p_mpa, push=(S > 0))
    k = lim / abs(S)
    F = mul(dir_tip, k)
    return F, solve_forces(g, th, psi, om, F, p_mpa)

# ----------------------------------------------------------------------------
# Епюри уздовж ланок
# ----------------------------------------------------------------------------
def beam_diagram(axis_pts, loads, n=200):
    """Ламана вісь (список точок) з навантаженнями loads = [(точка_прикладання, сила, точка_на_осі_s)].
    Повертає список (s, x, y, N, V, M) — внутрішні зусилля у перерізі s від сил, прикладених ДАЛІ по осі (s' > s).
    Знак M: + = розтяг "верхнього" (лівого) волокна... тут лише модуль важливий."""
    # параметризація ламаної
    seg = []; s_acc = 0.0
    for i in range(len(axis_pts) - 1):
        L = dist(axis_pts[i], axis_pts[i + 1]); seg.append((s_acc, s_acc + L, axis_pts[i], axis_pts[i + 1])); s_acc += L
    total = s_acc
    def at(s):
        for s0, s1, p0, p1 in seg:
            if s <= s1 + 1e-9:
                u = unit(sub(p1, p0)); return add(p0, mul(u, s - s0)), u
        u = unit(sub(seg[-1][3], seg[-1][2])); return seg[-1][3], u
    out = []
    for i in range(n + 1):
        s = total * i / n
        P, u = at(s); nrm = (-u[1], u[0])
        Fx = Fy = M = 0.0
        for (pl, f, sl) in loads:
            if sl > s + 1e-6:
                Fx += f[0]; Fy += f[1]; M += cross(sub(pl, P), f)
        N = -(Fx * u[0] + Fy * u[1]); V = -(Fx * nrm[0] + Fy * nrm[1])
        out.append((s, P[0], P[1], N, V, -M))
    return out, total

def boom_axis_and_loads(g, sol):
    bp = sol['bp']; A, K_, B = bp['A'], bp['K'], bp['B']
    axis = [A, K_, B]
    L1 = dist(A, K_)
    # положення навантажень уздовж осі: A→s=0, D→s=sD, F→s=L1+(L2−sF), B→s=L1+L2
    loads = [(bp['D'], sol['boom']['D'], g['sD']), (bp['F'], sol['boom']['F'], L1 + g['L2'] - g['sF']),
             (B, sol['boom']['B'], L1 + g['L2']), (A, sol['boom']['A'], 0.0)]
    return axis, loads

def stick_axis_and_loads(g, sol):
    sp = sol['sp']; bp = sol['bp']; B = bp['B']; E = sp['E']
    axis = [B, E]
    loads = [(B, sol['stick']['B'], 0.0), (sp['G'], sol['stick']['G'], 0.0 + 1e-3),   # п'ята: біля B
             (sp['H'], sol['stick']['H'], g['sH']), (sp['R'], sol['stick']['R'], g['Ls'] - g['rx']), (E, sol['stick']['E'], g['Ls'])]
    return axis, loads

# ----------------------------------------------------------------------------
# Розрахункові випадки
# ----------------------------------------------------------------------------
def load_cases(g):
    """Список випадків: (назва, th, psi, om, напрямок сили на зубі (одиничний, у системі ковша або світі), обмежувальний циліндр)."""
    th0, th1 = K.boom_range(g); ps0, ps1 = K.stick_range(g); _, om0, om1, _ = K.bucket_range(g)
    cases = []
    # 1. Відрив ґрунту ковшем (bucket breakout): рукоять ~90°, стріла низько, сила ⟂ радіусу ковша
    for th in (th0, th0 + 20):
        for psi in (90, 110, 130, ps1):
            for om in (om0 + 2, 0, 20, 50, 80):      # включно з початком підкручування (найбільші сили в тязі/коромислі)
                cases.append(('Відрив ковшем', th, psi, om, 'tangential', 'bucket'))
    # 2. Підтягування рукояттю (arm crowd): сила ⟂ лінії B→зуб
    for th in (th0, th0 + 20, 10):
        for psi in (70, 90, 110, 130, 150):
            for om in (30, 60):
                cases.append(('Підтягування рукояттю', th, psi, om, 'crowd', 'stick'))
    # 3. Підйом стрілою (boom lift): вертикальна сила вниз на зубі, обмежена push циліндра стріли
    for th in (th0, th0 + 15, 0, 20, 40):
        for psi in (110, 140, ps1):
            cases.append(('Підйом стрілою', th, psi, 10, 'down', 'boom'))
    # 4. Притискання стрілою (boom down, pull циліндра): вертикальна сила вгору на зубі
    for th in (th0 + 5, 0, 20):
        for psi in (90, 120, 150):
            cases.append(('Притискання стрілою', th, psi, 40, 'up', 'boom'))
    return cases

def tip_dir(sol_geom, kind, g, th, psi, om):
    bp = K.boom_points(g, th); sp = K.stick_points(g, bp, psi)
    E = sp['E']; T = add(E, rot((g['tip'], 0), sp['a_s'] - om)); B = bp['B']
    if kind == 'tangential':
        u = unit(sub(T, E)); return (u[1], -u[0])          # ⟂ радіусу, "на себе" при підкручуванні (напрямок уточнюється масштабом)
    if kind == 'crowd':
        u = unit(sub(T, B)); return (u[1], -u[0])
    if kind == 'down': return (0.0, -1.0)
    if kind == 'up': return (0.0, 1.0)

def run_cases(g, p_mpa):
    """Проганяє всі випадки при тиску p_mpa; повертає список результатів з максимальними зусиллями."""
    results = []
    for (name, th, psi, om, kind, limiter) in load_cases(g):
        d = tip_dir(None, kind, g, th, psi, om)
        # Копання (відрив ковшем / підтягування рукояттю) виконується ШТОВХАННЯМ циліндра (поршнева порожнина):
        # напрямок опору ґрунту на зубі обираємо так, щоб активний циліндр працював на стиск (S > 0).
        if kind in ('tangential', 'crowd'):
            probe = solve_forces(g, th, psi, om, d, p_mpa)
            if probe is None: continue
            if probe['cyl'][limiter] < 0: d = mul(d, -1)
        F, sol = scale_to_limit(g, th, psi, om, d, limiter, p_mpa)
        if sol is None: continue
        # Реактивні (замкнені) циліндри: Z50 не має портових запобіжних клапанів, тож замкнена порожнина тримає
        # до P_LOCK (≈250 бар, далі — ущільнення/рукави). Обмежуємо їх на max(p_mpa, P_LOCK): консервативно для конструкції.
        k = 1.0
        for key in ('boom', 'stick', 'bucket'):
            S = sol['cyl'][key]; lim = cyl_limit(key, max(p_mpa, P_LOCK), push=(S > 0))
            if abs(S) > lim * 1.0001: k = min(k, lim / abs(S))
        if k < 1.0:
            F = mul(F, k); sol = solve_forces(g, th, psi, om, F, p_mpa)
        # межа стійкості для вертикальних випадків (підйом/притискання стрілою)
        if kind in ('down', 'up') and norm(F) > F_STAB:
            F = mul(F, F_STAB / norm(F)); sol = solve_forces(g, th, psi, om, F, p_mpa)
        results.append(dict(name=name, th=th, psi=psi, om=om, F=F, Ftip=norm(F), sol=sol))
    return results

# ----------------------------------------------------------------------------
# Перевірки
# ----------------------------------------------------------------------------
def max_internal(results, g, member):
    """Максимальні |M|, |N|, |V| уздовж ланки по всіх випадках; повертає (список профілів M(s) для огинаючої, s_total)."""
    env = None; total = None
    for r in results:
        axis, loads = (boom_axis_and_loads if member == 'boom' else stick_axis_and_loads)(g, r['sol'])
        diag, total = beam_diagram(axis, loads)
        if env is None: env = [[d[0], 0.0, 0.0, 0.0, None] for d in diag]
        for i, d in enumerate(diag):
            if abs(d[5]) > env[i][1]: env[i][1] = abs(d[5]); env[i][4] = r
            env[i][2] = max(env[i][2], abs(d[3])); env[i][3] = max(env[i][3], abs(d[4]))
    return env, total

def pin_check(F_kN, d, boss_len, fork_t, fy_pin, bush_len, p_allow):
    """Палець у вилці: згин M = F(b+2a)/8, зріз двозрізний; тиск у втулці p = F/(d·L)."""
    F = F_kN * 1000
    M = F * (boss_len + 2 * fork_t) / 8
    W = math.pi * d ** 3 / 32
    sigma = M / W
    tau = F / 2 / (math.pi * d * d / 4)
    p_bush = F / (d * bush_len)
    p_fork = F / 2 / (d * fork_t)
    return dict(sigma=sigma, tau=tau, p_bush=p_bush, p_fork=p_fork, sf_bend=fy_pin / sigma if sigma > 0 else 99,
                sf_shear=(0.58 * fy_pin) / tau if tau > 0 else 99, ok_bush=p_bush <= p_allow)

def weld_len_required(F_kN, leg, tau_w=150.0):
    """Довжина кутового шва (мм) для сили F при катеті leg: τ = F / (0.7·k·L) ≤ τ_w."""
    return F_kN * 1000 / (0.7 * leg * tau_w)

# ----------------------------------------------------------------------------
# Звіт
# ----------------------------------------------------------------------------
def fmt_env(env, total, stations):
    """Значення огинаючої у заданих станціях s (мм). M у env — кН·мм → повертаємо кН·м."""
    out = []
    for (label, s) in stations:
        # максимум у вікні ±25 мм: момент стрибає на ексцентричних кронштейнах (D, F, G, H) — беремо гірший бік
        idx = [k for k in range(len(env)) if abs(env[k][0] - s) <= 25] or [min(range(len(env)), key=lambda k: abs(env[k][0] - s))]
        i = max(idx, key=lambda k: env[k][1])
        out.append((label, s, env[i][1] / 1e3, max(env[k][2] for k in idx), max(env[k][3] for k in idx), env[i][4]))
    return out

# ----------------------------------------------------------------------------
# Шарніри: пальці, втулки, вилки, шви
# ----------------------------------------------------------------------------
def joint_table(g, joints, tube_w_boom, tube_w_stick, plate_boss=10, plate_clevis=12, out=sys.stdout):
    """joints — dict максимальних сил (кН) за ключами 'стріла:A', 'рукоять:B', 'циліндр:boom' ... (випадок 250 бар).
    Геометрія шарнірів — як у SCAD (бобишка = ширина труби + 2 накладки; вилки циліндрів = 2 пластини plate_clevis)."""
    p = lambda *a: print(*a, file=out)
    fy_pin = MAT[PIN_MAT]['fy']; fy_alt = MAT[PIN_MAT_ALT]['fy']; fy_pl = MAT[PLATE_MAT]['fy']
    bb = tube_w_boom + 2 * plate_boss; bs = tube_w_stick + 2 * plate_boss
    # (назва, d, сила, b — довжина бобишки/вушка між опорами, a — товщина опорної пластини, gap — зазор між вушком і пластиною, L_втулки, [p] втулки, тип)
    J = [
        ('A — вісь стріли на колоні (Ø30, бобишка 140 мм, дві втулки по краях 2×45, бронза/к-т ГАЗ-53)', 30, joints['стріла:A'], 140, plate_clevis, 1, 90, 40.0, 'бронза 2×45'),
        ('B — стріла–рукоять (Ø30, пакет рукояті 60+2×8=76, шайби 2×2, вилка стріли 2×12)', 30, joints['рукоять:B'], tube_w_stick + 16, plate_clevis, 2, tube_w_stick + 16, P_BEAR_STEEL, 'сталь/сталь'),
        ('E — вісь ковша (Ø30; бобишка у рукояті 80, вуха ковша 12 + зовнішні бобишки 10; палець зафіксований у вухах)', 30, joints['рукоять:E'], bs, plate_clevis, 1, bs, P_BEAR_STEEL, 'сталь/сталь'),
        ('E — вісь ковша, варіант Ø25 (латунні втулки Газель)', 25, joints['рукоять:E'], bs, plate_boss, 1, 80, 40.0, 'латунь'),
        ('C/D — вушка циліндра стріли ШС30 (вилка 2×12, вушко 28)', 30, joints['циліндр:boom'], 28, plate_clevis, 1, 22, 999, 'ШС30 (C0=310 кН)'),
        ('F/H — бази циліндрів рукояті/ковша ШС25 (вилка 2×12, вушко 25)', 25, joints['циліндр:stick'], 25, plate_clevis, 1, 20, 999, 'ШС25 (C0=240 кН)'),
        ('G — шток цил. рукояті у п\'яті (вушко 25 між щоками 60, приварені розпірні втулки 16.5 + щока 8)', 25, joints['рукоять:G'], 25, 24.5, 1, 20, 999, 'ШС25'),
        ('J — шток цил. ковша / коромисло / тяга (Ø25; приварені бобишки коромисла впритул до вушка)', 25, max(joints['циліндр:bucket'], joints['циліндр:link']), 25, 37.5, 1, 20, 999, 'ШС25 + бобишки'),
        ('R — вісь коромисла (Ø30, бобишка у вухах рукояті, бронзові втулки 2×35)', 30, joints['рукоять:R'], bs, plate_boss, 1, 70, 40.0, 'бронза 2×35'),
        ('Q — тяга–ківш (Ø25; тяги 10 + бобишки 25 впритул до вух ковша 12, між вухами приварена розпірна втулка)', 25, joints['циліндр:link'], 0, plate_clevis, 1, 70, P_BEAR_STEEL, 'сталь/сталь, 2×35'),
    ]
    p("| Шарнір | d | F, кН | M згину, кН·мм | σ згину, МПа | SF шкворінь 45Х (fy≈600) | SF 40Х (785) | τ зрізу, МПа | p втулки, МПа ([p]) | p вилка/пластина, МПа (≤1.5·fy=%d) |" % (1.5 * fy_pl))
    p("|---|---|---|---|---|---|---|---|---|---|")
    for (name, d, F, b, a, gap, Lb, pall, typ) in J:
        Fn = F * 1000
        M = Fn * (b + 4 * gap + 2 * a) / 8
        if 'дві втулки по краях' in name:       # навантаження передається двома втулками біля опор: M = F/2·(a/2 + зазор + Lвт/2)
            M = Fn / 2 * (a / 2 + gap + (Lb / 2) / 2)
        if name.startswith('J —'):               # J: циліндр по центру (F_cyl, проліт вушко+бобишки) АБО передача тяга→коромисло між сусідніми пластинами
            Fc = joints['циліндр:bucket'] * 1000; Fl = joints['циліндр:link'] * 1000
            M = max(Fc * (b + 4 * gap + 2 * a) / 8, Fl / 2 * 11.0); Fn = max(Fc, Fl)
        if name.startswith('Q —'):               # Q: сила переходить з пластини тяги (10) на сусіднє вухо (12) через зазор 1 мм
            M = Fn / 2 * (5 + gap + a / 2)
        W = math.pi * d ** 3 / 32
        sig = M / W; tau = Fn / 2 / (math.pi * d * d / 4)
        pb = Fn / (d * Lb); pf = Fn / 2 / (d * a)
        flag = '' if pb <= pall else ' ⚠'
        p(f"| {name} | {d} | {F:.1f} | {M/1e3:.0f} | {sig:.0f} | {fy_pin/sig:.2f} | {fy_alt/sig:.2f} | {tau:.0f} | {pb:.0f} ({pall if pall < 999 else '—'}){flag} | {pf:.0f} |")
    p()
    p("Формула згину пальця: M = F·(b + 4·зазор + 2·a)/8 (вільне обпирання на центри пластин); зріз двозрізний; тиск у втулці p = F/(d·L).")
    p("Сферичні шарніри ШС перевіряються за статичною вантажопідйомністю C0 (ГОСТ 3635-78): ШС25 — 240 кН, ШС30 — 310 кН → запас > 4.")

def weld_table(joints, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    tw = 150.0  # МПа — допустиме для кутового шва Э50А/Св-08Г2С на Ст3 (Rwz = 166 по межі сплавлення, з m=0.9)
    W = [
        ('Вилка D (2 пласт. 12 мм → сідло 10 мм + стінки труби)', joints['циліндр:boom'], 6, 2 * 2 * 210),
        ('Сідло D → стінки труби (бокові стінки 2×(260 мм) двобічно)', joints['циліндр:boom'], 5, 4 * 250),
        ('Вежа F циліндра рукояті (2 пласт. 12 × основа 138 на верхній накладці, двобічно; вісь на 90 мм над швом → момент)', joints['циліндр:stick'], 6, 2 * 2 * 138, 90),
        ('Вилка H циліндра ковша (2 пласт. 12 × основа 106 на сідлі, двобічно; вісь на 60 мм над швом → момент)', joints['циліндр:bucket'], 6, 2 * 2 * 106, 60),
        ('Щоки п\'яти рукояті → труба (2 щоки × 2 кромки × 480)', joints['рукоять:G'] + joints['рукоять:B'], 6, 4 * 470),
        ('Вилка B стріли (2 пласт. 12 × периметр ~600)', joints['рукоять:B'], 6, 2 * 590),
        ('Накладки A (2 кільця Ø130 навколо втулки 66 + зовнішній контур)', joints['стріла:A'], 6, 2 * (math.pi * 66 + math.pi * 130) * 0.8),
        ('Втулка E крізь трубу (шов по колу Ø66 з двох боків + накладки)', joints['рукоять:E'], 5, 2 * math.pi * 66 + 2 * math.pi * 100),
    ]
    p("| Вузол | F, кН | катет k, мм | наявна довжина швів, мм | потрібна L при [τ]=150 МПа, мм | коеф. використання |")
    p("|---|---|---|---|---|---|")
    for row in W:
        name, F, k, L = row[:4]; ecc = row[4] if len(row) > 4 else 0
        Lreq = weld_len_required(F, k, tw)
        util = Lreq / L
        if ecc:                                   # 4 шви довжиною L/4: зріз + згин від ексцентриситету осі над швом
            a = 0.7 * k; l1 = L / 4
            util = math.hypot(F * 1000 / (a * L), F * 1000 * ecc / (4 * a * l1 ** 2 / 6)) / tw
        flag = '' if util <= 1.0 else ' ⚠'
        p(f"| {name} | {F:.1f} | {k} | {L:.0f} | {Lreq:.0f} | {util:.2f}{flag} |")
    p()
    p("Шви: кутові двобічні, катет 5–6 мм (труба 5 мм: k ≤ 1.2·t = 6), електроди Э50А (УОНИ-13/55) або дріт Св-08Г2С; "
      "розрахункова довжина lw = L − 10 мм на кожен шов; не варити на радіусах кутів труби; кінці накладок — плавний перехід, шви навколо.")

def report(g, boom_tube, stick_tube, plates, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    fy_t = MAT[TUBE_MAT]['fy']; fy_p = MAT[PLATE_MAT]['fy']; fy_pin = MAT[PIN_MAT]['fy']
    p("# Розрахунок міцності стріли та рукояті")
    p()
    p(f"Труби: {TUBE_MAT} (fy={fy_t} МПа). Пластини/накладки: {PLATE_MAT} (fy={fy_p} МПа). Пальці: {PIN_MAT} (fy={fy_pin} МПа).")
    p(f"Запаси по текучості: робота 160 бар ×{DYN} (динаміка) → SF≥{SF_NOM}; 200 бар → SF≥{SF_PEAK}; 250 бар (замкнений циліндр) → SF≥{SF_LOCK}.")
    p()
    cases = {
        f'160 бар ×{DYN}': (K.P_NOM * DYN, SF_NOM),
        '200 бар': (K.P_MAX, SF_PEAK),
        '250 бар (замк.)': (P_LOCK, SF_LOCK),
    }
    # --- максимальні сили на зубі і в циліндрах
    p("## Граничні зусилля на зубі ковша (за випадками, 160 бар без динаміки)")
    res160 = run_cases(g, K.P_NOM)
    p("| Випадок | кількість положень | F_зуб макс, кН | F_зуб мін, кН |")
    p("|---|---|---|---|")
    for name in dict.fromkeys(r['name'] for r in res160):
        rr = [r['Ftip'] for r in res160 if r['name'] == name]
        p(f"| {name} | {len(rr)} | {max(rr):.1f} | {min(rr):.1f} |")
    p()
    # --- станції
    L1, L2, Ls = g['L1'], g['L2'], g['Ls']
    boom_st = [('A (вісь)', 0), ('D (кронштейн цил. стріли)', g['sD']), ('K (перелом)', L1), ('F (база цил. рукояті)', L1 + L2 - g['sF']),
               ('середина 2-го сегм.', L1 + L2 / 2), ('B (вісь рукояті)', L1 + L2)]
    stick_st = [('B+ (корінь: момент циліндра рукояті)', 30), ('кінець щік (+400)', 430), ('H (база цил. ковша)', g['sH']), ('середина', Ls / 2), ('R (коромисло)', Ls - g['rx']), ('E (вісь ковша)', Ls)]
    bt = rhs_props(*boom_tube); st = rhs_props(*stick_tube)
    p(f"## Перерізи")
    p(f"- Стріла: труба {boom_tube[0]}×{boom_tube[1]}×{boom_tube[2]}: A={bt['A']:.0f} мм², I={bt['I']/1e4:.0f} см⁴, W={bt['W']/1e3:.1f} см³ (слабка вісь W={bt['W_w']/1e3:.1f} см³), {bt['mass']:.1f} кг/м")
    p(f"- Рукоять: труба {stick_tube[0]}×{stick_tube[1]}×{stick_tube[2]}: A={st['A']:.0f} мм², I={st['I']/1e4:.0f} см⁴, W={st['W']/1e3:.1f} см³ (слабка вісь W={st['W_w']/1e3:.1f} см³), {st['mass']:.1f} кг/м")
    for name, (tp, hp, n, span) in plates.items():
        p(f"- Підсилення «{name}»: {n} пласт. {tp}×{hp} мм, зона {span}")
    p()
    worst = {}
    for cname, (pm, sf) in cases.items():
        res = run_cases(g, pm)
        p(f"## Випадок тиску: {cname} (допустиме σ = fy/{sf}: труба {fy_t/sf:.0f} МПа, пластини {fy_p/sf:.0f} МПа)")
        for member, tube, props, stations, plate_key in (('Стріла', boom_tube, bt, boom_st, 'boom'), ('Рукоять', stick_tube, st, stick_st, 'stick')):
            env, total = max_internal(res, g, member.lower() if member == 'Стріла' else 'stick')
            env, total = max_internal(res, g, 'boom' if member == 'Стріла' else 'stick')
            p(f"### {member}")
            p("| Станція | s, мм | M макс, кН·м | N, кН | V, кН | σ труба, МПа | σ з накладками, МПа | SF (з накл.) | критичний випадок |")
            p("|---|---|---|---|---|---|---|---|---|")
            for (label, s, M, N, V, r) in fmt_env(env, total, stations):
                sig_t = M * 1e6 / props['W'] + N * 1e3 / props['A']
                # накладки в зоні?
                comp = props; has = False
                for pname, (tp, hp, n, span) in plates.items():
                    if pname.startswith(plate_key) and span[0] <= s <= span[1]:
                        comp = section_with_plates(tube, [(tp, hp, n)]); has = True
                sig_c = M * 1e6 / comp['W'] + N * 1e3 / comp['A']
                sf_c = (fy_p if has else fy_t) / sig_c if sig_c > 0 else 99
                crit = f"{r['name']} θ={r['th']:.0f}° ψ={r['psi']:.0f}° ω={r['om']:.0f}° F={r['Ftip']:.1f} кН" if r else '—'
                flag = '' if sf_c >= sf else ' ⚠'
                p(f"| {label} | {s:.0f} | {M:.2f} | {N:.1f} | {V:.1f} | {sig_t:.0f} | {sig_c:.0f}{'*' if has else ''} | {sf_c:.2f}{flag} | {crit} |")
            worst.setdefault(member, []).append(max(e[1] for e in env) / 1e6)
        # --- шарніри: максимальні сили
        p("### Максимальні сили у шарнірах, кН")
        joints = {}
        for r in res:
            s = r['sol']
            for k, v in s['boom'].items(): joints[f'стріла:{k}'] = max(joints.get(f'стріла:{k}', 0), norm(v))
            for k, v in s['stick'].items(): joints[f'рукоять:{k}'] = max(joints.get(f'рукоять:{k}', 0), norm(v))
            for k, v in s['cyl'].items(): joints[f'циліндр:{k}'] = max(joints.get(f'циліндр:{k}', 0), abs(v))
        p("| " + " | ".join(joints.keys()) + " |")
        p("|" + "---|" * len(joints))
        p("| " + " | ".join(f"{v:.1f}" for v in joints.values()) + " |")
        p()
        worst.setdefault('joints', []).append(joints)
    # --- бокове навантаження (слабка вісь): 0.15·F_зуб на зубі → згин стріли/рукояті у горизонтальній площині + кручення
    p("## Бокове навантаження (оцінка: 0.15 × макс. сила на зубі при 200 бар, плече = виліт від перерізу)")
    res200 = run_cases(g, K.P_MAX); Fmax = max(r['Ftip'] for r in res200)
    Flat = 0.15 * Fmax
    reach_B = g['Ls'] + g['tip']                      # від осі B до зуба (рукоять розкрита)
    reach_D = reach_B + (g['L1'] + g['L2'] - g['sD'])  # від D до зуба уздовж осі
    M_lat_stick = Flat * reach_B / 1e3; M_lat_boom = Flat * reach_D / 1e3
    p(f"- F_бок = {Flat:.1f} кН (F_зуб макс = {Fmax:.1f} кН). Рукоять біля B: M_бок = {M_lat_stick:.1f} кН·м → σ = {M_lat_stick*1e6/st['W_w']:.0f} МПа (труба, слабка вісь W={st['W_w']/1e3:.1f} см³; щоки не рахуємо).")
    p(f"- Стріла біля D: M_бок = {M_lat_boom:.1f} кН·м → σ = {M_lat_boom*1e6/bt['W_w']:.0f} МПа (W_слабка={bt['W_w']/1e3:.1f} см³). Кручення від F_бок·(відстань до осі ≈ 0.3 м) ≈ {Flat*0.3:.1f} кН·м → τ ≈ {Flat*0.3*1e6/(2*(bt['A']/1.0)*0.5*0.9*boom_tube[0]*0.5):.0f} МПа (оцінка Бредта, мала).")
    p()
    p("## Шарніри: пальці, втулки, вилки (сили випадку 250 бар — верхня межа)")
    joint_table(g, worst['joints'][-1], boom_tube[1], stick_tube[1], out=out)
    p()
    p("## Зварні шви кронштейнів (сили випадку 250 бар)")
    weld_table(worst['joints'][-1], out=out)
    return worst

def sections_table(g, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    p("| Труба h×w×t | A, мм² | I, см⁴ | W, см³ | W слабка, см³ | кг/м |")
    p("|---|---|---|---|---|---|")
    for h, w, t in TUBES:
        pr = rhs_props(h, w, t)
        p(f"| {h}×{w}×{t} | {pr['A']:.0f} | {pr['I']/1e4:.0f} | {pr['W']/1e3:.1f} | {pr['W_w']/1e3:.1f} | {pr['mass']:.1f} |")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sections', action='store_true')
    ap.add_argument('--boom', default='120x80x5'); ap.add_argument('--stick', default='100x60x5')
    ap.add_argument('--fstab', type=float, default=None, help='межа стійкості машини: макс. вертикальна сила на зубі, кН')
    a = ap.parse_args()
    g = dict(K.GEOM)
    if a.sections: sections_table(g); sys.exit()
    if a.fstab is not None: F_STAB = a.fstab
    boom_tube = tuple(int(x) for x in a.boom.split('x')); stick_tube = tuple(int(x) for x in a.stick.split('x'))
    # вильоти кронштейнів залежать від висоти труби — так само, як у SCAD (boom_cyl_bracket=60, stick_cyl_bracket=98, ...)
    g['eD'] = boom_tube[0] / 2 + 60; g['eF'] = boom_tube[0] / 2 + 98
    g['eH'] = stick_tube[0] / 2 + 70; g['ry'] = stick_tube[0] / 2 + 25
    # зони накладок — як у SCAD (boom_bend_gussets: back/fwd від K; stick_cheeks: 0..420; stick_tip_bosses)
    back = max(250, g['L1'] - g['sD'] + 180, g['L1'] - (g['L1'] + g['L2'] - g['sF']) + 160)
    fwd = max(250, g['sD'] - g['L1'] + 180)
    plates = {
        'boom: щоки перелому (охоплюють F, K, D)': (8, boom_tube[0] + 20, 2, (g['L1'] - back, g['L1'] + fwd)),
        'stick: щоки п\'яти 8 мм, корінь (з рукою п\'яти, h+60)': (8, stick_tube[0] + 60, 2, (0, 150)),
        'stick: щоки п\'яти 8 мм (h+40, виступають на 20 мм за полиці)': (8, stick_tube[0] + 40, 2, (150, 420)),
        'stick: накладки кінця': (10, stick_tube[0], 2, (g['Ls'] - g['rx'] - 120, g['Ls'])),
    }
    report(g, boom_tube, stick_tube, plates)
