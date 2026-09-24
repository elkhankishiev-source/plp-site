#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Список клиентов и их объектов — один лист, читаемый глазами.

Эльнур 24.09.2026: «отправишь список клиентов дополненный актуальный и красивый
легко читаемый».

Истина — Supabase: clients + client_objects. Никакого «вручную»: файл каждый раз
собирается заново, правка идёт в базу, а не в файл.

ВАЖНО ПРО МЕСТО. Здесь персональные данные: имена, телефоны, почты, суммы.
Репозиторий сайта ПУБЛИЧНЫЙ, поэтому файл кладётся в ~/PLP-выгрузки и туда же
не попадает ничего из git. Наружу этот лист не публикуется никогда.

    python3 tools/clients_report.py                 # собрать файлы
    python3 tools/clients_report.py --послать --го  # и отправить в «PLP | отдел продаж»

Наружу уходит только по явному «го» — и только в нашу рабочую группу, где эти
данные и так есть у людей, которые с ними работают.
"""

import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ENV = os.path.expanduser('~/.plp_site_supabase.env')
ВЫХОД = os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.html')
ТАБЛИЦА = os.path.expanduser('~/PLP-выгрузки/Клиенты_PLP.xlsx')
PKT = ZoneInfo('Asia/Bangkok')


def creds():
    env = {}
    for line in open(ENV, encoding='utf-8'):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env['SUPABASE_URL'].rstrip('/'), env['SUPABASE_SERVICE_KEY']


def взять(путь):
    url, key = creds()
    r = urllib.request.Request(url + '/rest/v1/' + путь,
                               headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    return json.load(urllib.request.urlopen(r, timeout=90))


def деньги(x):
    try:
        n = int(float(x))
    except Exception:
        return ''
    return '{:,}'.format(n).replace(',', ' ') + ' ฿'


def дата(x):
    if not x:
        return ''
    try:
        return datetime.date.fromisoformat(str(x)[:10]).strftime('%d.%m.%Y')
    except Exception:
        return str(x)[:10]


def дополнить(связки, объекты):
    """Раскладываем колонки представления по именам, которыми пользуется отчёт.

    Считать здесь больше нечего: всё посчитано в client_objects_full, и ровно
    то же видят двойник и кабинет. Здесь — только перенос имён, чтобы не
    заводить второй свод правил о том, что такое «срок по проекту».
    """
    for с in связки:
        с['handover_on'] = с.get('передача')
        с['передача_откуда'] = (с.get('передача_откуда') or '')
        if с['передача_откуда'] == 'по договору':
            с['передача_откуда'] = ''
        с['stage'] = с.get('стадия') or ''
        с['стадия_откуда'] = (с.get('стадия_откуда') or '')
        if с['стадия_откуда'] == 'по договору':
            с['стадия_откуда'] = ''
        пл = с.get('площадь_м2')
        if пл:
            try:
                с['площадь'] = ('%g' % float(пл)) + ' м2'
            except Exception:
                с['площадь'] = str(пл)


# 25.09, Эльнур: «стоп, это один лист! Поиск и редактирование прям там же
# возможно, если это эксель». Листы «Поиск» и «Заполнить» убраны: искать Excel
# умеет по Ctrl+F на любом листе, а править можно прямо здесь — значение живёт
# в левой верхней клетке объединения, она и редактируется.
# Правки возвращаются в базу через tools/clients_import.py.


def таблица(строки, РОЛЬ):
    """Лист собственников. Собран заново 25.09.2026 под диктовку Эльнура:

      «Горизонтальные и вертикальные разметки в таблице, между людьми толстые,
       между объектами тонкие, прочерчено от края до края! Один человек — одна
       колонка, совладелец там же, рядом с владельцем. Таблица закрыта.»

    Устройство простое и держится на одном правиле: сначала пишем ВСЕ строки,
    потом одним проходом расставляем рамки по всему прямоугольнику листа, и
    только в самом конце объединяем клетки человека. Порядок не декоративный:
    запись рамки в неглавную клетку объединения openpyxl переносит на главную,
    и линия уезжает не туда.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    ТОЛСТАЯ = Side(style='medium', color='6E6A4F')   # между людьми и по краю
    ТОНКАЯ = Side(style='thin', color='B8B0A0')      # между объектами и колонками
    ЧЕЛОВЕК = 5            # колонки, принадлежащие человеку: имя, код, телефон, почта, кабинет
    ВЫСОТА = 14            # строка объекта
    СТРОКА = 12            # одна строка текста в клетке
    ВОЗДУХ = 2             # минимальный отступ сверху и снизу полосы
    ТОН = ('FFFFFF', 'F4F2EA')

    шапка = ['Собственник и совладелец', 'Код', 'Телефон', 'Почта', 'Кабинет',
             'Проект', 'Юнит', 'Спальни', 'Площадь', 'Район', 'Состояние',
             'Цена, ฿', 'Куплено', 'Передача', 'Откуда срок', 'Статус УК',
             'Чего не хватает', 'Код объекта']
    ВПРАВО = {'Цена, ฿'}
    ЦЕНТР = {'Кабинет', 'Юнит', 'Спальни', 'Площадь', 'Куплено', 'Передача', 'Откуда срок'}
    # Перенос ТОЛЬКО в колонках человека: у полосы высота считается под имя, там
    # вторая строка поместится. У строк объектов высота одна на весь лист, и
    # перенесённый текст просто спрячется под нижним краем клетки — это хуже,
    # чем узкая колонка. Поэтому объектные колонки не переносим, а укорачиваем
    # само содержимое (см. «чего не хватает» в client_objects_full).
    ПЕРЕНОС = {'Собственник и совладелец', 'Почта'}
    # Потолки на болтливые колонки: они переносятся по словам, поэтому узкая
    # колонка не режет текст, а экономит ширину листа.
    ПОТОЛОК = {'Собственник и совладелец': 20, 'Почта': 16,
               'Состояние': 16, 'Чего не хватает': 24, 'Код объекта': 19,
               'Проект': 34}
    # У «Проекта» потолка нет намеренно: название не переносится (высота строки
    # на листе одна) и обрезать его нельзя — «AYANA Heights Seaview Residen…»
    # это не экономия, а испорченные данные. Пустое место резать можно,
    # содержимое — нет.

    wb = Workbook()
    ws = wb.active
    ws.title = 'Собственники'
    ws.append(шапка)

    # ---- 1. строки. Полоса человека: воздух, его объекты, воздух ----------
    ряд, полосы = 2, []
    for имя, к, юниты in строки:
        первый = ряд
        совладельцы = []
        for u in юниты:
            for н, р in (u.get('совладельцы') or []):
                м = '%s — %s' % (н, РОЛЬ.get(р, р or ''))
                if м not in совладельцы:
                    совладельцы.append(м)
        объектные = []
        ряд += 1                                   # воздух сверху
        for u in юниты:
            сп = u.get('спальни')
            значения = [
                # «The » в начале названия ничего не говорит и стоит на восьми
                # проектах из шестнадцати — снимаем, колонка уже на четыре знака.
                re.sub(r'^The ', '', u.get('проект') or u.get('project_name') or ''),
                u.get('unit') or '',
                сп if сп == 'студия' else ((сп + ' сп.') if сп else ''),
                u.get('площадь') or '', u.get('район') or '', u.get('stage') or '',
                int(float(u['purchase_price'])) if u.get('purchase_price') else None,
                дата(u.get('bought_on')), дата(u.get('handover_on')),
                ('со слов' if u.get('handover_caveat') else '') or u.get('передача_откуда') or '',
                u.get('uk_status') or '', u.get('не_хватает') or '', u.get('object_id') or '']
            for i, зн in enumerate(значения, ЧЕЛОВЕК + 1):
                ws.cell(row=ряд, column=i, value=зн)
            объектные.append(ряд)
            ряд += 1
        ряд += 1                                   # воздух снизу
        последний = ряд - 1
        # данные человека — в первую строку полосы: там будет левая верхняя
        # клетка объединения, только она и хранит значение
        for i, зн in enumerate([
                имя + (('\n' + '\n'.join(совладельцы)) if совладельцы else ''),
                к.get('code') or '', ('+' + str(к['phone'])) if к.get('phone') else '',
                к.get('email') or '', 'да' if к.get('вход') else ''], 1):
            ws.cell(row=первый, column=i, value=зн)
        полосы.append((первый, последний, объектные, len(совладельцы) + 1))

    низ, право = ряд - 1, len(шапка)

    # ---- 2. рамки. Один проход по всему прямоугольнику: пустых клеток нет --
    сверху_толстая = {1, 2} | {п[0] for п in полосы}
    сверху_тонкая = {r for _, _, об, _ in полосы for r in об[1:]}
    for r in range(1, низ + 1):
        for c in range(1, право + 1):
            кл = ws.cell(row=r, column=c)
            кл.border = Border(
                top=ТОЛСТАЯ if r in сверху_толстая else (ТОНКАЯ if r in сверху_тонкая else None),
                bottom=ТОЛСТАЯ if r == низ else None,
                left=ТОЛСТАЯ if c == 1 else ТОНКАЯ,
                right=ТОЛСТАЯ if c == право else ТОНКАЯ)

    # ---- 3. заливка, шрифт, выравнивание ---------------------------------
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='6E6A4F')
        c.alignment = Alignment(vertical='center', wrap_text=True, indent=1)
    for н, (первый, последний, _, _) in enumerate(полосы):
        тон = PatternFill('solid', fgColor=ТОН[н % 2])
        for r in range(первый, последний + 1):
            for c in range(1, право + 1):
                ws.cell(row=r, column=c).fill = тон
        ws.cell(row=первый, column=1).font = Font(bold=True)
    for i, имя_к in enumerate(шапка, 1):
        гор = 'right' if имя_к in ВПРАВО else ('center' if имя_к in ЦЕНТР else 'left')
        for r in range(2, низ + 1):
            кл = ws.cell(row=r, column=i)
            кл.alignment = Alignment(horizontal=гор,
                                     vertical='center' if i <= ЧЕЛОВЕК else 'top',
                                     wrap_text=имя_к in ПЕРЕНОС,
                                     indent=1 if гор in ('left', 'right') else 0)
            if имя_к == 'Цена, ฿':
                кл.number_format = '# ##0'
            if имя_к in ('Юнит', 'Код объекта'):
                кл.font = Font(color='6B6459')

    # ---- 4. высоты. Полоса обязана вместить имя в три строки --------------
    ws.row_dimensions[1].height = 26
    for r in range(2, низ + 1):
        ws.row_dimensions[r].height = ВЫСОТА
    for первый, последний, объектные, строк_имени in полосы:
        добор = max(ВОЗДУХ, int((max(3, строк_имени) * СТРОКА - len(объектные) * ВЫСОТА) / 2) + 1)
        ws.row_dimensions[первый].height = добор
        ws.row_dimensions[последний].height = добор

    # ---- 5. ширины: по СОДЕРЖИМОМУ, не по заголовку ----------------------
    # Эльнур 25.09: «ширину пустого места в таблицах уменьши и посмотри, чтобы
    # всё было красиво симметрично». Раньше ширину задирал заголовок: колонка
    # «Статус УК» пуста у всех сорока девяти строк, а занимала одиннадцать
    # знаков, «Кабинет» под слово «да» — девять. Заголовок переносится по
    # словам, значит держать его в одну строку не нужно.
    ширины, пустота, по_данным_все = {}, {}, {}
    объектных = sum(len(о) for _, _, о, _ in полосы)
    for i, имя_к in enumerate(шапка, 1):
        значения = [max((len(x) for x in str(ws.cell(row=r, column=i).value or '').split('\n')),
                        default=0) for r in range(2, низ + 1)]
        по_данным = max(значения) if значения else 0
        по_данным_все[имя_к] = по_данным
        занято = sum(1 for x in значения if x)
        пустота[имя_к] = занято < объектных / 3        # колонка почти пустая
        по_шапке = len(имя_к) // 2 + 2                 # заголовок переносится, хватит двух строк
        ширины[имя_к] = min(max(по_данным + 2, по_шапке, 5), ПОТОЛОК.get(имя_к, 20))

    # Симметрия: колонки одного смысла получают одинаковую ширину, иначе лист
    # выглядит рваным. Но почти пустую колонку симметрия НЕ раздувает — она и
    # была главным источником пустого места: «Статус УК» пуст у всех сорока
    # девяти строк и занимал одиннадцать знаков.
    for семья in (('Куплено', 'Передача'),
                  ('Юнит', 'Спальни', 'Район'),
                  ('Откуда срок', 'Кабинет')):
        живые = [к for к in семья if not пустота[к]]
        if живые:
            общая = max(ширины[к] for к in живые)
            for к in живые:
                ширины[к] = общая
    # У почти пустой колонки ширину задаёт ТОЛЬКО её содержимое: заголовок
    # перенесётся, а резать значения нельзя — обрезанная клетка хуже пустого
    # места. «Статус УК» пуст совсем, ему хватает минимума.
    for имя_к in шапка:
        if пустота[имя_к]:
            ширины[имя_к] = min(max(по_данным_все[имя_к] + 2, 5), ПОТОЛОК.get(имя_к, 20))

    for i, имя_к in enumerate(шапка, 1):
        ws.column_dimensions[get_column_letter(i)].width = ширины[имя_к]

    # ---- 6. объединение — В САМОМ КОНЦЕ, после рамок ---------------------
    for первый, последний, _, _ in полосы:
        if последний > первый:
            for c in range(1, ЧЕЛОВЕК + 1):
                ws.merge_cells(start_row=первый, start_column=c,
                               end_row=последний, end_column=c)

    ws.freeze_panes = 'A2'
    ws.sheet_view.showGridLines = False
    wb.save(ТАБЛИЦА)


