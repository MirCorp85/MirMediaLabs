"""OPENFIELD PACK — the Studio apps ported from wexloops/openfield (MIT), run by freefield.py's queue as "native" apps.

A native app's manifest (server/studio_packs/openfield/apps/<id>/app.json) has `"native": "<kind>"`; Python plans
the graphs here instead of one fixed workflow. Every graph still goes through freefield._render (live progress, cancel,
and the exact graph kept for "Download workflow" / "Open in ComfyUI").

  object3d  Object · Photo to 3D      TRELLIS.2 (core ComfyUI 0.42) → GLB (Studio 3D shelf) + turntable (library)
  stage     Stage · Block a Shot      browser clay blocking → LTX-2.5 Layout-to-Render IC-LoRA (look frame: FLUX Klein edit)
  seam      Seam Doctor               SEAM score (tiles + texture) → trim (ffmpeg) / re-render across the wrap / LTX bridge
  era       Era Look & Speed Ramp     1960-2020 film grade (numpy, any length, keeps sound) + FILM speed ramps (GPU)
  scene     Scene · Shot List to Cut  Gemma 3 12B plans shots inside ComfyUI → LTX-2.5 per shot → hard cuts

Also here: the phone drop box (QR → one-time LAN upload page) and the Stage editor's blocking ingest.
"""
import base64
import io
import json
import math
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid

try:
    import numpy as np
except ImportError:              # a build without numpy: the pixel passes report it instead of the module failing
    np = None

import comfy
import core

FFMPEG = core.FFMPEG
FFPROBE = os.path.join(os.path.dirname(core.FFMPEG), "ffprobe.exe" if os.name == "nt" else "ffprobe")
if not os.path.isfile(FFPROBE):
    import shutil as _sh
    FFPROBE = _sh.which("ffprobe") or FFPROBE
NO_WIN = 0x08000000 if os.name == "nt" else 0               # CREATE_NO_WINDOW: no console flashes


def _ff():
    import freefield
    return freefield


def _tmpdir():
    d = os.path.join(_ff().DATA, "tmp")
    os.makedirs(d, exist_ok=True)
    return d


def _tmp(ext):
    return os.path.join(_tmpdir(), "%s_%s%s" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6], ext))


def _run(args, inp=None, timeout=1800):
    p = subprocess.run(args, input=inp, capture_output=True, timeout=timeout, creationflags=NO_WIN)
    if p.returncode != 0:
        raise RuntimeError("%s failed: %s" % (os.path.basename(args[0]), (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:]))
    return p.stdout


def video_info(path):
    d = json.loads(_run([FFPROBE, "-v", "error", "-count_frames", "-show_entries",
                         "stream=codec_type,width,height,r_frame_rate,nb_read_frames", "-of", "json", path]))
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), None)
    if not v:
        raise _ff().InputError("the file has no picture")
    a, b = (str(v.get("r_frame_rate") or "24/1").split("/") + ["1"])[:2]
    fps = float(a) / float(b) if float(b or 0) else 24.0
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": fps or 24.0, "frames": int(v.get("nb_read_frames") or 0),
            "audio": any(s.get("codec_type") == "audio" for s in d.get("streams") or [])}


def _stage(j, text):
    j["stage"] = text
    j["progress"] = None


def _check_cancel(j):
    if j.get("_cancel"):
        raise comfy.Cancelled()


def _graph(a, name):
    with open(os.path.join(a["_dir"], name), encoding="utf-8") as f:
        return json.load(f)


def _prefix(g, aid):
    """Our own output subfolder for every Save node (ComfyUI's output dir stays tidy)."""
    for n in g.values():
        if str(n.get("class_type", "")).startswith(("Save", "VHS_VideoCombine")) and isinstance((n.get("inputs") or {}).get("filename_prefix"), str):
            n["inputs"]["filename_prefix"] = "%s/ff_%s" % (comfy.OUT_PREFIX or "mirmedialabs", aid.replace("-", "_"))
    return g


def render(a, j, graph, label=""):
    _check_cancel(j)
    outs, _ = _ff()._render(_prefix(graph, a["id"]), a, j, label=label)
    return outs


def entries(outs, node=None):
    """Every saved file a run reported (any output key: images / gifs / 3d / text …), optionally of one node."""
    out = []
    for nid, ent in (outs or {}).items():
        if node is not None and str(nid) != str(node):
            continue
        for v in (ent or {}).values():
            if isinstance(v, list):
                out += [e for e in v if isinstance(e, dict) and e.get("filename") and e.get("type", "output") == "output"]
    return out


def lib_save(src, a, j, prompt, label, ext=None, meta=None):
    """A local file or a ComfyUI output entry → the lab library (indexed like any Studio result)."""
    ext = ext or (os.path.splitext(src if isinstance(src, str) else src.get("filename", ""))[1].lower() or ".mp4")
    name = core.new_name("ff_%s" % a["id"].replace("-", "_"), ext)
    dest = os.path.join(core.LIB, name)
    if isinstance(src, dict):
        comfy.fetch(src, dest)
    else:
        import shutil
        shutil.copyfile(src, dest)
    core.index_add(name, dict({"model": "ff:" + a["id"], "tool": "Studio · " + a["name"], "prompt": (prompt or a["name"])[:2000],
                               "job": j["id"], "created": time.time(), "user": j.get("user") or "owner", "seed": j.get("seed"),
                               "output": label, **({"session": j["session"]} if j.get("session") else {})}, **(meta or {})))
    return name


def fetch_tmp(entry, ext=None):
    p = _tmp(ext or os.path.splitext(entry.get("filename", ""))[1] or ".bin")
    comfy.fetch(entry, p)
    return p


