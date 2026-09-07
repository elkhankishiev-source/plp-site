#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Приводит описания объектов к человеческому виду.

Зачем: часть карточек хранит заметки из материалов застройщика — смесь языков
и внутренних сокращений («363 units», «Common 5,230 м², вкл. green 1,800»).
Клиент это читает на странице объекта. Переписываем по-русски, ничего не
добавляя от себя: только то, что уже есть в описании.

    python3 tools/polish_usp.py                 # показать «было → стало», не менять
    python3 tools/polish_usp.py --apply         # записать в карточки
    python3 tools/polish_usp.py --id PLP-VIVANA # один объект
"""
import argparse, json, os, re, sys, urllib.request

MODEL = 'claude-sonnet-4-6'
RAW = re.compile(r'[A-Za-z]{4,}')


def creds():
    c = json.load(open('/tmp/.sb'))
    return c['url'], c['key']


URL, KEY = creds()
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}


def anthropic_key():
    """Ключ живёт в n8n — там же, где им пользуются боты. Отдельной копии не заводим."""
    k = os.environ.get('ANTHROPIC_API_KEY')
    if k:
        return k
    try:
        src = open(os.path.expanduser('~/plp_diag.py'), encoding='utf-8').read()
        api = re.search(r'API_KEY\s*=\s*"([^"]+)"', src).group(1)
        v = json.load(urllib.request.urlopen(urllib.request.Request(
            'https://proplib.app.n8n.cloud/api/v1/variables?limit=100', headers={'X-N8N-API-KEY': api}), timeout=60))
        for x in v['data']:
            if x['key'] == 'ANTHROPIC_API_KEY' and x.get('value'):
                return x['value']
    except Exception as e:
        sys.exit('не достал ключ Anthropic: ' + str(e)[:120])
    sys.exit('ключа Anthropic нет ни в окружении, ни в n8n')


AK = None

SYSTEM = (
    'Ты редактор карточек недвижимости Property Library Phuket. '
    'Тебе дают сырое описание проекта — заметки из материалов застройщика. '
    'Перепиши его для страницы объекта на сайте.\n'
    'ПРАВИЛА:\n'
    '— только по-русски, без английских слов и внутренних сокращений;\n'
    '— НИЧЕГО не добавляй: все числа, названия и факты бери из исходника;\n'
    '— что непонятно или похоже на служебную пометку — выбрасывай;\n'
    '— 3–5 коротких предложений, спокойный тон, без рекламных восклицаний;\n'
    '— не обещай доходность и не называй проценты, если их нет в исходнике;\n'
    '— не пиши контакты, комиссии и ссылки;\n'
    '— начни с того, что это за проект и где он, дальше — чем интересен.\n'
    'Верни только готовый текст, без пояснений.'
)


def ask(raw, name):
    body = {'model': MODEL, 'max_tokens': 600, 'system': SYSTEM,
            'messages': [{'role': 'user', 'content': 'Проект: %s\n\nСырое описание:\n%s' % (name, raw)}]}
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                                 headers={'x-api-key': AK, 'anthropic-version': '2023-06-01',
                                          'content-type': 'application/json'})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    return (r['content'][0]['text'] or '').strip()


def main():
    global AK
    ap = argparse.ArgumentParser(description='Причесать описания объектов')
    ap.add_argument('--apply', action='store_true', help='записать результат в карточки')
    ap.add_argument('--id', help='только один объект')
    ap.add_argument('--limit', type=int, default=3, help='сколько объектов взять (по умолчанию 3)')
    a = ap.parse_args()
    AK = anthropic_key()

    q = URL + '/rest/v1/objects?select=plp_property_id,name,usp&on_site=is.true&order=plp_property_id'
    if a.id:
        q += '&plp_property_id=eq.' + a.id
    rows = json.load(urllib.request.urlopen(urllib.request.Request(q, headers=H), timeout=90))
    rows = [r for r in rows if (r.get('usp') or '').strip() and RAW.search(r['usp'])]
    if not a.id:
        rows = rows[:a.limit]
    if not rows:
        print('нечего править')
        return

    for r in rows:
        new = ask(r['usp'], r.get('name') or r['plp_property_id'])
        print('\n═══ %s · %s ═══' % (r['plp_property_id'], (r.get('name') or '')[:40]))
        print('было:  ', r['usp'][:220].replace('\n', ' '))
        print('стало: ', new[:400].replace('\n', ' '))
        if a.apply:
            req = urllib.request.Request(
                URL + '/rest/v1/objects?plp_property_id=eq.' + r['plp_property_id'],
                data=json.dumps({'usp': new}).encode(), headers=H, method='PATCH')
            urllib.request.urlopen(req, timeout=90)
            print('→ записано')
    if not a.apply:
        print('\nЭто показ. Чтобы записать — тот же запуск с --apply')


if __name__ == '__main__':
    main()
