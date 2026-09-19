#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прогрев кэша: был тройным и круглосуточным, станет одинарным и по рабочим часам.

Разбор журнала 19.09.2026 показал, во что обходится служебный шум. В расписании root
лежала ОДНА строка, в которую слиплись ТРИ задания:

    */50 ... curl ... -d text:[[ПРОГРЕВ]] ... */50 ... -d phone:66900000000 ... */50 ... -d source:warm

Из-за слипания это выполняется как одна команда — три обращения к мозгу подряд. Кэш
греет первое, второе и третье просто покупают ещё два ответа. В журнале это видно как
четыре вызова модели в :50 и четыре в :00.

Плюс payload мусорный: `-d text:[[ПРОГРЕВ]]` не JSON, и мозг отвечает на него как на
реплику клиента — в логе прогрева лежат настоящие продающие реплики, которые никто не
прочитает.

Счёт по журналу: один заход к Opus это ~$0.098, создание кэша заново ~$0.61. Тройной
прогрев два раза в час = 6 лишних заходов в час.

Что делаем по призме:
  • удаляем лишнее — из трёх заходов оставляем один;
  • упрощаем — нормальный JSON вместо строки с двоеточием;
  • не греем пустоту — только в рабочие часы 10:00–22:00 по Пхукету (03:00–15:00 UTC),
    ночью живых диалогов нет и держать кэш незачем.

Прогрев ОБЯЗАН звать модель, иначе кэш не создаётся: probe тут не подходит, он именно
для сторожа живости.

    python3 vps_warm_fix.py            # показать, что изменится
    python3 vps_warm_fix.py --apply    # переписать расписание
"""
import subprocess, sys

APPLY = '--apply' in sys.argv

NEW_LINE = ('50 3-14 * * * K=$(sed -n "s/^PLP_API_KEY=//p" /opt/plp-api/.env); '
            'curl -s -m 90 -X POST http://127.0.0.1:8090/brain '
            '-H "Content-Type: application/json" -H "x-plp-key: $K" '
            '''-d '{"input":{"text":"прогрев кэша","phone":"66999000998","source":"warm"}}' '''
            '>> /var/log/plp-warm.log 2>&1')


def main():
    cur = subprocess.run(['crontab', '-l'], capture_output=True, text=True).stdout
    keep, dropped = [], []
    for ln in cur.splitlines():
        if 'plp-warm.log' in ln:
            dropped.append(ln)
        else:
            keep.append(ln)
    if not dropped:
        print('строк прогрева не найдено — возможно, уже переписано')
        if any('66999000998' in l for l in keep):
            print('новый прогрев на месте')
        return 0
    print('БЫЛО (%d строк, в них %d обращений к мозгу):'
          % (len(dropped), sum(l.count('/brain') for l in dropped)))
    for l in dropped:
        print('   ' + l[:150] + ('…' if len(l) > 150 else ''))
    print('\nСТАНЕТ (1 обращение, 12 раз в сутки, только 10:00–22:00 Пхукет):')
    print('   ' + NEW_LINE[:150] + '…')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    new = '\n'.join(keep + [NEW_LINE]) + '\n'
    p = subprocess.run(['crontab', '-'], input=new, capture_output=True, text=True)
    if p.returncode:
        print('не принято: ' + p.stderr[:200])
        return 1
    back = subprocess.run(['crontab', '-l'], capture_output=True, text=True).stdout
    ok = '66999000998' in back and back.count('/brain') == 1
    print('записано. обращений к мозгу в расписании: %d' % back.count('/brain'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
