#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 330: двойник видит историю лида из CRM, а не заходит в разговор с чистого листа.

Эльнур 18.09.2026: «очень важно, чтобы вся информация вела учёт, диалоги, данные…
важно, чтобы ИИ знал контекст всего диалога, который есть в CRM и зеркале» → «го!».

Сегодня же выяснилось, что истории у нас не было: из тысячи карточек она была
импортирована у нуля, в зеркале присутствовал 31 человек. Теперь в `crm_notes`
лежит 5052 записи из amoCRM — заметки менеджеров, звонки, вложения по лидам и
контактам, с 2023 года.

Эта правка отдаёт их мозгу: если у человека есть сделка, в промпт уходит до восьми
последних записей его истории, коротко и с датами. Это не переписка из мессенджеров
(она в amoCRM лежит в отдельном разделе, куда у нашего ключа доступа нет), а рабочая
память менеджеров: что человеку обещали, что он просил, чем закончился звонок.

    python3 vps_brain_crmhistory.py            # показать, что изменится
    python3 vps_brain_crmhistory.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR_FETCH = "var _team=[];"
NEW_FETCH = """/* 18.09.2026 правка 330: история лида из amoCRM — в мозг. tools/vps_brain_crmhistory.py */
var _crmNotes=[];
try{
  var _lid330=(_pf&&_pf[0]&&_pf[0].amocrm_lead_id)||null;
  if(_lid330){
    _crmNotes=await get.call(this, base+'/crm_notes?entity_type=eq.lead&entity_id=eq.'+_lid330
      +'&select=created_at_crm,note_type,text&order=created_at_crm.desc&limit=8')||[];
  }
}catch(_e330){}
""" + ANCHOR_FETCH

ANCHOR_RET = "team:_team"
NEW_RET = "team:_team,crm_notes:_crmNotes"

ANCHOR_PROMPT = "var _TEAMLINE='';"
NEW_PROMPT = """var _CRMHIST330='';
try{
  var _cn330=(ctx.crm_notes||[]).filter(function(n){return String(n.text||'').trim().length>1;});
  if(_cn330.length){
    _CRMHIST330='\\n\\nИСТОРИЯ ЭТОГО ЧЕЛОВЕКА В НАШЕЙ CRM (записи менеджеров, свежие сверху). '
      +'Это рабочая память компании: что ему обещали, о чём он просил, чем кончился звонок. '
      +'Опирайся на неё, но НЕ пересказывай её человеку и не говори, что у тебя есть записи о нём:\\n'
      + _cn330.map(function(n){
          var d=String(n.created_at_crm||'').slice(0,10).split('-').reverse().join('.');
          return '· '+(d||'без даты')+' '+String(n.text||'').replace(/\\s+/g,' ').slice(0,160);
        }).join('\\n');
  }
}catch(_e330b){}
""" + ANCHOR_PROMPT

ANCHOR_DYN = '+_TEAMLINE+_WHOIS321+'
NEW_DYN = '+_TEAMLINE+_WHOIS321+_CRMHIST330+'


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 330' in src:
        print('правка 330 уже стоит')
        return 0
    steps = [(ANCHOR_FETCH, NEW_FETCH, 'история читается из crm_notes'),
             (ANCHOR_RET, NEW_RET, 'история едет в контекст'),
             (ANCHOR_PROMPT, NEW_PROMPT, 'блок истории собирается'),
             (ANCHOR_DYN, NEW_DYN, 'блок истории уходит в промпт')]
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
