#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 335: «это Дарья» определяется в системе ОДИН раз, а не двумя разными способами.

Эльнур 19.09.2026 прислал Дарье её же реплику:

    «Поняла, коротко. Текст готов, но номера получателя у меня нет,
     поэтому в очередь я ничего НЕ ПОСТАВИЛ. Пришли номер, и ПОСТАВЛЮ.»
    «Ты ведь женский род, а почему — не поставиЛ?»

Разобрал до конца, и виновата не модель. Эта фраза ЗАШИТА в коде, строка 2777, и у неё
есть оба варианта:

    reply += (_isDar ? '…я ничего не поставила…' : '…я ничего не поставил…');

Значит в тот момент `_isDar` был ложным. Смотрим, как он считается:

    строка 1168 (для промпта):  _isDaria = ctx.persona ? (ctx.persona === 'Дарья') : (…канал…)
    строка 1927 (для кода):     _isDar   = (_DCH.indexOf(channelId) >= 0) || phone === '66960169127'

Один и тот же вопрос «это Дарья?» решается двумя разными способами. Промпт слушает
ПЕРСОНУ, а код — только канал и один номер. Эльнур писал Дарье со своего личного номера:
персона пришла «Дарья» (это видно в переписке), а канал под условие не подошёл — и код
решил, что говорит мужчина.

Последствия были шире одной фразы, все три из-за этой же строки:
  • зашитые реплики уходили в мужском роде;
  • род-гард (строка 2052) при `!_isDar` работает В ОБРАТНУЮ СТОРОНУ и переписывает
    женские формы в мужские — то есть система сама портила правильный текст модели;
  • тревога «род 291» молчала: за неделю ноль срабатываний при живой ошибке сегодня.

Правка делает признак ОДНИМ: сначала персона, и только если персоны нет — канал и номер.
Ровно так же, как это уже решено для промпта.

    python3 vps_brain_gender.py            # показать, что изменится
    python3 vps_brain_gender.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = ("const _isDar=(_DCH.indexOf(String(fc.channelId||''))>=0)"
       "||String(fc.phone||'')==='66960169127';")

NEW = ("""/* 19.09.2026 правка 335: признак «это Дарья» один на всю систему. Раньше промпт
   смотрел персону, а код — только канал, и при разговоре с личного номера код считал,
   что говорит мужчина: зашитые фразы уходили в мужском роде, род-гард переписывал
   женские формы в мужские, тревога молчала. Разбор — в tools/vps_brain_gender.py */
const _isDar=String(fc.persona||'')
  ? String(fc.persona||'')==='Дарья'
  : ((_DCH.indexOf(String(fc.channelId||''))>=0)||String(fc.phone||'')==='66960169127');
try{ console.log('[род 335] персона='+String(fc.persona||'(нет)')+' → '+(_isDar?'Дарья, женский род':'мужской род')); }catch(_e335){}""")


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 335' in src:
        print('правка 335 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('строка признака найдена %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: _isDar считается по персоне, как и в промпте')
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
    print('  ✓ признак «это Дарья» теперь один')
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
