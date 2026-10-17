"""MIR MEDIA LABS — paths, storage, isolation guard, access key, prompt engine.

Isolation contract (checked by /api/isolation):
  * every file this app reads or writes lives under ROOT (the install folder)
    — its own library, references, job history, settings and update folder;
  * it never imports outside code and never calls other apps;
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
    if fn in _ASSET_CACHE:
        return _ASSET_CACHE[fn]
    if fn not in ASSETS:
        return None
    import zlib
    data = zlib.decompress(ASSETS[fn])
    if len(data) < 262144:                           # pages / icons stay cached; preview media is decoded per request
        _ASSET_CACHE[fn] = data
    return data


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
    if at is not None and r.returncode == 0 and not os.path.isfile(dst):
        # a seek at/after the clip's last frame writes nothing (and says nothing): take the final frame instead
        args = [FFMPEG, "-y", "-v", "error", "-sseof", "-0.5", "-i", src, "-update", "1"] + (["-vf", ",".join(vf)] if vf else [])
        r = subprocess.run(args + [dst], capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError("ffmpeg: %s" % ((r.stderr or "")[-300:] or "no frame at %s s in %s" % (at, os.path.basename(src))))
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
    """Resolve and enforce the sandbox: inside our own folders, never inside MIR."""
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
        for i in range(20):            # Windows: a reader / antivirus holding the file briefly → WinError 5 on replace
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.1 * (i + 1))
        with open(path, "w", encoding="utf-8") as f:     # still locked for rename: overwrite in place, never lose the save
            json.dump(obj, f, indent=1)
        try:
            os.remove(tmp)
        except OSError:
            pass


def access_key():
    """Media Lab's own access key — unrelated to any other key."""
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
DEFAULT_ENGINE = "gemma4:12b"  # MirAI: chat, prompt building + Auto-mode model picker (never renders); falls back to any installed gemma4 / first model
LEGACY_ENGINES = ()   # (qwen3.5:9b used to be remapped to Gemma — it is a normal pickable engine now)
# Local brains the owner can pick in the model picker (MUSE chat + Director + prompt writer). Any other installed
# Ollama tag still works from Settings → Prompt engine; these are the tested ones.
LOCAL_ENGINES = [
    {"model": "gemma4:12b", "label": "Gemma 4 12B", "note": "recommended · sees pictures", "vision": True, "gb": 8.0},
    {"model": "llama3.1:8b", "label": "Llama 3.1 8B", "note": "lighter + faster · text only", "vision": False, "gb": 4.9},
]


def engine_label(model=None):
    m = model or engine_model()
    return next((e["label"] for e in LOCAL_ENGINES if e["model"] == m or m.startswith(e["model"] + "-")), pretty_tag(m))


def pretty_tag(m):
    """'qwen3.5:9b-mtp-nodraft' -> 'Qwen 3.5 9B (mtp-nodraft)' for any installed Ollama tag."""
    name, _, tag = (m or "").rpartition("/")[-1].partition(":")
    fam = re.sub(r"^([a-z]+)([0-9])", r"\1 \2", name).replace("-", " ").strip()
    fam = " ".join(w.upper() if w in ("hf", "mtp") else (w[:1].upper() + w[1:]) for w in fam.split())
    size, _, extra = tag.partition("-")
    return (fam + (" " + size.upper() if size else "") + (" (%s)" % extra if extra else "")).strip() or m


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


FALLBACK_ENGINE = "qwen3.5:9b"                  # used only when the chosen engine fails to load


class _Broken(set):
    """Engines Ollama failed to start. Entries EXPIRE after 10 min (a load that failed because a render held the GPU
    must not pin MirAI to the fallback for the rest of the run); picking a model in Settings clears it at once."""
    def __init__(self):
        super().__init__()
        self.t = {}

    def add(self, m):
        self.t[m] = time.time()
        super().add(m)

    def discard(self, m):
        self.t.pop(m, None)
        super().discard(m)

    def __contains__(self, m):
        if m in self.t and time.time() - self.t[m] > 600:
            self.discard(m)
        return super().__contains__(m)


