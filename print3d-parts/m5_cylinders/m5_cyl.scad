// =============================================================================
//  Циліндри друкованої моделі 1:5 на шпильці M5×0.8 і моторедукторі N20
//
//  Шпилька — шток, вона НЕ крутиться: на її хвості поршень-шайба з пазом, що ковзає
//  по ребру всередині гільзи. Гайка M5 — всередині шестерні в голові циліндра (біля
//  виходу штока), шестерня — на підшипнику MR128. N20 стоїть паралельно, збоку,
//  корпусом уздовж гільзи; шестерня на його валу крутить шестерню гайки.
//
//  Зворотний зв'язок:
//    енкодер  — 2 магніти Ø2×1 (N і S назустріч) у торці шестерні гайки, 2 латчі
//               Холла (US1881 / DRV5013) у передній стінці під 90° → квадратура,
//               4 фронти на оберт гайки = 0.2 мм ходу;
//    кінцевики — магніт Ø2×1 (той самий, що в енкодері) у боці поршня і 2 датчики Холла
//               (DRV5032): «розкритий» — у приливі гільзи одразу за головою, «зведений» —
//               у задній кришці. Упори механічні (поршень об голову / об дно кришки); датчик
//               спрацьовує за ~2–3 мм до упору.
//
//  Довжини, хід, вушка й зовнішній Ø гільзи — з моделі (scad/excavator_boom.scad), 1:SC;
//  модель підключається як бібліотека й не змінюється. Мотор, шестерні й розміри гільзи —
//  сталі нижче; calc.py читає їх звідси ж і рахує, чи мотор тягне (CALC.md).
//
//  openscad -D 'cyl="stick"' -D 'pp="asm"' -D 'ext=40' m5_cyl.scad     — збірка, висунутий на 40 мм
//  pp: asm | cut | headcut (розрізи) | tube | head_rear | head_front | gear | pinion | puck | cap | eye
//      pair, collide — перевірки make.sh
// =============================================================================
include <../../scad/excavator_boom.scad>
// Невдалий include — не помилка: модулі стають порожні, а STL валідними й порожніми
assert(!is_undef(boom_cyl_closed), "scad/excavator_boom.scad не підключився");
part = "none";

/* [Мотор і шестерні] */
SC = 5;                     // масштаб набору (print3d-parts/parts.scad; calc.py звіряє)
MOTOR = [298, 60];          // 12GAN20-298, 60 об/хв — вибір; що дали б інші N20 — у CALC.md
GEAR_M = 0.6; GEAR_ALPHA = 20;
Z_NUT = 27;                 // шестерня гайки: менша не вміщає гайку S8 і два магніти Ø2
Z_PIN = [27, 27, 27];       // шестерня мотора: стріла, рукоять, ківш; 27 = 1:1 (вибір)
TUBE_ID = [11.0, 9.0, 9.0]; // гільза всередині: зовнішній Ø — з моделі, внутрішній — під поршень
PUCK = 6.0;                 // довжина поршня
REAR_WALL = 1.2;            // дно кришки
EYE_LEN = 9.0;              // вісь вушка → корпус (як eye_len 45 у моделі), з обох кінців
FRONT_GAP = 1.0;            // шийка вушка штока ↔ ніс голови у зведеному

/* [Вибір] */
cyl = "stick";      // boom | stick | bucket
pp = "asm";
ext = 0;            // висування штока, друковані мм (0…хід)
// Кут мотора навколо осі циліндра, °: 0 = +Y (ліворуч, якщо дивитись від колони на ківш), 90 = +Z.
// Усі три ліворуч: мотори й джгути на одному боці, поза площиною механізму (make.sh collide: чисто)
MOTOR_PHI = [0, 0, 0];
show_buy = true;    // покупне (мотор, шпилька, гайка, підшипник, магніти, датчики) у збірці

/* [Допуски друку] */
FIT = 0.15;         // радіальний зазор посадок, мм
PRESS = 0.0;        // під підшипник — у натяг, підбирається пробою

