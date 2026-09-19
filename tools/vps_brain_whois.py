#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 321: «кто есть кто» переезжает из текста в опознание по номеру.

Эльнур 18.09.2026: «я уже давал задачу, чтобы вся система чётко понимала и различала,
кто есть кто и как мы общаемся, не путали и следовали этому, ты не фиксируешь в железо…
даже сами участники должны знать друг друга, чтобы мы могли общаться и взаимодействовать».

Как было. Реестр участников (system_participants, 17 записей с 14.09) описывал роли
ПРОЗОЙ, и номера лежали внутри текста: «Двойник Эльнур: WhatsApp +66955492587».
Опознать по такой строке невозможно, поэтому код пользовался отдельным зашитым
списком _OWN_TEAM, а он жил своей жизнью. Отсюда путаница: рабочий номер числился
в карточке «Оксана Штойк Валид Пхт Plp Рабочий», а личный — «ТЕСТ Клод сквозной
(удалить)», и система не знала, что оба — Эльнур.

Что сделано до этой правки (в базе): у реестра появились настоящие поля —
phones, tg_ids, channel_ids, persona, is_internal, address_as — и они заполнены.

Что делает правка в коде:
  1. Реестр читается вместе с номерами (раньше брались только название и роль).
  2. «Свой» определяется по реестру ИЛИ по зашитому списку: список остаётся
     страховкой на случай, если база недоступна, но истина теперь одна — таблица.
  3. В промпт подаётся строка «КТО ПЕРЕД ТОБОЙ» с именем из реестра — чтобы двойник
     не гадал, свой это, коллега или клиент, и обращался как принято.

    python3 vps_brain_whois.py            # показать, что изменится
    python3 vps_brain_whois.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD_SEL = ("'/system_participants?select=code,title,purpose,escalates_to,"
           "visible_to_client,active&active=is.true&limit=30'")
NEW_SEL = ("'/system_participants?select=code,title,purpose,escalates_to,"
           "visible_to_client,active,phones,tg_ids,channel_ids,persona,is_internal,"
           "address_as&active=is.true&limit=30'")

OLD_OWN = 'var _isOwnerChat=_OWN_TEAM.indexOf(String(ctx.phone||"").replace(/[^0-9]/g,""))>=0;'
NEW_OWN = """/* 18.09.2026 правка 321: своего опознаёт РЕЕСТР участников, зашитый список — страховка.
   Подробности и причина — в tools/vps_brain_whois.py. */
var _me321=null;
try{
  var _phone321=String(ctx.phone||"").replace(/[^0-9]/g,"");
  (ctx.team||[]).forEach(function(t){
    if(_me321||!_phone321)return;
    var _ph=[].concat(t.phones||[],t.tg_ids||[]).map(function(x){return String(x).replace(/[^0-9]/g,"");});
    if(_ph.indexOf(_phone321)>=0)_me321=t;
  });
}catch(_e321){}
var _isOwnerChat=(_me321&&_me321.is_internal===true)||_OWN_TEAM.indexOf(String(ctx.phone||"").replace(/[^0-9]/g,""))>=0;
var _WHOIS321='';
if(_me321){
  _WHOIS321='\\n\\nКТО ПЕРЕД ТОБОЙ: '+String(_me321.address_as||_me321.title||'')
    +(_me321.is_internal?' — это НАШ человек из реестра участников, не клиент. Анкету не задаёшь, не продаёшь, работаешь как рабочая рука.'
                        :' — участник нашего контура по реестру.')
    +' Так записано в реестре участников, это не догадка.';
  try{console.log('[кто 321] '+(_me321.code||'')+' | '+(_me321.address_as||_me321.title||''));}catch(_e321b){}
}"""

OLD_DYN = '+_TEAMLINE+'
NEW_DYN = '+_TEAMLINE+_WHOIS321+'


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 321' in src:
        print('правка 321 уже стоит')
        return 0
    steps = [(OLD_SEL, NEW_SEL, 'реестр читается вместе с номерами'),
             (OLD_OWN, NEW_OWN, 'свой определяется по реестру, список — страховка'),
             (OLD_DYN, NEW_DYN, 'строка «кто перед тобой» уходит в промпт')]
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
