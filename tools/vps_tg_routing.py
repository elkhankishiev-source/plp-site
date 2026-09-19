#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разводка уведомлений: в «Тех офис» только поломки, в «Отдел продаж» только работа.

Эльнур 18.09.2026: «мне надо, чтобы в группе ТГ Тех ПЛП писались только технические
ошибки и всё, что связано с исправностью-неисправностью. В группу отдел продаж только
рабочие моменты по рынку. В целом мне надо, чтобы ты сам рассортировал уведомления
по релевантности».

Как было (проверено по коду всех активных сценариев):
  ТЕХ ОФИС (-5571405041) получал, кроме сторожей, ещё и всю рабочую жизнь:
    • зеркало переписки «💬 Дарья → +66…» на КАЖДУЮ реплику двойника;
    • «клиент, который уже купил, написал» из Instagram и клиентского бота;
    • дайджест «🔄 Сверка актуальности каталога» — изменения цен, наличия и стройки.
  ОТДЕЛ ПРОДАЖ (-4664612682) получал, кроме лидов и вех, техническую аварию:
    • «🔴 Заявка с сайта принята В ОБХОД сервера — plp-api не ответил».

Стало:
  ТЕХ ОФИС  — только поломки и здоровье: приёмник ошибок, сторожа сайта и каналов,
              квоты и кредиты, токен amoCRM, расхождения канона, обход сервера.
  ОТДЕЛ ПРОДАЖ — работа и рынок: горячие лиды, заявки, ответы клиентов и покупателей,
              вехи сделок, изменения цен и наличия, документы из почты.

    python3 vps_tg_routing.py            # показать, что изменится
    python3 vps_tg_routing.py --apply    # применить и перезапустить n8n
"""
import json, subprocess, sys

APPLY = '--apply' in sys.argv
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
SALES = '$env.TG_ALERT_CHAT_ID'
TECH = '$env.TG_TECH_CHAT_ID'

# (сценарий, узел, что было, что стало, зачем)
MOVES = [
    ('WF_wa_wazzup%', 'Log Reply WA', TECH, SALES,
     'зеркало переписки двойника — это работа, а не поломка'),
    ('WF_ig_meta%', 'Покупатель: уведомить', TECH, SALES,
     'написал покупатель — это разговор с клиентом'),
    ('WF_validator_PROD%', 'Покупатель: уведомить', TECH, SALES,
     'написал покупатель — это разговор с клиентом'),
    ('WF_freshness%', 'Сверка', TECH, SALES,
     'изменения цен, наличия и стройки — рыночный повод'),
    ('WF_site_lead%', 'Сказать людям', SALES, TECH,
     'заявка в обход сервера — авария, а не рабочий момент'),
]


def ssh(cmd, inp=None):
    return subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, cmd], input=inp,
                          capture_output=True, text=True, timeout=180)


def psql(sql):
    r = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin', sql)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def node_code(wf, node):
    """Текст узла: у кодового узла это jsCode, у запроса — тело jsonBody.
    Уведомление о заявке в обход сервера живёт как раз во втором виде."""
    for field in ('jsCode', 'jsonBody'):
        sql = ("select n->'parameters'->>'%s' from workflow_entity w, "
               "jsonb_array_elements(w.nodes::jsonb) n where w.name like '%s' and n->>'name'='%s';"
               % (field, wf, node.replace("'", "''")))
        out = psql(sql)
        if out:
            return field, out
    return None, ''"''"


def main():
    plan = []
    for wf, node, old, new, why in MOVES:
        field, code = node_code(wf, node)
        if not code:
            print('узел не найден: %s / %s' % (wf, node))
            continue
        cnt = code.count(old)
        if not cnt:
            print('%-22s %-24s уже переставлен' % (wf[:22], node[:24]))
            continue
        plan.append((wf, node, old, new, why, cnt, code, field))
        print('%-22s %-24s %d× → %s  (%s)'
              % (wf[:22], node[:24], cnt, 'отдел продаж' if new == SALES else 'тех офис', why))
    if not plan:
        print('\nвсё уже разведено')
        return 0
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    tag = '$plp1809r$'
    for wf, node, old, new, why, cnt, code, field in plan:
        fixed = code.replace(old, new)
        if tag in fixed:
            print('метка кавычек встретилась в коде, пропускаю %s' % node)
            continue
        sql = ("update workflow_entity set nodes = (\n"
               "  select jsonb_agg(case when n->>'name'='%s'\n"
               "    then jsonb_set(n, '{parameters,%s}', to_jsonb(%s%s%s::text))\n"
               "    else n end)\n"
               "  from jsonb_array_elements(nodes::jsonb) n)\n"
               "where name like '%s';" % (node.replace("'", "''"), field, tag, fixed, tag, wf))
        ssh('cat > /tmp/route.sql', sql)
        psql_out = ssh('docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/route.sql')
        print('  ✓ %-22s %-24s %s' % (wf[:22], node[:24], psql_out.stdout.strip()))
    for wf, node, old, new, why, cnt, code, field in plan:
        _f, now = node_code(wf, node)
        ok = (now.count(old) == 0)
        print('проверка: %-22s %-20s %s' % (wf[:22], node[:20], 'ок' if ok else 'НЕ ПРИМЕНИЛОСЬ'))
    ssh("docker restart n8n-n8n-1 >/dev/null 2>&1; sleep 6; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'")
    print('n8n перезапущен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
