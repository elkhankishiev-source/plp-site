#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Дополняем карточки людей тем, что уже есть в CRM и в личном Telegram.

Берём клиентов, у которых есть объекты, и для каждого ищем:
  • в amoCRM — полное имя, почту, второй телефон, id контакта и сделки;
  • в Telegram Эльнура — id и @ник, чтобы потом дать доступ в кабинет.
Пишем только пустое: то, что уже стоит, не трогаем.

    python3 tools/enrich_clients.py --dry     # показать, что нашлось
    python3 tools/enrich_clients.py           # записать
    python3 tools/enrich_clients.py --no-tg   # только CRM
"""
import argparse, asyncio, json, pathlib, re, shutil, urllib.parse, urllib.request

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
AMO_KEY = pathlib.Path('/Users/elnurkhankishiev/.plp_amo_proxy').read_text().strip()
PROXY = 'https://proplib.app.n8n.cloud/webhook/amo-proxy'


def req(method, path, body=None):
    r = urllib.request.Request(URL + '/rest/v1/' + path,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=H, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode()
    return json.loads(raw) if raw.strip() else None


def amo(ep):
    r = urllib.request.Request(PROXY, data=json.dumps({'ep': ep}).encode(),
                               headers={'x-plp-key': AMO_KEY, 'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(r, timeout=90))
    except Exception:
        return {}


def fields(contact):
    """Достаём почты и телефоны из карточки amoCRM."""
    mails, phones = [], []
    for f in (contact.get('custom_fields_values') or []):
        code = f.get('field_code')
        for v in (f.get('values') or []):
            val = str(v.get('value') or '')
            if code == 'EMAIL' and val:
                mails.append(val)
            elif code == 'PHONE' and val:
                phones.append(val)
    return mails, phones


async def tg_lookup(people):
    """Ищем людей в личном Telegram по телефону — нужен id для кабинета."""
    from telethon import TelegramClient
    from telethon.tl.functions.contacts import ImportContactsRequest
    from telethon.tl.types import InputPhoneContact
    src = pathlib.Path('/Users/elnurkhankishiev/.tg_session_userbot.session')
    copy = pathlib.Path('/tmp/plp_tg_enrich.session')
    if copy.exists():
        copy.unlink()
    shutil.copy(src, copy)
    creds = json.loads(pathlib.Path('/Users/elnurkhankishiev/.tg_creds.json').read_text())
    cl = TelegramClient(str(copy).replace('.session', ''), int(creds['api_id']), creds['api_hash'])
    await cl.start()
    found = {}
    # сначала пробуем по диалогам — это не трогает контакты Эльнура
    by_phone = {}
    async for d in cl.iter_dialogs(limit=500):
        ph = getattr(d.entity, 'phone', None)
        if ph:
            by_phone[re.sub(r'\D', '', ph)[-9:]] = d.entity
    for code, phone in people:
        tail = re.sub(r'\D', '', phone or '')[-9:]
        e = by_phone.get(tail)
        if e:
            found[code] = {'tg_id': e.id, 'username': getattr(e, 'username', None),
                           'name': ' '.join(x for x in [getattr(e, 'first_name', ''), getattr(e, 'last_name', '')] if x)}
    await cl.disconnect()
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--no-tg', action='store_true')
    a = ap.parse_args()

    links = req('GET', 'client_objects?select=client_id&limit=500') or []
    ids = sorted({x['client_id'] for x in links})
    people = []
    for i in range(0, len(ids), 25):
        chunk = ','.join(ids[i:i + 25])
        people += req('GET', 'clients?select=client_id,code,name,phone,email,tg_id,amo_contact_id,notes'
                             '&client_id=in.(%s)' % chunk) or []
    # служебные записи (тесты и сам Эльнур) не трогаем
    SKIP = {'PLP-001555', 'PLP-004198'}
    people = [p for p in people if p['code'] not in SKIP]
    print('людей с объектами:', len(people))

    tg = {}
    if not a.no_tg:
        try:
            tg = asyncio.run(tg_lookup([(p['code'], p.get('phone') or '') for p in people]))
            print('нашлись в Telegram:', len(tg))
        except Exception as e:
            print('Telegram пропущен:', str(e)[:80])

    for p in people:
        patch = {}
        phone = re.sub(r'\D', '', p.get('phone') or '')
        note_add = []

        if phone:
            r = amo('contacts?query=%s&limit=1&with=leads' % phone[-10:])
            cts = ((r.get('_embedded') or {}).get('contacts') or [])
            if cts:
                ct = cts[0]
                mails, phones = fields(ct)
                if not p.get('email') and mails:
                    patch['email'] = mails[0]
                if not p.get('amo_contact_id'):
                    patch['amo_contact_id'] = ct.get('id')
                nm = (ct.get('name') or '').strip()
                if nm and len(nm) > len(p.get('name') or '') and 'лид' not in nm.lower() and 'сделка' not in nm.lower():
                    patch['name'] = nm
                extra = [x for x in phones if re.sub(r'\D', '', x)[-9:] != phone[-9:]]
                if extra:
                    note_add.append('Ещё телефоны из CRM: ' + ', '.join(extra[:3]))
                leads = ((ct.get('_embedded') or {}).get('leads') or [])
                if leads:
                    note_add.append('Сделок в CRM: %d' % len(leads))

        t = tg.get(p['code'])
        if t:
            if not p.get('tg_id'):
                patch['tg_id'] = t['tg_id']
            if t.get('username'):
                note_add.append('Telegram: @' + t['username'])

        if note_add:
            have = p.get('notes') or ''
            fresh = [x for x in note_add if x.split(':')[0] not in have]
            if fresh:
                patch['notes'] = (have + '\n' + ' · '.join(fresh)).strip()
        if not patch:
            continue
        print('%-14s %-26s %s' % (p['code'], (patch.get('name') or p.get('name') or '')[:26],
                                  ', '.join(k for k in patch if k != 'notes') or 'заметка'))
        if not a.dry:
            req('PATCH', 'clients?code=eq.' + p['code'], patch)


if __name__ == '__main__':
    main()
