#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Переписка двойника → лента сделки в amoCRM.

Разбор 22.09.2026. Менеджер открывает сделку человека, с которым двойник вёл живой
диалог, и видит пустую ленту. Проверено по сделкам: 412711606 — 35 сообщений в диалоге,
заметок 0; 66954292656 — 29 сообщений, заметок 0. При этом у той, кому ушло ОДНО
холодное касание, в карточке 79 копий одной строки. Картина перевёрнута.
Поле chat_history.synced_to_amocrm стоит false у всех 6843 строк за всё время — поле
есть, ставить его некому. Скрипт закрывает именно эту дыру.

Кладём НЕ по сообщению на заметку, а одну заметку на день разговора: менеджеру нужен
разговор, а не тридцать записей. На этом уже обжигались — см. цикл из 78 заметок
в сделке 23121585 (tools/amo_touch_notes.py).

Путь в amoCRM идёт БЕЗ префикса /api/v4 — вебхук подставляет его сам.

    python3 amo_dialog_notes.py                 # показать, что запишется
    python3 amo_dialog_notes.py --apply         # записать
    python3 amo_dialog_notes.py --days 7        # окно (по умолчанию 30 дней)
"""
import json, os, sys, urllib.request, collections, datetime

APPLY = '--apply' in sys.argv
DAYS = 30
if '--days' in sys.argv:
    DAYS = int(sys.argv[sys.argv.index('--days') + 1])
HOOK = 'https://hub.property-library.com/webhook/amo-write'


def env():
    # читаем ОБА файла: на Маке в ~/.plp_site_supabase.env есть Supabase, но нет ключа
    # вебхука; на сервере /opt/plp-api/.env содержит и то и другое. Раньше цикл
    # прерывался на первом файле и ключ вебхука терялся — отсюда «403 bad key».
    out = {}
    for путь in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env'):
        if not os.path.exists(путь):
            continue
        for ln in open(путь, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1)
                out.setdefault(k, v.strip().strip('"\''))
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}
# Ключ вебхука: сначала окружение, иначе тот же .env, откуда взяты ключи Supabase.
# На сервере он лежит в /opt/plp-api/.env — значит по крону скрипт работает без настройки.
KEY = os.environ.get('PLP_WEBHOOK_KEY') or E.get('PLP_WEBHOOK_KEY', '')


def sb(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def amo(method, ep, payload):
    body = json.dumps({'m': method, 'ep': ep, 'payload': payload}).encode()
    r = urllib.request.Request(HOOK, data=body, method='POST',
                               headers={'Content-Type': 'application/json', 'x-plp-key': KEY})
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.read().decode()[:200]


# служебные каналы: офисный бот — это переписка с сотрудниками, ей в карточке клиента не место
СЛУЖЕБНЫЕ = {'office_bot', 'qa_test', 'tg_backfill'}
ИМЯ_КАНАЛА = {'whatsapp': 'WhatsApp', 'telegram': 'Telegram', 'tg_userbot': 'Telegram',
              'tg_bot': 'Telegram (бот)'}


def свои_номера():
    """Номера участников системы: их переписка — не диалог с клиентом."""
    свои = set()
    for r in sb('/system_participants?select=phones,tg_ids'):
        for p in (r.get('phones') or []):
            свои.add(str(p))
        for t in (r.get('tg_ids') or []):
            свои.add(str(t))
    return свои


def main():
    свои = свои_номера()
    с = (datetime.datetime.utcnow() - datetime.timedelta(days=DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    # Supabase отдаёт не больше 1000 строк за запрос — листаем, иначе часть диалогов
    # просто не попадёт в CRM и это будет незаметно (ровно та ошибка, на которой
    # я уже спотыкался: «проверил на одном прогоне и решил, что всё»).
    строки = []
    сдвиг = 0
    while True:
        порция = sb('/chat_history?synced_to_amocrm=is.false&ts=gte.' + с +
                    '&phone_norm=not.is.null&select=id,phone_norm,channel,role,content,ts,source'
                    '&order=ts.asc&limit=1000&offset=%d' % сдвиг)
        строки += порция
        if len(порция) < 1000:
            break
        сдвиг += 1000
    print('несинхронизированных реплик за %d дн.: %d' % (DAYS, len(строки)))

    # группируем: сделка × день × канал → один разговор
    группы = collections.OrderedDict()
    без_сделки = collections.Counter()
    лид_кэш = {}
    for s in строки:
        ph = str(s.get('phone_norm') or '')
        if not ph or ph in свои:
            continue
        if str(s.get('source') or '') in СЛУЖЕБНЫЕ:
            continue
        if not str(s.get('content') or '').strip():
            continue
        if ph not in лид_кэш:
            r = sb('/rpc/lead_for_phone', 'POST', {'p': ph})
            лид_кэш[ph] = (r[0]['lead_id'] if r else None)
        лид = лид_кэш[ph]
        if not лид:
            без_сделки[ph] += 1
            continue
        день = str(s['ts'])[:10]
        группы.setdefault((лид, день, s.get('channel') or '—'), []).append(s)

    print('людей без открытой сделки в CRM (пропускаю): %d реплик у %d человек'
          % (sum(без_сделки.values()), len(без_сделки)))
    print('заметок к записи: %d\n' % len(группы))

    записано = 0
    for (лид, день, канал), реплики in группы.items():
        д = datetime.datetime.strptime(день, '%Y-%m-%d').strftime('%d.%m.%Y')
        шапка = 'Переписка %s, %s — %d сообщ.' % (д, ИМЯ_КАНАЛА.get(канал, канал), len(реплики))
        тело = []
        for s in реплики:
            кто = 'Клиент' if s['role'] == 'user' else 'Мы'
            час = str(s['ts'])[11:16]
            текст = ' '.join(str(s['content']).split())
            тело.append('%s %s: %s' % (час, кто, текст[:700]))
        текст = шапка + '\n\n' + '\n'.join(тело)
        if len(текст) > 9000:
            текст = текст[:9000] + '\n…обрезано'
        if not APPLY:
            print('— сделка %s · %s · %s' % (лид, д, ИМЯ_КАНАЛА.get(канал, канал)))
            if записано < 3:
                print('   ' + текст[:400].replace('\n', '\n   ') + '\n')
            записано += 1
            continue
        if not KEY:
            print('нет ключа PLP_WEBHOOK_KEY в окружении — отменяю')
            return 1
        try:
            res = amo('POST', 'leads/%d/notes' % лид, [{'note_type': 'common', 'params': {'text': текст}}])
        except Exception as ex:
            print('   ✗ сделка %s %s: %s' % (лид, д, str(ex)[:110]))
            continue
        if '"id"' not in res:
            print('   ✗ сделка %s %s: %s' % (лид, д, res[:110]))
            continue
        # отметку ставим только после подтверждённой записи, каждой реплике отдельно:
        # так повторный прогон не задвоит заметку, даже если упадёт на середине
        for s in реплики:
            try:
                sb('/chat_history?id=eq.%d' % s['id'], 'PATCH',
                   {'synced_to_amocrm': True, 'amocrm_lead_id': лид})
            except Exception as ex:
                print('   ⚠ заметка записана, отметку не поставил на реплике %s: %s' % (s['id'], str(ex)[:70]))
        записано += 1

    if not APPLY:
        print('\nЭто отчёт, ничего не записано. Записать: --apply')
    else:
        print('\nзаписано заметок: %d из %d' % (записано, len(группы)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
