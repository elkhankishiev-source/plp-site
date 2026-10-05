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
ТОКЕН, КОМУ = env('TG_BOT_TOKEN'), env('TG_TECH_CHAT_ID')
ПРОДАЖИ = ''   # офисный бот, «PLP · Тех офис»


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
    # 04.10.2026: ежедневная сверка (sverka_dnya.py, 07:30): нарушения правил в сообщениях лидам и решения, утверждённые, но не внедрённые.
    try:
        r = urllib.request.Request(SB + '/' + urllib.parse.quote('сверка_дня') + '?select=*&order=' + urllib.parse.quote('день') + '.desc&limit=1',
                                   headers={'apikey': SK, 'Authorization': 'Bearer ' + SK})
        св = (json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or '[]') or [None])[0]
        if св:
            пр = св.get('по_правилам') or {}
            # 05.10.2026 Эльнур: «продажи это продажи, тех это тех» — работа с лидами уходит в «Отдел продаж», в «Тех офис» только техника
            global ПРОДАЖИ
            ПРОДАЖИ = ('📋 Работа с лидами за сутки (%s): сообщений %s, нарушений %s' % (пхукет.strftime('%d.%m'), св.get('сообщений'), св.get('нарушений'))
                       + ''.join('\n• %s: %s' % (k.split(' (')[0], v) for k, v in sorted(пр.items(), key=lambda z: -z[1])[:6])
                       + ''.join('\n  пример %s — %s' % (x.get('номер'), str(x.get('кусок'))[:90]) for x in (св.get('примеры') or [])[:4]))
            текст += '\n📌 Утверждено, но не внедрено: %d' % len(св.get('не_внедрено') or [])
    except Exception as ex:
        текст += '\n\n📋 Сверка не прочиталась: ' + str(ex)[:80]
    # 04.10.2026: обычные отказы привратника за сутки — одной строкой (раньше каждые 20 минут в Тех офис).
    try:
        с = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
        r = urllib.request.Request(SB + '/funnel_events?event_type=eq.gate_decision&ts=gte.' + с
                                   + '&select=metadata&limit=5000', headers={'apikey': SK, 'Authorization': 'Bearer ' + SK})
        ев = json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or '[]')
        пр = {}
        for e in ев:
            m = e.get('metadata') or {}
            if m.get('decision') != 'DENY':
                continue
            for x in (m.get('denies') or []):
                x = str(x)
                x = 'лимит номера в сутки' if 'потолок в сутки' in x else ('канал выключен' if 'канал выключен' in x else
                    ('тихие часы' if x == 'quiet_hours' else ('ждём часы человека или разброс' if x.startswith('плотность') else x[:50])))
                пр[x] = пр.get(x, 0) + 1
        if пр:
            текст += '\n\n🚦 Привратник за сутки не пустил: ' + ', '.join('%s ×%d' % (k, v) for k, v in sorted(пр.items(), key=lambda z: -z[1])[:5])
    except Exception as ex:
        текст += '\n\n🚦 Отказы привратника не прочитались: ' + str(ex)[:80]
    if '--покажи' in sys.argv:
        print(текст); print('--- в Отдел продаж ---'); print(ПРОДАЖИ)
        return 0
    if ПРОДАЖИ and env('TG_ALERT_CHAT_ID'):
        try:
            urllib.request.urlopen(urllib.request.Request('https://api.telegram.org/bot%s/sendMessage' % ТОКЕН,
                data=json.dumps({'chat_id': env('TG_ALERT_CHAT_ID'), 'text': ПРОДАЖИ[:3900], 'disable_web_page_preview': True}).encode(),
                headers={'Content-Type': 'application/json'}), timeout=60)
            print('итог по лидам ушёл в Отдел продаж')
        except Exception as e:
            print('в Отдел продаж не ушло:', e)
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
