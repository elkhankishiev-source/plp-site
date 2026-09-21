#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снос тестовых сделок в amoCRM. ВНИМАНИЕ: API amoCRM удалять сделки НЕ даёт.

ПРОВЕРЕНО 19.09.2026 на всех 56 помеченных сделках: после DELETE все 56 остались живы
(живая сделка отвечает на PATCH своим id, удалённая — нет). Узел падает с
«Cannot read properties of undefined (reading \'data\')» — amoCRM отвечает без тела,
но сделку не удаляет. Ни DELETE /leads/{id}, ни DELETE /leads с массивом, ни
POST /leads/delete не работают.

Моя ошибка, из-за которой я сперва отчитался об успехе: путь ep передавался с префиксом
«/api/v4», который сценарий подставляет сам, и amoCRM возвращал 404 «Cannot DELETE …»,
а скрипт искал в ответе слово «error» и не находил. Теперь успех проверяется фактом.

Что остаётся: удалять в интерфейсе amoCRM (фильтр по названию «УДАЛИТЬ» → выделить всё
→ удалить), либо увести их в «Закрыто и не реализовано» через amo_park_tests.py.

Эльнур 19.09.2026: «го по сделкам» — снести 56 тестовых сделок, помеченных [УДАЛИТЬ].

Отбор жёсткий, чтобы не задеть живое:
  • в названии есть «УДАЛИТЬ» или «ДУБЛЬ — удалить»;
  • сделка не удалена ранее;
  • цена ровно 0 — у живой сделки почти всегда есть сумма, это последний предохранитель.
Всё, что не проходит хотя бы одно условие, остаётся и печатается отдельно.

Удаление необратимо, поэтому перед сносом список сохраняется в файл: если что-то потом
понадобится восстановить руками, будет видно, что именно снесли.

Удаляет через WF_amo_write (вебхук /amo-write, метод DELETE) — тот самый сценарий, где
DELETE был дописан и опубликован 19.09.

    python3 amo_delete_tests.py            # показать список
    python3 amo_delete_tests.py --apply    # снести
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime

APPLY = '--apply' in sys.argv
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'amo_deleted_%s.json' % datetime.now().strftime('%Y%m%d_%H%M'))
MARKS = ('УДАЛИТЬ', 'удалить в UI')


def env():
    out = {}
    for ln in open(os.path.expanduser('~/.plp_site_supabase.env'), encoding='utf-8'):
        if '=' in ln and not ln.strip().startswith('#'):
            k, v = ln.strip().split('=', 1)
            out[k] = v.strip().strip('"\'')
    return out


E = env()
BASE = E['SUPABASE_URL'].rstrip('/') + '/rest/v1'
H = {'apikey': E['SUPABASE_SERVICE_KEY'], 'Authorization': 'Bearer ' + E['SUPABASE_SERVICE_KEY']}


def sb(path):
    r = urllib.request.Request(BASE + path, headers=H)
    with urllib.request.urlopen(r, timeout=90) as f:
        return json.loads(f.read().decode() or '[]')


def amo_call(method, ep, payload, key):
    """Путь ep идёт БЕЗ префикса /api/v4: сценарий подставляет его сам.

    На этом я и обжёгся: слал '/api/v4/leads/123', получал 404 «Cannot DELETE …»
    и засчитывал как успех, потому что проверял наличие слова 'error' в ответе.
    Теперь успех проверяется фактом: после удаления PATCH по той же сделке обязан
    вернуть 404. Живая сделка на PATCH отвечает своим id."""
    body = json.dumps({'m': method, 'ep': ep, 'payload': payload}).encode()
    r = urllib.request.Request('https://hub.property-library.com/webhook/amo-write',
                               data=body, method='POST',
                               headers={'Content-Type': 'application/json', 'x-plp-key': key})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return f.read().decode()[:200]
    except Exception as e:
        return 'исключение: ' + str(e)[:120]


def жива_ли(lead_id, key):
    """Единственная честная проверка: живая сделка отвечает на PATCH своим id."""
    res = amo_call('PATCH', 'leads/%d' % lead_id, {'price': 0}, key)
    return ('"id"' in res)


def main():
    rows = []
    for mark in MARKS:
        rows += sb('/crm_leads?name=ilike.' + urllib.parse.quote('*%s*' % mark)
                   + '&is_deleted=is.false&select=id,name,price,status_id,pipeline_id&limit=300')
    seen, uniq = set(), []
    for r in rows:
        if r['id'] in seen:
            continue
        seen.add(r['id'])
        uniq.append(r)

    сносим = [r for r in uniq if not r.get('price')]
    оставляем = [r for r in uniq if r.get('price')]
    print('помечено к удалению: %d' % len(uniq))
    print('пойдут под снос (цена 0): %d' % len(сносим))
    if оставляем:
        print('\nНЕ трогаю — у них есть сумма, проверь глазами:')
        for r in оставляем:
            print('   %s  %s  цена %s' % (r['id'], str(r['name'])[:50], r['price']))
    print()
    for r in сносим[:10]:
        print('   %s  %s' % (r['id'], str(r['name'])[:60]))
    if len(сносим) > 10:
        print('   … и ещё %d' % (len(сносим) - 10))

    if not APPLY:
        print('\nЭто отчёт. Снести: --apply')
        return 0

    json.dump(сносим, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nсписок сохранён: %s' % OUT)
    key = os.environ.get('PLP_WEBHOOK_KEY', '')
    if not key:
        print('нет ключа PLP_WEBHOOK_KEY в окружении — снос отменён')
        return 1
    for r in сносим:
        amo_call('DELETE', 'leads/%d' % r['id'], {}, key)
    # считаем не ответы, а факт: кто из них ещё отвечает на запрос
    живых = [r for r in сносим if жива_ли(r['id'], key)]
    print('\nснесено: %d, осталось живых: %d' % (len(сносим) - len(живых), len(живых)))
    for r in живых[:10]:
        print('   уцелела: %s %s' % (r['id'], str(r['name'])[:50]))
    return 0 if not живых else 1


if __name__ == '__main__':
    sys.exit(main())
