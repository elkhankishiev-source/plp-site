#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Всё, что есть у застройщика на Диске — из одной ссылки.

Эльнур 16.09.2026: «главное, чтобы был инструмент, который умеет доставать всю
необходимую информацию из ссылки гугл диска: из файлов, из текста, из фото, из
картинок — не сливался и не говорил „там этого нет“, хотя всё там».

Что делает:
  • берёт ссылку на папку из реестра источников (object_sources) или из карточки;
  • обходит папку ЦЕЛИКОМ, со всеми вложенными, постранично — ничего не пропуская;
  • читает прайсы и буклеты (PDF, Excel, Google-таблицы, Документы) текстом;
  • достаёт цены по свободным юнитам, срок сдачи, планировки, инфраструктуру;
  • складывает снимки и планы по видам, чтобы залить их tools/photos.py;
  • печатает ОПИСЬ: что нашёл, что прочитал, что не смог — и почему.

Ключи: ~/.plp_google_oauth.json + ~/.plp_google_tokens_drive.json (доступ Диска
уже выдан). Наружу ничего не пишет: только чтение Диска и запись в свою папку.

    python3 tools/drive_pull.py PLP-HERITAGE            # опись папки объекта
    python3 tools/drive_pull.py PLP-HERITAGE --files    # + скачать прайсы и разобрать
    python3 tools/drive_pull.py --url <ссылка> --files  # по произвольной ссылке
    python3 tools/drive_pull.py --all                   # опись по всем объектам сайта
    python3 tools/drive_pull.py PLP-HYTHE --vision     # готовит кадры для чтения глазами
    python3 tools/drive_pull.py PLP-HYTHE --price      # разобрать прайс: «от», «до», тиры
    python3 tools/drive_pull.py PLP-HALO1 --photos     # скачать снимки и планы по видам
    python3 tools/drive_pull.py PLP-HYTHE --price --apply   # и записать в карточку
