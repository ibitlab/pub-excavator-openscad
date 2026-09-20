#!/usr/bin/env bash
# macOS: 3DconnexionHelper відкриває SpaceMouse МОНОПОЛЬНО (IOHID seize), тому Chrome/WebHID отримує «Failed to open the device».
# Цей скрипт тимчасово вимикає/вмикає помічник драйвера. Системне розширення com.3dconnexion.driver не чіпається; після
# перезавантаження або входу в систему помічник стартує сам (LaunchAgent com.3dconnexion.helper, RunAtLoad).
#   tools/spacemouse-driver.sh status   — хто зараз тримає мишу
#   tools/spacemouse-driver.sh off      — закрити помічник → миша вільна для браузера (CAD-програми її на цей час не бачать)
#   tools/spacemouse-driver.sh on       — запустити помічник знову
# Автоматично (вимкнути на час роботи сервера і повернути після виходу): tools/with-spacemouse.sh <команда>, npm run preview:sm
[ "$(uname)" = "Darwin" ] || { echo "лише для macOS"; exit 1; }
holders() { ioreg -l -w 0 | awk '/"Product" = "Space(Mouse|Navigator|Pilot)/{f=1;c=0} f{c++; if ($0 ~ /IOUserClientCreator/) print "  тримає: " $0; if (c>60) exit}' | sed 's/.*"IOUserClientCreator" = //' | sort -u | sed 's/^/  відкрито процесом: /'; }
case "${1:-status}" in
  off) osascript -e 'quit app "3DconnexionHelper"' 2>/dev/null; sleep 1; pkill -x 3DconnexionHelper 2>/dev/null; pkill -x 3DxRadialMenu 2>/dev/null; pkill -x 3DxVirtualNumpad 2>/dev/null
       echo "помічник 3Dconnexion закрито — у сторінці натисніть кнопку SpaceMouse ще раз"; holders ;;
  on)  open /Applications/3DconnexionHelper.app && echo "помічник 3Dconnexion запущено" ;;
  *)   pgrep -lf 3DconnexionHelper >/dev/null && echo "3DconnexionHelper ПРАЦЮЄ (тримає мишу монопольно → WebHID у Chrome не відкриє пристрій)" || echo "3DconnexionHelper не запущено — миша вільна для браузера"; holders ;;
esac
