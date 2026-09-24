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
//  Розміри — у ДРУКОВАНИХ мм (на відміну від набору): посадка стрижня, шуруп і
//  виїмка не масштабуються. Від моделі беруться лише контур плити, відстань між
//  плитами (втулка A) і висота осі A над землею — через parts.scad, який підключає
//  модель як бібліотеку; ні модель, ні набір цим файлом не змінюються.
//
//  Відкритий у OpenSCAD, файл показує стійку з плитами (what = "view").
//  STL робить make.sh:   openscad -o stl/stand_post.stl -D 'what="post"' stand.scad
// =============================================================================
include <../parts.scad>
part = "none";     // модель — лише бібліотека, її збірку не малювати
pp = "none";       // і жодного компонента набору
assert(!is_undef(SC) && !is_undef(C_w) && !is_undef(ground_below_A), "print3d-parts/parts.scad або модель не підключилися");

/* [Що малювати] */
// view — усе разом з плитами; base / peg / post — одна деталь для STL; fit / seat — перевірки посадки
what = "view";

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

// Плити колони так, як вони сидять у виїмках стійки, що стоїть на основі
module stand_plates() {
    for (s = [-1, 1])
        translate([0, s * ((boom_foot_boss_len + 2) / 2 + 6) / SC, STAND_A_H + STAND_BASE_T])
            scale(1 / SC) make_post_plate();
}

if      (what == "base") stand_base();
else if (what == "peg")  stand_peg();
else if (what == "post") stand_post();
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
