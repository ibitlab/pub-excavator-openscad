#!/usr/bin/env bash
# Перевірка РУХОМИХ пар на зіткнення: вузли ставляться у світову систему при заданих кутах (part="collide"),
# рахується об'єм перетину (см³), допуск 0.05 см³. Кути поза межами модель сама обмежує ходом циліндра, тому
# -90 і 200 дають рівно крайні положення. Три проходи: хід циліндра ковша, рукояті, стріли.
# Остання частина довідкова (не зупиняє збирання): ківш × стріла та ківш × циліндр стріли при складеній рукояті.
cd "$(dirname "$0")/.."
SCAD=scad/excavator_boom.scad; TMP=$(mktemp -d); bad=0
vol() { # a b boom_angle stick_angle bucket_angle
  local f="$TMP/x.stl"; rm -f "$f"
  openscad -o "$f" --export-format binstl -D 'part="collide"' -D "ov_a=\"$1\"" -D "ov_b=\"$2\"" -D "boom_angle=$3" -D "stick_angle=$4" -D "bucket_angle=$5" "$SCAD" >/dev/null 2>&1
  if [ -s "$f" ]; then python3 tools/stl_volume.py "$f"; else echo 0.000; fi
}
sweep() { # назва_параметра "кути" "пари"
  local what=$1 angles=$2 pairs=$3 pr a b v worst at x
  for pr in $pairs; do
    a=${pr%%:*}; b=${pr##*:}; worst=0.000; at=""
    for x in $angles; do
      case $what in bucket) v=$(vol "$a" "$b" 10 100 "$x") ;; stick) v=$(vol "$a" "$b" 10 "$x" 60) ;; boom) v=$(vol "$a" "$b" "$x" 100 60) ;; esac
      if python3 -c "import sys; sys.exit(0 if float('$v') > float('$worst') else 1)"; then worst=$v; at=$x; fi
    done
    if python3 -c "import sys; sys.exit(0 if float('$worst') > 0.05 else 1)"; then echo "ЗІТКНЕННЯ  $a × $b : до $worst см³ (кут $what = ${at}°)"; bad=1
    else echo "ok          $a × $b : 0 на всьому ході ($what, $(echo $angles | wc -w | tr -d ' ') положень)"; fi
  done
}
sweep bucket "-90 -10 0 15 30 45 60 75 90 105 120 130 200" "m_bucket:m_stick m_bucket:m_rocker m_bucket:m_link m_bucket:m_bcyl m_link:m_stick m_rocker:m_stick m_link:m_rocker m_bcyl:m_stick m_bcyl:m_rocker"
sweep stick  "0 60 70 80 90 100 110 120 130 140 150 200" "m_scyl:m_boom m_scyl:m_stick m_stick:m_boom"
sweep boom   "-90 -30 -15 0 15 30 45 90" "m_bmcyl:m_boom"
echo "-- довідково: ківш × стріла / циліндр стріли при складеній рукояті, см³ перетину (0 = не дістає; >0 — у цій позі не підкручувати ківш до упору)"
for psi in 0 60 70 80; do
  line="   рукоять $( [ $psi = 0 ] && echo 'складена до упору' || echo "${psi}°"):"
  for om in 200 110 80 40; do v=$(vol m_bucket m_boom 10 "$psi" "$om"); v2=$(vol m_bucket m_bmcyl 10 "$psi" "$om"); line="$line  ківш $( [ $om = 200 ] && echo max || echo "${om}°" ) → стріла $v / циліндр стріли $v2;"; done
  echo "$line"
done
rm -rf "$TMP"; [ $bad -eq 0 ] && echo "РЕЗУЛЬТАТ: рухомі пари не зіткаються" || echo "РЕЗУЛЬТАТ: є зіткнення рухомих пар — див. вище"
exit $bad
