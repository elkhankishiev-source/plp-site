#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож живости переходит на бесплатную проверку мозга.

Продолжение правки 334. Сам мозг уже умеет отвечать на `probe: true` без вызова модели,
осталось переключить того, кто его дёргает: `/opt/plp-health.py`, крон каждые 10 минут.

Было: настоящее сообщение «здравствуйте» и покупка полного ответа продавца — около
десяти центов за заход, 144 захода в сутки.
Станет: тот же путь до сборки промпта, ответ `{"ok":true,"prompt_chars":59510,…}`, ноль.

Проверка при этом становится СТРОЖЕ, а не слабее: раньше признаком здоровья было наличие
слова reply в ответе, теперь — что промпт реально собрался и каноны подгрузились. Пустой
или обрезанный контекст сторож теперь заметит, а раньше не замечал.

    python3 vps_health_probe.py            # показать, что изменится
    python3 vps_health_probe.py --apply    # применить и проверить прогоном
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-health.py'
APPLY = '--apply' in sys.argv

OLD = """c, тело = код('http://127.0.0.1:8090/brain',
              {'Content-Type': 'application/json', 'x-plp-key': API},
              json.dumps({'text': 'здравствуйте', 'phone': '66999000999', 'source': 'telegram'}).encode())
проверки['мозг отвечает'] = (c == 200 and 'reply' in тело, 'код %s' % c)"""

NEW = """# 19.09.2026: проверяем мозг режимом probe (правка 334) — он проходит весь путь до
# сборки промпта и НЕ зовёт модель. Прежняя проверка покупала готовый ответ продавца
# каждые десять минут: около десяти центов за заход, больше 400 долларов в месяц.
c, тело = код('http://127.0.0.1:8090/brain',
              {'Content-Type': 'application/json', 'x-plp-key': API},
              json.dumps({'probe': True, 'text': 'проверка живости',
                          'phone': '66999000999', 'source': 'telegram'}).encode())
_соб = 0
try:
    _соб = int(json.loads(тело).get('prompt_chars') or 0)
except Exception:
    pass
проверки['мозг собирает контекст'] = (c == 200 and _соб > 2000, 'промпт %d знаков' % _соб)"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 334' in src:
        print('уже переключено')
        return 0
    if src.count(OLD) != 1:
        print('проверка мозга найдена %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: сторож зовёт мозг в режиме probe, без оплаты ответа модели')
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    open(SRC, 'w', encoding='utf-8').write(src.replace(OLD, NEW, 1))
    chk = subprocess.run(['python3', '-c', 'import ast;ast.parse(open("%s",encoding="utf-8").read())' % SRC],
                         capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:400])
        return 1
    run = subprocess.run(['python3', SRC], capture_output=True, text=True, timeout=180)
    print(run.stdout.strip()[-600:] or run.stderr.strip()[-400:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
