#!/usr/bin/env bash
# Перевірка: вузли зварної конструкції мають прилягати, але НЕ перекриватися.
# Для кожної пари вузлів рахується об'єм перетину (см³); допуск 0.05 см³ (числовий шум на спільних гранях).
cd "$(dirname "$0")/.."
SCAD=scad/excavator_boom.scad; TMP=$(mktemp -d); bad=0
BOOM="boom_tubes boom_gussets boom_bracket_D boom_bracket_F boom_foot_boss boom_fork_B"
STICK="stick_tube stick_cheeks stick_bracket_H stick_tip"
BUCKET="bucket_sides bucket_shell bucket_top bucket_edge bucket_ears bucket_wear"
check() { # список вузлів
  local arr=($1) i j
  for ((i=0; i<${#arr[@]}; i++)); do for ((j=i+1; j<${#arr[@]}; j++)); do
    a=${arr[$i]}; b=${arr[$j]}; f="$TMP/$a-$b.stl"
    openscad -o "$f" -D 'part="overlap"' -D "ov_a=\"$a\"" -D "ov_b=\"$b\"" "$SCAD" >/dev/null 2>&1
    if [ -s "$f" ]; then v=$(python3 tools/stl_volume.py "$f"); else v=0.000; fi
    if python3 -c "import sys; sys.exit(0 if float('$v') > 0.05 else 1)"; then echo "ПЕРЕКРИТТЯ  $a × $b : $v см³"; bad=1; else echo "ok          $a × $b : $v см³"; fi
  done; done
}
# необов'язковий аргумент: boom | stick | bucket — перевірити лише одну групу
case "${1:-all}" in boom) check "$BOOM" ;; stick) check "$STICK" ;; bucket) check "$BUCKET" ;; *) check "$BOOM"; check "$STICK"; check "$BUCKET" ;; esac
rm -rf "$TMP"; [ $bad -eq 0 ] && echo "РЕЗУЛЬТАТ: перекриттів немає" || echo "РЕЗУЛЬТАТ: є перекриття — див. вище"
exit $bad
