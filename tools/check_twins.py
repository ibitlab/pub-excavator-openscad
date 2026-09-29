#!/usr/bin/env python3
"""
check_twins.py — звірка Python-двійників з моделлю: tools/kinematics.py (кінематика) і tools/bucket.py
(профіль ковша) проти scad/excavator_boom.scad. Модель — єдине джерело правди; двійники пишуться руками
і тихо розходяться з нею, коли параметр міняють лише в одному місці.

Один запуск OpenSCAD (≈0.2 с, без геометрії): до моделі через -D дописується вираз echo(TWIN = …),
який друкує її параметри й обчислені величини; модель при цьому не змінюється ані рядком. Звіряються:
  1. параметри: GEOM і CYL (kinematics.py), BUCKET і STICK (bucket.py) — з відповідними змінними моделі;
  2. похідні: хорда й кут стріли, точки шарнірів у системах стріли/рукояті;
  3. діапазони кутів з довжин циліндрів (стріла, рукоять, ківш);
  4. пози: світові точки B, D, F, E, G, H, R, J, Q, вістря зуба й довжини трьох циліндрів
     у 27 позах (межі й середини трьох кутів) — функції pt_*() моделі проти kinematics.py;
  5. профіль ковша: спинка, дуга п'яти, дно, розгортка обичайки.

Запуск (потрібен shapely → через venv):  tools/.venv/bin/python tools/check_twins.py [-v] [-D змінна=значення …]
  -v  — надрукувати всі звірені величини, не лише розбіжності
  -D  — передати в OpenSCAD (самоперевірка: -D boom_L1=901 має дати розбіжність)
Код виходу: 0 — усе збігається, 1 — є розбіжності, 2 — модель не прочиталась.
"""
import argparse, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kinematics as K                                     # noqa: E402
try:
    import bucket as BK                                    # noqa: E402  (тягне shapely)
except ImportError as e:
    sys.exit(f"check_twins: {e} — запускати через tools/.venv/bin/python")

SCAD = os.path.join(HERE, '..', 'scad', 'excavator_boom.scad')

# Допуски. OpenSCAD друкує числа з 6 значущими цифрами: 2134.26 — це ±0.005 мм.
TOL_PARAM = 1e-6     # параметри — точно (відносна)
TOL_MM = 0.05        # точки й довжини, мм
TOL_DEG = 0.01       # кути, °
TOL_DEG_BUCKET = 0.05  # межі кута ковша: модель сканує з кроком 0.25° і уточнює лінійно, Python — бісекцією по довжині
SHOW_PER_GROUP = 5     # скільки розбіжностей друкувати в групі (крім параметрів — їх усі)

# ----------------------------------------------------------------------------
# Що з чим звіряється: (назва для звіту, вираз OpenSCAD, значення Python, допуск, відносний?)
# ----------------------------------------------------------------------------
GEOM_MAP = dict(L1='boom_L1', L2='boom_L2', bend='boom_bend', Cx='boom_cyl_base[0]', Cy='boom_cyl_base[1]',
                sD='boom_cyl_sD', eD='boom_cyl_eD', Ls='stick_L', sF='stick_cyl_sF', eF='stick_cyl_eF',
                hx='stick_heel_x', hy='stick_heel_y', sH='bucket_cyl_sH', eH='bucket_cyl_eH',
                rx='rocker_rx', ry='rocker_ry', Lr='rocker_L', Ll='link_L', qx='bucket_ear[0]', qy='bucket_ear[1]',
                tip='bucket_tip', A_height='ground_below_A')
GEOM_SKIP = {'A_setback'}   # у 2D не використовується, у моделі відповідника немає
CYL_FIELDS = ('bore', 'rod', 'stroke', 'closed', 'pin')
# STICK у bucket.py — розміри біля осі E, які в моделі обчислюються з інших параметрів
STICK_MAP = dict(tip_ext='stick_tip_ext', tip_chamfer='stick_tip_chamfer', h2='stick_tube_h/2',
                 tip_plate_back='rocker_rx + 120', bushE_len='stick_tube_w + 2*plate_boss',
                 r_tip_R='bush_od_small/2 + 12', r_bush_R='bush_od_small/2',
                 rocker_r_R='pin_R/2 + 22', rocker_r_J='pin_JQ/2 + 20', link_r='pin_JQ/2 + 20',
                 j_boss_r='(pin_JQ + 16)/2', eye_r='(bucket_cyl_pin + 2*14)/2', rod_r='bucket_cyl_rod/2',
                 body_r='(bucket_cyl_bore + 2*5)/2', plate_boss='plate_boss',
                 pin_E='pin_E', pin_JQ='pin_JQ', link_w_in='link_w_in', bush_small='bush_od_small')


