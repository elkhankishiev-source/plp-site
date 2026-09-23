#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Читает документы клиента моделью и кладёт разбор в client_docs.parsed.

Эльнур 23.09.2026: «кредит пополнил, вперёд решай все зависшие задачи».
Это и была зависшая: 18 документов лежали со статусом «new», среди них
договоры по Ayana F-607 и Modeva D-103, которые закрывают цены и графики.

Отличие от contracts_pull.py: тот ходит в почту и ищет новое. Этот берёт то,
что уже лежит в хранилище, и только читает. Разделены нарочно — поиск в почте
и чтение моделью ломаются по разным причинам, и чинить их надо порознь.

Картинки читаются так же, как PDF: у счетов от застройщика часто нет текстового
слоя, это фотографии. Раньше такой документ уходил в «доверие low, страницы
пустые» — не потому что пустой, а потому что его отправляли как текст.

    python3 tools/docs_parse.py                 # показать очередь
    python3 tools/docs_parse.py --apply         # разобрать
    python3 tools/docs_parse.py --apply --id 46 # один документ
    python3 tools/docs_parse.py --apply --limit 5
"""
import base64, json, os, sys, urllib.error, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
ОДИН = int(sys.argv[sys.argv.index('--id') + 1]) if '--id' in sys.argv else None
ПРЕДЕЛ = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 40
BUCKET = 'client-docs'
# 32 МБ — потолок вложения у модели; крупнее пропускаем с честной пометкой
ПОТОЛОК = 30 * 1024 * 1024

СИСТЕМА = (
 'Ты разбираешь документ по сделке с недвижимостью на Пхукете: договор, бронь, '
 'график платежей, счёт, отчёт о стройке или переписку.\n'
 'Верни СТРОГО JSON, без пояснений вокруг:\n'
 '{"project":"","unit":"","buyer":"","developer":"","price":null,"currency":"THB",'
 '"area_sqm":null,"bedrooms":null,"contract_date":"YYYY-MM-DD","handover_date":"YYYY-MM-DD",'
 '"stage":"","payments":[{"date":"YYYY-MM-DD","note":"","amount":0,"percent":null,"paid":false}],'
 '"summary":"","confidence":"high|medium|low"}\n\n'
 'Правила:\n'
 '• Берём ТОЛЬКО написанное в документе. Чего нет — null. Не досчитывай и не угадывай.\n'
 '• price — полная стоимость юнита по договору. Сумма одного платежа из счёта — это НЕ price.\n'
 '• В котировке (quotation) цена бывает до скидки: если видно и то и другое, бери итоговую.\n'
 '• payments — все этапы графика. paid=true только если в документе прямо отмечено, что оплачено.\n'
 '• Комиссию агентства в payments не переноси.\n'
 '• summary — одно-два предложения по-русски: что это за документ и о чём он.\n'
 '• confidence low ставь, если текст не читается или документ не про конкретный юнит.'
)


def env():
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
SBURL = E['SUPABASE_URL'].rstrip('/')
BASE = SBURL + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def ключ_модели():
    if E.get('ANTHROPIC_API_KEY'):
        return E['ANTHROPIC_API_KEY']
    for путь in ('~/.plp_anthropic_key', '~/.anthropic_key'):
        p = os.path.expanduser(путь)
        if os.path.exists(p):
            return open(p).read().strip()
    raise SystemExit('нет ключа ANTHROPIC_API_KEY')


def sb(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    try:
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError('база %s %s → %s %s' % (method, path, e.code, e.read().decode()[:300]))
    return json.loads(raw) if raw.strip() else []


def скачать(storage_key):
    url = '%s/storage/v1/object/%s/%s' % (SBURL, BUCKET, urllib.parse.quote(storage_key))
    r = urllib.request.Request(url, headers={'apikey': E['SUPABASE_SERVICE_KEY'],
                                             'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']})
    with urllib.request.urlopen(r, timeout=180) as f:
        return f.read()


def спросить(данные, mime, подсказка, ak):
    """PDF идёт как документ, картинка — как изображение. Иначе модель видит пустоту."""
    if mime == 'application/pdf':
        вложение = {'type': 'document',
                    'source': {'type': 'base64', 'media_type': 'application/pdf',
                               'data': base64.b64encode(данные).decode()}}
    else:
        тип = mime if mime in ('image/png', 'image/jpeg', 'image/gif', 'image/webp') else 'image/png'
        вложение = {'type': 'image',
                    'source': {'type': 'base64', 'media_type': тип,
                               'data': base64.b64encode(данные).decode()}}
    тело = {'model': 'claude-sonnet-5', 'max_tokens': 6000, 'system': СИСТЕМА,
            'messages': [{'role': 'user', 'content': [вложение, {'type': 'text', 'text': подсказка}]}]}
    r = urllib.request.Request('https://api.anthropic.com/v1/messages',
                               data=json.dumps(тело).encode(),
                               headers={'x-api-key': ak, 'anthropic-version': '2023-06-01',
                                        'content-type': 'application/json'})
    with urllib.request.urlopen(r, timeout=300) as f:
        ответ = json.load(f)
    # Ответ не всегда один текстовый блок: бывает размышление впереди, бывает
    # обрыв по лимиту. Раньше брали content[0]['text'] вслепую и падали на KeyError
    # 'text' — четыре документа из восемнадцати, в том числе сам договор по F-607.
    куски = [b.get('text', '') for b in ответ.get('content', []) if b.get('type') == 'text']
    t = '\n'.join(k for k in куски if k)
    if not t:
        raise RuntimeError('модель вернула без текста (stop_reason=%s)' % ответ.get('stop_reason'))
    if ответ.get('stop_reason') == 'max_tokens' and t.rfind('}') < t.find('{'):
        raise RuntimeError('ответ обрезан по лимиту — документ слишком длинный для одного прохода')
    return json.loads(t[t.find('{'):t.rfind('}') + 1])


def main():
    усл = '/client_docs?status=eq.new&select=id,kind,file_name,object_id,mime,size_bytes,storage_key'
    if ОДИН:
        усл = '/client_docs?id=eq.%d&select=id,kind,file_name,object_id,mime,size_bytes,storage_key' % ОДИН
    очередь = sb(усл + '&order=id')[:ПРЕДЕЛ]
    print('в очереди на разбор: %d\n' % len(очередь))
    for д in очередь:
        print('  %-4s %-14s %-46s %s' % (д['id'], д.get('object_id') or '—',
                                         str(д.get('file_name'))[:46],
                                         '%.1f МБ' % (( д.get('size_bytes') or 0) / 1048576)))
    if not APPLY:
        print('\nЭто отчёт. Разобрать: --apply')
        return 0

    ak = ключ_модели()
    ок = сбой = 0
    for д in очередь:
        подпись = '%s %s' % (д['id'], str(д.get('file_name'))[:40])
        if (д.get('size_bytes') or 0) > ПОТОЛОК:
            sb('/client_docs?id=eq.%d' % д['id'], 'PATCH',
               {'status': 'skipped', 'parse_error': 'файл больше 30 МБ — модель не примет'})
            print('  ⤬ %s: крупнее 30 МБ' % подпись)
            сбой += 1
            continue
        try:
            данные = скачать(д['storage_key'])
            подсказка = ('Юнит %s. Разбери документ.' % д['object_id']) if д.get('object_id') \
                else 'Разбери документ.'
            разбор = спросить(данные, д.get('mime') or 'application/pdf', подсказка, ak)
            sb('/client_docs?id=eq.%d' % д['id'], 'PATCH',
               {'status': 'parsed', 'parsed': разбор, 'parse_error': None,
                'parsed_at': 'now()'})
            ок += 1
            print('  ✓ %-46s %s | %s' % (подпись, разбор.get('confidence'),
                                         str(разбор.get('summary'))[:70]))
        except Exception as e:
            сбой += 1
            беда = str(e)[:220]
            try:
                sb('/client_docs?id=eq.%d' % д['id'], 'PATCH', {'parse_error': беда})
            except Exception:
                pass
            print('  ✗ %-46s %s' % (подпись, беда))
    print('\nразобрано: %d, не вышло: %d' % (ок, сбой))
    return 0


if __name__ == '__main__':
    sys.exit(main())
