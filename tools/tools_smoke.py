#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож инструментов: проверяет, что двойник может ДОСТАТЬ, а не что служба жива.

Эльнур 23.09.2026: «посмотри, где нам не хватает сторожей».

Пробел виден по сегодняшнему дню. Все сторожа рапортовали «ок», пока:
  • поиск объекта не возвращал НИ ОДНОГО объекта с момента появления — в запросе
    стояла колонка, которой в базе нет;
  • цены по юнитам не показывались ни разу — инструмент ходил в несуществующую таблицу;
  • персональный оффер не собирался ни разу — две поломки подряд в одном месте.
Служба при этом была active, мозг отвечал, сайт открывался. Мы следили за тем,
что процесс жив, а не за тем, что он отдаёт.

Этот сторож зовёт каждый инструмент с заведомо известным входом и проверяет
ответ по смыслу: не «пришло 200», а «в ответе есть то, что обязано быть».
Модель не трогает — дёргает ровно те запросы, которые делает инструмент.

    python3 tools_smoke.py           # показать
    python3 tools_smoke.py --tg      # и сообщить в тех-чат, если что-то сломано
"""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request

СООБЩАТЬ = '--tg' in sys.argv


def env():
    out = {}
    for путь in ('/opt/plp-api/.env', os.path.expanduser('~/.plp_site_supabase.env')):
        if not os.path.exists(путь):
            continue
        for ln in open(путь, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1)
                out.setdefault(k, v.strip().strip('"\''))
        if out.get('SUPABASE_URL'):
            break
    return out


E = env()
SB = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def гет(путь, тело=None):
    r = urllib.request.Request(SB + путь,
                               data=json.dumps(тело).encode() if тело is not None else None,
                               method='POST' if тело is not None else 'GET',
                               headers=dict(H, **({'Content-Type': 'application/json'} if тело is not None else {})))
    try:
        with urllib.request.urlopen(r, timeout=30) as f:
            return 200, json.loads(f.read().decode() or 'null')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:220]
    except Exception as e:
        return 0, str(e)[:220]


# Каждая проверка: имя · что зовём · чему обязан быть равен ответ.
# Входы взяты боевые и устойчивые: проект из каталога, юнит с договором.
ПРОВЕРКИ = []


def проверка(имя):
    def обёртка(f):
        ПРОВЕРКИ.append((имя, f))
        return f
    return обёртка


@проверка('поиск объекта по названию')
def _():
    поля = ('name,district,price_from_usd,price_from_thb,bedrooms,stage,handover_date,public_code,'
            'plp_property_id,on_site,first_payment,ownership,plot_area_sqm,built_area_sqm,'
            'purpose,usp,price_tiers,unit_types')
    м = urllib.parse.quote('Estella')
    к, д = гет('/objects?or=(name.ilike.*%s*,plp_property_id.ilike.*%s*,public_code.ilike.*%s*)'
               '&select=%s&order=price_from_usd.desc.nullslast&limit=3' % (м, м, м, поля))
    if к != 200:
        return False, 'запрос не прошёл: %s %s' % (к, д)
    if not д:
        return False, 'по «Estella» не нашлось ничего'
    return True, 'нашлось %d, первый %s' % (len(д), д[0].get('plp_property_id'))


@проверка('поиск объекта по номеру юнита')
def _():
    м = urllib.parse.quote('F302')
    к, д = гет('/objects?or=(name.ilike.*%s*,plp_property_id.ilike.*%s*,public_code.ilike.*%s*)'
               '&select=plp_property_id&limit=3' % (м, м, м))
    if к != 200:
        return False, 'запрос не прошёл: %s %s' % (к, д)
    return (bool(д), 'нашёлся %s' % д[0]['plp_property_id'] if д else 'по «F302» пусто')


@проверка('цены по юнитам у проекта')
def _():
    к, д = гет('/objects?plp_property_id=eq.PLP-VIVANA&select=price_tiers&limit=1')
    if к != 200:
        return False, 'запрос не прошёл: %s %s' % (к, д)
    т = (д[0] or {}).get('price_tiers') if д else None
    if isinstance(т, str):
        try:
            т = json.loads(т)
        except Exception:
            т = None
    if not isinstance(т, list) or not т:
        return False, 'у Vivana пропали разбивки по юнитам'
    есть = [x for x in т if x.get('price_from_thb') or x.get('price_thb') or x.get('price_usd')]
    return (bool(есть), 'юнитов %d, с ценой %d' % (len(т), len(есть)))


@проверка('карточка купленного юнита')
def _():
    к, д = гет('/client_objects?object_id=ilike.*A12&select=object_id,purchase_price,payment_plan&limit=3')
    if к != 200:
        return False, 'запрос не прошёл: %s %s' % (к, д)
    if not д:
        return False, 'юнит A12 среди купленных не нашёлся'
    с_ценой = [x for x in д if x.get('purchase_price')]
    return (bool(с_ценой), 'строк %d, с ценой %d' % (len(д), len(с_ценой)))


@проверка('опознание человека по номеру')
def _():
    к, д = гет('/rpc/identity_resolve', {'p_value': '66954143874'})
    if к != 200:
        return False, 'запрос не прошёл: %s %s' % (к, д)
    return (bool(д and д.get('найден')), 'опознан' if (д or {}).get('найден') else 'не опознан свой же номер')


@проверка('сборка персонального оффера')
def _():
    к, д = гет('/rpc/offer_create', {'p_client_code': 'PLP-001106', 'p_property_id': 'PLP-KATABELLO',
                                     'p_by': 'сторож', 'p_days': 1, 'p_note': None,
                                     'p_blocks': None, 'p_custom': None})
    if к != 200:
        return False, 'не собрался: %s %s' % (к, д)
    токен = д.get('token') if isinstance(д, dict) else (д[0].get('token') if isinstance(д, list) and д else д)
    return (bool(токен), 'токен выдан' if токен else 'токен не выдан')


@проверка('код клиента достаётся по номеру')
def _():
    к, д = гет('/client_profiles?phone_norm=eq.35797430452&select=client_id&limit=1')
    if к != 200 or not д:
        return False, 'профиль не нашёлся: %s' % к
    к2, д2 = гет('/clients?client_id=eq.%s&select=code&limit=1' % д[0]['client_id'])
    if к2 != 200 or not д2 or not д2[0].get('code'):
        return False, 'код клиента не достался'
    return True, д2[0]['code']


@проверка('доступность аренды по датам')
def _():
    к, д = гет('/objects?purpose=in.(%s,rent)&on_site=eq.true&select=plp_property_id&limit=5'
               % urllib.parse.quote('аренда'))
    return (к == 200 and bool(д), 'объектов аренды на витрине %d' % (len(д) if isinstance(д, list) else 0))


def main():
    сломано = []
    print('СТОРОЖ ИНСТРУМЕНТОВ — проверяем, что двойник может достать\n')
    for имя, f in ПРОВЕРКИ:
        try:
            ок, нота = f()
        except Exception as e:
            ок, нота = False, 'проверка упала: %s' % str(e)[:150]
        print('  %-34s %s  %s' % (имя, 'ок      ' if ок else 'СЛОМАНО ', нота))
        if not ок:
            сломано.append('%s — %s' % (имя, нота))
    print('\nпроверок %d, сломано %d' % (len(ПРОВЕРКИ), len(сломано)))
    if сломано and СООБЩАТЬ:
        токен, чат = E.get('TG_BOT_TOKEN'), E.get('TG_TECH_CHAT_ID')
        if токен and чат:
            текст = ('Инструменты двойника: не отдают данные (%d из %d)\n\n' % (len(сломано), len(ПРОВЕРКИ))
                     + '\n'.join('• ' + с for с in сломано)
                     + '\n\nСлужба при этом может быть жива — проверяется именно ответ.')
            try:
                urllib.request.urlopen(urllib.request.Request(
                    'https://api.telegram.org/bot%s/sendMessage' % токен,
                    data=json.dumps({'chat_id': чат, 'text': текст}).encode(),
                    headers={'Content-Type': 'application/json'}), timeout=30).read()
                print('сообщено в тех-чат')
            except Exception as e:
                print('сообщить не вышло: %s' % str(e)[:120])
    return 1 if сломано else 0


if __name__ == '__main__':
    sys.exit(main())
