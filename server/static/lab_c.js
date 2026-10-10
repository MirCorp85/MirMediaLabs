/* MEDIA LAB · CREATE CENTER layout (sample C, picked Oct 10 2026). Re-arranges the classic page — every feature stays:
   • header: brand · PROJECT picker (the chat session = a project: its own chat + media) · production state · GPU/queue · voice · settings
   • left: this project's media (the library, scoped to the project) · centre: MirAI chat · right: the production timeline
   • bottom dock: Create · Projects (Series + Production, merged) · Library · Editor · Publish · Tools (everything else)
   Opt out with ?classic=1 (or localStorage mml.layout=classic). Identical in both lab copies. */
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
  if (right) right.appendChild(prod);
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
        $('#lc-new-series').onclick = function () { window.mmlSeries && mmlSeries(); };
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
        $('#lc-open').onclick = function () { mmlProjects(p.id); };
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

  // ── Tools: everything that isn't a main feature ────────────────────────────────────────────────────────────────
  function tools() {
    var T = [['download', 'Downloader', 'links → MP3 / MP4', function () { mmlGrab(); }],
             ['tv', 'Series studio', 'build a series by hand', function () { mmlSeries(); }],
             ['layers', 'LoRA library', 'styles & characters', function () { lOpen(); }],
             ['sparkle', 'Skills & pipelines', 'presets, multi-step', function () { var c = $('.col.left .card.skl'); if (c) { c.style.display = 'block'; openBook && openBook(); } }],
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
    nav.innerHTML = [['create', 'lab', 'Create'], ['projects', 'layers', 'Projects'], ['library', 'grid', 'Library'], ['editor', 'scissors', 'Editor'],
                     ['publish', 'globe', 'Publish'], ['tools', 'wand', 'Tools']]
      .map(function (b) { return '<button data-t="' + b[0] + '"' + (b[0] === 'create' ? ' class="on"' : '') + '>' + mi(b[1]) + b[2] + '</button>'; }).join('');
    var wide = function () { return window.matchMedia('(min-width: 861px)').matches; };
    nav.querySelectorAll('button').forEach(function (b) {
      b.onclick = function () {
        var t = b.dataset.t;
        if (t === 'projects') return mmlProjects();
        if (t === 'publish') return mmlSocial();
        if (t === 'editor') return mmlEditor();
        if (t === 'tools') return tools();
        if (t === 'library' && wide()) { document.body.classList.toggle('lc-libwide'); b.classList.toggle('on', document.body.classList.contains('lc-libwide')); return; }
        setTab(t);
      };
    });
  }
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
      window.MI && MI.fill && MI.fill(grid);
    });
  }

  window.MI && MI.fill && MI.fill(document.body);
})();
