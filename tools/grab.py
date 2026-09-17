#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Достать всё по любой ссылке: файлы, текст, детали договора.

Эльнур 17.09.2026: «создай инструмент, чтобы вытаскивать все необходимые файлы из
любой ссылки любого формата… ты уже как-то читал и доставал все детали из контрактов,
надо это сделать уже серьёзнее и создать сильный инструмент под это».

Раньше это было размазано: Диск читал drive_pull, прайсы Laguna — laguna_prices,
каналы — tg_prices, а сканы не читал никто. Здесь один вход на всё.

ЧТО ПОНИМАЕТ НА ВХОДЕ
  • папка или файл Google Drive          (drive.google.com/…/folders/<id>, /file/d/<id>)
  • папка или файл Dropbox               (dropbox.com/scl/fo/…  и /s/…)
  • прямая ссылка на файл по http(s)
  • обычная веб-страница — снимает с неё ссылки на файлы и качает их
  • путь в хранилище Supabase            (storage:client-docs/contracts/…)
  • локальная папка или файл

ЧТО ДЕЛАЕТ ДАЛЬШЕ
  1. скачивает всё, включая вложенные папки, и складывает в кэш;
  2. называет каждый файл по смыслу (прайс, планировка, мастер-план, договор, фото…);
  3. вынимает текст: сначала текстовый слой, а если его нет — распознаёт страницы
     средствами самой macOS (tools/ocr/plpocr, Vision). Именно это открыло 17
     подписанных договоров клиентов: в них ноль текста, по картинке на страницу,
     и прежний разбор честно отвечал «страницы полностью белые»;
  4. по договору вынимает поля: юнит, этаж, корпус, площадь дома и участка, спальни,
     цена, валюта, форма владения, даты договора и передачи, график платежей.

ЧЕГО НЕ ДЕЛАЕТ
  • не пишет в базу сам — только показывает, что нашёл (запись отдельным шагом);
  • не кладёт добытое в репозиторий: кэш живёт в ~/plp_grab, репозиторий публичный;
  • не выдумывает: поля, которых в документе нет, остаются пустыми.

    python3 tools/grab.py <ссылка>                  # что там лежит
    python3 tools/grab.py <ссылка> --text           # и вынуть текст
    python3 tools/grab.py <ссылка> --contract       # и разобрать как договор
    python3 tools/grab.py storage:client-docs/contracts/PLP-ESTELLA-A12 --contract
