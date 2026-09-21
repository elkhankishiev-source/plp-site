#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимает паузы, которые никто не просил. Двойники должны работать, а не молчать.

Эльнур 20.09.2026: «фиксирую, по идее не должно быть ни кого на стопах, ии двойники
рабочие в тг и ватсапе пишут лидам, работают, наполняют срм, ведут по воронке, ставят
задачи, сверь, что бы все именно так и было».

Что нашлось. На паузе (`ai_paused`) стоят 279 профилей. По датам видно, что это не
решения людей, а массовые простановки:

    13.07.2026 — 179 профилей за один день
    10.07.2026 — 26
    04.06.2026 — 24
    30.05.2026 — 20

У Laura прямо в карточке причина: «AmoCRM импорт старых лидов». То есть паузу выставили,
чтобы ИИ не набросился на базу при импорте, и забыли снять.

Проверка по перепискам: слова «не пишите», «отстаньте», «стоп», «не интересует» и прочие
отказы нашлись ровно у ОДНОГО ключа — и это наша собственная группа «Отдел продаж»
(«Стоп уведомления»). У остальных 275 человек ни одной просьбы не писать.

Кого НЕ трогаем, даже при массовом снятии:
  • наши группы и служебные чаты;
  • всех, у кого роль не «лид» (коллеги, партнёры, застройщики, свои);
  • тех, кто действительно просил не писать.

    python3 unpause_bulk.py            # показать, кого снимем и кого оставим
    python3 unpause_bulk.py --apply    # снять паузы
"""
import json, os, re, sys, urllib.request

APPLY = '--apply' in sys.argv

ГРУППЫ = {'4664612682', '5571405041'}
НЕ_ЛИД = {'internal', 'partner', 'developer', 'colleague', 'team', 'family', 'supplier'}
ОТКАЗ = re.compile(r'(не пишит|не беспоко|отстан|отпишит|стоп увед|перестань|удалите мо|'
                   r'заблокир|не интересу|больше не надо|прекрат)', re.I)


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
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def allrows(path):
    out, off = [], 0
    while True:
        b = call(path + '&limit=1000&offset=%d' % off)
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def main():
    пауза = allrows('/client_profiles?ai_paused=is.true'
                    '&select=phone_norm,tg_id,name,contact_role,updated_at')
    ключи = [str(p.get('phone_norm') or p.get('tg_id') or '') for p in пауза]
    ключи = [k for k in ключи if k]

    # кто действительно просил не писать
    просили = set()
    for i in range(0, len(ключи), 50):
        часть = ','.join(ключи[i:i + 50])
        for r in call('/chat_history?phone_norm=in.(%s)&role=eq.user&select=phone_norm,content'
                      '&limit=1000' % часть):
            if ОТКАЗ.search(str(r.get('content') or '')):
                просили.add(str(r['phone_norm']))

    снимем, оставим = [], []
    for p in пауза:
        ключ = str(p.get('phone_norm') or p.get('tg_id') or '')
        роль = str(p.get('contact_role') or '').lower()
        if ключ in ГРУППЫ:
            оставим.append((p, 'наша группа'))
        elif роль in НЕ_ЛИД:
            оставим.append((p, 'роль «%s»' % роль))
        elif ключ in просили:
            оставим.append((p, 'человек просил не писать'))
        else:
            снимем.append(p)

    print('на паузе: %d' % len(пауза))
    print('оставляем на паузе: %d' % len(оставим))
    for p, поч in оставим[:12]:
        print('   %-14s %-26s %s' % (p.get('phone_norm') or p.get('tg_id'),
                                     str(p.get('name'))[:26], поч))
    print('\nснимаем паузу: %d' % len(снимем))
    for p in снимем[:8]:
        print('   %-14s %-26s пауза от %s' % (p.get('phone_norm') or p.get('tg_id'),
                                              str(p.get('name'))[:26],
                                              str(p.get('updated_at'))[:10]))
    if not APPLY:
        print('\nЭто отчёт. Снять: --apply')
        return 0
    n = 0
    for p in снимем:
        # у таблицы нет колонки id: адресуем по номеру, а при его отсутствии по tg_id
        if p.get('phone_norm'):
            адрес = '/client_profiles?phone_norm=eq.%s' % p['phone_norm']
        elif p.get('tg_id'):
            адрес = '/client_profiles?tg_id=eq.%s' % p['tg_id']
        else:
            continue
        call(адрес, 'PATCH', {'ai_paused': False})
        n += 1
        if n % 100 == 0:
            print('   … снято %d' % n)
    print('\nснято пауз: %d' % n)
    print('осталось на паузе: %d (группы, не-лиды и те, кто просил)' % len(оставим))
    return 0


if __name__ == '__main__':
    sys.exit(main())
