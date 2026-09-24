#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Публикация правок n8n: чтобы исправленное действительно исполнялось.

Эльнур 18.09.2026 про непубликуемые правки: «чини, как ты вообще такое допустил».

Что происходит. n8n 2.38 исполняет не то, что лежит в workflow_entity.nodes — это
черновик. Исполняется ОПУБЛИКОВАННАЯ версия: строка workflow_history, на которую
смотрит workflow_entity."activeVersionId". Правки через SQL и через публичный API
меняют только черновик, поэтому «UPDATE 1» был, а поведение оставалось старым.

Сверка это подтвердила ровно: из 70 активных сценариев черновик расходится с живой
версией у восьми — и это те же восемь, куда я вносил правки:

  WF_wa_wazzup       правка 329: старая реплика из истории Wazzup не считается свежей
  WF_validator_PROD  разводка уведомлений по релевантности
  WF_touch_send      отправка утверждённых касаний
  WF_freshness       сверка цен и наличия уходит в отдел продаж, не в тех-чат
  WF_site_lead       заявка в обход сервера уходит в тех-чат, не в отдел продаж
  WF_ig_meta         разговор с покупателем уходит в отдел продаж
  WF_meeting         встречи
  WF_amo_write       запись в amoCRM

Что делает скрипт. Переносит черновик в ту самую строку workflow_history, на которую
уже смотрит activeVersionId. Новых версий не плодит, номер версии не трогает: меняется
только содержимое живой версии. Перед этим складывает копию в таблицу
workflow_history_bak_<дата>, из неё откат делается одной командой.

    python3 n8n_publish.py             # показать расхождения
    python3 n8n_publish.py --apply     # опубликовать и перезапустить n8n
    python3 n8n_publish.py --rollback workflow_history_bak_20260919_1500
