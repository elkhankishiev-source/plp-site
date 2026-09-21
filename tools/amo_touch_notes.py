#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""След касания в amoCRM: менеджер открывает сделку и видит, что человеку писали.

Эльнур: «очень важно, что бы вся информация вела учёт, диалоги, данные, объекты, заявки,
воронки, сайт, кабинет, срм» и «каждая карточка должна быть заполнена, наполняться и
вестись по воронке».

Проверено 19.09 после первой волны: по сделкам тех, кому мы написали, заметок НОЛЬ.
Сообщение ушло, в нашей базе записано, а в amoCRM — пусто. Менеджер, открыв карточку,
не узнает ни что писали, ни что именно, ни по какому проекту. Для него человек
по-прежнему «не отвечает».

Скрипт берёт отправленные касания, у которых ещё нет отметки, находит сделку человека
и кладёт в её ленту заметку: кто написал, каким каналом, по какому поводу и сам текст.
Отметку ставит в `touch_queue.source_ref`, чтобы не задваивать.

Путь запроса в amoCRM идёт БЕЗ префикса «/api/v4» — сценарий подставляет его сам
(на этом я уже обжигался, см. tools/amo_delete_tests.py).

    python3 amo_touch_notes.py            # показать, что будет записано
    python3 amo_touch_notes.py --apply    # записать заметки
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
HOOK = 'https://hub.property-library.com/webhook/amo-write'


def env():
    """Ключи лежат по-разному: на Маке в ~/.plp_site_supabase.env, на сервере в
    /opt/plp-api/.env. Скрипт должен работать и там, и там — он ходит в крон."""
    out = {}
    for путь in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env'):
        if not os.path.exists(путь):
            continue
        for ln in open(путь, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1)
                out.setdefault(k, v.strip().strip('"\''))
        if out.get('SUPABASE_URL'):
            break
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}
KEY = os.environ.get('PLP_WEBHOOK_KEY', '')


def sb(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def amo(method, ep, payload):
    body = json.dumps({'m': method, 'ep': ep, 'payload': payload}).encode()
    r = urllib.request.Request(HOOK, data=body, method='POST',
                               headers={'Content-Type': 'application/json', 'x-plp-key': KEY})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return f.read().decode()[:200]
    except Exception as e:
        return 'исключение: ' + str(e)[:110]


ЖЕНСКИЕ = {'Дарья'}
НЕ_ЛИД = {'internal', 'partner', 'developer', 'colleague', 'team', 'family', 'supplier'}


def роль(phone):
    """Заметку о продающем касании кладём только клиенту. Коллеге и застройщику
    её ставить незачем: они не в воронке, а карточка засоряется."""
    p = sb('/client_profiles?phone_norm=eq.%s&select=contact_role&limit=1' % phone)
    return str((p[0].get('contact_role') if p else '') or '').lower()


def сделка_по_номеру(phone):
    cp = sb('/crm_contact_phones?phone_norm=eq.%s&select=contact_id' % phone)
    if not cp:
        return None
    L = sb('/crm_leads?contacts=cs.[%d]&is_deleted=is.false&select=id,name'
           '&order=updated_at_crm.desc&limit=1' % cp[0]['contact_id'])
    return L[0] if L else None


def main():
    отправленные = sb('/touch_queue?status=eq.sent&source_ref=is.null'
                      '&select=id,phone,persona,channel,occasion,body,sent_at'
                      '&order=sent_at.desc&limit=50')
    print('отправленных касаний без отметки в CRM: %d\n' % len(отправленные))
    план = []
    for t in отправленные:
        ph = str(t.get('phone') or '')
        r = роль(ph)
        if r in НЕ_ЛИД:
            print('   %-14s роль «%s» — заметку не ставлю' % (ph, r))
            continue
        сд = сделка_по_номеру(ph)
        if not сд:
            print('   %-14s сделки в CRM нет — пропускаю' % t.get('phone'))
            continue
        канал = 'Telegram' if str(t.get('channel')) in ('telegram', 'tg_bot') else 'WhatsApp'
        кто = t.get('persona') or 'Двойник'
        глагол = 'написала' if кто in ЖЕНСКИЕ else 'написал'
        текст = ('%s %s в %s: %s\n\n«%s»'
                 % (кто, глагол, канал,
                    t.get('occasion') or 'касание', str(t.get('body') or '').strip()))
        план.append((t, сд, текст))
        print('   %-14s → сделка %s «%s»' % (t['phone'], сд['id'], str(сд['name'])[:40]))
    if not план:
        print('нечего записывать')
        return 0
    if not APPLY:
        print('\nпример заметки:\n%s' % план[0][2][:300])
        print('\nЭто отчёт. Записать: --apply')
        return 0
    if not KEY:
        print('нет ключа PLP_WEBHOOK_KEY в окружении — отменяю')
        return 1
    ok = 0
    for t, сд, текст in план:
        res = amo('POST', 'leads/%d/notes' % сд['id'],
                  [{'note_type': 'common', 'params': {'text': текст}}])
        если_ок = '"id"' in res
        if если_ок:
            sb('/touch_queue?id=eq.%d' % t['id'], 'PATCH',
               {'source_ref': 'amo_note:%s' % сд['id']})
            ok += 1
        else:
            print('   ✗ %s: %s' % (t['phone'], res[:110]))
    print('\nзаписано заметок: %d из %d' % (ok, len(план)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
