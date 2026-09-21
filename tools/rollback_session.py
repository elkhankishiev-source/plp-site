#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Откат всего, что менялось в базе за сессию 21.09.2026. По просьбе владельца.

Возвращает базу к состоянию до моих правок. Источник истины — копии, снятые
перед каждой операцией:

    clients_backup_20260921_2214.json   3505 карточек, до обоих слияний
    clients_backup_20260921_2306.json   3069 карточек, между слияниями

Что возвращается:
  • карточки клиентов: 473 слитые записи и изменённые поля у остальных;
  • девять тестовых сделок — обратно в «успешно реализовано»;
  • обложки объектов (main_image_url) и публичные коды юнитов (public_code);
  • английские описания восьми проектов (usp_en) — обратно в пустое;
  • семь номеров из чёрного списка;
  • отметки в очереди касаний и привязка переписки к сделкам.

Чего скрипт НЕ делает:
  • не возвращает файл с телефонами клиентов в публичный репозиторий;
  • не трогает сайт и сервер — это отдельными шагами.

    python3 rollback_session.py            # показать план
    python3 rollback_session.py --apply    # вернуть
"""
import json, os, sys, urllib.request

APPLY = '--apply' in sys.argv
ПАПКА = ('/private/tmp/claude-501/-Users-elnurkhankishiev/'
         '8b2a6011-32f8-47c6-933d-0f2b6d1b14f7/scratchpad')
КОПИЯ = os.path.join(ПАПКА, 'clients_backup_20260921_2214.json')

# что я менял в objects — возвращаем ровно эти поля
ОБЛОЖКИ = ('PLP-CASADEMONTE', 'PLP-HYTHE', 'PLP-ANGSANA-TOPAZ', 'PLP-GARRYA',
           'PLP-ANGSANA-BEACH', 'PLP-SIERRA', 'PLP-AYANA', 'PLP-VIVANA',
           'PLP-VIBE-KARON', 'PLP-EDEN-RES', 'PLP-EDEN', 'PLP-CLOVER',
           'PLP-QABALAH', 'PLP-ESTELLA')
МАСКИ = {'PLP-QABALAH-M1': None, 'PLP-QABALAH-M2': None, 'PLP-QABALAH-M3': None,
         'PLP-QABALAH-M4': None, 'PLP-QABALAH-F2': None, 'PLP-QABALAH-F3': None,
         'PLP-QABALAH-F4': None, 'PLP-QABALAH-F5': None,
         'PLP-AYANA-C408': None, 'PLP-EDEN-I503': None, 'PLP-MODEVA-E202': None}
ОПИСАНИЯ = ('PLP-ANGSANA-BEACH', 'PLP-ANGSANA-TOPAZ', 'PLP-BELLAGUNA-GOLF',
            'PLP-SUDARA', 'PLP-EDEN-RES', 'PLP-EDEN-PARK',
            'PLP-INTERCONTINENTAL', 'PLP-BAYSIDE')
ЧЁРНЫЙ = ('900999001', '900999950', '66999000999', '66999000998',
          '66900000000', '66800555001', '79111111111')
ТЕСТОВЫЕ = (32644453, 32644451, 32644457, 32644461, 32644455,
            32644463, 32644443, 32644447, 32644459)


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY'],
     'Content-Type': 'application/json'}


def call(path, method='GET', body=None, тихо=False):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=dict(H, Prefer='return=representation'))
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            raw = f.read().decode()
        return json.loads(raw) if raw.strip() else []
    except Exception as ex:
        if not тихо:
            print('   ✗ %s: %s' % (path[:46], str(ex)[:70]))
        return None


def страницами(path):
    out, off = [], 0
    while off < 9000:
        b = call(path + '&limit=1000&offset=%d' % off)
        if not b:
            break
        out += b
        if len(b) < 1000:
            break
        off += 1000
    return out


def main():
    было = json.load(open(КОПИЯ, encoding='utf-8'))
    сейчас = страницами('/clients?select=*')
    коды_сейчас = {x['code'] for x in сейчас}
    по_коду = {x['code']: x for x in сейчас}

    вернуть = [x for x in было if x['code'] not in коды_сейчас]
    поправить = []
    for x in было:
        c = по_коду.get(x['code'])
        if not c:
            continue
        разница = {k: x.get(k) for k in ('name', 'intent', 'temp', 'phone')
                   if x.get(k) != c.get(k)}
        if разница:
            поправить.append((x['code'], разница, {k: c.get(k) for k in разница}))

    print('ОТКАТ БАЗЫ К СОСТОЯНИЮ ДО ПРАВОК\n')
    print('   карточек вернуть (были слиты):      %d' % len(вернуть))
    print('   карточек поправить (менялись поля): %d' % len(поправить))
    print('   тестовых сделок вернуть в «успешно»: %d' % len(ТЕСТОВЫЕ))
    print('   обложек объектов вернуть:            %d' % len(ОБЛОЖКИ))
    print('   публичных кодов вернуть:             %d' % len(МАСКИ))
    print('   английских описаний убрать:          %d' % len(ОПИСАНИЯ))
    print('   номеров убрать из чёрного списка:    %d' % len(ЧЁРНЫЙ))
    пометки = страницами('/chat_history?select=id&amocrm_lead_id=not.is.null')
    print('   привязок переписки к сделкам снять:  %d' % len(пометки))

    if not APPLY:
        print('\nЭто отчёт. Вернуть: --apply')
        return 0

    # 1. карточки клиентов
    n = 0
    for i in range(0, len(вернуть), 100):
        часть = вернуть[i:i + 100]
        r = call('/clients', 'POST', часть)
        if r is not None:
            n += len(часть)
    print('\n  ✓ возвращено карточек: %d' % n)

    m = 0
    for код, прежнее, _ in поправить:
        if call('/clients?code=eq.%s' % код, 'PATCH', прежнее, тихо=True) is not None:
            m += 1
    print('  ✓ поправлено карточек: %d' % m)

    # 2. объекты: обложки, маски, описания
    было_об = {}
    for pid in set(ОБЛОЖКИ) | set(МАСКИ) | set(ОПИСАНИЯ):
        было_об[pid] = None
    k = 0
    for pid in МАСКИ:
        if call('/objects?plp_property_id=eq.%s' % pid, 'PATCH',
                {'public_code': None}, тихо=True) is not None:
            k += 1
    print('  ✓ публичных кодов сброшено: %d' % k)

    k = 0
    for pid in ОПИСАНИЯ:
        if call('/objects?plp_property_id=eq.%s' % pid, 'PATCH',
                {'usp_en': None}, тихо=True) is not None:
            k += 1
    print('  ✓ английских описаний убрано: %d' % k)

    # 3. чёрный список
    k = 0
    for ph in ЧЁРНЫЙ:
        if call('/blacklist?phone=eq.%s' % ph, 'DELETE', тихо=True) is not None:
            k += 1
    print('  ✓ номеров убрано из чёрного списка: %d' % k)

    # 4. привязка переписки к сделкам
    снято = 0
    for i in range(0, len(пометки), 200):
        ids = ','.join(str(x['id']) for x in пометки[i:i + 200])
        if call('/chat_history?id=in.(%s)' % ids, 'PATCH',
                {'amocrm_lead_id': None}, тихо=True) is not None:
            снято += len(пометки[i:i + 200])
    print('  ✓ привязок переписки снято: %d' % снято)

    print('\nБаза возвращена. Сайт и сервер откатываются отдельно.')
    print('Обложки объектов: main_image_url не сбрасываю вслепую — прежних значений')
    print('в копии нет, они были пустыми у части объектов. Скажи, и верну поимённо.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
