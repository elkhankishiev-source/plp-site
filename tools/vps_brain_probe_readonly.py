#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 338: проверка живости ничего не создаёт в базе. Она проверяет, а не работает.

Найдено 19.09.2026 сразу после правки 337. Проверяя, что связка каналов пополняется, я
увидел в журнале «к человеку PLP-004523 добавлен канал ig» — при том что номер
66900000777 давно принадлежит карточке PLP-001547.

Разбор: `client_resolve` заводит НОВУЮ карточку, если приходит незнакомая пара
«канал + ключ». Мой probe передавал номер телефона, но с `source: telegram` и
`source: instagram` — для системы это новый адрес в новом канале, и она честно заводила
человека. За сегодня так появились пустые PLP-004521, 004522, 004523 и другие: без имени,
без телефона, просто мусор.

Сторож живости ходит каждые десять минут и делает ровно то же самое.

Правка: в режиме `probe` блок опознания клиента (client_resolve, запись в client_timeline
и связка 337) пропускается целиком. Проверка остаётся честной — контекст, каталог, каноны
и промпт собираются как обычно, а база остаётся нетронутой.

    python3 vps_brain_probe_readonly.py            # показать, что изменится
    python3 vps_brain_probe_readonly.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

OLD = """/* ЕДИНЫЙ ID КЛИЕНТА: одно касание = одна ячейка PLP-xxxxxx (client_resolve) */
var client=null;var _chan='';
try{"""

NEW = """/* ЕДИНЫЙ ID КЛИЕНТА: одно касание = одна ячейка PLP-xxxxxx (client_resolve) */
var client=null;var _chan='';
/* 19.09.2026 правка 338: проверка живости (probe) ничего не создаёт. Без этого
   сторож каждые десять минут заводил пустые карточки, потому что client_resolve
   видит незнакомую пару «канал + ключ» и честно создаёт человека.
   Разбор — в tools/vps_brain_probe_readonly.py */
if(!(p && p.probe===true))
try{"""


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 338' in src:
        print('правка 338 уже стоит')
        return 0
    if src.count(OLD) != 1:
        print('якорь найден %d раз — отменяю' % src.count(OLD))
        return 1
    if not APPLY:
        print('будет изменено: в режиме probe опознание клиента и запись связок пропускаются')
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
    print('  ✓ probe больше ничего не создаёт')
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
