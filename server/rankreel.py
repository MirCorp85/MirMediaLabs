r"""RANK REEL — one-call builder for viral "ranking" Shorts (MIR RANK SHORTS plan, Oct 26 2026).

topic + 5-7 clips (library refs or links) → Downloader grabs links → each clip auto-trimmed to its loudest window →
Kokoro VO verdict per clip (the transformation layer YouTube's reused-content rule needs) → one MIR MOTION project
with the `rankreel` scene (MirRemotion/src/rank/RankReel.tsx: 2-line keyword title, rank ladder, shuffled order with
#1 last) → saved in Motion Studio (editable) → rendered to the library → optional Social draft (YouTube Short + Reels,
approve-only as always).

POST /api/motion/rankreel {title, keywords, items:[{query|url|src, label, rank, dur?, trimIn?, verdict?, focusX?}], order, seed,
                           voice, vo, auto_verdicts, draft, session}   → {id}
GET  /api/motion/rankreel/<id>                                          → {status, stage, pct, project, src, post, error, sources}
GET  /api/motion/rankreel/sources?q=                                     → ranked candidates, 9:16 Shorts first, 16:9 last
"""
import html
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import wave

import core, remotion

W, H, FPS = 1080, 1920, 30
MIN_CLIP, MAX_CLIP, DEF_CLIP = 2.5, 12.0, 5.0
MAX_ITEMS = 8
REELS = {}                      # id -> job
DEF_VOICE = "am_michael"        # energetic US male suits sports/fails; MirAI keeps its own voice


