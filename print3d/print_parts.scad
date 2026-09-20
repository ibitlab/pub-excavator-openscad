// =============================================================================
//  Деталі міні-екскаватора, підготовані до друку на FDM-принтері.
//
//  Модель НЕ змінюється: цей файл підключає scad/excavator_boom.scad як бібліотеку
//  (part="none" → модель нічого не малює сама) і збирає з її модулів друковані деталі.
//
//  Запуск завжди через make.sh — він підставляє part="none" і потрібний pp.
//      openscad -o x.stl -D 'part="none"' -D 'pp="boom"' print3d/print_parts.scad
// =============================================================================
include <../scad/excavator_boom.scad>

// Підключення могло не спрацювати: тоді КОЖЕН модуль тихо порожній, а STL виходить
// валідним і порожнім (жодна числова перевірка цього не бачить).
assert(!is_undef(boom_tube_h) && !is_undef(bush_od_main), "scad/excavator_boom.scad не підключився");

/* [Друк] */
// Масштаб 1:SC. 7 — найбільший цілий, за якого стріла (1674.7 мм) влазить у 250 мм: 239.2 мм.
SC = 7;
// Діаметр сопла, мм — з нього рахуються межі тонких стінок у звіті
NOZZLE = 0.4;
// Діаметральний зазор палець↔отвір, ДРУКОВАНІ мм. Увесь зазор знімається з пальця,
// щоб не чіпати жодного отвору в моделі.
FIT_PIN = 0.40;
// Втулка у розточеному гнізді, друковані мм (менше — тугіше)
FIT_BUSH = 0.15;
// Шток у гільзі циліндра, друковані мм — має лишатися рухомим
FIT_SLIDE = 0.35;
// Голівка пальця: наскільки вона більша за палець і яка заввишки, друковані мм
PIN_HEAD_D = 1.6;
PIN_HEAD_H = 1.0;

/* [Hidden] */
// Яку деталь віддати. Список — у make.sh
pp = "none";
eps = 0.01;
// друковані мм → мм моделі (усередині scale(1/SC) все міряється в мм моделі)
function P(x) = x * SC;

// -----------------------------------------------------------------------------
//  Загальне: орієнтація на столі
// -----------------------------------------------------------------------------
// Усі вузли цієї моделі призматичні вздовж Y, а ВСІ осі шарнірів паралельні Y.
// Тому Y ставиться вертикально: кожен шар — той самий 2D-контур, отвори під пальці
// виходять круглими й вертикальними, пластини лягають горизонтально.
// Слайсер сам опускає деталь на стіл, тому нуль по Z тут не виставляється.
module lay() { scale(1/SC) rotate([90, 0, 0]) children(); }

// Циліндричний виріз з віссю вздовж Y (як у module bushing моделі)
module ybore(p, d, len) { translate(p) rotate([90, 0, 0]) cylinder(d = d, h = len, center = true, $fn = 96); }

// -----------------------------------------------------------------------------
//  Зварні вузли: з них вирізаються гнізда під окремо друковані втулки
// -----------------------------------------------------------------------------
// Втулки в моделі вже намальовані всередині вузлів. Щоб надрукувати їх окремо,
// гніздо розточується на Ø_зовн + зазор — рівно там, де стоїть втулка.
// Довжина вирізу береться з тієї ж формули, що й довжина втулки, плюс перебіг:
// виріз, що закінчується рівно на площині грані, лишає плівку нульової товщини.

module print_boom() {
    difference() {
        part_by_name("boom");
        ybore([0, 0, 0], bush_od_main + P(FIT_BUSH), boom_foot_boss_len + 1);   // гніздо втулки A
    }
}

module print_stick() {
    tip_len = stick_tube_w + 2*plate_boss;      // = довжина втулок E і R у stick_tip_bosses()
    difference() {
        part_by_name("stick");
        ybore([0, 0, 0],   bush_od_main  + P(FIT_BUSH), stick_pack_w + 1);      // гніздо втулки B
        ybore(p3(E_s),     bushE_od      + P(FIT_BUSH), tip_len + 1);           // гніздо втулки E
        ybore(p3(R_s),     bush_od_small + P(FIT_BUSH), tip_len + 1);           // гніздо втулки R
    }
}

// Ківш іде як є. Розпірна втулка Q за специфікацією моделі приварена до ОБОХ вух
// (BOM_ROUND: «приварити до обох вух»), тож окремою деталлю вона бути не може —
// вирізати її означало б лишити в наборі деталь, якій нема на чому триматися.
// Так само лишаються в вузлах приварні бобишки G, J, link_boss і bk_boss_E.
module print_bucket() { part_by_name("bucket"); }

