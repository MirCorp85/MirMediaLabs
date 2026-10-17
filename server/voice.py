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
STT_DIR = core.CONFIG.get("voice_stt_dir") or ""          # installer: <install>\engine\models\whisper (pre-downloaded)
IDLE = 600
READY_S = 600                                          # first start may download the ~150 MB model

# Self-contained worker. Installed PCs: faster-whisper (CTranslate2, CPU int8) in the voice runtime (tts-venv);
# the dev source falls back to openai-whisper. argv: model, download dir ("" = default cache).
_WORKER = r'''
import json, sys
name, root = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "") or None
try:
    from faster_whisper import WhisperModel
    m = WhisperModel(name, device="cpu", compute_type="int8", download_root=root)
    import soundfile as sf                       # the wav is already 16 kHz mono (ffmpeg): no PyAV decode
    def tr(wav, lang):
        audio, _sr = sf.read(wav, dtype="float32")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        segs, info = m.transcribe(audio, language=lang or None, condition_on_previous_text=False, vad_filter=True)
        return " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.6).strip(), info.language
except ImportError:
    import whisper
    m = whisper.load_model(name, device="cpu", download_root=root)
    def tr(wav, lang):
        out = m.transcribe(wav, fp16=False, language=lang or None, condition_on_previous_text=False, no_speech_threshold=0.6)
        segs = [s for s in out.get("segments") or [] if s.get("no_speech_prob", 0) < 0.6]
        return " ".join(s["text"].strip() for s in segs).strip(), out.get("language", "")
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    try:
        r = json.loads(line)
        text, lang = tr(r["wav"], r.get("lang"))
        print(json.dumps({"ok": True, "text": text, "lang": lang}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:300]}), flush=True)
'''
NO_EARS = "MUSE's ears (speech recognition) aren't installed on this PC — run MirMediaLabs-Setup.exe and choose Repair"

_LOCK = threading.Lock()
_P = {"proc": None, "used": 0.0}
TMP = os.path.join(core.DATA, "voice_tmp")
# whisper's favourite hallucinations on silence / room noise
_JUNK = {"", "you", "thank you", "thanks for watching", "thank you for watching", "bye", ".", "okay", "so"}


def _has(py, mods):
    try:
        return subprocess.run([py, "-c", "import importlib.util as u,sys;sys.exit(0 if any(u.find_spec(m) for m in %r) else 1)" % (mods,)],
                              capture_output=True, timeout=60,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
    except Exception:
        return False


_PY = {}


def _python():
    """The interpreter that runs the ears. NEVER sys.executable in the compiled PC edition (that is MirMediaLabs.exe):
    config stt_python → the voice runtime (tts-venv, faster-whisper) → this Python on a source install."""
    if "py" in _PY:
        return _PY["py"]
    try:
        import tts
        cands = [core.CONFIG.get("stt_python"), tts.TTS_PY]
    except Exception:
        cands = [core.CONFIG.get("stt_python")]
    compiled = "__compiled__" in globals() or getattr(sys, "frozen", False)
    if not compiled:
        exe = sys.executable
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        cands.append(alt if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(alt) else exe)
    for py in cands:
        if py and os.path.isfile(py) and _has(py, ("faster_whisper", "whisper")):
            _PY["py"] = py
            return py
    raise RuntimeError(NO_EARS)


def _start():
    p = subprocess.Popen([_python(), "-c", _WORKER, MODEL, STT_DIR], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         env=dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_DISABLE_TELEMETRY="1",
                                  PATH=os.path.dirname(core.FFMPEG) + os.pathsep + os.environ.get("PATH", "")))
    got = []
    t = threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True)
    t.start()
    t.join(READY_S)                                     # never hang a request on a worker that won't start
    try:
        ready = json.loads(got[0] if got else "{}")
    except ValueError:
        ready = {}
    if not ready.get("ready"):
        try:
            p.kill()
        except Exception:
            pass
        _P["proc"] = None
        _PY.pop("py", None)
        raise RuntimeError(NO_EARS if not got else "MUSE's ears didn't start (speech model failed to load)")
    _P["proc"] = p
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
