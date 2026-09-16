/* Картинка превью для мессенджеров.
   Эльнур 16.09.2026: «почему когда вставил ссылку в сообщение, не подтянулось превью?
   Все ссылки до единой должны красиво отображаться».
   Причина: страница объекта ссылалась на /img/<КОД>.jpg, а такого файла для новых
   объектов не было — мессенджер получал 404 и рисовал голую строку.
   Здесь кадр объекта из хранилища сохраняется в /img/<КОД>.jpg перед сборкой страниц. */
import fs from 'node:fs';
import path from 'node:path';
import https from 'node:https';

const ROOT = '/Users/elnurkhankishiev/plp-site';
const ENV = path.join(process.env.HOME, '.plp_site_supabase.env');

function env() {
  const out = {};
  for (const line of fs.readFileSync(ENV, 'utf8').split('\n')) {
    if (!line.includes('=') || line.trim().startsWith('#')) continue;
    const [k, v] = line.split('=');
    out[k.trim()] = v.trim().replace(/^["']|["']$/g, '');
  }
  return out;
}

function get(url, headers = {}) {
  return new Promise((res, rej) => {
    https.get(url, { headers }, r => {
      if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        return get(r.headers.location, headers).then(res, rej);
      }
      if (r.statusCode !== 200) { r.resume(); return rej(new Error('HTTP ' + r.statusCode)); }
      const chunks = [];
      r.on('data', c => chunks.push(c));
      r.on('end', () => res(Buffer.concat(chunks)));
    }).on('error', rej);
  });
}

const e = env();
const head = { apikey: e.SUPABASE_SERVICE_KEY, Authorization: 'Bearer ' + e.SUPABASE_SERVICE_KEY };
const rows = JSON.parse(await get(e.SUPABASE_URL.replace(/\/$/, '') +
  '/rest/v1/objects?select=plp_property_id,public_code,main_image_url,gallery_urls&on_site=eq.true', head));

let made = 0, skipped = 0, empty = [];
for (const o of rows) {
  const code = o.public_code || o.plp_property_id;
  const dest = path.join(ROOT, 'img', code + '.jpg');
  if (fs.existsSync(dest)) { skipped++; continue; }
  let src = o.main_image_url;
  if (!src && Array.isArray(o.gallery_urls)) src = o.gallery_urls.find(u => typeof u === 'string');
  if (!src) { empty.push(code); continue; }
  /* просим у хранилища кадр 1200 px: столько и нужно мессенджеру для крупного превью */
  const url = src.includes('/render/image/')
    ? src.replace(/([?&])width=\d+/, '$1width=1200') + (src.includes('width=') ? '' : (src.includes('?') ? '&' : '?') + 'width=1200')
    : src;
  try {
    const buf = await get(url);
    if (buf.length < 3000) throw new Error('пустой кадр');
    fs.writeFileSync(dest, buf);
    made++;
  } catch (err) {
    empty.push(code + ' (' + String(err.message).slice(0, 30) + ')');
  }
}
console.log('превью ссылок: создано ' + made + ', уже было ' + skipped +
  (empty.length ? ', без кадра ' + empty.length + ': ' + empty.slice(0, 6).join(', ') : ''));
