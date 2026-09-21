import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
// Модель лежить поза текою сторінки (scad/excavator_boom.scad) і підключається як текст (?raw):
// у режимі dev правка .scad одразу перезавантажує сторінку, у build — модель вшивається в dist/.
// Політика безпеки вмісту — лише для зібраної сторінки: у dev Vite вставляє власні
// інлайн-скрипти (HMR), і CSP зламала б `npm run dev`. У dist/ інлайн-скриптів немає.
// Це другий рубіж, не перший: вхід із адреси перевіряє src/share.js. Але якщо колись
// у розмітку просочиться чужий рядок, браузер не дасть йому виконатися.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",      // WASM-рушій OpenSCAD; інлайн-скрипти заборонені
  "worker-src 'self' blob:",                   // рушій крутиться у веб-воркері
  "style-src 'self' 'unsafe-inline'",          // стилі сторінки лежать у <style>
  "img-src 'self' data: blob:",
  "connect-src 'self'",                        // нікуди не ходимо: ні телеметрії, ні CDN
  "object-src 'none'", "base-uri 'none'", "form-action 'none'",
  // frame-ancestors через <meta> браузер ігнорує — це лише заголовок. На GitHub Pages
  // заголовків не поставити, тож від вбудовування в чужу сторінку захисту немає;
  // сторінка нічого не зберігає й ніде не автентифікується, тож ціна цього нульова.
].join('; ');

const cspPlugin = {
  name: 'csp-meta',
  apply: 'build',
  transformIndexHtml: html => html.replace('<meta charset="utf-8">',
    `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${CSP}">`),
};

export default defineConfig({
  plugins: [cspPlugin],
  root: here,
  base: './',                                   // відносні шляхи: dist/ можна класти в будь-яку підтеку статичного хостингу
  server: { port: 8766, fs: { allow: [path.resolve(here, '../..')] } },
  preview: { port: 8767 },
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['openscad-wasm-prebuilt'] }, // 14 МБ з убудованим wasm — не передзбирати
  build: { target: 'esnext', chunkSizeWarningLimit: 20000, outDir: 'dist', emptyOutDir: true },
});
