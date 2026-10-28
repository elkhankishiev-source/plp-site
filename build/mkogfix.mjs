/* Картинка превью по теме страницы — последний шаг сборки.
   06.10.2026 Эльнур: «ссылки, которые мы отправляем, все без исключения должны иметь превью с красивой картинкой в тему ссылки».
   Нашёл: страницы предложений, гайдов и районов копируют шапку главной, и в мессенджере Vibe II, ZERO, гайды и районы
   показывали фото Heritage — чужой проект. Здесь, после всех сборщиков, каждой такой странице ставится своя картинка:
   оффер — его превью 1200×630, район — фото флагманского объекта района, гайды и /predstart — фирменная картинка. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';

function jpegSize(p) {
  try {
    const b = fs.readFileSync(p);
    let i = 2;
    while (i < b.length) {
      if (b[i] !== 0xFF) { i++; continue; }
      const m = b[i + 1], len = b.readUInt16BE(i + 2);
      if (m >= 0xC0 && m <= 0xC3) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
      i += 2 + len;
    }
  } catch (e) {}
  return null;
}

/* 28.10.2026 Эльнур: «копии не уместны… своди в одну истину». Лист живёт только по адресу /<лист>/<номер>/ (build/nomera.json),
   старые адреса (<лист>.html, <лист>/index.html, kuartz-fizz.html) — переадресации из build/mkoffers.mjs. Превью ставим листу
   и каждой его переадресации (их находим по canonical), чтобы мессенджер по старой ссылке показал ту же картинку. */
const ПРЕВЬЮ = { vibe2: 'offers/vibe2/img/preview-v13.jpg', 'zero-naiyang': 'offers/zero-naiyang/img/preview-v10.jpg',
  // 07.10 Эльнур: «превью ссылки соответствующее фото, не везде одно и то же» — /cg-capital и /aileen показывали Heritage
  'cg-capital': 'offers/cg-capital/img/preview-v10.jpg', aileen: 'offers/aileen/img/preview-v10.jpg',
  kuartz: 'offers/kuartz/img/preview-v11.jpg', fizz: 'offers/fizz/img/preview-v12.jpg', eden: 'offers/eden/img/preview-v10.jpg',
  millennium: 'offers/millennium/img/preview-v10.jpg',
  top15: 'offers/top15/img/preview-v4.jpg',
  purita: 'offers/purita/img/preview-v10.jpg',
  'naturale-kamala': 'offers/naturale-kamala/img/preview-v1.jpg' };
const НОМЕРА = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/nomera.json'), 'utf8'));
const ОФФЕРЫ = {};
const корневые = fs.readdirSync(ROOT).filter(f => f.endsWith('.html'))
  .concat(fs.readdirSync(ROOT, { withFileTypes: true }).filter(e => e.isDirectory() && fs.existsSync(path.join(ROOT, e.name, 'index.html'))).map(e => e.name + '/index.html'));
for (const [slug, img] of Object.entries(ПРЕВЬЮ)) {
  if (!НОМЕРА[slug]) continue;
  const адрес = SITE + '/' + slug + '/' + НОМЕРА[slug] + '/';
  ОФФЕРЫ[slug + '/' + НОМЕРА[slug] + '/index.html'] = img;
  for (const f of корневые)
    if (fs.readFileSync(path.join(ROOT, f), 'utf8').includes('<link rel="canonical" href="' + адрес + '">')) ОФФЕРЫ[f] = img;
}
const РАЙОНЫ = { 'bang-tao': 'PLP-SIERRA', kamala: 'PLP-VIVANA', kata: 'PLP-KATABELLO', 'koh-kaew': 'PLP-ZENITHY', layan: 'PLP-SUNHILLS-LAYAN',
  'nai-yang': 'PLP-ZERO-NAIYANG', rawai: 'PLP-FANTASY-RAWAI', surin: 'PLP-BIANCANA', karon: 'PLP-VIBE-KARON',
  laguna: 'PLP-BELLAGUNA', thalang: 'PLP-QABALAH', 'ao-por': 'PLP-TONINO-OV' };
/* 09.10.2026 Эльнур: «превью некрасивое… чтобы все превью ссылок были всегда красивыми, а не мертво-глухо».
   Главная, «Купить», «Аренда», «Управление», «О нас», «Добавить объект» наследовали шапку главной с фото Heritage,
   а /predstart и гайды — серую обложку. Теперь у каждой своя фирменная карточка 1200×630 (tools/og_objects.py --pages). */
const ФИРМЕННАЯ = fs.existsSync(path.join(ROOT, 'img/og/page-default.jpg')) ? 'img/og/page-default.jpg' : 'img/og-default.jpg';
const ГЛАВНЫЕ = { 'index.html': 'index', 'buy.html': 'buy', 'rent.html': 'rent', 'management.html': 'management',
  'about.html': 'about', 'predstart.html': 'predstart', 'add-property.html': 'add-property' };

const задания = [];
for (const [f, img] of Object.entries(ОФФЕРЫ)) задания.push([f, img]);
for (const [f, имя] of Object.entries(ГЛАВНЫЕ)) {
  const карточка = 'img/og/page-' + имя + '.jpg';
  задания.push([f, fs.existsSync(path.join(ROOT, карточка)) ? карточка : ФИРМЕННАЯ]);
}
for (const f of fs.readdirSync(path.join(ROOT, 'guide'))) if (f.endsWith('.html')) задания.push(['guide/' + f, ФИРМЕННАЯ]);
for (const f of fs.readdirSync(path.join(ROOT, 'districts'))) if (f.endsWith('.html')) {
  const код = РАЙОНЫ[f.replace(/\.html$/, '')];
  задания.push(['districts/' + f, код && fs.existsSync(path.join(ROOT, 'img', код + '.jpg')) ? 'img/' + код + '.jpg' : ФИРМЕННАЯ]);
}

let n = 0;
for (const [file, img] of задания) {
  const p = path.join(ROOT, file);
  if (!fs.existsSync(p) || !fs.existsSync(path.join(ROOT, img))) continue;
  let html = fs.readFileSync(p, 'utf8');
  const url = SITE + '/' + img;
  const sz = jpegSize(path.join(ROOT, img));
  const до = html;
  html = html.replace(/(<meta property="og:image" content=")[^"]*(")/, '$1' + url + '$2')
             .replace(/(<meta property="og:image:secure_url" content=")[^"]*(")/, '$1' + url + '$2')
             .replace(/(<meta name="twitter:image" content=")[^"]*(")/, '$1' + url + '$2');
  if (sz) html = html.replace(/(<meta property="og:image:width" content=")[^"]*(")/, '$1' + sz.w + '$2')
                     .replace(/(<meta property="og:image:height" content=")[^"]*(")/, '$1' + sz.h + '$2');
  /* 10.10.2026: Telegram в превью ссылки /eden показал общий заголовок «Агентство недвижимости на Пхукете» —
     он взял twitter:title/description, а там стоял текст главной. Метки twitter повторяют og этой страницы. */
  const огЗаг = (html.match(/<meta property="og:title" content="([^"]*)"/) || [])[1];
  const огОп = (html.match(/<meta property="og:description" content="([^"]*)"/) || [])[1];
  if (огЗаг) html = html.replace(/(<meta name="twitter:title" content=")[^"]*(")/, (m, a, b) => a + огЗаг + b);
  if (огОп) html = html.replace(/(<meta name="twitter:description" content=")[^"]*(")/, (m, a, b) => a + огОп + b);
  if (html !== до) { fs.writeFileSync(p, html); n++; }
}
console.log('превью по теме: обновлено страниц', n, 'из', задания.length);