// Коромисло й тяга — це ДВІ окремі пластини кожне (у машині їх тримають самі пальці).
// $one = true віддає одну з дзеркальної пари.
//
// ПАСТКА: у коромислі пластина й бобишка осі J розкладаються по РІЗНІ боки при $one.
// Пластина стає за y0 = s>0 ? w_out/2 : …, а бобишка — через rotate([90,0,0]) translate([0,0,s*…]),
// і цей поворот відправляє +Z у −Y. При s = +1 пластина лягає на +41…+51, бобишка на −41…−13.5:
// дві деталі, що не торкаються. У повній збірці це непомітно, бо є обидві сторони.
// Тому бобишка береться як є (−41…−13.5), а пластина дзеркалиться до −51…−41 — так вони
// стикуються І пластина опиняється знизу, тобто лягає на стіл усією площею.
module rocker_el(k) { $sel = k; $one = true; rocker_link_pts([0, 0], [rocker_L, 0], [0, 0], "rocker"); }
module print_rocker_plate() {
    mirror([0, 1, 0]) rocker_el("rocker_plate");
    rocker_el("J_boss");
}
// У тязі такої пастки немає: бобишки задані прямою координатою y, тож обидві на боці пластини,
// і пластина вже виходить нижньою — 0 % нависань, уся площа на столі.
module print_link_plate() { $one = true; rocker_link_pts([0, 0], [0, 0], [link_L, 0], "link"); }

