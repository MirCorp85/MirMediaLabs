r"""MIR MOTION — Remotion motion-graphics engine for the Media Lab (Motion Studio, Video Editor scenes, Series, Producer).

The React/Remotion side lives in <install>\motion (render daemon server.mjs on 127.0.0.1:5421,
scenes in src/scenes.tsx, browser preview bundle dist/mir-motion-player.js, scene catalog dist/schema.json).
This module: Motion Studio projects, render jobs → library (session-tagged), segmented long renders with a
per-segment cache, Whisper word timings for captions/lyrics, the AI scene writer, and daemon supervision.
CPU only — never takes the GPU render lock, so it runs alongside H3/Comfy jobs.

A motion PROJECT: {id, name, w, h, fps, font, palette{bg,fg,acc,acc2}, session, tracks:[{kind, name, mute, hide,
clips:[{id, type, start, dur, props, trans{type,dur}, out{type,dur}, kf{x,y,scale,rotate,opacity,blur}}]}]}
Media props are "lib:<name>" / "ref:<name>" (ownership-checked here before anything is sent to the daemon).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid

import core

ENGINE = core.CONFIG.get("motion_dir") or os.environ.get("MML_MOTION_DIR") or os.path.join(core.ROOT, "motion")
PORT = int(core.CONFIG.get("motion_port") or os.environ.get("MML_MOTION_PORT") or 5421)
BASE = "http://127.0.0.1:%d/" % PORT
FONTS = os.path.join(core.STATIC, "fonts", "mir")
MD = os.path.join(core.DATA, "motion")
PROJ = os.path.join(MD, "projects")
CACHE = os.path.join(MD, "cache")      # segment + still cache (keyed by content hash)
SEG_S = 45.0                           # long renders are cut into ≤45 s segments, each cached by content
MAX_CLIPS = 600
_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
JOBS = {}                              # jid -> {id,status,pct,stage,name,user,started,finished,error,segs}
_JLOCK = threading.Lock()
_DLOCK = threading.Lock()
for _d in (PROJ, CACHE):
    os.makedirs(_d, exist_ok=True)


# ── daemon ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _http(path, body=None, timeout=10):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def health():
    try:
        return _http("health", timeout=2)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def ensure_daemon(wait=40):
    """Start the Node render daemon (hidden, detached) if it isn't answering; wait until it's up."""
    if health().get("ok"):
        return True
    with _DLOCK:
        if health().get("ok"):
            return True
        node = core.CONFIG.get("node") or shutil.which("node") or (r"C:\Program Files\nodejs\node.exe" if os.name == "nt" else "node")
        log = open(os.path.join(MD, "daemon.log"), "ab")
        env = dict(os.environ, MIR_LIB=core.LIB, MIR_REFS=core.REFS, MIR_MOTION_PORT=str(PORT), MIR_FONTS=FONTS)
        if os.path.isabs(node):                                       # the installer's private Node: first on PATH
            env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")
        flags = (0x00000008 | 0x08000000) if os.name == "nt" else 0       # DETACHED_PROCESS | CREATE_NO_WINDOW
        subprocess.Popen([node, "server.mjs"], cwd=ENGINE, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         env=env, creationflags=flags, close_fds=True)
        t = time.time()
        while time.time() - t < wait:
            time.sleep(1)
            if health().get("ok"):
                return True
    return False


_SCHEMA = {"t": 0, "d": None}


def schema():
    p = os.path.join(ENGINE, "dist", "schema.json")
    try:
        m = os.path.getmtime(p)
        if _SCHEMA["t"] != m:
            _SCHEMA.update(t=m, d=json.load(open(p, encoding="utf-8")))
    except Exception:
        pass
    return _SCHEMA["d"] or {"scenes": {}, "textAnims": [], "transitions": []}


# ── project helpers ─────────────────────────────────────────────────────────────────────────────────────────────
def _num(v, d=0.0, lo=None, hi=None):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = d
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def duration(p):
    return max([_num(c.get("start")) + _num(c.get("dur")) for t in p.get("tracks") or [] for c in t.get("clips") or []] + [0.0])


def _media_refs(p):
    """Every "lib:"/"ref:" string inside clip props (src, images[], …)."""
    out = set()

    def walk(v):
        if isinstance(v, str):
            if re.match(r"^(lib|ref):[^/\\]+$", v):
                out.add(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    for t in p.get("tracks") or []:
        for c in t.get("clips") or []:
            walk(c.get("props") or {})
    return out


def clean(p):
    """Bound + normalise a project before it goes to the daemon."""
    sc = schema().get("scenes") or {}
    p = dict(p or {})
    p["w"] = int(_num(p.get("w"), 1280, 128, 3840)) & ~1
    p["h"] = int(_num(p.get("h"), 720, 128, 3840)) & ~1
    p["fps"] = int(_num(p.get("fps"), 30, 1, 60))
    tracks, n = [], 0
    for t in (p.get("tracks") or [])[:24]:
        if not isinstance(t, dict):
            continue
        clips = []
        for c in t.get("clips") or []:
            if not isinstance(c, dict) or (sc and c.get("type") not in sc) or n >= MAX_CLIPS:
                continue
            n += 1
            c = dict(c)
            c["id"] = str(c.get("id") or uuid.uuid4().hex[:8])[:24]
            c["start"] = round(_num(c.get("start"), 0, 0, 6 * 3600), 3)
            c["dur"] = round(_num(c.get("dur"), 3, 0.05, 6 * 3600), 3)
            c["props"] = c.get("props") if isinstance(c.get("props"), dict) else {}
            clips.append(c)
        tracks.append({"kind": t.get("kind") or "scene", "name": str(t.get("name") or "")[:40], "mute": bool(t.get("mute")),
                       "hide": bool(t.get("hide")), "clips": clips})
    p["tracks"] = tracks
    return p


def _slice(p, a, b):
    """The clips that touch [a,b) — the content a segment's cache key depends on."""
    keep = []
    for t in p.get("tracks") or []:
        for c in t.get("clips") or []:
            if c["start"] < b and c["start"] + c["dur"] > a:
                keep.append(c)
    return keep


