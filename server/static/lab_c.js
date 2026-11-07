/* MEDIA LAB · CREATE CENTER layout (sample C, picked Oct 10 2026). Re-arranges the classic page — every feature stays:
   • header: brand · PROJECT picker (the chat session = a project: its own chat + media) · production state · GPU/queue · voice · settings
   • left: this project's media (the library, scoped to the project) · centre: MirAI chat · right: the production timeline
   • bottom dock: Create · Projects (Series + Production, merged) · Library · Editor · Publish · Tools (everything else)
   Opt out with ?classic=1 (or localStorage mml.layout=classic). */
(function () {
  try { if (/[?&]classic=1/.test(location.search) || localStorage.getItem('mml.layout') === 'classic') return; } catch (e) { }
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var mi = function (n) { return '<i class="mi" data-ic="' + n + '"></i>'; };
  var J = function (u, o) { o = o || {}; if (o.body && typeof o.body !== 'string') { o.body = JSON.stringify(o.body); o.headers = { 'Content-Type': 'application/json' }; }
    return fetch(u, Object.assign({ credentials: 'same-origin' }, o)).then(function (r) { return r.json(); }); };
  document.body.classList.add('labc');

  // ── header: the project picker (moved session button) + production state ─────────────────────────────────────────
  var top = $('header.top'), brand = $('.top .brand'), sess = $('#b-sess');
  if (sess && brand) {
    sess.classList.add('lc-proj'); sess.title = 'Project — each one keeps its own chat and media';
    brand.after(sess);
    var st = document.createElement('span'); st.className = 'lc-state'; st.id = 'lc-state'; st.hidden = true; sess.after(st);
  }

  // ── left: the library becomes "this project's media" ────────────────────────────────────────────────────────────
  var lib = $('.col.right .card.lib'), left = $('.col.left'), right = $('.col.right');
  if (lib && left) { left.appendChild(lib); var h = lib.querySelector('.h'); if (h && h.firstChild && h.firstChild.nodeType === 3) h.firstChild.textContent = 'Project media'; }

  // ── right: production timeline ─────────────────────────────────────────────────────────────────────────────────
  var prod = document.createElement('div'); prod.className = 'card lc-prod'; prod.id = 'lc-prod';
  prod.innerHTML = '<div class="lc-empty">Loading productions…</div>';
  // panel no longer mounted (Nov 2 2026) — drawProd still drives the header state chip
  var ICON = { done: 'check-circle', now: 'hourglass', wait: 'bell', fail: 'warn', todo: 'dot' };
  var STATE = { running: ['working', 'run'], waiting: ['needs your OK', 'wait'], paused: ['stopped — needs you', 'fail'], done: ['finished', 'ok'] };
  var CUR = null, PIN = null;
  try { PIN = localStorage.getItem('mml.prodpin'); } catch (e) { }
  function act(id, a, body) {
    J('api/produce/' + id + '/' + a, { method: 'POST', body: body || {} }).then(function (j) { if (j.error) alert(j.error); drawProd(); });
  }
  function drawProd() {
    J('api/produce').then(function (j) {
      var L = (j.productions || []).filter(function (p) { return p.state !== 'cancelled'; });
      var live = L.find(function (p) { return p.id === PIN; }) || L.find(function (p) { return /running|waiting|paused/.test(p.state); }) || L[0];
      var s = $('#lc-state');
      if (!live) {
        if (s) s.hidden = true;
        prod.innerHTML = '<div class="h">' + mi('film') + ' Production</div><div class="lc-empty">No production yet. Ask MirAI in the chat — e.g. ' +
          '<i>“make a kids musical about a brave little turtle, 3 characters”</i> — and the whole pipeline (cast, world, song, shots, edit, post) shows up here.</div>' +
          '<button class="lc-btn" id="lc-new-series">' + mi('tv') + ' Or build a series by hand</button>';
        $('#lc-new-series', prod).onclick = function () { window.mmlSeries && mmlSeries(); };
        return;
      }
      return J('api/produce/' + live.id + '/project').then(function (p) {
        CUR = p;
        var stt = STATE[p.state] || [p.state, ''];
        if (s) { s.hidden = false; s.className = 'lc-state ' + stt[1]; s.textContent = p.title + ' · ' + stt[0]; s.onclick = function () { mmlProjects(); }; }
        var acts = [];
        if (p.state === 'waiting' && p.stage === 'approve_look') acts.push('<button class="lc-btn ok" data-a="approve">' + mi('check') + ' Approve the look</button>');
        if (p.state === 'paused') acts.push('<button class="lc-btn pri" data-a="retry">' + mi('play') + ' Resume</button>');
        if (p.state === 'running') acts.push('<button class="lc-btn" data-a="pause">' + mi('pause') + ' Pause</button>');
        acts.push('<button class="lc-btn" id="lc-open">' + mi('layers') + ' Open project</button>');
        var log = (p.log || []).slice(-6).reverse().map(function (e) { return '<div class="' + esc(e.lvl || '') + '">' + esc(e.msg) + '</div>'; }).join('');
        var others = L.filter(function (x) { return x.id !== p.id; }).slice(0, 4);
        prod.innerHTML = '<div class="h">' + mi('film') + ' Production</div><div class="ttl">' + esc(p.title) + '</div>' +
          (p.run ? '<small style="color:var(--dim)">' + p.run.left + ' steps left · ~' + Math.round(p.run.eta / 60) + ' min</small>' : '') +
          '<div class="lc-acts">' + acts.join('') + '</div>' +
          '<div>' + (p.steps || []).map(function (x) {
            return '<div class="lc-step ' + x.state + '">' + mi(ICON[x.state] || 'dot') + '<div><b>' + esc(x.label) + '</b>' + (x.detail ? '<small>' + esc(x.detail) + '</small>' : '') + '</div></div>'; }).join('') + '</div>' +
          '<div class="h" style="margin-top:4px">' + mi('brain') + ' MirAI</div><div class="lc-log">' + log + '</div>' +
          (others.length ? '<div class="h" style="margin-top:4px">' + mi('layers') + ' Other projects</div><div class="lc-mini">' + others.map(function (o) {
            return '<a data-pin="' + o.id + '"><span>' + esc(o.title) + '</span><small style="color:var(--dim)">' + esc((STATE[o.state] || [o.state])[0]) + '</small></a>'; }).join('') + '</div>' : '');
        prod.querySelectorAll('[data-a]').forEach(function (b) { b.onclick = function () { act(p.id, b.dataset.a); }; });
        prod.querySelectorAll('[data-pin]').forEach(function (a) { a.onclick = function () { PIN = a.dataset.pin; try { localStorage.setItem('mml.prodpin', PIN); } catch (e) { } drawProd(); }; });
        $('#lc-open', prod).onclick = function () { mmlProjects(p.id); };
      });
    }).catch(function () { });
  }
  drawProd(); setInterval(function () { if (!document.hidden) drawProd(); }, 10000);

  // ── Projects = Production + Series, one place ──────────────────────────────────────────────────────────────────
  window.mmlProjects = function (id) {
    if (document.getElementById('mml-pr')) return;
    var f = document.createElement('iframe'); f.id = 'mml-pr'; f.src = 'production' + (id ? '?id=' + id : ''); f.allow = 'autoplay; fullscreen';
    f.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:9997;background:#000'; document.body.appendChild(f);
  };
  window.mmlProduction = window.mmlProjects;
  var _series = window.mmlSeries;
  window.mmlSeries = function (sid) {
    if (!sid) return _series && _series();
    if (document.getElementById('mml-se')) return;
    var f = document.createElement('iframe'); f.id = 'mml-se'; f.src = 'series?id=' + encodeURIComponent(sid); f.allow = 'autoplay; fullscreen; clipboard-write';
    f.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:9998;background:#000'; document.body.appendChild(f);
  };
  window.addEventListener('message', function (e) {
    var d = e.data || {};
    if (d.mml === 'prod-series') { var f = document.getElementById('mml-pr'); if (f) f.remove(); mmlSeries(d.id); }
    if (d.mml === 'prod-close') drawProd();
  });

  // ── STUDIO (freefield.py / static/studio.html): open-weights apps; results land in the library ──────────────
  window.mmlStudio = function (appId) {
    var f = document.getElementById('mml-st'); if (f) return;
    f = document.createElement('iframe'); f.id = 'mml-st'; f.src = 'studio' + (appId ? '?app=' + encodeURIComponent(appId) : ''); f.allow = 'autoplay; fullscreen; clipboard-write';
    f.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:10000;background:#000'; document.body.appendChild(f);
    try { closeLB(); } catch (e) { }
  };
  window.addEventListener('message', function (e) {
    var d = e.data || {}; if (['studio-close', 'studio-editor', 'studio-attach'].indexOf(d.mml) < 0) return;
    var f = document.getElementById('mml-st'); if (f) f.remove();
    try { loadLib(); } catch (x) { }
    if (d.mml === 'studio-editor') try { mmlEditor(d.src || ''); } catch (x) { }
    if (d.mml === 'studio-attach' && d.ref) try { atts.push(d.ref); saveAtts(); renderAtts(); setTab('create'); toast('Attached — ready for your next request'); } catch (x) { }
  });

  // ── CAST (characters.py / static/cast.html): character-sheet packs; "Use in CopyCat" closes CAST and opens CopyCat ──
  window.mmlCast = function (id) {
    var f = document.getElementById('mml-cast'); if (f) return;
    f = document.createElement('iframe'); f.id = 'mml-cast'; f.src = 'cast' + (id ? '?id=' + encodeURIComponent(id) : ''); f.allow = 'clipboard-write';
    f.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:10000;background:#000'; document.body.appendChild(f);
    try { closeLB(); } catch (e) { }
  };
  window.addEventListener('message', function (e) {
    var d = e.data || {}; if (d.mml !== 'cast-close' && d.mml !== 'cast-copycat') return;
    var f = document.getElementById('mml-cast'); if (f) f.remove();
    if (d.mml === 'cast-copycat') { var w = document.getElementById('mml-cc'); if (w) w.remove(); try { mmlCopyCat(d.id); } catch (x) { } }
  });

  // ── Tools: everything that isn't a main feature ────────────────────────────────────────────────────────────────
  function tools() {
    var T = [['diamond', 'Studio', 'open-weights apps · image · video · audio', function () { mmlStudio(); }],
             ['sparkle', 'Motion studio', 'Remotion titles · captions · lyric & long videos', function () { mmlMotion(); }],
             ['bolt', 'Kinetic editor', 'kinetic type on a beat grid · effects', function () { mmlMotion({ editor: 1 }); }],
             ['pencil', 'Design', 'layered canvas · posters · mockups · Edit Elements', function () { mmlDesign(); }],
             ['users', 'Cast', 'character sheets · consistent faces for every tool', function () { mmlCast(); }],
             ['user', 'CopyCat', 'swap a person in a video · copy a dance', function () { mmlCopyCat(); }],
             ['download', 'Downloader', 'links → MP3 / MP4', function () { mmlGrab(); }],
             ['tv', 'Series studio', 'build a series by hand', function () { mmlSeries(); }],
             ['layers', 'LoRA library', 'styles & characters', function () { lOpen(); }],
             ['sparkle', 'Skills & pipelines', 'presets, multi-step', function () { window.openSkills && openSkills(); }],
             ['book', 'Command book', '/commands', function () { openBook(); }],
             ['palette', 'Theme', '', function () { openThemes(); }],
             ['type', 'Fonts', 'MIR typefaces', function () { window.MirFont && MirFont.openPicker(); }],
             ['note', 'Help · about', 'report a bug', function () { var b = $('#b-about'); b && b.onclick && b.onclick(); }]];
    var u = $('#b-users'); if (u && u.style.display !== 'none') T.push(['shield', 'Host control', 'who has access', function () { openUsers(); }]);
    var w = document.createElement('div'); w.className = 'lc-tools';
    w.innerHTML = '<div class="sh"><h4>TOOLS</h4>' + T.map(function (t, i) { return '<button data-i="' + i + '">' + mi(t[0]) + '<b>' + t[1] + '</b>' + (t[2] ? '<small>' + t[2] + '</small>' : '') + '</button>'; }).join('') + '</div>';
    w.onclick = function (e) { var b = e.target.closest('[data-i]'); w.remove(); if (b) try { T[+b.dataset.i][3](); } catch (x) { } };
    document.body.appendChild(w); window.MI && MI.fill && MI.fill(w);
  }

  // ── bottom dock (desktop) / tab bar (phone): the six main features ──────────────────────────────────────────────
  var nav = $('nav.tabs');
  if (nav) {
    nav.innerHTML = [['create', 'lab', 'Create'], ['projects', 'layers', 'Projects'], ['library', 'grid', 'Library'], ['editor', 'scissors', 'Editor'], ['studio', 'diamond', 'Studio'], ['design', 'pencil', 'Design'], ['motion', 'sparkle', 'Motion'], ['cast', 'users', 'Cast'], ['copycat', 'user', 'CopyCat'], ['flow', 'chain', 'Flow'],
                     ['publish', 'globe', 'Publish'], ['tools', 'wand', 'Tools']]
      .map(function (b) { return '<button data-t="' + b[0] + '"' + (b[0] === 'create' ? ' class="on"' : '') + '>' + mi(b[1]) + b[2] + '</button>'; }).join('');
    var wide = function () { return window.matchMedia('(min-width: 861px)').matches; };
    nav.querySelectorAll('button').forEach(function (b) {
      b.onclick = function () {
        var t = b.dataset.t;
        if (t === 'projects') return mmlProjects();
        if (t === 'publish') return mmlSocial();
        if (t === 'editor') return mmlEditor();
        if (t === 'motion') return mmlMotion();
        if (t === 'flow') return mmlFlow();
        if (t === 'studio') return mmlStudio();
        if (t === 'design') return mmlDesign();
        if (t === 'cast') return mmlCast();
        if (t === 'copycat') return mmlCopyCat();
        if (t === 'tools') return tools();
        if (t === 'create') return goHome();
        if (t === 'library' && wide()) { document.body.classList.toggle('lc-libwide'); b.classList.toggle('on', document.body.classList.contains('lc-libwide')); return; }
        setTab(t);
      };
    });
  }
  document.body.classList.add('lc-ready');
  // Create = home: close every studio overlay, panel and sheet, show the chat
  window.goHome = function () {
    ['mml-ed', 'mml-pr', 'mml-gr', 'mml-se', 'mml-so', 'mml-mo', 'mml-fl', 'mml-ds', 'mml-cc', 'mml-st', 'mml-ex', 'mml-rr'].forEach(function (id) { var f = document.getElementById(id); if (f) f.remove(); });
    document.querySelectorAll('.lc-tools').forEach(function (x) { x.remove(); });
    document.body.classList.remove('lc-libwide');
    try { if (document.getElementById('sheet').classList.contains('on')) closeSheet(); } catch (e) { }
    setTab('create');
    if (nav) nav.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x.dataset.t === 'create'); });
    try { var th = document.getElementById('thread'); if (th) th.scrollTop = th.scrollHeight; } catch (e) { }
  };
  // ── Library → PROJECTS tab: every project as a folder; open one and pull its media into your message ──────────────
  var filt = $('#filters');
  if (filt) {
    var pb = document.createElement('button'); pb.dataset.k = '__projects'; pb.textContent = 'PROJECTS'; filt.appendChild(pb);
    pb.onclick = function () { filt.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === pb); }); libProjects(); };
  }
  function tile(it) {
    var ref = it.kind === 'ref', n = encodeURIComponent(it.name), v = /\.(mp4|webm|mov)$/i.test(it.name), a = /\.(wav|mp3|flac|ogg|m4a)$/i.test(it.name);
    var th = a ? '' : '<img loading="lazy" src="' + (ref ? 'refthumb/' : 'thumb/') + n + '" style="width:100%;aspect-ratio:1;object-fit:cover;display:block;border-radius:10px">';
    return '<div class="lc-pt" style="position:relative;border-radius:10px;overflow:hidden;background:#111;border:1px solid var(--line)">' +
      (a ? '<div style="aspect-ratio:1;display:grid;place-items:center;color:var(--acc)">' + mi('music') + '</div>' : th) +
      (v ? '<span style="position:absolute;top:6px;left:6px;font-size:10px;background:#000a;padding:2px 6px;border-radius:6px">VIDEO</span>' : '') +
      '<div style="position:absolute;left:0;right:0;bottom:0;padding:4px 6px;font-size:10.5px;background:linear-gradient(transparent,#000d);display:flex;align-items:center;gap:4px">' +
      '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(it.label) + '</span>' +
      '<button data-use="' + esc(it.name) + '" data-ref="' + (ref ? 1 : 0) + '" data-lbl="' + esc(it.label) + '" title="Use in your next message" ' +
      'style="border:0;border-radius:6px;background:var(--acc);color:#fff;font-size:10px;font-weight:700;padding:3px 7px;cursor:pointer">USE</button></div>' +
      (it.redo ? '<button data-redo="' + esc(JSON.stringify(it.redo)) + '" data-lbl="' + esc(it.label) + '" title="Make this again, with your changes" ' +
        'style="position:absolute;top:6px;right:6px;z-index:2;border:0;border-radius:6px;background:#000c;color:#fff;font-size:10px;font-weight:700;padding:3px 7px;cursor:pointer">' + mi('refresh') + ' REDO</button>' : '') +
      '<a href="' + (ref ? 'refs/' : 'media/') + n + '" target="_blank" style="position:absolute;inset:0 0 26px 0" title="Open"></a></div>';
  }
  function useIt(name, isRef, label) {
    if (!isRef) return useAsRef(name);
    try {
      if (!atts.some(function (a) { return a.name === name; })) atts.push({ name: name, kind: kindOf(name), url: '/refs/' + name, label: label || name });
      saveAtts(); renderAtts(); toast('Attached: ' + (label || name)); if (innerWidth <= 860) setTab('create');
    } catch (e) { }
  }
  function seriesGroups(d) {
    var r = function (n, l) { return n ? { kind: 'ref', name: n, label: l } : null; }, L = function (n, l) { return n ? { kind: 'lib', name: n, label: l } : null; };
    var g = [], cast = [], world = [], shots = [], fin = [];
    (d.characters || []).forEach(function (c) { cast.push(r(c.hero, c.name), r(c.sheet, c.name + ' · turnaround')); });
    if (d.lineup) cast.push(r(d.lineup, 'cast lineup'));
    (d.locations || []).forEach(function (l) { world.push(r(l.image, l.name), r(l.sheet, l.name + ' · sheet')); });
    (d.episodes || []).forEach(function (e) {
      if (e.song) fin.push(L(e.song, (e.title || 'episode') + ' · song'));
      (e.chunks || []).forEach(function (c) { if (c.clip) shots.push(L(c.clip, 'shot ' + (c.i + 1))); });
      if (e.final) fin.push(L(e.final, (e.title || 'episode') + ' · final'));
    });
    [['Cast', cast], ['World', world], ['Song & final', fin], ['Shots', shots]].forEach(function (x) { var it = x[1].filter(Boolean); if (it.length) g.push({ title: x[0], items: it }); });
    return g;
  }
  function libProjects() {
    var grid = $('#grid'); $('#more').style.display = 'none';
    grid.innerHTML = '<div style="grid-column:1/-1;color:var(--faint);padding:8px 2px">Loading projects…</div>';
    Promise.all([J('api/produce'), J('api/series').catch(function () { return {}; })]).then(function (r) {
      var P = (r[0].productions || []).filter(function (p) { return p.sid; }), own = {};
      P.forEach(function (p) { own[p.sid] = 1; });
      var S = (r[1].series || []).filter(function (s) { return !own[s.id]; });
      var rows = P.map(function (p) { return { id: 'p:' + p.id, title: p.title, sub: 'production' }; })
        .concat(S.map(function (s) { return { id: 's:' + s.id, title: s.name, sub: 'series' }; }));
      $('#libcount').textContent = rows.length + ' project' + (rows.length === 1 ? '' : 's');
      grid.innerHTML = rows.length ? rows.map(function (x) {
        return '<div data-proj="' + x.id + '" style="grid-column:1/-1;display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;cursor:pointer">' +
          mi(x.sub === 'series' ? 'tv' : 'folder') + '<div style="flex:1;min-width:0"><b style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(x.title) + '</b>' +
          '<small style="color:var(--faint)">' + x.sub + '</small></div>' + mi('chevron-right') + '</div>'; }).join('')
        : '<div style="grid-column:1/-1;color:var(--faint);padding:8px 2px">No projects yet — ask MirAI to make one, or build a series in Tools → Series studio.</div>';
      grid.querySelectorAll('[data-proj]').forEach(function (el) { el.onclick = function () { libProject(el.dataset.proj, el.querySelector('b').textContent); }; });
      window.MI && MI.fill && MI.fill(grid);
    });
  }
  function libProject(key, title) {
    var grid = $('#grid'), isP = key.slice(0, 2) === 'p:', id = key.slice(2);
    grid.innerHTML = '<div style="grid-column:1/-1;color:var(--faint);padding:8px 2px">Loading…</div>';
    (isP ? J('api/produce/' + id + '/project').then(function (p) { return p.groups || []; })
         : J('api/series/' + id).then(seriesGroups)).then(function (G) {
      var n = G.reduce(function (a, g) { return a + g.items.length; }, 0);
      $('#libcount').textContent = n + ' item' + (n === 1 ? '' : 's');
      grid.innerHTML = '<button id="lc-pback" style="grid-column:1/-1;text-align:left;border:0;background:none;color:var(--acc);cursor:pointer;padding:4px 2px;font-weight:700">' +
        mi('chevron-left') + ' ' + esc(title) + '</button>' +
        (G.length ? G.map(function (g) { return '<div style="grid-column:1/-1;font-size:10.5px;letter-spacing:.14em;color:var(--dim);margin-top:6px">' + esc(g.title.toUpperCase()) + '</div>' + g.items.map(tile).join(''); }).join('')
          : '<div style="grid-column:1/-1;color:var(--faint);padding:8px 2px">Nothing made in this project yet.</div>');
      $('#lc-pback').onclick = libProjects;
      grid.querySelectorAll('[data-use]').forEach(function (b) { b.onclick = function (e) { e.preventDefault(); e.stopPropagation(); useIt(b.dataset.use, b.dataset.ref === '1', b.dataset.lbl); }; });
      grid.querySelectorAll('[data-redo]').forEach(function (b) { b.onclick = function (e) {
        e.preventDefault(); e.stopPropagation();
        var r = JSON.parse(b.dataset.redo), what = r.step === 'shot' ? 'shot ' + (r.target + 1) : b.dataset.lbl;
        var note = prompt('Redo ' + what + ' — what should change? (optional, e.g. "clean edges, no black spikes around the characters")', '');
        if (note === null) return;
        fetch('api/produce/' + id + '/redo_step', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ step: r.step, target: r.target == null ? null : r.target, note: note.trim() }) })
          .then(function (x) { return x.json(); })
          .then(function (j) { if (j && j.error) return toast(j.error, 1); toast('Redoing ' + what + ' — then a fresh final edit'); libProject(key, title); })
          .catch(function (er) { toast(String(er), 1); });
      }; });
      window.MI && MI.fill && MI.fill(grid);
    });
  }

  window.MI && MI.fill && MI.fill(document.body);
})();

