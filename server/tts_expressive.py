r"""EXPRESSIVE NARRATOR — Chatterbox (Resemble AI, MIT) for Motion Studio (picked after a blind listening test
against Kokoro and IndexTTS2). Same shape as tts.py: one persistent worker process (its own venv
a venv you point expressive_python at, PyTorch with CUDA), JSON lines over stdin, cached WAVs, unloaded when idle.

Voices stay the Kokoro picker list: each voice id is CLONED from a short Kokoro sample of that voice (made once, cached), so
"Michael" sounds like Michael — but acted. Acting = `exaggeration` (0.25 calm … 1.0 wild) + `cfg` (lower = slower, more
deliberate). Motion Studio maps each scene's mood and the project's intensity onto them (motion_wizard.acting()).
While it voices, a lock file asks the AI-art batch to keep off the GPU (mg_assets/build_art.py checks it).
"""
import hashlib
import json
import os
import subprocess
import threading
import time

import core
import engines

PY = engines.expressive_python()      # optional Chatterbox (MIT) venv; empty = off, Kokoro speaks
CACHE = os.path.join(core.DATA, "tts_expressive")
LOCKFILE = os.path.join(core.DATA, "gpu_voice.lock")
IDLE = 300
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
REF_TEXT = "I've always loved walking through the city at night, when the streets are quiet and the lights are warm."

_WORKER = r'''
import json, sys, soundfile as sf, torch
from chatterbox.tts import ChatterboxTTS
dev = "cuda" if torch.cuda.is_available() else "cpu"
m = ChatterboxTTS.from_pretrained(device=dev)
print(json.dumps({"ready": True, "device": dev}), flush=True)
for line in sys.stdin:
    try:
        r = json.loads(line)
        wav = m.generate(r["text"], audio_prompt_path=r["ref"], exaggeration=float(r["ex"]), cfg_weight=float(r["cfg"]))
        a = wav.squeeze(0).cpu().numpy()
        sf.write(r["out"], a, m.sr)
        print(json.dumps({"ok": True, "dur": len(a) / m.sr}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:300]}), flush=True)
'''

_LOCK = threading.Lock()
_P = {"proc": None, "used": 0.0, "device": ""}


def available():
    return bool(PY) and os.path.isfile(PY)


def _start():
    os.makedirs(CACHE, exist_ok=True)
    src = os.path.join(CACHE, "_worker.py")
    with open(src, "w", encoding="utf-8") as f:
        f.write(_WORKER)
    p = subprocess.Popen([PY, src], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, creationflags=NO_WINDOW)
    ready = {}
    for _ in range(20):                      # the model prints a few banner lines before our ready line
        ln = p.stdout.readline()
        if not ln:
            break
        try:
            ready = json.loads(ln)
            if ready.get("ready"):
                break
        except ValueError:
            continue
    if not ready.get("ready"):
        p.kill()
        raise RuntimeError("the expressive voice engine didn't start")
    _P.update(proc=p, device=ready.get("device", ""))
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


def ref_for(voice):
    """A clean Kokoro sample of the picker voice → the timbre Chatterbox clones."""
    from . import tts
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, "ref_%s.wav" % voice)
    if not os.path.isfile(out):
        import shutil
        shutil.copy2(tts.say(REF_TEXT, voice, 1.0), out)
    return out


def gpu_lock(on=True):
    try:
        if on:
            open(LOCKFILE, "w").write(str(time.time()))
        elif os.path.isfile(LOCKFILE):
            os.remove(LOCKFILE)
    except OSError:
        pass


def say(text, voice, ex=0.6, cfg=0.4):
    """→ path of a WAV of `text` in `voice`, acted with exaggeration `ex` (cached)."""
    from . import tts
    text = tts.clean(text)
    if not text:
        raise ValueError("nothing to say")
    voice = voice if voice in tts.VOICES else tts.DEFAULT_VOICE
    ex, cfg = max(0.25, min(1.0, float(ex))), max(0.2, min(0.8, float(cfg)))
    key = hashlib.sha1(("%s|%s|%.2f|%.2f" % (text, voice, ex, cfg)).encode("utf-8")).hexdigest()[:20]
    out = os.path.join(CACHE, key + ".wav")
    if os.path.isfile(out):
        return out
    ref = ref_for(voice)
    with _LOCK:
        if not _P["proc"] or _P["proc"].poll() is not None:
            _start()
        _P["used"] = time.time()
        p = _P["proc"]
        p.stdin.write(json.dumps({"text": text, "ref": ref, "ex": ex, "cfg": cfg, "out": out}) + "\n")
        p.stdin.flush()
        r = {}
        while True:
            ln = p.stdout.readline()
            if not ln:
                break
            try:
                r = json.loads(ln)
                if "ok" in r:
                    break
            except ValueError:
                continue
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "expressive voice failed")
    return out


def unload():
    with _LOCK:
        if _P["proc"]:
            try:
                _P["proc"].kill()
            except Exception:
                pass
            _P["proc"] = None