"""
import datetime, json, os, re, sys, urllib.parse, urllib.request, urllib.error

OAUTH = os.path.expanduser('~/.plp_google_oauth.json')
TOKENS = os.path.expanduser('~/.plp_google_tokens_drive.json')
ENVF = os.path.expanduser('~/.plp_site_supabase.env')
CACHE = os.path.expanduser('~/plp_drive_cache')
API = 'https://www.googleapis.com/drive/v3/files'

KIND = [
    ('price',    r'price|прайс|pricelist|наличи|availab'),
    ('factsheet',r'factsheet|fact sheet|спецификац|specification'),
    ('brochure', r'brochure|буклет|e-?book|presentation|презентац|profile'),
    ('unitplan', r'unit plan|floor ?plan|планировк|layout|тип'),
    ('master',   r'master ?plan|мастер|site ?plan|генплан'),
    ('facility', r'facilit|инфраструктур|amenit|common'),
    ('progress', r'progress|ход стро|стройк|construction'),
    ('contract', r'contract|договор|agreement|reserv'),
    ('payment',  r'payment|рассроч|installment|план оплат'),
    ('photo',    r'photo|фото|perspective|render|рендер|show ?unit|interior|exterior'),
    ('video',    r'vdo|video|видео|walkthrough|360'),
    ('map',      r'\bmap\b|карта|location|локац'),
]
TEXTUAL = {
    'application/pdf': 'pdf',
    'application/vnd.google-apps.document': 'gdoc',
    'application/vnd.google-apps.spreadsheet': 'gsheet',
    'application/vnd.google-apps.presentation': 'gslides',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt', 'text/csv': 'csv',
}
EXPORT = {'gdoc': 'text/plain', 'gsheet': 'text/csv', 'gslides': 'text/plain'}


def token():
    o = json.load(open(OAUTH)); t = json.load(open(TOKENS))
    data = urllib.parse.urlencode({'client_id': o['client_id'], 'client_secret': o['client_secret'],
                                   'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token'}).encode()
    r = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    return json.loads(urllib.request.urlopen(r, timeout=40).read())['access_token']


def api(tok, params):
    url = API + '?' + urllib.parse.urlencode(params)
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def folder_id(link):
    m = re.search(r'/folders/([A-Za-z0-9_-]{20,})', str(link) or '')
    if m: return m.group(1)
    m = re.search(r'[?&]id=([A-Za-z0-9_-]{20,})', str(link) or '')
    if m: return m.group(1)
    m = re.search(r'/d/([A-Za-z0-9_-]{20,})', str(link) or '')
    return m.group(1) if m else None


def walk(tok, root, depth=0, path='', seen=None, out=None, limit=4000):
    """Обход ВСЕЙ папки: вложенные, постранично. Ничего не пропускаем."""
    seen = seen if seen is not None else set()
    out = out if out is not None else []
    if root in seen or len(out) > limit: return out
    seen.add(root)
    page = None
    while True:
        p = {'q': "'%s' in parents and trashed=false" % root,
             'fields': 'nextPageToken,files(id,name,mimeType,size,modifiedTime)',
             'pageSize': 1000, 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
        if page: p['pageToken'] = page
        try:
            d = api(tok, p)
        except urllib.error.HTTPError as e:
            out.append({'error': '%s: %s' % (path or root, e.code)}); return out
        for f in d.get('files', []):
            f['path'] = (path + '/' + f['name']).lstrip('/')
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                out.append(f)
                walk(tok, f['id'], depth + 1, f['path'], seen, out, limit)
            else:
                out.append(f)
        page = d.get('nextPageToken')
        if not page: break
    return out


def kind_of(f):
    blob = f.get('path', '') + ' ' + f.get('name', '')
    for k, rx in KIND:
        if re.search(rx, blob, re.I): return k
    mt = f.get('mimeType', '')
    if mt.startswith('image/'): return 'photo'
    if mt.startswith('video/'): return 'video'
    return 'other'


def fetch(tok, f, dest):
    """Скачать файл (или выгрузить Google-документ текстом)."""
    t = TEXTUAL.get(f['mimeType'])
    if t in EXPORT:
        url = API + '/' + f['id'] + '/export?mimeType=' + urllib.parse.quote(EXPORT[t])
    else:
        url = API + '/' + f['id'] + '?alt=media&supportsAllDrives=true'
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
    b = urllib.request.urlopen(r, timeout=300).read()
    open(dest, 'wb').write(b)
    return len(b)


def text_of(path, mime):
    if path.lower().endswith('.pdf'):
        try:
            import fitz
            return '\n'.join(p.get_text() for p in fitz.open(path))
        except Exception as ex:
            return '[pdf не прочитан: %s]' % str(ex)[:60]
    if path.lower().endswith(('.csv', '.txt')):
        return open(path, encoding='utf-8', errors='replace').read()
    if path.lower().endswith('.xlsx'):
        try:
            import zipfile, xml.etree.ElementTree as ET
            z = zipfile.ZipFile(path)
            shared = []
            if 'xl/sharedStrings.xml' in z.namelist():
                root = ET.fromstring(z.read('xl/sharedStrings.xml'))
                shared = [''.join(t.text or '' for t in si.iter() if t.tag.endswith('}t')) for si in root]
            rows = []
            for nm in [n for n in z.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml', n)]:
                root = ET.fromstring(z.read(nm))
                for row in root.iter():
                    if not row.tag.endswith('}row'): continue
                    vals = []
                    for c in row:
                        v = ''.join(x.text or '' for x in c.iter() if x.tag.endswith('}v'))
                        if c.get('t') == 's' and v.isdigit() and int(v) < len(shared): v = shared[int(v)]
                        vals.append(v)
                    if any(vals): rows.append(' | '.join(vals))
            return '\n'.join(rows)
        except Exception as ex:
            return '[xlsx не прочитан: %s]' % str(ex)[:60]
    return ''


MONEY = re.compile(r'\b\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?\b')
HAND = re.compile(r'(?:handover|completion|сдач\w*|заверш\w*|ready)\D{0,25}((?:Q[1-4]\s*)?20[2-3]\d)', re.I)


def facts(text):
    """Что удалось понять из текста: цены, сроки, наличие."""
    av = len(re.findall(r'\bavailable\b', text, re.I))
    sold = len(re.findall(r'\bsold\b', text, re.I))
    prices = sorted({float(x.replace(',', '')) for x in MONEY.findall(text)} - {0.0})
    prices = [p for p in prices if 500_000 <= p <= 500_000_000]
    hand = sorted({m.group(1).upper().replace(' ', '') for m in HAND.finditer(text)})
    return {'available_rows': av, 'sold_rows': sold,
            'price_min': prices[0] if prices else None, 'price_max': prices[-1] if prices else None,
            'handover': hand[:4]}


def sb(path):
    env = {}
    for line in open(ENVF):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1); env[k] = v.strip().strip('"').strip("'")
    key = env['SUPABASE_SERVICE_KEY']
    r = urllib.request.Request(env['SUPABASE_URL'].rstrip('/') + '/rest/v1/' + path,
                               headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.loads(urllib.request.urlopen(r, timeout=90).read())


def link_for(pid):
    """Ссылка на папку: сначала реестр источников, потом поле карточки."""
    rows = sb('object_sources?select=url,kind,note&project_key=eq.' + urllib.parse.quote(pid))
    for r in rows:
        if folder_id(r.get('url')) and re.search(r'drive|диск', str(r.get('kind') or ''), re.I):
            return r['url'], 'реестр источников'
    for r in rows:
        if folder_id(r.get('url')): return r['url'], 'реестр источников'
    o = sb('objects?select=brochure_url,floorplan_url&plp_property_id=eq.' + urllib.parse.quote(pid))
    if o:
        for f in ('brochure_url', 'floorplan_url'):
            if folder_id(o[0].get(f)): return o[0][f], 'карточка объекта (%s)' % f
    return None, None


def report(pid, link, tok, want_files):
    fid = folder_id(link)
    print('=' * 78)
    print('%s · %s' % (pid, link))
    if not fid:
        print('  ссылка не похожа на папку Диска'); return
    files = walk(tok, fid)
    errs = [f for f in files if f.get('error')]
    folders = [f for f in files if f.get('mimeType') == 'application/vnd.google-apps.folder']
    docs = [f for f in files if f.get('mimeType') != 'application/vnd.google-apps.folder' and not f.get('error')]
    print('  папок %d, файлов %d%s' % (len(folders), len(docs),
          (', закрытых веток %d' % len(errs)) if errs else ''))
    by = {}
    for f in docs: by.setdefault(kind_of(f), []).append(f)
    for k in sorted(by, key=lambda x: -len(by[x])):
        names = ', '.join(sorted(x['name'] for x in by[k])[:3])
        print('   %-10s %3d  %s' % (k, len(by[k]), names[:96]))
    for e in errs[:3]:
        print('   ⚠ не открылась ветка: %s' % e['error'])
    if not want_files: return
    os.makedirs(os.path.join(CACHE, pid), exist_ok=True)
    order = ['price', 'factsheet', 'payment', 'unitplan', 'brochure']
    picked = []
    for k in order:
        for f in sorted(by.get(k, []), key=lambda x: x.get('modifiedTime', ''), reverse=True)[:2]:
            if TEXTUAL.get(f['mimeType']): picked.append(f)
    if not picked:
        print('   читать нечего: ни прайса, ни спецификации, ни буклета в текстовом виде')
        return
    for f in picked:
        ext = {'gdoc': '.txt', 'gsheet': '.csv', 'gslides': '.txt'}.get(TEXTUAL.get(f['mimeType']), '')
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:70] + ext
        dest = os.path.join(CACHE, pid, safe)
        try:
            if not os.path.exists(dest): fetch(tok, f, dest)
            txt = text_of(dest, f['mimeType'])
            fc = facts(txt)
            print('   ▸ %s · %s' % (f['path'][:60], f.get('modifiedTime', '')[:10]))
            print('     свободно строк %s, продано %s, цены %s…%s, сроки %s' % (
                fc['available_rows'], fc['sold_rows'],
                ('%.2f млн' % (fc['price_min'] / 1e6)) if fc['price_min'] else '—',
                ('%.2f млн' % (fc['price_max'] / 1e6)) if fc['price_max'] else '—',
                ', '.join(fc['handover']) or '—'))
        except Exception as ex:
            print('   ✗ %s: %s' % (f['name'][:50], str(ex)[:70]))


def vision(pid, link, tok, limit=12):
    """Прайсы и спецификации часто приходят картинкой: текста в них нет, но данные есть.
    Эльнур: «не сливайся и не говори, что там этого нет». Достаём страницы кадрами —
    их читают глазами (инструмент печатает пути)."""
    fid = folder_id(link)
    if not fid:
        print('  ссылка не похожа на папку Диска'); return
    files = [f for f in walk(tok, fid) if f.get('mimeType') and not f.get('error')
             and f['mimeType'] != 'application/vnd.google-apps.folder']
    want = [f for f in files if kind_of(f) in ('price', 'factsheet', 'payment', 'unitplan', 'master')]
    want += [f for f in files if kind_of(f) == 'brochure' and f['mimeType'] == 'application/pdf']
    want = sorted(want, key=lambda x: x.get('modifiedTime', ''), reverse=True)[:limit]
    outdir = os.path.join(CACHE, pid, 'кадры')
    os.makedirs(outdir, exist_ok=True)
    made = []
    for f in want:
        raw = os.path.join(CACHE, pid, re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:70])
        try:
            if not os.path.exists(raw): fetch(tok, f, raw)
        except Exception as ex:
            print('   ✗ %s: %s' % (f['name'][:44], str(ex)[:60])); continue
        if f['mimeType'] == 'application/pdf':
            try:
                import fitz
                doc = fitz.open(raw)
                has_text = any(p.get_text().strip() for p in doc)
                pages = range(min(doc.page_count, 6))
                if has_text:
                    made.append(('текст', raw, doc.page_count)); continue
                for i in pages:
                    png = os.path.join(outdir, re.sub(r'\W+', '_', f['name'])[:40] + '_%02d.png' % (i + 1))
                    if not os.path.exists(png):
                        doc[i].get_pixmap(dpi=140).save(png)
                    made.append(('кадр', png, None))
            except Exception as ex:
                print('   ✗ pdf %s: %s' % (f['name'][:40], str(ex)[:60]))
        elif f['mimeType'].startswith('image/'):
            dst = os.path.join(outdir, re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:60])
            if not os.path.exists(dst):
                open(dst, 'wb').write(open(raw, 'rb').read())
            made.append(('снимок', dst, None))
    print('  подготовлено к чтению: %d' % len(made))
    for kind, path, pages in made:
        print('   %-7s %s%s' % (kind, path, (' (%d стр., текст читается)' % pages) if pages else ''))


def price_from_drive(pid, link, tok, apply=False):
    """Прайс с Диска — тем же разбором, что и прайс из Telegram (tools/tg_prices.py):
    в цену идут только свободные юниты."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tg_prices as TP
    fid = folder_id(link)
    if not fid:
        print('  ссылка не похожа на папку Диска'); return None
    files = [f for f in walk(tok, fid) if not f.get('error')
             and f.get('mimeType') != 'application/vnd.google-apps.folder']
    cand = [f for f in files if kind_of(f) == 'price' and TEXTUAL.get(f['mimeType'])]
    cand.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
    if not cand:
        print('  прайса в текстовом виде нет — смотрите --vision (файл может быть картинкой)')
        return None
    for f in cand[:3]:
        raw = os.path.join(CACHE, pid, re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:70])
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        try:
            if not os.path.exists(raw): fetch(tok, f, raw)
            units = TP.parse_units(raw)
        except Exception as ex:
            print('   ✗ %s: %s' % (f['name'][:44], str(ex)[:60])); continue
        s2 = TP.summarize(units, pid)
        if not s2:
            print('   ▸ %s · свободных строк нет' % f['name'][:60]); continue
        money = lambda v: f'{v:,}'.replace(',', ' ') + ' ฿'
        print('   ▸ %s · %s' % (f['name'][:60], f.get('modifiedTime', '')[:10]))
        print('     свободно %d, от %s до %s' % (s2['avail'], money(s2['from']), money(s2['to'])))
        for t in s2['tiers']:
            print('       %s сп. · %s м² · от %s' % (t['bedrooms'], t['area_sqm'], money(t['price_from_thb'])))
        if apply:
            # предохранитель: в папке застройщика лежат прайсы соседних проектов
            # (у Panora — виллы и кондо в одной папке). Резкое расхождение с текущей
            # ценой — не правка, а повод спросить.
            cur = None
            try:
                e0 = {}
                for line in open(ENVF):
                    if '=' in line and not line.strip().startswith('#'):
                        k, v = line.strip().split('=', 1); e0[k] = v.strip().strip('"').strip("'")
                q = urllib.request.Request(e0['SUPABASE_URL'].rstrip('/') +
                        '/rest/v1/objects?select=price_from_thb&plp_property_id=eq.' + urllib.parse.quote(pid),
                        headers={'apikey': e0['SUPABASE_SERVICE_KEY'],
                                 'Authorization': 'Bearer ' + e0['SUPABASE_SERVICE_KEY']})
                cur = (json.loads(urllib.request.urlopen(q, timeout=30).read()) or [{}])[0].get('price_from_thb')
            except Exception:
                pass
            if cur and abs(s2['from'] - cur) > cur * 0.25:
                print('     ⚠ не записываю: в карточке %s ฿, в прайсе %s ฿ — расхождение больше четверти.'
                      % (f'{cur:,}'.replace(',', ' '), money(s2['from'])))
                print('       Похоже, в папке лежит прайс другого проекта. Нужно подтверждение.')
                return s2
            e = {}
            for line in open(ENVF):
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1); e[k] = v.strip().strip('"').strip("'")
            TP.patch(e, pid, {'price_from_thb': s2['from'], 'price_to_thb': s2['to'],
                              'price_tiers': s2['tiers'], 'availability': 'свободно %d' % s2['avail'],
                              'last_synced_at': datetime.datetime.utcnow().isoformat() + 'Z'})
            print('     ✓ записано в карточку (источник: Диск, файл от %s)' % f.get('modifiedTime', '')[:10])
        return s2
    return None


