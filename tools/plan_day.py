#!/usr/bin/env python3
"""01.10.2026. План дня Эльнуру в 07:45 по Пхукету (после посева 07:30).
Эльнур: «в 07:30 не просто запуск, а планер… всё на ладони». Текст собирает база: public."план_дня"()."""
import json, urllib.request


def env(key, файл='/opt/plp-api/.env'):
    for line in open(файл, encoding='utf-8'):
        if line.startswith(key + '='):
            return line.split('=', 1)[1].strip().strip('"\'')
    return ''


SB, KEY = env('SUPABASE_URL').rstrip('/'), env('SUPABASE_SERVICE_KEY') or env('SUPABASE_KEY')
r = urllib.request.Request(SB + '/rest/v1/rpc/%D0%BF%D0%BB%D0%B0%D0%BD_%D0%B4%D0%BD%D1%8F', data=b'{}', method='POST',
                           headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
текст = json.load(urllib.request.urlopen(r, timeout=60))
tok, owner = env('TG_ELNURPHUKET_TOKEN'), int(env('TG_OWNER_CHAT_ID') or 509498386)
urllib.request.urlopen(urllib.request.Request('https://api.telegram.org/bot%s/sendMessage' % tok,
    data=json.dumps({'chat_id': owner, 'text': текст[:4000], 'disable_web_page_preview': True}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=30)
print('план дня отправлен,', len(текст), 'знаков')
