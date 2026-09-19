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


def seen(key):
    try:
        d = json.load(open(SEEN))
    except Exception:
        d = {}
    now = time.time()
    d = {k: v for k, v in d.items() if now - v < TTL}
    was = key in d
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


def main():
    if '--digest' in sys.argv:
        return digest()
    if '--feed' in sys.argv:
        return feed()
    tech, sales = [], []

    # 1. касание одобрено, но не ушло больше часа — отправщик или привратник встал
    stuck = get('/touch_queue?status=eq.approved&created_at=lt.' + urllib.parse.quote(iso(70))
                + '&select=id,phone,created_at,note&limit=20')
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

    for line in tech:
        print('ТЕХ   | ' + line)
    for line in sales:
        print('ПРОДА | ' + line)
    if not tech and not sales:
        print('всё ровно, писать не о чем')
    if not SEND:
        return 0
    for line in tech:
        if not seen('tech:' + line[:60]):
            tg('TG_TECH_CHAT_ID', line)
    for line in sales:
        if not seen('sales:' + line[:60]):
            tg('TG_ALERT_CHAT_ID', line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
