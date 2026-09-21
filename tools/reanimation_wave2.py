#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вторая волна реанимации: настоящие лиды из «Не отвечают», по одному, с поводом.

Эльнур 19.09.2026: «такое пойдет да, ток это не тест, а настоящая работа с настоящими
лидами из настоящей срм… его цель, выйти на лида, установить связь, заслужить доверие,
закрыть его боль, и тогда мы можем его квалить, скорить, продавать!»

Откуда берём. Воронка сверки, этап «Не отвечают» (61429858) — 191 сделка. У каждой в
карточке amoCRM записано, что человек сам указал в заявке: проект, цель покупки, язык,
город. Это и есть повод: не «вы ещё думаете?», а «вы смотрели такой-то проект, там
изменились цены и остатки».

Кого НЕ трогаем (железные правила Эльнура, проверяются здесь же, а не на словах):
  • спам, чёрный список, явный СТОП (ai_paused) — молчим;
  • застройщики, партнёры, коллеги, свои — им не продают, воронку им не ведут;
  • купившие — им пишем только по прямому апруву;
  • первая волна 18.09 — второй раз тем же людям не пишем;
  • у кого нет карточки клиента — привратник таких всё равно не пропустит;
  • тайские номера не исключаем, но помечаем: с ними сперва разбираемся, кто это.

Темп. Суббота и воскресенье — одно касание, не шквал. Поэтому волна кладётся
черновиками, а к отправке помечается ровно столько, сколько названо в --send N,
с интервалом, и только в окно 11:00–21:00 по Пхукету.

    python3 reanimation_wave2.py              # собрать, проверить, показать и записать список
    python3 reanimation_wave2.py --apply      # положить черновиками в очередь касаний
    python3 reanimation_wave2.py --apply --send 3   # три из них пометить к отправке
