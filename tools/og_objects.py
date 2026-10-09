# -*- coding: utf-8 -*-
# Фирменные превью ссылок 1200×630 для страниц объектов и главных страниц (09.10.2026).
# Эльнур: «смотрю другие ссылки, превью некрасивое… чтобы все превью ссылок были всегда красивыми».
# Образец — tools/og_cards.py (листы-офферы): фото слева, справа знак PLP, район, название, цена, плашка.
#
#   python3 tools/og_objects.py            # карточки объектов, только недостающие → img/og/<код>.jpg
#   python3 tools/og_objects.py --force    # пересобрать все
#   python3 tools/og_objects.py --pages    # карточки главных страниц → img/og/page-<имя>.jpg
#   python3 tools/og_objects.py heritage kye-r1   # только эти (по адресу страницы)
#
# Цена берётся из objects.price_from_thb (Supabase). Нет цены — карточка без цены, ничего не выдумываем.
# Внутренний код с номером юнита в имя файла и текст не попадает: только публичный код.
# Рендер: один Chrome на пачку из 10 карточек, никогда два одновременно (Мак 8 ГБ).
import os, re, sys, json, time, shutil, subprocess, tempfile, urllib.request, html as H

SITE = os.path.expanduser('~/plp-site')
OUT = os.path.join(SITE, 'img', 'og')
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
LOGO = os.path.join(SITE, 'offers/vibe2/img/plp-logo-ink.webp')
CACHE = os.path.expanduser('~/.cache/plp-og')
BATCH = 10

# Тот же словарь, что в build/gen.mjs (DISTRICT_RU). Незнакомый район не переводим наугад — надзаголовок пустой.
DISTRICT_RU = {
    'Rawai': 'Равай', 'Bang Tao': 'Банг Тао', 'Nai Yang': 'Най Янг', 'Surin': 'Сурин', 'Koh Kaew': 'Ко Кео',
    'Kamala': 'Камала', 'Kata': 'Ката', 'Layan': 'Лаян', 'Patong': 'Патонг', 'Cherng Talay': 'Чернг Талай',
    'Nai Harn': 'Най Харн', 'Laguna': 'Лагуна', 'Kamala Beach': 'Камала', 'Nai Thon': 'Най Тон',
    'Thalang': 'Таланг', 'Mai Khao': 'Май Кхао', 'Karon': 'Карон', 'Naiharn': 'Найхарн',
}

# Главные страницы: имя → (фото, надзаголовок, заголовок, подзаголовок, сдвиг кадра)
PAGES = {
    'index':        ('img/PLP-GARRYA.jpg', 'Пхукет', 'Property Library Phuket', 'Недвижимость Пхукета для жизни и дохода', 'center'),
    'buy':          ('img/PLP-INTERCONTINENTAL.jpg', 'Кондо и виллы', 'Купить на Пхукете', '', 'center'),
    'rent':         ('img/PLP-ZENITHY.jpg', 'Виллы и апартаменты', 'Аренда на Пхукете', '', 'center'),
    'management':   ('img/management-hero-1600.webp', 'Для собственников', 'Управление и сдача', '', 'center'),
    'about':        ('img/elnur-founder-beige.jpg', 'Property Library Phuket', 'О нас', 'Подбор и сопровождение сделки на Пхукете', 'center 18%'),
    'predstart':    ('img/PLP-EDEN-LAKE.jpg', 'До старта продаж', 'Закрытые предложения', '', 'center'),
    'add-property': ('img/PLP-TONINO-OV.jpg', 'Для собственников', 'Добавить объект', 'Сдать или продать на Пхукете', 'center'),
    'default':      ('img/PLP-ANGSANA-TOPAZ.jpg', 'Пхукет', 'Property Library Phuket', 'Недвижимость Пхукета для жизни и дохода', 'center'),
}

# У объекта нет своего кадра в img/ — берём фото с его листа-оффера, если лист есть.
FALLBACK_PHOTO = {'PLP-FIZZ': 'offers/fizz/img/f-pool.webp', 'PLP-KUARTZ': 'offers/kuartz/img/k-pool2.webp'}


def sb(sql):
    tok = open(os.path.expanduser('~/.plp_sb_mgmt')).read().strip()
    r = urllib.request.Request('https://api.supabase.com/v1/projects/dyxufgjrumebvrhadjun/database/query',
                               data=json.dumps({'query': sql}).encode(),
                               headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json',
                                        'User-Agent': 'plp-og/1.0'})
    return json.load(urllib.request.urlopen(r, timeout=60))


def fonts_css():
    """Manrope один раз скачивается в ~/.cache/plp-og: 115 запросов к Google на пачку медленно,
    а один сорвавшийся даёт карточку шрифтом Arial."""
    os.makedirs(CACHE, exist_ok=True)
    css_path = os.path.join(CACHE, 'manrope.css')
    if not os.path.exists(css_path):
        ua = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36'
        req = urllib.request.Request('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=block',
                                     headers={'User-Agent': ua})
        css = urllib.request.urlopen(req, timeout=30).read().decode()
        for u in sorted(set(re.findall(r'url\((https://[^)]+)\)', css))):
            fn = os.path.join(CACHE, u.rsplit('/', 1)[-1])
            if not os.path.exists(fn):
                open(fn, 'wb').write(urllib.request.urlopen(u, timeout=30).read())
            css = css.replace(u, 'file://' + fn)
        open(css_path, 'w').write(css)
    return open(css_path).read()


