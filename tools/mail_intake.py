#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборщик рабочей почты: письма с вложениями попадают в систему, а не лежат в ящике.

Эльнур 18.09.2026: «го всё по порядку, не бросай, делай».

Зачем. Цепочка «почта → разбор → карточка» существовала только на бумаге: приёмник
документов в n8n был выключен, и звать его было некому — сборщика писем не было
вообще. А в ящике elnur@property-library.com лежит ровно то, что обязано быть в
карточках: график платежей и штраф по Ayana Heights F607, лизхолд-договор на подпись,
чек по расторгнутому юниту от Rhom Bho, отчёты застройщиков о стройке.

Что делает. Раз в пятнадцать минут заходит по IMAP, берёт новые письма, вытаскивает
вложения и ссылки на Диск и Дропбокс, кладёт файлы в приватное хранилище и заводит
строку в mail_intake. В карточки клиентов ничего не пишет: по канону правку истины
делает человек, задача сборщика — чтобы ничего не потерялось и всё было видно.

Отправителя пытается узнать: сверяет адрес письма с контактами клиентов. Узнал —
подставляет клиента, не узнал — оставляет пустым, врать не надо.

Почта на GoDaddy: imap.secureserver.net:993. Логин и пароль в ~/.plp_titan_mail.

    python3 mail_intake.py            # отчёт: что нашлось, ничего не пишет
    python3 mail_intake.py --apply    # разобрать и записать
    python3 mail_intake.py --days 60  # насколько глубоко смотреть (по умолчанию 3)
