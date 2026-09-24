// =============================================================================
//  Міні-екскаватор: КОЖЕН компонент окремо — так, як його ріжуть з металу
//  перед зварюванням. Друкується й склеюється як конструктор.
//
//  Відмінність від замороженого набору print3d_deprecated/: там друкувалися ЗВАРНІ вузли (стріла одним
//  тілом). Тут — труби, пластини, накладки, сідла, ребра, втулки, пальці окремо.
//
//  Модель НЕ змінюється: цей файл підключає scad/excavator_boom.scad як бібліотеку
//  (part="none") і дістає компоненти її ж механізмом $sel/$one.
//
//  Запуск завжди через make.sh:
//      openscad -o x.stl -D 'part="none"' -D 'pp="gusset"' -D 'own="boom"' parts.scad
// =============================================================================
include <../scad/excavator_boom.scad>

// Невдалий include НЕ помилка: всі модулі стають порожні, STL виходить валідним
// і порожнім, і жодна числова перевірка цього не бачить.
assert(!is_undef(boom_tube_h) && !is_undef(bush_od_main), "scad/excavator_boom.scad не підключився");

/* [Друк] */
// Масштаб 1:SC. 5 — найбільший цілий, за якого найдовша труба (рукоять, 1050 мм)
// влазить у 250 мм: 210 мм. 1:4 дало б 262.5 мм.
SC = 5;
NOZZLE = 0.4;
// Діаметральний зазор палець↔отвір, ДРУКОВАНІ мм — знімається з пальця,
// щоб не чіпати жодного отвору в моделі
FIT_PIN = 0.40;
// Шток у гільзі циліндра, друковані мм — циліндр має лишатися рухомим
FIT_SLIDE = 0.35;
// Голівка пальця, друковані мм
PIN_HEAD_D = 1.6;
PIN_HEAD_H = 1.0;

/* [Hidden] */
pp = "none";     // ключ компонента
own = "";        // вузол-власник; порожньо = компонент будується тут
ori = "y";       // яка вісь МОДЕЛІ дивиться вгору на столі: x, y, z (raw = без повороту, для обміру)
pre = 0;         // попередній поворот навколо Y моделі, ° — для деталей, нахилених у вузлі
eps = 0.01;
function P(x) = x * SC;          // друковані мм → мм моделі

// Бренд на деталях — після SC: таблиця місць у brand.scad рахує z граней через нього.
include <brand.scad>
assert(!is_undef(brand_marks), "print3d-parts/brand.scad не підключився");

// Орієнтація на столі: деталь кладеться найменшим розміром догори.
//
// Єдиного правила «Y догори» НЕ досить, хоча всі осі шарнірів паралельні Y.
// Пластини вузлів справді мають товщину вздовж Y (`plate_xz(pts, t, y0)`), а от смуги
// зі списку BOM_STRIPS задані тим самим модулем, але з t = ШИРИНА деталі: у сідла H
// «товщина» 60 мм — це його ширина, а справжні 10 мм лежать у профілі. З «Y догори»
// така смуга стає на ребро (bk_top виходив 1.6 × 34 × 60 — лезо, яке впаде зі столу).
// Тому вісь задається на деталь, у parts.tsv, і звірена обміром кожної з них.
// Частина деталей до того ж стоїть у вузлі під кутом: ніж ковша, сідло D, ребро п'яти,
// накладка перелому, зуб. Їх жодна з трьох осей не кладе плазом — ніж виходив баштою
// 60 мм заввишки на основі 15×15. Усі вони призматичні вздовж Y (складова Y найбільшої
// нормалі ≈ 0), тому поворот навколо Y кладе їхню найбільшу грань на стіл. Кут `pre`
// не підібраний на око: він порахований із нормалі цієї грані (див. README).
// Бренд (brand.scad) вирізається вже В КООРДИНАТАХ СТОЛУ, після укладання: так його
// положення задається друкованими мм по STL, а модель і решта обгортки не знають про нього.
module lay() {
    difference() {
        scale(1/SC)
            if      (ori == "y") rotate([90, 0, 0]) rotate([0, pre, 0]) children();   // +Y моделі → +Z столу
            else if (ori == "x") rotate([0, -90, 0]) rotate([0, pre, 0]) children();  // +X моделі → +Z столу
            else rotate([0, pre, 0]) children();                                       // z або raw: як у моделі
        brand_cut(pp);
    }
}

