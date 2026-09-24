#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Список клиентов и их объектов — один лист, читаемый глазами.

Эльнур 24.09.2026: «отправишь список клиентов дополненный актуальный и красивый
легко читаемый».

Истина — Supabase: clients + client_objects. Никакого «вручную»: файл каждый раз
собирается заново, правка идёт в базу, а не в файл.

ВАЖНО ПРО МЕСТО. Здесь персональные данные: имена, телефоны, почты, суммы.
Репозиторий сайта ПУБЛИЧНЫЙ, поэтому файл кладётся в ~/PLP-выгрузки и туда же
не попадает ничего из git. Наружу этот лист не публикуется никогда.

    python3 tools/clients_report.py
"""

import datetime
import html
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ENV = os.path.expanduser('~/.plp_site_supabase.env')
ВЫХОД = os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.html')
PKT = ZoneInfo('Asia/Bangkok')


def creds():
    env = {}
    for line in open(ENV, encoding='utf-8'):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env['SUPABASE_URL'].rstrip('/'), env['SUPABASE_SERVICE_KEY']


def взять(путь):
    url, key = creds()
    r = urllib.request.Request(url + '/rest/v1/' + путь,
                               headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.load(urllib.request.urlopen(r, timeout=90))


def деньги(x):
    try:
        n = int(float(x))
    except Exception:
        return ''
    return '{:,}'.format(n).replace(',', ' ') + ' ฿'


def дата(x):
    if not x:
        return ''
    try:
        return datetime.date.fromisoformat(str(x)[:10]).strftime('%d.%m.%Y')
    except Exception:
        return str(x)[:10]


def главное():
    клиенты = {c['client_id']: c for c in взять(
        'clients?select=client_id,code,name,phone,email,cabinet_enabled,phone_status&limit=5000')}
    связки = взять('client_objects?select=client_id,object_id,unit,project_name,rel,stage,uk_status,'
                   'purchase_price,currency,bought_on,handover_on,next_payment_on,next_payment_amount,'
                   'handover_caveat&limit=2000')

    # у кого что: группируем по человеку
    по_людям = {}
    for с in связки:
        по_людям.setdefault(с['client_id'], []).append(с)

    строки = []
    for cid, юниты in по_людям.items():
        c = клиенты.get(cid) or {}
        строки.append((c.get('name') or '(без имени)', c, юниты))
    строки.sort(key=lambda x: x[0].lower())

    всего_юнитов = len(связки)
    с_ценой = sum(1 for с in связки if с.get('purchase_price'))
    сумма = sum(float(с['purchase_price']) for с in связки if с.get('purchase_price'))
    кабинет = sum(1 for _, c, _ in строки if c.get('cabinet_enabled'))
    бн = sum(1 for _, c, _ in строки if not (c.get('phone') or '').strip())

    РОЛЬ = {'owns': 'владелец', 'spouse': 'супруг(а)', 'lost': 'сделка не состоялась'}

    куски = []
    for имя, c, юниты in строки:
        конт = []
        if c.get('phone'):
            конт.append('+' + html.escape(str(c['phone'])))
        if c.get('email'):
            конт.append(html.escape(c['email']))
        мет = []
        if c.get('cabinet_enabled'):
            мет.append('<span class="м м-каб">кабинет открыт</span>')
        if not (c.get('phone') or '').strip():
            мет.append('<span class="м м-нет">нет телефона</span>')
        ряды = []
        for u in sorted(юниты, key=lambda x: (x.get('project_name') or '', x.get('unit') or '')):
            плохо = ' класс-плохо' if (u.get('rel') == 'lost' or (u.get('stage') or '') == 'расторгнут') else ''
            ряды.append(
                '<tr class="%s"><td class="пр">%s</td><td class="юн">%s</td>'
                '<td>%s</td><td class="ц">%s</td><td>%s</td><td>%s</td><td class="сост">%s</td></tr>' % (
                    плохо.strip(),
                    html.escape(u.get('project_name') or '—'),
                    html.escape(u.get('unit') or '—'),
                    html.escape(РОЛЬ.get(u.get('rel'), u.get('rel') or '')),
                    деньги(u.get('purchase_price')),
                    дата(u.get('bought_on')),
                    дата(u.get('handover_on')) + ('<span class="ог" title="срок со слов, не подтверждён документом">?</span>'
                                                  if u.get('handover_caveat') else ''),
                    html.escape(u.get('stage') or '')))
        куски.append(
            '<section class="чел"><header><h2>%s</h2><div class="код">%s</div>'
            '<div class="конт">%s</div><div class="меты">%s</div></header>'
            '<table><thead><tr><th>Проект</th><th>Юнит</th><th>Роль</th><th>Сумма</th>'
            '<th>Куплено</th><th>Передача</th><th>Состояние</th></tr></thead><tbody>%s</tbody></table>'
            '</section>' % (html.escape(имя), html.escape(c.get('code') or ''),
                            ' · '.join(конт) or '<i>контактов нет</i>',
                            ''.join(мет), ''.join(ряды)))

    сейчас = datetime.datetime.now(PKT).strftime('%d.%m.%Y, %H:%M по Пхукету')
    док = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Клиенты PLP</title>
<style>
:root{--фон:#faf8f4;--лист:#fff;--чернила:#23201b;--тихо:#7a7368;--рамка:#e7e1d6;--олива:#D2D5B3;--тревога:#8f4b3a}
*{box-sizing:border-box}
body{margin:0;background:var(--фон);color:var(--чернила);
 font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.обёртка{max-width:1080px;margin:0 auto;padding:32px 16px 72px}
h1{font-size:clamp(24px,3.4vw,34px);margin:0 0 6px;letter-spacing:-.02em}
.под{color:var(--тихо);margin:0 0 26px;font-size:.93rem}
.итоги{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 30px}
.итог{background:var(--лист);border:1px solid var(--рамка);border-radius:14px;padding:14px 16px}
.итог b{display:block;font-size:1.5rem;letter-spacing:-.02em}
.итог span{color:var(--тихо);font-size:.8rem}
.чел{background:var(--лист);border:1px solid var(--рамка);border-radius:16px;padding:18px 18px 8px;margin:0 0 14px}
.чел header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:12px}
.чел h2{font-size:1.12rem;margin:0;letter-spacing:-.01em}
.код{color:var(--тихо);font-size:.78rem;font-variant-numeric:tabular-nums}
.конт{color:var(--тихо);font-size:.84rem;flex:1 1 100%}
.меты{display:flex;gap:6px;flex-wrap:wrap}
.м{font-size:.72rem;padding:3px 9px;border-radius:999px;border:1px solid var(--рамка)}
.м-каб{background:var(--олива)}
.м-нет{color:var(--тревога);border-color:currentColor}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;font-weight:600;color:var(--тихо);font-size:.75rem;text-transform:uppercase;
 letter-spacing:.04em;padding:0 10px 6px 0;border-bottom:1px solid var(--рамка)}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--фон);vertical-align:top}
tr:last-child td{border-bottom:none}
.пр{font-weight:600}
.юн{font-variant-numeric:tabular-nums;color:var(--тихо)}
.ц{font-variant-numeric:tabular-nums;white-space:nowrap}
.сост{color:var(--тихо);font-size:.82rem}
.класс-плохо td{opacity:.55;text-decoration:line-through solid rgba(0,0,0,.25)}
.ог{display:inline-block;margin-left:4px;width:15px;height:15px;line-height:15px;text-align:center;
 border-radius:50%;background:var(--олива);font-size:.68rem;cursor:help;text-decoration:none}
footer{color:var(--тихо);font-size:.8rem;margin-top:28px;line-height:1.7}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--фон:#17150f;--лист:#1f1c16;
 --чернила:#efe9dd;--тихо:#9c948a;--рамка:#302b23}}
@media print{body{background:#fff}.чел{break-inside:avoid;box-shadow:none}}
</style></head><body><div class="обёртка">
<h1>Клиенты Property Library</h1>
<p class="под">Собрано из базы @СЕЙЧАС@. Файл пересобирается командой, вручную не правится.</p>
<div class="итоги">
 <div class="итог"><b>@ЛЮДЕЙ@</b><span>человек с объектом</span></div>
 <div class="итог"><b>@ЮНИТОВ@</b><span>юнитов за ними</span></div>
 <div class="итог"><b>@СЦЕНОЙ@ из @ЮНИТОВ@</b><span>юнитов с известной суммой</span></div>
 <div class="итог"><b>@СУММА@</b><span>сумма известных сделок</span></div>
 <div class="итог"><b>@КАБИНЕТ@</b><span>с открытым кабинетом</span></div>
 <div class="итог"><b>@БЕЗНОМЕРА@</b><span>без телефона</span></div>
</div>
@КАРТОЧКИ@
<footer>Кружок «?» у даты передачи — срок назван со слов, документом не подтверждён.<br>
Перечёркнутая строка — сделка не состоялась или договор расторгнут.<br>
Персональные данные. Наружу этот лист не выкладывается.</footer>
</div></body></html>"""
    for метка, значение in (('@СЕЙЧАС@', сейчас), ('@ЛЮДЕЙ@', len(строки)), ('@ЮНИТОВ@', всего_юнитов),
                            ('@СЦЕНОЙ@', с_ценой), ('@СУММА@', деньги(сумма)),
                            ('@КАБИНЕТ@', кабинет), ('@БЕЗНОМЕРА@', бн),
                            ('@КАРТОЧКИ@', '\n'.join(куски))):
        док = док.replace(метка, str(значение))

    os.makedirs(os.path.dirname(ВЫХОД), exist_ok=True)
    open(ВЫХОД, 'w', encoding='utf-8').write(док)
    print('готово: %s' % ВЫХОД)
    print('человек %d, юнитов %d, с суммой %d, сумма %s' % (len(строки), всего_юнитов, с_ценой, деньги(сумма)))


if __name__ == '__main__':
    главное()