"""
import email, imaplib, json, os, re, sys, urllib.parse, urllib.request
from email.header import decode_header

APPLY = '--apply' in sys.argv
DAYS = 3
if '--days' in sys.argv:
    DAYS = int(sys.argv[sys.argv.index('--days') + 1])

MAIL_FILE = os.path.expanduser('~/.plp_titan_mail')
# На Маке ключи лежат в своём файле, на VPS — в .env сервиса. Берём тот, что есть.
ENV_FILE = next((p for p in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env') if os.path.exists(p)), os.path.expanduser('~/.plp_site_supabase.env'))
BUCKET = 'client-docs'
OWNER_TG = '509498386'   # личный Telegram Эльнура: туда уходят протоколы созвонов
# Почтовые адреса расшифровщиков: письмо от них — это и есть готовый протокол.
NOTETAKER = re.compile(r'@(tldv\.io|fathom\.video|otter\.ai|fireflies\.ai|read\.ai|tactiq\.io|grain\.com|sembly\.ai)$', re.I)
KEEP = re.compile(r'\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|heic|zip)$', re.I)
LINKS = re.compile(r'https?://(?:drive\.google\.com|docs\.google\.com|www\.dropbox\.com|dropbox\.com)[^\s<>"\')]+', re.I)
KIND = [('договор', r'agreement|contract|договор|лизхолд|leasehold'),
        ('счёт', r'invoice|счёт|payment request|штраф|penalty'),
        ('график платежей', r'payment schedule|график платеж|schedule of payment'),
        ('прайс', r'price\s*list|прайс|termsheet|term sheet'),
        ('стройка', r'construction update|progress report|отчёт о строительстве'),
        ('рассылка', r'newsletter|unsubscribe|invitation|webinar')]


def env():
    out = {}
    for ln in open(ENV_FILE, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/')
KEY = E['SUPABASE_SERVICE_KEY']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}


def rest(path, method='GET', body=None, raw=None, ctype='application/json'):
    h = dict(H)
    h['Content-Type'] = ctype
    # Файл с тем же именем уже лежит в хранилище — это не ошибка, а повтор разбора:
    # без этого заголовка повторный проход писал в карточку письма «не сохранилось».
    if path.startswith('/storage/'):
        h['x-upsert'] = 'true'
    if method in ('POST', 'PATCH'):
        h['Prefer'] = 'return=representation'
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            t = f.read().decode('utf-8', 'replace')
        return json.loads(t) if t.strip().startswith(('[', '{')) else t
    except urllib.error.HTTPError as ex:
        return {'error': ex.code, 'body': ex.read().decode('utf-8', 'replace')[:200]}


def notify(text, to_owner=False):
    tok = os.environ.get('TG_BOT_TOKEN') or E.get('TG_BOT_TOKEN') or ''
    # Протокол созвона уходит лично Эльнуру, деловое письмо — в рабочий чат.
    chat = (OWNER_TG if to_owner else '') or os.environ.get('TG_ALERT_CHAT_ID') or E.get('TG_ALERT_CHAT_ID') or ''
    if not tok or not chat:
        return
    try:
        req = urllib.request.Request(
            'https://api.telegram.org/bot' + tok + '/sendMessage',
            data=json.dumps({'chat_id': chat, 'text': text,
                             'disable_web_page_preview': True}).encode(),
            headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=20)
    except Exception:
        pass


def dec(s):
    if not s:
        return ''
    out = []
    for part, enc in decode_header(s):
        if isinstance(part, bytes):
            try:
                out.append(part.decode(enc or 'utf-8', 'replace'))
            except LookupError:
                out.append(part.decode('utf-8', 'replace'))
        else:
            out.append(part)
    return ''.join(out)


def guess(subject, names):
    hay = (subject + ' ' + ' '.join(names)).lower()
    for label, rx in KIND:
        if re.search(rx, hay, re.I):
            return label
    return None


def known_client(addr):
    """Узнаём отправителя по адресу: почта → контакт amoCRM → его телефон → наш клиент.
    Отдельного поля с почтой у клиента нет, адреса лежат в карточках amoCRM внутри
    custom_fields; для этого 18.09.2026 заведено представление contact_emails."""
    if not addr:
        return None
    a = urllib.parse.quote(addr.lower())
    rows = rest('/rest/v1/contact_emails?select=contact_id,contact_name&email=eq.' + a + '&limit=5')
    if not isinstance(rows, list) or not rows:
        return None
    ids = ','.join(str(r['contact_id']) for r in rows)
    ph = rest('/rest/v1/crm_contact_phones?select=phone_norm&contact_id=in.(%s)&limit=10' % ids)
    for p in (ph if isinstance(ph, list) else []):
        cp = rest('/rest/v1/client_profiles?select=client_id,name&phone_norm=eq.' + str(p['phone_norm']) + '&limit=1')
        if isinstance(cp, list) and cp and cp[0].get('client_id'):
            return cp[0]
    return None


UNIT_RX = re.compile(r'\b([A-Za-z]{1,3})[\-\s]?(\d{3,4})\b')


def unit_map():
    """Карта «номер юнита → клиент и объект» из связок client_objects.
    Письма от застройщиков почти всегда называют юнит в теме: F-607, C-408, MBD103,
    KKF702. Это надёжнее почты отправителя: адрес может быть чужой, номер юнита — нет."""
    rows = rest('/rest/v1/client_objects?select=client_id,object_id,unit,project_name,rel&limit=500')
    m = {}
    for r in (rows if isinstance(rows, list) else []):
        u = re.sub(r'[^A-Za-z0-9]', '', str(r.get('unit') or '')).upper()
        if len(u) >= 4:
            m.setdefault(u, r)
    return m


def find_unit(text, umap):
    for mt in UNIT_RX.finditer(text or ''):
        key = (mt.group(1) + mt.group(2)).upper()
        if key in umap:
            return umap[key]
        # в письме «PH-MOB-MBD103» встречается и часть кода, и полный номер
        for k in umap:
            if k.endswith(key) or key.endswith(k):
                return umap[k]
    return None


def rematch():
    """Пройтись по уже разобранным письмам и проставить клиента там, где узнали."""
    rows = rest('/rest/v1/mail_intake?select=id,from_email,subject,body_preview,files,client_id&client_id=is.null')
    umap = unit_map()
    fixed = 0
    for r in (rows if isinstance(rows, list) else []):
        # номер юнита часто стоит только в имени вложения: PH-MOB-MBD103-Warning+INV-Signed.pdf
        hay = ' '.join([r.get('subject') or '', r.get('body_preview') or ''] +
                       [f.get('name') or '' for f in (r.get('files') or [])])
        hit = find_unit(hay, umap)
        if hit:
            rest('/rest/v1/mail_intake?id=eq.%d' % r['id'], 'PATCH',
                 {'client_id': hit['client_id'], 'object_id': hit['object_id'],
                  'note': 'узнан по номеру юнита %s (%s)' % (hit.get('unit'), hit.get('project_name'))})
            print('  письмо %d → %s %s' % (r['id'], hit.get('project_name'), hit.get('unit')))
            fixed += 1
            continue
        cl = known_client(r.get('from_email'))
        if cl:
            rest('/rest/v1/mail_intake?id=eq.%d' % r['id'], 'PATCH', {'client_id': cl['client_id']})
            print('  письмо %d → клиент %s' % (r['id'], cl.get('name') or cl['client_id']))
            fixed += 1
    print('узнано отправителей: %d из %d' % (fixed, len(rows) if isinstance(rows, list) else 0))
    return 0


def accounts():
    """Ящиков у нас несколько (elnur@, info@, key@ и другие на GoDaddy).
    Список живёт в ~/.plp_mail_accounts, по строке на ящик: логин;пароль[;сервер].
    Файла нет — работаем с одним ящиком из ~/.plp_titan_mail, как раньше."""
    multi = os.path.expanduser('~/.plp_mail_accounts')
    out = []
    if os.path.exists(multi):
        for ln in open(multi, encoding='utf-8'):
            ln = ln.strip()
            if not ln or ln.startswith('#'):
                continue
            parts = [x.strip() for x in ln.split(';')]
            out.append((parts[0], parts[1], parts[2] if len(parts) > 2 else 'imap.secureserver.net'))
    if not out:
        u, p = [l.strip() for l in open(MAIL_FILE, encoding='utf-8') if l.strip()][:2]
        out.append((u, p, 'imap.secureserver.net'))
    return out


def main():
    if '--rematch' in sys.argv:
        return rematch()
    total = 0
    for u, p, host in accounts():
        print('== ящик %s' % u)
        try:
            total += one_box(u, p, host)
        except Exception as ex:
            print('   не зашёл: %s' % str(ex)[:120])
    return 0


def one_box(u, p, host):
    m = imaplib.IMAP4_SSL(host, 993, timeout=40)
    m.login(u, p)
    m.select('INBOX')
    since = (__import__('datetime').date.today() - __import__('datetime').timedelta(days=DAYS)).strftime('%d-%b-%Y')
    st, ids = m.search(None, 'SINCE', since)
    ids = ids[0].split()
    print('писем с %s: %d' % (since, len(ids)))
    seen = 0
    for i in ids:
        st, d = m.fetch(i, '(RFC822)')
        if not d or not d[0]:
            continue
        msg = email.message_from_bytes(d[0][1])
        mid = (msg.get('Message-ID') or '').strip() or ('noid-' + i.decode())
        subject = dec(msg.get('Subject'))
        frm = dec(msg.get('From'))
        addr = (re.findall(r'[\w.+-]+@[\w.-]+', frm) or [''])[0].lower()
        date = msg.get('Date') or ''
        files, text = [], ''
        for part in msg.walk():
            ctype = part.get_content_type()
            fname = dec(part.get_filename())
            if fname and KEEP.search(fname):
                payload = part.get_payload(decode=True) or b''
                files.append({'name': fname, 'size': len(payload), 'type': ctype, '_bytes': payload})
            elif ctype == 'text/plain' and not text:
                try:
                    text = (part.get_payload(decode=True) or b'').decode('utf-8', 'replace')[:4000]
                except Exception:
                    pass
        links = sorted(set(LINKS.findall(text)))[:8]
        # 18.09.2026, Эльнур: «транскрибатор может мне результаты отправлять сразу в ТГ?
        # Чтобы я их не искал нигде». Любой расшифровщик присылает итог письмом —
        # значит письмо и есть доставка: пересылаем текст ему в Telegram как есть.
        if NOTETAKER.search(addr or ''):
            body = re.sub(r'\n{3,}', '\n\n', text).strip()
            head = 'Протокол созвона: %s\n\n' % subject[:120]
            if APPLY and body:
                notify(head + body[:3200], to_owner=True)
                print('  протокол с созвона отправлен в Telegram: %s' % subject[:60])
            continue
        if not files and not links:
            continue
        seen += 1
        kind = guess(subject, [f['name'] for f in files])
        print('  %-42s | %-58s | вложений %d, ссылок %d%s'
              % (frm[:42], subject[:58], len(files), len(links), (' | ' + kind) if kind else ''))
        if not APPLY:
            continue
        if isinstance(rest('/rest/v1/mail_intake?message_id=eq.' + urllib.parse.quote(mid) + '&select=id'), list) \
           and rest('/rest/v1/mail_intake?message_id=eq.' + urllib.parse.quote(mid) + '&select=id'):
            continue
        saved = []
        for f in files:
            # \w в питоне включает кириллицу, а ключ в хранилище её не принимает:
            # 25 вложений из 53 не сохранились с ошибкой InvalidKey. Оставляем только латиницу.
            safe = re.sub(r'[^A-Za-z0-9._-]+', '_', f['name']).strip('_')[-80:]
            if not re.search(r'[A-Za-z0-9]', safe):
                safe = 'file%d%s' % (files.index(f) + 1, os.path.splitext(f['name'])[1][:6])
            path = 'mail/%s/%s' % (re.sub(r'[^\w]+', '_', mid)[-40:], safe)
            up = rest('/storage/v1/object/' + BUCKET + '/' + urllib.parse.quote(path),
                      'POST', raw=f['_bytes'], ctype=f['type'] or 'application/octet-stream')
            ok = not (isinstance(up, dict) and up.get('error'))
            saved.append({'name': f['name'], 'size': f['size'], 'type': f['type'],
                          'path': (BUCKET + '/' + path) if ok else None,
                          'error': None if ok else str(up)[:120]})
        cl = known_client(addr)
        try:
            from email.utils import parsedate_to_datetime
            sent = parsedate_to_datetime(date).isoformat() if date else None
        except Exception:
            sent = None
        row = rest('/rest/v1/mail_intake', 'POST', {
            'message_id': mid, 'from_email': addr, 'from_name': frm[:120], 'sent_at': sent,
            'subject': subject[:300], 'body_preview': text[:600],
            'files': saved, 'links': links, 'guess_kind': kind,
            'client_id': (cl or {}).get('client_id'),
            'status': 'new'})
        if isinstance(row, dict) and row.get('error'):
            print('     не записал: %s' % str(row)[:140])
        elif kind in ('договор', 'счёт', 'график платежей', 'стройка'):
            # Деловое письмо не должно ждать, пока его кто-то заметит: сразу в офисный чат.
            # Рассылки и приглашения не трогаем, иначе чат превратится в шум.
            notify('📄 %s: %s\nот %s, файлов %d\nв приёмнике почты, ждёт решения'
                   % (kind, subject[:90], addr, len(saved)))
    m.logout()
    print('   писем с вложениями или ссылками: %d%s'
          % (seen, '' if APPLY else '  (это отчёт, запись включает --apply)'))
    return seen


if __name__ == '__main__':
    sys.exit(main())
