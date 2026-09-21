#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 342: блоки загрузки контекста перестают падать молча.

Урок дня 19.09.2026. Правка 330 не работала с момента установки и выглядела живой ровно
потому, что была обёрнута в `try{...}catch(_e330){}` — пустой catch. Ошибка
`ReferenceError: Cannot access '_pf' before initialization` возникала на каждом вызове и
никуда не попадала. Ни в журнал, ни в ответ, никуда.

Проверить это было нечем: `node --check` синтаксис принимает, сервис поднимается, ответы
приходят. Просто в промпте нет куска, который должен там быть.

Правка делает пустые catch громкими у блоков, которые ОБЯЗАНЫ что-то дать в контекст:
история CRM, факты о человеке, связка каналов, участники. Теперь поломка любого из них
оставляет строку в журнале и её видно в `journalctl -u plp-api`.

Правило на будущее: если блок обязан что-то принести, его catch обязан об этом кричать.

    python3 vps_brain_loud_catch.py            # показать, что изменится
    python3 vps_brain_loud_catch.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

# метка catch → что именно не загрузилось
БЛОКИ = {
    '_e330': 'история CRM',
    '_e339': 'факты о человеке',
    '_e337': 'связка каналов',
    '_e333': 'история по всем каналам',
    '_e321': 'реестр участников',
}


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 342' in src:
        print('правка 342 уже стоит')
        return 0
    план = []
    for метка, что in БЛОКИ.items():
        старое = '}catch(%s){}' % метка
        if src.count(старое) == 1:
            новое = ("}catch(%s){ try{console.log('[сбой 342] не загрузилось: %s — '"
                     "+String(%s&&%s.message||%s).slice(0,120));}catch(_){} }"
                     % (метка, что, метка, метка, метка))
            план.append((старое, новое, что))
        else:
            print('   пропускаю %s (%s): найдено %d раз' % (метка, что, src.count(старое)))
    if not план:
        print('нечего менять')
        return 0
    for _, _, что in план:
        print('будет громким: %s' % что)
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    src = src.replace('/* 18.09.2026 правка 330',
                      '/* правка 342: пустые catch ниже сделаны громкими — tools/vps_brain_loud_catch.py */\n'
                      '/* 18.09.2026 правка 330', 1)
    for старое, новое, _ in план:
        src = src.replace(старое, новое, 1)
    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ %d блоков теперь сообщают о сбое' % len(план))
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