/* [Hidden] */
$fn = 72;
eps = 0.01;
KEYS = ["boom", "stick", "bucket"];
ki = search([cyl], KEYS)[0];

// --- покупне
M5_D = 5.0; M5_NUT_S = 8.0; M5_NUT_H = 4.0;
BRG = [8, 12, 3.5];                 // MR128ZZ: d, D, B
N20_W = 12; N20_T = 10; N20_GB = 9; N20_MOT = 15; N20_SHAFT = [3.0, 2.5, 10];   // Ø, лиска, довжина
N20_HOLE = 9;                       // два M1.6 на торці редуктора, між осями
HALL = [4.1, 3.1, 1.6];             // TO-92S: ширина, висота, товщина (з запасом)
MAG_ENC = [2.0, 1.0];               // магніт енкодера Ø×h
MAG_LIM = MAG_ENC;                  // магніт поршня — той самий: один розмір на все

// --- голова (осьовий стек від заднього торця x_hr)
LIP = 1.8; TUBE_IN = 1.0;           // губа й глибина паза під торець гільзи
GAP_SH = 0.3; GEAR_B = 5.0; GAP_F = 0.4; FWALL = 2.0;
HEAD_CORE = LIP + BRG[2] + GAP_SH + GEAR_B + GAP_F + FWALL;   // 13.0; calc.py складає з тих самих сталих
R_MAG = 5.7;                        // радіус магнітів енкодера: навпроти граней гайки, між гранню й западиною
WALL = 1.2;
NOSE_D = 8.0; NOSE_BORE = 5.3;
EAR_R = 2.2; EAR_ANG = [120, 240];  // вушка під M2 (відносно напрямку на мотор)

// --- дані циліндра з моделі
function mv(k, n) = let(t = [
    ["closed", boom_cyl_closed, stick_cyl_closed, bucket_cyl_closed],
    ["stroke", boom_cyl_stroke, stick_cyl_stroke, bucket_cyl_stroke],
    ["bore",   boom_cyl_bore,   stick_cyl_bore,   bucket_cyl_bore],
    ["pin",    boom_cyl_pin,    stick_cyl_pin,    bucket_cyl_pin],
    ["wall",   6.5, 5, 5]]) t[search([n], t)[0]][1 + search([k], KEYS)[0]];
// міжосьова пари з корекцією (inv αw = 2·tgα·(x1+x2)/(z1+z2) + inv α) — та сама формула, що в calc.py
function _inv(a) = tan(a) - a * PI / 180;
function _aw(t, lo = 0, hi = 60, n = 40) = n == 0 ? (lo + hi) / 2 :
    let(m = (lo + hi) / 2) _inv(m) < t ? _aw(t, m, hi, n - 1) : _aw(t, lo, m, n - 1);
function center_dist(z1, x1, z2, x2) = let(t = 2 * tan(GEAR_ALPHA) * (x1 + x2) / (z1 + z2) + _inv(GEAR_ALPHA))
    GEAR_M * (z1 + z2) / 2 * cos(GEAR_ALPHA) / cos(_aw(t));
function shift(z) = round(max(0, (17 - z) / 17) * 100) / 100;   // проти підрізання при z < 17

L0    = mv(cyl, "closed") / SC;
S     = mv(cyl, "stroke") / SC;
OD    = (mv(cyl, "bore") + 2 * mv(cyl, "wall")) / SC;
ID    = TUBE_ID[ki];
PIN   = mv(cyl, "pin") / SC;
EYE_OD = (mv(cyl, "pin") + 28) / SC;
EYE_W  = (mv(cyl, "pin") >= 30 ? cyl_eye_w_30 : cyl_eye_w_25) / SC;
EYE_R  = EYE_OD / 2;
ZP = Z_PIN[ki]; XP = shift(ZP); A = center_dist(Z_NUT, 0, ZP, XP);
MOTOR_NAME = str("12GAN20-", MOTOR[0], ", ", MOTOR[1], " об/хв");
PHI = MOTOR_PHI[ki];

