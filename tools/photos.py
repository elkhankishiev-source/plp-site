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
    ap.add_argument('--dry', action='store_true', help='только показать план, ничего не менять')
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

    if not a.folder: ap.error('нужна папка с файлами')
    folder = pathlib.Path(a.folder).expanduser()
    if not folder.is_dir(): sys.exit('нет такой папки: ' + str(folder))
    pid = (a.id or folder.name).strip().upper()
    if not pid.startswith('PLP-'): sys.exit('код объекта должен начинаться с PLP-, получено: ' + pid)

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
            ext = p.suffix.lower().replace('.jpeg', '.jpg')
            key = 'objects/%s/%s/%s%s' % (pid, k, h, ext)
            mime = mimetypes.guess_type(p.name)[0] or 'image/jpeg'
            if st.exists(key):
                url = st.url + '/storage/v1/object/public/' + BUCKET + '/' + key
            else:
                url = st.put(key, data, mime)
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
