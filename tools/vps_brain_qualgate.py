#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 319: анкету пишем только тем, кто покупает. Свои и партнёры — не лиды.

Эльнур 18.09.2026: «если система держит меня как покупателем, почему тогда она
выдаёт мне секреты внутрянку».

Вторая половина того же вопроса. Читать досье двойник своим уже не даёт (правка 317),
а ПИСАТЬ анкету продолжал всем подряд: разборщик `_qual241` тянет из любого сообщения
бюджет, район, цель и спальни и кладёт их в client_profiles по номеру. Роль при этом
не смотрится вовсе. Доказательство из журнала ровно сегодня, 06:33:

    [qual] записано: district_interest,location_preference | {"district_interest":["Karon"], …}
    [инструменты] роль Эльнур: весь набор (9)

Это была реплика самого Эльнура — и система записала ему «интересуется Кароном».
Так и получается, что система «держит его покупателем»: его же профиль наполняется
анкетой лида. То же самое происходило с застройщиками и партнёрами: их прайс
с ценами и площадями оседал у них в карточке как «бюджет клиента».

Правка: перед записью смотрим, кто это.
  • номер из _OWN_TEAM — свои, не пишем;
  • contact_role partner / developer / colleague / internal / family — не пишем
    (справочник роли в базе: lead, partner, developer, colleague, family, internal,
     buyer, spam — своим ставим internal);
  • всем остальным всё как было.
Запись не просто пропускается, а пишется в журнал с причиной — иначе завтра нельзя
будет проверить, что правка работает.

    python3 vps_brain_qualgate.py            # показать, что изменится
    python3 vps_brain_qualgate.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = "if(Object.keys(_pp).length&&p.phone){\n"
NEW = """/* 18.09.2026 правка 319: анкета — только покупателю. Свой номер и партнёр/застройщик
   получали в свой профиль «бюджет», «район» и «цель», надёрганные из их же сообщений. */
var _roleQ319=String(_prof0.contact_role||'').toLowerCase();
var _notLead319=(_OWN_TEAM.indexOf(_pn)>=0)?'свой номер'
  :(['partner','developer','colleague','internal','family','team','owner'].indexOf(_roleQ319)>=0?('роль '+_roleQ319):'');
if(_notLead319&&Object.keys(_pp).length){
  try{console.log('[qual] НЕ пишу ('+_notLead319+'): '+Object.keys(_pp).join(','));}catch(_e319){}
  _pp={};
}
if(Object.keys(_pp).length&&p.phone){
"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 319' in src:
        print('правка 319 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: перед записью анкеты проверяется роль (свои и партнёры — мимо)')
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
    print('  ✓ ворота роли перед записью анкеты')
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
