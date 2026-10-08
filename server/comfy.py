"""Local ComfyUI engine access — the GPU resource MIR MEDIA LABS shares with the PC.

Uses the ComfyUI install that Comfy Desktop manages (same weights on disk), starts
it headless on :8188 when nothing answers, and only ever touches ITS OWN prompts:
cancel interrupts a prompt only when that prompt id is ours.
"""
import json
import os
import subprocess
import threading
import time

import requests

import core
import platform_util as pu
import console
import explain

LOCAL = os.environ.get("LOCALAPPDATA", "")
_CFG = core.CONFIG                   # set by the installer; empty on the build PC (Comfy Desktop paths)
if pu.IS_WIN:
    _DEF_ROOT = os.path.join(LOCAL, "Comfy-Desktop", "ComfyUI-Installs", "ComfyUI")
    _DEF_SHARED = os.path.join(LOCAL, "Comfy-Desktop", "ComfyUI-Shared")
else:                                # Linux: headless ComfyUI installed by install.sh
    _DEF_ROOT = os.path.join(core.ROOT, "comfy")
    _DEF_SHARED = os.path.join(core.ROOT, "comfy", "shared")
COMFY_ROOT = _CFG.get("comfy_root") or _DEF_ROOT
COMFY_PY = _CFG.get("comfy_python") or pu.venv_python(os.path.join(COMFY_ROOT, "ComfyUI", ".venv"))
COMFY_SHARED = _CFG.get("comfy_shared") or _DEF_SHARED
PORTS = (8188, 8000, 8189, 8001)
BASE = "http://127.0.0.1:8188"
OUT_PREFIX = "mirmedialabs"          # our own subfolder in ComfyUI's output dir
_LOCK = threading.Lock()

