r"""RANK REEL PRODUCER — the step-by-step wizard behind /mlab/rankreel (static/rankreel.html), modelled on the EXPLAINED
producer: a project per reel, a pipeline with checkpoints where the person approves, every step redoable.

  moments  topic → the brain writes N ranked moments (label + a specific search query) + the 2-line title   [checkpoint]
  clips    per moment: find_sources() (9:16 Shorts FIRST, 16:9 fallback) → download → auto-trim            [checkpoint]
           the person can swap a candidate, paste a link, re-search, or change trim / length
  script   empty verdict lines written by the brain; title, highlight words, voice are editable               [checkpoint]
  render   Kokoro VO per clip → MIR MOTION `rankreel` project (saved in Motion Studio) → library render      [checkpoint]
           a copy lands in the optional export folder (rankreel_export_dir in Settings / mml_config.json)
  publish  optional Social draft (YouTube Short + Reels) — approve-only in Social as always

Projects: data/rankreel/<uid>/<id>.json. Heavy lifting reuses rankreel.py (find_sources, _grab, peak_window, _dims,
build_project). Auto mode skips the checkpoints up to the final cut.
"""
import json
import os
import re
import shutil
import threading
import time
import uuid

import core, rankreel, remotion

D = os.path.join(core.DATA, "rankreel")
import engines
OUT_DIR = engines.path("rankreel_export_dir", "MML_RANKREEL_EXPORT", "")   # optional extra copy of every reel
STAGES = ["moments", "clips", "script", "render", "publish", "done"]
AUTO_SPARES = 3              # automatic mode plans this many extra moments as stand-ins for clips that fail
_LOCKS = {}
_ID = re.compile(r"^[a-z0-9]{8,16}$")


def _dir(uid):
    d = os.path.join(D, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid)))
    os.makedirs(d, exist_ok=True)
    return d


def _lock(pid):
    return _LOCKS.setdefault(pid, threading.Lock())


