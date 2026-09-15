#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полный обход сайта и кабинета: каждая кнопка нажата, формы заполнены и отправлены.

Эльнур 15.09.2026: «пройти по каждому блоку и каждой кнопке: нажать, заполнить, отправить,
сверить, принять, отменить, забронировать, получить оффер, загрузить документ — что они
дают и куда идут».

Как работает. Страница открывается в Playwright (твой Chrome, без отдельного браузера).
Обходчик раз за разом находит видимые кнопки, ссылки, пункты выбора и сворачиваемые окна,
перед «отправляющими» кнопками заполняет пустые поля тестовыми данными, подсовывает
тестовый файл в загрузки, соглашается с подтверждениями — и нажимает. После каждого
нажатия записывает, что произошло: запрос на сервер (куда и с каким действием),
переход, новое окно, диалог, сообщение на экране или хотя бы изменение блока.

🔒 Наружу НИЧЕГО не уходит. Все запросы к api/hub/Supabase перехватываются: запись +
правдоподобный ответ-заглушка. Заявки не падают в amoCRM, чат не будит мозг, письма и
сообщения не отправляются. Кабинет поднимается на снимке реальных данных (ключ штаба).

Запуск (нужен playwright: pip3 install playwright):
    python3 tools/flow_audit.py                      # все сценарии → /tmp/plp_flow_audit.json
    python3 tools/flow_audit.py index-desktop owner-staff
    python3 tools/flow_audit.py --list
