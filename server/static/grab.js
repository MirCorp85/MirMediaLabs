/* MIR MEDIA LABS · Downloader (grab.py) — identical in both lab copies.
   Link → MP3 / MP4 (+ optional stills) in the library → editor, Series studio, or a chat reference. */
(function () {
  'use strict';
  var B = location.pathname.indexOf('/mlab') === 0 ? '/mlab' : '';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mi(n) { return window.MI ? MI.html(n) : ''; }
  function api(path, body) {
    var o = { cache: 'no-store', credentials: 'same-origin' };
    if (body !== undefined) { o.method = 'POST'; o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok && !j.error) j.error = 'HTTP ' + r.status; return j; }); });
  }
  var toastT;
  function toast(t, err) { var e = $('#gr-toast'); e.textContent = t; e.className = 'toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'toast'; }, err ? 5200 : 2600); }
  function mmss(t) { t = Math.max(0, Math.round(+t || 0)); var h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = t % 60; return (h ? h + ':' + ('0' + m).slice(-2) : m) + ':' + ('0' + s).slice(-2); }
  function size(b) { return !b ? '' : b > 1048576 ? (b / 1048576).toFixed(1) + ' MB/s' : Math.round(b / 1024) + ' KB/s'; }

  /* ── theme: the lab's palette (same table as series.js) ── */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    r.setProperty('--bg', t[0]); r.setProperty('--panel', t[1]); r.setProperty('--panel2', t[2]); r.setProperty('--ink', t[3]); r.setProperty('--acc', t[4]); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/miros-prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });

  /* ── going places: framed in the lab → tell the lab page; on its own (app WebView) → navigate ── */
  var FRAMED = window.parent !== window;
  function go(msg, url) {
    if (FRAMED) return window.parent.postMessage(msg, '*');
    if (window.MMLApp && MMLApp.close && msg.mml === 'grab-close') return MMLApp.close('');
    location.href = B + url;
  }
  $('#gr-back').href = (B || '') + '/';
  $('#gr-back').addEventListener('click', function (e) { if (FRAMED || window.MMLApp) { e.preventDefault(); go({ mml: 'grab-close' }, '/'); } });
  $('#gr-editor').onclick = function () { go({ mml: 'grab-editor' }, '/editor'); };
  $('#gr-series').onclick = function () { go({ mml: 'grab-series' }, '/series'); };

  /* the lab's open chat session (project): what's grabbed or converted is filed there */
  function SESSION() { try { return localStorage.getItem('mml.session') || ''; } catch (e) { return ''; } }

  /* ── options ── */
  var OPT = { mode: 'mp3', abr: '192', q: '1080', stills: '0' }, PROBE = null;
  function chips(id, key) {
    $('#' + id).addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      OPT[key] = b.dataset.v; $$('button', this).forEach(function (x) { x.classList.toggle('on', x === b); }); showOpts();
    });
  }
  chips('gr-mode', 'mode'); chips('gr-abr', 'abr'); chips('gr-q', 'q'); chips('gr-stills', 'stills');
  function showOpts() {
    $$('[data-for="a"]').forEach(function (e) { e.hidden = OPT.mode === 'video'; });
    $$('[data-for="v"]').forEach(function (e) { e.hidden = OPT.mode === 'mp3'; });
  }
  showOpts();

  function check() {
    var u = $('#gr-u').value.trim(); if (!u) return Promise.resolve(null);
    $('#gr-pv').innerHTML = '<p class="dim">Looking at the link…</p>';
    return api('/api/grab/probe', { url: u }).then(function (d) {
      if (d.error) { PROBE = null; $('#gr-pv').innerHTML = '<p class="dim" style="color:#e5484d">' + esc(d.error) + '</p>'; return null; }
      PROBE = d; PROBE.url = u;
      $('#gr-pv').innerHTML = '<div class="gr-pv">' + (d.thumb ? '<img alt="" src="' + esc(d.thumb) + '" referrerpolicy="no-referrer">' : '') +
        '<div><b>' + esc(d.title || 'Untitled') + '</b><small>' + esc([d.uploader, d.site, d.duration ? mmss(d.duration) : (d.live ? 'live' : ''),
          d.heights && d.heights.length ? 'up to ' + d.heights[d.heights.length - 1] + 'p' : '', d.license].filter(Boolean).join(' · ')) + '</small></div></div>';
      if (d.duration && !$('#gr-e').value) $('#gr-e').placeholder = 'end ' + mmss(d.duration);
      return d;
    });
  }
  $('#gr-check').onclick = check;
  $('#gr-u').addEventListener('keydown', function (e) { if (e.key === 'Enter') start(); });
  $('#gr-u').addEventListener('paste', function () { setTimeout(check, 30); });

  function start() {
    var u = $('#gr-u').value.trim(); if (!u) return toast('paste a link first', 1);
    var b = $('#gr-go'); b.disabled = true;
    var p = PROBE && PROBE.url === u ? Promise.resolve(PROBE) : Promise.resolve(null);
    p.then(function (pv) {
      return api('/api/grab', { session: SESSION(), url: u, mode: OPT.mode, quality: OPT.q, abr: OPT.abr, stills: +OPT.stills, start: $('#gr-s').value.trim(), end: $('#gr-e').value.trim(),
        title: pv && pv.title, thumb: pv && pv.thumb });
    }).then(function (d) {
      b.disabled = false;
      if (d.error) return toast(d.error, 1);
      toast('Downloading — it lands in your library');
      $('#gr-u').value = ''; $('#gr-s').value = ''; $('#gr-e').value = ''; $('#gr-pv').innerHTML = ''; PROBE = null;
      load();
    }).catch(function () { b.disabled = false; toast('the lab didn\'t answer', 1); });
  }
  $('#gr-go').onclick = start;

  /* ── Download | Convert ── */
  function tab(t) {
    $$('#gr-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.t === t); });
    $('#gr-dl').hidden = t !== 'dl'; $('#gr-cv').hidden = t !== 'cv';
    try { localStorage.setItem('mml.grab.tab', t); } catch (e) { }
  }
  $('#gr-tabs').addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) tab(b.dataset.t); });
  try { tab(/[?&]convert\b/.test(location.search) ? 'cv' : localStorage.getItem('mml.grab.tab') || 'dl'); } catch (e) { tab('dl'); }

  /* ── converter: a file (upload or library) → MP3 / M4A / WAV / MP4 ── */
  var CV = { to: 'mp3', abr: '192', file: null, lib: null, title: '' };
  var CV_WHAT = { mp3: 'MP3 — plays everywhere; the usual pick for songs and voice-overs.',
    m4a: 'M4A (AAC) — a little smaller than MP3 at the same quality; great on iPhone.',
    wav: 'WAV — uncompressed, the biggest file; best for editing or a music engine.',
    mp4: 'MP4 (H.264) — turns MKV / WEBM / MOV / AVI into a video the editor and every phone play.' };
  function cvShow() {
    $$('[data-cv="a"]').forEach(function (e) { e.hidden = CV.to === 'wav' || CV.to === 'mp4'; });
    $('#cv-what').textContent = CV_WHAT[CV.to];
    $('#cv-src').innerHTML = CV.title ? '<div class="cv-src">' + mi(CV.lib ? 'folder' : 'upload') + '<b title="' + esc(CV.title) + '">' + esc(CV.title) + '</b>' +
      '<button class="eb sm ic" id="cv-clear" title="Pick another file">' + mi('close') + '</button></div><div class="cv-up" hidden><i></i></div>' : '';
    $('#cv-drop').hidden = !!CV.title;
    if (window.MI && MI.fill) MI.fill($('#gr-cv'));
  }
  function cvChips(id, key) {
    $('#' + id).addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      CV[key] = b.dataset.v; $$('button', this).forEach(function (x) { x.classList.toggle('on', x === b); }); cvShow();
    });
  }
  cvChips('cv-to', 'to'); cvChips('cv-abr', 'abr');
  function cvSet(file, lib, title) { CV.file = file; CV.lib = lib; CV.title = title || ''; cvShow(); }
  $('#cv-pick').onclick = function () { $('#cv-file').click(); };
  $('#cv-file').addEventListener('change', function () { var f = this.files[0]; if (f) cvSet(f, null, f.name); this.value = ''; });
  $('#cv-src').addEventListener('click', function (e) { if (e.target.closest('#cv-clear')) cvSet(null, null, ''); });
  var dz = $('#cv-drop');
  ['dragenter', 'dragover'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('over'); }); });
  ['dragleave', 'drop'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('over'); }); });
  dz.addEventListener('drop', function (e) { var f = e.dataTransfer.files[0]; if (f) cvSet(f, null, f.name); });
  $('#cv-lib').onclick = function () {   /* videos + audio already in the library (renders, downloads, uploads) */
    var m = document.createElement('div'); m.className = 'zoom lp';
    m.innerHTML = '<div class="lp-box"><div class="lp-hd"><b>Pick a file to convert</b><span class="sp"></span><button class="eb sm ic" data-lp="x">' + mi('close') + '</button></div>' +
      '<div class="lp-grid"><p class="dim">Loading your library…</p></div></div>';
    document.body.appendChild(m);
    m.addEventListener('click', function (e) {
      if (e.target === m || e.target.closest('[data-lp="x"]')) return m.remove();
      var it = e.target.closest('[data-ln]'); if (!it) return;
      m.remove(); cvSet(null, it.dataset.ln, it.title || it.dataset.ln);
    });
    Promise.all([api('/api/library?limit=100&kind=video'), api('/api/library?limit=100&kind=audio')]).then(function (rs) {
      var items = (rs[0].items || []).concat(rs[1].items || []).sort(function (a, b) { return (b.mtime || 0) - (a.mtime || 0); }), g = $('.lp-grid', m);
      if (!items.length) { g.innerHTML = '<p class="dim">No videos or audio in your library yet.</p>'; return; }
      g.innerHTML = items.map(function (it) {
        var au = it.kind === 'audio';
        return '<button class="lp-it' + (au ? ' au' : '') + '" data-ln="' + esc(it.name) + '" title="' + esc(it.prompt || it.name) + '">' +
          (au ? mi('music') + '<span>' + esc(it.prompt || it.name) + '</span>' : '<img alt="" loading="lazy" src="' + B + '/thumb/' + encodeURIComponent(it.name) + '">') + '</button>';
      }).join('');
      if (window.MI && MI.fill) MI.fill(g);
    });
  };
  $('#cv-go').onclick = function () {
    if (!CV.file && !CV.lib) return toast('choose a file first', 1);
    var b = this, fields = { session: SESSION(), to: CV.to, abr: CV.abr, start: $('#cv-s').value.trim(), end: $('#cv-e').value.trim() };
    b.disabled = true;
    var done = function (d) {
      b.disabled = false;
      if (!d || d.error) return toast((d && d.error) || 'the lab didn\'t answer', 1);
      toast('Converting — it lands in your library'); cvSet(null, null, ''); $('#cv-s').value = ''; $('#cv-e').value = ''; load();
    };
    if (CV.lib) return api('/api/grab/convert', Object.assign({ lib: CV.lib }, fields)).then(done, function () { done(null); });
    var fd = new FormData(); fd.append('file', CV.file); Object.keys(fields).forEach(function (k) { fd.append(k, fields[k]); });
    var x = new XMLHttpRequest(), bar = $('#cv-src .cv-up'); if (bar) bar.hidden = false;
    x.open('POST', B + '/api/grab/convert'); x.withCredentials = true;
    x.upload.onprogress = function (e) { if (e.lengthComputable && bar) bar.firstChild.style.width = Math.round(100 * e.loaded / e.total) + '%'; };
    x.onload = function () { var d = {}; try { d = JSON.parse(x.responseText); } catch (e) { d = { error: x.status === 413 ? 'that file is too big (600 MB max)' : 'HTTP ' + x.status }; } done(d); };
    x.onerror = function () { done(null); };
    x.send(fd);
  };
  cvShow();

  /* ── the list ── */
  var JOBS = [], timer = null;
  function fileRow(n) {
    var url = B + '/media/' + encodeURIComponent(n), au = /\.(mp3|m4a|wav)$/i.test(n), im = /\.(jpe?g|png|webp)$/i.test(n);
    var media = au ? '<audio controls preload="none" src="' + url + '"></audio>' : im ? '<img alt="" src="' + B + '/thumb/' + encodeURIComponent(n) + '">'
      : '<video muted preload="metadata" src="' + url + '#t=0.5"></video>';
    return '<div class="gr-file" data-n="' + esc(n) + '">' + media + '<span class="nm">' + esc(n) + '</span>' +
      (im ? '' : '<button class="eb sm" data-a="edit" title="Put it on the editor timeline">' + mi('scissors') + ' Editor</button>') +
      '<button class="eb sm" data-a="series" title="' + (au ? 'Use it as an episode song in the Series studio' : 'Use it in the Series studio (style frames, hero photo, song)') + '">' + mi('tv') + ' Series</button>' +
      '<button class="eb sm" data-a="ref" title="Attach it to your next chat request">' + mi('attach') + ' Attach</button>' +
      '<a class="eb sm ic" href="' + url + '?dl=1" title="Save to this device">' + mi('download') + '</a></div>';
  }
  function draw() {
    var el = $('#gr-list');
    if (!JOBS.length) { el.innerHTML = '<p class="dim">Nothing yet. Paste a link above.</p>'; return; }
    el.innerHTML = JOBS.map(function (j) {
      var live = j.status === 'queued' || j.status === 'running';
      var what = j.mode === 'convert' ? 'converted → ' + String(j.to || '').toUpperCase() : j.mode === 'mp3' ? 'MP3' : j.mode === 'video' ? 'MP4 ' + j.quality + (j.quality === 'best' ? '' : 'p') : 'MP4 + MP3';
      var st = j.status === 'failed' ? '<div class="st err">' + esc(j.error || 'failed') + '</div>'
        : j.status === 'canceled' ? '<div class="st">canceled</div>'
        : live ? '<div class="bar"><i style="width:' + Math.max(3, j.pct || 0) + '%"></i></div><div class="st">' + esc(j.stage || j.status) +
          (j.pct ? ' · ' + Math.round(j.pct) + '%' : '') + (j.speed ? ' · ' + size(j.speed) : '') + (j.eta ? ' · ' + mmss(j.eta) + ' left' : '') + '</div>'
        : '<div class="st">' + mi('check') + ' in your library</div>';
      var files = j.files || [], stills = files.filter(function (n) { return /\.(jpe?g|png|webp)$/i.test(n); }), main = files.filter(function (n) { return stills.indexOf(n) < 0; });
      return '<div class="gr-job" data-j="' + esc(j.id) + '"><div class="hd">' + mi(j.mode === 'convert' ? 'refresh' : j.mode === 'mp3' ? 'music' : 'video') + '<b title="' + esc(j.url) + '">' + esc(j.title || j.url) + '</b>' +
        '<span class="dim" style="font-size:12px">' + esc(what) + (j.start != null || j.end != null ? ' · ' + mmss(j.start || 0) + '–' + (j.end != null ? mmss(j.end) : 'end') : '') + '</span>' +
        (live ? '<button class="eb sm ic" data-a="cancel" title="Cancel">' + mi('close') + '</button>' : '') + '</div>' + st +
        (main.length ? '<div class="gr-files">' + main.map(fileRow).join('') + '</div>' : '') +
        (stills.length ? '<div class="row"><span class="lbl">Stills</span><div class="gr-stills">' + stills.map(function (n) { return '<img alt="" title="' + esc(n) + '" src="' + B + '/thumb/' + encodeURIComponent(n) + '">'; }).join('') +
          '</div><button class="eb sm" data-a="series-stills" title="Open the Series studio — pick these as style frames from the library">' + mi('palette') + ' Use as style frames</button></div>' : '') +
        '</div>';
    }).join('');
    if (window.MI && MI.fill) MI.fill(el);
  }
  function load() {
    return api('/api/grab').then(function (d) {
      if (d.error) return;
      if (d.available === false) $('#gr-pv').innerHTML = '<p class="dim" style="color:#e5484d">The downloader (yt-dlp) isn\'t installed on the lab PC.</p>';
      JOBS = d.jobs || []; draw();
      clearTimeout(timer);
      if (JOBS.some(function (j) { return j.status === 'queued' || j.status === 'running'; })) timer = setTimeout(load, 1200);
    }).catch(function () { clearTimeout(timer); timer = setTimeout(load, 4000); });
  }
  $('#gr-list').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-a]'); if (!b) return;
    var a = b.dataset.a, f = b.closest('[data-n]'), n = f && f.dataset.n, jb = b.closest('[data-j]');
    if (a === 'cancel') return api('/api/grab/' + jb.dataset.j + '/cancel', {}).then(load);
    if (a === 'edit') return go({ mml: 'grab-editor', src: 'lib:' + n }, '/editor?add=' + encodeURIComponent('lib:' + n));
    if (a === 'series' || a === 'series-stills') return go({ mml: 'grab-series', file: n }, '/series');
    if (a === 'ref') {
      if (window.MMLApp && MMLApp.useAsRef) return MMLApp.useAsRef(n);      /* phone / TV app: back to its own chat */
      return api('/api/library/' + encodeURIComponent(n) + '/use', {}).then(function (d) {
        if (d.error) return toast(d.error, 1);
        if (FRAMED) { window.parent.postMessage({ mml: 'grab-attach', ref: d }, '*'); return; }
        try { var at = JSON.parse(localStorage.getItem('mml.atts') || '[]'); at.push(d); localStorage.setItem('mml.atts', JSON.stringify(at)); } catch (e) { }
        toast('Attached — it\'s waiting in the chat box');
      });
    }
  });
  load();
})();
