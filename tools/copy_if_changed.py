#!/usr/bin/env python3
"""copy_if_changed.py — скопіювати PNG сторінки PDF у docs/img/, лише якщо сторінка змінилась ПО СУТІ.

Сторінки ескізів і аркушів несуть у шапці «… · версія · дата», у підвалі — дату. Звичайне `cp`
робило з кожного збирання новий двійковий файл у git, хоча креслення те саме. Тут пікселі звіряються БЕЗ смуг
шапки й підвалу: різниця лише там — старий файл лишається байт-у-байт; інакше — копіюється.

    tools/.venv/bin/python tools/copy_if_changed.py SRC DST [--top ММ] [--bottom ММ]

--top / --bottom — висота смуг, які не звіряються, мм від краю аркуша (A4; масштаб — з ширини
картинки й орієнтації). Типово — з tools/page_style.py: поле + шапка + 1 мм зверху (20), поле знизу
(10; підвал стоїть на 5.4–8 мм від низу). У тілі сторінки мінливого бути не повинно: примітка ескізів навмисно без
версії (tools/bom_drawings.py, foot_note). Змінився розмір картинки — це теж зміна, копіюється.
"""
import argparse, os, shutil, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import page_style as ps          # noqa: E402

TOP = ps.MARGIN + ps.HEAD_H + 1.0   # шапка з лінією і 1 мм запасу
BOTTOM = ps.MARGIN                  # підвал


def body(path, top, bottom):
    a = np.asarray(Image.open(path).convert('RGB'))
    h, w = a.shape[:2]
    px_mm = w / (297.0 if w > h else 210.0)
    return a[int(round(top * px_mm)):h - int(round(bottom * px_mm))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--top', type=float, default=TOP)
    ap.add_argument('--bottom', type=float, default=BOTTOM)
    a = ap.parse_args()
    name = os.path.relpath(a.dst)
    if os.path.exists(a.dst):
        old, new = body(a.dst, a.top, a.bottom), body(a.src, a.top, a.bottom)
        if old.shape == new.shape and np.array_equal(old, new):
            print(f"  {name}: те саме поза шапкою й підвалом — лишено як є")
            return 0
    shutil.copyfile(a.src, a.dst)
    print(f"  {name}: оновлено")
    return 0


if __name__ == '__main__':
    sys.exit(main())
