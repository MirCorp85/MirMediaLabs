"""
editor.py — MIR MEDIA LABS timeline video editor (server side).
═══════════════════════════════════════════════════════════════════════════════
IDENTICAL in both copies (standalone server/editor.py and MirOS aimr-trading/miros_mlab/editor.py) —
the media-lab sync rule: copy, never import across. Each copy wires it in with
    editor.register(app, hooks)
where hooks gives the copy's own auth helpers (uid, my_file, my_ref, store_ref, ref_info, can_attach).

What it does (ffmpeg only — the compiled PC edition ships no Pillow / numpy):
  • projects     data/editor/projects/<user>/<id>.json  (tracks → clips, saved by the web editor)
  • probe        duration / size / fps / audio of a library item or attachment
  • strip, wave  filmstrip sprites + waveform peaks for the timeline (cached in data/editor/cache)
  • frame, cut   a frame / a trimmed segment of the timeline → a lab attachment (refs/) so every AI
                 engine can use it (animate, extend, restyle, re-score, cover …) — the editor's AI tools
                 are the lab's own /api/generate with these refs, so nothing here knows engine names
  • render       the whole timeline (or a range) → one MP4 in the library: multi-track video layers with
                 trim / speed / fit / position / scale / opacity / colour / looks / fades / crossfades,
                 image clips with Ken Burns motion, text titles, and an audio mix of every clip with
                 volume, fades and speed. Progress is live (ffmpeg -progress).
"""
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import threading
import time
import uuid

try:                      # MirOS copy lives in the miros_mlab package
    from . import core
except ImportError:       # standalone server runs its modules flat
    import core

ED = os.path.join(core.DATA, "editor")
PROJ = os.path.join(ED, "projects")
CACHE = os.path.join(ED, "cache")
TMP = os.path.join(ED, "tmp")
for _d in (PROJ, CACHE, TMP):
    os.makedirs(_d, exist_ok=True)

RENDERS = {}                      # rid -> {status, pct, stage, out, error, user, started, finished}
_RLOCK = threading.Lock()
_PROBE = {}
_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
MAX_CLIPS = 400
MAX_DUR = 3600.0                  # one hour: longest timeline position / export (stops a stray start=1e7 rendering for days)
SPEED_LO, SPEED_HI = 0.1, 8.0     # same range in clip_len, the render and the preview (editor.js spd())
LOOKS = {   # name -> ffmpeg filter chain (applied after colour)
    "none": "", "mono": "hue=s=0", "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "warm": "colorbalance=rs=.08:gs=.02:bs=-.08:rm=.06:bm=-.06", "cool": "colorbalance=rs=-.06:bs=.08:rm=-.04:bm=.06",
    "vivid": "eq=saturation=1.35:contrast=1.08", "fade": "eq=contrast=.85:brightness=.04:saturation=.8",
    "noir": "hue=s=0,eq=contrast=1.35:brightness=-.03", "vignette": "vignette=PI/4",
    "film": "noise=alls=8:allf=t,vignette=PI/5", "blur": "gblur=sigma=6", "sharpen": "unsharp=5:5:1.0",
}


# ── small helpers ─────────────────────────────────────────────────────────────────────────────
def _run(args, timeout=120, binary=False):
    return subprocess.run([core.FFMPEG, "-hide_banner"] + args, capture_output=True, timeout=timeout,
                          creationflags=getattr(core, "NO_WINDOW", 0), text=not binary)


def _num(v, d=0.0, lo=None, hi=None):
    try:
        x = float(v)
        if x != x:
            x = d
    except (TypeError, ValueError):
        x = d
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def _ffesc_path(p):
    """Windows path inside an ffmpeg filter argument (textfile=, fontfile=)."""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _color(c, d="black"):
    c = str(c or d).strip()
    return c if re.match(r"^(#[0-9a-fA-F]{6}|[a-z]{3,20})$", c) else d