"""
import datetime, json, os, sys, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
SEND_N = int(sys.argv[sys.argv.index('--send') + 1]) if '--send' in sys.argv else 0
STATUS_NOANSWER = 61429858
CAMPAIGN = 'реанимация-не-отвечают-19.09.2026'
# Пишет тот, кто ОТВЕТСТВЕННЫЙ за сделку в amoCRM. Иначе сторож справедливо ругается:
# «переписку вёл Эльнур, а в CRM ответственный Дарья». И это же распределяет нагрузку
# между каналами — Эльнур 19.09: «можно такой же формат как и мой», продажи ведут оба.
ВЛАДЕЛЬЦЫ = {
    10172498: dict(имя='Эльнур', персона='Эльнур',
                   wa='73fa0d4d-14f2-4d2f-8d4f-45c760f4e793',
                   tg='db2b55be-11da-4bc2-abcb-c8562f0fbed4'),
    10882506: dict(имя='Дарья', персона='Дарья',
                   wa='35d237fd-a3be-4496-886a-418dfa09c529',
                   tg='f2a15f1d-a252-448c-a7d2-c6ee5edfb7a0'),
}
ПО_УМОЛЧАНИЮ = 10172498
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wave2_final.json')

# первая волна 18.09 — этим людям уже написали, повторно не трогаем
WAVE1 = {'66928329118', '375295684404', '79253754477', '46704571181', '14085061252'}

NOT_A_LEAD = {'partner', 'developer', 'colleague', 'internal', 'team', 'family', 'supplier'}


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def get(path):
    r = urllib.request.Request(BASE + path, headers=H)
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers=dict(H, **{'Content-Type': 'application/json',
                                                  'Prefer': 'return=representation'}), method='POST')
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def cf(lead, name):
    for f in (lead.get('custom_fields') or []):
        if f.get('field_name') == name:
            vals = f.get('values') or []
            if vals and vals[0].get('value'):
                return str(vals[0]['value']).strip()
    return ''


# в карточках amoCRM вместо имени часто стоит служебное слово; «Здравствуйте, Новый.»
# живому человеку отправить нельзя, поэтому такие слова именем не считаем
NOT_NAMES = ('новый', 'новая', 'лид', 'заявка', 'сделка', 'клиент', 'контакт', 'без',
             'lead', 'client', 'test', 'тест', 'unknown', 'whatsapp', 'telegram',
             'instagram', 'facebook', 'fb', 'ig', 'red', 'plp')


def clean_name(s):
    """Имя человека из чего угодно: «Новый лид RED - Абдул», «Иван Петров», «Dima».

    В amoCRM имя почти всегда спрятано за служебной приставкой источника, а первым
    словом стоит «Новый». Берём то, что после разделителя, и отбрасываем фамилию:
    в первом касании она лишняя."""
    s = str(s or '').strip()
    for sep in (' - ', ' — ', ' – ', ':'):
        if sep in s:
            s = s.split(sep)[-1].strip()
    if not s or any(ch.isdigit() for ch in s):
        return ''
    w = s.split()[0].strip('.,')
    if w.lower() in NOT_NAMES or not (1 < len(w) <= 20):
        return ''
    return w


def clean_project(s):
    """Название проекта, а не описание лота: «2BR 78 кв.м» проектом не является."""
    s = str(s or '').strip()
    if not (2 < len(s) <= 30):
        return ''
    low = s.lower()
    if s[0].isdigit() or any(k in low for k in ('кв.м', 'кв. м', 'm2', 'м2', 'br ', 'студи')):
        return ''
    return s


# У части заявок поле «Проект» пустое, но название проекта стоит в метке рекламы.
# Берём только те метки, которые однозначно ложатся на каталог: «title» без уточнения
# пропускаем — под этим брендом у нас полтора десятка проектов, ошибиться нельзя.
UTM_PROJECT = (('title-serenity', 'The Title Serenity Naiyang'),
               ('eden', 'Gardens of Eden'),
               ('balcony', 'The BALCONY Nai Yang'),
               ('coralina', 'The Title Coralina Kamala'),
               ('bayside', 'Laguna Beach Residences Bayside'),
               ('ayana', 'AYANA Heights Seaview Residences'))


def project_from_utm(lead):
    """Проект из рекламной метки — когда поле «Проект» в заявке пустое."""
    hay = ''
    for f in (lead.get('custom_fields') or []):
        if f.get('field_code') in ('UTM_CAMPAIGN', 'UTM_MEDIUM', 'UTM_CONTENT'):
            vals = f.get('values') or []
            if vals:
                hay += ' ' + str(vals[0].get('value') or '')
    hay = hay.lower()
    for slug, title in UTM_PROJECT:
        if slug in hay:
            return title
    return ''


def first_name(s):
    """Имя человека из названия сделки вида «Новый лид RED - Alex»."""
    s = str(s or '')
    for sep in (' - ', ' — ', ':'):
        if sep in s:
            s = s.split(sep)[-1]
    s = s.strip().strip('.,')
    if not s or len(s) > 24 or any(ch.isdigit() for ch in s):
        return ''
    low = s.lower()
    if low.startswith(('новый лид', 'заявка', 'сделка', 'lead', 'без имени')):
        return ''
    return s.split()[0]


def кто_ведёт(lead):
    """Ответственный за сделку решает, от чьего лица идёт касание и с какого канала."""
    uid = lead.get('responsible_user_id')
    return ВЛАДЕЛЬЦЫ.get(uid, ВЛАДЕЛЬЦЫ[ПО_УМОЛЧАНИЮ])


def body_for(name, project, goal, city, phone='', автор='Эльнур'):
    """Первое касание: кто мы, откуда знакомы, повод, и одна вилка на выбор.

    Ни цен, ни объектов, ни созвона: это возобновление разговора, а не продажа.
    Вопрос один и с вариантами — на открытый вопрос после года молчания не отвечают.

    Формулировки берутся разные. Десять одинаковых сообщений подряд с одного номера
    WhatsApp читает как рассылку робота и закрывает номер, а нас уже один раз выбило."""
    v = sum(ord(c) for c in (phone or name or 'x')) % 3
    hi = 'Здравствуйте, %s.' % name if name else 'Здравствуйте.'
    if project:
        povod = [
            'Вы оставляли заявку по проекту %s на Пхукете, тогда мы так и не поговорили. '
            'За это время там поменялись цены и остатки.' % project,
            'Вы писали нам про %s на Пхукете, а разговор тогда не сложился. '
            'С тех пор по проекту сдвинулись и цены, и наличие.' % project,
            'Вы интересовались проектом %s на Пхукете, но тогда мы не созвонились. '
            'С того времени там многое поменялось.' % project][v]
    else:
        povod = [
            'Вы оставляли заявку по Пхукету, тогда мы так и не поговорили. '
            'За это время рынок заметно сдвинулся.',
            'Вы писали нам про Пхукет, а разговор тогда не сложился. '
            'С тех пор по острову изменились и цены, и условия рассрочки.',
            'Вы интересовались Пхукетом, но тогда мы не созвонились. '
            'Рынок с того времени прилично сдвинулся.'][v]
    low = goal.lower()
    # Вилка короткая и без спорной интонации. «или всё-таки и для себя» читается как
    # пререкание с человеком, а мы просто уточняем задачу (замечание Эльнура 19.09).
    if 'инвест' in low or 'аренд' in low or 'доход' in low:
        vilka = ['Скажите, сейчас смотрите под доход от аренды или для себя?',
                 'Уточню одно: под аренду или для себя?',
                 'Чтобы говорить по делу: под доход или для жизни?'][v]
    elif 'себя' in low or 'жизн' in low or 'прожив' in low:
        vilka = ['Скажите, сейчас смотрите для себя или под аренду?',
                 'Уточню одно: для жизни или под доход?',
                 'Чтобы говорить по делу: для себя или с расчётом на аренду?'][v]
    else:
        vilka = ['Скажите, смотрите под доход от аренды или для себя?',
                 'Уточню одно: под доход или для себя?',
                 'Чтобы говорить по делу: под аренду или для жизни?'][v]
    return '%s Это %s, Property Library Phuket. %s %s' % (hi, автор, povod, vilka)


def main():
    leads = get('/crm_leads?status_id=eq.%d&is_deleted=is.false'
                '&select=id,name,created_at_crm,updated_at_crm,custom_fields,contacts,responsible_user_id'
                '&order=created_at_crm.desc&limit=300' % STATUS_NOANSWER)
    print('в «Не отвечают»: %d сделок' % len(leads))

    ids = sorted({c for l in leads for c in (l.get('contacts') or [])})
    phones, names = {}, {}
    for i in range(0, len(ids), 80):
        chunk = ','.join(str(x) for x in ids[i:i + 80])
        for r in get('/crm_contact_phones?contact_id=in.(%s)&select=contact_id,phone_norm' % chunk):
            phones.setdefault(r['contact_id'], str(r['phone_norm'] or '').replace('+', ''))
        # имя берём из карточки контакта: в названии сделки его чаще нет вовсе
        for r in get('/crm_contacts?id=in.(%s)&select=id,name,first_name' % chunk):
            names[r['id']] = str(r.get('first_name') or r.get('name') or '').strip()

    rows, drop = [], {}
    for l in leads:
        ph, nm = '', ''
        for c in (l.get('contacts') or []):
            ph = phones.get(c, '')
            if ph:
                nm = names.get(c, '')
                break
        if not ph or len(ph) < 10:
            drop['нет номера'] = drop.get('нет номера', 0) + 1
            continue
        if ph in WAVE1:
            drop['первая волна'] = drop.get('первая волна', 0) + 1
            continue
        вед = кто_ведёт(l)
        rows.append(dict(lead_id=l['id'], phone=ph, ведёт=вед['имя'],
                         персона=вед['персона'], канал_wa=вед['wa'], канал_tg=вед['tg'],
                         name=clean_name(nm) or first_name(l.get('name')),
                         project=clean_project(cf(l, 'Проект')) or project_from_utm(l), goal=cf(l, 'Цель покупки'),
                         city=cf(l, 'Локация'), lang=cf(l, 'Язык'),
                         created=str(l.get('created_at_crm'))[:10]))

    uniq, seen = [], set()
    for r in rows:
        if r['phone'] in seen:
            drop['дубль номера'] = drop.get('дубль номера', 0) + 1
            continue
        seen.add(r['phone'])
        uniq.append(r)

    # проверки пачками, а не по одному: 183 человека это 183 круга по сети
    def chunked(vals, n=60):
        for i in range(0, len(vals), n):
            yield vals[i:i + n]

    profs, cards, black = {}, {}, set()
    allph = [r['phone'] for r in uniq]
    for ch in chunked(allph):
        lst = ','.join(ch)
        for x in get('/client_profiles?phone_norm=in.(%s)&select=phone_norm,is_spam,'
                     'is_blacklisted,ai_paused,contact_role,purchase_status' % lst):
            profs.setdefault(str(x['phone_norm']), []).append(x)
        for x in get('/clients?phone=in.(%s)&select=client_id,code,phone,is_internal,phone_status' % lst):
            cards.setdefault(str(x.get('phone') or '').replace('+', ''), []).append(x)
        for x in get('/blacklist?phone=in.(%s)&select=phone' % lst):
            black.add(str(x['phone']).replace('+', ''))
    # часть карточек хранит номер с плюсом — добираем их вторым проходом
    miss = [p for p in allph if p not in cards]
    for ch in chunked(miss):
        lst = ','.join('+' + p for p in ch)
        for x in get('/clients?phone=in.(%s)&select=client_id,code,phone,is_internal' % urllib.parse.quote(lst, safe=',')):
            cards.setdefault(str(x.get('phone') or '').replace('+', ''), []).append(x)

    no_profile = 0
    ok = []
    for r in uniq:
        p = profs.get(r['phone'], [])
        if not p:
            no_profile += 1
        bad = None
        for x in p:
            if x.get('is_spam'):
                bad = 'спам'
            elif x.get('is_blacklisted'):
                bad = 'чёрный список'
            elif x.get('ai_paused'):
                bad = 'стоп от человека'
            elif str(x.get('contact_role') or '').lower() in NOT_A_LEAD:
                bad = 'не лид: ' + str(x.get('contact_role'))
            elif str(x.get('purchase_status') or '').lower() in ('won', 'closed'):
                bad = 'уже купил'
        if not bad and r['phone'] in black:
            bad = 'чёрный список'
        cl = cards.get(r['phone'], [])
        # номер, размеченный как непригодный, в волну не берём: писать в пустоту
        # значит жечь лимиты канала и портить статистику доставки
        if cl and str(cl[0].get('phone_status') or 'ok') not in ('ok', 'None', ''):
            drop['битый номер: ' + str(cl[0].get('phone_status'))] = \
                drop.get('битый номер: ' + str(cl[0].get('phone_status')), 0) + 1
            continue
        if cl and not r['name']:
            r['name'] = clean_name(cl[0].get('name'))
        if not bad:
            if not cl:
                bad = 'нет карточки клиента'
            elif any(c.get('is_internal') for c in cl):
                bad = 'свой'
        if bad:
            drop[bad] = drop.get(bad, 0) + 1
            continue
        r['client_code'] = cl[0].get('code')
        r['thai'] = r['phone'].startswith('66')
        r['body'] = body_for(r['name'], r['project'], r['goal'], r['city'], r['phone'], r['персона'])
        ok.append(r)

    # сперва свежие: чем ближе заявка, тем теплее разговор
    ok.sort(key=lambda x: x['created'], reverse=True)
    # сперва те, где повод самый предметный: есть и имя, и проект из заявки
    blank = [x for x in ok if not x['project'] and not x['name']]
    if blank:
        drop['ни имени, ни проекта — повода нет'] = len(blank)
    ok = [x for x in ok if x['project'] or x['name']]
    ok.sort(key=lambda x: (0 if (x['project'] and x['name']) else 1 if x['project'] else 2))
    ok = ok[:10]

    print('без профиля в базе (флаги спам/стоп/роль по ним не проверить): %d из %d'
          % (no_profile, len(uniq)))
    print('отсеяно: %s' % ('; '.join('%s %d' % (k, v) for k, v in sorted(drop.items())) or 'никого'))
    print('к работе: %d\n' % len(ok))
    for i, r in enumerate(ok, 1):
        print('%2d. %-12s %-14s %-16s ведёт %-7s %s%s'
              % (i, r['name'], r['phone'], r['project'][:16], r['ведёт'],
                 r['city'][:18], '  ⚠ тайский' if r['thai'] else ''))
        print('    ' + r['body'])
    json.dump(ok, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nсписок записан: %s' % OUT)

    if not APPLY:
        print('\nЭто отчёт. Положить в очередь: --apply [--send N]')
        return 0

    # Отправщик за один проход берёт восемь строк. Если положить всё разом как
    # «готово к отправке», десять сообщений уйдут с одного номера почти одновременно —
    # это и есть шквал, за который закрывают номер. Разносим по времени.
    STEP_MIN = 25
    start = datetime.datetime.now(datetime.timezone.utc)
    made = 0
    for i, r in enumerate(ok):
        if get('/touch_queue?phone=eq.%s&campaign=eq.%s&select=id'
               % (r['phone'], urllib.parse.quote(CAMPAIGN))):
            print('уже в очереди: %s' % r['name'])
            continue
        post('/touch_queue', {
            'phone': r['phone'], 'channel': 'whatsapp', 'agent': 'owner_task',
            'occasion': 'реанимация: заявка по проекту %s' % (r['project'] or 'Пхукет'),
            'body': r['body'],
            'status': 'approved' if i < SEND_N else 'draft',
            'persona': r['персона'], 'source_channel_id': r['канал_tg'],
            'scheduled_at': (start + datetime.timedelta(minutes=STEP_MIN * i)).isoformat(),
            'source_persona': r['персона'].lower(),
            'kind': 'cold', 'step': 1, 'campaign': CAMPAIGN,
            'note': 'этап «Не отвечают», повод из заявки: %s / %s' % (r['project'], r['goal'])})
        made += 1
    print('\nположено в очередь: %d, из них к отправке: %d' % (made, min(SEND_N, made)))
    print('интервал между сообщениями: %d минут, последнее уйдёт примерно в %s'
          % (STEP_MIN, (start + datetime.timedelta(minutes=STEP_MIN * (min(SEND_N, made) - 1), hours=7)).strftime('%H:%M по Пхукету')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
