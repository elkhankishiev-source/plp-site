/* Генератор листов-офферов по одному шаблону. 09.10.2026.
   Эльнур: «всё равно разнобой, не соблюдаются блоки, нет продающей логики»; «размести логично фотки квартир,
   не делай кашу, следуй плану чёткому». Порядок блоков одобрен 08.10 и одинаков на всех листах:
     1 шапка: что продаём · 2 квартиры и цены (таблица → фото квартир → планировки) · 3 как купить ·
     4 как войти по стартовой цене · 5 кому подойдёт и наш взгляд · 6 доход · 7 проект (общие зоны, инфраструктура,
     мастер-план) · 8 место · 9 рынок · 10 застройщик · 11 кнопки.
   Фото квартир — только в блоке 2, фото общих зон — только в блоке 7, одно фото дважды не ставим.
   Данные: offers/<slug>/sheet.json (тексты и цифры перенесены из проверенных листов).
     node tools/offer_sheet.mjs kuartz fizz vibe2 zero-naiyang eden   → offers/<slug>/page.htm */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const DD = (name, style) => `<div class="dd" style="${style}"><img src="../../img/doodles/${name}.webp" alt=""></div>`;
const ROT = ['-.6deg', '.5deg', '.4deg', '-.5deg', '.6deg', '-.4deg'];

const CSS = `
/* offer_sheet.mjs: единые ряды фото */
.dd{position:absolute;z-index:6;pointer-events:none}
.dd img{width:100%;display:block;filter:drop-shadow(0 .6mm .8mm rgba(23,24,15,.18))}
.plans-band{position:relative}
.pgrid.c3{grid-template-columns:repeat(3,1fr);gap:7mm 5mm}
.pgrid.c3 .pol img{height:38mm}
.pgrid.plans .pol img{object-fit:contain;background:#fff}
.sub3{font-weight:700;font-size:7.6pt;letter-spacing:.14em;text-transform:uppercase;color:var(--olive);margin:8mm 0 3mm}
`;

function polRow(items, cols, plans) {
  if (!items || !items.length) return '';
  const c = cols || (items.length === 3 || items.length === 5 || items.length === 6 ? 3 : 2);
  return `<div class="pgrid${c === 3 ? ' c3' : ''}${plans ? ' plans' : ''}">\n` +
    items.map((p, i) => `    <div class="pol" style="transform:rotate(${plans ? '0deg' : ROT[i % ROT.length]})"><img src="${esc(p.src)}" alt="${esc(p.alt || p.cap)}"><i>${esc(p.cap)}</i></div>`).join('\n') +
    '\n  </div>';
}

function wide(p, h) {
  return `<div class="photo" style="position:relative;left:0;top:0;width:100%;height:${h || 101}mm;margin-top:5mm${p.contain ? ';background:#fff' : ''}"><img${p.contain ? ' style="object-fit:contain"' : ''} src="${esc(p.src)}" alt="${esc(p.alt)}"></div>` +
    (p.cap ? `\n  <p class="src">${p.cap}</p>` : '');
}

function cardsRow(cards, layout) {
  if (!cards || !cards.length) return '';
  if (cards.length === 1) return `<div style="margin-top:4mm">\n    ${cards[0]}\n  </div>`;
  return `<div class="grid ${layout || 'g2'}" style="margin-top:4mm;align-items:start">\n    ${cards.join('\n    ')}\n  </div>`;
}

function section(eyebrow, h2, body, extra) {
  return `<section class="pad">\n  <div class="eyebrow">${eyebrow}</div>\n  <h2>${h2}</h2>${extra ? '\n  ' + extra : ''}\n  ${body.trim()}\n</section>`;
}

