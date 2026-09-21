#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расхождение «вёл один, ответственный другой» перестаёт зацикливать касание.

Найдено 19.09.2026 по живому случаю. Олеся (79384431102): касание ушло от Эльнура, а в
amoCRM за сделку отвечает Дарья. Планировщик ставит следующее касание, `touchwork.mjs`
его снимает:

    'переписку вёл Эльнур, а в CRM ответственный Дарья — разобраться руками'

Планировщик ставит снова, сторож снимает снова. Круг замкнулся, и в тех-чат каждые
пятнадцать минут падает одно и то же сообщение. Руками при этом никто ничего не разбирает.

Хуже: строкой НИЖЕ тот же код при обычном ходе сам подставляет персону ответственного
(`persona: OWNERS[L.responsible].persona`). То есть файл противоречит сам себе: в одной
ветке расхождение это повод всё снять, в другой — повод молча поправить.

Как правильно, по канону #111 «одна история на одного человека»: **кто начал разговор,
тот его и ведёт дальше**. Менять лицо посреди переписки нельзя — для человека это выглядит
как новый собеседник. А вот кто записан ответственным в CRM — наше внутреннее дело.

Правка: касание не снимается. За ним остаётся персона того, кто ВЁЛ разговор, канал
подбирается под неё же, а расхождение уходит в тех-чат одной строкой — чтобы Эльнур
решил, менять ли ответственного в CRM.

    python3 vps_touchwork_persona.py            # показать, что изменится
    python3 vps_touchwork_persona.py --apply    # применить и проверить прогоном
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-touch/touchwork.mjs'
APPLY = '--apply' in sys.argv

OLD = """    if (q.kind === 'silence' && q.persona && q.persona !== 'Бот' && q.persona !== owner.persona) {
      await sb('PATCH', '/touch_queue?id=eq.' + q.id, { status: 'cancelled', note: 'переписку вёл ' + q.persona + ', а в CRM ответственный ' + owner.persona + ' — разобраться руками' });
      log('расхождение двойника', q.id, q.persona, '≠', owner.persona);
      continue;
    }"""

NEW = """    /* 19.09.2026: расхождение «вёл один, ответственный другой» больше не снимает касание.
       Раньше планировщик ставил его заново, сторож снова снимал, и так по кругу каждые
       пятнадцать минут. По канону #111 разговор продолжает тот, кто его ВЁЛ: менять лицо
       посреди переписки нельзя, человек воспримет это как нового собеседника. Кто записан
       ответственным в CRM — наше внутреннее дело, о расхождении просто сообщаем.
       Разбор — в tools/vps_touchwork_persona.py */
    let вёл = owner;
    if (q.kind === 'silence' && q.persona && q.persona !== 'Бот' && q.persona !== owner.persona) {
      const свой = Object.values(OWNERS).find((o) => o.persona === q.persona);
      if (свой) вёл = свой;
      log('расхождение: вёл', q.persona, 'ответственный', owner.persona, '— продолжает', вёл.persona);
    }"""

OLD2 = ("    await sb('PATCH', '/touch_queue?id=eq.' + q.id, "
        "{ task_id: tid, persona: OWNERS[L.responsible].persona, source_channel_id: owner.wa });")
NEW2 = ("    await sb('PATCH', '/touch_queue?id=eq.' + q.id, "
        "{ task_id: tid, persona: вёл.persona, source_channel_id: вёл.wa });")


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'больше не снимает касание' in src:
        print('правка уже стоит')
        return 0
    for o, w in ((OLD, 'блок отмены'), (OLD2, 'подстановка персоны')):
        if src.count(o) != 1:
            print('%s найден %d раз — отменяю' % (w, src.count(o)))
            return 1
    if not APPLY:
        print('будет изменено: касание не снимается, продолжает тот, кто вёл разговор')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ цикл разорван')
    run = subprocess.run(['node', SRC], capture_output=True, text=True, timeout=240,
                         env={'PATH': '/usr/bin:/bin', 'TEST': '1', 'HOME': '/root'})
    print('пробный прогон без записи:')
    print((run.stdout or run.stderr).strip()[-700:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
