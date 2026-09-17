#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Термшиты Banyan Group (Laguna) → цены и планировки карточки.

Эльнур 17.09.2026: «У лагуны на Гугл диске есть вся информация, цены и файлы — тут цены
<папка Dropbox>, тут все проекты <папка Диска>».

Откуда берём. У Banyan Group цены живут не в канале и не в папке проекта, а одной
папкой термшитов: по файлу на корпус, в имени файла — дата прайса. Поэтому отдельный
вход, но выход — общий: units → tg_prices.summarize() → та же запись в карточку,
тот же предохранитель ±25%, те же price_tiers и unit_types.

Что важно в этих таблицах:
  • RESERVED / SOLD — юнита уже нет. Цена «от» считается только по свободным строкам;
  • спец-кампания даёт по тому же юниту ВТОРУЮ цену — живая именно она (сверено
    по 19 юнитам Hibiscus и Garrya: спеццена ниже обычной в 19 случаях из 19);
  • взнос за бронирование (100 000 … 1 000 000 ฿) стоит отдельной строкой и в первой
    версии читался как цена лота — отсюда было «от 1 000 000» у семи проектов;
  • «3-PH» — пентхаус. На Katabello пентхаусы, свёрнутые в обычные спальни, дали
    «три спальни дешевле двух»; здесь они идут отдельным тиром.

    python3 tools/laguna_prices.py            # отчёт было → станет
    python3 tools/laguna_prices.py --apply    # записать в public.objects
    python3 tools/laguna_prices.py --fetch    # заново скачать папку прайсов
