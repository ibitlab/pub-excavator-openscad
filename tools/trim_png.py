#!/usr/bin/env python3
"""Обрізає порожні поля навколо рендера, лишаючи рівну рамку.

`openscad --viewall` вписує не деталь, а її габаритну СФЕРУ, тож довга тонка
деталь займає 16–17 % кадру, решта — тло. Тут кадр підрізається по вмісту.

Тло визначається за кутовим пікселем, поріг — щоб не чіплятися за згладжування.
Файли переписуються на місці.

  tools/trim_png.py docs/img/part_*.png
  tools/trim_png.py --margin 3 файл.png        # рамка у % від більшого боку вмісту
  tools/trim_png.py --common поза1.png поза2.png ...

`--common` рахує ОДНУ рамку на всі файли (об'єднання їхнього вмісту) і ріже всіх
однаково. Саме так і тільки так можна підрізати знімки поз (`side_default`,
`folded`, `max_reach`, `dig_deep`, `max_height`): вони знімаються однією камерою
й порівнюються між собою, тож після НЕЗАЛЕЖНОЇ підрізки кожен дістав би свій
масштаб і порівняння перестало б бути порівнянням.
"""
import argparse
import os
import sys

from PIL import Image, ImageChops

THRESH = 8          # відхилення від тла, за яким піксель вважається вмістом


def content_box(im):
    bg = Image.new('RGB', im.size, im.getpixel((0, 0)))
    mask = ImageChops.difference(im, bg).convert('L').point(lambda p: 255 if p > THRESH else 0)
    return mask.getbbox()


def with_margin(bb, size, margin_pct, min_margin=14):
    w, h = size
    m = max(min_margin, int(max(bb[2] - bb[0], bb[3] - bb[1]) * margin_pct / 100))
    return (max(0, bb[0] - m), max(0, bb[1] - m), min(w, bb[2] + m), min(h, bb[3] + m))


def crop_to(path, box):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    if box == (0, 0, w, h):
        print(f'  {path}: підрізати нема що')
        return False
    bb = content_box(im)
    im.crop(box).save(path)
    fill = ((bb[2] - bb[0]) * (bb[3] - bb[1])) if bb else 0
    now = fill / ((box[2] - box[0]) * (box[3] - box[1])) * 100
    print(f'  {path}: {w}×{h} → {box[2]-box[0]}×{box[3]-box[1]}, '
          f'вміст {fill / (w * h) * 100:.0f}% → {now:.0f}%')
    return True


def trim(path, margin_pct):
    im = Image.open(path).convert('RGB')
    bb = content_box(im)
    if not bb:
        print(f'  {path}: порожній кадр — пропущено')
        return False
    return crop_to(path, with_margin(bb, im.size, margin_pct))


def edges(path):
    """Яких країв кадру торкається геометрія. Порожній список = деталь ціла в кадрі."""
    im = Image.open(path).convert('RGB')
    w, h = im.size
    bb = content_box(im)
    if not bb:
        return ['порожній']
    return [n for n, c in (('ліворуч', bb[0] <= 1), ('зверху', bb[1] <= 1),
                           ('праворуч', bb[2] >= w - 1), ('знизу', bb[3] >= h - 1)) if c]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--margin', type=float, default=3.0, help='рамка, %% від більшого боку вмісту')
    ap.add_argument('--common', action='store_true', help='одна рамка на всі файли')
    ap.add_argument('--edges', action='store_true',
                    help='нічого не різати: лише сказати, чи деталь не вилазить за кадр')
    ap.add_argument('--report', action='store_true',
                    help='таблиця по всіх файлах: розмір, заповнення, краї, порожні')
    a = ap.parse_args()
    if a.report:
        # Одна команда замість десятка відкритих картинок: більшість питань про
        # рендер («не порожньо? не зрізано? не половина кадру біла?») — числові.
        print(f'{"файл":38} {"розмір":>12} {"вміст":>6}  стан')
        for f in a.files:
            im = Image.open(f).convert('RGB')
            w, h = im.size
            bb = content_box(im)
            if not bb:
                print(f'{os.path.basename(f):38} {f"{w}×{h}":>12} {"—":>6}  ПОРОЖНІЙ')
                continue
            fill = (bb[2] - bb[0]) * (bb[3] - bb[1]) / (w * h) * 100
            e = edges(f)
            state = f'ЗРІЗАНО: {", ".join(e)}' if e else ('багато полів' if fill < 55 else 'ok')
            print(f'{os.path.basename(f):38} {f"{w}×{h}":>12} {fill:5.0f}%  {state}')
        return
    if a.edges:
        bad = 0
        for f in a.files:
            e = edges(f)
            if e:
                print(f'  !!! {os.path.basename(f)}: ЗРІЗАНО {", ".join(e)}')
                bad += 1
        print(f'  цілих у кадрі: {len(a.files) - bad} з {len(a.files)}')
        sys.exit(1 if bad else 0)
    files = [f for f in a.files if os.path.isfile(f)]
    for f in set(a.files) - set(files):
        print(f'  {f}: немає файлу', file=sys.stderr)
    if not files:
        return

    n = 0
    if a.common:
        sizes = {Image.open(f).size for f in files}
        if len(sizes) > 1:
            sys.exit(f'--common потребує однакового розміру кадрів, а тут {sizes}')
        box = None
        for f in files:
            bb = content_box(Image.open(f).convert('RGB'))
            if bb:
                box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                              max(box[2], bb[2]), max(box[3], bb[3]))
        if box is None:
            sys.exit('усі кадри порожні')
        box = with_margin(box, sizes.pop(), a.margin)
        for f in files:
            n += crop_to(f, box)
    else:
        for f in files:
            n += trim(f, a.margin)
    print(f'  підрізано: {n}')


if __name__ == '__main__':
    main()