"""
import io, json, os, re, subprocess, sys, urllib.parse, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/plp_grab')
OCR = os.path.join(HERE, 'ocr', 'plpocr')
ENVF = os.path.expanduser('~/.plp_site_supabase.env')
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) plp-grab/1.0'}

KIND = [
    ('master',   r'master ?plan|мастер|site ?plan|генплан'),
    ('unitplan', r'unit ?plans?|floor ?plans?|villas? ?plans?|планировк|layout|поэтажн'),
    ('price',    r'price|прайс|pricelist|наличи|availab|termsheet|term sheet'),
    ('contract', r'contract|договор|agreement|booking|reserv|бронь|schedule|инвойс|invoice'),
    ('brochure', r'brochure|буклет|e-?book|presentation|презентац|profile|sales ?kit'),
    ('photo',    r'photo|фото|render|рендер|perspective|interior|exterior'),
    ('video',    r'vdo|video|видео|walkthrough|360'),
]
TEXTUAL = {'.pdf', '.txt', '.csv', '.md', '.json', '.docx', '.xlsx'}
IMAGE = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.tif', '.tiff'}


def kind_of(name):
    low = str(name).lower()
    for k, rx in KIND:
        if re.search(rx, low):
            return k
    return 'other'


def env():
    e = {}
    if os.path.exists(ENVF):
        for line in open(ENVF):
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                e[k] = v.strip().strip('"').strip("'")
    return e


# ─────────────────────────── источники ───────────────────────────

def drive_token():
    o = json.load(open(os.path.expanduser('~/.plp_google_oauth.json')))
    t = json.load(open(os.path.expanduser('~/.plp_google_tokens_drive.json')))
    c = o.get('installed') or o.get('web') or o
    d = urllib.parse.urlencode({'client_id': c['client_id'], 'client_secret': c['client_secret'],
                                'refresh_token': t['refresh_token'],
                                'grant_type': 'refresh_token'}).encode()
    return json.loads(urllib.request.urlopen(
        'https://oauth2.googleapis.com/token', d, timeout=60).read())['access_token']


def drive_walk(tok, fid, path=''):
    """Обход папки со всеми вложенными. Постраничный: без nextPageToken видна
    только первая горсть файлов — на этом не раз обжигались."""
    H = {'Authorization': 'Bearer ' + tok}
    out, page = [], None
    while True:
        q = urllib.parse.quote("'%s' in parents and trashed=false" % fid)
        u = ('https://www.googleapis.com/drive/v3/files?q=%s&pageSize=200'
             '&fields=nextPageToken,files(id,name,mimeType,size,modifiedTime)' % q)
        if page:
            u += '&pageToken=' + page
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=90).read())
        for f in d.get('files', []):
            if f['mimeType'].endswith('.folder'):
                out += drive_walk(tok, f['id'], path + f['name'] + '/')
            else:
                f['path'] = path
                out.append(f)
        page = d.get('nextPageToken')
        if not page:
            break
    return out


def drive_get(tok, f, dest):
    H = {'Authorization': 'Bearer ' + tok}
    if f['mimeType'].startswith('application/vnd.google-apps'):
        exp = {'document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
               'spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
               'presentation': 'application/pdf'}.get(f['mimeType'].rsplit('.', 1)[-1])
        if not exp:
            return False
        u = 'https://www.googleapis.com/drive/v3/files/%s/export?mimeType=%s' % (f['id'], urllib.parse.quote(exp))
    else:
        u = 'https://www.googleapis.com/drive/v3/files/%s?alt=media' % f['id']
    open(dest, 'wb').write(urllib.request.urlopen(
        urllib.request.Request(u, headers=H), timeout=600).read())
    return True


def from_dropbox(url, out):
    """Папка Dropbox отдаётся архивом, одиночный файл — как есть."""
    u = re.sub(r'[?&]dl=\d', '', url) + ('&' if '?' in url else '?') + 'dl=1'
    blob = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=900).read()
    if blob[:2] == b'PK':
        n = 0
        z = zipfile.ZipFile(io.BytesIO(blob))
        for m in z.namelist():
            if m.endswith('/'):
                continue
            dst = os.path.join(out, os.path.basename(m))
            open(dst, 'wb').write(z.read(m))
            n += 1
        return n
    name = urllib.parse.unquote(url.rstrip('/').split('/')[-1].split('?')[0]) or 'file'
    open(os.path.join(out, name), 'wb').write(blob)
    return 1


def from_page(url, out):
    """Обычная страница: снимаем ссылки на файлы и качаем их."""
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode('utf-8', 'ignore')
    links = set()
    for m in re.finditer(r'''(?:href|src)=["']([^"']+)["']''', html):
        u = urllib.parse.urljoin(url, m.group(1))
        if os.path.splitext(u.split('?')[0])[1].lower() in (TEXTUAL | IMAGE):
            links.add(u)
    n = 0
    for u in sorted(links)[:80]:
        try:
            name = urllib.parse.unquote(os.path.basename(u.split('?')[0])) or ('file%d' % n)
            open(os.path.join(out, name), 'wb').write(
                urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=300).read())
            n += 1
        except Exception:
            pass
    return n


def from_storage(spec, out):
    """storage:<бакет>/<путь> — папка или файл в хранилище Supabase."""
    e = env()
    B, key = e['SUPABASE_URL'].rstrip('/'), e['SUPABASE_SERVICE_KEY']
    H = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    bucket, _, path = spec.partition('/')
    bucket = bucket.split(':', 1)[1] if ':' in bucket else bucket

    def one(p, name):
        blob = urllib.request.urlopen(urllib.request.Request(
            '%s/storage/v1/object/%s/%s' % (B, bucket, urllib.parse.quote(p)), headers=H), timeout=600).read()
        open(os.path.join(out, name), 'wb').write(blob)

    r = urllib.request.Request('%s/storage/v1/object/list/%s' % (B, bucket),
                               data=json.dumps({'prefix': path.rstrip('/') + '/', 'limit': 200}).encode(),
                               method='POST', headers=H)
    items = json.loads(urllib.request.urlopen(r, timeout=120).read())
    n = 0
    for x in items:
        if x.get('id') is None:          # это подпапка
            continue
        one(path.rstrip('/') + '/' + x['name'], x['name'])
        n += 1
    if not n:                            # значит путь указывал на файл
        one(path, os.path.basename(path))
        n = 1
    return n


def fetch_all(src, out):
    os.makedirs(out, exist_ok=True)
    if src.startswith('storage:'):
        return from_storage(src, out), 'хранилище Supabase'
    if os.path.exists(src):
        import shutil
        if os.path.isdir(src):
            n = 0
            for root, _, files in os.walk(src):
                for f in files:
                    shutil.copy2(os.path.join(root, f), os.path.join(out, f)); n += 1
            return n, 'локальная папка'
        shutil.copy2(src, os.path.join(out, os.path.basename(src)))
        return 1, 'локальный файл'
    if 'dropbox.com' in src:
        return from_dropbox(src, out), 'Dropbox'
    m = re.search(r'/folders/([A-Za-z0-9_\-]{10,})', src) or re.search(r'[?&]id=([A-Za-z0-9_\-]{10,})', src)
    if 'drive.google.com' in src and m:
        tok = drive_token()
        files = drive_walk(tok, m.group(1))
        n = 0
        for f in files:
            safe = re.sub(r'[^\w.\- ]+', '_', (f.get('path', '') + f['name']))[-90:]
            try:
                if drive_get(tok, f, os.path.join(out, safe)):
                    n += 1
            except Exception:
                pass
        return n, 'папка Google Drive'
    m = re.search(r'/file/d/([A-Za-z0-9_\-]{10,})', src)
    if 'drive.google.com' in src and m:
        tok = drive_token()
        H = {'Authorization': 'Bearer ' + tok}
        meta = json.loads(urllib.request.urlopen(urllib.request.Request(
            'https://www.googleapis.com/drive/v3/files/%s?fields=id,name,mimeType' % m.group(1),
            headers=H), timeout=60).read())
        drive_get(tok, meta, os.path.join(out, re.sub(r'[^\w.\- ]+', '_', meta['name'])))
        return 1, 'файл Google Drive'
    if src.startswith('http'):
        ext = os.path.splitext(src.split('?')[0])[1].lower()
        if ext in (TEXTUAL | IMAGE):
            name = urllib.parse.unquote(os.path.basename(src.split('?')[0]))
            open(os.path.join(out, name), 'wb').write(
                urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=600).read())
            return 1, 'прямая ссылка'
        return from_page(src, out), 'веб-страница'
    return 0, 'не понял ссылку'


# ─────────────────────────── текст ───────────────────────────

def text_of(path, ocr_pages=12):
    """Текст файла. Если текстового слоя нет — распознаём страницы.

    Порог в 40 символов на страницу выбран по живым договорам: у сканов выходит
    ноль, у нормальных PDF — сотни."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        try:
            import fitz
        except ImportError:
            return '', 'нет PyMuPDF'
        d = fitz.open(path)
        txt = '\n'.join(p.get_text() for p in d)
        if len(txt.strip()) >= 40 * max(1, d.page_count):
            return txt, 'текстовый слой'
        if not os.path.exists(OCR):
            return txt, 'скан, распознаватель не собран (swiftc -O -o tools/ocr/plpocr tools/ocr/plpocr.swift)'
        tmp = path + '.pages'
        os.makedirs(tmp, exist_ok=True)
        pages = []
        for i, p in enumerate(d):
            if i >= ocr_pages:
                break
            f = os.path.join(tmp, 'p%03d.png' % i)
            if not os.path.exists(f):
                p.get_pixmap(dpi=220).save(f)
            pages.append(f)
        if not pages:
            return txt, 'пусто'
        r = subprocess.run([OCR] + pages, capture_output=True, text=True, timeout=900)
        return r.stdout, 'распознано со сканов (%d стр.)' % len(pages)
    if ext in IMAGE and os.path.exists(OCR):
        r = subprocess.run([OCR, path], capture_output=True, text=True, timeout=300)
        return r.stdout, 'распознано с картинки'
    if ext == '.docx':
        try:
            z = zipfile.ZipFile(path)
            x = z.read('word/document.xml').decode('utf-8', 'ignore')
            return re.sub(r'<[^>]+>', ' ', x), 'docx'
        except Exception as ex:
            return '', str(ex)[:60]
    if ext in ('.txt', '.csv', '.md', '.json'):
        return open(path, encoding='utf-8', errors='ignore').read(), 'текст'
    return '', 'не текстовый'


