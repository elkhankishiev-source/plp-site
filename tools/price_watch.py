#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Еженедельная сверка цен: только отчёт, ничего не пишет.

Эльнур 16.09.2026: «сверку цен можно гонять раз в неделю автоматически, отчётом
без записи» — го. Раз в неделю проходим по всем объектам продажи, сравниваем
цену в карточке с прайсом застройщика (канал в Telegram, иначе папка на Диске)
и присылаем в Telegram короткий список того, что разошлось.

Ничего не меняет. Правки делаются руками после просмотра:
    python3 tools/tg_prices.py --apply        # цены из каналов
    python3 tools/drive_pull.py --price --apply PLP-XXX

Запуск: python3 tools/price_watch.py [--send]
"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERT = os.path.expanduser('~/.plp_tg_alert')
SEND = '--send' in sys.argv


def tg(text):
    raw = open(ALERT).read().split()
    token, chat = raw[0], raw[1]
    data = urllib.parse.urlencode({'chat_id': chat, 'text': text,
                                   'disable_web_page_preview': 'true'}).encode()
    urllib.request.urlopen('https://api.telegram.org/bot%s/sendMessage' % token, data=data, timeout=40)


def main():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'tg_prices.py')],
                         capture_output=True, text=True, timeout=1800).stdout
    diff, nochan, nolist, soldout = [], [], [], []
    for line in out.splitlines():
        if '≠' in line:
            m = re.match(r'(\S+)\s+.*?прайс (\S+):\s+свободно (\d+)\s+от (.+?) \(было (.+?)\)', line)
            if m:
                diff.append('• %s: в карточке %s, в прайсе %s (лист от %s, свободно %s)'
                            % (m.group(1), m.group(5).strip(), m.group(4).strip(), m.group(2), m.group(3)))
            else:
                diff.append('• ' + line.strip())
        elif 'РАСПРОДАНО' in line:
            soldout.append('• ' + line.split()[0] + ' — застройщик пишет SOLD OUT')
        elif 'канала нет' in line:
            nochan.append(line.split()[0])
        elif 'прайса нет' in line:
            nolist.append(line.split()[0])
    today = datetime.date.today().strftime('%d.%m.%Y')
    parts = ['Сверка цен с застройщиками · %s' % today]
    parts.append('Разошлось: %d' % len(diff))
    parts += diff[:20] if diff else ['Все цены совпадают с прайсами.']
    if soldout:
        parts.append(''); parts += soldout
    if nolist:
        parts.append('')
        parts.append('Канал есть, но прайс файлом не выкладывают (%d): %s'
                     % (len(nolist), ', '.join(nolist[:12])))
        parts.append('У них цена — из папки на Диске: tools/drive_pull.py --price')
    if nochan:
        parts.append('')
        parts.append('Канала застройщика нет вовсе (%d): %s' % (len(nochan), ', '.join(nochan[:12])))
        parts.append('Нужна ссылка на канал или папку — дальше подтянется само.')
    parts.append('')
    parts.append('Ничего не изменено. Правки: tools/tg_prices.py --apply')
    text = '\n'.join(parts)
    print(text)
    if SEND:
        try:
            tg(text[:3900])
        except Exception as ex:
            print('[отчёт не ушёл в Telegram: %s]' % str(ex)[:80])


if __name__ == '__main__':
    main()