def short_name(n):
    # «… · квартира», «… · вилла, вторичка» — приписка юнита, её отрезаем; «Eden · Lake Residences» — часть имени
    n = re.sub(r'\s+·\s+(квартира|вилла|таунхаус)\b.*$', '', n or '')
    n = re.sub(r'\s+·\s+', ' ', n)
    n = re.sub(r',\s*[А-ЯЁа-яё][^,]*$', '', n)          # «KUARTZ, Карон» → «KUARTZ»
    n = re.sub(r',\s*у\s+.*$', '', n)                    # «The GENS by Botanica, у Blue Tree»
    n = re.sub(r',\s*(Autograph Collection Residences)$', '', n)
    return n.strip()


PRESTART_SQM = {'PLP-KUARTZ', 'PLP-FIZZ'}  # закрытый старт: застройщик объявит прайс на старте


def price_mln(v):
    if not v:
        return ''
    m = int(float(v)) // 10000 / 100                     # отсекаем, а не округляем вверх: «от» не завышаем
    s = ('%.2f' % m).rstrip('0').rstrip('.').replace('.', ',')
    return 'от %s млн ฿' % s


def fmt_word(o, unit):
    t = str(o.get('type') or '').lower()
    if str(o.get('purpose') or '').lower() in ('аренда', 'rent'):
        return 'аренда'
    if t.startswith('вилл') or t.startswith('vill'):
        return 'вилла' if unit else 'виллы'
    if t.startswith('таун') or t.startswith('town'):
        return 'таунхаус' if unit else 'таунхаусы'
    return 'квартира' if unit else 'кондо'


T = '''<!doctype html><html><head><meta charset="utf-8"><style>{{fonts}}
*{margin:0;box-sizing:border-box}body{width:1200px;background:#EFECE2;font-family:Manrope,Arial,sans-serif}
.card{width:1200px;height:630px;display:flex;overflow:hidden;background:#EFECE2}
.ph{width:690px;height:630px;flex:none}.ph img{width:100%;height:100%;object-fit:cover;display:block}
.tx{width:510px;padding:46px 44px 40px;display:flex;flex-direction:column;overflow:hidden}.logo{height:46px;width:auto;align-self:flex-start;flex:none}
.ey{margin-top:auto;font-size:19px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5E6B35}
h1{font-weight:800;line-height:1.04;color:#1F1F1A;margin:12px 0 20px;overflow-wrap:anywhere}
.sub{font-size:28px;line-height:1.25;font-weight:700;color:#3A3A32}
.pr{font-size:38px;font-weight:800;color:#1F1F1A}.tag{margin-top:16px;align-self:flex-start;background:#5E6B35;color:#fff;font-size:20px;font-weight:700;padding:9px 16px;border-radius:8px}
.ft{margin-top:26px;font-size:16px;color:#6B6A60;font-weight:500;flex:none}</style></head><body>{{cards}}
<script>
document.fonts.ready.then(function(){
  document.querySelectorAll('.card').forEach(function(c){
    var h=c.querySelector('h1'), tx=c.querySelector('.tx'), fs=parseInt(h.dataset.fs,10);
    function bad(){ var lh=fs*1.04; return h.scrollWidth>h.clientWidth+1 || h.offsetHeight>lh*3+2 || tx.scrollHeight>tx.clientHeight+1; }
    h.style.fontSize=fs+'px';
    while(bad() && fs>30){ fs-=2; h.style.fontSize=fs+'px'; }
    c.dataset.ok = bad() ? '0' : '1';
  });
  document.title='done';
});
</script></body></html>'''


def nobr(t):
    """Короткий предлог или союз не висит в конце строки: «Купить на / Пхукете» → «Купить / на Пхукете»."""
    return re.sub(r'(?<![\w])(на|и|в|во|с|со|к|у|о|об|для|или|до|от|по|за|из|at|by|of|La|The)\s+', lambda m: m.group(1) + '\u00a0', t)


def card_html(photo, ey, title, price, tag, foot, sub='', pos='center'):
    title, sub = nobr(title), nobr(sub)
    longest = max((len(w) for w in title.split()), default=1)
    fs = 72 if len(title) <= 10 else (60 if len(title) <= 18 else 50)
    fs = min(fs, int(420 / (0.62 * longest)))
    parts = ['<div class="card"><div class="ph"><img src="file://%s" style="object-position:%s"></div><div class="tx">' % (H.escape(photo), pos),
             '<img class="logo" src="file://%s">' % H.escape(LOGO),
             '<div class="ey">%s</div>' % H.escape(ey),
             '<h1 data-fs="%d">%s</h1>' % (fs, H.escape(title))]
    if sub:
        parts.append('<div class="sub">%s</div>' % H.escape(sub))
    if price:
        parts.append('<div class="pr">%s</div>' % H.escape(price))
    if tag:
        parts.append('<div class="tag">%s</div>' % H.escape(tag))
    parts.append('<div class="ft">%s</div></div></div>' % H.escape(foot))
    return ''.join(parts)