def отправить(нехватка, людей, юнитов, с_суммой):
    """Таблицу — в группу «PLP | отдел продаж», с обращением к Дарье.

    Упоминание ссылкой на id: в группе подсветится и придёт уведомлением, даже
    если публичного ника нет. Тот же приём, что в переписи собственников.
    """
    токен = open(os.path.expanduser('~/.plp_bot_elnurphuket_bot')).read().strip()
    чат = os.environ.get('TG_SALES_CHAT_ID', '-4664612682')
    дарья = os.environ.get('DARIA_TG_ID', '8227351774')
    строки = '\n'.join('• %s — не хватает у %d из %d' % (к, v, юнитов)
                       for к, v in нехватка)
    подпись = (
        '<a href="tg://user?id=%s">Дарья</a>, список клиентов и их объектов на сегодня.\n\n'
        '%d человек, %d объектов, сумма известна по %d.\n'
        'Район, спальни, срок передачи и стадию подтянул из карточек проектов — '
        'в колонках «откуда» видно, взято по юниту или по проекту.\n\n'
        'Чего не хватает:\n%s\n\n'
        'Заполни, что знаешь, прямо в файле и пришли обратно — перенесу в базу.'
        % (дарья, людей, юнитов, с_суммой, строки))

    гр = '----------%s' % os.urandom(8).hex()
    части = []
    for имя, зн in (('chat_id', чат), ('caption', подпись), ('parse_mode', 'HTML')):
        части.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                      % (гр, имя, зн)).encode())
    части.append(('--%s\r\nContent-Disposition: form-data; name="document"; filename="%s"\r\n'
                  'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n'
                  % (гр, os.path.basename(ТАБЛИЦА))).encode())
    части.append(open(ТАБЛИЦА, 'rb').read())
    части.append(('\r\n--%s--\r\n' % гр).encode())
    тело = b''.join(части)
    r = urllib.request.Request('https://api.telegram.org/bot%s/sendDocument' % токен, data=тело,
                               headers={'Content-Type': 'multipart/form-data; boundary=%s' % гр})
    ответ = json.loads(urllib.request.urlopen(r, timeout=180).read().decode())
    print('отправлено в «PLP | отдел продаж»: %s' % ответ.get('ok'))
    return ответ


