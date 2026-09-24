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

    python3 tools/clients_report.py                 # собрать файлы
    python3 tools/clients_report.py --послать --го  # и отправить в «PLP | отдел продаж»

Наружу уходит только по явному «го» — и только в нашу рабочую группу, где эти
данные и так есть у людей, которые с ними работают.
"""

import datetime
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ENV = os.path.expanduser('~/.plp_site_supabase.env')
ВЫХОД = os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.html')
ТАБЛИЦА = os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.xlsx')
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


def дополнить(связки, объекты):
    """Пустые клетки заполняем тем, что УЖЕ есть в реестре объектов.

    Эльнур 24.09: «надо чтобы они были заполнены». Половина колонок пустовала не
    потому, что мы не знаем, а потому что знание лежало в соседней таблице: срок
    сдачи и стадия есть у юнита или у его проекта, спальни и площадь тоже.

    Данные НЕ копируем в client_objects — закон одного экземпляра. Достаём при
    сборке и помечаем, что взято по проекту, а не по договору: «сдача 12.2026
    по проекту» и «сдача 12.2026» — разные утверждения, и путать их нельзя.
    """
    for с in связки:
        o = объекты.get(с.get('object_id')) or {}
        p = объекты.get(o.get('parent_object_id')) or {}
        если = lambda *xs: next((x for x in xs if x not in (None, '', [])), None)

        if not с.get('handover_on'):
            д = если(o.get('handover_date'), p.get('handover_date'))
            if д:
                с['handover_on'] = д
                с['передача_откуда'] = 'по юниту' if o.get('handover_date') else 'по проекту'
        if not (с.get('stage') or '').strip():
            ст = если(o.get('stage'), p.get('stage'))
            if ст:
                с['stage'] = {'Ready': 'сдан', 'Construction': 'строится',
                              'Pre-sale': 'старт продаж', 'Sold out': 'распродан',
                              'Resale': 'вторичка', 'Announced': 'анонсирован'}.get(ст, ст)
                с['стадия_откуда'] = 'по юниту' if o.get('stage') else 'по проекту'
        сп = если(o.get('bedrooms'), o.get('bedrooms_min'), p.get('bedrooms_min'))
        if сп:
            с['спальни'] = str(сп)
            с['спальни_откуда'] = 'по юниту' if (o.get('bedrooms') or o.get('bedrooms_min')) else 'по проекту'
        пл = если(o.get('area_sqm'), o.get('area_min'))
        if пл:
            try:
                с['площадь'] = ('%g' % float(пл)) + ' м2'
            except Exception:
                с['площадь'] = str(пл)
        с['район'] = если(o.get('district'), p.get('district')) or ''
        с['владение'] = если(o.get('ownership'), p.get('ownership')) or ''
        не_хватает = []
        if not с.get('purchase_price'):
            не_хватает.append('сумма')
        if not с.get('bought_on'):
            не_хватает.append('дата покупки')
        if not с.get('handover_on'):
            не_хватает.append('срок передачи')
        if not с.get('спальни'):
            не_хватает.append('спальни')
        if not с.get('uk_status'):
            не_хватает.append('статус УК')
        с['не_хватает'] = ', '.join(не_хватает)


def таблица(строки, РОЛЬ):
    """Тот же список таблицей: одна строка = один юнит, чтобы можно было
    сортировать и фильтровать в Excel или Numbers."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Клиенты'
    шапка = ['Клиент', 'Код', 'Телефон', 'Почта', 'Кабинет',
             'Проект', 'Юнит', 'Район', 'Спальни', 'Площадь', 'Владение', 'Роль',
             'Сумма, ฿', 'Куплено', 'Передача', 'Откуда срок', 'Состояние',
             'Откуда стадия', 'Статус УК', 'Чего не хватает', 'Внутренний код объекта']
    ws.append(шапка)
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='6E6A4F')
        c.alignment = Alignment(vertical='center')
    ws.freeze_panes = 'A2'

    for имя, к, юниты in строки:
        for u in sorted(юниты, key=lambda x: (x.get('project_name') or '', x.get('unit') or '')):
            ws.append([
                имя, к.get('code') or '',
                ('+' + str(к['phone'])) if к.get('phone') else '',
                к.get('email') or '',
                'да' if к.get('cabinet_enabled') else '',
                u.get('project_name') or '', u.get('unit') or '',
                u.get('район') or '', u.get('спальни') or '', u.get('площадь') or '',
                u.get('владение') or '',
                РОЛЬ.get(u.get('rel'), u.get('rel') or ''),
                int(float(u['purchase_price'])) if u.get('purchase_price') else None,
                дата(u.get('bought_on')), дата(u.get('handover_on')),
                ('со слов' if u.get('handover_caveat') else '') or u.get('передача_откуда') or '',
                u.get('stage') or '', u.get('стадия_откуда') or '',
                u.get('uk_status') or '', u.get('не_хватает') or '',
                u.get('object_id') or '',
            ])
    ширины = [26, 12, 16, 28, 9, 26, 10, 13, 8, 10, 11, 22, 14, 12, 12, 13, 34, 13, 11, 34, 24]
    for i, w in enumerate(ширины, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for ряд in ws.iter_rows(min_row=2, min_col=13, max_col=13):
        for c in ряд:
            c.number_format = '# ##0'
    ws.auto_filter.ref = ws.dimensions
    wb.save(ТАБЛИЦА)


def отправить(нехватка, людей, юнитов, с_суммой):
    """Таблицу — в группу «PLP | отдел продаж», с обращением к Дарье.

    Упоминание ссылкой на id: в группе подсветится и придёт уведомлением, даже
    если публичного ника нет. Тот же приём, что в переписи собственников.
    """
    токен = open(os.path.expanduser('~/.plp_bot_elnurphuket_bot')).read().strip()
    чат = os.environ.get('TG_SALES_CHAT_ID', '-4664612682')
    дарья = os.environ.get('DARIA_TG_ID', '8227351774')
    строки = '\n'.join('• %s — не хватает у %d из %d' % (к, v, юнитов)
                       for к, v in нехватка)
    подпись = (
        '<a href="tg://user?id=%s">Дарья</a>, список клиентов и их объектов на сегодня.\n\n'
        '%d человек, %d объектов, сумма известна по %d.\n'
        'Район, спальни, срок передачи и стадию подтянул из карточек проектов — '
        'в колонках «откуда» видно, взято по юниту или по проекту.\n\n'
        'Чего не хватает:\n%s\n\n'
        'Заполни, что знаешь, прямо в файле и пришли обратно — перенесу в базу.'
        % (дарья, людей, юнитов, с_суммой, строки))

    гр = '----------%s' % os.urandom(8).hex()
    части = []
    for имя, зн in (('chat_id', чат), ('caption', подпись), ('parse_mode', 'HTML')):
        части.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                      % (гр, имя, зн)).encode())
    части.append(('--%s\r\nContent-Disposition: form-data; name="document"; filename="%s"\r\n'
                  'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n'
                  % (гр, os.path.basename(ТАБЛИЦА))).encode())
    части.append(open(ТАБЛИЦА, 'rb').read())
    части.append(('\r\n--%s--\r\n' % гр).encode())
    тело = b''.join(части)
    r = urllib.request.Request('https://api.telegram.org/bot%s/sendDocument' % токен, data=тело,
                               headers={'Content-Type': 'multipart/form-data; boundary=%s' % гр})
    ответ = json.loads(urllib.request.urlopen(r, timeout=180).read().decode())
    print('отправлено в «PLP | отдел продаж»: %s' % ответ.get('ok'))
    return ответ


