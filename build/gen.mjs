#!/usr/bin/env node
/**
 * PLP site generator — «одна истина» из Supabase.
 *
 * Что делает:
 *   1. Читает objects WHERE on_site=true из Supabase REST (+ rental_benchmarks).
 *   2. Впечатывает свежий каталог PL.PROPERTIES в index.html между маркерами
 *      PLP:AUTO-CATALOG:START / END (остальной код index.html не трогает).
 *   3. Генерит самодостаточные страницы object/<slug>.html (SEO: og + JSON-LD).
 *   4. Перегенерит sitemap.xml (главная + все страницы объектов).
 *
 * Ключ Supabase НЕ хранится в репозитории. Берётся (в порядке приоритета):
 *   - переменные окружения SUPABASE_URL / SUPABASE_SERVICE_KEY;
 *   - локальный файл ~/.plp_site_supabase.env (KEY=VALUE построчно),
 *     либо путь в переменной PLP_SB_ENV.
 *
 * Запуск:  node build/gen.mjs
 *
 * ВАЖНО про источники полей (см. build/README.md):
 *   Из Supabase: title, loc, type, price, beds, area, roi, deadline, status,
 *   desc (из usp), фото, диапазон доходности (rental_benchmarks).
 *   НЕ из Supabase (сохраняются из текущего index.html по property_id):
 *   calc (движок калькулятора: сезоны/handoverTHB/buildYears), grad, budget.
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const INDEX = path.join(ROOT, 'index.html');
const OBJDIR = path.join(ROOT, 'object');

/* Размеры JPEG без внешних зависимостей: идём по маркерам до SOF.
   Нужны для og:image:width/height — без них WhatsApp не рисует превью. */
function jpegSize(file) {
  try {
    const b = fs.readFileSync(file);
    if (b.length < 4 || b[0] !== 0xFF || b[1] !== 0xD8) return null;
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xFF) { i++; continue; }
      const m = b[i + 1];
      if (m === 0xD8 || m === 0x01 || (m >= 0xD0 && m <= 0xD7)) { i += 2; continue; }
      if (m === 0xDA) break;                       // начались данные — SOF уже прошли
      const len = b.readUInt16BE(i + 2);
      if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
        return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
      }
      i += 2 + len;
    }
  } catch (e) { /* нет файла — просто не выводим размеры */ }
  return null;
}
const SITEMAP = path.join(ROOT, 'sitemap.xml');

const SITE_BASE = 'https://property-library.com';
const WA = '66955492587';
const RATE = 35; // THB→USD для витринного priceUSD (как в текущем каталоге)

const MARK_START = '/* PLP:AUTO-CATALOG:START — сгенерировано build/gen.mjs из Supabase; вручную не править (calc/grad/budget сохраняются между прогонами) */';
const MARK_END = '/* PLP:AUTO-CATALOG:END */';
const MARK_RENT_START = '/* PLP:AUTO-RENTALS:START — сгенерировано build/gen.mjs из Supabase (объекты аренды); вручную не править (grad сохраняется между прогонами) */';
const MARK_RENT_END = '/* PLP:AUTO-RENTALS:END */';
const MARK_NY_START = '/* PLP:AUTO-NETYIELD:START — сгенерировано build/gen.mjs из Supabase rental_benchmarks (disp_yield_low/high_pct по району); вручную не править */';
const MARK_NY_END = '/* PLP:AUTO-NETYIELD:END */';

// EN-район → RU-подпись (loc.ru). loc.en приходит из Supabase objects.district.
const DISTRICT_RU = {
  'Rawai': 'Равай', 'Bang Tao': 'Банг Тао', 'Nai Yang': 'Най Янг',
  'Surin': 'Сурин', 'Koh Kaew': 'Ко Кео', 'Kamala': 'Камала',
  'Kata': 'Ката', 'Layan': 'Лаян', 'Patong': 'Патонг',
  'Cherng Talay': 'Чернг Талай', 'Nai Harn': 'Най Харн', 'Laguna': 'Лагуна',
  'Kamala Beach': 'Камала', 'Nai Thon': 'Най Тон',
  'Thalang': 'Таланг', 'Mai Khao': 'Май Кхао', 'Karon': 'Карон', 'Naiharn': 'Найхарн',
};

// -------------------------------------------------------------- env / supabase
function loadEnv() {
  const envFile = process.env.PLP_SB_ENV || path.join(os.homedir(), '.plp_site_supabase.env');
  let url = process.env.SUPABASE_URL, key = process.env.SUPABASE_SERVICE_KEY;
  if ((!url || !key) && fs.existsSync(envFile)) {
    for (const line of fs.readFileSync(envFile, 'utf8').split('\n')) {
      const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*)$/);
      if (!m) continue;
      const v = m[2].trim();
      if (m[1] === 'SUPABASE_URL' && !url) url = v;
      if (m[1] === 'SUPABASE_SERVICE_KEY' && !key) key = v;
    }
  }
  if (!url || !key) {
    console.error('[gen] Нет SUPABASE_URL / SUPABASE_SERVICE_KEY (env или ' + envFile + ').');
    process.exit(1);
  }
  return { url: url.replace(/\/$/, ''), key };
}

async function sbGet(env, q) {
  const r = await fetch(env.url + '/rest/v1/' + q, {
    headers: { apikey: env.key, Authorization: 'Bearer ' + env.key, Accept: 'application/json' },
  });
  if (!r.ok) throw new Error('Supabase ' + q + ' → HTTP ' + r.status + ': ' + (await r.text()).slice(0, 300));
  return r.json();
}

// ------------------------------------------------------------------- helpers
const DASH = '–'; // en-dash, как в текущем каталоге

function fmtNum(n) {
  if (n === null || n === undefined) return '';
  return String(n);
}
function bedsLabel(o) {
  const min = o.bedrooms_min, max = o.bedrooms_max;
  if (min === null || min === undefined || max === null || max === undefined) {
    return (o.bedrooms || '').replace(/-/g, DASH);
  }
  const lo = min === 0 ? 'Studio' : String(min);
  if (min === max) return lo;
  return lo + DASH + String(max);
}
function areaLabel(o) {
  const min = o.area_min, max = o.area_max;
  if (min === null || min === undefined || max === null || max === undefined) {
    // area_sqm бывает «замусорен» аннотацией — берём только числовую часть
    const raw = String(o.area_sqm || '').match(/[\d.]+\s*[-–]\s*[\d.]+|[\d.]+/);
    return raw ? raw[0].replace(/-/g, DASH) + ' м²' : '';
  }
  if (min === max) return fmtNum(min) + ' м²';
  return fmtNum(min) + DASH + fmtNum(max) + ' м²';
}
function deadline(handover) {
  if (!handover) return { ru: '', en: '' };
  const [y, m] = handover.split('-');
  const q = Math.floor((parseInt(m, 10) - 1) / 3) + 1;
  return { ru: q + 'Q ' + y, en: 'Q' + q + ' ' + y };
}
const STATUS_MAP = { active: 'available', archived: 'reserved', sold: 'sold' };
function statusLabel(s) { return STATUS_MAP[s] || 'available'; }

function typeLabel(t) {
  const v = String(t || '').toLowerCase();
  if (v.startsWith('vill') || v === 'вилла') return { ru: 'Вилла', en: 'Villa' };
  return { ru: 'Кондо', en: 'Condo' };
}
function typeRu(t) { return typeLabel(t).ru; }

function slugOf(pid) { return pid.replace(/^PLP-/, '').toLowerCase(); }

