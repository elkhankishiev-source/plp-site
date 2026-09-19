#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Исходящее касание подписывается персоной — иначе ответ человека некому отнести.

Проверил первое живое касание волны 19.09.2026 (Архат, 16:33). Дошло, привратник
пропустил, в истории записалось. Но строка легла без подписи:

    assistant | whatsapp | источник: touch_queue | персона: None

Почему это важно. В мозге есть правка 70: у каждого двойника СВОЯ нить разговора, и
разбирается она по `meta.persona` на строке истории. Непомеченные строки приходится
угадывать по каналу и дате. Значит, когда Архат ответит, система не будет знать наверняка,
кто именно ему писал — Эльнур или Дарья, — и может продолжить разговор не тем голосом.
Для человека это выглядит как разговор с двумя разными людьми в одном чате.

Это ровно то, чего Эльнур требует канонoм #111: «одна история на одного человека, всё
идёт как продолжение единого человека».

Правка: при записи отправленного касания в историю проставляем `meta.persona` из строки
очереди (её кладёт туда планировщик касаний) и помечаем кампанию — чтобы потом было
видно, из какой волны пришёл разговор.

    python3 vps_touch_persona_stamp.py            # показать, что изменится
    python3 vps_touch_persona_stamp.py --apply    # записать в черновик сценария
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
WF = 'WF_touch_send%'
NODE = 'Отправить утверждённые'

OLD = """      body: { phone: r.phone, channel: (r.channel === 'telegram' ? 'telegram' : 'whatsapp'),
              role: 'assistant', content: body, source: 'touch_queue' } });"""

NEW = """      /* 19.09.2026: подписываем строку персоной. Без подписи мозг не знает, кто вёл
         разговор, и ответ человека может уйти не тем голосом (правка 70, канон #111).
         Разбор — в tools/vps_touch_persona_stamp.py */
      body: { phone: r.phone, channel: (r.channel === 'telegram' ? 'telegram' : 'whatsapp'),
              role: 'assistant', content: body, source: 'touch_queue',
              meta: { persona: (r.persona || (String(r.agent||'')==='owner_task' ? 'Эльнур' : null)),
                      campaign: r.campaign || null, touch_id: r.id } } });"""


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
    if 'подписываем строку персоной' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: отправленное касание пишется в историю с персоной и кампанией')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909ps2$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/tpers.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                    'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/tpers.sql'],
                   capture_output=True, text=True, timeout=300)
    print('черновик: %s' % ('ок' if 'подписываем строку персоной' in code() else 'НЕ ЗАПИСАЛОСЬ'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
