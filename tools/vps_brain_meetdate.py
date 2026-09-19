#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 331: встречу нельзя поставить через год. Проверяем дату перед бронью.

18.09.2026 Эльнур переслал двойнику текст «Онлайн-встреча по проекту Estella сегодня,
18 сентября, в 14:30 по Пхукету». Двойник забронировал встречу на **18 сентября 2027
года**: создал событие в Google Календаре, выдал ссылку Meet и завёл запись в базе.
Обнаружено при сверке 19.09, фантом снят.

Причина: дату выбирает модель и отдаёт готовой строкой ГГГГ-ММ-ДД. Год она может
написать любой, а код брал строку как есть — проверялся только формат.

Правка: перед бронью смотрим на дату. Прошлое и всё, что дальше 92 дней, не бронируем,
а возвращаем модели требование переспросить день у человека. Девяносто два дня это
заведомо больше любой живой договорённости о созвоне и заведомо меньше года.

    python3 vps_brain_meetdate.py            # показать, что изменится
    python3 vps_brain_meetdate.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = """    const kind = ['online', 'office', 'tour'].indexOf(String((inp && inp.kind) || '')) >= 0 ? inp.kind : 'online';"""
NEW = """    /* 18.09.2026 правка 331: двойник поставил встречу на 2027 год из фразы «18 сентября».
       Дату теперь проверяем: прошлое и дальше 92 дней не бронируем. tools/vps_brain_meetdate.py */
    const _when331 = Date.parse(w.length <= 16 ? (w + ':00+07:00') : w);
    const _days331 = (_when331 - Date.now()) / 86400000;
    if (!_when331 || _days331 < -0.5 || _days331 > 92) {
      return 'Дата ' + w.slice(0, 16) + ' не годится: она ' + (_days331 > 92 ? 'слишком далеко' : 'в прошлом')
           + '. Переспроси у человека день и час одной короткой фразой и вызови снова, '
           + 'указав ближайшую подходящую дату этого года.';
    }
""" + OLD


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 331' in src:
        print('правка 331 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('якорь найден %d раз — правка отменена' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: дата встречи проверяется перед бронью (прошлое и дальше 92 дней отбиваются)')
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
    print('  ✓ проверка даты встречи')
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
