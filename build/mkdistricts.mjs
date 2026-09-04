import fs from 'node:fs';
import path from 'node:path';
const ROOT='/Users/elnurkhankishiev/plp-site';
const SITE='https://property-library.com';
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// районы: русское имя (как в каталоге) → адрес, падеж, рыночная справка
const D=[
 {ru:'Банг Тао', slug:'bang-tao', in:'Банг Тао', m2:135000, yoy:15.2, yld:7.1, src:'CBRE, I квартал 2025',
  about:'Западное побережье, пляж Банг Тао и район Лагуны. Здесь больше всего новых проектов и самый устойчивый спрос на аренду: рядом международные школы, рестораны и гольф.'},
 {ru:'Лаян', slug:'layan', in:'Лаяне', m2:128000, yoy:13.0, yld:6.9, src:'Knight Frank, 2025',
  about:'Тихая бухта к северу от Банг Тао. Спокойнее и зеленее соседей, при этом до инфраструктуры Лагуны десять минут на машине.'},
 {ru:'Сурин', slug:'surin', in:'Сурине', m2:125000, yoy:11.3, yld:7.0, src:'Knight Frank, 2025',
  about:'Один из самых престижных пляжей острова. Виллы на склонах с видом на море, закрытые резиденции, высокая цена входа и стабильный премиальный спрос.'},
 {ru:'Камала', slug:'kamala', in:'Камале', m2:115000, yoy:10.8, yld:6.5, src:'FazWaz, 2025',
  about:'Семейный район между Сурином и Патонгом. Длинный спокойный пляж, набережная, школы рядом — сюда чаще переезжают жить, а не только инвестировать.'},
 {ru:'Равай', slug:'rawai', in:'Равае', m2:85000, yoy:8.5, yld:5.9, src:'FazWaz, 2025',
  about:'Юг острова: рыбацкая гавань, рынки, лодки на Ко Ланта и Пхи-Пхи. Самый доступный вход в рынок и большая русскоязычная община.'},
 {ru:'Ката', slug:'kata', in:'Кате', about:
  'Курортный юго-запад с двумя пляжами — Ката и Ката Ной. Живой туристический поток круглый год, хорошая загрузка посуточной аренды.'},
 {ru:'Най Янг', slug:'nai-yang', in:'Най Янге', about:
  'Северо-запад рядом с аэропортом и национальным парком. Тихо, зелено, до терминала пятнадцать минут — удобно тем, кто часто летает.'},
 {ru:'Ко Кео', slug:'koh-kaew', in:'Ко Кео', about:
  'Восточная часть острова недалеко от Пхукет-Тауна. Марины, международные школы, спокойная жизнь вне туристических потоков.'},
];

const idx=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');

function sections(mainHtml){
  const parts=[]; const re=/<section\b[^>]*>/g; const st=[]; let m;
  while((m=re.exec(mainHtml))!==null) st.push({i:m.index,tag:m[0]});
  for(let k=0;k<st.length;k++){
    const from=st[k].i,to=k+1<st.length?st[k+1].i:mainHtml.length;
    const id=(st[k].tag.match(/id="([^"]+)"/)||[])[1]||null;
    parts.push({id,html:mainHtml.slice(from,to),order:k});
  }
  return parts;
}

const mStart=idx.indexOf('<main'), mOpen=idx.indexOf('>',mStart)+1, mEnd=idx.indexOf('</main>');
const head=idx.slice(0,mOpen), tail=idx.slice(mEnd);
const parts=sections(idx.slice(mOpen,mEnd));
let saleHtml=(parts.find(p=>p.id==='sale')||{}).html||'';

const outDir=path.join(ROOT,'districts');
if(!fs.existsSync(outDir)) fs.mkdirSync(outDir,{recursive:true});

/* Объекты района — берём уже собранный блок PLP:OBJECT-INDEX с главной,
   чтобы не заводить второй источник правды. Ключ — русское имя района. */
const OI = (() => {
  const m = {};
  const s0 = idx.indexOf('PLP:OBJECT-INDEX:START'), s1 = idx.indexOf('PLP:OBJECT-INDEX:END');
  if (s0 === -1 || s1 === -1) return m;
  const blk = idx.slice(s0, s1);
  const re = /<div class="oi-col"><h3>([^<]+)<\/h3>(<ul>[\s\S]*?<\/ul>)<\/div>/g;
  let x;
  while ((x = re.exec(blk))) m[x[1].trim()] = x[2];
  return m;
})();

const fmt=n=>String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' ');
const links=D.map(d=>`<a class="chipf" href="${d.slug}.html">${esc(d.ru)}</a>`).join(' ');

