/* Закрытые офферы (/vibe2). Эльнур 18.09: «собираешь страничку на базе моего сайта, даёшь
   ссылку, и эту страничку даёшь в PDF». Шапка, подвал и скрипты — с главной, как у «О нас».
   Сам лендинг живёт в offers/<код>/page.htm и вкладывается рамкой: у него свои стили
   печатного листа, которые иначе спорили бы со стилями сайта. PDF печатается с того же
   page.htm (Documents/Codex/офферы/tools/publish_site.py), поэтому совпадает один в один.

   Страница закрыта от поисковиков и в sitemap не попадает: это предложение для своих. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://property-library.com';
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const OFFERS = [
  {
    slug: 'aileen', dir: 'offers/aileen',
    title: 'Aileen Residence Lagoon · Лагуна — предстарт',
    desc: 'Aileen Residence Lagoon в Лагуне: таунхаусы 159,3 м² с бассейном, цены, график оплаты и что построил застройщик. Предложение для клиентов Property Library Phuket.',
    pdf: 'Aileen_Lagoon.pdf',
  },
  {
    slug: 'vibe2', dir: 'offers/vibe2',
    title: 'Vibe II · Карон — закрытый предстарт',
    desc: 'Vibe II на Кароне: предстартовые цены, бронь, график оплаты и расчёт аренды. Предложение для клиентов Property Library Phuket.',
    pdf: 'Vibe2_Karon.pdf',
  },
  {
    /* 04.10.2026 Эльнур: «на секретной странице… зеро наянг гарантия 10% годовых». Факты: objects PLP-ZERO-NAIYANG
       (current_promo, unit_types, payment_plan; прайс и сообщение застройщика 07.09.2026) и презентация застройщика 11.2025. */
    slug: 'zero-naiyang', dir: 'offers/zero-naiyang',
    title: 'The ZERO Nai Yang · Най Янг — гарантия 10% на три года',
    desc: 'The ZERO Nai Yang в 350 метрах от пляжа Най Янг: гарантия 10% годовых на три года, цены, график оплаты. Предложение для клиентов Property Library Phuket.',
  },
];

const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const mStart = idx.indexOf('<main'), mOpen = idx.indexOf('>', mStart) + 1, mEnd = idx.indexOf('</main>');
const head = idx.slice(0, mOpen), tail = idx.slice(mEnd);

