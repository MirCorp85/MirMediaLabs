"""MIR MEDIA LABS — paths, storage, isolation guard, access key, prompt engine.

Isolation contract (checked by /api/isolation):
  * every file this app reads or writes lives under ROOT (the install folder)
    — its own library, references, job history, settings and update folder;
  * it never imports MirOS / AiMir code and never calls the MirOS dashboard (:5000);
  * the only shared things are machine resources: the GPU through the local ComfyUI
    engine and the local Ollama engine (used only to rewrite prompts, with no context).
"""
import json
import os
import re
import secrets
import threading
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server")
STATIC = os.path.join(SERVER, "static")
DATA = os.path.join(ROOT, "data")
LIB = os.path.join(DATA, "library")
REFS = os.path.join(DATA, "refs")
TRASH = os.path.join(DATA, "trash")
LOGS = os.path.join(DATA, "logs")
THUMBS = os.path.join(DATA, "thumbs")
UPDATES = os.path.join(ROOT, "updates")
PREFS_FILE = os.path.join(DATA, "prefs.json")
JOBS_FILE = os.path.join(DATA, "jobs.json")
INDEX_FILE = os.path.join(LIB, "index.json")
KEY_FILE = os.path.join(DATA, "access_key.txt")

APP_NAME = "MIR MEDIA LABS"
CREATOR = {"name": "MirCorp", "email": "mirmedialabs@gmail.com", "license": "GPL-3.0-or-later",
           "copyright": "\u00a9 2026 MirCorp", "github": "https://github.com/MirCorp85/MirMediaLabs",
           "patreon": "https://www.patreon.com/cw/MirCorp"}
APP_VERSION = "1.0"
PORT = 5400

for _d in (DATA, LIB, REFS, TRASH, LOGS, THUMBS, UPDATES):
    os.makedirs(_d, exist_ok=True)

# Owner-only machine settings that never ship: data/local.json (gitignored), e.g.
#   {"forbidden_paths": ["D:/private"], "ffmpeg": "C:/tools/ffmpeg.exe"}
LOCAL = {}
try:
    with open(os.path.join(DATA, "local.json"), encoding="utf-8") as _f:
        LOCAL = json.load(_f)
except (OSError, ValueError):
    pass

# Extra places this app must never touch (the ALLOWED list below already confines it).
FORBIDDEN = [os.path.normcase(os.path.abspath(p)) for p in LOCAL.get("forbidden_paths", []) if p]
ALLOWED = [os.path.normcase(os.path.abspath(p)) for p in (DATA, UPDATES, STATIC)]

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
VID_EXT = (".mp4", ".mov", ".webm", ".m4v", ".mkv")
AUD_EXT = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac")
TXT_EXT = (".txt", ".md", ".lrc", ".srt", ".json", ".csv")
from platform_util import IS_WIN, NO_WINDOW  # noqa: E402  (0 on Linux)

# Installed copies (MirMediaLabs-Setup.exe) write mml_config.json at ROOT with their own engine and
# ffmpeg paths; the dev copy on the build PC has no config and keeps the paths it always used.
CONFIG = {}
try:
    with open(os.path.join(ROOT, "mml_config.json"), encoding="utf-8") as _f:
        CONFIG = json.load(_f)
except (OSError, ValueError):
    pass

# Optional model-file swaps, e.g. a GPU without NVFP4 support (AMD / pre-Blackwell) can point a model slot at a
# portable fp8/bf16 file with the same architecture: {"model_overrides": {"<shipped file>": "<replacement file>"}}
MODEL_OVERRIDES = {k: v for k, v in (CONFIG.get("model_overrides") or {}).items() if k and v}


def apply_model_overrides(table):
    """Swap overridden file names inside a renderer's model table (str / list / '|'-alternatives), in place."""
    def one(v):
        if isinstance(v, str):
            return "|".join(MODEL_OVERRIDES.get(x, x) for x in v.split("|"))
        if isinstance(v, list):
            return [one(x) for x in v]
        return v
    items = table.items() if isinstance(table, dict) else enumerate(table)
    for k, v in list(items):
        table[k] = one(v)
    return table


