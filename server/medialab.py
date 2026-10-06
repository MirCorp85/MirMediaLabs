"""MIR MEDIA LABS — standalone generative media studio.

    python medialab.py            → http://127.0.0.1:5400  (LAN: http://<pc-ip>:5400)

Four local models through ComfyUI: MiniMax H3 (video), MiniMax Music 3.0, Qwen-Image 2.1,
ACE-Step 1.5. Its own console, ⚙ parameters per model, 📎 references (audio/image/text/video),
its own library (data/library), its own access key and its own update server (/updates).
Completely separate from MirOS: no MirOS imports, no calls to the MirOS dashboard, no access
to MirOS files — see core.py for the sandbox and /api/isolation for the live audit.
"""
import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import socket
import sys
import threading
import time
from urllib.parse import quote

from flask import Flask, Response, abort, g, jsonify, redirect, request, send_file, send_from_directory

import cloud
import comfy
import core
import params
import pcupdate
import renderers
import llm
import skills
import loras
import users
import events
import perf
import console
import tts
import router
import watermark

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024
UPLOAD_MAX_MB = 500
users.load()
events.load()
console.start()

# -- access gate: every person has their own key (users.py). Loopback = the owner on this PC. --
OPEN_PATHS = ("/api/ping", "/privacy", "/sw.js", "/static/apple-touch-icon.png", "/static/icon-192.png", "/static/icon-512.png")
LOOPBACK_ONLY = ("/api/admin/presence",)       # read by the owner's MirOS ACCESS panel on this PC


def _loopback():
    return request.remote_addr in ("127.0.0.1", "::1")


@app.before_request
def gate():
    if request.path in OPEN_PATHS:
        return None
    if request.path.startswith("/updates/pc/"):     # PC update channel: signed files + channel token
        return None if pcupdate.publisher_ok(request) else (jsonify({"error": "forbidden"}), 403)
    if request.path in LOOPBACK_ONLY:
        return None if _loopback() else (jsonify({"error": "local only"}), 403)
    if not REMOTE["on"] and not _loopback():        # the host paused remote access
        if request.path.startswith(("/api/", "/media/", "/thumb/", "/refs/", "/updates/")):
            return jsonify({"error": "the host has paused remote access to this Media Lab"}), 503
        return Response(PAUSED_HTML, mimetype="text/html", status=503)
    # an invite link's ?key= wins over a saved cookie: a phone that still holds an old/replaced key
    # must be signed in by a fresh invite, not bounced to the key page
    supplied = request.args.get("key") or request.headers.get("X-MML-Key") or request.cookies.get("mml_key")
    supplied = (supplied or "").strip() or None     # pasted keys often carry a space or line break
    ip = request.remote_addr or "?"
    u = users.owner() if _loopback() else users.by_key(supplied)   # this PC is always the host, whatever key it holds
    if u and not _loopback():
        _clear_fails(ip)                            # a right key always gets in and lifts the lockout
    if not u and not _loopback():
        if _locked_out(ip):
            return jsonify({"error": "too many wrong keys - try again in 15 minutes"}), 429
        if supplied:
            _note_fail(ip, supplied)
    if not u:
        if request.path.startswith(("/api/", "/media/", "/thumb/", "/refs/", "/updates/")):
            return jsonify({"error": "unauthorized - Media Lab access key required"}), 401
        msg = ("That key didn't work. Check it and try again &mdash; or ask the lab owner for a fresh invite."
               if request.args.get("key") else "")
        resp = Response(LOGIN_HTML.replace("{MSG}", msg), mimetype="text/html", status=401)
        if request.cookies.get("mml_key"):
            resp.delete_cookie("mml_key")           # drop a dead saved key so the next invite / typed key starts clean
        return resp
    g.user = u
    ua = request.headers.get("User-Agent", "")
    handoff = (request.args.get("key") and request.method == "GET" and request.path == "/" and "Android" in ua
               and "MirMediaLabs" not in ua and not request.args.get("web"))
    if not _loopback() and u.get("role") != "owner" and not handoff \
            and (request.path == "/" or request.path.startswith(("/api/", "/media/", "/thumb/", "/refs/"))):
        dev = _device_id()                          # ONE device per person's key (the owner's master key: any number)
        why = users.bind_device(u, dev, users.device_of(ua)) if dev else \
            "update MIR MEDIA LABS (menu → Check for updates) — this version can't sign in any more"
        if why:
            if request.path.startswith(("/api/", "/media/", "/thumb/", "/refs/")):
                return jsonify({"error": why, "device_locked": True}), 403
            return Response(LOGIN_HTML.replace("{MSG}", why), mimetype="text/html", status=403)
    users.touch(u, request.remote_addr, ua, request.path)
    if request.args.get("key") and request.method == "GET" and request.path == "/":
        if handoff:
            resp = Response(_android_handoff(supplied), mimetype="text/html")   # open the installed app
        else:
            ios = any(t in ua for t in ("iPhone", "iPad", "iPod"))
            resp = redirect(request.path + ("?joined=1" if ios else ""))   # iPhone: lab shows "Add to Home Screen"
        resp.set_cookie("mml_key", supplied, max_age=3600 * 24 * 365, httponly=True, samesite="Lax")
        return resp
    return None


_DEV_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _device_id():
    """Which device is calling: the app sends X-MML-Device (and &dev= on media URLs); a browser gets a
    random mml_dev cookie on its first visit. None = an app too old to say (it must update)."""
    for v in (request.headers.get("X-MML-Device"), request.args.get("dev"), request.cookies.get("mml_dev")):
        if v and _DEV_RE.match(v):
            return v
    if "MirMediaLabs-Android" in request.headers.get("User-Agent", ""):
        return None
    g.new_dev = "b" + secrets.token_urlsafe(18)
    return g.new_dev


@app.after_request
def _set_device_cookie(resp):
    if getattr(g, "new_dev", None):
        resp.set_cookie("mml_dev", g.new_dev, max_age=3600 * 24 * 365 * 5, httponly=True, samesite="Lax")
    return resp


def _android_handoff(key):
    """Invite opened on an Android phone: hand it to the MIR MEDIA LABS app (mirmedialabs://join, which the app
    already parses); without the app, Chrome follows browser_fallback_url and the web lab opens signed in."""
    from urllib.parse import quote
    base = request.host_url.rstrip("/")
    away = core.prefs().get("away_url") or ""
    q = "url=" + quote(base, safe="") + "&key=" + quote(key, safe="") + ("&away=" + quote(away, safe="") if away else "")
    web = base + "/?web=1&key=" + quote(key, safe="")
    intent = "intent://join?" + q + "#Intent;scheme=mirmedialabs;package=com.mirmedialabs.app;S.browser_fallback_url=" + quote(web, safe="") + ";end"
    app = "mirmedialabs://join?" + q
    esc = lambda x: x.replace("&", "&amp;").replace('"', "&quot;")
    return (HANDOFF_HTML.replace("{INTENT}", esc(intent)).replace("{APP}", esc(app)).replace("{WEB}", esc(web))
            .replace("{GET}", esc(core.CREATOR.get("github", "") + "/releases/latest")))


HANDOFF_HTML = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>MIR MEDIA LABS</title>
<body style="background:#0d0806;color:#fff1e2;font:16px/1.5 system-ui,sans-serif;margin:0;min-height:100vh;display:grid;place-items:center;text-align:center;padding:24px;box-sizing:border-box">
<div style="max-width:360px;width:100%">
<img src="/static/icon-192.png" width="88" height="88" style="border-radius:22px" alt="">
<div style="letter-spacing:.3em;font-weight:800;color:#ff5a1f;margin:14px 0 4px">MIR MEDIA LABS</div>
<p style="color:#c4a58c;margin:0 0 22px">You're invited to a lab. Opening it in the app&hellip;</p>
<a href="{INTENT}" style="display:block;padding:15px;border-radius:14px;background:#ff5a1f;color:#160a04;font-weight:700;text-decoration:none">Open in the app</a>
<a href="{WEB}" style="display:block;padding:14px;border-radius:14px;border:1px solid rgba(255,140,70,.4);color:#fff1e2;text-decoration:none;margin-top:10px">Continue in the browser</a>
<p style="color:#7d6352;font-size:14px;margin-top:22px">No app yet? <a href="{GET}" style="color:#ffc21a">Get MIR MEDIA LABS for Android</a>, then scan the invite again.</p>
</div>
<script>setTimeout(function(){location.href="{INTENT}".replace(/&amp;/g,"&")},300)</script>
</body>"""


# brute-force guard: 10 DIFFERENT wrong keys from one address in 15 min -> lockout. Counting distinct keys
# (not requests) matters: an app holding one stale key polls many endpoints and must not lock itself out.
_FAILS = {}                                         # ip -> {sha256(key): last_seen}
_FAIL_LOCK = threading.Lock()


def _note_fail(ip, key):
    import hashlib
    h = hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()
    with _FAIL_LOCK:
        now = time.time()
        d = {k: t for k, t in _FAILS.get(ip, {}).items() if now - t < 900}
        d[h] = now
        _FAILS[ip] = d


def _locked_out(ip):
    with _FAIL_LOCK:
        now = time.time()
        return sum(1 for t in _FAILS.get(ip, {}).values() if now - t < 900) >= 10


def _clear_fails(ip):
    with _FAIL_LOCK:
        _FAILS.pop(ip, None)


REMOTE = {"on": core.prefs().get("remote_access", True) is not False}
PAUSED_HTML = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>MIR MEDIA LABS</title><body style="background:#07070b;color:#e9e7f5;font:15px system-ui;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center"><div style="letter-spacing:.3em;font-weight:800;margin-bottom:14px">MIR MEDIA LABS</div>
<p style="color:#aaa">The host has paused remote access. Try again later.</p></div>"""