def checks():
    """Список (група, назва, вираз OpenSCAD, значення Python, допуск, відносний)."""
    g, b = K.GEOM, BK.BUCKET
    out = []
    for k, v in g.items():
        if k in GEOM_SKIP: continue
        if k not in GEOM_MAP:
            out.append(('параметри', f"GEOM['{k}']", 'undef', v, 0, False)); continue   # новий ключ без відповідника
        out.append(('параметри', f"GEOM['{k}'] ↔ {GEOM_MAP[k]}", GEOM_MAP[k], v, TOL_PARAM, True))
    for c, d in K.CYL.items():
        for f in CYL_FIELDS:
            out.append(('параметри', f"CYL['{c}']['{f}'] ↔ {c}_cyl_{f}", f"{c}_cyl_{f}", d[f], TOL_PARAM, True))
    for k, v in b.items():
        out.append(('параметри', f"BUCKET['{k}'] ↔ bucket_{k}", f"bucket_{k}", list(v) if isinstance(v, tuple) else v, TOL_PARAM, True))
    for k, v in BK.STICK.items():
        if k not in STICK_MAP:
            out.append(('параметри', f"STICK['{k}']", 'undef', v, 0, False)); continue
        out.append(('параметри', f"STICK['{k}'] ↔ {STICK_MAP[k]}", STICK_MAP[k], v, TOL_PARAM, True))

    # похідна геометрія: хорда стріли, точки в системах стріли (θ = 0) і рукояті
    alpha1, Lb = K.boom_shape(g)
    out += [('похідні', 'хорда стріли Lb', 'boom_Lb', Lb, TOL_MM, False),
            ('похідні', 'кут 1-го сегмента alpha1', 'boom_alpha1', alpha1, TOL_DEG, False)]
    bp = K.boom_points(g, 0.0)
    for n in ('K', 'B', 'D', 'F'):
        out.append(('похідні', f'{n} у системі стріли', f'{n}_l', list(bp[n]), TOL_MM, False))
    out.append(('похідні', 'C (база циліндра стріли)', 'C_w', list(bp['C']), TOL_MM, False))
    loc = dict(E_s=(g['Ls'], 0), G_s=(-g['hx'], g['hy']), H_s=(g['sH'], g['eH']), R_s=(g['Ls'] - g['rx'], g['ry']))
    for n, v in loc.items():
        out.append(('похідні', f'{n[0]} у системі рукояті', n, list(v), TOL_MM, False))

    # діапазони кутів
    th, ps = K.boom_range(g), K.stick_range(g)
    _, om0, om1, _ = K.bucket_range(g)
    out += [('діапазони', 'стріла, мін.', 'boom_angle_min', th[0], TOL_DEG, False),
            ('діапазони', 'стріла, макс.', 'boom_angle_max', th[1], TOL_DEG, False),
            ('діапазони', 'рукоять, мін.', 'stick_angle_min', ps[0], TOL_DEG, False),
            ('діапазони', 'рукоять, макс.', 'stick_angle_max', ps[1], TOL_DEG, False),
            ('діапазони', 'ківш, мін.', 'bucket_angle_min', om0, TOL_DEG_BUCKET, False),
            ('діапазони', 'ківш, макс.', 'bucket_angle_max', om1, TOL_DEG_BUCKET, False)]

    # пози: межі й середини кожного кута (ківш — на 0.5° всередину, щоб не впертися в межу ходу)
    if None in th or None in ps or None in (om0, om1):
        return out   # діапазон не розв'язується — розбіжність уже покажуть рядки вище
    ths = (th[0], (th[0] + th[1]) / 2, th[1])
    pss = (ps[0], (ps[0] + ps[1]) / 2, ps[1])
    oms = (om0 + 0.5, (om0 + om1) / 2, om1 - 0.5)
    for t in ths:
        for s in pss:
            for o in oms:
                bp = K.boom_points(g, t); sp = K.stick_points(g, bp, s); fw = K.bucket_points_fwd(g, sp, o)
                tipP = K.add(sp['E'], K.rot((g['tip'], 0), sp['a_s'] - o))
                a = f'{t!r}, {s!r}, {o!r}'   # повна точність: :g дав би лише 6 знаків
                pose = f'θ={t:.1f} ψ={s:.1f} ω={o:.1f}'
                pts = [('B', f'pt_B({t!r})', bp['B']), ('D', f'pt_D({t!r})', bp['D']), ('F', f'pt_F({t!r})', bp['F']),
                       ('E', f'pt_E({t!r}, {s!r})', sp['E']), ('G', f'pt_G({t!r}, {s!r})', sp['G']),
                       ('H', f'pt_H({t!r}, {s!r})', sp['H']), ('R', f'pt_R({t!r}, {s!r})', sp['R']),
                       ('Q', f'pt_Q({a})', fw and fw['Q']), ('J', f'pt_J({a})', fw and fw['J']),
                       ('зуб', f'pt_tip({a})', tipP)]
                for n, e, v in pts:
                    out.append(('пози', f'{pose}: {n}', e, None if v is None else list(v), TOL_MM, False))
                out += [('пози', f'{pose}: L циліндра стріли', f'boom_cyl_len({t!r})', K.dist(bp['C'], bp['D']), TOL_MM, False),
                        ('пози', f'{pose}: L циліндра рукояті', f'stick_cyl_len({t!r}, {s!r})', K.dist(bp['F'], sp['G']), TOL_MM, False),
                        ('пози', f'{pose}: L циліндра ковша', f'bucket_cyl_len({a})', fw and fw['L'], TOL_MM, False)]

    # профіль ковша
    pr = BK.profile(b, g)
    out += [('ківш', 'спинка', 'bk_back_len', pr['Lb'], TOL_MM, False),
            ('ківш', "дуга п'яти, °", 'bk_turn2', pr['turn2'], TOL_DEG, False),
            ('ківш', 'дно (до ножа)', 'bk_floor_len', pr['floor_len'], TOL_MM, False),
            ('ківш', 'розгортка обичайки', 'bk_dev_len', pr['dev_len'], TOL_MM, False),
            ('ківш', 'внутрішня ширина', 'bk_w_in', BK.capacity(b, g)['w_in'], TOL_MM, False)]
    return out


