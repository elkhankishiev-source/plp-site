/* 01.11.2026 Эльнур: «Один адрес листа, внутри переключатель RU/EN… Вторую копию не заводим».
   Английский листа = offers/<лист>/en.json (только слова, цифры остаются в page.htm). Переводит js/offer-lang.js на странице.
   Здесь сборочная проверка: каждый русский текст листа есть в en.json, места {0}… совпадают с числами узла,
   в английском нет своих цифр (цифры только из разметки) и нет кириллицы.
   node build/offer_lang.mjs <лист>            — проверка (код 1 при пропуске или ошибке)
   node build/offer_lang.mjs <лист> --skeleton — дописать в en.json недостающие ключи с пустым значением */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export const NUM = /\d+(?:[ \u00a0\u202f]\d{3})*(?:,\d+)?/g;
export const ключ = (t) => t.replace(NUM, '#');
const ent = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', laquo: '«', raquo: '»', mdash: '—', ndash: '–', middot: '·', thinsp: ' ', hellip: '…', times: '×', rarr: '→', larr: '←', darr: '↓', sup2: '²' };
const раскрой = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z0-9]+);/gi, (m, e) =>
  e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : +e.slice(1)) : (ent[e.toLowerCase()] ?? m));

/* те же узлы, что видит TreeWalker на странице: текст тела вне script/style, с кириллицей */
export function узлы(html) {
  let h = html.slice(html.search(/<body[\s>]/i));
  h = h.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<style[\s\S]*?<\/style>/gi, '').replace(/<noscript[\s\S]*?<\/noscript>/gi, '').replace(/<!--[\s\S]*?-->/g, '');
  return h.split(/<[^>]*>/).map((t) => раскрой(t).replace(/\s+/g, ' ').trim()).filter((t) => /[А-Яа-яЁё]/.test(t));
}

export function проверь(slug) {
  const dir = path.join(ROOT, 'offers', slug), fp = path.join(dir, 'en.json');
  if (!fs.existsSync(fp)) return null;
  const en = JSON.parse(fs.readFileSync(fp, 'utf8'));
  const все = узлы(fs.readFileSync(path.join(dir, 'page.htm'), 'utf8'));
  const нет = [], плохо = [], нужны = new Set();
  for (const t of все) {
    const k = ключ(t); нужны.add(k);
    const v = en[k];
    if (v == null || v === '') { нет.push(k); continue; }
    const n = (t.match(NUM) || []).length;
    const места = [...v.matchAll(/\{(\d+)\}/g)].map((m) => +m[1]);
    if (места.some((i) => i >= n)) плохо.push(k + ' → место {' + Math.max(...места) + '}, чисел ' + n);
    if (n && new Set(места).size < n) плохо.push(k + ' → в английском не все числа (' + new Set(места).size + ' из ' + n + ')');
    if (/\d/.test(v.replace(/\{\d+\}/g, '').replace(/\b(?:[A-Za-z]+\d+[A-Za-z\d]*|\d+[A-Za-z]+)\b/g, ''))) плохо.push(k + ' → своя цифра в английском: ' + v);
    if (/[А-Яа-яЁё]/.test(v)) плохо.push(k + ' → кириллица в английском');
  }
  const лишние = Object.keys(en).filter((k) => !нужны.has(k) && !k.startsWith('_'));
  return { всего: нужны.size, нет: [...new Set(нет)], плохо, лишние, en, fp };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const slug = process.argv[2];
  if (!slug) { console.error('node build/offer_lang.mjs <лист> [--skeleton]'); process.exit(2); }
  const fp = path.join(ROOT, 'offers', slug, 'en.json');
  if (process.argv.includes('--skeleton') && !fs.existsSync(fp)) fs.writeFileSync(fp, '{}\n');
  const r = проверь(slug);
  if (!r) { console.log(slug + ': нет en.json'); process.exit(0); }
  if (process.argv.includes('--skeleton')) {
    for (const k of r.нет) if (!(k in r.en)) r.en[k] = '';
    fs.writeFileSync(fp, JSON.stringify(r.en, null, 1) + '\n');
  }
  console.log(`${slug}: текстов ${r.всего}, без перевода ${r.нет.length}, ошибок ${r.плохо.length}, лишних ключей ${r.лишние.length}`);
  for (const k of r.нет.slice(0, 40)) console.log('  нет: ' + k);
  for (const k of r.плохо) console.log('  ошибка: ' + k);
  for (const k of r.лишние.slice(0, 20)) console.log('  лишний: ' + k);
  process.exit(r.нет.length || r.плохо.length ? 1 : 0);
}