# Compiled PC builds (installer\build.ps1) add two generated modules: _buildinfo (version + signed
# update channel) and _assets (web UI embedded in the binary, so no readable files ship).
try:
    import _buildinfo
    BUILD = dict(_buildinfo.INFO)
except ImportError:
    BUILD = {}
try:
    import _assets
    ASSETS = _assets.FILES
except ImportError:
    ASSETS = None
APP_VERSION = BUILD.get("version", APP_VERSION)
PORT = int(CONFIG.get("port") or PORT)
_ASSET_CACHE = {}


def asset(fn):
    """Embedded static file → bytes (None when not embedded / unknown)."""
    if ASSETS is None:
        return None
    fn = fn.replace("\\", "/").lstrip("/")
    if fn not in _ASSET_CACHE and fn in ASSETS:
        import zlib
        _ASSET_CACHE[fn] = zlib.decompress(ASSETS[fn])
    return _ASSET_CACHE.get(fn)


def _find_ffmpeg():
    for c in (CONFIG.get("ffmpeg"), LOCAL.get("ffmpeg"), os.environ.get("MML_FFMPEG")):
        if c and os.path.isfile(c):
            return c
    try:
        import imageio_ffmpeg          # installed copies ship ffmpeg through this wheel
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


FFMPEG = _find_ffmpeg()


# ── media geometry without Pillow (the compiled PC edition ships no PIL — ffmpeg + a tiny EXIF reader) ──
def exif_orientation(path):
    """JPEG EXIF orientation (1-8; 1 = upright). Phones store portrait shots sideways + this tag."""
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"\xff\xd8":
                return 1
            while True:
                m = f.read(4)
                if len(m) < 4 or m[0] != 0xFF:
                    return 1
                size = int.from_bytes(m[2:4], "big")
                if m[1] == 0xE1:
                    d = f.read(size - 2)
                    if d[:6] != b"Exif\x00\x00":
                        return 1
                    t = d[6:]
                    bo = "little" if t[:2] == b"II" else "big"
                    ifd = int.from_bytes(t[4:8], bo)
                    for i in range(int.from_bytes(t[ifd:ifd + 2], bo)):
                        e = t[ifd + 2 + 12 * i: ifd + 14 + 12 * i]
                        if int.from_bytes(e[0:2], bo) == 0x0112:
                            v = int.from_bytes(e[8:10], bo)
                            return v if 1 <= v <= 8 else 1
                    return 1
                if m[1] in (0xDA, 0xD9):          # image data started: no EXIF block
                    return 1
                f.seek(size - 2, 1)
    except Exception:
        return 1


# EXIF orientation → ffmpeg filter that makes the pixels upright
_EXIF_VF = {2: "hflip", 3: "hflip,vflip", 4: "vflip", 5: "transpose=0", 6: "transpose=1", 7: "transpose=3", 8: "transpose=2"}


