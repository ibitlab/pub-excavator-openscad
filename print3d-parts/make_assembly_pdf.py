#!/usr/bin/env python3
"""
make_assembly_pdf.py — ASSEMBLY.md у PDF для друку на папері (A4).

Чому окремий скрипт, а не pandoc: у наборі не має бути зовнішніх залежностей,
крім того, що вже є (python з Pillow + Chrome; у проєкті це tools/.venv/bin/python). Розмітка ASSEMBLY.md — вузький підмножок
Markdown (заголовки, таблиці, цитата, картинки, списки), і його розбір тут повний:
якщо make_assembly.py почне писати щось нове, скрипт зупиниться з помилкою,
а не мовчки викине рядок.

Що робить із картинками: ВСІ вбудовує у файл (base64), у тому числі ті, що в
ASSEMBLY.md стоять лише посиланням («[аркуш](…)» у колонці «Ескіз»). Аркуш
ескіза на папері нікуди не «клікнеш», тому посилання перетворюється на підпис
«див. ескіз 1.3», а сам аркуш друкується одразу після таблиці свого розділу.

Використання:
    tools/.venv/bin/python print3d-parts/make_assembly_pdf.py        # → print3d-parts/ASSEMBLY.pdf
    … --md ФАЙЛ --out ФАЙЛ                                           # інші шляхи
    … --keep-html ФАЙЛ                                               # лишити HTML (він самодостатній)
    CHROME=/шлях/до/chrome …                                         # інший браузер

Номери сторінок Chrome малює лише через DevTools Protocol, тож вони з'являються,
коли поруч є node з puppeteer-core (tools/media). Без нього PDF той самий, але
без колонтитула — про це буде сказано в кінці.
"""
import argparse
import base64
import datetime
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from author import line as author_line       # noqa: E402  авторство по центру колонтитула (AUTHORS у корені)
import page_style                            # noqa: E402  один вигляд шапки й підвалу для всіх PDF
CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
]

# ---------------------------------------------------------------- картинки
def data_uri(path, max_w=1600):
    """PNG у base64. RGBA кладеться на біле: у друку прозорий фон — це дірка,
    а не білий колір, і принтер може віддати її сірим. Порожні поля обрізаються:
    в аркушах ескізів їх до третини кадру, і без обрізки креслення друкується
    дрібнішим, ніж дозволяє папір."""
    from PIL import Image, ImageChops
    im = Image.open(path)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert('RGB')
    box = ImageChops.difference(im, Image.new('RGB', im.size, 'white')).convert('L').point(
        lambda v: 255 if v > 12 else 0).getbbox()
    if box:
        pad = round(max(im.width, im.height) * 0.012)
        im = im.crop((max(box[0] - pad, 0), max(box[1] - pad, 0),
                      min(box[2] + pad, im.width), min(box[3] + pad, im.height)))
    if im.width > max_w:                      # 1600 px на 186 мм ширини ≈ 218 dpi — більше папір не покаже
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), im.width, im.height


class Images:
    """Кеш вбудованих картинок: один файл — один base64, скільки б разів не траплявся."""
    def __init__(self, base_dir):
        self.base = base_dir
        self.cache = {}
        self.missing = []

    def get(self, src):
        path = os.path.normpath(os.path.join(self.base, src))
        if path not in self.cache:
            if not os.path.exists(path):
                self.missing.append(src)
                self.cache[path] = None
            else:
                self.cache[path] = data_uri(path)
        return self.cache[path]


# ---------------------------------------------------------------- розбір Markdown
RE_IMG = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
RE_LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
RE_CODE = re.compile(r'`([^`]+)`')
RE_BOLD = re.compile(r'\*\*([^*]+)\*\*')
RE_ITAL = re.compile(r'(?<!\*)\*([^*]+)\*(?!\*)')


