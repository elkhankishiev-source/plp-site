#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Квалификация перестаёт заводить лида на владельца, коллегу и застройщика.

Эльнур 19.09.2026: «мы работаем ток с лидами, у каждой категории своё назначение, мы
продаём лидам, и коротко отвечаем коллегам, не ведём их по воронке».

Найдено при разборе очереди amoCRM. За сегодня семь раз подряд туда падал `create_lead`
с телефоном 66954143874 — это ЛИЧНЫЙ номер Эльнура, роль `internal` — и с именем
«ТЕСТ Клод сквозной (удалить)», прилипшим к профилю от старого теста.

Источник — `WF_agent_qualified`. В нём **ноль упоминаний роли**: сценарий квалифицирует
кого угодно, кто заговорил. Владельца, коллегу, застройщика. Спасал только дедуп в
очереди (`deduped: true`), то есть новых сделок не появлялось — но сама попытка вести
владельца по воронке происходила при каждом его сообщении.

Правка: перед постановкой в очередь смотрим роль в `client_profiles`. Если это не лид —
выходим молча, без ошибки: человек не клиент, квалифицировать нечего. Разговор при этом
идёт как шёл, блокируется только запись лида в CRM.

Имя профиля уже исправлено на «Эльнур (личный номер)», чтобы мусор не тиражировался.

    python3 vps_qualified_role_guard.py            # показать, что изменится
    python3 vps_qualified_role_guard.py --apply    # записать в черновик сценария
"""
import subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
WF = 'WF_agent_qualified%'
NODE = 'Parse Payload'

OLD = """const body = $input.first().json.body || $input.first().json;"""

NEW = """const body = $input.first().json.body || $input.first().json;
/* 19.09.2026: лида заводим только на ЛИДА. Сценарий раньше не смотрел на роль вовсе,
   и квалифицировал владельца, коллег и застройщиков — в очередь amoCRM семь раз за день
   падал create_lead на личный номер Эльнура. Разбор — в tools/vps_qualified_role_guard.py */
try{
  const _тел = String(body.phone || body.contact_phone || '').replace(/\\D/g, '');
  if (_тел) {
    const _пр = await this.helpers.httpRequest({ timeout: 15000, method: 'GET', json: true,
      url: $env.SUPABASE_URL + '/rest/v1/client_profiles?phone_norm=eq.' + _тел
           + '&select=contact_role&limit=1',
      headers: { apikey: $env.SUPABASE_SERVICE_KEY,
                 Authorization: 'Bearer ' + $env.SUPABASE_SERVICE_KEY } });
    const _роль = String(((Array.isArray(_пр) ? _пр[0] : null) || {}).contact_role || '').toLowerCase();
    const _неЛид = ['internal','partner','developer','colleague','team','family','supplier'];
    if (_роль && _неЛид.indexOf(_роль) >= 0) {
      console.log('[роль] ' + _тел + ' это «' + _роль + '», лида не завожу');
      return [];
    }
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
    if 'лида не завожу' in js:
        print('правка уже стоит')
        return 0
    if js.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % js.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: не-лида в CRM не заводим, разговор не трогаем')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    fixed = js.replace(OLD, NEW, 1)
    tag = '$plp1909q$'
    if tag in fixed:
        print('метка кавычек встретилась в коде — отменяю')
        return 1
    sql = ("update workflow_entity set nodes = (select jsonb_agg(case when n->>'name'='%s' "
           "then jsonb_set(n,'{parameters,jsCode}',to_jsonb(%s%s%s::text)) else n end) "
           "from jsonb_array_elements(nodes::jsonb) n) where name like '%s';"
           % (NODE, tag, fixed, tag, WF))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'cat > /tmp/qrole.sql'],
                   input=sql, capture_output=True, text=True, timeout=120)
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                    'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin < /tmp/qrole.sql'],
                   capture_output=True, text=True, timeout=300)
    print('черновик: %s' % ('ок' if 'лида не завожу' in code() else 'НЕ ЗАПИСАЛОСЬ'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
