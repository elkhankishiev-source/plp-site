/* Общие части сайта и кабинета — в одном месте.
   Эльнур 06.09: «сайт и кабинет по-прежнему не один ресурс». Шапка, мобильное
   меню и подвал теперь лежат в build/parts и вставляются в обе страницы между
   маркерами. Правишь один файл — меняется везде, расхождения больше не копятся. */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const P = f => fs.readFileSync(path.join(ROOT, 'build/parts', f), 'utf8');

const HEADER = P('header.html');
const MNAV   = P('mnav.html');
const FOOTER = P('footer.html');
const HEADTH = P('head-theme.html');

/* чем страницы отличаются: подсветка текущего места */
const VARIANTS = {
  site: {
    switch: '<b>Сайт</b><a href="owner.html" data-i18n="nav.cabinet">Кабинет</a>',
    mnav:   '<span class="swch mswch" role="group" aria-label="Сайт или кабинет"><b>Сайт</b><a href="owner.html" onclick="toggleNav(false)" data-i18n="nav.cabinet">Кабинет</a></span>',
  },
  cabinet: {
    switch: '<a href="index.html">Сайт</a><b>Кабинет</b>',
    mnav:   '<span class="swch mswch" role="group" aria-label="Сайт или кабинет"><a href="index.html" onclick="toggleNav(false)">Сайт</a><b>Кабинет</b></span>',
  },
};

const UI = fs.readFileSync(path.join(ROOT, 'build/parts/ui-common.css'), 'utf8');

const MARKS = [
  ['<!-- PLP:HEADER:START -->', '<!-- PLP:HEADER:END -->', HEADER],
  ['<!-- PLP:MNAV:START -->',   '<!-- PLP:MNAV:END -->',   MNAV],
  ['<!-- PLP:FOOTER:START -->', '<!-- PLP:FOOTER:END -->', FOOTER],
  ['<!-- PLP:HEADTHEME:START -->', '<!-- PLP:HEADTHEME:END -->', HEADTH],
  /* общий блок стилей интерфейса — внутри <style>, поэтому маркеры без HTML-комментария */
  ['/* PLP:UI:START */', '/* PLP:UI:END */', UI],
];

function apply(file, variant) {
  const full = path.join(ROOT, file);
  let html = fs.readFileSync(full, 'utf8');
  const v = VARIANTS[variant];
  let done = 0;

  for (const [open, close, part] of MARKS) {
    const i = html.indexOf(open), j = html.indexOf(close);
    if (i === -1 || j === -1 || j < i) continue;          // маркеров нет — не трогаем
    const body = part.replace('<!--SWITCH-->', v.switch).replace('<!--MNAV-LINK-->', v.mnav);
    html = html.slice(0, i + open.length) + '\n' + body + '\n' + html.slice(j);
    done++;
  }
  /* 15.09: подвал и меню пишут ссылки якорями (#sale, #map, #about, #faq). На главной они
     ведут к разделам, а в кабинете и анкете таких разделов нет — ссылки были мёртвыми.
     Якорь, которого на странице нет, ведём на главную к этому разделу. */
  let fixed = 0;
  if (!file.endsWith('.css')) html = html.replace(/href="#([a-zA-Z][\w-]*)"/g, (all, id) => {
    if (html.includes('id="' + id + '"')) return all;
    fixed++;
    return id === 'top' ? 'href="/"' : 'href="/#' + id + '"';
  });
  fs.writeFileSync(full, html);
  console.log(`${file}: обновлено частей ${done}/${MARKS.length}` + (fixed ? `, якорей на главную: ${fixed}` : ''));
  return done;
}

/* у анкеты и страницы управления своя вёрстка без подвала — им отдаём шапку и меню */
/* 20.09: стили витрины переехали в assets/app.css (build/mkassets.mjs). Общий
   блок интерфейса живёт по тем же маркерам, только уже не внутри страницы. */
const targets = [['index.html', 'site'], ['owner.html', 'cabinet'],
                 ['add-property.html', 'site'], ['assets/app.css', 'site']];
let total = 0;
for (const [f, v] of targets) {
  if (!fs.existsSync(path.join(ROOT, f))) continue;
  total += apply(f, v);
}
console.log('всего вставок:', total);

/* 16.09: add-property.html носит копию каталога и раньше застывала — в ней месяцами
   жили старые цены и ссылки на фото с сайта застройщика. Держим копию свежей. */
(function syncAddPropCatalog(){
  const catPath = path.join(ROOT, 'assets/catalog.js');
  const idxPath = fs.existsSync(catPath) ? catPath : path.join(ROOT, 'index.html');
  const apPath = path.join(ROOT, 'add-property.html');
  if (!fs.existsSync(apPath)) return;
  const idx = fs.readFileSync(idxPath, 'utf8');
  const ap = fs.readFileSync(apPath, 'utf8');
  /* 21.09: синхронизировался только каталог ПРОДАЖИ, а блок аренды в анкете
     застыл с прошлой весны. Там остались внутренние коды с номерами вилл
     (PLP-MANOR-S14, PLP-ESTELLA-A24) и мёртвые адреса фото на Supabase, хотя
     анкета открыта для индексации. Обновляем оба блока. */
  let out = ap, обновлено = [];
  for (const [S, E, имя] of [['/* PLP:AUTO-CATALOG:START', 'PLP:AUTO-CATALOG:END', 'продажа'],
                             ['/* PLP:AUTO-RENTALS:START', 'PLP:AUTO-RENTALS:END', 'аренда']]) {
    const i = idx.indexOf(S), e = idx.indexOf(E);
    const j = out.indexOf(S), k = out.indexOf(E);
    if (i < 0 || e < 0 || j < 0 || k < 0) continue;
    const block = idx.slice(i, idx.indexOf('*/', e) + 2);
    const стало = out.slice(0, j) + block + out.slice(out.indexOf('*/', k) + 2);
    if (стало !== out) { out = стало; обновлено.push(имя); }
  }
  if (out !== ap) {
    fs.writeFileSync(apPath, out);
    console.log('add-property.html: каталог обновлён из общего файла —', обновлено.join(' и '));
  }
})();
