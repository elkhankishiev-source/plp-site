#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 319б: в ворота анкеты добавлены роли internal и family.

Справочник ролей в базе задан проверкой contact_role_ok и допускает ровно:
lead, partner, developer, colleague, family, internal, buyer, spam.
В правке 319 я перечислил свои выдуманные «team» и «owner», которых в базе быть
не может, и забыл две настоящие: internal (наши) и family (родные — тот случай,
когда двойник не узнал брата Эльнура и начал вести его как лида).
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv
OLD = ":(['partner','developer','team','owner','colleague'].indexOf(_roleQ319)>=0?('роль '+_roleQ319):'');"
NEW = ":(['partner','developer','colleague','internal','family','team','owner'].indexOf(_roleQ319)>=0?('роль '+_roleQ319):'');"


def main():
    src = open(SRC, encoding='utf-8').read()
    if NEW in src:
        print('правка 319б уже стоит')
        return 0
    if OLD not in src:
        print('якорь не найден — правка отменена')
        return 1
    if not APPLY:
        print('будет изменено: роли internal и family тоже не получают анкету лида')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ internal и family в воротах')
    subprocess.run(['systemctl', 'restart', 'plp-api'], capture_output=True, timeout=120)
    subprocess.run(['sleep', '4'])
    st = subprocess.run(['systemctl', 'is-active', 'plp-api'], capture_output=True, text=True).stdout.strip()
    print('сервис: %s' % st)
    if st != 'active':
        shutil.copy2(bak, SRC)
        subprocess.run(['systemctl', 'restart', 'plp-api'], capture_output=True, timeout=120)
        print('не поднялся — откатил')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
