#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Наблюдатель: смотрит за лидами, очередями и здоровьем, пишет только когда есть о чём.

Эльнур 18.09.2026: «следи пристально, как идут лиды, и вся работа в CRM, прям глубокое
наблюдение и сразу подхват, и следи за чатами, чтобы не было всякого недоразумения».

Правило разводки то же, что и у остальных уведомлений:
  • «PLP · Тех офис» — только поломки: застрявшие очереди, отказы привратника,
    молчание зеркала переписки, сборщик почты не отработал;
  • «PLP | отдел продаж» — только работа: человек написал и остался без ответа.

Молчит, когда всё в порядке. Один и тот же повод повторно не шлёт: отпечаток лежит
в /tmp/plp_watch_seen.json и живёт шесть часов.

    python3 plp_watch.py           # показать, ничего не отправляя
    python3 plp_watch.py --send    # отправить найденное в нужные чаты
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

SEND = '--send' in sys.argv
SEEN = '/tmp/plp_watch_seen.json'
TTL = 6 * 3600
# 23.09.2026: про одного и того же человека «ждёт ответа» напоминаем РАЗ В СУТКИ,
# а не каждые 20 минут. Ключ дедупа уже без чисел, но шестичасовой срок давал
# четыре повтора в день про одно и то же. Эльнур: «глупое уведомление каждые
# 20 минут». Остальные поводы живут прежние шесть часов.
TTL_ОЖИДАНИЕ = 24 * 3600
ENV = next((p for p in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env')
            if os.path.exists(p)), None)