// диапазон доходности из rental_benchmarks: (district,type) → (district,Кондо) → 6–12
function yieldRange(benchmarks, district, type) {
  const tr = typeRu(type);
  const find = (d, u) => benchmarks.find(b => b.district === d && b.unit_type === u);
  let b = find(district, tr) || find(district, 'Кондо') ||
          benchmarks.find(x => x.district === district);
  if (b && b.disp_yield_low_pct != null && b.disp_yield_high_pct != null) {
    return { low: b.disp_yield_low_pct, high: b.disp_yield_high_pct };
  }
  return { low: 6, high: 12 }; // клиентский ориентир по умолчанию
}

// сохраняемый из index.html движок калькулятора (fallback для новых объектов)
function fallbackCalc(o) {
  const priceTHB = o.price_from_thb || 0;
  const sr = o.season_rates || {};
  const high = sr.high_thb_month || 0, low = sr.low_thb_month || 0;
  const shoulder = high && low ? Math.round((high + low) / 2) : (high || low || 0);
  const occ = o.occupancy_est_pct || 70;
  // Сколько осталось строить — из даты сдачи. Раньше стояло 0, и график платежей
  // ставил все взносы на сегодня. Сдан или дата неизвестна → 0 (рассрочки нет).
  let buildYears = 0;
  if (o.handover_date) {
    const months = (new Date(o.handover_date) - new Date()) / (1000 * 60 * 60 * 24 * 30.44);
    buildYears = months > 0 ? Math.round((months / 12) * 10) / 10 : 0;
  }
  // Первый взнос — как у застройщика, а не выдуманные 30%.
  const downPct = Number(o.first_payment) > 0 ? Number(o.first_payment) : undefined;

  return {
    priceTHB, handoverTHB: priceTHB, areaM2: o.area_min || 0, mgmtPct: 20,
    maintM2Month: o.maintenance_fee_thb_sqm || 80, capexM2: 800, metersTHB: 15000,
    // Рост цены ПОСЛЕ сдачи. До сдачи он уже заложен в handoverTHB.
    // Эльнур 04.09: на стройке проект даёт ~30–35% за 2–3 года, после сдачи 1–5% в год.
    // Потолок 5 — страховка: если в базу опять попадёт рост за всю стройку, он сюда не пролезет.
    capGrowthPct: Math.min(Number(o.capital_growth_pct) || 3, 5), buildYears,
    downPct,
    // План застройщика — дословно из базы. Не разбираем на строки: формулировки у всех
    // разные, любой разбор — выдумка. Таблица рядом остаётся прикидкой.
    paymentPlan: o.payment_plan || o.payment_schedule || '',
    estimated: true,
    seasons: {
      high: { rent: high, occ, months: 4 },
      shoulder: { rent: shoulder, occ, months: 2 },
      low: { rent: low, occ, months: 6 },
    },
  };
}

// Короткое имя застройщика для карточки. В базе поле развёрнутое, с юридическим
// названием и регистрационным номером — в карточке это нечитаемая простыня.
// Ничего не выдумываем: только отрезаем служебные хвосты от того, что уже есть.
function shortDev(dev) {
  if (!dev) return '';
  let d = String(dev).split(' — ')[0].split(' – ')[0].trim();
  // скобки с реквизитами, годами и адресами выбрасываем, короткий бренд оставляем
  d = d.replace(/\s*\(([^)]*)\)/g, (m, inner) =>
    (/\d/.test(inner) || inner.length > 12) ? '' : ' (' + inner.trim() + ')');
  d = d.replace(/\s*\b(Public Company Limited|Co\.,? ?Ltd\.?|Company Limited|PCL|PLC)\b\.?/gi, '');
  return d.replace(/[\s,;]+$/, '').trim();
}

// Факты из базы кладём поверх сохранённого calc: срок стройки, первый взнос,
// план застройщика и потолок роста — это данные, а не ручная настройка витрины.
// Всё остальное в calc (сезоны, расходы) правится руками и переживает пересборку.
function withFacts(calc, o) {
  const c = Object.assign({}, calc);
  let buildYears = 0;
  if (o.handover_date) {
    const months = (new Date(o.handover_date) - new Date()) / (1000 * 60 * 60 * 24 * 30.44);
    buildYears = months > 0 ? Math.round((months / 12) * 10) / 10 : 0;
  }
  c.buildYears = buildYears;
  if (Number(o.first_payment) > 0) c.downPct = Number(o.first_payment);
  c.paymentPlan = o.payment_plan || o.payment_schedule || '';
  // Сдан по-настоящему — только stage='Ready' (канон №38). Если стройка идёт,
  // а дата сдачи в базе уже прошла — это устаревшая дата, а не сданный объект.
  c.ready = o.stage === 'Ready';
  // Потолок 5 — канон Эльнура 04.09: после сдачи 1–5% в год.
  c.capGrowthPct = Math.min(Number(o.capital_growth_pct) || c.capGrowthPct || 3, 5);
  return c;
}

// ----------------------------------------------- парсинг текущего PL.PROPERTIES
// Возвращает { block, arr, hasMarkers, preserve } — preserve по property_id.
function parseExisting(html) {
  const s = html.indexOf(MARK_START);
  const e = html.indexOf(MARK_END);
  let region, hasMarkers = false;
  if (s !== -1 && e !== -1 && e > s) {
    hasMarkers = true;
    region = html.slice(s + MARK_START.length, e);
  } else {
    region = html; // первый прогон: маркеров ещё нет
  }
  const ai = region.indexOf('PL.PROPERTIES=');
  if (ai === -1) return { arr: [], hasMarkers, preserve: {} };
  const lb = region.indexOf('[', ai);
  const end = region.indexOf('\n];', lb);
  const arrText = region.slice(lb, end + 2);
  let arr = [];
  try { arr = eval(arrText); } catch (err) {
    console.error('[gen] Не удалось разобрать текущий PL.PROPERTIES:', err.message);
  }
  const preserve = {};
  for (const p of arr) {
    preserve[p.property_id] = { calc: p.calc, grad: p.grad, budget: p.budget };
  }
  return { arr, hasMarkers, preserve };
}