WEIGHTS = {
    "h3": ["minimax_h3_fl2va_pruned_int8_convrot.safetensors", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"],
    "music3": ["minimax_music3_dit_fp16.safetensors|minimax_music3_dit_int8_convrot.safetensors",
               "minimax_music3_text_encoder_pruned_int8_convrot.safetensors"],
    "qimg": ["qwen_image_2.1_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors"],
    "ace": ["acestep_v1.5_xl_turbo_bf16.safetensors", "qwen_4b_ace15.safetensors"],
}
for _ws in WEIGHTS.values():
    core.apply_model_overrides(_ws)


def _model_paths_yaml():
    if _CFG:
        return _CFG.get("comfy_model_paths")     # None → only ComfyUI's own models/ folder
    base = os.path.join(os.environ.get("APPDATA", ""), "Comfy Desktop")
    inst = os.path.join(base, "instance-model-paths")
    try:
        ymls = [os.path.join(inst, f) for f in os.listdir(inst) if f.endswith(".yaml")]
        if ymls:
            return max(ymls, key=os.path.getmtime)
    except OSError:
        pass
    return os.path.join(base, "shared_model_paths.yaml")


def _port_open(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _probe(port):
    """Socket pre-check (a closed localhost port costs ~2 s per HTTP try on Windows),
    then the HTTP check. A ComfyUI busy loading weights can be slow to answer — an open
    port that times out still counts as up."""
    if not _port_open(port):
        return False
    try:
        r = requests.get("http://127.0.0.1:%d/system_stats" % port, timeout=6)
        return r.status_code == 200 and "comfyui_version" in ((r.json() or {}).get("system") or {})
    except requests.exceptions.Timeout:
        return True
    except Exception:
        return False


def up():
    """True if a ComfyUI answers; repoints BASE at it."""
    global BASE
    cur = int(BASE.rsplit(":", 1)[1])
    for port in (cur,) + tuple(p for p in PORTS if p != cur):
        if _probe(port):
            BASE = "http://127.0.0.1:%d" % port
            return True
    return False


def start(wait=True, timeout=240):
    with _LOCK:
        if up():
            return True
        if not os.path.isfile(COMFY_PY):
            raise RuntimeError("ComfyUI engine not found — run MirMediaLabs-Setup.exe (Repair)" if pu.IS_WIN else
                               "ComfyUI engine not found — run install.sh --engine")
        busy = pu.find_pids(r"ComfyUI.*main\.py.*--port 8188")
        if busy:
            # an engine process exists but isn't answering: give it a grace period (it may be loading),
            # then treat it as frozen (crashed but still holding :8188), kill it and start fresh
            t0 = time.time()
            while time.time() - t0 < 60 and not up():
                time.sleep(3)
            if up():
                return True
            pu.kill_pids(busy)
            time.sleep(3)
            busy = []
        if not busy:
            cmd = [COMFY_PY, "-s", os.path.join("ComfyUI", "main.py"), "--listen", "127.0.0.1", "--port", "8188",
                   "--input-directory", os.path.join(COMFY_SHARED, "input"),
                   "--output-directory", os.path.join(COMFY_SHARED, "output")] + (_CFG.get("comfy_args") or [])
            yml = _model_paths_yaml()
            if yml:
                cmd += ["--extra-model-paths-config", yml]
            with open(os.path.join(core.LOGS, "comfy_engine_out.log"), "a") as lf, \
                    open(os.path.join(core.LOGS, "comfy_engine_err.log"), "a") as ef:
                subprocess.Popen(cmd, cwd=COMFY_ROOT, stdout=lf, stderr=ef, **pu.detached_kwargs(),
                                 env=dict(os.environ, **{k: str(v) for k, v in (_CFG.get("comfy_env") or {}).items()}))  # e.g. HSA_OVERRIDE_GFX_VERSION
    if not wait:
        return True
    t0 = time.time()
    while time.time() - t0 < timeout:
        if up():
            return True
        time.sleep(3)
    raise RuntimeError("ComfyUI engine didn't come up within %ds" % timeout)


def ensure():
    if not up():
        start(wait=True)


_MODELS_CACHE = {}


def models(folder):
    try:
        v = set(requests.get(BASE + "/models/" + folder, timeout=8).json())
        _MODELS_CACHE[folder] = v
        return v
    except Exception:
        return _MODELS_CACHE.get(folder, set())


def status():
    if not up():
        return {"up": False, "port": None, "models": {k: None for k in WEIGHTS}}
    have = models("diffusion_models") | models("text_encoders")
    ready = {k: (all(any(alt in have for alt in w.split("|")) for w in ws) if have else None) for k, ws in WEIGHTS.items()}
    try:
        st = requests.get(BASE + "/system_stats", timeout=3).json()
        dev = (st.get("devices") or [{}])[0]
        vram = {"total": dev.get("vram_total"), "free": dev.get("vram_free"), "name": dev.get("name")}
        ver = (st.get("system") or {}).get("comfyui_version")
    except Exception:
        vram, ver = {}, None
    try:
        q = requests.get(BASE + "/queue", timeout=3).json()
        qlen = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
    except Exception:
        qlen = None
    return {"up": True, "port": int(BASE.rsplit(":", 1)[1]), "version": ver, "models": ready, "vram": vram, "queue": qlen}


def free():
    """Unload models + caches (processed by ComfyUI between prompts, so it never breaks a running render)."""
    try:
        requests.post(BASE + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
        time.sleep(3)
    except Exception:
        pass


def upload(path):
    core.safe_path(path)
    with open(path, "rb") as f:
        up_ = requests.post(BASE + "/upload/image", files={"image": (os.path.basename(path), f)},
                            data={"overwrite": "true"}, timeout=180).json()
    return up_["name"] if not up_.get("subfolder") else up_["subfolder"] + "/" + up_["name"]


class Cancelled(Exception):
    pass


class EngineLost(RuntimeError):
    """ComfyUI went away under a job (crash, OOM, or someone else restarted/killed it)."""


# ── live progress: ComfyUI's /ws broadcasts "executing" (which node) + "progress" (step n of max) ──────────────────
# Tiny stdlib websocket reader (no extra dependency; the compiled PC edition stays lean). job["progress"] =
# {"what": "composing the song", "value": 1841, "max": 3001, "pct": 61, "eta": 590} — the status card shows it.
_WHAT = [("MiniMaxMusic3TextEncode", "composing the song"), ("TextEncodeAceStep", "writing the music codes"),
         ("KSampler", "diffusion"), ("SamplerCustom", "diffusion"), ("VAEDecode", "decoding"), ("VAEEncode", "reading the input"),
         ("TextEncode", "reading the prompt"), ("CLIPTextEncode", "reading the prompt"), ("Loader", "loading the model"),
         ("LoadAudio", "loading inputs"), ("LoadImage", "loading inputs"), ("Save", "saving"), ("Upscale", "upscaling")]


def _what(cls):
    return next((w for k, w in _WHAT if k.lower() in (cls or "").lower()), "working")


PREVIEW_METHOD = {"sharp": "taesd", "fast": "latent2rgb", "off": "none"}   # taesd falls back to latent2rgb without a decoder


def preview_method():
    """Lab setting live_preview (sharp | fast | off) → ComfyUI's per-prompt preview_method."""
    return PREVIEW_METHOD.get(str(core.prefs().get("live_preview") or "sharp"), "taesd")


def _frame(job, img):
    """Keep only the newest live preview (≤ ~4 fps): job['_pv'] = JPEG bytes, progress.pv = frame number."""
    now = time.time()
    if now - job.get("_pv_t", 0) < 0.25:
        return
    job["_pv"], job["_pv_t"] = img, now
    job["_pv_n"] = job.get("_pv_n", 0) + 1
    job["progress"] = dict(job.get("progress") or {"what": "diffusion"}, pv=job["_pv_n"])


class _Watch(threading.Thread):
    def __init__(self, job, pid, graph):
        super().__init__(daemon=True)
        self.job, self.pid, self.graph, self.stop = job, pid, graph, False
        self.cid = "mml-watch-%s" % os.urandom(4).hex()   # previews are sent only to the client that queued the prompt
        self.ready = threading.Event()                     # set once the socket is open, so no early frame is missed
        self.t0 = None

    def run(self):
        import base64
        import socket
        import struct
        try:
            host, port = BASE.split("//", 1)[1].split("/", 1)[0].rsplit(":", 1)
            s = socket.create_connection((host, int(port)), timeout=5)
            key = base64.b64encode(os.urandom(16)).decode()
            s.sendall(("GET /ws?clientId=%s HTTP/1.1\r\nHost: %s:%s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                       "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (self.cid, host, port, key)).encode())
            buf = b""
            while b"\r\n\r\n" not in buf:
                c = s.recv(4096)
                if not c:
                    return
                buf += c
            if b" 101 " not in buf.split(b"\r\n", 1)[0]:
                return
            self.ready.set()
            buf = buf.split(b"\r\n\r\n", 1)[1]
            s.settimeout(1.0)

            def need(n):
                nonlocal buf
                while len(buf) < n:
                    if self.stop:
                        raise EOFError
                    try:
                        c = s.recv(65536)
                    except socket.timeout:
                        continue
                    if not c:
                        raise EOFError
                    buf += c
                out, buf = buf[:n], buf[n:]
                return out

            while not self.stop:
                b1, b2 = need(2)
                op, ln = b1 & 0x0F, b2 & 0x7F
                if ln == 126:
                    ln = struct.unpack(">H", need(2))[0]
                elif ln == 127:
                    ln = struct.unpack(">Q", need(8))[0]
                mask = need(4) if b2 & 0x80 else None
                data = need(ln)
                if mask:
                    data = bytes(x ^ mask[i % 4] for i, x in enumerate(data))
                if op == 8:
                    return
                if op == 2 and len(data) > 8:                  # binary: live sampler preview (JPEG)
                    ev = struct.unpack(">I", data[:4])[0]
                    if ev == 1:                                # PREVIEW_IMAGE: [image type][image]
                        _frame(self.job, data[8:])
                    elif ev == 4:                              # PREVIEW_IMAGE_WITH_METADATA: [len][json][image]
                        n = struct.unpack(">I", data[4:8])[0]
                        try:
                            meta = json.loads(data[8:8 + n].decode("utf-8", "replace"))
                        except ValueError:
                            meta = {}
                        if meta.get("prompt_id") in (None, self.pid):
                            _frame(self.job, data[8 + n:])
                    continue
                if op != 1:
                    continue                                   # pings
                try:
                    m = json.loads(data.decode("utf-8", "replace"))
                except ValueError:
                    continue
                d = m.get("data") or {}
                if d.get("prompt_id") not in (None, self.pid):
                    continue
                if m.get("type") == "executing" and d.get("node"):
                    cls = (self.graph.get(str(d["node"])) or {}).get("class_type", "")
                    self.job["progress"] = {"what": _what(cls), "node": cls, "pv": self.job.get("_pv_n")}
                    self.t0 = None
                    console.emit("COMFY", "%s · %s" % (cls, explain.node(cls)), self.job)
                elif m.get("type") == "execution_cached" and d.get("nodes"):
                    console.emit("COMFY", "reusing %d cached step(s) from the last render" % len(d["nodes"]), self.job)
                elif m.get("type") == "execution_error":
                    console.emit("COMFY", "error in %s · %s" % (d.get("node_type", "?"), d.get("exception_message", "")[:90]), self.job, "error")
                elif m.get("type") == "progress" and d.get("max"):
                    v, mx = int(d.get("value") or 0), int(d["max"])
                    now = time.time()
                    if self.t0 is None or v <= 1:
                        self.t0 = (now, v)
                    eta = None
                    if v > self.t0[1] and now > self.t0[0]:
                        eta = int((mx - v) * (now - self.t0[0]) / (v - self.t0[1]))
                    cls = (self.graph.get(str(d.get("node"))) or {}).get("class_type", "") if d.get("node") else ""
                    prev = self.job.get("progress") or {}
                    self.job["progress"] = {"what": _what(cls) if cls else prev.get("what", "working"), "node": cls or prev.get("node", ""),
                                            "value": v, "max": mx, "pct": int(v * 100 / mx), "eta": eta,
                                            "pv": self.job.get("_pv_n")}
                    rate = ""
                    if v > self.t0[1] and now > self.t0[0]:
                        spi = (now - self.t0[0]) / (v - self.t0[1])
                        rate = (" · %.1f s/it" % spi) if spi >= 1 else (" · %.1f it/s" % (1 / spi))
                    node = cls or prev.get("node", "")
                    console.emit("COMFY", "%s · step %d/%d%s%s" % (explain.node(node).split(" · ")[0] if node else "working", v, mx, rate,
                                 (" · " + explain.eta(eta)) if eta else ""), self.job)
        except Exception:
            return


def run(graph, want, job, timeout_s=120 * 60):
    """Submit a graph, wait for it, return the first output entry of kind want
    ('video' | 'audio' | 'image'). job['_cancel'] aborts; job['comfy_pid'] is recorded."""
    if job.get("loras"):                   # LoRA Samples picked for this render → chain them onto the model
        try:
            from . import loras as _loras
        except ImportError:
            import loras as _loras
        graph = _loras.apply(graph, job)
    job["progress"] = None
    watch = _Watch(job, "", graph)                 # socket first: live previews go to this client id
    watch.start()
    watch.ready.wait(3)
    try:
        r = requests.post(BASE + "/prompt", json={"prompt": graph, "client_id": watch.cid,
                                                  "extra_data": {"preview_method": preview_method()}}, timeout=20)
        d = r.json()
        if r.status_code != 200 or "prompt_id" not in d:
            raise RuntimeError("ComfyUI rejected the graph: %s" % json.dumps(d.get("node_errors") or d.get("error") or d)[:600])
        pid, t0 = d["prompt_id"], time.time()
        job["comfy_pid"] = watch.pid = pid
        return _wait(graph, want, job, timeout_s, pid, t0)
    finally:
        watch.stop = True
        job["progress"] = None
        for k in ("_pv", "_pv_t", "_pv_n"):
            job.pop(k, None)


def _wait(graph, want, job, timeout_s, pid, t0):
    while True:
        time.sleep(3)
        if job.get("_cancel"):
            cancel(pid)
            raise Cancelled()
        if time.time() - t0 > timeout_s:
            cancel(pid)
            raise RuntimeError("render timed out after %d min" % (timeout_s // 60))
        try:
            hist = requests.get(BASE + "/history/" + pid, timeout=30).json()
        except requests.exceptions.ConnectionError:
            raise EngineLost("ComfyUI stopped mid-job (crash / out of VRAM / restarted by another app)")
        except Exception:
            continue
        if pid not in hist:
            pg = job.get("progress") or {}
            if _pending(pid):
                job["stage"] = "queued in ComfyUI"
            elif pg.get("what"):
                eta = pg.get("eta")
                job["stage"] = pg["what"] + (" · %d%%" % pg["pct"] if pg.get("max") else "") + \
                    (" · ~%s left" % (("%d min" % round(eta / 60)) if eta >= 90 else "%d s" % eta) if eta else "")
            else:
                job["stage"] = "rendering"
            continue
        status_ = hist[pid].get("status") or {}
        if status_.get("status_str") != "success":
            errs = [m[1] for m in status_.get("messages", []) if m[0] == "execution_error"]
            if any(m[0] == "execution_interrupted" for m in status_.get("messages", [])):
                raise Cancelled()
            raise RuntimeError("ComfyUI error: %s" % (json.dumps(errs[0])[:600] if errs else status_))
        outs = hist[pid].get("outputs", {}).values()
        if want == "audio":
            hits = [a for o in outs for a in o.get("audio", [])]
        elif want == "video":
            # only what the graph SAVED: LoadVideo nodes also list their input clip (type "input") as a preview, and
            # taking that one returned the reference / anchor clip instead of the render
            hits = [v for o in outs for v in o.get("images", []) + o.get("videos", [])
                    if str(v.get("filename", "")).lower().endswith(".mp4") and v.get("type", "output") == "output"]
        else:
            hits = [i for o in outs for i in o.get("images", []) if i.get("type") == "output"]
        if not hits:
            raise RuntimeError("render finished but produced no %s" % want)
        return hits[0], time.time() - t0


def _pending(pid):
    try:
        q = requests.get(BASE + "/queue", timeout=5).json()
        return any(len(e) > 1 and e[1] == pid for e in q.get("queue_pending", []))
    except Exception:
        return False


def cancel(pid):
    """Interrupt/dequeue ONLY our prompt — never someone else's render."""
    try:
        q = requests.get(BASE + "/queue", timeout=5).json()
        if any(len(e) > 1 and e[1] == pid for e in q.get("queue_running", [])):
            requests.post(BASE + "/interrupt", json={"prompt_id": pid}, timeout=10)
        elif any(len(e) > 1 and e[1] == pid for e in q.get("queue_pending", [])):
            requests.post(BASE + "/queue", json={"delete": [pid]}, timeout=10)
    except Exception:
        pass


def fetch(entry, dest):
    core.safe_path(dest)
    with requests.get(BASE + "/view", params={"filename": entry["filename"], "subfolder": entry.get("subfolder", ""),
                                               "type": entry.get("type", "output")}, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    return dest
