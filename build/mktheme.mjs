/* Цвет системных полей браузера на КАЖДОЙ странице.
   Эльнур 06.09: «причина мигания не в оттягивании, найди и исправь в целом везде».
   Мигание давал theme-color: он был жёстко тёмный на главной и отсутствовал на
   остальных — браузер красил свою полосу и фон под страницей чужим цветом.
   Здесь один источник: build/parts/head-theme.html разносится по всем страницам,
   плюс каждой гарантируется фон на <html>, иначе при оттягивании светит белое. */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const PART = fs.readFileSync(path.join(ROOT, 'build/parts/head-theme.html'), 'utf8').trim();
const OPEN = '<!-- PLP:HEADTHEME:START -->', CLOSE = '<!-- PLP:HEADTHEME:END -->';
const HTMLBG = 'html{background:var(--bg);overscroll-behavior-y:none}';
const ANTIFLICK = fs.readFileSync(path.join(ROOT, 'build/parts/anti-flicker.css'), 'utf8').trim();
const AF_MARK = '/* PLP:ANTIFLICKER */';
/* у печатных страниц своих токенов нет — берём фон прямо из body */
const plainBg = html => {
  const m = html.match(/body\s*\{[^}]*?background:\s*([^;}]+)/s);
  return m ? m[1].trim() : null;
};

const skip = new Set(['node_modules', '.git', 'build']);
function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (skip.has(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

let fixed = 0, bg = 0;
for (const file of walk(ROOT)) {
  let html = fs.readFileSync(file, 'utf8');
  const before = html;

  /* старые статичные значения убираем — иначе спорят с общим блоком */
  html = html.replace(/\n?<meta name="theme-color"(?![^>]*media)[^>]*>/g, '')
             .replace(/\n?<meta name="apple-mobile-web-app-status-bar-style"[^>]*>/g, '');

  const i = html.indexOf(OPEN), j = html.indexOf(CLOSE);
  if (i !== -1 && j !== -1 && j > i) {
    html = html.slice(0, i + OPEN.length) + '\n' + PART + '\n' + html.slice(j);
  } else {
    const m = html.match(/<meta name="viewport"[^>]*>/) || html.match(/<head[^>]*>/);
    if (!m) continue;
    const at = html.indexOf(m[0]) + m[0].length;
    html = html.slice(0, at) + '\n' + OPEN + '\n' + PART + '\n' + CLOSE + html.slice(at);
  }

  /* фон на самом <html>: без него оттягивание показывает чужой цвет */
  /* прежние вставки убираем — иначе после смены палитры копятся дубли */
  html = html.replace(/\nhtml\{background:[^}]*overscroll-behavior-y:none\}/g, '');
  const rule = html.includes('--bg:') ? HTMLBG
    : (plainBg(html) ? `html{background:${plainBg(html)};overscroll-behavior-y:none}` : null);
  if (rule && !html.includes(rule)) {
    const s = html.indexOf('<style');
    if (s !== -1) {
      const at = html.indexOf('>', s) + 1;
      html = html.slice(0, at) + '\n' + rule + html.slice(at);
      bg++;
    }
  }

  /* Защита от мигания — тем же одним источником на все страницы.
     Кладём в НАЧАЛО первого <style>: закрывающий тег искать нельзя, он
     встречается внутри JS-строк (печатная форма отчёта в кабинете) — вставка
     туда ломала скрипт целиком. Правила внутри помечены !important, поэтому
     от места в файле не зависят. */
  const afStart = html.indexOf(AF_MARK);
  if (afStart !== -1) {
    const afEnd = html.indexOf(AF_MARK, afStart + AF_MARK.length);
    if (afEnd !== -1) html = html.slice(0, afStart) + AF_MARK + '\n' + ANTIFLICK + '\n' + html.slice(afEnd);
  } else {
    const s0 = html.indexOf('<style');
    if (s0 !== -1) {
      const at = html.indexOf('>', s0) + 1;
      html = html.slice(0, at) + '\n' + AF_MARK + '\n' + ANTIFLICK + '\n' + AF_MARK + html.slice(at);
    }
  }
  if (html !== before) { fs.writeFileSync(file, html); fixed++; }
}
console.log(`страниц с общим блоком темы: ${fixed}, добавлен фон html: ${bg}`);
