#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сквозные сценарии «как человек»: от первого нажатия до отправки — и сверка, что ушло.

Эльнур 15.09.2026: «нажать, заполнить, отправить, сверить, принять, отменить, забронировать,
получить оффер, загрузить документ». Каждый сценарий идёт по шагам, в конце проверяет:
ушёл ли нужный запрос (куда и с каким действием/полями) и что увидел посетитель.

🔒 Наружу ничего не уходит: запросы перехватываются (tools/flow_audit.Recorder).
Телефон в формах — тестовый номер Эльнура, имя «ТЕСТ Claude».

    python3 tools/journeys.py            # сайт (компьютер и телефон) + кабинет → /tmp/plp_journeys.json
"""
import json, os, re, sys, time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cab_check, flow_audit  # noqa: E402

cab_check.PORT = int(os.environ.get('AUDIT_PORT', 8805))
BASE = 'http://127.0.0.1:%d' % cab_check.PORT
OUT = os.environ.get('JOURNEYS_OUT', '/tmp/plp_journeys.json')
PHONE, NAME = '+66954143874', 'ТЕСТ Claude'


class J:
    def __init__(self, pw, data, device, jpg, pdf):
        self.data, self.device, self.jpg, self.pdf = data, device, jpg, pdf
        self.browser = pw.chromium.launch(channel='chrome', headless=True)
        self.ctx = (self.browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='ru-RU')
                    if device == 'mobile' else self.browser.new_context(viewport={'width': 1400, 'height': 900}, locale='ru-RU'))
        self.rec = flow_audit.Recorder(data)
        self.ctx.route('**/*', self.rec.handle)
        self.popups, self.dialogs, self.errors = [], [], []
        self.opening = False
        def on_page(p):
            if self.opening:   # страницу открывает сам сценарий — не трогаем
                return
            self.popups.append(p.url)
            try: p.close()
            except Exception: pass
        self.ctx.on('page', on_page)
        self.results = []

    def page(self, path, staff=False):
        self.opening = True
        pg = self.ctx.new_page()
        self.opening = False
        pg.on('dialog', lambda d: (self.dialogs.append(d.message[:100]), d.accept()))
        pg.on('pageerror', lambda e: self.errors.append(str(e)[:150]))
        pg.on('filechooser', lambda fc: fc.set_files(self.jpg))
        pg.goto(BASE + path, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(2200)
        if staff:
            pg.evaluate("() => { try { localStorage.setItem('plp_owner_sel', JSON.stringify(['PLP-DEMO'])); } catch(e){} }")
            pg.evaluate("(d) => window.__cabDemo(d)", self.data)
            pg.wait_for_timeout(1200)
        pg.add_style_tag(content='*{transition:none!important;animation:none!important}.reveal{opacity:1!important;transform:none!important}')
        return pg

    def run(self, name, fn, expect=None, where=''):
        n_req, n_pop, n_dlg, n_err = len(self.rec.reqs), len(self.popups), len(self.dialogs), len(self.errors)
        note, seen_text = '', ''
        try:
            seen_text = fn() or ''
            status = 'ok'
        except Exception as e:
            status, note = 'сбой шага', str(e).split('\n')[0][:160]
        reqs = [{k: r[k] for k in ('method', 'host', 'path', 'action', 'keys', 'has_file')} for r in self.rec.reqs[n_req:]
                if not r['path'].startswith('/siteevents')]
        hit = None
        if expect and status == 'ok':
            hit = next((r for r in reqs if re.search(expect, (r['path'] or '') + ' ' + (r['action'] or ''))), None)
            if not hit:
                status, note = 'не ушёл запрос', 'ждали: ' + expect
        errs = self.errors[n_err:]
        if errs and status == 'ok':
            status, note = 'ошибка страницы', errs[0]
        self.results.append({'name': name, 'device': self.device, 'where': where, 'status': status, 'note': note,
                             'requests': reqs, 'popups': self.popups[n_pop:], 'dialogs': self.dialogs[n_dlg:],
                             'visitor_sees': (seen_text or '')[:220], 'errors': errs[:3]})
        print('  %-3s %-9s %-44s %s %s' % ('✓' if status == 'ok' else '✗', self.device, name[:44], status if status != 'ok' else '', [(r['path'][-18:], r['action']) for r in reqs][:3]), flush=True)

    def close(self):
        self.ctx.close(); self.browser.close()


def txt(pg, sel):
    try:
        return pg.locator(sel).last.inner_text(timeout=1500).replace('\n', ' ').strip()
    except Exception:
        return ''


def site(j):
    pg = j.page('/index.html')

    def quiz():
        pg.evaluate("() => openQuiz()"); pg.wait_for_timeout(400)
        for _ in range(14):   # выбор ответа сам переводит на следующий шаг
            if pg.locator('#qzSend').count():
                break
            pg.locator('#qzBody .qz-opt').first.click(); pg.wait_for_timeout(450)
        pg.fill('#qzName', NAME); pg.fill('#qzContact', PHONE); pg.check('#qzOk')
        pg.wait_for_timeout(1700)
        pg.locator('#qzSend').click(); pg.wait_for_timeout(1500)
        return txt(pg, '#qzBody')
    j.run('Квиз: 8 шагов → контакт → отправить', quiz, expect=r'site-lead', where='Подбор за 10 минут')
    pg.evaluate("() => { try { closeQuiz(); } catch(e){} }")

    def chat_message():
        pg.evaluate("() => openChat()"); pg.wait_for_timeout(2500)
        pg.fill('#chatField', 'Что купить на 5 млн бат?'); pg.press('#chatField', 'Enter')
        pg.wait_for_timeout(2500)
        return txt(pg, '#chatwin .msg.bot')
    j.run('Чат: вопрос консультанту → ответ', chat_message, expect=r'site-chat', where='Чат «Дарья»')

    def chat_lead():
        # как человек: в меню чата «Оставить контакт — соберём подборку»
        pg.evaluate("() => { const b=[...document.querySelectorAll('#chatwin button')].filter(x=>x.offsetParent).find(x=>/оставить контакт/i.test(x.textContent)); if(!b) throw new Error('в меню чата нет «Оставить контакт»'); b.click(); }")
        pg.wait_for_timeout(700)
        f = pg.locator('#chatwin .leadform').last
        f.wait_for(state='visible', timeout=8000)
        f.locator('.lf-goal').select_option(index=1); f.locator('.lf-budget').select_option(index=1)
        f.locator('.lf-name').fill(NAME); f.locator('.lf-phone').fill(PHONE); f.locator('.lf-ok').check()
        pg.wait_for_timeout(1700); f.locator('.send').click(); pg.wait_for_timeout(1800)
        return txt(pg, '#chatwin .msg')
    j.run('Заявка в чате: цель, бюджет, имя, телефон → отправить', chat_lead, expect=r'site-lead', where='Чат «Дарья»')

    def catalog():
        pg.evaluate("() => { const b=[...document.querySelectorAll('button')].find(x=>/Получить каталог/.test(x.textContent)); b.scrollIntoView(); b.click(); }")
        pg.wait_for_timeout(2600)
        opened = pg.evaluate("() => document.getElementById('chatwin').classList.contains('open')")
        return ('чат открыт: ' if opened else 'чат НЕ открыт: ') + txt(pg, '#chatwin .msg.bot')
    j.run('«Получить каталог» → чат с запросом каталога', catalog, where='Каталог PDF')

    def prop_offer():
        pg.evaluate("() => { try { closeChat && closeChat(); } catch(e){} document.getElementById('chatwin').classList.remove('open'); }")
        pg.evaluate("() => { const c=document.querySelector('#saleCar .prop'); c.scrollIntoView({block:'center'}); c.click(); }")
        pg.wait_for_timeout(1500)
        btns = pg.evaluate("() => [...document.querySelectorAll('.modal-overlay.open button, .modal-overlay.open a')].map(b => (b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean).slice(0,40)")
        target = next((b for b in btns if re.search(r'КП|оффер|предложени|расчёт|рассчит', b, re.I)), None)
        if not target:
            return 'кнопок оффера нет; в карточке: ' + ', '.join(btns[:20])
        pg.evaluate("(t) => [...document.querySelectorAll('.modal-overlay.open button, .modal-overlay.open a')].find(b => (b.innerText||'').trim()===t).click()", target)
        pg.wait_for_timeout(2500)
        return 'нажато «%s»; окна: %s; чат: %s' % (target, j.popups[-1:] or '—', txt(pg, '#chatwin .msg.bot'))
    j.run('Карточка объекта → «Получить КП / оффер»', prop_offer, where='Продажа → карточка')

    def fav_compare():
        pg.evaluate("() => document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'))")
        pg.evaluate("() => { const f=[...document.querySelectorAll('#saleCar .prop .fav')].slice(0,2); f.forEach(x=>x.click()); const c=[...document.querySelectorAll('#saleCar .prop .cmpb')].slice(0,2); c.forEach(x=>x.click()); }")
        pg.wait_for_timeout(600)
        tray = txt(pg, '#tray')
        pg.evaluate("() => { try { openCompare(); } catch(e){ throw e; } }"); pg.wait_for_timeout(900)
        cmp_open = pg.evaluate("() => !!document.querySelector('.modal-overlay.open, #compareModal.open, .cmpmodal.open')")
        return 'полоса: %s · сравнение открыто: %s' % (tray[:80], cmp_open)
    j.run('Избранное ×2 и сравнение ×2 → окно сравнения', fav_compare, where='Продажа')

    def fav_lead():
        pg.evaluate("() => document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'))")
        pg.goto(BASE + '/index.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2200)
        # избранное помнится между заходами: жмём сердечки, пока в полосе не появится «Подборка»
        for _ in range(3):
            if pg.evaluate("() => [...document.querySelectorAll('#tray button')].some(x=>x.offsetParent && /подборк/i.test(x.textContent))"):
                break
            pg.evaluate("() => { [...document.querySelectorAll('#saleCar .prop .fav:not(.on)')].slice(0,2).forEach(x=>x.click()); }"); pg.wait_for_timeout(400)
        pg.evaluate("() => { const b=document.querySelector('#tray .t-fav'); if(!b || !b.offsetParent) throw new Error('на полосе избранного нет кнопки подборки'); b.click(); }")
        pg.wait_for_timeout(2600)
        f = pg.locator('#chatwin .leadform').last
        f.locator('.lf-goal').select_option(index=1); f.locator('.lf-budget').select_option(index=1)
        f.locator('.lf-name').fill(NAME); f.locator('.lf-phone').fill(PHONE); f.locator('.lf-ok').check()
        pg.wait_for_timeout(1700); f.locator('.send').click(); pg.wait_for_timeout(1500)
        return txt(pg, '#chatwin .msg')
    j.run('Подборка из избранного → контакт → отправить', fav_lead, expect=r'site-lead', where='Полоса избранного')

    def rent_avail():
        pg.evaluate("() => { const i=document.getElementById('rentIn'), o=document.getElementById('rentOut'); const d=n=>new Date(Date.now()+n*864e5).toISOString().slice(0,10); i.value=d(10); o.value=d(14); checkAvailability(); }")
        pg.wait_for_timeout(1500)
        return txt(pg, '#rent .dstatus, #rentDateStatus, #rent .rent-dates')
    j.run('Аренда: даты → «Показать свободные»', rent_avail, expect=r'check-availability', where='Аренда')

    def rent_request():
        # свежая страница: у одной вкладки форма контакта показывается один раз за визит
        pg.goto(BASE + '/index.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2200)
        pg.evaluate("() => { const b=[...document.querySelectorAll('#rent button')].find(x=>/Оставить запрос/.test(x.textContent)); b.scrollIntoView(); b.click(); }")
        pg.wait_for_timeout(5200)
        f = pg.locator('#chatwin .leadform').last
        f.wait_for(state='visible', timeout=8000)
        f.locator('.lf-goal').select_option(index=1); f.locator('.lf-budget').select_option(index=1)
        f.locator('.lf-name').fill(NAME); f.locator('.lf-phone').fill(PHONE); f.locator('.lf-ok').check()
        pg.wait_for_timeout(1700); f.locator('.send').click(); pg.wait_for_timeout(1800)
        return txt(pg, '#chatwin .msg')
    j.run('Аренда: «Оставить запрос» → контакт → отправить', rent_request, expect=r'site-lead', where='Аренда')

    def service():
        pg.goto(BASE + '/about.html', wait_until='domcontentloaded'); pg.wait_for_timeout(2200)   # блок «Сервис» живёт на /about
        pg.evaluate("() => { const b=[...document.querySelectorAll('button, .srv-card, a')].find(x=>/Трансфер на просмотр/.test(x.textContent)); if(!b) throw new Error('на /about нет «Трансфер на просмотр»'); b.scrollIntoView(); b.click(); }")
        pg.wait_for_timeout(1500)
        f = pg.locator('#chatwin .leadform').last
        f.wait_for(state='visible', timeout=8000)
        f.locator('.lf-goal').select_option(index=1); f.locator('.lf-budget').select_option(index=1)
        f.locator('.lf-name').fill(NAME); f.locator('.lf-phone').fill(PHONE); f.locator('.lf-ok').check()
        pg.wait_for_timeout(1700); f.locator('.send').click(); pg.wait_for_timeout(1800)
        return txt(pg, '#chatwin .msg')
    j.run('Услуга «Трансфер на просмотр» → контакт → отправить', service, expect=r'site-lead', where='О нас · Сервис')
    pg.close()


def add_property(j):
    pg = j.page('/add-property.html')

    def flow():
        def chip(box):
            pg.evaluate("(id) => { const c=document.querySelector('#'+id+' .chipf'); if(c && !c.classList.contains('on')) c.click(); }", box)
        def nxt():
            pg.click('#ap-next'); pg.wait_for_timeout(900)
            err = txt(pg, '#ap-err')
            if err: raise RuntimeError('шаг не пропустил: ' + err)
        for b in ('ap-kind', 'ap-beds', 'ap-area'): chip(b)
        pg.fill('#ap-area-sqm', '120'); nxt()                                   # 1 · Объект
        for b in ('ap-stage', 'ap-goal'): chip(b)
        pg.fill('#ap-price', '9000000'); nxt()                                  # 2 · Условия
        pg.set_input_files('#ap-files', j.jpg); pg.wait_for_timeout(1800); nxt()  # 3 · Фото
        pg.fill('#ap-address', 'ТЕСТ обход кнопок'); pg.fill('#ap-desc', 'ТЕСТ — не обрабатывать'); nxt()  # 4 · Описание
        pg.fill('#ap-name', NAME); pg.fill('#ap-phone', PHONE); chip('ap-via')    # 5 · Контакты
        pg.click('#ap-next'); pg.wait_for_timeout(2500)
        return txt(pg, '#ap-ok') or txt(pg, '#ap-err')
    j.run('Разместить объект: 5 шагов, фото, контакт → отправить', flow, expect=r'submit_object', where='Анкета собственника')
    pg.close()


def cabinet(j):
    pg = j.page('/__cab.html', staff=True)

    def tab(t):
        pg.evaluate("(t) => { const a=document.querySelector('#cab-nav a[data-tab=\"'+t+'\"]'); const b=document.getElementById('cab-body'); if (b.hidden || !a.classList.contains('on')) a.click(); document.querySelectorAll('#cab-body .foldh').forEach(h => { const i=h.querySelector('.foldi'); if (i && i.textContent.trim()==='+') h.click(); }); }", t)
        pg.wait_for_timeout(400)

    def form_via(t, button_re, save_re=r'сохран|внести|добав|постав|отправ|создат|записать|собрать', upload=False):
        def go():
            tab(t)
            label = pg.evaluate("""([re]) => { const r=new RegExp(re,'i');
                const secs=[...document.getElementById('cab-body').children].filter(e=>e.style.display!=='none' && !e.hidden);
                const all=[]; secs.forEach(sec => sec.querySelectorAll('summary, button, .lnk, a[href="#"], [data-uk]').forEach(x => all.push(x)));
                const b=all.find(x=>r.test(x.textContent||''));
                if(!b) return '';
                const fold=b.closest('.card.fold'); if(fold && !fold.classList.contains('open')) fold.querySelector(':scope > .foldh').click();
                b.scrollIntoView({block:'center'}); b.click(); return (b.textContent||'').trim(); }""", [button_re])
            if not label:
                raise RuntimeError('нет кнопки /%s/ в разделе %s' % (button_re, t))
            pg.wait_for_timeout(600)
            if upload:
                files = pg.locator('#cl-form input[type=file], #cab-body input[type=file]')
                if files.count():
                    files.first.set_input_files(j.pdf)
                    pg.wait_for_timeout(1500)
            # выпадающие списки в форме заявки: берём первый пункт
            pg.evaluate("""() => { const scope=document.getElementById('cl-form').innerHTML.length>20 ? document.getElementById('cl-form') : document.getElementById('cab-body');
                scope.querySelectorAll('.picker').forEach(pk => { if (!pk.offsetParent) return; const v=pk.querySelector('.pickval');
                  if (v && !v.classList.contains('dim')) return; pk.querySelector('.pickbtn').click(); const it=pk.querySelector('.pickitem'); if (it) it.click(); }); }""")
            if pg.evaluate("() => (document.getElementById('cl-form')||{}).innerHTML.length > 20"):
                pg.evaluate(flow_audit.FILL_JS.replace("const el = document.querySelector('[data-audit-id=\"' + id + '\"]');\n  if (!el) return 0;", "const el = document.getElementById('cl-form');"), 'x')
                saved = pg.evaluate("([re]) => { const r=new RegExp(re,'i'); const f=document.getElementById('cl-form'); const b=[...f.querySelectorAll('button')].filter(x=>x.offsetParent && !/отмен|закры/i.test(x.textContent)).find(x=>r.test(x.textContent)) || f.querySelector('#f-save'); if(!b) return ''; b.click(); return b.textContent.trim(); }", [save_re])
                pg.wait_for_timeout(1200)
                msg = txt(pg, '#say, .say, .toast')
                pg.evaluate("() => { const c=document.getElementById('f-cancel'); if(c) c.click(); }")
                return 'кнопка «%s» → «%s» · %s' % (label, saved, msg)
            if re.search(r'развернуть', label, re.I):
                pg.evaluate(flow_audit.FILL_JS.replace("const el = document.querySelector('[data-audit-id=\"' + id + '\"]');\n  if (!el) return 0;", "const el = [...document.querySelectorAll('#cab-body details[open]')].pop() || document.getElementById('cab-body');"), 'x')
                saved = pg.evaluate("([re]) => { const r=new RegExp(re,'i'); const d=[...document.querySelectorAll('#cab-body details[open]')].pop(); if(!d) return ''; const b=[...d.querySelectorAll('button')].filter(x=>x.offsetParent).find(x=>r.test(x.textContent)); if(!b) return ''; b.click(); return b.textContent.trim(); }", [save_re])
                pg.wait_for_timeout(1200)
                return 'раскрыто «%s» → «%s» · %s' % (label, saved, txt(pg, '#say, .say, .toast'))
            return 'кнопка «%s» · %s' % (label, txt(pg, '#say, .say, .toast'))
        return go

    j.run('Бронирования: новая бронь → сохранить', form_via('calendar', r'бронь|добав|заезд|нажми'), expect=r'uk_booking_save', where='Кабинет · Бронирования')
    j.run('Финансы: внести операцию → сохранить', form_via('money', r'внести операц'), expect=r'uk_tx', where='Кабинет · Финансы')
    j.run('Расходы: изменить ставки → сохранить', form_via('costs', r'измен|заполн|правк|ставк'), expect=r'uk_costs_update', where='Кабинет · Расходы')
    j.run('Документы: загрузить файл', form_via('docs', r'загрузить документ', upload=True), expect=r'uk_doc_file|my_doc', where='Кабинет · Документы')
    j.run('Обслуживание: поставить работу → сохранить', form_via('service', r'поставить работу'), expect=r'uk_task', where='Кабинет · Обслуживание')
    def request_new():
        tab('actions')
        pg.evaluate("() => { const d=document.querySelector('#sec-request details, #sec-request'); if (d && d.tagName==='DETAILS') d.open=true; }")
        pg.wait_for_timeout(300)
        # «что нужно»: не бронь (для брони обязательны даты)
        pg.evaluate("""() => { const pks=[...document.querySelectorAll('#sec-request .picker')].filter(p=>p.offsetParent);
            pks.forEach((pk, i) => { pk.querySelector('.pickbtn').click(); const items=[...pk.querySelectorAll('.pickitem')];
              const v=pk.querySelector('.pickval'); if (v && !v.classList.contains('dim')) { pk.querySelector('.pickbtn').click(); return; }
            const it = items.find(x => !/брон/i.test(x.textContent)) || items[0]; if (it) it.click(); }); }""")
        obj = pg.evaluate("() => (document.querySelector('#r-obj .pickval')||{}).textContent")
        pg.evaluate("() => { const t=document.getElementById('r-details'); if (t) t.value='ТЕСТ обход кнопок — не обрабатывать'; }")
        st = pg.evaluate("""() => { const b=document.getElementById('r-send'); const r=b.getBoundingClientRect();
            const d=b.closest('details'); const info={disabled:b.disabled, w:r.width, h:r.height, details_open: d ? d.open : null,
              kinds:[...document.querySelectorAll('#sec-request .pickval')].map(v=>v.textContent)};
            b.scrollIntoView({block:'center'}); b.click(); return info; }""")
        pg.wait_for_timeout(1200)
        return 'объект в форме по умолчанию: %s · %s' % (obj, txt(pg, '#r-ok') or txt(pg, '#r-err'))
    j.run('Заявки: оставить заявку → отправить', request_new, expect=r'request_new', where='Кабинет · Заявки')

    def object_save():
        tab('object')
        pg.evaluate("() => { const d=document.querySelector('#sec-objedit details, #sec-objedit'); if (d && d.tagName==='DETAILS') d.open=true; document.querySelectorAll('#sec-objedit details').forEach(x=>x.open=true); }")
        pg.wait_for_timeout(400)
        # меняем одно поле, иначе кабинет честно отвечает «Ничего не изменилось» и не шлёт пустое сохранение
        pg.evaluate("""() => { const f=[...document.querySelectorAll('#oe-body input[type=text], #oe-body input:not([type]), #oe-body textarea')].find(x=>x.offsetParent);
            if (f) { f.value = (f.value||'') + ' (тест)'; f.dispatchEvent(new Event('input',{bubbles:true})); f.dispatchEvent(new Event('change',{bubbles:true})); }
            const b=document.getElementById('oe-save'); if(!b) throw new Error('нет кнопки «Сохранить» в карточке объекта'); b.scrollIntoView(); b.click(); }""")
        pg.wait_for_timeout(1200)
        return txt(pg, '#sec-objedit .sub, #say, .say')
    j.run('Объект: карточка → сохранить', object_save, expect=r'object_edit|save_object', where='Кабинет · Объект')

    def report():
        tab('docs')
        pg.evaluate("() => { const a=document.querySelector('#sec-reports [data-rep]'); a.click(); }")
        pg.wait_for_timeout(1200)
        return 'окна: %s' % (j.popups[-1:] or '—')
    j.run('Документы: отчёт → «Открыть и распечатать»', report, where='Кабинет · Документы')
    pg.close()

    lg = j.page('/owner.html')

    def login():
        lg.fill('#login', '954143874'); lg.click('#send-code'); lg.wait_for_timeout(900)
        lg.fill('#code', '123456'); lg.click('#check-code'); lg.wait_for_timeout(2500)
        return 'кабинет открыт' if lg.evaluate("() => document.getElementById('app').style.display !== 'none'") else txt(lg, '#gate-err')
    j.run('Вход: номер → код → кабинет', login, expect=r'verify_code', where='Кабинет · вход')
    lg.close()


def main():
    from playwright.sync_api import sync_playwright
    tok = cab_check.token()
    data = cab_check.fetch_data(tok)
    jpg, pdf = flow_audit.make_files()
    srv = cab_check.serve(cab_check.build_page(stub=False).replace('setTimeout(function(){\n  var q = new URLSearchParams', 'if(false)setTimeout(function(){\n  var q = new URLSearchParams'), data)
    out = []
    try:
        with sync_playwright() as pw:
            for device in ('desktop', 'mobile'):
                j = J(pw, data, device, jpg, pdf)
                print('== сайт,', device); site(j)
                if device == 'desktop':
                    print('== анкета'); add_property(j)
                print('== кабинет,', device); cabinet(j)
                out += j.results; j.close()
    finally:
        srv.shutdown()
    json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
    bad = [r for r in out if r['status'] != 'ok']
    print('сценариев %d, не прошли %d → %s' % (len(out), len(bad), OUT))


if __name__ == '__main__':
    main()
