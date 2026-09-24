#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Модель мозга обязана существовать в живом списке Anthropic.

Повод, урок 67: «модель выбирали один раз и больше не пересматривали». И
обратная беда 23.09: я объявил Opus 5.5 несуществующей, потому что сверился со
справочником, а не с API — модель вышла 21.09.

Сторож не решает, какая модель лучше. Он отвечает на один вопрос: та, что стоит
в бою, вообще ещё живая? Модель, снятую с продажи, мозг узнает отказом на
живом клиенте, а не здесь.

Список моделей отдаётся бесплатно: это не вызов модели, кредитов не тратит.

    python3 tools/model_check.py          # что стоит и живо ли
    python3 tools/model_check.py --тихо   # только при беде

Ноль — всё живо. Единица — модель в бою не найдена в списке.
"""

import json
import re
import subprocess
import sys
import urllib.request

ТИХО = '--тихо' in sys.argv
СЕРВЕР = 'root@167.172.66.20'
КЛЮЧ_SSH = '~/.ssh/plp_vps'


def ssh(команда):
    p = subprocess.run(['ssh', '-i', КЛЮЧ_SSH.replace('~', __import__('os').path.expanduser('~')),
                        '-o', 'ConnectTimeout=15', СЕРВЕР, команда],
                       capture_output=True, text=True, timeout=60)
    return p.stdout


def модели_в_бою():
    # Кириллица в ERE на сервере ведёт себя непредсказуемо (ловил это не раз),
    # поэтому grep берёт грубо, а разбирает уже Python.
    т = ssh("grep -n '^const MODEL' /opt/plp-api/brain.mjs")
    из = {}
    for м in re.finditer(r"const (MODEL\S*?)='([^']+)'", т):
        из[м.group(1)] = м.group(2)
    return из


def живой_список():
    ключ = ssh("grep -m1 '^ANTHROPIC_API_KEY=' /opt/plp-api/.env | cut -d= -f2-").strip()
    if not ключ:
        return None
    r = urllib.request.Request('https://api.anthropic.com/v1/models?limit=100',
                               headers={'x-api-key': ключ, 'anthropic-version': '2023-06-01'})
    д = json.load(urllib.request.urlopen(r, timeout=30))
    return {m['id'] for m in д.get('data', [])}


def главное():
    стоит = модели_в_бою()
    if not стоит:
        print('[модель] 🔴 не нашёл ни одной константы MODEL в /opt/plp-api/brain.mjs')
        return 1
    живые = живой_список()
    if живые is None:
        print('[модель] 🔴 ключ Anthropic не читается с сервера — сверить не с чем')
        return 1
    мёртвые = {к: v for к, v in стоит.items() if v not in живые}
    if мёртвые:
        print('[модель] 🔴 в бою стоит то, чего нет в живом списке Anthropic:')
        for к, v in мёртвые.items():
            print('   %-14s %s' % (к, v))
        print('[модель] живых моделей в списке: %d' % len(живые))
        return 1
    if not ТИХО:
        for к, v in стоит.items():
            print('[модель] %-14s %-22s живая' % (к, v))
    return 0


if __name__ == '__main__':
    sys.exit(главное())
