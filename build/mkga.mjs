// 05.10.2026 Эльнур «да»: Google Analytics 4 (ресурс property-library.com, поток «Сайт PLP»).
// Вставляет тег GA на каждую страницу сайта перед </head>, один раз (по метке PLP:GA). Идёт последним шагом сборки.
import fs from 'fs';
import path from 'path';
const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const ID = 'G-HQNDG3B8MW';
const TAG = `<!-- PLP:GA --><script async src="https://www.googletagmanager.com/gtag/js?id=${ID}"></script>`
  + `<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${ID}');</script>`;
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
    if (s.includes('PLP:GA')) continue;
    fs.writeFileSync(p, s.replace('</head>', TAG + '</head>'));
    n++;
  }
})(ROOT);
console.log('GA: добавлено на', n, 'страниц, всего страниц с <head>:', all);