def render(jobs):
    """jobs: [(имя файла, html карточки)] → пачками по BATCH через один Chrome."""
    css = fonts_css()
    tmp = tempfile.mkdtemp(prefix='plp-og-')
    made = []
    try:
        for b in range(0, len(jobs), BATCH):
            chunk = jobs[b:b + BATCH]
            page = T.replace('{{fonts}}', css).replace('{{cards}}', ''.join(h for _, h in chunk))
            f = os.path.join(tmp, 'batch.htm'); open(f, 'w', encoding='utf-8').write(page)
            png = os.path.join(tmp, 'batch.png')
            if os.path.exists(png): os.remove(png)
            prof = tempfile.mkdtemp(prefix='plp-og-prof-')
            pr = subprocess.Popen([CH, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                                   '--user-data-dir=' + prof, '--window-size=1200,%d' % (630 * len(chunk)),
                                   '--virtual-time-budget=8000', '--screenshot=' + png, 'file://' + f],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                last = -1
                for _ in range(90):
                    time.sleep(1)
                    if os.path.exists(png):
                        sz = os.path.getsize(png)
                        if sz > 50000 and sz == last: break
                        last = sz
            finally:
                pr.kill(); pr.wait(); shutil.rmtree(prof, ignore_errors=True)
            if not os.path.exists(png):
                print('  пачка %d: Chrome не дал снимок' % (b // BATCH + 1)); continue
            for i, (name, _) in enumerate(chunk):
                out = os.path.join(OUT, name)
                for q in (3, 4, 5, 6):
                    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', png, '-vf', 'crop=1200:630:0:%d' % (630 * i),
                                    '-q:v', str(q), out], check=True)
                    if os.path.getsize(out) < 290000: break   # WhatsApp молча бросает картинку тяжелее 300 КБ
                made.append(out)
            print('  пачка %d: %d карточек' % (b // BATCH + 1, len(chunk)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return made


def object_jobs(only, force):
    pages = {f[:-5] for f in os.listdir(os.path.join(SITE, 'object')) if f.endswith('.html')}
    rows = sb("select plp_property_id, public_code, name, district, beach, type, purpose, price_from_thb, price_per_sqm_thb, stage, parent_object_id "
              "from objects where on_site or purpose in ('аренда','rent')")
    jobs, skipped, nophoto, noey = [], 0, [], []
    seen = set()
    for o in rows:
        pub = o.get('public_code') or o.get('plp_property_id')
        slug = re.sub(r'^PLP-', '', pub).lower()
        if slug not in pages or slug in seen: continue
        if only and slug not in only: continue
        seen.add(slug)
        out = os.path.join(OUT, pub + '.jpg')
        if os.path.exists(out) and not force:
            skipped += 1; continue
        photo = os.path.join(SITE, 'img', pub + '.jpg')
        if not os.path.exists(photo):
            fb = FALLBACK_PHOTO.get(pub)
            photo = os.path.join(SITE, fb) if fb and os.path.exists(os.path.join(SITE, fb)) else None
        if not photo:
            nophoto.append(slug); continue
        en = o.get('district') or o.get('beach') or ''
        ey = DISTRICT_RU.get(en, '')
        if en and not ey: noey.append('%s (%s)' % (slug, en))
        unit = bool(o.get('parent_object_id'))
        rent = str(o.get('purpose') or '').lower() in ('аренда', 'rent')
        price = '' if rent else price_mln(o.get('price_from_thb'))
        # 09.10.2026: до официального прайса (закрытый старт) — ориентир за м², как на листах KUARTZ/FIZZ, без общей цены «от».
        if not rent and o.get('price_per_sqm_thb') and str(o.get('plp_property_id')) in PRESTART_SQM:
            price = '≈%d тыс. ฿ за м²' % round(float(o['price_per_sqm_thb']) / 1000)
        jobs.append((pub + '.jpg', card_html(photo, ey, short_name(o.get('name')), price, fmt_word(o, unit),
                                             'Property Library Phuket · для наших клиентов')))
    print('объектов со страницей: %d, к рендеру: %d, уже есть: %d' % (len(pages), len(jobs), skipped))
    if nophoto: print('без фото (карточки нет):', ', '.join(sorted(nophoto)))
    if noey: print('район без перевода (надзаголовок пустой):', ', '.join(noey))
    return jobs


def page_jobs(only):
    jobs = []
    for name, (ph, ey, t, sub, pos) in PAGES.items():
        if only and name not in only: continue
        jobs.append(('page-%s.jpg' % name, card_html(os.path.join(SITE, ph), ey, t, '', '', 'property-library.com', sub, pos)))
    return jobs


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    force = '--force' in args
    only = {a for a in args if not a.startswith('--')}
    jobs = page_jobs(only) if '--pages' in args else object_jobs(only, force)
    made = render(jobs)
    print('готово карточек:', len(made), '→', OUT)
