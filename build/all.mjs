/* Одна команда на всю сборку: node build/all.mjs
   Порядок важен — сначала данные и страницы, потом общие части, потом тема.
   Эльнур: «одна правка — один результат», поэтому руками ничего не досыпаем. */
import { execFileSync } from 'node:child_process';
/* 06.09: mkshared обязан идти ДО mkpages/mkdistricts/mkextra — они копируют
   стили из index.html, и при старом порядке buy/rent/районы отставали на одну
   сборку: правка общей части появлялась на них только со второго прогона. */
const steps = ['mkog.mjs', 'gen.mjs', 'mkshared.mjs', 'mkpages.mjs', 'mkdistricts.mjs', 'mkextra.mjs',
               'mkabout.mjs', 'mkoffers.mjs', 'mktheme.mjs', 'mkpreview.mjs', 'mklinks.mjs'];
for (const s of steps) {
  process.stdout.write(`— ${s}\n`);
  execFileSync('node', [`build/${s}`], { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
}
/* Приёмка карточек идёт на каждой сборке — чтобы противоречия всплывали сами,
   а не когда Эльнур их заметит. Сборку не валит: это отчёт, а не запрет. */
try {
  /* 23.09.2026: перед приёмкой каталога проверяем, не уехали ли на страницы
     настоящие номера юнитов. Маскировка в базе есть, но в сборку включена не
     была — и в admin.html с add-property.html лежали PLP-MANOR-S14 и имя владельца. */
  execFileSync('python3', ['tools/privacy_check.py'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
  /* 24.09.2026 Эльнур: «в разделе запросить каталог исчезала картинка».
     Два файла снёс коммит сжатия, разметка осталась звать прежние имена,
     сборка прошла молча. Теперь ссылка, пережившая файл, видна сразу. */
  execFileSync('python3', ['tools/images_check.py'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
  /* 24.09.2026 Эльнур: «а разве это всё едино? не понимаю». Разметка общих
     частей вставляется из build/parts, а стили каждая страница носила свои —
     и копии тихо расходились. Теперь расхождение видно на сборке, а не глазами. */
  execFileSync('python3', ['tools/parts_check.py'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
  /* 24.09.2026: поиск и тексты. Обе проверки родились из просьбы Эльнура
     «сверь сразу все страницы… нет ли ошибок в тексте, сео оптимизация».
     Держим их на сборке, иначе заголовки и описания снова уедут в обрез. */
  execFileSync('python3', ['tools/site_audit.py'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
  execFileSync('python3', ['tools/text_check.py'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
  execFileSync('python3', ['tools/catalog_audit.py', '--short'],
    { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
} catch (e) { console.log('[приёмка] проверка не отработала'); }
/* 15.09 Эльнур: «сделал для мака — телефон должен соответствовать, автоматически».
   Сверка вида (компьютер/телефон × светлая/тёмная) и кабинет на реальных данных.
   Сборку не валят — это отчёт. Быстрая сборка без них: PLP_FAST=1 node build/all.mjs */
if (!process.env.PLP_FAST) {
  for (const [tool, name] of [['tools/object_consistency.py', 'карточки'], ['tools/privacy_guard.py', 'личные данные'], ['tools/uk_path.py', 'путь объекта'], ['tools/ui_parity.py', 'вид'], ['tools/cab_check.py', 'кабинет']]) {
    try {
      execFileSync('python3', [tool, '--short'], { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
    } catch (e) { /* замечания уже напечатаны строкой выше */ }
  }
}
console.log('сборка завершена');