def _key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:20]


def _ff(args, timeout=1800):
    r = subprocess.run([core.FFMPEG, "-nostdin", "-y", "-loglevel", "error"] + args, capture_output=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.decode("utf-8", "replace")[-300:])


def _wait(jid, dj, job, base, span):
    """Poll one daemon job, mapping its progress into job['pct'] over [base, base+span]."""
    while True:
        if job.get("status") == "cancelled":
            try:
                _http("cancel/" + dj, {})
            except Exception:
                pass
            raise RuntimeError("cancelled")
        s = _http("job/" + dj, timeout=10)
        job["pct"] = round(base + span * (s.get("pct") or 0) / 100.0, 1)
        if s.get("status") == "done":
            return
        if s.get("status") in ("error", "cancelled"):
            raise RuntimeError(s.get("error") or s.get("status"))
        time.sleep(0.8)


CODEC_EXT = {"mp4": ".mp4", "h265": ".mp4", "webm": ".webm", "alpha": ".webm", "prores": ".mov", "gif": ".gif", "mp3": ".mp3", "wav": ".wav"}


def render(jid, p, out, codec, crf, on_done):
    """Short renders go straight to the daemon; long mp4 renders run as cached muted segments + one audio pass."""
    job = JOBS[jid]
    try:
        if not ensure_daemon():
            raise RuntimeError("the motion engine (Node render daemon) did not start — see data/motion/daemon.log")
        total = duration(p)
        if total <= 0:
            raise RuntimeError("the timeline is empty")
        fps = p["fps"]
        if codec != "mp4" or total <= SEG_S * 1.5:
            job["stage"] = "rendering"
            dj = jid + "_" + uuid.uuid4().hex[:4]
            _http("render", {"id": dj, "project": p, "out": out, "codec": codec, "crf": crf})
            _wait(jid, dj, job, 0, 100)
        else:
            nf = int(round(total * fps))
            step = int(SEG_S * fps)
            ranges = [(a, min(nf, a + step) - 1) for a in range(0, nf, step)]
            job["segs"] = len(ranges)
            files = []
            has_audio = any(t.get("kind") == "audio" or any((c.get("type") in ("media", "visualizer") and not (c.get("props") or {}).get("mute"))
                                                              for c in t.get("clips") or []) for t in p["tracks"])
            span = 85.0 / len(ranges)
            for i, (a, b) in enumerate(ranges):
                k = _key(p["w"], p["h"], p["fps"], p.get("font"), p.get("palette"), a, b, _slice(p, a / fps, (b + 1) / fps), "v2")
                seg = os.path.join(CACHE, "seg_%s.mp4" % k)
                files.append(seg)
                job["stage"] = "segment %d/%d%s" % (i + 1, len(ranges), " (cached)" if os.path.isfile(seg) else "")
                if os.path.isfile(seg):
                    job["pct"] = round(span * (i + 1), 1)
                    job["cached"] = job.get("cached", 0) + 1
                    continue
                dj = "%s_s%d" % (jid, i)
                tmp = seg[:-4] + ".part.mp4"
                _http("render", {"id": dj, "project": p, "out": tmp, "codec": "mp4", "crf": crf, "frameRange": [a, b], "muted": True})
                _wait(jid, dj, job, span * i, span)
                os.replace(tmp, seg)
            lst = os.path.join(CACHE, jid + "_list.txt")
            with open(lst, "w", encoding="utf-8") as f:
                f.write("".join("file '%s'\n" % x.replace("\\", "/") for x in files))
            job["stage"] = "joining"
            video = os.path.join(CACHE, jid + "_video.mp4")
            _ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
            if has_audio:
                job["stage"] = "audio"
                wav = os.path.join(CACHE, jid + "_audio.wav")
                dj = jid + "_aud"
                _http("render", {"id": dj, "project": p, "out": wav, "codec": "wav"})
                _wait(jid, dj, job, 85, 12)
                _ff(["-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
                os.remove(wav)
                os.remove(video)
            else:
                shutil.move(video, out)
            os.remove(lst)
        on_done(job)
        job.update(status="done", pct=100.0, stage="done", finished=time.time())
    except Exception as e:
        if job.get("status") != "cancelled":
            job.update(status="error", error=str(e)[:600], finished=time.time())
        else:
            job["finished"] = time.time()


def prune_cache(max_gb=8.0):
    fs = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE)), key=lambda x: os.path.getatime(x))
    tot = sum(os.path.getsize(f) for f in fs)
    while fs and tot > max_gb * 1e9:
        f = fs.pop(0)
        tot -= os.path.getsize(f)
        try:
            os.remove(f)
        except OSError:
            pass