USED = {"model": None}
TOK = {"in": 0, "out": 0, "secs": 0.0, "calls": 0, "ctx": 0, "num_ctx": 0}   # tokens of the job being worked on


def tok_reset():
    TOK.update({"in": 0, "out": 0, "secs": 0.0, "calls": 0, "ctx": 0, "num_ctx": 0})


def tok_add(tin=0, tout=0, secs=0.0, num_ctx=0):
    """Every AI call adds here: local Ollama (prompt_eval/eval counts) and cloud brains (usage)."""
    TOK["in"] += int(tin or 0)
    TOK["out"] += int(tout or 0)
    TOK["secs"] += float(secs or 0)
    TOK["calls"] += 1
    if tin:
        TOK["ctx"] = max(TOK["ctx"], int(tin or 0) + int(tout or 0))
    if num_ctx:
        TOK["num_ctx"] = int(num_ctx)


def tok_from_ollama(d, body=None):
    try:
        tin, tout = d.get("prompt_eval_count") or 0, d.get("eval_count") or 0
        if tin or tout:
            tok_add(tin, tout, (d.get("eval_duration") or 0) / 1e9,
                    ((body or {}).get("options") or {}).get("num_ctx") or CTX_OK.get((body or {}).get("model"), 0) or 16384)
    except Exception:
        pass
CTX_OK = {}                                         # engine -> num_ctx it starts with here (learned)                              # the local engine that actually answered last (bubble label)
ENGINE_BROKEN = _Broken()                           # engines Ollama failed to start this run (llama-server exit) → skipped


def engine_twin(m, tags):
    """A working stand-in for an engine that won't load: its -nodraft build (same weights, no bundled draft model —
    gemma4:12b's MTP draft crashes newer Ollama with 'Gemma4Assistant requires ctx_other'), else the fallback."""
    for t in (m + "-nodraft", m.split(":")[0] + ":" + m.split(":")[-1] + "-nodraft"):
        if t in tags and t not in ENGINE_BROKEN:
            return t
    return FALLBACK_ENGINE


CTX_CAP = int(CONFIG.get("max_ctx") or 65536)        # never ask any engine for more than this


def model_max_ctx(tag):
    """The context length the model itself supports (Ollama tags)."""
    try:
        for t in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", []):
            if t["name"] == tag:
                return int((t.get("details") or {}).get("context_length") or 0)
    except Exception:
        pass
    return 0


def engine_window(tag):
    """MirAI's memory for this engine: as big as the model supports (up to CTX_CAP), minus what was learned on this
    PC (a window that crashed it or spilled it off the GPU is remembered in CTX_OK)."""
    mx = model_max_ctx(tag) or 16384
    return max(2048, min(mx, CTX_CAP, CTX_OK.get(tag) or 10 ** 9))


