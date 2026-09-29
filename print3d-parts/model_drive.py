#!/usr/bin/env python3
"""Привід циліндрів друкованої моделі гвинтом M5×0.8: оберти гайки й моторедуктор.

Модель рухається «як справжня»: кожен циліндр проходить свій хід за той самий час,
що й циліндр машини від насоса. Звідси швидкість штока моделі = швидкість машини / SC,
а оберти гайки = швидкість / крок. Далі — найгірша за всіма позами сила на кожному
циліндрі від ваги самої моделі (маса — з РЕАЛЬНИХ STL набору) і момент та потужність,
за якими підбирати моторедуктор.

Нічого не вписується руками: циліндри й геометрія — з `tools/kinematics.py` (звіряються
з моделлю), маса — з `stl/`, масштаб — з `parts.scad`, місткість ковша — з
`tools/bucket.py`. Результат замінює блок між маркерами в `README.md` набору.

usage: model_drive.py            # переписати блок у README.md
       model_drive.py --print    # лише надрукувати, README не чіпати
"""
import glob
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, HERE)

try:
    import shapely  # noqa: F401  потрібен bucket.py (місткість і центр ваги ковша)
except ImportError:
    venv = os.path.join(ROOT, 'tools', '.venv', 'bin', 'python')
    if os.path.exists(venv) and os.path.realpath(sys.executable) != os.path.realpath(venv):
        os.execv(venv, [venv] + sys.argv)
    sys.exit('model_drive.py: потрібен shapely (tools/.venv)')

import bucket                      # noqa: E402
import kinematics as K             # noqa: E402
from make_bom import PLA           # noqa: E402  г/см³ — та сама густина, що в BOM

# --- Припущення (змінюються тут, решта рахується) -------------------------------------
Q_LPM = 11.0        # л/хв — насос НШ-10 через редукцію 3 (TECHNICAL, розділ 5); весь потік в один циліндр
PITCH = 0.8         # мм — M5 зі стандартним кроком
D2 = 4.480          # мм — середній діаметр різьби M5×0.8 (ISO 724)
MU_THREAD = 0.20    # тертя гайки по гвинту: сталь/латунь з мастилом ≈ 0.15, друкована гайка ≈ 0.2–0.25
MU_FACE = 0.20      # тертя торця гайки об опору (без упорного підшипника)
R_FACE = 3.25       # мм — середній радіус торця гайки M5 (S8)
FILL = 1.0          # частка суцільного PLA: тонкі стінки набору друкуються майже суцільними — беремо з запасом
DRIVE_G = 15.0      # г — моторедуктор N20 із тримачем і гайкою на кожному циліндрі (сидить біля бази)
SAND = 1.6          # г/см³ — сухий пісок у ковші з «шапкою» (ISO 7451)
MARGIN = 2.0        # запас на тертя друкованих шарнірів, перекіс, просідання напруги
GRID = 21           # точок на хід кожного циліндра при пошуку найгіршої пози
g0 = 9.81e-3        # Н на грам

# Моторедуктори 12GAN20 (N20) при 12 В — рядки таблиці з даташиту постачальника:
# (редуктор X у назві 12GAN20-X, холостий хід: об/хв, А; номінал: об/хв, А, кг·см; зупинка: кг·см, А)
N20_V = 12.0
N20 = [
    (10, 4000, .16, 3000, .34, .04, .60, .60), (10, 2000, .02, 1600, .06, .12, 1.0, .35),
    (20, 1000, .19, 800, .28, .30, 2.4, .60), (30, 800, .11, 700, .16, .35, 3.0, .40),
    (30, 600, .03, 500, .07, .40, 3.2, .20), (50, 400, .11, 340, .17, .50, 4.0, .30),
    (100, 300, .05, 240, .09, .60, 4.0, .30), (200, 200, .02, 160, .04, 1.0, 7.0, 1.0),
    (298, 130, .11, 100, .18, 1.5, 9.0, 1.0), (298, 100, .04, 80, .07, 2.0, 16.0, 1.0),
    (298, 60, .04, 40, .06, 2.0, 16.0, 1.0),
]
N20_PICK = [(10, 2000), (20, 1000), (30, 800), (50, 400)]   # що порівнювати по циліндрах: повільніші — у 4+ рази за машину
ETA_GEAR = {10: .70, 20: .65, 30: .60, 50: .60, 100: .55, 200: .50, 298: .45}   # ККД редуктора, оцінка
OVERLOAD = 0.5      # частка моменту зупинки, вище якої мотор гріється (там же його найбільша потужність)

