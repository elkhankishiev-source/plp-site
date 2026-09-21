#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Один и тот же промпт должен быть побайтово одинаковым. Иначе кэш не работает.

Сверка расхода 21.09.2026 показала: из 92 обращений к мозгу за трое суток 20
шли мимо кэша — с `cache_read=0` и полной перезаписью. Это 581 тысяча токенов
записи, то есть **$5.81 из $10.31**, больше половины счёта за мозг.

Причина нашлась в логе. У роли «Эльнур» постоянный блок промпта имеет ШЕСТЬ
разных отпечатков: jwsafx (200 раз), 1kx8yce (154), 1h9m55q (53), p1g39v (3),
91qnmm (2), nuv4t1 (1). При этом длина у них одинаковая — 53 025 знаков.
Одинаковая длина при разном содержимом означает одно: те же куски, но в другом
порядке.

Разложил блок по частям — гуляет ровно одна:

    h_proto    1 вариант  — протокол стабилен
    h_ident    1 вариант  — личность стабильна
    h_etalon   1 вариант  — эталоны стабильны
    h_lead     1 вариант  — лид стабилен
    h_canon    4 варианта — ВОТ ОНО

Правила канона читаются так:

    /canon_rules?...&order=domain&limit=60

Сортировка только по домену. Внутри одного домена порядок строк Postgres не
гарантирует — он отдаёт их так, как удобно планировщику, и от запроса к запросу
порядок меняется. Правила перемешиваются, текст блока получается другой, отпечаток
другой — и Anthropic берёт с нас полную цену за запись кэша вместо десятой доли
за чтение.

Лечение в одну строку: добавить второй ключ сортировки. `order=domain,rule_key`
даёт строгий и повторяемый порядок при любом числе правил.

Побочная польза: прогрев кэша наконец начнёт попадать в цель. Сейчас он греет
один вариант блока, а живой вызов приходит с другим и всё равно платит.

    python3 vps_brain_canon_order.py            # показать правку
    python3 vps_brain_canon_order.py --apply    # применить и перезапустить мозг
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

БЫЛО = '&select=rule_key,domain,title,content,short&order=domain&limit=60'
СТАЛО = ('&select=rule_key,domain,title,content,short&order=domain,rule_key&limit=60'
         '/* 21.09: без второго ключа Postgres отдавал правила одного домена в '
         'произвольном порядке — постоянный блок промпта каждый раз получался '
         'другим, кэш перезаписывался, и это стоило половины счёта за мозг */')


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'order=domain,rule_key' in src:
        print('правка уже стоит')
        return 0
    n = src.count(БЫЛО)
    if n != 1:
        print('точка правки найдена %d раз — отменяю, чтобы не задеть лишнее' % n)
        return 1
    print('было:  order=domain')
    print('стало: order=domain,rule_key')
    print('\nэффект: постоянный блок промпта перестаёт меняться от запроса к запросу,')
    print('кэш начинает читаться вместо перезаписи (~$5.8 из $10.3 за трое суток)')
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
    print('  проверить через час: в логе prompt-sizes у роли «Эльнур» должен')
    print('  остаться ОДИН h_static, а в ai_usage cache_read перестать быть нулём')
    return 0


if __name__ == '__main__':
    sys.exit(main())
