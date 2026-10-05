// PDF закрытых предложений по одному стандарту (05.10.2026).
// Эльнур: «какие страшные PDF-офферы, очень нелогичные и не по стандартам». Были распечатки веб-страниц, один PDF — лента 1,2 м.
// Стандарт: A4, одна-две страницы. Шапка бренда → фото (если есть) → название, район, метка → два абзаца сути →
// таблица планировок (если есть) → «что важно знать» → один призыв (WhatsApp Эльнура с готовым текстом) → источник и дата. Данные — CARDS из build/mkoffers.mjs,
// фото — из каталога/папки предложения. Цифр от себя не добавляем.
// НЕ ЗАПУСКАТЬ (05.10 Эльнур: «эталон пдф на офер это карон вайб 2 или лучше! другие стремное не надо»).
// Этот сборщик делал одностраничные листы хуже эталона и затёр PDF Vibe II и ZERO.
//   node tools/offer_pdf.mjs            — пересобрать все PDF предложений
import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os'; import { spawn } from 'node:child_process';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const src = fs.readFileSync(path.join(ROOT, 'build/mkoffers.mjs'), 'utf8');
const i = src.indexOf('const CARDS = ['); const j = src.indexOf('\n];', i);
const CARDS = new Function('return ' + src.slice(i + 'const CARDS = '.length, j + 2))();
const ФОТО = {   // главное фото предложения: каталог (R2) или папка предложения на сайте
  'The ZERO Nai Yang': 'https://pub-8e4357d7dd6c4c018600cb6d37990142.r2.dev/objects/PLP-ZERO-NAIYANG/exterior/c89b25feead6ed06-1600.webp',
  'Vibe II': 'file://' + path.join(ROOT, 'offers/vibe2/img/preview.jpg'),
};
const WA = 'https://wa.me/66955492587?text=';   // рабочий WhatsApp Эльнура, как у кнопок на странице предложений
const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/(\d) (?=\d)/g, '$1\u00a0').replace(/ (м²|млн|тыс\.)/g, '\u00a0$1');   // число не рвём по строкам
const сегодня = new Date().toLocaleDateString('ru-RU', { timeZone: 'Asia/Bangkok', day: '2-digit', month: '2-digit', year: 'numeric' });

function html(c) {
  const фото = ФОТО[c.name];
  const планы = (c.plans || []).map(([t, a]) => `<tr><td>${esc(t)}</td><td>${esc(a)}</td></tr>`).join('');
  const текст = c.ask || 'Здравствуйте! Пришлите, пожалуйста, презентацию ' + c.name;
  return `<!doctype html><html lang="ru"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
<style>
@page{size:A4;margin:0}
*{box-sizing:border-box}
body{margin:0;font-family:Manrope,Arial,sans-serif;color:#2A2A22;background:#EFECE2}
.page{width:210mm;min-height:297mm;padding:14mm 15mm 12mm;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;font-size:9pt;color:#5E6B35;letter-spacing:.04em;text-transform:uppercase;font-weight:800}
.top span:last-child{color:#8A8775;font-weight:600;text-transform:none;letter-spacing:0}
.hero{margin:7mm 0 6mm;height:${фото ? '92mm' : '0'};border-radius:5mm;overflow:hidden;background:#D2D5B3}
.hero img{width:100%;height:100%;object-fit:cover;display:block}
.tag{display:inline-block;background:#5E6B35;color:#EFECE2;font-size:9pt;font-weight:800;padding:1.6mm 3.5mm;border-radius:20mm;margin-bottom:3mm}
h1{font-size:30pt;line-height:1.05;margin:0 0 1.5mm;font-weight:800;color:#1E2017}
.where{font-size:12pt;color:#5E6B35;font-weight:600;margin-bottom:6mm}
p{font-size:11pt;line-height:1.55;margin:0 0 3.5mm}
table{width:100%;border-collapse:collapse;margin:3mm 0 5mm;font-size:10.5pt}
th{text-align:left;background:#5E6B35;color:#EFECE2;padding:2.5mm 3mm;font-weight:800}
td{padding:2.2mm 3mm;border-bottom:.3mm solid #D2D5B3;background:#F6F4EC}
.note{background:#F6F4EC;border-left:1.2mm solid #B4533A;padding:3.5mm 4mm;border-radius:2mm;font-size:10.5pt;line-height:1.5;margin:2mm 0 5mm}
.cta{text-decoration:none;margin-top:auto;background:#1E2017;color:#EFECE2;border-radius:4mm;padding:5mm 6mm;display:flex;justify-content:space-between;align-items:center}
.cta b{font-size:13pt}.cta span{font-size:10pt;color:#D2D5B3}
.foot{font-size:8pt;color:#8A8775;margin-top:3mm;line-height:1.4}
</style></head><body><div class="page">
<div class="top"><span>Property Library Phuket · закрытое предложение</span><span>${сегодня}</span></div>
${фото ? `<div class="hero"><img src="${фото}"></div>` : '<div style="height:10mm"></div>'}
<div><span class="tag">${esc(c.tag)}</span></div>
<h1>${esc(c.name)}</h1><div class="where">${esc(c.where)}, Пхукет</div>
${(c.text || []).map((t) => `<p>${esc(t)}</p>`).join('')}
${планы ? `<table><tr><th>Планировка</th><th>Площадь</th></tr>${планы}</table>` : ''}
${c.note ? `<div class="note">${esc(c.note)}</div>` : ''}
<a class="cta" href="${WA}${encodeURIComponent(текст)}"><div><b>Получить презентацию</b><br><span>WhatsApp +66 95 549 2587</span></div><span>Эльнур Ханкишиев</span></a>
<div class="foot">Источники: данные застройщика и открытые публикации на ${сегодня}. Цена и наличие подтверждаются на дату брони. Не является публичной офертой.</div>
</div></body></html>`;
}

async function печать(htmlPath, out) {
  // Chrome сам печатает в файл; после печати он иногда не выходит, поэтому ждём файл и закрываем его сами
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'opdf-')); const tmp = path.join(dir, 'out.pdf');
  const ch = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--allow-file-access-from-files', '--user-data-dir=' + dir,
    '--no-pdf-header-footer', '--virtual-time-budget=8000', '--print-to-pdf=' + tmp, 'file://' + htmlPath], { stdio: 'ignore' });
  const ждать = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    let был = -1;
    for (let k = 0; k < 120; k++) {
      await ждать(500);
      const р = fs.existsSync(tmp) ? fs.statSync(tmp).size : 0;
      if (р > 0 && р === был) break; был = р;
    }
    if (!(был > 0)) throw new Error('Chrome не напечатал ' + out);
    fs.copyFileSync(tmp, out);
  } finally { try { ch.kill('SIGKILL'); } catch (e) {} await ждать(400); try { fs.rmSync(dir, { recursive: true, force: true }); } catch (e) {} }
}

for (const c of CARDS) {
  if (!c.pdf) continue;
  const out = path.join(ROOT, c.pdf.replace(/^\//, ''));
  const h = path.join(os.tmpdir(), 'offer_' + Date.now() + '.html'); fs.writeFileSync(h, html(c));
  await печать(h, out); fs.rmSync(h, { force: true });
  console.log(c.name, '→', c.pdf, fs.statSync(out).size, 'байт');
}