def _host():
    """The PC running the server (and its GPU) — the only place access is managed from."""
    return _loopback()


def uid():
    return g.user["id"]


def is_owner():
    return g.user.get("role") == "owner"


def mine(owner_id):
    """The host PC sees everything; everyone else only what they created (legacy items belong to the owner)."""
    return _host() or (owner_id or "owner") == uid()


LOGIN_HTML = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>MIR MEDIA LABS</title><body style="background:#07070b;color:#e9e7f5;font:15px system-ui;display:grid;place-items:center;height:100vh;margin:0">
<form onsubmit="location='/?key='+encodeURIComponent(k.value.trim());return false" style="text-align:center">
<div style="letter-spacing:.3em;font-weight:800;margin-bottom:14px">MIR MEDIA LABS</div>
<input id=k placeholder="access key" style="padding:12px;border-radius:10px;border:1px solid #333;background:#111;color:#fff;width:260px">
<button style="display:block;margin:10px auto 0;padding:10px 22px;border-radius:10px;border:0;background:#ff5a1f;color:#160a04;font-weight:700">Sign in</button>
<p style="color:#ff6b6b;font-size:13px;max-width:280px;margin:12px auto 0">{MSG}</p>
<p style="color:#888;font-size:12px">Ask the owner of this Media Lab for your personal access key.</p></form>"""


@app.after_request
def no_cache_api(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith("/api/") or request.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ── jobs: one GPU worker, FIFO, persisted ──────────────────────────────────
JOBS = {}
ORDER = []
Q = queue.Queue()
_JLOCK = threading.Lock()
PUBLIC = ("id", "model", "prompt", "refs", "loras", "status", "stage", "log", "output", "files", "created", "started",
          "finished", "error", "params", "user", "input", "skill", "pipeline", "steps", "step", "route", "lora_sel",
          "loras_skipped", "plan", "pipeline_id", "knobs", "progress", "brain")


def _persist():
    with _JLOCK:
        keep = ORDER[-300:]
        core.save_json(core.JOBS_FILE, [{k: JOBS[i].get(k) for k in PUBLIC} for i in keep if i in JOBS])


def _load_jobs():
    for j in core.load_json(core.JOBS_FILE, []):
        if j.get("status") == "running":
            j["status"], j["error"] = "error", "server restarted during the render"
        JOBS[j["id"]] = j
        ORDER.append(j["id"])
        if j.get("status") == "queued":
            Q.put(j["id"])


def public(j):
    d = {k: j.get(k) for k in PUBLIC}
    if _host():   # host PC: label whose request this is
        u = users.by_id(j.get("user") or "owner")
        d["user_name"] = u["name"] if u else (j.get("user") or "owner")
        d["mine"] = (j.get("user") or "owner") == uid()
    return d


def _what(model):
    """'a song request', 'an image request' — role words, never engine names."""
    lbl = next((v["label"] for v in skills.ROLES.values() if v["model"] == model), "media").lower()
    return ("an " if lbl[:1] in "aeiou" else "a ") + lbl + " request"


def _lora_note(job, skipped, what):
    """Say which picked LoRAs this request can't use (wrong kind of model) instead of dropping them silently."""
    if not skipped:
        return
    names = [x["name"] for x in skipped]
    job["loras_skipped"] = sorted(set((job.get("loras_skipped") or []) + names))
    for x in skipped:
        job["log"] = (job.get("log") or "") + "LoRA not used: %s (%s) — this is %s\n" % (x["name"], x["why"], what)


def _lora_apply(job, model, what):
    """Pick the job's LoRAs for the engine that renders now (pipelines change engine per step) + add trigger words."""
    skipped = []
    picked = loras.pick(model, job.get("lora_sel"), skipped)
    _lora_note(job, skipped, what)
    job["loras"] = picked
    trig = [t for l in picked for t in l["triggers"] if t and t.lower() not in (job.get("prompt") or "").lower()]
    if trig:
        job["prompt"] = ((job["prompt"] + ", ") if job.get("prompt") else "") + ", ".join(trig[:8])
    if picked:
        job["log"] = (job.get("log") or "") + "LoRA applied: %s\n" % ", ".join(
            "%s · %.2f" % (l["name"], l["strength"]) for l in picked)
    return picked


def _run_once(job):
    for attempt in (1, 2):
        try:
            return renderers.RUNNERS[job["model"]](job)
        except comfy.EngineLost:
            if attempt == 2 or job.get("_cancel"):
                raise
            renderers.log(job, "GPU engine went away — restarting it and retrying once …")
            time.sleep(5)
            comfy.start(wait=True)


def _ref_seconds(name):
    p = core.in_dir(core.REFS, name)
    return renderers.media_seconds(p) if p else 0


def _run_pipeline(job):
    """Follow the manual inside this ONE job — the job's refs always end as what the person attached
    (also after an error / cancel), so "Again" re-attaches the right files."""
    base = list(job.get("refs") or [])
    try:
        return _pipeline_steps(job, base)
    finally:
        job["refs"] = base


def _pipeline_steps(job, base):
    """Each step gets its own ordered inputs (the person's attachments and/or earlier outputs), MUSE's prompt
    for that step (else the template), the knobs, and what earlier steps carry forward."""
    outs, files, texts = [], [], []
    owner = job.get("user") or "owner"
    man = skills.pipeline(job.get("pipeline_id") or "") or {"steps": job["steps"]}
    knobs = job.get("knobs") or {}
    plan = job.get("plan") or []
    meta = {}                                    # carried forward: style · lyrics · bpm · key (latest step wins)
    n = len(job["steps"])
    for i, st in enumerate(job["steps"], 1):
        if job.get("_cancel"):
            raise comfy.Cancelled()
        row = plan[i - 1] if i - 1 < len(plan) else {}
        mdl = skills.model_for(st["role"])        # role → today's engine for that role
        refs = skills.resolve_inputs(st, base, outs, core.kind_of, _ref_seconds)
        has_img = i == 1 and any(core.kind_of(r) == "image" for r in refs)
        prompt = (row.get("prompt") or "").strip() or skills.fill(st["tpl"], job.get("input"), has_img)
        over, add = skills.knob_effects(man, knobs, i, mdl)
        pre, post = skills.carry_text(st, meta, mdl)
        prompt = core.clean_ws(" ".join(x for x in (pre + ("." if pre and prompt else ""), prompt, add, st.get("add", "")) if x)) + post
        po = skills.overrides(st, mdl)
        if st.get("mode"):
            po["mode"] = st["mode"]
        po.update(over)
        if st.get("mode") == "voice" and sum(1 for r in refs if core.kind_of(r) == "audio") < 2:
            raise RuntimeError(skills.missing(man, [core.kind_of(r) for r in base]) or
                               "the voice swap needs the song AND a voice recording")
        job.update(model=mdl, step="%d/%d" % (i, n), refs=refs, prompt=prompt,
                   params=params.get(mdl, override=po, uid=owner))
        if row:
            row.update(status="running", inputs=list(refs), used=prompt[:1500])
        renderers.log(job, "▶ step %d/%d · %s%s" % (i, n, skills.step_label(st),
                                                   (" · inputs: " + ", ".join(refs)) if refs else ""))
        _persist()
        if job.get("lora_sel"):
            _lora_apply(job, mdl, "a %s step" % skills.ROLES[st["role"]]["label"].lower())
        try:
            res = _run_once(job)
        except Exception:
            if row:
                row["status"] = "error"
            raise
        files += res["files"]
        meta.update({k: v for k, v in (res.get("meta") or {}).items() if v})
        if st["role"] == "text" and (res.get("text") or "").strip():      # a writing step hands its lyrics forward
            meta["lyrics"] = llm.sanitize_lyrics(res["text"]) or res["text"].strip()
        texts.append("── step %d · %s ──" % (i, skills.step_label(st)) + chr(10) + (res.get("text") or ""))
        made = []
        for fn in res["files"]:
            src = core.in_dir(core.LIB, fn)
            if src:
                stem, ext = os.path.splitext(fn)
                ref = _store_ref(stem, ext.lower(), owner)
                shutil.copy2(src, core.safe_path(os.path.join(core.REFS, ref)))
                made.append(ref)
        outs.append(made)
        if row:
            row.update(status="done", files=list(res["files"]))
        _persist()
    return {"files": files, "text": chr(10).join(texts)}