def inline(text, sketches=None, step=None):
    """Рядковий Markdown → HTML. Чужого тексту тут немає (файл свій, згенерований),
    але екрануємо все одно: інакше «<» у розмірі зламає розмітку."""
    out = html.escape(text)
    def code(m): return f'<code>{m.group(1)}</code>'
    def link(m):
        label, href = m.group(1), m.group(2)
        if sketches is not None and href.lower().endswith('.png'):
            sketches.append((step, href))        # аркуш піде картинкою після таблиці
            return f'<span class="ref">ескіз {html.escape(step)}</span>' if step else 'ескіз нижче'
        return label                             # на папері посилання не натиснеш — лишається текст
    out = RE_LINK.sub(link, out)
    out = RE_BOLD.sub(lambda m: f'<strong>{m.group(1)}</strong>', out)
    out = RE_ITAL.sub(lambda m: f'<em>{m.group(1)}</em>', out)
    out = RE_CODE.sub(code, out)
    return out


def parse(md):
    """Markdown → список блоків. Невідомий рядок зупиняє скрипт: краще впасти тут,
    ніж мовчки надрукувати інструкцію, у якій чогось бракує."""
    lines = md.split('\n')
    blocks, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith('# '):
            blocks.append(('h1', ln[2:].strip())); i += 1
        elif ln.startswith('## '):
            blocks.append(('h2', ln[3:].strip())); i += 1
        elif ln.startswith('### '):
            blocks.append(('h3', ln[4:].strip())); i += 1
        elif ln.startswith('> '):
            buf = []
            while i < len(lines) and lines[i].startswith('>'):
                buf.append(lines[i].lstrip('>').strip()); i += 1
            blocks.append(('quote', '\n'.join(buf)))
        elif ln.startswith('!['):
            m = RE_IMG.fullmatch(ln.strip())
            if not m:
                sys.exit(f'не розібрав рядок з картинкою: {ln}')
            alt, src = m.group(1), m.group(2)
            cap = ''
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith('*') and not lines[j].strip().startswith('**'):
                cap = lines[j].strip().strip('*'); i = j
            blocks.append(('img', (src, alt, cap))); i += 1
        elif ln.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            head, align, body = rows[0], rows[1], rows[2:]
            align = ['right' if a.endswith(':') and not a.startswith(':') else
                     'center' if a.startswith(':') and a.endswith(':') else 'left' for a in align]
            blocks.append(('table', (head, align, body)))
        elif ln.startswith('- '):
            items, cur = [], None
            while i < len(lines) and (lines[i].startswith('- ') or lines[i].startswith('  ') or not lines[i].strip()):
                if lines[i].startswith('- '):
                    if cur is not None: items.append(' '.join(cur))
                    cur = [lines[i][2:].strip()]
                elif lines[i].strip():
                    cur.append(lines[i].strip())
                else:
                    if i + 1 < len(lines) and not lines[i + 1].startswith(('- ', '  ')):
                        break
                i += 1
            if cur is not None: items.append(' '.join(cur))
            blocks.append(('ul', items))
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(('|', '#', '>', '- ', '![')):
                buf.append(lines[i].strip()); i += 1
            blocks.append(('p', ' '.join(buf)))
    return blocks


