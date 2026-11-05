/* MIR MEDIA LABS · STUDIO — neuregex/freefield's open-weights apps (freefield.py). The form of every app is drawn
   from its app.json (inputs / options / presets / modes); runs go to /api/ff/run and land in the lab library. */
(function () {
  'use strict';
  var B = false ? '/' : '';
  var FRAMED = window.parent !== window;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var mi = function (n) { return '<i class="mi" data-ic="' + n + '"></i>'; };
  var icons = function () { try { if (window.MI && MI.scan) MI.scan(); else if (window.MI && MI.hydrate) MI.hydrate(document); } catch (e) { } };
  function api(path, body) {
    var o = { method: body ? 'POST' : 'GET', headers: {}, cache: 'no-store', credentials: 'same-origin' };
    if (body) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(body); }
    return fetch(B + path, o).then(function (r) { return r.json().catch(function () { return { error: 'HTTP ' + r.status }; }); });
  }
  var toastT;
  function toast(t, err) { var e = $('#st-toast'); e.textContent = t; e.className = 'st-toast on' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(function () { e.className = 'st-toast'; }, err ? 5200 : 2600); }

  /* theme — same table as Flow / Motion Studio / editor */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style;
    ['--bg', '--panel', '--panel2', '--ink', '--acc'].forEach(function (k, i) { r.setProperty(k, t[i]); }); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });
  var SESSION = (function () { try { return localStorage.getItem('mml.session') || ''; } catch (e) { return ''; } })();
  var LS = function (k, v) { try { if (v === undefined) return localStorage.getItem('mml.studio.' + k); localStorage.setItem('mml.studio.' + k, v); } catch (e) { } };

  var SEC = [['all', 'All'], ['image', 'Image'], ['video', 'Video'], ['3d', '3D'], ['audio', 'Audio'], ['utility', 'Utility']];
  var SEC_IC = { image: 'image', video: 'film', '3d': 'mesh', audio: 'music', utility: 'gear' };
  function dur(s) { s = Math.round(s); return s < 90 ? s + ' s' : s < 5400 ? Math.round(s / 60) + ' min' : (s / 3600).toFixed(1) + ' h'; }
  var S = { apps: [], engine: {}, tab: LS('tab') || 'all', q: '', only: LS('only') === '1', app: null, vals: {}, preset: '', job: null, poll: null };

  /* ── grid ─────────────────────────────────────────────────────────────────────────────────────────────── */
  function load(refresh) {
    var dev = /[?&]dev=1/.test(location.search);
    return api('/api/ff/apps?' + (refresh ? 'refresh=1&' : '') + (dev ? 'dev=1' : '')).then(function (d) {
      if (d.error) return toast(d.error, true);
      S.apps = d.apps || []; S.engine = d.engine || {};
      $('#st-q').placeholder = 'Search ' + S.apps.length + ' apps…';
      drawTabs(); drawGrid(); drawEngine();
    });
  }
  function drawEngine() {
    var e = S.engine, el = $('#st-engine'), n = $('#st-notice');
    var ready = S.apps.filter(function (a) { return a.ready.state === 'ready'; }).length;
    el.textContent = e.up ? 'ComfyUI ' + (e.version || '?') + ' · ' + ready + '/' + S.apps.length + ' ready' : 'ComfyUI is off';
    el.className = 'chip' + (e.up ? '' : ' bad');
    var need = S.apps.filter(function (a) { return a.ready.state === 'needs_engine'; }).length;
    if (e.up && need && e.version && e.version !== e.wants) {
      n.hidden = false;
      n.innerHTML = mi('warn') + ' <b>' + need + ' apps need ComfyUI ' + esc(e.wants) + '</b> (this PC runs ' + esc(e.version) + ') — they use nodes added after it, like <code>ReferenceMultiLatent</code>. Update Comfy Desktop when no render is running, then press ' +
        '<a href="#" data-a="refresh">re-check</a>.';
    } else n.hidden = true;
    icons();
  }
  function drawTabs() {
    $('#st-tabs').innerHTML = SEC.map(function (s) {
      var n = s[0] === 'all' ? S.apps.length : S.apps.filter(function (a) { return a.section === s[0]; }).length;
      return n || s[0] === 'all' ? '<button data-tab="' + s[0] + '"' + (S.tab === s[0] ? ' class="on"' : '') + '>' + s[1] + '<b>' + n + '</b></button>' : '';
    }).join('');
    $('#st-only').checked = S.only;
  }
  var RANK = { ready: 0, needs_models: 1, needs_engine: 2, needs_nodes: 3, draft: 4, engine_down: 5 };
  function drawGrid() {
    var q = S.q.toLowerCase();
    var list = S.apps.filter(function (a) {
      if (S.tab !== 'all' && a.section !== S.tab) return false;
      if (S.only && a.ready.state !== 'ready') return false;
      return !q || (a.name + ' ' + a.summary + ' ' + a.rebuilds + ' ' + a.model + ' ' + a.id).toLowerCase().indexOf(q) >= 0;
    }).sort(function (x, y) { return (RANK[x.ready.state] - RANK[y.ready.state]) || x.name.localeCompare(y.name); });
    var g = $('#st-grid');
    if (!list.length) { g.innerHTML = '<div class="st-sec">Nothing matches' + (S.only ? ' — untick “Ready on this PC” to see every app' : '') + '</div>'; return; }
    var html = '', last = null;
    list.forEach(function (a) {
      var grp = a.ready.state === 'ready' ? 'Ready on this PC' : a.ready.state === 'needs_models' ? 'One download away' : 'Needs an engine update / node pack';
      if (grp !== last) { html += '<div class="st-sec">' + grp + '</div>'; last = grp; }
      html += '<div class="card' + (a.ready.state === 'ready' ? '' : ' off') + '" data-s="' + a.section + '" data-app="' + a.id + '">' +
        '<div class="k">' + mi(SEC_IC[a.section] || 'sparkle') + '<b>' + esc(a.name) + '</b><span class="sp"></span><span class="badge ' + a.ready.state + '">' + esc(a.ready.label) + '</span></div>' +
        '<p>' + esc(a.summary || a.rebuilds) + '</p>' +
        '<div class="m"><span>' + esc(a.model || a.pack) + '</span><span class="sp"></span>' + (a.peak_gb ? '<span>' + a.peak_gb + ' GB VRAM</span>' : '') + '</div></div>';
    });
    g.innerHTML = html; icons();
  }

  /* ── app panel ────────────────────────────────────────────────────────────────────────────────────────── */
  function openApp(id, keep) {
    return api('/api/ff/app/' + encodeURIComponent(id)).then(function (a) {
      if (a.error) return toast(a.error, true);
      var prev = S.app; S.app = a; S.preset = '';
      if (!keep) S.vals = {};
      else if (prev) { var ids = {}; a.inputs.forEach(function (i) { ids[i.id] = 1; }); Object.keys(S.vals).forEach(function (k) { if (!ids[k]) delete S.vals[k]; }); }
      a.inputs.forEach(function (i) { if (S.vals[i.id] === undefined && i.default !== undefined) S.vals[i.id] = i.multiple ? (Array.isArray(i.default) ? i.default.slice() : []) : i.default; });
      $('#ap').hidden = false;
      $('#ap-name').textContent = a.name;
      $('#ap-sub').textContent = (a.higgsfield_feature ? 'Rebuilds ' + a.higgsfield_feature + ' · ' : '') + (a.summary || '');
      var r = a.ready; $('#ap-ready').className = 'badge ' + r.state; $('#ap-ready').textContent = r.label;
      $('[data-a=getmodels]').hidden = r.state !== 'needs_models';
      $('[data-a=getmodels] span').textContent = 'Get models (' + r.gb + ' GB)';
      $('[data-a=run]').disabled = r.state !== 'ready' && r.state !== 'draft';
      $('#ap-msg').textContent = r.state === 'ready' ? (a.vram && a.vram.peak_gb ? 'peak ' + a.vram.peak_gb + ' GB VRAM' + (a.vram.measured_on ? ' · ' + a.vram.measured_on : '') : '') :
        r.state === 'needs_models' ? r.missing.length + ' model file(s) missing' : r.nodes.length ? 'missing nodes: ' + r.nodes.slice(0, 3).join(', ') : r.label;
      if (a.est_s && r.state === 'ready') $('#ap-msg').textContent = 'about ' + dur(a.est_s) + ' on this PC' + ($('#ap-msg').textContent ? ' · ' + $('#ap-msg').textContent : '');
      if (!keep) S.loras = [];
      S.loraList = null;
      if (a.lora_family) api('/api/ff/loras?family=' + encodeURIComponent(a.lora_family)).then(function (d) { S.loraList = d.loras || []; S.loraMax = d.max || 4; if (S.app === a) drawForm(); });
      drawForm(); drawHow(); ptab(LS('pt') === 'how' ? 'how' : 'form');
      if (!keep) resetResult();
      icons();
    });
  }
  function closeApp() { $('#ap').hidden = true; S.app = null; stopPoll(); }
  function ptab(t) { $$('.ap-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.pt === t); }); $('#ap-form').hidden = t !== 'form'; $('#ap-how').hidden = t !== 'how'; }

  function drawForm() {
    var a = S.app, f = $('#ap-form'), h = '';
    if (a.modes && a.modes.length > 1) {
      h += '<div class="modes">' + a.modes.map(function (m) {
        var o = S.apps.filter(function (x) { return x.id === m; })[0];
        var lbl = (o && (o.mode_label || (o.section[0].toUpperCase() + o.section.slice(1)))) || m;
        return '<button type="button" data-mode="' + m + '"' + (m === a.id ? ' class="on"' : '') + '>' + esc(lbl) + '</button>';
      }).join('') + '</div>';
    }
    if (a.presets && a.presets.length) {
      h += '<div class="fld"><label>Preset</label><div class="pills" data-preset>' + '<button type="button" data-pv=""' + (!S.preset ? ' class="on"' : '') + '>Default</button>' +
        a.presets.map(function (p) { return '<button type="button" data-pv="' + esc(p.id) + '"' + (S.preset === p.id ? ' class="on"' : '') + '>' + esc(p.label) + '</button>'; }).join('') + '</div></div>';
    }
    if (a.page === 'stage') h += '<div class="fld"><a class="eb" style="width:100%" href="' + B + '/studio-stage">' + mi('mesh') + 'Open the Stage editor (block the shot in 3D)</a><div class="help">Or drop any grey-clay / layout clip below.</div></div>';
    a.inputs.forEach(function (i) { h += field(i); });
    if (a.lora_family) h += loraField(a);
    f.innerHTML = h; icons();
  }
  /* LoRAs: only files whose weights match this app's model family (checked from the safetensors header) */
  function loraField(a) {
    var L = S.loraList, picked = S.loras || [];
    if (!L) return '<div class="fld"><label>LoRAs</label><div class="help">Reading your LoRA folder…</div></div>';
    var fits = L.filter(function (l) { return l.family === a.lora_family; }), unk = L.filter(function (l) { return !l.family; });
    var h = '<div class="fld"><label>LoRAs <span class="dim">· ' + esc(a.lora_label || a.lora_family) + ' only</span></label>';
    h += picked.map(function (p, k) {
      return '<div class="row" style="gap:6px;align-items:center"><span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis">' + esc(p.name.split('/').pop()) + '</span>' +
        '<input type="range" min="0" max="1.5" step="0.05" value="' + p.strength + '" data-lstr="' + k + '" style="width:90px"><output>' + p.strength + '</output>' +
        '<button class="eb ic" type="button" data-ldel="' + k + '">' + mi('close') + '</button></div>';
    }).join('');
    if (picked.length < (S.loraMax || 4)) {
      var opts = fits.concat(unk).filter(function (l) { return !picked.some(function (p) { return p.name === l.name; }); });
      h += opts.length ? '<select data-ladd><option value="">Add a LoRA…</option>' + opts.map(function (l) {
        return '<option value="' + esc(l.name) + '">' + esc(l.name.split('/').pop()) + (l.family ? '' : ' (type unknown)') + '</option>'; }).join('') + '</select>' :
        '<div class="help">No ' + esc(a.lora_label || a.lora_family) + ' LoRAs in ComfyUI’s loras folder' + (L.length ? ' (' + L.length + ' for other models are hidden)' : '') + '.</div>';
    }
    return h + '</div>';
  }
  function lbl(i) { return '<label>' + esc(i.label) + (i.required ? '' : (['image', 'video', 'audio'].indexOf(i.type) >= 0 ? '' : '')) + '</label>' + (i.help ? '<div class="help">' + esc(i.help) + '</div>' : ''); }
  function field(i) {
    var v = S.vals[i.id], id = 'f-' + i.id;
    switch (i.type) {
      case 'text': return '<div class="fld">' + lbl(i) + '<input type="text" id="' + id + '" data-in="' + i.id + '" value="' + esc(v == null ? '' : v) + '"></div>';
      case 'textarea': return '<div class="fld">' + lbl(i) + '<textarea id="' + id + '" data-in="' + i.id + '">' + esc(v == null ? '' : v) + '</textarea></div>';
      case 'number': return '<div class="fld">' + lbl(i) + '<input type="number" data-in="' + i.id + '" value="' + esc(v == null ? '' : v) + '"' + rng(i) + '></div>';
      case 'slider': return '<div class="fld">' + lbl(i) + '<div class="row"><input type="range" data-in="' + i.id + '" value="' + esc(v) + '"' + rng(i) + '><output>' + esc(v) + '</output></div></div>';
      case 'seed': return '<div class="fld">' + lbl(i) + '<div class="row seedrow"><input type="number" data-in="' + i.id + '" value="' + esc(v == null ? -1 : v) + '"><button class="eb" type="button" data-seed="' + i.id + '" title="Random every run">' + mi('refresh') + '</button></div></div>';
      case 'toggle': return '<div class="fld"><label style="font-weight:600;display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" data-in="' + i.id + '"' + (v ? ' checked' : '') + '>' + esc(i.label) + '</label>' + (i.help ? '<div class="help">' + esc(i.help) + '</div>' : '') + '</div>';
      case 'select':
        var opts = i.options || [];
        if (i.multiple) {
          var picked = Array.isArray(v) ? v : [];
          return '<div class="fld">' + lbl(i) + '<div class="help">pick up to ' + (i.multiple.max || opts.length) + (i.multiple.ordered ? ', in order' : '') + '</div><div class="pills" data-multi="' + i.id + '">' +
            opts.map(function (o) { var k = picked.indexOf(String(o.value)); return '<button type="button" data-ov="' + esc(o.value) + '"' + (k >= 0 ? ' class="on"' : '') + '>' + esc(o.label) + (k >= 0 && i.multiple.ordered ? '<sup>' + (k + 1) + '</sup>' : '') + '</button>'; }).join('') + '</div></div>';
        }
        if (i.gallery || opts.length <= 8) {
          var cls = i.gallery ? 'gal' : 'pills';
          return '<div class="fld">' + lbl(i) + '<div class="' + cls + '" data-one="' + i.id + '">' + opts.map(function (o) {
            return '<button type="button" data-ov="' + esc(o.value) + '"' + (String(o.value) === String(v) ? ' class="on"' : '') + '>' + esc(o.label) + '</button>'; }).join('') + '</div></div>';
        }
        return '<div class="fld">' + lbl(i) + '<select data-in="' + i.id + '">' + opts.map(function (o) { return '<option value="' + esc(o.value) + '"' + (String(o.value) === String(v) ? ' selected' : '') + '>' + esc(o.label) + '</option>'; }).join('') + '</select></div>';
      case 'image': case 'video': case 'audio':
        var fv = v || null, src = fv && fv.url, paintOf = i.paint;
        var pv = fv ? (i.type === 'image' ? '<div class="pv" style="background-image:url(\'' + esc(src) + '\')"></div>' : i.type === 'video' && fv.thumb ? '<div class="pv" style="background-image:url(\'' + esc(fv.thumb) + '\')"></div>' : '<div class="pv">' + mi(i.type === 'video' ? 'film' : 'music') + '</div>') : '<div class="pv">' + mi(paintOf ? 'palette' : i.type === 'image' ? 'image' : i.type === 'video' ? 'film' : 'music') + '</div>';
        return '<div class="fld">' + lbl(i) + '<div class="drop" data-drop="' + i.id + '">' + pv + '<div class="nm">' + (fv ? esc(fv.name) : paintOf ? 'Paint over the photo above' : 'Drop a ' + i.type + ' here') + '</div><div class="bt">' +
          (paintOf ? '<button class="eb" type="button" data-paint="' + i.id + '">' + mi('palette') + 'Paint</button>' :
            '<button class="eb" type="button" data-up="' + i.id + '">' + mi('upload') + 'Upload</button><button class="eb" type="button" data-lib="' + i.id + '">' + mi('grid') + 'Library</button>' +
            (i.type === 'video' ? '<button class="eb" type="button" data-phone="' + i.id + '" title="Film it on your phone: scan a QR code, the clip lands here">' + mi('phone') + 'Phone</button>' : '')) +
          (fv ? '<button class="eb ic" type="button" data-clr="' + i.id + '" title="Remove">' + mi('close') + '</button>' : '') + '</div></div></div>';
    }
    return '';
  }
  function rng(i) { return (i.min != null ? ' min="' + i.min + '"' : '') + (i.max != null ? ' max="' + i.max + '"' : '') + (i.step != null ? ' step="' + i.step + '"' : ' step="any"'); }
  function inputOf(id) { return S.app.inputs.filter(function (i) { return i.id === id; })[0]; }

  function drawHow() {
    var a = S.app, r = a.ready, miss = {};
    (r.missing || []).forEach(function (m) { miss[m.file] = 1; });
    var h = (a.powers ? '<p class="have">' + mi('check-circle') + ' This engine also powers ' + esc(a.powers) + '.</p>' : '') + '<h4>Models</h4><table>' + (a.models || []).map(function (m) {
      var f = m.file.split('/').pop(), al = r.aliases && r.aliases[f];
      return '<tr><td><b>' + esc(f) + '</b><br><span class="dim">' + esc(m.repo) + ' · ' + esc(m.dir) + ' · ' + esc(m.phase) + (m.license ? ' · ' + esc(m.license) : '') + '</span>' +
        (al ? '<br><span class="have">using ' + esc(al) + ' (same model, other quant)</span>' : '') + '</td><td class="r ' + (miss[m.file] ? 'miss' : 'have') + '">' + m.gb + ' GB<br>' + (miss[m.file] ? 'missing' : 'installed') + '</td></tr>';
    }).join('') + '</table>';
    if (r.nodes && r.nodes.length) h += '<h4>Missing node types</h4><ul>' + r.nodes.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join('') + '</ul>' +
      ((a.custom_nodes || []).length ? '<p class="dim">Needs ' + a.custom_nodes.map(function (c) { return esc(c.repo.split('/').pop()) + ' @' + esc(c.commit.slice(0, 7)); }).join(', ') + '</p>' :
        '<p class="dim">These ship with ComfyUI ' + esc(S.engine.wants || '0.42') + ' — update Comfy Desktop.</p>');
    if (a.vram && a.vram.peak_gb) h += '<h4>VRAM</h4><p class="dim">peak ' + a.vram.peak_gb + ' GB' + (a.vram.measured_on ? ' · measured on ' + esc(a.vram.measured_on) : '') + '</p>';
    if (a.notes) h += '<h4>Notes</h4><p class="dim">' + esc(a.notes) + '</p>';
    if (a.source && a.source.notes) h += '<h4>Workflow</h4><p class="dim">' + esc(a.source.template ? a.source.template + ' — ' : '') + esc(a.source.notes) + '</p>';
    if (a.credits && a.credits.length) h += '<h4>Credits</h4><ul>' + a.credits.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join('') + '</ul>';
    h += '<p class="dim" style="font-size:11px">From neuregex/freefield (MIT) · every model is open weights, run on this PC’s ComfyUI.</p>';
    $('#ap-how').innerHTML = h;
  }

  /* ── form events ──────────────────────────────────────────────────────────────────────────────────────── */
  $('#ap-form').addEventListener('input', function (e) {
    var t = e.target, id = t.dataset.in;
    var i = id && inputOf(id);
    if (t.dataset.lstr != null) { var lp = S.loras[+t.dataset.lstr]; if (lp) { lp.strength = +t.value; t.nextSibling.textContent = t.value; } return; }
    if (t.hasAttribute('data-ladd')) { if (t.value) { S.loras.push({ name: t.value, strength: 0.8 }); drawForm(); } return; }
    if (!id) return;
    if (t.type === 'checkbox') S.vals[id] = t.checked;
    else if (t.type === 'range' || t.type === 'number') { S.vals[id] = t.value === '' ? undefined : +t.value; var o = t.parentNode.querySelector('output'); if (o) o.textContent = t.value; }
    else S.vals[id] = t.value;
    if (i && i.type === 'select' && !i.multiple) { var hit = (i.options || []).filter(function (o) { return String(o.value) === t.value; })[0]; if (hit) S.vals[id] = hit.value; }
  });
  $('#ap-form').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var box = b.parentNode;
    if (b.dataset.mode) { if (b.dataset.mode !== S.app.id) openApp(b.dataset.mode, true); return; }
    if (box.hasAttribute('data-preset')) { S.preset = b.dataset.pv; $$('button', box).forEach(function (x) { x.classList.toggle('on', x === b); }); return; }
    if (box.dataset.one) { var i = inputOf(box.dataset.one), hit = (i.options || []).filter(function (o) { return String(o.value) === b.dataset.ov; })[0];
      S.vals[i.id] = hit ? hit.value : b.dataset.ov; $$('button', box).forEach(function (x) { x.classList.toggle('on', x === b); }); return; }
    if (box.dataset.multi) { var mi_ = inputOf(box.dataset.multi), cur = Array.isArray(S.vals[mi_.id]) ? S.vals[mi_.id].slice() : [], k = cur.indexOf(b.dataset.ov);
      if (k >= 0) cur.splice(k, 1); else { if (mi_.multiple.max && cur.length >= mi_.multiple.max) return toast('At most ' + mi_.multiple.max, true); cur.push(b.dataset.ov); }
      S.vals[mi_.id] = cur; drawForm(); return; }
    if (b.dataset.seed) { S.vals[b.dataset.seed] = -1; drawForm(); return; }
    if (b.dataset.up) return pickFile(b.dataset.up);
    if (b.dataset.lib) return openLib(b.dataset.lib);
    if (b.dataset.clr) { delete S.vals[b.dataset.clr]; drawForm(); return; }
    if (b.dataset.ldel != null) { S.loras.splice(+b.dataset.ldel, 1); drawForm(); return; }
    if (b.dataset.phone) return phoneDrop(b.dataset.phone);
    if (b.dataset.paint) return openPaint(b.dataset.paint);
  });
  $('#ap-form').addEventListener('dragover', function (e) { var d = e.target.closest('[data-drop]'); if (d) { e.preventDefault(); d.classList.add('over'); } });
  $('#ap-form').addEventListener('dragleave', function (e) { var d = e.target.closest('[data-drop]'); if (d) d.classList.remove('over'); });
  $('#ap-form').addEventListener('drop', function (e) { var d = e.target.closest('[data-drop]'); if (!d) return; e.preventDefault(); d.classList.remove('over');
    var f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) upload(d.dataset.drop, f); });

  function pickFile(id) {
    var i = inputOf(id), inp = $('#st-file');
    inp.accept = i.type + '/*'; inp.value = '';
    inp.onchange = function () { if (inp.files[0]) upload(id, inp.files[0]); };
    inp.click();
  }
  function upload(id, file) {
    var i = inputOf(id);
    if (i && i.limits && i.limits.max_mb && file.size > i.limits.max_mb * 1e6) return toast('Over ' + i.limits.max_mb + ' MB', true);
    var fd = new FormData(); fd.append('file', file);
    toast('Uploading…');
    return fetch(B + '/api/ff/upload', { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) return toast(d.error, true);
      S.vals[id] = { up: d.name, name: file.name, url: URL.createObjectURL(file) }; drawForm(); toast('Added');
    }).catch(function () { toast('Upload failed', true); });
  }

  /* phone drop box: a one-time QR link on the LAN; the clip the phone sends becomes this input */
  var PH = { t: null };
  function phoneDrop(id) {
    api('/api/ff/phone', {}).then(function (d) {
      if (d.error) return toast(d.error, true);
      var box = $('#ph') || document.body.appendChild(Object.assign(document.createElement('div'), { id: 'ph', className: 'ph' }));
      box.hidden = false;
      box.innerHTML = '<div class="ph-card"><b>Send a clip from your phone</b><div class="ph-qr">' + d.qr + '</div><small class="dim">Same Wi-Fi as this PC. One clip, link expires in 15 min.</small>' +
        '<code>' + esc(d.url) + '</code><span id="ph-st" class="dim">Waiting for the phone…</span><button class="eb" type="button" data-phclose>Close</button></div>';
      box.onclick = function (e) { if (e.target === box || e.target.closest('[data-phclose]')) { box.hidden = true; clearInterval(PH.t); } };
      clearInterval(PH.t);
      PH.t = setInterval(function () {
        api('/api/ff/phone/' + d.token).then(function (s) {
          if (!s || s.error) return;
          $('#ph-st').textContent = s.status === 'receiving' ? 'Receiving…' : s.status === 'expired' ? 'Expired. Make a new code.' : s.status === 'closed' ? 'Closed after bad files.' : 'Waiting for the phone…';
          if (s.status === 'done') { clearInterval(PH.t); box.hidden = true; S.vals[id] = { up: s.up, name: s.name || 'phone clip', url: B + '/api/ff/inbox/' + encodeURIComponent(s.up) }; drawForm(); toast('Clip from the phone added'); }
          if (s.status === 'expired' || s.status === 'closed') clearInterval(PH.t);
        });
      }, 2000);
    });
  }

  /* library picker */
  function openLib(id) {
    var i = inputOf(id); $('#lp').hidden = false; $('#lp-body').innerHTML = '<p class="dim">Loading…</p>';
    api('/api/library?kind=' + i.type + '&limit=120').then(function (d) {
      var items = d.items || [];
      $('#lp-body').innerHTML = items.length ? items.map(function (x) {
        return '<button type="button" data-pick="' + esc(x.name) + '">' + (x.kind === 'audio' ? '<div style="display:flex;align-items:center;justify-content:center;height:100%">' + mi('music') + '</div>' : '<img loading="lazy" src="' + B + '/thumb/' + encodeURIComponent(x.name) + '">') + '<span>' + esc(x.prompt || x.name) + '</span></button>';
      }).join('') : '<p class="dim">No ' + i.type + 's in the library yet.</p>';
      $('#lp-body').onclick = function (e) { var b = e.target.closest('[data-pick]'); if (!b) return; var n = b.dataset.pick;
        S.vals[id] = { lib: n, name: n, url: B + '/media/' + encodeURIComponent(n), thumb: B + '/thumb/' + encodeURIComponent(n) }; $('#lp').hidden = true; drawForm(); };
      icons();
    });
  }

  /* inpaint mask painter: white strokes on black, at the photo's own size */
  var MP = { id: null, draw: false };
  function openPaint(id) {
    var i = inputOf(id), base = S.vals[i.paint];
    if (!base || !base.url) return toast('Add the photo first', true);
    var img = new Image(); img.crossOrigin = 'anonymous';
    img.onload = function () {
      var c = $('#mp-img'), m = $('#mp-mask'); c.width = m.width = img.naturalWidth; c.height = m.height = img.naturalHeight;
      c.getContext('2d').drawImage(img, 0, 0); var x = m.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, m.width, m.height);
      MP.id = id; $('#mp').hidden = false; place();
    };
    img.onerror = function () { toast('Could not load the photo', true); };
    img.src = base.url;
  }
  function place() { var c = $('#mp-img'), m = $('#mp-mask'); m.style.width = c.clientWidth + 'px'; m.style.height = c.clientHeight + 'px'; m.style.left = c.offsetLeft + 'px'; m.style.top = c.offsetTop + 'px'; }
  window.addEventListener('resize', function () { if (!$('#mp').hidden) place(); });
  function stroke(e) {
    var m = $('#mp-mask'), r = m.getBoundingClientRect(), sx = m.width / r.width, x = m.getContext('2d');
    var p = e.touches ? e.touches[0] : e;
    x.fillStyle = '#fff'; x.beginPath(); x.arc((p.clientX - r.left) * sx, (p.clientY - r.top) * sx, +$('#mp-size').value * sx / 2, 0, 7); x.fill();
  }
  ['pointerdown'].forEach(function (ev) { $('#mp-mask').addEventListener(ev, function (e) { MP.draw = true; stroke(e); }); });
  $('#mp-mask').addEventListener('pointermove', function (e) { if (MP.draw) stroke(e); });
  window.addEventListener('pointerup', function () { MP.draw = false; });

  /* ── run + progress ───────────────────────────────────────────────────────────────────────────────────── */
  function payload() {
    var out = {};
    Object.keys(S.vals).forEach(function (k) {
      var v = S.vals[k];
      if (v && typeof v === 'object' && !Array.isArray(v)) { if (v.lib) out[k] = { lib: v.lib }; else if (v.up) out[k] = { up: v.up }; }
      else if (v !== undefined) out[k] = v;
    });
    return out;
  }
  function run() {
    var a = S.app; if (!a) return;
    var miss = a.inputs.filter(function (i) { return (i.required || ['image', 'video', 'audio'].indexOf(i.type) >= 0) && (S.vals[i.id] == null || S.vals[i.id] === '') && i.default == null; });
    if (miss.length) return toast('Add: ' + miss.map(function (i) { return i.label; }).join(', '), true);
    $('[data-a=run]').disabled = true;
    api('/api/ff/run', { app: a.id, values: payload(), preset: S.preset || null, session: SESSION, loras: S.loras || [] }).then(function (j) {
      $('[data-a=run]').disabled = false;
      if (j.error) return toast(j.error, true);
      S.job = j.id; toast('Queued'); follow(j.id);
    });
  }
  function resetResult() { stopPoll(); $('#ap-result').innerHTML = '<div class="empty dim">' + mi('sparkle') + '<span>Your result shows up here</span></div>'; $('#ap-prog').hidden = true; $('[data-a=stop]').hidden = true; icons(); }
  function stopPoll() { clearTimeout(S.poll); S.poll = null; }
  function follow(jid) {
    stopPoll(); $('[data-a=stop]').hidden = false; $('#ap-prog').hidden = false;
    var tick = function () {
      api('/api/ff/jobs/' + jid).then(function (j) {
        if (j.error || !j.id) { stopPoll(); return; }
        var p = j.progress || {}, pct = p.max ? p.pct : (j.status === 'done' ? 100 : 0);
        $('#ap-prog .bar i').style.width = pct + '%';
        $('#ap-prog span').textContent = j.stage || j.status;
        if (p.pv) {
          var r = $('#ap-result'), im = $('#ap-live');
          if (!im) { r.innerHTML = '<figure><img id="ap-live"></figure>'; im = $('#ap-live'); }
          im.src = B + '/api/ff/jobs/' + jid + '/preview?n=' + p.pv;
        }
        if (j.status === 'done' || j.status === 'error' || j.status === 'cancelled') { done(j); return; }
        S.poll = setTimeout(tick, 1500);
      }).catch(function () { S.poll = setTimeout(tick, 3000); });
    };
    tick(); busy();
  }
  function media(n, cls) {
    var u = B + '/media/' + encodeURIComponent(n), k = /\.(mp4|webm|mov|m4v|mkv)$/i.test(n) ? 'video' : /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(n) ? 'audio' : 'image';
    return k === 'video' ? '<video src="' + u + '" controls autoplay loop playsinline></video>' : k === 'audio' ? '<audio src="' + u + '" controls autoplay></audio>' : '<img src="' + u + '">';
  }
  function done(j) {
    stopPoll(); $('[data-a=stop]').hidden = true; $('#ap-prog').hidden = true; busy();
    var r = $('#ap-result');
    if (j.status !== 'done') { r.innerHTML = '<div class="err">' + (j.status === 'cancelled' ? 'Stopped.' : esc(j.error || 'failed')) + '</div>' + extras(j); icons(); return; }
    r.innerHTML = report(j) + (j.models3d || []).map(function (g) {
      return '<figure class="glb"><div class="pv">' + mi('mesh') + '</div><div class="acts"><a class="eb" href="' + B + '/api/ff/model3d/' + encodeURIComponent(g) + '?dl=1">' + mi('download') + 'GLB model</a>' +
        '<a class="eb" target="_blank" href="' + B + '/api/ff/model3d/' + encodeURIComponent(g) + '">' + mi('external') + 'Open</a></div><small class="dim" style="text-align:center">' + esc(g) + ' · saved to the Studio 3D shelf</small></figure>';
    }).join('') + (j.files || []).map(function (n) {
      if (/\.txt$/i.test(n)) return '<figure><a class="eb" href="' + B + '/media/' + encodeURIComponent(n) + '" target="_blank">' + mi('note') + 'Shot list</a></figure>';
      return '<figure>' + media(n) + '<div class="acts"><button class="eb" data-r="edit" data-n="' + esc(n) + '">' + mi('scissors') + 'Editor</button>' +
        '<button class="eb" data-r="attach" data-n="' + esc(n) + '">' + mi('attach') + 'Attach to chat</button>' +
        '<button class="eb" data-r="reuse" data-n="' + esc(n) + '">' + mi('refresh') + 'Use as input</button>' +
        '<a class="eb" href="' + B + '/media/' + encodeURIComponent(n) + '?dl=1">' + mi('download') + '</a></div><small class="dim" style="text-align:center">' + (j.secs ? dur(j.secs) + ' on the GPU · ' : '') + 'saved to the library</small></figure>';
    }).join('') + extras(j);
    icons();
  }
  /* Seam Doctor's before/after, Scene's shot list */
  function report(j) {
    var h = '', rp = j.report;
    if (rp && rp.before) {
      var row = function (t, m) { return '<tr><td>' + t + '</td><td><b class="' + (m.verdict === 'seamless' ? 'have' : 'miss') + '">' + m.verdict + '</b></td><td>' + m.ratio + '×</td><td class="dim">texture ' + m.texture.ratio + ' · layout ' + m.composition.ratio + '</td></tr>'; };
      h += '<div class="seam"><table>' + row('Before', rp.before) + (rp.after ? row('After · ' + esc(rp.method), rp.after) : '') + '</table>' +
        (rp.note ? '<p class="dim">' + esc(rp.note) + '</p>' : '') + (rp.plan && rp.plan.frames ? '<p class="dim">kept frames ' + rp.plan.start + '–' + (rp.plan.start + rp.plan.frames - 1) + ' of ' + rp.plan.of + '</p>' : '') +
        '<p class="dim" style="font-size:11px">The wrap jump vs. a normal frame step: under ~1.5× (layout) and 2× (texture) reads as seamless.</p></div>';
    }
    if (j.shots && j.shots.length) h += '<ol class="shots">' + j.shots.map(function (s) { return '<li><b>' + esc(s.framing) + ' · ' + esc(s.move) + ' · ' + s.seconds + ' s</b> ' + esc(s.action) + '</li>'; }).join('') + '</ol>';
    return h;
  }
  /* every graph the run sent: download it, or open ComfyUI and drop it on the canvas */
  function extras(j) {
    if (!j.graphs || !j.graphs.length) return '';
    return '<div class="wf"><small class="dim">Workflows this run sent to ComfyUI</small>' + j.graphs.map(function (g, k) {
      return '<div class="row"><span style="flex:1">' + esc(g.label) + '</span><a class="eb" href="' + B + '/api/ff/jobs/' + j.id + '/workflow?n=' + k + '&dl=1">' + mi('download') + 'Workflow</a>' +
        '<a class="eb" data-comfy="' + j.id + ':' + k + '" href="http://' + location.hostname + ':8188/" target="_blank" title="Opens ComfyUI and downloads the workflow: drop the file on the canvas">' + mi('external') + 'ComfyUI</a></div>';
    }).join('') + '</div>';
  }
  document.addEventListener('click', function (e) {
    var c = e.target.closest('[data-comfy]'); if (!c) return;
    var p = c.dataset.comfy.split(':'), a = document.createElement('a');
    a.href = B + '/api/ff/jobs/' + p[0] + '/workflow?n=' + p[1] + '&dl=1'; document.body.appendChild(a); a.click(); a.remove();
    toast('Drop the downloaded workflow onto the ComfyUI canvas');
  });
  $('#ap-result').addEventListener('click', function (e) {
    var b = e.target.closest('[data-r]'); if (!b) return; var n = b.dataset.n;
    if (b.dataset.r === 'edit') { if (FRAMED) window.parent.postMessage({ mml: 'studio-editor', src: 'lib:' + n }, '*'); else location.href = B + '/editor?add=' + encodeURIComponent('lib:' + n); }
    else if (b.dataset.r === 'attach') {
      fetch(B + '/api/library/' + encodeURIComponent(n) + '/use', { method: 'POST', credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
        if (FRAMED) window.parent.postMessage({ mml: 'studio-attach', ref: d }, '*'); else toast('Attached'); });
    } else if (b.dataset.r === 'reuse') {
      var kind = /\.(mp4|webm|mov|m4v|mkv)$/i.test(n) ? 'video' : /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(n) ? 'audio' : 'image';
      var i = S.app.inputs.filter(function (x) { return x.type === kind && !x.paint; })[0];
      if (!i) return toast('This app takes no ' + kind, true);
      S.vals[i.id] = { lib: n, name: n, url: B + '/media/' + encodeURIComponent(n), thumb: B + '/thumb/' + encodeURIComponent(n) }; drawForm(); ptab('form'); toast('Set as ' + i.label);
    }
  });

  /* ── drawers: runs + models ───────────────────────────────────────────────────────────────────────────── */
  var DRT = null;
  function drawer(title, fill) { $('#dr').hidden = false; $('#dr-title').textContent = title; clearInterval(DRT); fill(); DRT = setInterval(fill, 2500); }
  function closeDrawer() { $('#dr').hidden = true; clearInterval(DRT); }
  function jobsDrawer() {
    drawer('Runs', function () {
      api('/api/ff/jobs').then(function (d) {
        var js = d.jobs || [];
        $('#dr-body').innerHTML = js.length ? js.map(function (j) {
          var f = (j.files || [])[0];
          return '<div class="jrow" data-job="' + j.id + '" data-app="' + j.app + '">' + (f && !/\.(mp3|wav|flac|ogg)$/i.test(f) ? '<img src="' + B + '/thumb/' + encodeURIComponent(f) + '">' : '') +
            '<div class="t"><b>' + esc(j.name) + '</b><small>' + esc(j.stage || j.error || new Date(j.created * 1000).toLocaleString()) + '</small></div><span class="st-' + j.status + '">' + j.status + '</span>' +
            (j.status === 'running' || j.status === 'queued' ? '<button class="eb ic" data-jstop="' + j.id + '">' + mi('stop') + '</button>' : '') + '</div>';
        }).join('') : '<p class="dim">No runs yet.</p>';
        icons();
      });
    });
  }
  function dlDrawer() {
    drawer('Model downloads', function () {
      api('/api/ff/download').then(function (d) {
        var ds = d.downloads || [];
        $('#dr-body').innerHTML = (ds.length ? ds.map(function (x) {
          var pct = x.total ? Math.min(100, Math.round(x.done * 100 / x.total)) : 0;
          return '<div class="dlrow"><div style="display:flex;gap:8px"><b style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis">' + esc(x.name) + '</b><span class="st-' + x.status + '">' + x.status + (x.status === 'downloading' ? ' ' + pct + '%' : '') + '</span>' +
            (x.status === 'downloading' || x.status === 'queued' ? '<button class="eb ic" data-dlstop="' + esc(x.name) + '">' + mi('stop') + '</button>' : '') + '</div>' +
            '<div class="bar"><i style="width:' + pct + '%"></i></div><small class="dim">' + esc(x.dir) + ' · ' + (x.done / 1e9).toFixed(2) + ' / ' + (x.total / 1e9).toFixed(2) + ' GB' + (x.error ? ' · ' + esc(x.error) : '') + '</small></div>';
        }).join('') : '<p class="dim">Nothing downloading. Open an app marked “needs … GB” and press Get models.</p>') +
          '<p class="dim" style="font-size:11px">Files go to Comfy Desktop’s shared models folder, so the lab and ComfyUI both see them.</p>';
        var act = ds.filter(function (x) { return x.status === 'downloading' || x.status === 'queued'; }).length;
        $('#st-dlc').hidden = !act; $('#st-dlc').textContent = act;
        if (!act && ds.some(function (x) { return x.status === 'done'; }) && !dlDrawer.reloaded) { dlDrawer.reloaded = 1; load(true); }
        icons();
      });
    });
  }
  function getModels() {
    var a = S.app; if (!a) return;
    if (!confirm('Download ' + a.ready.gb + ' GB of open-weights models for ' + a.name + ' from Hugging Face?')) return;
    api('/api/ff/download', { apps: [a.id] }).then(function (d) { if (d.error) return toast(d.error, true); dlDrawer.reloaded = 0; dlDrawer(); });
  }
  function busy() {
    api('/api/ff/status').then(function (s) {
      var n = (s.running ? 1 : 0); $('#st-busy').hidden = !n; $('#st-busy').textContent = n;
      var act = (s.downloads || []).filter(function (x) { return x.status === 'downloading' || x.status === 'queued'; }).length;
      $('#st-dlc').hidden = !act; $('#st-dlc').textContent = act;
    });
  }

  /* ── global clicks ────────────────────────────────────────────────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    var c = e.target.closest('[data-app]');
    if (c && c.classList.contains('card')) return openApp(c.dataset.app);
    var tb = e.target.closest('[data-tab]'); if (tb) { S.tab = tb.dataset.tab; LS('tab', S.tab); drawTabs(); drawGrid(); return; }
    var pt = e.target.closest('[data-pt]'); if (pt) { ptab(pt.dataset.pt); LS('pt', pt.dataset.pt); return; }
    var js = e.target.closest('[data-jstop]'); if (js) { api('/api/ff/jobs/' + js.dataset.jstop + '/cancel', {}); return; }
    var ds = e.target.closest('[data-dlstop]'); if (ds) { api('/api/ff/download', { cancel: true, name: ds.dataset.dlstop }); return; }
    var jr = e.target.closest('.jrow'); if (jr) { closeDrawer(); openApp(jr.dataset.app).then(function () { api('/api/ff/jobs/' + jr.dataset.job).then(function (j) { if (j.status === 'done' || j.status === 'error' || j.status === 'cancelled') done(j); else follow(j.id); }); }); return; }
    var b = e.target.closest('[data-a]'); if (!b) return;
    var a = b.dataset.a;
    if (a === 'close') { if (FRAMED) return window.parent.postMessage({ mml: 'studio-close' }, '*'); location.href = B + '/'; }
    else if (a === 'back') closeApp();
    else if (a === 'run') run();
    else if (a === 'stop') { if (S.job) api('/api/ff/jobs/' + S.job + '/cancel', {}); }
    else if (a === 'getmodels') getModels();
    else if (a === 'jobs') jobsDrawer();
    else if (a === 'downloads') { dlDrawer.reloaded = 1; dlDrawer(); }
    else if (a === 'drclose') closeDrawer();
    else if (a === 'lpclose') $('#lp').hidden = true;
    else if (a === 'mpclose') $('#mp').hidden = true;
    else if (a === 'mpclear') { var m = $('#mp-mask'), x = m.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, m.width, m.height); }
    else if (a === 'mpdone') {
      var id = MP.id; $('#mp-mask').toBlob(function (bl) { $('#mp').hidden = true; upload(id, new File([bl], 'mask.png', { type: 'image/png' })); }, 'image/png');
    }
    else if (a === 'refresh') { e.preventDefault(); toast('Re-checking the engine…'); load(true); }
  });
  $('#st-q').addEventListener('input', function (e) { S.q = e.target.value; drawGrid(); });
  $('#st-only').addEventListener('change', function (e) { S.only = e.target.checked; LS('only', S.only ? '1' : '0'); drawGrid(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { if (!$('#mp').hidden) $('#mp').hidden = true; else if (!$('#lp').hidden) $('#lp').hidden = true; else if (!$('#dr').hidden) closeDrawer(); else if (!$('#ap').hidden) closeApp(); } });

  /* the lab's library side panel: a click or a drop → this app's input (by reference, no re-upload) */
  window.addEventListener('message', function (e) {
    var d = e.data || {}; if (d.mml !== 'studio-lib' || !d.name) return;
    if (!S.app || $('#ap').hidden) return window.parent.postMessage({ mml: 'studio-lib-miss' }, '*');
    var n = d.name, kind = /\.(mp4|webm|mov|m4v|mkv)$/i.test(n) ? 'video' : /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(n) ? 'audio' : 'image';
    var at = d.at && document.elementFromPoint(d.at[0], d.at[1]), zone = at && at.closest && at.closest('[data-drop]');
    var fits = S.app.inputs.filter(function (i) { return i.type === kind && !i.paint; });
    var i = (zone && inputOf(zone.dataset.drop)) || fits.filter(function (x) { return !S.vals[x.id]; })[0] || fits[0];
    if (!i || i.type !== kind) return toast('This app takes no ' + kind, true);
    S.vals[i.id] = { lib: n, name: n, url: B + '/media/' + encodeURIComponent(n), thumb: B + '/thumb/' + encodeURIComponent(n) };
    drawForm(); ptab('form'); toast('Set as ' + i.label);
  });
  document.addEventListener('dragover', function (e) { if ([].indexOf.call(e.dataTransfer.types || [], 'text/mml-lib') >= 0) { var z = e.target.closest && e.target.closest('[data-drop]'); $$('[data-drop]').forEach(function (x) { x.classList.toggle('over', x === z); }); } });
  document.addEventListener('drop', function () { $$('[data-drop]').forEach(function (x) { x.classList.remove('over'); }); }, true);

  load().then(function () {
    var q = new URLSearchParams(location.search), app = q.get('app');
    if (!app || !/^[a-z0-9-]+$/.test(app)) return;
    openApp(app).then(function () {
      if (!q.get('clay') || !S.app) return;                // back from the Stage editor with a blocking clip
      S.vals.clay = { up: q.get('clay'), name: 'Stage blocking', url: B + '/api/ff/inbox/' + encodeURIComponent(q.get('clay')) };
      ['prompt', 'era', 'ramp'].forEach(function (k) { if (q.get(k) != null && inputOf(k)) S.vals[k] = k === 'era' ? +q.get(k) : q.get(k); });
      drawForm(); toast('Blocking added. Press Run.');
    });
  });
  busy(); setInterval(busy, 8000);
})();