/* ── LIBRARY SIDE PANEL: while Studio / Design / Motion / CopyCat is open (wide screens), the home page's own library
   card pins to a left column beside the tool. Drag a tile into the tool (it arrives as a real file drop), or click it to
   send it to the tool's first matching input. The tools are same-origin iframes, so the bridge runs from here. ──── */
(function () {
  'use strict';
  var TOOLS = { 'mml-st': 'studio', 'mml-ds': 'design', 'mml-mo': 'motion', 'mml-cc': 'copycat' };
  var W = 276, card = document.querySelector('.card.lib');
  if (!card) return;
  var home = document.createComment('lib-home');
  var mi = function (n) { return window.MI ? MI.html(n, 'sm') : ''; };
  var wide = function () { return window.matchMedia('(min-width: 861px)').matches; };
  var hidden = function () { try { return localStorage.getItem('mml.libside') === '0'; } catch (e) { return false; } };
  var say = function (t) { try { toast(t); } catch (e) { } };
  var kindOf = function (n) { return /\.(mp4|webm|mov|m4v|mkv)$/i.test(n) ? 'video' : /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(n) ? 'audio' : 'image'; };

  var tab = document.createElement('button');
  tab.id = 'lc-sidetab'; tab.type = 'button';
  tab.onclick = function () { try { localStorage.setItem('mml.libside', hidden() ? '1' : '0'); } catch (e) { } layout(); };
  document.body.appendChild(tab);
  // a clear Hide button in the library's own header (only while it sits beside a tool)
  var hideBtn = document.createElement('button');
  hideBtn.id = 'lc-sidehide'; hideBtn.type = 'button'; hideBtn.className = 'btn sm'; hideBtn.title = 'Hide the library (bring it back with the Library tab on the left edge)';
  hideBtn.onclick = function (e) { e.stopPropagation(); try { localStorage.setItem('mml.libside', '0'); } catch (x) { } layout(); };
  var head = card.querySelector('.h'); if (head) head.appendChild(hideBtn);

  function open() { for (var id in TOOLS) { var e = document.getElementById(id); if (e) return e; } return null; }
  function frameOf(o) { return o && (o.tagName === 'IFRAME' ? o : o.querySelector('iframe')); }

  function layout() {
    var o = open(), on = !!o && wide(), show = on && !hidden();
    document.body.classList.toggle('lc-side', on);
    if (show && card.parentNode !== document.body) { card.parentNode.insertBefore(home, card); document.body.appendChild(card); }
    if (!show && home.parentNode) { home.parentNode.insertBefore(card, home); home.remove(); }
    card.classList.toggle('lc-sidecard', show);
    tab.innerHTML = mi('chevron-right') + '<span>Library</span>';
    tab.title = 'Show the library';
    tab.classList.toggle('shut', !show);
    hideBtn.innerHTML = mi('chevron-left') + 'Hide';
    for (var id in TOOLS) {
      var e = document.getElementById(id); if (!e) continue;
      var off = show ? W : on ? 24 : 0;                          // hidden: leave room for the slim Library tab
      e.style.left = off + 'px'; e.style.width = off ? 'calc(100% - ' + off + 'px)' : '100%'; e.style.right = 'auto';
      if (on) hook(e);
    }
  }
  new MutationObserver(function (m) {
    if (m.some(function (r) { return [].some.call(r.addedNodes, isTool) || [].some.call(r.removedNodes, isTool); })) layout();
  }).observe(document.body, { childList: true });
  function isTool(n) { return n && n.id && TOOLS[n.id]; }
  addEventListener('resize', layout);
  setInterval(function () {                                      // new results land while a tool is open
    if (card.classList.contains('lc-sidecard') && !document.hidden && !card.matches(':hover')) try { loadLib(true); } catch (e) { }
  }, 20000);

  // drag out of the library
  card.addEventListener('mouseover', function (e) { var t = e.target.closest('.th'); if (t && !t.draggable) t.draggable = true; });
  card.addEventListener('dragstart', function (e) {
    var t = e.target.closest('.th'); if (!t) return;
    e.dataTransfer.setData('text/mml-lib', t.dataset.n);
    e.dataTransfer.setData('text/uri-list', location.origin + '/media/' + encodeURIComponent(t.dataset.n));
    e.dataTransfer.effectAllowed = 'copy';
  });
  // click a tile while a tool is open → into the tool
  card.addEventListener('click', function (e) {
    if (!card.classList.contains('lc-sidecard')) return;
    var t = e.target.closest('.th'); if (!t || e.target.closest('button')) return;
    e.preventDefault(); e.stopPropagation(); send(t.dataset.n);
  }, true);

  function send(name) {
    var o = open(); if (!o) return;
    var kind = TOOLS[o.id], f = frameOf(o), w = f && f.contentWindow;
    if (!w) return;
    if (kind === 'studio') return w.postMessage({ mml: 'studio-lib', name: name }, '*');
    if (kind === 'motion') { w.postMessage({ mml: 'motion-add', src: 'lib:' + name }, '*'); return say('Sent to Motion'); }
    toInput(w, name).then(function (ok) { say(ok ? 'Added ' + name : 'Drag it onto the spot you want in the tool'); });
  }
  function fileFor(w, name) {
    return w.fetch('/media/' + encodeURIComponent(name), { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob();
    }).then(function (b) { return new w.File([b], name, { type: b.type || (kindOf(name) + '/*') }); });
  }
  function accepts(inp, kind) { var a = (inp.accept || '').toLowerCase(); return !a || a.indexOf(kind + '/') >= 0 || a.indexOf('*') >= 0 && a.indexOf('/') < 0; }
  function setFile(w, inp, file) {
    var dt = new w.DataTransfer(); dt.items.add(file); inp.files = dt.files;
    inp.dispatchEvent(new w.Event('input', { bubbles: true })); inp.dispatchEvent(new w.Event('change', { bubbles: true }));
  }
  function toInput(w, name, near) {
    var doc = w.document, kind = kindOf(name);
    var all = [].slice.call(doc.querySelectorAll('input[type=file]')).filter(function (i) { return accepts(i, kind) && !i.disabled; });
    if (near) { var lab = near.closest('label,.drop,[class*=drop],[class*=upload]'); var mine = lab && lab.querySelector('input[type=file]'); if (mine) all = [mine]; }
    var inp = all.filter(function (i) { return !i.files || !i.files.length; })[0] || all[0];
    if (!inp) return Promise.resolve(false);
    return fileFor(w, name).then(function (file) { setFile(w, inp, file); return true; }).catch(function () { return false; });
  }
  // drop into a tool: turn the library drag into a real file drop on whatever is under the pointer
  function hook(o) {
    var f = frameOf(o); if (!f) return;
    var go = function () {
      var w = f.contentWindow; if (!w || w.__mmlLib) return;
      try { w.__mmlLib = 1; } catch (e) { return; }
      var has = function (e) { return e.dataTransfer && [].indexOf.call(e.dataTransfer.types || [], 'text/mml-lib') >= 0; };
      ['dragenter', 'dragover'].forEach(function (ev) { w.addEventListener(ev, function (e) { if (has(e)) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } }, true); });
      w.addEventListener('drop', function (e) {
        if (!has(e)) return;
        e.preventDefault(); e.stopImmediatePropagation();
        var name = e.dataTransfer.getData('text/mml-lib'), target = e.target, x = e.clientX, y = e.clientY;
        if (TOOLS[o.id] === 'studio') { w.postMessage({ mml: 'studio-lib', name: name, at: [x, y] }, '*'); return; }
        if (TOOLS[o.id] === 'motion') { w.postMessage({ mml: 'motion-add', src: 'lib:' + name }, '*'); return; }
        fileFor(w, name).then(function (file) {
          if (target.matches && target.matches('input[type=file]')) return setFile(w, target, file);
          var dt = new w.DataTransfer(), handled = false; dt.items.add(file);
          ['dragenter', 'dragover', 'drop'].forEach(function (ev) {
            var de = new w.DragEvent(ev, { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, clientX: x, clientY: y });
            target.dispatchEvent(de); if (ev === 'drop') handled = de.defaultPrevented;
          });
          if (!handled) toInput(w, name, target).then(function (ok) { if (!ok) say('This spot does not take files'); });
        }).catch(function () { say('Could not load ' + name); });
      }, true);
      if (TOOLS[o.id] === 'copycat') theme(w);
    };
    try { if (f.contentDocument && f.contentDocument.readyState !== 'loading' && f.contentWindow.location.href !== 'about:blank') go(); } catch (e) { }
    if (!f.__mmlHooked) { f.__mmlHooked = 1; f.addEventListener('load', function () { try { f.contentWindow.__mmlLib = 0; } catch (e) { } go(); }); }
  }
  // CopyCat wears the current lab theme (its own build ships a lime accent)
  function theme(w) {
    var cs = getComputedStyle(document.documentElement), v = function (k) { return cs.getPropertyValue(k).trim(); };
    var css = ':root{--bg:' + v('--bg') + ';--panel:' + v('--panel') + ';--panel-2:' + v('--panel2') + ';--line:' + v('--line2') + ';--text:' + v('--ink') +
      ';--muted:' + v('--dim') + ';--accent:' + v('--acc') + ';--accent-ink:' + v('--bg') + ';--danger:' + v('--red') + '}' +
      'body{background:var(--bg)!important;font-family:' + (v('--sans') || 'system-ui,sans-serif') + '}';
    var d = w.document, s = d.getElementById('mml-theme') || d.head.appendChild(Object.assign(d.createElement('style'), { id: 'mml-theme' }));
    s.textContent = css;
  }
  window.addEventListener('message', function (e) { if ((e.data || {}).mml === 'studio-lib-miss') say('Open an app in Studio first'); });
  layout();
})();
