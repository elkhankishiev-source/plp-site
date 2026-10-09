// PDF предложения одной длинной страницей — как эталон Vibe II (Vibe2_Karon.pdf: 210 мм в ширину, весь лист целиком).
// 08.10.2026 Эльнур: «надо доделать так, чтобы я мог нажать и скачать ту же версию».
// Печатает сам лист предложения (offers/<slug>/page.htm) — в PDF ровно то, что на странице.
// Высоту страницы задаёт @page{size:210mm <высота>mm} в page.htm с запасом; пустой низ обрезается сам (08.10).
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
let prof = ''; // 09.10.2026: профиль Chrome удаляем за собой (накопилось 137 штук, 1,8 ГБ)
const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
try {
  await new Promise((r) => setTimeout(r, 1000));
  // 08.10.2026: Chrome печатает за ~30 с, но потом не выходит (висит его обновлятор) — ждём, пока файл допишется, и закрываем сами.
  const ch = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--disable-gpu',
    '--user-data-dir=' + (prof = fs.mkdtempSync(path.join(os.tmpdir(), 'pdfprof-'))), '--no-pdf-header-footer', '--virtual-time-budget=15000',
    '--print-to-pdf=' + raw, `http://127.0.0.1:${port}/offers/${slug}/page.htm?pdf=1`], { stdio: 'ignore' });
  let прошлый = -1, ровно = 0;
  for (let i = 0; i < 90 && ровно < 3; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const n = fs.existsSync(raw) ? fs.statSync(raw).size : 0;
    ровно = (n > 0 && n === прошлый) ? ровно + 1 : 0; прошлый = n;
  }
  try { ch.kill('SIGKILL'); } catch (e) {}
  if (!fs.existsSync(raw)) throw new Error('Chrome не напечатал PDF за 3 минуты');
  execFileSync(path.join(os.homedir(), '.local/bin/uv'), ['run', '-q', '--python', '3.12', '--with', 'pymupdf', 'python', '-c',
    `import pymupdf,sys
d=pymupdf.open(sys.argv[1])
# 09.10.2026 Эльнур: «скачал PDF — не одна сплошная страница, на второй текст и длинное пустое поле». Лист длиннее @page (2400 мм) —
# Chrome рвёт его на страницы. Склеиваем все страницы в одну, у последней берём высоту до последнего текста.
def _низ(pg):
    bl=pg.get_text('blocks'); return max(b[3] for b in bl) if bl else 0
W=d[0].rect.width; части=[]
for i,pg in enumerate(d):
    h=pg.rect.height if i<d.page_count-1 else min(pg.rect.height,_низ(pg)+28)
    if h>1: части.append((i,h))
o=pymupdf.open(); итог=sum(h for i,h in части); np=o.new_page(width=W,height=итог); y=0
for i,h in части:
    np.show_pdf_page(pymupdf.Rect(0,y,W,y+h), d, i, clip=pymupdf.Rect(0,0,W,h)); y+=h
d=o; h=итог
d.rewrite_images(dpi_threshold=160, dpi_target=150, quality=78); d.save(sys.argv[2], garbage=4, deflate=True); print(d.page_count, 'стр.', round(h/72*25.4), 'мм')`,
    raw, out], { stdio: 'inherit', timeout: 180000 });
  console.log(out, (fs.statSync(out).size / 1e6).toFixed(1) + ' МБ');
} finally { srv.kill('SIGKILL'); fs.rmSync(raw, { force: true }); if (prof) fs.rmSync(prof, { recursive: true, force: true }); }

// 09.10.2026: Chrome иногда печатает до того, как догрузились картинки (Vibe II: 22 из 24, Aileen: половина).
// Сверяем число картинок в PDF с листом; меньше — пересобираем ещё раз (до двух повторов).
{
  const html = fs.readFileSync(path.join(ROOT, 'offers', slug, 'page.htm'), 'utf8');
  const нужно = (html.match(/<img[^>]+src="(?!data:)/g) || []).length;
  const сколько = () => +execFileSync(path.join(os.homedir(), '.local/bin/uv'), ['run', '-q', '--python', '3.12', '--with', 'pymupdf', 'python', '-c',
    'import pymupdf,sys;print(len(pymupdf.open(sys.argv[1])[0].get_images()))', out]).toString().trim();
  let есть = сколько();
  if (есть < нужно && !process.env.PDF_RETRY) {
    for (let i = 0; i < 2 && есть < нужно; i++) {
      console.log('картинок в PDF', есть, 'из', нужно, '— пересобираю');
      execFileSync(process.execPath, [process.argv[1], slug, name], { stdio: 'inherit', env: { ...process.env, PDF_RETRY: '1' } });
      есть = сколько();
    }
  }
  console.log('картинок в PDF', есть, 'из', нужно, есть < нужно ? '⚠️ НЕ ВСЕ' : '✓');
}
