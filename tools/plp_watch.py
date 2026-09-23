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
    r = urllib.request.Request(BASE + path, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=40) as f:
            return json.loads(f.read().decode() or '[]')
    except Exception:
        return []


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


def seen(key):
    try:
        d = json.load(open(SEEN))
    except Exception:
        d = {}
    now = time.time()
    срок = TTL_ОЖИДАНИЕ if ':🕑' in key or key.startswith(('sales:🕑', 'tech:🕑')) else TTL
    d = {k: v for k, v in d.items() if now - v < max(TTL, TTL_ОЖИДАНИЕ)}
    was = (key in d) and (now - d[key] < срок)
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
       # демо и тестовые номера: это не люди, напоминать о них в отдел продаж незачем
       '66900000777', '66900000999', '66900000998', '66999000999', '66999000998',
       '66900000000', '900000777', '66900000099',
       '5571405041',      # группа «PLP · Тех офис»
       '4664612682'}      # группа «PLP | отдел продаж»


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
        tg_owner(text)
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
    except Exception:
        pass


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
    375297006858 без тройки даёт 75297006858, то есть «код 7, Россия».
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

    # 2. привратник отказал за последний час — причины важнее самого факта
    den = get('/funnel_events?event_type=eq.gate_decision&ts=gte.' + urllib.parse.quote(iso(60))
              + '&select=metadata&limit=200')
    bad = [d for d in den if (d.get('metadata') or {}).get('decision') == 'DENY']
    if bad:
        why = {}
        for d in bad:
            for r in ((d.get('metadata') or {}).get('denies') or ['без причины']):
                why[r] = why.get(r, 0) + 1
        tech.append('🚫 Привратник отказал %d раз за час: %s'
                    % (len(bad), ', '.join('%s ×%d' % (k, v) for k, v in sorted(why.items(), key=lambda x: -x[1])[:4])))

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
        if SEND and not seen('meet:' + str(m['id'])):
            tg_owner(txt)
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
                    tech.append(line)
                    if SEND and not seen('chan:' + nm + st):
                        tg_owner(line)
    except Exception as ex:
        tech.append('📵 Не смог проверить каналы Wazzup: %s' % str(ex)[:70])

    # 10. два наших сообщения подряд без входящего — так делать нельзя, особенно с
    #     новым номером. Причину 18.09 устранили (правка 329, старое входящее), но
    #     сам симптом надо видеть сразу: это прямой путь к жалобе и бану.
    last = get('/chat_history?ts=gte.' + urllib.parse.quote(iso(720))
               + '&select=ts,phone_norm,role,source&order=ts.asc&limit=600')
    byph = {}
    for r in last:
        if r.get('phone_norm') and r['phone_norm'] not in OWN:
            byph.setdefault(r['phone_norm'], []).append(r)
    for ph, rr in byph.items():
        tail = [x['role'] for x in rr][-3:]
        if len(tail) >= 2 and tail[-1] == 'assistant' and tail[-2] == 'assistant':
            tech.append('✋ Двойник отправил два сообщения подряд без ответа человека: %s' % ph)

    # 11. сборщик почты не отработал
    if os.path.exists('/var/log/plp_mail_intake.log'):
        age = (time.time() - os.path.getmtime('/var/log/plp_mail_intake.log')) / 60
        if age > 40:
            tech.append('📪 Сборщик почты молчит %d минут' % age)

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
        if not seen('tech:' + без_чисел(line[:60])):
            tg('TG_TECH_CHAT_ID', line)
    for line in sales:
        if not seen('sales:' + без_чисел(line[:60])):
            tg('TG_ALERT_CHAT_ID', line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
