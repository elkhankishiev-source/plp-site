/* 05.11.2026 Эльнур «го!»: запись сессий квиза (session replay) на открытой библиотеке rrweb (MIT, копия в /js/vendor/, без чужих CDN).
   Записываются не видео и не ввод, а действия на странице: что было на экране, нажатия, прокрутка, уход.
   Правила: 1) только /kviz/, включается после показа страницы, первый экран не тормозит;
   2) по правилу аналитики 21.10 (opt-out, как GA и пиксель в consent.js): пишем, пока посетитель не выбрал «Только необходимые»;
      06.11 Эльнур «го сайт: запись квиза по правилу 21.10»: до этого ждали «Принять», а плашки с 21.10 нет, записей было 0;
   3) не пишем наши проверки (utm_source test_, verify_, audit_) и роботов; 4) выборка 50% сессий;
   5) все поля ввода скрыты (maskAllInputs), форма с именем и номером (#f) не записывается вовсе, в записи на её месте пустой блок;
   6) пачки уходят в наш приёмник n8n, хранятся в закрытом хранилище 30 дней, на сайте их не видно.
   Потолок одной сессии: 2 МБ и 15 минут. */
(function () {
  if (window.PLPReplay) return;
  var LIB = '/js/vendor/rrweb-record-2.1.7.min.js';
  var URL_ = 'https://n8n-167-172-66-20.sslip.io/webhook/kviz-replay';
  var SAMPLE = 50, MAX_BYTES = 2000000, MAX_MS = 15 * 60000, PART = 60000;

  function consent() {
    try {
      var o = JSON.parse(localStorage.getItem('plp_consent') || 'null');
      if (!o || o.ver !== 1) return '';
      if (Date.now() - Date.parse(o.t) > 365 * 864e5) return '';
      return o.v || '';
    } catch (e) { return ''; }
  }
  var q = new URLSearchParams(location.search);
  var src = (q.get('utm_source') || '').toLowerCase();
  if (/^(test|verify|audit)_/.test(src)) return;
  if (/bot|crawl|spider|slurp|headlesschrome|lighthouse|facebookexternalhit|preview/i.test(navigator.userAgent || '')) return;

  var T = window.PLPTrack || {};
  var sid = T.sid || '', vid = T.vid || '';
  if (!/^[A-Za-z0-9_-]{8,40}$/.test(sid)) {
    try { sid = sessionStorage.getItem('plp_sid') || ''; } catch (e) {}
    if (!/^[A-Za-z0-9_-]{8,40}$/.test(sid)) return;
  }
  /* выборка: решение по id сессии, до загрузки библиотеки; одна и та же сессия всегда в выборке или вне её */
  var hsh = 2166136261;
  for (var i = 0; i < sid.length; i++) { hsh ^= sid.charCodeAt(i); hsh = Math.imul(hsh, 16777619) >>> 0; }
  if (hsh % 100 >= SAMPLE) return;

  var buf = [], bufBytes = 0, sent = 0, seq = 0, t0 = Date.now(), stop = null, timer = null, done = false;
  function meta(evs, fin) {
    return JSON.stringify({ sid: sid, vid: vid, seq: seq++, t0: t0, page: location.pathname + (q.get('p') ? '?p=' + q.get('p') : ''),
      src: src.slice(0, 80), cmp: (q.get('utm_campaign') || '').slice(0, 80),
      dev: innerWidth < 700 ? 'mobile' : (innerWidth < 1100 ? 'tablet' : 'desktop'), w: innerWidth, h: innerHeight, fin: !!fin, ev: evs });
  }
  function post(body, beacon) {
    try {
      if (beacon && navigator.sendBeacon && body.length < PART && navigator.sendBeacon(URL_, new Blob([body], { type: 'text/plain' }))) return;
      fetch(URL_, { method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain' }, body: body, keepalive: body.length < PART });
    } catch (e) {}
  }
  function flush(fin) {
    clearTimeout(timer); timer = null;
    if (!buf.length) return;
    var evs = buf; buf = []; bufBytes = 0;
    /* при уходе со страницы шлём кусками до 60 КБ: больше браузер при закрытии не отправит */
    var part = [], size = 0;
    for (var k = 0; k < evs.length; k++) {
      var n = JSON.stringify(evs[k]).length;
      if (part.length && size + n > PART) { post(meta(part, false), fin); part = []; size = 0; }
      part.push(evs[k]); size += n;
    }
    if (part.length) post(meta(part, fin), fin);
  }
  function end() { if (done) return; done = true; try { stop && stop(); } catch (e) {} flush(true); }
  function emit(e) {
    if (done) return;
    var n = JSON.stringify(e).length;
    sent += n;
    if (sent > MAX_BYTES || Date.now() - t0 > MAX_MS) { end(); return; }
    buf.push(e); bufBytes += n;
    /* полный снимок страницы (тип 2) уходит сразу обычным запросом, остальное раз в 10 с или по 60 КБ */
    if (e.type === 2 || bufBytes > PART) flush(false);
    else if (!timer) timer = setTimeout(function () { flush(false); }, 10000);
  }
  function start() {
    if (stop || done || start.busy) return;
    start.busy = true;
    var s = document.createElement('script'); s.src = LIB; s.async = true;
    s.onload = function () {
      try {
        if (consent() === 'necessary' || !window.rrwebRecord) return;
        t0 = Date.now();
        stop = rrwebRecord.record({ emit: emit, maskAllInputs: true, blockSelector: '#f, form, .rr-block',
          recordCanvas: false, collectFonts: false, inlineImages: false, slimDOMOptions: 'all',
          sampling: { mousemove: 100, scroll: 200, media: 800, input: 'last' } }) || null;
      } catch (e) {}
    };
    document.head.appendChild(s);
  }
  addEventListener('pagehide', function () { if (stop) flush(true); });
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden' && stop) flush(true); });

  /* согласие: нет отказа — пишем; выберет «Только необходимые» — останавливаем (проверка раз в 2 с, до 3 минут) */
  var tries = 0;
  function check() {
    var c = consent();
    if (c === 'necessary') { if (stop) end(); return; }
    if (!stop) start();
    if (++tries < 90 || stop) setTimeout(check, 2000);
  }
  function go() { setTimeout(function () { (window.requestIdleCallback || function (f) { setTimeout(f, 1); })(check); }, 1500); }
  if (document.readyState === 'complete') go(); else addEventListener('load', go);

  window.PLPReplay = { flush: function () { flush(false); }, on: function () { return !!stop; } };
})();
