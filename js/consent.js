/* 16.10.2026 Эльнур «доработай!»: согласие на cookies по закону Таиланда о персональных данных (PDPA).
   Принятый подход: плашка согласия (consent banner) с выбором «Принять / Только необходимые»
   и режим согласия (consent mode): пока человек не нажал «Принять», Google Analytics и пиксель Meta
   не загружаются вовсе. Выбор хранится в localStorage (plp_consent) год, потом спрашиваем снова.
   Страница сама только объявляет, что у неё есть: window.PLP_GA (метка PLP:GA, build/mkga.mjs)
   и window.PLP_PIXEL (метка PLP:PIXEL, build/mktrack.mjs). Грузит их только этот файл.
   Отказ: Lead с квиза в Meta не уходит (там стоит проверка window.fbq), generate_lead в GA остаётся в dataLayer
   и никуда не отправляется. Изменить выбор: PLPConsent.open() (кнопка в privacy.html, раздел 5). */
(function () {
  if (window.PLPConsent) return;
  var KEY = 'plp_consent', VER = 1, DAYS = 365;
  var TEST = location.protocol === 'file:' || /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])$/.test(location.hostname) || navigator.webdriver;

  function read() {
    try {
      var o = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!o || o.ver !== VER || (o.v !== 'all' && o.v !== 'necessary')) return null;
      if (Date.now() - Date.parse(o.t) > DAYS * 864e5) return null;
      return o.v;
    } catch (e) { return null; }
  }
  function write(v) { try { localStorage.setItem(KEY, JSON.stringify({ v: v, t: new Date().toISOString(), ver: VER })); } catch (e) {} }

  var loaded = false;
  function loadAll() {
    if (loaded) return; loaded = true;
    /* Google Analytics 4: режим согласия Google (consent mode v2), до этого места gtag.js не грузился */
    var ga = window.PLP_GA;
    if (ga) {
      window.dataLayer = window.dataLayer || [];
      if (typeof window.gtag !== 'function') window.gtag = function () { dataLayer.push(arguments); };
      gtag('consent', 'update', { ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'granted', analytics_storage: 'granted' });
      gtag('js', new Date()); gtag('config', ga);
      var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(ga);
      document.head.appendChild(s);
    }
    /* Пиксель Meta: только PageView здесь; Lead шлёт сам квиз после отправки анкеты. Тестовые заходы не шлём (как раньше). */
    var px = window.PLP_PIXEL;
    if (px && !TEST) {
      /* 22.10.2026 Эльнур «го»: качество сопоставления событий Meta (Event Match Quality, PageView 6,1 из 10).
         Как советует Meta: (1) куки _fbc из fbclid ставим сразу на входе, формат fb.1.<мс>.<fbclid>;
         (2) external_id = постоянный id посетителя первой стороны (plp_vid, тот же, что у js/track.js и в заявке),
         пиксель сам хэширует его SHA-256, сервер заявок шлёт в Meta тот же хэш (sitelead.mjs, CAPI).
         Номер и имя здесь не передаём: они появляются только в квизе при заявке (kviz/index.html, PLPPixelUser). */
      fbcFromClick();
      var vid = visitorId();
      !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
      if (vid) fbq('init', px, { external_id: vid }); else fbq('init', px);
      fbq('track', 'PageView');
    }
  }

  function ck(n) { var m = (document.cookie || '').match(new RegExp('(?:^|; )' + n + '=([^;]*)')); return m ? decodeURIComponent(m[1]) : ''; }
  /* id посетителя: тот же ключ и формат, что в js/track.js (там он заводится первым, если скрипт есть на странице) */
  function visitorId() {
    var v = '';
    try { v = (window.PLPTrack && PLPTrack.vid) || localStorage.getItem('plp_vid') || ''; } catch (e) {}
    if (!v) v = ck('plp_vid');
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(v || '')) {
      try { v = crypto.randomUUID().replace(/-/g, ''); } catch (e) { v = Date.now().toString(36) + Math.random().toString(36).slice(2, 12); }
    }
    try { localStorage.setItem('plp_vid', v); } catch (e) {}
    try { document.cookie = 'plp_vid=' + encodeURIComponent(v) + '; max-age=' + (395 * 86400) + '; path=/; SameSite=Lax'; } catch (e) {}
    return v;
  }
  /* _fbc: новый клик по рекламе (новый fbclid) обновляет куки, старый не трогаем; домен как у самого пикселя */
  function fbcFromClick() {
    var id = '';
    try { id = new URLSearchParams(location.search).get('fbclid') || ''; } catch (e) {}
    if (!id) return;
    var cur = ck('_fbc');
    if (cur && cur.slice(-(id.length + 1)) === '.' + id) return;
    var dom = /(^|\.)property-library\.com$/.test(location.hostname) ? '; domain=.property-library.com' : '';
    try { document.cookie = '_fbc=' + encodeURIComponent('fb.1.' + Date.now() + '.' + id) + '; max-age=' + (90 * 86400) + '; path=/; SameSite=Lax' + dom; } catch (e) {}
  }

  /* отказ после согласия: уже загруженное не выгрузить, поэтому стираем их cookies и перезагружаем страницу */
  function wipe() {
    var host = location.hostname.replace(/^www\./, '');
    (document.cookie || '').split(';').forEach(function (c) {
      var n = c.split('=')[0].trim();
      if (/^(_ga|_gid|_gat|_fbp|_fbc)/.test(n)) {
        ['', '; domain=' + host, '; domain=.' + host].forEach(function (d) { document.cookie = n + '=; max-age=0; path=/' + d; });
      }
    });
  }

  var T = {
    ru: { t: 'Сайт использует cookies. Необходимые нужны для работы страниц. Аналитику Google и пиксель Meta для рекламы включаем только с вашего согласия.',
          more: 'Подробнее', yes: 'Принять', no: 'Только необходимые', aria: 'Согласие на cookies' },
    en: { t: 'This site uses cookies. Essential ones keep the pages working. Google Analytics and the Meta Pixel for ads run only with your consent.',
          more: 'Details', yes: 'Accept', no: 'Essential only', aria: 'Cookie consent' }
  };
  function lang() {
    try { var l = localStorage.getItem('pl_lang') || localStorage.getItem('plp_lang'); if (l === 'en' || l === 'ru') return l; } catch (e) {}
    return /^en/i.test(document.documentElement.lang || '') ? 'en' : 'ru';
  }

  var box = null;
  function hide() {
    if (box && box.parentNode) box.parentNode.removeChild(box);
    box = null; document.documentElement.classList.remove('plp-cb-on');
  }
  function show() {
    if (box || !document.body) return;
    var L = T[lang()];
    if (!document.getElementById('plp-cb-css')) {
      var st = document.createElement('style'); st.id = 'plp-cb-css';
      st.textContent =
        '.plp-cb{position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:72;max-width:640px;margin:0 auto;' +
        'background:#1f1d19;color:#f3f1ea;border-radius:16px;padding:14px 16px;box-shadow:0 12px 36px rgba(0,0,0,.28);' +
        'font:500 13.5px/1.45 Manrope,system-ui,-apple-system,sans-serif;display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}' +
        '.plp-cb p{margin:0;flex:1 1 300px}.plp-cb a{color:#d2d5b3;text-decoration:underline}' +
        '.plp-cb .b{display:flex;gap:8px;flex:0 0 auto;margin-left:auto}' +
        '.plp-cb button{font:inherit;font-weight:700;border-radius:999px;padding:9px 16px;cursor:pointer;border:1px solid #6b6759;background:transparent;color:#f3f1ea;white-space:nowrap}' +
        '.plp-cb button.y{background:#d2d5b3;border-color:#d2d5b3;color:#1f1d19}' +
        'html.plp-cb-on body{padding-bottom:calc(var(--plp-cb-h,120px) + 16px)}' +
        'html.plp-cb-on .fab,html.plp-cb-on .fabwrap,html.plp-cb-on .tray{bottom:calc(var(--plp-cb-h,120px) + 24px)!important}' +
        'html.plp-cb-on #toTop{bottom:calc(var(--plp-cb-h,120px) + 84px)!important}' +
        '@media (max-width:600px){.plp-cb{left:8px;right:8px;bottom:calc(8px + env(safe-area-inset-bottom,0px));font-size:11.5px;line-height:1.35;padding:9px 12px;border-radius:12px;gap:7px 10px}' +
        '.plp-cb p{flex:1 1 100%}.plp-cb .b{width:100%;gap:6px}.plp-cb button{flex:1;font-size:12px;padding:7px 10px}}';
      document.head.appendChild(st);
    }
    box = document.createElement('div');
    box.className = 'plp-cb'; box.setAttribute('role', 'region'); box.setAttribute('aria-label', L.aria);
    box.innerHTML = '<p>' + L.t + ' <a href="/privacy.html#cookies">' + L.more + '</a></p>' +
      '<div class="b"><button type="button" class="n">' + L.no + '</button><button type="button" class="y">' + L.yes + '</button></div>';
    box.querySelector('.y').onclick = function () { write('all'); hide(); loadAll(); };
    box.querySelector('.n').onclick = function () {
      var was = loaded; write('necessary'); hide();
      if (was) { wipe(); location.reload(); }
    };
    document.body.appendChild(box);
    var fit = function () { if (box) document.documentElement.style.setProperty('--plp-cb-h', box.offsetHeight + 'px'); };
    fit(); addEventListener('resize', fit);
    document.documentElement.classList.add('plp-cb-on');
  }

  window.PLPConsent = { get: read, open: show, granted: function () { return read() === 'all'; } };

  /* 21.10.2026 Эльнур «как делают продвинутые компании, нам тоже надо, го»: после плашки 16.10 Meta перестала видеть заходы
     (клики 45 в день, заходов 2–6, было 34 из 41), группы объявлений ушли в обучение с 0 конверсий, расход упал втрое.
     Как у конкурентов и до 16.10: аналитика и пиксель грузятся сразу (opt-out), плашку не показываем.
     Отказ остаётся: privacy.html, раздел 5, кнопка PLPConsent.open() → «Только необходимые» — после этого не грузим.
     Откат: вернуть прежние 4 строки (git show 0e0e0e0:js/consent.js). */
  var v = read();
  if (v !== 'necessary') loadAll();
})();
