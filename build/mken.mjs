/* Английская версия сайта — та же витрина, но видимая для поиска.
   Эльнур 20.09: «сео оптимизацию настрой, поиски запросы страницы сам скажи».

   Дыра, найденная при сверке 21.09: английская версия сайта существует для
   человека и не существует для поиска. Словарь полный — 640 ключей, все 253
   ключа главной переведены, кнопка EN работает. Но адрес у обеих версий один,
   в разметке всегда `lang="ru"`, а `hreflang` нет ни на одной странице. Google
   видит только русскую версию. На Пхукете это половина спроса: англоязычные
   покупатели ищут «phuket condo for sale», «villa rental phuket» и не находят
   нас вовсе.

   Что делает шаг: берёт уже собранные страницы и складывает английские копии в
   /en/. Перевод не пишется заново — подставляется тот же словарь PL.I18N.en,
   который витрина применяет в браузере. Значит расхождений между тем, что видит
   человек по кнопке EN, и тем, что видит поисковик, не будет.

   Взаимные ссылки: на русской странице появляется hreflang на английскую и
   наоборот, плюс x-default на русскую. Без этого Google считает версии
   отдельными страницами с одинаковым смыслом и режет обе.

   Чего шаг НЕ делает: не трогает страницы объектов (там тексты застройщиков,
   их перевод — отдельная работа) и кабинет.

       node build/mken.mjs
*/
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const SITE = 'https://property-library.com';
const OUT = path.join(ROOT, 'en');

/* какие страницы переводим и как они называются по-английски */
const PAGES = [
  { file: 'index.html', slug: '', title: 'Phuket Property — buy or rent with Property Library',
    desc: 'Villas and apartments in Phuket: verified projects, yield calculations, deal support, visa and settling in. We live here and pick property the way we pick it for ourselves.' },
  { file: 'buy.html', slug: 'buy', title: 'Buy property in Phuket — villas and apartments',
    desc: 'Villas, apartments and condos in Phuket from developers and owners. Verified projects, yield calculations, full deal support.' },
  { file: 'rent.html', slug: 'rent', title: 'Rent a villa or apartment in Phuket',
    desc: 'Long-term rentals of villas and apartments in Phuket. Availability by dates, transfer, cleaning, help on the ground.' },
  { file: 'about.html', slug: 'about', title: 'About Property Library Phuket',
    desc: 'Who we are and how we work: the founder, our approach, how a deal goes and client stories. Property search, purchase and support in Phuket.' },
  { file: 'management.html', slug: 'management', title: 'Property management in Phuket',
    desc: 'We manage your property in Phuket: guests, bookings, cleaning, reporting and payouts to the owner.' },
];

