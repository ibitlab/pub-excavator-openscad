#!/usr/bin/env bash
# BOM + DXF 1:1 + PDF-ескізи всіх деталей. Використання: tools/bom_drawings.sh [--out ТЕКА]   (за замовчуванням build/)
set -e
cd "$(dirname "$0")/.."
if [ ! -x tools/.venv/bin/python ]; then
  echo "== створюю tools/.venv (matplotlib для PDF)"; python3 -m venv tools/.venv; tools/.venv/bin/pip install --quiet matplotlib shapely
fi
tools/.venv/bin/python tools/bom_drawings.py "$@"