"""
import datetime, glob, io, json, os, re, sys, urllib.request, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_prices as TP

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/.plp_laguna_prices')
DROPBOX = ('https://www.dropbox.com/scl/fo/6df5l8bdcoj1y7vor9agm/'
           'AE545ci08HqioW30ZFpSGPU?rlkey=01fgix4dpc3filjccjbiywuaw&dl=1')
DRIVE = 'https://drive.google.com/drive/folders/1TiY3RGpfhlHh4Xc6vDd9lF6kMwfnKtrv'
APPLY = '--apply' in sys.argv
FETCH = '--fetch' in sys.argv
FORCE = '--force' in sys.argv

# Карточка ← какие термшиты её описывают. Один проект = несколько корпусов и фаз.
MAP = {
    'PLP-ANGSANA-BEACH':  ['ANBR Termsheet'],
    'PLP-ANGSANA-TOPAZ':  ['Angsana Golf Residences Topaz'],
    'PLP-BELLAGUNA-GOLF': ['Bellaguna Golf Residences', 'Special Campaign LGR Hisbuscus'],
    'PLP-BELLAGUNA':      ['Bellaguna Lake Residences'],
    'PLP-GARRYA':         ['Residences at Garrya', 'Special Campaign Garrya'],
}
# Есть прайс — карточки нет. Печатаем в конце отчёта, заводим только по «го».
NOCARD = {
    'Laguna Beach Residences Bayside':   ['Laguna Beach Residences Bayside'],
    'Laguna Beach Residences Seashore':  ['Laguna Beach Residences Seashore', 'Special Campaign LBR Seashore'],
    'Laguna Lake Residences Aster':      ['Laguna Lake Residences Aster'],
    'Lakelands Waterfront Villas':       ['Lakelands Waterfront Villas'],
    'Lakelands Waterside Residences':    ['Lakelands Waterside Residences'],
    'Sky Park Aurora & Celeste':         ['Sky Park Aurora'],
    'Sky Park Elara':                    ['Sky Park Elara', 'Special Campaign Skypark Elara'],
    'Angsana Oceanview Residences':      ['ANOV '],
    'Banyan Tree Beach Residences':      ['Banyan Tree Beach Residences', 'Special Campaign BTBR'],
    'Yara Residences':                   ['Yara Residences'],
}
# Сичон — другая провинция, не наш рынок.
SKIP = ['BTRS-Price-List']

PRICE = r'(?:[\d,]{9,}|RESERVED|SOLD(?:\s+OUT)?)'
FLAT = re.compile(
    r'\b(\d{3,4})\s+([1-5])(-PH)?\s+((?:\d{2,4}\s+){1,3})(?:Thai\s+)?(FH|LH)\s+'
    r'((?:[A-Za-z]+\s+){0,4})((?:[\d,]{9,}\s+)?' + PRICE + r')(?![\d,])')
VILLA = re.compile(r'\b(\d{1,3})\s+([1-5])\s+(\d{3,4})\s+((?:\d{2,4}\s+){1,3})(' + PRICE + r')(?![\d,])')
BARE = re.compile(r'\b(\d{3,4})\s+([1-5])(-PH)?\s+((?:\d{2,4}(?:\.\d\d)?\s+){2,4})(' + PRICE + r')(?![\d,])')


def fetch():
    """Папка термшитов одним архивом. Без ключей: ссылка «поделиться» + dl=1."""
    os.makedirs(CACHE, exist_ok=True)
    req = urllib.request.Request(DROPBOX, headers={'User-Agent': 'Mozilla/5.0'})
    blob = urllib.request.urlopen(req, timeout=300).read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    n = 0
    for m in z.namelist():
        if m.lower().endswith('.pdf'):
            open(os.path.join(CACHE, os.path.basename(m)), 'wb').write(z.read(m))
            n += 1
    print('скачано термшитов: %d → %s' % (n, CACHE))
    return n


def sheet_date(name):
    m = re.search(r'(20\d{2})(\d{2})(\d{2})', name)
    return '%s-%s-%s' % m.groups() if m else '0000-00-00'


def _price(tok):
    """Спец-цена идёт второй колонкой. RESERVED после цены означает, что юнита нет."""
    if re.search(r'RESERVED|SOLD', tok, re.I):
        return None
    nums = re.findall(r'[\d,]{9,}', tok)
    return int(nums[-1].replace(',', '')) if nums else None


def lots_of(path):
    """Строки таблицы → юниты в формате tg_prices (status/price/area/beds/ph/code)."""
    import fitz
    out, seen = [], set()
    for page in fitz.open(path):
        lines = {}
        for x in page.get_text('words'):
            lines.setdefault(round(x[1] / 4), []).append((x[0], x[4]))
        for k in sorted(lines):
            line = ' '.join(t for _, t in sorted(lines[k]))
            hits = [(m, 'flat') for m in FLAT.finditer(line)]
            if not hits:
                hits = [(m, 'villa') for m in VILLA.finditer(line)]
            if not hits:
                hits = [(m, 'bare') for m in BARE.finditer(line)]
            for m, kind in hits:
                if kind == 'flat':
                    unit, beds, ph, areas, _own, _fit, price = m.groups()
                    ar = [float(x) for x in areas.split()]
                    area = ar[0]
                elif kind == 'bare':
                    unit, beds, ph, areas, price = m.groups()
                    area = float(areas.split()[0])
                else:
                    unit, beds, land, built, price = m.groups()
                    ph = None
                    if not (100 <= float(land) <= 3000):
                        continue
                    area = float(built.split()[-1])
                if unit in seen:
                    continue
                p = _price(price)
                if p and not (40_000 <= p / area <= 2_500_000):
                    continue        # цена за метр вне здравого смысла — строка не про лот
                seen.add(unit)
                out.append({'code': unit, 'beds': int(beds), 'ph': bool(ph), 'area': area,
                            'price': p, 'status': 'available' if p else 'sold'})
    return out


def sheets(pats):
    got = []
    for f in sorted(set(glob.glob(os.path.join(CACHE, '*.pdf')))):
        base = os.path.basename(f)
        if any(s.lower() in base.lower() for s in SKIP):
            continue
        if any(p.lower() in base.lower() for p in pats):
            got.append(f)
    return got


def units_of(pats):
    """Слияние корпусов и фаз. Ключ — номер юнита; побеждает самый свежий термшит,
    при равной дате — спец-кампания (у неё живая цена)."""
    rows, used = {}, []
    order = sorted(sheets(pats), key=lambda f: (sheet_date(f), 'special' in f.lower()))
    for f in order:
        lots = lots_of(f)
        if not lots:
            continue
        used.append((os.path.basename(f), sheet_date(f), len(lots)))
        for r in lots:
            rows[r['code']] = r
    return list(rows.values()), used


def main():
    if FETCH or not glob.glob(os.path.join(CACHE, '*.pdf')):
        fetch()
    objs, env = TP.sb('objects?select=plp_property_id,name,price_from_thb,price_to_thb,availability'
                      '&plp_property_id=in.(%s)' % ','.join(MAP))
    by = {o['plp_property_id']: o for o in objs}
    money = lambda v: f'{v:,}'.replace(',', ' ') + ' ฿'
    changed = 0
    print('%-20s %-8s %-16s %-16s %s' % ('объект', 'прайс', 'было', 'станет', 'свободно'))
    for pid, pats in MAP.items():
        o = by.get(pid)
        if not o:
            print('%-20s карточки нет в базе' % pid)
            continue
        u, used = units_of(pats)
        if not u:
            print('%-20s термшит не разобран' % pid)
            continue
        s = TP.summarize(u, pid)
        as_of = max(d for _, d, _ in used)
        if not s:
            print('%-20s %-8s все юниты заняты — «распродан, остался запрос»' % (pid, as_of))
            continue
        old = o.get('price_from_thb')
        big = old and abs(s['from'] - old) > old * 0.25
        print('%-20s %-8s %-16s %-16s %d из %d%s' % (
            pid, as_of, money(old) if old else '—', money(s['from']), s['avail'],
            len(u), '   ⚠ больше четверти — нужен «го»' if big else ''))
        for f, d, n in used:
            print('        ← %s (%s, строк %d)' % (f[:62], d, n))
        if APPLY and not (big and not FORCE):
            body = {'price_from_thb': s['from'], 'price_to_thb': s['to'],
                    'price_tiers': s['tiers'], 'availability': 'свободно %d' % s['avail'],
                    'last_synced_at': datetime.datetime.utcnow().isoformat() + 'Z'}
            if s.get('layouts'):
                body['unit_types'] = s['layouts']
            TP.patch(env, pid, body)
            changed += 1
    print('\nПрайс есть, карточки нет:')
    for name, pats in NOCARD.items():
        u, used = units_of(pats)
        if not u:
            continue
        s = TP.summarize(u, None)
        as_of = max(d for _, d, _ in used)
        if s:
            print('  %-36s %-8s от %-14s свободно %d из %d' % (name, as_of, money(s['from']), s['avail'], len(u)))
        else:
            print('  %-36s %-8s распродан (%d юнитов)' % (name, as_of, len(u)))
    if APPLY:
        print('\nзаписано карточек: %d — пересобрать сайт: node build/all.mjs' % changed)


if __name__ == '__main__':
    main()
