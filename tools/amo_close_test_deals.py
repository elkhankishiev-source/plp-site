#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тестовые сделки лежали в «успешно реализовано» и завышали счёт продаж.

Разбор 21.09.2026. В CRM 56 сделок, помеченных вручную «[УДАЛИТЬ]». Удалить их
через API нельзя — amoCRM удаление сделок наружу не отдаёт (проверено 19.09:
на DELETE приходит 404 «Cannot DELETE»). Поэтому вопрос был отложен.

При проверке выяснилось, что 47 из них и так лежат в «закрыто, не реализовано»
и никому не мешают. А вот девять — в статусе «УСПЕШНО РЕАЛИЗОВАНО»:

    [УДАЛИТЬ — дубль структуры] ×9, созданы 11.06.2026, сумма 0 ฿

Денег они не искажают — суммы нулевые. Но искажают счёт: успешных сделок в CRM
двадцать семь, из них девять тестовых. То есть реальных восемнадцать, а любая
конверсия, посчитанная по числу сделок, завышена в полтора раза.

Перевод в «закрыто, не реализовано» — то, что доступно через API и решает
задачу: сделка перестаёт считаться продажей. Сами записи останутся в CRM, их
можно удалить руками в интерфейсе, если понадобится.

    python3 amo_close_test_deals.py            # показать
    python3 amo_close_test_deals.py --apply    # перевести в «не реализовано»
"""
import json, os, sys, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
УСПЕХ, ОТКАЗ = 142, 143          # штатные статусы amoCRM
МЕТКИ = ('УДАЛИТЬ', 'удалить в UI')
КЛЮЧ = os.path.expanduser('~/.plp_webhook_key')


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def sb(path):
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=90))
    except Exception as ex:
        print('   (база не ответила: %s)' % str(ex)[:60])
        return []


def amo(method, ep, payload, key):
    """Путь идёт БЕЗ префикса /api/v4 — сценарий подставляет его сам."""
    body = json.dumps({'m': method, 'ep': ep, 'payload': payload}).encode()
    r = urllib.request.Request('https://hub.property-library.com/webhook/amo-write',
                               data=body, method='POST',
                               headers={'Content-Type': 'application/json', 'x-plp-key': key})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return f.read().decode()[:220]
    except Exception as ex:
        return 'исключение: ' + str(ex)[:110]


def main():
    сделки = []
    for м in МЕТКИ:
        сделки += sb('/crm_leads?name=ilike.' + urllib.parse.quote('*%s*' % м)
                     + '&is_deleted=is.false&status_id=eq.%d'
                     + '&select=id,name,price,created_at_crm,responsible_user_id&limit=300'
                     if False else
                     '/crm_leads?name=ilike.' + urllib.parse.quote('*%s*' % м)
                     + '&is_deleted=is.false&select=id,name,price,status_id&limit=300')
    видели, цель = set(), []
    for с in сделки:
        if с['id'] in видели:
            continue
        видели.add(с['id'])
        if с.get('status_id') == УСПЕХ:
            цель.append(с)

    все_успешные = sb('/crm_leads?status_id=eq.%d&select=id,price&limit=1000' % УСПЕХ)
    print('сделок с пометкой «удалить»: %d' % len(видели))
    print('из них в статусе «успешно реализовано»: %d\n' % len(цель))
    for с in цель:
        print('   %-10s %-40s сумма %s' % (с['id'], str(с['name'])[:40], с.get('price')))
    if все_успешные:
        живых = len(все_успешные) - len(цель)
        print('\nуспешных сделок в CRM сейчас: %d. После правки останется %d — это и есть'
              % (len(все_успешные), живых))
        print('настоящее число: конверсия по сделкам перестанет быть завышенной.')
    if not цель:
        print('\nв «успешно реализовано» тестовых нет — править нечего')
        return 0
    if not APPLY:
        print('\nЭто отчёт. Перевести в «закрыто, не реализовано»: --apply')
        return 0
    if not os.path.exists(КЛЮЧ):
        print('нет ключа %s — отменяю' % КЛЮЧ)
        return 1
    key = open(КЛЮЧ).read().strip()
    ок = 0
    for с in цель:
        res = amo('PATCH', 'leads/%d' % с['id'], {'status_id': ОТКАЗ}, key)
        if '"id"' in res:
            ок += 1
            print('   ✓ %s переведена в «не реализовано»' % с['id'])
        else:
            print('   ✗ %s: %s' % (с['id'], res[:110]))
    print('\nпереведено: %d из %d' % (ок, len(цель)))
    print('записи остались в CRM — удалить совсем можно только руками в интерфейсе')
    return 0


if __name__ == '__main__':
    sys.exit(main())