def главное():
    связки = взять('client_objects?select=client_id,object_id,unit,project_name,rel,stage,uk_status,'
                   'purchase_price,currency,bought_on,handover_on,next_payment_on,next_payment_amount,'
                   'handover_caveat&limit=2000')
    # 24.09: сначала связки, потом ТОЛЬКО нужные люди. Запрос всех клиентов с
    # limit=5000 Supabase молча обрезает на тысяче — в таблице половина строк
    # оставалась без кода и телефона, хотя в базе они есть. Тот же урок уже был
    # записан («limit больше 1000 Supabase молча обрезает») и всё равно повторился.
    нужны = sorted({с['client_id'] for с in связки if с.get('client_id')})
    клиенты = {}
    for i in range(0, len(нужны), 40):
        куча = ','.join(нужны[i:i + 40])
        for c in взять('clients?client_id=in.(' + urllib.parse.quote(куча) +
                       ')&select=client_id,code,name,phone,email,cabinet_enabled,phone_status'):
            клиенты[c['client_id']] = c
    объекты = {o['plp_property_id']: o for o in взять(
        'objects?select=plp_property_id,name,parent_object_id,stage,handover_date,bedrooms,bedrooms_min,'
        'area_sqm,area_min,district,type,ownership&limit=3000')}
    дополнить(связки, объекты)

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
    таблица(строки, РОЛЬ)
    print('готово: %s' % ТАБЛИЦА)
    нехватка = []
    for к in ('сумма', 'дата покупки', 'срок передачи', 'спальни', 'статус УК'):
        n = sum(1 for с in связки if к in (с.get('не_хватает') or ''))
        if n:
            нехватка.append((к, n))
    print('человек %d, юнитов %d, с суммой %d, сумма %s' % (len(строки), всего_юнитов, с_ценой, деньги(сумма)))
    print('не хватает: ' + '; '.join('%s у %d' % (к, n) for к, n in нехватка))
    if '--послать' in sys.argv:
        if '--го' not in sys.argv:
            print('наружу не отправлял. Отправить: --послать --го')
        else:
            отправить(нехватка, len(строки), всего_юнитов, с_ценой)


if __name__ == '__main__':
    главное()
