/* MIR MEDIA LABS · SOCIAL panel — VIRAL-Ω growth agent UI.
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
  function toast(t) { var d = document.createElement('div'); d.className = 'toast'; d.textContent = t; document.body.appendChild(d); setTimeout(function () { d.remove(); }, Math.max(3200, String(t).length * 70)); }
  function fmt(n) { n = +n || 0; return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(n); }
  function when(ts) { return ts ? new Date(ts * 1000).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''; }
  function last(p, plat) { var h = (p.metrics || {})[plat]; return h && h.length ? h[h.length - 1] : null; }

  function load() {
    return Promise.all([api('api/social/stats'), api('api/social/posts')]).then(function (r) {
      STATS = r[0]; POSTS = r[1].posts; if (AN && Date.now() - AN._t > 120000) AN = null;   // analytics is heavy: refresh every 2 min
      $('#acct-ig').classList.toggle('on', STATS.accounts.instagram.connected);
      $('#acct-yt').classList.toggle('on', STATS.accounts.youtube.connected);
      var tb = $('#acct-tt'); if (tb) tb.classList.toggle('on', !!(STATS.accounts.tiktok || {}).connected);
      var fbb = $('#acct-fb'); if (fbb) fbb.classList.toggle('on', !!(STATS.accounts.facebook || {}).connected);
      render();
      clearTimeout(load.prep);                   // a post is still being formatted → check again soon, not in 20 s
      if (POSTS.some(function (p) { return p.status === 'preparing'; })) load.prep = setTimeout(function again() { if (canRefresh()) load(); else load.prep = setTimeout(again, 4000); }, 4000);
    }).catch(function (e) {                      // server restarting / phone switching networks: keep what's shown and retry
      if (!STATS) $('#view').innerHTML = '<div class="empty">' + esc(e.message) + ' — retrying…</div>';
      clearTimeout(load.retry); load.retry = setTimeout(load, 5000);
    });
  }

  function card(p, sub) {
    var m = '';
    ['instagram', 'youtube', 'tiktok', 'facebook'].forEach(function (pl) {
      var x = last(p, pl), r = (p.remote || {})[pl];
      if (r && r.inbox && !/^\d+$/.test(r.id || '')) { m += '<span>TT sent to your TikTok inbox — publish it in the TikTok app' + (p.video_url ? ' · not there? <a href="' + esc(p.video_url) + '" download="' + p.id + '.mp4" style="color:var(--acc)">save video</a> and upload it by hand — it links back here on its own' : '') + '</span>'; return; }   // real video id arrives once it's posted
      if (r) m += '<span>' + ({ instagram: 'IG', youtube: 'YT', tiktok: 'TT', facebook: 'FB' })[pl] + ' <a href="' + esc(r.url) + '" target="_blank" style="color:var(--acc)">open</a>' +
        (x ? ' · <b>' + fmt(x.views || x.plays) + '</b> views · <b>' + fmt(x.likes) + '</b> likes' + (x.shares != null ? ' · <b>' + fmt(x.shares) + '</b> shares' : '') : '') + '</span>';
    });
    var a = '';
    if (p.status === 'draft' || p.status === 'failed' || p.status === 'rejected')
      a = '<button class="sb ok" data-a="approve">' + mi('check') + ' Approve</button><button class="sb" data-a="now">' + mi('send') + ' Post now</button>' +
          '<button class="sb" data-a="edit">' + mi('type') + ' Edit</button><button class="sb" data-a="rewrite">' + mi('wand') + ' Rewrite</button>' +
          (p.status === 'draft' ? '<button class="sb bad" data-a="reject">' + mi('x-circle') + '</button>' : '');
    else if (p.status === 'scheduled') a = '<button class="sb" data-a="edit">' + mi('type') + ' Edit</button><button class="sb" data-a="now">' + mi('send') + ' Post now</button><button class="sb bad" data-a="reject">Unschedule</button>';
    else if (p.status === 'published') a = '<button class="sb" data-a="metrics">' + mi('refresh') + ' Refresh stats</button>' +
      (p.video_url ? '<button class="sb" data-a="repost" title="Post this video again on another platform">' + mi('forward') + ' Repost</button>' : '');
    a += '<span class="sp"></span><button class="sb ic bad" data-a="delete" title="Delete">' + mi('trash') + '</button>';
    var st = '<span class="st ' + p.status + '">' + esc(p.status) + (p.schedule_at && p.status === 'scheduled' ? ' · ' + when(p.schedule_at) : '') + '</span>';
    if (sub) return '<div class="card sub" data-id="' + p.id + '"><div class="meta"><div class="why">' + mi('forward') + ' repost · ' + pchips(p.platforms) + ' ' + st +
      (p.published_at ? ' · ' + esc(when(p.published_at)) : '') + '</div>' + (p.error ? '<div class="why" style="color:var(--bad)">' + esc(p.error) + '</div>' : '') +
      '<div class="mx">' + m + '</div></div><div class="act">' + a + '</div></div>';
    return '<div class="card" data-id="' + p.id + '"><div class="media">' +
      (p.video_url ? '<div class="pvw" data-pv="' + p.id + '" title="Preview"><img class="cv" src="' + esc(p.cover_url) + '" alt=""><span class="play">' + mi('play') + '</span></div>' : '<img class="cv" alt="">') +
      '<div class="meta">' + steps(p) + st +
      (p.status === 'preparing' ? '<div class="why">VIRAL-Ω is formatting to 9:16 and writing the copy…</div><div class="prep"><i></i></div>' : '') +
      '<div class="hook">' + esc(p.hook || p.yt_title || '') + '</div><div class="cap">' + esc(p.caption || '') + '</div>' +
      '<div class="tags">' + (p.hashtags || []).map(function (h) { return '#' + esc(h); }).join(' ') + '</div>' +
      (p.why ? '<div class="why">' + esc(p.why) + '</div>' : '') + (p.error ? '<div class="why" style="color:var(--bad)">' + esc(p.error) + '</div>' : '') +
      '<div class="mx">' + m + '</div><div class="why">' + (p.platforms || []).join(' + ') + (p.pillar ? ' · ' + esc(p.pillar) : '') +
      (p.repost_of ? ' · ' + mi('forward') + ' repost' + ((p.repost_from || []).length ? ' (was on ' + esc(p.repost_from.join(' + ')) + ')' : '') : '') +
      ((p.reposts || []).length ? ' · reposted ×' + p.reposts.length : '') + '</div></div></div>' +
      (window.VIRAL ? VIRAL.cardExtra(p) : '') + '<div class="act">' + a + '</div></div>';
  }

  // every post of the same video (reposts + other drafts of the same library file) stays together as ONE card
  function famKey(p) {
    for (var i = 0; p.repost_of && i < 9; i++) { var o = POSTS.find(function (x) { return x.id === p.repost_of; }); if (!o) break; p = o; }
    return p.library_ref || p.id;
  }
  function families(list) {                 // keeps list order (by each video's first post in it); original first inside
    var by = {}, out = [];
    list.forEach(function (p) { var k = famKey(p); if (!by[k]) out.push(by[k] = []); by[k].push(p); });
    out.forEach(function (f) { f.sort(function (a, b) { return (a.created || 0) - (b.created || 0); }); });
    return out;
  }
  function famCard(f) { return f.length < 2 ? card(f[0]) : '<div class="fam">' + card(f[0]) + f.slice(1).map(function (p) { return card(p, true); }).join('') + '</div>'; }

  function render() {
    document.querySelectorAll('.so-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.v === VIEW); });
    var v = $('#view'), h = '';
    if (VIEW === 'queue') {
      var q = POSTS.filter(function (p) { return /draft|preparing|failed/.test(p.status); });
      h = '<div class="row" style="margin-bottom:12px"><button class="sb pri" id="new">' + mi('plus') + ' New post from library</button><button class="sb" id="attach">' + mi('upload') + ' Attach file</button><input type="file" id="attach-f" accept="video/*,image/*" hidden><span class="dim" style="color:var(--faint)">Drafts wait here for your approval. In the lab chat, add “post it” to send a creation straight here.</span></div>' +
        (q.length ? '<div class="grid">' + q.map(card).join('') + '</div>' : '<div class="empty">No drafts. Make something in the lab, then send it to Social.</div>');
    } else if (VIEW === 'calendar') {
      var s = POSTS.filter(function (p) { return /scheduled|publishing|published/.test(p.status); }).sort(function (a, b) { return (b.schedule_at || b.published_at || 0) - (a.schedule_at || a.published_at || 0); });
      var live = s.filter(function (p) { return p.remote && Object.keys(p.remote).length; }).length;
      h = '<div class="row" style="margin-bottom:12px"><span class="dim" style="color:var(--faint);flex:1">' +
        (live ? live + ' live post' + (live > 1 ? 's' : '') + ' — pull the latest views, likes & shares from every platform.' : 'Scheduled & published posts. Live stats appear once a post goes up.') + '</span>' +
        (live ? '<button class="sb pri" id="refresh-all">' + mi('refresh') + ' Refresh all stats</button>' : '') + '</div>' +
        (s.length ? '<div class="grid">' + families(s).map(famCard).join('') + '</div>' : '<div class="empty">Nothing scheduled yet.</div>');
    }     else if (VIEW === 'analytics') h = analytics();
    else if (VIEW === 'skills') h = skillsView();
    else if (VIEW === 'overview') h = overview();
    else if (VIEW === 'agent') h = agent();
    else if (VIEW === 'accounts') h = accountsView();
    else if (window.VIRAL && VIRAL.views[VIEW]) h = VIRAL.views[VIEW]();
    if (window.VIRAL && VIRAL.wrap[VIEW]) h = VIRAL.wrap[VIEW](h);      // brief on Overview, insights under Analytics
    v.innerHTML = h;
    if (window.MI && MI.fill) MI.fill(v);
    bind();
    if (window.VIRAL) VIRAL.bind(VIEW);
  }

  /* ── charts (pure SVG, theme colours) ─────────────────────────────────────────── */
  var C = { ig: '#e1306c', yt: '#ff4433', tt: '#25f4ee', acc: 'var(--acc)', ok: 'var(--ok)' };
  var PNAME = { instagram: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok', facebook: 'Facebook' }, PCOL = { instagram: '#e1306c', youtube: '#ff4433', tiktok: '#25f4ee', facebook: '#1877f2' };
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
    if (!AN) { getAN(); return '<div class="empty">Loading analytics…</div>'; }
    var f = AN.followers, t = STATS.totals, ps = AN.posts, lf = f.length ? f[f.length - 1] : {}, ff = f.length ? f[0] : {};
    var dl = function (k) { return lf[k] != null && ff[k] != null ? lf[k] - ff[k] : null; };
    var eng = ps.length ? ps.reduce(function (a, p) { return a + p.eng; }, 0) / ps.length : 0;
    var kp = [['IG followers', lf.instagram, dl('instagram')], ['YT subscribers', lf.youtube, dl('youtube')], ['TikTok followers', lf.tiktok, dl('tiktok')], ['Total views', t.views], ['Likes', t.likes],
      ['Shares', t.shares], ['Saves', t.saved], ['Avg engagement', eng ? eng.toFixed(1) + '%' : null], ['Median views/post', AN.median_views]];
    var recent = ps.slice(-5), last30 = ps.slice(-30), off = ps.length - last30.length;
    var plats = Object.keys(AN.platforms).map(function (k) { return { name: PNAME[k] || k, value: AN.platforms[k].views, color: PCOL[k] || C.acc }; });
    var sk = { 'IG followers': ['instagram', C.ig], 'YT subscribers': ['youtube', C.yt], 'TikTok followers': ['tiktok', C.tt] };
    return '<div class="kpis">' + kp.map(function (k) {
        var z = sk[k[0]]; return tile(k[0], k[1], { delta: k[2], color: z && z[1], spark: z && spark(fser(f, z[0]), z[1]) }); }).join('') + '</div>' +
      '<div class="box"><h3>Posting activity <span class="hint">last 16 weeks · consistency drives reach</span></h3>' + activity(ps, 16) + '</div>' +
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

  var STAGES = [['preparing', 'Preparing', 'hourglass', 'queue'], ['draft', 'Needs approval', 'check-circle', 'queue'], ['scheduled', 'Scheduled', 'clock', 'calendar'], ['published', 'Live', 'live', 'analytics']];
  function steps(p) {                        // where this post is in the flow: Preparing → Approval → Scheduled → Live
    var i = { preparing: 0, draft: 1, failed: 1, rejected: 1, scheduled: 2, approved: 2, publishing: 2, published: 3 }[p.status];
    if (i == null) return '';
    return '<div class="steps">' + STAGES.map(function (st, n) { return '<span class="' + (n < i ? 'done' : n === i ? 'now' + (/failed|rejected/.test(p.status) ? ' bad' : '') : '') + '" title="' + st[1] + '"></span>'; }).join('') + '</div>';
  }
  function getAN() {
    if (getAN.busy) return; getAN.busy = 1;
    api('api/social/analytics').then(function (j) { j._t = Date.now(); AN = j; getAN.busy = 0; if (VIEW === 'overview' || VIEW === 'analytics') render(); })
      .catch(function (e) { getAN.busy = 0; toast(e.message); });
  }
  function spark(pts, color) {               // tiny trend line for a KPI tile
    if (!pts || pts.length < 2) return '';
    var ys = pts.map(function (p) { return p[1]; }), y0 = Math.min.apply(0, ys), y1 = Math.max.apply(0, ys), x0 = pts[0][0], x1 = pts[pts.length - 1][0];
    if (y1 === y0) { y1 += 1; y0 -= 1; }
    var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + (2 + (p[0] - x0) / ((x1 - x0) || 1) * 96).toFixed(1) + ' ' + (26 - (p[1] - y0) / (y1 - y0) * 22).toFixed(1); }).join(' ');
    return '<svg class="spk" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>';
  }
  function tile(label, value, opt) {
    opt = opt || {};
    var d = opt.delta;
    return '<div class="kpi' + (opt.go ? ' click" data-go="' + opt.go : '') + '"' + (opt.color ? ' style="--kc:' + opt.color + '"' : '') + '>' +
      '<small>' + (opt.icon ? mi(opt.icon) + ' ' : '') + label + '</small><b>' + (value == null ? '—' : typeof value === 'string' ? value : fmt(value)) + '</b>' +
      (d != null && d !== 0 ? '<em class="' + (d > 0 ? 'up' : 'down') + '">' + (d > 0 ? '+' : '') + fmt(d) + (opt.dlabel ? ' ' + opt.dlabel : '') + '</em>' : opt.sub ? '<em>' + esc(opt.sub) + '</em>' : '') +
      (opt.spark || '') + '</div>';
  }
  function pchips(pl) { return (pl || []).map(function (x) { return '<span class="pc" style="--pc:' + (PCOL[x] || 'var(--acc)') + '">' + ({ instagram: 'IG', youtube: 'YT', tiktok: 'TT', facebook: 'FB' }[x] || x) + '</span>'; }).join(''); }
  function since(f, k, days) {               // follower change over the last N days
    var cut = Date.now() / 1000 - days * 86400, s = f.filter(function (r) { return r[k] != null; });
    if (s.length < 2) return null;
    var base = s.filter(function (r) { return r.t <= cut; }).pop() || s[0];
    return s[s.length - 1][k] - base[k];
  }
  function stacked(cols, h) {                // views per day, one segment per platform
    h = h || 170;
    var mx = Math.max.apply(0, cols.map(function (c) { return c.total; })) || 0;
    if (!mx) return nodata('No views in this window yet.');
    var bw = 550 / cols.length, g = '';
    for (var i = 1; i <= 3; i++) { var yv = mx * i / 3, y = h - 22 - yv / mx * (h - 34); g += '<line x1="40" x2="590" y1="' + y + '" y2="' + y + '" class="gl"/><text x="34" y="' + (y + 4) + '" class="ax" text-anchor="end">' + fmt(Math.round(yv)) + '</text>'; }
    return '<svg class="ch" viewBox="0 0 600 ' + h + '">' + g + cols.map(function (c, i) {
      var x = 40 + i * bw + bw * 0.16, y = h - 22, out = '';
      Object.keys(PCOL).concat(['other']).forEach(function (k) {
        var v = c.by[k] || 0; if (!v) return;
        var bh = v / mx * (h - 34); y -= bh;
        out += '<rect x="' + x + '" y="' + y + '" width="' + bw * 0.68 + '" height="' + bh + '" fill="' + (PCOL[k] || 'var(--faint)') + '"><title>' + esc(c.label + ' · ' + (PNAME[k] || 'Other') + ': ' + fmt(v)) + '</title></rect>';
      });
      return out + '<text x="' + (x + bw * 0.34) + '" y="' + (h - 8) + '" class="ax" text-anchor="middle">' + esc(c.label) + '</text>';
    }).join('') + '</svg>' + legend(Object.keys(PCOL).map(function (k) { return { name: PNAME[k], color: PCOL[k] }; }));
  }
  function dayKey(t) { var d = new Date(t * 1000); return d.getFullYear() + '-' + d.getMonth() + '-' + d.getDate(); }
  function viewsByDay(ps, n) {
    var cols = [], idx = {};
    for (var i = n - 1; i >= 0; i--) {
      var d = new Date(Date.now() - i * 86400e3), k = dayKey(d.getTime() / 1000);
      idx[k] = cols.length; cols.push({ label: i === 0 ? 'today' : (n > 10 ? String(d.getDate()) : d.toLocaleDateString([], { weekday: 'short' })), by: {}, total: 0 });
    }
    ps.forEach(function (p) {
      var c = cols[idx[dayKey(p.t)]]; if (!c) return;
      var got = 0;
      Object.keys(p.curve || {}).forEach(function (pl) { var cv = p.curve[pl]; if (cv && cv.length) { var v = cv[cv.length - 1].views || 0; c.by[pl] = (c.by[pl] || 0) + v; got += v; } });
      if (p.views > got) c.by.other = (c.by.other || 0) + p.views - got;
      c.total += Math.max(p.views, got);
    });
    return cols;
  }
  function activity(ps, weeks) {             // GitHub-style posting calendar
    var cnt = {}; ps.forEach(function (p) { var k = dayKey(p.t); cnt[k] = (cnt[k] || 0) + 1; });
    var now = new Date(), start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay() - (weeks - 1) * 7), cells = '', streak = 0;
    for (var i = 0; i < weeks * 7; i++) {
      var d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      if (d > now) { cells += '<i class="fut"></i>'; continue; }
      var n = cnt[dayKey(d.getTime() / 1000)] || 0;
      cells += '<i class="l' + Math.min(3, n) + '" title="' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' · ' + n + ' post' + (n === 1 ? '' : 's') + '"></i>';
    }
    for (var j = 0; j < 365; j++) { if (cnt[dayKey(Date.now() / 1000 - j * 86400)]) streak++; else if (j) break; }
    return '<div class="cal" style="grid-template-columns:repeat(' + weeks + ',15px)">' + cells + '</div>' +
      '<div class="lg"><span>Less</span><span><i class="l0"></i><i class="l1"></i><i class="l2"></i><i class="l3"></i></span><span>More</span><span class="sp"></span><span>' + (streak ? '<b>' + streak + '</b>-day posting streak' : 'No post today yet') + '</span></div>';
  }

  function overview() {
    if (!AN) getAN();
    var c = STATS.counts, t = STATS.totals, f = STATS.followers || [], lf = f.length ? f[f.length - 1] : {}, a = STATS.accounts;
    var ideas = (STATS.ideas || {}).ideas || [];
    var need = POSTS.filter(function (p) { return p.status === 'draft' || p.status === 'failed'; });
    var sched = POSTS.filter(function (p) { return /scheduled|approved|publishing/.test(p.status); }).sort(function (x, y) { return (x.schedule_at || 0) - (y.schedule_at || 0); });
    var miss = [!a.instagram.connected && 'Instagram', !a.youtube.connected && (a.youtube.expired ? 'YouTube (sign-in expired)' : 'YouTube')].filter(Boolean);
    var eng = t.views ? ((t.likes + t.comments + t.shares + t.saved) / t.views * 100).toFixed(1) + '%' : null;
    var ps = AN ? AN.posts : [], wk = Date.now() / 1000 - 7 * 86400;
    var v7 = ps.filter(function (p) { return p.t >= wk; }).reduce(function (s, p) { return s + p.views; }, 0);

    var pipe = '<div class="pipe">' + STAGES.map(function (st, i) {
      var list = POSTS.filter(function (p) { return st[0] === 'draft' ? /draft|failed/.test(p.status) : st[0] === 'scheduled' ? /scheduled|approved|publishing/.test(p.status) : p.status === st[0]; })
        .sort(function (x, y) { return (y.updated || 0) - (x.updated || 0); });
      var n = st[0] === 'published' ? c.published : list.length, failed = st[0] === 'draft' ? c.failed : 0;
      return (i ? '<span class="arr">' + mi('chevron-right') + '</span>' : '') +
        '<div class="stage ' + st[0] + (n ? ' has' : '') + '" data-go="' + st[3] + '"><div class="sh">' + mi(st[2]) + '<span>' + st[1] + '</span><b>' + (n || 0) + '</b></div>' +
        '<div class="th">' + (list.slice(0, 3).map(function (p) { return '<img src="' + esc(p.cover_url) + '" alt="" title="' + esc(p.hook || '') + '">'; }).join('') || '<span class="none">—</span>') + '</div>' +
        (st[0] === 'preparing' && n ? '<div class="prep"><i></i></div>' : '') + (failed ? '<div class="why" style="color:var(--bad)">' + failed + ' failed</div>' : '') + '</div>';
    }).join('') + '</div>';

    var kp = '<div class="kpis">' +
      tile('Instagram', lf.instagram, { color: PCOL.instagram, go: 'analytics', delta: since(f, 'instagram', 7), dlabel: '7d', spark: spark(fser(f, 'instagram'), PCOL.instagram), sub: 'followers' }) +
      tile('YouTube', lf.youtube, { color: PCOL.youtube, go: 'analytics', delta: since(f, 'youtube', 7), dlabel: '7d', spark: spark(fser(f, 'youtube'), PCOL.youtube), sub: 'subscribers' }) +
      tile('TikTok', lf.tiktok, { color: PCOL.tiktok, go: 'analytics', delta: since(f, 'tiktok', 7), dlabel: '7d', spark: spark(fser(f, 'tiktok'), PCOL.tiktok), sub: 'followers' }) +
      tile('Views · 7 days', AN ? v7 : null, { icon: 'eye', go: 'analytics', sub: fmt(t.views) + ' all time' }) +
      tile('Engagement', eng, { icon: 'heart', go: 'analytics', sub: fmt(t.likes) + ' likes · ' + fmt(t.shares) + ' shares' }) +
      tile('Published', c.published, { icon: 'send', go: 'calendar', sub: AN ? 'median ' + fmt(AN.median_views) + ' views' : '' }) + '</div>';

    var top = ps.slice().sort(function (x, y) { return y.views - x.views; })[0];
    var plats = AN ? Object.keys(AN.platforms).map(function (k) { return { name: PNAME[k] || k, value: AN.platforms[k].views, color: PCOL[k] || C.acc }; }) : [];
    var wait = '<div class="nodata">Loading charts…</div>';

    return (miss.length ? '<div class="warnb">' + mi('warn') + ' ' + miss.join(' and ') + ' not connected — <a href="#" data-go="accounts">connect in Accounts</a></div>' : '') +
      '<h2 class="sec">' + mi('layers') + ' Your posts right now <span class="hint">click a stage to open it</span></h2>' + pipe +
      '<h2 class="sec">' + mi('finance') + ' How you’re doing</h2>' + kp +
      '<div class="g2 wide"><div class="box"><h3>Views by day <span class="hint">last 14 days · by the day a post went up</span></h3>' + (AN ? stacked(viewsByDay(ps, 14)) : wait) + '</div>' +
      '<div class="box"><h3>Where views come from</h3>' + (AN ? donut(plats) : wait) + '</div></div>' +
      '<div class="g3"><div class="box"><h3>Needs you</h3>' + (need.length ? need.slice(0, 4).map(function (p) {
          return '<div class="tp"><img src="' + esc(p.cover_url) + '" alt=""><span class="tt">' + esc(p.hook || p.yt_title || 'Untitled') + '<small>' + pchips(p.platforms) + (p.status === 'failed' ? ' <span style="color:var(--bad)">failed</span>' : '') + '</small></span><button class="sb ok" data-ap="' + p.id + '" title="Approve">' + mi('check') + '</button></div>'; }).join('') +
          (need.length > 4 ? '<a href="#" class="more" data-go="queue">+' + (need.length - 4) + ' more in Queue</a>' : '') : nodata('Nothing waiting. Make something in the lab and say “post it”.')) + '</div>' +
        '<div class="box"><h3>Up next</h3>' + (sched.length ? '<div class="tl">' + families(sched).slice(0, 5).map(function (f) {
          var p = f[0], pl = [], at = Math.min.apply(null, f.map(function (q) { return q.schedule_at || Infinity; }));
          f.forEach(function (q) { (q.platforms || []).forEach(function (x) { if (pl.indexOf(x) < 0) pl.push(x); }); });
          return '<div class="ti"><span class="dot"></span><div><b>' + esc((isFinite(at) && when(at)) || 'queued') + '</b><div class="tt">' + esc(p.hook || p.yt_title || '') + '</div><small>' + pchips(pl) + '</small></div></div>'; }).join('') + '</div>' : nodata('Nothing scheduled. Approve a draft to queue it.')) + '</div>' +
        '<div class="box"><h3>Top post</h3>' + (top ? '<div class="spot"><img src="' + esc(top.cover) + '" alt=""><div><div class="hook">' + esc(top.hook) + '</div><div class="big">' + fmt(top.views) + '<small> views</small></div>' +
          '<div class="mx"><span><b>' + fmt(top.likes) + '</b> likes</span><span><b>' + fmt(top.shares) + '</b> shares</span><span><b>' + top.eng + '%</b> eng</span></div>' +
          (top.pillar && top.pillar.length > 1 ? '<div class="why">' + esc(top.pillar) + '</div>' : '') + '</div></div>' : AN ? nodata('No published posts yet.') : wait) + '</div></div>' +
      '<div class="g2 wide"><div class="box"><h3>Posting activity <span class="hint">last 12 weeks</span></h3>' + (AN ? activity(ps, 12) : wait) + '</div>' +
      '<div class="box"><h3>Audience growth</h3>' + lines([{ name: 'Instagram', color: C.ig, pts: fser(f, 'instagram') }, { name: 'YouTube', color: C.yt, pts: fser(f, 'youtube') }, { name: 'TikTok', color: C.tt, pts: fser(f, 'tiktok') }], 140) + '</div></div>' +
      '<h2 class="sec">' + mi('agent') + ' VIRAL-Ω’s take</h2><!--brief-->' +
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

  function metaBox() {
    var a = STATS.accounts, m = a.meta || {}, base = (a.tiktok && a.tiktok.base) || 'https://<set the public address below>';
    return '<div class="box"><h3>Facebook + Instagram — one-time login</h3><div class="row">' +
      (a.facebook.connected ? '<span class="acct on">Facebook · ' + esc(a.facebook.page || '') + '</span>' : '<span class="acct">Facebook not connected</span>') +
      (a.instagram.connected ? '<span class="acct on">Instagram · @' + esc(a.instagram.username) + '</span>' : '<span class="acct">Instagram not connected</span>') + '</div>' +
      '<div class="why">One sign-in connects your Facebook Page and the Instagram account linked to it; access renews automatically. ' +
      'Meta app → Facebook Login → Valid OAuth Redirect URIs: <b>' + esc(base) + '/social/meta/callback</b></div>' +
      '<label class="f">Meta app ID + secret (Meta for Developers → your app → Settings → Basic)</label>' +
      '<div class="row"><input class="t" id="mt-app" placeholder="app id" value="' + esc(m.app_id || '') + '"><input class="t" id="mt-sec" type="password" autocomplete="off" placeholder="' + (m.has_app ? 'saved — leave empty to keep' : 'app secret') + '"></div>' +
      '<div class="row" style="margin-top:10px"><button class="sb" id="mt-save">Save app</button><button class="sb pri" id="mt-go"' + (m.has_app ? '' : ' disabled') + '>Continue with Facebook</button></div></div>';
  }

  function accountsView() {
    var a = STATS.accounts;
    return metaBox() + '<div class="box"><h3>Instagram ' + esc(a.handle) + '</h3><div class="row">' + (a.instagram.connected ? '<span class="acct on">connected · @' + esc(a.instagram.username) + '</span>' + (a.instagram.expires ? '<span class="why">token renews automatically · expires ' + when(a.instagram.expires) + '</span>' : '') : '<span class="acct">not connected</span>') + '</div>' +
      '<label class="f">Instagram access token — Meta app → Instagram → API setup with Instagram login → Generate token (starts with IG…). An older Facebook-Page token also works.</label><input class="t" id="ig-tok" type="password" autocomplete="off">' +
      '<label class="f">Instagram app ID (optional)</label><input class="t" id="ig-app">' +
      '<label class="f">Instagram app secret (optional — only needed for short 1-hour tokens)</label><input class="t" id="ig-sec" type="password" autocomplete="off">' +
      '<label class="f">Public https address of this lab (Instagram downloads the video from here)</label><input class="t" id="pub" placeholder="https://your-lab.example.com">' +
      '<div class="row" style="margin-top:10px"><button class="sb pri" id="ig-save">Connect Instagram</button></div></div>' +
      '<div class="box"><h3>YouTube</h3><div class="row">' + (a.youtube.connected ? '<span class="acct on">connected · ' + esc(a.youtube.channel) + '</span>' : a.youtube.expired ? '<span class="acct" style="color:#ff6b5b">sign-in expired · ' + esc(a.youtube.channel) + ' — click Reconnect Google</span>' : '<span class="acct">not connected</span>') + '</div>' +
      '<label class="f">Google OAuth client ID (Desktop app; redirect: this lab’s …/api/social/youtube/callback)</label><input class="t" id="yt-id">' +
      '<label class="f">Client secret</label><input class="t" id="yt-sec" type="password" autocomplete="off">' +
      '<div class="row" style="margin-top:10px"><button class="sb" id="yt-save">Save client</button><button class="sb pri" id="yt-go"' + (a.youtube.has_client ? '' : ' disabled') + '>' + (a.youtube.expired ? 'Reconnect Google' : 'Sign in with Google') + '</button><span class="why">Do this on the lab PC.</span></div></div>' + ttBox() + fbBox();
  }

  function fbBox() {
    var f = STATS.accounts.facebook || {};
    return '<div class="box"><h3>Facebook Page</h3><div class="row">' + (f.connected ? '<span class="acct on">connected · ' + esc(f.page || '') + '</span><button class="sb" id="fb-off">Disconnect</button>' : '<span class="acct">not connected</span>') + '</div>' +
      '<label class="f">Facebook user access token — Meta app → Graph API Explorer, with pages_show_list, pages_manage_posts, pages_read_engagement, publish_video</label><input class="t" id="fb-tok" type="password" autocomplete="off">' +
      '<label class="f">Page name (optional — first Page if empty)</label><input class="t" id="fb-page" placeholder="' + esc((f.pages || []).join(', ')) + '">' +
      '<label class="f">App ID + secret (optional — turns a short token into one that never expires)</label><div class="row"><input class="t" id="fb-app" placeholder="app id"><input class="t" id="fb-sec" type="password" autocomplete="off" placeholder="app secret"></div>' +
      '<div class="row" style="margin-top:10px"><button class="sb pri" id="fb-save">Connect Facebook</button><span class="why">Videos upload straight from this PC — no public address needed.</span></div></div>';
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
    if (a === 'repost') return repostDlg(p);
  }

  /* REPOST: an old published video → a new post for platform(s) it isn't on yet */
  var PL_NAME = { instagram: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok', facebook: 'Facebook' };
  // TikTok per-post settings, wording per TikTok's Content Sharing Guidelines (privacy has NO default, interactions off
  // by default, exact disclosure/consent text) — shared by the post editor and the Repost dialog.
  // ttFields → html (ids tt-*), ttWire(btns) → live label logic + disables the publish button(s), ttRead → settings.
  // Inbox mode (ci.post_mode, unaudited client): the video goes to the creator's TikTok inbox and every choice is made in TikTok.
  var TT_PROCESS = 'After publishing, it may take a few minutes for your video to process and be visible on your TikTok profile.';
  var TT_PICK = 'You need to indicate if your content promotes yourself, a third party, or both.';
  function ttFields(T, ci) {
    var who = esc(ci.creator_nickname || ci.creator_username || '');
    if (ci.post_mode === 'inbox')
      return '<h3>TikTok · send to ' + who + '’s TikTok inbox</h3>' +
        '<div class="why">MIR MEDIA LABS uploads this video to your TikTok app as a draft. Open TikTok, tap the notification, then choose who can see it, set comments/Duet/Stitch and publish. ' +
        'Nothing goes public until you post it in TikTok.</div><div class="why">' + TT_PROCESS + ' Video limit: ' + (ci.max_video_post_duration_sec || '?') + 's.</div>';
    var opts = ci.privacy_level_options || [], lab = { PUBLIC_TO_EVERYONE: 'Everyone', MUTUAL_FOLLOW_FRIENDS: 'Friends', FOLLOWER_OF_CREATOR: 'Followers', SELF_ONLY: 'Only me' };
    var ck = function (id, on, dis, txt) { return '<label class="row" style="font-size:12px' + (dis ? ';opacity:.45' : '') + '"><input type="checkbox" id="' + id + '"' + (on && !dis ? ' checked' : '') + (dis ? ' disabled' : '') + '> ' + txt + '</label>'; };
    return '<h3>TikTok · posting as ' + who + '</h3>' +
      '<label class="f">Who can see this video</label><select class="t" id="tt-priv"><option value="">Choose…</option>' + opts.map(function (o) { return '<option value="' + o + '"' + (T.privacy_level === o ? ' selected' : '') + '>' + (lab[o] || o) + '</option>'; }).join('') + '</select>' +
      '<div class="row" style="margin-top:8px">' + ck('tt-cm', T.allow_comment, ci.comment_disabled, 'Allow comments') + ck('tt-du', T.allow_duet, ci.duet_disabled, 'Allow Duet') + ck('tt-st', T.allow_stitch, ci.stitch_disabled, 'Allow Stitch') + '</div>' +
      '<div class="row" style="margin-top:8px">' + ck('tt-dis', T.disclose, false, 'Disclose commercial content') + '</div>' +
      '<div class="row" id="tt-disrow"' + (T.disclose ? '' : ' hidden') + '>' + ck('tt-org', T.brand_organic, false, 'Your brand') + ck('tt-bc', T.brand_content, false, 'Branded content (paid partnership)') + '</div>' +
      '<div class="why" id="tt-label"></div>' +
      '<label class="row" style="font-size:12px;margin-top:8px"><input type="checkbox" id="tt-ok"' + (T.consent ? ' checked' : '') + '> By posting, you agree to TikTok’s <span id="tt-bcp"></span>' +
      '<a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" style="color:var(--acc)">Music Usage Confirmation</a>.</label>' +
      '<div class="why">' + TT_PROCESS + '</div><div class="why">Labelled as AI-generated content. Video limit: ' + (ci.max_video_post_duration_sec || '?') + 's.</div>';
  }
  function ttWire(btns) {
    btns = (btns || []).filter(Boolean);
    if (!$('#tt-dis')) { btns.forEach(function (x) { x.disabled = false; x.title = ''; }); return; }     // inbox mode: nothing to gate
    var lbl = function () {
      var o = $('#tt-org').checked, b = $('#tt-bc').checked, d = $('#tt-dis').checked, none = d && !o && !b;
      $('#tt-disrow').hidden = !d;
      $('#tt-label').textContent = !d ? '' : b ? 'Your video will be labeled as ‘Paid partnership’.' : o ? 'Your video will be labeled as ‘Promotional content’.' : TT_PICK;
      $('#tt-bcp').innerHTML = d && b ? '<a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" style="color:var(--acc)">Branded Content Policy</a> and ' : '';
      var so = $('#tt-priv').querySelector('option[value="SELF_ONLY"]');
      if (so) {
        so.disabled = d && b; so.title = $('#tt-priv').title = so.disabled ? 'Branded content visibility cannot be set to private.' : '';
        if (so.selected && so.disabled) $('#tt-priv').value = '';
      }
      btns.forEach(function (x) { x.disabled = none; x.title = none ? TT_PICK : ''; });                    // disclosure on, nothing picked → can't publish
    };
    ['tt-dis', 'tt-org', 'tt-bc'].forEach(function (i) { $('#' + i).onchange = lbl; }); lbl();
  }
  function ttRead() {
    if (!$('#tt-priv')) return null;
    return { privacy_level: $('#tt-priv').value, allow_comment: $('#tt-cm').checked, allow_duet: $('#tt-du').checked, allow_stitch: $('#tt-st').checked,
      disclose: $('#tt-dis').checked, brand_organic: $('#tt-dis').checked && $('#tt-org').checked, brand_content: $('#tt-dis').checked && $('#tt-bc').checked, consent: $('#tt-ok').checked };
  }

  function repostDlg(p) {
    var m = $('#modal'), on = Object.keys(p.remote || {}), acc = (STATS && STATS.accounts) || {};
    var rows = ['instagram', 'youtube', 'tiktok', 'facebook'].map(function (pl) {
      var posted = on.indexOf(pl) > -1, conn = !!(acc[pl] || {}).connected;
      return '<label class="row" style="font-size:13px;gap:8px;padding:4px 0"><input type="checkbox" data-rp="' + pl + '"' + (!posted && conn ? ' checked' : '') + '> ' + PL_NAME[pl] +
        (posted ? ' <span class="why" style="margin:0">already posted here</span>' : '') + (!conn ? ' <span class="why" style="margin:0;color:var(--bad)">not connected</span>' : '') + '</label>';
    }).join('');
    m.innerHTML = '<div class="in" style="max-width:460px"><div class="row"><b style="flex:1">' + mi('forward') + ' Repost to another platform</b><button class="sb ic" id="mx">' + mi('close') + '</button></div>' +
      '<div class="row" style="align-items:flex-start;margin-top:10px;gap:12px"><img src="' + esc(p.cover_url) + '" style="width:72px;aspect-ratio:9/16;object-fit:cover;border-radius:8px;background:#000">' +
      '<div style="flex:1"><div class="hook" style="margin:0 0 6px">' + esc(p.hook || p.yt_title || '') + '</div><div class="why" style="margin:0">Live on: ' + (on.length ? on.map(function (x) { return PL_NAME[x] || x; }).join(', ') : '—') +
      '</div><div class="why">A new post is made with the same video + captions (edit them after). The original stays as it is.</div></div></div>' +
      '<label class="f">Post it on</label>' + rows +
      '<div id="rp-ttbox" class="box" hidden style="margin-top:8px"></div>' +
      '<label class="f">When</label><select class="t" id="rp-when"><option value="draft">Save as draft — I\'ll edit captions first</option><option value="best">Schedule — VIRAL-Ω picks the best time</option>' +
      '<option value="at">Schedule — pick a time</option><option value="now">Post now</option></select>' +
      '<input class="t" type="datetime-local" id="rp-at" hidden style="margin-top:6px">' +
      '<div class="row" style="margin-top:12px;justify-content:flex-end"><button class="sb" id="rp-cancel">Cancel</button><button class="sb pri" id="rp-go">' + mi('forward') + ' Repost</button></div></div>';
    m.hidden = false; if (window.MI && MI.fill) MI.fill(m);
    var close = function () { m.hidden = true; };
    $('#mx').onclick = close; $('#rp-cancel').onclick = close;
    $('#rp-when').onchange = function () { $('#rp-at').hidden = this.value !== 'at'; };
    // TikTok needs its own per-post choices before it can be scheduled/posted — shown inline when TikTok is ticked
    var ttCi = null, ttCb = m.querySelector('[data-rp="tiktok"]');
    var ttDraw = function () {
      var bx = $('#rp-ttbox'); bx.hidden = !(ttCb && ttCb.checked);
      if (bx.hidden) { $('#rp-go').disabled = false; $('#rp-go').title = ''; return; }                   // TikTok unticked → nothing to gate
      if (ttCi) { bx.innerHTML = ttFields(p.tiktok || {}, ttCi); ttWire([$('#rp-go')]); return; }
      bx.innerHTML = '<div class="why">Checking your TikTok account…</div>';
      api('api/social/tiktok/creator').then(function (ci) { ttCi = ci; ttDraw(); }).catch(function (e) { bx.innerHTML = '<div class="warnb">' + esc(e.message) + ' — connect TikTok in Accounts</div>'; });
    };
    if (ttCb) ttCb.onchange = ttDraw;
    ttDraw();
    $('#rp-go').onclick = function () {
      var pl = [].slice.call(m.querySelectorAll('[data-rp]:checked')).map(function (c) { return c.dataset.rp; });
      if (!pl.length) return toast('Pick at least one platform');
      var w = $('#rp-when').value, when = w, tt = pl.indexOf('tiktok') > -1 ? ttRead() : null;
      if (tt && w !== 'draft') {                                  // a draft can be finished later in Edit → TikTok
        if (!tt.privacy_level) return toast('TikTok: choose who can see this video');
        if (!tt.consent) return toast('TikTok: tick the Music Usage Confirmation');
      }
      if (w === 'at') { var v = $('#rp-at').value; if (!v) return toast('Pick a date and time'); when = String(new Date(v).getTime() / 1000); }
      if (w === 'now' && !confirm('Post this video now to ' + pl.map(function (x) { return PL_NAME[x]; }).join(' + ') + '?')) return;
      var b = this, body = { platforms: pl, when: when };
      b.disabled = true;
      if (tt) body.tiktok = tt;
      api('api/social/posts/' + p.id + '/repost', { method: 'POST', body: body }).then(function (r) {
        close();
        var inbox = pl.indexOf('tiktok') > -1 && ttCi && ttCi.post_mode === 'inbox';
        toast(r.note ? 'Repost ' + r.note : w === 'draft' ? 'Repost saved to the queue — edit and approve it there' :
          w === 'now' ? (inbox ? 'Sending to your TikTok inbox — open TikTok to publish it' : 'Reposting now… ' + (pl.indexOf('tiktok') > -1 ? TT_PROCESS : '')) : 'Repost scheduled');
        if (w === 'draft' || r.status === 'draft') VIEW = 'queue';
        return load();
      }).catch(function (e) { b.disabled = false; toast(e.message); });
    };
  }

  function preview(p) {
    if (!p) return;
    var m = $('#modal'), tab = function (u, r, l) { return '<button class="sb" data-pvs="' + esc(u) + '" data-r="' + r + '">' + l + '</button>'; };
    m.innerHTML = '<div class="in" style="text-align:center"><div class="row"><b style="flex:1;text-align:left">Preview — ' + esc(p.hook || p.yt_title || '') + '</b><button class="sb ic" id="mx">' + mi('close') + '</button></div>' +
      '<div class="row" style="justify-content:center;margin:8px 0">' + tab(p.video_url, '9/16', '9:16 Reels / TikTok / Short') + (p.yt_video_url ? tab(p.yt_video_url, '16/9', 'YouTube 16:9') : '') + '</div>' +
      '<video id="pvx" src="' + esc(p.video_url) + '" controls autoplay playsinline style="max-width:100%;max-height:70vh;aspect-ratio:9/16;border-radius:12px;background:#000"></video>' +
      '<div class="row" style="justify-content:center;margin-top:10px">' + (p.status === 'draft' ? '<button class="sb ok" id="pv-ap">' + mi('check') + ' Approve</button>' : '') + '<button class="sb" id="pv-ed">' + mi('edit') + ' Edit</button></div></div>';
    m.hidden = false; if (window.MI && MI.fill) MI.fill(m);
    var v = $('#pvx'), close = function () { v.pause(); m.hidden = true; };
    $('#mx').onclick = close;
    m.querySelectorAll('[data-pvs]').forEach(function (b) { b.onclick = function () { v.src = b.dataset.pvs; v.style.aspectRatio = b.dataset.r; v.play().catch(function () {}); }; });
    var ap = $('#pv-ap'); if (ap) ap.onclick = function () { close(); act(p.id, 'approve'); };
    $('#pv-ed').onclick = function () { v.pause(); editor(p); };
  }

  function editor(p) {
    var m = $('#modal'), dt = p.schedule_at ? new Date(p.schedule_at * 1000) : null;
    var loc = dt ? new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
    m.innerHTML = '<div class="in"><div class="row"><b style="flex:1">Edit post</b><button class="sb ic" id="mx">' + mi('close') + '</button></div>' +
      '<div class="row" style="align-items:flex-start;margin-top:10px"><video id="pv" src="' + esc(p.video_url) + '" controls playsinline style="width:160px;aspect-ratio:9/16;border-radius:10px;background:#000"></video>' +
      '<div style="flex:1;min-width:220px"><label class="f">Hook (on-screen, first second)</label><input class="t" id="e-hook" value="' + esc(p.hook || '') + '">' +
      '<label class="f">Instagram caption</label><textarea class="t" id="e-cap">' + esc(p.caption || '') + '</textarea>' +
      '<label class="f">Hashtags (space separated, no #)</label><input class="t" id="e-tags" value="' + esc((p.hashtags || []).join(' ')) + '"></div></div>' +
      (p.yt_video_url ? '<label class="f">YouTube 16:9 preview</label><video src="' + esc(p.yt_video_url) + '" controls playsinline preload="metadata" style="width:100%;max-width:420px;aspect-ratio:16/9;border-radius:10px;background:#000"></video>' : '') +
      '<label class="f">YouTube format</label><select class="t" id="e-ytf">' + [['video', 'Normal video (16:9)'], ['short', 'Short (9:16)'], ['both', 'Both — normal video + Short']].map(function (o) {
        return '<option value="' + o[0] + '"' + ((p.yt_format || 'video') === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select>' +
      '<label class="f">YouTube title</label><input class="t" id="e-yt" value="' + esc(p.yt_title || '') + '">' +
      '<label class="f">TikTok caption</label><textarea class="t" id="e-ttc">' + esc(p.tt_caption || '') + '</textarea>' +
      '<label class="f">Facebook caption</label><textarea class="t" id="e-fbc">' + esc(p.fb_caption || '') + '</textarea>' +
      '<label class="f">Pinned first comment</label><input class="t" id="e-pin" value="' + esc(p.pinned_comment || '') + '">' +
      '<label class="f">YouTube description</label><textarea class="t" id="e-ytd">' + esc(p.yt_description || '') + '</textarea>' +
      '<div class="row"><label class="row" style="font-size:12px"><input type="checkbox" id="e-ig"' + ((p.platforms || []).indexOf('instagram') > -1 ? ' checked' : '') + '> Instagram</label>' +
      '<label class="row" style="font-size:12px"><input type="checkbox" id="e-ytb"' + ((p.platforms || []).indexOf('youtube') > -1 ? ' checked' : '') + '> YouTube</label>' +
      '<label class="row" style="font-size:12px"><input type="checkbox" id="e-tt"' + ((p.platforms || []).indexOf('tiktok') > -1 ? ' checked' : '') + '> TikTok</label>' +
      '<label class="row" style="font-size:12px"><input type="checkbox" id="e-fb"' + ((p.platforms || []).indexOf('facebook') > -1 ? ' checked' : '') + '> Facebook</label>' +
      '<label class="f" style="margin:0">Post at</label><input class="t" type="datetime-local" id="e-at" value="' + loc + '" style="width:auto">' +
      '<button class="sb" id="e-cover">' + mi('camera') + ' Use current frame as cover</button></div>' +
      '<div id="e-ttbox" class="box" style="margin-top:12px" hidden></div>' +
      '<div class="row" style="margin-top:14px;justify-content:flex-end"><button class="sb" id="e-cancel">Cancel</button><button class="sb pri" id="e-save">Save</button></div></div>';
    m.hidden = false;
    var T = Object.assign({}, p.tiktok || {});
    var ttBoxDraw = function (ci) {
      var bx = $('#e-ttbox'); if (!bx) return;
      bx.hidden = !$('#e-tt').checked;
      if (bx.hidden) { $('#e-save').disabled = false; $('#e-save').title = ''; return; }
      if (!ci) { bx.innerHTML = '<div class="why">Checking your TikTok account…</div>'; api('api/social/tiktok/creator').then(ttBoxDraw).catch(function (e) { bx.innerHTML = '<div class="warnb">' + esc(e.message) + ' — connect TikTok in Accounts</div>'; }); return; }
      bx.innerHTML = ttFields(T, ci);
      ttWire([$('#e-save')]);
    };
    $('#e-tt').onchange = function () { ttBoxDraw(); };
    ttBoxDraw();
    if (window.MI && MI.fill) MI.fill(m);
    var close = function () { m.hidden = true; m.innerHTML = ''; };
    $('#mx').onclick = $('#e-cancel').onclick = close;
    $('#e-cover').onclick = function () { api('api/social/posts/' + p.id, { method: 'POST', body: { cover_at: $('#pv').currentTime } }).then(function () { toast('Cover set'); }); };
    $('#e-save').onclick = function () {
      var pl = []; if ($('#e-ig').checked) pl.push('instagram'); if ($('#e-ytb').checked) pl.push('youtube'); if ($('#e-tt').checked) pl.push('tiktok'); if ($('#e-fb') && $('#e-fb').checked) pl.push('facebook');
      var b = { hook: $('#e-hook').value, caption: $('#e-cap').value, hashtags: $('#e-tags').value.split(/[\s,#]+/).filter(Boolean),
        yt_title: $('#e-yt').value, yt_description: $('#e-ytd').value, platforms: pl,
        tt_caption: $('#e-ttc').value, fb_caption: $('#e-fbc').value, pinned_comment: $('#e-pin').value, yt_format: $('#e-ytf').value };
      if ($('#tt-priv')) b.tiktok = ttRead();
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
    document.querySelectorAll('[data-pv]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); preview(POSTS.filter(function (x) { return x.id === b.dataset.pv; })[0]); }; });
    var at = $('#attach'), af = $('#attach-f');
    if (at && af) {
      at.onclick = function () { af.click(); };
      af.onchange = function () {
        var f = af.files[0]; if (!f) return;
        var brief = prompt('Brief for VIRAL-Ω (optional): angle, series, call to action…', '') || '';
        var plats = prompt('Platforms (comma list: instagram,youtube,tiktok,facebook)', 'instagram,youtube,tiktok,facebook') || '';
        var fd = new FormData(); fd.append('file', f); fd.append('brief', brief); fd.append('platforms', plats.replace(/\s+/g, ''));
        toast('Uploading ' + f.name + '…');
        fetch('api/social/upload', { method: 'POST', body: fd }).then(function (r) { return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || r.status); return j; }); })
          .then(function () { af.value = ''; toast('VIRAL-Ω is writing the best title, caption + hashtags per platform…'); load(); })
          .catch(function (e) { af.value = ''; toast(e.message); });
      };
    }
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
    var ra = $('#refresh-all'); if (ra) ra.onclick = function () { var o = ra.innerHTML; ra.disabled = true; ra.innerHTML = mi('refresh') + ' Refreshing…'; if (window.MI && MI.fill) MI.fill(ra);
      api('api/social/metrics/refresh-all', { method: 'POST' }).then(function (r) { toast(r.errors ? 'Updated ' + (r.refreshed || 0) + '/' + (r.posts || 0) + ' posts · ' + r.errors + ' failed — ' + (r.error || '') : 'Updated all ' + (r.refreshed || 0) + ' post' + (r.refreshed === 1 ? '' : 's')); return load(); }).catch(function (e) { toast(e.message); ra.disabled = false; ra.innerHTML = o; if (window.MI && MI.fill) MI.fill(ra); }); };
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
    var yg = $('#yt-go'); if (yg) yg.onclick = function () { window.open('api/social/youtube/connect', '_blank'); };
    var mts = $('#mt-save'); if (mts) mts.onclick = function () { api('api/social/accounts', { method: 'POST', body: { meta_app_id: $('#mt-app').value, meta_app_secret: $('#mt-sec').value } }).then(function () { toast('Saved'); load(); }).catch(function (e) { toast(e.message); }); };
    var mtg = $('#mt-go'); if (mtg) mtg.onclick = function () { window.open('api/social/meta/connect', '_blank'); };
    var tts = $('#tt-save'); if (tts) tts.onclick = function () { api('api/social/accounts', { method: 'POST', body: { tt_client_key: $('#tt-key').value, tt_client_secret: $('#tt-sec').value } }).then(function () { toast('Saved'); load(); }).catch(function (e) { toast(e.message); }); };
    var ttg = $('#tt-go'); if (ttg) ttg.onclick = function () { window.open('api/social/tiktok/connect', '_blank'); };
    var tto = $('#tt-off'); if (tto) tto.onclick = function () { if (confirm('Disconnect TikTok? (Deletes the saved sign-in.)')) api('api/social/tiktok/disconnect', { method: 'POST' }).then(load); };
    var fbs = $('#fb-save'); if (fbs) fbs.onclick = function () { api('api/social/accounts', { method: 'POST', body: { fb_token: $('#fb-tok').value, fb_page: $('#fb-page').value, fb_app_id: $('#fb-app').value, fb_app_secret: $('#fb-sec').value } }).then(function () { toast('Facebook connected'); load(); }).catch(function (e) { toast(e.message); }); };
    var fbo = $('#fb-off'); if (fbo) fbo.onclick = function () { if (confirm('Disconnect Facebook?')) api('api/social/accounts', { method: 'POST', body: { fb_off: 1 } }).then(load); };
    var pub = $('#pub'); if (pub) api('api/social/accounts').then(function (a) { pub.value = a.public_base || ''; });
  }

  document.querySelectorAll('.so-tabs button').forEach(function (b) { b.onclick = function () { VIEW = b.dataset.v; render(); }; });
  $('#so-close').onclick = function () { if (window.MMLApp && MMLApp.close) return MMLApp.close(''); if (window.parent !== window) window.parent.postMessage({ mml: 'social-close' }, '*'); else history.back(); };
  window.addEventListener('message', function (e) { var d = e.data || {}; if (d.mml === 'social-toast') { toast(d.text); setTimeout(load, 1500); } });
  window.SOCIAL = { api: api, esc: esc, mi: mi, toast: toast, fmt: fmt, when: when, reload: load, render: function () { render(); },
    posts: function () { return POSTS; }, stats: function () { return STATS; }, go: function (v) { VIEW = v; render(); }, view: function () { return VIEW; } };
  var t = new URLSearchParams(location.search).get('v'); if (t) VIEW = t;
  load();
  function canRefresh() { return !document.hidden && $('#modal').hidden && VIEW !== 'agent' && VIEW !== 'accounts' && VIEW !== 'skills' && VIEW !== 'analytics' && !(window.VIRAL && VIRAL.views[VIEW]); }
  setInterval(function () { if (canRefresh()) load(); }, 20000);
})();
