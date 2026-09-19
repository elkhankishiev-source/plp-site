#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 320: карточку под ответом клеим только к тому объекту, о котором идёт речь.

Эльнур 18.09.2026: «я прошу совет по встрече по Естелле, а он пишет ссылку на Карон
Вайб». Он прав, и это не выдумка модели, а код.

Реплика 06:26 в рабочем WhatsApp: весь ответ по Estella (сроки, фрихолд, мебельный
пакет, УК), а последней строкой приклеено:
    «📊 Карточка «Vibe Residence Karon», цены, планировки и расчёт:
     https://property-library.com/object/vibe-karon»

Почему так вышло:
  • в его профиле с 16.09 висел фокус объекта active_object_id = PLP-VIBE-KARON;
  • слова «какие расходы, доходность» включили доставку карточки;
  • объект ответа код ищет по названиям из ПОДБОРКИ, а Estella распродана и в
    подборку не попала — значит «в ответе объект не узнан»;
  • дальше стояло `_linkId = _featId || profile.active_object_id`, и код молча взял
    трёхдневной давности фокус.

То есть при любом разговоре о том, чего нет в текущей подборке, под ответ уезжала
ссылка на прошлый проект. Для клиента это выглядит как подмена темы.

Правка: старый фокус годится, только если о нём упомянуто ПРЯМО СЕЙЧАС — в реплике
человека или в нашем ответе. Не упомянут — ссылки нет вовсе. Объект, названный в
ответе, работает как раньше.

Заодно снят сам застрявший фокус у четырёх своих профилей (team_profiles_clean.py).
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = "  var _linkId=_featId||((fc.profile&&fc.profile.active_object_id)||null);"
NEW = """  /* 18.09.2026 правка 320: см. историю в tools/vps_brain_cardlink.py.
     Фокус из профиля — только если о нём говорят сейчас, иначе ссылки нет. */
  var _focus320=(fc.profile&&fc.profile.active_object_id)||null;
  var _linkId=_featId||null;
  if(!_linkId&&_focus320){
    var _fo320=(fc.objects||[]).filter(function(o){return String(o.plp_property_id)===String(_focus320);})[0];
    var _ws320=String((_fo320&&_fo320.name)||'').replace(/[,(·].*/,'').split(/[\\s\\-]+/);
    var _bw320='';
    for(var _i320=0;_i320<_ws320.length;_i320++){
      var _w320=_ws320[_i320];
      if(_w320.length>=4&&!/^(the|title|plp|phuket|bang|tao|rawai|surin|kamala|naiyang|layan|kata|karon|autograph|collection|residences?|villas?|nai|yang|de|by)$/i.test(_w320)){_bw320=_w320;break;}
    }
    if(_bw320){
      var _hay320=String(reply||'')+' '+String(fc.text||'');
      if(new RegExp(_bw320.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'i').test(_hay320))_linkId=_focus320;
      else { try{console.log('[карточка 320] фокус '+_focus320+' не по теме ответа — ссылку не клею');}catch(_e320){} }
    }
  }"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 320' in src:
        print('правка 320 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: ссылка на карточку только по объекту из этого разговора')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:500])
        return 1
    print('  ✓ фокус из профиля больше не подставляется молча')
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
