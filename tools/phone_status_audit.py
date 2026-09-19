#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разметка номеров и её подключение к делу: битый номер больше не уходит в работу.

Эльнур 19.09.2026: «нельзя бросать битые и не закрытые вопросы… ищи, закрывай».

Что нашлось. В карточках есть поле `phone_status`, и оно даже частично заполнено:
ok 963, no_country 26, too_short 8, too_long 2, junk 1. А всего карточек 3508.
И главное: **это поле не читает никто** — ни мозг, ни один сценарий n8n. Разметка
есть, работы от неё ноль. Это ровно тот случай, который в системе уже назывался
«настроено, но мертво».

Правила разметки, без угадывания:
  ok          — 10–15 цифр, похоже на международный номер;
  no_country  — 7–9 цифр: номер без кода страны, дописать его нельзя, не угадывая
                страну; писать на такой нельзя;
  too_short   — меньше 7 цифр;
  too_long    — больше 15 цифр (обычно это id группы, а не человек);
  telegram_id — короткое значение, совпадающее с чьим-то tg_id либо имеющее переписку
                только в Telegram: это не телефон, в WhatsApp по нему не достучаться;
  empty       — номера нет вовсе.

Достраивать коды стран я не берусь: «904010791» может быть и российским, и казахским,
и чьим угодно. Написать не тому человеку хуже, чем не написать вовсе.

    python3 phone_status_audit.py            # показать сводку и что изменится
    python3 phone_status_audit.py --apply    # проставить phone_status
"""
import json, os, sys, urllib.request
from collections import Counter, defaultdict

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


def allrows(path):
    out, off = [], 0
    while True:
        b = call(path + '&limit=1000&offset=%d' % off)
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def digits(x):
    return ''.join(ch for ch in str(x or '') if ch.isdigit())


def main():
    cl = allrows('/clients?select=client_id,code,name,phone,tg_id,phone_status&order=code')
    tg = {digits(c['tg_id']) for c in cl if c.get('tg_id')}
    hist = defaultdict(set)
    keys = [digits(c['phone']) for c in cl if digits(c.get('phone'))]
    short_keys = [k for k in keys if len(k) < 10]
    for i in range(0, len(short_keys), 60):
        for r in call('/chat_history?phone_norm=in.(%s)&select=phone_norm,channel'
                      % ','.join(short_keys[i:i + 60])):
            hist[str(r['phone_norm'])].add(str(r.get('channel')))

    plan, now = {}, Counter()
    for c in cl:
        p = digits(c.get('phone'))
        if not p:
            st = 'empty'
        elif len(p) > 15:
            st = 'too_long'
        elif len(p) >= 10:
            st = 'ok'
        elif len(p) < 7:
            st = 'too_short'
        else:
            ch = hist.get(p, set())
            if p in tg or (ch and 'whatsapp' not in ch):
                st = 'telegram_id'
            else:
                st = 'no_country'
        now[st] += 1
        if str(c.get('phone_status') or '') != st:
            plan[c['client_id']] = st

    print('как должно быть размечено:')
    for k, v in now.most_common():
        print('   %-12s %d' % (k, v))
    print('\nтребуют правки: %d карточек' % len(plan))
    сломано = sum(v for k, v in now.items() if k in ('no_country', 'too_short', 'too_long', 'telegram_id'))
    print('карточек, на которые в WhatsApp писать нельзя: %d' % сломано)
    if not APPLY:
        print('\nЭто отчёт. Проставить: --apply')
        return 0
    done = 0
    items = list(plan.items())
    for cid, st in items:
        call('/clients?client_id=eq.%s' % cid, 'PATCH', {'phone_status': st})
        done += 1
        if done % 250 == 0:
            print('   … %d из %d' % (done, len(items)))
    print('\nразмечено: %d' % done)
    return 0


if __name__ == '__main__':
    sys.exit(main())
