#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Еженедельное обновление цен и наличия: само правит безопасное, спорное — спрашивает.

Эльнур 16.09.2026: «данные должны обновляться автоматически, сами: цены, детали,
наличие». Порядок такой:
  1. каналы застройщиков (tools/tg_prices.py) — цена и наличие по свободным юнитам;
  2. папки на Диске (tools/drive_pull.py) — там, где канала нет;
  3. пересборка сайта со всеми проверками; если проверка падает — не публикуем;
  4. выкладка и короткий отчёт в Telegram: что изменилось и что ждёт подтверждения.

Правка больше четверти цены не применяется никогда: в папке застройщика лежит и
прайс соседнего проекта, а в канале — разные фазы. Такое уходит в отчёт.

    python3 tools/price_watch.py             # сухой прогон, ничего не меняет
    python3 tools/price_watch.py --apply     # обновить данные и пересобрать
    python3 tools/price_watch.py --apply --send --publish   # + выложить и отчитаться
"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERT = os.path.expanduser('~/.plp_tg_alert')
APPLY = '--apply' in sys.argv
SEND = '--send' in sys.argv
PUBLISH = '--publish' in sys.argv
PY3 = sys.executable


def run(args, timeout=2400):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return (r.stdout or '') + (r.stderr or '')


def tg(text):
    raw = open(ALERT).read().split()
    data = urllib.parse.urlencode({'chat_id': raw[1], 'text': text,
                                   'disable_web_page_preview': 'true'}).encode()
    urllib.request.urlopen('https://api.telegram.org/bot%s/sendMessage' % raw[0], data=data, timeout=40)


def main():
    changed, waiting, soldout, nolist, nochan = [], [], [], [], []
    args = [PY3, os.path.join(ROOT, 'tools', 'tg_prices.py')] + (['--apply'] if APPLY else [])
    out = run(args)
    cur = None
    for line in out.splitlines():
        if '≠' in line:
            m = re.match(r'(\S+)\s+.*?прайс (\S+):\s+свободно (\d+)\s+от (.+?) \(было (.+?)\)', line)
            cur = ('• %s: %s → %s (прайс от %s, свободно %s)'
                   % (m.group(1), m.group(5).strip(), m.group(4).strip(), m.group(2), m.group(3))) if m else ('• ' + line.strip())
            changed.append(cur)
        elif 'не записываю' in line and changed:
            waiting.append(changed.pop().replace('→', 'против'))
        elif 'РАСПРОДАНО' in line:
            soldout.append('• %s — застройщик пишет SOLD OUT' % line.split()[0])
        elif 'прайса нет' in line:
            nolist.append(line.split()[0])
        elif 'канала нет' in line:
            nochan.append(line.split()[0])

    if APPLY and nolist:
        d = run([PY3, os.path.join(ROOT, 'tools', 'drive_pull.py'), '--price', '--apply'] + nolist[:12])
        pid = None
        for line in d.splitlines():
            if line.startswith('PLP') or line.startswith('INTAKE') or line.startswith('RESALE'):
                pid = line.split(' ')[0]
            if '✓ записано' in line and pid:
                changed.append('• %s: цена обновлена с Диска' % pid)
            if '⚠ не записываю' in line and pid:
                waiting.append('• %s: прайс с Диска расходится больше чем на четверть' % pid)

    built = published = ''
    if APPLY:
        b = run(['node', os.path.join(ROOT, 'build', 'all.mjs')], timeout=3000)
        ok = all(s in b for s in ('[вид] ок', '[кабинет] ок')) and 'сборка завершена' in b
        built = 'сборка: ок' if ok else 'сборка: ПРОВЕРКИ НЕ ПРОШЛИ — не публикую'
        if ok and PUBLISH:
            st = run(['git', 'status', '--porcelain'])
            if st.strip():
                run(['git', 'add', '-A'])
                run(['git', 'commit', '-m', 'Обновление цен и наличия по прайсам застройщиков (автосверка)'])
                push = run(['git', 'push', 'origin', 'main'])
                published = 'сайт обновлён' if 'error' not in push.lower() else 'выложить не удалось'
            else:
                published = 'на сайте всё и так свежее'

    today = datetime.date.today().strftime('%d.%m.%Y')
    parts = ['Цены и наличие · %s' % today]
    parts.append('Обновлено: %d, ждёт подтверждения: %d' % (len(changed), len(waiting)))
    parts += changed[:15] if changed else ['Изменений нет.']
    if waiting:
        parts.append(''); parts.append('Спорное, не трогал:'); parts += waiting[:8]
    if soldout:
        parts.append(''); parts += soldout
    if nolist:
        parts.append(''); parts.append('Канал есть, прайс файлом не выкладывают (%d): %s'
                                       % (len(nolist), ', '.join(nolist[:10])))
    if nochan:
        parts.append(''); parts.append('Канала застройщика нет (%d): %s' % (len(nochan), ', '.join(nochan[:10])))
        parts.append('Нужна ссылка на канал или папку — дальше подтянется само.')
    if built:
        parts.append(''); parts.append(built + ('; ' + published if published else ''))
    if not APPLY:
        parts.append(''); parts.append('Сухой прогон: ничего не менял.')
    text = '\n'.join(parts)
    print(text)
    if SEND:
        try:
            tg(text[:3900])
        except Exception as ex:
            print('[отчёт не ушёл в Telegram: %s]' % str(ex)[:80])


if __name__ == '__main__':
    main()
