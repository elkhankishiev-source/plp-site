#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перепись собственников для отдела продаж: кто, чем владеет, как связаться.

Эльнур 23.09.2026: «дай мне новый файл в тг чат плп продажи для дарьи, тегни её».
Прошлый файл от 23.09 устарел в тот же день: в нём Bayside 2205 стоял за
Александром, а покупки не было — он её отменил.

Что внутри и чего нет:
  • есть: код клиента, как с ним связаться, его юниты, стадия, срок передачи,
    цена покупки по ДОГОВОРУ (не по полю сделки в CRM — оно врёт, см. Katabello);
  • нет: сумм, которые собственник хочет «на руки», и любых его личных
    договорённостей. Это внутренняя кухня продавца, а не справочник.
  • юнит зовётся своим кодом PLP-… — по нему он одинаково ищется в базе,
    в кабинете и в CRM.

    python3 tools/census_owners.py                     # собрать файл
    python3 tools/census_owners.py --послать --го      # собрать и отправить в отдел продаж
"""
import datetime, html, json, os, sys, urllib.parse, urllib.request

ПОСЛАТЬ = '--послать' in sys.argv and '--го' in sys.argv
# 🔴 Файл НЕ кладём внутрь ~/plp-site: этот каталог — открытый репозиторий
# GitHub Pages, а здесь имена, телефоны и цены клиентов. Мы уже налетали на это
# с units_owners.json. Место файла — вне репозитория.
ВЫХОД = os.path.expanduser('~/PLP-выгрузки/перепись_собственников.html')


def env():
    out = {}
    for путь in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env'):
        if not os.path.exists(путь):
            continue
        for ln in open(путь, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1)
                out.setdefault(k, v.strip().strip('"\''))
        if out.get('SUPABASE_URL'):
            break
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def sb(path):
    """Читаем ВСЁ, а не первую тысячу.

    23.09.2026: Supabase отдаёт максимум 1000 строк за раз. В базе около четырёх
    с половиной тысяч карточек, и Александр с девятью юнитами в первую тысячу
    не попал — в переписи он оказался без имени и без кода. На эти же грабли
    мы уже наступали в amo_dialog_notes.py. Листаем страницами."""
    из, шаг, всё = 0, 1000, []
    while True:
        r = urllib.request.Request(BASE + path, headers=dict(H, Range='%d-%d' % (из, из + шаг - 1)))
        with urllib.request.urlopen(r, timeout=120) as f:
            кусок = json.loads(f.read().decode())
        всё += кусок
        if len(кусок) < шаг:
            return всё
        из += шаг


def e(s):
    return html.escape(str(s if s is not None else ''))


def деньги(v):
    if not v:
        return ''
    return '{:,.0f}'.format(float(v)).replace(',', ' ') + ' ฿'


def дата(d):
    if not d:
        return ''
    try:
        y, m, dd = str(d)[:10].split('-')
        return '%s.%s.%s' % (dd, m, y)
    except Exception:
        return str(d)[:10]


МЕСЯЦЫ = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
          'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']


def собрать():
    люди = {c['client_id']: c for c in sb('/clients?select=client_id,code,name,phone,tg_id,email,notes')}
    юниты = sb('/client_objects?rel=in.(owns,spouse)&select=client_id,plp_property_id,project_name,'
               'unit,rel,stage,uk_status,purchase_price,handover_on,next_payment_on,'
               'next_payment_amount,note&order=plp_property_id')
    объекты = {o['plp_property_id']: o for o in
               sb('/objects?select=plp_property_id,type,district,area_sqm,bedrooms,'
                  'plot_area_sqm,built_area_sqm,handover_date,name')}
    по_людям = {}
    for u in юниты:
        по_людям.setdefault(u['client_id'], []).append(u)
    return люди, по_людям, объекты


РАЙОН = {'Bang Tao': 'Банг Тао', 'Layan': 'Лаян', 'Kata': 'Ката', 'Surin': 'Сурин',
         'Nai Yang': 'Най Янг', 'Kamala': 'Камала', 'Rawai': 'Равай', 'Koh Kaew': 'Ко Кео'}


def площадь(o):
    """У виллы два числа — дом и участок. У квартиры одно."""
    if not o:
        return ''
    вилла = 'вилл' in str(o.get('type') or '').lower()
    дом, уч = o.get('built_area_sqm'), o.get('plot_area_sqm')
    if вилла and дом and уч:
        return '%s м² дом · %s м² участок' % (дом, уч)
    a = o.get('area_sqm')
    if not a:
        return ''
    return str(a).rstrip('0').rstrip('.') + ' м²' if '.' in str(a) else str(a) + ' м²'


def main():
    люди, по_людям, объекты = собрать()
    сегодня = datetime.date.today()
    подпись = '%d %s %d' % (сегодня.day, МЕСЯЦЫ[сегодня.month - 1], сегодня.year)

    строки, всего_юнитов = [], 0
    for cid, список in sorted(по_людям.items(),
                              key=lambda kv: str(люди.get(kv[0], {}).get('name') or 'я')):
        ч = люди.get(cid) or {}
        связь = []
        if ч.get('phone'):
            связь.append('+' + str(ч['phone']))
        if ч.get('tg_id'):
            связь.append('Telegram есть')
        if ч.get('email'):
            связь.append(e(ч['email']))
        карточки = []
        for u in sorted(список, key=lambda x: x['plp_property_id'] or ''):
            всего_юнитов += 1
            o = объекты.get(u['plp_property_id']) or {}
            факты = []
            if o.get('district'):
                факты.append(РАЙОН.get(o['district'], o['district']))
            if o.get('type'):
                факты.append(o['type'])
            пл = площадь(o)
            if пл:
                факты.append(пл)
            if o.get('bedrooms'):
                факты.append(str(o['bedrooms']) + ' спальни')
            хвост = []
            if u.get('stage'):
                хвост.append(u['stage'])
            if u.get('handover_on'):
                хвост.append('передача ' + дата(u['handover_on']))
            if u.get('purchase_price'):
                хвост.append('покупка ' + деньги(u['purchase_price']))
            if u.get('next_payment_on'):
                хвост.append('ближайший платёж ' + дата(u['next_payment_on']) +
                             (' — ' + деньги(u['next_payment_amount']) if u.get('next_payment_amount') else ''))
            if u.get('uk_status'):
                хвост.append('УК: ' + u['uk_status'])
            заметка = str(u.get('note') or '').split('\n')[0][:150]
            карточки.append(
                '<li><b>%s</b>%s<div class="f">%s</div>%s%s</li>'
                % (e(u['plp_property_id']),
                   ' <span class="sp">супруг(а)</span>' if u.get('rel') == 'spouse' else '',
                   e(' · '.join(факты)) or '<i>данных по объекту нет</i>',
                   ('<div class="h">' + e(' · '.join(хвост)) + '</div>') if хвост else '',
                   ('<div class="n">' + e(заметка) + '</div>') if заметка else ''))
        строки.append(
            '<section><h2>%s <span class="code">%s</span></h2>'
            '<div class="c">%s</div><ul>%s</ul></section>'
            % (e(ч.get('name') or '—'), e(ч.get('code') or ''),
               e(' · '.join(связь)) or '<i>связи в карточке нет</i>', ''.join(карточки)))

    html_out = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Собственники PLP</title>
<style>
:root{--ink:#17180F;--muted:#6B6F60;--bg:#EFECE2;--card:#fff;--line:#DCDACB;--olive:#5E6B35;--rust:#B4533A}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
 --ink:#ECEADF;--muted:#8E9183;--bg:#15160F;--card:#1E2017;--line:#31341F;--olive:#A8B478;--rust:#D97A5E}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:16px/1.55 -apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.w{max-width:760px;margin:0 auto;padding:22px 16px 70px}
h1{font-size:25px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:14px;margin-bottom:6px}
.note{background:var(--card);border-left:3px solid var(--rust);padding:10px 12px;
 border-radius:0 8px 8px 0;font-size:14px;margin:14px 0 20px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;
 padding:14px 15px;margin:0 0 12px}
h2{font-size:17px;margin:0 0 3px;font-weight:700}
.code{color:var(--muted);font-weight:400;font-size:13px;margin-left:5px}
.c{color:var(--muted);font-size:13.5px;margin-bottom:9px}
ul{list-style:none;margin:0;padding:0}
li{border-top:1px solid var(--line);padding:9px 0 7px}
li:first-child{border-top:0;padding-top:2px}
li b{font-size:14.5px;letter-spacing:.01em}
.sp{font-size:11.5px;color:#fff;background:var(--olive);border-radius:20px;padding:1px 8px;margin-left:5px}
.f{font-size:14px;margin-top:2px}
.h{font-size:13.5px;color:var(--olive);margin-top:3px}
.n{font-size:13px;color:var(--muted);margin-top:4px}
i{color:var(--muted)}
</style></head><body><div class="w">
<h1>Собственники PLP</h1>
<div class="sub">%d человек · %d объектов · собрано %s</div>
<div class="note">Юнит зовётся своим кодом <b>PLP-…</b> — по нему он ищется одинаково
в базе, в кабинете собственника и в CRM. Цена покупки взята из договора, а не из поля
сделки в CRM: поле там расходится с договором. Личные договорённости собственников
о продаже в файл не выносим.</div>
%s
</div></body></html>""" % (len(по_людям), всего_юнитов, подпись, '\n'.join(строки))

    os.makedirs(os.path.dirname(ВЫХОД), exist_ok=True)
    open(ВЫХОД, 'w', encoding='utf-8').write(html_out)
    print('собрано: %d человек, %d объектов' % (len(по_людям), всего_юнитов))
    print('файл: %s (%.0f КБ)' % (ВЫХОД, os.path.getsize(ВЫХОД) / 1024))
    if not ПОСЛАТЬ:
        print('\nНаружу не отправлял. Отправить в отдел продаж: --послать --го')
    return ВЫХОД, len(по_людям), всего_юнитов


