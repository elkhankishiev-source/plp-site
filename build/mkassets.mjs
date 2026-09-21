/* Общий код сайта переезжает из каждой страницы в три отдельных файла.
   Эльнур 20.09.2026: «когда крутишь карточки, они как будто бы подвисают… блоки
   сайта организованы немного странно, чтобы не было перегруза, было всё
   эффективно и логично».

   Как было. Каждая страница несла ВНУТРИ СЕБЯ 133 КБ стилей и 865 КБ скрипта,
   из которых 574 КБ — каталог объектов. Шесть страниц (главная, покупка, аренда,
   о нас, управление, Vibe 2) носили один и тот же мегабайт. Браузер не может его
   переиспользовать: при каждом переходе он заново качает и заново разбирает весь
   код. Отсюда и «подвисает» — главный поток занят разбором, а не прокруткой.
   Отдельная беда: каталог жил в шести копиях и расходился между ними (18.09
   страницы отстали от главной на сборку и месяц показывали старые цены).

   Как стало:
     assets/app.css      — стили, один файл на весь сайт
     assets/catalog.js   — каталог продажи и аренды, ОДИН экземпляр
     assets/app.js       — код витрины
   Страницы подключают их тегами. Браузер качает каждый файл ОДИН раз и дальше
   берёт из кэша: переход «главная → аренда → покупка» перестаёт стоить мегабайт.

   Почему каталог отдельным файлом от кода. Каталог меняется каждую сборку (цены,
   статусы, фото), а код — редко. Разделив их, мы не сбрасываем кэш кода при
   каждом обновлении цен.

   Порядок подключения обязателен: catalog.js объявляет window.PL с каталогом,
   app.js его дочитывает. Поэтому в app.js `window.PL = {}` заменён на
   `window.PL = window.PL || {}` — иначе код затирал бы каталог при старте.

   Шаг идемпотентный: если страница уже облегчена, он только обновляет отпечаток
   версии в адресах (?v=…), чтобы браузер забрал свежий файл после правки.

       node build/mkassets.mjs
*/
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const ASSETS = path.join(ROOT, 'assets');

/* Страницы с общим кодом витрины. owner.html (кабинет) и add-property.html
   (анкета) живут на своём коде — их не трогаем. */
const PAGES = ['index.html', 'buy.html', 'rent.html', 'about.html',
               'management.html', 'vibe2.html'];

const AF = '/* PLP:ANTIFLICKER */';
const SALE_START = '/* ===== SALE CATALOG';
const RENT_END = '/* PLP:AUTO-RENTALS:END */';

