#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точный поиск по Диску по ИМЕНИ файла.

25.09.2026. Встроенный поиск коннектора умеет только fullText и выдаёт простыни.
Здесь запрос идёт прямо в Drive API теми же ключами, что у drive_pull.py, и
печатает только имя, размер и дату — этого хватает, чтобы понять, есть файл
или нет.

    python3 tools/drive_search.py Clover Manor Estella
"""
import json, os, sys, urllib.parse, urllib.request

def токен():
    o = json.load(open(os.path.expanduser('~/.plp_google_oauth.json')))
    t = json.load(open(os.path.expanduser('~/.plp_google_tokens_drive.json')))
    ои = o.get('installed') or o.get('web') or o
    d = urllib.parse.urlencode({'client_id': ои['client_id'], 'client_secret': ои['client_secret'],
                                'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token'}).encode()
    r = urllib.request.Request('https://oauth2.googleapis.com/token', data=d)
    return json.load(urllib.request.urlopen(r, timeout=30))['access_token']

def найти(q, tk, n=25):
    url = ('https://www.googleapis.com/drive/v3/files?q=' + urllib.parse.quote(q) +
           '&fields=files(id,name,mimeType,size,parents,modifiedTime)&pageSize=%d' % n +
           '&includeItemsFromAllDrives=true&supportsAllDrives=true')
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tk})
    return json.load(urllib.request.urlopen(r, timeout=60)).get('files', [])

if __name__ == '__main__':
    tk = токен()
    for слово in sys.argv[1:]:
        q = "name contains '%s' and trashed=false" % слово.replace("'", "\\'")
        ф = найти(q, tk)
        print('=== %-14s найдено %d' % (слово, len(ф)))
        for x in ф[:12]:
            размер = int(x.get('size') or 0)
            print('    %-62s %6.1f МБ  %s' % (x['name'][:62], размер/1e6, x['modifiedTime'][:10]))
