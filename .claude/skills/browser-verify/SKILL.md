---
name: browser-verify
description: Перевірка вебсторінок проєкту (3D-сторінка з сервером, WASM-сторінка, статичний viewer.html) у headless Chrome — знімки, очікування готовності, зміна параметрів, підставні пристрої (WebHID, Gamepad), кадри для відео. Використовуй щоразу, коли змінюєш tools/viewer/ або tools/viewer-wasm/, перед словами «сторінка працює», і коли треба показати, як вона виглядає, — не обмежуйся curl чи збиранням без помилок.
---

# Перевірка сторінок у headless Chrome

Інструмент: `tools/media/page_shot.mjs` (опції — у шапці файлу). `puppeteer-core` свідомо не в `package.json` (зауваження `npm audit` у його залежностях) — один раз: `npm i --no-save --prefix tools/media puppeteer-core`.

```
python3 tools/viewer.py --port 8791 &                       # або: cd tools/viewer-wasm && npx vite preview --port 8797 --strictPort &
node tools/media/page_shot.mjs http://127.0.0.1:8791/ --out /tmp/shot.png --view Ізометрія
node tools/media/page_shot.mjs "http://127.0.0.1:8791/?boom_L1=1100&bucket_width=450" --out /tmp/changed.png   # параметри через адресу → перебудова
```
Код виходу 3 = на сторінці були помилки JS. Знімок обов'язково ВІДКРИЙ і подивись: «файл створено» нічого не доводить.

## Граблі, на які вже наступали
- `--virtual-time-budget` НЕ чекає веб-воркерів: WASM-сторінка знімається на «Завантажую рушій…». Чекай `window.__READY__` (сторінки ставлять його після першої побудови).
- `--dump-dom` зависає на сторінці з безперервним `requestAnimationFrame`.
- WebGL у headless: `--enable-unsafe-swiftshader --use-angle=swiftshader`. Перші кадри після побудови сцени повільні — тести руху починай після паузи ≈1 с.
- Сервер `viewer.py` має відкидати `?…` з адреси (інакше 404); `vite preview` потребує попереднього `vite build`.
- `file://`: WebHID і модулі з CDN працюють, модульні воркери — ні (WASM-версія лише через http).
- Зміна поля параметра з тесту: відкрити `<details>` групи, потрійний клік у `#p_НАЗВА input`, ввести значення, чекати в `#status` «змінено параметрів: N».
- Підставні пристрої ставляться ДО скриптів сторінки (`evaluateOnNewDocument`): зразок — `tools/viewer-wasm/test/spacemouse.mjs` (Gamepad API і WebHID). Це перевіряє логіку, а не залізо — так і кажи користувачеві.
- Після тестів зупини сервери (`pkill -f "viewer.py --port"`, `pkill -f "vite preview"`) і завислі `headless=new`.
