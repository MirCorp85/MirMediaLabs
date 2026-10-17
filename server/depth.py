"""Depth control video for H3 motion control (Node Flow "depth" option + Pose Preview).

ComfyUI has no depth preprocessor (only SDPose + Canny), so depth is made locally with Depth Anything V2 Small
(HF depth-anything/Depth-Anything-V2-Small-hf, ~100 MB, cached in data/models). Frames are normalised with ONE range for
the whole clip (no per-frame flicker), near = white, written as a grey mp4 at the source fps. H3 then follows it with
control = as_is. Depth beats pose on fast / overlapping action (no skeleton to break or swap).

Runs in this process when torch + transformers are importable (source installs); otherwise (the compiled PC edition)
the same worker code runs in the engine's own Python (the ComfyUI venv already has torch + transformers)."""
import json
import os
import subprocess
import sys

try:
    from . import core
except ImportError:
    import core

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
CACHE = os.path.join(core.DATA, "models", "hf")

# Self-contained worker: argv = ffmpeg src dst max_side cache model_id. Prints one JSON line.
WORKER = r'''
import json, re, subprocess, sys
import numpy as np
import torch
from transformers import AutoModelForDepthEstimation
ff, src, dst, max_side, cache, mid = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]
NW = 0x08000000 if sys.platform == "win32" else 0
r = subprocess.run([ff, "-hide_banner", "-i", src], capture_output=True, text=True, timeout=30, creationflags=NW)
m = re.search(r", (\d{2,5})x(\d{2,5})", r.stderr)
w, h = (int(m.group(1)), int(m.group(2))) if m else (832, 480)
m = re.search(r"(\d+(?:\.\d+)?) fps", r.stderr)
fps = float(m.group(1)) if m else 24.0
k = min(1.0, max_side / float(max(w, h)))
w, h = int(w * k) // 2 * 2, int(h * k) // 2 * 2
dec = subprocess.run([ff, "-v", "error", "-i", src, "-vf", "scale=%d:%d" % (w, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     capture_output=True, timeout=900, creationflags=NW)
raw = np.frombuffer(dec.stdout, np.uint8)
n = raw.size // (w * h * 3)
if not n:
    print(json.dumps({"error": "couldn't read frames from the clip"})); sys.exit(0)
frames = raw[:n * w * h * 3].reshape(n, h, w, 3)
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl = AutoModelForDepthEstimation.from_pretrained(mid, cache_dir=cache).to(dev).eval()
if dev == "cuda":
    mdl = mdl.half()
sc = 518.0 / min(w, h)                                   # DA-V2 input: short side 518, both sides multiples of 14
ih, iw = int(round(h * sc / 14)) * 14, int(round(w * sc / 14)) * 14
mean = torch.tensor([0.485, 0.456, 0.406], device=dev).view(1, 3, 1, 1)
std = torch.tensor([0.229, 0.224, 0.225], device=dev).view(1, 3, 1, 1)
out = []
with torch.inference_mode():
    for i in range(0, n, 8):
        x = torch.from_numpy(frames[i:i + 8].copy()).to(dev).permute(0, 3, 1, 2).float() / 255.0
        x = torch.nn.functional.interpolate(x, size=(ih, iw), mode="bicubic", align_corners=False)
        x = (x - mean) / std
        d = mdl(pixel_values=x.half() if dev == "cuda" else x).predicted_depth.float()
        d = torch.nn.functional.interpolate(d.unsqueeze(1), size=(h, w), mode="bicubic", align_corners=False)[:, 0]
        out.append(d.cpu().numpy())
dep = np.concatenate(out)
lo, hi = np.percentile(dep, 1), np.percentile(dep, 99)
g = (np.clip((dep - lo) / max(1e-6, hi - lo), 0, 1) * 255).astype(np.uint8)
enc = subprocess.run([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "%dx%d" % (w, h), "-r", "%g" % fps,
                      "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst],
                     input=g.tobytes(), capture_output=True, timeout=900, creationflags=NW)
print(json.dumps({"error": enc.stderr.decode("utf-8", "replace")[-300:]} if enc.returncode else {"ok": True, "frames": int(n)}))
'''


def _python():
    """This interpreter if it can run the model, else the engine's (ComfyUI venv) Python."""
    if not getattr(sys, "frozen", False) and "__compiled__" not in globals():
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            return sys.executable.replace("pythonw.exe", "python.exe")
        except Exception:
            pass
    try:
        from . import comfy
    except ImportError:
        import comfy
    if comfy.COMFY_PY and os.path.isfile(comfy.COMFY_PY):
        return comfy.COMFY_PY
    raise RuntimeError("depth needs the engine's Python (torch + transformers) — run Setup → Repair")


def depth_video(src, dst, max_side=640, stop=None):
    """src clip → dst grey depth mp4 (same length + fps). stop() → True aborts."""
    os.makedirs(CACHE, exist_ok=True)
    logf = os.path.join(CACHE, "depth_worker.log")      # stderr to a file: download bars must never fill a pipe
    with open(logf, "w", encoding="utf-8") as lf:
        p = subprocess.Popen([_python(), "-c", WORKER, core.FFMPEG, src, dst, str(int(max_side)), CACHE, MODEL_ID],
                             stdout=subprocess.PIPE, stderr=lf, text=True, creationflags=core.NO_WINDOW,
                             env=dict(os.environ, HF_HUB_DISABLE_TELEMETRY="1", PYTHONIOENCODING="utf-8"))
        while p.poll() is None:
            try:
                p.wait(1)
            except subprocess.TimeoutExpired:
                if stop and stop():
                    p.kill()
                    raise RuntimeError("stopped")
        out = p.stdout.read()
    try:
        res = json.loads((out or "").strip().splitlines()[-1])
    except Exception:
        res = {"error": (core.read_text(logf) or "depth worker failed")[-300:]}
    if res.get("error") or not os.path.isfile(dst):
        raise RuntimeError("depth: %s" % (res.get("error") or "no output"))
    return dst