const hash = s => crypto.createHash('md5').update(s).digest('hex').slice(0, 8);
const big = (html, tag) => {
  const re = new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`, 'g');
  let m;
  while ((m = re.exec(html)) !== null) if (m[1].length > 20000) return m;
  return null;
};

/* ——— 1. вынимаем общий код из главной, если он ещё внутри ——— */
function extract() {
  const file = path.join(ROOT, 'index.html');
  let html = fs.readFileSync(file, 'utf8');

  const st = big(html, 'style');
  if (st) {
    const css = st[1];
    /* начало стилей (фон страницы и защита от мигания) остаётся в странице:
       туда пишет build/mktheme.mjs, и эти правила обязаны примениться до
       первой отрисовки, иначе на телефоне мигает фон */
    const a = css.indexOf(AF), b = css.indexOf(AF, a + AF.length);
    const cut = b === -1 ? 0 : b + AF.length;
    fs.mkdirSync(ASSETS, { recursive: true });
    fs.writeFileSync(path.join(ASSETS, 'app.css'), css.slice(cut).trim() + '\n');
    html = html.slice(0, st.index) + '<style>\n' + css.slice(0, cut).trim() +
      '\n</style>\n<!-- PLP:ASSET-CSS -->' + html.slice(st.index + st[0].length);
    console.log('[assets] app.css:', (css.length - cut) / 1024 | 0, 'КБ вынесено из index.html');
  }

  const sc = big(html, 'script');
  if (sc) {
    const js = sc[1];
    const i = js.indexOf(SALE_START);
    const j = js.indexOf(RENT_END);
    if (i === -1 || j === -1) { console.error('[assets] каталог в коде не найден — прерываю'); process.exit(1); }
    const end = j + RENT_END.length;
    const catalog = js.slice(i, end);
    const code = (js.slice(0, i) + js.slice(end)).replace('window.PL = {};',
      'window.PL = window.PL || {};   /* каталог приходит из assets/catalog.js */');
    if (code.indexOf('window.PL = window.PL || {}') === -1) {
      console.error('[assets] не нашёл объявление window.PL — прерываю'); process.exit(1);
    }
    fs.mkdirSync(ASSETS, { recursive: true });
    fs.writeFileSync(path.join(ASSETS, 'catalog.js'),
      '/* Каталог витрины. Пишется build/gen.mjs из Supabase; вручную не править. */\n' +
      'window.PL = window.PL || {};\n' + catalog + '\n');
    fs.writeFileSync(path.join(ASSETS, 'app.js'), code.trim() + '\n');
    html = html.slice(0, sc.index) + '<!-- PLP:ASSET-JS -->' + html.slice(sc.index + sc[0].length);
    console.log('[assets] catalog.js:', catalog.length / 1024 | 0, 'КБ, app.js:', code.length / 1024 | 0, 'КБ');
  }
  if (st || sc) fs.writeFileSync(file, html);
}

/* ——— 2. расставляем теги на всех страницах с нужными отпечатками ——— */
function link() {
  const v = {
    css: hash(fs.readFileSync(path.join(ASSETS, 'app.css'))),
    cat: hash(fs.readFileSync(path.join(ASSETS, 'catalog.js'))),
    app: hash(fs.readFileSync(path.join(ASSETS, 'app.js'))),
  };
  const CSS_TAG = `<!-- PLP:ASSET-CSS --><link rel="stylesheet" href="/assets/app.css?v=${v.css}">`;
  const JS_TAG = `<!-- PLP:ASSET-JS --><script src="/assets/catalog.js?v=${v.cat}"></script>\n` +
                 `<script src="/assets/app.js?v=${v.app}"></script>`;
  /* 21.09: обновлять отпечатки только в шести страницах было мало. Районы, гайды
     и страницы объектов получают теги копированием из index.html на СВОИХ шагах
     сборки, то есть до этого. Пока каталог не менялся, отпечатки совпадали
     случайно; после первого же обновления цен районы понесли бы старый адрес и
     люди с тёплым кэшем видели бы вчерашние цифры. Проходим по всем страницам,
     где эти теги есть. */
  const страницы = new Set(PAGES);
  const обойти = dir => {
    for (const f of fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
      const п = (dir ? dir + '/' : '') + f.name;
      if (f.isDirectory()) { if (!/^(\.|node_modules|build|tools|img|assets)$/.test(f.name)) обойти(п); continue; }
      if (!f.name.endsWith('.html')) continue;
      if (fs.readFileSync(path.join(ROOT, п), 'utf8').includes('PLP:ASSET-')) страницы.add(п);
    }
  };
  обойти('');

  let n = 0;
  for (const f of страницы) {
    const full = path.join(ROOT, f);
    if (!fs.existsSync(full)) continue;
    let html = fs.readFileSync(full, 'utf8');
    const was = html;

    /* страница ещё носит код внутри себя — вырезаем так же, как на главной */
    const st = big(html, 'style');
    if (st) {
      const css = st[1];
      const a = css.indexOf(AF), b = css.indexOf(AF, a + AF.length);
      const cut = b === -1 ? 0 : b + AF.length;
      html = html.slice(0, st.index) + '<style>\n' + css.slice(0, cut).trim() +
        '\n</style>\n<!-- PLP:ASSET-CSS -->' + html.slice(st.index + st[0].length);
    }
    const sc = big(html, 'script');
    if (sc) html = html.slice(0, sc.index) + '<!-- PLP:ASSET-JS -->' + html.slice(sc.index + sc[0].length);

    /* обновляем теги (или ставим впервые) */
    html = html.replace(/<!-- PLP:ASSET-CSS -->(<link rel="stylesheet" href="\/assets\/app\.css\?v=\w+">)?/, CSS_TAG);
    html = html.replace(/<!-- PLP:ASSET-JS -->(<script src="\/assets\/catalog\.js\?v=\w+"><\/script>\s*<script src="\/assets\/app\.js\?v=\w+"><\/script>)?/, JS_TAG);

    if (html !== was) { fs.writeFileSync(full, html); n++; }
    if (PAGES.includes(f)) console.log('   %s %s КБ', f.padEnd(18), (html.length / 1024 | 0));
  }
  console.log('[assets] страниц с общим кодом:', страницы.size, '· обновлено:', n);
}

extract();
if (fs.existsSync(path.join(ASSETS, 'app.js'))) link();
