#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выкладка инструмента на сервер с проверкой и откатом. И сверка всех копий.

Эльнур 23.09.2026: «правки инструментов идут в обход репозитория — желательно
распространить механизм, иначе баг».

Повод. За один день дважды: `docs_apply.py` поправили локально и не выложили —
крон падал каждый час; потом я правил живой `tools_plp_watch.py` прямо на сервере,
минуя репозиторий, и помощник поймал это во время аудита.

Правило здесь одно и жёсткое: **истина в репозитории, сервер только принимает**.
Обратного направления у инструмента нет намеренно — иначе снова разъедется.

    python3 tools/deploy_tool.py --сверить          # кто с кем разошёлся
    python3 tools/deploy_tool.py docs_apply.py      # показать, что поедет
    python3 tools/deploy_tool.py docs_apply.py --го # выложить с проверкой и откатом
    python3 tools/deploy_tool.py --всё --го         # выложить все разошедшиеся
"""
import hashlib, os, subprocess, sys

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
КЛЮЧ = os.path.expanduser('~/.ssh/plp_vps')
VPS = 'root@' + open(os.path.expanduser('~/.plp_vps_ip')).read().strip()

# Куда какой инструмент едет. Два адреса, потому что так сложилось исторически:
# в /opt/plp-api лежат те, что зовёт мозг и его кроны (с приставкой tools_),
# в /opt/plp-tools — самостоятельные инструменты.
КУДА = {
    'amo_dialog_notes.py':  '/opt/plp-tools/amo_dialog_notes.py',
    'amo_touch_notes.py':   '/opt/plp-api/tools_amo_touch_notes.py',
    'crm_notes_import.py':  '/opt/plp-api/tools_crm_notes_import.py',
    'docs_apply.py':        '/opt/plp-tools/docs_apply.py',
    'docs_parse.py':        '/opt/plp-tools/docs_parse.py',
    'mail_intake.py':       '/opt/plp-api/tools_mail_intake.py',
    'plp_watch.py':         '/opt/plp-api/tools_plp_watch.py',
    'tools_smoke.py':       '/opt/plp-tools/tools_smoke.py',
    'census_owners.py':     '/opt/plp-tools/census_owners.py',
    # 24.09.2026: главный сторож жил ТОЛЬКО на сервере и под дисциплину
    # выкладки не попадал — правка шла руками, истины в репозитории не было.
    'plp_health.py':        '/opt/plp-health.py',
}
# Чем проверить, что выложенное живо. Пусто — значит только синтаксис.
ПРОБА = {
    'plp_health.py': '',            # сам по себе только проверяет и печатает
    'docs_apply.py': '',            # без --apply только читает
    'docs_parse.py': '',
    'plp_watch.py': '',             # без --send только печатает
    'tools_smoke.py': '',
    'amo_touch_notes.py': '',
    'crm_notes_import.py': '--status',
    'census_owners.py': '',
}
ГО = '--го' in sys.argv


def ссш(команда, timeout=180):
    return subprocess.run(['ssh', '-i', КЛЮЧ, VPS, команда],
                          capture_output=True, text=True, timeout=timeout)


def отпечаток(путь):
    try:
        return hashlib.md5(open(путь, 'rb').read()).hexdigest()
    except Exception:
        return None


def отпечатки_сервера():
    пути = ' '.join(КУДА.values())
    r = ссш('md5sum %s 2>/dev/null' % пути)
    из = {}
    for ln in r.stdout.splitlines():
        ч = ln.split()
        if len(ч) == 2:
            из[ч[1]] = ч[0]
    return из


def сверка():
    сервер = отпечатки_сервера()
    расходятся = []
    print('%-24s %-34s %s' % ('инструмент', 'на сервере', 'состояние'))
    for имя, путь in sorted(КУДА.items()):
        свой = отпечаток(os.path.join(КОРЕНЬ, 'tools', имя))
        чужой = сервер.get(путь)
        if свой is None:
            сост = 'нет в репозитории'
        elif чужой is None:
            сост = 'НЕТ НА СЕРВЕРЕ'
            расходятся.append(имя)
        elif свой == чужой:
            сост = 'совпадают'
        else:
            сост = 'РАЗОШЛИСЬ'
            расходятся.append(имя)
        print('%-24s %-34s %s' % (имя, путь, сост))
    print('\nразошлись: %d из %d' % (len(расходятся), len(КУДА)))
    return расходятся


def выложить(имя):
    свой = os.path.join(КОРЕНЬ, 'tools', имя)
    цель = КУДА.get(имя)
    if not цель:
        print('не знаю, куда класть %s — допиши в КУДА' % имя)
        return False
    if not os.path.exists(свой):
        print('%s нет в репозитории' % имя)
        return False

    # 1. синтаксис у себя, до того как трогать сервер
    r = subprocess.run([sys.executable, '-c',
                        'import ast,io,sys;ast.parse(io.open(sys.argv[1],encoding="utf-8").read())', свой],
                       capture_output=True, text=True)
    if r.returncode:
        print('   ✗ синтаксис не разбирается — не выкладываю\n%s' % r.stderr.strip()[:300])
        return False
    print('   синтаксис: ок')

    if not ГО:
        print('   это отчёт. выложить: --го')
        return True

    # 2. точка возврата на сервере
    метка = цель + '.назад'
    ссш('cp -f %s %s 2>/dev/null; true' % (цель, метка))

    # 3. копируем
    r = subprocess.run(['scp', '-i', КЛЮЧ, свой, VPS + ':' + цель],
                       capture_output=True, text=True, timeout=180)
    if r.returncode:
        print('   ✗ не скопировалось: %s' % r.stderr.strip()[:200])
        return False
    print('   скопировано в %s' % цель)

    # 4. проба: синтаксис на сервере и прогон в режиме отчёта
    r = ссш('python3 -c "import ast,io;ast.parse(io.open(\'%s\',encoding=\'utf-8\').read())"' % цель)
    if r.returncode:
        ссш('cp -f %s %s' % (метка, цель))
        print('   ✗ на сервере не разбирается — ВЕРНУЛ как было')
        return False
    если_проба = ПРОБА.get(имя)
    if если_проба is not None:
        r = ссш('cd %s && timeout 240 python3 %s %s 2>&1 | tail -4'
                % (os.path.dirname(цель), os.path.basename(цель), если_проба), timeout=300)
        живой = r.stdout.strip()
        плохо = ('Traceback' in живой) or ('Error' in живой and 'ок' not in живой)
        print('   проба: %s' % (живой.replace('\n', ' | ')[:180] or 'без вывода'))
        if плохо:
            ссш('cp -f %s %s' % (метка, цель))
            print('   ✗ прогон упал — ВЕРНУЛ как было')
            return False
    print('   ✓ выложено и проверено')
    return True


def main():
    if '--сверить' in sys.argv:
        сверка()
        return 0
    if '--всё' in sys.argv:
        for имя in сверка():
            print('\n%s' % имя)
            выложить(имя)
        return 0
    имена = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not имена:
        print(__doc__)
        return 1
    беда = 0
    for имя in имена:
        print('%s' % имя)
        if not выложить(имя):
            беда = 1
    return беда


if __name__ == '__main__':
    sys.exit(main())
