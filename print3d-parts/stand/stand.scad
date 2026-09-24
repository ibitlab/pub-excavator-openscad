// =============================================================================
//  Стійка для показу надрукованого набору — ТИМЧАСОВЕ рішення, поки в моделі
//  немає рами причепа. НЕ деталь машини й не частина набору: власна тека,
//  власний make.sh; у parts.tsv, BOM і аркуші не входить.
//
//  Три деталі, між собою не клеяться:
//    stand_peg  — стрижень Ø12×30 на фланці Ø22×3, наскрізний отвір Ø3: знизу
//                 крізь основу (або крізь будь-яку дошку — тоді основа не потрібна)
//                 закручується чорний гіпсовий шуруп 3.5 мм. Сталь усередині
//                 стрижня — щоб не зламався під навантаженням.
//    stand_base — плита на стіл; дальню від отвору частину придавлює вантаж.
//                 Отвір Ø3 під шуруп стрижня і потай Ø10 знизу під шляпку, щоб
//                 основа лежала рівно. Замість неї годиться шматок дошки.
//    stand_post — поворотна стійка-трикутник: сідає отвором на стрижень (фланець
//                 ховається у виїмку знизу) і крутиться. Вертикальна стійка,
//                 п'ята вперед, розкіс між ними і трикутне вікно; зверху «голова»
//                 з виїмками 0.5 мм на бічних гранях за контуром нижньої круглої
//                 частини плити колони (26_post_plate): плита сідає у виїмку, і
//                 обидві плити стають рівно на відстані втулки A. Клеїти лише
//                 плити у виїмки. Усі кромки, крім нижніх, скруглені.
//
//  І прищепка на циліндр (stand_clip): ступінчаста C-скоба, що защіпається знизу
//  одразу на голий шток і на кінець гільзи. Рукав на гільзі має отвір під штуцер
//  масляного входу (він у моделі за 25 мм від торця гільзи) — на гільзі скоба сидить
//  замком, не тертям; торець переходу впирається в гільзу — від втягування шток тримає
//  упор, від висунення — натяг рукава на штоку. Одна скоба на циліндр, два розміри:
//  стріла (шток Ø8, гільза Ø15.2) і рукоять з ковшем (Ø5, Ø12).
//
//  Розміри — у ДРУКОВАНИХ мм (на відміну від набору): посадка стрижня, шуруп і
//  виїмка не масштабуються. Від моделі беруться лише контур плити, відстань між
//  плитами (втулка A), висота осі A над землею і діаметри штоків — через parts.scad,
//  який підключає модель як бібліотеку; ні модель, ні набір цим файлом не змінюються.
//
//  Відкритий у OpenSCAD, файл показує стійку з плитами (what = "view").
//  STL робить make.sh:   openscad -o stl/stand_post.stl -D 'what="post"' stand.scad
//                        openscad -o stl/clip_boom.stl -D 'what="clip"' -D CLIP_I=0 stand.scad
// =============================================================================
include <../parts.scad>
part = "none";     // модель — лише бібліотека, її збірку не малювати
pp = "none";       // і жодного компонента набору
assert(!is_undef(SC) && !is_undef(C_w) && !is_undef(ground_below_A), "print3d-parts/parts.scad або модель не підключилися");

/* [Що малювати] */
// view — стійка з плитами; base / peg / post — одна деталь для STL; clip — прищепка
// CLIP_I; clips — обидві прищепки і одна на циліндрі стріли (картинка);
// fit / seat — посадка плит; clip_fit / clip_seat — посадка прищепки на циліндрі
what = "view";

/* [Прищепка на циліндр] */
// Який циліндр: 0 — стріли (шток Ø8, гільза Ø15.2), 1 — рукояті й ковша (Ø5, Ø12)
CLIP_I = 0;
// Рукав на штоку і на гільзі (стріла / решта), друковані мм; на штоку не довший за голий
// шток при повному втягуванні (6 мм), на гільзі — щоб накрити штуцер за 5 мм від торця
CLIP_ROD_L = 5;
CLIP_BODY_L = [10, 8];
// Кут обхвату обох рукавів: губки при защіпанні розходяться на ~9 % — PLA витримує
CLIP_ARC = 225;
// Стінка рукавів (4 лінії сопла)
CLIP_WALL = 1.6;
// Діаметральний зазор рукавів: 0 — у номінал (FDM сам звужує дуги на 0.1–0.2, і сидить
// з натягом); спадає — поставити −0.1, туго — +0.1
CLIP_FIT = 0;
// Зазор отвору під штуцер (по діаметру)
CLIP_PORT_FIT = 0.4;

