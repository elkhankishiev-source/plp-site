#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож перестаёт считать застрявшим то, что просто ждёт своего часа.

Эльнур 20.09.2026: «а че там сторож в рабочей группе в тг пишет, что там за проблема и
почему, мы разве ещё всё не вылечили?.. очень хорошо, что система мониторит проблемы, но
плохо, что их никто не слушает и не чинит».

Проблема была ложной, и вот почему. Правило смотрело на время СОЗДАНИЯ касания:

    /touch_queue?status=eq.approved&created_at=lt.<час назад>

А касания волны создаются пачкой за одну минуту и раскладываются по времени на весь
день: 13:47, 14:22, 14:57, 15:32, 16:07. Через час после создания сторож объявлял
застрявшими пять штук, которые спокойно ждут своей очереди.

Правильный признак «встало» — не «давно создано», а «время отправки прошло, а не ушло».
Смотрим на `scheduled_at`: если он в прошлом больше чем на час, значит отправщик или
привратник действительно не сработали. Касания без времени судим по созданию, как раньше.

    python3 vps_watch_stuck_fix.py            # показать, что изменится
    python3 vps_watch_stuck_fix.py --apply    # применить и прогнать сторожа
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/tools_plp_watch.py'
APPLY = '--apply' in sys.argv

OLD = """    stuck = get('/touch_queue?status=eq.approved&created_at=lt.' + urllib.parse.quote(iso(70))
                + '&select=id,phone,created_at,note&limit=20')"""

NEW = """    # 20.09.2026: «застряло» — это когда ВРЕМЯ ОТПРАВКИ прошло, а касание не ушло.
    # Раньше смотрели на время создания, и вся волна, разложенная по часам вперёд,
    # объявлялась застрявшей через час после постановки в очередь.
    час_назад = urllib.parse.quote(iso(70))
    stuck = [t for t in get('/touch_queue?status=eq.approved'
                            '&select=id,phone,created_at,scheduled_at,note&limit=60')
             if (str(t.get('scheduled_at') or '') < час_назад.replace('%3A', ':')
                 if t.get('scheduled_at')
                 else str(t.get('created_at') or '') < час_назад.replace('%3A', ':'))]"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'ВРЕМЯ ОТПРАВКИ прошло' in src:
        print('правка уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: застрявшим считается просроченное, а не просто созданное давно')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1))
    chk = subprocess.run(['python3', '-c',
                          'import ast;ast.parse(open("%s",encoding="utf-8").read())' % SRC],
                         capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    run = subprocess.run(['python3', SRC], capture_output=True, text=True, timeout=240)
    print('  ✓ применено\n\nпрогон без отправки:')
    print((run.stdout or run.stderr).strip()[-600:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
