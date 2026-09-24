import fs from 'node:fs';
import path from 'node:path';
const ROOT='/Users/elnurkhankishiev/plp-site';
const SITE='https://property-library.com';
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const idx=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const mStart=idx.indexOf('<main'), mOpen=idx.indexOf('>',mStart)+1, mEnd=idx.indexOf('</main>');
const head=idx.slice(0,mOpen), tail=idx.slice(mEnd);
/* 22.09.2026: подвал в index.html лежит ВНУТРИ <main>, а эти страницы берут только
   верх и низ главной — середину собирают сами. Поэтому на управлении, «о нас»,
   двенадцати статьях гайда и восьми районах подвала не было вовсе: человек доходил
   до низа и упирался в пустоту. Берём подвал из главной по маркерам и ставим перед
   низом. Источник один — build/parts/footer.html, копии не разойдутся. */
const _fS = idx.indexOf('<!-- PLP:FOOTER:START -->');
const _fE = idx.indexOf('<!-- PLP:FOOTER:END -->');
const ПОДВАЛ = (_fS >= 0 && _fE > _fS) ? idx.slice(_fS, _fE + '<!-- PLP:FOOTER:END -->'.length) : '';


// секции главной — чтобы переиспользовать каталог на других страницах
function grabSection(id){
  const main=idx.slice(mOpen,mEnd);
  const re=/<section\b[^>]*>/g; const st=[]; let m;
  while((m=re.exec(main))!==null) st.push({i:m.index,tag:m[0]});
  for(let k=0;k<st.length;k++){
    const idm=st[k].tag.match(/id="([^"]+)"/);
    if(idm&&idm[1]===id) return main.slice(st[k].i, k+1<st.length?st[k+1].i:main.length);
  }
  return '';
}
const SALE=grabSection('sale'), RENT=grabSection('rent');

/* Куски блока аренды помечены в index.html маркерами PLP:PART:<имя>, чтобы
   страница управления могла расставить их в нужном порядке, а не копировать
   всё скопом. Порядок задал Эльнур 06.09. */
function grabPart(name){
  const a=idx.indexOf(`<!-- PLP:PART:${name}:START -->`);
  const b=idx.indexOf(`<!-- PLP:PART:${name}:END -->`);
  if(a===-1||b===-1||b<a) return '';
  return idx.slice(a, b).replace(`<!-- PLP:PART:${name}:START -->`, '');
}
/* каталог аренды = секция целиком минус три куска, которые расставим отдельно */
function rentCatalogOnly(){
  let x=RENT;
  for(const n of ['rent-band','rent-care','rent-island']){
    const a=x.indexOf(`<!-- PLP:PART:${n}:START -->`);
    const b=x.indexOf(`<!-- PLP:PART:${n}:END -->`);
    if(a!==-1&&b!==-1&&b>a) x=x.slice(0,a)+x.slice(b+`<!-- PLP:PART:${n}:END -->`.length);
  }
  return x;
}
const wrapSection = inner => inner ? `<section style="padding-top:26px"><div class="container">${inner}</div></section>` : '';

