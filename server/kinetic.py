r"""MIR KINETIC — the Motion editor's engine: kinetic type on a beat grid + the OpenKatana effect packs (/motion/editor).
Remotion (remotion.py) still serves Motion Studio, EXPLAINED, RANK REEL and Series.

Engine: <install>/kinetic (engines.kinetic(); engine/ = film.html + core/blocks/compositor + fx/ OpenKatana packs, Apache-2.0;
render/worker.mjs = a headless Chrome driven over CDP with Node's own WebSocket — no npm packages, no daemon).
Everything runs on this PC: Chrome renders the frames, cv2 averages the sub-frames into motion blur and adds bloom + grain,
ffmpeg encodes, numpy synthesises the sound kit and mixes the music from the library. Nothing calls out.

A kinetic PROJECT: {id, name, w, h, fps, bpm, beats, palette{bg,paper,accent,hot,ink}, font, hud, hudOut, logo, music{src,
offset,stopBeat,gain}, sounds{name:dB}, kit{name:"lib:file"}, cues[[beat,name,gain]], scenes[{id,block,k0,k1,opts}],
captions[[k0,k1,[[word,beat]...]]], fx[{id,type,k0,k1,params}], session}. Media is "lib:<file>" (ownership-checked here).
"""
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import threading
import time
import uuid
import wave

try:
    import numpy as np
except ImportError:              # a build without numpy: the pixel passes report it instead of the module failing
    np = None

import core

import engines

ENGINE = engines.kinetic()
WEB = os.path.join(ENGINE, "engine")
WORKER = os.path.join(ENGINE, "render", "worker.mjs")
MIRFONTS = engines.static_dir(os.path.join("fonts", "mir"))          # the MIR typefaces (woff2 + fonts.json)
NODE = engines.node()
FFMPEG = core.FFMPEG
FFPROBE = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe" if os.name == "nt" else "ffprobe")
if not os.path.isfile(FFPROBE):
    FFPROBE = shutil.which("ffprobe") or FFPROBE
MD = os.path.join(core.DATA, "kinetic")
PROJ = os.path.join(MD, "projects")
CACHE = os.path.join(MD, "cache")
KIT = os.path.join(MD, "kit")
JOBDIR = os.path.join(MD, "jobs")
for _d in (PROJ, CACHE, KIT, JOBDIR):
    os.makedirs(_d, exist_ok=True)
_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
JOBS = {}
_JLOCK = threading.Lock()

BLOCKS = ["Words", "Strike", "Graph", "Hero", "Prompt", "Stretch", "Fly", "Notes", "Counters", "Progress", "Chain", "Rewind", "Picture", "Logo"]
# OpenKatana effects the post stage runs (time effects need the shot re-rendered at other frames; motion blur covers that)
FX_TYPES = {"local_whip", "local_zoom_blur", "local_halftone", "local_speed_lines", "local_frame_slices", "local_selective_color", "local_posterize",
            "local_paper_frame", "local_curve", "local_turbulent_displace", "local_wave_warp", "local_ripple", "local_shockwave", "local_twirl",
            "local_bulge", "local_polar", "local_kaleidoscope", "local_mirror", "local_gaussian_blur", "local_directional_blur", "local_radial_blur",
            "local_camera_lens_blur", "local_unsharp_mask", "local_channel_blur", "local_tilt_shift", "local_rgb_split", "local_motion_tile",
            "local_find_edges", "local_emboss", "local_mosaic", "local_scatter", "local_fractal_noise", "local_cell_pattern", "local_gradient_ramp",
            "local_four_color_gradient", "local_grid", "local_radio_waves", "local_lightning", "local_deep_glow", "local_lens_flare",
            "local_light_rays", "local_light_sweep"}
# the Signature palette in the kinetic engine's five roles (bg / paper / accent / hot / ink)
PALETTE = {"bg": "#08080A", "paper": "#F2F6FA", "accent": "#FFB547", "hot": "#FF8A1F", "ink": "#0B0B0D"}
PAL_NAMES = ("bg", "paper", "accent", "hot", "ink")
MAX_BEATS = 4000
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# ── environment ───────────────────────────────────────────────────────────────────────────────────────────────
def chrome():
    for p in (os.environ.get("MIR_CHROME"), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("microsoft-edge")):
        if p and os.path.isfile(p):
            return p
    return ""


def _cv2():
    try:
        import cv2
        return cv2
    except Exception:
        return None


def health():
    return {"ok": bool(os.path.isfile(WORKER) and os.path.isfile(NODE) and chrome() and os.path.isfile(FFMPEG)), "engine": os.path.isfile(WORKER),
            "node": os.path.isfile(NODE), "chrome": os.path.basename(chrome()) or None, "ffmpeg": os.path.isfile(FFMPEG), "cv2": bool(_cv2()),
            "blocks": BLOCKS, "fx": sorted(FX_TYPES), "ram_gb": round(_ram_gb(), 1), "cpus": os.cpu_count() or 4}


def _ram_gb():
    try:
        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in
                        ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
        m = M(); m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys / 2 ** 30
    except Exception:
        return 16.0


def fonts():
    """The MIR typefaces the editor offers beside Archivo (woff2 in MirFonts/out)."""
    try:
        with open(os.path.join(MIRFONTS, "fonts.json"), encoding="utf-8") as f:
            fl = json.load(f)
        return [x for x in fl if isinstance(x, dict) and re.match(r"^[a-z0-9]{2,24}$", str(x.get("id") or "")) and os.path.isfile(os.path.join(MIRFONTS, x["id"] + ".woff2"))]
    except Exception:
        return []


# ── project validation ─────────────────────────────────────────────────────────────────────────────────────────
def _num(v, d=0.0, lo=None, hi=None):
    try:
        v = float(v)
        if not math.isfinite(v):
            return d
    except Exception:
        return d
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _beat(v, beats, d=0.0):
    return round(_num(v, d, 0, beats), 3)


def _plain(v, depth=0):
    """JSON-plain copy of block options (numbers, strings ≤ 2000 chars, bools, lists, dicts), depth-limited."""
    if depth > 8:
        return None
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v if math.isfinite(v) else 0
    if isinstance(v, str):
        return v[:2000]
    if isinstance(v, list):
        return [_plain(x, depth + 1) for x in v[:400]]
    if isinstance(v, dict):
        return {str(k)[:64]: _plain(x, depth + 1) for k, x in list(v.items())[:120]}
    return None


def _lib(v):
    """'lib:<file>' → normalised, or '' when it is not a library reference."""
    if isinstance(v, str) and v.startswith("lib:"):
        n = os.path.basename(v[4:].strip())
        return "lib:" + n if n and not n.startswith(".") else ""
    return ""


def _cid(v):
    v = str(v or "")
    return v if re.match(r"^[a-z0-9]{1,16}$", v) else uuid.uuid4().hex[:8]


