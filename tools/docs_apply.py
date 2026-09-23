#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разобранный договор → карточка юнита. Недостающее звено.

Эльнур 23.09.2026: «почему нет информации, если она есть! просто ты не собрал его».

Так и было. `contracts_pull.py` забирал договоры из почты и читал их моделью,
складывая разбор в `client_docs.parsed`: цена, площадь, спальни, срок передачи,
график платежей. А дальше — ничего. В `fill_client_units.py` прямо написано,
что площадь и цена «приходят из договора и уже записаны отдельно». Не записаны:
у KKF402 в разборе лежат 66 м², 2 спальни и 8 274 500 ฿, а в карточке пусто.

Этот файл переносит разбор в карточки и больше ничего не делает.

Правила, которые важнее кода:
  • заполняем ТОЛЬКО пустое. Заполненное руками человеком не трогаем;
  • при расхождении документов побеждает договор, за ним бронь, за ней график,
    за ним котировка, последним — счёт. В котировке цена до скидки, в счёте —
    сумма одного платежа, их легко принять за цену юнита;
  • берём только разбор с доверием high и medium. low — это чаще всего скан
    без текстового слоя, там модель честно написала «страницы пустые»;
  • ближайший платёж — первый неоплаченный с датой не раньше сегодня.

    python3 tools/docs_apply.py           # показать, что будет записано
    python3 tools/docs_apply.py --apply   # записать
"""
import datetime, json, os, sys, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
ВЕС = {'contract': 5, 'booking': 4, 'schedule': 3, 'quotation': 2, 'invoice': 1}
СЕГОДНЯ = datetime.date.today().isoformat()


def env():
    out = {}
    for путь in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env'):
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
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def sb(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    try:
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError('база %s %s → %s %s' % (method, path, e.code, e.read().decode()[:300]))
    return json.loads(raw) if raw.strip() else []


def пусто(v):
    return v is None or str(v).strip() == ''


def число(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def ближайший(платежи):
    """Первый неоплаченный платёж с датой не раньше сегодня."""
    будущие = [p for p in платежи if not p.get('paid') and p.get('date') and p['date'] >= СЕГОДНЯ]
    будущие.sort(key=lambda p: p['date'])
    return будущие[0] if будущие else None


def main():
    доки = sb('/client_docs?status=eq.parsed&object_id=not.is.null'
              '&select=id,kind,file_name,object_id,parsed')
    # собираем по юниту, лучший документ впереди
    по_юниту = {}
    for д in доки:
        p = д.get('parsed') or {}
        if p.get('confidence') not in ('high', 'medium'):
            continue
        по_юниту.setdefault(д['object_id'], []).append(д)
    for юнит in по_юниту:
        по_юниту[юнит].sort(key=lambda д: ВЕС.get(д.get('kind'), 0), reverse=True)

    print('юнитов с читаемым разбором: %d\n' % len(по_юниту))
    правок = 0
    for юнит, список in sorted(по_юниту.items()):
        o = sb('/objects?plp_property_id=eq.%s&select=plp_property_id,name,type,area_sqm,'
               'bedrooms,bedrooms_min,bedrooms_max,handover_date' % urllib.parse.quote(юнит))
        co = sb('/client_objects?object_id=eq.%s&select=id,client_id,purchase_price,'
                'currency,handover_on,payment_plan,next_payment_on,next_payment_amount,stage'
                % urllib.parse.quote(юнит))
        if not o:
            print('%-24s нет такого объекта — пропускаю' % юнит)
            continue
        o = o[0]

        # лучшее значение каждого поля: идём от самого весомого документа к слабому
        лучшее, откуда = {}, {}
        for д in список:
            p = д.get('parsed') or {}
            for поле, зн in (('price', число(p.get('price'))),
                             ('area_sqm', число(p.get('area_sqm'))),
                             ('bedrooms', число(p.get('bedrooms'))),
                             ('handover_date', p.get('handover_date')),
                             ('payments', p.get('payments') or None)):
                if зн and поле not in лучшее:
                    лучшее[поле] = зн
                    откуда[поле] = '%s (%s)' % (д.get('file_name', '')[:38], д.get('kind'))

        правка_o, правка_co = {}, {}
        if пусто(o.get('area_sqm')) and лучшее.get('area_sqm'):
            правка_o['area_sqm'] = лучшее['area_sqm']
        if лучшее.get('bedrooms') and o.get('bedrooms_min') is None:
            правка_o['bedrooms_min'] = int(лучшее['bedrooms'])
            правка_o['bedrooms_max'] = int(лучшее['bedrooms'])
            if пусто(o.get('bedrooms')):
                правка_o['bedrooms'] = str(int(лучшее['bedrooms']))
        if пусто(o.get('handover_date')) and лучшее.get('handover_date'):
            правка_o['handover_date'] = лучшее['handover_date']

        if co:
            c = co[0]
            if пусто(c.get('purchase_price')) and лучшее.get('price'):
                # purchase_price в базе целочисленный: 7066661.0 он не примет.
                правка_co['purchase_price'] = int(round(лучшее['price']))
                правка_co['currency'] = c.get('currency') or 'THB'
            if пусто(c.get('handover_on')) and лучшее.get('handover_date'):
                правка_co['handover_on'] = лучшее['handover_date']
            if пусто(c.get('payment_plan')) and лучшее.get('payments'):
                правка_co['payment_plan'] = json.dumps(лучшее['payments'], ensure_ascii=False)
            бл = ближайший(лучшее.get('payments') or [])
            if бл and пусто(c.get('next_payment_on')):
                правка_co['next_payment_on'] = бл['date']
                правка_co['next_payment_amount'] = бл['amount']

        if not правка_o and not правка_co:
            print('%-24s всё уже на месте' % юнит)
            continue
        правок += 1
        print('%-24s %s' % (юнит, str(o.get('name'))[:34]))
        for к, v in list(правка_o.items()) + list(правка_co.items()):
            ист = откуда.get({'bedrooms_min': 'bedrooms', 'bedrooms_max': 'bedrooms',
                              'purchase_price': 'price', 'handover_on': 'handover_date',
                              'payment_plan': 'payments', 'next_payment_on': 'payments',
                              'next_payment_amount': 'payments'}.get(к, к), '')
            зн = str(v)[:60] + ('…' if len(str(v)) > 60 else '')
            print('     %-22s ← %s   [%s]' % (к, зн, ист))
        if APPLY:
            if правка_o:
                sb('/objects?plp_property_id=eq.%s' % urllib.parse.quote(юнит), 'PATCH', правка_o)
            if правка_co:
                sb('/client_objects?object_id=eq.%s' % urllib.parse.quote(юнит),
                   'PATCH', правка_co)

    print('\nюнитов к правке: %d' % правок)
    if not APPLY and правок:
        print('Это отчёт. Записать: --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