def отправить(путь, людей, юнитов):
    """В группу «PLP | отдел продаж» файлом, с обращением к Дарье.

    Отправляем ботом. Упоминание — ссылкой на её id: в группе это подсветится
    и придёт уведомлением, даже если у неё нет публичного @ника.
    """
    токен = open(os.path.expanduser('~/.plp_bot_elnurphuket_bot')).read().strip()
    чат = E.get('TG_ALERT_CHAT_ID') or os.environ.get('TG_ALERT_CHAT_ID')
    if not чат:
        raise SystemExit('не знаю id группы отдела продаж (TG_ALERT_CHAT_ID)')
    дарья = os.environ.get('DARIA_TG_ID', '8227351774')
    подпись = (
        '<a href="tg://user?id=%s">Дарья</a>, перепись собственников на сегодня.\n\n'
        '%d человек, %d объектов. Что изменилось против вчерашнего файла:\n'
        '• Bayside 2205 убран — Александр эту покупку отменил, её не было;\n'
        '• у Ayana F-607 появились цена, площадь и срок передачи из договора;\n'
        '• юниты названы своим кодом PLP-… — он одинаков в базе, в кабинете и в CRM.\n\n'
        'Дополни своими, чего не хватает, — и пришли обратно.' % (дарья, людей, юнитов))
    гр = '----------%s' % os.urandom(8).hex()
    части = []
    for имя, зн in (('chat_id', чат), ('caption', подпись), ('parse_mode', 'HTML')):
        части.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                      % (гр, имя, зн)).encode())
    части.append(('--%s\r\nContent-Disposition: form-data; name="document"; filename="%s"\r\n'
                  'Content-Type: text/html\r\n\r\n' % (гр, os.path.basename(путь))).encode())
    части.append(open(путь, 'rb').read())
    части.append(('\r\n--%s--\r\n' % гр).encode())
    тело = b''.join(части)
    r = urllib.request.Request('https://api.telegram.org/bot%s/sendDocument' % токен, data=тело,
                               headers={'Content-Type': 'multipart/form-data; boundary=%s' % гр})
    with urllib.request.urlopen(r, timeout=120) as f:
        ответ = json.loads(f.read().decode())
    print('отправлено в отдел продаж: %s' % ответ.get('ok'))
    return ответ


if __name__ == '__main__':
    путь, людей, юнитов = main()
    if ПОСЛАТЬ:
        отправить(путь, людей, юнитов)
