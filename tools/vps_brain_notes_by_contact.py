#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 341: история CRM ищется и по контакту, а не только по сделке.

Продолжение разбора правки 340. После переноса блоков ниже профиля факты о клиенте
пошли (10 штук у Архата), а заметки CRM так и остались нулём. Разобрал до конца.

Две причины, обе в самом запросе правки 330:

1. Заметки искались по СДЕЛКЕ: `entity_type=eq.lead&entity_id=<amocrm_lead_id из профиля>`.
   А в базе 868 заметок из 1000 привязаны к КОНТАКТУ, и лишь 132 к сделке. То есть мимо
   проходило большинство записей менеджеров.
2. Тип сущности в базе записан двояко — и `lead`, и `leads`. Условие `eq.lead` половину
   отсекало.

Плюс сам ключ брался из профиля, которого у части людей просто нет: у Архата и Дмитрия
`client_profiles` пуст, и взять `amocrm_lead_id` неоткуда.

Правка: контакт человека находим по НОМЕРУ через `crm_contact_phones` (это работает для
всех), и берём заметки и по контакту, и по сделке, с обоими написаниями типа.

    python3 vps_brain_notes_by_contact.py            # показать, что изменится
    python3 vps_brain_notes_by_contact.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = """  var _lid330=(_pf&&_pf[0]&&_pf[0].amocrm_lead_id)||null;
  if(_lid330){
    _crmNotes=await get.call(this, base+'/crm_notes?entity_type=eq.lead&entity_id=eq.'+_lid330
      +'&select=created_at_crm,note_type,text&order=created_at_crm.desc&limit=8')||[];
  }"""

NEW = """  /* 19.09.2026 правка 341: ищем и по контакту, и по сделке, с обоими написаниями типа.
     Раньше брали только сделку и только 'lead' — мимо проходили 868 заметок из 1000,
     а у части людей профиля нет вовсе. Разбор — в tools/vps_brain_notes_by_contact.py */
  var _ids341=[];
  var _lid330=(_pf&&_pf[0]&&_pf[0].amocrm_lead_id)||null;
  if(_lid330)_ids341.push(String(_lid330));
  if(_pn){
    var _cp341=await get.call(this,base+'/crm_contact_phones?phone_norm=eq.'+encodeURIComponent(_pn)
      +'&select=contact_id&limit=3')||[];
    _cp341.forEach(function(x){ if(x.contact_id)_ids341.push(String(x.contact_id)); });
  }
  if(_ids341.length){
    _crmNotes=await get.call(this, base+'/crm_notes?entity_id=in.('+_ids341.join(',')+')'
      +'&select=created_at_crm,note_type,text,entity_type&order=created_at_crm.desc&limit=10')||[];
  }"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 341' in src:
        print('правка 341 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('точка правки найдена %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: заметки CRM ищутся по контакту и по сделке')
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
    print('  ✓ заметки ищутся по контакту и по сделке')
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