X_CI = EYE_LEN + REAR_WALL;           // дно кришки = упор поршня (зведений); стакан — з 9 мм, як корпус у моделі:
                                      // ближче до вушка — щоки вилки бази
X_HR = X_CI + S + PUCK;               // задній торець голови = упор поршня (розкритий)
X_BRG = X_HR + LIP;
X_GEAR = X_BRG + BRG[2] + GAP_SH;
X_FW = X_GEAR + GEAR_B + GAP_F;       // стик голова/передня стінка
X_HF = X_FW + FWALL;
X_NOSE = L0 - EYE_LEN - FRONT_GAP;
SCREW_L = L0 - PIN / 2 - 0.8 - X_CI;
assert(X_NOSE >= X_HF, str(cyl, ": голова не влазить у зведену довжину"));

// шестерні
R_TIP_G = GEAR_M * (Z_NUT / 2 + 1);
R_CH = R_TIP_G + 0.5;                 // камера шестерні гайки
R_TIP_P = GEAR_M * (ZP / 2 + 1 + XP);
R_LOBE = R_TIP_P + 0.5 + WALL;        // прилив під шестерню мотора
R_HEAD = R_CH + WALL;
assert(A >= OD / 2 + N20_T / 2 + 0.5, "мотор ближче до гільзи, ніж можна");

// кути навколо осі X (0 = +Y, 90 = +Z)
function dirv(a) = [0, cos(a), sin(a)];
PHI_SENS = PHI + 180;                 // датчики кінцевиків, магніт поршня
PHI_KEY  = PHI + 90;                  // ребро проти провертання
ENC_ANG  = [PHI + 90, PHI + 180];     // латчі енкодера — 90° один від одного

// -----------------------------------------------------------------------------
//  Допоміжне: усе будується у площині YZ (профіль) і витягується вздовж X
// -----------------------------------------------------------------------------
module along(x0, x1) { translate([x0, 0, 0]) rotate([0, 90, 0]) rotate([0, 0, 90]) linear_extrude(x1 - x0) children(); }
// у профілі: вісь X профілю = Y світу, вісь Y профілю = Z світу... після rotate — перевірено на dirv()
module at_ang(a, r) { rotate([a, 0, 0]) translate([0, r, 0]) children(); }       // точка на радіусі r під кутом a (3D)
// те саме в профілі; вісь X дитини — уздовж радіуса, тож square([радіально, по дотичній]) однаковий за будь-якого кута
module p2_at(a, r) { translate([r * cos(a), r * sin(a)]) rotate(a) children(); }

// евольвентна шестерня (2D), корекція x, бічний зазор bl
function inv_(a) = tan(a) - a * PI / 180;
module gear2d(z, m, x = 0, alpha = 20, bl = 0.06) {
    r = m * z / 2; rb = r * cos(alpha); ra = r + m * (1 + x); rf = r - m * (1.25 - x);
    psi = (PI / 2 + 2 * x * tan(alpha)) / z - bl / (2 * r);
    r0 = max(rb, rf);
    half = function(rr) max(0.5, (psi + inv_(alpha) - inv_(acos(min(1, rb / rr)))) * 180 / PI);
    n = 8;
    rs = [for (i = [0:n]) r0 + (ra - r0) * i / n];
    union() {
        circle(r = rf, $fn = z * 3);
        for (k = [0:z - 1]) rotate(k * 360 / z) polygon(concat(
            [[rf * 0.95 * cos(-half(r0)), rf * 0.95 * sin(-half(r0)) ]],
            [for (rr = rs) [rr * cos(-half(rr)), rr * sin(-half(rr))]],
            [for (i = [n:-1:0]) let(rr = rs[i]) [rr * cos(half(rr)), rr * sin(half(rr))]],
            [[rf * 0.95 * cos(half(r0)), rf * 0.95 * sin(half(r0))]]));
    }
}