def worker():
    while True:
        jid = Q.get()
        job = JOBS.get(jid)
        if not job or job.get("status") != "queued":
            continue
        job["status"], job["started"] = "running", time.time()
        _persist()
        console.set_current(job["id"])
        console.emit("LAB", "worker picked up the job · GPU is yours", job)
        brain = cloud.for_job(job)                   # owner only: Claude / GPT as MUSE, Director + prompt writer
        cloud.activate(brain)
        if brain:
            job["brain"] = cloud.label_of(brain)
            console.emit("MUSE", "cloud brain · %s" % job["brain"], job)
        elif (job.get("user") or "owner") == "owner" and cloud.brain()["provider"] != "local" and cloud.spent() >= cloud.cap():
            console.emit("MUSE", "cloud brain paused — this month's $%.0f cap is reached; using the local engine" % cloud.cap(), job, "warn")
        try:
            if job.get("model") == "auto":
                _route(job)
                _persist()
            res = _run_pipeline(job) if job.get("steps") else _run_once(job)
            if watermark.enabled() and res["files"]:
                job["stage"] = "watermarking"
                if watermark.apply(res["files"], lambda m: console.emit("LAB", m, job, "warn")):
                    console.emit("LAB", "watermarked · " + watermark.text(), job)
            job["files"], job["output"] = res["files"], res["text"]
            job["status"] = "done"
        except comfy.Cancelled:
            job["status"], job["error"] = "cancelled", "cancelled"
        except Exception as e:
            job["status"], job["error"] = "error", str(e)[:1500]
        finally:
            cloud.activate(None)
            job["finished"] = time.time()
            console.emit("LAB", {"done": "finished · saved to the library", "cancelled": "cancelled"}.get(job["status"], "stopped · " + str(job.get("error", ""))[:90]), job)
            console.set_current(None)
            job["stage"] = ""
            job.pop("_cancel", None)
            _persist()
            events.job_event(job)          # phone / TV notification (long-poll feed)


# ── MUSE Director: Auto mode decides the tool for each message ─────────────
# If the LoRAs you picked can't load on the engine MUSE chose, use the sibling role whose engine can
# (songs → music: the LoRA library's music LoRAs are for the music engine; the song engine takes none).
_LORA_ALT = {"song": "music"}

def _recent(owner, limit=4):
    """This person's last finished turns, for follow-ups like 'now animate it'."""
    with _JLOCK:
        js = [JOBS[i] for i in ORDER if i in JOBS and (JOBS[i].get("user") or "owner") == owner
              and JOBS[i].get("status") == "done"]
    out = []
    for j in js[-limit:]:
        tool = (j.get("route") or {}).get("label") or params.MODELS.get(j.get("model"), {}).get("label", j.get("model"))
        made = ", ".join(sorted({core.kind_of(f) or "file" for f in j.get("files") or []}))
        out.append({"q": j.get("input") or j.get("prompt") or "", "tool": tool, "made": made, "files": j.get("files") or []})
    return out


def _attach_previous(job, recent, want_kind=None):
    """Copy the newest earlier result into this job's references (the Director said 'use_previous')."""
    for h in reversed(recent):
        for f in h["files"]:
            if want_kind and core.kind_of(f) != want_kind:
                continue
            p = core.in_dir(core.LIB, f)
            if not p:
                continue
            stem, ext = os.path.splitext(os.path.basename(p))
            ref = _store_ref(stem, ext.lower(), owner=job.get("user") or "owner")
            shutil.copy2(p, core.safe_path(os.path.join(core.REFS, ref)))
            job["refs"] = list(job.get("refs") or []) + [ref]
            return ref
    return None


def _route(job):
    owner = job.get("user") or "owner"
    job["stage"] = "MUSE is deciding …"
    renderers.log(job, "MUSE is reading your message …")
    recent = _recent(owner)
    d = router.decide(job.get("input") or "", job.get("refs"), recent, model=llm.MODEL_TAG)
    console.emit("MUSE", "picked %s%s%s" % (d.get("pipeline") or d.get("skill") or d.get("role") or d.get("action"),
                 " · " + d["why"] if d.get("why") else "", " (%d ms)" % d["ms"] if d.get("ms") else " (rules)"), job)
    alt = _LORA_ALT.get(d.get("role")) if d["action"] == "render" else None
    sel = job.get("lora_sel")
    if alt and sel and not loras.pick(skills.model_for(d["role"]), sel) and loras.pick(skills.model_for(alt), sel):
        who0 = users.by_id(owner)
        if not who0 or not users.can_use(who0, skills.model_for(alt)):
            d["why"] = ((d.get("why") or "") + "; " if d.get("why") else "") + "%s instead, so your LoRA applies" % skills.ROLES[alt]["label"]
            d["role"] = alt
    if d.get("use_previous") and d["action"] != "chat":
        want = "image" if d.get("role") == "video" or d.get("skill") == "animate" else None
        _attach_previous(job, recent, want) or _attach_previous(job, recent)
    who = users.by_id(owner)
    if who:
        picks = [skills.model_for(st["role"]) for st in skills.pipeline(d["pipeline"])["steps"]] if d["action"] == "pipeline" \
            else ["llama"] if d["action"] == "chat" or (d["action"] == "skill" and d.get("role") == "text") \
            else [skills.model_for(d["role"])]
        deny = next((users.can_use(who, m) for m in picks if users.can_use(who, m)), None)
        if deny:
            raise RuntimeError("MUSE wanted %s, but %s" % (router.label(d), deny))
    lbl = router.label(d)
    job["route"] = {"label": lbl, "why": d.get("why", ""), "by": d.get("by", "rules"), "action": d["action"]}
    renderers.log(job, "MUSE → %s%s" % (lbl, (" — " + d["why"]) if d.get("why") else ""))
    prompt, refs = d.get("prompt") or job.get("input") or "", job.get("refs") or []
    if d["action"] == "chat" or (d["action"] == "skill" and d.get("role") == "text"):
        job["model"] = "llama"
        job["params"] = params.get("llama", uid=owner)
        if d["action"] == "skill":
            sk = skills.skill(d["skill"])
            job.update(skill=sk["name"], prompt=skills.fill(sk["tpl"], prompt),
                       params=params.get("llama", override=skills.overrides(sk, "llama"), uid=owner))
        else:
            job["prompt"] = prompt
        with _JLOCK:
            hist = [JOBS[i] for i in ORDER if i in JOBS and JOBS[i].get("model") == "llama" and JOBS[i].get("status") == "done"
                    and (JOBS[i].get("user") or "owner") == owner and JOBS[i].get("output") and JOBS[i] is not job]
        job["history"] = [{"q": h.get("input") or h.get("prompt") or "", "a": h["output"][:6000]} for h in hist[-12:]]
        return
    if d["action"] == "pipeline":
        pl = skills.pipeline(d["pipeline"])
        kv = dict(skills.knob_values(pl, d.get("knobs")), **(job.get("knobs") or {}))   # the person's dials beat MUSE's
        job.update(model=skills.model_for(pl["steps"][0]["role"]), pipeline=pl["name"], pipeline_id=pl["id"],
                   steps=pl["steps"], step="0/%d" % len(pl["steps"]), input=prompt,
                   plan=skills.plan_for(pl, d.get("steps")), knobs=kv)
        for row in job["plan"]:
            renderers.log(job, "  %d. %s — %s" % (row["n"], row["label"], row["does"]))
        return
    has_img = any(core.kind_of(r) == "image" for r in refs)
    if d["action"] == "skill":
        sk = skills.skill(d["skill"])
        model = skills.model_for(sk["role"])
        kv = skills.knob_values(sk, d.get("knobs"))
        over, add = skills.knob_effects(sk, kv, None, model)
        filled = skills.fill(sk["tpl"], prompt, has_img)
        job.update(model=model, skill=sk["name"], prompt=(filled + " " + add).strip() if add else filled, knobs=kv,
                   params=params.get(model, override=dict(skills.overrides(sk, model), **over), uid=owner))
    else:
        model = skills.model_for(d["role"])
        p = params.get(model, uid=owner)
        modes = next((f.get("opts") for f in params.MODELS.get(model, {}).get("fields", []) if f.get("k") == "mode"), [])
        if "mode" in p and any(o[0] == "auto" for o in modes):
            p["mode"] = "auto"      # Auto mode: the attachments decide (picture → edit, none → generate), not a saved manual mode
        job.update(model=model, prompt=prompt, params=p)
    if job.get("lora_sel"):
        _lora_apply(job, model, _what(model))


