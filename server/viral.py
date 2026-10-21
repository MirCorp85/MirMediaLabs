"""
viral.py — VIRAL-Ω's research desk + hook engine.
═══════════════════════════════════════════════════════════════════════════════
social.py is the publisher; this module gives its agent the resources it lacked:

  brain      the owner's cloud brain (cloud.py: Claude / GPT / GLM) when one is set, else the local engine
  trends     live radar every 6 h: YouTube niche outliers + trending, Google Trends, Reddit, Google News, TikTok
             Creative Center (best-effort) → brain scores the fit for our account → picks with ready lab prompts
  watchlist  inspiration channels (YouTube handles): videos running far above that channel's own median
  hooks      hook library (our hooks scored by results) + 40 proven formulas; write-then-judge Hook Lab;
             vision (the local vision engine looks at 3 frames so the hook matches what's on screen)
  lint       platform rules (lengths, banned/spam tags, AI honesty, engagement bait) on every package
  lessons    weekly lessons.md, learned from our own numbers, appended to VIRAL's brief on every call
  captions   MIR MOTION (Remotion) burns an on-screen hook + Whisper word captions onto a post's video
  insights   hold rate (IG avg watch time / YT % viewed), share/save rates, YouTube retention curves

Nothing here publishes. Everything still lands as a draft the owner approves (social.approve is the only door).
  data/social/trends.json · watch.json · lessons.md · hooks_cache.json
"""
import base64
import os
import re
import statistics
import threading
import time
import xml.etree.ElementTree as ET

import requests

import core
import social

SD = social.SD
TR_FILE = os.path.join(SD, "trends.json")
WATCH_FILE = os.path.join(SD, "watch.json")
LESSONS_FILE = os.path.join(SD, "lessons.md")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MML-VIRAL/1.0"}
TREND_EVERY = 6 * 3600
WATCH_EVERY = 12 * 3600
DEFAULT_KW = ["ai video", "ai animation", "ai short film"]       # YouTube search = 100 quota units each; keep it small
DEFAULT_SUBS = ["aivideo", "StableDiffusion", "midjourney", "singularity"]
DEFAULT_NEWS = "AI video generator OR AI animation OR AI art"
_RLOCK = threading.Lock()
_STATE = {"refreshing": False, "captions": {}}


def _log(msg):
    social._log(msg)


def cfg():
    """Owner settings for the research desk (stored inside accounts.json → "viral")."""
    v = social.accounts().get("viral") or {}
    return {"keywords": v.get("keywords") or DEFAULT_KW, "subreddits": v.get("subreddits") or DEFAULT_SUBS,
            "news": v.get("news") or DEFAULT_NEWS, "auto_trends": v.get("auto_trends", True),
            "auto_captions": v.get("auto_captions", True), "auto_hooklab": v.get("auto_hooklab", True),
            "region": v.get("region") or "US",
            "reddit": bool(v.get("reddit_id") and v.get("reddit_secret"))}


def set_cfg(b):
    a = social.accounts()
    v = a.setdefault("viral", {})
    for k in ("keywords", "subreddits"):
        if isinstance(b.get(k), list):
            v[k] = [str(x).strip()[:60] for x in b[k] if str(x).strip()][:8]
    for k in ("news", "region", "reddit_id", "reddit_secret"):
        if isinstance(b.get(k), str) and b[k].strip():
            v[k] = b[k].strip()[:120]
    for k in ("auto_trends", "auto_captions", "auto_hooklab"):
        if k in b:
            v[k] = bool(b[k])
    social.save_accounts(a)
    return cfg()


# ── brain: the owner's cloud brain ─────────────────────────────────────────────────────────────────────────────────────
def brain_ask(prompt, system, timeout=300):
    """VIRAL's copywriter brain. Returns text, or None when no cloud brain is set (caller falls back local)."""
    b = social._brain()
    if not b:
        return None
    try:
        import cloud
        return cloud.ask(b, prompt, system, role="social", timeout=timeout) or None
    except Exception as e:
        _log("[viral] cloud brain: %s — using the local engine" % str(e)[:200])
        return None


def handle():
    return social.accounts().get("handle") or "our account"


def brand_tag():
    """The account handle as a hashtag ('@my_lab' → 'my_lab'); '' when no handle is set."""
    return re.sub(r"[^\w]", "", social.accounts().get("handle") or "").lower()


def lessons_text():
    try:
        with open(LESSONS_FILE, encoding="utf-8") as f:
            t = f.read().strip()
        return ("\n\n## Lessons learned from OUR numbers (apply them)\n" + t[:3000]) if t else ""
    except OSError:
        return ""


# ── trend radar ───────────────────────────────────────────────────────────────────────────────────────────────────
def _feed(url, n=15):
    """RSS or Atom → [{title, link, ...child tags}]."""
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in list(root.iter("item")) + list(root.iter("{http://www.w3.org/2005/Atom}entry")):
        d = {}
        for c in it:
            tag = c.tag.split("}")[-1]
            if tag == "link" and c.get("href"):
                d["link"] = c.get("href")
            elif tag not in d:
                d[tag] = (c.text or "").strip()
        if d.get("title"):
            out.append(d)
        if len(out) >= n:
            break
    return out


