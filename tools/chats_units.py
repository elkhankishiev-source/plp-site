#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""В переписке ищет куски, где рядом стоят НОМЕР ЮНИТА и сумма.

Продолжение chats_pull.py: сумма сама по себе ничего не значит — в разговоре
летают и прайсы, и цены за метр, и чужие проекты. Ищем места, где сумма стоит
рядом с номером юнита, и показываем их с контекстом, чтобы решал человек.

Ничего не записывает: это разведка, а не заливка.

    python3 tools/chats_units.py
"""
import glob, os, re, zipfile

# юнит → как он может быть назван в переписке
ЮНИТЫ = {
 'PLP-AYANA-F519':  ['F519', 'F-519'],
 'PLP-AYANA-A35':   ['A35', 'A-35'],
 'PLP-AYANA-A36':   ['A36', 'A-36'],
 'PLP-AYANA-F412':  ['F412', 'F-412'],
 'PLP-VIVI-A304':   ['A304', 'A-304'],
 'PLP-VIVI-A507':   ['A507', 'A-507'],
 'PLP-LEGENDARY-A707': ['A707', 'A-707'],
 'PLP-LEGENDARY-I705': ['i705', 'I705', 'I-705'],
 'PLP-LEGENDARY-D301': ['D301', 'D-301'],
 'PLP-EDEN-F404':   ['F404', 'F 404', 'F-404'],
 'PLP-EDEN-F105':   ['F105', 'F-105'],
 'PLP-SERENITY-A515': ['A515', 'A-515'],
 'PLP-QABALAH-F3':  ['Qabalah F3', 'F3 Qabalah', 'вилла F3', 'F-3'],
 'PLP-QABALAH-M14': ['M14', 'М14', 'M-14'],
 'PLP-QABALAH-M1':  ['M1 ', 'М1 '],
 'PLP-QABALAH-M2':  ['M2 ', 'М2 '],
 'PLP-QABALAH-M3':  ['M3 ', 'М3 '],
 'PLP-QABALAH-M4':  ['M4 ', 'М4 '],
 'PLP-QABALAH-F2':  ['F2 ', 'Ф2 '],
 'PLP-QABALAH-F4':  ['F4 ', 'Ф4 '],
 'PLP-MODEVA-D103': ['D103', 'D-103'],
 'PLP-BALCONY-D306':['D306', 'D-306'],
 'PLP-BALCONY-G402':['G402', 'G-402'],
 'PLP-BIANCANA-C413':['C413', 'C-413'],
 'PLP-KATABELLO-A606':['A606', 'A-606'],
 'PLP-KATABELLO-F707':['F707', 'F-707'],
 'PLP-CLOVER-A11':  ['Clover A11', 'A11'],
 'PLP-CLOVER-D46':  ['D46'],
 'PLP-CLOVER-D58':  ['D58'],
 'PLP-MANOR-S14':   ['S14', 'S-14'],
 'PLP-MANOR-S17':   ['S17', 'S-17'],
 'PLP-ESTELLA-A24': ['A24', 'A-24'],
}
ДЕНЬГИ = re.compile(r'\d[\d  .,]{5,}\s*(?:thb|бат|฿|baht)', re.I)

тексты = []
for п in glob.glob(os.path.expanduser('~/PLP-выгрузки/переписки/*.zip')):
    try:
        z = zipfile.ZipFile(п)
        for n in z.namelist():
            if n.lower().endswith('.txt'):
                тексты.append((os.path.basename(п), z.read(n).decode('utf-8', 'ignore')))
    except Exception:
        pass

for код, имена in ЮНИТЫ.items():
    находки = []
    for файл, т in тексты:
        for им in имена:
            for м in re.finditer(re.escape(им), т):
                кусок = т[max(0, м.start()-260):м.end()+260]
                if ДЕНЬГИ.search(кусок):
                    к = re.sub(r'\s+', ' ', кусок).strip()
                    if к not in находки:
                        находки.append(к)
    if находки:
        print('\n### %s — кусков %d' % (код, len(находки)))
        for к in находки[:2]:
            print('   ', к[:330])
