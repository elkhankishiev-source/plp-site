#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обложка карточки: кадр, по которому видно, что продаётся.

Эльнур 20.09.2026: «на некоторые объекты залиты странные фотки с китайскими
буквами… или вид издалека здание, там даже не понятно, что продаётся. Сверка
полная!»

Сверка сделана: все 93 обложки просмотрены подряд, контактным листом. Нашлось
три беды, и все три — одного корня. Обложку никто не выбирал: карточка брала
первый кадр из галереи, а он ложился туда как пришёл от застройщика.

  1. СЪЁМКА С ДРОНА. Комплекс снят с километра — крыши среди зелени. Красиво и
     бесполезно: покупатель не видит ни дома, ни двора. Так стояли Casa de Monte,
     Hythe, Angsana Topaz, Garrya, Angsana Beach, Sierra, Ayana, Vibe Karon.
  2. МАСТЕРПЛАН. Схема участка сверху вместо фотографии: Eden, Eden Residences,
     Clover.
  3. РЕКЛАМНЫЙ ЛИСТ. Кадр с чужим текстом поверх: Estella (надписи «Private Pool»
     во весь кадр), Sierra (баннер с моделью), Qabalah (пустая арка въезда).

Что делает скрипт. Записывает в objects.main_image_url тот кадр, который выбран
глазами по галерее объекта. Сборка (build/gen.mjs, heroGallery) с 21.09 ставит
главный кадр первым в ленте карточки — до этого поле main_image_url вообще ни на
что не влияло, и поменять обложку из базы было нельзя.

Никакие фото не удаляются и не переснимаются: меняется только очередь.

    python3 set_cover_photos.py            # показать, что поменяется
    python3 set_cover_photos.py --apply    # записать
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv

# объект → номер кадра в его нынешней ленте, который станет обложкой
ВЫБОР = {
    'PLP-CASADEMONTE':   (1, 'вилла с аркой вблизи вместо посёлка с дрона'),
    'PLP-HYTHE':         (5, 'фасад с бассейном вместо мастерплана'),
    'PLP-ANGSANA-TOPAZ': (6, 'корпус над водой вместо панорамы гольф-поля'),
    'PLP-GARRYA':        (2, 'корпуса и бассейн вместо пляжа с высоты'),
    'PLP-ANGSANA-BEACH': (4, 'здание вблизи вместо береговой линии'),
    'PLP-SIERRA':        (5, 'фасад вместо съёмки долины'),
    'PLP-AYANA':         (1, 'входная группа вместо комплекса среди джунглей'),
    'PLP-VIVANA':        (4, 'фасад с фонтаном вместо аквапарка крупным планом'),
    'PLP-VIBE-KARON':    (1, 'зона отдыха вместо панорамы Карона'),
    'PLP-EDEN-RES':      (4, 'бассейн и корпус вместо мастерплана'),
    'PLP-EDEN':          (1, 'бассейн и фасад вместо мастерплана'),
    'PLP-CLOVER':        (6, 'вилла с бассейном вместо стройплощадки с дрона'),
    'PLP-QABALAH':       (4, 'фасад виллы вместо пустой арки въезда'),
    'PLP-ESTELLA':       (5, 'вилла с бассейном вместо листа с надписями'),
}

# объекты, где выбирать не из чего — нужна съёмка или материалы застройщика
НУЖНЫ_ФОТО = {
    'PLP-GENS-BOTANICA': 'единственный кадр — рекламная страница с текстом и машиной',
    'PLP-EDEN-LAKE': 'кадров нет вовсе',
    'PLP-BAYSIDE-U1': 'кадров нет вовсе',
    'PLP-CAPRI-U1': 'кадров нет вовсе',
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode()
    return json.loads(raw) if raw.strip() else []


def лента(pid):
    """Нынешняя лента карточки — ровно та, по которой выбирали кадры."""
    s = open(os.path.join(ROOT, 'assets/catalog.js'), encoding='utf-8').read()
    for имя in ('PL.PROPERTIES', 'PL.RENTALS'):
        i = s.index(имя + '=['); j = s.index('\n];', i)
        for p in json.loads(s[i + len(имя) + 1:j + 2]):
            if p['property_id'] == pid:
                return p.get('photos') or []
    return []


def исходный(pid, r2):
    """В каталоге лежит адрес копии на R2, в базе — исходный адрес кадра.

    Пишем в main_image_url именно исходный: сборка сверяет главный кадр со
    списком gallery_urls по строгому равенству, и адрес копии в этот список не
    попал бы — кадр продублировался бы в ленте.
    """
    строки = call('/objects?plp_property_id=eq.%s&select=gallery_urls' % pid)
    хвост = r2.rsplit('/', 1)[-1].replace('-1600.webp', '').replace('-760.webp', '')
    for u in (строки[0].get('gallery_urls') or []) if строки else []:
        имя = u.split('?')[0].rsplit('/', 1)[-1]
        if имя.rsplit('.', 1)[0] == хвост:
            return u
    return None


def main():
    план, беда = [], []
    for pid, (n, почему) in ВЫБОР.items():
        ph = лента(pid)
        if len(ph) <= n:
            беда.append((pid, 'в ленте %d кадров, нужен №%d' % (len(ph), n)))
            continue
        src = исходный(pid, ph[n])
        if not src:
            беда.append((pid, 'кадр №%d не нашёлся в галерее объекта' % n))
            continue
        план.append((pid, src, почему))

    print('обложек к замене: %d\n' % len(план))
    for pid, u, почему in план:
        print('   %-22s %s' % (pid.replace('PLP-', ''), почему))
    if беда:
        print('\nне сошлось (лента изменилась — пересмотреть выбор):')
        for pid, п in беда:
            print('   %-22s %s' % (pid, п))
    print('\nнужны нормальные кадры, заменить нечем:')
    for pid, п in НУЖНЫ_ФОТО.items():
        print('   %-22s %s' % (pid.replace('PLP-', ''), п))

    if not APPLY:
        print('\nЭто отчёт. Записать: --apply')
        return 0
    for pid, u, _ in план:
        call('/objects?plp_property_id=eq.%s' % pid, 'PATCH', {'main_image_url': u})
    print('\nзаписано обложек: %d' % len(план))
    print('дальше: node build/gen.mjs && node build/mkassets.mjs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
