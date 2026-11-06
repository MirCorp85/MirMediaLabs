r"""MIR MOTION GRAPHICS — per-style AI art library builder.

Every motion style (styles.json) has its own art direction. For each concept in concepts.json this asks the Media Lab
(the lab's ComfyUI, Qwen-Image 2.1, local GPU) for the concept drawn in that style on a flat white background, then cuts it out
(BiRefNet via rembg, in the optional art venv: mml_config "mg_art_python") and trims it to a square transparent PNG + a small webp thumb:

  public/mg/art/<style>/<concept>.png   (≤1024 px, RGBA)
  public/mg/art/<style>/<concept>.webp  (256 px thumb for the wizard's library browser)
  public/mg/art/manifest.json           {style: {concept: {tags, w, h, made}}}

Resumable and idempotent (existing files are skipped). Usage (run with the mg-assets venv python, -I):
  python -I build_art.py [--style signature] [--only sun,earth] [--limit 4] [--concept "a tiny submarine" --tags sub,ocean]
The wizard calls `ensure(style, concept, tags)` through the same code path to grow a library on demand.
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "public", "mg", "art")
LIB = os.environ.get("MIR_LIB") or os.path.join(os.path.dirname(ROOT), "data", "library")
API = os.environ.get("MIR_LAB_API") or "http://127.0.0.1:5400"
STYLES = json.load(open(os.path.join(HERE, "styles.json"), encoding="utf-8"))
CONCEPTS = json.load(open(os.path.join(HERE, "concepts.json"), encoding="utf-8"))
_REM = {}
DIRECT = "--lab" not in sys.argv            # default: straight to ComfyUI (warm model); --lab = through the Media Lab queue



def _mp(bd, path, field):
    """multipart/form-data body with one file."""
    import uuid
    nl = bytes([13, 10])
    head = ('--%s' % bd).encode() + nl + ('Content-Disposition: form-data; name="%s"; filename="%s_%s"' % (field, uuid.uuid4().hex[:8], os.path.basename(path))).encode()         + nl + b"Content-Type: image/png" + nl + nl
    return head + open(path, "rb").read() + nl + ('--%s--' % bd).encode() + nl

def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


COMFY = "http://127.0.0.1:8188"
QIMG = {"dit": "qwen_image_2.1_int8_convrot.safetensors", "te": "qwen3vl_8b_int8_convrot.safetensors", "vae": "qwen_image_2.1_vae_bf16.safetensors"}
STEPS = 25


VOICE_LOCK = os.environ.get("MIR_VOICE_LOCK") or os.path.join(os.path.dirname(ROOT), "data", "gpu_voice.lock")


def _lab_busy():
    try:                                    # Motion Studio's expressive narrator is on the GPU (stale locks expire after 20 min)
        if os.path.isfile(VOICE_LOCK) and time.time() - os.path.getmtime(VOICE_LOCK) < 1200:
            return True
    except OSError:
        pass
    try:
        return any(j.get("status") == "running" for j in call("/api/jobs")[:20])
    except Exception:
        return False


def comfy_upload(path):
    """Put a local picture into ComfyUI's input folder → its name (for LoadImage)."""
    import uuid
    b = uuid.uuid4().hex
    body = _mp(b, path, "image")
    req = urllib.request.Request(COMFY + "/upload/image", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["name"]


def generate_direct(prompt, seed, w=1024, h=1024, refs=None, _try=0):
    try:
        return _generate_direct(prompt, seed, w, h, refs)
    except RuntimeError as e:                    # host RAM squeeze ("hostbuf_file_reader_read failed") → free ComfyUI + retry
        if _try >= 2 or not ("comfy error" in str(e) or "timed out" in str(e)):
            raise
        try:
            urllib.request.urlopen(urllib.request.Request(COMFY + "/interrupt", data=b"", method="POST"), timeout=15)
        except Exception:
            pass
        try:
            urllib.request.urlopen(urllib.request.Request(COMFY + "/free", data=b'{"unload_models": true, "free_memory": true}',
                                                          headers={"Content-Type": "application/json"}), timeout=30)
        except Exception:
            pass
        time.sleep(20)
        return generate_direct(prompt, seed, w, h, refs, _try + 1)


def _generate_direct(prompt, seed, w=1024, h=1024, refs=None):
    """Batch path: the same Qwen-Image 2.1 graph the Media Lab builds (renderers.qimg_render), sent straight to ComfyUI so
    the model stays loaded between images (the lab frees VRAM after every job → ~5 min/image; warm ≈ 1 min). Waits while
    a Media Lab job is running so it never fights the person's own renders for the GPU."""
    while _lab_busy():
        time.sleep(15)
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": QIMG["dit"], "weight_dtype": "default"}},
         "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
         "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": QIMG["te"], "type": "qwen_image", "device": "default"}},
         "4": {"class_type": "VAELoader", "inputs": {"vae_name": QIMG["vae"]}},
         "5": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["3", 0], "prompt": prompt, "negative_prompt": "", "resolution": 1024}},
         "6": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
         "7": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["6", 0],
                                                    "seed": seed, "steps": STEPS, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
         "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
         "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "mg_art/art"}}}
    if refs:                                    # Qwen EDIT: reference pictures feed the encoder, the latent comes from ref 1's size
        g["5"]["inputs"]["vae"] = ["4", 0]
        for i, r in enumerate(refs[:3]):
            g[str(20 + i)] = {"class_type": "LoadImage", "inputs": {"image": comfy_upload(r)}}
            g["5"]["inputs"]["images.image_%d" % (i + 1)] = [str(20 + i), 0]
        g["7"]["inputs"]["latent_image"] = ["5", 2]
        del g["6"]
    req = urllib.request.Request(COMFY + "/prompt", data=json.dumps({"prompt": g}).encode(), headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req, timeout=60).read())["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(2)
        h = json.loads(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30).read()).get(pid)
        if not h:
            continue
        if (h.get("status") or {}).get("status_str") == "error":
            raise RuntimeError("comfy error: %s" % str(h.get("status"))[:300])
        imgs = ((h.get("outputs") or {}).get("9") or {}).get("images") or []
        if imgs:
            im = imgs[0]
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
            path = os.path.join(os.path.dirname(OUT), "_raw", os.path.basename(im["filename"]))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(urllib.request.urlopen(COMFY + "/view?" + q, timeout=60).read())
            return path
    raise RuntimeError("comfy timed out")