def env():
    out = {}
    for ln in open(ENV, encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def get(path):
    # 05.10.2026: русские имена полей (слит_в, важность, состояние) не кодировались — запрос падал,
    # ошибка глоталась, проверки двойников и P1 молча ничего не видели. Кодируем только не-ASCII.
    path = urllib.parse.quote(path, safe="/?&=.,()*:!'~%+-_[]<>|;$@")
    r = urllib.request.Request(BASE + path, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=40) as f:
            return json.loads(f.read().decode() or '[]')
    except Exception:
        return []


def post(path, body):
    r = urllib.request.Request(BASE + urllib.parse.quote(path, safe="/?&=.,()*:!'~%+-_"), data=json.dumps(body).encode(),
                               headers=dict(H, **{'Content-Type': 'application/json', 'Prefer': 'return=minimal'}),
                               method='POST')
    try:
        urllib.request.urlopen(r, timeout=30)
        return True
    except Exception:
        return False


def patch(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers=dict(H, **{'Content-Type': 'application/json'}),
                               method='PATCH')
    try:
        urllib.request.urlopen(r, timeout=30)
        return True
    except Exception:
        return False


# 23.09.2026. Разбор уведомлений: из 191 «продажной» строки сторожа за пять дней
# 184 оказались про тестовые записи — «ТЕСТ Клод сквозной» 107 раз, «Эльнур
# (личный номер)» 38, «Андрей Тестовый (DEMO)» 29. Настоящих поводов семь.
# Такую ленту перестают читать, и вместе с шумом теряются живые строки.
ТЕСТОВАЯ_ЗАПИСЬ = re.compile(r'тест|test|demo|демо|проверк|заглушк', re.I)
СВОИ_НОМЕРА = ('66954143874', '66955492587', '509498386', '66960169127',
               '66640709032', '8554364120', '8227351774')


# Идентификатор группы WhatsApp — это не человек. Такие приходят длинной строкой
# цифр (120363…), и внутри них рассылки застройщиков: «два новых проекта», «special
# offer». Сторож считал их людьми и писал «ждёт ответа 1337 минут». Отвечать на
# рассылку в группе никто не должен — это не вопрос нам.
ГРУППОВОЙ_ID = re.compile(r'\b1203\d{11,}\b')
# Отрицательное число в начале — id чата Telegram, тоже не человек.
ЧАТ_ID = re.compile(r'(?<![\d])-\d{9,}')


# 23.09.2026, Эльнур: «это ненужное уведомление, я буду писать сразу там, где
# приходит уведомление». Речь про канал userbot_elnur — это ЛИЧНЫЙ телеграм
# Эльнура через мост. Туда пишут ему лично: реклама курсов, знакомые, холодные
# предложения. Отвечать за него система не должна и напоминать об этом тоже.
# Рабочие каналы (wazzup, telegram клиентов, сайт) остаются под присмотром.
ЛИЧНЫЕ_КАНАЛЫ = ('userbot_elnur', 'tg_userbot', 'userbot')


def шум(строка):
    """Не человек или не повод: тест, свой номер, групповая рассылка, id чата."""
    т = str(строка)
    if ТЕСТОВАЯ_ЗАПИСЬ.search(т) or ГРУППОВОЙ_ID.search(т) or ЧАТ_ID.search(т):
        return True
    if any(('(' + к + ')') in т for к in ЛИЧНЫЕ_КАНАЛЫ):
        return True
    цифры = re.sub(r'\D', '', т)
    return any(н in цифры for н in СВОИ_НОМЕРА)


def tg(chat_key, text):
    tok, chat = E.get('TG_BOT_TOKEN', ''), E.get(chat_key, '')
    if not (tok and chat):
        return False
    try:
        req = urllib.request.Request('https://api.telegram.org/bot' + tok + '/sendMessage',
                                     data=json.dumps({'chat_id': chat, 'text': text,
                                                      'disable_web_page_preview': True}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception:
        return False


def без_чисел(s):
    """Ключ дедупа не должен зависеть от счётчика в тексте.

    «ждёт ответа 459 мин» и «479 мин» — это одно и то же событие, а для дедупа были
    разными, потому что число входило в ключ. Из-за этого одно напоминание уходило
    в группу каждые двадцать минут без конца."""
    return ''.join('#' if c.isdigit() else c for c in s)


def seen(key, mark=True):
    """04.10.2026 Эльнур: «уведомления должен кто-то читать, не должно ничего проходить само собой».
    Раньше отметка «уже сообщил» ставилась ДО отправки: Telegram не ответил — сообщение пропадало,
    а сторож молчал до конца срока. Теперь вызывающий сначала спрашивает (mark=False), шлёт,
    и только после ok от Telegram ставит отметку (seen(key))."""
    try:
        d = json.load(open(SEEN))
    except Exception:
        d = {}
    now = time.time()
    срок = TTL_ОЖИДАНИЕ if ':🕑' in key or key.startswith(('sales:🕑', 'tech:🕑')) else TTL
    d = {k: v for k, v in d.items() if now - v < max(TTL, TTL_ОЖИДАНИЕ)}
    was = (key in d) and (now - d[key] < срок)
    if mark:
        d[key] = now
    try:
        json.dump(d, open(SEEN, 'w'))
    except Exception:
        pass
    return was


def iso(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# свои номера и наши же групповые чаты: это не клиенты, о них не напоминаем
OWN = {'66954143874', '509498386', '8554364120', '66955492587', '66960169127',
       '66640709032', '8227351774',
       # демо и тестовые номера: это не люди. 03.10.2026: сами номера — в PLP_DEMO_NUMBERS на сервере
       # (маски «669••••••» в публичном коде ничего не ловили: «настроено, но мертво»)
       '900000777',
       '5571405041',      # группа «PLP · Тех офис»
       '4664612682',      # группа «PLP | отдел продаж»
       '7909976765', '8617913608'}   # 03.10: id самих ботов (клиентский, офисный) — не люди
OWN |= {x.strip() for x in E.get('PLP_DEMO_NUMBERS', '').split(',') if x.strip()}   # 03.10: демо-номера из настроек сервера


def feed():
    """Лента для Эльнура: кто написал и что мы ответили. Эльнур 18.09: «пиши мне,
    держи в курсе по лидам и CRM, что пишут, какая реакция». Свои номера не показываем:
    его собственная переписка с двойником ему и так видна."""
    since = iso(150)
    rows = get('/chat_history?ts=gte.' + urllib.parse.quote(since)
               + '&select=ts,phone_norm,role,content,source&order=ts.asc&limit=300')
    by = {}
    for r in rows:
        if not r.get('phone_norm') or r['phone_norm'] in OWN:
            continue
        by.setdefault(r['phone_norm'], []).append(r)
    lines = []
    for ph, rr in by.items():
        last_user = [x for x in rr if x['role'] == 'user']
        if not last_user:
            continue
        lu = last_user[-1]
        after = [x for x in rr if x['role'] == 'assistant' and x['ts'] > lu['ts']]
        name = get('/client_profiles?select=name&or=(phone_norm.eq.%s,tg_id.eq.%s)&limit=1' % (ph, ph))
        who = (name[0]['name'] if name and name[0].get('name') else ph)
        said = (lu.get('content') or '').replace('\n', ' ')[:110]
        if after:
            react = 'ответили: ' + (after[-1].get('content') or '').replace('\n', ' ')[:110]
        else:
            mins = (datetime.now(timezone.utc) - datetime.fromisoformat(lu['ts'][:19] + '+00:00')).total_seconds() / 60
            react = 'БЕЗ ОТВЕТА уже %d мин' % mins
        lines.append('👤 %s (%s)\n   сказал: «%s»\n   %s' % (who[:34], ph, said, react))
    if not lines:
        print('за два часа новых реплик от людей не было')
        return 0
    text = '💬 Что пишут и как реагируем\n\n' + '\n\n'.join(lines[:8])
    print(text)
    if SEND:
        tg('TG_ALERT_CHAT_ID', text)   # 02.10.2026 Эльнур: «отдел продаж — работа над лидами с командой»; в личке это дублировало вызовы «лид ответил»
    return 0


def tg_owner(text):
    tok = E.get('TG_BOT_TOKEN', '')
    if not tok:
        return
    try:
        req = urllib.request.Request('https://api.telegram.org/bot' + tok + '/sendMessage',
                                     data=json.dumps({'chat_id': '509498386', 'text': text,
                                                      'disable_web_page_preview': True}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception:
        return False


def digest():
    """Утренняя сводка по лидам и CRM: одна короткая карточка вместо копания в чатах.
    Эльнур 18.09: «контролируй лиды и CRM, прям держи каждого на пушке, чтобы мне
    сразу сказать или починить»."""
    day = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    q = urllib.parse.quote
    new_msgs = get('/chat_history?ts=gte.' + q(day) + '&role=eq.user&select=phone_norm,source&limit=500')
    people = sorted({m['phone_norm'] for m in new_msgs if m.get('phone_norm')})
    sent = get('/touch_queue?sent_at=gte.' + q(day) + '&select=id&limit=200')
    planned = get('/touch_queue?status=in.(planned,approved)&select=id&limit=200')
    deals = get('/crm_leads?updated_at_crm=gte.' + q(day) + '&select=id&limit=500')
    docs = get('/mail_intake?created_at=gte.' + q(day) + '&select=id,guess_kind&limit=100')
    biz = [d for d in docs if d.get('guess_kind') in ('договор', 'счёт', 'график платежей', 'стройка')]
    lines = ['📊 Сводка за сутки',
             'Написали нам: %d человек, %d сообщений' % (len(people), len(new_msgs)),
             'Касаний ушло: %d, в очереди: %d' % (len(sent), len(planned)),
             'Сделок тронуто в CRM: %d' % len(deals),
             'Писем с документами: %d (из них деловых %d)' % (len(docs), len(biz))]
    text = '\n'.join(lines)
    print(text)
    if SEND:
        tg('TG_ALERT_CHAT_ID', text)
    return 0


# ——— номера телефонов: битый номер не должен стать карточкой ———
# 03.09.2026 перенос из amoCRM создал 473 карточки с ОТКУШЕННОЙ первой цифрой:
# у номеров с трёхзначным кодом страны пропадала первая цифра (375 → 75,
# 972 → 72, 420 → 20). Выглядит как исправный номер, а написать по нему нельзя —
# такого абонента нет. Заметили это только через две недели и случайно.
# Кода того переноса не сохранилось, поэтому ловим следствие: любой новый номер,
# который не начинается ни с одного существующего кода страны.
КОДЫ_СТРАН = (
    '1','7','20','27','30','31','32','33','34','36','39','40','41','43','44','45','46','47','48','49',
    '51','52','53','54','55','56','57','58','60','61','62','63','64','65','66','81','82','84','86','90',
    '91','92','93','94','95','98',
    '211','212','213','216','218','220','221','222','223','224','225','226','227','228','229','230','231',
    '232','233','234','235','236','237','238','239','240','241','242','243','244','245','248','249','250',
    '251','252','253','254','255','256','257','258','260','261','262','263','264','265','266','267','268',
    '269','290','291','297','298','299','350','351','352','353','354','355','356','357','358','359','370',
    '371','372','373','374','375','376','377','378','379','380','381','382','383','385','386','387','389',
    '420','421','423','500','501','502','503','504','505','506','507','508','509','590','591','592','593',
    '595','597','598','599','670','672','673','674','675','676','677','678','679','680','681','682','683',
    '685','686','687','688','689','690','691','692','850','852','853','855','856','870','880','886','960',
    '961','962','963','964','965','966','967','968','970','971','972','973','974','975','976','977','992',
    '993','994','995','996','998',
)


def номер_битый(тел, все_номера=None):
    """Правда ли, что по этому номеру нельзя позвонить.

    Проверка по коду страны здесь НЕ работает, и это стоило мне одного захода:
    у откушенного номера остаток всё равно начинается с настоящего кода —
    3752••••••58 без тройки даёт 752••••••58, то есть «код 7, Россия».
    Формально безупречно, а абонента нет.

    Доказательный признак один: в базе есть ДРУГОЙ номер, который равен
    «какая-то цифра + этот». Совпадение одиннадцати цифр подряд случайным не
    бывает — значит перед нами одна и та же запись, у которой отвалилась первая
    цифра. Именно так 03.09.2026 перенос из amoCRM испортил 473 карточки.

    Вторая проверка, слабее: длина номера для стран, где она фиксирована.
    """
    ц = re.sub(r'\D', '', str(тел or ''))
    if not (10 <= len(ц) <= 15):
        return None                      # не телефон (например Telegram id) — не наше дело

    if все_номера:
        for c in '123456789':
            if (c + ц) in все_номера:
                return ('в базе есть %s — это тот же номер с целой первой цифрой'
                        % (c + ц))

    ДЛИНА = {'7': 11, '375': 12, '380': 12, '972': 12, '66': 11, '420': 12,
             '994': 12, '995': 12, '996': 12, '998': 12, '90': 12, '49': (12, 13)}
    for код, нужно in sorted(ДЛИНА.items(), key=lambda x: -len(x[0])):
        if ц.startswith(код):
            ок = (len(ц) == нужно) if isinstance(нужно, int) else (len(ц) in нужно)
            if not ок:
                return 'для кода +%s ожидается %s цифр, а здесь %d' % (код, нужно, len(ц))
            break
    return None


def main():
    if '--digest' in sys.argv:
        return digest()
    if '--feed' in sys.argv:
        return feed()
    tech, sales = [], []

    # 0. новые карточки с непригодным номером — ловим в день появления, а не через две недели
    свежие = get('/clients?created_at=gte.' + urllib.parse.quote(iso(180))
                 + '&select=code,name,phone&limit=300')
    все_номера = set()
    if свежие:
        for стр in range(0, 6000, 1000):
            куски = get('/clients?select=phone&limit=1000&offset=%d' % стр)
            все_номера |= {re.sub(r'\D', '', str(x.get('phone') or '')) for x in куски if x.get('phone')}
            if len(куски) < 1000:
                break
    битые = [(c, номер_битый(c.get('phone'), все_номера)) for c in свежие if c.get('phone')]
    битые = [(c, п) for c, п in битые if п]
    if битые:
        примеры = ', '.join('%s (%s)' % (c.get('phone'), c.get('code')) for c, _ in битые[:5])
        tech.append('☎️ Непригодные номера в новых карточках (%d): %s. %s'
                    % (len(битые), примеры, битые[0][1]))

    # 0а. 05.10.2026: P1 из таблицы тревог доходили только утренней сводкой 08:05 — вечерний автостоп мозга никто не увидел.
    # Открытая P1 — сразу в «Тех офис» (повтор той же строки отсеивает seen()).
    for а in get('/alerts?важность=eq.P1&состояние=eq.открыт&select=id,кто,ключ,текст&limit=20') or []:
        tech.append('🚨 P1 %s: %s' % (а.get('ключ'), str(а.get('текст') or '')[:220]))

    # 0б. 05.10.2026: двойник карточки. Валерии в 22:55 завелись две лишние карточки — номер стоял в поле Telegram id,
    # а id пришёл с приставкой «tg». Ловим в тот же час: tg_id из 11+ цифр (это номер) или телефон, который уже есть у другой карточки.
    новые = get('/clients?created_at=gte.' + urllib.parse.quote(iso(180)) + '&слит_в=is.null&select=code,phone,tg_id&limit=200')
    дв = []
    for c in новые or []:
        if c.get('tg_id') and len(str(c['tg_id'])) >= 11:
            дв.append('%s (номер в поле Telegram id)' % c.get('code'))
        elif c.get('phone'):
            те = get('/clients?phone=eq.%s&code=neq.%s&слит_в=is.null&select=code&limit=1'
                     % (urllib.parse.quote(str(c['phone'])), urllib.parse.quote(str(c.get('code')))))
            if те:
                дв.append('%s = %s (один телефон)' % (c.get('code'), те[0].get('code')))
    if дв:
        tech.append('👥 Похоже на двойника карточки (%d): %s. Склейка — client_link, только после проверки.' % (len(дв), ', '.join(дв[:6])))

    # 0в. 06.10.2026: учёт обещаний. Симоне 01.10 двойник пообещал «подборку с фото и видео» — за 5 дней ничего:
    # обещание нигде не становилось задачей. Каждое «пришлю / соберу / подготовлю / отправлю» клиенту — дело в пульте.
    _обещ = re.compile(r'(пришлю|вышлю|отправлю|скину|соберу|подготовлю|подберу и пришлю|сделаю расч|посчитаю и пришлю|пришлём|соберём|подготовим|отправим)', re.I)
    for м in get('/chat_history?role=eq.assistant&ts=gte.' + urllib.parse.quote(iso(60))
                 + '&source=in.(wazzup,telegram_direct,touch_queue)&select=id,phone_norm,ts,content&limit=200') or []:
        тел = str(м.get('phone_norm') or '')
        if not тел or тел in OWN or тел.startswith('9009990'):
            continue
        т = str(м.get('content') or '')
        if not _обещ.search(т):
            continue
        метка = '#ch%s' % м.get('id')
        if get('/ops_orders?text=like.*' + метка + '*&select=id&limit=1'):
            continue
        кусок = re.sub(r'\s+', ' ', т)[:160]
        текст = 'Обещание клиенту …%s: «%s» — исполнить или снять с объяснением %s' % (тел[-4:], кусок, метка)
        if post('/ops_orders', {'text': текст, 'status': 'новое'}):
            sales.append('🤝 Двойник пообещал …%s: «%s» — дело в пульте' % (тел[-4:], кусок[:100]))

    # 0е. 06.10.2026: OpenClaw с ~02.10 не отвечал Эльнуру — его WhatsApp «personal» отключился (terminal disconnect),
    # а сторожа на это не было четыре дня. Есть такие строки за последний час — тревога: нужен QR с телефона Эльнура.
    try:
        _лог = '/tmp/openclaw/openclaw-%s.log' % datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if os.path.exists(_лог):
            _хв = open(_лог, encoding='utf-8', errors='ignore').read()[-200000:]
            _i = _хв.rfind('terminal disconnect')
            _стр = _хв[_хв.rfind('\n', 0, _i) + 1:(_хв.find('\n', _i) if _хв.find('\n', _i) > 0 else len(_хв))] if _i >= 0 else ''
            _м = re.search(r'"time":"([0-9T:\-]{19})', _стр)
            _св = _м and (datetime.now(timezone.utc) - datetime.strptime(_м.group(1), '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)) < timedelta(minutes=90)
            if _св:
                tech.append('📵 OpenClaw: WhatsApp «personal» отключён (terminal disconnect) — Эльнуру нужно заново привязать по QR, бот ему не отвечает')
    except Exception:
        pass

    # 0д. 06.10.2026: очередь «Клоду». Двойник 06.10 пять раз сказал Эльнуру «ставлю Клоду задачу», а такой очереди не было —
    # поручения пропадали (Sansiri, Nakara, Naturale, Mouana, Arise). Теперь каждое такое обещание — дело в пульте с текстом поручения.
    for м in get('/chat_history?role=eq.assistant&ts=gte.' + urllib.parse.quote(iso(60))
                 + '&phone_norm=in.(509498386,66954143874,8554364120,66960169127,8227351774)&select=id,phone_norm,ts,content&limit=100') or []:
        т = str(м.get('content') or '')
        if not re.search(r'((ставлю|передам|передаю|оставляю|записал|заведу)[^.!?]{0,40}(клод|claude)|(клод|claude)[^.!?]{0,15}задач)', т, re.I):
            continue
        метка = '#ch%s' % м.get('id')
        if get('/ops_orders?text=like.*' + метка + '*&select=id&limit=1'):
            continue
        пред = get('/chat_history?phone_norm=eq.%s&role=eq.user&ts=lte.%s&order=ts.desc&limit=1&select=content' % (м['phone_norm'], urllib.parse.quote(str(м['ts'])))) or []
        поручение = re.sub(r'\s+', ' ', str((пред[0] if пред else {}).get('content') or ''))[:200]
        if post('/ops_orders', {'text': 'Клоду от Эльнура %s: %s | двойник: %s' % (метка, поручение, re.sub(r'\s+', ' ', т)[:300]), 'status': 'новое'}):
            tech.append('📥 Поручение Клоду из чата: «%s» — в «Дела»' % поручение[:100])

    # 0г. 06.10.2026: петля тестировщика. Валерия (SMM) пишет боту «ошибка: …» — заносим в кандидаты эталонного набора
    # вместе с ответом бота, на который она указала, и ставим дело. Набор растёт от каждой найденной ошибки.
    for з in get('/chat_history?role=eq.user&ts=gte.' + urllib.parse.quote(iso(60))
                 + '&phone_norm=in.(412711606,375333942426)&select=id,phone_norm,ts,content&limit=50') or []:
        т = str(з.get('content') or '')
        if not re.match(r'^\s*(ошибк|error|неверно|не так)', т, re.I):
            continue
        ключ = 'ch%s' % з.get('id')
        if get('/эталон_кандидаты?ключ=eq.' + ключ + '&select=id&limit=1'):
            continue
        пред = get('/chat_history?phone_norm=eq.%s&ts=lt.%s&order=ts.desc&limit=4&select=role,content' % (з['phone_norm'], urllib.parse.quote(str(з['ts'])))) or []
        бот = next((str(x.get('content') or '') for x in пред if x.get('role') == 'assistant'), '')
        вопрос = next((str(x.get('content') or '') for x in пред if x.get('role') == 'user'), '')
        if post('/эталон_кандидаты', {'кто': 'Валерия', 'замечание': т[:1000], 'ответ_бота': бот[:1500], 'вопрос': вопрос[:600], 'ключ': ключ}):
            post('/ops_orders', {'text': 'Случай для эталонного набора от Валерии: «%s» — разобрать и добавить в evals/набор.json' % т[:150], 'status': 'новое'})
            tech.append('🧪 Валерия отметила ошибку бота: «%s» — в кандидаты набора' % т[:120])

    # 1. касание одобрено, но не ушло больше часа — отправщик или привратник встал.
    # 23.09: сторож смотрел на created_at — когда строку ЗАВЕЛИ, а не когда ей пора.
    # Касание, заведённое 21-го и назначенное на 25-е, он объявлял застрявшим и
    # держал ложную тревогу сутками. Срок наступил — тогда и спрашиваем.
    stuck = get('/touch_queue?status=eq.approved&created_at=lt.' + urllib.parse.quote(iso(70))
                + '&scheduled_at=lt.' + urllib.parse.quote(iso(70))
                + '&select=id,phone,created_at,scheduled_at,note&limit=20')
    if stuck:
        tech.append('⏳ Касания одобрены, но не ушли (%d): %s'
                    % (len(stuck), ', '.join(str(s['id']) for s in stuck[:10])))

    # 1б. 05.10.2026 Эльнур: «последнее сообщение лидам в 14:50, почему никто не следит?» С 13:17 до 21:00 касания
    # застревали в черновиках (проверка смысла не видела офферов) и в плане (ложный потолок), а пункт 1 смотрит
    # только approved — 6 часов тишины прошли без тревоги. Теперь: в рабочее окно 08:00–20:30 по Пхукету
    # есть просроченные больше 2 ч касания и за 2 ч ни одно не ушло — тревога с главными причинами.
    _час = datetime.now(timezone.utc) + timedelta(hours=7)
    if 8 * 60 + 120 <= _час.hour * 60 + _час.minute <= 20 * 60 + 30:
        висят = get('/touch_queue?status=in.(planned,draft)&kind=in.(cold,silence)&scheduled_at=lt.'
                    + urllib.parse.quote(iso(120)) + '&select=id,status,note&limit=300')
        ушло = get('/touch_queue?status=eq.sent&sent_at=gte.' + urllib.parse.quote(iso(120)) + '&select=id&limit=1')
        if висят and not ушло:
            причины = {}
            for x in висят:
                к = re.sub(r'[0-9.,:]+', '#', str(x.get('note') or 'без заметки'))[:60]
                причины[к] = причины.get(к, 0) + 1
            tech.append('🛑 Касания стоят: за 2 ч не ушло ни одного, просрочено %d (черновиков %d). Причины: %s'
                        % (len(висят), sum(1 for x in висят if x.get('status') == 'draft'),
                           '; '.join('%s ×%d' % (k, v) for k, v in sorted(причины.items(), key=lambda x: -x[1])[:4])))

    # 2. привратник отказал за последний час — причины важнее самого факта
    den = get('/funnel_events?event_type=eq.gate_decision&ts=gte.' + urllib.parse.quote(iso(60))
              + '&select=metadata&limit=200')
    bad = [d for d in den if (d.get('metadata') or {}).get('decision') == 'DENY']
    # 04.10.2026 Эльнур: «уведомления без внимания — шум». За 3 суток 2360 отказов, из них 3 настоящие поломки,
    # остальное — обычная работа (лимит номера, выключенный канал, тихие часы, чёрный список).
    # Обычные отказы — одной строкой в утренней сводке (svodka_trevog.py), сюда только поломки.
    _ОБЫЧНО = ('плотность:', 'quiet_hours', 'blacklist', 'purchase_status_won', 'роль «internal»')
    if bad:
        why = {}
        for d in bad:
            for r in ((d.get('metadata') or {}).get('denies') or ['без причины']):
                if str(r).startswith(_ОБЫЧНО):
                    continue
                why[r] = why.get(r, 0) + 1
        if why:
            tech.append('🚫 Привратник не пустил по поломке %d раз за час: %s'
                        % (sum(why.values()), ', '.join('%s ×%d' % (k, v) for k, v in sorted(why.items(), key=lambda x: -x[1])[:4])))

    # 3. очередь amoCRM встала
    # Массовая заливка (например перевод сделок) сама по себе не авария: очередь держит
    # темп и ловит «429 rate limited» от amoCRM. Тревога только если очередь ВСТАЛА —
    # есть висящие задачи и при этом за полчаса ничего не выполнено.
    pend = get('/amocrm_queue?status=eq.pending&created_at=lt.' + urllib.parse.quote(iso(90))
               + '&select=id&limit=200')
    moved = get('/amocrm_queue?status=eq.done&completed_at=gte.' + urllib.parse.quote(iso(30))
                + '&select=id&limit=5')
    if len(pend) > 5 and not moved:
        tech.append('📇 Очередь amoCRM встала: %d задач ждут, за полчаса не выполнено ни одной' % len(pend))
    failed = get('/amocrm_queue?status=eq.failed&created_at=gte.' + urllib.parse.quote(iso(180))
                 + '&select=id,last_error&limit=20')
    if failed:
        tech.append('📇 Ошибки в очереди amoCRM (%d): %s'
                    % (len(failed), (failed[0].get('last_error') or '')[:90]))

    # 4. зеркало переписки молчит в рабочее время — канал мог отвалиться
    hour = int(datetime.now(timezone.utc).strftime('%H')) + 7
    if 3 <= (hour % 24) <= 19:
        last = get('/chat_history?select=ts&order=ts.desc&limit=1')
        if last:
            gap = (datetime.now(timezone.utc) - datetime.fromisoformat(last[0]['ts'][:19] + '+00:00')).total_seconds() / 60
            if gap > 240:
                tech.append('🔇 В зеркале переписки тишина %d минут — проверь каналы' % gap)

    # 5. человек написал и остался без ответа — это уже работа, а не поломка
    recent = get('/chat_history?ts=gte.' + urllib.parse.quote(iso(1440))
                 + '&select=phone_norm,role,ts,source,content&order=ts.desc&limit=600')
    bypho = {}
    for r in recent:
        bypho.setdefault(r['phone_norm'], []).append(r)
    waiting = []
    for ph, rows in bypho.items():
        rows.sort(key=lambda x: x['ts'])
        if rows[-1]['role'] != 'user':
            continue
        # групповые чаты — это источник новостей от партнёров, а не разговор с клиентом:
        # в группе мы не отвечаем, и напоминать об «ответе» там неправильно
        if str(rows[-1].get('source') or '').endswith('_group'):
            continue
        if ph in OWN:
            continue
        mins = (datetime.now(timezone.utc) - datetime.fromisoformat(rows[-1]['ts'][:19] + '+00:00')).total_seconds() / 60
        if mins > 20:
            waiting.append((ph, int(mins), (rows[-1].get('content') or '')[:70], rows[-1].get('source')))
    for ph, mins, txt, src in waiting[:6]:
        if ph in OWN or ph.startswith('669000000') or ph.startswith('900'):
            continue   # свой или тестовый номер, это не клиент
        # застройщика и партнёра не дёргаем и о них не напоминаем: по правилу Эльнура
        # их вообще не мучаем, ответ им не обязателен
        pr = get('/client_profiles?select=name,contact_role&or=(phone_norm.eq.%s,tg_id.eq.%s)&limit=1' % (ph, ph))
        role = (pr[0].get('contact_role') if pr else None) or 'lead'
        if role != 'lead':
            continue
        who = (pr[0].get('name') if pr and pr[0].get('name') else ph)
        sales.append('🕑 %s (%s) ждёт ответа %d мин: «%s»' % (who, src, mins, txt))

    # 6. продолжение касания от другого человека или с другого номера — чиним сразу.
    #    Эльнур 18.09: «это настоящий лид, так нельзя делать». Механику я поправил,
    #    но сторож обязан ловить повтор, а не надеяться, что правка вечная.
    pend_t = get('/touch_queue?status=in.(planned,draft,approved)'
                 '&select=id,phone,persona,source_channel_id,campaign,kind&limit=200')
    for t in pend_t:
        hist = get('/touch_queue?phone=eq.' + urllib.parse.quote(str(t['phone'] or ''))
                   + '&status=in.(sent,approved)&order=id.asc&select=persona,source_channel_id&limit=1')
        if not hist:
            continue
        first = hist[0]
        fix = {}
        if first.get('persona') and t.get('persona') and first['persona'] != t['persona']:
            fix['persona'] = first['persona']
        if first.get('source_channel_id') and t.get('source_channel_id') \
           and first['source_channel_id'] != t['source_channel_id']:
            fix['source_channel_id'] = first['source_channel_id']
        if not fix:
            continue
        if SEND:
            patch('/touch_queue?id=eq.%d' % t['id'], fix)
        tech.append('🔀 Касание %d для %s готовилось от «%s», а разговор ведёт «%s» — поправил'
                    % (t['id'], t['phone'], t.get('persona'), first.get('persona')))

    # 7. Застройщика, партнёра, коллегу писать МОЖНО, мучить нельзя.
    #    Эльнур 18.09: «ты можешь их трогать, ток не мучай!». Значит: никаких лестниц
    #    дожима и не чаще раза в месяц. Разговор по делу и ответ на их сообщение —
    #    сколько угодно, это не касание.
    for t in get('/touch_queue?status=in.(planned,draft,approved)&select=id,phone,agent,occasion,kind&limit=200'):
        pr = get('/client_profiles?select=name,contact_role&or=(phone_norm.eq.%s,tg_id.eq.%s)&limit=1'
                 % (t['phone'], t['phone']))
        role = (pr[0].get('contact_role') if pr else None) or 'lead'
        if role == 'lead':
            continue
        # 01.10.2026: правило «не мучить застройщиков» снимало вызов «на связи» живой Дарье (role=internal,
        # agent=owner_task) как «уже писали за 30 дней». Свои и поручения владельца — не касание, их не трогаем.
        if role == 'internal' or (t.get('agent') or '') == 'owner_task':
            continue
        who = (pr[0].get('name') if pr and pr[0].get('name') else t['phone'])
        why = None
        if (t.get('kind') or '') in ('cold', 'silence'):
            why = 'это лестница дожима, а «%s» по ней не ведут' % role
        elif (t.get('kind') or '') == 'cold' and (t.get('channel') or '') == 'whatsapp':
            why = 'холодные через WhatsApp выключены после выпадения канала 18.09'
        else:
            was = get('/touch_queue?phone=eq.%s&status=eq.sent&sent_at=gte.%s&select=id&limit=3'
                      % (t['phone'], urllib.parse.quote(iso(43200))))
            if was:
                why = 'ему уже писали в последние 30 дней'
        if not why:
            continue
        if SEND:
            patch('/touch_queue?id=eq.%d' % t['id'],
                  {'status': 'cancelled', 'note': 'снято сторожем: %s' % why})
        tech.append('🛑 Касание %d для «%s» (%s) снято: %s' % (t['id'], who, role, why))

    # 8. встречи: напомнить Эльнуру заранее и не дать встрече «повиснуть» после
    #    Сегодня лид Valerie согласился на созвон в 12:00, напоминание осталось
    #    черновиком, никто никому не написал, встреча так и висит «назначена».
    NAZ = urllib.parse.quote('назначена')   # кириллица в адресе обязана быть закодирована,
    # иначе запрос молча падает, и проверка встреч не работает вовсе
    soon = get('/meetings?status=eq.' + NAZ + '&meet_at=gte.' + urllib.parse.quote(iso(0))
               + '&meet_at=lte.' + urllib.parse.quote(iso(-45)) + '&select=id,meet_at,phone_norm,note&limit=10')
    for m in soon:
        pr = get('/client_profiles?select=name&or=(phone_norm.eq.%s,tg_id.eq.%s)&limit=1'
                 % (m['phone_norm'], m['phone_norm']))
        who = (pr[0].get('name') if pr and pr[0].get('name') else m['phone_norm'])
        link = ''
        mm = re.search(r'https://meet\.google\.com/[a-z-]+', m.get('note') or '')
        if mm:
            link = '\n' + mm.group(0)
        txt = '📅 Через 30–45 минут созвон: %s%s' % (who, link)
        if SEND and not seen('meet:' + str(m['id']), mark=False):
            # 02.10.2026 Эльнур: «в личку — тому, кто ответственный». Ведёт Дарья (так пишет заметка встречи) —
            # напоминание ей, иначе Эльнуру; через «на связи» → Telegram офисным ботом.
            _кто = 'Дарья' if re.search(r'вед[её]т\s+дарь', m.get('note') or '', re.I) else 'Эльнур'
            try:
                _r = urllib.request.Request(E['SUPABASE_URL'].rstrip('/') + '/rest/v1/rpc/' + urllib.parse.quote('позвать'),
                    data=json.dumps({'p_persona': _кто, 'p_text': txt}).encode(), method='POST',
                    headers={'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
                             'Content-Type': 'application/json'})
                urllib.request.urlopen(_r, timeout=20)
                seen('meet:' + str(m['id']))
            except Exception:
                if tg_owner(txt):
                    seen('meet:' + str(m['id']))
        print('ЛИЧНО | ' + txt.replace('\n', ' '))

    past = get('/meetings?status=eq.' + NAZ + '&meet_at=lt.' + urllib.parse.quote(iso(90))
               + '&meet_at=gte.' + urllib.parse.quote(iso(2880)) + '&select=id,meet_at,phone_norm&limit=10')
    for m in past:
        if str(m.get('phone_norm') or '') in OWN:
            continue   # встреча на своём номере — это проверка, а не сделка
        pr = get('/client_profiles?select=name&or=(phone_norm.eq.%s,tg_id.eq.%s)&limit=1'
                 % (m['phone_norm'], m['phone_norm']))
        who = (pr[0].get('name') if pr and pr[0].get('name') else m['phone_norm'])
        sales.append('📅 Созвон с %s прошёл по времени, а статус до сих пор «назначена». '
                     'Состоялся или переносим?' % who)

    # 9. состояние каналов связи. 18.09: WhatsApp рабочего номера отвалился в qridle
    #    (сессия отпала, нужен QR), и об этом никто не узнал — Эльнур заметил сам.
    #    Сторож каналов такую проверку не делал вовсе.
    try:
        tok = ''
        for ln in open('/opt/plp-api/.env', encoding='utf-8') if os.path.exists('/opt/plp-api/.env') else []:
            if ln.startswith('WAZZUP_TOKEN='):
                tok = ln.strip().split('=', 1)[1].strip('"\'')
        if tok:
            rq = urllib.request.Request('https://api.wazzup24.com/v3/channels',
                                        headers={'Authorization': 'Bearer ' + tok})
            with urllib.request.urlopen(rq, timeout=25) as f:
                chans = json.loads(f.read().decode() or '[]')
            for c in chans:
                st = str(c.get('state') or '')
                nm = '%s %s' % (c.get('transport'), c.get('plainId'))
                if 'не акт' in str(c.get('name') or ''):
                    continue          # старые отключённые номера не трогаем
                if st != 'active':
                    line = ('📵 Канал %s не на связи: состояние «%s». '
                            'qridle значит сессия отпала и нужен новый QR, blocked значит бан.' % (nm, st))
                    tech.append(line)   # 02.10.2026: только в «Тех офис» (была ещё копия в личку — дубль)
    except Exception as ex:
        tech.append('📵 Не смог проверить каналы Wazzup: %s' % str(ex)[:70])

    # 10. два наших сообщения подряд без входящего — так делать нельзя, особенно с
    #     новым номером. Причину 18.09 устранили (правка 329, старое входящее), но
    #     сам симптом надо видеть сразу: это прямой путь к жалобе и бану.
    last = get('/chat_history?ts=gte.' + urllib.parse.quote(iso(720))
               + '&select=ts,phone_norm,role,source&order=ts.asc&limit=600')
    byph = {}
    for r in last:
        # 04.10.2026: ручные сообщения Эльнура из личного Telegram (мост пишет их в историю как наши)
        # и служебные чаты — не «двойник». Было ложное «два подряд» на Романа (…7412), которому писал сам Эльнур.
        if str(r.get('source') or '') in ('userbot_elnur', 'office_bot', 'wazzup_group', 'tg_backfill'):
            continue
        if r.get('phone_norm') and r['phone_norm'] not in OWN:
            byph.setdefault(r['phone_norm'], []).append(r)
    for ph, rr in byph.items():
        tail = [x['role'] for x in rr][-3:]
        if len(tail) >= 2 and tail[-1] == 'assistant' and tail[-2] == 'assistant':
            # 05.10.2026: канон 114 — в день 0 до пяти наших сообщений без ответа с шагом 3 часа, это лестница, а не ошибка.
            # Тревога была шумом каждые 20 минут. Нарушение — два подряд чаще, чем раз в 2,5 часа (шквал).
            try:
                t1 = datetime.fromisoformat(str(rr[-2]['ts']).replace('Z', '+00:00'))
                t2 = datetime.fromisoformat(str(rr[-1]['ts']).replace('Z', '+00:00'))
                шквал = (t2 - t1).total_seconds() < 2.5 * 3600
            except Exception:
                шквал = True
            if шквал:
                tech.append('✋ Двойник отправил два сообщения подряд чаще раза в 2,5 ч без ответа человека: %s' % ph)

    # 11. сборщик почты не отработал
    if os.path.exists('/var/log/plp_mail_intake.log'):
        age = (time.time() - os.path.getmtime('/var/log/plp_mail_intake.log')) / 60
        # 02.10.2026: сбор почты с 01.10 по пн и чт 09:05 (Эльнур: «2 раза в неделю хватит») — молчание до 4,5 суток норма
        if age > 4.5 * 24 * 60:
            tech.append('📪 Сборщик почты молчит %.1f суток (по плану пн и чт)' % (age / 1440))

    # 12. 04.10.2026: мост личного Telegram пролежал 17:11–18:10 по Пхукету (AuthKeyDuplicated, 157 перезапусков) —
    #     ни один сторож не заметил. Мост раз в 5 минут пишет «heartbeat» в свой журнал; нет свежей отметки 15 минут — тревога.
    _мост = '/home/claw/plp_tg_userbot.log'
    if os.path.exists(_мост):
        try:
            with open(_мост, 'rb') as fh:
                fh.seek(max(0, os.path.getsize(_мост) - 20000))
                хвост = fh.read().decode('utf-8', 'ignore').splitlines()
            пульс = [l for l in хвост if 'heartbeat: connected=True' in l or 'bridge up as' in l]
            if пульс:
                t0 = datetime.strptime(пульс[-1][:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                мин = (datetime.now(timezone.utc) - t0).total_seconds() / 60
                if мин > 15:
                    tech.append('🔌 Мост личного Telegram молчит %d мин: нет отметки «на связи». Сообщения из личного TG не попадают в систему, поиск по номеру в TG стоит' % мин)
        except Exception as ex:
            tech.append('🔌 Не смог проверить мост личного Telegram: %s' % str(ex)[:60])

    _было = (len(tech), len(sales))
    tech = [l for l in tech if not шум(l)]
    sales = [l for l in sales if not шум(l)]
    if _было != (len(tech), len(sales)):
        print('отсеяно как шум: тех %d, прода %d'
              % (_было[0] - len(tech), _было[1] - len(sales)))
    for line in tech:
        print('ТЕХ   | ' + line)
    for line in sales:
        print('ПРОДА | ' + line)
    if not tech and not sales:
        print('всё ровно, писать не о чем')
    if not SEND:
        return 0
    for line in tech:
        k = 'tech:' + без_чисел(line[:60])
        if not seen(k, mark=False) and tg('TG_TECH_CHAT_ID', line):
            seen(k)
    for line in sales:
        k = 'sales:' + без_чисел(line[:60])
        if not seen(k, mark=False) and tg('TG_ALERT_CHAT_ID', line):
            seen(k)
    return 0


if __name__ == '__main__':
    sys.exit(main())
