# -*- coding: utf-8 -*-
"""Naturale Kamala: sheet.json листа-оффера. 24.10.2026.
Эльнур 23.10: «виллы топ, и себе в работу тоже взять их, закинь их к нам на сайт и в офер»; «ок го».
Источники (материалы_проекта, папка застройщика AAG Development):
  P = 2026.10.15 Naturale Kamala Price List (прайс 15.10.2026: цены, предпродажная цена на 2 сделки, график, взносы)
  B = Brochure Naturale Kamala (брошюра застройщика)
  F = планировки и рендеры по типам Aria / Kamala / Andaman (слайды застройщика, обновление планировок 18.10.2026)
Номера участков, комиссии и «на руки» в лист НЕ переносить. Срока сдачи в документах нет: не писать.
Прайс Phase 2 (другая очередь, Cherng Talay) и фактшит очереди 1 к этому листу не относятся.
    python3 offers/naturale-kamala/make_sheet.py && node tools/offer_sheet.mjs naturale-kamala
"""
import json, os, re
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLUG = 'naturale-kamala'
NOMER = json.load(open(os.path.join(ROOT, 'build/nomera.json')))[SLUG]
URL = '/%s/%s' % (SLUG, NOMER)
PREVIEW = 'preview-v1.jpg'
k = json.load(open(os.path.join(ROOT, 'offers/kuartz/sheet.json')))

head = k['head']
head = head.replace("location.replace('/kuartz'", "location.replace('%s'" % URL)
head = re.sub(r'<title>.*?</title>', '<title>Naturale Kamala · Камала, виллы с бассейном · Property Library Phuket</title>', head)
head = re.sub(r'(<meta property="og:title" content=")[^"]*', r"\1Naturale Kamala: 14 вилл с бассейном на Millionaire's Mile", head)
head = re.sub(r'(<meta property="og:description" content=")[^"]*',
              r'\1Предложение Property Library Phuket: виллы Naturale Kamala от AAG Development. Три типа, цены от 67,7 млн ฿, график оплаты, планировки', head)
head = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\1https://property-library.com' + URL, head)
head = re.sub(r'(<meta property="og:image" content=")[^"]*', r'\1https://property-library.com/offers/%s/img/%s' % (SLUG, PREVIEW), head)
head = re.sub(r'@page\{size:210mm \d+mm', '@page{size:210mm 4200mm', head)
assert 'kuartz' not in head.lower(), 'в голове остался KUARTZ'

WA = 'https://wa.me/66955492587?text=' + quote('Здравствуйте! Интересны виллы Naturale Kamala')

SM = 'color:var(--muted);font-size:7.6pt'


def usd(thb):  # курс витрины сайта 35 ฿ за $ (build/gen.mjs RATE)
    return '%s млн $' % ('%.2f' % (thb / 35e6)).replace('.', ',')