def главное():
    # 24.09: читаем ЗАПОЛНЕННОЕ представление client_objects_full — то же самое,
    # что видят двойник в Телеграме и кабинет собственника. Раньше дозаполнение
    # жило только здесь, в отчёте, и у клиента в кабинете клетки оставались
    # пустыми: починил в одном месте из трёх.
    связки = взять('client_objects_full?select=*&limit=2000')
    # 24.09: сначала связки, потом ТОЛЬКО нужные люди. Запрос всех клиентов с
    # limit=5000 Supabase молча обрезает на тысяче — в таблице половина строк
    # оставалась без кода и телефона, хотя в базе они есть. Тот же урок уже был
    # записан («limit больше 1000 Supabase молча обрезает») и всё равно повторился.
    нужны = sorted({с['client_id'] for с in связки if с.get('client_id')})
    # Вход в кабинет живёт в owner_accounts: человек входит по своему номеру и
    # коду. Колонка clients.cabinet_enabled к этому отношения не имеет — она
    # стоит false у 35 человек, у которых вход есть. Смотреть надо туда, где
    # вход заводится.
    входы = взять('owner_accounts?select=client_id,phone,status&limit=1000')
    клиенты = {}
    for i in range(0, len(нужны), 40):
        куча = ','.join(нужны[i:i + 40])
        for c in взять('clients?client_id=in.(' + urllib.parse.quote(куча) +
                       ')&select=client_id,code,name,phone,email,cabinet_enabled,phone_status,is_internal'):
            клиенты[c['client_id']] = c
    # 24.09: свои — Эльнур и Дарья — в списке КЛИЕНТОВ быть не должны. Их вилла
    # Manor S1-20 в базе записана так же, как клиентская, и они приехали вместе
    # со всеми. Для этого в clients и заведён признак is_internal; я его не
    # спросил. Фильтруем здесь, а не вычищаем связку: связка верная, это их юнит.
    свои = {i for i, c in клиенты.items() if c.get('is_internal')}
    связки = [с for с in связки if с.get('client_id') not in свои]
    дополнить(связки, None)

    по_id = {a.get('client_id') for a in входы if a.get('client_id')}
    по_тел = {str(a.get('phone') or '').replace('+', '') for a in входы if a.get('phone')}
    for c in клиенты.values():
        c['вход'] = (c['client_id'] in по_id
                     or str(c.get('phone') or '').replace('+', '') in по_тел)

    # 24.09, Эльнур, две поправки подряд:
    #   «когда совладельцы и у них общая недвижимость — не надо всех писать,
    #    дублировать, множить»
    #   «имя, перечисление, закончили, теперь уже новое имя»
    # Значит: блок на ЧЕЛОВЕКА, внутри перечень его объектов. Общий объект
    # стоит ОДИН раз — у того, кто записан владельцем, а совладелец назван прямо
    # в строке объекта. Отдельного блока на одного только совладельца не заводим:
    # это и было бы то самое размножение.
    # 24.09, Эльнур: «там где сделка не состоялась, зачем она». Это список
    # собственников, а не история попыток: расторгнутые и несостоявшиеся не берём.
    связки = [с for с in связки
              if с.get('rel') != 'lost' and (с.get('stage') or '') != 'расторгнут']

    по_юнитам = {}
    for с in связки:
        по_юнитам.setdefault(с['object_id'], []).append(с)

    по_людям = {}
    for oid, доли in по_юнитам.items():
        доли.sort(key=lambda x: (0 if x.get('rel') == 'owns' else 1,
                                 (клиенты.get(x['client_id'], {}).get('name') or '')))
        главный = доли[0]
        u = dict(главный)
        u['совладельцы'] = [(клиенты.get(д['client_id'], {}).get('name') or '—', д.get('rel'))
                            for д in доли[1:]]  # из тех же связок, что и блоки
        u['роли'] = [д.get('rel') for д in доли]
        по_людям.setdefault(главный['client_id'], []).append(u)

    строки = []
    for cid, юниты in по_людям.items():
        к = клиенты.get(cid) or {}
        юниты.sort(key=lambda x: ((x.get('project_name') or '').lower(), x.get('unit') or ''))
        строки.append((к.get('name') or '(без имени)', к, юниты))
    for _, _, ю in строки:
        ю.sort(key=lambda x: ((x.get('проект') or x.get('project_name') or '').lower(),
                              x.get('unit') or ''))
    строки.sort(key=lambda x: x[0].lower())

    всего_юнитов = sum(len(ю) for _, _, ю in строки)
    людей = len({с['client_id'] for с in связки})
    все_ю = [u for _, _, ю in строки for u in ю]
    с_ценой = sum(1 for u in все_ю if u.get('purchase_price'))
    сумма = sum(float(u['purchase_price']) for u in все_ю if u.get('purchase_price'))
    кабинет = sum(1 for _, к, _ in строки if к.get('вход'))
    бн = sum(1 for _, к, _ in строки if not (к.get('phone') or '').strip())

    РОЛЬ = {'owns': 'владелец', 'spouse': 'супруг(а)', 'lost': 'сделка не состоялась'}

    куски = []
    for имя, к, юниты in строки:
        хвост = []
        if к.get('code'):
            хвост.append(html.escape(к['code']))
        if к.get('phone'):
            хвост.append('+' + html.escape(str(к['phone'])))
        if к.get('email'):
            хвост.append(html.escape(к['email']))
        мет = []
        if к.get('вход'):
            мет.append('<span class="м м-каб">кабинет открыт</span>')
        if not (к.get('phone') or '').strip():
            мет.append('<span class="м м-нет">нет телефона</span>')

        блоки = []
        for u in юниты:
            вместе = ', '.join(html.escape(н) for н, _ in (u.get('совладельцы') or []))
            поля = [
                ('Район', u.get('район')),
                ('Спальни', u.get('спальни')),
                ('Площадь', u.get('площадь')),
                ('Владение', u.get('владение')),
                ('Сумма', деньги(u.get('purchase_price'))),
                ('Куплено', дата(u.get('bought_on'))),
                ('Передача', (дата(u.get('handover_on')) or '') +
                 ('<span class="ог" title="срок со слов, документом не подтверждён">?</span>'
                  if u.get('handover_caveat')
                  else (' <i>' + html.escape(u.get('передача_откуда') or '') + '</i>'
                        if u.get('передача_откуда') else ''))),
                ('Состояние', html.escape(u.get('stage') or '') +
                 (' <i>' + html.escape(u.get('стадия_откуда') or '') + '</i>'
                  if u.get('стадия_откуда') else '')),
                ('Статус УК', u.get('uk_status')),
            ]
            клетки = ''.join('<div class="кл"><span>%s</span><b>%s</b></div>' % (н, з)
                             for н, з in поля if з)
            нет = ('<div class="нет">не хватает: %s</div>' % html.escape(u['не_хватает'])) if u.get('не_хватает') else ''
            блоки.append(
                '<div class="об"><div class="об-шапка"><b>%s</b> <span class="юн">%s</span>%s</div>'
                '<div class="сетка">%s</div>%s</div>' % (
                    html.escape(u.get('проект') or u.get('project_name') or '—'),
                    html.escape(u.get('unit') or ''),
                    (' <span class="вместе">совместно с ' + вместе + '</span>') if вместе else '',
                    клетки, нет))

        куски.append(
            '<section class="чел"><header><h2>%s</h2><div class="код">%s</div>'
            '<div class="меты">%s</div></header>%s</section>' % (
                html.escape(имя), ' · '.join(хвост), ''.join(мет), ''.join(блоки)))

    сейчас = datetime.datetime.now(PKT).strftime('%d.%m.%Y, %H:%M по Пхукету')
    док = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Клиенты PLP</title>