/* [Стійка для показу] */
// Вісь A над столом — як над землею в моделі (650 мм → 130)
STAND_A_H = ground_below_A / SC;
// Стрижень: діаметр і висота над фланцем, фланець; отвір у стійці ширший на STAND_FIT
STAND_PEG_D = 12;
STAND_PEG_H = 30;
STAND_FLANGE_D = 22;
STAND_FLANGE_T = 3;
STAND_FIT   = 0.5;
// Шуруп у стрижні: наскрізний отвір; потай під шляпку на нижній грані основи
STAND_SCREW_D = 3;
STAND_SCREW_HEAD_D = 10;
// Виїмка під плиту: глибина і зазор по контуру (на бік)
STAND_POCKET = 0.5;
STAND_POCKET_FIT = 0.2;
// Основа: довжина назад від стрижня (під вантаж), уперед, ширина, товщина
STAND_BASE_BACK  = 125;
STAND_BASE_FRONT = 55;
STAND_BASE_W = 90;
STAND_BASE_T = 4;
// Стійка: п'ята вперед від осі стрижня, її товщина, ширина розкосу, бортик
// навколо виїмки, висота голови над центром нижнього кола плити, радіус кромок
STAND_FOOT_X = 50;
STAND_FOOT_T = 6;
STAND_BRACE  = 8;
STAND_RIM    = 3.3;
STAND_HEAD   = 6;
STAND_ROUND  = 1.5;

// Між плитами колони — довжина втулки A + 2 (як у post_schematic моделі)
STAND_W = (boom_foot_boss_len + 2) / SC;

// Контур плити колони 1:SC у площині XZ моделі (тут X, Y), вісь A в початку —
// ті самі кола, що в make_post_plate() набору і post_schematic() моделі
module stand_plate_2d() {
    hull() {
        circle(d = 110 / SC, $fn = 96);
        translate(C_w / SC) circle(d = 90 / SC, $fn = 96);
        translate([0, (C_w[1] - 150) / SC]) circle(d = 110 / SC, $fn = 96);
    }
}

// Центр нижнього кола плити над столом і верх голови стійки. Голова невисока:
// вище контур плити розширюється вперед до осі C, і тіло стало б клином
function stand_lobe_z() = STAND_A_H + (C_w[1] - 150) / SC;
function stand_top() = stand_lobe_z() + STAND_HEAD;
// Права кромка плити на висоті z: дотична від нижнього кола (Ø110) до кола осі C
// (Ø90) — те саме, що робить hull() у контурі плити. Повертає [x, nx]: nx — складова
// нормалі кромки, щоб зазор і бортик перевести з перпендикуляра в горизонталь
function stand_plate_edge(z) = let(
        c1 = [0, stand_lobe_z()], r1 = 55 / SC,
        c2 = C_w / SC + [0, STAND_A_H], r2 = 45 / SC,
        d = c2 - c1, a = atan2(d[1], d[0]) - acos((r1 - r2) / norm(d)),
        n = [cos(a), sin(a)])
    [(n * c1 + r1 - n[1] * z) / n[0], n[0]];

// Стрижень на фланці з наскрізним отвором під шуруп. Друкується фланцем на стіл.
module stand_peg() {
    difference() {
        union() {
            cylinder(d = STAND_FLANGE_D, h = STAND_FLANGE_T, $fn = 96);
            translate([0, 0, STAND_FLANGE_T]) {
                cylinder(d = STAND_PEG_D, h = STAND_PEG_H - 1, $fn = 96);
                translate([0, 0, STAND_PEG_H - 1]) cylinder(d1 = STAND_PEG_D, d2 = STAND_PEG_D - 2, h = 1, $fn = 96);
            }
        }
        translate([0, 0, -1]) cylinder(d = STAND_SCREW_D, h = STAND_FLANGE_T + STAND_PEG_H + 2, $fn = 32);
    }
}

