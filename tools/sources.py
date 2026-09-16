#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реестр источников: откуда у каждого объекта берётся правда.

Эльнур 16.09.2026: «объект — источник информации гугл диск, иногда прайс в тг-группе,
значит ссылка на тг-группу. Это сохраняешь в базе, и по требованию ты там это и берёшь.
Если чего-то не хватает — говоришь».

Живёт в таблице public.object_sources. Виды приведены к одному словарю:
    drive  — папка застройщика на Google Диске (материалы, прайсы, планы, фото)
    tg     — канал застройщика в Telegram (свежие цены и наличие)
    site   — публичный сайт проекта
    map    — точка на карте
    other  — прочее (лендинги, агрегаторы, заметки)

Читают реестр: tools/drive_pull.py (папка) и tools/tg_prices.py (канал).

    python3 tools/sources.py             # покрытие и чего не хватает
    python3 tools/sources.py --apply     # привести виды к словарю и дописать из карточек
"""
import json, os, re, sys, urllib.parse, urllib.request, urllib.error, datetime

ENVF = os.path.expanduser('~/.plp_site_supabase.env')
APPLY = '--apply' in sys.argv
MAP = [('drive', r'drive\.google|диск|dropbox|sharepoint'), ('tg', r't\.me|telegram|тг|tg'),
       ('price', r'прайс|price'), ('map', r'maps\.|карт|\bmap\b'), ('site', r'сайт|site|linktr|press|media|tour')]


def env():
    e = {}
    for line in open(ENVF):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1); e[k] = v.strip().strip('"').strip("'")
    return e


E = env()
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1/'


def get(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=90).read())


def send(path, body, method='POST', prefer='return=minimal'):
    r = urllib.request.Request(BASE + path, data=json.dumps(body, ensure_ascii=False).encode(), method=method,
                               headers={**H, 'Content-Type': 'application/json', 'Prefer': prefer})
    return urllib.request.urlopen(r, timeout=60)


def norm_kind(kind, url):
    blob = (str(kind or '') + ' ' + str(url or '')).lower()
    for k, rx in MAP:
        if re.search(rx, blob): return k
    return 'other'


def main():
    objs = get('objects?select=plp_property_id,name,brochure_url,website_url,map_url,floorplan_url'
               '&on_site=eq.true&order=plp_property_id')
    src = get('object_sources?select=*&limit=1000')
    by = {}
    for s in src: by.setdefault(s['project_key'], []).append(s)
    today = datetime.date.today().isoformat()
    fixed = added = 0
    gaps = []
    for o in objs:
        pid = o['plp_property_id']
        rows = by.get(pid, [])
        have = {}
        for r in rows:
            k = norm_kind(r.get('kind'), r.get('url'))
            have.setdefault(k, r)
            if APPLY and r.get('kind') != k:
                send('object_sources?id=eq.%s' % r['id'], {'kind': k}, 'PATCH'); fixed += 1
        # дописываем из карточки то, чего в реестре нет
        for field, kind, note in (('brochure_url', 'drive', 'папка застройщика из карточки'),
                                  ('website_url', 'site', 'сайт проекта из карточки'),
                                  ('map_url', 'map', 'точка на карте из карточки')):
            u = str(o.get(field) or '').strip()
            if not u.startswith('http'): continue
            k = norm_kind(kind, u)
            if k in have: continue
            if APPLY:
                try:
                    send('object_sources', {'project_key': pid, 'project_name': o['name'], 'kind': k,
                                            'url': u, 'note': note, 'added_by': 'tools/sources.py',
                                            'last_checked': today})
                except urllib.error.HTTPError as ex:
                    # такая ссылка уже лежит в реестре под другим видом — это не ошибка
                    if ex.code not in (409, 400): raise
                    continue
            have[k] = {'url': u}; added += 1
        miss = [k for k in ('drive', 'tg') if k not in have]
        print('%-20s %-5s %-5s %-5s %s' % (pid,
              'диск' if 'drive' in have else ' —', 'тг' if 'tg' in have else ' —',
              'сайт' if 'site' in have else ' —',
              ('НЕ ХВАТАЕТ: ' + ', '.join(miss)) if miss else ''))
        if miss: gaps.append((pid, miss))
    print('\nвидов приведено к словарю: %d, дописано из карточек: %d%s' % (fixed, added, '' if APPLY else ' (черновик)'))
    if gaps:
        nd = [p for p, m in gaps if 'drive' in m]
        nt = [p for p, m in gaps if 'tg' in m]
        if nd: print('\nбез папки на Диске (%d): %s' % (len(nd), ', '.join(nd)))
        if nt: print('\nбез канала застройщика (%d): %s' % (len(nt), ', '.join(nt)))
        print('\nЭто и есть список, что просить у Эльнура: одна ссылка на объект — и цены подтянутся сами.')


if __name__ == '__main__':
    main()