def _iso_secs(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    return sum(int(x or 0) * k for x, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def _yt_videos(ids):
    rows = {}
    for i in range(0, len(ids), 50):
        r = social._yt("GET", "/youtube/v3/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50])})
        for v in r.get("items") or []:
            s, sn = v.get("statistics", {}), v.get("snippet", {})
            pub = time.mktime(time.strptime(sn.get("publishedAt", "1970-01-01T00:00:00Z")[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
            rows[v["id"]] = {"id": v["id"], "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                             "channel_id": sn.get("channelId", ""), "views": int(s.get("viewCount", 0)),
                             "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0)),
                             "secs": _iso_secs(v.get("contentDetails", {}).get("duration")), "published": pub,
                             "thumb": ((sn.get("thumbnails") or {}).get("medium") or {}).get("url", ""),
                             "url": "https://youtu.be/" + v["id"]}
    return rows


def _yt_subs(chan_ids):
    subs, ids = {}, [c for c in chan_ids if c]
    for i in range(0, len(ids), 50):
        r = social._yt("GET", "/youtube/v3/channels", params={"part": "statistics", "id": ",".join(ids[i:i + 50])})
        for c in r.get("items") or []:
            subs[c["id"]] = int(c.get("statistics", {}).get("subscriberCount", 0) or 0)
    return subs


def src_youtube_niche(c):
    """Our niche on YouTube this week, ranked by OUTLIER score = views ÷ channel subscribers (luck-adjusted reach)."""
    after = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7 * 86400))
    ids = []
    for kw in c["keywords"][:3]:
        r = social._yt("GET", "/youtube/v3/search", params={"part": "id", "q": kw, "type": "video", "order": "viewCount",
                                                            "publishedAfter": after, "maxResults": 12, "relevanceLanguage": "en"})
        ids += [it["id"]["videoId"] for it in r.get("items") or [] if (it.get("id") or {}).get("videoId")]
    vids = _yt_videos(list(dict.fromkeys(ids)))
    subs = _yt_subs({v["channel_id"] for v in vids.values()})
    out = []
    for v in vids.values():
        hrs = max(1.0, (time.time() - v["published"]) / 3600)
        out_x = v["views"] / max(500, subs.get(v["channel_id"], 0))
        out.append({"src": "YouTube niche", "title": v["title"], "url": v["url"], "thumb": v["thumb"],
                    "stat": "%s views · %.1f× subs · %s/h · %ss" % (_k(v["views"]), out_x, _k(v["views"] / hrs), v["secs"]),
                    "signal": out_x, "who": v["channel"], "secs": v["secs"]})
    return sorted(out, key=lambda x: -x["signal"])[:15]


def src_youtube_trending(c):
    r = social._yt("GET", "/youtube/v3/videos", params={"part": "snippet,statistics", "chart": "mostPopular",
                                                        "regionCode": c["region"], "maxResults": 15})
    return [{"src": "YouTube trending", "title": v["snippet"]["title"], "url": "https://youtu.be/" + v["id"],
             "thumb": ((v["snippet"].get("thumbnails") or {}).get("medium") or {}).get("url", ""),
             "stat": "%s views" % _k(int(v.get("statistics", {}).get("viewCount", 0))), "who": v["snippet"].get("channelTitle", ""),
             "signal": int(v.get("statistics", {}).get("viewCount", 0))} for v in r.get("items") or []]


def src_google_trends(c):
    rows = _feed("https://trends.google.com/trending/rss?geo=%s" % c["region"], 20)
    return [{"src": "Google Trends", "title": r["title"], "url": r.get("link", ""), "stat": (r.get("approx_traffic") or "") + " searches",
             "signal": int(re.sub(r"\D", "", r.get("approx_traffic") or "0") or 0)} for r in rows]


REDDIT_UA = "windows:mml.viral:1.0"


def _reddit_token():
    """Reddit blocks anonymous scripts (403/429) — a free "script" app at reddit.com/prefs/apps gives an app-only token."""
    v = social.accounts().get("viral") or {}
    if not (v.get("reddit_id") and v.get("reddit_secret")):
        raise RuntimeError("Reddit blocks anonymous access — add a free Reddit app id + secret in Sources")
    if v.get("reddit_tok") and v.get("reddit_exp", 0) > time.time():
        return v["reddit_tok"]
    r = requests.post("https://www.reddit.com/api/v1/access_token", auth=(v["reddit_id"], v["reddit_secret"]),
                      data={"grant_type": "client_credentials"}, headers={"User-Agent": REDDIT_UA}, timeout=20).json()
    if "access_token" not in r:
        raise RuntimeError("Reddit login failed: %s" % (r.get("error") or r))
    a = social.accounts()
    a.setdefault("viral", {}).update(reddit_tok=r["access_token"], reddit_exp=time.time() + r.get("expires_in", 3600) - 60)
    social.save_accounts(a)
    return r["access_token"]


def src_reddit(c):
    tok, out = _reddit_token(), []
    for sub in c["subreddits"][:5]:
        r = requests.get("https://oauth.reddit.com/r/%s/top" % sub, params={"t": "week", "limit": 8}, timeout=20,
                         headers={"User-Agent": REDDIT_UA, "Authorization": "bearer " + tok})
        r.raise_for_status()
        for ch in r.json()["data"]["children"]:
            d = ch["data"]
            out.append({"src": "Reddit r/" + sub, "title": d.get("title", ""), "url": "https://reddit.com" + d.get("permalink", ""),
                        "stat": "%s upvotes · %s comments" % (_k(d.get("score", 0)), _k(d.get("num_comments", 0))),
                        "signal": int(d.get("score", 0))})
    return out


def src_news(c):
    from urllib.parse import quote
    rows = _feed("https://news.google.com/rss/search?q=%s+when:7d&hl=en-US&gl=US&ceid=US:en" % quote(c["news"]), 15)
    return [{"src": "Google News", "title": r["title"], "url": r.get("link", ""), "stat": r.get("pubDate", "")[:16], "signal": 0} for r in rows]


def src_tiktok(c):
    """TikTok Creative Center trending hashtags. Its API wants a browser session — best-effort, honest when blocked."""
    r = requests.get("https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list",
                     params={"page": 1, "limit": 20, "period": 7, "country_code": c["region"], "sort_by": "popular"},
                     headers=dict(UA, Referer="https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"),
                     timeout=20)
    j = r.json() if r.content else {}
    rows = ((j.get("data") or {}).get("list")) or []
    if not rows:
        raise RuntimeError("Creative Center needs a signed browser session (%s)" % (j.get("msg") or r.status_code))
    return [{"src": "TikTok hashtags", "title": "#" + x.get("hashtag_name", ""), "stat": "%s posts · rank %s" % (_k(x.get("publish_cnt", 0)), x.get("rank")),
             "url": "https://www.tiktok.com/tag/" + x.get("hashtag_name", ""), "signal": int(x.get("video_views", 0) or 0)} for x in rows]


SOURCES = (("YouTube niche", src_youtube_niche, True), ("YouTube trending", src_youtube_trending, True),
           ("Google Trends", src_google_trends, False), ("Reddit", src_reddit, False), ("Google News", src_news, False),
           ("TikTok", src_tiktok, False))


def _k(n):
    n = float(n or 0)
    return "%.1fM" % (n / 1e6) if n >= 1e6 else "%.1fK" % (n / 1e3) if n >= 1e3 else str(int(n))


def trends():
    return core.load_json(TR_FILE, {"t": 0, "items": [], "picks": [], "sources": {}, "summary": ""})


def refresh_trends(force=False):
    old = trends()
    if not force and time.time() - old.get("t", 0) < TREND_EVERY:
        return old
    if not _RLOCK.acquire(blocking=False):
        return dict(old, busy=True)
    _STATE["refreshing"] = True
    try:
        c, items, srcs = cfg(), [], {}
        yt_ok = bool((social.accounts().get("youtube") or {}).get("refresh_token"))
        for name, fn, need_yt in SOURCES:
            if need_yt and not yt_ok:
                srcs[name] = {"ok": False, "n": 0, "err": "connect YouTube in Accounts"}
                continue
            try:
                rows = fn(c)
                items += rows
                srcs[name] = {"ok": True, "n": len(rows)}
            except Exception as e:
                srcs[name] = {"ok": False, "n": 0, "err": str(e)[:160]}
        seen = old.get("seen") or {}
        now = time.time()
        for it in items:     # momentum: new this refresh, or its signal grew ≥20 %
            key = re.sub(r"\W+", "", it["title"].lower())[:80]
            prev = seen.get(key)
            it["rising"] = not prev or (it.get("signal", 0) > prev.get("signal", 0) * 1.2 and it.get("signal", 0) > 0)
            it["first_seen"] = (prev or {}).get("first", now)
            seen[key] = {"first": it["first_seen"], "signal": it.get("signal", 0), "last": now}
        seen = {k: v for k, v in seen.items() if now - v.get("last", 0) < 14 * 86400}
        compact = [{"i": i, "src": x["src"], "title": x["title"][:110], "stat": x.get("stat", ""), "rising": x["rising"]}
                   for i, x in enumerate(items)][:90]
        d = social.ask_agent(
            "You are scouting LIVE trends for %s (an AI media studio: striking AI-generated short videos, images, "
            "music). Below are real items pulled from YouTube, Google Trends, Reddit, Google News and TikTok in the last days. "
            "Pick the 8 with the best FIT (we can make an original AI video riding it, brand-safe, no real people's likeness, "
            "no copyrighted characters/music) and the most momentum. For each give a concrete original angle. Return JSON "
            '{"summary": 2 sentences on what is moving this week, "picks":[{"i": item index, "fit": 0-10, "angle": our '
            'original take, "hook": on-screen hook <=7 words, "format": e.g. before/after, POV, series, loop, "lab_prompt": '
            'ready-to-run MIR MEDIA LABS generation prompt (visual, motion, camera, mood), "duration": seconds, "why"}]}' % handle(),
            {"items": compact})
        picks = []
        for p in (d.get("picks") or [])[:10]:
            try:
                src = items[int(p.get("i"))]
            except (TypeError, ValueError, IndexError):
                continue
            picks.append(dict(p, title=src["title"], src=src["src"], url=src.get("url", ""), stat=src.get("stat", ""),
                              rising=src.get("rising"), thumb=src.get("thumb", "")))
        picks.sort(key=lambda x: -float(x.get("fit") or 0))
        out = {"t": now, "items": items[:150], "picks": picks, "sources": srcs, "summary": d.get("summary", ""), "seen": seen}
        core.save_json(TR_FILE, out)
        if picks:
            social._push("owner", "social_trends", "%s: %d trends worth riding" % (social.AGENT, len(picks)), picks[0].get("angle", "")[:120])
        return out
    finally:
        _STATE["refreshing"] = False
        _RLOCK.release()


# ── inspiration watchlist (YouTube channels) ─────────────────────────────────────────────────────────────────────
def watch():
    return core.load_json(WATCH_FILE, {"channels": [], "outliers": [], "t": 0})


def watch_add(handle):
    h = str(handle or "").strip()
    h = re.sub(r"^https?://(www\.)?youtube\.com/", "", h).strip("/")
    params = {"part": "snippet,contentDetails,statistics"}
    if h.startswith("channel/"):
        params["id"] = h.split("/", 1)[1]
    else:
        params["forHandle"] = h if h.startswith("@") else "@" + h
    it = (social._yt("GET", "/youtube/v3/channels", params=params).get("items") or [None])[0]
    if not it:
        raise ValueError("no YouTube channel found for %s" % handle)
    w = watch()
    if not any(c["id"] == it["id"] for c in w["channels"]):
        w["channels"].append({"id": it["id"], "title": it["snippet"]["title"], "handle": h,
                              "uploads": it["contentDetails"]["relatedPlaylists"]["uploads"],
                              "subs": int(it.get("statistics", {}).get("subscriberCount", 0) or 0)})
        w["channels"] = w["channels"][:20]
        core.save_json(WATCH_FILE, w)
    return w


def watch_remove(cid):
    w = watch()
    w["channels"] = [c for c in w["channels"] if c["id"] != cid]
    w["outliers"] = [o for o in w["outliers"] if o.get("channel_id") != cid]
    core.save_json(WATCH_FILE, w)
    return w


def watch_scan():
    """Per channel: its last 15 uploads; flag the ones at ≥2.5× that channel's own median (≈3 quota units/channel)."""
    w = watch()
    outl = []
    for ch in w["channels"]:
        try:
            pl = social._yt("GET", "/youtube/v3/playlistItems", params={"part": "contentDetails", "playlistId": ch["uploads"], "maxResults": 15})
            vids = _yt_videos([x["contentDetails"]["videoId"] for x in pl.get("items") or []])
            if len(vids) < 3:
                continue
            med = statistics.median(v["views"] for v in vids.values()) or 1
            for v in vids.values():
                x = v["views"] / med
                if x >= 2.5 and time.time() - v["published"] < 45 * 86400:
                    outl.append(dict(v, x=round(x, 1), channel_id=ch["id"], median=med))
        except Exception as e:
            _log("[viral] watch %s: %s" % (ch.get("title"), e))
    w["outliers"] = sorted(outl, key=lambda v: -v["x"])[:30]
    w["t"] = time.time()
    core.save_json(WATCH_FILE, w)
    return w


# ── performance: hold rate, share/save rate, retention ───────────────────────────────────────────────────────────
def post_score(p):
    """One published post → the numbers VIRAL learns from."""
    v = l = sh = sv = c = 0
    hold, dur = None, float((p.get("media") or {}).get("duration") or 0)
    for pl, h in (p.get("metrics") or {}).items():
        if not h:
            continue
        x = h[-1]
        v += social._views(x); l += int(x.get("likes", 0) or 0); c += int(x.get("comments", 0) or 0)
        sh += int(x.get("shares", 0) or 0); sv += int(x.get("saved", 0) or 0)
        if pl == "instagram" and x.get("ig_reels_avg_watch_time") and dur:
            hold = min(1.5, float(x["ig_reels_avg_watch_time"]) / 1000.0 / dur)     # ms ÷ length (loops push it past 1)
        if pl == "youtube" and x.get("avg_view_pct") and hold is None:
            hold = float(x["avg_view_pct"]) / 100.0
    return {"views": v, "likes": l, "comments": c, "shares": sh, "saved": sv,
            "share_rate": round(sh / v * 100, 2) if v else 0, "save_rate": round(sv / v * 100, 2) if v else 0,
            "eng": round((l + c + sh + sv) / v * 100, 2) if v else 0, "hold": round(hold, 3) if hold is not None else None}


def yt_retention(vid):
    r = social._yt("GET", "/v2/reports", base="https://youtubeanalytics.googleapis.com", params={
        "ids": "channel==MINE", "startDate": "2020-01-01", "endDate": time.strftime("%Y-%m-%d"),
        "metrics": "audienceWatchRatio", "dimensions": "elapsedVideoTimeRatio", "filters": "video==" + vid})
    return [[round(float(a), 3), round(float(b), 3)] for a, b in r.get("rows") or []]


def insights():
    """Analytics the base charts don't have: hook leaderboard, hold/share/save, pillar×time heatmap, outliers, retention."""
    pub = [p for p in social.posts() if p["status"] == "published"]
    rows = []
    for p in pub:
        s = post_score(p)
        lt = time.localtime(p.get("published_at", 0))
        rows.append(dict(s, id=p["id"], hook=p.get("hook") or p.get("yt_title") or "", pillar=p.get("pillar") or "—",
                         angle=(p.get("hook_lab") or {}).get("angle") or "", t=p.get("published_at"), hour=lt.tm_hour,
                         dow=lt.tm_wday, cover="api/social/media/%s.jpg" % p["id"], retention=(p.get("retention") or {}).get("youtube"),
                         captions=bool(p.get("captioned"))))
    med = statistics.median([r["views"] for r in rows]) if rows else 0
    for r in rows:
        r["x_median"] = round(r["views"] / med, 2) if med else None
    board = sorted(rows, key=lambda r: -((r["x_median"] or 0) + (r["hold"] or 0) + r["share_rate"] / 2))
    pill = {}
    for r in rows:   # pillar × day-part heatmap (4 blocks) — average views
        cell = pill.setdefault(r["pillar"], [[0, 0] for _ in range(4)])
        b = 0 if r["hour"] < 11 else 1 if r["hour"] < 15 else 2 if r["hour"] < 19 else 3
        cell[b][0] += r["views"]; cell[b][1] += 1
    heat = [{"pillar": k, "cells": [round(a / n) if n else None for a, n in v]} for k, v in pill.items()]
    holds = [r["hold"] for r in rows if r["hold"] is not None]
    cap = [r["views"] for r in rows if r["captions"]]
    nocap = [r["views"] for r in rows if not r["captions"]]
    return {"median_views": med, "hooks": board[:15], "heat": heat, "blocks": ["morning", "midday", "afternoon", "evening"],
            "outliers": [r for r in rows if r["x_median"] and r["x_median"] >= 2][-6:],
            "retention": [{"hook": r["hook"][:30], "pts": r["retention"]} for r in rows if r["retention"]][-5:],
            "avg_hold": round(statistics.mean(holds), 3) if holds else None,
            "captions_effect": {"with": round(statistics.mean(cap)) if cap else None, "without": round(statistics.mean(nocap)) if nocap else None,
                                "n_with": len(cap), "n_without": len(nocap)}}


# ── hook engine ──────────────────────────────────────────────────────────────────────────────────────────────────
FORMULAS = [
    ("curiosity", "This shouldn't be possible"), ("curiosity", "Wait for the last second"), ("curiosity", "Nobody noticed the {detail}"),
    ("curiosity", "Watch what happens to the {thing}"), ("curiosity", "The ending changes everything"), ("curiosity", "Look closer at the {thing}"),
    ("bold claim", "This city doesn't exist"), ("bold claim", "{thing} that never happened"), ("bold claim", "AI made this in {n} seconds"),
    ("bold claim", "Not real. Not one frame."), ("bold claim", "The most {adj} {thing} ever made"), ("bold claim", "You've never seen {thing} like this"),
    ("question", "Would you live here?"), ("question", "Which one: 1 or 2?"), ("question", "Real or AI?"), ("question", "Could you spot the glitch?"),
    ("question", "What would you name this?"), ("number", "{n} worlds in {n2} seconds"), ("number", "Day {n} of {series}"),
    ("number", "{n} places that don't exist"), ("number", "Part {n}: {thing}"), ("pov", "POV: you wake up in {place}"),
    ("pov", "POV: {thing} is your neighbour"), ("pov", "POV: the last {thing} on Earth"), ("pov", "POV: you found {thing}"),
    ("contrast", "{a} vs {b}"), ("contrast", "Before AI / after AI"), ("contrast", "Expectation vs what AI made"),
    ("contrast", "Same prompt, {n} styles"), ("story", "He built this for one reason"), ("story", "It started as one sentence"),
    ("story", "The prompt was just three words"), ("challenge", "Pause on the best frame"), ("challenge", "Find the {thing}"),
    ("challenge", "Comment a world, I'll make it"), ("series", "{series} #{n}"), ("series", "Cities that don't exist #{n}"),
    ("sensory", "Turn the sound on"), ("sensory", "Satisfying {thing}"), ("sensory", "This sound was AI too"),
]
BANNED_TAGS = {"follow4follow", "f4f", "like4like", "l4l", "followforfollow", "likeforlike", "instagood", "tagsforlikes",
               "midjourney", "sora", "runway", "pika", "kling", "veo", "dalle", "fyp", "foryou", "foryoupage", "viral"}
BAIT = re.compile(r"\b(like if|comment yes|type yes|tag \d+ friends|follow (me )?for follow|share this or|"
                  r"giveaway|free iphone|100% real|not ai|real footage)\b", re.I)


def hook_library():
    """Our own hooks, scored by results (× median views + hold + share rate)."""
    ins = insights()
    return [{"hook": h["hook"], "angle": h["angle"], "x_median": h["x_median"], "hold": h["hold"], "share_rate": h["share_rate"]}
            for h in ins["hooks"] if h["hook"]][:12]


def frames(pid, n=3):
    """3 JPG stills across the post's video → base64 (for the vision engine)."""
    p = social.get(pid)
    if not p or not p.get("media"):
        return []
    src = os.path.join(social.OUT, p["media"]["file"])
    dur = float(p["media"].get("duration") or 6)
    out = []
    for i, at in enumerate((0.4, dur * 0.4, dur * 0.8)[:n]):
        f = os.path.join(social.OUT, "%s_f%d.jpg" % (pid, i))
        social._ff(["-ss", "%.2f" % at, "-i", src, "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "4", f], 60)
        if os.path.isfile(f):
            with open(f, "rb") as fh:
                out.append(base64.b64encode(fh.read()).decode())
            os.remove(f)
    return out


def see(pid, force=False):
    """The local vision engine describes what is ACTUALLY on screen (first frame, middle, end). Cached on the post."""
    p = social.get(pid)
    if not p:
        return ""
    if p.get("vision") and not force:
        return p["vision"]
    imgs = frames(pid)
    if not imgs:
        return ""
    try:
        txt = core.ask("These are 3 frames (start, middle, end) of one short video. In 3-5 plain sentences: what is the "
                       "subject, what happens, what is the single most surprising visual, what is in the very FIRST frame, "
                       "and does the end loop back to the start? No guessing beyond what you see.",
                       "You describe video frames precisely for a social media editor.", timeout=240, images=imgs)
    except Exception as e:
        _log("[viral] vision: %s" % e)
        return ""
    social.update(pid, vision=txt[:1200])
    return txt[:1200]


def lint(p):
    """Platform rules + our hard rules → [{field, level: error|warn, msg}]."""
    out = []

    def add(f, lv, m):
        out.append({"field": f, "level": lv, "msg": m})
    hook = (p.get("hook") or "").strip()
    if hook and len(hook.split()) > 7:
        add("hook", "warn", "hook is %d words — keep it ≤7 so it reads in the first second" % len(hook.split()))
    cap = p.get("caption") or ""
    if len(cap) > 2200:
        add("caption", "error", "Instagram caption is %d chars (max 2200)" % len(cap))
    first = cap.split("\n", 1)[0]
    if cap and len(first) > 125:
        add("caption", "warn", "line 1 is %d chars — IG cuts it at ~125, the hook must be above the fold" % len(first))
    tags = [str(h).lower().lstrip("#") for h in p.get("hashtags") or []]
    if len(tags) > 8:
        add("hashtags", "warn", "%d hashtags — 3-6 niche tags classify better than a wall" % len(tags))
    bad = sorted(set(tags) & BANNED_TAGS)
    if bad:
        add("hashtags", "error", "remove spam / tools-we-didn't-use tags: #" + " #".join(bad))
    brand = brand_tag()
    if brand and brand not in tags:
        add("hashtags", "warn", "missing the brand tag #" + brand)
    tt = p.get("tt_caption") or ""
    if "tiktok" in (p.get("platforms") or []):
        if len(tt) > 2200:
            add("tt_caption", "error", "TikTok caption over 2200 chars")
        elif len(tt) > 150:
            add("tt_caption", "warn", "TikTok caption %d chars — under 150 performs best" % len(tt))
        if not (p.get("tiktok") or {}).get("privacy_level"):
            add("tiktok", "warn", "TikTok privacy not chosen yet (required before Approve)")
    yt = p.get("yt_title") or ""
    if "youtube" in (p.get("platforms") or []):
        if not yt:
            add("yt_title", "error", "YouTube title missing")
        elif len(yt) > 100:
            add("yt_title", "error", "YouTube title %d chars (max 100)" % len(yt))
        elif len(yt) > 70:
            add("yt_title", "warn", "YouTube title %d chars — ≤70 shows in full in search" % len(yt))
        if "#shorts" in (p.get("yt_description") or "").lower():
            add("yt_description", "error", "remove #shorts — we post normal 16:9 videos")
        if len(p.get("yt_description") or "") > 5000:
            add("yt_description", "error", "YouTube description over 5000 chars")
    for f in ("hook", "caption", "tt_caption", "fb_caption", "yt_title", "yt_description", "pinned_comment"):
        m = BAIT.search(p.get(f) or "")
        if m:
            add(f, "error", "“%s” breaks platform rules or our honesty rule (content is AI-generated)" % m.group(0))
    if not p.get("pinned_comment"):
        add("pinned_comment", "warn", "no pinned first comment — first-hour replies are a strong signal")
    return out


def hook_lab(pid=None, note="", n=10, apply=False):
    """Write N hooks with different angles, then a separate JUDGE pass scores them. Stored on the post as hook_lab."""
    p = social.get(pid) if pid else None
    ctx = {"note": note, "winning_hooks": hook_library(),
           "formulas": [{"angle": a, "template": t} for a, t in FORMULAS],
           "trends": [{"angle": x.get("angle"), "format": x.get("format")} for x in trends().get("picks", [])[:5]]}
    if p:
        ctx["post"] = {k: p.get(k) for k in ("hook", "caption", "brief", "pillar", "platforms")}
        ctx["on_screen"] = see(pid)
        ctx["duration"] = (p.get("media") or {}).get("duration")
    gen = social.ask_agent(
        "Write %d on-screen first-second HOOKS (<=7 words each) for this piece. Each must use a DIFFERENT angle "
        "(curiosity, bold claim, question, number, POV, contrast, story, challenge, series, sensory). Ground them in what is "
        "actually ON SCREEN (on_screen) — a hook that promises something the first frame doesn't show kills retention. Learn "
        "from winning_hooks; adapt formulas, don't paste them. Return JSON {\"hooks\":[{\"text\",\"angle\",\"formula\"}]}" % n, ctx)
    cands = [h for h in (gen.get("hooks") or []) if isinstance(h, dict) and h.get("text")][:n]
    if not cands:
        return {"hooks": [], "error": "the writer returned no hooks"}
    judge = social.ask_agent(
        "Act as a STRICT, independent short-form hook judge (you did not write these). Score each hook 1-10 on: "
        "stop (would a thumb stop in 1 s), gap (curiosity gap that only watching closes), match (honestly matches the first "
        "frame — use on_screen), clarity (instant to read, <=7 words), safe (no bait, no false claims, AI-honest). total = "
        "weighted 0-100 (stop 30, gap 25, match 25, clarity 10, safe 10). Return JSON {\"scores\":[{\"i\",\"stop\",\"gap\","
        "\"match\",\"clarity\",\"safe\",\"total\",\"note\"}],\"best\": i,\"why\": one sentence}",
        dict(ctx, hooks=[{"i": i, "text": h["text"], "angle": h.get("angle")} for i, h in enumerate(cands)], formulas=None, winning_hooks=None))
    sc = {int(s.get("i", -1)): s for s in judge.get("scores") or [] if isinstance(s, dict) and str(s.get("i", "")).lstrip("-").isdigit()}
    rows = []
    for i, h in enumerate(cands):
        s = sc.get(i, {})
        rows.append(dict(h, total=float(s.get("total") or 0), parts={k: s.get(k) for k in ("stop", "gap", "match", "clarity", "safe")},
                         note=s.get("note", ""), words=len(h["text"].split()),
                         lint=[x["msg"] for x in lint({"hook": h["text"], "pinned_comment": "x", "hashtags": [brand_tag()]}) if x["field"] == "hook"]))
    rows.sort(key=lambda r: -r["total"])
    res = {"t": time.time(), "hooks": rows, "why": judge.get("why", ""), "on_screen": ctx.get("on_screen", "")}
    if p:
        upd = {"hook_lab": {"t": res["t"], "hooks": rows[:5], "why": res["why"], "angle": rows[0].get("angle", "")}}
        if apply and rows:
            upd["hook"] = rows[0]["text"]
        social.update(pid, **upd)
    return res


# ── lessons (weekly, from our own numbers) ───────────────────────────────────────────────────────────────────────
def write_lessons():
    ins = insights()
    if not ins["hooks"]:
        return ""
    txt = social.ask_agent(
        "From OUR post results below, write at most 10 short bullet lessons that will change what we post next "
        "(hooks/angles that beat the median, hold-rate patterns, captions on vs off, pillars, day-parts, what flopped). "
        "Only claims the numbers support; cite the number in each bullet. Plain markdown bullets.",
        {k: ins[k] for k in ("median_views", "hooks", "heat", "blocks", "avg_hold", "captions_effect")}, want_json=False)
    txt = (txt or "").strip()
    if txt:
        with open(LESSONS_FILE, "w", encoding="utf-8") as f:
            f.write("_Updated %s_\n\n%s\n" % (time.strftime("%Y-%m-%d"), txt[:3000]))
    return txt


# ── captions via MIR MOTION (Remotion) ───────────────────────────────────────────────────────────────────────────
CAP_STYLES = ("pop", "karaoke", "reveal", "box", "plain")


def captions(pid, mode="both", style="pop", pos="bottom", upper=True, hook_text=None, wait=False):
    """Burn captions onto the post's 9:16 video with MIR MOTION. mode: hook (on-screen hook for the first 2.5 s),
    speech (Whisper word captions), both. The raw video is kept as media_raw; the post stays a DRAFT."""
    p = social.get(pid)
    if not p or not p.get("media"):
        raise ValueError("post has no formatted video yet")
    if p["status"] not in ("draft", "failed", "rejected", "preparing"):
        raise ValueError("only drafts can be re-captioned")
    style = style if style in CAP_STYLES else "pop"
    job = {"status": "running", "stage": "starting", "t": time.time(), "mode": mode}
    _STATE["captions"][pid] = job

    def run():
        import remotion
        try:
            raw = (p.get("media_raw") or p["media"])["file"]
            src = os.path.join(social.OUT, raw)
            dur = float(social.probe(src)["duration"] or (p["media"].get("duration") or 0))
            if dur <= 0:
                raise RuntimeError("could not read the video length")
            lib_in = core.new_name("social_raw", ".mp4")            # Remotion reads media from the library ("lib:")
            import shutil
            shutil.copy2(src, os.path.join(core.LIB, lib_in))      # temporary: not indexed, removed after the render
            caps, words = [], []
            if mode in ("speech", "both"):
                job["stage"] = "transcribing (Whisper)"
                import series_audio
                try:
                    words = [w for w in ((series_audio.words_of(src) or {}).get("words") or []) if w.get("w")]
                except Exception as e:
                    _log("[viral] whisper: %s" % e)
            h = (hook_text if hook_text is not None else p.get("hook") or "").strip()
            hook_end = 0.0
            if h and (mode in ("hook", "both") or not words):      # speech chosen but nobody talks → the hook still goes on
                hook_end = min(2.6, dur)
                caps.append(remotion.scene("captions", hook_end, {"text": h, "style": "box", "pos": "middle", "perLine": 4,
                                                                  "size": 84, "upper": bool(upper)}, 0.0, out={"type": "fade", "dur": 0.3}))
            ws = [{"w": w["w"], "s": float(w["s"]), "e": float(w["e"])} for w in words if float(w["s"]) >= hook_end - 0.05]
            if len(ws) >= 3:
                caps.append(remotion.scene("captions", max(0.5, min(dur, ws[-1]["e"] + 0.6) - ws[0]["s"]),
                                           {"words": [dict(w, s=w["s"] - ws[0]["s"], e=w["e"] - ws[0]["s"]) for w in ws],
                                            "style": style, "pos": pos, "perLine": 4, "size": 72, "upper": bool(upper)}, ws[0]["s"]))
            if not caps:
                raise RuntimeError("nothing to caption (no hook text and no speech found)")
            proj = remotion.project("VIRAL-Ω captions " + pid, 1080, 1920, 30,
                                    [{"kind": "scene", "name": "Video", "clips": [remotion.scene("media", dur, {"src": "lib:" + lib_in, "kind": "video"}, 0.0)]},
                                     {"kind": "captions", "name": "Captions", "clips": caps}])
            job["stage"] = "rendering (MIR MOTION)"
            lib_out = core.new_name("social_cap", ".mp4")
            try:
                remotion.render_sync(proj, os.path.join(core.LIB, lib_out), "mp4", 18)
            finally:
                try:
                    os.remove(os.path.join(core.LIB, lib_in))
                except OSError:
                    pass
            core.index_add(lib_out, {"model": "social+motion", "prompt": "Captioned: " + h[:80], "created": time.time(), "user": "owner"})
            job["stage"] = "formatting"
            media = social.format_vertical(os.path.join(core.LIB, lib_out), pid + "_cap")
            new = dict(p["media"], file=media["file"], duration=media["duration"])
            social.update(pid, media=new, media_raw=p.get("media_raw") or p["media"], captioned={"mode": mode, "style": style,
                          "words": len(ws), "t": time.time(), "lib": lib_out})
            cv = os.path.join(social.OUT, pid + "_cap.jpg")
            if os.path.isfile(cv):
                os.replace(cv, os.path.join(social.OUT, pid + ".jpg"))
            job.update(status="done", stage="done", words=len(ws))
        except Exception as e:
            job.update(status="failed", error=str(e)[:300])
            _log("[viral] captions %s: %s" % (pid, e))

    if wait:
        run()
    else:
        threading.Thread(target=run, daemon=True, name="viral-captions").start()
    return job


def uncaption(pid):
    p = social.get(pid)
    if not p or not p.get("media_raw"):
        raise ValueError("no uncaptioned original kept")
    social._ff(["-ss", "0.5", "-i", os.path.join(social.OUT, p["media_raw"]["file"]), "-frames:v", "1", "-q:v", "2",
                os.path.join(social.OUT, pid + ".jpg")], 60)
    return social.update(pid, media=p["media_raw"], media_raw=None, captioned=None)


def on_drafted(pid):
    """Called by social.create_draft after the copy is written: judge the hook, decide on captions, lint."""
    c = cfg()
    try:
        if c["auto_hooklab"]:
            hook_lab(pid, apply=True)
    except Exception as e:
        _log("[viral] auto hook lab: %s" % e)
    p = social.get(pid) or {}
    try:
        dec = (p.get("captions") or "none").lower()
        if c["auto_captions"] and dec in ("hook", "speech", "both") and p.get("media"):
            captions(pid, mode=dec, wait=True)
    except Exception as e:
        _log("[viral] auto captions: %s" % e)
    social.update(pid, lint=lint(social.get(pid) or {}))


# ── daily brief + pipeline ───────────────────────────────────────────────────────────────────────────────────────
def brief():
    tr = trends()
    pub = [p for p in social.posts() if p["status"] == "published" and time.time() - p.get("published_at", 0) < 3 * 86400]
    win = max(pub, key=lambda p: post_score(p)["views"], default=None)
    w = watch()
    return {"trends": tr.get("picks", [])[:3], "summary": tr.get("summary", ""), "trends_t": tr.get("t", 0),
            "recommend": (tr.get("picks") or [None])[0],
            "winner": dict(post_score(win), id=win["id"], hook=win.get("hook") or win.get("yt_title"), cover="api/social/media/%s.jpg" % win["id"]) if win else None,
            "outlier": (w.get("outliers") or [None])[0], "refreshing": _STATE["refreshing"],
            "lessons": lessons_text().strip()[:600]}


def pipeline():
    ideas = core.load_json(os.path.join(SD, "ideas.json"), {}).get("ideas") or []
    tr = trends().get("picks") or []
    cols = {"ideas": [{"title": i.get("title"), "hook": i.get("hook"), "lab_prompt": i.get("lab_prompt"), "src": "VIRAL-Ω"} for i in ideas] +
                     [{"title": t.get("angle") or t.get("title"), "hook": t.get("hook"), "lab_prompt": t.get("lab_prompt"), "src": t.get("src")} for t in tr[:5]],
            "preparing": [], "draft": [], "scheduled": [], "live": []}
    for p in sorted(social.posts(), key=lambda x: -x.get("updated", 0)):
        k = {"preparing": "preparing", "draft": "draft", "failed": "draft", "scheduled": "scheduled", "approved": "scheduled",
             "publishing": "scheduled", "published": "live"}.get(p["status"])
        if k and len(cols[k]) < 12:
            cols[k].append({"id": p["id"], "hook": p.get("hook") or p.get("yt_title") or p["id"], "status": p["status"],
                            "at": p.get("schedule_at") or p.get("published_at"), "cover": "api/social/media/%s.jpg" % p["id"]})
    return cols


# ── background desk ──────────────────────────────────────────────────────────────────────────────────────────────
_STARTED = []


def _loop():
    time.sleep(90)                                   # let the server settle first
    last_watch = last_ret = 0
    while True:
        try:
            now = time.time()
            yt_ok = bool((social.accounts().get("youtube") or {}).get("refresh_token"))
            if cfg()["auto_trends"] and now - trends().get("t", 0) > TREND_EVERY:
                refresh_trends()
            if yt_ok and watch()["channels"] and now - last_watch > WATCH_EVERY:
                last_watch = now
                watch_scan()
            if yt_ok and now - last_ret > 12 * 3600:      # YouTube Analytics lags ~2 days: retention for posts 3-30 days old
                last_ret = now
                for p in social.posts():
                    yid = ((p.get("remote") or {}).get("youtube") or {}).get("id")
                    age = now - p.get("published_at", now)
                    if yid and 3 * 86400 < age < 30 * 86400 and not (p.get("retention") or {}).get("youtube"):
                        try:
                            pts = yt_retention(yid)
                            if pts:
                                social.update(p["id"], retention=dict(p.get("retention") or {}, youtube=pts))
                        except Exception as e:
                            _log("[viral] retention: %s" % str(e)[:160])
                            break
            lt = time.localtime()
            mt = os.path.getmtime(LESSONS_FILE) if os.path.isfile(LESSONS_FILE) else 0
            if lt.tm_wday == 0 and lt.tm_hour >= 9 and now - mt > 5 * 86400:
                write_lessons()
        except Exception as e:
            _log("[viral] loop: %s" % e)
        time.sleep(600)


def start():
    if not _STARTED:
        _STARTED.append(1)
        threading.Thread(target=_loop, daemon=True, name="viral-desk").start()


# ── routes (/api/viral/*) ───────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    from flask import request, jsonify, abort

    def owner():
        if not hk["is_owner"]():
            abort(403)

    def body():
        return request.get_json(silent=True) or {}

    def safe(fn, *a, **k):
        try:
            return jsonify(fn(*a, **k))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            _log("[viral] %s: %s" % (getattr(fn, "__name__", "?"), e))
            return jsonify({"error": str(e)[:300]}), 500

    @app.get("/api/viral/trends")
    def viral_trends():
        owner()
        t = trends()
        t.pop("seen", None)
        return jsonify(dict(t, refreshing=_STATE["refreshing"], config=cfg()))

    @app.post("/api/viral/trends/refresh")
    def viral_trends_refresh():
        owner()
        if _STATE["refreshing"]:
            return jsonify({"refreshing": True})
        threading.Thread(target=refresh_trends, kwargs={"force": True}, daemon=True, name="viral-trends").start()
        return jsonify({"refreshing": True})

    @app.post("/api/viral/config")
    def viral_config():
        owner()
        return safe(set_cfg, body())

    @app.get("/api/viral/watch")
    def viral_watch():
        owner()
        return jsonify(watch())

    @app.post("/api/viral/watch")
    def viral_watch_edit():
        owner()
        b = body()
        if b.get("remove"):
            return safe(watch_remove, b["remove"])
        if b.get("scan"):
            return safe(watch_scan)
        return safe(watch_add, b.get("handle", ""))

    @app.post("/api/viral/hooklab")
    def viral_hooklab():
        owner()
        b = body()
        return safe(hook_lab, b.get("post") or None, b.get("note", ""), int(b.get("n") or 10), bool(b.get("apply")))

    @app.get("/api/viral/lint/<pid>")
    def viral_lint(pid):
        owner()
        p = social.get(pid)
        return jsonify({"lint": lint(p)}) if p else (jsonify({"error": "not found"}), 404)

    @app.post("/api/viral/see/<pid>")
    def viral_see(pid):
        owner()
        return safe(lambda: {"vision": see(pid, force=True)})

    @app.post("/api/viral/captions/<pid>")
    def viral_captions(pid):
        owner()
        b = body()
        if b.get("remove"):
            return safe(uncaption, pid)
        return safe(captions, pid, b.get("mode") or "both", b.get("style") or "pop", b.get("pos") or "bottom",
                    bool(b.get("upper", True)), b.get("hook"))

    @app.get("/api/viral/captions/<pid>")
    def viral_captions_state(pid):
        owner()
        return jsonify(_STATE["captions"].get(pid) or {})

    @app.get("/api/viral/insights")
    def viral_insights():
        owner()
        return safe(insights)

    @app.get("/api/viral/brief")
    def viral_brief():
        owner()
        return safe(brief)

    @app.get("/api/viral/pipeline")
    def viral_pipeline():
        owner()
        return safe(pipeline)

    @app.get("/api/viral/hooks")
    def viral_hooks():
        owner()
        return jsonify({"library": hook_library(), "formulas": [{"angle": a, "template": t} for a, t in FORMULAS]})

    @app.post("/api/viral/lessons")
    def viral_lessons():
        owner()
        return safe(lambda: {"lessons": write_lessons()})

    @app.get("/api/viral/lessons")
    def viral_lessons_get():
        owner()
        return jsonify({"lessons": lessons_text()})
