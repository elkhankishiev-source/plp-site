#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прогонные номера в чёрный список: мозг разговаривал с ними как с людьми.

Сверка расхода 21.09.2026. За последние 300 вызовов мозга $29.63, и вот кто
наговорил больше всех:

    66954143874   83 вызова   $9.69   личный номер Эльнура
    900999001     21          $3.69   прогон
    509498386     19          $2.96   Telegram Эльнура
    66999000999   25          $1.39   прогон
    900999950      4          $0.88   прогон
    66800555001    4          $0.61   прогон (source=qa_test)

Прогонные номера не в чёрном списке, хотя соседние по виду (66900000777,
66999000001) там лежат. Мозг отвечал им полным разбором: читал каноны, поднимал
историю, собирал промпт на 53 тысячи знаков — и платил как за живого клиента.
Около $6 из $29 за трое суток, то есть каждый пятый доллар.

Второй вред тише и хуже: эти диалоги попадают в статистику. По цифрам кажется,
что система нагружена, а живых клиентских диалогов за те же трое суток был один.

Проверка перед внесением: у каждого номера смотрим профиль и переписку. Если у
номера есть имя, роль или осмысленная реплика живого человека — НЕ вносим и
говорим об этом вслух. Лучше оставить лишний прогон, чем закрыть рот двойнику
перед настоящим клиентом.

    python3 blacklist_test_numbers.py            # показать разбор
    python3 blacklist_test_numbers.py --apply    # внести
"""
import json, os, re, sys, urllib.request

APPLY = '--apply' in sys.argv

# номер → чем он себя выдал
ПОДОЗРЕВАЕМЫЕ = {
    '900999001':   'короткий синтетический номер, 21 вызов мозга за 3 суток',
    '900999950':   'короткий синтетический номер',
    '66999000999': 'номер из ряда 6699900xxxx, соседи по ряду уже в списке',
    '66999000998': 'номер из ряда 6699900xxxx',
    '66900000000': 'номер из ряда 6690000xxxx, соседи по ряду уже в списке',
    '66800555001': 'помечен source=qa_test',
    '79111111111': 'одиннадцать единиц — заведомо выдуманный номер',
}

# признаки живого человека в переписке: если встретилось — номер не трогаем
ЖИВОЙ = re.compile(r'(куп|аренд|цен|стоимост|вилл|квартир|бюджет|район|инвест|'
                   r'сколько|интересует|подскажите|хочу|можно ли)', re.I)


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
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            raw = f.read().decode()
        return json.loads(raw) if raw.strip() else []
    except Exception:
        return []


def main():
    есть = {str(x.get('phone') or '') for x in call('/blacklist?select=phone&limit=500')}
    вносим, пропускаем = [], []

    for номер, почему in ПОДОЗРЕВАЕМЫЕ.items():
        if номер in есть:
            пропускаем.append((номер, 'уже в списке'))
            continue
        проф = call('/client_profiles?phone_norm=eq.%s&select=name,contact_role,source' % номер)
        реплики = call('/chat_history?phone_norm=eq.%s&role=eq.user&select=content&limit=20' % номер)
        имя = (проф[0].get('name') if проф else None) or ''
        роль = (проф[0].get('contact_role') if проф else None) or ''
        живые = [str(r.get('content') or '') for r in реплики if ЖИВОЙ.search(str(r.get('content') or ''))]
        if имя.strip() or роль.strip() or живые:
            пропускаем.append((номер, 'похож на живого: имя «%s», роль «%s», осмысленных реплик %d'
                               % (имя[:20], роль, len(живые))))
            continue
        вносим.append((номер, почему, len(реплики)))

    print('в чёрном списке сейчас: %d\n' % len(есть))
    print('ВНЕСТИ (%d):' % len(вносим))
    for номер, почему, n in вносим:
        print('   %-14s реплик %-3d %s' % (номер, n, почему))
    print('\nНЕ ТРОГАЕМ (%d):' % len(пропускаем))
    for номер, почему in пропускаем:
        print('   %-14s %s' % (номер, почему))

    if not APPLY:
        print('\nЭто отчёт. Внести: --apply')
        return 0
    for номер, почему, _ in вносим:
        call('/blacklist', 'POST', {'phone': номер, 'name': 'прогон',
                                    'reason': 'сверка расхода 21.09: ' + почему})
    print('\nвнесено: %d' % len(вносим))
    return 0


if __name__ == '__main__':
    sys.exit(main())