# ---------------------------------------------------------------- HTML
CSS = """
@page { size: A4 portrait; margin: 25mm 10mm 10mm 10mm; }   /* поля як в аркушів; зверху — місце під шапку (tools/page_style.py) */
* { box-sizing: border-box; }
body { font: 10.2pt/1.42 "Helvetica Neue", Helvetica, Arial, sans-serif; color: #000;
       background: #fff; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 19pt; line-height: 1.2; margin: 0 0 3mm; }
h2 { font-size: 14pt; margin: 0 0 3mm; padding-bottom: 1.5mm; border-bottom: 1.2pt solid #000;
     break-before: page; break-after: avoid; }
h2:first-of-type, h2.flow { break-before: auto; }
h2.flow { margin-top: 7mm; }   /* короткий розділ іде слідом, а не з нової сторінки */
h3 { font-size: 11.5pt; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.6mm; break-inside: avoid; }   /* абзаци короткі: хвіст у два рядки на окремій сторінці нікому не потрібен */
strong { font-weight: 700; }
code { font: 9.2pt/1.3 "SF Mono", Menlo, Consolas, monospace; background: #eee;
       padding: 0 0.6mm; border-radius: 0.6mm; overflow-wrap: anywhere; }
ul { margin: 0 0 3mm; padding-left: 5mm; }
li { margin-bottom: 1.6mm; break-inside: avoid; }

.warn { border: 1.2pt solid #000; background: #f2f2f2; padding: 3mm 3.5mm; margin: 0 0 5mm;
        font-size: 9.6pt; break-inside: avoid; }
.warn p:last-child { margin-bottom: 0; }

table { width: 100%; border-collapse: collapse; margin: 0 0 4mm; font-size: 9pt; }
thead { display: table-header-group; }            /* шапка повторюється на кожній сторінці */
th, td { border: 0.5pt solid #999; padding: 1.1mm 1.5mm; vertical-align: top; text-align: left; }
th { background: #e6e6e6; font-weight: 700; font-size: 8.8pt; }
tr { break-inside: avoid; }
td.right, th.right { text-align: right; }
td.center, th.center { text-align: center; }
tbody tr:nth-child(even) { background: #f6f6f6; }
/* Назва файлу не переноситься по літерах: «04_gus / set» на столі не впізнати. */
td code, th code { white-space: nowrap; overflow-wrap: normal; background: none; font-size: 8.8pt; }
.ref { white-space: nowrap; font-size: 8.6pt; }
.keep { break-inside: avoid; }                    /* підпис разом зі своєю короткою таблицею */
.keep table { margin-bottom: 4mm; }

figure { margin: 0 0 5mm; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; }
figcaption { font-size: 9pt; font-style: italic; margin-top: 1.2mm; }
figure.sheet { margin-bottom: 4mm; }
figure.sheet img { max-height: 112mm; border: 0.4pt solid #bbb; }   /* два аркуші на сторінку */
figure.tall img { max-height: 198mm; }   /* креслення прив'язок разом із заголовком і текстом розділу — на одну сторінку */
.sheets-title { font-size: 10.5pt; font-weight: 700; margin: 0 0 3mm; break-after: avoid; }

.lead { font-size: 9.4pt; color: #333; margin-bottom: 4mm; }
.toc { border: 0.5pt solid #999; padding: 3mm 3.5mm 3mm 8mm; margin: 0 0 5mm; font-size: 9.6pt;
       break-inside: avoid; }
.toc li { margin-bottom: 1mm; }
.toc-title { font-weight: 700; margin: 0 0 2mm; margin-left: -4.5mm; }
.missing { color: #000; border: 1pt dashed #000; padding: 2mm; font-size: 9pt; }
"""


def short_sections(blocks, limit_mm=130):
    """Назви розділів, які НЕ починаються з нової сторінки. «5. Колона» — один
    рядок таблиці, і окрема сторінка під нього — просто витрачений папір.
    Висота прикидається грубо (рядок ≈ 9 мм, аркуш ескіза ≈ 118 мм): точність
    тут не потрібна, треба лише відрізнити розділ на пів сторінки від великого."""
    out, cur, h = set(), None, 0
    def close():
        if cur and h < limit_mm:
            out.add(cur)
    for kind, val in blocks:
        if kind == 'h2':
            close(); cur, h = val, 14
        elif cur is None:
            continue
        elif kind == 'table':
            h += 10 + 9 * len(val[2]) + 118 * sum(r.count('](') for row in val[2] for r in row)
        elif kind == 'img':
            h += 80
        else:
            h += 14
    close()
    return out


