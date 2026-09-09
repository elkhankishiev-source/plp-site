#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Заливка фотографий объекта в хранилище и запись их в карточку.

Порядок работы (канон catalog/media_upload_standard):
  1. Кладём файлы в папку с именем PLP-кода объекта или указываем --id.
  2. Раскладываем по видам: обложка, галерея, мастер-план, планировки,
     инфраструктура, ход стройки. Вид определяется по имени файла или по
     подпапке — руками ничего выбирать не нужно.
  3. Заливаем в бакет object-media по адресу objects/<PLP-ID>/<вид>/<файл>.
     Одинаковые файлы не заливаются дважды: сверяем по содержимому.
  4. Дописываем ссылки в карточку объекта: обложка, галерея, группы снимков,
     ход стройки. Существующие данные не затираются — дополняются.
  5. Отмечаем дату сверки, чтобы было видно, насколько карточка свежая.

Материалы застройщика часто приходят одним PDF — из него кадры достаются сами:
    python3 tools/photos.py --pdf ~/Downloads/ayana.pdf --id PLP-AYANA

Запуск:
    python3 tools/photos.py ~/Downloads/PLP-HERITAGE
    python3 tools/photos.py ~/Downloads/фото --id PLP-HERITAGE
    python3 tools/photos.py ~/Downloads/фото --id PLP-HERITAGE --kind plans
    python3 tools/photos.py --list          # что уже лежит у объектов

Ничего не удаляет и не публикует наружу. Пишет только в свой бакет и в поля
объекта, которые сам же и заполняет.
"""
import argparse, hashlib, json, mimetypes, os, pathlib, re, sys, urllib.request

BUCKET = 'object-media'
KINDS = {
    'cover':      ('обложка',        re.compile(r'(cover|обложк|main|hero|титул)', re.I)),
    'exterior':   ('территория',     re.compile(r'(exterior|facade|фасад|террит|вид|view|pool|бассейн)', re.I)),
    'interior':   ('интерьеры',      re.compile(r'(interior|интерьер|room|комнат|kitchen|кухн|bath|ванн|living|спальн|bedroom)', re.I)),
    'master':     ('мастер-план',    re.compile(r'(master|мастер.?план|siteplan|генплан)', re.I)),
    'plans':      ('планировки',     re.compile(r'(plan|layout|планиров|floor|этаж|тип\b|unit.?type)', re.I)),
    'facilities': ('инфраструктура', re.compile(r'(facilit|инфраструктур|amenit|gym|spa|lobby|clubhouse|kids)', re.I)),
    'progress':   ('ход стройки',    re.compile(r'(progress|стройк|construction|weekly|отчёт|отчет)', re.I)),
}
ORDER = ['cover', 'exterior', 'interior', 'facilities', 'master', 'plans', 'progress']
IMG = re.compile(r'\.(jpe?g|png|webp|heic)$', re.I)
MAX_W = 2000          # шире держать незачем: витрина отдаёт превью 760–1600
MAX_BYTES = 500_000   # 09.09: опущен с 900k — хранилище было занято на 69%, средний файл ~350k


def looks_like_image(data: bytes) -> bool:
    """Файл действительно картинка, а не страница входа Google и не ошибка."""
    if len(data) < 3000:
        return False
    head = data[:12]
    if head[:3] == b'\xff\xd8\xff':                    return True      # jpeg
    if head[:8] == b'\x89PNG\r\n\x1a\n':                return True      # png
    if head[:4] == b'RIFF' and data[8:12] == b'WEBP':   return True
    if head[4:12] in (b'ftypheic', b'ftypheix', b'ftypmif1'): return True
    return False


def shrink(data: bytes):
    """Уменьшаем до разумного размера прямо перед заливкой: оригинал не храним."""
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data))
        im = im.convert('RGB')
        if im.width > MAX_W:
            im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
        for q in (86, 78, 70, 62):
            buf = io.BytesIO()
            im.save(buf, 'JPEG', quality=q, optimize=True, progressive=True)
            out = buf.getvalue()
            if len(out) <= MAX_BYTES or q == 62:
                return out, 'image/jpeg'
    except Exception:
        pass
    return data, None


def creds():
    """Ключи берём из окружения, иначе из n8n — там они и живут."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if url and key:
        return url.rstrip('/'), key
    diag = pathlib.Path.home() / 'plp_diag.py'
    m = re.search(r'API_KEY = "([^"]+)"', diag.read_text()) if diag.exists() else None
    if not m:
        sys.exit('нет ключей: задайте SUPABASE_URL и SUPABASE_SERVICE_KEY')
    req = urllib.request.Request('https://proplib.app.n8n.cloud/api/v1/variables?limit=200',
                                 headers={'X-N8N-API-KEY': m.group(1)})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    v = {x['key']: x['value'] for x in data['data']}
    return v['SUPABASE_URL'].rstrip('/'), v['SUPABASE_SERVICE_KEY']


