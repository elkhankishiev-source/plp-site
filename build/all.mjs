/* Одна команда на всю сборку: node build/all.mjs
   Порядок важен — сначала данные и страницы, потом общие части, потом тема.
   Эльнур: «одна правка — один результат», поэтому руками ничего не досыпаем. */
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
/* 13.10.2026: корень сайта = папка над build/. Раньше был прописан ~/plp-site, и сборка из другой копии
   (рабочее дерево, клон) переписывала рабочую копию ~/plp-site. */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
/* 06.09: mkshared обязан идти ДО mkpages/mkdistricts/mkextra — они копируют
   стили из index.html, и при старом порядке buy/rent/районы отставали на одну
   сборку: правка общей части появлялась на них только со второго прогона. */
const steps = ['mkog.mjs', 'gen.mjs', 'mkshared.mjs', 'mkpages.mjs', 'mkdistricts.mjs', 'mkextra.mjs',
               'mkabout.mjs', 'mkoffers.mjs', 'mktheme.mjs', 'mkpreview.mjs', 'mklinks.mjs', 'mkga.mjs', 'mktrack.mjs', 'mkogfix.mjs',
               'mknomer.mjs'];  // 28.10 сторож одной истины: лист только по /<лист>/<номер>/ (пишет mkoffers), старые адреса = переадресации
for (const s of steps) {
  process.stdout.write(`— ${s}\n`);
  execFileSync('node', [`build/${s}`], { cwd: ROOT, stdio: 'inherit' });
  /* 09.10.2026 Эльнур: «превью ссылок всегда красивые». После mkog (фото объектов) и до gen (страницы берут
     img/og/<код>.jpg, если он есть) — фирменные карточки для НОВЫХ объектов. Упал генератор — сборку не валим. */
  if (s === 'mkog.mjs') {
    try { execFileSync('python3', ['tools/og_objects.py'], { cwd: ROOT, stdio: 'inherit', timeout: 600000 }); }
    catch (e) { process.stdout.write('⚠️ превью новых объектов не сделаны: ' + String(e.message).slice(0, 120) + '\n'); }
  }
}
/* Приёмка карточек идёт на каждой сборке — чтобы противоречия всплывали сами,
   а не когда Эльнур их заметит. Сборку не валит: это отчёт, а не запрет. */
try {
  /* 23.09.2026: перед приёмкой каталога проверяем, не уехали ли на страницы
     настоящие номера юнитов. Маскировка в базе есть, но в сборку включена не
     была — и в admin.html с add-property.html лежали PLP-MANOR-S14 и имя владельца. */
  execFileSync('python3', ['tools/privacy_check.py'],
    { cwd: ROOT, stdio: 'inherit' });
  /* 24.09.2026 Эльнур: «в разделе запросить каталог исчезала картинка».
     Два файла снёс коммит сжатия, разметка осталась звать прежние имена,
     сборка прошла молча. Теперь ссылка, пережившая файл, видна сразу. */
  execFileSync('python3', ['tools/images_check.py'],
    { cwd: ROOT, stdio: 'inherit' });
  /* 24.09.2026 Эльнур: «а разве это всё едино? не понимаю». Разметка общих
     частей вставляется из build/parts, а стили каждая страница носила свои —
     и копии тихо расходились. Теперь расхождение видно на сборке, а не глазами. */
  execFileSync('python3', ['tools/parts_check.py'],
    { cwd: ROOT, stdio: 'inherit' });
  /* 24.09.2026: поиск и тексты. Обе проверки родились из просьбы Эльнура
     «сверь сразу все страницы… нет ли ошибок в тексте, сео оптимизация».
     Держим их на сборке, иначе заголовки и описания снова уедут в обрез. */
  execFileSync('python3', ['tools/site_audit.py'],
    { cwd: ROOT, stdio: 'inherit' });
  execFileSync('python3', ['tools/text_check.py'],
    { cwd: ROOT, stdio: 'inherit' });
  execFileSync('python3', ['tools/catalog_audit.py', '--short'],
    { cwd: ROOT, stdio: 'inherit' });
} catch (e) { console.log('[приёмка] проверка не отработала'); }
/* 10.10.2026 решение №271 (Эльнур 08.10: «стандарт заполнения карточек на сайте, там до сих пор всё вразнобой»).
   Минимум публичной карточки по канону №91 — по каждой продажной карточке: каких полей нет и откуда брать.
   Отдельным шагом: если упадёт, остальная приёмка уже отработала. Сборку не валит (как вся приёмка);
   PLP_CARDS_STRICT=1 — остановить сборку, если есть карточки ниже минимума (включать по слову Эльнура). */
try {
  execFileSync('python3', ['tools/card_standard.py', '--short'].concat(process.env.PLP_CARDS_STRICT ? ['--strict'] : []),
    { cwd: ROOT, stdio: 'inherit' });
} catch (e) {
  if (process.env.PLP_CARDS_STRICT) { console.log('[стандарт карточки] есть карточки ниже минимума — сборка остановлена (PLP_CARDS_STRICT)'); process.exit(1); }
  console.log('[стандарт карточки] проверка не отработала');
}
/* 22.10.2026 Эльнур: «смотри, чтобы все презы, все страницы не расходились». Сверка витрин: цена «от» из базы против каталога
   (все страницы), листов, PDF, /predstart, квиза, offers_truth. Цена «от» разошлась с базой — сборка падает (выкладку price_watch не делает).
   Остальное (свободно, условия, «ещё 5%», проект «не существует») — отчёт строкой. Полная таблица: python3 tools/сверка_витрин.py */
try {
  execFileSync('python3', ['tools/сверка_витрин.py', '--short', '--strict'], { cwd: ROOT, stdio: 'inherit' });
} catch (e) {
  console.log('[сверка витрин] цена «от» разошлась с базой — сборка остановлена. Таблица: python3 tools/сверка_витрин.py');
  process.exit(1);
}
/* 15.09 Эльнур: «сделал для мака — телефон должен соответствовать, автоматически».
   Сверка вида (компьютер/телефон × светлая/тёмная) и кабинет на реальных данных.
   Сборку не валят — это отчёт. Быстрая сборка без них: PLP_FAST=1 node build/all.mjs */
if (!process.env.PLP_FAST) {
  for (const [tool, name] of [['tools/object_consistency.py', 'карточки'], ['tools/privacy_guard.py', 'личные данные'], ['tools/uk_path.py', 'путь объекта'], ['tools/ui_parity.py', 'вид'], ['tools/cab_check.py', 'кабинет']]) {
    try {
      execFileSync('python3', [tool, '--short'], { cwd: ROOT, stdio: 'inherit' });
    } catch (e) { /* замечания уже напечатаны строкой выше */ }
  }
}
console.log('сборка завершена');
