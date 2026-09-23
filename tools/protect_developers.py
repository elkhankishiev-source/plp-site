#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Застройщиков и партнёров не трогаем: проставляем роль там, где её забыли.

Эльнур 18.09.2026: «Камилле не пиши, она застройщик, оставь её в покое! Это касается
всех… не мучай застройщиков!!!! Зафиксируй раз и навсегда».

Механика запрета уже есть и работает: `touch_blocked` не пускает касания никому,
у кого contact_role не «lead». Проверено на живых карточках: Камилла Art House,
Коля Clover, Anna Ayana, PLP Developer info — все закрыты.

Слабое место одно: роль заполнена у горстки профилей. У кого она пустая, тот для
системы обычный лид, и однажды ему уйдёт касание. Этот скрипт закрывает дыру
заранее: читает переписку и ставит роль там, где человек явно с той стороны рынка.

Признаки берём жёсткие, чтобы не пометить живого покупателя:
  • говорит от лица проекта: «наш проект», «мы застройщик», «our project», «our team»;
  • шлёт рабочие материалы рынка: прайс для агентов, комиссия агенту, co-broke,
    «уважаемые партнёры», приглашение на брокерский показ;
  • подпись с названием компании-застройщика в имени профиля.

    python3 protect_developers.py            # показать кандидатов
    python3 protect_developers.py --apply    # проставить роль
"""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request

APPLY = '--apply' in sys.argv
ENV = os.path.expanduser('~/.plp_site_supabase.env')

STRONG = re.compile(
    r'(наш проект|мы застройщик|от застройщика мы|our project|our team|our development|'
    r'коммисси\w* агент|комисси\w* агент|для агентов|agent commission|co-?broke|'
    r'уважаемые партн[её]р|dear partners|dear agents|прайс для агент|broker (?:event|preview)|'
    r'sales gallery|шоурум нашего|наш отдел продаж)', re.I)
NAMEDEV = re.compile(r'(develop|residence|property|group|estate|realty|villas|construction|'
                     r'застройщик|девелопер)', re.I)


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
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.loads(f.read().decode() or '[]')


def get_страницами(path):
    """Читаем ВСЮ выборку, а не первую тысячу.

    23.09.2026: Supabase отдаёт максимум 1000 строк за раз и МОЛЧА обрезает —
    `limit=4000` в запросе ничего не меняет, ответ всё равно 1000 строк
    (проверено: Content-Range 0-999/3393). Реплик клиентов в chat_history 3393,
    то есть сторож застройщиков видел последнюю тысячу и 2393 реплики не читал:
    партнёр, писавший раньше, роль не получал. Те же грабли были в
    census_owners.py и amo_dialog_notes.py. Листаем заголовком Range.

    Только чтение: PATCH по страницам гонять нельзя — запись повторится."""
    # свой limit в пути перебивает Range: каждая страница вернёт одну и ту же
    # первую тысячу, и цикл не кончится никогда.
    path = re.sub(r'[?&]limit=\d+', lambda m: '?' if m.group(0)[0] == '?' else '', path)
    path = path.replace('?&', '?').rstrip('?&')
    из, шаг, всё = 0, 1000, []
    while True:
        r = urllib.request.Request(BASE + path, headers=dict(H, Range='%d-%d' % (из, из + шаг - 1)))
        try:
            with urllib.request.urlopen(r, timeout=120) as f:
                кусок = json.loads(f.read().decode() or '[]')
        except urllib.error.HTTPError as ex:
            if ex.code == 416:      # строк ровно кратно 1000 — страниц больше нет
                return всё
            raise
        всё += кусок
        if len(кусок) < шаг:
            return всё
        из += шаг


def patch(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers=dict(H, **{'Content-Type': 'application/json'}), method='PATCH')
    urllib.request.urlopen(r, timeout=30)


def main():
    # второй ключ сортировки обязателен: ts не уникален, и без id.desc страницы
    # Range перемешаются — строки повторятся или потеряются
    rows = get_страницами('/chat_history?role=eq.user&select=phone_norm,content&order=ts.desc,id.desc')
    byp = {}
    for r in rows:
        ph = r.get('phone_norm')
        if not ph:
            continue
        byp.setdefault(ph, []).append(r.get('content') or '')
    hits = {}
    for ph, texts in byp.items():
        hay = ' '.join(texts)[:6000]
        m = STRONG.search(hay)
        if m:
            hits[ph] = m.group(0)[:40]
    if not hits:
        print('кандидатов нет')
        return 0
    # Тот же обрез, только не со стороны Supabase, а со своей: раньше сюда
    # доходило 125 номеров и срез [:200] не мешал, после правки 23.09 доходит 319
    # и 119 номеров молча выпадали. Идём пачками по 100 — длинный in.() ещё и
    # упирается в длину URL.
    ключи = list(hits)
    profs = []
    for i in range(0, len(ключи), 100):
        profs += get('/client_profiles?phone_norm=in.(%s)&select=phone_norm,name,contact_role'
                     % ','.join(ключи[i:i + 100])) or []
    todo = [p for p in profs if not p.get('contact_role')]
    print('нашлось по переписке: %d, из них без роли: %d' % (len(hits), len(todo)))
    for p in todo:
        why = hits.get(p['phone_norm'], '')
        kind = 'developer' if NAMEDEV.search(p.get('name') or '') else 'partner'
        print('  %-13s %-34s → %-9s (сигнал: «%s»)' % (p['phone_norm'], (p.get('name') or '')[:34], kind, why))
        if APPLY:
            patch('/client_profiles?phone_norm=eq.' + p['phone_norm'],
                  {'contact_role': kind,
                   'contact_role_by': 'код: признаки рынка в переписке, 18.09.2026 — касания запрещены'})
    if not APPLY:
        print('\nЭто отчёт. Проставить роль: --apply')
    else:
        print('\nроль проставлена: %d — касания им больше не уйдут' % len(todo))
    return 0


if __name__ == '__main__':
    sys.exit(main())
