"""Live backend events for the MirAI bubble's one-line console.

Every headless piece of the lab (worker, MirAI router, Ollama, ComfyUI and its log, GPU) calls emit(); the bubble
shows the newest line for its job. Lines are plain English: explain.py turns ComfyUI node classes into what the
model is actually doing ("KSampler" -> "denoising - each step sharpens the frames").
"""
import collections
import os
import threading
import time

import core

_LOCK = threading.Lock()
_RING = collections.deque(maxlen=2000)
_SEQ = [0]
_LATEST = {}          # job id -> newest line for that job
_GLOBAL = [None]      # newest engine-wide line (GPU, model loads, other users' queue) - host only


def emit(src, text, job=None, level="info"):
    """src: LAB · MirAI · COMFY · GPU · IMG · VID · SONG · TEXT. job: a job dict or id (None = engine-wide)."""
    jid = job.get("id") if isinstance(job, dict) else job
    text = " ".join(str(text).split())[:160]
    if not text:
        return
    with _LOCK:
        _SEQ[0] += 1
        ln = {"seq": _SEQ[0], "t": time.time(), "src": src, "text": text, "job": jid, "level": level}
        _RING.append(ln)
        if jid:
            _LATEST[jid] = ln
            if len(_LATEST) > 400:
                for k in list(_LATEST)[:100]:
                    _LATEST.pop(k, None)
        else:
            _GLOBAL[0] = ln


def latest(job_ids, host=False):
    """{job id: line} for the given jobs; the host also gets the newest engine-wide line when it is newer."""
    with _LOCK:
        out = {j: dict(_LATEST[j]) for j in job_ids if j in _LATEST}
        g = _GLOBAL[0]
    if host and g:
        for j in job_ids:
            if j in out and g["seq"] > out[j]["seq"] and time.time() - g["t"] < 20:
                out[j] = dict(g)
    return out, _SEQ[0]


# -- ComfyUI log tail: model loads, VRAM moves, OOM - the stuff the websocket never says ----------------------
_SKIP = ("it/s]", "s/it]", "%|", "Prompt executed", "got prompt", "To see the GUI", "Starting server")
_KEEP = (("Requested to load", "loading model"), ("loaded completely", "model fully in VRAM"),
         ("loaded partially", "model partly offloaded to RAM (low VRAM)"), ("Unloaded", "freeing VRAM"),
         ("out of memory", "OUT OF VRAM"), ("OutOfMemory", "OUT OF VRAM"), ("Error", "engine error"),
         ("model weight dtype", "model precision"), ("lora key not loaded", "LoRA key skipped"))
_CUR = {"job": None}


def set_current(jid):
    """The job the GPU is working on now - ComfyUI log lines are tagged to it."""
    _CUR["job"] = jid


def _tail(path, src):
    pos = os.path.getsize(path) if os.path.exists(path) else 0
    while True:
        time.sleep(1.0)
        try:
            if not os.path.exists(path):
                continue
            size = os.path.getsize(path)
            if size < pos:
                pos = 0
            if size == pos:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                chunk = f.read(64 * 1024)
                pos = f.tell()
            for raw in chunk.splitlines():
                s = raw.strip()
                if not s or any(k in s for k in _SKIP):
                    continue
                hit = next((lbl for k, lbl in _KEEP if k.lower() in s.lower()), None)
                if hit:
                    emit(src, hit + " · " + s[:110], _CUR["job"], "warn" if "VRAM" in hit or "error" in hit else "info")
        except Exception:
            time.sleep(5)


def start():
    for name in ("comfy_engine_out.log", "comfy_engine_err.log"):
        threading.Thread(target=_tail, args=(os.path.join(core.LOGS, name), "COMFY"), daemon=True).start()
