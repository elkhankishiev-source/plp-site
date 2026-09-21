#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 340: история CRM и факты о клиенте грузятся ПОСЛЕ того, как профиль прочитан.

Найдено 19.09.2026, когда новая правка 339 показала `facts: 0` при десяти фактах в базе.

Разбор. Оба блока обращаются к профилю `_pf`:

    строка 653 (правка 330):  var _lid330 = (_pf && _pf[0] && _pf[0].amocrm_lead_id) || null;
    строка 664 (правка 339):  var _cid339 = (_pf && _pf[0] && _pf[0].client_id) || null;

А объявлен профиль ниже:

    строка 766:  const _pf = p.phone ? await get.call(...client_profiles...) : [];

`const` в JavaScript не поднимается: обращение до объявления бросает ReferenceError. Оба
блока обёрнуты в try/catch, поэтому падали молча — и выглядели работающими.

Значит **правка 330 не работала ни разу с момента установки 18.09**: история лида из
amoCRM в мозг не попадала, хотя 5052 заметки были импортированы, и я об этом отчитался.
Классическое «настроено, но мертво», причём созданное мной.

Правка переносит оба блока ниже объявления профиля, ничего в них не меняя.

    python3 vps_brain_fix_order.py            # показать, что изменится
    python3 vps_brain_fix_order.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, re, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv


def вырезать(src, начало, конец):
    i = src.index(начало)
    j = src.index(конец, i) + len(конец)
    return src[i:j], src[:i] + src[j:]


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 340' in src:
        print('правка 340 уже стоит')
        return 0

    н330 = '/* 18.09.2026 правка 330'
    н339 = '/* 19.09.2026 правка 339'
    якорь = "const _pf=p.phone?await get.call(this,base+'/client_profiles?or=(phone_norm.eq.'+_pn"
    for имя, что in (('блок 330', н330), ('блок 339', н339), ('объявление профиля', якорь)):
        if src.count(что) != 1:
            print('%s найден %d раз — отменяю' % (имя, src.count(что)))
            return 1
    if src.index(н330) > src.index(якорь):
        print('блоки уже ниже профиля — переносить нечего')
        return 0

    if not APPLY:
        print('будет изменено: блоки 330 и 339 переедут ниже объявления профиля')
        print('сейчас 330 на позиции %d, 339 на %d, профиль на %d'
              % (src.index(н330), src.index(н339), src.index(якорь)))
        print('\nЭто отчёт. Применить: --apply')
        return 0

    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)

    кусок339, src = вырезать(src, н339, '}catch(_e339){}')
    кусок330, src = вырезать(src, н330, '}catch(_e330){}')
    # строка объявления профиля целиком, до конца строки
    i = src.index(якорь)
    j = src.index('\n', i)
    шапка = ('\n/* 19.09.2026 правка 340: эти два блока стояли ВЫШЕ объявления профиля и падали\n'
             '   в ReferenceError молча — см. tools/vps_brain_fix_order.py */\n')
    src = src[:j + 1] + шапка + кусок330 + '\n' + кусок339 + '\n' + src[j + 1:]

    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ блоки перенесены ниже профиля')
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
