#!/usr/bin/env python3
"""Перенос переписки WhatsApp в карточку человека.

Зачем: OpenClaw подключён к личному WhatsApp, но архива сообщений у него нет —
он хранит только ключи сессии и видит лишь новые входящие. Старая переписка
живёт на телефоне. Экспорт чата — единственный безопасный способ её забрать:
ничего не переподключаем, сессию не трогаем, наружу не пишем.

Как получить файл: WhatsApp → открыть чат → ⋮ (или имя чата) → «Экспорт чата»
→ «Без медиафайлов» → сохранить .txt.

Запуск:
    python3 build/wa_history.py чат.txt PLP-003816
    python3 build/wa_history.py чат.txt PLP-003816 --dry     # только показать

Ключ вебхука берётся из переменной окружения PLP_WEBHOOK_KEY.
"""
import json, os, re, sys, urllib.request
from datetime import datetime

URL = 'https://proplib.app.n8n.cloud/webhook/simplecore'

# WhatsApp пишет дату по-разному в зависимости от языка и системы
LINE = re.compile(
    r'^\[?(\d{1,2})[./](\d{1,2})[./](\d{2,4})[,.]?\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*'
    r'([APap][Mm])?\]?\s*[-–]?\s*([^:]{1,60}):\s*(.*)$')

SKIP = re.compile(
    r'(Messages and calls are end-to-end encrypted|Сообщения и звонки защищены|'
    r'<Media omitted>|<Медиафайл пропущен>|Вы удалили это сообщение|'
    r'This message was deleted|образ профиля|security code changed)', re.I)


def parse(path, me_hints):
    """Разбирает экспорт в список записей для ленты."""
    out, cur = [], None
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        for raw in f:
            raw = raw.replace('‎', '').rstrip('\n')
            m = LINE.match(raw)
            if not m:
                if cur and raw.strip():          # продолжение многострочного
                    cur['text'] += '\n' + raw.strip()
                continue
            d, mo, y, hh, mm, ss, ampm, who, text = m.groups()
            if SKIP.search(text or ''):
                cur = None
                continue
            y = int(y) + (2000 if len(y) == 2 else 0)
            hh = int(hh)
            if ampm:
                if ampm.lower() == 'pm' and hh != 12: hh += 12
                if ampm.lower() == 'am' and hh == 12: hh = 0
            try:                                  # день и месяц местами — как повезёт
                ts = datetime(y, int(mo), int(d), hh, int(mm), int(ss or 0))
            except ValueError:
                try:
                    ts = datetime(y, int(d), int(mo), hh, int(mm), int(ss or 0))
                except ValueError:
                    continue
            mine = any(h.lower() in who.lower() for h in me_hints)
            cur = {'ts': ts.isoformat() + 'Z',
                   'text': (text or '').strip(),
                   'actor': 'manager' if mine else 'client',
                   'channel': 'wa_personal'}
            out.append(cur)
    return [e for e in out if e['text']]


def send(code, entries, key):
    body = json.dumps({'action': 'client_history', 'code': code,
                       'entries': entries, 'channel': 'wa_personal'}).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={'Content-Type': 'application/json',
                                          'x-plp-key': key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    path, code = args[0], args[1]
    me = os.environ.get('PLP_ME', 'Эльнур,Elnur,PLP,Property Library').split(',')

    entries = parse(path, me)
    if not entries:
        print('Ничего не разобралось. Проверьте, что это экспорт чата WhatsApp.')
        sys.exit(2)

    print(f'Разобрано сообщений: {len(entries)}')
    print(f'Период: {entries[0]["ts"][:10]} — {entries[-1]["ts"][:10]}')
    print(f'От клиента: {sum(1 for e in entries if e["actor"] == "client")}, '
          f'от нас: {sum(1 for e in entries if e["actor"] == "manager")}')
    print('\nПервые три:')
    for e in entries[:3]:
        print(f'  {e["ts"][:16]}  {e["actor"]:8s} {e["text"][:70]}')

    if dry:
        print('\n--dry: ничего не отправлено.')
        return

    key = os.environ.get('PLP_WEBHOOK_KEY', '')
    if not key:
        print('\nНет PLP_WEBHOOK_KEY в окружении.')
        sys.exit(3)

    # отправляем частями, чтобы не упереться в размер запроса
    sent = 0
    for i in range(0, len(entries), 200):
        chunk = entries[i:i + 200]
        r = send(code, chunk, key)
        sent += len(chunk)
        print(f'  отправлено {sent}/{len(entries)}')
    print(f'\nГотово: история {code} дополнена.')


if __name__ == '__main__':
    main()
