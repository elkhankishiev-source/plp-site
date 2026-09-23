#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перечень всех страниц сайта: что видно, что спрятано и насколько спрятано.

Эльнур 23.09.2026: «как нам видеть списки всех скрытых страниц, то что мы создали».

Отвечает на три разных вопроса, которые легко перепутать:
  в карте сайта  — поисковик узнает о странице сам;
  noindex        — просим поисковик не показывать её в выдаче;
  кто-то ведёт   — есть ли на неё ссылка хоть с одной нашей страницы.

Отдельно печатает предупреждение, которое важнее всех трёх: сайт лежит на
GitHub Pages из ОТКРЫТОГО репозитория. noindex прячет страницу от Гугла, но не
от человека: весь список файлов виден на github.com любому. Поэтому «скрытая
страница» у нас означает «её не найдут поиском», а не «её нельзя прочитать».
Всё, что правда закрыто, должно жить на сервере за паролем, а не здесь.

    python3 tools/pages_index.py           # перечень на экран
    python3 tools/pages_index.py --md      # тот же перечень разметкой, чтобы переслать
"""
import os, re, sys, urllib.request

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ДОМЕН = 'https://property-library.com'
MD = '--md' in sys.argv

ОПИСАНИЯ = {
    'index.html': 'главная: каталог продажи и полоса аренды',
    'buy.html': 'покупка: каталог с картой',
    'rent.html': 'аренда: каталог объектов',
    'management.html': 'управление объектом',
    'about.html': 'о нас',
    'add-property.html': 'сдать или продать свой объект',
    'owner.html': 'кабинет собственника — вход по личному коду',
    'admin.html': 'админка УК — служебная',
    'offer.html': 'конструктор персонального оффера',
    'vibe2.html': 'лендинг Vibe II Карон + PDF',
    'privacy.html': 'политика конфиденциальности',
    'rules.html': 'правила',
    'terms.html': 'условия',
    '404.html': 'страница «не найдено»',
    'guide/index.html': 'гид: оглавление',
    'offers/vibe2/page.htm': 'исходный лист лендинга Vibe II (его показывает vibe2.html в рамке)',
}


def страницы():
    из = []
    for каталог, папки, файлы in os.walk(КОРЕНЬ):
        папки[:] = [п for п in папки if п not in ('.git', 'build', 'tools', 'img', '.github')]
        for ф in файлы:
            if ф.endswith(('.html', '.htm')):
                из.append(os.path.relpath(os.path.join(каталог, ф), КОРЕНЬ))
    return sorted(из)


def главное():
    все = страницы()
    карта = set()
    путь = os.path.join(КОРЕНЬ, 'sitemap.xml')
    if os.path.exists(путь):
        for m in re.finditer(r'<loc>([^<]+)</loc>', open(путь, encoding='utf-8').read()):
            а = m.group(1).replace(ДОМЕН, '').lstrip('/')
            карта.add(а or 'index.html')
            карта.add((а + 'index.html') if а.endswith('/') else а)
            if а and not а.endswith('.html'):
                карта.add(а + '.html')

    роботы = open(os.path.join(КОРЕНЬ, 'robots.txt'), encoding='utf-8').read() \
        if os.path.exists(os.path.join(КОРЕНЬ, 'robots.txt')) else ''
    закрыто_роботами = {ln.split(':', 1)[1].strip().lstrip('/')
                        for ln in роботы.splitlines() if ln.lower().startswith('disallow:')
                        and ln.split(':', 1)[1].strip() not in ('', '/')}

    # на кого ссылаются: собираем все ссылки со всех наших страниц
    ведут = {}
    for с in все:
        try:
            текст = open(os.path.join(КОРЕНЬ, с), encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        for m in re.finditer(r'href="([^"#?]+)', текст):
            ц = m.group(1)
            if ц.startswith(('http', 'mailto:', 'tel:', '//')):
                if not ц.startswith(ДОМЕН):
                    continue
                ц = ц[len(ДОМЕН):]
            ц = ц.lstrip('/')
            for вариант in (ц, ц + '.html', ц.rstrip('/') + '/index.html', 'object/' + ц + '.html'):
                if вариант in все and вариант != с:
                    ведут.setdefault(вариант, set()).add(с)

    строки = []
    for с in все:
        # meta robots у нас стоит не в первых строках: у vibe2.html она на 155-й тысяче
        # знаков, потому что перед ней идёт весь общий блок стилей главной.
        текст = open(os.path.join(КОРЕНЬ, с), encoding='utf-8', errors='ignore').read()
        ni = bool(re.search(r'name=["\']robots["\'][^>]*noindex', текст, re.I))
        в_карте = с in карта or с.replace('/index.html', '/') in карта
        откуда = ведут.get(с, set())
        if в_карте and not ni:
            вид, почему = 'открытая', ''
        elif ni or с in закрыто_роботами:
            вид = 'скрытая'
            почему = 'noindex' + (' + robots.txt' if с in закрыто_роботами else '')
        elif not в_карте and not откуда:
            вид, почему = 'ПОТЕРЯННАЯ', 'нет ни в карте сайта, ни в одной ссылке'
        elif not в_карте:
            вид, почему = 'без карты', 'ссылки есть, в карте сайта нет'
        else:
            вид, почему = 'открытая', ''
        строки.append((вид, с, почему, len(откуда)))

    порядок = {'ПОТЕРЯННАЯ': 0, 'скрытая': 1, 'без карты': 2, 'открытая': 3}
    строки.sort(key=lambda r: (порядок[r[0]], r[1]))

    п = print
    if MD:
        p = lambda s='': п(s)
    else:
        p = lambda s='': п(s)

    p('СТРАНИЦЫ САЙТА property-library.com — всего %d' % len(все))
    p('')
    p('⚠ Сразу о главном: репозиторий сайта на GitHub ОТКРЫТ. «Скрытая» здесь')
    p('  значит «не попадёт в поиск Гугла», а не «её нельзя прочитать»: список')
    p('  файлов и их содержимое видны любому на github.com. Всё, что правда')
    p('  закрыто — кабинет, админка, пульт — должно стоять на сервере за паролем.')
    p('')
    сейчас = None
    for вид, с, почему, сколько in строки:
        if вид != сейчас:
            сейчас = вид
            всего = sum(1 for r in строки if r[0] == вид)
            p('')
            p('%s — %d' % ({'ПОТЕРЯННАЯ': '🔴 ПОТЕРЯННЫЕ: созданы, но к ним не попасть',
                            'скрытая': '🔒 СКРЫТЫЕ ОТ ПОИСКА',
                            'без карты': '🟡 ЕСТЬ ССЫЛКИ, НЕТ В КАРТЕ САЙТА',
                            'открытая': '✔ ОТКРЫТЫЕ'}[вид], всего))
        оп = ОПИСАНИЯ.get(с, '')
        хвост = (' — ' + оп) if оп else ''
        доп = (' · %s' % почему) if почему else ''
        ссыл = (' · ведут %d' % сколько) if сколько else ' · ссылок нет'
        if вид == 'открытая' and not оп and с.startswith(('object/', 'guide/', 'districts/')):
            continue          # 88 карточек объектов не печатаем поимённо
        p('  %-42s%s%s%s' % (с, хвост, доп, ссыл))
    скрыто_объектов = sum(1 for в, с, _, _ in строки
                          if в == 'открытая' and с.startswith(('object/', 'guide/', 'districts/')))
    if скрыто_объектов:
        p('  (+ %d страниц объектов, гида и районов — все открытые)' % скрыто_объектов)
    p('')
    return 0


if __name__ == '__main__':
    sys.exit(главное())
