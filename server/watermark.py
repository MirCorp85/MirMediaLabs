"""MIR MEDIA LABS watermark — every finished render is marked before it reaches the library.

  * images + video: a small, semi-transparent "MIR MEDIA LABS" mark in the bottom-right corner
  * video + audio: an "AI-generated with MIR MEDIA LABS" tag in the file's metadata

On by default. Host prefs: "watermark" (false = off) and "watermark_text" (the visible text).
ffmpeg only (drawtext) — the compiled PC edition ships no Pillow. Runs once per file (the library
index remembers "wm"), and a failure never fails the render.
"""
import os
import subprocess

import core

TAG = "AI-generated with MIR MEDIA LABS"
IMAGE = (".png", ".jpg", ".jpeg", ".webp")
VIDEO = (".mp4", ".mov", ".webm", ".mkv")
AUDIO = (".mp3", ".wav", ".flac", ".m4a", ".ogg")
FONTS = ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")


def enabled():
    return core.prefs().get("watermark", True) is not False


def text():
    return (core.prefs().get("watermark_text") or "MIR MEDIA LABS").strip()[:40] or "MIR MEDIA LABS"


def _esc(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _drawtext(txtfile):
    """Text ~3.2% of the short side, 2.5% margin, white @70% with a soft shadow. Text comes from a file
    so no quoting of user text inside the filtergraph."""
    font = next((f for f in FONTS if os.path.exists(f)), None)
    vf = ("drawtext=textfile='%s':fontsize='max(12,min(w,h)*0.032)':fontcolor=white@0.72"
          ":shadowcolor=black@0.45:shadowx=1:shadowy=1"
          ":x='w-tw-max(8,min(w,h)*0.025)':y='h-th-max(8,min(w,h)*0.025)'") % _esc(txtfile)
    return vf + (":fontfile='%s'" % _esc(font) if font else "")


def _ffmpeg(args):
    r = subprocess.run([core.FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + args, capture_output=True,
                       text=True, timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: %s" % (r.stderr or "")[-300:])


def _visible(path, video):
    ext = os.path.splitext(path)[1]
    tmp, txt = path + ".wm" + ext, path + ".wm.txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write(text())
    try:
        if video:
            _ffmpeg(["-i", path, "-vf", _drawtext(txt), "-map", "0:v", "-map", "0:a?", "-c:v", "libx264", "-crf", "16",
                     "-pix_fmt", "yuv420p", "-c:a", "copy", "-metadata", "comment=" + TAG, "-movflags", "+faststart", tmp])
        else:
            q = ["-q:v", "2"] if ext.lower() in (".jpg", ".jpeg") else (["-quality", "95"] if ext.lower() == ".webp" else [])
            _ffmpeg(["-i", path, "-vf", _drawtext(txt), "-frames:v", "1", "-update", "1"] + q + [tmp])
        os.replace(tmp, path)
    finally:
        for p in (tmp, txt):
            if os.path.exists(p):
                os.remove(p)


def _tag(path):
    """Metadata only (audio): stream copy, no re-encode."""
    tmp = path + ".wm" + os.path.splitext(path)[1]
    try:
        _ffmpeg(["-i", path, "-map", "0", "-c", "copy", "-metadata", "comment=" + TAG,
                 "-metadata", "encoded_by=MIR MEDIA LABS", tmp])
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def apply(files, log=None):
    """Mark each new library file once. Returns how many were marked."""
    if not enabled():
        return 0
    ix, done = core.index(), []
    for fn in files or []:
        p = core.in_dir(core.LIB, fn)
        if not p or not os.path.exists(p) or (ix.get(fn) or {}).get("wm"):
            continue
        ext = os.path.splitext(fn)[1].lower()
        try:
            if ext in IMAGE:
                _visible(p, False)
            elif ext in VIDEO:
                _visible(p, True)
            elif ext in AUDIO:
                _tag(p)
            else:
                continue
            done.append(fn)
        except Exception as e:                         # never lose a finished render over its watermark
            if log:
                log("watermark skipped for %s: %s" % (fn, str(e)[:160]))
    if done:
        ix = core.index()                              # re-read: don't clobber entries written meanwhile
        for fn in done:
            if fn in ix:
                ix[fn]["wm"] = 1
        core.save_json(core.INDEX_FILE, ix)
    return len(done)
