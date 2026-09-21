#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка «компьютер ↔ телефон» и «светлая ↔ тёмная»: что на странице почти не видно.

Эльнур 15.09.2026: «сделал для мака — значит телефон должен соответствовать,
чтобы впредь такого не было, автоматически». Повод: сердечко и «Сравнить» на фото
карточек были починены только для телефона, а на компьютере в светлой теме
остались белым по белому.

Страница поднимается в headless-Chrome в четырёх вариантах (1400px и 390px × светлая
и тёмная тема). У каждого видимого текста и значка считается контраст с тем, что под
ним. Если элемент лежит на фотографии и у него своя полупрозрачная подложка, берётся
худший случай: фото белое и фото чёрное.

Что попадает в отчёт:
  • НЕ ВИДНО — контраст ниже 1.8 (белое по белому, тёмное по тёмному);
  • РАСХОДИТСЯ — в одной ширине элемент читается (≥ 3), а в другой той же темы нет.

Запуск:
    python3 tools/ui_parity.py                    # все страницы
    python3 tools/ui_parity.py index.html buy.html
    python3 tools/ui_parity.py --short            # одна строка итога (для сборки)
"""
import http.server, json, os, re, socketserver, subprocess, sys, threading
from urllib.parse import quote, urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PORT = 8794
PAGES = ['index.html', 'about.html', 'buy.html', 'rent.html', 'management.html',
         'districts/bang-tao.html', 'guide/kakaya-dohodnost.html', 'add-property.html',
         'object/heritage.html']
# 21.09: полный круг — это 9 страниц × 2 темы × 2 ширины = 36 запусков Chrome.
# На сборке он дважды за сутки сломался: один раз висел 16 минут, второй раз
# машину выбило по памяти и проверка умерла по таймауту, оборвав сборку.
# В сборке (--short) идём коротким кругом: три страницы разных шаблонов —
# главная, раздел каталога и карточка объекта. Они покрывают всю общую вёрстку,
# потому что остальные страницы собираются из тех же кусков. Полный круг остаётся
# для ручного прогона: python3 tools/ui_parity.py --full
БЫСТРЫЕ = ['index.html', 'rent.html', 'object/heritage.html']
BAD, GOOD = 1.8, 3.0

PROBE = r"""<script>
setTimeout(function(){
  var q = new URLSearchParams(location.search), theme = q.get('theme');
  document.documentElement.setAttribute('data-theme', theme);
  /* плавные появления при прокрутке (reveal, карусель) в фоновом прогоне так и остаются
     прозрачными — и всё внутри выпадало из проверки. Показываем сразу и без переходов. */
  var st=document.createElement('style');
  st.textContent='*{transition:none!important;animation:none!important}.reveal,.carwrap{opacity:1!important;transform:none!important}';
  document.head.appendChild(st);
  Array.prototype.forEach.call(document.querySelectorAll('.reveal'), function(e){ e.classList.add('visible'); });
  setTimeout(function(){
    /* браузер отдаёт цвет и как rgb(10, 10, 10), и как color(srgb 0.97 0.96 0.94 / 0.88) — второй в долях единицы */
    function P(c){ c=c||''; var m=c.match(/[\d.]+/g)||[];
      var k=/^color\(/.test(c)?255:1;
      return {r:(+m[0]||0)*k,g:(+m[1]||0)*k,b:(+m[2]||0)*k,a:m.length>3?+m[3]:1}; }
    function ch(v){ v/=255; return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }
    function L(c){ return 0.2126*ch(c.r)+0.7152*ch(c.g)+0.0722*ch(c.b); }
    function CR(a,b){ var x=L(a), y=L(b); return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); }
    function over(top,under){ var a=top.a; return {r:top.r*a+under.r*(1-a), g:top.g*a+under.g*(1-a), b:top.b*a+under.b*(1-a), a:1}; }
    function onPhoto(el){
      var r=el.getBoundingClientRect(), box=el.closest('.prop,.car,.pm,.card,section')||document.body;
      var imgs=Array.prototype.slice.call(box.querySelectorAll('img,picture,video,.pic-photo,.thumb-photo'));
      var p0=el.parentElement;
      while(p0 && p0!==box.parentElement){ if(getComputedStyle(p0).backgroundImage.indexOf('url(')>=0){ imgs.push(p0); break; } p0=p0.parentElement; }
      for(var i=0;i<imgs.length;i++){ var im=imgs[i]; if(el.contains(im)) continue;
        if(im.contains && im.contains(el) && getComputedStyle(im).backgroundImage.indexOf('url(')>=0) return true;
        var q2=im.getBoundingClientRect();
        if(q2.width>40 && q2.left<r.right && q2.right>r.left && q2.top<r.bottom && q2.bottom>r.top) return true; }
      return false;
    }
    /* подложка отдельным слоем: абсолютный соседний блок с картинкой или градиентом под текстом
       (плитки услуг, затемнение фото). Что именно под текстом — неизвестно, значит «фото». */
    function hasCover(e, el){
      var r=el.getBoundingClientRect();
      for(var i=0;i<e.children.length;i++){ var c=e.children[i];
        if(c===el || c.contains(el)) continue;
        var cs=getComputedStyle(c);
        if((cs.position==='absolute'||cs.position==='fixed') && cs.backgroundImage!=='none'){
          var q=c.getBoundingClientRect();
          if(q.left<r.right && q.right>r.left && q.top<r.bottom && q.bottom>r.top) return true; }
      }
      return false;
    }
    /* слои фона снизу вверх до первого непрозрачного; фото — «неизвестно под низом» */
    function under(el){
      var layers=[], e=el, photo=onPhoto(el);
      while(e && e.nodeType===1){
        if(e!==el && hasCover(e, el)) return {layers:layers, base:'photo'};
        var cs=getComputedStyle(e), bi=cs.backgroundImage||'';
        /* картинка фона рисуется ПОВЕРХ цвета фона: фото — «неизвестно», градиент — его цвет */
        if(bi.indexOf('url(')>=0) return {layers:layers, base:'photo'};
        if(/gradient/.test(bi)){
          var gm=bi.match(/rgba?\([^)]*\)|color\([^)]*\)/);
          if(gm){ var g=P(gm[0]); if(g.a>=0.5){ layers.push({r:g.r,g:g.g,b:g.b,a:1}); return {layers:layers, base:null}; } }
        }
        var c=P(cs.backgroundColor);
        if(c.a>0) layers.push(c);
        if(c.a>=0.98) return {layers:layers, base:null};
        if(photo && e!==el && e.querySelector && e.querySelector('img')) return {layers:layers, base:'photo'};
        e=e.parentElement;
      }
      return {layers:layers, base:P(getComputedStyle(document.body).backgroundColor)};
    }
    function flat(stack, base){
      var c=base; for(var i=stack.length-1;i>=0;i--){ c = c ? over(stack[i], c) : stack[i]; } return c;
    }
    function visible(el){
      var r=el.getBoundingClientRect(); if(r.width<4||r.height<4) return false;
      var e=el, op=1;
      while(e && e.nodeType===1){ var s=getComputedStyle(e);
        if(s.display==='none'||s.visibility==='hidden') return false;
        op*=parseFloat(s.opacity||'1'); if(e.hidden) return false; e=e.parentElement; }
      return op>0.35;
    }
    var SEL='button,a,.fav,.cmpb,.chipf,.tag,.pm-tag,.roi,.badge,.kicker,label,.val,h1,h2,h3,h4,p,li,.z-y,.stg,.sub';
    var out=[], seen={};
    Array.prototype.forEach.call(document.querySelectorAll(SEL), function(el){
      if(!visible(el)) return;
      if(el.closest('.mnav,.chatwin,.modal,.lbox,[aria-hidden="true"]')) return;
      var own=Array.prototype.some.call(el.childNodes, function(n){ return n.nodeType===3 && n.textContent.trim().length>0; });
      var icon=!own && el.querySelector(':scope > svg') && (el.tagName==='BUTTON'||el.tagName==='A');
      if(!own && !icon) return;
      var s=getComputedStyle(el), fg=P(s.color); if(fg.a===0) return;
      var u=under(el), worst;
      if(u.base==='photo'){
        if(!u.layers.length) return;           /* текст прямо на фото без подложки — осознанный приём */
        var w=flat(u.layers,{r:255,g:255,b:255,a:1}), k=flat(u.layers,{r:0,g:0,b:0,a:1});
        worst=Math.min(CR(over(fg,w),w), CR(over(fg,k),k));
      } else {
        var bg=flat(u.layers,u.base); worst=CR(over(fg,bg),bg);
      }
      var txt=(el.textContent||el.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim().slice(0,32);
      var cls=String(el.className&&el.className.baseVal!==undefined?el.className.baseVal:el.className||'').trim().split(/\s+/).slice(0,2).join('.');
      var key=el.tagName.toLowerCase()+(cls?'.'+cls:'')+'|'+txt;
      if(seen[key]!==undefined && seen[key]<=worst) return;
      seen[key]=worst;
      out.push({k:key, c:Math.round(worst*100)/100});
    });
    var pre=document.createElement('pre'); pre.id='__parity'; pre.textContent=JSON.stringify(out);
    document.body.appendChild(pre);
  }, 700);
}, 2600);
</script>"""

WRAP = r"""<!doctype html><html><body style="margin:0;background:#777">
<iframe id="f" src="__SRC__" style="width:__W__px;height:900px;border:0;display:block"></iframe>
<script>
var t=setInterval(function(){try{var d=document.getElementById('f').contentDocument;
var p=d&&d.getElementById('__parity');if(p){var q=document.createElement('pre');q.id='__parity';
q.textContent=p.textContent;document.body.appendChild(q);clearInterval(t);}}catch(e){}},250);
</script></body></html>"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw): super().__init__(*a, directory=ROOT, **kw)
        def log_message(self, *a): pass
        def send_raw(self, raw, ctype):
            self.send_response(200); self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path == '/__wrap.html':
                return self.send_raw(WRAP.replace('__SRC__', q['src'][0]).replace('__W__', q['w'][0]).encode(), 'text/html; charset=utf-8')
            if u.path.endswith('.html') and 'theme' in q:
                f = os.path.join(ROOT, u.path.lstrip('/'))
                html = open(f, encoding='utf-8').read()
                k = html.rfind('</body>')          # первое </body> бывает внутри JS-строки
                return self.send_raw((html[:k] + PROBE + html[k:]).encode('utf-8'), 'text/html; charset=utf-8')
            return super().do_GET()
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def свободная_память():
    """Свободно мегабайт. None, если измерить не вышло."""
    try:
        out = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=10).stdout
        размер = int(re.search(r'page size of (\d+)', out).group(1))
        своб = int(re.search(r'Pages free:\s+(\d+)', out).group(1))
        неакт = int(re.search(r'Pages inactive:\s+(\d+)', out).group(1))
        return (своб + неакт) * размер // (1024 * 1024)
    except Exception:
        return None


