#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реальные ставки аренды из Telegram-каналов — чтобы сверить наши ориентиры.

Эльнур 21.09.2026: «объекты аренды без ставки — потому что они ещё строятся,
поэтому надо ставить примерную цену для характерного объекта, который уже
работает в этой же локации рядом… инф искать вкл парсинг тг каналов».

Ориентир по району мы уже показываем — он считается из rental_benchmarks
(ставка за м² по району и типу, собрана по ADR AirDNA, листингам Airbnb, Agoda,
Booking и отчётам Knight Frank). Но это кабинетная оценка. Здесь берём живой
рынок: что прямо сейчас сдают в каналах Пхукета и почём.

Источник — каналы, на которые подписан рабочий аккаунт. Только чтение: ничего
не публикуем, никому не пишем, ни на что не отвечаем.

Что делает:
  • читает объявления об аренде за последние N дней;
  • достаёт из текста район, тип жилья, число спален и ставку в месяц;
  • считает медиану по связке «район + тип + спальни»;
  • сравнивает с нашим ориентиром и показывает расхождение.

Чего НЕ делает: ничего не пишет в базу. Решение, менять ли ориентир, за
человеком — объявления бывают завышенными, а бывают и приманкой.

    python3 tg_rent_rates.py              # за 30 дней, отчёт
    python3 tg_rent_rates.py --days 90    # глубже
