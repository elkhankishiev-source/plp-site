#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 333: мозг видит историю ЧЕЛОВЕКА, а не историю одного мессенджера.

Эльнур 19.09.2026: «всё идёт как продолжение единого человека, ведётся одна история на
одного человека, ты не дробишь их на 16 или на разные каналы, ты начинаешь работать с
одним человеком и ты видишь всю историю его существования от начала до конца».

Как было, проверено по коду. Ключ истории — один:
    const _pn = String(p.phone||'').replace(/[^0-9]/g,'');        (строка 579)
    var _hraw = ... '/chat_history?phone_norm=eq.' + _pn + ...    (строка 690)
То есть переписка берётся строго по тому ключу, которым человек пришёл СЕЙЧАС. Написал
в WhatsApp с номера — видим номерную ветку. Написал в Telegram, где ключ это его tg-id,
— видим только телеграмную. Одна и та же живая связка разрезана пополам.

При этом связка в базе УЖЕ ЕСТЬ и наполнена: `contact_identities`, 6023 записи, один
client_id на все его каналы; больше чем в одном канале опознаны 1620 человек. Мозг ею
просто не пользовался при сборе истории — классическое «настроено, но мертво».
Единый ID (client_resolve) вызывается ниже по коду, когда история уже собрана.

Правка: перед загрузкой истории собираем ВСЕ ключи этого человека по contact_identities
и читаем переписку по ним всем (`phone_norm=in.(…)`). Связка не нашлась — работаем как
раньше, по одному ключу. Записи amoCRM в ключи не берём: там id сделки, а не канал связи.

    python3 vps_brain_one_thread.py            # показать, что изменится
    python3 vps_brain_one_thread.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = ("var _hraw=p.phone?await get.call(this,base+'/chat_history?phone_norm=eq.'+_pn"
       "+'&meta->>archived_by=is.null'")

NEW = ("""/* 19.09.2026 правка 333: один человек — одна история (канон #111). Ключи всех его
   каналов берём из contact_identities, иначе разговор разрезан по мессенджерам.
   Разбор — в tools/vps_brain_one_thread.py */
var _keys333=[_pn];
try{
  if(_pn){
    var _own333=await get.call(this,base+'/contact_identities?external_id=eq.'+encodeURIComponent(_pn)
      +'&select=client_id&limit=1');
    var _cid333=(_own333[0]||{}).client_id||null;
    if(_cid333){
      var _all333=await get.call(this,base+'/contact_identities?client_id=eq.'+encodeURIComponent(_cid333)
        +'&channel=neq.amocrm&select=external_id,channel&limit=20')||[];
      _all333.forEach(function(x){
        var _k=String(x.external_id||'').replace(/[^0-9]/g,'');
        if(_k && _keys333.indexOf(_k)<0) _keys333.push(_k);
      });
      if(_keys333.length>1) console.log('[одна история 333] каналов человека: '+_keys333.length);
    }
  }
}catch(_e333){}
var _hkey333=(_keys333.length>1)
  ? ('phone_norm=in.('+_keys333.join(',')+')')
  : ('phone_norm=eq.'+_pn);
"""
       + "var _hraw=p.phone?await get.call(this,base+'/chat_history?'+_hkey333"
         "+'&meta->>archived_by=is.null'")


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 333' in src:
        print('правка 333 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: переписка грузится по всем ключам человека из contact_identities')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1))
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    print('  ✓ история собирается по всем каналам человека')
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
