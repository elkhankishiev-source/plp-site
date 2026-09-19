#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реестр участников узнаёт свои каналы. И печатает карту «кто есть кто» одним взглядом.

Эльнур 19.09.2026: «зафиксируй себе где угодно, не позабудь кто есть из наших всех
участников, в чём проблема; если ты не знаешь, значит они тем более».

Он прав, и вот в чём была проблема. Реестр `system_participants` есть, в нём 19 записей,
мозг его читает. Но поле `channel_ids` пустое У ВСЕХ ДЕВЯТНАДЦАТИ. То есть реестр знает
имена и телефоны, но не знает, с какого КАНАЛА кто говорит. Из-за этого сегодня я сам
поставил волну касаний с подписью «Это Эльнур» на канал 35d237fd, который на самом деле
Дарьин: реестр мне этого не сказал, правда лежала в другой таблице, channels_config.
Если этого не знаю я, то и двойник не знает.

Что делает скрипт:
  • тянет живую правду о каналах из Wazzup (номер, транспорт, состояние) и сверяет с
    channels_config, где записано, чей это канал;
  • раскладывает channel_ids и недостающие номера по участникам;
  • печатает карту: кто, кем представляется, с каких номеров и каналов, кого система
    считает своим, а кого клиентом.

    python3 participants_channels.py            # показать карту и что будет дописано
    python3 participants_channels.py --apply    # дописать каналы в реестр
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv

# кому какой участник реестра соответствует по владельцу канала в channels_config
OWNER_TO_CODE = {'elnur': 'double_elnur', 'daria': 'double_daria'}

# номера, которые Parse WA выбрасывает на входе как «свои» — писать на них бесполезно
SELF_MUTED = ('66955492587', '66829935173')


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def wazzup_channels():
    """Живое состояние каналов. Если Wazzup недоступен — работаем по конфигурации."""
    tok = os.environ.get('WAZZUP_TOKEN', '')
    if not tok:
        return {}
    try:
        r = urllib.request.Request('https://api.wazzup24.com/v3/channels',
                                   headers={'Authorization': 'Bearer ' + tok})
        with urllib.request.urlopen(r, timeout=25) as f:
            return {c['channelId']: c for c in json.load(f)}
    except Exception:
        return {}


def main():
    cfg = call('/channels_config?select=name,wazzup_uuid,transport,owner,active')
    live = wazzup_channels()
    people = call('/system_participants?select=code,title,persona,is_internal,phones,tg_ids,'
                  'channel_ids,kind,active')
    by_code = {p['code']: p for p in people}

    plan = {}
    for c in cfg:
        code = OWNER_TO_CODE.get(str(c.get('owner') or ''))
        uuid = str(c.get('wazzup_uuid') or '')
        if not code or not uuid or code not in by_code:
            continue
        cur = by_code[code]
        ids = list(cur.get('channel_ids') or [])
        phones = list(cur.get('phones') or [])
        plain = str((live.get(uuid) or {}).get('plainId') or '')
        if uuid not in ids:
            ids.append(uuid)
        if plain and plain not in phones:
            phones.append(plain)
        if ids != (cur.get('channel_ids') or []) or phones != (cur.get('phones') or []):
            plan[code] = {'channel_ids': ids, 'phones': phones}
            # накапливаем: у человека каналов несколько, следующий круг не должен стереть
            # предыдущий — на этом я уже один раз записал Дарье только телеграм
            cur['channel_ids'] = ids
            cur['phones'] = phones

    print('КТО ЕСТЬ КТО — карта участников\n')
    owner_of = {}
    for c in cfg:
        owner_of[str(c.get('wazzup_uuid'))] = (str(c.get('owner') or ''), str(c.get('name') or ''))
    for p in sorted(people, key=lambda x: (not x.get('is_internal'), x['code'])):
        ids = (plan.get(p['code'], {}).get('channel_ids') or p.get('channel_ids') or [])
        phones = (plan.get(p['code'], {}).get('phones') or p.get('phones') or [])
        if not ids and not phones and not (p.get('tg_ids') or []):
            continue
        print('%-18s %-9s %s' % (p['code'], str(p.get('persona') or '—'),
                                 'СВОЙ' if p.get('is_internal') else 'не свой'))
        print('   %s' % str(p.get('title'))[:70])
        for ph in phones:
            mark = '  ← вход с этого номера система глушит (_SELF в Parse WA)' if ph in SELF_MUTED else ''
            print('   тел  +%s%s' % (ph, mark))
        for t in (p.get('tg_ids') or []):
            print('   тг   %s' % t)
        for u in ids:
            nm = owner_of.get(u, ('', ''))[1]
            st = (live.get(u) or {}).get('state', '?')
            tr = (live.get(u) or {}).get('transport', '?')
            print('   канал %-9s %-11s %-9s %s' % (tr, nm, st, u[:8]))
        print()

    if not plan:
        print('каналы у всех уже проставлены')
        return 0
    print('будет дописано: %s' % ', '.join(sorted(plan)))
    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    for code, patch in plan.items():
        call('/system_participants?code=eq.%s' % code, 'PATCH', patch)
        print('  ✓ %s: каналов %d, номеров %d' % (code, len(patch['channel_ids']), len(patch['phones'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
