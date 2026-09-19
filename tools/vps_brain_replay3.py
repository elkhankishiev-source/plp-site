#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 332в: тот же текст дважды за пять минут — это доставка, а не человек.

332/332б закрыли старый повтор: Wazzup подсунул реплику Ирины от ноября как свежую,
двойник ответил, человек получил второе сообщение подряд. Порог там — час и больше.

Осталась вторая половина той же беды: канал может доставить ОДНО И ТО ЖЕ сообщение
дважды за минуту. Возраст меньше часа, значит 332 пропускала, и человек снова получал
два ответа подряд. Именно за это нас и блокируют.

Середину трогать нельзя: если человек через двадцать минут повторяет вопрос, потому
что мы молчали, отвечать обязательно. Поэтому окно молчания — два края:
  • старше часа  — это история, её подсунул канал;
  • младше пяти минут — это повторная доставка одного и того же;
  • между ними — живой человек, отвечаем.

    python3 vps_brain_replay3.py            # показать, что изменится
    python3 vps_brain_replay3.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = "      if(_age>3600000){ _replay332=true;"
NEW = "      if(_age>3600000||_age<300000){ _replay332=true;"


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 332в' in src:
        print('правка 332в уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('строка условия найдена %d раз — правка отменена' % src.count(OLD))
        return 1
    mark = "/* 18.09.2026 правка 332в: два края окна — старше часа это история, младше пяти минут это повторная доставка. */\n"
    if not APPLY:
        print('будет изменено: молчим и на старом повторе, и на повторной доставке за 5 минут')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, mark + NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ два края окна молчания')
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
