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
];

const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const mStart = idx.indexOf('<main'), mOpen = idx.indexOf('>', mStart) + 1, mEnd = idx.indexOf('</main>');
const head = idx.slice(0, mOpen), tail = idx.slice(mEnd);

for (const o of OFFERS) {
  if (!fs.existsSync(path.join(ROOT, o.dir, 'page.htm'))) { console.log('нет лендинга:', o.dir); continue; }
  const v = fs.statSync(path.join(ROOT, o.dir, 'page.htm')).mtimeMs.toString(36);
  const body = `<section class="offer-wrap" style="padding:18px 0 28px"><div class="container">
  <div style="display:flex;justify-content:flex-end;margin:0 0 10px">
    <a class="btn btn-ghost" href="/${o.dir}/${o.pdf}" download style="font-size:14px">Скачать PDF</a>
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
  html = html.replace(/href="#(why|sale|rent|map|quiz|faq|do|contacts|about)"/g, 'href="index.html#$1"');

  fs.writeFileSync(path.join(ROOT, o.slug + '.html'), html);
  console.log(o.slug + '.html собран:', html.length, 'байт');
}