// контур голови в профілі (YZ): коло навколо осі + прилив навколо вала мотора
module head_outline(extra = 0) {
    hull() {
        circle(r = R_HEAD + extra);
        p2_at(PHI, A) circle(r = R_LOBE + extra);
    }
    for (a = EAR_ANG) p2_at(PHI + a, R_CH + EAR_R) circle(r = EAR_R + WALL * 0.6 + extra);
}
module ear_holes(d) { for (a = EAR_ANG) p2_at(PHI + a, R_CH + EAR_R) circle(d = d, $fn = 24); }
module motor_profile(c = 0) {        // переріз N20: 12 уздовж дотичної, 10 радіально
    p2_at(PHI, A) square([N20_T + 2 * c, N20_W + 2 * c], center = true);
}

// -----------------------------------------------------------------------------
//  Деталі (у системі циліндра, вісь +X від пальця бази)
// -----------------------------------------------------------------------------
// Гільза: друкується стоячи на задньому торці. Ребро проти провертання всередині,
// прилив датчика «розкритий» біля переднього торця, канавка під дроти.
module tube() {
    x0 = X_CI; x1 = X_HR + TUBE_IN;
    difference() {
        union() {
            along(x0, x1) circle(d = OD);
            // прилив датчика (з фасками 45° знизу для друку)
            hull() {
                along(X_HR - 7, X_HR) p2_at(PHI_SENS, OD / 2 + 0.6) square([2.6, HALL[0] + 2], center = true);
                along(X_HR - 9.6, X_HR - 9.5) p2_at(PHI_SENS, OD / 2 - 0.5) square([0.2, HALL[0] + 2], center = true);
            }
            // мотор тримають два M1.6 на торці редуктора; хвіст — крапля клею до гільзи (хомут з фаскою під
            // друк виходив плавником більшим за сам мотор)
        }
        along(x0 - 1, x1 + 1) circle(d = ID);
        // кишеня датчика «розкритий»: навпроти магніту поршня, коли той на упорі
        translate([X_HR - PUCK / 2, 0, 0]) rotate([PHI_SENS, 0, 0])
            translate([-HALL[1] / 2, -HALL[0] / 2, OD / 2]) cube([HALL[1], HALL[0], HALL[2] + 2]);
        // канавка під дроти датчика «зведений» (з кришки до приливу)
        along(x0 - 1, X_HR - 6) p2_at(PHI_SENS, OD / 2) square([1.4, 1.2], center = true);
        // мітка орієнтації на передньому торці (проти мотора — там і датчики)
        along(x1 - 1.5, x1 + 1) p2_at(PHI_SENS, OD / 2) circle(d = 0.8, $fn = 12);
    }
    // ребро проти провертання
    along(x0, X_HR) p2_at(PHI_KEY, ID / 2 - 0.35) square([1.2, 1.3], center = true);
}

// Голова, задня частина: губа (упор поршня), гніздо MR128, камера шестерень, кріплення мотора.
// Друкується заднім торцем на стіл — без жодного нависання: усе — кишені догори.
module head_rear() {
    difference() {
        along(X_HR, X_FW) head_outline();
        // паз під торець гільзи
        along(X_HR - 1, X_HR + TUBE_IN) difference() { circle(d = OD + 2 * FIT); circle(d = ID - 0.2); }
        // отвір шпильки
        along(X_HR - 1, X_BRG + 1) circle(d = M5_D + 0.6);
        // підшипник і виїмка під внутрішнє кільце (губа тримає лише зовнішнє)
        along(X_BRG, X_BRG + BRG[2] + eps) circle(d = BRG[1] + PRESS);
        along(X_BRG - 0.25, X_BRG + 0.1) circle(d = BRG[1] - 1.8);
        // камера шестерні гайки і шестерні мотора
        along(X_BRG + BRG[2], X_FW + 1) { circle(r = R_CH); p2_at(PHI, A) circle(r = R_TIP_P + 0.5); }
        // вал мотора, бобишка редуктора, гвинти M1.6 (голівки — у зенківках з боку камери)
        along(X_HR - 1, X_GEAR) p2_at(PHI, A) circle(d = N20_SHAFT[0] + 0.6, $fn = 24);
        along(X_HR - 1, X_HR + 0.6) p2_at(PHI, A) circle(d = 4.4, $fn = 24);
        for (s = [-1, 1]) {
            along(X_HR - 1, X_GEAR) p2_at(PHI, A) translate([0, s * N20_HOLE / 2]) circle(d = 1.8, $fn = 16);
            along(X_GEAR - 1.4, X_GEAR + 1) p2_at(PHI, A) translate([0, s * N20_HOLE / 2]) circle(d = 3.3, $fn = 16);
        }
        // вушка M2: отвір під саморіз
        along(X_HR - 1, X_FW + 1) ear_holes(1.6);
        // вихід дротів датчиків на боці датчиків
        along(X_HR - 1, X_FW + 1) p2_at(PHI_SENS, R_HEAD) square([3.0, 2.0], center = true);
    }
}

