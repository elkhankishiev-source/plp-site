#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Номера с откушенной первой цифрой: выглядят валидными, а человека по ним не найти.

Нашлось 19.09.2026 на карточке Валерии. В базе два номера:

    375333942426  — «Валерия (маркетолог/контент)», PLP-001289
     75333942426  — «Валерия смм Радион Red», PLP-003490

Второй короче ровно на первую цифру. Моя прежняя проверка считает его исправным: одиннадцать
цифр, выглядит как номер. А написать по нему нельзя — такого абонента нет.

Рядом нашлись ещё: 72546602031 и 75296220117 и 75447519929 — все с пометкой «восстановлена
после ошибочного слияния 03.09». То есть при том слиянии первая цифра терялась системно.

Как ищем, чтобы не гадать: берём номер N и проверяем, есть ли в базе другой номер, который
равен «какая-то цифра + N». Если такой ровно один — это пара «целый и откушенный».
Совпадение по одиннадцати цифрам подряд случайным быть не может.

Чинит слиянием карточек (client_merge), оставляя ту, где номер целый: так сохраняются связи,
а не затирается человек.

    python3 audit_lost_digit.py            # показать пары
    python3 audit_lost_digit.py --apply    # слить откушенные в целые
"""
import json, os, sys, urllib.request
from collections import defaultdict

APPLY = '--apply' in sys.argv


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


def digits(x):
    return ''.join(ch for ch in str(x or '') if ch.isdigit())


def main():
    rows, off = [], 0
    while True:
        b = call('/clients?select=client_id,code,name,phone,phone_status,is_internal'
                 '&order=code&limit=1000&offset=%d' % off)
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    by = defaultdict(list)
    for c in rows:
        p = digits(c.get('phone'))
        if p:
            by[p].append(c)
    все = set(by)

    пары = []
    for p in sorted(все):
        if not (10 <= len(p) <= 13):
            continue
        целые = [d + p for d in '0123456789' if (d + p) in все]
        if len(целые) == 1:
            пары.append((p, целые[0]))

    # Совпадение имён — второе доказательство, что это один человек, а не два разных.
    # Служебную приставку источника отбрасываем: «Новый лид RED - Охі» и «Охі» это один Охі.
    def ядро(имя):
        """Имя без служебной обвязки: «RU | Елена Цой», «Новый лид RED - Охі»,
        «Новая сделка RED - Роман | +905338…» — во всех трёх нужно одно и то же имя."""
        t = str(имя or '').strip()
        if '|' in t:
            части = [x.strip() for x in t.split('|')]
            # выкидываем языковые метки и куски с цифрами, берём самый «именной» кусок
            части = [x for x in части
                     if x and not any(ch.isdigit() for ch in x) and len(x) > 2]
            t = max(части, key=len) if части else t
        for sep in (' - ', ' — ', ' – '):
            if sep in t:
                t = t.split(sep)[-1].strip()
        буквы = ''.join(ch for ch in t.lower() if ch.isalpha())
        return буквы[:12]   # хвост фамилии может быть обрезан в одной из карточек

    доказанные, спорные = [], []
    for кор, длин in пары:
        a = {ядро(x.get('name')) for x in by[кор] if ядро(x.get('name'))}
        b2 = {ядро(x.get('name')) for x in by[длин] if ядро(x.get('name'))}
        совпало = bool(a & b2) or any(
            x and y and (x.startswith(y) or y.startswith(x)) for x in a for y in b2)
        (доказанные if совпало else спорные).append((кор, длин))

    print('карточек: %d, уникальных номеров: %d' % (len(rows), len(все)))
    print('пар «откушенный / целый»: %d' % len(пары))
    print('   из них имена совпадают (один человек доказан): %d' % len(доказанные))
    print('   имена разные, руками смотреть: %d\n' % len(спорные))
    пары = доказанные
    for кор, длин in пары[:8]:
        имя_к = ', '.join(str(x.get('name') or '') for x in by[кор])
        имя_д = ', '.join(str(x.get('name') or '') for x in by[длин])
        print('   %-13s «%s»' % (кор, имя_к[:34]))
        print('   %-13s «%s»   ← целый' % (длин, имя_д[:34]))
    if len(пары) > 8:
        print('   … и ещё %d пар' % (len(пары) - 8))
    if спорные:
        print('\nимена не совпали, НЕ сливаю:')
        for кор, длин in спорные[:6]:
            print('   %-13s «%s»  ↔  %-13s «%s»'
                  % (кор, str(by[кор][0].get('name'))[:24], длин, str(by[длин][0].get('name'))[:24]))
        if len(спорные) > 6:
            print('   … и ещё %d' % (len(спорные) - 6))
    print()
    if not пары:
        print('таких пар нет')
        return 0
    if not APPLY:
        print('Это отчёт. Слить откушенные в целые: --apply')
        return 0

    слито = 0
    for кор, длин in пары:
        keep = by[длин][0]
        for c in by[кор]:
            if c['code'] == keep['code']:
                continue
            try:
                call('/rpc/client_merge', 'POST',
                     {'p_keep': keep['code'], 'p_drop': c['code'],
                      'p_actor': 'аудит откушенных цифр 19.09.2026'})
                print('   ✓ %s (%s) слит в %s (%s)' % (c['code'], кор, keep['code'], длин))
                слито += 1
            except Exception as e:
                print('   ✗ %s → %s: %s' % (c['code'], keep['code'], str(e)[:90]))
    print('\nслито карточек: %d' % слито)
    return 0


if __name__ == '__main__':
    sys.exit(main())
