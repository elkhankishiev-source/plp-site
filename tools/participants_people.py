#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Живые люди в реестре участников — и разбор того, где система их путает.

Эльнур 19.09.2026: «не позабудь кто есть из наших всех участников, в чём проблема; если
ты не знаешь, значит они тем более, вот баги».

В `system_participants` до этого были только машины и роли: мозг, двойники, боты,
сторожа. Живых людей не было вообще. Поэтому «кто есть кто» знали про ботов и не знали
про людей.

ЧТО НАШЛОСЬ В КАРТОТЕКЕ КЛИЕНТОВ — наши собственные номера и группы лежат там как
клиенты, под чужими именами:

  PLP-001557  «Оксана Штойк Валид Пхт Plp Рабочий»   тел 66955492587
              Это НАШ рабочий номер Эльнура, канал elnur_wa_new. Записан как Оксана.
  PLP-003133  «Дарья Ханкишиева ❤️»                   тел 66640709032
  PLP-003208  «Дарья»                                 тел 66960169127
              Это каналы двойника Дарьи, а не люди.
  PLP-001555  «ТЕСТ»                                  тел 66954143874, тг 509498386
              Это личный номер Эльнура, названный «ТЕСТ».
  PLP-004198  «Эльнур»                                тел 954143874  — номер без кода страны
  PLP-001514  «Elnur»                                 тел 509498386  — это тг-id в поле телефона
  PLP-001463  «4664612682»                            — группа «Отдел продаж» как клиент
  PLP-004192  «PLP | Developer info»                  тел 12036319…  — WhatsApp-группа как клиент
  PLP-003490  «Валерия смм Радион Red»                тел 75333942426 — номер битый (нет 3)
              дубль к PLP-001289 «Валерия (маркетолог/контент)» 375333942426

Скрипт заводит живых людей как участников, чтобы система знала их по имени и роли, и
печатает список подозрительных карточек, чтобы их разобрать руками, а не молча слить.

    python3 participants_people.py            # показать
    python3 participants_people.py --apply    # завести людей в реестр
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv

PEOPLE = [
    dict(code='person_elnur', kind='человек', title='Эльнур Ханкишиев — владелец',
         persona='Эльнур', is_internal=True, address_as='Эльнур',
         phones=['66954143874'], tg_ids=['509498386', '8554364120'],
         purpose='Владелец компании. Решает всё: цены, скидки, кому и что писать, что публиковать. '
                 'Его поручение — это приказ и разрешение одновременно.',
         can='Всё.', cannot='—',
         note='Личный номер +66 95-414-3874 — его собственный, он с него работает сам, '
              'иногда отвечает через ИИ. В переписку на этом номере не вмешиваться.'),
    dict(code='person_valeria', kind='человек', title='Валерия — СММ и тестирование системы',
         persona=None, is_internal=True, address_as='Валерия',
         phones=['375333942426'], tg_ids=[],
         purpose='Ведёт соцсети и контент, а также проверяет систему как тестировщик.',
         can='Смотреть и проверять работу двойников, готовить контент.',
         cannot='Не лид и не клиент: анкету ей не задают, по воронке не ведут.',
         note='В картотеке два дубля: PLP-001289 и PLP-003490 с битым номером 75333942426.'),
    dict(code='person_oksana', kind='человек', title='Оксана — агент, уволилась',
         persona=None, is_internal=True, address_as='Оксана',
         phones=['79777426165'], tg_ids=[],
         purpose='Работала агентом, уволилась. Её сделки переведены на Эльнура.',
         can='—', cannot='Ей не пишем и на неё ничего не назначаем.',
         note='Карточка PLP-001557 «Оксана Штойк Валид Пхт Plp Рабочий» к ней отношения не '
              'имеет: там наш рабочий номер 66955492587.'),
    dict(code='person_victoria', kind='человек', title='Виктория — ОКК, подрядчик',
         persona=None, is_internal=True, address_as='Виктория',
         phones=['380964647719'], tg_ids=[],
         purpose='Отдел контроля качества на подряде: слушает и проверяет разговоры.',
         can='Смотреть разговоры и оценивать качество.',
         cannot='Не клиент, по воронке не ведём.', note=None),
]

SUSPECT = ['PLP-001557', 'PLP-003133', 'PLP-003208', 'PLP-001555', 'PLP-004198',
           'PLP-001514', 'PLP-001463', 'PLP-004192', 'PLP-003490']


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


def main():
    have = {p['code'] for p in call('/system_participants?select=code')}
    print('ЖИВЫЕ ЛЮДИ В РЕЕСТРЕ\n')
    for p in PEOPLE:
        print('%-16s %-34s %s' % (p['code'], p['title'],
                                  'уже есть' if p['code'] in have else 'будет заведён'))
    print('\nПОДОЗРИТЕЛЬНЫЕ КАРТОЧКИ (наши номера и группы под видом клиентов):')
    for code in SUSPECT:
        r = call('/clients?code=eq.%s&select=code,name,phone,tg_id,is_internal' % code)
        if r:
            x = r[0]
            print('  %-11s %-38s тел=%-14s тг=%-10s свой=%s'
                  % (x['code'], str(x.get('name'))[:38], str(x.get('phone')),
                     str(x.get('tg_id')), x.get('is_internal')))
    if not APPLY:
        print('\nЭто отчёт. Завести людей: --apply')
        print('Карточки НЕ трогаю: слияние и переименование — только по твоему слову.')
        return 0
    for p in PEOPLE:
        if p['code'] in have:
            call('/system_participants?code=eq.%s' % p['code'], 'PATCH',
                 {k: v for k, v in p.items() if k != 'code'})
            print('  ✓ обновлён %s' % p['code'])
        else:
            call('/system_participants', 'POST', dict(p, active=True, visible_to_client=False))
            print('  ✓ заведён %s' % p['code'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