BEGIN, END = '<!-- model_drive:begin -->', '<!-- model_drive:end -->'
NAMES = dict(boom='Стріла', stick='Рукоять', bucket='Ківш')

# Де сидить кожна деталь набору: точка кінематики (назва або середина двох), точка на осі
# рукояті ('s', мм від B) чи в системі ковша ('bk', x, y). None — нерухома (колона).
# Нова деталь у parts.tsv без рядка тут зупиняє скрипт: вага має кудись лягти.
WHERE = {
    'tube_boom_seg1': ('A', 'K'), 'tube_boom_seg2': ('K', 'B'), 'tube_stick': ('s', K.GEOM['Ls'] / 2),
    'gusset': 'K', 'cover': 'K', 'D_saddle': 'K', 'D_clevis': 'D', 'F_tower': 'F', 'A_doubler': 'A', 'B_fork': 'B',
    'cheek': ('s', 150), 'heel_rib': 'G', 'H_clevis': 'H', 'H_saddle': 'H', 'tip_plate': 'E',
    'rocker_plate': ('R', 'J'), 'link_plate': ('J', 'Q'),
    'bk_shell': 'bk', 'bk_side_L': 'bk', 'bk_side_R': 'bk', 'bk_top': 'bk', 'bk_lip_rib': 'bk', 'bk_ear': 'bk',
    'bk_wear': 'bk', 'bk_edge': 'T', 'bk_tooth': 'T',
    'post_plate': None,
    'cyl_boom_body': ('C', 'D'), 'cyl_boom_rod': ('C', 'D'), 'cyl_stick_body': ('F', 'G'), 'cyl_stick_rod': ('F', 'G'),
    'cyl_bucket_body': ('H', 'J'), 'cyl_bucket_rod': ('H', 'J'),
    'A_bushing': 'A', 'B_bushing': 'B', 'E_bushing': 'E', 'R_bushing': 'R', 'G_boss': 'G', 'J_boss': 'J',
    'link_boss': ('J', 'Q'), 'bk_boss_E': 'E', 'bk_spacer_Q': 'Q', 'washer_B': 'B',
    'pin_A': None, 'pin_C': None, 'pin_B': 'B', 'pin_D': 'D', 'pin_E': 'E', 'pin_F': 'F', 'pin_G': 'G',
    'pin_H': 'H', 'pin_J': 'J', 'pin_Q': 'Q', 'pin_R': 'R',
}


def stl_volume(path):
    """Об'єм бінарного STL, см³ (набір пише лише binstl)."""
    import struct
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0]
    v = 0.0
    for i in range(n):
        a0, a1, a2, b0, b1, b2, c0, c1, c2 = struct.unpack('<9f', data[96 + i * 50:132 + i * 50])
        v += a0 * (b1 * c2 - b2 * c1) - a1 * (b0 * c2 - b2 * c0) + a2 * (b0 * c1 - b1 * c0)
    return abs(v) / 6000.0


def scale():
    m = re.search(r'^SC\s*=\s*(\d+)\s*;', open(os.path.join(HERE, 'parts.scad'), encoding='utf-8').read(), re.M)
    return int(m.group(1))


def check_cylinders():
    """Циліндри kinematics.py мають збігатися з моделлю — інакше рахуємо чужу машину."""
    src = open(os.path.join(ROOT, 'scad', 'excavator_boom.scad'), encoding='utf-8').read()
    bad = []
    for k, c in K.CYL.items():
        for f in ('bore', 'rod', 'stroke'):
            m = re.search(rf'^{k}_cyl_{f}\s*=\s*([\d.]+)\s*;', src, re.M)
            if not m or float(m.group(1)) != c[f]:
                bad.append(f'{k}_cyl_{f}: модель {m.group(1) if m else "?"}, kinematics.py {c[f]}')
    if bad:
        sys.exit('model_drive.py: циліндри розійшлися з моделлю:\n  ' + '\n  '.join(bad))


