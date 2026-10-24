/* Линт листов-офферов: «преза, а не статья» + чёрный список шума. 24.10.2026.
   Повод: Эльнур 24.10 — «в листах везде тексты лишние, глупые, не для презы, ложный шум».
   Проверяет СОБРАННЫЙ page.htm (у всех листов один HTML: секции, подписи .src, карточки), не sheet.json.
   Правила и пороги описаны в ~/.claude/skills/plp-offer-sheet/SKILL.md (копия в закрытом plp-ops).

     node tools/offer_lint.mjs all            таблица нарушений по всем листам
     node tools/offer_lint.mjs <slug> [-v]    подробно по одному листу (каждое нарушение с текстом)
     node tools/offer_lint.mjs <slug> --metrics   длины по блокам (для калибровки порогов)
     node tools/offer_lint.mjs --file x.htm --kind kondo --metrics   чужой html (эталон из git)
     --strict   выход с кодом 1 при любом нарушении

   Из сборки (tools/offer_sheet.mjs): по умолчанию только предупреждение; OFFER_LINT=strict — сборка падает. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/* виллы и таунхаусы: слово «дом» там законно; остальные листы — кондоминиумы (НЕ_ДЕЛАТЬ №28) */
const БЕЗ_ПРОВЕРКИ_ДОМ = new Set(['aileen', 'naturale-kamala', 'top15']);

/* ПОРОГИ. 24.10 вечер: сняты с единственного эталона — лист ZERO Nai Yang (offers/zero-naiyang, коммит 224961a0;
   его максимумы: лид 203, «Наш взгляд» 247 в версии d63ecbfb, подпись 157, подписей в блоке 4, блок 656) с запасом,
   и сверены с отметками по PURITA (~/plp-ops/офферы/PURITA_отметки_2410.md):
     «Наш взгляд» 592 зн. → ШУМ (пересказ самоописания, «Что учесть»); у ZERO 339 зн. ровно на лишнюю оговорку длиннее → 260;
     лид «Проекта» 265 зн. → ШУМ (значение названия, слоган) → 230;
     9 подписей в «Квартирах и ценах» → ШУМ (одна подпись под каждой таблицей, с датой) → 4;
     блок «Квартиры и цены» 2156 зн. → ШУМ (две таблицы с одними площадями, абзац-пересказ) → 1400.
   Было до 24.10 вечера: абзац 330, лид 260, взгляд 300, подпись 200, подписей 5, блок 1500. */
export const ПОРОГИ = {
  абзац: 280,      // самый длинный <p> не-подпись, знаков: одна мысль на абзац
  лид: 230,        // .lead / .sub
  взгляд: 260,     // абзац «Наш взгляд»
  подпись: 160,    // один <p class="src">
  подписей_в_блоке: 4,
  блок: 1400       // текст блока без подписей и без подписей к фото
};

const МЕС = '(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*';
const R = (s, f = 'i') => new RegExp(s, f);

