/* MIR MEDIA LABS · Series studio — IDENTICAL in both lab copies (standalone :5400 and MirOS /mlab).
   Setup (format · style · length · song) → style bible → cast (character builder: hero, turnaround, expressions,
   voice) → world → episodes. A musical episode is song-first: the writer lays the lyrics on the format's beats, the
   song is made, cut into bar-aligned shots, and every shot is generated TO its slice of the song (mouths follow the
   vocal) — "continue" shots start on the last frames of the one before, "cut" shots start on a new first frame.
   The shots are joined under the one continuous master song. Every render goes through the lab's own /api/generate
   (queue, rights, one-at-a-time) using the request /api/series/<id>/plan writes; /attach files the result back.
   Engine names never appear here. */
(function () {
  'use strict';
  var B = location.pathname.indexOf('/mlab') === 0 ? '/mlab' : '';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mi(n) { return window.MI ? MI.html(n) : ''; }
  function rid() { return Math.random().toString(36).slice(2, 14).replace(/[^a-z0-9]/g, 'x').padEnd(12, 'a'); }
  function api(path, body) {
    var o = { cache: 'no-store', credentials: 'same-origin' };
    if (body !== undefined) { o.method = 'POST'; o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok && !j.error) j.error = 'HTTP ' + r.status; if (r.status === 409) j.busy = true; return j; }); });
  }
  function ago(t) { var s = Math.max(0, Date.now() / 1000 - t); return s < 60 ? Math.round(s) + ' s ago' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : new Date(t * 1000).toLocaleString(); }
  function dur(s) { s = Math.max(0, Math.round(s || 0)); return s < 90 ? s + ' s' : s < 5400 ? Math.round(s / 60) + ' min' : (s / 3600).toFixed(1) + ' h'; }
  var toastT;
  function toast(t, err) { var e = $('#se-toast'); e.textContent = t; e.className = 'toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'toast'; }, err ? 5200 : 2600); }
  function ref(n) { return n ? B + '/refs/' + encodeURIComponent(n) : ''; }
  function lib(n) { return n ? B + '/media/' + encodeURIComponent(n) : ''; }
  function mmss(t) { t = Math.max(0, +t || 0); return Math.floor(t / 60) + ':' + ('0' + Math.floor(t % 60)).slice(-2); }

  /* ── theme: the lab's palette ── */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    r.setProperty('--bg', t[0]); r.setProperty('--panel', t[1]); r.setProperty('--panel2', t[2]); r.setProperty('--ink', t[3]); r.setProperty('--acc', t[4]); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/miros-prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });
  var FRAMED = window.parent !== window;
  $('#se-back').href = (B || '') + '/';
  $('#se-back').addEventListener('click', function (e) { if (FRAMED) { e.preventDefault(); window.parent.postMessage({ mml: 'series-close' }, '*'); } else if (window.MMLApp) { e.preventDefault(); MMLApp.close(''); } });

  var S = null, LIST = [], TAB = 'setup', STYLE_REFS = [], VOICES = [], JOBS = {}, saveT = null, filePurpose = null;
  var P = { styles: [], structures: [], lengths: [], aspects: [], character: [], object: [], song: [] };
  var OPEN = {};                         /* which character / object builders are expanded */
  var OPENCH = {};                       /* phone: which episode shots are open for editing */
  var RUN = null, RUNSIG = '', HIST = { log: [], versions: [] };   /* the background run (server-side, crash-safe) */
  function slug(v) { return String(v).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }
  function pv(key) { var f = (P.previews || {})[key]; return f ? B + '/static/series/samples/' + f : ''; }
  function pvTag(key, cls) {
    var u = pv(key); if (!u) return '';
    if (/\.(mp3|m4a|ogg|wav)$/.test(u)) return '<span class="pva" data-au="' + u + '" title="Listen to an example">' + mi('play') + '</span>';
    return (/\.mp4$/.test(u) ? '<video class="' + (cls || 'pv') + '" src="' + u + '" muted loop playsinline autoplay></video>' : '<img class="' + (cls || 'pv') + '" src="' + u + '" loading="lazy">') +
      (cls ? '' : '<span class="pvz" title="See it bigger">' + mi('search') + '</span>');
  }
  /* plain "what it does" lines (series_help.py): one per field, one per option */
  function H(k) { return (P.help || {})[k] || { desc: '', opts: {} }; }
  function odesc(k, v) { return ((H(k).opts || {})[String(v)]) || ''; }
  function curDesc(k, cur) { return (Array.isArray(cur) ? cur : cur == null || cur === '' ? [] : [cur]).map(function (v) { return odesc(k, v); }).filter(Boolean).join(' · '); }
  function helpLine(k, cur) {
    var d = H(k).desc, c = curDesc(k, cur);
    return (d || Object.keys(H(k).opts || {}).length) ? '<p class="fhelp">' + esc(d) + ' <b class="odesc" data-od="' + k + '" data-cur="' + esc(c) + '">' + esc(c) + '</b></p>' : '';
  }
  function typing() { var a = document.activeElement; return a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) && a.type !== 'range'; }

  /* the run lives on the server; the page only watches it */
  function pollRun() {
    if (!S || document.hidden) return;
    api('/api/series/' + S.id + '/run').then(function (r) {
      if (!r || r.error) return;
      RUN = r;
      var run = r.run || {}, sig = [run.state, (run.done || []).length, run.step && run.step.key, JSON.stringify(r.recognising || {})].join('|');
      var changed = sig !== RUNSIG; RUNSIG = sig;
      var b = $('#se-runbadge'); b.hidden = !(run.state === 'running' || run.state === 'paused'); b.textContent = run.state === 'paused' ? '!' : '●'; b.className = 'badge ' + (run.state || '');
      if (changed && !typing()) return open(S.id).then(function () { if (TAB === 'hist') loadHist(); });
      drawRunBits();
      if (TAB === 'hist' && changed) loadHist();
    });
  }
  setInterval(pollRun, 4000);
  function loadHist() {
    return Promise.all([api('/api/series/' + S.id + '/log?limit=200'), api('/api/series/' + S.id + '/versions')]).then(function (a) {
      HIST.log = (a[0].events || []).reverse(); HIST.versions = a[1].versions || []; drawHist();
    });
  }

  /* ── load / save ── */
  function loadList(pick) {
    return api('/api/series').then(function (j) {
      LIST = j.series || [];
      var sel = $('#se-pick');
      sel.innerHTML = LIST.map(function (s) { return '<option value="' + s.id + '">' + esc(s.name) + '</option>'; }).join('');
      var id = pick || (S && S.id) || (localStorage.getItem('mml.series') || '') || (LIST[0] && LIST[0].id);
      if (!LIST.some(function (s) { return s.id === id; })) id = LIST[0] && LIST[0].id;
      $('#se-empty').hidden = !!LIST.length; $('#se-main').hidden = !LIST.length; sel.hidden = !LIST.length;
      if (id) { sel.value = id; return open(id); }
    });
  }
  function open(id) {
    return api('/api/series/' + id).then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); try { localStorage.setItem('mml.series', id); } catch (e) { } draw(); QUEUE = []; pollQueue(); });
  }
  function fixup() {
    S.setup = S.setup || { structure: 'musical', style: 'animated3d', length: 120, aspect: '16:9', clip: 10, song: { genre: 'nursery rhyme', bpm: 100, mood: 'happy', vocal: 'solo lead', lang: 'English' } };
    S.setup.song = S.setup.song || {};
    S.objects = S.objects || [];
    (S.characters || []).concat(S.objects).forEach(function (c) { c.traits = c.traits || {}; });
  }
  function payload() {   /* chunk edits travel as chunk_edits (the map itself is server-owned) */
    (S.episodes || []).forEach(function (e) {
      if (e.chunks) { e.chunk_edits = {}; e.chunks.forEach(function (c) { e.chunk_edits[c.i] = { shot: c.shot, link: c.link, singer: c.singer }; }); }
    });
    return S;
  }
  function save(now) {
    clearTimeout(saveT); $('#se-save').textContent = 'saving…';
    var go = function () {
      return api('/api/series', payload()).then(function (d) {
        if (d.error) { $('#se-save').textContent = ''; return toast(d.error, 1); }
        S = d; fixup(); $('#se-save').textContent = 'saved';
        (S.characters || []).forEach(function (c) { var e = $('[data-c="' + c.id + '"] .built'); if (e) e.textContent = c.built || 'Pick options below — the description writes itself.'; });
        (S.objects || []).forEach(function (o) { var e = $('[data-o="' + o.id + '"] .built'); if (e) e.textContent = o.built || 'Pick options below — the description writes itself.'; });
        var o = LIST.find(function (x) { return x.id === d.id; }); if (o && o.name !== d.name) { o.name = d.name; loadList(d.id); }
      });
    };
    if (now) return go();
    saveT = setTimeout(go, 700);
    return Promise.resolve();
  }

  /* ── drawing ── */
  function draw() {
    $('#se-name').value = S.name || '';
    $('#se-style').value = S.style_prompt || '';
    $('#se-analysis').textContent = S.style_analysis || '';
    $('#se-style-refs').innerHTML = STYLE_REFS.map(function (r) { return '<img src="' + ref(r) + '">'; }).join('');
    drawSetup(); drawCast(); drawLocs(); drawObjs(); drawEps(); drawRunBits(); if (TAB === 'hist') drawHist(); if (TAB === 'assets') drawAssets();
    $$('#se-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.t === TAB); });
    $$('section[data-p]').forEach(function (p) { p.hidden = p.dataset.p !== TAB; });
    if (window.MI && MI.fill) MI.fill(document);
  }
  function pic(src, cap, wide, isVideo, sq) {
    var m = src ? (isVideo ? '<video src="' + src + '" muted loop playsinline preload="metadata"></video>' : '<img src="' + src + '" loading="lazy">') : '<span>' + esc(cap) + ' — not made yet</span>';
    return '<div class="pic' + (wide ? ' wide' : '') + (sq ? ' sq' : '') + '">' + (src ? '<span class="cap">' + esc(cap) + '</span>' : '') + m + '</div>';
  }

  /* Setup: format · style · length · song */
  function beatBar(beats) {
    var col = { sing: 'var(--acc)', action: 'color-mix(in srgb,var(--ink) 35%,transparent)', establish: 'color-mix(in srgb,var(--ink) 20%,transparent)', dialogue: '#5aa9ff' };
    return '<div class="beats">' + (beats || []).map(function (b) { return '<i style="flex:' + b[1] + ';background:' + (col[b[2]] || col.action) + '" title="' + esc(b[0] + ' · ' + b[2]) + '"></i>'; }).join('') + '</div>';
  }
  function chips(id, opts, cur, fmt) {
    var k = id.slice(4);
    $(id).innerHTML = opts.map(function (o) {
      var p = pvTag(k + '__' + slug(o)), au = p.indexOf('class="pva"') >= 0;
      return '<button data-a="su" data-k="' + k + '" data-v="' + esc(o) + '" class="' + (String(o) === String(cur) ? 'on' : '') + (p && !au ? ' haspv' : '') + '" title="' + esc(odesc(k, o)) + '">' + (au ? '' : p) + '<span>' + esc(fmt ? fmt(o) : o) + '</span>' + (au ? p : '') + '</button>';
    }).join('');
    underRow($(id).closest('.row'), helpLine(k, cur));
  }
  function underRow(row, html) {   /* a help line directly below a setup row (kept in step with redraws) */
    var n = row.nextElementSibling;
    if (!n || !n.classList.contains('suhelp')) { n = document.createElement('div'); n.className = 'suhelp'; row.parentNode.insertBefore(n, row.nextSibling); }
    n.innerHTML = html;
  }
  function drawSetup() {
    if (!P.styles.length) return;
    var su = S.setup;
    $('#su-struct').innerHTML = P.structures.map(function (s) {
      var beats = s.id === 'custom' ? (su.beats || []) : s.beats;
      return '<button class="tile' + (su.structure === s.id ? ' on' : '') + '" data-a="struct" data-v="' + s.id + '"><b>' + esc(s.name) + '</b><span>' + esc(s.blurb) + '</span>' + beatBar(beats) + '</button>';
    }).join('');
    var bb = $('#su-beats'); bb.hidden = su.structure !== 'custom';
    if (su.structure === 'custom') {
      bb.innerHTML = (su.beats || []).map(function (b, i) {
        return '<div class="row beat" data-b="' + i + '"><input data-bf="0" value="' + esc(b[0]) + '" placeholder="Beat name">' +
          '<select data-bf="2">' + ['sing', 'action', 'establish'].map(function (k) { return '<option' + (b[2] === k ? ' selected' : '') + '>' + k + '</option>'; }).join('') + '</select>' +
          '<input data-bf="1" type="range" min="2" max="40" value="' + Math.round(b[1] * 100) + '" title="share of the runtime">' +
          '<button class="eb ic sm" data-a="beat-del">' + mi('trash') + '</button></div>';
      }).join('') + '<button class="eb sm" data-a="beat-add">' + mi('plus') + ' Add beat</button>';
    }
    $('#su-style').innerHTML = P.styles.map(function (s) {
      return '<button class="tile st' + (su.style === s.id ? ' on' : '') + '" data-a="style" data-v="' + s.id + '"><div class="thumb">' + pvTag('style_' + s.id, 'tv') + '</div><b>' + esc(s.name) + '</b><span>' + esc(s.blurb) + '</span></button>';
    }).join('');
    var cs = P.styles.find(function (x) { return x.id === su.style; });   /* phone: tiles drop their blurb, the picked one is spelled out */
    underRow($('#su-style'), cs ? '<p class="fhelp phone"><b class="odesc">' + esc(cs.name) + '</b> — ' + esc(cs.blurb) + '</p>' : '');
    chips('#su-len', P.lengths, su.length, function (v) { return v < 60 ? v + ' s' : (v / 60) + (v % 60 ? '' : '') + ' min'; });
    chips('#su-aspect', P.aspects, su.aspect);
    chips('#su-clip', [6, 8, 10, 12], su.clip || 10, function (v) { return '~' + v + ' s'; });
    chips('#su-join', ['soft', 'cut'], su.join || 'soft', function (v) { return { soft: 'soft dissolve on cuts', cut: 'hard cuts' }[v]; });
    chips('#su-res', ['draft', 'standard', 'high', 'max'], su.res || 'standard', function (v) { return { draft: 'draft (fast test)', standard: 'standard', high: 'high', max: 'max 768p (slow)' }[v]; });
    var shots = Math.round(su.length / (su.clip || 10)), song = Math.round(su.length / 120 * 25), cuts = Math.ceil(shots / 2.5),
      per = { draft: 2.5, standard: 4.5, high: 10, max: 16 }[su.res || 'standard'];
    $('#su-est').innerHTML = mi('hourglass') + ' About <b>' + shots + ' shots</b> · song ≈ ' + song + ' min · first frames ≈ ' + Math.round(cuts * 0.6) + ' min · shots ≈ ' + Math.round(shots * per) + ' min — <b>≈ ' + Math.round((song + cuts * 0.6 + shots * per) / 6) / 10 + ' h</b> of render time on this PC.';
    $('#su-song').innerHTML = P.song.map(function (f) {
      var v = su.song[f.k];
      if (f.type === 'range') return '<div class="row"><span class="lbl">' + esc(f.label) + '</span><input type="range" data-ss="' + f.k + '" min="' + f.range[0] + '" max="' + f.range[1] + '" value="' + (v || f.range[2]) + '"><b class="rv">' + (v || f.range[2]) + '</b></div><div class="suhelp">' + helpLine(f.k, null) + '</div>';
      return '<div class="row"><span class="lbl">' + esc(f.label) + '</span><div class="chips">' + f.opts.map(function (o) {
        return '<button data-a="song" data-k="' + f.k + '" data-v="' + esc(o) + '" class="' + (o === v ? 'on' : '') + '" title="' + esc(odesc(f.k, o)) + '"><span>' + esc(o) + '</span>' + pvTag(f.k + '__' + slug(o)) + '</button>';
      }).join('') + '</div></div><div class="suhelp">' + helpLine(f.k, v) + '</div>';
    }).join('');
  }

  /* Cast: the character builder */
  function voiceOpts(v) {
    return '<option value="">— speaking voice —</option>' + VOICES.map(function (x) { var id = x.id || x; return '<option value="' + esc(id) + '"' + (id === v ? ' selected' : '') + '>' + esc(x.label || x.name || id) + '</option>'; }).join('');
  }
  function field(c, f) {
    var t = c.traits || {}, v = t[f.k];
    if (f.type === 'swatch') return f.opts.map(function (o) { return '<button class="sw' + (o === v ? ' on' : '') + '" data-a="tr" data-k="' + f.k + '" data-v="' + o + '" style="background:' + o + '" title="' + esc(odesc(f.k, o) || o) + '"></button>'; }).join('');
    if (f.type === 'range') return '<input type="range" data-tk="' + f.k + '" min="' + f.range[0] + '" max="' + f.range[1] + '" value="' + (v || f.range[2]) + '"><b class="rv">' + (v || f.range[2]) + '</b> <span class="dim">' + esc(f.unit || '') + '</span>';
    if (f.type === 'text') return '<input data-tk="' + f.k + '" value="' + esc(v || '') + '" placeholder="' + esc(f.ph || '') + '">';
    var many = f.type === 'many';
    return f.opts.map(function (o) {
      var on = many ? (v || []).indexOf(o) >= 0 : o === v, p = pvTag(f.k + '__' + slug(o));
      var au = p.indexOf('class="pva"') >= 0;
      return '<button class="' + (on ? 'on' : '') + (p && !au ? ' haspv' : '') + '" data-a="tr" data-k="' + f.k + '" data-v="' + esc(o) + '"' + (many ? ' data-m="1"' : '') + ' title="' + esc(odesc(f.k, o)) + '">' + (au ? '' : p) + '<span>' + esc(o) + '</span>' + (au ? p : '') + '</button>';
    }).join('');
  }
  function builder(c, spec) {
    var groups = [];
    (spec || P.character).forEach(function (f) { var g = groups.find(function (x) { return x.n === f.group; }); if (!g) groups.push(g = { n: f.group, f: [] }); g.f.push(f); });
    return '<div class="build">' + groups.map(function (g, gi) {
      return '<details' + (gi === 0 ? ' open' : '') + '><summary>' + esc(g.n) + '</summary>' + g.f.map(function (f) {
        return '<div class="fld"><span class="lbl">' + esc(f.label) + '</span><div class="fbody"><div class="chips' + (f.type === 'swatch' ? ' sws' : '') + '">' + field(c, f) + '</div>' + helpLine(f.k, (c.traits || {})[f.k]) + '</div></div>';
      }).join('') + '</details>';
    }).join('') + '</div>';
  }
  function drawCast() {
    var lead = (S.characters || []).some(function (c) { return c.hero; });
    $('#se-cast').innerHTML = (S.characters || []).map(function (c) {
      var first = !lead || c === (S.characters || []).find(function (x) { return x.hero; }), op = OPEN[c.id] != null ? OPEN[c.id] : !c.hero;
      return '<div class="card char" data-c="' + c.id + '">' +
        '<div class="row"><input data-f="name" value="' + esc(c.name) + '" placeholder="Name"><button class="eb ic sm" data-a="dup-char" title="Duplicate as a variant">' + mi('copy') + '</button><button class="eb ic sm" data-a="rand-char" title="Randomize">' + mi('sparkle') + '</button><button class="eb ic sm" data-a="del-char" title="Remove">' + mi('trash') + '</button></div>' +
        '<div class="built">' + esc(c.built || 'Pick options below — the description writes itself.') + '</div>' +
        '<div class="pics3">' + pic(ref(c.hero), 'Hero') + pic(ref(c.sheet), 'Turnaround', true) + pic(ref(c.expr), 'Expressions', false, false, true) + '</div>' +
        '<div class="row">' +
        '<button class="eb sm pri" data-a="hero">' + mi('image') + (c.hero ? ' Redraw character' : lead && !first ? ' Build in series style' : ' Build character') + '</button>' +
        '<button class="eb sm" data-a="hero-photo" title="' + (lead && !first ? 'Turn a photo into this character, drawn in the lead’s series style' : 'Turn a photo into this character') + ' — only use photos of people who agreed to this">' + mi('camera') + ' From a photo</button>' + '<button class="eb sm" data-a="hero-lib" title="A picture already in your library (only of people who agreed to this)">' + mi('folder') + ' From library</button>' +
        '<button class="eb sm" data-a="sheet"' + (c.hero ? '' : ' disabled') + '>' + mi('layers') + ' Turnaround</button>' +
        '<button class="eb sm" data-a="expr"' + (c.hero ? '' : ' disabled') + '>' + mi('user') + ' Expressions</button>' +
        '<button class="eb sm" data-a="asset-save" data-k="characters"' + (c.hero || c.sheet ? '' : ' disabled') + ' title="Keep this character for any series">' + mi('folder') + ' Save to assets</button></div>' +
        '<button class="eb sm ghost" data-a="toggle-build">' + mi(op ? 'chevron-down' : 'chevron-right') + ' Character builder</button>' +
        (op ? builder(c) +
          '<label>Extra details (your words win) <textarea data-f="desc" rows="2" placeholder="anything the options miss — a patch on the knee, a missing tooth…">' + esc(c.desc) + '</textarea></label>' +
          '<div class="row"><label class="grow">Speaking voice <select data-f="voice">' + voiceOpts(c.voice) + '</select></label><button class="eb sm" data-a="hear">' + mi('volume') + ' Hear</button></div>' +
          (c.voice_desc ? '<p class="dim">Singing voice: ' + esc(c.voice_desc) + ' — written into the song.</p>' : '') : '') +
        '</div>';
    }).join('') || '<p class="dim">Add your lead character first — every other character is drawn in its style.</p>';
    $('#se-lineup-card').hidden = !S.lineup;
    $('#se-lineup').innerHTML = S.lineup ? pic(ref(S.lineup), 'Lineup', true) : '';
  }
  /* architectural views of a location (series.py LOC_VIEWS — same order) */
  var LVIEWS = [['cutaway', '3D cutaway', '16:9'], ['cutaway2', 'Opposite corner', '16:9'], ['top', 'Top view', '1:1']];
  function hasViews(l) { return l.views && Object.keys(l.views).length > 0; }
  function viewSteps(l, only) {
    var nm = l.name || 'Location';
    return LVIEWS.map(function (v, i) { return { kind: 'locview', target: l.id, extra: { i: i }, label: nm + ' — ' + v[1].toLowerCase() }; })
      .filter(function (x, i) { return only == null || i === only; });
  }
  function drawLocs() {
    $('#se-locs').innerHTML = (S.locations || []).map(function (l) {
      return '<div class="card" data-l="' + l.id + '">' +
        '<div class="row"><input data-f="name" value="' + esc(l.name) + '" placeholder="Name (e.g. Playroom)"><button class="eb ic sm" data-a="del-loc" title="Remove">' + mi('trash') + '</button></div>' +
        '<textarea data-f="desc" rows="3" placeholder="What is there (toy shelves, a small basket in the corner, a window with sunshine…)">' + esc(l.desc) + '</textarea>' +
        '<div class="pics">' + pic(ref(l.image), 'Location', true) + pic(ref(l.sheet), 'Turnaround', true) + '</div>' +
        '<div class="row"><button class="eb sm" data-a="loc" title="Draws the location, then its turnaround sheet">' + mi('image') + (l.image ? ' Redraw' : ' Draw location + turnaround') + '</button>' +
        '<button class="eb sm" data-a="locsheet"' + (l.image ? '' : ' disabled') + ' title="One sheet: the place as a cutaway from front, right, back and left + a small floor plan">' + mi('layers') + (l.sheet ? ' Redraw turnaround' : ' Turnaround') + '</button>' +
        '<button class="eb sm" data-a="locviews"' + (l.image ? '' : ' disabled') + ' title="3D cutaway from two corners + top view, all built from the location picture">' + mi('box') + (hasViews(l) ? ' Redraw 3D views' : ' Build 3D views') + '</button>' +
        '<button class="eb sm" data-a="asset-save" data-k="locations"' + (l.image ? '' : ' disabled') + '>' + mi('folder') + ' Save to assets</button></div>' +
        (l.image || hasViews(l) ? '<div class="lviews">' + LVIEWS.map(function (v, i) {
          var r = (l.views || {})[v[0]];
          return '<div class="lv' + (v[0] === 'cutaway' ? ' big' : '') + '">' + pic(ref(r), v[1], true) +
            '<button class="eb sm ic lv-re" data-a="locview" data-i="' + i + '" title="' + (r ? 'Redraw' : 'Draw') + ' the ' + esc(v[1].toLowerCase()) + '"' + (l.image ? '' : ' disabled') + '>' + mi(r ? 'refresh' : 'image') + '</button></div>';
        }).join('') + '</div>' : '') + '</div>';
    }).join('') || '<p class="dim">Locations share the series style, so any character can be placed in any of them.</p>';
  }
  /* Objects: the object builder (vehicles, animals, plants, buildings, props) */
  function drawObjs() {
    $('#se-objs').innerHTML = (S.objects || []).map(function (o) {
      var op = OPEN[o.id] != null ? OPEN[o.id] : !o.hero;
      return '<div class="card char" data-o="' + o.id + '">' +
        '<div class="row"><input data-f="name" value="' + esc(o.name) + '" placeholder="Name (e.g. Old Chevy truck)"><button class="eb ic sm" data-a="dup-obj" title="Duplicate as a variant">' + mi('copy') + '</button><button class="eb ic sm" data-a="rand-obj" title="Randomize">' + mi('sparkle') + '</button><button class="eb ic sm" data-a="del-obj" title="Remove">' + mi('trash') + '</button></div>' +
        '<div class="built">' + esc(o.built || 'Pick options below — the description writes itself.') + '</div>' +
        '<div class="pics3">' + pic(ref(o.hero), 'Design', false, false, true) + pic(ref(o.sheet), 'Turnaround', true) + pic(ref(o.detail), 'Details', false, false, true) + '</div>' +
        '<div class="row">' +
        '<button class="eb sm pri" data-a="obj-build" title="Design, then its turnaround and detail sheet drawn from it">' + mi('image') + (o.hero ? ' Redraw object' : ' Build object') + '</button>' +
        '<button class="eb sm" data-a="obj-photo" title="Turn a photo of a real object into this series\' style">' + mi('camera') + ' From a photo</button>' +
        '<button class="eb sm" data-a="obj-lib" title="A picture already in your library">' + mi('folder') + ' From library</button>' +
        '<button class="eb sm" data-a="objsheet"' + (o.hero ? '' : ' disabled') + '>' + mi('layers') + ' Turnaround</button>' +
        '<button class="eb sm" data-a="objdetail"' + (o.hero ? '' : ' disabled') + '>' + mi('search') + ' Details</button>' +
        '<button class="eb sm" data-a="asset-save" data-k="objects"' + (o.hero || o.sheet ? '' : ' disabled') + ' title="Keep this object for any series">' + mi('folder') + ' Save to assets</button></div>' +
        '<button class="eb sm ghost" data-a="toggle-build">' + mi(op ? 'chevron-down' : 'chevron-right') + ' Object builder</button>' +
        (op ? builder(o, P.object) +
          '<label>Extra details (your words win) <textarea data-f="desc" rows="2" placeholder="anything the options miss — a dented fender, a surfboard on the roof…">' + esc(o.desc) + '</textarea></label>' : '') +
        '</div>';
    }).join('') || '<p class="dim">No objects yet. Add a car, a plane, a pet, a tree… — anything that should look the same in every shot.</p>';
  }
  function propChips(ep) {
    var objs = S.objects || [];
    if (!objs.length) return '';
    return '<div class="chips props"><span class="lbl">' + mi('box') + ' Objects</span>' + objs.map(function (o) { return '<button data-a="prop" data-id="' + o.id + '" class="' + ((ep.props || []).indexOf(o.id) >= 0 ? 'on' : '') + '"' + (o.hero || o.sheet ? '' : ' title="draw it first — it is sent as a picture"') + '>' + esc(o.name || 'unnamed') + '</button>'; }).join('') + '</div>';
  }
  function castChips(ep) {
    return (S.characters || []).map(function (c) { return '<button data-a="cast" data-id="' + c.id + '" class="' + ((ep.cast || []).indexOf(c.id) >= 0 ? 'on' : '') + '">' + esc(c.name || 'unnamed') + '</button>'; }).join('');
  }

  /* Episodes: the musical timeline */
  function timeline(e) {
    var tot = e.song_secs || 1;
    return '<div class="tl">' + (e.chunks || []).map(function (c) {
      var st = c.clip ? (c.stale ? 'stale' : 'done') : (busyChunk(e, c.i) ? 'run' : (c.key ? 'key' : ''));
      return '<i class="' + c.kind + ' ' + st + (c.link === 'cut' ? ' cut' : '') + '" style="flex:' + (c.end - c.start) / tot + '" data-a="goto" data-i="' + c.i + '" title="' + esc('#' + (c.i + 1) + ' ' + c.section + ' · ' + mmss(c.start) + '–' + mmss(c.end)) + '"></i>';
    }).join('') + '</div>';
  }
  function busyChunk(e, i) {
    var r = RUN && RUN.run; if (r && r.ep === e.id && r.step && r.step.i === i) return true;
    if (QUEUE.some(function (x) { return (x.state === 'queued' || x.state === 'running') && x.target === e.id && x.i === i; })) return true;
    return Object.keys(JOBS).some(function (k) { var a = JOBS[k].attach; return a && a.target === e.id && a.i === i; });
  }
  function chunkCard(e, c) {
    var prev = (e.chunks || [])[c.i - 1];
    var needKey = c.link === 'cut' || c.i === 0 || !(prev && prev.clipref);
    var op = OPENCH[e.id + ':' + c.i];
    return '<div class="chunk ' + c.kind + (op ? ' open' : '') + '" data-k="' + c.i + '" id="ch-' + e.id + '-' + c.i + '">' +
      '<div class="ch-h"><b>#' + (c.i + 1) + '</b> <span class="sec">' + esc(c.section) + '</span> <span class="dim">' + mmss(c.start) + '–' + mmss(c.end) + ' · ' + (c.end - c.start).toFixed(1) + ' s</span><span class="sp"></span>' +
      '<button class="eb sm ic ch-more" data-a="ch-open" title="Edit this shot">' + mi(op ? 'chevron-down' : 'chevron-right') + '</button>' +
      '<div class="seg"><button data-a="link" data-v="continue" class="' + (c.link === 'continue' ? 'on' : '') + '"' + (c.i === 0 ? ' disabled' : '') + ' title="Keep rolling from the last frames of the shot before">' + mi('chain') + ' continue</button><button data-a="link" data-v="cut" class="' + (c.link === 'cut' ? 'on' : '') + '" title="New angle — starts from its own first frame">' + mi('scissors') + ' cut</button></div></div>' +
      (c.lines && c.lines.length ? '<div class="lyr">♪ ' + esc(c.lines.join(' / ')) + '</div>' : '<div class="lyr dim">instrumental</div>') +
      '<div class="ch-b"><div class="ch-media">' + (c.clip ? pic(lib(c.clip), c.stale ? 'needs re-render' : 'Shot', true, true) : pic(needKey ? ref(c.key) : '', needKey ? 'First frame' : 'continues shot #' + c.i, true)) + '</div>' +
      '<div class="ch-t"><div class="row"><input data-cf="singer" value="' + esc(c.singer) + '" placeholder="who sings"></div><textarea data-cf="shot" rows="4" placeholder="what we see — write shots fills this">' + esc(c.shot) + '</textarea>' +
      '<div class="row">' + (needKey ? '<button class="eb sm" data-a="key">' + mi('image') + (c.key ? ' New first frame' : ' First frame') + '</button>' : '') +
      '<button class="eb sm pri" data-a="shot"' + (needKey && !c.key ? ' title="Makes the first frame, then the shot"' : '') + '>' + mi('video') + (c.clip ? ' Re-render' : needKey && !c.key ? ' First frame + render' : ' Render') + '</button>' +
      ((c.takes || []).length > 1 ? '<label class="take">Take <select data-take="1">' + c.takes.map(function (t, k) { return '<option value="' + esc(t.clip) + '"' + (t.clip === c.clip ? ' selected' : '') + '>' + (k + 1) + ' · ' + new Date(t.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '</option>'; }).join('') + '</select></label>' : '') +
      '</div></div></div></div>';
  }
  function drawEps() {
    $('#se-eps').innerHTML = (S.episodes || []).map(function (e, i) {
      var song = e.song_text || {}, chunks = e.chunks || [], done = chunks.filter(function (c) { return c.clip && !c.stale; }).length;
      var eta = Math.round((S.setup.length || 120) / 120 * 25), up = e.song_source === 'upload' && e.song;
      return '<div class="card ep" data-e="' + e.id + '">' +
        '<div class="row"><input data-f="title" value="' + esc(e.title) + '" placeholder="Episode ' + (i + 1) + ' title"><button class="eb ic sm" data-a="del-ep" title="Remove">' + mi('trash') + '</button></div>' +
        '<textarea data-f="idea" rows="2" placeholder="Idea in a sentence (the fox and the bunny find out that sharing makes a picnic twice as fun)">' + esc(e.idea) + '</textarea>' +
        '<div class="row"><input data-f="lesson" value="' + esc(e.lesson) + '" placeholder="Lesson (sharing)">' +
        '<select data-f="location"><option value="">— main location —</option>' + (S.locations || []).map(function (l) { return '<option value="' + l.id + '"' + (l.id === e.location ? ' selected' : '') + '>' + esc(l.name || 'unnamed') + '</option>'; }).join('') + '</select></div>' +
        '<div class="chips">' + castChips(e) + '</div>' + propChips(e) +
        '<div data-runp="' + e.id + '"></div>' +
        (up ? '<div class="step"><b>1</b> Your song <span class="sp"></span><button class="eb sm" data-a="use-song">' + mi('upload') + ' Replace</button>' + '<button class="eb sm" data-a="song-lib" title="An MP3 / song already in your library, e.g. one from the Downloader">' + mi('folder') + ' From library</button>' +
            '<button class="eb sm pri" data-a="recognise">' + mi('mic') + (e.words ? ' Recognise again' : ' Recognise the lyrics') + '</button></div>' +
            '<audio controls src="' + lib(e.song) + '"></audio><div class="row"><button class="eb sm" data-a="asset-save" data-k="songs">' + mi('folder') + ' Save song to assets</button><span class="dim" data-recog="' + e.id + '"></span></div>' +
            (e.words ? '<p class="dim">' + e.words.length + ' sung words found' + (e.lang ? ' (' + esc(e.lang) + ')' : '') + ' — every shot below carries the words sung in it. Fix any misheard words in the shots.</p>' +
              '<textarea data-sf="lyrics" rows="6">' + esc(song.lyrics) + '</textarea>' : '<p class="dim">The PC separates the voice from the music and listens for every word and when it is sung (a few minutes, no GPU needed).</p>')
          : '<div class="step"><b>1</b> Song <span class="sp"></span><button class="eb sm" data-a="use-song" title="Use a song you already have — the shots follow its lyrics">' + mi('upload') + ' Use my song</button><button class="eb sm" data-a="song-lib" title="An MP3 / song already in your library, e.g. one from the Downloader">' + mi('folder') + ' From library</button><button class="eb sm" data-a="write-musical">' + mi('wand') + (song.lyrics ? ' Rewrite' : ' Write the song') + '</button></div>' +
            (song.lyrics ? '<input class="ttl" data-sf="title" value="' + esc(song.title) + '"><textarea data-sf="lyrics" rows="8">' + esc(song.lyrics) + '</textarea><div class="dim cap2">' + esc(song.caption) + '</div>' : '<p class="dim">Write an original song on your format’s beats — or use your own song and the shots will follow its lyrics.</p>') +
            '<div class="step"><b>2</b> Record <span class="sp"></span><button class="eb sm pri" data-a="song"' + (song.lyrics ? '' : ' disabled') + '>' + mi('music') + (e.song ? ' Record again' : ' Make the song') + '</button></div>' +
            (e.song ? '<audio controls src="' + lib(e.song) + '"></audio><button class="eb sm" data-a="asset-save" data-k="songs">' + mi('folder') + ' Save song to assets</button>' : (song.lyrics ? '<p class="dim">Singing a ' + mmss(S.setup.length) + ' song takes about ' + eta + ' min.</p>' : ''))) +
        (chunks.length ? '<div class="step"><b>3</b> Shots <span class="dim">' + chunks.length + ' shots · ' + done + ' rendered · ' + mmss(e.song_secs) + '</span><span class="sp"></span><button class="eb sm" data-a="write-chunks">' + mi('wand') + ' Write shots</button><button class="eb sm" data-a="remap" title="Cut the song into shots again">' + mi('refresh') + '</button></div>' +
          timeline(e) +
          '<div class="chunks">' + chunks.map(function (c) { return chunkCard(e, c); }).join('') + '</div>' +
          '<div class="step"><b>4</b> Finish <span class="sp"></span><button class="eb sm pri" data-a="assemble"' + (done === chunks.length ? '' : ' disabled') + '>' + mi('film') + ' Assemble the episode</button><button class="eb sm" data-a="edit"' + (done ? '' : ' disabled') + '>' + mi('scissors') + ' Open in editor</button></div>' +
          (e.final ? pic(lib(e.final), 'Finished episode', true, true) : '') : '') +
        '<details class="classic"><summary>Single scene (no song)</summary>' +
        '<div class="row"><select data-f="seconds">' + [5, 8, 10, 12, 15].map(function (s) { return '<option' + (+e.seconds === s ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select><button class="eb sm" data-a="write-shots">' + mi('wand') + ' Write shot list</button><button class="eb sm" data-a="scene">' + mi('video') + ' Render scene</button></div>' +
        '<textarea data-f="shots" rows="4" placeholder="[0-3s] wide shot, static. …">' + esc(e.shots) + '</textarea>' +
        '<div class="clips">' + (e.scenes || []).map(function (n) { return '<div class="pic wide"><video src="' + lib(n) + '" muted loop playsinline preload="metadata"></video><button class="x" data-a="rm-scene" data-n="' + esc(n) + '" title="Remove from episode">×</button></div>'; }).join('') + '</div></details>' +
        '</div>';
    }).join('') || '<p class="dim">An episode starts with an idea and a lesson. The song comes next, then the shots are cut to it.</p>';
  }

  /* ── asset library: characters, locations, looks and songs saved for reuse in any series ── */
  var ASSETS = [], AKIND = '', AROOT = '';
  var AK = { '': 'All', characters: 'Characters', locations: 'Locations', objects: 'Objects', styles: 'Looks', songs: 'Songs' };
  function afile(a, f) { return f ? B + '/api/assets/file?id=' + encodeURIComponent(a.id) + '&f=' + encodeURIComponent(f) : ''; }
  function loadAssets() { return api('/api/assets').then(function (j) { ASSETS = j.assets || []; AROOT = j.root || ''; drawAssets(); }); }
  function drawAssets() {
    if (!$('#as-grid')) return;
    $('#as-root').textContent = AROOT;
    $('#as-kinds').innerHTML = Object.keys(AK).map(function (k) {
      var n = ASSETS.filter(function (a) { return !k || a.kind === k; }).length;
      return '<button data-a="akind" data-v="' + k + '" class="' + (AKIND === k ? 'on' : '') + '">' + AK[k] + ' ' + n + '</button>';
    }).join('');
    var list = ASSETS.filter(function (a) { return !AKIND || a.kind === AKIND; });
    $('#as-grid').innerHTML = list.map(function (a) {
      var song = a.kind === 'songs', f = a.files || {};
      var media = song ? '<audio controls preload="none" src="' + afile(a, f.song) + '"></audio>' :
        '<div class="as-pics">' + ['hero', 'sheet', 'expr', 'detail', 'image', 'sample'].filter(function (k) { return f[k]; }).map(function (k) { return '<div class="pic' + (k === 'sheet' || k === 'image' ? ' wide' : ' sq') + '"><img src="' + afile(a, f[k]) + '" loading="lazy"></div>'; }).join('') + '</div>';
      var eps = (S && S.episodes || []).map(function (e, i) { return '<option value="' + e.id + '">' + esc(e.title || 'Episode ' + (i + 1)) + '</option>'; }).join('');
      return '<div class="card asset" data-asset="' + esc(a.id) + '">' +
        '<div class="row"><b class="grow">' + esc(a.name || 'untitled') + '</b><span class="tag">' + (AK[a.kind] || a.kind).replace(/s$/, '') + '</span>' +
        '<button class="eb ic sm" data-a="asset-rename" title="Rename">' + mi('type') + '</button><button class="eb ic sm" data-a="asset-del" title="Remove from the library">' + mi('trash') + '</button></div>' +
        media +
        '<p class="dim">' + esc(a.built || a.desc || a.lyrics || '') + '</p>' +
        '<p class="dim">' + (a.from ? 'from “' + esc(a.from) + '” · ' : '') + (a.created ? ago(a.created) : '') + (a.secs ? ' · ' + mmss(a.secs) : '') + '</p>' +
        '<div class="row">' + (song ? '<select class="as-ep">' + eps + '</select>' : '') +
        '<button class="eb sm pri" data-a="asset-use"' + (S ? '' : ' disabled') + '>' + mi('plus') + ' Use in this series</button></div></div>';
    }).join('') || '<p class="dim">Nothing saved yet. Use “Save to assets” on a character, location, object, song or look — or save this series’ whole cast above.</p>';
    if (window.MI && MI.fill) MI.fill($('#as-grid'));
  }
  function saveAsset(kind, target) {
    return save(true).then(function () { return api('/api/assets/save', { series: S.id, kind: kind, target: target }); })
      .then(function (r) { if (r.error) return toast(r.error, 1); toast((r.saved || []).length > 1 ? r.saved.length + ' characters saved to your assets' : '“' + ((r.saved || [])[0] || {}).name + '” saved to your assets'); loadAssets(); });
  }

  /* ── the background run: panel on the episode + the History tab ── */
  var STEPN = { write: 'Writing the song', song: 'Recording the song', transcribe: 'Recognising the lyrics', shots: 'Writing the shots',
    keyframe: 'First frame of shot', chunk: 'Rendering shot', assemble: 'Assembling the episode' };
  function stepName(st) { return st ? (STEPN[st.kind] || st.kind) + (st.i != null ? ' ' + (st.i + 1) : '') : ''; }
  function runPanel(e) {
    var r = (RUN && RUN.run) || {}, mine = r.ep === e.id, st = mine ? r.state : '', pr = (mine && RUN.progress) || {};
    var other = r.ep && r.ep !== e.id && (r.state === 'running' || r.state === 'paused');
    var tot = (pr.done || 0) + (pr.left || 0), pct = tot ? Math.round(100 * (pr.done || 0) / tot) : 0, now = mine && r.step;
    var h = '<div class="runp ' + (st || 'idle') + '">';
    if (st === 'running' || st === 'paused') {
      h += '<div class="rp-top"><b>' + (st === 'running' ? mi('play') + ' Rendering in the background' : mi('pause') + ' Paused') + '</b><span class="sp"></span>' +
        '<span class="dim">' + (pr.done || 0) + ' steps done · ~' + (pr.left || 0) + ' to go' + (pr.eta ? ' · about ' + dur(pr.eta) + ' left' : '') + '</span></div>' +
        '<div class="bar"><i style="width:' + Math.max(3, pct) + '%"></i></div>' +
        '<div class="rp-now">' + (now ? esc(stepName(now)) + (now.stage ? ' — ' + esc(now.stage) : '') + (now.pct != null ? ' · ' + now.pct + '%' : '') :
          (RUN.next && st === 'running' ? 'Next: ' + esc(RUN.next.label) + (RUN.next.i != null ? ' ' + (RUN.next.i + 1) : '') + ' (waiting for the lab)' : '')) + '</div>' +
        (r.error ? '<div class="rp-err">' + mi('warn') + ' ' + esc(r.error) + '</div>' : '') +
        '<div class="row">' + (now ? '<button class="eb sm" data-a="run" data-v="cancel" title="Stop the render running now — the run waits; Resume redoes it, Skip moves on">' + mi('close') + ' Cancel this step</button>' : '') +
          (st === 'running' ? '<button class="eb sm" data-a="run" data-v="pause">' + mi('pause') + ' Pause</button>' :
          '<button class="eb sm pri" data-a="run" data-v="resume">' + mi('play') + ' Resume</button><button class="eb sm" data-a="run" data-v="retry">' + mi('refresh') + ' Retry</button><button class="eb sm" data-a="run" data-v="skip">' + mi('forward') + ' Skip this step</button>') +
        '<button class="eb sm" data-a="run" data-v="stop" title="End this run (finished steps stay in the series)">' + mi('stop') + ' Stop</button>' +
        '<button class="eb sm ghost" data-a="tab-hist">' + mi('clock') + ' History</button></div>';
    } else {
      h += '<div class="row"><button class="eb sm pri" data-a="run" data-v="start"' + (other ? ' disabled title="another episode is rendering"' : '') + '>' + mi('play') +
        (st === 'done' ? ' Run again (only what changed)' : ' Make the whole episode') + '</button>' +
        '<span class="dim">' + (st === 'done' ? 'Finished ' + ago(r.updated) + '.' : 'Runs on the PC in the background — safe to close this page; a crash or restart picks up where it stopped.') + '</span></div>';
    }
    return h + '</div>';
  }
  function drawRunBits() {
    if (!S) return;
    $$('[data-runp]').forEach(function (el) { var e = epOf(el.dataset.runp); if (e) el.innerHTML = runPanel(e); });
    var r = (RUN && RUN.run) || {}, e = r.ep && epOf(r.ep);
    if ($('#hi-run')) $('#hi-run').innerHTML = '<h3>' + mi('play') + ' Background run</h3>' + (e ? '<p class="dim">' + esc(e.title || 'Episode') + '</p>' + runPanel(e) : '<p class="dim">Nothing has run yet. Start one from an episode: “Make the whole episode”.</p>');
    (RUN && RUN.recognising ? Object.keys(RUN.recognising) : []).forEach(function (eid) {
      var x = RUN.recognising[eid], el = $('[data-recog="' + eid + '"]');
      if (el) el.innerHTML = x.state === 'running' ? mi('hourglass') + ' ' + esc(x.msg || 'listening …') : x.state === 'error' ? '<span class="rp-err">' + esc(x.error) + '</span>' : '';
    });
    if (window.MI && MI.fill) MI.fill(document);
  }
  var EVN = { 'run-start': 'Run started', 'run-pause': 'Paused', 'run-resume': 'Resumed', 'run-retry': 'Retrying', 'run-skip': 'Skipped a step', 'run-stop': 'Stopped', 'step-cancelled': 'Cancelled',
    'run-done': 'Episode finished', 'step-start': 'Started', 'step-queued': 'Queued', 'step-done': 'Done', 'step-failed': 'Failed', 'step-interrupted': 'Interrupted (will redo)',
    'lab-restarted': 'Lab restarted — picking up', checkpoint: 'Checkpoint', restore: 'Restored a checkpoint', attached: 'Added to the series', transcribed: 'Lyrics recognised',
    'transcribe-failed': 'Lyrics recognition failed', 'song-uploaded': 'Song uploaded', created: 'Series created', setup: 'Setup changed', 'write-failed': 'Writer failed', 'runner-error': 'Runner error' };
  function evText(x) {
    var s = EVN[x.ev] || x.ev, st = x.step ? stepName({ kind: x.step, i: x.i }) : '';
    if (x.ev === 'checkpoint') return s + ': ' + esc(x.label);
    if (x.ev === 'run-pause' && x.why) return s + ' — ' + esc(x.why);
    if (x.ev === 'step-failed') return s + ': ' + esc(st) + ' — ' + esc(x.error) + (x.retry ? ' (retrying once)' : x.paused ? ' (run paused)' : '');
    if (st) return s + ': ' + esc(st) + (x.secs ? ' · ' + dur(x.secs) : '');
    if (x.ev === 'transcribed') return s + ' · ' + x.words + ' words' + (x.lang ? ' · ' + esc(x.lang) : '');
    return s;
  }
  function drawHist() {
    drawRunBits();
    $('#hi-versions').innerHTML = HIST.versions.slice(0, 60).map(function (v, i) {
      return '<div class="vrow"><span class="dim">' + ago(v.t) + '</span> <b>' + esc(v.label) + '</b><span class="sp"></span>' + (i ? '<button class="eb sm" data-a="restore" data-v="' + esc(v.version) + '">Restore</button>' : '<span class="dim">current</span>') + '</div>';
    }).join('') || '<p class="dim">No checkpoints yet.</p>';
    $('#hi-log').innerHTML = HIST.log.map(function (x) {
      var cls = /failed|error/.test(x.ev) ? 'bad' : /done|transcribed|run-done/.test(x.ev) ? 'ok' : /interrupt|restart|pause/.test(x.ev) ? 'warn' : '';
      return '<div class="ev ' + cls + '"><span class="dim">' + new Date(x.t * 1000).toLocaleString() + '</span> ' + evText(x) + '</div>';
    }).join('') || '<p class="dim">Nothing yet.</p>';
  }

  /* ── rendering through the lab ── */
  /* one-off pictures go through the server's queue: it renders them in order and files each one back into the series
     itself, so they still land if this page is closed (or the phone sleeps) mid-render */
  var QKINDS = ['hero', 'character', 'sheet', 'expr', 'lineup', 'location', 'locsheet', 'locview', 'scene', 'song', 'keyframe', 'chunk', 'object', 'objsheet', 'objdetail'], QUEUE = [], qT = null, qDone = {};
  function enqueue(steps) {
    return save(true).then(function () { return api('/api/series/' + S.id + '/queue', { steps: steps }); }).then(function (r) {
      if (r.error === 'HTTP 404') {      /* an older lab server without the queue: render them one after another from here */
        var go = function (k) { if (k < steps.length) run(steps[k].kind, steps[k].target, steps[k].label, steps[k].extra, function (ok) { if (ok) go(k + 1); }); };
        return go(0);
      }
      if (r.error) return toast(r.error, 1);
      QUEUE = r.items || []; drawJobs(); toast(steps.length > 1 ? steps.length + ' pictures queued — they fill in one by one' : steps[0].label + ' — on its way');
      pollQueue();
    });
  }
  function pollQueue() {
    clearTimeout(qT);
    if (!S) return;
    var sid = S.id;
    api('/api/series/' + sid + '/queue').then(function (r) {
      if (!S || S.id !== sid) return;
      var fresh = false;
      QUEUE = r.items || [];
      QUEUE.forEach(function (x) {
        if ((x.state === 'done' || x.state === 'error') && !qDone[x.id]) {
          qDone[x.id] = 1;
          if (x.done_t && Date.now() / 1000 - x.done_t < 600) {
            if (x.state === 'done') { fresh = true; toast(x.label + ' — done'); } else toast(x.label + ' — ' + (x.error || 'failed'), 1);
          }
        }
      });
      drawJobs();
      if (fresh) api('/api/series/' + sid).then(function (d) { if (d && !d.error && S && S.id === sid) { S = d; fixup(); draw(); } });
      if (QUEUE.some(function (x) { return x.state === 'queued' || x.state === 'running'; })) qT = setTimeout(pollQueue, 2500);
    }).catch(function () { qT = setTimeout(pollQueue, 5000); });
  }
  function run(kind, target, label, extra, then) {
    if (!then && QKINDS.indexOf(kind) >= 0) return enqueue([{ kind: kind, target: target, extra: extra || {}, label: label }]);
    return save(true).then(function () {
      return api('/api/series/' + S.id + '/plan', { kind: kind, target: target, extra: extra || {} });
    }).then(function (p) {
      if (!p || p.error) { toast((p && p.error) || 'nothing to do', 1); if (then) then(false); return; }
      var att = Object.assign({}, p.attach); if (extra && extra.i != null) att.i = extra.i;
      return api('/api/generate', { model: p.model, prompt: p.prompt, refs: p.refs, override: p.override, series: true }).then(function (j) {
        if (j.busy && then) { toast('the lab is busy — trying again shortly'); return setTimeout(function () { run(kind, target, label, extra, then); }, 15000); }
        if (j.error) { toast(j.error, 1); if (then) then(false); return; }
        JOBS[j.id] = { label: label, attach: att, pct: 0, status: j.status, then: then }; drawJobs(); poll(j.id); drawEps();
        toast(label + ' — on its way');
      });
    });
  }
  function poll(id) {
    api('/api/jobs/' + id).then(function (j) {
      var J = JOBS[id]; if (!J) return;
      J.status = j.status; J.stage = j.stage; J.pct = j.progress && j.progress.pct != null ? j.progress.pct : J.pct;
      drawJobs();
      if (j.status === 'queued' || j.status === 'running') return setTimeout(function () { poll(id); }, 2500);
      delete JOBS[id]; drawJobs();
      if (j.status !== 'done') { toast(J.label + ' — ' + (j.status === 'cancelled' ? 'cancelled' : (j.error || j.status)), j.status !== 'cancelled'); if (J.then) J.then(false); return drawEps(); }
      var f = (j.files || []).filter(function (n) { return /\.(mp4|mov|webm|png|jpe?g|webp|mp3|wav|flac|ogg|m4a)$/i.test(n); })[0];
      if (!f) { toast(J.label + ' finished without a media file', 1); if (J.then) J.then(false); return; }
      api('/api/series/' + S.id + '/attach', { file: String(f).split('/').pop(), kind: J.attach.kind, target: J.attach.target, i: J.attach.i }).then(function (d) {
        if (d.error) { toast(d.error, 1); if (J.then) J.then(false); return; }
        S = d; fixup(); draw(); toast(J.label + ' — done');
        if (J.then) J.then(true);
      });
    }).catch(function () { setTimeout(function () { poll(id); }, 5000); });
  }
  function drawJobs() {
    var row = function (label, stage, pct, live, cancel) {
      return '<div class="job">' + (live ? '<div class="livepv" data-livepv="' + esc(live) + '"><img alt=""><span class="lp-tag"><i></i>LIVE</span></div>' : '') +
        '<div class="job-hd"><span>' + esc(label) + ' · ' + esc(stage || '') + '</span><button class="job-x" ' + cancel + ' title="Cancel this step">' + mi('close') + '</button></div>' +
        '<div class="bar"><i style="width:' + Math.max(4, pct || 0) + '%"></i></div></div>';
    };
    var q = QUEUE.filter(function (x) { return x.state === 'queued' || x.state === 'running'; });
    $('#se-jobs').innerHTML = Object.keys(JOBS).map(function (k) { var J = JOBS[k];
      return row(J.label, J.stage || J.status, J.pct, J.status === 'running' && k, 'data-xjob="' + esc(k) + '"'); }).join('') +
      q.map(function (x) {
        return row(x.label, x.state === 'queued' ? 'waiting its turn' : (x.stage || 'rendering'), x.state === 'running' ? x.pct : 0, x.state === 'running' && x.job, 'data-xq="' + esc(x.id) + '"');
      }).join('') +
      (q.length > 1 ? '<button class="eb sm job-all" data-xq="all">' + mi('close') + ' Cancel all ' + q.length + '</button>' : '');
  }
  /* cancel one step: a picture rendering from this page (its GPU job) or one in the server-side picture queue */
  $('#se-jobs').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-xjob],[data-xq]'); if (!b || !S) return;
    b.disabled = true;
    if (b.dataset.xjob) {
      var J = JOBS[b.dataset.xjob]; if (J) J.cancelled = true;
      return api('/api/jobs/' + b.dataset.xjob + '/cancel', {}).then(function (r) { if (r.error) { b.disabled = false; return toast(r.error, 1); } toast((J ? J.label : 'Step') + ' — cancelling'); });
    }
    if (b.dataset.xq === 'all' && !confirm('Cancel every picture still waiting or rendering?')) { b.disabled = false; return; }
    api('/api/series/' + S.id + '/queue', { cancel: b.dataset.xq }).then(function (r) {
      if (r.error) { b.disabled = false; return toast(r.error, 1); }
      QUEUE = r.items || []; drawJobs(); toast(b.dataset.xq === 'all' ? 'Cancelled' : 'Step cancelled');
    });
  });
  function upload(files) {
    return Promise.all([].slice.call(files).map(function (f) {
      var fd = new FormData(); fd.append('file', f);
      return fetch(B + '/api/upload', { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.json(); });
    })).then(function (rs) { var bad = rs.filter(function (r) { return r.error; }); if (bad.length) toast(bad[0].error, 1); return rs.filter(function (r) { return r.name; }).map(function (r) { return r.name; }); });
  }
  function epOf(id) { return (S.episodes || []).find(function (e) { return e.id === id; }); }
  function needsKey(e, c) { var prev = (e.chunks || [])[c.i - 1]; return c.link === 'cut' || c.i === 0 || !(prev && prev.clipref); }
  /* first frame (when the shot needs one) + the shot, queued on the server: it files each one back itself, so a
     closed tab or a reloaded window can no longer leave a finished render unattached */
  function renderShot(e, c) {
    var lbl = (e.title || 'Episode') + ' — shot ' + (c.i + 1), steps = [];
    if (needsKey(e, c) && !c.key) steps.push({ kind: 'keyframe', target: e.id, extra: { i: c.i }, label: lbl + ' first frame' });
    steps.push({ kind: 'chunk', target: e.id, extra: { i: c.i }, label: lbl });
    return enqueue(steps);
  }
  /* ── random character (Surprise me / Randomize) ── */
  function pick(a) { return a[Math.floor(Math.random() * a.length)]; }
  function randomTraits() {
    var t = {};
    P.character.forEach(function (f) {
      if (f.type === 'one') t[f.k] = pick(f.opts);
      else if (f.type === 'swatch') t[f.k] = pick(f.opts);
      else if (f.type === 'many') { var n = 1 + Math.floor(Math.random() * 2), o = f.opts.slice(); t[f.k] = []; while (n-- > 0 && o.length) t[f.k].push(o.splice(Math.floor(Math.random() * o.length), 1)[0]); }
      else if (f.type === 'range') t[f.k] = f.range[0] + Math.floor(Math.random() * (f.range[1] - f.range[0] + 1));
    });
    if (['kid', 'toddler'].indexOf(t.kind) >= 0) t.age = t.kind === 'toddler' ? 2 + Math.floor(Math.random() * 2) : 4 + Math.floor(Math.random() * 6);
    if (t.kind !== 'kid' && t.kind !== 'toddler' && t.kind !== 'grown-up' && t.kind !== 'grandparent') { t.hair = pick(['none', 'fluffy tuft', 'none']); }
    t.top = Math.random() < .2 ? 'none' : t.top; t.catch = '';
    return t;
  }
  function randomObj() {
    var t = {};
    P.object.forEach(function (f) {
      if (f.type === 'one' || f.type === 'swatch') t[f.k] = pick(f.opts);
      else if (f.type === 'many') { var n = 1 + Math.floor(Math.random() * 2), o = f.opts.slice(); t[f.k] = []; while (n-- > 0 && o.length) t[f.k].push(o.splice(Math.floor(Math.random() * o.length), 1)[0]); }
      else if (f.type === 'range') t[f.k] = f.range[0] + Math.floor(Math.random() * (f.range[1] - f.range[0] + 1));
    });
    if (Math.random() < .6) t.o_face = 'no face (a real object)';
    return t;
  }
  function objSteps(o, photo) {
    var nm = o.name || 'Object';
    return [{ kind: 'object', target: o.id, extra: photo ? { photo: photo } : {}, label: nm + ' — design' + (photo ? ' from photo' : '') },
            { kind: 'objsheet', target: o.id, label: nm + ' — turnaround' },
            { kind: 'objdetail', target: o.id, label: nm + ' — details' }];
  }
  var NAMES = ['Pip', 'Lulu', 'Bo', 'Momo', 'Ziggy', 'Nia', 'Tito', 'Bea', 'Koko', 'Rafa', 'Juno', 'Ollie', 'Mira', 'Dot', 'Pepper', 'Wren'];

  /* ── events ── */
  function itemOf(el) {
    var c = el.closest('[data-c]'), l = el.closest('[data-l]'), e = el.closest('[data-e]'), ob = el.closest('[data-o]');
    if (c) return { list: S.characters, it: S.characters.find(function (x) { return x.id === c.dataset.c; }) };
    if (ob) return { list: S.objects, it: S.objects.find(function (x) { return x.id === ob.dataset.o; }) };
    if (l) return { list: S.locations, it: S.locations.find(function (x) { return x.id === l.dataset.l; }) };
    if (e) return { list: S.episodes, it: S.episodes.find(function (x) { return x.id === e.dataset.e; }) };
    return {};
  }
  function chunkOf(el) { var e = itemOf(el).it, k = el.closest('[data-k]'); return e && k ? { e: e, c: (e.chunks || [])[+k.dataset.k] } : {}; }
  document.addEventListener('input', function (ev) {
    var t = ev.target; if (!S) return;
    if (t.id === 'se-name') { S.name = t.value; return save(); }
    if (t.id === 'se-style') { S.style_prompt = t.value; return save(); }
    if (t.dataset.ss) { S.setup.song[t.dataset.ss] = +t.value; var rv = t.parentNode.querySelector('.rv'); if (rv) rv.textContent = t.value; return save(); }
    if (t.dataset.bf) { var bi = +t.closest('[data-b]').dataset.b, b = S.setup.beats[bi]; b[+t.dataset.bf] = t.dataset.bf === '1' ? +t.value / 100 : t.value; if (t.dataset.bf !== '0') drawSetup(); return save(); }
    if (t.dataset.tk) { var oc = itemOf(t).it; oc.traits[t.dataset.tk] = t.type === 'range' ? +t.value : t.value; var r2 = t.parentNode.querySelector('.rv'); if (r2) r2.textContent = t.value; return save(); }
    if (t.dataset.cf) { var o = chunkOf(t); if (o.c) { o.c[t.dataset.cf] = t.value; save(); } return; }
    if (t.dataset.sf) { var ep = itemOf(t).it; ep.song_text = ep.song_text || {}; ep.song_text[t.dataset.sf] = t.value; return save(); }
    var f = t.dataset.f; if (!f) return;
    var oi = itemOf(t); if (!oi.it) return;
    oi.it[f] = f === 'seconds' ? +t.value : t.value; save();
  });
  document.addEventListener('change', function (ev) { if (ev.target.dataset.f) ev.target.dispatchEvent(new Event('input', { bubbles: true })); });
  $('#se-pick').addEventListener('change', function () { open(this.value); });
  document.addEventListener('change', function (ev) {
    var t = ev.target; if (!t.dataset.take) return;
    var o = chunkOf(t); if (!o.c) return;
    api('/api/series/' + S.id + '/episode/' + o.e.id + '/take', { i: o.c.i, clip: t.value }).then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); toast('Shot ' + (o.c.i + 1) + ': take switched — shots that continue from it need a re-render'); });
  });
  $('#se-song').addEventListener('change', function () {
    var fs = [].slice.call(this.files), why = filePurpose; this.value = '';
    if (!why || !why.song || !fs.length) return;
    toast('Uploading the song…');
    upload(fs).then(function (names) { if (names.length) useSongRef(why.song, names[0]); });
  });
  function useSongRef(eid, refName) {
    return api('/api/series/' + S.id + '/episode/' + eid + '/usesong', { ref: refName }).then(function (d) {
      if (d.error) return toast(d.error, 1); S = d; fixup(); draw();
      return api('/api/series/' + S.id + '/episode/' + eid + '/recognise', {}).then(function () { toast('Song added — listening for the lyrics now'); pollRun(); });
    });
  }
  function heroFromPhoto(cid, photo) {
    var ch = S.characters.find(function (c) { return c.id === cid; }), nm = (ch && ch.name) || 'Character';
    enqueue([{ kind: 'hero', target: cid, extra: { photo: photo }, label: nm + ' — hero from photo' },
             { kind: 'sheet', target: cid, label: nm + ' — turnaround' },
             { kind: 'expr', target: cid, label: nm + ' — expressions' }]);
  }
  /* ── "From library": anything already in the library (renders, downloads, stills) → a reference here ── */
  function libPick(kind, multi, title, done) {
    var m = document.createElement('div'); m.className = 'zoom lp'; var sel = [];
    m.innerHTML = '<div class="lp-box"><div class="lp-hd"><b>' + esc(title) + '</b><span class="sp"></span>' +
      '<button class="eb sm pri" data-lp="ok" disabled>' + mi('check') + ' Use</button><button class="eb sm ic" data-lp="x">' + mi('close') + '</button></div>' +
      '<div class="lp-grid"><p class="dim">Loading your library…</p></div></div>';
    document.body.appendChild(m);
    var close = function () { m.remove(); };
    m.addEventListener('click', function (e) {
      if (e.target === m || e.target.closest('[data-lp="x"]')) return close();
      if (e.target.closest('[data-lp="ok"]')) {
        close(); toast('Bringing ' + sel.length + ' in…');
        return Promise.all(sel.map(function (n) { return api('/api/library/' + encodeURIComponent(n) + '/use', {}); })).then(function (rs) {
          var bad = rs.filter(function (r) { return r.error; }); if (bad.length) toast(bad[0].error, 1);
          var refs = rs.filter(function (r) { return r.name; }).map(function (r) { return r.name; }); if (refs.length) done(refs);
        });
      }
      var it = e.target.closest('[data-ln]'); if (!it) return;
      var n = it.dataset.ln, ix = sel.indexOf(n);
      if (!multi) { sel = ix >= 0 ? [] : [n]; $$('[data-ln]', m).forEach(function (x) { x.classList.toggle('on', sel.indexOf(x.dataset.ln) >= 0); }); }
      else { if (ix >= 0) sel.splice(ix, 1); else if (sel.length < 8) sel.push(n); it.classList.toggle('on', sel.indexOf(n) >= 0); }
      $('[data-lp="ok"]', m).disabled = !sel.length;
    });
    api('/api/library?limit=120&kind=' + kind).then(function (d) {
      var items = d.items || [], g = $('.lp-grid', m);
      if (!items.length) { g.innerHTML = '<p class="dim">No ' + (kind === 'audio' ? 'audio' : 'pictures') + ' in your library yet — the Downloader can grab some.</p>'; return; }
      g.innerHTML = items.map(function (it) {
        var dl = it.model === 'download';
        return '<button class="lp-it' + (kind === 'audio' ? ' au' : '') + '" data-ln="' + esc(it.name) + '" title="' + esc(it.prompt || it.name) + '">' +
          (kind === 'audio' ? mi('music') + '<span>' + esc(it.prompt || it.name) + '</span>' : '<img alt="" loading="lazy" src="' + B + '/thumb/' + encodeURIComponent(it.name) + '">') +
          (dl ? '<i class="lpk-tag">' + mi('download') + '</i>' : '') + '</button>';
      }).join('');
    });
  }
  $('#se-file').addEventListener('change', function () {
    var fs = [].slice.call(this.files), why = filePurpose; this.value = '';
    upload(fs).then(function (names) {
      if (!names.length) return;
      if (why === 'style') { STYLE_REFS = STYLE_REFS.concat(names).slice(-8); draw(); }
      else if (why && why.hero) heroFromPhoto(why.hero, names[0]);
      else if (why && why.obj) { var ob = S.objects.find(function (x) { return x.id === why.obj; }); if (ob) enqueue(objSteps(ob, names[0])); }
    });
  });
  var PVAU = null;
  document.addEventListener('click', function (ev) {
    var pa = ev.target.closest && ev.target.closest('.pva');
    if (pa) {     /* example audio: play / stop without picking the option */
      ev.stopPropagation(); ev.preventDefault();
      var again = PVAU && PVAU.dataset.src === pa.dataset.au && !PVAU.paused;
      if (PVAU) PVAU.pause();
      $$('.pva.on').forEach(function (x) { x.classList.remove('on'); });
      if (again) return;
      PVAU = new Audio(pa.dataset.au); PVAU.dataset.src = pa.dataset.au; pa.classList.add('on');
      PVAU.onended = function () { pa.classList.remove('on'); }; PVAU.play().catch(function () { pa.classList.remove('on'); });
      return;
    }
    var pz = ev.target.closest && ev.target.closest('.pvz');
    if (pz) { ev.stopPropagation(); ev.preventDefault(); var m0 = pz.parentNode.querySelector('.pv'); if (m0) zoom(m0); return; }
    var b = ev.target.closest('[data-a],[data-t]');
    if (!b) { var m = ev.target.closest('.pic img,.pic video'); if (m) zoom(m); return; }
    if (b.dataset.t && b.closest('#se-tabs')) { TAB = b.dataset.t; draw(); if (TAB === 'assets') loadAssets(); if (TAB === 'hist') loadHist(); return; }
    var a = b.dataset.a, o = itemOf(b), it = o.it;
    if (a === 'new') {
      var name = prompt('Name your series', 'My kids series'); if (name == null) return;
      return api('/api/series', { name: name || 'My kids series' }).then(function (d) { if (d.error) return toast(d.error, 1); TAB = 'setup'; loadList(d.id); });
    }
    if (!S) return;
    if (a === 'ch-open') {   /* phone: open / close one shot's text */
      var ck = b.closest('.chunk'), ep = b.closest('[data-e]'), kk = (ep && ep.dataset.e) + ':' + ck.dataset.k;
      OPENCH[kk] = !OPENCH[kk]; ck.classList.toggle('open', OPENCH[kk]); b.innerHTML = mi(OPENCH[kk] ? 'chevron-down' : 'chevron-right'); return;
    }
    /* setup */
    if (a === 'struct') { S.setup.structure = b.dataset.v; if (b.dataset.v === 'custom' && !(S.setup.beats || []).length) S.setup.beats = [['Intro', .1, 'establish'], ['Verse', .3, 'sing'], ['Chorus', .4, 'sing'], ['Outro', .2, 'action']]; drawSetup(); return save(); }
    if (a === 'beat-add') { S.setup.beats.push(['Beat', .15, 'sing']); drawSetup(); return save(); }
    if (a === 'beat-del') { S.setup.beats.splice(+b.closest('[data-b]').dataset.b, 1); drawSetup(); return save(); }
    if (a === 'style') {
      var ps = P.styles.find(function (x) { return x.id === b.dataset.v; });
      if (S.style_prompt && S.setup.style !== b.dataset.v && !confirm('Replace the style bible with the ' + ps.name + ' look?')) { S.setup.style = b.dataset.v; drawSetup(); return save(); }
      S.setup.style = b.dataset.v; S.style_prompt = ps.style_prompt; if (ps.aspect && S.setup.aspect === '16:9') S.setup.aspect = ps.aspect === '21:9' ? '21:9' : S.setup.aspect;
      $('#se-style').value = S.style_prompt; drawSetup(); return save();
    }
    if (a === 'su') { var k = b.dataset.k, v = b.dataset.v; S.setup[k === 'len' ? 'length' : k] = (k === 'aspect' || k === 'res' || k === 'join') ? v : +v; drawSetup(); return save(); }
    if (a === 'song') { S.setup.song[b.dataset.k] = b.dataset.v; drawSetup(); return save(); }
    if (a === 'style-attach') { filePurpose = 'style'; $('#se-file').multiple = true; return $('#se-file').click(); }
    if (a === 'style-lib') return libPick('image', true, 'Style frames from your library (up to 8)', function (refs) { STYLE_REFS = STYLE_REFS.concat(refs).slice(-8); draw(); });
    if (a === 'style-run') {
      if (!STYLE_REFS.length) return toast('attach a few frames first', 1);
      toast('Studying the frames…');
      return save(true).then(function () { return api('/api/series/' + S.id + '/style', { refs: STYLE_REFS }); }).then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); toast('Style bible written'); });
    }
    /* cast */
    if (a === 'add-char' || a === 'add-rand') {
      var nc = { id: rid(), name: a === 'add-rand' ? pick(NAMES) : '', desc: '', traits: a === 'add-rand' ? randomTraits() : { kind: 'kid', role: (S.characters || []).length ? 'best friend' : 'lead' } };
      S.characters.push(nc); OPEN[nc.id] = true; TAB = 'cast'; save(true).then(draw); return;
    }
    if (a === 'toggle-build') { OPEN[it.id] = !(OPEN[it.id] != null ? OPEN[it.id] : !it.hero); return drawCast(), MI && MI.fill && MI.fill($('#se-cast')); }
    if (a === 'rand-char') { it.traits = randomTraits(); if (!it.name) it.name = pick(NAMES); save(true).then(drawCast); return; }
    if (a === 'dup-char') { var cp = { id: rid(), name: (it.name || 'Character') + ' 2', desc: it.desc, voice: it.voice, traits: JSON.parse(JSON.stringify(it.traits || {})) }; S.characters.splice(S.characters.indexOf(it) + 1, 0, cp); OPEN[cp.id] = true; save(true).then(drawCast); return; }
    if (a === 'tr') {
      var key = b.dataset.k, val = b.dataset.v;
      if (b.dataset.m) { var arr = it.traits[key] = it.traits[key] || [], ix = arr.indexOf(val); if (ix >= 0) arr.splice(ix, 1); else arr.push(val); b.classList.toggle('on', ix < 0); }
      else { var same = it.traits[key] === val; if (same) delete it.traits[key]; else it.traits[key] = val; $$('[data-k="' + key + '"]', b.parentNode).forEach(function (x) { x.classList.toggle('on', !same && x === b); }); }
      var od = b.closest('.fbody') && b.closest('.fbody').querySelector('.odesc');
      if (od) { var cd = curDesc(key, it.traits[key]); od.dataset.cur = cd; od.textContent = cd; od.classList.remove('hov'); }
      return save();
    }
    if (a === 'hear') {
      var line = (it.traits && it.traits.catch) || ('Hi! I\'m ' + (it.name || 'your new friend') + '. Let\'s sing together!');
      var au = $('#se-voice'); au.src = B + '/api/tts?text=' + encodeURIComponent(line) + (it.voice ? '&voice=' + encodeURIComponent(it.voice) : ''); au.play().catch(function () { toast('voice preview unavailable', 1); }); return;
    }
    if (a === 'add-loc') { S.locations.push({ id: rid(), name: '', desc: '' }); save(true).then(draw); return; }
    if (a === 'add-ep') { S.episodes.push({ id: rid(), title: '', idea: '', lesson: '', cast: S.characters.map(function (c) { return c.id; }).slice(0, 3), seconds: 10 }); TAB = 'eps'; save(true).then(draw); return; }
    /* objects */
    if (a === 'add-obj' || a === 'add-obj-rand') {
      var no = { id: rid(), name: '', desc: '', traits: a === 'add-obj-rand' ? randomObj() : { o_kind: 'car' } };
      if (a === 'add-obj-rand') no.name = (no.traits.o_kind || 'object').replace(/^./, function (x) { return x.toUpperCase(); });
      S.objects.push(no); OPEN[no.id] = true; TAB = 'objs'; save(true).then(draw); return;
    }
    if (a === 'rand-obj') { it.traits = randomObj(); save(true).then(drawObjs); return; }
    if (a === 'dup-obj') { var co = { id: rid(), name: (it.name || 'Object') + ' 2', desc: it.desc, traits: JSON.parse(JSON.stringify(it.traits || {})) }; S.objects.splice(S.objects.indexOf(it) + 1, 0, co); OPEN[co.id] = true; save(true).then(drawObjs); return; }
    if (a === 'obj-build') { if (it.hero && !confirm('Redraw this object? Its turnaround and details are drawn again from the new design.')) return; return enqueue(objSteps(it)); }
    if (a === 'obj-photo') { filePurpose = { obj: it.id }; $('#se-file').multiple = false; return $('#se-file').click(); }
    if (a === 'obj-lib') { var oid = it.id; return libPick('image', false, 'Object photo from your library', function (refs) { var ob = S.objects.find(function (x) { return x.id === oid; }); if (ob) enqueue(objSteps(ob, refs[0])); }); }
    if (a === 'objsheet') return enqueue([objSteps(it)[1]]);
    if (a === 'objdetail') return enqueue([objSteps(it)[2]]);
    if (a === 'prop') {
      var pe = itemOf(b).it, pid = b.dataset.id, pk = (pe.props || []).indexOf(pid);
      pe.props = pe.props || [];
      if (pk >= 0) pe.props.splice(pk, 1); else { if (pe.props.length >= 4) return toast('up to 4 objects per episode — each one is sent as a picture', 1); pe.props.push(pid); }
      b.classList.toggle('on', pk < 0); return save();
    }
    if (a === 'del-char' || a === 'del-loc' || a === 'del-ep' || a === 'del-obj') {
      if (!confirm('Remove this?')) return;
      o.list.splice(o.list.indexOf(it), 1); save(true).then(draw); return;
    }
    if (a === 'hero') {     /* build the whole character: hero, then the turnaround + expressions drawn from that hero */
      var lead = S.characters.find(function (c) { return c.hero && c.id !== it.id; }), nm = it.name || 'Character';
      return enqueue([{ kind: lead ? 'character' : 'hero', target: it.id, label: nm + ' — hero' },
                      { kind: 'sheet', target: it.id, label: nm + ' — turnaround' },
                      { kind: 'expr', target: it.id, label: nm + ' — expressions' }]);
    }
    if (a === 'hero-photo') { filePurpose = { hero: it.id }; $('#se-file').multiple = false; return $('#se-file').click(); }
    if (a === 'hero-lib') { var hid = it.id; return libPick('image', false, 'Hero photo from your library', function (refs) { heroFromPhoto(hid, refs[0]); }); }
    if (a === 'sheet') return run('sheet', it.id, (it.name || 'Character') + ' — turnaround');
    if (a === 'expr') return run('expr', it.id, (it.name || 'Character') + ' — expressions');
    if (a === 'lineup') return run('lineup', null, 'Cast lineup');
    if (a === 'loc') {
      if (it.image && hasViews(it) && !confirm('Redraw the location? Its turnaround is drawn again from the new picture too (3D views stay until you rebuild them).')) return;
      return enqueue([{ kind: 'location', target: it.id, label: (it.name || 'Location') },
                      { kind: 'locsheet', target: it.id, label: (it.name || 'Location') + ' — turnaround' }]);
    }
    if (a === 'locsheet') return enqueue([{ kind: 'locsheet', target: it.id, label: (it.name || 'Location') + ' — turnaround' }]);
    if (a === 'locviews') return enqueue(viewSteps(it));
    if (a === 'locview') return enqueue(viewSteps(it, +b.dataset.i));
    if (a === 'cast') {
      var ep = itemOf(b).it, id = b.dataset.id, kk = (ep.cast || []).indexOf(id);
      ep.cast = ep.cast || []; if (kk >= 0) ep.cast.splice(kk, 1); else ep.cast.push(id);
      b.classList.toggle('on', kk < 0); return save();
    }
    /* episodes */
    if (a === 'write-shots' || a === 'write-song' || a === 'write-musical' || a === 'write-chunks') {
      if (a === 'write-musical' && it.chunks && it.chunks.some(function (c) { return c.clip; }) && !confirm('A new song replaces the shot map (rendered shots stay in your library). Go on?')) return;
      var what = { 'write-song': 'song', 'write-musical': 'musical', 'write-chunks': 'chunks', 'write-shots': 'shots' }[a];
      toast({ song: 'Writing the song…', musical: 'Writing the song on your format…', chunks: 'Directing every shot…', shots: 'Writing the shot list…' }[what]);
      b.disabled = true;
      return save(true).then(function () { return api('/api/series/' + S.id + '/write', { episode: it.id, what: what }); })
        .then(function (d) { b.disabled = false; if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); });
    }
    if (a === 'scene') return run('scene', it.id, (it.title || 'Episode') + ' — scene');
    if (a === 'song') return run('song', it.id, (it.title || 'Episode') + ' — song');
    if (a === 'remap') { if (!confirm('Cut the song into shots again? Shot texts and renders on the map are cleared.')) return; return api('/api/series/' + S.id + '/episode/' + it.id + '/remap', {}).then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); }); }
    if (a === 'goto') { var el = $('#ch-' + it.id + '-' + b.dataset.i); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    if (a === 'link') { var oc = chunkOf(b); if (!oc.c || b.disabled) return; oc.c.link = b.dataset.v; save(true).then(drawEps); return; }
    if (a === 'key') { var ok = chunkOf(b); return run('keyframe', ok.e.id, (ok.e.title || 'Episode') + ' — shot ' + (ok.c.i + 1) + ' first frame', { i: ok.c.i }); }
    if (a === 'shot') { var os = chunkOf(b); return renderShot(os.e, os.c); }
    if (a === 'run') {
      var act = b.dataset.v, eid = it ? it.id : (RUN && RUN.run && RUN.run.ep);
      if (act === 'stop' && !confirm('Stop this run? Steps already finished stay in the series; the render running now is cancelled.')) return;
      if (act === 'start' && eid) { var e0 = epOf(eid); if (e0 && !e0.song && !(e0.idea || e0.title)) return toast('give the episode an idea first', 1); }
      return save(true).then(function () { return api('/api/series/' + S.id + '/run', { action: act, episode: eid }); })
        .then(function (r) { if (r.error) return toast(r.error, 1); RUN = r; drawRunBits(); toast({ start: 'Running in the background — safe to close this page', pause: 'Pausing after the current step', resume: 'Resumed', retry: 'Retrying', skip: 'Skipped', cancel: 'Step cancelled — Resume to redo it, or Skip', stop: 'Run stopped' }[act] || 'ok'); });
    }
    if (a === 'tab-hist') { TAB = 'hist'; draw(); return loadHist(); }
    if (a === 'akind') { AKIND = b.dataset.v; return drawAssets(); }
    if (a === 'asset-save') return saveAsset(b.dataset.k, b.dataset.k === 'styles' ? null : (b.dataset.k === 'songs' ? it.id : it.id));
    if (a === 'asset-save-cast') return saveAsset('cast');
    if (a === 'asset-use' || a === 'asset-del' || a === 'asset-rename') {
      var card = b.closest('[data-asset]'), aid = card.dataset.asset, asset = ASSETS.find(function (x) { return x.id === aid; }) || {};
      if (a === 'asset-del') { if (!confirm('Remove “' + asset.name + '” from your asset library? (It goes to the lab trash; series that use it keep their copy.)')) return; return api('/api/assets/delete', { asset: aid }).then(loadAssets); }
      if (a === 'asset-rename') { var nn = prompt('Name', asset.name || ''); if (!nn) return; return api('/api/assets/rename', { asset: aid, name: nn }).then(loadAssets); }
      var epSel = card.querySelector('.as-ep');
      if (asset.kind === 'songs' && !(epSel && epSel.value)) return toast('add an episode first', 1);
      if (asset.kind === 'styles' && S.style_prompt && !confirm('Replace this series’ style bible with “' + asset.name + '”?')) return;
      return save(true).then(function () { return api('/api/assets/use', { series: S.id, asset: aid, episode: epSel && epSel.value }); })
        .then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); toast('“' + asset.name + '” added to ' + (S.name || 'this series')); });
    }
    if (a === 'use-song') { filePurpose = { song: it.id }; return $('#se-song').click(); }
    if (a === 'song-lib') { var seid = it.id; return libPick('audio', false, 'Song from your library', function (refs) { toast('Using the song…'); useSongRef(seid, refs[0]); }); }
    if (a === 'recognise') {
      return api('/api/series/' + S.id + '/episode/' + it.id + '/recognise', {}).then(function (r) { if (r.error) return toast(r.error, 1); toast('Listening to your song — a few minutes'); pollRun(); });
    }
    if (a === 'walk-back' || a === 'restore') {
      if (!confirm(a === 'walk-back' ? 'Go back one step? (Your renders stay in the library, and you can undo this.)' : 'Restore this checkpoint? (You can undo this.)')) return;
      return api('/api/series/' + S.id + '/restore', a === 'walk-back' ? { back: true } : { version: b.dataset.v })
        .then(function (d) { if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); loadHist(); toast('Restored — any running render was paused'); });
    }
    if (a === 'assemble') {
      toast('Joining the shots under the song…'); b.disabled = true;
      return save(true).then(function () { return api('/api/series/' + S.id + '/episode/' + it.id + '/assemble', {}); })
        .then(function (d) { b.disabled = false; if (d.error) return toast(d.error, 1); S = d; fixup(); draw(); toast('Episode assembled — it\'s in your library'); });
    }
    if (a === 'rm-scene') return api('/api/series/' + S.id + '/episode/' + it.id + '/scene/remove', { file: b.dataset.n }).then(function (d) { if (!d.error) { S = d; fixup(); draw(); } });
    if (a === 'edit') return save(true).then(function () { return api('/api/series/' + S.id + '/episode/' + it.id + '/edit', {}); })
      .then(function (d) { if (d.error) return toast(d.error, 1); if (FRAMED) window.parent.postMessage({ mml: 'series-edit', project: d.project }, '*'); else location.href = B + '/editor?p=' + d.project; });
  });
  function zoom(m) {
    var z = document.createElement('div'); z.className = 'zoom';
    z.innerHTML = m.tagName === 'VIDEO' ? '<video src="' + m.src + '" controls autoplay loop playsinline></video>' : '<img src="' + m.src + '">';
    z.addEventListener('click', function (e) { if (e.target === z) z.remove(); }); document.body.appendChild(z);
  }
  /* hovering an option shows its line; leaving puts the picked option's line back */
  function odBox(c) { var f = c.closest('.fbody'); if (f) return f; var r = c.closest('.row'); return r && r.nextElementSibling; }
  document.addEventListener('mouseover', function (e) {
    var c = e.target.closest && e.target.closest('.chips button[data-k]'), box = c && odBox(c);
    var od = box && box.querySelector && box.querySelector('.odesc[data-od="' + c.dataset.k + '"]');
    if (od) { od.textContent = odesc(c.dataset.k, c.dataset.v) || od.dataset.cur; od.classList.add('hov'); }
  });
  document.addEventListener('mouseout', function (e) {
    if (!(e.target.closest && e.target.closest('.chips button[data-k]'))) return;
    $$('.odesc.hov').forEach(function (od) { od.textContent = od.dataset.cur || ''; od.classList.remove('hov'); });
  });
  document.addEventListener('mouseover', function (e) { var v = e.target.closest && e.target.closest('.pic video'); if (v && !v.closest('.zoom')) v.play().catch(function () { }); });
  document.addEventListener('mouseout', function (e) { var v = e.target.closest && e.target.closest('.pic video'); if (v && !v.closest('.zoom')) v.pause(); });

  api('/api/tts/voices').then(function (j) { VOICES = j.voices || []; if (!Array.isArray(VOICES)) VOICES = []; if (S) drawCast(); }).catch(function () { });
  api('/api/series/presets').then(function (j) { if (j && j.styles) { P = j; if (S) draw(); } });
  /* live render viewer: newest ComfyUI sampler preview of each running picture (204 = unchanged) */
  var LPV = {};
  setInterval(function () {
    if (document.hidden) return;
    $$('[data-livepv]').forEach(function (e) {
      var id = e.dataset.livepv, st = LPV[id] || (LPV[id] = { n: '', url: '' });
      if (st.busy) return; st.busy = 1;
      fetch(B + '/api/jobs/' + id + '/preview?n=' + st.n, { cache: 'no-store', credentials: 'same-origin' }).then(function (r) {
        if (r.status !== 200) return null; st.n = r.headers.get('X-Frame-N') || ''; return r.blob();
      }).then(function (bl) { if (bl) { if (st.url) URL.revokeObjectURL(st.url); st.url = URL.createObjectURL(bl); } })
        .catch(function () { }).then(function () {
          st.busy = 0;
          if (st.url) $$('[data-livepv="' + id + '"]').forEach(function (x) { var i = x.querySelector('img'); if (i.getAttribute('src') !== st.url) i.src = st.url; x.classList.add('on'); });
        });
    });
  }, 600);
  loadList();
})();
