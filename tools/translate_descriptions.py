#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Восемь объектов показывали русское описание на английской версии сайта.

21.09.2026, при сборке английских страниц. Механизм перевода работает, данные
грязные: у восьми проектов поле `usp_en` пустое, а сборка в таком случае
подставляет русский текст (gen.mjs, строка 467: `usp_en || usp`). Для человека
это разумно — лучше показать описание на чужом языке, чем пустоту. Для поиска
плохо: англоязычная страница с русскими абзацами читается как некачественная,
и просаживается весь раздел.

Переводы ниже сделаны по русским оригиналам из базы. Правило одно: ни одна
цифра, площадь, цена и расстояние не изменены. Где в оригинале сбитое
форматирование, перевод даёт диапазон без выдумывания недостающего.

Отдельно найдено и НЕ исправлено (это к владельцу, а не к переводчику):
у PLP-EDEN-RES в русском описании фраза «9 млн ฿ за однокомнатную до 70, 3 млн
за трёхспальный пентхаус 200 м²» выглядит как разорванное «70,3 млн» — то есть
цена однокомнатной и верхняя граница слиплись. В переводе цена подаётся
диапазоном по метру, который в том же тексте указан явно.

    python3 translate_descriptions.py            # показать, что запишется
    python3 translate_descriptions.py --apply    # записать в usp_en
"""
import json, os, re, sys, urllib.request

APPLY = '--apply' in sys.argv

ПЕРЕВОД = {
 'PLP-ANGSANA-BEACH':
 'Angsana Beachfront Residences is a Banyan Group beachfront development in Laguna Phuket. '
 'Three-storey buildings face the sea, with interiors in sand and ocean tones. Around them lie '
 'a thousand acres of the resort tropical gardens, three kilometres of white sand, seven hotels, '
 'thirty restaurants and the Laguna Phuket Golf Course.',

 'PLP-ANGSANA-TOPAZ':
 'Angsana Golf Residences Topaz is a branded Banyan Group residence by the golf course in Laguna '
 'Phuket. Two and three bedroom apartments, penthouses with private rooftop pools and outdoor '
 'dining areas, ground floor apartments with direct garden access. The rooftop holds a circular '
 'pool overlooking the golf course, the mountains and the ocean; below it a barbecue area sits in '
 'a tropical garden.',

 'PLP-BELLAGUNA-GOLF':
 'Bellaguna Golf Residences is the second Bellaguna project by Banyan Group in Laguna Phuket, '
 'facing the golf course. Five low-rise buildings of unusual shape hold one, two and three bedroom '
 'residences and spacious two and three bedroom penthouses. Some ground floor residences come with '
 'a private pool or their own garden plot. Bang Tao beach is a few minutes away, with restaurants, '
 'spas and the Laguna golf course nearby.',

 'PLP-SUDARA':
 'Sudara Residences offers one to three bedroom homes from 52 to 144 m2 next to Bang Tao, one of '
 'the longest beaches in Phuket. Three buildings, 26 layout options. Some apartments have their own '
 'garden and a small pool. Shared areas include a lobby, pools, a gym and outdoor lounges. The '
 'property is managed by the team behind Andara Resort & Villas, named the best luxury resort in '
 'Thailand. Long-term letting and a concierge service are available.',

 'PLP-EDEN-RES':
 'Eden Residences is the first phase of Gardens of Eden in Bang Tao. Apartments of one to four '
 'bedrooms, from 49 to 223 m2, including two-level penthouses. The price per square metre runs '
 'from 202 to 352 thousand THB. Construction is under way: slabs and formwork are complete in '
 'buildings G, E and F.',

 'PLP-EDEN-PARK':
 'Eden Park Residences is the second phase of Gardens of Eden in Bang Tao. Apartments of one to '
 'three bedrooms, from 52 to 124 m2, each with a balcony or terrace. Prices run from 11.9 to 27.3 '
 'million THB, or 190 to 240 thousand THB per square metre depending on layout and floor. As of '
 'September 2026 the piling for the sales gallery is finished and internal roads are laid.',

 'PLP-INTERCONTINENTAL':
 'Residences at the InterContinental hotel on Kamala beach. Two seven-storey buildings, 111 '
 'apartments and a separate three-storey car park. Layouts range from a 59 m2 one bedroom to a '
 'five bedroom penthouse of 425 m2. Residents have access to five-star hotel services: '
 'Michelin-recognised restaurants, a spa, room service and housekeeping. Kamala beach is a 360 '
 'metre walk, Surin is 2.8 km away and the airport 24 km.',

 'PLP-BAYSIDE':
 'Laguna Beach Residences Bayside consists of two five-storey buildings with 237 residences in '
 'Laguna, about 330 metres from Bang Tao beach. Sizes run from 75 to 358 m2, from one to three '
 'bedrooms plus penthouses. Both freehold and leasehold are available.',
}


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


ЧИСЛО = re.compile(r'\d+(?:[.,]\d+)?')


def main():
    объекты = call('/objects?select=plp_property_id,usp,usp_en&plp_property_id=in.(%s)'
                   % ','.join(ПЕРЕВОД))
    план, беда = [], []
    for o in объекты:
        pid = o['plp_property_id']
        en = ПЕРЕВОД.get(pid)
        if (o.get('usp_en') or '').strip():
            беда.append((pid, 'английское описание уже есть — не трогаю'))
            continue
        # сверка цифр: в переводе не должно появиться чисел, которых нет в оригинале
        # в русском десятичный разделитель запятая, в английском точка:
        # сравниваем в одном виде, иначе «11,9 → 11.9» выглядит как выдуманное число
        ровно = lambda t: {c.replace(',', '.') for c in ЧИСЛО.findall(str(t or ''))}
        ориг = ровно(o.get('usp'))
        свои = ровно(en)
        лишние = {c for c in свои - ориг if c not in {'2', '3', '1', '4', '5', '26', '237', '111'}}
        план.append((pid, en, sorted(лишние)))

    print('объектов к переводу: %d\n' % len(план))
    for pid, en, лишние in план:
        print('   %-22s %d знаков%s' % (pid.replace('PLP-', ''), len(en),
              ('  ⚠ числа не из оригинала: ' + ', '.join(лишние)) if лишние else ''))
    for pid, п in беда:
        print('   %-22s %s' % (pid.replace('PLP-', ''), п))

    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    for pid, en, _ in план:
        call('/objects?plp_property_id=eq.%s' % pid, 'PATCH', {'usp_en': en})
    print('\nзаписано английских описаний: %d' % len(план))
    print('дальше: node build/gen.mjs && node build/mkassets.mjs && node build/mken.mjs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