def load(uid, pid):
    if not _ID.match(str(pid)):
        return None
    try:
        with open(os.path.join(_dir(uid), pid + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(p):
    p["updated"] = time.time()
    path = os.path.join(_dir(p["user"]), p["id"] + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)
    for i in range(40):          # Windows: replace fails while the page's poll has the file open — retry, never kill the worker
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 + 0.01 * i)
    os.replace(tmp, path)


def log(p, msg, lvl="info"):
    p.setdefault("log", []).append({"t": time.time(), "msg": str(msg)[:300], "lvl": lvl})
    p["log"] = p["log"][-120:]


def listing(uid):
    out = []
    for f in os.listdir(_dir(uid)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(_dir(uid), f), encoding="utf-8") as fh:
                    p = json.load(fh)
                ready = [m for m in p.get("moments") or [] if m.get("src")]
                out.append({"id": p["id"], "title": p.get("title") or p.get("topic"), "state": p.get("state"), "stage": p.get("stage"),
                            "created": p.get("created"), "updated": p.get("updated"), "thumb": (ready[0].get("thumb") if ready else ""),
                            "src": (p.get("render") or {}).get("src", "")})
            except Exception:
                pass
    return sorted(out, key=lambda r: -(r.get("updated") or 0))


# ── brain ──────────────────────────────────────────────────────────────────────────────────────────────────
def _ask_json(prompt, system, ask):
    """the cloud brain (VIRAL's) first, the local engine as fallback → dict."""
    txt = None
    try:
        import viral
        txt = viral.brain_ask(prompt, system, timeout=240)
    except Exception:
        txt = None
    if txt is None and ask:
        r = ask(prompt, system)
        if isinstance(r, dict):
            return r
        txt = r
    m = re.search(r"\{.*\}", str(txt or ""), re.S)
    if not m:
        raise RuntimeError("the writer returned nothing usable")
    return json.loads(m.group(0))


def write_moments(p, ask):
    sys_ = ("You plan viral YouTube Shorts ranking videos (5-7 real moments ranked, #1 saved for last). Pick REAL, famous, "
            "well-documented moments that exist as short clips on YouTube. For each: label = 1-3 words shown on screen; "
            "query = a specific YouTube search (names + place + year, no hashtags); why = 6-10 words. Rank 1 = the best. "
            "Also: title = 'Ranking the …' in two short lines split by \\n (the 2nd line carries the keywords); keywords = the "
            "words to colour (comma separated). Reply JSON: {\"title\": \"...\", \"keywords\": \"...\", \"moments\": "
            "[{\"rank\": 1, \"label\": \"...\", \"query\": \"...\", \"why\": \"...\"}]}")
    n = p["count"] + (AUTO_SPARES if p.get("auto") else 0)     # automatic runs plan spares that stand in for clips that fail
    j = _ask_json("Topic: %s\nHow many: %d" % (p["topic"], n), sys_, ask)
    ms = [m for m in j.get("moments") or [] if isinstance(m, dict) and m.get("query")][:n]
    if len(ms) < 3:
        raise RuntimeError("the writer found fewer than 3 moments — try a broader topic")
    p["title"] = p.get("title") or str(j.get("title") or "Ranking the best\n" + p["topic"])[:120]
    p["keywords"] = p.get("keywords") or str(j.get("keywords") or "")[:80]
    p["moments"] = [_moment(i + 1, m) for i, m in enumerate(sorted(ms, key=lambda m: int(m.get("rank") or 99)))]


REFILL_ROUNDS = 3             # automatic mode: up to 3 rounds of fresh replacement moments when clips fail (user, Nov 4 2026:
                              # "I asked for 6 clips and it used 3 — fix that forever")


def write_refill(p, need, ask):
    """Ask for `need` NEW moments on the same topic that aren't any already tried, with different searches.
    Returns a list of moment dicts ranked after every existing one (so the original #1 keeps its spot)."""
    tried = ["%s (search: %s)" % (m["label"], m["query"]) for m in p.get("_tried", []) + p["moments"]]
    sys_ = ("You plan viral YouTube Shorts ranking videos. Some planned moments had no usable real footage on YouTube. "
            "Suggest REPLACEMENT moments: REAL, famous, well-documented, and very likely to exist as real video clips "
            "(news footage, broadcast, phone video) on YouTube. Never repeat a moment already tried. For each: label = 1-3 words; "
            "query = a specific YouTube search (names + place + year, no hashtags) worded differently from earlier ones; "
            "why = 6-10 words. Reply JSON: {\"moments\": [{\"label\": \"...\", \"query\": \"...\", \"why\": \"...\"}]}")
    j = _ask_json("Topic: %s\nHow many: %d\nAlready tried (do NOT repeat):\n- %s" % (p["topic"], need + 1, "\n- ".join(tried)),
                  sys_, ask)
    seen = {m["label"].lower() for m in p.get("_tried", []) + p["moments"]}
    base = max([m["rank"] for m in p["moments"]] + [0])
    out = []
    for m in j.get("moments") or []:
        if isinstance(m, dict) and m.get("query") and str(m.get("label") or "").lower() not in seen:
            out.append(_moment(base + len(out) + 1, m))
            seen.add(out[-1]["label"].lower())
    return out[:need + 1]


def _moment(rank, m):
    return {"rank": rank, "label": str(m.get("label") or "")[:40], "query": str(m.get("query") or "")[:150],
            "why": str(m.get("why") or "")[:120], "verdict": str(m.get("verdict") or "")[:120], "status": "todo",
            "cands": [], "pick": "", "src": "", "trimIn": None, "dur": 6.0}


# ── clips ──────────────────────────────────────────────────────────────────────────────────────────────────
def find_clip(p, m):
    m.update(status="finding", err="")
    found = rankreel.find_sources(m["query"])
    m["cands"] = [{"url": c["url"], "id": c["id"], "title": c["title"][:90], "views": c["views"], "vertical": c["vertical"],
                   "rel": c.get("rel", 0), "secs": c.get("secs", 0),
                   "thumb": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % c["id"]} for c in found[:6]]
    if not m["cands"]:
        m.update(status="error", err="nothing found — edit the search and try again")


def fetch_clip(p, m, url=None, sid=""):
    """Download the pick (or the next candidates when a pick is private / sign-in only), then auto-trim."""
    urls = [url] if url else [c["url"] for c in m["cands"][:4]]
    m.update(status="downloading", err="")
    err = None
    for u in urls:
        try:
            name = rankreel._grab(u, p["user"], sid)
            path = core.in_dir(core.LIB, name)
            ln = rankreel._length(path)
            dur = min(max(rankreel.MIN_CLIP, float(m.get("dur") or 6)), max(rankreel.MIN_CLIP, ln or 6))
            w, h = rankreel._dims(path)
            vid = re.search(r"(?:v=|/shorts/|youtu\.be/)([\w-]{11})", u)
            m.update(pick=u, src=name, length=round(ln, 2), dur=round(dur, 2), aspect=round(w / h, 4) if w and h else 0.5625,
                     trimIn=rankreel.peak_window(path, dur), status="ready",
                     # YouTube → its own thumbnail; TikTok / Reels / anything else → a still from our copy (/thumb/<file>)
                     thumb=("https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid.group(1)) if vid else "thumb/" + name)
            return
        except Exception as e:
            err = e
    m.update(status="error", err=str(err)[:200] if err else "download failed")


# ── eyes: does the clip really show the moment? (automatic mode's stand-in for the person checking the Clips step) ──
QC_FRAMES = 6


def qc_clip(p, m):
    """One contact sheet (6 frames spread over the WHOLE clip, row-major) → the vision brain looks at it → (ok, best_t, why).
    ok=False for talking heads / podcasts / reaction cams / fan-edit graphics / text cards / game recreations.
    best_t = where the key action happens, so the trim lands on the play instead of on the loudest talking."""
    path = core.in_dir(core.LIB, m["src"])
    ln = float(m.get("length") or rankreel._length(path) or 0)
    if ln <= 0:
        return True, None, "no length"
    ts = [round(ln * (i + 0.5) / QC_FRAMES, 2) for i in range(QC_FRAMES)]
    d = os.path.join(D, "qc", p["id"])
    os.makedirs(d, exist_ok=True)
    sheet = os.path.join(d, "r%d_%s.jpg" % (m["rank"], uuid.uuid4().hex[:6]))
    sel = "+".join("lt(prev_pts*TB\\,%s)*gte(pts*TB\\,%s)" % (t, t) for t in ts)
    r = rankreel._ffrun(["-y", "-i", path, "-vf", "select='%s',scale=-2:360,tile=%dx1" % (sel, QC_FRAMES), "-frames:v", "1", "-q:v", "4", sheet], timeout=120)
    if not os.path.isfile(sheet):
        return True, None, "no frames (%s)" % r.stderr[-120:]
    import remix
    sys_ = ("You check clips for a viral sports/moments ranking Short. Be strict but fair. Reply ONE JSON object only: "
            '{"ok": true|false, "frame": <1-%d where the key action is clearest, or 0>, "why": "<8 words>"}' % QC_FRAMES)
    task = ("Moment: %s — %s\nSearch used: %s\nThe image is a contact sheet of %d frames from the clip, left to right in time order "
            "(at %s seconds). ok=true only if the clip shows REAL footage of THIS moment (the actual play/event). ok=false if it is mostly "
            "a talking head, podcast, reaction cam, slideshow, fan-edit graphic/text card, video-game recreation, or a different event."
            % (m["label"], m.get("why") or "", m["query"], QC_FRAMES, ", ".join(map(str, ts))))
    try:
        txt = remix.brain_see(task, [sheet], sys_, timeout=180) or ""
        j = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    except Exception as e:
        return True, None, "check unavailable (%s)" % str(e)[:60]          # never block a run because the checker is down
    fr = int(j.get("frame") or 0)
    return bool(j.get("ok")), (ts[fr - 1] if 1 <= fr <= QC_FRAMES else None), str(j.get("why") or "")[:80]


FINE_FRAMES = 12            # second look: 12 frames (6 per row, 2 rows) around the action the first look found
PRE, POST = 4.5, 1.8        # window = 4.5 s of build-up before the money shot + 1.8 s of payoff/reaction after it
MIN_WIN = 5.0


def _fine_sheet(p, m, path, a, span):
    ts = [round(a + span * i / (FINE_FRAMES - 1), 2) for i in range(FINE_FRAMES)]
    sheet = os.path.join(D, "qc", p["id"], "r%d_fine_%s.jpg" % (m["rank"], uuid.uuid4().hex[:6]))
    sel = "+".join("lt(prev_pts*TB\\,%s)*gte(pts*TB\\,%s)" % (t, t) for t in ts)
    rankreel._ffrun(["-y", "-i", path, "-vf", "select='%s',scale=-2:260,tile=6x2" % sel, "-frames:v", "1", "-q:v", "4", sheet], timeout=120)
    return ts, (sheet if os.path.isfile(sheet) else None)


def refine_window(p, m, center):
    """Zoomed second look (12 frames ~1.3 s apart around the first look's pick) → {"sig": t, "shot": t}:
    sig  = the SIGNATURE — where the thing the label promises is clearest (between the legs, over the car, from the free-throw
           line); its FIRST clear occurrence, which is often the full-speed angle.
    shot = the MONEY SHOT — the instant the play completes (ball through the rim, goal in, the landing); the clearer of
           full speed / slow-mo.
    History: fixed 6 s windows cut take-offs; start/end marking let replays balloon the window; a money-shot-only window kept
    LaVine's slow-mo slam but lost the between-the-legs, which only reads clearly in the full-speed wide shot before it."""
    import remix
    path = core.in_dir(core.LIB, m["src"])
    ln = float(m.get("length") or 0)
    span = min(ln, max(14.0, 1.5 * ln / QC_FRAMES))
    a = max(0.0, min(ln - span, center - span / 2))
    ts, sheet = _fine_sheet(p, m, path, a, span)
    if not sheet:
        return None
    sys_ = ('You mark two instants of a moment in a clip. Reply ONE JSON object only: {"signature": <0-%d>, "finish": <0-%d>}'
            % (FINE_FRAMES, FINE_FRAMES))
    task = ("Moment: %s — %s\nThe image is a contact sheet of %d frames, 6 per row, TWO rows, read left→right then the second row "
            "(frame 1 = top-left, frame %d = bottom-right), at %s seconds.\n"
            "signature = the frame where the SPECIAL thing this moment is named for is most clearly visible (e.g. the ball passing "
            "between the legs, jumping over the car/person, taking off from the free-throw line, the elbow in the rim). If it "
            "appears more than once, give its FIRST clear occurrence.\n"
            "finish = the MONEY SHOT — the instant the moment completes (ball through the hoop, the goal going in, the landing); "
            "if it appears twice (full speed + slow-mo replay), the clearer one.\nAnswer 0 for either if it is not in any frame."
            % (m["label"], m.get("why") or "", FINE_FRAMES, FINE_FRAMES, ", ".join(map(str, ts))))
    try:
        txt = remix.brain_see(task, [sheet], sys_, timeout=180) or ""
        j = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        sg, fn = int(j.get("signature") or 0), int(j.get("finish") or 0)
    except Exception:
        return None
    out = {"sig": ts[sg - 1] if 1 <= sg <= FINE_FRAMES else None, "shot": ts[fn - 1] if 1 <= fn <= FINE_FRAMES else None}
    return out if (out["sig"] is not None or out["shot"] is not None) else None


SIG_LEAD = 1.5              # seconds kept before the signature frame (the move starts just before it reads clearly)


def fit_window(m, shot, sig=None):
    """Clip = from just before the SIGNATURE (or PRE s before the money shot) → POST s after the money shot, ≥5 s, ≤12 s.
    Too long → the signature wins the start and the clip runs as far toward the finish as 12 s allows."""
    ln = float(m.get("length") or 0) or (shot or sig) + POST
    if shot is None:
        shot = sig
    a = shot - PRE
    if sig is not None and sig <= shot:
        a = min(a, sig - SIG_LEAD)
    a = max(0.0, a)
    end = min(ln, shot + POST)
    if end - a > rankreel.MAX_CLIP:
        end = a + rankreel.MAX_CLIP
    if end - a < MIN_WIN:                     # near the source's start/end: grow the other way to ≥5 s
        end = min(ln, a + MIN_WIN)
        a = max(0.0, end - MIN_WIN)
    m["trimIn"], m["dur"] = round(a, 2), round(max(rankreel.MIN_CLIP, end - a), 2)


def fetch_checked(p, m, sid=""):
    """Automatic mode: download candidates in turn until one passes the visual check; trim around the action the brain saw."""
    tried = 0
    for c in m["cands"][:4]:
        if c.get("rel", 0) < rankreel.REL_MIN and tried:
            break
        fetch_clip(p, m, c["url"], sid)
        if m["status"] != "ready":
            continue
        tried += 1
        ok, best_t, why = qc_clip(p, m)
        log(p, "#%d %s — check: %s%s" % (m["rank"], m["label"], "pass" if ok else "reject", (" · " + why) if why else ""),
            "done" if ok else "warn")
        if ok:
            if best_t is not None:
                mk = refine_window(p, m, best_t)         # second, zoomed look: signature move + money shot
                if mk:
                    fit_window(m, mk["shot"], mk["sig"])
                else:
                    fit_window(m, best_t)
            m["qc"] = why
            return
        if tried >= 3:
            break
    m.update(status="error", err="no candidate passed the visual check — a spare takes its place")


# ── per-clip jobs (swap a shot / re-search) ─────────────────────────────────────────────────────────────────
# A swap used to run as a whole-project step: the reel went "running" for the 30-40 s download, every row's tools were
# disabled and further clicks got 409 — the page looked frozen. Now only that clip is busy; the download runs OUTSIDE the
# project lock on a copy of the moment, and the result is merged into a freshly re-read project (cut edits made to other
# clips meanwhile survive). A failed swap keeps the old shot and says why.
_CLIP_FIELDS = ("cands", "pick", "src", "length", "dur", "aspect", "trimIn", "status", "thumb", "err", "query")


def _clip_job(uid, pid, rank, action, url, sid=""):
    with _lock(pid):
        p = load(uid, pid)
        m = next((x for x in p["moments"] if x["rank"] == rank), None)
        if not m:
            return
        key = (m["label"], m["query"])
        old = {k: m.get(k) for k in ("pick", "src", "status", "trimIn", "dur", "length", "aspect", "thumb")}
        m.update(status="finding" if action == "requery" else "downloading", err="", want=url or "")
        save(p)
        work = json.loads(json.dumps(m))

    def go():
        shell = {"id": pid, "user": uid}
        try:
            if action == "requery":
                find_clip(shell, work)
            if action == "pick" or work.get("cands"):
                fetch_clip(shell, work, url or None, sid)
        except Exception as e:
            work.update(status="error", err=str(e)[:200])
        if work.get("status") != "ready" and old.get("src"):       # keep the shot that was there, explain the failure
            msg = work.get("err") or "couldn't get that shot"
            work.update(old, err="Couldn't use that shot — kept the previous one (%s)" % msg[:140])
        work.pop("want", None)
        with _lock(pid):
            p = load(uid, pid)
            if not p:
                return
            tgt = next((x for x in p["moments"] if (x["label"], x["query"]) == key), None) or \
                next((x for x in p["moments"] if x["rank"] == rank), None)
            if tgt:
                for k in _CLIP_FIELDS:
                    if k in work:
                        tgt[k] = work[k]
                tgt.pop("want", None)
                log(p, "#%d %s — %s" % (tgt["rank"], tgt["label"], "new shot ready" if not tgt.get("err") else tgt["err"]),
                    "done" if not tgt.get("err") else "warn")
            save(p)
    threading.Thread(target=go, daemon=True, name="rankreel-clip-%s-%d" % (pid, rank)).start()


# ── workers ────────────────────────────────────────────────────────────────────────────────────────────────
def _run(uid, pid, fn):
    def go():
        with _lock(pid):
            p = load(uid, pid)
            if not p:
                return
            try:
                p["state"] = "running"
                save(p)
                fn(p)
            except Exception as e:
                p.update(state="error", error=str(e)[:400])
                log(p, "stopped: %s" % e, "error")
            try:
                save(p)
            except Exception:
                time.sleep(1)
                save(p)
    threading.Thread(target=go, daemon=True, name="rankreel-" + pid).start()


def step_moments(p, ask):
    log(p, "writing the ranked moments for “%s”" % p["topic"])
    write_moments(p, ask)
    log(p, "%d moments ready" % len(p["moments"]), "done")
    _wait_or_go(p, "moments", ask)


def step_clips(p, ask, only=None, sid=""):
    p["stage"] = "clips"
    auto = p.get("auto") and only is None
    ready_n = lambda: sum(x["status"] == "ready" for x in p["moments"])

    def run(ms, tag=""):
        for i, m in enumerate(ms):
            if auto and ready_n() >= p["count"]:
                break                                   # enough good clips — the remaining spares aren't needed
            p["stage_note"] = "%sclip %d/%d · %s" % (tag, i + 1, len(ms), m["label"])
            save(p)
            if not m["cands"] or only is not None:
                find_clip(p, m)
                save(p)
            if auto and m["cands"]:
                # Low title-relevance used to reject the moment outright (that's how "Trump Butler" got dropped without a
                # look). The visual check is the real judge, so low-relevance results are still looked at (fetch_checked
                # stops after the first low-relevance candidate fails).
                fetch_checked(p, m, sid)                # the vision brain looks at each clip before it's used
            elif m["cands"]:
                fetch_clip(p, m, None, sid)
            log(p, "#%d %s — %s" % (m["rank"], m["label"], "ready" if m["status"] == "ready" else m.get("err")),
                "done" if m["status"] == "ready" else "warn")
            save(p)

    run([m for m in p["moments"] if only is None or m["rank"] in only])
    rounds = 0
    while auto and ready_n() < p["count"] and rounds < REFILL_ROUNDS:   # never settle for fewer clips than asked
        rounds += 1
        need = p["count"] - ready_n()
        log(p, "only %d of %d clips usable — finding %d replacement moments (round %d/%d)"
            % (ready_n(), p["count"], need, rounds, REFILL_ROUNDS), "warn")
        p.setdefault("_tried", []).extend({"label": m["label"], "query": m["query"]}
                                          for m in p["moments"] if m["status"] != "ready")
        p["moments"] = [m for m in p["moments"] if m["status"] == "ready" or m["status"] == "todo"]
        try:
            new = write_refill(p, need, ask)
        except Exception as e:
            log(p, "couldn't plan replacements: %s" % str(e)[:120], "warn")
            break
        if not new:
            break
        p["moments"] += new
        save(p)
        run(new, "refill %d · " % rounds)
    if auto and ready_n() < p["count"]:
        log(p, "only %d of %d clips could be found after %d refill rounds" % (ready_n(), p["count"], rounds), "warn")
    if auto:                                            # keep the best `count` ready clips, in rank order, renumbered
        keep = sorted([m for m in p["moments"] if m["status"] == "ready"], key=lambda m: m["rank"])[:p["count"]]
        dropped = len(p["moments"]) - len(keep)
        for i, m in enumerate(keep):
            m["rank"] = i + 1
        p["moments"] = keep
        if dropped:
            log(p, "kept the %d best clips (%d spare or failed moments left out)" % (len(keep), dropped))
        if len(keep) < 3:
            raise RuntimeError("only %d usable clips found — try a broader topic" % len(keep))
    p["stage_note"] = ""
    _wait_or_go(p, "clips", ask)


def step_script(p, ask):
    p["stage"] = "script"
    ready = [m for m in p["moments"] if m["status"] == "ready"]
    items = [{"rank": m["rank"], "label": m["label"], "verdict": m.get("verdict") or ""} for m in ready]
    log(p, "writing the voice-over lines")
    rankreel.write_verdicts(p["title"], items, lambda pr, sy: _ask_json(pr, sy, ask))
    by = {it["rank"]: it["verdict"] for it in items}
    for m in ready:
        m["verdict"] = m.get("verdict") or by.get(m["rank"], "")
    log(p, "script ready", "done")
    _wait_or_go(p, "script", ask)


VO_TIMEOUT = 90


def _say(text, voice):
    """tts.say with a time limit — it shares one Kokoro worker + lock with MirAI, and a stuck call used to hang the reel forever."""
    import tts
    box = {}

    def go():
        try:
            box["wav"] = tts.say(text, voice, 1.1)
        except Exception as e:
            box["err"] = e
    t = threading.Thread(target=go, daemon=True, name="rankreel-vo")
    t.start()
    t.join(VO_TIMEOUT)
    if t.is_alive() or "err" in box:
        return None
    return box.get("wav")


def step_render(p, ask, sid=""):
    import tts
    p["stage"] = "render"
    ready = sorted([m for m in p["moments"] if m["status"] == "ready"], key=lambda m: m["rank"])
    if len(ready) < 3:
        raise RuntimeError("a ranking needs at least 3 ready clips")
    items = []
    voice = p.get("voice") if p.get("voice") in tts.VOICES else rankreel.DEF_VOICE
    for i, m in enumerate(ready):
        it = {"src": "lib:" + m["src"], "label": m["label"], "rank": i + 1, "trimIn": float(m.get("trimIn") or 0),
              "dur": round(float(m.get("dur") or 6), 2), "verdict": m.get("verdict") or "", "aspect": m.get("aspect", 0.5625),
              "source": m.get("pick", "")}
        if it["verdict"] and p.get("vo", True):
            p["stage_note"] = "voice %d/%d" % (i + 1, len(ready))
            save(p)
            wav = _say(it["verdict"], voice)
            if not wav:                                  # voice engine stuck/busy — keep going, just without this line's VO
                log(p, "#%d voice-over skipped (voice engine didn't answer in %d s)" % (it["rank"], VO_TIMEOUT), "warn")
                items.append(it)
                continue
            it["vo"] = "lib:" + rankreel._to_lib(wav, p["user"], sid, it["verdict"])
            it["voDur"] = round(rankreel._wav_secs(wav), 2)
            it["dur"] = round(min(rankreel.MAX_CLIP, max(it["dur"], it["voDur"] + 0.8)), 2)
        items.append(it)
    pj = rankreel.build_project(p["title"], p.get("keywords") or "", items, p.get("order") or "shuffle", int(p.get("seed") or 7),
                                session=sid, extra={k: p[k] for k in ("kwColor", "hook", "intro") if p.get(k) not in (None, "")})
    if p.get("project"):
        pj["id"] = p["project"]
    p["project"] = remotion.save_project(p["user"], pj)
    pj["id"] = p["project"]
    p["stage_note"] = "rendering"
    log(p, "rendering %d clips" % len(items))
    save(p)
    mj = remotion.start_job(remotion.clean(pj), p["user"], sid, "mp4", 20, "rankreel", prefix="rankreel")
    p["render"] = {"job": mj["id"], "pct": 0}
    while mj.get("status") == "running":
        p["render"]["pct"] = mj.get("pct") or 0
        p["stage_note"] = "rendering · %s" % (mj.get("stage") or "")
        save(p)
        time.sleep(1.5)
    if mj.get("status") != "done":
        raise RuntimeError(mj.get("error") or "render %s" % mj.get("status"))
    p["render"] = {"job": mj["id"], "pct": 100, "src": mj["src"], "url": mj["url"], "secs": mj.get("dur")}
    if OUT_DIR:                                              # optional export folder (mml_config / Settings)
      try:
          os.makedirs(OUT_DIR, exist_ok=True)
          import unicodedata
          plain = unicodedata.normalize("NFKD", p["title"].replace("\n", " ")).encode("ascii", "ignore").decode()   # Clásico → Clasico
          slug = re.sub(r"[^A-Za-z0-9]+", "_", plain).strip("_")[:60] or "rank_reel"
          dst = os.path.join(OUT_DIR, "%s_%s.mp4" % (slug, time.strftime("%Y%m%d_%H%M")))
          shutil.copy2(os.path.join(core.LIB, mj["src"].split(":", 1)[-1]), dst)
          p["render"]["copy"] = dst
      except Exception as e:
          log(p, "couldn't copy to the export folder: %s" % e, "warn")
    p["stage_note"] = ""
    log(p, "final cut ready", "done")
    p.update(state="waiting", wait="final")


def _wait_or_go(p, stage, ask):
    """Checkpoint after a stage; auto mode rolls straight on to the next one (stops before publishing)."""
    p["stage"] = stage
    if p.get("auto") and stage != "render":
        nxt = {"moments": step_clips, "clips": step_script, "script": step_render}[stage]
        save(p)
        return nxt(p, ask) if stage != "script" else step_render(p, ask)
    p.update(state="waiting", wait=stage)
    log(p, {"moments": "check the moments", "clips": "check the clips", "script": "check the script"}[stage], "need")


# ── Flask ──────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, static(fn), session(sid), ask(prompt, system), is_owner()."""
    from flask import jsonify, request

    U = lambda: hk["uid"]()
    ask = hk.get("ask")

    try:                         # a restart kills worker threads: runs left "running" would look busy forever
        for ud in os.listdir(D):
            for f in os.listdir(os.path.join(D, ud)) if os.path.isdir(os.path.join(D, ud)) else []:
                if f.endswith(".json"):
                    path = os.path.join(D, ud, f)
                    with open(path, encoding="utf-8") as fh:
                        p = json.load(fh)
                    if p.get("state") == "running":
                        p.update(state="error", error="The lab restarted while this step was running — press Try again.", stage_note="")
                        log(p, "interrupted by a restart", "warn")
                        save(p)
    except Exception:
        pass

    @app.route("/rankreel")
    def rrw_page():
        return hk["static"]("rankreel.html")

    @app.route("/api/rankreel/runs")
    def rrw_runs():
        return jsonify({"runs": listing(U())})

    @app.route("/api/rankreel/start", methods=["POST"])
    def rrw_new():
        b = request.get_json(silent=True) or {}
        topic = str(b.get("topic") or "").strip()[:150]
        if not topic:
            return jsonify({"error": "give it a topic"}), 400
        pid = uuid.uuid4().hex[:12]
        p = {"id": pid, "user": U(), "topic": topic, "title": "", "keywords": "", "count": int(rankreel._f(b.get("count"), 6, 3, 8)),
             "voice": b.get("voice") or rankreel.DEF_VOICE, "vo": True, "auto": bool(b.get("auto")), "order": "shuffle",
             "seed": int(time.time()) % 9973 + 1, "state": "running", "stage": "moments", "moments": [], "created": time.time(), "log": []}
        save(p)
        _run(U(), pid, lambda p: step_moments(p, ask))
        return jsonify(p)

    @app.route("/api/rankreel/<pid>")
    def rrw_get(pid):
        p = load(U(), pid)
        return jsonify(p) if p else (jsonify({"error": "no such reel"}), 404)

    @app.route("/api/rankreel/<pid>/<action>", methods=["POST"])
    def rrw_act(pid, action):
        uid = U()
        p = load(uid, pid)
        if not p:
            return jsonify({"error": "no such reel"}), 404
        b = request.get_json(silent=True) or {}
        if p.get("state") == "running" and action not in ("delete", "edit"):
            return jsonify({"error": "still working — wait for the current step"}), 409
        if action in ("approve", "redo") and any(m.get("status") in ("finding", "downloading") for m in p.get("moments") or []):
            return jsonify({"error": "a clip is still downloading — wait a moment, then try again"}), 409
        sid = hk["session"](b.get("session")) or ""

        def edits(p):          # title / keywords / voice / per-moment fields from the page
            for k in ("title", "keywords", "voice", "kwColor", "hook", "order"):
                if k in b:
                    p[k] = str(b[k])[:120]
            if "seed" in b:
                p["seed"] = int(rankreel._f(b["seed"], 7, 1, 9999))
            if isinstance(b.get("moments"), list) and p["stage"] == "moments":     # edited / reordered list (rank = list order)
                p["moments"] = [_moment(i + 1, m) for i, m in enumerate([m for m in b["moments"][:8] if isinstance(m, dict) and m.get("query")])]
            for e in b.get("clips") or []:
                m = next((x for x in p["moments"] if x["rank"] == e.get("rank")), None)
                if m:
                    for k, lo, hi in (("trimIn", 0, 3600), ("dur", rankreel.MIN_CLIP, rankreel.MAX_CLIP)):
                        if e.get(k) not in (None, ""):
                            m[k] = round(rankreel._f(e[k], m.get(k) or 0, lo, hi), 2)
                    for k in ("label", "verdict", "query"):
                        if k in e:
                            m[k] = str(e[k])[:150]

        if action == "edit":
            with _lock(pid):
                p = load(uid, pid)
                edits(p)
                save(p)
            return jsonify(p)
        if action == "delete":
            try:
                os.remove(os.path.join(_dir(uid), pid + ".json"))
            except OSError:
                pass
            return jsonify({"ok": True})

        edits(p)
        p["error"] = ""
        save(p)
        if action == "approve":
            nxt = {"moments": lambda p: step_clips(p, ask, sid=sid), "clips": lambda p: step_script(p, ask),
                   "script": lambda p: step_render(p, ask, sid)}.get(p.get("wait") or p["stage"])
            if p.get("wait") == "final":
                owner = bool(hk["is_owner"]())      # resolved HERE: is_owner reads flask.g, which the worker thread has no access to
                def publish(p):
                    p["stage"] = "publish"
                    if b.get("draft") and owner:
                        import social
                        credits = "; ".join(m.get("pick", "") for m in p["moments"] if m.get("pick"))
                        post = social.create_draft(p["render"]["src"].split(":", 1)[-1],      # bare library name (create_draft basenames it; "lib:x" never matched)
                                                    b.get("platforms") or ["youtube", "instagram"],
                                                   brief="Ranking Short: %s. Credit the original clips: %s" % (p["title"].replace("\n", " "), credits[:900]),
                                                   fit="crop", yt_format="short", captions="none")
                        p["post"] = post["id"]
                        log(p, "Social draft made — approve it in Social to post", "done")
                    p.update(stage="done", state="done", wait="")
                    log(p, "done", "done")
                _run(uid, pid, publish)
            elif nxt:
                _run(uid, pid, nxt)
            else:
                return jsonify({"error": "nothing to approve"}), 400
        elif action in ("requery", "pick"):        # one clip: new search + top pick, or this candidate / pasted link
            rank, url = int(b.get("rank") or 0), str(b.get("url") or "").strip()
            if action == "pick" and not re.match(r"^https?://", url):
                return jsonify({"error": "paste a full link"}), 400

            m = next((x for x in p["moments"] if x["rank"] == rank), None)
            if not m:
                return jsonify({"error": "no such clip"}), 404
            if m.get("status") in ("finding", "downloading"):
                return jsonify({"error": "that clip is still downloading"}), 409
            _clip_job(uid, pid, rank, action, url, sid)    # per-clip: the reel stays editable, other clips untouched
        elif action == "drop":                     # remove a moment from the ranking
            rank = int(b.get("rank") or 0)
            p["moments"] = [m for m in p["moments"] if m["rank"] != rank]
            for i, m in enumerate(sorted(p["moments"], key=lambda m: m["rank"])):
                m["rank"] = i + 1
            save(p)
        elif action == "back":                     # step back to a checkpoint without redoing anything (swap one clip, edit lines)
            step = b.get("step")
            if step not in ("clips", "script"):
                return jsonify({"error": "can only go back to clips or script"}), 400
            p.update(stage=step, state="waiting", wait=step)
            log(p, "back to the %s" % step, "need")
            save(p)
        elif action == "redo":                     # go back to a stage and run it again
            step = b.get("step")
            fn = {"moments": lambda p: (p.update(title="", keywords=""), step_moments(p, ask)),
                  "clips": lambda p: step_clips(p, ask, sid=sid), "script": lambda p: step_script(p, ask),
                  "render": lambda p: step_render(p, ask, sid)}.get(step)
            if not fn:
                return jsonify({"error": "unknown step"}), 400
            if step == "script":
                for m in p["moments"]:
                    m["verdict"] = ""
                save(p)
            _run(uid, pid, fn)
        else:
            return jsonify({"error": "unknown action"}), 400
        return jsonify(load(uid, pid))
