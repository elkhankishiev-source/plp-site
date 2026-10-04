#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сводка тревог за сутки в «PLP · Тех офис». Серверная версия.

04.10.2026. Сводка жила на Маке (~/plp-крон/сводка_тревог.py) и не приходила, когда Мак спал.
Эльнур «го»: расписания с Мака на сервер. Здесь ходим в базу служебным ключом сервера
(в .env), а не ключом администратора проекта: его на сервер не кладём.
Сторожа уроков и реестр системы на Маке остались: их команды написаны с путями Мака.

Модель не зовётся. Только две функции базы и Telegram.

    python3 svodka_trevog.py           # собрать и отправить
    python3 svodka_trevog.py --покажи  # показать, не отправляя
"""
import json, sys, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB = env('SUPABASE_URL').rstrip('/') + '/rest/v1'
SK = env('SUPABASE_SERVICE_KEY')
ТОКЕН, КОМУ = env('TG_BOT_TOKEN'), env('TG_TECH_CHAT_ID')   # офисный бот, «PLP · Тех офис»


def rpc(имя, тело=None):
    r = urllib.request.Request(SB + '/rpc/' + urllib.parse.quote(имя), method='POST',
                               data=json.dumps(тело or {}).encode(),
                               headers={'apikey': SK, 'Authorization': 'Bearer ' + SK,
                                        'Content-Type': 'application/json'})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=90).read().decode() or 'null')
    except urllib.error.HTTPError as e:
        raise SystemExit('база, %s: %s' % (имя, e.read().decode()[:300]))


def главное():
    if '--покажи' not in sys.argv:
        rpc('погасить_крикунов')   # меняет базу, поэтому только при настоящей отправке
    строки = rpc('сводка_тревог') or []
    пхукет = datetime.now(timezone.utc) + timedelta(hours=7)
    if not строки:
        текст = 'Сводка за сутки, %s\n\nТихо: ни одной тревоги.' % пхукет.strftime('%d.%m %H:%M')
    else:
        части, текущий = [], None
        for с in строки:
            if с['раздел'] != текущий:
                текущий = с['раздел']
                части.append('\n' + текущий)
            части.append('• ' + с['строка'])
        текст = 'Сводка за сутки, %s\n%s' % (пхукет.strftime('%d.%m %H:%M'), '\n'.join(части))
    if '--покажи' in sys.argv:
        print(текст)
        return 0
    r = urllib.request.Request('https://api.telegram.org/bot%s/sendMessage' % ТОКЕН,
                               data=json.dumps({'chat_id': КОМУ, 'text': текст[:3900],
                                                'disable_web_page_preview': True}).encode(),
                               headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(r, timeout=60)
        print('%s сводка отправлена, строк %d' % (пхукет.strftime('%d.%m %H:%M'), len(строки)))
    except urllib.error.HTTPError as e:
        print('не ушло:', e.read().decode()[:200])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(главное())
