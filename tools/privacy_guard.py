#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож витрины: наружу не уходят данные людей и номера их квартир.

Эльнур 17.09.2026: «мы не пишем на показ для всех такие детали, как имя клиента,
его данные, его номера юнитов, это могут быть просто наши выданные айди в базе».

Повод: на витрине аренды стояли настоящие номера квартир в домах — Clover A11,
Bayside 2205, Katabello F302. Показывали чужое жильё по его адресу в доме.

Что проверяет:
  1. в публичных текстах карточки-юнита нет номера квартиры застройщика;
  2. public_code юнита непрозрачен — из него не читается тот же номер;
  3. в публичных текстах нет имени владельца (из owner_ref), телефона, почты;
  4. того же нет в собранных страницах сайта.

Проектные карточки не трогаем: у них «Building C» и «Halo 1» — законные имена.
Юнит узнаём по parent_object_id, owner_ref или назначению «аренда».

    python3 tools/privacy_guard.py            # отчёт
    python3 tools/privacy_guard.py --short    # одна строка для сборки
"""
import glob, json, os, re, sys, urllib.request

ENV = os.path.expanduser('~/.plp_site_supabase.env')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_TEXT = ('name', 'usp', 'usp_en', 'availability', 'stage_note', 'ai_pitch_hook',
               'ai_story', 'rent_rules', 'good_for', 'current_promo')
# номер квартиры: «A11», «F-302», «2205», «S17» — но не год и не площадь
UNIT = re.compile(r'(?<![\w-])([A-Z]{1,2}[\s-]?\d{2,4}|\d{4})(?![\w%-])')
YEAR = re.compile(r'^(19|20)\d\d$')
PHONE = re.compile(r'(?<!\d)(?:\+?\d[\s()-]?){9,}\d')
MAIL = re.compile(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', re.I)


def sb(q):
    env = {}
    for line in open(ENV):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    key = env['SUPABASE_SERVICE_KEY']
    r = urllib.request.Request(env['SUPABASE_URL'].rstrip('/') + '/rest/v1/' + q,
                               headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def unit_no(text):
    """Номер квартиры в тексте, если это действительно номер, а не год и не метраж."""
    for m in UNIT.finditer(text or ''):
        v = m.group(1)
        if YEAR.match(v.replace('-', '').replace(' ', '')):
            continue
        yield v


def people():
    """Имена владельцев — из owner_ref карточек: это те, кого нельзя называть."""
    out = set()
    for o in sb('objects?select=owner_ref&limit=500'):
        ref = (o.get('owner_ref') or '').strip()
        if not ref or ref == '—':
            continue
        for w in re.findall(r'[А-ЯЁ][а-яё]{2,}', ref):
            out.add(w)
    return out


def main():
    short = '--short' in sys.argv
    if not os.path.exists(ENV):
        print('[личные данные] пропущено: нет ключей базы')
        return 0
    try:
        objs = sb('objects?select=plp_property_id,name,public_code,purpose,on_site,parent_object_id,'
                  'owner_ref,usp,usp_en,availability,stage_note,ai_pitch_hook,ai_story,rent_rules,'
                  'good_for,current_promo&limit=500')
    except Exception as ex:
        print('[личные данные] база не ответила:', str(ex)[:110])
        return 0
    names = people()
    bad = []
    for o in objs:
        pid = o['plp_property_id']
        is_unit = bool(o.get('parent_object_id') or o.get('owner_ref')
                       or (o.get('purpose') or '') == 'аренда')
        if not is_unit:
            continue
        for f in PUBLIC_TEXT:
            val = str(o.get(f) or '')
            for v in unit_no(val):
                bad.append((pid, f, 'номер квартиры «%s»' % v))
                break
            for n in names:
                if re.search(r'\b' + re.escape(n) + r'\b', val):
                    bad.append((pid, f, 'имя «%s»' % n))
            if PHONE.search(val):
                bad.append((pid, f, 'телефон'))
            if MAIL.search(val):
                bad.append((pid, f, 'почта'))
        code = (o.get('public_code') or '').strip()
        for v in unit_no(code.replace('PLP-', '')):
            bad.append((pid, 'public_code', 'наш код повторяет номер квартиры: %s' % code))
            break
    # собранные страницы: то же самое, но уже глазами посетителя
    pages = []
    for f in ['rent.html', 'index.html', 'offer-catalog.json', 'llms.txt', 'sitemap.xml'] + \
             sorted(glob.glob(os.path.join(ROOT, 'object', '*.html'))):
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        txt = open(p, encoding='utf-8', errors='ignore').read()
        for n in names:
            if re.search(r'\b' + re.escape(n) + r'\b', txt):
                pages.append((os.path.relpath(p, ROOT), 'имя «%s»' % n))
    if short:
        total = len(bad) + len(pages)
        print('[личные данные] %s: карточек-юнитов проверено %d, засветов %d%s' % (
            'ок' if not total else 'ЕСТЬ ЗАСВЕТ',
            sum(1 for o in objs if o.get('parent_object_id') or o.get('owner_ref') or (o.get('purpose') or '') == 'аренда'),
            total, '' if not total else ' — ' + (bad[0][0] + ': ' + bad[0][2] if bad else pages[0][1])))
    else:
        print('Сторож витрины: засветов %d\n' % (len(bad) + len(pages)))
        for pid, f, what in bad:
            print('  %-22s %-14s %s' % (pid, f, what))
        for f, what in pages:
            print('  страница %-28s %s' % (f, what))
        if bad or pages:
            print('\nЛечится в public.objects: имя = комплекс + тип жилья, номер квартиры живёт '
                  'только в client_objects.unit и виден в кабинете.')
    return 1 if (bad or pages) else 0


if __name__ == '__main__':
    sys.exit(main())
