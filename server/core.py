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
           "patreon": "https://www.patreon.com/MirCorp"}
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
NO_WINDOW = 0x08000000

# Installed copies (MirMediaLabs-Setup.exe) write mml_config.json at ROOT with their own engine and
# ffmpeg paths; the dev copy on the build PC has no config and keeps the paths it always used.
CONFIG = {}
try:
    with open(os.path.join(ROOT, "mml_config.json"), encoding="utf-8") as _f:
        CONFIG = json.load(_f)
except (OSError, ValueError):
    pass

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
DEFAULT_ENGINE = "llama3.1:8b"  # MUSE: chat, prompt building + Auto-mode model picker (never renders); falls back to any installed llama3.1 / first model


def engine_model():
    want = prefs().get("engine_model") or DEFAULT_ENGINE
    try:
        tags = [m["name"] for m in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return want
    if want in tags or not tags:
        return want
    pick = next((t for t in tags if t.startswith("llama3.1")), None) or tags[0]
    return pick


_CAPS = {}


def engine_sees(model=None):
    """True when the prompt engine can look at pictures (Ollama 'vision' capability). MUSE (Llama 3.1) is
    text-only: pictures are then left out of engine requests instead of failing them."""
    m = model or engine_model()
    if m not in _CAPS:
        try:
            r = requests.post(OLLAMA + "/api/show", json={"model": m}, timeout=5)
            _CAPS[m] = "vision" in (r.json().get("capabilities") or [])
        except Exception:
            return False
    return _CAPS[m]


def ask(prompt, system, timeout=120, images=None):
    model = engine_model()
    body = {"model": model, "prompt": prompt, "system": system, "stream": False, "think": False}
    if images and engine_sees(model):
        body["images"] = images
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