function page({file,depth,title,desc,body,jsonld}){
  let html=head+'\n'+body+'\n'+ПОДВАЛ+'\n'+tail;
  const url=SITE+'/'+file;
  html=html.replace(/<title>[\s\S]*?<\/title>/,'<title>'+esc(title)+'</title>');
  html=html.replace(/(<meta name="description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
  html=html.replace(/(<link rel="canonical" href=")[^"]*(")/,'$1'+url+'$2');
  html=html.replace(/(<meta property="og:url" content=")[^"]*(")/,'$1'+url+'$2');
  html=html.replace(/(<meta property="og:title" content=")[^"]*(")/,'$1'+esc(title)+'$2');
  html=html.replace(/(<meta property="og:description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
  const up=depth?'../':'';
  html=html.replace(/href="#top"/g,'href="'+up+'index.html"');
  html=html.replace(/href="#(why|sale|rent|map|quiz|about|faq|do|steps|contacts)"/g,'href="'+up+'index.html#$1"');
  if(depth) html=html.replace(/(href|src)="(img\/|favicon|buy\.html|rent\.html|owner\.html|management\.html|add-property\.html|about\.html|districts\/|guide\/|offer\.html|privacy\.html|rules\.html|terms\.html|index\.html)/g,'$1="../$2');
  if(jsonld) html=html.replace('</head>','<script type="application/ld+json">'+JSON.stringify(jsonld)+'</script>\n</head>');
  fs.writeFileSync(path.join(ROOT,file),html);
  return file;
}

const card=(t,d)=>`<div class="vcard"><h3 style="margin:0 0 6px;font-size:17px">${esc(t)}</h3><p class="sub" style="margin:0;font-size:15px">${esc(d)}</p></div>`;

/* ── УПРАВЛЕНИЕ ─────────────────────────────────────────── */
const services=[
 ['Ищем и селим гостей','Размещаем объект, отвечаем на запросы, проверяем гостей и оформляем заезд.'],
 ['Ведём календарь','Свободные даты, брони, ваши личные заезды — всё в одном календаре.'],
 ['Убираем и обслуживаем','Уборка между гостями, бассейн, сад, мелкий ремонт. Каждый расход с чеком.'],
 ['Считаем и платим','Ежемесячный отчёт: доход, расходы, комиссия, сумма к выплате. Без ручных таблиц.'],
 ['Держим документы','Договор, акты, счета — в кабинете, а не в переписке.'],
 ['Отвечаем гостям вместо вас','Круглосуточно, на русском и английском. Вас не беспокоим по мелочам.'],
];
/* Порядок разделов задал Эльнур 06.09:
   управление → аренда с заботой → сколько стоит → свой объект →
   каталог аренды → запрос 24/7 → понравился остров.
   Плитки услуг и «что видно в кабинете» стоят рядом со своими разделами. */
const M_HERO = `<section style="padding-bottom:0"><div class="container">
  <p class="kicker">Property Library · управление</p>
  <h1 style="font-size:clamp(28px,4.4vw,44px);margin:0 0 12px">Управление недвижимостью на Пхукете</h1>
  <p class="sub" style="max-width:64ch;margin:0 0 8px">Вы отдаёте ключи — мы берём на себя гостей, уборку, ремонт и отчётность.
  Каждый месяц вы видите доход, расходы и сумму к выплате в личном кабинете, а не в переписке с менеджером.</p>
</div></section>
<!-- 24.09.2026 Эльнур прислал снимок: терраса, бассейн, горы. Настоящая съёмка,
     не рендер — для страницы про управление это важнее красоты.
     Две обрезки: 16:9 на компьютере и 4:3 на телефоне. Одна широкая картинка на
     телефоне превращается в полоску, поэтому кадр там выше. picture выбирает сам,
     лишнего не качает. -->
<section style="padding:18px 0 0"><div class="container">
  <picture class="mng-hero">
    <source media="(max-width:640px)" srcset="img/management-hero-mob-900.webp" width="900" height="600">
    <source media="(max-width:1100px)" srcset="img/management-hero-1000.webp" width="1000" height="562">
    <img src="img/management-hero-1600.webp" width="1600" height="900" loading="eager" decoding="async"
         alt="Терраса с бассейном на вилле под нашим управлением, Пхукет">
  </picture>
</div></section>`;
const M_LIST = `<section id="list-property" style="padding-top:22px"><div class="container">
  <div style="background:var(--green-soft);border:1px solid var(--line,rgba(var(--ink-rgb),.12));border-radius:24px;padding:clamp(20px,3vw,30px)">
    <div class="lp-grid">
      <div>
        <span class="kicker">Свой объект</span>
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0 10px">
          <h2 style="font-size:clamp(24px,3.4vw,34px);margin:0">Разместить объект</h2>
          <!-- ссылку на этот раздел удобно отправить собственнику: бот, WhatsApp, письмо -->
          <button type="button" class="share-btn" data-share="/management#list-property"
                  data-share-title="Разместить объект — Property Library"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.6" y1="10.5" x2="15.4" y2="6.5"></line><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"></line></svg><span>Поделиться</span></button>
        </div>
        <p class="sub" style="margin:0 0 14px;max-width:52ch">Зачем это вам: объект попадает к тем, кто уже ищет
        жильё на Пхукете — на сайт, в каталог консьерж-бота и в подборки, которые мы отправляем клиентам.
        Переписку, показы и договор берём на себя.</p>
        <ul class="sub" style="margin:0 0 18px;padding-left:20px;line-height:1.9;font-size:15px">
          <li>Сдать в аренду или продать — решаете вы, карточку готовим под цель</li>
          <li>Оценим ставку и цену по свежим сделкам района, а не «на глаз»</li>
          <li>Пока объект стоит пустым, он приносит только расходы</li>
        </ul>
        <div class="hero-cta" style="margin:0">
          <a class="btn btn-primary" href="add-property.html">Разместить объект</a>
          <a class="btn btn-ghost" href="owner.html">Личный кабинет</a>
        </div>
      </div>
      <div style="background:var(--paper);border-radius:18px;padding:18px 20px">
        <p style="margin:0 0 10px;font-weight:700;font-size:15px">Пять коротких шагов</p>
        <ol style="margin:0;padding-left:20px;color:var(--muted);font-size:15px;line-height:1.9">
          <li>Тип, район, спальни</li>
          <li>Готовность и на что рассчитываете</li>
          <li>Фото и видео — можно пачкой</li>
          <li>Описание и адрес</li>
          <li>Контакты — и всё</li>
        </ol>
        <p class="sub" style="margin:12px 0 0;font-size:14px">Регистрация не нужна. Проверим материалы,
        оформим карточку и пришлём ссылку.</p>
      </div>
    </div>
  </div>
</div></section>`;
const M_SERV = `<section style="padding-top:26px"><div class="container">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px">
    ${services.map(s=>`<div style="background:var(--paper);border:1px solid var(--line,rgba(var(--ink-rgb),.1));border-radius:18px;padding:18px 20px">
      <h3 style="margin:0 0 6px;font-size:17px">${esc(s[0])}</h3>
      <p class="sub" style="margin:0;font-size:15px">${esc(s[1])}</p></div>`).join('')}
  </div>
</div></section>
`;
const M_PRICE = `<section style="padding-top:26px"><div class="container">
  <h2 style="font-size:clamp(22px,3vw,28px);margin:0 0 14px">Сколько это стоит</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px">
    <div style="background:var(--paper);border:1px solid var(--line,rgba(var(--ink-rgb),.1));border-radius:18px;padding:18px 20px">
      <div style="font-size:30px;font-weight:800">20%</div>
      <div class="sub" style="font-size:14px">от дохода · короткие сроки</div></div>
    <div style="background:var(--paper);border:1px solid var(--line,rgba(var(--ink-rgb),.1));border-radius:18px;padding:18px 20px">
      <div style="font-size:30px;font-weight:800">15%</div>
      <div class="sub" style="font-size:14px">от дохода · договор на год</div></div>
    <div style="background:#1a1c12;border:1px solid #D2D5B3;border-radius:18px;padding:18px 20px;color:#EDEDE9">
      <div style="font-size:30px;font-weight:800;color:#D2D5B3">0 ฿</div>
      <div style="font-size:14px;color:#b7b7ac">за подключение объекта</div></div>
  </div>
  <p class="sub" style="font-size:14px;margin-top:12px">Комиссия удерживается из дохода — платить отдельно ничего не нужно.
  Расходы на уборку и ремонт показываем отдельной строкой с чеком.</p>
</div></section>
`;
const M_CABIN = `<section style="padding-top:26px"><div class="container">
  <h2 style="font-size:clamp(22px,3vw,28px);margin:0 0 10px">Что видно в кабинете</h2>
  <p class="sub" style="max-width:62ch;margin:0 0 16px">Доступ по коду из WhatsApp — без паролей и приложений.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px">
    ${['Сумма к выплате за период','Доходы и расходы построчно','Календарь заездов','История отчётов по месяцам','Работы по объекту','Заявка на уборку или ремонт']
      .map(t=>`<div style="border:1px dashed #d8d5c9;border-radius:14px;padding:14px 16px;font-size:15px">${esc(t)}</div>`).join('')}
  </div>
  <div class="hero-cta" style="margin-top:22px">
    <a class="btn btn-primary" href="owner.html">Войти в кабинет</a>
    <a class="btn btn-ghost" href="https://t.me/elnurphuket_bot?start=uk" target="_blank" rel="noopener">Обсудить объект в Telegram</a>
  </div>
</div></section>`;
/* «Что видно в кабинете» на публичной странице не нужно: Эльнур 06.09 —
   «в кабинете уже и так видно». Блок M_CABIN оставлен в файле на случай
   возврата, но в страницу не собирается. */
/* Эльнур 06.09 (уточнение): со страницы управления убираем каталог аренды,
   «Запрос на аренду 24/7» и «Понравился остров?» — их место в блоке аренды.
   Остаётся услуга управления: как мы работаем, аренда с заботой, сколько
   стоит и как разместить свой объект. */
const mgmt = [M_HERO, M_SERV, wrapSection(grabPart('rent-care')), M_PRICE,
              M_LIST].join('\n');


const made=[];
made.push(page({file:'management.html',depth:0,
  /* 24.09: было 79 знаков. Оставляем район работы и бренд. */
  title:'Управление недвижимостью на Пхукете | Property Library',
  desc:'Возьмём на себя гостей, уборку, ремонт и отчётность. Комиссия от 15% дохода, подключение бесплатно. Отчёты и выплаты — в личном кабинете.',
  /* Эльнур 06.09: «в блоке управление зачем аренда размещена?» — страница про
     услугу управления, каталог аренды живёт на rent.html. */
  body:mgmt}));

/* ── ГАЙДЫ ──────────────────────────────────────────────── */
const faq=JSON.parse(fs.readFileSync('/Users/elnurkhankishiev/plp-site/build/faq.json','utf8'));
const slugs={'1':'inostranec-mozhet-kupit','2':'leasehold-ili-freehold','3':'nalogi-i-rashody',
             '4':'skolko-oformlyaetsya-sdelka','5':'kupit-udalenno','6':'stoimost-uslug',
             '7':'kakaya-dohodnost','8':'garantirovannaya-dohodnost','9':'kto-upravlyaet-obektom',
             '10':'viza-i-vnzh','11':'risk-nedostroya','12':'pereprodazha-do-sdachi'};
const gdir=path.join(ROOT,'guide');
if(!fs.existsSync(gdir)) fs.mkdirSync(gdir,{recursive:true});

for(const f of faq){
  const slug=slugs[f.n]; if(!slug) continue;
  const others=faq.filter(x=>x.n!==f.n).map(x=>
    `<li style="margin:8px 0"><a href="${slugs[x.n]}.html">${esc(x.q)}</a></li>`).join('');
  const body=`<section style="padding-bottom:0"><div class="container" style="max-width:760px">
    <p class="kicker">Справочник покупателя</p>
    <h1 style="font-size:clamp(26px,3.8vw,38px);margin:0 0 16px">${esc(f.q)}</h1>
    <p style="font-size:18px;line-height:1.7;margin:0 0 20px">${esc(f.a)}</p>
    <div style="background:var(--green-soft);border-radius:18px;padding:18px 20px;margin:24px 0">
      <p style="margin:0 0 12px;font-size:15px">Разберём вашу ситуацию бесплатно — ответим за пять минут в рабочее время.</p>
      <div class="hero-cta" style="margin:0">
        <a class="btn btn-primary" href="https://t.me/elnurphuket_bot?start=faq" target="_blank" rel="noopener">Спросить в Telegram</a>
        <a class="btn btn-ghost" href="../buy.html">Смотреть объекты</a>
      </div>
    </div>
    <h2 style="font-size:20px;margin:28px 0 8px">Другие вопросы</h2>
    <ul style="padding-left:18px;margin:0">${others}</ul>
  </div></section>
  ${SALE}`;
  made.push(page({file:'guide/'+slug+'.html',depth:1,
    /* 24.09: вопросы в гайде длинные, и бренд «Property Library Phuket»
       добивал заголовок до 70+ знаков — поиск обрезал именно бренд.
       Берём короткую форму, а если и с ней не влезает — оставляем вопрос. */
    title:(f.q+' | Property Library').length<=65 ? f.q+' | Property Library' : f.q,
    desc:f.a.slice(0,158),
    body,
    jsonld:{'@context':'https://schema.org','@type':'FAQPage','mainEntity':[{'@type':'Question','name':f.q,
      'acceptedAnswer':{'@type':'Answer','text':f.a}}]}}));
}
/* 17.09 Эльнур: «справочник покупателя классный блок, не видел его у нас, может
   пусть он будет там где-то, где ФАК… это надо как-то объединить со справочником».
   Короткий ответ живёт на главной, полный разбор — здесь; связывает их оглавление,
   на которое ведут все двенадцать ссылок «Подробно в справочнике». */
{
  const items = faq.filter(f => slugs[f.n]).map(f =>
    `<li style="margin:0"><a href="${slugs[f.n]}.html" style="display:block;padding:14px 16px;` +
    `background:var(--card,#fff);border:1px solid var(--line,#e7e7e2);border-radius:14px;` +
    `text-decoration:none;color:inherit"><b style="display:block;font-size:17px;line-height:1.35">` +
    `${esc(f.q)}</b><span style="display:block;margin-top:6px;font-size:14px;opacity:.75;` +
    `line-height:1.5">${esc(f.a.slice(0, 150))}…</span></a></li>`).join('');
  const body = `<section style="padding-bottom:0"><div class="container" style="max-width:760px">
    <p class="kicker">Справочник покупателя</p>
    <h1 style="font-size:clamp(26px,3.8vw,38px);margin:0 0 10px">Что нужно знать до покупки на Пхукете</h1>
    <p style="font-size:18px;line-height:1.7;margin:0 0 22px">${faq.length} разборов: собственность,
      налоги, сроки, доходность, риски и управление. Коротко о том же — в блоке
      «Нас часто спрашивают» на главной.</p>
    <ul style="list-style:none;padding:0;margin:0;display:grid;gap:10px">${items}</ul>
  </div></section>
  ${SALE}`;
  made.push(page({file:'guide/index.html',depth:1,
    title:'Справочник покупателя недвижимости на Пхукете | Property Library',
    desc:'Собственность, налоги, сроки сделки, доходность, риски и управление — ' + faq.length + ' разборов простым языком.',
    body,
    jsonld:{'@context':'https://schema.org','@type':'FAQPage','mainEntity':faq.map(f=>({'@type':'Question',
      'name':f.q,'acceptedAnswer':{'@type':'Answer','text':f.a}}))}}));
}
console.log('создано страниц:',made.length);
console.log(made.join('\n'));
