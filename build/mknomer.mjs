/* 22.10.2026 Эльнур: «одна ссылка для всех, но с доп номером, просто название длиннее, чтобы его наугад не нашли».
   Это «скрытая ссылка» (unlisted link, как у YouTube и Google Drive): страница есть, но в меню, sitemap и поиске её нет,
   и угадать адрес по имени проекта нельзя. Номер у листа один для всех получателей.
   Здесь из готового <лист>.html делаем копию по адресу /<лист>/<номер>/: те же лист, PDF и счётчик site_events
   (в нём страница видна как /<лист>/<номер>, по ней считаем, сколько раз и когда открыли).
   Номера живут только в build/nomera.json, поменять номер = поменять там и пересобрать.
   Старые адреса /<лист> пока работают как были: по ним уже разосланы ссылки.
   Идёт последним шагом в build/all.mjs, после счётчиков и превью. Повторный прогон ничего не меняет. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const nomera = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/nomera.json'), 'utf8'));

for (const [slug, nomer] of Object.entries(nomera)) {
  if (slug.startsWith('_')) continue;
  const src = path.join(ROOT, slug + '.html');
  if (!fs.existsSync(src)) { console.log('mknomer: нет ' + slug + '.html, пропускаю (лист собирается отдельно)'); continue; }
  const url = SITE + '/' + slug + '/' + nomer;
  let html = fs.readFileSync(src, 'utf8');
  html = html.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + url + '$2');
  html = html.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + url + '$2');
  /* страница лежит на два уровня глубже: относительные пути переводим от корня сайта */
  html = html.replace(/(\s(?:src|href)=")(?![a-z]+:|\/|#|\?|data:|mailto:|tel:)([^"]+")/gi, '$1/$2');
  html = html.replace(/href="\/index\.html"/g, 'href="/"');
  /* и в скриптах главной, которые подставляют пути сами: знак в шапке и фото каталога */
  html = html.split("var want = pre + 'img/brand/").join("var want = '/img/brand/");
  html = html.split("p.img='img/'+").join("p.img='/img/'+");
  const dir = path.join(ROOT, slug, nomer);
  fs.mkdirSync(dir, { recursive: true });
  const out = path.join(dir, 'index.html');
  if (!fs.existsSync(out) || fs.readFileSync(out, 'utf8') !== html) fs.writeFileSync(out, html);
  console.log('mknomer: ' + url);
}