// Голова, передня стінка з носом-напрямною. Латчі енкодера — у кишенях на передньому торці
// (чутливою стороною до шестерні, дно 0.4 мм), виводи — канавками назовні.
module head_front() {
    difference() {
        union() {
            along(X_FW, X_HF) head_outline();
            along(X_HF - eps, X_NOSE) circle(d = NOSE_D);
        }
        along(X_FW - 1, X_NOSE + 1) circle(d = NOSE_BORE);
        along(X_FW - 1, X_HF - 0.4) circle(d = M5_D + 1.2);     // не труться об торець гайки
        for (a = ENC_ANG) {
            translate([X_HF - HALL[2], 0, 0]) rotate([a, 0, 0]) translate([0, R_MAG - HALL[1] / 2, -HALL[0] / 2])
                cube([HALL[2] + 1, HALL[1], HALL[0]]);
            translate([X_HF - 0.8, 0, 0]) rotate([a, 0, 0]) translate([0, R_MAG, -1.3]) cube([1, R_HEAD + 5, 2.6]);
        }
        along(X_FW - 1, X_HF + 1) ear_holes(2.3);
    }
}

// Шестерня гайки: гайка M5 закладається на паузі друку (замкнена з обох боків),
// маточина — у підшипник, магніти — на передньому торці навпроти граней гайки.
module nut_gear() {
    difference() {
        union() {
            along(X_GEAR, X_GEAR + GEAR_B) rotate(PHI) gear2d(Z_NUT, GEAR_M, 0, GEAR_ALPHA);   // зуб — на мотор
            along(X_GEAR - GAP_SH, X_GEAR + eps) circle(d = BRG[0] + 1.4);   // заплечик: лише внутрішнє кільце
            along(X_BRG, X_GEAR) circle(d = BRG[0]);                         // маточина
        }
        along(X_BRG - 1, X_GEAR + GEAR_B + 1) circle(d = M5_D + 0.4);
        along(X_GEAR + (GEAR_B - M5_NUT_H - 0.1) / 2, X_GEAR + (GEAR_B + M5_NUT_H + 0.1) / 2)
            rotate(30 + PHI) circle(d = (M5_NUT_S + 0.1) / cos(30), $fn = 6);   // грані — до магнітів
        for (a = [0, 180]) translate([X_GEAR + GEAR_B - MAG_ENC[1] - 0.05, 0, 0]) rotate([PHI + a, 0, 0])
            translate([0, R_MAG, 0]) rotate([0, 90, 0]) cylinder(d = MAG_ENC[0] + 0.1, h = MAG_ENC[1] + 1, $fn = 24);
    }
}

module pinion() {
    translate([0, 0, 0]) rotate([PHI, 0, 0]) translate([0, A, 0]) rotate([-PHI, 0, 0])
    difference() {
        along(X_GEAR, X_GEAR + GEAR_B) rotate(PHI + 180 + 180 / ZP) gear2d(ZP, GEAR_M, XP, GEAR_ALPHA);   // западина — на гайку
        along(X_GEAR - 1, X_GEAR + GEAR_B + 1) rotate(PHI) d_shaft(0.05);   // лиска — так само, як на валу мотора
    }
}

