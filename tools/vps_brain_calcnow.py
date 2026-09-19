#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 326: просят посчитать — считай инструментом, а не обещай.

Эльнур 18.09.2026 в своём же диалоге, 16:23 по Пхукету: «Ничего не считает, с чего вдруг».
И он прав. В ответе стояло «точную цифру по конкретному юниту прогоню через калькулятор
с графиком платежей» — то есть обещание вместо действия, притом что инструмент расчёта
у двойника есть и работает.

Это тот же патерн, который Эльнур гоняет весь день: сказал — значит сделал в том же ходе.
Общее правило в большом промпте теряется, поэтому требование подаётся ровно в тот ход,
когда человек попросил считать: код видит просьбу и добавляет указание вызвать
plp_yield_calc по объекту, о котором идёт речь.

    python3 vps_brain_calcnow.py            # показать, что изменится
    python3 vps_brain_calcnow.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = '  if(_tm310){'
NEW = """  /* 18.09.2026 правка 326: просьба посчитать = вызов калькулятора в этом же ходе.
     Эльнур: «Ничего не считает, с чего вдруг». История в tools/vps_brain_calcnow.py */
  try{
    var _t326=String(ctx.text||'');
    var _ask326=/посчита|рассчита|расч[её]т|доходност|окупаем|сколько\\s+(?:принес|заработ|выход|будет)|график\\s*платеж|рассрочк|roi|yield/i.test(_t326);
    if(_ask326){
      var _obj326='';
      try{
        (ctx.objects||[]).forEach(function(o){
          if(_obj326)return;
          var w=String(o.name||'').replace(/[,(·].*/,'').split(/[\\s\\-]+/).filter(function(x){
            return x.length>=4 && !/^(the|title|plp|phuket|villa|villas|residence|residences|collection|karon|kata|rawai|surin|kamala|layan|bang|tao|nai|yang)$/i.test(x);})[0];
          if(w && new RegExp(w.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'i').test(_t326+' '+String((ctx.profile&&ctx.profile.active_object_id)||''))) _obj326=String(o.name||'');
        });
      }catch(_e){}
      _JIT286+='\\n\\n🧮 ЧЕЛОВЕК ПОПРОСИЛ ПОСЧИТАТЬ. Считай СЕЙЧАС инструментом plp_yield_calc'
        +(_obj326?(' по объекту «'+_obj326.slice(0,60)+'»'):' по объекту, о котором идёт речь')
        +', и дай цифры в ответе. ЗАПРЕЩЕНО обещать расчёт словами: «прогоню через калькулятор», '
        +'«посчитаю и пришлю», «подготовлю расчёт» — это обещание без дела. Если объект непонятен, '
        +'спроси ОДИН короткий вопрос, какой юнит считаем, и всё.';
    }
  }catch(_e326){}
""" + ANCHOR


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 326' in src:
        print('правка 326 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: на просьбу посчитать подаётся требование вызвать калькулятор')
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
    print('  ✓ расчёт делается, а не обещается')
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
