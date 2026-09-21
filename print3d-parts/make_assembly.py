#!/usr/bin/env python3
"""Складає ASSEMBLY.md — покрокову інструкцію складання надрукованого набору.

Порядок з'єднань (що до чого приварюється в металі) — у assembly.tsv, це знання
про конструкцію й пишеться руками. Усі ЧИСЛА беруться звідси:
  * назва файлу, кількість, розмір у металі — parts.tsv (він сам із echo(BOM_*));
  * габарит надрукованої деталі — check_print.py, тобто виміряний зі STL.

Окремо рахується таблиця «як не сплутати»: пари деталей, у яких УСІ три габарити
збігаються з точністю до TOL. Саме на них губиться той, хто складає: 34_B_bushing
і 35_E_bushing різняться на 0.8 мм, 36_R_bushing і 41_bk_spacer_Q — на 0.4.

usage: make_assembly.py parts.tsv assembly.tsv check.json [тека_версії] [report.echo] > ASSEMBLY.md
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'print3d'))
from make_bom import sheet, sheets           # noqa: E402  (спільне на два набори)

# Рендер готового вузла на початку розділу — щоб було видно, що саме складається.
# Ці картинки оновлює build_version.sh; яких немає, тих просто не буде в тексті.
NODE_IMG = {
    '1. Стріла': 'part_boom.png',
    '2. Рукоять': 'part_stick.png',
    '3. Ківш': 'part_bucket.png',
}

TOL = 2.0        # мм: більша різниця вже помітна оком
SAME = 0.05      # мм: деталі однакові, взаємозамінні


def load_parts(path):
    """ключ_pp → (файл, к-сть, група, опис)."""
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        f = line.split('\t')
        out[f[0]] = dict(file=f[-4], qty=int(f[-3]), group=f[-2], desc=f[-1])
    return out


def load_pos(path):
    """positions.json від make_pos_drawing.py: [деталь, що міряємо, мм у металі].

    Числа беруться звідти, а не з коду моделі: вони ВИМІРЯНІ зі слідів деталей на
    базових пластинах, і та сама таблиця стоїть підписами на кресленні.
    """
    if not path or not os.path.isfile(path):
        return [], 5, {}
    d = json.load(open(path, encoding='utf-8'))
    return d['rows'], d['scale'], d.get('bases', {})


def load_steps(path):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        step, node, key, to, how = line.split('\t')
        rows.append(dict(step=step, node=node, key=key, to=to, how=how))
    return rows


def dims(checks, parts, key):
    name = f"{parts[key]['file']}_x{parts[key]['qty']}.stl"
    return checks.get(name, {}).get('габарит', [0, 0, 0])


def confusable(parts, checks):
    """Пари деталей, у яких усі три габарити збігаються з точністю до TOL."""
    items = []
    for key, p in parts.items():
        d = dims(checks, parts, key)
        if d and max(d) > 0:
            items.append((key, p, sorted(d, reverse=True)))
    pairs = []
    for i, (k1, p1, d1) in enumerate(items):
        for k2, p2, d2 in items[i + 1:]:
            if max(abs(a - b) for a, b in zip(d1, d2)) > TOL:
                continue
            # Найкращий розрізняльник — той, де найбільша ВІДНОСНА різниця:
            # Ø7.2 проти 6.2 (16 %) видно, а 15.3 проти 14.7 (4 %) — ні.
            best = max(diffs(d1, d2), key=lambda t: abs(t[1] - t[2]) / max(t[1], t[2]))
            rel = abs(best[1] - best[2]) / max(best[1], best[2])
            pairs.append((rel, best, k1, p1, d1, k2, p2, d2))
    pairs.sort(key=lambda r: r[0])       # найнебезпечніші (найсхожіші) — угорі
    return pairs


def fmt(d):
    return ' × '.join(f'{v:.1f}' for v in d)


def shape(d):
    """(Ø, довжина) для деталі обертання або None. d — габарити за спаданням.

    Однакові можуть бути будь-які ДВА з трьох: у довгої втулки це два менші
    (Ø9.0 × 16.0), а в короткої бобишки — два більші (Ø10.0 × 5.0).
    """
    for i, j, k in ((1, 2, 0), (0, 1, 2), (0, 2, 1)):
        if abs(d[i] - d[j]) < 0.15:
            return (d[i] + d[j]) / 2, d[k]
    return None


def fmt_shape(d):
    r = shape(d)
    return f'Ø{r[0]:.1f} × {r[1]:.1f}' if r else fmt(d)


def diffs(d1, d2):
    """[(назва, a, b)] — за чим порівнювати дві деталі однакової форми."""
    r1, r2 = shape(d1), shape(d2)
    if r1 and r2:
        return [('Ø', r1[0], r2[0]), ('довжина', r1[1], r2[1])]
    names = ['найбільший розмір', 'середній розмір', 'товщина']
    return list(zip(names, d1, d2))


def main():
    parts = load_parts(sys.argv[1])
    steps = load_steps(sys.argv[2])
    checks = {c['файл']: c for c in json.load(open(sys.argv[3], encoding='utf-8'))}
    ver_dir = sys.argv[4] if len(sys.argv) > 4 else ''
    pos, SC, bases = load_pos(sys.argv[5] if len(sys.argv) > 5 else '')
    here = os.path.dirname(os.path.abspath(sys.argv[1]))
    smap = sheets(ver_dir, here)
    img_dir = os.path.join(os.path.dirname(here), 'docs', 'img')

    def node_img(node):
        f = NODE_IMG.get(node)
        if not f or not os.path.isfile(os.path.join(img_dir, f)):
            return ''
        return os.path.relpath(os.path.join(img_dir, f), here)

    missing = [s['key'] for s in steps if s['key'] not in parts]
    if missing:
        sys.exit(f'у parts.tsv немає ключів: {", ".join(missing)}')
    unused = [k for k in parts if k not in {s['key'] for s in steps}]
    if unused:
        sys.exit(f'деталі без кроку складання: {", ".join(unused)}')

    print('# Складання набору 1:5: що до чого приклеюється')
    print()
    print('> Згенеровано `make.sh`. Порядок з\'єднань — `assembly.tsv`, габарити —')
    print('> ВИМІРЯНІ зі STL, назви й розміри в металі — `parts.tsv` (з `echo(BOM_*)` моделі).')
    print('>')
    print('> **УВАГА:** масштабна модель, згенерована штучним інтелектом. Метал не різаний,')
    print('> машину не збудовано. Порядок відповідає порядку ЗВАРЮВАННЯ в металі, але')
    print('> інженер його не перевіряв. Див. `SAFETY.md`.')
    print()
    print('Клей — той самий шов: у кроках 1–5 з\'єднання нерухомі. Рухомими лишаються')
    print('тільки пальці кроку 7 і штоки циліндрів.')
    print()

    # ---------------------------------------------------------------- сплутати
    pairs = confusable(parts, checks)
    print('## Як не сплутати схожі деталі')
    print()
    if not pairs:
        print('Пар деталей, у яких збігаються всі три габарити, у наборі немає.')
    else:
        print(f'Пари, у яких усі три габарити збігаються з точністю до {TOL:g} мм — '
              'на око їх не розрізнити, міряйте штангенциркулем:')
        print()
        print('| Деталь | Габарит, мм | Деталь | Габарит, мм | Різниця | Чим відрізняються |')
        print('|---|---|---|---|---:|---|')
        for rel, best, k1, p1, d1, k2, p2, d2 in pairs:
            name, a, b = best
            if abs(a - b) < SAME:
                note, dtxt = '**однакові — взаємозамінні**', '—'
            else:
                note = f'{name}: {a:.1f} проти {b:.1f}'
                dtxt = f'{abs(a - b):.1f}'
            print(f'| `{p1["file"]}` | {fmt_shape(d1)} | `{p2["file"]}` | {fmt_shape(d2)} '
                  f'| {dtxt} | {note} |')
    print()
    print('Габарити тут — у позі друку (деталь лежить так, як вийшла з принтера),')
    print('відсортовані від найбільшого до найменшого, щоб порівняння не залежало від того,')
    print('яким боком ви взяли деталь.')
    print()

    # ------------------------------------------------ прив'язки накладних деталей
    if pos:
        print('## Де саме стають накладні деталі')
        print()
        print('Більшість деталей упирається в кромку або в отвір — їх не поставиш інакше.')
        print('Але чотири приварюються ПОСЕРЕД пластини, нічим не впираючись: вежа F,')
        print('вилка D, вилка H і вуха ковша. На око їх не виставити.')
        print()
        print('Числа ВИМІРЯНІ зі слідів деталей на базових пластинах — не взяті з коду')
        print('моделі й не вписані руками. Праворуч та сама відстань на надрукованій')
        print('деталі. Це ті самі числа, що стоять підписами на кресленні.')
        if os.path.isfile(os.path.join(here, 'img', 'positions.png')):
            print()
            print('![прив\'язки накладних деталей](img/positions.png)')
        prev = None
        for part, what, mm in pos:
            if part != prev:
                name = parts[part]['file'] if part in parts else part
                on = bases.get(part)
                print(f'\n**`{name}` на `{on}`**\n' if on else f'\n**`{name}`**\n')
                print('| Розмір | У металі, мм | Надруковано, мм |')
                print('|---|---:|---:|')
                prev = part
            print(f'| {what} | {mm:g} | {mm / SC:.2f} |')
        print()
        print('Усі чотири — дзеркальні пари й стоять симетрично середній площині вузла,')
        print('тому «від бічної кромки до зовнішньої грані» однакове з обох боків.')
        print('Відступи міряються по СЛІДУ деталі на базі: бобишка навколо отвору звисає')
        print('за основу (у вежі F на 17.5 мм за лінію перелому, у вуха ковша на 56 мм')
        print('позаду накладки), і за габаритом контуру деталь стала б не на місце.')
        print()

    # ---------------------------------------------------------------- кроки
    last = None
    for s in steps:
        if s['node'] != last:
            print(f'\n## {s["node"]}\n')
            img = node_img(s['node'])
            if img:
                print(f'![{s["node"]}]({img})')
                print()
            print('| Крок | Файл | К-сть | Габарит друку, мм | Ескіз | Куди | Як |')
            print('|---|---|---:|---|---|---|---|')
            last = s['node']
        p = parts[s['key']]
        d = dims(checks, parts, s['key'])
        # Круглі — як Ø×довжина, решта — XYZ у позі друку: плиту так упізнати легше
        ds = sorted(d, reverse=True)
        size = fmt_shape(ds) if shape(ds) else fmt(d)
        link = sheet(smap, s['key'])
        link = f'[аркуш]({link})' if link else '—'
        print(f'| {s["step"]} | `{p["file"]}` | {p["qty"]} | {size} | {link} '
              f'| {s["to"]} | {s["how"]} |')

    print()
    print('## Позначення')
    print()
    print('- **Ескіз** — аркуш із контуром і розмірами деталі В МЕТАЛІ. Саме за ним')
    print('  упізнаєте пластину, коли на столі лежать три схожі. Аркушів немає у смуг,')
    print('  круглих деталей і пальців: їхні розміри цілком описані рядком специфікації.')
    print('- **Габарит друку** — виміряний зі STL, у міліметрах надрукованої деталі.')
    print('  Розмір у металі (лист 8 мм, труба 120×80×5 тощо) — у `BOM.md` і `parts.tsv`.')
    print('- Числа в колонці **Як** — це розміри В МЕТАЛІ, як їх бачить модель')
    print('  (отвір Ø66, проміжок 30 мм). На надрукованій деталі вони вп\'ятеро менші:')
    print('  Ø66 → 13.2 мм, проміжок 30 → 6 мм. Так зроблено навмисно — за цими числами')
    print('  деталь упізнається на кресленнях і в BOM.')
    print('- **К-сть** — скільки штук цього файлу в наборі; дзеркальні пари друкуються')
    print('  з одного файлу, тож ліва й права деталь однакові.')
    print('- Кроки 1–5 — вузли, їх можна складати в будь-якому порядку між собою.')
    print('  Крок 6 (циліндри) і 7 (пальці) — останні.')


if __name__ == '__main__':
    main()