// Поршень-шайба на хвості шпильки: нарізається самою шпилькою й садиться на клей.
module puck(e = 0) {
    translate([e, 0, 0]) difference() {
        along(X_CI, X_CI + PUCK) circle(d = ID - 0.3);
        along(X_CI - 1, X_CI + PUCK + 1) circle(d = 4.2);
        along(X_CI - 1, X_CI + PUCK + 1) p2_at(PHI_KEY, ID / 2) square([2.2, 2.4], center = true);   // ребро сягає ID/2−0.95: зазор 0.15
        translate([X_CI + PUCK / 2, 0, 0]) rotate([PHI_SENS, 0, 0]) translate([0, ID / 2 - 0.15 - MAG_LIM[1] - 0.1, 0])
            rotate([-90, 0, 0]) cylinder(d = MAG_LIM[0] + 0.1, h = 5, $fn = 24);
    }
}

// Задня кришка з вушком бази: гільза вклеюється в стакан; датчик «зведений» — у приливі стакана.
// Друкується стаканом донизу: дно — міст над Ø стакана, далі шийка й вушко.
module cap() {
    cup = 5.5; cod = OD + 2 * FIT + 2.0;
    difference() {
        union() {
            along(X_CI - REAR_WALL, X_CI + cup) circle(d = cod);
            hull() {
                along(X_CI + 0.8, X_CI + cup) p2_at(PHI_SENS, cod / 2 + 0.6) square([2.6, HALL[0] + 2], center = true);
                along(X_CI - REAR_WALL, X_CI - REAR_WALL + 0.1) p2_at(PHI_SENS, cod / 2 - 1) square([0.2, HALL[0] + 2], center = true);
            }
            rotate([90, 0, 0]) cylinder(d = EYE_OD, h = EYE_W, center = true);
            translate([0, -EYE_W / 2, -EYE_OD * 0.35]) cube([X_CI - REAR_WALL + eps, EYE_W, EYE_OD * 0.7]);
        }
        along(X_CI, X_CI + cup + 1) circle(d = OD + 2 * FIT);
        translate([X_CI + PUCK / 2, 0, 0]) rotate([PHI_SENS, 0, 0])
            translate([-HALL[1] / 2, -HALL[0] / 2, OD / 2 + FIT + 0.3]) cube([HALL[1], HALL[0], HALL[2] + 2]);
        rotate([90, 0, 0]) cylinder(d = PIN, h = 20, center = true);
    }
}

// Вушко штока: M5 вкручується в шийку (нарізає PLA сама) і садиться на клей
module rod_eye(e = 0) {
    translate([L0 + e, 0, 0]) difference() {
        union() {
            rotate([90, 0, 0]) cylinder(d = EYE_OD, h = EYE_W, center = true);
            translate([-EYE_LEN, -EYE_W / 2, -EYE_OD * 0.35]) cube([EYE_LEN - PIN / 2, EYE_W, EYE_OD * 0.7]);
            translate([-EYE_LEN, 0, 0]) rotate([0, 90, 0]) cylinder(d = min(NOSE_D, EYE_OD * 0.7), h = EYE_LEN - EYE_R + 1);
        }
        rotate([90, 0, 0]) cylinder(d = PIN, h = 20, center = true);
        translate([-EYE_LEN - 1, 0, 0]) rotate([0, 90, 0]) cylinder(d = 4.2, h = EYE_LEN - PIN / 2 - 0.8 + 1);
    }
}

// -----------------------------------------------------------------------------
//  Покупне (для збірки й розрізу)
// -----------------------------------------------------------------------------
module screw(e = 0) { translate([X_CI + e, 0, 0]) rotate([0, 90, 0]) cylinder(d = M5_D, h = SCREW_L, $fn = 24); }
module nut() { along(X_GEAR + (GEAR_B - M5_NUT_H) / 2, X_GEAR + (GEAR_B + M5_NUT_H) / 2)
    difference() { rotate(30 + PHI) circle(d = M5_NUT_S / cos(30), $fn = 6); circle(d = M5_D); } }
