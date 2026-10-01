#!/usr/bin/env python3
"""01.10.2026. Досылка после сбоя: тем, кто получил заглушку «вернусь с ответом», после восстановления мозга — ответ по сути.
Эльнур: «сторож обязан чинить, а не сообщать». Источник — public."досылка" (пишет WF_wa_wazzup на brain_down).
Каждые 10 минут (крон). Одна строка за раз, не старше 24 ч, до 3 попыток. Привратник перед отправкой обязателен.
Если человеку уже ответили после заглушки (вручную или двойник) — закрываем без отправки."""
import json, urllib.request, urllib.parse, datetime


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB, SK = env('SUPABASE_URL').rstrip('/') + '/rest/v1', env('SUPABASE_SERVICE_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}
T = urllib.parse.quote('досылка')


def http(m, url, body=None, headers=None, timeout=60):
    r = urllib.request.Request(url, method=m, headers=headers or H,
                               data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    raw = urllib.request.urlopen(r, timeout=timeout).read().decode() or 'null'
    return json.loads(raw)


def patch(i, d):
    http('PATCH', SB + '/' + T + '?id=eq.%d' % i, d, dict(H, Prefer='return=minimal'))


rows = http('GET', SB + '/' + T + '?done_at=is.null&attempts=lt.3&order=created_at.asc&limit=1'
            '&created_at=lt.' + urllib.parse.quote((datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=2)).isoformat() + 'Z')
            + '&created_at=gt.' + urllib.parse.quote((datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=24)).isoformat() + 'Z'))
if not rows:
    print('досылать некому'); raise SystemExit
r = rows[0]
since = urllib.parse.quote(r['created_at'])
БОТ = r['channel'] == 'tg_bot'   # 01.10.2026: клиентский бот @elnurphuket_bot — ответ через Bot API
later = http('GET', SB + '/chat_history?select=id&role=eq.assistant&%s&ts=gt.%s&limit=1'
             % (('tg_id=eq.' + str(r.get('chat_id') or '')) if БОТ else ('phone_norm=eq.' + r['phone']), since))
if later:
    patch(r['id'], {'done_at': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + 'Z', 'note': 'уже ответили после заглушки — не досылаем'})
    print('уже ответили:', r['id']); raise SystemExit
out = http('POST', 'https://api.property-library.com/brain',
           {'input': {'phone': r['phone'], 'chatId': (r.get('chat_id') or r['phone']), 'text': r['text'] or '', 'name': r.get('name') or '',
                      'source': ('telegram_direct' if БОТ else 'wazzup'), 'channel': ('telegram' if БОТ else r['channel']),
                      'channelId': r.get('channel_id'), 'persona': r.get('persona'), 'tg_id': (r.get('chat_id') if БОТ else None)}},
           {'x-plp-key': env('PLP_API_KEY'), 'Content-Type': 'application/json'}, timeout=150)
reply = str((out or {}).get('reply') or '').strip()
if (out or {}).get('brain_down') or not reply:
    patch(r['id'], {'attempts': (r.get('attempts') or 0) + 1, 'note': 'мозг ещё недоступен'})
    print('мозг ещё недоступен:', r['id']); raise SystemExit
gate = http('POST', 'http://127.0.0.1:5678/webhook/outbound-gate',
            {'phone': r['phone'], 'channel': ('telegram' if БОТ else r['channel']), 'agent': ('validator' if БОТ else 'auto'),
             'occasion': 'досылка после сбоя', 'message': reply, 'tg': (r.get('chat_id') if БОТ else None),
             'reason': 'dosylka'}, {'Content-Type': 'application/json', 'x-plp-key': env('PLP_WEBHOOK_KEY')})
if not (gate or {}).get('allow'):
    patch(r['id'], {'attempts': (r.get('attempts') or 0) + 1, 'note': 'привратник: ' + json.dumps((gate or {}).get('denies'), ensure_ascii=False)[:200]})
    print('привратник не пустил:', r['id']); raise SystemExit
if БОТ:
    http('POST', 'https://api.telegram.org/bot%s/sendMessage' % env('TG_ELNURPHUKET_TOKEN'),
         {'chat_id': r.get('chat_id'), 'text': reply}, {'Content-Type': 'application/json'})
else:
    http('POST', 'https://api.wazzup24.com/v3/message',
         {'channelId': r.get('channel_id'), 'chatType': ('telegram' if r['channel'] == 'telegram' else 'whatsapp'),
          'chatId': r.get('chat_id') or r['phone'], 'text': reply},
         {'Authorization': 'Bearer ' + env('WAZZUP_TOKEN'), 'Content-Type': 'application/json'})
http('POST', SB + '/chat_history', [{'phone': r['phone'], 'role': 'assistant', 'content': reply,
                                     'channel': ('telegram' if БОТ else r['channel']), 'source': ('telegram_direct' if БОТ else 'wazzup'),
                                     'tg_id': (r.get('chat_id') if БОТ else None), 'meta': {'persona': r.get('persona'), 'досылка': True}}],
     dict(H, Prefer='return=minimal'))
patch(r['id'], {'done_at': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + 'Z', 'note': 'досланo: ' + reply[:150]})
print('дослано:', r['id'], r['phone'][-4:])
