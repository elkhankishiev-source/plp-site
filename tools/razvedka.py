#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разведка по расписанию: находки ложатся в таблицу «разведка», проверяемые цифры — в «факты_рынка».

05.10.2026 Эльнур: «все результаты не исчезают без следа, по необходимости система берёт в работу»,
«чтобы у SMM был доступ», «застройщик — эталон, открытые источники — дополнение на апрув».

    python3 razvedka.py --yt      # новые ролики конкурентов на YouTube (открытые ленты, бесплатно), раз в сутки
    python3 razvedka.py --web     # новости застройщиков и рынка через поиск модели (около $1 за проход), раз в неделю
    python3 razvedka.py --yt --покажи   # собрать и показать, ничего не записывать

Ничего никому не отправляет. Факты из открытых источников ложатся со статусом «на_апрув»:
двойник их не видит, пока Эльнур не отметит.
"""
import hashlib, json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET


def env(k, f='/opt/plp-api/.env'):
    for l in open(f, encoding='utf-8'):
        if l.startswith(k + '='):
            return l.split('=', 1)[1].strip().strip('"\'')
    return ''


SB = env('SUPABASE_URL').rstrip('/') + '/rest/v1'
SK = env('SUPABASE_SERVICE_KEY')
H = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'}
ПОКАЖИ = '--покажи' in sys.argv

# Конкуренты на YouTube (05.10: найдены по нашим прошлым разборам). Добавлять сюда.
YT = {
    'Thailand Villa Center': 'UCMoL28XbmOtHnB-3pucoMUQ',
    'Andaman City Phuket': 'UCFpX5jRCs70WDpe36Gsk2mg',
    'Tumanov Group': 'UCqeV4QXM0-j12-dXeDB10GQ',
    'Royal Property Thailand': 'UCU2ZUkn_67i3uOywh4Sc_XA',
    'Mango Family Phuket': 'UCJy5vvB3cVSmvrK5gsdO8cg',
    # 05.10 Эльнур: «под контролем» — Малина, Mango, Валера Phuket 4 Life, Жанна GetYourPhuket
    'Малина (Дмитрий Тюменцев, @malina.thailand)': 'UCZ_ThWnR8Kx0l0hc6Oct4vg',  # 05.10: прежний UCpRv… был пустой однофамилец
    # 05.10: новые сильные игроки (разбор помощника): Лосев, VillaCarte, Hayat Estate, My Land Phuket
    'Losev.Thai (Алексей Лосев)': 'UC94iv6CO0wMu66sAaN8fh3g',
    'VillaCarte': 'UCt5bJSvlrU8q7IGuO1LHjkg',
    'Hayat Estate': 'UC8EKQx1pP2hbO0n0_RZF3YQ',
    'My Land Phuket (Ольга и Сергей)': 'UCfVWbTzM3mbiEdmLm2EzYjw',
}

# О ком ищем новости раз в неделю: наши застройщики и рынок острова.
ЗАСТРОЙЩИКИ = ['The Title (Rhom Bho) и AssetWise', 'ESM Group (Vibe, Карон)', 'The Zero (Най Янг, Банг Тао)',
              'Central Group / CG Capital (Лаян, The Standard)', 'Laguna Phuket / Banyan Group', 'Origin Property Phuket']
РЫНОК = ['турпоток Пхукета и аэропорт (AOT, новые рейсы)', 'предложение и цены кондо на Пхукете (Colliers, C9, CBRE, Knight Frank)',
         'законы для иностранных покупателей в Таиланде (лизхолд, визы, налоги)', 'новая инфраструктура Пхукета (больницы, моллы, дороги)']


def запиши(таблица, строки, конфликт=None):
    if ПОКАЖИ or not строки:
        for s in строки:
            print(json.dumps(s, ensure_ascii=False)[:300])
        return
    url = SB + '/' + urllib.parse.quote(таблица) + (('?on_conflict=' + urllib.parse.quote(конфликт)) if конфликт else '')
    r = urllib.request.Request(url, method='POST', data=json.dumps(строки, ensure_ascii=False).encode(),
                               headers=dict(H, Prefer='resolution=ignore-duplicates,return=minimal'))
    urllib.request.urlopen(r, timeout=60)


def _yt_токен():
    """05.10: открытые ленты YouTube с серверного адреса отдают 404 — берём официальный API по нашему входу Google."""
    t = json.load(open('/root/.plp_google_youtube.json'))
    o = json.load(open('/root/.plp_google_oauth.json'))
    r = urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
        'refresh_token': t['refresh_token'], 'client_id': o['client_id'], 'client_secret': o['client_secret'],
        'grant_type': 'refresh_token'}).encode())
    return json.loads(urllib.request.urlopen(r, timeout=30).read())['access_token']


def yt():
    гр = datetime.now(timezone.utc) - timedelta(days=14)
    ток = _yt_токен()
    def api(path):
        q = urllib.request.Request('https://www.googleapis.com/youtube/v3/' + path, headers={'Authorization': 'Bearer ' + ток})
        return json.loads(urllib.request.urlopen(q, timeout=30).read())
    строки = []
    for имя, cid in YT.items():
        try:
            items = api('playlistItems?part=snippet,contentDetails&maxResults=15&playlistId=UU' + cid[2:]).get('items', [])
        except Exception as e:
            print('канал не открылся:', имя, e)
            continue
        свежие = [x for x in items if datetime.fromisoformat(x['contentDetails']['videoPublishedAt'].replace('Z', '+00:00')) >= гр]
        стат = {}
        if свежие:
            for v in api('videos?part=statistics&id=' + ','.join(x['contentDetails']['videoId'] for x in свежие)).get('items', []):
                стат[v['id']] = v.get('statistics', {})
        for x in свежие:
            vid = x['contentDetails']['videoId']; st = стат.get(vid, {})
            строки.append({'сборщик': 'yt_competitors', 'канал': 'youtube', 'источник': имя, 'тема': 'конкурент',
                           'заголовок': x['snippet'].get('title', ''), 'текст': x['snippet'].get('description', '')[:1500],
                           'ссылка': 'https://www.youtube.com/watch?v=' + vid,
                           'метрики': {'просмотры': int(st.get('viewCount', 0) or 0), 'лайки': int(st.get('likeCount', 0) or 0),
                                       'комментарии': int(st.get('commentCount', 0) or 0)},
                           'опубликовано': x['contentDetails']['videoPublishedAt'], 'ключ': 'yt:' + vid, 'для_кого': 'smm'})
    запиши('разведка', строки, 'ключ')
    print('YouTube: роликов за 14 дней', len(строки))


def web():
    ak = env('ANTHROPIC_API_KEY')
    задание = ('Найди в интернете НОВОСТИ ЗА ПОСЛЕДНИЕ 10 ДНЕЙ (сегодня ' + datetime.now(timezone.utc).strftime('%d.%m.%Y') + ') по темам: '
               + '; '.join(ЗАСТРОЙЩИКИ + РЫНОК) + '. Нужны только проверяемые факты с цифрами или событиями: старт продаж, цены, '
               'проданность, награды, сдача, турпоток, рейсы, законы, стройка. Без рекламы агентств и без пересказа старого. '
               'Ответь ТОЛЬКО JSON-списком: [{"тема": "застройщик или рынок, коротко", "факт": "по-русски, 1-2 предложения с цифрой", '
               '"источник": "издание и URL", "дата": "ДД.ММ.ГГГГ", "вид": "застройщик|пресса|отчёт|брокер"}]. '
               'Вид «застройщик» — только если источник сам застройщик (его сайт, пресс-релиз). Если ничего нового — [].')
    body = {'model': 'claude-opus-5-5', 'max_tokens': 6000, 'output_config': {'effort': 'low'},
            'tools': [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 12}],
            'messages': [{'role': 'user', 'content': задание}]}
    r = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                               headers={'x-api-key': ak, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    d = json.loads(urllib.request.urlopen(r, timeout=600).read().decode())
    txt = ''.join(c.get('text', '') for c in d.get('content', []) if c.get('type') == 'text')
    try:
        факты = json.loads(txt[txt.find('['):txt.rfind(']') + 1] or '[]')
    except Exception:
        факты = []
    ф, р = [], []
    for x in факты:
        факт = str(x.get('факт') or '').strip()
        if len(факт) < 20:
            continue
        вид = x.get('вид') if x.get('вид') in ('застройщик', 'пресса', 'отчёт', 'брокер') else 'пресса'
        ключ = 'web:' + hashlib.md5(факт.lower().encode()).hexdigest()[:16]
        ф.append({'тема': str(x.get('тема') or 'рынок')[:80], 'факт': факт, 'источник': str(x.get('источник') or '')[:300],
                  'дата_источника': str(x.get('дата') or '')[:20], 'вид': вид,
                  # 04.10 Эльнур: «то, что у застройщика, — эталон; открытые источники — дополнение на апрув»
                  'статус': 'эталон' if вид == 'застройщик' else 'на_апрув', 'кто_добавил': 'web_scout',
                  'заметка': 'разведчик, проход ' + datetime.now(timezone.utc).strftime('%d.%m.%Y')})
        р.append({'сборщик': 'web_scout', 'канал': 'web', 'источник': str(x.get('источник') or '')[:300],
                  'тема': 'застройщик' if вид == 'застройщик' else 'рынок', 'заголовок': str(x.get('тема') or '')[:200],
                  'текст': факт, 'ключ': ключ, 'для_кого': 'smm'})
    # повторы фактов из прошлых проходов не кладём
    if ф and not ПОКАЖИ:
        уже = {r['факт'].lower() for r in json.loads(urllib.request.urlopen(urllib.request.Request(
            SB + '/' + urllib.parse.quote('факты_рынка') + '?select=' + urllib.parse.quote('факт') + '&limit=2000', headers=H), timeout=60).read() or b'[]')}
        ф = [x for x in ф if x['факт'].lower() not in уже]
    запиши('факты_рынка', ф)
    запиши('разведка', р, 'ключ')
    use = d.get('usage', {})
    print('веб-разведка: фактов', len(ф), '| поисков', (use.get('server_tool_use') or {}).get('web_search_requests'),
          '| токенов', use.get('input_tokens'), '+', use.get('output_tokens'))


if __name__ == '__main__':
    if '--yt' in sys.argv:
        yt()
    if '--web' in sys.argv:
        web()
