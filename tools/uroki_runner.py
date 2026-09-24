#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Гоняет сторожей уроков, записанных КОМАНДОЙ, и пишет состояние обратно в базу.

Повод. 24.09.2026: из 88 уроков функция `уроки_проверить()` проверяла 31 —
она выполняет только `сторож_sql`. Ещё у 29 уроков сторож записан в поле
`сторож_команда`, и его не запускал НИКОГДА никто: база шелл выполнить не может,
а такого бегунка не существовало. Поле было заполнено, выглядело рабочим и
ничего не проверяло.

Контракт, без которого автоматика невозможна:

    КОМАНДА ВОЗВРАЩАЕТ НОЛЬ, ПОКА ВСЁ ЦЕЛО.
    Ненулевой код возврата = старая беда вернулась.

Старые команды писались иначе — «команда — и словами, что ожидать»:

    ssh root@… "grep -c _TAIL285 /opt/plp-api/brain.mjs" — меньше двух значит отвалилось

Машина такое проверить не может: ожидание живёт в прозе. Такие команды бегунок
НЕ выполняет, а честно помечает «сторож прозой — переписать». Пустота названа,
а не спрятана: ровно то, чего не хватало самому механизму.

Где запускать: на Маке. Команды написаны с его точки зрения — `~/plp-site`,
`~/.ssh/plp_vps`, `ssh root@…`. На сервере половины путей нет.

    python3 tools/uroki_runner.py            # отчёт, в базу ничего не пишет
    python3 tools/uroki_runner.py --писать   # прогнать и записать состояние
    python3 tools/uroki_runner.py --урок 61  # один урок
"""

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ПИСАТЬ = '--писать' in sys.argv
ТАЙМАУТ = 60

ОДИН = None
if '--урок' in sys.argv:
    try:
        ОДИН = int(sys.argv[sys.argv.index('--урок') + 1])
    except (IndexError, ValueError):
        sys.exit('после --урок нужен номер')

# Признак непереписанной команды: длинное тире с пояснением, что ожидать.
# Пока оно там, ожидание живёт в прозе, а не в коде возврата.
ПРОЗА = (' — ', ' – ', 'должно быть', 'должен ', 'ждём ', 'значит ', 'не ноль')

# Первое слово настоящей команды — это программа. Если первого слова нет в этом
# списке, перед нами не команда, а поручение человеку («Нажать…», «Открыть…»,
# «Проверять при каждой правке…») или чистый SQL. Запускать такое нельзя:
# 24.09 бегунок честно попробовал и получил «Нажать: command not found».
ПРОГРАММЫ = {'ssh', 'curl', 'grep', 'cd', 'python3', 'python', 'md5', 'md5sum',
             'ls', 'test', 'docker', 'psql', 'node', 'bash', 'sh', 'git',
             'diff', 'cmp', 'cat', 'head', 'tail', 'wc', 'find', 'awk', 'sed',
             'systemctl', 'journalctl', 'jq', 'printf', 'echo', 'stat'}


def какая(cmd):
    """Что это: исполнимая команда, чистый SQL или поручение человеку."""
    голый = cmd.strip().lstrip('!').strip()
    if голый[:7].lower() == 'select ':
        return 'sql'
    первое = голый.split()[0] if голый.split() else ''
    первое = первое.strip('`"\'()')
    if первое not in ПРОГРАММЫ:
        return 'человеку'
    if any(м in cmd for м in ПРОЗА):
        return 'проза'
    return 'команда'



def env():
    out = {}
    for путь in (os.path.expanduser('~/.plp_site_supabase.env'), '/opt/plp-api/.env'):
        if not os.path.exists(путь):
            continue
        for ln in open(путь, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1)
                out.setdefault(k, v.strip().strip('"\''))
        if out.get('SUPABASE_URL'):
            break
    return out


E = env()
if not E.get('SUPABASE_URL'):
    sys.exit('не нашёл SUPABASE_URL: положите ~/.plp_site_supabase.env')
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'],
     'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def запрос(путь, метод='GET', тело=None):
    r = urllib.request.Request(BASE + путь, method=метод,
                               headers=dict(H, Prefer='return=minimal'),
                               data=json.dumps(тело).encode() if тело else None)
    with urllib.request.urlopen(r, timeout=45) as resp:
        сырое = resp.read().decode('utf-8', 'ignore')
    return json.loads(сырое) if сырое.strip().startswith(('[', '{')) else None


def взять_уроки():
    поля = ','.join(urllib.parse.quote(x) for x in ('id', 'что_сломалось', 'сторож_команда'))
    путь = ('/' + urllib.parse.quote('уроки') + '?select=' + поля
            + '&' + urllib.parse.quote('сторож_команда') + '=not.is.null'
            + '&' + urllib.parse.quote('сторож_sql') + '=is.null'
            + '&order=id')
    return [у for у in (запрос(путь) or [])
            if (у.get('сторож_команда') or '').strip()
            and (ОДИН is None or у['id'] == ОДИН)]


def записать(ид, состояние, подробности):
    if not ПИСАТЬ:
        return
    запрос('/' + urllib.parse.quote('уроки') + '?id=eq.%d' % ид, 'PATCH',
           {'состояние': состояние, 'подробности': подробности[:400]})


def прогнать(cmd):
    """Ноль — всё цело. Ненулевой код — беда вернулась."""
    try:
        p = subprocess.run(cmd, shell=True, timeout=ТАЙМАУТ,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        хвост = (p.stdout or b'').decode('utf-8', 'ignore').strip().splitlines()
        return p.returncode, (хвост[-1][:200] if хвост else '')
    except subprocess.TimeoutExpired:
        return 124, 'не уложился в %d с' % ТАЙМАУТ
    except Exception as e:
        return 125, str(e)[:200]


def главное():
    уроки = взять_уроки()
    if not уроки:
        print('уроков со сторожем-командой не нашлось')
        return 0
    прозой = исполнено = вернулось = сломано = 0
    for у in уроки:
        cmd = у['сторож_команда'].strip()
        имя = (у.get('что_сломалось') or '')[:58]
        вид = какая(cmd)
        if вид != 'команда':
            прозой += 1
            метка = {'sql': 'СТОРОЖ SQL В ПОЛЕ КОМАНДЫ — перенести в сторож_sql',
                     'человеку': 'поручение человеку — машина не выполнит',
                     'проза': 'сторож прозой — переписать'}[вид]
            print('  %3d  %-9s %s' % (у['id'], вид.upper(), имя))
            записать(у['id'], метка, cmd[:200])
            continue
        код, хвост = прогнать(cmd)
        исполнено += 1
        if код == 0:
            print('  %3d  ок        %s' % (у['id'], имя))
            записать(у['id'], 'ок', '')
        elif код in (124, 125):
            сломано += 1
            print('  %3d  СЛОМАН    %s — %s' % (у['id'], имя, хвост))
            записать(у['id'], 'сторож сломан', хвост)
        else:
            вернулось += 1
            print('  %3d  ВЕРНУЛОСЬ %s — код %d, %s' % (у['id'], имя, код, хвост))
            записать(у['id'], 'ВЕРНУЛОСЬ', 'код %d: %s' % (код, хвост))
    print('\nвсего %d: выполнено %d, вернулось %d, сторож сломан %d, прозой %d'
          % (len(уроки), исполнено, вернулось, сломано, прозой))
    if not ПИСАТЬ:
        print('это отчёт, в базу ничего не записано. Записать: --писать')
    return 1 if (вернулось or сломано) else 0


if __name__ == '__main__':
    sys.exit(главное())