/* [ключ, заголовок, где ищем (src|all), regex, пояснение] */
const ПРАВИЛА = [
  ['даты', 'даты в подписях', 'src',
    R('\\b\\d{1,2}\\.\\d{1,2}\\.\\d{2,4}\\b|' + МЕС + '\\s+20\\d\\d|\\b\\d{1,2}\\s+' + МЕС + '\\s+20\\d\\d'),
    'решение №273: в подписях источников дат нет'],
  ['сайты', 'сайты в подписях', 'src',
    R('(?<![\\w@/-])(?!property-library)[\\w-]+\\.(?:com|net|org|co\\.th|io|ru|travel)\\b|https?://'),
    'решение №273: сайты и ссылки в подписях не называем'],
  /* 24.10 Эльнур: «по версии Bangkok Post — ок, почему бы и нет, такой формат можно, мы не должны скрывать имён».
     Названия СМИ и аналитики (Bangkok Post, The Nation, AirROI, Colliers…) в подписях РАЗРЕШЕНЫ: правило «сми» снято.
     Запрещено по-прежнему: сайты и ссылки (правило «сайты»), порталы (сборка, ПОРТАЛЫ в offer_sheet.mjs),
     продавцы-агенты (правило «агент»), даты, контакты застройщика, комиссии, номера юнитов, «на руки». */
  ['агент', 'агент-продавец, порталы', 'all',
    R('Plus Property|партн[её]р\\w* застройщика по продажам|эксклюзивн\\w* агент|sole agent|Estatyx|FazWaz|DDproperty|Hipflat|Tranio'),
    '№273: имя агента-продавца или портала = слив лида напрямую (PURITA 24.10: Plus Property, Sole Agent 2026, назван 4 раза)'],
  ['оговорки', 'оговорки', 'all',
    R('могут (?:меняться|отличаться|сдвигаться|быть изменены)|может (?:меняться|отличаться|сдвигаться)|гарантии нет|не гарантир|честная оговорка|оговорк|уточняем|уточним|подтвердим по|пришлём по запросу|независимых цифр|нет (?:независимых )?данных|в листе показан|показываем соседний|не объявлен|не утверждённый проект|что учесть|размеры и расстановка мебели|расстановка мебели ориентир|это прогноз|предложение архитекторов'),
    'служебные оговорки в теле листа: клиенту нужна опора на факты, а не «могут меняться»'],
  ['пересказ', 'пересказ брошюры, слоганы', 'all',
    R('слоган|девиз|по-тайски|звучит по-русски|в переводе|по самоописанию|по описанию|застройщик (?:сам )?(?:описывает|называет|задумал|формулирует)|называет себя|компани\\w+ номер один|«[A-Za-z][^»]{8,}»|играет на |по фактам это так'),
    'пересказ слоганов, названий и самоописаний застройщика вместо цифр и ценности'],
  ['служебное', 'служебные пояснения', 'all',
    R('нашей практики|наша переписка|наша сравнительная|нашей оценке|сейл-кит|sales ?kit|карточк\\w+ проекта|внутренн'),
    'внутренняя кухня (переписка, таблицы, карточка) покупателю не нужна и источником не является'],
  ['давление', 'давление, даты акций', 'all',
    R('\\bдо \\d{1,2} ' + МЕС + '|успей|не упусти|последн(?:ие|их|яя|ий) \\d|осталось \\d+ (?:квартир|юнит|лот)|ждать не стоит|работает на вас|без риска|кто зашёл|уходят первыми|вырастет на|\\+\\s?20\\s?%[^.]{0,30}(?:октябр|старт|открыт\\w+ продаж)|только до'),
    '№321/322: лимит без даты и без процента будущего роста'],
  ['юниты', 'юниты, комиссии, агент', 'all',
    R('(?:юнит|unit|лот)[а-я]*\\s*[№#]\\s*\\d|\\b[A-Z]{1,2}\\d?-\\d{1,3}\\b|комисси|агентск|брокер|вознагражден|на руки'),
    'НЕ_ДЕЛАТЬ №5, 6: номера юнитов, комиссии, «на руки» наружу не идут'],
  ['стиль', 'стиль: тире, «не X, а Y»', 'all',
    R('—| – |\\bне [^.!?;:<>]{2,50}, а [^.!?<>]{2,}'),
    'приметы ИИ: длинное тире, «не X, а Y»'],
];
const ДОМ = ['дом', '«дом» про кондо', 'all', R('(?<![\\wа-яё])дом(?:а|у|ом|е|ов|ам|ами|ах)?(?![\\wа-яё])'),
  'НЕ_ДЕЛАТЬ №28; «дом моды/ETRO» не считаем'];

export const КАТЕГОРИИ = [['длина', 'блоки длиннее порога'], ...ПРАВИЛА.map((r) => [r[0], r[1]]), ['дом', ДОМ[1]], ['повтор', 'повтор подписей']];

