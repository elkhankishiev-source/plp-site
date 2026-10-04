#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ежедневная сверка: всё ли, что ушло лидам, по правилам, и что утверждено, но не внедрено.

04.10.2026 Эльнур: «важно всё сверить, утвердить, почему никто не среагировал на нарушения…
сделай всё детально под учёт и подсчёт с отметкой каждого выполненного», «отчёт берёшь на автомате».

Что делает раз в сутки (07:30 Пхукет, до сводки 08:05):
1) все наши сообщения лидам за 24 часа (касания и живые ответы) — одним-двумя вызовами Opus
   проверяет по главным правилам и считает нарушения по каждому правилу;
2) решения Эльнура со статусом не «работает» — список «утверждено, но не внедрено»;
3) кладёт итог в таблицу «сверка_дня»; сводка тревог показывает его одной-двумя строками.
Ничего никому не отправляет, только считает и записывает.

    python3 sverka_dnya.py          # посчитать и записать
    python3 sverka_dnya.py --покажи # посчитать, показать, не записывать
"""
import json, sys, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB = env('SUPABASE_URL').rstrip('/') + '/rest/v1'
SK = env('SUPABASE_SERVICE_KEY')
AK = env('ANTHROPIC_API_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}
# Свои номера команды — те же, что в сторожe plp_watch. Тестовые и демо-номера в публичный код не пишем:
# они лежат в настройках сервера (PLP_DEMO_NUMBERS), как у сторожа (03.10).
СВОИ = {'66954143874', '66955492587', '66640709032', '509498386', '8554364120', '8227351774', '66960169127'}
СВОИ |= {x.strip() for x in env('PLP_DEMO_NUMBERS').split(',') if x.strip()}
ПРАВИЛА = [
    'цена объекта, которую не спрашивали и не связанная с разговором (по запросу и вилкой — хорошо)',
    'бессвязная фраза или ложная «поправка» своего сообщения',
    'вопрос о бюджете или сумме в лоб',
    'спрашивает то, что клиент уже сказал',
    'по аренде спрашивает число людей, а не спален',
    'повторное приветствие в идущем разговоре',
    'служебная метка или текст для своих',
    'признаётся, что это бот или ИИ',
    'касание без нового повода, повтор прошлого текста',
    'ответ режет квалификацию: нет заботы, экспертизы или следующего шага',
]


def get(path):
    r = urllib.request.Request(SB + path, headers=H)
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or '[]')


def opus(system, user):
    body = {'model': 'claude-opus-5-5', 'max_tokens': 4000, 'output_config': {'effort': 'low'},
            'system': system, 'messages': [{'role': 'user', 'content': user}]}
    r = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                               headers={'x-api-key': AK, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    d = json.loads(urllib.request.urlopen(r, timeout=180).read().decode())
    return ''.join(c.get('text', '') for c in d.get('content', []) if c.get('type') == 'text')


def главное():
    с = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    исход = get('/chat_history?select=phone_norm,role,content,ts,source&ts=gte.' + с
                + '&role=eq.assistant&source=in.(touch_queue,wazzup,telegram)&order=ts.asc&limit=600')
    исход = [x for x in исход if str(x.get('phone_norm') or '') not in СВОИ and len(str(x.get('phone_norm') or '')) <= 15]
    итог = {п: 0 for п in ПРАВИЛА}
    примеры = []
    for i in range(0, len(исход), 40):
        пачка = исход[i:i + 40]
        текст = '\n'.join('%d) [%s] %s' % (k + 1, x['source'], str(x['content'])[:500].replace('\n', ' ')) for k, x in enumerate(пачка))
        ответ = opus('Ты проверяешь сообщения агентства недвижимости на Пхукете лидам. Правила (номера): '
                     + '; '.join('%d — %s' % (n + 1, p) for n, p in enumerate(ПРАВИЛА))
                     + '. Цены вилкой — это хорошо. Не придирайся к стилю. Ответь ТОЛЬКО JSON-списком нарушений: '
                       '[{"сообщение": номер, "правило": номер, "кусок": "до 12 слов"}], пусто — [].', текст)
        try:
            список = json.loads(ответ[ответ.find('['):ответ.rfind(']') + 1] or '[]')
        except Exception:
            список = []
        for н in список:
            try:
                п = ПРАВИЛА[int(н['правило']) - 1]; x = пачка[int(н['сообщение']) - 1]
            except Exception:
                continue
            итог[п] += 1
            if len(примеры) < 12:
                примеры.append({'номер': '…' + str(x['phone_norm'])[-4:], 'правило': п, 'кусок': str(н.get('кусок', ''))[:120]})
    висит = get('/' + urllib.parse.quote('решения_эльнура') + '?select=id,' + urllib.parse.quote('дата') + ','
                + urllib.parse.quote('что') + ',' + urllib.parse.quote('статус') + '&order=id.asc&limit=1000')
    висит = [r for r in висит if str(r.get('статус') or '').strip() not in ('работает', 'выполнено', 'отменено')]
    нарушений = sum(итог.values())
    запись = {'день': datetime.now(timezone.utc).date().isoformat(), 'сообщений': len(исход), 'нарушений': нарушений,
              'по_правилам': {k: v for k, v in итог.items() if v}, 'примеры': примеры,
              'не_внедрено': [{'id': r['id'], 'дата': r.get('дата'), 'что': str(r.get('что'))[:160], 'статус': r.get('статус')} for r in висит]}
    print('сообщений лидам за сутки: %d, нарушений: %d' % (len(исход), нарушений))
    for k, v in итог.items():
        if v: print('  %s: %d' % (k, v))
    print('утверждено, но не внедрено: %d' % len(висит))
    for r in висит[:15]:
        print('  №%s %s — %s [%s]' % (r['id'], r.get('дата'), str(r.get('что'))[:90], r.get('статус')))
    if '--покажи' in sys.argv:
        return 0
    r = urllib.request.Request(SB + '/' + urllib.parse.quote('сверка_дня') + '?on_conflict=' + urllib.parse.quote('день'), method='POST',
                               data=json.dumps(запись, ensure_ascii=False).encode(),
                               headers=dict(H, Prefer='resolution=merge-duplicates,return=minimal'))
    urllib.request.urlopen(r, timeout=60)
    print('записано в сверка_дня')
    return 0


if __name__ == '__main__':
    sys.exit(главное())
