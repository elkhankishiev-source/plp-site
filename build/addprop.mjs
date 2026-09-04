import fs from 'node:fs';
import path from 'node:path';
const ROOT='/Users/elnurkhankishiev/plp-site';
const SITE='https://property-library.com';
const SB='https://dyxufgjrumebvrhadjun.supabase.co';
const ANON='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR5eHVmZ2pydW1lYnZyaGFkanVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyMzcxOTYsImV4cCI6MjA5MzgxMzE5Nn0.VLIX0d-OGqZfDpS6WWaBaGkEsTxWa4iQhCozRqOcEAo';
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const idx=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const mStart=idx.indexOf('<main'), mOpen=idx.indexOf('>',mStart)+1, mEnd=idx.indexOf('</main>');
const head=idx.slice(0,mOpen), tail=idx.slice(mEnd);

const chips=(id,arr)=>`<div class="filters" id="${id}">`+
  arr.map(v=>`<span class="chipf" data-v="${esc(v)}">${esc(v)}</span>`).join('')+`</div>`;
const lab=t=>`<label style="display:block;color:#5c5c54;font-size:13px;margin:18px 0 6px">${esc(t)}</label>`;
const inp=(id,ph,type='text')=>`<input id="${id}" type="${type}" placeholder="${esc(ph)}" style="width:100%;border:1px solid #e7e5dc;border-radius:14px;padding:12px 14px;font-size:15px;font-family:inherit">`;
const ta=(id,ph)=>`<textarea id="${id}" placeholder="${esc(ph)}" style="width:100%;min-height:92px;border:1px solid #e7e5dc;border-radius:14px;padding:12px 14px;font-size:15px;font-family:inherit"></textarea>`;

