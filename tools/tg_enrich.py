#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поднимаем по владельцам всё, что есть в личном Telegram Эльнура.

Для каждого человека с объектом ищем диалог — по телефону, затем по имени —
и забираем: id, @ник, когда последний раз общались, сколько сообщений.
По желанию (--facts) короткое резюме переписки: о чём договаривались.

    python3 tools/tg_enrich.py --dry        # показать, кого нашли
    python3 tools/tg_enrich.py              # записать id и ник в базу
    python3 tools/tg_enrich.py --facts      # плюс резюме переписки в заметку
"""
import argparse, asyncio, json, os, pathlib, re, shutil, sys, urllib.request

c = json.load(open('/tmp/.sb'))
URL, KEY = c['url'], c['key']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
SKIP = {'PLP-001555', 'PLP-004198'}          # тестовая запись и сам Эльнур


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


SYSTEM = (
    'Ты читаешь личную переписку риелтора с клиентом и выжимаешь суть для карточки клиента. '
    'Верни СТРОГО JSON: {"facts":["..."]} — до четырёх коротких пунктов по-русски: '
    'о чём договорились, что человек ищет, что обещали, что мешает. '
    'Только то, что прямо сказано в переписке. Ничего не выдумывай. '
    'НЕ переносить наши комиссии и заработки. '
    'Не утверждать, что клиент кому-то должен, если это не сказано прямо.'
)


def ask(text, name, ak):
    r = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps({'model': 'claude-sonnet-4-6', 'max_tokens': 600, 'system': SYSTEM,
                         'messages': [{'role': 'user',
                                       'content': 'Переписка с клиентом %s:\n\n%s' % (name, text[:18000])}]}).encode(),
        headers={'x-api-key': ak, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    t = json.load(urllib.request.urlopen(r, timeout=180))['content'][0]['text']
    return json.loads(t[t.find('{'):t.rfind('}') + 1]).get('facts') or []


async def run(people, want_facts, dry):
    from telethon import TelegramClient
    src = pathlib.Path('/Users/elnurkhankishiev/.tg_session_userbot.session')
    copy = pathlib.Path('/tmp/plp_tg_enrich2.session')
    if copy.exists():
        copy.unlink()
    shutil.copy(src, copy)
    creds = json.loads(pathlib.Path('/Users/elnurkhankishiev/.tg_creds.json').read_text())
    cl = TelegramClient(str(copy).replace('.session', ''), int(creds['api_id']), creds['api_hash'])
    await cl.start()
    ak = anthropic_key() if want_facts else None

    # один проход по диалогам: собираем и телефоны, и имена
    dialogs = []
    async for d in cl.iter_dialogs(limit=600):
        e = d.entity
        # только личные диалоги: группы, каналы и боты нам не подходят
        if getattr(e, 'bot', False) or not hasattr(e, 'first_name'):
            continue
        dialogs.append({'name': d.name or '', 'entity': e, 'id': d.id,
                        'phone': re.sub(r'\D', '', getattr(e, 'phone', '') or '')})
    print('диалогов просмотрено:', len(dialogs))

    for p in people:
        phone = re.sub(r'\D', '', p.get('phone') or '')
        hit = None
        # 1) уже знаем telegram-id — берём его, ничего не угадываем
        if p.get('tg_id'):
            hit = next((d for d in dialogs if getattr(d['entity'], 'id', None) == p['tg_id']), None)
        # 2) телефон — единственное надёжное совпадение
        if not hit and phone:
            hit = next((d for d in dialogs if d['phone'] and d['phone'][-9:] == phone[-9:]), None)
        # 3) по имени — только если совпало И имя, И фамилия: одного «Виктора»
        #    мало, иначе к Виктору Путило прилетает Виктория
        if not hit:
            words = [w.lower() for w in re.split(r'[\s(),]+', p.get('name') or '')
                     if len(w) > 3 and w.isalpha()]
            if len(words) >= 2:
                hit = next((d for d in dialogs
                            if all(w in d['name'].lower() for w in words[:2])), None)
        if not hit:
            print('%-14s %-26s — в Telegram не нашёл' % (p['code'], (p.get('name') or '')[:26]))
            continue

        e = hit['entity']
        uname = getattr(e, 'username', None)
        msgs = await cl.get_messages(hit['id'], limit=60)
        last = msgs[0].date.strftime('%d.%m.%Y') if msgs else '—'
        print('%-14s %-26s @%-16s сообщений %d, последнее %s'
              % (p['code'], (p.get('name') or '')[:26], uname or '—', len(msgs), last))
        if dry:
            continue

        patch = {}
        if not p.get('tg_id'):
            patch['tg_id'] = getattr(e, 'id', None)
        add = ['Telegram: @' + uname] if uname else []
        add.append('Последнее сообщение в Telegram: ' + last)

        if want_facts and msgs:
            text = '\n'.join('%s: %s' % ('мы' if m.out else 'клиент', (m.message or '')[:400])
                             for m in reversed(msgs) if m.message)
            if len(text) > 200:
                try:
                    facts = ask(text, p.get('name') or '', ak)
                    if facts:
                        add.append('Из переписки в Telegram: ' + ' · '.join(facts[:4]))
                        for f in facts[:4]:
                            print('      • ' + str(f)[:96])
                except Exception as ex:
                    print('      резюме не вышло:', str(ex)[:60])

        have = p.get('notes') or ''
        fresh = [x for x in add if x.split(':')[0] not in have]
        if fresh:
            patch['notes'] = (have + '\n' + '\n'.join(fresh)).strip()
        if patch:
            req('PATCH', 'clients?code=eq.' + p['code'], patch)
    await cl.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--facts', action='store_true', help='добавить резюме переписки')
    a = ap.parse_args()

    links = req('GET', 'client_objects?select=client_id&limit=500') or []
    ids = sorted({x['client_id'] for x in links})
    people = []
    for i in range(0, len(ids), 25):
        people += req('GET', 'clients?select=client_id,code,name,phone,tg_id,notes&client_id=in.(%s)'
                      % ','.join(ids[i:i + 25])) or []
    people = [p for p in people if p['code'] not in SKIP]
    print('владельцев:', len(people))
    asyncio.run(run(people, a.facts, a.dry))


if __name__ == '__main__':
    main()
