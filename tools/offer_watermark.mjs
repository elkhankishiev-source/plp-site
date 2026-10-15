// 15.10.2026 Эльнур: «на наших офферах должны быть по страницам водяные знаки логотипа… чтобы не мешало лидам, но и не могли воровать себе».
// Водяной знак: логотип PL + «property-library.com», по диагонали повтором, прозрачность 8% на картинках и 5% поверх всего листа;
// строка в подвале «Property Library Phuket · property-library.com». Рисунок — img/brand/plp-wm.svg.
// Вставка идемпотентна (метка WM-PLP): вызывается из tools/offer_sheet.mjs при сборке и руками для листов без sheet.json:
//   node tools/offer_watermark.mjs cg-capital
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const CSS = `/* WM-PLP: водяной знак PL (15.10.2026) */
.photo::after,.pol::after,.pdfcover::after{content:"";position:absolute;inset:0;z-index:4;pointer-events:none;background:url(../../img/brand/plp-wm.svg) center/46mm auto;opacity:.16}
.pol::after{inset:2mm 2mm 8mm}
.w::after{content:"";position:absolute;inset:0;z-index:9;pointer-events:none;background:url(../../img/brand/plp-wm.svg) 0 0/90mm auto;opacity:.07}
.wmfoot{text-align:center;font-size:8pt;letter-spacing:.04em;color:var(--muted);padding:5mm 0 6mm}
`;
export const FOOT = '<div class="wmfoot">Property Library Phuket · property-library.com</div>';

export function applyWatermark(html) {
  if (html.includes('WM-PLP')) return html;
  let h = html.replace('</style>', CSS + '</style>');
  h = h.replace(/<\/footer>(\s*<\/div>)/, '</footer>\n' + FOOT + '$1');
  if (!h.includes('class="wmfoot"')) throw new Error('не нашёл место для подвала (</footer> и закрытие .w)');
  return h;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  for (const slug of process.argv.slice(2)) {
    const f = path.join(ROOT, 'offers', slug, 'page.htm');
    const a = fs.readFileSync(f, 'utf8'), b = applyWatermark(a);
    if (a !== b) fs.writeFileSync(f, b);
    console.log(slug, a !== b ? 'знак добавлен' : 'уже есть');
  }
}
