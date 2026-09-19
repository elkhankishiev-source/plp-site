#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 328: коллег и застройщиков не двигаем по воронке покупателей.

Эльнур 18.09.2026: «Коллег не надо вести по воронке, я уже говорил».

Опасность была прямая. Расчёт этапа зашит на этапы воронки PLP WEB v2 и роль
собеседника не смотрит вовсе. Камиллу мы только что перевели в воронку «Коллеги»,
и стоило бы ей написать — система выставила бы её сделке этап из воронки покупателей
и утащила бы карточку обратно. То же с любым партнёром.

Правка: расчёт этапа пропускается, если роль собеседника не «lead». Отвечать ему
это не мешает, двигается только воронка.

    python3 vps_stage_role_guard.py            # показать, что изменится
    python3 vps_stage_role_guard.py --apply    # применить и перезапустить n8n
"""
import subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
TARGETS = [('WF_wa_wazzup%', 'Calc Stage WA'),
           ('WF_validator_PROD%', 'Calc Stage')]
GUARD = ("/* 18.09.2026 правка 328: не лид — по воронке покупателей не двигаем. "
         "Эльнур: «коллег не надо вести по воронке». */\n"
         "{const _role328=String((($('Brain').first().json||{}).profile||{}).contact_role||'lead');\n"
         " if(_role328!=='lead'){ try{console.log('[этап 328] роль '+_role328+': воронку не трогаем');}catch(e){} return []; }}\n")


def ssh(cmd, inp=None):
    return subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, cmd], input=inp,
                          capture_output=True, text=True, timeout=180)


def psql(sql):
    r = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin', sql)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def code(wf, node):
    return psql("select n->'parameters'->>'jsCode' from workflow_entity w, "
                "jsonb_array_elements(w.nodes::jsonb) n where w.name like '%s' and n->>'name'='%s';"
                % (wf, node.replace("'", "''")))


def main():
    plan = []
    for wf, node in TARGETS:
        src = code(wf, node)
        if not src:
            print('узел не найден: %s / %s' % (wf, node))
            continue
        if 'правка 328' in src:
            print('%-22s %-16s уже стоит' % (wf[:22], node))
            continue
        plan.append((wf, node, src))
        print('%-22s %-16s будет добавлена проверка роли' % (wf[:22], node))
    if not plan:
        print('\nменять нечего')
        return 0
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    for wf, node, src in plan:
        fixed = GUARD + src
        tag = '$plpstage$'
        if tag in fixed:
            print('метка встретилась в коде — пропускаю %s' % node)
            continue
        sql = ("update workflow_entity set nodes = (\n"
               "  select jsonb_agg(case when n->>'name'='%s'\n"
               "    then jsonb_set(n, '{parameters,jsCode}', to_jsonb(%s%s%s::text))\n"
               "    else n end)\n"
               "  from jsonb_array_elements(nodes::jsonb) n)\n"
               "where name like '%s';" % (node.replace("'", "''"), tag, fixed, tag, wf))
        ssh('cat > /tmp/stage.sql', sql)
        out = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/stage.sql')
        ok = 'правка 328' in code(wf, node)
        print('  %s %-22s %-16s %s' % ('✓' if ok else '✗', wf[:22], node, out.stdout.strip()))
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
