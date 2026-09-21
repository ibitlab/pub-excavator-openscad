#!/usr/bin/env python3
"""Рендер ракурсів, збережених у 3D-сторінці (`views.json`).

Сторінка (`tools/viewer.sh`) дає кнопки «Копіювати / Додати / Зберегти» — вони пишуть
JSON із камерою, кутами, зміненими параметрами і видимістю. Тут цей JSON стає
рендером OpenSCAD.

  tools/views.py list
  tools/views.py flags перелом-згори
  tools/views.py render перелом-згори --out /tmp/x.png --size 1600x1100
  tools/views.py check круговий-тест --file /tmp/rt.json --page /tmp/rt.png

ЧОМУ ВІДСТАНЬ ПЕРЕРАХОВУЄТЬСЯ. Камера сторінки вже в системі координат моделі
(`camera.up = 0,0,1`), тому око й ціль ідуть в OpenSCAD як є — шестизначною формою
`--camera=eye,target`. А кут огляду різний, і його не можна задати з командного рядка:

    сторінка   32°  по вертикалі (fov у makeCamera)
    OpenSCAD   22.5° — виміряно: куб 200 мм на відстані 1000 дає 558 пікс. з 1000

Тому око відсувається так, щоб кадр на площині цілі лишився тим самим:
    k = tan(32/2) / tan(22.5/2) = 1.4416
Для паралельної проєкції OpenSCAD бере висоту кадру = відстань × 2·tan(22.5/2)
(виміряно: 0.39683 на трьох відстанях), звідси відстань із півкадру сторінки.

ЧОГО CLI НЕ ВІДТВОРИТЬ: `show.pins` і `show.edges` — суто сторінкові, у моделі таких
параметрів немає. Решта видимості лягає на `show_*` моделі.
"""
import argparse
import json
import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, 'scad', 'excavator_boom.scad')
VIEWS = os.path.join(ROOT, 'views.json')

FOV_OS = 22.5                                   # кут огляду OpenSCAD, виміряний
SHOW = {'cylinders': 'show_cylinders', 'linkage': 'show_bucket_linkage', 'bucket': 'show_bucket',
        'post': 'show_post', 'ground': 'show_ground', 'envelope': 'show_envelope'}
PAGE_ONLY = ('pins', 'edges')


def load(path=VIEWS):
    if not os.path.isfile(path):
        sys.exit(f'{path} немає — збережіть ракурс кнопкою «Зберегти» у tools/viewer.sh')
    # «Зберегти» дає {"views": [...]}, «Копіювати» — один об'єкт. Приймаємо обидва:
    # інакше вставлений із буфера ракурс доводиться загортати руками.
    d = json.load(open(path, encoding='utf-8'))
    return d['views'] if isinstance(d, dict) and 'views' in d else [d]


def find(name, views):
    # Сторінка сама підставляє мітку часу замість порожньої назви, але у файлах,
    # збережених раніше, безіменні записи трапляються: один такий беремо без питань.
    names = ', '.join(v['name'] or '(без назви)' for v in views)
    if not name:
        if len(views) == 1:
            return views[0]
        sys.exit('у файлі кілька ракурсів — потрібна назва: ' + names)
    for v in views:
        if v['name'] == name:
            return v
    sys.exit(f'ракурс «{name}» не знайдено; є: {names}')


def camera_arg(cam):
    """--camera=eye,target з відстанню, перерахованою під кут огляду OpenSCAD."""
    eye, tgt = cam['eye'], cam['target']
    d = [e - t for e, t in zip(eye, tgt)]
    dist = math.dist(eye, tgt)
    if dist < 1e-6:
        sys.exit('око збігається з ціллю')
    if cam['projection'] == 'p':
        k = math.tan(math.radians(cam.get('fov_v', 32) / 2)) / math.tan(math.radians(FOV_OS / 2))
        new = dist * k
    else:
        new = 2 * cam['half_height'] / (2 * math.tan(math.radians(FOV_OS / 2)))
    u = [c / dist for c in d]
    e = [t + c * new for t, c in zip(tgt, u)]
    return (f'--camera={e[0]:.2f},{e[1]:.2f},{e[2]:.2f},'
            f'{tgt[0]:.2f},{tgt[1]:.2f},{tgt[2]:.2f}')


