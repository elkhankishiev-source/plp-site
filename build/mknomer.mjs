/* Сторож одной истины листов-офферов. Запуск: node build/mknomer.mjs (последний шаг build/all.mjs и проверка в pre-push).
   22.10.2026 Эльнур: «одна ссылка для всех, но с доп номером, просто название длиннее, чтобы его наугад не нашли» —
   скрытая ссылка (unlisted link): /<лист>/<номер>/, номера в build/nomera.json.
   До 28.10 этот файл копировал готовый <лист>.html в /<лист>/<номер>/index.html, и у листа было две живые страницы.
   28.10.2026 Эльнур: «копии не уместны… ищи все копии, дубли, доработай, своди в одну истину! это наше важное правило».
   Теперь лист пишет только build/mkoffers.mjs, сразу по номерному адресу; старые адреса там же становятся переадресацией.
   Здесь ничего не собирается, только проверка: копия листа вне номерного адреса или кривая переадресация = код 1. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const nomera = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/nomera.json'), 'utf8'));
const плохо = [];
const листы = new Set();

for (const [slug, nomer] of Object.entries(nomera)) {
  if (slug.startsWith('_')) continue;
  const f = path.join(slug, nomer, 'index.html');
  листы.add(f);
  if (!fs.existsSync(path.join(ROOT, f))) { плохо.push(f + ': нет листа (node build/mkoffers.mjs)'); continue; }
  const h = fs.readFileSync(path.join(ROOT, f), 'utf8');
  if (!h.includes('id="offerFrame"')) плохо.push(f + ': это не лист (нет offerFrame)');
  if (!h.includes('<link rel="canonical" href="' + SITE + '/' + slug + '/' + nomer + '/">')) плохо.push(f + ': canonical не на свой номерной адрес');
  /* 01.11.2026 Эльнур: «нужен ток один [адрес]». Лендинг рамки /offers/<лист>/page.htm вне рамки сам ведёт на номерной адрес */
  const lp = path.join(ROOT, 'offers', slug, 'page.htm');
  if (fs.existsSync(lp)) {
    const l = fs.readFileSync(lp, 'utf8').slice(0, 8000), to = '/' + slug + '/' + nomer + '/';
    if (!l.includes('PLP:ONEADDR') || !l.includes("location.replace('" + to + "'+location.search")) плохо.push('offers/' + slug + '/page.htm: вне рамки не ведёт на ' + to + ' (node build/mkoffers.mjs)');
    if (!l.includes('<link rel="canonical" href="' + SITE + to + '">')) плохо.push('offers/' + slug + '/page.htm: canonical не на ' + to);
  }
}

/* любая другая страница с рамкой листа = вторая копия */
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name.startsWith('.') || e.name === 'node_modules' || e.name === 'offers') continue;
    const p = path.join(d, e.name);
    if (e.isDirectory()) { walk(p); continue; }
    if (!e.name.endsWith('.html')) continue;
    const rel = path.relative(ROOT, p);
    if (листы.has(rel)) continue;
    const h = fs.readFileSync(p, 'utf8');
    if (/id="offerFrame"[^>]*src="\/offers\//.test(h)) плохо.push(rel + ': вторая копия листа (должна быть переадресация)');
    const m = h.match(/<!-- PLP:REDIRECT (\/[^ ]+\/) /);
    if (m) {
      if (!h.includes('<link rel="canonical" href="' + SITE + m[1] + '">')) плохо.push(rel + ': canonical переадресации не на ' + m[1]);
      if (!h.includes('url=' + m[1] + '"')) плохо.push(rel + ': refresh не на ' + m[1]);
      if (!fs.existsSync(path.join(ROOT, m[1], 'index.html'))) плохо.push(rel + ': ведёт на ' + m[1] + ', а листа там нет');
    }
  }
})(ROOT);

if (плохо.length) { console.log('[одна истина листов] ' + плохо.length + ':\n  ' + плохо.join('\n  ')); process.exit(1); }
console.log('[одна истина листов] ' + листы.size + ' листов, у каждого один адрес /<лист>/<номер>/, копий нет');