"""
import json, os, re, sys, time, threading
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cab_check  # noqa: E402  (сервер страниц и снимок данных кабинета)

ROOT = cab_check.ROOT
OUT = os.environ.get('AUDIT_OUT', '/tmp/plp_flow_audit.json')
cab_check.PORT = int(os.environ.get('AUDIT_PORT', cab_check.PORT))
TEST_DIR = '/tmp/plp_flow_files'
BASE = 'http://127.0.0.1:%d' % cab_check.PORT

SCENARIOS = {
    'index-desktop':   ('/index.html', 'desktop', None),
    'index-mobile':    ('/index.html', 'mobile', None),
    'buy-desktop':     ('/buy.html', 'desktop', None),
    'rent-desktop':    ('/rent.html', 'desktop', None),
    'district-desktop': ('/districts/bang-tao.html', 'desktop', None),
    'management-desktop': ('/management.html', 'desktop', None),
    'addprop-desktop': ('/add-property.html', 'desktop', None),
    'object-desktop':  ('/object/heritage.html', 'desktop', None),
    'owner-login':     ('/owner.html', 'desktop', 'gate'),
    'owner-staff':     ('/__cab.html', 'desktop', 'staff'),
    'owner-staff-mobile': ('/__cab.html', 'mobile', 'staff'),
    'cabinet-desktop': ('/__cab.html', 'desktop', 'staff'),
    'cabinet-mobile':  ('/__cab.html', 'mobile', 'staff'),
}

SUBMIT_RE = re.compile(r'отправ|сохран|далее|дальше|войти|получ|остав|заброн|запис|размест|добав|созда|принят|принять|'
                       r'отклон|готово|продолж|рассчит|показать|подобр|запрос|сменить|внести|поставить|назнач|'
                       r'загруз|прикреп|send|next|save|submit|ok\b|✓|➤|→', re.I)
SKIP_TEXT_RE = re.compile(r'^(выйти|logout)$', re.I)
MSG_SEL = ('.say,.toast,.err,.ok,.status,.done,[role=alert],.msg,.qz-done,.st,.df-status,.hintline,'
           '.fstate,.upstate,.saved,.note-ok,.empty,.pickempty,.chat-msg,.bubble')

WALK_JS = r"""
(opts) => {
  const SEL = 'button, a[href], [onclick], [role=button], .opt, .chipf, .fbtn, .lnk, .foldh, .msub-h, .pickbtn, ' +
              '.pickitem, [data-tab], .qz-opt, .zone, .prop, .srv-card, .tab, summary, label.rf-check, ' +
              'input[type=checkbox], input[type=radio], .mdot, .unit, .bcell, .zprop, .mobj, .faq-q';
  const vis = el => { const r = el.getBoundingClientRect(); if (r.width < 3 || r.height < 3) return false;
    let e = el; while (e && e.nodeType === 1) { const s = getComputedStyle(e);
      if (s.display === 'none' || s.visibility === 'hidden' || e.hidden) return false; e = e.parentElement; }
    return true; };
  const txt = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '')
                    .replace(/\s+/g, ' ').trim().slice(0, 60);
  const where = el => {
    const box = el.closest('.modal, .pm, #chatwin, .chatwin, dialog, .qz, #quiz, section, .card, #app, header, footer, .mnav');
    if (!box) return '';
    const h = box.querySelector('.kicker, h2, h3, .foldh, .title, legend');
    return ((box.id ? '#' + box.id + ' ' : '') + (h ? txt(h) : '')).slice(0, 70);
  };
  const out = [];
  let n = 0;
  document.querySelectorAll(SEL).forEach(el => {
    if (!vis(el)) return;
    if (el.closest('[data-audit-skip]')) return;
    if (el.closest('.leaflet-control-attribution, .maplibregl-ctrl-attrib')) return;
    // вложенная кнопка внутри уже кликабельного элемента — берём самый внутренний
    const label = txt(el);
    const cls = String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '')
                  .trim().split(/\s+/).slice(0, 3).join('.');
    const sig = el.tagName + '|' + cls + '|' + label + '|' + where(el);
    const id = 'a' + (++n);
    el.setAttribute('data-audit-id', id);
    out.push({ id, sig, tag: el.tagName.toLowerCase(), cls, label, where: where(el),
               href: el.getAttribute('href') || '', type: el.getAttribute('type') || '',
               onclick: (el.getAttribute('onclick') || '').slice(0, 80) });
  });
  return out;
}
"""

FILL_JS = r"""
(id) => {
  const el = document.querySelector('[data-audit-id="' + id + '"]');
  if (!el) return 0;
  const box = el.closest('form, .modal, .pm, #chatwin, .chatwin, dialog, .qz, #quiz, .card, section, .fgrid, #cl-form') || document.body;
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2 && getComputedStyle(e).visibility !== 'hidden'; };
  const set = (e, v) => { const proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype :
                          (e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype);
    const d = Object.getOwnPropertyDescriptor(proto, 'value'); d && d.set ? d.set.call(e, v) : (e.value = v);
    e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); };
  const iso = d => { const x = new Date(Date.now() + d * 864e5); return x.toISOString().slice(0, 10); };
  let n = 0;
  const fields = box.querySelectorAll('input, textarea, select');
  if (fields.length > 40) return 0;
  fields.forEach(f => {
    if (!vis(f) || f.disabled || f.readOnly) return;
    const t = (f.getAttribute('type') || f.tagName).toLowerCase();
    if (['hidden', 'file', 'submit', 'button', 'checkbox', 'radio', 'range', 'search'].includes(t)) return;
    if (f.value && f.tagName !== 'SELECT') return;
    const hint = ((f.name || '') + ' ' + (f.id || '') + ' ' + (f.placeholder || '') + ' ' + (f.getAttribute('aria-label') || '')).toLowerCase();
    let v = 'ТЕСТ обход кнопок — не обрабатывать';
    if (t === 'tel' || /phone|тел|номер|whatsapp/.test(hint)) v = '+66954143874';
    else if (t === 'email' || /mail|почт/.test(hint)) v = 'audit.test@example.com';
    else if (t === 'number' || /цен|сумм|price|amount|бюджет|площад|спал|кол|cost/.test(hint)) v = '3';
    else if (t === 'date') v = /out|выезд|до|end|to/.test(hint) ? iso(12) : iso(8);
    else if (t === 'datetime-local') v = iso(9) + 'T15:00';
    else if (t === 'time') v = '15:00';
    else if (t === 'password') v = 'Test-audit-2026';
    else if (/имя|name|фио/.test(hint)) v = 'ТЕСТ Claude';
    else if (/код|code|otp/.test(hint)) v = '123456';
    else if (/url|ссылк|link|drive/.test(hint)) v = 'https://drive.google.com/drive/folders/TEST-AUDIT';
    if (f.tagName === 'SELECT') { if (f.options.length > 1 && f.selectedIndex <= 0) { f.selectedIndex = 1; f.dispatchEvent(new Event('change', { bubbles: true })); n++; } return; }
    set(f, v); n++;
  });
  return n;
}
"""

SNAP_JS = r"""
([id, msgSel]) => {
  const el = document.querySelector('[data-audit-id="' + id + '"]');
  const box = el ? (el.closest('.modal, .pm, #chatwin, .chatwin, dialog, section, .card, #app') || document.body) : document.body;
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  const msgs = Array.from(document.querySelectorAll(msgSel)).filter(vis).map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  let h = 5381; const s = box.innerHTML; for (let i = 0; i < s.length; i += 7) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  const open = document.querySelectorAll('.open, .on, [open], .visible').length;
  return { msgs: msgs.slice(0, 40), box: h + ':' + s.length, open, url: location.href, scroll: Math.round(scrollY),
           title: document.title, bodyLen: document.body.innerHTML.length };
}
"""


def link_target_ok(href, current_path):
    """Ссылка внутри сайта: есть ли такая страница и такой раздел на ней."""
    u = urlparse(href)
    path = u.path or current_path
    if path in ('', '/'):
        f = 'index.html'
    else:
        f = path.lstrip('/')
        if f.startswith('__cab'):
            f = 'owner.html'
        if not f.endswith('.html') and '.' not in os.path.basename(f):
            f = f + '.html'
    full = os.path.join(ROOT, f)
    if not os.path.exists(full):
        return False, 'нет страницы ' + f
    if u.fragment:
        html = open(full, encoding='utf-8', errors='ignore').read()
        if ('id="%s"' % u.fragment) not in html and ("id='%s'" % u.fragment) not in html:
            return False, 'на %s нет раздела #%s' % (f, u.fragment)
    return True, ''


def make_files():
    os.makedirs(TEST_DIR, exist_ok=True)
    jpg = os.path.join(TEST_DIR, 'test-audit.jpg')
    pdf = os.path.join(TEST_DIR, 'test-audit.pdf')
    if not os.path.exists(jpg):
        try:
            from PIL import Image
            Image.new('RGB', (64, 48), (180, 190, 150)).save(jpg, quality=80)
        except Exception:
            open(jpg, 'wb').write(bytes.fromhex('ffd8ffe000104a46494600010100000100010000ffd9'))
    if not os.path.exists(pdf):
        open(pdf, 'wb').write(b'%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n')
    return jpg, pdf


class Recorder:
    def __init__(self, data):
        self.data = data
        self.reqs = []
        self.lock = threading.Lock()

    def stub_for(self, host, path, method, body, query):
        if host.endswith('api.property-library.com') and path.startswith('/ukowner'):
            act = (body or {}).get('action') if isinstance(body, dict) else None
            if act == 'data':
                return self.data
            if act == 'card':
                pid = body.get('property_id')
                p = next((x for x in self.data.get('properties', []) if x.get('id') == pid), None)
                return {'ok': True, 'property': p}
            if act == 'request_code':
                return {'ok': True, 'sent': True, 'channel': body.get('channel') or 'whatsapp', 'mask': '+66 •••• 3874'}
            if act in ('verify_code', 'login'):
                return {'ok': True, 'token': 'audit-token', 'owner': self.data.get('owner')}
            if act == 'me':
                return {'ok': True, 'owner': self.data.get('owner')}
            return {'ok': True, 'rows': [], 'items': [], 'id': 1, 'doc_id': 1, 'data': {'rows': []}}
        if host.endswith('api.property-library.com') and path.startswith('/offer'):
            return '<html><body><h1>ОФФЕР (заглушка обхода)</h1></body></html>'
        if 'check-availability' in path:
            return {'ok': True, 'available': [], 'check_in': query.get('check_in', [''])[0], 'check_out': query.get('check_out', [''])[0]}
        if 'site-chat' in path or 'site-voice' in path:
            return {'ok': True, 'reply': 'Тестовый ответ обходчика.', 'text': 'Тестовый ответ обходчика.'}
        if 'supabase.co' in host:
            return [] if method == 'GET' else {'ok': True, 'Key': 'audit/test.jpg'}
        return {'ok': True}

    def handle(self, route, request):
        u = urlparse(request.url)
        host, path = u.hostname or '', u.path
        external = (host.endswith('property-library.com') and host != 'property-library.com') or 'supabase.co' in host \
            or host in ('api.telegram.org',)
        if not external:
            return route.continue_()
        if 'supabase.co' in host and request.method == 'GET' and '/storage/' in path:
            return route.continue_()   # фото объектов — чтение, не действие
        body = None
        raw = request.post_data or ''
        try:
            body = json.loads(raw) if raw else None
        except Exception:
            body = {'_raw': raw[:80]}
        keys = sorted(body.keys()) if isinstance(body, dict) else []
        entry = {'t': time.time(), 'method': request.method, 'host': host, 'path': path,
                 'action': (body or {}).get('action') if isinstance(body, dict) else None,
                 'keys': [k for k in keys if k not in ('token', 'data')][:14],
                 'has_file': bool(isinstance(body, dict) and body.get('data') and len(str(body.get('data'))) > 40),
                 'query': sorted(parse_qs(u.query).keys())}
        with self.lock:
            self.reqs.append(entry)
        stub = self.stub_for(host, path, request.method, body, parse_qs(u.query))
        if isinstance(stub, str):
            return route.fulfill(status=200, content_type='text/html; charset=utf-8', body=stub)
        return route.fulfill(status=200, content_type='application/json',
                             headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(stub, ensure_ascii=False))


def run_scenario(pw, name, data, jpg, pdf, max_actions=420, budget_s=720):
    path, device, mode = SCENARIOS[name]
    browser = pw.chromium.launch(channel='chrome', headless=True)
    if device == 'mobile':
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, locale='ru-RU')
    else:
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900}, locale='ru-RU')
    rec = Recorder(data)
    ctx.route('**/*', rec.handle)
    page = ctx.new_page()
    events = {'dialogs': [], 'popups': [], 'downloads': [], 'errors': [], 'choosers': 0}
    page.on('dialog', lambda d: (events['dialogs'].append(d.message[:120]), d.accept('тест') if d.type == 'prompt' else d.accept()))
    page.on('pageerror', lambda e: events['errors'].append(str(e)[:160]))
    page.on('download', lambda d: events['downloads'].append(d.suggested_filename))

    def on_popup(p):
        events['popups'].append(p.url)
        try: p.close()
        except Exception: pass
    ctx.on('page', on_popup)

    def on_chooser(fc):
        events['choosers'] += 1
        acc = ''
        try: acc = fc.element.get_attribute('accept') or ''
        except Exception: pass
        try: fc.set_files(pdf if ('pdf' in acc and 'image' not in acc) else jpg)
        except Exception: pass
    page.on('filechooser', on_chooser)

    def boot():
        page.goto(BASE + path, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(2200)
        if mode == 'staff':
            page.evaluate("() => { try { localStorage.setItem('plp_owner_sel', JSON.stringify(['PLP-DEMO'])); } catch(e){} }")
            page.evaluate("(d) => window.__cabDemo && window.__cabDemo(d)", data)
            page.wait_for_timeout(1500)
        page.add_style_tag(content='*{transition:none!important;animation:none!important}.reveal{opacity:1!important;transform:none!important}')
        page.evaluate("() => document.querySelectorAll('.reveal').forEach(e => e.classList.add('visible'))")

    boot()
    start = time.time()
    done, results = set(), []
    home = urlparse(page.url).path
    stale_rounds = 0
    while len(results) < max_actions and time.time() - start < budget_s:
        try:
            items = page.evaluate(WALK_JS, {})
        except Exception:
            boot(); continue
        todo = [it for it in items if it['sig'] not in done]
        if not todo:
            stale_rounds += 1
            if stale_rounds > 1: break
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); page.wait_for_timeout(600)
            continue
        stale_rounds = 0
        it = todo[0]
        done.add(it['sig'])
        rec_i = {'label': it['label'], 'where': it['where'], 'tag': it['tag'], 'cls': it['cls'], 'onclick': it['onclick']}
        href = it['href']
        if SKIP_TEXT_RE.search(it['label'] or ''):
            rec_i.update(verdict='пропуск', note='выход — не нажимаем, чтобы не рвать обход'); results.append(rec_i); continue
        if it['tag'] == 'a' and href and not href.startswith('#') and not href.startswith('javascript'):
            u = urlparse(href)
            if u.scheme in ('tel', 'mailto'):
                rec_i.update(verdict='ссылка', note=href[:80]); results.append(rec_i); continue
            if u.netloc and not u.netloc.startswith('127.0.0.1'):
                rec_i.update(verdict='ссылка наружу', note=href[:100]); results.append(rec_i); continue
            ok_l, why = link_target_ok(href, path)
            rec_i.update(verdict='ссылка' if ok_l else 'битая ссылка', note=(href[:100] + ('' if ok_l else ' — ' + why)))
            results.append(rec_i); continue
        if it['tag'] == 'a' and href.startswith('#') and len(href) > 1:
            exists = page.evaluate("(h) => !!document.getElementById(h.slice(1))", href)
            if not exists:
                rec_i.update(verdict='битая ссылка', note=href + ' — на этой странице нет такого раздела'); results.append(rec_i); continue
        filled = 0
        if SUBMIT_RE.search(it['label'] or '') or it['tag'] in ('button',):
            try: filled = page.evaluate(FILL_JS, it['id'])
            except Exception: filled = 0
        try:
            before = page.evaluate(SNAP_JS, [it['id'], MSG_SEL])
        except Exception:
            before = None
        n_req, n_dlg, n_pop, n_err, n_dl, n_ch = len(rec.reqs), len(events['dialogs']), len(events['popups']), len(events['errors']), len(events['downloads']), events['choosers']
        how = 'мышью'
        try:
            page.locator('[data-audit-id="%s"]' % it['id']).first.click(timeout=1200, no_wait_after=True)
        except Exception as e:
            # элемент перекрыт или вне экрана — жмём так, как это сделал бы сам обработчик
            try:
                ok_js = page.evaluate("(id) => { const el = document.querySelector('[data-audit-id=\"' + id + '\"]'); if (!el) return false; el.scrollIntoView({block:'center'}); el.click(); return true; }", it['id'])
                how = 'скриптом (перекрыт или вне экрана)'
                if not ok_js:
                    raise e
            except Exception as e2:
                rec_i.update(verdict='не нажалась', note=str(e2).split('\n')[0][:120]); results.append(rec_i); continue
        page.wait_for_timeout(650)
        rec_i['how'] = how
        try:
            after = page.evaluate(SNAP_JS, [it['id'], MSG_SEL])
        except Exception:
            after = None
        reqs = rec.reqs[n_req:]
        rec_i['filled'] = filled
        rec_i['requests'] = [{k: r[k] for k in ('method', 'host', 'path', 'action', 'keys', 'has_file', 'query')} for r in reqs]
        rec_i['dialogs'] = events['dialogs'][n_dlg:]
        rec_i['popups'] = events['popups'][n_pop:]
        rec_i['downloads'] = events['downloads'][n_dl:]
        rec_i['errors'] = events['errors'][n_err:]
        rec_i['file_chosen'] = events['choosers'] - n_ch
        new_msgs = []
        nav = None
        if before and after:
            new_msgs = [m for m in after['msgs'] if m not in before['msgs']][:4]
            if urlparse(after['url']).path != urlparse(before['url']).path:
                nav = after['url']
        changed = bool(before and after and (before['box'] != after['box'] or before['open'] != after['open']
                       or before['scroll'] != after['scroll'] or before['bodyLen'] != after['bodyLen']))
        rec_i['messages'] = new_msgs
        rec_i['navigated'] = nav
        if rec_i['errors']:
            verdict = 'ошибка страницы'
        elif reqs or nav or rec_i['popups'] or rec_i['dialogs'] or rec_i['downloads'] or rec_i['file_chosen']:
            verdict = 'работает'
        elif new_msgs or changed:
            verdict = 'отвечает на экране'
        else:
            verdict = 'нет реакции'
        rec_i['verdict'] = verdict
        results.append(rec_i)
        if nav and urlparse(nav).path != home:
            boot()
    ctx.close(); browser.close()
    return {'scenario': name, 'path': path, 'device': device, 'mode': mode, 'actions': results,
            'requests_total': len(rec.reqs), 'elapsed_s': round(time.time() - start), 'errors': events['errors'][:30]}


CAB_WALK_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); if (r.width < 3 || r.height < 3) return false;
    let e = el; while (e && e.nodeType === 1) { const st = getComputedStyle(e);
      if (st.display === 'none' || st.visibility === 'hidden' || e.hidden) return false; e = e.parentElement; } return true; };
  const txt = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const roots = [document.getElementById('cl-form'), document.getElementById('cab-body')].filter(Boolean);
  const SEL = 'button, a[href="#"], a:not([href]), [onclick], .lnk, .opt, .chipf, .msub-h, [data-a], [data-uk], [data-rep], .bcell, .unit, input[type=checkbox], label.rf-check';
  const SKIP = '.pickall, .picknone, .pickitem, .pickbtn, .foldh, .picker *, #cab-nav *, .fab, .chathead *';
  const out = []; let n = 0;
  roots.forEach(root => root.querySelectorAll(SEL).forEach(el => {
    if (!vis(el) || el.matches(SKIP) || el.closest('.picker')) return;
    const card = el.closest('#cl-form, .card, [id^="sec-"], #portfolio');
    const head = card ? card.querySelector('.foldh span, h3, h2, .eyebrow') : null;
    const inForm = !!el.closest('#cl-form');
    const label = txt(el);
    const where = (inForm ? 'окно: ' : '') + (head ? txt(head) : (card && card.id) || '');
    const id = 'c' + (++n); el.setAttribute('data-audit-id', id);
    out.push({ id, label, where, inForm, tag: el.tagName.toLowerCase(), elid: el.id || '',
               cls: String(el.className || '').split(/\s+/).slice(0, 2).join('.'),
               sig: (inForm ? 'F|' : '') + where + '|' + label + '|' + (el.id || '') });
  }));
  return out;
}
"""