let made=[];
for(const d of D){
  const title=`Недвижимость в ${d.in}, Пхукет — купить виллу или апартаменты | Property Library`;
  const desc=`${d.about} Проверенные объекты в ${d.in}: цены, доходность, сопровождение сделки.`;
  const url=`${SITE}/districts/${d.slug}.html`;

  const market = d.m2 ? `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-top:24px">
      <div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:16px 18px">
        <div style="font-size:26px;font-weight:800;letter-spacing:-.01em">฿${fmt(d.m2)}</div>
        <div style="color:#5c5c54;font-size:13px;margin-top:2px">за м² · медиана</div></div>
      <div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:16px 18px">
        <div style="font-size:26px;font-weight:800;letter-spacing:-.01em">+${d.yoy}%</div>
        <div style="color:#5c5c54;font-size:13px;margin-top:2px">рост цены за год</div></div>
      <div style="background:#fff;border:1px solid #e7e5dc;border-radius:18px;padding:16px 18px">
        <div style="font-size:26px;font-weight:800;letter-spacing:-.01em">${d.yld}%</div>
        <div style="color:#5c5c54;font-size:13px;margin-top:2px">доходность аренды</div></div>
    </div>
    <p class="sub" style="font-size:14px;margin-top:10px">Источник: ${esc(d.src)}. Цифры по рынку района — ориентир, не гарантия по конкретному объекту.</p>` : '';

  const intro=`<section style="padding-bottom:0"><div class="container">
    <p class="kicker">Пхукет · ${esc(d.ru)}</p>
    <h1 style="font-size:clamp(28px,4.2vw,42px);margin:0 0 12px">Недвижимость в ${esc(d.in)}, Пхукет</h1>
    <p class="sub" style="max-width:64ch;margin:0">${esc(d.about)}</p>
    ${market}
  </div></section>`;

  const mine = OI[d.ru]
    ? `<section class="obj-index" style="padding:40px 0"><div class="container">
    <h2 style="font-size:22px;margin:0 0 6px">Объекты в ${esc(d.in)}</h2>
    <p class="sub" style="margin:0 0 18px">Проекты этого района из нашего каталога — с ценами от застройщика.</p>
    <div class="oi-grid"><div class="oi-col">${OI[d.ru]}</div></div>
  </div></section>`
    : '';

  const others=`<section style="padding-top:0"><div class="container">
    <h2 style="font-size:20px;margin:0 0 12px">Другие районы</h2>
    <div class="filters">${links}</div>
  </div></section>`;

  // автофильтр каталога по этому району
  const autoFilter=`<script>
window.addEventListener('load',function(){
  try{
    if(typeof activeFilter!=='undefined'&&typeof applyFilters==='function'){
      activeFilter.loc=new Set([${JSON.stringify(d.ru)}]);
      if(typeof buildLocChips==='function') buildLocChips();
      applyFilters();
    }
  }catch(e){}
});
</script>`;

  // заголовок секции дублирует H1 страницы и отодвигает объекты за экран
  saleHtml = saleHtml.replace(
    /<div class="head-row reveal">\s*<div>\s*<span class="kicker"[^>]*>[\s\S]*?<\/p>\s*<\/div>\s*<div class="arrows">[\s\S]*?<\/div>\s*<\/div>/, '');
  saleHtml = saleHtml.replace(
    /<div class="head-row reveal">\s*<div>\s*<span class="kicker"[^>]*>[\s\S]*?<\/p>\s*<\/div>/, '<div class="head-row reveal"><div>');
  let html=head+'\n'+intro+'\n'+saleHtml+'\n'+mine+'\n'+others+'\n'+tail;
  html=html.replace(/<title>[\s\S]*?<\/title>/,'<title>'+esc(title)+'</title>');
  html=html.replace(/(<meta name="description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
  html=html.replace(/(<link rel="canonical" href=")[^"]*(")/,'$1'+url+'$2');
  html=html.replace(/(<meta property="og:url" content=")[^"]*(")/,'$1'+url+'$2');
  html=html.replace(/(<meta property="og:title" content=")[^"]*(")/,'$1'+esc(title)+'$2');
  html=html.replace(/(<meta property="og:description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
  // страница лежит в подпапке — ресурсы и ссылки на уровень выше
  html=html.replace(/href="#top"/g,'href="../index.html"');
  html=html.replace(/href="#(why|sale|rent|map|quiz|about|faq|do|steps|contacts)"/g,'href="../index.html#$1"');
  html=html.replace(/(href|src)="(img\/|object\/|favicon|buy\.html|rent\.html|owner\.html|privacy\.html|rules\.html|terms\.html|index\.html)/g,'$1="../$2');
  html=html.replace('</body>',autoFilter+'\n</body>');
  fs.writeFileSync(path.join(outDir,d.slug+'.html'),html);
  made.push(d.slug);
}
console.log('страниц районов:',made.length,'→',made.join(', '));
