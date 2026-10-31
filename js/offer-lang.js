/* 01.11.2026 Эльнур: «Один адрес листа, внутри переключатель RU/EN, и текст оффера переводится на той же странице.
   Вторую копию не заводим». Подключается в offers/<лист>/page.htm сборкой build/mkoffers.mjs, если рядом лежит en.json.

   Как устроено:
   - Цифры живут только в разметке листа (page.htm, русская версия). В en.json лежат слова: ключ = русский текст узла,
     где каждое число заменено на «#», значение = английский текст с местами {0}, {1}… под эти же числа по порядку.
     При переводе числа берутся из самой страницы; меняется только запись (1,41 → 1.41, 7 997 000 → 7,997,000).
   - Язык: ?lang=en|ru (у листа или у страницы-обёртки) → сохранённый выбор pl_lang → язык браузера
     (есть русский/украинский/белорусский/казахский среди языков браузера → RU, иначе EN).
     Выбор по ?lang и по кнопке запоминается в pl_lang (тот же ключ, что у переключателя сайта).
   - PDF и печать (?pdf) всегда русские: PDF собирается с этой же страницы и сверяется с ней. */
(function () {
  var Q = location.search;
  if (/[?&]pdf/.test(Q)) return;
  var top = window, inFrame = false;
  try { if (window.parent !== window && window.parent.location.host === location.host) { top = window.parent; inFrame = true; } } catch (e) {}
  function qLang(s) { var m = /[?&]lang=(ru|en)\b/i.exec(s || ''); return m ? m[1].toLowerCase() : ''; }
  function stored() { try { return localStorage.getItem('pl_lang') || ''; } catch (e) { return ''; } }
  function store(l) { try { localStorage.setItem('pl_lang', l); } catch (e) {} }
  function browser() {
    var ls = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || 'ru']);
    for (var i = 0; i < ls.length; i++) if (/^(ru|uk|be|kk)\b/i.test(ls[i])) return 'ru';
    return 'en';
  }
  var explicit = qLang(Q) || (inFrame ? qLang(top.location.search) : '');
  if (explicit) store(explicit);
  var lang = explicit || stored() || browser();
  if (lang !== 'en' && lang !== 'ru') lang = 'ru';
  var SRC = (document.currentScript && document.currentScript.getAttribute('data-en')) || 'en.json';

  var NUM = /\d+(?:[ \u00a0\u202f]\d{3})*(?:,\d+)?/g;
  function key(t) { return t.replace(NUM, '#'); }
  function enNum(n) { return n.replace(/,(\d+)$/, '.$1').replace(/[ \u00a0\u202f](?=\d{3})/g, ','); }
  var dict = null, nodes = null, cur = 'ru';
  function collect() {
    nodes = [];
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode && n.parentNode.nodeName;
        if (p === 'SCRIPT' || p === 'STYLE' || p === 'NOSCRIPT') return NodeFilter.FILTER_REJECT;
        /* русский текст или число в русской записи (30,2% · 4 800): у второго меняется только запись числа */
        return /[А-Яа-яЁё]|\d,\d|\d[ \u00a0\u202f]\d{3}/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    for (var n; (n = w.nextNode());) nodes.push({ n: n, ru: n.nodeValue });
  }
  function tr(ru) {
    var core = ru.replace(/\s+/g, ' ').trim(), lead = /^\s/.test(ru) ? ' ' : '', tail = /\s$/.test(ru) ? ' ' : '';
    if (!/[А-Яа-яЁё]/.test(core)) return lead + core.replace(NUM, enNum) + tail;
    var en = dict[key(core)];
    if (en == null) return null;
    var nums = core.match(NUM) || [];
    return lead + en.replace(/\{(\d+)\}/g, function (_, i) { return nums[+i] != null ? enNum(nums[+i]) : ''; }) + tail;
  }
  function height() {
    if (!inFrame) return;
    var w = document.querySelector('.w') || document.body;
    try { top.postMessage({ plpOfferHeight: Math.ceil(w.getBoundingClientRect().height) }, location.origin); } catch (e) {}
  }
  var loading = null;
  function load(cb) {
    if (dict) { cb(); return; }
    if (loading) { loading.push(cb); return; }
    loading = [cb];
    fetch(SRC, { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (d) { dict = d || {}; var q = loading; loading = []; q.forEach(function (f) { f(); }); });
  }
  function apply(l) {
    if (l === 'en' && !dict) { load(function () { apply('en'); }); return; }
    if (!nodes) collect();
    for (var i = 0; i < nodes.length; i++) {
      var x = nodes[i], v = l === 'en' ? tr(x.ru) : x.ru;
      if (v == null) v = x.ru;
      if (x.n.nodeValue !== v) x.n.nodeValue = v;
    }
    cur = l;
    document.documentElement.lang = l;
    document.documentElement.style.visibility = '';
    if (inFrame) { try { top.postMessage({ plpOfferLangNow: l }, location.origin); } catch (e) {} }
    height(); setTimeout(height, 400);
  }
  /* язык меняется кнопкой над листом (postMessage) или переключателем сайта (тот же pl_lang, событие storage) */
  addEventListener('message', function (e) {
    if (e.origin === location.origin && e.data && (e.data.plpLang === 'en' || e.data.plpLang === 'ru')) { store(e.data.plpLang); apply(e.data.plpLang); }
  });
  addEventListener('storage', function (e) { if (e.key === 'pl_lang' && (e.newValue === 'en' || e.newValue === 'ru') && e.newValue !== cur) apply(e.newValue); });
  window.plpOfferLang = function (l) { store(l); apply(l); };

  if (lang === 'en') {
    document.documentElement.style.visibility = 'hidden';
    setTimeout(function () { document.documentElement.style.visibility = ''; }, 2500);
    load(function () {});
    var go = function () { apply('en'); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
  } else if (inFrame) {
    try { top.postMessage({ plpOfferLangNow: 'ru' }, location.origin); } catch (e) {}
  }
})();