class Store:
    def __init__(self):
        self.url, self.key = creds()
        self.h = {'apikey': self.key, 'Authorization': 'Bearer ' + self.key}

    def rest(self, path, method='GET', body=None, prefer=None):
        h = dict(self.h); h['Content-Type'] = 'application/json'
        if prefer: h['Prefer'] = prefer
        req = urllib.request.Request(self.url + '/rest/v1/' + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers=h)
        r = urllib.request.urlopen(req, timeout=90)
        raw = r.read()
        return json.loads(raw) if raw else None

    def exists(self, key):
        req = urllib.request.Request(self.url + '/storage/v1/object/info/public/' + BUCKET + '/' + key,
                                     headers=self.h)
        try:
            urllib.request.urlopen(req, timeout=30); return True
        except Exception:
            return False

    def put(self, key, data, mime):
        h = dict(self.h); h['Content-Type'] = mime; h['x-upsert'] = 'true'
        req = urllib.request.Request(self.url + '/storage/v1/object/' + BUCKET + '/' + key,
                                     data=data, method='POST', headers=h)
        urllib.request.urlopen(req, timeout=300)
        return self.url + '/storage/v1/object/public/' + BUCKET + '/' + key


def kind_of(path: pathlib.Path, forced=None):
    if forced: return forced
    parent = path.parent.name.lower()
    for k in KINDS:
        if parent == k or KINDS[k][1].search(parent): return k
    for k in ORDER:
        if KINDS[k][1].search(path.name): return k
    return 'exterior'