def masses():
    """[(ключ, маса г, де)] з STL набору: об'єм одного файлу × к-сть × PLA × FILL."""
    out, missing = [], []
    for line in open(os.path.join(HERE, 'parts.tsv'), encoding='utf-8'):
        if not line.strip() or line.startswith('#'):
            continue
        r = line.rstrip('\n').split('\t')
        key, file, qty = r[0], r[4], int(r[5])
        if key not in WHERE:
            missing.append(key)
            continue
        hits = glob.glob(os.path.join(HERE, 'stl', '**', f'{file}_x{qty}.stl'), recursive=True)
        if not hits:
            sys.exit(f'model_drive.py: немає STL для {key} ({file}_x{qty}.stl) — спершу make.sh')
        out.append((key, stl_volume(hits[0]) * qty * PLA * FILL, WHERE[key]))
    if missing:
        sys.exit('model_drive.py: деталі без місця у WHERE: ' + ', '.join(missing))
    return out


def pose(g, th, psi, om, bk_pts):
    """Усі точки кінематики в позі; None — поза недосяжна."""
    bp = K.boom_points(g, th)
    sp = K.stick_points(g, bp, psi)
    fw = K.bucket_points_fwd(g, sp, om)
    if fw is None:
        return None
    axis = sp['a_s'] - om
    p = {k: bp[k] for k in 'ABCDFK'}
    p.update({k: sp[k] for k in 'EGHR'})
    p.update(J=fw['J'], Q=fw['Q'], T=K.add(sp['E'], K.rot((g['tip'], 0), axis)), L_bk=fw['L'],
             L_bm=K.dist(bp['C'], bp['D']), L_st=K.dist(bp['F'], sp['G']))
    for name, (x, y) in bk_pts.items():
        p[name] = K.add(sp['E'], K.rot((x, y), axis))
    p['_B'], p['_us'] = bp['B'], sp['us']
    return p


def locate(p, where):
    if isinstance(where, str):
        return p[where]
    if where[0] == 's':
        return K.add(p['_B'], K.mul(p['_us'], where[1]))
    return K.mul(K.add(p[where[0]], p[where[1]]), 0.5)


def height(g, th, psi, om, load, bk_pts):
    """(Σ маса·висота, г·мм у геометрії машини; довжини трьох циліндрів)."""
    p = pose(g, th, psi, om, bk_pts)
    if p is None:
        return None
    return sum(m * locate(p, w)[1] for m, w in load), (p['L_bm'], p['L_st'], p['L_bk'])


def forces(g, load, bk_pts):
    """Найбільша сила штовхання й тягнення на кожному циліндрі за всіма позами, Н.

    Віртуальна робота: F = g·dΣ(m·y)/dL при нерухомих двох інших циліндрах. Відношення
    dy/dL безрозмірне, тож геометрію машини не треба масштабувати — лише маса модельна.
    Додатна F — вага стискає циліндр (щоб тримати, його треба штовхати)."""
    th0, th1 = K.boom_range(g)
    ps0, ps1 = K.stick_range(g)
    _, om0, om1, _ = K.bucket_range(g)
    lin = lambda a, b: [a + (b - a) * i / (GRID - 1) for i in range(GRID)]
    h = 0.02
    F = {k: [0.0, 0.0] for k in K.CYL}          # [макс. штовхання, макс. тягнення]
    for th in lin(th0, th1):
        for psi in lin(ps0, ps1):
            for om in lin(om0, om1):
                base = height(g, th, psi, om, load, bk_pts)
                if base is None:
                    continue
                for i, (key, d) in enumerate((('boom', (h, 0, 0)), ('stick', (0, h, 0)), ('bucket', (0, 0, h)))):
                    nxt = height(g, th + d[0], psi + d[1], om + d[2], load, bk_pts)
                    if nxt is None:
                        continue
                    dL = nxt[1][i] - base[1][i]
                    if abs(dL) < 1e-9:
                        continue
                    f = g0 * (nxt[0] - base[0]) / dL
                    F[key][0] = max(F[key][0], f)
                    F[key][1] = max(F[key][1], -f)
    return F


