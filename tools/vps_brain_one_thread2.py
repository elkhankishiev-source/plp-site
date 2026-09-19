#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 333б: предохранитель на склейку истории. Один человек — это один человек.

Проверяя правку 333 на живых данных, нашёл мину в самой таблице связки. В
`contact_identities` есть строки с ПУСТЫМ client_id, и таких строк около 1300 — почти
вся база номеров висит «ни на ком». Пока client_id пустой, склейка просто не срабатывает
и это спасло. Но если кто-нибудь однажды проставит этим строкам один общий id, правка
333 послушно соберёт в одну переписку 1300 чужих людей и подаст это мозгу как историю
одного собеседника. Чужие бюджеты, чужие имена, чужие договорённости в одном окне.

Поэтому два предохранителя, оба дешёвые:
  • берём только ту строку связки, где client_id ЗАПОЛНЕН (было: первую попавшуюся —
    а первой могла оказаться пустая, и склейка молча не работала);
  • если у «человека» больше шести ключей — это не человек, а мусорная связка. Тогда
    работаем по одному ключу, как раньше, и говорим об этом в журнал.

У живого человека каналов связи единицы: номер, телеграм, инстаграм, почта. Шесть — это
уже с запасом.

    python3 vps_brain_one_thread2.py            # показать, что изменится
    python3 vps_brain_one_thread2.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

STEPS = [
    ("'/contact_identities?external_id=eq.'+encodeURIComponent(_pn)\n      +'&select=client_id&limit=1'",
     "'/contact_identities?external_id=eq.'+encodeURIComponent(_pn)\n"
     "      +'&client_id=not.is.null&select=client_id&limit=1'",
     'связку ищем только там, где владелец записи заполнен'),
    ("      if(_keys333.length>1) console.log('[одна история 333] каналов человека: '+_keys333.length);",
     "      /* 19.09.2026 правка 333б: больше шести ключей — это не человек, а мусорная связка. */\n"
     "      if(_keys333.length>6){ console.log('[одна история 333б] ключей '+_keys333.length"
     "+' — на человека не похоже, беру только свой'); _keys333=[_pn]; }\n"
     "      else if(_keys333.length>1) console.log('[одна история 333] каналов человека: '+_keys333.length);",
     'потолок в шесть ключей: мусорную связку в контекст не пускаем'),
]


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 333б' in src:
        print('правка 333б уже стоит')
        return 0
    if 'правка 333' not in src:
        print('правки 333 нет — сначала она')
        return 1
    miss = [w for o, _, w in STEPS if src.count(o) != 1]
    if miss:
        print('НЕ НАЙДЕНО однозначно: %s — отменяю' % '; '.join(miss))
        return 1
    if not APPLY:
        for _, _, w in STEPS:
            print('будет изменено: %s' % w)
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    for old, new, w in STEPS:
        src = src.replace(old, new, 1)
        print('  ✓ %s' % w)
    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
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
