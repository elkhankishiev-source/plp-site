#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привратник учится отказывать по битому номеру. Разметка перестаёт быть мёртвой.

Эльнур 19.09.2026: «нельзя бросать битые и не закрытые вопросы… ищи, закрывай».

`phone_status` в карточках проставлен, но его не читал НИКТО: ни мозг, ни один сценарий.
Размеченные «no_country», «too_short», «telegram_id» спокойно уходили в очередь касаний
и в отправку — система честно пыталась достучаться по номеру, которого не существует.

Правка добавляет привратнику один отказ: если у карточки человека номер помечен как
непригодный, наружу ничего не идёт, и в решении прямо написано почему. Это не запрет
работать с человеком: через Telegram по tg_id или после исправления номера он снова
доступен. Это запрет писать в пустоту.

Отказ не распространяется на Telegram: там адресом может быть tg_id, а не номер.

    python3 vps_gate_phone_status.py            # показать, что изменится
    python3 vps_gate_phone_status.py --apply    # записать и опубликовать
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
WF = 'WF_outbound_gate%'
NODE = 'Policy Engine'

OLD = "if(!msg)D.push('empty_message');"

NEW = """if(!msg)D.push('empty_message');
/* 19.09.2026: номер помечен как непригодный — писать в пустоту не даём.
   Telegram не трогаем: там адрес может быть tg_id, а не телефон.
   Разбор — в tools/vps_gate_phone_status.py */
try{
  if(client&&client.id&&channel!=='telegram'&&channel!=='tg'&&channel!=='tg_bot'){
    var _cs=await get.call(this,base+'/clients?client_id=eq.'+encodeURIComponent(client.id)
      +'&select=phone_status&limit=1');
    var _ps=String((_cs[0]||{}).phone_status||'');
    if(['no_country','too_short','too_long','telegram_id','empty'].indexOf(_ps)>=0){
      D.push('битый номер ('+_ps+') — в WhatsApp по нему не достучаться');
    }
  }
}catch(_eps){}"""


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
    if 'битый номер' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: привратник отказывает, если номер помечен непригодным')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909ps$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/gateps.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                    'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/gateps.sql'],
                   capture_output=True, text=True, timeout=300)
    print('черновик: %s' % ('ок' if 'битый номер' in code() else 'НЕ ЗАПИСАЛОСЬ'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
