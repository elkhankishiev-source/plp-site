#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обход каждой кнопки страницы: что живое, что не отвечает.

Ручной осмотр это не ловит. Здесь страница поднимается в headless-браузере,
сеть подменяется заглушкой, и по каждому кликабельному элементу делается клик.
Кнопка считается мёртвой, если после клика НИЧЕГО не изменилось: ни разметка,
ни открытые панели, ни счётчик сетевых вызовов, ни локальная подпись самого
элемента и его четырёх предков. Локальная часть обязательна: без неё клик по
соседнему пункту меню закрывает предыдущее и выглядит как «живой».

Запуск:
    python3 tools/tapaudit.py owner.html      # кабинет (демо-сессия)
    python3 tools/tapaudit.py index.html      # витрина
    python3 tools/tapaudit.py index.html --json отчёт.json
"""
import http.server, json, os, re, socketserver, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PORT = 8907

INJECT = r"""
<script>
/* сеть наружу не пускаем: считаем вызовы и отдаём правдоподобную заглушку */
window.__net = 0;
(function () {
  var real = window.fetch;
  window.fetch = function (u, o) {
    window.__net++;
    var body = { ok: true, rows: [], items: [], files: [], properties: [], data: {}, reply: 'ок' };
    return Promise.resolve(new Response(JSON.stringify(body),
      { status: 200, headers: { 'Content-Type': 'application/json' } }));
  };
  var xo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function () { window.__net++; return xo.apply(this, arguments); };
})();
try { localStorage.setItem('plp_owner_session', 'demo'); } catch (e) {}
/* Кабинет без данных показывает только экран входа, и обходить там нечего.
   Если рядом лежит снимок данных демо-владельца, поднимаем на нём весь
   кабинет: тогда обход видит разделы, таблицы и кнопки действий. */
