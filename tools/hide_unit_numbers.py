#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Убирает реальные номера вилл и квартир с витрины. Правило Эльнура.

Эльнур 20.09.2026: «у кабалы не должны светиться реальные номера вилл, я говорил это
правило!»

Правило уже было: на витрине не светим ни данные клиента, ни номер юнита застройщика.
Проверка показала, что оно нарушено в названиях объектов:

    Villa Qabalah · M-1, M-2, M-3, M-4, F-2, F-3, F-4, F-5   (8 вилл)
    Legendary · E-206, Modeva · A-509                        (2 квартиры)

Номер виллы — это адрес конкретного человека. По нему находят соседей, владельца и
понимают, кто именно сдаёт. Наружу он не идёт никогда.

Чем заменяем. Номер выкидываем, а различие сохраняем по смыслу: спальни, площадь, вид.
Если различать нечем (у вилл Кабалы пусто вообще всё), остаётся общее название — тогда
карточки одинаковые, и это честный сигнал, что их пора наполнить.

Внутренний код `plp_property_id` НЕ трогаем: на него завязаны ссылки, папки с фото и
CRM. Меняется только видимое имя.

    python3 hide_unit_numbers.py            # показать, что изменится
    python3 hide_unit_numbers.py --apply    # переименовать
"""
import json, os, re, sys, urllib.request

APPLY = '--apply' in sys.argv

# «· M-1», «· E-206», «· A-509» — номер юнита в хвосте названия
НОМЕР = re.compile(r'\s*[·•]\s*[A-ZА-Я]{1,2}\s*-\s*\d{1,4}\s*$')


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


def новое_имя(x):
    """Имя без номера, но с сохранением того, чем объект отличается."""
    имя = НОМЕР.sub('', str(x.get('name') or '')).strip(' ·•-')
    сп = x.get('bedrooms')
    пл = x.get('area_sqm')
    хвост = ''
    if сп:
        n = str(сп)
        хвост = ('%s спальни' % n) if not n.isdigit() else (
            '%s спальня' % n if n == '1' else '%s спальни' % n if n in ('2', '3', '4') else '%s спален' % n)
    elif пл:
        хвост = '%s м2' % int(float(пл))
    return (имя + ' · ' + хвост) if хвост else имя


def main():
    o = call('/objects?select=plp_property_id,name,bedrooms,area_sqm,purpose&limit=400')
    план = [(x, новое_имя(x)) for x in o if НОМЕР.search(str(x.get('name') or ''))]
    print('объектов с номером юнита в названии: %d\n' % len(план))
    for x, имя in план:
        print('   %-22s «%s»  →  «%s»' % (x['plp_property_id'][:22], x['name'], имя))
    if not план:
        print('нарушений нет')
        return 0
    if not APPLY:
        print('\nЭто отчёт. Переименовать: --apply')
        return 0
    for x, имя in план:
        call('/objects?plp_property_id=eq.%s' % x['plp_property_id'], 'PATCH', {'name': имя})
    print('\nпереименовано: %d' % len(план))
    print('внутренние коды не менялись — ссылки и фото на месте')
    return 0


if __name__ == '__main__':
    sys.exit(main())
