import fs from 'node:fs';
import path from 'node:path';
const ROOT='/Users/elnurkhankishiev/plp-site';
const SITE='https://property-library.com';
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const idx=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const mStart=idx.indexOf('<main'), mOpen=idx.indexOf('>',mStart)+1, mEnd=idx.indexOf('</main>');
const head=idx.slice(0,mOpen), tail=idx.slice(mEnd);

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

function page({file,depth,title,desc,body,jsonld}){
  let html=head+'\n'+body+'\n'+tail;
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
  if(depth) html=html.replace(/(href|src)="(img\/|favicon|buy\.html|rent\.html|owner\.html|privacy\.html|rules\.html|terms\.html|index\.html)/g,'$1="../$2');
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
const mgmt=`<section style="padding-bottom:0"><div class="container">
  <p class="kicker">Property Library · управление</p>
  <h1 style="font-size:clamp(28px,4.4vw,44px);margin:0 0 12px">Управление недвижимостью на Пхукете</h1>
  <p class="sub" style="max-width:64ch;margin:0 0 8px">Вы отдаёте ключи — мы берём на себя гостей, уборку, ремонт и отчётность.
  Каждый месяц вы видите доход, расходы и сумму к выплате в личном кабинете, а не в переписке с менеджером.</p>
</div></section>

<section style="padding-top:26px"><div class="container">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px">
    ${services.map(s=>`<div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:18px 20px">
      <h3 style="margin:0 0 6px;font-size:17px">${esc(s[0])}</h3>
      <p class="sub" style="margin:0;font-size:15px">${esc(s[1])}</p></div>`).join('')}
  </div>
</div></section>

<!--OBJECTS-->

<section style="padding-top:26px"><div class="container">
  <h2 style="font-size:clamp(22px,3vw,28px);margin:0 0 14px">Сколько это стоит</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px">
    <div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:18px 20px">
      <div style="font-size:30px;font-weight:800">20%</div>
      <div class="sub" style="font-size:14px">от дохода · короткие сроки</div></div>
    <div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:18px 20px">
      <div style="font-size:30px;font-weight:800">15%</div>
      <div class="sub" style="font-size:14px">от дохода · договор на год</div></div>
    <div style="background:#1a1c12;border:1px solid #D2D5B3;border-radius:18px;padding:18px 20px;color:#EDEDE9">
      <div style="font-size:30px;font-weight:800;color:#D2D5B3">0 ฿</div>
      <div style="font-size:14px;color:#b7b7ac">за подключение объекта</div></div>
  </div>
  <p class="sub" style="font-size:14px;margin-top:12px">Комиссия удерживается из дохода — платить отдельно ничего не нужно.
  Расходы на уборку и ремонт показываем отдельной строкой с чеком.</p>
</div></section>

<section style="padding-top:26px"><div class="container">
  <h2 style="font-size:clamp(22px,3vw,28px);margin:0 0 10px">Что видно в кабинете</h2>
  <p class="sub" style="max-width:62ch;margin:0 0 16px">Доступ по коду из WhatsApp — без паролей и приложений.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px">
    ${['Сумма к выплате за период','Доходы и расходы построчно','Календарь заездов','История отчётов по месяцам','Работы по объекту','Заявка на уборку или ремонт']
      .map(t=>`<div style="border:1px dashed #d8d5c9;border-radius:14px;padding:14px 16px;font-size:15px">${esc(t)}</div>`).join('')}
  </div>
  <div class="hero-cta" style="margin-top:22px">
    <a class="btn btn-primary" href="owner.html">Войти в кабинет</a>
    <a class="btn btn-ghost" href="https://wa.me/66955492587" target="_blank" rel="noopener">Обсудить объект в WhatsApp</a>
  </div>
</div></section>

<section id="list-property" style="padding-top:26px"><div class="container">
  <div style="background:#fff;border:1px solid #e7e5dc;border-radius:24px;padding:clamp(20px,3vw,32px);max-width:760px">
    <span class="kicker">Свой объект</span>
    <h2 style="font-size:clamp(22px,3vw,30px);margin:6px 0 8px">Разместить свой объект</h2>
    <p class="sub" style="margin:0 0 18px">Пять коротких шагов: расскажите об объекте и приложите фото.
    Мы проверим материалы, оформим карточку и опубликуем. Регистрация не нужна.</p>
    <ol style="margin:0 0 22px;padding-left:20px;color:#5c5c54;font-size:15px;line-height:1.9">
      <li>Тип, район, спальни</li>
      <li>Готовность и на что рассчитываете</li>
      <li>Фото и видео — можно перетащить сразу пачкой</li>
      <li>Описание и адрес</li>
      <li>Контакты — и всё</li>
    </ol>
    <div class="hero-cta" style="margin:0">
      <a class="btn btn-primary" href="add-property.html">Разместить объект</a>
      <a class="btn btn-ghost" href="owner.html">Личный кабинет</a>
    </div>
  </div>
</div></section>`;

const made=[];
made.push(page({file:'management.html',depth:0,
  title:'Управление недвижимостью на Пхукете — сдача, отчёты, выплаты | Property Library',
  desc:'Возьмём на себя гостей, уборку, ремонт и отчётность. Комиссия от 15% дохода, подключение бесплатно. Отчёты и выплаты — в личном кабинете.',
  body:mgmt.replace('<!--OBJECTS-->', RENT)}));

/* ── ГАЙДЫ ──────────────────────────────────────────────── */
const faq=JSON.parse(fs.readFileSync('/Users/elnurkhankishiev/plp-site/build/faq.json','utf8'));
const slugs={'1':'inostranec-mozhet-kupit','2':'leasehold-ili-freehold','3':'skolko-oformlyaetsya-sdelka',
             '4':'rashody-pri-pokupke','5':'kupit-udalenno','6':'stoimost-uslug'};
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
    <div style="background:#E9EBD9;border-radius:18px;padding:18px 20px;margin:24px 0">
      <p style="margin:0 0 12px;font-size:15px">Разберём вашу ситуацию бесплатно — ответим за пять минут в рабочее время.</p>
      <div class="hero-cta" style="margin:0">
        <a class="btn btn-primary" href="https://wa.me/66955492587" target="_blank" rel="noopener">Спросить в WhatsApp</a>
        <a class="btn btn-ghost" href="../buy.html">Смотреть объекты</a>
      </div>
    </div>
    <h2 style="font-size:20px;margin:28px 0 8px">Другие вопросы</h2>
    <ul style="padding-left:18px;margin:0">${others}</ul>
  </div></section>
  ${SALE}`;
  made.push(page({file:'guide/'+slug+'.html',depth:1,
    title:f.q+' — Property Library Phuket',
    desc:f.a.slice(0,158),
    body,
    jsonld:{'@context':'https://schema.org','@type':'FAQPage','mainEntity':[{'@type':'Question','name':f.q,
      'acceptedAnswer':{'@type':'Answer','text':f.a}}]}}));
}
console.log('создано страниц:',made.length);
console.log(made.join('\n'));
