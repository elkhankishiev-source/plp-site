#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привязка юнитов к людям по словам Эльнура (07.09.2026).

Что делает:
  1. Находит или заводит человека по телефону (client_resolve — тот же путь,
     что у ботов, поэтому дублей не плодим).
  2. Заводит карточку юнита, если её ещё нет; на витрину она не выходит.
  3. Связывает человека с юнитом в client_objects и переносит пометку Эльнура.

    python3 tools/link_units.py --dry     # показать, что будет сделано
    python3 tools/link_units.py           # сделать
"""
import argparse, json, sys, urllib.parse, urllib.request

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
HREP = dict(H, Prefer='return=representation')

# (код юнита, имя объекта, район, человек, телефон, отношение, пометка)
ROWS = [
    ('PLP-AYANA-F519', 'Ayana Heights · F-519', 'Phuket', 'Сергей', '+972548011761', 'owns',
     'Сделка велась в личном WhatsApp/Telegram Эльнура. Имя уточнить: в переписке Sergei Kuzmeniuk и Vadim Kashnikov.'),
    ('PLP-AYANA-F607', 'Ayana Heights · F-607', 'Phuket', 'Анастасия', '+375336205666', 'owns',
     'Ирина Киселёва в переписке — бывший менеджер Ayana, не клиент.'),
    ('PLP-KATABELLO-F602', 'Katabello · F-602', 'Kata', 'Виктор Путило', 'email:Putilo1968@mail.ru', 'lost',
     'Слетел, потерял 100 000 ฿. Дожимать — нравится юг, однажды купит. Юнит перепродан агенту Нине.'),
    ('PLP-KATABELLO-A606', 'Katabello · A-606', 'Kata', 'Юрий', '+380931116161', 'owns',
     'Двушка. Друг сестры Эльнура. Покупали вместе с Никой (+380637782071).'),
    ('PLP-BIANCANA-C413', 'Biancana Surin · C-413', 'Surin', 'Юрий', '+380931116161', 'owns',
     'Однушка. Тот же Юрий и Ника (+380637782071).'),
    ('PLP-KATABELLO-F702', 'Katabello · F-702', 'Kata', 'Игорь', '+77019822604', 'owns',
     'Сложная сделка: не платил год, потерял 400 000 ฿. Дорабатывать. Жена — Махабат (Любовь), +77477208087.'),
    ('PLP-KATABELLO-F707', 'Katabello · F-707', 'Kata', 'Антон', '+996555959597', 'owns',
     'Перекуплен у Хусейна (друг Эльнура, слетел). Писать ТОЛЬКО в Telegram. Второй юнит — Balcony D-306.'),
    ('PLP-BALCONY-D306', 'The BALCONY · D-306', 'Nai Yang', 'Антон', '+996555959597', 'owns',
     'Второй юнит Антона. Писать только в Telegram.'),
    ('PLP-LEGENDARY-A606', 'Legendary · A-606', 'Bang Tao', 'Ирина', '+77055276161', 'owns',
     'У неё два проекта: Legendary A-606 и VIVI A-507. Покупала вместе с подругой Анной.'),
    ('PLP-VIVI-A507', 'The Title VIVI · A-507', 'Bang Tao', 'Ирина', '+77055276161', 'owns',
     'Второй объект Ирины.'),
    ('PLP-LEGENDARY-A707', 'Legendary · A-707', 'Bang Tao', 'Анна', '+77051763070', 'owns',
     'У неё Legendary A-707 и VIVI A-304. Подруга Ирины (+77055276161), покупали вместе.'),
    ('PLP-VIVI-A304', 'The Title VIVI · A-304', 'Bang Tao', 'Анна', '+77051763070', 'owns',
     'Второй объект Анны.'),
    ('PLP-LEGENDARY-F304', 'Legendary · F-304', 'Bang Tao', 'Елена', '+79167948021', 'owns',
     'Покупала с мужем Владимиром — НЕ афишировать. Ещё её объект: Qabalah F-2, 3 спальни.'),
    ('PLP-QABALAH-F2', 'Villa Qabalah · F-2', 'Bang Tao', 'Елена', '+79167948021', 'owns',
     '3 спальни. Куплена, когда Эльнур работал в проекте.'),
    ('PLP-LEGENDARY-F507', 'Legendary · F-507', 'Bang Tao', 'Екатерина', '+79037467402', 'owns',
     'Подруга Елены, та её и привела. Прямого общения с Эльнуром не было.'),
    ('PLP-LEGENDARY-I705', 'Legendary · I-705', 'Bang Tao', 'Кирилл', '+79119249693', 'owns',
     'Второй объект — Modeva D-103, там оплачен только депозит.'),
    ('PLP-MODEVA-D103', 'Modeva · D-103', 'Bang Tao', 'Кирилл', '+79119249693', 'owns',
     'Оплачен только депозит, похоже, хочет отказаться, на связь не выходит. Дать ссылку на кабинет, когда будет готов.'),
    ('PLP-EDEN-F105', 'Gardens of Eden · F-105', 'Bang Tao', 'Юрий Гончарук', '+77015118477', 'owns',
     'Хороший клиент, купил один объект. Когда Eden сдадут — предложить второй. Греть под The Standard на Лаяне. Имя из переписки, подтвердить.'),
    ('PLP-EDEN-K504', 'Gardens of Eden · K-504', 'Bang Tao', 'Агис', '+6588704801', 'owns',
     'Грек, друг Константина Злобина. Жена Женя говорит по-русски, тот же номер.'),
]

# юниты без владельца — заводим карточку и оставляем пометку
ORPHANS = [
    ('PLP-LEGENDARY-E206', 'Legendary · E-206', 'Bang Tao',
     'Владелец не установлен. В переписке Bingling Liao. Эльнур: «не помню, кто это».'),
    ('PLP-MODEVA-A509', 'Modeva · A-509', 'Bang Tao',
     'Клиент Дарьи — она даст данные.'),
]


def req(method, path, body=None, rep=False):
    r = urllib.request.Request(URL + '/rest/v1/' + path,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=HREP if rep else H, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode()
    return json.loads(raw) if raw.strip() else None


def rpc(fn, body):
    return req('POST', 'rpc/' + fn, body)


def ensure_object(code, name, district):
    got = req('GET', 'objects?select=plp_property_id&plp_property_id=eq.' + code + '&limit=1')
    if got:
        return False
    req('POST', 'objects', {
        'notion_id': code.lower(), 'plp_property_id': code, 'public_code': code, 'name': name,
        'purpose': 'продажа', 'on_site': False, 'district': district, 'type': 'Кондо',
        'source': 'слова Эльнура 07.09'})
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    for code, name, district, who, phone, rel, note in ROWS:
        if a.dry:
            print('%-22s → %-16s %-16s %s' % (code, who, phone, rel))
            continue
        made = ensure_object(code, name, district)
        channel, handle = ('email', phone.split(':', 1)[1]) if phone.startswith('email:') else ('wa', phone)
        r = rpc('client_resolve', {'p_channel': channel, 'p_handle': handle, 'p_name': who,
                                   'p_source': 'личные сделки Эльнура'})
        cl = r[0] if isinstance(r, list) else r
        if not cl or not cl.get('code'):
            print('%-22s ✗ человек не завёлся (%s)' % (code, phone))
            continue
        full = req('GET', 'clients?select=client_id,code,name,notes&code=eq.' + cl['code'] + '&limit=1')[0]
        link = req('GET', 'client_objects?select=id&client_id=eq.%s&object_id=eq.%s&limit=1'
                   % (full['client_id'], code))
        proj = name.split(' · ')[0]
        unit = name.split(' · ')[1] if ' · ' in name else ''
        if link:
            req('PATCH', 'client_objects?id=eq.%d' % link[0]['id'], {'rel': rel, 'note': note})
            act = 'связь обновлена'
        else:
            req('POST', 'client_objects', {'client_id': full['client_id'], 'object_id': code,
                                           'unit': unit, 'project_name': proj, 'rel': rel, 'note': note})
            act = 'связь создана'
        print('%-22s %-14s %s · %s%s' % (code, cl['code'], who, act, ' + карточка' if made else ''))

    for code, name, district, note in ORPHANS:
        if a.dry:
            print('%-22s → без владельца' % code)
            continue
        made = ensure_object(code, name, district)
        req('POST', 'object_sources', {'project_key': code, 'project_name': name, 'kind': 'note',
                                       'url': 'internal://unit-note/' + code, 'audience': 'internal',
                                       'note': note, 'added_by': 'Эльнур 07.09', 'last_ok': True})
        print('%-22s без владельца · пометка записана%s' % (code, ' + карточка' if made else ''))


if __name__ == '__main__':
    main()
