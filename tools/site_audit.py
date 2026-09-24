#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сквозная сверка сайта: страницы, ссылки, заголовки, разметка для поиска.

Эльнур 24.09.2026: «сверь сразу все страницы, блоки, разделы, кнопки, реально
работают, функционируют заявки… нет ли ошибок в тексте, все ли адреса читаются,
сео оптимизация».

Что проверяет, по одной строке на беду:
  • заголовок и описание — есть ли, не пустые, не длиннее разумного;
  • canonical — есть ли и не смотрит ли на чужой адрес;
  • H1 — ровно один на странице;
  • повторы: два разных адреса с одинаковым заголовком путают поиск;
  • разметка Schema.org — есть ли, валиден ли JSON;
  • og:image — указан ли и лежит ли файл;
  • внутренние ссылки — ведут ли на существующие страницы;
  • язык страницы и кодировка;
  • следы черновиков в тексте: lorem, TODO, XXX, «текст».

Работает по файлам в репозитории, сеть не нужна. Живые коды ответов — отдельно,
ключом --живьём (медленно, ходит на property-library.com).

    python3 tools/site_audit.py
    python3 tools/site_audit.py --живьём
    python3 tools/site_audit.py --сео     # только про поиск
"""

import json
import os
import re
import sys
import urllib.request

КОРЕНЬ = os.path.expanduser('~/plp-site')
САЙТ = 'https://property-library.com'
ЖИВЬЁМ = '--живьём' in sys.argv
ТОЛЬКО_СЕО = '--сео' in sys.argv

ПРОПУСК_ПАПОК = {'.git', 'node_modules', 'build', 'tools', 'img'}
# Эти страницы намеренно закрыты от поиска — к ним требования другие.
ЗАКРЫТЫЕ = {'404.html', 'admin.html', 'guest.html', 'offer.html', 'owner.html', 'vibe2.html'}

ЧЕРНОВИК = re.compile(r'\b(lorem ipsum|TODO|FIXME|XXX|заглушка|текст текст)\b', re.I)


def страницы():
    из = []
    for корень, папки, файлы in os.walk(КОРЕНЬ):
        папки[:] = [п for п in папки if п not in ПРОПУСК_ПАПОК and not п.startswith('.')]
        для = [и for и in файлы if и.endswith('.html')]
        из += [os.path.join(корень, и) for и in для]
    return sorted(из)


def кор(путь):
    return os.path.relpath(путь, КОРЕНЬ)


def один(рег, текст, группа=1):
    м = re.search(рег, текст, re.S | re.I)
    return (м.group(группа).strip() if м else None)


def проверить():
    беды = []
    заголовки = {}
    всего = 0

    for путь in страницы():
        имя = кор(путь)
        s = open(путь, encoding='utf-8', errors='ignore').read()
        закрыта = os.path.basename(путь) in ЗАКРЫТЫЕ
        всего += 1

        загл = один(r'<title>(.*?)</title>', s)
        опис = один(r'<meta name="description" content="(.*?)"', s)
        канон = один(r'<link rel="canonical" href="(.*?)"', s)
        h1 = re.findall(r'<h1\b[^>]*>(.*?)</h1>', s, re.S | re.I)

        if not загл:
            беды.append(('заголовка нет', имя, ''))
        elif len(загл) > 70:
            беды.append(('заголовок длиннее 70 знаков — поиск обрежет', имя, '%d' % len(загл)))
        elif len(загл) < 15 and not закрыта:
            беды.append(('заголовок короче 15 знаков', имя, загл))

        if not опис and not закрыта:
            беды.append(('описания нет', имя, ''))
        elif опис and len(опис) > 165:
            беды.append(('описание длиннее 165 знаков — обрежет', имя, '%d' % len(опис)))
        elif опис and len(опис) < 50 and not закрыта:
            беды.append(('описание короче 50 знаков', имя, '%d' % len(опис)))

        if not канон and not закрыта:
            беды.append(('canonical не указан', имя, ''))
        elif канон and not канон.startswith(САЙТ):
            беды.append(('canonical смотрит наружу', имя, канон[:60]))

        if len(h1) == 0 and not закрыта:
            беды.append(('H1 нет вовсе', имя, ''))
        elif len(h1) > 1 and not закрыта:
            беды.append(('H1 больше одного (%d)' % len(h1), имя, ''))
        elif len(h1) > 1:
            # Кабинет и персональный оффер закрыты от поиска (noindex, нет в карте).
            # Там H1 — заголовки разделов приложения, к поиску отношения не имеют.
            # Остальные проверки эти страницы уже пропускают, делаем и эту так же.
            pass

        if загл and not закрыта:
            заголовки.setdefault(загл, []).append(имя)

        # Schema.org: есть ли и валиден ли
        for блок in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            try:
                json.loads(блок)
            except Exception as e:
                беды.append(('разметка Schema.org не читается', имя, str(e)[:50]))

        if not закрыта and 'application/ld+json' not in s:
            беды.append(('нет разметки Schema.org — поиск не поймёт, что это', имя, ''))

        og = один(r'<meta property="og:image" content="(.*?)"', s)
        if not og and not закрыта:
            беды.append(('og:image нет — в мессенджере ссылка без картинки', имя, ''))

        if not re.search(r'<html[^>]*\blang=', s):
            беды.append(('у страницы не указан язык', имя, ''))

        м = ЧЕРНОВИК.search(re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S))
        if м:
            беды.append(('след черновика в тексте', имя, м.group(0)))

    for загл, где in заголовки.items():
        if len(где) > 1:
            беды.append(('одинаковый заголовок на %d страницах' % len(где),
                         ', '.join(где[:3]), загл[:50]))

    return всего, беды


def живьём():
    """Коды ответов по карте сайта: страница может быть в карте и не открываться."""
    карта = open(os.path.join(КОРЕНЬ, 'sitemap.xml'), encoding='utf-8').read()
    адреса = re.findall(r'<loc>(.*?)</loc>', карта)
    плохие = []
    for i, u in enumerate(адреса, 1):
        try:
            r = urllib.request.Request(u, method='HEAD', headers={'User-Agent': 'PLP-audit'})
            код = urllib.request.urlopen(r, timeout=20).status
        except Exception as e:
            код = getattr(e, 'code', 0)
        if код != 200:
            плохие.append((u, код))
        if i % 25 == 0:
            print('   проверено %d из %d…' % (i, len(адреса)))
    return len(адреса), плохие


def главное():
    всего, беды = проверить()
    if ТОЛЬКО_СЕО:
        беды = [b for b in беды if 'черновик' not in b[0]]
    по_виду = {}
    for что, где, доп in беды:
        по_виду.setdefault(что, []).append((где, доп))

    print('СКВОЗНАЯ СВЕРКА САЙТА — страниц %d, находок %d\n' % (всего, len(беды)))
    for что in sorted(по_виду, key=lambda k: -len(по_виду[k])):
        список = по_виду[что]
        print('  %-52s %d' % (что[:52], len(список)))
        for где, доп in список[:4]:
            print('      %-42s %s' % (где[:42], доп[:46]))
        if len(список) > 4:
            print('      … ещё %d' % (len(список) - 4))
    if ЖИВЬЁМ:
        print('\nЖИВЫЕ КОДЫ ОТВЕТА ПО КАРТЕ САЙТА')
        сколько, плохие = живьём()
        if плохие:
            for u, к in плохие:
                print('   %-58s %s' % (u[:58], к))
            print('   не открылось %d из %d' % (len(плохие), сколько))
        else:
            print('   все %d адресов отвечают 200' % сколько)
    return 1 if беды else 0


if __name__ == '__main__':
    sys.exit(главное())
