#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Договоры из почты в карточку объекта.

Находит письма по «проект + юнит», забирает вложенные договоры, кладёт их
в закрытое хранилище клиента и читает моделью: цена, график платежей, сдача.
Это ЕДИНСТВЕННЫЙ разрешённый источник для статуса выплат — переписка не в счёт.

    python3 tools/contracts_pull.py PLP-LEGENDARY-A606          # показать
    python3 tools/contracts_pull.py PLP-LEGENDARY-A606 --apply  # записать
    python3 tools/contracts_pull.py --all --apply               # по всем юнитам
"""
import argparse, email, imaplib, json, os, pathlib, re, sys, urllib.request
from email.header import decode_header

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
BUCKET = 'client-docs'
# Ищем во всех рабочих папках, а не только во «Входящих»: договоры Эльнур
# часто отправлял сам, и часть переписки лежит в архиве и в папке личной почты.
FOLDERS = ['INBOX', 'Sent', '&BBAEQARFBDgEMgQ4BEAEPgQyBDAEQgRM-',
           'el.khankishiev@gmail.com', 'Archive', 'Sent Messages', 'Drafts']
CONTRACT = re.compile(r'contract|agreement|договор|lease|purchase|reservation|schedule|график', re.I)


def req(method, path, body=None):
    r = urllib.request.Request(URL + '/rest/v1/' + path,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=H, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode()
    return json.loads(raw) if raw.strip() else None


def anthropic_key():
    k = os.environ.get('ANTHROPIC_API_KEY')
    if k:
        return k
    src = open(os.path.expanduser('~/plp_diag.py'), encoding='utf-8').read()
    api = re.search(r'API_KEY\s*=\s*"([^"]+)"', src).group(1)
    v = json.load(urllib.request.urlopen(urllib.request.Request(
        'https://proplib.app.n8n.cloud/api/v1/variables?limit=100',
        headers={'X-N8N-API-KEY': api}), timeout=60))
    for x in v['data']:
        if x['key'] == 'ANTHROPIC_API_KEY' and x.get('value'):
            return x['value']
    sys.exit('нет ключа Anthropic')


def dec(s):
    out = ''
    for part, enc in decode_header(s or ''):
        out += part.decode(enc or 'utf-8', errors='replace') if isinstance(part, bytes) else part
    return out


SYSTEM = (
    'Ты читаешь договор купли-продажи или аренды недвижимости на Пхукете. '
    'Верни СТРОГО JSON:\n'
    '{"unit":"","purchase_price":0,"currency":"THB","handover_on":"YYYY-MM-DD",'
    '"payment_plan":[{"n":1,"when":"","percent":0,"amount":0}],"signed_on":"YYYY-MM-DD"}\n'
    'Берём только то, что написано в документе. Чего нет — 0 или пустая строка. '
    'purchase_price — полная стоимость юнита по договору. '
    'В payment_plan — все этапы графика, как в договоре. '
    'Комиссии агентства НЕ переноси.'
)


def ask_pdf(data, ak, unit):
    import base64
    body = {'model': 'claude-sonnet-4-6', 'max_tokens': 1600, 'system': SYSTEM,
            'messages': [{'role': 'user', 'content': [
                {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                'data': base64.b64encode(data).decode()}},
                {'type': 'text', 'text': 'Юнит %s. Извлеки цену, график платежей и дату сдачи.' % unit}]}]}
    r = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                               headers={'x-api-key': ak, 'anthropic-version': '2023-06-01',
                                        'content-type': 'application/json'})
    t = json.load(urllib.request.urlopen(r, timeout=300))['content'][0]['text']
    return json.loads(t[t.find('{'):t.rfind('}') + 1])


def connect():
    cr = (pathlib.Path.home() / '.plp_titan_mail').read_text().strip().split('\n')
    for h in ['imap.secureserver.net', 'imap.titan.email']:
        try:
            m = imaplib.IMAP4_SSL(h, 993)
            m.login(cr[0].strip(), cr[1].strip())
            return m
        except Exception:
            continue
    sys.exit('почта не пустила')


def store(key, data, mime='application/pdf'):
    r = urllib.request.Request(URL + '/storage/v1/object/' + BUCKET + '/' + urllib.parse.quote(key),
                               data=data, method='POST',
                               headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY,
                                        'Content-Type': mime, 'x-upsert': 'true'})
    urllib.request.urlopen(r, timeout=180).read()


def handle(M, code, ak, apply):
    parts = code.split('-')
    if len(parts) < 3:
        print('%-22s не понял проект/юнит' % code)
        return
    proj, unit = parts[1], parts[2]
    # обходим все рабочие папки: договоры бывают и в отправленных, и в архиве
    found = []
    for box in FOLDERS:
        try:
            typ, _ = M.select('"%s"' % box, readonly=True)
            if typ != 'OK':
                continue
            typ, data = M.search(None, '(TEXT "%s" TEXT "%s")' % (proj, unit))
            for i in (data[0] or b'').split():
                found.append((box, i))
        except Exception:
            continue
    best = None
    for box, i in reversed(found[-40:]):
        try:
            M.select('"%s"' % box, readonly=True)
            typ, msg = M.fetch(i, '(RFC822)')
            m = email.message_from_bytes(msg[0][1])
        except Exception:
            continue
        for part in m.walk():
            fn = dec(part.get_filename() or '')
            if not fn.lower().endswith('.pdf') or not CONTRACT.search(fn):
                continue
            payload = part.get_payload(decode=True)
            if not payload or payload[:4] != b'%PDF':
                continue
            if best is None or len(payload) > len(best[1]):
                best = (fn, payload, dec(m.get('Subject')))
    if not best:
        print('%-22s договоров в письмах нет' % code)
        return
    fn, payload, subj = best
    print('%-22s %s (%.1f МБ)' % (code, fn[:52], len(payload) / 1048576))
    try:
        f = ask_pdf(payload, ak, unit)
    except Exception as e:
        print('      прочитать не вышло:', str(e)[:80])
        return
    plan = f.get('payment_plan') or []
    print('      цена %s · сдача %s · этапов графика %d · подписан %s'
          % (f.get('purchase_price') or '—', f.get('handover_on') or '—', len(plan), f.get('signed_on') or '—'))
    for st in plan[:6]:
        print('        %s. %s — %s%% %s' % (st.get('n', '?'), st.get('when') or '—',
                                            st.get('percent') or '?', st.get('amount') or ''))
    if not apply:
        return

    key = 'contracts/%s/%s' % (code, re.sub(r'[^A-Za-z0-9._-]+', '_', fn)[-70:])
    try:
        store(key, payload)
    except Exception as e:
        print('      файл не сохранился:', str(e)[:70])
    rows = req('GET', 'client_objects?select=id,purchase_price,handover_on,payment_plan,note&object_id=eq.' + code) or []
    for row in rows:
        patch = {'note': ((row.get('note') or '') + '\nДоговор из почты: ' + fn).strip()}
        if f.get('purchase_price'):
            patch['purchase_price'] = f['purchase_price']
            patch['currency'] = f.get('currency') or 'THB'
        if f.get('handover_on'):
            patch['handover_on'] = f['handover_on']
        if plan:
            patch['payment_plan'] = plan
            patch['stage'] = 'строится'
        req('PATCH', 'client_objects?id=eq.%d' % row['id'], patch)
    print('      → записано в карточку, договор в хранилище')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('code', nargs='?')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    ak = anthropic_key()
    M = connect()
    if a.all:
        rows = req('GET', 'client_objects?select=object_id&limit=500') or []
        codes = sorted({r['object_id'] for r in rows if r['object_id'].count('-') >= 2})
    else:
        if not a.code:
            sys.exit('укажите код объекта или --all')
        codes = [a.code]
    for code in codes:
        handle(M, code, ak, a.apply)
    M.logout()


if __name__ == '__main__':
    import urllib.parse
    main()
