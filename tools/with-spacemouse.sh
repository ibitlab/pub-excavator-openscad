#!/usr/bin/env bash
# Запускає команду з вільною для браузера SpaceMouse (macOS): перед стартом закриває помічник драйвера 3Dconnexion,
# а коли команда завершиться з БУДЬ-ЯКОЇ причини (Ctrl+C, закриття термінала, помилка, звичайний вихід) — запускає його знову.
# Якщо помічник до старту не працював, після виходу він не запускається: повертається той стан, який був.
#   tools/with-spacemouse.sh tools/viewer.sh                 сторінка з сервером
#   cd tools/viewer-wasm && npm run preview:sm               WASM-сторінка (так само: npm run dev:sm)
# Не спрацює лише при kill -9 самого скрипта — тоді вручну: tools/spacemouse-driver.sh on
DRV="${SM_DRIVER:-$(cd "$(dirname "$0")" && pwd)/spacemouse-driver.sh}"
[ $# -gt 0 ] || { sed -n '2,7p' "$0"; exit 1; }
helper_running() { [ -n "$SM_FORCE" ] || pgrep -x 3DconnexionHelper >/dev/null; }
if [ "$(uname)" != "Darwin" ] || ! helper_running; then exec "$@"; fi      # не macOS або драйвер і так вимкнено — просто запускаємо
restore() { trap - EXIT INT TERM HUP; echo; "$DRV" on; }
trap restore EXIT; trap 'exit 130' INT; trap 'exit 143' TERM; trap 'exit 129' HUP
"$DRV" off
"$@"                                                           # на передньому плані: Ctrl+C отримують і команда, і цей скрипт; trap чекає її завершення
