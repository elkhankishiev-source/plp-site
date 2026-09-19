#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправщик касаний учится писать в Telegram по номеру человека.

Эльнур 19.09.2026: «сперва пишем ему на ватсап по его номеру, если он там молчит часов
6-9, пишем потом на его тг через его номер, чтобы достучаться, всё идёт как продолжение
единого человека».

Как было. В WF_touch_send есть две ветки отправки:
  • channel='telegram' И есть tg_username → наш бот @elnurphuket_bot;
  • всё остальное → Wazzup, и там ЖЁСТКО прописано chatType:'whatsapp'.
То есть Telegram был доступен только через username и только нашим ботом, а бот первым
писать не может. Отсюда и мой ошибочный вывод «в Telegram этим лидам не достучаться».

Что проверено вживую 19.09: Wazzup принимает chatType:'telegram' с НОМЕРОМ ТЕЛЕФОНА в
chatId и возвращает messageId. Каналы tgapi привязаны к нашим же номерам:
  Эльнур  +66955492587  wa 73fa0d4d…  ↔  tg db2b55be…
  Дарья   +66640709032  wa 35d237fd…  ↔  tg f2a15f1d…

Правка: chatType берётся из строки очереди, а для Telegram канал подменяется на
tg-близнеца ТОГО ЖЕ владельца — человек получает продолжение от того же лица, а не от
другого сотрудника. Ветка с нашим ботом остаётся для тех, у кого есть username.

    python3 vps_touch_tg_channel.py            # показать, что изменится
    python3 vps_touch_tg_channel.py --apply    # записать в черновик сценария
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
NODE = 'Отправить утверждённые'
WF = 'WF_touch_send%'

OLD = """        body: { channelId: (r.source_channel_id
                              ? r.source_channel_id
                              : (String(r.agent||'')==='owner_task'
                                  ? '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793' : $env.WAZZUP_CHANNEL_DEFAULT)),
                chatType: 'whatsapp', chatId: r.phone, text: body } });"""

NEW = """        /* 19.09.2026: один человек — одна история (канон #111). Если касание помечено
           каналом telegram, идём в Telegram ПО НОМЕРУ через tgapi-близнеца того же
           владельца: человек получает продолжение от того же лица, а не от другого. */
        body: (function(){
          var _wa = (r.source_channel_id
                      ? r.source_channel_id
                      : (String(r.agent||'')==='owner_task'
                          ? '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793' : $env.WAZZUP_CHANNEL_DEFAULT));
          var _TG = { '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793': 'db2b55be-11da-4bc2-abcb-c8562f0fbed4',
                      '35d237fd-a3be-4496-886a-418dfa09c529': 'f2a15f1d-a252-448c-a7d2-c6ee5edfb7a0' };
          var _tg = String(r.channel) === 'telegram';
          return { channelId: (_tg ? (_TG[_wa] || 'db2b55be-11da-4bc2-abcb-c8562f0fbed4') : _wa),
                   chatType: (_tg ? 'telegram' : 'whatsapp'), chatId: r.phone, text: body };
        })() });"""


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
    if 'канон #111' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: касание с channel=telegram уходит в Telegram по номеру,')
        print('через tgapi-канал того же владельца; whatsapp остаётся как был')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909tg$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/touchtg.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    out = subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                          'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/touchtg.sql'],
                         capture_output=True, text=True, timeout=300)
    print('запись:', out.stdout.strip() or out.stderr.strip()[:200])
    print('проверка:', 'ок' if 'канон #111' in code() else 'НЕ ПРИМЕНИЛОСЬ')
    print('\nЭто ЧЕРНОВИК. В бой пойдёт вместе с n8n_publish.py --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