def clean(p):
    p = p if isinstance(p, dict) else {}
    beats = int(_num(p.get("beats"), 42, 1, MAX_BEATS))
    pal = dict(PALETTE)
    for k in PAL_NAMES:
        v = str((p.get("palette") or {}).get(k) or "")
        if _HEX.match(v):
            pal[k] = v.upper()
    out = {"id": str(p.get("id") or "")[:32], "name": str(p.get("name") or "Untitled film")[:120],
           "w": int(_num(p.get("w"), 1920, 320, 4096)), "h": int(_num(p.get("h"), 1080, 320, 4096)),
           "fps": int(_num(p.get("fps"), 60, 24, 60)), "bpm": round(_num(p.get("bpm"), 120, 40, 300), 2), "beats": beats, "palette": pal,
           "font": str(p.get("font") or "")[:24] if re.match(r"^[a-z0-9]{0,24}$", str(p.get("font") or "")) else "",
           "hud": False if p.get("hud") in (False, None, "") else str(p.get("hud"))[:80],
           "hudOut": [_beat(p["hudOut"][0], beats), _beat(p["hudOut"][1], beats)] if isinstance(p.get("hudOut"), list) and len(p["hudOut"]) == 2 else None,
           "logo": _lib(p.get("logo")), "music": None, "sounds": {}, "kit": {}, "cues": [], "scenes": [], "captions": [], "fx": [],
           "session": str(p.get("session") or "")[:64]}
    m = p.get("music")
    if isinstance(m, dict) and _lib(m.get("src")):
        out["music"] = {"src": _lib(m["src"]), "offset": _num(m.get("offset"), 0, 0, 36000), "gain": _num(m.get("gain"), -3.5, -40, 12),
                        "stopBeat": _beat(m["stopBeat"], beats) if m.get("stopBeat") not in (None, "", False) else None}
    for k, v in (p.get("sounds") or {}).items() if isinstance(p.get("sounds"), dict) else []:
        if re.match(r"^[a-z0-9_]{1,24}$", str(k)):
            out["sounds"][k] = round(_num(v, 0, -40, 12), 1)
    for k, v in (p.get("kit") or {}).items() if isinstance(p.get("kit"), dict) else []:
        if re.match(r"^[a-z0-9_]{1,24}$", str(k)) and _lib(v):
            out["kit"][k] = _lib(v)
    for c in (p.get("cues") or [])[:400]:
        if isinstance(c, list) and len(c) >= 2 and re.match(r"^[a-z0-9_]{1,24}$", str(c[1])):
            out["cues"].append([_beat(c[0], beats), str(c[1]), _num(c[2] if len(c) > 2 else 1, 1, 0, 4)])
    last = 0.0
    for s in sorted([s for s in (p.get("scenes") or []) if isinstance(s, dict) and s.get("block") in BLOCKS][:200], key=lambda s: _num(s.get("k0"), 0)):
        k0, k1 = _beat(s.get("k0"), beats), _beat(s.get("k1"), beats)
        k0 = max(k0, last)                                    # blocks are sequential: no overlaps
        if k1 - k0 < .5:
            continue
        out["scenes"].append({"id": _cid(s.get("id")), "block": s["block"], "k0": k0, "k1": k1, "opts": _plain(s.get("opts") or {}) or {}})
        last = k1
    for c in (p.get("captions") or [])[:200]:
        if isinstance(c, list) and len(c) == 3 and isinstance(c[2], list):
            words = [[str(w[0])[:40], _beat(w[1], beats)] for w in c[2][:60] if isinstance(w, list) and len(w) == 2]
            if words:
                out["captions"].append([_beat(c[0], beats), _beat(c[1], beats), words])
    for f in (p.get("fx") or [])[:60]:
        if isinstance(f, dict) and f.get("type") in FX_TYPES:
            k0, k1 = _beat(f.get("k0"), beats), _beat(f.get("k1"), beats)
            if k1 > k0:
                out["fx"].append({"id": _cid(f.get("id")), "type": f["type"], "k0": k0, "k1": k1, "params": _plain(f.get("params") or {}) or {}})
    return out


def duration(p):
    return p["beats"] * 60.0 / p["bpm"]


