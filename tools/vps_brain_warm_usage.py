#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прогрев кэша тоже стоит денег — пусть он попадает в счётчик.

Сверка расхода 21.09.2026. В таблице `ai_usage` за 20.09 стоит ОДНА строка на
$0.37. В логе за те же сутки — 201 сборка промпта. Разбор:

    144  бесплатная проверка живости (правка 334, модель не звали)
     48  прогрев кэша (правка 319) — ПЛАТНЫЙ, но в учёт не попадает
      1  настоящий ответ клиенту — единственный, что записан

Прогрев делает свой запрос к Anthropic и выходит через `return` ДО того места,
где пишется строка расхода. Формально это не ошибка — просто ветка вышла раньше.
По деньгам: 48 прогревов в сутки по ~29 900 токенов чтения кэша, это порядка
$0.40 в день и **около $22 в месяц мимо всякого учёта**.

Почему это хуже, чем сама сумма. Счётчик — единственное место, где видно, куда
уходят кредиты. Пока треть расхода в него не попадает, любой разбор «почему так
дорого» начинается с неверных цифр: 20.09 по учёту кажется, что система почти
ничего не потратила, хотя реально работала весь день.

Правка добавляет запись в `ai_usage` прямо в ветке прогрева, перед выходом.
Помечаем отдельным именем `brain_warm`, чтобы прогрев было видно отдельно от
живых диалогов и можно было честно спросить: а окупается ли он вообще.

Запись мягкая: любая ошибка глотается, на сам прогрев не влияет.

    python3 vps_brain_warm_usage.py            # показать правку
    python3 vps_brain_warm_usage.py --apply    # применить и перезапустить мозг
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

БЫЛО = """        const u = (_w && _w.usage) || {};
        console.log('319 прогрев кэша: чтение ' + (u.cache_read_input_tokens || 0)
                    + ', запись ' + (u.cache_creation_input_tokens || 0));"""

СТАЛО = """        const u = (_w && _w.usage) || {};
        console.log('319 прогрев кэша: чтение ' + (u.cache_read_input_tokens || 0)
                    + ', запись ' + (u.cache_creation_input_tokens || 0));
        /* 21.09.2026: прогрев выходил через return ДО записи расхода, и около
           48 платных вызовов в сутки не попадали в ai_usage вовсе (~$22/мес
           мимо учёта). Пишем отдельным именем brain_warm — так видно, сколько
           стоит сам прогрев, и можно проверить, окупается ли он. */
        try {
          await helpers.httpRequest({ method: 'POST', timeout: 5000,
            url: env.SUPABASE_URL + '/rest/v1/ai_usage',
            headers: { apikey: env.SUPABASE_SERVICE_KEY,
                       Authorization: 'Bearer ' + env.SUPABASE_SERVICE_KEY,
                       'Content-Type': 'application/json', Prefer: 'return=minimal' },
            body: { wf: 'brain_warm', model: (_w && _w.model) || MODEL,
                    channel: 'warm', phone: (input && input.phone) || null,
                    input_tokens: u.input_tokens || 0, output_tokens: u.output_tokens || 0,
                    cache_read: u.cache_read_input_tokens || 0,
                    cache_write: u.cache_creation_input_tokens || 0 },
            json: true });
        } catch (_eWarm) {}"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'brain_warm' in src:
        print('правка уже стоит')
        return 0
    n = src.count(БЫЛО)
    if n != 1:
        print('точка правки найдена %d раз — отменяю' % n)
        return 1
    print('в ветку прогрева добавляется запись расхода под именем brain_warm')
    print('было: прогрев платит и выходит молча')
    print('стало: каждый прогрев виден в ai_usage отдельной строкой')
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0

    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(БЫЛО, СТАЛО, 1))

    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1

    subprocess.run(['systemctl', 'restart', 'plp-api'], capture_output=True, timeout=120)
    subprocess.run(['sleep', '4'])
    st = subprocess.run(['systemctl', 'is-active', 'plp-api'],
                        capture_output=True, text=True).stdout.strip()
    if st != 'active':
        shutil.copy2(bak, SRC)
        subprocess.run(['systemctl', 'restart', 'plp-api'], capture_output=True, timeout=120)
        print('служба не поднялась (%s) — откатил' % st)
        return 1
    print('\n  ✓ применено, мозг перезапущен и жив')
    print('  копия перед правкой: %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
