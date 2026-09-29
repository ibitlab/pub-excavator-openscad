# versions/ — archive · архів

**English.** The current build is always in [`../latest/`](../latest/). A version lands here, under its own name, only when a newer build changes the geometry or the report numbers: `tools/build_version.sh` moves the old `latest/` here with `git mv`, the 1:5 printed kit and its sub-versions included. Cosmetic rebuilds (colours, renders, PDF style) refresh `latest/` in place instead.

V002–V005 are not in the tree: their STL and DXF were byte-identical to V001, and the only change in the numbers (the tooth reach, 2890 → 2904 mm) is carried by every later version. They stay in git as tags — `git checkout V004`, for example. V001 is kept as the starting point.

**Українською.** Поточне збирання завжди в [`../latest/`](../latest/). Версія потрапляє сюди, під своєю назвою, лише коли новіше збирання змінило геометрію чи числа звітів: `tools/build_version.sh` переносить старий `latest/` сюди через `git mv` — разом із друкованим набором 1:5 і його підверсіями. Косметичні перезбирання (кольори, рендери, стиль PDF) оновлюють `latest/` на місці.

V002–V005 у дереві немає: їхні STL і DXF були байт-у-байт такі самі, як у V001, а єдина зміна в числах (виліт зуба, 2890 → 2904 мм) є в кожній пізнішій версії. У git вони лишаються тегами — наприклад, `git checkout V004`. V001 збережено як точку відліку.
