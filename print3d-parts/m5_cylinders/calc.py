#!/usr/bin/env python3
"""Циліндри моделі 1:5 на шпильці M5: довжини, маса, сили, мотор і шестерні → CALC.md.

Схема — у README.md поруч: шпилька M5×0.8 — шток, гайка крутиться в шестерні в голові
циліндра, поруч паралельно N20.

Скрипт нічого не вибирає сам: мотор, шестерні й розміри гільзи — сталі `m5_cyl.scad`
(вибір користувача), звідти ж їх і читає. Він перевіряє, що вибране влазить і тягне, і
показує, що дали б інші N20 з найкращою для кожного парою шестерень.

  1. ланцюжок довжин: зведена довжина й хід — як у моделі (1:SC), голова вміщується;
  2. сили — з print3d-parts/model_drive.py (віртуальна робота за всіма позами) з масою
     набору, де циліндри набору замінено цими: друковане — з їхніх STL, плюс сталь
     шпильки, гайка, підшипник і мотор, кожне там, де воно справді сидить;
  3. час ходу й навантаження мотора — порожня модель і з повним ковшем піску.

usage: calc.py --kit-stl ТЕКА --own-stl ТЕКА --out CALC.md    # так кличе make.sh
       calc.py --print                                        # теки — за замовчуванням, лише надрукувати
"""
import ast
import glob
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'print3d-parts'))
import model_drive as md          # noqa: E402  (сам перезапускається через tools/.venv)
import bucket                     # noqa: E402
import kinematics as K            # noqa: E402
from author import md_footer      # noqa: E402


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def _first(*dirs):
    """Перша тека, де справді лежать STL (build/ щойно зібраного або latest/)."""
    return next((d for d in dirs if glob.glob(os.path.join(d, '**', '*.stl'), recursive=True)), dirs[0])


KIT_STL = _arg('--kit-stl') or _first(os.path.join(ROOT, 'build', 'print3d', 'stl'), os.path.join(ROOT, 'latest', 'print3d', 'stl'))
OWN_STL = _arg('--own-stl') or _first(os.path.join(ROOT, 'build', 'm5_cylinders', 'stl'),
                                      os.path.join(ROOT, 'latest', 'print3d', 'm5_cylinders', 'stl'))
OUT = None if '--print' in sys.argv else _arg('--out')
md.STL = KIT_STL


def scad_consts():
    """Сталі з m5_cyl.scad — те саме джерело, з якого будуються деталі."""
    src = open(os.path.join(HERE, 'm5_cyl.scad'), encoding='utf-8').read()

    def get(name):
        m = re.search(rf'(?<![\w$]){name}\s*=\s*([^;]+);', src)
        if not m:
            sys.exit(f'calc.py: у m5_cyl.scad немає сталої {name}')
        return ast.literal_eval(m.group(1).strip())
    names = ('SC MOTOR GEAR_M GEAR_ALPHA Z_NUT Z_PIN TUBE_ID PUCK REAR_WALL EYE_LEN FRONT_GAP '
             'LIP GAP_SH GEAR_B GAP_F FWALL BRG N20_T').split()
    c = {n: get(n) for n in names}
    c['HEAD_CORE'] = c['LIP'] + c['BRG'][2] + c['GAP_SH'] + c['GEAR_B'] + c['GAP_F'] + c['FWALL']
    return c


C = scad_consts()
Z_PIN_MIN, Z_PIN_MAX = 13, 34   # що перебирати для порівняння; < 17 — з корекцією
A_MAX = 18.0        # мм — далі мотор уже стирчить більше, ніж сама голова
MOTOR_GAP = 0.6     # мм — корпус мотора ↔ гільза
ETA_SPUR = 0.90     # ККД друкованої прямозубої пари з мастилом
SPEED_TOL = 1.10    # пара на 10 % повільніша за найшвидшу, але компактніша — краща
KEYS = ('boom', 'stick', 'bucket')

# маса покупного, г
STEEL_G_PER_MM = 0.154   # шпилька M5 (DIN 976), 1 м ≈ 154 г
N20_G = 10.0             # 12GAN20 з редуктором
BUY_G = 1.1 + 0.6 + 0.3  # гайка M5, MR128ZZ, магніти й датчики


