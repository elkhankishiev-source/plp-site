#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ужимает уже залитые снимки объектов прямо в хранилище.

Зачем: первые загрузки шли оригиналами по 2–8 МБ. Витрина их всё равно
показывает через уменьшение, значит вес в хранилище — чистые потери места
и трафика. Берём у Supabase его же уменьшенную копию (2000 px, качество 80)
и кладём на место оригинала. Ссылки не меняются.

Запуск:
    python3 tools/shrink_storage.py --dry          # посчитать, ничего не менять
    python3 tools/shrink_storage.py                # ужать всё тяжелее порога
    python3 tools/shrink_storage.py --limit 50     # первые 50 файлов
"""
import argparse, json, os, sys, urllib.request

BUCKET = 'object-media'
THRESHOLD = 900_000        # ниже этого веса трогать нечего
WIDTH = 2000
QUALITY = 80


def creds():
    for p in ('/tmp/.sb', os.path.expanduser('~/.plp_site_supabase.env')):
        try:
            c = json.load(open(p))
            return c['url'], c['key']
        except Exception:
            continue
    sys.exit('не нашёл ключи Supabase')


URL, KEY = creds()
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}


def listing(prefix=''):
    """Полный обход бакета: папки объектов и их подпапки."""
    out, stack = [], [prefix]
    while stack:
        p = stack.pop()
        body = json.dumps({'prefix': p, 'limit': 1000}).encode()
        req = urllib.request.Request(URL + '/storage/v1/object/list/' + BUCKET, data=body,
                                     headers=dict(H, **{'Content-Type': 'application/json'}))
        try:
            rows = json.load(urllib.request.urlopen(req, timeout=90))
        except Exception:
            continue
        for r in rows:
            name = (p + r['name']) if p.endswith('/') or not p else (p + '/' + r['name'])
            if r.get('id') is None:                 # это папка
                stack.append(name + '/')
            else:
                out.append((name, int((r.get('metadata') or {}).get('size') or 0)))
    return out


def small_copy(key):
    u = (URL + '/storage/v1/render/image/public/' + BUCKET + '/' + urllib.parse.quote(key) +
         '?width=%d&quality=%d&resize=contain' % (WIDTH, QUALITY))
    return urllib.request.urlopen(u, timeout=120).read()


def put(key, data, mime='image/jpeg'):
    req = urllib.request.Request(URL + '/storage/v1/object/' + BUCKET + '/' + urllib.parse.quote(key),
                                 data=data, method='POST',
                                 headers=dict(H, **{'Content-Type': mime, 'x-upsert': 'true'}))
    urllib.request.urlopen(req, timeout=180).read()


def main():
    import urllib.parse  # noqa: F401  (нужен внутри small_copy/put)
    ap = argparse.ArgumentParser(description='Ужать снимки в хранилище')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    files = [(k, s) for k, s in listing('objects/') if s > THRESHOLD]
    files.sort(key=lambda x: -x[1])
    if a.limit:
        files = files[:a.limit]
    total = sum(s for _, s in files)
    print('тяжёлых файлов: %d, вес %.1f МБ' % (len(files), total / 1048576))
    if a.dry:
        for k, s in files[:15]:
            print('   %6.1f МБ  %s' % (s / 1048576, k[-70:]))
        return

    saved, done, failed = 0, 0, 0
    for k, s in files:
        try:
            data = small_copy(k)
            if len(data) >= s:                      # меньше не стало — оставляем как было
                continue
            put(k, data)
            saved += s - len(data)
            done += 1
            if done % 10 == 0:
                print('   ужато %d, освобождено %.1f МБ' % (done, saved / 1048576))
        except Exception as e:
            failed += 1
            print('   не вышло:', k[-50:], str(e)[:60])
    print('готово: ужато %d файлов, освобождено %.1f МБ, пропущено с ошибкой %d'
          % (done, saved / 1048576, failed))


if __name__ == '__main__':
    import urllib.parse
    main()
