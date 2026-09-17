#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Карточки купленных юнитов: наполнить от проекта и вывести на витрину.

Эльнур 17.09.2026: «посмотри, кто наши клиенты, что они купили, и размести их
объекты в блоке аренда… объекты клиентов выгружай сразу, будем зато видеть и будут
готовы постепенно к любому действию».

Что делает. По каждому юниту, купленному через нас (client_objects.rel = 'owns'),
берёт карточку проекта-родителя и переносит оттуда то, что у юнита и так общее:
снимки, район, пляж, тип жилья, что рядом, форму владения, координаты. Свои данные
юнита — площадь, число спален, цену покупки, срок передачи — НЕ выдумывает: они
приходят из договора (tools через client_docs) и уже записаны отдельно.

Чего сознательно не делает:
  • не придумывает площадь и спальни, если их нет в договоре — пустое поле честнее;
  • не публикует имя владельца и номер квартиры застройщика (сторож privacy_guard);
  • не ставит ставку аренды — её называет собственник.

Отметка о сроке ставится по проекту: «дом сдаётся в 1Q 2027 — принимаем брони
заранее» либо «сдан, заезд возможен сразу». Без неё карточка обещает то, чего нет.

    python3 tools/fill_client_units.py            # отчёт, что будет сделано
    python3 tools/fill_client_units.py --apply    # наполнить
    python3 tools/fill_client_units.py --apply --publish   # и вывести на витрину
"""
import json, os, sys, urllib.request

ENV = os.path.expanduser('~/.plp_site_supabase.env')
APPLY = '--apply' in sys.argv
PUBLISH = '--publish' in sys.argv

# поля, которые у юнита такие же, как у проекта: их перенос — не выдумка
FROM_PARENT = ('main_image_url', 'gallery_urls', 'photo_groups', 'district', 'beach',
               'distance_beach_m', 'distance_airport_km', 'lat', 'lng', 'coord_source',
               'nearby', 'amenities', 'type', 'ownership', 'developer', 'map_url',
               'rental_yield_min', 'rental_yield_max')


def creds():
    env = {}
    for line in open(ENV):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env['SUPABASE_URL'].rstrip('/') + '/rest/v1/', env['SUPABASE_SERVICE_KEY']


def main():
    base, key = creds()
    HG = {'apikey': key, 'Authorization': 'Bearer ' + key}
    HP = dict(HG, **{'Content-Type': 'application/json', 'Prefer': 'return=minimal'})

    def get(q):
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(base + q, headers=HG), timeout=60).read())

    def patch(pid, body):
        urllib.request.urlopen(urllib.request.Request(
            base + 'objects?plp_property_id=eq.' + pid,
            data=json.dumps(body, ensure_ascii=False).encode(),
            method='PATCH', headers=HP), timeout=60)

    objs = {o['plp_property_id']: o for o in get(
        'objects?select=*&limit=400')}
    bought = [c for c in get('client_objects?select=object_id,rel,handover_on&limit=300')
              if c.get('rel') == 'owns' and c.get('object_id') in objs]

    def quarter(d):
        if not d:
            return None
        y, m = int(str(d)[:4]), int(str(d)[5:7] or 1)
        return '%dQ %d' % ((m - 1) // 3 + 1, y)

    # порядковый номер юнита внутри своего проекта — по нему сдвигаем ленту кадров
    sibling_index, per_parent = {}, {}
    for c in sorted(bought, key=lambda x: x['object_id']):
        par_id = objs[c['object_id']].get('parent_object_id') or ''
        n = per_parent.get(par_id, 0)
        sibling_index[c['object_id']] = n
        per_parent[par_id] = n + 1

    done = pub = 0
    seen = set()
    print('%-22s %-34s %s' % ('юнит', 'проект', 'что переносим'))
    for c in bought:
        pid = c['object_id']
        if pid in seen:
            continue
        seen.add(pid)
        o = objs[pid]
        par = objs.get(o.get('parent_object_id') or '')
        if not par:
            print('%-22s %-34s родителя нет — пропускаю' % (pid, '—'))
            continue
        body = {}
        for f in FROM_PARENT:
            if not o.get(f) and par.get(f):
                body[f] = par[f]
        # 🔴 17.09 Эльнур: «ты можешь ставить разные фото на одинаковые юниты, чтобы
        # не выглядело стрёмно». У юнитов одного проекта лента общая, и десять карточек
        # Qabalah шли с одинаковой обложкой. Сдвигаем ленту по кругу на номер юнита:
        # снимки те же самые (других у нас нет), но обложка у каждого своя.
        gal = body.get('gallery_urls') or o.get('gallery_urls') or par.get('gallery_urls')
        if isinstance(gal, list) and len(gal) > 1:
            k = sibling_index.get(pid, 0) % len(gal)
            rot = gal[k:] + gal[:k]
            body['gallery_urls'] = rot
            body['main_image_url'] = rot[0]
        # срок передачи: у юнита свой, иначе проектный
        # 17.09: у Modeva E202 в записи покупки стояло 4Q 2026, а у самого дома — 1Q 2027.
        # Дом не может отдать юнит раньше, чем сдан сам: берём ПОЗДНЮЮ из двух дат,
        # иначе карточка обещает заезд раньше, чем будут ключи.
        cand = [d for d in (c.get('handover_on'), o.get('handover_date'),
                            par.get('handover_date')) if d]
        hand = max(str(d)[:10] for d in cand) if cand else None
        ready = str(par.get('stage') or '') in ('Ready',) or (
            hand and str(hand)[:10] <= '2026-09-17')
        note = ('Сдан, заезд возможен сразу. Даты подтверждаем у собственника.'
                if ready else
                ('Дом сдаётся в %s — принимаем брони заранее, заезд после передачи ключей.' % quarter(hand)
                 if hand else 'Срок передачи уточняем у застройщика — напишем точную дату в ответ на запрос.'))
        if o.get('stage_note') != note:
            body['stage_note'] = note
        # поле и отметка обязаны говорить одно и то же, иначе сторож карточек
        # честно ругается на собственную же надпись
        if hand and str(o.get('handover_date') or '')[:10] != hand:
            body['handover_date'] = hand
        if PUBLISH and not o.get('on_site'):
            body['on_site'] = True
            body['purpose'] = 'аренда'
        if not body:
            continue
        print('%-22s %-34s %s' % (pid, (par.get('name') or '')[:34],
                                  ', '.join(sorted(body))[:70]))
        if APPLY:
            patch(pid, body)
            done += 1
            if body.get('on_site'):
                pub += 1
    if APPLY:
        print('\nнаполнено карточек: %d, выведено на витрину: %d' % (done, pub))
        print('пересобрать сайт: node build/all.mjs')
    else:
        print('\nэто отчёт. Записать: --apply, вывести на витрину: --apply --publish')


if __name__ == '__main__':
    main()