def nut_torque(f, against, mu_face=MU_FACE):
    """Момент на гайці, Н·мм: різьба (проти вантажу чи з ним) + торець об опору."""
    lam = math.atan(PITCH / (math.pi * D2))
    phi = math.atan(MU_THREAD / math.cos(math.radians(30)))
    thread = f * D2 / 2 * (math.tan(lam + phi) if against else max(0.0, math.tan(phi - lam)))
    return thread + f * mu_face * R_FACE


def torques(F, mu_face=MU_FACE):
    """{(циліндр, 0 висування | 1 втягування): момент на гайці, Н·мм} — більший із «піднімає» і «гальмує»."""
    return {(k, s): max(nut_torque(F[k][s], True, mu_face), nut_torque(F[k][1 - s], False, mu_face))
            for k in K.CYL for s in (0, 1)}


def n20_stall(ratio, n0, i0, i_stall):
    """Момент зупинки на валу, Н·мм — зі струму, а не з даташиту.

    Сталий магнітний потік: Kt = Ke = U / ω₀ (через редуктор — уже на вихідному валу),
    тож T = η·U·(I_зуп − I_хх) / ω₀. Паспортні кг·см у 12GAN20 з цим не сходяться: за
    ними механічна потужність виходить більшою за електричну."""
    return ETA_GEAR[ratio] * N20_V * (i_stall - i0) / (n0 * 2 * math.pi / 60) * 1000