# ── pages + static ─────────────────────────────────────────────────────────
_MIME = {".js": "application/javascript", ".css": "text/css", ".html": "text/html", ".json": "application/json",
         ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".ico": "image/x-icon"}


def _static(fn):
    if core.ASSETS is None:                        # dev copy: files on disk
        return send_from_directory(core.STATIC, fn)
    data = core.asset(fn)                          # compiled build: embedded in the binary
    if data is None:
        abort(404)
    ext = os.path.splitext(fn)[1].lower()
    resp = Response(data, mimetype=_MIME.get(ext) or mimetypes.guess_type(fn)[0] or "application/octet-stream")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/")
def home():
    return _static("index.html")


# ── iPhone / home-screen web app (PWA) ──────────────────────────────────────
# iOS gives a home-screen app its OWN cookie jar, so the Safari login does not carry over.
# The manifest is served per user with their key in start_url: the installed app's first
# launch hits /?key=… and sets its own cookie.
@app.route("/manifest.webmanifest")
def pwa_manifest():
    start = "/?key=" + g.user["key"] if g.user.get("key") else "/"
    icons = [{"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
             {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]
    resp = jsonify({"name": core.APP_NAME, "short_name": "Media Labs", "id": "/", "start_url": start, "scope": "/",
                    "display": "standalone", "background_color": "#0d0806", "theme_color": "#0d0806", "icons": icons})
    resp.mimetype = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-store"
    return resp


SW_JS = """const OFF='<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><body style="background:#0d0806;color:#fff1e2;font:15px system-ui;display:grid;place-items:center;height:100vh;margin:0;text-align:center"><div><b style="letter-spacing:.3em">MIR MEDIA LABS</b><p>The lab is unreachable right now.<br>Check your connection and try again.</p><button onclick="location.reload()">Retry</button></div>';
self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.mode==='navigate')e.respondWith(fetch(e.request).catch(()=>new Response(OFF,{headers:{'Content-Type':'text/html'}})));});
"""


@app.route("/sw.js")
def pwa_sw():
    resp = Response(SW_JS, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


PRIVACY_HTML = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>MIR MEDIA LABS - Privacy policy</title>
<body style="background:#0d0806;color:#fff1e2;font:16px/1.65 system-ui,sans-serif;max-width:720px;margin:0 auto;padding:28px 18px">
<h1 style="font-size:24px">MIR MEDIA LABS - Privacy policy</h1><p style="color:#c4a58c">Last updated: October 5, 2026 &middot; MirCorp</p>
<h2 style="font-size:18px">The short version</h2>
<p>MIR MEDIA LABS is a remote control for a media studio that runs on <b>your own computer</b> (your "lab"). The app talks only to the lab address you enter. MirCorp runs no servers for the app and receives none of your prompts, files or creations.</p>
<h2 style="font-size:18px">What the app handles</h2>
<ul><li><b>Lab address and access key</b> - stored on your phone so it can connect to your lab.</li>
<li><b>Prompts, attachments and generated media</b> - sent to and stored on your lab only, to create and show your results.</li>
<li><b>Content reports</b> - if you report a result, the report (file name, reason, time) is saved on your lab for its owner.</li>
<li><b>Camera</b> - used only to scan an invite QR code; no pictures are stored or sent.</li>
<li><b>Notifications</b> - delivered directly from your lab, without Google or third-party push services.</li></ul>
<h2 style="font-size:18px">What the app does not do</h2>
<ul><li>No accounts with MirCorp, no advertising, no analytics or tracking SDKs.</li>
<li>No selling or sharing of data with third parties.</li></ul>
<p>Bug reports and feedback are sent only if you choose to email them, and include the device details shown before you send.</p>
<h2 style="font-size:18px">Your lab</h2>
<p>Whoever runs a lab controls the data on it. If someone else invited you to their lab, they can see the jobs you submit and can remove your access. Ask them to delete your creations, or delete them yourself in the app.</p>
<h2 style="font-size:18px">Children</h2><p>The app is not directed at children under 13.</p>
<h2 style="font-size:18px">Contact</h2><p>MirCorp - mirmedialabs@gmail.com</p></body>"""


@app.route("/privacy")
def privacy():
    return Response(PRIVACY_HTML, mimetype="text/html")


@app.route("/static/<path:fn>")
def static_files(fn):
    return _static(fn)


@app.route("/api/ping")
def ping():
    return jsonify({"app": core.APP_NAME, "version": core.APP_VERSION, "features": ["events", "invite-away"]})


# ── notifications: long-poll feed for the phone / TV apps (events.py) ───────
@app.route("/api/events")
def events_feed():
    try:
        since = int(request.args.get("since", 0))
        wait = float(request.args.get("wait", 0))
    except ValueError:
        return jsonify({"error": "bad cursor"}), 400
    out, last = events.wait(uid(), since, wait)
    return jsonify({"events": out, "last": last})


@app.route("/api/events/test", methods=["POST"])
def events_test():
    ev = events.push(uid(), "notice", "Notifications are working",
                     "This is how MIR MEDIA LABS tells you a render is ready.", test=True)
    return jsonify({"ok": True, "id": ev["id"]})


# ── status ─────────────────────────────────────────────────────────────────
_STATUS = {"t": 0, "v": None}


def _refresh_status():
    try:
        tags = [m["name"] for m in core.requests.get(core.OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
        eng = {"up": True, "model": core.engine_model(), "available": tags}
    except Exception:
        eng = {"up": False, "model": core.prefs().get("engine_model") or core.DEFAULT_ENGINE, "available": []}
        core.ensure_ollama(wait=0)                  # self-heal: relaunch Ollama, status flips back on its own
    cs = comfy.status()
    cs.setdefault("models", {})["llama"] = llm.ready(eng.get("available")) if eng.get("up") else None
    _STATUS["v"] = {"comfy": cs, "engine": eng}
    _STATUS["t"] = time.time()


def _status_loop():
    while True:
        try:
            _refresh_status()
        except Exception:
            pass
        time.sleep(4)


@app.route("/api/status")
def status():
    if _STATUS["v"] is None:
        _refresh_status()
    r = next((JOBS[i] for i in reversed(ORDER) if JOBS.get(i, {}).get("status") == "running"), None)
    running = ({"id": r["id"], "model": r["model"], "mine": mine(r.get("user"))} if r else None)
    queued = [i for i in ORDER if JOBS.get(i, {}).get("status") == "queued"]
    return jsonify(dict(_STATUS["v"], app=core.APP_NAME, version=core.APP_VERSION, running=running, queued=queued,
                        creator=core.CREATOR, lan_ip=_lan_ip(), port=core.PORT,
                        apk=core.load_json(os.path.join(core.UPDATES, "version.json"), {})))


@app.route("/api/perf")
def api_perf():
    """Live PC performance for the desktop client card - this PC only (never exposed to the LAN)."""
    if not _loopback():
        return jsonify({"error": "local only"}), 403
    busy = any(JOBS.get(i, {}).get("status") == "running" for i in ORDER[-20:])
    return jsonify(perf.snapshot(busy))


@app.route("/api/engine/start", methods=["POST"])
def engine_start():
    try:
        if not os.path.isfile(comfy.COMFY_PY):
            raise RuntimeError("ComfyUI engine not found — run MirMediaLabs-Setup.exe (Repair)")
        # background: a frozen engine needs a ~60 s grace check before it's replaced
        threading.Thread(target=lambda: comfy.start(wait=False), daemon=True).start()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        if not is_owner():
            return jsonify({"error": "only the owner can change the prompt engine"}), 403
        m = str((request.get_json(silent=True) or {}).get("engine_model") or "").strip()
        if m:
            core.save_pref("engine_model", m[:120])
        _refresh_status()
    return jsonify({"engine_model": core.engine_model()})


# ── models + parameters ────────────────────────────────────────────────────
@app.route("/api/models")
def models():
    out = {"auto": AUTO_MODEL}                     # first = the default: MUSE Director picks the engine per message
    out.update({k: dict(v, values=params.get(k, uid=uid())) for k, v in params.MODELS.items()})
    return jsonify(out)


AUTO_MODEL = {"label": "AUTO · MUSE", "kind": "auto", "color": "#b48cff", "params": [], "values": {},
              "desc": "Just say what you want. MUSE reads it and picks the model, skill or pipeline, or simply answers.",
              "accepts": {"image": "pictures to edit or animate", "video": "motion reference", "audio": "tracks to remix",
                          "text": "lyrics, scripts, notes"}}


@app.route("/api/params/<model>", methods=["GET", "POST"])
def model_params(model):
    if model not in params.MODELS:
        abort(404)
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        if body.get("reset"):
            return jsonify(params.save(model, {}, uid()))
        return jsonify(params.save(model, body.get("values") or {}, uid()))
    return jsonify(params.get(model, uid=uid()))


# ── references (📎) ─────────────────────────────────────────────────────────
def _ref_info(name):
    p = os.path.join(core.REFS, name)
    info = {"name": name, "kind": core.kind_of(name), "url": "/refs/" + name, "size": os.path.getsize(p),
            "label": name.split("_", 2)[-1] if name.startswith("ref_") else name}
    if info["kind"] == "text":
        info["preview"] = core.read_text(p, 400)
    return info


REFS_INDEX = os.path.join(core.DATA, "refs_index.json")


def _store_ref(stem, ext, owner=None):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)[:40].strip("_") or "ref"
    name = "ref_%d_%s%s" % (int(time.time() * 1000), safe, ext)
    ix = core.load_json(REFS_INDEX, {})
    ix[name] = owner or uid()
    core.save_json(REFS_INDEX, ix)
    return name


def _my_ref(name):
    return mine(core.load_json(REFS_INDEX, {}).get(os.path.basename(str(name))))


# HEIC/HEIF (iPhone + Samsung camera default), AVIF, GIF, BMP, TIFF pictures → JPEG/PNG · 3GP / AVI / WMV clips → MP4 ·
# AMR / OPUS / WMA / AIFF audio → MP3. ffmpeg only (the compiled PC edition ships no Pillow).
_CONVERT = {".heic": ".jpg", ".heif": ".jpg", ".avif": ".jpg", ".gif": ".jpg", ".bmp": ".png", ".tif": ".png", ".tiff": ".png",
            ".3gp": ".mp4", ".3g2": ".mp4", ".avi": ".mp4", ".wmv": ".mp4", ".mpg": ".mp4", ".mpeg": ".mp4", ".ts": ".mp4",
            ".amr": ".mp3", ".opus": ".mp3", ".wma": ".mp3", ".aif": ".mp3", ".aiff": ".mp3", ".weba": ".mp3"}


def _upload_converted(f, stem, ext):
    to = _CONVERT[ext]
    tmp = core.safe_path(os.path.join(core.REFS, "_in_%d%s" % (int(time.time() * 1000), ext)))
    f.save(tmp)
    try:
        if os.path.getsize(tmp) > UPLOAD_MAX_MB * 1024 * 1024:
            return jsonify({"error": "file over %d MB" % UPLOAD_MAX_MB}), 400
        name = _store_ref(stem, to)
        out = core.safe_path(os.path.join(core.REFS, name))
        if to in (".jpg", ".png"):
            args = ["-i", tmp, "-frames:v", "1"] + (["-q:v", "2"] if to == ".jpg" else [])
        elif to == ".mp4":
            args = ["-i", tmp, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-c:a", "aac", "-movflags", "+faststart"]
        else:
            args = ["-i", tmp, "-vn", "-c:a", "libmp3lame", "-q:a", "2"]
        try:
            renderers.ffmpeg(args + [out], 600)
        except Exception:
            ix = core.load_json(REFS_INDEX, {})
            ix.pop(name, None)
            core.save_json(REFS_INDEX, ix)
            hint = " — on the phone set the camera to JPEG / 'Most Compatible'" if ext in (".heic", ".heif") else ""
            return jsonify({"error": "couldn't read that %s file%s" % (ext, hint)}), 400
        return jsonify(_ref_info(name))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no file"}), 400
    stem, ext = os.path.splitext(f.filename)
    ext = ext.lower()
    if ext in _CONVERT:                            # phone formats the engines can't load → converted on arrival
        return _upload_converted(f, stem, ext)
    if not core.kind_of("x" + ext):
        return jsonify({"error": "unsupported type %s — images png/jpg/webp · video mp4/mov/webm · audio mp3/wav/flac/ogg/m4a · text txt/md/lrc/srt" % ext}), 400
    name = _store_ref(stem, ext)
    path = core.safe_path(os.path.join(core.REFS, name))
    f.save(path)
    if os.path.getsize(path) > UPLOAD_MAX_MB * 1024 * 1024:
        os.remove(path)
        return jsonify({"error": "file over %d MB" % UPLOAD_MAX_MB}), 400
    return jsonify(_ref_info(name))


@app.route("/api/upload-text", methods=["POST"])
def upload_text():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty text"}), 400
    if str(body.get("name") or "") == "llama_text":     # MUSE reply → "Use as text ref": only what the engine should get
        text = llm.clean_for_ref(text) or text
    name = _store_ref(str(body.get("name") or "note"), ".txt")
    with open(core.safe_path(os.path.join(core.REFS, name)), "w", encoding="utf-8") as f:
        f.write(text[:50000])
    return jsonify(_ref_info(name))


@app.route("/refs/<path:name>")
def ref_file(name):
    p = core.in_dir(core.REFS, name)
    if not p or not _my_ref(name):
        abort(404)
    return send_file(p, conditional=True)


# ── generate + jobs ────────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    body = request.get_json(silent=True) or {}
    model = body.get("model")
    prompt = str(body.get("prompt") or "").strip()[:8000]
    sk_id, pl_id = body.get("skill"), body.get("pipeline")
    cmd = skills.parse(prompt)            # chat command book: /image … /skill product … /pipe musicvideo …
    if cmd and cmd.get("error"):
        return jsonify({"error": cmd["error"]}), 400
    if cmd:
        prompt = cmd["prompt"]
        model = cmd.get("model") or model
        sk_id, pl_id = cmd.get("skill") or sk_id, cmd.get("pipeline") or pl_id
    sk = skills.skill(sk_id) if sk_id else None
    pl = skills.pipeline(pl_id) if pl_id and not sk else None
    if (sk_id and not sk) or (pl_id and not pl and not sk):
        return jsonify({"error": "unknown skill / pipeline"}), 400
    if sk:
        model = skills.model_for(sk["role"])
    elif pl:
        model = skills.model_for(pl["steps"][0]["role"])
    if model not in renderers.RUNNERS and model != "auto":      # auto = MUSE Director decides in the worker
        return jsonify({"error": "unknown model"}), 400
    asked = [os.path.basename(str(n)) for n in (body.get("refs") or [])]
    if len(asked) > 16:
        return jsonify({"error": "too many attachments (%d) — 16 at most per request" % len(asked)}), 400
    refs = [n for n in asked if core.in_dir(core.REFS, n) and os.path.isfile(core.in_dir(core.REFS, n)) and _my_ref(n)]
    if len(refs) < len(asked):                     # never quietly render without what the person attached
        gone = [n.split("_", 2)[-1] for n in asked if n not in refs]
        return jsonify({"error": "attachment%s no longer on the lab: %s — remove %s and attach again"
                        % ("s" if len(gone) > 1 else "", ", ".join(gone[:4]), "them" if len(gone) > 1 else "it"), "missing": gone}), 400
    if not prompt and not refs:
        return jsonify({"error": "write a prompt or attach a reference"}), 400
    if sk and skills.missing(sk, [core.kind_of(r) for r in refs]):
        return jsonify({"error": skills.missing(sk, [core.kind_of(r) for r in refs])}), 400
    if pl and skills.missing(pl, [core.kind_of(r) for r in refs]):
        return jsonify({"error": skills.missing(pl, [core.kind_of(r) for r in refs])}), 400
    deny = users.over_limit(g.user) or (None if model == "auto" else users.can_use(g.user, model))
    if not deny and pl:
        deny = next((users.can_use(g.user, skills.model_for(st["role"])) for st in pl["steps"]
                     if users.can_use(g.user, skills.model_for(st["role"]))), None)
    if deny:
        return jsonify({"error": deny}), 403
    with _JLOCK:
        busy = next((JOBS[i] for i in ORDER if i in JOBS and JOBS[i].get("status") in ("queued", "running")
                     and (JOBS[i].get("user") or "owner") == uid()), None)
    if busy:   # one request at a time: the next can't start until the previous finishes
        return jsonify({"error": "the lab is still working on your previous request — wait for it to finish",
                        "busy": busy["id"]}), 409
    sel = [] if model == "llama" else loras.selection(body.get("loras"))     # LoRAs are for the media engines
    if body.get("params") and model != "auto":
        params.save(model, body["params"], uid())
    jid = "j%d" % int(time.time() * 1000)
    job = {"id": jid, "model": model, "prompt": prompt, "refs": refs, "status": "queued", "stage": "queued",
           "log": "", "output": "", "files": [], "created": time.time(),
           "params": {} if model == "auto" else params.get(model, uid=uid()),
           "user": uid(), "input": prompt, "loras": [], "lora_sel": sel}
    if sk:
        kv = skills.knob_values(sk, body.get("knobs"))
        over, add = skills.knob_effects(sk, kv, None, model)
        po = dict(skills.overrides(sk, model), **over)
        filled = skills.fill(sk["tpl"], prompt, sk["role"] != "text" and any(core.kind_of(r) == "image" for r in refs))
        job.update(skill=sk["name"], prompt=(filled + " " + add).strip() if add else filled, knobs=kv,
                   params=params.get(model, override=po, uid=uid()))
    elif pl:
        job.update(pipeline=pl["name"], pipeline_id=pl["id"], steps=pl["steps"], step="0/%d" % len(pl["steps"]),
                   plan=skills.plan_for(pl), knobs=skills.knob_values(pl, body.get("knobs")))
    if sel and model != "auto" and not pl:          # direct request: LoRAs + trigger words go in now (Auto: after MUSE picks)
        _lora_apply(job, model, _what(model))
    if model == "auto":
        job["who"] = {"name": g.user.get("name", ""), "role": g.user.get("role", "")}
    if model == "llama":
        with _JLOCK:
            hist = [JOBS[i] for i in ORDER if i in JOBS and JOBS[i].get("model") == "llama" and JOBS[i].get("status") == "done"
                    and (JOBS[i].get("user") or "owner") == uid() and JOBS[i].get("output")]
        job["history"] = [{"q": h.get("input") or h.get("prompt") or "", "a": h["output"][:6000]} for h in hist[-12:]]
        job["who"] = {"name": g.user.get("name", ""), "role": g.user.get("role", "")}
    users.count_job(g.user)
    with _JLOCK:
        JOBS[jid] = job
        ORDER.append(jid)
    _persist()
    Q.put(jid)
    return jsonify(public(job))


@app.route("/api/miros-prefs", methods=["GET", "POST"])
def font_prefs():
    """MIR FONTS pick for this Media Lab user (same API shape as MirOS so mirfont.js is copied verbatim)."""
    key, tkey = "font_" + uid(), "mltheme_" + uid()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        if body.get("key") == "font":
            fid = str((body.get("value") or {}).get("id") or "")[:20]
            core.save_pref(key, {"id": fid})
        elif body.get("key") == "voice":                # MUSE voice: {id, speed, on} - one pick for PC, phone and TV
            v = body.get("value") or {}
            core.save_pref("voice_" + uid(), {"id": v.get("id") if v.get("id") in tts.VOICES else tts.DEFAULT_VOICE,
                                              "speed": min(1.3, max(0.7, float(v.get("speed") or 1.0))), "on": v.get("on") is not False})
        elif body.get("key") == "mltheme":
            tid = str((body.get("value") or {}).get("id") or "")
            if tid in ("claude", "graphite", "obsidian", "midnight", "paper"):
                core.save_pref(tkey, {"id": tid})
    return jsonify({"font": core.prefs().get(key) or {"id": ""}, "mltheme": core.prefs().get(tkey) or {"id": ""},
                    "voice": core.prefs().get("voice_" + uid()) or {"id": tts.DEFAULT_VOICE, "speed": 1.0, "on": True}})



# ── LoRA SAMPLES (Civitai catalog → ComfyUI loras folder → applied per render) ──
@app.route("/api/loras/catalog")
def loras_catalog():
    try:
        return jsonify(loras.catalog(request.args.get("role", "video"), request.args.get("q", "")[:80],
                                     request.args.get("sort", "popular"), request.args.get("cursor") or None))
    except Exception as e:
        return jsonify({"error": "LoRA catalog unavailable: %s" % e, "items": []}), 502


@app.route("/api/loras/installed")
def loras_installed():
    return jsonify({"items": loras.installed(), "downloads": loras.DL, "roles": {k: v["label"] for k, v in loras.ROLES.items()}})


@app.route("/api/loras/install", methods=["POST"])
def loras_install():
    if not is_owner():
        return jsonify({"error": "only the owner can install LoRAs"}), 403
    item = (request.get_json(silent=True) or {}).get("item") or {}
    try:
        key = loras.install(item, core.prefs().get("civitai_token", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"key": key})


@app.route("/api/loras/remove", methods=["POST"])
def loras_remove():
    if not is_owner():
        return jsonify({"error": "only the owner can remove LoRAs"}), 403
    try:
        loras.remove((request.get_json(silent=True) or {}).get("file"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


# ── cloud brain (owner, host PC only): Claude / GPT as MUSE, Director + prompt writer ──
@app.route("/api/cloud")
def cloud_get():
    if (r := _host_only()):
        return r
    return jsonify(cloud.summary())                 # never contains a key


@app.route("/api/cloud/key", methods=["POST"])
def cloud_key():
    if (r := _host_only()):
        return r
    b = request.get_json(silent=True) or {}
    prov = b.get("provider")
    if prov not in cloud.PROVIDERS:
        return jsonify({"error": "unknown provider"}), 400
    key = str(b.get("key") or "").strip()[:300]
    if key:
        try:
            gpts = cloud.check_key(prov, key)       # validate before saving
        except cloud.CloudError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:                      # never a bare HTTP 500 in the Settings card
            return jsonify({"error": "couldn't check the %s key: %s" % (cloud.NAMES[prov], e)}), 502
        core.save_pref(prov + "_key", key)
        if prov == "openai":
            core.save_pref("openai_models", gpts)
        elif prov == "fireworks":
            core.save_pref("fireworks_models", gpts)     # only the GLM ids Fireworks actually served
            b0 = cloud.brain()
            if b0["provider"] == "fireworks" and b0["model"] not in gpts:
                core.save_pref("brain", {"provider": "fireworks", "model": gpts[0]})
        users.log("saved the %s API key" % cloud.NAMES[prov], "host")
    else:
        core.save_pref(prov + "_key", "")
        if cloud.brain()["provider"] == prov:
            core.save_pref("brain", {"provider": "local", "model": ""})
        users.log("removed the %s API key" % cloud.NAMES[prov], "host")
    return jsonify(cloud.summary())


@app.route("/api/cloud/brain", methods=["POST"])
def cloud_brain():
    if (r := _host_only()):
        return r
    b = request.get_json(silent=True) or {}
    prov, model = b.get("provider"), str(b.get("model") or "")
    if "cap" in b:
        try:
            core.save_pref("cloud_cap", max(0.0, min(10000.0, float(b["cap"]))))
        except (TypeError, ValueError):
            return jsonify({"error": "the monthly cap must be a number"}), 400
    if prov == "local":
        core.save_pref("brain", {"provider": "local", "model": ""})
    elif prov in cloud.PROVIDERS:
        if not cloud.keys()[prov]:
            return jsonify({"error": "save the %s API key first" % cloud.NAMES[prov]}), 400
        if not any(m["id"] == model and m["provider"] == prov for m in cloud.models()):
            return jsonify({"error": "unknown model"}), 400
        core.save_pref("brain", {"provider": prov, "model": model})
    return jsonify(cloud.summary())


@app.route("/api/cloud/params", methods=["POST"])
def cloud_params():
    """Model picker: per-model max output / temperature / effort. {model, params|null}."""
    if (r := _host_only()):
        return r
    b = request.get_json(silent=True) or {}
    model = str(b.get("model") or "")
    if not any(m["id"] == model for m in cloud.models()):
        return jsonify({"error": "unknown model"}), 400
    try:
        cloud.set_params(model, b.get("params"))
    except cloud.CloudError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(cloud.summary())


@app.route("/api/loras/token", methods=["GET", "POST"])
def loras_token():
    """Civitai API key for LoRA downloads (owner only). GET never returns the key itself."""
    if not is_owner():
        return jsonify({"error": "owner only"}), 403
    if request.method == "POST":
        tok = str((request.get_json(silent=True) or {}).get("token") or "").strip()[:200]
        if tok:
            try:
                user = loras.check_token(tok)        # validate before saving
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({"error": "couldn't reach Civitai to check the key: %s" % e}), 502
            core.save_pref("civitai_token", tok)
            core.save_pref("civitai_user", user)
        else:
            core.save_pref("civitai_token", "")
            core.save_pref("civitai_user", "")
    p = core.prefs()
    return jsonify({"set": bool(p.get("civitai_token")), "user": p.get("civitai_user") or ""})


@app.route("/api/plan/preview")
def plan_preview():
    """Composer hint: what MUSE will most likely do with this message (quick rules only, no model call)."""
    kinds = [k for k in (request.args.get("kinds") or "").split(",") if k][:16]
    return jsonify(router.preview(str(request.args.get("prompt") or "")[:2000], kinds) or {})


@app.route("/api/skills")
def skills_catalog():
    return jsonify(skills.catalog())


@app.route("/api/tts")
def api_tts():
    """MUSE's voice: one sentence -> WAV (natural local Kokoro voice, CPU only, cached)."""
    v = core.prefs().get("voice_" + uid()) or {}
    try:
        path = tts.say(request.args.get("text") or "", request.args.get("voice") or v.get("id") or tts.DEFAULT_VOICE,
                       request.args.get("speed") or v.get("speed") or 1.0)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 503
    resp = send_file(path, mimetype="audio/wav")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@app.route("/api/tts/voices")
def api_tts_voices():
    return jsonify({"voices": [{"id": k, "label": l} for k, l in tts.VOICES.items()], "default": tts.DEFAULT_VOICE,
                    "available": tts.available()})


@app.route("/api/console")
def api_console():
    """Newest live backend line per job for the MUSE bubble. The host PC also sees engine-wide lines."""
    ids = [i for i in (request.args.get("jobs") or "").split(",")[:20] if i in JOBS and mine(JOBS[i].get("user"))]
    lines, seq = console.latest(ids, host=_host())
    return jsonify({"lines": {k: {"src": v["src"], "text": v["text"], "level": v["level"], "t": v["t"]} for k, v in lines.items()},
                    "seq": seq})


@app.route("/api/jobs")
def jobs():
    n = min(200, int(request.args.get("limit", 60)))
    own = [i for i in ORDER if i in JOBS and mine(JOBS[i].get("user"))]
    return jsonify([public(JOBS[i]) for i in reversed(own[-n:])])


@app.route("/api/jobs/<jid>")
def job_get(jid):
    j = JOBS.get(jid)
    return jsonify(public(j)) if j and mine(j.get("user")) else (jsonify({"error": "no such job"}), 404)


@app.route("/api/jobs/<jid>/cancel", methods=["POST"])
def job_cancel(jid):
    j = JOBS.get(jid)
    if not j or not mine(j.get("user")):
        return jsonify({"error": "no such job"}), 404
    if j["status"] == "queued":
        j["status"], j["error"], j["finished"] = "cancelled", "cancelled", time.time()
        _persist()
    elif j["status"] == "running":
        j["_cancel"] = True
        if j.get("comfy_pid"):
            comfy.cancel(j["comfy_pid"])     # only ever our own prompt id
    return jsonify(public(j))


@app.route("/api/jobs/clear", methods=["POST"])
def jobs_clear():
    with _JLOCK:
        for i in list(ORDER):
            if JOBS.get(i, {}).get("status") in ("done", "error", "cancelled") and (JOBS[i].get("user") or "owner") == uid():
                ORDER.remove(i)
                JOBS.pop(i, None)
    _persist()
    return jsonify({"ok": True})


# ── library ────────────────────────────────────────────────────────────────
def _lib_files():
    out = []
    for f in os.listdir(core.LIB):
        k = core.kind_of(f)
        if k in ("image", "video", "audio"):
            p = os.path.join(core.LIB, f)
            out.append((os.path.getmtime(p), f, k, os.path.getsize(p)))
    out.sort(reverse=True)
    return out


@app.route("/api/library")
def library():
    kind = request.args.get("kind") or ""
    off = int(request.args.get("offset", 0))
    n = min(200, int(request.args.get("limit", 60)))
    ix = core.index()
    items = [x for x in _lib_files() if (not kind or x[2] == kind) and mine(ix.get(x[1], {}).get("user"))]
    return jsonify({"total": len(items), "items": [
        {"name": f, "kind": k, "size": sz, "mtime": mt, "url": "/media/" + f,
         "thumb": "/thumb/" + f if k != "audio" else None, **{key: ix.get(f, {}).get(key) for key in ("model", "prompt", "job", "mode", "seed")}}
        for mt, f, k, sz in items[off:off + n]]})


def _my_file(name):
    return mine(core.index().get(os.path.basename(str(name)), {}).get("user"))


@app.route("/media/<path:name>")
def media(name):
    p = core.in_dir(core.LIB, name)
    if not p or not _my_file(name):
        abort(404)
    return send_file(p, conditional=True, as_attachment=bool(request.args.get("dl")), download_name=os.path.basename(p))


@app.route("/thumb/<path:name>")
def thumb(name):
    src = core.in_dir(core.LIB, name)
    if not src or core.kind_of(name) not in ("image", "video") or not _my_file(name):
        abort(404)
    t = os.path.join(core.THUMBS, name + ".jpg")
    if not os.path.isfile(t) or os.path.getmtime(t) < os.path.getmtime(src):
        try:
            # ffmpeg for both (no Pillow in the compiled PC edition — image thumbnails used to 404 there)
            core.still(src, t, 480, at=None if core.kind_of(name) == "image" else 0.6)
        except Exception:
            abort(404)
    return send_file(t, max_age=3600)


@app.route("/api/library/<path:name>/delete", methods=["POST"])
def lib_delete(name):
    p = core.in_dir(core.LIB, name)
    if not p or not _my_file(name):
        return jsonify({"error": "not found"}), 404
    shutil.move(p, core.safe_path(os.path.join(core.TRASH, os.path.basename(p))))   # recoverable from data/trash
    return jsonify({"ok": True})


@app.route("/api/report", methods=["POST"])
def report_content():
    """In-app content report (Google Play AI-content policy). Logged to data/reports.jsonl for the
    lab owner; the reported file leaves the reporter's library (data/trash, recoverable)."""
    b = request.get_json(silent=True) or {}
    name = str(b.get("file") or "")[:200]
    rec = {"t": time.time(), "user": g.user.get("id") or g.user.get("name"), "file": name,
           "model": str(b.get("model") or "")[:40], "reason": str(b.get("reason") or "")[:80],
           "edition": str(b.get("edition") or "")[:12]}
    with open(os.path.join(core.DATA, "reports.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    p = core.in_dir(core.LIB, name) if name else None
    if p and _my_file(name):
        shutil.move(p, core.safe_path(os.path.join(core.TRASH, os.path.basename(p))))
    return jsonify({"ok": True})


@app.route("/api/library/<path:name>/use", methods=["POST"])
def lib_use(name):
    """Send a finished piece back in as a reference (e.g. Qwen image → H3 animate)."""
    p = core.in_dir(core.LIB, name)
    if not p or not _my_file(name):
        return jsonify({"error": "not found"}), 404
    stem, ext = os.path.splitext(os.path.basename(p))
    ref = _store_ref(stem, ext.lower())
    shutil.copy2(p, core.safe_path(os.path.join(core.REFS, ref)))
    return jsonify(_ref_info(ref))


# -- users (owner only) + presence --------------------------------------------
def _running_by_user():
    out = {}
    for j in list(JOBS.values()):
        if j.get("status") in ("running", "queued"):
            k = j.get("user") or "owner"
            out[k] = out.get(k, 0) + 1
    return out


@app.route("/api/me")
def me():
    return jsonify({"id": uid(), "name": g.user["name"], "role": g.user["role"], "host": _host()})


@app.route("/api/online")
def online():
    """Who is live right now (app 'population' button) — any signed-in person. Names + device kind only:
    never keys, IPs, limits or other people's jobs."""
    s = users.summary(include_keys=False, running_by_user=_running_by_user())
    people = [{"name": u["name"], "host": u["role"] == "owner", "you": u["id"] == uid(),
               "creating": u["running"] > 0, "devices": sorted({d["device"] for d in u["devices"] if d["live"]})}
              for u in s["users"] if u["live"]]
    people.sort(key=lambda p: (not p["you"], not p["host"], p["name"].lower()))
    return jsonify({"live": len(people), "people": people})


def _my_invite():
    """This person's own sign-in link: the address they reached the lab on (the LAN address on the GPU PC)
    + their key + the away address, same shape as a host invite."""
    if _loopback():
        base = "http://%s:%s" % (_lan_ip() or "127.0.0.1", core.PORT)
    else:
        base = request.host_url.rstrip("/")
    away = core.prefs().get("away_url") or ""
    return base + "/?key=" + g.user["key"] + ("&away=" + quote(away, safe="") if away else "")


def _master_guard():
    """The owner's key is the MASTER key (sees every chat, runs Host Control): it is only ever shown
    on the host PC itself, never to a remote device — even one signed in with it."""
    if g.user.get("role") == "owner" and not _host():
        return jsonify({"error": "the master key is only shown on the host PC"}), 403
    return None


@app.route("/api/my-key")
def my_key():
    """Your own key + invite link (the 'My key' QR sheet; 'Master key' on the host PC). Only ever the caller's own key."""
    if (r := _master_guard()):
        return r
    return jsonify({"name": g.user["name"], "key": g.user["key"], "invite": _my_invite(),
                    "master": g.user.get("role") == "owner", "away": bool(core.prefs().get("away_url"))})


@app.route("/api/my-key/qr")
def my_key_qr():
    """QR of your own invite (kind=invite) or bare key (kind=key). fmt=svg for the web,
    fmt=matrix ({size, rows:["0101…"]}) for the app to draw natively. Never encodes arbitrary text."""
    if (r := _master_guard()):
        return r
    text = g.user["key"] if request.args.get("kind") == "key" else _my_invite()
    try:
        import io
        import qrcode
        if request.args.get("fmt") == "matrix":
            q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(text)
            q.make(fit=True)
            m = q.get_matrix()
            return jsonify({"size": len(m), "rows": ["".join("1" if c else "0" for c in r) for r in m]})
        import qrcode.image.svg
        img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathFillImage, border=2)
        buf = io.BytesIO()
        img.save(buf)
        resp = Response(buf.getvalue(), mimetype="image/svg+xml")
        resp.headers["Cache-Control"] = "no-store"
        return resp
    except Exception as e:
        return jsonify({"error": "QR unavailable: %s" % e}), 500


def _host_only():
    if not _host():
        return jsonify({"error": "host only — manage access from MIR MEDIA LABS on the GPU PC"}), 403
    return None


@app.route("/api/host/users", methods=["GET", "POST"])
def host_users():
    if (r := _host_only()):
        return r
    if request.method == "POST":
        b = request.get_json(silent=True) or {}
        u = users.create(b.get("name"), b.get("allow"), b.get("daily"), b.get("expires_days"))
        return jsonify({"id": u["id"], "name": u["name"], "key": u["key"]})
    d = users.summary(include_keys=True, running_by_user=_running_by_user())
    d.update(remote=REMOTE["on"], log=users.recent_log(), lan=_lan_ip(), port=core.PORT, away=core.prefs().get("away_url") or "",
             engines=[{"id": k, "label": users.ENGINE_NAMES[k]} for k in users.ENGINES])
    return jsonify(d)


@app.route("/api/host/users/<user_id>", methods=["POST"])
def host_user(user_id):
    if (r := _host_only()):
        return r
    b = request.get_json(silent=True) or {}
    act = b.get("action")
    if act == "stop":                              # stop everything this person has running or waiting
        n = 0
        for j in list(JOBS.values()):
            if (j.get("user") or "owner") == user_id and j.get("status") in ("queued", "running"):
                n += 1
                if j["status"] == "queued":
                    j["status"], j["error"], j["finished"] = "cancelled", "stopped by the host", time.time()
                    events.job_event(j)
                else:
                    j["_cancel"] = True
                    if j.get("comfy_pid"):
                        comfy.cancel(j["comfy_pid"])
        _persist()
        u = users.by_id(user_id)
        users.log("stopped %d request%s" % (n, "" if n == 1 else "s"), u["name"] if u else user_id)
        return jsonify({"ok": True, "stopped": n})
    u, err = users.update(user_id, act, b)
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True, "key": u["key"] if u else None})


@app.route("/api/host/remote", methods=["POST"])
def host_remote():
    if (r := _host_only()):
        return r
    REMOTE["on"] = bool((request.get_json(silent=True) or {}).get("on"))
    core.save_pref("remote_access", REMOTE["on"])
    users.log("remote access " + ("ON" if REMOTE["on"] else "PAUSED"), "host")
    return jsonify({"remote": REMOTE["on"]})


@app.route("/api/host/notice", methods=["POST"])
def host_notice():
    """Push a short message to every phone / TV signed in to this lab."""
    if (r := _host_only()):
        return r
    text = str((request.get_json(silent=True) or {}).get("text") or "").strip()[:300]
    if not text:
        return jsonify({"error": "write a message first"}), 400
    events.push("*", "notice", "Message from the lab host", text)
    users.log("sent a notice: " + text[:60], "host")
    return jsonify({"ok": True})


@app.route("/api/host/away", methods=["POST"])
def host_away():
    """The lab's away-from-home address (router port-forward / DDNS name), added to invite links + QR codes."""
    if (r := _host_only()):
        return r
    url = str((request.get_json(silent=True) or {}).get("url") or "").strip()[:200]
    if url and not re.match(r"^https?://[^\s/?#]+(:\d+)?/?$", url, re.I):
        return jsonify({"error": "use a form like http://my-lab.duckdns.org:5400"}), 400
    core.save_pref("away_url", url.rstrip("/"))
    return jsonify({"away": url.rstrip("/")})


@app.route("/api/host/qr")
def host_qr():
    """Invite QR as SVG (pure-Python encoder, no Pillow)."""
    if (r := _host_only()):
        return r
    try:
        import io
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(request.args.get("text", "")[:600], image_factory=qrcode.image.svg.SvgPathFillImage, border=2)
        buf = io.BytesIO()
        img.save(buf)
        return Response(buf.getvalue(), mimetype="image/svg+xml")
    except Exception as e:
        return jsonify({"error": "QR unavailable: %s" % e}), 500


@app.route("/api/admin/presence")
def admin_presence():
    """Loopback only (see gate) - feeds the MirOS ACCESS panel. Never includes keys."""
    return jsonify(users.summary(include_keys=False, running_by_user=_running_by_user()))


# ── update server: the Android app checks /updates/android.json (+ .sig, Ed25519) — version.json for pre-2.0 apps ──
@app.route("/updates/<path:fn>")
def updates(fn):
    if fn in ("pc/version.json", "pc/version.json.sig", "pc/MirMediaLabs-Setup.exe"):
        p = core.in_dir(os.path.join(core.UPDATES, "pc"), fn[3:])
    elif fn in ("version.json", "android.json", "android.json.sig") or (fn.lower().endswith(".apk") and "/" not in fn):
        p = core.in_dir(core.UPDATES, fn)
    else:
        abort(404)
    if not p:
        abort(404)
    resp = send_file(p, conditional=True)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ── PC self-update (installed copies; owner only) ─────────────────────────
@app.route("/api/pc-update", methods=["GET", "POST"])
def pc_update():
    if not is_owner():
        return jsonify({"error": "owner only"}), 403
    act = (request.get_json(silent=True) or {}).get("action") if request.method == "POST" else None
    if act == "check":
        pcupdate.check()
    elif act == "apply":
        if any(j.get("status") == "running" for j in JOBS.values()):
            return jsonify({"error": "a render is running — update when it finishes"}), 409
        err = pcupdate.apply()
        if err:
            return jsonify({"error": err}), 500
        return jsonify({"ok": True, "restarting": True})
    return jsonify(pcupdate.STATE)


# ── isolation audit ────────────────────────────────────────────────────────
@app.route("/api/isolation")
def isolation():
    bad_mods = [m for m in sys.modules if re.search(r"(^|\.)(dashboard|rh_api|rh_scheduler|recon|trinity|settlement|"
                                                       r"miros_prompts|hermes_acp|alpaca_api|csp_strategy)$", m)]
    roots = {"root": core.ROOT, "data": core.DATA, "library": core.LIB, "refs": core.REFS, "updates": core.UPDATES}
    return jsonify({
        "separate_from_miros": not bad_mods,
        "miros_modules_loaded": bad_mods,
        "own_folders": roots,
        "blocked_paths": core.FORBIDDEN if is_owner() else ["(owner only)"],
        "own_access_key": True,
        "talks_to": {"comfyui": comfy.BASE + " (GPU renders)", "ollama": core.OLLAMA + " (prompt rewriting only, no context)"},
        "never_talks_to": ["MirOS dashboard :5000", "Robinhood / brokers", "MirOS vault", "Hermes"],
    })


def _lan_ip():
    """This PC's LAN address (no traffic is sent; a UDP connect just picks the route)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _port_busy(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    if _port_busy(core.PORT):
        print("MIR MEDIA LABS already running on :%d" % core.PORT)
        sys.exit(0)
    _load_jobs()
    threading.Thread(target=worker, daemon=True, name="mml-gpu-worker").start()
    threading.Thread(target=_status_loop, daemon=True, name="mml-status").start()
    threading.Thread(target=pcupdate.loop, daemon=True, name="mml-pc-update").start()
    pcupdate.cleanup()
    try:
        import tls
        tls.start(app)                              # :80 helper + :443 HTTPS when a cert exists
    except Exception as e:                          # HTTPS is optional; never block the lab
        print("HTTPS not started: %s" % e)
    print("MIR MEDIA LABS v%s on http://127.0.0.1:%d  (LAN key in data/access_key.txt)" % (core.APP_VERSION, core.PORT))
    app.run(host="0.0.0.0", port=core.PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
