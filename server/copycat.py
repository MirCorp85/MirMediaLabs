"""COPYCAT: swap a person / object in a video, or copy a dance onto another character (MiniMax H3 + SAM 3.1 on ComfyUI).

Engine = Openjutsu by D3voz (MIT, https://github.com/D3voz/openjutsu) with the lab's overlay (installer/copycat), which
Setup downloads, patches and builds into <install>/engines/copycat (Next.js, basePath /copycat).

Two loopback-only children, both hidden, started with the lab and on demand:
  * Next app            127.0.0.1:5472  (node + node_modules/next, `next start`)
  * comfy-api-proxy     127.0.0.1:5473  (.venv-proxy, patched by patch_proxy.py) -> ComfyUI :8188
The browser only ever talks to the lab's /copycat/* — this module streams it to :5472 (SSE + 500 MB uploads), behind the
lab's own key gate. Fix faces is switched off in the app (InsightFace / YOLO licences)."""
import os
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests
from flask import Response, jsonify, request, stream_with_context

import core
import engines

ROOT = engines.copycat()
NODE = engines.node()
NEXT_BIN = os.path.join(ROOT, "node_modules", "next", "dist", "bin", "next")
PROXY_EXE = os.path.join(ROOT, ".venv-proxy", "Scripts", "comfy-api-proxy.exe") if os.name == "nt" else os.path.join(ROOT, ".venv-proxy", "bin", "comfy-api-proxy")
APP_PORT = int(core.CONFIG.get("copycat_port") or 5472)          # own ports: never clashes with another CopyCat on this PC
PROXY_PORT = int(core.CONFIG.get("copycat_proxy_port") or APP_PORT + 1)
COMFY = "http://127.0.0.1:8188"
BASE = "/copycat"
LOGS = os.path.join(ROOT, "logs")
UP = "http://127.0.0.1:%d" % APP_PORT
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_DETACH = 0x00000008 if os.name == "nt" else 0
_LOCK = threading.Lock()
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
        "upgrade", "host", "content-length", "cookie", "authorization", "origin", "x-forwarded-for", "x-forwarded-host",
        "x-forwarded-proto", "accept-encoding"}
_SESSION = requests.Session()
_SESSION.trust_env = False                       # never route loopback through a system proxy


def _open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def installed():
    return os.path.isfile(NEXT_BIN) and os.path.isfile(PROXY_EXE) and os.path.isdir(os.path.join(ROOT, ".next"))


def status():
    return {"installed": installed(), "app": _open(APP_PORT), "proxy": _open(PROXY_PORT), "url": BASE}


def _spawn(cmd, name, env=None):
    os.makedirs(LOGS, exist_ok=True)
    lf = open(os.path.join(LOGS, name + ".log"), "ab")
    subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                     creationflags=_DETACH | _NO_WINDOW)


def ensure(wait=0):
    """Start whatever is down. Returns status(); waits up to `wait` s for the app port."""
    if not installed():
        return status()
    with _LOCK:
        if not _open(PROXY_PORT):
            _spawn([PROXY_EXE, "run", "--comfyui", COMFY, "--host", "127.0.0.1", "--port", str(PROXY_PORT),
                    "--max-upload-mb", "500"], "proxy")
        if not _open(APP_PORT):
            env = dict(os.environ, NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production",
                       COMFY_BASE_URL="http://127.0.0.1:%d" % PROXY_PORT, COMFYUI_URL=COMFY, COMFY_API_KEY="")
            env.pop("OPENJUTSU_PASSWORD", None)   # loopback-only; the lab's key gate guards it
            _spawn([NODE, NEXT_BIN, "start", "--hostname", "127.0.0.1", "--port", str(APP_PORT)], "app", env)
    t0 = time.time()
    while wait and time.time() - t0 < wait and not _open(APP_PORT):
        time.sleep(0.5)
    return status()


def _pids():
    """CopyCat's own processes (Next app + proxy launcher + its python), matched by their command line.
    (netstat / Get-NetTCPConnection on this PC don't report these listeners' LISTEN state reliably.)"""
    if os.name != "nt":
        out = subprocess.run(["pgrep", "-f", ROOT], capture_output=True, text=True, timeout=30).stdout
        return sorted({p.strip() for p in out.split() if p.strip().isdigit()})
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*" + ROOT.replace("'", "''") + "\\*' -and "
          "($_.Name -eq 'node.exe' -or $_.Name -eq 'python.exe' -or $_.Name -eq 'comfy-api-proxy.exe') } | "
          "ForEach-Object { $_.ProcessId }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30,
                         creationflags=_NO_WINDOW).stdout
    return sorted({p.strip() for p in out.split() if p.strip().isdigit()})


