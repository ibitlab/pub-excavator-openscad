#!/usr/bin/env bash
# BOM + DXF 1:1 + PDF-ескізи всіх деталей. Використання: tools/bom_drawings.sh [--out ТЕКА]   (за замовчуванням build/)
set -e
cd "$(dirname "$0")/.."
if [ ! -x tools/.venv/bin/python ]; then
  echo "== створюю tools/.venv (tools/requirements.txt)"; python3 -m venv tools/.venv; tools/.venv/bin/python -m pip install --quiet -r tools/requirements.txt
fi
tools/.venv/bin/python tools/bom_drawings.py "$@"