for (const o of OFFERS) {
  if (!fs.existsSync(path.join(ROOT, o.dir, 'page.htm'))) { console.log('нет лендинга:', o.dir); continue; }
  const v = fs.statSync(path.join(ROOT, o.dir, 'page.htm')).mtimeMs.toString(36);
  /* 02.10.2026: кнопка PDF только когда файл правда лежит рядом. У Aileen кнопка стояла,
     а файла не было, и человек получал «не найдено». Надпись по правилу кнопок «Получить + что». */
  const hasPdf = o.pdf && fs.existsSync(path.join(ROOT, o.dir, o.pdf));
  const body = `<section class="offer-wrap" style="padding:18px 0 28px"><div class="container">
  <div style="display:flex;justify-content:flex-end;margin:0 0 10px">
    ${hasPdf ? `<a class="btn btn-ghost" href="/${o.dir}/${o.pdf}" download style="font-size:14px">Получить PDF</a>` : ''}
  </div>
  <div id="offerBox" style="width:100%;max-width:794px;margin:0 auto;overflow:hidden;border-radius:14px;background:#EFECE2;box-shadow:0 2px 18px rgba(23,24,15,.08);height:4531px">
    <iframe id="offerFrame" src="/${o.dir}/page.htm?v=${v}" title="${esc(o.title)}" loading="eager" scrolling="no"
      style="display:block;width:794px;height:4531px;border:0;transform-origin:0 0"></iframe>
  </div>
</div></section>
<script>
/* Лист оффера показываем ровно как в PDF: ширина листа 794px (210 мм), на узком экране
   уменьшаем его целиком, а не перестраиваем в колонку. Эльнур 18.09: «как в PDF, рядом». */
(function () {
  var box = document.getElementById('offerBox'), f = document.getElementById('offerFrame'), H = 4531;
  function layout() {
    var k = Math.min(1, box.clientWidth / 794);
    f.style.transform = k < 1 ? 'scale(' + k + ')' : '';
    f.style.height = H + 'px';
    box.style.height = Math.ceil(H * k) + 'px';
  }
  function fit() {
    try { var d = f.contentDocument, w = d.querySelector('.w') || d.body; var h = w.getBoundingClientRect().height; if (h > 300) H = Math.ceil(h); } catch (e) {}
    layout();
  }
  f.addEventListener('load', function () { fit(); setTimeout(fit, 700); setTimeout(fit, 2000); });
  addEventListener('resize', layout);
  addEventListener('message', function (e) { if (e && e.data && e.data.plpOfferHeight > 300) { H = Math.ceil(e.data.plpOfferHeight); layout(); } });
  layout();
})();
</script>`;

  const url = SITE + '/' + o.slug;
  let html = head + '\n' + body + '\n' + tail;
  html = html.replace(/<title>[\s\S]*?<\/title>/, '<title>' + esc(o.title) + '</title>');
  html = html.replace(/(<meta name="description" content=")[^"]*(")/, '$1' + esc(o.desc) + '$2');
  html = html.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + url + '$2');
  html = html.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + url + '$2');
  html = html.replace(/(<meta property="og:title" content=")[^"]*(")/, '$1' + esc(o.title) + '$2');
  html = html.replace(/(<meta property="og:description" content=")[^"]*(")/, '$1' + esc(o.desc) + '$2');
  /* разметка главной не нужна; поисковикам страница закрыта */
  const headEnd = html.indexOf('</head>');
  html = html.slice(0, headEnd).replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>\s*/g, '')
    .replace(/<meta name="robots"[^>]*>\s*/g, '') + '<meta name="robots" content="noindex, nofollow">\n' + html.slice(headEnd);
  /* якоря главной ведут на главную */
  html = html.replace(/href="#top"/g, 'href="index.html"');
  html = html.replace(/href="#(why|sale|rent|map|quiz|faq|do|contacts|about)"/g, 'href="/#$1"');

  fs.writeFileSync(path.join(ROOT, o.slug + '.html'), html);
  console.log(o.slug + '.html собран:', html.length, 'байт');
}

/* ——— 02.10.2026. Скрытая страница закрытых предложений: /predstart ———
   Эльнур 02.10: «в секретной странице надо собрать инф по двум новым оферам квартц и физ»,
   «офер карон вайб 2 ну как то не понятно, их там два, ссылка и пдф». Здесь у каждого
   предложения одна карточка: открыть страницу и, если есть, получить PDF.
   Факты KUARTZ и FIZZ только из базы: objects (PLP-KUARTZ, PLP-FIZZ) и материалы_проекта
   (презентация застройщика «KUARTZ & FIZZ Mini Present», 01.10.2026, страница в скобках).
   Цен у этих двух пока нет, поэтому кнопка ведёт в WhatsApp за презентацией.
   Номеров юнитов, комиссий и «на руки» здесь не бывает: репозиторий открытый.
   Страница в корне, а не в offers/: общая шапка главной ссылается на картинки относительно. */
const WA = 'https://wa.me/66955492587?text=';
const CARDS = [
  {
    name: 'Vibe II', where: 'Карон', tag: 'закрытый лист',
    text: ['Второй проект застройщика, у которого первый Vibe за пять дней после старта продал 61% квартир.',
           'Студии от 3,2 млн бат, это около 91 тыс. долларов за 28 м². Бронь 100–200 тыс. бат, депозит возвратный 30 дней. Сдача в IV квартале 2029.'],
    open: '/vibe2', pdf: '/offers/vibe2/Vibe2_Karon.pdf',
  },
  {
    name: 'The ZERO Nai Yang', where: 'Най Янг', tag: 'гарантия 10% × 3 года',
    text: ['Бутиковый эко-проект в 350 метрах от пляжа Най Янг и в 2,5 км от аэропорта. 150 квартир в двух пятиэтажных корпусах, сдача в III квартале 2028.',
           'Студии от 4,45 млн бат. Застройщик гарантирует 10% годовых три года при покупке в лизхолд, первый взнос снижен до 25%.'],
    open: '/zero-naiyang',
    pdf: '/offers/zero-naiyang/ZERO_NaiYang.pdf',
  },
  {
    name: 'KUARTZ', where: 'Карон', tag: 'старт продаж в октябре',
    text: ['Старт закрытых продаж от The Title и AssetWise, лучшего застройщика Пхукета 2024 года по версии PropertyGuru. 400 метров до пляжа Карон, два дома по 7 этажей, 189 квартир на участке 4 412,8 м².',
           'В проекте 23 объекта инфраструктуры, среди них бассейн 25 метров и бассейн на крыше. Ориентир около 120 тыс. бат за м², точный прайс на старте.'],
    plans: [['1 спальня', '31,7–37,9 м²'], ['1 спальня плюс', '45–47,8 м²'], ['2 спальни', '56,6–62,7 м²'],
            ['пентхаус, 2 спальни', '69,5 м²'], ['пентхаус, 2 спальни плюс', '89,2–97,2 м²']],
    note: 'Формируем список инвесторов закрытого старта: участники первыми выбирают планировку и получают условия старта.',
    ask: 'Здравствуйте! Пришлите, пожалуйста, презентацию KUARTZ на Кароне',
    pdf: '/offers/kuartz/KUARTZ_Karon.pdf',
  },
  {
    name: 'FIZZ', where: 'Ката', tag: 'старт продаж в октябре',
    text: ['Второй старт The Title и AssetWise в октябре, на Кате. Один жилой дом в 7 этажей на 135 квартир и отдельный трёхэтажный клубный дом, участок 3 801 м². Ориентир около 120 тыс. бат за м².',
           'Камерный дом, где можно жить с питомцами. 25 объектов инфраструктуры и бассейн 25 на 5 метров. Сдача по плану застройщика в I квартале 2029.'],
    plans: [['1 спальня', '31–33 м²'], ['1 спальня плюс', '44–52 м²'], ['2 спальни', '58 м²'],
            ['пентхаус, 2 спальни', '64–77 м²'], ['пентхаус, 3 спальни', '105–110 м²']],
    note: 'Формируем список инвесторов закрытого старта: участники первыми выбирают планировку и получают условия старта.',
    ask: 'Здравствуйте! Пришлите, пожалуйста, презентацию FIZZ на Кате',
    pdf: '/offers/fizz/FIZZ_Kata.pdf',
  },
  {
    /* 04.10.2026 Эльнур: новый премиальный проект Central Group на Лаяне. Подтверждено: Bangkok Post 25.06.2026 (CG Capital,
       второй проект на Пхукете, Лаян, отель и брендированные резиденции, кондо и виллы). Названия, цен и сроков нет — цифр не ставим. */
    name: 'Новый проект Central Group', where: 'Лаян', tag: 'скоро старт',
    text: ['Второй жилой проект Central Group на Пхукете после The Standard Residences: отель и брендированные резиденции у пляжа Лаян, кондо и виллы. Около 100 квартир и своя коммерция рядом. Ориентир входа от 10–15 млн бат.',
           'Central Group построила на острове Central Phuket (Festival и Floresta, расширение на $836 млн к 2028 году) и Porto de Phuket в соседнем Чернгталае. Вторую очередь Porto Central уже объявила; по нашим данным, Porto de Phuket 2 войдёт в новый проект на Лаяне. Их The Standard на Банг Тао продан на 85% ещё до сдачи, внутри него к концу 2026 открывается POP Phuket.',
           'Формируем список инвесторов закрытого старта: участники первыми выбирают планировку и получают условия старта.'],
    ask: 'Здравствуйте! Хочу первым получить информацию о новом проекте Central Group на Лаяне',
    pdf: '/offers/central-layan/Central_Layan.pdf',
  },
];

function card(c) {
  const pdfOk = c.pdf && fs.existsSync(path.join(ROOT, c.pdf.replace(/^\//, '')));
  const btns = [];
  if (c.open) btns.push(`<a class="btn btn-primary" href="${c.open}">Открыть предложение</a>`);
  if (pdfOk) btns.push(`<a class="btn btn-ghost" href="${c.pdf}" download>Получить PDF</a>`);
  if (c.ask) btns.push(`<a class="btn btn-primary" href="${WA}${encodeURIComponent(c.ask)}" target="_blank" rel="noopener">Получить презентацию</a>`);
  const plans = c.plans ? `<ul class="pc-plans">${c.plans.map(([a, b]) => `<li><span>${esc(a)}</span><b>${esc(b)}</b></li>`).join('')}</ul>` : '';
  /* 05.10.2026 Эльнур: «карточки гигантские, некрасивые». Компактно: название, метка, одна ключевая строка, кнопки;
     полный текст и планировки — по «Подробнее». */
  const ключ = String(c.text[1] || c.text[0] || '').split(/(?<=\.)\s/)[0];
  const ещё = c.text.map(t => `<p>${esc(t)}</p>`).join('') + plans + (c.note ? `<p class="pc-note">${esc(c.note)}</p>` : '');
  return `<article class="pc-card">
    <div class="pc-top"><h2>${esc(c.name)}<span>, ${esc(c.where)}</span></h2><em>${esc(c.tag)}</em></div>
    <p class="pc-key">${esc(ключ)}</p>
    <details class="pc-more"><summary>Подробнее</summary>${ещё}</details>
    <div class="pc-btns">${btns.join('')}</div>
  </article>`;
}

{
  const title = 'Закрытые предложения · Property Library Phuket';
  const desc = 'Проекты Пхукета до официального старта продаж. Предварительные условия для клиентов Property Library Phuket.';
  const body = `<style>
.pc-wrap{padding:28px 0 40px}
.pc-wrap h1{font-size:clamp(1.6rem,4vw,2.2rem);margin:0 0 8px}
.pc-lead{color:var(--muted);margin:0 0 22px;max-width:640px}
.pc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,280px),1fr));gap:12px;align-items:start}
.pc-card{background:var(--paper);border:1px solid var(--line);border-radius:var(--r,14px);padding:14px 16px;display:flex;flex-direction:column;gap:8px}
.pc-key{font-size:.95rem}
.pc-more summary{cursor:pointer;color:var(--muted);font-size:.88rem}
.pc-more[open]{display:flex;flex-direction:column;gap:8px}
.pc-more p{font-size:.92rem}
.pc-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.pc-top h2{margin:0;font-size:1.12rem}
.pc-top h2 span{font-weight:500;color:var(--muted)}
.pc-top em{font-style:normal;font-size:.8rem;padding:3px 10px;border-radius:99px;background:var(--green-soft);color:var(--green-text)}
.pc-card p{margin:0;line-height:1.5}
.pc-plans{list-style:none;margin:4px 0 0;padding:0;border-top:1px solid var(--line)}
.pc-plans li{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);font-size:.92rem}
.pc-plans b{font-weight:600;white-space:nowrap}
.pc-note{color:var(--muted);font-size:.9rem}
.pc-btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto;padding-top:6px}
.pc-btns .btn{font-size:13px;padding:7px 12px}
.pc-foot{color:var(--muted);font-size:.85rem;margin:20px 0 0;max-width:640px}
</style>
<section class="pc-wrap"><div class="container">
  <h1>Закрытые предложения</h1>
  <p class="pc-lead">Проекты до официального старта продаж. Условия здесь предварительные, точный прайс и планировки присылаем лично.</p>
  <div class="pc-grid">
  ${CARDS.map(card).join('\n  ')}
  </div>
  <p class="pc-foot">Площади и состав KUARTZ и FIZZ взяты из презентации застройщика от 01.10.2026, застройщик может их изменить. Условия Vibe II предварительные, до официального прайса. Условия The ZERO Nai Yang по данным застройщика на 07.09.2026. Central Group: Bangkok Post 25.06.2026, данные Central Group; ориентир цены по нашим данным, условия уточняются у застройщика. Ориентир KUARTZ и FIZZ — до официального прайса.</p>
</div></section>`;

  const url = SITE + '/predstart';
  let html = head + '\n' + body + '\n' + tail;
  html = html.replace(/<title>[\s\S]*?<\/title>/, '<title>' + esc(title) + '</title>');
  html = html.replace(/(<meta name="description" content=")[^"]*(")/, '$1' + esc(desc) + '$2');
  html = html.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + url + '$2');
  html = html.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + url + '$2');
  html = html.replace(/(<meta property="og:title" content=")[^"]*(")/, '$1' + esc(title) + '$2');
  html = html.replace(/(<meta property="og:description" content=")[^"]*(")/, '$1' + esc(desc) + '$2');
  const headEnd = html.indexOf('</head>');
  html = html.slice(0, headEnd).replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>\s*/g, '')
    .replace(/<meta name="robots"[^>]*>\s*/g, '') + '<meta name="robots" content="noindex, nofollow">\n' + html.slice(headEnd);
  html = html.replace(/href="#top"/g, 'href="index.html"');
  html = html.replace(/href="#(why|sale|rent|map|quiz|faq|do|contacts|about)"/g, 'href="/#$1"');
  fs.writeFileSync(path.join(ROOT, 'predstart.html'), html);
  console.log('predstart.html собран:', html.length, 'байт');
}
