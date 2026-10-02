#!/usr/bin/env python3
"""01.10.2026. Вызовы «на связи» ведущему в Telegram через бота @elnurphuket_bot.
Эльнур: «ты пиши лучше в тг такое». Источник — public."вызовы_тг" (пишет функция позвать()).
Крон раз в минуту. Не старше суток, до 3 попыток (счёт по полю ошибка)."""
import json, urllib.request, urllib.parse, datetime


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB, SK = env('SUPABASE_URL').rstrip('/') + '/rest/v1', env('SUPABASE_SERVICE_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}
T = urllib.parse.quote('вызовы_тг')
TOK = env('TG_BOT_TOKEN')  # 02.10: офисный бот @plp_assist_bot — с ним переписывались и Эльнур, и Дарья (8554364120); клиентский бот ей писать не может


def http(m, url, body=None, headers=None):
    r = urllib.request.Request(url, method=m, headers=headers or H,
                               data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    return json.loads(urllib.request.urlopen(r, timeout=40).read().decode() or 'null')


now = datetime.datetime.now(datetime.timezone.utc)
rows = http('GET', SB + '/' + T + '?sent_at=is.null&order=id.asc&limit=10&created_at=gt.'
            + urllib.parse.quote((now - datetime.timedelta(hours=24)).isoformat()))
for r in rows or []:
    tries = (r.get('ошибка') or '').count('|')
    if tries >= 3:
        continue
    try:
        http('POST', 'https://api.telegram.org/bot%s/sendMessage' % TOK,
             {'chat_id': r['chat_id'], 'text': r['text'][:4000], 'disable_web_page_preview': True},
             {'Content-Type': 'application/json'})
        http('PATCH', SB + '/' + T + '?id=eq.%d' % r['id'], {'sent_at': now.isoformat()}, dict(H, Prefer='return=minimal'))
        print('отправлен вызов', r['id'], r.get('persona'))
    except Exception as e:
        http('PATCH', SB + '/' + T + '?id=eq.%d' % r['id'], {'ошибка': (r.get('ошибка') or '') + '|' + str(e)[:80]},
             dict(H, Prefer='return=minimal'))
        print('сбой', r['id'], str(e)[:80])
