#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""В переписке ищет МОМЕНТ СДЕЛКИ: где назвали цену, бронь, инвойс, подписание.

25.09.2026. Продолжение chats_pull.py. Сумма сама по себе ничего не значит: в
разговоре летают прайсы, цены за метр и чужие проекты. Ищем реплики, где сумма
стоит рядом со словом сделки — «бронь», «инвойс», «договор», «оплатил», «итого»,
«перевёл», «депозит», — и печатаем их с датой. Дальше читает человек.

Ничего не записывает: это разведка.

    python3 tools/chats_deals.py                # все переписки
    python3 tools/chats_deals.py Науменко F519  # только по словам в имени файла
"""
import glob, os, re, sys, zipfile

ПАПКА = os.path.expanduser('~/PLP-выгрузки/переписки')
ДЕНЬГИ = re.compile(r'\d[\d  .,]{5,}\s*(?:thb|бат|฿|baht|млн)', re.I)
СДЕЛКА = re.compile(
    r'брон|инвойс|invoice|догов|contract|оплат|оплач|перевёл|перевел|перевод|'
    r'депозит|deposit|итого|резерв|подпис|sign|первый платёж|первый платеж|'
    r'стоимост|цена вилл|цена юнит|полная сумма|остаток', re.I)
РЕПЛИКА = re.compile(r'\[(\d\d\.\d\d\.\d{4}), [\d:]+\] ([^:]{1,60}): (.*)')


def реплики(текст):
    из = []
    for ln in текст.replace('‎', '').split('\n'):
        м = РЕПЛИКА.match(ln.strip())
        if м:
            из.append((м.group(1), м.group(2).strip(), м.group(3).strip()))
        elif из:
            из[-1] = (из[-1][0], из[-1][1], из[-1][2] + ' ' + ln.strip())
    return из


def главное():
    отбор = [x.lower() for x in sys.argv[1:]]
    for п in sorted(glob.glob(os.path.join(ПАПКА, '*.zip'))):
        имя = os.path.basename(п)
        if отбор and not any(о in имя.lower() for о in отбор):
            continue
        текст = ''
        try:
            z = zipfile.ZipFile(п)
            for n in z.namelist():
                if n.lower().endswith('.txt'):
                    текст += z.read(n).decode('utf-8', 'ignore')
        except Exception:
            continue
        нашли = []
        for дата, кто, что in реплики(текст):
            if ДЕНЬГИ.search(что) and СДЕЛКА.search(что):
                к = re.sub(r'\s+', ' ', что).strip()
                if len(к) > 12 and к not in [x[2] for x in нашли]:
                    нашли.append((дата, кто, к))
        if нашли:
            print('\n=== %s' % имя[:80])
            for дата, кто, что in нашли[:14]:
                print('  %s %-22s %s' % (дата, кто[:22], что[:250]))


if __name__ == '__main__':
    главное()