def scad_values(exprs, defines):
    """Обчислити вирази в контексті моделі одним запуском OpenSCAD."""
    with tempfile.TemporaryDirectory() as tmp:
        echo = os.path.join(tmp, 'twin.echo')
        cmd = ['openscad', '-o', echo, '-D', 'part="none"',
               '-D', f"TWIN__ = echo(TWIN__ = [{', '.join(exprs)}]) 0"]
        for d in defines: cmd += ['-D', d]
        r = subprocess.run(cmd + [SCAD], capture_output=True, text=True)
        text = open(echo, encoding='utf-8').read() if os.path.exists(echo) else ''
    m = re.search(r'^ECHO: TWIN__ = (.*)$', text, re.M)
    if not m:
        sys.stderr.write(r.stderr[-2000:])
        sys.exit("check_twins: OpenSCAD не надрукував TWIN__ — модель не прочиталась")
    s = re.sub(r'\bundef\b', 'null', m.group(1))
    s = re.sub(r'(?<![\w.])(-?)inf\b', r'"\1inf"', s).replace('nan', '"nan"')
    return json.loads(s)


def differs(py, sc, tol, rel):
    """Повертає (чи розбіжність, найбільша різниця)."""
    if py is None or sc is None:
        return (py is None) != (sc is None), None
    if isinstance(py, (list, tuple)):
        if not isinstance(sc, list) or len(sc) != len(py): return True, None
        res = [differs(a, c, tol, rel) for a, c in zip(py, sc)]
        ds = [d for _, d in res if d is not None]
        return any(bad for bad, _ in res), (max(ds) if ds else None)
    if isinstance(sc, str) or isinstance(py, str): return py != sc, None
    d = abs(py - sc)
    lim = tol * max(1.0, abs(py)) if rel else tol
    return d > lim, d


def fmt(v):
    if v is None: return 'undef'
    if isinstance(v, (list, tuple)): return '[' + ', '.join(fmt(x) for x in v) + ']'
    if isinstance(v, float): return f'{v:.4f}'.rstrip('0').rstrip('.')
    return str(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('-D', dest='defines', action='append', default=[], metavar='ЗМІННА=ЗНАЧЕННЯ')
    a = ap.parse_args()
    cs = checks()
    vals = scad_values([c[2] for c in cs], a.defines)
    bad = 0; groups = {}
    for (grp, name, expr, py, tol, rel), sc in zip(cs, vals):
        wrong, d = differs(py, sc, tol, rel)
        n = groups.setdefault(grp, [0, 0]); n[wrong] += 1
        if wrong:
            bad += 1
            # причину видно з параметрів; похідні від одного параметра розходяться сотнями — показати перші
            if a.verbose or grp == 'параметри' or n[1] <= SHOW_PER_GROUP:
                print(f"✗ {name}: Python {fmt(py)}, модель {fmt(sc)}" + (f" (різниця {d:.4g})" if d is not None else ''))
        elif a.verbose:
            print(f"  {name}: {fmt(py)}")
    for grp, (ok, nb) in groups.items():
        if not a.verbose and grp != 'параметри' and nb > SHOW_PER_GROUP:
            print(f"✗ {grp}: ще {nb - SHOW_PER_GROUP} розбіжностей (усі — з -v)")
    summary = ', '.join(f"{g} {ok}" + (f" (✗ {nb})" if nb else '') for g, (ok, nb) in groups.items())
    if bad:
        print(f"РЕЗУЛЬТАТ: розбіжностей Python ↔ модель — {bad} із {len(cs)} звірених величин ({summary})")
        print("  модель — джерело правди: виправити tools/kinematics.py / tools/bucket.py під неї")
        return 1
    print(f"РЕЗУЛЬТАТ: двійники збігаються з моделлю — {len(cs)} величин ({summary})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
