// PDF предложения одной длинной страницей — как эталон Vibe II (Vibe2_Karon.pdf: 210 мм в ширину, весь лист целиком).
// 08.10.2026 Эльнур: «надо доделать так, чтобы я мог нажать и скачать ту же версию».
// Печатает сам лист предложения (offers/<slug>/page.htm) — в PDF ровно то, что на странице.
// Высоту страницы задаёт @page{size:210mm <высота>mm} в page.htm: если лист вырос — поднять высоту там.
// Печать через DevTools (Page.printToPDF) на листе 1,5 м зависала, file:// — тоже; работает Chrome из командной строки
// по локальному адресу. Потом картинки ужимаются до 150 dpi (29 МБ → около 3 МБ).
//   node tools/offer_longpdf.mjs cg-capital CentralGroup_Phuket.pdf
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [slug, name] = process.argv.slice(2);
if (!slug || !name) { console.error('node tools/offer_longpdf.mjs <slug> <файл.pdf>'); process.exit(1); }
const out = path.join(ROOT, 'offers', slug, name);
const raw = path.join(os.tmpdir(), 'offer_raw_' + slug + '.pdf');
const port = 8700 + Math.floor(Math.random() * 200);
const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
try {
  await new Promise((r) => setTimeout(r, 1000));
  execFileSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--disable-gpu',
    '--no-pdf-header-footer', '--virtual-time-budget=15000', '--print-to-pdf=' + raw,
    `http://127.0.0.1:${port}/offers/${slug}/page.htm?pdf=1`], { stdio: 'ignore', timeout: 120000 });
  execFileSync(path.join(os.homedir(), '.local/bin/uv'), ['run', '-q', '--python', '3.12', '--with', 'pymupdf', 'python', '-c',
    `import pymupdf,sys; d=pymupdf.open(sys.argv[1]); d.rewrite_images(dpi_threshold=160, dpi_target=150, quality=78); d.save(sys.argv[2], garbage=4, deflate=True); print(d.page_count, 'стр.')`,
    raw, out], { stdio: 'inherit', timeout: 180000 });
  console.log(out, (fs.statSync(out).size / 1e6).toFixed(1) + ' МБ');
} finally { srv.kill('SIGKILL'); fs.rmSync(raw, { force: true }); }
