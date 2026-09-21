#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привратник учится видеть роль: застройщику и партнёру первыми не пишем.

Эльнур, железно, 18.09.2026: «Камиле не пиши, она застройщик, оставь её в покое! Это
касается всех… не мучай застройщиков!!!!!» И 19.09: «мы работаем ток с лидами, у каждой
категории своё назначение, мы продаём лидам, и коротко отвечаем коллегам, не ведём их по
воронке».

Проверил 19.09: в привратнике **ноль упоминаний contact_role**. Он отказывает по чёрному
списку, по спаму, по паузе, по купившему, по битому номеру — но роль человека не смотрит
вовсе. Правило держалось на стороже `plp_watch`, который чистит уже поставленные касания
раз в двадцать минут. Значит касание, поставленное между его проходами, уходило.

И это не теория: сегодня нашлись восемь карточек, где профиль говорит «застройщик» или
«партнёр», а сама карточка числилась клиентом. Среди них Камилла Art House и Коля Clover
Villas — те самые застройщики.

Правка ставит отказ в единственной точке, через которую проходит ВСЁ исходящее.

Что именно запрещено: писать ПЕРВЫМИ тому, кто не лид. Что разрешено и не трогается:
  • `agent='auto'` — это ответ на входящее сообщение. Ответить коллеге или застройщику
    можно и нужно, это не касание;
  • `agent='office'` — внутренняя переписка команды.
Всё остальное (проактив, реанимация, кампании, поручения) для не-лида отклоняется с
понятной причиной, а не молча.

    python3 vps_gate_role_guard.py            # показать, что изменится
    python3 vps_gate_role_guard.py --apply    # записать в черновик сценария
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
WF = 'WF_outbound_gate%'
NODE = 'Policy Engine'

OLD = "if(prof.is_spam===true)D.push('is_spam(тест/мусор)');"

NEW = """if(prof.is_spam===true)D.push('is_spam(тест/мусор)');
/* 19.09.2026: роль решает, можно ли писать ПЕРВЫМИ. Железное правило Эльнура
   «не мучай застройщиков» до сих пор жило только в стороже, который подчищает
   очередь постфактум. Разбор — в tools/vps_gate_role_guard.py */
try{
  var _РОЛЬ=String(prof.contact_role||'').toLowerCase();
  var _НЕ_ЛИД=['developer','partner','colleague','internal','team','family','supplier'];
  var _ОТВЕТ=(agent==='auto'||agent==='office');   /* ответ на входящее — не касание */
  if(_РОЛЬ && _НЕ_ЛИД.indexOf(_РОЛЬ)>=0 && !_ОТВЕТ){
    D.push('роль «'+_РОЛЬ+'»: первыми не пишем, отвечаем только на входящее');
  }
}catch(_eроль){}"""


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
    if 'первыми не пишем' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: привратник отказывает писать первыми не-лиду')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909role$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/gaterole.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                    'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/gaterole.sql'],
                   capture_output=True, text=True, timeout=300)
    print('черновик: %s' % ('ок' if 'первыми не пишем' in code() else 'НЕ ЗАПИСАЛОСЬ'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