def _font():
    for f in (os.path.join(core.STATIC, "fonts", "editor.ttf"), r"C:\Windows\Fonts\segoeuib.ttf",
              r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.isfile(f):
            return f
    return None


def probe(path):
    """{kind, dur, w, h, fps, audio} — cached per file version."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    if key in _PROBE:
        return _PROBE[key]
    kind = core.kind_of(path)
    info = {"kind": kind, "dur": None, "w": None, "h": None, "fps": None, "audio": False}
    try:
        r = _run(["-i", path], 30)
        err = r.stderr or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m and kind != "image":
            info["dur"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3)
        m = re.search(r"Stream #\S+.*?Video:.*?(\d{2,5})x(\d{2,5})", err)
        if m:
            sz = core.media_size(path) or (int(m.group(1)), int(m.group(2)))
            info["w"], info["h"] = sz
        m = re.search(r"(\d+(?:\.\d+)?) fps", err)
        if m:
            info["fps"] = float(m.group(1))
        info["audio"] = bool(re.search(r"Stream #\S+.*?Audio:", err))
    except Exception:
        pass
    _PROBE[key] = info
    return info


def _cache_name(path, *parts):
    h = hashlib.sha1(("%s|%s|%s" % (path, os.path.getmtime(path), "|".join(map(str, parts)))).encode()).hexdigest()[:20]
    return os.path.join(CACHE, h)


def strip(path, n=10, h=56):
    """Filmstrip sprite: n frames across the clip, side by side (one JPEG)."""
    n, h = int(_num(n, 10, 1, 40)), int(_num(h, 56, 24, 160))
    out = _cache_name(path, "strip", n, h) + ".jpg"
    if os.path.isfile(out):
        return out
    info = probe(path) or {}
    if info.get("kind") == "image":
        core.still(path, out, None)
        r = _run(["-y", "-v", "error", "-i", out, "-vf", "scale=-2:%d" % h, out + ".jpg"], 30)
        if os.path.isfile(out + ".jpg"):
            os.replace(out + ".jpg", out)
        return out
    dur = info.get("dur") or 1.0
    rate = max(0.01, n / max(0.1, dur))
    r = _run(["-y", "-v", "error", "-i", path, "-vf", "fps=%.5f,scale=-2:%d,tile=%dx1" % (rate, h, n),
              "-frames:v", "1", "-q:v", "5", out], 120)
    if not os.path.isfile(out):
        core.still(path, out, h * 2, at=min(0.5, dur / 2))
    return out


def wave(path, n=600):
    """Waveform peaks 0..1 (n buckets) of a clip's audio."""
    n = int(_num(n, 600, 50, 4000))
    out = _cache_name(path, "wave", n) + ".json"
    if os.path.isfile(out):
        try:
            return json.load(open(out, encoding="utf-8"))
        except Exception:
            pass
    r = _run(["-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "2000", "-f", "s16le", "-"], 120, binary=True)
    raw = r.stdout or b""
    cnt = len(raw) // 2
    peaks = []
    if cnt:
        vals = struct.unpack("<%dh" % cnt, raw[:cnt * 2])
        step = max(1, cnt // n)
        for i in range(0, cnt, step):
            seg = vals[i:i + step]
            peaks.append(round(max(abs(v) for v in seg) / 32768.0, 3) if seg else 0)
        peaks = peaks[:n]
    res = {"peaks": peaks, "dur": round(cnt / 2000.0, 3)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f)
    return res


# ── the renderer ──────────────────────────────────────────────────────────────────────────────
def _atempo(speed):
    """atempo only takes 0.5–2 per stage → chain stages."""
    s, parts = speed, []
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append("atempo=%.4f" % s)
    return ",".join(parts)


def clip_len(c):
    if c.get("type") in ("text", "image", "color"):
        return _num(c.get("dur"), 3.0, 0.1, MAX_DUR)
    return min(MAX_DUR, max(0.05, (_num(c.get("out"), 1.0) - _num(c.get("in"), 0.0)) / _num(c.get("speed"), 1.0, SPEED_LO, SPEED_HI)))


def clip_start(c):
    return _num(c.get("start"), 0, 0, MAX_DUR)


def timeline_len(project):
    return max([clip_start(c) + clip_len(c) for t in (project.get("tracks") or []) if isinstance(t, dict)
                for c in (t.get("clips") or [])[:MAX_CLIPS] if isinstance(c, dict)] + [0.0])


def build(project, resolve, out_path, rng=None, w=None, h=None, tmpdir=TMP):
    """Timeline → ffmpeg argv. resolve(src) -> absolute path or None. Returns (argv, total_seconds).
    Title text + the filter graph go into tmpdir (render() gives each export its own and deletes it)."""
    W = int(_num(w or project.get("w"), 1280, 160, 3840)) // 2 * 2
    H = int(_num(h or project.get("h"), 720, 160, 3840)) // 2 * 2
    FPS = int(_num(project.get("fps"), 30, 10, 60))
    tracks = [t for t in (project.get("tracks") or []) if isinstance(t, dict)]
    clips_all = []
    for ti, t in enumerate(tracks):
        for c in (t.get("clips") or [])[:MAX_CLIPS]:
            if isinstance(c, dict):
                clips_all.append((ti, t, c))
    T = min(MAX_DUR, max(timeline_len(project), 0.5))
    a0, a1 = 0.0, T
    if rng and len(rng) == 2:
        a0, a1 = _num(rng[0], 0, 0, T), _num(rng[1], T, 0, T)
        if a1 - a0 < 0.1:
            a0, a1 = 0.0, T
    inputs, fl, amix = [], [], []
    fl.append("color=c=%s:s=%dx%d:r=%d:d=%.3f,format=yuv420p[base]" % (_color(project.get("bg")), W, H, FPS, T))
    layer = "base"
    k = 0
    font = _font()
    # video tracks: the first video track in the list is the TOP layer → draw from the bottom up
    vtracks = [(ti, t) for ti, t in enumerate(tracks) if t.get("kind") == "video"]
    for ti, t in reversed(vtracks):
        if t.get("hidden"):
            continue
        for c in sorted((t.get("clips") or [])[:MAX_CLIPS], key=lambda x: _num(x.get("start"))):
            typ = c.get("type") or "video"
            st, ln = clip_start(c), clip_len(c)
            fi, fo = _num(c.get("fade_in"), 0, 0, ln / 2), _num(c.get("fade_out"), 0, 0, ln / 2)
            if typ == "color":
                src = "color=c=%s:s=%dx%d:r=%d:d=%.3f,format=yuva420p" % (_color(c.get("color")), W, H, FPS, ln)
                lab = "c%d" % k
                chain = [src]
            else:
                p = resolve(c.get("src"))
                if not p:
                    continue
                info = probe(p) or {}
                idx = inputs.count("-i")
                if typ == "image" or info.get("kind") == "image":
                    inputs += ["-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % (ln + 0.5), "-i", p]
                    chain = ["[%d:v]trim=duration=%.3f" % (idx, ln), "setpts=PTS-STARTPTS"]
                else:
                    a, b = _num(c.get("in"), 0, 0), _num(c.get("out"), 1)
                    b = max(b, a + 0.05)
                    inputs += ["-ss", "%.3f" % a, "-t", "%.3f" % (b - a), "-i", p]     # input seek: fast on long sources
                    sp = _num(c.get("speed"), 1, SPEED_LO, SPEED_HI)
                    chain = ["[%d:v]trim=duration=%.3f" % (idx, b - a), "setpts=(PTS-STARTPTS)/%.4f" % sp]
                    if not t.get("muted") and not c.get("muted") and info.get("audio") and _num(c.get("volume"), 1, 0, 4) > 0:
                        amix.append(_achain(idx, 0, b - a, sp, c, st, ln, k))
                chain.append("fps=%d" % FPS)
                fit = c.get("fit") or "cover"
                motion = c.get("motion") or ""
                if motion in ("zoomin", "zoomout", "panleft", "panright") and (typ == "image" or info.get("kind") == "image"):
                    nfr = max(1, int(ln * FPS))
                    z = "1+0.18*on/%d" % nfr if motion == "zoomin" else "1.18-0.18*on/%d" % nfr if motion == "zoomout" else "1.15"
                    x = "iw/2-(iw/zoom/2)" if motion.startswith("zoom") else \
                        "(iw-iw/zoom)*on/%d" % nfr if motion == "panright" else "(iw-iw/zoom)*(1-on/%d)" % nfr
                    chain.append("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (W * 2, H * 2, W * 2, H * 2))
                    chain.append("zoompan=z='%s':x='%s':y='ih/2-(ih/zoom/2)':d=1:s=%dx%d:fps=%d" % (z, x, W, H, FPS))
                elif fit == "contain":
                    chain.append("scale=%d:%d:force_original_aspect_ratio=decrease" % (W, H))
                elif fit == "stretch":
                    chain.append("scale=%d:%d" % (W, H))
                else:
                    chain.append("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (W, H, W, H))
                sc = _num(c.get("scale"), 1, 0.05, 4)
                if abs(sc - 1) > 0.001:
                    chain.append("scale=trunc(iw*%.4f/2)*2:trunc(ih*%.4f/2)*2" % (sc, sc))
                if c.get("flip"):
                    chain.append("hflip")
                rot = int(_num(c.get("rotate"), 0)) % 360
                if rot == 90:
                    chain.append("transpose=1")
                elif rot == 180:
                    chain.append("hflip,vflip")
                elif rot == 270:
                    chain.append("transpose=2")
                br, ct, sa = _num(c.get("brightness"), 0, -1, 1), _num(c.get("contrast"), 1, 0, 3), _num(c.get("saturation"), 1, 0, 3)
                if br or ct != 1 or sa != 1:
                    chain.append("eq=brightness=%.3f:contrast=%.3f:saturation=%.3f" % (br, ct, sa))
                look = LOOKS.get(str(c.get("look") or "none"), "")
                if look:
                    chain.append(look)
                chain.append("format=yuva420p")
                lab = "c%d" % k
            if fi > 0:
                chain.append("fade=t=in:st=0:d=%.3f:alpha=1" % fi)
            if fo > 0:
                chain.append("fade=t=out:st=%.3f:d=%.3f:alpha=1" % (max(0, ln - fo), fo))
            op = _num(c.get("opacity"), 1, 0, 1)
            if op < 0.999:
                chain.append("colorchannelmixer=aa=%.3f" % op)
            chain.append("setpts=PTS+%.3f/TB" % st)
            fl.append(",".join(chain) + "[%s]" % lab)
            x = "(W-w)/2+%.4f*W" % _num(c.get("x"), 0, -2, 2)
            y = "(H-h)/2+%.4f*H" % _num(c.get("y"), 0, -2, 2)
            fl.append("[%s][%s]overlay=x='%s':y='%s':eof_action=pass:enable='between(t,%.3f,%.3f)'[L%d]"
                      % (layer, lab, x, y, st, st + ln, k))
            layer = "L%d" % k
            k += 1
    # text tracks (drawn above all video)
    for ti, t in enumerate(tracks):
        if t.get("kind") != "text" or t.get("hidden") or not font:
            continue
        for c in (t.get("clips") or [])[:MAX_CLIPS]:
            txt = str(c.get("text") or "").strip()
            if not txt:
                continue
            st, ln = clip_start(c), clip_len(c)
            fi, fo = _num(c.get("fade_in"), 0.3, 0, ln / 2), _num(c.get("fade_out"), 0.3, 0, ln / 2)
            tf = os.path.join(tmpdir, "t_%s.txt" % uuid.uuid4().hex[:10])
            with open(tf, "w", encoding="utf-8") as f:
                f.write(txt[:2000])
            size = int(_num(c.get("size"), 0.07, 0.015, 0.4) * H)
            pos = c.get("pos") or "center"
            ys = {"top": "h*0.08", "center": "(h-text_h)/2", "bottom": "h*0.92-text_h", "lower": "h*0.78-text_h"}.get(pos, "(h-text_h)/2")
            xs = "(w-text_w)/2+%.4f*w" % _num(c.get("x"), 0, -1, 1)
            ys = "%s+%.4f*h" % (ys, _num(c.get("y"), 0, -1, 1))
            alpha = "if(lt(t,%.3f),0,if(lt(t,%.3f),(t-%.3f)/%.3f,if(gt(t,%.3f),(%.3f-t)/%.3f,1)))" % (
                st, st + fi, st, max(fi, 0.001), st + ln - fo, st + ln, max(fo, 0.001))
            dt = ("drawtext=fontfile='%s':textfile='%s':fontsize=%d:fontcolor=%s:x='%s':y='%s':line_spacing=%d"
                  ":alpha='%s':enable='between(t,%.3f,%.3f)'" % (_ffesc_path(font), _ffesc_path(tf), size,
                                                               _color(c.get("color"), "white"), xs, ys, int(size * .25),
                                                               alpha, st, st + ln))
            if c.get("box", True):
                dt += ":box=1:boxcolor=%s@%.2f:boxborderw=%d" % (_color(c.get("box_color"), "black"),
                                                                _num(c.get("box_alpha"), 0.45, 0, 1), int(size * .35))
            if c.get("shadow", True):
                dt += ":shadowcolor=black@0.6:shadowx=2:shadowy=2"
            fl.append("[%s]%s[X%d]" % (layer, dt, k))
            layer = "X%d" % k
            k += 1
    # audio tracks
    for ti, t in enumerate(tracks):
        if t.get("kind") != "audio" or t.get("muted"):
            continue
        for c in (t.get("clips") or [])[:MAX_CLIPS]:
            if c.get("muted"):
                continue
            p = resolve(c.get("src"))
            if not p or _num(c.get("volume"), 1, 0, 4) <= 0:
                continue
            idx = inputs.count("-i")
            a, b = _num(c.get("in"), 0, 0), _num(c.get("out"), 1)
            b = max(b, a + 0.05)
            inputs += ["-ss", "%.3f" % a, "-t", "%.3f" % (b - a), "-i", p]
            amix.append(_achain(idx, 0, b - a, _num(c.get("speed"), 1, SPEED_LO, SPEED_HI), c, clip_start(c), clip_len(c), k))
            k += 1
    fl.append("[%s]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS,format=yuv420p[vout]" % (layer, a0, a1))
    if amix:
        fl.extend(x[0] for x in amix)
        mix = "".join("[%s]" % x[1] for x in amix)
        mv = _num(project.get("master"), 1, 0, 4)
        fl.append("%samix=inputs=%d:normalize=0:dropout_transition=0,volume=%.3f,apad,atrim=start=%.3f:end=%.3f,"
                  "asetpts=PTS-STARTPTS,alimiter=limit=0.95[aout]" % (mix, len(amix), mv, a0, a1))
    else:
        fl.append("anullsrc=r=48000:cl=stereo,atrim=duration=%.3f[aout]" % (a1 - a0))
    gf = os.path.join(tmpdir, "g_%s.txt" % uuid.uuid4().hex[:10])
    with open(gf, "w", encoding="utf-8") as f:
        f.write(";\n".join(fl))
    argv = ["-y", "-v", "error", "-progress", "pipe:1", "-nostats"] + inputs + [
        "-/filter_complex", gf, "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", project.get("preset") if project.get("preset") in _PRESETS else "veryfast", "-crf", str(int(_num(project.get("crf"), 19, 12, 35))),
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", "-t", "%.3f" % (a1 - a0), out_path]
    return argv, a1 - a0


def _achain(idx, a, b, sp, c, st, ln, k):
    vol = _num(c.get("volume"), 1, 0, 4)
    fi, fo = _num(c.get("afade_in", c.get("fade_in")), 0, 0, ln / 2), _num(c.get("afade_out", c.get("fade_out")), 0, 0, ln / 2)
    ch = ["[%d:a]atrim=start=%.3f:end=%.3f" % (idx, a, b), "asetpts=PTS-STARTPTS", "aresample=48000",
          "aformat=channel_layouts=stereo"]
    if abs(sp - 1) > 0.001:
        ch.append(_atempo(sp))
    ch.append("volume=%.3f" % vol)
    if fi > 0:
        ch.append("afade=t=in:st=0:d=%.3f" % fi)
    if fo > 0:
        ch.append("afade=t=out:st=%.3f:d=%.3f" % (max(0, ln - fo), fo))
    ms = int(st * 1000)
    ch.append("adelay=%d|%d" % (ms, ms))
    return (",".join(ch) + "[a%d]" % k, "a%d" % k)


_PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow")


def _ffmpeg(argv, job, total):
    """Run one ffmpeg export, updating job pct. Returns (returncode, stderr text) — stderr fully read."""
    p = subprocess.Popen([core.FFMPEG, "-hide_banner"] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", creationflags=getattr(core, "NO_WINDOW", 0))
    job["_proc"] = p
    err = []
    reader = threading.Thread(target=lambda: err.extend(p.stderr.readlines()), daemon=True)
    reader.start()
    for ln in p.stdout:
        m = re.match(r"out_time_(?:us|ms)=(\d+)", ln.strip())
        if m and total > 0:
            job["pct"] = min(99.0, round(int(m.group(1)) / 1e6 / total * 100, 1))
        if job.get("cancel"):
            p.kill()
    p.wait()
    reader.join(10)                 # the stderr text decides the ffmpeg<7 fallback — it must be complete first
    return p.returncode, "".join(err)


def _prune_renders():
    cut = time.time() - 6 * 3600
    for k in [k for k, r in RENDERS.items() if r.get("status") != "running" and (r.get("finished") or 0) < cut]:
        RENDERS.pop(k, None)


def render(rid, project, resolve, out_path, rng, on_done):
    job = RENDERS[rid]
    tmpdir = os.path.join(TMP, rid)
    try:
        os.makedirs(tmpdir, exist_ok=True)
        argv, total = build(project, resolve, out_path, rng, tmpdir=tmpdir)
        job.update(stage="rendering", total=round(total, 2))
        rc, err = _ffmpeg(argv, job, total)
        if rc != 0 and not job.get("cancel") and "/filter_complex" in err:      # ffmpeg < 7: old script flag
            argv = [("-filter_complex_script" if x == "-/filter_complex" else x) for x in argv]
            rc, err = _ffmpeg(argv, job, total)
        if job.get("cancel"):
            raise RuntimeError("cancelled")
        if rc != 0 or not os.path.isfile(out_path):
            raise RuntimeError((err or "ffmpeg failed")[-600:])
        job.update(pct=100.0)
        on_done(job)
        job.update(status="done", stage="done", finished=time.time())
    except Exception as e:
        job.update(status="cancelled" if str(e) == "cancelled" else "error", error=str(e)[-600:], finished=time.time())
        try:
            if os.path.isfile(out_path):
                os.remove(out_path)
        except OSError:
            pass
    finally:
        job.pop("_proc", None)
        shutil.rmtree(tmpdir, ignore_errors=True)       # title text + filter graph of this export


# ── Flask wiring (both copies call register) ────────────────────────────────────────────────────
def register(app, hk):
    from flask import request, jsonify, send_file, abort

    def resolve(src):
        kind, _, name = str(src or "").partition(":")
        name = os.path.basename(name)
        if not name:
            return None
        if kind == "lib" and hk["my_file"](name):
            p = core.in_dir(core.LIB, name)
        elif kind == "ref" and hk["my_ref"](name):
            p = core.in_dir(core.REFS, name)
        else:
            return None
        return p if p and os.path.isfile(p) else None

    def pdir():
        d = os.path.join(PROJ, re.sub(r"[^A-Za-z0-9_-]", "_", str(hk["uid"]())))
        os.makedirs(d, exist_ok=True)
        return d

    def need_src():
        p = resolve(request.args.get("src") or (request.get_json(silent=True) or {}).get("src"))
        if not p:
            abort(404)
        return p

    @app.route("/editor")
    def editor_page():
        return hk["static"]("editor.html")

    @app.route("/api/editor/projects")
    def ed_projects():
        out = []
        for f in os.listdir(pdir()):
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(pdir(), f), encoding="utf-8"))
            except Exception:
                continue
            clips = sum(len(t.get("clips") or []) for t in d.get("tracks") or [])
            dur = timeline_len(d)
            out.append({"id": d.get("id"), "name": d.get("name") or "Untitled edit", "updated": d.get("updated"),
                        "clips": clips, "dur": round(dur, 2), "w": d.get("w"), "h": d.get("h"), "cover": d.get("cover")})
        out.sort(key=lambda x: -(x.get("updated") or 0))
        return jsonify({"projects": out})

    @app.route("/api/editor/project/<pid>")
    def ed_get(pid):
        if not _ID_RE.match(pid):
            abort(404)
        p = os.path.join(pdir(), pid + ".json")
        if not os.path.isfile(p):
            return jsonify({"error": "no such project"}), 404
        return jsonify(json.load(open(p, encoding="utf-8")))

    @app.route("/api/editor/project", methods=["POST"])
    def ed_save():
        d = request.get_json(silent=True) or {}
        pid = str(d.get("id") or "")
        if not _ID_RE.match(pid):
            pid = uuid.uuid4().hex[:12]
        d["id"] = pid
        d["name"] = str(d.get("name") or "Untitled edit")[:120]
        d["updated"] = time.time()
        d.setdefault("created", time.time())
        if not isinstance(d.get("tracks"), list) or len(d["tracks"]) > 24:
            return jsonify({"error": "bad tracks"}), 400
        raw = json.dumps(d)
        if len(raw) > 4 * 1024 * 1024:
            return jsonify({"error": "project too large"}), 400
        tmp = os.path.join(pdir(), pid + ".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, os.path.join(pdir(), pid + ".json"))
        return jsonify({"id": pid, "updated": d["updated"]})

    @app.route("/api/editor/project/<pid>/delete", methods=["POST"])
    def ed_delete(pid):
        if not _ID_RE.match(pid):
            abort(404)
        p = os.path.join(pdir(), pid + ".json")
        if os.path.isfile(p):
            tr = os.path.join(core.TRASH, "edit_%s_%d.json" % (pid, int(time.time())))
            shutil.move(p, tr)          # recoverable, like the library
        return jsonify({"ok": True})

    @app.route("/api/editor/probe")
    def ed_probe():
        p = need_src()
        return jsonify(probe(p) or {})

    @app.route("/api/editor/strip")
    def ed_strip():
        p = need_src()
        try:
            return send_file(strip(p, request.args.get("n", 10), request.args.get("h", 56)), max_age=86400)
        except Exception:
            abort(404)

    @app.route("/api/editor/wave")
    def ed_wave():
        p = need_src()
        try:
            return jsonify(wave(p, request.args.get("n", 600)))
        except Exception as e:
            return jsonify({"peaks": [], "error": str(e)[:200]})

    @app.route("/api/editor/frame", methods=["POST"])
    def ed_frame():
        """A frame of a clip → lab attachment (the AI tools animate / extend / edit from it)."""
        err = hk["can_attach"]()
        if err:
            return jsonify({"error": err}), 403
        b = request.get_json(silent=True) or {}
        p = resolve(b.get("src"))
        if not p:
            return jsonify({"error": "clip source not found"}), 404
        name = hk["store_ref"](os.path.splitext(os.path.basename(p))[0][:24] + "_frame", ".png")
        out = core.safe_path(os.path.join(core.REFS, name))
        at = _num(b.get("t"), 0, 0)
        try:
            if core.kind_of(p) == "image":
                core.still(p, out)
            else:
                dur = (probe(p) or {}).get("dur") or 0
                core.still(p, out, at=min(at, max(0, dur - 0.06)) if dur else at)
        except Exception as e:
            return jsonify({"error": "couldn't grab that frame: %s" % str(e)[-160:]}), 400
        return jsonify(hk["ref_info"](name))

    @app.route("/api/editor/cut", methods=["POST"])
    def ed_cut():
        """A trimmed segment of one clip (or the rendered timeline range) → lab attachment."""
        err = hk["can_attach"]()
        if err:
            return jsonify({"error": err}), 403
        b = request.get_json(silent=True) or {}
        p = resolve(b.get("src"))
        if not p:
            return jsonify({"error": "clip source not found"}), 404
        a, z = _num(b.get("in"), 0, 0), _num(b.get("out"), 0, 0)
        kind = core.kind_of(p)
        ext = ".mp3" if kind == "audio" or b.get("audio_only") else ".mp4"
        name = hk["store_ref"](os.path.splitext(os.path.basename(p))[0][:24] + "_cut", ext)
        out = core.safe_path(os.path.join(core.REFS, name))
        args = ["-y", "-v", "error", "-i", p, "-ss", "%.3f" % a] + (["-t", "%.3f" % (z - a)] if z > a else [])   # frame-accurate
        if ext == ".mp3":
            args += ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]
        else:
            args += ["-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                     "-c:a", "aac", "-movflags", "+faststart"]
        r = _run(args + [out], 600)
        if r.returncode != 0 or not os.path.isfile(out):
            return jsonify({"error": "cut failed: %s" % (r.stderr or "")[-200:]}), 400
        return jsonify(hk["ref_info"](name))

    @app.route("/api/editor/render", methods=["POST"])
    def ed_render():
        b = request.get_json(silent=True) or {}
        proj = b.get("project") or {}
        if not isinstance(proj, dict) or not isinstance(proj.get("tracks"), list):
            return jsonify({"error": "nothing to render"}), 400
        me = hk["uid"]()
        target = "ref" if b.get("target") == "ref" else "library"
        # same gates as the rest of the lab: an export counts as a job (daily limit); an attachment needs the attach right
        err = (hk.get("can_render") or (lambda: None))() or (hk["can_attach"]() if target == "ref" else None)
        if err:
            return jsonify({"error": err}), 403
        if max([_num(c.get("start")) + clip_len(c) for t in proj["tracks"] if isinstance(t, dict)
                for c in (t.get("clips") or []) if isinstance(c, dict)] + [0]) > MAX_DUR:
            return jsonify({"error": "the timeline is longer than %d minutes — trim it before exporting" % (MAX_DUR // 60)}), 400
        rid = "r" + uuid.uuid4().hex[:10]
        with _RLOCK:                # check + claim the slot together, so a double-click can't start two exports
            _prune_renders()
            if any(r.get("user") == me and r.get("status") == "running" for r in RENDERS.values()):
                return jsonify({"error": "an export is already running — wait for it or cancel it"}), 409
            RENDERS[rid] = {"id": rid, "status": "running", "stage": "preparing", "pct": 0.0, "user": me, "started": time.time(),
                            "target": target, "project": proj.get("id")}
        try:
            if target == "ref":
                name = hk["store_ref"](re.sub(r"[^A-Za-z0-9_-]+", "_", str(proj.get("name") or "edit"))[:24] + "_edit", ".mp4")
                out = core.safe_path(os.path.join(core.REFS, name))
            else:
                name = core.new_name("edit", ".mp4")
                out = os.path.join(core.LIB, name)
        except Exception:
            RENDERS.pop(rid, None)
            raise
        RENDERS[rid]["name"] = name
        (hk.get("count_render") or (lambda: None))()

        def done(job):
            if target == "library":
                clips = sum(len(t.get("clips") or []) for t in proj.get("tracks") or [])
                core.index_add(name, {"model": "editor", "prompt": str(proj.get("name") or "Edit")[:2000], "job": rid,
                                      "created": time.time(), "user": me, "mode": "edit", "clips": clips,
                                      "size": "%sx%s" % (proj.get("w"), proj.get("h")), "project": proj.get("id")})
                job["url"] = "media/" + name
            else:
                job["ref"] = hk["ref_info"](name)
        rng = b.get("range") if isinstance(b.get("range"), list) else None
        # resolve every source NOW — ownership checks need this request; the render thread has none
        paths = {}
        for t in proj.get("tracks") or []:
            for c in (t.get("clips") or []) if isinstance(t, dict) else []:
                if isinstance(c, dict) and c.get("src") and c["src"] not in paths:
                    paths[c["src"]] = resolve(c["src"])
        threading.Thread(target=render, args=(rid, proj, paths.get, out, rng, done), daemon=True).start()
        return jsonify({k: v for k, v in RENDERS[rid].items() if not k.startswith("_")})

    @app.route("/api/editor/render/<rid>")
    def ed_render_status(rid):
        r = RENDERS.get(rid)
        if not r or r.get("user") != hk["uid"]():
            return jsonify({"error": "no such export"}), 404
        return jsonify({k: v for k, v in r.items() if not k.startswith("_")})

    @app.route("/api/editor/render/<rid>/cancel", methods=["POST"])
    def ed_render_cancel(rid):
        r = RENDERS.get(rid)
        if not r or r.get("user") != hk["uid"]():
            return jsonify({"error": "no such export"}), 404
        r["cancel"] = True
        pr = r.get("_proc")
        if pr is not None:
            try:
                pr.kill()
            except Exception:
                pass
        return jsonify({"ok": True})

    @app.route("/api/editor/looks")
    def ed_looks():
        return jsonify({"looks": list(LOOKS.keys()), "font": bool(_font())})
