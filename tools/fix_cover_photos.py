#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Главное фото объекта должно быть горизонтальным и показывать сам объект.

Эльнур 20.09.2026: «когда крутишь карточки, они как будто бы подвисают… на некоторые
объекты залиты странные фотки… или вид издалека здание, там даже не понятно, что
продаётся. Сверка полная!»

Разбор. Карточка каталога рассчитана на горизонтальный снимок. Когда главным стоит
вертикальный, браузер пересчитывает раскладку ряда на каждой такой карточке — отсюда и
рывки при прокрутке. Проверка всех ста главных фото нашла пять таких:

    PLP-PEYLAA      1800×2279   общий план издалека + «Image intended for marketing only»
    PLP-QABALAH-M1  1536×1920   бетонная стена и треугольник неба
    PLP-QABALAH-M2  1537×1920   то же
    PLP-QABALAH-M3  1536×1920   то же
    PLP-VIVI-A304   2000×1867   почти квадрат

Скрипт для каждого такого объекта ищет в его галерее горизонтальный снимок (ширина
больше высоты минимум в 1,25 раза) и ставит главным. Если в галерее горизонтальных нет,
объект попадает в список на досъёмку — выдумывать нечего.

    python3 fix_cover_photos.py            # показать, что заменится
    python3 fix_cover_photos.py --apply    # заменить главные фото
"""
import json, os, struct, sys, urllib.request

APPLY = '--apply' in sys.argv
МИН_ШИРИНА = 1000
МИН_ПРОПОРЦИЯ = 1.25


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


def размер(url):
    """Размер картинки по первым килобайтам, без скачивания целиком."""
    try:
        req = urllib.request.Request(url, headers={'Range': 'bytes=0-6000'})
        d = urllib.request.urlopen(req, timeout=20).read()
    except Exception:
        return None
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF:
            i += 1
            continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack('>HH', d[i + 5:i + 9])
            return (w, h)
        if m in (0xD8, 0xD9):
            i += 2
            continue
        try:
            i += 2 + struct.unpack('>H', d[i + 2:i + 4])[0]
        except Exception:
            return None
    return None


def главное_годится(r):
    if not r:
        return True          # не смогли измерить — не трогаем
    w, h = r
    return w >= МИН_ШИРИНА and (w / h) >= МИН_ПРОПОРЦИЯ


def main():
    o = call('/objects?select=plp_property_id,name,purpose,main_image_url,gallery_urls'
             '&main_image_url=not.is.null&limit=300')
    плохие = []
    for x in o:
        r = размер(x['main_image_url'])
        if not главное_годится(r):
            плохие.append((x, r))
    print('главных фото проверено: %d' % len(o))
    print('не годятся для карточки: %d\n' % len(плохие))

    # Порядок важен: сначала интерьер и фасад самого объекта, и только в конце общие
    # планы. Мастерплан и планировки главными не ставим — по ним не видно, что продаётся.
    ПОРЯДОК = ('interior', 'exterior', 'cover', 'facilities')
    ЗАПРЕТ = ('master', 'plans', 'plan', 'layout', 'site')

    def вес(url):
        u = url.lower()
        if any(('/%s/' % z) in u or z in u.rsplit('/', 1)[-1] for z in ЗАПРЕТ):
            return 99
        for i, г in enumerate(ПОРЯДОК):
            if ('/%s/' % г) in u:
                return i
        return len(ПОРЯДОК)

    план, досъёмка = [], []
    for x, r in плохие:
        замена = None
        галерея = sorted((x.get('gallery_urls') or []), key=вес)
        for url in галерея:
            if url == x['main_image_url'] or вес(url) == 99:
                continue
            rr = размер(url)
            if главное_годится(rr) and rr:
                замена = (url, rr)
                break
        w, h = r if r else (0, 0)
        if замена:
            план.append((x, замена))
            print('   %-20s %4dx%-4d → %dx%d  %s'
                  % (x['plp_property_id'][:20], w, h, замена[1][0], замена[1][1],
                     замена[0][-38:]))
        else:
            досъёмка.append(x)
            print('   %-20s %4dx%-4d → замены в галерее НЕТ, нужна съёмка'
                  % (x['plp_property_id'][:20], w, h))

    if not APPLY:
        print('\nЭто отчёт. Заменить: --apply')
        return 0
    for x, (url, _) in план:
        call('/objects?plp_property_id=eq.%s' % x['plp_property_id'], 'PATCH',
             {'main_image_url': url})
        print('  ✓ %s' % x['plp_property_id'])
    print('\nзаменено главных фото: %d' % len(план))
    if досъёмка:
        print('нужна съёмка или подбор фото: %s'
              % ', '.join(x['plp_property_id'] for x in досъёмка))
    return 0


if __name__ == '__main__':
    sys.exit(main())
