// Контури деталей стріли в перерізі — для креслення «де саме стають накладні деталі».
// Модель підключається як бібліотека і НЕ змінюється.
//
//   openscad -o out.svg -D 'part="none"' -D 'k="F_tower"' -D 'ycut=19.5' pos_cut.scad
//   openscad -o geo.echo -D 'part="none"' -D 'k=""' pos_cut.scad      // тільки числа
//
// projection(cut=true) ріже площиною z=0, а пластини вузла лежать у площині XZ
// (товщина — уздовж Y). Тому спершу translate підсуває потрібний зріз у y=0, і лише
// потім rotate([90,0,0]) кладе його на z=0. Зворотний порядок дає порожній файл:
// поворот уже переніс Y у Z, і зсув по Y нічого не ріже.

include <../scad/excavator_boom.scad>
assert(!is_undef(boom_tube_h) && !is_undef(cover_half), "scad/excavator_boom.scad не підключився");

k = "";        // ключ $sel деталі вузла "boom"
ycut = 0;      // на якій відстані вздовж Y брати переріз

if (k == "") {
    echo(GEO = [
        ["alpha1", boom_alpha1],                 // нахил 1-го сегмента до хорди
        ["u2_ang", boom_alpha1 - boom_bend],     // нахил 2-го сегмента
        ["K", K_l],                              // точка перелому у системі стріли
        ["D_org", D_org], ["D_u", D_u],          // початок і вісь кронштейна D
        ["F_hole", F_l], ["D_hole", D_l],        // центри отворів
        ["tube_h", boom_tube_h], ["tube_w", boom_tube_w],
        ["cover_t", plate_gusset], ["saddle_t", plate_boss], ["plate", plate_clevis],
        ["gap_F", clevis_gap_25], ["gap_D", clevis_gap_30],
        ["cover_half", cover_half], ["tower_fwd", tower_fwd]]);
} else {
    projection(cut = true) rotate([90, 0, 0]) translate([0, -ycut, 0]) {
        $sel = k; $one = true;
        part_by_name("boom");
    }
}