J = {
 'slug': SLUG,
 'pdf': 'Naturale_Kamala.pdf',
 'head': head,
 'top': k['top'].replace('по презентации застройщика', 'по прайсу и брошюре застройщика'),
 'hero': '''<div class="hero" style="height:118mm">
  <div class="txt">
    <div class="eyebrow">Камала · Millionaire's Mile</div>
    <h1 style="font-size:40pt;white-space:normal;line-height:.95">Naturale<br><span>Kamala</span></h1>
    <p class="sub">14 вилл с бассейном на склоне Millionaire's Mile у пляжа Камала. Три типа на 3, 4 и 5 спален, у старших вид на океан. От 67,7 млн ฿ (около 1,93 млн $), на ближайшие две сделки предпродажная цена от 57,5 млн ฿.</p>
  </div>
  <div class="photo" style="left:90mm;top:24mm;width:112mm;height:76mm;transform:rotate(-1.5deg)"><img src="img/hero.webp" alt="Naturale Kamala, вилла Andaman с бассейном, рендер застройщика"></div>
  <div class="label" style="left:150mm;top:9mm;transform:rotate(6deg)">14 вилл</div>
  <div style="position:absolute;left:92mm;top:102.5mm;font-size:7pt;color:var(--muted);z-index:3">Вилла Andaman, рендер застройщика</div>
</div>''',
 'stats': '''<div class="stats">
  <div class="stat"><b>14</b><span>вилл, 2 уже проданы</span></div>
  <div class="stat"><b>3–5</b><span>спален, три типа вилл</span></div>
  <div class="stat"><b>67,7 млн ฿</b><span>цена «от», вилла Aria</span></div>
  <div class="stat"><b>25 км</b><span>до аэропорта</span></div>
</div>''',
 'units': {
  'eyebrow': 'Виллы и цены',
  'h2': 'Три типа вилл с бассейном и садом в цене',
  'lead': 'Aria на 3 спальни с террасой, Kamala на 4 спальни с частичным видом на океан и Andaman на 5 спален с видом на океан. В цену каждой виллы входят бассейн с солёной водой, скрытые кондиционеры, встроенные шкафы, кухня-пантри со встроенной техникой, умное освещение, ванные и ландшафтный сад.',
  'facts': '''<div class="facts" style="grid-template-columns:repeat(4,1fr);margin:5mm 0 6mm">
    <div><b>14</b><span>вилл в посёлке</span></div>
    <div><b>12</b><span>в продаже, 2 проданы</span></div>
    <div><b>30%</b><span>взнос: бронь 2% и договор 28%</span></div>
    <div><b>лизхолд</b><span>аренда земли, регистрируется в госорганах</span></div>
  </div>''',
  'cards': [
   '''<div class="card"><h3>Площади и бассейны</h3>
      <table>
        <tr><td>Aria · 3 спальни</td><td class="r num">жилая 248 м²</td></tr>
        <tr><td><span style="%s">с террасами 385 м², участок 285–297 м², бассейн 15 × 3,4 м</span></td><td></td></tr>
        <tr><td>Kamala · 4 спальни</td><td class="r num">жилая 526–589 м²</td></tr>
        <tr><td><span style="%s">с террасами 911–1 000 м², участок 500–550 м², бассейн 18,1 × 6 м</span></td><td></td></tr>
        <tr><td>Andaman · 5 спален</td><td class="r num">жилая 778–798 м²</td></tr>
        <tr><td><span style="%s">с террасами 1 312–1 461 м², участок 624–973 м², бассейн 21,15 × 6,5 м</span></td><td></td></tr>
      </table>
      <p class="src">Жилая площадь: внутри дома. С террасами: общая застроенная площадь, жилая и внешняя вместе. Прайс застройщика, 15.10.2026. Размеры ориентировочные, окончательный обмер после стройки.</p></div>''' % (SM, SM, SM),
   '''<div class="card"><h3>Что в каждом типе</h3>
      <ul class="l">
        <li><b>Aria</b>: 3 спальни с ванными и гардеробными, 2 столовые, 2 кухни (европейская и тайская), беседка-сала, 2 места на парковке</li>
        <li><b>Kamala</b>: 4 спальни (можно до 6), 8 санузлов, семейная комната, спортзал и сауна, кабинет, частный лифт, комната для горничной, 3 места</li>
        <li><b>Andaman</b>: 5 спален (можно до 9), 9 санузлов, спа, спортзал, сауна и парная, кинозал, кабинет, частный лифт, 2 комнаты для горничной, 4 места</li>
      </ul>
      <p class="src">Прайс и брошюра застройщика, 2026.</p></div>''',
  ],
  'cards_wide': [
   '''<div class="card"><h3>Цены по типам, млн ฿</h3>
      <table>
        <tr><td style="color:var(--muted)">Тип</td><td class="r" style="color:var(--muted);font-weight:600">прайс 15.10</td><td class="r" style="color:var(--muted);font-weight:600">предпродажная цена</td></tr>
        <tr><td>Aria, 3 спальни<span style="%s"> · 5 вилл</span></td><td class="r num">67,7–73,1</td><td class="r num hl">57,5–62,1</td></tr>
        <tr><td>Kamala, 4 спальни<span style="%s"> · 4 виллы</span></td><td class="r num">157,7–178,9</td><td class="r num hl">134–152</td></tr>
        <tr><td>Andaman, 5 спален<span style="%s"> · 3 виллы</span></td><td class="r num">267,1–311,8</td><td class="r num hl">227–265</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Цена «от» по прайсу: Aria 67,7 млн ฿ (около %s), Kamala 157,7 млн ฿ (около %s), Andaman 267,1 млн ฿ (около %s). Предпродажная цена действует на ближайшие две сделки проекта, дальше цена по прайсу. Подберём виллу под задачу и уточним, осталась ли предпродажная цена.</p>
      <p class="src">Прайс застройщика AAG Development от 15.10.2026, цены в батах за виллу. Доллары по курсу сайта 35 ฿ за $, ориентир. Цены могут меняться без уведомления.</p></div>''' % (SM, SM, SM, usd(67.7e6), usd(157.7e6), usd(267.1e6)),
  ],
  'photos_title': 'Виллы снаружи и внутри',
  'photos': [
   {'src': 'img/r-aria.webp', 'alt': 'Naturale Kamala, вилла Aria, рендер застройщика', 'cap': 'Aria: терраса и бассейн'},
   {'src': 'img/i-aria-living.webp', 'alt': 'Вилла Aria, гостиная, рендер застройщика', 'cap': 'Aria: гостиная'},
   {'src': 'img/i-aria-master.webp', 'alt': 'Вилла Aria, главная спальня, рендер застройщика', 'cap': 'Aria: главная спальня'},
   {'src': 'img/r-kamala.webp', 'alt': 'Naturale Kamala, вилла Kamala, рендер застройщика', 'cap': 'Kamala: бассейн на верхней террасе'},
   {'src': 'img/i-kamala-living.webp', 'alt': 'Вилла Kamala, гостиная, рендер застройщика', 'cap': 'Kamala: гостиная'},
   {'src': 'img/i-kamala-master.webp', 'alt': 'Вилла Kamala, главная спальня, рендер застройщика', 'cap': 'Kamala: главная спальня'},
   {'src': 'img/i-andaman-pool.webp', 'alt': 'Вилла Andaman, гостиная и бассейн, рендер застройщика', 'cap': 'Andaman: гостиная и бассейн'},
   {'src': 'img/i-andaman-master.webp', 'alt': 'Вилла Andaman, главная спальня с видом на океан, рендер застройщика', 'cap': 'Andaman: спальня с видом'},
   {'src': 'img/i-andaman-spa.webp', 'alt': 'Вилла Andaman, спа, рендер застройщика', 'cap': 'Andaman: спа'},
  ],
  'photos_note': 'Рендеры застройщика, отделка может отличаться.',
  'plans_title': 'Планировки по этажам',
  'plans_cols': 2,
  'plans_pol': [
   {'src': 'img/pl-aria-1.webp', 'alt': 'Aria, первый этаж', 'cap': 'Aria, 1 этаж'},
   {'src': 'img/pl-aria-2.webp', 'alt': 'Aria, второй этаж', 'cap': 'Aria, 2 этаж'},
   {'src': 'img/pl-kamala-1.webp', 'alt': 'Kamala, первый этаж', 'cap': 'Kamala, 1 этаж'},
   {'src': 'img/pl-kamala-2.webp', 'alt': 'Kamala, второй этаж', 'cap': 'Kamala, 2 этаж'},
   {'src': 'img/pl-kamala-3.webp', 'alt': 'Kamala, третий этаж', 'cap': 'Kamala, 3 этаж'},
   {'src': 'img/pl-andaman-0.webp', 'alt': 'Andaman, цокольный этаж', 'cap': 'Andaman, цоколь'},
   {'src': 'img/pl-andaman-1.webp', 'alt': 'Andaman, первый этаж', 'cap': 'Andaman, 1 этаж'},
   {'src': 'img/pl-andaman-2.webp', 'alt': 'Andaman, второй этаж', 'cap': 'Andaman, 2 этаж'},
   {'src': 'img/pl-andaman-3.webp', 'alt': 'Andaman, третий этаж', 'cap': 'Andaman, 3 этаж'},
  ],
  'plans_src': 'Планировки застройщика, обновление 18.10.2026.',
 },
 'project': {
  'h2': 'Посёлок из 14 вилл у пляжа Камала',
  'lead': "Виллы стоят на склоне Millionaire's Mile. Застройщик называет это место «Beverly Hills of Asia» и описывает каждую виллу как личный мир для здоровья: бассейн с солёной водой, спа, спортзал, сауна и парная, террасы для загара. Набор зависит от типа виллы, он описан выше.",
  'big': {'src': 'img/aerial.webp', 'alt': 'Naturale Kamala, посёлок из 14 вилл на склоне, рендер застройщика', 'contain': False,
          'cap': "Посёлок на склоне Millionaire's Mile, рендер застройщика."},
  'cards': [
   '''<div class="card"><h3>Что входит в содержание посёлка</h3>
      <ul class="l">
        <li>Охрана 24 часа и видеонаблюдение</li>
        <li>Вывоз мусора</li>
        <li>Общее электричество и водоснабжение</li>
        <li>Уход за общим ландшафтным садом</li>
        <li>По желанию отдельно: чистка бассейна, садовник, горничная и обслуживание виллы</li>
      </ul>
      <p class="src">Прайс застройщика, 15.10.2026.</p></div>''',
   '''<div class="card"><h3>Взносы после покупки</h3>
      <table>
        <tr><td>Содержание, за м² участка в месяц</td><td class="r num">50 ฿</td></tr>
        <tr><td>Оплата содержания</td><td class="r num">за год вперёд</td></tr>
        <tr><td>Резервный фонд, за м² участка разово</td><td class="r num">500 ฿</td></tr>
        <tr><td>Электричество</td><td class="r num">по счётчику</td></tr>
        <tr><td>Вода</td><td class="r num">от проекта</td></tr>
      </table>
      <p class="src">Прайс застройщика, 15.10.2026. Электричество платится напрямую поставщику.</p></div>''',
  ],
  'plans': [],
 },
 'buy': {
  'h2': 'Бронь, договор и этапы стройки',
  'html': '''<div class="card" style="max-width:170mm"><table>
        <tr><td>Бронь (невозвратная)</td><td class="r num">2%</td></tr>
        <tr><td>Договор</td><td class="r num">28%</td></tr>
        <tr><td>Фундамент готов</td><td class="r num">20%</td></tr>
        <tr><td>Каркас готов</td><td class="r num">15%</td></tr>
        <tr><td>Кровля готова</td><td class="r num">15%</td></tr>
        <tr><td>Плитка пола и стен готова</td><td class="r num">10%</td></tr>
        <tr><td>Вилла готова, ключи</td><td class="r num">10%</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Пример для Aria по предпродажной цене 57,5 млн ฿: бронь 1 150 000 ฿, договор 16 100 000 ฿, вместе 30% и 17 250 000 ฿. Налоги и сборы при регистрации аренды застройщик и покупатель делят поровну. Если владелец меняется до сдачи, юридический сбор 200 000 ฿ за договор.</p>
      <p class="src">Условия оплаты: прайс застройщика, 15.10.2026. Застройщик может менять условия без уведомления.</p></div>'''
 },
 'step': {
  'eyebrow': 'Предпродажная цена',
  'h2': 'Как войти по цене на ближайшие две сделки',
  'items': [
   ['Сейчас', 'Выбираем виллу', 'подберём тип под вашу задачу и уточним, осталась ли предпродажная цена'],
   ['Бронь 2%', 'Невозвратный взнос', 'фиксирует виллу за вами'],
   ['Договор 28%', 'Подписание договора', 'вместе с бронью 30% от цены виллы'],
   ['4 этапа стройки', 'Фундамент, каркас, кровля, плитка', '20%, 15%, 15% и 10% по готовности этапа'],
   ['Ключи 10%', 'Вилла готова', 'последний платёж при передаче виллы'],
  ],
  'src': 'Прайс застройщика от 15.10.2026: предпродажная цена ограничена ближайшими двумя сделками. Срок сдачи в материалах застройщика не указан.',
 },
 'who': {
  'h2': 'Для жизни у океана',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><ul class="l">
      <li><b>Семье для жизни</b>: от 3 до 5 спален, у каждой спальни своя ванная и гардеробная, сад и бассейн на участке</li>
      <li><b>Тем, кто ценит вид</b>: у Andaman вид на океан, у Kamala частичный вид</li>
    </ul></div>
    <div class="card"><ul class="l">
      <li><b>Тем, кому нужен сервис</b>: застройщик предлагает обслуживание виллы, бассейна и сада, горничную</li>
      <li><b>Для сдачи в аренду</b>: застройщик предлагает услугу аренды по запросу</li>
    </ul></div>
  </div>
  <div class="card" style="margin-top:6mm"><h3>Наш взгляд</h3>
    <p style="margin:1.5mm 0 0;color:var(--ink2)">Это штучный продукт: всего 14 вилл, две уже проданы. По фактам застройщика сильные стороны такие: Millionaire's Mile у пляжа Камала, бассейн с солёной водой и сервис, у Kamala и Andaman спортзал, сауна и частный лифт, у Andaman ещё спа и кинозал. Что учесть: земля в лизхолде (договор аренды регистрируется в государственных органах), срока сдачи в материалах застройщика нет, поэтому уточним его до брони.</p>
    <p class="src">Прайс и брошюра застройщика, 2026.</p></div>'''
 },
 'income': {
  'h2': 'Аренда и сервис после покупки',
  'html': '''<div style="margin-top:5mm">
    <div class="card"><h3>Что предлагает застройщик</h3>
      <ul class="l">
        <li>Сервис виллы по желанию: чистка бассейна, уход за садом, горничная, обслуживание виллы</li>
        <li>Услуга аренды для арендаторов по запросу</li>
      </ul>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Прогноза доходности и ставок аренды в материалах застройщика нет, поэтому цифр не приводим.</p>
      <p class="src">Прайс застройщика, 15.10.2026.</p></div>
  </div>'''
 },
 'place': {
  'h2': "Камала: Millionaire's Mile рядом с пляжем",
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><h3>Дорога</h3>
      <table>
        <tr><td>Пляж Камала</td><td class="r num">рядом</td></tr>
        <tr><td>Аэропорт</td><td class="r num">25 км</td></tr>
      </table></div>
    <div class="card"><h3>Торговля и отдых</h3>
      <ul class="l">
        <li>Villa Market, Tops (24 часа), Boat Avenue, Central Phuket</li>
        <li>Cafe del Mar, Laguna Golf Club, Phuket Boat Lagoon, Royal Phuket Marina</li>
      </ul></div>
  </div>
  <div class="grid g2" style="align-items:start;margin-top:5mm">
    <div class="card"><h3>Школы</h3>
      <ul class="l">
        <li>HeadStart International School</li>
        <li>BCIS International School</li>
        <li>ISP International School</li>
        <li>British International School</li>
      </ul></div>
    <div class="card"><h3>Больницы</h3>
      <ul class="l">
        <li>Bumrungrad International Hospital</li>
        <li>Bangkok Hospital Clinic</li>
        <li>Wattanapat Hospital</li>
        <li>Bangkok Hospital</li>
      </ul></div>
  </div>
  <p class="src">Список мест рядом: брошюра застройщика. Расстояния застройщик не указывает.</p>
  <div class="photo" style="position:relative;left:0;top:0;width:100%;height:101mm;margin-top:5mm"><img src="img/map.webp" alt="Naturale Kamala на карте Пхукета, Камала и аэропорт"></div>
  <p class="src">Карта застройщика: Камала на западном побережье, до международного аэропорта 25 км.</p>'''
 },
 'developer': {
  'h2': 'AAG Development: виллы Naturale на Пхукете',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><h3>Застройщик</h3>
      <ul class="l">
        <li><b>AAG Development</b>: застройщик проектов Naturale Phuket</li>
        <li><b>Naturale Kamala</b>: 14 вилл на Millionaire's Mile, три типа Aria, Kamala и Andaman</li>
      </ul>
      <p class="src">Брошюра застройщика, 2026.</p></div>
    <div class="card"><h3>Награды застройщика</h3>
      <ul class="l">
        <li>Asia Pacific Property Awards 2026–2027, Award Winner</li>
        <li>PropertyGuru Thailand Property Awards 2025, Best Luxury Housing / Villa Development (Phuket)</li>
        <li>Dot Property Southeast Asia Awards 2025, Best Luxury Villa Development</li>
      </ul>
      <p class="src">Награды указаны в брошюре застройщика для Naturale Phuket Luxury Pool Villas.</p></div>
  </div>'''
 },
 'cta': '''<footer class="cta">
  <div class="ctahead">
    <div><div class="eyebrow">Следующий шаг</div><h2>Подберём виллу под вашу задачу</h2></div>
    <p>Покажем планировки и цену по каждой вилле, уточним, осталась ли предпродажная цена, и пришлём график платежей.</p>
  </div>
  <div class="links">
    <a class="main" href="%s"><b>Написать Эльнуру →</b><span>WhatsApp</span></a>
    <a href="https://t.me/elnurphuket_bot?start=naturale_offer"><b>Telegram</b><span>@elnurphuket_bot</span></a>
    <a href="https://property-library.com"><b>Сайт</b><span>каталог объектов</span></a>
    <a href="https://t.me/property_library_phuket"><b>Канал</b><span>новости рынка</span></a>
  </div>
  <div class="foot"><span>Property Library Phuket. Сопровождаем от выбора до ключей</span><span>По материалам застройщика, условия могут меняться.</span></div>
</footer>''' % WA,
 'tail': k['tail'],
}
json.dump(J, open(os.path.join(ROOT, 'offers/%s/sheet.json' % SLUG), 'w'), ensure_ascii=False, indent=1)
print('sheet.json готов', URL)
