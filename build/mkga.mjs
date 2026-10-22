// 05.10.2026 Эльнур «да»: Google Analytics 4 (ресурс property-library.com, поток «Сайт PLP»).
// 16.10.2026 Эльнур «доработай!» (PDPA): gtag.js больше не грузится сразу. Страница только объявляет PLP_GA и режим
// согласия Google «всё запрещено», а грузит GA /js/consent.js после «Принять» на плашке согласия.
// Метка PLP:GA ставится на каждую страницу (кроме кабинета владельца) один раз; старый тег (до 16.10) заменяется.
import fs from 'fs';
import path from 'path';
const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const ID = 'G-HQNDG3B8MW';
const OLD = `<!-- PLP:GA --><script async src="https://www.googletagmanager.com/gtag/js?id=${ID}"></script>`
  + `<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${ID}');</script>`;
const TAG = `<!-- PLP:GA --><script>window.PLP_GA='${ID}';window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}`
  + `gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied'});</script>`
  + `<script src="/js/consent.js" defer></script>`;
const SKIP = new Set(['node_modules', '.git', 'build', 'tools', 'n8n', 'scripts']);
let n = 0, all = 0;
(function walk(d) {
  for (const f of fs.readdirSync(d, { withFileTypes: true })) {
    if (f.name.startsWith('.') || SKIP.has(f.name)) continue;
    const p = path.join(d, f.name);
    if (f.isDirectory()) { walk(p); continue; }
    if (!/\.html?$/.test(f.name) || f.name === 'owner.html') continue;  // кабинет владельца не считаем
    const s = fs.readFileSync(p, 'utf8');
    if (!s.includes('</head>')) continue;
    all++;
    let t = s;
    if (t.includes(TAG)) { /* уже новый */ }
    else if (t.includes(OLD)) t = t.split(OLD).join(TAG);
    else if (t.includes('PLP:GA')) throw new Error('mkga: метка PLP:GA есть, но тег не узнан: ' + path.relative(ROOT, p));
    else t = t.replace('</head>', TAG + '</head>');
    /* GA грузит только consent.js: прямой gtag.js на странице = обход согласия */
    if (t.includes('googletagmanager.com/gtag/js')) throw new Error('mkga: прямая загрузка gtag.js мимо согласия: ' + path.relative(ROOT, p));
    if (t !== s) { fs.writeFileSync(p, t); n++; }
  }
})(ROOT);
console.log('GA (через согласие): обновлено', n, 'страниц, всего страниц с <head>:', all);
/* 22.10.2026 claude-инвентаризация: исходники листов offers/<slug>/sheet.json хранили старый тег (до 16.10), и каждая пересборка листа
   возвращала в page.htm загрузку gtag.js мимо согласия. Чиним сам исходник, чтобы пересборка давала тег с согласием. */
let ns = 0;
const OFF = path.join(ROOT, 'offers');
for (const d of fs.existsSync(OFF) ? fs.readdirSync(OFF) : []) {
  const p = path.join(OFF, d, 'sheet.json');
  if (!fs.existsSync(p)) continue;
  const s = fs.readFileSync(p, 'utf8');
  const oe = JSON.stringify(OLD).slice(1, -1), te = JSON.stringify(TAG).slice(1, -1);   // как строка лежит внутри JSON
  const t = s.includes(oe) ? s.split(oe).join(te) : s;   // заменяем текстом, разметку файла не трогаем
  JSON.parse(t);
  if (t !== s) { fs.writeFileSync(p, t); ns++; }
  if (t.includes('googletagmanager.com/gtag/js')) throw new Error('mkga: в исходнике листа прямая загрузка gtag.js: ' + path.relative(ROOT, p));
}
console.log('GA в исходниках листов: исправлено', ns);