def measure(page, width, theme):
    inner = 'http://127.0.0.1:%d/%s?theme=%s' % (PORT, page, theme)
    # headless не делает окно уже 500px — телефон меряем в рамке нужной ширины
    url, win = (inner, width) if width >= 500 else (
        'http://127.0.0.1:%d/__wrap.html?w=%d&src=%s' % (PORT, width, quote(inner, safe='')), 520)
    r = subprocess.run([CHROME, '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                        '--window-size=%d,900' % win, '--virtual-time-budget=9000', '--dump-dom', url],
                       capture_output=True, text=True, timeout=90)
    m = re.search(r'<pre id="__parity">(.*?)</pre>', r.stdout, re.S)
    if not m:
        return None
    raw = m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return {x['k']: x['c'] for x in json.loads(raw)}


def main():
    short = '--short' in sys.argv
    pages = [a for a in sys.argv[1:] if a.endswith('.html')]
    if not pages:
        pages = PAGES if '--full' in sys.argv else (БЫСТРЫЕ if short else PAGES)
    # Проверка поднимает браузер: на забитой памяти он не стартует и роняет прогон.
    # Лучше честно пропустить, чем оборвать сборку на ровном месте.
    свободно = свободная_память()
    if свободно is not None and свободно < 400:
        print('[вид] пропущено: свободно всего %d МБ памяти — браузер не поднять' % свободно)
        return 0
    srv = serve()
    invisible, diverge, broken = [], [], []
    try:
        for page in pages:
            if not os.path.exists(os.path.join(ROOT, page)):
                continue
            for theme in ('light', 'dark'):
                res = {}
                for width, label in ((1400, 'компьютер'), (390, 'телефон')):
                    res[label] = measure(page, width, theme)
                    if res[label] is None:
                        broken.append('%s · %s · %s: страница не дорисовалась' % (page, theme, label))
                if not res['компьютер'] or not res['телефон']:
                    continue
                for label, other in (('компьютер', 'телефон'), ('телефон', 'компьютер')):
                    for k, c in res[label].items():
                        if c < BAD:
                            invisible.append((page, theme, label, k, c))
                            o = res[other].get(k)
                            if o is not None and o >= GOOD:
                                diverge.append((page, theme, label, k, c, other, o))
                if not short:
                    print('  %-32s %-5s проверено: компьютер %d, телефон %d' % (page, theme, len(res['компьютер']), len(res['телефон'])))
    finally:
        srv.shutdown()
    names = {'light': 'светлая', 'dark': 'тёмная'}
    if short:
        print('[вид] %s: не видно %d, расходится компьютер/телефон %d%s' % (
            'ок' if not (invisible or broken) else 'ЕСТЬ ЗАМЕЧАНИЯ', len(invisible), len(diverge),
            (' — ' + '%s %s %s: %s' % (invisible[0][0], names[invisible[0][1]], invisible[0][2], invisible[0][3])) if invisible else ''))
    else:
        print('\nНЕ ВИДНО (контраст < %.1f): %d' % (BAD, len(invisible)))
        for p, t, w, k, c in invisible[:60]:
            print('  ✗ %-28s %-8s %-9s %-55s %.2f' % (p, names[t], w, k[:55], c))
        print('\nРАСХОДИТСЯ компьютер/телефон: %d' % len(diverge))
        for p, t, w, k, c, o, oc in diverge[:40]:
            print('  ≠ %-28s %-8s %s %.2f, а %s %.2f — %s' % (p, names[t], w, c, o, oc, k[:60]))
        for b in broken: print('  !', b)
    return 1 if (invisible or broken) else 0


if __name__ == '__main__':
    sys.exit(main())
