/* Одна команда на всю сборку: node build/all.mjs
   Порядок важен — сначала данные и страницы, потом общие части, потом тема.
   Эльнур: «одна правка — один результат», поэтому руками ничего не досыпаем. */
import { execFileSync } from 'node:child_process';
const steps = ['gen.mjs', 'mkpages.mjs', 'mkdistricts.mjs', 'mkextra.mjs', 'mkshared.mjs', 'mktheme.mjs'];
for (const s of steps) {
  process.stdout.write(`— ${s}\n`);
  execFileSync('node', [`build/${s}`], { cwd: '/Users/elnurkhankishiev/plp-site', stdio: 'inherit' });
}
console.log('сборка завершена');