def run_cabinet(pw, data, jpg, pdf, device='desktop', budget_s=900):
    """Кабинет штаба: раздел за разделом, все окна раскрыты, каждая кнопка и каждая форма."""
    browser = pw.chromium.launch(channel='chrome', headless=True)
    ctx = (browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='ru-RU')
           if device == 'mobile' else browser.new_context(viewport={'width': 1400, 'height': 900}, locale='ru-RU'))
    rec = Recorder(data)
    ctx.route('**/*', rec.handle)
    page = ctx.new_page()
    ev = {'dialogs': [], 'popups': [], 'errors': [], 'downloads': [], 'choosers': 0}
    page.on('dialog', lambda d: (ev['dialogs'].append(d.message[:120]), d.accept('тест') if d.type == 'prompt' else d.accept()))
    page.on('pageerror', lambda e: ev['errors'].append(str(e)[:160]))
    page.on('download', lambda d: ev['downloads'].append(d.suggested_filename))
    ctx.on('page', lambda p: (ev['popups'].append(p.url), p.close()))
    def chooser(fc):
        ev['choosers'] += 1
        try: fc.set_files(jpg)
        except Exception: pass
    page.on('filechooser', chooser)

    def boot():
        page.goto(BASE + '/__cab.html', wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate("() => { try { localStorage.setItem('plp_owner_sel', JSON.stringify(['PLP-DEMO'])); } catch(e){} }")
        page.evaluate("(d) => window.__cabDemo && window.__cabDemo(d)", data)
        page.wait_for_timeout(1200)
        page.add_style_tag(content='*{transition:none!important;animation:none!important}')

    boot()
    tabs = page.evaluate("() => Array.from(document.querySelectorAll('#cab-nav a[data-tab]')).map(a => [a.getAttribute('data-tab'), (a.innerText||'').replace(/\\s+\\d+$/,'').trim()])")
    results, start = [], time.time()
    for tab, tab_name in tabs:
        if time.time() - start > budget_s: break
        done = set()
        for _round in range(60):
            if time.time() - start > budget_s: break
            # раздел открыт, все окна раскрыты
            page.evaluate("""(t) => { const nav = document.getElementById('cab-nav'), body = document.getElementById('cab-body');
                const a = nav && nav.querySelector('a[data-tab="' + t + '"]');
                if (a && (window.CAB_TAB !== t || body.hidden)) { if (body.hidden || !a.classList.contains('on')) a.click(); }
                document.querySelectorAll('#cab-body .foldh').forEach(h => { const i = h.querySelector('.foldi'); if (i && i.textContent.trim() === '+') h.click(); }); }""", tab)
            page.wait_for_timeout(250)
            items = page.evaluate(CAB_WALK_JS)
            # сначала то, что внутри открытой формы; «Отмена/Закрыть» — в самом конце
            items.sort(key=lambda x: (0 if x['inForm'] else 1, 1 if re.search(r'отмен|закры|×', x['label'] or '', re.I) else 0))
            todo = [x for x in items if x['sig'] not in done]
            if not todo: break
            it = todo[0]; done.add(it['sig'])
            r = {'label': it['label'], 'where': tab_name + ' · ' + it['where'], 'tag': it['tag'], 'cls': it['cls']}
            filled = page.evaluate(FILL_JS, it['id']) if (it['inForm'] or SUBMIT_RE.search(it['label'] or '')) else 0
            before = page.evaluate(SNAP_JS, [it['id'], MSG_SEL])
            nr, nd, npop, ne, nch = len(rec.reqs), len(ev['dialogs']), len(ev['popups']), len(ev['errors']), ev['choosers']
            try:
                page.locator('[data-audit-id="%s"]' % it['id']).first.click(timeout=1200, no_wait_after=True)
            except Exception:
                try: page.evaluate("(id) => document.querySelector('[data-audit-id=\"' + id + '\"]').click()", it['id'])
                except Exception as e:
                    r.update(verdict='не нажалась', note=str(e)[:100]); results.append(r); continue
            page.wait_for_timeout(700)
            after = page.evaluate(SNAP_JS, [it['id'], MSG_SEL])
            reqs = rec.reqs[nr:]
            r.update(filled=filled, requests=[{k: q[k] for k in ('method', 'host', 'path', 'action', 'keys', 'has_file', 'query')} for q in reqs],
                     dialogs=ev['dialogs'][nd:], popups=ev['popups'][npop:], errors=ev['errors'][ne:], file_chosen=ev['choosers'] - nch,
                     messages=[m for m in after['msgs'] if m not in before['msgs']][:4])
            changed = before['box'] != after['box'] or before['open'] != after['open'] or before['bodyLen'] != after['bodyLen']
            if r['errors']: r['verdict'] = 'ошибка страницы'
            elif reqs or r['popups'] or r['dialogs'] or r['file_chosen']: r['verdict'] = 'работает'
            elif r['messages'] or changed: r['verdict'] = 'отвечает на экране'
            else: r['verdict'] = 'нет реакции'
            results.append(r)
            if urlparse(page.url).path != '/__cab.html':
                boot()
    ctx.close(); browser.close()
    return {'scenario': 'cabinet-' + device, 'path': '/owner', 'device': device, 'mode': 'staff', 'actions': results,
            'requests_total': len(rec.reqs), 'elapsed_s': round(time.time() - start), 'errors': ev['errors'][:30]}


def main():
    if '--list' in sys.argv:
        print('\n'.join(SCENARIOS)); return 0
    want = [a for a in sys.argv[1:] if a in SCENARIOS] or list(SCENARIOS)
    from playwright.sync_api import sync_playwright
    tok = cab_check.token()
    data = cab_check.fetch_data(tok) if tok else {'ok': True, 'owner': {'name': 'Тест', 'is_staff': True}, 'properties': [], 'totals': {}}
    jpg, pdf = make_files()
    srv = cab_check.serve(cab_check.build_page().replace('setTimeout(function(){\n  var q = new URLSearchParams', 'if(false)setTimeout(function(){\n  var q = new URLSearchParams'), data)
    report = {'started': time.strftime('%Y-%m-%d %H:%M'), 'scenarios': []}
    try:
        with sync_playwright() as pw:
            for name in want:
                t0 = time.time()
                try:
                    r = run_cabinet(pw, data, jpg, pdf, device=SCENARIOS[name][1]) if name.startswith('cabinet') else run_scenario(pw, name, data, jpg, pdf)
                except Exception as e:
                    r = {'scenario': name, 'fatal': str(e)[:300], 'actions': []}
                report['scenarios'].append(r)
                v = {}
                for a in r.get('actions', []):
                    v[a.get('verdict')] = v.get(a.get('verdict'), 0) + 1
                print('%-22s %4ds  действий %3d  %s' % (name, time.time() - t0, len(r.get('actions', [])), v), flush=True)
                json.dump(report, open(OUT, 'w'), ensure_ascii=False, indent=1)
    finally:
        srv.shutdown()
    print('отчёт:', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
