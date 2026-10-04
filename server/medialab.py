"""MIR MEDIA LABS — standalone generative media studio.

    python medialab.py            → http://127.0.0.1:5400  (LAN: http://<pc-ip>:5400)

Four local models through ComfyUI: MiniMax H3 (video), MiniMax Music 3.0, Qwen-Image 2.1,
ACE-Step 1.5. Its own console, ⚙ parameters per model, 📎 references (audio/image/text/video),
its own library (data/library), its own access key and its own update server (/updates).
Completely separate from MirOS: no MirOS imports, no calls to the MirOS dashboard, no access
to MirOS files — see core.py for the sandbox and /api/isolation for the live audit.
"""
import mimetypes
import os
import queue
import re
import shutil
import socket
import sys
import threading
import time

from flask import Flask, Response, abort, g, jsonify, redirect, request, send_file, send_from_directory

import comfy
import core
import params
import pcupdate
import renderers
import llm
import skills
import loras
import users
import perf
import router

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024
UPLOAD_MAX_MB = 500
users.load()

# -- access gate: every person has their own key (users.py). Loopback = the owner on this PC. --
OPEN_PATHS = ("/api/ping",)
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
    supplied = request.cookies.get("mml_key") or request.headers.get("X-MML-Key") or request.args.get("key")
    ip = request.remote_addr or "?"
    if not _loopback() and _locked_out(ip):
        return jsonify({"error": "too many wrong keys - try again in 15 minutes"}), 429
    u = users.by_key(supplied) or (users.owner() if _loopback() else None)
    if not u and supplied and not _loopback():
        _note_fail(ip)
    if not u:
        if request.path.startswith(("/api/", "/media/", "/thumb/", "/refs/", "/updates/")):
            return jsonify({"error": "unauthorized - Media Lab access key required"}), 401
        return Response(LOGIN_HTML, mimetype="text/html", status=401)
    g.user = u
    users.touch(u, request.remote_addr, request.headers.get("User-Agent", ""), request.path)
    if request.args.get("key") and request.method == "GET" and request.path == "/":
        resp = redirect(request.path)
        resp.set_cookie("mml_key", request.args["key"], max_age=3600 * 24 * 365, httponly=True, samesite="Lax")
        return resp
    return None


# brute-force guard: 10 wrong keys from one address -> 15 min lockout
_FAILS = {}
_FAIL_LOCK = threading.Lock()


def _note_fail(ip):
    with _FAIL_LOCK:
        now = time.time()
        _FAILS[ip] = [t for t in _FAILS.get(ip, []) if now - t < 900] + [now]


def _locked_out(ip):
    with _FAIL_LOCK:
        return len([t for t in _FAILS.get(ip, []) if time.time() - t < 900]) >= 10


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
    """Owner sees everything; a user only what they created (legacy items belong to the owner)."""
    return is_owner() or (owner_id or "owner") == uid()


LOGIN_HTML = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>MIR MEDIA LABS</title><body style="background:#07070b;color:#e9e7f5;font:15px system-ui;display:grid;place-items:center;height:100vh;margin:0">
<form onsubmit="location='/?key='+encodeURIComponent(k.value);return false" style="text-align:center">
<div style="letter-spacing:.3em;font-weight:800;margin-bottom:14px">MIR MEDIA LABS</div>
<input id=k placeholder="access key" style="padding:12px;border-radius:10px;border:1px solid #333;background:#111;color:#fff;width:260px">
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
          "finished", "error", "params", "user", "input", "skill", "pipeline", "steps", "step", "route")


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
    if is_owner():   # master key: label whose request this is
        u = users.by_id(j.get("user") or "owner")
        d["user_name"] = u["name"] if u else (j.get("user") or "owner")
        d["mine"] = (j.get("user") or "owner") == uid()
    return d


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


def _run_pipeline(job):
    """Chain the steps inside this ONE job; each step's outputs become references for later steps."""
    base, outs, files, texts = list(job.get("refs") or []), [], [], []
    owner = job.get("user") or "owner"
    n = len(job["steps"])
    for i, st in enumerate(job["steps"], 1):
        if job.get("_cancel"):
            raise comfy.Cancelled()
        use = st.get("use")
        extra = (outs[-1] if outs else []) if use == "prev" else [r for o in outs for r in o] if use == "all" else []
        mdl = skills.model_for(st["role"])        # role → today's engine for that role
        job.update(model=mdl, step="%d/%d" % (i, n), refs=base + extra,
                   prompt=skills.fill(st["tpl"], job.get("input"), i == 1 and any(core.kind_of(r) == "image" for r in base)),
                   params=params.get(mdl, override=skills.overrides(st, mdl), uid=owner))
        renderers.log(job, "▶ step %d/%d · %s" % (i, n, skills.ROLES[st["role"]]["label"]))
        res = _run_once(job)
        files += res["files"]
        texts.append("── step %d · %s ──" % (i, skills.ROLES[st["role"]]["label"]) + chr(10) + (res.get("text") or ""))
        refs = []
        for fn in res["files"]:
            src = core.in_dir(core.LIB, fn)
            if src:
                stem, ext = os.path.splitext(fn)
                ref = _store_ref(stem, ext.lower(), owner)
                shutil.copy2(src, core.safe_path(os.path.join(core.REFS, ref)))
                refs.append(ref)
        outs.append(refs)
    job["refs"] = base
    return {"files": files, "text": chr(10).join(texts)}


