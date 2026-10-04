/* MIR FONTS — 10 original MirOS typefaces + a picker, shared by every MirOS web surface
   (desktop /miros, mobile web /miros/m, Media Lab /mlab). The choice is stored in
   /api/miros-prefs {font:{id}} so desktop, phone web and the native app all follow it.
   Usage: <script src="/static/fonts/miros/mirfont.js" data-vars="--font,--disp"></script>
          MirFont.openPicker()   — opens the chooser */
(function () {
  var FONTS = [
    {id: '', name: 'MirOS Default', desc: 'The original system look (Sora / Inter)'},
    {id: 'orbit', name: 'Mir Orbit', desc: 'Round monoline geometric — calm, friendly HUD sans'},
    {id: 'vector', name: 'Mir Vector', desc: 'Square-cut technical strokes with mitred corners'},
    {id: 'horizon', name: 'Mir Horizon', desc: 'Extended hairline — airy, wide, cinematic titles'},
    {id: 'bastion', name: 'Mir Bastion', desc: 'Condensed heavy — dense data and loud headings'},
    {id: 'stencil', name: 'Mir Stencil', desc: 'Military stencil — bridged gaps through every letter'},
    {id: 'pixel', name: 'Mir Pixel', desc: '8-bit pixel grid — retro terminal energy'},
    {id: 'matrix', name: 'Mir Matrix', desc: 'LED dot-matrix — scoreboard / ticker display'},
    {id: 'velocity', name: 'Mir Velocity', desc: 'Forward-slanted speed sans — motion and momentum'},
    {id: 'hollow', name: 'Mir Hollow', desc: 'Outlined inline letters — neon-tube display'},
    {id: 'quill', name: 'Mir Quill', desc: 'Broad-nib contrast — thick stems, hairline joins'}
  ];
  var me = document.currentScript;
  var VARS = ((me && me.getAttribute('data-vars')) || '--font,--disp').split(',');
  var BASE = '/static/fonts/miros/';
  var orig = {}, cur = null;

  var css = FONTS.filter(function (f) { return f.id; }).map(function (f) {
    return "@font-face{font-family:'" + f.name + "';src:url(" + BASE + f.id + ".woff2) format('woff2');font-display:swap}";
  }).join('') +
    '#mirfont-ov{position:fixed;inset:0;z-index:99999;background:rgba(5,4,3,.72);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:16px}' +
    '#mirfont-ov .mf{width:min(720px,100%);max-height:88vh;overflow:auto;background:#14100b;border:1px solid rgba(255,196,107,.3);border-radius:18px;padding:16px;color:#f3ead8;box-shadow:0 20px 60px rgba(0,0,0,.6)}' +
    '#mirfont-ov .mfh{display:flex;align-items:center;gap:10px;margin-bottom:12px;font:700 12px/1 ui-monospace,Consolas,monospace;letter-spacing:2px;color:#ffc46b}' +
    '#mirfont-ov .mfh b{flex:1}#mirfont-ov .mfh a{cursor:pointer;padding:6px 10px;border-radius:9px;background:rgba(255,255,255,.08);color:#f3ead8}' +
    '#mirfont-ov .mfg{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}' +
    '#mirfont-ov .mfo{cursor:pointer;border:1px solid rgba(255,226,140,.14);border-radius:13px;padding:11px 12px;background:rgba(255,236,170,.03);text-align:left;color:inherit}' +
    '#mirfont-ov .mfo:hover{border-color:rgba(255,196,107,.5)}#mirfont-ov .mfo.on{border-color:#ffc46b;box-shadow:0 0 0 1px #ffc46b inset,0 0 18px rgba(255,180,80,.25)}' +
    '#mirfont-ov .mfo .s{font-size:22px;line-height:1.15;margin:2px 0 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '#mirfont-ov .mfo .n{font:700 10.5px ui-monospace,Consolas,monospace;letter-spacing:1.6px;color:#ffc46b;text-transform:uppercase}' +
    '#mirfont-ov .mfo .d{font:11px/1.35 system-ui,sans-serif;color:#a99a80}';
  var st = document.createElement('style');
  st.id = 'mirfont-css';
  st.textContent = css;
  (document.head || document.documentElement).appendChild(st);

  function byId(id) { for (var i = 0; i < FONTS.length; i++) if (FONTS[i].id === id) return FONTS[i]; return FONTS[0]; }

  function apply(id) {
    id = id || '';
    if (id === cur) return;
    cur = id;
    var root = document.documentElement, cs = getComputedStyle(root);
    VARS.forEach(function (v) {
      v = v.trim();
      if (!(v in orig)) orig[v] = cs.getPropertyValue(v).trim();
      if (!id) root.style.removeProperty(v);
      else root.style.setProperty(v, "'" + byId(id).name + "'," + (orig[v] || 'system-ui,sans-serif'));
    });
    root.setAttribute('data-mirfont', id);
    // same-origin embedded pages (Media Lab iframe) follow instantly
    [].forEach.call(document.querySelectorAll('iframe'), function (f) {
      try { if (f.contentWindow && f.contentWindow.MirFont) f.contentWindow.MirFont.apply(id); } catch (e) {}
    });
  }

  function save(id) {
    apply(id);
    fetch('/api/miros-prefs', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key: 'font', value: {id: id || ''}})}).catch(function () {});
  }

  function sync() {
    fetch('/api/miros-prefs', {cache: 'no-store'}).then(function (r) { return r.json(); })
      .then(function (d) { apply(d && d.font ? d.font.id : ''); }).catch(function () {});
  }

  function openPicker() {
    var old = document.getElementById('mirfont-ov');
    if (old) old.remove();
    var ov = document.createElement('div');
    ov.id = 'mirfont-ov';
    ov.innerHTML = '<div class="mf"><div class="mfh"><b>Aa · MIR FONTS</b><a data-x>✕ CLOSE</a></div><div class="mfg">' +
      FONTS.map(function (f) {
        return '<button class="mfo' + (f.id === (cur || '') ? ' on' : '') + '" data-id="' + f.id + '"><div class="n">' + f.name +
          '</div><div class="s" style="font-family:' + (f.id ? "'" + f.name + "'," : '') + 'system-ui,sans-serif">MirOS Aa 4,561</div><div class="d">' + f.desc + '</div></button>';
      }).join('') + '</div></div>';
    ov.addEventListener('click', function (e) {
      if (e.target === ov || e.target.closest('[data-x]')) { ov.remove(); return; }
      var b = e.target.closest('.mfo');
      if (!b) return;
      save(b.getAttribute('data-id'));
      [].forEach.call(ov.querySelectorAll('.mfo'), function (x) { x.classList.toggle('on', x === b); });
    });
    document.body.appendChild(ov);
  }

  window.MirFont = {list: FONTS, apply: apply, set: save, openPicker: openPicker, current: function () { return cur || ''; }};
  sync();
  setInterval(function () { if (!document.hidden) sync(); }, 20000);   // picks up changes made on other devices
  document.addEventListener('visibilitychange', function () { if (!document.hidden) sync(); });
})();
