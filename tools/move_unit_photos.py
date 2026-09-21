#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Номер квартиры уезжал в мессенджер вместе с картинкой. Переносим снимки.

21.09.2026, находка сторожа витрины после того, как его научили смотреть не
только в тексты, но и в адреса. Два объекта:

    PLP-VIVI-A304 → страница /object/vivi-r3   снимки .../objects/PLP-VIVI-A304/...
    PLP-VIVI-A507 → страница /object/vivi-r5   снимки .../objects/PLP-VIVI-A507/...

Адрес страницы замаскирован правильно, а путь к фотографии — нет. Достаточно
навести курсор на картинку или отправить ссылку в WhatsApp, где рисуется
превью, и номер квартиры виден. Это то самое железное правило Эльнура: «у
кабалы не должны светиться реальные номера вилл».

Остальные 47 юнитов берут снимки из папки проекта (PLP-VIVI, PLP-AYANA) и
чисты. Эти два — исключение: у них своя папка, названная внутренним кодом.

Что делает скрипт: копирует файлы в хранилище под безопасным именем (папка по
публичному коду), переписывает ссылки в базе и только потом удаляет старые
копии. Порядок важен: сначала новое работает, потом убираем старое — иначе
между шагами карточка осталась бы без картинок.

    python3 move_unit_photos.py            # показать план
    python3 move_unit_photos.py --apply    # перенести
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
R2 = json.load(open(os.path.expanduser('~/.plp_r2.json')))


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
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def клиент():
    import boto3
    return boto3.client('s3', endpoint_url=R2['endpoint'],
                        aws_access_key_id=R2['access_key_id'],
                        aws_secret_access_key=R2['secret_access_key'],
                        region_name='auto')


def main():
    объекты = call('/objects?select=plp_property_id,public_code,gallery_urls,main_image_url,'
                   'photo_groups&on_site=eq.true&limit=300')
    план = []
    for o in объекты:
        внутр = o['plp_property_id']
        публ = o.get('public_code') or внутр
        if публ == внутр:
            continue                       # маски нет — этим занимается mask_unit_codes.py
        кадры = list(o.get('gallery_urls') or [])
        if o.get('main_image_url'):
            кадры.append(o['main_image_url'])
        пути = {u for u in кадры if '/objects/%s/' % внутр in str(u)}
        if пути:
            план.append((o, внутр, публ, sorted(пути)))

    print('объектов, у которых снимки лежат под внутренним кодом: %d\n' % len(план))
    for o, внутр, публ, пути in план:
        print('   %-22s папка %-22s → %-22s кадров %d'
              % (o['plp_property_id'], внутр, публ, len(пути)))
    if not план:
        print('засветов в путях к снимкам нет')
        return 0
    if not APPLY:
        print('\nЭто отчёт. Перенести: --apply')
        return 0

    s3 = клиент()
    bucket = R2['bucket']
    перенесено, к_удалению = 0, []
    for o, внутр, публ, пути in план:
        замена = {}
        for url in пути:
            ключ = url.split('.r2.dev/')[-1].split('?')[0]
            новый = ключ.replace('objects/%s/' % внутр, 'objects/%s/' % публ, 1)
            if ключ == новый:
                continue
            s3.copy_object(Bucket=bucket, Key=новый,
                           CopySource={'Bucket': bucket, 'Key': ключ})
            замена[url] = url.replace('objects/%s/' % внутр, 'objects/%s/' % публ, 1)
            к_удалению.append(ключ)
            перенесено += 1
        if not замена:
            continue
        тело = {}
        if o.get('gallery_urls'):
            тело['gallery_urls'] = [замена.get(u, u) for u in o['gallery_urls']]
        if o.get('main_image_url'):
            тело['main_image_url'] = замена.get(o['main_image_url'], o['main_image_url'])
        if o.get('photo_groups'):
            гр = json.loads(json.dumps(o['photo_groups']))
            for g in гр:
                if isinstance(g, dict) and isinstance(g.get('urls'), list):
                    g['urls'] = [замена.get(u, u) for u in g['urls']]
            тело['photo_groups'] = гр
        call('/objects?plp_property_id=eq.%s' % o['plp_property_id'], 'PATCH', тело)
        print('   ✓ %s: ссылок переписано %d' % (o['plp_property_id'], len(замена)))

    # старые копии убираем последними: сначала убеждаемся, что новые отдаются
    живых = 0
    for o, внутр, публ, пути in план:
        проба = sorted(пути)[0].replace('objects/%s/' % внутр, 'objects/%s/' % публ, 1)
        try:
            # 21.09: без заголовка браузера хранилище отвечает 403, и проверка
            # объявляла живые файлы мёртвыми — старые копии оставались на месте
            # вместе с номером квартиры в адресе.
            req = urllib.request.Request(проба, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req, timeout=30).read(64)
            живых += 1
        except Exception as ex:
            print('   ⚠ новый адрес не отвечает (%s) — старые копии НЕ удаляю' % str(ex)[:50])
            к_удалению = []
            break
    if к_удалению and живых == len(план):
        for ключ in к_удалению:
            s3.delete_object(Bucket=bucket, Key=ключ)
        print('\nстарых копий удалено: %d' % len(к_удалению))
    print('перенесено снимков: %d' % перенесено)
    print('дальше: node build/gen.mjs && node build/mkassets.mjs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
