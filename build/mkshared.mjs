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
    mnav:   '<a href="owner.html" onclick="toggleNav(false)" data-i18n="nav.cabinet">Кабинет</a>',
  },
  cabinet: {
    switch: '<a href="index.html">Сайт</a><b>Кабинет</b>',
    mnav:   '<a href="index.html" onclick="toggleNav(false)">На сайт</a>',
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
  fs.writeFileSync(full, html);
  console.log(`${file}: обновлено частей ${done}/${MARKS.length}`);
  return done;
}

/* у анкеты и страницы управления своя вёрстка без подвала — им отдаём шапку и меню */
const targets = [['index.html', 'site'], ['owner.html', 'cabinet'],
                 ['add-property.html', 'site']];
let total = 0;
for (const [f, v] of targets) {
  if (!fs.existsSync(path.join(ROOT, f))) continue;
  total += apply(f, v);
}
console.log('всего вставок:', total);
