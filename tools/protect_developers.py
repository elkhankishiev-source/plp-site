#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Застройщиков и партнёров не трогаем: проставляем роль там, где её забыли.

Эльнур 18.09.2026: «Камилле не пиши, она застройщик, оставь её в покое! Это касается
всех… не мучай застройщиков!!!! Зафиксируй раз и навсегда».

Механика запрета уже есть и работает: `touch_blocked` не пускает касания никому,
у кого contact_role не «lead». Проверено на живых карточках: Камилла Art House,
Коля Clover, Anna Ayana, PLP Developer info — все закрыты.

Слабое место одно: роль заполнена у горстки профилей. У кого она пустая, тот для
системы обычный лид, и однажды ему уйдёт касание. Этот скрипт закрывает дыру
заранее: читает переписку и ставит роль там, где человек явно с той стороны рынка.

Признаки берём жёсткие, чтобы не пометить живого покупателя:
  • говорит от лица проекта: «наш проект», «мы застройщик», «our project», «our team»;
  • шлёт рабочие материалы рынка: прайс для агентов, комиссия агенту, co-broke,
    «уважаемые партнёры», приглашение на брокерский показ;
  • подпись с названием компании-застройщика в имени профиля.

    python3 protect_developers.py            # показать кандидатов
    python3 protect_developers.py --apply    # проставить роль
"""
import json, os, re, sys, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
ENV = os.path.expanduser('~/.plp_site_supabase.env')

STRONG = re.compile(
    r'(наш проект|мы застройщик|от застройщика мы|our project|our team|our development|'
    r'коммисси\w* агент|комисси\w* агент|для агентов|agent commission|co-?broke|'
    r'уважаемые партн[её]р|dear partners|dear agents|прайс для агент|broker (?:event|preview)|'
    r'sales gallery|шоурум нашего|наш отдел продаж)', re.I)
NAMEDEV = re.compile(r'(develop|residence|property|group|estate|realty|villas|construction|'
                     r'застройщик|девелопер)', re.I)


def env():
    out = {}
    for ln in open(ENV, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def get(path):
    r = urllib.request.Request(BASE + path, headers=H)
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.loads(f.read().decode() or '[]')


def patch(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers=dict(H, **{'Content-Type': 'application/json'}), method='PATCH')
    urllib.request.urlopen(r, timeout=30)


def main():
    rows = get('/chat_history?role=eq.user&select=phone_norm,content&limit=4000&order=ts.desc')
    byp = {}
    for r in rows:
        ph = r.get('phone_norm')
        if not ph:
            continue
        byp.setdefault(ph, []).append(r.get('content') or '')
    hits = {}
    for ph, texts in byp.items():
        hay = ' '.join(texts)[:6000]
        m = STRONG.search(hay)
        if m:
            hits[ph] = m.group(0)[:40]
    if not hits:
        print('кандидатов нет')
        return 0
    profs = get('/client_profiles?phone_norm=in.(%s)&select=phone_norm,name,contact_role'
                % ','.join(list(hits)[:200]))
    todo = [p for p in profs if not p.get('contact_role')]
    print('нашлось по переписке: %d, из них без роли: %d' % (len(hits), len(todo)))
    for p in todo:
        why = hits.get(p['phone_norm'], '')
        kind = 'developer' if NAMEDEV.search(p.get('name') or '') else 'partner'
        print('  %-13s %-34s → %-9s (сигнал: «%s»)' % (p['phone_norm'], (p.get('name') or '')[:34], kind, why))
        if APPLY:
            patch('/client_profiles?phone_norm=eq.' + p['phone_norm'],
                  {'contact_role': kind,
                   'contact_role_by': 'код: признаки рынка в переписке, 18.09.2026 — касания запрещены'})
    if not APPLY:
        print('\nЭто отчёт. Проставить роль: --apply')
    else:
        print('\nроль проставлена: %d — касания им больше не уйдут' % len(todo))
    return 0


if __name__ == '__main__':
    sys.exit(main())