window.__demoBoot = function () {
  if (!window.__cabDemo) return false;
  var x = new XMLHttpRequest();
  try {
    x.open('GET', '/.demo_data.json', false); x.send(null);
    if (x.status === 200) { window.__cabDemo(JSON.parse(x.responseText)); return true; }
  } catch (e) {}
  return false;
};
window.__errors = [];
window.addEventListener('error', function (e) { window.__errors.push(String(e.message).slice(0, 120)); });
</script>
"""

WALK = r"""
(function () {
  try { if (window.__demoBoot) window.__demoBoot(); } catch (e) {}
  /* Ограничение: обработчики, которые вешаются в момент отрисовки раздела,
     проверяются только для открытого раздела. Прощёлкивание всех вкладок разом
     ломает отрисовку на середине, поэтому разделы гоняем отдельными прогонами. */
  var SEL = 'button, .opt, .lnk, [data-a], [data-uk], .msub-h, .foldh, .chipf, .fbtn, .qz-opt, .tab, .cab-nav a';
  function hash(str) {
    var h = 5381, i = str.length;
    while (i) { h = (h * 33) ^ str.charCodeAt(--i); }
    return (h >>> 0).toString(36);
  }
  /* Длины разметки мало: у карусели и кнопки «сравнить» меняются только классы
     и атрибуты, длина остаётся та же. Берём отпечаток самого ближнего блока
     целиком, вместе с классами и data-атрибутами. */
  function sig(el) {
    var s = [], n = el;
    for (var i = 0; i < 5 && n; i++) {
      s.push(n.className || '', n.hidden ? 'h' : '', n.getAttribute && (n.getAttribute('aria-pressed') || ''));
      n = n.parentElement;
    }
    var box = el.closest('.prop, .card, .modal, .panel, .fmenu, section, main') || el.parentElement;
    s.push(box ? hash(box.outerHTML) : '0');
    /* Значения полей живут в свойстве value, а не в разметке: чипы «бассейн»,
       «тихий час с 22:00» подставляют текст в input и внешне ничего не меняют.
       Без этого они выглядели мёртвыми, а на деле работают. */
    if (box) {
      var vals = [];
      Array.prototype.forEach.call(box.querySelectorAll('input, textarea, select'), function (f) {
        vals.push(f.value || '', f.checked ? '1' : '0');
      });
      s.push(hash(vals.join('\u0001')));
    }
    /* Часть кнопок отвечает не в своей карточке, а глобально: полоса избранного,
       открытая модалка, тема. Без них честные нажатия выглядят мёртвыми. */
    var tray = document.getElementById('tray');
    var modal = document.querySelector('.modal.open, .open.modal, dialog[open]');
    s.push(tray ? hash(tray.outerHTML) : '0');
    s.push(modal ? hash(modal.className + String(modal.innerHTML.length)) : '0');
    s.push(hash(document.body.className + '|' + (document.documentElement.getAttribute('data-theme') || '')));
    s.push(String(window.scrollY | 0));
    return s.join('|');
  }
  function snap() {
    return { len: document.body.innerHTML.length,
             open: document.querySelectorAll('.open, .on, [hidden]').length,
             net: window.__net || 0 };
  }
  var out = [];
  var FROM = __FROM__, TO = __TO__;
  function pass() {
    var els = Array.prototype.slice.call(document.querySelectorAll(SEL));
    out.push({ __total: els.length });
    els.forEach(function (el, i) {
      if (i < FROM || i >= TO) return;
      if (!el || el.disabled) return;
      var label = (el.textContent || el.getAttribute('aria-label') || el.className || '').replace(/\s+/g, ' ').trim().slice(0, 46);
      var key = i;
      if (el.tagName === 'A' && el.getAttribute('href') && el.getAttribute('href').indexOf('#') !== 0) {
        out.push({ label: label, kind: 'ссылка', ok: true, note: el.getAttribute('href').slice(0, 60) }); return;
      }
      var b1 = snap(), s1 = sig(el);
      try { el.click(); } catch (e) { out.push({ label: label, ok: false, note: 'ошибка клика: ' + e.message.slice(0, 60) }); return; }
      var b2 = snap(), s2 = sig(el);
      var moved = (b1.len !== b2.len) || (b1.open !== b2.open) || (b1.net !== b2.net) || (s1 !== s2);
      out.push({ label: label, kind: el.tagName.toLowerCase(), ok: moved, note: moved ? '' : 'реакции нет' });
    });
  }
  pass();
  var box = document.createElement('pre'); box.id = '__audit';
  box.textContent = JSON.stringify({ items: out, errors: window.__errors || [] });
  document.body.appendChild(box);
})();
"""


def serve():
    os.chdir(ROOT)
    h = http.server.SimpleHTTPRequestHandler
    class Quiet(h):
        def log_message(self, *a): pass
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(page, frm=0, to=100000):
    src = os.path.join(ROOT, page)
    html = open(src, encoding='utf-8').read()
    i = html.lower().find('<head>')
    if i < 0:
        sys.exit('нет <head> в ' + page)
    patched = html[:i + 6] + INJECT + html[i + 6:]
    # клик-обход добавляем в конец страницы, после всех скриптов
    walk = WALK.replace('__FROM__', str(frm)).replace('__TO__', str(to))
    # 🔴 09.09: подставляли скрипт в ПЕРВОЕ «</body>», а в кабинете такой тег
    # есть внутри JS-строки (печатная форма). Скрипт ломался, страница падала
    # с SyntaxError, и обход показывал полсотни «мёртвых» кнопок, которых нет.
    # Вставляем в последнее вхождение.
    tail = '<script>setTimeout(function(){' + walk + '}, 2200);</script></body>'
    k = patched.rfind('</body>')
    patched = patched[:k] + tail + patched[k + 7:]
    tmp = os.path.join(ROOT, '.audit_tmp.html')
    open(tmp, 'w', encoding='utf-8').write(patched)
    try:
        r = subprocess.run([CHROME, '--headless', '--disable-gpu', '--no-sandbox',
                            '--virtual-time-budget=15000', '--dump-dom',
                            'http://127.0.0.1:%d/.audit_tmp.html' % PORT],
                           capture_output=True, text=True, timeout=180)
        m = re.search(r'<pre id="__audit">(.*?)</pre>', r.stdout, re.S)
        if not m:
            return None, 'обход не отработал (страница не дошла до конца)'
        raw = m.group(1)
        raw = raw.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return json.loads(raw), None
    finally:
        try: os.remove(tmp)
        except OSError: pass


def main():
    page = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    step = 25
    srv = serve()
    items, errors, total = [], [], None
    try:
        # первый проход узнаёт, сколько всего элементов
        data, err = run(page, 0, step)
        if err:
            print('✗', err); sys.exit(1)
        total = next((x['__total'] for x in data['items'] if '__total' in x), 0)
        items += [x for x in data['items'] if '__total' not in x]
        errors += data.get('errors', [])
        frm = step
        while frm < total:
            data, err = run(page, frm, frm + step)
            if not err:
                items += [x for x in data['items'] if '__total' not in x]
                errors += data.get('errors', [])
            frm += step
            print('    ... %d из %d' % (min(frm, total), total), end='\r', flush=True)
    finally:
        srv.shutdown()
    print(' ' * 40, end='\r')
    dead = [x for x in items if not x.get('ok')]
    links = [x for x in items if x.get('kind') == 'ссылка']
    print('%s: кликабельных элементов %d, проверено %d' % (page, total, len(items)))
    print('  ссылки (переход, не клик): %d' % len(links))
    print('  ответили на нажатие: %d' % (len(items) - len(links) - len(dead)))
    print('  БЕЗ РЕАКЦИИ: %d' % len(dead))
    from collections import Counter
    cnt = Counter((d['label'], d.get('note', '')) for d in dead)
    for (label, note), n in cnt.most_common():
        print('    ✗ %-46s %s%s' % (label, note, (' ×%d' % n) if n > 1 else ''))
    if errors:
        print('  ошибки страницы: %d' % len(errors))
        for e in list(dict.fromkeys(errors))[:6]:
            print('    !', e)
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump({'items': items, 'errors': errors}, open(out, 'w'), ensure_ascii=False, indent=1)
        print('  отчёт:', out)


if __name__ == '__main__':
    main()
