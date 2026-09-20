#!/usr/bin/env bash
# Друга версія 3D-перегляду: усе в браузері (OpenSCAD-WASM у веб-воркері + three.js), без бекенду.
# Використання: tools/viewer-wasm.sh          — dev-сервер Vite (правка .scad перезавантажує сторінку)
#               tools/viewer-wasm.sh build    — статичний сайт у tools/viewer-wasm/dist/ (будь-який статичний хостинг)
#               tools/viewer-wasm.sh preview  — переглянути зібраний dist/ локально
#               tools/viewer-wasm.sh test     — димовий тест без браузера
cd "$(dirname "$0")/viewer-wasm"
command -v npm >/dev/null || { echo "потрібен Node.js ≥ 20.19 (npm)"; exit 1; }
[ -d node_modules ] || npm install
case "${1:-dev}" in build) npm run build ;; preview) npm run build && npm run preview ;; test) npm test ;; *) npm run dev ;; esac
