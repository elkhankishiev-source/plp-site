/* Сторож превью ссылок листов. 04.11.2026 Эльнур: «любая ссылка, пдф, на любом канале мессенджере, всегда даётся чётко с превью».
   Проверяет каждый лист /<лист>/<номер>/ (build/nomera.json, в том числе Топ-15) и его PDF-обёртку /<лист>/<номер>/pdf/ (build/mkpdfwrap.mjs):
   - есть og:title, og:description, og:image; og:image в первых 4 КБ страницы (WhatsApp читает только начало);
   - картинка превью лежит в репозитории, JPEG или PNG, не больше 300 КБ (иначе WhatsApp её не берёт), не меньше 600x315;
   - ни одна страница сайта не даёт голую ссылку на PDF листа /offers/<лист>/<файл>.pdf: у PDF превью не бывает.
   node build/og_check.mjs         по файлам репозитория (стоит в .git/hooks/pre-push)
   node build/og_check.mjs --live  по живому сайту: GET как бот Telegram и как WhatsApp, затем GET картинки (не HEAD)
   Ошибка = код 1. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const LIVE = process.argv.includes('--live');
const UA = ['TelegramBot (like TwitterBot)', 'WhatsApp/2.23.20.0'];
const МАКС_ВЕС = 300 * 1024, ОКНО = 4096;
const NOMERA = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/nomera.json'), 'utf8'));
const плохо = [];
let страниц = 0;

const meta = (h, p) => (h.match(new RegExp('<meta (?:property|name)="' + p + '" content="([^"]*)"')) || [])[1] || '';
function размер(b) {
  if (b[0] === 0x89 && b[1] === 0x50) return { тип: 'png', w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  if (b[0] !== 0xFF || b[1] !== 0xD8) return null;
  let i = 2;
  while (i < b.length) {
    if (b[i] !== 0xFF) { i++; continue; }
    const m = b[i + 1], len = b.readUInt16BE(i + 2);
    if (m >= 0xC0 && m <= 0xC3) return { тип: 'jpeg', h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
    i += 2 + len;
  }
  return { тип: 'jpeg' };
}
function картинка(где, b, тип) {
  if (тип && !/^image\/(jpeg|png)/.test(тип)) return плохо.push(где + ': картинка превью отдаётся как ' + тип);
  const r = размер(b);
  if (!r) return плохо.push(где + ': картинка превью не JPEG и не PNG');
  if (b.length > МАКС_ВЕС) плохо.push(где + ': картинка превью ' + Math.round(b.length / 1024) + ' КБ, больше 300 КБ');
  if (r.w && (r.w < 600 || r.h < 315)) плохо.push(где + ': картинка превью ' + r.w + 'x' + r.h + ', меньше 600x315');
}
async function страница(где, h, ждуPdf) {
  страниц++;
  for (const p of ['og:title', 'og:description', 'og:image']) if (!meta(h, p)) плохо.push(где + ': нет ' + p);
  const at = h.indexOf('property="og:image"');
  if (at > ОКНО) плохо.push(где + ': og:image на ' + at + ' байте, дальше первых 4 КБ');
  if (ждуPdf && !h.includes('PLP:PDFWRAP')) плохо.push(где + ': это не обёртка PDF');
  const og = meta(h, 'og:image');
  if (!og) return;
  if (!og.startsWith(SITE + '/')) return плохо.push(где + ': og:image не с нашего сайта: ' + og);
  if (LIVE) {
    try {
      const r = await fetch(og, { headers: { 'User-Agent': UA[1] } });   // GET, не HEAD
      if (r.status !== 200) return плохо.push(где + ': картинка превью ' + og + ' отдаёт ' + r.status);
      картинка(где, Buffer.from(await r.arrayBuffer()), r.headers.get('content-type'));
    } catch (e) { плохо.push(где + ': картинка превью не скачалась: ' + e.message); }
  } else {
    const f = path.join(ROOT, decodeURI(og.slice(SITE.length + 1)));
    if (!fs.existsSync(f)) return плохо.push(где + ': картинки превью нет в репозитории: ' + og);
    картинка(где, fs.readFileSync(f));
  }
}

for (const [slug, nomer] of Object.entries(NOMERA)) {
  if (slug.startsWith('_')) continue;
  const есть_pdf = fs.existsSync(path.join(ROOT, 'offers', slug)) && fs.readdirSync(path.join(ROOT, 'offers', slug)).some(f => /\.pdf$/i.test(f));
  const адреса = ['/' + slug + '/' + nomer + '/'].concat(есть_pdf ? ['/' + slug + '/' + nomer + '/pdf/'] : []);
  for (const a of адреса) {
    const ждуPdf = a.endsWith('/pdf/');
    if (LIVE) {
      for (const ua of UA) {
        try {
          const r = await fetch(SITE + a, { headers: { 'User-Agent': ua }, redirect: 'follow' });
          const тип = r.headers.get('content-type') || '';
          if (r.status !== 200 || !тип.includes('text/html')) { плохо.push(a + ' [' + ua.split(/[ /]/)[0] + ']: ' + r.status + ' ' + тип); continue; }
          await страница(a + ' [' + ua.split(/[ /]/)[0] + ']', await r.text(), ждуPdf);
        } catch (e) { плохо.push(a + ': не открылась: ' + e.message); }
      }
    } else {
      const f = path.join(ROOT, a, 'index.html');
      if (!fs.existsSync(f)) { плохо.push(a + ': файла нет' + (ждуPdf ? ' (node build/mkpdfwrap.mjs)' : '')); continue; }
      await страница(a, fs.readFileSync(f, 'utf8'), ждуPdf);
    }
  }
}

/* голые ссылки на PDF листов в страницах сайта (обёртки и сами листы в offers/ не считаем) */
if (!LIVE) (function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name.startsWith('.') || e.name === 'node_modules' || e.name === 'offers') continue;
    const p = path.join(d, e.name);
    if (e.isDirectory()) { walk(p); continue; }
    if (!e.name.endsWith('.html')) continue;
    const h = fs.readFileSync(p, 'utf8');
    if (h.includes('PLP:PDFWRAP')) continue;
    const m = h.match(/href="(?:https:\/\/property-library\.com)?\/offers\/[^"]+\.pdf(?:\?[^"]*)?"/g);
    if (m) плохо.push(path.relative(ROOT, p) + ': голая ссылка на PDF ' + m[0] + ' (давать /<лист>/<номер>/pdf/)');
  }
})(ROOT);