"""
import datetime, difflib, json, re, subprocess, sys

KEY = '/Users/elnurkhankishiev/.ssh/plp_vps'
VPS = open('/Users/elnurkhankishiev/.plp_vps_ip').read().strip()
APPLY = '--apply' in sys.argv
ROLLBACK = sys.argv[sys.argv.index('--rollback') + 1] if '--rollback' in sys.argv else None

DIFF_WHERE = ('from workflow_entity w join workflow_history h on h."versionId"=w."activeVersionId" '
              'where w.active=true and h.nodes::text <> w.nodes::text')


def psql(sql):
    r = subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                        'docker exec -i n8n-postgres-1 psql -U n8n -t -A -f /dev/stdin'],
                       input=sql, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:400])
    return r.stdout.strip()


def diffs():
    out = psql('select w.name, length(w.nodes::text), length(h.nodes::text) ' + DIFF_WHERE + ' order by w.name;')
    # 23.09.2026. psql -A разделяет колонки чёрточкой, и она же стоит В ИМЕНИ
    # сценария: «PLP — 5 @plp_assist_bot v2 | ИИ-Офис команды». split рвал строку
    # на четыре куска и падал с too many values to unpack — инструмент публикации
    # не работал вовсе, пока имя с чёрточкой попадало в выборку.
    # Режем С КОНЦА ровно два раза: имя первое, за ним две длины.
    return [ln.rsplit('|', 2) for ln in out.splitlines() if ln.strip()]


ОПАСНОЕ = [
    (r'sslip\.io', 'технический адрес sslip.io вместо домена'),
    (r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'голый IP вместо домена'),
    (r'https?://(127\.0\.0\.1|localhost)', 'локальный адрес — снаружи не отвечает'),
]


def тела(name):
    """Черновик и живая версия одного сценария, как текст."""
    sql = ("select w.nodes::text from workflow_entity w where w.name = $n$%s$n$;" % name)
    черновик = psql(sql)
    живая = psql("select h.nodes::text from workflow_entity w "
                 "join workflow_history h on h.\"versionId\"=w.\"activeVersionId\" "
                 "where w.name = $n$%s$n$;" % name)
    return черновик, живая


def чем_отличается(name):
    """Что именно разошлось. Инструмент до 24.09 печатал только ДЛИНЫ — и по ним
    нельзя понять, какая сторона правильная. У WF_offer_page живая версия ходила
    на домен, а черновик — на технический адрес sslip.io: «опубликовать» означало
    бы сломать ссылку на оффер клиенту. Поэтому показываем значения."""
    try:
        ч, ж = тела(name)
        а = json.dumps(json.loads(ж), ensure_ascii=False, indent=1, sort_keys=True).split('\n')
        б = json.dumps(json.loads(ч), ensure_ascii=False, indent=1, sort_keys=True).split('\n')
    except Exception as e:
        return ['   не смог разобрать: %s' % str(e)[:90]], ч if 'ч' in dir() else '', ''
    строки = []
    for x in difflib.unified_diff(а, б, lineterm='', n=0):
        if x[:3] in ('+++', '---') or x[:2] == '@@':
            continue
        if x[:1] == '-':
            строки.append('   живая:    ' + x[1:].strip()[:150])
        elif x[:1] == '+':
            строки.append('   черновик: ' + x[1:].strip()[:150])
    return строки, ч, ж


def опасное_в_черновике(ч, ж):
    """Черновик тянет назад то, от чего мы уже ушли?"""
    беды = []
    for рег, что in ОПАСНОЕ:
        if re.search(рег, ч or '') and not re.search(рег, ж or ''):
            беды.append(что)
    return беды


def main():
    if ROLLBACK:
        if not ROLLBACK.startswith('workflow_history_bak_'):
            print('имя копии должно начинаться с workflow_history_bak_')
            return 1
        n = psql('update workflow_history h set nodes=b.nodes, connections=b.connections, '
                 '"updatedAt"=now() from %s b where b."versionId"=h."versionId"; ' % ROLLBACK)
        print('откат: %s' % n)
        subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'docker restart n8n-n8n-1'],
                       capture_output=True, timeout=300)
        print('n8n перезапущен')
        return 0

    d = diffs()
    # 24.09.2026. Сравнение шло по СЫРОМУ тексту nodes::text. n8n при перезапуске
    # переписывает черновик в другом порядке ключей: содержимое то же, текст другой,
    # и инструмент объявлял расхождение. Именно из этого выросла строка в реестре
    # «правка лежит черновиком, в бою старая версия» — по существу версии совпадали.
    # Отсеиваем такие пары: сравниваем смысл, а не байты.
    настоящие = []
    for name, dr, lv in d:
        строки, ч, ж = чем_отличается(name)
        if строки:
            настоящие.append((name, dr, lv, строки, ч, ж))
        else:
            print('%-70s текст разошёлся, содержимое то же (порядок ключей)' % name[:70])
    if not настоящие:
        print('расхождений по существу нет: живые версии совпадают с черновиками')
        return 0
    опасно = []
    for name, dr, lv, строки, ч, ж in настоящие:
        print('%-70s черновик %s / живая %s' % (name[:70], dr, lv))
        for x in строки[:12]:
            print(x)
        if len(строки) > 12:
            print('   … ещё %d строк различий' % (len(строки) - 12))
        for что in опасное_в_черновике(ч, ж):
            print('   🔴 публиковать НЕЛЬЗЯ: %s' % что)
            опасно.append((name, что))
    if not APPLY:
        print('\nЭто отчёт. Опубликовать: --apply')
        return 0
    if опасно:
        print('\n🔴 не публикую: черновик вернул бы то, от чего мы ушли:')
        for name, что in опасно:
            print('   %-50s %s' % (name[:50], что))
        print('Сначала привести черновик в порядок в самом n8n, потом публиковать.')
        return 1

    bak = 'workflow_history_bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M')
    psql('create table %s as select h.* %s;' % (bak, DIFF_WHERE))
    print('\nкопия живых версий: %s' % bak)
    psql('update workflow_history h set nodes=w.nodes, connections=w.connections, "updatedAt"=now() '
         'from workflow_entity w where h."versionId"=w."activeVersionId" and w.active=true '
         'and h.nodes::text <> w.nodes::text;')
    left = diffs()
    if left:
        print('НЕ ОПУБЛИКОВАЛОСЬ: %s' % ', '.join(x[0] for x in left))
        return 1
    print('опубликовано: %d сценариев, расхождений не осталось' % len(d))
    subprocess.run(['ssh', '-i', KEY, 'root@' + VPS, 'docker restart n8n-n8n-1'],
                   capture_output=True, timeout=300)
    st = subprocess.run(['ssh', '-i', KEY, 'root@' + VPS,
                         "sleep 15; docker ps --filter name=n8n-n8n-1 --format '{{.Status}}'"],
                        capture_output=True, text=True, timeout=300).stdout.strip()
    print('n8n: %s' % st)
    print('откат при беде: python3 n8n_publish.py --rollback %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
