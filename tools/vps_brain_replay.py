#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 332: не отвечаем на сообщение, которое уже было в переписке раньше.

18.09.2026 Wazzup, создавая чат под наше касание, подсунул реплику Ирины от 11 ноября
2025 года как свежую. Двойник ответил на неё, человек получил два сообщения подряд,
а вечером канал выпал. Правка на входе в n8n готова, но не опубликована и в бой не
идёт, а холодная работа с лидами нужна сегодня.

Поэтому ту же защиту ставим в мозге, где выкладка работает без чужих разрешений.
Признак проще и надёжнее, чем дата: если ровно этот текст уже лежит в переписке с
этим человеком и пришёл больше часа назад — это повтор истории, а не разговор.
Короткие реплики («да», «?») не трогаем: их человек может повторить по-настоящему,
поэтому проверяем только тексты длиннее 25 знаков.

    python3 vps_brain_replay.py            # показать, что изменится
    python3 vps_brain_replay.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "var _hraw=p.phone?await get.call(this,base+'/chat_history?phone_norm=eq.'+_pn"
NEW = """/* 18.09.2026 правка 332: повтор старого сообщения — это история, а не разговор.
   Причина и разбор — в tools/vps_brain_replay.py */
var _replay332=false;
try{
  var _t332=String(p.text||'').trim();
  if(_t332.length>25 && p.phone){
    var _same=await get.call(this, base+'/chat_history?phone_norm=eq.'+_pn
      +'&role=eq.user&content=eq.'+encodeURIComponent(_t332)
      +'&select=ts&order=ts.asc&limit=2')||[];
    if(_same.length){
      var _age=Date.now()-Date.parse(_same[0].ts||'');
      if(_age>3600000){ _replay332=true;
        try{console.log('[повтор 332] это же сообщение уже было '+String(_same[0].ts).slice(0,16)+' — не отвечаю');}catch(_e){}
      }
    }
  }
}catch(_e332){}
""" + ANCHOR


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 332' in src:
        print('правка 332 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(ANCHOR))
        return 1
    # второй шаг: пустой ответ, если это повтор
    RET_OLD = "return [{json:{client_memory:client_memory"
    if src.count(RET_OLD) != 1:
        print('точка возврата не найдена (%d) — правка отменена' % src.count(RET_OLD))
        return 1
    RET_NEW = ("if(_replay332){ return [{json:{skip:true, skip_reason:'повтор старого сообщения', "
               "reply:'', phone:p.phone, text:String(p.text||'')}}]; }\n"
               + RET_OLD)
    if not APPLY:
        print('будет изменено: мозг молчит, если ровно этот текст уже был в переписке час назад и раньше')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    src = src.replace(ANCHOR, NEW, 1).replace(RET_OLD, RET_NEW, 1)
    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ защита от повторов в мозге')
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
