/* Ссылка на PDF листа всегда с превью. Запуск: node build/mkpdfwrap.mjs (в build/all.mjs после mkogfix; mkoffers зовёт сам).
   04.11.2026 Эльнур: «любая ссылка, пдф, на любом канале мессенджере, всегда даётся чётко с превью; я с личного тг отправил
   пдф по пурите и топ15, и они просто лысые без превью». Он отправил голые адреса /offers/<лист>/<файл>.pdf: у PDF нет
   Open Graph, Telegram и WhatsApp показывают пустую ссылку. Такой адрес раздавали кнопка «PDF ↓» на листе и карточки /predstart.
   Теперь у каждого PDF листа есть адрес /<лист>/<номер>/pdf/: маленькая страница с превью листа (те же og:image и описание),
   человека она сразу переводит на сам файл скриптом. Meta refresh здесь нарочно нет: часть ботов (Facebook, Instagram) по нему
   уходит, и тогда превью снова стало бы голым PDF. Скрипты боты не исполняют; без скрипта у человека кнопка «Открыть PDF».
   Это переадресация на файл, а не вторая копия листа (одна истина листа, 28.10 и 01.11, сторож build/mknomer.mjs).
   Проверка превью: node build/og_check.mjs (pre-push), живьём node build/og_check.mjs --live. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const unesc = s => String(s || '').replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const meta = (h, prop) => unesc((h.match(new RegExp('<meta (?:property|name)="' + prop + '" content="([^"]*)"')) || [])[1] || '');

const NOMERA = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/nomera.json'), 'utf8'));
let n = 0;
for (const [slug, nomer] of Object.entries(NOMERA)) {
  if (slug.startsWith('_')) continue;
  const dir = path.join(ROOT, 'offers', slug);
  const pdfs = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => /\.pdf$/i.test(f)) : [];
  if (pdfs.length !== 1) { if (pdfs.length > 1) console.log('⚠ mkpdfwrap ' + slug + ': PDF больше одного (' + pdfs.join(', ') + '), обёртку не пишу'); continue; }
  const лист = path.join(ROOT, slug, nomer, 'index.html');
  if (!fs.existsSync(лист)) { console.log('⚠ mkpdfwrap ' + slug + ': нет листа ' + slug + '/' + nomer + '/ (node build/mkoffers.mjs)'); continue; }
  const h = fs.readFileSync(лист, 'utf8');
  const title = meta(h, 'og:title'), desc = meta(h, 'og:description'), og = meta(h, 'og:image');
  if (!title || !og) { console.log('⚠ mkpdfwrap ' + slug + ': у листа нет og:title или og:image'); continue; }
  const файл = '/offers/' + slug + '/' + pdfs[0];
  /* метка версии, чтобы человек не получил старый PDF из кэша (как ?v= в пульте) */
  const v = crypto.createHash('sha1').update(fs.readFileSync(path.join(dir, pdfs[0]))).digest('hex').slice(0, 8);
  const to = encodeURI(файл) + '?v=' + v;
  const url = SITE + '/' + slug + '/' + nomer + '/pdf/';
  const t = esc(title + ' · PDF'), d = esc(desc), o = esc(og);
  const html = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<!-- PLP:PDFWRAP ${файл} -->
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${t}</title>
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="${d}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Property Library Phuket">
<meta property="og:title" content="${t}"><meta property="og:description" content="${d}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${o}"><meta property="og:image:secure_url" content="${o}">
<meta property="og:image:type" content="image/jpeg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="${t}"><meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${t}"><meta name="twitter:description" content="${d}">
<meta name="twitter:image" content="${o}"><meta name="twitter:image:alt" content="${t}">
<link rel="canonical" href="${url}">
<script>location.replace('${to}');</script>
</head><body style="margin:0;background:#0C0D09;color:#EFECE2;font-family:Manrope,system-ui,sans-serif;text-align:center">
<p style="padding:24px 16px 8px"><img src="${o}" alt="${t}" style="max-width:100%;width:600px;border-radius:12px"></p>
<p><a href="${to}" style="display:inline-block;padding:10px 18px;border:1px solid rgba(239,236,226,.4);border-radius:999px;color:#EFECE2;text-decoration:none">Открыть PDF</a></p>
</body></html>
`;
  const out = path.join(ROOT, slug, nomer, 'pdf', 'index.html');
  if (fs.existsSync(out) && fs.readFileSync(out, 'utf8') === html) continue;
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, html);
  n++;
  console.log('  PDF с превью: /' + slug + '/' + nomer + '/pdf/ → ' + файл);
}
console.log('mkpdfwrap: обёрток PDF обновлено ' + n);