// ------------------------------------------------------------- сборка каталога
function buildCatalog(objects, benchmarks, preserve) {
  return objects.map((o, i) => {
    const pid = o.plp_property_id;
    const keep = preserve[pid] || {};
    const en = o.district || o.beach || '';
    const usp = (o.usp || '').trim();
    const uspEn = (o.usp_en || '').trim() || usp; // EN-описание из usp_en, фолбэк на usp
    return {
      property_id: pid,
      title: o.name,
      funnel: 'sale',
      grad: keep.grad || ('g' + ((i % 4) + 1)),
      loc: { ru: DISTRICT_RU[en] || en, en },
      type: typeLabel(o.type),
      priceUSD: o.price_from_thb ? Math.round(o.price_from_thb / RATE) : null,
      roi: (o.roi === 0 || o.roi) ? o.roi : null,
      budget: keep.budget || 'b1',
      beds: bedsLabel(o),
      area: areaLabel(o),
      deadline: deadline(o.handover_date),
      status: statusLabel(o.status),
      // 30.08 канон №38: «готов/сдан» — ТОЛЬКО из stage='Ready', никогда из даты сдачи.
      ready: o.stage === 'Ready',
      // 03.09: стадия отдельным полем — по ней фильтр и бейдж на карточке
      // числовой диапазон спален — по нему работает фильтр «Спальни»
      bmin: (o.bedrooms_min === 0 || o.bedrooms_min) ? o.bedrooms_min : null,
      bmax: (o.bedrooms_max === 0 || o.bedrooms_max) ? o.bedrooms_max : null,
      stage_key: (function(){
        var st = String(o.stage || '').toLowerCase();
        if (st === 'ready') return 'ready';
        if (st === 'construction') return 'construction';
        if (st === 'pre-sale' || st === 'presale') return 'presale';
        if (st === 'resale' || String(o.purpose||'').toLowerCase() === 'resale') return 'resale';
        return '';
      })(),
      desc: { ru: usp, en: uspEn },
      // 02.09: то, что человек ищет глазами в первую очередь — море и застройщик.
      // Пишем только если данные есть, пустое поле карточка не рисует.
      // координаты нужны карте объектов — без них метку не поставить
      lat: (o.lat === 0 || o.lat) ? Number(o.lat) : null,
      lng: (o.lng === 0 || o.lng) ? Number(o.lng) : null,
      // 02.09: приблизительные точки помечаем — карта не должна выдавать их за адрес
      coordOk: o.coord_source === 'exact' || o.coord_source === 'verified',
      // 02.09: цена в карточке — это минимум из прайса на дату сверки, а не
      // «сегодня». Отдаём дату, чтобы витрина честно её показывала.
      priceDate: o.last_synced_at ? String(o.last_synced_at).slice(0, 10) : null,
      // сколько юнитов свободно по последнему прайсу застройщика
      avail: (function(){ var m=/(\d+)/.exec(o.availability || ''); return m ? +m[1] : null; })(),
      beach: o.beach || null,
      beachM: (o.distance_beach_m === 0 || o.distance_beach_m) ? o.distance_beach_m : null,
      // Снимки из хранилища: первый идёт обложкой, остальные — лентой в карточке.
      // Локальные img/<ID>.jpg остаются запасным вариантом для старых объектов.
      photo: o.main_image_url || null,
      photos: Array.isArray(o.gallery_urls) ? o.gallery_urls.slice(0, 8) : null,
      // Планировки: человек выбирает тип и сразу видит его площадь и спальни.
      // Где застройщик не давал названий планировок, берём тиры из прайса
      // (минимальная цена на каждый тип спальни) — Эльнур 05.09: «продаётся
      // проект, а что там можно купить». Цены и площади — из price_tiers,
      // ничего не досочиняем.
      units: unitsOf(o),
      // Витрина «горячие предложения»: порядок задаём вручную в базе (hot_rank).
      hot: (o.hot_rank === 0 || o.hot_rank) ? Number(o.hot_rank) : null,
      // Ход стройки и разделы снимков — показываем, если застройщик их дал.
      progress: o.build_progress || null,
      groups: Array.isArray(o.photo_groups) ? o.photo_groups : null,
      developer: shortDev(o.developer) || null,
      developerFull: o.developer || null,
      calc: withFacts(keep.calc || fallbackCalc(o), o),
    };
  });
}

/* Что можно купить в проекте: сначала именованные планировки застройщика,
   иначе — тиры прайса (по одной строке на тип спальни, цена «от»). */
function unitsOf(o) {
  const named = Array.isArray(o.unit_types) ? o.unit_types.slice(0, 12) : [];
  // Тиры приходят от разных застройщиков в двух видах: с числом спален или с
  // подписью типа «Studio / 1BR / 2BR», цена — price_from_thb либо price_thb.
  // Приводим к одному виду, иначе половина проектов остаётся без планировок.
  const tiers = (Array.isArray(o.price_tiers) ? o.price_tiers : []).map(t => {
    let b = t.bedrooms;
    if (b == null && t.type) {
      const s = String(t.type).toLowerCase();
      const m = /(\d+)\s*(br|bed)/.exec(s);
      b = /studio/.test(s) ? 0 : (m ? +m[1] : null);
    }
    return Object.assign({}, t, { bedrooms: b,
      price_from_thb: t.price_from_thb || t.price_thb || null });
  }).filter(t => t.bedrooms != null);
  const priceByBeds = {};
  for (const t of tiers) {
    const b = t.bedrooms;
    if (b == null || !t.price_from_thb) continue;
    if (!priceByBeds[b] || t.price_from_thb < priceByBeds[b]) priceByBeds[b] = t.price_from_thb;
  }
  if (named.length) {
    // Цену «от» из прайса подставляем только там, где планировка с таким числом
    // спален одна. Иначе AURA, SELENE и MYRRHA получали одинаковый ценник —
    // это цена группы «3 спальни», а не конкретного типа.
    const perBeds = {};
    for (const u of named) perBeds[u.beds] = (perBeds[u.beds] || 0) + 1;
    return named.map(u => {
      const from = priceByBeds[u.beds];
      return (from && perBeds[u.beds] === 1) ? Object.assign({}, u, { from }) : u;
    });
  }
  if (!tiers.length) return null;
  const byBeds = new Map();
  for (const t of tiers) {
    const b = t.bedrooms;
    if (b == null) continue;
    const cur = byBeds.get(b);
    if (!cur || (t.price_from_thb && t.price_from_thb < cur.price_from_thb)) byBeds.set(b, t);
  }
  return [...byBeds.entries()].sort((a, c) => a[0] - c[0]).map(([b, t]) => ({
    name: b === 0 ? 'Студия' : b + (b === 1 ? ' спальня' : b < 5 ? ' спальни' : ' спален'),
    beds: b,
    area: t.area_sqm || null,
    from: t.price_from_thb || null,
  }));
}

function emitCatalogBlock(catalog) {
  const items = catalog.map(p => '  ' + JSON.stringify(p)).join(',\n');
  return MARK_START + '\n' +
    'PL.PROPERTIES=[\n' + items + '\n];\n' +
    MARK_END;
}

// заменить (или врезать) блок каталога в index.html
function writeIndex(html, catalog) {
  const block = emitCatalogBlock(catalog);
  const s = html.indexOf(MARK_START);
  const e = html.indexOf(MARK_END);
  if (s !== -1 && e !== -1 && e > s) {
    return html.slice(0, s) + block + html.slice(e + MARK_END.length);
  }
  // первый прогон — оборачиваем существующий PL.PROPERTIES=[...];
  const ai = html.indexOf('PL.PROPERTIES=');
  const lb = html.indexOf('[', ai);
  const end = html.indexOf('\n];', lb) + 3; // включая '\n];'
  return html.slice(0, ai) + block + html.slice(end);
}

// -------------------------------------------------------------- аренда (RENTALS)
// Парсит текущий PL.RENTALS для сохранения grad по property_id.
function parseExistingRentals(html) {
  const s = html.indexOf(MARK_RENT_START);
  const e = html.indexOf(MARK_RENT_END);
  let region = (s !== -1 && e !== -1 && e > s) ? html.slice(s + MARK_RENT_START.length, e) : html;
  const ai = region.indexOf('PL.RENTALS=');
  if (ai === -1) return {};
  const lb = region.indexOf('[', ai);
  const end = region.indexOf('\n];', lb);
  if (lb === -1 || end === -1) return {};
  let arr = [];
  try { arr = eval(region.slice(lb, end + 2)); } catch (err) { return {}; }
  const preserve = {};
  for (const p of arr) if (p && p.property_id) preserve[p.property_id] = { grad: p.grad };
  return preserve;
}

// Короткий тег для карточки аренды: до пляжа → мин.срок → «Аренда».
function rentTag(o) {
  if (o.distance_beach_m) return { ru: o.distance_beach_m + ' м до моря', en: o.distance_beach_m + ' m to the sea' };
  if (o.min_stay) return { ru: 'от ' + o.min_stay + ' мес', en: 'from ' + o.min_stay + ' mo' };
  // 30.08: раньше падало в заглушку «Аренда» — но блок и так называется «Аренда».
  // Нечего сказать по объекту — не пишем ничего.
  return { ru: '', en: '' };
}