def photos(pid, link, tok, per_kind=14):
    """Снимки, планировки и мастер-план с Диска — по видам, в папку для tools/photos.py.
    Отбор по смыслу за инструментом не закреплён: сначала смотрим контактный лист
    глазами, мусор удаляем, и только потом заливаем (канон отбора кадров)."""
    fid = folder_id(link)
    if not fid:
        print('  ссылка не похожа на папку Диска'); return
    files = [f for f in walk(tok, fid) if not f.get('error')
             and str(f.get('mimeType', '')).startswith('image/')]
    want = {'photo': 'exterior', 'facility': 'facilities', 'unitplan': 'plans', 'master': 'master'}
    base = os.path.join(CACHE, pid, 'photos')
    got = {}
    for f in sorted(files, key=lambda x: x.get('modifiedTime', ''), reverse=True):
        k = want.get(kind_of(f))
        if not k: continue
        got.setdefault(k, [])
        if len(got[k]) >= per_kind: continue
        d = os.path.join(base, k); os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:60])
        try:
            if not os.path.exists(dest): fetch(tok, f, dest)
            got[k].append(dest)
        except Exception as ex:
            print('   ✗ %s: %s' % (f['name'][:40], str(ex)[:50]))
    if not got:
        print('  снимков в папке нет'); return
    for k, v in got.items():
        print('   %-10s %d → %s' % (k, len(v), os.path.join(base, k)))
    print('   дальше: посмотреть глазами, лишнее удалить, затем')
    print('   python3 tools/photos.py %s --id %s' % (base, pid))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    want_files = '--files' in sys.argv
    tok = token()
    want_vision = '--vision' in sys.argv
    want_price = '--price' in sys.argv
    want_photos = '--photos' in sys.argv
    do_apply = '--apply' in sys.argv
    if '--url' in sys.argv:
        link = sys.argv[sys.argv.index('--url') + 1]
        if want_vision: vision('ссылка', link, tok)
        else: report('ссылка', link, tok, want_files)
        return
    if '--all' in sys.argv:
        rows = sb('objects?select=plp_property_id&on_site=eq.true&order=plp_property_id')
        ids = [r['plp_property_id'] for r in rows]
    else:
        ids = args
    if not ids:
        print(__doc__); return
    for pid in ids:
        link, src = link_for(pid)
        if not link:
            print('=' * 78); print('%s · ссылки на папку нет ни в реестре, ни в карточке' % pid); continue
        if want_photos:
            print('=' * 78); print('%s · %s' % (pid, link)); photos(pid, link, tok)
        elif want_price:
            print('=' * 78); print('%s · %s' % (pid, link)); price_from_drive(pid, link, tok, do_apply)
        elif want_vision:
            print('=' * 78); print('%s · %s' % (pid, link)); vision(pid, link, tok)
        else:
            report(pid, link, tok, want_files)


if __name__ == '__main__':
    main()