def n20_section(w, sc, q, F_empty, F_sand):
    """Розділ README: каталог 12GAN20 і що кожен варіант дасть на кожному циліндрі."""
    motors = {(r, n0): (r, n0, i0, n20_stall(r, n0, i0, ist), ds * 98.07, ist)
              for r, n0, i0, _, _, _, ds, ist in N20}           # 1 кг·см = 98.07 Н·мм
    name = lambda r, n0: f'12GAN20-{r}, {n0} об/хв'
    real = {k: (c['stroke'] / (q / c['A_push']), c['stroke'] / (q / c['A_pull'])) for k, c in K.CYL.items()}
    turns = {k: c['stroke'] / sc / PITCH for k, c in K.CYL.items()}

    def run(k, m, T):
        """(час висування, час втягування, частка моменту зупинки) при прямому приводі гайки."""
        _, n0, _, ts, _, _ = m
        load = max(T[k, 0], T[k, 1]) / ts
        t = [turns[k] / (n0 * (1 - T[k, s] / ts) / 60) if T[k, s] < ts else None for s in (0, 1)]
        return t[0], t[1], load

    w('### Моторедуктор N20 (12GAN20, 12 В)')
    w('')
    w('Число після дефіса в назві 12GAN20-**X** — передатне число редуктора: -50 = 50:1. Мотор у '
      'більшості 12-вольтових варіантів той самий (≈ 20 000 об/хв до редуктора), тож більше X — '
      'повільніший вал і більший момент. Паспортним '
      'моментам цієї серії вірити не можна: за ними механічна потужність виходить більшою за електричну '
      f'(ККД понад 100 %). Тому момент зупинки перераховано зі струму: T = η·U·(I_зуп − I_хх)/ω₀, ККД '
      f'редуктора — оцінка {min(ETA_GEAR.values()):.2f}–{max(ETA_GEAR.values()):.2f}. Найбільша '
      'потужність мотора — на половині моменту зупинки й половині обертів.')
    w('')
    w('| Мотор | Холостий хід, об/хв | Струм зупинки, А | Момент зупинки за даташитом, Н·мм | Момент зупинки зі струму, Н·мм | Найбільша потужність, Вт |')
    w('|---|---:|---:|---:|---:|---:|')
    for (r, n0), (_, _, _, ts, ds, ist) in motors.items():
        mark = ' ¹' if ist == 1.0 else ''
        w(f'| {name(r, n0)}{mark} | {n0} | {ist:.2f} | {ds:.0f} | {ts:.1f} | {ts / 1000 * n0 * 2 * math.pi / 60 / 4:.2f} |')
    if any(m[5] == 1.0 for m in motors.values()):
        w('')
        w('¹ Струм зупинки рівно 1.00 А в кількох рядках поспіль схожий на заглушку в даташиті — '
          'момент і потужність цих рядків, найімовірніше, завищені.')
    w('')
    w(f'Нижче — вал мотора прямо на гайці (1:1). Під навантаженням оберти падають лінійно: '
      f'n = n₀·(1 − T/T_зуп). У клітинці — час висування / втягування моделі і яку частку моменту зупинки '
      f'бере найважчий із двох рухів; ⚠ — понад {OVERLOAD * 100:.0f} %: мотор гріється, для постійної роботи '
      f'не годиться. Упорний підшипник F5-10M під гайкою прибирає тертя її торця.')
    picks = [motors[p] for p in N20_PICK]
    fit = {}
    for title, F in (('Порожня модель', F_empty), ('З повним ковшем піску', F_sand)):
        w('')
        w(f'**{title}:**')
        w('')
        w('| Циліндр | Машина: висування / втягування, с | ' + ' | '.join(name(m[0], m[1]) for m in picks) + ' |')
        w('|---|---:|' + '---:|' * len(picks))
        for bearing, mu in (('', MU_FACE), (', упорний підшипник', 0.0)):
            T = torques(F, mu)
            for k in K.CYL:
                cells = []
                for m in picks:
                    te, tr, ld = run(k, m, T)
                    ok = te is not None and tr is not None and ld <= OVERLOAD
                    fit[title, bearing, k, m[:2]] = (ok, te, tr)
                    cells.append('стоїть' if te is None or tr is None else
                                 f'{te:.0f} / {tr:.0f} с · {ld * 100:.0f} %' + ('' if ok else ' ⚠'))
                w(f'| {NAMES[k]}{bearing} | {real[k][0]:.1f} / {real[k][1]:.1f} | ' + ' | '.join(cells) + ' |')
    w('')
    # Висновок рахується з тих самих таблиць: при зміні маси чи тертя він зміниться сам.
    for bearing, label in (('', 'без підшипника'), (', упорний підшипник', 'з упорним підшипником')):
        one = [m for m in picks if all(fit['Порожня модель', bearing, k, m[:2]][0] for k in K.CYL)]
        if one:
            best = max(one, key=lambda m: m[1])
            slow = [fit['Порожня модель', bearing, k, best[:2]][1 + s] / real[k][s] for k in K.CYL for s in (0, 1)]
            txt = (f'один тип на всі три — {", ".join(name(m[0], m[1]) for m in one)}; найшвидший із них '
                   f'({name(best[0], best[1])}) повільніший за машину в {min(slow):.1f}–{max(slow):.1f} раза')
        else:
            txt = 'жоден варіант не тягне всі три циліндри без перегріву'
        each = []
        for k in K.CYL:
            ok = [m for m in picks if fit['Порожня модель', bearing, k, m[:2]][0]]
            each.append(f'{NAMES[k].lower()} — ' + (name(*max(ok, key=lambda m: m[1])[:2]) if ok else 'жоден'))
        w(f'- **Порожня модель, {label}:** {txt}. Найшвидший придатний окремо: {", ".join(each)}.')
    sand = [NAMES[k].lower() for k in K.CYL
            if not any(fit['З повним ковшем піску', ', упорний підшипник', k, m[:2]][0] for m in picks)]
    w('- **З піском:** ' + (f'{", ".join(sand)} — не тягне жоден N20 навіть з упорним підшипником; '
                            'тут потрібен мотор класу 370 або 25GA (важчий — зміни `DRIVE_G`).' if sand else
                            'N20 тягне всі три з упорним підшипником.'))
    w('')
    w('Це оцінка: перевір на своєму моторі — важок на важелі до вала або струм під навантаженням проти таблиці.')


