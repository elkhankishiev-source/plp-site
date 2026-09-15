#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка кабинета на РЕАЛЬНЫХ данных — без входа по коду.

Эльнур 15.09.2026: «разделы пустые, куда всё исчезло» и «хочу, чтобы у тебя
был полный доступ к моему кабинету». Данные берём ключом штаба прямо с сервера,
страницу кабинета поднимаем локально в headless-Chrome и смотрим, что рисуется.

Что проверяет (компьютер 1400px и телефон 390px):
  • все шаги отрисовки кабинета прошли без ошибок (window.__cabSteps);
  • при входе разделы свёрнуты, приветствие стоит отдельно;
  • объект не выбран → разделы объекта просят выбрать, а не показывают первый;
  • объект выбран → каждый раздел объекта не пустой, шапка и обзор говорят о нём.

Запуск:
    python3 tools/cab_check.py                 # отчёт
    python3 tools/cab_check.py --short         # одна строка итога (для сборки)
    python3 tools/cab_check.py --shots         # + скриншоты разделов в /tmp/plp_cab_shots
    python3 tools/cab_check.py --as-client PLP-001555   # кабинет глазами клиента

Данные НЕ пишутся в репозиторий (он публичный): страница и ответ сервера
отдаются из памяти локального сервера.
"""
import http.server, json, os, re, socketserver, subprocess, sys, threading, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
API = 'https://api.property-library.com/ukowner'
PORT = 8793
SHOTS = '/tmp/plp_cab_shots'
OBJ_TABS = ['calendar', 'money', 'costs', 'docs', 'service', 'object']
TAB_RU = {'overview': 'Обзор', 'calendar': 'Бронирования', 'money': 'Финансы',
          'costs': 'Расходы', 'docs': 'Документы', 'service': 'Обслуживание', 'object': 'Объект'}


def token():
    t = os.environ.get('PLP_STAFF_TOKEN')
    f = os.path.expanduser('~/.plp_staff_token')
    if not t and os.path.exists(f):
        t = open(f).read().strip()
    return t


def fetch_data(tok, as_client=None, as_owner=None):
    body = {'action': 'data', 'token': tok}
    if as_client: body['as_client'] = as_client
    if as_owner: body['as_owner'] = as_owner
    r = urllib.request.Request(API, data=json.dumps(body).encode(),
                               headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(r, timeout=90).read())


STUB = r"""<script>
/* сеть кабинета подменена: данные — снимок с сервера, действия — пустой успех */
(function(){
  var real = window.fetch;
  window.__DATA = null;
  window.fetch = function(u, o){
    var url = String(u||'');
    if (/api\.property-library\.com|hub\.property-library\.com/.test(url)) {
      var b = {}; try { b = JSON.parse((o&&o.body)||'{}'); } catch(e){}
      var body = (b.action==='data') ? window.__DATA : {ok:true, rows:[], items:[]};
      return Promise.resolve(new Response(JSON.stringify(body), {status:200, headers:{'Content-Type':'application/json'}}));
    }
    return real.apply(this, arguments);
  };
  var x = new XMLHttpRequest(); x.open('GET', '/__data.json', false); x.send(null);
  window.__DATA = JSON.parse(x.responseText);
  window.__errs = [];
  window.addEventListener('error', function(e){ window.__errs.push(String(e.message).slice(0,140)); });
  try {
    localStorage.clear();
    var q = new URLSearchParams(location.search);
    if (q.get('pid')) localStorage.setItem('plp_owner_sel', JSON.stringify([q.get('pid')]));
    if (q.get('theme')) localStorage.setItem('plp_theme', q.get('theme'));
  } catch(e){}
})();
</script>"""

PROBE = r"""<script>
setTimeout(function(){
  var q = new URLSearchParams(location.search), out = {steps:[], errs:[], checks:[]};
  function ok(name, cond, note){ out.checks.push({name:name, ok:!!cond, note:note||''}); }
  function vis(el){ return !!el && el.style.display!=='none' && !el.hidden && el.getClientRects().length>0; }
  function txt(el){ return el ? (el.innerText||'').replace(/\s+/g,' ').trim() : ''; }
  try { window.__cabDemo(window.__DATA); } catch(e){ out.errs.push('boot: '+e.message); }
  setTimeout(function(){
    out.steps = (window.__cabSteps||[]).filter(function(s){ return !/:ok$/.test(s); });
    var body = document.getElementById('cab-body'), nav = document.getElementById('cab-nav');
    var hello = document.getElementById('cab-hello');
    ok('при входе разделы свёрнуты', body && body.hidden && !nav.querySelector('a.on'));
    ok('приветствие видно отдельно', hello && txt(hello).length > 5 && !body.contains(hello));
    /* ширина: на телефоне кабинет не должен уезжать за экран — ни свёрнутый, ни в раскрытом разделе */
    function widthOk(where){
      var sw = document.documentElement.scrollWidth, vw = window.innerWidth, wide = [];
      if (sw > vw + 1) {
        Array.prototype.forEach.call(document.querySelectorAll('#app *'), function(el){
          var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
          if (r.right > vw + 1 && r.width > 0 && el.children.length < 8 && cs.position !== 'fixed')
            wide.push((el.id?'#'+el.id:'')+'.'+String(el.className||el.tagName).split(' ')[0]+'→'+Math.round(r.right));
        });
      }
      ok('не шире экрана: '+where, sw <= vw + 1, 'ширина '+sw+' при экране '+vw+': '+wide.slice(0,6).join(', '));
    }
    widthOk('вход');
    /* 15.09 Эльнур: разделов кабинета в бургере быть не должно */
    try { toggleNav(true); } catch(e){}
    var mn = document.getElementById('mnav'), labels = Array.prototype.map.call(nav.querySelectorAll('a[data-tab]'), function(a){ return txt(a); });
    var dup = mn ? Array.prototype.filter.call(mn.querySelectorAll('a,button'), function(b){ return labels.indexOf(txt(b)) >= 0; }).map(txt) : [];
    ok('в бургере нет разделов кабинета', !dup.length, dup.join(', '));
    try { toggleNav(false); } catch(e){}
    var tab = q.get('tab');
    function open(t){ var a = nav.querySelector('a[data-tab="'+t+'"]'); if(a){ a.click(); } return a; }
    if (q.get('mode') === 'shot') {
      if (tab) { open(tab); var b2=document.getElementById('cab-body'); if(b2) b2.scrollIntoView({block:'start'}); window.scrollBy(0,-120); }
      return;
    }
    var pid = q.get('pid'), all = (window.__DATA.properties||[]);
    var ask = document.getElementById('sel-ask');
    if (!pid) {
      OBJ_TABS.forEach(function(t){
        if(!open(t)) return;
        var others = Array.prototype.filter.call(body.children, function(el){ return el.id!=='sel-ask' && el.id!=='demo-note' && vis(el) && txt(el).length; });
        ok('не выбран → «'+t+'» просит выбрать объект', vis(ask) && !others.length, others.map(function(e){return e.id;}).join(','));
        widthOk(t);
      });
      ok('обзор не называет первый объект', /не выбран/i.test(txt(document.querySelector('#portfolio .ov-obj'))));
    } else {
      var p = all.filter(function(x){ return String(x.id)===pid; })[0] || {};
      var name = p.name || p.id || '';
      ok('шапка показывает выбранный объект', txt(document.getElementById('ctx-obj')).indexOf(name) >= 0, txt(document.getElementById('ctx-obj')));
      ok('обзор про выбранный объект', txt(document.querySelector('#portfolio .ov-obj')).indexOf(name) >= 0);
      open('overview'); widthOk('overview');
      /* каждое сворачиваемое окно внутри раздела тоже раскрываем — ширина ломается чаще всего там */
      Array.prototype.forEach.call(document.querySelectorAll('#cab-body .foldh, #cab-body .msub-h'), function(h){ try{ h.click(); }catch(e){} });
      widthOk('overview, окна раскрыты');
      OBJ_TABS.forEach(function(t){
        if(!open(t)) return;
        var shown = Array.prototype.filter.call(body.children, function(el){ return el.id!=='sel-ask' && el.id!=='demo-note' && vis(el); });
        var len = shown.reduce(function(n,el){ return n + txt(el).length; }, 0);
        ok('выбран → «'+t+'» не пустой', len > 15 && !vis(ask), 'символов: '+len);
        widthOk(t);
      });
    }
    out.errs = out.errs.concat(window.__errs||[]);
    var pre = document.createElement('pre'); pre.id='__cab'; pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }, 1800);
}, 600);
var OBJ_TABS = __OBJ_TABS__;
</script>"""


# 🔴 headless-Chrome не делает окно уже 500px: --window-size=390 молча даёт 500 и лишь
# обрезает скриншот. Телефон проверяем в рамке ровно нужной ширины внутри окна.
WRAP = r"""<!doctype html><html><body style="margin:0;background:#777">
<iframe id="f" src="__SRC__" style="width:__W__px;height:__H__px;border:0;display:block"></iframe>
<script>
var t=setInterval(function(){try{var d=document.getElementById('f').contentDocument;
var p=d&&d.getElementById('__cab');if(p){var q=document.createElement('pre');q.id='__cab';
q.textContent=p.textContent;document.body.appendChild(q);clearInterval(t);}}catch(e){}},250);
</script></body></html>"""


def page_url(width, height, qs):
    inner = 'http://127.0.0.1:%d/__cab.html?%s' % (PORT, qs)
    if width >= 500:
        return inner, width, height
    from urllib.parse import quote
    return ('http://127.0.0.1:%d/__wrap.html?w=%d&h=%d&src=%s' % (PORT, width, height, quote(inner, safe=''))), 520, height


def build_page():
    html = open(os.path.join(ROOT, 'owner.html'), encoding='utf-8').read()
    i = html.lower().find('<head>') + 6
    html = html[:i] + STUB + html[i:]
    k = html.rfind('</body>')          # в кабинете первое </body> живёт внутри JS-строки
    probe = PROBE.replace('__OBJ_TABS__', json.dumps(OBJ_TABS))
    return html[:k] + probe + html[k:]


def serve(page, data):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw): super().__init__(*a, directory=ROOT, **kw)
        def log_message(self, *a): pass
        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/__wrap.html':
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                raw = (WRAP.replace('__SRC__', q['src'][0]).replace('__W__', q['w'][0])
                           .replace('__H__', q['h'][0])).encode('utf-8')
                self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            if path in ('/__cab.html', '/__data.json'):
                raw = (page if path == '/__cab.html' else json.dumps(data, ensure_ascii=False)).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if path.endswith('.html') else 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            return super().do_GET()
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def chrome(url, width, height, shot=None):
    args = [CHROME, '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
            '--window-size=%d,%d' % (width, height), '--virtual-time-budget=12000']
    args += (['--screenshot=' + shot] if shot else ['--dump-dom'])
    return subprocess.run(args + [url], capture_output=True, text=True, timeout=180).stdout


def richest(data):
    best, score = None, -1
    props = [p for p in (data.get('properties') or []) if not p.get('brief')]
    real = [p for p in props if 'DEMO' not in str(p.get('id', ''))]
    for p in (real or props):
        s = sum(len(p.get(k) or []) for k in ('bookings', 'transactions', 'statements', 'docs', 'tasks_all', 'months'))
        if s > score: best, score = p, s
    return best


def main():
    short = '--short' in sys.argv
    tok = token()
    if not tok:
        print('[кабинет] пропущено: нет ключа штаба (~/.plp_staff_token)'); return 0
    as_client = sys.argv[sys.argv.index('--as-client') + 1] if '--as-client' in sys.argv else None
    try:
        data = fetch_data(tok, as_client=as_client)
    except Exception as e:
        print('[кабинет] сервер не ответил:', str(e)[:120]); return 0 if short else 1
    if not data.get('ok'):
        print('[кабинет] сервер отказал:', data.get('error')); return 1
    props = data.get('properties') or []
    best = richest(data)
    srv = serve(build_page(), data)
    fails, lines = [], []
    try:
        scenarios = [('объект не выбран', '')] if len(props) > 1 else []
        if best: scenarios.append(('выбран «%s»' % (best.get('name') or best.get('id')), best['id']))
        for width, label in ((1400, 'компьютер'), (390, 'телефон')):
            for title, pid in scenarios:
                url, ww, hh = page_url(width, 900, 'pid=%s' % pid)
                dom = chrome(url, ww, hh)
                m = re.search(r'<pre id="__cab">(.*?)</pre>', dom, re.S)
                if not m:
                    fails.append('%s · %s: кабинет не дорисовался' % (label, title)); continue
                res = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))
                for s in res['steps']: fails.append('%s · %s: блок упал — %s' % (label, title, s))
                for e in res['errs'][:3]: fails.append('%s · %s: ошибка страницы — %s' % (label, title, e))
                for c in res['checks']:
                    mark = '✓' if c['ok'] else '✗'
                    lines.append('  %s %-9s %-28s %s %s' % (mark, label, title[:28], c['name'], ('(' + c['note'] + ')') if (c['note'] and not c['ok']) else ''))
                    if not c['ok']: fails.append('%s · %s: %s %s' % (label, title, c['name'], c['note']))
        if '--shots' in sys.argv and best:
            os.makedirs(SHOTS, exist_ok=True)
            for width, label in ((1400, 'mac'), (390, 'phone')):
                for t in ['overview'] + OBJ_TABS:
                    path = os.path.join(SHOTS, '%s-%s.png' % (label, t))
                    url, ww, hh = page_url(width, 1400 if width > 900 else 1700,
                                           'pid=%s&mode=shot&tab=%s' % (best['id'], t))
                    chrome(url, ww, hh, shot=path)
                    if width < 500:   # рамка лежит слева — отрезаем серое поле справа (sips режет по центру)
                        try:
                            from PIL import Image
                            im = Image.open(path); im.crop((0, 0, width, im.size[1])).save(path)
                        except Exception:
                            pass
            lines.append('  скриншоты: ' + SHOTS)
    finally:
        srv.shutdown()
    if short:
        print('[кабинет] %s: объектов %d, проверок %d, сломано %d%s' % (
            'ок' if not fails else 'ЕСТЬ ПОЛОМКИ', len(props), len(lines), len(fails),
            ('' if not fails else ' — ' + fails[0][:140])))
    else:
        print('Кабинет на реальных данных: объектов %d, пример — %s' % (len(props), best and best.get('id')))
        print('\n'.join(lines))
        print('итог: сломано %d' % len(fails))
        for f in fails[:20]: print('  !', f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