// Основа: плита зі скругленими кутами, отвір під шуруп і потай знизу (конус 45° —
// не звис). Стрижень стоїть на ній фланцем, у місці отвору.
module stand_base() {
    L = STAND_BASE_BACK + STAND_BASE_FRONT;
    difference() {
        linear_extrude(STAND_BASE_T)
            translate([-STAND_BASE_BACK, -STAND_BASE_W / 2])
                offset(r = 8, $fn = 48) offset(delta = -8) square([L, STAND_BASE_W]);
        translate([0, 0, -1]) cylinder(d = STAND_SCREW_D, h = STAND_BASE_T + 2, $fn = 32);
        translate([0, 0, -eps]) cylinder(d1 = STAND_SCREW_HEAD_D + 2 * eps, d2 = STAND_SCREW_D,
                                         h = (STAND_SCREW_HEAD_D - STAND_SCREW_D) / 2, $fn = 48);
    }
}

// Тіло стійки без виїмок і отворів — окремо, бо перевірка «seat» звіряє з ним плити.
// Скруглення: профіль стиснуто на R, тіло звужено на 2R і «роздуто» кулею R назад —
// усі опуклі кромки стають радіусом R. Низ продовжено вниз і зрізано площиною z = 0:
// нижні кромки лишаються гострими, бо стійка друкується на них.
module stand_post_body() {
    zl = stand_lobe_z();
    zt = stand_top();
    R = STAND_ROUND;
    // спина і передня грань стійки — бортик навколо нижнього кола плити (Ø110 + зазор)
    xb = 55 / SC + STAND_POCKET_FIT + STAND_RIM;
    // верхній передній кут голови — бортик від правої кромки плити
    e = stand_plate_edge(zt);
    x_top = e[0] + (STAND_POCKET_FIT + STAND_RIM) / e[1];
    // профіль у XZ: спина, п'ята, розкіс від п'яти до кута голови, верх голови
    profile = [[-xb, -2 * R], [STAND_FOOT_X, -2 * R], [STAND_FOOT_X, 0], [x_top, zt], [-xb, zt]];
    // вікно: стійка (x = xb), п'ята (z = STAND_FOOT_T), внутрішня кромка розкосу
    // (паралельно зовнішній, на STAND_BRACE углиб) і стеля на 3 мм нижче центра кола
    u = ([x_top, zt] - [STAND_FOOT_X, 0]) / norm([x_top, zt] - [STAND_FOOT_X, 0]);
    p0 = [STAND_FOOT_X, 0] + STAND_BRACE * [-u[1], u[0]];
    function xi(z) = p0[0] + (z - p0[1]) * u[0] / u[1];
    zw = zl - 3;
    window = [[xb, STAND_FOOT_T], [xi(STAND_FOOT_T), STAND_FOOT_T], [xi(zw), zw], [xb, zw]];
    assert(xi(zw) > xb + 3, "розкіс упирається у стійку — вікна не лишилося");
    // зріз — відніманням куба знизу, не перетином: у прев'ю (F5) грань перетину на
    // z = 0 збігалася б з верхом основи і давала смуги по всій плиті
    difference() {
        minkowski() {
            rotate([90, 0, 0]) linear_extrude(STAND_W + 2 * STAND_POCKET - 2 * R, center = true)
                offset(delta = -R) difference() { polygon(profile); polygon(window); }
            sphere(r = R, $fn = 24);
        }
        translate([-100, -50, -100]) cube([200, 100, 100]);
    }
}

