"""MirAI voice - natural local text-to-speech (Kokoro 82M, ONNX, on the CPU: never touches the GPU the renders need).

A long-lived worker process (the engine runtime's own tts-venv) loads Kokoro once and turns one sentence at a time
into a WAV. Results are cached by (text, voice, speed). The worker starts on first use and stops after 10 idle minutes.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time

import core
import console
import platform_util as pu

DEFAULT_VOICE = "af_bella"
VOICES = {   # id: label - the ones offered in the pickers (Kokoro v1.0 English voices)
    "af_bella": "Bella · American, bright", "af_heart": "Heart · American, warm", "af_nicole": "Nicole · American, soft",
    "af_sky": "Sky · American, light", "bf_emma": "Emma · British, calm", "am_michael": "Michael · American male",
    "am_fenrir": "Fenrir · American male, deep", "bm_george": "George · British male",
}
_CFG = core.CONFIG
_RUNTIME = os.path.dirname(os.path.dirname(os.path.dirname(_CFG.get("comfy_python") or ""))) if _CFG.get("comfy_python") else ""
TTS_PY = _CFG.get("tts_python") or (pu.venv_python(os.path.join(_RUNTIME, "tts-venv")) if _RUNTIME else "")
MODELS = _CFG.get("tts_models") or os.path.join(_CFG.get("comfy_root") or "", "models", "kokoro")
CACHE = os.path.join(core.DATA, "tts_cache")
IDLE = 600

_WORKER = r'''
import json, sys, soundfile as sf
from kokoro_onnx import Kokoro
M = sys.argv[1]
k = Kokoro(M + "/kokoro-v1.0.onnx", M + "/voices-v1.0.bin")
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    try:
        r = json.loads(line)
        a, sr = k.create(r["text"], voice=r["voice"], speed=float(r["speed"]), lang="en-gb" if r["voice"][0] == "b" else "en-us")
        sf.write(r["out"], a, sr)
        print(json.dumps({"ok": True, "dur": len(a) / sr}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:300]}), flush=True)
'''

_LOCK = threading.Lock()
_P = {"proc": None, "used": 0.0}


def available():
    return bool(TTS_PY) and os.path.isfile(TTS_PY) and os.path.isfile(os.path.join(MODELS, "kokoro-v1.0.onnx"))


def clean(text):
    """What MirAI says out loud: no markdown, code, links, slash commands or emoji."""
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", " a link ", t)
    t = re.sub(r"[*_#>|~]+", " ", t)
    t = re.sub(r"(^|\s)/[a-z][\w-]*", " ", t)
    t = re.sub(r"--[\w-]+(\s+\d+(\.\d+)?)?", " ", t)
    t = re.sub(r"\be\.g\.", "for example", t, flags=re.I)
    t = re.sub(r"\bi\.e\.", "that is", t, flags=re.I)
    t = re.sub(r"[^\w\s.,!?;:'\"()%$&+-]", " ", t)
    return " ".join(t.split())[:400]


def _start():
    os.makedirs(CACHE, exist_ok=True)
    src = os.path.join(CACHE, "_worker.py")
    with open(src, "w", encoding="utf-8") as f:
        f.write(_WORKER)
    p = subprocess.Popen([TTS_PY, src, MODELS], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, bufsize=1, creationflags=pu.NO_WINDOW)
    ready = json.loads(p.stdout.readline() or "{}")
    if not ready.get("ready"):
        p.kill()
        raise RuntimeError("MirAI voice engine didn't start")
    _P["proc"] = p
    console.emit("VOICE", "voice engine loaded (Kokoro · CPU)")
    threading.Thread(target=_reaper, daemon=True).start()


def _reaper():
    while True:
        time.sleep(30)
        with _LOCK:
            p = _P["proc"]
            if not p:
                return
            if time.time() - _P["used"] > IDLE or p.poll() is not None:
                try:
                    p.kill()
                except Exception:
                    pass
                _P["proc"] = None
                return


def say(text, voice=DEFAULT_VOICE, speed=1.0):
    """-> path of a WAV for one sentence (cached)."""
    text = clean(text)
    if not text:
        raise ValueError("nothing to say")
    voice = voice if voice in VOICES else DEFAULT_VOICE
    speed = min(1.3, max(0.7, float(speed or 1.0)))
    key = hashlib.sha1(("%s|%s|%.2f" % (text, voice, speed)).encode("utf-8")).hexdigest()[:20]
    out = os.path.join(CACHE, key + ".wav")
    if os.path.isfile(out):
        return out
    if not available():
        raise RuntimeError("MirAI voice isn't installed - run MirMediaLabs-Setup.exe (Repair)")
    with _LOCK:
        if not _P["proc"] or _P["proc"].poll() is not None:
            _start()
        _P["used"] = time.time()
        p = _P["proc"]
        t0 = time.time()
        p.stdin.write(json.dumps({"text": text, "voice": voice, "speed": speed, "out": out}) + "\n")
        p.stdin.flush()
        r = json.loads(p.stdout.readline() or "{}")
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "voice failed")
    console.emit("VOICE", "speaking · %s · %.1f s audio in %.1f s" % (voice, r.get("dur", 0), time.time() - t0))
    _prune()
    return out


def _prune(keep=400):
    try:
        fs = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith(".wav")), key=os.path.getmtime)
        for f in fs[:-keep]:
            os.remove(f)
    except Exception:
        pass
