#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 325: зашла речь про Vibe — сразу говорим и про вторую очередь.

Эльнур 18.09.2026: «Если предлагал вайб 1, то можно сразу и про второй сообщить».

Правка 312 научила двойника предлагать Vibe II, но только в момент касания, то есть
когда мы пишем первыми. В живом разговоре, где человек сам спросил про Vibe Residence
Karon, вторая очередь не упоминалась вовсе — а это как раз момент, когда она уместна.

Теперь: если в разговоре прозвучал Vibe (по-русски или латиницей), в тот же ход
подаётся короткое напоминание сказать про вторую очередь — одной фразой, без давления,
и только один раз: если Vibe II в переписке уже звучал, молчим.

Факты те же, что в правке 312, из закрытого листа: вход около 115 тыс. ฿ за м2,
студии от примерно 3,2 млн ฿, первый Vibe за пять дней продал 61% квартир.

    python3 vps_brain_vibe2.py            # показать, что изменится
    python3 vps_brain_vibe2.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "    /* 18.09.2026 правка 312: Vibe II в касаниях, по теме"
NEW = """    /* 18.09.2026 правка 325: про Vibe спросили в живом разговоре — упомяни вторую очередь.
       Эльнур: «если предлагал вайб 1, то можно сразу и про второй сообщить». */
    try{
      var _h325=(ctx.history||[]).map(function(m){return String((m&&m.content)||'');}).join(' ');
      var _all325=String(ctx.text||'')+' '+_h325;
      var _vibe325=/vibe|вайб/i.test(_all325);
      var _said325=/vibe\\s*(?:ii|2)|вайб\\s*(?:2|два|второй)|втор(?:ая|ой)\\s+очеред/i.test(_all325);
      if(_vibe325 && !_said325){
        _JIT286+='\\n\\n🏝 РЕЧЬ ЗАШЛА ПРО VIBE. Скажи в этом же ответе одной фразой, что у застройщика '
          +'есть вторая очередь, Vibe II на Кароне, сейчас закрытый лист до официального старта: '
          +'вход около 115 тыс. ฿ за м2, студии от примерно 3,2 млн ฿. Первый Vibe за пять дней '
          +'продал 61% квартир, поэтому по второй очереди квота ограничена. Без давления и без '
          +'повторов: одной фразой, дальше по теме человека.';
      }
    }catch(_e325){}
""" + ANCHOR


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 325' in src:
        print('правка 325 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: в живом разговоре про Vibe подаётся напоминание про вторую очередь')
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
    print('  ✓ Vibe II в живом разговоре')
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