function buildRentals(objects, preserve) {
  return objects.map((o, i) => {
    const pid = o.plp_property_id;
    const keep = preserve[pid] || {};
    const en = o.district || o.beach || '';
    const usp = (o.usp || '').trim();
    const uspEn = (o.usp_en || '').trim() || usp;
    const S = (v) => (v === undefined || v === null) ? '' : String(v).trim();
    return {
      property_id: pid,
      title: o.name,
      funnel: 'rent',
      grad: keep.grad || ('g' + ((i % 4) + 1)),
      loc: { ru: DISTRICT_RU[en] || en, en },
      type: typeLabel(o.type),
      beds: bedsLabel(o),
      bmin: (o.bedrooms_min === 0 || o.bedrooms_min) ? o.bedrooms_min : null,
      bmax: (o.bedrooms_max === 0 || o.bedrooms_max) ? o.bedrooms_max : null,
      area: areaLabel(o),
      tag: rentTag(o),
      desc: { ru: usp, en: uspEn },
      // 02.09: аренда тоже встаёт на карту — координаты из той же таблицы
      lat: (o.lat === 0 || o.lat) ? Number(o.lat) : null,
      lng: (o.lng === 0 || o.lng) ? Number(o.lng) : null,
      coordOk: o.coord_source === 'exact' || o.coord_source === 'verified',
      min_stay: (o.min_stay === 0 || o.min_stay) ? o.min_stay : null,
      deposit: (o.deposit === 0 || o.deposit) ? o.deposit : null,
      // фильтр удобств: источники — amenities (если есть) + rent_included; distance_beach_m для «у моря»
      amenities: S(o.amenities),
      beach_m: (o.distance_beach_m === 0 || o.distance_beach_m) ? o.distance_beach_m : null,
      included: S(o.rent_included),
      excluded: S(o.rent_excluded),
      rules: S(o.rent_rules),
      // 05.09: у аренды на витрине не было ни одного снимка — поля просто не
      // доезжали из базы. Теперь галерея, разделы и планировки тянутся так же,
      // как у продажи.
      photo: o.main_image_url || null,
      photos: Array.isArray(o.gallery_urls) ? o.gallery_urls.slice(0, 8) : null,
      groups: Array.isArray(o.photo_groups) ? o.photo_groups : null,
      units: unitsOf(o),
    };
  });
}

function emitRentalsBlock(rentals) {
  // < → <, чтобы свободный текст из БД не мог закрыть <script>
  const items = rentals.map(p => '  ' + JSON.stringify(p).replace(/</g, '\\u003c')).join(',\n');
  return MARK_RENT_START + '\n' +
    'PL.RENTALS=[\n' + items + '\n];\n' +
    MARK_RENT_END;
}

function writeRentals(html, rentals) {
  const block = emitRentalsBlock(rentals);
  const s = html.indexOf(MARK_RENT_START);
  const e = html.indexOf(MARK_RENT_END);
  if (s !== -1 && e !== -1 && e > s) {
    return html.slice(0, s) + block + html.slice(e + MARK_RENT_END.length);
  }
  // первый прогон — оборачиваем существующий PL.RENTALS=[...];
  const ai = html.indexOf('PL.RENTALS=');
  if (ai === -1) { console.error('[gen] PL.RENTALS не найден в index.html — аренда не обновлена.'); return html; }
  const lb = html.indexOf('[', ai);
  const end = html.indexOf('\n];', lb) + 3;
  return html.slice(0, ai) + block + html.slice(end);
}

// ------------------------------------------------- PL.NETYIELD (доходность района)
// «Одна истина»: диапазон доходности района на карточках = disp_yield_low/high_pct
// из rental_benchmarks. Если у района несколько unit_type — берём min(low)..max(high)
// (самый широкий клиентский ориентир). Ключ = EN-название района (как в NETYIELD/DISTRICTKEY).
function buildNetyield(benchmarks) {
  const acc = {}; // district → { low, high }
  for (const b of benchmarks) {
    const d = b.district;
    if (!d || b.disp_yield_low_pct == null || b.disp_yield_high_pct == null) continue;
    const lo = Number(b.disp_yield_low_pct), hi = Number(b.disp_yield_high_pct);
    if (!isFinite(lo) || !isFinite(hi)) continue;
    if (!acc[d]) acc[d] = { low: lo, high: hi };
    else { acc[d].low = Math.min(acc[d].low, lo); acc[d].high = Math.max(acc[d].high, hi); }
  }
  const out = {};
  for (const d of Object.keys(acc).sort()) out[d] = acc[d].low + DASH + acc[d].high; // «7–11» (en-dash)
  return out;
}

function emitNetyieldBlock(netyield) {
  const items = Object.keys(netyield).map(d => '  ' + JSON.stringify(d) + ':' + JSON.stringify(netyield[d])).join(',\n');
  return MARK_NY_START + '\n' +
    'PL.NETYIELD={\n' + items + '\n};\n' +
    MARK_NY_END;
}

/* Список всех объектов обычными ссылками.
   28 страниц object/*.html были сиротами: на них не вело ни одной ссылки ни из
   HTML, ни из JS — только карта сайта. Для поиска это худшее, что может быть:
   внутренние ссылки и есть главный сигнал важности страницы. Блок статический,
   скрипты его не перерисовывают, поэтому ссылки видны и роботу, и человеку. */
const MARK_OI_START = '<!-- PLP:OBJECT-INDEX:START — сгенерировано build/gen.mjs, вручную не править -->';
const MARK_OI_END = '<!-- PLP:OBJECT-INDEX:END -->';

function writeObjectIndex(html, objects) {
  const byDistrict = new Map();
  for (const o of objects) {
    if (!o.plp_property_id) continue;
    const d = (o.district || 'Пхукет').trim();
    if (!byDistrict.has(d)) byDistrict.set(d, []);
    byDistrict.get(d).push(o);
  }
  if (!byDistrict.size) { console.error('[gen] Список объектов пуст — блок ссылок не тронут.'); return html; }

  // Эльнур 04.09: не «район → внутри объекты», а просто один выезжающий список,
  // строка = объект. Разбивка по районам читалась как полотно.
  const all = [];
  for (const list of byDistrict.values()) all.push(...list);
  all.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
  const total = all.length;
  const rows = all.map((o) => {
    const href = 'object/' + slugOf(o.plp_property_id) + '.html';
    const price = o.price_from_thb ? fmtBahtShort(Number(o.price_from_thb)) : '';
    const d = DISTRICT_RU[(o.district || '').trim()] || o.district || '';
    return '<li><a href="' + href + '">' + htmlEsc(o.name || o.plp_property_id) + '</a>' +
      '<span class="oi-d">' + htmlEsc(d) + '</span>' +
      (price ? '<span class="oi-p">' + htmlEsc(price) + '</span>' : '') + '</li>';
  }).join('');

  const block = MARK_OI_START + '\n' +
    '<section class="obj-index" id="all-objects"><div class="container">' +
    '<details class="oi-box"><summary><b>Объекты в каталоге</b>' +
    '<span class="oi-n">' + total + '</span></summary>' +
    '<p class="sub">Все проекты, с которыми мы работаем, — с ценами от застройщика ' +
    'и условиями рассрочки.</p>' +
    '<ul class="oi-list">' + rows + '</ul></details>' +
    '</div></section>\n' + MARK_OI_END;

  console.log('[gen] блок ссылок на объекты:', total, 'ссылок одним списком');

  const s = html.indexOf(MARK_OI_START);
  const e = html.indexOf(MARK_OI_END);
  if (s === -1 || e === -1 || e < s) {
    console.error('[gen] Маркеры PLP:OBJECT-INDEX не найдены — блок ссылок не вставлен.');
    return html;
  }
  return html.slice(0, s) + block + html.slice(e + MARK_OI_END.length);
}

function fmtBahtShort(n) {
  if (!n || !isFinite(n)) return '';
  return n >= 1e6 ? (n / 1e6).toFixed(n % 1e6 === 0 ? 0 : 1).replace('.', ',') + ' млн ฿'
                  : Math.round(n / 1000) + ' тыс. ฿';
}