const body=`
<section style="padding-bottom:0"><div class="container" style="max-width:820px">
  <p class="kicker">Собственникам</p>
  <h1 style="font-size:clamp(28px,4.2vw,42px);margin:0 0 10px">Разместить объект</h1>
  <p class="sub" style="max-width:62ch;margin:0">Пять коротких шагов: расскажите об объекте, приложите фото —
  мы проверим, оформим карточку и опубликуем. Регистрация не нужна.</p>

  <div class="ap-steps" id="ap-steps">
    <span class="on">1 · Объект</span><span>2 · Условия</span><span>3 · Фото</span><span>4 · Описание</span><span>5 · Контакты</span>
  </div>

  <div class="ap-card">
    <div class="ap-step" data-step="1">
      <h2 style="font-size:20px;margin:0 0 4px">Что у вас за объект</h2>
      ${lab('Тип')}${chips('ap-kind',['Вилла','Кондо','Дом','Таунхаус','Участок'])}
      ${lab('Спален')}${chips('ap-beds',['Студия','1','2','3','4 и больше'])}
      ${lab('Район')}${chips('ap-area',['Банг Тао','Лаян','Сурин','Камала','Раваи','Най Харн','Ката','Патонг','Другой'])}
      ${lab('Площадь, м²')}${inp('ap-area-sqm','Например, 320')}
    </div>

    <div class="ap-step" data-step="2" hidden>
      <h2 style="font-size:20px;margin:0 0 4px">Готовность и цель</h2>
      ${lab('Объект готов?')}${chips('ap-stage',['Готов','Строится','Уже сдаётся'])}
      ${lab('Что хотите')}${chips('ap-goal',['Сдавать через вас','Продать','Посчитать доходность'])}
      ${lab('Ожидаемая цена или ставка, ฿')}${inp('ap-price','Например, 24500000 или 165000 в месяц')}
      <p class="sub" style="font-size:13px;margin-top:8px">Точную цену обсудим — сейчас достаточно ориентира.</p>

      <div id="ap-nightly" hidden style="margin-top:18px;padding-top:16px;border-top:1px solid rgba(10,10,10,.08)">
        <h3 style="font-size:16px;margin:0 0 4px">Стоимость проживания</h3>
        <p class="sub" style="font-size:13px;margin:0 0 12px">Заполните сетку — и сайт сам посчитает цену на любые даты
        со скидкой за срок. Без неё придётся каждый раз уточнять вручную.</p>
        <div class="ap-row3">
          ${lab('Высокий сезон, ฿/ночь<span class="ap-hint">декабрь–апрель</span>')}${inp('ap-nh','18000')}
          ${lab('Средний, ฿/ночь<span class="ap-hint">май–июль</span>')}${inp('ap-ns','13000')}
          ${lab('Низкий, ฿/ночь<span class="ap-hint">август–ноябрь</span>')}${inp('ap-nl','9000')}
        </div>
        <div class="ap-row3" style="margin-top:12px">
          ${lab('Скидка от 3 ночей, %')}${inp('ap-d3','')}
          ${lab('Скидка от 7 ночей, %')}${inp('ap-d7','')}
          ${lab('Скидка от 14 ночей, %')}${inp('ap-d14','')}
        </div>
        <div class="ap-row3" style="margin-top:12px">
          ${lab('Скидка от 30 ночей, %')}${inp('ap-d30','')}
          ${lab('Скидка от 90 ночей, %')}${inp('ap-d90','')}
          ${lab('Минимальный срок, ночей')}${inp('ap-min','')}
        </div>
        <p class="sub" style="font-size:12.5px;margin-top:8px">Заполняйте только те ступени, которые у вас есть —
        пустые не показываем. Считаем всегда по самой выгодной для гостя.</p>
      </div>
    </div>

    <div class="ap-step" data-step="3" hidden>
      <h2 style="font-size:20px;margin:0 0 4px">Фото и видео</h2>
      <p class="sub" style="margin:0 0 12px">Чем больше кадров, тем быстрее опубликуем. Снаружи, внутри, бассейн, вид.
      Можно и видео — до 30 файлов.</p>
      <div class="ap-drop" id="ap-drop">
        <input type="file" id="ap-files" accept="image/*,video/*" multiple hidden>
        <b>Перетащите файлы сюда</b>
        <span>или нажмите, чтобы выбрать</span>
      </div>
      <div class="ap-grid" id="ap-preview"></div>
      <div id="ap-upstat" class="sub" style="font-size:13px;margin-top:8px"></div>
    </div>

    <div class="ap-step" data-step="4" hidden>
      <h2 style="font-size:20px;margin:0 0 4px">Опишите объект</h2>
      ${lab('Название комплекса и адрес')}${inp('ap-address','Например: Laguna Park 2, вилла 14/3')}
      ${lab('Описание')}${ta('ap-desc','Что важно знать: планировка, вид, ремонт, чем хорош район')}
      ${lab('Что есть в доме')}${ta('ap-amen','Бассейн, барбекю, парковка, охрана, стиральная машина, генератор')}
    </div>

    <div class="ap-step" data-step="5" hidden>
      <h2 style="font-size:20px;margin:0 0 4px">Как с вами связаться</h2>
      ${lab('Как к вам обращаться')}${inp('ap-name','Например, Александр')}
      ${lab('Телефон')}${inp('ap-phone','+66 95 123 4567','tel')}
      ${lab('Где удобнее общаться')}${chips('ap-via',['WhatsApp','Telegram','Звонок'])}
      <div class="ap-sum" id="ap-sum"></div>
    </div>

    <div class="ap-nav">
      <button type="button" class="btn btn-ghost" id="ap-back" hidden>Назад</button>
      <button type="button" class="btn btn-primary" id="ap-next">Дальше</button>
    </div>
    <div class="ok" id="ap-ok" style="color:#3f6b34;font-size:14px;margin-top:10px"></div>
    <div class="err" id="ap-err" style="color:#8f4b3a;font-size:14px;margin-top:10px"></div>
  </div>
</div></section>

<style>
.ap-steps{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 16px}
.ap-steps span{font-size:12.5px;color:var(--muted);border:1px solid rgba(10,10,10,.1);
  border-radius:999px;padding:6px 12px;white-space:nowrap}
.ap-steps span.on{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:600}
.ap-steps span.done{background:var(--green-soft);border-color:var(--green);color:var(--ink)}
.ap-card{background:#fff;border:1px solid #e7e5dc;border-radius:24px;padding:clamp(20px,3vw,30px)}
.ap-nav{display:flex;gap:10px;margin-top:24px}
.ap-nav .btn{flex:0 0 auto}
.ap-drop{border:2px dashed #d8d5c9;border-radius:18px;padding:28px;text-align:center;cursor:pointer;
  display:flex;flex-direction:column;gap:4px;transition:border-color .2s,background .2s}
.ap-drop:hover,.ap-drop.over{border-color:var(--green-deep);background:#fafaf5}
.ap-drop b{font-size:15px}.ap-drop span{color:var(--muted);font-size:13.5px}
.ap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:10px;margin-top:14px}
.ap-thumb{position:relative;aspect-ratio:1;border-radius:12px;overflow:hidden;background:#f1f0ea;
  display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted)}
.ap-thumb img{width:100%;height:100%;object-fit:cover}
.ap-thumb .x{position:absolute;top:4px;right:4px;width:22px;height:22px;border-radius:50%;
  background:rgba(10,10,10,.6);color:#fff;border:0;font-size:14px;line-height:1;cursor:pointer}
.ap-thumb .bar{position:absolute;left:0;bottom:0;height:3px;background:var(--green-deep);width:0}
.ap-sum{background:#f7f6f1;border-radius:16px;padding:16px 18px;margin-top:18px;font-size:14.5px;line-height:1.7}
.ap-sum b{color:var(--ink)}
</style>

<script>
(function(){
  var SB=${JSON.stringify(SB)}, ANON=${JSON.stringify(ANON)};
  var API='https://proplib.app.n8n.cloud/webhook/uk-owner';
  var g=function(id){return document.getElementById(id);};
  var num=function(id){var e=g(id); return e?(parseInt(String(e.value).replace(/[^0-9]/g,''),10)||0):0;};
  var step=1, MAXSTEP=5, files=[], ref='obj-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7);

  ['ap-kind','ap-beds','ap-area','ap-stage','ap-goal','ap-via'].forEach(function(id){
    var box=g(id); if(!box) return;
    Array.prototype.forEach.call(box.querySelectorAll('.chipf'),function(c){
      c.style.cursor='pointer';
      c.onclick=function(){
        var was=c.classList.contains('on');
        Array.prototype.forEach.call(box.querySelectorAll('.chipf'),function(x){x.classList.remove('on');});
        if(!was) c.classList.add('on');
        /* сетка цен нужна только тем, кто сдаёт: продавцу её показывать незачем */
        if(id==='ap-goal'){
          var sell=/Продать/.test(pick('ap-goal')||'');
          var nb=g('ap-nightly'); if(nb) nb.hidden = sell || !pick('ap-goal');
        }
      };
    });
  });
  function pick(id){ var el=g(id).querySelector('.chipf.on'); return el?el.getAttribute('data-v'):''; }

  function show(n){
    step=n;
    Array.prototype.forEach.call(document.querySelectorAll('.ap-step'),function(s){
      s.hidden = (+s.getAttribute('data-step') !== n);
    });
    var chips=g('ap-steps').children;
    for(var i=0;i<chips.length;i++){
      chips[i].classList.toggle('on', i===n-1);
      chips[i].classList.toggle('done', i<n-1);
    }
    g('ap-back').hidden = (n===1);
    g('ap-next').textContent = (n===MAXSTEP) ? 'Отправить объект' : 'Дальше';
    if(n===MAXSTEP) summary();
    window.scrollTo({top:g('ap-steps').getBoundingClientRect().top+window.scrollY-90,behavior:'smooth'});
  }
  function summary(){
    var rows=[['Объект',pick('ap-kind')],['Спален',pick('ap-beds')],['Район',pick('ap-area')],
      ['Площадь',g('ap-area-sqm').value.trim()?g('ap-area-sqm').value.trim()+' м²':''],
      ['Готовность',pick('ap-stage')],['Цель',pick('ap-goal')],
      ['Ориентир по цене',g('ap-price').value.trim()],
      ['Адрес',g('ap-address').value.trim()],['Файлов',files.length?String(files.length):'']];
    g('ap-sum').innerHTML='<b>Проверьте, всё ли верно</b><br>'+
      rows.filter(function(r){return r[1];}).map(function(r){return r[0]+': '+r[1];}).join('<br>');
  }

  /* ── файлы ── */
  var drop=g('ap-drop'), input=g('ap-files');
  drop.onclick=function(){ input.click(); };
  ['dragenter','dragover'].forEach(function(e){ drop.addEventListener(e,function(ev){ev.preventDefault();drop.classList.add('over');}); });
  ['dragleave','drop'].forEach(function(e){ drop.addEventListener(e,function(ev){ev.preventDefault();drop.classList.remove('over');}); });
  drop.addEventListener('drop',function(ev){ addFiles(ev.dataTransfer.files); });
  input.onchange=function(){ addFiles(input.files); input.value=''; };

  function addFiles(list){
    Array.prototype.forEach.call(list,function(f){
      if(files.length>=30) return;
      if(f.size > 40*1024*1024){ g('ap-err').textContent='Файл «'+f.name+'» больше 40 МБ — уменьшите или пришлите ссылкой.'; return; }
      var item={file:f,name:f.name,type:f.type,url:null,done:false};
      files.push(item); drawThumb(item); upload(item);
    });
    stat();
  }
  function drawThumb(item){
    var d=document.createElement('div'); d.className='ap-thumb'; item.el=d;
    if(/^image\\//.test(item.type)){
      var img=document.createElement('img'); img.alt=''; img.src=URL.createObjectURL(item.file); d.appendChild(img);
    } else { d.appendChild(document.createTextNode('видео')); }
    var x=document.createElement('button'); x.className='x'; x.type='button'; x.textContent='×';
    x.onclick=function(ev){ ev.stopPropagation(); files=files.filter(function(f){return f!==item;}); d.remove(); stat(); };
    var bar=document.createElement('div'); bar.className='bar'; item.bar=bar;
    d.appendChild(x); d.appendChild(bar);
    g('ap-preview').appendChild(d);
  }
  function upload(item){
    var safe=item.name.replace(/[^a-zA-Z0-9._-]/g,'_').slice(-60);
    var key='intake/'+ref+'/'+Date.now()+'_'+safe;
    var xhr=new XMLHttpRequest();
    xhr.open('POST', SB+'/storage/v1/object/object-media/'+key, true);
    xhr.setRequestHeader('Authorization','Bearer '+ANON);
    xhr.setRequestHeader('apikey',ANON);
    xhr.setRequestHeader('x-upsert','true');
    if(item.type) xhr.setRequestHeader('Content-Type',item.type);
    xhr.upload.onprogress=function(e){ if(e.lengthComputable&&item.bar) item.bar.style.width=Math.round(e.loaded/e.total*100)+'%'; };
    xhr.onload=function(){
      if(xhr.status>=200&&xhr.status<300){
        item.done=true; item.url=SB+'/storage/v1/object/public/object-media/'+key;
        if(item.bar) item.bar.style.width='100%';
      } else { item.error=true; if(item.el) item.el.style.borderColor='#c98b7a'; }
      stat();
    };
    xhr.onerror=function(){ item.error=true; stat(); };
    xhr.send(item.file);
  }
  function stat(){
    var done=files.filter(function(f){return f.done;}).length;
    var bad=files.filter(function(f){return f.error;}).length;
    g('ap-upstat').textContent = files.length
      ? ('Загружено '+done+' из '+files.length+(bad?', с ошибкой '+bad:''))
      : '';
  }

  g('ap-back').onclick=function(){ if(step>1) show(step-1); };
  g('ap-next').onclick=function(){
    g('ap-err').textContent=''; g('ap-ok').textContent='';
    if(step===1 && !pick('ap-kind')){ g('ap-err').textContent='Выберите тип объекта.'; return; }
    if(step<MAXSTEP){ show(step+1); return; }

    var name=g('ap-name').value.trim(), phone=g('ap-phone').value.trim();
    if(!name){ g('ap-err').textContent='Как к вам обращаться?'; return; }
    if(!phone){ g('ap-err').textContent='Оставьте телефон — иначе не сможем ответить.'; return; }
    if(files.some(function(f){return !f.done && !f.error;})){ g('ap-err').textContent='Дождитесь загрузки файлов.'; return; }

    var btn=g('ap-next'); btn.disabled=true; btn.textContent='Отправляем…';
    fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      action:'submit_object', ref:ref, name:name, phone:phone, contact_via:pick('ap-via'),
      kind:pick('ap-kind'), beds:pick('ap-beds'), district:pick('ap-area'),
      area_sqm:g('ap-area-sqm').value.trim(), stage:pick('ap-stage'), goal:pick('ap-goal'),
      price_thb:(g('ap-price').value.replace(/[^0-9]/g,'')||null),
      address:g('ap-address').value.trim(), description:g('ap-desc').value.trim(),
      amenities:g('ap-amen').value.trim(),
      /* сетка цен: по ней сайт считает стоимость на любые даты */
      nightly:{high:num('ap-nh'), shoulder:num('ap-ns'), low:num('ap-nl')},
      discounts:[{nights:3,off:num('ap-d3')},{nights:7,off:num('ap-d7')},{nights:14,off:num('ap-d14')},
                 {nights:30,off:num('ap-d30')},{nights:90,off:num('ap-d90')}].filter(function(d){return d.off>0;}),
      min_stay:num('ap-min'),
      media:files.filter(function(f){return f.done;}).map(function(f){return {url:f.url,type:f.type,name:f.name};})
    })}).then(function(r){return r.json();}).then(function(d){
      btn.disabled=false; btn.textContent='Отправить объект';
      if(d&&d.ok){
        document.querySelector('.ap-card').innerHTML=
          '<h2 style="font-size:22px;margin:0 0 8px">Спасибо, объект принят</h2>'+
          '<p class="sub" style="margin:0 0 14px">Менеджер посмотрит материалы, оформит карточку и свяжется с вами. '+
          'Обычно это занимает один рабочий день.</p>'+
          '<div class="hero-cta" style="margin:0"><a class="btn btn-primary" href="index.html">На главную</a>'+
          '<a class="btn btn-ghost" href="https://wa.me/66955492587" target="_blank" rel="noopener">Написать в WhatsApp</a></div>';
        window.scrollTo({top:0,behavior:'smooth'});
      } else { g('ap-err').textContent='Не отправилось. Напишите нам в WhatsApp — примем объект вручную.'; }
    }).catch(function(){
      btn.disabled=false; btn.textContent='Отправить объект';
      g('ap-err').textContent='Нет связи с сервером.';
    });
  };

  show(1);
})();
</script>`;