const ent = (s) => s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (h) => ent(h.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
const cut = (s, n = 170) => (s.length > n ? s.slice(0, n) + '…' : s);

function blocks(html) {
  let b = html.slice(html.indexOf('<body') >= 0 ? html.indexOf('<body') : 0);
  b = b.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '').replace(/<svg[\s\S]*?<\/svg>/g, '');
  const parts = b.split(/(?=<section\b|<footer\b)/);
  return parts.map((p, i) => {
    let name;
    if (i === 0) name = 'шапка';
    else if (/^<footer/.test(p)) name = 'кнопки';
    else {
      const e = p.match(/<div class="eyebrow"[^>]*>([\s\S]*?)<\/div>/);
      const h = p.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
      name = text((e ? e[1] : '') || (h ? h[1] : '') || 'блок') || 'блок';
    }
    return { name, html: p };
  });
}

function pars(h) {
  const out = [];
  for (const m of h.matchAll(/<p(\s[^>]*)?>([\s\S]*?)<\/p>/g)) {
    const cls = ((m[1] || '').match(/class="([^"]*)"/) || [])[1] || '';
    out.push({ cls, t: text(m[2]) });
  }
  return out;
}

export function metrics(html) {
  return blocks(html).map((bl) => {
    const ps = pars(bl.html);
    const prose = ps.filter((p) => !/\bsrc\b/.test(p.cls));
    const src = ps.filter((p) => /\bsrc\b/.test(p.cls));
    const lead = prose.filter((p) => /\b(lead|sub)\b/.test(p.cls));
    const plain = prose.filter((p) => !/\b(lead|sub)\b/.test(p.cls));
    const взгляд = [...bl.html.matchAll(/<h3>\s*Наш взгляд\s*<\/h3>\s*<p[^>]*>([\s\S]*?)<\/p>/g)].map((m) => text(m[1]));
    const total = text(bl.html.replace(/<p class="src"[\s\S]*?<\/p>/g, '').replace(/<i>[\s\S]*?<\/i>/g, '').replace(/<h2[\s\S]*?<\/h2>/g, '')).length;
    const h2m = bl.html.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
    return {
      name: bl.name, total, h2: h2m ? text(h2m[1]).length : 0,
      lead: Math.max(0, ...lead.map((p) => p.t.length)),
      maxP: Math.max(0, ...plain.map((p) => p.t.length)),
      взгляд: Math.max(0, ...взгляд.map((t) => t.length)),
      srcN: src.length, maxSrc: Math.max(0, ...src.map((p) => p.t.length)),
      _html: bl.html, _src: src, _prose: prose
    };
  });
}

/* → [{блок, кат, текст, why}] */
export function lint(html, { slug = '' } = {}) {
  const out = [];
  const add = (блок, кат, т, why) => out.push({ блок, кат, текст: cut(т), why });
  const П = ПОРОГИ;
  const srcAll = [];
  for (const b of metrics(html)) {
    if (b.name !== 'кнопки' && b.total > П.блок) add(b.name, 'длина', `текста в блоке ${b.total} знаков (порог ${П.блок})`, 'блок длиннее нормы «преза»');
    if (b.maxP > П.абзац) add(b.name, 'длина', `абзац ${b.maxP} зн. (порог ${П.абзац}): ` + b._prose.find((p) => p.t.length === b.maxP).t, 'длинный абзац');
    if (b.lead > П.лид) add(b.name, 'длина', `лид ${b.lead} зн. (порог ${П.лид}): ` + b._prose.find((p) => p.t.length === b.lead).t, 'длинный лид');
    if (b.взгляд > П.взгляд) add(b.name, 'длина', `«Наш взгляд» ${b.взгляд} зн. (порог ${П.взгляд})`, 'длинный «Наш взгляд»');
    if (b.maxSrc > П.подпись) add(b.name, 'длина', `подпись ${b.maxSrc} зн. (порог ${П.подпись}): ` + b._src.find((p) => p.t.length === b.maxSrc).t, 'длинная подпись-источник');
    if (b.srcN > П.подписей_в_блоке) add(b.name, 'длина', `подписей-источников в блоке: ${b.srcN} (порог ${П.подписей_в_блоке})`, 'подписи под каждой карточкой');
    for (const p of b._src) srcAll.push(p.t);
    const body = text(b._html);
    const src = b._src.map((p) => p.t).join(' | ');
    for (const [k, , where, re, why] of ПРАВИЛА) {
      if (b.name === 'кнопки' && k === 'оговорки') continue;  /* строка «условия могут меняться» в подвале есть на всех листах с эталона 08.10: не считаем */
      const hay = where === 'src' ? src : body;
      for (const m of hay.matchAll(new RegExp(re.source, re.flags + 'g'))) {
        const a = Math.max(0, m.index - 40);
        add(b.name, k, '…' + hay.slice(a, m.index + m[0].length + 40) + '…', why);
      }
    }
    if (!БЕЗ_ПРОВЕРКИ_ДОМ.has(slug)) {
      for (const m of body.matchAll(new RegExp(ДОМ[3].source, 'gi'))) {
        const ctx = body.slice(Math.max(0, m.index - 12), m.index + m[0].length + 12);
        if (/ETRO|моды/.test(ctx)) continue;
        add(b.name, 'дом', '…' + body.slice(Math.max(0, m.index - 40), m.index + 40) + '…', ДОМ[4]);
      }
    }
  }
  const cnt = new Map();
  for (const s of srcAll) cnt.set(s, (cnt.get(s) || 0) + 1);
  for (const [s, n] of cnt) if (n >= 3) add('весь лист', 'повтор', `«${s}» ×${n}`, 'одна и та же подпись под каждой карточкой');
  return out;
}

