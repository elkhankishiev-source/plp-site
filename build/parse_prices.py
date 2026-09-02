# -*- coding: utf-8 -*-
"""Разбор прайсов застройщика: только Available, «от» = минимум по спальням."""
import fitz, re, json, glob, os

def parse(path):
    doc = fitz.open(path)
    text = "\n".join(p.get_text() for p in doc)
    lines = [l.strip() for l in text.split("\n")]
    rows, i = [], 0
    while i < len(lines):
        # статус — якорь строки; вокруг него собираем поля
        if lines[i] in ('Available','Reserved','Sold','Booked','Hold','Blocked'):
            st = lines[i]
            win = lines[max(0,i-3):i+12]
            nums = []
            for w in win:
                w2 = w.replace(',','').replace(' ','')
                if re.fullmatch(r'\d+(\.\d+)?', w2):
                    nums.append(float(w2))
            # тип комнаты: «1 BEDROOM …», «STUDIO», «2 BEDROOM …»
            rt = next((w for w in win if re.search(r'BEDROOM|BED ROOM|STUDIO|VILLA|DUPLEX|PENTHOUSE', w, re.I)), '')
            # у застройщиков разнобой: «1 BEDROOM», «One Bedroom», «1BR», «Studio»
            WORD = {'one':1,'two':2,'three':3,'four':4,'five':5}
            beds = None
            m = re.search(r'(\d)\s*(?:BEDROOM|BED ROOM|BR\b)', rt, re.I)
            if m:
                beds = int(m.group(1))
            else:
                m2 = re.search(r'\b(one|two|three|four|five)\b\s*bed', rt, re.I)
                if m2: beds = WORD[m2.group(1).lower()]
                elif re.search(r'STUDIO', rt, re.I): beds = 0
            if beds is None: beds = 0
            # площадь 15..600, цена > 500 000
            area = next((n for n in nums if 15 <= n <= 600), None)
            price = max([n for n in nums if n > 500000], default=None)
            if price and area:
                rows.append({'status': st, 'beds': beds, 'area': area, 'price': price})
            i += 1
        else:
            i += 1
    return rows

def summarize(rows):
    av = [r for r in rows if r['status'] == 'Available']
    if not av: return None
    tiers = {}
    for r in av:
        b = r['beds']
        if b not in tiers or r['price'] < tiers[b]['price_from_thb']:
            tiers[b] = {'bedrooms': b, 'area_sqm': r['area'], 'price_from_thb': int(r['price'])}
    prices = [r['price'] for r in av]
    return {
        'available': len(av),
        'total_rows': len(rows),
        'price_from_thb': int(min(prices)),
        'price_to_thb': int(max(prices)),
        'tiers': [tiers[k] for k in sorted(tiers)],
    }

out = {}
for f in sorted(glob.glob('prices/*.pdf')):
    pid = os.path.basename(f)[:-4]
    try:
        rows = parse(f)
        s = summarize(rows)
        out[pid] = s
        if s:
            t = ', '.join(f"{x['bedrooms'] or 'студия'}BR от {x['price_from_thb']:,}".replace(',',' ') for x in s['tiers'])
            print(f"  {pid:22s} свободно {s['available']:>3} из {s['total_rows']:>3}  {s['price_from_thb']:>11,} – {s['price_to_thb']:>11,}".replace(',',' '))
            print(f"  {'':22s} {t}")
        else:
            print(f"  {pid:22s} ⚠️ свободных нет или не разобрался ({len(rows)} строк)")
    except Exception as e:
        print(f"  {pid:22s} ошибка: {str(e)[:60]}")
        out[pid] = None
json.dump(out, open('prices_parsed.json','w'), ensure_ascii=False, indent=1)
