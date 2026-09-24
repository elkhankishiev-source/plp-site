#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Переносит заполненный лист «Заполнить» обратно в базу.

Эльнур 25.09.2026: «как его редактировать, если надо». Листы «Собственники» и
«Поиск» пересобираются из базы, и правка в них теряется при следующей сборке.
Править надо лист «Заполнить»: жёлтые клетки, по строке на объект. Этот
инструмент читает их и пишет в client_objects — с пометкой, что значение
вписано руками, когда и из какого файла.

Пустая клетка означает «не знаю» и НЕ затирает то, что уже есть в базе.
Занятую клетку тоже не трогаем молча: если в базе уже стоит другое значение,
инструмент показывает расхождение и без --го ничего не пишет.

    python3 tools/clients_import.py ~/PLP-выгрузки/Клиенты_PLP.xlsx        # показать
    python3 tools/clients_import.py ~/PLP-выгрузки/Клиенты_PLP.xlsx --го   # записать
"""

import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

ENV = os.path.expanduser('~/.plp_site_supabase.env')
ГО = '--го' in sys.argv


def creds():
    env = {}
    for line in open(ENV, encoding='utf-8'):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env['SUPABASE_URL'].rstrip('/'), env['SUPABASE_SERVICE_KEY']


def запрос(путь, метод='GET', тело=None):
    url, key = creds()
    h = {'apikey': key, 'Authorization': 'Bearer ' + key,
         'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    r = urllib.request.Request(url + '/rest/v1/' + путь, method=метод,
                               data=json.dumps(тело).encode() if тело is not None else None,
                               headers=h)
    с = urllib.request.urlopen(r, timeout=60).read().decode()
    return json.loads(с) if с.strip() else []


def число(x):
    if x in (None, ''):
        return None
    if isinstance(x, (int, float)):
        return int(x)
    ч = str(x).replace(' ', '').replace(' ', '').replace(',', '').replace('฿', '')
    try:
        return int(float(ч))
    except Exception:
        return None


def дата(x):
    if x in (None, ''):
        return None
    if isinstance(x, datetime.datetime):
        return x.date().isoformat()
    if isinstance(x, datetime.date):
        return x.isoformat()
    т = str(x).strip()
    for ф in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.datetime.strptime(т, ф).date().isoformat()
        except ValueError:
            pass
    return None


def главное():
    пути = [a for a in sys.argv[1:] if not a.startswith('--')]
    путь = пути[0] if пути else os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.xlsx')
    from openpyxl import load_workbook
    ws = load_workbook(путь, data_only=True)['Заполнить']

    есть = {}
    for с in запрос('client_objects?select=id,object_id,client_id,purchase_price,bought_on,'
                    'handover_on,uk_status&limit=2000'):
        есть.setdefault(с['object_id'], []).append(с)

    правки, споры, пусто = [], [], 0
    for р in ws.iter_rows(min_row=2, values_only=True):
        код = (р[0] or '').strip() if isinstance(р[0], str) else р[0]
        if not код or not str(код).startswith('PLP-'):
            continue
        новое = {}
        for поле, зн, преобр in (('purchase_price', р[5], число), ('bought_on', р[6], дата),
                                 ('handover_on', р[7], дата), ('uk_status', р[8], None)):
            v = преобр(зн) if преобр else (str(зн).strip() if зн not in (None, '') else None)
            if v is not None:
                новое[поле] = v
        if not новое:
            пусто += 1
            continue
        for строка in есть.get(код, []):
            к_записи = {}
            for поле, v in новое.items():
                старое = строка.get(поле)
                if старое in (None, ''):
                    к_записи[поле] = v
                elif str(старое)[:10] != str(v)[:10]:
                    споры.append((код, поле, старое, v))
            if к_записи:
                правки.append((строка['id'], код, к_записи))

    print('строк с ответами: %d, пустых: %d' % (len(правки), пусто))
    for _, код, к in правки:
        print('   %-24s %s' % (код, ', '.join('%s=%s' % kv for kv in к.items())))
    if споры:
        print('\nРАСХОЖДЕНИЯ — в базе уже стоит другое, не трогаю:')
        for код, поле, старое, новое_ in споры:
            print('   %-24s %-16s база %s ← в файле %s' % (код, поле, старое, новое_))
    if not ГО:
        print('\nЭто разбор. Записать: --го')
        return 0
    метка = 'вписано руками из %s, %s' % (os.path.basename(путь),
                                          datetime.date.today().strftime('%d.%m.%Y'))
    for ид, код, к in правки:
        стар = запрос('client_objects?id=eq.%d&select=note' % ид)
        примечание = ((стар[0].get('note') + ' · ') if стар and стар[0].get('note') else '') + метка
        запрос('client_objects?id=eq.%d' % ид, 'PATCH', dict(к, note=примечание))
    print('\nзаписано строк: %d' % len(правки))
    return 0


if __name__ == '__main__':
    sys.exit(главное())