// Поворотна стійка-трикутник. Друкується стоячи (п'ятою на стіл): отвір під
// стрижень вертикальний і круглий, виїмки — на прямовисних гранях, розкіс
// нахилений назовні донизу — не звис; стеля вікна і стеля отвору — містки,
// виїмка під фланець переходить в отвір конусом 45°.
// render(): у прев'ю (F5) OpenCSG малював розкіс з «вирізаною» передньою гранню —
// тіло після minkowski невипукле; з готової сітки стійка показується цілою.
module stand_post() {
    zt = stand_top();
    hole_d = STAND_PEG_D + STAND_FIT;
    fl_d = STAND_FLANGE_D + 2 * STAND_POCKET_FIT;
    fl_h = STAND_FLANGE_T + STAND_POCKET_FIT;
    render(convexity = 8) difference() {
        stand_post_body();
        // виїмки під плити: контур плити, піднятий на висоту осі A, обрізаний по верху голови
        for (s = [-1, 1]) translate([0, s * (STAND_W / 2 + STAND_POCKET), 0]) rotate([90, 0, 0])
            linear_extrude(2 * STAND_POCKET, center = true) offset(delta = STAND_POCKET_FIT)
                intersection() {
                    translate([0, STAND_A_H]) stand_plate_2d();
                    translate([-60, -1]) square([120, zt + 1]);
                }
        // отвір під стрижень: стеля на 1 мм вище його верхівки
        translate([0, 0, -1]) cylinder(d = hole_d, h = STAND_FLANGE_T + STAND_PEG_H + 2, $fn = 96);
        // виїмка під фланець знизу і конус 45° від неї до отвору
        translate([0, 0, -1]) cylinder(d = fl_d, h = fl_h + 1, $fn = 96);
        translate([0, 0, fl_h]) cylinder(d1 = fl_d, d2 = hole_d, h = (fl_d - hole_d) / 2, $fn = 96);
    }
}

// Розміри циліндрів набору, друковані мм: [шток, гільза зовні, рукав на гільзі].
// Стінки гільз 6.5 (стріла) і 5 — ті самі, що parts.scad передає в hyd_cyl_part().
function clip_sizes() = [
    [boom_cyl_rod / SC,  (boom_cyl_bore + 2 * 6.5) / SC, CLIP_BODY_L[0]],
    [stick_cyl_rod / SC, (stick_cyl_bore + 2 * 5) / SC,  CLIP_BODY_L[1]]];
// Штуцер масляного входу: Ø16, за 25 мм від торця гільзи — літерали з hyd_cyl_part()
CLIP_PORT_D = 16 / SC;
CLIP_PORT_X = 25 / SC;

// Профіль рукава: кільце з вирізом на CLIP_ARC, кінці губок скруглені (offset стискає
// кільце майже до середньої лінії і роздуває назад — вузькі кінці стають півколами).
// Круглі губки легко наїжджають на деталь і не дряпають її. Виріз дивиться на +X.
module clip_ring_2d(ri, ro) {
    w = ro - ri;
    g = (360 - CLIP_ARC) / 2;
    offset(r = 0.45 * w, $fn = 32) offset(delta = -0.45 * w)
        difference() {
            circle(r = ro, $fn = 96);
            circle(r = ri, $fn = 96);
            polygon([[0, 0], [3 * ro * cos(g), 3 * ro * sin(g)], [3 * ro, 3 * ro * sin(g)],
                     [3 * ro, -3 * ro * sin(g)], [3 * ro * cos(g), -3 * ro * sin(g)]]);
        }
}
// Висота упорного торця над низом прищепки: рукав штока + конус переходу (45°)
function clip_step(i) = let(s = clip_sizes()[i]) CLIP_ROD_L + (s[1] - s[0]) / 2;

// Тіло прищепки без отвору під штуцер (перевірка clip_seat звіряє з ним штуцер).
// Вісь Z, рукав штока внизу (z = 0), виріз на +X, штуцер — з боку −X.
// Друкується стоячи на рукаві штока: конус переходу 45° назовні — не звис.
module clip_body(i = CLIP_I) {
    s = clip_sizes()[i];
    ri_r = (s[0] + CLIP_FIT) / 2;  ro_r = ri_r + CLIP_WALL;
    ri_b = (s[1] + CLIP_FIT) / 2;  ro_b = ri_b + CLIP_WALL;
    z1 = CLIP_ROD_L;
    z2 = clip_step(i);
    union() {
        linear_extrude(z1 + eps) clip_ring_2d(ri_r, ro_r);
        // перехід: зовні конус від рукава штока до рукава гільзи, всередині отвір штока;
        // верхній торець (z2) від ri_r до ri_b — упор у торець гільзи
        translate([0, 0, z1]) rotate([0, 0, (360 - CLIP_ARC) / 2]) rotate_extrude(angle = CLIP_ARC, $fn = 96)
            polygon([[ri_r, 0], [ro_r, 0], [ro_b, z2 - z1], [ri_r, z2 - z1]]);
        translate([0, 0, z2 - eps]) linear_extrude(s[2] + eps) clip_ring_2d(ri_b, ro_b);
    }
}
// Отвір під штуцер: крізь спинку рукава гільзи, за CLIP_PORT_X від упорного торця
module clip_port_hole(i = CLIP_I) {
    s = clip_sizes()[i];
    translate([0, 0, clip_step(i) + CLIP_PORT_X]) rotate([0, -90, 0])
        cylinder(d = CLIP_PORT_D + CLIP_PORT_FIT, h = s[1], $fn = 48);
}
module stand_clip(i = CLIP_I) {
    difference() { clip_body(i); clip_port_hole(i); }
}