def generate(prompt, seed):
    if DIRECT:
        return generate_direct(prompt, seed)
    body = {"model": "qimg", "prompt": prompt + " 1:1 --seed %d" % seed, "literal": True, "internal": True, "fresh": True}
    while True:
        try:
            j = call("/api/generate", body)
            break
        except urllib.error.HTTPError as e:
            if e.code == 409:            # the GPU queue is busy — wait our turn
                time.sleep(10)
                continue
            raise RuntimeError("generate: %s" % e.read()[:300])
    jid = j["id"]
    while True:
        time.sleep(3)
        j = call("/api/jobs/" + jid)
        if j["status"] in ("done", "error", "cancelled"):
            break
    if j["status"] != "done" or not j.get("files"):
        raise RuntimeError("qimg %s: %s" % (j["status"], str(j.get("log", ""))[-300:]))
    return os.path.join(LIB, os.path.basename(j["files"][0]))


def cutout(src, dst, thumb):
    from PIL import Image
    from rembg import new_session, remove
    if "s" not in _REM:
        _REM["s"] = new_session("birefnet-general")
    im = Image.open(src).convert("RGB")
    rgba = remove(im, session=_REM["s"], post_process_mask=True)
    bb = rgba.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    if not bb:
        raise RuntimeError("cutout found no subject")
    rgba = rgba.crop(bb)
    w, h = rgba.size
    side = int(max(w, h) * 1.06)                                  # square canvas, a little air around the subject
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(rgba, ((side - w) // 2, (side - h) // 2))
    if side > 1024:
        sq = sq.resize((1024, 1024), Image.LANCZOS)
    sq.save(dst, optimize=True)
    sq.resize((256, 256), Image.LANCZOS).save(thumb, "WEBP", quality=82)
    return sq.size


def manifest():
    p = os.path.join(OUT, "manifest.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def save_manifest(m):
    p = os.path.join(OUT, "manifest.json")
    tmp = p + ".tmp"
    json.dump(m, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, p)


def ensure(style, cid, subject=None, tags=None, force=False):
    """Make one concept in one style (no-op if it exists) → manifest entry."""
    st = STYLES[style]
    c = CONCEPTS.get(cid) or {"subject": subject or cid.replace("_", " "), "tags": tags or [cid]}
    d = os.path.join(OUT, style)
    os.makedirs(d, exist_ok=True)
    png, thumb = os.path.join(d, cid + ".png"), os.path.join(d, cid + ".webp")
    m = manifest()
    if os.path.isfile(png) and not force:
        return m.get(style, {}).get(cid)
    prompt = st["art"].replace("{s}", c["subject"])
    seed = 1000 + sum(map(ord, style + cid)) % 9000
    t0 = time.time()
    raw = generate(prompt, seed)
    w, h = cutout(raw, png, thumb)
    m = manifest()                                                # re-read: another builder may have added entries meanwhile
    m.setdefault(style, {})[cid] = {"tags": c["tags"], "subject": c["subject"], "w": w, "h": h, "made": int(time.time())}
    save_manifest(m)
    print("%-10s %-14s %4.0fs" % (style, cid, time.time() - t0), flush=True)
    return m[style][cid]


def main():
    a = sys.argv[1:]
    arg = lambda k: a[a.index(k) + 1] if k in a else None
    styles = [arg("--style")] if arg("--style") else list(STYLES)
    if arg("--concept"):
        cid = "".join(ch if ch.isalnum() else "_" for ch in arg("--concept").lower()).strip("_")[:40]
        for s in styles:
            ensure(s, cid, arg("--concept"), (arg("--tags") or cid).split(","))
        return
    only = set((arg("--only") or "").split(",")) - {""}
    ids = [c for c in CONCEPTS if not only or c in only][: int(arg("--limit") or 9999)]
    # one batch at a time: Oct 28 2026 eight orphaned copies queued Qwen jobs in parallel until ComfyUI died
    lock = os.path.join(HERE, "build_art.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        old = open(lock).read().strip()
        alive = bool(old) and subprocess.run(["tasklist", "/FI", "PID eq %s" % old], capture_output=True, text=True).stdout.count(old) > 0
        if alive:
            print("another batch is running (pid %s) — not starting a second one" % old, flush=True)
            return
        open(lock, "w").write(str(os.getpid()))
    try:
        # concept-major order: every style gets the most useful concepts first, so a half-built library is still usable
        for cid in ids:
            for s in styles:
                for attempt in range(3):
                    try:
                        ensure(s, cid)
                        break
                    except Exception as e:
                        down = "10061" in str(e) or "refused" in str(e).lower()
                        if down:                     # ComfyUI went away: wait for it instead of failing every concept
                            print("ComfyUI is down — waiting for it (%s/%s)" % (s, cid), flush=True)
                            t0 = time.time()
                            while time.time() - t0 < 1800:
                                time.sleep(15)
                                try:
                                    urllib.request.urlopen(COMFY + "/system_stats", timeout=3)
                                    break
                                except Exception:
                                    pass
                            continue
                        print("FAILED %s/%s: %s" % (s, cid, str(e)[:200]), flush=True)
                        break
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


if __name__ == "__main__":
    main()
