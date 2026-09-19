#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 322: посреди разговора ничего левого. Железно, в коде и в правиле.

Эльнур 18.09.2026: «такого не должно быть вообще, это галюны, так нельзя. Диалоги
должны быть только в тему, нельзя посреди разговора сказать что-то вообще левое.
Это железно, истина!»

Правка 320 убрала причину сегодняшнего случая (ссылка на прошлый объект из фокуса).
Эта правка ставит сам запрет, чтобы левая тема не пролезла никаким другим путём:

  1. СТОРОЖ В КОДЕ. Перед отправкой каждое предложение со ссылкой на карточку
     объекта проверяется: назван ли этот проект в разговоре — в реплике человека
     или раньше в переписке. Не назван — предложение выбрасывается целиком, и это
     пишется в журнал. Исключение одно: человек прямо просит подобрать или показать
     варианты — тогда новый проект и есть ответ по теме.
  2. ПРАВИЛО В ПРОМПТЕ. Прямой запрет менять тему: отвечаем про то, о чём спросили,
     и не подставляем другой проект, акцию или ссылку по своей инициативе.

Сторож детерминированный: он не «просит модель быть аккуратнее», а режет. Поэтому
проверка идёт по названию проекта из самой ссылки, а не по смыслу.

    python3 vps_brain_ontopic.py            # показать, что изменится
    python3 vps_brain_ontopic.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

# 1. Сторож ставим сразу после блока доставки карточки (правка 320).
ANCHOR = "// === CALC/OFFER: доставка HTML-ссылки (+PDF) в диалог по объекту в фокусе ==="
GUARD = """/* 18.09.2026 правка 322: сторож «только в тему». История в tools/vps_brain_ontopic.py. */
function _ontopic322(_rep, _fc){
  try{
    var _conv=(String(_fc.text||'')+' '+((_fc.history||[]).map(function(h){
      return String((h&&(h.content||h.message))||'');}).join(' '))).toLowerCase();
    var _asks=/подбер|подбор|что есть|какие есть|варианты|покажи|предложи|каталог|подборк|альтернатив|ещё что|еще что/i.test(String(_fc.text||''));
    if(_asks) return _rep;
    var _STOP=/^(the|villa|villas|title|plp|phuket|karon|kata|rawai|surin|kamala|layan|bang|tao|nai|yang|naiyang|residence|residences|collection|autograph|condo|by|de)$/i;
    var _parts=String(_rep||'').split(/(?<=[.!?…])\\s+/);
    /* тело ответа без строк со ссылкой: если проект назван в самом разборе,
       ссылка на него по теме, даже когда человек писал имя по-русски («вайб») */
    var _body=_parts.filter(function(s){return !/property-library\\.com\\/object\\//i.test(s);}).join(' ').toLowerCase();
    var _kept=[], _cut=[];
    for(var _i=0;_i<_parts.length;_i++){
      var _s=_parts[_i];
      var _m=_s.match(/property-library\\.com\\/object\\/([a-z0-9\\-]+)/i);
      if(!_m){ _kept.push(_s); continue; }
      var _w=_m[1].split('-').filter(function(x){ return x.length>=4 && !_STOP.test(x); });
      if(!_w.length){ _kept.push(_s); continue; }
      var _ok=false;
      for(var _j=0;_j<_w.length;_j++){ var _lw=_w[_j].toLowerCase(); if(_conv.indexOf(_lw)>=0||_body.indexOf(_lw)>=0){ _ok=true; break; } }
      if(_ok) _kept.push(_s); else _cut.push(_m[1]);
    }
    if(_cut.length){
      try{console.log('[в тему 322] выброшено не по разговору: '+_cut.join(', '));}catch(_e){}
      return _kept.join(' ').replace(/\\s{2,}/g,' ').trim();
    }
  }catch(_e322){}
  return _rep;
}
""" + ANCHOR

# 2. Правило в промпте — в тот же запретный блок, где остальные «нельзя».
OLD_BAN = 'ЗАПРЕЩЕНО (помимо канона): ДЛИННОЕ ТИРЕ'
NEW_BAN = ('ЗАПРЕЩЕНО (помимо канона): '
           'МЕНЯТЬ ТЕМУ. Отвечаешь ровно про то, о чём спросили. Нельзя по своей инициативе '
           'подставлять другой проект, другую локацию, акцию, ссылку или «кстати, посмотрите» — '
           'если человек об этом не спрашивал и это не ответ на его просьбу показать варианты. '
           'Разговор про один объект — значит только про него, пока человек сам не свернёт на другое. '
           'ДЛИННОЕ ТИРЕ')


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 322' in src:
        print('правка 322 уже стоит')
        return 0
    steps = [(ANCHOR, GUARD, 'сторож «только в тему» в коде'),
             (OLD_BAN, NEW_BAN, 'запрет менять тему в правилах речи')]
    for old, _, what in steps:
        if src.count(old) != 1:
            print('якорь «%s» найден %d раз — правка отменена' % (what, src.count(old)))
            return 1
    if not APPLY:
        for _, _, what in steps:
            print('будет изменено: %s' % what)
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    for old, new, what in steps:
        src = src.replace(old, new, 1)
        print('  ✓ %s' % what)
    # вызов сторожа: сразу после того, как ссылка доставлена
    old_call = "\nreturn [{json:{persona:fc.persona||'',reply,score,handoff"
    new_call = "\nreply=_ontopic322(reply, fc);\nreturn [{json:{persona:fc.persona||'',reply,score,handoff"
    if src.count(old_call) != 1:
        shutil.copy2(bak, SRC)
        print('точка вызова сторожа не найдена (%d) — откатил' % src.count(old_call))
        return 1
    src = src.replace(old_call, new_call, 1)
    print('  ✓ сторож включён перед отдачей ответа')
    open(SRC, 'w', encoding='utf-8').write(src)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:500])
        return 1
    print('синтаксис ок; копия: %s' % bak)
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