def media_size(path):
    """Upright (width, height) of a picture or clip — EXIF + video rotation applied. None if unreadable."""
    import subprocess
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                           timeout=30, creationflags=NO_WINDOW)
        m = re.search(r"Stream #\S+.*?Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
        if not m:
            return None
        w, h = int(m.group(1)), int(m.group(2))
        rot = re.search(r"(?:rotate\s*:\s*|rotation of\s*)(-?\d+(?:\.\d+)?)", r.stderr)
        turned = rot and abs(round(float(rot.group(1)))) % 180 == 90
        if kind_of(path) == "image":
            turned = exif_orientation(path) in (5, 6, 7, 8)
        return (h, w) if turned else (w, h)
    except Exception:
        return None


def still(src, dst, max_side=None, at=None):
    """Upright JPEG/PNG still of a picture (EXIF applied) or a frame of a clip, optionally downsized."""
    import subprocess
    vf = []
    pre = []
    if kind_of(src) == "image":
        pre = ["-noautorotate"]              # orientation is applied explicitly from EXIF, never twice
        if _EXIF_VF.get(exif_orientation(src)):
            vf.append(_EXIF_VF[exif_orientation(src)])
    elif at is not None:
        pre = ["-ss", "%.2f" % at]
    if max_side:
        vf.append("scale='min(%d,iw)':'min(%d,ih)':force_original_aspect_ratio=decrease" % (max_side, max_side))
    args = [FFMPEG, "-y", "-v", "error"] + pre + ["-i", src, "-frames:v", "1"] + (["-vf", ",".join(vf)] if vf else [])
    if dst.lower().endswith(".jpg"):
        args += ["-q:v", "3"]
    r = subprocess.run(args + [dst], capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError("ffmpeg: %s" % (r.stderr or "")[-300:])
    return dst


def kind_of(name):
    n = name.lower()
    if n.endswith(IMG_EXT):
        return "image"
    if n.endswith(VID_EXT):
        return "video"
    if n.endswith(AUD_EXT):
        return "audio"
    if n.endswith(TXT_EXT):
        return "text"
    return None


def safe_path(path):
    """Resolve and enforce the sandbox: inside our own folders, never inside MirOS."""
    p = os.path.normcase(os.path.abspath(path))
    if any(p == f or p.startswith(f + os.sep) for f in FORBIDDEN):
        raise PermissionError("blocked: outside MIR MEDIA LABS sandbox")
    if not any(p == a or p.startswith(a + os.sep) for a in ALLOWED):
        raise PermissionError("blocked: outside MIR MEDIA LABS sandbox")
    return os.path.abspath(path)


def in_dir(folder, name):
    """A client-supplied file name → path inside `folder` (no traversal), or None."""
    name = os.path.basename(str(name or ""))
    if not name or name.startswith("."):
        return None
    p = os.path.join(folder, name)
    return safe_path(p) if os.path.isfile(p) else None


# ── small JSON stores ──────────────────────────────────────────────────────
_IO_LOCK = threading.Lock()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    safe_path(path)
    with _IO_LOCK:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
        os.replace(tmp, path)


def access_key():
    """Media Lab's own access key — unrelated to the MirOS PIN or dashboard key."""
    try:
        k = open(KEY_FILE, encoding="utf-8").read().strip()
        if k:
            return k
    except OSError:
        pass
    k = "mml-" + secrets.token_urlsafe(18)
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(k)
    return k


def prefs():
    return load_json(PREFS_FILE, {})


def save_pref(key, value):
    p = prefs()
    p[key] = value
    p["_updated"] = time.time()
    save_json(PREFS_FILE, p)
    return p


# ── library index (output file → model / prompt / job) ─────────────────────
def index():
    return load_json(INDEX_FILE, {})


def index_add(name, meta):
    ix = index()
    ix[name] = meta
    save_json(INDEX_FILE, ix)


def new_name(prefix, ext):
    name = "%s_%s%s" % (prefix, time.strftime("%Y%m%d_%H%M%S"), ext)
    if os.path.exists(os.path.join(LIB, name)):
        name = "%s_%d%s" % (prefix, int(time.time() * 1000), ext)
    return name


# ── prompt engine (local Ollama) — rewrites prompts only, never sees anything else ──
OLLAMA = "http://127.0.0.1:11434"
DEFAULT_ENGINE = "gemma4:12b"  # MUSE: chat, prompt building + Auto-mode model picker (never renders); falls back to any installed gemma4 / first model
LEGACY_ENGINES = ("llama3.1:8b", "qwen3.5:9b")   # older installs pinned these → moved to DEFAULT_ENGINE


_OLLAMA_LOCK = threading.Lock()
_OLLAMA_TRY = {"t": 0}


def ollama_up(timeout=2):
    try:
        return requests.get(OLLAMA + "/api/version", timeout=timeout).ok
    except Exception:
        return False


def _ollama_cmd():
    """Ollama's desktop app when installed (it keeps the user's own settings), else `ollama serve`."""
    import shutil
    la = os.environ.get("LOCALAPPDATA", "")
    app = os.path.join(la, "Programs", "Ollama", "ollama app.exe")
    if os.name == "nt" and os.path.isfile(app):
        return [app]
    for c in (CONFIG.get("ollama"), LOCAL.get("ollama"), shutil.which("ollama"),
              os.path.join(la, "Programs", "Ollama", "ollama.exe"), "/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"):
        if c and os.path.isfile(c):
            return [c, "serve"]
    return None


def ensure_ollama(wait=60):
    """Start Ollama when it isn't running. wait=0 → launch and return (status loop); otherwise block
    until it answers or `wait` seconds pass. Launch attempts are spaced 30 s apart."""
    if ollama_up():
        return True
    with _OLLAMA_LOCK:
        if ollama_up():
            return True
        cmd = _ollama_cmd()
        if cmd and time.time() - _OLLAMA_TRY["t"] > 30:
            _OLLAMA_TRY["t"] = time.time()
            import subprocess
            import platform_util as pu
            try:
                subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, **pu.detached_kwargs())
                print("Ollama was not running - started it: %s" % cmd[0])
            except OSError as e:
                print("could not start Ollama: %s" % e)
    end = time.time() + wait
    while time.time() < end:
        if ollama_up():
            return True
        time.sleep(1)
    return False


def engine_model():
    want = prefs().get("engine_model") or DEFAULT_ENGINE
    if want in LEGACY_ENGINES:
        want = DEFAULT_ENGINE
    try:
        tags = [m["name"] for m in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return want
    if want in tags or not tags:
        return want
    pick = next((t for t in tags if t.startswith(DEFAULT_ENGINE.split(":")[0])), None) or tags[0]
    return pick


_CAPS = {}


def engine_sees(model=None):
    """True when the prompt engine can look at pictures (Ollama 'vision' capability). MUSE (Gemma 4 12B) sees
    pictures; a text-only engine: pictures are then left out of engine requests instead of failing them."""
    if model is None and _cloud_brain():
        import cloud
        return cloud.sees(_cloud_brain())            # Claude / GPT read pictures; GLM 5.2 is text-only
    m = model or engine_model()
    if m not in _CAPS:
        try:
            r = requests.post(OLLAMA + "/api/show", json={"model": m}, timeout=5)
            _CAPS[m] = "vision" in (r.json().get("capabilities") or [])
        except Exception:
            return False
    return _CAPS[m]


def _note(msg):
    try:                                             # never let a console encoding issue break a render
        print(msg)
    except Exception:
        pass


def _cloud_brain():
    try:
        import cloud
        return cloud.active()
    except Exception:
        return None


def ask(prompt, system, timeout=120, images=None, want_json=False, role="prompt"):
    b = _cloud_brain()                               # the owner's cloud brain for this job (else local)
    if b:
        import cloud
        try:
            return cloud.ask(b, prompt, system, images=images, want_json=want_json, role=role,
                             timeout=max(timeout, 180))
        except cloud.CloudError as e:
            _note("[cloud] %s — using the local engine for this step" % e)
    ensure_ollama()
    model = engine_model()
    body = {"model": model, "prompt": prompt, "system": system, "stream": False, "think": False}
    if images and engine_sees(model):
        body["images"] = images
    r = requests.post(OLLAMA + "/api/generate", json=body, timeout=timeout)
    if r.status_code >= 500 and ("loading model" in r.text or "llama-server" in r.text):
        # the engine couldn't load: ComfyUI still holds the GPU from the last render. Free it and try once more —
        # before, this failed silently and the director / picture-reading rewriter fell back to the raw words
        _note("[engine] %s couldn't load (GPU busy) — freeing ComfyUI VRAM and retrying" % model)
        try:
            try:
                from . import comfy as _c
            except ImportError:
                import comfy as _c
            requests.post(_c.BASE + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
            time.sleep(3)
        except Exception:
            pass
        r = requests.post(OLLAMA + "/api/generate", json=body, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    return (d.get("response") or "").strip() or (d.get("thinking") or "").strip()


def evict_ollama():
    """Free VRAM/RAM before a heavy render (big text encoders stage in system RAM)."""
    try:
        for m in requests.get(OLLAMA + "/api/ps", timeout=5).json().get("models", []):
            requests.post(OLLAMA + "/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
        for _ in range(30):
            if not requests.get(OLLAMA + "/api/ps", timeout=5).json().get("models"):
                break
            time.sleep(2)
    except Exception:
        pass


def read_text(path, limit=20000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit).strip()
    except OSError:
        return ""


def clean_ws(t):
    return re.sub(r"\s{2,}", " ", t or "").strip(" ,.-")
