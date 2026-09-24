#!/usr/bin/env python3
"""Прев'ю PDF для README: кілька сторінок рядком, трохи внахлист, з тінню — щоб з першого
погляду було видно, що всередині документа. Сторінки рендерить сам poppler (pdftoppm) —
тобто це той самий PDF, що лежить за посиланням, а не знімок HTML.

    tools/.venv/bin/python tools/media/pdf_preview.py ФАЙЛ.pdf 1,9,10,12 docs/img/pdf_sheets.png [--height 420]

Запускає tools/media/readme_media.sh; сторінки для кожного PDF підібрані там.
"""
import argparse
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument('pdf'); ap.add_argument('pages'); ap.add_argument('out')
ap.add_argument('--height', type=int, default=420, help='висота сторінки в прев\'ю, px')
ap.add_argument('--overlap', type=float, default=0.18, help='частка ширини сторінки, що заходить під наступну')
a = ap.parse_args()

pages = []
with tempfile.TemporaryDirectory() as t:
    for n in map(int, a.pages.split(',')):
        base = os.path.join(t, f'p{n}')
        subprocess.run(['pdftoppm', '-r', '110', '-png', '-f', str(n), '-l', str(n), '-singlefile', a.pdf, base], check=True)
        im = Image.open(base + '.png').convert('RGB')
        im = im.resize((round(im.width * a.height / im.height), a.height), Image.LANCZOS)
        ImageDraw.Draw(im).rectangle([0, 0, im.width - 1, im.height - 1], outline=(190, 190, 190))
        pages.append(im)

pad, sh = 18, 10                                               # поле навколо і зсув тіні
step = [round(p.width * (1 - a.overlap)) for p in pages[:-1]]
W = sum(step) + pages[-1].width + 2 * pad + sh
H = a.height + 2 * pad + sh
canvas = Image.new('RGBA', (W, H), (255, 255, 255, 0))
x = pad
for i, p in enumerate(pages):
    shadow = Image.new('RGBA', (p.width + 4 * sh, p.height + 4 * sh), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([2 * sh, 2 * sh, 2 * sh + p.width, 2 * sh + p.height], fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(sh * 0.6))
    canvas.alpha_composite(shadow, (x - 2 * sh + sh // 2, pad - 2 * sh + sh))
    canvas.paste(p, (x, pad))
    if i < len(step):
        x += step[i]
canvas.save(a.out, optimize=True)
print(f'  {a.out}: {len(pages)} стор. з {os.path.basename(a.pdf)}, {W}×{H}, {os.path.getsize(a.out) // 1024} КБ')