def inv(a):
    return math.tan(a) - a


def center_distance(z1, x1, z2, x2):
    """Робоча міжосьова з корекцією — та сама формула, що center_dist() у m5_cyl.scad."""
    a0 = math.radians(C['GEAR_ALPHA'])
    target = 2 * math.tan(a0) * (x1 + x2) / (z1 + z2) + inv(a0)
    lo, hi = 0.0, math.radians(60)
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if inv(mid) < target else (lo, mid)
    return C['GEAR_M'] * (z1 + z2) / 2 * math.cos(a0) / math.cos(lo)


def shift(z):
    return round(max(0.0, (17 - z) / 17), 2)


def geometry(sc):
    """Розміри кожного циліндра в друкованих мм і перевірка, що все влазить у зведену довжину."""
    src = open(os.path.join(ROOT, 'scad', 'excavator_boom.scad'), encoding='utf-8').read()
    val = lambda n: float(re.search(rf'^{n}\s*=\s*([\d.]+)\s*;', src, re.M).group(1))
    out = {}
    for i, k in enumerate(KEYS):
        wall = 6.5 if k == 'boom' else 5.0                      # як у hyd_cylinder() моделі
        c = dict(L0=val(f'{k}_cyl_closed') / sc, S=val(f'{k}_cyl_stroke') / sc,
                 od=(val(f'{k}_cyl_bore') + 2 * wall) / sc, pin=val(f'{k}_cyl_pin') / sc, id=C['TUBE_ID'][i])
        c['x_ci'] = C['EYE_LEN'] + C['REAR_WALL']                # дно кришки: упор поршня у зведеному
        c['x_hr'] = c['x_ci'] + c['S'] + C['PUCK']              # задній торець голови: упор у розкритому
        c['nose'] = c['L0'] - C['EYE_LEN'] - C['FRONT_GAP'] - c['x_hr'] - C['HEAD_CORE']
        c['screw'] = c['L0'] - c['pin'] / 2 - 0.8 - c['x_ci']  # хвіст у поршні → кінець у вушку
        c['a_min'] = c['od'] / 2 + C['N20_T'] / 2 + MOTOR_GAP
        if c['nose'] < 0:
            sys.exit(f'calc.py: {k}: голова не влазить у зведену довжину (бракує {-c["nose"]:.1f} мм)')
        out[k] = c
    return out


def gear_pairs(a_min):
    """[(z_pin, x_pin, a, i)] — пари, що стають: мотор не ближче a_min до гільзи і не далі A_MAX."""
    res = []
    for zp in range(Z_PIN_MIN, Z_PIN_MAX + 1):
        a = center_distance(C['Z_NUT'], 0.0, zp, shift(zp))
        if a_min <= a <= A_MAX:
            res.append((zp, shift(zp), a, C['Z_NUT'] / zp))
    return res


def own_mass():
    """Друковані деталі циліндрів, г: {(циліндр, 'body'|'rod'): маса} з їхніх STL."""
    out = {}
    for f in glob.glob(os.path.join(OWN_STL, '*.stl')):
        m = re.match(r'(boom|stick|bucket)_(\w+)_x(\d+)\.stl$', os.path.basename(f))
        if m:
            k, part, qty = m.group(1), m.group(2), int(m.group(3))
            side = 'rod' if part in ('puck', 'eye') else 'body'
            out[k, side] = out.get((k, side), 0.0) + md.stl_volume(f) * qty * md.PLA * md.FILL
    if len(out) < 2 * len(KEYS):
        sys.exit(f'calc.py: немає STL циліндрів у {OWN_STL} — спершу make.sh stl')
    return out


