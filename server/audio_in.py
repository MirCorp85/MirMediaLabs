"""Your own audio for a MirAI project (Oct 11 2026).

Modes (wizard → setup.audio = {"mode", "file", "enhance"}):
  make         — MirAI writes + records the song (the old default)
  own          — use my audio as the soundtrack exactly (a song, a voice-over, a promo read — no music added)
  voice_music  — my voice + a music bed the lab composes to fit under it (ducked, -14 LUFS)
  remix        — the lab turns my audio into a song: it hears my words and sings them in the chosen style
  remix_me     — same, then ACE-Step 1.5 VOICE SWAP re-sings it in MY voice (my recording = the timbre sample)
"enhance" (any mode with a file) cleans the recording first: hum/rumble cut, denoise, de-ess, voice EQ, level.
"""
import os
import re
import subprocess
import time

try:
    from . import core
except ImportError:
    import core

MODES = ("make", "own", "voice_music", "remix", "remix_me")
AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".mp4", ".mov", ".webm")


def _ff(args, timeout=900):
    return subprocess.run([core.FFMPEG, "-hide_banner", "-y"] + args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(core, "NO_WINDOW", 0))


def seconds(path):
    r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                       creationflags=getattr(core, "NO_WINDOW", 0))
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _add(name, prompt, uid, session=""):
    core.index_add(name, {"prompt": prompt, "model": "upload", "created": time.time(), "user": uid or "owner",
                          **({"session": session} if session else {})})


def save_upload(fs, uid, enhance_it=False, session=""):
    """Werkzeug FileStorage → library audio (video uploads keep only their sound). → {name, secs, enhanced}"""
    ext = os.path.splitext(fs.filename or "")[1].lower()
    if ext not in AUDIO_EXT:
        raise ValueError("attach an audio file (mp3, wav, m4a, flac…) or a video to take the sound from")
    raw = os.path.join(core.LIB, core.new_name("myaudio_raw", ext))
    fs.save(raw)
    name = core.new_name("myaudio", ".wav")
    r = _ff(["-i", raw, "-vn", "-ac", "2", "-ar", "48000", os.path.join(core.LIB, name)])
    os.remove(raw)
    if r.returncode:
        raise ValueError("couldn't read that file's audio")
    title = os.path.splitext(os.path.basename(fs.filename))[0][:80]
    _add(name, "My audio: " + title, uid, session)
    if enhance_it:
        name = enhance(name, uid, session)
    return {"name": name, "secs": round(seconds(os.path.join(core.LIB, name)), 2), "enhanced": bool(enhance_it), "title": title}


def enhance(name, uid="owner", session=""):
    """Studio clean-up for a voice / recording → a new library file (the original stays)."""
    src = core.in_dir(core.LIB, name)
    out = core.new_name("myaudio_enhanced", ".wav")
    af = ("highpass=f=75,lowpass=f=16000,afftdn=nr=12:nf=-30:tn=1,deesser=i=0.4,"
          "equalizer=f=200:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,"
          "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
          "loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000")
    r = _ff(["-i", src, "-af", af, "-ac", "2", os.path.join(core.LIB, out)])
    if r.returncode:
        raise ValueError("enhance failed: " + r.stderr[-300:])
    _add(out, "My audio (enhanced)", uid, session)
    return out


def mix_bed(voice, bed, uid="owner", session=""):
    """Voice on top, the composed bed ducked under it (sidechain) → a library file the same length as the voice."""
    v, b = core.in_dir(core.LIB, voice), core.in_dir(core.LIB, bed)
    out = core.new_name("myaudio_mix", ".wav")
    fc = ("[1:a]volume=0.55,aresample=48000[bg];[0:a]aresample=48000,asplit=2[vo][sc];"
          "[bg][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];"
          "[vo][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11")
    r = _ff(["-i", v, "-stream_loop", "-1", "-i", b, "-filter_complex", fc, "-ac", "2", os.path.join(core.LIB, out)])
    if r.returncode:
        raise ValueError("mixing the music under your voice failed: " + r.stderr[-300:])
    _add(out, "My voice + music bed", uid, session)
    return out


def bed_caption(song):
    song = song or {}
    bits = [song.get("genre") or "cinematic corporate", song.get("mood") or "uplifting"]
    if song.get("bpm"):
        bits.append("%s BPM" % song["bpm"])
    return "instrumental background music, " + ", ".join(bits) + ", no vocals, steady, leaves room for a voice-over"


def transcript(name):
    """The words in my audio (for remix: the lab sings them)."""
    try:
        from . import series_audio as sa
    except ImportError:
        import series_audio as sa
    got = sa.words_of(core.in_dir(core.LIB, name))
    words = [w.get("w") or w.get("word") or w.get("text") or "" for w in got.get("words") or []]
    text = " ".join(x.strip() for x in words if x.strip())
    lines, cur = [], []
    for w in text.split():                       # ~7 words per sung line
        cur.append(w)
        if len(cur) >= 7 or w.endswith((".", "!", "?")):
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)[:3500]
