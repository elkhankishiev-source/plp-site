#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 337: связка каналов человека пополняется сама, а не живёт разовым импортом.

Эльнур 19.09.2026: «главное еще что бы каждый человек имел историю хронологию, а наша
умная система вела ее и пользовалась ей».

Пользоваться научились правкой 333: мозг собирает переписку по ВСЕМ ключам человека из
`contact_identities`. А вот ВЕСТИ — нет. Проверка показала: все записи в этой таблице
датированы 16.09, источники «crm_contacts» и «chat_history», то есть это разовый импорт.
Ни один сценарий и ни одна часть мозга туда не пишет.

Значит связка мёртвая: человек, который завтра напишет с нового канала, к своей истории
присоединён не будет, и разговор опять разрежется надвое. Ровно как было до 333.

Правка: сразу после `client_resolve` (он уже определяет единый client_id по любому
каналу) записываем связь «этот client_id ↔ этот ключ ↔ этот канал», если её ещё нет.
Одна запись на человека и канал; повторы отсекаются проверкой перед вставкой.

Пишем только когда клиент опознан и ключ похож на настоящий адрес — мусор в связку не
пускаем, иначе получим склейку чужих людей (об этом предохранитель 333б).

    python3 vps_brain_identity_grow.py            # показать, что изменится
    python3 vps_brain_identity_grow.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "    if(_r0&&_r0.code)client={id:_r0.client_id,code:_r0.code,temp:_r0.temp,is_new:!!_r0.is_new};"

NEW = ANCHOR + """
    /* 19.09.2026 правка 337: ведём связку каналов, а не только читаем её.
       Без этого contact_identities остаётся разовым импортом от 16.09, и правка 333
       не увидит новых каналов человека. Разбор — в tools/vps_brain_identity_grow.py */
    try{
      if(client&&client.id&&_handle&&/^[0-9]{6,20}$/.test(String(_handle).replace(/\\D/g,''))){
        var _key337=String(_handle).replace(/\\D/g,'');
        var _есть=await get.call(this,base+'/contact_identities?client_id=eq.'
          +encodeURIComponent(client.id)+'&external_id=eq.'+encodeURIComponent(_key337)
          +'&select=id&limit=1');
        if(!_есть.length){
          await this.helpers.httpRequest({ timeout:15000, method:'POST',
            url:base+'/contact_identities',
            headers:Object.assign({},h,{'Content-Type':'application/json',Prefer:'return=minimal'}),
            body:{client_id:client.id, channel:_chan, external_id:_key337,
                  display:(p.name||null), source:'разговор', first_seen:new Date().toISOString(),
                  last_seen:new Date().toISOString()}, json:true});
          console.log('[связка 337] к человеку '+client.code+' добавлен канал '+_chan+' / '+_key337);
        }
      }
    }catch(_e337){}"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 337' in src:
        print('правка 337 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — отменяю' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: после опознания клиента связь «человек ↔ канал» дописывается')
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
    print('  ✓ связка каналов теперь пополняется')
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
