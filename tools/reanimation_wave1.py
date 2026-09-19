#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Первая волна по старым лидам из воронки сверки: пять человек, тексты в очередь касаний.

Эльнур 18.09.2026: «можно вообще начать с воронки сверка спам, только не всем писать,
а тем, кто был с низким бюджетом и адекватный» → «полный го».

Кому пишем. Из 414 сделок в стадиях «Спам» и «Не отвечают» 380 оказались живыми
людьми с рабочим номером и нормальным именем. Все пятеро пришли осенью и зимой 2025
с квиза по проекту Balcony, никто ничего не купил, в чёрных списках никого.

Текст по канону первого касания: поздороваться, коротко напомнить, кто мы и откуда
знакомы, и спросить про планы. Ни бюджета, ни объектов, ни цен, ни созвона: это
первое касание после долгой паузы, продажа тут убивает разговор.

Темп. Номер +66955492587 для WhatsApp новый, массовая холодная рассылка с него это
прямой путь в бан. Поэтому сегодня уходят двое, остальные ждут своей очереди.
И один отдельно: у Alex сейчас ночь по его часовому поясу, ему только по расписанию.

    python3 reanimation_wave1.py           # показать тексты
    python3 reanimation_wave1.py --apply   # положить в очередь (двое к отправке, трое черновиком)
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
CHANNEL = '73fa0d4d-14f2-4d2f-8d4f-45c760f4e793'   # WhatsApp +66955492587

PEOPLE = [
    dict(name='Ирина', phone='66928329118', send=True, where='Чалонг, Пхукет',
         body='Здравствуйте, Ирина. Это Эльнур, Property Library Phuket. '
              'Вы писали нам про Пхукет прошлой осенью, тогда мы так и не поговорили. '
              'Вы сейчас на острове?'),
    dict(name='Дмитрий', phone='375295684404', send=True, where='Варшава',
         body='Здравствуйте, Дмитрий. Это Эльнур, Property Library Phuket. '
              'В ноябре вы интересовались Пхукетом, для жизни и отдыха. '
              'Как сейчас, остров ещё в планах?'),
    dict(name='Ирина', phone='79253754477', send=False, where='Анталия',
         body='Здравствуйте, Ирина. Это Эльнур, Property Library Phuket. '
              'В декабре вы смотрели Пхукет, для жизни и отдыха. '
              'Тема ещё живая или пока другое направление?'),
    dict(name='Микола', phone='46704571181', send=False, where='Стокгольм',
         body='Здравствуйте. Это Эльнур, Property Library Phuket. '
              'В декабре вы оставляли заявку по Пхукету, смотрели под доход. '
              'Интерес ещё есть?'),
    dict(name='Алекс', phone='14085061252', send=False, where='Калифорния, сейчас ночь',
         body='Здравствуйте, Алекс. Это Эльнур, Property Library Phuket. '
              'В ноябре вы оставляли заявку по Пхукету, интерес был инвестиционный. '
              'Тема ещё актуальна?'),
]


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


def rest(path, method='GET', body=None):
    e = env()
    base, key = e['SUPABASE_URL'].rstrip('/') + '/rest/v1', e['SUPABASE_SERVICE_KEY']
    h = {'apikey': key, 'Authorization': 'Bearer ' + key,
         'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def main():
    for p in PEOPLE:
        print('%-8s %-14s %-22s %s' % (p['name'], p['phone'], p['where'],
                                       'СЕГОДНЯ' if p['send'] else 'черновик, ждёт очереди'))
        print('    ' + p['body'])
    if not APPLY:
        print('\nЭто отчёт. Положить в очередь: --apply')
        return 0
    made = 0
    for p in PEOPLE:
        import urllib.parse
        exists = rest('/touch_queue?phone=eq.%s&campaign=eq.%s&select=id'
                      % (p['phone'], urllib.parse.quote('сверка-спам-18.09.2026')))
        if exists:
            print('уже в очереди: %s' % p['name'])
            continue
        rest('/touch_queue', 'POST', {
            'phone': p['phone'], 'channel': 'whatsapp', 'agent': 'owner_task',
            'occasion': 'реанимация: воронка сверки', 'body': p['body'],
            'status': 'approved' if p['send'] else 'draft',
            'persona': 'Эльнур', 'source_persona': 'elnur',
            'source_channel_id': CHANNEL, 'kind': 'cold', 'step': 1,
            'campaign': 'сверка-спам-18.09.2026',
            'note': 'первая волна, отобрано по низкому бюджету и живому номеру'})
        made += 1
    print('\nположено в очередь: %d' % made)
    print('отправку делает WF_touch_send раз в 10 минут, после проверки привратником')
    return 0


if __name__ == '__main__':
    sys.exit(main())
