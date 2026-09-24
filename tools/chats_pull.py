#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Экспорты переписки WhatsApp с Диска: скачать и достать суммы.

25.09.2026, Эльнур: «ты потерял цену, плохо искал, много чего потерял, надо
искать». Так и было: я искал договоры в базе, в почте и в папках объектов на
Диске — и не догадался, что на Диске лежат 22 выгрузки переписки WhatsApp, и в
именах файлов прямо стоят номера юнитов: «Вадим … F519 Ayana Condo», «Анна …
Legendary A707, Vivi A304». Там и цены, и графики, и условия.

Скачивает в ~/PLP-выгрузки/переписки и печатает, какие суммы встречаются.

    python3 tools/chats_pull.py
"""
import io, json, os, re, sys, urllib.parse, urllib.request, zipfile
sys.path.insert(0, '/tmp')
from dsearch import токен, найти

ПАПКА = os.path.expanduser('~/PLP-выгрузки/переписки')

def скачать(fid, tk):
    r = urllib.request.Request('https://www.googleapis.com/drive/v3/files/%s?alt=media' % fid,
                               headers={'Authorization': 'Bearer ' + tk})
    return urllib.request.urlopen(r, timeout=180).read()

ДЕНЬГИ = re.compile(r'(\d[\d  .,]{5,})\s*(?:thb|бат|฿|baht)', re.I)

def главное():
    tk = токен()
    ф = найти("name contains 'WhatsApp Chat' and trashed=false", tk, 200)
    for x in sorted(ф, key=lambda y: y['name']):
        имя = x['name']
        путь = os.path.join(ПАПКА, re.sub(r'[^\w.\- ]', '_', имя))
        if not путь.endswith('.zip'):
            путь += '.zip'
        if not os.path.exists(путь):
            try:
                open(путь, 'wb').write(скачать(x['id'], tk))
            except Exception as e:
                print('  не скачался %s: %s' % (имя[:40], str(e)[:60])); continue
        текст = ''
        try:
            z = zipfile.ZipFile(путь)
            for n in z.namelist():
                if n.lower().endswith('.txt'):
                    текст += z.read(n).decode('utf-8', 'ignore')
        except Exception as e:
            print('  не распаковался %s: %s' % (имя[:40], str(e)[:50])); continue
        суммы = {}
        for м in ДЕНЬГИ.finditer(текст):
            ч = re.sub(r'[  ,]', '', м.group(1)).rstrip('.')
            try:
                v = int(float(ч))
            except Exception:
                continue
            if 1_000_000 <= v <= 200_000_000:
                суммы[v] = суммы.get(v, 0) + 1
        топ = sorted(суммы.items(), key=lambda kv: -kv[1])[:6]
        print('%-72s знаков %6d · сумм %d' % (имя[:72], len(текст), len(суммы)))
        if топ:
            print('      ' + ', '.join('%s ฿ ×%d' % ('{:,}'.format(v).replace(',', ' '), n) for v, n in топ))

if __name__ == '__main__':
    главное()
