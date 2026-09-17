#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ворота CRM: карточку заводим не только на скоринг «А».

Эльнур 17.09.2026: «а это не сильно грубо, почему только а?» и «всех остальных
под пресс».

Как было. В трёх воркфлоу подряд стоял узел «Score A …?» с условием score === 'A'.
За две недели: A — 5 диалогов, B — 7, C — 102, без оценки — 6. То есть в CRM
попадало около 4% разговоров, остальные 96% исчезали: человек писал, двойник
отвечал, и следа в CRM не оставалось.

Как стало. Карточка заводится на любой диалог, где оценка вообще выставлена
(A, B или C). Без оценки — по-прежнему нет: это служебные и пустые прогоны.

Чего НЕ трогаем и почему:
  • второй фильтр «есть номер» в WF_agent_qualified и третий в WF7 (не меньше
    десяти цифр) оставлены как есть. Их снятие пускает в CRM телеграм-идентификаторы
    из девяти цифр, а ключ идемпотентности в узле «Enqueue AmoCRM» содержит
    Date.now() — то есть каждое сообщение заводило бы НОВУЮ сделку. Сначала дедуп
    по platform_id, потом уже эти ворота;
  • сам расчёт этапа. Он предлагает этап по последней реплике, и для продвинутых
    сделок предложение уходит назад — но сторож «только вперёд» это отбивает
    корректно. Шум в журнале, а не поломка.

Резервная копия узлов кладётся рядом; откат — n8n хранит версии воркфлоу.

    python3 vps_crm_gates.py            # показать, что изменится
    python3 vps_crm_gates.py --apply    # применить и перезапустить n8n
"""
import datetime, json, os, subprocess, sys

APPLY = '--apply' in sys.argv
PSQL = ['docker', 'exec', 'n8n-postgres-1', 'psql', '-U', 'n8n', '-t', '-A', '-c']
BACKUP = '/root/n8n_gates_backup_%s.json' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

# воркфлоу → имя узла-ворот
GATES = [
    ('CM9lfLZw2qlKT3XP', 'Score A WA?',  'WhatsApp'),
    ('OaCvP3zK7r2J9Uhl', 'Score A IG?',  'Instagram'),
    ('3AO7lAToGYJyxvz6', 'Score A?',     'Telegram, клиентский бот'),
]


def q(sql):
    r = subprocess.run(PSQL + [sql], capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def gate_node(wid, name):
    sql = ("select n->>'name' from workflow_entity w, jsonb_array_elements(w.nodes::jsonb) n "
           "where w.id='%s' and n->>'name' ilike '%%score%%'" % wid)
    return [x for x in q(sql).split('\n') if x.strip()]


def main():
    found, plan = [], []
    for wid, name, chan in GATES:
        names = gate_node(wid, name)
        if not names:
            print('%-26s ворот со скорингом нет' % chan)
            continue
        for nm in names:
            cur = q("select n->'parameters'->'conditions'->'conditions'->0->>'rightValue' "
                    "from workflow_entity w, jsonb_array_elements(w.nodes::jsonb) n "
                    "where w.id='%s' and n->>'name'='%s'" % (wid, nm.replace("'", "''")))
            op = q("select n->'parameters'->'conditions'->'conditions'->0->'operator'->>'operation' "
                   "from workflow_entity w, jsonb_array_elements(w.nodes::jsonb) n "
                   "where w.id='%s' and n->>'name'='%s'" % (wid, nm.replace("'", "''")))
            print('%-26s %-16s сейчас: %s «%s»' % (chan, nm, op or '—', cur or '—'))
            found.append((wid, nm, chan, cur, op))
            if (cur or '').strip() == 'A':
                plan.append((wid, nm, chan))

    if not plan:
        print('\nворот с условием «строго A» не осталось — менять нечего')
        return 0
    print('\nБудет изменено: %d' % len(plan))
    for wid, nm, chan in plan:
        print('   %-26s %-16s  A  →  A, B или C (регулярка ^[ABC]$)' % (chan, nm))
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0

    # резервная копия целиком: узлы всех трёх воркфлоу
    dump = {}
    for wid, _, chan in GATES:
        dump[wid] = json.loads(q("select nodes::text from workflow_entity where id='%s'" % wid) or '[]')
    open(BACKUP, 'w', encoding='utf-8').write(json.dumps(dump, ensure_ascii=False))
    print('\nрезервная копия узлов: %s' % BACKUP)

    for wid, nm, chan in plan:
        sql = ("""update workflow_entity set nodes = (
                   select jsonb_agg(case when n->>'name' = '%s'
                     then jsonb_set(jsonb_set(n,
                            '{parameters,conditions,conditions,0,rightValue}', '"^[ABC]$"'),
                            '{parameters,conditions,conditions,0,operator,operation}', '"regex"')
                     else n end)
                   from jsonb_array_elements(nodes::jsonb) n)
                 where id='%s'""" % (nm.replace("'", "''"), wid))
        q(sql)
        print('   ✓ %-26s %s' % (chan, nm))

    print('\nперезапускаю n8n, чтобы он перечитал воркфлоу…')
    subprocess.run(['docker', 'restart', 'n8n'], capture_output=True, timeout=180)
    return 0


if __name__ == '__main__':
    sys.exit(main())