# ─────────────────────────── договор ───────────────────────────

NUM = r'[\d][\d,\. ]{4,}'


def money(s):
    v = re.sub(r'[^\d.]', '', str(s).replace(',', ''))
    v = v.split('.')[0] if v.count('.') > 1 else v
    try:
        return int(float(v))
    except Exception:
        return None


def parse_contract(text):
    """Поля договора. Ничего не досочиняем: чего нет — того нет.

    Эльнур: «в контракте обычно есть все детали, планировки и т.п. — такие данные
    уже должны собираться в кабинете у владельца». Поэтому берём и то, чего не было
    в прежнем разборе: этаж, корпус, форму владения, площадь участка."""
    t = re.sub(r'[ \t]+', ' ', text)
    out = {}

    m = re.search(r'(?:Unit|Room|Plot|Villa)\s*(?:\(s\))?\s*(?:No|#)\.?\s*[:\.]*\s*([A-Z]{0,3}[\- ]?\d{1,4}[A-Z]?)', t, re.I)
    if m:
        out['unit'] = m.group(1).replace(' ', '')
    m = re.search(r'Booking\s*No\.?\s*[:\.]*\s*([A-Z0-9\-]{4,})', t, re.I)
    if m:
        out['booking_no'] = m.group(1)
    m = re.search(r'Floor\s*(?:Level)?\s*[:\.]*\s*(\d{1,3})', t, re.I)
    if m:
        out['floor'] = int(m.group(1))
    m = re.search(r'(?:Building|Tower|Block|Корпус)\s*[:\.]*\s*([A-Z0-9]{1,3})\b', t, re.I)
    if m:
        out['building'] = m.group(1)

    m = (re.search(r'(?:House|Built[- ]?up|Internal|Unit)\s*(?:Area\s*)?(?:Size)?\s*\(?(?:SQ\.?M|sqm|м²)\)?\s*[:\.]*\s*(' + NUM + r')', t, re.I)
         or re.search(r'(' + NUM + r')\s*(?:SQ\.?\s?M|sqm|кв\.?\s?м|м²)', t, re.I))
    if m:
        a = money(m.group(1))
        if a and 10 <= a <= 5000:
            out['area_sqm'] = a
    m = re.search(r'Land\s*(?:Area\s*)?(?:Size)?\s*\(?(?:SQ\.?M|sqm)\)?\s*[:\.]*\s*(' + NUM + r')', t, re.I)
    if m:
        a = money(m.group(1))
        if a and 30 <= a <= 20000:
            out['plot_sqm'] = a
    m = re.search(r'(\d)\s*(?:bed ?rooms?|BR\b|спальн)', t, re.I)
    if m:
        out['bedrooms'] = int(m.group(1))

    m = (re.search(r'Total\s*Selling\s*Price[^\d฿]{0,20}[฿B]?\s*(' + NUM + r')', t, re.I)
         or re.search(r'(?:Selling|Purchase|Total)\s*Price[^\d฿]{0,20}[฿B]?\s*(' + NUM + r')', t, re.I))
    if m:
        p = money(m.group(1))
        if p and p > 100000:
            out['price'] = p
    if re.search(r'lease ?hold|аренд\w* прав|30\s*(?:\+\s*30)+', t, re.I):
        out['ownership'] = 'leasehold'
    if re.search(r'free ?hold|фрихолд', t, re.I):
        out['ownership'] = 'freehold' if 'ownership' not in out else 'leasehold + freehold'

    # Табличная строка виллы: «A12  187.00  ฿4,650,000.00  252.50  ฿13,950,000.00»
    # — номер, участок, цена участка, дом, цена дома. Именно так печатает бронь
    # The Title: отдельных подписей «Unit No.» в таблице нет.
    m = re.search(r'\b([A-Z]{0,2}\d{1,4}[A-Z]?)\s+(' + NUM + r')\s*[฿B]\s*(' + NUM + r')\s+(' + NUM + r')\s*[฿B]\s*(' + NUM + r')', t)
    if m:
        land, house = money(m.group(2)), money(m.group(4))
        out.setdefault('unit', m.group(1))
        if land and 30 <= land <= 20000:
            out.setdefault('plot_sqm', land)
        if house and 10 <= house <= 5000:
            out.setdefault('area_sqm', house)

    m = re.search(r'Date\s*[:\.]*\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d)', t)
    if m:
        out['contract_date'] = m.group(1)
    # «Payable on the date of transfer of the Ownership Within...July-September 2026»
    m = (re.search(r'transfer of the Ownership[^\n]{0,40}?((?:[A-Z][a-z]{2,9}\s*[-–]\s*)?[A-Z][a-z]{2,9}\s+20\d\d)', t)
         or re.search(r'(?:handover|completion|передач\w*)[^\n.]{0,40}?((?:Q[1-4]\s*)?20\d\d)', t, re.I))
    if m:
        out['handover'] = m.group(1).strip()

    pays = []
    for m in re.finditer(r'(Booking Deposit|Contract Payment|[1-9](?:st|nd|rd|th)?[\'"]?\s*Installment[^,\n]{0,24}|'
                         r'last payment)[^\d฿]{0,40}[฿B]?\s*(' + NUM + r')'
                         r'(?:[^\n]{0,60}?(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d|[A-Z][a-z]+\s*[-–]\s*[A-Z][a-z]+\s+20\d\d))?',
                         t, re.I):
        amt = money(m.group(2))
        if amt and amt > 1000:
            pays.append({'note': re.sub(r'\s+', ' ', m.group(1)).strip(),
                         'amount': amt, 'date': (m.group(3) or '').strip() or None})
    if pays:
        out['payments'] = pays[:12]
    return out


