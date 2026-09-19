#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Канон: один человек — одна история, каналы это способ достучаться, а не разные люди.

Эльнур 19.09.2026, дословно: «когда берём лид в работу, сперва пишем ему на ватсап по
его номеру, если он там молчит часов 6-9, пишем потом на его тг через его номер, чтобы
достучаться, всё идёт как продолжение единого человека, ведётся одна история на одного
человека, ты не дробишь их на 16 или на разные каналы, ты начинаешь работать с одним
человеком и ты видишь всю историю его существования от начала до конца».

Повод: я доложил «рассылка в Telegram невозможна, ни у кого нет tg_id». Это была ошибка
мышления. tg_id нужен НАШЕМУ боту — он не имеет права писать первым. А у нас есть каналы
Wazzup типа tgapi, привязанные к нашим же номерам, и они пишут в Telegram ПО НОМЕРУ
ТЕЛЕФОНА. Номер у нас есть у всех. Значит достучаться можно, и порядок задан Эльнуром.

Кладём правилом в канон, чтобы это читал мозг, а не только я.

    python3 canon_one_person_one_thread.py            # показать, что будет записано
    python3 canon_one_person_one_thread.py --apply    # записать правило
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
RULE_KEY = 'one_person_one_thread'

CONTENT = """ОДИН ЧЕЛОВЕК — ОДНА ИСТОРИЯ. Зафиксировано Эльнуром 19.09.2026.

ЧЕЛОВЕК ПЕРВИЧЕН, КАНАЛ ВТОРИЧЕН. WhatsApp, Telegram, Instagram, чат сайта, почта — это
способы достучаться до ОДНОГО человека, а не разные люди и не разные переписки. Одна
карточка, одна история, один путь по воронке. Дробить человека по каналам запрещено.

ПОРЯДОК КАСАНИЙ, когда лид взят в работу:
  1. Первым — WhatsApp по его номеру телефона.
  2. Если в WhatsApp молчит 6–9 часов — то же самое продолжение разговора уходит ему
     в Telegram ПО ТОМУ ЖЕ НОМЕРУ (канал Wazzup типа tgapi умеет писать в Telegram по
     номеру, наш собственный бот так не умеет и первым писать не может).
  3. Второе касание — не новое знакомство. Это продолжение той же мысли, тем же именем,
     тем же тоном: «пишу сюда, вдруг так удобнее». Заново не здороваемся и заново не
     представляемся.

ЧТО ЭТО ЗНАЧИТ В РАБОТЕ:
  • Взяв человека в работу, участник видит ВСЮ его историю от первого касания до
    последнего, из всех каналов сразу, а не кусок из одного мессенджера.
  • Ответ в любом канале продолжает общий разговор: знание из WhatsApp доступно в
    Telegram и наоборот.
  • Смена канала — не смена персоны. Кто начал разговор, тот его и ведёт дальше.
  • «Нет tg_id» не повод бросить человека: есть номер — значит есть Telegram-путь.

ИСТИНА ИСТОРИИ: chat_history ведётся по номеру человека (phone_norm), канал — лишь
пометка на строке. Контекст мозгу собирается по номеру, без деления по каналам."""


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
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
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


ROW = {
    'domain': 'sales',
    'rule_key': RULE_KEY,
    'title': 'ОДИН ЧЕЛОВЕК — ОДНА ИСТОРИЯ: WhatsApp, через 6–9 часов Telegram по тому же номеру',
    'content': CONTENT,
    'short': ('Человек первичен, канал вторичен: одна карточка и одна история на все каналы. '
              'Первым пишем в WhatsApp по номеру; молчит 6–9 часов — продолжаем ТУ ЖЕ переписку '
              'в Telegram по тому же номеру, не здороваясь заново. Каналом человека не дробим.'),
    'source': 'Эльнур, 19.09.2026, переписка',
    # без machine_scope правило ложится со scope ['human'] и мозг его не читает —
    # ровно «настроено, но мертво»; brain = живой мозг на VPS, brain_core = копия в n8n
    'machine_scope': ['brain', 'brain_core'],
    'severity': 'iron',
    'enforced_by': 'canon + touch_escalate.py + WF_touch_send',
}


def main():
    cur = call('/canon_rules?rule_key=eq.%s&select=id,title' % RULE_KEY)
    print(('обновлю правило #%d' % cur[0]['id']) if cur else 'добавлю новое правило')
    print('\n%s\n\n%s' % (ROW['title'], CONTENT))
    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    if cur:
        out = call('/canon_rules?id=eq.%d' % cur[0]['id'], 'PATCH', ROW)
    else:
        out = call('/canon_rules', 'POST', ROW)
    print('\nзаписано: canon_rules #%s, severity=%s' % (out[0]['id'], out[0].get('severity')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
