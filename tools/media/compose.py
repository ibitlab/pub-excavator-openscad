#!/usr/bin/env python3
"""Збирання зображень для публікацій (запускати через tools/.venv/bin/python — потрібні Pillow і matplotlib).
  compose.py grid OUT.png --cols 2 --cell 1200x1000 [--bg f8f8f8] ФАЙЛИ…      колаж-сітка
  compose.py poses OUT.png ТЕКА                                                 4 пози в ОДНОМУ масштабі зі спільною лінією землі
        (у ТЕЦІ: pose_reach|deep|height|transport.png + такі самі .json з --meta сторінки; знімки — ортогональні, «Збоку», --clean)
  compose.py drawings ТЕКА [--dpi 220]                                          ескізи деталей у високій роздільності (ТЕКА/drawings/png)
  compose.py clearances OUT.png [--dpi 220]                                     2D-зазори ковша на ході циліндра
"""
import sys, os, json, math, argparse
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))

def grid(out, files, cols, cell, bg, gap=16):
    rows = (len(files) + cols - 1) // cols
    im = Image.new('RGB', (cols * cell[0] + (cols + 1) * gap, rows * cell[1] + (rows + 1) * gap), bg)
    for i, f in enumerate(files):
        t = Image.open(f).convert('RGB'); t.thumbnail(cell, Image.LANCZOS)
        im.paste(t, (gap + (i % cols) * (cell[0] + gap) + (cell[0] - t.width) // 2, gap + (i // cols) * (cell[1] + gap) + (cell[1] - t.height) // 2))
    im.save(out, optimize=True)

def poses(out, src, S=0.40, X=(-350, 3100), ground=650, gap=18, bg=(243, 241, 236)):
    """Кожен знімок вписаний по-своєму; масштаб знімка відновлюється з камери сторінки (ортогональна: піввисота кадру = 0.42·відстань/zoom),
    потім усі пози вирізаються одним світовим вікном (мм від осі A) і зводяться до спільного масштабу S пкс/мм."""
    rows = [(('reach', 'deep'), -2500, 650), (('height', 'transport'), -800, 2350)]
    cw = round((X[1] - X[0]) * S); H = sum(round((z1 - z0) * S) for _, z0, z1 in rows) + 3 * gap
    im = Image.new('RGB', (2 * cw + 3 * gap, H), bg); y = gap
    for names, Z0, Z1 in rows:
        ch = round((Z1 - Z0) * S)
        for i, n in enumerate(names):
            t = Image.open(f'{src}/pose_{n}.png').convert('RGB'); m = json.load(open(f'{src}/pose_{n}.json'))
            s = t.height / (2 * 0.42 * math.dist(m['p'], m['t']) / m['zoom']); tx, tz = m['t'][0], m['t'][2]
            box = (t.width / 2 + (X[0] - tx) * s, t.height / 2 - (Z1 - tz) * s, t.width / 2 + (X[1] - tx) * s, t.height / 2 - (Z0 - tz) * s)
            cell = Image.new('RGB', (round(box[2] - box[0]), round(box[3] - box[1])), bg); cell.paste(t, (-round(box[0]), -round(box[1])))
            cell = cell.resize((cw, ch), Image.LANCZOS); gy = round((Z1 + ground) * S)
            ImageDraw.Draw(cell).line([(0, gy), (cw, gy)], fill=(150, 130, 100), width=3); im.paste(cell, (gap + i * (cw + gap), y))
        y += ch + gap
    im.save(out, optimize=True)

def _hires(dpi):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.figure as mf
    orig = mf.Figure.savefig
    def sv(self, fname, *a, **k):
        if str(fname).endswith('.png'): k['dpi'] = dpi            # скрипти проєкту пишуть PNG з екранною роздільністю — тут підміняється на льоту, без змін у них
        return orig(self, fname, *a, **k)
    mf.Figure.savefig = sv

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['grid', 'poses', 'drawings', 'clearances']); ap.add_argument('out'); ap.add_argument('files', nargs='*')
    ap.add_argument('--cols', type=int, default=2); ap.add_argument('--cell', default='1200x1000'); ap.add_argument('--bg', default='f3f1ec'); ap.add_argument('--dpi', type=int, default=220)
    a = ap.parse_args(); bg = tuple(int(a.bg[i:i + 2], 16) for i in (0, 2, 4))
    if a.cmd == 'grid': grid(a.out, a.files, a.cols, tuple(int(x) for x in a.cell.split('x')), bg)
    elif a.cmd == 'poses': poses(a.out, a.files[0])
    elif a.cmd == 'drawings':
        _hires(a.dpi); import bom_drawings; sys.argv = ['x', '--out', a.out]; bom_drawings.main()
    elif a.cmd == 'clearances':
        _hires(a.dpi); import bucket, kinematics as K; bucket.plot(dict(bucket.BUCKET), dict(K.GEOM), a.out)