def frame_png(video, at_frame=0, size=None):
    p = _tmp(".png")
    vf = ["select=eq(n\\,%d)" % at_frame]
    if size:
        vf.append("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (size[0], size[1], size[0], size[1]))
    _run([FFMPEG, "-v", "error", "-y", "-i", video, "-vf", ",".join(vf), "-frames:v", "1", p])
    return p


# ── validation (called by freefield.submit so the form shows the error, not the queue) ─────────────────────────────
def validate(a, vals):
    kind = a.get("native")
    if kind == "stage" and not str(vals.get("prompt") or "").strip():
        raise _ff().InputError("Say what the shot is (the prompt)")
    if kind == "scene" and len(str(vals.get("scene") or "").strip()) < 12:
        raise _ff().InputError("Write the scene in a sentence or two")
    if kind not in ("object3d", "stage", "seam", "era", "scene"):
        raise _ff().InputError("unknown pack app kind: %s" % kind)


def run(a, j, vals):
    kind = a["native"]
    return {"object3d": run_object, "stage": run_stage, "seam": run_seam, "era": run_era, "scene": run_scene}[kind](a, j, vals)


# ══ OBJECT · photo → 3D (TRELLIS.2) ═══════════════════════════════════════════════════════════════════════════════
_OBJ_KNOBS = ("up", "kS", "kG", "kU", "kT")


def run_object(a, j, vals):
    q = "high" if vals.get("quality") == "high" else "draft"
    own = vals.get("cutout") == "own"
    g = _graph(a, "object-own-alpha.json" if own else "object-%s.json" % q)
    if own:                                       # the own-alpha graph takes the chosen quality's step counts
        ref = _graph(a, "object-%s.json" % q)
        for k in _OBJ_KNOBS:
            if k in g and k in ref:
                for f in ("steps", "target_resolution"):
                    if f in ref[k]["inputs"] and f in g[k]["inputs"]:
                        g[k]["inputs"][f] = ref[k]["inputs"][f]
    _stage(j, "uploading the photo")
    img = next(k for k, n in g.items() if n["class_type"] == "LoadImage")
    g[img]["inputs"]["image"] = comfy.upload(vals["image"]["path"])
    seed = int(vals.get("seed") or 0) % (2 ** 31)
    for i, k in enumerate(("kS", "kG", "kU", "kT")):
        if k in g:
            g[k]["inputs"]["seed"] = seed + i
    outs = render(a, j, g, "Object (%s)" % q)
    glbs = [e for e in entries(outs) if e["filename"].lower().endswith((".glb", ".gltf"))]
    vids = [e for e in entries(outs) if e["filename"].lower().endswith((".mp4", ".webm", ".mov"))]
    if not glbs:
        raise RuntimeError("TRELLIS finished but saved no GLB")
    _stage(j, "saving the model")
    glb = core.new_name("ff_object3d", ".glb")
    comfy.fetch(glbs[0], os.path.join(_ff().MODELS3D, glb))
    j["models3d"] = [glb]
    meta = {"glb": glb, "src_name": vals["image"].get("name")}
    core.save_json(os.path.join(_ff().MODELS3D, glb + ".json"), {"made": time.time(), "job": j["id"], "user": j.get("user") or "owner",
                                                               "from": os.path.basename(vals["image"]["path"]), "quality": q})
    files = [lib_save(v, a, j, "3D model · " + (vals["image"].get("name") or "object"), "Turntable", meta=meta) for v in vids[:1]]
    return files


def models3d(user=None):
    d = _ff().MODELS3D
    out = []
    for n in sorted(os.listdir(d), reverse=True):
        if not n.lower().endswith(".glb"):
            continue
        m = core.load_json(os.path.join(d, n + ".json"), {})
        if user and (m.get("user") or "owner") != user:
            continue
        out.append({"name": n, "made": m.get("made") or os.path.getmtime(os.path.join(d, n)), "quality": m.get("quality"),
                    "size": os.path.getsize(os.path.join(d, n))})
    return out


# ══ ERA GRADE + SPEED RAMP (OpenField catalog.ts / graphs/director.ts) ════════════════════════════════════════════
ERA_DECADES = [
    (1960, "1960s period film, dye-transfer color, rich reds and painted skies, soft contrast, fine grain",
     dict(sat=1.3, contrast=0.92, fade=0.04, lift=(0.0, 0.04, 0.06), gain=(1.1, 1.0, 0.84), grain=0.06, bloom=0.12, vignette=0.38)),
    (1970, "1970s film look, warm faded color, lifted blacks, soft contrast, heavy grain",
     dict(sat=0.74, contrast=0.84, fade=0.11, lift=(0.05, 0.03, 0.0), gain=(1.06, 0.98, 0.82), grain=0.085, bloom=0.15, vignette=0.3)),
    (1980, "1980s look, punchy saturated color, diffusion filter bloom on the highlights",
     dict(sat=1.28, contrast=1.08, fade=0.03, lift=(0.025, 0.0, 0.04), gain=(1.03, 0.96, 1.02), grain=0.05, bloom=0.42, vignette=0.2)),
    (1990, "1990s look, slightly green shadows, analog print texture",
     dict(sat=0.94, contrast=1.06, fade=0.03, lift=(0.0, 0.035, 0.01), gain=(1.03, 1.0, 0.93), grain=0.045, bloom=0.08, vignette=0.22)),
    (2000, "early 2000s look, desaturated bleach-bypass contrast, cool steel tones",
     dict(sat=0.5, contrast=1.35, fade=0.0, lift=(0.0, 0.02, 0.03), gain=(0.94, 1.0, 1.02), grain=0.035, bloom=0.05, vignette=0.3)),
    (2010, "2010s digital cinema look, teal shadows and warm skin tones, clean image",
     dict(sat=1.05, contrast=1.1, fade=0.0, lift=(-0.01, 0.02, 0.045), gain=(1.06, 1.0, 0.93), grain=0.012, bloom=0.04, vignette=0.15)),
    (2020, "modern high-dynamic-range digital look, clean and crisp",
     dict(sat=1.08, contrast=1.04, fade=0.0, lift=(0.0, 0.0, 0.0), gain=(1.0, 1.0, 1.0), grain=0.0, bloom=0.02, vignette=0.08)),
]


def era_text(year):
    return min(ERA_DECADES, key=lambda d: abs(d[0] - year))[1]


def era_grade(year):
    """Grade knobs for a year: eased blend between the decades either side (catalog.ts eraGrade)."""
    y = max(1960, min(2020, int(round(year))))
    i = min(len(ERA_DECADES) - 2, (y - 1960) // 10)
    a, b = ERA_DECADES[i][2], ERA_DECADES[i + 1][2]
    lin = (y - ERA_DECADES[i][0]) / 10.0
    t = lin * lin * (3 - 2 * lin)
    mix = lambda x, z: x + (z - x) * t
    return {k: (tuple(mix(a[k][c], b[k][c]) for c in range(3)) if isinstance(a[k], tuple) else mix(a[k], b[k])) for k in a}


def grade_frame(f, g, amount, rng):
    """GRADE_SHADER (graphs/director.ts) in numpy on one RGB float32 frame 0..1. Bloom: a blur of the highlights
    (the shader's 16-tap ring, as a gaussian); grain: per-frame noise weighted toward the mid-tones."""
    import cv2
    src = f
    c = f.copy()
    h, w = f.shape[:2]
    if g["bloom"] > 0:
        r = max(w, h) * 0.012
        hi = np.maximum(f - 0.55, 0.0)
        c += cv2.GaussianBlur(hi, (0, 0), sigmaX=max(1.0, r * 1.4)) * g["bloom"] * 2.2
    l = c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722
    c = l[..., None] + (c - l[..., None]) * g["sat"]
    c = (c - 0.5) * g["contrast"] + 0.5
    wgt = np.clip(l, 0, 1)
    wgt = (wgt * wgt * (3 - 2 * wgt))[..., None]
    c += np.array(g["lift"], np.float32) * (1 - wgt)
    c *= 1 + (np.array(g["gain"], np.float32) - 1) * wgt
    c = g["fade"] + (1 - g["fade"] * 0.35 - g["fade"]) * np.clip(c, 0, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xx / w - 0.5, yy / h - 0.5
    c *= (1 - g["vignette"] * (dx * dx + dy * dy) * 1.6)[..., None]
    if g["grain"] > 0:
        n = rng.random((h, w), dtype=np.float32) - 0.5
        c += (n * g["grain"] * (1.2 - np.abs(l - 0.5)))[..., None]
    return np.clip(src + (np.clip(c, 0, 1) - src) * amount, 0, 1)


def grade_video(src, year, amount=1.0, j=None):
    """Stream a clip through the era grade with ffmpeg (any length; the sound is copied across untouched)."""
    info = video_info(src)
    w, h = info["w"] - info["w"] % 2, info["h"] - info["h"] % 2
    out = _tmp(".mp4")
    g = era_grade(year)
    rng = np.random.default_rng(1234)
    dec = subprocess.Popen([FFMPEG, "-v", "error", "-i", src, "-vf", "scale=%d:%d" % (w, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, creationflags=NO_WIN)
    enc_args = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h), "-r", "%.6f" % info["fps"], "-i", "-"]
    if info["audio"]:
        enc_args += ["-i", src, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    enc_args += ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    enc = subprocess.Popen(enc_args, stdin=subprocess.PIPE, creationflags=NO_WIN)
    size, k, total = w * h * 3, 0, max(1, info["frames"])
    try:
        while True:
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            f = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0
            enc.stdin.write((grade_frame(f, g, amount, rng) * 255.0 + 0.5).astype(np.uint8).tobytes())
            k += 1
            if j is not None:
                if j.get("_cancel"):
                    raise comfy.Cancelled()
                if k % 8 == 0:
                    j["stage"] = "grading %d%%" % min(99, k * 100 // total)
                    j["progress"] = {"what": "era grade", "value": k, "max": total, "pct": min(99, k * 100 // total)}
    finally:
        try:
            enc.stdin.close()
        except Exception:
            pass
        dec.kill()
        enc.wait(600)
    if enc.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("the graded clip could not be written")
    return out


RAMPS = ("linear", "slowmo", "rampup", "impact", "bullet")


def _sm(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ramp_speed(rid, u):
    if rid == "slowmo":
        return 0.5
    if rid == "rampup":
        return 0.35 + 1.45 * _sm(0.15, 0.85, u)
    if rid == "impact":
        return 1.35 - 1.1 * _sm(0.32, 0.44, u) * (1 - _sm(0.6, 0.72, u))
    if rid == "bullet":
        return 1 - 0.8 * _sm(0.25, 0.4, u) * (1 - _sm(0.6, 0.75, u))
    return 1.0


def ramp_plan(rid, frames):
    """catalog.ts rampPlan: FILM multiplier + which frames of the dense batch the output keeps."""
    if rid == "linear" or frames < 2:
        return 1, list(range(frames))
    span = frames - 1
    mn = min(ramp_speed(rid, i / 100.0) for i in range(101))
    mult = max(2, min(5, int(math.ceil(1 / mn - 1e-6))))
    last = span * mult
    idx, s = [], 0.0
    while s <= span + 1e-9:
        idx.append(min(last, int(round(s * mult))))
        s += ramp_speed(rid, s / span)
    if idx[-1] != last:
        idx.append(last)
    return mult, idx


RAMP_MAX_S = 10          # FILM holds every in-between frame in RAM: cap the ramped section
RAMP_MAX_SIDE = 1280


def ramp_video(a, j, src, rid):
    """Retime a clip on the GPU: FILM fills in-betweens, GetImagesFromBatchIndexed keeps frames along the speed curve.
    The ramped clip is silent (the sound no longer lines up)."""
    info = video_info(src)
    clip = src
    if info["frames"] > RAMP_MAX_S * info["fps"] + 1 or max(info["w"], info["h"]) > RAMP_MAX_SIDE:
        _stage(j, "fitting the clip for the ramp")
        k = min(1.0, RAMP_MAX_SIDE / float(max(info["w"], info["h"])))
        w, h = int(info["w"] * k) // 2 * 2, int(info["h"] * k) // 2 * 2
        clip = _tmp(".mp4")
        _run([FFMPEG, "-v", "error", "-y", "-i", src, "-t", str(RAMP_MAX_S), "-vf", "scale=%d:%d" % (w, h), "-an",
              "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", clip])
        info = video_info(clip)
    mult, idx = ramp_plan(rid, info["frames"])
    g = {
        "src": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(clip)}},
        "parts": {"class_type": "GetVideoComponents", "inputs": {"video": ["src", 0]}},
        "film": {"class_type": "FrameInterpolationModelLoader", "inputs": {"model_name": "film_net_fp16.safetensors"}},
        "vfi": {"class_type": "FrameInterpolate", "inputs": {"interp_model": ["film", 0], "images": ["parts", 0], "multiplier": mult}},
        "pick": {"class_type": "GetImagesFromBatchIndexed", "inputs": {"images": ["vfi", 0], "indexes": ", ".join(map(str, idx))}},
        "vid": {"class_type": "CreateVideo", "inputs": {"images": ["pick", 0], "fps": ["parts", 2]}},
        "save": {"class_type": "SaveVideo", "inputs": {"video": ["vid", 0], "filename_prefix": "ramp", "format": "auto", "codec": "auto"}},
    }
    outs = render(a, j, g, "Speed ramp (%s)" % rid)
    v = [e for e in entries(outs, "save")]
    if not v:
        raise RuntimeError("the speed ramp saved nothing")
    return fetch_tmp(v[0], ".mp4")


def post(a, j, path, year=0, ramp="linear", amount=1.0):
    """Era grade then speed ramp on a finished clip (Stage / Scene / Era app)."""
    out = path
    if year:
        _stage(j, "era grade · %ds" % (int(year) // 10 * 10))
        out = grade_video(out, year, amount, j)
    if ramp and ramp != "linear":
        _stage(j, "speed ramp · " + ramp)
        out = ramp_video(a, j, out, ramp)
    return out


def run_era(a, j, vals):
    src = vals["clip"]["path"]
    out = post(a, j, src, int(vals.get("year") or 1974), vals.get("ramp") or "linear", float(vals.get("amount", 1.0)))
    tag = "%d look" % int(vals.get("year") or 1974) + ("" if (vals.get("ramp") or "linear") == "linear" else " · " + vals["ramp"])
    return [lib_save(out, a, j, tag + " · " + (vals["clip"].get("name") or "clip"), "Graded clip", ".mp4")]


# ══ STAGE · clay blocking → LTX-2.5 Layout-to-Render (graphs/stage.ts) ═════════════════════════════════════════════
LTX_T = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
LTX_TE = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
LTX_VAE = "ltx-2.5-video-vae-bf16.safetensors"
LTX_AVAE = "ltx-2.5-audio-vae-bf16.safetensors"
LTX_UP = "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
LAYOUT_LORA = "ltx-2.5-22b-ic-lora-layout-to-render-1.0.safetensors"
SIG1 = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
SIG2 = "0.909375, 0.725, 0.421875, 0.0"
NEG = "pc game, console game, video game, cartoon, childish, ugly"
STAGE_FPS = 24
STAGE_MAX_FRAMES = 121                    # 5 s at 24 fps: what a 16 GB card renders at 720p


def _ltx_name(base):
    """A model's name as ComfyUI knows it on this PC (same model, other quant / subfolder counts)."""
    for d in ("diffusion_models", "text_encoders", "vae", "latent_upscale_models", "loras"):
        name, how = _ff().resolve_model({"file": base, "dir": d})
        if name:
            return name
    return base


def stage_frames(n):
    return max(9, min(STAGE_MAX_FRAMES, (n - 1) // 8 * 8 + 1))


def fit_clay(src, j):
    """The clay clip on LTX's grid: sides a multiple of 64 (≤ 1280), 24 fps, 8k+1 frames, silent, near-lossless."""
    info = video_info(src)
    k = min(1.0, 1280.0 / max(info["w"], info["h"]))
    w = max(256, int(info["w"] * k) // 64 * 64)
    h = max(256, int(info["h"] * k) // 64 * 64)
    total = int(round(info["frames"] / info["fps"] * STAGE_FPS)) if info["fps"] else info["frames"]
    n = stage_frames(max(9, total))
    out = _tmp(".mp4")
    _stage(j, "fitting the clay to %dx%d · %d frames" % (w, h, n))
    _run([FFMPEG, "-v", "error", "-y", "-i", src, "-vf", "fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (STAGE_FPS, w, h, w, h),
          "-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    return out, w, h, n


def look_edit_instruction(text):
    t = re.sub(r"\s+", " ", str(text).strip())
    if t and t[-1] not in ".!?":
        t += "."
    return ("Keep the exact camera angle, framing, perspective, object positions, sizes and proportions of image 1. "
            "Do not move, add or remove anything. Turn the grey clay shapes into a finished, photographic film still: " + t)


def stage_shot_graph(clay, w, h, look, prompt, seed):
    half = min(w, h) // 2
    def guide(pos, neg, lat, img, frame, factor, crop):
        return {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {
            "positive": pos, "negative": neg, "vae": ["vvae", 0], "latent": lat, "image": img, "frame_idx": frame, "strength": 1,
            "latent_downscale_factor": factor, "crop": crop, "use_tiled_encode": False, "tile_size": 256, "tile_overlap": 64,
            "use_streaming": False, "tile_frames": 97}}
    return {
        "vvae": {"class_type": "VAELoader", "inputs": {"vae_name": _ltx_name(LTX_VAE)}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": _ltx_name(LTX_T), "weight_dtype": "default"}},
        "icl": {"class_type": "LTXICLoRALoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": _ltx_name(LAYOUT_LORA), "strength_model": 1}},
        "upmodel": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": _ltx_name(LTX_UP)}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": _ltx_name(LTX_TE), "type": "ltxv", "device": "default"}},
        "clay": {"class_type": "LoadVideo", "inputs": {"file": clay}},
        "clayParts": {"class_type": "GetVideoComponents", "inputs": {"video": ["clay", 0]}},
        "clayHalf": {"class_type": "ResizeImageMaskNode", "inputs": {"input": ["clayParts", 0], "resize_type": "scale shorter dimension",
                                                                     "resize_type.shorter_size": half, "scale_method": "lanczos"}},
        "claySize": {"class_type": "GetImageSize", "inputs": {"image": ["clayHalf", 0]}},
        "look": {"class_type": "LoadImage", "inputs": {"image": look}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": ""}},
        "cond": {"class_type": "LTXVConditioning", "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": ["clayParts", 2]}},
        "lat1": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": ["claySize", 0], "height": ["claySize", 1], "length": ["claySize", 2], "batch_size": 1}},
        "g1clay": guide(["cond", 0], ["cond", 1], ["lat1", 0], ["clayHalf", 0], 0, ["icl", 1], "disabled"),
        "g1look": guide(["g1clay", 0], ["g1clay", 1], ["g1clay", 2], ["look", 0], -1, ["icl", 1], "center"),
        "noise1": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "cfg1": {"class_type": "CFGGuider", "inputs": {"model": ["icl", 0], "positive": ["g1look", 0], "negative": ["g1look", 1], "cfg": 1}},
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "sig1": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIG1}},
        "s1": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise1", 0], "guider": ["cfg1", 0], "sampler": ["sampler", 0], "sigmas": ["sig1", 0], "latent_image": ["g1look", 2]}},
        "crop1": {"class_type": "LTXVCropGuides", "inputs": {"positive": ["g1look", 0], "negative": ["g1look", 1], "latent": ["s1", 0]}},
        "up": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["crop1", 2], "upscale_model": ["upmodel", 0], "vae": ["vvae", 0]}},
        "g2clay": guide(["cond", 0], ["cond", 1], ["up", 0], ["clayHalf", 0], 0, 1, "disabled"),
        "g2look": guide(["g2clay", 0], ["g2clay", 1], ["g2clay", 2], ["look", 0], -1, 1, "center"),
        "noise2": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "cfg2": {"class_type": "CFGGuider", "inputs": {"model": ["icl", 0], "positive": ["g2look", 0], "negative": ["g2look", 1], "cfg": 1}},
        "sig2": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIG2}},
        "s2": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise2", 0], "guider": ["cfg2", 0], "sampler": ["sampler", 0], "sigmas": ["sig2", 0], "latent_image": ["g2look", 2]}},
        "crop2": {"class_type": "LTXVCropGuides", "inputs": {"positive": ["g2look", 0], "negative": ["g2look", 1], "latent": ["s2", 0]}},
        "dv": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["crop2", 2], "vae": ["vvae", 0], "tile_size": 512, "overlap": 64, "temporal_size": 128, "temporal_overlap": 32}},
        "vid": {"class_type": "CreateVideo", "inputs": {"images": ["dv", 0], "fps": ["clayParts", 2], "bit_depth": 8, "color_space": "sRGB", "codec": "none"}},
        "save": {"class_type": "SaveVideo", "inputs": {"video": ["vid", 0], "filename_prefix": "stage", "format": "auto", "codec": "auto"}},
    }


def run_stage(a, j, vals):
    ff = _ff()
    prompt = str(vals["prompt"]).strip()
    seed = int(vals.get("seed") or 0) % (2 ** 48)
    clay, w, h, n = fit_clay(vals["clay"]["path"], j)
    files = []
    if vals.get("look"):
        look = vals["look"]["path"]
    else:                                         # look frame: FLUX Klein edit of the clay's first frame (Studio Edit)
        if not ff.ready("edit"):
            raise RuntimeError("No look frame: add one, or get the Studio Edit app's models (FLUX Klein paints the look frame)")
        lw, lh = (1344, int(round(1344 * h / w / 16)) * 16) if w >= h else (int(round(1344 * w / h / 16)) * 16, 1344)
        first = frame_png(clay, 0, (lw, lh))
        ea = ff.get("edit")
        r = ff.readiness(ea, refresh=True)
        g, _ = ff.build(ea, {"image": {"path": first}, "instruction": look_edit_instruction(prompt), "seed": seed % (2 ** 31)},
                        asset=lambda f: comfy.upload(f["path"]), aliases=r["aliases"])
        _stage(j, "painting the look frame")
        outs = render(a, j, g, "Stage look frame (FLUX Klein edit)")
        imgs = [e for e in entries(outs) if e["filename"].lower().endswith((".png", ".jpg", ".webp"))]
        if not imgs:
            raise RuntimeError("the look frame came out empty")
        look = fetch_tmp(imgs[0], ".png")
        files.append(lib_save(look, a, j, "Stage look frame · " + prompt, "Look frame", ".png"))
    _stage(j, "uploading the blocking")
    g = stage_shot_graph(comfy.upload(clay), w, h, comfy.upload(look), prompt, seed)
    outs = render(a, j, g, "Stage shot (LTX-2.5 Layout to Render)")
    vids = [e for e in entries(outs, "save")]
    if not vids:
        raise RuntimeError("the shot saved nothing")
    shot = fetch_tmp(vids[0], ".mp4")
    shot = post(a, j, shot, int(vals.get("era") or 0), vals.get("ramp") or "linear")
    files.insert(0, lib_save(shot, a, j, prompt, "Shot", ".mp4", meta={"stage_clay": os.path.basename(vals["clay"]["path"])}))
    return files


# ══ SEAM DOCTOR (server/seam.ts + graphs/seam.ts) ══════════════════════════════════════════════════════════════════
SEAM = dict(wrapInvisible=3.0, seamless=1.5, localFloor=0.05, textureSeamless=2.0, textureInvisible=0.35, textureFloor=0.08, minFrames=8)
TILES, TILE_W, TEX_W = 8, 256, 416


def _gray(path, width, info):
    h = max(2, 2 * int(round(width * info["h"] / info["w"] / 2)))
    raw = _run([FFMPEG, "-v", "error", "-i", path, "-vf", "scale=%d:%d:flags=area" % (width, h), "-fps_mode", "passthrough", "-an",
                "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    n = len(raw) // (width * h)
    return np.frombuffer(raw[:n * width * h], np.uint8).reshape(n, h, width)


def _tiles(fr):
    n, h, w = fr.shape
    th, tw = h // TILES, w // TILES
    return fr[:, :th * TILES, :tw * TILES].reshape(n, TILES, th, TILES, tw).astype(np.float32).mean(axis=(2, 4)).reshape(n, -1)


def seam_load(path):
    info = video_info(path)
    a, b = _gray(path, TILE_W, info), _gray(path, TEX_W, info)
    n = min(len(a), len(b))
    if n < SEAM["minFrames"]:
        raise _ff().InputError("The clip is %d frames; the seam check needs at least %d." % (n, SEAM["minFrames"]))
    tiles, tex = _tiles(a[:n]), b[:n].astype(np.int16)
    return {"tiles": tiles, "tex": tex, "fps": info["fps"], "w": info["w"], "h": info["h"], "n": n,
            "ts": np.abs(np.diff(tex, axis=0)).mean(axis=(1, 2)), "cs": np.abs(np.diff(tiles, axis=0)).max(axis=1)}


def _tex(a, b):
    return float(np.abs(a - b).mean())


def _tile(a, b):
    return float(np.abs(a - b).max())


def _med(xs):
    return float(np.median(xs)) if len(xs) else 0.0


def score_window(L, start=0, end=None):
    end = L["n"] if end is None else end
    n = end - start
    tex_steps = L["ts"][start:end - 1]
    tile_steps = L["cs"][start:end - 1]
    loc = [i for i in (1, 2, 3, n - 4, n - 3, n - 2) if 0 <= i < n - 1]
    tex_wrap = _tex(L["tex"][end - 1], L["tex"][start])
    tex_local = max(_med([tex_steps[i] for i in loc]), SEAM["textureFloor"])
    tile_wrap = _tile(L["tiles"][end - 1], L["tiles"][start])
    tile_local = max(_med([tile_steps[i] for i in loc]), SEAM["localFloor"])
    tr, cr = tex_wrap / tex_local, tile_wrap / tile_local
    tex_ok = tex_wrap < SEAM["textureInvisible"] or tr <= SEAM["textureSeamless"]
    comp_ok = tile_wrap < SEAM["wrapInvisible"] or cr <= SEAM["seamless"]
    ratio = tr if comp_ok else max(tr, cr)
    return {"n": n, "fps": round(L["fps"], 3), "verdict": "seamless" if tex_ok and comp_ok else "visible", "ratio": round(ratio, 2),
            "texture": {"wrap": round(tex_wrap, 3), "local": round(tex_local, 3), "ratio": round(tr, 3)},
            "composition": {"wrap": round(tile_wrap, 3), "local": round(tile_local, 3), "ratio": round(cr, 3)}}


def measure(path, splices=()):
    L = seam_load(path)
    m = score_window(L)
    sp = [f for f in splices if 0 < f < L["n"]]
    if sp:
        base = max(_med(L["ts"][1:]), SEAM["textureFloor"])
        m["splices"] = [{"frame": f, "ratio": round(_tex(L["tex"][f - 1], L["tex"][f]) / base, 2)} for f in sp]
        worst = max(s["ratio"] for s in m["splices"])
        if worst > SEAM["textureSeamless"]:
            m["verdict"] = "visible"
        m["ratio"] = round(max(m["ratio"], worst), 2)
    return m


def plan_trim(L):
    n = L["n"]
    min_len = max(SEAM["minFrames"], int(math.ceil(n / 2.0)))      # a trim keeps at least half the loop
    base = max(_med(L["ts"][1:]), SEAM["textureFloor"])
    for ln in range(n - 1, min_len - 1, -1):
        best = None
        for s in range(0, n - ln + 1):
            if _tex(L["tex"][s + ln - 1], L["tex"][s]) > SEAM["textureSeamless"] * 1.25 * base:
                continue
            m = score_window(L, s, s + ln)
            if m["verdict"] == "seamless" and (not best or m["ratio"] < best[2]["ratio"]):
                best = (s, ln, m)
        if best:
            return {"start": best[0], "frames": best[1], "predicted": best[2]}
    return None


def plan_bridge(n, fps, seconds=1.0):
    want = int(round(seconds * fps))
    inner = max(7, int(round((2 * want + 1) / 8.0)) * 8 - 1)
    while inner > 7 and n - inner < math.ceil(n / 3.0):
        inner -= 8
    if n - inner < 2:
        raise _ff().InputError("A %d-frame clip is too short to bridge." % n)
    a_ = inner // 2
    b_ = inner - a_
    return {"anchorA": n - 1 - a_, "anchorB": b_, "inner": inner, "bridgeFrames": inner + 2, "splice": (n - 1 - a_) - b_ + 1}


def _fit32(src, info, j):
    """LTX needs sides on a 32 grid; the fix and the body must share one size."""
    if info["w"] % 32 == 0 and info["h"] % 32 == 0:
        return src, info
    w, h = max(256, info["w"] // 32 * 32), max(256, info["h"] // 32 * 32)
    _stage(j, "fitting the loop to %dx%d" % (w, h))
    out = _tmp(".mp4")
    _run([FFMPEG, "-v", "error", "-y", "-i", src, "-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h),
          "-an", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", out])
    return out, video_info(out)


def _trim(src, start, frames, fps):
    out = _tmp(".mp4")
    _run([FFMPEG, "-v", "error", "-y", "-i", src, "-vf", "select=between(n\\,%d\\,%d),setpts=N/(%.6f*TB)" % (start, start + frames - 1, fps),
          "-r", "%.6f" % fps, "-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    return out


def _ltx_names(g):
    for n in g.values():
        i = n.get("inputs") or {}
        for k in ("unet_name", "clip_name", "vae_name"):
            if isinstance(i.get(k), str):
                i[k] = _ltx_name(i[k])
    return g


def seam_bridge_graph(a, video, info, plan, prompt, seed):
    g = _ltx_names(_graph(a, "seam-bridge.json"))
    n, fps = info["frames"], info["fps"]
    g["src"]["inputs"].update(video=video, frame_load_cap=n, skip_first_frames=0)
    g["body"]["inputs"].update(batch_index=plan["anchorB"], length=plan["anchorA"] - plan["anchorB"] + 1)
    g["anchorA"]["inputs"]["batch_index"] = plan["anchorA"]
    g["anchorB"]["inputs"]["batch_index"] = plan["anchorB"]
    g["pos"]["inputs"]["text"] = prompt
    g["cond"]["inputs"]["frame_rate"] = fps
    g["latV"]["inputs"].update(width=info["w"], height=info["h"], length=plan["bridgeFrames"])
    g["latA"]["inputs"].update(frames_number=plan["bridgeFrames"], frame_rate=fps)
    g["noise1"]["inputs"]["noise_seed"] = seed
    g["inner"]["inputs"].update(batch_index=1, length=plan["inner"])
    g["out"]["inputs"]["frame_rate"] = fps
    return g


def seam_regen_graph(a, video, info, prompt, seed, sigma):
    n, fps = info["frames"], info["fps"]
    if n % 8 != 1:
        raise _ff().InputError("A re-render across the wrap needs an 8k+1 frame loop; this one has %d frames. Use Trim or Bridge." % n)
    if n < 33:
        raise _ff().InputError("A %d-frame loop is too short to re-render across its wrap." % n)
    h = (n - 1) // 2
    hold_start, hold_end = 9, 8
    tail = [0.725, 0.4219]
    sig = [sigma] + [s for s in tail if s < sigma - 0.05]
    if len(sig) < 2:
        sig.append(round(sigma * 0.5, 4))
    g = _ltx_names(_graph(a, "seam-regen.json"))
    g["src"]["inputs"].update(video=video, frame_load_cap=n, skip_first_frames=0)
    g["late"]["inputs"].update(batch_index=h, length=n - h)
    g["early"]["inputs"].update(batch_index=0, length=h)
    g["pos"]["inputs"]["text"] = prompt
    g["cond"]["inputs"]["frame_rate"] = fps
    g["latA"]["inputs"].update(frames_number=n, frame_rate=fps)
    g["mask"]["inputs"].update(start_time=round(hold_start / fps, 4), end_time=round((n - hold_end) / fps, 4), video_fps=fps)
    g["sigmas"]["inputs"]["sigmas"] = ", ".join("%.4f" % s for s in sig + [0])
    g["noise"]["inputs"]["noise_seed"] = seed
    g["backHead"]["inputs"].update(batch_index=n - h, length=h)
    g["backTail"]["inputs"].update(batch_index=0, length=n - h)
    g["out"]["inputs"]["frame_rate"] = fps
    return g, [h]


def run_seam(a, j, vals):
    src = vals["video"]["path"]
    fix = vals.get("fix") or "auto"
    _stage(j, "measuring the loop")
    before = measure(src)
    j["report"] = {"before": before, "fix": fix}
    name = vals["video"].get("name") or "loop"
    if fix == "check" or (fix == "auto" and before["verdict"] == "seamless"):
        j["report"]["note"] = "already seamless — nothing to fix" if before["verdict"] == "seamless" else "measured only"
        return []
    info = video_info(src)
    seed = int(vals.get("seed") or 0) % (2 ** 48)
    prompt = str(vals.get("prompt") or "").strip() or "A seamless looping shot, continuous natural motion, the same scene throughout."
    L = seam_load(src)
    method, out, splices = fix, None, []
    if fix in ("auto", "trim"):
        _stage(j, "searching for the best-closing window")
        plan = plan_trim(L)
        if plan:
            method = "trim"
            out = _trim(src, plan["start"], plan["frames"], info["fps"])
            j["report"]["plan"] = {"start": plan["start"], "frames": plan["frames"], "of": L["n"]}
        elif fix == "trim":
            raise RuntimeError("No trim of this loop closes cleanly (it keeps at least half the clip). Try Re-render or Bridge.")
        else:
            method = "regen" if (L["n"] % 8 == 1 and L["n"] >= 33) else "bridge"
    if out is None:
        clip, ci = _fit32(src, info, j)
        ci["frames"] = min(ci["frames"] or L["n"], L["n"])
        vname = comfy.upload(clip)
        if method == "regen":
            g, splices = seam_regen_graph(a, vname, ci, prompt, seed, float(vals.get("strength") or 0.55))
            outs = render(a, j, g, "Seam re-render across the wrap")
        else:
            method = "bridge"
            plan = plan_bridge(ci["frames"], ci["fps"])
            g = seam_bridge_graph(a, vname, ci, plan, prompt, seed)
            splices = [plan["splice"]]
            j["report"]["plan"] = plan
            outs = render(a, j, g, "Seam bridge (LTX first/last)")
        v = entries(outs, "out")
        if not v:
            raise RuntimeError("the fix saved nothing")
        out = fetch_tmp(v[0], ".mp4")
    _stage(j, "measuring the fixed loop")
    after = measure(out, splices)
    j["report"].update(method=method, after=after)
    label = "%s · seam %s → %s (%s)" % (name, before["ratio"], after["ratio"], method)
    return [lib_save(out, a, j, label, "Fixed loop", ".mp4", meta={"seam": {"before": before["ratio"], "after": after["ratio"],
                                                                           "verdict": after["verdict"], "method": method}})]


# ══ SCENE · shot list (local LLM in ComfyUI) → LTX-2.5 shots → cut (graphs/director.ts) ═════════════════════════════
FRAMINGS = {"wide": "wide establishing shot", "medium": "medium shot", "closeup": "close-up shot", "extreme": "extreme close-up",
            "ots": "over-the-shoulder shot", "low": "low-angle shot", "high": "high-angle shot", "aerial": "aerial drone shot"}
MOVES = {"static": "locked-off camera", "pushin": "slow push in", "pullback": "slow pull back", "panleft": "camera pans left",
         "panright": "camera pans right", "tracking": "tracking shot following the subject", "handheld": "handheld camera",
         "crane": "crane up", "orbit": "camera orbits the subject", "dolly": "dolly sideways"}
SIZES = {("16:9", "480p"): (768, 448), ("16:9", "720p"): (1280, 704), ("9:16", "480p"): (448, 768), ("9:16", "720p"): (704, 1280),
         ("1:1", "480p"): (576, 576), ("1:1", "720p"): (960, 960)}


def planner_system(lo, hi):
    return "\n".join([
        "You are a film director planning coverage. Split the user's scene into a shot list that tells it in order.",
        "Use %d to %d shots. Vary the framing from shot to shot." % (lo, hi),
        "Reply with JSON only, no prose and no code fences, exactly this shape:",
        '{"shots":[{"framing":"...","move":"...","action":"...","seconds":3}]}',
        "framing is one of: %s." % ", ".join(FRAMINGS),
        "move is one of: %s." % ", ".join(MOVES),
        "action is one sentence in the present tense that stands on its own: who is in frame, where they are, and what they do. "
        "Describe the character and the place the same way in every shot.",
        "seconds is a whole number from 2 to 6."])


def parse_shots(text, scene, hi):
    shots = []
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            for s in (json.loads(m.group(0)).get("shots") or [])[:hi]:
                act = str(s.get("action") or "").strip()
                if act:
                    shots.append({"framing": s.get("framing") if s.get("framing") in FRAMINGS else "medium",
                                  "move": s.get("move") if s.get("move") in MOVES else "static", "action": act[:400],
                                  "seconds": max(2, min(6, int(s.get("seconds") or 3)))})
        except (ValueError, TypeError):
            shots = []
    if not shots:                                 # the planner failed: one shot per sentence
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", scene) if len(x.strip()) > 3][:hi]
        cyc = ["wide", "medium", "closeup", "low", "ots", "high"]
        shots = [{"framing": cyc[i % len(cyc)], "move": "static" if i % 2 else "pushin", "action": s, "seconds": 3} for i, s in enumerate(sents)]
    return shots


def t2v_graph(a, prompt, w, h, frames, seed):
    g = _ltx_names(_graph(a, "video-t2v.json"))
    for k in ("upmodel",):
        if k in g:
            g[k]["inputs"]["model_name"] = _ltx_name(g[k]["inputs"]["model_name"])
    g["pos"]["inputs"]["text"] = prompt
    g["latV"]["inputs"].update(width=w // 2, height=h // 2, length=frames)
    g["latA"]["inputs"].update(frames_number=frames, frame_rate=24)
    g["cond"]["inputs"]["frame_rate"] = 24
    g["noise1"]["inputs"]["noise_seed"] = seed
    g["noise2"]["inputs"]["noise_seed"] = seed + 1
    g["vid"]["inputs"]["fps"] = 24
    return g


def run_scene(a, j, vals):
    scene = str(vals["scene"]).strip()
    hi = max(2, min(6, int(vals.get("shots") or 4)))
    lo = min(2, hi)
    seed = int(vals.get("seed") or 0) % (2 ** 31)
    year = int(vals.get("era") or 0)
    # 1 · plan the shots with Gemma 3 12B inside ComfyUI
    g = _graph(a, "director-plan.json")
    clip = next(k for k, n in g.items() if n["class_type"] == "CLIPLoader")
    g[clip]["inputs"]["clip_name"] = _ltx_name("gemma_3_12B_it_fp4_mixed.safetensors")
    g["sys"]["inputs"]["value"] = planner_system(lo, hi)
    g["gen"]["inputs"].update({"prompt": scene, "sampling_mode.seed": seed})
    _stage(j, "planning the shots")
    outs = render(a, j, g, "Scene shot list (Gemma 3 12B)")
    text = ""
    for e in entries(outs, "save"):
        try:
            with open(fetch_tmp(e, ".txt"), encoding="utf-8", errors="replace") as f:
                text = f.read()
            break
        except Exception:
            pass
    if not text:
        text = " ".join(str(x) for v in (outs.get("save") or {}).values() if isinstance(v, list) for x in v if isinstance(x, str))
    shots = parse_shots(text, scene, hi)
    j["shots"] = shots
    plan_txt = "\n".join("%d. [%s · %s · %ds] %s" % (i + 1, FRAMINGS[s["framing"]], MOVES[s["move"]], s["seconds"], s["action"]) for i, s in enumerate(shots))
    plan_file = _tmp(".txt")
    with open(plan_file, "w", encoding="utf-8") as f:
        f.write("SCENE\n" + scene + "\n\nSHOT LIST\n" + plan_txt + "\n")
    files = [lib_save(plan_file, a, j, "Shot list · " + scene, "Shot list", ".txt")]
    if vals.get("plan_only"):
        return files
    # 2 · render each shot
    w, h = SIZES.get((vals.get("aspect") or "16:9", vals.get("size") or "480p"), (768, 448))
    era = (", " + era_text(year)) if year else ""
    clips = []
    for i, s in enumerate(shots):
        _check_cancel(j)
        frames = max(9, int(round(s["seconds"] * 24 - 1) / 8) * 8 + 1)
        prompt = "%s, %s. %s%s" % (FRAMINGS[s["framing"]].capitalize(), MOVES[s["move"]], s["action"], era)
        _stage(j, "shot %d of %d" % (i + 1, len(shots)))
        outs = render(a, j, t2v_graph(a, prompt, w, h, frames, seed + 10 * i), "Scene shot %d" % (i + 1))
        v = entries(outs, "save")
        if not v:
            raise RuntimeError("shot %d saved nothing" % (i + 1))
        clips.append(fetch_tmp(v[0], ".mp4"))
    # 3 · hard cuts, in order, at one size
    _stage(j, "cutting %d shots together" % len(clips))
    out = _tmp(".mp4")
    args = [FFMPEG, "-v", "error", "-y"]
    for c in clips:
        args += ["-i", c]
    fc = "".join("[%d:v]fps=24,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v%d];" % (i, w, h, w, h, i) for i in range(len(clips)))
    fc += "".join("[v%d]" % i for i in range(len(clips))) + "concat=n=%d:v=1:a=0[out]" % len(clips)
    _run(args + ["-filter_complex", fc, "-map", "[out]", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    if year:
        out = post(a, j, out, year, "linear")
    files.insert(0, lib_save(out, a, j, scene, "Scene", ".mp4", meta={"shots": len(clips)}))
    return files


# ══ PHONE DROP BOX (server/phone.ts): QR → a one-time LAN page that takes exactly one clip ═════════════════════════
_PHONE = {}
_PHONE_LOCK = threading.Lock()
PHONE_TTL = 15 * 60
PHONE_MAX = 800 * 1024 * 1024
_VID_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))           # no packet is sent; this only picks the LAN interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def phone_open(host_url, user, kind="video"):
    tok = secrets.token_urlsafe(32)
    base = host_url.rstrip("/")
    if re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$", base):
        port = (re.search(r":(\d+)$", base) or [None, str(core.PORT)])[1]
        base = "http://%s:%s" % (_lan_ip(), port)
    url = "%s/ffdrop/%s" % (base, tok)
    with _PHONE_LOCK:
        for k in [k for k, v in _PHONE.items() if time.time() - v["t"] > PHONE_TTL]:
            _PHONE.pop(k, None)
        _PHONE[tok] = {"t": time.time(), "user": user, "kind": kind, "status": "open", "bad": 0, "file": None, "name": None}
    import qrcode
    import qrcode.image.svg
    buf = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathFillImage, border=2).save(buf)
    return {"token": tok, "url": url, "qr": buf.getvalue().decode("utf-8"), "expires_s": PHONE_TTL}


def phone_state(tok, user):
    s = _PHONE.get(tok)
    if not s or s["user"] != user:
        return None
    if s["status"] == "open" and time.time() - s["t"] > PHONE_TTL:
        s["status"] = "expired"
    return {"status": s["status"], "up": s["file"], "name": s["name"]}


PHONE_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Send a clip to Studio</title><style>
body{margin:0;background:#141413;color:#f5f4ef;font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center}
main{width:min(420px,92vw);text-align:center}h1{font-size:20px;margin:0 0 6px}p{color:#bdb9ad;margin:0 0 22px}
label,button{display:block;width:100%;box-sizing:border-box;padding:16px;border-radius:14px;border:0;font:600 17px system-ui;margin:10px 0;cursor:pointer}
label{background:#d97757;color:#141413}button{background:#30302e;color:#f5f4ef}input{display:none}
.bar{height:8px;border-radius:8px;background:#30302e;overflow:hidden;margin:18px 0 8px}.bar i{display:block;height:100%;width:0;background:#d97757;transition:width .2s}
#st{min-height:22px;color:#bdb9ad}</style></head><body><main>
<h1>Send a clip to Studio</h1><p>Film the move, or pick a clip you already have. It goes straight to the PC, once.</p>
<label>Film now<input id="cam" type="file" accept="video/*" capture="environment"></label>
<label style="background:#3a3936;color:#f5f4ef">Choose a clip<input id="pick" type="file" accept="video/*"></label>
<div class="bar"><i id="bar"></i></div><div id="st"></div></main><script>
function send(f){if(!f)return;var x=new XMLHttpRequest(),st=document.getElementById('st'),bar=document.getElementById('bar');
x.open('POST',location.pathname.replace(/\\/$/,'')+'/upload');x.setRequestHeader('X-Filename',encodeURIComponent(f.name||'clip.mp4'));
x.upload.onprogress=function(e){if(e.lengthComputable){bar.style.width=(e.loaded*100/e.total)+'%';st.textContent='Sending '+Math.round(e.loaded*100/e.total)+'%';}};
x.onload=function(){st.textContent=x.status==200?'Done. It is in Studio now; you can close this page.':('Not sent: '+x.responseText);};
x.onerror=function(){st.textContent='The PC did not answer. Same Wi-Fi?';};x.send(f);}
document.getElementById('cam').onchange=function(e){send(e.target.files[0]);};document.getElementById('pick').onchange=function(e){send(e.target.files[0]);};
</script></body></html>"""


def phone_page(tok):
    s = _PHONE.get(tok)
    if not s or s["status"] != "open" or time.time() - s["t"] > PHONE_TTL:
        return None
    return PHONE_HTML


def phone_upload(tok, stream, filename, length):
    s = _PHONE.get(tok)
    if not s or s["status"] != "open" or time.time() - s["t"] > PHONE_TTL:
        return "this link has been used or has expired; make a new QR code on the PC", 410
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in _VID_EXT:
        ext = ".mp4"
    if length and length > PHONE_MAX:
        return "the clip is over %d MB" % (PHONE_MAX // 1024 // 1024), 413
    s["status"] = "receiving"
    p = os.path.join(_ff().INBOX, "%s_phone_%s%s" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6], ext))
    got = 0
    try:
        with open(p, "wb") as f:
            while True:
                chunk = stream.read(1 << 20)
                if not chunk:
                    break
                got += len(chunk)
                if got > PHONE_MAX:
                    raise ValueError("too big")
                f.write(chunk)
        video_info(p)                               # it must really be a video
    except Exception as e:
        try:
            os.remove(p)
        except OSError:
            pass
        s["bad"] += 1
        s["status"] = "open" if s["bad"] < 3 else "closed"
        return "that file is not a video the PC can read (%s)" % str(e)[:80], 400
    s.update(status="done", file=os.path.basename(p), name=filename or "phone clip")
    return "ok", 200


# ══ STAGE EDITOR: blocking frames from the browser → the clay clip ═════════════════════════════════════════════════
_DATA_URL = re.compile(r"^data:image/(png|jpeg);base64,([A-Za-z0-9+/=\s]+)$")


def ingest_blocking(b):
    frames = b.get("clay") or []
    w, h = int(b.get("width") or 0), int(b.get("height") or 0)
    if not (64 <= w <= 1280 and 64 <= h <= 1280) or w % 64 or h % 64:
        raise _ff().InputError("the clay size must be on a 64-pixel grid, at most 1280")
    if not (9 <= len(frames) <= 241):
        raise _ff().InputError("the clay needs 9 to 241 frames")
    out = os.path.join(_ff().INBOX, "%s_stageclay_%s.mp4" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6]))
    enc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(STAGE_FPS), "-i", "-", "-vf", "scale=%d:%d" % (w, h),
                            "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WIN)
    try:
        for fr in frames:
            m = _DATA_URL.match(fr if isinstance(fr, str) else "")
            if not m:
                raise _ff().InputError("every clay frame must be a PNG or JPEG data URL")
            enc.stdin.write(base64.b64decode(m.group(2)))
    finally:
        enc.stdin.close()
        enc.wait(300)
    if enc.returncode != 0:
        raise RuntimeError("ffmpeg could not encode the clay: %s" % (enc.stderr.read() or b"").decode("utf-8", "replace")[-200:])
    scene = b.get("scene")
    if isinstance(scene, dict):
        core.save_json(out + ".scene.json", scene)
    return {"up": os.path.basename(out), "name": "Stage blocking · %d frames" % len(frames)}


# ── routes ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    from flask import Response, abort, jsonify, request, send_file
    ff = _ff()

    @app.route("/studio-stage")
    def ff_stage_page():
        return hk["static"]("stage.html")

    @app.route("/api/ff/stage/blocking", methods=["POST"])
    def ff_stage_blocking():
        try:
            return jsonify(ingest_blocking(request.get_json(silent=True) or {}))
        except ff.InputError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)[:300]}), 500

    @app.route("/api/ff/stage/scene/<name>")
    def ff_stage_scene(name):
        p = core.in_dir(ff.INBOX, name + ".scene.json") if re.match(r"^[\w.-]+$", name) else None
        if not p:
            abort(404)
        return jsonify(core.load_json(p, {}))

    @app.route("/api/ff/inbox/<name>")
    def ff_inbox(name):
        """An uploaded / phone / Stage input, for the form's preview."""
        p = core.in_dir(ff.INBOX, name)
        if not p or not core.kind_of(name):
            abort(404)
        return send_file(p, conditional=True)

    @app.route("/api/ff/models3d")
    def ff_models3d():
        return jsonify({"models": models3d(None if hk["is_owner"]() else hk["uid"]())})

    @app.route("/api/ff/model3d/<name>")
    def ff_model3d(name):
        if not re.match(r"^[\w.-]+\.glb$", name):
            abort(404)
        p = core.in_dir(ff.MODELS3D, name)
        if not p:
            abort(404)
        m = core.load_json(p + ".json", {})
        if not (hk["is_owner"]() or (m.get("user") or "owner") == hk["uid"]()):
            abort(404)
        return send_file(p, mimetype="model/gltf-binary", as_attachment=bool(request.args.get("dl")), download_name=name, conditional=True)

    @app.route("/api/ff/phone", methods=["POST"])
    def ff_phone():
        return jsonify(phone_open(request.host_url, hk["uid"]()))

    @app.route("/api/ff/phone/<tok>")
    def ff_phone_state(tok):
        s = phone_state(tok, hk["uid"]())
        if not s:
            abort(404)
        return jsonify(s)

    @app.route("/ffdrop/<tok>")
    def ff_drop_page(tok):
        h = phone_page(tok)
        if not h:
            return Response("<p style='font:16px system-ui;padding:24px'>This link has been used or has expired. Make a new QR code on the PC.</p>",
                            status=410, mimetype="text/html")
        return Response(h, mimetype="text/html", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.route("/ffdrop/<tok>/upload", methods=["POST"])
    def ff_drop_upload(tok):
        from urllib.parse import unquote
        msg, code = phone_upload(tok, request.stream, unquote(request.headers.get("X-Filename") or ""), request.content_length or 0)
        return Response(msg, status=code, mimetype="text/plain")
