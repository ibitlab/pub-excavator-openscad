#!/usr/bin/env bash
# Інтерактивний 3D-перегляд моделі в браузері: обертання/панорама/масштаб, кути — миттєво, решта параметрів — через OpenSCAD (≈0.4 с).
# Використання: tools/viewer.sh [--port 8765]          статична сторінка: python3 tools/viewer.py --export ФАЙЛ.html
cd "$(dirname "$0")/.."
command -v openscad >/dev/null || { echo "потрібен openscad у PATH"; exit 1; }
exec python3 tools/viewer.py --open "$@"
