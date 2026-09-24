#!/usr/bin/env python3
"""HTML → PDF через Chrome, з шапкою й підвалом tools/page_style.py. Спільне для генераторів PDF
(зараз — аркуші розкладки print3d-parts/sheets/make_sheets.py).

    from html_pdf import to_pdf, find_chrome
    how = to_pdf(html_path, pdf_path, find_chrome(), 'Назва документа', '2026-01-01', header=None)
"""
import os
import shutil
import subprocess
import sys

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


def find_chrome():
    return os.environ.get('CHROME') or next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)


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
