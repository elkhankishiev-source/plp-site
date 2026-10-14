/* 14.10.2026 Эльнур: «Мне нужен максимальный трекинг лидов и посетителей нас: сайт, квиз, бот».
   Постоянный id посетителя первой стороны (plp_vid: localStorage + cookie на год), сессия вкладки, куки Meta (_fbp, _fbc)
   и первый источник визита. Персональных данных здесь нет: номер появляется только в заявке, и уже база
   склеивает этот id с человеком (visitor_links → v_lead_track).
   Подключение: <script src="/js/track.js"></script>, затем PLPTrack.init(ключ, страница) и PLPTrack.ev('имя', 'значение'). */
(function () {
  function ck(n) { var m = (document.cookie || '').match(new RegExp('(?:^|; )' + n + '=([^;]*)')); return m ? decodeURIComponent(m[1]) : ''; }
  function setck(n, v, days) { try { document.cookie = n + '=' + encodeURIComponent(v) + '; max-age=' + (days * 86400) + '; path=/; SameSite=Lax'; } catch (e) {} }
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function rid() { try { return crypto.randomUUID().replace(/-/g, ''); } catch (e) { return Date.now().toString(36) + Math.random().toString(36).slice(2, 12); } }

  var vid = ls('plp_vid') || ck('plp_vid');
  if (!/^[A-Za-z0-9_-]{8,64}$/.test(vid || '')) vid = rid();
  ls('plp_vid', vid); setck('plp_vid', vid, 395);

  var sid = '';
  try { sid = sessionStorage.getItem('plp_sid'); if (!sid) { sid = rid().slice(0, 18); sessionStorage.setItem('plp_sid', sid); } } catch (e) { sid = 'ns' + rid().slice(0, 16); }

  var q = new URLSearchParams(location.search), utm = {};
  q.forEach(function (v, k) { if (/^utm_|^gclid$|^fbclid$|^yclid$/.test(k)) utm[k] = String(v).slice(0, 300); });

  /* _fbc: пиксель Meta сам ставит его при fbclid; если пиксель не успел или заблокирован — собираем по формату Meta */
  var fbc = ck('_fbc');
  if (!fbc && utm.fbclid) { fbc = 'fb.1.' + Date.now() + '.' + utm.fbclid; setck('_fbc', fbc, 90); }

  /* первый источник: с чего человек пришёл впервые (реклама, канал, поиск); не перетирается последующими визитами */
  var ft = null;
  try { ft = JSON.parse(ls('plp_ft') || 'null'); } catch (e) { ft = null; }
  if (!ft) {
    ft = { ts: new Date().toISOString(), page: location.pathname + (q.get('p') ? '?p=' + q.get('p') : ''), ref: (document.referrer || '').slice(0, 200) };
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'].forEach(function (k) { if (utm[k]) ft[k] = utm[k].slice(0, 80); });
    ls('plp_ft', JSON.stringify(ft));
  }
  var visits = +(ls('plp_visits') || 0);
  try { if (!sessionStorage.getItem('plp_counted')) { visits++; ls('plp_visits', String(visits)); sessionStorage.setItem('plp_counted', '1'); } } catch (e) {}

  var URL_ = '', PAGE = location.pathname, T0 = Date.now(), EV = [], timer = null;
  function flush(final) {
    if (!URL_ || !EV.length) return;
    var body = JSON.stringify({ session_id: sid, visitor_id: vid, page: PAGE, referrer: document.referrer || '',
      utm: Object.keys(utm).length ? utm : null, events: EV.splice(0, 60),
      device: (innerWidth < 700 ? 'mobile' : (innerWidth < 1100 ? 'tablet' : 'desktop')),
      lang: (document.documentElement.lang || navigator.language || '').slice(0, 8), duration_ms: Date.now() - T0 });
    try {
      if (final && navigator.sendBeacon) navigator.sendBeacon(URL_, new Blob([body], { type: 'text/plain' }));
      else fetch(URL_, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: body, keepalive: true });
    } catch (e) {}
  }

  window.PLPTrack = {
    vid: vid, sid: sid,
    init: function (key, page) {
      URL_ = 'https://api.property-library.com/siteevents?key=' + encodeURIComponent(key || '');
      if (page) PAGE = String(page).slice(0, 200);
      addEventListener('pagehide', function () { flush(true); });
      document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') flush(true); });
    },
    ev: function (name, v) {
      if (EV.length >= 60) return;
      var o = { e: String(name).slice(0, 40), t: Date.now() - T0 };
      if (v != null && v !== '') o.v = String(v).slice(0, 80);
      EV.push(o);
      clearTimeout(timer); timer = setTimeout(function () { flush(false); }, 4000);
    },
    flush: flush,
    /* для заявки: всё, что нужно склейке и будущей серверной отправке в Meta (CAPI) */
    lead: function () { return { visitor_id: vid, session_id: sid, fbp: ck('_fbp') || undefined, fbc: fbc || ck('_fbc') || undefined, first_touch: ft, visits: visits }; }
  };
})();
