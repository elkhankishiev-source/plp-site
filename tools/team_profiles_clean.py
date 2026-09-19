#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Свои номера перестают быть «покупателями»: роль ставим, чужую анкету стираем.

Эльнур 18.09.2026: «если система держит меня как покупателем, почему тогда она
выдаёт мне секреты внутрянку, разберись, а то будут проблемы у нас!»

Причина, почему система вообще считала его покупателем: у всех семи своих номеров
contact_role пустой (заполнен он лишь у 43 профилей из 1844), а разборщик анкеты
писал в профиль бюджет, район, цель и тип из ЛЮБОГО сообщения — включая его
собственные тестовые реплики. В его карточках накопилось:

  8554364120  «Эльнур PLP»  бюджет 97–285 тыс. $, цель «аренда/доход», Камала, Карон
  509498386   «Elnur»       бюджет 0–1 млн $, цель «для себя», Карон, инвестор
  66954143874 тестовый      бюджет 20 тыс. $, вилла, Ката, Карон, семья

Это выдумка машины, а не его запрос. Запись мы уже закрыли правкой 319 в brain.mjs;
здесь убираем накопленное и ставим роль, чтобы ворота работали и по роли тоже.

Что делает скрипт:
  1. contact_role = 'team' для семи своих номеров (пометка, кем поставлено);
  2. обнуляет поля анкеты лида: бюджет, цель, район, предпочтение локации, тип,
     спальни, сегмент, скоринг, этап, крючок. Ничего не удаляет, только поля.
  3. переписку, имена, паузы, сделки и объекты НЕ трогает.

    python3 team_profiles_clean.py            # показать, что будет
    python3 team_profiles_clean.py --apply    # применить
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
ENV = os.path.expanduser('~/.plp_site_supabase.env')
TEAM = ['66954143874', '509498386', '66960169127',
        '66640709032', '8554364120', '8227351774']
# 66955492587 СОЗНАТЕЛЬНО не тронут, и это находка для Эльнура: номер стоит в списке
# своих (наш рабочий WhatsApp), но профиль называется «Оксана Штойк Валид Пхт Plp
# Рабочий», за ним сделка amoCRM 34009111 и сегмент мёртвой базы A. То есть в карточке
# клиента записан НАШ рабочий номер. Пока не решено, чей он, роль ставить нельзя:
# сейчас любой, кто пишет с него, считается внутренней командой.
CLEAR = ['budget_usd_min', 'budget_usd_max', 'budget_min', 'budget_max', 'goal',
         'district_interest', 'location_preference', 'property_type', 'bedroom',
         'segment', 'scoring', 'stage', 'key_hook', 'key_hook_at',
         # 18.09: фокус объекта — из-за него под ответом про Estella уехала ссылка
         # на «Vibe Residence Karon», поставленную ещё 16.09.
         'active_object_id', 'active_object_set_at']


def env():
    out = {}
    for ln in open(ENV, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


def req(url, method='GET', body=None, key=None):
    h = {'apikey': key, 'Authorization': 'Bearer ' + key,
         'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=30) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def main():
    e = env()
    base, key = e['SUPABASE_URL'].rstrip('/') + '/rest/v1', e['SUPABASE_SERVICE_KEY']
    flt = 'phone_norm=in.(%s)' % ','.join(TEAM)
    rows = req('%s/client_profiles?%s&select=client_id,phone_norm,name,contact_role,%s'
               % (base, flt, ','.join(CLEAR)), key=key)
    print('своих профилей найдено: %d' % len(rows))
    dirty = 0
    for r in rows:
        junk = {k: r[k] for k in CLEAR if r.get(k) not in (None, [], '')}
        print('  %-12s %-34s роль: %-8s' % (r['phone_norm'], (r.get('name') or '')[:34],
                                            r.get('contact_role') or '—'))
        if junk:
            dirty += 1
            print('       чужая анкета: %s' % json.dumps(junk, ensure_ascii=False)[:150])
    print('\nбудет поставлена роль internal: %d, очищено анкет: %d' % (len(rows), dirty))
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    body = {'contact_role': 'internal', 'contact_role_by': 'система: свой номер, правка 319'}
    for k in CLEAR:
        body[k] = None
    got = req('%s/client_profiles?%s' % (base, flt), 'PATCH', body, key)
    print('обновлено профилей: %d' % len(got))
    return 0


if __name__ == '__main__':
    sys.exit(main())