function render(J) {
  const out = [];
  // 1. шапка
  let hero = J.hero;
  hero = hero.replace(/\n<\/div>$/, '\n  ' + DD('palm', 'left:186mm;top:88mm;width:18mm;transform:rotate(-6deg)') + '\n</div>');
  out.push(J.top, hero, J.stats);

  // 2. квартиры и цены
  const U = J.units;
  let ub = '';
  if (U.lead) ub += `<p class="lead">${U.lead}</p>\n  `;
  if (U.facts) ub += U.facts + '\n  ';
  ub += cardsRow(U.cards, U.cards_layout);
  if (U.photos && U.photos.length) {
    ub += `\n  <div class="sub3">Квартиры внутри</div>\n  ` + polRow(U.photos);
    if (U.photos_note) ub += `\n  <p class="src">${U.photos_note}</p>`;
  }
  if (U.plans_pol && U.plans_pol.length) {
    ub += `\n  <div class="sub3">${U.plans_title || 'Планировки'}</div>\n  ` + polRow(U.plans_pol, U.plans_cols || (U.plans_pol.length > 4 ? 3 : 2), true);
    if (U.plans_src) ub += `\n  <p class="src">${U.plans_src}</p>`;
  }
  if (U.plans && U.plans.length) {
    ub += `\n  <div class="sub3">${U.plans_title || 'Планировки'}</div>\n  ` + U.plans.map((p) => wide(p, 101)).join('\n  ');
  }
  if (U.accent) {
    out.push(`<section class="pad">\n  <div class="accent">\n    <div class="ph" style="background:var(--rust);color:#fff">${U.accent}</div>\n    <div class="eyebrow" style="margin-top:2mm">Квартиры и цены</div>\n    <h2 style="max-width:none">${U.h2}</h2>\n    ${ub}\n  </div>\n</section>`);
  } else {
    out.push(section('Квартиры и цены', U.h2, ub));
  }

  // 3. как купить
  out.push(section('Как купить', J.buy.h2, J.buy.html, DD('key', 'right:15mm;top:9mm;width:15mm;transform:rotate(10deg)')));

  // 4. как войти по стартовой цене
  const S = J.step;
  out.push(`<section class="pad">\n  <div class="plans-band">\n    <div class="eyebrow" style="color:var(--sun)">${S.eyebrow}</div>\n    <h2 style="color:#fff">${S.h2}</h2>\n    ` +
    DD('calendar', 'right:8mm;top:-6mm;width:15mm;transform:rotate(7deg)') + '\n    <ol class="tl2">\n' +
    S.items.map(([b, s, e]) => `      <li><b>${b}</b><span>${s}</span><em>${e}</em></li>`).join('\n') +
    `\n    </ol>\n    <p class="src" style="color:rgba(255,255,255,.6)">${S.src}</p>\n  </div>\n</section>`);

  // 5. кому подойдёт и наш взгляд
  out.push(section('Кому подойдёт', J.who.h2, J.who.html));

  // 6. доход
  out.push(section('Доход', J.income.h2, J.income.html, DD('chart', 'right:15mm;top:10mm;width:15mm;transform:rotate(5deg)')));

  // 7. проект: общие зоны, инфраструктура, мастер-план
  const P = J.project;
  let pb = '';
  if (P.lead) pb += `<p class="lead">${P.lead}</p>\n  `;
  if (P.big) pb += wide(P.big, 101) + '\n  ';
  if (P.photos && P.photos.length) pb += `<div class="sub3">Общие зоны</div>\n  ` + polRow(P.photos) + '\n  ';
  pb += cardsRow(P.cards, 'g2');
  if (P.plans && P.plans.length) pb += `\n  <div class="sub3">${P.plans_title || 'Мастер-план'}</div>\n  ` + P.plans.map((p) => wide(p, p.contain ? 101 : 101)).join('\n  ');
  out.push(section('Проект', P.h2, pb));

  // 8. место
  out.push(section('Место', J.place.h2, J.place.html, DD('pin', 'right:15mm;top:9mm;width:14mm;transform:rotate(-6deg)')));
  // 9. рынок
  out.push(section(J.market.eyebrow || 'Рынок', J.market.h2, J.market.html));
  // 10. застройщик (+ прошлые фазы)
  out.push(section('Кто строит', J.developer.h2, J.developer.html));
  for (const x of J.developer.after || []) out.push(x);

  // 11. кнопки: PDF как на остальных листах
  let cta = J.cta;
  if (!/\.pdf"/.test(cta) && J.pdf) {
    cta = cta.replace(/(<a href="https:\/\/t\.me\/property_library_phuket">.*?<\/a>)/s,
      `$1\n    <a href="${esc(J.pdf)}" download><b>PDF</b><span>скачать лист</span></a>`);
  }
  { /* кнопки в одну строку при любом их числе */
    const n = (cta.match(/<a /g) || []).length;
    if (n) cta = cta.replace('<div class="links">', `<div class="links" style="grid-template-columns:1.4fr repeat(${n - 1},1fr)">`);
  }
  out.push(cta);

  let head = J.head;
  if (!head.includes('offer_sheet.mjs: единые ряды фото')) head = head.replace('</style>', CSS + '</style>');
  return head + '<body><div class="w">\n\n' + out.join('\n\n') + J.tail;
}

const slugs = process.argv.slice(2);
if (!slugs.length) { console.log('node tools/offer_sheet.mjs <slug> …'); process.exit(1); }
for (const slug of slugs) {
  const J = JSON.parse(fs.readFileSync(path.join(ROOT, 'offers', slug, 'sheet.json'), 'utf8'));
  const html = render(J);
  fs.writeFileSync(path.join(ROOT, 'offers', slug, 'page.htm'), html);
  console.log(slug, 'собран:', html.length, 'знаков');
}
