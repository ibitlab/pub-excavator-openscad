#!/usr/bin/env python3
"""Рядок авторства для згенерованих документів — з одного місця.

Джерело — перший рядок файлу `AUTHORS` у корені репозиторію («Ihor Ivaniuk · @ibitlab»).
Кожен генератор (BOM, аркуші, ескізи, звіти версії) ставить його дрібно
внизу: у Markdown — `<sub>` після лінійки, у PDF — по центру колонтитула, на
картинках — сірим у правому нижньому куті. Не гучно, але на кожному документі.

    from author import line, md_footer, credit
    print(md_footer())                      # Markdown
    credit(fig)                             # matplotlib-фігура перед savefig
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = 'Ihor Ivaniuk · @ibitlab'


def line():
    try:
        with open(os.path.join(ROOT, 'AUTHORS'), encoding='utf-8') as f:
            return f.readline().strip() or DEFAULT
    except OSError:
        return DEFAULT


def md_footer():
    return f'\n---\n<sub>{line()}</sub>\n'


def credit(fig, x=0.992, y=0.006):
    """Дрібний сірий підпис у правому нижньому куті фігури matplotlib."""
    fig.text(x, y, line(), fontsize=7, color='0.5', ha='right', va='bottom')
