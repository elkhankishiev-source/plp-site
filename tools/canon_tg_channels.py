#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Канон рабочего контура: лиды идут только через рабочие номера Эльнура и Дарьи.

Эльнур 20.09.2026, дважды поправил меня: «вся работа с лидами идет через рабочие номера
Эльнур и Дарья в тг и ватсап, конект через вазап в срм. Телемост он вроде как для личного.
Зафиксируй навсегда это! Чат боты в тг есть, пишут в рабочих группах и нам на рабочие и
все ок все работает».

Моя ошибка была двойной. Сначала я решил, что раз Wazzup отдал `messageId`, значит
сообщение ушло — и отчитался о восьми доставленных касаниях, которых не было. Потом,
разобравшись, предложил слать через мост telethon — а он для личного и к лидам отношения
не имеет.

Как на самом деле: рабочий контур это WhatsApp и Telegram на рабочих номерах Эльнура
(+66955492587) и Дарьи (+66640709032), подключённые через Wazzup, оттуда же связь с CRM.
Чат-боты в Telegram тоже работают — отвечают в наших группах и на рабочие номера.

Единственное реальное ограничение, и оно не наше: написать ПЕРВЫМ в Telegram по номеру
телефона нельзя. Адрес там это id чата, который появляется только после сообщения от
человека. Поэтому холодное касание идёт в WhatsApp, а Telegram подхватывает разговор,
когда человек уже ответил.

    python3 canon_tg_channels.py            # показать
    python3 canon_tg_channels.py --apply    # записать правило
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
RULE_KEY = 'telegram_three_channels'

CONTENT = """РАБОЧИЕ КАНАЛЫ И ЧЕМ ОНИ ОТЛИЧАЮТСЯ. Зафиксировано Эльнуром 20.09.2026.

ГЛАВНОЕ: ВСЯ РАБОТА С ЛИДАМИ ИДЁТ ЧЕРЕЗ РАБОЧИЕ НОМЕРА ЭЛЬНУРА И ДАРЬИ — в Telegram и
в WhatsApp, подключённые через Wazzup, и оттуда же связь с CRM. Это единственный рабочий
контур. Мост telethon (живой аккаунт) — ЛИЧНОЕ, для работы с лидами не используется.

РАБОЧИЕ КАНАЛЫ (через Wazzup, связаны с CRM):
  • WhatsApp Эльнура +66955492587 и Дарьи +66640709032 — сюда можно писать ПЕРВЫМИ
    по номеру телефона. Это основной путь для холодного касания.
  • Telegram Эльнура и Дарьи (те же номера) — работают для переписки с теми, кто уже
    писал нам: у такого человека есть чат, и ответ уходит в него. Всё это исправно.

ОГРАНИЧЕНИЕ TELEGRAM, не наше: написать ПЕРВЫМ по номеру телефона в Telegram нельзя.
Адресом там служит внутренний id чата, который появляется только после сообщения от
человека. Wazzup на попытку по номеру возвращает messageId, а следом присылает
status=error, BAD_CONTACT. Проверено 20.09 и на номере лида, и на нашем собственном.

ЧАТ-БОТЫ В TELEGRAM работают и нужны: отвечают в рабочих группах и нам на рабочие
номера. К холодным касаниям отношения не имеют.

МОСТ TELETHON (живой аккаунт) — ЛИЧНОЕ. В работе с лидами не участвует.

ОТСЮДА ПОРЯДОК ХОЛОДНОГО КАСАНИЯ:
  • первым пишем в WhatsApp по номеру, с рабочего номера того, кто ведёт сделку в CRM;
  • Telegram подключается, когда человек уже ответил хоть куда-то: тогда его чат есть
    и продолжать можно там;
  • писать первым в Telegram по номеру — нельзя, это не наша настройка, а устройство
    Telegram.

КАК ПРОВЕРЯТЬ ОТПРАВКУ: ответ Wazzup с messageId НЕ означает доставку. Доставка
подтверждается только эхом со статусом, которое приходит вебхуком спустя секунды.
Считать отправленным по ответу сервера — ошибка, из-за неё 19.09 восемь касаний были
записаны как доставленные, хотя не дошли ни одно."""


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
    'domain': 'system',
    'rule_key': RULE_KEY,
    'title': 'РАБОЧИЙ КОНТУР: лиды только через рабочие номера Эльнура и Дарьи (Wazzup → CRM)',
    'content': CONTENT,
    'short': ('Вся работа с лидами — через рабочие номера Эльнура и Дарьи в WhatsApp и Telegram, '
              'подключённые к Wazzup и CRM. Холодное касание — в WhatsApp по номеру. В Telegram '
              'первым по номеру написать нельзя (устройство Telegram), только в существующий чат. '
              'Мост telethon — личное, лидов не касается. messageId ≠ доставка.'),
    'source': 'Эльнур, 20.09.2026',
    'machine_scope': ['brain', 'brain_core'],
    'severity': 'iron',
    'enforced_by': 'канон + touch_send + Wazzup',
}


def main():
    cur = call('/canon_rules?rule_key=eq.%s&select=id' % RULE_KEY)
    print(('обновлю правило #%d' % cur[0]['id']) if cur else 'добавлю новое правило')
    print('\n%s\n\n%s' % (ROW['title'], CONTENT))
    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    out = (call('/canon_rules?id=eq.%d' % cur[0]['id'], 'PATCH', ROW) if cur
           else call('/canon_rules', 'POST', ROW))
    print('\nзаписано: canon_rules #%s, severity=%s' % (out[0]['id'], out[0].get('severity')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
