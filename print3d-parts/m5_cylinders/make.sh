#!/usr/bin/env bash
# Циліндри моделі на шпильці M5 і моторедукторі N20: перевірки, STL, рендери, CALC.md, схема підключення.
#
#   print3d-parts/m5_cylinders/make.sh                        # усе → build/m5_cylinders/
#   print3d-parts/m5_cylinders/make.sh --out ТЕКА --kit-stl ТЕКА   # так кличе print3d-parts/make.sh
#   print3d-parts/m5_cylinders/make.sh pairs collide          # лише вибрані кроки
#   PHIS="0 90 -90 180" ALL=1 …/make.sh collide              # перебрати кути мотора (без ALL — до першого чистого)
#
# Кроки: pairs — власні деталі не перетинаються (у двох крайніх положеннях штока);
#        collide — новий циліндр без вушок не зачіпає машину (вушка ті самі, що в моделі);
#        stl — деталі на стіл + check_print.py набору; png — збірки й розрізи; calc — CALC.md;
#        wiring — схема підключення WIRING.svg.
# Перетин чи зіткнення зупиняє збирання (код 1) — і набір разом із ним.
set -u
OUT=""; KIT=""; STEPS=""
abs() { case "$1" in /*) echo "$1" ;; *) echo "$PWD/$1" ;; esac; }   # відносні — від того, звідки кличуть
while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT=$(abs "$2"); shift 2 ;;
        --kit-stl) KIT=$(abs "$2"); shift 2 ;;
        *) STEPS="$STEPS $1"; shift ;;
    esac
done
cd "$(dirname "$0")" || exit 1
ROOT=../..
OUT=${OUT:-$PWD/$ROOT/build/m5_cylinders}
STEPS=${STEPS:-pairs collide stl png calc wiring}
mkdir -p "$OUT"
TMP=$(mktemp -d)
vol() { if [ -s "$1" ]; then python3 $ROOT/tools/stl_volume.py "$1"; else echo 0.000; fi; }   # см³
big() { python3 -c "import sys; sys.exit(0 if float('$1') > float('$2') else 1)"; }
# Порожній перетин OpenSCAD віддає кодом 1 з «Current top level object is empty» і без файлу — це «чисто».
# Але він же зрідка падає (segfault, код 139) теж без файлу — і таке не можна мовчки прийняти за «чисто»:
# усе, крім порожнього результату, — до трьох спроб, далі помилка збирання.
scad() {   # scad <вихід.stl> <аргументи openscad…>
    local out=$1 try rc; shift
    for try in 1 2 3; do
        rm -f "$out"
        openscad -o "$out" --export-format binstl "$@" m5_cyl.scad >/dev/null 2>"$TMP/scad_err.txt"; rc=$?
        [ $rc -eq 0 ] && return 0
        [ $rc -eq 1 ] && grep -q 'top level object is empty' "$TMP/scad_err.txt" \
            && ! grep -qE 'ERROR|Assertion' "$TMP/scad_err.txt" && return 0
        echo "  (openscad упав, код $rc, спроба $try: $*)" >&2
    done
    echo "  ПОМИЛКА: openscad не відпрацював тричі — $*"; bad=1; return 1
}
CYLS="boom stick bucket"
# shellcheck disable=SC2034  # читаються непрямо: v=STROKE_$c; S=${!v}
STROKE_boom=100 STROKE_stick=80 STROKE_bucket=60
bad=0

case " $STEPS " in *" pairs "*)
echo "== перетини власних деталей (допуск 0.0005 см³)"
# пари, що мають лише торкатися; шпилька у вушку й поршні — у натяг навмисно (нарізає PLA), не перевіряється
PAIRS="tube:head_rear head_rear:head_front gear:head_rear gear:head_front pinion:head_rear pinion:head_front pinion:gear
motor:tube motor:head_rear motor:pinion puck:tube screw:gear screw:head_front screw:head_rear bearing:head_rear
bearing:gear nut:gear cap:tube halls:tube halls:head_front halls:cap magnets:gear magnets:puck eye:head_front"
for c in $CYLS; do
    v=STROKE_$c; S=${!v}
    for e in 0 $S; do
        for pr in $PAIRS; do
            a=${pr%%:*}; b=${pr##*:}; f=$TMP/p.stl
            scad "$f" -D "cyl=\"$c\"" -D 'pp="pair"' -D "pa=\"$a\"" -D "pb=\"$b\"" -D "ext=$e" || continue
            v=$(vol "$f")
            if big "$v" 0.0005; then echo "  ПЕРЕТИН $c ext=$e: $a × $b = $v см³"; bad=1; fi
        done
    done
    echo "  $c: $(echo "$PAIRS" | wc -w | tr -d ' ') пар × 2 положення штока"
done
;; esac

case " $STEPS " in *" collide "*)
echo "== зіткнення з машиною (новий циліндр без вушок × вузол, см³ у мірі машини; допуск 0.05)"
for c in $CYLS; do
    case $c in
        boom)   with="m_boom m_post";                    sweep=boom;   angles="-90 -30 0 30 90" ;;
        stick)  with="m_boom m_stick";                   sweep=stick;  angles="0 70 100 130 200" ;;
        bucket) with="m_stick m_rocker m_link m_bucket"; sweep=bucket; angles="-90 0 45 90 130 200" ;;
    esac
    for phi in ${PHIS:-model}; do
        worst=0; at=""
        [ "$phi" = model ] && PD="" || PD="MOTOR_PHI=[$phi,$phi,$phi]"
        for x in $angles; do
            case $sweep in boom)   A="-D boom_angle=$x -D stick_angle=100 -D bucket_angle=60" ;;
                           stick)  A="-D boom_angle=10 -D stick_angle=$x -D bucket_angle=60" ;;
                           bucket) A="-D boom_angle=10 -D stick_angle=100 -D bucket_angle=$x" ;; esac
            for w in $with; do
                f=$TMP/c.stl
                # shellcheck disable=SC2086  # $A — набір прапорців -D, розбиття навмисне
                scad "$f" -D "cyl=\"$c\"" -D 'pp="collide"' -D "with=\"$w\"" ${PD:+-D "$PD"} $A || continue
                v=$(vol "$f")
                # bash 3.2: змінна перед «°» чи кирилицею — лише в ${…}, інакше значення тихо зникає
                if big "$v" "$worst"; then worst=$v; at="$w @ ${x}°"; fi
            done
        done
        label=$([ "$phi" = model ] && echo "мотор як у m5_cyl.scad" || echo "мотор ${phi}°")
        if big "$worst" 0.05; then
            echo "  $c, $label: зіткнення до $worst см³ ($at)"; [ "$phi" = model ] && bad=1
        else echo "  $c, $label: чисто ($(echo "$angles" | wc -w | tr -d ' ') положень × $(echo "$with" | wc -w | tr -d ' ') вузли)"; [ -n "${ALL:-}" ] || break; fi
    done
done
;; esac

case " $STEPS " in *" stl "*)
echo "== STL і друкованість"
mkdir -p "$OUT/stl"; rm -f "$OUT"/stl/*.stl
for c in $CYLS; do
    for p in tube head_rear head_front gear pinion puck cap eye; do
        f="$OUT/stl/${c}_${p}_x1.stl"
        openscad -o "$f" --export-format binstl -D "cyl=\"$c\"" -D "pp=\"$p\"" m5_cyl.scad >/dev/null 2>"$TMP/err.txt" \
            || { echo "  ПОМИЛКА рендера: $c $p"; cat "$TMP/err.txt"; bad=1; }
        [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній"; bad=1; }
    done
done
echo "  файлів: $(ls "$OUT"/stl/*.stl | wc -l | tr -d ' ')"
python3 ../check_print.py "$OUT"/stl/*.stl --bed 250 --angle 45 | grep -vE '^\s+увага' || true
;; esac

case " $STEPS " in *" png "*)
echo "== рендери"
mkdir -p "$OUT/img"; rm -f "$OUT"/img/*.png
for c in $CYLS; do
    v=STROKE_$c; S=${!v}
    openscad -o "$OUT/img/${c}_closed.png" --imgsize=1400,700 --viewall --autocenter --colorscheme=Tomorrow -D "cyl=\"$c\"" -D 'pp="asm"' -D ext=0 --camera=0,0,0,60,0,25,0 m5_cyl.scad >/dev/null 2>&1
    openscad -o "$OUT/img/${c}_open.png"   --imgsize=1400,700 --viewall --autocenter --colorscheme=Tomorrow -D "cyl=\"$c\"" -D 'pp="asm"' -D "ext=$S" --camera=0,0,0,60,0,25,0 m5_cyl.scad >/dev/null 2>&1
    # розрізи — повним рендером: у прев'ю площина розрізу бере колір не деталі, а того, що вирізає
    openscad --render -o "$OUT/img/${c}_cut.png"  --imgsize=1400,700 --viewall --autocenter --colorscheme=Tomorrow -D "cyl=\"$c\"" -D 'pp="cut"' -D "ext=$((S/2))" --camera=0,0,0,90,0,0,0 m5_cyl.scad >/dev/null 2>&1
    openscad --render -o "$OUT/img/${c}_head.png" --imgsize=1200,900 --colorscheme=Tomorrow -D "cyl=\"$c\"" -D 'pp="headcut"' -D "ext=$((S/2))" --camera=0,0,0,90,0,0,200 m5_cyl.scad >/dev/null 2>&1
done
python3 "$ROOT"/tools/trim_png.py --margin 3 "$OUT"/img/*.png >/dev/null
if python3 "$ROOT"/tools/trim_png.py --report "$OUT"/img/*.png | grep -iE 'порожн|ПОРОЖН'; then echo "  ПОМИЛКА: порожній рендер"; bad=1; fi
n=$(ls "$OUT"/img/*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" -eq 12 ]; then echo "  знімків: $n"; else echo "  ПОМИЛКА: знімків $n замість 12 (openscad упав?)"; bad=1; fi
;; esac

case " $STEPS " in *" calc "*)
echo "== розрахунок"
python3 calc.py ${KIT:+--kit-stl "$KIT"} --own-stl "$OUT/stl" --out "$OUT/CALC.md" || bad=1
;; esac

case " $STEPS " in *" wiring "*)
echo "== схема підключення"
python3 wiring.py --out "$OUT/WIRING.svg" || bad=1
;; esac

rm -rf "$TMP"
[ $bad -eq 0 ] && echo "  циліндри M5: без зауважень" || echo "  циліндри M5: є зауваження — див. вище"
exit $bad