<style>
:root{--фон:#faf8f4;--лист:#fff;--чернила:#23201b;--тихо:#7a7368;--рамка:#e7e1d6;--олива:#D2D5B3;--тревога:#8f4b3a}
*{box-sizing:border-box}
body{margin:0;background:var(--фон);color:var(--чернила);
 font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.обёртка{max-width:1080px;margin:0 auto;padding:32px 16px 72px}
h1{font-size:clamp(24px,3.4vw,34px);margin:0 0 6px;letter-spacing:-.02em}
.под{color:var(--тихо);margin:0 0 26px;font-size:.93rem}
.итоги{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 30px}
.итог{background:var(--лист);border:1px solid var(--рамка);border-radius:14px;padding:14px 16px}
.итог b{display:block;font-size:1.5rem;letter-spacing:-.02em}
.итог span{color:var(--тихо);font-size:.8rem}
.чел{background:var(--лист);border:1px solid var(--рамка);border-radius:16px;padding:18px 18px 8px;margin:0 0 14px}
.чел header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:12px}
.чел h2{font-size:1.12rem;margin:0;letter-spacing:-.01em}
.код{color:var(--тихо);font-size:.78rem;font-variant-numeric:tabular-nums}
.конт{color:var(--тихо);font-size:.84rem;flex:1 1 100%}
.меты{display:flex;gap:6px;flex-wrap:wrap}
.м{font-size:.72rem;padding:3px 9px;border-radius:999px;border:1px solid var(--рамка)}
.м-каб{background:var(--олива)}
.м-нет{color:var(--тревога);border-color:currentColor}
.об{border-top:1px solid var(--рамка);padding:12px 0 4px}\n.об:first-of-type{border-top:none;padding-top:4px}\n.об-шапка{font-size:.95rem;margin-bottom:2px}\n.об-шапка .юн{color:var(--тихо);font-variant-numeric:tabular-nums}\n.вместе{font-size:.78rem;color:var(--тихо)}\n.сетка{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-top:12px}\n.кл{background:var(--фон);border-radius:10px;padding:8px 10px}\n.кл span{display:block;font-size:.68rem;color:var(--тихо);text-transform:uppercase;letter-spacing:.04em}\n.кл b{font-size:.9rem;font-weight:600}\n.кл i{font-style:normal;color:var(--тихо);font-weight:400;font-size:.78rem}\n.нет{margin-top:10px;font-size:.8rem;color:var(--тревога)}\n.чел.плохо{opacity:.6}\ntable{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;font-weight:600;color:var(--тихо);font-size:.75rem;text-transform:uppercase;
 letter-spacing:.04em;padding:0 10px 6px 0;border-bottom:1px solid var(--рамка)}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--фон);vertical-align:top}
