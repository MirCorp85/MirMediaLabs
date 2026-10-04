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

LOCAL = os.environ.get("LOCALAPPDATA", "")
_CFG = core.CONFIG                   # set by the installer; empty on the build PC (Comfy Desktop paths)
COMFY_ROOT = _CFG.get("comfy_root") or os.path.join(LOCAL, "Comfy-Desktop", "ComfyUI-Installs", "ComfyUI")
COMFY_PY = _CFG.get("comfy_python") or os.path.join(COMFY_ROOT, "ComfyUI", ".venv", "Scripts", "python.exe")
COMFY_SHARED = _CFG.get("comfy_shared") or os.path.join(LOCAL, "Comfy-Desktop", "ComfyUI-Shared")
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
            raise RuntimeError("ComfyUI engine not found — run MirMediaLabs-Setup.exe (Repair)")
        busy = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*ComfyUI*main.py*--port 8188*' }).Count"],
            capture_output=True, text=True, timeout=20, creationflags=core.NO_WINDOW).stdout.strip()
        if busy and busy != "0":
            # an engine process exists but isn't answering: give it a grace period (it may be loading),
            # then treat it as frozen (crashed but still holding :8188), kill it and start fresh
            t0 = time.time()
            while time.time() - t0 < 60 and not up():
                time.sleep(3)
            if up():
                return True
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*ComfyUI*main.py*--port 8188*' } | "
                            "ForEach-Object { taskkill /F /T /PID $_.ProcessId }"],
                           capture_output=True, timeout=30, creationflags=core.NO_WINDOW)
            time.sleep(3)
            busy = "0"
        if not busy or busy == "0":
            cmd = [COMFY_PY, "-s", os.path.join("ComfyUI", "main.py"), "--listen", "127.0.0.1", "--port", "8188",
                   "--input-directory", os.path.join(COMFY_SHARED, "input"),
                   "--output-directory", os.path.join(COMFY_SHARED, "output")] + (_CFG.get("comfy_args") or [])
            yml = _model_paths_yaml()
            if yml:
                cmd += ["--extra-model-paths-config", yml]
            with open(os.path.join(core.LOGS, "comfy_engine_out.log"), "a") as lf, \
                    open(os.path.join(core.LOGS, "comfy_engine_err.log"), "a") as ef:
                subprocess.Popen(cmd, cwd=COMFY_ROOT, stdout=lf, stderr=ef, creationflags=0x00000008 | core.NO_WINDOW)
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


def run(graph, want, job, timeout_s=120 * 60):
    """Submit a graph, wait for it, return the first output entry of kind want
    ('video' | 'audio' | 'image'). job['_cancel'] aborts; job['comfy_pid'] is recorded."""
    if job.get("loras"):                   # LoRA Samples picked for this render → chain them onto the model
        try:
            from . import loras as _loras
        except ImportError:
            import loras as _loras
        graph = _loras.apply(graph, job)
    r = requests.post(BASE + "/prompt", json={"prompt": graph}, timeout=20)
    d = r.json()
    if r.status_code != 200 or "prompt_id" not in d:
        raise RuntimeError("ComfyUI rejected the graph: %s" % json.dumps(d.get("node_errors") or d.get("error") or d)[:600])
    pid, t0 = d["prompt_id"], time.time()
    job["comfy_pid"] = pid
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
            job["stage"] = "queued in ComfyUI" if _pending(pid) else "rendering"
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
            hits = [v for o in outs for v in o.get("images", []) + o.get("videos", [])
                    if str(v.get("filename", "")).lower().endswith(".mp4")]
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
