"""SERIES audio — hear an uploaded song: vocal stem (Demucs) + every sung word with its time (Whisper), then lines and
sections. The heavy work runs in a CHILD process (python series_audio.py stems|words …) so a crash or the RAM of the
speech models never touches the lab. CPU by default: ComfyUI usually holds the GPU. Identical in the MirOS copy.

    python series_audio.py stems <song> <out_dir>      → prints {"vocal": path}
    python series_audio.py words <wav> [model] [lang]  → prints {"words": [{"w","s","e"}], "lang": ".."}
"""
import json
import os
import re
import subprocess
import sys

WHISPER_MODEL = "small"
GAP_LINE = 0.6            # a pause this long (s) ends a sung line
GAP_SECTION = 3.0         # a pause this long splits sections (instrumental between them)
LINE_MAX = 9              # words per line at most


def _python():
    """python.exe next to the lab's interpreter (the lab itself runs under pythonw)."""
    exe = sys.executable
    alt = os.path.join(os.path.dirname(exe), "python.exe")
    return alt if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(alt) else exe


def _ffmpeg():
    try:
        try:
            from . import core
        except ImportError:
            import core
        return core.FFMPEG
    except Exception:
        return "ffmpeg"


def _child(args, timeout):
    r = subprocess.run([_python(), os.path.abspath(__file__)] + args, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                       env=dict(os.environ, PYTHONIOENCODING="utf-8", SERIES_FFMPEG=_ffmpeg()))
    last = next((l for l in reversed((r.stdout or "").splitlines()) if l.startswith("{")), None)
    if r.returncode != 0 or not last:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
        msg = " | ".join(tail)
        if "No module named" in msg:
            msg = "speech tools are not installed on this PC (%s)" % msg
        raise RuntimeError(msg[-400:] or "audio tool failed")
    return json.loads(last)


def vocal_stem(song, out_dir):
    """→ path of the isolated vocal (wav)."""
    return _child(["stems", song, out_dir], 1800)["vocal"]


def words_of(wav, model=WHISPER_MODEL, lang=None):
    return _child(["words", wav, model] + ([lang] if lang else []), 3600)


# ── words → lines → sections (pure, runs in the lab) ───────────────────────────────────────────────────────────────
def _norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def lines_of(words):
    lines, cur = [], []
    for w in words:
        if cur and (w["s"] - cur[-1]["e"] > GAP_LINE or len(cur) >= LINE_MAX):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return [{"text": " ".join(x["w"] for x in l).strip(), "s": l[0]["s"], "e": l[-1]["e"]} for l in lines]


def sections_of(words, secs):
    """Sung blocks split by long pauses; the gaps become instrumental sections; blocks whose lines repeat = Chorus."""
    lines = lines_of(words)
    if not lines:
        return [{"tag": "Instrumental", "kind": "action", "lines": [], "start": 0.0, "end": secs, "singer": "", "idea": ""}]
    blocks, cur = [], [lines[0]]
    for l in lines[1:]:
        if l["s"] - cur[-1]["e"] > GAP_SECTION:
            blocks.append(cur)
            cur = []
        cur.append(l)
    blocks.append(cur)
    def grams(b):                                      # 3-word phrases of a block (chorus = phrases that come back)
        w = _norm(" ".join(l["text"] for l in b)).split()
        return {" ".join(w[i:i + 3]) for i in range(max(0, len(w) - 2))}
    gs = [grams(b) for b in blocks]
    out, verse, t = [], 0, 0.0
    for k, b in enumerate(blocks):
        s, e = b[0]["s"], b[-1]["e"]
        if s - t > GAP_SECTION:
            out.append({"tag": "Intro" if not out else "Break", "kind": "action", "lines": [], "start": t, "end": s, "singer": "", "idea": ""})
        others = set().union(*[g for j, g in enumerate(gs) if j != k]) if len(gs) > 1 else set()
        rep = bool(gs[k]) and len(gs[k] & others) >= 0.4 * len(gs[k])
        if not rep:
            verse += 1
        out.append({"tag": "Chorus" if rep else "Verse %d" % verse, "kind": "sing", "lines": [l["text"] for l in b],
                    "start": s, "end": e, "singer": "", "idea": ""})
        t = e
    if secs - t > GAP_SECTION:
        out.append({"tag": "Outro", "kind": "action", "lines": [], "start": t, "end": secs, "singer": "", "idea": ""})
    # sections touch: each one runs to the next one's start (short gaps belong to the section before)
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"] = round((a["end"] + b["start"]) / 2, 3) if b["start"] > a["end"] else a["end"]
    out[0]["start"], out[-1]["end"] = 0.0, secs
    return out


def lyrics_text(sections):
    return "\n\n".join("[%s]\n%s" % (s["tag"], "\n".join(s["lines"])) if s["lines"] else "[%s]" % s["tag"] for s in sections)


# ── child-process entry points ─────────────────────────────────────────────────────────────────────────────────────
def _stems(song, out_dir):
    import demucs.separate
    os.makedirs(out_dir, exist_ok=True)
    demucs.separate.main(["--two-stems", "vocals", "-n", "htdemucs", "-d", "cpu", "-o", out_dir, "--filename",
                          "{track}_{stem}.{ext}", song])
    stem = os.path.splitext(os.path.basename(song))[0]
    vocal = os.path.join(out_dir, "htdemucs", stem + "_vocals.wav")
    if not os.path.isfile(vocal):
        raise RuntimeError("demucs wrote no vocal stem")
    return {"vocal": vocal}


def _pcm16k(path):
    """Decode with the lab's own ffmpeg (Whisper's loader wants an ffmpeg on PATH, which this PC doesn't have)."""
    import numpy as np
    r = subprocess.run([os.environ.get("SERIES_FFMPEG") or "ffmpeg", "-nostdin", "-i", path, "-f", "f32le", "-ac", "1",
                        "-ar", "16000", "-"], capture_output=True, timeout=600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("could not read the audio: " + r.stderr.decode("utf-8", "replace")[-200:])
    return np.frombuffer(r.stdout, np.float32).copy()


def _words(wav, model=WHISPER_MODEL, lang=None):
    import whisper
    m = whisper.load_model(model, device="cpu")
    r = m.transcribe(_pcm16k(wav), word_timestamps=True, language=lang, fp16=False, condition_on_previous_text=False,
                     no_speech_threshold=0.5, initial_prompt="Song lyrics.")
    words = []
    for seg in r.get("segments") or []:
        if seg.get("no_speech_prob", 0) > 0.8 and seg.get("avg_logprob", 0) < -1.0:
            continue                                   # hallucinated text over an instrumental passage
        for w in seg.get("words") or []:
            t = (w.get("word") or "").strip()
            if t:
                words.append({"w": t, "s": round(float(w["start"]), 3), "e": round(float(w["end"]), 3)})
    return {"words": words, "lang": r.get("language")}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "stems":
        out = _stems(sys.argv[2], sys.argv[3])
    elif cmd == "words":
        out = _words(sys.argv[2], *(sys.argv[3:5]))
    else:
        raise SystemExit("unknown command")
    print(json.dumps(out))
