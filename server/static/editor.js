/* MIR MEDIA LABS · timeline editor — IDENTICAL in both lab copies (standalone :5400 and MirOS /mlab).
   Timeline (video / image / colour / text / audio tracks) · live preview compositor · trim / split / move / ripple ·
   speed, volume, fades, crossfades, fit, position, scale, rotate, colour, looks, Ken Burns, titles ·
   AI tools (animate, extend, regenerate, restyle, edit picture, remix, score, voiceover, fill gap) run through the
   lab's own /api/generate with frames / cuts of your clips as references, and land back on the timeline ·
   export through ffmpeg (editor.py) into the library or as a lab attachment. Engine names never appear here. */
(function () {
  'use strict';
  var B = location.pathname.indexOf('/mlab') === 0 ? '/mlab' : '';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var ED = $('#ed'), STAGE = $('#ed-stage'), WRAP = $('#ed-stagewrap'), TRACKS = $('#ed-tracks'), HEADS = $('#ed-heads'),
    SCROLL = $('#ed-scroll'), RULER = $('#ed-ruler'), PH = $('#ed-ph'), INSP = $('#ed-insp');
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mi(n, c) { return window.MI ? MI.html(n, c) : ''; }
  function uid() { return Math.random().toString(36).slice(2, 10); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function num(v, d) { v = parseFloat(v); return isFinite(v) ? v : d; }
  function fmt(s, fine) { s = Math.max(0, s || 0); var m = Math.floor(s / 60), r = s - m * 60;
    return String(m).padStart(2, '0') + ':' + (fine ? r.toFixed(2).padStart(5, '0') : String(Math.floor(r)).padStart(2, '0')); }
  function api(path, body, method) {
    var o = { cache: 'no-store', credentials: 'same-origin' };
    if (body !== undefined) { o.method = method || 'POST'; o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok && !j.error) j.error = 'HTTP ' + r.status; j._status = r.status; return j; }); });
  }
  var toastT;
  function toast(t, err) { var e = $('#ed-toast'); e.textContent = t; e.className = 'ed-toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'ed-toast'; }, err ? 5200 : 2600); }

  /* ── theme: the lab's palette (shared localStorage + /api/miros-prefs) ── */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    r.setProperty('--bg', t[0]); r.setProperty('--panel', t[1]); r.setProperty('--panel2', t[2]); r.setProperty('--ink', t[3]); r.setProperty('--acc', t[4]);
    var m = $('meta[name=theme-color]'); if (m) m.content = t[1]; }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/miros-prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });

  /* ── project model ── */
  var KIND_OF = { video: 'video', image: 'video', color: 'video', audio: 'audio', text: 'text' };
  var COLORS = { video: 'var(--vid)', image: 'var(--img)', audio: 'var(--aud)', text: 'var(--txt)', color: 'var(--col)' };
  function blank() {
    return { id: null, name: 'Untitled edit', w: 1280, h: 720, fps: 30, bg: '#000000', master: 1, tracks: [
      { id: 't1', kind: 'text', name: 'Titles', clips: [] }, { id: 'v2', kind: 'video', name: 'V2', clips: [] },
      { id: 'v1', kind: 'video', name: 'V1', clips: [] }, { id: 'a1', kind: 'audio', name: 'A1', clips: [] },
      { id: 'a2', kind: 'audio', name: 'Music', clips: [] }] };
  }
  var P = blank(), SEL = null, PPS = 80, T = 0, PLAYING = false, SNAP = true, META = {}, DIRTY = false;
  function len(c) { if (c.type === 'text' || c.type === 'image' || c.type === 'color') return Math.max(0.1, num(c.dur, 3));
    return Math.max(0.05, (num(c.out, 1) - num(c.in, 0)) / Math.max(0.1, num(c.speed, 1))); }
  function end(c) { return num(c.start, 0) + len(c); }
  function visEnd() { var t = 0; P.tracks.forEach(function (tr) { if (tr.kind === 'video') tr.clips.forEach(function (c) { t = Math.max(t, end(c)); }); }); return t; }
  function total() { var t = 0; P.tracks.forEach(function (tr) { tr.clips.forEach(function (c) { t = Math.max(t, end(c)); }); }); return t; }
  function find(id) { for (var i = 0; i < P.tracks.length; i++) for (var j = 0; j < P.tracks[i].clips.length; j++) if (P.tracks[i].clips[j].id === id) return { t: P.tracks[i], c: P.tracks[i].clips[j], i: j }; return null; }
  function trackOf(id) { return P.tracks.filter(function (t) { return t.id === id; })[0]; }
  function url(src) { var k = String(src || '').split(':'), n = k.slice(1).join(':'); return k[0] === 'lib' ? B + '/media/' + encodeURIComponent(n) : k[0] === 'ref' ? B + '/refs/' + encodeURIComponent(n) : ''; }
  function q(src) { return 'src=' + encodeURIComponent(src); }
  function kindOfName(n) { n = String(n).toLowerCase(); return /\.(mp4|mov|webm|m4v|mkv)$/.test(n) ? 'video' : /\.(png|jpe?g|webp)$/.test(n) ? 'image' : /\.(mp3|wav|flac|ogg|m4a|aac)$/.test(n) ? 'audio' : 'file'; }
  function probe(src) { if (META[src]) return Promise.resolve(META[src]);
    return api('/api/editor/probe?' + q(src)).then(function (m) { if (!m.error) META[src] = m; return m; }); }

  /* ── undo / redo + autosave ── */
  var UNDO = [], REDO = [], last = JSON.stringify(P), saveT = null;
  function commit(noSave) {
    var now = JSON.stringify(P);
    if (now === last) return;
    UNDO.push(last); if (UNDO.length > 120) UNDO.shift(); REDO = []; last = now;
    if (!noSave) dirty();
  }
  function restore(s) { P = JSON.parse(s); last = s; if (SEL && !find(SEL)) SEL = null; drawAll(); dirty(); }
  function undo() { if (!UNDO.length) return; REDO.push(last); restore(UNDO.pop()); }
  function redo() { if (!REDO.length) return; UNDO.push(last); restore(REDO.pop()); }
  function dirty() { DIRTY = true; $('#ed-save').textContent = 'editing…'; clearTimeout(saveT); saveT = setTimeout(save, 1400); }
  function save() {
    if (!P.tracks.some(function (t) { return t.clips.length; }) && !P.id) { $('#ed-save').textContent = ''; return Promise.resolve(); }
    $('#ed-save').textContent = 'saving…';
    var cv = firstVisual(); if (cv && cv.src) P.cover = cv.src;
    return api('/api/editor/project', P).then(function (r) {
      if (r.error) { $('#ed-save').textContent = 'not saved'; toast('Save failed: ' + r.error, 1); return; }
      if (!P.id) { P.id = r.id; last = JSON.stringify(P); try { history.replaceState(null, '', location.pathname + '?p=' + r.id); } catch (e) { } }
      DIRTY = false; $('#ed-save').textContent = 'saved'; try { localStorage.setItem('mml.ed.last', P.id); } catch (e) { }
    }).catch(function () { $('#ed-save').textContent = 'offline — not saved'; });
  }
  function firstVisual() { for (var i = P.tracks.length - 1; i >= 0; i--) if (P.tracks[i].kind === 'video') for (var j = 0; j < P.tracks[i].clips.length; j++) if (P.tracks[i].clips[j].src) return P.tracks[i].clips[j]; return null; }

  /* ── adding clips ── */
  function free(tr, a, b, skip) { return !tr.clips.some(function (c) { return c.id !== skip && c.start < b - 1e-3 && end(c) > a + 1e-3; }); }
  function pickTrack(kind, at, l) {
    var ts = P.tracks.filter(function (t) { return t.kind === kind && !t.locked; });
    if (kind === 'video') ts = ts.slice().reverse();          // V1 (bottom) first
    for (var i = 0; i < ts.length; i++) if (free(ts[i], at, at + l)) return ts[i];
    return ts[0] || null;
  }
  function addMedia(src, opts) {
    opts = opts || {};
    var k = kindOfName(src);
    return probe(src).then(function (m) {
      if (m.error) { toast('Can\'t read that file: ' + m.error, 1); return null; }
      var type = m.kind === 'image' ? 'image' : m.kind === 'audio' ? 'audio' : 'video';
      var c = { id: uid(), type: type, src: src, name: opts.name || src.split(':').slice(1).join(':').replace(/^ref_\d+_/, ''), start: 0,
        speed: 1, volume: 1, fade_in: 0, fade_out: 0, opacity: 1, scale: 1, x: 0, y: 0, fit: 'cover', prompt: opts.prompt || '',
        sw: m.w, sh: m.h, sdur: m.dur, audio: m.audio };
      if (type === 'image') c.dur = opts.dur || 4; else { c.in = 0; c.out = m.dur || 4; if (opts.dur) c.out = Math.min(c.out, opts.dur); }
      var at = opts.at != null ? opts.at : T, tr = opts.track ? trackOf(opts.track) : null;
      if (!tr || KIND_OF[type] !== tr.kind) tr = pickTrack(KIND_OF[type], at, len(c));
      if (!tr) { tr = { id: uid(), kind: KIND_OF[type], name: KIND_OF[type] === 'audio' ? 'A' : 'V', clips: [] }; P.tracks.push(tr); }
      if (opts.ripple) rippleInsert(tr, at, len(c));
      else if (!free(tr, at, at + len(c)) && !opts.overlap) { var e = 0; tr.clips.forEach(function (x) { if (end(x) > e) e = end(x); }); at = opts.at != null ? at : e; }
      c.start = Math.max(0, at);
      tr.clips.push(c); SEL = c.id;
      commit(); drawAll(); return c;
    });
  }
  function rippleInsert(tr, at, l) { tr.clips.forEach(function (x) { if (x.start >= at - 1e-3) x.start += l; }); }
  function addText(at) {
    var tr = pickTrack('text', at == null ? T : at, 3) || (function () { var t = { id: uid(), kind: 'text', name: 'Titles', clips: [] }; P.tracks.unshift(t); return t; })();
    var c = { id: uid(), type: 'text', text: 'Your title', start: at == null ? T : at, dur: 3, size: 0.07, color: '#ffffff', pos: 'center', box: true,
      box_color: '#000000', box_alpha: 0.45, shadow: true, fade_in: 0.3, fade_out: 0.3, x: 0, y: 0 };
    tr.clips.push(c); SEL = c.id; commit(); drawAll(); openInsp();
  }
  function addColor() {
    var tr = pickTrack('video', T, 3); if (!tr) return;
    var c = { id: uid(), type: 'color', color: '#111111', start: T, dur: 3, fade_in: 0, fade_out: 0, opacity: 1, name: 'Colour' };
    if (!free(tr, T, T + 3)) tr = P.tracks.filter(function (t) { return t.kind === 'video'; })[0];
    tr.clips.push(c); SEL = c.id; commit(); drawAll(); openInsp();
  }

  /* ── editing ops ── */
  function split() {
    var f = SEL && find(SEL), c = f && f.c;
    if (!c || T <= c.start + 0.05 || T >= end(c) - 0.05) {   // no selection: split whatever sits under the playhead on the top-most track
      var hit = null; P.tracks.forEach(function (t) { t.clips.forEach(function (x) { if (!hit && T > x.start + 0.05 && T < end(x) - 0.05) hit = { t: t, c: x }; }); });
      if (!hit) { toast('Put the playhead over a clip to split it'); return; }
      f = hit; c = hit.c;
    }
    var d = T - c.start, b = JSON.parse(JSON.stringify(c)); b.id = uid();
    if (c.type === 'text' || c.type === 'image' || c.type === 'color') { b.dur = c.dur - d; c.dur = d; if (c.type === 'image' && c.motion) b.motion = c.motion; }
    else { var cut = num(c.in, 0) + d * num(c.speed, 1); b.in = cut; c.out = cut; }
    b.start = T; c.fade_out = 0; b.fade_in = 0;
    f.t.clips.push(b); SEL = b.id; commit(); drawAll();
  }
  function del(ripple) {
    var f = SEL && find(SEL); if (!f) return;
    var l = len(f.c), s = f.c.start;
    f.t.clips.splice(f.i, 1);
    if (ripple) f.t.clips.forEach(function (x) { if (x.start >= s) x.start = Math.max(0, x.start - l); });
    SEL = null; commit(); drawAll();
  }
  function dup() { var f = SEL && find(SEL); if (!f) return; var b = JSON.parse(JSON.stringify(f.c)); b.id = uid(); b.start = end(f.c);
    if (!free(f.t, b.start, b.start + len(b))) rippleInsert(f.t, b.start, len(b));
    f.t.clips.push(b); SEL = b.id; commit(); drawAll(); }
  function detachAudio() {
    var f = SEL && find(SEL); if (!f || f.c.type !== 'video') return;
    var a = { id: uid(), type: 'audio', src: f.c.src, name: (f.c.name || '') + ' · audio', start: f.c.start, in: f.c.in, out: f.c.out, speed: f.c.speed,
      volume: f.c.volume == null ? 1 : f.c.volume, fade_in: f.c.fade_in, fade_out: f.c.fade_out, sdur: f.c.sdur };
    var tr = pickTrack('audio', a.start, len(a)); if (!tr) return;
    tr.clips.push(a); f.c.muted = true; SEL = a.id; commit(); drawAll(); toast('Audio detached to ' + tr.name);
  }
  function crossfade() {   // pull the selected clip back over the one before it on the same track
    var f = SEL && find(SEL); if (!f) return;
    var prev = f.t.clips.filter(function (x) { return x.id !== f.c.id && end(x) <= f.c.start + 0.01; }).sort(function (a, b) { return end(b) - end(a); })[0];
    if (!prev) { toast('Nothing before this clip on its track'); return; }
    var d = Math.min(0.8, len(prev) / 2, len(f.c) / 2), sh = f.c.start - (end(prev) - d);
    f.t.clips.forEach(function (x) { if (x.start >= f.c.start - 1e-3) x.start -= sh; });
    f.c.fade_in = d; prev.fade_out = 0; commit(); drawAll(); toast('Crossfade ' + d.toFixed(1) + 's');
  }

  /* ══════════ TIMELINE DRAWING ══════════ */
  var WAVES = {};
  function drawAll() { drawHeads(); drawTracks(); drawRuler(); drawPH(); drawInsp(); render(true); }
  function drawHeads() {
    HEADS.innerHTML = P.tracks.map(function (t) {
      var ic = t.kind === 'video' ? 'video' : t.kind === 'audio' ? 'music' : 'type';
      return '<div class="th" data-t="' + t.id + '"><b>' + mi(ic, 'sm') + esc(t.name) + '</b><div class="tb">' +
        (t.kind !== 'text' ? '<button data-x="mute" class="' + (t.muted ? 'on' : '') + '" title="Mute">' + mi(t.muted ? 'mute' : 'volume', 'sm') + '</button>' : '') +
        (t.kind !== 'audio' ? '<button data-x="hide" class="' + (t.hidden ? 'on' : '') + '" title="Hide">' + mi('x-circle', 'sm') + '</button>' : '') +
        '<button data-x="lock" class="' + (t.locked ? 'on' : '') + '" title="Lock">' + mi('lock', 'sm') + '</button>' +
        '<button data-x="rm" title="Remove empty track">' + mi('close', 'sm') + '</button></div></div>';
    }).join('');
    $$('.th button', HEADS).forEach(function (b) { b.onclick = function () {
      var t = trackOf(b.parentNode.parentNode.dataset.t), x = b.dataset.x;
      if (x === 'rm') { if (t.clips.length) { toast('Empty the track first'); return; } P.tracks.splice(P.tracks.indexOf(t), 1); }
      else t[x === 'mute' ? 'muted' : x === 'hide' ? 'hidden' : 'locked'] = !t[x === 'mute' ? 'muted' : x === 'hide' ? 'hidden' : 'locked'];
      commit(); drawAll(); }; });
  }
  function stripURL(c) {
    var n = clamp(Math.round((c.sdur || len(c)) * 1.2), 2, 30);
    return B + '/api/editor/strip?' + q(c.src) + '&n=' + (c.type === 'image' ? 1 : n) + '&h=56';
  }
  function drawTracks() {
    var w = Math.max(total() + 20, (SCROLL.clientWidth || 800) / PPS + 4) * PPS;
    TRACKS.style.width = w + 'px'; RULER.style.width = w + 'px';
    TRACKS.innerHTML = P.tracks.map(function (t) { return '<div class="tr" data-t="' + t.id + '"></div>'; }).join('');
    P.tracks.forEach(function (t) {
      var row = $('.tr[data-t="' + t.id + '"]', TRACKS);
      t.clips.forEach(function (c) { row.appendChild(clipEl(c, t)); });
    });
  }
  function clipEl(c, t) {
    var e = document.createElement('div'), l = len(c);
    e.className = 'clip' + (c.id === SEL ? ' sel' : '') + (c.muted || t.muted ? ' muted' : '') + (BUSY[c.id] ? ' busy' : '');
    e.dataset.id = c.id;
    e.style.left = (c.start * PPS) + 'px'; e.style.width = Math.max(6, l * PPS) + 'px';
    e.style.setProperty('--c', COLORS[c.type] || 'var(--vid)');
    var inner = '';
    if (c.type === 'video' || c.type === 'image') {
      var sp = num(c.speed, 1), full = (c.type === 'image' ? l : (c.sdur || l) / sp) * PPS;
      inner += '<div class="st" style="background-image:url(\'' + stripURL(c) + '\');' + (c.type === 'image' ? 'background-size:auto 100%' :
        'background-size:' + full.toFixed(1) + 'px 100%;background-repeat:no-repeat;background-position:' + (-(num(c.in, 0) / sp) * PPS).toFixed(1) + 'px 0') + '"></div>';
    } else if (c.type === 'audio') inner += '<canvas class="wv"></canvas>';
    else if (c.type === 'color') inner += '<div class="st" style="background:' + esc(c.color) + '"></div>';
    var ic = { video: 'video', image: 'image', audio: 'music', text: 'type', color: 'palette' }[c.type];
    inner += '<div class="lb">' + mi(ic, 'sm') + esc(c.type === 'text' ? c.text : c.name || c.type) + '</div>';
    var fx = [];
    if (num(c.speed, 1) !== 1) fx.push(num(c.speed, 1) + '×');
    if (c.look && c.look !== 'none') fx.push(c.look);
    if (c.motion) fx.push(c.motion);
    if (c.muted) fx.push('muted');
    if (fx.length) inner += '<div class="fx">' + esc(fx.join(' · ')) + '</div>';
    if (num(c.fade_in, 0) > 0) inner += '<div class="fade" style="left:0;width:' + (c.fade_in / l * 100) + '%"></div>';
    if (num(c.fade_out, 0) > 0) inner += '<div class="fade o" style="right:0;width:' + (c.fade_out / l * 100) + '%"></div>';
    inner += '<div class="h l"></div><div class="h r"></div>';
    e.innerHTML = inner;
    if (c.type === 'audio') drawWave(e.querySelector('canvas'), c);
    e.addEventListener('pointerdown', function (ev) { clipDown(ev, c, t, e); });
    e.addEventListener('dblclick', function () { SEL = c.id; openInsp(); drawInsp(); });
    return e;
  }
  function drawWave(cv, c) {
    function paint(pk) {
      if (!cv.isConnected) return;
      var w = cv.clientWidth || 100, h = cv.clientHeight || 40; cv.width = w; cv.height = h;
      var x = cv.getContext('2d'), d = pk.dur || c.sdur || 1, a = num(c.in, 0) / d, b = num(c.out, d) / d;
      x.fillStyle = 'rgba(255,255,255,.75)';
      for (var i = 0; i < w; i += 2) {
        var p = pk.peaks[Math.floor((a + (b - a) * i / w) * pk.peaks.length)] || 0, hh = Math.max(1, p * h * 0.9 * Math.min(1.6, num(c.volume, 1)));
        x.fillRect(i, (h - hh) / 2, 1.4, hh);
      }
    }
    if (WAVES[c.src]) { requestAnimationFrame(function () { paint(WAVES[c.src]); }); return; }
    api('/api/editor/wave?' + q(c.src) + '&n=1200').then(function (pk) { if (pk.peaks) { WAVES[c.src] = pk; paint(pk); } });
  }
  function drawRuler() {
    var w = parseFloat(RULER.style.width) || 1000, cv = RULER.querySelector('canvas');
    if (!cv) { cv = document.createElement('canvas'); RULER.appendChild(cv); }
    var dpr = window.devicePixelRatio || 1; cv.width = w * dpr; cv.height = 24 * dpr; cv.style.width = w + 'px'; cv.style.height = '24px';
    var x = cv.getContext('2d'); x.scale(dpr, dpr);
    var cs = getComputedStyle(document.documentElement);
    var ink = (cs.getPropertyValue('--ink') || '#ddd').trim(); x.fillStyle = ink; x.strokeStyle = ink; x.globalAlpha = 0.55;
    x.font = '10px ' + (cs.getPropertyValue('--mono') || 'monospace');
    var step = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60].filter(function (s) { return s * PPS >= 60; })[0] || 60;
    for (var i = 0; i * step / 5 * PPS < w; i++) {
      var s = Math.round(i * step / 5 * 1000) / 1000, px = Math.round(s * PPS) + 0.5, major = i % 5 === 0;
      x.beginPath(); x.moveTo(px, major ? 10 : 17); x.lineTo(px, 24); x.stroke();
      if (major) x.fillText(step < 1 ? s.toFixed(step < 0.25 ? 1 : 2).replace(/0$/, '') + 's' : fmt(s), px + 3, 10);
    }
  }
  function drawPH() { PH.style.left = (T * PPS) + 'px'; PH.style.height = (24 + TRACKS.offsetHeight) + 'px';
    $('#ed-tc').textContent = fmt(T, 1) + ' / ' + fmt(total(), 1); }
  function seek(t, keepView) { T = clamp(t, 0, Math.max(total(), 0)); drawPH(); render(true);
    if (!keepView) { var x = T * PPS; if (x < SCROLL.scrollLeft + 20 || x > SCROLL.scrollLeft + SCROLL.clientWidth - 40) SCROLL.scrollLeft = x - SCROLL.clientWidth * 0.4; } }

  /* ── pointer: move / trim / change track; ruler scrub ── */
  function snapPoints(skip) { var p = [0, T]; P.tracks.forEach(function (t) { t.clips.forEach(function (c) { if (c.id !== skip) { p.push(c.start, end(c)); } }); }); return p; }
  var snapLine = null;
  function showSnap(t) { if (!snapLine) { snapLine = document.createElement('div'); snapLine.className = 'snapline'; SCROLL.appendChild(snapLine); }
    snapLine.style.display = t == null ? 'none' : 'block'; if (t != null) { snapLine.style.left = (t * PPS) + 'px'; snapLine.style.height = (24 + TRACKS.offsetHeight) + 'px'; } }
  function snap(v, skip) { if (!SNAP) return { v: v, s: null }; var best = null, th = 8 / PPS;
    snapPoints(skip).forEach(function (p) { if (Math.abs(p - v) < th && (best == null || Math.abs(p - v) < Math.abs(best - v))) best = p; });
    return best == null ? { v: v, s: null } : { v: best, s: best }; }
  function clipDown(ev, c, t, el) {
    if (ev.button > 0) return;
    ev.preventDefault(); ev.stopPropagation();
    if (SEL !== c.id) { SEL = c.id; $$('.clip.sel', TRACKS).forEach(function (x) { x.classList.remove('sel'); }); el.classList.add('sel'); drawInsp(); render(true); }
    if (t.locked) return;
    var mode = ev.target.classList.contains('l') ? 'l' : ev.target.classList.contains('r') ? 'r' : 'm';
    var x0 = ev.clientX, o = JSON.parse(JSON.stringify(c)), moved = false, curT = t, pid = ev.pointerId;
    function mv(e) {
      if (e.pointerId !== pid) return;
      var d = (e.clientX - x0) / PPS;
      if (!moved && Math.abs(e.clientX - x0) < 3) return;
      moved = true;
      if (mode === 'm') {
        var ns = Math.max(0, o.start + d), s1 = snap(ns, c.id), s2 = snap(ns + len(c), c.id);
        if (s1.s != null) ns = s1.v; else if (s2.s != null) ns = s2.v - len(c);
        c.start = Math.max(0, ns); showSnap(s1.s != null ? s1.s : s2.s);
        var row = document.elementsFromPoint(e.clientX, e.clientY).filter(function (n) { return n.classList && n.classList.contains('tr'); })[0];
        var nt = row && trackOf(row.dataset.t);
        if (nt && nt !== curT && nt.kind === KIND_OF[c.type] && !nt.locked) { curT.clips.splice(curT.clips.indexOf(c), 1); nt.clips.push(c); curT = nt; row.appendChild(el); }
      } else if (mode === 'l') {
        var st = snap(o.start + d, c.id), nd = st.v - o.start; showSnap(st.s);
        if (c.type === 'video' || c.type === 'audio') { nd = Math.max(nd, -num(o.in, 0) / num(o.speed, 1)); nd = Math.min(nd, len(o) - 0.1);
          c.in = num(o.in, 0) + nd * num(o.speed, 1); c.start = o.start + nd; }
        else { nd = Math.min(nd, len(o) - 0.1); nd = Math.max(nd, -o.start); c.start = o.start + nd; c.dur = o.dur - nd; }
      } else {
        var en = snap(o.start + len(o) + d, c.id); showSnap(en.s);
        var nl = Math.max(0.1, en.v - o.start);
        if (c.type === 'video' || c.type === 'audio') c.out = Math.min(c.sdur || 1e9, num(o.in, 0) + nl * num(o.speed, 1));
        else c.dur = nl;
      }
      var cel = $('.clip[data-id="' + c.id + '"]', TRACKS);
      if (cel) { cel.style.left = (c.start * PPS) + 'px'; cel.style.width = Math.max(6, len(c) * PPS) + 'px'; }
      render(true);
    }
    function up(e) { if (e && e.pointerId !== pid) return; window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up); showSnap(null);
      if (moved) { commit(); drawAll(); } }
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up);
  }
  function rulerScrub(ev) {
    var r = SCROLL.getBoundingClientRect();
    function at(e) { seek((e.clientX - r.left + SCROLL.scrollLeft) / PPS, true); }
    at(ev); RULER.setPointerCapture(ev.pointerId);
    function mv(e) { at(e); } function up() { RULER.removeEventListener('pointermove', mv); RULER.removeEventListener('pointerup', up); }
    RULER.addEventListener('pointermove', mv); RULER.addEventListener('pointerup', up);
  }
  RULER.addEventListener('pointerdown', function (e) { e.preventDefault(); pause(); rulerScrub(e); });
  TRACKS.addEventListener('pointerdown', function (e) {
    if (e.target.closest('.clip')) return;
    var r = SCROLL.getBoundingClientRect(); pause(); SEL = null; $$('.clip.sel', TRACKS).forEach(function (x) { x.classList.remove('sel'); });
    seek((e.clientX - r.left + SCROLL.scrollLeft) / PPS, true); drawInsp();
  });
  // drag from the media bin (desktop) onto a track
  TRACKS.addEventListener('dragover', function (e) { e.preventDefault(); var row = e.target.closest('.tr'); $$('.tr.drop', TRACKS).forEach(function (x) { if (x !== row) x.classList.remove('drop'); }); if (row) row.classList.add('drop'); });
  TRACKS.addEventListener('dragleave', function (e) { if (!TRACKS.contains(e.relatedTarget)) $$('.tr.drop', TRACKS).forEach(function (x) { x.classList.remove('drop'); }); });
  TRACKS.addEventListener('drop', function (e) {
    e.preventDefault(); $$('.tr.drop', TRACKS).forEach(function (x) { x.classList.remove('drop'); });
    var src = e.dataTransfer.getData('text/mml-src'), row = e.target.closest('.tr'), r = SCROLL.getBoundingClientRect();
    if (e.dataTransfer.files && e.dataTransfer.files.length && !src) { uploadFiles(e.dataTransfer.files, (e.clientX - r.left + SCROLL.scrollLeft) / PPS); return; }
    if (!src) return;
    addMedia(src, { at: Math.max(0, (e.clientX - r.left + SCROLL.scrollLeft) / PPS), track: row && row.dataset.t, overlap: true, prompt: e.dataTransfer.getData('text/mml-prompt') });
  });
  SCROLL.addEventListener('scroll', function () { HEADS.scrollTop = SCROLL.scrollTop; });
  SCROLL.addEventListener('wheel', function (e) { if (e.ctrlKey) { e.preventDefault(); zoom(PPS * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX); } }, { passive: false });
  function zoom(v, cx) { var r = SCROLL.getBoundingClientRect(), ax = cx == null ? T * PPS - SCROLL.scrollLeft : cx - r.left, at = (SCROLL.scrollLeft + ax) / PPS;
    PPS = clamp(v, 10, 400); $('#ed-zoom').value = PPS; drawTracks(); drawRuler(); drawPH(); SCROLL.scrollLeft = at * PPS - ax; }
  $('#ed-zoom').oninput = function () { zoom(+this.value); };

  /* ══════════ PREVIEW COMPOSITOR ══════════ */
  var POOL = {}, SW = 640, SH = 360;
  function fitStage() {
    var r = WRAP.getBoundingClientRect(), ar = P.w / P.h, w = r.width - 20, h = r.height - 20;
    if (w / h > ar) w = h * ar; else h = w / ar;
    SW = Math.max(80, Math.floor(w)); SH = Math.max(45, Math.floor(h));
    STAGE.style.width = SW + 'px'; STAGE.style.height = SH + 'px'; STAGE.style.background = P.bg || '#000';
    render(true);
  }
  new ResizeObserver(fitStage).observe(WRAP);
  var FILT = { mono: 'grayscale(1)', sepia: 'sepia(.9)', warm: 'sepia(.25) saturate(1.2)', cool: 'hue-rotate(-12deg) saturate(1.1)', vivid: 'saturate(1.35) contrast(1.08)',
    fade: 'contrast(.85) brightness(1.04) saturate(.8)', noir: 'grayscale(1) contrast(1.35) brightness(.97)', blur: 'blur(3px)', sharpen: 'contrast(1.06)', film: 'contrast(1.05) sepia(.12)', vignette: '' };
  function fadeK(c, t) { var l = len(c), a = t - c.start, k = 1; if (num(c.fade_in, 0) > 0 && a < c.fade_in) k = a / c.fade_in; if (num(c.fade_out, 0) > 0 && a > l - c.fade_out) k = Math.min(k, (l - a) / c.fade_out); return clamp(k, 0, 1); }
  function el(c) {
    var e = POOL[c.id];
    if (e && e._src === (c.src || c.type)) return e;
    if (e) { try { e.pause && e.pause(); } catch (x) { } e.remove(); }
    if (c.type === 'video') { e = document.createElement('video'); e.preload = 'auto'; e.playsInline = true; e.setAttribute('playsinline', ''); e.src = url(c.src); }
    else if (c.type === 'audio') { e = document.createElement('audio'); e.preload = 'auto'; e.src = url(c.src); }
    else if (c.type === 'image') { e = document.createElement('img'); e.src = url(c.src); e.draggable = false; }
    else if (c.type === 'color') { e = document.createElement('div'); }
    else { e = document.createElement('div'); e.className = 'tx'; e.innerHTML = '<span></span>'; }
    e._src = c.src || c.type; if (c.type !== 'text') e.classList.add('ly');
    e.style.display = 'none'; STAGE.appendChild(e); POOL[c.id] = e;
    if (c.type === 'video') e.addEventListener('loadedmetadata', function () { if (!c.sw) { c.sw = e.videoWidth; c.sh = e.videoHeight; } render(true); });
    if (c.type === 'image') e.addEventListener('load', function () { if (!c.sw) { c.sw = e.naturalWidth; c.sh = e.naturalHeight; } render(true); });
    return e;
  }
  var MASTER = null, STALLED = false, STALL_T = 0;
  function render(force) {
    var live = {}, z = 1, t = T; MASTER = null; STALLED = false;
    var empty = !P.tracks.some(function (tr) { return tr.clips.length; });
    var em = $('.empty', STAGE);
    if (empty && !em) { em = document.createElement('div'); em.className = 'empty'; em.innerHTML = 'Add clips from the Library or generate with AI — drag them onto the timeline, or tap <b>+</b> on a card.'; STAGE.appendChild(em); }
    if (!empty && em) em.remove();
    for (var i = P.tracks.length - 1; i >= 0; i--) {           // bottom track first → higher z for upper tracks
      var tr = P.tracks[i];
      tr.clips.slice().sort(function (a, b) { return a.start - b.start; }).forEach(function (c) {
        var on = t >= c.start && t < end(c) && !(tr.hidden && tr.kind !== 'audio'), near = t >= c.start - 2.5 && t < end(c);
        if (!on && !near) return;
        var e = el(c); live[c.id] = 1;
        var srcT = num(c.in, 0) + (t - c.start) * num(c.speed, 1);
        if (c.type === 'video' || c.type === 'audio') {
          var muted = tr.muted || c.muted || !on;
          e.muted = muted; e.volume = clamp(num(c.volume, 1) * num(P.master, 1) * fadeK(c, t), 0, 1);
          var rate = clamp(num(c.speed, 1), 0.0625, 16);
          if (on && PLAYING) {
            if (e.error) { /* broken source — never let it hold the clock */ }
            else if (e.paused) { if (!e.seeking && Math.abs(e.currentTime - srcT) > 0.1) { try { e.currentTime = srcT; } catch (x) { } }   // pre-rolled → no seek, no stall
              if (e.playbackRate !== rate) e.playbackRate = rate; var pr = e.play(); if (pr && pr.catch) pr.catch(function () { }); }
            else if (!e.seeking) {   // drift: nudge the rate for small error, hard-seek only for a big jump (seeks flush the buffer → the old freeze loop)
              var d = e.currentTime - srcT, r = rate;
              if (Math.abs(d) > 0.75) { try { e.currentTime = srcT; } catch (x) { } }
              else if (Math.abs(d) > 0.04) r = rate * clamp(1 - d * 0.6, 0.9, 1.1);
              if (Math.abs(e.playbackRate - r) > 0.001) e.playbackRate = r;
              if (!MASTER || (c.type === 'audio' && !muted && MASTER.c.type !== 'audio')) MASTER = { e: e, c: c }; }
            if (!e.error && (e.seeking || e.readyState < 3) && !e.ended) STALLED = true; }
          else { if (!e.paused) e.pause(); if (e.playbackRate !== rate) e.playbackRate = rate;
            var want = on ? srcT : num(c.in, 0); if (!e.seeking && Math.abs(e.currentTime - want) > 0.04 && (force || on || !PLAYING || e.readyState >= 1)) { try { e.currentTime = want; } catch (x) { } } }
        }
        if (c.type === 'audio') return;
        if (!on) { e.style.display = 'none'; return; }
        e.style.display = ''; e.style.zIndex = z++;
        if (c.type === 'text') {
          var sp = e.firstChild; sp.textContent = c.text || '';
          var fs = num(c.size, 0.07) * SH;
          sp.style.fontSize = fs + 'px'; sp.style.color = c.color || '#fff';
          sp.style.background = c.box === false ? 'transparent' : hexA(c.box_color || '#000000', num(c.box_alpha, 0.45));
          sp.style.textShadow = c.shadow === false ? 'none' : '2px 2px 3px rgba(0,0,0,.6)';
          var pos = c.pos || 'center', y = { top: 0.08, center: 0.5, bottom: 0.92, lower: 0.78 }[pos];
          e.style.top = ((y + num(c.y, 0)) * 100) + '%'; e.style.transform = 'translate(' + (num(c.x, 0) * 100) + '%,' + (pos === 'top' ? '0' : pos === 'center' ? '-50%' : '-100%') + ')';
          e.style.opacity = fadeK(c, t); return;
        }
        var w0 = c.type === 'color' ? SW : (c.sw || 16), h0 = c.type === 'color' ? SH : (c.sh || 9), fit = c.fit || 'cover', s, w, h;
        if (fit === 'stretch' || c.type === 'color') { w = SW; h = SH; } else { s = fit === 'contain' ? Math.min(SW / w0, SH / h0) : Math.max(SW / w0, SH / h0); w = w0 * s; h = h0 * s; }
        var sc = num(c.scale, 1), kb = 1, kx = 0;
        if (c.type === 'image' && c.motion) { var pgs = clamp((t - c.start) / len(c), 0, 1);
          if (c.motion === 'zoomin') kb = 1 + 0.18 * pgs; else if (c.motion === 'zoomout') kb = 1.18 - 0.18 * pgs;
          else { kb = 1.15; kx = (c.motion === 'panright' ? -1 : 1) * (pgs - 0.5) * 0.13 * SW; } }
        e.style.width = w + 'px'; e.style.height = h + 'px';
        if (c.type === 'color') e.style.background = c.color || '#000';
        var rot = num(c.rotate, 0);
        e.style.transform = 'translate(-50%,-50%) translate(' + (num(c.x, 0) * SW + kx) + 'px,' + (num(c.y, 0) * SH) + 'px) rotate(' + rot + 'deg) scale(' + (sc * kb * (c.flip ? -1 : 1)) + ',' + (sc * kb) + ')';
        e.style.opacity = clamp(num(c.opacity, 1) * fadeK(c, t), 0, 1);
        var f = []; if (num(c.brightness, 0)) f.push('brightness(' + (1 + num(c.brightness, 0)) + ')'); if (num(c.contrast, 1) !== 1) f.push('contrast(' + c.contrast + ')');
        if (num(c.saturation, 1) !== 1) f.push('saturate(' + c.saturation + ')'); if (c.look && FILT[c.look]) f.push(FILT[c.look]);
        e.style.filter = f.join(' ');
      });
    }
    var now = performance.now(), idle = [];
    Object.keys(POOL).forEach(function (id) { var e = POOL[id]; if (live[id]) { e._idle = 0; return; }
      if (e.pause && !e.paused) e.pause(); e.style.display = 'none';
      if (!find(id)) { drop(id); return; }
      if (e.pause) { e._idle = e._idle || now; idle.push(id); } });
    // idle <video>/<audio> keep HTTP range connections open — the browser allows ~6 per host, so a pile of them starves the
    // clips that ARE playing (the freeze). Keep only the 4 most recent for quick scrub-back; release the rest.
    idle.sort(function (a, b) { return POOL[b]._idle - POOL[a]._idle; }).slice(4).forEach(drop);
  }
  function drop(id) { var e = POOL[id]; if (!e) return; if (e.pause) { try { e.pause(); e.removeAttribute('src'); e.load(); } catch (x) { } } e.remove(); delete POOL[id]; }
  function hexA(h, a) { var m = /^#?([0-9a-f]{6})$/i.exec(h || ''); if (!m) return 'rgba(0,0,0,' + a + ')'; var n = parseInt(m[1], 16); return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')'; }
  var raf = 0, t0 = 0, tStart = 0, lastNow = 0;
  function loop(now) { if (!PLAYING) return;
    // Clock: follow the playing media itself (audio first) so sound never gets re-seeked; while a clip is buffering, hold
    // the playhead instead of running ahead of it (wall-clock-only timing drifted → hard seek → re-buffer → freeze).
    if (now - lastNow > 250) { t0 = now; tStart = T; }   // background tab / main-thread hitch: resume, don't leap ahead
    lastNow = now; var wall = tStart + (now - t0) / 1000;
    if (STALLED) { if (!STALL_T) STALL_T = now; } else STALL_T = 0;
    if (STALLED && now - STALL_T < 4000) { t0 = now; tStart = T; }   // give up holding after 4s (dead source) and free-run
    else {
      var m = MASTER, mt = m && !m.e.paused && !m.e.seeking && m.e.readyState >= 3 ? m.c.start + (m.e.currentTime - num(m.c.in, 0)) / num(m.c.speed, 1) : null;
      if (mt != null && mt >= m.c.start && mt < end(m.c) && Math.abs(mt - wall) < 1) { if (mt > T) T = mt; t0 = now; tStart = T; }
      else T = Math.max(T, wall); }
    if (T >= total()) { T = total(); pause(); }
    drawPH(); render(); var x = T * PPS; if (x > SCROLL.scrollLeft + SCROLL.clientWidth - 30) SCROLL.scrollLeft = x - 60;
    raf = requestAnimationFrame(loop); }
  function play() { if (PLAYING) return; if (T >= total() - 0.05) T = 0; PLAYING = true; t0 = lastNow = performance.now(); tStart = T; $('#ed-play').innerHTML = mi('pause'); raf = requestAnimationFrame(loop); }
  function pause() { if (!PLAYING) return; PLAYING = false; cancelAnimationFrame(raf); $('#ed-play').innerHTML = mi('play'); render(true); drawPH(); }

  /* ══════════ INSPECTOR ══════════ */
  function openInsp() { if (window.innerWidth <= 1180) { ED.classList.add('insp-on'); scrim(true); } }
  function scrim(on) { var s = $('.scrim'); if (on && !s) { s = document.createElement('div'); s.className = 'scrim'; s.onclick = function () { ED.classList.remove('insp-on', 'bin-on'); scrim(false); }; document.body.appendChild(s); } if (!on && s) s.remove(); }
  function row(label, key, v, min, max, step, unit) {
    return '<label class="row"><span>' + label + '</span><input type="range" data-k="' + key + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + v + '"><em>' + (+v).toFixed(step < 0.1 ? 2 : 1) + (unit || '') + '</em></label>';
  }
  function sel(label, key, v, opts) { return '<label class="row"><span>' + label + '</span><select data-k="' + key + '" style="grid-column:span 2">' + opts.map(function (o) { return '<option value="' + o[0] + '"' + (String(v) === String(o[0]) ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select></label>'; }
  function drawInsp() {
    var f = SEL && find(SEL);
    if (!f) {   // project settings
      INSP.innerHTML = '<div class="insp"><h3>' + mi('sliders') + ' Edit settings</h3><div class="sub">' + P.w + '×' + P.h + ' · ' + P.fps + ' fps · ' + fmt(total(), 1) + '</div>' +
        '<div class="grp"><b>Canvas</b>' + sel('FPS', 'fps', P.fps, [[24, '24'], [25, '25'], [30, '30'], [60, '60']]) +
        '<label class="row"><span>Background</span><input type="color" data-k="bg" value="' + esc(P.bg || '#000000') + '"></label>' + row('Master vol.', 'master', num(P.master, 1), 0, 2, 0.05) + '</div>' +
        '<div class="grp"><b>Shortcuts</b><div class="dim" style="font-size:12px;line-height:1.7">Space play · S split · Del delete (Shift = ripple) · Ctrl+D duplicate · Ctrl+Z / Y undo / redo · ← → step a frame · Home / End · + / − zoom · drag clip edges to trim · drag between tracks</div></div>' +
        '<div class="grp"><b>AI</b><div class="ai"><button class="eb" data-x="ai-tab">' + mi('sparkle') + ' Open the AI panel</button><button class="eb" data-x="score">' + mi('music') + ' Score the whole edit</button></div></div></div>';
      wireInsp(P); return;
    }
    var c = f.c, h = '<div class="insp">';
    var title = { video: 'Video clip', image: 'Picture', audio: 'Audio', text: 'Title', color: 'Colour card' }[c.type];
    h += '<h3>' + mi({ video: 'video', image: 'image', audio: 'music', text: 'type', color: 'palette' }[c.type]) + ' ' + title + '</h3><div class="sub">' + esc(c.name || '') + ' · ' + fmt(c.start, 1) + ' → ' + fmt(end(c), 1) + ' (' + len(c).toFixed(2) + 's)</div>';
    if (c.type === 'text') {
      h += '<div class="grp"><b>Text</b><textarea data-k="text">' + esc(c.text) + '</textarea>' + row('Size', 'size', num(c.size, 0.07), 0.02, 0.3, 0.005) +
        '<label class="row"><span>Colour</span><input type="color" data-k="color" value="' + esc(c.color || '#ffffff') + '"></label>' +
        sel('Position', 'pos', c.pos || 'center', [['top', 'Top'], ['center', 'Centre'], ['lower', 'Lower third'], ['bottom', 'Bottom']]) +
        row('Nudge X', 'x', num(c.x, 0), -0.5, 0.5, 0.01) + row('Nudge Y', 'y', num(c.y, 0), -0.5, 0.5, 0.01) +
        sel('Box', 'box', c.box === false ? 0 : 1, [[1, 'On'], [0, 'Off']]) + '<label class="row"><span>Box colour</span><input type="color" data-k="box_color" value="' + esc(c.box_color || '#000000') + '"></label>' +
        row('Box opacity', 'box_alpha', num(c.box_alpha, 0.45), 0, 1, 0.05) + '</div>';
    }
    h += '<div class="grp"><b>Timing</b>' + row('Start', 'start', c.start, 0, Math.max(60, total() + 10), 0.01, 's');
    if (c.type === 'video' || c.type === 'audio') h += row('In', 'in', num(c.in, 0), 0, c.sdur || 60, 0.01, 's') + row('Out', 'out', num(c.out, 1), 0.05, c.sdur || 60, 0.01, 's') + row('Speed', 'speed', num(c.speed, 1), 0.25, 4, 0.05, '×');
    else h += row('Duration', 'dur', num(c.dur, 3), 0.1, 60, 0.05, 's');
    h += row('Fade in', 'fade_in', num(c.fade_in, 0), 0, Math.min(5, len(c) / 2), 0.05, 's') + row('Fade out', 'fade_out', num(c.fade_out, 0), 0, Math.min(5, len(c) / 2), 0.05, 's') + '</div>';
    if (c.type === 'video' || c.type === 'audio') h += '<div class="grp"><b>Sound</b>' + row('Volume', 'volume', num(c.volume, 1), 0, 2, 0.05) + sel('Muted', 'muted', c.muted ? 1 : 0, [[0, 'No'], [1, 'Yes']]) + '</div>';
    if (c.type === 'video' || c.type === 'image' || c.type === 'color') {
      h += '<div class="grp"><b>Frame</b>' + (c.type === 'color' ? '<label class="row"><span>Colour</span><input type="color" data-k="color" value="' + esc(c.color || '#111111') + '"></label>' :
        sel('Fit', 'fit', c.fit || 'cover', [['cover', 'Fill (crop)'], ['contain', 'Fit (bars)'], ['stretch', 'Stretch']]) + row('Scale', 'scale', num(c.scale, 1), 0.1, 3, 0.01) +
        row('Position X', 'x', num(c.x, 0), -1, 1, 0.01) + row('Position Y', 'y', num(c.y, 0), -1, 1, 0.01) + sel('Rotate', 'rotate', num(c.rotate, 0), [[0, '0°'], [90, '90°'], [180, '180°'], [270, '270°']]) +
        sel('Mirror', 'flip', c.flip ? 1 : 0, [[0, 'No'], [1, 'Yes']])) + row('Opacity', 'opacity', num(c.opacity, 1), 0, 1, 0.01) +
        (c.type === 'image' ? sel('Motion', 'motion', c.motion || '', [['', 'None'], ['zoomin', 'Slow zoom in'], ['zoomout', 'Slow zoom out'], ['panleft', 'Pan left'], ['panright', 'Pan right']]) : '') + '</div>';
      if (c.type !== 'color') h += '<div class="grp"><b>Colour</b>' + row('Brightness', 'brightness', num(c.brightness, 0), -0.5, 0.5, 0.01) + row('Contrast', 'contrast', num(c.contrast, 1), 0.3, 2, 0.01) +
        row('Saturation', 'saturation', num(c.saturation, 1), 0, 2.5, 0.01) +
        sel('Look', 'look', c.look || 'none', [['none', 'None'], ['vivid', 'Vivid'], ['warm', 'Warm'], ['cool', 'Cool'], ['fade', 'Faded'], ['film', 'Film grain'], ['mono', 'Mono'], ['noir', 'Noir'], ['sepia', 'Sepia'], ['vignette', 'Vignette'], ['blur', 'Blur'], ['sharpen', 'Sharpen']]) + '</div>';
    }
    // AI tools — role words only, never engine names
    h += '<div class="grp"><b>AI tools</b><textarea id="ai-cp" placeholder="What should change? (optional for some tools)">' + esc(c.prompt || '') + '</textarea><div class="ai" style="margin-top:6px">';
    if (c.type === 'video') h += '<button class="eb" data-ai="extend">' + mi('forward') + ' Extend this shot</button><button class="eb" data-ai="regen">' + mi('refresh') + ' Regenerate this shot</button>' +
      '<button class="eb" data-ai="restyle">' + mi('wand') + ' Restyle this shot</button><button class="eb" data-ai="still">' + mi('camera') + ' Freeze frame at playhead</button>';
    if (c.type === 'image') h += '<button class="eb" data-ai="animate">' + mi('video') + ' Animate this picture</button><button class="eb" data-ai="editimg">' + mi('wand') + ' Edit this picture</button>';
    if (c.type === 'audio') h += '<button class="eb" data-ai="remix">' + mi('music') + ' Remix / cover this audio</button>';
    if (c.type !== 'text' && c.type !== 'color') h += '<button class="eb" data-ai="asref">' + mi('attach') + ' Use as reference in the AI panel</button>';
    if (c.type === 'text') h += '<div class="dim" style="font-size:12px">Titles render with the edit — style them above.</div>';
    h += '</div></div>';
    h += '<div class="grp"><b>Clip</b><div class="row2"><button class="eb" data-x="split">' + mi('scissors') + ' Split</button><button class="eb" data-x="dup">' + mi('copy') + ' Duplicate</button>' +
      '<button class="eb" data-x="xfade">' + mi('layers') + ' Crossfade</button>' + (c.type === 'video' && c.audio !== false ? '<button class="eb" data-x="detach">' + mi('music') + ' Detach audio</button>' : '<span></span>') +
      '<button class="eb" data-x="del">' + mi('trash') + ' Delete</button><button class="eb" data-x="ripple">' + mi('trash') + ' Ripple delete</button></div></div></div>';
    INSP.innerHTML = h; wireInsp(c);
  }
  function wireInsp(o) {
    var isP = o === P;
    $$('[data-k]', INSP).forEach(function (inp) {
      var k = inp.dataset.k;
      function apply(fin) {
        var v = inp.type === 'range' || inp.type === 'number' ? parseFloat(inp.value) : inp.value;
        if (k === 'muted' || k === 'flip' || k === 'box') v = inp.value === '1';
        if (k === 'rotate' || k === 'fps') v = parseInt(inp.value, 10);
        if (k === 'out' && !isP) v = Math.max(v, num(o.in, 0) + 0.05);
        if (k === 'in' && !isP) v = Math.min(v, num(o.out, 1) - 0.05);
        o[k] = v;
        var em = inp.parentNode.querySelector('em'); if (em) em.textContent = (+v).toFixed(inp.step < 0.1 ? 2 : 1) + (k === 'speed' ? '×' : /start|in|out|dur|fade/.test(k) ? 's' : '');
        if (isP && k === 'bg') STAGE.style.background = v;
        if (fin) { commit(); drawTracks(); drawPH(); if (k === 'fps') drawInsp(); } else { var ce = !isP && $('.clip[data-id="' + o.id + '"]', TRACKS); if (ce) { ce.style.left = (o.start * PPS) + 'px'; ce.style.width = Math.max(6, len(o) * PPS) + 'px'; } }
        render(true);
      }
      inp.addEventListener('input', function () { apply(false); });
      inp.addEventListener('change', function () { apply(true); });
    });
    $$('[data-x]', INSP).forEach(function (b) { b.onclick = function () { var x = b.dataset.x;
      if (x === 'split') split(); else if (x === 'dup') dup(); else if (x === 'del') del(false); else if (x === 'ripple') del(true);
      else if (x === 'detach') detachAudio(); else if (x === 'xfade') crossfade(); else if (x === 'ai-tab') { binTab('ai'); ED.classList.add('bin-on'); }
      else if (x === 'score') aiScore(); }; });
    $$('[data-ai]', INSP).forEach(function (b) { b.onclick = function () { clipAI(b.dataset.ai, o, ($('#ai-cp') || {}).value || ''); }; });
    var cp = $('#ai-cp'); if (cp) cp.onchange = function () { o.prompt = cp.value; commit(); };
  }

  /* ══════════ MEDIA BIN ══════════ */
  var LIBK = '', LIBOFF = 0;
  function binTab(t) { $$('.ed-bin .tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.t === t); }); $$('.ed-bin .pane').forEach(function (p) { p.hidden = p.dataset.p !== t; }); if (t === 'ai') drawJobs(); }
  $$('.ed-bin .tabs button').forEach(function (b) { b.onclick = function () { binTab(b.dataset.t); }; });
  $$('.ed-bin .chips button').forEach(function (b) { b.onclick = function () { $$('.ed-bin .chips button').forEach(function (x) { x.classList.toggle('on', x === b); }); LIBK = b.dataset.k; LIBOFF = 0; loadLib(); }; });
  function loadLib(more) {
    var g = $('#ed-lib'); if (!more) { LIBOFF = 0; g.innerHTML = '<div class="dim">loading…</div>'; }
    api('/api/library?limit=40&offset=' + LIBOFF + '&kind=' + LIBK).then(function (d) {
      if (!more) g.innerHTML = ''; var mb = $('.more', g); if (mb) mb.remove();
      (d.items || []).forEach(function (it) { g.appendChild(card('lib:' + it.name, it.kind, it.prompt || it.name, it.thumb ? B + '/thumb/' + encodeURIComponent(it.name) : null, it.prompt)); });
      LIBOFF += (d.items || []).length;
      if (!g.children.length) g.innerHTML = '<div class="dim">Your library is empty — generate something in the lab or the AI tab.</div>';
      if (LIBOFF < (d.total || 0)) { var b = document.createElement('button'); b.className = 'eb more'; b.textContent = 'More'; b.onclick = function () { loadLib(true); }; g.appendChild(b); }
    }).catch(function () { g.innerHTML = '<div class="dim">couldn\'t load the library</div>'; });
  }
  function card(src, kind, label, thumb, prompt) {
    var d = document.createElement('div'); d.className = 'mi-card'; d.draggable = true; d.title = label || '';
    d.innerHTML = (thumb ? '<img src="' + thumb + '" loading="lazy" alt="">' : '<div class="au">' + mi(kind === 'audio' ? 'music' : 'note', 'lg') + '<span>' + esc(String(label).slice(0, 60)) + '</span></div>') +
      '<span class="k">' + mi(kind === 'video' ? 'video' : kind === 'image' ? 'image' : 'music', 'sm') + '</span><div class="nm">' + esc(String(label).slice(0, 80)) + '</div><button class="add" title="Add at the playhead">' + mi('plus', 'sm') + '</button>';
    d.addEventListener('dragstart', function (e) { e.dataTransfer.setData('text/mml-src', src); e.dataTransfer.setData('text/mml-prompt', prompt || ''); e.dataTransfer.effectAllowed = 'copy'; });
    d.querySelector('.add').onclick = function (e) { e.stopPropagation(); addMedia(src, { prompt: prompt }).then(function (c) { if (c) { toast('Added at ' + fmt(c.start, 1)); if (window.innerWidth <= 760) { ED.classList.remove('bin-on'); scrim(false); } } }); };
    return d;
  }
  function uploadFiles(files, at) {
    [].slice.call(files).forEach(function (f, i) {
      var fd = new FormData(); fd.append('file', f, f.name); toast('Uploading ' + f.name + '…');
      fetch(B + '/api/upload', { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
        if (j.error) { toast(j.error, 1); return; }
        addMedia('ref:' + j.name, { at: at != null ? at : T, name: f.name });
      }).catch(function () { toast('Upload failed', 1); });
    });
  }
  $('#ed-file').onchange = function () { uploadFiles(this.files); this.value = ''; };

  /* ══════════ AI ══════════ */
  var ROLES = { video: { label: 'Video', model: 'h3' }, image: { label: 'Image', model: 'qimg' }, music: { label: 'Music', model: 'ace' }, song: { label: 'Song', model: 'music3' } };
  var ROLE = 'video', AIREFS = [], JOBS = {}, BUSY = {};
  api('/api/skills').then(function (d) { if (d && d.roles) { ['video', 'image', 'music', 'song'].forEach(function (r) { if (d.roles[r]) ROLES[r] = { label: d.roles[r].label, model: d.roles[r].model }; }); drawRoles(); } });
  function drawRoles() {
    $('#ai-role').innerHTML = ['video', 'image', 'music', 'song'].map(function (r) { return '<button data-r="' + r + '" class="' + (r === ROLE ? 'on' : '') + '">' + esc(ROLES[r].label) + '</button>'; }).join('');
    $$('#ai-role button').forEach(function (b) { b.onclick = function () { ROLE = b.dataset.r; drawRoles(); }; });
    var o = '';
    if (ROLE === 'music' || ROLE === 'song') o += '<label>Length <input type="number" id="ai-len" min="5" max="240" value="' + Math.max(10, Math.min(240, Math.round(total() || 30))) + '"> s</label>';
    if (AIREFS.length) o += '<span>References:</span>' + AIREFS.map(function (r, i) { return '<button class="eb" data-rr="' + i + '" title="Remove">' + mi(r.kind === 'image' ? 'image' : r.kind === 'audio' ? 'music' : 'video', 'sm') + ' ' + esc(r.label) + ' ×</button>'; }).join('');
    $('#ai-opts').innerHTML = o;
    $$('#ai-opts [data-rr]').forEach(function (b) { b.onclick = function () { AIREFS.splice(+b.dataset.rr, 1); drawRoles(); }; });
  }
  drawRoles();
  $('#ai-go').onclick = function () {
    var p = $('#ai-prompt').value.trim(); if (!p && !AIREFS.length) { toast('Describe what to generate'); return; }
    var lenS = $('#ai-len') ? +$('#ai-len').value : 0;
    gen({ role: ROLE, prompt: p + (lenS ? ' · ' + lenS + 's' : ''), refs: AIREFS.map(function (r) { return r.name; }), label: ROLES[ROLE].label + ' · ' + (p || 'from reference').slice(0, 40),
      place: { mode: 'at', at: T, kind: ROLE === 'image' || ROLE === 'video' ? 'video' : 'audio', track: ROLE === 'music' || ROLE === 'song' ? musicTrack() : null } });
    AIREFS = []; drawRoles();
  };
  function musicTrack() { var t = P.tracks.filter(function (x) { return x.kind === 'audio'; }); return (t[t.length - 1] || {}).id; }
  function frameRef(c, at) { return api('/api/editor/frame', { src: c.src, t: at }).then(function (r) { if (r.error) throw r.error; return r; }); }
  function cutRef(c) { return api('/api/editor/cut', { src: c.src, in: num(c.in, 0), out: num(c.out, 0) }).then(function (r) { if (r.error) throw r.error; return r; }); }
  function clipAI(kind, c, prompt) {
    prompt = (prompt || '').trim(); var srcT = num(c.in, 0) + clamp(T - c.start, 0, len(c)) * num(c.speed, 1), l = len(c);
    var fail = function (e) { toast(String(e && e.error || e), 1); delete BUSY[c.id]; drawTracks(); };
    if (kind === 'still') { if (T < c.start || T > end(c)) { toast('Move the playhead over this clip first'); return; }
      frameRef(c, srcT).then(function (r) { var tr = P.tracks.filter(function (x) { return x.kind === 'video'; })[0]; addMedia('ref:' + r.name, { at: T, track: tr.id, dur: 2, overlap: true, name: 'freeze frame' }); }).catch(fail); return; }
    if (kind === 'asref') {
      var p = c.type === 'video' ? (T >= c.start && T <= end(c) ? frameRef(c, srcT) : frameRef(c, num(c.in, 0))) : c.type === 'image' ? frameRef(c, 0) : cutRef(c);
      p.then(function (r) { AIREFS.push({ name: r.name, kind: r.kind, label: (r.label || r.name).slice(0, 18) }); binTab('ai'); drawRoles(); ED.classList.add('bin-on'); toast('Attached — write a prompt in the AI panel'); }).catch(fail); return; }
    BUSY[c.id] = 1; drawTracks();
    if (kind === 'extend') frameRef(c, num(c.out, 1) - 0.05).then(function (r) {
      gen({ role: 'video', prompt: prompt || c.prompt || 'continue the shot naturally, same scene, same camera', refs: [r.name], label: 'Extend · ' + (c.name || ''),
        place: { mode: 'after', clip: c.id }, busy: c.id }); }).catch(fail);
    else if (kind === 'regen') frameRef(c, num(c.in, 0)).then(function (r) {
      gen({ role: 'video', prompt: prompt || c.prompt || 'the same shot, re-imagined', refs: [r.name], label: 'Regenerate · ' + (c.name || ''), place: { mode: 'replace', clip: c.id, keep: l }, busy: c.id }); }).catch(fail);
    else if (kind === 'restyle') cutRef(c).then(function (r) {
      gen({ role: 'video', prompt: prompt || 'restyle this shot', refs: [r.name], label: 'Restyle · ' + (c.name || ''), place: { mode: 'replace', clip: c.id, keep: l }, busy: c.id }); }).catch(fail);
    else if (kind === 'animate') frameRef(c, 0).then(function (r) {
      gen({ role: 'video', prompt: prompt || c.prompt || 'bring this picture to life with gentle natural motion', refs: [r.name], label: 'Animate · ' + (c.name || ''), place: { mode: 'replace', clip: c.id }, busy: c.id }); }).catch(fail);
    else if (kind === 'editimg') { if (!prompt) { delete BUSY[c.id]; drawTracks(); toast('Say what to change in the box above'); return; }
      frameRef(c, 0).then(function (r) { gen({ role: 'image', prompt: prompt, refs: [r.name], label: 'Edit picture · ' + (c.name || ''), place: { mode: 'replace', clip: c.id, keep: l }, busy: c.id }); }).catch(fail); }
    else if (kind === 'remix') cutRef(c).then(function (r) {
      gen({ role: 'music', prompt: (prompt || c.prompt || 'a fresh cover of this track') + ' · ' + Math.round(l) + 's', refs: [r.name], label: 'Remix · ' + (c.name || ''), place: { mode: 'replace', clip: c.id }, busy: c.id }); }).catch(fail);
  }
  function aiScore() {
    var tl = Math.round(total()); if (tl < 3) { toast('Add some clips first — the score follows the edit length'); return; }
    modal('<h3>' + mi('music') + ' Score the edit</h3><div class="dim">One track the length of your edit (' + tl + 's), placed on the music track from the start.</div>' +
      '<div class="opt"><span>Style</span><input id="sc-p" value="cinematic score that builds and resolves, emotional, wide"></div>' +
      '<div class="opt"><span>Kind</span><select id="sc-r"><option value="music">' + esc(ROLES.music.label) + ' (instrumental)</option><option value="song">' + esc(ROLES.song.label) + ' (with vocals)</option></select></div>' +
      '<div class="acts"><button class="eb" data-m="x">Cancel</button><button class="eb pri" data-m="go">' + mi('sparkle') + ' Generate</button></div>', function (box) {
      $('[data-m=go]', box).onclick = function () { var r = $('#sc-r').value; closeModal();
        gen({ role: r, prompt: $('#sc-p').value + ' · ' + tl + 's', refs: [], label: 'Score · ' + tl + 's', place: { mode: 'at', at: 0, kind: 'audio', track: musicTrack(), trim: tl } }); };
    });
  }
  function aiFill() {
    var v1 = P.tracks.filter(function (t) { return t.kind === 'video'; }).slice(-1)[0]; if (!v1) return;
    var cs = v1.clips.slice().sort(function (a, b) { return a.start - b.start; }), prev = null, next = null;
    cs.forEach(function (c) { if (end(c) <= T + 1e-3) prev = c; if (!next && c.start > T) next = c; });
    var a = prev ? end(prev) : 0, b = next ? next.start : a + 5;
    if (cs.some(function (c) { return T >= c.start && T < end(c); })) { toast('The playhead is on a clip — put it in an empty gap on ' + v1.name); return; }
    modal('<h3>' + mi('wand') + ' Fill the gap</h3><div class="dim">A new shot for ' + fmt(a, 1) + ' → ' + fmt(b, 1) + ' (' + (b - a).toFixed(1) + 's)' + (prev ? ', continuing from the clip before it' : '') + '.</div>' +
      '<div class="opt"><span>Shot</span><input id="fg-p" placeholder="what happens in this shot"></div><div class="acts"><button class="eb" data-m="x">Cancel</button><button class="eb pri" data-m="go">' + mi('sparkle') + ' Generate</button></div>', function (box) {
      $('[data-m=go]', box).onclick = function () { var p = $('#fg-p').value.trim() || (prev && prev.prompt) || 'a natural continuation of the scene'; closeModal();
        var go = function (refs) { gen({ role: 'video', prompt: p, refs: refs, label: 'Fill gap · ' + p.slice(0, 30), place: { mode: 'at', at: a, kind: 'video', track: v1.id, trim: b - a } }); };
        if (prev && prev.type === 'video') frameRef(prev, num(prev.out, 1) - 0.05).then(function (r) { go([r.name]); }).catch(function () { go([]); });
        else if (prev && prev.type === 'image') frameRef(prev, 0).then(function (r) { go([r.name]); }).catch(function () { go([]); }); else go([]); };
    });
  }
  function aiVoice() {
    api('/api/tts/voices').then(function (v) {
      var vs = (v.voices || []).map(function (x) { return '<option value="' + esc(x.id) + '"' + (x.id === v.default ? ' selected' : '') + '>' + esc(x.label) + '</option>'; }).join('');
      if (v.available === false) { toast('The voice engine isn\'t installed on this lab', 1); return; }
      modal('<h3>' + mi('mic') + ' Voiceover</h3><div class="dim">Each sentence becomes a line on an audio track from the playhead.</div><textarea id="vo-t" rows="5" placeholder="Type the narration…"></textarea>' +
        '<div class="opt"><span>Voice</span><select id="vo-v">' + vs + '</select></div><div class="acts"><button class="eb" data-m="x">Cancel</button><button class="eb pri" data-m="go">' + mi('mic') + ' Create</button></div>', function (box) {
        $('[data-m=go]', box).onclick = function () {
          var txt = $('#vo-t').value.trim(), voice = $('#vo-v').value; if (!txt) return; closeModal();
          var lines = txt.match(/[^.!?\n]+[.!?]*/g).map(function (s) { return s.trim(); }).filter(Boolean), at = T, tr = P.tracks.filter(function (t) { return t.kind === 'audio'; })[0];
          var jid = 'vo' + uid(); JOBS[jid] = { label: 'Voiceover · ' + lines.length + ' lines', status: 'running', pct: 0 }; drawJobs(); binTab('ai');
          (function next(i) {
            if (i >= lines.length) { JOBS[jid].status = 'done'; JOBS[jid].pct = 100; drawJobs(); return; }
            fetch(B + '/api/tts?voice=' + encodeURIComponent(voice) + '&text=' + encodeURIComponent(lines[i]), { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw 'voice failed'; return r.blob(); })
              .then(function (b) { var fd = new FormData(); fd.append('file', b, 'voiceover_' + (i + 1) + '.wav'); return fetch(B + '/api/upload', { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.json(); }); })
              .then(function (j) { if (j.error) throw j.error; return addMedia('ref:' + j.name, { at: at, track: tr && tr.id, overlap: true, name: lines[i].slice(0, 40) }); })
              .then(function (c) { if (c) at = end(c) + 0.25; JOBS[jid].pct = Math.round((i + 1) / lines.length * 100); drawJobs(); next(i + 1); })
              .catch(function (e) { JOBS[jid].status = 'error'; JOBS[jid].error = String(e); drawJobs(); toast(String(e), 1); });
          })(0);
        };
      });
    });
  }
  function gen(o) {
    var role = ROLES[o.role] || ROLES.video;
    var tmp = 'p' + uid(); JOBS[tmp] = { label: o.label, status: 'starting', pct: 0 }; drawJobs(); binTab('ai');
    api('/api/generate', { model: role.model, prompt: o.prompt, refs: o.refs || [] }).then(function (j) {
      delete JOBS[tmp];
      if (j.error) { toast(j.error, 1); if (o.busy) { delete BUSY[o.busy]; drawTracks(); } drawJobs(); return; }
      JOBS[j.id] = { label: o.label, status: j.status, pct: 0, place: o.place, busy: o.busy }; drawJobs(); poll(j.id);
      toast(o.label + ' — on its way');
    }).catch(function () { delete JOBS[tmp]; toast('The lab didn\'t answer', 1); drawJobs(); });
  }
  function poll(id) {
    api('/api/jobs/' + id).then(function (j) {
      var J = JOBS[id]; if (!J) return;
      J.status = j.status; J.stage = j.stage; J.pct = j.progress && j.progress.pct != null ? j.progress.pct : J.pct; J.error = j.error;
      drawJobs();
      if (j.status === 'queued' || j.status === 'running') { setTimeout(function () { poll(id); }, 2500); return; }
      if (J.busy) { delete BUSY[J.busy]; }
      if (j.status !== 'done') { toast(J.label + ' — ' + (j.error || j.status), 1); drawTracks(); return; }
      var f = (j.files || []).filter(function (n) { return /\.(mp4|mov|webm|png|jpe?g|webp|mp3|wav|flac|ogg|m4a)$/i.test(n); })[0];
      if (!f) { toast(J.label + ' finished without a media file', 1); drawTracks(); return; }
      land('lib:' + String(f).split('/').pop(), J.place || {}, j.prompt);
      loadLib();
    }).catch(function () { setTimeout(function () { poll(id); }, 5000); });
  }
  function land(src, pl, prompt) {
    var tgt = pl.clip && find(pl.clip);
    if (pl.mode === 'replace' && tgt) {
      probe(src).then(function (m) {
        var c = tgt.c, keep = pl.keep, type = m.kind === 'image' ? 'image' : m.kind === 'audio' ? 'audio' : 'video';
        if (KIND_OF[type] !== tgt.t.kind) { addMedia(src, { at: c.start, prompt: prompt }); return; }
        c.type = type; c.src = src; c.sw = m.w; c.sh = m.h; c.sdur = m.dur; c.audio = m.audio; c.prompt = prompt || c.prompt; c.name = (c.name || '').replace(/^(.*?)( · AI)?$/, '$1 · AI');
        if (type === 'image') { c.dur = keep || c.dur || 4; delete c.in; delete c.out; }
        else { c.in = 0; c.out = keep ? Math.min(m.dur || keep, keep * num(c.speed, 1)) : (m.dur || 4); delete c.dur; }
        delete META[src]; commit(); drawAll(); toast('Replaced on the timeline');
      }); return;
    }
    if (pl.mode === 'after' && tgt) { addMedia(src, { at: end(tgt.c), track: tgt.t.id, ripple: true, prompt: prompt }).then(function () { toast('Added after the shot'); }); return; }
    addMedia(src, { at: pl.at != null ? pl.at : T, track: pl.track, overlap: true, prompt: prompt, dur: pl.trim }).then(function (c) {
      if (c && pl.trim && (c.type === 'audio' || c.type === 'video')) { c.out = Math.min(c.out, num(c.in, 0) + pl.trim); if (c.type === 'audio') c.fade_out = Math.min(2, len(c) / 4); commit(); drawAll(); }
      if (c) toast('Landed on ' + ((trackOf(pl.track) || {}).name || 'the timeline'));
    });
  }
  function drawJobs() {
    var ks = Object.keys(JOBS), box = $('#ai-jobs'); if (!box) return;
    box.innerHTML = ks.length ? ks.reverse().map(function (k) { var j = JOBS[k];
      return '<div class="job"><b>' + esc(j.label) + '</b><span class="' + (j.status === 'error' ? 'err' : 'dim') + '">' + esc(j.status === 'error' ? (j.error || 'failed') : (j.stage || j.status)) +
        (j.pct ? ' · ' + Math.round(j.pct) + '%' : '') + '</span><div class="bar"><i style="width:' + (j.status === 'done' ? 100 : j.pct || (j.status === 'running' ? 8 : 2)) + '%"></i></div></div>'; }).join('') : '<div class="dim">nothing running</div>';
    var run = ks.filter(function (k) { return /running|queued|starting/.test(JOBS[k].status); }).length;
    var t = $('.ed-bin .tabs [data-t=ai]'); if (t) t.textContent = run ? 'AI · ' + run : 'AI';
  }

  /* ══════════ EXPORT + PROJECTS ══════════ */
  function modal(html, wire) { var m = $('#ed-modal'); m.innerHTML = '<div class="box">' + html + '</div>'; m.hidden = false;
    m.onclick = function (e) { if (e.target === m) closeModal(); }; $$('[data-m=x]', m).forEach(function (b) { b.onclick = closeModal; }); if (wire) wire(m); }
  function closeModal() { var m = $('#ed-modal'); m.hidden = true; m.innerHTML = ''; }
  var EXP = null;
  function exportDlg() {
    if (total() < 0.2) { toast('Nothing to export yet'); return; }
    pause(); save();
    var f = SEL && find(SEL);
    modal('<h3>' + mi('upload') + ' Export</h3><div class="dim">' + esc(P.name) + ' · ' + fmt(total(), 1) + '</div>' +
      '<div class="opt"><span>Quality</span><select id="x-q"><option value="1">Project · ' + P.w + '×' + P.h + '</option><option value="0.5">Half size (fast preview)</option>' +
      (Math.max(P.w, P.h) < 1920 ? '<option value="1.5">1.5× sharper</option>' : '') + '</select></div>' +
      '<div class="opt"><span>Range</span><select id="x-r"><option value="all">Whole edit</option>' + (f ? '<option value="sel">Selected clip only</option>' : '') + '<option value="ph">Playhead → end</option></select></div>' +
      '<div class="opt"><span>Send to</span><select id="x-t"><option value="library">Library</option><option value="ref">Lab attachment (use it in the next request)</option></select></div>' +
      '<div class="acts"><button class="eb" data-m="x">Close</button><button class="eb pri" data-m="go">' + mi('upload') + ' Export</button></div><div id="x-st"></div>', function (box) {
      $('[data-m=go]', box).onclick = function () {
        var s = +$('#x-q').value, r = $('#x-r').value, pj = JSON.parse(JSON.stringify(P));
        pj.w = Math.round(P.w * s / 2) * 2; pj.h = Math.round(P.h * s / 2) * 2;
        var rng = r === 'sel' && f ? [f.c.start, end(f.c)] : r === 'ph' ? [T, total()] : null;
        $('[data-m=go]', box).disabled = true;
        api('/api/editor/render', { project: pj, range: rng, target: $('#x-t').value }).then(function (j) {
          if (j.error) { $('#x-st').innerHTML = '<p class="err" style="color:#ff8f8f">' + esc(j.error) + '</p>'; $('[data-m=go]', box).disabled = false; return; }
          EXP = j.id; xpoll(j.id, box);
        });
      };
    });
  }
  function xpoll(id, box) {
    api('/api/editor/render/' + id).then(function (j) {
      var st = $('#x-st', box); if (!st) return;
      if (j.status === 'running') { st.innerHTML = '<div class="big"><i style="width:' + (j.pct || 2) + '%"></i></div><div class="dim">' + esc(j.stage) + ' · ' + Math.round(j.pct || 0) + '% <button class="eb" id="x-c" style="margin-left:8px">Cancel</button></div>';
        $('#x-c', st).onclick = function () { api('/api/editor/render/' + id + '/cancel', {}); }; setTimeout(function () { xpoll(id, box); }, 900); return; }
      if (j.status !== 'done') { st.innerHTML = '<p style="color:#ff8f8f">' + esc(j.error || j.status) + '</p>'; return; }
      var u = j.ref ? B + '/refs/' + encodeURIComponent(j.ref.name) : B + '/media/' + encodeURIComponent(j.name);
      st.innerHTML = '<div class="dim">' + (j.ref ? 'Saved as a lab attachment — it\'s ready in the composer.' : 'Saved to your library.') + '</div><video src="' + u + '" controls playsinline></video>' +
        '<div class="acts"><a class="eb" href="' + u + (j.ref ? '' : '?dl=1') + '" download>' + mi('download') + ' Download</a>' + (j.ref ? '' : '<button class="eb" id="x-add">' + mi('plus') + ' Add to timeline</button>') +
        '<button class="eb pri" id="x-lab">' + mi('lab') + ' Back to the lab</button></div>';
      var xa = $('#x-add', st); if (xa) xa.onclick = function () { closeModal(); addMedia('lib:' + j.name, { at: total() }); };
      $('#x-lab', st).onclick = function () { closeEditor(j.ref ? { ref: j.ref } : { lib: j.name }); };
      loadLib();
    });
  }
  function projectsDlg() {
    api('/api/editor/projects').then(function (d) {
      var ps = d.projects || [];
      modal('<h3>' + mi('folder') + ' Your edits</h3><button class="eb pri" id="pj-new">' + mi('plus') + ' New edit</button>' +
        (ps.length ? ps.map(function (p) { return '<div class="prow" data-id="' + p.id + '">' + mi('film') + '<div class="m"><b>' + esc(p.name) + '</b><small>' + p.clips + ' clips · ' + fmt(p.dur) + ' · ' +
          p.w + '×' + p.h + ' · ' + new Date(p.updated * 1000).toLocaleString() + '</small></div><button class="eb ic" data-del="' + p.id + '" title="Delete">' + mi('trash', 'sm') + '</button></div>'; }).join('') :
          '<p class="dim">No saved edits yet — they save automatically as you work.</p>') + '<div class="acts"><button class="eb" data-m="x">Close</button></div>', function (box) {
        $('#pj-new', box).onclick = function () { closeModal(); openProject(null); };
        $$('.prow', box).forEach(function (r) { r.onclick = function (e) { if (e.target.closest('[data-del]')) return; closeModal(); openProject(r.dataset.id); }; });
        $$('[data-del]', box).forEach(function (b) { b.onclick = function () { if (!confirm('Delete this edit? (It moves to the lab trash.)')) return;
          api('/api/editor/project/' + b.dataset.del + '/delete', {}).then(function () { if (P.id === b.dataset.del) openProject(null); projectsDlg(); }); }; });
      });
    });
  }
  function openProject(id) {
    pause(); Object.keys(POOL).forEach(function (k) { POOL[k].remove(); delete POOL[k]; });
    var go = function (p) { P = p; SEL = null; T = 0; UNDO = []; REDO = []; last = JSON.stringify(P); $('#ed-name').value = P.name; $('#ed-aspect').value = P.w + 'x' + P.h;
      try { history.replaceState(null, '', location.pathname + (P.id ? '?p=' + P.id : '')); } catch (e) { } fitStage(); drawAll(); };
    if (!id) { go(blank()); return Promise.resolve(); }
    return api('/api/editor/project/' + id).then(function (p) { if (p.error) { if (id !== lastP) toast(p.error, 1); go(blank()); return; } go(p); });
  }
  function closeEditor(info) {
    save();
    var msg = { mml: 'editor-close', info: info || null };
    if (window.parent !== window) { window.parent.postMessage(msg, '*'); return; }
    if (window.MMLApp && MMLApp.close) { MMLApp.close(JSON.stringify(info || {})); return; }
    location.href = B + '/';
  }

  /* ── top bar + transport + keys ── */
  $('#ed-name').onchange = function () { P.name = this.value.trim() || 'Untitled edit'; commit(); };
  $('#ed-aspect').onchange = function () { var v = this.value.split('x'); P.w = +v[0]; P.h = +v[1]; commit(); fitStage(); drawInsp(); };
  function action(a) {
    if (a === 'close') closeEditor(); else if (a === 'undo') undo(); else if (a === 'redo') redo(); else if (a === 'projects') projectsDlg(); else if (a === 'export') exportDlg();
    else if (a === 'play') PLAYING ? pause() : play(); else if (a === 'start') { pause(); seek(0); } else if (a === 'end') { pause(); seek(total()); }
    else if (a === 'split') split(); else if (a === 'dup') dup(); else if (a === 'del') del(false);
    else if (a === 'snap') { SNAP = !SNAP; $('#ed-snap').classList.toggle('on', SNAP); toast('Snapping ' + (SNAP ? 'on' : 'off')); }
    else if (a === 'insp') { ED.classList.toggle('insp-on'); scrim(ED.classList.contains('insp-on')); }
    else if (a === 'bin') { ED.classList.toggle('bin-on'); scrim(ED.classList.contains('bin-on')); }
    else if (a === 'upload') $('#ed-file').click(); else if (a === 'addtext') addText(); else if (a === 'addcolor') addColor();
    else if (a.indexOf('addtrack-') === 0) { var k = a.split('-')[1], n = P.tracks.filter(function (t) { return t.kind === k; }).length + 1;
      var t = { id: uid(), kind: k, name: (k === 'video' ? 'V' : k === 'audio' ? 'A' : 'Titles ') + n, clips: [] };
      if (k === 'audio') P.tracks.push(t); else P.tracks.splice(k === 'text' ? 0 : P.tracks.filter(function (x) { return x.kind === 'text'; }).length, 0, t); commit(); drawAll(); }
    else if (a === 'score') aiScore(); else if (a === 'voice') aiVoice(); else if (a === 'fill') aiFill();
  }
  document.addEventListener('click', function (e) { var b = e.target.closest('[data-a]'); if (b && !b.closest('#ed-insp')) action(b.dataset.a); });
  $('#ed-snap').classList.add('on');
  document.addEventListener('keydown', function (e) {
    if (/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '') || !$('#ed-modal').hidden) { if (e.key === 'Escape') closeModal(); return; }
    var k = e.key, fr = 1 / (P.fps || 30);
    if (k === ' ') { e.preventDefault(); PLAYING ? pause() : play(); }
    else if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'Z')) { e.preventDefault(); e.shiftKey ? redo() : undo(); }
    else if ((e.ctrlKey || e.metaKey) && (k === 'y' || k === 'Y')) { e.preventDefault(); redo(); }
    else if ((e.ctrlKey || e.metaKey) && (k === 'd' || k === 'D')) { e.preventDefault(); dup(); }
    else if ((e.ctrlKey || e.metaKey) && (k === 's' || k === 'S')) { e.preventDefault(); save(); }
    else if (k === 's' || k === 'S') split(); else if (k === 'Delete' || k === 'Backspace') del(e.shiftKey);
    else if (k === 'ArrowLeft') { pause(); seek(T - (e.shiftKey ? 1 : fr)); } else if (k === 'ArrowRight') { pause(); seek(T + (e.shiftKey ? 1 : fr)); }
    else if (k === 'Home') { pause(); seek(0); } else if (k === 'End') { pause(); seek(total()); }
    else if (k === '+' || k === '=') zoom(PPS * 1.25); else if (k === '-') zoom(PPS / 1.25);
    else if (k === 'Escape') { SEL = null; drawAll(); ED.classList.remove('insp-on', 'bin-on'); scrim(false); }
  });
  window.addEventListener('beforeunload', function () { if (DIRTY) save(); });
  window.addEventListener('message', function (e) { var d = e.data || {}; if (d.mml === 'editor-add' && d.src) addMedia(d.src, { prompt: d.prompt }); });

  /* ── boot: ?p=<project> opens it · ?add=lib:x (repeatable) drops items in (from the lab's "Edit" buttons) ── */
  var qs = new URLSearchParams(location.search), adds = qs.getAll('add'), lastP = null;
  try { lastP = localStorage.getItem('mml.ed.last'); } catch (e) { }
  var bootP = qs.get('p') || (qs.get('new') ? null : lastP);       // reopen the edit you were working on
  (bootP ? openProject(bootP) : openProject(null)).then(function () {
    var chain = Promise.resolve();
    adds.forEach(function (s) { chain = chain.then(function () { return addMedia(s, { at: kindOfName(s) === 'audio' ? 0 : visEnd() }); }); });
    if (adds.length) chain.then(function () { try { history.replaceState(null, '', location.pathname + (P.id ? '?p=' + P.id : '')); } catch (e) { } });
  });
  loadLib();
  window.MMLEditor = { add: function (src, prompt) { return addMedia(src, { prompt: prompt }); }, project: function () { return P; }, save: save };
})();
