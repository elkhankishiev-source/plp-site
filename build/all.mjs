/* Одна команда на всю сборку: node build/all.mjs
   Порядок важен — сначала данные и страницы, потом общие части, потом тема.
   Эльнур: «одна правка — один результат», поэтому руками ничего не досыпаем. */
import { execFileSync } from 'node:child_process';
/* 06.09: mkshared обязан идти ДО mkpages/mkdistricts/mkextra — они копируют
   стили из index.html, и при старом порядке buy/rent/районы отставали на одну
   сборку: правка общей части появлялась на них только со второго прогона. */
const steps = ['gen.mjs', 'mkshared.mjs', 'mkpages.mjs', 'mkdistricts.mjs', 'mkextra.mjs',
               'mktheme.mjs', 'mklinks.mjs'];
for (const s of steps) {
  process.stdout.write(`— ${s}\n`);
  execFileSync('node', [`build/${s}`], { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
}
console.log('сборка завершена');
