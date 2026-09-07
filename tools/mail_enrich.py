#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Наполнение карточек клиентов фактами из переписки.

По каждому юниту находит письма в рабочей почте, отдаёт их модели и получает
цифры: цена покупки, сдача, ближайший платёж, стадия. Пишет в client_objects
только пустые поля — то, что уже стоит руками, не трогаем.

    python3 tools/mail_enrich.py --dry            # показать, что нашлось
    python3 tools/mail_enrich.py                  # записать
    python3 tools/mail_enrich.py --unit F-607     # один юнит
"""
import argparse, email, imaplib, json, os, pathlib, re, sys, urllib.request
from email.header import decode_header

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}

# юнит в почте → наш код объекта
UNITS = {
    'F-519': 'PLP-AYANA-F519', 'F-607': 'PLP-AYANA-F607',
    'KKF-602': 'PLP-KATABELLO-F602', 'KKA-606': 'PLP-KATABELLO-A606',
    'KKF-702': 'PLP-KATABELLO-F702', 'KKF-707': 'PLP-KATABELLO-F707',
    'A-606': 'PLP-LEGENDARY-A606', 'A-707': 'PLP-LEGENDARY-A707',
    'E-206': 'PLP-LEGENDARY-E206', 'F-304': 'PLP-LEGENDARY-F304',
    'F-507': 'PLP-LEGENDARY-F507', 'I-705': 'PLP-LEGENDARY-I705',
    'MBA-509': 'PLP-MODEVA-A509', 'MBD-103': 'PLP-MODEVA-D103',
    'F-105': 'PLP-EDEN-F105', 'K-504': 'PLP-EDEN-K504',
    'BSC-413': 'PLP-BIANCANA-C413',
    'F-404': 'PLP-EDEN-F404', 'F-412': 'PLP-AYANA-F412', 'A-701': 'PLP-CAPRI-A701',
    'A-12': 'PLP-ESTELLA-A12', 'M-30': 'PLP-MORI-M30', 'D-301': 'PLP-LEGENDARY-D301',
    'G-402': 'PLP-BALCONY-G402', 'M-14': 'PLP-QABALAH-M14', '2417': 'PLP-BAYSIDE-2417',
    'C-202': 'PLP-AYANA-C202', 'F-4': 'PLP-QABALAH-F4', 'A-35': 'PLP-AYANA-A35',
    'F-3': 'PLP-QABALAH-F3', 'A-36': 'PLP-AYANA-A36', 'M-1': 'PLP-QABALAH-M1',
    'M-2': 'PLP-QABALAH-M2', 'M-4': 'PLP-QABALAH-M4', 'A-515': 'PLP-SERENITY-A515',
    'M-3': 'PLP-QABALAH-M3', 'D-306': 'PLP-BALCONY-D306', 'A-507': 'PLP-VIVI-A507',
    'A-304': 'PLP-VIVI-A304', 'F-2': 'PLP-QABALAH-F2',
}

SYSTEM = (
    'Ты разбираешь деловую переписку по покупке квартиры на Пхукете. '
    'Верни СТРОГО JSON без пояснений:\n'
    '{"purchase_price":0,"currency":"THB","handover_on":"YYYY-MM-DD",'
    '"next_payment_on":"YYYY-MM-DD","next_payment_amount":0,'
    '"stage":"бронь|договор|строится|сдан|расторгнут","payment_plan":"",'
    '"facts":["короткие факты по-русски"]}\n'
    'Правила: бери только то, что прямо написано в письмах. '
    'purchase_price — полная стоимость юнита, НЕ сумма отдельного платежа. '
    'Если чего-то нет — оставь пустым (0 или ""). Ничего не придумывай. '
    'В facts — до 4 коротких пунктов: что происходило со сделкой.\n'
    'ЗАПРЕЩЕНО переносить наши комиссии, агентские бонусы, чеки агентству и '
    'упоминания PPA / Property Library как получателя денег — это внутренняя кухня, '
    'её видит клиент в кабинете.\n'
    'Если письма явно про ДРУГОЙ проект или другой юнит — верни пустой JSON '
    '{"facts":[]} и ничего не выдумывай.\n'
    'НЕ утверждать, что клиент недоплатил или что есть долг: в письмах суммы бывают '
    'частичными и без последних поступлений. Такие места писать как '
    '«по письму от <дата> — сверить с графиком».'
)


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


AK = None


def dec(s):
    out = ''
    for part, enc in decode_header(s or ''):
        out += part.decode(enc or 'utf-8', errors='replace') if isinstance(part, bytes) else part
    return out


def body(msg):
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == 'text/plain':
                try:
                    return p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', 'replace')
                except Exception:
                    continue
        return ''
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', 'replace')
    except Exception:
        return ''


def ask(text, unit):
    r = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps({'model': 'claude-sonnet-4-6', 'max_tokens': 900, 'system': SYSTEM,
                         'messages': [{'role': 'user', 'content': 'Юнит %s. Письма:\n\n%s' % (unit, text[:24000])}]}).encode(),
        headers={'x-api-key': AK, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    t = json.load(urllib.request.urlopen(r, timeout=240))['content'][0]['text']
    return json.loads(t[t.find('{'):t.rfind('}') + 1])


def req(method, path, b=None):
    r = urllib.request.Request(URL + '/rest/v1/' + path,
                               data=json.dumps(b).encode() if b is not None else None,
                               headers=H, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode()
    return json.loads(raw) if raw.strip() else None


def main():
    global AK
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--unit')
    a = ap.parse_args()
    AK = anthropic_key()

    cr = (pathlib.Path.home() / '.plp_titan_mail').read_text().strip().split('\n')
    M = None
    for h in ['imap.secureserver.net', 'imap.titan.email']:
        try:
            M = imaplib.IMAP4_SSL(h, 993)
            M.login(cr[0].strip(), cr[1].strip())
            break
        except Exception:
            M = None
    if not M:
        sys.exit('почта не пустила')
    M.select('INBOX')

    todo = {a.unit: UNITS[a.unit]} if a.unit else UNITS
    for unit, code in todo.items():
        # «M-1» или «F-2» встречаются в чужих письмах сотнями. Такой маркер
        # ищем только вместе с названием проекта, иначе в карточку попадает чужое.
        # Номер юнита сам по себе ничего не значит: A-606 есть и в Legendary,
        # и в Katabello. Ищем ВСЕГДА вместе с названием проекта.
        project = code.split('-')[1].title() if code.count('-') >= 2 else ''
        if not project:
            print('%-22s пропущен: не понял проект по коду' % code)
            continue
        ids = set()
        for v in {unit, unit.replace('-', ' '), unit.replace('-', '')}:
            try:
                typ, data = M.search(None, '(TEXT "%s" TEXT "%s")' % (project, v))
                ids |= set((data[0] or b'').split())
            except Exception:
                pass
        chunks = []
        for i in list(ids)[-12:]:
            try:
                typ, msg = M.fetch(i, '(RFC822)')
                m = email.message_from_bytes(msg[0][1])
            except Exception:
                continue
            chunks.append('--- %s | %s\n%s' % (dec(m.get('Date'))[:22], dec(m.get('Subject'))[:90], body(m)[:2200]))
        if not chunks:
            print('%-22s писем нет' % code)
            continue
        try:
            f = ask('\n\n'.join(chunks), unit)
        except Exception as e:
            print('%-22s разбор не вышел: %s' % (code, str(e)[:70]))
            continue
        print('%-22s цена %-12s сдача %-11s платёж %s %s' % (
            code, f.get('purchase_price') or '—', f.get('handover_on') or '—',
            f.get('next_payment_on') or '—', f.get('next_payment_amount') or ''))
        for x in (f.get('facts') or [])[:4]:
            print('      • ' + str(x)[:96])
        if a.dry:
            continue
        rows = req('GET', 'client_objects?select=id,purchase_price,handover_on,next_payment_on,next_payment_amount,stage,payment_plan,note&object_id=eq.' + code)
        for row in (rows or []):
            patch = {}
            if not row.get('purchase_price') and f.get('purchase_price'):
                patch['purchase_price'] = f['purchase_price']
                patch['currency'] = f.get('currency') or 'THB'
            for k in ('handover_on', 'next_payment_on', 'stage', 'payment_plan'):
                if not row.get(k) and f.get(k):
                    patch[k] = f[k]
            if not row.get('next_payment_amount') and f.get('next_payment_amount'):
                patch['next_payment_amount'] = f['next_payment_amount']
            facts = ' · '.join(str(x) for x in (f.get('facts') or [])[:4])
            if facts:
                patch['note'] = ((row.get('note') or '') + '\nИз переписки: ' + facts).strip()
            if patch:
                req('PATCH', 'client_objects?id=eq.%d' % row['id'], patch)
        print('      → записано в карточку')
    M.logout()


if __name__ == '__main__':
    main()
