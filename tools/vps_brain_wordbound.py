#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 318: \\b не видит кириллицу — чиним это везде, а не по одному месту.

Эльнур 18.09.2026 про речь двойника: «убери полностью машинный вымеренный текст»,
и раньше: «ищи патерн, сверяй, исправляй по всему сайту, кабинету, везде».

Ловушка известная (правка 276b её уже ловила в одном месте): в JS \\w это только
[A-Za-z0-9_], кириллица в него НЕ входит. Значит \\b рядом с русской буквой ведёт себя
наоборот: «сурин\\b» не находит «сурин море», зато находит «сурин5». Запрет молча
не срабатывает НИ РАЗУ, и в журнале это никак не видно — правило есть, а эффекта нет.

Проверено в node на живых примерах, мёртвыми оказались:
  • запреты речи: «как дела», «конечно/безусловно», «к сожалению» — двойник
    спокойно писал их клиенту, хотя они запрещены каноном;
  • разбор денег: «150к бат», «5 м бат» — единица не распознавалась, бюджет уходил
    в профиль неверным;
  • районы: «сурин», «кату», «ката» — район из сообщения не определялся;
  • признаки: «муж», «зп», «в мес», «тур», «сад», «нал», «против», «не хочу»;
  • женский род у Дарьи: «Я Дарья» не ловилось.

Чиним механически и разом: в каждом регулярном выражении, где рядом с \\b есть
кириллица, ставим границу слова, которая знает русский алфавит:
  левая  \\b → (?<![А-Яа-яЁёA-Za-z0-9_])
  правая \\b → (?![А-Яа-яЁёA-Za-z0-9_])
Сторона определяется по символу перед \\b: начало выражения, «(» или «|» — левая,
иначе правая. Чисто латинские выражения не трогаем: там \\b работает корректно.

    python3 vps_brain_wordbound.py            # показать, что изменится
    python3 vps_brain_wordbound.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, re, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

LB = '(?<![А-Яа-яЁёA-Za-z0-9_])'
LA = '(?![А-Яа-яЁёA-Za-z0-9_])'
CYR = re.compile('[А-Яа-яЁё]')
LIT = re.compile(r'/(?:[^/\\\n\[]|\\.|\[(?:[^\]\\]|\\.)*\])+/[a-z]*')

# Почтовый фильтр оставляем как есть: он чисто латинский по смыслу, а юникодная
# граница там наоборот ослабила бы вырезание адресов, слитых с русским словом.
SKIP = ('[\\w.+-]+@',)


def fix_literal(lit):
    out, i, n = [], 0, len(lit)
    while i < n:
        if lit[i] == '\\' and i + 1 < n and lit[i + 1] == 'b':
            prev = ''.join(out)
            # левая граница: начало выражения, открытая группа или альтернатива
            left = prev.endswith('/') or prev.endswith('(') or prev.endswith('|') \
                or prev.endswith(':') or prev.endswith('^')
            out.append(LB if left else LA)
            i += 2
        else:
            if lit[i] == '\\' and i + 1 < n:
                out.append(lit[i:i + 2]); i += 2; continue
            out.append(lit[i]); i += 1
    return ''.join(out)


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 318' in src:
        print('правка 318 уже стоит')
        return 0
    lines = src.split('\n')
    plan = []
    for idx, line in enumerate(lines):
        if line.lstrip().startswith(('*', '/*', '//')):
            continue
        for m in LIT.finditer(line):
            lit = m.group(0)
            if '\\b' not in lit or not CYR.search(lit):
                continue
            # «/*» — начало комментария, а не выражения: в JS регулярка со звёздочки
            # начинаться не может, так что признак надёжный.
            if lit.startswith('/*') or any(s in lit for s in SKIP):
                continue
            plan.append((idx, lit, fix_literal(lit)))

    if not plan:
        print('выражений с мёртвой границей слова не осталось')
        return 0
    print('выражений к починке: %d' % len(plan))
    for idx, old, new in plan:
        print('  строка %-5d %s' % (idx + 1, old[:96]))
    if not APPLY:
        print('\nЭто отчёт. Применить: --apply')
        return 0

    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    for idx, old, new in plan:
        lines[idx] = lines[idx].replace(old, new, 1)

    # Починка обнажила вторую небрежность: у коротких вариантов не было ЛЕВОЙ границы.
    # Пока «к\\b» был мёртв, это ничего не значило; ожив, он начал ловить последнюю букву
    # любого слова — «банк», «срок», «Ок» читались как денежный сигнал, а «нал\\b» делал
    # из «канала» и «финала» разговор про наличные. Дописываем левую границу ровно там,
    # где вариант в одну-три буквы стоит без неё.
    text = '\n'.join(lines)
    left = [('|к' + LA + '|k' + LA + '|тыс)', '|' + LB + 'к' + LA + '|' + LB + 'k' + LA + '|тыс)'),
            ('|нал' + LA + '|деклар', '|' + LB + 'нал' + LA + '|деклар')]
    for old, new in left:
        if old not in text:
            print('левая граница: якорь не найден, пропускаю')
            continue
        text = text.replace(old, new, 1)
        print('  ✓ левая граница дописана: %s' % new[:46])
    lines = text.split('\n')

    marker = ('/* 18.09.2026 правка 318: \\b в JS не видит кириллицу — %d выражений '
              'молча не срабатывали. Границы слова теперь знают русский алфавит. */\n' % len(plan))
    out = marker + '\n'.join(lines)
    open(SRC, 'w', encoding='utf-8').write(out)
    chk = subprocess.run(['node', '--check', SRC], capture_output=True, text=True)
    if chk.returncode:
        shutil.copy2(bak, SRC)
        print('СИНТАКСИС СЛОМАН — откатил:\n' + chk.stderr[:500])
        return 1
    print('синтаксис ок; копия: %s' % bak)
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
