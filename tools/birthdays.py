#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поздравление с днём рождения от компании.

Эльнур 02.10.2026: «дни рождения поздравлять от лица компании»; текст одобрен его «го» 02.10:
«{Имя}, с днём рождения! Здоровья, тепла и много солнца в этом году. Команда Property Library Phuket».

Откуда даты: clients."день_рождения" (заполняется только из документа или со слов человека,
источник в соседнем поле). Раз в сутки ищем тех, у кого сегодня день рождения ПО ИХ ЧАСАМ, и ставим
поздравление в обычную очередь касаний touch_queue (status approved, kind 'birthday', agent owner_task —
поручение владельца: купившим двойник пишет только по апруву Эльнура, а это его апрув) на утро по их
часам — дальше привратник, окно 08:00–20:30 и отправщик WF_touch_send, как у всех касаний.
Лестницу касаний это не сдвигает: планировщик смотрит только свои виды (silence, cold).

Не ставим, если: нет номера; карточка своя (is_internal); имя не годится для обращения
(латиница, «Новый лид RED…», пусто) — такое уходит списком в вывод, руками решаем; в этом году уже
поздравляли.

    python3 tools/birthdays.py                       # показать, кого поздравили бы сегодня
    python3 tools/birthdays.py --apply               # поставить в очередь
    python3 tools/birthdays.py --дата 2026-10-15     # проверить на другой день (без записи)
"""
import datetime, json, re, sys, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

APPLY = '--apply' in sys.argv
ДАТА = sys.argv[sys.argv.index('--дата') + 1] if '--дата' in sys.argv else None
ТЕКСТ = '{имя}, с днём рождения! Здоровья, тепла и много солнца в этом году. Команда Property Library Phuket'
WA_ЭЛЬНУР = '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793'   # рабочий WhatsApp Эльнура (канон №129)


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB, SK = env('SUPABASE_URL').rstrip('/') + '/rest/v1', env('SUPABASE_SERVICE_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}


def rpc(name, body):
    r = urllib.request.Request(SB + '/rpc/' + urllib.parse.quote(name), method='POST',
                               data=json.dumps(body).encode(), headers=H)
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or 'null')


def get(path):
    r = urllib.request.Request(SB + path, headers=H)
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or '[]')


def имя_годится(n):
    n = (n or '').strip()
    return bool(re.fullmatch(r'[А-ЯЁ][а-яё]+(-[А-ЯЁ][а-яё]+)?', n.split(' ')[0])) and not re.search(r'лид|сделка|RED|\|', n)


def main():
    люди = get('/clients?select=client_id,code,name,phone,is_internal,' + urllib.parse.quote('день_рождения')
               + '&' + urllib.parse.quote('день_рождения') + '=not.is.null')
    ставим, руками = [], []
    for ч in люди:
        if ч.get('is_internal'):
            continue
        tz = (rpc('tz_for_phone', {'p_phone': ч['phone']}) if ч.get('phone') else None) or 'Asia/Bangkok'
        сегодня = datetime.date.fromisoformat(ДАТА) if ДАТА else \
            datetime.datetime.now(datetime.timezone.utc).astimezone(ZoneInfo(tz)).date()
        др = datetime.date.fromisoformat(ч['день_рождения'])
        if (др.month, др.day) != (сегодня.month, сегодня.day):
            continue
        if not ч.get('phone'):
            руками.append('%s: сегодня день рождения, но номера нет — поздравить через близких или руками' % ч['code']); continue
        if not имя_годится(ч.get('name')):
            руками.append('%s: имя «%s» не годится для обращения' % (ч['code'], ч.get('name'))); continue
        уже = get('/touch_queue?select=id&kind=eq.birthday&phone=eq.%s&created_at=gte.%s-01-01' % (ч['phone'], сегодня.year))
        if уже:
            continue
        канал = get('/chat_history?select=channel&phone=eq.%s&order=id.desc&limit=1' % ч['phone'])
        канал = (канал[0]['channel'] if канал else 'whatsapp') or 'whatsapp'
        канал = 'telegram' if канал == 'telegram' else 'whatsapp'
        # 09:00 по часам человека; окно и праздники досчитывает touch_slot
        утро = datetime.datetime.combine(сегодня, datetime.time(9, 0), tzinfo=ZoneInfo(tz))
        когда = rpc('touch_slot', {'p_at': утро.astimezone(datetime.timezone.utc).isoformat(), 'p_phone': ч['phone']})
        ставим.append({'phone': ч['phone'], 'channel': канал, 'agent': 'owner_task', 'kind': 'birthday',   # поручение владельца: правило «купившим только по апруву» его пропускает
                      
                       'occasion': 'день рождения (источник даты: карточка клиента)',
                       'body': ТЕКСТ.format(имя=ч['name'].split(' ')[0]), 'status': 'approved',
                       'scheduled_at': когда, 'persona': 'Эльнур', 'source_channel_id': WA_ЭЛЬНУР,
                       'decided_by': 'Эльнур 02.10: текст поздравления одобрен'})
    print('дней рождения в карточках: %d; поздравить сегодня: %d%s' % (
        len(люди), len(ставим), '' if APPLY and not ДАТА else ' (без записи)'))
    for т in ставим:
        print('  ✓ %s · %s · %s' % (т['phone'][:4] + '…', т['channel'], т['body'][:60]))
    for р in руками:
        print('  ⚠ ' + р)
    if APPLY and not ДАТА and ставим:
        r = urllib.request.Request(SB + '/touch_queue', method='POST', data=json.dumps(ставим, ensure_ascii=False).encode(),
                                   headers=dict(H, Prefer='return=minimal'))
        urllib.request.urlopen(r, timeout=60)
        print('поставлено в очередь: %d' % len(ставим))
    return 0


if __name__ == '__main__':
    sys.exit(main())
