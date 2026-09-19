#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 329: не отвечаем на старые сообщения, которые Wazzup подсовывает из истории.

18.09.2026. Эльнур: «я открыл ватсап, там ток два наших сообщения… ты глючишь,
будь внимательнее, сверяй!». Он прав, я ошибся, и вот что было на самом деле.

Мы написали Ирине в 16:03. Через 14 секунд прилетело «входящее» от неё —
«Но Рада познакомиться )», и двойник на него ответил. В чате у Эльнура при этом
только два НАШИХ сообщения: она ничего не писала.

Разобрал сырой вебхук. Поле dateTime у этого сообщения:

    "dateTime": "2025-11-11T15:39:00.002Z"

Это её сообщение от 11 НОЯБРЯ 2025 года, почти годичной давности. Когда наше касание
создало чат, Wazzup отдал вместе с ним кусок старой переписки — она осталась от
прежнего владельца номера. Признака «это история» в вебхуке нет, стоит обычный
inbound, поэтому система приняла его за свежую реплику и ответила. Отсюда и два
сообщения подряд незнакомому человеку — худшее, что можно сделать на новом номере.

Правка: на входе проверяем возраст сообщения. Старше пятнадцати минут — не наше
«сейчас», в мозг не идёт и ответа не будет.

    python3 vps_wa_stale.py            # показать, что изменится
    python3 vps_wa_stale.py --apply    # применить и перезапустить n8n
"""
import subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
WF = 'WF_wa_wazzup%'
NODE = 'Parse WA'

OLD = "if(m.fromMe||m.isEcho||m.status==='outbound'||m.status==='read'||m.status==='delivered'||m.status==='sent')continue;"
NEW = (OLD +
       "/* 18.09.2026 правка 329: Wazzup вместе с новым чатом отдаёт СТАРУЮ переписку. "
       "11.09 так прилетела реплика Ирины от 11.11.2025, и двойник ответил на неё как на "
       "свежую — человек получил два сообщения подряд. Отвечаем только на свежее. */"
       "try{var _age329=Date.parse(m.dateTime||m.datetime||m.time||'');"
       "if(_age329 && (_now-_age329) > 15*60*1000){continue;}}catch(_e329){}")


def ssh(cmd, inp=None):
    return subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, cmd], input=inp,
                          capture_output=True, text=True, timeout=180)


def psql(sql):
    r = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin', sql)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def code():
    return psql("select n->'parameters'->>'jsCode' from workflow_entity w, "
                "jsonb_array_elements(w.nodes::jsonb) n where w.name like '%s' and n->>'name'='%s';"
                % (WF, NODE))


def main():
    src = code()
    if 'правка 329' in src:
        print('правка 329 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('якорь найден %d раз — отмена' % src.count(OLD))
        return 1
    print('будет изменено: сообщения старше 15 минут не считаются свежими и без ответа')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = src.replace(OLD, NEW, 1)
    tag = '$plpstale$'
    if tag in fixed:
        print('метка встретилась в коде — отмена')
        return 1
    sql = ("update workflow_entity set nodes = (\n"
           "  select jsonb_agg(case when n->>'name'='%s'\n"
           "    then jsonb_set(n, '{parameters,jsCode}', to_jsonb(%s%s%s::text))\n"
           "    else n end)\n"
           "  from jsonb_array_elements(nodes::jsonb) n)\n"
           "where name like '%s';" % (NODE, tag, fixed, tag, WF))
    ssh('cat > /tmp/stale.sql', sql)
    out = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/stale.sql')
    print(out.stdout.strip() or out.stderr[:200])
    if 'правка 329' not in code():
        print('НЕ ПРИМЕНИЛОСЬ')
        return 1
    print('  ✓ проверка возраста сообщения на месте')
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
