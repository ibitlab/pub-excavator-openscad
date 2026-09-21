#!/usr/bin/env bash
# Друга версія 3D-перегляду: усе в браузері (OpenSCAD-WASM у веб-воркері + three.js), без бекенду.
# Використання: tools/viewer-wasm.sh          — dev-сервер Vite (правка .scad перезавантажує сторінку)
#               tools/viewer-wasm.sh build    — статичний сайт у tools/viewer-wasm/dist/ (будь-який статичний хостинг)
#               tools/viewer-wasm.sh preview  — переглянути зібраний dist/ локально
#               tools/viewer-wasm.sh phone    — те саме, але видно з телефона в тій же Wi-Fi
#               tools/viewer-wasm.sh test     — димовий тест без браузера
#
# ЧОМУ ОКРЕМИЙ РЕЖИМ ДЛЯ ТЕЛЕФОНА. Vite (і dev, і preview) слухає лише 127.0.0.1,
# тож із телефона сторінка просто не відкриється — це не потребує налаштування
# сервера, потрібен прапорець --host. Він відкриває сторінку всій локальній мережі:
# сайт статичний, бекенду й даних тут немає, але в чужій мережі краще не тримати.
# Серверна сторінка (tools/viewer.sh) лишається прив'язаною до 127.0.0.1 навмисно.
cd "$(dirname "$0")/viewer-wasm"
command -v npm >/dev/null || { echo "потрібен Node.js ≥ 20.19 (npm)"; exit 1; }
[ -d node_modules ] || npm install
case "${1:-dev}" in
  build)   npm run build ;;
  preview) npm run build && npm run preview ;;
  phone)   npm run build
           ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
                || hostname -I 2>/dev/null | awk '{print $1}')
           echo "  на телефоні (та сама Wi-Fi): http://${ip:-АДРЕСА-ЦЬОГО-КОМПʼЮТЕРА}:8767/"
           npx vite preview --host --port 8767 --strictPort ;;
  test)    npm test ;;
  *)       npm run dev ;;
esac