"""
import asyncio, json, os, re, statistics, sys, urllib.request
from collections import defaultdict

ДНЕЙ = 30
if '--days' in sys.argv:
    ДНЕЙ = int(sys.argv[sys.argv.index('--days') + 1])

КАНАЛЫ = ['Пхукет - Аренда - Недвижимость', 'Барахолка Пхукет Жилье',
          'Недвижимость Пхукет', 'Пхукет 📢 Объявления', 'Недвижа',
          'Переуступки Пхукет | Вторичка | Недвижимость |']

РАЙОНЫ = {
    'Bang Tao': ('банг тао', 'бангтао', 'bang tao', 'bangtao', 'лагун', 'laguna'),
    'Layan': ('лаян', 'layan'), 'Surin': ('сурин', 'surin'),
    'Kamala': ('камала', 'kamala'), 'Rawai': ('раваи', 'равай', 'rawai'),
    'Kata': ('ката', 'kata'), 'Karon': ('карон', 'karon'),
    'Nai Harn': ('най харн', 'найхарн', 'nai harn'),
    'Nai Yang': ('най янг', 'найянг', 'nai yang'),
    'Patong': ('патонг', 'patong'), 'Cherng Talay': ('черн талай', 'cherng talay'),
    'Koh Kaew': ('ко кео', 'koh kaew'), 'Thalang': ('таланг', 'thalang'),
    'Chalong': ('чалонг', 'chalong'), 'Mai Khao': ('май као', 'mai khao'),
}

ВИЛЛА = re.compile(r'(вилл|villa|дом\b|house\b|таунха|townhouse)', re.I)
КОНДО = re.compile(r'(кондо|condo|апарт|apartment|студи|studio|квартир)', re.I)
СПАЛЬНИ = re.compile(r'(\d+)\s*[- ]?\s*(?:спал|bed|br\b|bd\b|ком)', re.I)
# площадь: «120 м2», «120 кв.м», «120 sqm», «120 m²»
ПЛОЩАДЬ = re.compile(r'(\d{2,4})\s*(?:м2|м²|кв\.?\s*м|sq\.?m|sqm|m2|m²)', re.I)
# 120’000 · 120 000 · 120000 · 120к · 120k · 120 тыс
ЦЕНА = re.compile(r'(\d{1,3}(?:[ ’ \',.]\d{3})+|\d{2,3})\s*(?:к\b|k\b|тыс|000)?\s*'
                  r'(?:бат|฿|thb|baht)?', re.I)
МЕСЯЦ = re.compile(r'(в\s*месяц|/\s*мес|мес\b|month|/mo|годов|annual|long|длительн)', re.I)
СУТКИ = re.compile(r'(сутк|ноч|/\s*день|per night|nightly|в день)', re.I)


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


def наш_ориентир():
    """Ставка за м² по району и типу — то, из чего витрина считает ориентир."""
    E = env()
    url = E['SUPABASE_URL'].rstrip('/') + '/rest/v1/rental_benchmarks?select=district,unit_type,rate_sqm_low,rate_sqm_high&limit=50'
    r = urllib.request.Request(url, headers={'apikey': E['SUPABASE_SERVICE_KEY'],
                                             'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']})
    try:
        return json.load(urllib.request.urlopen(r, timeout=60))
    except Exception:
        return []


def цена_из(текст):
    """Ставка в батах за месяц. Посуточные и слишком мелкие числа отбрасываем."""
    if СУТКИ.search(текст) and not МЕСЯЦ.search(текст):
        return None
    лучшие = []
    for m in ЦЕНА.finditer(текст):
        сырое = m.group(1)
        чисто = re.sub(r'[ ’ \',.]', '', сырое)
        if not чисто.isdigit():
            continue
        v = int(чисто)
        хвост = текст[m.end():m.end() + 6].lower()
        if len(чисто) <= 3 and ('к' in хвост or 'k' in хвост or 'тыс' in хвост):
            v *= 1000
        if 8000 <= v <= 900000:          # месячная аренда на Пхукете живёт в этих рамках
            лучшие.append(v)
    return min(лучшие) if лучшие else None


def разобрать(текст):
    t = текст.lower()
    район = next((r for r, слова in РАЙОНЫ.items() if any(w in t for w in слова)), None)
    if not район:
        return None
    тип = 'Вилла' if ВИЛЛА.search(t) else ('Кондо' if КОНДО.search(t) else None)
    if not тип:
        return None
    ц = цена_из(текст)
    if not ц:
        return None
    сп = СПАЛЬНИ.search(t)
    пл = ПЛОЩАДЬ.search(t)
    площадь = int(пл.group(1)) if пл else None
    if площадь and not (20 <= площадь <= 2000):
        площадь = None
    return {'район': район, 'тип': тип, 'спален': int(сп.group(1)) if сп else None,
            'цена': ц, 'площадь': площадь}


async def собрать():
    from telethon import TelegramClient
    import datetime
    creds = json.load(open(os.path.expanduser('~/.tg_creds.json')))
    cl = TelegramClient(os.path.expanduser('~/.tg_session'),
                        int(creds['api_id']), creds['api_hash'])
    await cl.start()
    цели = {}
    async for d in cl.iter_dialogs(limit=400):
        имя = str(d.name or '').strip()
        if имя in КАНАЛЫ:
            цели[имя] = d.entity
    порог = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ДНЕЙ)
    найдено, прочитано = [], 0
    for имя, ent in цели.items():
        n = 0
        async for msg in cl.iter_messages(ent, limit=1500):
            if msg.date and msg.date < порог:
                break
            t = (msg.message or '').strip()
            прочитано += 1
            if len(t) < 40:
                continue
            r = разобрать(t)
            if r:
                r['канал'] = имя
                найдено.append(r)
                n += 1
        print('   %-46s объявлений со ставкой: %d' % (имя[:46], n))
    await cl.disconnect()
    return найдено, прочитано


def main():
    print('читаю каналы за %d дней (только чтение, ничего не публикуем)\n' % ДНЕЙ)
    найдено, прочитано = asyncio.run(собрать())
    print('\nпросмотрено сообщений: %d, распознано ставок: %d\n' % (прочитано, len(найдено)))
    if not найдено:
        print('ставок не набралось — возможно, изменился вид объявлений')
        return 0

    по = defaultdict(list)
    for r in найдено:
        по[(r['район'], r['тип'])].append(r['цена'])

    бенч = {(b['district'], b['unit_type']): b for b in наш_ориентир()}
    print('%-14s %-7s %5s %10s %10s %10s  %8s  %-11s'
          % ('район', 'тип', 'шт', 'медиана', 'нижняя', 'верхняя', 'рынок/м²', 'наш ор./м²'))
    for (район, тип), цены in sorted(по.items(), key=lambda x: -len(x[1])):
        if len(цены) < 3:
            continue
        мед = int(statistics.median(цены))
        низ, верх = min(цены), max(цены)
        b = бенч.get((район, тип))
        # прямое сравнение возможно только в одних единицах: считаем рыночную
        # ставку за метр по тем объявлениям, где указана площадь
        сметром = [r for r in найдено if r['район'] == район and r['тип'] == тип and r.get('площадь')]
        рын_м2 = int(statistics.median([r['цена'] / r['площадь'] for r in сметром])) if len(сметром) >= 3 else None
        ор = ('%s–%s' % (b['rate_sqm_low'], b['rate_sqm_high'])) if b else '—'
        оценка = ''
        if рын_м2 and b:
            низк = int(b['rate_sqm_low'])
            if рын_м2 < низк * 0.7:
                оценка = '  ⚠ наш ориентир выше рынка'
            elif рын_м2 > int(b['rate_sqm_high']) * 1.3:
                оценка = '  ⚠ наш ориентир ниже рынка'
            else:
                оценка = '  сходится'
        print('%-14s %-7s %5d %10s %10s %10s  %8s  %-11s%s'
              % (район, тип, len(цены), f'{мед:,}'.replace(',', ' '),
                 f'{низ:,}'.replace(',', ' '), f'{верх:,}'.replace(',', ' '),
                 (str(рын_м2) if рын_м2 else '—'), ор, оценка))

    print('\nЭто рынок объявлений: цены в нём бывают завышены и бывают приманкой.')
    print('В базу ничего не записано — сверьте с нашим ориентиром и решите сами.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