def fit_window(tag, win, load):
    """Load `tag` at `win`; if the GPU can't hold it all (spills to the CPU = slow) or it won't start, halve the window
    and retry, down to 8K. Remembers the result in CTX_OK. load(num_ctx) -> requests.Response."""
    while True:
        r = load(win)
        ok = r is not None and r.ok
        spilled = False
        if ok:
            try:
                m = next((m for m in requests.get(OLLAMA + "/api/ps", timeout=3).json().get("models", []) if m["name"] == tag), None)
                spilled = bool(m and m.get("size") and m.get("size_vram", 0) < 0.97 * m["size"])
            except Exception:
                pass
        if (ok and not spilled) or win <= 8192:
            if ok:
                CTX_OK[tag] = win
            return r, win
        win = max(8192, win // 2)
        _note("[engine] %s: shrinking MirAI's memory to %d tokens to fit the GPU" % (tag, win))
        try:
            requests.post(OLLAMA + "/api/generate", json={"model": tag, "keep_alive": 0}, timeout=30)
        except Exception:
            pass


def free_for_engine(model):
    """Make room for MirAI's picked engine: unload every OTHER model Ollama holds (old engines, other apps' models)
    and ComfyUI's idle models. A picked engine that "won't start" is usually just out of VRAM, not broken."""
    try:
        for m in requests.get(OLLAMA + "/api/ps", timeout=3).json().get("models", []):
            if m["name"] != model:
                requests.post(OLLAMA + "/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
    except Exception:
        pass
    try:
        import comfy as _c
        q = requests.get(_c.BASE + "/queue", timeout=3).json()
        if not (q.get("queue_running") or q.get("queue_pending")):     # never pull models out from under a render
            requests.post(_c.BASE + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
    except Exception:
        pass
    time.sleep(2)


def engine_failed(r):
    return r is not None and r.status_code >= 500 and ("llama-server" in r.text or "loading model" in r.text)


def engine_post(path, body, **kw):
    """POST to Ollama with the engine in body['model']; an engine that can't start is marked broken and the request is
    retried on its stand-in (vision kept when the stand-in is the same family)."""
    r = None
    freed = False
    if body.get("model") in CTX_OK:
        o = body.get("options") or {}
        body = dict(body, options=dict(o, num_ctx=min(int(o.get("num_ctx") or 10 ** 9), CTX_OK[body["model"]])))
    for _ in range(5):
        r = requests.post(OLLAMA + path, json=body, **kw)
        if engine_failed(r) and not freed:            # out of VRAM? free the GPU and try the SAME engine once more
            freed = True
            free_for_engine(body.get("model"))
            continue
        nc = int((body.get("options") or {}).get("num_ctx") or 0)
        if engine_failed(r) and (nc == 0 or nc > 8192):   # some engines only start with a smaller context (no num_ctx
            body = dict(body, options=dict(body.get("options") or {}, num_ctx=8192))   # = the Modelfile's, often huge)
            CTX_OK[body["model"]] = 8192
            continue
        if not engine_failed(r) or body.get("model") == FALLBACK_ENGINE:
            if r is not None and r.ok:
                USED["model"] = body.get("model")
                if body.get("stream") is False:
                    try:
                        tok_from_ollama(r.json(), body)
                    except Exception:
                        pass
            return r
        ENGINE_BROKEN.add(body["model"])
        try:
            tags = [m["name"] for m in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
        except Exception:
            tags = []
        nxt = engine_twin(body["model"], tags)
        print("[engine] %s won't start — using %s" % (body["model"], nxt))
        body = dict(body, model=nxt)
        if body.get("images") and not engine_sees(nxt):
            body.pop("images", None)
    if r is not None and r.ok:
        USED["model"] = body.get("model")
    return r


def used_label(job=None):
    """'Gemma 4 12B', or 'Qwen 3.5 9B · fallback' when the picked engine couldn't run."""
    m = USED.get("model")
    if not m:
        return None
    picked = prefs().get("engine_model") or DEFAULT_ENGINE
    lab = engine_label(m).split(" · ", 1)[-1]
    return lab if (m == picked or m.startswith(picked + "-") or picked.startswith(m)) else lab + " · fallback"


def engine_model():
    want = prefs().get("engine_model") or DEFAULT_ENGINE
    if want in LEGACY_ENGINES:
        want = DEFAULT_ENGINE
    try:
        tags = [m["name"] for m in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return want
    if want in ENGINE_BROKEN:
        return engine_twin(want, tags)
    if want in tags or not tags:
        return want
    pick = next((t for t in tags if t.startswith(DEFAULT_ENGINE.split(":")[0])), None) or tags[0]
    return pick


_CAPS = {}


def engine_sees(model=None):
    """True when the prompt engine can look at pictures (Ollama 'vision' capability). MirAI (Gemma 4 12B) sees
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


VISION_PREF = ("qwen3.5:9b", "gemma4:12b-nodraft", "gemma4:12b")   # qwen3.5:9b: verified reading pictures (Gemma 4 + images crashes Ollama)


def vision_model():
    """A picture-reading engine: the chosen one if it has vision, else the first installed vision model that loads."""
    m = engine_model()
    if engine_sees(m) and not m.startswith("gemma4"):
        return m
    try:
        tags = [t["name"] for t in requests.get(OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return None
    for t in list(VISION_PREF) + tags:
        if t in tags and t not in ENGINE_BROKEN and engine_sees(t):
            return t
    return None


def can_see():
    return bool(vision_model())


def ask(prompt, system, timeout=120, images=None, want_json=False, role="prompt"):
    b = _cloud_brain()                               # the owner's cloud brain for this job (else local)
    if b:
        import cloud
        try:
            return cloud.ask(b, prompt, system, images=images, want_json=want_json, role=role,
                             timeout=max(timeout, 180))
        except cloud.CloudError as e:
            _note("[cloud] %s — using the local engine for this step" % e)
    gpu_wait("engine")
    ensure_ollama()
    model = engine_model()
    body = {"model": model, "prompt": prompt, "system": system, "stream": False, "think": False}
    if images:
        vm = vision_model()
        if vm:
            body["model"] = model = vm       # pictures go to an engine that can actually see them
            body["images"] = images
    r = engine_post("/api/generate", body, timeout=timeout)
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
    if r.status_code >= 500 and "llama-server" in r.text and model != FALLBACK_ENGINE:
        # the engine itself won't start (e.g. an Ollama update broke it) — answer with the fallback engine instead
        # of failing the whole step; the chosen engine stays chosen
        _note("[engine] %s won't start (%s) — using %s for this step" % (model, r.text[:120], FALLBACK_ENGINE))
        body.update(model=FALLBACK_ENGINE)
        body.pop("images", None)
        r = requests.post(OLLAMA + "/api/generate", json=body, timeout=timeout)
    r.raise_for_status()
    USED["model"] = body.get("model")
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


# ── RENDER PRIORITY: while a render holds the GPU, nothing else loads a model ───────────────────────────────────────
# prepare_gpu() takes the lock (after unloading Ollama) and the GPU worker releases it when the job ends. Every AI call
# (MUSE chat, the Director, Social, series writers) checks it first and WAITS — they must never pull a model back into
# VRAM/RAM mid-render. The worker thread itself is exempt (a render's own steps).
RENDER_LOCK = os.path.join(DATA, "rendering.lock")
RENDER_LOCK_MAX_S = 3 * 3600                    # a lock older than this is stale (crash) and ignored


def render_lock(job_id=""):
    try:
        with open(RENDER_LOCK, "w", encoding="utf-8") as f:
            json.dump({"job": job_id, "t": time.time(), "pid": os.getpid()}, f)
    except OSError:
        pass


def render_unlock():
    try:
        os.remove(RENDER_LOCK)
    except OSError:
        pass


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True                                # old lock without a pid: trust the age limit
    if pid == os.getpid():
        return True
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return True


def rendering():
    """→ the lock info while a render owns the GPU, else None."""
    try:
        with open(RENDER_LOCK, encoding="utf-8") as f:
            d = json.load(f)
        if time.time() - float(d.get("t") or 0) < RENDER_LOCK_MAX_S:
            if not _pid_alive(d.get("pid")):       # owner died (restart/crash mid-render) → stale; free the GPU for AI calls
                render_unlock()
                return None
            return d
    except (OSError, ValueError):
        pass
    return None


def gpu_wait(who="", max_wait=RENDER_LOCK_MAX_S):
    """Block an AI call until the render finishes (the GPU worker never waits on itself)."""
    if threading.current_thread().name == "mml-gpu-worker" or not rendering():
        return
    print("[gpu] %s waiting — a render has priority" % (who or "AI call"))
    t0 = time.time()
    while rendering() and time.time() - t0 < max_wait:
        time.sleep(3)
