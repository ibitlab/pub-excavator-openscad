#!/usr/bin/env python3
"""Креслення «де саме стають накладні деталі» + числа до нього.

Чотири деталі вузлів приварюються ПОСЕРЕД пластини, не впираючись ні в кромку,
ні в отвір: вежа F, вилка D, вилка H і вуха ковша. Словами це читається погано,
тому тут малюється вид збоку з реальними контурами і переріз із торця.

Числа не вписані руками й не взяті з коду моделі: відступи й положення отворів
ВИМІРЮЮТЬСЯ з контурів, які дає `projection(cut=true)` (pos_cut.scad). Проміжки
пар і габарити бази — параметри моделі через `echo(GEO)`. Аркуші розкладки беруть
схеми з compute(); main() — для ручної перевірки: картинка + positions.json з тими
самими числами (мм у металі), щоб звіряти читанням, а не оком.

usage: make_pos_drawing.py out.png out.json report.echo
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from math import cos, radians, sin

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CUT = os.path.join(HERE, 'pos_cut.scad')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from bom_drawings import parse_svg_loops                      # noqa: E402
from author import credit, made_with                          # noqa: E402

BLUE, GREY, RED = '#1f4e9c', '0.45', '#c0392b'

# Кожна деталь: у якому вузлі живе, на чому стоїть, як розвернути вид, звідки
# міряти. `up` = +1 деталь стоїть НА базі, −1 висить ПІД нею.
SPECS = [
    dict(key='F_tower', base='cover', own='boom', gap='gap_F', base_k='base_F',
         surf='surf_F', up=+1, holes=[('F', 'F_hole')],
         title='1. Вежа F на верхній накладці перелому',
         sub='вид збоку, 1-й сегмент горизонтально; нуль — лінія перелому',
         front_note='лінія перелому', front_is_bend=True),
    dict(key='D_clevis', base='D_saddle', own='boom', gap='gap_D', base_k='base_D',
         surf='surf_D', up=-1, holes=[('D', 'D_hole')],
         title='2. Вилка D на сідлі під переломом',
         sub='вид збоку, вісь кронштейна горизонтально; нуль — задня кромка сідла'),
    dict(key='H_clevis', base='H_saddle', own='stick', gap='gap_H', base_k='base_H',
         surf='surf_H', up=+1, holes=[('H', 'H_hole')],
         title='3. Вилка H на сідлі рукояті',
         sub='вид збоку, вісь рукояті горизонтально; нуль — задня кромка сідла'),
    dict(key='bk_ear', base='bk_top', own='bucket', gap='gap_E', base_k='base_E',
         surf=None, up=+1, holes=[('E', 'E_hole'), ('Q', 'Q_hole')],
         title='4. Вуха ковша на накладці під вуха',
         sub='вид збоку, накладка горизонтально; нуль — задня кромка накладки'),
]


def part_files(path=None):
    """ключ_pp → назва файлу (05_cover, 08_F_tower…).

    Без цього креслення не зіставити з набором: база на всіх панелях — однакова
    сіра смуга, і зрозуміти, ЯКА це пластина, ні з чого.
    """
    path = path or os.path.join(HERE, 'parts.tsv')
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line and not line.startswith('#'):
            f = line.split('\t')
            out[f[0]] = f[-4]
    return out


def echo_of(path, name):
    m = re.search(rf'ECHO: {name} = (\[.*?\])\n', open(path, encoding='utf-8').read(), re.S)
    return json.loads(m.group(1).replace('undef', 'null')) if m else None


def run(out, **defs):
    cmd = ['openscad', '-o', out, '-D', 'part="none"']
    for k, v in defs.items():
        cmd += ['-D', f'{k}={v}']
    subprocess.run(cmd + [CUT], check=True, capture_output=True)


def outline(tmp, own, key, ycut):
    """Контури деталі у системі її вузла. parse_svg_loops інвертує Y — вертаємо."""
    svg = os.path.join(tmp, f'{own}_{key}.svg')
    run(svg, own=f'"{own}"', k=f'"{key}"', ycut=ycut)
    return [[(x, -y) for x, y in loop] for loop in parse_svg_loops(svg)]


def rot(pts, a):
    c, s = cos(radians(a)), sin(radians(a))
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def place(loops, a, dx, dy):
    return [[(x + dx, y + dy) for x, y in rot(l, a)] for l in loops]


def span(loops):
    xs = [p[0] for l in loops for p in l]
    ys = [p[1] for l in loops for p in l]
    return min(xs), max(xs), min(ys), max(ys)


def footprint(loops, surf, tol=0.8):
    """Слід деталі на базі — не габарит контуру.

    Бобишка навколо отвору виступає за основу: у вежі F вона перекриває лінію
    перелому на 17.5 мм, у вуха ковша звисає на 56 мм позаду накладки. Варити
    треба по сліду, тому беруться лише точки, що лежать НА поверхні бази.
    """
    xs = [p[0] for l in loops for p in l if abs(p[1] - surf) < tol]
    return (min(xs), max(xs)) if xs else span(loops)[:2]


def _area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def draw_loops(ax, loops, fc, ec, lw=1.4, z=2):
    for i, loop in enumerate(sorted(loops, key=lambda l: -abs(_area(l)))):
        ax.fill([p[0] for p in loop], [p[1] for p in loop],
                fc=('w' if i else fc), ec=ec, lw=lw, zorder=z + i)


def dim_h(ax, y, x0, x1, txt, tick=6, up=True):
    if abs(x1 - x0) < 0.05:
        return
    ax.annotate('', (x0, y), (x1, y), arrowprops=dict(arrowstyle='<->', color=BLUE, lw=1.0))
    for x in (x0, x1):
        ax.plot([x, x], [y - tick, y + tick], color=BLUE, lw=0.8)
    ax.text((x0 + x1) / 2, y + (tick * 1.4 if up else -tick * 2.4), txt,
            color=BLUE, fontsize=8, ha='center', va='bottom' if up else 'top')


def dim_v(ax, x, y0, y1, txt, tick=6):
    ax.annotate('', (x, y0), (x, y1), arrowprops=dict(arrowstyle='<->', color=BLUE, lw=1.0))
    for y in (y0, y1):
        ax.plot([x - tick, x + tick], [y, y], color=BLUE, lw=0.8)
    ax.text(x - tick * 1.8, (y0 + y1) / 2, txt, color=BLUE, fontsize=8,
            ha='right', va='center', rotation=90)


def head(fig, x, y, title, sub):
    """Заголовок панелі — через fig.text: set_title і власний підпис налазять."""
    fig.text(x, y, title, fontsize=11.5, weight='bold')
    fig.text(x, y - 0.014, sub, fontsize=8.5, color='0.35')


def frame(spec, geo, loops):
    """Поворот і зсув, після яких база горизонтальна, а нуль — там, де його шукають."""
    key, base = spec['key'], spec['base']
    if key == 'F_tower':
        a = -geo['alpha1']
        o = rot([tuple(geo['K'])], a)[0]
        return a, -o[0], -o[1] + geo['surf_F'] * 0 - geo['surf_F'] + geo['surf_F']
    if key == 'D_clevis':
        a = -geo['u2_ang']
        o = rot([tuple(geo['D_org'])], a)[0]
        return a, -o[0], -o[1]
    if key == 'H_clevis':
        return 0.0, 0.0, 0.0
    return -90.0, 0.0, 0.0        # ківш: вісь x (до зуба) стає вертикаллю


def compute():
    """Контури й числа для всіх чотирьох деталей — те, з чого малюється positions.png
    і пишеться positions.json. Окремою функцією, бо ті самі схеми малюють ще аркуші
    розкладки (sheets/make_sheets.py) — у своєму стилі, але з цих самих чисел.

    Повертає (data, rows, files): data — по деталі контури part/base у системі, де база
    горизонтальна (surf — її поверхня, bx/px — кромки бази й слід деталі, x0 — нуль
    відліку, holes — центри отворів), rows — рядки для positions.json (мм у металі)."""
    files = part_files()
    with tempfile.TemporaryDirectory() as tmp:
        run(os.path.join(tmp, 'g.echo'), k='""')
        geo = dict(echo_of(os.path.join(tmp, 'g.echo'), 'GEO'))
        pl = geo['plate']
        data = []
        for sp in SPECS:
            gap = geo[sp['gap']]
            t = geo['ear_t'] if sp['key'] == 'bk_ear' else pl
            part = outline(tmp, sp['own'], sp['key'], gap / 2 + t / 2)
            base = outline(tmp, sp['own'], sp['base'], 0.0)
            a, dx, dy = frame(sp, geo, None)
            part = place(part, a, dx, dy)
            base = place(base, a, dx, dy)
            holes = [(n, place([[tuple(geo[g])]], a, dx, dy)[0][0]) for n, g in sp['holes']]
            data.append(dict(spec=sp, part=part, base=base, holes=holes, gap=gap, t=t,
                             base_w=geo[sp['base_k']][0], base_t=geo[sp['base_k']][1]))

    # ------------------------------------------------------- числа з контурів
    rows = []
    for d in data:
        sp, up = d['spec'], d['spec']['up']
        bx0, bx1, by0, by1 = span(d['base'])
        surf = by1 if up > 0 else by0          # поверхня, на яку спирається деталь
        px0, px1 = footprint(d['part'], surf)
        d['surf'] = surf
        d['bx'] = (bx0, bx1)
        d['px'] = (px0, px1)
        bend = d['spec'].get('front_is_bend')
        x0 = 0.0 if bend else bx0              # нуль: лінія перелому або задня кромка бази
        d['x0'] = x0
        name = 'накладки' if sp['key'] in ('F_tower', 'bk_ear') else 'сідла'
        put = rows.append
        if bend:
            put([sp['key'], 'задня кромка деталі від задньої кромки накладки', px0 - bx0])
            put([sp['key'], 'передня кромка деталі не доходить до лінії перелому на', 0 - px1])
        else:
            put([sp['key'], f'відступ від задньої кромки {name}', px0 - bx0])
            put([sp['key'], f'відступ від передньої кромки {name}', bx1 - px1])
        for n, (hx, hy) in d['holes']:
            if bend:
                where = 'назад від лінії перелому'
            elif hx < bx0:                     # вісь E ковша звисає ПОЗАДУ накладки
                where = f'позаду задньої кромки {name}'
            elif hx > bx1:
                where = f'попереду передньої кромки {name}'
            else:
                where = f'від задньої кромки {name}'
            put([sp['key'], f'центр отвору {n} {where}', abs(hx - x0)])
            put([sp['key'], f'центр отвору {n} від поверхні {name}', abs(hy - surf)])
        put([sp['key'], 'проміжок між пластинами пари', d['gap']])
        put([sp['key'], f'від бічної кромки {name} до зовнішньої грані пластини',
             (d['base_w'] - d['gap']) / 2 - d['t']])

    # Округлення: контур приходить багатокутником, звідси 11.999 замість 12
    rows = [[a, b, round(v, 1)] for a, b, v in rows]
    return data, rows, files


def main():
    out_png, out_json = sys.argv[1], sys.argv[2]
    rep = open(sys.argv[3], encoding='utf-8').read() if len(sys.argv) > 3 else ''
    m = re.search(r'=== друк компонентів 1:(\d+)', rep)
    scale = int(m.group(1)) if m else 5

    data, rows, files = compute()
    bases = {sp['key']: files.get(sp['base'], sp['base']) for sp in SPECS}
    json.dump({'scale': scale, 'rows': rows, 'bases': bases}, open(out_json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # ------------------------------------------------------------- креслення
    # Розкладка в ДЮЙМАХ, не в частках висоти: інакше поля й заголовки стискаються
    # разом із числом панелей і з четвертої починають налазити одне на одне.
    n = len(data)
    TOP, ROW, BOT = 1.05, 4.3, 0.62
    FH = TOP + n * ROW + BOT
    fig = plt.figure(figsize=(15, FH))
    fig.text(0.055, 1 - 0.42 / FH, 'Де саме стають накладні деталі',
             fontsize=17, weight='bold', va='top')
    fig.text(0.055, 1 - 0.74 / FH, 'чотири деталі, що приварюються посеред пластини — '
             'не впираючись ні в кромку, ні в отвір', fontsize=10, color='0.35', va='top')

    for i, d in enumerate(data):
        sp, up = d['spec'], d['spec']['up']
        top_in = BOT + (n - i) * ROW                 # верх смуги цього рядка, дюйми
        fpart, fbase = files.get(sp['key'], sp['key']), files.get(sp['base'], sp['base'])
        head(fig, 0.055, (top_in - 0.24) / FH,
             f'{sp["title"]}  —  {fpart} на {fbase}', sp['sub'])
        surf, (bx0, bx1), (px0, px1), x0 = d['surf'], d['bx'], d['px'], d['x0']
        by0, by1 = span(d['base'])[2:]
        w = max(bx1 - bx0, px1 - px0)

        ax = fig.add_axes([0.05, (top_in - ROW + 0.30) / FH, 0.60, (ROW - 1.05) / FH])
        draw_loops(ax, d['base'], '#e8e8e8', GREY, 1.2, 2)
        draw_loops(ax, d['part'], '#cfe0f5', BLUE, 1.6, 4)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.plot([bx0 - 0.28 * w, bx1 + 0.12 * w], [surf, surf], color='0.6', lw=0.7,
                ls=(0, (5, 4)), zorder=1)

        hy_top = max(h[1][1] for h in d['holes'])
        hy_bot = min(h[1][1] for h in d['holes'])
        # Виносити розміри треба за КОНТУР, а не за центр отвору: у вуха ковша
        # бобишка навколо осі E піднімається на 40 мм вище самої осі.
        edge = max(span(d['part'])[3], span(d['base'])[3]) if up > 0 else \
            min(span(d['part'])[2], span(d['base'])[2])
        nh = len(d['holes'])
        far = edge + up * (0.12 + 0.13 * nh) * w
        ax.plot([x0, x0], [surf, far], color=RED, lw=1.1, ls=(0, (7, 4)), zorder=6)
        ax.text(x0 + 0.012 * w, far, sp.get('front_note', f'задня кромка {fbase}'),
                color=RED, fontsize=8.5, va='center')
        # нижче/вище САМОЇ бази, а не її поверхні: сідло H завтовшки 10 мм, і підпис
        # зі зсувом у частках довжини ліг би просто на смугу
        ax.text(bx1, surf - up * (d['base_t'] + 0.03 * w), fbase, color=GREY, fontsize=9,
                ha='right', va='top' if up > 0 else 'bottom')
        # праворуч від КОНТУРУ, а не від сліду: у вежі F слід кінчається раніше,
        # і підпис ліг би просто на бобишку
        ax.text(span(d['part'])[1] + 0.03 * w, (surf + edge) / 2, fpart, color=BLUE,
                fontsize=9.5, weight='bold', ha='left', va='center')

        def pair(v):
            return f'{v:.0f}\n({v / scale:.1f})'

        # відступи — під базою (або над нею, якщо деталь висить знизу), двома рівнями
        fx1 = 0.0 if sp.get('front_is_bend') else bx1
        y_in1, y_in2 = surf - up * 0.13 * w, surf - up * 0.25 * w
        dim_h(ax, y_in1, bx0, px0, pair(px0 - bx0), up=up < 0)
        dim_h(ax, y_in2, px1, fx1, pair(fx1 - px1), up=up < 0)

        # Отвори: висоти — ліворуч, відстані вздовж — ЗА контуром деталі. Якщо класти
        # їх біля поверхні бази, лінія лягає всередину самої деталі й нечитна.
        # Ліворуч виносимо від лівого краю ВСЬОГО зображення: у вуха ковша деталь
        # звисає на 56 мм позаду накладки, і виноска від кромки бази лягла б на неї.
        lx = min(bx0, span(d['part'])[0])
        for j, (nm, (hx, hy)) in enumerate(d['holes']):
            ax.plot(hx, hy, marker='+', ms=13, color=RED, mew=1.6, zorder=8)
            dim_v(ax, lx - (0.10 + 0.13 * j) * w, surf, hy, f'{nm}: {pair(abs(hy - surf))}')
            dim_h(ax, edge + up * (0.05 + 0.11 * j) * w, x0, hx,
                  f'{nm}: {abs(hx - x0):.0f} ({abs(hx - x0) / scale:.1f})', up=up > 0)

        # У межі йде ВСЕ, що намальовано, включно з винесеними розмірами: інакше
        # вони опиняються поза панеллю й наїжджають на сусідній рядок.
        used = [surf, hy_top, hy_bot, far, y_in1, y_in2,
                span(d['part'])[2], span(d['part'])[3], by0, by1]
        ax.set_xlim(lx - (0.14 + 0.13 * nh) * w, max(bx1, px1) + 0.16 * w)
        ax.set_ylim(min(used) - 0.10 * w, max(used) + 0.10 * w)

        # ------------------------------------------------------------ переріз
        ax = fig.add_axes([0.70, (top_in - ROW + 0.30) / FH, 0.27, (ROW - 1.05) / FH])
        head(fig, 0.70, (top_in - 0.24) / FH, f'Переріз: {fpart} на {fbase}',
             'вид з торця вузла')
        ax.set_aspect('equal')
        ax.axis('off')
        bw, bt, gap, t = d['base_w'], d['base_t'], d['gap'], d['t']
        Hh = max(60.0, 0.9 * bw / 2)
        ax.fill([-bw / 2, bw / 2, bw / 2, -bw / 2], [0, 0, -up * bt, -up * bt],
                fc='#e8e8e8', ec=GREY, lw=1.2)
        for s in (-1, 1):
            x = gap / 2 if s > 0 else -gap / 2 - t
            ax.fill([x, x + t, x + t, x], [0, 0, up * Hh, up * Hh], fc='#cfe0f5', ec=BLUE, lw=1.6)
        edge = (bw - gap) / 2 - t
        dim_h(ax, up * (Hh + 0.10 * bw), -gap / 2, gap / 2,
              f'{gap:g} мм\n({gap / scale:.1f} друк.)', up=up > 0)
        for a0, a1, txt in ((-bw / 2, -gap / 2 - t, f'{edge:g} мм\n({edge / scale:.1f} друк.)'),
                            (gap / 2 + t, bw / 2, f'{edge:g}')):
            dim_h(ax, -up * (bt + 0.09 * bw), a0, a1, txt, up=up < 0)
        # Відступ підпису — не у частках ширини: у вузької бази 60 мм 0.4×bw = 24,
        # і текст розміру (він у пунктах, а не в мм) налазить на нього.
        cap = bt + 0.16 * bw + 34
        ax.text(0, -up * cap, f'{fbase}: {bw:g} × {bt:g} мм · {fpart}: пластина {t:g} мм',
                ha='center', fontsize=8.5, color='0.35')
        ax.set_xlim(-bw / 2 - 0.14 * bw, bw / 2 + 0.14 * bw)
        lo, hi = sorted([-up * (cap + 24), up * (Hh + 0.30 * bw)])
        ax.set_ylim(lo, hi)

    fig.text(0.055, 0.34 / FH, 'Розміри в мм у МЕТАЛІ, у дужках — та сама відстань на '
             f'надрукованій деталі (1:{scale}). Контури — з моделі перерізом, відступи '
             'ВИМІРЯНІ з них: слід деталі на базі, а не габарит контуру.',
             fontsize=8.5, color='0.4', va='top')
    fig.text(0.055, 0.17 / FH, f'УВАГА: {made_with()} Інженер не перевіряв, метал не '
             'різаний. Див. SAFETY.md', fontsize=8.5, color='0.45', va='top')
    credit(fig)
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    print(f'  {out_png}')
    print(f'  {out_json}')


if __name__ == '__main__':
    main()
