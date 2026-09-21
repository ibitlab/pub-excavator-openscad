#!/usr/bin/env python3
"""Креслення «де саме стають накладні деталі» для ASSEMBLY.md.

Вежа F і вилка D — єдині деталі вузла, що приварюються ПОСЕРЕД пластини, нічим не
впираючись у кромку чи отвір. Словами це читається погано, тому тут малюється
вид збоку з реальними контурами і поперечний переріз.

Контури беруться з моделі через `projection(cut=true)` (pos_cut.scad), розміри —
з того самого `echo(POS)`, що й таблиця в ASSEMBLY.md, тож розійтися вони не можуть.

usage: make_pos_drawing.py report.echo out.png
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

BLUE, GREY, RED = '#1f4e9c', '0.45', '#c0392b'
# Y, на якому брати переріз: 0 — деталь на всю ширину, інакше середина пластини
CUTS = {'cover': 0.0, 'D_saddle': 0.0, 'F_tower': None, 'D_clevis': None}


def echo_of(path, name):
    m = re.search(rf'ECHO: {name} = (\[.*?\])\n', open(path, encoding='utf-8').read(), re.S)
    return json.loads(m.group(1).replace('undef', 'null')) if m else None


def run(out, **defs):
    cmd = ['openscad', '-o', out, '-D', 'part="none"']
    for k, v in defs.items():
        cmd += ['-D', f'{k}={v}']
    subprocess.run(cmd + [CUT], check=True, capture_output=True)


def outline(tmp, key, ycut):
    """Контури деталі у системі стріли. parse_svg_loops уже інвертує Y — вертаємо."""
    svg = os.path.join(tmp, f'{key}.svg')
    run(svg, k=f'"{key}"', ycut=ycut)
    return [[(x, -y) for x, y in loop] for loop in parse_svg_loops(svg)]


def rot(pts, a):
    c, s = cos(radians(a)), sin(radians(a))
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def draw_loops(ax, loops, fc, ec, lw=1.4, z=2):
    for i, loop in enumerate(sorted(loops, key=lambda l: -abs(_area(l)))):
        ax.fill([p[0] for p in loop], [p[1] for p in loop],
                fc=('w' if i else fc), ec=ec, lw=lw, zorder=z + i)


def _area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def dim_h(ax, y, x0, x1, txt, tick=6, up=True):
    ax.annotate('', (x0, y), (x1, y), arrowprops=dict(arrowstyle='<->', color=BLUE, lw=1.0))
    for x in (x0, x1):
        ax.plot([x, x], [y - tick, y + tick], color=BLUE, lw=0.8)
    ax.text((x0 + x1) / 2, y + (tick * 1.6 if up else -tick * 2.6), txt,
            color=BLUE, fontsize=8.5, ha='center', va='bottom' if up else 'top')


def dim_v(ax, x, y0, y1, txt, tick=6):
    ax.annotate('', (x, y0), (x, y1), arrowprops=dict(arrowstyle='<->', color=BLUE, lw=1.0))
    for y in (y0, y1):
        ax.plot([x - tick, x + tick], [y, y], color=BLUE, lw=0.8)
    ax.text(x - tick * 1.8, (y0 + y1) / 2, txt, color=BLUE, fontsize=8.5,
            ha='right', va='center', rotation=90)


def label(ax, x, y, txt, color='0.2', fontsize=9, **kw):
    ax.text(x, y, txt, fontsize=fontsize, color=color, **kw)


def head(fig, x, y, title, sub):
    """Заголовок панелі — через fig.text: set_title і власний підпис налазять."""
    fig.text(x, y, title, fontsize=11.5, weight='bold')
    fig.text(x, y - 0.021, sub, fontsize=8.5, color='0.35')


def side_view(ax, base, part):
    """Вид збоку: база світла, накладна деталь синя, датум — у нулі."""
    draw_loops(ax, base, '#e8e8e8', GREY, 1.2, 2)
    draw_loops(ax, part, '#cfe0f5', BLUE, 1.6, 4)
    ax.set_aspect('equal')
    ax.axis('off')


def main():
    report, out = sys.argv[1], sys.argv[2]
    pos_rows = echo_of(report, 'POS') or []
    scale = int(re.search(r'=== друк компонентів 1:(\d+)', open(report, encoding='utf-8').read()).group(1))
    P = {(r[0], r[2]): r[3] for r in pos_rows}

    def mm(part, what):
        v = P[(part, what)]
        return f'{v:g} мм\n({v / scale:.1f} друк.)'

    with tempfile.TemporaryDirectory() as tmp:
        run(os.path.join(tmp, 'g.echo'), k='""')
        geo = dict(echo_of(os.path.join(tmp, 'g.echo'), 'GEO'))
        gap_F, gap_D, pl = geo['gap_F'], geo['gap_D'], geo['plate']
        CUTS['F_tower'] = gap_F / 2 + pl / 2
        CUTS['D_clevis'] = gap_D / 2 + pl / 2
        loops = {k: outline(tmp, k, v) for k, v in CUTS.items()}

    fig = plt.figure(figsize=(15, 10.5))
    fig.suptitle('Де саме стають накладні деталі', fontsize=17, weight='bold', x=0.06, ha='left')
    fig.text(0.06, 0.945, 'вежа F на накладці перелому і вилка D на сідлі — '
             'єдині деталі стріли, що не впираються ні в кромку, ні в отвір',
             fontsize=10, color='0.35')

    # ---------------------------------------------------------------- вежа F
    a = -geo['alpha1']                      # 1-й сегмент — горизонтально
    K = rot([tuple(geo['K'])], a)[0]
    ax = fig.add_axes([0.05, 0.53, 0.60, 0.33])
    head(fig, 0.05, 0.885, '1. Вежа F на верхній накладці перелому',
         'вид збоку, 1-й сегмент горизонтально; нуль — лінія перелому')
    base = [[(x - K[0], y - K[1]) for x, y in rot(l, a)] for l in loops['cover']]
    part = [[(x - K[0], y - K[1]) for x, y in rot(l, a)] for l in loops['F_tower']]
    hole = rot([tuple(geo['F_hole'])], a)[0]
    hole = (hole[0] - K[0], hole[1] - K[1])
    side_view(ax, base, part)

    top = geo['tube_h'] / 2 + geo['cover_t']          # верхня поверхня накладки
    rear = -geo['cover_half']
    ax.plot([0, 0], [top - 40, hole[1] + 78], color=RED, lw=1.1, ls=(0, (7, 4)), zorder=6)
    label(ax, 6, hole[1] + 80, 'лінія перелому', color=RED, fontsize=8.5)
    ax.plot([rear - 46, 160], [top, top], color='0.6', lw=0.7, ls=(0, (5, 4)), zorder=1)
    ax.plot(*hole, marker='+', ms=13, color=RED, mew=1.6, zorder=8)

    dim_h(ax, top - 48, rear, geo['tower_fwd'],
          mm('F_tower', 'довжина основи вежі на накладці'), up=False)
    ax.annotate(mm('F_tower', 'передня кромка вежі не доходить до лінії перелому на'),
                (geo['tower_fwd'] / 2, top + 4), xytext=(112, top + 66), fontsize=8.5,
                color=BLUE, ha='center', arrowprops=dict(arrowstyle='->', color=BLUE, lw=0.9))
    dim_h(ax, hole[1] + 40, hole[0], 0, mm('F_tower', 'центр отвору F назад від лінії перелому'))
    dim_v(ax, rear - 62, top, hole[1], mm('F_tower', 'центр отвору F над верхньою поверхнею накладки'))
    ax.annotate('задня кромка вежі — ВРІВЕНЬ\nіз задньою кромкою накладки',
                (rear, top + 4), xytext=(rear + 24, top + 132), fontsize=9, color=RED,
                ha='center', arrowprops=dict(arrowstyle='->', color=RED, lw=1.0))
    ax.set_xlim(rear - 96, 196)
    ax.set_ylim(top - 96, hole[1] + 112)

    # ---------------------------------------------------------------- вилка D
    a = -geo['u2_ang']
    O = rot([tuple(geo['D_org'])], a)[0]
    ax = fig.add_axes([0.05, 0.06, 0.60, 0.33])
    head(fig, 0.05, 0.415, '2. Вилка D на сідлі під переломом',
         'вид збоку, вісь кронштейна горизонтально; нуль — середина сідла')
    base = [[(x - O[0], y - O[1]) for x, y in rot(l, a)] for l in loops['D_saddle']]
    part = [[(x - O[0], y - O[1]) for x, y in rot(l, a)] for l in loops['D_clevis']]
    hole = rot([tuple(geo['D_hole'])], a)[0]
    hole = (hole[0] - O[0], hole[1] - O[1])
    side_view(ax, base, part)

    bot = -geo['tube_h'] / 2 - geo['saddle_t']        # нижня поверхня сідла
    ax.plot([-176, 176], [bot, bot], color='0.6', lw=0.7, ls=(0, (5, 4)), zorder=1)
    ax.plot([0, 0], [bot + 30, hole[1] - 40], color=RED, lw=1.1, ls=(0, (7, 4)), zorder=6)
    ax.plot(*hole, marker='+', ms=13, color=RED, mew=1.6, zorder=8)
    off = P[('D_clevis', 'відступ кромки вилки від кожного торця сідла')]
    txt = mm('D_clevis', 'відступ кромки вилки від кожного торця сідла')
    dim_h(ax, bot + 34, -130, -130 + off, txt)
    dim_h(ax, bot + 34, 130 - off, 130, txt)
    label(ax, 0, bot + 40, 'відступ однаковий з обох торців', color=BLUE,
          ha='center', fontsize=8.5)
    dim_v(ax, -174, bot, hole[1], mm('D_clevis', 'центр отвору D нижче нижньої поверхні сідла'))
    ax.annotate('отвір D — рівно посередині\nдовжини сідла', (0, hole[1]),
                xytext=(118, hole[1] - 40), fontsize=9, color=RED, ha='center',
                arrowprops=dict(arrowstyle='->', color=RED, lw=1.0))
    ax.set_xlim(-208, 208)
    ax.set_ylim(hole[1] - 76, bot + 62)

    # ------------------------------------------------- перерізи (з чисел, не з STL)
    # d = +1 вежа стоїть НА накладці, d = −1 вилка висить ПІД сідлом — як на виді збоку
    for i, (key, gap, base_t, d, title, edge_what, gap_what) in enumerate([
            ('F_tower', gap_F, geo['cover_t'], +1, 'Переріз: вежа F на накладці',
             'від бічної кромки накладки до зовнішньої грані пластини',
             'проміжок між двома пластинами вежі'),
            ('D_clevis', gap_D, geo['saddle_t'], -1, 'Переріз: вилка D на сідлі',
             'від бічної кромки сідла до зовнішньої грані пластини',
             'проміжок між двома пластинами вилки')]):
        ax = fig.add_axes([0.70, 0.53 - i * 0.47, 0.27, 0.33])
        head(fig, 0.70, 0.885 - i * 0.47, title, 'вид з торця вузла')
        ax.set_aspect('equal')
        ax.axis('off')
        w, H = geo['tube_w'], 90
        ax.fill([-w / 2, w / 2, w / 2, -w / 2], [0, 0, -d * base_t, -d * base_t],
                fc='#e8e8e8', ec=GREY, lw=1.2)
        for s in (-1, 1):
            x0 = gap / 2 if s > 0 else -gap / 2 - pl
            ax.fill([x0, x0 + pl, x0 + pl, x0], [0, 0, d * H, d * H],
                    fc='#cfe0f5', ec=BLUE, lw=1.6)
        edge = P[(key, edge_what)]
        dim_h(ax, d * (H + 16), -gap / 2, gap / 2, mm(key, gap_what), up=d > 0)
        for x0, x1, txt in ((-w / 2, -gap / 2 - pl, f'{edge:g} мм\n({edge / scale:.1f} друк.)'),
                            (gap / 2 + pl, w / 2, f'{edge:g}')):
            dim_h(ax, -d * (base_t + 20), x0, x1, txt, up=d < 0)
        label(ax, 0, -d * (base_t + 62), f'ширина пластини-бази {w:g} мм, товщина {base_t:g}',
              ha='center', fontsize=8.5, color='0.35')
        ax.set_xlim(-w / 2 - 34, w / 2 + 34)
        lo, hi = sorted([-d * (base_t + 78), d * (H + 46)])
        ax.set_ylim(lo, hi)

    fig.text(0.06, 0.028, 'Розміри в мм у МЕТАЛІ, у дужках — та сама відстань на надрукованій '
             f'деталі (1:{scale}). Контури — з моделі, перерізом; числа — з echo(POS).',
             fontsize=8.5, color='0.4')
    fig.text(0.06, 0.008, 'УВАГА: згенеровано ШІ, інженер не перевіряв, метал не різаний. '
             'Див. SAFETY.md', fontsize=8.5, color='0.45')
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f'  {out}')


if __name__ == '__main__':
    main()