def main():
    check_cylinders()
    sc = scale()
    g = K.GEOM
    q = Q_LPM * 1e6 / 60                                     # мм³/с
    parts = masses()

    b = bucket.BUCKET
    pr = bucket.profile(b, g)
    cap = bucket.capacity(b, g)
    sand_g = cap['heaped'] * 1000 / sc ** 3 * SAND           # л → см³ моделі → г
    bk_pts = {'bk': tuple(pr['side'].centroid.coords[0]), 'sand': tuple(pr['struck'].centroid.coords[0])}

    load = [(m, w) for _, m, w in parts if w is not None]
    load += [(DRIVE_G, 'F'), (DRIVE_G, 'H')]                 # привід циліндра стріли — на колоні
    F_empty = forces(g, load, bk_pts)
    F_sand = forces(g, load + [(sand_g, 'sand')], bk_pts)

    L = []
    w = L.append
    w(BEGIN)
    w('<!-- Згенеровано print3d-parts/model_drive.py (make.sh). Руками не правити: зміни припущення у скрипті. -->')
    w('')
    w('## Привід циліндрів гвинтом M5')
    w('')
    w(f'Якщо циліндр моделі — гвинт **M5×0.8** (шток) і гайка, яку крутить моторедуктор, то за один оберт '
      f'гайки шток проходить {PITCH} мм. Щоб модель рухалась **як машина**, кожен циліндр має пройти свій '
      f'хід за той самий час, що й справжній від насоса ({Q_LPM:g} л/хв, НШ-10 через редукцію 3 — '
      f'`TECHNICAL.md`, розділ 5). Тобто шток моделі в {sc} разів повільніший, а швидкість гайки '
      f'n = v / {PITCH}. Висування повільніше за втягування: при висуванні олія заповнює всю площу поршня, '
      f'а при втягуванні лише кільце навколо штока.')
    w('')
    w('| Циліндр | Рух | Шток машини, мм/с | Час ходу, с | Шток моделі, мм/с | Гайка M5×0.8, об/хв | Гайка M5×0.8, об/с | Обертів на хід |')
    w('|---|---|---:|---:|---:|---:|---:|---:|')
    speed = {}
    for k, c in K.CYL.items():
        for mv, area in (('висування', c['A_push']), ('втягування', c['A_pull'])):
            v = q / area
            n = v / sc / PITCH
            speed[k, mv] = n
            w(f'| {NAMES[k]} | {mv} | {v:.1f} | {c["stroke"] / v:.1f} | {v / sc:.1f} | {n * 60:.0f} | '
              f'{n:.1f} | {c["stroke"] / sc / PITCH:.0f} |')
    w('')
    w('Це найбільші швидкості: коли розподільник пускає весь потік в один циліндр. Якщо рухаються два '
      'одразу, потік ділиться, і в машини, і в моделі.')
    w('')
    w('### Маса рухомих частин')
    w('')
    groups = {}
    for key, m, where in parts:
        grp = ('Колона (нерухома)' if where is None else 'Ківш' if key.startswith('bk_') else
               'Гідроциліндри' if key.startswith('cyl_') else 'Пальці' if key.startswith('pin_') else
               'Важільна система' if key.startswith(('rocker', 'link')) else
               'Рукоять' if key in ('tube_stick', 'cheek', 'heel_rib', 'H_clevis', 'H_saddle', 'tip_plate') else
               'Втулки й бобишки' if key.endswith(('bushing', 'boss', 'boss_E', 'spacer_Q', 'washer_B')) else 'Стріла')
        groups[grp] = groups.get(grp, 0.0) + m
    w(f'Об\'єм — із самих STL набору, густина PLA {PLA} г/см³, заповнення {FILL * 100:.0f} % (стінки набору '
      f'тонкі й друкуються майже суцільними, тож це верхня межа). Пісок — повний ківш «з шапкою»: '
      f'{cap["heaped"]:.1f} л у машині = {cap["heaped"] * 1000 / sc ** 3:.0f} см³ у моделі.')
    w('')
    w('| Що | Маса, г |')
    w('|---|---:|')
    for grp in ('Стріла', 'Рукоять', 'Ківш', 'Важільна система', 'Гідроциліндри', 'Втулки й бобишки', 'Пальці'):
        w(f'| {grp} | {groups.get(grp, 0):.0f} |')
    w(f'| Моторедуктори на циліндрах рукояті й ковша (оцінка), 2 × {DRIVE_G:.0f} | {2 * DRIVE_G:.0f} |')
    w(f'| **Разом рухоме** | **{sum(m for m, _ in load):.0f}** |')
    w(f'| Пісок у ковші, ρ = {SAND} г/см³ | {sand_g:.0f} |')
    w(f'| {groups.get("Колона (нерухома)", 0):.0f} г колони й пальців A, C не рахуються: вони не рухаються | — |')
    w('')
    w('### Навантаження і моторедуктор')
    w('')
    w(f'Сила на кожному циліндрі — найгірша з {GRID}³ поз у межах ходів (віртуальна робота: скільки '
      f'грамів піднімається на мм ходу). Центри ваги деталей поставлено в їхні шарніри чи на середину '
      f'ланки, ковша й піску — у центр профілю з `tools/bucket.py`. Момент на гайці — різьба M5×0.8 '
      f'(тертя {MU_THREAD}) плюс торець гайки об опору (тертя {MU_FACE}). M5 самогальмівний: '
      f'опускати вантаж теж треба крутити, момент менший, але не нуль. Потужність — на гайці, при '
      f'обертах із таблиці вище. **Паспорт** — що має бути в моторедуктора: номінальний (не пусковий) '
      f'момент із запасом ×{MARGIN:g} на тертя друкованих шарнірів, перекіс і просідання напруги; '
      f'оберти під навантаженням не менші за потрібні (холостий хід ≈ на 20–25 % вищий).')
    w('')
    w('| Циліндр | Рух | Вага проти руху, Н (порожній / з піском) | Момент на гайці, Н·мм (порожній / з піском) | Потужність на гайці, Вт (порожній / з піском) | Паспорт: момент ≥, г·см (порожній / з піском) | Паспорт: оберти ≥, об/хв |')
    w('|---|---|---:|---:|---:|---:|---:|')
    T_empty, T_sand = torques(F_empty), torques(F_sand)
    for k in K.CYL:
        for mv, sign in (('висування', 0), ('втягування', 1)):
            n = speed[k, mv]
            tq = [T_empty[k, sign], T_sand[k, sign]]
            fs = [F_empty[k][sign], F_sand[k][sign]]        # висування: проти руху — штовхання
            pw = [t / 1000 * 2 * math.pi * n for t in tq]
            gcm = [t * MARGIN * 10.197 for t in tq]           # 1 Н·мм = 10.197 г·см
            w(f'| {NAMES[k]} | {mv} | {fs[0]:.1f} / {fs[1]:.1f} | {tq[0]:.1f} / {tq[1]:.1f} | '
              f'{pw[0]:.1f} / {pw[1]:.1f} | {gcm[0]:.0f} / {gcm[1]:.0f} | {n * 60:.0f} |')
    w('')
    w('«Вага проти руху» — найбільша сила, яку гайка долає, піднімаючи; у позах, де вага сама тягне '
      'в бік руху, гайка її гальмує, і момент рахується й для цього випадку — у таблиці більший із двох. '
      'Найважче стрілі: вона тримає все. Пісок важить більше за саму модель: якщо копати не треба, '
      f'підбирай за «порожнім». Маса приводу взята під N20 ({DRIVE_G:g} г); важчий мотор (25GA ≈ 70–100 г) '
      'сам додає навантаження стрілі — зміни `DRIVE_G` і перерахуй. '
      'Упорний підшипник під гайкою (F5-10M) прибирає тертя торця — момент падає майже вдвічі. '
      f'Припущення (витрата, тертя, заповнення, маса приводу, запас) — сталі на початку '
      f'`print3d-parts/model_drive.py`; після зміни — `python3 print3d-parts/model_drive.py`.')
    w('')
    n20_section(w, sc, q, F_empty, F_sand)
    w(END)
    block = '\n'.join(L)

    if '--print' in sys.argv:
        print(block)
        return
    path = os.path.join(HERE, 'README.md')
    txt = open(path, encoding='utf-8').read()
    if BEGIN in txt:
        txt = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), lambda _: block, txt, flags=re.S)
    else:
        txt = txt.replace('\n## Важливе, що цей набір НЕ дає', '\n' + block + '\n\n## Важливе, що цей набір НЕ дає', 1)
        if BEGIN not in txt:
            sys.exit('model_drive.py: не знайшов, куди вставити блок у README.md')
    open(path, 'w', encoding='utf-8').write(txt)
    print(f'  print3d-parts/README.md — привід M5 (стріла тримає до {F_sand["boom"][0]:.1f} Н з піском)')


if __name__ == '__main__':
    main()
