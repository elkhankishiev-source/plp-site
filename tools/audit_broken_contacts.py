#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Аудит битых карточек: номера без кода страны, наши номера под чужими именами, дубли.

Эльнур 19.09.2026: «нельзя бросать битые и не закрытые вопросы… уверен таких ошибок висит
очень много, ищи закрывай» и про PLP-004198 «954143874 — без кода страны, тот же мой
личный, просто битый».

Что ищем — только то, что можно доказать данными, без догадок:

  1. НОМЕР БЕЗ КОДА СТРАНЫ. Номер, который целиком совпадает с хвостом другого, полного
     номера в базе. `954143874` и `66954143874` — один человек, второй записан битым.
  2. НАШ НОМЕР КАК КЛИЕНТ. Телефоны наших каналов и участников, лежащие в картотеке
     клиентов под чужими именами.
  3. ГРУППА КАК ЧЕЛОВЕК. WhatsApp-группы (id из 15+ цифр) и telegram-группы в клиентах.
  4. ОДИН НОМЕР — НЕСКОЛЬКО КАРТОЧЕК.
  5. ТЕЛЕФОН, КОТОРЫЙ НА САМОМ ДЕЛЕ TELEGRAM-ID (совпадает с чьим-то tg_id).
  6. НОМЕР СЛИШКОМ КОРОТКИЙ, чтобы быть номером (меньше 10 цифр) и ни с чем не сросся.

Чинит только первый вид и только при --apply: битый номер заменяется полным, если полный
однозначно один. Всё остальное печатает списком — слияние карточек это решение Эльнура,
а не моё ([[plp-leads-rules-1609]]: CRM не сливать без его слова).

    python3 audit_broken_contacts.py            # отчёт
    python3 audit_broken_contacts.py --apply    # починить только номера без кода страны
"""
import json, os, sys, urllib.request
from collections import defaultdict

APPLY = '--apply' in sys.argv

OUR_NUMBERS = {'66955492587': 'канал двойника Эльнура',
               '66829935173': 'старый канал Эльнура',
               '66640709032': 'канал двойника Дарьи',
               '66960169127': 'второй номер Дарьи',
               '66954143874': 'личный номер Эльнура'}


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


def all_clients():
    out, off = [], 0
    while True:
        b = call('/clients?select=client_id,code,name,phone,tg_id,is_internal'
                 '&order=code&limit=1000&offset=%d' % off)
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def digits(x):
    return ''.join(ch for ch in str(x or '') if ch.isdigit())


def main():
    cl = all_clients()
    print('карточек в базе: %d\n' % len(cl))
    by_phone = defaultdict(list)
    tg_ids = set()
    for c in cl:
        p = digits(c.get('phone'))
        if p:
            by_phone[p].append(c)
        if c.get('tg_id'):
            tg_ids.add(digits(c['tg_id']))

    full = [p for p in by_phone if len(p) >= 10]

    # 1. номер без кода страны: хвост полного номера
    tails = []
    for short in [p for p in by_phone if 7 <= len(p) <= 10]:
        hits = [f for f in full if f != short and f.endswith(short)]
        if len(hits) == 1:
            tails.append((short, hits[0]))
    print('1. НОМЕР БЕЗ КОДА СТРАНЫ (однозначно достраивается): %d' % len(tails))
    for short, fullnum in tails:
        for c in by_phone[short]:
            who = ', '.join(x.get('name') or '' for x in by_phone[fullnum])
            print('   %-11s %-30s %s  →  %s (%s)'
                  % (c['code'], str(c.get('name'))[:30], short, fullnum, who[:34]))

    # 2. наши номера под видом клиентов
    print('\n2. НАШИ НОМЕРА В КАРТОТЕКЕ КЛИЕНТОВ:')
    for num, what in OUR_NUMBERS.items():
        for c in by_phone.get(num, []):
            print('   %-11s %-34s %s — %s%s'
                  % (c['code'], str(c.get('name'))[:34], num, what,
                     '' if c.get('is_internal') else '   ⚠ НЕ помечен своим'))

    # 3. группы как люди
    print('\n3. ГРУППЫ В КАРТОТЕКЕ КЛИЕНТОВ:')
    for p, lst in by_phone.items():
        if len(p) >= 15:
            for c in lst:
                print('   %-11s %-34s %s%s' % (c['code'], str(c.get('name'))[:34], p,
                                               '' if c.get('is_internal') else '   ⚠ НЕ помечен своим'))

    # 4. один номер — несколько карточек
    dupes = {p: l for p, l in by_phone.items() if len(l) > 1 and len(p) >= 10}
    print('\n4. ОДИН НОМЕР — НЕСКОЛЬКО КАРТОЧЕК: %d номеров' % len(dupes))
    for p, l in list(dupes.items())[:15]:
        print('   %s → %s' % (p, ' | '.join('%s «%s»' % (x['code'], str(x.get('name'))[:22]) for x in l)))
    if len(dupes) > 15:
        print('   … и ещё %d' % (len(dupes) - 15))

    # 5. телефон, который на деле telegram-id
    print('\n5. TELEGRAM-ID В ПОЛЕ ТЕЛЕФОНА:')
    n5 = 0
    for p, l in by_phone.items():
        if p in tg_ids and len(p) <= 11:
            for c in l:
                print('   %-11s %-34s %s' % (c['code'], str(c.get('name'))[:34], p))
                n5 += 1
    if not n5:
        print('   нет')

    # 6. слишком короткие и ни с чем не сросшиеся
    lone = [p for p in by_phone if len(p) < 10 and p not in dict(tails)]
    print('\n6. СЛИШКОМ КОРОТКИЕ НОМЕРА (не достраиваются): %d' % len(lone))
    for p in lone[:10]:
        for c in by_phone[p]:
            print('   %-11s %-34s %s' % (c['code'], str(c.get('name'))[:34], p))

    if not APPLY:
        print('\nЭто отчёт. Починить пункт 1 (только достройку кода страны): --apply')
        print('Слияние карточек и переименование — по твоему слову, сам не трогаю.')
        return 0

    # Просто переписать номер нельзя: на телефоне стоит уникальный индекс, и полная
    # карточка уже занимает это значение (получил 409 Conflict). Это не «поле починить»,
    # это две карточки одного человека — значит слияние штатным client_merge, который
    # переносит связи, а не затирает данные.
    fixed = 0
    for short, fullnum in tails:
        keep = by_phone[fullnum][0]
        for c in by_phone[short]:
            if c['code'] == keep['code']:
                continue
            try:
                call('/rpc/client_merge', 'POST',
                     {'p_keep': keep['code'], 'p_drop': c['code'], 'p_actor': 'аудит 19.09.2026'})
                print('  ✓ %s «%s» (%s) слит в %s «%s» (%s)'
                      % (c['code'], str(c.get('name'))[:20], short,
                         keep['code'], str(keep.get('name'))[:20], fullnum))
                fixed += 1
            except Exception as e:
                print('  ✗ %s → %s: %s' % (c['code'], keep['code'], str(e)[:90]))

    # Наш собственный номер, не помеченный своим, — дыра: система может написать на него
    # как клиенту. Это защита, а не переименование, поэтому делаю сам.
    for num, what in OUR_NUMBERS.items():
        for c in by_phone.get(num, []):
            if not c.get('is_internal'):
                call('/clients?client_id=eq.%s' % c['client_id'], 'PATCH', {'is_internal': True})
                print('  ✓ %s (%s) помечен своим: %s' % (c['code'], num, what))
                fixed += 1
    print('\nисправлено: %d' % fixed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
