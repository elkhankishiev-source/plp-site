#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разведка по рабочей почте: что вообще есть по каждому владельцу.

Ищем письма по фамилии, почте, последним цифрам телефона и по кодам его юнитов
(всегда «проект + юнит»). Показываем: сколько писем, какие вложения, темы.
Ничего не скачиваем и не пишем в базу — это карта, по которой дальше работаем.

    python3 tools/mail_scan_clients.py              # по всем владельцам
    python3 tools/mail_scan_clients.py PLP-001858   # по одному
"""
import email, imaplib, json, pathlib, re, sys, urllib.request
from email.header import decode_header

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}
SKIP = {'PLP-001555', 'PLP-004198'}
# Ищем во всех рабочих папках, а не только во «Входящих»: договоры Эльнур
# часто отправлял сам, и часть переписки лежит в архиве и в папке личной почты.
FOLDERS = ['INBOX', 'Sent', '&BBAEQARFBDgEMgQ4BEAEPgQyBDAEQgRM-',
           'el.khankishiev@gmail.com', 'Archive', 'Sent Messages', 'Drafts']
DOC = re.compile(r'\.(pdf|docx?|xlsx?|jpg|jpeg|png)$', re.I)
CONTRACT = re.compile(r'contract|agreement|договор|lease|sale|purchase|reservation|бронир', re.I)
MONEY = re.compile(r'invoice|payment|счёт|счет|платёж|платеж|schedule|график', re.I)


def req(path):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(URL + '/rest/v1/' + path, headers=H), timeout=90))


def dec(s):
    out = ''
    for part, enc in decode_header(s or ''):
        out += part.decode(enc or 'utf-8', errors='replace') if isinstance(part, bytes) else part
    return out


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


def search(M, term):
    """Ищем по всем рабочим папкам; ключ письма — папка + номер."""
    out = set()
    for box in FOLDERS:
        try:
            typ, _ = M.select('"%s"' % box, readonly=True)
            if typ != 'OK':
                continue
            typ, data = M.search(None, 'TEXT', '"%s"' % term)
            for i in (data[0] or b'').split():
                out.add((box, i))
        except Exception:
            continue
    return out


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    links = req('client_objects?select=client_id,object_id&limit=500')
    by_client = {}
    for x in links:
        by_client.setdefault(x['client_id'], []).append(x['object_id'])
    ids = sorted(by_client)
    people = []
    for i in range(0, len(ids), 25):
        people += req('clients?select=client_id,code,name,phone,email&client_id=in.(%s)'
                      % ','.join(ids[i:i + 25]))
    people = [p for p in people if p['code'] not in SKIP and (not only or p['code'] == only)]

    M = connect()
    print('владельцев к проверке:', len(people), '· папок:', len(FOLDERS), '\n')

    for p in people:
        terms = []
        name = (p.get('name') or '').strip()
        for w in re.split(r'[\s(),]+', name):
            if len(w) > 4 and w.isalpha():
                terms.append(w)
        if p.get('email'):
            terms.append(p['email'])
        ph = re.sub(r'\D', '', p.get('phone') or '')
        if len(ph) >= 9:
            terms.append(ph[-9:])

        ids_found = set()
        for t in terms[:4]:
            ids_found |= search(M, t)
        # плюс письма по его юнитам: всегда проект + юнит
        for code in by_client.get(p['client_id'], []):
            parts = code.split('-')
            if len(parts) >= 3:
                proj, unit = parts[1], parts[2]
                for box in FOLDERS:
                    try:
                        typ, _ = M.select('"%s"' % box, readonly=True)
                        if typ != 'OK':
                            continue
                        typ, data = M.search(None, '(TEXT "%s" TEXT "%s")' % (proj, unit))
                        for i in (data[0] or b'').split():
                            ids_found.add((box, i))
                    except Exception:
                        continue

        if not ids_found:
            print('%-26s %-16s — писем нет' % (name[:26], p.get('phone') or ''))
            continue

        docs, subjects, dates = [], [], []
        for box, i in list(ids_found)[-40:]:
            try:
                M.select('"%s"' % box, readonly=True)
                typ, msg = M.fetch(i, '(RFC822)')
                m = email.message_from_bytes(msg[0][1])
            except Exception:
                continue
            subj = dec(m.get('Subject'))
            subjects.append(subj)
            dates.append(dec(m.get('Date'))[:16])
            for part in m.walk():
                fn = dec(part.get_filename() or '')
                if fn and DOC.search(fn):
                    docs.append(fn)

        contracts = [d for d in docs if CONTRACT.search(d)]
        bills = [d for d in docs if MONEY.search(d)]
        print('%-26s %-16s писем %-4d вложений %-3d · договоров %d · счетов %d'
              % (name[:26], p.get('phone') or '', len(ids_found), len(docs), len(contracts), len(bills)))
        for d in (contracts + bills)[:4]:
            print('      📎 ' + d[:80])
        for s in subjects[-3:]:
            if s:
                print('      · ' + s[:80])
    M.logout()


if __name__ == '__main__':
    main()