def stop():
    """Stop both children. Running ComfyUI jobs keep going inside ComfyUI."""
    killed = []
    for pid in _pids():
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, creationflags=_NO_WINDOW)
        else:
            subprocess.run(["kill", pid], capture_output=True)
        killed.append(pid)
    return killed


class _Sized:
    def __init__(self, stream, n):
        self._s, self._n = stream, n

    def __len__(self):
        return self._n

    def read(self, amt=-1):
        return self._s.read(65536 if amt is None or amt < 0 else amt)


# ── GPU / RAM handoff (Nov 5 2026, after "HostBuffer.read_file_slice failed" = Windows error 1450, commit exhausted) ──
# H3 stages ~20 GB + its 32B text encoder ~15 GB in system RAM, so a CopyCat job takes the lab's normal render priority:
# render lock (MirAI / MUSE / voice wait), Ollama evicted, ComfyUI's idle cache freed. When the last CopyCat job ends the
# lock is released and the engines that were resident before are loaded back (same keep-alive + context as before).
_ACTIVE = set()
_PARKED = []
_TERMINAL = {"succeeded", "failed", "canceled", "expired"}


def _core():
    try:
        import core
    except ImportError:
        import core
    return core


def _gpu_take():
    core = _core()
    with _LOCK:
        held = core.rendering()
        if held and not str(held.get("job", "")).startswith("copycat"):
            return False                          # another lab render owns the GPU; ComfyUI queues us behind it
        first = not _ACTIVE
        core.render_lock("copycat")
    if first:
        try:
            parked = [(m["name"], m.get("context_length")) for m in
                      core.requests.get(core.OLLAMA + "/api/ps", timeout=5).json().get("models", [])]
        except Exception:
            parked = []
        _PARKED[:] = parked or _PARKED
        core.evict_ollama()
        try:
            q = core.requests.get(COMFY + "/queue", timeout=5).json()
            if not (q.get("queue_running") or q.get("queue_pending")):       # never pull models out from under a render
                core.requests.post(COMFY + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
        except Exception:
            pass
    return True


def _gpu_give():
    core = _core()
    with _LOCK:
        if _ACTIVE:
            return
        held = core.rendering()
        if held and str(held.get("job", "")).startswith("copycat"):
            core.render_unlock()
        parked, _PARKED[:] = list(_PARKED), []
    for name, ctx in parked:                       # back to how it was (the heart engine is pinned, keep_alive -1)
        body = {"model": name, "prompt": "", "keep_alive": -1}
        if ctx:
            body["options"] = {"num_ctx": int(ctx)}
        try:
            core.requests.post(core.OLLAMA + "/api/generate", json=body, timeout=180)
        except Exception:
            pass


_HDR = {"Host": "127.0.0.1:%d" % APP_PORT, "Origin": UP}


def _saved_file():
    return os.path.join(_core().DATA, "copycat_saved.json")


def _pending_file():
    return os.path.join(_core().DATA, "copycat_pending.json")


def _pending(jid, kind=None, drop=False):
    """Every submitted CopyCat render is remembered on disk until its result is in the library, so a lab restart
    (or a render longer than any watcher) never loses one — register() resumes watchers for whatever is left."""
    core = _core()
    with _LOCK:
        p = core.load_json(_pending_file(), {})
        if drop:
            p.pop(jid, None)
        elif kind:
            p.setdefault(jid, {"kind": kind, "t": time.time()})
        core.save_json(_pending_file(), p)
        return p


def _download(url, prefix, ext):
    core = _core()
    name = core.new_name(prefix, ext)
    with _SESSION.get(url, headers=_HDR, stream=True, timeout=(10, 600)) as r:
        r.raise_for_status()
        tmp = os.path.join(core.LIB, name + ".part")
        with open(tmp, "wb") as f:
            for ch in r.iter_content(1 << 20):
                f.write(ch)
        if os.path.getsize(tmp) < 1024:
            os.remove(tmp)
            raise IOError("empty output")
        os.replace(tmp, os.path.join(core.LIB, name))
    return name


def _to_library(jid, kind="job", info=None):
    """Copy a finished render's outputs into the Media Lab library (once per job).
    kind "job" = /api/jobs (swap, dance copy, object, face, colour, montage…); "picture" = From-picture mode
    (/api/picture: the prepared picture and the final picture-to-video)."""
    core = _core()
    with _LOCK:
        done = core.load_json(_saved_file(), {})
        if jid in done:
            return done[jid]
        done[jid] = []                            # claim it so two watchers never save twice
        core.save_json(_saved_file(), done)
    names = []
    try:
        if kind == "picture":
            info = info or _SESSION.get(UP + BASE + "/api/picture", params={"id": jid}, headers=_HDR, timeout=30).json()
            video = not info.get("frame")
            names.append(_download(UP + BASE + "/api/picture?id=%s&media=result" % jid, "copycat", ".mp4" if video else ".png"))
            prompt = "CopyCat picture → video" if video else "CopyCat prepared picture"
        else:
            job = _SESSION.get(UP + BASE + "/api/jobs/" + jid, headers=_HDR, timeout=30).json()
            o = job.get("video")
            if o:
                ext = os.path.splitext(o.get("name") or "")[1].lower() or ".mp4"
                names.append(_download(UP + BASE + "/api/jobs/%s/outputs/%s" % (jid, o["id"]), "copycat", ext))
            prompt = "CopyCat swap / dance copy"
        for name in names:
            core.index_add(name, {"model": "copycat", "engine": "CopyCat", "prompt": prompt,
                                  "job": "copycat-" + jid, "created": time.time(), "user": "owner"})
    except Exception as e:
        with _LOCK:
            done = core.load_json(_saved_file(), {})
            done.pop(jid, None)                   # let a later pass retry
            core.save_json(_saved_file(), done)
        print("[copycat] library save failed for %s: %s" % (jid, e))
        return None
    with _LOCK:
        done = core.load_json(_saved_file(), {})
        done[jid] = names
        core.save_json(_saved_file(), done)
    return names


def _poll(jid, kind):
    """-> ("running" | "succeeded" | "failed" | "gone", picture-info-or-None)"""
    if kind == "picture":
        r = _SESSION.get(UP + BASE + "/api/picture", params={"id": jid}, headers=_HDR, timeout=30)
        if r.status_code == 404:
            return "gone", None
        if r.status_code == 422:
            return "failed", None
        if r.status_code >= 500:
            return "running", None               # ComfyUI / the app briefly unreachable — keep waiting
        j = r.json()
        if j.get("status") != "ready":
            return "running", None
        return ("succeeded", j) if j.get("url") else ("failed", None)   # a description pass has text, no media
    r = _SESSION.get(UP + BASE + "/api/jobs/" + jid, headers=_HDR, timeout=30)
    j = {}
    try:
        j = r.json()
    except ValueError:
        pass
    if r.status_code == 404 or str(j.get("error") or "").startswith("No job"):   # the proxy forgot it (restart / expiry)
        return "gone", None
    if not r.ok:
        return "running", None
    st = j.get("status")
    if st == "succeeded":
        return "succeeded", None
    return ("failed", None) if st in _TERMINAL else ("running", None)


def _watch(jid, t0=None, gpu=True, kind="job"):
    t0 = t0 or time.time()
    st, info, misses = "running", None, 0
    try:
        while time.time() - t0 < 24 * 3600:       # long H3 renders queue behind each other — never give up early
            time.sleep(10)
            try:
                st, info = _poll(jid, kind)
                misses = 0
            except Exception:
                st, misses = "running", misses + 1   # app restarting etc.
                if misses > 360:                  # an hour without an answer
                    break
            if st != "running":
                break
    finally:
        if gpu:
            with _LOCK:
                _ACTIVE.discard(jid)
            _gpu_give()
    if st == "succeeded":
        for i in range(5):                        # download hiccups: retry with backoff
            if _to_library(jid, kind, info) is not None:
                break
            time.sleep(15 * (i + 1))
        else:
            return                                # stays pending: retried on the next lab start
    if st in ("succeeded", "failed", "gone"):
        _pending(jid, drop=True)


def _track(jid, kind, gpu=False):
    _pending(jid, kind)
    threading.Thread(target=_watch, args=(jid, None, gpu, kind), daemon=True,
                     name="copycat-%s-%s" % (kind, jid[:8])).start()


def _resume():
    """After a lab restart: pick every unfinished CopyCat render back up."""
    ensure(wait=60)
    try:
        for jid, v in list(_core().load_json(_pending_file(), {}).items()):
            if time.time() - (v.get("t") or 0) > 3 * 86400:
                _pending(jid, drop=True)          # ComfyUI history doesn't keep them this long
                continue
            threading.Thread(target=_watch, args=(jid, None, False, v.get("kind") or "job"), daemon=True,
                             name="copycat-resume-" + jid[:8]).start()
    except Exception as e:
        print("[copycat] resume failed: %s" % e)


def _same_origin():
    o = request.headers.get("Origin")
    return o is None or urlparse(o).netloc == request.host


def proxy(sub):
    if not _same_origin():
        return jsonify({"error": "Cross-origin requests to CopyCat are not allowed."}), 403
    if not _open(APP_PORT) and not installed():
        return Response("<!doctype html><meta name=viewport content='width=device-width'><body style='font:15px system-ui;"
                        "background:#111;color:#ddd;padding:32px'><h2>CopyCat isn't installed yet</h2><p>Run MIR MEDIA LABS "
                        "Setup → Repair with <b>Studio apps, CopyCat + Design</b> ticked (source installs: Setup.bat).</p>",
                        status=503, mimetype="text/html")
    if not _open(APP_PORT):
        st = ensure(wait=25)
        if not st["app"]:
            return jsonify({"error": "CopyCat didn't start", "status": st,
                            "log": os.path.join(LOGS, "app.log")}), 503
    hdr = {k: v for k, v in request.headers.items() if k.lower() not in _HOP}
    hdr["Host"] = "127.0.0.1:%d" % APP_PORT
    hdr["Accept-Encoding"] = "identity"           # keep SSE frames unbuffered
    if request.headers.get("Origin"):
        hdr["Origin"] = UP                        # we checked same-origin above; the app checks Origin == its Host
    body = None
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        n = request.content_length
        if n:
            # streamed through, never held in memory (uploads up to 512 MB). A sized wrapper, or requests can't
            # measure werkzeug's stream and falls back to chunked framing that clashes with Content-Length.
            body = _Sized(request.stream, n)
    url = UP + BASE + ("/" + sub if sub is not None else "")
    submit = request.method == "POST" and (sub or "").strip("/") == "api/jobs"
    picture = request.method == "POST" and (sub or "").strip("/") == "api/picture"
    if picture:                                   # From-picture mode: small JSON {id} back → watch it into the library
        try:
            up = _SESSION.request("POST", url, params=request.args, headers=hdr, data=body, timeout=(10, 900))
        except requests.RequestException as e:
            return jsonify({"error": "CopyCat unreachable: %s" % e}), 502
        try:
            jid = up.json().get("id") if up.ok else None
        except ValueError:
            jid = None
        if jid:
            _track(jid, "picture")
        out = [(k, v) for k, v in up.headers.items() if k.lower() not in _HOP]
        return Response(up.content, status=up.status_code, headers=out)
    took = False
    if submit:
        try:
            took = _gpu_take()                    # render priority + free RAM/VRAM before the upload reaches ComfyUI
        except Exception:
            took = False
    try:
        up = _SESSION.request(request.method, url, params=request.args, headers=hdr, data=body, stream=True,
                              allow_redirects=False, timeout=(10, None if "/events" in (sub or "") else 900))
    except requests.RequestException as e:
        if took:
            _gpu_give()
        return jsonify({"error": "CopyCat unreachable: %s" % e}), 502
    except BaseException:                          # client went away mid-upload etc. — never leave the lock / engine parked
        if took:
            _gpu_give()
        raise
    if submit:
        jid = None
        try:
            data = up.content                      # small JSON {id, status}; read it to learn the job id
            jid = up.json().get("id") if up.ok else None
        except ValueError:
            pass
        except BaseException:
            if took:
                _gpu_give()
            raise
        if jid:                                    # every job: GPU handoff (if taken) + result -> library
            if took:
                with _LOCK:
                    _ACTIVE.add(jid)
            _track(jid, "job", took)
        elif took:
            _gpu_give()
        out = [(k, v) for k, v in up.raw.headers.items() if k.lower() not in _HOP]
        return Response(data, status=up.status_code, headers=out)
    out = [(k, v) for k, v in up.raw.headers.items() if k.lower() not in _HOP or k.lower() == "content-length"]
    out = [(k, v.replace(UP, "") if k.lower() == "location" else v) for k, v in out]

    def gen():
        try:
            for ch in up.iter_content(chunk_size=None):
                if ch:
                    yield ch
        finally:
            up.close()
    return Response(stream_with_context(gen()) if request.method != "HEAD" else b"", status=up.status_code, headers=out,
                    direct_passthrough=True)


def register(app, hk):
    M = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    @app.route("/copycat", methods=M)
    def cc_root():
        return proxy(None)

    @app.route("/copycat/", methods=M)
    def cc_slash():
        return proxy("")

    @app.route("/copycat/<path:sub>", methods=M)
    def cc_sub(sub):
        return proxy(sub)

    @app.route("/api/copycat/status")
    def cc_status():
        return jsonify(status())

    @app.route("/api/copycat/<act>", methods=["POST"])
    def cc_act(act):
        if not hk["is_owner"]():
            return jsonify({"ok": False, "error": "owner only"}), 403
        if act == "start":
            return jsonify(dict(ensure(wait=30), ok=True))
        if act == "stop":
            return jsonify({"ok": True, "stopped": stop()})
        return jsonify({"ok": False, "error": "unknown action"}), 400

    # start with the lab (cheap: no GPU until a job runs; ComfyUI does the work)
    # …and pick back up every render that was still running (or not yet saved) when the lab last stopped
    threading.Thread(target=_resume, daemon=True, name="copycat-start").start()
