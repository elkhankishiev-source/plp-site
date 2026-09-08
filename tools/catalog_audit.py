#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Приёмка карточек: одна проверка на все витрины.

Эльнур 08.09: «как сделать так, чтобы ты раз и навсегда зафиксировал себе
инструмент приёмки верной и вообще чтобы ты это делал».

Правила живут в базе (функция catalog_audit) — оттуда их читают трое:
  • сборка сайта (node build/all.mjs зовёт этот файл и печатает итог),
  • кабинет, блок «Сверка с правилами»,
  • еженедельный отчёт в рабочий чат.
Одно место правды, три выхода.

    python3 tools/catalog_audit.py            # всё
    python3 tools/catalog_audit.py --errors   # только ошибки
    python3 tools/catalog_audit.py --short    # одна строка для сборки
"""
import json, sys, urllib.request

SB = '/tmp/.sb'


def rows():
    d = json.load(open(SB))
    h = {'apikey': d['key'], 'Authorization': 'Bearer ' + d['key'],
         'Content-Type': 'application/json'}
    r = urllib.request.Request(d['url'].rstrip('/') + '/rest/v1/rpc/catalog_audit',
                               data=b'{}', headers=h)
    return json.load(urllib.request.urlopen(r, timeout=90))


def main():
    only_err = '--errors' in sys.argv
    short = '--short' in sys.argv
    try:
        r = rows()
    except Exception as e:
        print('приёмка карточек: база не ответила (%s)' % str(e)[:60])
        return 0
    errs = [x for x in r if x['severity'] == 'ошибка']
    if short:
        print('[приёмка] карточек с расхождениями: %d (ошибок %d, замечаний %d)'
              % (len({x['plp_property_id'] for x in r}), len(errs), len(r) - len(errs)))
        for x in errs[:5]:
            print('[приёмка] 🔴 %s — %s%s' % (x['plp_property_id'], x['issue'],
                                              (': ' + x['detail']) if x.get('detail') else ''))
        return 0
    show = errs if only_err else r
    if not show:
        print('приёмка карточек: расхождений нет')
        return 0
    cur = None
    for x in show:
        if x['plp_property_id'] != cur:
            cur = x['plp_property_id']
            print('\n%s · %s' % (cur, x['name'] or ''))
        print('   %s %s%s' % ('🔴' if x['severity'] == 'ошибка' else '•',
                              x['issue'], (' — ' + x['detail']) if x.get('detail') else ''))
    print('\nвсего: %d замечаний по %d карточкам (ошибок %d)'
          % (len(show), len({x['plp_property_id'] for x in show}), len(errs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
