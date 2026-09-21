#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Оставшиеся 37 пар с откушенной цифрой: сначала имя, потом слияние.

19.09 нашлись 473 пары «откушенный / целый» номер. 436 из них слиты 21.09 —
там имена совпадали, доказательство было полным. Оставшиеся 37 скрипт пропустил,
потому что имена не совпали. Разбор показал, почему они не совпали, и это три
разные причины:

  1. ОДНО ИМЯ, РАЗНАЯ ЗАПИСЬ. «Elena» и «Елена», «raman TANGRBERGENOV» и
     «Раман», «Aliaksandr» и «Александр», «ksenia» и «Ксения». Латиница против
     кириллицы, полное имя против короткого.

  2. ИМЯ ЕСТЬ ТОЛЬКО У БИТОЙ ЗАПИСИ, у целой пусто — 23 пары из 37. Это важно:
     если слить «в пользу целого» как обычно, имя пропадёт совсем. Сначала
     переносим имя в целую карточку, потом сливаем.

  3. У ЦЕЛОЙ ЗАПИСИ ВМЕСТО ИМЕНИ ПОМЕТКА: «Лид (рассылка Сурин)»,
     «Сделка #16670273», «Gardens of Eden-Marquiz», «Заявка от (…)». Это не имя
     человека, а след источника. Настоящее имя — у битой записи.

Во всех трёх случаях человек один: одиннадцать цифр подряд совпадают, а у
короткого номера нет ни одного сообщения за всё время и в amoCRM он не значится.

Порядок работы: переносим в целую карточку то, чего у неё нет (имя, намерение,
температура), и только потом сливаем. Так ничего не теряется.

    python3 merge_lost_digit_rest.py            # показать план
    python3 merge_lost_digit_rest.py --apply    # перенести и слить
"""
import json, os, re, sys, urllib.request

APPLY = '--apply' in sys.argv

# Что НЕ является именем человека. Первый прогон показал две ошибки разом:
# «Без имени» и «6 имя» уезжали в целую карточку как имя, а «Gardens of
# Eden-Marquiz» и «Сделка #16670273» считались именем и не давали перенести
# настоящее («Жениш», «Тома», «Sardor»). Это следы источника, а не люди.
ПОМЕТКА = re.compile(
    r'^(none|null|лид|новый лид|новая сделка|заявка от.*|сделка.*|клиент|'
    r'без имени|[\d\s№#.,-]+|.*рассылк.*|.*\bred\b.*|.*визуал.*|'
    r'\d+\s*имя|gardens of eden.*|.*marquiz.*|.*-\s*marquiz)$', re.I)


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
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read().decode()
        return json.loads(raw) if raw.strip() else []
    except Exception as ex:
        print('   ✗ %s: %s' % (path[:50], str(ex)[:80]))
        return None


def все_карточки():
    out, off = {}, 0
    while off < 8000:
        b = call('/clients?select=code,name,phone,temp,intent,notes&limit=1000&offset=%d' % off)
        if not b:
            break
        for x in b:
            if x.get('phone'):
                out[re.sub(r'\D', '', str(x['phone']))] = x
        if len(b) < 1000:
            break
        off += 1000
    return out


def имя_настоящее(v):
    s = str(v or '').strip()
    return bool(s) and not ПОМЕТКА.match(s)


def main():
    карточки = все_карточки()
    номера = set(карточки)
    пары = []
    for n in номера:
        if not (10 <= len(n) <= 15):
            continue
        for c in '123456789':
            if (c + n) in номера:
                пары.append((n, карточки[n], c + n, карточки[c + n]))
                break

    print('пар «откушенный / целый» осталось: %d\n' % len(пары))
    план = []
    for кор, a, цел, b in sorted(пары):
        перенос = {}
        if имя_настоящее(a.get('name')) and not имя_настоящее(b.get('name')):
            перенос['name'] = a['name']
        for поле in ('intent', 'temp'):
            if a.get(поле) and not b.get(поле):
                перенос[поле] = a[поле]
        план.append((кор, a, цел, b, перенос))

    print('%-13s %-26s %-13s %-22s %s' % ('битый', 'имя у битого', 'целый', 'имя у целого', 'перенесём'))
    for кор, a, цел, b, перенос in план:
        print('%-13s %-26s %-13s %-22s %s'
              % (кор, str(a.get('name'))[:26], цел, str(b.get('name'))[:22],
                 ', '.join(перенос) or '—'))
    с_именем = sum(1 for *_, п in план if 'name' in п)
    print('\nиз них у целой карточки нет имени и оно перейдёт от битой: %d' % с_именем)

    if not APPLY:
        print('\nЭто отчёт. Перенести и слить: --apply')
        return 0

    перенесено = слито = 0
    for кор, a, цел, b, перенос in план:
        if перенос:
            r = call('/clients?phone=eq.%s' % цел, 'PATCH', перенос)
            if r is not None:
                перенесено += 1
        r = call('/rpc/client_merge', 'POST',
                 {'p_keep': b['code'], 'p_drop': a['code'],
                  'p_actor': 'откушенная цифра, разбор имён 21.09.2026'})
        if r is not None:
            слито += 1
            print('   ✓ %s (%s) → %s (%s)%s'
                  % (a['code'], кор, b['code'], цел,
                     ('  имя «%s» перенесено' % перенос['name']) if 'name' in перенос else ''))
    print('\nперенесено полей в целые карточки: %d, слито пар: %d' % (перенесено, слито))
    return 0


if __name__ == '__main__':
    sys.exit(main())
