#!/usr/bin/env python3
"""Документація: посилання, якорі й однаковість двомовних двійників.

  * кожне відносне посилання й картинка в .md веде на файл, що існує; `#якір` — на справжній
    заголовок (правило GitHub: нижній регістр, пробіли → «-», решта розділових знаків геть);
  * двійники (README, TECHNICAL, QUICKSTART, SAFETY — .md / .uk.md) мають однаковий кістяк:
    та сама послідовність заголовків, таблиць (з кількістю рядків), картинок, блоків коду й
    цитат. Номери рядків не звіряються — один перенос рядка ще не розбіжність структури.

    python3 tools/check_docs.py          # код 1 і перелік, якщо щось не так

Архів `_deprecated/`, зібрані `versions/` і залежності не перевіряються.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWINS = ['README', 'TECHNICAL', 'QUICKSTART', 'SAFETY']
SKIP = ('_deprecated/', 'versions/', 'node_modules/', '.claude/')


def md_files():
    out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files', '*.md'], cwd=ROOT,
                         capture_output=True, text=True).stdout.split('\n')
    return [f for f in out if f and not f.startswith(SKIP) and '/node_modules/' not in f]


def anchor(text):
    return re.sub(r'[^\w\- ]', '', text.strip().lower()).replace(' ', '-')


def anchors(path):
    return {anchor(m.group(1)) for l in open(path, encoding='utf-8')
            for m in [re.match(r'#+ (.*)', l.lstrip('> ').rstrip())] if m}


def skeleton(path):
    """Кістяк документа: послідовність блоків без тексту."""
    out, in_code = [], False
    for l in open(path, encoding='utf-8'):
        l = l.rstrip('\n')
        if l.startswith('```'):
            in_code = not in_code
            if in_code:
                out.append('код')
            continue
        if in_code:
            continue
        m = re.match(r'(#+) ', l)
        if m:
            out.append('h' + str(len(m.group(1))))
        elif l.startswith('|'):
            if out and out[-1].startswith('таблиця'):
                out[-1] = f'таблиця {int(out[-1].split()[1]) + 1}'
            else:
                out.append('таблиця 1')
        elif l.startswith('>'):
            if not out or out[-1] != 'цитата':
                out.append('цитата')
        elif re.match(r'\s*\[?!\[', l):
            out.append('картинка')
    return out


def main():
    bad = []
    files = md_files()
    for f in files:
        txt = open(os.path.join(ROOT, f), encoding='utf-8').read()
        txt = re.sub(r'```.*?```', '', txt, flags=re.S)             # приклади в коді — не посилання
        for link in re.findall(r'\]\(([^)\s]+)\)', txt):
            if link.startswith(('http://', 'https://', 'mailto:')):
                continue
            path, _, anc = link.partition('#')
            target = os.path.normpath(os.path.join(os.path.dirname(os.path.join(ROOT, f)), path)) if path else os.path.join(ROOT, f)
            if path and not os.path.exists(target):
                bad.append(f'{f}: немає файлу — {link}')
            elif anc and target.endswith('.md') and anc not in anchors(target):
                bad.append(f'{f}: немає якоря — {link}')
    for name in TWINS:
        a, b = os.path.join(ROOT, name + '.md'), os.path.join(ROOT, name + '.uk.md')
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        sa, sb = skeleton(a), skeleton(b)
        if sa != sb:
            i = next((k for k in range(min(len(sa), len(sb))) if sa[k] != sb[k]), min(len(sa), len(sb)))
            bad.append(f'{name}.md / {name}.uk.md: кістяк розходиться з блоку {i + 1}: '
                       f'{sa[i] if i < len(sa) else "—"} проти {sb[i] if i < len(sb) else "—"}')
    print(f'  документів: {len(files)}, двійників: {len(TWINS)}')
    if bad:
        print('  НЕ ТАК:')
        for x in bad:
            print('   ', x)
        sys.exit(1)
    print('  посилання, якорі й двійники в порядку')


if __name__ == '__main__':
    main()
