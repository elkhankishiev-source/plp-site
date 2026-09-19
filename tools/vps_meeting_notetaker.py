#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расшифровщик заходит на созвон сам: бота приглашаем в момент создания встречи.

Эльнур 18.09.2026, после созвона по Estella без записи: «почему ты сразу на автомате
не сделал, чтобы всегда был бот».

Справедливо. Аккаунт Fireflies есть, права админа есть, израсходовано 0 минут,
интеграций ноль — то есть инструмент был, а пользоваться им никто не начал.
Классическое «настроено, но мертво», ровно тот патерн, который я же и ищу.

Правка: когда система бронирует встречу (WF_meeting → узел Prep собирает тело
события Google Календаря), в список участников добавляется fred@fireflies.ai.
Fireflies заходит в созвон по приглашению, без всяких интеграций с календарём, и
пишет расшифровку с первой минуты.

Касается только созвонов, которые бронирует система. Встречи, созданные руками в
календаре, этим не покрываются — для них нужен либо разовый коннект календаря в
Fireflies, либо сторож (делается отдельно).

    python3 vps_meeting_notetaker.py            # показать, что изменится
    python3 vps_meeting_notetaker.py --apply    # применить и перезапустить n8n
"""
import json, subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'

OLD = "conferenceSolutionKey:{type:'hangoutsMeet'}}}};"
NEW = ("conferenceSolutionKey:{type:'hangoutsMeet'}}},"
       "\n    /* 18.09.2026: расшифровщик заходит сам. Эльнур: «почему ты сразу на автомате"
       "\n       не сделал, чтобы всегда был бот». Приглашение = участие, интеграция не нужна. */"
       "\n    attendees:[{email:'fred@fireflies.ai'}]};")


def ssh(cmd, inp=None):
    return subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, cmd], input=inp,
                          capture_output=True, text=True, timeout=180)


def psql_file(path):
    r = ssh("docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < " + path)
    if r.returncode:
        raise RuntimeError(r.stderr[:400])
    return r.stdout.strip()


def psql(sql):
    r = ssh("docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin", sql)
    if r.returncode:
        raise RuntimeError(r.stderr[:400])
    return r.stdout.strip()


def main():
    cur = psql("select n->'parameters'->>'jsCode' from workflow_entity w, "
               "jsonb_array_elements(w.nodes::jsonb) n where w.name like 'WF_meeting%' "
               "and n->>'name'='Prep';")
    if 'fred@fireflies.ai' in cur:
        print('расшифровщик уже приглашается — ничего не меняю')
        return 0
    if OLD not in cur:
        print('якорь в узле Prep не найден — правка отменена')
        return 1
    print('будет изменено: в тело встречи Google Календаря добавляется участник fred@fireflies.ai')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    new_code = cur.replace(OLD, NEW, 1)
    # Долларовые кавычки: в коде узла полно одинарных кавычек и переносов строк,
    # через переменные psql они ломаются (первая попытка молча не применилась).
    tag = '$plp1809$'
    if tag in new_code:
        print('метка долларовых кавычек встретилась в коде — правка отменена')
        return 1
    sql = ("update workflow_entity set nodes = (\n"
           "  select jsonb_agg(case when n->>'name'='Prep'\n"
           "    then jsonb_set(n, '{parameters,jsCode}', to_jsonb(" + tag + new_code + tag + "::text))\n"
           "    else n end)\n"
           "  from jsonb_array_elements(nodes::jsonb) n)\n"
           "where name like 'WF_meeting%';")
    ssh("cat > /tmp/prep.sql", sql)
    print(psql_file('/tmp/prep.sql'))
    chk = psql("select case when n->'parameters'->>'jsCode' like '%fred@fireflies.ai%' "
               "then 'приглашение на месте' else 'НЕ ПРИМЕНИЛОСЬ' end "
               "from workflow_entity w, jsonb_array_elements(w.nodes::jsonb) n "
               "where w.name like 'WF_meeting%' and n->>'name'='Prep';")
    print(chk)
    if 'НЕ ПРИМЕНИЛОСЬ' in chk:
        return 1
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен, чтобы перечитать сценарий')
    return 0


if __name__ == '__main__':
    sys.exit(main())