module bearing() { along(X_BRG, X_BRG + BRG[2]) difference() { circle(d = BRG[1]); circle(d = BRG[0]); } }
module motor() {
    along(X_HR - N20_GB, X_HR) motor_profile();
    along(X_HR - N20_GB - N20_MOT, X_HR - N20_GB) intersection() { motor_profile(); p2_at(PHI, A) circle(d = N20_W); }
    along(X_HR, X_HR + N20_SHAFT[2]) p2_at(PHI, A) d_shaft(0);
}
module d_shaft(c) {                  // вал N20 з лиською (у профілі, центр — у початку)
    intersection() { circle(d = N20_SHAFT[0] + c, $fn = 24);
                     translate([N20_SHAFT[1] - N20_SHAFT[0] / 2 + c / 2 - 4, -2]) square(4); }
}
module magnets(e = 0) {
    for (a = [0, 180]) translate([X_GEAR + GEAR_B - MAG_ENC[1], 0, 0]) rotate([PHI + a, 0, 0])
        translate([0, R_MAG, 0]) rotate([0, 90, 0]) cylinder(d = MAG_ENC[0], h = MAG_ENC[1], $fn = 24);
    translate([X_CI + PUCK / 2 + e, 0, 0]) rotate([PHI_SENS, 0, 0])
        translate([0, ID / 2 - 0.15 - MAG_LIM[1], 0]) rotate([-90, 0, 0]) cylinder(d = MAG_LIM[0], h = MAG_LIM[1], $fn = 24);
}
module halls() {
    for (a = ENC_ANG) translate([X_HF - HALL[2] + 0.05, 0, 0]) rotate([a, 0, 0])
        translate([0, R_MAG - HALL[1] / 2 + 0.05, -HALL[0] / 2 + 0.05]) cube([HALL[2] - 0.1, HALL[1] - 0.1, HALL[0] - 0.1]);
    translate([X_HR - PUCK / 2, 0, 0]) rotate([PHI_SENS, 0, 0]) translate([-HALL[1] / 2 + 0.05, -HALL[0] / 2 + 0.05, OD / 2 + 0.05]) cube([HALL[1] - 0.1, HALL[0] - 0.1, HALL[2] - 0.1]);
    translate([X_CI + PUCK / 2, 0, 0]) rotate([PHI_SENS, 0, 0]) translate([-HALL[1] / 2 + 0.05, -HALL[0] / 2 + 0.05, OD / 2 + FIT + 0.35]) cube([HALL[1] - 0.1, HALL[0] - 0.1, HALL[2] - 0.1]);
}
// колір деталі; у розрізі ріжеться кожна окремо — тоді площина розрізу має колір своєї деталі
$CUT = false;
module cutter() { rotate([PHI + 90, 0, 0]) translate([-10, 0, -50]) cube([400, 60, 100]); }
module cc(c) { color(c) if ($CUT) difference() { children(); cutter(); } else children(); }
module buy(e = 0) {
    cc([0.75, 0.76, 0.78]) screw(e);
    cc([0.7, 0.7, 0.72]) nut();
    cc([0.55, 0.57, 0.6]) bearing();
    cc([0.85, 0.7, 0.3]) motor();
    cc([0.8, 0.1, 0.1]) magnets(e);
    cc([0.15, 0.15, 0.15]) halls();
}
// окрема деталь за назвою — для перевірки перетинів (make.sh)
module piece(n, e) {
    if (n == "tube") tube(); else if (n == "head_rear") head_rear(); else if (n == "head_front") head_front();
    else if (n == "gear") nut_gear(); else if (n == "pinion") pinion(); else if (n == "cap") cap();
    else if (n == "puck") puck(e); else if (n == "eye") rod_eye(e); else if (n == "screw") screw(e);
    else if (n == "nut") nut(); else if (n == "bearing") bearing(); else if (n == "motor") motor();
    else if (n == "magnets") magnets(e); else if (n == "halls") halls();
    else echo(str("!!! невідома деталь: ", n));
}

