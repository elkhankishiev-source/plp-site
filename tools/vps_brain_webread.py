#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка 323: двойник получает чтение веба. «Доступа в интернет нет» больше не ответ.

Эльнур 18.09.2026: «Ты можешь ещё сам копнуть эту инф, чтобы дать им ответ, на сайтах,
в интернете» → двойник: «живого доступа в интернет и на сторонние сайты у меня нет».
Эльнур: «6. го!»

Это был честный ответ и одновременно позор системы: сценарий чтения страниц
WF_web_read живёт и активен (вебхук /webhook/web-read, читает через r.jina.ai,
отдаёт чистый текст), но инструментом двойнику его никто не выдал. Классика
«настроено, но мертво»: возможность есть, пользоваться ею некому.

Правка добавляет девятый инструмент plp_web_read:
  • берёт страницу по ссылке и возвращает текст (до 3500 знаков);
  • работает по прямой ссылке от человека и по ссылке из наших материалов;
  • в описании прямо сказано: цитировать только увиденное, цены и сроки с оговоркой
    «по сайту застройщика на сегодня», в каталог это не попадает без сверки.

    python3 vps_brain_webread.py            # показать, что изменится
    python3 vps_brain_webread.py --apply    # применить, проверить синтаксис, перезапустить
"""
import datetime, shutil, subprocess, sys

SRC = '/opt/plp-api/brain.mjs'
APPLY = '--apply' in sys.argv

ANCHOR_DEF = "  {\n    name: 'plp_objects_search',"
NEW_DEF = """  {
    /* 18.09.2026 правка 323: чтение страницы по ссылке. История в tools/vps_brain_webread.py */
    name: 'plp_web_read',
    description:
      'Прочитать страницу по ссылке и вернуть её текст. Вызывай, когда человек прислал ссылку и просит '
      + 'посмотреть, или когда нужно свериться с сайтом застройщика: сроки, наличие, условия, новости проекта. '
      + 'Отвечай ТОЛЬКО тем, что реально вернулось: не додумывай и не пересказывай по памяти. '
      + 'Цены и сроки со стороннего сайта подавай с оговоркой «по сайту застройщика на сегодня» — '
      + 'в наш каталог они не попадают без сверки. Если страница не открылась, так и скажи одной фразой '
      + 'и предложи прислать ключевое текстом. Соцсети (Instagram, TikTok, Facebook) читать бесполезно, туда не ходи.',
    input_schema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'полная ссылка на страницу, начиная с http' },
        looking_for: { type: 'string', description: 'что именно ищем на странице: сроки сдачи, цены, условия, контакты' }
      },
      required: ['url']
    }
  },
""" + ANCHOR_DEF

ANCHOR_RUN = "  if (name === 'plp_objects_search') {"
NEW_RUN = """  if (name === 'plp_web_read') {
    const u = String((inp && inp.url) || '').trim();
    if (!/^https?:\\/\\//i.test(u)) return 'Ссылка не похожа на адрес страницы. Попроси прислать её целиком, начиная с http.';
    if (/instagram\\.com|tiktok\\.com|facebook\\.com|fb\\.watch|threads\\.net|twitter\\.com|\\bx\\.com/i.test(u)) {
      return 'Это соцсеть: страница закрыта логином, читать её бесполезно. Попроси прислать суть текстом или ссылку на сайт проекта.';
    }
    try {
      const r = await helpers.httpRequest({ method: 'POST',
        url: 'http://127.0.0.1:5678/webhook/web-read',
        headers: { 'x-plp-key': env.PLP_WEBHOOK_KEY },
        body: { url: u }, json: true, timeout: 45000 });
      const c = Array.isArray(r) ? r[0] : r;
      const txt = String((c && (c.text || c.content)) || '').trim();
      if (!txt) return 'Страница не открылась. Скажи об этом одной фразой и попроси ключевое текстом: выдумывать содержимое нельзя.';
      return 'Текст страницы ' + u + ' (что искали: ' + String((inp && inp.looking_for) || 'общая информация') + '):\\n'
        + txt.slice(0, 3500)
        + '\\n\\nЭто со стороннего сайта. Цитируй только то, что здесь есть; цены и сроки подавай как «по сайту застройщика на сегодня».';
    } catch (e) {
      return 'Чтение страницы не отработало. Не обещай посмотреть позже — скажи, что содержимое по ссылке не видишь, и попроси ключевое текстом.';
    }
  }

""" + ANCHOR_RUN


def main():
    src = open(SRC, encoding='utf-8').read()
    if 'правка 323' in src:
        print('правка 323 уже стоит')
        return 0
    steps = [(ANCHOR_DEF, NEW_DEF, 'инструмент plp_web_read объявлен'),
             (ANCHOR_RUN, NEW_RUN, 'исполнитель инструмента добавлен')]
    for old, _, what in steps:
        if src.count(old) != 1:
            print('якорь «%s» найден %d раз — правка отменена' % (what, src.count(old)))
            return 1
    if not APPLY:
        for _, _, what in steps:
            print('будет изменено: %s' % what)
        print('\nЭто отчёт. Применить: --apply')
        return 0
    bak = SRC + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(SRC, bak)
    for old, new, what in steps:
        src = src.replace(old, new, 1)
        print('  ✓ %s' % what)
    open(SRC, 'w', encoding='utf-8').write(src)
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
