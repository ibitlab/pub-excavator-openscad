#!/usr/bin/env bash
# Друга версія 3D-перегляду: усе в браузері (OpenSCAD-WASM у веб-воркері + three.js), без бекенду.
# Використання: web/viewer-wasm.sh          — dev-сервер Vite (правка .scad перезавантажує сторінку)
#               web/viewer-wasm.sh build    — статичний сайт у web/viewer-wasm/dist/ (будь-який статичний хостинг)
#               web/viewer-wasm.sh preview  — переглянути зібраний dist/ локально
#               web/viewer-wasm.sh phone    — те саме, але видно з телефона в тій же Wi-Fi
#               web/viewer-wasm.sh test     — димовий тест без браузера
#
# ЧОМУ ОКРЕМИЙ РЕЖИМ ДЛЯ ТЕЛЕФОНА. Vite (і dev, і preview) слухає лише 127.0.0.1,
# тож із телефона сторінка просто не відкриється — це не потребує налаштування
# сервера, потрібен прапорець --host. Він відкриває сторінку всій локальній мережі:
# сайт статичний, бекенду й даних тут немає, але в чужій мережі краще не тримати.
# Серверна сторінка (web/viewer.sh) лишається прив'язаною до 127.0.0.1 навмисно.
cd "$(dirname "$0")/viewer-wasm"
command -v npm >/dev/null || { echo "потрібен Node.js ≥ 20.19 (npm)"; exit 1; }
[ -d node_modules ] || npm install
case "${1:-dev}" in
  build)   npm run build ;;
  preview) npm run build && npm run preview ;;
  phone)   npm run build
           ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
                || hostname -I 2>/dev/null | awk '{print $1}')
           echo "  on the phone (same Wi-Fi): http://${ip:-THIS-COMPUTER-ADDRESS}:8767/"
           # WebXR (AR) працює лише в безпечному контексті, а це звичайний http у мережі
           echo "  AR: in Chrome on the phone open chrome://flags/#unsafely-treat-insecure-origin-as-secure"
           echo "      → http://${ip:-THIS-COMPUTER-ADDRESS}:8767 → Enabled → Relaunch (set back to Default after testing)"
           npx vite preview --host --port 8767 --strictPort ;;
  test)    npm test ;;
  *)       npm run dev ;;
esac