def main():
    md.check_cylinders()
    sc = md.scale()
    if sc != C['SC']:
        sys.exit(f'calc.py: SC у m5_cyl.scad = {C["SC"]}, у parts.scad = {sc}')
    g = K.GEOM
    geo = geometry(sc)
    printed = own_mass()

    # --- маса й центр ваги кожного циліндра (відстані в мм МАШИНИ від пальця бази / штока)
    ends = dict(boom=('C', 'D'), stick=('F', 'G'), bucket=('H', 'J'))
    cyl_load, cyl_rows = [], []
    for k, c in geo.items():
        body_p, rod_p = printed[k, 'body'], printed[k, 'rod']
        head_x = c['x_hr'] + 6                                    # мотор, гайка, підшипник
        body_m = body_p + N20_G + BUY_G
        body_x = (body_p * c['L0'] * 0.55 + (N20_G + BUY_G) * head_x) / body_m
        steel = c['screw'] * STEEL_G_PER_MM
        rod_back = c['L0'] - (c['x_ci'] + c['screw'] / 2)         # від пальця штока — не міняється з ходом
        p1, p2 = ends[k]
        cyl_load += [(body_m, ('ax', p1, p2, body_x * sc)), (rod_p + steel, ('axr', p1, p2, rod_back * sc))]
        cyl_rows.append((k, body_p, rod_p, steel, body_m + rod_p + steel))

    orig_locate = md.locate

    def locate(p, where):
        """Точка на осі циліндра: 'ax' — d мм від першої точки, 'axr' — від другої."""
        if isinstance(where, tuple) and where[0] in ('ax', 'axr'):
            _, a, b, d = where
            A, B = (p[a], p[b]) if where[0] == 'ax' else (p[b], p[a])
            return K.add(A, K.mul(K.sub(B, A), d / K.dist(A, B)))
        return orig_locate(p, where)
    md.locate = locate

    parts = [(m, w) for key, m, w in md.masses() if w is not None and not key.startswith('cyl_')]
    pr = bucket.profile(bucket.BUCKET, g)
    cap = bucket.capacity(bucket.BUCKET, g)
    sand_g = cap['heaped'] * 1000 / sc ** 3 * md.SAND
    bk_pts = {'bk': tuple(pr['side'].centroid.coords[0]), 'sand': tuple(pr['struck'].centroid.coords[0])}
    load = parts + cyl_load
    F_empty = md.forces(g, load, bk_pts)
    F_sand = md.forces(g, load + [(sand_g, 'sand')], bk_pts)
    T_empty, T_sand = md.torques(F_empty, 0.0), md.torques(F_sand, 0.0)   # підшипник — торця немає

    q = md.Q_LPM * 1e6 / 60
    real = {k: (c['stroke'] / (q / c['A_push']), c['stroke'] / (q / c['A_pull'])) for k, c in K.CYL.items()}
    turns = {k: geo[k]['S'] / md.PITCH for k in geo}
    every = {(r, n0): (md.n20_stall(r, n0, i0, ist), ds * 98.07, rated * 98.07, ist)
             for r, n0, i0, _, _, rated, ds, ist in md.N20}

    def run(k, n0, ts, i, T):
        """(час висування, втягування, частка моменту зупинки мотора) або None — стоїть."""
        tm = [T[k, s] / (i * ETA_SPUR) for s in (0, 1)]
        if max(tm) >= ts:
            return None
        t = [turns[k] / (n0 / i * (1 - tm[s] / ts) / 60) for s in (0, 1)]
        return t[0], t[1], max(tm) / ts

    # --- вибране
    R, N0 = C['MOTOR']
    if (R, N0) not in every:
        sys.exit(f'calc.py: 12GAN20-{R}, {N0} об/хв немає в каталозі model_drive.N20')
    TS, TS_DS, T_RATED, IST = every[R, N0]
    pick = {}
    for i, k in enumerate(KEYS):
        zp = C['Z_PIN'][i]
        a = center_distance(C['Z_NUT'], 0.0, zp, shift(zp))
        res = run(k, N0, TS, C['Z_NUT'] / zp, T_empty)
        if a < geo[k]['a_min'] or a > A_MAX:
            sys.exit(f'calc.py: {k}: пара {C["Z_NUT"]}/{zp} (a = {a:.2f}) не стає: треба {geo[k]["a_min"]:.1f}…{A_MAX:g} мм')
        if res is None:
            sys.exit(f'calc.py: {k}: 12GAN20-{R}, {N0} об/хв з парою {C["Z_NUT"]}/{zp} не тягне порожню модель')
        pick[k] = (a, zp, C['Z_NUT'] / zp, res)

    # --- порівняння: кожен N20 з найкращою парою на кожен циліндр
    pairs = {k: gear_pairs(c['a_min']) for k, c in geo.items()}
    best = {}
    for (r, n0), (ts, _, _, ist) in every.items():
        if ist == 1.0 and (r, n0) != (R, N0):
            continue                                          # рядки з «заглушкою» струму — не порівнюємо
        for k in geo:
            cand = []
            for zp, xp, a, i in pairs[k]:
                res = run(k, n0, ts, i, T_empty)
                if res and res[2] <= md.OVERLOAD:
                    cand.append((max(res[0] / real[k][0], res[1] / real[k][1]), a, zp, i, res))
            if cand:
                top = max(1.0, min(cand)[0]) * SPEED_TOL
                best[r, n0, k] = min((c for c in cand if c[0] <= top), key=lambda c: c[1])
    ranked = sorted((max(best[r, n0, k][0] for k in geo), r, n0) for (r, n0) in every
                    if all((r, n0, k) in best for k in geo))

    L = []
    w = L.append
    w('# Циліндри M5 — розрахунок')
    w('')
    w('> Згенеровано `print3d-parts/m5_cylinders/calc.py` (крок `make.sh`) — руками не правити. '
      'Як влаштовано й навіщо — `print3d-parts/m5_cylinders/README.md`.')
    w('')
    w(f'## Довжини (друковані мм, 1:{sc})')
    w('')
    w('Зведена довжина й хід — ті самі, що в моделі. Упори — поршень об дно кришки (зведений) і об задній '
      'торець голови (розкритий); шийка вушка штока голови не торкається.')
    w('')
    w('| Циліндр | Зведений | Хід | Розкритий | Гільза Ø зовн. / внутр. | Дно кришки | Голова від | Запас на ніс | Шпилька M5 |')
    w('|---|---:|---:|---:|---|---:|---:|---:|---:|')
    for k, c in geo.items():
        w(f'| {md.NAMES[k]} | {c["L0"]:.0f} | {c["S"]:.0f} | {c["L0"] + c["S"]:.0f} | {c["od"]:.1f} / {c["id"]:.1f} | '
          f'{c["x_ci"]:.1f} | {c["x_hr"]:.1f} | {c["nose"]:.1f} | {c["screw"]:.0f} |')
    w('')
    w(f'«Дно кришки» й «голова від» — від осі пальця бази. Голова займає {C["HEAD_CORE"]:.1f} мм; що лишилось '
      '(«запас на ніс») — напрямна шпильки попереду голови.')
    w('')
    w('## Маса циліндрів')
    w('')
    w('| Циліндр | Друковане: корпус, г | Друковане: шток, г | Шпилька, г | Разом з мотором, г |')
    w('|---|---:|---:|---:|---:|')
    for k, bp, rp, st, tot in cyl_rows:
        w(f'| {md.NAMES[k]} | {bp:.1f} | {rp:.1f} | {st:.1f} | {tot:.1f} |')
    w('')
    w(f'Друковане — з STL циліндрів, PLA {md.PLA} г/см³, 100 %. Мотор {N20_G:g} г і гайка з підшипником сидять '
      'у голові; сталь шпильки важить приблизно як уся друкована гільза. Решта машини — з STL набору.')
    w('')
    w('## Вибраний мотор')
    w('')
    w(f'**12GAN20-{R}, {N0} об/хв**, шестерні ' + ', '.join(
        f'{md.NAMES[k].lower()} {C["Z_NUT"]}/{pick[k][1]}' for k in KEYS) +
      f', міжосьова {pick["boom"][0]:.2f} мм. Час ходу моделі (висування / втягування) і частка моменту зупинки мотора:')
    w('')
    w('| Циліндр | Машина, с | Модель порожня, с | Модель з піском, с | Повільніше за машину |')
    w('|---|---:|---:|---:|---:|')
    for k in KEYS:
        a, zp, i, (te, tr, ld) = pick[k]
        rs = run(k, N0, TS, i, T_sand)
        slow = max(te / real[k][0], tr / real[k][1])
        w(f'| {md.NAMES[k]} | {real[k][0]:.1f} / {real[k][1]:.1f} | {te:.0f} / {tr:.0f} · {ld * 100:.1f} % | ' +
          ('стоїть' if rs is None else f'{rs[0]:.0f} / {rs[1]:.0f} · {rs[2] * 100:.1f} %') + f' | ×{slow:.0f} |')
    lam = math.atan(md.PITCH / (math.pi * md.D2))
    phi = math.atan(md.MU_THREAD / math.cos(math.radians(30)))
    kf = md.D2 / 2 * math.tan(lam + phi)                    # Н·мм на Н осьової сили
    w('')
    w('Сила ваги на циліндрах, Н (порожня / з піском, штовхає / тягне): ' + '; '.join(
        f'{md.NAMES[k].lower()} {F_empty[k][0]:.1f}/{F_empty[k][1]:.1f} · {F_sand[k][0]:.1f}/{F_sand[k][1]:.1f}'
        for k in KEYS) + '.')
    w('')
    w(f'**Упори.** Номінальний момент з даташиту ({T_RATED:.0f} Н·мм) дає на шпильці ≈ {T_RATED * ETA_SPUR / kf:.0f} Н, '
      f'момент зупинки ({min(TS, TS_DS):.0f}–{max(TS, TS_DS):.0f} Н·мм) — ≈ {min(TS, TS_DS) * ETA_SPUR / kf:.0f} Н'
      + (' (струм зупинки в даташиті — «заглушка» 1.00 А)' if IST == 1.0 else '') +
      f'. Вага ж — не більше {max(max(F_sand[k]) for k in KEYS):.0f} Н. Друковані упори й MR128 (осьово ≈ 150 Н) '
      'розраховані на вагу, а не на мотор: зупиняють датчики кінцевиків, драйвер обмежує струм.')
    w('')
    w('## Що дали б інші N20')
    w('')
    w(f'Шестерня гайки z = {C["Z_NUT"]} (менша не вміщає гайку й магніти), модуль {C["GEAR_M"]}. Мотор не ближче '
      f'{MOTOR_GAP} мм до гільзи й не далі {A_MAX:g} мм від осі, тож прискорити гайку шестернями майже нікуди '
      f'(i ≥ {C["Z_NUT"] / Z_PIN_MAX:.2f}) — швидкість задає сам мотор. ККД пари {ETA_SPUR}. Кожен мотор — з '
      f'найкомпактнішою парою, не повільнішою за найшвидшу більш ніж на {SPEED_TOL * 100 - 100:.0f} %, і лише без '
      f'перегріву (≤ {md.OVERLOAD * 100:.0f} % моменту зупинки) на порожній моделі.')
    w('')
    w('| Мотор | Стріла | Рукоять | Ківш | Повільніше за машину |')
    w('|---|---|---|---|---:|')
    for worst, r, n0 in ranked:
        cells = [f'{C["Z_NUT"]}/{best[r, n0, k][2]}: {best[r, n0, k][4][0]:.1f} / {best[r, n0, k][4][1]:.1f} с · '
                 f'{best[r, n0, k][4][2] * 100:.0f} %' for k in KEYS]
        mark = ' ← вибрано' if (r, n0) == (R, N0) else ''
        w(f'| 12GAN20-{r}, {n0} об/хв{mark} | ' + ' | '.join(cells) + f' | ×{worst:.1f} |')
    w('')
    w('Машина: ' + ', '.join(f'{md.NAMES[k].lower()} {real[k][0]:.1f} / {real[k][1]:.1f} с' for k in KEYS) +
      ' (висування / втягування, весь потік насоса в один циліндр).')
    w('')
    w(md_footer())
    text = '\n'.join(L) + '\n'
    if OUT is None:
        print(text)
        return
    open(OUT, 'w', encoding='utf-8').write(text)
    print(f'  {os.path.relpath(OUT, ROOT)} — мотор 12GAN20-{R}, {N0} об/хв; стріла ' +
          f'{pick["boom"][3][0]:.0f} с на хід')


if __name__ == '__main__':
    main()