module body_parts() {
    cc([0.2, 0.2, 0.22]) tube();
    cc([0.25, 0.45, 0.75]) head_rear();
    cc([0.3, 0.55, 0.85]) head_front();
    cc([0.9, 0.55, 0.15]) nut_gear();
    cc([0.95, 0.75, 0.2]) pinion();
    cc([0.2, 0.2, 0.22]) cap();
}
module rod_parts(e) {
    cc([0.35, 0.35, 0.38]) puck(e);
    cc([0.2, 0.2, 0.22]) rod_eye(e);
}
module cyl_asm(e) {
    body_parts();
    rod_parts(e);
    if (show_buy) buy(e);
}

// Нова геометрія без вушок (вушка — ті самі, що в моделі) — для перевірки зіткнень
cn_only = "";   // діагностика: лише одна деталь
module cyl_new(e) {
    difference() {
        if (cn_only != "") piece(cn_only, e);
        else union() { tube(); head_rear(); head_front(); cap(); buy(e); }
        translate([-50, -50, -50]) cube([X_CI - REAR_WALL + 50, 100, 100]);   // вушко бази й шийка
    }
}

// -----------------------------------------------------------------------------
//  Вибір
// -----------------------------------------------------------------------------
// Укладання на стіл: вісь X деталі — догори (деталі, що друкуються «стоячи»)
module up(x0) { rotate([0, -90, 0]) translate([-x0, 0, 0]) children(); }
module down(x0) { rotate([0, 90, 0]) translate([-x0, 0, 0]) children(); }

if (pp == "asm") cyl_asm(ext);
// розріз площиною через вісь шпильки й вал мотора; повернуто розрізом до −Y (камера 90,0,0)
else if (pp == "cut" || pp == "headcut") translate([pp == "headcut" ? -(X_HR + 6) : 0, 0, 0]) rotate([90 - PHI, 0, 0])
    let($CUT = true) cyl_asm(ext);
else if (pp == "tube")       up(X_CI) tube();
else if (pp == "head_rear")  up(X_HR) head_rear();
else if (pp == "head_front") up(X_FW) head_front();
else if (pp == "gear")       down(X_GEAR + GEAR_B) nut_gear();
else if (pp == "pinion")     up(X_GEAR) rotate([-PHI, 0, 0]) translate([0, 0, 0]) pinion_centered();
else if (pp == "puck")       up(X_CI) puck();
else if (pp == "cap")        down(X_CI + 5.5) cap();
else if (pp == "eye")        up(L0 - EYE_LEN) rod_eye();
else if (pp == "pair") intersection() { piece(pa, ext); piece(pb, ext); }
else if (pp == "collide") {
    // машина в позі (boom_angle, stick_angle, bucket_angle з -D), новий циліндр × деталь `with`
    P1 = cyl == "boom" ? C_w : cyl == "stick" ? pt_F(th_eff) : pt_H(th_eff, psi_eff);
    P2 = cyl == "boom" ? pt_D(th_eff) : cyl == "stick" ? pt_G(th_eff, psi_eff) : pt_J(th_eff, psi_eff, om_eff);
    Lm = norm(P2 - P1);
    intersection() {
        translate(p3(P1)) rotate([0, -ang2(P2 - P1), 0]) scale(SC) cyl_new((Lm - mv(cyl, "closed")) / SC);
        part_by_name(with);
    }
}
else if (pp != "none") echo(str("!!! невідома деталь: ", pp));

with = "m_stick";
pa = "tube"; pb = "motor";
module pinion_centered() { translate([0, -A * cos(PHI), -A * sin(PHI)]) pinion(); }

echo(str("=== M5 ", cyl, ": зведений ", L0, ", хід ", S, ", голова ", X_HR, "…", X_NOSE, ", шпилька ", SCREW_L,
         ", шестерні ", Z_NUT, "/", ZP, " a=", A, ", мотор ", MOTOR_NAME));
