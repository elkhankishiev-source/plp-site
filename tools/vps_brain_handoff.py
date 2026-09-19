#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 324: «передайте живому человеку» — это передача, а не пожелание.

18.09.2026, сверка мёртвых сценариев: приёмник передачи человеку (d-agent-handoff)
подключён ко всем трём каналам, но за неделю не сработал НИ РАЗУ. Причина не в
проводке: ворота стоят на признаке handoff, а он появляется, только если модель сама
поставила метку [HANDOFF]. В переписке при этом лежат прямые просьбы:

  08.09 17:09 «Передайте меня живому менеджеру, хочу говорить с человеком»
  08.09 17:12 то же самое
  08.09 17:24 «Передайте меня живому менеджеру пожалуйста»
  08.09 17:29 «Хочу поговорить с живым человеком, передайте менеджеру»
  11.09 08:57 «Хочу созвон с менеджером в четверг вечером»

Человек повторил четыре раза подряд — значит его не передали ни разу.

Правка ставит передачу КОДОМ, не полагаясь на решение модели: если в реплике прямая
просьба о живом человеке, handoff=true независимо от того, что вернула модель.
Свои номера исключены: Эльнур и команда не передаются сами себе.

    python3 vps_brain_handoff.py            # показать, что изменится
    python3 vps_brain_handoff.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "const fc=$('Fetch Context').first().json;"
NEW = ANCHOR + """
/* 18.09.2026 правка 324: прямая просьба о человеке = передача. tools/vps_brain_handoff.py */
try{
  var _t324=String(fc.text||'');
  var _human324=/(жив(?:ой|ому|ым|ого)\\s+(?:человек\\w*|менеджер\\w*|оператор\\w*))|(?:поговорить|связаться|общаться)\\s+с\\s+(?:живым\\s+)?(?:человеком|менеджером|оператором)|переда(?:йте|й)\\s+(?:меня\\s+)?(?:живому|человеку|менеджеру|оператору)|позов(?:ите|и)\\s+(?:человека|менеджера|оператора|эльнура|дарью)|свяжите\\s+(?:меня\\s+)?с\\s+(?:человеком|менеджером|эльнуром|дарьей)|нужен\\s+человек[,\\s]+а\\s+не\\s+бот/i.test(_t324);
  var _own324=_OWN_TEAM.indexOf(String(fc.phone||'').replace(/[^0-9]/g,''))>=0;
  if(_human324 && !_own324 && !handoff){
    handoff=true;
    try{console.log('[передача 324] прямая просьба о живом человеке — ставлю передачу');}catch(_e){}
  }
}catch(_e324){}"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 324' in src:
        print('правка 324 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: передача человеку ставится кодом по прямой просьбе')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(ANCHOR, NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:500])
        return 1
    print('  ✓ передача по прямой просьбе')
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