// Циліндр стріли з набору (гільза + шток), 1:SC, шток висунутий на частку ходу f;
// вісь X, вушко гільзи в початку, штуцери догори — як у hyd_cyl_part() і cyl_part()
module clip_demo_cyl(f = 0.4) {
    L = boom_cyl_closed + f * boom_cyl_stroke;
    body_L = boom_cyl_closed - 2 * 45 - 30;
    scale(1 / SC) {
        make_cyl_body(boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
        translate([L, 0, 0]) hyd_cyl_part("rod", boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke,
                                          boom_cyl_pin, wall = 6.5, rod_vis = L - 2 * 45 - body_L + 1);
    }
}
// Прищепка стріли на місці: упорний торець на торці гільзи (x = 45 + body_L), рукав
// гільзи назад по −X, виріз донизу, отвір під штуцер догори
module clip_demo_placed(hole = true) {
    x_end = (45 + boom_cyl_closed - 2 * 45 - 30) / SC;
    translate([x_end + clip_step(0), 0, 0]) rotate([0, -90, 0]) rotate([0, 0, 180])
        if (hole) stand_clip(0); else clip_body(0);
}
// Картинка: обидві прищепки стоять поруч, далі кінець циліндра стріли (гільза зрізана
// за 25 мм до торця, шток — за 30 після) з прищепкою на місці і штуцером в отворі
module stand_clips() {
    x_end = (45 + boom_cyl_closed - 2 * 45 - 30) / SC;
    color([0.85, 0.85, 0.88]) { stand_clip(0); translate([22, 0, 0]) stand_clip(1); }
    translate([50 - x_end + 25, 0, 0]) {
        color([0.45, 0.45, 0.48]) intersection() {
            clip_demo_cyl();
            translate([x_end - 25, -20, -20]) cube([55, 40, 40]);
        }
        color([0.95, 0.70, 0.20]) clip_demo_placed();
    }
}

// Плити колони так, як вони сидять у виїмках стійки, що стоїть на основі
module stand_plates() {
    for (s = [-1, 1])
        translate([0, s * ((boom_foot_boss_len + 2) / 2 + 6) / SC, STAND_A_H + STAND_BASE_T])
            scale(1 / SC) make_post_plate();
}

if      (what == "base") stand_base();
else if (what == "peg")  stand_peg();
else if (what == "post") stand_post();
else if (what == "clip") stand_clip();
else if (what == "clips") stand_clips();
// прищепка на циліндрі стріли: з гільзою і штоком не перетинається (має бути порожньо)…
else if (what == "clip_fit")  intersection() { clip_demo_placed(); clip_demo_cyl(); }
// …а без отвору під штуцер перетинається саме зі штуцером (має бути > 0)
else if (what == "clip_seat") intersection() { clip_demo_placed(hole = false); clip_demo_cyl(); }
// перетин плит зі стійкою — має бути порожнім (OpenSCAD тоді не пише файл)
else if (what == "fit")  intersection() { translate([0, 0, STAND_BASE_T]) stand_post(); stand_plates(); }
// перетин плит із тілом без виїмок — має бути > 0: виїмки саме там, де плити
else if (what == "seat") intersection() { translate([0, 0, STAND_BASE_T]) stand_post_body(); stand_plates(); }
else {
    color([0.80, 0.80, 0.75]) stand_base();
    color([0.55, 0.55, 0.60]) translate([0, 0, STAND_BASE_T]) stand_peg();
    color([0.95, 0.70, 0.20]) translate([0, 0, STAND_BASE_T]) stand_post();
    color([0.30, 0.30, 0.30, 0.55]) stand_plates();     // напівпрозорі: видно, як сідає нижнє коло
}
