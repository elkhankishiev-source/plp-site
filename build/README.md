# build/gen.mjs — генератор сайта из Supabase («одна истина»)

Каталог на главной и отдельные страницы объектов генерируются из Supabase,
а не правятся руками.

## Вся сборка одной командой

```bash
node build/all.mjs
```

Порядок: `gen` (данные и страницы объектов) → `mkpages` → `mkdistricts` →
`mkextra` → `mkshared` (шапка, меню, подвал, общий CSS из `build/parts`) →
`mktheme` (цвет системных полей браузера и фон `<html>` на КАЖДОЙ странице —
без него при прокрутке и оттягивании светит чужой цвет и кажется, что фон мигает).

Правится только `index.html`, `owner.html` и файлы в `build/parts`. Остальные
страницы собираются — руками их не трогаем, иначе правки затрутся.


## Как перезапустить (когда объект изменился в базе)

```bash
node build/gen.mjs
```

Ничего ставить не нужно — только Node (встроенные `fetch`/`fs`, без npm).

Что делает один прогон:
1. Читает `objects` WHERE `on_site=true` + `rental_benchmarks` из Supabase REST.
2. Впечатывает свежий `PL.PROPERTIES` в `index.html` **между маркерами**
   `PLP:AUTO-CATALOG:START` / `PLP:AUTO-CATALOG:END` (остальной код не трогает —
   фильтры, калькулятор, чат, карта остаются как есть).
3. Генерит `object/<slug>.html` на каждый объект (slug из `plp_property_id`:
   `PLP-HERITAGE` → `object/heritage.html`). Каждая страница самодостаточна:
   тёмная тема сайта, фото, характеристики, диапазон доходности, описание,
   кнопки WhatsApp + «Смотреть на сайте», og-теги и JSON-LD (`Residence`+`Product`)
   для отдельной индексации в Google.
4. Перегенерит `sitemap.xml` (главная + якоря + все страницы объектов).

После прогона — `git add index.html object/ sitemap.xml build/`, commit, push.

## Ключ Supabase — НЕ в репозитории

Ключ читается в момент запуска (в порядке приоритета):
1. переменные окружения `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`;
2. локальный файл `~/.plp_site_supabase.env` (по строкам `KEY=VALUE`),
   либо путь в `PLP_SB_ENV`.

Файл `~/.plp_site_supabase.env` лежит **вне** репозитория и в git не попадает.
Значения берутся из n8n variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
Никогда не коммитить ключ в `index.html`, `build/` или любой файл репозитория.

Пример локального файла (значения — свои, не коммитить):
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-key>
```

## Какие поля откуда (важно для «одной истины»)

**Из Supabase (objects):** `title`(name), `loc`(district + RU-словарь),
`type`, `priceUSD`/priceTHB(price_from_thb), `beds`(bedrooms_min/max, Studio=0),
`area`(area_min/max), `roi`, `deadline`(handover_date), `status`, `desc`(usp),
фото `img/<id>.jpg`. Диапазон доходности на страницах — из `rental_benchmarks`
по (district, type) с фолбэком на (district, Кондо) → 6–12%.

**НЕ из Supabase — сохраняются из текущего `index.html` по `property_id`
между прогонами** (в базе этих данных в нужной форме нет, и они питают
калькулятор — их нельзя терять):
- `calc` — движок калькулятора (посезонные ставки high/shoulder/low,
  `handoverTHB`, `buildYears`, `capexM2`, `metersTHB`, `mgmtPct`, occ и т.д.);
- `grad` — цветовой градиент карточки (косметика);
- `budget` — тир бюджета для фильтра.

Генератор каждый прогон **перечитывает** эти поля из блока между маркерами и
переносит в новый каталог. Значит, ручную донастройку `calc` можно делать прямо
в `index.html` между маркерами (только сами `calc`/`grad`/`budget`) — она
переживёт следующую перегенерацию. Всё остальное в блоке — производное от
Supabase, править руками бессмысленно (перезатрётся).

Для нового объекта, которого ещё нет в `index.html`, генератор строит `calc`
из Supabase (`season_rates`/`occupancy_est_pct`, `estimated:true`) — черновой,
его стоит потом донастроить вручную.

### Маппинг статуса
`active → available`, `archived → reserved`, `sold → sold`.

## Известные хвосты
- `usp` объекта **PLP-MODEVA** в базе содержит опечатку («Банgtao» вместо
  «Бангтао») — она теперь видна и в каталоге, и на странице объекта. Фиксить
  в Supabase (`objects.usp`), затем перезапустить генератор.
- Опционально: живой fetch каталога из Supabase без пересборки (сейчас данные
  «запекаются» в статические файлы при `node build/gen.mjs`).

## Общие части сайта и кабинета (06.09.2026)

Шапка, мобильное меню и подвал лежат в `build/parts/` и вставляются в страницы
между маркерами `<!-- PLP:HEADER:START/END -->`, `MNAV`, `FOOTER`.

- правим **только** файл в `build/parts/`, потом `node build/mkshared.mjs`;
- различия страниц задаются метками: `<!--SWITCH-->` (тумблер Сайт/Кабинет)
  и `<!--MNAV-LINK-->` (пункт меню) — их подставляет сборщик по варианту
  `site` или `cabinet`;
- колокольчик лежит в общей шапке скрытым, кабинет показывает его сам.

Порядок полной пересборки: `mkshared` → `gen` → `mkpages` → `mkdistricts` → `mkextra`.
