/* MIR MEDIA LABS · SOCIAL — VIRAL-Ω research desk. Loaded before social.js, which calls into window.VIRAL:
   views (Trends / Hook Lab / Planner tabs), wrap (brief on Overview, insights under Analytics), cardExtra (lint, hook
   scores, Captions / Hook Lab / Preview buttons on drafts) and bind. Talks to /api/viral/* (viral.py). Never publishes. */
(function () {
  'use strict';
  var S = function () { return window.SOCIAL; };
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return S().esc(s); }, mi = function (n) { return S().mi(n); }, fmt = function (n) { return S().fmt(n); };
  var api = function (u, o) { return S().api(u, o); };
  var TR = null, WATCH = null, BRIEF = null, INS = null, PIPE = null, HL = { post: '', out: null, busy: false }, CFG_OPEN = false, RX = null, RXT = null, RXSEED = '';
  var PLAT = { instagram: 'IG', youtube: 'YT', tiktok: 'TT', facebook: 'FB' };

  function ago(t) { if (!t) return 'never'; var s = Date.now() / 1000 - t; return s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago'; }
  function make(prompt) {
    var msg = { mml: 'social-make', prompt: prompt, social: { platforms: ['instagram', 'youtube'] } };
    if (window.parent !== window) { window.parent.postMessage(msg, '*'); S().toast('Sent to the lab — it becomes a draft when it renders'); }
    else { navigator.clipboard && navigator.clipboard.writeText(prompt); S().toast('Open Social from the lab to make it — prompt copied'); }
  }
  function score(v) { v = Math.max(0, Math.min(100, +v || 0)); return '<span class="vx-bar"><i style="width:' + v + '%;background:' + (v >= 75 ? 'var(--ok)' : v >= 55 ? 'var(--warn)' : 'var(--bad)') + '"></i></span><b>' + Math.round(v) + '</b>'; }

  // ── Trends ──────────────────────────────────────────────────────────────────────────────────────────────────────
  function trendsView() {
    if (!TR) { Promise.all([api('api/viral/trends'), api('api/viral/watch')]).then(function (r) { TR = r[0]; WATCH = r[1]; S().render(); }).catch(function (e) { S().toast(e.message); }); return '<div class="empty">Loading the trend radar…</div>'; }
    var c = TR.config || {}, src = TR.sources || {};
    var chips = Object.keys(src).map(function (k) { var x = src[k]; return '<span class="vx-chip ' + (x.ok ? 'ok' : 'bad') + '" title="' + esc(x.err || '') + '">' + esc(k) + ' · ' + (x.ok ? x.n : 'off') + '</span>'; }).join('');
    var picks = (TR.picks || []).map(function (p, i) {
      return '<div class="vx-pick">' + (p.thumb ? '<img src="' + esc(p.thumb) + '" alt="">' : '<div class="vx-ph">' + mi('radar') + '</div>') +
        '<div class="vx-pb"><div class="vx-src">' + esc(p.src) + (p.rising ? ' <span class="vx-up">' + mi('bolt') + ' rising</span>' : '') + ' · fit <b>' + esc(p.fit) + '/10</b></div>' +
        '<a class="vx-t" href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(p.title) + '</a><small>' + esc(p.stat) + '</small>' +
        '<div class="vx-angle"><b>Our angle:</b> ' + esc(p.angle) + '</div>' +
        '<div class="vx-hook">“' + esc(p.hook) + '” <small>' + esc(p.format || '') + (p.duration ? ' · ' + esc(p.duration) + 's' : '') + '</small></div>' +
        (p.why ? '<div class="why">' + esc(p.why) + '</div>' : '') +
        '<div class="row"><button class="sb pri" data-vmk="' + i + '">' + mi('sparkle') + ' Make it</button>' + (/youtu/.test(p.url || '') ? '<button class="sb" data-vrx="' + esc(p.url) + '" title="Watch this video and make our own version">' + mi('layers') + ' Remix</button>' : '') + '<button class="sb" data-vcp="' + i + '">' + mi('copy') + ' Prompt</button></div></div></div>';
    }).join('');
    var bySrc = {}; (TR.items || []).forEach(function (x) { (bySrc[x.src] = bySrc[x.src] || []).push(x); });
    var feed = Object.keys(bySrc).map(function (k) {
      return '<details class="vx-feed"><summary>' + esc(k) + ' <small>(' + bySrc[k].length + ')</small></summary>' + bySrc[k].slice(0, 15).map(function (x) {
        return '<div class="vx-fi">' + (x.rising ? '<span class="vx-up">' + mi('bolt') + '</span>' : '') + '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.title) + '</a><small>' + esc(x.stat || '') + (x.who ? ' · ' + esc(x.who) : '') + '</small></div>';
      }).join('') + '</details>';
    }).join('');
    var w = WATCH || { channels: [], outliers: [] };
    return '<div class="box"><div class="row"><h3 style="flex:1;margin:0">Trend radar <span class="hint">live · updated ' + ago(TR.t) + ' · every 6 h</span></h3>' +
        '<button class="sb" id="vx-cfg">' + mi('sliders') + ' Sources</button><button class="sb pri" id="vx-ref"' + (TR.refreshing ? ' disabled' : '') + '>' + mi('refresh') + (TR.refreshing ? ' Scanning…' : ' Scan now') + '</button></div>' +
        '<div class="vx-chips">' + chips + '</div>' + (TR.summary ? '<div class="vx-sum">' + esc(TR.summary) + '</div>' : '') +
        (CFG_OPEN ? '<div class="vx-cfgb"><label class="f">YouTube niche searches (comma, max 3 used — 100 quota units each)</label><input class="t" id="vx-kw" value="' + esc((c.keywords || []).join(', ')) + '">' +
          '<label class="f">Subreddits</label><input class="t" id="vx-sub" value="' + esc((c.subreddits || []).join(', ')) + '">' +
          '<label class="f">Reddit app (free: reddit.com/prefs/apps → create app → type “script”) ' + (c.reddit ? '<span style="color:var(--ok)">connected</span>' : '') + '</label><div class="row"><input class="t" id="vx-rid" placeholder="client id" style="flex:1"><input class="t" id="vx-rsec" type="password" placeholder="secret" style="flex:1"></div>' +
          '<label class="f">News search</label><input class="t" id="vx-news" value="' + esc(c.news || '') + '">' +
          '<div class="row" style="margin-top:8px"><label><input type="checkbox" id="vx-at"' + (c.auto_trends ? ' checked' : '') + '> auto-scan</label>' +
          '<label><input type="checkbox" id="vx-ah"' + (c.auto_hooklab ? ' checked' : '') + '> judge hooks on every draft</label>' +
          '<label><input type="checkbox" id="vx-ac"' + (c.auto_captions ? ' checked' : '') + '> let VIRAL burn captions</label>' +
          '<span class="sp"></span><button class="sb ok" id="vx-cfgs">' + mi('check') + ' Save</button></div></div>' : '') + '</div>' +
      (picks ? '<div class="vx-picks">' + picks + '</div>' : '<div class="empty">No picks yet — press Scan now (YouTube sources need YouTube connected in Accounts).</div>') +
      '<div class="g2"><div class="box"><h3>Raw feed</h3>' + (feed || '<div class="nodata">Nothing pulled yet.</div>') + '</div>' +
      '<div class="box"><h3>Inspiration watchlist <span class="hint">videos at 2.5×+ their channel’s median</span></h3>' +
        '<div class="row"><input class="t" id="vx-wh" placeholder="@channelhandle or youtube.com/@…" style="flex:1"><button class="sb" id="vx-wa">' + mi('plus') + ' Watch</button><button class="sb" id="vx-ws">' + mi('refresh') + '</button></div>' +
        '<div class="vx-chips">' + w.channels.map(function (ch) { return '<span class="vx-chip">' + esc(ch.title) + ' <a href="#" data-vwr="' + esc(ch.id) + '">×</a></span>'; }).join('') + '</div>' +
        (w.outliers.length ? w.outliers.slice(0, 10).map(function (o) { return '<div class="vx-fi"><b class="vx-x">' + o.x + '×</b><a href="' + esc(o.url) + '" target="_blank" rel="noopener">' + esc(o.title) + '</a><small>' + esc(o.channel) + ' · ' + fmt(o.views) + ' views · <a href="#" data-vrx="' + esc(o.url) + '">remix it</a></small></div>'; }).join('')
          : '<div class="nodata">' + (w.channels.length ? 'No outliers right now.' : 'Add channels you admire — VIRAL flags their breakout videos.') + '</div>') + '</div></div>';
  }

  // ── Hook Lab ────────────────────────────────────────────────────────────────────────────────────────────────────
  function hooklabView() {
    var ps = S().posts().filter(function (p) { return p.media || p.hook; }).slice(0, 40);
    var p = ps.filter(function (x) { return x.id === HL.post; })[0];
    var o = HL.out;
    var rows = o && o.hooks ? o.hooks.map(function (h, i) {
      var pr = h.parts || {};
      return '<div class="vx-hr' + (i === 0 ? ' best' : '') + '"><div class="vx-ht">' + (i === 0 ? mi('star') + ' ' : '') + esc(h.text) + '<small>' + esc(h.angle || '') + ' · ' + h.words + ' words' + (h.formula ? ' · ' + esc(h.formula) : '') + '</small>' +
        (h.note ? '<div class="why">' + esc(h.note) + '</div>' : '') + ((h.lint || []).length ? '<div class="vx-lint warn">' + esc(h.lint.join(' · ')) + '</div>' : '') + '</div>' +
        '<div class="vx-hs">' + score(h.total) + '<small>stop ' + (pr.stop || '–') + ' · gap ' + (pr.gap || '–') + ' · match ' + (pr.match || '–') + ' · clear ' + (pr.clarity || '–') + ' · safe ' + (pr.safe || '–') + '</small></div>' +
        '<div class="vx-ha"><button class="sb" data-hpv="' + i + '">' + mi('eye') + '</button>' + (p && /draft|failed|scheduled/.test(p.status) ? '<button class="sb ok" data-huse="' + i + '">Use</button>' : '') + '</div></div>';
    }).join('') : '';
    return '<div class="g2"><div class="box"><h3>Hook Lab <span class="hint">writes hooks, then a strict judge ranks them</span></h3>' +
        '<label class="f">Post</label><select class="t" id="vx-hp"><option value="">— no post: general hooks for the account —</option>' + ps.map(function (x) { return '<option value="' + x.id + '"' + (x.id === HL.post ? ' selected' : '') + '>' + esc((x.hook || x.yt_title || x.id).slice(0, 60)) + ' · ' + x.status + '</option>'; }).join('') + '</select>' +
        '<label class="f">Direction (optional)</label><input class="t" id="vx-hn" placeholder="e.g. lean into the loop, series name, mystery angle" value="' + esc(HL.note || '') + '">' +
        '<div class="row" style="margin-top:10px"><select class="t" id="vx-hc" style="width:auto">' + [6, 10, 14].map(function (n) { return '<option' + (n === 10 ? ' selected' : '') + '>' + n + '</option>'; }).join('') + '</select><span class="dim">hooks</span><span class="sp"></span>' +
        '<button class="sb pri" id="vx-hrun"' + (HL.busy ? ' disabled' : '') + '>' + mi('wand') + (HL.busy ? ' VIRAL-Ω is writing + judging…' : ' Run Hook Lab') + '</button></div>' +
        (o && o.on_screen ? '<div class="vx-sum"><b>What’s on screen:</b> ' + esc(o.on_screen) + '</div>' : '') + (o && o.why ? '<div class="why">' + esc(o.why) + '</div>' : '') + (o && o.error ? '<div class="why" style="color:var(--bad)">' + esc(o.error) + '</div>' : '') + '</div>' +
      '<div class="box vx-mock"><h3>Frame-1 preview</h3><div class="vx-phone" id="vx-ph" style="' + (p && p.cover_url ? 'background-image:url(' + esc(p.cover_url) + ')' : '') + '"><span id="vx-pht">' + esc((o && o.hooks && o.hooks[0] && o.hooks[0].text) || (p && p.hook) || 'Your hook here') + '</span></div></div></div>' +
      (rows ? '<div class="box"><h3>Ranked hooks</h3>' + rows + '</div>' : '') +
      '<div class="box"><h3>Hook library</h3><div id="vx-lib" class="nodata">Loading…</div></div>';
  }

  // ── Remix: study a viral video → our original version → judged ────────────────────────────────────────────────────
  var STRAT = { auto: 'Auto — VIRAL picks', restyle: 'Restyle — same shot + motion, new subject & look', motion: 'Copy the movement — new character & world', recreate: 'Recreate — same structure, all-new shots' };
  function remixView() {
    if (!RX) { api('api/viral/remix').then(function (j) { RX = j; S().render(); }).catch(function (e) { S().toast(e.message); }); return '<div class="empty">Loading Remix…</div>'; }
    var fr = function (r, f) { return '<img src="api/viral/remix/' + r.id + '/frame/' + esc(f) + '" alt="">'; };
    var sc = function (v) { return v == null ? '–' : (Math.round(v * 10) / 10); };
    var list = (RX.remixes || []).map(function (r) {
      var live = /queued|running/.test(r.status), A = r.analysis || {};
      var atts = (r.attempts || []).map(function (a) {
        var j = a.judge || {}, p = a.plan || {};
        return '<div class="vx-att' + (r.best === a.n ? ' best' : '') + '"><div class="vx-ah"><b>Attempt ' + a.n + '</b> · ' + esc(p.strategy || '') + (r.best === a.n ? ' · ' + mi('star') + ' used' : '') +
          (a.judge ? ' <span class="vx-pass ' + (j.passed ? 'ok' : 'bad') + '">' + (j.passed ? 'passed' : 'below the bar') + '</span>' : a.status === 'failed' ? ' <span class="vx-pass bad">render failed</span>' : ' <span class="vx-pass">' + esc(a.status) + '</span>') + '</div>' +
          (p.concept ? '<div class="cap"><b>' + esc(p.title || '') + '</b> — ' + esc(p.concept) + '</div>' : '') + (p.twist ? '<div class="why"><b>Ours because:</b> ' + esc(p.twist) + '</div>' : '') +
          (p.hero ? '<div class="vx-hero"><img src="thumb/' + esc(p.hero) + '" alt=""><span><b>Locked character</b> — every shot renders from this one picture<small>' + esc(p.character || '') + '</small></span></div>' : '') +
          (a.judge ? '<div class="vx-scores"><span>mechanics <b>' + sc(j.mechanics) + '</b></span><span>originality <b>' + sc(j.originality) + '</b></span><span>quality <b>' + sc(j.quality) + '</b></span><span>hook <b>' + sc(j.hook) + '</b></span>' + (j.too_close ? '<span class="bad">too close to the source</span>' : '') + '</div>' +
            '<div class="vx-strip">' + (j.frames || []).map(function (f) { return fr(r, f); }).join('') + '</div>' + (j.why ? '<div class="why">' + esc(j.why) + '</div>' : '') +
            ((j.fixes || []).length && !j.passed ? '<div class="why"><b>Fixes for the next try:</b> ' + esc(j.fixes.join(' · ')) + '</div>' : '') : '') +
          (a.error ? '<div class="why" style="color:var(--bad)">' + esc(a.error) + '</div>' : '') + '</div>';
      }).join('');
      return '<div class="box vx-rx"><div class="row"><div style="flex:1;min-width:0"><b>' + esc(r.title || r.source) + '</b><small class="vx-sub">' + esc(STRAT[r.strategy] || r.strategy) + ' · ' + S().when(r.created) + '</small></div>' +
        '<span class="st ' + (r.status === 'done' ? 'published' : r.status === 'failed' ? 'failed' : 'scheduled') + '">' + esc(r.status) + '</span>' +
        (live ? '<button class="sb bad" data-rxc="' + r.id + '">Stop</button>' : '<button class="sb ic" data-rxd="' + r.id + '" title="Delete">' + mi('trash') + '</button>') + '</div>' +
        (live ? '<div class="vx-sum">' + mi('hourglass') + ' ' + esc(r.stage || '') + '</div>' : '') + (r.error ? '<div class="why" style="color:var(--bad)">' + esc(r.error) + '</div>' : '') +
        ((r.src_frames || []).length ? '<small class="vx-sub">The source, as VIRAL saw it</small><div class="vx-strip">' + r.src_frames.map(function (f) { return fr(r, f); }).join('') + '</div>' : '') +
        (A.mechanics ? '<details class="vx-feed"' + (live ? ' open' : '') + '><summary>Why it went viral</summary><div class="cap" style="max-height:none"><b>Hook:</b> ' + esc(A.hook) + '<br><b>Payoff:</b> ' + esc(A.payoff || '') + '<br><b>Mechanics:</b> ' + esc((A.mechanics || []).join(' · ')) + '<br><b>Won\u2019t copy:</b> ' + esc((A.protected || []).join(' · ')) + '<br><b>Strategy:</b> ' + esc(A.strategy || '') + ' — ' + esc(A.why_strategy || '') + '</div></details>' : '') +
        atts + (r.post ? '<div class="row"><button class="sb ok" data-go="queue">' + mi('check') + ' Open the draft in Queue</button></div>' : '') + '</div>';
    }).join('');
    return '<div class="box"><h3>Remix a viral video <span class="hint">VIRAL watches it, keeps what makes it travel, makes our own version, then judges the result</span></h3>' +
      '<label class="f">Video link (YouTube / Shorts, TikTok, Instagram…) — or lib:&lt;library file&gt;</label><input class="t" id="rx-src" value="' + esc(RXSEED) + '" placeholder="https://youtube.com/shorts/…">' +
      '<div class="row"><div style="flex:2;min-width:220px"><label class="f">How close</label><select class="t" id="rx-st">' + Object.keys(STRAT).map(function (k) { return '<option value="' + k + '">' + STRAT[k] + '</option>'; }).join('') + '</select></div>' +
      '<div style="flex:1;min-width:120px"><label class="f">Tries</label><select class="t" id="rx-n"><option value="1">1</option><option value="2" selected>2 (re-render if the judge says no)</option><option value="3">3</option></select></div></div>' +
      '<label class="f">Your direction (optional)</label><input class="t" id="rx-no" placeholder="e.g. make it a robot chef, keep the ending twist, our Cities that don\u2019t exist series">' +
      '<details class="vx-feed"><summary>Our identity (VIRAL keeps every remix on-brand)</summary><textarea class="t" id="rx-id" rows="3">' + esc(RX.identity || '') + '</textarea><button class="sb" id="rx-ids">' + mi('check') + ' Save identity</button></details>' +
      '<div class="row" style="margin-top:10px"><span class="dim" style="flex:1">Their footage, music and anyone\u2019s likeness are never reused — only the mechanics. The result lands as a draft for your approval.</span><button class="sb pri" id="rx-go">' + mi('layers') + ' Remix it</button></div></div>' +
      (list || '<div class="empty">No remixes yet. Paste a link, or press Remix on a trend pick.</div>');
  }

  // ── Planner: week calendar (drag scheduled posts between days) + pipeline board ────────────────────────────────────
  function plannerView() {
    if (!PIPE) { api('api/viral/pipeline').then(function (j) { PIPE = j; S().render(); }).catch(function (e) { S().toast(e.message); }); return '<div class="empty">Loading the planner…</div>'; }
    var d0 = new Date(); d0.setHours(0, 0, 0, 0);
    var days = []; for (var i = 0; i < 7; i++) days.push(new Date(d0.getTime() + i * 864e5));
    var sch = S().posts().filter(function (p) { return p.status === 'scheduled' && p.schedule_at; });
    var cal = days.map(function (d, i) {
      var a = d.getTime() / 1000, b = a + 86400;
      var here = sch.filter(function (p) { return p.schedule_at >= a && p.schedule_at < b; }).sort(function (x, y) { return x.schedule_at - y.schedule_at; });
      return '<div class="vx-day" data-day="' + a + '"><div class="vx-dh">' + d.toLocaleDateString([], { weekday: 'short', day: 'numeric' }) + '</div>' + here.map(function (p) {
        return '<div class="vx-ev" draggable="true" data-ev="' + p.id + '"><img src="' + esc(p.cover_url) + '" alt=""><span>' + new Date(p.schedule_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '<br>' + esc((p.hook || p.yt_title || '').slice(0, 40)) + '<small>' + (p.platforms || []).map(function (x) { return PLAT[x]; }).join(' ') + '</small></span></div>';
      }).join('') + '</div>';
    }).join('');
    var col = function (k, label, list, fn) { return '<div class="vx-col"><div class="vx-ch">' + label + ' <small>' + list.length + '</small></div>' + list.map(fn).join('') + '</div>'; };
    var pc = function (p) { return '<div class="vx-k">' + (p.cover ? '<img src="' + esc(p.cover) + '" alt="">' : '') + '<span>' + esc(p.hook) + (p.at ? '<small>' + S().when(p.at) + '</small>' : '') + '</span></div>'; };
    return '<div class="box"><h3>This week <span class="hint">drag a scheduled post to another day (or tap it on a phone) — it keeps its time</span></h3><div class="vx-cal">' + cal + '</div></div>' +
      '<div class="box"><h3>Pipeline</h3><div class="vx-board">' +
      col('ideas', 'Ideas', PIPE.ideas, function (x, i) { return '<div class="vx-k idea"><span>' + esc(x.title) + '<small>“' + esc(x.hook || '') + '” · ' + esc(x.src || '') + '</small></span>' + (x.lab_prompt ? '<button class="sb ic" data-pmk="' + i + '" title="Make it">' + mi('sparkle') + '</button>' : '') + '</div>'; }) +
      col('preparing', 'Preparing', PIPE.preparing, pc) + col('draft', 'Needs approval', PIPE.draft, pc) + col('scheduled', 'Scheduled', PIPE.scheduled, pc) + col('live', 'Live', PIPE.live, pc) +
      '</div></div>';
  }

  // ── Overview brief + Analytics insights ─────────────────────────────────────────────────────────────────────────
  function briefBox() {
    if (!BRIEF) { api('api/viral/brief').then(function (j) { BRIEF = j; S().render(); }).catch(function () { BRIEF = {}; }); return ''; }
    var b = BRIEF, w = b.winner, o = b.outlier;
    return '<div class="box vx-brief"><h3>' + mi('agent') + ' VIRAL-Ω daily brief <span class="hint">trends ' + ago(b.trends_t) + '</span></h3><div class="vx-bg">' +
      '<div><small>Riding now</small>' + ((b.trends || []).length ? b.trends.map(function (t) { return '<div class="vx-bt"><b>' + esc(t.angle || t.title) + '</b><small>' + esc(t.src) + ' · fit ' + esc(t.fit) + '/10</small></div>'; }).join('') : '<div class="nodata">No trend scan yet — <a href="#" data-go="trends">open Trends</a></div>') + '</div>' +
      '<div><small>Recommendation</small>' + (b.recommend ? '<div class="vx-bt"><b>“' + esc(b.recommend.hook) + '”</b><small>' + esc(b.recommend.format || '') + ' · ' + esc(b.recommend.why || '') + '</small></div><button class="sb pri" id="vx-brm">' + mi('sparkle') + ' Make it</button>' : '<div class="nodata">—</div>') + '</div>' +
      '<div><small>Recent winner</small>' + (w ? '<div class="vx-bt"><b>' + esc(w.hook) + '</b><small>' + fmt(w.views) + ' views · ' + w.share_rate + '% shares' + (w.hold != null ? ' · hold ' + Math.round(w.hold * 100) + '%' : '') + '</small></div>' : '<div class="nodata">No posts in the last 3 days.</div>') +
        (o ? '<small style="margin-top:8px">Watchlist breakout</small><div class="vx-bt"><b>' + o.x + '× · ' + esc(o.title) + '</b><small>' + esc(o.channel) + '</small></div>' : '') + '</div></div>' +
      (b.lessons ? '<details class="vx-feed"><summary>Lessons VIRAL learned from your numbers</summary><div class="cap" style="white-space:pre-wrap;max-height:none">' + esc(b.lessons) + '</div></details>' : '') + '</div>';
  }

  function insightsBox() {
    if (!INS) { api('api/viral/insights').then(function (j) { INS = j; S().render(); }).catch(function () { INS = { hooks: [] }; }); return '<div class="box"><div class="nodata">Loading VIRAL-Ω insights…</div></div>'; }
    var I = INS, ce = I.captions_effect || {};
    var heat = (I.heat || []).length ? '<table class="vx-heat"><tr><th></th>' + I.blocks.map(function (b) { return '<th>' + b + '</th>'; }).join('') + '</tr>' + I.heat.map(function (r) {
      var mx = Math.max.apply(0, I.heat.map(function (x) { return Math.max.apply(0, x.cells.map(function (c) { return c || 0; })); })) || 1;
      return '<tr><td>' + esc(r.pillar.slice(0, 16)) + '</td>' + r.cells.map(function (c) { return '<td style="background:' + (c == null ? 'transparent' : 'color-mix(in srgb,var(--acc) ' + Math.round(c / mx * 100) + '%,var(--panel2))') + '">' + (c == null ? '' : fmt(c)) + '</td>'; }).join('') + '</tr>';
    }).join('') + '</table>' : '<div class="nodata">Needs published posts.</div>';
    var ret = (I.retention || []).length ? (function () {
      var cols = ['var(--acc)', 'var(--ok)', 'var(--warn)', '#8ab4f8', '#c58af9'];
      return '<svg class="ch" viewBox="0 0 600 160">' + I.retention.map(function (r, i) { return '<path fill="none" stroke="' + cols[i % 5] + '" stroke-width="2" d="' + r.pts.map(function (p, j) { return (j ? 'L' : 'M') + (40 + p[0] * 550).toFixed(1) + ' ' + (140 - Math.min(1.5, p[1]) / 1.5 * 130).toFixed(1); }).join(' ') + '"/>'; }).join('') +
        '<text x="40" y="156" fill="currentColor" font-size="10">start</text><text x="560" y="156" fill="currentColor" font-size="10">end</text></svg><div class="lg">' + I.retention.map(function (r, i) { return '<span><i style="background:' + cols[i % 5] + '"></i>' + esc(r.hook) + '</span>'; }).join('') + '</div>';
    })() : '<div class="nodata">YouTube retention curves appear ~3 days after a video goes up.</div>';
    return '<div class="kpis"><div class="kpi"><small>Avg hold</small><b>' + (I.avg_hold != null ? Math.round(I.avg_hold * 100) + '%' : '—') + '</b></div>' +
        '<div class="kpi"><small>Median views</small><b>' + fmt(I.median_views) + '</b></div>' +
        '<div class="kpi"><small>Captioned avg</small><b>' + (ce.with != null ? fmt(ce.with) : '—') + '</b><em>' + (ce.n_with || 0) + ' posts</em></div>' +
        '<div class="kpi"><small>No captions avg</small><b>' + (ce.without != null ? fmt(ce.without) : '—') + '</b><em>' + (ce.n_without || 0) + ' posts</em></div></div>' +
      '<div class="g2"><div class="box"><h3>Hook leaderboard <span class="hint">× median · hold · share rate</span></h3>' + ((I.hooks || []).length ? I.hooks.slice(0, 8).map(function (h, i) {
        return '<div class="tp"><span class="rk">' + (i + 1) + '</span><img src="' + esc(h.cover) + '" alt=""><span class="tt">' + esc(h.hook) + '<small>' + esc(h.angle || h.pillar) + (h.captions ? ' · captioned' : '') + '</small></span><b>' + (h.x_median != null ? h.x_median + '×' : '—') + '</b><small style="width:110px;text-align:right">' + (h.hold != null ? 'hold ' + Math.round(h.hold * 100) + '% · ' : '') + h.share_rate + '% sh</small></div>';
      }).join('') : '<div class="nodata">No published posts yet.</div>') + '</div>' +
      '<div class="box"><h3>Pillar × time of day <span class="hint">avg views</span></h3>' + heat + '</div></div>' +
      '<div class="g2"><div class="box"><h3>YouTube retention</h3>' + ret + '</div>' +
      '<div class="box"><h3>Breakout posts <span class="hint">2×+ median</span></h3>' + ((I.outliers || []).length ? I.outliers.map(function (h) { return '<div class="tp"><img src="' + esc(h.cover) + '" alt=""><span class="tt">' + esc(h.hook) + '</span><b>' + h.x_median + '×</b></div>'; }).join('') : '<div class="nodata">None yet — VIRAL tells you when one breaks out.</div>') +
        '<button class="sb" id="vx-les">' + mi('book') + ' Re-learn lessons now</button></div></div>';
  }

  // ── on every post card ──────────────────────────────────────────────────────────────────────────────────────────
  function cardExtra(p) {
    var h = '', L = p.lint || [];
    var er = L.filter(function (x) { return x.level === 'error'; }).length, wn = L.length - er;
    if (L.length) h += '<details class="vx-lint ' + (er ? 'bad' : 'warn') + '"><summary>' + mi('warn') + ' ' + (er ? er + ' to fix' : '') + (er && wn ? ' · ' : '') + (wn ? wn + ' tip' + (wn > 1 ? 's' : '') : '') + '</summary>' + L.map(function (x) { return '<div>' + (x.level === 'error' ? '✖' : '•') + ' <b>' + esc(x.field) + '</b> ' + esc(x.msg) + '</div>'; }).join('') + '</details>';
    var hl = p.hook_lab;
    if (hl && hl.hooks && hl.hooks.length) h += '<div class="vx-mini">Hook Lab: ' + hl.hooks.slice(0, 3).map(function (x) { return '<span>' + esc(x.text) + ' <b>' + Math.round(x.total) + '</b></span>'; }).join('') + '</div>';
    if (p.captioned) h += '<div class="vx-mini">' + mi('cc') + ' captioned (' + esc(p.captioned.mode) + ', ' + esc(p.captioned.style) + ')</div>';
    else if (p.captions && p.captions !== 'none' && p.status === 'draft') h += '<div class="vx-mini">' + mi('cc') + ' VIRAL suggests captions: ' + esc(p.captions) + '</div>';
    if (/draft|failed|rejected|scheduled/.test(p.status) && p.media)
      h += '<div class="vx-tools"><button class="sb" data-vhl="' + p.id + '">' + mi('wand') + ' Hook Lab</button>' +
        (/draft|failed|rejected/.test(p.status) ? '<button class="sb" data-vcap="' + p.id + '">' + mi('cc') + (p.captioned ? ' Captions ✓' : ' Captions') + '</button>' : '') +
        '<button class="sb" data-vpv="' + p.id + '">' + mi('phone') + ' Platform preview</button></div>';
    return h;
  }

  function modal(html) { var m = $('#modal'); m.innerHTML = '<div class="in">' + html + '</div>'; m.hidden = false; if (window.MI && MI.fill) MI.fill(m); var x = $('#vx-mx'); if (x) x.onclick = function () { m.hidden = true; }; return m; }
  function post(id) { return S().posts().filter(function (p) { return p.id === id; })[0]; }

  function captionsDlg(p) {
    var m = modal('<div class="row"><b style="flex:1">Captions — MIR MOTION</b><button class="sb ic" id="vx-mx">' + mi('close') + '</button></div>' +
      '<p class="dim">Burns text into the 9:16 video (Reels / TikTok / FB). The YouTube 16:9 file stays clean. The original is kept — you can undo.</p>' +
      '<label class="f">What</label><select class="t" id="cx-m"><option value="hook">Hook on screen (first 2.5 s)</option><option value="speech">Spoken / sung words (Whisper)</option><option value="both" selected>Both</option></select>' +
      '<label class="f">Hook text</label><input class="t" id="cx-h" value="' + esc(p.hook || '') + '">' +
      '<div class="row"><div style="flex:1"><label class="f">Word style</label><select class="t" id="cx-s">' + ['pop', 'karaoke', 'reveal', 'box', 'plain'].map(function (s) { return '<option>' + s + '</option>'; }).join('') + '</select></div>' +
      '<div style="flex:1"><label class="f">Position</label><select class="t" id="cx-p"><option>bottom</option><option>middle</option><option>top</option></select></div></div>' +
      '<label style="display:block;margin:8px 0"><input type="checkbox" id="cx-u" checked> UPPERCASE</label><div id="cx-st" class="why"></div>' +
      '<div class="row">' + (p.captioned ? '<button class="sb bad" id="cx-off">Remove captions</button>' : '') + '<span class="sp"></span><button class="sb pri" id="cx-go">' + mi('cc') + ' Burn captions</button></div>');
    var poll = function () {
      api('api/viral/captions/' + p.id).then(function (j) {
        $('#cx-st', m) && ($('#cx-st', m).textContent = j.status === 'failed' ? 'Failed: ' + j.error : j.status === 'done' ? 'Done — ' + (j.words || 0) + ' words captioned.' : (j.stage || 'working') + '…');
        if (j.status === 'running') setTimeout(poll, 3000); else { S().toast(j.status === 'done' ? 'Captions burned in' : 'Captions failed'); S().reload(); }
      });
    };
    $('#cx-go', m).onclick = function () {
      $('#cx-go', m).disabled = true;
      api('api/viral/captions/' + p.id, { method: 'POST', body: { mode: $('#cx-m', m).value, hook: $('#cx-h', m).value, style: $('#cx-s', m).value, pos: $('#cx-p', m).value, upper: $('#cx-u', m).checked } })
        .then(function () { setTimeout(poll, 1500); }).catch(function (e) { $('#cx-st', m).textContent = e.message; $('#cx-go', m).disabled = false; });
    };
    var off = $('#cx-off', m); if (off) off.onclick = function () { api('api/viral/captions/' + p.id, { method: 'POST', body: { remove: true } }).then(function () { m.hidden = true; S().toast('Original video restored'); S().reload(); }).catch(function (e) { S().toast(e.message); }); };
  }

  function previewDlg(p) {
    var tags = (p.hashtags || []).map(function (h) { return '#' + h; }).join(' ');
    var ig = p.caption || '', fold = ig.split('\n')[0].slice(0, 125);
    var cnt = function (s, max) { var n = (s || '').length; return '<span class="vx-cnt' + (n > max ? ' over' : '') + '">' + n + '/' + max + '</span>'; };
    var phone = function (cls, inner) { return '<div class="vx-pm ' + cls + '"><div class="vx-pv" style="background-image:url(' + esc(p.cover_url) + ')">' + (p.captioned ? '' : '<span class="vx-ov">' + esc(p.hook || '') + '</span>') + inner + '</div></div>'; };
    var pl = p.platforms || [];
    modal('<div class="row"><b style="flex:1">How it will look</b><button class="sb ic" id="vx-mx">' + mi('close') + '</button></div><div class="vx-pms">' +
      (pl.indexOf('instagram') >= 0 ? '<div><small>Instagram Reels ' + cnt(ig, 2200) + '</small>' + phone('ig', '<div class="vx-cap"><b>mirmedialabs</b> ' + esc(fold) + (ig.length > fold.length ? ' <i>… more</i>' : '') + '<div class="tags">' + esc(tags) + '</div></div>') + '</div>' : '') +
      (pl.indexOf('tiktok') >= 0 ? '<div><small>TikTok ' + cnt(p.tt_caption, 150) + '</small>' + phone('tt', '<div class="vx-cap"><b>@mirmedialabs</b><br>' + esc(p.tt_caption || '') + '</div>') + '</div>' : '') +
      (pl.indexOf('facebook') >= 0 ? '<div><small>Facebook Reels</small>' + phone('fb', '<div class="vx-cap">' + esc(p.fb_caption || '') + '</div>') + '</div>' : '') +
      (pl.indexOf('youtube') >= 0 ? '<div class="vx-yt"><small>YouTube ' + cnt(p.yt_title, 70) + '</small><div class="vx-yth" style="background-image:url(' + esc(p.yt_video_url ? 'api/social/media/' + p.id + '_yt.jpg' : p.cover_url) + ')"></div><b>' + esc(p.yt_title || '(no title)') + '</b><small>MIR MEDIA LABS</small><div class="cap" style="white-space:pre-wrap">' + esc(p.yt_description || '') + '</div></div>' : '') +
      '</div>' + (p.pinned_comment ? '<div class="vx-sum"><b>Pinned comment:</b> ' + esc(p.pinned_comment) + '</div>' : ''));
  }

  function bind(view) {
    var root = $('#view');
    $$('[data-vhl]', root).forEach(function (b) { b.onclick = function () { HL.post = b.dataset.vhl; HL.out = (post(HL.post) || {}).hook_lab || null; S().go('hooklab'); }; });
    $$('[data-vcap]', root).forEach(function (b) { b.onclick = function () { captionsDlg(post(b.dataset.vcap)); }; });
    $$('[data-vpv]', root).forEach(function (b) { b.onclick = function () { previewDlg(post(b.dataset.vpv)); }; });
    $$('[data-vrx]', root).forEach(function (b) { b.onclick = function (e) { e.preventDefault(); RXSEED = b.dataset.vrx; S().go('remix'); }; });
    if (RXT && view !== 'remix') { clearInterval(RXT); RXT = null; }
    if (view === 'remix' && RX) {
      $('#rx-go').onclick = function () {
        var src = $('#rx-src').value.trim(); if (!src) return S().toast('Paste a video link first');
        $('#rx-go').disabled = true;
        api('api/viral/remix', { method: 'POST', body: { source: src, strategy: $('#rx-st').value, attempts: +$('#rx-n').value, notes: $('#rx-no').value } })
          .then(function () { RXSEED = ''; RX = null; S().toast('VIRAL is on it — downloading and watching the video'); S().render(); }).catch(function (e) { S().toast(e.message); $('#rx-go').disabled = false; });
      };
      $('#rx-ids').onclick = function () { api('api/viral/remix', { method: 'POST', body: { identity: $('#rx-id').value } }).then(function () { S().toast('Identity saved'); }).catch(function (e) { S().toast(e.message); }); };
      $$('[data-rxc]').forEach(function (b) { b.onclick = function () { api('api/viral/remix/' + b.dataset.rxc + '/cancel', { method: 'POST' }).then(function () { RX = null; S().render(); }); }; });
      $$('[data-rxd]').forEach(function (b) { b.onclick = function () { if (confirm('Delete this remix record? (The draft and library files stay.)')) api('api/viral/remix/' + b.dataset.rxd + '/delete', { method: 'POST' }).then(function () { RX = null; S().render(); }); }; });
      var live = (RX.remixes || []).some(function (r) { return /queued|running/.test(r.status); });
      if (live && !RXT) RXT = setInterval(function () {
        if (S().view() !== 'remix' || (document.activeElement && /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))) return;
        api('api/viral/remix').then(function (j) { RX = j; S().render(); if (!(j.remixes || []).some(function (r) { return /queued|running/.test(r.status); })) { clearInterval(RXT); RXT = null; S().reload(); } });
      }, 8000);
    }
    if (view === 'overview') { var bm = $('#vx-brm'); if (bm) bm.onclick = function () { make(BRIEF.recommend.lab_prompt); }; }
    if (view === 'analytics') { var le = $('#vx-les'); if (le) le.onclick = function () { le.disabled = true; S().toast('VIRAL-Ω is re-reading your numbers…'); api('api/viral/lessons', { method: 'POST' }).then(function () { BRIEF = null; S().toast('Lessons updated — VIRAL uses them on every post'); }).catch(function (e) { S().toast(e.message); }).then(function () { le.disabled = false; }); }; }
    if (view === 'trends' && TR) {
      $$('[data-vmk]').forEach(function (b) { b.onclick = function () { make(TR.picks[+b.dataset.vmk].lab_prompt); }; });
      $$('[data-vcp]').forEach(function (b) { b.onclick = function () { navigator.clipboard && navigator.clipboard.writeText(TR.picks[+b.dataset.vcp].lab_prompt || ''); S().toast('Prompt copied'); }; });
      $('#vx-cfg').onclick = function () { CFG_OPEN = !CFG_OPEN; S().render(); };
      var cs = $('#vx-cfgs'); if (cs) cs.onclick = function () {
        var sp = function (v) { return v.split(',').map(function (x) { return x.trim(); }).filter(Boolean); };
        api('api/viral/config', { method: 'POST', body: { keywords: sp($('#vx-kw').value), subreddits: sp($('#vx-sub').value), news: $('#vx-news').value, reddit_id: $('#vx-rid').value, reddit_secret: $('#vx-rsec').value, auto_trends: $('#vx-at').checked, auto_hooklab: $('#vx-ah').checked, auto_captions: $('#vx-ac').checked } })
          .then(function (c) { TR.config = c; CFG_OPEN = false; S().toast('Saved — next scan uses them'); S().render(); }).catch(function (e) { S().toast(e.message); });
      };
      $('#vx-ref').onclick = function () {
        api('api/viral/trends/refresh', { method: 'POST' }).then(function () { TR.refreshing = true; S().render(); S().toast('Scanning YouTube, Google, Reddit, news, TikTok…');
          var t = setInterval(function () { api('api/viral/trends').then(function (j) { if (!j.refreshing) { clearInterval(t); TR = j; BRIEF = null; if (S().view() === 'trends') S().render(); S().toast('Trend radar updated'); } }); }, 5000); });
      };
      var wa = $('#vx-wa'); wa.onclick = function () { var h = $('#vx-wh').value.trim(); if (!h) return; wa.disabled = true; api('api/viral/watch', { method: 'POST', body: { handle: h } }).then(function () { return api('api/viral/watch', { method: 'POST', body: { scan: 1 } }); }).then(function (w) { WATCH = w; S().render(); }).catch(function (e) { S().toast(e.message); wa.disabled = false; }); };
      $('#vx-ws').onclick = function () { S().toast('Scanning watchlist…'); api('api/viral/watch', { method: 'POST', body: { scan: 1 } }).then(function (w) { WATCH = w; S().render(); }).catch(function (e) { S().toast(e.message); }); };
      $$('[data-vwr]').forEach(function (a) { a.onclick = function (e) { e.preventDefault(); api('api/viral/watch', { method: 'POST', body: { remove: a.dataset.vwr } }).then(function (w) { WATCH = w; S().render(); }); }; });
    }
    if (view === 'hooklab') {
      $('#vx-hp').onchange = function () { HL.post = this.value; HL.out = (post(HL.post) || {}).hook_lab || null; S().render(); };
      $('#vx-hn').oninput = function () { HL.note = this.value; };
      $('#vx-hrun').onclick = function () {
        HL.busy = true; S().render();
        api('api/viral/hooklab', { method: 'POST', body: { post: HL.post || null, note: HL.note || '', n: +$('#vx-hc').value } })
          .then(function (j) { HL.out = j; }).catch(function (e) { HL.out = { error: e.message }; }).then(function () { HL.busy = false; if (S().view() === 'hooklab') S().render(); });
      };
      $$('[data-hpv]').forEach(function (b) { b.onclick = function () { $('#vx-pht').textContent = HL.out.hooks[+b.dataset.hpv].text; }; });
      $$('[data-huse]').forEach(function (b) { b.onclick = function () { var t = HL.out.hooks[+b.dataset.huse].text; api('api/social/posts/' + HL.post, { method: 'POST', body: { hook: t } }).then(function () { S().toast('Hook set: ' + t); S().reload(); }).catch(function (e) { S().toast(e.message); }); }; });
      api('api/viral/hooks').then(function (j) {
        var el = $('#vx-lib'); if (!el) return;
        el.className = '';
        el.innerHTML = '<div class="g2"><div><small class="dim">Our hooks by result</small>' + (j.library.length ? j.library.map(function (h) { return '<div class="vx-fi"><b class="vx-x">' + (h.x_median != null ? h.x_median + '×' : '—') + '</b>' + esc(h.hook) + '<small>' + (h.hold != null ? 'hold ' + Math.round(h.hold * 100) + '%' : '') + '</small></div>'; }).join('') : '<div class="nodata">Fills in as posts get metrics.</div>') + '</div>' +
          '<div><small class="dim">Proven formulas VIRAL adapts</small><div class="vx-chips">' + j.formulas.map(function (f) { return '<span class="vx-chip" title="' + esc(f.angle) + '">' + esc(f.template) + '</span>'; }).join('') + '</div></div></div>';
      });
    }
    if (view === 'planner' && PIPE) {
      $$('[data-pmk]').forEach(function (b) { b.onclick = function () { make(PIPE.ideas[+b.dataset.pmk].lab_prompt); }; });
      var move = function (p, dayTs) {
        var old = new Date(p.schedule_at * 1000), nd = new Date(dayTs * 1000);
        nd.setHours(old.getHours(), old.getMinutes(), 0, 0);
        if (nd.getTime() < Date.now() + 5 * 60e3) { S().toast('That time has already passed'); return; }
        api('api/social/posts/' + p.id, { method: 'POST', body: { schedule_at: nd.getTime() / 1000 } }).then(function () { $('#modal').hidden = true; S().toast('Moved to ' + nd.toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })); PIPE = null; S().reload(); }).catch(function (e) { S().toast(e.message); });
      };
      $$('[data-ev]').forEach(function (e) {
        e.ondragstart = function (ev) { ev.dataTransfer.setData('text/plain', e.dataset.ev); };
        e.onclick = function () {                    // touch screens can't drag: tap → pick the day
          var p = post(e.dataset.ev); if (!p) return;
          var m = modal('<div class="row"><b style="flex:1">Move “' + esc((p.hook || p.yt_title || '').slice(0, 40)) + '”</b><button class="sb ic" id="vx-mx">' + mi('close') + '</button></div><p class="dim">Keeps ' + new Date(p.schedule_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' — pick the day:</p><div class="vx-days">' +
            $$('.vx-day').map(function (d) { return '<button class="sb" data-mvd="' + d.dataset.day + '">' + esc(d.querySelector('.vx-dh').textContent) + '</button>'; }).join('') + '</div>');
          $$('[data-mvd]', m).forEach(function (b) { b.onclick = function () { move(p, +b.dataset.mvd); }; });
        };
      });
      $$('.vx-day').forEach(function (d) {
        d.ondragover = function (ev) { ev.preventDefault(); d.classList.add('over'); };
        d.ondragleave = function () { d.classList.remove('over'); };
        d.ondrop = function (ev) {
          ev.preventDefault(); d.classList.remove('over');
          var p = post(ev.dataTransfer.getData('text/plain')); if (p) move(p, +d.dataset.day);
        };
      });
    }
  }

  window.VIRAL = {
    views: { trends: trendsView, hooklab: hooklabView, planner: plannerView, remix: remixView },
    wrap: { overview: function (h) { return briefBox() + h; }, analytics: function (h) { return h.indexOf('class="kpis"') >= 0 ? h + '<h2 class="vx-h2">' + mi('agent') + ' VIRAL-Ω insights</h2>' + insightsBox() : h; } },
    cardExtra: cardExtra, bind: bind
  };
})();
