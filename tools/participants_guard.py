#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож реестра участников: у системы должен быть ОДИН ответ на вопрос «кто свой».

Эльнур 18.09.2026: «ты не фиксируешь в железо, забываешь, и задачи, правила не
выполняются». Это про то, что списки «своих номеров» жили в трёх местах и расходились.

Сторож сверяет два места и показывает расхождение:
  • таблица system_participants в Supabase — истина с 18.09.2026;
  • зашитый список _OWN_TEAM в /opt/plp-api/brain.mjs — страховка на случай, когда
    база недоступна. Он обязан быть подмножеством реестра, иначе номер работает
    как свой, а система про него ничего не знает.

Ещё сторож смотрит на карточки клиентов по этим номерам: у своего номера роль
обязана быть internal, а анкеты лида (бюджет, цель, район, фокус объекта) быть не
должно — иначе система снова начнёт считать нас покупателями.

    python3 participants_guard.py          # отчёт
    python3 participants_guard.py --quiet  # только расхождения, код возврата 1 при них
"""
import json, os, re, subprocess, sys, urllib.request

QUIET = '--quiet' in sys.argv
ENV = os.path.expanduser('~/.plp_site_supabase.env')
VPS_IP = open(os.path.expanduser('~/.plp_vps_ip')).read().strip()
KEY_PATH = os.path.expanduser('~/.ssh/plp_vps')
ANKETA = ('budget_usd_min', 'budget_usd_max', 'goal', 'district_interest',
          'location_preference', 'property_type', 'segment', 'scoring',
          'active_object_id')


def env():
    out = {}
    for ln in open(ENV, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


def rest(path, key, base):
    r = urllib.request.Request(base + path, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read().decode() or '[]')


def own_team_from_code():
    out = subprocess.run(['ssh', '-i', KEY_PATH, '-o', 'ConnectTimeout=15', 'root@' + VPS_IP,
                          "grep -m1 'const _OWN_TEAM=' /opt/plp-api/brain.mjs"],
                         capture_output=True, text=True, timeout=60).stdout
    return re.findall(r"'(\d+)'", out)


def main():
    e = env()
    base, key = e['SUPABASE_URL'].rstrip('/') + '/rest/v1', e['SUPABASE_SERVICE_KEY']
    rows = rest('/system_participants?select=code,title,address_as,persona,is_internal,phones,tg_ids&active=is.true', key, base)
    reg = {}
    for r in rows:
        for p in (r.get('phones') or []) + (r.get('tg_ids') or []):
            reg[str(p)] = r
    code = own_team_from_code()
    bad = []

    if not QUIET:
        print('РЕЕСТР УЧАСТНИКОВ: %d записей, номеров в них %d' % (len(rows), len(reg)))
        for r in sorted(rows, key=lambda x: (not x.get('is_internal'), x['code'])):
            ph = (r.get('phones') or []) + (r.get('tg_ids') or [])
            print('  %-20s %-10s %-46s %s' % (r['code'], 'свой' if r.get('is_internal') else 'внешний',
                                              (r.get('address_as') or r['title'])[:46], ', '.join(ph) or '—'))

    lost = [p for p in code if p not in reg]
    if lost:
        bad.append('в коде есть свои номера, которых нет в реестре: %s' % ', '.join(lost))

    nums = sorted(set(list(reg.keys()) + code))
    prof = rest('/client_profiles?or=(phone_norm.in.(%s),tg_id.in.(%s))&select=phone_norm,tg_id,name,contact_role,%s'
                % (','.join(nums), ','.join(nums), ','.join(ANKETA)), key, base)
    if not QUIET and prof:
        print('\nКАРТОЧКИ ПО ЭТИМ НОМЕРАМ:')
    for p in prof:
        num = str(p.get('phone_norm') or p.get('tg_id') or '')
        junk = [k for k in ANKETA if p.get(k) not in (None, [], '')]
        role = p.get('contact_role') or '—'
        if not QUIET:
            print('  %-13s %-34s роль: %-9s %s' % (num, (p.get('name') or '')[:34], role,
                                                   ('анкета лида: ' + ','.join(junk)) if junk else 'чисто'))
        if num in reg and reg[num].get('is_internal'):
            if role != 'internal':
                bad.append('%s (%s): роль «%s», а должна быть internal' % (num, p.get('name'), role))
            if junk:
                bad.append('%s (%s): в карточке своего лежит анкета лида: %s' % (num, p.get('name'), ', '.join(junk)))

    print('\nРАСХОЖДЕНИЙ: %d' % len(bad))
    for b in bad:
        print('  🔴 ' + b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
