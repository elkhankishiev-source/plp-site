#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Безымянные карточки получают имя из amoCRM. Человек без имени — половина карточки.

Эльнур: «каждая карточка должна быть заполнена, наполняться и вестись по воронке»,
и 19.09: «нельзя бросать битые и не закрытые вопросы».

Нашлось 89 карточек вообще без имени. Писать такому человеку приходится безлично
(«Здравствуйте.»), а это заметно холоднее и хуже работает.

Из них 26 привязаны к контакту amoCRM, где имя есть. Остальные 63 пришли из WhatsApp
и Telegram без имени вовсе — там брать неоткуда, их оставляем как есть.

Служебные подписи именем не считаются: в amoCRM часто стоит «Новый лид RED -» или
«Новый лид RED - None». Такие пропускаем, иначе получим обращение «Здравствуйте, Новый».

    python3 clients_restore_names.py            # показать, что подставится
    python3 clients_restore_names.py --apply    # записать имена
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv

NOT_NAMES = ('новый', 'новая', 'лид', 'заявка', 'сделка', 'клиент', 'контакт', 'без',
             'lead', 'client', 'test', 'тест', 'unknown', 'none', 'null', 'whatsapp',
             'telegram', 'instagram', 'facebook', 'fb', 'ig', 'red', 'plp')


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


def clean(s):
    """Имя человека, а не служебная подпись источника и не заметка менеджера."""
    s = str(s or '').strip()
    # «TG-лид 5553620221 (18.06, без имени) — вернуть в работу» это заметка, а не имя.
    # Длинная строка, скобки и цифры внутри — верные признаки, что имени тут нет.
    if len(s.split()) > 3 or '(' in s or any(ch.isdigit() for ch in s):
        return ''
    for sep in (' - ', ' — ', ' – ', ':'):
        if sep in s:
            s = s.split(sep)[-1].strip()
    if not s or any(ch.isdigit() for ch in s):
        return ''
    # в поле имени встречаются обрывки фраз («вернуть в»), а не имена:
    # инфинитивы и предлоги именем не бывают
    ПРЕДЛОГИ = {'в', 'на', 'за', 'по', 'до', 'из', 'к', 'с', 'у', 'о', 'от', 'для',
                'при', 'об', 'под', 'над', 'же', 'и', 'а', 'но', 'или'}
    def похоже_на_имя(w):
        low = w.lower()
        if low in NOT_NAMES or low in ПРЕДЛОГИ:
            return False
        if low.endswith(('ть', 'ти', 'чь', 'ться', 'тись')):
            return False
        return len(w) > 1
    words = [w.strip('.,') for w in s.split()]
    words = [w for w in words if похоже_на_имя(w)]
    if not words:
        return ''
    name = ' '.join(words[:2])
    return name if 1 < len(name) <= 40 else ''


def main():
    rows = call('/clients?name=is.null&select=client_id,code,phone,amo_contact_id&limit=500')
    print('карточек без имени: %d' % len(rows))
    plan = []
    for c in rows:
        if not c.get('amo_contact_id'):
            continue
        r = call('/crm_contacts?id=eq.%s&select=name,first_name' % c['amo_contact_id'])
        if not r:
            continue
        nm = clean(r[0].get('first_name')) or clean(r[0].get('name'))
        if nm:
            plan.append((c, nm))
    print('имя нашлось в amoCRM: %d\n' % len(plan))
    for c, nm in plan:
        print('   %-11s %-14s → %s' % (c['code'], str(c.get('phone')), nm))
    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    for c, nm in plan:
        call('/clients?client_id=eq.%s' % c['client_id'], 'PATCH', {'name': nm})
    print('\nзаполнено имён: %d' % len(plan))
    print('остались без имени: %d — в amoCRM их нет, брать неоткуда'
          % (len(rows) - len(plan)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