# ── AI scene writer ─────────────────────────────────────────────────────────────────────────────────────────────
def ai_system():
    sc = schema()
    lines = []
    for k, s in (sc.get("scenes") or {}).items():
        f = ", ".join("%s(%s%s)" % (x["k"], x["t"], (":" + "|".join(map(str, x.get("opts") or []))[:120]) if x.get("opts") else "")
                      for x in s.get("fields") or [])
        lines.append("- %s [%s track, default %ss]: %s" % (k, s.get("track"), s.get("dur"), f))
    return ("You are MIR MOTION's director: you turn a request into motion-graphics clips for a Remotion timeline.\n"
            "Scene types and their props:\n" + "\n".join(lines) +
            "\nText animations: " + ", ".join(sc.get("textAnims") or []) +
            "\nTransitions (clip.trans / clip.out = {type, dur}): " + ", ".join(sc.get("transitions") or []) +
            "\nRules: return ONE JSON object {\"name\":..., \"palette\":{\"bg\",\"fg\",\"acc\",\"acc2\"} (hex, optional), "
            "\"font\": one of bastion|hollow|horizon|matrix|orbit|pixel|quill|stencil|vector|velocity (optional), "
            "\"tracks\":[{\"kind\":\"scene|overlay|captions|audio\",\"clips\":[{\"type\",\"start\",\"dur\",\"props\",\"trans\",\"out\"}]}]}. "
            "Times in seconds; scene-track clips are back-to-back and may overlap by the transition length; overlays (lowerthird, "
            "captions, shape, transparent titles) go on later tracks. Only use media names from the AVAILABLE MEDIA list, as \"lib:<name>\". "
            "Keep on-screen text short and punchy. Colour props left empty use the project palette. No prose, JSON only.")


