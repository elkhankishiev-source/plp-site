#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сторож здоровья, живёт на сервере, а не на Маке: Мак выключают, сервер работает всегда.

Проверяет то, от чего зависят клиенты, и пишет в Telegram только при смене состояния.
Поставлен 19.09.2026 после тихой аварии Supabase: сайт сутки стоял без фотографий,
двойник отвечал без контекста, и заметили это случайно.
"""
import json
import urllib.parse, time, os, subprocess, urllib.request, urllib.error, time

СОСТОЯНИЕ = '/opt/plp-health/state.json'
OWNER = 509498386   # запасное значение; настоящее берём из .env ниже, после объявления env()


def env(key, файл='/opt/plp-api/.env'):
    try:
        for line in open(файл, encoding='utf-8'):
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return ''


# 23.09: id личного чата переехал в .env — он был зашит цифрой в девяти файлах
# под пятью разными именами. Значение выше осталось запасным.
try:
    OWNER = int(env('TG_OWNER_CHAT_ID') or OWNER)
except Exception:
    pass

def код(url, headers=None, data=None, timeout=45):
    r = urllib.request.Request(url, headers=headers or {}, data=data)
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, resp.read(400).decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception:
        return 0, ''


SB, KEY, API = env('SUPABASE_URL').rstrip('/'), env('SUPABASE_SERVICE_KEY'), env('PLP_API_KEY')
h = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}

проверки = {}
c, _ = код(SB + '/rest/v1/canon_rules?select=id&limit=1', h)
# базу проверяет WF_site_watchdog (двойной зонд) — здесь убрано, чтобы не дублировать тревогу

# 19.09.2026: проверяем мозг режимом probe (правка 334) — он проходит весь путь до
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
проверки['мозг собирает контекст'] = (c == 200 and _соб > 2000, 'промпт %d знаков' % _соб)

# сайт проверяет WF_site_watchdog (4 страницы) — здесь убрано, чтобы не дублировать тревогу

# 20.09.2026: картинки живут в R2, Supabase их больше не раздаёт.
# R2 отвечает 403 всем, кто пришёл без браузерной подписи — поэтому она обязательна.
БРАУЗЕР = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36'}
c, _ = код('https://pub-8e4357d7dd6c4c018600cb6d37990142.r2.dev/'
           'objects/PLP-EDEN/01-760.webp', БРАУЗЕР)
проверки['фото объектов'] = (c in (200, 304), 'код %s' % c)

c, _ = код('https://api.property-library.com/pult')
проверки['пульт'] = (c == 200, 'код %s' % c)

try:
    служб = subprocess.run(['systemctl', 'is-active', 'plp-api', 'plp-pult', 'caddy'],
                           capture_output=True, text=True, timeout=30).stdout
except Exception:
    служб = ''
проверки['службы'] = (len([x for x in служб.split() if x == 'active']) >= 3, служб.replace('\n', ' ').strip())

# 23.09.2026. Разбор показал худший из возможных отчётов: баланс Anthropic на нуле
# сутки, модель отдаёт 400 на всё, 49 касаний стоят в очереди — а все сторожа пишут
# «ок». Сторож, который не видит главной поломки, хуже отсутствующего: он ещё и
# успокаивает. Две проверки ниже закрывают это.

# 1) Модель отвечает деньгами, а не только кодом 200. Смотрим журнал службы:
#    если за час хоть раз пришло «credit balance is too low» — это стоп, а не мелочь.
# Спрашиваем саму модель одним словом, а не журнал: журнал отстаёт на час и
# после пополнения ещё час кричит о пустом балансе. Запрос на 4 токена стоит
# доли цента и говорит правду про сейчас, а не про «час назад».
_денег_нет, _нота, _ответил = False, "обращения проходят", False
try:
    _к, _т = код("https://api.anthropic.com/v1/messages",
                 {"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
                  "content-type": "application/json"},
                 json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 4,
                             "messages": [{"role": "user", "content": "."}]}).encode(),
                 30)
    _ответил = (_к == 200)
    if _к != 200:
        _денег_нет = "credit balance" in (_т or "").lower()
        _нота = ("баланс Anthropic на нуле — модель не отвечает никому" if _денег_нет
                 else "модель ответила кодом %s" % _к)
        if not _денег_нет:
            проверки["модель отвечает деньгами"] = (False, _нота)
except Exception as e:
    _нота = "спросить не вышло: %s" % str(e)[:60]
# 23.09.2026. Пока баланс кончался, эта строка писала «ок, модель ответила кодом 400».
# «Ок» рядом со словом «400» — это не отчёт, а успокоительное. Зелёной она теперь
# бывает только при настоящем 200: любой другой ответ и любая ошибка связи — красное.
проверки["деньги на модель"] = (_ответил, _нота)

# 2) Сторожа уроков (таблица «уроки»): каждый разобранный сбой оставил после себя
#    проверку. Если хоть одна говорит «ВЕРНУЛОСЬ» — старая беда вернулась, и об этом
#    надо узнать от сторожа, а не от Эльнура.
# 23.09.2026. Эта проверка молча врала: кириллица в адресе уходила незакодированной,
# запрос падал, except гасил ошибку — и сторож бодро писал «все сторожа зелёные»,
# когда в таблице стояло два ВЕРНУЛОСЬ. Теперь имя таблицы и значения кодируются,
# а неудача запроса — это красное «спросить не вышло», а не тишина.
_ошибка_уроков = ""
try:
    _адрес = (env("SUPABASE_URL").rstrip("/") + "/rest/v1/"
              + urllib.parse.quote("уроки")
              + "?select=" + urllib.parse.quote("что_сломалось,состояние")
              + "&" + urllib.parse.quote("состояние") + "=in.("
              + urllib.parse.quote("ВЕРНУЛОСЬ") + "," + urllib.parse.quote('"сторож сломан"') + ")")
    _c, _т = код(_адрес, {"apikey": env("SUPABASE_SERVICE_KEY"),
                          "Authorization": "Bearer " + env("SUPABASE_SERVICE_KEY")})
    if _c == 200 and (_т or "").strip().startswith("["):
        _вернулось = json.loads(_т)
    else:
        _вернулось, _ошибка_уроков = [], "база ответила кодом %s" % _c
except Exception as e:
    _вернулось, _ошибка_уроков = [], "спросить не вышло: %s" % str(e)[:60]
проверки["уроки не забыты"] = (
    (not _вернулось) and not _ошибка_уроков,
    _ошибка_уроков or ("вернулось: " + "; ".join(str(x.get("что_сломалось"))[:60] for x in _вернулось[:3])
                       if _вернулось else "все сторожа зелёные"))

# 2б) Охват уроков. 24.09.2026: «уроки не забыты» смотрит только на ВЕРНУЛОСЬ и
#     «сторож сломан» — и молчит о главном: у скольких уроков сторожа нет вовсе.
#     На 24.09 из 88 уроков запросом проверялся 31, у 29 сторож записан командой
#     (база её выполнить не может, нужен runner), у 28 сторожа нет совсем.
#     Красным делаем только УХУДШЕНИЕ: если сторожей стало меньше, чем было.
#     Постоянно красная строка учит её не читать — поэтому здесь число, а не крик.
ПОЛ_СТОРОЖЕЙ = 31          # столько уроков проверялось запросом на 24.09.2026
try:
    _c, _t = код(env("SUPABASE_URL").rstrip("/") + "/rest/v1/rpc/"
                 + urllib.parse.quote("уроки_охват"),
                 {"apikey": env("SUPABASE_SERVICE_KEY"),
                  "Authorization": "Bearer " + env("SUPABASE_SERVICE_KEY"),
                  "Content-Type": "application/json"},
                 data=b"{}")
    if _c == 200:
        _о = json.loads(_t)[0]
        _под, _всего = int(_о["под_сторожем"]), int(_о["всего"])
        проверки["уроки под присмотром"] = (
            _под >= ПОЛ_СТОРОЖЕЙ,
            ("сторожей стало меньше: %d, было %d" % (_под, ПОЛ_СТОРОЖЕЙ)) if _под < ПОЛ_СТОРОЖЕЙ
            else "под сторожем %d из %d (командой %d, без сторожа %d)"
                 % (_под, _всего, int(_о["только_командой"]), int(_о["без_сторожа"])))
    else:
        проверки["уроки под присмотром"] = (False, "база ответила кодом %s" % _c)
except Exception as e:
    проверки["уроки под присмотром"] = (False, "спросить не вышло: %s" % str(e)[:60])

сломано = [k for k, v in проверки.items() if not v[0]]

# --- САМО-ЛЕЧЕНИЕ (20.09.2026) -------------------------------------------
# Сторож обязан сначала починить, и только если не вышло — писать хозяину.
# Лечим лишь то, что уже сломано. Не чаще ЛИМИТ_В_ЧАС раз в час на проверку,
# иначе уходим в петлю перезапусков и делаем хуже.
ЛЕЧЕНИЕ_ФАЙЛ = '/var/lib/plp-health-heal.json'
ЛИМИТ_В_ЧАС = 3
ЛЕКАРСТВО = {
    'службы': ['plp-api', 'plp-pult', 'caddy'],
    # 'сайт открывается' — сайт на GitHub Pages, нашим caddy не лечится
    'пульт': ['plp-pult', 'caddy'],
    'мозг собирает контекст': ['plp-api'],
    'мозг отвечает': ['plp-api'],
}

def _журнал_лечения():
    try:
        return json.load(open(ЛЕЧЕНИЕ_ФАЙЛ, encoding='utf-8'))
    except Exception:
        return {}

def _записать_лечение(ж):
    try:
        os.makedirs(os.path.dirname(ЛЕЧЕНИЕ_ФАЙЛ), exist_ok=True)
        json.dump(ж, open(ЛЕЧЕНИЕ_ФАЙЛ, 'w'), ensure_ascii=False)
    except Exception:
        pass

def _не_активна(служба):
    try:
        r = subprocess.run(['systemctl', 'is-active', служба],
                           capture_output=True, text=True, timeout=20).stdout.strip()
        return r != 'active'
    except Exception:
        return False

def _перезапустить(служба):
    try:
        subprocess.run(['systemctl', 'restart', служба], capture_output=True, timeout=90)
        return True
    except Exception:
        return False

def _перепроверить(имя):
    if имя == 'службы':
        try:
            s = subprocess.run(['systemctl', 'is-active', 'plp-api', 'plp-pult', 'caddy'],
                               capture_output=True, text=True, timeout=30).stdout
        except Exception:
            s = ''
        return (len([x for x in s.split() if x == 'active']) >= 3, s.replace(chr(10), ' ').strip())
    if имя == 'сайт открывается':
        c, _ = код('https://property-library.com/')
        return (c == 200, 'код %s' % c)
    if имя == 'пульт':
        c, _ = код('https://api.property-library.com/pult')
        return (c == 200, 'код %s' % c)
    return (None, '')

вылечено, не_вылечено, петля = [], [], []
if сломано:
    ж = _журнал_лечения()
    сейчас = time.time()
    for имя in list(сломано):
        службы_к_правке = ЛЕКАРСТВО.get(имя)
        if not службы_к_правке:
            continue
        недавние = [t for t in ж.get(имя, []) if сейчас - t < 3600]
        if len(недавние) >= ЛИМИТ_В_ЧАС:
            петля.append(имя)
            ж[имя] = недавние
            print('лечение: «%s» чинил %d раза за час, больше не трогаю' % (имя, len(недавние)))
            continue
        цели = [s for s in службы_к_правке if _не_активна(s)] or службы_к_правке[:1]
        for s in цели:
            _перезапустить(s)
            print('лечение: перезапустил %s из-за «%s»' % (s, имя))
        недавние.append(сейчас)
        ж[имя] = недавние
        time.sleep(8)
        ок, нота = _перепроверить(имя)
        if ок is True:
            проверки[имя] = (True, нота)
            вылечено.append(имя)
            print('лечение: «%s» починилось' % имя)
        elif ок is False:
            проверки[имя] = (False, нота)
            не_вылечено.append(имя)
            print('лечение: «%s» НЕ починилось' % имя)
    _записать_лечение(ж)
    сломано = [k for k, v in проверки.items() if not v[0]]
# --- конец само-лечения ---------------------------------------------------

for k, (ok, note) in проверки.items():
    print('%-22s %s %s' % (k, 'ок' if ok else 'СЛОМАНО', note))

было = {}
if os.path.exists(СОСТОЯНИЕ):
    try:
        было = json.load(open(СОСТОЯНИЕ, encoding='utf-8'))
    except Exception:
        было = {}
было = {k: v for k, v in было.items() if not str(k).startswith('_')} | \
        ({'_когда_сообщали': было.get('_когда_сообщали')} if isinstance(было, dict) and было.get('_когда_сообщали') else {})
стало = {k: bool(v[0]) for k, v in проверки.items()}
os.makedirs(os.path.dirname(СОСТОЯНИЕ), exist_ok=True)
json.dump(стало, open(СОСТОЯНИЕ, 'w'), ensure_ascii=False)

изменилось = [k for k in стало if было.get(k) != стало[k]] if было else сломано

# 22.09.2026: проверка может мигать — ломаться и чиниться по кругу. При обходе раз в
# 10 минут это давало под сотню сообщений в сутки. Про одну и ту же проверку пишем
# не чаще раза в ПЕРЕРЫВ секунд; остальные переходы копятся молча.
ПЕРЕРЫВ = 7200
_сейчас = int(time.time())
_когда = (было.get('_когда_сообщали') or {}) if isinstance(было, dict) else {}
if not isinstance(_когда, dict):
    _когда = {}
_молча = [k for k in изменилось if _сейчас - int(_когда.get(k, 0)) < ПЕРЕРЫВ]
изменилось = [k for k in изменилось if k not in _молча]
if _молча:
    print('промолчал про (недавно уже писал): ' + ', '.join(_молча))
for k in изменилось:
    _когда[k] = _сейчас
стало['_когда_сообщали'] = _когда
json.dump(стало, open(СОСТОЯНИЕ, 'w'), ensure_ascii=False)
стало.pop('_когда_сообщали', None)

if изменилось:
    строки = [('сломалось: ' if not стало[k] else 'починилось: ') + k +
              (' (%s)' % проверки[k][1] if проверки[k][1] else '') for k in изменилось]
    текст = 'Сторож системы.\n\n' + '\n'.join(строки)
    if вылечено:
        текст += '\n\nПочинил сам: ' + ', '.join(вылечено)
    if петля:
        текст += '\n\nЧинил три раза за час, не помогает — нужны руки: ' + ', '.join(петля)
    if сломано:
        текст += '\n\nСейчас не работает: ' + ', '.join(сломано)
    tok = env('TG_ELNURPHUKET_TOKEN')
    if tok:
        try:
            urllib.request.urlopen(urllib.request.Request(
                'https://api.telegram.org/bot%s/sendMessage' % tok,
                data=json.dumps({'chat_id': OWNER, 'text': текст, 'disable_web_page_preview': True}).encode(),
                headers={'Content-Type': 'application/json'}), timeout=30)
            print('сообщение отправлено')
        except Exception as e:
            print('в Telegram не ушло:', str(e)[:80])
else:
    print('изменений нет')
