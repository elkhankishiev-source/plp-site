#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""История лидов из amoCRM в зеркало: заметки, звонки, вложения.

Эльнур 18.09.2026: «очень важно, чтобы вся информация вела учёт, диалоги, данные…
вытащить переписку и заметки из amoCRM в зеркало по каждому лиду — го!»

Зачем. Из тысячи проверенных карточек история диалога была импортирована у НУЛЯ,
в зеркале переписки присутствовал 31 человек. Двойник заходил в разговор без прошлого.
Таблица `crm_notes` при этом существовала с мая и содержала ЧЕТЫРЕ строки — ещё один
случай «настроено, но мертво».

Как берём. amoCRM отдаёт заметки пачками: /api/v4/leads/notes?limit=250&page=N,
то же для контактов. Идём страницами, пока не кончатся, и кладём в crm_notes как есть,
вместе с сырым телом (raw) — потом можно разобрать что угодно без повторного обхода.
Темп щадящий: amoCRM нас уже банил за частоту, поэтому пауза между запросами и
продолжение с последней страницы (global_flags), чтобы прерывание не начинало заново.

Чего тут НЕТ. Переписка из мессенджеров в amoCRM лежит не в заметках, а в отдельном
разделе чатов, к которому у нашего ключа доступа нет. Наши WhatsApp и Telegram и так
пишутся в зеркало с 09.09, так что дыра закрывается с двух сторон.

    python3 crm_notes_import.py                # продолжить обход (лиды)
    python3 crm_notes_import.py --entity contacts
    python3 crm_notes_import.py --restart      # начать с первой страницы
    python3 crm_notes_import.py --status       # сколько уже лежит
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

ENV = next((p for p in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env')
            if os.path.exists(p)), None)
ENTITY = 'leads'
if '--entity' in sys.argv:
    ENTITY = sys.argv[sys.argv.index('--entity') + 1]
RESTART = '--restart' in sys.argv
STATUS = '--status' in sys.argv
PAGES = int(sys.argv[sys.argv.index('--pages') + 1]) if '--pages' in sys.argv else 40
PAUSE = 1.2


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
PROBE = 'http://127.0.0.1:5678/webhook/amo-probe'
WKEY = E.get('PLP_WEBHOOK_KEY', '')


def sb(path, method='GET', body=None, prefer=None):
    h = dict(H)
    h['Content-Type'] = 'application/json'
    if prefer:
        h['Prefer'] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        t = f.read().decode()
    return json.loads(t) if t.strip().startswith(('[', '{')) else t


def sb_страницами(path):
    """Читаем ВСЮ таблицу, а не первую тысячу.

    23.09.2026: Supabase отдаёт максимум 1000 строк за раз и МОЛЧА обрезает —
    `limit=20000` в запросе ничего не меняет, ответ всё равно 1000 строк
    (проверено: Content-Range 0-999/5387). В crm_notes 5387 строк, то есть
    отчёт «сколько заметок импортировано» врал в пять раз и показывал 1000.
    На те же грабли мы наступали в census_owners.py и amo_dialog_notes.py.
    Листаем заголовком Range, как в census_owners.py.

    Только чтение: гонять PATCH или POST по страницам нельзя — запись повторится."""
    # свой limit в пути ломает листание: он перебивает Range, и каждая страница
    # возвращает одну и ту же первую тысячу — цикл не кончится никогда.
    path = re.sub(r'[?&]limit=\d+', lambda m: m.group(0)[0] if m.group(0)[0] == '?' else '', path)
    path = path.replace('?&', '?').rstrip('?&')
    из, шаг, всё = 0, 1000, []
    while True:
        r = urllib.request.Request(BASE + path, headers=dict(H, Range='%d-%d' % (из, из + шаг - 1)))
        try:
            with urllib.request.urlopen(r, timeout=120) as f:
                кусок = json.loads(f.read().decode() or '[]')
        except urllib.error.HTTPError as ex:
            if ex.code == 416:      # строк ровно кратно 1000 — страниц больше нет
                return всё
            raise
        всё += кусок
        if len(кусок) < шаг:
            return всё
        из += шаг


def amo(path):
    r = urllib.request.Request(PROBE, data=json.dumps({'path': path}).encode(),
                               headers={'Content-Type': 'application/json', 'x-plp-key': WKEY},
                               method='POST')
    with urllib.request.urlopen(r, timeout=90) as f:
        d = json.loads(f.read().decode() or '{}')
    if not d.get('data'):
        return None
    return json.loads(d['data'])


def flag(key, value=None):
    if value is None:
        r = sb('/global_flags?key=eq.' + urllib.parse.quote(key) + '&select=value')
        return (r[0]['value'] if r else None)
    sb('/global_flags', 'POST', {'key': key, 'value': str(value)},
       prefer='resolution=merge-duplicates')


def main():
    if STATUS:
        # order=id обязателен: без него страницы Range могут перемешаться и
        # строки повторятся или потеряются
        rows = sb_страницами('/crm_notes?select=entity_type&order=id')
        import collections
        print('строк в crm_notes: %d %s' % (len(rows), dict(collections.Counter(r['entity_type'] for r in rows))))
        print('страница, на которой остановились: лиды=%s, контакты=%s'
              % (flag('crm_notes_page_leads'), flag('crm_notes_page_contacts')))
        return 0

    key = 'crm_notes_page_' + ENTITY
    page = 1 if RESTART else int(flag(key) or 1)
    total = 0
    for _ in range(PAGES):
        j = amo('/api/v4/%s/notes?limit=250&page=%d' % (ENTITY, page))
        if not j:
            print('страница %d: пусто, обход закончен' % page)
            flag(key, page)
            break
        notes = (j.get('_embedded') or {}).get('notes') or []
        if not notes:
            print('страница %d: заметок нет, конец' % page)
            flag(key, page)
            break
        batch = []
        for n in notes:
            p = n.get('params') or {}
            txt = p.get('text') or p.get('original_name') or p.get('link') or ''
            if n.get('note_type', '').startswith('call'):
                txt = 'звонок %s сек, %s' % (p.get('duration'), p.get('phone') or '')
            batch.append({'id': n['id'], 'entity_id': n.get('entity_id'),
                          'entity_type': 'lead' if ENTITY == 'leads' else 'contact',
                          'note_type': n.get('note_type'), 'created_by': n.get('created_by'),
                          'created_at_crm': None, 'updated_at_crm': None,
                          'text': str(txt)[:4000], 'raw': p})
            for fld, src in (('created_at_crm', 'created_at'), ('updated_at_crm', 'updated_at')):
                if n.get(src):
                    import datetime
                    batch[-1][fld] = datetime.datetime.utcfromtimestamp(n[src]).isoformat() + '+00:00'
        sb('/crm_notes', 'POST', batch, prefer='resolution=merge-duplicates,return=minimal')
        total += len(batch)
        flag(key, page + 1)
        print('страница %d: +%d (всего за заход %d)' % (page, len(batch), total))
        page += 1
        time.sleep(PAUSE)
    print('готово, добавлено за заход: %d' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
