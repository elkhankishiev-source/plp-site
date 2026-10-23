# -*- coding: utf-8 -*-
"""PURITA Phuket Bangtao: sheet.json листа-оффера. 23.10.2026.
Эльнур 23.10: «скинул инф по проекту пурита, ищи данные эталон и что ещё пишут в интернете, сделай презентацию офер, ссылку мне сюда скинь».
Источники (папка застройщика, группа «PLP | Developer info», 22.10):
  K = PURITA PROJECT SALES KIT FOR AGENT (CG Capital, 22.10.2026)
  N = AGENT NIGHT PURITA PROJECT 22 Oct 2026 (презентация вечера для агентов)
  P = Phuket Service Presentation (Plus Property, эксклюзивный агент проекта): диапазоны цен, прогноз аренды.
Комиссии, бонусы агентам, контакты отдела продаж застройщика в лист НЕ переносить.
Голова листа берётся с KUARTZ (тот же набор стилей), меняются заголовок, превью и адрес.
    python3 offers/purita/make_sheet.py && node tools/offer_sheet.mjs purita
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOMER = json.load(open(os.path.join(ROOT, 'build/nomera.json')))['purita']
URL = '/purita/' + NOMER
k = json.load(open(os.path.join(ROOT, 'offers/kuartz/sheet.json')))

head = k['head']
head = head.replace("location.replace('/kuartz'", "location.replace('%s'" % URL)
head = re.sub(r'<title>.*?</title>', '<title>PURITA · Банг Тао, CG Capital · Property Library Phuket</title>', head)
head = re.sub(r'(<meta property="og:title" content=")[^"]*', r'\1PURITA на Банг Тао: новый проект CG Capital', head)
head = re.sub(r'(<meta property="og:description" content=")[^"]*',
              r'\1Предложение Property Library Phuket: PURITA на Банг Тао от CG Capital (Central Group). Квартиры с мебелью, цены, условия оплаты, аренда по прогнозу управляющей компании', head)
head = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\1https://property-library.com' + URL, head)
head = re.sub(r'(<meta property="og:image" content=")[^"]*', r'\1https://property-library.com/offers/purita/img/preview-v10.jpg', head)
head = re.sub(r'@page\{size:210mm \d+mm', '@page{size:210mm 3000mm', head)
assert 'kuartz' not in head.lower(), 'в голове остался KUARTZ'

WA = 'https://wa.me/66955492587?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5%21%20%D0%98%D0%BD%D1%82%D0%B5%D1%80%D0%B5%D1%81%D0%B5%D0%BD%20PURITA%20%D0%BD%D0%B0%20%D0%91%D0%B0%D0%BD%D0%B3%20%D0%A2%D0%B0%D0%BE'

J = {
 'slug': 'purita',
 'pdf': 'PURITA_Bangtao.pdf',
 'head': head,
 'top': k['top'],
 'hero': '''<div class="hero" style="height:118mm">
  <div class="txt">
    <div class="eyebrow">Банг Тао · Central Group</div>
    <h1 style="font-size:46pt;white-space:normal;line-height:.95">PURITA<br><span>на Банг Тао</span></h1>
    <p class="sub">Первый собственный жилой проект Central Group на Пхукете. Сад 3 рай с бассейном 50 метров, квартиры с мебелью. Старт от 7,29 млн ฿, сдача в 2028.</p>
  </div>
  <div class="photo" style="left:90mm;top:24mm;width:112mm;height:76mm;transform:rotate(-1.5deg)"><img src="img/p-hero-air.webp" alt="PURITA, сад 3 рай и бассейн 50 м, рендер застройщика"></div>
  <div class="label" style="left:150mm;top:9mm;transform:rotate(6deg)">новый старт</div>
</div>''',
 'stats': '''<div class="stats">
  <div class="stat"><b>258</b><span>квартир и одна вилла</span></div>
  <div class="stat"><b>25</b><span>квартир на рай участка</span></div>
  <div class="stat"><b>50 м</b><span>бассейн в саду 3 рай</span></div>
  <div class="stat"><b>2028</b><span>сдача по плану</span></div>
</div>''',
 'units': {
  'h2': 'Квартиры с мебелью и потолками 3 метра',
  'lead': 'Три типа квартир и одна вилла на 5 спален. Больше половины проекта составляют 1-спальные. У части 2-спальных на первом этаже выход прямо в сад.',
  'facts': '''<div class="facts" style="grid-template-columns:repeat(4,1fr);margin:5mm 0 6mm">
    <div><b>10 рай</b><span>участок, 16 289 м²</span></div>
    <div><b>4 × 6</b><span>корпусов × этажей</span></div>
    <div><b>258</b><span>квартир</span></div>
    <div><b>125</b><span>парковочных мест</span></div>
  </div>''',
  'cards': [
   '''<div class="card"><h3>Цены по типам квартир</h3>
      <table>
        <tr><td>1-спальная<span style="color:var(--muted);font-size:7.6pt"> · 147 шт.</span></td><td class="r num">от 7,29 млн ฿</td></tr>
        <tr><td>2 спальни<span style="color:var(--muted);font-size:7.6pt"> · 78 шт.</span></td><td class="r num">14,69–16,49 млн ฿</td></tr>
        <tr><td>2 спальни плюс<span style="color:var(--muted);font-size:7.6pt"> · 32 шт.</span></td><td class="r num">19–21,9 млн ฿</td></tr>
        <tr><td>Вилла, 5 спален<span style="color:var(--muted);font-size:7.6pt"> · 1 шт.</span></td><td class="r num">по запросу</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Старт 1-спальных от 7,29 млн ฿, верхние лоты этого типа до 8,49 млн ฿. Подберём лот по стартовой цене.</p>
      <p class="src">Старт 7,29 млн: презентация застройщика 22.10.2026. Остальные диапазоны: презентация Plus Property, партнёра застройщика по продажам, октябрь 2026. Цены могут меняться.</p></div>''',
   '''<div class="card"><h3>Типы квартир и площади</h3>
      <table>
        <tr><td>1-спальная</td><td class="r num">56,4–58,4 м²</td></tr>
        <tr><td>2 спальни</td><td class="r num">93 м²</td></tr>
        <tr><td>2 спальни, выход в сад</td><td class="r num">103,5 м²</td></tr>
        <tr><td>2 спальни плюс</td><td class="r num">124,5 м²</td></tr>
        <tr><td>2 спальни плюс, выход в сад</td><td class="r num">136 м²</td></tr>
        <tr><td>Вилла, 5 спален</td><td class="r num">708 м²</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Высота потолка в гостиной и главной спальне 3 м, в остальных комнатах 2,65 м.</p>
      <p class="src">Площади и потолки: каталог продаж застройщика, слайды Factsheet и Specification.</p></div>'''
  ],
  'photos': [
   {'src': 'img/u-1br.webp', 'alt': 'PURITA, 1-спальная, гостиная, рендер застройщика', 'cap': '1-спальная · 56,4–58,4 м²'},
   {'src': 'img/u-bed.webp', 'alt': 'PURITA, спальня, рендер застройщика', 'cap': 'спальня с окном в сад'},
   {'src': 'img/u-2br.webp', 'alt': 'PURITA, 2 спальни, гостиная, рендер застройщика', 'cap': '2 спальни · 93–103,5 м²'},
   {'src': 'img/u-2brp.webp', 'alt': 'PURITA, 2 спальни плюс, гостиная, рендер застройщика', 'cap': '2 спальни плюс · 124,5–136 м²'}
  ],
  'plans_cols': 3,
  'plans_src': 'Планировки: каталог продаж застройщика. Варианты с выходом в сад 103,5 и 136 м² есть в каталоге, пришлём по запросу.',
  'plans_pol': [
   {'src': 'img/pl-1br.webp', 'alt': 'Планировка 1-спальной 56,4 м²', 'cap': '1-спальная · 56,4 м²'},
   {'src': 'img/pl-2br.webp', 'alt': 'Планировка 2-спальной 93 м²', 'cap': '2 спальни · 93 м²'},
   {'src': 'img/pl-2brp.webp', 'alt': 'Планировка 2 спальни плюс 124,5 м²', 'cap': '2 спальни плюс · 124,5 м²'}
  ]
 },
 'project': {
  'h2': 'Сад 3 рай, бассейн 50 метров, всё для жизни внутри',
  'lead': 'Название от тайского «бхурита», полнота: в комплексе есть всё нужное, чтобы не искать в другом месте. Фасады повторяют рябь песка и линию волны, на балконах дерево.',
  'big': {'src': 'img/p-pool.webp', 'alt': 'PURITA, бассейн 50 м во дворе, рендер застройщика', 'contain': False, 'cap': ''},
  'photos': [
   {'src': 'img/p-courtyard.webp', 'alt': 'PURITA, двор', 'cap': 'двор и бассейн'},
   {'src': 'img/p-lobby.webp', 'alt': 'PURITA, лобби', 'cap': 'лобби'},
   {'src': 'img/p-cowork.webp', 'alt': 'PURITA, коворкинг', 'cap': 'коворкинг'},
   {'src': 'img/p-gym.webp', 'alt': 'PURITA, фитнес', 'cap': 'фитнес с видом на сад'}
  ],
  'cards': [
   '''<div class="card"><h3>Инфраструктура</h3>
      <ul class="l">
        <li>Сад 3 рай, бассейн 50 м и бассейн-купель</li>
        <li>Лобби, лаунж и полуоткрытая терраса</li>
        <li>Коворкинг и переговорные</li>
        <li>Фитнес, раздевалки с паровыми комнатами</li>
        <li>Плотность 25 квартир на рай</li>
      </ul>
      <p class="src">Источник: каталог продаж застройщика.</p></div>''',
   '''<div class="card"><h3>Что входит в квартиру</h3>
      <ul class="l">
        <li>Мебель, кухня, шкафы и техника уже в цене</li>
        <li>Кухня: Gorenje, холодильник LG, мойка TEKA</li>
        <li>Сантехника Kohler, скрытые кондиционеры Mitsubishi</li>
        <li>Пол под дерево в комнатах, керамогранит в ванных</li>
      </ul>
      <p class="src">Источник: каталог продаж застройщика, слайд Specification; марки «или аналог».</p></div>''',
   '''<div class="card"><h3>Команда</h3>
      <ul class="l">
        <li>Застройщик: CG Capital, инвестиционная часть Central Group</li>
        <li>Архитектура: stu/D/O, ландшафт: Shma</li>
        <li>Продажи и сдача в аренду: Plus Property из группы Sansiri</li>
      </ul>
      <p class="src">Источники: каталог продаж застройщика; презентация Plus Property.</p></div>'''
  ],
  'plans': [
   {'src': 'img/mp.webp', 'alt': 'Мастер-план PURITA, первый этаж', 'contain': True,
    'cap': 'Мастер-план первого этажа, визуализация застройщика: корпуса A–D вокруг сада с бассейном, вилла в углу участка.'}
  ]
 },
 'buy': {
  'h2': 'Бронь, договор и оплата',
  'html': '''<div class="card" style="max-width:170mm"><table>
        <tr><td>Бронь, 1-спальная</td><td class="r num">100 000 ฿</td></tr>
        <tr><td>Бронь, 2 спальни и 2 спальни плюс</td><td class="r num">200 000 ฿</td></tr>
        <tr><td>Бронь, вилла</td><td class="r num">300 000 ฿</td></tr>
        <tr><td>При подписании договора</td><td class="r num">20%</td></tr>
        <tr><td>Взносы на время строительства</td><td class="r num">30%</td></tr>
        <tr><td>Остаток при передаче квартиры</td><td class="r num">50%</td></tr>
        <tr><td>Содержание, за м² в месяц</td><td class="r num">80 ฿</td></tr>
        <tr><td>Фонд проекта, за м² разово</td><td class="r num">600 ฿</td></tr>
      </table>
      <p class="src">Условия: каталог продаж застройщика, слайд Term payment. Остаток 50% посчитан нами как разница; график взносов пришлём по выбранной квартире.</p></div>'''
 },
 'step': {
  'eyebrow': 'Старт продаж',
  'h2': 'Как войти по стартовой цене',
  'items': [
   ['22 октября 2026', 'Презентация проекта', 'материалы у нас, подберём лот под вашу задачу'],
   ['конец ноября 2026', 'Первые продажи', 'бронируем лот до открытых продаж'],
   ['январь 2027', 'Шоу-юнит в POP Phuket', 'покажем квартиру вживую'],
   ['2028', 'Сдача', 'ключи, мебель уже в квартире, запуск аренды']
  ],
  'src': 'Источники: презентация CG Capital 10.10.2026 (первые продажи, шоу-юнит); каталог продаж застройщика 22.10.2026 (сдача: ноябрь 2028 в Factsheet, июнь 2028 в юридической справке того же каталога).'
 },
 'who': {
  'h2': 'Для жизни на Банг Тао и на долгий горизонт',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><ul class="l">
      <li><b>Семьям</b>: школа Headstart в 10 минутах, сад и бассейн во дворе</li>
      <li><b>На долгий сезон</b>: коворкинг, фитнес, торговый квартал POP Phuket рядом</li>
    </ul></div>
    <div class="card"><ul class="l">
      <li><b>Инвесторам вдолгую</b>: мебель в цене, сдача через управляющую Plus Property</li>
      <li><b>Тем, кто смотрит на марку</b>: первый собственный жилой проект Central Group на острове</li>
    </ul></div>
  </div>
  <div class="card" style="margin-top:6mm"><h3>Наш взгляд</h3>
    <p style="margin:1.5mm 0 0;color:var(--ink2)">Проект на долгий горизонт: сдача в 2028 году, и это не первая линия, до пляжа Банг Тао 1,5 км. Сильная сторона в том, что за проектом стоит Central Group. Плотность низкая, сад большой, мебель уже в цене. По юридической справке застройщика экологическое заключение получено, разрешение на строительство ещё оформляется. Документы проекта проверим для вас до брони.</p>
    <p class="src">Источник: юридическая справка в каталоге продаж застройщика.</p></div>'''
 },
 'income': {
  'h2': 'Аренда по прогнозу управляющей компании',
  'html': '''<div style="margin-top:5mm">
    <div class="card"><h3>Ожидаемая аренда в месяц</h3>
      <table>
        <tr><td>1-спальная · 56,4–58,4 м²</td><td class="r num">50–60 тыс. ฿</td></tr>
        <tr><td>2 спальни · 93–103,5 м²</td><td class="r num">80–90 тыс. ฿</td></tr>
        <tr><td>2 спальни плюс · 124,5–136 м²</td><td class="r num">100–120 тыс. ฿</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Доходность по их оценке 8–12% в год. Это прогноз компании, которая будет сдавать квартиры, гарантии нет. Свой расчёт по лоту сделаем с учётом содержания и налогов.</p>
      <p class="src">Источник: презентация Plus Property (группа Sansiri), Expected rental rate, октябрь 2026.</p></div>
  </div>'''
 },
 'place': {
  'h2': 'Банг Тао: центр района Чернгталай',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><h3>Рядом с проектом</h3>
      <ul class="l">
        <li>POP Phuket, торговый квартал Central, по соседству</li>
        <li>Boat Avenue 500 м, парк и площадка 300 м</li>
        <li>Porto de Phuket 900 м</li>
        <li>Клиника Bangkok Phuket Laguna 1 км</li>
      </ul></div>
    <div class="card"><h3>Дорога</h3>
      <ul class="l">
        <li>Пляж Банг Тао 1,5 км</li>
        <li>Гольф Laguna 2,5 км</li>
        <li>Школа Headstart 10 мин, UWC 20 мин</li>
        <li>Больница Bumrungrad 30 мин</li>
      </ul></div>
  </div>
  <div class="facts" style="grid-template-columns:repeat(4,1fr);margin-top:6mm">
    <div><b>1,5 км</b><span>пляж Банг Тао</span></div>
    <div><b>2,5 км</b><span>гольф Laguna</span></div>
    <div><b>25 мин</b><span>аэропорт</span></div>
    <div><b>30 мин</b><span>Пхукет-таун</span></div>
  </div>
  <p class="src">Расстояния и время на машине: каталог продаж застройщика, слайд Neighborhood.</p>
  <div class="photo" style="position:relative;left:0;top:0;width:100%;height:101mm;margin-top:5mm;background:#fff"><img style="object-fit:contain" src="img/map.webp" alt="PURITA на карте Банг Тао"></div>
  <p class="src">Карта застройщика: проект на дороге Пасак–Коктанод, по соседству POP Phuket, чуть дальше Boat Avenue.</p>'''
 },
 'market': {
  'eyebrow': 'Рынок',
  'h2': 'Банг Тао в цифрах',
  'html': '''<div class="facts" style="grid-template-columns:repeat(4,1fr);margin-top:3mm">
    <div><b>82%</b><span>загрузка отелей Банг Тао и Чернгталая</span></div>
    <div><b>+20%</b><span>к средней цене номера</span></div>
    <div><b>17,2 млн</b><span>пассажиров аэропорта в 2026, 70% иностранцы</span></div>
    <div><b>115 000</b><span>иностранцев на визах LTR и DTV</span></div>
  </div>
  <p style="margin-top:4mm;color:var(--ink2);max-width:160mm">На подходе крупные открытия: POP Phuket в 2026, больница Bumrungrad в 2027, школа North London Collegiate в 2028. Район всё больше живёт круглый год, а не только в сезон.</p>
  <p class="src">Источник: презентация застройщика, 22.10.2026; первоисточники цифр в ней не названы.</p>'''
 },
 'developer': {
  'h2': 'CG Capital: жилые проекты Central Group',
  'html': '''<div class="grid g64" style="align-items:start">
    <div class="card"><h3>Компания</h3>
      <ul class="l">
        <li><b>Central Group</b>: семейная группа Чиратхиват, первый магазин в Бангкоке в 1947 году. Сегодня больше 100 универмагов и торговых центров, на Пхукете 7 торговых объектов, среди них Central Phuket, и 7 отелей.</li>
        <li><b>CG Capital</b>: инвестиционная часть группы. Строит брендированные резиденции вместе с гостиничными марками; объём проектов, по данным компании, больше 20 млрд ฿.</li>
        <li><b>The Standard Residences, Банг Тао</b>: продано 90%. По прайсу застройщика на 20.10 свободно 19 квартир из 188.</li>
        <li><b>InterContinental Residences Bangkok Asoke</b>: продано 60%.</li>
        <li><b>PURITA</b>: первый проект компании на Пхукете под собственной маркой, без гостиничного бренда.</li>
      </ul>
      <p class="src">Источники: презентация застройщика 22.10.2026; прайс The Standard на 20.10.2026; Central Group, Википедия.</p></div>
    <div class="card"><h3>Проекты</h3>
      <ul class="l">
        <li>The Standard Residences, Банг Тао: сдача в конце 2026</li>
        <li>InterContinental Residences, Бангкок</li>
        <li>Andaz на Лаяне: старт продаж в I квартале 2027</li>
        <li>POP Phuket, торговый квартал на Банг Тао</li>
      </ul></div>
  </div>
  <div class="pgrid">
    <div class="pol" style="transform:rotate(-.6deg)"><img src="img/cg-standard.webp" alt="The Standard Residences Phuket Bang Tao"><i>The Standard, Банг Тао</i></div>
    <div class="pol" style="transform:rotate(.5deg)"><img src="img/cg-ic.webp" alt="InterContinental Residences Bangkok Asoke"><i>InterContinental, Бангкок</i></div>
    <div class="pol" style="transform:rotate(.4deg)"><img src="img/pop.webp" alt="POP Phuket"><i>POP Phuket</i></div>
    <div class="pol" style="transform:rotate(-.5deg)"><img src="img/u-villa2.webp" alt="PURITA, вилла"><i>вилла PURITA, 708 м²</i></div>
  </div>'''
 },
 'cta': '''<footer class="cta">
  <div class="ctahead">
    <div><div class="eyebrow">Следующий шаг</div><h2>Лот до открытых продаж</h2></div>
    <p>Подберём квартиру в PURITA под вашу задачу, уточним стартовую цену по лоту и пришлём график платежей.</p>
  </div>
  <div class="links">
    <a class="main" href="%s"><b>Написать Эльнуру →</b><span>WhatsApp</span></a>
    <a href="https://t.me/elnurphuket_bot?start=purita_offer"><b>Telegram</b><span>@elnurphuket_bot</span></a>
    <a href="https://property-library.com"><b>Сайт</b><span>каталог объектов</span></a>
    <a href="https://t.me/property_library_phuket"><b>Канал</b><span>новости рынка</span></a>
  </div>
  <div class="foot"><span>Property Library Phuket. Сопровождаем от выбора до ключей</span><span>По материалам застройщика, условия могут меняться.</span></div>
</footer>''' % WA,
 'tail': k['tail'],
}
json.dump(J, open(os.path.join(ROOT, 'offers/purita/sheet.json'), 'w'), ensure_ascii=False, indent=1)
print('sheet.json готов', URL)
