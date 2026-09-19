#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Передача сделок Оксаны Эльнуру: через очередь действий, пачками.

Эльнур 18.09.2026: «я забрал себе её номер! и всех её клиентов получается» → «полный го».

Кто такая Оксана, нашёл сам, не спрашивая: в amoCRM это пользователь id 12195834,
«Оксана / Валидатор», key@property-library.com. За ней 474 сделки, 256 не закрытых.

Первая пачка — самое ценное, 61 сделка: встреча назначена (3), квалифицирован
(20 + 18 в разных воронках), отложенный спрос (20).

Почему через очередь, а не прямым запросом в amoCRM: amoCRM нас уже банил за частоту,
и очередь (таблица amocrm_queue → сценарий WF7) для того и построена — она держит
темп, повторяет при сбое, ведёт журнал и защищает от дублей ключом идемпотентности.
Прямые PATCH мимо неё запрещены каноном.

    python3 oksana_handover.py            # показать пачку
    python3 oksana_handover.py --apply    # поставить в очередь
    python3 oksana_handover.py --check    # что стало со сделками в очереди
"""
import json, os, sys, urllib.request

FROM_USER, TO_USER = 12195834, 10172498
BATCH = '/private/tmp/claude-501/-Users-elnurkhankishiev/8b2a6011-32f8-47c6-933d-0f2b6d1b14f7/scratchpad/oksana_batch1.json'
APPLY = '--apply' in sys.argv
CHECK = '--check' in sys.argv
ALL = '--all' in sys.argv          # 18.09: «просто её лиды переведи на меня и все» — вся её база
RAW = '/tmp/oks.json'              # выгрузка её сделок из зеркала


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


def rest(path, method='GET', body=None):
    e = env()
    base, key = e['SUPABASE_URL'].rstrip('/') + '/rest/v1', e['SUPABASE_SERVICE_KEY']
    h = {'apikey': key, 'Authorization': 'Bearer ' + key,
         'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def main():
    if ALL:
        raw = json.load(open(RAW, encoding='utf-8'))
        done = {r['id'] for r in json.load(open(BATCH, encoding='utf-8'))}
        rows = [{'id': r['id'], 'name': r.get('name') or '', 'st': 'остальные',
                 'pipe': '', 'upd': (r.get('updated_at_crm') or '')[:10]}
                for r in raw if not r.get('is_deleted') and r['id'] not in done]
    else:
        rows = json.load(open(BATCH, encoding='utf-8'))
    if CHECK:
        ids = ','.join(str(r['id']) for r in rows)
        q = rest('/amocrm_queue?action_type=eq.update_lead&amocrm_lead_id=in.(%s)&select=amocrm_lead_id,status,last_error,completed_at' % ids)
        import collections
        c = collections.Counter(x['status'] for x in q)
        print('в очереди: %d | %s' % (len(q), dict(c)))
        for x in q:
            if x['status'] not in ('done',):
                print('  %-10s %-9s %s' % (x['amocrm_lead_id'], x['status'], (x.get('last_error') or '')[:70]))
        mirror = rest('/crm_leads?id=in.(%s)&select=id,responsible_user_id' % ids)
        moved = sum(1 for m in mirror if m['responsible_user_id'] == TO_USER)
        print('в зеркале уже на Эльнуре: %d из %d (зеркало обновляется кроном раз в 3 часа)' % (moved, len(mirror)))
        return 0

    print('пачка 1: %d сделок Оксаны (12195834) → Эльнур (10172498)' % len(rows))
    import collections
    for k, v in collections.Counter(r['st'] for r in rows).most_common():
        print('   %-22s %d' % (k, v))
    if not APPLY:
        print('\nЭто отчёт. Поставить в очередь: --apply')
        return 0

    made = 0
    for r in rows:
        key = 'oksana-handover-%s' % r['id']
        if rest('/amocrm_queue?idempotency_key=eq.%s&select=id' % key):
            continue
        rest('/amocrm_queue', 'POST', {
            'idempotency_key': key,
            'action_type': 'update_lead',
            'amocrm_lead_id': r['id'],
            'payload': {'responsible_user_id': TO_USER},
            'source_wf': 'tools/oksana_handover.py',
            'priority': 60,
            'status': 'pending'})
        made += 1
    print('поставлено в очередь: %d (остальные уже стояли)' % made)
    print('исполняет WF7, темпом очереди. Проверить: python3 oksana_handover.py --check')
    return 0


if __name__ == '__main__':
    sys.exit(main())
