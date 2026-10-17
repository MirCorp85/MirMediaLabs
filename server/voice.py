"""MUSE live voice - talk to the lab hands-free (ported from MIR VoiceServer, adapted: no MIR server, no finance).

The page listens (energy VAD, barge-in), sends each utterance here; a long-lived whisper worker (CPU - the GPU belongs
to the renders) turns it into text. The page then sends that text to MirAI like a typed message (model "auto", so she
chats OR renders), and speaks the reply with the Kokoro voice (/api/tts). The worker stops after 10 idle minutes.
"""
import json
import os
import subprocess
import sys
import threading
import time

import core
import console

MODEL = core.CONFIG.get("voice_stt_model") or "base"
IDLE = 600

_WORKER = r'''
import json, sys, whisper
m = whisper.load_model(sys.argv[1], device="cpu")
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    try:
        r = json.loads(line)
        out = m.transcribe(r["wav"], fp16=False, language=r.get("lang") or None, condition_on_previous_text=False,
                           no_speech_threshold=0.6)
        segs = [s for s in out.get("segments") or [] if s.get("no_speech_prob", 0) < 0.6]
        print(json.dumps({"ok": True, "text": " ".join(s["text"].strip() for s in segs).strip(),
                          "lang": out.get("language", "")}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:300]}), flush=True)
'''

_LOCK = threading.Lock()
_P = {"proc": None, "used": 0.0}
TMP = os.path.join(core.DATA, "voice_tmp")
# whisper's favourite hallucinations on silence / room noise
_JUNK = {"", "you", "thank you", "thanks for watching", "thank you for watching", "bye", ".", "okay", "so"}


def _python():
    exe = sys.executable
    alt = os.path.join(os.path.dirname(exe), "python.exe")
    return alt if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(alt) else exe


def _start():
    _P["proc"] = subprocess.Popen([_python(), "-c", _WORKER, MODEL], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8",
                                           PATH=os.path.dirname(core.FFMPEG) + os.pathsep + os.environ.get("PATH", "")))
    ready = json.loads(_P["proc"].stdout.readline() or "{}")
    if not ready.get("ready"):
        _P["proc"] = None
        raise RuntimeError("speech recognition isn't installed on this PC")
    console.emit("VOICE", "MUSE ears ready (whisper %s, CPU)" % MODEL)
    threading.Thread(target=_reaper, daemon=True).start()


def _reaper():
    while True:
        time.sleep(30)
        with _LOCK:
            p = _P["proc"]
            if not p or p.poll() is not None:
                return
            if time.time() - _P["used"] > IDLE:
                try:
                    p.kill()
                except Exception:
                    pass
                _P["proc"] = None
                return


def warm():
    with _LOCK:
        if not _P["proc"] or _P["proc"].poll() is not None:
            _start()
        _P["used"] = time.time()


def hear(fs, lang=None):
    """uploaded audio (any format ffmpeg reads) -> what was said ('' = nothing worth answering)."""
    os.makedirs(TMP, exist_ok=True)
    stamp = "%d_%d" % (time.time() * 1000, threading.get_ident())
    raw, wav = os.path.join(TMP, stamp + ".in"), os.path.join(TMP, stamp + ".wav")
    try:
        fs.save(raw)
        subprocess.run([core.FFMPEG, "-hide_banner", "-y", "-i", raw, "-ac", "1", "-ar", "16000", wav],
                       capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not os.path.isfile(wav):
            raise RuntimeError("couldn't read the recording")
        t0 = time.time()
        with _LOCK:
            if not _P["proc"] or _P["proc"].poll() is not None:
                _start()
            _P["used"] = time.time()
            p = _P["proc"]
            p.stdin.write(json.dumps({"wav": wav, "lang": lang}) + "\n")
            p.stdin.flush()
            r = json.loads(p.stdout.readline() or "{}")
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "speech recognition failed")
        text = (r.get("text") or "").strip()
        if text.lower().strip(" .!?,") in _JUNK:
            text = ""
        console.emit("VOICE", "MUSE heard (%.1f s): %s" % (time.time() - t0, text[:80] or "-"))
        return text
    finally:
        for f in (raw, wav):
            try:
                os.remove(f)
            except Exception:
                pass
