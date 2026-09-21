/* Страница «О нас» (/about). Эльнур 15.09: «О нас» больше не блок в середине главной,
   а своя страница. Собирается из index.html так же, как management и гайды: шапка,
   стили, скрипты и словари — с главной, содержимое — из build/parts/about-*.html
   (дословно перенесённые с главной блоки) и живых кусков главной (кейсы, заявка).

   🔒 Подача (память plp-positioning-quiet-consulting): без документов, лицензий,
   офиса, юрлица и оправданий. В разметке Organization — ни адреса, ни телефона. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const P = f => fs.readFileSync(path.join(ROOT, 'build/parts', f), 'utf8');

const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const mStart = idx.indexOf('<main'), mOpen = idx.indexOf('>', mStart) + 1, mEnd = idx.indexOf('</main>');
const head = idx.slice(0, mOpen), tail = idx.slice(mEnd);

function grabPart(name) {
  const a = idx.indexOf(`<!-- PLP:PART:${name}:START -->`);
  const b = idx.indexOf(`<!-- PLP:PART:${name}:END -->`);
  if (a === -1 || b === -1 || b < a) throw new Error('нет куска главной: ' + name);
  return idx.slice(a + `<!-- PLP:PART:${name}:START -->`.length, b);
}

const HERO = `<section style="padding-bottom:32px"><div class="container">
  <span class="kicker" data-i18n="nav.about">О нас</span>
  <h1 style="font-size:clamp(30px,4.6vw,48px);margin:6px 0 12px">Property Library Phuket</h1>
  <p class="sub" style="max-width:62ch;margin:0" data-i18n="ft.tag">Мы уже выбрали Пхукет, поможем и вам. Все под ключ — от первого звонка до заезда и получения дохода.</p>
</div></section>`;

/* 21.09: сюда я сначала добавил полосу фактов с главной — и увидел на снимке,
   что те же четыре цифры уже стоят в рассказе основателя. Две одинаковые полосы
   подряд читаются как сбой вёрстки. Факты остаются там, где они и были: рядом
   с человеком, который за них отвечает. */

/* Порядок страницы «О нас» — по тому, в каком порядке человек задаёт вопросы:
   кто вы → чем докажете → как работаете → с кем уже сделали → что ещё берёте
   на себя → как начать. Раньше три блока обещаний шли до единственной
   конкретики, а факты отсутствовали вовсе. */
const body = [
  HERO,
  P('about-founder.html'),          // кто мы + цифры: годы, сделки, объём
  P('about-steps.html'),            // как работаем: восемь шагов сделки
  grabPart('cases'),                // с кем уже сделали
  P('about-approach.html'),         // что ещё берём на себя
  `<section style="padding-top:0">${grabPart('final')}</section>`,
].join('\n');

const title = 'О нас — Property Library Phuket';
const desc = 'Кто мы и как работаем: основатель, наш подход, как проходит сделка и истории клиентов. Подбор, сделка и сопровождение на Пхукете под ключ.';
const url = SITE + '/about';

let html = head + '\n' + body + '\n' + tail;
html = html.replace(/<title>[\s\S]*?<\/title>/, '<title>' + esc(title) + '</title>');
html = html.replace(/(<meta name="description" content=")[^"]*(")/, '$1' + esc(desc) + '$2');
html = html.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + url + '$2');
html = html.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + url + '$2');
html = html.replace(/(<meta property="og:title" content=")[^"]*(")/, '$1' + esc(title) + '$2');
html = html.replace(/(<meta property="og:description" content=")[^"]*(")/, '$1' + esc(desc) + '$2');
/* разметка главной (агентство с адресом и каталог) этой странице не нужна */
const headEnd = html.indexOf('</head>');
html = html.slice(0, headEnd).replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>\s*/g, '') + html.slice(headEnd);
const org = {
  '@context': 'https://schema.org', '@type': 'Organization',
  name: 'Property Library Phuket', url: SITE,
  logo: SITE + '/img/brand/plp-mark-ink.png',
  sameAs: ['https://t.me/property_library_phuket', 'https://www.instagram.com/property.library.phuket/'],
};
html = html.replace('</head>', '<script type="application/ld+json">' + JSON.stringify(org) + '</script>\n</head>');
/* якоря главной со страницы «О нас» ведут на главную; #about здесь свой */
html = html.replace(/href="#top"/g, 'href="index.html"');
html = html.replace(/href="#(why|sale|rent|map|quiz|faq|do|contacts)"/g, 'href="index.html#$1"');

fs.writeFileSync(path.join(ROOT, 'about.html'), html);
console.log('about.html собран:', html.length, 'байт');