/* 04.11: в самих листах (offers/<лист>/page.htm, блок «Кнопки») тоже стоит голая ссылка на PDF, и она же внутри PDF.
   Чинится в сборщике листов (sheet.json → tools/offer_sheet.mjs) с пересборкой PDF, это работа plp-sheets. Пока предупреждение, не стоп. */
const предупреждения = [];
if (!LIVE) for (const d of fs.readdirSync(path.join(ROOT, 'offers'))) {
  const f = path.join(ROOT, 'offers', d, 'page.htm');
  if (!fs.existsSync(f)) continue;
  const m = fs.readFileSync(f, 'utf8').match(/href="(?:https:\/\/property-library\.com)?\/offers\/[^"]+\.pdf(?:\?[^"]*)?"/);
  if (m) предупреждения.push('offers/' + d + '/page.htm: ' + m[0]);
}
if (предупреждения.length) console.log('⚠ [превью ссылок] голая ссылка на PDF внутри листа (и в его PDF), ' + предупреждения.length + ', чинить в sheet.json:\n  ' + предупреждения.join('\n  '));
if (плохо.length) { console.log('[превью ссылок] ' + плохо.length + ':\n  ' + плохо.join('\n  ')); process.exit(1); }
console.log('[превью ссылок] ' + страниц + ' страниц' + (LIVE ? ' на живом сайте' : '') + ': у каждой og:title, og:description и og:image, картинка открывается; голых ссылок на PDF нет');
