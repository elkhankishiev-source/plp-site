#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Номер виллы не должен стоять в адресе страницы. Одиннадцать последних.

Эльнур, правило повторено дважды: «у кабалы не должны светиться реальные номера
вилл», «на витрине нет ни данных клиента, ни номера юнита застройщика».

20.09 я убрал номера из НАЗВАНИЙ объектов и решил, что закрыл вопрос. Сверка
21.09 показала, что нет: номера остались в АДРЕСАХ страниц, а адрес виден
сильнее названия. На живом сайте открываются (проверено, HTTP 200):

    property-library.com/object/qabalah-m1 · -m2 · -m3 · -m4
    property-library.com/object/qabalah-f2 · -f3 · -f4 · -f5

Адрес строится из `public_code`, и у этих восьми он не замаскирован — равен
внутреннему коду с номером виллы. Хуже: картинка предпросмотра лежит по адресу
`/img/PLP-QABALAH-M1.jpg`, то есть при отправке ссылки в WhatsApp номер виллы
уезжает в превью сообщения.

Ещё трое ждут своей очереди: PLP-AYANA-C408, PLP-EDEN-I503, PLP-MODEVA-E202
стоят `on_site=true` без маски, страниц у них пока нет только потому, что сборка
отстала от базы. На следующей сборке засветов стало бы одиннадцать.

Механизм давно есть и работает у остальных 38 юнитов: `public_code` держит
псевдоним (U1, U2, R1…), адрес строится из него, внутренний код остаётся внутри.
Эти одиннадцать просто через него не прошли. Скрипт продолжает нумерацию
проекта, не занимая уже выданные псевдонимы, и переименовывает картинки
предпросмотра.

Что НЕ меняется: внутренний `plp_property_id` — на нём завязаны CRM, папки с
фото и история. Меняется только то, что видно снаружи.

    python3 mask_unit_codes.py            # показать план
    python3 mask_unit_codes.py --apply    # применить
"""
import json, os, re, shutil, sys, urllib.request

APPLY = '--apply' in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# номер юнита в хвосте кода: «-M1», «-C408», «-F707»
НОМЕР = re.compile(r'[-_][A-Z]{1,2}\d{1,4}$')
# уже выданные псевдонимы: U1 (квартира), R1 (вилла в аренде)
ПСЕВДО = re.compile(r'[-_]([UR])(\d+)$')


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def main():
    o = call('/objects?select=plp_property_id,public_code,name,parent_object_id,purpose,on_site'
             '&on_site=eq.true&limit=300')
    свои = {x['plp_property_id']: x for x in o}

    # какие псевдонимы уже заняты внутри каждого проекта
    занято = {}
    for x in o:
        p = x.get('parent_object_id')
        if not p:
            continue
        m = ПСЕВДО.search(str(x.get('public_code') or ''))
        if m:
            занято.setdefault(p, set()).add((m.group(1), int(m.group(2))))

    план = []
    for x in sorted(o, key=lambda z: z['plp_property_id']):
        код = str(x.get('public_code') or x['plp_property_id'])
        if not НОМЕР.search(код) or ПСЕВДО.search(код):
            continue                       # маска уже стоит
        род = x.get('parent_object_id')
        if not род:
            continue                       # это сам проект, а не юнит
        # вилла в аренде получает R, квартира — U; смотрим на тип соседей
        буква = 'R' if 'вилл' in str(x.get('name') or '').lower() else 'U'
        взято = занято.setdefault(род, set())
        n = 1
        while (буква, n) in взято:
            n += 1
        взято.add((буква, n))
        новый = '%s-%s%d' % (род, буква, n)
        план.append((x, новый))

    print('объектов на витрине: %d' % len(o))
    print('с номером юнита в публичном коде: %d\n' % len(план))
    for x, новый in план:
        стар = x.get('public_code') or x['plp_property_id']
        print('   %-22s  %-22s → %-22s  /object/%s'
              % (x['plp_property_id'], стар, новый, новый.replace('PLP-', '').lower()))
    if not план:
        print('нарушений нет')
        return 0

    # картинки предпросмотра названы по публичному коду — их тоже переименовываем
    картинки = []
    for x, новый in план:
        стар = x.get('public_code') or x['plp_property_id']
        путь = os.path.join(ROOT, 'img', стар + '.jpg')
        if os.path.exists(путь):
            картинки.append((путь, os.path.join(ROOT, 'img', новый + '.jpg')))
    print('\nкартинок предпросмотра переименовать: %d' % len(картинки))
    for a, b in картинки:
        print('   %s → %s' % (os.path.basename(a), os.path.basename(b)))

    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    for x, новый in план:
        call('/objects?plp_property_id=eq.%s' % x['plp_property_id'], 'PATCH',
             {'public_code': новый})
    for a, b in картинки:
        shutil.move(a, b)
    print('\nзамаскировано объектов: %d, переименовано картинок: %d' % (len(план), len(картинки)))
    print('внутренние коды не менялись — CRM, фото и история на месте')
    print('дальше: node build/all.mjs — страницы со старыми адресами будут удалены')
    return 0


if __name__ == '__main__':
    sys.exit(main())