/* ---------- CLI ---------- */
const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const args = process.argv.slice(2);
  const flag = (n) => args.includes(n);
  const fileI = args.indexOf('--file'), kindI = args.indexOf('--kind');
  const skip = new Set([fileI + 1, kindI + 1].filter((i) => i > 0));
  const rest = args.filter((a, i) => !a.startsWith('-') && !skip.has(i));
  let jobs;
  if (fileI >= 0) jobs = [{ slug: args[kindI + 1] === 'villa' ? 'aileen' : 'x', file: args[fileI + 1] }];
  else {
    const all = fs.readdirSync(path.join(ROOT, 'offers')).filter((d) => fs.existsSync(path.join(ROOT, 'offers', d, 'page.htm'))).sort();
    const want = !rest.length || rest[0] === 'all' ? all : rest;
    jobs = want.map((s) => ({ slug: s, file: path.join(ROOT, 'offers', s, 'page.htm') }));
  }
  const rows = []; let total = 0;
  for (const j of jobs) {
    const html = fs.readFileSync(j.file, 'utf8');
    if (flag('--metrics')) {
      console.log('== ' + j.slug);
      console.log('блок'.padEnd(34) + ['всего', 'h2', 'лид', 'абзац', 'взгляд', 'подп', 'макс.подп'].map((x) => x.padStart(9)).join(''));
      for (const b of metrics(html)) console.log(b.name.slice(0, 33).padEnd(34) + [b.total, b.h2, b.lead, b.maxP, b.взгляд, b.srcN, b.maxSrc].map((x) => String(x).padStart(9)).join(''));
      continue;
    }
    const f = lint(html, { slug: j.slug });
    total += f.length;
    const by = {}; for (const x of f) by[x.кат] = (by[x.кат] || 0) + 1;
    rows.push({ slug: j.slug, by, n: f.length });
    if (flag('-v') || jobs.length === 1) {
      console.log('== ' + j.slug + ': ' + f.length + ' замечаний');
      for (const x of f) console.log(`  [${x.кат}] ${x.блок}: ${x.текст}`);
    }
  }
  if (!flag('--metrics')) {
    const cats = КАТЕГОРИИ.map((c) => c[0]);
    console.log('\n' + 'лист'.padEnd(18) + cats.map((c) => c.padStart(10)).join('') + '   всего');
    for (const r of rows) console.log(r.slug.padEnd(18) + cats.map((c) => String(r.by[c] || 0).padStart(10)).join('') + String(r.n).padStart(8));
    console.log('\nИтого замечаний: ' + total + '. В сборке по умолчанию предупреждение; OFFER_LINT=strict — сборка падает.');
    if (flag('--strict') && total) process.exit(1);
  }
}