function writeNetyield(html, netyield) {
  const block = emitNetyieldBlock(netyield);
  const s = html.indexOf(MARK_NY_START);
  const e = html.indexOf(MARK_NY_END);
  if (s !== -1 && e !== -1 && e > s) {
    return html.slice(0, s) + block + html.slice(e + MARK_NY_END.length);
  }
  // первый прогон — оборачиваем существующий PL.NETYIELD={...};
  const ai = html.indexOf('PL.NETYIELD=');
  if (ai === -1) { console.error('[gen] PL.NETYIELD не найден в index.html — доходность не обновлена.'); return html; }
  const lb = html.indexOf('{', ai);
  const end = html.indexOf('\n};', lb);
  if (lb === -1 || end === -1) { console.error('[gen] Не разобрал границы PL.NETYIELD — доходность не обновлена.'); return html; }
  return html.slice(0, ai) + block + html.slice(end + 3); // включая '\n};'
}

// -------------------------------------------------------------------- SEO/pages
function htmlEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function jsonLdSafe(obj) {
  // < → <, чтобы описание не могло закрыть <script>
  return JSON.stringify(obj).replace(/</g, '\\u003c');
}
function truncate(s, n) {
  s = String(s || '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
}
function chipRow(items) {
  return items.filter(x => x && x.v).map(x =>
    '<div class="chip"><span class="k">' + htmlEsc(x.k) + '</span><span class="v">' + htmlEsc(x.v) + '</span></div>'
  ).join('');
}

function objectPage(o, benchmarks) {
  const pid = o.plp_property_id;
  const slug = slugOf(pid);
  const url = SITE_BASE + '/object/' + slug + '.html';
  const img = SITE_BASE + '/img/' + pid + '.jpg';
  // Реальные размеры картинки: WhatsApp без og:image:width/height часто вообще
  // не рисует превью, а соврать нельзя — высота у карточек разная (674…1167).
  const imgDim = jpegSize(path.join(ROOT, 'img', pid + '.jpg'));
  const en = o.district || o.beach || '';
  const ru = DISTRICT_RU[en] || en;
  const t = typeLabel(o.type);
  const beds = bedsLabel(o);
  const area = areaLabel(o);
  const dl = deadline(o.handover_date);
  const yr = yieldRange(benchmarks, en, o.type);
  const usp = (o.usp || '').trim();
  const uspEn = (o.usp_en || '').trim(); // EN-описание; секция рендерится только если непусто
  const priceTHB = o.price_from_thb;
  const priceFmt = priceTHB ? new Intl.NumberFormat('ru-RU').format(priceTHB) + ' ฿' : '';
  const title = o.name + ' — ' + ru + ', Пхукет | Property Library';
  const metaDesc = truncate(usp || (o.name + ' — ' + t.ru + ' в районе ' + ru + ', Пхукет.'), 200);
  const distBeach = o.distance_beach_m ? o.distance_beach_m + ' м до пляжа' : '';

  const waText = encodeURIComponent(o.name + ' — интересует этот объект. ' + url);
  const waLink = 'https://wa.me/' + WA + '?text=' + waText;
  const backLink = '../#object=' + encodeURIComponent(pid);

  const ld = {
    '@context': 'https://schema.org',
    '@type': ['Residence', 'Product'],
    name: o.name,
    description: truncate(usp, 500),
    url,
    image: img,
    address: { '@type': 'PostalAddress', addressRegion: 'Phuket', addressLocality: ru, addressCountry: 'TH' },
  };
  if (o.developer) ld.brand = { '@type': 'Organization', name: o.developer };
  if (o.bedrooms_max != null) ld.numberOfRooms = o.bedrooms_max;
  if (o.area_max != null) ld.floorSize = { '@type': 'QuantitativeValue', value: o.area_max, unitCode: 'MTK' };
  if (priceTHB) ld.offers = {
    '@type': 'Offer', priceCurrency: 'THB', price: priceTHB,
    availability: o.status === 'sold' ? 'https://schema.org/SoldOut' : 'https://schema.org/InStock',
    url,
  };

  // Материалы застройщика: показываем только то, что реально заполнено в базе,
  // и только http(s) — чтобы мусорное поле не уехало в разметку.
  const linkOk = (u) => typeof u === 'string' && /^https?:\/\//i.test(u.trim());
  const matLinks = [
    { u: o.brochure_url, t: 'Сейл-кит и презентация' },
    { u: o.floorplan_url, t: 'Планировки' },
    { u: o.video_url, t: '3D-тур и видео' },
    { u: o.website_url, t: 'Сайт проекта' },
    { u: o.map_url, t: 'На карте' },
  ].filter((x) => linkOk(x.u));
  const materials = matLinks.length
    ? '<section class="desc"><h2>Материалы застройщика</h2><div class="cta">' +
      matLinks.map((x) => '<a class="btn ghost" href="' + htmlEsc(x.u.trim()) +
        '" rel="noopener nofollow" target="_blank">' + htmlEsc(x.t) + '</a>').join('') +
      '</div></section>'
    : '';

  // Галерея, планировки и ход стройки — те же данные, что и в карточке на сайте.
  const gallery = Array.isArray(o.gallery_urls) ? o.gallery_urls.filter(u => /^https?:/.test(u)).slice(0, 8) : [];
  const heroSrc = o.main_image_url || (gallery[0] || ('../img/' + pid + '.jpg'));
  const shots = gallery.length > 1
    ? '<div class="shots">' + gallery.map((u, i) =>
        '<button type="button" class="' + (i ? '' : 'on') + '" data-src="' + htmlEsc(u) + '" aria-label="Фото ' + (i + 1) + '">' +
        '<img src="' + htmlEsc(u) + '" alt="" loading="lazy" decoding="async"></button>').join('') + '</div>'
    : '';
  const unitList = unitsOf(o) || [];
  const unitsBlock = unitList.length
    ? '<section class="desc"><h2>Что можно купить</h2><div class="units">' +
      unitList.map(u => '<div class="unitc"><b>' + htmlEsc(u.name || 'Тип') + '</b>' +
        '<span>' + [u.area ? ('от ' + u.area + ' м²') : '', (u.beds != null ? u.beds + ' сп.' : '')].filter(Boolean).join(' · ') + '</span>' +
        (u.from ? '<u>от ' + new Intl.NumberFormat('ru-RU').format(u.from) + ' ฿</u>' : '') + '</div>').join('') +
      '</div></section>'
    : '';
  const bp = o.build_progress && Array.isArray(o.build_progress.photos) ? o.build_progress : null;
  const progressBlock = bp && bp.photos.length
    ? '<section class="desc"><h2>Ход строительства' + (bp.as_of ? ' <small style="font-weight:400;color:var(--muted)">' + htmlEsc(bp.as_of) + '</small>' : '') + '</h2>' +
      '<div class="prgs">' + bp.photos.slice(0, 6).map(u => '<img src="' + htmlEsc(u) + '" alt="" loading="lazy" decoding="async">').join('') + '</div>' +
      (bp.source ? '<p style="font-size:13px;color:var(--muted);margin-top:8px">' + htmlEsc(bp.source) + '</p>' : '') +
      '</section>'
    : '';

  const chips = chipRow([
    { k: 'Тип', v: t.ru },
    { k: 'Спальни', v: beds },
    { k: 'Площадь', v: area },
    { k: 'Сдача', v: dl.ru },
    { k: 'Доходность', v: o.roi ? '~' + o.roi + '%/год' : '' },
    { k: 'До пляжа', v: distBeach },
    { k: 'Застройщик', v: shortDev(o.developer) },
    // Полное юридическое название — отдельной строкой и только если оно
    // действительно длиннее короткого: реквизиты нужны, но не вместо имени.
    { k: 'Юридическое лицо', v: (o.developer && shortDev(o.developer) !== String(o.developer).trim()) ? o.developer : '' },
  ]);

  return `<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){try{var v=localStorage.getItem('pl_theme');
if(v==='dark'||v==='light')document.documentElement.setAttribute('data-theme',v);}catch(e){}})();</script>
<title>${htmlEsc(title)}</title>
<meta name="description" content="${htmlEsc(metaDesc)}">
<link rel="canonical" href="${htmlEsc(url)}">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<meta property="og:type" content="product">
<meta property="og:site_name" content="Property Library Phuket">
<meta property="og:title" content="${htmlEsc(o.name + ' — ' + ru)}">
<meta property="og:description" content="${htmlEsc(metaDesc)}">
<meta property="og:url" content="${htmlEsc(url)}">
<meta property="og:image" content="${htmlEsc(img)}">
<meta property="og:image:secure_url" content="${htmlEsc(img)}">
<meta property="og:image:type" content="image/jpeg">${imgDim ? `
<meta property="og:image:width" content="${imgDim.w}">
<meta property="og:image:height" content="${imgDim.h}">` : ''}
<meta property="og:image:alt" content="${htmlEsc(o.name)}">
<meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${htmlEsc(o.name + ' — ' + ru)}">
<meta name="twitter:description" content="${htmlEsc(metaDesc)}">
<meta name="twitter:image" content="${htmlEsc(img)}">
<script type="application/ld+json">${jsonLdSafe(ld)}</script>
<style>
/* Эльнур 05.09: сайт — единая система. Страница объекта живёт в тех же
   цветах и с тем же набором блоков, что и карточка на сайте. */
:root{--green:#D2D5B3;--green-deep:#5F6242;--olive:#5F6242;--ink:#22251C;--paper:#FBFBF7;
  --bg:#F4F4EE;--card:#FBFBF7;--line:#E6E6DE;--muted:#6B6B63;--text:#22251C;--r:20px}
/* тёмное оформление — тот же канон, что и на сайте; выбор берётся из настройки браузера
   или из того, что человек выбрал кнопкой на сайте */
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){--ink:#ECEFE0;--text:#ECEFE0;--muted:#B9BCA6;
    --bg:#0C0D09;--paper:#191A12;--card:#191A12;--line:#2C2E22;--green-deep:#C3C79A}
}
:root[data-theme="dark"]{--ink:#ECEFE0;--text:#ECEFE0;--muted:#B9BCA6;
  --bg:#0C0D09;--paper:#191A12;--card:#191A12;--line:#2C2E22;--green-deep:#C3C79A}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--text);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit}
.wrap{max-width:920px;margin:0 auto;padding:0 20px}
header.top{padding:18px 0;border-bottom:1px solid var(--line)}
.brand{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:600;letter-spacing:.02em;color:var(--ink)}
.brand img{display:block;border-radius:6px}
.brand small{color:var(--muted);font-weight:400}
.hero{position:relative;border-radius:var(--r);overflow:hidden;margin:24px 0;border:1px solid var(--line);background:var(--card)}
.hero img{display:block;width:100%;height:auto;max-height:520px;object-fit:cover}
.hero .badge{position:absolute;top:14px;left:14px;background:rgba(16,15,12,.62);backdrop-filter:blur(6px);color:#fff;padding:7px 13px;border-radius:999px;font-size:13px;border:0}
/* галерея как в карточке: крупный кадр, под ним миниатюры */
.shots{display:flex;gap:8px;overflow-x:auto;margin:-8px 0 22px;padding-bottom:6px}
.shots button{flex:0 0 96px;height:68px;padding:0;border:2px solid transparent;border-radius:10px;overflow:hidden;background:#eceadf;cursor:pointer}
.shots button.on{border-color:var(--green-deep)}
.shots img{width:100%;height:100%;object-fit:cover;display:block}
.units{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.unitc{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:10px 13px;min-width:150px}
.unitc b{display:block;font-size:14px}
.unitc span{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.unitc u{display:block;text-decoration:none;font-weight:700;font-size:13px;margin-top:3px}
.prgs{display:flex;gap:8px;overflow-x:auto;margin-top:10px;padding-bottom:6px}
.prgs img{flex:0 0 190px;height:130px;object-fit:cover;border-radius:11px;display:block}
h1{font-size:clamp(24px,4vw,34px);line-height:1.2;margin:8px 0 4px}
.loc{color:var(--muted);margin:0 0 14px}
.price{font-size:clamp(22px,3.5vw,30px);font-weight:700;color:var(--ink)}
.price small{display:block;font-size:13px;font-weight:400;color:var(--muted);margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0}
.chip{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;min-width:120px}
.chip .k{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.chip .v{display:block;font-weight:600;margin-top:2px}
.yield{margin:22px 0;padding:18px 20px;border:1px solid var(--line);border-radius:var(--r);background:linear-gradient(180deg,rgba(210,213,179,.08),rgba(210,213,179,.02))}
.yield .num{font-size:26px;font-weight:700;color:var(--green-deep)}
.yield .lbl{color:var(--muted);font-size:14px}
section.desc{margin:26px 0}
section.desc h2{font-size:18px;margin:0 0 10px;color:var(--ink)}
section.desc p{color:var(--text);opacity:.94;white-space:pre-line}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin:28px 0}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:14px 22px;border-radius:14px;font-weight:600;text-decoration:none;border:1px solid var(--line);cursor:pointer}
.btn.wa{background:#25D366;color:#0b2b18;border-color:#25D366}
.btn.primary{background:var(--green);color:var(--on-green,#14150F);border-color:var(--green)}
.btn.ghost{background:transparent;color:var(--text)}
footer{border-top:1px solid var(--line);margin-top:40px;padding:22px 0 40px;color:var(--muted);font-size:14px}
footer a{color:var(--green-deep);text-decoration:none}
</style>
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="../" aria-label="Property Library — на главную"><img id="brandMark" src="../img/brand/plp-mark-ink.png" alt="" width="24" height="24">Property Library Phuket <small>· недвижимость на Пхукете</small></a></div></header>
<script>(function(){var i=document.getElementById('brandMark');if(!i)return;
var d=document.documentElement.getAttribute('data-theme');
var dark = d==='dark' || (d!=='light' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
if(dark) i.src='../img/brand/plp-mark-white.png';})();</script>
<main class="wrap">
  <div class="hero">
    <img id="mainShot" src="${htmlEsc(heroSrc)}" alt="${htmlEsc(o.name)}" loading="lazy">
    <div class="badge">${htmlEsc(t.ru)} · ${htmlEsc(ru)}</div>
  </div>
  ${shots}
  <h1>${htmlEsc(o.name)}</h1>
  <p class="loc">${htmlEsc(ru)}, Пхукет${distBeach ? ' · ' + htmlEsc(distBeach) : ''}</p>
  ${priceFmt ? '<div class="price">от ' + htmlEsc(priceFmt) + '<small>стартовая цена застройщика</small></div>' : ''}
  <div class="chips">${chips}</div>
  <div class="yield">
    <div class="num">${yr.low}${DASH}${yr.high}%</div>
    <div class="lbl">Ориентир доходности по району (${htmlEsc(ru)}, ${htmlEsc(t.ru.toLowerCase())}) — потенциал при активном управлении. Индивидуально, раскрывается со специалистом.</div>
  </div>
  ${unitsBlock}
  ${progressBlock}
  ${usp ? '<section class="desc"><h2>Об объекте</h2><p>' + htmlEsc(usp) + '</p></section>' : ''}
  ${uspEn ? '<section class="desc" lang="en"><h2>About</h2><p>' + htmlEsc(uspEn) + '</p></section>' : ''}
  ${materials}
  <div class="cta">
    <a class="btn wa" href="${htmlEsc(waLink)}" rel="noopener" target="_blank">WhatsApp — узнать детали</a>
    <a class="btn primary" href="${htmlEsc(backLink)}">Открыть карточку на сайте</a>
    <a class="btn ghost" href="${htmlEsc(backLink)}">Рассчитать доходность</a>
  </div>
</main>
<script>
/* миниатюры листают главный кадр — как в карточке на сайте */
(function(){
  var main=document.getElementById('mainShot');
  var strip=document.querySelector('.shots');
  if(!main||!strip) return;
  strip.addEventListener('click',function(e){
    var b=e.target.closest('button'); if(!b) return;
    main.src=b.dataset.src;
    Array.prototype.forEach.call(strip.children,function(x){ x.classList.toggle('on',x===b); });
  });
})();
</script>
<footer><div class="wrap">Property Library Phuket · <a href="https://wa.me/${WA}" rel="noopener" target="_blank">WhatsApp +66 95 549 2587</a> · <a href="../">на главную</a><br>Данные носят справочный характер и не являются офертой.</div></footer>
</body>
</html>
`;
}

// -------------------------------------------------------------------- sitemap
function sitemap(objects) {
  const today = new Date().toISOString().slice(0, 10);
  // 02.09: якоря заменены отдельными страницами — их и индексируем.
  // Раньше генератор перезаписывал sitemap и терял разделы, собранные скриптами.
  const anchors = ['#quiz', '#about', '#faq', '#contacts'];
  const pages = [
    ['buy.html', '0.9'], ['rent.html', '0.9'], ['management.html', '0.8'],
    ['add-property.html', '0.8'],
    ...['bang-tao','layan','surin','kamala','rawai','kata','nai-yang','koh-kaew']
        .map(d => ['districts/' + d + '.html', '0.8']),
    ...['inostranec-mozhet-kupit','leasehold-ili-freehold','skolko-oformlyaetsya-sdelka',
        'rashody-pri-pokupke','kupit-udalenno','stoimost-uslug']
        .map(g => ['guide/' + g + '.html', '0.6']),
  ];
  const parts = [];
  parts.push('<?xml version="1.0" encoding="UTF-8"?>');
  parts.push('<!-- Сгенерировано build/gen.mjs. Главная + якоря + отдельные страницы объектов. -->');
  parts.push('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">');
  parts.push(`  <url><loc>${SITE_BASE}/</loc><lastmod>${today}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>`);
  for (const a of anchors) {
    parts.push(`  <url><loc>${SITE_BASE}/${a}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>`);
  }
  for (const [pg, pri] of pages) {
    parts.push(`  <url><loc>${SITE_BASE}/${pg}</loc><lastmod>${today}</lastmod><changefreq>weekly</changefreq><priority>${pri}</priority></url>`);
  }
  // 30.08: правовые документы тоже индексируем — они часть сайта
  for (const doc of ['privacy.html', 'rules.html', 'terms.html']) {
    parts.push(`  <url><loc>${SITE_BASE}/${doc}</loc><lastmod>${today}</lastmod><changefreq>yearly</changefreq><priority>0.3</priority></url>`);
  }
  for (const o of objects) {
    const loc = SITE_BASE + '/object/' + slugOf(o.plp_property_id) + '.html';
    parts.push(`  <url><loc>${loc}</loc><lastmod>${today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>`);
  }
  parts.push('</urlset>');
  return parts.join('\n') + '\n';
}

// ------------------------------------------------------------------------ main
async function main() {
  const env = loadEnv();
  console.log('[gen] Supabase:', env.url);

  // 30.08: добавлен фильтр по назначению. Раньше в каталог продажи попадало ВСЁ с
  // on_site=true — пока аренды на витрине не было, баг не проявлялся; как только
  // появились арендные объекты, они протекли в продажу (21 → 27).
  const objects = await sbGet(env,
    'objects?on_site=eq.true&purpose=not.in.(' + encodeURIComponent('аренда') + ',rent)' +
    '&order=plp_property_id' +
    '&select=plp_property_id,name,district,beach,purpose,type,price_from_thb,price_to_thb,' +
    'bedrooms,bedrooms_min,bedrooms_max,area_sqm,area_min,area_max,roi,rental_yield_pct,' +
    'capital_growth_pct,handover_date,status,stage,developer,distance_beach_m,usp,usp_en,'+
    'bedrooms_min,bedrooms_max,' +
    'brochure_url,floorplan_url,video_url,website_url,map_url,' +
    'season_rates,occupancy_est_pct,maintenance_fee_thb_sqm,lat,lng,coord_source,last_synced_at,availability,' +
    'first_payment,payment_plan,payment_schedule,main_image_url,gallery_urls,unit_types,price_tiers,build_progress,photo_groups,hot_rank');
  const benchmarks = await sbGet(env,
    'rental_benchmarks?select=district,unit_type,disp_yield_low_pct,disp_yield_high_pct');

  // объекты аренды: purpose IN (аренда,rent) И on_site=true.
  // 30.08: убрано исключение для PLP-TEST-RENT — тестовый эталон утекал на публичный сайт.
  const rentals = await sbGet(env,
    'objects?select=plp_property_id,name,district,beach,purpose,type,bedrooms,bedrooms_min,' +
    'bedrooms_max,area_sqm,area_min,area_max,min_stay,deposit,rent_included,rent_excluded,' +
    'rent_rules,amenities,usp,usp_en,distance_beach_m,on_site,lat,lng,coord_source,last_synced_at,' +
    'main_image_url,gallery_urls,photo_groups,unit_types,price_tiers' +
    '&and=(or(purpose.eq.' + encodeURIComponent('аренда') + ',purpose.eq.rent),' +
    'on_site.eq.true)&order=plp_property_id');

  console.log('[gen] Объектов on_site=true:', objects.length, '| benchmarks:', benchmarks.length, '| аренда:', rentals.length);
  if (!objects.length) { console.error('[gen] Пусто — прерываю, index.html не трогаю.'); process.exit(1); }

  // 1) каталог продажи + аренда в index.html (с сохранением calc/grad/budget)
  let html = fs.readFileSync(INDEX, 'utf8');
  const { preserve } = parseExisting(html);
  const catalog = buildCatalog(objects, benchmarks, preserve);
  html = writeIndex(html, catalog);
  const rentPreserve = parseExistingRentals(html);
  const rentList = buildRentals(rentals, rentPreserve);
  // 30.08: пока в аренде нет объектов с on_site=true — показываем штатную карточку
  // «Скоро в каталоге» (ветка p.soon в renderRent), а не пустую полосу.
  if (!rentList.length) {
    rentList.push({
      property_id: 'PLP-RENT-SOON', soon: true, funnel: 'rent', grad: 'g1',
      loc: { ru: 'Пхукет', en: 'Phuket' },
      type: { ru: 'Вилла / апартаменты', en: 'Villa / apartment' },
    });
    console.log('[gen] аренда пуста → вставлена карточка «Скоро в каталоге»');
  }
  html = writeRentals(html, rentList);
  // доходность района (PL.NETYIELD) из rental_benchmarks — fail-closed: пустой ответ не трогаем
  const netyield = buildNetyield(benchmarks);
  if (Object.keys(netyield).length) {
    html = writeNetyield(html, netyield);
    console.log('[gen] PL.NETYIELD обновлён из rental_benchmarks:', Object.keys(netyield).length, 'районов');
  } else {
    console.error('[gen] rental_benchmarks пуст — PL.NETYIELD не тронут (fail-closed).');
  }
  html = writeObjectIndex(html, objects);
  fs.writeFileSync(INDEX, html);
  console.log('[gen] index.html: каталог продажи', catalog.length, '+ аренда', rentList.length, 'обновлены');

  // 2) страницы объектов
  // Аренде страницы тоже нужны — карта и каталог на них ссылаются. Раньше их не
  // делали из-за утечки: в 08.26 из-за протечки аренды в продажу на прод уехали
  // страницы с именем собственника. Сейчас objectPage поля owner_ref/owner_contact_id
  // не выводит вовсе, поэтому безопасно; выборку для аренды берём полную, чтобы
  // страница не собиралась из половины данных.
  const rentIds = rentals.map(r => r.plp_property_id).filter(Boolean);
  let rentFull = [];
  if (rentIds.length) {
    rentFull = await sbGet(env, 'objects?plp_property_id=in.(' +
      rentIds.map(encodeURIComponent).join(',') + ')&select=*');
  }
  const seenPage = new Set();
  const pageList = [];
  for (const o of objects.concat(rentFull)) {
    if (!o || !o.plp_property_id || seenPage.has(o.plp_property_id)) continue;
    seenPage.add(o.plp_property_id);
    pageList.push(o);
  }
  if (!fs.existsSync(OBJDIR)) fs.mkdirSync(OBJDIR, { recursive: true });
  let pages = 0;
  for (const o of pageList) {
    const slug = slugOf(o.plp_property_id);
    fs.writeFileSync(path.join(OBJDIR, slug + '.html'), objectPage(o, benchmarks));
    pages++;
  }
  // 30.08: удаляем страницы объектов, которых больше нет в каталоге.
  // Раньше генератор только дописывал — из-за бага с протечкой аренды в продажу
  // на прод уехали страницы арендных юнитов с ИМЕНЕМ СОБСТВЕННИКА и номером
  // квартиры, и после исправления каталога они там так и остались.
  const keep = new Set(pageList.map(o => slugOf(o.plp_property_id) + '.html'));
  let removed = 0;
  for (const f of fs.readdirSync(OBJDIR)) {
    if (f.endsWith('.html') && !keep.has(f)) { fs.unlinkSync(path.join(OBJDIR, f)); removed++; }
  }
  console.log('[gen] object/*.html:', pages, 'страниц' + (removed ? ', удалено лишних: ' + removed : ''));

  // 3) sitemap
  fs.writeFileSync(SITEMAP, sitemap(objects));
  console.log('[gen] sitemap.xml обновлён');

  // 4) короткий список для конструктора оффера в кабинете: чтобы сотрудник
  //    выбирал объект и тип юнита из списка, а не вбивал ID руками.
  const offerCat = objects.map(o => ({
    id: o.plp_property_id,
    name: o.name,
    district: DISTRICT_RU[o.district || ''] || o.district || '',
    type: typeLabel(o.type).ru,
    price_from: o.price_from_thb || null,
    units: unitsOf(o) || [],
  })).filter(x => x.id && x.name);
  fs.writeFileSync(path.join(ROOT, 'offer-catalog.json'),
    JSON.stringify({ updated: new Date().toISOString().slice(0, 10), items: offerCat }, null, 1));
  console.log('[gen] offer-catalog.json:', offerCat.length, 'объектов для конструктора оффера');

  console.log('[gen] Готово.');
}

main().catch(e => { console.error('[gen] ОШИБКА:', e.message); process.exit(1); });

/* ═══════════════════════════════════════════════════════════════
   СТРАНИЦЫ РАЗДЕЛОВ (01.09)
   Собираются ИЗ index.html, а не пишутся заново: шапка, подвал,
   стили и скрипты берутся оттуда же. Правка на главной автоматически
   расходится по всем разделам — один экземпляр вместо копий.
   ═══════════════════════════════════════════════════════════════ */

function splitSections(mainHtml) {
  // режем <main> на секции; для каждой запоминаем id (если есть)
  const parts = [];
  const re = /<section\b[^>]*>/g;
  const starts = [];
  let m;
  while ((m = re.exec(mainHtml)) !== null) starts.push({ i: m.index, tag: m[0] });
  for (let k = 0; k < starts.length; k++) {
    const from = starts[k].i;
    const to = k + 1 < starts.length ? starts[k + 1].i : mainHtml.length;
    const idm = starts[k].tag.match(/id="([^"]+)"/);
    parts.push({ id: idm ? idm[1] : null, html: mainHtml.slice(from, to), order: k });
  }
  return parts;
}