# ── Flask routes ────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, my_file, my_ref, static(fn), session(sid)->valid sid, ask(prompt, system, want_json), words(path)->[{w,s,e}],
    lib_list() -> [{name, kind, prompt}] (this user's library, newest first)."""
    from flask import abort, jsonify, request, send_file

    def pdir():
        d = os.path.join(PROJ, re.sub(r"[^A-Za-z0-9_-]", "_", str(hk["uid"]())))
        os.makedirs(d, exist_ok=True)
        return d

    def owned(p):
        bad = []
        for r in _media_refs(p):
            kind, _, name = r.partition(":")
            ok = hk["my_file"](name) if kind == "lib" else hk["my_ref"](name)
            path = core.in_dir(core.LIB if kind == "lib" else core.REFS, name)
            if not ok or not path or not os.path.isfile(path):
                bad.append(r)
        return bad

    @app.route("/motion")
    def motion_page():
        return hk["static"]("motion.html")

    @app.route("/motion/player.js")
    def motion_player():
        p = os.path.join(ENGINE, "dist", "mir-motion-player.js")
        if not os.path.isfile(p):
            abort(404)
        return send_file(p, mimetype="application/javascript", max_age=60)

    @app.route("/motion/fonts/<name>")
    def motion_font(name):
        name = os.path.basename(name)
        p = os.path.join(FONTS, name)
        if not re.match(r"^[a-z]+\.(woff2|ttf)$", name) or not os.path.isfile(p):
            abort(404)
        return send_file(p, max_age=86400)

    @app.route("/api/motion/health")
    def mo_health():
        h = health()
        if not h.get("ok") and request.args.get("start"):
            threading.Thread(target=ensure_daemon, daemon=True).start()
        return jsonify(h)

    @app.route("/api/motion/schema")
    def mo_schema():
        return jsonify(schema())

    @app.route("/api/motion/projects")
    def mo_projects():
        out = []
        for f in os.listdir(pdir()):
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(pdir(), f), encoding="utf-8"))
            except Exception:
                continue
            out.append({"id": d.get("id"), "name": d.get("name") or "Untitled motion", "updated": d.get("updated"),
                        "dur": round(duration(d), 2), "w": d.get("w"), "h": d.get("h"), "session": d.get("session") or "",
                        "clips": sum(len(t.get("clips") or []) for t in d.get("tracks") or [])})
        sid = request.args.get("session")
        if sid is not None:
            out = [o for o in out if (o["session"] or "") == sid]
        out.sort(key=lambda x: -(x.get("updated") or 0))
        return jsonify({"projects": out})

    @app.route("/api/motion/project/<pid>")
    def mo_get(pid):
        p = os.path.join(pdir(), pid + ".json")
        if not _ID_RE.match(pid) or not os.path.isfile(p):
            return jsonify({"error": "no such project"}), 404
        return jsonify(json.load(open(p, encoding="utf-8")))

    @app.route("/api/motion/project", methods=["POST"])
    def mo_save():
        d = request.get_json(silent=True) or {}
        pid = str(d.get("id") or "")
        if not _ID_RE.match(pid):
            pid = uuid.uuid4().hex[:12]
        d = clean(d)
        d["id"] = pid
        d["name"] = str(d.get("name") or "Untitled motion")[:120]
        d["session"] = hk["session"](d.get("session")) or ""
        d["updated"] = time.time()
        d.setdefault("created", time.time())
        raw = json.dumps(d)
        if len(raw) > 6 * 1024 * 1024:
            return jsonify({"error": "project too large"}), 400
        vdir = os.path.join(pdir(), "versions")
        old = os.path.join(pdir(), pid + ".json")
        if os.path.isfile(old) and time.time() - os.path.getmtime(old) > 300:     # a restorable version every 5 min of work
            os.makedirs(vdir, exist_ok=True)
            shutil.copy2(old, os.path.join(vdir, "%s_%d.json" % (pid, int(os.path.getmtime(old)))))
        tmp = old + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, old)
        return jsonify({"id": pid, "updated": d["updated"]})

    @app.route("/api/motion/project/<pid>/versions")
    def mo_versions(pid):
        vdir = os.path.join(pdir(), "versions")
        vs = sorted((f for f in os.listdir(vdir) if f.startswith(pid + "_")), reverse=True) if os.path.isdir(vdir) else []
        return jsonify({"versions": [{"file": f, "t": int(f.rsplit("_", 1)[1].split(".")[0])} for f in vs[:50]]})

    @app.route("/api/motion/project/<pid>/restore", methods=["POST"])
    def mo_restore(pid):
        f = os.path.basename(str((request.get_json(silent=True) or {}).get("file") or ""))
        src = os.path.join(pdir(), "versions", f)
        if not _ID_RE.match(pid) or not f.startswith(pid + "_") or not os.path.isfile(src):
            abort(404)
        return jsonify(json.load(open(src, encoding="utf-8")))

    @app.route("/api/motion/project/<pid>/delete", methods=["POST"])
    def mo_delete(pid):
        p = os.path.join(pdir(), pid + ".json")
        if _ID_RE.match(pid) and os.path.isfile(p):
            shutil.move(p, os.path.join(core.TRASH, "motion_%s_%d.json" % (pid, int(time.time()))))
        return jsonify({"ok": True})

    @app.route("/api/motion/render", methods=["POST"])
    def mo_render():
        b = request.get_json(silent=True) or {}
        p = clean(b.get("project") or {})
        if not any(t["clips"] for t in p["tracks"]):
            return jsonify({"error": "nothing to render"}), 400
        bad = owned(p)
        if bad:
            return jsonify({"error": "media not available: " + ", ".join(sorted(bad)[:5])}), 400
        me = hk["uid"]()
        with _JLOCK:
            if sum(1 for j in JOBS.values() if j.get("user") == me and j.get("status") == "running") >= 2:
                return jsonify({"error": "two motion renders are already running — wait or cancel one"}), 409
        codec = b.get("codec") if b.get("codec") in CODEC_EXT else "mp4"
        crf = int(_num(b.get("crf"), 20, 12, 36))
        name = core.new_name("motion", CODEC_EXT[codec])
        out = os.path.join(core.LIB, name)
        sid = hk["session"](b.get("session") if "session" in b else p.get("session")) or ""
        jid = "m" + uuid.uuid4().hex[:10]
        JOBS[jid] = {"id": jid, "status": "running", "stage": "starting", "pct": 0.0, "user": me, "started": time.time(),
                     "name": name, "project": p.get("id"), "dur": round(duration(p), 2), "codec": codec, "purpose": b.get("purpose") or ""}

        def done(job):
            meta = {"model": "motion", "prompt": str(p.get("name") or "Motion")[:2000], "job": jid, "created": time.time(),
                    "user": me, "mode": "motion", "size": "%sx%s" % (p["w"], p["h"]), "project": p.get("id"),
                    "secs": round(duration(p), 2), "codec": codec}
            if sid:
                meta["session"] = sid
            core.index_add(name, meta)
            job["url"] = "media/" + name
            job["src"] = "lib:" + name
            prune_cache()
        threading.Thread(target=render, args=(jid, p, out, codec, crf, done), daemon=True).start()
        return jsonify(JOBS[jid])

    @app.route("/api/motion/jobs")
    def mo_jobs():
        me = hk["uid"]()
        js = [j for j in JOBS.values() if j.get("user") == me]
        js.sort(key=lambda j: -j.get("started", 0))
        return jsonify({"jobs": js[:30]})

    @app.route("/api/motion/job/<jid>")
    def mo_job(jid):
        j = JOBS.get(jid)
        if not j or j.get("user") != hk["uid"]():
            return jsonify({"error": "no such render"}), 404
        return jsonify(j)

    @app.route("/api/motion/job/<jid>/cancel", methods=["POST"])
    def mo_cancel(jid):
        j = JOBS.get(jid)
        if j and j.get("user") == hk["uid"]() and j.get("status") == "running":
            j["status"] = "cancelled"
        return jsonify({"ok": True})

    @app.route("/api/motion/still", methods=["POST"])
    def mo_still():
        """One frame as JPEG (thumbnails, AI critique, phone preview)."""
        b = request.get_json(silent=True) or {}
        p = clean(b.get("project") or {})
        if owned(p):
            return jsonify({"error": "media not available"}), 400
        fr = int(_num(b.get("frame"), 0, 0))
        out = os.path.join(CACHE, "still_%s.jpg" % _key(p, fr, b.get("scale")))
        if not os.path.isfile(out):
            if not ensure_daemon():
                return jsonify({"error": "motion engine offline"}), 503
            r = _http("still", {"project": p, "frame": fr, "out": out, "scale": _num(b.get("scale"), 0.5, 0.1, 1)}, timeout=120)
            if r.get("error"):
                return jsonify(r), 500
        return send_file(out, mimetype="image/jpeg")

    @app.route("/api/motion/words", methods=["POST"])
    def mo_words():
        """Whisper word timings for a library/ref audio or video → captions / lyrics scenes."""
        s = str((request.get_json(silent=True) or {}).get("src") or "")
        kind, _, name = s.partition(":")
        ok = hk["my_file"](name) if kind == "lib" else hk["my_ref"](name) if kind == "ref" else False
        path = core.in_dir(core.LIB if kind == "lib" else core.REFS, name) if ok else None
        if not path or not os.path.isfile(path):
            return jsonify({"error": "pick an audio or video from your library"}), 400
        try:
            return jsonify({"words": hk["words"](path)})
        except Exception as e:
            return jsonify({"error": str(e)[:300]}), 500

    @app.route("/api/motion/ai", methods=["POST"])
    def mo_ai():
        """Request → clips. mode=project (whole timeline) | scene (one clip for the inspector) | props (rewrite one clip)."""
        b = request.get_json(silent=True) or {}
        ask = str(b.get("ask") or "").strip()[:3000]
        if not ask:
            return jsonify({"error": "say what you want"}), 400
        media = hk["lib_list"]()[:60]
        ctx = "AVAILABLE MEDIA:\n" + "\n".join("- %s (%s) %s" % (m["name"], m.get("kind"), (m.get("prompt") or "")[:80]) for m in media)
        cur = b.get("project")
        if isinstance(cur, dict) and cur.get("tracks"):
            ctx += "\nCURRENT PROJECT (%ss, %sx%s): %s" % (round(duration(cur), 1), cur.get("w"), cur.get("h"),
                                                           json.dumps(cur.get("tracks"))[:6000])
        if b.get("clip"):
            ctx += "\nSELECTED CLIP: " + json.dumps(b["clip"])[:3000]
        mode = b.get("mode") or "project"
        want = {"project": "Return the FULL new project JSON (it replaces the timeline; keep what the user didn't ask to change).",
                "append": "Return a project JSON holding ONLY the new clips; start times relative to 0 (they're inserted at the playhead).",
                "props": "Return {\"tracks\":[{\"kind\":..., \"clips\":[<the selected clip, rewritten>]}]}."}.get(mode, "")
        secs = _num(b.get("secs"), 0, 0, 7200)
        if secs:
            want += " Target length: %d seconds." % secs
        try:
            raw = hk["ask"]("%s\n\n%s\n\nREQUEST: %s" % (ctx, want, ask), ai_system())
        except Exception as e:
            return jsonify({"error": "the writer failed: %s" % str(e)[:200]}), 500
        s = raw if isinstance(raw, dict) else None
        if s is None:
            m = re.search(r"\{.*\}", str(raw or ""), re.S)
            try:
                s = json.loads(m.group(0)) if m else {}
            except Exception:
                s = {}
        if not s.get("tracks"):
            return jsonify({"error": "the writer returned no scenes — try rephrasing", "raw": str(raw)[:500]}), 500
        return jsonify(clean(dict(s, w=(cur or {}).get("w") or 1280, h=(cur or {}).get("h") or 720, fps=(cur or {}).get("fps") or 30)))


# ── builders other modules use (Series, Producer, Editor, MUSE tools) ─────────────────────────────────────────────
def scene(kind, dur, props=None, start=0.0, trans=None, out=None):
    c = {"id": uuid.uuid4().hex[:8], "type": kind, "start": round(start, 3), "dur": round(dur, 3), "props": props or {}}
    if trans:
        c["trans"] = trans
    if out:
        c["out"] = out
    return c


def project(name, w=1280, h=720, fps=30, tracks=None, palette=None, font=None, session=""):
    return {"name": name, "w": w, "h": h, "fps": fps, "tracks": tracks or [], "palette": palette, "font": font, "session": session}


def render_sync(p, out, codec="mp4", crf=20, timeout=3600):
    """Blocking render for background pipelines (Series assemble, Producer). Returns out path."""
    p = clean(p)
    jid = "s" + uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "status": "running", "stage": "starting", "pct": 0.0, "user": "_pipeline", "started": time.time()}
    render(jid, p, out, codec, crf, lambda j: None)
    j = JOBS.pop(jid, {})
    if j.get("status") != "done":
        raise RuntimeError("motion render failed: %s" % (j.get("error") or j.get("status")))
    return out
