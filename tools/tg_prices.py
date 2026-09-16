#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Цены и наличие из каналов застройщиков (Telegram) → карточка объекта.

Эльнур 16.09.2026: «у Тайта есть группы в ТГ-канале, где они постоянно публикуют
цены и актуальное наличие. Не цены старта на юниты, которых уже нет — таких цен
уже нет, а ты пишешь „от“. Некоторые распроданы — ставим „продан, но по запросу“».

Что делает:
  • находит канал проекта среди подписок рабочего аккаунта;
  • берёт САМЫЙ СВЕЖИЙ прайс (плоский, не master-plan);
  • считает «от» и «до» ТОЛЬКО по строкам со статусом Available;
  • собирает тиры по числу спален (минимум в каждом);
  • видит «SOLD OUT» в канале и помечает объект распроданным.

Наружу ничего не пишет: только чтение своих подписок.

    python3 tools/tg_prices.py                 # все объекты продажи, отчёт
    python3 tools/tg_prices.py PLP-CORALINA    # один объект
    python3 tools/tg_prices.py --apply         # записать в public.objects
"""
import asyncio, json, os, re, sys, unicodedata, urllib.request, urllib.parse, urllib.error, datetime

ENV = os.path.expanduser('~/.plp_site_supabase.env')
CREDS = os.path.expanduser('~/.tg_creds.json')
SESSION = os.path.expanduser('~/.tg_session')
CACHE = '/tmp/plp_tg_prices'
APPLY = '--apply' in sys.argv
FORCE = '--force' in sys.argv   # переписать тиры даже если цена «от» не изменилась
ONLY = [a for a in sys.argv[1:] if not a.startswith('--')]

# Имя канала ищем по названию проекта; здесь — только исключения, где имена не совпадают.
ALIAS = {
    'PLP-VIVI': 'Vivi Bangtao', 'PLP-HALO1': 'Halo 1 Naiyang', 'PLP-EDEN': 'Gardens of Eden',
    'PLP-EDEN-RES': 'Gardens of Eden', 'PLP-EDEN-PARK': 'Gardens of Eden', 'PLP-EDEN-ETRO': 'Gardens of Eden',
    'PLP-ZERO-BANGTAO': 'The Zero Bang Tao', 'PLP-ZERO-NAIYANG': 'The Zero Bang Tao',
    'PLP-SUNHILLS-LAYAN': 'Sun Hills Lakeside', 'PLP-VIBE-KARON': 'VIBE', 'PLP-FANTASY-RAWAI': 'Fantasea',
    'PLP-AYANA': 'AYANA Phuket', 'PLP-MANOR': None, 'PLP-STANDARD': None,
    'PLP-VIBE-KARON': 'VIBE_RESIDENCE',
}

def plain(name):
    """Название канала стилизованными буквами (𝐕𝐈𝐁𝐄_𝐑𝐄𝐒𝐈𝐃𝐄𝐍𝐂𝐄) не совпадало ни с чем:
    для машины это другие символы. Приводим к обычным буквам перед сравнением."""
    s = unicodedata.normalize('NFKD', str(name or ''))
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()

STAT = re.compile(r'^(available|sold|reserved|booked|hold|sold out)$', re.I)
BEDRX = [(r'(\d)\s*beds?\b', None), (r'three\s*bedroom|3\s*bedroom', 3),
         (r'two\s*bedroom|2\s*bedroom', 2), (r'one\s*bedroom|1\s*bedroom|studio', 1)]


def sb(path):
    env = {}
    for line in open(ENV):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    key = env['SUPABASE_SERVICE_KEY']
    req = urllib.request.Request(env['SUPABASE_URL'].rstrip('/') + '/rest/v1/' + path,
                                 headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(req, timeout=90).read()), env


def sources(env):
    """Каналы застройщиков из реестра источников: {объект: имя канала}."""
    key = env['SUPABASE_SERVICE_KEY']
    req = urllib.request.Request(env['SUPABASE_URL'].rstrip('/') +
                                 "/rest/v1/object_sources?select=project_key,kind,url&kind=eq.tg&limit=500",
                                 headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    out = {}
    for r in json.loads(urllib.request.urlopen(req, timeout=60).read()):
        m = re.search(r't\.me/(?:s/)?([A-Za-z0-9_]{4,})', str(r.get('url') or ''))
        if m:
            out[r['project_key']] = m.group(1).lower()
    return out


def remember_channel(env, pid, name, username):
    """Нашли канал — записываем в реестр, чтобы в следующий раз не угадывать."""
    if not username:
        return
    key = env['SUPABASE_SERVICE_KEY']
    base = env['SUPABASE_URL'].rstrip('/') + '/rest/v1/object_sources'
    body = {'project_key': pid, 'project_name': name, 'kind': 'tg',
            'url': 'https://t.me/' + username, 'note': 'канал застройщика: прайсы и наличие',
            'added_by': 'tools/tg_prices.py', 'last_checked': datetime.date.today().isoformat()}
    try:
        r = urllib.request.Request(base, data=json.dumps(body, ensure_ascii=False).encode(), method='POST',
                                   headers={'apikey': key, 'Authorization': 'Bearer ' + key,
                                            'Content-Type': 'application/json', 'Prefer': 'return=minimal'})
        urllib.request.urlopen(r, timeout=30)
    except urllib.error.HTTPError as ex:
        if ex.code not in (409, 400):
            raise


def patch(env, pid, body):
    key = env['SUPABASE_SERVICE_KEY']
    req = urllib.request.Request(env['SUPABASE_URL'].rstrip('/') + '/rest/v1/objects?plp_property_id=eq.' + pid,
                                 data=json.dumps(body, ensure_ascii=False).encode(), method='PATCH',
                                 headers={'apikey': key, 'Authorization': 'Bearer ' + key,
                                          'Content-Type': 'application/json', 'Prefer': 'return=minimal'})
    urllib.request.urlopen(req, timeout=60)


def parse_units(path):
    """Строки прайса: статус, цена юнита, площадь, спальни.

    🔴 16.09: запись брали десятью ячейками подряд — и в неё затекала СЛЕДУЮЩАЯ
    строка таблицы. У Vivana из-за этого «2 спальни» получили цену однокомнатной.
    Поэтому: спальни ищем в первых ячейках по одной, цену берём ПЕРВУЮ (в строке
    за ней идут цена за метр, цена земли и цена дома), площадь сверяем с ценой за метр."""
    import fitz
    cells = []
    for page in fitz.open(path):
        cells += [c.strip() for c in page.get_text().split('\n') if c.strip()]
    recs, cur = [], None
    for c in cells:
        if STAT.match(c):
            if cur:
                recs.append(cur)
            cur = {'status': c.lower().replace(' ', ''), 'cells': []}
        elif cur is not None:
            cur['cells'].append(c)
    if cur:
        recs.append(cur)
    num = lambda c: float(c.replace(',', '').replace(' ', '')) if re.fullmatch(r'[\d,\s]+(?:\.\d+)?', c or '') else None
    out = []
    for r in recs:
        head = r['cells'][:9]
        nums = [(k, num(c)) for k, c in enumerate(head)]
        nums = [(k, v) for k, v in nums if v is not None]
        pr = next(((k, v) for k, v in nums if v >= 1_000_000), None)
        if not pr:
            continue
        pk, price = pr
        persq = next((v for k, v in nums if 20_000 <= v < 1_000_000), None)
        area = None
        if persq:
            area = next((v for k, v in nums if 15 <= v <= 3000 and abs(price / v - persq) <= persq * 0.06), None)
        if area is None:
            before = [v for k, v in nums if k < pk and 25 <= v <= 3000]
            area = before[-1] if before else None
        beds = None
        for c in head[:6]:                      # тип комнаты — в своих ячейках, не в соседней строке
            for rx, val in BEDRX:
                m = re.search(rx, c, re.I)
                if m:
                    beds = val if val else int(m.group(1))
                    break
            if beds:
                break
        if beds is None:
            # у вилл столбец «No. Bedrooms» — просто число перед ценой (Casa de Monte: «2»)
            bare = [v for k, v in nums if k < pk and float(v).is_integer() and 1 <= v <= 6]
            if bare:
                beds = int(bare[-1])
        out.append({'status': r['status'], 'price': int(price), 'area': area, 'beds': beds})
    col = parse_columns(path)          # второй способ: строки по координатам слов
    av = lambda x: sum(1 for r in x if r['status'] == 'available')
    # 🔴 16.09: у Vibe столбец статуса идёт ПОСЛЕ цены, и разбор по ячейкам приписывал
    # статус соседней строке: 8 свободных вместо 23. В шапке прайса обычно написано,
    # сколько свободно — по ней и выбираем, какой разбор верен.
    hint = None
    try:
        import fitz
        head = fitz.open(path)[0].get_text()[:400]
        m = re.search(r'(\d{1,4})\s*(?:units?\s*)?(?:-|—|:)?\s*(\d{1,4})\s*available', head, re.I)
        if m:
            hint = int(m.group(2))
        else:
            m = re.search(r'available\D{0,10}(\d{1,4})', head, re.I)
            hint = int(m.group(1)) if m else None
    except Exception:
        pass
    def sane(rows):
        """Доля строк, где цена за метр похожа на правду: 20 тыс.—600 тыс. ฿/м².
        Так отличаем таблицу юнитов от страницы с условиями оплаты, где тоже есть
        крупные числа (у AYANA из неё прилетал «взнос 1 500 000» вместо цены)."""
        got = [r for r in rows if r.get('area') and r['area'] > 5]
        if not got:
            return 0.0
        ok = sum(1 for r in got if 20_000 <= r['price'] / r['area'] <= 600_000)
        return ok / len(got)
    if hint:
        if abs(av(col) - hint) < abs(av(out) - hint):
            return col
        return out
    if not out:
        return col
    if not col:
        return out
    sc, so = sane(col), sane(out)
    if abs(sc - so) > 0.15:
        return col if sc > so else out
    return col if av(col) > av(out) else out


def parse_columns(path):
    """Вторая раскладка прайса: столбца статуса нет, а текст идёт колонками
    (так у Hythe: сначала все номера квартир, потом типы, потом площади, потом цены).
    Порядок текста тут бесполезен — собираем строки по КООРДИНАТАМ слов на странице.
    Такой файл и есть перечень свободного: его публикуют как «available units»."""
    import fitz
    out = []
    for page in fitz.open(path):
        words = page.get_text('words')          # (x0, y0, x1, y1, слово, …)
        if not words: continue
        rows = {}
        for w in words:
            key = round(w[1] / 4)               # строка — слова на одной высоте
            rows.setdefault(key, []).append((w[0], w[4]))
        for key in sorted(rows):
            cells = [t for _, t in sorted(rows[key])]
            line = ' '.join(cells)
            # номер юнита: буквы и сразу цифры (A201, B-201, CKA201). Раньше под шаблон
            # попадала строка «1 - 30 SEP 2026» из условий оплаты, и в цену уезжал взнос.
            if not re.search(r'\b[A-Z]{1,3}-?\d{3,4}[A-Z]?\b', line): continue
            if re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b', line, re.I) \
               and len(re.findall(r'\d', line)) < 12: continue
            nums = []
            for c in cells:
                cc = c.replace(',', '').replace(' ', '')
                if re.fullmatch(r'\d+(?:\.\d+)?', cc): nums.append(float(cc))
            price = next((v for v in reversed(nums) if v >= 1_000_000), None)
            if not price: continue
            persq = next((v for v in nums if 20_000 <= v < 1_000_000), None)
            area = None
            if persq:
                area = next((v for v in nums if 10 <= v <= 3000 and abs(price / v - persq) <= persq * 0.08), None)
            if area is None:
                area = next((v for v in nums if 20 <= v <= 3000), None)
            # спальни: сначала раскладка «2B+2B», потом «2 bed», и только потом «2BR».
            # Иначе номер этажа в соседней колонке («B 4 B-402») читался как спальни.
            m = (re.search(r'\b(\d)\s*B\s*\+\s*\d\s*B\b', line)
                 or re.search(r'(\d)\s*bed', line, re.I)
                 or re.search(r'\b(\d)\s*BR\b', line))
            st = 'sold' if re.search(r'\bsold|reserved\b', line, re.I) else 'available'
            out.append({'status': st, 'price': int(price), 'area': area,
                        'beds': int(m.group(1)) if m else None})
    return out


async def one_channel(cl, hit, pid):
    """Свежий прайс и отдельный пост SOLD OUT в канале проекта."""
    newest, soldout = None, None
    async for m in cl.iter_messages(hit.entity, limit=150):
        # только отдельный пост «SOLD OUT», иначе «башня А sold out» закроет весь проект
        if m.text and re.fullmatch(r'\W*sold\s*out\W*', m.text.strip(), re.I) and soldout is None:
            soldout = m.date
        nm = (m.file.name if (m.document and m.file and m.file.name) else '') or ''
        if nm.lower().endswith('.pdf') and re.search(r'price', nm, re.I) and not re.search(r'master', nm, re.I):
            if newest is None:
                newest = (m.date, nm, m)
    entry = {'channel': hit.name, 'username': str(getattr(hit.entity, 'username', '') or ''),
             'soldout': soldout.strftime('%Y-%m-%d') if soldout else None}
    if newest:
        dt, nm, m = newest
        path = os.path.join(CACHE, re.sub(r'[^A-Za-z0-9._-]+', '_', pid + '_' + nm))
        os.makedirs(CACHE, exist_ok=True)
        if not os.path.exists(path):
            await m.download_media(path)
        entry['file'] = os.path.basename(path)
        entry['as_of'] = dt.strftime('%Y-%m-%d')
        try:
            entry['units'] = parse_units(path)
        except Exception as ex:
            entry['error'] = str(ex)[:80]
    return entry


async def collect(objs, known=None):
    from telethon import TelegramClient
    c = json.load(open(CREDS))
    cl = TelegramClient(SESSION, c['api_id'], c['api_hash'])
    await cl.connect()
    if not await cl.is_user_authorized():
        print('Telegram: рабочий аккаунт не залогинен — прайсы не читаю')
        return {}
    dialogs = [d async for d in cl.iter_dialogs(limit=800) if d.is_channel]
    known = known or {}
    os.makedirs(CACHE, exist_ok=True)
    res = {}
    for o in objs:
        pid = o['plp_property_id']
        if pid in ALIAS and ALIAS[pid] is None:
            continue
        # 16.09: канал объекта записан в реестре источников — берём его, а не угадываем
        uname = known.get(pid)
        if uname:
            hit = next((d for d in dialogs if str(getattr(d.entity, 'username', '') or '').lower() == uname
                        or plain(d.name) == uname), None)
            if hit:
                res[pid] = await one_channel(cl, hit, pid)
                continue
        needle = ALIAS.get(pid) or re.sub(r'^(the\s+title|the)\s+', '', str(o['name']), flags=re.I)
        needle = re.sub(r'[,–—].*$', '', needle).strip()
        # общие слова названий («villa», «the title», район) канал не опознают:
        # «Villa Kirara» ловилась на «VillaCarte», «Sun Hills Lakeside» — на «Sun Hills Ольгинка»
        STOP = {'the', 'title', 'villa', 'villas', 'phuket', 'residence', 'residences', 'condo',
                'bang', 'tao', 'bangtao', 'naiyang', 'nayang', 'kamala', 'rawai', 'surin', 'layan',
                'karon', 'kata', 'project', 'official', 'hills', 'park', 'gardens'}
        words = [w.lower() for w in re.split(r'[\s,\-]+', needle) if len(w) > 3]
        key = [w for w in words if w not in STOP] or words
        best, score = None, 0
        for d in dialogs:
            nm = plain(d.name)
            sc = sum(1 for w in key if w in nm) * 2 + sum(1 for w in words if w in nm)
            if sc > score and key[0] in nm:   # первое слово — имя проекта, по нему и опознаём
                best, score = d, sc
        hit = best
        if not hit:
            res[pid] = {'channel': None}
            continue
        res[pid] = await one_channel(cl, hit, pid)
    await cl.disconnect()
    return res


RULES = {}
try:
    RULES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'price_rules.json')))
except Exception:
    pass


def summarize(u, pid=None):
    av = [x for x in u if x['status'] == 'available']
    # правило объекта: в одном прайсе бывают две разные серии (виллы и компактные дома)
    rule = RULES.get(pid or '', {})
    if rule.get('min_area'):
        keep = [x for x in av if x.get('area') and x['area'] >= rule['min_area']]
        if keep:
            av = keep
    if not av:
        return None
    tiers, byb = [], {}
    for x in av:
        if x['beds']:
            byb.setdefault(x['beds'], []).append(x)
    for b in sorted(byb):
        m = min(byb[b], key=lambda x: x['price'])
        tiers.append({'bedrooms': b, 'area_sqm': m['area'], 'price_from_thb': m['price']})
    return {'from': min(x['price'] for x in av), 'to': max(x['price'] for x in av),
            'avail': len(av), 'sold_rows': len(u) - len(av), 'tiers': tiers}


def main():
    rows, env = sb('objects?select=plp_property_id,name,price_from_thb,price_to_thb,stage,status,availability'
                   '&on_site=eq.true&purpose=not.in.(' + urllib.parse.quote('аренда') + ',rent)')
    if ONLY:
        rows = [r for r in rows if r['plp_property_id'] in ONLY]
    known = sources(env)
    data = asyncio.run(collect(rows, known))
    money = lambda v: f'{v:,}'.replace(',', ' ') + ' ฿'
    changed = 0
    for o in rows:
        pid = o['plp_property_id']
        e = data.get(pid) or {}
        if not e.get('channel'):
            print('%-20s канала нет' % pid)
            continue
        if APPLY and pid not in known and e.get('username'):
            remember_channel(env, pid, o['name'], e['username'])
        s = summarize(e.get('units') or [], pid)
        # «SOLD OUT» свежее прайса — значит прайс уже не про наличие (так было у Estella:
        # в прайсе одна свободная вилла, а через месяц канал написал SOLD OUT)
        if s and e.get('soldout') and e.get('as_of') and e['soldout'] > e['as_of']:
            s = None
        if not s:
            note = 'РАСПРОДАНО' if e.get('soldout') else 'прайса нет'
            print('%-20s %-34s %s%s' % (pid, e['channel'][:34], note,
                                        (' (' + e['soldout'] + ')') if e.get('soldout') else ''))
            if APPLY and e.get('soldout') and str(o.get('stage')) != 'Resale':
                patch(env, pid, {'status': 'sold', 'stage': 'Sold out',
                                 'availability': 'У застройщика распродано. Ищем на вторичном рынке по запросу.'})
                changed += 1
            continue
        old = o.get('price_from_thb')
        mark = '=' if old and abs(old - s['from']) <= s['from'] * 0.005 else '≠'
        print('%-20s %-24s прайс %s: свободно %-4d от %s (было %s) %s' % (
            pid, e['channel'][:24], e.get('as_of', '?'), s['avail'], money(s['from']),
            money(old) if old else '—', mark))
        # предохранитель: правку больше четверти цены руками не подтверждали — не пишем.
        # Так в карточку не уедет прайс соседнего проекта из той же папки или канала.
        if RULES.get(pid, {}).get('manual'):
            print('     ⌁ цена ведётся руками: %s' % RULES[pid].get('why', '')[:90])
            continue
        big = old and abs(s['from'] - old) > old * 0.25
        if big and not FORCE:
            print('     ⚠ расхождение больше четверти — не записываю, нужно подтверждение')
        if APPLY and (mark == '≠' or FORCE) and not (big and not FORCE):
            patch(env, pid, {'price_from_thb': s['from'], 'price_to_thb': s['to'],
                             'price_tiers': s['tiers'], 'availability': 'свободно %d' % s['avail'],
                             'last_synced_at': datetime.datetime.utcnow().isoformat() + 'Z'})
            changed += 1
    if APPLY:
        print('\nзаписано карточек: %d — пересобрать сайт: node build/all.mjs' % changed)


if __name__ == '__main__':
    main()