def lit(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return '[' + ','.join(lit(x) for x in v) + ']'
    return str(v)


def flags(view, size='1600x1100', part=None):
    cam = view['camera']
    w, h = (int(x) for x in size.lower().split('x'))
    out = [f'--imgsize={w},{h}', camera_arg(cam),
           '--projection=' + ('p' if cam['projection'] == 'p' else 'o'),
           '--colorscheme=Tomorrow', '--render=cgal']
    a = view.get('angles', {})
    for k, name in (('boom', 'boom_angle'), ('stick', 'stick_angle'), ('bucket', 'bucket_angle')):
        if k in a:
            out += ['-D', f'{name}={lit(a[k])}']
    if view.get('ground_below_A') is not None:        # сторінка рухає землю окремо від моделі
        out += ['-D', f'ground_below_A={lit(view["ground_below_A"])}']
    for k, v in view.get('params', {}).items():
        out += ['-D', f'{k}={lit(v)}']
    for k, v in view.get('show', {}).items():
        if k in SHOW:
            out += ['-D', f'{SHOW[k]}={lit(bool(v))}']
    if part:
        out += ['-D', f'part="{part}"']
    return out


def render(out, args):
    if os.path.exists(out):
        os.remove(out)                        # OpenSCAD не створює файл, якщо результат порожній
    subprocess.run(['openscad', '-o', out] + args + [SCAD], check=True, capture_output=True)
    if not os.path.exists(out):
        sys.exit('OpenSCAD нічого не намалював — перевірте параметри ракурсу')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'flags', 'render', 'check'])
    ap.add_argument('name', nargs='?')
    ap.add_argument('--out', default='/tmp/view.png')
    ap.add_argument('--size', default='1600x1100')
    ap.add_argument('--part', help='рендерити один вузол замість усієї машини')
    ap.add_argument('--file', default=VIEWS)
    ap.add_argument('--page', help='знімок канви (view_roundtrip.mjs) для команди check')
    a = ap.parse_args()
    views = load(a.file)

    if a.cmd == 'list':
        for v in views:
            c = v['camera']
            note = f' — {v["note"]}' if v.get('note') else ''
            page = [k for k in PAGE_ONLY if not v.get('show', {}).get(k, True)]
            warn = f'  (сторінкове, не відтвориться: {", ".join(page)})' if page else ''
            print(f'  {(v["name"] or "(без назви)"):24} {c["projection"]} око {c["eye"]} '
                  f'ціль {c["target"]}{note}{warn}')
        return

    v = find(a.name, views)
    args = flags(v, a.size, a.part)
    if a.cmd == 'flags':
        print(' '.join(args))
        return

    if a.cmd == 'check':
        if not a.page:
            sys.exit('потрібен --page: знімок канви від tools/media/view_roundtrip.mjs')
        from PIL import Image
        import numpy as np
        w, h = Image.open(a.page).size
        args = flags(v, f'{w}x{h}', a.part)
        out = a.out if a.out != '/tmp/view.png' else '/tmp/views_check.png'
        render(out, args)

        def mask(p):
            # машина кольорова або темна, тло сторінки — світлий сірий градієнт
            m = np.asarray(Image.open(p).convert('RGB')).astype(int)
            return (m.max(2) - m.min(2) > 28) | (m.mean(2) < 140)

        def box(m):
            ys, xs = np.where(m)
            return xs.min(), ys.min(), xs.max(), ys.max()

        pg, sc = mask(a.page), mask(out)
        bp, bs = box(pg), box(sc)
        kx = (bs[2] - bs[0]) / (bp[2] - bp[0])
        ky = (bs[3] - bs[1]) / (bp[3] - bp[1])
        dx = ((bs[0] + bs[2]) - (bp[0] + bp[2])) / 2
        dy = ((bs[1] + bs[3]) - (bp[1] + bp[3])) / 2
        print(f'  сторінка {bp[2]-bp[0]}×{bp[3]-bp[1]} · openscad {bs[2]-bs[0]}×{bs[3]-bs[1]}')
        print(f'  масштаб {kx:.3f} / {ky:.3f} · зсув центра {dx:+.0f} / {dy:+.0f} пікс.')
        bad = abs(kx - 1) > 0.02 or abs(ky - 1) > 0.02 or abs(dx) > 6 or abs(dy) > 6
        print('  !!! кадр не збігається зі сторінкою' if bad else '  кадр збігається зі сторінкою')
        sys.exit(1 if bad else 0)

    render(a.out, args)
    print(f'  {a.out}')


if __name__ == '__main__':
    main()