tr:last-child td{border-bottom:none}
.пр{font-weight:600}
.юн{font-variant-numeric:tabular-nums;color:var(--тихо)}
.ц{font-variant-numeric:tabular-nums;white-space:nowrap}
.сост{color:var(--тихо);font-size:.82rem}
.класс-плохо td{opacity:.55;text-decoration:line-through solid rgba(0,0,0,.25)}
.ог{display:inline-block;margin-left:4px;width:15px;height:15px;line-height:15px;text-align:center;
 border-radius:50%;background:var(--олива);font-size:.68rem;cursor:help;text-decoration:none}
footer{color:var(--тихо);font-size:.8rem;margin-top:28px;line-height:1.7}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--фон:#17150f;--лист:#1f1c16;
 --чернила:#efe9dd;--тихо:#9c948a;--рамка:#302b23}}
@media print{body{background:#fff}.чел{break-inside:avoid;box-shadow:none}}
</style></head><body><div class="обёртка">
<h1>Клиенты Property Library</h1>
<p class="под">Собрано из базы @СЕЙЧАС@. Файл пересобирается командой, вручную не правится.</p>
<div class="итоги">
 <div class="итог"><b>@ЛЮДЕЙ@</b><span>человек-собственников</span></div>
 <div class="итог"><b>@ЮНИТОВ@</b><span>объектов, строка = объект</span></div>
 <div class="итог"><b>@СЦЕНОЙ@ из @ЮНИТОВ@</b><span>юнитов с известной суммой</span></div>
 <div class="итог"><b>@СУММА@</b><span>сумма известных сделок</span></div>
 <div class="итог"><b>@КАБИНЕТ@</b><span>с открытым кабинетом</span></div>
 <div class="итог"><b>@БЕЗНОМЕРА@</b><span>без телефона</span></div>
</div>
@КАРТОЧКИ@
<footer>Кружок «?» у даты передачи — срок назван со слов, документом не подтверждён.<br>
Перечёркнутая строка — сделка не состоялась или договор расторгнут.<br>
Персональные данные. Наружу этот лист не выкладывается.</footer>
</div></body></html>"""
    for метка, значение in (('@СЕЙЧАС@', сейчас), ('@ЛЮДЕЙ@', людей), ('@ЮНИТОВ@', всего_юнитов),
                            ('@СЦЕНОЙ@', с_ценой), ('@СУММА@', деньги(сумма)),
                            ('@КАБИНЕТ@', кабинет), ('@БЕЗНОМЕРА@', бн),
                            ('@КАРТОЧКИ@', '\n'.join(куски))):
        док = док.replace(метка, str(значение))

    os.makedirs(os.path.dirname(ВЫХОД), exist_ok=True)
    open(ВЫХОД, 'w', encoding='utf-8').write(док)
    print('готово: %s' % ВЫХОД)
    таблица(строки, РОЛЬ)
    print('готово: %s' % ТАБЛИЦА)
    нехватка = []
    for к in ('сумма', 'дата покупки', 'срок передачи', 'спальни', 'статус УК'):
        n = sum(1 for u in все_ю if к in (u.get('не_хватает') or ''))
        if n:
            нехватка.append((к, n))
    print('человек %d, объектов %d, с суммой %d, сумма %s' % (людей, всего_юнитов, с_ценой, деньги(сумма)))
    print('не хватает: ' + '; '.join('%s у %d' % (к, n) for к, n in нехватка))
    if '--послать' in sys.argv:
        if '--го' not in sys.argv:
            print('наружу не отправлял. Отправить: --послать --го')
        else:
            отправить(нехватка, людей, всего_юнитов, с_ценой)


if __name__ == '__main__':
    главное()
