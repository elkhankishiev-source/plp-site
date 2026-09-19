#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 334: проверка «мозг жив» перестаёт покупать ответ модели.

Найдено 19.09.2026 при разборе журнала после публикации n8n. Модель зовут ровно каждые
десять минут, в :00:07, и это не люди. Источник — `/opt/plp-health.py` в кроне root:

    */10 * * * * /usr/bin/python3 /opt/plp-health.py

Он шлёт в мозг настоящее сообщение «здравствуйте» от номера 66999000999 и ждёт полный
ответ. То есть сторож живости каждые десять минут покупает у Anthropic готовую реплику
продавца, которую никто никогда не прочитает.

Цена по журналу: один такой заход это ~3 300 входных токенов, ~29 800 чтения кэша и
~60 выходных. На Opus это около десяти центов. Шесть раз в час, 144 раза в сутки —
порядка 14 долларов в день, больше 400 в месяц. За строчку «мозг отвечает: ок».

Призма Эльнура, шаг первый: усомнись в требовании. Что мы на самом деле хотим знать?
Что сервис поднят, что он достаёт контекст из базы и что промпт собирается. Ответ модели
для этого не нужен вообще.

Правка: мозг понимает поле `probe: true`. Он проходит ВЕСЬ путь — профиль, история,
каталог, каноны, сборка промпта — и возвращает размер собранного промпта и число правил
вместо вызова модели. Сломается сборка контекста — проверка это увидит. Заплатим ноль.

    python3 vps_brain_probe.py            # показать, что изменится
    python3 vps_brain_probe.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR = "    const _reqBody = JSON.parse(store['Build Body'].claude_body);"

NEW = """    /* 19.09.2026 правка 334: проверка живости не покупает ответ модели.
       Весь путь пройден — контекст, каталог, каноны, промпт собран. Этого достаточно,
       чтобы знать, что мозг цел. Разбор — в tools/vps_brain_probe.py */
    if (input && input.probe === true) {
      var _b334 = null;
      try { _b334 = JSON.parse(store['Build Body'].claude_body); } catch (e) {}
      var _sys334 = (_b334 && _b334.system) || '';
      var _len334 = (typeof _sys334 === 'string')
        ? _sys334.length
        : JSON.stringify(_sys334 || '').length;
      console.log('[проверка 334] промпт ' + _len334 + ' знаков, модель не звал');
      return { ok: _len334 > 2000, probe: true, prompt_chars: _len334,
               canon_rules: ((store['Fetch Context'] || {}).knowledge_canon || []).length,
               history: ((store['Fetch Context'] || {}).history || []).length,
               reply: '' };
    }
""" + ANCHOR


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 334' in src:
        print('правка 334 уже стоит')
        return 0
    if src.count(ANCHOR) != 1:
        print('якорь найден %d раз — отменяю' % src.count(ANCHOR))
        return 1
    if not APPLY:
        print('будет изменено: запрос с probe:true доходит до сборки промпта и возвращает')
        print('его размер, не вызывая модель')
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
    print('  ✓ режим проверки без модели')
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
