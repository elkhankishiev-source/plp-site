#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка карточки объекта с самой собой: поля против описания.

Эльнур 16.09.2026: «страница объекта должна быть богаче карточки, но точно без расхождений».
Повод: у Heritage в полях «сдан в декабре 2025, от 5,53 млн», а в описании «завершение
в первом квартале 2026, от 5,05 млн».

Что сверяет по каждому объекту (источник — Supabase public.objects):
  • срок сдачи: год и квартал из описания против handover_date;
  • стадия: слова «сдан / строится / старт продаж» в описании против stage;
  • цена «от»: число из описания против price_from_thb (допуск 5%);
  • спальни и площади: диапазоны из описания против bedrooms_min/max и area_min/max.

Ничего не правит — печатает список. Запуск:
    python3 tools/object_consistency.py            # отчёт
    python3 tools/object_consistency.py --short    # одна строка (для сборки)
"""
import json, os, re, sys, urllib.request

ENV = os.path.expanduser('~/.plp_site_supabase.env')
Q = ('plp_property_id,name,usp,usp_en,ai_pitch_hook,ai_story,stage_note,'
     'handover_date,stage,status,price_from_thb,price_to_thb,'
     'bedrooms_min,bedrooms_max,area_min,area_max,on_site,current_promo')
# 16.09: на сайте четыре группы продажи — старт продаж, строится, готово к заезду,
# вторичка. Сторож сверяет описание с группой, а не с сырым словом стадии: «анонсирован»
# и «старт продаж» — одна полка, спорить им не о чем.
STAGE_GROUP = {'Ready': 'ready', 'Construction': 'construction', 'Pre-sale': 'presale',
               'Announced': 'presale', 'Resale': 'resale', 'Sold out': 'resale'}
GROUP_RU = {'ready': 'готово к заезду', 'construction': 'строится',
            'presale': 'старт продаж', 'resale': 'вторичка'}
GROUP_WORDS = {
    'ready':        r'сдан\w*|готов\w* к заезду|готовое жиль|введ[её]н в эксплуатац',
    'construction': r'строится|идёт строительство|в стадии строительства',
    'presale':      r'старт продаж|пресейл|предпродаж',
    'resale':       r'вторичн\w*|вторичк\w*|перепродаж\w*|переуступ\w*',
}
# что друг другу не противоречит: пресейл — это та же стройка, вторичка почти всегда
# уже готова, а распроданный у застройщика проект и есть вторичный рынок
OK_PAIRS = {('presale', 'construction'), ('construction', 'presale'),
            ('resale', 'ready'), ('ready', 'resale')}


def sb():
    env = {}
    for line in open(ENV):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    url = env['SUPABASE_URL'].rstrip('/') + '/rest/v1/objects?select=' + Q + '&on_site=eq.true'
    key = env['SUPABASE_SERVICE_KEY']
    r = urllib.request.Request(url, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def money_in(text):
    """Цены из текста — только там, где рядом сказано, что это цена.

    Без этого в «цену» попадали площадь участка в млн, бюджет проекта и прочие числа:
    у Legendary «700 млн» — это не цена квартиры."""
    out = []
    PRICE_NEAR = r'(?:цен\w*|стоимост\w*|от|начина\w*|price|from|start\w*|starts?\s+at)\W{0,18}'
    for m in re.finditer(PRICE_NEAR + r'(\d[\d\s.,]{2,})\s*(млн|миллион\w*|m\b|thb|бат|฿)', text, re.I):
        raw = m.group(1).replace(' ', '').replace(' ', '')
        unit = m.group(2).lower()
        try:
            val = float(raw.replace(',', '.')) if raw.count('.') + raw.count(',') <= 1 else float(raw.replace('.', '').replace(',', '.'))
        except ValueError:
            continue
        if unit.startswith(('млн', 'миллион', 'm')):
            val *= 1_000_000
        if val >= 300_000:
            out.append(val)
    return out


HAND_NEAR = r'(?:сдач\w*|сда[её]тся|сдан\w*|заверш\w*|готовност\w*|ввод\w*|handover|completion|ready|delivery)'

# 16.09: в одном предложении живут две даты — «строительство началось в июле 2025,
# завершение — декабрь 2026». Сторож брал первую и пять раз кричал на верные карточки.
# Кусок про НАЧАЛО стройки вырезаем: срок сдачи ищем только в остатке.
START_RE = re.compile(
    r'(?:строительств\w*|стройк\w*|construction)[^.;]{0,25}?'
    r'(?:начал\w*|стартовал\w*|started|began|start)\w*[^.;,]{0,45}|'
    r'\bconstruction\s+(?:[a-z\u0430-\u044f]{3,10}\.?\s+)?20[2-3]\d\s*(?:\u2192|->|-|\u2014)',
    re.I)


def handover_text(text):
    """Текст без упоминаний о начале стройки — в нём ищем срок сдачи."""
    return START_RE.sub(' ', text)


def years_in(text):
    """Год сдачи — только рядом со словами о сдаче: иначе год награды или основания
    компании читается как срок (Heritage: «награда 2024 года»)."""
    out = set()
    for m in re.finditer(HAND_NEAR + r'[^.;]{0,60}?\b(20[2-3]\d)\b|\b(20[2-3]\d)\b[^.;]{0,25}?' + HAND_NEAR, text, re.I):
        out.add(int(m.group(1) or m.group(2)))
    return out


def quarters_in(text):
    """Квартал сдачи — тоже только в предложении про сдачу."""
    q = set()
    for sent in re.split(r'[.;]\s*', text):
        if not re.search(HAND_NEAR, sent, re.I):
            continue
        for m in re.finditer(r'\b([1-4])\s*[- ]?\s*(?:q|кв(?:артал\w*)?)\b|\bq\s*([1-4])\b', sent, re.I):
            q.add(int(m.group(1) or m.group(2)))
        for w, n in {'перв': 1, 'втор': 2, 'трет': 3, 'четверт': 4}.items():
            if re.search(w + r'\w*\s+квартал', sent, re.I):
                q.add(n)
    return q


# 16.09: в одном проекте бывают две линейки — виллы и коммерция (Casa de Monte).
# Предложение про коммерцию говорит о СВОЁМ метраже и своей цене: это не спор с полями.
OTHER_LINE = re.compile(r'коммерч|commercial|торгов\w*\s+помещ|офисн\w*|shophouse', re.I)


def check(o):
    bad = []
    # 🔴 17.09: сторож читал только usp и usp_en и печатал «расхождений 0», пока
    # в ai_pitch_hook и ai_story у Heritage стояло «сдача Q1 2026» и «1BR от 5.05M»,
    # а у Kirara — «Completion Q2 2026». Эти поля читает мозг двойника: именно из них
    # клиенту уезжали протухшие сроки и цены. Теперь они сверяются наравне с описанием.
    parts = [str(o.get('usp') or ''), str(o.get('usp_en') or ''),
             str(o.get('ai_pitch_hook') or ''), str(o.get('ai_story') or ''),
             str(o.get('stage_note') or '')]
    keep = []
    for part in parts:
        keep.append(' '.join(s for s in re.split(r'(?<=[.;])\s+', part) if not OTHER_LINE.search(s)))
    txt = ' '.join(keep)
    if not txt.strip():
        return bad
    pid = o['plp_property_id']
    hd = (o.get('handover_date') or '')[:10]
    if hd:
        y, m = int(hd[:4]), int(hd[5:7] or 1)
        htxt = handover_text(txt)
        ys = years_in(htxt)
        if ys and y not in ys and all(abs(v - y) >= 1 for v in ys):
            bad.append((pid, 'срок сдачи', 'в полях %s' % hd, 'в описании %s' % ', '.join(map(str, sorted(ys)))))
        qs = quarters_in(htxt)
        qf = (m - 1) // 3 + 1
        if qs and qf not in qs and (not ys or y in ys):
            bad.append((pid, 'квартал сдачи', 'в полях %dQ %d' % (qf, y), 'в описании %s' % ', '.join('%dQ' % x for x in sorted(qs))))
    grp = STAGE_GROUP.get(o.get('stage'))
    if grp:
        found = [g for g, w in GROUP_WORDS.items()
                 if g != grp and (grp, g) not in OK_PAIRS and re.search(w, txt, re.I)]
        if found and not re.search(GROUP_WORDS[grp], txt, re.I):
            bad.append((pid, 'стадия', 'в полях «%s»' % GROUP_RU[grp],
                        'в описании «%s»' % GROUP_RU[found[0]]))
    pf = o.get('price_from_thb')
    prices = money_in(txt)
    if pf and prices:
        lo = min(prices)
        if abs(lo - pf) > pf * 0.05:
            f = lambda v: ('%.2f' % (v / 1e6)).rstrip('0').rstrip('.') + ' млн ฿'
            bad.append((pid, 'цена «от»', 'в полях ' + f(pf), 'в описании ' + f(lo)))
    # 🔴 17.09 Эльнур: «фантазия равай скидки 1 млн — грубая ошибка, такие штуки
    # вообще убирай везде». На витрине как «акции» стояли: заглушка «[нужно от
    # Эльнура]», заметки «уточнить у застройщика», догадки с пометкой (estimated),
    # акция со сроком до 31.10.2025 и «цена со скидкой 5 700 000» на карточке,
    # где написано «от 3 570 000». Одиннадцать штук.
    promo = str(o.get('current_promo') or '').strip()
    if promo:
        if re.search(r'нужно от|уточнить|запросить|todo|\[|по договорённости', promo, re.I):
            bad.append((pid, 'акция', 'заглушка на витрине', promo[:60]))
        elif re.search(r'\(estimated\)|предположительно', promo, re.I):
            bad.append((pid, 'акция', 'догадка, не подтверждено', promo[:60]))
        else:
            md = re.search(r'скидк\w*\s+([\d\s]{6,})\s*฿', promo)
            mp = re.search(r'цена\s+([\d\s]{6,})\s*฿', promo, re.I)
            if md and mp and pf:
                price = int(re.sub(r'\D', '', mp.group(1)))
                if price > pf * 1.2:
                    bad.append((pid, 'акция', 'цена со скидкой %s' % price, 'а в карточке «от %s»' % int(pf)))
    bmin, bmax = o.get('bedrooms_min'), o.get('bedrooms_max')
    mb = re.search(r'от\s+(\d)\s*до\s+(\d)\s+спал|(\d)\s*[–-]\s*(\d)\s*(?:сп|спал|br\b)', txt, re.I)
    if mb and bmin and bmax:
        a, b = (int(mb.group(1) or mb.group(3)), int(mb.group(2) or mb.group(4)))
        if (a, b) != (bmin, bmax):
            bad.append((pid, 'спальни', 'в полях %d–%d' % (bmin, bmax), 'в описании %d–%d' % (a, b)))
    amin, amax = o.get('area_min'), o.get('area_max')
    ma = re.search(r'от\s+(\d{2,4})\s*до\s+(\d{2,4})\s*(?:квадратных метров|м²|м2|sqm|m²)', txt, re.I)
    if ma and re.search(r'участ\w*|land|plot|территор\w*', txt[max(0, ma.start() - 90):ma.start()], re.I):
        ma = None          # это про участок, а не про площадь жилья
    if ma and amin and amax:
        a, b = int(ma.group(1)), int(ma.group(2))
        if abs(a - amin) > max(2, amin * 0.05) or abs(b - amax) > max(2, amax * 0.05):
            bad.append((pid, 'площади', 'в полях %g–%g м²' % (amin, amax), 'в описании %d–%d м²' % (a, b)))
    return bad


def main():
    short = '--short' in sys.argv
    if not os.path.exists(ENV):
        print('[карточки] пропущено: нет ключей базы (~/.plp_site_supabase.env)')
        return 0
    try:
        objs = sb()
    except Exception as ex:
        print('[карточки] база не ответила:', str(ex)[:120])
        return 0
    rows = []
    for o in objs:
        rows += check(o)
    if short:
        print('[карточки] %s: объектов %d, расхождений %d%s' % (
            'ок' if not rows else 'ЕСТЬ РАСХОЖДЕНИЯ', len(objs), len(rows),
            '' if not rows else ' — ' + rows[0][0] + ': ' + rows[0][1]))
    else:
        print('Сверка описания с полями: объектов %d, расхождений %d\n' % (len(objs), len(rows)))
        w = max([len(r[0]) for r in rows] + [10])
        for pid, what, a, b in rows:
            print('  %-*s %-14s %-28s %s' % (w, pid, what, a, b))
        if rows:
            print('\nПравится в базе (public.objects): поле или текст usp — по первоисточнику застройщика.')
    return 1 if rows else 0


if __name__ == '__main__':
    sys.exit(main())
