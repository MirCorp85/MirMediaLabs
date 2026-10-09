/* MIR MEDIA LABS · SOCIAL panel — VIRAL-Ω growth agent UI. Identical in both lab copies.
   Talks only to /api/social/* (social.py). Nothing posts without the owner pressing Approve. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var mi = function (n) { return window.MI ? MI.html(n) : ''; };
  var VIEW = 'overview', STATS = null, POSTS = [], CHAT = [];

  function api(u, o) {
    o = o || {};
    if (o.body && typeof o.body !== 'string') { o.body = JSON.stringify(o.body); o.headers = { 'Content-Type': 'application/json' }; }
    return fetch(u, o).then(function (r) { return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || r.status); return j; }); });
  }
  function toast(t) { var d = document.createElement('div'); d.className = 'toast'; d.textContent = t; document.body.appendChild(d); setTimeout(function () { d.remove(); }, 3200); }
  function fmt(n) { n = +n || 0; return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(n); }
  function when(ts) { return ts ? new Date(ts * 1000).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''; }
  function last(p, plat) { var h = (p.metrics || {})[plat]; return h && h.length ? h[h.length - 1] : null; }

  function load() {
    return Promise.all([api('api/social/stats'), api('api/social/posts')]).then(function (r) {
      STATS = r[0]; POSTS = r[1].posts; AN = null;
      $('#acct-ig').classList.toggle('on', STATS.accounts.instagram.connected);
      $('#acct-yt').classList.toggle('on', STATS.accounts.youtube.connected);
      var tb = $('#acct-tt'); if (tb) tb.classList.toggle('on', !!(STATS.accounts.tiktok || {}).connected);
      render();
    }).catch(function (e) { $('#view').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  }

  function card(p) {
    var m = '';
    ['instagram', 'youtube', 'tiktok'].forEach(function (pl) {
      var x = last(p, pl), r = (p.remote || {})[pl];
      if (r) m += '<span>' + ({ instagram: 'IG', youtube: 'YT', tiktok: 'TT' })[pl] + ' <a href="' + esc(r.url) + '" target="_blank" style="color:var(--acc)">open</a>' +
        (x ? ' · <b>' + fmt(x.views || x.plays) + '</b> views · <b>' + fmt(x.likes) + '</b> likes' + (x.shares != null ? ' · <b>' + fmt(x.shares) + '</b> shares' : '') : '') + '</span>';
    });
    var a = '';
    if (p.status === 'draft' || p.status === 'failed' || p.status === 'rejected')
      a = '<button class="sb ok" data-a="approve">' + mi('check') + ' Approve</button><button class="sb" data-a="now">' + mi('send') + ' Post now</button>' +
          '<button class="sb" data-a="edit">' + mi('type') + ' Edit</button><button class="sb" data-a="rewrite">' + mi('wand') + ' Rewrite</button>' +
          (p.status === 'draft' ? '<button class="sb bad" data-a="reject">' + mi('x-circle') + '</button>' : '');
    else if (p.status === 'scheduled') a = '<button class="sb" data-a="edit">' + mi('type') + ' Edit</button><button class="sb" data-a="now">' + mi('send') + ' Post now</button><button class="sb bad" data-a="reject">Unschedule</button>';
    else if (p.status === 'published') a = '<button class="sb" data-a="metrics">' + mi('refresh') + ' Refresh stats</button>';
    a += '<span class="sp"></span><button class="sb ic bad" data-a="delete" title="Delete">' + mi('trash') + '</button>';
    return '<div class="card" data-id="' + p.id + '"><div class="media">' +
      (p.video_url ? '<video src="' + esc(p.video_url) + '" poster="' + esc(p.cover_url) + '" muted loop playsinline preload="none" onmouseenter="this.play().catch(function(){})" onmouseleave="this.pause()" onclick="this.paused?this.play().catch(function(){}):this.pause()"></video>' : '<img class="cv" alt="">') +
      '<div class="meta"><span class="st ' + p.status + '">' + esc(p.status) + (p.schedule_at && p.status === 'scheduled' ? ' · ' + when(p.schedule_at) : '') + '</span>' +
      (p.status === 'preparing' ? '<div class="why">VIRAL-Ω is formatting to 9:16 and writing the copy…</div>' : '') +
      '<div class="hook">' + esc(p.hook || p.yt_title || '') + '</div><div class="cap">' + esc(p.caption || '') + '</div>' +
      '<div class="tags">' + (p.hashtags || []).map(function (h) { return '#' + esc(h); }).join(' ') + '</div>' +
      (p.why ? '<div class="why">' + esc(p.why) + '</div>' : '') + (p.error ? '<div class="why" style="color:var(--bad)">' + esc(p.error) + '</div>' : '') +
      '<div class="mx">' + m + '</div><div class="why">' + (p.platforms || []).join(' + ') + (p.pillar ? ' · ' + esc(p.pillar) : '') + '</div></div></div>' +
      '<div class="act">' + a + '</div></div>';
  }

  function render() {
    document.querySelectorAll('.so-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.v === VIEW); });
    var v = $('#view'), h = '';
    if (VIEW === 'queue') {
      var q = POSTS.filter(function (p) { return /draft|preparing|failed/.test(p.status); });
      h = '<div class="row" style="margin-bottom:12px"><button class="sb pri" id="new">' + mi('plus') + ' New post from library</button><span class="dim" style="color:var(--faint)">Drafts wait here for your approval. In the lab chat, add “post it” to send a creation straight here.</span></div>' +
        (q.length ? '<div class="grid">' + q.map(card).join('') + '</div>' : '<div class="empty">No drafts. Make something in the lab, then send it to Social.</div>');
    } else if (VIEW === 'calendar') {
      var s = POSTS.filter(function (p) { return /scheduled|publishing|published/.test(p.status); }).sort(function (a, b) { return (b.schedule_at || b.published_at || 0) - (a.schedule_at || a.published_at || 0); });
      h = s.length ? '<div class="grid">' + s.map(card).join('') + '</div>' : '<div class="empty">Nothing scheduled yet.</div>';
    }     else if (VIEW === 'analytics') h = analytics();
    else if (VIEW === 'skills') h = skillsView();
    else if (VIEW === 'overview') h = overview();
    else if (VIEW === 'agent') h = agent();
    else if (VIEW === 'accounts') h = accountsView();
    v.innerHTML = h;
    if (window.MI && MI.fill) MI.fill(v);
    bind();
  }

  /* ── charts (pure SVG, theme colours) ─────────────────────────────────────────── */
  var C = { ig: '#e1306c', yt: '#ff4433', tt: '#25f4ee', acc: 'var(--acc)', ok: 'var(--ok)' };
  var PNAME = { instagram: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok' }, PCOL = { instagram: '#e1306c', youtube: '#ff4433', tiktok: '#25f4ee' };
  var PAL = ['#d97757', '#5fd38d', '#5b8def', '#e3a949', '#b48cff'];
  function nodata(t) { return '<div class="nodata">' + (t || 'Collecting data — charts fill in as posts get metrics.') + '</div>'; }
  function legend(series) { return '<div class="lg">' + series.map(function (s) { return '<span><i style="background:' + s.color + '"></i>' + esc(s.name) + '</span>'; }).join('') + '</div>'; }
  function lines(series, h) {
    h = h || 160; var all = []; series.forEach(function (s) { all = all.concat(s.pts); });
    if (all.length < 2) return nodata();
    var xs = all.map(function (p) { return p[0]; }), ys = all.map(function (p) { return p[1]; });
    var x0 = Math.min.apply(0, xs), x1 = Math.max.apply(0, xs), y0 = Math.min.apply(0, ys), y1 = Math.max.apply(0, ys);
    if (x1 === x0) x1 = x0 + 1;
    if (y1 === y0) { y1 += 1; y0 = Math.max(0, y0 - 1); }
    var X = function (v) { return 40 + (v - x0) / (x1 - x0) * 550; }, Y = function (v) { return h - 22 - (v - y0) / (y1 - y0) * (h - 34); };
    var g = '';
    for (var i = 0; i <= 3; i++) { var yv = y0 + (y1 - y0) * i / 3; g += '<line x1="40" x2="590" y1="' + Y(yv) + '" y2="' + Y(yv) + '" class="gl"/><text x="34" y="' + (Y(yv) + 4) + '" class="ax" text-anchor="end">' + fmt(Math.round(yv)) + '</text>'; }
    return '<svg class="ch" viewBox="0 0 600 ' + h + '">' + g + series.map(function (s) {
      if (!s.pts.length) return '';
      var d = s.pts.map(function (p, i) { return (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); }).join(' ');
      var last = s.pts[s.pts.length - 1];
      return '<path d="' + d + ' L' + X(last[0]) + ' ' + (h - 22) + ' L' + X(s.pts[0][0]) + ' ' + (h - 22) + 'Z" fill="' + s.color + '" opacity=".08"/>' +
        '<path d="' + d + '" fill="none" stroke="' + s.color + '" stroke-width="2.4" vector-effect="non-scaling-stroke"/>' +
        '<circle cx="' + X(last[0]) + '" cy="' + Y(last[1]) + '" r="3.5" fill="' + s.color + '"/>';
    }).join('') + '</svg>' + legend(series);
  }
  function bars(items, opt) {
    opt = opt || {};
    if (!items.length || !items.some(function (i) { return i.value; })) return nodata(opt.empty);
    var h = opt.h || 150, mx = Math.max.apply(0, items.map(function (i) { return i.value; })) || 1, bw = 550 / items.length;
    var ref = '';
    if (opt.ref) { var ry = h - 22 - opt.ref / mx * (h - 34); ref = '<line x1="40" x2="590" y1="' + ry + '" y2="' + ry + '" class="ref"/><text x="590" y="' + (ry - 4) + '" class="ax" text-anchor="end">median ' + fmt(opt.ref) + '</text>'; }
    return '<svg class="ch" viewBox="0 0 600 ' + h + '">' + items.map(function (it, i) {
      var bh = it.value / mx * (h - 34), x = 40 + i * bw + bw * 0.15;
      return '<rect x="' + x + '" y="' + (h - 22 - bh) + '" width="' + bw * 0.7 + '" height="' + Math.max(1, bh) + '" rx="3" fill="' + (it.color || 'var(--acc)') + '"><title>' + esc(it.title || it.label + ': ' + fmt(it.value)) + '</title></rect>' +
        (items.length <= 24 ? '<text x="' + (x + bw * 0.35) + '" y="' + (h - 8) + '" class="ax" text-anchor="middle">' + esc(it.label) + '</text>' : '');
    }).join('') + ref + '</svg>';
  }
  function donut(parts) {
    var tot = parts.reduce(function (a, p) { return a + p.value; }, 0); if (!tot) return nodata();
    var a0 = -Math.PI / 2, out = '';
    parts.forEach(function (p) {
      var a1 = a0 + p.value / tot * Math.PI * 2, big = a1 - a0 > Math.PI ? 1 : 0;
      out += '<path d="M' + (60 + 50 * Math.cos(a0)) + ' ' + (60 + 50 * Math.sin(a0)) + ' A50 50 0 ' + big + ' 1 ' + (60 + 50 * Math.cos(a1 - 0.0001)) + ' ' + (60 + 50 * Math.sin(a1 - 0.0001)) + '" fill="none" stroke="' + p.color + '" stroke-width="18"/>';
      a0 = a1;
    });
    return '<div class="row" style="gap:18px"><svg viewBox="0 0 120 120" style="width:120px;height:120px">' + out + '<text x="60" y="65" text-anchor="middle" class="dn">' + fmt(tot) + '</text></svg><div>' +
      parts.map(function (p) { return '<div class="lg"><span><i style="background:' + p.color + '"></i>' + esc(p.name) + ' · <b>' + fmt(p.value) + '</b> (' + Math.round(p.value / tot * 100) + '%)</span></div>'; }).join('') + '</div></div>';
  }
  function heat(hours) {
    var mx = Math.max.apply(0, hours.map(function (h) { return h.avg; })) || 1;
    return '<div class="heat">' + hours.map(function (h) { return '<div title="' + h.h + ':00 · avg ' + fmt(h.avg) + ' views · ' + h.n + ' posts" style="background:color-mix(in srgb,var(--acc) ' + Math.round(h.avg / mx * 100) + '%,var(--panel2))"><small>' + h.h + '</small></div>'; }).join('') + '</div>';
  }
  function fser(f, k) { return f.filter(function (r) { return r[k] != null; }).map(function (r) { return [r.t, r[k]]; }); }

  var AN = null;
  function analytics() {
    if (!AN) { api('api/social/analytics').then(function (j) { AN = j; render(); }).catch(function (e) { toast(e.message); }); return '<div class="empty">Loading analytics…</div>'; }
    var f = AN.followers, t = STATS.totals, ps = AN.posts, lf = f.length ? f[f.length - 1] : {}, ff = f.length ? f[0] : {};
    var dl = function (k) { return lf[k] != null && ff[k] != null ? lf[k] - ff[k] : null; };
    var eng = ps.length ? ps.reduce(function (a, p) { return a + p.eng; }, 0) / ps.length : 0;
    var kp = [['IG followers', lf.instagram, dl('instagram')], ['YT subscribers', lf.youtube, dl('youtube')], ['TikTok followers', lf.tiktok, dl('tiktok')], ['Total views', t.views], ['Likes', t.likes],
      ['Shares', t.shares], ['Saves', t.saved], ['Avg engagement', eng ? eng.toFixed(1) + '%' : null], ['Median views/post', AN.median_views]];
    var recent = ps.slice(-5), last30 = ps.slice(-30), off = ps.length - last30.length;
    var plats = Object.keys(AN.platforms).map(function (k) { return { name: PNAME[k] || k, value: AN.platforms[k].views, color: PCOL[k] || C.acc }; });
    return '<div class="kpis">' + kp.map(function (k) {
        return '<div class="kpi"><small>' + k[0] + '</small><b>' + (k[1] == null ? '—' : typeof k[1] === 'string' ? k[1] : fmt(k[1])) + '</b>' +
          (k[2] != null ? '<em class="' + (k[2] >= 0 ? 'up' : 'down') + '">' + (k[2] >= 0 ? '+' : '') + fmt(k[2]) + '</em>' : '') + '</div>'; }).join('') + '</div>' +
      '<div class="g2"><div class="box"><h3>Audience growth</h3>' + lines([{ name: 'Instagram followers', color: C.ig, pts: fser(f, 'instagram') }, { name: 'YouTube subscribers', color: C.yt, pts: fser(f, 'youtube') }, { name: 'TikTok followers', color: C.tt, pts: fser(f, 'tiktok') }]) + '</div>' +
      '<div class="box"><h3>Views by platform</h3>' + donut(plats) + '</div></div>' +
      '<div class="box"><h3>Views per post <span class="hint">green = beat your median</span></h3>' + bars(last30.map(function (p, i) { return { label: '#' + (off + i + 1), value: p.views, color: p.views >= AN.median_views ? C.ok : C.acc, title: p.hook + ' · ' + fmt(p.views) + ' views' }; }), { ref: AN.median_views }) + '</div>' +
      '<div class="g2"><div class="box"><h3>Engagement rate per post</h3>' + bars(last30.map(function (p, i) { return { label: String(off + i + 1), value: p.eng, title: p.hook + ' · ' + p.eng + '%' }; })) + '</div>' +
      '<div class="box"><h3>First-week view curve <span class="hint">last 5 posts · hours after posting</span></h3>' + lines(recent.map(function (p, i) { var c = p.curve.instagram || p.curve.tiktok || p.curve.youtube || []; return { name: (p.hook || '').slice(0, 22), color: PAL[i], pts: c.map(function (x) { return [x.t, x.views]; }) }; })) + '</div></div>' +
      '<div class="g2"><div class="box"><h3>Best hour to post <span class="hint">avg views by publish hour</span></h3>' + heat(AN.hours) + '</div>' +
      '<div class="box"><h3>Best day</h3>' + bars(AN.days.map(function (d) { return { label: d.d, value: d.avg, title: d.n + ' posts · avg ' + fmt(d.avg) }; }), { h: 120 }) + '</div></div>' +
      '<div class="g2"><div class="box"><h3>Content pillars <span class="hint">avg views</span></h3>' + bars(AN.pillars.slice(0, 8).map(function (p) { return { label: p.pillar.slice(0, 12), value: p.avg, title: p.pillar + ' · ' + p.posts + ' posts' }; }), { h: 140 }) + '</div>' +
      '<div class="box"><h3>Top posts</h3>' + (ps.length ? ps.slice().sort(function (a, b) { return b.views - a.views; }).slice(0, 6).map(function (p, i) {
        return '<div class="tp"><span class="rk">' + (i + 1) + '</span><img src="' + esc(p.cover) + '" alt=""><span class="tt">' + esc(p.hook) + '<small>' + esc(p.pillar) + ' · ' + p.eng + '% eng</small></span><b>' + fmt(p.views) + '</b></div>'; }).join('') : nodata('No published posts yet.')) + '</div></div>' +
      '<div class="box"><h3>Weekly report</h3><div id="rep" class="cap" style="max-height:none"></div><button class="sb" id="report">' + mi('book') + ' Write this week’s report</button></div>';
  }

  function overview() {
    var c = STATS.counts, t = STATS.totals, f = STATS.followers || [], lf = f.length ? f[f.length - 1] : {}, a = STATS.accounts;
    var ideas = (STATS.ideas || {}).ideas || [];
    var need = POSTS.filter(function (p) { return p.status === 'draft'; });
    var next = POSTS.filter(function (p) { return p.status === 'scheduled'; }).sort(function (x, y) { return x.schedule_at - y.schedule_at; })[0];
    var miss = [!a.instagram.connected && 'Instagram', !a.youtube.connected && 'YouTube'].filter(Boolean);
    return (miss.length ? '<div class="warnb">' + mi('warn') + ' ' + miss.join(' and ') + ' not connected — <a href="#" data-go="accounts">connect in Accounts</a></div>' : '') +
      '<div class="kpis">' + [['Awaiting approval', c.draft, 'queue'], ['Scheduled', c.scheduled, 'calendar'], ['Published', c.published, 'calendar'], ['IG followers', lf.instagram, 'analytics'], ['YT subscribers', lf.youtube, 'analytics'], ['Total views', t.views, 'analytics']]
        .map(function (k) { return '<div class="kpi click" data-go="' + k[2] + '"><small>' + k[0] + '</small><b>' + (k[1] == null ? '—' : fmt(k[1])) + '</b></div>'; }).join('') + '</div>' +
      '<div class="g2"><div class="box"><h3>Needs you</h3>' + (need.length ? need.slice(0, 4).map(function (p) {
        return '<div class="tp"><img src="' + esc(p.cover_url) + '" alt=""><span class="tt">' + esc(p.hook || '') + '<small>' + (p.platforms || []).join(' + ') + '</small></span><button class="sb ok" data-ap="' + p.id + '">' + mi('check') + ' Approve</button></div>'; }).join('') : nodata('Nothing waiting. Make something in the lab and say “post it”.')) +
      (next ? '<div class="why" style="margin-top:10px">Next post: ' + esc(next.hook || '') + ' · ' + when(next.schedule_at) + '</div>' : '') + '</div>' +
      '<div class="box"><h3>Audience</h3>' + lines([{ name: 'Instagram', color: C.ig, pts: fser(f, 'instagram') }, { name: 'YouTube', color: C.yt, pts: fser(f, 'youtube') }, { name: 'TikTok', color: C.tt, pts: fser(f, 'tiktok') }], 140) + '</div></div>' +
      '<div class="box"><h3>VIRAL-Ω suggests</h3>' + (ideas.length ? ideas.map(function (i, n) { return '<div class="idea"><b>' + esc(i.title) + '</b> — ' + esc(i.hook) + ' <button class="sb" data-make="' + n + '">' + mi('sparkle') + ' Make</button></div>'; }).join('') : nodata('No ideas yet — open the VIRAL-Ω tab.')) + '</div>';
  }

  var SKL = null, SKOUT = null;
  function skillsView() {
    if (!SKL) { api('api/social/skills').then(function (j) { SKL = j.skills; render(); }).catch(function (e) { toast(e.message); }); return '<div class="empty">Loading skills…</div>'; }
    var opts = POSTS.filter(function (p) { return p.hook || p.caption; }).slice(0, 30);
    return '<div class="box"><h3>VIRAL-Ω skills</h3><div class="row"><select class="t" id="sk-post" style="width:auto;max-width:340px"><option value="">Apply to: the account as a whole</option>' +
      opts.map(function (p) { return '<option value="' + p.id + '">' + esc((p.hook || p.caption || p.id).slice(0, 60)) + ' · ' + p.status + '</option>'; }).join('') + '</select>' +
      '<input class="t" id="sk-note" placeholder="extra direction (optional)" style="flex:1;min-width:180px"></div></div>' +
      '<div class="skg">' + SKL.map(function (k) { return '<button class="skc" data-sk="' + k.key + '"><span class="ic">' + mi(k.icon) + '</span><b>' + esc(k.name) + '</b><small>' + esc(k.desc) + '</small></button>'; }).join('') + '</div>' +
      '<div class="box" id="sk-out"' + (SKOUT ? '' : ' hidden') + '>' + (SKOUT ? skillOut(SKOUT) : '') + '</div>';
  }
  function skillOut(o) {
    function val(v) {
      if (Array.isArray(v)) return '<ul>' + v.map(function (x) { return '<li>' + val(x) + '</li>'; }).join('') + '</ul>';
      if (v && typeof v === 'object') return Object.keys(v).map(function (k) {
        var mk = k === 'lab_prompt' ? ' <button class="sb" data-mk="' + esc(v[k]) + '">' + mi('sparkle') + ' Make</button>' : '';
        return '<div><span class="kk">' + esc(k) + ':</span> ' + val(v[k]) + mk + '</div>'; }).join('');
      return esc(v);
    }
    var o2 = {}; Object.keys(o).forEach(function (k) { if (k[0] !== '_') o2[k] = o[k]; });
    return '<h3>' + esc(o._skill || 'Result') + '</h3><div class="sko">' + val(o2) + '</div>';
  }

  function agent() {
    var ideas = (STATS.ideas || {}).ideas || [];
    return '<div class="box"><h3>Today’s ideas from VIRAL-Ω</h3>' + (ideas.length ? ideas.map(function (i, n) {
      return '<div class="idea"><b>' + esc(i.title) + '</b> <span class="dim" style="color:var(--faint)">· ' + esc(i.pillar || '') + ' · ' + esc(i.duration || '') + 's</span><div>Hook: ' + esc(i.hook) + '</div><div class="why">' + esc(i.why) + '</div>' +
        '<div class="row" style="margin-top:6px"><button class="sb pri" data-make="' + n + '">' + mi('sparkle') + ' Make it in the lab</button></div></div>';
    }).join('') : '<div class="dim" style="color:var(--faint)">No ideas yet.</div>') +
      '<button class="sb" id="gen-ideas" style="margin-top:8px">' + mi('refresh') + ' New ideas</button></div>' +
      '<div class="box"><h3>Ask VIRAL-Ω</h3><div class="chat" id="chat">' + CHAT.map(function (m) { return '<div class="msg ' + (m.me ? 'me' : '') + '">' + esc(m.t) + '</div>'; }).join('') + '</div>' +
      '<div class="row" style="margin-top:10px"><input class="t" id="q" placeholder="e.g. Why did yesterday’s reel stall? What should I post tonight?" style="flex:1"><label class="row" style="font-size:12px"><input type="checkbox" id="loc"> local model</label><button class="sb pri" id="ask">' + mi('send') + '</button></div></div>';
  }

  function accountsView() {
    var a = STATS.accounts;
    return '<div class="box"><h3>Instagram ' + esc(a.handle) + '</h3><div class="row">' + (a.instagram.connected ? '<span class="acct on">connected · @' + esc(a.instagram.username) + '</span>' + (a.instagram.expires ? '<span class="why">token renews automatically · expires ' + when(a.instagram.expires) + '</span>' : '') : '<span class="acct">not connected</span>') + '</div>' +
      '<label class="f">Instagram access token — Meta app → Instagram → API setup with Instagram login → Generate token (starts with IG…). An older Facebook-Page token also works.</label><input class="t" id="ig-tok" type="password" autocomplete="off">' +
      '<label class="f">Instagram app ID (optional)</label><input class="t" id="ig-app">' +
      '<label class="f">Instagram app secret (optional — only needed for short 1-hour tokens)</label><input class="t" id="ig-sec" type="password" autocomplete="off">' +
      '<label class="f">Public https address of this lab (Instagram downloads the video from here)</label><input class="t" id="pub" placeholder="https://your-lab.example.com">' +
      '<div class="row" style="margin-top:10px"><button class="sb pri" id="ig-save">Connect Instagram</button></div></div>' +
      '<div class="box"><h3>YouTube</h3><div class="row">' + (a.youtube.connected ? '<span class="acct on">connected · ' + esc(a.youtube.channel) + '</span>' : '<span class="acct">not connected</span>') + '</div>' +
      '<label class="f">Google OAuth client ID (Desktop app; redirect: this lab’s …/api/social/youtube/callback)</label><input class="t" id="yt-id">' +
      '<label class="f">Client secret</label><input class="t" id="yt-sec" type="password" autocomplete="off">' +
      '<div class="row" style="margin-top:10px"><button class="sb" id="yt-save">Save client</button><button class="sb pri" id="yt-go"' + (a.youtube.has_client ? '' : ' disabled') + '>Sign in with Google</button><span class="why">Do this on the lab PC.</span></div></div>' + ttBox();
  }

  function ttBox() {
    var t = STATS.accounts.tiktok || {}, base = t.base || 'https://<set the public address above>';
    return '<div class="box"><h3>TikTok</h3><div class="row">' + (t.connected ? '<span class="acct on">connected · @' + esc(t.username || '') + '</span><button class="sb" id="tt-off">Disconnect</button>' : '<span class="acct">not connected</span>') + '</div>' +
      '<div class="why">TikTok developer app → Login Kit redirect URI: <b>' + esc(base) + '/social/tiktok/callback</b> · Terms: ' + esc(base) + '/social/tiktok/legal/terms · Privacy: ' + esc(base) + '/social/tiktok/legal/privacy</div>' +
      '<label class="f">Client key</label><input class="t" id="tt-key">' +
      '<label class="f">Client secret</label><input class="t" id="tt-sec" type="password" autocomplete="off">' +
      '<div class="row" style="margin-top:10px"><button class="sb" id="tt-save">Save client</button><button class="sb pri" id="tt-go"' + (t.has_client ? '' : ' disabled') + '>Sign in with TikTok</button>' +
      '<span class="why">Until TikTok approves the app, posts only go up as “Only me” and the TikTok account must be set to private.</span></div></div>';
  }

  function act(id, a) {
    var p = POSTS.find(function (x) { return x.id === id; });
    var go = function (u, b) { return api('api/social/posts/' + id + u, { method: 'POST', body: b || {} }).then(load).catch(function (e) { toast(e.message); }); };
    if (a === 'approve') return go('/approve').then(function () { toast('Approved — VIRAL-Ω scheduled it for the best slot'); });
    if (a === 'now') { if (confirm('Publish now to ' + (p.platforms || []).join(' + ') + '?')) go('/publish-now').then(function () { toast('Publishing…'); }); return; }
    if (a === 'reject') return go('/reject');
    if (a === 'metrics') return go('/metrics');
    if (a === 'delete') { if (confirm('Delete this post from Social? (Already-published posts stay on the platforms.)')) go('/delete'); return; }
    if (a === 'rewrite') { var n = prompt('Direction for VIRAL-Ω (optional):', ''); if (n === null) return; toast('Rewriting…'); return go('/rewrite', { note: n }); }
    if (a === 'edit') return editor(p);
  }

  function editor(p) {
    var m = $('#modal'), dt = p.schedule_at ? new Date(p.schedule_at * 1000) : null;
    var loc = dt ? new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
    m.innerHTML = '<div class="in"><div class="row"><b style="flex:1">Edit post</b><button class="sb ic" id="mx">' + mi('close') + '</button></div>' +
      '<div class="row" style="align-items:flex-start;margin-top:10px"><video id="pv" src="' + esc(p.video_url) + '" controls playsinline style="width:160px;aspect-ratio:9/16;border-radius:10px;background:#000"></video>' +
      '<div style="flex:1;min-width:220px"><label class="f">Hook (on-screen, first second)</label><input class="t" id="e-hook" value="' + esc(p.hook || '') + '">' +
      '<label class="f">Instagram caption</label><textarea class="t" id="e-cap">' + esc(p.caption || '') + '</textarea>' +
      '<label class="f">Hashtags (space separated, no #)</label><input class="t" id="e-tags" value="' + esc((p.hashtags || []).join(' ')) + '"></div></div>' +
      '<label class="f">YouTube title</label><input class="t" id="e-yt" value="' + esc(p.yt_title || '') + '">' +
      '<label class="f">YouTube description</label><textarea class="t" id="e-ytd">' + esc(p.yt_description || '') + '</textarea>' +
      '<div class="row"><label class="row" style="font-size:12px"><input type="checkbox" id="e-ig"' + ((p.platforms || []).indexOf('instagram') > -1 ? ' checked' : '') + '> Instagram</label>' +
      '<label class="row" style="font-size:12px"><input type="checkbox" id="e-ytb"' + ((p.platforms || []).indexOf('youtube') > -1 ? ' checked' : '') + '> YouTube</label>' +
      '<label class="row" style="font-size:12px"><input type="checkbox" id="e-tt"' + ((p.platforms || []).indexOf('tiktok') > -1 ? ' checked' : '') + '> TikTok</label>' +
      '<label class="f" style="margin:0">Post at</label><input class="t" type="datetime-local" id="e-at" value="' + loc + '" style="width:auto">' +
      '<button class="sb" id="e-cover">' + mi('camera') + ' Use current frame as cover</button></div>' +
      '<div id="e-ttbox" class="box" style="margin-top:12px" hidden></div>' +
      '<div class="row" style="margin-top:14px;justify-content:flex-end"><button class="sb" id="e-cancel">Cancel</button><button class="sb pri" id="e-save">Save</button></div></div>';
    m.hidden = false;
    var T = Object.assign({}, p.tiktok || {});
    var ttBoxDraw = function (ci) {
      var bx = $('#e-ttbox'); if (!bx) return;
      bx.hidden = !$('#e-tt').checked; if (bx.hidden) return;
      if (!ci) { bx.innerHTML = '<div class="why">Checking your TikTok account…</div>'; api('api/social/tiktok/creator').then(ttBoxDraw).catch(function (e) { bx.innerHTML = '<div class="warnb">' + esc(e.message) + ' — connect TikTok in Accounts</div>'; }); return; }
      var opts = ci.privacy_level_options || [], lab = { PUBLIC_TO_EVERYONE: 'Everyone', MUTUAL_FOLLOW_FRIENDS: 'Friends', FOLLOWER_OF_CREATOR: 'Followers', SELF_ONLY: 'Only me' };
      var ck = function (id, on, dis, txt) { return '<label class="row" style="font-size:12px' + (dis ? ';opacity:.45' : '') + '"><input type="checkbox" id="' + id + '"' + (on && !dis ? ' checked' : '') + (dis ? ' disabled' : '') + '> ' + txt + '</label>'; };
      bx.innerHTML = '<h3>TikTok · posting as ' + esc(ci.creator_nickname || ci.creator_username || '') + '</h3>' +
        '<label class="f">Who can see this video</label><select class="t" id="tt-priv"><option value="">Choose…</option>' + opts.map(function (o) { return '<option value="' + o + '"' + (T.privacy_level === o ? ' selected' : '') + '>' + (lab[o] || o) + '</option>'; }).join('') + '</select>' +
        '<div class="row" style="margin-top:8px">' + ck('tt-cm', T.allow_comment, ci.comment_disabled, 'Allow comments') + ck('tt-du', T.allow_duet, ci.duet_disabled, 'Allow Duet') + ck('tt-st', T.allow_stitch, ci.stitch_disabled, 'Allow Stitch') + '</div>' +
        '<div class="row" style="margin-top:8px">' + ck('tt-dis', T.disclose, false, 'Disclose commercial content') + '</div>' +
        '<div class="row" id="tt-disrow"' + (T.disclose ? '' : ' hidden') + '>' + ck('tt-org', T.brand_organic, false, 'Your brand') + ck('tt-bc', T.brand_content, false, 'Branded content (paid partnership)') + '</div>' +
        '<div class="why" id="tt-label"></div>' +
        '<label class="row" style="font-size:12px;margin-top:8px"><input type="checkbox" id="tt-ok"' + (T.consent ? ' checked' : '') + '> By posting, I agree to TikTok’s <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" style="color:var(--acc)">Music Usage Confirmation</a>' +
        '<span id="tt-bcp"></span></label><div class="why">Labelled as AI-generated content. Video limit: ' + (ci.max_video_post_duration_sec || '?') + 's.</div>';
      var lbl = function () {
        var o = $('#tt-org').checked, b = $('#tt-bc').checked, d = $('#tt-dis').checked;
        $('#tt-disrow').hidden = !d;
        $('#tt-label').textContent = !d ? '' : b ? 'Your video will be labelled “Paid partnership”.' : o ? 'Your video will be labelled “Promotional content”.' : 'Pick at least one.';
        $('#tt-bcp').innerHTML = d && b ? ' and <a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" style="color:var(--acc)">Branded Content Policy</a>' : '';
        var so = $('#tt-priv').querySelector('option[value="SELF_ONLY"]'); if (so) { so.disabled = d && b; if (so.selected && so.disabled) $('#tt-priv').value = ''; }
      };
      ['tt-dis', 'tt-org', 'tt-bc'].forEach(function (i) { $('#' + i).onchange = lbl; }); lbl();
    };
    $('#e-tt').onchange = function () { ttBoxDraw(); };
    ttBoxDraw();
    if (window.MI && MI.fill) MI.fill(m);
    var close = function () { m.hidden = true; m.innerHTML = ''; };
    $('#mx').onclick = $('#e-cancel').onclick = close;
    $('#e-cover').onclick = function () { api('api/social/posts/' + p.id, { method: 'POST', body: { cover_at: $('#pv').currentTime } }).then(function () { toast('Cover set'); }); };
    $('#e-save').onclick = function () {
      var pl = []; if ($('#e-ig').checked) pl.push('instagram'); if ($('#e-ytb').checked) pl.push('youtube'); if ($('#e-tt').checked) pl.push('tiktok');
      var b = { hook: $('#e-hook').value, caption: $('#e-cap').value, hashtags: $('#e-tags').value.split(/[\s,#]+/).filter(Boolean),
        yt_title: $('#e-yt').value, yt_description: $('#e-ytd').value, platforms: pl };
      if ($('#tt-priv')) b.tiktok = { privacy_level: $('#tt-priv').value, allow_comment: $('#tt-cm').checked, allow_duet: $('#tt-du').checked, allow_stitch: $('#tt-st').checked,
        disclose: $('#tt-dis').checked, brand_organic: $('#tt-dis').checked && $('#tt-org').checked, brand_content: $('#tt-dis').checked && $('#tt-bc').checked, consent: $('#tt-ok').checked };
      if ($('#e-at').value) b.schedule_at = new Date($('#e-at').value).getTime() / 1000;
      api('api/social/posts/' + p.id, { method: 'POST', body: b }).then(function () { close(); load(); toast('Saved'); }).catch(function (e) { toast(e.message); });
    };
  }

  function pickLibrary() {
    api('api/library?limit=200').then(function (j) {
      var items = (j.items || j.library || j || []).filter(function (x) { return /video|image/.test(x.kind || ''); }).slice(0, 60);
      var m = $('#modal');
      m.innerHTML = '<div class="in"><div class="row"><b style="flex:1">Pick a creation to post</b><button class="sb ic" id="mx">' + mi('close') + '</button></div>' +
        '<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr));margin-top:12px">' + items.map(function (x) {
          return '<button class="card" data-pick="' + esc(x.name) + '" style="cursor:pointer;padding:0;border:1px solid var(--line)"><img src="' + esc(x.thumb || ('thumb/' + x.name)) + '" style="width:100%;aspect-ratio:1;object-fit:cover"><span style="padding:6px;font-size:11px;text-align:left">' + esc((x.prompt || x.name).slice(0, 60)) + '</span></button>';
        }).join('') + '</div><label class="f">Brief for VIRAL-Ω (optional)</label><input class="t" id="brief" placeholder="angle, series name, call to action…"></div>';
      m.hidden = false; if (window.MI && MI.fill) MI.fill(m);
      $('#mx').onclick = function () { m.hidden = true; };
      m.querySelectorAll('[data-pick]').forEach(function (b) {
        b.onclick = function () {
          api('api/social/draft', { method: 'POST', body: { library_ref: b.dataset.pick, brief: $('#brief').value } })
            .then(function () { m.hidden = true; toast('VIRAL-Ω is preparing the post…'); load(); }).catch(function (e) { toast(e.message); });
        };
      });
    }).catch(function (e) { toast(e.message); });
  }

  function bind() {
    document.querySelectorAll('.card[data-id] [data-a]').forEach(function (b) { b.onclick = function () { act(b.closest('.card').dataset.id, b.dataset.a); }; });
    var n = $('#new'); if (n) n.onclick = pickLibrary;
    document.querySelectorAll('[data-go]').forEach(function (b) { b.onclick = function (e) { e.preventDefault(); VIEW = b.dataset.go; render(); }; });
    document.querySelectorAll('[data-ap]').forEach(function (b) { b.onclick = function () { act(b.dataset.ap, 'approve'); }; });
    document.querySelectorAll('[data-sk]').forEach(function (b) {
      b.onclick = function () {
        document.querySelectorAll('.skc').forEach(function (x) { x.disabled = true; });
        var o = $('#sk-out'); o.hidden = false; o.innerHTML = '<div class="nodata">VIRAL-Ω is working…</div>';
        api('api/social/skills/' + b.dataset.sk, { method: 'POST', body: { post: $('#sk-post').value || null, note: $('#sk-note').value } })
          .then(function (j) { SKOUT = j; }).catch(function (e) { SKOUT = { _skill: 'Error', error: e.message }; }).then(render);
      };
    });
    document.querySelectorAll('[data-mk]').forEach(function (b) {
      b.onclick = function () { if (window.parent !== window) window.parent.postMessage({ mml: 'social-make', prompt: b.dataset.mk, social: { platforms: ['instagram', 'youtube'] } }, '*'); else toast('Open Social from the lab to send this to the chat'); };
    });
    var r = $('#report'); if (r) r.onclick = function () { r.disabled = true; $('#rep').textContent = 'VIRAL-Ω is reviewing the week…'; api('api/social/report', { method: 'POST' }).then(function (j) { $('#rep').textContent = j.report; }).catch(function (e) { $('#rep').textContent = e.message; }).then(function () { r.disabled = false; }); };
    var gi = $('#gen-ideas'); if (gi) gi.onclick = function () { gi.disabled = true; toast('Thinking up ideas…'); api('api/social/ideas', { method: 'POST' }).then(load).catch(function (e) { toast(e.message); gi.disabled = false; }); };
    document.querySelectorAll('[data-make]').forEach(function (b) {
      b.onclick = function () {
        var i = STATS.ideas.ideas[+b.dataset.make];
        var msg = { mml: 'social-make', prompt: i.lab_prompt, social: { platforms: ['instagram', 'youtube'] } };
        if (window.parent !== window) { window.parent.postMessage(msg, '*'); } else { toast('Open Social from the lab to send this to the chat'); }
      };
    });
    var ask = $('#ask'); if (ask) {
      var send = function () {
        var q = $('#q').value.trim(); if (!q) return;
        CHAT.push({ me: 1, t: q }); CHAT.push({ t: '…' }); render();
        api('api/social/ask', { method: 'POST', body: { q: q, local: $('#loc') && $('#loc').checked } })
          .then(function (j) { CHAT[CHAT.length - 1].t = j.answer; }).catch(function (e) { CHAT[CHAT.length - 1].t = e.message; }).then(render);
      };
      ask.onclick = send; $('#q').onkeydown = function (e) { if (e.key === 'Enter') send(); };
    }
    var igs = $('#ig-save'); if (igs) igs.onclick = function () {
      var b = { public_base: $('#pub').value }; if ($('#ig-tok').value) { b.ig_token = $('#ig-tok').value; b.ig_app_id = $('#ig-app').value; b.ig_app_secret = $('#ig-sec').value; }
      api('api/social/accounts', { method: 'POST', body: b }).then(function () { toast('Saved'); load(); }).catch(function (e) { toast(e.message); });
    };
    var ys = $('#yt-save'); if (ys) ys.onclick = function () { api('api/social/accounts', { method: 'POST', body: { yt_client_id: $('#yt-id').value, yt_client_secret: $('#yt-sec').value } }).then(function () { toast('Saved'); load(); }).catch(function (e) { toast(e.message); }); };
    var yg = $('#yt-go'); if (yg) yg.onclick = function () { window.open(location.hostname === '127.0.0.1' || location.hostname === 'localhost' ? 'api/social/youtube/connect' : 'http://127.0.0.1:5400/api/social/youtube/connect', '_blank'); };
    var tts = $('#tt-save'); if (tts) tts.onclick = function () { api('api/social/accounts', { method: 'POST', body: { tt_client_key: $('#tt-key').value, tt_client_secret: $('#tt-sec').value } }).then(function () { toast('Saved'); load(); }).catch(function (e) { toast(e.message); }); };
    var ttg = $('#tt-go'); if (ttg) ttg.onclick = function () { window.open('api/social/tiktok/connect', '_blank'); };
    var tto = $('#tt-off'); if (tto) tto.onclick = function () { if (confirm('Disconnect TikTok? (Deletes the saved sign-in.)')) api('api/social/tiktok/disconnect', { method: 'POST' }).then(load); };
    var pub = $('#pub'); if (pub) api('api/social/accounts').then(function (a) { pub.value = a.public_base || ''; });
  }

  document.querySelectorAll('.so-tabs button').forEach(function (b) { b.onclick = function () { VIEW = b.dataset.v; render(); }; });
  $('#so-close').onclick = function () { if (window.MMLApp && MMLApp.close) return MMLApp.close(''); if (window.parent !== window) window.parent.postMessage({ mml: 'social-close' }, '*'); else history.back(); };
  window.addEventListener('message', function (e) { var d = e.data || {}; if (d.mml === 'social-toast') { toast(d.text); setTimeout(load, 1500); } });
  var t = new URLSearchParams(location.search).get('v'); if (t) VIEW = t;
  load();
  setInterval(function () { if (!document.hidden && $('#modal').hidden && VIEW !== 'agent' && VIEW !== 'accounts' && VIEW !== 'skills' && VIEW !== 'analytics') load(); }, 20000);
})();
