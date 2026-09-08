#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Наполнение карточки объекта материалами застройщика с Google Диска.

Как это работает:
  1. Папку проекта перечисляет n8n (у него полный доступ к Диску) — WF_drive_scout.
  2. Подпапки раскладываются по видам: рендеры, интерьеры, мастер-план, планировки.
  3. Файлы качаются напрямую и СРАЗУ ужимаются — оригиналы не храним.
  4. Заливка и запись в карточку — тем же инструментом, что и всегда (photos.py).

Запуск:
    python3 tools/drive_pull.py --folder <id папки проекта> --id PLP-VIVANA
    python3 tools/drive_pull.py --folder <id> --id PLP-VIVANA --dry     # только показать план
    python3 tools/drive_pull.py --list <id папки>                       # что внутри

Требуется включённый WF_drive_scout (после работы его выключают обратно).
"""
import argparse, json, os, pathlib, re, subprocess, sys, urllib.request

SCOUT = 'https://proplib.app.n8n.cloud/webhook/drive-scout'
KEYFILE = os.path.expanduser('~/.plp_webhook_key')
IMG = re.compile(r'\.(jpe?g|png|webp)$', re.I)
MAX_PER_KIND = 10          # больше витрине не нужно, а место и трафик бережём

# в эти папки не заходим: там не витрина, а служебное и чужое
SKIP_FOLDER = re.compile(
    r'event|видео|video|logo|логотип|contact|payment|company\s*profile|'
    r'furniture|living\s*serv|360|walkthrough|map|карта|price|прайс|'
    r'location|локац|site\s*visit|участок|land\s*photo|progress|прогресс|'
    r'construction\s*photo|стройк|floor\s*view|view\s*from|вид\s*из', re.I)

# по имени подпапки понимаем, что это за снимки
KIND_BY_FOLDER = [
    ('master',     re.compile(r'master\s*plan|site\s*plan|генплан|мастер', re.I)),
    ('plans',      re.compile(r'floor\s*plan|unit\s*plan|layout|планиров', re.I)),
    ('facilities', re.compile(r'facilit|amenit|clubhouse|инфраструктур', re.I)),
    ('interior',   re.compile(r'interior|интерьер|room|living', re.I)),
    ('exterior',   re.compile(r'exterior|perspective|aerial|building|фасад|рендер', re.I)),
    ('interior',   re.compile(r'show\s*unit|show\s*room|шоу.?рум', re.I)),
]


def key():
    return pathlib.Path(KEYFILE).read_text().strip()


def scout(q):
    req = urllib.request.Request(SCOUT, data=json.dumps({'q': q}).encode(),
                                 headers={'x-plp-key': key(), 'Content-Type': 'application/json'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=120))
    except Exception as e:
        sys.exit('Диск не ответил: %s\nПроверьте, включён ли WF_drive_scout.' % str(e)[:120])
    return r.get('files') or []


def children(fid):
    return scout("'%s' in parents and trashed=false" % fid)


def walk(fid, kind=None, depth=0, seen=None):
    """Спускаемся по подпапкам и запоминаем, к какому виду относится каждый файл."""
    out = []
    seen = seen if seen is not None else set()
    if fid in seen or depth > 3:
        return out
    seen.add(fid)
    for f in children(fid):
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            if SKIP_FOLDER.search(f['name']):
                continue
            k = kind
            for name, rx in KIND_BY_FOLDER:
                if rx.search(f['name']):
                    k = name
                    break
            out += walk(f['id'], k, depth + 1, seen)
        elif IMG.search(f['name']):
            k = kind
            if not k:
                for name, rx in KIND_BY_FOLDER:
                    if rx.search(f['name']):
                        k = name
                        break
            out.append({'id': f['id'], 'name': f['name'], 'kind': k or 'exterior',
                        'size': int(f.get('size') or 0),
                        'render': 1 if re.search(r'perspect|render|рендер|3d', f['name'], re.I) else 0})
    return out


def download(fid, dst):
    url = 'https://drive.google.com/uc?export=download&id=%s&confirm=t' % fid
    r = subprocess.run(['curl', '-sL', '-m', '180', url, '-o', str(dst)], capture_output=True)
    if r.returncode != 0 or not dst.exists() or dst.stat().st_size < 3000:
        return False
    head = dst.open('rb').read(8)
    return head[:3] == b'\xff\xd8\xff' or head[:8] == b'\x89PNG\r\n\x1a\n' or head[:4] == b'RIFF'


def main():
    ap = argparse.ArgumentParser(description='Материалы застройщика с Диска в карточку объекта')
    ap.add_argument('--folder', help='id папки проекта на Диске')
    ap.add_argument('--id', help='PLP-код объекта')
    ap.add_argument('--list', dest='listing', help='показать содержимое папки и выйти')
    ap.add_argument('--dry', action='store_true', help='показать план, ничего не качать')
    ap.add_argument('--max', type=int, default=MAX_PER_KIND, help='сколько снимков брать на вид')
    a = ap.parse_args()

    if a.listing:
        for f in children(a.listing):
            mark = '📁' if f['mimeType'].endswith('folder') else '  '
            mb = int(f.get('size') or 0) / 1048576
            print('%s %-56s %s' % (mark, f['name'][:56], ('%.1f МБ' % mb) if mb else ''))
        return
    if not a.folder or not a.id:
        ap.error('нужны --folder и --id (или --list)')

    files = walk(a.folder)
    if not files:
        sys.exit('в папке нет изображений — проверьте id и доступ')
    by = {}
    for f in files:
        by.setdefault(f['kind'], []).append(f)
    print('нашёл на Диске:', ', '.join('%s: %d' % (k, len(v)) for k, v in by.items()))

    plan = {}
    for k, v in by.items():
        # сначала рендеры (их видно по имени), потом всё остальное по величине
        v.sort(key=lambda x: (-x.get('render', 0), -x['size']))
        plan[k] = v[:a.max]
    print('возьму:', ', '.join('%s: %d' % (k, len(v)) for k, v in plan.items()))
    if a.dry:
        for k, v in plan.items():
            for f in v:
                print('   %-12s %s' % (k, f['name'][:60]))
        return

    dst = pathlib.Path('/tmp/plp_drive_pull') / a.id
    if dst.exists():
        for p in dst.rglob('*'):
            if p.is_file():
                p.unlink()
    got = 0
    for k, v in plan.items():
        (dst / k).mkdir(parents=True, exist_ok=True)
        for f in v:
            ext = '.png' if f['name'].lower().endswith('.png') else '.jpg'
            p = dst / k / (re.sub(r'[^A-Za-z0-9._-]+', '_', f['name'])[:40] + ext)
            if download(f['id'], p):
                got += 1
            else:
                print('   не скачался:', f['name'][:50])
                if p.exists():
                    p.unlink()
    print('скачал файлов:', got)
    if not got:
        sys.exit('ничего не скачалось')

    here = pathlib.Path(__file__).parent
    subprocess.run([sys.executable, str(here / 'photos.py'), str(dst), '--id', a.id])


if __name__ == '__main__':
    main()