def main():
    ap = argparse.ArgumentParser(description='Заливка фотографий объекта')
    ap.add_argument('folder', nargs='?', help='папка с файлами')
    ap.add_argument('--id', help='PLP-код объекта (иначе берётся из имени папки)')
    ap.add_argument('--kind', choices=list(KINDS), help='считать все файлы одним видом')
    ap.add_argument('--list', action='store_true', help='показать, что уже есть у объектов')
    ap.add_argument('--report', action='store_true', help='чего не хватает: по объектам на сайте')
    ap.add_argument('--dry', action='store_true', help='только показать план, ничего не менять')
    ap.add_argument('--pdf', help='взять кадры из PDF застройщика (презентация, буклет)')
    a = ap.parse_args()
    st = Store()

    if a.list:
        rows = st.rest('objects?select=plp_property_id,name,on_site,main_image_url,gallery_urls,photo_groups'
                       '&order=plp_property_id')
        print('%-24s %-34s %-6s %-8s %s' % ('ID', 'название', 'сайт', 'обложка', 'фото/групп'))
        for o in rows:
            g = o.get('gallery_urls') or []
            gr = o.get('photo_groups') or []
            print('%-24s %-34s %-6s %-8s %d/%d' % (
                o['plp_property_id'], (o.get('name') or '')[:32],
                'да' if o.get('on_site') else '—',
                'есть' if o.get('main_image_url') else 'НЕТ',
                len(g) if isinstance(g, list) else 0, len(gr) if isinstance(gr, list) else 0))
        return

    # Отчёт по нехватке: что просить у застройщика в первую очередь.
    # Разделы важны по-разному, поэтому и спрос с них разный.
    if a.report:
        rows = st.rest('objects?select=plp_property_id,name,on_site,main_image_url,gallery_urls,photo_groups'
                       '&on_site=is.true&order=plp_property_id')
        # обложка засчитывается по main_image_url: у старых карточек её ставили
        # до того, как появились разделы, и группы cover у них просто нет
        NEED = [('exterior', 'территория'), ('interior', 'интерьеры'),
                ('master', 'мастер-план'), ('plans', 'планировки')]
        holes = []
        for o in rows:
            have = {}
            for grp in (o.get('photo_groups') or []):
                if isinstance(grp, dict):
                    have[grp.get('key')] = len(grp.get('urls') or [])
            if not have and (o.get('gallery_urls') or []):
                have['exterior'] = len(o['gallery_urls'])   # старые карточки без разделов
            miss = [ru for k, ru in NEED if not have.get(k)]
            if not o.get('main_image_url'):
                miss.insert(0, 'обложка')
            total = sum(have.values()) + (1 if o.get('main_image_url') and not have.get('cover') else 0)
            holes.append((total, o['plp_property_id'], (o.get('name') or '')[:30], miss))
        holes.sort()
        print('Объекты на сайте: %d. Сначала те, где снимков меньше всего.\n' % len(rows))
        print('%-22s %-32s %-6s %s' % ('ID', 'название', 'фото', 'чего нет'))
        for total, pid, name, miss in holes:
            print('%-22s %-32s %-6d %s' % (pid, name, total, ', '.join(miss) if miss else '— всё есть'))
        pust = [h for h in holes if h[0] == 0]
        if pust:
            print('\nБез единого снимка: %d — с них и начинать.' % len(pust))
        return

    # Материалы застройщика часто приходят одним PDF. Достаём встроенные кадры:
    # это исходные рендеры без наложенного текста — ровно то, что нужно витрине.
    if a.pdf:
        src = pathlib.Path(a.pdf).expanduser()
        if not src.is_file(): sys.exit('нет файла: ' + str(src))
        head = src.open('rb').read(5)
        if head[:4] != b'%PDF':
            sys.exit('это не PDF, а похоже на страницу входа — откройте доступ к файлу и скачайте заново')
        try:
            import fitz
        except ImportError:
            sys.exit('нужен модуль PyMuPDF: pip3 install pymupdf')
        dst = pathlib.Path('/tmp/plp_pdf_shots'); dst.mkdir(exist_ok=True)
        # 07.09: падало с PermissionError, если внутри остались подпапки от
        # прошлого отбора (exterior/facilities/plans). Чистим и файлы, и папки.
        import shutil
        for old in dst.iterdir():
            shutil.rmtree(old) if old.is_dir() else old.unlink()
        doc = fitz.open(src)
        seen, got = set(), 0
        for i, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen: continue
                seen.add(xref)
                try: d = doc.extract_image(xref)
                except Exception: continue
                w, hgt = d.get('width', 0), d.get('height', 0)
                if w < 1200 or hgt < 700: continue          # мелочь и иконки не берём
                ratio = w / max(hgt, 1)
                if ratio < 1.1 or ratio > 2.4: continue     # обрезки и полоски пропускаем
                (dst / ('p%02d_%d.%s' % (i + 1, xref, d.get('ext', 'jpg')))).write_bytes(d['image'])
                got += 1
        print('из PDF отобрано кадров:', got, '→', dst)
        if not got: sys.exit('в этом PDF нет крупных кадров — пришлите папку с фото')
        a.folder = str(dst)

    if not a.folder: ap.error('нужна папка с файлами')
    folder = pathlib.Path(a.folder).expanduser()
    if not folder.is_dir(): sys.exit('нет такой папки: ' + str(folder))
    pid = (a.id or folder.name).strip().upper()
    # Коды бывают не только PLP-: вторичка заводится как RESALE-…, приём с Диска
    # как INTAKE-…. Проверяем не приставку, а что объект вообще есть в базе.
    if not re.match(r'^[A-Z][A-Z0-9]*-[A-Z0-9-]+$', pid):
        sys.exit('код объекта выглядит странно: ' + pid)

    obj = st.rest('objects?plp_property_id=eq.' + urllib.parse.quote(pid) +
                  '&select=plp_property_id,name,main_image_url,gallery_urls,photo_groups,build_progress')
    if not obj: sys.exit('объекта ' + pid + ' нет в базе — заведите карточку до заливки фото')
    obj = obj[0]
    print('объект:', pid, '·', obj.get('name') or '')

    files = sorted([p for p in folder.rglob('*') if p.is_file() and IMG.search(p.name)])
    if not files: sys.exit('в папке нет изображений')

    seen_hash = set()
    by_kind = {}
    for p in files:
        data = p.read_bytes()
        h = hashlib.sha256(data).hexdigest()[:16]
        if h in seen_hash:             # один и тот же файл в двух местах
            continue
        seen_hash.add(h)
        by_kind.setdefault(kind_of(p, a.kind), []).append((p, data, h))

    plan = ', '.join('%s: %d' % (KINDS[k][0], len(v)) for k, v in by_kind.items())
    print('нашёл:', plan)
    if a.dry: return

    added = {k: [] for k in by_kind}
    for k, items in by_kind.items():
        for p, data, h in items:
            if not looks_like_image(data):
                print('   пропуск (это не изображение, похоже на страницу входа):', p.name)
                continue
            small, forced = shrink(data)
            ext = '.jpg' if forced else p.suffix.lower().replace('.jpeg', '.jpg')
            mime = forced or (mimetypes.guess_type(p.name)[0] or 'image/jpeg')
            key = 'objects/%s/%s/%s%s' % (pid, k, h, ext)
            if st.exists(key):
                url = st.url + '/storage/v1/object/public/' + BUCKET + '/' + key
            else:
                url = st.put(key, small, mime)
            added[k].append(url)
        print('  %-16s %d файлов' % (KINDS[k][0], len(added[k])))

    # 4. дописываем в карточку, ничего не затирая
    gallery = list(obj.get('gallery_urls') or [])
    groups = list(obj.get('photo_groups') or [])
    prog = obj.get('build_progress') or {}
    patch = {}

    cover = (added.get('cover') or added.get('exterior') or [None])[0]
    if cover and not obj.get('main_image_url'):
        patch['main_image_url'] = cover

    for k in ORDER:
        if k in ('progress',) or k not in added: continue
        for u in added[k]:
            if u not in gallery: gallery.append(u)
        name = KINDS[k][0].capitalize()
        grp = next((g for g in groups if isinstance(g, dict) and g.get('key') == k), None)
        if grp is None:
            groups.append({'key': k, 'name': name, 'urls': list(added[k])})
        else:
            grp['urls'] = list(dict.fromkeys(list(grp.get('urls') or []) + added[k]))
    if gallery: patch['gallery_urls'] = gallery[:40]
    if groups: patch['photo_groups'] = groups

    if 'progress' in added:
        photos = list(dict.fromkeys(list(prog.get('photos') or []) + added['progress']))
        prog['photos'] = photos[:24]
        patch['build_progress'] = prog

    patch['last_synced_at'] = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    st.rest('objects?plp_property_id=eq.' + urllib.parse.quote(pid), 'PATCH', patch,
            prefer='return=minimal')
    print('карточка обновлена: обложка %s, в галерее %d, групп %d, стройка %d' % (
        'есть' if (patch.get('main_image_url') or obj.get('main_image_url')) else 'нет',
        len(patch.get('gallery_urls') or gallery), len(groups),
        len((patch.get('build_progress') or prog).get('photos') or [])))
    print('дальше: node build/all.mjs — и фото появятся на сайте')


if __name__ == '__main__':
    import urllib.parse
    main()
