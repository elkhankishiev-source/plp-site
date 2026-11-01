# -*- coding: utf-8 -*-
"""The Title Katabello: sheet.json листа-оффера. 01.11.2026.
Эльнур 01.11 ~12:55: «отправь ту же презу, только PDF, со всеми отсылками на нас и наше! Превью тоже должен быть корректный»;
«не выдумывай, только из источников застройщика и наших».
Источники:
  P  = KAT Price list V.3 от 30.10.26 (~/tg_prices): цены свободных квартир, обслуживание 80 ฿/м² в месяц, фонд 800 ฿/м²
  P0 = KAT Price list P.1 V.2 от 26.06.26 (~/tg_prices/backfill): 1 спальня 28 м² стоила 4 620 000 ฿ (рост к 30.10 +5%)
  B  = 20250401_Katabello_E - Brochure.pdf (Диск, материалы_проекта): участок, корпуса, 760 квартир, 20 зон, расстояния,
       планировки (стр. 25), что входит в квартиру (стр. 26), карта (стр. 7)
  F707 = сверка платежей застройщика: бронь 100 000, 25% при договоре, 25% и 25% во время стройки, 25% при сдаче
  Эльнур 01.11: сдача «ориентировочно 4 квартал 2027»; решение №359 (что входит в цену); скидки только в личку, на лист НЕ писать.
НЕ писать: даты сдачи из брошюры (Q2/June 2027), скидки, номера юнитов, комиссии, «на руки», контакты застройщика.
«700 м до пляжа Ката» в брошюре НЕТ (700 м там у Karon Plaza): на листе только расстояния из брошюры.
Доходность: канон 75 (ориентир 6–12% годовых), цифры 7% и сезонные ставки карточки без источника застройщика не берём.
    python3 offers/katabello/make_sheet.py && node tools/offer_sheet.mjs katabello
"""
import json, os, re
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLUG = 'katabello'
NOMER = json.load(open(os.path.join(ROOT, 'build/nomera.json')))[SLUG]
URL = '/%s/%s/' % (SLUG, NOMER)
PREVIEW = 'preview-v1.jpg'
k = json.load(open(os.path.join(ROOT, 'offers/kuartz/sheet.json')))

head = k['head']
head = head.replace("location.replace('/kuartz'", "location.replace('%s'" % URL)
head = re.sub(r'<title>.*?</title>', '<title>The Title Katabello · Ката, квартиры у пляжа · Property Library Phuket</title>', head)
head = re.sub(r'(<meta property="og:title" content=")[^"]*', r'\1The Title Katabello: квартиры у пляжа Ката от 4,85 млн ฿', head)
head = re.sub(r'(<meta property="og:description" content=")[^"]*',
              r'\1Предложение Property Library Phuket: квартиры с ремонтом, 20 зон отдыха, бронь 100 000 ฿ и оплата четырьмя частями до сдачи без процентов. Цены, планировки, сроки', head)
head = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\1https://property-library.com' + URL, head)
head = re.sub(r'(<meta property="og:image" content=")[^"]*', r'\1https://property-library.com/offers/%s/img/%s' % (SLUG, PREVIEW), head)
head = re.sub(r'(<meta name="description" content=")[^"]*',
              r'\1The Title Katabello у пляжа Ката: квартиры с ремонтом от 4 851 000 ฿, бронь 100 000 ฿, оплата до сдачи без процентов. Предложение Property Library Phuket.', head)
assert 'kuartz' not in head.lower(), 'в голове остался KUARTZ'

WA = 'https://wa.me/66955492587?text=' + quote('Здравствуйте! Интересен Katabello на Кате')