// Плита колони. Повторює post_schematic() без пальців A і C — вони друкуються окремо.
// rotate([90,0,0]) — як у самій моделі: без нього плита стоїть на ребрі (товщина 1.7 мм
// виявляється горизонтальною, а деталь — 80 мм заввишки).
module print_post_plate() {
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

// -----------------------------------------------------------------------------
//  Гідроциліндри — робочі: шток ходить у гільзі
// -----------------------------------------------------------------------------
// У моделі корпус суцільний (вона показує машину, а не механізм друку). Тут у ньому
// свердлиться глухий канал під шток.
//   корпус займає X ∈ [eye_len, eye_len + body_L], body_L = closed - 2*eye_len - 30
//   шток входить із дальшого торця; при повністю зведеному циліндрі він заходить
//   на (rod_vis - 30) = (stroke + 20). Тому глибина каналу = stroke + 40.
function cyl_body_L(closed, eye_len) = closed - 2*eye_len - 30;
function cyl_bore_depth(stroke) = stroke + 40;

module print_cyl_body(bore, rod, closed, stroke, pin, wall = 5, eye_len = 45) {
    body_L = cyl_body_L(closed, eye_len);
    depth  = cyl_bore_depth(stroke);
    assert(depth < body_L - 20, "канал під шток глибший за гільзу — зменш stroke або перевір eye_len");
    difference() {
        hyd_cyl_part("body", bore, rod, closed, stroke, pin, wall, eye_len);
        translate([eye_len + body_L - depth, 0, 0]) rotate([0, 90, 0])
            cylinder(d = rod + P(FIT_SLIDE), h = depth + eps, $fn = 96);
    }
}
module print_cyl_rod(bore, rod, closed, stroke, pin, wall = 5, eye_len = 45) {
    hyd_cyl_part("rod", bore, rod, closed, stroke, pin, wall, eye_len);
}

// -----------------------------------------------------------------------------
//  Втулки й пальці
// -----------------------------------------------------------------------------
// Втулка друкується в номінал: зазор під палець уже закладений у сам палець.
module print_bush(od, id, len) {
    rotate([90, 0, 0]) difference() {
        cylinder(d = od, h = len, center = true, $fn = 96);
        cylinder(d = id, h = len + 2, center = true, $fn = 96);
    }
}

// Палець: вісь вертикально, голівка на столі. Увесь зазор у з'єднанні — тут,
// тому жоден отвір у вузлах не переробляється.
module print_pin(d, len) {
    dp = d - P(FIT_PIN);
    assert(dp > 0, "палець тонший за зазор");
    rotate([-90, 0, 0]) {                     // після lay() вісь пальця стане вертикальною
        cylinder(d = dp, h = len, center = true, $fn = 64);
        translate([0, 0, -len/2]) cylinder(d = dp + P(PIN_HEAD_D), h = P(PIN_HEAD_H), center = true, $fn = 64);
    }
}

// довжини пальців — ті самі формули, що у assembly() і post_schematic()
pin_len_A  = boom_foot_boss_len + 2 + 40;
pin_len_C  = pin_len_A;
pin_len_B  = boom_tube_w + 2*plate_clevis + 24;
pin_len_D  = clevis_gap_30 + 2*plate_clevis + 20;
pin_len_F  = clevis_gap_25 + 2*plate_clevis + 20;
pin_len_G  = stick_pack_w + 20;
pin_len_H  = clevis_gap_25 + 2*plate_clevis + 20;
pin_len_R  = link_w_in + 20;

// -----------------------------------------------------------------------------
//  Вибір деталі
// -----------------------------------------------------------------------------
if      (pp == "post_plate")      lay() print_post_plate();
else if (pp == "boom")            lay() print_boom();
else if (pp == "stick")           lay() print_stick();
else if (pp == "bucket")          lay() print_bucket();
else if (pp == "rocker_plate")    lay() print_rocker_plate();
else if (pp == "link_plate")      lay() print_link_plate();

else if (pp == "cyl_boom_body")   lay() print_cyl_body(boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
else if (pp == "cyl_boom_rod")    lay() print_cyl_rod (boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
else if (pp == "cyl_stick_body")  lay() print_cyl_body(stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
else if (pp == "cyl_stick_rod")   lay() print_cyl_rod (stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
else if (pp == "cyl_bucket_body") lay() print_cyl_body(bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
else if (pp == "cyl_bucket_rod")  lay() print_cyl_rod (bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);

else if (pp == "bush_A")          lay() print_bush(bush_od_main,  pin_A,  boom_foot_boss_len);
else if (pp == "bush_B")          lay() print_bush(bush_od_main,  pin_B,  stick_pack_w);
else if (pp == "bush_E")          lay() print_bush(bushE_od,      pin_E,  stick_tube_w + 2*plate_boss);
else if (pp == "bush_R")          lay() print_bush(bush_od_small, pin_R,  stick_tube_w + 2*plate_boss);

else if (pp == "pin_A")           lay() print_pin(pin_A,           pin_len_A);
else if (pp == "pin_C")           lay() print_pin(boom_cyl_pin,    pin_len_C);
else if (pp == "pin_B")           lay() print_pin(pin_B,           pin_len_B);
else if (pp == "pin_D")           lay() print_pin(boom_cyl_pin,    pin_len_D);
else if (pp == "pin_E")           lay() print_pin(pin_E,           pin_E_len);
else if (pp == "pin_F")           lay() print_pin(stick_cyl_pin,   pin_len_F);
else if (pp == "pin_G")           lay() print_pin(stick_cyl_pin,   pin_len_G);
else if (pp == "pin_H")           lay() print_pin(bucket_cyl_pin,  pin_len_H);
else if (pp == "pin_J")           lay() print_pin(pin_JQ,          pin_JQ_len);
else if (pp == "pin_Q")           lay() print_pin(pin_JQ,          pin_JQ_len);
else if (pp == "pin_R")           lay() print_pin(pin_R,           pin_len_R);

else if (pp == "none") {
    // Звіт: усе, що треба знати перед друком, у ДРУКОВАНИХ міліметрах.
    echo(str("=== друк 1:", SC, ", сопло ", NOZZLE, " мм"));
    echo(str("--- найтонші стінки (2 лінії = ", 2*NOZZLE, " мм):"));
    echo(str("    стінка труби стріли/рукояті ", boom_tube_t, " → ", boom_tube_t/SC));
    echo(str("    обичайка ковша ", bucket_shell_t, " → ", bucket_shell_t/SC));
    echo(str("    боковина ковша ", bucket_side_t, " → ", bucket_side_t/SC));
    echo(str("    щока/косинка ", plate_gusset, " → ", plate_gusset/SC));
    echo(str("    накладка ", plate_boss, " → ", plate_boss/SC));
    echo(str("    вилка ", plate_clevis, " → ", plate_clevis/SC));
    echo(str("--- пальці (друкований Ø = номінал/SC - ", FIT_PIN, "):"));
    echo(str("    Ø30 → ", 30/SC - FIT_PIN, "   Ø25 → ", 25/SC - FIT_PIN));
    echo(str("--- втулки (Ø зовн / Ø внутр, друковані):"));
    echo(str("    A,B,E ", bush_od_main/SC, " / ", pin_A/SC, "   R,Q ", bush_od_small/SC, " / ", pin_R/SC));
    echo(str("--- штоки циліндрів, друкований Ø: стріли ", boom_cyl_rod/SC, ", рукояті/ковша ", stick_cyl_rod/SC));
    echo(str("--- канал у гільзі, друкований Ø: стріли ", (boom_cyl_rod + P(FIT_SLIDE))/SC, ", рукояті/ковша ", (stick_cyl_rod + P(FIT_SLIDE))/SC));
    echo(str("--- шайби осі B: ", (boom_tube_w - stick_pack_w)/2, " → ", (boom_tube_w - stick_pack_w)/2/SC, " мм — тонші за шар, НЕ друкуються"));
    if ((boom_tube_t)/SC < 2*NOZZLE) echo(str("WARNING: стінка труби ", boom_tube_t/SC, " мм < двох ліній ", 2*NOZZLE, " — слайсер друкуватиме її однією тонкою стінкою"));
    if ((bucket_shell_t)/SC < 2*NOZZLE) echo(str("WARNING: обичайка ковша ", bucket_shell_t/SC, " мм < двох ліній ", 2*NOZZLE));
    if ((boom_tube_t)/SC < NOZZLE) echo(str("WARNING: стінка труби ", boom_tube_t/SC, " мм < сопла — зникне зі слайсу"));
}
else echo(str("!!! невідома друкована деталь: ", pp));
