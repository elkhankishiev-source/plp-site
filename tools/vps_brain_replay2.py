#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 332б: довести защиту от повтора до конца конвейера.

332 ставила признак и делала ранний возврат внутри сбора контекста. Но сбор контекста
не решает, отвечать или нет: makeBrain берёт его результат и всё равно ведёт дальше —
Cap check, Build Body, вызов модели. То есть признак стоял, а поведение не менялось:
модель всё равно ответила бы на подсунутую Wazzup старую реплику, только уже по пустому
контексту. Ровно та ошибка, за которую Эльнур спрашивал: проверено «обновилось», а не
«ведёт себя иначе».

Правка ставит разрыв там, где он работает — сразу после сбора контекста в makeBrain:
пустой ответ, модель не зовётся, денег не тратится. Отправки не будет: привратник
пустое сообщение наружу не пропускает.

    python3 vps_brain_replay2.py            # показать, что изменится
    python3 vps_brain_replay2.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "    store['Fetch Context'] = await run(_node_fetch, input);"
NEW = ANCHOR + """
    /* 18.09.2026 правка 332б: разрыв конвейера на повторе. Разбор — в tools/vps_brain_replay2.py */
    if (store['Fetch Context'] && store['Fetch Context'].skip === true) {
      console.log('[повтор 332] отвечать не буду: ' + String(store['Fetch Context'].skip_reason || ''));
      return { reply: '', skip: true, skip_reason: String(store['Fetch Context'].skip_reason || ''), score: null };
    }"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 332б' in src:
        print('правка 332б уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: после сбора контекста конвейер останавливается, модель не зовётся')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(ANCHOR, NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ разрыв конвейера на повторе')
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
