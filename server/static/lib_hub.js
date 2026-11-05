/* LIBRARY HUB (Nov 5 2026, desktop only ≥861px) — the dock's Library button opens a full library page between the header and
   the dock: category sidebar (type · time · source · session · projects), live stats + charts (30-day activity, storage by
   type, top sources — every chart is clickable and filters), search, sort, grid/list views and date-grouped results.
   Phones keep the old Library tab. Uses the page's own globals (libItems, MODELS, SESS, showFile, useAsRef, mmlSocialDraft). */
(function () {
  'use strict';
  var wide = function () { return window.matchMedia('(min-width: 861px)').matches; };
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var ic = function (n, sz) { return window.MI ? MI.html(n, sz || 'sm') : ''; };
  var LSg = function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } };
  var LSs = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { } };

  var KIND = { image: ['Images', 'image', 'var(--lh-img)'], video: ['Videos', 'video', 'var(--lh-vid)'], audio: ['Audio', 'music', 'var(--lh-aud)'] };
  var PAL = ['#ff7a3d', '#4fc3c8', '#b48cff', '#7bd389', '#f2c14e', '#ff6b9a', '#6aa7ff', '#c9a27e'];
  var DAY = 86400000;

  var ALL = [], loaded = false, loading = null, el = null, shown = 0, view = [];
  var F = { kind: '', src: '', sess: null, when: '', day: null, q: '' };
  var sort = LSg('mml.lh.sort', 'new'), mode = LSg('mml.lh.mode', 'grid'), size = +LSg('mml.lh.size', '150') || 150;

  // ── CSS ───────────────────────────────────────────────────────────────────────────────────────────────────────────
  var css = document.createElement('style'); css.id = 'lh-css';
  css.textContent = [
    ':root{--lh-img:var(--acc,#ff7a3d);--lh-vid:#4fc3c8;--lh-aud:#b48cff}',
    '#mml-lh{position:fixed;left:0;right:0;z-index:40;display:grid;grid-template-columns:232px minmax(0,1fr);background:var(--bg);border-top:1px solid var(--line);font-family:var(--sans,system-ui,sans-serif);color:var(--ink)}',
    '#mml-lh *{box-sizing:border-box}',
    '#mml-lh .lh-side{border-right:1px solid var(--line);overflow:auto;padding:14px 10px 20px;background:color-mix(in srgb,var(--panel,#111) 70%,transparent)}',
    '#mml-lh .lh-sec{font:700 9.5px var(--mono,monospace);letter-spacing:.16em;color:var(--faint);padding:14px 10px 6px;text-transform:uppercase}',
    '#mml-lh .lh-sec:first-child{padding-top:2px}',
    '#mml-lh .lh-cat{display:flex;align-items:center;gap:9px;width:100%;border:0;background:none;color:var(--dim);font-size:12.5px;padding:7px 10px;border-radius:9px;cursor:pointer;text-align:left}',
    '#mml-lh .lh-cat:hover{background:color-mix(in srgb,var(--ink) 6%,transparent);color:var(--ink)}',
    '#mml-lh .lh-cat.on{background:color-mix(in srgb,var(--acc) 16%,transparent);color:var(--ink);box-shadow:inset 2px 0 0 var(--acc)}',
    '#mml-lh .lh-cat .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '#mml-lh .lh-cat .ct{font:600 10.5px var(--mono,monospace);color:var(--faint)}',
    '#mml-lh .lh-cat .dot{width:8px;height:8px;border-radius:50%;flex:none}',
    '#mml-lh .lh-cat .mi{width:15px;height:15px;flex:none}',
    '#mml-lh .lh-main{display:flex;flex-direction:column;min-width:0;min-height:0}',
    '#mml-lh .lh-bar{display:flex;align-items:center;gap:10px;padding:12px 18px;border-bottom:1px solid var(--line)}',
    '#mml-lh .lh-bar h2{margin:0;font-size:15px;letter-spacing:.06em;font-weight:800;display:flex;align-items:center;gap:8px;white-space:nowrap}',
    '#mml-lh .lh-bar .sub{font:600 11px var(--mono,monospace);color:var(--faint);white-space:nowrap}',
    '#mml-lh .lh-q{flex:1;max-width:460px;display:flex;align-items:center;gap:8px;margin-left:auto;padding:0 12px;height:34px;border:1px solid var(--line2,var(--line));border-radius:10px;background:var(--panel2,#151515)}',
    '#mml-lh .lh-q input{flex:1;border:0;background:none;color:var(--ink);font-size:13px;outline:none;min-width:0}',
    '#mml-lh .lh-q:focus-within{border-color:var(--acc)}',
    '#mml-lh select,#mml-lh .lh-ib{height:34px;border:1px solid var(--line2,var(--line));border-radius:10px;background:var(--panel2,#151515);color:var(--ink);font-size:12px;padding:0 10px;cursor:pointer}',
    '#mml-lh .lh-ib{display:inline-grid;place-items:center;padding:0 9px}',
    '#mml-lh .lh-ib.on{border-color:var(--acc);color:var(--acc)}',
    '#mml-lh .lh-seg{display:flex;gap:4px}',
    '#mml-lh input[type=range]{width:90px;accent-color:var(--acc)}',
    '#mml-lh .lh-scroll{flex:1;overflow:auto;padding:16px 18px 30px}',
    '#mml-lh .lh-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}',
    '#mml-lh .lh-kpi{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--panel,#111);cursor:pointer;position:relative;overflow:hidden}',
    '#mml-lh .lh-kpi:hover{border-color:var(--line2,var(--acc))}',
    '#mml-lh .lh-kpi.on{border-color:var(--acc)}',
    '#mml-lh .lh-kpi .k{font:700 9.5px var(--mono,monospace);letter-spacing:.14em;color:var(--faint);display:flex;align-items:center;gap:6px}',
    '#mml-lh .lh-kpi .v{font-size:24px;font-weight:800;margin-top:4px;font-variant-numeric:tabular-nums}',
    '#mml-lh .lh-kpi .s{font:500 11px var(--mono,monospace);color:var(--dim);margin-top:2px}',
    '#mml-lh .lh-kpi i.bar{position:absolute;left:0;bottom:0;height:3px;background:var(--c)}',
    '#mml-lh .lh-charts{display:grid;grid-template-columns:minmax(0,2.1fr) minmax(0,1fr) minmax(0,1.3fr);gap:10px;margin-bottom:18px}',
    '#mml-lh .lh-card{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--panel,#111);min-width:0}',
    '#mml-lh .lh-card h4{margin:0 0 10px;font:700 9.5px var(--mono,monospace);letter-spacing:.14em;color:var(--faint);display:flex;align-items:center;gap:8px}',
    '#mml-lh .lh-card h4 .lg{margin-left:auto;display:flex;gap:10px;letter-spacing:.06em}',
    '#mml-lh .lh-card h4 .lg span{display:flex;align-items:center;gap:4px}',
    '#mml-lh .lh-card h4 .lg i{width:7px;height:7px;border-radius:2px;display:inline-block}',
    '#mml-lh svg .b{cursor:pointer;transition:opacity .15s}',
    '#mml-lh svg .b:hover{opacity:.75}',
    '#mml-lh svg .ax{font:500 9px var(--mono,monospace);fill:var(--faint)}',
    '#mml-lh .lh-donut{display:flex;align-items:center;gap:14px}',
    '#mml-lh .lh-donut ul{list-style:none;margin:0;padding:0;flex:1;min-width:0}',
    '#mml-lh .lh-donut li{display:flex;align-items:center;gap:7px;font-size:12px;padding:4px 0;cursor:pointer;color:var(--dim)}',
    '#mml-lh .lh-donut li:hover{color:var(--ink)}',
    '#mml-lh .lh-donut li b{margin-left:auto;font:600 11px var(--mono,monospace);color:var(--ink);white-space:nowrap}',
    '#mml-lh .lh-donut svg{flex:none}',
    '#mml-lh .lh-donut li i{width:8px;height:8px;border-radius:50%}',
    '#mml-lh .lh-hb{display:flex;align-items:center;gap:8px;font-size:11.5px;padding:3px 0;cursor:pointer;color:var(--dim)}',
    '#mml-lh .lh-hb:hover{color:var(--ink)}',
    '#mml-lh .lh-hb .n{width:78px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '#mml-lh .lh-hb .t{flex:1;height:8px;border-radius:4px;background:color-mix(in srgb,var(--ink) 7%,transparent);overflow:hidden}',
    '#mml-lh .lh-hb .t i{display:block;height:100%;border-radius:4px}',
    '#mml-lh .lh-hb b{font:600 10.5px var(--mono,monospace);color:var(--ink);width:34px;text-align:right}',
    '#mml-lh .lh-chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 12px}',
    '#mml-lh .lh-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid color-mix(in srgb,var(--acc) 50%,transparent);background:color-mix(in srgb,var(--acc) 12%,transparent);color:var(--ink);border-radius:20px;padding:4px 6px 4px 11px;font-size:11.5px;cursor:pointer}',
    '#mml-lh .lh-chip span{opacity:.7}',
    '#mml-lh .lh-chip:hover span{opacity:1}',
    '#mml-lh .lh-clear{border:0;background:none;color:var(--dim);font-size:11.5px;cursor:pointer;text-decoration:underline}',
    '#mml-lh .lh-res{font:600 11px var(--mono,monospace);color:var(--faint);margin-left:auto}',
    '#mml-lh .lh-day{display:flex;align-items:baseline;gap:10px;margin:16px 0 8px;font-size:13px;font-weight:700;position:sticky;top:-16px;z-index:2;background:var(--bg);padding:6px 0}',
    '#mml-lh .lh-day small{font:600 10.5px var(--mono,monospace);color:var(--faint)}',
    '#mml-lh .lh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--ts,150px),1fr));gap:8px}',
    '#mml-lh .lh-t{position:relative;aspect-ratio:1;border-radius:11px;overflow:hidden;background:var(--panel2,#151515);border:1px solid var(--line);cursor:pointer}',
    '#mml-lh .lh-t:hover{border-color:var(--c);box-shadow:0 6px 22px -12px var(--c)}',
    '#mml-lh .lh-t img{width:100%;height:100%;object-fit:cover;display:block}',
    '#mml-lh .lh-t .au{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;background:radial-gradient(circle at 50% 40%,color-mix(in srgb,var(--c) 26%,transparent),transparent 70%)}',
    '#mml-lh .lh-t .au .wv{display:flex;align-items:center;gap:2px;height:28px}',
    '#mml-lh .lh-t .au .wv i{width:3px;border-radius:2px;background:var(--c);opacity:.8}',
    '#mml-lh .lh-t .bd{position:absolute;top:6px;left:6px;display:flex;gap:4px}',
    '#mml-lh .lh-t .bd span{font:700 9px var(--mono,monospace);letter-spacing:.08em;padding:3px 6px;border-radius:6px;background:#000b;color:#fff;display:flex;align-items:center;gap:3px}',
    '#mml-lh .lh-t .bd .src{background:var(--c);color:#000}',
    '#mml-lh .lh-t .ac{position:absolute;top:6px;right:6px;display:flex;gap:4px;opacity:0;transition:opacity .15s}',
    '#mml-lh .lh-t:hover .ac{opacity:1}',
    '#mml-lh .lh-t .ac button,#mml-lh .lh-t .ac a{width:26px;height:26px;display:grid;place-items:center;border:0;border-radius:7px;background:#000c;color:#fff;cursor:pointer}',
    '#mml-lh .lh-t .ac button:hover,#mml-lh .lh-t .ac a:hover{background:var(--acc)}',
    '#mml-lh .lh-t .cp{position:absolute;left:0;right:0;bottom:0;padding:18px 8px 6px;background:linear-gradient(transparent,#000d);color:#fff;font-size:10.5px;line-height:1.3;opacity:0;transition:opacity .15s;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}',
    '#mml-lh .lh-t:hover .cp{opacity:1}',
    '#mml-lh table{width:100%;border-collapse:collapse;font-size:12px}',
    '#mml-lh th{font:700 9.5px var(--mono,monospace);letter-spacing:.12em;color:var(--faint);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}',
    '#mml-lh td{padding:5px 8px;border-bottom:1px solid color-mix(in srgb,var(--line) 60%,transparent);color:var(--dim);white-space:nowrap}',
    '#mml-lh tr.r{cursor:pointer}#mml-lh tr.r:hover td{background:color-mix(in srgb,var(--ink) 5%,transparent);color:var(--ink)}',
    '#mml-lh td.nm{color:var(--ink);max-width:340px;overflow:hidden;text-overflow:ellipsis}',
    '#mml-lh td .tb{width:34px;height:34px;border-radius:7px;object-fit:cover;display:block;background:var(--panel2)}',
    '#mml-lh td .tb.a{display:grid;place-items:center;color:var(--lh-aud)}',
    '#mml-lh td .pr{max-width:320px;overflow:hidden;text-overflow:ellipsis;display:block}',
    '#mml-lh .lh-empty{padding:60px 20px;text-align:center;color:var(--faint);font-size:13px}',
    '#mml-lh .lh-load{padding:60px 20px;text-align:center;color:var(--dim);font:600 12px var(--mono,monospace)}',
    '#mml-lh .lh-sent{height:40px}',
    '@media (max-width:1280px){#mml-lh .lh-charts{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}#mml-lh .lh-charts .lh-card:first-child{grid-column:1/-1}}',
    '@media (max-width:860px){#mml-lh{display:none!important}}'
  ].join('\n');
  document.head.appendChild(css);

  // ── data ──────────────────────────────────────────────────────────────────────────────────────────────────────────
  function fetchAll() {
    if (loading) return loading;
    var acc = [];
    var page = function (off) {
      return fetch('api/library?kind=&offset=' + off + '&limit=200', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
        acc = acc.concat(j.items || []);
        if (el) { var l = $('.lh-load', el); if (l) l.textContent = 'Loading library… ' + acc.length + ' / ' + (j.total || '?'); }
        if ((j.items || []).length && acc.length < (j.total || 0)) return page(acc.length);
      });
    };
    loading = page(0).then(function () { ALL = acc; loaded = true; loading = null; }).catch(function () { loading = null; });
    return loading;
  }
  var srcColor = {};
  function colorOf(m) {
    var md = (window.MODELS || {})[m]; if (md && md.color) return md.color;
    if (!srcColor[m]) { var h = 0; String(m || '?').split('').forEach(function (c) { h = (h * 31 + c.charCodeAt(0)) >>> 0; }); srcColor[m] = PAL[h % PAL.length]; }
    return srcColor[m];
  }
  function srcName(m) { if (!m) return 'Other'; var S = window.SHORT || {}; return S[m] || String(m).replace(/[-_]/g, ' ').toUpperCase(); }
  function fmtB(b) { if (!b) return '0 B'; var u = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.min(4, Math.floor(Math.log(b) / Math.log(1024))); return (b / Math.pow(1024, i)).toFixed(i > 1 ? 1 : 0) + ' ' + u[i]; }
  function dayKey(t) { var d = new Date(t * 1000); d.setHours(0, 0, 0, 0); return d.getTime(); }
  function today0() { var d = new Date(); d.setHours(0, 0, 0, 0); return d.getTime(); }
  function dayLabel(k) {
    var t = today0(); if (k === t) return 'Today'; if (k === t - DAY) return 'Yesterday';
    var d = new Date(k); if (t - k < 7 * DAY) return d.toLocaleDateString(undefined, { weekday: 'long' });
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
  }
  function sessOf(it) { return it.session || ''; }
  function sessName(id) { if (!id) return 'General'; var s = ((window.SESS || {}).list || []).find(function (x) { return x.id === id; }); return s ? s.name : 'Session ' + id.slice(0, 6); }

  function match(it, skip) {
    if (skip !== 'kind' && F.kind && it.kind !== F.kind) return false;
    if (skip !== 'src' && F.src && it.model !== F.src) return false;
    if (skip !== 'sess' && F.sess != null && sessOf(it) !== F.sess) return false;
    if (skip !== 'when' && F.when) { var age = today0() - dayKey(it.mtime); if (F.when === 'today' && age > 0) return false; if (F.when === 'week' && age >= 7 * DAY) return false; if (F.when === 'month' && age >= 30 * DAY) return false; if (F.when === 'older' && age < 30 * DAY) return false; }
    if (skip !== 'day' && F.day != null && dayKey(it.mtime) !== F.day) return false;
    if (F.q) { var h = (it.name + ' ' + (it.prompt || '') + ' ' + (it.model || '') + ' ' + srcName(it.model)).toLowerCase(); if (F.q.split(/\s+/).some(function (w) { return w && h.indexOf(w) < 0; })) return false; }
    return true;
  }
  function sorted(L) {
    var f = { new: function (a, b) { return b.mtime - a.mtime; }, old: function (a, b) { return a.mtime - b.mtime; }, big: function (a, b) { return (b.size || 0) - (a.size || 0); },
              name: function (a, b) { return a.name.localeCompare(b.name); }, src: function (a, b) { return srcName(a.model).localeCompare(srcName(b.model)) || b.mtime - a.mtime; } }[sort] || function () { return 0; };
    return L.slice().sort(f);
  }

  // ── shell ─────────────────────────────────────────────────────────────────────────────────────────────────────────
  function place() {
    if (!el) return;
    var top = $('header.top'), nav = $('nav.tabs');
    var t = top ? top.getBoundingClientRect().bottom : 0, b = nav && nav.offsetParent ? innerHeight - nav.getBoundingClientRect().top : 0;
    el.style.top = Math.max(0, t) + 'px'; el.style.bottom = Math.max(0, b) + 'px';
  }
  function navOn(on) {
    var b = document.querySelector('nav.tabs button[data-t="library"]');
    document.querySelectorAll('nav.tabs button').forEach(function (x) { x.classList.toggle('on', on ? x === b : x.dataset.t === 'create'); });
  }
  function open() {
    if (el) return;
    document.body.classList.remove('lc-libwide');
    el = document.createElement('div'); el.id = 'mml-lh';
    el.innerHTML = '<aside class="lh-side"></aside><section class="lh-main">' +
      '<div class="lh-bar"><h2>' + ic('grid') + ' LIBRARY</h2><span class="sub" id="lh-sub"></span>' +
      '<label class="lh-q">' + ic('search') + '<input id="lh-q" placeholder="Search names, prompts, tools…   ( / )" autocomplete="off"></label>' +
      '<select id="lh-sort" title="Sort"><option value="new">Newest first</option><option value="old">Oldest first</option><option value="big">Largest first</option><option value="name">Name A–Z</option><option value="src">By source</option></select>' +
      '<div class="lh-seg"><button class="lh-ib" data-mode="grid" title="Grid view">' + ic('grid') + '</button><button class="lh-ib" data-mode="list" title="List view">' + ic('list') + '</button></div>' +
      '<input type="range" id="lh-size" min="100" max="260" step="10" title="Thumbnail size">' +
      '<button class="lh-ib" id="lh-x" title="Close (Esc)">' + ic('close') + '</button></div>' +
      '<div class="lh-scroll"><div class="lh-load">Loading library…</div></div></section>';
    document.body.appendChild(el);
    place(); navOn(true);
    $('#lh-sort', el).value = sort; $('#lh-size', el).value = size; el.style.setProperty('--ts', size + 'px');
    var qt; $('#lh-q', el).oninput = function (e) { clearTimeout(qt); qt = setTimeout(function () { F.q = e.target.value.trim().toLowerCase(); draw(); }, 140); };
    $('#lh-sort', el).onchange = function (e) { sort = e.target.value; LSs('mml.lh.sort', sort); draw(); };
    $('#lh-size', el).oninput = function (e) { size = +e.target.value; LSs('mml.lh.size', size); el.style.setProperty('--ts', size + 'px'); };
    el.querySelectorAll('[data-mode]').forEach(function (b) { b.onclick = function () { mode = b.dataset.mode; LSs('mml.lh.mode', mode); draw(); }; });
    $('#lh-x', el).onclick = close;
    window.MI && MI.hydrate && MI.hydrate(el);
    (loaded ? Promise.resolve() : fetchAll()).then(draw);
    if (loaded) fetchAll().then(function () { if (el) draw(true); });   // refresh in the background
  }
  function close() {
    if (!el) return;
    el.remove(); el = null; navOn(false);
    var m = $('#more'); if (m && m.dataset.lhHid) { delete m.dataset.lhHid; }
    try { loadLib(true); } catch (e) { }                       // give the side library its own list back
  }
  window.mmlLibHub = { open: open, close: close, refresh: function () { fetchAll().then(function () { if (el) draw(true); }); } };

  // ── draw ──────────────────────────────────────────────────────────────────────────────────────────────────────────
  function cat(key, val, label, count, lead, on) {
    return '<button class="lh-cat' + (on ? ' on' : '') + '" data-f="' + key + '" data-v="' + esc(val) + '">' + lead + '<span class="nm">' + esc(label) + '</span><span class="ct">' + count + '</span></button>';
  }
  function count(fn, skip) { var n = 0; for (var i = 0; i < ALL.length; i++) if (match(ALL[i], skip) && fn(ALL[i])) n++; return n; }
  function drawSide() {
    var s = $('.lh-side', el), h = '';
    h += '<div class="lh-sec">Library</div>';
    h += cat('kind', '', 'Everything', count(function () { return true; }, 'kind'), ic('layers'), !F.kind);
    Object.keys(KIND).forEach(function (k) { h += cat('kind', k, KIND[k][0], count(function (it) { return it.kind === k; }, 'kind'), '<i class="dot" style="background:' + KIND[k][2] + '"></i>', F.kind === k); });
    h += '<div class="lh-sec">When</div>';
    [['', 'Any time', 'clock'], ['today', 'Today', 'sun'], ['week', 'Last 7 days', 'activity'], ['month', 'Last 30 days', 'activity'], ['older', 'Older', 'box']].forEach(function (w) {
      var F0 = F.when; F.when = w[0]; var n = count(function () { return true; }, 'day'); F.when = F0;
      h += cat('when', w[0], w[1], n, ic(w[2]), F.when === w[0] && F.day == null);
    });
    var src = {}; ALL.forEach(function (it) { if (match(it, 'src')) src[it.model || ''] = (src[it.model || ''] || 0) + 1; });
    var sk = Object.keys(src).sort(function (a, b) { return src[b] - src[a]; });
    h += '<div class="lh-sec">Sources · ' + sk.length + '</div>';
    h += cat('src', '', 'All sources', ALL.filter(function (it) { return match(it, 'src'); }).length, ic('sparkle'), !F.src);
    sk.forEach(function (m) { h += cat('src', m, srcName(m), src[m], '<i class="dot" style="background:' + colorOf(m) + '"></i>', F.src === m); });
    var ses = {}; ALL.forEach(function (it) { if (match(it, 'sess')) ses[sessOf(it)] = (ses[sessOf(it)] || 0) + 1; });
    var sids = Object.keys(ses).sort(function (a, b) { return a === '' ? -1 : b === '' ? 1 : ses[b] - ses[a]; });
    h += '<div class="lh-sec">Sessions</div>';
    h += cat('sess', '*', 'All sessions', ALL.filter(function (it) { return match(it, 'sess'); }).length, ic('folder'), F.sess == null);
    sids.forEach(function (id) { h += cat('sess', id, sessName(id), ses[id], ic(id ? 'folder' : 'star'), F.sess === id); });
    h += '<div class="lh-sec">Projects</div>';
    h += '<button class="lh-cat" id="lh-proj">' + ic('film') + '<span class="nm">Productions & series</span>' + ic('chevron-right') + '</button>';
    s.innerHTML = h;
    s.querySelectorAll('[data-f]').forEach(function (b) {
      b.onclick = function () {
        var k = b.dataset.f, v = b.dataset.v;
        if (k === 'sess') F.sess = v === '*' ? null : v; else F[k] = v;
        if (k === 'when') F.day = null;
        draw();
      };
    });
    $('#lh-proj', s).onclick = function () { window.mmlProjects && mmlProjects(); };
  }

  function kpis() {
    var base = ALL.filter(function (it) { return match(it, 'kind'); });
    var tot = { n: base.length, b: 0 }, by = {};
    Object.keys(KIND).forEach(function (k) { by[k] = { n: 0, b: 0 }; });
    base.forEach(function (it) { tot.b += it.size || 0; if (by[it.kind]) { by[it.kind].n++; by[it.kind].b += it.size || 0; } });
    var wk = base.filter(function (it) { return today0() - dayKey(it.mtime) < 7 * DAY; }).length;
    var card = function (k, label, icon, v, s, c, frac) {
      return '<div class="lh-kpi' + (F.kind === k ? ' on' : '') + '" data-k="' + k + '" style="--c:' + c + '"><div class="k">' + ic(icon) + label + '</div><div class="v">' + v.toLocaleString() + '</div><div class="s">' + s + '</div><i class="bar" style="width:' + Math.round(frac * 100) + '%"></i></div>';
    };
    return '<div class="lh-stats">' +
      card('', 'ALL FILES', 'layers', tot.n, fmtB(tot.b) + ' · ' + wk + ' this week', 'var(--acc)', 1) +
      Object.keys(KIND).map(function (k) { return card(k, KIND[k][0].toUpperCase(), KIND[k][1], by[k].n, fmtB(by[k].b), KIND[k][2], tot.n ? by[k].n / tot.n : 0); }).join('') + '</div>';
  }

  function activity() {
    // the activity chart ignores the time filters so it can be used to pick a day
    var N = 30, t0 = today0(), days = [], base = ALL.filter(function (it) { var w = F.when, d = F.day; F.when = ''; F.day = null; var r = match(it); F.when = w; F.day = d; return r; });
    for (var i = N - 1; i >= 0; i--) days.push({ k: t0 - i * DAY, image: 0, video: 0, audio: 0, n: 0 });
    var idx = {}; days.forEach(function (d, i) { idx[d.k] = i; });
    base.forEach(function (it) { var i = idx[dayKey(it.mtime)]; if (i == null) return; var d = days[i]; if (d[it.kind] != null) d[it.kind]++; d.n++; });
    var max = Math.max(1, Math.max.apply(null, days.map(function (d) { return d.n; })));
    var W = 600, H = 120, P = 18, bw = (W - P) / N, g = '';
    [0.5, 1].forEach(function (f) { var y = H - 14 - (H - 24) * f; g += '<line x1="' + P + '" x2="' + W + '" y1="' + y + '" y2="' + y + '" stroke="var(--line)" stroke-dasharray="2 3"/><text class="ax" x="0" y="' + (y + 3) + '">' + Math.round(max * f) + '</text>'; });
    days.forEach(function (d, i) {
      var x = P + i * bw + 1.5, y = H - 14, sel = F.day === d.k;
      ['image', 'video', 'audio'].forEach(function (k) {
        if (!d[k]) return; var h = (H - 24) * d[k] / max; y -= h;
        g += '<rect class="b" data-day="' + d.k + '" x="' + x + '" y="' + y + '" width="' + Math.max(2, bw - 3) + '" height="' + h + '" rx="1.5" fill="' + KIND[k][2] + '" opacity="' + (F.day == null || sel ? 1 : .3) + '"/>';
      });
      g += '<rect class="b" data-day="' + d.k + '" x="' + (P + i * bw) + '" y="0" width="' + bw + '" height="' + (H - 14) + '" fill="transparent"><title>' + dayLabel(d.k) + ' — ' + d.n + ' files (' + d.image + ' img · ' + d.video + ' vid · ' + d.audio + ' audio)</title></rect>';
      if (i % 5 === 0 || i === N - 1) g += '<text class="ax" x="' + (x + bw / 2 - 1.5) + '" y="' + (H - 2) + '" text-anchor="middle">' + new Date(d.k).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }) + '</text>';
    });
    var lg = Object.keys(KIND).map(function (k) { return '<span><i style="background:' + KIND[k][2] + '"></i>' + KIND[k][0] + '</span>'; }).join('');
    return '<div class="lh-card"><h4>' + ic('chart') + 'ACTIVITY · LAST 30 DAYS<span class="lg">' + lg + '</span></h4><svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="display:block">' + g + '</svg></div>';
  }

  function storage() {
    var base = ALL.filter(function (it) { return match(it, 'kind'); }), by = {}, tot = 0;
    base.forEach(function (it) { by[it.kind] = (by[it.kind] || 0) + (it.size || 0); tot += it.size || 0; });
    var R = 42, C = 2 * Math.PI * R, off = 0, arcs = '';
    Object.keys(KIND).forEach(function (k) {
      var f = tot ? (by[k] || 0) / tot : 0; if (!f) return;
      arcs += '<circle class="b" data-k="' + k + '" r="' + R + '" cx="60" cy="60" fill="none" stroke="' + KIND[k][2] + '" stroke-width="' + (F.kind === k ? 16 : 12) + '" stroke-dasharray="' + (f * C - 1.5) + ' ' + C + '" stroke-dashoffset="' + (-off * C) + '" transform="rotate(-90 60 60)"><title>' + KIND[k][0] + ' · ' + fmtB(by[k]) + '</title></circle>';
      off += f;
    });
    var li = Object.keys(KIND).map(function (k) { return '<li data-k="' + k + '"><i style="background:' + KIND[k][2] + '"></i>' + KIND[k][0] + '<b>' + fmtB(by[k] || 0) + '</b></li>'; }).join('');
    return '<div class="lh-card"><h4>' + ic('server') + 'STORAGE</h4><div class="lh-donut"><svg viewBox="0 0 120 120" width="112" height="112">' +
      '<circle r="' + R + '" cx="60" cy="60" fill="none" stroke="var(--line)" stroke-width="12"/>' + arcs +
      '<text x="60" y="58" text-anchor="middle" style="font:800 14px var(--sans,system-ui);fill:var(--ink)">' + fmtB(tot).split(' ')[0] + '</text>' +
      '<text x="60" y="73" text-anchor="middle" class="ax">' + (fmtB(tot).split(' ')[1] || '') + '</text></svg><ul>' + li + '</ul></div></div>';
  }

  function sources() {
    var c = {}; ALL.forEach(function (it) { if (match(it, 'src')) c[it.model || ''] = (c[it.model || ''] || 0) + 1; });
    var k = Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).slice(0, 7), max = k.length ? c[k[0]] : 1;
    return '<div class="lh-card"><h4>' + ic('sparkle') + 'TOP SOURCES</h4>' + (k.length ? k.map(function (m) {
      return '<div class="lh-hb" data-src="' + esc(m) + '" style="' + (F.src && F.src !== m ? 'opacity:.45' : '') + '"><span class="n">' + esc(srcName(m)) + '</span><span class="t"><i style="width:' + Math.max(3, c[m] / max * 100) + '%;background:' + colorOf(m) + '"></i></span><b>' + c[m] + '</b></div>';
    }).join('') : '<div class="lh-empty" style="padding:20px">—</div>') + '</div>';
  }

  function chips() {
    var c = [];
    if (F.kind) c.push(['kind', KIND[F.kind][0]]);
    if (F.when) c.push(['when', { today: 'Today', week: 'Last 7 days', month: 'Last 30 days', older: 'Older' }[F.when]]);
    if (F.day != null) c.push(['day', dayLabel(F.day)]);
    if (F.src) c.push(['src', srcName(F.src)]);
    if (F.sess != null) c.push(['sess', sessName(F.sess)]);
    if (F.q) c.push(['q', '“' + F.q + '”']);
    return '<div class="lh-chips">' + c.map(function (x) { return '<span class="lh-chip" data-x="' + x[0] + '">' + esc(x[1]) + '<span>' + ic('close') + '</span></span>'; }).join('') +
      (c.length > 1 ? '<button class="lh-clear" id="lh-clr">Clear all</button>' : '') + '<span class="lh-res">' + view.length.toLocaleString() + ' file' + (view.length === 1 ? '' : 's') + '</span></div>';
  }

  function wave(name) { var h = 0, s = ''; for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0; for (var j = 0; j < 14; j++) { h = (h * 1103515245 + 12345) >>> 0; s += '<i style="height:' + (6 + h % 22) + 'px"></i>'; } return s; }
  function tileHTML(it, i) {
    var c = colorOf(it.model), n = encodeURIComponent(it.name), K = KIND[it.kind] || KIND.image;
    var body = it.kind === 'audio' ? '<div class="au"><div class="wv">' + wave(it.name) + '</div><span style="font-size:10.5px;color:var(--dim);max-width:90%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(it.name) + '</span></div>'
      : '<img loading="lazy" src="thumb/' + n + '" alt="" onerror="this.style.visibility=\'hidden\'">';
    return '<div class="lh-t" data-i="' + i + '" style="--c:' + c + '" title="' + esc(it.name) + '">' + body +
      '<div class="bd"><span class="src">' + esc(srcName(it.model)) + '</span>' + (it.kind !== 'image' ? '<span>' + ic(K[1]) + '</span>' : '') + '</div>' +
      '<div class="ac"><button data-use="' + i + '" title="Use in your next message">' + ic('plus') + '</button>' +
      (it.kind !== 'audio' ? '<button data-vir="' + i + '" title="Send to VIRAL-Ω">' + ic('trending-up') + '</button>' : '') +
      '<a href="media/' + n + '?dl=1" title="Download" data-dl="1">' + ic('download') + '</a></div>' +
      (it.prompt ? '<div class="cp">' + esc(it.prompt) + '</div>' : '') + '</div>';
  }
  function rowHTML(it, i) {
    var n = encodeURIComponent(it.name), d = new Date(it.mtime * 1000);
    return '<tr class="r" data-i="' + i + '"><td>' + (it.kind === 'audio' ? '<span class="tb a">' + ic('music') + '</span>' : '<img class="tb" loading="lazy" src="thumb/' + n + '" alt="">') + '</td>' +
      '<td class="nm">' + esc(it.name) + '</td><td><span style="display:inline-flex;align-items:center;gap:6px"><i style="width:7px;height:7px;border-radius:50%;background:' + colorOf(it.model) + '"></i>' + esc(srcName(it.model)) + '</span></td>' +
      '<td>' + (KIND[it.kind] || ['—'])[0] + '</td><td>' + fmtB(it.size) + '</td><td>' + d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '</td>' +
      '<td><span class="pr">' + esc(it.prompt || '') + '</span></td></tr>';
  }

  var CHUNK = 160;
  function more() {
    var box = $('#lh-res', el); if (!box) return;
    var end = Math.min(view.length, shown + CHUNK), h = '';
    if (mode === 'list') {
      for (var i = shown; i < end; i++) h += rowHTML(view[i], i);
      $('tbody', box).insertAdjacentHTML('beforeend', h);
    } else {
      var grp = sort === 'new' || sort === 'old', last = shown ? (grp ? dayKey(view[shown - 1].mtime) : 0) : null, cur = box.lastElementChild && box.lastElementChild.classList.contains('lh-grid') ? box.lastElementChild : null;
      for (var j = shown; j < end; j++) {
        var it = view[j];
        if (grp) {
          var k = dayKey(it.mtime);
          if (k !== last) {
            var cnt = 0; for (var z = j; z < view.length && dayKey(view[z].mtime) === k; z++) cnt++;
            if (h) { cur ? cur.insertAdjacentHTML('beforeend', h) : 0; h = ''; }
            box.insertAdjacentHTML('beforeend', '<div class="lh-day">' + dayLabel(k) + '<small>' + cnt + ' file' + (cnt === 1 ? '' : 's') + '</small></div><div class="lh-grid"></div>');
            cur = box.lastElementChild; last = k;
          }
        } else if (!cur) { box.insertAdjacentHTML('beforeend', '<div class="lh-grid"></div>'); cur = box.lastElementChild; }
        h += tileHTML(it, j);
      }
      if (h && cur) cur.insertAdjacentHTML('beforeend', h);
    }
    shown = end;
    window.MI && MI.hydrate && MI.hydrate(box);
    $('.lh-sent', el).style.display = shown < view.length ? 'block' : 'none';
  }

  function draw(keepScroll) {
    if (!el) return;
    if (!loaded) { $('.lh-scroll', el).innerHTML = '<div class="lh-load">Could not load the library — try again.</div>'; return; }
    var sc = $('.lh-scroll', el), st = keepScroll ? sc.scrollTop : 0;
    view = sorted(ALL.filter(function (it) { return match(it); }));
    var totB = ALL.reduce(function (a, it) { return a + (it.size || 0); }, 0);
    $('#lh-sub', el).textContent = ALL.length.toLocaleString() + ' files · ' + fmtB(totB);
    el.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b.dataset.mode === mode); });
    $('#lh-size', el).style.display = mode === 'grid' ? '' : 'none';
    drawSide();
    sc.innerHTML = kpis() + '<div class="lh-charts">' + activity() + storage() + sources() + '</div>' + chips() +
      (view.length ? (mode === 'list' ? '<div id="lh-res"><table><thead><tr><th></th><th data-s="name">NAME</th><th data-s="src">SOURCE</th><th>TYPE</th><th data-s="big">SIZE</th><th data-s="new">DATE</th><th>PROMPT</th></tr></thead><tbody></tbody></table></div>' : '<div id="lh-res"></div>')
        : '<div class="lh-empty">' + ic('search', 'lg') + '<br>No files match. <button class="lh-clear" id="lh-clr2">Clear filters</button></div>') +
      '<div class="lh-sent"></div>';
    shown = 0; if (view.length) more();
    sc.scrollTop = st;
    window.MI && MI.hydrate && MI.hydrate(el);
    wire(sc);
  }

  function clearAll() { F = { kind: '', src: '', sess: null, when: '', day: null, q: '' }; var q = $('#lh-q', el); if (q) q.value = ''; draw(); }
  function openItem(i) {
    var it = view[i]; if (!it) return;
    try { libItems = view.slice(); var m = $('#more'); if (m) m.style.display = 'none'; showFile(it.name, it.model); } catch (e) { window.open('media/' + encodeURIComponent(it.name), '_blank'); }
  }
  function wire(sc) {
    sc.querySelectorAll('.lh-kpi').forEach(function (k) { k.onclick = function () { F.kind = F.kind === k.dataset.k ? '' : k.dataset.k; draw(true); }; });
    sc.querySelectorAll('.lh-donut [data-k]').forEach(function (k) { k.onclick = function () { F.kind = F.kind === k.dataset.k ? '' : k.dataset.k; draw(true); }; });
    sc.querySelectorAll('[data-day]').forEach(function (b) { b.onclick = function () { var d = +b.dataset.day; F.day = F.day === d ? null : d; F.when = ''; draw(true); }; });
    sc.querySelectorAll('[data-src]').forEach(function (b) { b.onclick = function () { F.src = F.src === b.dataset.src ? '' : b.dataset.src; draw(true); }; });
    sc.querySelectorAll('.lh-chip').forEach(function (c) { c.onclick = function () { var x = c.dataset.x; if (x === 'sess') F.sess = null; else if (x === 'day') F.day = null; else { F[x] = ''; if (x === 'q') $('#lh-q', el).value = ''; } draw(true); }; });
    [$('#lh-clr', sc), $('#lh-clr2', sc)].forEach(function (b) { if (b) b.onclick = clearAll; });
    sc.querySelectorAll('th[data-s]').forEach(function (th) { th.onclick = function () { sort = th.dataset.s; LSs('mml.lh.sort', sort); $('#lh-sort', el).value = sort; draw(true); }; });
    var res = $('#lh-res', sc);
    if (res) res.onclick = function (e) {
      var u = e.target.closest('[data-use]'), v = e.target.closest('[data-vir]');
      if (e.target.closest('[data-dl]')) return;
      if (u) { e.stopPropagation(); try { useAsRef(view[+u.dataset.use].name); } catch (x) { } return; }
      if (v) { e.stopPropagation(); try { mmlSocialDraft(view[+v.dataset.vir].name); } catch (x) { } return; }
      var t = e.target.closest('[data-i]'); if (t) openItem(+t.dataset.i);
    };
    var sent = $('.lh-sent', sc);
    if (sent && 'IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (en) { if (en[0].isIntersecting && el && shown < view.length) more(); }, { root: sc, rootMargin: '600px' });
      io.observe(sent);
    }
  }

  // ── hooks into the page ───────────────────────────────────────────────────────────────────────────────────────────
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('nav.tabs button');
    if (!b || !wide()) return;
    if (b.dataset.t === 'library') { e.preventDefault(); e.stopImmediatePropagation(); el ? close() : open(); return; }
    if (el) close();                                          // any other dock button leaves the library
  }, true);
  document.addEventListener('keydown', function (e) {
    if (!el) return;
    var lb = document.getElementById('lb'), inLb = lb && lb.classList.contains('on'), a = document.activeElement, typing = a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);
    if (e.key === 'Escape' && !inLb) { if (typing && a.id === 'lh-q' && a.value) { a.value = ''; F.q = ''; draw(); } else close(); }
    if (e.key === '/' && !typing && !inLb) { e.preventDefault(); $('#lh-q', el).focus(); }
  });
  addEventListener('resize', function () { if (el && !wide()) close(); place(); });
  // lightbox delete / new renders → refresh the hub's data
  var _load = window.loadLib;
  if (typeof _load === 'function') {
    var rt = null;
    window.loadLib = function () {
      var r = _load.apply(this, arguments);
      if (el && !(document.getElementById('lb') || {}).classList.contains('on')) { clearTimeout(rt); rt = setTimeout(function () { fetchAll().then(function () { if (el) draw(true); }); }, 400); }
      return r;
    };
  }
  var _home = window.goHome;
  if (typeof _home === 'function') window.goHome = function () { close(); return _home.apply(this, arguments); };
})();
