#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 336: Дарья ведёт продажи. Промпт говорил обратное реестру.

Эльнур 19.09.2026, когда я в третий раз переспросил, можно ли писать покупателям от лица
Дарьи: «вот результат когда ты не слушаешь меня и не пишешь в железо. Она работает на
продажах в основном, и отвечает за аренду, но там в основном может гнать ИИ, и передавать
потом Дарье».

Он прав дважды. Во-первых, реестр участников УЖЕ описывал её верно:

    «Двойник ИИ на рабочих каналах Дарьи… Ведёт продажи наравне с Эльнуром
     и сверх того всю аренду, управление и заселение.»

Во-вторых, промпт мозга говорил ровно обратное, причём в обеих персонах сразу:

    «Мы семейное бутиковое агентство: Эльнур основатель, Дарья партнёр и супруга;
     он ведёт продажи, ОНА АРЕНДУ И УПРАВЛЕНИЕ.»

Эта строка стоит и у Дарьи, и у Эльнура. Значит двойник Дарьи читал про себя, что продажи
не её дело, а двойник Эльнура — что отдавать ей покупателя неправильно. Отсюда и моя
осторожность: я поверил промпту, а не реестру.

Правка приводит промпт к реестру и к словам Эльнура.

    python3 vps_brain_daria_role.py            # показать, что изменится
    python3 vps_brain_daria_role.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = ('Мы семейное бутиковое агентство: Эльнур основатель, Дарья партнёр и супруга; '
       'он ведёт продажи, она аренду и управление.')

NEW = ('Мы семейное бутиковое агентство: Эльнур основатель, Дарья партнёр и супруга. '
       'ПРОДАЖИ ВЕДУТ ОБА, наравне: и Эльнур, и Дарья. Сверх того на Дарье аренда, '
       'управление и заселение. Передать клиента от одного к другому можно всегда, '
       'это не смена темы и не понижение уровня.')


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'ПРОДАЖИ ВЕДУТ ОБА' in src:
        print('правка 336 уже стоит')
        return 0
    n = src.count(OLD)
    if n < 1:
        print('строка не найдена — отменяю')
        return 1
    print('строка встречается %d раз (в персонах Дарьи и Эльнура)' % n)
    if not APPLY:
        print('\nбыло:  %s\nстанет: %s' % (OLD, NEW))
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ роль Дарьи в промпте совпала с реестром')
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
