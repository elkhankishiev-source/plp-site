/* Превью ссылки: чтобы любая наша ссылка в мессенджере открывалась картинкой и текстом.
   Эльнур 16.09.2026: «если кто-либо когда-либо из нас будет отправлять ссылку клиенту
   или куда-либо, каждая ссылка должна быть с превью — красивая соответствующая картинка».
   Служебные страницы (оффер, правила, 404) раньше уходили голой строкой. */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const SITE = 'https://property-library.com';
const IMG = SITE + '/img/og-default.jpg';
const MARK = '<!-- PLP:PREVIEW -->';

const PAGES = {
  'offer.html':   ['Персональное предложение · Property Library Phuket', 'Подборка объектов Пхукета, собранная под ваш запрос: цены, сроки, доходность.'],
  'privacy.html': ['Политика конфиденциальности · Property Library Phuket', 'Как мы обращаемся с данными, которые вы оставляете на сайте.'],
  'rules.html':   ['Правила сайта · Property Library Phuket', 'Условия использования сайта Property Library Phuket.'],
  'terms.html':   ['Условия работы · Property Library Phuket', 'На каких условиях мы подбираем и сопровождаем покупку на Пхукете.'],
  '404.html':     ['Страница не найдена · Property Library Phuket', 'Такой страницы нет. Каталог объектов Пхукета — на главной.'],
};

let done = 0;
for (const [file, [title, desc]] of Object.entries(PAGES)) {
  const p = path.join(ROOT, file);
  if (!fs.existsSync(p)) continue;
  let html = fs.readFileSync(p, 'utf8');
  if (html.includes(MARK)) {
    html = html.replace(new RegExp(MARK + '[\\s\\S]*?' + MARK, 'm'), MARK);
  }
  const url = SITE + '/' + file.replace(/\.html$/, '').replace(/^index$/, '');
  const block = [MARK,
    `<meta property="og:type" content="website">`,
    `<meta property="og:site_name" content="Property Library Phuket">`,
    `<meta property="og:title" content="${title}">`,
    `<meta property="og:description" content="${desc}">`,
    `<meta property="og:url" content="${url}">`,
    `<meta property="og:image" content="${IMG}">`,
    `<meta property="og:image:width" content="1200">`,
    `<meta property="og:image:height" content="630">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    `<meta name="twitter:title" content="${title}">`,
    `<meta name="twitter:description" content="${desc}">`,
    `<meta name="twitter:image" content="${IMG}">`,
    MARK].join('\n');
  if (html.includes(MARK)) html = html.replace(MARK, block);
  else html = html.replace(/<title>/, block + '\n<title>');
  fs.writeFileSync(p, html);
  done++;
}
console.log('превью ссылок: страниц дополнено ' + done);
