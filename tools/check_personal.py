#!/usr/bin/env python3
"""Перевірка staged-змін на персональні дані — перед КОЖНИМ комітом.

Дивиться не лише в текст: у двійкових файлах особисте ховається в метаданих. Так у репозиторій
уже потрапив ID облікового запису слайсера всередині .3mf, і його довелося вирізати з історії.

  * текст — лише ДОДАНІ рядки staged-диффу;
  * двійкові — весь файл: рядки байтів, члени zip-форматів (.3mf, .docx, .xlsx, .odt, .zip),
    текстові блоки PNG, текст і метадані PDF (pdftotext / pdfinfo, якщо є poppler).

Особисте цієї машини (домашня тека, ім'я користувача, пошта з git config) береться під час
запуску — у самому скрипті його немає, бо репозиторій публічний.

    python3 tools/check_personal.py          # код 1 і перелік знахідок, якщо щось є

Знайшлося — коміт не робити, показати користувачеві й чекати його слова.
"""
import io
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = 'tools/check_personal.py'


def git(*a):
    return subprocess.run(['git', *a], cwd=ROOT, capture_output=True)


def patterns():
    home = os.path.expanduser('~')
    user = os.environ.get('USER') or os.path.basename(home)
    email = git('config', 'user.email').stdout.decode().strip()
    pats = [
        # заглушки в прикладах (`/Users/…`, `/Users/<user>`, `/Users/*`) — не шлях, їх пропускаємо
        (r'/Users/(?![…<*])[^/\s"\'<>`]+', 'шлях до домашньої теки macOS'),
        (r'/home/(?![…<*])[^/\s"\'<>`]+', 'шлях до домашньої теки Linux'),
        (r'[A-Za-z]:\\\\Users\\\\', 'шлях до домашньої теки Windows'),
        (r'/(?:private/)?var/folders/', 'тимчасова тека macOS'),
        (r'file://', 'локальний file:// шлях'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b', 'адреса пошти'),
        (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 'UUID (id сесії, пристрою?)'),
        (r'\b[\w-]+\.local\b(?!\.)', 'ім\'я хоста .local'),                 # але не файл `settings.local.json`
        (r'(?i)\b(?:DesignerUserId|user_?id|access_?code|serial_?(?:no|number)|api_?key|auth_?token)\b', 'поле облікового запису / ключа'),
    ]
    if user and len(user) >= 3:
        pats.append((r'\b' + re.escape(user) + r'\b', 'ім\'я користувача цієї машини'))
    if email:
        pats.append((re.escape(email), 'пошта з git config'))
    return [(re.compile(p), why) for p, why in pats]


PATS = patterns()
ALLOWED_EMAIL = re.compile(r'@users\.noreply\.github\.com$|@example\.(?:com|org)$')


def scan_text(text, where, found):
    for rx, why in PATS:
        for m in rx.finditer(text):
            s = m.group(0)
            if why == 'адреса пошти' and ALLOWED_EMAIL.search(s):
                continue
            ctx = text[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ')
            found.append(f'{where}: {why} — «{ctx.strip()}»')


def png_text(b):
    out, i = [], 8
    while i + 8 <= len(b):
        n = int.from_bytes(b[i:i + 4], 'big'); t = b[i + 4:i + 8]
        if t in (b'tEXt', b'iTXt', b'zTXt'):
            out.append(b[i + 8:i + 8 + n].decode('latin-1'))
        i += 12 + n
    return '\n'.join(out)


def tool(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=120).stdout.decode('utf-8', 'replace')
    except (OSError, subprocess.TimeoutExpired):
        return ''


def scan_binary(path, b, found):
    scan_text(b.decode('latin-1'), path, found)                      # рядки байтів, EXIF, заголовки
    if zipfile.is_zipfile(io.BytesIO(b)):
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            for name in z.namelist():
                scan_text(z.read(name).decode('utf-8', 'replace'), f'{path} → {name}', found)
    if b[:8] == b'\x89PNG\r\n\x1a\n':
        scan_text(png_text(b), f'{path} (текстові блоки PNG)', found)
    if b[:5] == b'%PDF-':
        full = os.path.join(ROOT, path)
        scan_text(tool('pdfinfo', full), f'{path} (метадані PDF)', found)
        scan_text(tool('pdftotext', '-q', full, '-'), f'{path} (текст PDF)', found)


def main():
    if git('rev-parse', '--git-dir').returncode:
        sys.exit('не git-репозиторій')
    found = []
    names = [f for f in git('diff', '--cached', '--name-only', '-z', '--diff-filter=AMRC').stdout.decode().split('\0') if f]
    binary = set()
    for line in git('diff', '--cached', '--numstat', '-z', '--diff-filter=AMRC').stdout.decode().split('\0'):
        parts = line.split('\t')
        if len(parts) >= 3 and parts[0] == '-':
            binary.add(parts[2])
    for f in names:
        if f in binary or f == SELF:          # власні шаблони цей файл позначав би сам
            continue
        diff = git('diff', '--cached', '-U0', '--no-color', '--', f).stdout.decode('utf-8', 'replace')
        added = '\n'.join(l[1:] for l in diff.split('\n') if l.startswith('+') and not l.startswith('+++'))
        scan_text(added, f, found)
    for f in sorted(binary & set(names)):
        scan_binary(f, git('show', ':' + f).stdout, found)
    print(f'  перевірено staged-файлів: {len(names)} (двійкових: {len(binary & set(names))})')
    if found:
        # групуємо «файл + вид знахідки»: сотня UUID об'єктів у .3mf не має ховати один ID облікового запису
        groups = {}
        for x in found:
            where, rest = x.split(': ', 1)
            why, ctx = rest.split(' — ', 1)
            top = where.split(' → ')[0].split(' (')[0]              # член архіву / вид метаданих — у приклад, не в ключ
            groups.setdefault((top, why), []).append(f'{where}: {ctx}' if where != top else ctx)
        order = [why for _, why in PATS]                             # найважливіше — першим, UUID ближче до кінця
        order.sort(key=lambda w: w.startswith('UUID'))
        print('  ЗНАЙДЕНО — коміт не робити, показати користувачеві:')
        for (top, why), ctxs in sorted(groups.items(), key=lambda kv: (order.index(kv[0][1]), kv[0][0])):
            more = f' (ще {len(ctxs) - 1})' if len(ctxs) > 1 else ''
            print(f'    {top}: {why}{more} — {ctxs[0][:160]}')
        sys.exit(1)
    print('  персональних даних не знайдено')


if __name__ == '__main__':
    main()