def worker():
    while True:
        jid = Q.get()
        job = JOBS.get(jid)
        if not job or job.get("status") != "queued":
            continue
        job["status"], job["started"] = "running", time.time()
        _persist()
        try:
            if job.get("model") == "auto":
                _route(job)
                _persist()
            res = _run_pipeline(job) if job.get("steps") else _run_once(job)
            job["files"], job["output"] = res["files"], res["text"]
            job["status"] = "done"
        except comfy.Cancelled:
            job["status"], job["error"] = "cancelled", "cancelled"
        except Exception as e:
            job["status"], job["error"] = "error", str(e)[:1500]
        finally:
            job["finished"] = time.time()
            job["stage"] = ""
            job.pop("_cancel", None)
            _persist()


# ── MUSE Director: Auto mode decides the tool for each message ─────────────
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
        job.update(model=skills.model_for(pl["steps"][0]["role"]), pipeline=pl["name"], steps=pl["steps"],
                   step="0/%d" % len(pl["steps"]), input=prompt)
        return
    has_img = any(core.kind_of(r) == "image" for r in refs)
    if d["action"] == "skill":
        sk = skills.skill(d["skill"])
        model = skills.model_for(sk["role"])
        job.update(model=model, skill=sk["name"], prompt=skills.fill(sk["tpl"], prompt, has_img),
                   params=params.get(model, override=skills.overrides(sk, model), uid=owner))
    else:
        model = skills.model_for(d["role"])
        job.update(model=model, prompt=prompt, params=params.get(model, uid=owner))
    picked = loras.pick(model, job.pop("_loras", None))
    if picked:
        trig = [t for l in picked for t in l["triggers"] if t and t.lower() not in job["prompt"].lower()]
        if trig:
            job["prompt"] = (job["prompt"] + ", " if job["prompt"] else "") + ", ".join(trig[:8])
        job["loras"] = picked


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


@app.route("/static/<path:fn>")
def static_files(fn):
    return _static(fn)


@app.route("/api/ping")
def ping():
    return jsonify({"app": core.APP_NAME, "version": core.APP_VERSION})


# ── status ─────────────────────────────────────────────────────────────────
_STATUS = {"t": 0, "v": None}


def _refresh_status():
    try:
        tags = [m["name"] for m in core.requests.get(core.OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
        eng = {"up": True, "model": core.engine_model(), "available": tags}
    except Exception:
        eng = {"up": False, "model": core.prefs().get("engine_model") or core.DEFAULT_ENGINE, "available": []}
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


@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no file"}), 400
    stem, ext = os.path.splitext(f.filename)
    ext = ext.lower()
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
    refs = [os.path.basename(str(n)) for n in (body.get("refs") or [])][:16]
    refs = [n for n in refs if core.in_dir(core.REFS, n) and _my_ref(n)]
    if not prompt and not refs:
        return jsonify({"error": "write a prompt or attach a reference"}), 400
    if sk and sk.get("needs") and not any(core.kind_of(r) == sk["needs"] for r in refs):
        return jsonify({"error": "%s needs an attached %s (📎)" % (sk["name"], sk["needs"])}), 400
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
    picked = [] if model in ("llama", "auto") else loras.pick(model, body.get("loras"))   # LoRAs are for the media engines
    if picked:
        trig = [t for l in picked for t in l["triggers"] if t and t.lower() not in prompt.lower()]
        if trig:
            prompt = (prompt + ", " if prompt else "") + ", ".join(trig[:8])
    if body.get("params") and model != "auto":
        params.save(model, body["params"], uid())
    jid = "j%d" % int(time.time() * 1000)
    job = {"id": jid, "model": model, "prompt": prompt, "refs": refs, "status": "queued", "stage": "queued",
           "log": "", "output": "", "files": [], "created": time.time(),
           "params": {} if model == "auto" else params.get(model, uid=uid()),
           "user": uid(), "input": prompt, "loras": picked}
    if sk:
        job.update(skill=sk["name"], prompt=skills.fill(sk["tpl"], prompt, sk["role"] != "text" and any(core.kind_of(r) == "image" for r in refs)),
                   params=params.get(model, override=skills.overrides(sk, model), uid=uid()))
    elif pl:
        job.update(pipeline=pl["name"], steps=pl["steps"], step="0/%d" % len(pl["steps"]))
    if model == "auto":
        job["who"] = {"name": g.user.get("name", ""), "role": g.user.get("role", "")}
        job["_loras"] = body.get("loras")
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
        elif body.get("key") == "mltheme":
            tid = str((body.get("value") or {}).get("id") or "")
            if tid in ("claude", "graphite", "obsidian", "midnight", "paper"):
                core.save_pref(tkey, {"id": tid})
    return jsonify({"font": core.prefs().get(key) or {"id": ""}, "mltheme": core.prefs().get(tkey) or {"id": ""}})


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


@app.route("/api/skills")
def skills_catalog():
    return jsonify(skills.catalog())


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
            if core.kind_of(name) == "image":
                from PIL import Image, ImageOps
                im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
                im.thumbnail((480, 480))
                im.save(t, "JPEG", quality=82)
            else:
                renderers.ffmpeg(["-ss", "0.6", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", t], 60)
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
    d.update(remote=REMOTE["on"], log=users.recent_log(), lan=_lan_ip(), port=core.PORT,
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


# ── update server (the Android app checks /updates/version.json) ───────────
@app.route("/updates/<path:fn>")
def updates(fn):
    if fn in ("pc/version.json", "pc/version.json.sig", "pc/MirMediaLabs-Setup.exe"):
        p = core.in_dir(os.path.join(core.UPDATES, "pc"), fn[3:])
    elif fn == "version.json" or (fn.lower().endswith(".apk") and "/" not in fn):
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
    print("MIR MEDIA LABS v%s on http://127.0.0.1:%d  (LAN key in data/access_key.txt)" % (core.APP_VERSION, core.PORT))
    app.run(host="0.0.0.0", port=core.PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
