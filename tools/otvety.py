#!/usr/bin/env python3
"""02.10.2026. Ответ ведущего → клиенту. Эльнур: «система пишет в личку ответственному, спрашивает,
получает ответ и принимает к выполнению». Источник — public."вопросы_ведущему" (status='ответ').
Крон раз в 2 минуты. Мозг пишет клиенту ответ по существу, опираясь на слова ведущего; привратник обязателен.
Если клиенту уже ответили после вопроса — всё равно передаём (ответ ведущего новый), но только один раз."""
import json, urllib.request, urllib.parse, datetime


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB, SK = env('SUPABASE_URL').rstrip('/') + '/rest/v1', env('SUPABASE_SERVICE_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}
T = urllib.parse.quote('вопросы_ведущему')
WA = {'Эльнур': '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793', 'Дарья': '35d237fd-a3be-4496-886a-418dfa09c529'}


def http(m, url, body=None, headers=None, timeout=60):
    r = urllib.request.Request(url, method=m, headers=headers or H,
                               data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode() or 'null')


def patch(i, d):
    http('PATCH', SB + '/' + T + '?id=eq.%d' % i, d, dict(H, Prefer='return=minimal'))


now = datetime.datetime.now(datetime.timezone.utc).isoformat()
rows = http('GET', SB + '/' + T + '?status=eq.' + urllib.parse.quote('ответ') + '&done_at=is.null&order=id.asc&limit=3')
if not rows:
    print('передавать нечего'); raise SystemExit
for r in rows:
    try:
        tg = r.get('channel') in ('telegram', 'tg_bot')
        text = (r.get('client_text') or '').strip() + (
            '\n\n(Для тебя, клиенту не цитируй: на твой вопрос ведущему «%s» ведущий ответил: «%s». '
            'Напиши клиенту ответ по существу, опираясь на это, одним сообщением, без слов «спросил у коллеги».)'
            % ((r.get('question') or '')[:400], (r.get('answer') or '')[:1500]))
        out = http('POST', 'https://api.property-library.com/brain',
                   {'input': {'phone': r['phone'], 'chatId': r.get('chat_id') or r['phone'], 'text': text,
                              'name': r.get('client_name') or '', 'source': ('telegram_direct' if r.get('channel') == 'tg_bot' else 'wazzup'),
                              'channel': r.get('channel') or 'whatsapp', 'channelId': r.get('channel_id'), 'persona': r.get('persona')}},
                   {'x-plp-key': env('PLP_API_KEY'), 'Content-Type': 'application/json'}, timeout=150)
        reply = str((out or {}).get('reply') or '').strip()
        if (out or {}).get('brain_down') or not reply:
            patch(r['id'], {'note': 'мозг не ответил, попробую ещё'}); continue
        gate = http('POST', 'http://127.0.0.1:5678/webhook/outbound-gate',
                    {'phone': r['phone'], 'channel': (r.get('channel') or 'whatsapp'), 'agent': 'auto',
                     'occasion': 'ответ ведущего на вопрос клиента', 'message': reply, 'reason': 'otvety'},
                    {'Content-Type': 'application/json', 'x-plp-key': env('PLP_WEBHOOK_KEY')})
        if not (gate or {}).get('allow'):
            patch(r['id'], {'note': 'привратник: ' + json.dumps((gate or {}).get('denies'), ensure_ascii=False)[:200]}); continue
        if r.get('channel') == 'tg_bot':
            http('POST', 'https://api.telegram.org/bot%s/sendMessage' % env('TG_ELNURPHUKET_TOKEN'),
                 {'chat_id': r.get('chat_id'), 'text': reply}, {'Content-Type': 'application/json'})
        else:
            http('POST', 'https://api.wazzup24.com/v3/message',
                 {'channelId': r.get('channel_id') or WA.get(r.get('persona') or 'Эльнур'),
                  'chatType': ('telegram' if tg else 'whatsapp'), 'chatId': r.get('chat_id') or r['phone'], 'text': reply},
                 {'Authorization': 'Bearer ' + env('WAZZUP_TOKEN'), 'Content-Type': 'application/json'})
        http('POST', SB + '/chat_history', [{'phone': r['phone'], 'role': 'assistant', 'content': reply,
                                             'channel': ('telegram' if tg else 'whatsapp'), 'source': 'wazzup',
                                             'meta': {'persona': r.get('persona'), 'ответ_ведущего': r['id']}}],
             dict(H, Prefer='return=minimal'))
        patch(r['id'], {'status': 'закрыт', 'done_at': now, 'note': 'передано клиенту: ' + reply[:150]})
        print('передано клиенту по вопросу', r['id'])
    except Exception as e:
        patch(r['id'], {'note': 'сбой передачи: ' + str(e)[:150]})
        print('сбой', r['id'], str(e)[:100])