let html=head+'\n'+body+'\n'+tail;
const url=SITE+'/add-property.html';
const title='Разместить объект на Пхукете — сдать или продать через Property Library';
const extraCss=`
.ap-row3{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.ap-hint{display:block;font-weight:400;font-size:11.5px;color:var(--muted);margin-top:2px}
`;
const desc='Расскажите об объекте и приложите фото — проверим, оформим карточку и опубликуем. Управление арендой, отчёты и выплаты в личном кабинете.';
html=html.replace(/<title>[\s\S]*?<\/title>/,'<title>'+esc(title)+'</title>');
html=html.replace(/(<meta name="description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
html=html.replace(/(<link rel="canonical" href=")[^"]*(")/,'$1'+url+'$2');
html=html.replace(/(<meta property="og:url" content=")[^"]*(")/,'$1'+url+'$2');
html=html.replace(/(<meta property="og:title" content=")[^"]*(")/,'$1'+esc(title)+'$2');
html=html.replace(/(<meta property="og:description" content=")[^"]*(")/,'$1'+esc(desc)+'$2');
html=html.replace(/href="#top"/g,'href="index.html"');
html=html.replace('</style>', extraCss+'</style>');
html=html.replace(/href="#(why|sale|rent|map|quiz|about|faq|do|steps|contacts)"/g,'href="index.html#$1"');
fs.writeFileSync(path.join(ROOT,'add-property.html'), html);
console.log('add-property.html собран:', html.length, 'байт');