J = {
 'slug': SLUG,
 'pdf': 'Katabello_Kata.pdf',
 'head': head,
 'top': k['top'].replace('по презентации застройщика', 'по прайсу и брошюре застройщика'),
 'hero': '''<div class="hero" style="height:118mm">
  <div class="txt">
    <div class="eyebrow">Ката · The Title</div>
    <h1 style="font-size:44pt;white-space:normal;line-height:.95">The Title<br><span>Katabello</span></h1>
    <p class="sub">Квартира с ремонтом у пляжа Ката от 4 851 000 ฿ (около 144 тыс. $ по курсу ЕЦБ). Бронь 100 000 ฿, дальше четыре платежа по 25% до сдачи, без процентов.</p>
  </div>
  <div class="photo" style="left:90mm;top:24mm;width:112mm;height:76mm;transform:rotate(-1.5deg)"><img src="img/hero.webp" alt="The Title Katabello, корпуса и бассейн, рендер застройщика"></div>
  <div class="label" style="left:150mm;top:9mm;transform:rotate(6deg)">рассрочка 0%</div>
</div>''',
 'stats': '''<div class="stats">
  <div class="stat"><b>760</b><span>квартир, 8 корпусов по 7 этажей</span></div>
  <div class="stat"><b>20</b><span>зон отдыха, онсэн и сауна</span></div>
  <div class="stat"><b>25%</b><span>первый взнос, остальное до сдачи</span></div>
  <div class="stat"><b>IV кв. 2027</b><span>сдача, ориентировочно</span></div>
</div>''',
 'units': {
  'h2': 'Восемь типов квартир от 28 до 168 м²',
  'lead': 'Квартиры сдаются с полным ремонтом: сантехника, кондиционеры, встроенная кухня с варочной панелью и вытяжкой, шкафы, водонагреватель, шторы. Мебель и техника в цену не входят.',
  'facts': '''<div class="facts" style="grid-template-columns:repeat(4,1fr);margin:5mm 0 6mm">
    <div><b>23 606 м²</b><span>участок</span></div>
    <div><b>8 корпусов</b><span>по 7 этажей</span></div>
    <div><b>760</b><span>квартир</span></div>
    <div><b>2,6–2,75 м</b><span>высота потолков</span></div>
  </div>''',
  'cards': ['''<div class="card"><h3>Цены свободных квартир</h3>
      <table>
        <tr><td>1 спальня · 28 м²</td><td class="r num">4 851 000 ฿</td></tr>
        <tr><td>1 спальня · 37 м²</td><td class="r num">5 827 500–6 449 100 ฿</td></tr>
        <tr><td>1 спальня · 41 м²</td><td class="r num">6 242 250–6 371 400 ฿</td></tr>
        <tr><td>1 спальня плюс · 47 м²</td><td class="r num">7 303 800–8 290 800 ฿</td></tr>
        <tr><td>1 спальня плюс · 54–56 м²</td><td class="r num">8 937 600–9 922 500 ฿</td></tr>
        <tr><td>1 спальня плюс · 61 м²</td><td class="r num">10 632 300–11 208 750 ฿</td></tr>
        <tr><td>Пентхаус 2–3 спальни · 100–138 м²</td><td class="r num">13 965 000–21 300 300 ฿</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Цена зависит от корпуса, этажа и вида. 1 спальня 28 м² в долларах около 144 тыс. $ по курсу ЕЦБ.</p>
      <p class="src">Прайс застройщика, цены в батах.</p></div>'''],
  'photos': [
   {'src': 'img/i-living.webp', 'alt': 'Katabello, гостиная с кухней', 'cap': 'гостиная и кухня'},
   {'src': 'img/i-bed.webp', 'alt': 'Katabello, спальня', 'cap': 'спальня'},
   {'src': 'img/i-sofa.webp', 'alt': 'Katabello, зона отдыха', 'cap': 'зона отдыха'},
   {'src': 'img/i-dining.webp', 'alt': 'Katabello, кухня и столовая', 'cap': 'кухня и столовая'},
   {'src': 'img/i-bath.webp', 'alt': 'Katabello, ванная', 'cap': 'ванная'},
   {'src': 'img/show.webp', 'alt': 'Katabello, 1 спальня', 'cap': '1 спальня'},
  ],
  'photos_note': 'Интерьеры застройщика: мебель и декор показаны для примера.',
  'plans_title': 'Планировки',
  'plans_pol': [
   {'src': 'img/pl-28.webp', 'alt': 'Планировка 1 спальня 28 м²', 'cap': '1 спальня · 28 м²'},
   {'src': 'img/pl-37.webp', 'alt': 'Планировка 1 спальня 37 м²', 'cap': '1 спальня · 37 м²'},
   {'src': 'img/pl-41.webp', 'alt': 'Планировка 1 спальня 41 м²', 'cap': '1 спальня · 41 м²'},
   {'src': 'img/pl-47.webp', 'alt': 'Планировка 1 спальня плюс 47 м²', 'cap': '1 спальня плюс · 47 м²'},
   {'src': 'img/pl-56.webp', 'alt': 'Планировка 1 спальня плюс 56 м²', 'cap': '1 спальня плюс · 56 м²'},
  ],
  'plans_cols': 3,
  'plans_src': 'Планировки из брошюры застройщика.',
 },
 'buy': {
  'h2': 'Бронь 100 000 ฿ и четыре платежа по 25%',
  'html': '''<div class="grid g64" style="align-items:start">
    <div class="card"><h3>График платежей</h3>
      <table>
        <tr><td>Бронь</td><td class="r num">100 000 ฿</td></tr>
        <tr><td>Договор, в течение месяца после брони</td><td class="r num">25%</td></tr>
        <tr><td>Во время стройки</td><td class="r num">25%</td></tr>
        <tr><td>Во время стройки</td><td class="r num">25%</td></tr>
        <tr><td>При сдаче, за вычетом брони</td><td class="r num">25%</td></tr>
      </table>
      <div style="margin:3.5mm 0 0;background:var(--sun);border-radius:2mm;padding:3mm 3.5mm;font-size:9.4pt;font-weight:700;color:var(--ink)">Рассрочка на период строительства без процентов и без удорожания.</div>
      <p class="src">Условия оплаты застройщика.</p></div>
    <div class="pol" style="transform:rotate(.5deg)"><img style="height:70mm" src="img/gate.webp" alt="Katabello, въезд, рендер застройщика"><i>въезд в комплекс</i></div>
  </div>'''
 },
 'step': {
  'eyebrow': 'Ваш шаг',
  'h2': 'Как войти по текущему прайсу',
  'items': [
   ['июнь → октябрь', 'Прайс уже вырос на 5%', '1 спальня 28 м²: было 4 620 000 ฿, стало 4 851 000 ฿'],
   ['сейчас', 'Бронь 100 000 ฿', 'фиксируем квартиру по текущему прайсу'],
   ['в течение месяца', 'Договор и первый взнос 25%', 'дальше два платежа по 25% во время стройки'],
   ['IV квартал 2027', 'Сдача, ориентировочно', 'оставшиеся 25% и ключи от квартиры с ремонтом'],
  ],
  'src': 'Прайсы и условия оплаты застройщика.'
 },
 'who': {
  'h2': 'Кому подойдёт квартира у пляжа Ката',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><ul class="l">
      <li><b>Инвесторам</b>: вход от 4,85 млн ฿ и оплата частями до сдачи</li>
      <li><b>С питомцами</b>: свой бассейн и площадка для питомцев, груминг</li>
    </ul></div>
    <div class="card"><ul class="l">
      <li><b>Семьям</b>: детская комната, игровая, бассейн с горками</li>
      <li><b>Тем, кто работает удалённо</b>: коворкинг и переговорная</li>
    </ul></div>
  </div>
  <div class="card" style="margin-top:6mm"><h3>Наш взгляд</h3>
    <p style="margin:1.5mm 0 0;color:var(--ink2)">Сильная сторона Katabello во входе: квартира с ремонтом у пляжа Ката от 4,85 млн ฿ и оплата четырьмя частями до сдачи без процентов. С июня прайс на 1 спальню 28 м² вырос на 5%.</p>
    <p class="src">Прайс застройщика.</p></div>'''
 },
 'income': {
  'h2': 'Ориентир доходности 6–12% годовых',
  'html': '''<div class="grid g64" style="align-items:start">
    <div class="card" style="background:var(--sage);border-color:var(--sage)"><h3>Доход и расходы владельца</h3>
      <p style="margin:1mm 0 3mm;color:var(--ink2)">Ориентир доходности квартир на Пхукете 6–12% годовых. Точную цифру считаем по выбранной квартире: тип, этаж и вид.</p>
      <table>
        <tr><td style="color:var(--muted)">площадь</td><td class="r" style="color:var(--muted);font-weight:600">обслуживание в месяц</td><td class="r" style="color:var(--muted);font-weight:600">фонд разово</td></tr>
        <tr><td>28 м²</td><td class="r num">2 240 ฿</td><td class="r num">22 400 ฿</td></tr>
        <tr><td>37 м²</td><td class="r num">2 960 ฿</td><td class="r num">29 600 ฿</td></tr>
        <tr><td>47 м²</td><td class="r num">3 760 ฿</td><td class="r num">37 600 ฿</td></tr>
        <tr><td>56 м²</td><td class="r num">4 480 ฿</td><td class="r num">44 800 ฿</td></tr>
      </table>
      <p style="margin:3mm 0 0;color:var(--ink2);font-size:9pt">Обслуживание 80 ฿ за м² в месяц, фонд 800 ฿ за м² при приёмке.</p>
      <p class="src">Ориентир Property Library Phuket; ставки по прайсу застройщика, расчёт наш.</p></div>
    <div class="pol" style="transform:rotate(-.5deg)"><img style="height:78mm" src="img/sunset.webp" alt="Katabello, бассейн с пляжной зоной, рендер застройщика"><i>бассейн с пляжной зоной</i></div>
  </div>'''
 },
 'project': {
  'h2': '20 зон отдыха: 7 под открытым небом и 13 внутри',
  'lead': 'Курортный кондоминиум в средиземноморском стиле: бассейны-лагуны с пляжной зоной и горками, онсэн, сауна и паровая, большой фитнес с боксёрским рингом, кинозал и сёрф-кафе.',
  'big': {'src': 'img/lagoon.webp', 'alt': 'Katabello, бассейны-лагуны, рендер застройщика', 'contain': False, 'cap': ''},
  'photos': [
   {'src': 'img/oasis.webp', 'alt': 'Katabello, бассейн с островом', 'cap': 'бассейн с островом'},
   {'src': 'img/slides.webp', 'alt': 'Katabello, бассейн с горками', 'cap': 'бассейн с горками'},
   {'src': 'img/pet.webp', 'alt': 'Katabello, бассейн для питомцев', 'cap': 'бассейн для питомцев'},
   {'src': 'img/library.webp', 'alt': 'Katabello, библиотека', 'cap': 'библиотека'},
   {'src': 'img/surf.webp', 'alt': 'Katabello, детская зона', 'cap': 'детская зона'},
   {'src': 'img/gazebo.webp', 'alt': 'Katabello, сад и ротонда', 'cap': 'сад и ротонда'},
  ],
  'cards': ['''<div class="card"><h3>Инфраструктура</h3>
      <ul class="l">
        <li>Онсэн, сауна, паровая, йога</li>
        <li>Фитнес и боксёрский ринг</li>
        <li>Кинозал, библиотека, игровая</li>
        <li>Коворкинг и переговорная</li>
        <li>Детская комната, сёрф-кафе, лаунж</li>
        <li>Бассейн и площадка для питомцев, груминг</li>
      </ul></div>''', '''<div class="card"><h3>Проект в цифрах</h3>
      <ul class="l">
        <li>Участок 23 606 м²</li>
        <li>8 жилых корпусов по 7 этажей, 760 квартир</li>
        <li>350 мест на парковке, 5 с зарядкой</li>
        <li>80 мест для мотобайков</li>
      </ul>
      <p class="src">Брошюра застройщика.</p></div>'''],
  'plans_title': 'Мастер-план',
  'plans': [{'src': 'img/mp.webp', 'alt': 'Мастер-план Katabello, первый этаж', 'contain': True, 'cap': 'Мастер-план первого этажа, визуализация застройщика.'}],
 },
 'place': {
  'h2': 'Ката: в нескольких минутах от пляжа',
  'html': '''<div class="grid g2" style="align-items:start">
    <div class="card"><h3>Рядом с проектом</h3>
      <ul class="l">
        <li>Club Med Phuket, 950 м</li>
        <li>Пешеходная улица Каты у пляжа, 1,2 км</li>
        <li>Клиника HealthPlus, 1 км</li>
        <li>Больница Карона, 1,7 км</li>
      </ul></div>
    <div class="card"><h3>Школы и гольф</h3>
      <ul class="l">
        <li>Международная школа BCIS, 8 км</li>
        <li>Международная школа Ruamrudee, 9 км</li>
        <li>Гольф-клуб Phuket Country Club, 15 км</li>
      </ul></div>
  </div>
  <div class="facts" style="grid-template-columns:repeat(4,1fr);margin-top:6mm">
    <div><b>3 км</b><span>пляж Карон</span></div>
    <div><b>10 км</b><span>пляж Най Харн</span></div>
    <div><b>11 км</b><span>Патонг</span></div>
    <div><b>15 км</b><span>старый город Пхукета</span></div>
  </div>
  <p class="src">Расстояния по брошюре застройщика.</p>
  <div class="photo" style="position:relative;left:0;top:0;width:100%;height:101mm;margin-top:5mm;background:#fff"><img style="object-fit:contain" src="img/map.webp" alt="Katabello на карте Каты"></div>
  <p class="src">Карта застройщика.</p>'''
 },
 'developer': {
  'h2': 'The Title уже сдал Heritage, Legendary, Halo и Serenity',
  'html': '''<div class="grid g64" style="align-items:start">
    <div class="card"><h3>Застройщик</h3>
      <ul class="l">
        <li><b>The Title</b>: бренд компании Rhom Bho Property из группы AssetWise, акции группы торгуются на бирже Таиланда.</li>
        <li><b>2024</b>: PropertyGuru Thailand Property Awards назвали Rhom Bho лучшим застройщиком Пхукета.</li>
      </ul>
      <p class="src">Материалы застройщика.</p></div>
    <div class="card"><h3>Сданные проекты</h3>
      <ul class="l">
        <li>Heritage, Банг Тао</li>
        <li>Legendary, Банг Тао</li>
        <li>Halo, Най Янг</li>
        <li>Serenity, Най Янг</li>
      </ul></div>
  </div>
  <div class="pgrid c3">
    <div class="pol" style="transform:rotate(-.6deg)"><img src="img/t-legendary.webp" alt="The Title Legendary Bang-Tao"><i>Legendary, Банг Тао</i></div>
    <div class="pol" style="transform:rotate(.5deg)"><img src="img/t-heritage.webp" alt="The Title Heritage Bang-Tao"><i>Heritage, Банг Тао</i></div>
    <div class="pol" style="transform:rotate(.4deg)"><img src="img/t-serenity.webp" alt="The Title Serenity Naiyang"><i>Serenity, Най Янг</i></div>
  </div>'''
 },
 'cta': '''<footer class="cta">
  <div class="ctahead">
    <div><div class="eyebrow">Следующий шаг</div><h2>Расчёт по вашей квартире</h2></div>
    <p>Подберём квартиру в Katabello под ваш бюджет и пришлём график платежей по выбранному лоту.</p>
  </div>
  <div class="links">
    <a class="main" href="%s"><b>Написать Эльнуру →</b><span>WhatsApp</span></a>
    <a href="https://t.me/elnurphuket_bot?start=katabello_offer"><b>Telegram</b><span>@elnurphuket_bot</span></a>
    <a href="https://property-library.com/object/katabello"><b>Сайт</b><span>карточка проекта</span></a>
    <a href="https://t.me/property_library_phuket"><b>Канал</b><span>новости рынка</span></a>
  </div>
  <div class="foot"><span>Property Library Phuket. Сопровождаем от выбора до ключей</span><span>По прайсу и брошюре застройщика.</span></div>
</footer>''' % WA,
 'tail': k['tail'],
}
json.dump(J, open(os.path.join(ROOT, 'offers/%s/sheet.json' % SLUG), 'w'), ensure_ascii=False, indent=1)
print('sheet.json готов', URL)
