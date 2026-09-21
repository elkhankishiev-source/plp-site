#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправщик учится писать в Telegram по chat_id, а не только по @username.

Нашлось на живом горячем лиде 19.09.2026. Валери (PLP-001442) общается с нашим
клиентским ботом: все её сообщения — это `/start` в Telegram. Username у неё нет,
есть только числовой id 412711606, он же записан в поле телефона.

В WF_touch_send ветка Telegram выглядела так:

    if (r.channel === 'telegram' && r.tg_username) { …бот шлёт на '@'+username… }
    else { …Wazzup, chatId = r.phone… }

То есть без username касание проваливалось в ветку Wazzup и уходило в WhatsApp на
«номер» 412711606, которого не существует. Человек, с которым мы уже договорились о
созвоне, оказался недостижим — при том что он сам писал нашему боту и бот имеет полное
право ему ответить.

Правка: канал `tg_bot` всегда идёт через нашего бота, адрес — `@username`, если он есть,
иначе числовой chat_id. Канал `telegram` работает как раньше (Wazzup по номеру, правка
канона #111), плюс username через бота.

    python3 vps_touch_tg_byid.py            # показать, что изменится
    python3 vps_touch_tg_byid.py --apply    # записать в черновик сценария
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
WF = 'WF_touch_send%'
NODE = 'Отправить утверждённые'

OLD = """    if (String(r.channel) === 'telegram' && r.tg_username) {
      await _h.httpRequest({ timeout: 25000, method: 'POST', json: true,
        url: 'https://api.telegram.org/bot' + $env.TG_ELNURPHUKET_TOKEN + '/sendMessage',
        body: { chat_id: '@' + String(r.tg_username).replace(/^@/, ''), text: body } });
    } else {"""

NEW = """    /* 19.09.2026: наш бот умеет писать и по числовому chat_id, не только по @username.
       Человек, который сам нажал /start, боту доступен — а без этой ветки касание
       проваливалось в WhatsApp на «номер», которого нет.
       Разбор — в tools/vps_touch_tg_byid.py */
    var _чБот = (String(r.channel) === 'tg_bot')
             || (String(r.channel) === 'telegram' && r.tg_username);
    if (_чБот) {
      var _адрес = r.tg_username
        ? ('@' + String(r.tg_username).replace(/^@/, ''))
        : String(r.phone || '').replace(/\\D/g, '');
      if (!_адрес) { throw new Error('некуда слать: ни username, ни chat_id'); }
      await _h.httpRequest({ timeout: 25000, method: 'POST', json: true,
        url: 'https://api.telegram.org/bot' + $env.TG_ELNURPHUKET_TOKEN + '/sendMessage',
        body: { chat_id: _адрес, text: body } });
    } else {"""


def psql(sql):
    r = subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                        'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin'],
                       input=sql, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:400])
    return r.stdout.strip()


def code():
    return psql("select n->'parameters'->>'jsCode' from workflow_entity w, "
                "jsonb_array_elements(w.nodes::jsonb) n where w.name like '%s' "
                "and n->>'name'='%s';" % (WF, NODE))


def main():
    js = code()
    if not js:
        print('узел не найден')
        return 1
    if 'по числовому chat_id' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: канал tg_bot шлёт через нашего бота по chat_id или @username')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909tgid$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/tgid.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                    'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/tgid.sql'],
                   capture_output=True, text=True, timeout=300)
    print('черновик: %s' % ('ок' if 'по числовому chat_id' in code() else 'НЕ ЗАПИСАЛОСЬ'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