def render(blocks, images, title_hint):
    """Блоки → HTML. Аркуші ескізів, зібрані з таблиці розділу, друкуються одразу
    після неї: на папері вони мають бути поруч із кроками, а не за посиланням."""
    out, sketches, sec_no = [], [], 0
    toc = [b[1] for b in blocks if b[0] == 'h2']
    short = short_sections(blocks)

    def flush_sketches():
        nonlocal sketches
        if not sketches:
            return
        out.append('<p class="sheets-title">Аркуші ескізів до цього розділу '
                   '(контур і розміри В МЕТАЛІ, масштаб не дотриманий)</p>')
        for step, src in sketches:
            got = images.get(src)
            name = os.path.splitext(os.path.basename(src))[0]
            cap = f'Ескіз {step} · {html.escape(name)}' if step else html.escape(name)
            if got:
                out.append(f'<figure class="sheet"><img src="{got[0]}" alt="">'
                           f'<figcaption>{cap}</figcaption></figure>')
            else:
                out.append(f'<p class="missing">немає файлу ескіза: {html.escape(src)}</p>')
        sketches = []

    close_at = -1
    for idx, (kind, val) in enumerate(blocks):
        # Підпис накладної деталі й коротка таблиця під ним — один шматок:
        # інакше «06_D_clevis на 07_D_saddle» лишається внизу сторінки без розмірів.
        if kind == 'p' and idx + 1 < len(blocks) and blocks[idx + 1][0] == 'table' \
                and len(blocks[idx + 1][1][2]) <= 8:
            out.append('<div class="keep">')
            close_at = idx + 1
            # Прикінцевий абзац розділу йде в ту саму групу: сам по собі він
            # з'їдає цілу сторінку перед розривом на наступний розділ.
            tail = idx + 2
            if tail < len(blocks) and blocks[tail][0] == 'p' \
                    and (tail + 1 == len(blocks) or blocks[tail + 1][0] == 'h2'):
                close_at = tail
        if kind == 'h1':
            pass                      # заголовок — у шапці кожної сторінки (to_pdf, tools/page_style.py), як в аркушах
        elif kind == 'h2':
            flush_sketches()
            sec_no += 1
            cls = ' class="flow"' if val in short else ''
            out.append(f'<h2{cls}>{inline(val)}</h2>')
            if sec_no == 1:                      # зміст — на першій сторінці, перед першим розділом
                items = ''.join(f'<li>{inline(t)}</li>' for t in toc)
                out.insert(len(out) - 1,
                           f'<div class="toc"><p class="toc-title">У цьому аркуші</p><ul>{items}</ul></div>')
        elif kind == 'h3':
            out.append(f'<h3>{inline(val)}</h3>')
        elif kind == 'quote':
            body = ''.join(f'<p>{inline(p)}</p>' for p in val.split('\n\n') if p.strip())
            out.append(f'<div class="warn">{body}</div>')
        elif kind == 'p':
            out.append(f'<p>{inline(val)}</p>')
        elif kind == 'ul':
            out.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in val) + '</ul>')
        elif kind == 'img':
            src, alt, cap = val
            got = images.get(src)
            if not got:
                out.append(f'<p class="missing">немає картинки: {html.escape(src)}</p>')
                continue
            cls = 'tall' if got[2] > got[1] else ''
            fig = f'<figure class="{cls}"><img src="{got[0]}" alt="{html.escape(alt)}">'
            if cap:
                fig += f'<figcaption>{inline(cap)}</figcaption>'
            out.append(fig + '</figure>')
        elif kind == 'table':
            head, align, body = val
            th = ''.join(f'<th class="{a}">{inline(c)}</th>' for c, a in zip(head, align))
            rows = []
            for r in body:
                step = r[0].strip() if r else ''
                step = step if re.fullmatch(r'\d+\.\d+', step) else None
                tds = ''.join(f'<td class="{a}">{inline(c, sketches, step)}</td>'
                              for c, a in zip(r, align))
                rows.append(f'<tr>{tds}</tr>')
            out.append(f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>')
        if idx == close_at:
            out.append('</div>')
    flush_sketches()
    return (f'<!doctype html><html lang="uk"><head><meta charset="utf-8">'
            f'<title>{html.escape(title_hint)}</title><style>{CSS}</style></head>'
            f'<body>{"".join(out)}</body></html>')


# ---------------------------------------------------------------- PDF
def to_pdf(html_path, pdf_path, chrome, footer_title, date, header=None):
    """Спершу node+puppeteer-core (дає колонтитул із номерами сторінок), інакше —
    сам Chrome через --print-to-pdf. PDF в обох випадках той самий, крім номерів.
    Підвал — tools/page_style.footer_html. header = (заголовок, «набір · версія · дата»[, підзаголовок]) —
    шапка на кожній сторінці тим самим шаблоном (page_style.header_html); без неї документ малює шапку сам
    (аркуші розкладки — у SVG кожного аркуша)."""
    media = os.path.join(ROOT, 'tools', 'media')
    if shutil.which('node') and os.path.isdir(os.path.join(media, 'node_modules', 'puppeteer-core')):
        # Файл кладеться саме в tools/media: node шукає пакет від теки СКРИПТА,
        # а не від cwd, тож зі scratchpad імпорт puppeteer-core не знайдеться.
        js = os.path.join(media, '.topdf.tmp.mjs')
        with open(js, 'w') as f:
            f.write("""
import puppeteer from 'puppeteer-core';
const [chrome, src, out, header, footer] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: chrome, headless: 'new' });
const p = await b.newPage();
await p.goto('file://' + src, { waitUntil: 'load' });
await p.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true,
  displayHeaderFooter: true, headerTemplate: header, footerTemplate: footer });
await b.close();
""")
        try:
            head = page_style.header_html(*header) if header else '<div></div>'
            foot = page_style.footer_html(footer_title, date, author_line())
            r = subprocess.run(['node', js, chrome, html_path, pdf_path, head, foot],
                               cwd=media, capture_output=True, text=True)
        finally:
            os.remove(js)
        if r.returncode == 0 and os.path.exists(pdf_path):
            return 'node + puppeteer-core (з номерами сторінок)'
        print('  puppeteer не спрацював, друкую самим Chrome:', r.stderr.strip()[:200] or r.stdout.strip()[:200])
    r = subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                        f'--print-to-pdf={pdf_path}', html_path], capture_output=True, text=True)
    if not os.path.exists(pdf_path):
        sys.exit('Chrome не створив PDF:\n' + r.stderr[-800:])
    return 'Chrome --print-to-pdf (без номерів сторінок: потрібен node з puppeteer-core у tools/media)'


