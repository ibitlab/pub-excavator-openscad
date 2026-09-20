import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
// Модель лежить поза текою сторінки (scad/excavator_boom.scad) і підключається як текст (?raw):
// у режимі dev правка .scad одразу перезавантажує сторінку, у build — модель вшивається в dist/.
export default defineConfig({
  root: here,
  base: './',                                   // відносні шляхи: dist/ можна класти в будь-яку підтеку статичного хостингу
  server: { port: 8766, fs: { allow: [path.resolve(here, '../..')] } },
  preview: { port: 8767 },
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['openscad-wasm-prebuilt'] }, // 14 МБ з убудованим wasm — не передзбирати
  build: { target: 'esnext', chunkSizeWarningLimit: 20000, outDir: 'dist', emptyOutDir: true },
});
