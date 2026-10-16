// 16.10.2026 Эльнур «го», «чини сразу» (разбор ~/plp-ops/разборы/seo_1610/решения.md п.5).
// 1) Пиксель Meta 1387930368853540 на всех страницах, только PageView (раньше стоял лишь на квизе).
//    Не ставим в кабинет владельца, админку и гостевую: там клиенты и их данные. Квиз уже несёт свой пиксель с Lead.
// 2) Свой счётчик site_events: один код, тот, что на главной между метками PLP:COUNTER. Здесь он
//    сверяется на всех страницах, где уже есть, и добавляется на страницы объектов (116 карточек его не имели).
//    Страницы на js/track.js (квиз) не трогаем: там свой счётчик с id посетителя.
// Тестовые заходы (localhost, файл, headless-проверки) ни пиксель, ни счётчик не шлют.
// Идёт после mkga в build/all.mjs. Повторный прогон ничего не меняет.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const TEST = "location.protocol==='file:'||/^(localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0|\\[::1\\])$/.test(location.hostname)||navigator.webdriver";
const OLD_PIXEL = '<!-- PLP:PIXEL --><script>(function(){if(' + TEST + ')return;'
  + "!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');"
  + "fbq('init','1387930368853540');fbq('track','PageView');})();</script>";
/* 16.10.2026 (PDPA, «доработай!»): пиксель грузит только /js/consent.js после «Принять» на плашке согласия
   (consent.js подключает тег PLP:GA из mkga.mjs, он идёт раньше). Здесь страница лишь объявляет номер пикселя. */
const PIXEL = "<!-- PLP:PIXEL --><script>window.PLP_PIXEL='1387930368853540';</script>";

const C0 = '<!-- PLP:COUNTER:START', C1 = '<!-- PLP:COUNTER:END -->';
const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const i0 = idx.indexOf(C0), i1 = idx.indexOf(C1);
if (i0 < 0 || i1 < i0) throw new Error('mktrack: на главной нет меток PLP:COUNTER — источник счётчика потерян');
const COUNTER = idx.slice(i0, i1 + C1.length);

const SKIP_DIR = new Set(['node_modules', '.git', 'build', 'tools', 'n8n', 'scripts', '.check']);
const NO_PIXEL = new Set(['owner.html', 'admin.html', 'guest.html']);
const st = { pixel: 0, pixelHad: 0, cntAdd: 0, cntSync: 0, cntOld: 0, pages: 0 };

(function walk(d) {
  for (const f of fs.readdirSync(d, { withFileTypes: true })) {
    if (f.name.startsWith('.') || SKIP_DIR.has(f.name)) continue;
    const p = path.join(d, f.name);
    if (f.isDirectory()) { walk(p); continue; }
    if (!/\.html?$/.test(f.name) || NO_PIXEL.has(f.name)) continue;
    let s = fs.readFileSync(p, 'utf8');
    if (!s.includes('</head>')) continue;
    st.pages++;
    const b = s;
    const rel = path.relative(ROOT, p);

    if (s.includes(OLD_PIXEL)) { s = s.split(OLD_PIXEL).join(PIXEL); st.pixel++; }
    else if (s.includes(PIXEL)) st.pixelHad++;
    else if (s.includes('PLP:PIXEL')) throw new Error('mktrack: метка PLP:PIXEL есть, но код не узнан: ' + rel);
    else { s = s.replace('</head>', PIXEL + '</head>'); st.pixel++; }
    /* пиксель грузит только consent.js: fbevents.js прямо на странице = обход согласия */
    if (s.includes('fbevents.js')) throw new Error('mktrack: пиксель Meta грузится мимо согласия: ' + rel);
    if (!s.includes('/js/consent.js')) throw new Error('mktrack: на странице с пикселем нет /js/consent.js: ' + rel);

    if (p !== path.join(ROOT, 'index.html') && !s.includes('/js/track.js')) {
      const a0 = s.indexOf(C0), a1 = s.indexOf(C1);
      const k = s.indexOf('/* Обезличенная аналитика');
      if (a0 >= 0 && a1 > a0) {
        const cur = s.slice(a0, a1 + C1.length);
        if (cur !== COUNTER) { s = s.slice(0, a0) + COUNTER + s.slice(a1 + C1.length); st.cntSync++; }
      } else if (k >= 0) {
        /* старая копия без меток (страницы, собранные до 16.10): меняем на общий код */
        const s0 = s.lastIndexOf('<script>', k), s1 = s.indexOf('</script>', k);
        if (s0 < 0 || s1 < 0 || s.slice(s0 + 8, k).trim() !== '') throw new Error('mktrack: не разобрал старый счётчик на ' + rel);
        s = s.slice(0, s0) + COUNTER + s.slice(s1 + '</script>'.length); st.cntOld++;
      } else if (rel.startsWith('object' + path.sep) && !s.includes('siteevents')) {
        const e = s.lastIndexOf('</body>');
        if (e < 0) throw new Error('mktrack: нет </body> на ' + rel);
        s = s.slice(0, e) + COUNTER + '\n' + s.slice(e); st.cntAdd++;
      }
    }
    if (s !== b) fs.writeFileSync(p, s);
  }
})(ROOT);
console.log(`пиксель Meta (через согласие): обновлён на ${st.pixel}, уже был на ${st.pixelHad} из ${st.pages}; ` +
  `счётчик: добавлен ${st.cntAdd}, сверен ${st.cntSync}, старых копий заменено ${st.cntOld}`);