# ─────────────────────────── запуск ───────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__.strip().split('\n\n')[0])
        print('\n    python3 tools/grab.py <ссылка> [--text] [--contract]')
        return 2
    src = args[0]
    want_text = '--text' in sys.argv or '--contract' in sys.argv
    want_contract = '--contract' in sys.argv
    out = os.path.join(CACHE, re.sub(r'[^\w]+', '_', src)[-70:])
    n, how = fetch_all(src, out)
    print('Источник: %s → файлов %d' % (how, n))
    print('Кэш: %s\n' % out)
    files = sorted(os.path.join(out, f) for f in os.listdir(out)
                   if os.path.isfile(os.path.join(out, f)))
    print('%-52s %-10s %9s' % ('файл', 'что это', 'размер'))
    for f in files:
        print('%-52s %-10s %8dК' % (os.path.basename(f)[:52], kind_of(os.path.basename(f)),
                                    os.path.getsize(f) // 1024))
    if not want_text:
        print('\nВынуть текст: --text, разобрать договор: --contract')
        return 0
    for f in files:
        if os.path.splitext(f)[1].lower() not in (TEXTUAL | IMAGE):
            continue
        txt, how2 = text_of(f)
        print('\n─── %s  [%s, символов %d]' % (os.path.basename(f)[:60], how2, len(txt)))
        if want_contract and txt:
            d = parse_contract(txt)
            if d:
                for k, v in d.items():
                    print('    %-14s %s' % (k, json.dumps(v, ensure_ascii=False)[:150]))
            else:
                print('    полей договора не нашлось')
        elif txt:
            print('    ' + re.sub(r'\s+', ' ', txt)[:300] + '…')
    return 0


if __name__ == '__main__':
    sys.exit(main())
