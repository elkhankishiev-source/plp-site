#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ночная защита отправки: одобренное касание ждёт утра в поясе человека.

Эльнур 18.09.2026: «главное не ночь, когда клиент спит по его поясу».

Дыра была такая. В базе есть правильная механика: `touch_slot` двигает время касания
в окно 10:00–19:00 по часовому поясу самого человека (пояс берётся из кода номера),
воскресенье пропускает. Но отправщик `WF_touch_send` брал ВСЕ строки со статусом
«одобрено» и слал их немедленно, не глядя на поле `scheduled_at`. То есть расписание
существовало, а исполнитель его игнорировал: одобрил в 16:00 по Пхукету — человеку
в Калифорнии ушло в 02:00 ночи.

Правка: отправщик берёт только те строки, у которых время уже наступило
(или не задано вовсе). Само расписание не трогаем, оно и так считается правильно.

    python3 vps_touch_night.py            # показать, что изменится
    python3 vps_touch_night.py --apply    # применить и перезапустить n8n
"""
import subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
NODE = 'Отправить утверждённые'
WF = 'WF_touch_send%'

OLD = "url: SB + '/touch_queue?status=eq.approved&order=id.asc&limit=8' });"
NEW = ("/* 18.09.2026: не будим людей ночью. Время касания уже посчитано в их поясе\n"
       "     (touch_slot, окно 10:00–19:00), отправщик обязан его дождаться. */\n"
       "    url: SB + '/touch_queue?status=eq.approved&or=(scheduled_at.is.null,scheduled_at.lte.'\n"
       "          + encodeURIComponent(new Date().toISOString()) + ')&order=id.asc&limit=8' });")


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
    if 'не будим людей ночью' in src:
        print('ночная защита уже стоит')
        return 0
    if OLD not in src:
        print('якорь не найден — правка отменена')
        return 1
    print('будет изменено: отправщик ждёт времени из расписания, посчитанного по поясу человека')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = src.replace(OLD, NEW, 1)
    tag = '$plpnight$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отмена')
        return 1
    sql = ("update workflow_entity set nodes = (\n"
           "  select jsonb_agg(case when n->>'name'='%s'\n"
           "    then jsonb_set(n, '{parameters,jsCode}', to_jsonb(%s%s%s::text))\n"
           "    else n end)\n"
           "  from jsonb_array_elements(nodes::jsonb) n)\n"
           "where name like '%s';" % (NODE, tag, fixed, tag, WF))
    ssh('cat > /tmp/night.sql', sql)
    out = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/night.sql')
    print(out.stdout.strip() or out.stderr[:200])
    if 'не будим людей ночью' not in code():
        print('НЕ ПРИМЕНИЛОСЬ')
        return 1
    print('  ✓ проверка: отправщик читает расписание')
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
