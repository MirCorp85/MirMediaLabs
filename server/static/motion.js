/* MIR MEDIA LABS · MOTION STUDIO — Remotion motion-graphics editor (remotion.py + TOOLS\MirRemotion).
   Live preview = @remotion/player (motion/player.js → window.MirMotion); export = the Node render daemon.
   Project: {id,name,w,h,fps,font,palette,session,markers[],tracks:[{kind,name,mute,hide,clips:[{id,type,start,dur,props,trans,out,kf}]}]} */
(function () {
  'use strict';
  var B = location.pathname.indexOf('/mlab') === 0 ? '/mlab' : '';
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var mi = function (n, c) { return '<i class="mi' + (c ? ' ' + c : '') + '" data-ic="' + n + '"></i>'; };
  var icons = function () { try { if (window.MI && MI.scan) MI.scan(); } catch (e) { } };
  var uid = function () { return Math.random().toString(36).slice(2, 10); };
  var clone = function (o) { return JSON.parse(JSON.stringify(o)); };
  var Q = new URLSearchParams(location.search);
  function api(path, body, method) {
    var o = { method: method || (body ? 'POST' : 'GET'), headers: {}, cache: 'no-store', credentials: 'same-origin' };
    if (body) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return { error: 'HTTP ' + r.status }; }); });
  }
  var toastT;
  function toast(t, err) { var e = $('#mo-toast'); e.textContent = t; e.className = 'mo-toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'mo-toast'; }, err ? 5200 : 2600); }

  /* ── theme (same palette table as the editor) ── */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    r.setProperty('--bg', t[0]); r.setProperty('--panel', t[1]); r.setProperty('--panel2', t[2]); r.setProperty('--ink', t[3]); r.setProperty('--acc', t[4]); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/miros-prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });

  var MM = window.MirMotion;
  if (!MM) { document.body.innerHTML = '<div class="pad">The motion engine bundle (motion/player.js) did not load. Run <code>node build_player.mjs</code> in TOOLS\\MirRemotion.</div>'; return; }
  var SC = MM.schema, TA = MM.textAnims, TR = MM.transitions;
  var FONTS = ['', 'bastion', 'hollow', 'horizon', 'matrix', 'orbit', 'pixel', 'quill', 'stencil', 'vector', 'velocity'];
  var PALS = [['#0b0b10', '#f4f1ea', '#ffcc33', '#ff5a8a'], ['#0b1220', '#e6ecf5', '#3fb8c9', '#7c8cff'], ['#101010', '#ffffff', '#ff3b3b', '#ffb000'],
    ['#fff8ec', '#1e1d1a', '#ff7a59', '#2bb3a3'], ['#120a24', '#f2e9ff', '#c77dff', '#5ee7ff'], ['#0d1f12', '#effff2', '#7dff8a', '#f6ff6b'], ['#1a1410', '#f7efe6', '#d97757', '#e3a949']];
  var KINDS = { scene: 'Scenes', overlay: 'Overlays', captions: 'Captions', audio: 'Audio' };
  var SESSION = Q.get('session') != null ? Q.get('session') : (function () { try { return localStorage.getItem('mml.session') || ''; } catch (e) { return ''; } })();

  /* ── state ── */
  var P, SEL = null, UNDO = [], REDO = [], last = '', PX = 60, SNAP = true, LOOP = false, dirty = false, saveT = null, playing = false;
  function blank() { return { id: '', name: 'Untitled motion', w: 1280, h: 720, fps: 30, font: 'orbit', palette: { bg: '#0b0b10', fg: '#f4f1ea', acc: '#ffcc33', acc2: '#ff5a8a' }, session: SESSION, markers: [],
    tracks: [{ kind: 'scene', name: 'Scenes', clips: [] }, { kind: 'overlay', name: 'Overlays', clips: [] }, { kind: 'captions', name: 'Captions', clips: [] }, { kind: 'audio', name: 'Music', clips: [] }] }; }
  function dur() { return Math.max(1, MM.duration(P)); }
  function fps() { return P.fps || 30; }
  function view() { var v = clone(P); v.mediaBase = B + '/media/'; v.refBase = B + '/refs/'; v.fontBase = B + '/motion/fonts/'; return v; }
  function findClip(id) { for (var i = 0; i < P.tracks.length; i++) { var t = P.tracks[i]; for (var j = 0; j < t.clips.length; j++) if (t.clips[j].id === id) return { t: t, ti: i, c: t.clips[j], ci: j }; } return null; }
  function defaults(type) { var s = SC[type], o = {}; (s.fields || []).forEach(function (f) { if (f.d !== undefined && f.d !== '') o[f.k] = clone(f.d); }); return o; }

  /* ── undo + autosave ── */
  function commit(noRefresh) {
    var s = JSON.stringify(P); if (s === last) return; UNDO.push(last); if (UNDO.length > 200) UNDO.shift(); REDO = []; last = s; dirty = true;
    $('#mo-save').textContent = 'editing…'; clearTimeout(saveT); saveT = setTimeout(save, 1200); if (!noRefresh) refresh();
  }
  function undo() { if (!UNDO.length) return; REDO.push(last); last = UNDO.pop(); P = JSON.parse(last); dirty = true; clearTimeout(saveT); saveT = setTimeout(save, 1200); refresh(true); }
  function redo() { if (!REDO.length) return; UNDO.push(last); last = REDO.pop(); P = JSON.parse(last); dirty = true; clearTimeout(saveT); saveT = setTimeout(save, 1200); refresh(true); }
  function save() {
    if (!dirty) return Promise.resolve(); dirty = false; $('#mo-save').textContent = 'saving…';
    return api('/api/motion/project', P).then(function (d) {
      if (d.error) { $('#mo-save').textContent = 'not saved'; toast(d.error, 1); return; }
      if (!P.id) { P.id = d.id; last = JSON.stringify(P); try { history.replaceState(null, '', location.pathname + '?p=' + d.id); } catch (e) { } }
      $('#mo-save').textContent = 'saved';
    }).catch(function () { $('#mo-save').textContent = 'offline'; dirty = true; });
  }
  window.addEventListener('beforeunload', function () { if (dirty) navigator.sendBeacon && navigator.sendBeacon(B + '/api/motion/project', new Blob([JSON.stringify(P)], { type: 'application/json' })); });

  /* ── player ── */
  function fitStage() {
    var w = $('#mo-stagewrap'), s = $('#mo-stage'), aw = w.clientWidth - 20, ah = w.clientHeight - 20, r = P.w / P.h, W = aw, H = aw / r;
    if (H > ah) { H = ah; W = ah * r; } s.style.width = Math.max(40, W) + 'px'; s.style.height = Math.max(40, H) + 'px';
  }
  window.addEventListener('resize', fitStage);
  var curF = 0;
  function mountPlayer() { MM.mount($('#mo-player'), view(), { onFrame: function (f) { curF = f; tick(); } }); }
  function refresh(full) {
    MM.update(view()); drawTL(); if (full !== false) drawInsp(); tick(); $('#mo-name').value = P.name;
  }
  function T() { return curF / fps(); }
  function seek(t) { t = Math.max(0, Math.min(dur(), t)); curF = Math.round(t * fps()); MM.seek(curF); tick(); }
  function fmt(t) { var m = Math.floor(t / 60), s = t - m * 60; return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s.toFixed(2); }
  function tick() {
    $('#mo-tc').textContent = fmt(T()) + ' / ' + fmt(dur());
    $('#mo-ph').style.left = (T() * PX) + 'px';
    var p = MM.playing(); if (p !== playing) { playing = p; $('#mo-play').innerHTML = mi(p ? 'pause' : 'play'); icons(); }
    if (p && LOOP && SEL) { var h = findClip(SEL); if (h && T() >= h.c.start + h.c.dur - 0.04) seek(h.c.start); }
    if (p) { var sc = $('#mo-scroll'), x = T() * PX; if (x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = x - 60; }
  }
  function play() { if (MM.playing()) MM.pause(); else { if (T() >= dur() - 0.05) seek(0); MM.play(); } setTimeout(tick, 30); }

  /* ── timeline ── */
  function trackFor(kind) { var t = P.tracks.filter(function (x) { return x.kind === kind; })[0]; if (!t) { t = { kind: kind, name: KINDS[kind] || kind, clips: [] }; P.tracks.push(t); } return t; }
  function endOf(t) { return t.clips.reduce(function (m, c) { return Math.max(m, c.start + c.dur); }, 0); }
  function addScene(type, at, props, toTrack) {
    var s = SC[type]; if (!s) return null;
    var t = toTrack || trackFor(s.track), start = at != null ? at : (s.track === 'scene' ? endOf(t) : T());
    var c = { id: uid(), type: type, start: +start.toFixed(3), dur: s.dur, props: Object.assign(defaults(type), props || {}) };
    if (s.track === 'scene' && t.clips.length && start > 0) c.trans = { type: 'fade', dur: 0.5 };
    t.clips.push(c); SEL = c.id; commit(); return c;
  }
  function snapT(t, skip) {
    if (!SNAP) return t; var best = t, bd = 8 / PX, pts = [0, T()].concat(P.markers || []);
    P.tracks.forEach(function (tr) { tr.clips.forEach(function (c) { if (c.id !== skip) pts.push(c.start, c.start + c.dur); }); });
    pts.forEach(function (p) { if (Math.abs(p - t) < bd) { bd = Math.abs(p - t); best = p; } }); return best;
  }
  function drawTL() {
    var D = dur() + 10, W = Math.max($('#mo-scroll').clientWidth, D * PX);
    var heads = '', rows = '';
    P.tracks.forEach(function (t, i) {
      heads += '<div class="th" data-i="' + i + '"><span class="k" style="background:var(--' + t.kind + ')"></span><span class="nm" title="' + esc(t.name) + '">' + esc(t.name || KINDS[t.kind]) + '</span>' +
        (t.kind === 'audio' ? '<button data-h="mute" class="' + (t.mute ? 'on' : '') + '" title="Mute">' + mi('mute', 'sm') + '</button>' : '<button data-h="hide" class="' + (t.hide ? 'on' : '') + '" title="Hide">' + mi('eye-off', 'sm') + '</button>') +
        '<button data-h="up" title="Move up (draws above)">' + mi('chevron-down', 'sm') + '</button><button data-h="del" title="Delete track">' + mi('trash', 'sm') + '</button></div>';
      rows += '<div class="tr" data-i="' + i + '" style="width:' + W + 'px">' + t.clips.map(function (c) {
        var s = SC[c.type] || { label: c.type, icon: 'box' }, lab = (c.props && (c.props.text || c.props.title || c.props.name)) || s.label;
        var kfs = ''; Object.keys(c.kf || {}).forEach(function (k) { (c.kf[k] || []).forEach(function (p) { kfs += '<i class="kfd" style="left:' + (p[0] * PX) + 'px"></i>'; }); });
        var tri = c.trans && c.trans.type !== 'cut' ? '<i class="tri" style="width:' + (c.trans.dur * PX) + 'px"></i>' : '';
        return '<div class="cl ' + t.kind + (c.id === SEL ? ' sel' : '') + '" data-id="' + c.id + '" style="left:' + (c.start * PX) + 'px;width:' + Math.max(6, c.dur * PX) + 'px" title="' + esc(s.label + ' · ' + c.dur.toFixed(2) + 's') + '">' +
          tri + mi(s.icon, 'sm') + '<span>' + esc(String(lab).slice(0, 60)) + '</span>' + kfs + '<i class="h l"></i><i class="h r"></i></div>';
      }).join('') + '</div>';
    });
    heads += '<div class="th-add"><select class="mo-sel" id="addtrk" style="width:100%;height:26px"><option value="">+ track</option>' + Object.keys(KINDS).map(function (k) { return '<option value="' + k + '">' + KINDS[k] + '</option>'; }).join('') + '</select></div>';
    $('#mo-heads').innerHTML = heads; $('#mo-tracks').innerHTML = rows;
    var step = PX > 120 ? 0.5 : PX > 40 ? 1 : PX > 15 ? 5 : PX > 6 ? 10 : 30, r = '';
    for (var s = 0; s <= D; s += step) r += '<span style="left:' + (s * PX) + 'px">' + (step < 1 ? s.toFixed(1) : fmt(s).replace(/\.00$/, '')) + '</span>';
    (P.markers || []).forEach(function (m, i) { r += '<button class="mk" data-m="' + i + '" style="left:' + (m * PX) + 'px" title="Marker ' + fmt(m) + ' — click to jump, right-click to delete"></button>'; });
    $('#mo-ruler').innerHTML = r; $('#mo-ruler').style.width = W + 'px';
    $('#mo-scroll').onscroll = function () { $('#mo-heads').scrollTop = $('#mo-scroll').scrollTop; };
    icons(); bindTL();
  }
  function bindTL() {
    $$('#mo-heads .th button').forEach(function (b) { b.onclick = function () {
      var i = +b.closest('.th').dataset.i, t = P.tracks[i], h = b.dataset.h;
      if (h === 'mute') t.mute = !t.mute; else if (h === 'hide') t.hide = !t.hide;
      else if (h === 'up' && i < P.tracks.length - 1) { P.tracks.splice(i, 1); P.tracks.splice(i + 1, 0, t); }
      else if (h === 'del') { if (t.clips.length && !confirm('Delete this track and its ' + t.clips.length + ' clip(s)?')) return; P.tracks.splice(i, 1); }
      commit(); }; });
    var at = $('#addtrk'); if (at) at.onchange = function () { if (this.value) { P.tracks.push({ kind: this.value, name: KINDS[this.value], clips: [] }); commit(); } };
    $$('#mo-ruler .mk').forEach(function (m) { m.onclick = function (e) { e.stopPropagation(); seek(P.markers[+m.dataset.m]); };
      m.oncontextmenu = function (e) { e.preventDefault(); e.stopPropagation(); P.markers.splice(+m.dataset.m, 1); commit(); }; });
    $$('#mo-tracks .cl').forEach(function (el) { el.onpointerdown = function (e) { clipDrag(e, el); }; el.ondblclick = function () { var h = findClip(el.dataset.id); if (h) seek(h.c.start); }; });
    $$('#mo-tracks .tr').forEach(function (row) {
      row.ondragover = function (e) { e.preventDefault(); row.classList.add('drop'); };
      row.ondragleave = function () { row.classList.remove('drop'); };
      row.ondrop = function (e) { e.preventDefault(); row.classList.remove('drop');
        var x = e.clientX - row.getBoundingClientRect().left, t = snapT(Math.max(0, x / PX)), tr = P.tracks[+row.dataset.i];
        var ty = e.dataTransfer.getData('text/mo-scene'), src = e.dataTransfer.getData('text/mml-src'), kind = e.dataTransfer.getData('text/mml-kind');
        if (ty) { var s = SC[ty]; addScene(ty, t, null, s.track === tr.kind || (s.track === 'overlay' && tr.kind !== 'audio') ? tr : null); }
        else if (src) addMedia(src, kind, t, tr); };
      row.onpointerdown = function (e) { if (e.target === row) { SEL = null; seek(snapT((e.clientX - row.getBoundingClientRect().left) / PX)); drawTL(); drawInsp(); } };
    });
  }
  function clipDrag(e, el) {
    e.preventDefault(); e.stopPropagation(); var h = findClip(el.dataset.id); if (!h) return;
    if (SEL !== h.c.id) { SEL = h.c.id; drawTL(); drawInsp(); el = $('.cl[data-id="' + h.c.id + '"]'); }
    var mode = e.target.classList.contains('l') ? 'l' : e.target.classList.contains('r') ? 'r' : 'm', x0 = e.clientX, y0 = e.clientY, s0 = h.c.start, d0 = h.c.dur, moved = false;
    var trk = $('#mo-tracks'), rh = (trk.firstChild || {}).offsetHeight || 46;
    el.setPointerCapture(e.pointerId);
    el.onpointermove = function (ev) {
      var dt = (ev.clientX - x0) / PX; if (Math.abs(ev.clientX - x0) + Math.abs(ev.clientY - y0) > 3) moved = true; if (!moved) return;
      if (mode === 'm') { var ns = snapT(Math.max(0, s0 + dt), h.c.id), ne = snapT(ns + d0, h.c.id); if (ne !== ns + d0) ns = ne - d0; h.c.start = +Math.max(0, ns).toFixed(3); }
      else if (mode === 'r') h.c.dur = +Math.max(0.1, snapT(s0 + d0 + dt, h.c.id) - s0).toFixed(3);
      else { var nl = Math.min(s0 + d0 - 0.1, Math.max(0, snapT(s0 + dt, h.c.id))); h.c.start = +nl.toFixed(3); h.c.dur = +(s0 + d0 - nl).toFixed(3); }
      el.style.left = h.c.start * PX + 'px'; el.style.width = Math.max(6, h.c.dur * PX) + 'px';
      if (mode === 'm') { var ti = Math.max(0, Math.min(P.tracks.length - 1, h.ti + Math.round((ev.clientY - y0) / rh))); el.style.transform = 'translateY(' + ((ti - h.ti) * rh) + 'px)'; el._ti = ti; }
    };
    el.onpointerup = function () {
      el.onpointermove = el.onpointerup = null;
      if (!moved) { seek(Math.max(T(), 0)); return; }
      if (el._ti != null && el._ti !== h.ti) { var nt = P.tracks[el._ti]; if ((nt.kind === 'audio') === (h.t.kind === 'audio')) { h.t.clips.splice(h.ci, 1); nt.clips.push(h.c); } }
      commit();
    };
  }
  $('#mo-ruler').onpointerdown = function (e) {
    var r = $('#mo-ruler'), go = function (ev) { seek(snapT((ev.clientX - r.getBoundingClientRect().left) / PX)); };
    go(e); r.setPointerCapture(e.pointerId); r.onpointermove = go; r.onpointerup = function () { r.onpointermove = r.onpointerup = null; };
  };
  $('#mo-zoom').oninput = function () { PX = +this.value; drawTL(); tick(); };

  /* ── library media → clips ── */
  function kindOf(src, k) { if (k) return k; return /\.(mp3|wav|m4a|flac|ogg)$/i.test(src) ? 'audio' : /\.(png|jpe?g|webp|gif)$/i.test(src) ? 'image' : 'video'; }
  function addMedia(src, kind, at, tr) {
    kind = kindOf(src, kind);
    if (kind === 'audio') { var t = tr && tr.kind === 'audio' ? tr : trackFor('audio'); return addScene('audio', at != null ? at : 0, { src: src }, t); }
    var tt = tr && tr.kind !== 'audio' ? tr : trackFor('scene');
    var c = addScene('media', at != null ? at : endOf(tt), { src: src, kind: kind === 'image' ? 'image' : 'video', kenburns: kind === 'image' ? 'zoom-in' : 'none' }, tt);
    if (kind === 'video' && c) api('/api/editor/probe?src=' + encodeURIComponent(src)).then(function (d) { if (d && d.dur) { c.dur = +(+d.dur).toFixed(2); commit(); } });
    return c;
  }
  var LIBK = '', LIBOFF = 0;
  function loadLib(more) {
    var g = $('#mo-lib'); if (!more) { LIBOFF = 0; g.innerHTML = '<div class="dim">loading…</div>'; }
    api('/api/library?limit=40&offset=' + LIBOFF + '&kind=' + LIBK).then(function (d) {
      if (!more) g.innerHTML = ''; var mb = $('.more', g); if (mb) mb.remove();
      (d.items || []).forEach(function (it) { g.appendChild(libCard(it)); });
      LIBOFF += (d.items || []).length; icons();
      if (!g.children.length) g.innerHTML = '<div class="dim">Your library is empty.</div>';
      if (LIBOFF < (d.total || 0)) { var b = document.createElement('button'); b.className = 'eb more'; b.textContent = 'More'; b.onclick = function () { loadLib(true); }; g.appendChild(b); }
    }).catch(function () { g.innerHTML = '<div class="dim">couldn\'t load the library</div>'; });
  }
  function libCard(it, onPick) {
    var d = document.createElement('div'), src = 'lib:' + it.name; d.className = 'mi-card'; d.draggable = !onPick; d.title = it.prompt || it.name;
    var th = it.kind !== 'audio' ? B + '/thumb/' + encodeURIComponent(it.name) : null;
    d.innerHTML = (th ? '<img src="' + th + '" loading="lazy" alt="" onerror="this.remove()">' : '<div class="au">' + mi('music', 'lg') + '<span>' + esc(String(it.prompt || it.name).slice(0, 50)) + '</span></div>') +
      '<div class="nm">' + esc(String(it.prompt || it.name).slice(0, 80)) + '</div>' + (onPick ? '' : '<button class="add" title="Add">' + mi('plus', 'sm') + '</button>');
    if (onPick) d.onclick = function () { onPick(src, it, d); };
    else {
      d.addEventListener('dragstart', function (e) { e.dataTransfer.setData('text/mml-src', src); e.dataTransfer.setData('text/mml-kind', it.kind); e.dataTransfer.effectAllowed = 'copy'; });
      $('.add', d).onclick = function (e) { e.stopPropagation(); addMedia(src, it.kind); toast('Added ' + (it.kind === 'audio' ? 'to the audio track' : 'to the scenes')); };
    }
    return d;
  }
  $$('.mo-bin .chips button').forEach(function (b) { b.onclick = function () { $$('.mo-bin .chips button').forEach(function (x) { x.classList.toggle('on', x === b); }); LIBK = b.dataset.k; loadLib(); }; });
  /* picker modal: choose library file(s) */
  function pickMedia(kinds, multi, title) {
    return new Promise(function (resolve) {
      var picked = [], m = $('#mo-modal');
      m.innerHTML = '<div class="box"><h2>' + esc(title || 'Pick from your library') + '</h2><div class="pick-grid" id="pk"></div><div class="acts"><button class="eb" data-x="0">Cancel</button>' + (multi ? '<button class="eb pri" data-x="1">Use selected</button>' : '') + '</div></div>';
      m.hidden = false;
      var g = $('#pk'), ks = (kinds || '').split(',').filter(Boolean);
      var load = function (k) { return api('/api/library?limit=120&offset=0&kind=' + k).then(function (d) { return d.items || []; }); };
      Promise.all(ks.length ? ks.map(load) : [load('')]).then(function (ls) {
        var all = [].concat.apply([], ls); all.sort(function (a, b) { return (b.mtime || 0) - (a.mtime || 0); });
        if (!all.length) g.innerHTML = '<div class="dim">Nothing suitable in your library yet.</div>';
        all.forEach(function (it) { g.appendChild(libCard(it, function (src, item, el) {
          if (!multi) { m.hidden = true; resolve([src]); return; }
          var i = picked.indexOf(src); if (i < 0) { picked.push(src); el.classList.add('pick'); } else { picked.splice(i, 1); el.classList.remove('pick'); }
        })); }); icons();
      });
      $$('[data-x]', m).forEach(function (b) { b.onclick = function () { m.hidden = true; resolve(b.dataset.x === '1' ? picked : []); }; });
    });
  }

  /* ── scene list ── */
  function drawScenes() {
    var q = ($('#sc-q').value || '').toLowerCase(), groups = {};
    Object.keys(SC).forEach(function (k) { var s = SC[k]; if (q && (s.label + ' ' + k + ' ' + s.group).toLowerCase().indexOf(q) < 0) return; (groups[s.group] = groups[s.group] || []).push(k); });
    $('#sc-list').innerHTML = Object.keys(groups).map(function (g) {
      return '<div class="grp">' + esc(g) + '</div>' + groups[g].map(function (k) { var s = SC[k];
        return '<div class="scn" draggable="true" data-k="' + k + '">' + mi(s.icon) + '<div>' + esc(s.label) + '<small>' + s.track + ' · ' + s.dur + 's</small></div><button class="add" title="Add">' + mi('plus', 'sm') + '</button></div>'; }).join('');
    }).join('');
    $$('#sc-list .scn').forEach(function (el) {
      el.addEventListener('dragstart', function (e) { e.dataTransfer.setData('text/mo-scene', el.dataset.k); e.dataTransfer.effectAllowed = 'copy'; });
      el.onclick = function () { var k = el.dataset.k, s = SC[k]; var c = addScene(k, s.track === 'scene' ? null : T()); if (c) { seek(c.start + 0.01); toast(s.label + ' added'); } closeDrawers(); };
    });
    icons();
  }
  $('#sc-q').oninput = drawScenes;

  /* ── inspector ── */
  function field(f, v) {
    var id = 'f_' + f.k, val = v == null ? '' : v;
    switch (f.t) {
      case 'long': return '<textarea id="' + id + '" rows="4">' + esc(val) + '</textarea>';
      case 'num': return '<input id="' + id + '" type="number"' + (f.min != null ? ' min="' + f.min + '"' : '') + (f.max != null ? ' max="' + f.max + '"' : '') + ' step="' + (f.step || 'any') + '" value="' + esc(val) + '">';
      case 'color': return '<div class="clr"><input type="color" id="' + id + '_c" value="' + (/^#[0-9a-f]{6}$/i.test(val) ? val : '#000000') + '"><input type="text" id="' + id + '" value="' + esc(val) + '" placeholder="project palette"></div>';
      case 'select': return '<select id="' + id + '">' + (f.opts || []).map(function (o) { return '<option' + (String(o) === String(val) ? ' selected' : '') + ' value="' + esc(o) + '">' + esc(o || '—') + '</option>'; }).join('') + '</select>';
      case 'bool': return '<input id="' + id + '" type="checkbox"' + (val ? ' checked' : '') + '>';
      case 'media': return '<div class="clr"><input type="text" id="' + id + '" value="' + esc(val) + '" readonly placeholder="none"><button class="eb sm" data-pick="' + f.k + '" data-acc="' + (f.accept || '') + '">Pick</button></div>';
      case 'medias': return '<div class="medias" id="' + id + '">' + (val || []).map(function (s, i) { return '<span>' + esc(String(s).replace(/^lib:/, '').slice(0, 22)) + '<button data-rm="' + f.k + '" data-i="' + i + '">' + mi('close', 'sm') + '</button></span>'; }).join('') +
        '</div><button class="eb sm" data-picks="' + f.k + '" data-acc="' + (f.accept || '') + '" style="margin-top:4px">' + mi('plus', 'sm') + ' Add</button>';
      case 'list': return '<textarea id="' + id + '" rows="5" placeholder="Role | Name — one per line">' + esc((val || []).map(function (l) { return (l.role || '') + ' | ' + (l.name || ''); }).join('\n')) + '</textarea>';
      case 'json': return '<textarea id="' + id + '" rows="3" spellcheck="false" style="font-family:var(--mono);font-size:11px">' + esc(JSON.stringify(val || [])) + '</textarea>';
      default: return '<input id="' + id + '" type="text" value="' + esc(val) + '">';
    }
  }
  function readField(f) {
    var el = $('#f_' + f.k); if (!el) return undefined;
    switch (f.t) {
      case 'num': return el.value === '' ? undefined : +el.value;
      case 'bool': return el.checked;
      case 'list': return el.value.split('\n').map(function (l) { var p = l.split('|'); return { role: (p[0] || '').trim(), name: (p.slice(1).join('|') || '').trim() }; }).filter(function (x) { return x.role || x.name; });
      case 'json': try { return JSON.parse(el.value || '[]'); } catch (e) { toast('Not valid JSON — kept the old value', 1); return undefined; }
      case 'medias': return undefined;
      default: return el.value;
    }
  }
  var KFP = [['x', 'X %', 0], ['y', 'Y %', 0], ['scale', 'Scale', 1], ['rotate', 'Rotate °', 0], ['opacity', 'Opacity', 1], ['blur', 'Blur px', 0]];
  function drawInsp() {
    var box = $('#mo-insp'), h = SEL && findClip(SEL);
    if (!h) { box.innerHTML = projInsp(); bindProjInsp(); icons(); return; }
    var c = h.c, s = SC[c.type] || { label: c.type, fields: [], icon: 'box' }, tr = c.trans || { type: 'cut', dur: 0.5 }, ot = c.out || { type: 'cut', dur: 0.5 };
    var lt = T() - c.start, inside = lt >= 0 && lt <= c.dur;
    var html = '<div class="ins"><h3>' + mi(s.icon) + esc(s.label) + '</h3><div class="dim" style="font-size:11px">' + esc(h.t.name || h.t.kind) + ' track</div>' +
      '<h4>Timing</h4><div class="fld two"><div><label>Start (s)</label><input id="c_start" type="number" step="0.05" min="0" value="' + c.start + '"></div><div><label>Length (s)</label><input id="c_dur" type="number" step="0.05" min="0.1" value="' + c.dur + '"></div></div>' +
      '<div class="fld two"><div><label>Transition in</label><select id="c_tin">' + TR.map(function (o) { return '<option' + (o === tr.type ? ' selected' : '') + '>' + o + '</option>'; }).join('') + '</select></div><div><label>In length</label><input id="c_tind" type="number" step="0.1" min="0" max="5" value="' + tr.dur + '"></div></div>' +
      '<div class="fld two"><div><label>Transition out</label><select id="c_tout">' + TR.map(function (o) { return '<option' + (o === ot.type ? ' selected' : '') + '>' + o + '</option>'; }).join('') + '</select></div><div><label>Out length</label><input id="c_toutd" type="number" step="0.1" min="0" max="5" value="' + ot.dur + '"></div></div>' +
      '<h4>Content</h4>' + (s.fields || []).map(function (f) { return '<div class="fld"><label>' + esc(f.label) + '</label>' + field(f, (c.props || {})[f.k]) + '</div>'; }).join('');
    if (c.type === 'captions' || c.type === 'lyrics') html += '<button class="eb wide" data-a="autowords">' + mi('mic') + ' Time words from audio (Whisper)</button>';
    if (c.type === 'media' || c.type === 'split') html += '<button class="eb wide" data-a="fitmedia">' + mi('expand') + ' Length = video length</button>';
    html += '<h4>Keyframes</h4><div class="dim" style="font-size:11px;margin-bottom:6px">' + (inside ? 'Set a value at the playhead (' + lt.toFixed(2) + 's into the clip).' : 'Move the playhead inside the clip to add keys.') + '</div>' +
      KFP.map(function (k) { var pts = (c.kf || {})[k[0]] || [];
        return '<div class="kfrow"><b>' + k[1] + '</b><input type="number" step="any" style="width:64px" id="kf_' + k[0] + '" value="' + kfVal(c, k[0], lt, k[2]) + '"' + (inside ? '' : ' disabled') + '><button class="eb sm" data-kf="' + k[0] + '"' + (inside ? '' : ' disabled') + '>' + mi('plus', 'sm') + '</button>' +
          pts.map(function (p, i) { return '<span class="pt" data-kfj="' + k[0] + '" data-i="' + i + '" title="Jump · right-click deletes">' + p[0].toFixed(1) + 's=' + (+p[1]).toFixed(2) + '</span>'; }).join('') + '</div>'; }).join('') +
      '<h4>MUSE</h4><textarea id="c_ai" rows="2" placeholder="e.g. make it punchier, bigger text, neon colours"></textarea><button class="eb wide" data-a="airewrite">' + mi('sparkle') + ' Rewrite this clip</button>' +
      '<div style="display:flex;gap:6px;margin-top:14px"><button class="eb" data-a="dup">' + mi('copy') + ' Duplicate</button><button class="eb" data-a="del">' + mi('trash') + ' Delete</button></div></div>';
    box.innerHTML = html; icons();
    var num = function (id, fn) { var e = $('#' + id); if (e) e.onchange = function () { fn(+e.value); commit(); }; };
    num('c_start', function (v) { c.start = Math.max(0, v); }); num('c_dur', function (v) { c.dur = Math.max(0.1, v); });
    $('#c_tin').onchange = $('#c_tind').onchange = function () { var t = $('#c_tin').value; if (t === 'cut') delete c.trans; else c.trans = { type: t, dur: +$('#c_tind').value || 0.5 }; commit(); };
    $('#c_tout').onchange = $('#c_toutd').onchange = function () { var t = $('#c_tout').value; if (t === 'cut') delete c.out; else c.out = { type: t, dur: +$('#c_toutd').value || 0.5 }; commit(); };
    (s.fields || []).forEach(function (f) {
      var el = $('#f_' + f.k); if (!el || f.t === 'medias') return;
      var upd = function () { var v = readField(f); if (v === undefined || v === '') delete c.props[f.k]; else c.props[f.k] = v; commit(true); MM.update(view()); drawTL(); };
      el.oninput = f.t === 'text' || f.t === 'long' || f.t === 'num' ? debounce(upd, 250) : null; el.onchange = upd;
      var cp = $('#f_' + f.k + '_c'); if (cp) cp.oninput = function () { el.value = cp.value; upd(); };
    });
    $$('[data-pick]', box).forEach(function (b) { b.onclick = function () { pickMedia(b.dataset.acc, false, 'Pick ' + b.dataset.pick).then(function (l) { if (l[0]) { c.props[b.dataset.pick] = l[0]; commit(); } }); }; });
    $$('[data-picks]', box).forEach(function (b) { b.onclick = function () { pickMedia(b.dataset.acc, true, 'Pick images').then(function (l) { if (l.length) { c.props[b.dataset.picks] = (c.props[b.dataset.picks] || []).concat(l); commit(); } }); }; });
    $$('[data-rm]', box).forEach(function (b) { b.onclick = function () { c.props[b.dataset.rm].splice(+b.dataset.i, 1); commit(); }; });
    $$('[data-kf]', box).forEach(function (b) { b.onclick = function () { var k = b.dataset.kf, v = +$('#kf_' + k).value, t = +(T() - c.start).toFixed(3); c.kf = c.kf || {}; var a = (c.kf[k] = (c.kf[k] || []).filter(function (p) { return Math.abs(p[0] - t) > 0.02; })); a.push([t, v]); a.sort(function (x, y) { return x[0] - y[0]; }); commit(); }; });
    $$('[data-kfj]', box).forEach(function (sp) { var k = sp.dataset.kfj, i = +sp.dataset.i;
      sp.onclick = function () { seek(c.start + c.kf[k][i][0]); drawInsp(); };
      sp.oncontextmenu = function (e) { e.preventDefault(); c.kf[k].splice(i, 1); if (!c.kf[k].length) delete c.kf[k]; if (!Object.keys(c.kf).length) delete c.kf; commit(); }; });
    var aw = $('[data-a=autowords]', box); if (aw) aw.onclick = function () { autoWords(c); };
    var fm = $('[data-a=fitmedia]', box); if (fm) fm.onclick = function () { if (!c.props.src) return; api('/api/editor/probe?src=' + encodeURIComponent(c.props.src)).then(function (d) { if (d && d.dur) { c.dur = +(+d.dur - (c.props.trimIn || 0)).toFixed(2); commit(); } else toast('Not a video', 1); }); };
    $('[data-a=airewrite]', box).onclick = function () { var a = $('#c_ai').value.trim(); if (a) aiRun('props', a, c); };
    $('[data-a=dup]', box).onclick = dupSel; $('[data-a=del]', box).onclick = function () { delSel(false); };
  }
  function kfVal(c, k, t, d) { var a = (c.kf || {})[k]; if (!a || !a.length) return d; if (t <= a[0][0]) return a[0][1]; for (var i = 1; i < a.length; i++) if (t <= a[i][0]) { var p = (t - a[i - 1][0]) / (a[i][0] - a[i - 1][0]); return +(a[i - 1][1] + (a[i][1] - a[i - 1][1]) * p).toFixed(3); } return a[a.length - 1][1]; }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
  function projInsp() {
    var pal = P.palette || {};
    return '<div class="ins"><h3>' + mi('sliders') + 'Project</h3><div class="dim" style="font-size:11px">' + P.w + '×' + P.h + ' · ' + P.fps + ' fps · ' + fmt(dur()) + '</div>' +
      '<h4>Font</h4><div class="fld"><select id="p_font">' + FONTS.map(function (f) { return '<option value="' + f + '"' + (f === (P.font || '') ? ' selected' : '') + '>' + (f ? 'MIR ' + f : 'System') + '</option>'; }).join('') + '</select></div>' +
      '<h4>Palette</h4><div class="sw">' + PALS.map(function (p, i) { return '<button data-pal="' + i + '" title="' + p.join(' ') + '" style="background:linear-gradient(135deg,' + p[0] + ' 50%,' + p[2] + ' 50%)"></button>'; }).join('') + '</div>' +
      ['bg', 'fg', 'acc', 'acc2'].map(function (k) { return '<div class="fld"><label>' + { bg: 'Background', fg: 'Text', acc: 'Accent', acc2: 'Accent 2' }[k] + '</label><input type="color" id="p_' + k + '" value="' + (pal[k] || '#000000') + '"></div>'; }).join('') +
      '<h4>Tips</h4><div class="dim" style="font-size:12px">Drag scenes or library files onto a track. Space plays, S splits, M drops a marker, Del deletes (Shift = ripple), arrows nudge.</div></div>';
  }
  function bindProjInsp() {
    $('#p_font').onchange = function () { P.font = this.value; commit(); };
    $$('[data-pal]').forEach(function (b) { b.onclick = function () { var p = PALS[+b.dataset.pal]; P.palette = { bg: p[0], fg: p[1], acc: p[2], acc2: p[3] }; commit(); }; });
    ['bg', 'fg', 'acc', 'acc2'].forEach(function (k) { $('#p_' + k).oninput = debounce(function () { P.palette = P.palette || {}; P.palette[k] = $('#p_' + k).value; commit(); }, 200); });
  }
  function autoWords(c) {
    pickMedia('audio,video', false, 'Which audio should the words follow?').then(function (l) {
      if (!l[0]) return; toast('Listening… (Whisper, can take a minute)');
      api('/api/motion/words', { src: l[0] }).then(function (d) {
        if (d.error) return toast(d.error, 1);
        var ws = d.words || []; if (!ws.length) return toast('No words heard', 1);
        var off = ws[0].s; c.props.words = ws.map(function (w) { return { w: w.w, s: +(w.s - off).toFixed(3), e: +(w.e - off).toFixed(3) }; });
        c.props.text = ws.map(function (w) { return w.w; }).join(' ');
        c.dur = +(ws[ws.length - 1].e - off + 0.6).toFixed(2); c.start = +(off).toFixed(3);
        var at = P.tracks.filter(function (t) { return t.kind === 'audio'; })[0];
        if (!at || !at.clips.some(function (x) { return x.props.src === l[0]; })) addScene('audio', 0, { src: l[0] });
        commit(); toast(ws.length + ' words timed');
      });
    });
  }

  /* ── edit ops ── */
  function dupSel() { var h = SEL && findClip(SEL); if (!h) return; var c = clone(h.c); c.id = uid(); c.start = +(h.c.start + h.c.dur).toFixed(3); h.t.clips.push(c); SEL = c.id; commit(); }
  function delSel(ripple) {
    var h = SEL && findClip(SEL); if (!h) return; h.t.clips.splice(h.ci, 1);
    if (ripple) h.t.clips.forEach(function (c) { if (c.start > h.c.start) c.start = +Math.max(0, c.start - h.c.dur).toFixed(3); });
    SEL = null; commit();
  }
  function splitSel() {
    var h = SEL && findClip(SEL), t = T(); if (!h || t <= h.c.start + 0.05 || t >= h.c.start + h.c.dur - 0.05) return toast('Put the playhead inside the selected clip', 1);
    var a = h.c, b = clone(a); b.id = uid(); var cut = +(t - a.start).toFixed(3); b.start = +t.toFixed(3); b.dur = +(a.dur - cut).toFixed(3); a.dur = cut; delete b.trans; delete a.out;
    if (b.type === 'media' || b.type === 'audio') b.props.trimIn = +((a.props.trimIn || 0) + cut * (a.props.speed || 1)).toFixed(3);
    if (a.kf) { b.kf = {}; Object.keys(a.kf).forEach(function (k) { b.kf[k] = a.kf[k].filter(function (p) { return p[0] >= cut; }).map(function (p) { return [+(p[0] - cut).toFixed(3), p[1]]; }); a.kf[k] = a.kf[k].filter(function (p) { return p[0] < cut; }); }); }
    if (Array.isArray(a.props.words)) { b.props.words = a.props.words.filter(function (w) { return w.s >= cut; }).map(function (w) { return { w: w.w, s: +(w.s - cut).toFixed(3), e: +(w.e - cut).toFixed(3) }; }); a.props.words = a.props.words.filter(function (w) { return w.s < cut; }); }
    h.t.clips.push(b); SEL = b.id; commit();
  }
  function nudge(d) { var h = SEL && findClip(SEL); if (!h) return; h.c.start = +Math.max(0, h.c.start + d).toFixed(3); commit(); }

  /* ── top bar / transport / keys ── */
  var ACT = {
    close: function () { save(); var msg = { mml: 'motion-close' }; if (window.parent !== window) { window.parent.postMessage(msg, '*'); return; } if (window.MMLApp && MMLApp.close) { MMLApp.close('{}'); return; } location.href = B + '/'; },
    undo: undo, redo: redo, play: play, start: function () { seek(0); }, end: function () { seek(dur()); },
    loop: function () { LOOP = !LOOP; $('#mo-loop').classList.toggle('on', LOOP); },
    safe: function () { var s = $('#mo-safe'); s.hidden = !s.hidden; $('#mo-safebtn').classList.toggle('on', !s.hidden); },
    marker: function () { P.markers = P.markers || []; P.markers.push(+T().toFixed(3)); P.markers.sort(function (a, b) { return a - b; }); commit(); },
    split: splitSel, dup: dupSel, del: function (e) { delSel(e && e.shiftKey); },
    snap: function () { SNAP = !SNAP; $('#mo-snap').classList.toggle('on', SNAP); },
    bin: function () { document.body.classList.toggle('bin'); document.body.classList.remove('insp'); },
    insp: function () { document.body.classList.toggle('insp'); document.body.classList.remove('bin'); },
    style: function () { SEL = null; drawTL(); drawInsp(); document.body.classList.add('insp'); },
    projects: projects, versions: versions, export: exportDlg, critique: critique,
  };
  function closeDrawers() { document.body.classList.remove('bin', 'insp'); }
  $$('[data-a]').forEach(function (b) { if (b.closest('#mo-insp')) return; b.addEventListener('click', function (e) { var f = ACT[b.dataset.a]; if (f) f(e); }); });
  $('#mo-name').onchange = function () { P.name = this.value.trim() || 'Untitled motion'; commit(); };
  $('#mo-aspect').onchange = function () { var p = this.value.split('x'); P.w = +p[0]; P.h = +p[1]; commit(); fitStage(); mountPlayer(); };
  $('#mo-fps').onchange = function () { P.fps = +this.value; commit(); mountPlayer(); };
  $$('.mo-bin .tabs button').forEach(function (b) { b.onclick = function () { $$('.mo-bin .tabs button').forEach(function (x) { x.classList.toggle('on', x === b); }); $$('.mo-bin .pane').forEach(function (p) { p.hidden = p.dataset.p !== b.dataset.t; }); if (b.dataset.t === 'lib' && !$('#mo-lib').children.length) loadLib(); if (b.dataset.t === 'ai') pollJobs(); }; });
  document.addEventListener('keydown', function (e) {
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    var k = e.key, c = e.ctrlKey || e.metaKey;
    if (k === ' ') { e.preventDefault(); play(); } else if (c && k.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); } else if (c && k.toLowerCase() === 'y') { e.preventDefault(); redo(); }
    else if (c && k.toLowerCase() === 'd') { e.preventDefault(); dupSel(); } else if (c && k.toLowerCase() === 's') { e.preventDefault(); dirty = true; save(); }
    else if (k === 'Delete' || k === 'Backspace') delSel(e.shiftKey); else if (k === 's' || k === 'S') splitSel(); else if (k === 'm' || k === 'M') ACT.marker(); else if (k === 'l' || k === 'L') ACT.loop();
    else if (k === 'Home') seek(0); else if (k === 'End') seek(dur()); else if (k === 'ArrowLeft') { e.preventDefault(); SEL ? nudge(e.shiftKey ? -1 : -1 / fps()) : seek(T() - 1 / fps()); }
    else if (k === 'ArrowRight') { e.preventDefault(); SEL ? nudge(e.shiftKey ? 1 : 1 / fps()) : seek(T() + 1 / fps()); }
    else if (k === '+' || k === '=') { PX = Math.min(300, PX * 1.25); $('#mo-zoom').value = PX; drawTL(); } else if (k === '-') { PX = Math.max(4, PX / 1.25); $('#mo-zoom').value = PX; drawTL(); }
    else if (k === 'Escape') { SEL = null; drawTL(); drawInsp(); }
  });

  /* ── modals: projects / versions ── */
  function modal(html) { var m = $('#mo-modal'); m.innerHTML = '<div class="box">' + html + '</div>'; m.hidden = false; m.onclick = function (e) { if (e.target === m) m.hidden = true; }; icons(); return m; }
  function projects() {
    api('/api/motion/projects').then(function (d) {
      var m = modal('<h2>Motion projects</h2><div class="list">' + (d.projects || []).map(function (p) { return '<div data-id="' + p.id + '">' + mi('sparkle') + '<b style="flex:1">' + esc(p.name) + '</b><span class="dim">' + fmt(p.dur) + ' · ' + p.clips + ' clips</span><button class="eb sm" data-rm="' + p.id + '">' + mi('trash', 'sm') + '</button></div>'; }).join('') +
        '</div><div class="acts"><button class="eb" data-x="new">' + mi('plus') + ' New project</button><button class="eb" data-x="close">Close</button></div>');
      $$('.list>div', m).forEach(function (r) { r.onclick = function (e) { if (e.target.closest('[data-rm]')) return; m.hidden = true; open(r.dataset.id); }; });
      $$('[data-rm]', m).forEach(function (b) { b.onclick = function () { if (confirm('Move this project to the trash?')) api('/api/motion/project/' + b.dataset.rm + '/delete', {}).then(projects); }; });
      $('[data-x=new]', m).onclick = function () { m.hidden = true; save().then(function () { open(''); }); };
      $('[data-x=close]', m).onclick = function () { m.hidden = true; };
    });
  }
  function versions() {
    if (!P.id) return toast('Save first — versions appear every 5 minutes of work');
    api('/api/motion/project/' + P.id + '/versions').then(function (d) {
      var m = modal('<h2>Versions</h2><div class="list">' + ((d.versions || []).map(function (v) { return '<div data-f="' + v.file + '">' + mi('clock') + new Date(v.t * 1000).toLocaleString() + '</div>'; }).join('') || '<div class="dim">No earlier versions yet.</div>') + '</div><div class="acts"><button class="eb" data-x="c">Close</button></div>');
      $$('[data-f]', m).forEach(function (r) { r.onclick = function () { api('/api/motion/project/' + P.id + '/restore', { file: r.dataset.f }).then(function (p) { if (p.error) return toast(p.error, 1); p.id = P.id; P = p; m.hidden = true; commit(); mountPlayer(); toast('Restored — undo to go back'); }); }; });
      $('[data-x=c]', m).onclick = function () { m.hidden = true; };
    });
  }

  /* ── export + jobs ── */
  var CODECS = [['mp4', 'MP4 · H.264 (everything)'], ['h265', 'MP4 · H.265 (smaller)'], ['alpha', 'WebM with transparency (overlay)'], ['prores', 'ProRes 4444 + alpha (pro editors)'], ['webm', 'WebM'], ['gif', 'GIF'], ['mp3', 'Audio only · MP3']];
  function exportDlg() {
    save();
    var m = modal('<h2>Export with Remotion</h2><div class="fld"><label>Format</label><select id="x_codec">' + CODECS.map(function (c) { return '<option value="' + c[0] + '">' + c[1] + '</option>'; }).join('') + '</select></div>' +
      '<div class="fld"><label>Quality</label><select id="x_crf"><option value="16">Best</option><option value="20" selected>High</option><option value="26">Smaller file</option></select></div>' +
      '<div class="dim" style="font-size:12px">' + P.w + '×' + P.h + ' · ' + fmt(dur()) + (dur() > 67 ? ' · long video: rendered in cached 45 s segments — re-exports only redo what changed.' : '') + ' Renders on the CPU, next to any GPU jobs. Lands in your library' + (P.session ? ' (this project\'s session)' : '') + '.</div>' +
      '<div class="acts"><button class="eb" data-x="c">Cancel</button><button class="eb pri" data-x="go">' + mi('upload') + ' Render</button></div>');
    $('[data-x=c]', m).onclick = function () { m.hidden = true; };
    $('[data-x=go]', m).onclick = function () {
      m.hidden = true;
      api('/api/motion/render', { project: P, codec: $('#x_codec').value, crf: +$('#x_crf').value, session: P.session }).then(function (d) {
        if (d.error) return toast(d.error, 1); toast('Rendering…'); $$('.mo-bin .tabs button')[2].click(); pollJobs();
      });
    };
  }
  var jobT;
  function pollJobs() {
    clearTimeout(jobT);
    api('/api/motion/jobs').then(function (d) {
      var js = d.jobs || [], box = $('#mo-jobs');
      box.innerHTML = js.length ? js.slice(0, 8).map(function (j) {
        return '<div class="job"><b>' + esc(j.name || j.id) + '</b> <span class="dim">' + esc(j.status === 'running' ? j.stage : j.status) + (j.cached ? ' · ' + j.cached + ' cached' : '') + '</span>' +
          (j.status === 'running' ? '<div class="bar"><i style="width:' + (j.pct || 0) + '%"></i></div>' : '') + (j.error ? '<div style="color:#ff9b8f;font-size:11px">' + esc(j.error).slice(0, 220) + '</div>' : '') +
          '<div class="acts">' + (j.status === 'running' ? '<button class="eb sm" data-c="' + j.id + '">Cancel</button>' : '') +
          (j.status === 'done' && j.src ? '<a class="eb sm" href="' + B + '/' + j.url + '" target="_blank">' + mi('play', 'sm') + ' Watch</a><button class="eb sm" data-ed="' + j.src + '">' + mi('film', 'sm') + ' Video editor</button><button class="eb sm" data-at="' + j.src + '">' + mi('attach', 'sm') + ' Use in chat</button>' : '') + '</div></div>';
      }).join('') : '<div class="dim">nothing running</div>';
      $$('[data-c]', box).forEach(function (b) { b.onclick = function () { api('/api/motion/job/' + b.dataset.c + '/cancel', {}).then(pollJobs); }; });
      $$('[data-ed]', box).forEach(function (b) { b.onclick = function () { post({ mml: 'motion-editor', src: b.dataset.ed }); }; });
      $$('[data-at]', box).forEach(function (b) { b.onclick = function () { post({ mml: 'motion-attach', ref: b.dataset.at }); }; });
      icons();
      if (js.some(function (j) { return j.status === 'running'; })) jobT = setTimeout(pollJobs, 1500);
    });
  }
  function post(msg) { save(); if (window.parent !== window) window.parent.postMessage(msg, '*'); else if (msg.mml === 'motion-editor') location.href = B + '/editor?add=' + encodeURIComponent(msg.src); }

  /* ── engine status ── */
  function engine() { api('/api/motion/health?start=1').then(function (h) { var e = $('#mo-eng'); e.className = 'mo-eng ' + (h.ok ? 'ok' : 'bad'); e.textContent = h.ok ? 'Remotion ' + h.version + (h.busy ? ' · rendering' : '') : 'engine starting…'; if (!h.ok) setTimeout(engine, 4000); }); }

  /* ── AI ── */
  var AIMODE = 'append';
  $$('#ai-mode button').forEach(function (b) { b.onclick = function () { AIMODE = b.dataset.m; $$('#ai-mode button').forEach(function (x) { x.classList.toggle('on', x === b); }); }; });
  $('#ai-go').onclick = function () { var a = $('#ai-prompt').value.trim(); if (!a) return toast('Say what you want', 1); var h = SEL && findClip(SEL); if (AIMODE === 'props' && !h) return toast('Select a clip first', 1); aiRun(AIMODE, a, h && h.c, +$('#ai-secs').value || 0); };
  function aiRun(mode, ask, clip, secs) {
    toast('MUSE is writing…'); $('#ai-go').disabled = true;
    return api('/api/motion/ai', { ask: ask, mode: mode, project: P, clip: clip || null, secs: secs || 0 }).then(function (d) {
      $('#ai-go').disabled = false; if (d.error) return toast(d.error, 1);
      applyAI(mode, d, clip); toast('Done — undo (Ctrl+Z) if you don\'t like it');
    }).catch(function () { $('#ai-go').disabled = false; toast('MUSE is offline', 1); });
  }
  function applyAI(mode, d, clip) {
    if (d.palette && mode === 'project') P.palette = Object.assign({}, P.palette, d.palette);
    if (d.font && mode === 'project') P.font = d.font;
    if (mode === 'project') { var keep = { id: P.id, name: d.name || P.name, w: P.w, h: P.h, fps: P.fps, session: P.session, markers: P.markers, palette: P.palette, font: P.font }; P = Object.assign(keep, { tracks: d.tracks }); SEL = null; }
    else if (mode === 'props' && clip) { var nc = ((d.tracks || [])[0] || {}).clips || []; if (nc[0]) { var h = findClip(clip.id); if (h) { nc[0].id = clip.id; h.t.clips[h.ci] = nc[0]; } } }
    else { var at = T(); (d.tracks || []).forEach(function (t) { var tr = trackFor(t.kind); t.clips.forEach(function (c) { c.id = uid(); c.start = +(c.start + at).toFixed(3); tr.clips.push(c); }); }); }
    commit(); MM.update(view());
  }
  function critique() {
    toast('Rendering this frame for MUSE…');
    fetch(B + '/api/motion/still', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project: P, frame: curF, scale: 0.5 }) }).then(function (r) {
      if (!r.ok) throw 0; return r.blob();
    }).then(function (b) {
      var u = URL.createObjectURL(b);
      modal('<h2>Frame ' + curF + '</h2><img src="' + u + '" style="width:100%;border-radius:8px"><div class="dim" style="font-size:12px;margin-top:8px">Ask MUSE to change it — your words go to the AI tab with this frame\'s scenes.</div><textarea id="cq" rows="2" placeholder="e.g. title is too small, make the colours warmer"></textarea><div class="acts"><button class="eb" data-x="c">Close</button><button class="eb pri" data-x="go">' + mi('sparkle') + ' Fix it</button></div>');
      var m = $('#mo-modal'); $('[data-x=c]', m).onclick = function () { m.hidden = true; };
      $('[data-x=go]', m).onclick = function () { var a = $('#cq').value.trim(); if (!a) return; m.hidden = true; aiRun('project', 'At ' + T().toFixed(1) + 's: ' + a); };
    }).catch(function () { toast('Could not render the frame — is the engine running?', 1); });
  }

  /* ── wizards + templates ── */
  function seqProject(name, scenes, extra) { var p = blank(); p.name = name; p.id = P.id; p.session = P.session; p.w = P.w; p.h = P.h; p.fps = P.fps; p.palette = P.palette; p.font = P.font; var t = 0;
    scenes.forEach(function (s, i) { var c = { id: uid(), type: s[0], start: +t.toFixed(3), dur: s[1], props: Object.assign(defaults(s[0]), s[2] || {}) }; if (i) c.trans = { type: s[3] || 'fade', dur: 0.5 }; p.tracks[0].clips.push(c); t += s[1] - (i < scenes.length - 1 ? 0.5 : 0); });
    (extra || []).forEach(function (e) { trackIn(p, e.kind).clips.push(Object.assign({ id: uid() }, e.clip)); }); return p; }
  function trackIn(p, k) { var t = p.tracks.filter(function (x) { return x.kind === k; })[0]; if (!t) { t = { kind: k, name: KINDS[k], clips: [] }; p.tracks.push(t); } return t; }
  function replaceWith(p, msg) { if (P.tracks.some(function (t) { return t.clips.length; }) && !confirm('Replace the current timeline? (Undo brings it back.)')) return; P = p; SEL = null; commit(); mountPlayer(); seek(0); toast(msg || 'Ready'); }
  var TPL = [
    ['intro', 'film', 'Channel intro', 'Logo sting → title → subtitle — 7 s', function () { return seqProject('Channel intro', [['logo', 2.5, { text: 'MIR MEDIA' }], ['title', 4, { text: 'Episode One', sub: 'a MirOS production', anim: 'word-pop' }, 'zoom']]); }],
    ['promo', 'star', 'Promo · 30 s', 'Hook, three feature cards, stat, call to action', function () { return seqProject('Promo', [['title', 4, { text: 'Meet MIR MEDIA LABS', anim: 'kinetic' }], ['split', 6, { title: 'Create', body: 'Video, music and pictures from one sentence.' }, 'slide-left'], ['split', 6, { title: 'Edit', body: 'Timeline editor + motion studio.', flip: true }, 'slide-left'], ['split', 6, { title: 'Publish', body: 'Straight to YouTube and Instagram.' }, 'slide-left'], ['stat', 4, { value: 10, suffix: 'x', label: 'faster' }, 'zoom'], ['title', 5, { text: 'Try it today', sub: 'mirmedialabs', anim: 'stamp' }, 'iris']]); }],
    ['explainer', 'book', 'Explainer · 60 s', 'Chapters, quote, chart and credits', function () { return seqProject('Explainer', [['title', 4, { text: 'How it works', anim: 'mask-up' }], ['chapter', 3, { num: '1', title: 'The idea' }], ['quote', 6, { text: 'Simple things, done well.' }], ['chapter', 3, { num: '2', title: 'The numbers' }], ['chart', 7, { title: 'Growth' }], ['stat', 4, { value: 87, suffix: '%', label: 'success' }], ['credits', 10, { title: 'Thanks for watching' }, 'blur']]); }],
    ['lyrics', 'music', 'Lyric video', 'Pick a song → Whisper times every word', function () { return wizard('lyrics'); }],
    ['podcast', 'activity', 'Podcast visualizer', 'Audio bars + live captions', function () { return wizard('visualizer'); }],
    ['long', 'layers', 'Long video · chapters', 'Documentary skeleton: N chapters × footage + titles', function () { return wizard('long'); }],
    ['vertical', 'phone', 'Short / Reel (9:16)', 'Hook text, clip, captions, end card', function () { P.w = 1080; P.h = 1920; $('#mo-aspect').value = '1080x1920'; return seqProject('Short', [['title', 2.5, { text: 'Wait for it…', anim: 'shake', size: 140 }], ['media', 12, {}], ['title', 3, { text: 'Follow for more', anim: 'bounce' }, 'zoom']], [{ kind: 'captions', clip: { type: 'captions', start: 2.5, dur: 12, props: { style: 'pop', pos: 'middle', size: 90, upper: true } } }]); }],
  ];
  function drawTpl() {
    $('#tpl-list').innerHTML = TPL.map(function (t, i) { return '<div class="tpl" data-i="' + i + '"><b>' + mi(t[1]) + esc(t[2]) + '</b><small>' + esc(t[3]) + '</small></div>'; }).join('');
    $$('.tpl').forEach(function (el) { el.onclick = function () { var r = TPL[+el.dataset.i][4](); if (r && r.then) return; if (r) { replaceWith(r, 'Template loaded'); closeDrawers(); } }; }); icons();
  }
  function wizard(w) {
    if (w === 'lyrics') return pickMedia('audio', false, 'Pick the song').then(function (l) { if (!l[0]) return; toast('Timing the lyrics with Whisper…');
      api('/api/motion/words', { src: l[0] }).then(function (d) { if (d.error) return toast(d.error, 1); var ws = d.words || []; if (!ws.length) return toast('No vocals heard', 1); var end = ws[ws.length - 1].e + 2;
        replaceWith(seqProject('Lyric video', [['lyrics', end, { words: ws, text: ws.map(function (x) { return x.w; }).join(' ') }]], [{ kind: 'audio', clip: { type: 'audio', start: 0, dur: end, props: { src: l[0], volume: 1 } } }]), ws.length + ' words timed'); }); });
    if (w === 'captions') return pickMedia('video', false, 'Pick the video to caption').then(function (l) { if (!l[0]) return; toast('Transcribing…');
      Promise.all([api('/api/motion/words', { src: l[0] }), api('/api/editor/probe?src=' + encodeURIComponent(l[0]))]).then(function (r) { var d = r[0], pr = r[1] || {}; if (d.error) return toast(d.error, 1); var ws = d.words || [], len = +pr.dur || ((ws[ws.length - 1] || { e: 10 }).e + 1);
        var p = seqProject('Captioned video', [['media', len, { src: l[0], kind: 'video' }]], [{ kind: 'captions', clip: { type: 'captions', start: 0, dur: len, props: { words: ws, style: 'pop', upper: true } } }]);
        if (pr.w && pr.h) { p.w = pr.w & ~1; p.h = pr.h & ~1; } replaceWith(p, ws.length + ' words captioned'); }); });
    if (w === 'slideshow') return pickMedia('image', true, 'Pick the images (in order)').then(function (l) { if (!l.length) return; replaceWith(seqProject('Slideshow', [['slideshow', Math.max(6, l.length * 4), { images: l }]])); });
    if (w === 'visualizer') return pickMedia('audio', false, 'Pick the audio').then(function (l) { if (!l[0]) return; api('/api/editor/probe?src=' + encodeURIComponent(l[0])).then(function (pr) { var len = +(pr || {}).dur || 60;
      replaceWith(seqProject('Visualizer', [['visualizer', len, { src: l[0], title: P.name }]], [{ kind: 'audio', clip: { type: 'audio', start: 0, dur: len, props: { src: l[0] } } }]), 'Add captions with the Captions scene + Whisper'); }); });
    if (w === 'trailer') return pickMedia('video,image', true, 'Pick the clips for the trailer').then(function (l) { if (!l.length) return; var sc = [['title', 2.5, { text: 'This summer…', anim: 'tracking' }]];
      l.forEach(function (s, i) { sc.push(['media', 2.2, { src: s, kenburns: 'zoom-in' }, i % 2 ? 'flash' : 'glitch']); if (i === Math.floor(l.length / 2)) sc.push(['title', 2, { text: 'One story', anim: 'stamp' }, 'flash']); });
      sc.push(['title', 4, { text: P.name || 'Coming soon', sub: 'coming soon', anim: 'word-pop' }, 'iris']); replaceWith(seqProject('Trailer', sc)); });
    if (w === 'long') {
      var n = +prompt('How many chapters?', '5'); if (!n || n < 1) return; var per = +prompt('Minutes per chapter?', '2') * 60; if (!per) return;
      var sc = [['title', 5, { text: P.name || 'My documentary', anim: 'tracking' }]];
      for (var i = 1; i <= Math.min(40, n); i++) { sc.push(['chapter', 3, { num: String(i), title: 'Chapter ' + i }, 'wipe']); sc.push(['slideshow', Math.max(5, per - 3), { images: [] }, 'fade']); }
      sc.push(['credits', 12, { title: 'Credits' }, 'blur']);
      replaceWith(seqProject('Long video', sc), 'Fill each chapter: pick images or swap in footage — or ask MUSE'); return;
    }
  }
  $$('[data-w]').forEach(function (b) { b.onclick = function () { wizard(b.dataset.w); closeDrawers(); }; });

  /* ── open + messages from the lab ── */
  function open(id) {
    var go = function (p) { P = p; P.tracks = P.tracks || []; P.markers = P.markers || []; SEL = null; UNDO = []; REDO = []; last = JSON.stringify(P); dirty = false;
      $('#mo-aspect').value = P.w + 'x' + P.h; $('#mo-fps').value = String(P.fps); $('#mo-name').value = P.name;
      try { history.replaceState(null, '', location.pathname + (P.id ? '?p=' + P.id : '')); } catch (e) { }
      fitStage(); mountPlayer(); seek(0); refresh(); };
    if (!id) { go(blank()); return Promise.resolve(); }
    return api('/api/motion/project/' + id).then(function (p) { if (p.error) { toast(p.error, 1); go(blank()); } else go(p); });
  }
  window.addEventListener('message', function (e) { var d = e.data || {};
    if (d.mml === 'motion-add' && d.src) { addMedia(d.src, d.kind); toast('Added from the lab'); }
    if (d.mml === 'motion-open' && d.id) open(d.id);
  });
  drawScenes(); drawTpl(); engine();
  var first = Q.get('p') || '';
  open(first).then(function () {
    if (Q.get('add')) addMedia(Q.get('add'));
    if (Q.get('wizard')) wizard(Q.get('wizard'));
    if (Q.get('tpl')) { var t = TPL.filter(function (x) { return x[0] === Q.get('tpl'); })[0]; if (t) { var r = t[4](); if (r && !r.then) replaceWith(r); } }
    if (Q.get('ask')) { $('#ai-prompt').value = Q.get('ask'); $$('.mo-bin .tabs button')[2].click(); }
  });
  setInterval(function () { if (MM.playing()) tick(); }, 250);
})();
