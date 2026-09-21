#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 339: мозг перестаёт спрашивать то, что о человеке уже записано.

Эльнур: «очень важно, чтобы вся информация вела учёт» и «участник взял лида в работу — он
видит всю историю и всё знает, и как надо с ним работать, и куда дальше его двигать».

Найдено 19.09 при сверке «какие данные заполнены, но никем не читаются». В таблице
`client_facts` лежит **15 552 факта** о клиентах, собранных из amoCRM. И её не читает
НИКТО: ни мозг, ни один сценарий n8n, ни один скрипт.

Вот что там по Архату, которому мы сегодня написали:

    Цель покупки            Для инвестиций
    Мотив покупки           Инвестиция / доход
    Локация                 Kazakhstan, Nur-Sultan
    Проект                  InterContinental
    Лучшее время для связи  Viber
    Язык                    RU
    Сегмент клиента         Новый

А двойник спрашивает его «под доход или для себя?» — то есть спрашивает ровно то, что
записано. Для человека это выглядит так, будто его не слушали.

Правка: факты подгружаются по опознанному клиенту и подаются в промпт отдельным блоком,
рядом с историей CRM. Берём до двенадцати самых свежих, служебные ключи («country»,
«city» дублируют «Локация») отбрасываем.

Тон блока тот же, что у истории CRM: опираться можно, пересказывать человеку нельзя —
иначе получится «я о вас всё знаю», а это пугает.

    python3 vps_brain_client_facts.py            # показать, что изменится
    python3 vps_brain_client_facts.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

# 1. загрузка — сразу после загрузки заметок CRM, там же известен профиль
ANCHOR_LOAD = "}catch(_e330){}"
LOAD = """}catch(_e330){}
/* 19.09.2026 правка 339: факты о человеке из amoCRM (цель, мотив, город, проект, язык).
   Лежали мёртвым грузом: 15 552 записи, которые не читал никто.
   Разбор — в tools/vps_brain_client_facts.py */
var _facts339=[];
try{
  var _cid339=(_pf&&_pf[0]&&_pf[0].client_id)||null;
  if(!_cid339 && _pn){
    var _c339=await get.call(this,base+'/clients?phone=eq.'+encodeURIComponent(_pn)+'&select=client_id&limit=1');
    _cid339=(_c339[0]||{}).client_id||null;
  }
  if(_cid339){
    _facts339=await get.call(this,base+'/client_facts?client_id=eq.'+encodeURIComponent(_cid339)
      +'&select=key,value,noted_on&order=noted_on.desc&limit=14')||[];
  }
}catch(_e339){}"""

# 2. блок промпта — рядом с историей CRM
ANCHOR_BLOCK = "  var _CRMHIST330='';"
BLOCK = """  var _FACTS339='';
try{
  var _ПРОПУСК=['country','city','Источник','Сегмент клиента','Способ связи'];
  var _f339=(ctx.client_facts||[]).filter(function(f){
    return String(f.value||'').trim().length>1 && _ПРОПУСК.indexOf(String(f.key||''))<0;
  }).slice(0,12);
  if(_f339.length){
    _FACTS339='\\n\\nЧТО О НЁМ УЖЕ ЗАПИСАНО (из заявок и карточки CRM). Это факты, а не догадки: '
      +'НЕ переспрашивай то, что здесь есть, опирайся на это и уточняй только недостающее. '
      +'Человеку про записи не говори:\\n'
      + _f339.map(function(f){ return '· '+String(f.key||'')+': '+String(f.value||'').replace(/\\s+/g,' ').slice(0,90); }).join('\\n');
  }
}catch(_ef339){}
  var _CRMHIST330='';"""

STEPS = [
    (ANCHOR_LOAD, LOAD, 'загрузка фактов после заметок CRM'),
    (ANCHOR_BLOCK, BLOCK, 'блок «что о нём уже записано» в промпт'),
    ('crm_notes:_crmNotes,', 'crm_notes:_crmNotes,client_facts:_facts339,', 'факты передаются в контекст'),
    ('+_CRMHIST330+', '+_FACTS339+_CRMHIST330+', 'блок подключён к промпту'),
]


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 339' in src:
        print('правка 339 уже стоит')
        return 0
    miss = [w for o, _, w in STEPS if src.count(o) != 1]
    if miss:
        print('НЕ НАЙДЕНО однозначно: %s — отменяю' % '; '.join(miss))
        return 1
    if not APPLY:
        for _, _, w in STEPS:
            print('будет изменено: %s' % w)
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    for old, new, w in STEPS:
        src = src.replace(old, new, 1)
        print('  ✓ %s' % w)
    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
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
