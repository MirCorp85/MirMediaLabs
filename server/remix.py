"""
remix.py — VIRAL-Ω REMIX: study a viral video, make OUR original version of it in the Media Lab, and judge the result.
═══════════════════════════════════════════════════════════════════════════════
One remix = a background run:

  1 fetch     URL → Downloader (grab.py, yt-dlp) → library  ·  or a library file ("lib:<name>")
  2 see       scene-cut keyframes + Whisper words; the brain READS the frames (cloud brain or local vision)
  3 analyze   what makes it travel (hook, beats, pacing, payoff) vs what is PROTECTED (real people, characters,
              logos, music, the exact footage) + the best ≤8 s segment + which strategy fits
  4 plan      our original version: same mechanics, new subject / world / characters / look, our identity
  5 render    Media Lab H3 jobs (through the series runner's submit, so they queue like any lab request):
                restyle  = control·canny  → same composition + motion, new look and subject
                motion   = control·pose   → same body movement, new character + world
                recreate = text→video shots → the same structure, all-new footage (most original)
  6 judge     the brain compares source frames vs result frames: mechanics kept · originality · quality · hook
              → pass, or re-plan with concrete fixes and render again (best attempt kept)
  7 draft     the winner becomes a Social DRAFT (hook lab, captions, lint run as usual). Never published here.

The source footage, audio and anyone's likeness are never reused in the output — only the mechanics.
  data/social/remix/remixes.json · data/social/remix/<id>/ (frames)
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

import core
import social

RD = os.path.join(social.SD, "remix")
STORE = os.path.join(RD, "remixes.json")
STRATEGIES = ("auto", "restyle", "motion", "recreate")
PASS = {"mechanics": 6, "originality": 7, "quality": 6}
_LOCK = threading.RLock()
_QUEUE = []
_HK = {}
_RUNNING = {"id": None}
os.makedirs(RD, exist_ok=True)


def _log(m):
    social._log(m)


def all_():
    return core.load_json(STORE, [])


def get(rid):
    return next((r for r in all_() if r["id"] == rid), None)


def _upd(rid, **kw):
    with _LOCK:
        rs = all_()
        for r in rs:
            if r["id"] == rid:
                r.update(kw)
                r["updated"] = time.time()
                core.save_json(STORE, rs)
                return r
    return None


def _stage(rid, stage, **kw):
    _upd(rid, stage=stage, **kw)


def identity():
    v = social.accounts().get("viral") or {}
    return v.get("identity") or ("MIR MEDIA LABS: striking, cinematic, impossible-but-photoreal worlds and creatures; playful surreal "
                                 "twists; warm amber accent light; no real people, no celebrities, no existing characters or brands; "
                                 "formats that can become a numbered series.")


# ── a brain with eyes: the owner's cloud brain (Claude / GPT read pictures), else the local vision engine ─────────
def brain_see(task, images, system, timeout=420):
    """Look at the frame JPGs (in time order) → text."""
    import base64

    def b64(n):
        out = []
        for p in images[:n]:
            with open(p, "rb") as f:
                out.append(base64.b64encode(f.read()).decode())
        return out

    task += "\n\nThe pictures are in time order."
    b = social._brain()
    try:
        import cloud
        if b and cloud.sees(b):
            return cloud.ask(b, task, system, images=b64(10), role="social", timeout=timeout)
    except Exception as e:
        _log("[remix] cloud vision: %s — using the local vision engine" % e)
    return core.ask(task, system, timeout=400, images=b64(6))


def _json(txt):
    if isinstance(txt, dict):
        return txt
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def _sys():
    return social._soul() + "\n\n## Remix rules\nYou study a viral video to learn WHY it travels, then design OUR original " \
        "version for " + (social.accounts().get("handle") or "our account") + ". Keep the mechanics (hook type, structure, pacing, payoff, loop, format). Change the " \
        "expression: subject, characters, world, look, story details, sound. Never reuse their footage, music or text; never " \
        "depict real people, celebrities, existing characters, logos or brands. Our identity: " + identity() + \
        "\nAlways reply with ONE valid JSON object and nothing else."


# ── media helpers ───────────────────────────────────────────────────────────────────────────────────────────────────
def _ff(args, timeout=600):
    return subprocess.run([core.FFMPEG, "-hide_banner", "-y"] + args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(core, "NO_WINDOW", 0))


def cuts(path, thr=0.32):
    r = _ff(["-i", path, "-vf", "select='gt(scene,%s)',showinfo" % thr, "-an", "-f", "null", "-"], 900)
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def stills(path, times, outdir, tag):
    os.makedirs(outdir, exist_ok=True)
    out = []
    for i, t in enumerate(times):
        f = os.path.join(outdir, "%s_%02d.jpg" % (tag, i))
        _ff(["-ss", "%.2f" % max(0, t), "-i", path, "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", f], 60)
        if os.path.isfile(f):
            out.append(f)
    return out


def _times(dur, cut_list, n=10):
    ts = [0.3] + [c + 0.25 for c in cut_list if 0.6 < c < dur - 0.3]
    if len(ts) > n:                                        # keep an even spread of the cuts
        step = len(ts) / float(n)
        ts = [ts[int(i * step)] for i in range(n)]
    while len(ts) < min(n, 6):                             # few/no cuts: sample evenly
        ts = sorted(set(ts + [dur * k / 6.0 for k in range(1, 6)]))[:n]
    return sorted(ts)


def _lib_path(name):
    p = core.in_dir(core.LIB, name)
    return p if p and os.path.isfile(p) else None


# ── steps ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _fetch(r):
    src = r["source"]
    if src.startswith("lib:"):
        name = src[4:]
        if not _lib_path(name):
            raise RuntimeError("that library file is gone")
        return name, core.index().get(name, {}).get("prompt") or name
    import grab
    if not grab.available():
        raise RuntimeError("the Downloader (yt-dlp) isn't installed")
    job = {"id": "rx" + uuid.uuid4().hex[:8], "user": "owner", "url": grab._clean_url(src), "mode": "video", "status": "queued",
           "stage": "", "session": "", "pct": 0, "files": [], "created": time.time(), "start": None, "end": 90.0,
           "quality": "720", "abr": "192", "stills": 0, "title": None, "thumb": None}
    grab._run(job)                                          # first 90 s at 720p is plenty to study a short
    if job["status"] != "done" or not job["files"]:
        raise RuntimeError("download failed: %s" % (job.get("error") or job["status"]))
    return job["files"][0], job.get("title") or src


def _analyze(r, name):
    path = _lib_path(name)
    info = social.probe(path)
    dur = info["duration"] or 0
    if dur < 1:
        raise RuntimeError("couldn't read the video")
    cl = cuts(path)
    d = os.path.join(RD, r["id"])
    frames = stills(path, _times(dur, cl), d, "src")
    words = ""
    if info["audio"]:
        try:
            import series_audio
            ws = (series_audio.words_of(path) or {}).get("words") or []
            words = " ".join(w["w"] for w in ws)[:1500]
        except Exception as e:
            _log("[remix] whisper: %s" % e)
    meta = {"duration": round(dur, 1), "w": info["w"], "h": info["h"], "cuts": len(cl),
            "avg_shot_s": round(dur / (len(cl) + 1), 2), "speech": words, "title": r.get("title", "")}
    a = _json(brain_see(
        "Study this viral short (frames in time order, cut count, transcript in DATA). Return JSON {\"summary\": 2 sentences, "
        "\"hook\": what happens in the first 2 s and why it stops the scroll, \"beats\": [{\"t\": seconds, \"what\", \"camera\"}], "
        "\"pacing\", \"payoff\": the reward/twist/loop at the end, \"mechanics\": [the 3-6 things that make it travel], "
        "\"protected\": [what we must NOT copy: real people, characters, brands, logos, music, exact scenes], \"audio_role\", "
        "\"best_segment\": {\"start\": s, \"end\": s} (the strongest <=8 s stretch, usually the hook), \"strategy\": "
        "\"restyle\" (keep composition+motion, new look/subject — only if no real person's likeness drives it) | \"motion\" "
        "(a person's body movement is the point → new character) | \"recreate\" (structure/format is the point → all-new shots), "
        "\"why_strategy\"}\n\nDATA: " + json.dumps(meta, ensure_ascii=False), frames, _sys()))
    if not a.get("mechanics"):
        raise RuntimeError("the analysis came back empty")
    return a, meta, frames


def _plan(r, a, meta, fixes=None, prev=None):
    strat = r["strategy"] if r["strategy"] != "auto" else (a.get("strategy") if a.get("strategy") in STRATEGIES else "recreate")
    seg = a.get("best_segment") or {}
    secs = max(3.0, min(8.0, float(seg.get("end", 8) or 8) - float(seg.get("start", 0) or 0)))
    task = ("Design OUR original version of the analysed viral video. Strategy: %s. %s Owner notes: %s.\n"
            "Return JSON {\"title\", \"concept\": 1-2 sentences, \"twist\": what makes it unmistakably OURS (not a copy), "
            "\"hook\": on-screen hook <=7 words, \"keeps\": [mechanics we keep], \"changes\": [what we changed vs the source], "
            "\"character\": ONE precise visual design of the recurring hero(es) — shape, material, colours, face (keep faces simple), "
            "size; it is drawn once as a reference picture and every shot reuses it, so it must not change between shots, "
            "\"shots\": [{\"secs\": 3-8, \"prompt\": a full MiniMax H3 video prompt — the hero from the reference picture, its "
            "action, world, camera, light, look, sound; vertical 9:16; no text on screen; no humans or human hands unless the owner "
            "asked}]} — %s"
            % (strat, {"restyle": "ONE shot that re-renders the source segment's composition and motion (edges) with a brand-new "
                                  "subject, world and look — describe the new scene fully; it must not look like the source.",
                       "motion": "ONE shot: a brand-new character (creature, robot, stylised hero — never a real person) performs the "
                                 "source's exact body movement in a new world — describe character and world fully.",
                       "recreate": "1-3 NEW shots (total 6-16 s) that rebuild the same structure — hook, build, payoff — with "
                                   "different subject, world and story details. Every prompt stands alone."}[strat],
               r.get("notes") or "none",
               "ONE shot, secs=%.0f." % secs if strat in ("restyle", "motion") else "shots in story order."))
    data = {"analysis": {k: a.get(k) for k in ("summary", "hook", "beats", "pacing", "payoff", "mechanics", "protected", "audio_role")},
            "source": {k: meta.get(k) for k in ("duration", "cuts", "avg_shot_s")}}
    if fixes:
        task += "\nThis is a REVISION. The judge rejected the last attempt — apply every fix: " + json.dumps(fixes, ensure_ascii=False)
        data["previous_plan"] = prev
    p = social.ask_agent(task, data)
    shots = [s for s in (p.get("shots") or []) if isinstance(s, dict) and s.get("prompt")][:3]
    if not shots:
        raise RuntimeError("the plan came back without shots")
    if strat in ("restyle", "motion"):
        shots = shots[:1]
        shots[0]["secs"] = secs
    for s in shots:
        s["secs"] = int(round(max(3, min(8, float(s.get("secs") or 5)))))
    p.update(strategy=strat, shots=shots, segment={"start": float(seg.get("start", 0) or 0), "secs": secs})
    return p


def _segment_ref(r, name, seg):
    """The source stretch the control modes follow → a lab reference (muted: their sound is never reused)."""
    out = os.path.join(RD, r["id"], "segment.mp4")
    _ff(["-ss", "%.2f" % seg["start"], "-t", "%.2f" % seg["secs"], "-i", _lib_path(name), "-an", "-c:v", "libx264", "-crf", "18",
         "-pix_fmt", "yuv420p", out], 300)
    if not os.path.isfile(out):
        raise RuntimeError("couldn't cut the source segment")
    return _HK["to_ref"]("owner", out)


def _wait(jid, rid, label, limit=50 * 60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if (get(rid) or {}).get("status") == "cancelled":
            _HK.get("cancel", lambda _j: None)(jid)
            raise RuntimeError("cancelled")
        j = _HK["job"](jid) or {}
        st = j.get("status")
        if st == "done":
            return j
        if st in ("failed", "cancelled", "error"):
            raise RuntimeError("%s render %s: %s" % (label, st, (j.get("error") or "")[:200]))
        _stage(rid, "%s · %s" % (label, j.get("stage") or st or "queued"))
        time.sleep(6)
    raise RuntimeError("%s render took too long" % label)


def _submit(body, rid, label):
    for _ in range(120):                                   # the person's own request runs first; we queue behind it
        j, err, busy = _HK["submit"](None, body)
        if j:
            return j["id"]
        if not busy:
            raise RuntimeError("the lab refused the render: %s" % err)
        _stage(rid, "%s · waiting for the lab" % label)
        time.sleep(15)
    raise RuntimeError("the lab stayed busy")


def _hero(r, plan):
    """CHARACTER LOCK: draw the hero once (Qwen image), so every shot renders the SAME character from that picture."""
    if not plan.get("character") or plan["strategy"] == "restyle":
        return None, None
    prompt = ("Character design reference, full body, centred, plain soft studio background, vertical 9:16, photoreal "
              "cinematic look, no text: %s. %s" % (plan["character"], identity()))
    jid = _submit({"model": "qimg", "prompt": prompt, "refs": [], "override": {"aspect": "9:16"}}, r["id"], "hero design")
    j = _wait(jid, r["id"], "hero design", 20 * 60)
    imgs = [f for f in j.get("files") or [] if core.kind_of(f) == "image"]
    if not imgs:
        return None, None
    return imgs[0], _HK["to_ref"]("owner", _lib_path(imgs[0]))


def _render(r, plan, ref):
    files = []
    base = {"aspect": "9:16", "res": "standard", "quality": "turbo8", "enhance": "on", "audio": "auto"}
    hero_lib, hero = _hero(r, plan)
    plan["hero"] = hero_lib
    for i, s in enumerate(plan["shots"]):
        label = "shot %d/%d" % (i + 1, len(plan["shots"]))
        if plan["strategy"] == "restyle":
            ov = dict(base, mode="control", control="canny", replace="whole", control_audio="h3", seconds=s["secs"])
        elif plan["strategy"] == "motion":
            ov = dict(base, mode="control", control="pose", replace="whole", control_audio="h3", control_people=2, seconds=s["secs"])
        elif hero:
            ov = dict(base, mode="r2v", ref_role="identity", seconds=s["secs"])
        else:
            ov = dict(base, mode="t2v", seconds=s["secs"])
        refs = ([ref] if ref and plan["strategy"] != "recreate" else []) + ([hero] if hero else [])
        body = {"model": "h3", "prompt": s["prompt"], "refs": refs, "override": ov}
        jid = _submit(body, r["id"], label)
        j = _wait(jid, r["id"], label)
        vids = [f for f in j.get("files") or [] if core.kind_of(f) == "video"]
        if not vids:
            raise RuntimeError("%s finished without a video" % label)
        files.append(vids[0])
    if len(files) == 1:
        return files[0]
    paths = [_lib_path(f) for f in files]
    w, h = social.probe(paths[0])["w"] or 720, social.probe(paths[0])["h"] or 1280
    name = core.new_name("remix", ".mp4")
    fc = "".join("[%d:v]scale=%d:%d,setsar=1,fps=24[v%d];[%d:a]aresample=48000[a%d];" % (i, w, h, i, i, i) for i in range(len(paths)))
    fc += "".join("[v%d][a%d]" % (i, i) for i in range(len(paths))) + "concat=n=%d:v=1:a=1[v][a]" % len(paths)
    args = sum([["-i", p] for p in paths], []) + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                                                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", os.path.join(core.LIB, name)]
    rr = _ff(args, 900)
    if rr.returncode:
        raise RuntimeError("assembling the shots failed: " + rr.stderr[-200:])
    core.index_add(name, {"model": "remix", "prompt": plan.get("title") or "VIRAL-Ω remix", "created": time.time(), "user": "owner",
                          "parts": files})
    return name


def _judge(r, src_frames, name, plan, n):
    path = _lib_path(name)
    dur = social.probe(path)["duration"] or 5
    res = stills(path, [0.3] + [dur * k / 5.0 for k in range(1, 5)] + [max(0.3, dur - 0.3)], os.path.join(RD, r["id"]), "try%d" % n)
    picks = src_frames[:6]
    v = _json(brain_see(
        "You are a strict judge. The FIRST %d images are frames of the SOURCE viral video; the LAST %d are frames of OUR remix. "
        "Our plan: %s. Score 0-10: \"mechanics\" (keeps what made the source travel: hook type, structure, pacing, payoff), "
        "\"originality\" (clearly its own thing — different subject, world, characters, look; 10 = nobody would call it a copy; "
        "below 5 if it is basically the same footage restyled), \"quality\" (no melting faces, morphing limbs, garbled text, "
        "flicker, ugly artefacts), \"hook\" (frame 1 stops a thumb). Also \"too_close\" true/false, \"good\": [what works], "
        "\"fixes\": [concrete prompt-level changes for a re-render], \"verdict\": \"pass\"|\"redo\", \"why\": one sentence. "
        "Return JSON." % (len(picks), len(res), json.dumps({k: plan.get(k) for k in ("concept", "twist", "hook", "keeps", "changes")},
                                                           ensure_ascii=False)), picks + res, _sys()))
    for k in ("mechanics", "originality", "quality", "hook"):
        try:
            v[k] = float(v.get(k) or 0)
        except (TypeError, ValueError):
            v[k] = 0.0
    v["passed"] = all(v[k] >= PASS[k] for k in PASS) and not v.get("too_close")
    v["score"] = round(v["mechanics"] * 0.3 + v["originality"] * 0.3 + v["quality"] * 0.25 + v["hook"] * 0.15, 2)
    v["frames"] = [os.path.basename(f) for f in res]
    return v


def run(rid):
    r = get(rid)
    if not r:
        return
    _RUNNING["id"] = rid
    try:
        _upd(rid, status="running")
        _stage(rid, "fetching the source")
        name, title = _fetch(r)
        _upd(rid, src_lib=name, title=r.get("title") or title)
        r = get(rid)
        _stage(rid, "watching it (keyframes + transcript)")
        a, meta, frames = _analyze(r, name)
        _upd(rid, analysis=a, meta=meta, src_frames=[os.path.basename(f) for f in frames])
        prev = fixes = None
        attempts, best = [], None
        for n in range(1, int(r.get("max_attempts") or 2) + 1):
            _stage(rid, "planning our version" + (" (revision %d)" % (n - 1) if n > 1 else ""))
            plan = _plan(get(rid), a, meta, fixes, prev)
            ref = _segment_ref(r, name, plan["segment"]) if plan["strategy"] in ("restyle", "motion") else None
            att = {"n": n, "plan": plan, "status": "rendering", "t": time.time()}
            attempts.append(att)
            _upd(rid, attempts=attempts)
            try:
                out = _render(get(rid), plan, ref)
            except RuntimeError as e:
                if "cancelled" in str(e):
                    raise
                att.update(status="failed", error=str(e)[:300])
                _upd(rid, attempts=attempts)
                fixes, prev = ["the render failed (%s) — simplify the shot" % str(e)[:120]], plan
                continue
            _stage(rid, "judging attempt %d against the source" % n)
            v = _judge(r, frames, out, plan, n)
            att.update(status="judged", lib=out, judge=v)
            _upd(rid, attempts=attempts)
            if not best or v["score"] > best["judge"]["score"]:
                best = att
            if v["passed"]:
                break
            fixes, prev = v.get("fixes") or ["make it more original and cleaner"], plan
        if not best:
            raise RuntimeError("no attempt rendered")
        _stage(rid, "making the Social draft")
        bp = best["plan"]
        post = social.create_draft(best["lib"], social.PLATFORMS, brief="%s — %s Hook idea: %s. (Original remix inspired by the "
                                                                          "mechanics of %s — never mention or tag the source.)"
                                   % (bp.get("title", ""), bp.get("concept", ""), bp.get("hook", ""), r["source"] if not r["source"].startswith("lib:") else "a reference clip"))
        _upd(rid, status="done", stage="draft ready" if best["judge"]["passed"] else "draft ready (best attempt — below the bar)",
             best=best["n"], post=post["id"])
        social._push("owner", "social_remix", "%s: remix ready" % social.AGENT, (bp.get("title") or "")[:120], post=post["id"])
    except Exception as e:
        cancelled = (get(rid) or {}).get("status") == "cancelled"
        _upd(rid, status="cancelled" if cancelled else "failed", stage="", error=None if cancelled else str(e)[:400])
        _log("[remix] %s: %s" % (rid, e))
    finally:
        _RUNNING["id"] = None


def _worker():
    while True:
        rid = _QUEUE.pop(0) if _QUEUE else None
        if rid:
            run(rid)
        else:
            time.sleep(3)


def start(source, strategy="auto", notes="", max_attempts=2, title=""):
    source = str(source or "").strip()
    if not source:
        raise ValueError("paste a video link (YouTube, TikTok, Instagram…) or pick a library file")
    if not (source.startswith("lib:") or re.match(r"^https?://", source)):
        raise ValueError("that isn't a link")
    r = {"id": uuid.uuid4().hex[:10], "source": source, "title": str(title or "")[:200], "strategy": strategy if strategy in STRATEGIES else "auto",
         "notes": str(notes or "")[:600], "max_attempts": max(1, min(3, int(max_attempts or 2))), "status": "queued",
         "stage": "waiting its turn", "created": time.time(), "attempts": []}
    with _LOCK:
        rs = all_()
        rs.insert(0, r)
        core.save_json(STORE, rs[:60])
    _QUEUE.append(r["id"])
    return r


def cancel(rid):
    r = get(rid)
    if not r or r["status"] not in ("queued", "running"):
        raise ValueError("not running")
    if rid in _QUEUE:
        _QUEUE.remove(rid)
    return _upd(rid, status="cancelled", stage="")


def delete(rid):
    with _LOCK:
        core.save_json(STORE, [x for x in all_() if x["id"] != rid])
    shutil.rmtree(os.path.join(RD, os.path.basename(rid)), ignore_errors=True)


_STARTED = []


def boot():
    if _STARTED:
        return
    _STARTED.append(1)
    for r in all_():                                       # a restart mid-run: those runs can't resume
        if r["status"] in ("queued", "running"):
            _upd(r["id"], status="failed", error="the lab restarted during the remix — start it again", stage="")
    threading.Thread(target=_worker, daemon=True, name="viral-remix").start()


def register(app, hk):
    from flask import request, jsonify, abort, send_file
    _HK.update(hk)
    boot()

    def owner():
        if not hk["is_owner"]():
            abort(403)

    @app.get("/api/viral/remix")
    def remix_list():
        owner()
        return jsonify({"remixes": all_()[:30], "running": _RUNNING["id"], "queued": list(_QUEUE),
                        "ready": bool(hk.get("submit")), "identity": identity()})

    @app.post("/api/viral/remix")
    def remix_start():
        owner()
        b = request.get_json(silent=True) or {}
        if b.get("identity"):
            a = social.accounts()
            a.setdefault("viral", {})["identity"] = str(b["identity"])[:800]
            social.save_accounts(a)
            if not b.get("source"):
                return jsonify({"identity": identity()})
        if not hk.get("submit"):
            return jsonify({"error": "the lab render hook isn't wired"}), 500
        try:
            return jsonify(start(b.get("source"), b.get("strategy", "auto"), b.get("notes", ""), b.get("attempts", 2), b.get("title", "")))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/viral/remix/<rid>/cancel")
    def remix_cancel(rid):
        owner()
        try:
            return jsonify(cancel(rid))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/viral/remix/<rid>/delete")
    def remix_delete(rid):
        owner()
        delete(rid)
        return jsonify({"ok": True})

    @app.get("/api/viral/remix/<rid>/frame/<name>")
    def remix_frame(rid, name):
        owner()
        p = core.in_dir(os.path.join(RD, os.path.basename(rid)), name)
        return send_file(p, mimetype="image/jpeg") if p and os.path.isfile(p) else abort(404)