function sectionPage(indexHtml, opts) {
  const mStart = indexHtml.indexOf('<main');
  const mOpenEnd = indexHtml.indexOf('>', mStart) + 1;
  const mEnd = indexHtml.indexOf('</main>');
  const head = indexHtml.slice(0, mOpenEnd);
  const tail = indexHtml.slice(mEnd);
  const parts = splitSections(indexHtml.slice(mOpenEnd, mEnd));

  // берём только нужные секции: по id или по порядковому номеру
  const picked = opts.sections.map(sel => {
    const found = typeof sel === 'number'
      ? parts.find(p => p.order === sel)
      : parts.find(p => p.id === sel);
    return found ? found.html : '';
  }).join('\n');

  const intro =
    '<section style="padding-bottom:0"><div class="container">' +
    '<h1 style="font-size:clamp(28px,4.2vw,42px);margin:0 0 10px">' + htmlEsc(opts.h1) + '</h1>' +
    '<p class="sub" style="max-width:62ch;margin:0">' + htmlEsc(opts.intro) + '</p>' +
    '</div></section>';

  let out = head + '\n' + intro + '\n' + picked + '\n' + tail;

  // мета под конкретный раздел
  const url = SITE_BASE + '/' + opts.file;
  out = out.replace(/<title>[\s\S]*?<\/title>/, '<title>' + htmlEsc(opts.title) + '</title>');
  out = out.replace(/(<meta name="description" content=")[^"]*(")/, '$1' + htmlEsc(opts.desc) + '$2');
  out = out.replace(/(<link rel="canonical" href=")[^"]*(")/, '$1' + url + '$2');
  out = out.replace(/(<meta property="og:url" content=")[^"]*(")/, '$1' + url + '$2');
  out = out.replace(/(<meta property="og:title" content=")[^"]*(")/, '$1' + htmlEsc(opts.title) + '$2');
  out = out.replace(/(<meta property="og:description" content=")[^"]*(")/, '$1' + htmlEsc(opts.desc) + '$2');
  // пункт меню, соответствующий разделу, подсвечиваем
  out = out.replace('href="index.html#' + (opts.navId || '') + '"',
                    'href="index.html#' + (opts.navId || '') + '" class="on"');
  return out;
}

export function buildSectionPages(indexHtml) {
  const pages = [
    { file: 'buy.html', navId: 'sale', sections: ['sale', 8, 9],
      h1: 'Купить недвижимость на Пхукете',
      intro: 'Проверенные виллы и апартаменты от застройщиков и собственников. Каждый объект мы смотрим лично перед тем, как показать.',
      title: 'Купить недвижимость на Пхукете — виллы и апартаменты | Property Library',
      desc: 'Виллы, апартаменты и кондо на Пхукете от застройщиков и собственников. Проверенные объекты, расчёт доходности, сопровождение сделки.' },
    { file: 'rent.html', navId: 'rent', sections: ['rent'],
      h1: 'Аренда жилья на Пхукете',
      intro: 'Виллы и апартаменты для жизни и отдыха, аренда от месяца. Подберём под даты и бюджет, встретим и заселим.',
      title: 'Аренда виллы или апартаментов на Пхукете | Property Library',
      desc: 'Долгосрочная аренда вилл и апартаментов на Пхукете. Свободные объекты по датам, трансфер, уборка, помощь на месте.' },
  ];
  const written = [];
  for (const p of pages) {
    fs.writeFileSync(path.join(ROOT, p.file), sectionPage(indexHtml, p));
    written.push(p.file);
  }
  return written;
}
