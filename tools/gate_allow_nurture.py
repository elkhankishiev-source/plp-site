#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привратник учится пускать касания прогрева (agent='nurture').

Разбор 22.09.2026. Матрица в WF_outbound_gate, узел «Policy Engine», знает семь
агентов: validator, concierge, reanimator, proactive, auto, office, owner_task.
Всё прочее получает mWhy='unknown_agent' и отбой matrix_deny(unknown_agent).
А планировщик касаний подписывает строки agent='nurture'. Значит ни одно касание
прогрева не могло уйти никогда — с постройки механизма 17.09. Волна 18.09 прошла
только потому, что её подписали owner_task.

Проверено живьём: 8 одобренных касаний, проход отправщика 22.09 11:33 →
sent: 0, отложено: 8, в каждой строке «привратник: ["matrix_deny(unknown_agent)"]».

Правка добавляет nurture рядом с proactive и с тем же условием: нужен повод.
Повод планировщик кладёт всегда — воронка, этап, источник, о чём говорили.
Остальные предохранители не трогаются: тихие часы, чёрный список, суточный потолок,
kill-switch, touch_blocked работают как работали.

Правка через API меняет только ЧЕРНОВИК. Исполняется опубликованная версия, поэтому
скрипт сам зовёт n8n_publish.py --apply. Без этого «UPDATE прошёл, а поведение старое».

    python3 gate_allow_nurture.py            # показать, что изменится
    python3 gate_allow_nurture.py --apply    # внести и опубликовать
    python3 gate_allow_nurture.py --rollback # вернуть код узла из бэкапа
"""
import json, os, subprocess, sys, urllib.request, datetime

WF = '8RgKkdr0VPJOia2E'
BASE = 'https://hub.property-library.com/api/v1/'
APPLY = '--apply' in sys.argv
ROLLBACK = '--rollback' in sys.argv
BAK = os.path.expanduser('~/plp_backups/gate_policy_engine_%s.js')

ЦЕЛЬ = "else if(agent==='proactive'){mOK=!!occasion;mWhy='proactive=повод(+go)';}"
НОВОЕ = (ЦЕЛЬ + "\n"
  "/* 22.09.2026: агента nurture матрица не знала, и ВСЕ касания прогрева отбивались\n"
  "   matrix_deny(unknown_agent) — с 17.09, с самой постройки механизма. Прогрев = то же\n"
  "   касание по поводу, что и proactive: пускаем при наличии повода. Остальные\n"
  "   предохранители не меняются. */\n"
  "else if(agent==='nurture'){mOK=!!occasion;mWhy='nurture=прогрев базы, повод обязателен';}")


def key():
    return open(os.path.expanduser('~/.plp_n8n_local_key')).read().strip()


def api(path, method='GET', body=None):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={'X-N8N-API-KEY': key(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=40) as f:
        return json.load(f)


def узел(wf):
    for n in wf['nodes']:
        if n['name'] == 'Policy Engine':
            return n
    raise SystemExit('узел «Policy Engine» не найден — привратник изменился, править руками')


def main():
    wf = api('workflows/' + WF)
    n = узел(wf)
    код = n['parameters'].get('jsCode', '')

    if ROLLBACK:
        копии = sorted(f for f in os.listdir(os.path.expanduser('~/plp_backups'))
                       if f.startswith('gate_policy_engine_'))
        if not копии:
            print('бэкапов нет'); return 1
        путь = os.path.expanduser('~/plp_backups/' + копии[-1])
        n['parameters']['jsCode'] = open(путь, encoding='utf-8').read()
        api('workflows/' + WF, 'PUT', {'name': wf['name'], 'nodes': wf['nodes'],
                                       'connections': wf['connections'], 'settings': wf.get('settings', {})})
        print('код узла возвращён из', путь)
        subprocess.run([sys.executable, os.path.expanduser('~/plp-site/tools/n8n_publish.py'), '--apply'])
        return 0

    if "agent==='nurture'" in код:
        print('правка уже стоит в черновике')
    else:
        if ЦЕЛЬ not in код:
            print('не нашёл ветку proactive — привратник изменился, править руками'); return 1
        if not APPLY:
            print('Будет добавлено в узел «Policy Engine» сразу после ветки proactive:\n')
            print("  else if(agent==='nurture'){mOK=!!occasion;mWhy='nurture=прогрев базы, повод обязателен';}\n")
            print('Это отчёт. Внести и опубликовать: --apply')
            return 0
        os.makedirs(os.path.expanduser('~/plp_backups'), exist_ok=True)
        путь = BAK % datetime.datetime.now().strftime('%Y%m%d_%H%M')
        open(путь, 'w', encoding='utf-8').write(код)
        print('бэкап кода узла:', путь)
        n['parameters']['jsCode'] = код.replace(ЦЕЛЬ, НОВОЕ, 1)
        api('workflows/' + WF, 'PUT', {'name': wf['name'], 'nodes': wf['nodes'],
                                       'connections': wf['connections'], 'settings': wf.get('settings', {})})
        print('черновик обновлён')

    if APPLY:
        print('\nпубликую (иначе исполняться будет старая версия):')
        subprocess.run([sys.executable, os.path.expanduser('~/plp-site/tools/n8n_publish.py'), '--apply'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
