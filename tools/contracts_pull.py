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
           'el.khankishiev@gmail.com', 'Archive', 'Sent Messages', 'Drafts',
           'Spam', 'Junk']
# «Agency Agreement» — это НАШ договор с застройщиком, в карточку клиента не кладём
CONTRACT = re.compile(r'contract|agreement|договор|lease|purchase|reservation|schedule|график|'
                      r'addendum|дополнительн|booking|s&p|sale', re.I)
AGENCY = re.compile(r'agency\s*agreement|агентск', re.I)
# как застройщик сокращает наши проекты в именах файлов
PROJ_CODE = {'LEGENDARY': 'LEB', 'KATABELLO': 'KAT', 'ESTELLA': 'EST',
             'HERITAGE': 'HEB', 'SERENITY': 'SEN', 'CIELO': 'CIR',
             'MODEVA': 'MOB', 'ADORA': 'ADR'}


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
    flat = unit.replace('-', '')
    # Кто владелец — по нему и ищем: в письмах застройщика проект называется
    # своим кодом («PARK 2_NP»), а вот фамилия клиента и номер юнита есть всегда.
    owners = []
    try:
        rows = req('GET', 'client_objects?select=client_id&object_id=eq.' + code) or []
        for r in rows[:3]:
            c = req('GET', 'clients?select=name&client_id=eq.%s&limit=1' % r['client_id'])
            if c and c[0].get('name'):
                for w in re.split(r'[\s(),]+', c[0]['name']):
                    if len(w) > 4 and w.isalpha():
                        owners.append(w)
    except Exception:
        pass

    queries = ['(TEXT "%s" TEXT "%s")' % (proj, unit),
               '(TEXT "%s" TEXT "%s")' % (proj, flat)]
    for w in owners[:3]:
        queries.append('(TEXT "%s" TEXT "%s")' % (w, flat))
    if len(flat) >= 4:
        queries.append('TEXT "%s"' % flat)          # номер юнита сам по себе достаточно редкий

    found = []
    for box in FOLDERS:
        try:
            typ, _ = M.select('"%s"' % box, readonly=True)
            if typ != 'OK':
                continue
            for q in queries:
                try:
                    typ, data = M.search(None, q)
                    for i in (data[0] or b'').split():
                        found.append((box, i))
                except Exception:
                    continue
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
            if not CONTRACT.search(fn) or AGENCY.search(fn):
                continue
            # У застройщика в имени файла стоит код ЕГО проекта: PH-LEB (Legendary),
            # PH-KAT (Katabello), PH-EST (Estella). Номер юнита сам по себе врёт:
            # A-606 есть и в Legendary, и в Katabello. Чужой код — файл не наш.
            other = re.search(r'PH-([A-Z]{3})', fn, re.I)
            if other and PROJ_CODE.get(proj.upper()) and other.group(1).upper() != PROJ_CODE[proj.upper()]:
                continue
            if not re.search(r'\.(pdf|docx?)$', fn, re.I):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            is_pdf = payload[:4] == b'%PDF'
            # предпочитаем PDF: его модель прочитает; docx просто сохраним в карточку
            score = (1 if is_pdf else 0, len(payload))
            if best is None or score > best[3]:
                best = (fn, payload, dec(m.get('Subject')), score)
    if not best:
        print('%-22s договоров в письмах нет' % code)
        return
    fn, payload, subj, _score = best
    print('%-22s %s (%.1f МБ)' % (code, fn[:52], len(payload) / 1048576))
    if payload[:4] != b'%PDF':
        print('      это не PDF — сохраню в карточку, но читать не буду')
        f = {}
    else:
        try:
            f = ask_pdf(payload, ak, unit)
        except Exception as e:
            print('      прочитать не вышло:', str(e)[:80])
            f = {}
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
