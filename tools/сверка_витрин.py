#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка витрин: один факт, одна истина, остальное — копии (single source of truth + consistency check).

Эльнур 22.10.2026: «смотри, чтобы все презы, все страницы не расходились».
Истина: objects (цена «от», первый взнос, бронь, свободно, продано %) и горячие_офферы (тексты предложений).
Копии, которые сверяем с истиной и между собой:
  каталог index.html, cg-capital.html и встроенный в predstart.html (PL.PROPERTIES), offer-catalog.json,
  build/offers_truth.json, листы offers/*/sheet.json и page.htm, текст PDF листов, карточки /predstart,
  квиз kviz/index.html, горячие_офферы.
Проверки:
  цена     цена «от» в базе есть на каждой копии; ниже неё на копии цифры нет (устаревшая цена);
  свободно «свободно N» в базе и в каталоге;
  условия  первый взнос %, бронь, «продано N%» против базы;
  скидка   «и ещё 5%» всегда с «от остатка после первого этапа» (Эльнур 22.10, решение №321);
  копии    каталог predstart / cg-capital против index.html; цены в sheet.json, page.htm и PDF между собой;
  не существует  проект с пометкой «не существует» в базе не должен светиться на сайте (Artrio, 22.10);
  прайс    дата прайса на листе не старше свежего прайса застройщика в материалы_проекта (справка).
Ничего не правит. Ключи читает из ~/.plp_site_supabase.env и не печатает.

    python3 tools/сверка_витрин.py             # таблица расхождений
    python3 tools/сверка_витрин.py --short     # итог одной строкой (для сборки)
    python3 tools/сверка_витрин.py --strict    # код выхода 1, если цена «от» разошлась с базой
    python3 tools/сверка_витрин.py --сайт DIR  # другая копия сайта (например, чистый checkout)
Дата в каталоге (priceDate) — дата правки карточки, а на листе стоит дата прайса застройщика: это разные вещи, не сравниваем.
"""
import glob, html, json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if '--сайт' in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index('--сайт') + 1])
SHORT = '--short' in sys.argv
STRICT = '--strict' in sys.argv
ENV = os.path.expanduser('~/.plp_site_supabase.env')

# slug листа/квиза → ключ объекта в базе (выгрузка по website_url теряет eden, aileen, cg-capital)
SLUG = {
    'vibe2': 'PLP-VIBE2-KARON', 'kuartz': 'PLP-KUARTZ', 'fizz': 'PLP-FIZZ', 'zero-naiyang': 'PLP-ZERO-NAIYANG',
    'eden': 'PLP-EDEN-LAKE', 'aileen': 'PLP-AILEEN', 'millennium': 'PLP-MILLENNIUM', 'cg-capital': 'PLP-STANDARD',
}
ID2SLUG = {v: k for k, v in SLUG.items()}
CAT_ID = {'PLP-VIBE2-KARON': 'PLP-VIBE2'}   # в каталоге Vibe II лежит под ключом PLP-VIBE2
ПРОЕКТ = {'vibe2': 'Vibe II', 'kuartz': 'KUARTZ', 'fizz': 'FIZZ', 'zero-naiyang': 'ZERO Nai Yang', 'eden': 'Eden Lake',
          'aileen': 'Aileen', 'millennium': 'Millennium', 'cg-capital': 'The Standard'}
# листы, у которых цена в тексте относится к проекту целиком (у cg-capital в листе ещё Andaz/PURITA — их цен в базе нет)
РАЗДЕЛЫ_ЛИСТА = ('hero', 'stats', 'units', 'buy', 'cta', 'top', 'project', 'step', 'who', 'income', 'place', 'blocks', 'note', 'mode')

rows = []   # (вид, проект, где, поле, база, на копии)


def add(вид, проект, где, поле, база, копия):
    rows.append((вид, проект, где, поле, str(база), str(копия)))


def env():
    e = {}
    for line in open(ENV, encoding='utf-8'):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            e[k] = v.strip().strip('"').strip("'")
    return e


def rest(path):
    e = env()
    url = e['SUPABASE_URL'].rstrip('/') + '/rest/v1/' + urllib.parse.quote(path, safe="/?&=,.()*%:-_")
    key = e['SUPABASE_SERVICE_KEY']
    r = urllib.request.Request(url, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or '[]')


def read(rel):
    try:
        return open(os.path.join(ROOT, rel), encoding='utf-8').read()
    except Exception:
        return ''


def plain(s):
    s = re.sub(r'<style[\s\S]*?</style>|<script[\s\S]*?</script>', ' ', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s).replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ')
    return re.sub(r'\s+', ' ', s)


def flat(o):
    if isinstance(o, str):
        return [o]
    if isinstance(o, dict):
        return [x for v in o.values() for x in flat(v)]
    if isinstance(o, list):
        return [x for v in o for x in flat(v)]
    return []


def prices(text, точные=False):
    """Суммы в батах ≥ 1,5 млн. Точные: «5 767 967 ฿», «от 5 767 967», «–7 699 260» (цифры оси графика не берём).
    Круглые: «5,77 млн», «от 11,85 до 17,85 млн». Меньше 1,5 млн не берём: бронь, взнос, ставки аренды."""
    out = set()
    for m in re.finditer(r'(?<![\d,.])(\d{1,3}(?:[ ]\d{3}){2,})(?![\d])(\s?(?:฿|бат|THB)|\s?[–-]\s?\d)?', text):
        before = text[max(0, m.start() - 4):m.start()]
        if not (m.group(2) or re.search(r'(?:от|до|~|[–-])\s?$', before)):
            continue
        v = int(m.group(1).replace(' ', ''))
        if v >= 1_500_000:
            out.add(v)
    if not точные:
        for m in re.finditer(r'(?<![\d,.])(\d{1,3}(?:[,.]\d{1,2})?)(?:\s*(?:до|[–-])\s*(\d{1,3}(?:[,.]\d{1,2})?))?\s*млн', text):
            for g in (m.group(1), m.group(2)):
                if g:
                    v = round(float(g.replace(',', '.')) * 1_000_000)
                    if v >= 1_500_000:
                        out.add(v)
    return out


def близко(a, b, tol=0.006):
    return b and abs(a - b) / b <= tol


def has_price(tokens, db):
    return any(близко(t, db) for t in tokens)


def lower_than(tokens, db):
    return sorted(t for t in tokens if t >= 1_500_000 and t < db * (1 - 0.006))


def catalog(rel):
    t = read(rel)
    i = t.find('PL.PROPERTIES=')
    if i < 0:
        return {}
    arr, _ = json.JSONDecoder().raw_decode(t[i + len('PL.PROPERTIES='):].lstrip())
    return {x['property_id']: x for x in arr}


def cat_from(it):
    fr = [u.get('from') for u in (it.get('units') or []) if u.get('from')]
    return min(fr) if fr else None


def pdf_texts(paths):
    uv = shutil.which('uv') or os.path.expanduser('~/.local/bin/uv')
    if not paths or not os.path.exists(uv):
        return {}
    code = ('import sys,json,fitz\nout={}\nfor p in sys.argv[1:]:\n d=fitz.open(p)\n out[p]=" ".join(pg.get_text() for pg in d)\n'
            'print(json.dumps(out,ensure_ascii=False))')
    try:
        r = subprocess.run([uv, 'run', '--quiet', '--with', 'pymupdf', 'python', '-I', '-c', code] + paths,
                           capture_output=True, text=True, timeout=240)
        return json.loads(r.stdout)
    except Exception:
        return {}


def main():
    try:
        objs = {o['plp_property_id']: o for o in rest(
            'objects?select=plp_property_id,name,status,data_status,on_site,price_from_thb,first_payment,booking_deposit_thb,'
            'availability,sales_progress_pct&or=(' + ','.join('plp_property_id.eq.' + v for v in SLUG.values()) + ',data_status.ilike.не%20существует*)')}
        hot = rest('%D0%B3%D0%BE%D1%80%D1%8F%D1%87%D0%B8%D0%B5_%D0%BE%D1%84%D1%84%D0%B5%D1%80%D1%8B?select=id,%D1%88%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD,%D1%82%D0%B5%D0%BA%D1%81%D1%82,%D0%B0%D0%BA%D1%82%D0%B8%D0%B2%D0%B5%D0%BD'
                   '&%D0%B0%D0%BA%D1%82%D0%B8%D0%B2%D0%B5%D0%BD=eq.true')
    except Exception as e:
        print('[сверка витрин] база не ответила (%s)' % str(e)[:80])
        return 0

    # --- тексты копий по проектам
    surf = {s: {} for s in SLUG}        # slug → {имя копии: текст}
    sheet_text = {}
    for s in SLUG:
        try:
            d = json.load(open(os.path.join(ROOT, 'offers', s, 'sheet.json'), encoding='utf-8'))
            parts = [d[k] for k in РАЗДЕЛЫ_ЛИСТА if k in d]
            sheet_text[s] = plain(' '.join(flat(parts)))
            surf[s]['лист sheet.json'] = sheet_text[s]
            sheet_all = plain(' '.join(flat({k: v for k, v in d.items() if k not in ('head', 'tail', 'pdf', 'slug', 'mode')})))
        except Exception:
            sheet_all = ''
        pg = plain(read('offers/%s/page.htm' % s))
        if pg:
            surf[s]['лист page.htm'] = pg
            sheet_text.setdefault(s + ':page', pg)
        sheet_text[s + ':all'] = sheet_all
    pdfs = {}
    for s in SLUG:
        for p in glob.glob(os.path.join(ROOT, 'offers', s, '*.pdf')):
            pdfs[s] = p
    ptxt = pdf_texts(list(pdfs.values()))
    for s, p in pdfs.items():
        if p in ptxt:
            surf[s]['PDF листа'] = re.sub(r'\s+', ' ', ptxt[p].replace('\xa0', ' ').replace(' ', ' '))

    # квиз
    kv = read('kviz/index.html')
    for m in re.finditer(r"\n\s{2}([\w-]+):\s*\{\s*\n\s*id:'(PLP-[A-Z0-9-]+)'([\s\S]*?)(?=\n\s{2}[\w-]+:\s*\{\s*\n\s*id:'PLP-|\n\};)", kv):
        s = ID2SLUG.get(m.group(2))
        if s:
            body = m.group(3)
            keep = ' '.join(re.findall(r"(?:h1|sub|foot):'([^']*)'", body) + re.findall(r"facts:\[(.*?)\]\s*,\n", body))
            surf[s]['квиз'] = plain(keep)

    # карточки /predstart
    pst = read('predstart.html')
    for m in re.finditer(r'<article class="pc-card">([\s\S]*?)</article>', pst):
        card = m.group(1)
        h = re.search(r'href="/([a-z0-9-]+)"', card)
        if h and h.group(1) in SLUG:
            surf[h.group(1)]['карточка /predstart'] = plain(card)

    # горячие офферы
    for h in hot:
        t = (h.get('шаблон') or '') + ' ' + (h.get('текст') or '')
        m = re.search(r'property-library\.com/([a-z0-9-]+)', t)
        if m and m.group(1) in SLUG:
            surf[m.group(1)]['горячий оффер №%s' % h['id']] = plain(t)

    # --- 1. цена «от», условия, свободно, продано
    for s, pid in SLUG.items():
        o = objs.get(pid)
        if not o:
            add('ошибка', ПРОЕКТ[s], 'база', 'карточка', pid, 'нет в objects')
            continue
        db = int(float(o['price_from_thb'])) if o.get('price_from_thb') else None
        for где, т in surf[s].items():
            tok = prices(т)
            if db:
                # 23.10.2026 решение №322: квиз — посадочная рекламы Vibe II, там цена входа «от 2,8 млн бат», как в рекламе.
                # В базе остаётся цена пула 2 968 000 (№317). Исключение только для этой пары.
                if s == 'vibe2' and где == 'квиз' and 2_800_000 in tok:
                    continue
                if tok and not has_price(tok, db):
                    add('цена', ПРОЕКТ[s], где, 'цена от', '{:,}'.format(db).replace(',', ' '), ', '.join('{:,}'.format(x).replace(',', ' ') for x in sorted(tok)[:4]))
                low = lower_than(prices(т, True), db)
                if low and s != 'cg-capital':
                    add('цена', ПРОЕКТ[s], где, 'ниже цены «от»', '{:,}'.format(db).replace(',', ' '), ', '.join('{:,}'.format(x).replace(',', ' ') for x in low[:4]))
            fp = o.get('first_payment')
            for m in re.finditer(r'[Пп]ервый взнос(?: снижен до| от)?\s+(\d{2})\s*%', т):
                if fp and int(float(fp)) != int(m.group(1)):
                    add('условия', ПРОЕКТ[s], где, 'первый взнос %', fp, m.group(1))
            bd = o.get('booking_deposit_thb')
            for m in re.finditer(r'[Бб]ронь\s+(?:от\s+)?(\d[\d ]*)\s*(тыс|000)?', т):
                n = int(m.group(1).replace(' ', ''))
                n = n * 1000 if (m.group(2) == 'тыс' or n < 1000) else n
                if bd and int(float(bd)) != n and n >= 50_000:
                    add('условия', ПРОЕКТ[s], где, 'бронь, бат', bd, n)
            if s == 'cg-capital':
                sp = o.get('sales_progress_pct')
                for m in re.finditer(r'продан\w*\s+(?:на\s+)?(\d{2})\s*%|(\d{2})\s*%\s+(?:до сдачи\s+)?продан', т):
                    v = m.group(1) or m.group(2)
                    if sp and int(float(sp)) != int(v):
                        add('условия', ПРОЕКТ[s], где, 'продано %', sp, v)
        # свободно N
        mav = re.search(r'свободно\s+(\d+)', str(o.get('availability') or ''))
        if mav:
            for где, т in surf[s].items():
                for m in re.finditer(r'свободн\w*\s+(\d+)\s+из\s+\d+', т):
                    if m.group(1) != mav.group(1):
                        add('свободно', ПРОЕКТ[s], где, 'свободно', mav.group(1), m.group(1))

    # --- 2. каталоги
    base = catalog('index.html')
    for pid, o in objs.items():
        if pid not in SLUG.values():
            continue
        db = int(float(o['price_from_thb'])) if o.get('price_from_thb') else None
        it = base.get(CAT_ID.get(pid, pid))
        if it is None:
            add('цена', pid, 'каталог index.html', 'карточка', db, 'нет в каталоге')
            continue
        cf = cat_from(it)
        if db and cf and not близко(cf, db):
            add('цена', ПРОЕКТ[ID2SLUG[pid]], 'каталог index.html', 'цена от (units)', db, cf)
        mav = re.search(r'свободно\s+(\d+)', str(o.get('availability') or ''))
        if mav and str(it.get('avail')) != mav.group(1):
            add('свободно', ПРОЕКТ[ID2SLUG[pid]], 'каталог index.html', 'avail', mav.group(1), it.get('avail'))
    # каталог живёт копией в каждой странице сборки (главная, районы, гайды, листы): все должны совпадать с index.html
    страницы = sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, '**', '*.html'), recursive=True)
                      if '/.git/' not in f and '/node_modules/' not in f)
    for rel in страницы:
        if rel == 'index.html' or 'PL.PROPERTIES=' not in read(rel):
            continue
        c2 = catalog(rel)
        for pid, it in base.items():
            x = c2.get(pid)
            nm = ПРОЕКТ.get(ID2SLUG.get(pid, ''), it.get('title', pid))
            if x is None:
                add('копии', nm, 'каталог в ' + rel, 'карточка', 'есть в index.html', 'нет')
                continue
            for f in ('priceUSD', 'avail', 'priceDate', 'units', 'status', 'soldOut', 'deadline'):
                if json.dumps(it.get(f), sort_keys=True, ensure_ascii=False) != json.dumps(x.get(f), sort_keys=True, ensure_ascii=False):
                    add('копии', nm, 'каталог в ' + rel, f, str(it.get(f))[:40], str(x.get(f))[:40])
    oc = {}
    try:
        for it in json.loads(read('offer-catalog.json')).get('items', []):
            oc[it.get('pub')] = it
    except Exception:
        pass
    for pid, o in objs.items():
        k = CAT_ID.get(pid, pid)
        if pid in SLUG.values() and k in oc and o.get('price_from_thb'):
            db = int(float(o['price_from_thb']))
            if oc[k].get('price_from') and not близко(oc[k]['price_from'], db):
                add('цена', ПРОЕКТ[ID2SLUG[pid]], 'offer-catalog.json', 'цена от', db, oc[k]['price_from'])
    try:
        tr = json.loads(read('build/offers_truth.json')).get('офферы', {})
    except Exception:
        tr = {}
    for s, v in tr.items():
        o = objs.get(SLUG.get(s, ''))
        if o and o.get('price_from_thb') and v.get('цена_от') and not близко(v['цена_от'], int(float(o['price_from_thb']))):
            add('цена', ПРОЕКТ[s], 'build/offers_truth.json', 'цена от', int(float(o['price_from_thb'])), v['цена_от'])

    # --- 3. sheet.json ↔ page.htm ↔ PDF: суммы между собой
    for s in SLUG:
        a = prices(sheet_text.get(s + ':all', ''), True)
        b = prices(sheet_text.get(s + ':page', ''), True)
        if a and b and a != b:
            add('копии', ПРОЕКТ[s], 'sheet.json ↔ page.htm', 'суммы', ', '.join(map(str, sorted(a - b)[:3])) or '-', ', '.join(map(str, sorted(b - a)[:3])) or '-')
        p = prices(surf[s].get('PDF листа', ''), True)
        if b and p and p != b:
            add('копии', ПРОЕКТ[s], 'page.htm ↔ PDF', 'суммы', ', '.join(map(str, sorted(b - p)[:3])) or '-', ', '.join(map(str, sorted(p - b)[:3])) or '-')

    # --- 4. «и ещё 5%» только с «от остатка после первого этапа»
    files = [f for f in glob.glob(os.path.join(ROOT, '**', '*'), recursive=True)
             if os.path.isfile(f) and f.endswith(('.html', '.htm', '.json', '.txt', '.js')) and '/.git/' not in f
             and '/build/' not in f and '/tools/' not in f and '/node_modules/' not in f]
    for f in files:
        try:
            t = open(f, encoding='utf-8').read()
        except Exception:
            continue
        for m in re.finditer(r'(?:и\s+)?(?:ещё|еще|дополнительно)\s+5\s*%(?!\s*от остатка после первого этапа)', t):
            add('скидка', '5%', os.path.relpath(f, ROOT) + ':' + str(t.count('\n', 0, m.start()) + 1), '«ещё 5%»', 'от остатка после первого этапа', t[m.start():m.end() + 30].replace('\n', ' '))
    for h in hot:
        t = plain((h.get('шаблон') or '') + ' ' + (h.get('текст') or ''))
        for m in re.finditer(r'(?:ещё|еще)\s+5\s*%(?!\s*от остатка после первого этапа)', t):
            add('скидка', '5%', 'горячий оффер №%s' % h['id'], '«ещё 5%»', 'от остатка после первого этапа', t[m.start():m.end() + 30])

    # --- 5. проект «не существует»
    gone = [o for o in objs.values() if str(o.get('data_status') or '').lower().startswith('не существует')]
    for o in gone:
        if o.get('on_site'):
            add('не существует', o['name'], 'objects', 'on_site', 'false', 'true')
        word = re.sub(r'^(The Title|The)\s+', '', o['name']).split(',')[0].strip()
        for f in files + [os.path.join(ROOT, 'sitemap.xml'), os.path.join(ROOT, 'llms.txt')]:
            try:
                if re.search(re.escape(word), open(f, encoding='utf-8').read(), re.I):
                    add('не существует', o['name'], os.path.relpath(f, ROOT), 'упоминание', 'нет', word)
            except Exception:
                pass

    # --- 6. дата прайса на листе против свежего прайса застройщика (справка)
    try:
        for s, pid in SLUG.items():
            docs = rest('%D0%BC%D0%B0%D1%82%D0%B5%D1%80%D0%B8%D0%B0%D0%BB%D1%8B_%D0%BF%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D0%B0?select=name,modified&project_key=eq.' + urllib.parse.quote(pid) + '&name=ilike.*price*&order=modified.desc&limit=1')
            if not docs:
                continue
            md = docs[0]['modified'][:10]
            пол = ' '.join(surf[s].values())
            dts = re.findall(r'прайс\w*(?:\s+\w+){0,3}?\s+(?:от\s+)?(\d{2})\.(\d{2})(?:\.(\d{4}))?', пол)
            if dts:
                latest = max('2026-%s-%s' % (b, a) for a, b, _ in dts)
                if latest < md:
                    add('прайс', ПРОЕКТ[s], 'листы и карточки', 'дата прайса', md + ' (' + docs[0]['name'] + ')', latest)
    except Exception:
        pass

    # --- вывод
    uniq = []
    for r in rows:
        if r not in uniq:
            uniq.append(r)
    bad_price = [r for r in uniq if r[0] == 'цена']
    if SHORT:
        print('[сверка витрин] расхождений: %d (цена «от»: %d)' % (len(uniq), len(bad_price)) + ('' if not uniq else ' — python3 tools/сверка_витрин.py'))
    else:
        if not uniq:
            print('Сверка витрин: расхождений нет.')
        else:
            print('%-14s | %-16s | %-26s | %-22s | %-30s | %s' % ('вид', 'проект', 'где', 'поле', 'истина (база)', 'на копии'))
            for r in sorted(uniq):
                print('%-14s | %-16s | %-26s | %-22s | %-30s | %s' % tuple(x[:60] for x in r))
            print('всего: %d, из них цена «от»: %d' % (len(uniq), len(bad_price)))
    return 1 if (STRICT and bad_price) else 0


if __name__ == '__main__':
    sys.exit(main())
