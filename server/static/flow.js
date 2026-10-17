/* MIR MEDIA LABS · NODE FLOW — ComfyUI-style wires on MIR MEDIA LABS building blocks (nodeflow.py).
   Graph: {id,name,nodes:[{id,type,x,y,values}],links:[{id,from:[node,port],to:[node,port]}]}.
   Ports are typed (video/image/audio/text); incompatible wires are refused. Runs execute on the server
   (/api/flow/run) in topological order through /api/generate's direct-model path — the page only polls. */
(function () {
  'use strict';
  var B = location.pathname.indexOf('/mlab') === 0 ? '/mlab' : '';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var mi = function (n) { return '<i class="mi" data-ic="' + n + '"></i>'; };
  var icons = function () { try { if (window.MI && MI.scan) MI.scan(); } catch (e) { } };
  var clone = function (o) { return JSON.parse(JSON.stringify(o)); };
  function api(path, body) {
    var o = { method: body ? 'POST' : 'GET', headers: {}, cache: 'no-store', credentials: 'same-origin' };
    if (body) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return { error: 'HTTP ' + r.status }; }); });
  }
  var toastT;
  function toast(t, err) { var e = $('#nf-toast'); e.textContent = t; e.className = 'nf-toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'nf-toast'; }, err ? 5200 : 2600); }

  /* theme — same table as Motion Studio / editor */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    ['--bg', '--panel', '--panel2', '--ink', '--acc'].forEach(function (k, i) { r.setProperty(k, t[i]); }); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/miros-prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });
  var SESSION = (function () { try { return localStorage.getItem('mml.session') || ''; } catch (e) { return ''; } })();

  var CAT = {}, TPL = [], G = { id: '', name: 'Untitled flow', nodes: [], links: [] }, VIEW = { x: 40, y: 30, k: 1 };
  var SEL = null, RUN = null, RUNST = null, pollT = null;
  var world = $('#nf-world'), canvas = $('#nf-canvas'), svg = $('#nf-wires');
  var TCOL = { video: 'var(--video)', image: 'var(--image)', audio: 'var(--audio)', text: 'var(--text)', any: 'var(--any)', visual: 'var(--any)', same: 'var(--any)' };

  /* ── types ── */
  function node(id) { for (var i = 0; i < G.nodes.length; i++) if (G.nodes[i].id === id) return G.nodes[i]; return null; }
  function docOf(t) { var c = CAT[t] || {}, d = c.doc || {}; return { short: d.short || c.desc || '', when: d.when || '', tip: d.tip || '', tech: c.desc || '' }; }
  function docLong(t) { var d = docOf(t); return [d.when, d.tip ? 'Tip: ' + d.tip : ''].filter(Boolean).join('  '); }
  function info(t) { var d = docOf(t), c = CAT[t] || {};
    modal('<h3>' + mi(c.icon || 'box') + ' ' + esc(c.label || t) + '</h3><p>' + esc(d.short) + '</p>' + (d.when ? '<p><b>When to use it</b><br>' + esc(d.when) + '</p>' : '') +
      (d.tip ? '<p><b>Tip</b><br>' + esc(d.tip) + '</p>' : '') + (d.tech && d.tech !== d.short ? '<p class="dim" style="font-size:12px">' + esc(d.tech) + '</p>' : '')); }
  function spec(n) { return CAT[n.type] || { ins: [], outs: [], label: n.type }; }
  function portDef(n, pid, dir) { var l = spec(n)[dir === 'in' ? 'ins' : 'outs'] || []; for (var i = 0; i < l.length; i++) if (l[i][0] === pid) return l[i]; return null; }
  function outType(n, pid, seen) {
    var p = portDef(n, pid, 'out'); if (!p) return 'any';
    if (p[1] === 'any' && n.values && n.values._kind) return n.values._kind;
    if (p[1] === 'same') {
      seen = seen || {}; if (seen[n.id]) return 'visual'; seen[n.id] = 1;
      var l = G.links.filter(function (x) { return x.to[0] === n.id; })[0];
      return l && node(l.from[0]) ? outType(node(l.from[0]), l.from[1], seen) : 'visual';
    }
    return p[1];
  }
  function fits(o, i) {
    if (i === 'any' || o === 'any' || o === i) return true;
    if (i === 'visual') return o === 'image' || o === 'video' || o === 'visual';
    if (o === 'visual') return i === 'image' || i === 'video';
    return false;
  }

  /* ── view ── */
  function applyView() { world.style.transform = 'translate(' + VIEW.x + 'px,' + VIEW.y + 'px) scale(' + VIEW.k + ')'; }
  function toWorld(cx, cy) { var r = canvas.getBoundingClientRect(); return { x: (cx - r.left - VIEW.x) / VIEW.k, y: (cy - r.top - VIEW.y) / VIEW.k }; }
  function fit() {
    if (!G.nodes.length) return;
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    G.nodes.forEach(function (n) { var el = world.querySelector('[data-n="' + n.id + '"]'); var h = el ? el.offsetHeight : 160;
      x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y); x1 = Math.max(x1, n.x + 220); y1 = Math.max(y1, n.y + h); });
    var r = canvas.getBoundingClientRect(), k = Math.min(1.2, Math.max(0.3, Math.min((r.width - 60) / (x1 - x0), (r.height - 60) / (y1 - y0))));
    VIEW = { k: k, x: (r.width - (x1 - x0) * k) / 2 - x0 * k, y: (r.height - (y1 - y0) * k) / 2 - y0 * k }; applyView(); wires();
  }

  /* ── render ── */
  function nodeHTML(n) {
    var s = spec(n), st = (RUNST && RUNST.nodes[n.id]) || null;
    var ins = (s.ins || []).map(function (p) {
      return '<div class="port in' + (p[3] ? ' multi' : '') + '" style="--c:' + TCOL[p[1]] + '"><span class="dot" data-port="' + p[0] + '" data-dir="in" title="' + esc(p[1] + (p[3] ? ' · takes several' : '')) + '"></span>' + esc(p[2]) + '</div>';
    }).join('');
    var outs = (s.outs || []).map(function (p) {
      var t = outType(n, p[0]);
      return '<div class="port out" style="--c:' + TCOL[t] + '">' + esc(p[2]) + '<span class="dot" data-port="' + p[0] + '" data-dir="out" title="' + esc(t) + '"></span></div>';
    }).join('');
    var sum = summary(n), stc = st ? st.status : '', note = st ? (st.note || st.status) : sum;
    var pv = '';
    if (st && st.outs && st.outs.length) pv = '<div class="pv">' + st.outs.slice(0, 6).map(function (o) {
      if (o.kind === 'image') return '<img src="' + B + o.url + '" loading="lazy">';
      if (o.kind === 'video') return '<video src="' + B + o.url + '#t=0.5" muted preload="metadata" playsinline></video>';
      if (o.kind === 'audio') return '<audio src="' + B + o.url + '" controls preload="none"></audio>';
      return '<div class="tx">' + esc(o.text) + '</div>';
    }).join('') + '</div>';
    var ic = { running: 'hourglass', done: 'check-circle', error: 'warn', stopped: 'stop' }[stc] || 'dot';
    return '<div class="node' + (SEL === n.id ? ' sel' : '') + '" data-n="' + n.id + '" style="left:' + n.x + 'px;top:' + n.y + 'px;--nc:' + (s.color || 'var(--acc)') + '">' +
      '<div class="hd">' + mi(s.icon || 'box') + '<b>' + esc(s.label) + '</b><button class="x" data-info="' + n.type + '" title="' + esc(docLong(n.type)) + '">' + mi('book') + '</button><button class="x" data-del="' + n.id + '" title="Remove node">' + mi('close') + '</button></div>' +
      '<div class="ds" title="' + esc(docLong(n.type)) + '">' + esc(docOf(n.type).short) + '</div>' +
      '<div class="io"><div class="col">' + ins + '</div><div class="col out">' + outs + '</div></div>' +
      '<div class="st ' + stc + '">' + mi(ic) + '<span>' + esc(note || '') + '</span></div>' + pv + '</div>';
  }
  function summary(n) {
    var v = n.values || {};
    if (v._label) return v._label;
    if (n.type === 'in_text') return (v.text || 'empty').slice(0, 60);
    var s = spec(n), bits = [];
    (s.fields || []).forEach(function (f) { if (v[f.k] !== undefined && v[f.k] !== '' && String(v[f.k]) !== String(f.def) && bits.length < 3) bits.push((f.label || f.k).split(/[(:]/)[0].trim() + ' ' + v[f.k]); });
    return bits.join(' · ') || 'ready';
  }
  function render() {
    world.querySelectorAll('.node').forEach(function (e) { e.remove(); });
    world.insertAdjacentHTML('beforeend', G.nodes.map(nodeHTML).join(''));
    icons(); requestAnimationFrame(wires);
  }
  function dotXY(nid, pid, dir) {
    var el = world.querySelector('[data-n="' + nid + '"] .dot[data-port="' + pid + '"][data-dir="' + dir + '"]');
    if (!el) return null;
    var r = el.getBoundingClientRect(); return toWorld(r.left + r.width / 2, r.top + r.height / 2);
  }
  function curve(a, b) { var dx = Math.max(50, Math.abs(b.x - a.x) * 0.5); return 'M' + a.x + ',' + a.y + ' C' + (a.x + dx) + ',' + a.y + ' ' + (b.x - dx) + ',' + b.y + ' ' + b.x + ',' + b.y; }
  function wires(tmp) {
    var h = '';
    G.links.forEach(function (l) {
      var a = dotXY(l.from[0], l.from[1], 'out'), b = dotXY(l.to[0], l.to[1], 'in'); if (!a || !b) return;
      h += '<path d="' + curve(a, b) + '" stroke="' + TCOL[outType(node(l.from[0]), l.from[1])] + '" data-l="' + l.id + '"><title>Click to remove this wire</title></path>';
    });
    if (tmp && tmp.a && tmp.b) h += '<path class="tmp" d="' + curve(tmp.a, tmp.b) + '" stroke="' + TCOL[tmp.t] + '"></path>';
    svg.innerHTML = h;
  }

  /* ── edits ── */
  var dirty = false;
  function changed() { dirty = true; $('#nf-state').textContent = 'unsaved'; try { localStorage.setItem('mml.flow.draft', JSON.stringify(G)); } catch (e) { } }
  function addNode(type, x, y) {
    var s = CAT[type]; if (!s) return;
    var vals = {}; (s.fields || []).forEach(function (f) { if (f.def !== '' && f.def != null) vals[f.k] = f.def; });
    if (x == null) { var r = canvas.getBoundingClientRect(), c = toWorld(r.left + r.width / 2 - 110, r.top + r.height / 2 - 80); x = c.x + (G.nodes.length % 5) * 18; y = c.y + (G.nodes.length % 5) * 18; }
    var n = { id: 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), type: type, x: Math.round(x), y: Math.round(y), values: vals };
    G.nodes.push(n); SEL = n.id; changed(); render(); inspect();
  }
  function delNode(id) { G.nodes = G.nodes.filter(function (n) { return n.id !== id; }); G.links = G.links.filter(function (l) { return l.from[0] !== id && l.to[0] !== id; }); if (SEL === id) SEL = null; changed(); render(); inspect(); }
  function connect(from, to) {
    var a = node(from[0]), b = node(to[0]); if (!a || !b || a === b) return;
    var ot = outType(a, from[1]), ip = portDef(b, to[1], 'in');
    if (!ip) return;
    if (!fits(ot, ip[1])) { toast('Can\'t wire ' + ot + ' into ' + ip[1] + ' (' + ip[2] + ')', true); return; }
    if (wouldLoop(from[0], to[0])) { toast('That wire would make a loop', true); return; }
    if (G.links.some(function (l) { return l.from[0] === from[0] && l.from[1] === from[1] && l.to[0] === to[0] && l.to[1] === to[1]; })) return;
    if (!ip[3]) G.links = G.links.filter(function (l) { return !(l.to[0] === to[0] && l.to[1] === to[1]); });
    G.links.push({ id: 'l' + Date.now().toString(36), from: from, to: to }); changed(); render();
  }
  function wouldLoop(src, dst) {
    var stack = [dst], seen = {};
    while (stack.length) { var c = stack.pop(); if (c === src) return true; if (seen[c]) continue; seen[c] = 1;
      G.links.forEach(function (l) { if (l.from[0] === c) stack.push(l.to[0]); }); }
    return false;
  }

  /* ── pointer: pan, zoom, drag nodes, drag wires ── */
  var drag = null, pts = {};
  canvas.addEventListener('pointerdown', function (e) {
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (Object.keys(pts).length === 2) { var p = Object.values(pts); drag = { kind: 'pinch', d: Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y), k: VIEW.k, v: clone(VIEW) }; return; }
    var inf = e.target.closest('[data-info]'); if (inf) { info(inf.dataset.info); return; }
    var t = e.target, dot = t.closest('.dot'), del = t.closest('[data-del]'), nd = t.closest('.node'), wire = t.closest('path[data-l]');
    if (del) { delNode(del.dataset.del); return; }
    if (wire) { G.links = G.links.filter(function (l) { return l.id !== wire.dataset.l; }); changed(); render(); return; }
    if (dot) {
      var nid = dot.closest('.node').dataset.n, pid = dot.dataset.port;
      if (dot.dataset.dir === 'in') {                    // pick up an existing wire from its input end
        var l = G.links.filter(function (x) { return x.to[0] === nid && x.to[1] === pid; }).pop();
        if (!l) return;
        G.links = G.links.filter(function (x) { return x !== l; }); changed(); render();
        drag = { kind: 'wire', from: l.from, t: outType(node(l.from[0]), l.from[1]) };
      } else drag = { kind: 'wire', from: [nid, pid], t: outType(node(nid), pid) };
      canvas.setPointerCapture(e.pointerId); hilite(drag.t); e.preventDefault(); return;
    }
    if (nd) {
      var n = node(nd.dataset.n); if (SEL !== n.id) { SEL = n.id; world.querySelectorAll('.node').forEach(function (x) { x.classList.toggle('sel', x.dataset.n === SEL); }); inspect(); }
      if (t.closest('.hd') && !t.closest('button')) { drag = { kind: 'node', n: n, el: nd, sx: e.clientX, sy: e.clientY, x: n.x, y: n.y }; canvas.setPointerCapture(e.pointerId); }
      return;
    }
    if (SEL) { SEL = null; render(); inspect(); }
    drag = { kind: 'pan', sx: e.clientX, sy: e.clientY, x: VIEW.x, y: VIEW.y }; canvas.classList.add('pan'); canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', function (e) {
    if (pts[e.pointerId]) pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (!drag) return;
    if (drag.kind === 'pinch') { var p = Object.values(pts); if (p.length < 2) return; var d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
      zoomAt((p[0].x + p[1].x) / 2, (p[0].y + p[1].y) / 2, drag.k * d / drag.d); return; }
    if (drag.kind === 'pan') { VIEW.x = drag.x + e.clientX - drag.sx; VIEW.y = drag.y + e.clientY - drag.sy; applyView(); return; }
    if (drag.kind === 'node') { drag.n.x = Math.round(drag.x + (e.clientX - drag.sx) / VIEW.k); drag.n.y = Math.round(drag.y + (e.clientY - drag.sy) / VIEW.k);
      drag.el.style.left = drag.n.x + 'px'; drag.el.style.top = drag.n.y + 'px'; drag.moved = true; wires(); return; }
    if (drag.kind === 'wire') wires({ a: dotXY(drag.from[0], drag.from[1], 'out'), b: toWorld(e.clientX, e.clientY), t: drag.t });
  });
  function end(e) {
    delete pts[e.pointerId];
    if (!drag) return;
    var d = drag; drag = null; canvas.classList.remove('pan');
    if (d.kind === 'node' && d.moved) changed();
    if (d.kind === 'wire') {
      hilite(null);
      var el = document.elementFromPoint(e.clientX, e.clientY), dot = el && el.closest && el.closest('.dot[data-dir="in"]');
      if (dot) connect(d.from, [dot.closest('.node').dataset.n, dot.dataset.port]); else wires();
    }
  }
  canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
  function zoomAt(cx, cy, k) { k = Math.max(0.25, Math.min(2, k)); var w = toWorld(cx, cy), r = canvas.getBoundingClientRect();
    VIEW.k = k; VIEW.x = cx - r.left - w.x * k; VIEW.y = cy - r.top - w.y * k; applyView(); }
  canvas.addEventListener('wheel', function (e) { e.preventDefault(); zoomAt(e.clientX, e.clientY, VIEW.k * (e.deltaY < 0 ? 1.1 : 0.9)); }, { passive: false });
  function hilite(t) {
    world.querySelectorAll('.dot[data-dir="in"]').forEach(function (d) {
      d.classList.remove('ok', 'no'); if (!t) return;
      var p = portDef(node(d.closest('.node').dataset.n), d.dataset.port, 'in'); d.classList.add(p && fits(t, p[1]) ? 'ok' : 'no');
    });
  }

  /* ── inspector: fields from params.py MODELS + param_docs (same options as the ⚙ panel) ── */
  function inspect() {
    var box = $('#nf-insp'), n = SEL && node(SEL);
    box.classList.toggle('empty', !n);
    if (!n) { box.innerHTML = '<div class="dim pad">Select a node to see its settings.</div>'; return; }
    var s = spec(n), v = n.values || (n.values = {}), h = '<h3>' + mi(s.icon || 'box') + esc(s.label) + '</h3><div class="about"><b>' + esc(docOf(n.type).short) + '</b>' +
      (docOf(n.type).when ? '<br>' + esc(docOf(n.type).when) : '') + (docOf(n.type).tip ? '<br><i>Tip: ' + esc(docOf(n.type).tip) + '</i>' : '') + '</div>';
    if (s.form === 'file') {
      h += '<div class="fld"><label>File</label><div class="row"><button class="eb" data-f="upload">' + mi('upload') + ' Upload</button><button class="eb" data-f="lib">' + mi('grid') + ' Library</button></div>' +
        '<div class="pick">' + (v._label ? esc(v._label) + preview(v._kind, v._url) : 'nothing chosen yet') + '</div></div>';
    }
    var groups = {}, order = [];
    (s.fields || []).forEach(function (f) { var g = f.group || 'Settings'; if (!groups[g]) { groups[g] = []; order.push(g); } groups[g].push(f); });
    order.forEach(function (g, gi) {
      var adv = /advanced/i.test(g);
      h += '<details' + (gi < 2 && !adv ? ' open' : '') + '><summary>' + esc(g) + '</summary>' + groups[g].map(function (f) { return field(f, v[f.k]); }).join('') + '</details>';
    });
    if (s.model) h += '<div class="fld dim" style="font-size:11px">Runs on ' + esc(s.model.toUpperCase()) + ' through the lab queue with exactly these values (blank = default).</div>';
    box.innerHTML = h; icons();
  }
  function preview(kind, url) {
    if (!url) return '';
    if (kind === 'image') return '<img src="' + B + url + '">';
    if (kind === 'video') return '<video src="' + B + url + '" controls muted playsinline preload="metadata"></video>';
    if (kind === 'audio') return '<audio src="' + B + url + '" controls style="width:100%;margin-top:6px"></audio>';
    return '';
  }
  function field(f, val) {
    if (val === undefined) val = f.def;
    var id = 'f_' + f.k, h = '<div class="fld"><label for="' + id + '">' + esc(f.label || f.k) + '</label>';
    if (f.type === 'select') {
      h += '<select id="' + id + '" data-k="' + f.k + '">' + (f.opts || []).map(function (o) { var k = Array.isArray(o) ? o[0] : o, l = Array.isArray(o) ? o[1] : o;
        return '<option value="' + esc(k) + '"' + (String(k) === String(val) ? ' selected' : '') + '>' + esc(l) + '</option>'; }).join('') + '</select>';
      var od = f.opt_desc && f.opt_desc[String(val)];
      if (od) h += '<div class="d">' + esc(od) + '</div>';
    } else if (f.type === 'number') {
      h += '<input id="' + id + '" type="number" data-k="' + f.k + '" value="' + esc(val) + '"' + (f.min != null ? ' min="' + f.min + '"' : '') + (f.max != null ? ' max="' + f.max + '"' : '') + ' step="' + (f.step || 1) + '">';
    } else if (f.type === 'textarea' || f.k === 'text') {
      h += '<textarea id="' + id + '" data-k="' + f.k + '">' + esc(val) + '</textarea>';
    } else h += '<input id="' + id + '" data-k="' + f.k + '" value="' + esc(val) + '">';
    if (f.desc) h += '<div class="d">' + esc(f.desc) + '</div>';
    return h + '</div>';
  }
  $('#nf-insp').addEventListener('input', function (e) {
    var k = e.target.dataset && e.target.dataset.k, n = SEL && node(SEL); if (!k || !n) return;
    n.values[k] = e.target.type === 'number' ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value;
    changed();
    var el = world.querySelector('[data-n="' + n.id + '"] .st span'); if (el && !RUNST) el.textContent = summary(n);
    if (e.target.tagName === 'SELECT') inspect();
  });
  $('#nf-insp').addEventListener('click', function (e) {
    var b = e.target.closest('[data-f]'); if (!b) return;
    if (b.dataset.f === 'upload') { var fi = $('#nf-file'), s = spec(node(SEL)); fi.accept = { video: 'video/*', image: 'image/*', audio: 'audio/*' }[s.accept] || ''; fi.value = ''; fi.click(); }
    if (b.dataset.f === 'lib') libPick();
  });
  $('#nf-file').addEventListener('change', function () {
    var f = this.files[0], n = SEL && node(SEL); if (!f || !n) return;
    var fd = new FormData(); fd.append('file', f); toast('Uploading ' + f.name + '…');
    fetch(B + '/api/upload', { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) return toast(d.error, true);
      setFile(n, 'ref:' + d.name, d.kind, d.label || f.name, d.url);
    }).catch(function () { toast('Upload failed', true); });
  });
  function setFile(n, file, kind, label, url) {
    var want = spec(n).accept;
    if (want && want !== 'any' && kind !== want) return toast('This node takes ' + want + ', that is ' + kind, true);
    n.values.file = file; n.values._kind = kind; n.values._label = label; n.values._url = url;
    if (want === 'any') G.links = G.links.filter(function (l) { if (l.from[0] !== n.id) return true; var ip = portDef(node(l.to[0]), l.to[1], 'in'); return ip && fits(kind, ip[1]); });
    changed(); render(); inspect();
  }
  function libPick() {
    var n = node(SEL), want = spec(n).accept;
    api('/api/library?limit=120' + (want && want !== 'any' ? '&kind=' + want : '')).then(function (d) {
      var it = (d.items || []);
      modal('<h3>' + mi('grid') + ' Pick from your library</h3>' + (it.length ? '<div class="grid">' + it.map(function (x, i) {
        return '<button data-i="' + i + '">' + (x.thumb ? '<img src="' + B + x.thumb + '" loading="lazy">' : '<div style="height:72px;display:flex;align-items:center;justify-content:center">' + mi('music') + '</div>') + '<span>' + esc(x.name) + '</span></button>';
      }).join('') + '</div>' : '<div class="dim">Nothing in your library of that type yet.</div>'), function (e) {
        var b = e.target.closest('[data-i]'); if (!b) return; var x = it[+b.dataset.i]; closeModal(); setFile(n, 'lib:' + x.name, x.kind, x.name, x.url);
      });
    });
  }

  /* ── modals: add node, templates, open ── */
  function modal(html, onclick) { var m = $('#nf-modal'); m.innerHTML = '<div class="box">' + html + '</div>'; m.hidden = false; icons();
    m.onclick = function (e) { if (e.target === m) return closeModal(); if (onclick) onclick(e); }; }
  function closeModal() { $('#nf-modal').hidden = true; }
  function palette(target) {
    var cats = {}; Object.keys(CAT).forEach(function (k) { var c = CAT[k].cat; (cats[c] = cats[c] || []).push(k); });
    return Object.keys(cats).map(function (c) { return '<h4>' + esc(c) + '</h4>' + cats[c].map(function (k) {
      return target === 'modal' ? '<button class="it" data-add="' + k + '">' + mi(CAT[k].icon || 'box') + ' ' + esc(CAT[k].label) + '<small>' + esc(docOf(k).short) + '</small></button>'
        : '<button data-add="' + k + '" title="' + esc(docOf(k).short + '  ' + docLong(k)) + '">' + mi(CAT[k].icon || 'box') + '<span>' + esc(CAT[k].label) + '<small>' + esc(docOf(k).short) + '</small></span></button>'; }).join(''); }).join('');
  }
  $('#nf-pal').addEventListener('click', function (e) { var b = e.target.closest('[data-add]'); if (b) addNode(b.dataset.add); });
  function load(g) { G = clone(g); G.nodes = G.nodes || []; G.links = G.links || []; $('#nf-name').value = G.name || 'Untitled flow'; SEL = null; RUNST = null; render(); inspect(); setTimeout(fit, 30); }
  var ACT = {
    close: function () { try { localStorage.setItem('mml.flow.draft', JSON.stringify(G)); } catch (e) { }
      if (window.parent !== window) return window.parent.postMessage({ mml: 'flow-close' }, '*'); location.href = B + '/'; },
    add: function () { modal('<h3>' + mi('plus') + ' Add a node</h3>' + palette('modal'), function (e) { var b = e.target.closest('[data-add]'); if (b) { closeModal(); addNode(b.dataset.add); } }); },
    templates: function () { modal('<h3>' + mi('layers') + ' Starter flows</h3>' + TPL.map(function (t, i) { return '<button class="it" data-t="' + i + '"><b>' + esc(t.name) + '</b><small>' + esc(t.desc) + '</small></button>'; }).join(''),
      function (e) { var b = e.target.closest('[data-t]'); if (!b) return; closeModal(); load(TPL[+b.dataset.t].graph); changed(); toast('Template loaded — choose the input files, then Run'); }); },
    open: function () { api('/api/flow/graphs').then(function (d) { var L = d.graphs || [];
      modal('<h3>' + mi('folder') + ' Your flows</h3>' + (L.length ? L.map(function (g) { return '<div style="display:flex;gap:6px"><button class="it" data-g="' + esc(g.id) + '"><b>' + esc(g.name) + '</b><small>' + g.nodes + ' nodes · ' + new Date((g.updated || 0) * 1000).toLocaleString() + '</small></button><button class="eb ic" data-gd="' + esc(g.id) + '" title="Delete">' + mi('trash') + '</button></div>'; }).join('') : '<div class="dim">No saved flows yet.</div>'),
        function (e) { var b = e.target.closest('[data-g]'), x = e.target.closest('[data-gd]');
          if (x) { api('/api/flow/graphs/' + x.dataset.gd + '/delete', {}).then(function () { closeModal(); ACT.open(); }); return; }
          if (b) api('/api/flow/graphs/' + b.dataset.g).then(function (g) { closeModal(); if (g.error) return toast(g.error, true); load(g); dirty = false; $('#nf-state').textContent = 'saved'; }); }); }); },
    save: function () { G.name = $('#nf-name').value || 'Untitled flow'; return api('/api/flow/graphs', G).then(function (d) { if (d.error) return toast(d.error, true); G.id = d.id; dirty = false; $('#nf-state').textContent = 'saved'; toast('Flow saved'); }); },
    fit: fit,
    run: function () {
      if (!G.nodes.length) return toast('Add some nodes first', true);
      G.name = $('#nf-name').value || 'Untitled flow';
      api('/api/flow/run', { graph: G, session: SESSION }).then(function (d) { if (d.error) return toast(d.error, true); follow(d.id); toast('Flow running — renders go through the lab queue'); });
    },
    stop: function () { if (RUN) api('/api/flow/runs/' + RUN + '/stop', {}).then(function () { toast('Stopping…'); }); }
  };
  document.querySelector('.nf-top').addEventListener('click', function (e) { var b = e.target.closest('[data-a]'); if (b && ACT[b.dataset.a]) ACT[b.dataset.a](); });
  $('#nf-name').addEventListener('input', function () { G.name = this.value; changed(); });
  document.addEventListener('keydown', function (e) {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if ((e.key === 'Delete' || e.key === 'Backspace') && SEL) delNode(SEL);
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); ACT.save(); }
  });

  /* ── run status ── */
  function follow(id) {
    RUN = id; $('#nf-run').hidden = true; $('#nf-stop').hidden = false; clearTimeout(pollT);
    (function tick() {
      api('/api/flow/runs/' + id).then(function (d) {
        if (d.error) { RUN = null; $('#nf-run').hidden = false; $('#nf-stop').hidden = true; return; }
        RUNST = d; render(); $('#nf-state').textContent = 'run ' + d.status;
        if (d.status === 'running') { pollT = setTimeout(tick, 2000); return; }
        RUN = null; $('#nf-run').hidden = false; $('#nf-stop').hidden = true;
        if (d.status === 'done') toast('Flow finished — results are in your library'); else if (d.status === 'error') toast(d.error, true); else toast('Flow ' + d.status);
      }).catch(function () { pollT = setTimeout(tick, 4000); });
    })();
  }

  /* ── boot ── */
  api('/api/flow/catalog').then(function (d) {
    if (d.error) { toast(d.error, true); return; }
    CAT = d.nodes || {}; TPL = d.templates || [];
    Object.keys(CAT).forEach(function (k) { (CAT[k].fields || []).forEach(function (f) { if (f.odesc && !f.opt_desc) f.opt_desc = f.odesc; }); });
    $('#nf-pal').innerHTML = palette('side'); icons();
    var dr = null; try { dr = JSON.parse(localStorage.getItem('mml.flow.draft') || 'null'); } catch (e) { }
    if (dr && dr.nodes && dr.nodes.length) load(dr); else if (TPL[0]) load(TPL[0].graph); else render();
    applyView();
    api('/api/flow/runs').then(function (r) { var x = (r.runs || [])[0]; if (x && x.status === 'running') follow(x.id); });
  });
  window.addEventListener('resize', function () { wires(); });
})();