/* словарь берём из общего кода витрины — второго источника перевода нет */
function словарь() {
  const js = fs.readFileSync(path.join(ROOT, 'assets/app.js'), 'utf8');
  const нач = js.indexOf('PL.I18N');
  const enНач = js.indexOf('\nen: {', нач);
  if (нач === -1 || enНач === -1) throw new Error('словарь PL.I18N.en не найден в assets/app.js');
  /* от «en: {» до закрывающей скобки словаря: ищем строку «};» на нулевом уровне */
  let i = js.indexOf('{', enНач), уровень = 0, конец = -1;
  for (let k = i; k < js.length; k++) {
    if (js[k] === '{') уровень++;
    else if (js[k] === '}') { уровень--; if (уровень === 0) { конец = k; break; } }
  }
  const тело = js.slice(i, конец + 1);
  const м = {};
  const re = /"([a-z0-9._]+)"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
  let x;
  while ((x = re.exec(тело)) !== null) {
    м[x[1]] = x[2].replace(/\\"/g, '"').replace(/\\\\/g, '\\').replace(/\\n/g, '\n');
  }
  return м;
}

const EN = словарь();

/* Часть текста на странице не помечена ключами перевода: заголовки разделов
   пишет build/mkpages.mjs, названия районов приходят из данных, ссылки на
   справочник собираются в разметке. Для человека это неважно — он и так читает
   по-русски или переключает язык, — но поисковик видит английскую страницу с
   русскими заголовками и считает её некачественной. Переводим по тексту.
   Районы берём из той же карты имён, что и витрина. */
const РАЙОНЫ = {
  'Банг Тао': 'Bang Tao', 'Лаян': 'Layan', 'Сурин': 'Surin', 'Камала': 'Kamala',
  'Раваи': 'Rawai', 'Ката': 'Kata', 'Най Янг': 'Nai Yang', 'Ко Кео': 'Koh Kaew',
  'Най Харн': 'Nai Harn', 'Патонг': 'Patong', 'Черн Талай': 'Cherng Talay',
  'Лагуна': 'Laguna', 'Таланг': 'Thalang', 'Пхукет': 'Phuket', 'Карон': 'Karon',
};
/* Страница управления собирается отдельно (build/mkextra.mjs) и своих ключей
   перевода не имеет — тексты писались сразу в разметку. Переводим по тексту,
   как и остальное, чего не покрывает словарь. */
const УПРАВЛЕНИЕ = {
  'Property Library · управление': 'Property Library · management',
  'Управление недвижимостью на Пхукете': 'Property management in Phuket',
  'Вы отдаёте ключи — мы берём на себя гостей, уборку, ремонт и отчётность. Каждый месяц вы видите доход, расходы и сумму к выплате в личном кабинете, а не в переписке.':
    'You hand over the keys, we take on guests, cleaning, repairs and reporting. Every month you see income, costs and the payout in your account, not in a chat thread.',
  'Ежемесячный отчёт: доход, расходы, комиссия, сумма к выплате. Без ручных таблиц.':
    'A monthly statement: income, costs, our fee and the payout. No manual spreadsheets.',
  'Комиссия удерживается из дохода — платить отдельно ничего не нужно. Расходы на уборку и обслуживание — по факту, с чеками.':
    'The fee is deducted from income, so there is nothing to pay separately. Cleaning and maintenance are billed as incurred, with receipts.',
  'Зачем это вам: объект попадает к тем, кто уже ищет жильё на Пхукете — на сайт, в подборки менеджеров и в рассылки по базе клиентов.':
    'Why it matters: your property reaches people already looking in Phuket — the website, manager shortlists and mailings to our client base.',
  'Регистрация не нужна. Проверим материалы, оформим карточку и пришлём ссылку.':
    'No sign-up needed. We check the materials, build the listing and send you the link.',
  'Ищем и селим гостей': 'We find and check in guests',
  'Размещаем объект, отвечаем на запросы, проверяем гостей и оформляем заезд.':
    'We list the property, answer enquiries, vet guests and handle check-in.',
  'Ведём календарь': 'We keep the calendar',
  'Свободные даты, брони, ваши личные заезды — всё в одном календаре.':
    'Open dates, bookings and your own stays, all in one calendar.',
  'Убираем и обслуживаем': 'We clean and maintain',
  'Уборка между гостями, бассейн, сад, мелкий ремонт. Каждый расход с чеком.':
    'Cleaning between guests, pool, garden and small repairs. Every expense comes with a receipt.',
  'Считаем и платим': 'We report and pay out',
  'Держим документы': 'We keep the paperwork',
  'Договор, акты, счета — в кабинете, а не в переписке.':
    'Contracts, statements and invoices live in your account, not in a chat thread.',
  'Отвечаем гостям вместо вас': 'We answer guests for you',
  'Круглосуточно, на русском и английском. Вас не беспокоим по мелочам.':
    'Around the clock, in Russian and English. We do not bother you with small things.',
  'Сколько это стоит': 'What it costs',
  'от дохода · короткие сроки': 'of income · short stays',
  'от дохода · договор на год': 'of income · annual contract',
  'за подключение объекта': 'to onboard a property',
  'Комиссия удерживается из дохода — платить отдельно ничего не нужно.':
    'The fee is deducted from income, so there is nothing to pay separately.',
  'Свой объект': 'Your property',
  'Поделиться': 'Share',
  'Сдать в аренду или продать — решаете вы, карточку готовим под цель':
    'Rent it out or sell it, you decide. We prepare the listing for that goal',
  'Оценим ставку и цену по свежим сделкам района, а не «на глаз»':
    'We price it from recent deals in the area, not by eye',
  'Пока объект стоит пустым, он приносит только расходы':
    'An empty property only brings costs',
  'Личный кабинет': 'Owner account',
  'Пять коротких шагов': 'Five short steps',
  'Тип, район, спальни': 'Type, area, bedrooms',
  'Готовность и на что рассчитываете': 'Readiness and what you expect',
  'Фото и видео — можно пачкой': 'Photos and video, in bulk if you like',
  'Описание и адрес': 'Description and address',
  'Контакты — и всё': 'Contacts, and that is it',
};
const ФРАЗЫ = {
  'Подробно в справочнике →': 'Read the full guide →',
  'Весь справочник покупателя — 12 разборов': 'The full buyer guide — 12 explainers',
  'Нажмите метку — откроется карточка.': 'Tap a pin to open the property.',
  '← Весь остров': '← Whole island',
  'Объекты в продаже': 'Properties for sale',
  'Разместить объект': 'List your property',
  'Арендовать': 'Rent',
  'Купить': 'Buy',
  'Купить недвижимость на Пхукете': 'Buy property in Phuket',
  'Аренда жилья на Пхукете': 'Rent a home in Phuket',
  'Проверенные виллы и апартаменты от застройщиков и собственников. Каждый объект смотрим лично перед тем, как показать.':
    'Verified villas and apartments from developers and owners. We view every property ourselves before we show it.',
  'Виллы и апартаменты для жизни и отдыха. Подберём под даты и бюджет, встретим и заселим.':
    'Villas and apartments for living and holidays. We match them to your dates and budget, meet you and hand over the keys.',
  'Все проекты, с которыми мы работаем, — с ценами от застройщика и условиями рассрочки. Объекты в аренду — в разделе «Аренда»; на карте показаны и те, и другие.':
    'Every project we work with, with developer prices and payment plans. Rentals live in the Rent section; the map shows both.',
};

/* Названия объектов приходят из базы по-русски: «AYANA Heights · квартира (U3)»,
   «Villa Estella · вилла, 3 спальни». Английского имени в данных нет, а перевод
   нужен только для витрины — в CRM и офферах имя должно остаться прежним.
   Меняем не название целиком, а служебные слова внутри него. */
/* \b с кириллицей в JavaScript не работает — см. тот же разбор в assets/app.js */
const НЕБУКВА = '(?![А-Яа-яЁёA-Za-z])';
const СЛОВА = [
  [/·\s*квартира\s*\(/g, '· apartment ('], [/·\s*вилла,\s*/g, '· villa, '],
  [/·\s*вилла\s*\(/g, '· villa ('],
  [new RegExp('·\\s*квартира' + НЕБУКВА, 'g'), '· apartment'],
  [new RegExp('·\\s*вилла' + НЕБУКВА, 'g'), '· villa'],
  [new RegExp('(\\d+)\\s*спальни' + НЕБУКВА, 'g'), '$1 bedrooms'],
  [new RegExp('(\\d+)\\s*спальня' + НЕБУКВА, 'g'), '$1 bedroom'],
  [new RegExp('(\\d+)\\s*спален' + НЕБУКВА, 'g'), '$1 bedrooms'],
  [new RegExp(',\\s*Таланг' + НЕБУКВА, 'g'), ', Thalang'],
  [new RegExp(',\\s*Пхукет' + НЕБУКВА, 'g'), ', Phuket'],
];

/* Текст в разметке бывает разорван переносами и неразрывными пробелами:
   «объект попадает к тем, кто уже ищет\n        жильё». Сравнение по точному
   совпадению такие куски пропускает, поэтому ищем по «сжатому» виду. */
function заменитьГибко(html, ru, en) {
  const сжать = t => t.replace(/[\s\u00a0]+/g, ' ').trim();
  const цель = сжать(ru);
  return html.replace(/>([^<>]{10,})</g, (всё, внутри) =>
    сжать(внутри) === цель ? '>' + en + '<' : всё);
}

function добить(html) {
  let n = 0;
  for (const [re, en] of СЛОВА) {
    const до = html;
    html = html.replace(re, en);
    if (html !== до) n++;
  }
  for (const [ru, en] of Object.entries(УПРАВЛЕНИЕ)) {
    const до = html;
    html = заменитьГибко(html, ru, en);
    if (html !== до) n++;
  }
  for (const [ru, en] of Object.entries(ФРАЗЫ)) {
    const части = html.split('>' + ru + '<');
    if (части.length > 1) { n += части.length - 1; html = части.join('>' + en + '<'); }
  }
  for (const [ru, en] of Object.entries(РАЙОНЫ)) {
    const части = html.split('>' + ru + '<');
    if (части.length > 1) { n += части.length - 1; html = части.join('>' + en + '<'); }
  }
  return { html, добито: n };
}

function перевести(html) {
  let заменено = 0, мимо = 0;
  /* текст элемента с data-i18n меняем на английский; вложенную разметку не
     трогаем — в словаре лежит готовая строка, как и в браузере */
  html = html.replace(/(<([a-z0-9]+)\b[^>]*\bdata-i18n="([^"]+)"[^>]*>)([\s\S]*?)(<\/\2>)/gi,
    (всё, откр, тег, ключ, внутри, закр) => {
      const v = EN[ключ];
      if (v === undefined) { мимо++; return всё; }
      заменено++;
      return откр + v + закр;
    });
  /* подписи и заполнители — там же по ключу */
  html = html.replace(/data-i18n-ph="([^"]+)"([^>]*)placeholder="[^"]*"/gi,
    (всё, ключ, хвост) => EN[ключ] !== undefined
      ? `data-i18n-ph="${ключ}"${хвост}placeholder="${EN[ключ]}"` : всё);
  return { html, заменено, мимо };
}

function страница(p) {
  const src = path.join(ROOT, p.file);
  if (!fs.existsSync(src)) return null;
  let html = fs.readFileSync(src, 'utf8');
  const рус = SITE + '/' + (p.file === 'index.html' ? '' : p.file.replace('.html', ''));
  const анг = SITE + '/en/' + p.slug;

  const r = перевести(html);
  html = r.html;

  html = html.replace('<html lang="ru"', '<html lang="en"');
  html = html.replace(/<title>[\s\S]*?<\/title>/, '<title>' + p.title + '</title>');
  html = html.replace(/(<meta name="description" content=")[^"]*(")/, '$1' + p.desc + '$2');
  html = html.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + анг + '$2');
  html = html.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + анг + '$2');
  html = html.replace(/(<meta property="og:title" content=")[^"]*(")/, '$1' + p.title + '$2');
  html = html.replace(/(<meta property="og:description" content=")[^"]*(")/, '$1' + p.desc + '$2');
  html = html.replace(/(<meta property="og:locale" content=")[^"]*(")/, '$1en_US$2');

  /* язык витрины: без этого скрипт при загрузке вернёт русский поверх перевода */
  html = html.replace('</head>',
    '<script>try{localStorage.setItem("pl_lang","en")}catch(e){}window.__PL_LANG="en";</script>\n</head>');

  const д = добить(html);
  html = д.html;
  r.добито = д.добито;

  html = ссылки(html, рус, анг);

  /* адреса внутри страницы ведут на английские версии там, где они есть */
  for (const q of PAGES) {
    const из = q.file === 'index.html' ? 'index.html' : q.file;
    const куда = '/en/' + q.slug;
    html = html.split('href="' + из + '"').join('href="' + куда + '"');
    html = html.split('href="/' + из.replace('.html', '') + '"').join('href="' + куда + '"');
  }
  /* порядок полей важен: раньше стояло { html, ...r }, и распаковка возвращала
     html ДО замен языка, заголовка и hreflang — английская страница уезжала
     русской. Сначала распаковываем, потом кладём готовую разметку. */
  return { ...r, html, анг, рус };
}

function ссылки(html, рус, анг) {
  html = html.replace(/\s*<link rel="alternate" hreflang="[^"]*"[^>]*>/g, '');
  const блок = `\n<link rel="alternate" hreflang="ru" href="${рус}">` +
               `\n<link rel="alternate" hreflang="en" href="${анг}">` +
               `\n<link rel="alternate" hreflang="x-default" href="${рус}">`;
  return html.replace('</head>', блок + '\n</head>');
}

fs.mkdirSync(OUT, { recursive: true });
let всего = 0;
for (const p of PAGES) {
  const r = страница(p);
  if (!r) { console.log('нет страницы:', p.file); continue; }
  const файл = path.join(OUT, (p.slug || 'index') + '.html');
  fs.writeFileSync(файл, r.html);
  всего++;
  console.log('en/%s — по ключам: %d, по тексту: %d%s',
    (p.slug || 'index') + '.html', r.заменено, r.добито || 0,
    r.мимо ? (', без перевода: ' + r.мимо) : '');

  /* на русской странице — взаимная ссылка на английскую */
  const рфайл = path.join(ROOT, p.file);
  const было = fs.readFileSync(рфайл, 'utf8');
  const стало = ссылки(было, r.рус, r.анг);
  if (стало !== было) fs.writeFileSync(рфайл, стало);
}
console.log('английских страниц собрано:', всего);