def _f(v, d, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = d
    return max(lo, min(hi, v))


def _ffrun(args, timeout=300):
    return subprocess.run([core.FFMPEG, "-hide_banner", "-nostdin"] + args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _length(path):
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", _ffrun(["-i", path]).stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def peak_window(path, dur):
    """Start (s) of the loudest `dur`-second window — crowd roar / impact / laugh is where the moment is."""
    total = _length(path)
    if total <= dur + 0.5:
        return 0.0
    r = _ffrun(["-i", path, "-vn", "-af", "ebur128=peak=none", "-f", "null", "-"], timeout=180)
    pts = [(float(t), float(m)) for t, m in re.findall(r"t:\s*([\d.]+)\s+TARGET.*?M:\s*(-?[\d.]+)", r.stderr)]
    if len(pts) < 10:
        return 0.0
    best, best_t, j, acc = -1e9, 0.0, 0, 0.0
    for i, (t, m) in enumerate(pts):            # sliding mean of momentary loudness over [t-dur, t]
        acc += m
        while pts[j][0] < t - dur:
            acc -= pts[j][1]
            j += 1
        if t >= dur and acc / (i - j + 1) > best:
            best, best_t = acc / (i - j + 1), t - dur
    return round(max(0.0, min(total - dur, best_t - 0.4)), 2)     # lead-in so the hit isn't the first frame


def _dims(path):
    """(w, h) of a video file, rotation-aware (phone clips are often stored 16:9 + rotate=90)."""
    t = _ffrun(["-i", path]).stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", t)
    if not m:
        return 0, 0
    w, h = int(m.group(1)), int(m.group(2))
    if re.search(r"rotat\w*\s*:\s*-?(90|270)", t):
        w, h = h, w
    return w, h


_OCR = None


def burned_text(path, start=0.0, dur=6.0, n=4):
    """Share of n sampled frames carrying a creator's burned-in caption (Oct 30 2026, user: skip captioned clips).
    Caption-like = an OCR line ≥3% of frame height and ≥25% of its width — scoreboards / watermarks are too small.
    Returns 0.0 when OCR isn't installed (never blocks a reel)."""
    global _OCR
    try:
        if _OCR is None:
            from rapidocr_onnxruntime import RapidOCR
            _OCR = RapidOCR()
    except Exception:
        return 0.0
    import tempfile
    hits = 0
    with tempfile.TemporaryDirectory() as td:
        for k in range(n):
            fp = os.path.join(td, "f%d.jpg" % k)
            _ffrun(["-ss", "%.2f" % (start + dur * (k + 0.5) / n), "-i", path, "-frames:v", "1", "-vf", "scale=540:-2", "-y", fp], timeout=60)
            if not os.path.isfile(fp):
                continue
            try:
                res, _ = _OCR(fp)
            except Exception:
                continue
            w, h = _dims(fp)
            for box, _txt, conf in res or []:
                xs, ys = [pt[0] for pt in box], [pt[1] for pt in box]
                if float(conf) > 0.6 and h and (max(ys) - min(ys)) >= 0.03 * h and (max(xs) - min(xs)) >= 0.25 * w:
                    hits += 1
                    break
    return hits / float(n)


CAPTION_SKIP = 0.5    # captioned in ≥ half the sampled frames → try the next candidate


# ── source finder: 9:16 FIRST (Shorts / Reels), 16:9 only as a fallback ─────────────────────────────────────
MIN_VIEWS = 100_000        # "already went viral" bar from the plan; a lower-view vertical still beats any 16:9
MAX_SRC_SECS = 180         # Shorts are ≤3 min; longer = compilations / full highlights


def _api_search(q, n):
    """YouTube Data API search (needs the connected YouTube sign-in; 100 quota units/call). Unlike yt-dlp's search,
    this RETURNS Shorts. → [{id, title}] or None when the API is unavailable."""
    try:
        import social
        r = social._yt("GET", "/youtube/v3/search", params={"part": "snippet", "q": q, "type": "video", "videoDuration": "short",
                                                            "order": "relevance", "maxResults": n, "safeSearch": "none"})
        if not isinstance(r, dict) or r.get("error"):
            return None
        return [{"id": it["id"]["videoId"], "title": html.unescape(it["snippet"]["title"])} for it in r.get("items") or []
                if (it.get("id") or {}).get("videoId")]
    except Exception:
        return None


def _iso_secs(d):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    return sum(int(v or 0) * k for v, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def _api_details(ids):
    """id -> (views, seconds) in one videos.list call (1 quota unit)."""
    try:
        import social
        r = social._yt("GET", "/youtube/v3/videos", params={"part": "statistics,contentDetails", "id": ",".join(ids[:50])})
        return {it["id"]: (int((it.get("statistics") or {}).get("viewCount") or 0), _iso_secs((it.get("contentDetails") or {}).get("duration")))
                for it in r.get("items") or []}
    except Exception:
        return {}


def is_short(vid):
    """youtube.com/shorts/<id> serves a Short (200) but redirects a normal upload to /watch (303). One light request,
    no yt-dlp — heavy yt-dlp probing gets the PC rate-limited ("confirm you're not a bot")."""
    import urllib.request

    class _NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        r = urllib.request.build_opener(_NoRedir).open(urllib.request.Request(
            "https://www.youtube.com/shorts/" + vid, headers={"User-Agent": "Mozilla/5.0"}), timeout=10)
        return r.status == 200
    except Exception:
        return False


_STOP = {"the", "a", "an", "of", "vs", "v", "and", "in", "at", "on", "to", "for", "with", "against", "best", "top", "goal", "goals",
         "moment", "moments", "shorts", "short", "video", "clip", "highlights"}


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return set(re.findall(r"[a-z0-9]+", t))


def relevance(query, title):
    """Share of the query's key words (names, places, years) found in the title — 0..1. Stops a viral but
    unrelated Short (stat edit, story graphic) from winning just on views."""
    keys = {w for w in _norm(query) if w not in _STOP and len(w) > 1}
    return len(keys & _norm(title)) / len(keys) if keys else 1.0


REL_MIN = 0.5              # at least half the key words must be in the title to count as "found"


def find_sources(query, n=15, probe=10):
    """Ranked source candidates for one moment — 9:16 FIRST (Shorts), 16:9 only as a fallback.
    1. YouTube Data API search "<q> #shorts" (short videos, by views) — the only search that returns Shorts.
    2. Plain "<q>" API search only if step 1 found no vertical clip (saves quota).
    3. API down (YouTube sign-in expired) → yt-dlp search (no Shorts, so mostly 16:9).
    Real width/height is probed for each candidate. Order: vertical ≥MIN_VIEWS, other vertical, then landscape, by views."""
    import yt_dlp
    from concurrent.futures import ThreadPoolExecutor
    base = {"quiet": True, "no_warnings": True, "skip_download": True}

    def dims(c):
        try:
            with yt_dlp.YoutubeDL(base) as y:
                i = y.extract_info(c["url"], download=False) or {}
            c["w"], c["h"] = int(i.get("width") or 0), int(i.get("height") or 0)
            c["secs"] = i.get("duration") or 0
            c["views"] = c.get("views") or int(i.get("view_count") or 0)
        except Exception:
            c["w"] = c["h"] = 0
        c["vertical"] = bool(c["h"] and c["h"] > c["w"] * 1.05)
        return c

    def probe_all(cands):
        for c in cands:
            c["rel"] = round(relevance(query, c["title"]), 2)
        cands = sorted(cands, key=lambda c: (-c["rel"], -c["views"]))[:probe]
        with ThreadPoolExecutor(4) as ex:
            got = [c for c in ex.map(dims, cands) if c["w"] and (c["secs"] or 0) <= MAX_SRC_SECS]

        def tier(c):           # relevant vertical (viral first) > relevant 16:9 > anything else
            ok = c["rel"] >= REL_MIN
            return 0 if ok and c["vertical"] and c["views"] >= MIN_VIEWS else 1 if ok and c["vertical"] else 2 if ok else 3
        got.sort(key=lambda c: (tier(c), -c["rel"], -c["views"]))
        return got

    def short_check(c):        # API path: Short-ness via the /shorts/ URL; real aspect is measured after download
        c["vertical"] = is_short(c["id"])
        c["w"], c["h"] = (1080, 1920) if c["vertical"] else (1920, 1080)
        return c

    seen, out = set(), []
    for q in ("%s #shorts" % query, query):
        hits = _api_search(q, n)
        if hits is None:
            break
        hits = [h for h in hits if h["id"] not in seen]
        seen.update(h["id"] for h in hits)
        det = _api_details([h["id"] for h in hits])
        new = [{"id": h["id"], "url": "https://www.youtube.com/watch?v=" + h["id"], "title": h["title"],
                "views": det.get(h["id"], (0, 0))[0], "secs": det.get(h["id"], (0, 0))[1], "via": "api",
                "rel": round(relevance(query, h["title"]), 2)} for h in hits]
        new = [c for c in new if 0 < c["secs"] <= MAX_SRC_SECS]
        new = sorted(new, key=lambda c: (-c["rel"], -c["views"]))[:probe]
        with ThreadPoolExecutor(6) as ex:
            out += list(ex.map(short_check, new))
        out.sort(key=lambda c: (0 if c["rel"] >= REL_MIN and c["vertical"] and c["views"] >= MIN_VIEWS else
                                1 if c["rel"] >= REL_MIN and c["vertical"] else 2 if c["rel"] >= REL_MIN else 3, -c["rel"], -c["views"]))
        if out and out[0]["vertical"] and out[0]["rel"] >= REL_MIN:
            return out
    if out:
        return out
    cands = []                                         # fallback: yt-dlp search (never sees Shorts)
    for q in ("%s shorts" % query, query):
        try:
            with yt_dlp.YoutubeDL(dict(base, extract_flat=True)) as y:
                r = y.extract_info("ytsearch%d:%s" % (n, q), download=False) or {}
        except Exception:
            continue
        for e in r.get("entries") or []:
            vid = (e or {}).get("id")
            if vid and vid not in seen and (e.get("duration") or 0) <= MAX_SRC_SECS:
                seen.add(vid)
                cands.append({"id": vid, "url": "https://www.youtube.com/watch?v=" + vid, "title": e.get("title") or "",
                              "views": int(e.get("view_count") or 0), "via": "yt-dlp"})
    return probe_all(cands)


def _wav_secs(p):
    try:
        with wave.open(p) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def _grab(url, uid, sid):
    import grab
    if not grab.available():
        raise RuntimeError("the Downloader (yt-dlp) isn't installed")
    job = {"id": "rr" + uuid.uuid4().hex[:8], "user": uid, "url": grab._clean_url(url), "mode": "video", "status": "queued",
           "stage": "", "session": sid, "pct": 0, "files": [], "created": time.time(), "start": None, "end": 120.0,
           "quality": "1080", "abr": "192", "stills": 0, "title": None, "thumb": None}
    grab._run(job)
    if job["status"] != "done" or not job["files"]:
        raise RuntimeError("download failed for %s: %s" % (url[:80], job.get("error") or job["status"]))
    return job["files"][0]


def _to_lib(src_path, uid, sid, prompt):
    name = core.new_name("rankvo", ".wav")
    shutil.copy2(src_path, os.path.join(core.LIB, name))
    meta = {"user": uid, "model": "kokoro", "mode": "rankreel-vo", "prompt": prompt[:300], "created": time.time()}
    if sid:
        meta["session"] = sid
    core.index_add(name, meta)
    return name


def write_verdicts(title, items, ask):
    """Fill empty verdicts: one punchy line per clip, rank-aware (#1 gets the payoff line)."""
    need = [it for it in items if not it.get("verdict")]
    if not need or not ask:
        return
    brief = [{"rank": it["rank"], "label": it.get("label") or ""} for it in items]
    sys_ = ("You write voice-over for a viral YouTube Shorts ranking video. One line per clip, max 9 words, spoken, "
            "funny or hype. Only rank 1's line may start with 'Number one' (clips play shuffled, so never say other numbers). No emoji, no hashtags. "
            'Reply JSON: {"lines": [{"rank": 1, "verdict": "..."}]}')
    try:
        r = ask("Video: %s\nClips: %s" % (title.replace("\n", " "), json.dumps(brief)), sys_)
        if isinstance(r, str):
            r = json.loads(re.search(r"\{.*\}", r, re.S).group(0))
        got = {int(x.get("rank")): str(x.get("verdict") or "").strip() for x in (r or {}).get("lines") or []}
        for it in need:
            it["verdict"] = got.get(it["rank"], "")[:90]
    except Exception as e:
        import console
        console.emit("MOTION", "rank reel: verdict writer failed (%s) - clips keep empty lines" % str(e)[:120], level="warn")


def build_project(title, keywords, items, order="shuffle", seed=7, name=None, session="", extra=None):
    """items already resolved (src lib:, trimIn, dur, vo, voDur) → a 1080x1920 Motion project with one rankreel clip."""
    total = sum(it["dur"] for it in items) + _f((extra or {}).get("intro"), 0, 0, 3)
    props = dict({"title": title, "keywords": keywords, "items": items, "order": order, "seed": int(seed)}, **(extra or {}))
    clip = remotion.scene("rankreel", total, props)
    p = remotion.project(name or ("Rank Reel — " + title.replace("\n", " "))[:120], W, H, FPS,
                         tracks=[{"kind": "scene", "name": "Rank Reel", "clips": [clip]}], session=session)
    p["bg"] = "#000000"
    return p


def run(job, req, uid, sid, my_file, ask, is_owner):
    try:
        title = str(req.get("title") or "").strip()[:120]
        if not title:
            raise ValueError("a title is required")
        if "\n" not in title and len(title) > 14:      # always two lines — split at the word nearest the middle
            ws = title.split()
            cut = min(range(1, len(ws)), key=lambda i: abs(len(" ".join(ws[:i])) - len(title) / 2)) if len(ws) > 1 else 0
            title = " ".join(ws[:cut]) + "\n" + " ".join(ws[cut:]) if cut else title
        raw = [x for x in (req.get("items") or []) if isinstance(x, dict)][:MAX_ITEMS]
        if len(raw) < 3:
            raise ValueError("a ranking needs at least 3 clips (5-7 is the sweet spot)")
        items = []
        for i, x in enumerate(raw):
            job.update(stage="clip %d/%d" % (i + 1, len(raw)), pct=round(40.0 * i / len(raw), 1))
            ref = str(x.get("src") or "")
            grabbed = False
            source = str(x.get("url") or "")
            if not ref and not source and x.get("query"):          # find it: Shorts/Reels first, 16:9 fallback
                job["stage"] = "clip %d/%d · finding a vertical source" % (i + 1, len(raw))
                found = find_sources(str(x["query"])[:150])
                if not found:
                    raise ValueError("nothing found for clip %d (%s)" % (i + 1, x["query"]))
                err, fallback = None, None
                for c in found[:4]:                              # private / age-gated / sign-in pick → next best
                    try:
                        nm_c = _grab(c["url"], uid, sid)
                    except RuntimeError as e:
                        err = e
                        continue
                    pth = core.in_dir(core.LIB, nm_c)
                    d_c = _f(x.get("dur"), DEF_CLIP, MIN_CLIP, MAX_CLIP)
                    job["stage"] = "clip %d/%d · checking for burned-in captions" % (i + 1, len(raw))
                    txt = burned_text(pth, peak_window(pth, d_c), d_c) if pth else 0.0
                    rec = {"query": x["query"], "url": c["url"], "title": c["title"], "views": c["views"],
                           "vertical": c["vertical"], "rel": c.get("rel"), "captioned": txt}
                    if txt < CAPTION_SKIP:
                        ref, grabbed, source = "lib:" + nm_c, True, c["url"]
                        job.setdefault("sources", []).append(rec)
                        break
                    if fallback is None:                         # every pick captioned → keep the best-ranked one
                        fallback = (nm_c, c["url"], rec)
                if not ref and fallback:
                    ref, grabbed, source = "lib:" + fallback[0], True, fallback[1]
                    job.setdefault("sources", []).append(fallback[2])
                if not ref:
                    raise ValueError("no downloadable source for clip %d (%s): %s" % (i + 1, x["query"], err))
            if not ref and source:
                ref, grabbed = "lib:" + _grab(source, uid, sid), True
            nm = ref.split(":", 1)[-1]
            path = core.in_dir(core.LIB, nm)
            if not ref or not path or not os.path.isfile(path) or not (grabbed or my_file(nm)):
                raise ValueError("clip %d isn't in your library" % (i + 1))
            dur = _f(x.get("dur"), DEF_CLIP, MIN_CLIP, MAX_CLIP)
            ln = _length(path)
            if ln:
                dur = min(dur, max(MIN_CLIP, ln))
            trim = _f(x["trimIn"], 0, 0, 3600) if x.get("trimIn") not in (None, "") else peak_window(path, dur)
            w, h = _dims(path)
            it = {"src": "lib:" + nm, "label": str(x.get("label") or "")[:40], "rank": int(_f(x.get("rank"), i + 1, 1, 99)),
                  "trimIn": trim, "dur": round(dur, 2), "verdict": str(x.get("verdict") or "")[:120],
                  "play": int(_f(x.get("play"), i, 0, 99)), "aspect": round(w / h, 4) if w and h else 0.5625}
            for k in ("focusX", "focusY"):
                if x.get(k) not in (None, ""):
                    it[k] = _f(x[k], 50, 0, 100)
            if source:
                it["source"] = source                               # kept for the description credits
            items.append(it)
        if req.get("auto_verdicts", True):
            job["stage"] = "writing verdicts"
            write_verdicts(title, items, ask)
        if req.get("vo", True):
            import tts
            voice = req.get("voice") if req.get("voice") in tts.VOICES else DEF_VOICE
            for i, it in enumerate(items):
                if not it["verdict"]:
                    continue
                job.update(stage="voice %d/%d" % (i + 1, len(items)), pct=round(40 + 15.0 * i / len(items), 1))
                wav = tts.say(it["verdict"], voice, 1.1)
                it["vo"] = "lib:" + _to_lib(wav, uid, sid, it["verdict"])
                it["voDur"] = round(_wav_secs(wav), 2)
                it["dur"] = round(min(MAX_CLIP, max(it["dur"], it["voDur"] + 0.8)), 2)
        extra = {k: req[k] for k in ("kwColor", "intro", "hook", "sting", "clipVolume", "duckVolume", "voVolume", "captions", "fit") if k in req}
        p = build_project(title, str(req.get("keywords") or ""), items, req.get("order") or "shuffle",
                          _f(req.get("seed"), int(time.time()) % 9973 + 1, 1, 9999), session=sid, extra=extra)
        job["project"] = remotion.save_project(uid, p)
        p["id"] = job["project"]
        if not req.get("render", True):
            job.update(status="done", stage="project saved", pct=100.0)
            return

        def after(mj):
            job.update(src=mj["src"], url=mj["url"])
            if req.get("draft") and is_owner:
                import social
                post = social.create_draft(mj["src"], req.get("platforms") or ["youtube", "instagram"],
                                           brief="Ranking Short: %s. Clips credited to original creators in the description."
                                                 % title.replace("\n", " "), fit="crop", yt_format="short", captions="none")
                job["post"] = post["id"]
        job["stage"] = "rendering"
        mj = remotion.start_job(remotion.clean(p), uid, sid, "mp4", 20, "rankreel", prefix="rankreel", after=after)
        job["motion_job"] = mj["id"]
        while mj.get("status") == "running":
            job["pct"] = round(55 + 0.45 * (mj.get("pct") or 0), 1)
            job["stage"] = "rendering · " + str(mj.get("stage") or "")
            time.sleep(1)
        if mj.get("status") != "done":
            raise RuntimeError(mj.get("error") or "render %s" % mj.get("status"))
        job.update(status="done", stage="in your library" + (" + Social draft" if job.get("post") else ""), pct=100.0)
    except Exception as e:
        job.update(status="error", error=str(e)[:500])
    finally:
        job["finished"] = time.time()


def register(app, hk):
    """hk: uid, my_file(name), session(sid), ask(prompt, system), is_owner()."""
    from flask import jsonify, request

    @app.route("/api/motion/rankreel", methods=["POST"])
    def rr_start():
        req = request.get_json(silent=True) or {}
        uid = hk["uid"]()
        if sum(1 for j in REELS.values() if j["user"] == uid and j["status"] == "running") >= 2:
            return jsonify({"error": "two rank reels are already building"}), 409
        sid = hk["session"](req.get("session")) or ""
        # ownership needs the request context → resolve it here; the worker thread only checks set membership
        mine = {str(x.get("src")).split(":", 1)[-1] for x in req.get("items") or [] if isinstance(x, dict) and x.get("src")}
        mine = {n for n in mine if hk["my_file"](n)}
        rid = "rr" + uuid.uuid4().hex[:10]
        REELS[rid] = {"id": rid, "user": uid, "status": "running", "stage": "starting", "pct": 0.0, "started": time.time()}
        threading.Thread(target=run, args=(REELS[rid], req, uid, sid, mine.__contains__, hk.get("ask"), hk["is_owner"]()),
                         daemon=True, name="rankreel").start()
        return jsonify(REELS[rid])

    @app.route("/api/motion/rankreel/sources")
    def rr_sources():
        q = (request.args.get("q") or "").strip()[:150]
        if not q:
            return jsonify({"error": "q required"}), 400
        try:
            return jsonify({"query": q, "sources": find_sources(q)})
        except Exception as e:
            return jsonify({"error": str(e)[:300]}), 500

    @app.route("/api/motion/rankreel/<rid>")
    def rr_get(rid):
        j = REELS.get(rid)
        if not j or j["user"] != hk["uid"]():
            return jsonify({"error": "no such reel"}), 404
        return jsonify(j)
