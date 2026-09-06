/* Чистые адреса без .html. Эльнур спрашивал дважды: «html в адресной строке —
   это нормально?». GitHub Pages отдаёт /buy и /object/heritage так же, как
   /buy.html (проверено curl), поэтому сами файлы остаются на месте — старые
   ссылки продолжают работать, — а вот все внутренние ссылки, canonical, og:url
   и sitemap переводим на короткий вид. Пути делаем от корня сайта, чтобы они
   одинаково работали и с главной, и из object/, и из districts/. */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const skip = new Set(['node_modules', '.git', 'build']);
function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (skip.has(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

/* «buy.html» относительно текущей страницы → «/buy» от корня сайта */
function clean(fileDir, href) {
  const m = /^([^#?]+)\.html([#?].*)?$/.exec(href);
  if (!m) return null;
  /* ссылка от корня сайта («/buy.html») резолвится от корня репозитория */
  const base = m[1].startsWith('/') ? path.join(ROOT, m[1] + '.html') : path.resolve(fileDir, m[1] + '.html');
  const target = base;
  if (!target.startsWith(ROOT)) return null;
  let rel = target.slice(ROOT.length).replace(/\\/g, '/');   // /object/heritage.html
  rel = rel.replace(/\.html$/, '');
  if (rel === '/index') rel = '/';
  return rel + (m[2] || '');
}

let files = 0, links = 0;
for (const file of walk(ROOT)) {
  const dir = path.dirname(file);
  let html = fs.readFileSync(file, 'utf8');
  const before = html;

  html = html.replace(/(href=")([^"]+?\.html(?:[#?][^"]*)?)(")/g, (all, a, href, b) => {
    if (/^(https?:|mailto:|tel:|\/\/)/i.test(href)) return all;
    const c = clean(dir, href);
    if (!c) return all;
    links++;
    return a + c + b;
  });
  /* canonical и og:url живут абсолютными — их чистим отдельно */
  html = html.replace(/(https:\/\/property-library\.com\/[^"'\s<>]*?)\.html/g, '$1')
             .replace(/https:\/\/property-library\.com\/index(["'\s<>])/g, 'https://property-library.com/$1');

  if (html !== before) { fs.writeFileSync(file, html); files++; }
}

/* sitemap — тот же короткий вид */
const sm = path.join(ROOT, 'sitemap.xml');
if (fs.existsSync(sm)) {
  let x = fs.readFileSync(sm, 'utf8');
  const b = x;
  x = x.replace(/(https:\/\/property-library\.com\/[^<\s]*?)\.html/g, '$1')
       .replace(/https:\/\/property-library\.com\/index</g, 'https://property-library.com/<');
  if (x !== b) fs.writeFileSync(sm, x);
}
console.log(`чистые адреса: страниц ${files}, ссылок ${links}`);
