#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Светофор объекта: где он на пути «куплен → договор → аренда на сайте».

Эльнур 17.09.2026: «Один светофор на юните — всё верно! Но всё должно быть реальным,
не плашки и не сказал да, а участники ИИ не понимают вообще, клиент не видит,
владелец не знает».

Поэтому светофор здесь ничего не проставляет руками. Он спрашивает функцию базы
`uk_ready` — ту самую, что уже держит шесть шагов: договор, сдача, приёмка, опись,
ставки и правила, публикация. Один источник, три читателя: кабинет владельца,
эта сверка и (после правки) сама публикация.

Главное, что ловит: объект стоит на витрине, хотя лестницу не прошёл. На 17.09 так
висят все одиннадцать арендных карточек — договора управления нет ни у одной,
а значит `uk_booking_guard` всё равно не пропустит бронь. Показываем то,
что забронировать нельзя.

    python3 tools/uk_path.py            # светофор по всем юнитам
    python3 tools/uk_path.py --short    # одна строка для сборки
    python3 tools/uk_path.py PLP-CLOVER-A11
"""
import json, os, sys, urllib.request, urllib.error

ENV = os.path.expanduser('~/.plp_site_supabase.env')
STEP_SHORT = {'contract': 'договор', 'handover': 'сдан', 'accept': 'приёмка',
              'inventory': 'опись', 'pack': 'ставки', 'site': 'витрина'}


def creds():
    env = {}
    for line in open(ENV):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env['SUPABASE_URL'].rstrip('/') + '/rest/v1/', env['SUPABASE_SERVICE_KEY']


def get(base, key, q):
    r = urllib.request.Request(base + q, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def ready(base, key, pid):
    r = urllib.request.Request(base + 'rpc/uk_ready', data=json.dumps({'p_property': pid}).encode(),
                               method='POST', headers={'apikey': key, 'Authorization': 'Bearer ' + key,
                                                       'Content-Type': 'application/json'})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=60).read())
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': e.read()[:80].decode()}


def main():
    short = '--short' in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not os.path.exists(ENV):
        print('[путь объекта] пропущено: нет ключей базы')
        return 0
    base, key = creds()
    objs = get(base, key, 'objects?select=plp_property_id,name,purpose,on_site,parent_object_id,'
                          'owner_ref&limit=500')
    # лестница — про сдачу в аренду через нас. Карточки на продажу и перепродажу
    # она не касается: там нет ни договора управления, ни приёмки под гостей.
    units = [o for o in objs if (o.get('purpose') or '') == 'аренда']
    if only:
        units = [o for o in units if o['plp_property_id'] in only]
    rows, wrong = [], []
    for o in sorted(units, key=lambda x: x['plp_property_id']):
        pid = o['plp_property_id']
        r = ready(base, key, pid)
        if not r.get('ok'):
            continue
        steps = r.get('steps') or []
        done = sum(1 for s in steps if s['ok'])
        rows.append((pid, o.get('name') or '', done, len(steps), r, steps))
        # опубликован, хотя лестница не разрешает — самый опасный случай
        if o.get('on_site') and not r.get('can_publish'):
            wrong.append((pid, r.get('msg') or 'нет акта приёмки или описи'))
    if short:
        print('[путь объекта] %s: юнитов %d, на витрине без права %d%s' % (
            'ок' if not wrong else 'ВИТРИНА ВПЕРЁД ЛЕСТНИЦЫ', len(rows), len(wrong),
            '' if not wrong else ' — ' + wrong[0][0]))
        return 1 if wrong else 0
    print('Светофор пути «куплен → договор → аренда на сайте». Источник — функция uk_ready.\n')
    w = max([len(r[0]) for r in rows] + [10])
    for pid, name, done, total, r, steps in rows:
        marks = ' '.join(('%s✓' if s['ok'] else '%s·') % STEP_SHORT.get(s['key'], s['key'])[:7]
                         for s in steps)
        print('  %-*s %d/%d  %s' % (w, pid, done, total, marks))
        if r.get('msg'):
            print('  %-*s        держит: %s' % (w, '', r['msg']))
    if wrong:
        print('\n🔴 На витрине, хотя лестница не разрешает (%d):' % len(wrong))
        for pid, msg in wrong:
            print('   %-*s %s' % (w, pid, msg))
        print('\n   Бронь по ним всё равно не пройдёт: uk_booking_guard требует договор.')
        print('   Решение за Эльнуром: снять с витрины до договора или оставить как витрину-заявку.')
    return 1 if wrong else 0


if __name__ == '__main__':
    sys.exit(main())