def pdf_pages(path):
    d = open(path, 'rb').read()
    return len(re.findall(rb'/Type\s*/Page[^s]', d))


def main():
    ap = argparse.ArgumentParser(description='ASSEMBLY.md → PDF для друку на папері')
    ap.add_argument('--md', default=os.path.join(ROOT, 'print3d-parts', 'ASSEMBLY.md'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'print3d-parts', 'ASSEMBLY.pdf'))
    ap.add_argument('--keep-html', help='зберегти проміжний HTML (самодостатній, картинки всередині)')
    a = ap.parse_args()

    md = open(a.md, encoding='utf-8').read()
    blocks = parse(md)
    images = Images(os.path.dirname(os.path.abspath(a.md)))
    title = next((v for k, v in blocks if k == 'h1'), 'Складання набору')
    doc = render(blocks, images, title)

    html_path = a.keep_html or os.path.join(tempfile.mkdtemp(), 'assembly.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(doc)

    chrome = os.environ.get('CHROME') or next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)
    if not chrome:
        sys.exit('не знайшов Chrome; вкажіть CHROME=/шлях/до/chrome')
    date = datetime.date.today().isoformat()
    vd = os.path.join(ROOT, 'versions')
    vers = sorted(d for d in os.listdir(vd) if d.startswith('V')) if os.path.isdir(vd) else []
    meta = f"print3d-parts · {vers[-1] if vers else 'без версії'} · {date}"          # як у шапці аркушів розкладки
    head, _, sub = title.partition(': ')
    how = to_pdf(html_path, os.path.abspath(a.out), chrome, title, date, header=(head, meta, sub))

    n_img = sum(1 for v in images.cache.values() if v)
    print(f'  {a.out}: {pdf_pages(a.out)} стор., {os.path.getsize(a.out) // 1024} КБ, '
          f'картинок вбудовано {n_img}')
    print(f'  друк: {how}')
    if a.keep_html:
        print(f'  HTML: {html_path}')
    if images.missing:
        print('  УВАГА, немає файлів: ' + ', '.join(sorted(set(images.missing))))


if __name__ == '__main__':
    main()
