#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привязывает переписку к сделке: открываешь карточку — и видишь разговор.

Эльнур 21.09.2026: «срмка молчит и никто с ней тоже не работает?»

Сверка показала, в чём дело. Связь не рвётся — её вообще никто не ставит.
У ВСЕХ строк `chat_history` поле `amocrm_lead_id` пустое. Это значит:

  • в карточке сделки не видно разговора — менеджер открывает лид и не понимает,
    о чём вообще шла речь;
  • отчёты по сделке считают ноль касаний, хотя человеку писали;
  • двойник при следующем заходе не может опереться на то, что уже обсуждалось
    в рамках этой сделки.

Почему так вышло. Каждый канал (WhatsApp, Telegram, Instagram, сайт) пишет
строку истории своим узлом в n8n, и ни один из них не передаёт номер сделки:
в теле запроса только phone, role, content, channel, source. Поле в таблице
есть с самого начала — заполнять его просто забыли во всех восьми местах сразу.

Чинить в восьми сценариях — восемь шансов ошибиться и восемь публикаций. Связь
ставим в одном месте и для всех каналов сразу: по номеру телефона находим
сделку, которую система УЖЕ выбрала для этого человека (`client_profiles.
amocrm_lead_id`), а если профиля нет — через контакт в CRM по его номеру.

Какую сделку берём, если их несколько. Ту, что стоит в профиле. Это не наш
выбор, а тот, который система сделала раньше: по канону разные воронки — это
разные обращения одного человека, и склеивать их нельзя.

    python3 link_chat_to_deals.py            # показать, что свяжется
    python3 link_chat_to_deals.py --apply    # связать
    python3 link_chat_to_deals.py --apply --hours 2   # только свежее (для крона)
"""
import json, os, sys, urllib.request, datetime

APPLY = '--apply' in sys.argv
ЧАСЫ = None
if '--hours' in sys.argv:
    ЧАСЫ = int(sys.argv[sys.argv.index('--hours') + 1])


def env():
    out = {}
    путь = os.path.expanduser('~/.plp_site_supabase.env')
    if not os.path.exists(путь):
        путь = '/opt/plp-api/.env'
    for ln in open(путь, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    try:
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read().decode()
        return json.loads(raw) if raw.strip() else []
    except Exception as ex:
        print('   (база не ответила: %s)' % str(ex)[:70])
        return []


def страницами(path, шаг=1000, предел=20000):
    out, off = [], 0
    while off < предел:
        b = call(path + '&limit=%d&offset=%d' % (шаг, off))
        out += b
        if len(b) < шаг:
            break
        off += шаг
    return out


def main():
    условие = '/chat_history?amocrm_lead_id=is.null&phone_norm=not.is.null&select=id,phone_norm,ts'
    if ЧАСЫ:
        с = (datetime.datetime.utcnow() - datetime.timedelta(hours=ЧАСЫ)).strftime('%Y-%m-%dT%H:%M:%S')
        условие += '&ts=gte.' + с
    строки = страницами(условие + '&order=id.desc')
    if not строки:
        print('[связь] нечего связывать')
        return 0

    номера = sorted({str(x['phone_norm']) for x in строки if x.get('phone_norm')})
    print('строк без сделки: %d, разных номеров: %d' % (len(строки), len(номера)))

    # номер → сделка: сначала выбор системы из профиля, потом контакт в CRM
    сделка = {}
    for i in range(0, len(номера), 40):
        часть = ','.join(номера[i:i + 40])
        for p in call('/client_profiles?phone_norm=in.(%s)&amocrm_lead_id=not.is.null'
                      '&select=phone_norm,amocrm_lead_id' % часть):
            сделка[str(p['phone_norm'])] = p['amocrm_lead_id']

    нет_профиля = [n for n in номера if n not in сделка]
    через_контакт = 0
    for i in range(0, len(нет_профиля), 40):
        часть = ','.join(нет_профиля[i:i + 40])
        пары = call('/crm_contact_phones?phone_norm=in.(%s)&select=phone_norm,contact_id' % часть)
        if not пары:
            continue
        ids = sorted({str(x['contact_id']) for x in пары if x.get('contact_id')})
        кон = {}
        for j in range(0, len(ids), 40):
            for c in call('/crm_contacts?id=in.(%s)&select=id,lead_ids' % ','.join(ids[j:j + 40])):
                лиды = c.get('lead_ids') or []
                if лиды:
                    кон[str(c['id'])] = лиды[-1]     # последняя сделка контакта
        for x in пары:
            lid = кон.get(str(x.get('contact_id')))
            if lid and str(x['phone_norm']) not in сделка:
                сделка[str(x['phone_norm'])] = lid
                через_контакт += 1

    план = [(x['id'], сделка[str(x['phone_norm'])]) for x in строки
            if str(x.get('phone_norm')) in сделка]
    без = len(строки) - len(план)
    print('нашли сделку: %d строк (%d номеров через профиль, %d через контакт в CRM)'
          % (len(план), len(сделка) - через_контакт, через_контакт))
    print('останутся без сделки: %d строк — у этих номеров сделки в CRM нет вовсе' % без)

    if not APPLY:
        по_сделкам = {}
        for _, lid in план:
            по_сделкам[lid] = по_сделкам.get(lid, 0) + 1
        print('\nсамые многословные сделки:')
        for lid, n in sorted(по_сделкам.items(), key=lambda z: -z[1])[:8]:
            print('   сделка %-12s %d сообщений' % (lid, n))
        print('\nЭто отчёт. Связать: --apply')
        return 0

    # пишем пачками по сделке: одна сделка — один запрос на все её строки
    по_сделкам = {}
    for sid, lid in план:
        по_сделкам.setdefault(lid, []).append(sid)
    сделано = 0
    for lid, ids in по_сделкам.items():
        for i in range(0, len(ids), 100):
            часть = ','.join(str(x) for x in ids[i:i + 100])
            call('/chat_history?id=in.(%s)' % часть, 'PATCH', {'amocrm_lead_id': lid})
            сделано += len(ids[i:i + 100])
    print('\nсвязано строк: %d по %d сделкам' % (сделано, len(по_сделкам)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