// -----------------------------------------------------------------------------
//  Компоненти, яких у моделі немає окремими модулями
// -----------------------------------------------------------------------------
// Палець. Увесь зазор з'єднання — тут, тому жоден отвір у вузлах не переробляється.
// Палець будується вздовж +Z і друкується стоячи (ori = "z"): так його діаметр
// виходить круглим, а голівка дає і зчеплення зі столом, і упор у з'єднанні.
module make_pin(d, len) {
    dp = d - P(FIT_PIN);
    assert(dp > 0, "палець тонший за зазор");
    cylinder(d = dp, h = len, center = true, $fn = 64);
    translate([0, 0, -len/2]) cylinder(d = dp + P(PIN_HEAD_D), h = P(PIN_HEAD_H), center = true, $fn = 64);
}
// Кільце (втулка, бобишка, розпірка, шайба) — вісь уздовж Y, як у module bushing моделі.
//
// Круглі деталі НЕ дістаються через $sel, хоч і могли б: у тяги `link_boss` стоїть у
// подвійному циклі `for (s = sides()) for (P = [J, Q])`, і $one прибирає лише дзеркало —
// лишаються ДВІ бобишки в різних місцях замість однієї. Тому всі кільця будуються тут
// із тих самих виразів, що й у моделі; числа збігаються з її echo(BOM_ROUND).
module make_ring(od, id, len) {
    rotate([90, 0, 0]) difference() {
        cylinder(d = od, h = len, center = true, $fn = 96);
        cylinder(d = id, h = len + 2, center = true, $fn = 96);
    }
}
// Плита колони — post_schematic() без пальців A і C (вони друкуються окремо)
module make_post_plate() {
    rotate([90, 0, 0]) difference() {
        hull() {
            cylinder(d = 110, h = 12, center = true, $fn = 96);
            translate([C_w[0], C_w[1], 0]) cylinder(d = 90, h = 12, center = true, $fn = 96);
            translate([0, C_w[1] - 150, 0]) cylinder(d = 110, h = 12, center = true, $fn = 96);
        }
        cylinder(d = pin_A, h = 20, center = true, $fn = 96);
        translate([C_w[0], C_w[1], 0]) cylinder(d = boom_cyl_pin, h = 20, center = true, $fn = 96);
    }
}
// Гідроциліндр: у моделі корпус суцільний. Тут у ньому глухий канал під шток.
//   корпус займає X ∈ [eye_len, eye_len + body_L], body_L = closed - 2*eye_len - 30
//   зведений циліндр заганяє шток на (stroke + 20) — звідси глибина stroke + 40
module make_cyl_body(bore, rod, closed, stroke, pin, wall = 5, eye_len = 45) {
    body_L = closed - 2*eye_len - 30;
    depth  = stroke + 40;
    assert(depth < body_L - 20, "канал під шток глибший за гільзу");
    difference() {
        hyd_cyl_part("body", bore, rod, closed, stroke, pin, wall, eye_len);
        translate([eye_len + body_L - depth, 0, 0]) rotate([0, 90, 0])
            cylinder(d = rod + P(FIT_SLIDE), h = depth + eps, $fn = 96);
    }
}

// -----------------------------------------------------------------------------
//  Вибір компонента
// -----------------------------------------------------------------------------
// own != "" — компонент дістається з вузла механізмом самої моделі:
// $sel лишає одну деталь, $one — одну з дзеркальної пари.
module from_assembly() { $sel = pp; $one = true; part_by_name(own); }

if (own != "") lay() from_assembly();

// Труби — у власній системі, віссю вздовж +X (як для розгорток ескізів)
else if (pp == "tube_boom_seg1") lay() tube_local("boom_seg1");
else if (pp == "tube_boom_seg2") lay() tube_local("boom_seg2");
else if (pp == "tube_stick")     lay() tube_local("stick");

else if (pp == "post_plate")     lay() make_post_plate();

// Круглі. Розміри — ті самі вирази, що в моделі; звірено з її echo(BOM_ROUND).
else if (pp == "A_bushing")   lay() make_ring(bush_od_main,     pin_A,        boom_foot_boss_len);
else if (pp == "B_bushing")   lay() make_ring(bush_od_main,     pin_B,        stick_pack_w);
else if (pp == "E_bushing")   lay() make_ring(bushE_od,         pin_E,        stick_tube_w + 2*plate_boss);
else if (pp == "R_bushing")   lay() make_ring(bush_od_small,    pin_R,        stick_tube_w + 2*plate_boss);
else if (pp == "G_boss")      lay() make_ring(stick_cyl_pin + 14, stick_cyl_pin + 0.5, (stick_tube_w - clevis_gap_25)/2);
else if (pp == "J_boss")      lay() make_ring(pin_JQ + 16,      pin_JQ + 0.5, (link_w_in - clevis_gap_25)/2);
else if (pp == "link_boss")   lay() make_ring(link_boss_od,     pin_JQ + 0.5, link_boss_len);
else if (pp == "bk_boss_E")   lay() make_ring(bucket_boss_E_od, pin_E + 0.5,  bucket_boss_E_len);
else if (pp == "bk_spacer_Q") lay() make_ring(bush_od_small,    pin_JQ + 0.5, link_w_in);
else if (pp == "washer_B")    lay() make_ring(bush_od_main + 10, pin_B + 0.5, (boom_tube_w - stick_pack_w)/2);

