import fs from 'node:fs';
import path from 'node:path';
const ROOT = '/Users/elnurkhankishiev/plp-site';
const SITE_BASE = 'https://property-library.com';
const htmlEsc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function splitSections(mainHtml){
  const parts=[]; const re=/<section\b[^>]*>/g; const starts=[]; let m;
  while((m=re.exec(mainHtml))!==null) starts.push({i:m.index,tag:m[0]});
  for(let k=0;k<starts.length;k++){
    const from=starts[k].i, to=k+1<starts.length?starts[k+1].i:mainHtml.length;
    const idm=starts[k].tag.match(/id="([^"]+)"/);
    parts.push({id:idm?idm[1]:null,html:mainHtml.slice(from,to),order:k});
  }
  return parts;
}
function sectionPage(indexHtml,opts){
  const mStart=indexHtml.indexOf('<main');
  const mOpenEnd=indexHtml.indexOf('>',mStart)+1;
  const mEnd=indexHtml.indexOf('</main>');
  const head=indexHtml.slice(0,mOpenEnd), tail=indexHtml.slice(mEnd);
  const parts=splitSections(indexHtml.slice(mOpenEnd,mEnd));
  let picked=opts.sections.map(sel=>{
    const f = typeof sel==='number' ? parts.find(p=>p.order===sel) : parts.find(p=>p.id===sel);
    return f?f.html:'';
  }).join('\n');
  // компактное вступление: объекты должны попадать на первый экран
  const intro='<section style="padding:22px 0 0"><div class="container">'+
    '<h1 style="font-size:clamp(24px,3.2vw,34px);margin:0 0 6px">'+htmlEsc(opts.h1)+'</h1>'+
    '<p class="sub" style="max-width:62ch;margin:0;font-size:.95rem">'+htmlEsc(opts.intro)+'</p></div></section>';
  // Заголовок секции дублирует H1 страницы — вдвоём они съедали весь первый
  // экран, и ни одного объекта не было видно без прокрутки. На внутренней
  // странице оставляем только H1.
  picked = picked.replace(
    /<div class="head-row reveal">\s*<div>\s*<span class="kicker"[^>]*>[\s\S]*?<\/p>\s*<\/div>/,
    '<div class="head-row reveal"><div>');
  picked = picked.replace(/\s+aria-labelledby="(sale|rent)-title"/, '');
  // от заголовка остался пустой ряд со стрелками карусели — он держал
  // лишнюю полосу пустоты и разгонял фильтры по краям
  picked = picked.replace(
    /<div class="head-row reveal"><div>\s*<div class="arrows">[\s\S]*?<\/div>\s*<\/div>/,
    '');
  picked = picked.replace(/<div class="head-row reveal"><div>\s*<\/div>/, '');
  let out=head+'\n'+intro+'\n'+picked+'\n'+tail;
  const url=SITE_BASE+'/'+opts.file;
  out=out.replace(/<title>[\s\S]*?<\/title>/,'<title>'+htmlEsc(opts.title)+'</title>');
  out=out.replace(/(<meta name="description" content=")[^"]*(")/,'$1'+htmlEsc(opts.desc)+'$2');
  out=out.replace(/(<link rel="canonical" href=")[^"]*(")/,'$1'+url+'$2');
  out=out.replace(/(<meta property="og:url" content=")[^"]*(")/,'$1'+url+'$2');
  out=out.replace(/(<meta property="og:title" content=")[^"]*(")/,'$1'+htmlEsc(opts.title)+'$2');
  out=out.replace(/(<meta property="og:description" content=")[^"]*(")/,'$1'+htmlEsc(opts.desc)+'$2');

  // На внутренней странице якоря главной не работают — переводим их на index.html.
  // Логотип и «наверх» ведут на главную, свой раздел ссылается сам на себя.
  out=out.replace(/href="#top"/g,'href="index.html"');
  out=out.replace(/href="#(why|sale|rent|map|quiz|about|faq|do|steps|contacts)"/g,'href="index.html#$1"');
  if(opts.self) out=out.replace(new RegExp('href="index.html#'+opts.self+'"','g'),'href="'+opts.file+'"');

  return out;
}

/* Раскладка каталога: сетка карточек слева, живая карта справа.
   Включается только на buy.html и rent.html — главная остаётся каруселью,
   чтобы не ломать её ритм. */
/* На страницах-разделах фильтры должны быть узкой полосой, а не колонкой
   во весь экран: объекты обязаны попадать в первый экран. */
const COMPACT_CSS = `
<style>
#rentFilters{flex-direction:row!important;flex-wrap:wrap;align-items:center;gap:8px!important;margin-top:12px!important}
#rentFilters .rf-lab,#rentFilters>span.kicker{display:none}
#rentFilters .rf-more{margin-top:0;margin-left:auto}
#rentDateFilter{margin-top:10px}
#rentDateFilter .df-status{font-size:.8rem;margin-top:6px}
section#rent,section#sale{padding-top:10px}
@media(max-width:700px){
  /* на телефоне блок дат и фильтры не должны занимать весь экран */
  #rentDateFilter .df-fields{gap:8px}
  #rentFilters{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin-left:-14px;margin-right:-14px;padding:2px 14px 6px}
  #rentFilters::-webkit-scrollbar{display:none}
  #rentFilters .rf-more{margin-left:8px}
  #rentDateFilter .df-status{display:none}
}
</style>`;

const CATALOG_CSS = `
<style>
.catalog{padding-top:14px}
.catalog .filterbar{margin-top:12px}
.catalog .container>.reveal{margin-bottom:0}
.catalog .arrows{display:none}
.catalog .found{margin:14px 0 4px;font-size:.92rem;color:var(--muted)}
.catalog .found b{color:var(--ink);font-size:1.05rem}
.catrow{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:22px;align-items:start;margin-top:8px}
@media(max-width:1080px){.catrow{grid-template-columns:1fr}.catmap{display:none}}
.catalog .car{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:18px;
  overflow:visible;padding:2px;cursor:default;scroll-snap-type:none}
.catalog .car .prop{width:auto!important;min-width:0;scroll-snap-align:none;flex:none}
.catalog .car .prop.hl{outline:2px solid var(--ink);outline-offset:2px}
.catmap{position:sticky;top:88px}
.catmap .plpmap{height:calc(100vh - 168px);max-height:760px;margin:0}
.catmap .plpwrap{margin:0}
.catmap .capt{font-size:.8rem;color:var(--muted);margin:8px 0 0}
</style>`;

const CATALOG_MAP = `
<div class="catmap">
  <div class="plpwrap">
    <div class="plpfilt plpview" id="plpView" style="left:12px;right:auto">
      <button type="button" data-v="map" class="on">Карта</button>
      <button type="button" data-v="sat">Спутник</button>
    </div>
    <div id="plpMap" class="plpmap"></div>
  </div>
  <p class="capt" id="plpNote">Наведите на карточку — покажем объект на карте.</p>
</div>`;

const CATALOG_JS = `
<script>
/* Каталог и карта — одно целое: карта показывает то, что осталось после фильтров,
   наведение на карточку подсвечивает метку и наоборот. */
(function(){
  function visiblePids(){
    var out=[];
    document.querySelectorAll('.catalog .car .prop').forEach(function(el){
      if(el.style.display!=='none' && el.dataset.pid) out.push(el.dataset.pid);
    });
    return out;
  }
  function countFound(){
    var box=document.getElementById('found');
    if(!box) return;
    var n=visiblePids().length;
    var w=(n%10===1&&n%100!==11)?'объект':((n%10>=2&&n%10<=4&&(n%100<10||n%100>20))?'объекта':'объектов');
    box.innerHTML='<b>'+n+'</b> '+w+' по вашим фильтрам';
  }
  window.PLP_MAP_FILTER=function(){ return visiblePids(); };
  function sync(){ countFound(); if(window.renderMapReal){ try{ window.PLPMAP && window.drawPinsExternal && window.drawPinsExternal(); }catch(e){} } }

  /* каталог зовёт нас после каждой фильтрации — обновляем счётчик и карту */
  window.PLP_AFTER_FILTER=function(){ setTimeout(sync, 20); };
  document.addEventListener('mouseover', function(e){
    var card=e.target.closest && e.target.closest('.catalog .car .prop');
    if(!card||!card.dataset.pid) return;
    if(window.PLP_HIGHLIGHT) window.PLP_HIGHLIGHT(card.dataset.pid);
  });
  document.addEventListener('mouseout', function(e){
    var card=e.target.closest && e.target.closest('.catalog .car .prop');
    if(card && window.PLP_HIGHLIGHT) window.PLP_HIGHLIGHT(null);
  });
  window.addEventListener('load', function(){ setTimeout(sync,600); setTimeout(sync,1800); });
})();
</script>`;

function asCatalog(html, carId){
  // секцию каталога оборачиваем в две колонки и подкладываем карту
  const openIdx = html.indexOf('<div class="car" id="'+carId+'"></div>');
  if(openIdx < 0) return html;

  let out = html.replace('<div class="car" id="'+carId+'"></div>',
    '<p class="found" id="found"></p>'+
    '<div class="catrow"><div><div class="car" id="'+carId+'"></div></div>'+CATALOG_MAP+'</div>');
  out = out.replace(/<section id="(sale|rent)"/, '<section class="catalog" id="$1"');
  return out;
}

const idx=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const pages=[
 {file:'buy.html',self:'sale',sections:['sale',8,9],catalogCar:'saleCar',
  h1:'Купить недвижимость на Пхукете',
  intro:'Проверенные виллы и апартаменты от застройщиков и собственников. Каждый объект смотрим лично перед тем, как показать.',
  title:'Купить недвижимость на Пхукете — виллы и апартаменты | Property Library',
  desc:'Виллы, апартаменты и кондо на Пхукете от застройщиков и собственников. Проверенные объекты, расчёт доходности, сопровождение сделки.'},
 {file:'rent.html',self:'rent',sections:['rent'],
  h1:'Аренда жилья на Пхукете',
  intro:'Виллы и апартаменты для жизни и отдыха, аренда от месяца. Подберём под даты и бюджет, встретим и заселим.',
  title:'Аренда виллы или апартаментов на Пхукете | Property Library',
  desc:'Долгосрочная аренда вилл и апартаментов на Пхукете. Свободные объекты по датам, трансфер, уборка, помощь на месте.'},
];
for(const p of pages){
  let html=sectionPage(idx,p);
  if(p.catalogCar){
    html=asCatalog(html,p.catalogCar);
    // стиль и связка списка с картой — только на страницах каталога
    html=html.replace('</head>', CATALOG_CSS+'\n</head>');
    html=html.replace('</body>', CATALOG_JS+'\n</body>');
  }
  html=html.replace('</head>', COMPACT_CSS+'\n</head>');
  fs.writeFileSync(path.join(ROOT,p.file),html);
  console.log(p.file,'—',html.length,'байт, секций:',p.sections.length,p.catalogCar?'(каталог с картой)':'');
}
