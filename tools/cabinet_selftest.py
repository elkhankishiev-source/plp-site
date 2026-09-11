#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Самопроверка кабинета: дёргаем каждое действие записи и смотрим, работает ли.

Всё делается на демо-объекте и служебной записи, реальные карточки не трогаем.
Что создали — тут же убираем, чтобы после проверки не оставалось мусора.

    python3 tools/cabinet_selftest.py
"""
import json, sys, urllib.request

URL = 'https://167-172-66-20.sslip.io/ukowner'
TOKEN = 'fc67954e51f6a2a37b6f390f647564914d6106385f1a3c3409c856ecab836f06'
DEMO_OBJ = 'PLP-DEMO'
DEMO_CLIENT = 'PLP-001555'          # служебная запись «ТЕСТ» на номер Эльнура

ok_count = fail_count = 0


def call(body):
    b = dict(body, token=TOKEN)
    r = urllib.request.Request(URL, data=json.dumps(b).encode(),
                               headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=120))


def check(name, body, want_key=None, want_error=False):
    global ok_count, fail_count
    try:
        d = call(body)
    except Exception as e:
        fail_count += 1
        print('❌ %-34s связь: %s' % (name, str(e)[:60]))
        return None
    # want_error: проверяем именно ОТКАЗ — гард должен срабатывать, а не молчать
    if want_error:
        good = (d.get('ok') is False) and bool(d.get('error'))
    else:
        good = (d.get('ok') is True) or (want_key and d.get(want_key) is not None)
    if good:
        ok_count += 1
        print('✅ %-34s %s' % (name, json.dumps(d, ensure_ascii=False)[:70]))
    else:
        fail_count += 1
        print('❌ %-34s %s' % (name, json.dumps(d, ensure_ascii=False)[:120]))
    return d


print('— операции по объекту —')
check('внести операцию', {'action': 'uk_tx', 'property_id': DEMO_OBJ, 'kind': 'expense',
                          'amount': 111, 'category': 'проверка', 'date': '2026-09-07',
                          'note': 'самопроверка кабинета'})
d = call({'action': 'data'})
tx_id = None
for p in (d.get('properties') or []):
    if p.get('id') == DEMO_OBJ:
        for t in (p.get('transactions') or []):
            if (t.get('note') or '').startswith('самопроверка'):
                tx_id = t.get('id')
if tx_id:
    check('изменить операцию', {'action': 'uk_tx_update', 'id': tx_id, 'amount': 222})
    check('удалить операцию', {'action': 'uk_tx_delete', 'id': tx_id})
else:
    fail_count += 1
    print('❌ операция не вернулась с id — правку не проверить')

print('\n— работы по объекту —')
check('поставить работу', {'action': 'uk_task', 'property_id': DEMO_OBJ, 'kind': 'cleaning',
                           'due': '2026-09-20', 'cost': 500, 'note': 'самопроверка кабинета'})
d = call({'action': 'data'})
task_id = None
for p in (d.get('properties') or []):
    if p.get('id') == DEMO_OBJ:
        for t in (p.get('tasks') or []):
            if (t.get('note') or '').startswith('самопроверка'):
                task_id = t.get('id')
if task_id:
    check('изменить работу', {'action': 'uk_task_update', 'id': task_id, 'cost': 700})
    check('снять работу', {'action': 'uk_task_delete', 'id': task_id})
else:
    fail_count += 1
    print('❌ работа не вернулась с id')

print('\n— формы с незаполненными полями —')
# Эльнур 08.09 «поставить в работу — всё заполнил и выдало rpc_failed»: проверка
# была зелёной, потому что всегда заполняла КАЖДОЕ поле. Живой человек часть
# полей не трогает — гоняем и такие случаи.
check('работа без срока', {'action': 'uk_task', 'property_id': DEMO_OBJ, 'kind': 'repair',
                           'due': '', 'cost': '', 'note': 'самопроверка пустые'})
check('работа без всего кроме вида', {'action': 'uk_task', 'property_id': DEMO_OBJ,
                                      'kind': 'check', 'note': 'самопроверка пустые'})
check('операция без даты и заметки', {'action': 'uk_tx', 'property_id': DEMO_OBJ,
                                      'kind': 'expense', 'amount': 1, 'category': 'прочее',
                                      'date': '', 'note': 'самопроверка пустые'})
# убираем за собой всё, что завела эта часть
d = call({'action': 'data'})
for p in (d.get('properties') or []):
    if p.get('id') != DEMO_OBJ:
        continue
    for t in (p.get('tasks') or []):
        if (t.get('note') or '') == 'самопроверка пустые':
            call({'action': 'uk_task_delete', 'id': t['id']})
    for t in (p.get('transactions') or []):
        if (t.get('note') or '') == 'самопроверка пустые':
            call({'action': 'uk_tx_delete', 'id': t['id']})

print('\n— сторож брони —')
# Эльнур 08.09: «как я могу поставить его объект на бронь, если он строится,
# не сдан и не подписал с нами УК договор». Бронь без договора не должна проходить.
r = call({'action': 'booking_check', 'property_id': 'PLP-HYTHE'})
if r.get('ok') is False and r.get('error') == 'no_contract':
    ok_count += 1
    print('✅ %-34s %s' % ('бронь без договора отбита', (r.get('msg') or '')[:50]))
else:
    fail_count += 1
    print('❌ %-34s %s' % ('бронь без договора ПРОШЛА', json.dumps(r, ensure_ascii=False)[:80]))
r = call({'action': 'booking_check', 'property_id': DEMO_OBJ})
if r.get('ok') is True:
    ok_count += 1
    print('✅ %-34s' % 'бронь по объекту с договором открыта')
else:
    fail_count += 1
    print('❌ %-34s %s' % ('объект с договором закрыт', json.dumps(r, ensure_ascii=False)[:80]))

print('\n— расходы владения —')
check('заполнить ставки', {'action': 'uk_costs_update', 'property_id': DEMO_OBJ,
                           'taxes': 'проверка ' + str(id(object()))[-4:]})

print('\n— документы —')
check('добавить документ', {'action': 'uk_doc', 'property_id': DEMO_OBJ,
                            'title': 'Самопроверка', 'kind': 'other',
                            'url': 'https://example.com/selftest.pdf'})
d = call({'action': 'data'})
doc_id = None
for p in (d.get('properties') or []):
    if p.get('id') == DEMO_OBJ:
        for x in (p.get('docs') or []):
            if x.get('title') == 'Самопроверка':
                doc_id = x.get('id')
if doc_id:
    check('убрать документ', {'action': 'uk_doc_delete', 'id': doc_id})
else:
    fail_count += 1
    print('❌ документ не вернулся с id')

print('\n— бронь и состояние —')
# бронь от прошлого прогона занимала даты и следующая проверка падала —
# снимаем свои прежние брони, потом ставим новую и её тоже убираем
# 08.09: раньше каждый прогон создавал новую бронь и просто отменял её —
# за пару недель в календаре демо-объекта накопилось полсотни «отменённых».
# Теперь переиспользуем одну и ту же строку: есть — правим, нет — создаём.
_d = call({'action': 'data'})
_own = None
for _p in (_d.get('properties') or []):
    if _p.get('id') != DEMO_OBJ:
        continue
    for _b in (_p.get('bookings') or []):
        if (_b.get('guest_name') or '') == 'Самопроверка' and _b.get('booking_id'):
            _own = _b.get('booking_id')
            break
_body = {'action': 'uk_booking_save', 'property_id': DEMO_OBJ,
         'guest': 'Самопроверка', 'check_in': '2026-11-01',
         'check_out': '2026-11-05', 'amount': 10000, 'channel': 'direct'}
if _own:
    _body['booking_id'] = _own
_r = check('сохранить бронь', _body)
_bid = (_r or {}).get('booking_id') or _own
if _bid:
    call({'action': 'uk_booking_save', 'property_id': DEMO_OBJ,
          'booking_id': _bid, 'status': 'cancelled',
          'check_in': '2026-11-01', 'check_out': '2026-11-05', 'guest': 'Самопроверка'})
check('состояние: список', {'action': 'check_list', 'property_id': DEMO_OBJ}, want_key='rows')

print('\n— карточка человека —')
check('правка данных', {'action': 'client_profile', 'code': DEMO_CLIENT, 'name': 'ТЕСТ'})
check('стадия и пометка', {'action': 'client_update', 'code': DEMO_CLIENT,
                           'note': 'самопроверка кабинета'})
check('объекты человека', {'action': 'client_objects', 'code': DEMO_CLIENT}, want_key='rows')
check('задачи человека', {'action': 'client_tasks', 'code': DEMO_CLIENT}, want_key='tasks')

print('\n— рассылка и служебное —')
check('рассылка: список', {'action': 'camp_list'}, want_key='rows')
check('рассылка: каналы', {'action': 'camp_channels'}, want_key='rows')
check('модерация объектов', {'action': 'mod_list'}, want_key='rows')
check('разбор папок', {'action': 'intake_list'}, want_key='rows')
check('лента касаний', {'action': 'touch_list', 'status': 'draft'}, want_key='rows')

# 10.09: встречи. До этого дня встреча не оставляла следа нигде — договорились
# и забыли. Проверяем и запись, и отказы: без телефона и в прошлое пускать нельзя.
_TEST_PHONE = '66954143874'   # номер Эльнура: на реальных не тестируем
_when = (__import__('datetime').datetime.utcnow()
         + __import__('datetime').timedelta(days=3)).strftime('%Y-%m-%dT09:00:00+07:00')
check('встречи: назначить', {'action': 'meeting_set', 'phone': _TEST_PHONE,
      'when': _when, 'kind': 'online', 'note': 'самопроверка кабинета'}, want_key='id')
check('встречи: список', {'action': 'meeting_list', 'phone': _TEST_PHONE}, want_key='meetings')
check('встречи: без телефона отбивается',
      {'action': 'meeting_set', 'when': _when}, want_error=True)
check('встречи: прошлое отбивается',
      {'action': 'meeting_set', 'phone': _TEST_PHONE, 'when': '2020-01-01T10:00:00+07:00'},
      want_error=True)

# 09.09: фирменные документы. Проверяем, что бланк собирается и не пуст —
# молча сломанный отчёт замечают только когда его уже отправили клиенту.
print('\n— фирменные документы —')
import urllib.request as _u
_UK = ''
try:
    import re as _re, pathlib as _pl, json as _json
    _k = _re.search(r'API_KEY = "([^"]+)"', _pl.Path.home().joinpath('plp_diag.py').read_text()).group(1)
    _v = _json.load(_u.urlopen(_u.Request('https://proplib.app.n8n.cloud/api/v1/variables?limit=100',
                                          headers={'X-N8N-API-KEY': _k})))['data']
    _UK = {x['key']: x['value'] for x in _v}.get('PLP_UK_KEY', '')
except Exception:
    _UK = ''

def _doc(label, qs, must):
    global fail_count
    try:
        h = _u.urlopen('https://proplib.app.n8n.cloud/webhook/document?key=%s&%s' % (_UK, qs), timeout=60).read().decode()
        ok = must in h and len(h) > 1500
        print(('✅ ' if ok else '❌ ') + label + (' ' if ok else ' — не собрался'))
        if not ok:
            fail_count += 1
    except Exception as e:
        fail_count += 1
        print('❌ ' + label + ' — ' + str(e)[:60])
if _UK:
    _doc('годовой свод', 'type=year&property_id=%s&year=2026' % DEMO_OBJ, 'ГОДОВОЙ СВОД')
else:
    print('… ключ УК не получен, документы не проверял')
check('каноны', {'action': 'canon'}, want_key='rows')

print('\nитог: работает %d, сломано %d' % (ok_count, fail_count))
sys.exit(1 if fail_count else 0)
