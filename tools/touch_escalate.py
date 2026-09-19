#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Молчит в WhatsApp 6–9 часов — продолжаем ТУ ЖЕ переписку в Telegram по тому же номеру.

Эльнур 19.09.2026: «когда берём лид в работу, сперва пишем ему на ватсап по его номеру,
если он там молчит часов 6-9, пишем потом на его тг через его номер, чтобы достучаться,
всё идёт как продолжение единого человека, ведётся одна история на одного человека».

Канон #111 one_person_one_thread. Здесь — руки к этому правилу.

Что делает. Берёт отправленные касания в WhatsApp старше шести часов, проверяет, ответил
ли человек хоть что-то после этого (по его номеру, по ВСЕЙ истории, а не по каналу), и
если тишина — ставит в очередь продолжение в Telegram по тому же номеру, с того же лица,
с той же кампанией и тем же поводом.

Чего он НЕ делает:
  • не здоровается заново: это не новое знакомство, а продолжение одной мысли;
  • не пишет второй раз в Telegram, если туда уже писали по этому поводу;
  • не трогает того, кто ответил хоть в каком канале;
  • не обходит привратника: отправляет WF_touch_send, там все проверки на месте.

Окно 6–9 часов берём по нижней границе: шесть часов молчания уже основание, ждать до
девяти смысла нет. Само время отправки посчитает touch_slot в поясе человека.

    python3 touch_escalate.py            # показать, кого догоним
    python3 touch_escalate.py --apply    # поставить продолжения в очередь
"""
import datetime, json, os, sys, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
SILENT_HOURS = 6


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def last_question(body):
    """Свой же вопрос из первого касания — чтобы человек увидел ту же мысль, а не новую.

    Внутренний повод («реанимация: воронка сверки») наружу не идёт никогда: это наша
    пометка для очереди, а не слова для человека."""
    import re
    qs = re.findall(r'[^.!?\n]*\?', str(body or '').replace('\n', ' '))
    if qs:
        q = qs[-1].strip(' .,:;')
        if 8 < len(q) < 160:
            return q[0].upper() + q[1:]
    return ''


def continuation(name, body, phone):
    """Продолжение, а не новое знакомство: ни «здравствуйте», ни представления заново."""
    v = sum(ord(c) for c in (phone or 'x')) % 3
    who = (name + ', ') if name else ''
    lead = [
        '%sпишу сюда, вдруг в Telegram удобнее.' % who,
        '%sдублирую в Telegram, чтобы не потерялось.' % who,
        '%sперехожу сюда, в WhatsApp могло не дойти.' % who,
    ][v]
    if not name:
        lead = lead[0].upper() + lead[1:]
    q = last_question(body)
    tail = q if q else ['Тема ещё актуальна?',
                        'Интерес ещё живой?',
                        'По Пхукету тема ещё в силе?'][v]
    return '%s %s' % (lead, tail)


def main():
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=SILENT_HOURS)).isoformat()
    sent = call('/touch_queue?status=eq.sent&channel=eq.whatsapp&sent_at=lt.%s'
                '&select=id,phone,body,occasion,campaign,persona,agent,source_channel_id,'
                'source_persona,step,kind,client_code,sent_at&order=sent_at.desc&limit=200'
                % urllib.parse.quote(since))
    print('касаний в WhatsApp старше %d часов: %d' % (SILENT_HOURS, len(sent)))
    if not sent:
        return 0

    seen, plan = set(), []
    for t in sent:
        ph = str(t.get('phone') or '')
        if not ph or ph in seen:
            continue
        seen.add(ph)
        # ответил ли человек ПОСЛЕ нашего касания — по всей его истории, любой канал
        reply = call('/chat_history?phone_norm=eq.%s&role=eq.user&ts=gt.%s&select=id&limit=1'
                     % (ph, urllib.parse.quote(str(t['sent_at']))))
        if reply:
            continue
        already = call('/touch_queue?phone=eq.%s&channel=eq.telegram&select=id&limit=1' % ph)
        if already:
            continue
        cl = (call('/clients?phone=eq.%s&select=name&limit=1' % ph)
              or call('/clients?phone=eq.%s&select=name&limit=1' % urllib.parse.quote('+' + ph)))
        parts = str((cl[0].get('name') if cl else '') or '').split()
        name = parts[0] if parts else ''
        plan.append((t, ph, name))

    print('молчат и ещё не догнаны в Telegram: %d\n' % len(plan))
    for t, ph, name in plan:
        print('%-11s %-14s молчит с %s' % (name or '—', ph, str(t['sent_at'])[:16]))
        print('    ' + continuation(name, t.get('body'), ph))
    if not APPLY:
        print('\nЭто отчёт. Поставить в очередь: --apply')
        return 0

    made = 0
    for t, ph, name in plan:
        call('/touch_queue', 'POST', {
            'phone': ph, 'channel': 'telegram', 'agent': t.get('agent') or 'owner_task',
            'occasion': t.get('occasion'), 'body': continuation(name, t.get('body'), ph),
            'status': 'approved', 'persona': t.get('persona'),
            'source_persona': t.get('source_persona'),
            'source_channel_id': t.get('source_channel_id'),
            'kind': t.get('kind') or 'cold', 'step': (t.get('step') or 1),
            'campaign': t.get('campaign'), 'client_code': t.get('client_code'),
            'note': 'догон по канону #111: в WhatsApp тишина с %s' % str(t['sent_at'])[:16]})
        made += 1
    print('\nпоставлено продолжений в Telegram: %d' % made)
    print('отправит WF_touch_send раз в 10 минут, после привратника')
    return 0


if __name__ == '__main__':
    sys.exit(main())