def media_refs(p):
    refs = set()

    def walk(v):
        if isinstance(v, str):
            if v.startswith("lib:"):
                refs.add(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk([p.get("logo"), (p.get("music") or {}).get("src"), p.get("kit"), [s.get("opts") for s in p.get("scenes", [])]])
    return sorted(r for r in refs if r)


# ── the worker (Chrome over CDP) ──────────────────────────────────────────────────────────────────────────────
def _jobfile(p, jobdir, blur=True, quality=95, samples=12):
    media = {}
    for r in media_refs(p):
        name = r[4:]
        path = core.in_dir(core.LIB, name)
        if path and os.path.isfile(path):
            media[name] = path
    # gpu True: GPU Chromes scale across workers (software raster is CPU-bound); a GPU crash relaunches that worker in software
    job = {"engine": WEB, "spec": p, "media": media, "mirfonts": MIRFONTS, "chrome": chrome(), "blur": bool(blur), "quality": int(quality),
           "maxSamples": int(samples), "gpu": True}
    jf = os.path.join(jobdir, "job.json")
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(job, f)
    return jf


def _node(args, timeout=240):
    return subprocess.run([NODE, WORKER] + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def info(p, jobdir=None):
    """Film facts from the engine itself: duration, cues the blocks registered, hard cuts."""
    own = jobdir is None
    jobdir = jobdir or os.path.join(JOBDIR, "info_" + uuid.uuid4().hex[:8])
    os.makedirs(jobdir, exist_ok=True)
    try:
        r = _node(["--job", _jobfile(p, jobdir), "--info"])
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError((r.stderr or "the engine gave no film info").strip()[-600:])
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        if own:
            shutil.rmtree(jobdir, ignore_errors=True)


def still(p, frame, scale=0.5):
    """One frame as JPEG (thumbnails, the editor's effect preview, AI critique) → path in CACHE."""
    key = hashlib.sha1(json.dumps([p, int(frame), round(scale, 2)], sort_keys=True).encode()).hexdigest()[:20]
    out = os.path.join(CACHE, "still_%s.jpg" % key)
    if os.path.isfile(out):
        return out
    jobdir = os.path.join(JOBDIR, "still_" + key[:10])
    os.makedirs(jobdir, exist_ok=True)
    try:
        raw = os.path.join(jobdir, "frame.jpg")
        r = _node(["--job", _jobfile(p, jobdir, blur=False, quality=92), "--still", raw, "--frame", str(int(frame))], timeout=180)
        if r.returncode != 0 or not os.path.isfile(raw):
            raise RuntimeError((r.stderr or "still failed").strip()[-500:])
        cv2 = _cv2()
        if scale < .99 and cv2:
            im = cv2.imread(raw)
            cv2.imwrite(out, cv2.resize(im, (int(1920 * scale), int(1080 * scale)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 88])
        else:
            shutil.copyfile(raw, out)
        return out
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)


def _render_part(job, jf, dsf, f0, f1, part, fps, bloom, grain, crf, preset):
    """One worker: node streams JPEG sub-frames, cv2 averages them (motion blur) and adds bloom + grain, ffmpeg encodes."""
    cv2 = _cv2()
    W, H = int(round(1920 * dsf)), int(round(1080 * dsf))
    level = "5.2" if H > 1440 else "4.2"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    enc = ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-level", level, "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    node = subprocess.Popen([NODE, WORKER, "--job", jf, "--dsf", str(dsf), "--from", str(f0), "--to", str(f1)] + ([] if cv2 else ["--noblur"]),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1 << 24, creationflags=flags)
    job.setdefault("_procs", []).append(node)
    if cv2:
        ff = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-"] + enc + [part],
                              stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
    else:   # no cv2: the JPEGs go straight to the encoder (no motion blur, bloom or grain)
        ff = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "image2pipe", "-c:v", "mjpeg", "-r", str(fps), "-i", "-"] + enc + [part],
                              stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)

    def rd(n):
        b = node.stdout.read(n)
        return b if b is not None and len(b) == n else None
    gr = [np.random.default_rng(i).normal(0, 1, (H // 2, W // 2)).astype(np.float32) for i in range(8)] if cv2 and grain else None
    s = dsf / 2
    done = 0
    try:
        while True:
            if job.get("status") == "cancelled":
                break
            h = rd(8)
            if h is None:
                break
            k, n = struct.unpack("<II", h)
            if cv2:
                acc = None
                for _ in range(n):
                    L = struct.unpack("<I", rd(4))[0]
                    img = cv2.imdecode(np.frombuffer(rd(L), np.uint8), cv2.IMREAD_COLOR).astype(np.float32)
                    acc = img if acc is None else acc + img
                img = acc / n
                if bloom:   # bright pass at quarter resolution, two radii
                    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
                    br = np.clip(small - 175, 0, None)
                    bl = .6 * cv2.GaussianBlur(br, (0, 0), 5 * s) + .4 * cv2.GaussianBlur(br, (0, 0), 20 * s)
                    img += cv2.resize(bl, (W, H), interpolation=cv2.INTER_LINEAR) * .75
                if gr is not None:
                    img += cv2.resize(gr[k % 8], (W, H), interpolation=cv2.INTER_LINEAR)[..., None] * grain
                ff.stdin.write(np.clip(img + .5, 0, 255).astype(np.uint8).tobytes())
            else:
                for _ in range(n):
                    L = struct.unpack("<I", rd(4))[0]
                    b = rd(L)
                ff.stdin.write(b)
            done += 1
            job["_frames"][part] = done
    finally:
        try:
            ff.stdin.close()
        except Exception:
            pass
        if job.get("status") == "cancelled":
            node.kill()
        ff.wait(); node.wait()
    err = (node.stderr.read() or b"").decode("utf-8", "replace")
    return done, err[-800:]


def _workers(dsf, frames):
    ram, cpus = _ram_gb(), os.cpu_count() or 4
    per = 10 if dsf >= 2 else 3.5 if dsf >= 1 else 2.5
    return max(1, min(3 if dsf >= 2 else 6, int(ram // per), max(1, cpus // 3), max(1, frames // 90)))


def render(jid, p, out, opts, on_done):
    """The whole pipeline for a cleaned, ownership-checked project → out (mp4). Updates JOBS[jid] along the way."""
    job = JOBS[jid]
    jobdir = os.path.join(JOBDIR, jid)
    os.makedirs(jobdir, exist_ok=True)
    try:
        fps, dur = p["fps"], duration(p)
        total = int(round(dur * fps))
        w, h = p["w"], p["h"]
        dsf = 2.0 if max(w, h) >= 3000 else 2 / 3 if w == 1280 and h == 720 else 1.0
        job.update(stage="building the film", pct=.02)
        fi = info(p, jobdir)
        job["cues"] = len(fi.get("cues") or [])
        jf = _jobfile(p, jobdir, blur=opts.get("blur", True), quality=95, samples=opts.get("samples", 12))
        n = _workers(dsf, total)
        step = -(-total // n)
        parts, threads, errs = [], [], {}
        job["_frames"] = {}
        job.update(stage="rendering frames (%d worker%s)" % (n, "s" if n > 1 else ""), pct=.05, workers=n, frames=total)
        for i in range(n):
            f0, f1 = i * step, min(total, (i + 1) * step)
            if f0 >= f1:
                continue
            part = os.path.join(jobdir, "part%d.mp4" % i)
            parts.append((part, f0, f1))

            def run(part=part, f0=f0, f1=f1):
                try:
                    done, err = _render_part(job, jf, dsf, f0, f1, part, fps, opts.get("bloom", True), opts.get("grain", 2.2), opts.get("crf", 16), opts.get("preset", "medium"))
                    if done != f1 - f0 and job.get("status") != "cancelled":
                        errs[part] = "%d of %d frames: %s" % (done, f1 - f0, err)
                except Exception as e:
                    errs[part] = str(e)[:400]
            t = threading.Thread(target=run, daemon=True)
            threads.append(t); t.start()
        last, since = -1, time.time()
        while any(t.is_alive() for t in threads):
            time.sleep(.5)
            done = sum(job["_frames"].values())
            job["pct"] = .05 + .75 * done / max(1, total)
            job["stage"] = "rendering frames %d / %d" % (done, total)
            if done != last:
                last, since = done, time.time()
            elif time.time() - since > 300 or job.get("status") == "cancelled":   # a stalled or cancelled job frees its workers
                for pr in job.get("_procs", []):
                    try:
                        pr.kill()
                    except Exception:
                        pass
                if job.get("status") != "cancelled":
                    raise RuntimeError("render stalled at frame %d of %d (no progress for 5 min)" % (done, total))
                break
        if job.get("status") == "cancelled":
            return
        if errs:
            raise RuntimeError("; ".join(list(errs.values())[:2]))
        job.update(stage="joining", pct=.82)
        lst = os.path.join(jobdir, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write("".join("file '%s'\n" % os.path.basename(pt).replace("'", "'\\''") for pt, _, _ in parts))
        video = os.path.join(jobdir, "video.mp4")
        _ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
        job.update(stage="mixing the soundtrack", pct=.86)
        mixed = mix(p, fi, os.path.join(jobdir, "mix.wav"), lufs=opts.get("lufs", -14))
        job.update(stage="encoding", pct=.9)
        vf = []
        if (w, h) != (int(round(1920 * dsf)), int(round(1080 * dsf))):     # 9:16, 1:1, 4:5: the film centred on black
            vf = ["-vf", "scale=%d:-2:flags=lanczos,pad=%d:%d:0:(%d-ih)/2:black" % (w, w, h, h)]
        args = ["-i", video] + (["-i", mixed, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k"] if mixed else []) + vf
        args += (["-c:v", "copy"] if not vf else ["-c:v", "libx264", "-crf", str(opts.get("crf", 16)), "-preset", "medium", "-pix_fmt", "yuv420p"])
        _ff(args + ["-movflags", "+faststart", "-metadata", "title=%s" % p["name"].replace('"', ""), out])
        job.update(stage="checking", pct=.96)
        try:
            job["check"] = dynamism(out, dur, p["bpm"])
        except Exception as e:
            job["check"] = {"error": str(e)[:200]}
        job.update(status="done", stage="done", pct=1.0, finished=time.time(), size=os.path.getsize(out))
        on_done(job)
        shutil.rmtree(jobdir, ignore_errors=True)
    except Exception as e:
        job.update(status="error", stage="failed", error=str(e)[:900], finished=time.time())
    finally:
        job.pop("_frames", None)
        job.pop("_procs", None)


def _ff(args, timeout=3600):
    r = subprocess.run([FFMPEG, "-v", "error", "-y"] + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + (r.stderr or "").strip()[-400:])


# ── the sound kit (synthesised once, locally) ─────────────────────────────────────────────────────────────────
SR = 48000
KIT_NAMES = ["whoosh", "whoosh_2", "whoosh_big", "impact", "impact_big", "hit", "slash", "key", "key_2", "pop", "tick", "riser", "glitch", "logo_hit"]


def _lp_sweep(x, f0, f1, curve=1.0):
    """One-pole low-pass whose cutoff sweeps f0 → f1 (Hz) over the signal (sample loop; the kit is cached, so once)."""
    n = len(x)
    u = (np.arange(n) / max(1, n - 1)) ** curve
    fc = np.exp(np.log(f0) + (np.log(f1) - np.log(f0)) * u)
    a = np.exp(-2 * np.pi * fc / SR).astype(np.float64)
    y = np.empty(n); z = 0.0
    for i in range(n):
        z = a[i] * z + (1 - a[i]) * x[i]
        y[i] = z
    return y


def _synth(name):
    rng = np.random.default_rng(abs(hash(name)) % 65536 + 7)
    T = lambda d: np.arange(int(d * SR)) / SR
    noise = lambda d: rng.normal(0, 1, int(d * SR))
    dec = lambda t, k: np.exp(-k * t)
    sweep = lambda f0, f1, t, k=3.0: np.sin(2 * np.pi * np.cumsum(f1 + (f0 - f1) * np.exp(-k * t)) / SR)
    base = name.split("_")[0] if name[-2:] in ("_2",) else name
    if base == "whoosh":
        t = T(.7); e = np.sin(np.pi * np.clip(t / .7, 0, 1)) ** 2
        x = _lp_sweep(noise(.7), 300, 5000) * e
        x[len(x) // 2:] = _lp_sweep(x[len(x) // 2:], 5000, 500)
    elif base == "whoosh_big":
        t = T(1.3); e = np.sin(np.pi * np.clip(t / 1.3, 0, 1)) ** 1.5
        x = _lp_sweep(noise(1.3), 150, 2600) * e + .5 * np.sin(2 * np.pi * 45 * t) * e ** 2
    elif base == "impact":
        t = T(1.2); x = sweep(150, 42, t, 9) * dec(t, 5) + .6 * _lp_sweep(noise(1.2), 4000, 300) * dec(t, 28) + .3 * noise(1.2) * dec(t, 220)
    elif base == "impact_big":
        t = T(2.2); x = sweep(95, 32, t, 6) * dec(t, 2.2) + .5 * _lp_sweep(noise(2.2), 1800, 120) * dec(t, 7)
        x += .12 * sum(np.sin(2 * np.pi * f * t) * dec(t, 3.5) for f in (740, 1180, 1990))
    elif base == "hit":
        t = T(.5); x = noise(.5) * dec(t, 40) + .8 * sweep(180, 60, t, 20) * dec(t, 18)
    elif base == "slash":
        t = T(.6); n_ = noise(.6); x = (n_ - _lp_sweep(n_, 1500, 1500)) * dec(t, 9) * np.clip(t / .03, 0, 1)
        x = _lp_sweep(x, 9000, 1500)
    elif base == "key":
        t = T(.3); f = 1800 if name == "key" else 2300; x = noise(.3) * dec(t, 400) + .5 * np.sin(2 * np.pi * f * t) * dec(t, 70)
    elif base == "pop":
        t = T(.3); x = sweep(900, 240, t, 30) * dec(t, 14)
    elif base == "tick":
        t = T(.25); x = noise(.25) * dec(t, 900) + .4 * np.sin(2 * np.pi * 4200 * t) * dec(t, 120)
    elif base == "riser":
        t = T(2.2); u = np.clip(t / 2.2, 0, 1); x = _lp_sweep(noise(2.2), 200, 9000) * u ** 2 + .35 * sweep(1400, 160, 2.2 - t, 1.5) * u ** 1.5
    elif base == "glitch":
        t = T(.6); x = np.zeros_like(t); i = 0
        while i < len(t):
            L = int(rng.uniform(.015, .06) * SR); f = rng.uniform(200, 3000)
            seg = np.sign(np.sin(2 * np.pi * f * np.arange(L) / SR)) * rng.uniform(.3, 1)
            x[i:i + L] = seg[:len(x) - i]; i += L + int(rng.uniform(0, .04) * SR)
        x *= dec(t, 2)
    elif base == "logo_hit":
        t = T(3.0); x = sweep(90, 30, t, 5) * dec(t, 1.6) + .45 * _lp_sweep(noise(3.0), 1600, 100) * dec(t, 6) + .5 * np.sin(2 * np.pi * 50 * t) * dec(t, 1.3)
        x += .08 * sum(np.sin(2 * np.pi * f * t + .3 * np.sin(2 * np.pi * 5.5 * t)) * dec(t, 1.2) for f in (1046, 1318, 1568))
    else:
        return None
    x = x / (np.abs(x).max() or 1) * 10 ** (-1 / 20)
    fo = min(len(x), int(.01 * SR)); x[-fo:] *= np.linspace(1, 0, fo)
    return x.astype(np.float32)


def kit_path(name):
    """A synthesised kit sound (name or name_2 variant) → wav path; made on first use."""
    if name not in KIT_NAMES:
        return None
    p = os.path.join(KIT, name + ".wav")
    if not os.path.isfile(p):
        x = _synth(name)
        if x is None:
            return None
        with wave.open(p, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.stack([x, x], 1) * 32767).astype("<i2").tobytes())
    return p


# ── the mix: music bed from the library + a sound on every cue the blocks registered ─────────────────────────
# cue name: (kit names, first that exists | align: onset, peak, end or loop | offset s | level dB)
MIX_MAP = {
    'key': [('key', 'onset', 0, -19)], 'tick': [('tick', 'onset', 0, -15)], 'pop': [('pop', 'onset', 0, -15)],
    'thock': [('thock|pop', 'onset', 0, -9)], 'whoosh': [('whoosh', 'peak', .12, -12)], 'whoosh_big': [('whoosh_big|whoosh', 'peak', .14, -5)],
    'impact': [('impact', 'onset', 0, -2)], 'impact_big': [('impact_big|impact', 'onset', 0, -3)], 'hit': [('hit|impact', 'onset', 0, -2)],
    'slash': [('slash|whoosh', 'peak', .05, -3.5)], 'sparkle': [('sparkle|tick', 'onset', 0, -19)], 'glitch': [('glitch', 'onset', 0, -13)],
    'power_down': [('power_down|glitch', 'onset', 0, -12)], 'draw': [('draw|whoosh', 'onset', 0, -14)], 'riser': [('riser', 'end', 0, -9)],
    'drop': [('drop|impact_big|impact', 'onset', 0, -4)], 'stretch': [('stretch|whoosh', 'onset', 0, -12)], 'squeeze': [('stretch|whoosh', 'onset', 0, -15)],
    'send': [('send|key', 'onset', 0, -3), ('whoosh', 'peak', .1, -14)], 'click': [('click|key', 'onset', 0, -1.5), ('impact', 'onset', 0, -10)],
    'scroll': [('scroll', 'onset', 0, -17)], 'tick_run': [('tick_run|tick', 'loop', 0, -21)], 'ding': [('ding|tick', 'onset', 0, -15)],
    'rewind': [('rewind|whoosh_big|whoosh', 'onset', 0, -11)], 'suck': [('suck|riser', 'end', 0, -9)],
    'logo_hit': [('logo_hit|impact_big|impact', 'onset', 0, -3)],
}
BIG = ('impact_big', 'drop', 'hit', 'impact', 'slash', 'click', 'logo_hit')


def _decode(path, ss=0, t=None):
    args = [FFMPEG, "-v", "error"] + (["-ss", str(ss)] if ss else []) + (["-t", "%.4f" % t] if t else []) + ["-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(args, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def mix(p, fi, out, lufs=-14):
    """The soundtrack → out (wav), or None when the film has no music and no cues. Levels: spec.sounds overrides MIX_MAP."""
    cues = list(fi.get("cues") or [])
    for b, name, gain in p.get("cues", []):
        cues.append({"t": b * 60.0 / p["bpm"], "name": name, "gain": gain})
    if not cues and not p.get("music"):
        return None
    dur = duration(p) + .6
    N = int(dur * SR)
    sfx = np.zeros((N, 2), np.float32)
    cache = {}

    def sound(name):
        if name not in cache:
            xs = []
            src = p.get("kit", {}).get(name)
            path = core.in_dir(core.LIB, src[4:]) if src else None
            paths = [path] if path and os.path.isfile(path) else [kit_path(n) for n in (name, name + "_2") if kit_path(n)]
            for f in paths:
                x = _decode(f)
                if len(x):
                    pk = np.abs(x).max() or 1; xs.append(x / pk * 10 ** (-1 / 20))
            cache[name] = xs
        return cache[name]

    def pick(names):
        for n in names.split("|"):
            if sound(n):
                return n
        return None
    onset = lambda x: int(np.argmax(np.abs(x).max(1) > .2 * np.abs(x).max()))
    peak = lambda x: int(np.argmax(np.abs(x).max(1)))

    def place(x, start, g):
        s = int(round(start * SR)); lo, hi = max(0, s), min(N, s + len(x))
        if hi > lo:
            sfx[lo:hi] += x[lo - s:hi - s] * g
    levels = p.get("sounds") or {}
    count = {}
    for c in cues:
        name, t, gain = c["name"], float(c["t"]), float(c.get("gain", 1))
        i = count.get(name, 0); count[name] = i + 1
        for names, align, off, db in MIX_MAP.get(name, [(name, 'onset', 0, -8)]):
            if name in levels:
                db = levels[name]
            k = pick(names)
            if not k:
                continue
            xs = sound(k); x = xs[i % len(xs)]; g = gain * 10 ** (db / 20)
            if align == 'loop':
                L = c.get('dur', 1); stp = len(x) / SR if k == 'tick_run' else .075; q = 0
                while q * stp < L:
                    place(x if k == 'tick_run' else x[:int(stp * SR * 1.5)], t + q * stp, g); q += 1
                continue
            if align == 'end':
                start = c.get('end', t) - len(x) / SR
            elif align == 'peak':
                start = t + off - peak(x) / SR
            else:
                start = t + off - onset(x) / SR
            if 'dur' in c and align == 'onset':
                L = int(c['dur'] * SR); x = x[:L].copy(); fl = min(len(x), int(.25 * SR)); x[-fl:] *= np.linspace(1, 0, fl)[:, None]
            place(x, start, g)
    music = np.zeros((N, 2), np.float32)
    m = p.get("music")
    if m:
        path = core.in_dir(core.LIB, m["src"][4:])
        if path and os.path.isfile(path):
            BEAT = 60.0 / p["bpm"]; stop = m.get("stopBeat")
            st = (stop * BEAT if stop else duration(p)) + .03
            mus = _decode(path, m.get("offset", 0), st)
            if len(mus):
                fi_ = min(len(mus), int(.012 * SR)); mus[:fi_] *= np.linspace(0, 1, fi_)[:, None]
                if stop:
                    e = int((stop * BEAT + .015) * SR); mus = mus[:e]; fo = min(len(mus), int(.02 * SR)); mus[-fo:] *= np.linspace(1, 0, fo)[:, None]
                else:
                    fo = min(len(mus), int(1.2 * SR)); mus[-fo:] *= np.linspace(1, 0, fo)[:, None]
                music[:min(N, len(mus))] = mus[:N] * 10 ** (m.get("gain", -3.5) / 20)
    duck = np.ones(N, np.float32)
    for c in cues:
        if c["name"] in BIG or c["name"] in levels:
            s = int(float(c["t"]) * SR); dd = .5 if c["name"] in ('impact_big', 'drop', 'logo_hit') else .62
            env = np.concatenate([np.linspace(1, dd, int(.03 * SR)), np.linspace(dd, 1, int(.35 * SR))])
            seg = duck[s:s + len(env)]; duck[s:s + len(env)] = np.minimum(seg, env[:len(seg)])
    mixed = (music * duck[:, None] + sfx) * 10 ** (-6 / 20)
    tmp = out + ".raw.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mixed, -1, 1) * 32767).astype("<i2").tobytes())
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([FFMPEG, "-v", "info", "-i", tmp, "-af", "loudnorm=I=%s:TP=-1:LRA=11:print_format=json" % lufs, "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags).stderr
    try:
        js = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
        af = "loudnorm=I=%s:TP=-1:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true" % (
            lufs, js["input_i"], js["input_tp"], js["input_lra"], js["input_thresh"], js["target_offset"])
    except Exception:
        af = "loudnorm=I=%s:TP=-1:LRA=11" % lufs
    _ff(["-i", tmp, "-af", af, "-ar", str(SR), "-t", "%.4f" % duration(p), out])
    os.remove(tmp)
    return out


# ── measuring: the beat grid of a track, the dynamism of a render ─────────────────────────────────────────────
def beat_grid(path, bpm=None, start=0.0, window=0.0):
    """Tempo, first strong downbeat (offset) and drop candidates of a music file → the film's bpm + music.offset."""
    sr, hop, nf = 22050, 128, 2048
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    x = np.frombuffer(raw, np.float32)
    if len(x) < nf * 4:
        raise RuntimeError("the track is too short to measure")
    fr = sr / hop
    win = np.hanning(nf).astype(np.float32)
    nfr = 1 + (len(x) - nf) // hop
    S = np.abs(np.fft.rfft(np.stack([x[i * hop:i * hop + nf] * win for i in range(nfr)]), axis=1))
    L = np.log1p(10 * S)
    flux = np.concatenate([[0], np.maximum(0, np.diff(L, axis=0)).sum(1)])
    low = np.concatenate([[0], np.maximum(0, np.diff(L[:, :int(150 / (sr / nf))], axis=0)).sum(1)])
    rms = np.sqrt((S ** 2).mean(1))

    def norm(v):
        v = v - np.convolve(v, np.ones(int(fr)) / int(fr), "same"); return np.maximum(v, 0)
    k0 = int(start * fr); k1 = int((start + window) * fr) if window else len(flux)
    e = norm(flux)[:k1]; low = low[:k1]
    ac = np.correlate(e[k0:], e[k0:], "full")[len(e) - k0 - 1:]
    lags = np.arange(len(ac)); bpms = 60 * fr / np.maximum(lags, 1)
    ok = (bpms >= 60) & (bpms <= 200)
    prior = np.exp(-.5 * (np.log2(bpms / (bpm or 120)) / (.25 if bpm else .9)) ** 2)
    score = np.where(ok, ac * prior, 0)
    lag = int(np.argmax(score))
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = score[lag - 1], score[lag], score[lag + 1]; lagf = lag + .5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-9)
    else:
        lagf = lag or 1
    est = 60 * fr / lagf

    def comb(P, phases):
        n = int((len(e) - k0) / P) - 1
        if n < 2:
            return np.zeros(len(phases))
        pos = k0 + phases[:, None] + P * np.arange(n)[None, :]
        i = np.clip(pos.astype(int), 0, len(e) - 2); fpart = pos - i
        return (e[i] * (1 - fpart) + e[i + 1] * fpart).mean(1)
    g = np.exp(-.5 * (np.arange(-12, 13) / (.015 * fr)) ** 2); g /= g.sum()
    kk = norm(low)
    e = np.convolve(e / (e.max() + 1e-9) + 1.5 * kk / (kk.max() + 1e-9), g, "same")
    best, P, ph = -1, lagf, 0
    lo, hi = (bpm * .92, bpm * 1.08) if bpm else (est * .985, est * 1.015)
    for b in np.arange(lo, hi, .01):
        Pb = 60 * fr / b; phs = np.linspace(0, Pb, 96, endpoint=False); sc = comb(Pb, phs); j = int(np.argmax(sc))
        if sc[j] > best:
            best, P, ph = sc[j], Pb, phs[j]
    bpm_ = 60 * fr / P
    n = max(0, int((len(e) - k0) / P) - 1)
    beats = k0 + ph + P * np.arange(n)
    kick = norm(low)
    bar = [kick[(beats[i::4]).astype(int)].sum() if len(beats) > i else 0 for i in range(4)]
    d0 = int(np.argmax(bar))
    down = beats[d0::4] / fr if len(beats) else np.array([0.0])
    strength = min(1.0, float(e[beats.astype(int)].mean() / (e.mean() + 1e-9) / 4)) if len(beats) else 0.0
    ev = np.convolve(rms, np.ones(int(fr)) / int(fr), "same")
    at_ = lambda t: ev[min(len(ev) - 1, int(t * fr))]
    bars = [(t, at_(t + 2 * 4 * 60 / bpm_) / (at_(t - 4 * 60 / bpm_) + 1e-9)) for t in down if t > 4 * 60 / bpm_]
    drops = sorted(bars, key=lambda q: -q[1])[:3]
    off = float(down[0])
    return {"bpm": round(float(bpm_), 2), "offset": round(off, 3), "downbeats": [round(float(t), 3) for t in down[:16]],
            "drops": [{"music_s": round(float(t), 2), "film_beat": round((t - off) * bpm_ / 60, 1), "rise": round(float(r), 2)} for t, r in sorted(drops)],
            "grid_strength": round(strength, 2), "duration": round(len(x) / sr, 2), "film_beats_available": int((len(x) / sr - off) * bpm_ / 60)}


def dynamism(video, dur, bpm, tail=4.5):
    """Still frames and holds, measured like the reference reels (under 1.5 % of the frame changing = still), end card excluded."""
    cv2 = _cv2()
    w, h = 320, 180
    span = max(1.0, dur - tail)
    p = subprocess.Popen([FFMPEG, "-v", "error", "-t", str(span), "-i", video, "-vf", "fps=60,scale=%d:%d" % (w, h), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    prev = None; A = []; DL = []
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h:
            break
        g = np.frombuffer(b, np.uint8).reshape(h, w)
        if prev is not None:
            d = cv2.absdiff(g, prev) if cv2 else np.abs(g.astype(np.int16) - prev.astype(np.int16))
            A.append(float((d > 24).mean())); DL.append(float(abs(g.mean() - prev.mean())))
        prev = g
    p.wait()
    if not A:
        return {"error": "no frames decoded"}
    A = np.array(A); DL = np.array(DL); still = A < .015; B = 60 / bpm
    runs = []; s0 = None
    for i, v in enumerate(list(still) + [False]):
        if v and s0 is None:
            s0 = i
        if not v and s0 is not None:
            runs.append((s0 / 60, (i - s0) / 60)); s0 = None
    cuts = int(((A > .45) & ((DL > 18) | (A > .6))).sum())
    holds = [{"at": round(a, 2), "beat": round(a / B, 1), "len": round(d, 2)} for a, d in runs if d > .6]
    longest = max([d for _, d in runs], default=0)
    return {"seconds": round(len(A) / 60, 2), "still_share": round(float(still.mean()), 3), "longest_hold_s": round(longest, 2),
            "holds": holds[:8], "cuts": cuts, "cuts_per_10s": round(cuts / (len(A) / 60) * 10, 2), "flips": int((DL > 40).sum()),
            "pass": bool(still.mean() <= .4 and not holds), "targets": "≤ 40 % still frames, no hold over 0.6 s before the end card"}


# ── the AI writer ─────────────────────────────────────────────────────────────────────────────────────────────
def ai_system():
    blocks = ("Words (shots:[{at,style:punch3d|slam|stack|pair|split|cut,text,ground,color,in:cut|whipX|whipY,fx:punch|hit|beat|none,big,size,rot}], charge, exit:{type:zoom|collapse|flash,at,char}); "
              "Strike (items:[{at,word,ground,ui:{type:timeline|tiles|rack,...}}]); Graph (number,label,sub,ground) 6 beats; Hero (kicker,title,sub,whipOut) 8 beats; "
              "Prompt (label,text:[[plain],[keyword,1]],unit) 19 beats; Stretch (word,grounds) 8; Fly (words:[[word,ground]...]) 11; Notes (preview,notes,segments) 16; "
              "Counters (counters:[[number,label]...]) 11; Progress (lines,cards) 9; Chain (nodes:[[word,sub,ground]...]) 12; Rewind (label) 8; "
              "Picture (src:'lib:<image>',words:[[beat,word,ground]],reveal:slash|zoom,tint,weather:rain|snow|dust|null,cutIns) 8; Logo (wordmark,tagline,small) 11")
    return ("You write kinetic launch films for MIR KINETIC: huge words on every beat, whip pans, colour flips, 3D letters, a hard drop. "
            "Reply with ONE JSON object: {name, bpm, beats, palette:{bg,paper,accent,hot,ink hex}, hud:'LABEL · TEASER', hudOut:[beats-3,beats-1], "
            "scenes:[{block, k0, k1, opts}], fx:[{type,k0,k1,params}], captions:[]}. Beats are absolute; scenes are sequential and never overlap; "
            "the Logo block ends the film and is 8-11 beats; keep blocks near their nominal length. One idea per beat or half beat, one or two words, "
            "all caps, no hold over 0.6 s. Grounds/colours are palette names: bg, paper, accent, hot, ink. Blocks and their options: " + blocks +
            ". Effects (fx, optional, 1-3 short ones): " + ", ".join(sorted(FX_TYPES)) + " with OpenKatana params (e.g. local_rgb_split {amount:12,mode:'radial'}, "
            "local_shockwave {at:0,d:.6}, local_light_sweep {d:1}). Only images listed as AVAILABLE MEDIA may be used as 'lib:<name>'. Never invent numbers about the product.")


# ── Flask routes ───────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, my_file, static(fn), session(sid)->valid sid, ask(prompt, system), words(path)->[{w,s,e}], lib_list()->[{name,kind,prompt}]"""
    from flask import abort, jsonify, request, send_file, send_from_directory

    def pdir():
        d = os.path.join(PROJ, re.sub(r"[^A-Za-z0-9_-]", "_", str(hk["uid"]())))
        os.makedirs(d, exist_ok=True)
        return d

    def owned(p):
        bad = []
        for r in media_refs(p):
            name = r[4:]
            path = core.in_dir(core.LIB, name)
            if not hk["my_file"](name) or not path or not os.path.isfile(path):
                bad.append(r)
        return bad

    @app.route("/motion/editor")
    def kinetic_editor():
        """The Motion editor (MIR KINETIC). /motion itself stays the Motion Studio producer (motion_wizard.py)."""
        return hk["static"]("motion_editor.html")

    # the engine for the live preview iframe: film.html + its modules/fonts/fx beside it, media + MIR fonts at their relative paths
    @app.route("/kinetic/engine/media/<path:name>")
    def kinetic_media(name):
        name = os.path.basename(name)
        p = core.in_dir(core.LIB, name)
        if not p or not os.path.isfile(p) or not hk["my_file"](name):
            abort(404)
        return send_file(p, max_age=300)

    @app.route("/kinetic/engine/mirfonts/<name>")
    def kinetic_font(name):
        name = os.path.basename(name)
        p = os.path.join(MIRFONTS, name)
        if not re.match(r"^[a-z0-9]+\.(woff2|ttf)$", name) or not os.path.isfile(p):
            abort(404)
        return send_file(p, max_age=86400)

    @app.route("/kinetic/engine/<path:fn>")
    def kinetic_engine(fn):
        return send_from_directory(WEB, fn, max_age=30)

    @app.route("/api/kinetic/health")
    def kn_health():
        return jsonify(health())

    @app.route("/api/kinetic/fonts")
    def kn_fonts():
        return jsonify({"fonts": fonts()})

    @app.route("/api/kinetic/templates")
    def kn_templates():
        out = []
        ex = os.path.join(ENGINE, "examples")
        for f in sorted(os.listdir(ex)) if os.path.isdir(ex) else []:
            if f.endswith(".json"):
                try:
                    with open(os.path.join(ex, f), encoding="utf-8") as fh:
                        d = clean(json.load(fh))
                    out.append({"id": f[:-5], "name": d["name"], "beats": d["beats"], "bpm": d["bpm"], "project": d})
                except Exception:
                    pass
        return jsonify({"templates": out})

    @app.route("/api/kinetic/projects")
    def kn_projects():
        out = []
        for f in os.listdir(pdir()):
            if f.endswith(".json") and not f.endswith(".hist.json"):
                try:
                    with open(os.path.join(pdir(), f), encoding="utf-8") as fh:
                        d = json.load(fh)
                    out.append({"id": d.get("id"), "name": d.get("name"), "updated": d.get("updated", 0), "beats": d.get("beats"), "bpm": d.get("bpm"),
                                "secs": round(duration(clean(d)), 1), "scenes": len(d.get("scenes") or []), "session": d.get("session") or ""})
                except Exception:
                    pass
        out.sort(key=lambda d: -(d.get("updated") or 0))
        return jsonify({"projects": out})

    @app.route("/api/kinetic/project/<pid>")
    def kn_get(pid):
        p = os.path.join(pdir(), pid + ".json")
        if not _ID_RE.match(pid) or not os.path.isfile(p):
            return jsonify({"error": "no such project"}), 404
        with open(p, encoding="utf-8") as fh:
            return jsonify(json.load(fh))

    @app.route("/api/kinetic/project", methods=["POST"])
    def kn_save():
        b = request.get_json(silent=True) or {}
        d = clean(b)
        d["session"] = hk["session"](b.get("session")) or ""
        pid = save_project(hk["uid"](), d)
        return jsonify({"ok": True, "id": pid, "secs": round(duration(d), 2)})

    @app.route("/api/kinetic/project/<pid>/versions")
    def kn_versions(pid):
        h = os.path.join(pdir(), pid + ".hist.json")
        if not _ID_RE.match(pid) or not os.path.isfile(h):
            return jsonify({"versions": []})
        with open(h, encoding="utf-8") as fh:
            vs = json.load(fh)
        return jsonify({"versions": [{"i": i, "updated": v.get("updated", 0), "name": v.get("name"), "scenes": len(v.get("scenes") or [])} for i, v in enumerate(vs)]})

    @app.route("/api/kinetic/project/<pid>/restore", methods=["POST"])
    def kn_restore(pid):
        h = os.path.join(pdir(), pid + ".hist.json")
        i = int(_num((request.get_json(silent=True) or {}).get("i"), -1, -1, 99))
        if not _ID_RE.match(pid) or not os.path.isfile(h) or i < 0:
            return jsonify({"error": "no such version"}), 404
        with open(h, encoding="utf-8") as fh:
            vs = json.load(fh)
        if i >= len(vs):
            return jsonify({"error": "no such version"}), 404
        return jsonify(vs[i])

    @app.route("/api/kinetic/project/<pid>/delete", methods=["POST"])
    def kn_delete(pid):
        p = os.path.join(pdir(), pid + ".json")
        if _ID_RE.match(pid) and os.path.isfile(p):
            shutil.move(p, os.path.join(core.TRASH, "kinetic_%s_%d.json" % (pid, int(time.time()))))
            try:
                os.remove(os.path.join(pdir(), pid + ".hist.json"))
            except Exception:
                pass
        return jsonify({"ok": True})

    @app.route("/api/kinetic/render", methods=["POST"])
    def kn_render():
        b = request.get_json(silent=True) or {}
        p = clean(b.get("project") or {})
        if not p["scenes"]:
            return jsonify({"error": "nothing to render — add a block"}), 400
        bad = owned(p)
        if bad:
            return jsonify({"error": "media not available: " + ", ".join(bad[:5])}), 400
        h = health()
        if not h["ok"]:
            return jsonify({"error": "engine offline: " + ", ".join(k for k in ("engine", "node", "chrome", "ffmpeg") if not h[k])}), 503
        o = b.get("options") or {}
        opts = {"blur": o.get("blur", True) is not False, "bloom": o.get("bloom", True) is not False, "grain": _num(o.get("grain"), 2.2, 0, 8),
                "crf": int(_num(o.get("crf"), 16, 10, 30)), "preset": o.get("preset") if o.get("preset") in ("fast", "medium", "slow", "slower") else "medium",
                "lufs": _num(o.get("lufs"), -14, -24, -8), "samples": int(_num(o.get("samples"), 12, 2, 99))}
        me = hk["uid"]()
        sid = hk["session"](b.get("session") if "session" in b else p.get("session")) or ""
        try:
            return jsonify(start_job(p, me, sid, opts, b.get("purpose") or ""))
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 409

    @app.route("/api/kinetic/jobs")
    def kn_jobs():
        me = hk["uid"]()
        js = [_pub(j) for j in JOBS.values() if j.get("user") == me]
        js.sort(key=lambda j: -j.get("started", 0))
        return jsonify({"jobs": js[:30]})

    @app.route("/api/kinetic/job/<jid>")
    def kn_job(jid):
        j = JOBS.get(jid)
        if not j or j.get("user") != hk["uid"]():
            return jsonify({"error": "no such render"}), 404
        return jsonify(_pub(j))

    @app.route("/api/kinetic/job/<jid>/cancel", methods=["POST"])
    def kn_cancel(jid):
        j = JOBS.get(jid)
        if j and j.get("user") == hk["uid"]() and j.get("status") == "running":
            j["status"] = "cancelled"; j["stage"] = "cancelled"
        return jsonify({"ok": True})

    @app.route("/api/kinetic/still", methods=["POST"])
    def kn_still():
        b = request.get_json(silent=True) or {}
        p = clean(b.get("project") or {})
        if owned(p):
            return jsonify({"error": "media not available"}), 400
        if not health()["ok"]:
            return jsonify({"error": "engine offline"}), 503
        try:
            return send_file(still(p, int(_num(b.get("frame"), 0, 0, 10 ** 6)), _num(b.get("scale"), .5, .1, 1)), mimetype="image/jpeg")
        except Exception as e:
            return jsonify({"error": str(e)[:400]}), 500

    @app.route("/api/kinetic/beats", methods=["POST"])
    def kn_beats():
        """Measure a library track: tempo, downbeat offset, drops → spec.bpm + music.offset."""
        b = request.get_json(silent=True) or {}
        name = os.path.basename(str(b.get("src") or "")[4:]) if str(b.get("src") or "").startswith("lib:") else ""
        path = core.in_dir(core.LIB, name) if name and hk["my_file"](name) else None
        if not path or not os.path.isfile(path):
            return jsonify({"error": "pick a track from your library"}), 400
        try:
            return jsonify(beat_grid(path, _num(b.get("bpm"), 0, 0, 300) or None, _num(b.get("start"), 0, 0, 36000), _num(b.get("window"), 0, 0, 3600)))
        except Exception as e:
            return jsonify({"error": str(e)[:300]}), 500

    @app.route("/api/kinetic/words", methods=["POST"])
    def kn_words():
        """Whisper word timings for a library audio/video → a caption track in beats."""
        b = request.get_json(silent=True) or {}
        s = str(b.get("src") or "")
        name = os.path.basename(s[4:]) if s.startswith("lib:") else ""
        path = core.in_dir(core.LIB, name) if name and hk["my_file"](name) else None
        if not path or not os.path.isfile(path):
            return jsonify({"error": "pick an audio or video from your library"}), 400
        try:
            words = hk["words"](path)
        except Exception as e:
            return jsonify({"error": str(e)[:300]}), 500
        bpm = _num(b.get("bpm"), 120, 40, 300); off = _num(b.get("offset"), 0, 0, 36000)
        tb = lambda s_: round(max(0.0, (float(s_) - off)) * bpm / 60, 2)
        caps, cur = [], []
        for w in words:
            cur.append([str(w.get("w") or "").strip(), tb(w.get("s", 0))])
            if len(cur) >= 6 or (cur and str(w.get("w") or "").rstrip().endswith((".", "!", "?"))):
                caps.append([cur[0][1], tb(w.get("e", 0)) + .5, cur]); cur = []
        if cur:
            caps.append([cur[0][1], cur[-1][1] + 2, cur])
        return jsonify({"words": words, "captions": caps})

    @app.route("/api/kinetic/ai", methods=["POST"])
    def kn_ai():
        """Request → a project (mode=project replaces the timeline; mode=scene returns one block for the inspector)."""
        b = request.get_json(silent=True) or {}
        ask = str(b.get("ask") or "").strip()[:3000]
        if not ask:
            return jsonify({"error": "say what you want"}), 400
        media = [m for m in hk["lib_list"]()[:80] if m.get("kind") in ("image", "audio")]
        ctx = "AVAILABLE MEDIA:\n" + ("\n".join("- %s (%s) %s" % (m["name"], m.get("kind"), (m.get("prompt") or "")[:80]) for m in media) or "- none")
        cur = b.get("project")
        if isinstance(cur, dict):
            c = clean(cur)
            ctx += "\nCURRENT FILM (%s beats at %s BPM, %ss): %s" % (c["beats"], c["bpm"], round(duration(c), 1), json.dumps({"scenes": c["scenes"], "fx": c["fx"], "palette": c["palette"]})[:7000])
        mode = b.get("mode") or "project"
        want = {"project": "Return the FULL film JSON (it replaces the timeline; keep what the user did not ask to change).",
                "scene": "Return {\"scenes\":[<ONE block>]} with k0/k1 relative to 0 (it is inserted at the playhead).",
                "props": "Return {\"scenes\":[<the selected block, rewritten>]} keeping its k0/k1."}.get(mode, "")
        if b.get("scene"):
            ctx += "\nSELECTED BLOCK: " + json.dumps(b["scene"])[:3000]
        secs = _num(b.get("secs"), 0, 0, 600)
        if secs:
            want += " Target length: %d seconds (beats = seconds * bpm / 60)." % secs
        try:
            raw = hk["ask"]("%s\n\n%s\n\nREQUEST: %s" % (ctx, want, ask), ai_system())
        except Exception as e:
            return jsonify({"error": "the writer failed: %s" % str(e)[:200]}), 500
        s = raw if isinstance(raw, dict) else None
        if s is None:
            m = re.search(r"\{.*\}", str(raw or ""), re.S)
            try:
                s = json.loads(m.group(0)) if m else {}
            except Exception:
                s = {}
        if not s.get("scenes"):
            return jsonify({"error": "the writer returned no blocks — try rephrasing", "raw": str(raw)[:500]}), 500
        base = clean(cur) if isinstance(cur, dict) else clean({})
        if mode == "project":
            merged = dict(base, **{k: v for k, v in s.items() if k in ("name", "bpm", "beats", "palette", "hud", "hudOut", "scenes", "fx", "captions", "cues", "sounds")})
            return jsonify(clean(merged))
        return jsonify({"scenes": clean(dict(base, scenes=s["scenes"], beats=MAX_BEATS))["scenes"], "fx": clean(dict(base, fx=s.get("fx") or [], beats=MAX_BEATS))["fx"]})


def _pub(j):
    return {k: v for k, v in j.items() if not k.startswith("_")}


def start_job(p, me, sid="", opts=None, purpose="", prefix="kinetic", after=None):
    """Queue a library render of a cleaned + ownership-checked project → the JOBS entry. after(job) runs once it is in the library."""
    with _JLOCK:
        if sum(1 for j in JOBS.values() if j.get("user") == me and j.get("status") == "running") >= 2:
            raise RuntimeError("two renders are already running — wait or cancel one")
    opts = opts or {}
    name = core.new_name(prefix, ".mp4")
    out = os.path.join(core.LIB, name)
    jid = "k" + uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "status": "running", "stage": "starting", "pct": 0.0, "user": me, "started": time.time(), "name": name,
                 "project": p.get("id"), "dur": round(duration(p), 2), "size_px": "%sx%s" % (p["w"], p["h"]), "purpose": purpose, "engine": "kinetic"}

    def done(job):
        meta = {"model": "motion", "prompt": str(p.get("name") or "Kinetic film")[:2000], "job": jid, "created": time.time(), "user": me, "mode": "motion",
                "engine": "kinetic", "size": "%sx%s" % (p["w"], p["h"]), "project": p.get("id"), "secs": round(duration(p), 2), "codec": "mp4"}
        if sid:
            meta["session"] = sid
        core.index_add(name, meta)
        job["url"] = "media/" + name
        job["src"] = "lib:" + name
        prune_cache()
        if after:
            try:
                after(job)
            except Exception as e:
                job["after_error"] = str(e)[:300]
    threading.Thread(target=render, args=(jid, p, out, opts, done), daemon=True).start()
    return _pub(JOBS[jid])


def prune_cache(max_gb=4.0):
    fs = []
    for f in os.listdir(CACHE):
        p = os.path.join(CACHE, f)
        try:
            fs.append((os.path.getmtime(p), os.path.getsize(p), p))
        except Exception:
            pass
    total = sum(s for _, s, _ in fs)
    for _, s, p in sorted(fs):
        if total <= max_gb * 2 ** 30:
            break
        try:
            os.remove(p); total -= s
        except Exception:
            pass


def save_project(uid, d):
    """Write a project into uid's list (keeping the last 12 versions beside it) → pid."""
    d = clean(d)
    pid = d.get("id") or ""
    if not _ID_RE.match(pid):
        pid = uuid.uuid4().hex[:12]
    d.update(id=pid, updated=time.time())
    pd = os.path.join(PROJ, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid)))
    os.makedirs(pd, exist_ok=True)
    fp = os.path.join(pd, pid + ".json")
    if os.path.isfile(fp):
        try:
            with open(fp, encoding="utf-8") as f:
                prev = json.load(f)
            h = os.path.join(pd, pid + ".hist.json")
            hist = []
            if os.path.isfile(h):
                with open(h, encoding="utf-8") as f:
                    hist = json.load(f)
            if not hist or json.dumps(hist[0].get("scenes"), sort_keys=True) != json.dumps(prev.get("scenes"), sort_keys=True) or hist[0].get("fx") != prev.get("fx"):
                hist.insert(0, prev)
            with open(h, "w", encoding="utf-8") as f:
                json.dump(hist[:12], f)
        except Exception:
            pass
    d.setdefault("created", time.time())
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return pid


# ── builders other modules can use when they port over (same shape as remotion.scene/project/render_sync) ────
def scene(block, k0, k1, opts=None):
    return {"id": uuid.uuid4().hex[:8], "block": block, "k0": round(k0, 3), "k1": round(k1, 3), "opts": opts or {}}


def project(name, bpm=120, beats=32, w=1920, h=1080, fps=60, scenes=None, palette=None, font="", session="", hud=""):
    return {"name": name, "w": w, "h": h, "fps": fps, "bpm": bpm, "beats": beats, "palette": palette or dict(PALETTE), "font": font,
            "hud": hud, "scenes": scenes or [], "fx": [], "captions": [], "cues": [], "sounds": {}, "kit": {}, "session": session}


def render_sync(p, out, opts=None, timeout=3600):
    """Blocking render for background pipelines. Returns out path."""
    p = clean(p)
    jid = "s" + uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "status": "running", "stage": "starting", "pct": 0.0, "user": "_pipeline", "started": time.time()}
    render(jid, p, out, opts or {}, lambda j: None)
    j = JOBS.pop(jid, {})
    if j.get("status") != "done":
        raise RuntimeError("kinetic render failed: %s" % (j.get("error") or j.get("status")))
    return out
