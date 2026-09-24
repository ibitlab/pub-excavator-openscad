#!/usr/bin/env python3
"""Один вигляд шапки й підвалу для ВСІХ PDF проєкту — з одного місця.

Зразок — аркуші розкладки (`print3d-parts/sheets/SHEETS.pdf`):
  шапка   — жирний заголовок ліворуч; праворуч дрібно «набір · версія · дата»;
            під заголовком дрібний підзаголовок; суцільна чорна лінія 0.5 мм;
  підвал  — 7 pt сірим: назва документа ліворуч, автор (файл AUTHORS) посередині,
            «дата · с. N / M» праворуч.
Числа — у мм від краю поля (поле 10 мм з усіх боків).

Хто бере:
  * print3d-parts/sheets/make_sheets.py — шапка в SVG кожного аркуша (head_svg), підвал — to_pdf;
  * print3d-parts/make_assembly_pdf.py  — to_pdf(): шапка й підвал шаблонами Chrome (header_html, footer_html);
  * tools/bom_drawings.py               — ескізи деталей у matplotlib (mpl_header, mpl_footer).
Змінюєш вигляд — змінюй тут, і перезбери всі три PDF.
"""
import html

MARGIN = 10.0          # поле сторінки, мм
TITLE = 5.0            # заголовок, мм (≈ 14 pt), жирний
SMALL = 2.5            # підзаголовок і «набір · версія · дата», мм (≈ 7 pt)
TITLE_Y = 4.6          # базова лінія заголовка від верхнього поля, мм
SUB_Y = 7.9            # базова лінія підзаголовка
RULE_Y = 8.5           # центр лінії під шапкою
RULE_W = 0.5           # її товщина, мм
HEAD_H = 9.0           # висота шапки разом з лінією
FOOT_PT = 7            # підвал, pt
FOOT_Y = 5.7           # базова лінія підвалу від НИЖНЬОГО краю аркуша, мм (низ літер — 5.4 мм, як у Chrome)
CHROME_HEAD_DROP = 5.05   # зсув шапки в шаблоні Chrome донизу, мм — звірено pdftotext -bbox з аркушами (заголовок на 27.7 pt)
CHROME_RULE = 1.35        # поправка товщини рамки в шаблоні колонтитула Chrome — звірено растром із аркушами (0.36 мм)
INK, SUBINK, FOOTINK, AUTHINK = '#000', '#333', '#555', '#888'
FONT_CSS = "'Helvetica Neue', Helvetica, Arial, sans-serif"
FONT_MPL = ['Helvetica Neue', 'Helvetica', 'Arial', 'DejaVu Sans']   # DejaVu — для знаків, яких немає в Helvetica
MM_PER_PT = 25.4 / 72


# ------------------------------------------------------------------ Chrome (шаблони колонтитулів)
# Шаблони Chrome не бачать стилів сторінки: усе — інлайн, розміри в pt/mm.
def header_html(title, meta, sub=''):
    """Шапка кожної сторінки HTML-документа (як на аркушах): потрібне верхнє поле ≥ MARGIN + HEAD_H + 4 мм."""
    t, m, s = html.escape(title), html.escape(meta), html.escape(sub)
    big, small = f'{TITLE / MM_PER_PT:.1f}pt', f'{SMALL / MM_PER_PT:.1f}pt'
    # Chrome ставить шапку від самого краю аркуша, на ≈ 5 мм вище за поле аркушів — звідси CHROME_HEAD_DROP
    return (f'<div style="box-sizing:border-box;width:100%;padding:{CHROME_HEAD_DROP}mm {MARGIN}mm 0;font-family:{FONT_CSS};line-height:1.15">'
            f'<div style="border-bottom:{RULE_W / MM_PER_PT * CHROME_RULE:.2f}pt solid {INK}">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:{big};font-weight:700;color:{INK}">{t}</span>'
            f'<span style="font-size:{small};color:{SUBINK}">{m}</span></div>'
            + (f'<div style="font-size:{small};color:{SUBINK};line-height:0.9">{s}</div>' if sub else '')
            + '</div></div>')


def footer_html(title, date, author):
    style = f'font:{FOOT_PT}pt {FONT_CSS};color:{FOOTINK};width:100%;padding:0 {MARGIN}mm;position:relative;'
    return (f'<div style="{style}"><span>{html.escape(title)}</span>'
            f'<span style="position:absolute;left:0;right:0;text-align:center;color:{AUTHINK}">{html.escape(author)}</span>'
            f'<span style="float:right">{html.escape(date)} · с. <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


# ------------------------------------------------------------------ matplotlib (ескізи деталей)
def mpl_setup():
    import matplotlib
    matplotlib.rcParams['font.family'] = FONT_MPL


def _fig_mm(fig):
    w, h = fig.get_size_inches()
    return w * 25.4, h * 25.4


def mpl_header(fig, title, meta, sub=''):
    """Шапка аркуша matplotlib. Повертає y (частка висоти) під лінією — звідти можна писати далі."""
    from matplotlib.lines import Line2D
    W, H = _fig_mm(fig)
    X = lambda mm: mm / W
    Y = lambda mm_from_top: 1 - mm_from_top / H
    fig.text(X(MARGIN), Y(MARGIN + TITLE_Y), title, fontsize=TITLE / MM_PER_PT, weight='bold', color=INK, va='baseline')
    fig.text(X(W - MARGIN), Y(MARGIN + TITLE_Y), meta, fontsize=SMALL / MM_PER_PT, color=SUBINK, ha='right', va='baseline')
    if sub:
        fig.text(X(MARGIN), Y(MARGIN + SUB_Y), sub, fontsize=SMALL / MM_PER_PT, color=SUBINK, va='baseline')
    y = Y(MARGIN + RULE_Y)
    fig.add_artist(Line2D([X(MARGIN), X(W - MARGIN)], [y, y], lw=RULE_W / MM_PER_PT, color=INK, solid_capstyle='butt'))
    return Y(MARGIN + HEAD_H + 2)


def mpl_footer(fig, title, date, author, n, total):
    W, H = _fig_mm(fig)
    y = FOOT_Y / H
    kw = dict(fontsize=FOOT_PT, va='baseline')
    fig.text(MARGIN / W, y, title, color=FOOTINK, **kw)
    fig.text(0.5, y, author, color=AUTHINK, ha='center', **kw)
    fig.text(1 - MARGIN / W, y, f'{date} · с. {n} / {total}', color=FOOTINK, ha='right', **kw)
