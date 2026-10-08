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

const ОФФЕРЫ = { 'vibe2.html': 'offers/vibe2/img/preview.jpg', 'zero-naiyang.html': 'offers/zero-naiyang/img/preview.jpg',
  // 07.10 Эльнур: «превью ссылки соответствующее фото, не везде одно и то же» — /cg-capital и /aileen показывали Heritage
  'cg-capital.html': 'offers/cg-capital/img/preview.jpg', 'aileen.html': 'offers/aileen/img/hero.jpg',
  'kuartz-fizz.html': 'offers/kuartz-fizz/img/preview.jpg',
  'kuartz.html': 'offers/kuartz/img/preview.jpg', 'fizz.html': 'offers/fizz/img/preview.jpg', 'eden.html': 'offers/eden/img/preview.jpg' };
const РАЙОНЫ = { 'bang-tao': 'PLP-SIERRA', kamala: 'PLP-VIVANA', kata: 'PLP-KATABELLO', 'koh-kaew': 'PLP-ZENITHY', layan: 'PLP-SUNHILLS-LAYAN',
  'nai-yang': 'PLP-ZERO-NAIYANG', rawai: 'PLP-FANTASY-RAWAI', surin: 'PLP-BIANCANA', karon: 'PLP-VIBE-KARON' };
const ФИРМЕННАЯ = 'img/og-default.jpg';

const задания = [];
for (const [f, img] of Object.entries(ОФФЕРЫ)) задания.push([f, img]);
задания.push(['predstart.html', ФИРМЕННАЯ]);
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
  if (html !== до) { fs.writeFileSync(p, html); n++; }
}
console.log('превью по теме: обновлено страниц', n, 'из', задания.length);