else if (pp == "cyl_boom_body")   lay() make_cyl_body(boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
else if (pp == "cyl_boom_rod")    lay() hyd_cyl_part("rod", boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
else if (pp == "cyl_stick_body")  lay() make_cyl_body(stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
else if (pp == "cyl_stick_rod")   lay() hyd_cyl_part("rod", stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
else if (pp == "cyl_bucket_body") lay() make_cyl_body(bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
else if (pp == "cyl_bucket_rod")  lay() hyd_cyl_part("rod", bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);

// Пальці. Довжини — ті самі формули, що в assembly() і post_schematic();
// збігаються з echo(BOM_PINS) моделі.
else if (pp == "pin_A") lay() make_pin(pin_A,          boom_foot_boss_len + 2 + 40);
// УВАГА: рядок "pin_CD, 2 шт, Ø30×74" в echo(BOM_PINS) НЕПРАВИЛЬНИЙ — C і D різні.
// C тримає базу циліндра стріли в плитах колони (post_schematic(): pin(C, …, w + 40),
// w = boom_foot_boss_len + 2), тобто він такий самий, як A: 182. D — 74.
else if (pp == "pin_C") lay() make_pin(boom_cyl_pin,   boom_foot_boss_len + 2 + 40);
else if (pp == "pin_B") lay() make_pin(pin_B,          boom_tube_w + 2*plate_clevis + 24);
else if (pp == "pin_D") lay() make_pin(boom_cyl_pin,   clevis_gap_30 + 2*plate_clevis + 20);
else if (pp == "pin_E") lay() make_pin(pin_E,          pin_E_len);
else if (pp == "pin_F") lay() make_pin(stick_cyl_pin,  clevis_gap_25 + 2*plate_clevis + 20);
else if (pp == "pin_G") lay() make_pin(stick_cyl_pin,  stick_pack_w + 20);
else if (pp == "pin_H") lay() make_pin(bucket_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20);
else if (pp == "pin_J") lay() make_pin(pin_JQ,         pin_JQ_len);
else if (pp == "pin_Q") lay() make_pin(pin_JQ,         pin_JQ_len);
else if (pp == "pin_R") lay() make_pin(pin_R,          link_w_in + 20);

else if (pp == "none") {
    echo(str("=== друк компонентів 1:", SC, ", сопло ", NOZZLE, " мм"));
    echo(str("--- найтонше (дві лінії = ", 2*NOZZLE, " мм):"));
    echo(str("    стінка труби ", boom_tube_t, " → ", boom_tube_t/SC));
    echo(str("    обичайка ковша ", bucket_shell_t, " → ", bucket_shell_t/SC));
    echo(str("    боковина ковша ", bucket_side_t, " → ", bucket_side_t/SC));
    echo(str("    щока ", plate_gusset, " → ", plate_gusset/SC, "; накладка ", plate_boss, " → ", plate_boss/SC, "; вилка ", plate_clevis, " → ", plate_clevis/SC));
    echo(str("    шайба осі B ", (boom_tube_w - stick_pack_w)/2, " → ", (boom_tube_w - stick_pack_w)/2/SC));
    echo(str("--- пальці: Ø30 → ", 30/SC - FIT_PIN, ", Ø25 → ", 25/SC - FIT_PIN));
    echo(str("--- канал гільзи: стріли ", (boom_cyl_rod + P(FIT_SLIDE))/SC, ", решта ", (stick_cyl_rod + P(FIT_SLIDE))/SC));
    if (boom_tube_t/SC < 2*NOZZLE) echo(str("WARNING: стінка труби ", boom_tube_t/SC, " мм < двох ліній"));
    if (bucket_shell_t/SC < 2*NOZZLE) echo(str("WARNING: обичайка ковша ", bucket_shell_t/SC, " мм < двох ліній"));
    if ((boom_tube_w - stick_pack_w)/2/SC < NOZZLE) echo(str("WARNING: шайба осі B ", (boom_tube_w - stick_pack_w)/2/SC, " мм < сопла — не друкується"));

// Прив'язки накладних деталей рахує make_pos_drawing.py — обміром контурів,
    // а не з цих виразів: слід деталі на базі не збігається з габаритом її контуру.

}
else echo(str("!!! невідомий компонент: ", pp, " (own=", own, ")"));
