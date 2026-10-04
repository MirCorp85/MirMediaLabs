"""MIR MEDIA LABS — setup wizard (compiled into MirMediaLabs-Setup.exe by installer\\build.ps1).

Installs a self-contained copy on any Windows PC with an NVIDIA GPU:
  <dir>\\app\\MirMediaLabs.exe              the app, compiled to native code (bundled payload.zip)
  <dir>\\updates                            Android app update folder
  <dir>\\runtime\\uv.exe, python, venv      private Python 3.13 + PyTorch CUDA — the render engine only
  <dir>\\engine\\ComfyUI                     headless ComfyUI engine (pinned tag) + models/
  Ollama + MUSE (Llama 3.1 8B)              optional: chat, prompt building, Auto-mode model picker (never renders)
Everything except Ollama lives in <dir>; uninstall removes it.  Downloads resume.

  MirMediaLabs-Setup.exe                         wizard (install / modify / repair)
  MirMediaLabs-Setup.exe --update --dir <dir>    apply a signed update (started by the app)
  MirMediaLabs-Setup.exe --uninstall             remove
"""
import ctypes
import json
import os
import queue
import shutil
import string
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import zipfile

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def compiled():
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def self_exe():
    return os.path.abspath(sys.argv[0])


try:
    BUILD = json.load(open(resource("build.json"), encoding="utf-8"))
except (OSError, ValueError):
    BUILD = {}
APP = "MIR MEDIA LABS"
APP_ID = "MirMediaLabs"
VERSION = BUILD.get("version", "dev")
COMFY_TAG = "0.38.2"                      # the ComfyUI release MML's graphs are verified on
PY_VER = "3.13"
UV_URL = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
COMFY_URL = "https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v%s.zip" % COMFY_TAG
OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"
UA = {"User-Agent": "MirMediaLabs-Setup/" + VERSION}
NO_WINDOW = 0x08000000
GB = 1024 ** 3
HF = "https://huggingface.co/"
H3, M3, QI, ACE = (HF + "Comfy-Org/MiniMax-H3/resolve/main/", HF + "Comfy-Org/MiniMax-Music-3/resolve/main/",
                   HF + "Comfy-Org/Qwen-Image-2.1/resolve/main/",
                   HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/")
STYLES = ["art_is_explosion", "blooming_flowers", "bullet_time", "dark_magic", "fire_breath", "four_seasons",
          "kiss_camera", "spiral_ascent", "storm_magic", "truman_show"]

# (models subfolder/file, url, bytes)  — exactly what server/renderers.py loads
COMPONENTS = {
    "video": ("Video — MiniMax H3", "text→video, image→video, first+last frame, native audio", [
        ("diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", H3, 20970379616),
        ("text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", H3, 15687142551),
        ("vae/minimax_h3_video_vae_int8_convrot.safetensors", H3, 2811065184),
        ("vae/minimax_h3_audio_vae_fp32.safetensors", H3, 605254808),
        ("loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", H3, 1956192992),
        ("loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", H3, 1956193000),
    ] + [("embeddings/minimaxh3_%s.safetensors" % s, H3, 0) for s in STYLES]),
    "video_ref": ("Video add-on — reference→video", "keeps faces/identity from your pictures (needs Video)", [
        ("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", H3, 20970379616),
        ("loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", H3, 1956193000),
    ]),
    "music": ("Songs — MiniMax Music 3", "full songs with vocals, up to 5 min", [
        ("diffusion_models/minimax_music3_dit_fp16.safetensors", M3, 4914197682),
        ("text_encoders/minimax_music3_text_encoder_pruned_int8_convrot.safetensors", M3, 9196611886),
        ("vae/minimax_music3_dav.safetensors", M3, 216696128),
    ]),
    "image": ("Images — Qwen-Image 2.1", "text→image, multi-picture edit, background removal", [
        ("diffusion_models/qwen_image_2.1_int8_convrot.safetensors", QI, 7256783064),
        ("text_encoders/qwen3vl_8b_int8_convrot.safetensors", QI, 9350798360),
        ("vae/qwen_image_2.1_vae_bf16.safetensors", QI, 675509688),
    ]),
    "ace": ("Beats — ACE-Step 1.5 XL", "fast tracks, remix, cover, voice swap", [
        ("diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors", ACE, 9974719892),
        ("text_encoders/qwen_0.6b_ace15.safetensors", ACE, 1191588248),
        ("text_encoders/qwen_4b_ace15.safetensors", ACE, 8379154232),
        ("vae/ace_1.5_vae.safetensors", ACE, 337431732),
    ]),
}
# MUSE = the lab's general-purpose language model: conversation, prompt building for every render model, and the
# Auto-mode model picker. It never renders anything — images, video and music always come from the render models.
# The server pins the tag (llm.MODEL_TAG / core.DEFAULT_ENGINE) — change all three together.
MUSE_TAG = "llama3.1:8b"
ENGINES = {MUSE_TAG: ("MUSE · Llama 3.1 8B (recommended)", 4.9),
           "": ("None — no MUSE: no chat or Auto mode, prompts used exactly as typed", 0)}
RUNTIME_GB = 9.0      # python + torch CUDA + ComfyUI deps (+ download cache, removed afterwards)
PARALLEL_DOWNLOADS = 3   # model files fetched at once (a single HTTPS stream rarely fills a fast line)
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" % APP_ID
APK_URL = "https://github.com/MirCorp85/MirMediaLabs/releases/latest/download/MirMediaLabs.apk"

BG, PANEL, FG, DIM, ACCENT, BAD, OK = "#0c0e13", "#151922", "#e9edf5", "#8a93a6", "#ffc83d", "#ff6b6b", "#5fd38d"
SIDE, LINE, BRAND = "#10131a", "#232a38", "#ff5a1f"

# one-click model sets; "recommended" is picked from the GPU's VRAM on the system check
PRESETS = {"recommended": "Recommended for your GPU", "all": "Everything", "light": "Light — images + beats",
           "custom": "Custom"}


def preset_components(name, vram_gb):
    if name == "all":
        return set(COMPONENTS)
    if name == "light":
        return {"image", "ace"}
    if vram_gb >= 24:
        return set(COMPONENTS)
    if vram_gb >= 11.5:
        return {"video", "music", "image", "ace"}
    return {"music", "image", "ace"}                   # the video model needs 12 GB+


_APPDATA = os.environ.get("APPDATA", "")
LNK_START = os.path.join(_APPDATA, "Microsoft", "Windows", "Start Menu", "Programs", APP + ".lnk")
LNK_STARTUP = os.path.join(_APPDATA, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", APP + " (server).lnk")
LNK_DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop", APP + ".lnk")


def app_exe(d):
    return os.path.join(d, "app", "MirMediaLabs.exe")


def read_config(d):
    try:
        return json.load(open(os.path.join(d, "mml_config.json"), encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def all_model_files():
    return [f for k in COMPONENTS for f in COMPONENTS[k][2]]


def have_model(base, rel, size):
    """An existing copy counts only at the exact expected size (no half-downloaded files)."""
    if not base:
        return False
    p = os.path.join(base, rel.replace("/", os.sep))
    try:
        return os.path.isfile(p) and (not size or os.path.getsize(p) == size)
    except OSError:
        return False


def find_existing_models(exclude=None):
    """Scan the usual ComfyUI / Comfy Desktop model folders on every drive.
    Returns (best folder, files matched, GB saved) — or (None, 0, 0)."""
    import glob
    la, home = os.environ.get("LOCALAPPDATA", ""), os.path.expanduser("~")
    cands = [os.path.join(la, "Comfy-Desktop", "ComfyUI-Shared", "models"),
             os.path.join(home, "Documents", "ComfyUI", "models"), os.path.join(home, "ComfyUI", "models")]
    try:      # Comfy Desktop installs elsewhere: read its model-path yaml files
        for y in glob.glob(os.path.join(os.environ.get("APPDATA", ""), "Comfy Desktop", "**", "*.yaml"), recursive=True):
            for line in open(y, encoding="utf-8", errors="ignore"):
                if "base_path:" in line:
                    b = line.split("base_path:", 1)[1].strip().strip("'\"")
                    cands += [b, os.path.join(b, "models")]
    except Exception:
        pass
    for d in string.ascii_uppercase:
        root = d + ":\\"
        if not os.path.exists(root) or ctypes.windll.kernel32.GetDriveTypeW(root) != 3:
            continue
        for sub in ("", "AI", "Tools", "Programs", "Program Files"):
            base = os.path.join(root, sub)
            try:
                names = [n for n in os.listdir(base) if "comfy" in n.lower() or "mirmedialabs" in n.lower()]
            except OSError:
                continue
            for n in names:
                p = os.path.join(base, n)
                cands += [os.path.join(p, "models"), os.path.join(p, "ComfyUI", "models"),
                          os.path.join(p, "engine", "ComfyUI", "models")]      # another MML install
    ex = os.path.normcase(os.path.abspath(exclude)) if exclude else None
    best, bn, bgb, seen = None, 0, 0.0, set()
    for c in cands:
        c = os.path.abspath(c)
        k = os.path.normcase(c)
        if k in seen or not os.path.isdir(c) or (ex and k.startswith(ex)):
            continue
        seen.add(k)
        hits = [sz for rel, _, sz in all_model_files() if have_model(c, rel, sz)]
        gb = sum(hits) / GB
        if gb > bgb or (gb == bgb and len(hits) > bn):
            best, bn, bgb = c, len(hits), gb
    return (best, bn, bgb) if bn else (None, 0, 0.0)


def comp_bytes(key):
    return sum(sz for _, _, sz in COMPONENTS[key][2])


# ─────────────────────────────── system checks ───────────────────────────────
def run_quiet(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.stdout.strip()
    except Exception:
        return ""


def gpu_info():
    smi = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    out = run_quiet([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if not out:
        return None
    name, mem, drv = [x.strip() for x in out.splitlines()[0].split(",")[:3]]
    return {"name": name, "vram_gb": round(float(mem) / 1024, 1), "driver": drv}


def ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), ("pt", ctypes.c_ulonglong), ("pa", ctypes.c_ulonglong),
                    ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
    m = MS()
    m.l = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.total / GB, 1), round(m.pt / GB, 1)      # RAM, RAM + pagefile commit limit


def free_gb(path):
    d = os.path.splitdrive(os.path.abspath(path))[0] + "\\"
    try:
        return shutil.disk_usage(d).free / GB
    except OSError:
        return 0.0


def default_dir():
    prev = registry_install_dir()
    if prev:
        return prev
    drives = [d + ":\\" for d in string.ascii_uppercase if os.path.exists(d + ":\\")]
    fixed = [d for d in drives if ctypes.windll.kernel32.GetDriveTypeW(d) == 3]
    best = max(fixed or ["C:\\"], key=free_gb)
    return os.path.join(best, APP_ID)


def registry_install_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            return winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        return None


def torch_backend(driver):
    major = float(driver.split(".")[0] + "." + (driver.split(".")[1] if "." in driver else "0"))
    if major >= 580:
        return "cu130", ["torch==2.12.1", "torchvision==0.27.1", "torchaudio"]
    return "cu128", ["torch==2.11.0", "torchvision", "torchaudio"]


def ollama_exe():
    for c in (shutil.which("ollama"), os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")):
        if c and os.path.isfile(c):
            return c
    return None


def http_ok(url, timeout=3):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# ─────────────────────────────── installer engine ───────────────────────────────
class Cancelled(Exception):
    pass


class Installer:
    def __init__(self, opts, emit):
        self.o, self.emit = opts, emit
        self.dir = opts["dir"]
        self.rt = os.path.join(self.dir, "runtime")
        self.venv = os.path.join(self.rt, "venv")
        self.py = os.path.join(self.venv, "Scripts", "python.exe")
        self.uv = os.path.join(self.rt, "uv.exe")
        self.engine = os.path.join(self.dir, "engine")
        self.comfy = os.path.join(self.engine, "ComfyUI")
        self.models = os.path.join(self.comfy, "models")
        self.cache = os.path.join(self.rt, "cache")
        self.cancel = False
        self.logf = None
        self._log_lock = threading.Lock()
        self._dl_thread, self._dl_error = None, None

    # helpers
    def log(self, msg):
        line = time.strftime("%H:%M:%S ") + msg
        self.emit("log", line)
        with self._log_lock:                                # downloads log from worker threads
            if self.logf and not self.logf.closed:
                self.logf.write(line + "\n")
                self.logf.flush()

    def check(self):
        if self.cancel:
            raise Cancelled()

    def env(self):
        return dict(os.environ, UV_PYTHON_INSTALL_DIR=os.path.join(self.rt, "python"), UV_CACHE_DIR=self.cache,
                    UV_LINK_MODE="copy", UV_NO_PROGRESS="1", PYTHONUTF8="1", UV_HTTP_TIMEOUT="300")

    def sh(self, cmd, cwd=None):
        self.log("$ " + " ".join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)))
        p = subprocess.Popen(cmd, cwd=cwd, env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        tail = []
        for line in p.stdout:
            line = line.rstrip()
            if line:
                tail = (tail + [line])[-15:]
                self.log("  " + line[:220])
            if self.cancel:
                p.kill()
                raise Cancelled()
        if p.wait() != 0:
            raise RuntimeError("command failed (%d): %s\n%s" % (p.returncode, cmd[0], "\n".join(tail[-6:])))

    def download(self, url, dest, size=0, label=None, progress=None):
        """Resumable HTTP download → dest (skips when already complete).
        progress(label, have, total) replaces the per-file UI event (used by the parallel model downloads)."""
        label = label or os.path.basename(dest)
        report = progress or (lambda lb, h, t, rate=0: self.emit("file", (lb, h, t, rate)))
        if os.path.isfile(dest) and (not size or os.path.getsize(dest) == size):
            report(label, size or 1, size or 1)
            return dest
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        part = dest + ".part"
        for attempt in range(8):
            self.check()
            have = os.path.getsize(part) if os.path.isfile(part) else 0
            hdr = dict(UA)
            if have:
                hdr["Range"] = "bytes=%d-" % have
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
                    if have and r.status != 206:
                        have = 0                                   # server ignored Range → start over
                    total = size or (int(r.headers.get("Content-Length") or 0) + have)
                    t0, done0 = time.time(), have
                    with open(part, "ab" if have else "wb") as f:
                        while True:
                            self.check()
                            chunk = r.read(1 << 20)
                            if not chunk:
                                break
                            f.write(chunk)
                            have += len(chunk)
                            dt = time.time() - t0
                            report(label, have, total, (have - done0) / dt if dt > 0.5 else 0)
                if size and os.path.getsize(part) != size:
                    raise IOError("incomplete: %d of %d bytes" % (os.path.getsize(part), size))
                os.replace(part, dest)
                return dest
            except Cancelled:
                raise
            except Exception as e:
                self.log("  download retry %d (%s): %s" % (attempt + 1, label, e))
                time.sleep(min(30, 3 * (attempt + 1)))
        raise RuntimeError("could not download %s" % url)

    # steps
    def stop_running(self):
        """Stop this install's app + engine (never the setup running from data\\updates)."""
        dirs = " -or ".join("$_.ExecutablePath -like '%s\\*'" % os.path.join(self.dir, d).replace("'", "''")
                            for d in ("app", "runtime"))
        run_quiet(["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process | Where-Object { (%s) -and $_.ProcessId -ne %d } | ForEach-Object "
                   "{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % (dirs, os.getpid())], 60)
        time.sleep(1.5)

    def step_files(self):
        os.makedirs(self.dir, exist_ok=True)
        self.stop_running()
        # earlier builds shipped readable source — remove it; the app is now one compiled folder
        for old in ("server", "launcher.pyw", "app"):
            p = os.path.join(self.dir, old)
            for _ in range(10):
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    elif os.path.isfile(p):
                        os.remove(p)
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError("can't replace %s — close MIR MEDIA LABS and retry" % p)
        with zipfile.ZipFile(resource("payload.zip")) as z:
            for m in z.infolist():
                target = os.path.abspath(os.path.join(self.dir, m.filename))
                if not target.startswith(os.path.abspath(self.dir) + os.sep):
                    continue
                if m.filename.startswith("data/") and os.path.exists(target):
                    continue                                # never overwrite the user's data on repair
                z.extract(m, self.dir)
        for d in ("data", "data/logs", "engine/shared/input", "engine/shared/output"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        if compiled():                                     # keep a copy for Modify / Repair / Uninstall
            me = os.path.join(self.dir, "MirMediaLabs-Setup.exe")
            if self_exe().lower() != me.lower():
                shutil.copy2(self_exe(), me)

    def step_python(self):
        if not os.path.isfile(self.uv):
            z = self.download(UV_URL, os.path.join(self.cache, "uv.zip"), label="uv (package manager)")
            with zipfile.ZipFile(z) as zz:
                name = next(n for n in zz.namelist() if n.endswith("uv.exe"))
                with zz.open(name) as s, open(self.uv, "wb") as d:
                    shutil.copyfileobj(s, d)
        if not os.path.isfile(self.py):
            self.sh([self.uv, "venv", self.venv, "--python", PY_VER, "--managed-python"])

    def step_comfy(self):
        verf = os.path.join(self.comfy, "comfyui_version.py")
        if os.path.isfile(verf) and COMFY_TAG in open(verf, encoding="utf-8").read():
            self.log("ComfyUI %s already installed" % COMFY_TAG)
            return
        z = self.download(COMFY_URL, os.path.join(self.cache, "comfyui-%s.zip" % COMFY_TAG), label="ComfyUI engine")
        tmp = os.path.join(self.engine, "_new")
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(z) as zz:
            zz.extractall(tmp)
        src = os.path.join(tmp, os.listdir(tmp)[0])
        if os.path.isdir(self.comfy):                      # upgrade: keep downloaded models
            if os.path.isdir(self.models):
                shutil.rmtree(os.path.join(src, "models"), ignore_errors=True)
                shutil.move(self.models, os.path.join(src, "models"))
            shutil.rmtree(self.comfy, ignore_errors=True)
        shutil.move(src, self.comfy)
        shutil.rmtree(tmp, ignore_errors=True)

    def step_packages(self):
        backend, torch_pkgs = torch_backend(self.o["gpu"]["driver"])
        self.log("PyTorch backend: %s" % backend)
        base = [self.uv, "pip", "install", "--python", self.py, "--torch-backend", backend]
        self.sh(base + torch_pkgs)
        # engine only — the app itself is compiled and needs none of this (imageio-ffmpeg = its ffmpeg binary)
        self.sh(base + ["-r", os.path.join(self.comfy, "requirements.txt"), "imageio-ffmpeg"])

    def step_ollama(self):
        tag = self.o["engine"]
        if not tag:
            return
        exe = ollama_exe()
        if not exe and not http_ok("http://127.0.0.1:11434/api/tags"):
            setup = self.download(OLLAMA_URL, os.path.join(self.cache, "OllamaSetup.exe"), label="Ollama")
            self.log("installing Ollama (silent) …")
            self.sh([setup, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"])
            exe = ollama_exe()
        for i in range(60):
            if http_ok("http://127.0.0.1:11434/api/tags"):
                break
            if i == 5 and exe:
                subprocess.Popen([exe, "serve"], creationflags=NO_WINDOW | 0x00000008)
            time.sleep(2)
        else:
            raise RuntimeError("Ollama didn't start — install it from ollama.com, then run Repair")
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
                have = [m["name"] for m in json.load(r).get("models", [])]
        except Exception:
            have = []
        if tag in have:
            self.log("%s already installed" % tag)
        else:
            self.pull(tag)
        self.set_pref("engine_model", tag)

    def pull(self, tag):
        self.log("pulling %s …" % tag)
        req = urllib.request.Request("http://127.0.0.1:11434/api/pull", data=json.dumps({"model": tag}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            for line in r:
                self.check()
                d = json.loads(line or b"{}")
                if d.get("error"):
                    raise RuntimeError("ollama pull: " + d["error"])
                if d.get("total"):
                    self.emit("file", ("engine " + tag, d.get("completed", 0), d["total"], 0))

    def set_pref(self, key, val):
        prefs_f = os.path.join(self.dir, "data", "prefs.json")
        prefs = {}
        try:
            prefs = json.load(open(prefs_f, encoding="utf-8"))
        except (OSError, ValueError):
            pass
        prefs[key] = val
        json.dump(prefs, open(prefs_f, "w", encoding="utf-8"), indent=1)

    def step_models(self):
        """Download the chosen models PARALLEL_DOWNLOADS files at a time (one stream rarely fills a fast line),
        reporting one combined progress: ("dl", (done_bytes, total_bytes, bytes_per_s, files_done, files_total))."""
        from concurrent.futures import ThreadPoolExecutor
        files = [f for k in self.o["components"] for f in COMPONENTS[k][2]]
        reuse = self.o.get("reuse") or ""
        todo = []
        for rel, base, size in files:
            if have_model(reuse, rel, size):
                self.log("reusing %s" % rel)
                continue
            todo.append((rel, base, size))
        total = sum(s for _, _, s in todo) or 1
        have, lock = {}, threading.Lock()
        state = {"files": 0, "t0": time.time(), "b0": None, "last": 0.0}

        def prog(label, h, t, rate=0):
            with lock:
                have[label] = h
                done = sum(have.values())
                now = time.time()
                if state["b0"] is None:                     # resumed bytes don't count toward the speed
                    state["b0"], state["t0"] = done, now
                if now - state["last"] < 0.25 and done < total:
                    return
                state["last"] = now
                dt = now - state["t0"]
                bps = (done - state["b0"]) / dt if dt > 1 else 0
                self.emit("dl", (done, total, bps, state["files"], len(todo)))

        def one(item):
            rel, base, size = item
            self.check()
            name = rel.split("/")[-1]
            self.download(base + rel, os.path.join(self.models, rel.replace("/", os.sep)), size, name, progress=prog)
            with lock:
                state["files"] += 1
            prog(name, size or have.get(name, 0), size)
            self.log("model ready: %s" % name)

        self.emit("dl", (0, total, 0, 0, len(todo)))
        # biggest first, so the long poles start early and small files fill the gaps
        with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as ex:
            futs = [ex.submit(one, it) for it in sorted(todo, key=lambda x: -x[2])]
            try:
                for f in futs:
                    f.result()                              # re-raises Cancelled / download errors
            except BaseException:
                self.cancel = True                          # stop the other streams, then report the first error
                raise
        self.emit("dl", (total, total, 0, len(todo), len(todo)))

    def step_finish(self):
        reuse = self.o.get("reuse") or ""
        yml = None
        if reuse:
            yml = os.path.join(self.engine, "extra_model_paths.yaml")
            subs = ["diffusion_models", "text_encoders", "vae", "loras", "embeddings", "checkpoints", "model_patches"]
            with open(yml, "w", encoding="utf-8") as f:
                f.write("mml_existing:\n  base_path: %s\n" % json.dumps(reuse))
                for s in subs:
                    f.write("  %s: %s/\n" % (s, s))
        ff = run_quiet([self.py, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], 60)
        cfg_f = os.path.join(self.dir, "mml_config.json")
        cfg = read_config(self.dir)                         # keep e.g. a custom port / update_url
        cfg.update({"comfy_root": self.engine, "comfy_python": self.py,
                    "comfy_shared": os.path.join(self.engine, "shared"), "comfy_model_paths": yml,
                    "ffmpeg": ff.splitlines()[-1] if ff else None, "installed": time.strftime("%Y-%m-%d %H:%M"),
                    "version": VERSION, "components": self.o["components"], "engine": self.o["engine"],
                    "reuse": reuse or None})
        cfg.setdefault("comfy_args", [])
        cfg.setdefault("port", 5400)
        json.dump(cfg, open(cfg_f, "w", encoding="utf-8"), indent=1)

        # self-test: CUDA visible to the engine's PyTorch
        out = run_quiet([self.py, "-c", "import torch;print(torch.__version__, torch.cuda.is_available(), "
                                        "torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"], 180)
        self.log("PyTorch check: " + (out or "no output"))
        if "True" not in out:
            raise RuntimeError("PyTorch can't see the GPU (%s). Update the NVIDIA driver, then run Repair." % out)

        self.shortcuts()
        if self.o.get("lan"):
            self.log("opening port 5400 for your Wi-Fi (Windows will ask for permission) …")
            rule = ("netsh advfirewall firewall delete rule name='MIR MEDIA LABS' | Out-Null; "
                    "netsh advfirewall firewall add rule name='MIR MEDIA LABS' dir=in action=allow protocol=TCP "
                    "localport=5400 profile=private")
            run_quiet(["powershell", "-NoProfile", "-Command",
                       "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "
                       "'-NoProfile','-Command',\"%s\"" % rule], 180)
        self.register()
        shutil.rmtree(self.cache, ignore_errors=True)

    def shortcuts(self):
        exe = app_exe(self.dir)
        ico = os.path.join(self.dir, "MirMediaLabs.ico")
        links = [(LNK_START, "")]
        if self.o.get("desktop"):
            links.append((LNK_DESKTOP, ""))
        if self.o.get("autostart"):
            links.append((LNK_STARTUP, "--server-only"))
        elif os.path.exists(LNK_STARTUP):
            os.remove(LNK_STARTUP)
        for path, extra in links:
            ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{t}';"
                  "$s.Arguments='{x}';$s.WorkingDirectory='{w}';$s.IconLocation='{i}';$s.Save()").format(
                lnk=path.replace("'", "''"), t=exe.replace("'", "''"), x=extra,
                w=os.path.dirname(exe).replace("'", "''"), i=ico.replace("'", "''"))
            run_quiet(["powershell", "-NoProfile", "-Command", ps])

    def register(self):
        import winreg
        size_kb = 0
        for k in self.o["components"]:
            size_kb += comp_bytes(k) // 1024
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            me = os.path.join(self.dir, "MirMediaLabs-Setup.exe")
            for name, val in (("DisplayName", APP), ("DisplayVersion", VERSION), ("Publisher", "MirCorp"),
                              ("InstallLocation", self.dir), ("DisplayIcon", os.path.join(self.dir, "MirMediaLabs.ico")),
                              ("UninstallString", '"%s" --uninstall' % me), ("ModifyPath", '"%s"' % me)):
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, min(size_kb + int(RUNTIME_GB * 1024 * 1024), 0xFFFFFFFF))
            winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)

    def _models_bg(self):
        """Model downloads run in the background WHILE the runtime installs (they used to wait for it)."""
        try:
            self.step_models()
        except BaseException as e:                          # handed to the main thread by wait_models()
            self._dl_error = e

    def wait_models(self):
        while self._dl_thread and self._dl_thread.is_alive():
            self.check()
            self._dl_thread.join(0.5)
        if self._dl_error:
            raise self._dl_error

    def run(self):
        steps = [("App files", self.step_files, 1), ("Python runtime", self.step_python, 3),
                 ("ComfyUI engine", self.step_comfy, 3), ("PyTorch + engine packages", self.step_packages, 18)]
        if self.o["engine"]:
            steps.append(("MUSE · Llama 3.1 8B (Ollama)", self.step_ollama, 8))
        self._dl_thread, self._dl_error = None, None
        if self.o["components"]:
            steps.append(("Finishing model downloads", self.wait_models, 60))
        steps.append(("Shortcuts + self-test", self.step_finish, 4))
        os.makedirs(os.path.join(self.dir, "data", "logs"), exist_ok=True)
        self.logf = open(os.path.join(self.dir, "data", "logs", "install.log"), "a", encoding="utf-8")
        self.log("=== %s %s setup → %s  components=%s engine=%s" % (APP, VERSION, self.dir, self.o["components"],
                                                                     self.o["engine"] or "none"))
        weight = sum(w for _, _, w in steps)
        acc = 0
        try:
            for i, (name, fn, w) in enumerate(steps):
                self.emit("step", (i, name, acc / weight, w / weight))
                self.log("── " + name)
                fn()
                acc += w
                # models start once ComfyUI's folder is final (an upgrade moves models/), and then download
                # while PyTorch + packages + the prompt engine install — the two longest jobs overlap
                if fn == self.step_comfy and self.o["components"]:
                    self._dl_thread = threading.Thread(target=self._models_bg, daemon=True)
                    self._dl_thread.start()
            self.emit("step", (len(steps), "Done", 1.0, 0))
            self.emit("done", None)
        except Cancelled:
            self.log("cancelled — run setup again to resume (downloads continue where they stopped)")
            self.emit("failed", "Cancelled. Run setup again to resume; finished downloads are kept.")
        except Exception as e:
            self.log(traceback.format_exc())
            self.emit("failed", str(e))
        finally:
            if self._dl_thread and self._dl_thread.is_alive():
                self.cancel = True                          # a failed step stops the downloads too (they resume later)
                self._dl_thread.join(30)
            self.logf.close()


# ─────────────────────────────── wizard UI ───────────────────────────────
class Showcase(tk.Frame):
    """Rotating gallery of real MIR MEDIA LABS renders (built into the setup by installer\\make_showcase.py)."""

    def __init__(self, parent, big=True, every=4500):
        super().__init__(parent, bg=BG)
        self.slides, self.i, self.every = [], 0, every
        hi = float(parent.tk.call("tk", "scaling")) / (96 / 72) >= 1.4
        try:
            idx = json.load(open(resource(os.path.join("showcase", "index.json")), encoding="utf-8"))
        except (OSError, ValueError):
            idx = []
        for s in idx:
            fn = s["file"] + ("_2x" if hi else "_1x") + ("" if big else "_s") + ".png"
            try:
                self.slides.append((tk.PhotoImage(file=resource(os.path.join("showcase", fn))), s.get("caption", "")))
            except tk.TclError:
                pass
        if not self.slides:
            return
        self.pic = tk.Label(self, bg=BG, bd=0)
        self.pic.pack()
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="MADE WITH MIR MEDIA LABS", bg=BG, fg=BRAND, font=("Segoe UI Semibold", 8)).pack(side="left")
        self.cap = tk.Label(row, bg=BG, fg=DIM, font=("Segoe UI", 9), anchor="w")
        self.cap.pack(side="left", padx=8)
        self.dots = tk.Label(row, bg=BG, fg=DIM, font=("Segoe UI", 9))
        self.dots.pack(side="right")
        self.pic.bind("<Button-1>", lambda e: self.step(1))
        self.show()

    def show(self):
        img, cap = self.slides[self.i]
        self.pic.config(image=img)
        self.cap.config(text=cap)
        self.dots.config(text=" ".join("●" if k == self.i else "○" for k in range(len(self.slides))))

    def step(self, d=1):
        if self.slides and self.winfo_exists():
            self.i = (self.i + d) % len(self.slides)
            self.show()

    def start(self):
        if self.slides:
            self._tick()
        return self

    def _tick(self):
        if not self.winfo_exists():
            return
        self.step(1)
        self.after(self.every, self._tick)


class Wizard(tk.Tk):
    STEPS = ("Welcome", "Your PC", "Choose", "Ready", "Install", "Done")

    def __init__(self, update_dir=None):
        super().__init__()
        self.title("%s Setup" % APP)
        f = max(1.0, float(self.tk.call("tk", "scaling")) / (96 / 72))     # high-DPI screens
        w = min(1060 * f, self.winfo_screenwidth() * 0.92)
        h = min(720 * f, self.winfo_screenheight() * 0.88)
        self.geometry("%dx%d+%d+%d" % (w, h, (self.winfo_screenwidth() - w) / 2, (self.winfo_screenheight() - h) / 3))
        self.minsize(int(w * 0.9), int(h * 0.9))
        self.configure(bg=BG)
        try:
            self.iconbitmap(resource("MirMediaLabs.ico"))
        except tk.TclError:
            pass
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("Segoe UI", 10))
        for kind in ("TCheckbutton", "TRadiobutton"):
            st.configure(kind, background=BG, foreground=FG, indicatorbackground=PANEL,
                         indicatorforeground=ACCENT, indicatorsize=int(13 * f))
            st.map(kind, background=[("active", BG)])
            st.configure("Card." + kind, background=PANEL, foreground=FG, indicatorbackground=BG,
                         indicatorforeground=ACCENT, indicatorsize=int(13 * f))
            st.map("Card." + kind, background=[("active", PANEL)])
        st.configure("Accent.TButton", background=ACCENT, foreground="#111", font=("Segoe UI Semibold", 10), padding=(20, 7))
        st.map("Accent.TButton", background=[("disabled", "#5a5235"), ("active", "#ffd768")])
        st.configure("TButton", background=PANEL, foreground=FG, padding=(14, 7), bordercolor=LINE)
        st.map("TButton", background=[("active", "#202634")])
        for name, col in (("Horizontal.TProgressbar", ACCENT), ("Dl.Horizontal.TProgressbar", "#1fc8dc")):
            st.configure(name, background=col, troughcolor=PANEL, bordercolor=PANEL, lightcolor=col, darkcolor=col,
                         thickness=int(8 * f))
        st.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=FG)
        self.scale = f

        # ── left: brand + step list ──
        side = tk.Frame(self, bg=SIDE, width=int(230 * f))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=SIDE)
        brand.pack(fill="x", padx=20, pady=(24, 26))
        try:
            self._logo = tk.PhotoImage(file=resource("icon-64.png"))
            tk.Label(brand, image=self._logo, bg=SIDE).pack(anchor="w")
        except tk.TclError:
            pass
        tk.Label(brand, text="MIR MEDIA LABS", bg=SIDE, fg=ACCENT, font=("Segoe UI Black", 13)).pack(anchor="w", pady=(10, 0))
        tk.Label(brand, text="Setup · v%s" % VERSION, bg=SIDE, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w")
        self.step_lbls = []
        for i, name in enumerate(self.STEPS):
            r = tk.Frame(side, bg=SIDE)
            r.pack(fill="x", padx=14, pady=1)
            dot = tk.Label(r, text="○", bg=SIDE, fg=DIM, font=("Segoe UI", 11), width=2)
            dot.pack(side="left")
            lbl = tk.Label(r, text=name, bg=SIDE, fg=DIM, font=("Segoe UI", 10), anchor="w")
            lbl.pack(side="left", fill="x", padx=4, pady=5)
            self.step_lbls.append((dot, lbl))
        foot = tk.Frame(side, bg=SIDE)
        foot.pack(side="bottom", fill="x", padx=20, pady=18)
        tk.Label(foot, text="© 2026 MirCorp · GPL-3.0", bg=SIDE, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(foot, text="Free & open source", bg=SIDE, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")

        # ── right: page title, body, navigation ──
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        head = tk.Frame(main, bg=BG)
        head.pack(fill="x", padx=30, pady=(22, 2))
        self.ttl = tk.Label(head, text="", bg=BG, fg=FG, font=("Segoe UI Semibold", 17))
        self.ttl.pack(anchor="w")
        self.sub = tk.Label(head, text="", bg=BG, fg=DIM, font=("Segoe UI", 10))
        self.sub.pack(anchor="w")
        self.body = tk.Frame(main, bg=BG)
        self.body.pack(fill="both", expand=True, padx=30, pady=10)
        tk.Frame(main, bg=LINE, height=1).pack(fill="x")
        nav = tk.Frame(main, bg=BG)
        nav.pack(fill="x", padx=30, pady=14)
        self.btn_back = ttk.Button(nav, text="Back", command=self.back)
        self.btn_next = ttk.Button(nav, text="Next", style="Accent.TButton", command=self.next)
        self.btn_cancel = ttk.Button(nav, text="Cancel", command=self.on_cancel)
        self.btn_cancel.pack(side="left")
        self.btn_next.pack(side="right")
        self.btn_back.pack(side="right", padx=8)

        self.update_mode = bool(update_dir)
        self.sysinfo = None
        d = update_dir or default_dir()
        cfg = read_config(d) if (update_dir or registry_install_dir()) else {}
        prev = cfg.get("components")
        self.v_dir = tk.StringVar(value=d)
        self.v_comp = {k: tk.BooleanVar(value=(k in prev) if prev is not None else (k != "video_ref")) for k in COMPONENTS}
        self.v_preset = tk.StringVar(value="custom" if prev is not None else "recommended")
        old = cfg.get("engine", MUSE_TAG) if cfg else MUSE_TAG
        self.v_engine = tk.StringVar(value=old if old in ENGINES else MUSE_TAG)   # older installs had Qwen 3.5 → MUSE
        self.v_desktop = tk.BooleanVar(value=os.path.exists(LNK_DESKTOP) if cfg else True)
        self.v_auto = tk.BooleanVar(value=os.path.exists(LNK_STARTUP))
        self.v_lan = tk.BooleanVar(value=not cfg)          # firewall rule already added on first install
        self.v_reuse = tk.StringVar(value=cfg.get("reuse") or "")
        self.q = queue.Queue()
        self.inst = None
        self.pages = [self.page_welcome, self.page_system, self.page_options, self.page_ready, self.page_install,
                      self.page_finish]
        self.idx = 0
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        if self.update_mode:                               # signed update started by the app: straight to work
            self.title("%s — updating to v%s" % (APP, VERSION))
            self.sysinfo = {"gpu": gpu_info() or {"driver": "580"}}
            self.idx = 4
        self.show()

    # ── navigation
    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def show(self):
        self.clear()
        for i, (dot, lbl) in enumerate(self.step_lbls):
            cur, past = i == self.idx, i < self.idx
            dot.config(text="●" if cur else ("✓" if past else "○"), fg=ACCENT if cur else (OK if past else DIM))
            lbl.config(fg=FG if cur else (OK if past else DIM),
                       font=("Segoe UI Semibold" if cur else "Segoe UI", 10))
        self.btn_back.state(["!disabled"] if 0 < self.idx < 4 else ["disabled"])
        self.btn_next.state(["!disabled"])
        self.btn_next.config(text="Next")
        self.pages[self.idx]()

    def head(self, title, sub=""):
        self.ttl.config(text=title)
        self.sub.config(text=sub)

    def next(self):
        if self.idx == 2 and not self.validate_options():
            return
        if self.idx == 5:
            self.finish()
            return
        self.idx += 1
        self.show()

    def back(self):
        self.idx = max(0, self.idx - 1)
        self.show()

    def on_cancel(self):
        if self.inst and self.idx == 4 and not getattr(self, "_ended", False):
            if messagebox.askyesno(APP, "Stop the installation?\nFinished downloads are kept — run setup again to resume."):
                self.inst.cancel = True
            return
        self.destroy()

    def text(self, s, fg=FG, size=10, bold=False, pad=(0, 6), wrap=760, parent=None, bg=BG):
        wrap = int(wrap * self.scale)
        lbl = tk.Label(parent or self.body, text=s, bg=bg, fg=fg, justify="left", wraplength=wrap,
                       font=("Segoe UI Semibold" if bold else "Segoe UI", size))
        lbl.pack(anchor="w", pady=pad)
        return lbl

    def card(self, parent=None, title=None, **pack):
        c = tk.Frame(parent or self.body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        c.pack(fill="x", pady=(0, 10), **pack)
        inner = tk.Frame(c, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=14, pady=10)
        if title:
            tk.Label(inner, text=title.upper(), bg=PANEL, fg=ACCENT, font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(0, 4))
        return inner

    # ── pages
    def page_welcome(self):
        self.head("Welcome", "An independent AI agent front end for generative models — free and open source")
        prev = registry_install_dir()
        Showcase(self.body).start().pack(anchor="w", pady=(0, 12))
        self.text("Video with sound, full songs, images, beats and writing — rendered on this PC's GPU, "
                  "controlled from here, your phone or your TV.", size=11, bold=True, pad=(0, 4))
        grid = tk.Frame(self.body, bg=BG)
        grid.pack(fill="x", pady=(6, 8))
        feats = (("Video + sound", "MiniMax H3 · 4–15 s clips"), ("Full songs", "Music 3 · vocals, up to 5 min"),
                 ("Images", "Qwen-Image · edits, cutouts"), ("Beats", "ACE-Step · remix, cover"),
                 ("MUSE", "Llama 3.1 8B · chat + model picker"), ("Phone + TV", "free Android companion"))
        for i, (t, d) in enumerate(feats):
            c = tk.Frame(grid, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 8), pady=(0, 8))
            tk.Label(c, text=t, bg=PANEL, fg=FG, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(c, text=d, bg=PANEL, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 8))
        for col in range(3):
            grid.columnconfigure(col, weight=1)
        self.text("Setup installs, in one folder: the compiled app with signed updates · a private PyTorch runtime · "
                  "the ComfyUI render engine · the AI models you choose · optionally MUSE (Llama 3.1 8B through Ollama). "
                  "Nothing else on your PC changes; uninstall from Windows Settings → Apps.", fg=DIM)
        if prev:
            self.text("An existing install was found at %s — continuing will modify / repair it. "
                      "Your library and settings are kept." % prev, fg=ACCENT, pad=(8, 2))

    def page_system(self):
        self.head("Checking this PC", "MIR MEDIA LABS renders locally, so it needs an NVIDIA RTX card")
        if self.sysinfo is None:
            gpu = gpu_info()
            ram, commit = ram_gb()
            self.sysinfo = {"gpu": gpu, "ram": ram, "commit": commit,
                            "win": sys.getwindowsversion().build, "net": http_ok("https://huggingface.co", 8)}
        s = self.sysinfo
        rows, block = [], False
        g = s["gpu"]
        if not g:
            rows.append((BAD, "GPU", "No NVIDIA GPU found (nvidia-smi missing). MIR MEDIA LABS needs an NVIDIA RTX card."))
            block = True
        else:
            col = OK if g["vram_gb"] >= 11.5 else ACCENT
            rows.append((col, "GPU", "%s — %.0f GB VRAM%s" % (g["name"], g["vram_gb"],
                                                                "" if col == OK else "  (video needs 12 GB+; images, songs and beats work)")))
            drv = float(".".join(g["driver"].split(".")[:2]))
            if drv < 570:
                rows.append((BAD, "Driver", "%s — update the NVIDIA driver to 570 or newer first" % g["driver"]))
                block = True
            else:
                rows.append((OK, "Driver", "%s (%s)" % (g["driver"], torch_backend(g["driver"])[0])))
        rows.append((OK if s["ram"] >= 30 else ACCENT, "Memory", "%.0f GB RAM%s" % (
            s["ram"], "" if s["ram"] >= 30 else "  (32 GB recommended)")))
        pf = s["commit"] - s["ram"]
        rows.append((OK if s["commit"] >= 64 else ACCENT, "Page file", "%.0f GB%s" % (
            pf, "" if s["commit"] >= 64 else "  — raise it to 32–64 GB (System → Advanced → Virtual memory) "
                                               "or big video renders may crash")))
        rows.append((OK if s["win"] >= 19045 else ACCENT, "Windows", "build %d" % s["win"]))
        rows.append((OK if s["net"] else BAD, "Internet", "Hugging Face reachable" if s["net"] else
                     "can't reach huggingface.co — models can't download"))
        block = block or not s["net"]
        box = self.card()
        for col, k, v in rows:
            f = tk.Frame(box, bg=PANEL)
            f.pack(fill="x", pady=4)
            tk.Label(f, text="●", fg=col, bg=PANEL, font=("Segoe UI", 11)).pack(side="left")
            tk.Label(f, text=k, fg=FG, bg=PANEL, width=10, anchor="w", font=("Segoe UI Semibold", 10)).pack(side="left", padx=6)
            tk.Label(f, text=v, fg=DIM if col == OK else col, bg=PANEL, anchor="w", justify="left",
                     wraplength=int(560 * self.scale)).pack(side="left")
        if g:
            rec = preset_components("recommended", g["vram_gb"])
            self.text("Recommended for this GPU: " + ",  ".join(COMPONENTS[k][0].split(" — ")[1] for k in COMPONENTS if k in rec)
                      + ".  The video model is tuned for RTX 50-series; other RTX cards with 12 GB+ work, more slowly.",
                      fg=DIM, pad=(4, 0))
        if block:
            self.btn_next.state(["disabled"])
            ttk.Button(self.body, text="Check again", command=lambda: (setattr(self, "sysinfo", None), self.show())).pack(anchor="w", pady=10)

    def apply_preset(self):
        name = self.v_preset.get()
        if name == "custom":
            return
        vram = ((self.sysinfo or {}).get("gpu") or {}).get("vram_gb", 12)
        want = preset_components(name, vram)
        for k, v in self.v_comp.items():
            v.set(k in want)
        self.update_space()

    def page_options(self):
        self.head("Choose what to install", "Pick a set, or tick exactly the models you want")
        f = tk.Frame(self.body, bg=BG)
        f.pack(fill="x")
        tk.Label(f, text="Install to", bg=BG, fg=FG, font=("Segoe UI Semibold", 10)).pack(side="left")
        ttk.Entry(f, textvariable=self.v_dir, width=56).pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(f, text="Browse…", command=self.pick_dir).pack(side="left")
        self.lbl_space = tk.Label(self.body, bg=BG, fg=DIM, anchor="w")
        self.lbl_space.pack(fill="x", pady=(2, 8))

        box = self.card(title="AI models")
        pr = tk.Frame(box, bg=PANEL)
        pr.pack(fill="x", pady=(0, 6))
        for key, label in PRESETS.items():
            ttk.Radiobutton(pr, text=label, value=key, variable=self.v_preset, style="Card.TRadiobutton",
                            command=self.apply_preset).pack(side="left", padx=(0, 14))
        grid = tk.Frame(box, bg=PANEL)
        grid.pack(fill="x")
        for i, (k, (name, desc, _)) in enumerate(COMPONENTS.items()):
            ttk.Checkbutton(grid, text="%s  ·  %.0f GB" % (name, comp_bytes(k) / GB), variable=self.v_comp[k],
                            style="Card.TCheckbutton",
                            command=lambda: (self.v_preset.set("custom"), self.update_space())).grid(row=i, column=0, sticky="w", pady=1)
            tk.Label(grid, text=desc, bg=PANEL, fg=DIM, font=("Segoe UI", 9)).grid(row=i, column=1, sticky="w", padx=10)
        if self.v_preset.get() != "custom":
            self.apply_preset()

        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        eng = self.card(row, title="MUSE · chat + model picker", side="left", expand=True, padx=(0, 10))
        tk.Label(eng, text="The lab's language model: general conversation, prompt building for each render model, "
                           "and picking the right model per request in Auto mode. It never renders — images, video "
                           "and music come from the models above.",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 9), justify="left", wraplength=int(330 * self.scale)).pack(anchor="w", pady=(0, 6))
        installed = ollama_exe()
        for tag, (name, gb) in ENGINES.items():
            extra = "" if not tag else ("  ·  %.1f GB%s" % (gb, "" if installed else " + Ollama"))
            ttk.Radiobutton(eng, text=name + extra, value=tag, variable=self.v_engine, style="Card.TRadiobutton",
                            command=self.update_space).pack(anchor="w")
        opt = self.card(row, title="Options", side="left", expand=True)
        ttk.Checkbutton(opt, text="Desktop shortcut", variable=self.v_desktop, style="Card.TCheckbutton").pack(anchor="w")
        ttk.Checkbutton(opt, text="Start the server at sign-in (phones can always connect)",
                        variable=self.v_auto, style="Card.TCheckbutton").pack(anchor="w")
        ttk.Checkbutton(opt, text="Let phones / TVs on my Wi-Fi connect (firewall rule)",
                        variable=self.v_lan, style="Card.TCheckbutton").pack(anchor="w")

        r = tk.Frame(self.body, bg=BG)
        r.pack(fill="x", pady=(2, 0))
        tk.Label(r, text="Already have ComfyUI models?", bg=BG, fg=DIM).pack(side="left")
        ttk.Entry(r, textvariable=self.v_reuse, width=40).pack(side="left", padx=6)
        ttk.Button(r, text="Pick models folder…", command=self.pick_reuse).pack(side="left")
        self.lbl_found = tk.Label(self.body, bg=BG, fg=OK, anchor="w")
        self.lbl_found.pack(fill="x")
        if not self.v_reuse.get() and not getattr(self, "_scanned", False):
            self._scanned = True
            self.lbl_found.config(text="Looking for AI models already on this PC …", fg=DIM)
            self.after(50, self.auto_detect)
        self.update_space()

    def auto_detect(self):
        best, n, gb = find_existing_models(exclude=self.v_dir.get())
        if not self.lbl_found.winfo_exists():
            return
        if best:
            self.v_reuse.set(best)
            self.lbl_found.config(text="Found %d of %d models already on this PC (%s) — %.0f GB won't be downloaded again."
                                  % (n, len(all_model_files()), best, gb), fg=OK)
        else:
            self.lbl_found.config(text="No existing models found — they'll be downloaded.", fg=DIM)
        self.update_space()

    def pick_dir(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.v_dir.get()) or "C:\\")
        if d:
            d = os.path.normpath(d)
            self.v_dir.set(d if os.path.basename(d).lower() == APP_ID.lower() else os.path.join(d, APP_ID))
            self.update_space()

    def pick_reuse(self):
        d = filedialog.askdirectory(title="Select a ComfyUI 'models' folder")
        if d:
            self.v_reuse.set(os.path.normpath(d))
            self.update_space()

    def need_gb(self):
        reuse = self.v_reuse.get().strip()
        tot = RUNTIME_GB
        for k, v in self.v_comp.items():
            if v.get():
                for rel, _, sz in COMPONENTS[k][2]:
                    if not have_model(reuse, rel, sz):
                        tot += sz / GB
        tag = self.v_engine.get()
        if tag:
            tot += ENGINES[tag][1] + (0 if ollama_exe() else 2)
        return tot

    def update_space(self):
        if not hasattr(self, "lbl_space") or not self.lbl_space.winfo_exists():
            return
        need, free = self.need_gb(), free_gb(self.v_dir.get())
        self.lbl_space.config(text="Needs about %.0f GB  ·  %.0f GB free on that drive" % (need, free),
                              fg=OK if free > need + 5 else BAD)

    def validate_options(self):
        d = self.v_dir.get().strip()
        if not d or not os.path.isabs(d) or len(d) > 60:
            messagebox.showerror(APP, "Choose a short folder path (e.g. D:\\MirMediaLabs).")
            return False
        if self.v_comp["video_ref"].get() and not self.v_comp["video"].get():
            messagebox.showerror(APP, "The reference→video add-on needs the Video model too.")
            return False
        need, free = self.need_gb(), free_gb(d)
        if free < need + 2:
            return messagebox.askyesno(APP, "Only %.0f GB free but about %.0f GB is needed. Continue anyway?" % (free, need))
        return True

    def options(self):
        return {"dir": os.path.normpath(self.v_dir.get().strip()), "gpu": self.sysinfo["gpu"],
                "components": [k for k, v in self.v_comp.items() if v.get()], "engine": self.v_engine.get(),
                "desktop": self.v_desktop.get(), "autostart": self.v_auto.get(), "lan": self.v_lan.get(),
                "reuse": self.v_reuse.get().strip()}

    def page_ready(self):
        self.head("Ready to install", "Check the summary, then press Install")
        o = self.options()
        box = self.card(title="Summary")
        names = [COMPONENTS[k][0] for k in o["components"]] or ["(no models — app + engine only)"]
        for k, v in (("Folder", o["dir"]), ("Models", ",  ".join(names)), ("MUSE", ENGINES.get(o["engine"], (o["engine"],))[0] if o["engine"] else "none"),
                     ("Download", "about %.0f GB" % self.need_gb())):
            f = tk.Frame(box, bg=PANEL)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=k, bg=PANEL, fg=DIM, width=14, anchor="w").pack(side="left")
            tk.Label(f, text=v, bg=PANEL, fg=FG, anchor="w", justify="left", wraplength=int(560 * self.scale)).pack(side="left")
        self.text("Models download %d at a time while the runtime installs, so the two longest jobs overlap. "
                  "You can stop any time — downloads resume where they left off." % PARALLEL_DOWNLOADS, fg=DIM, pad=(4, 0))
        self.btn_next.config(text="Install")

    def page_install(self):
        self.head("Installing", "Feel free to keep using your PC — here's what MIR MEDIA LABS makes")
        self.btn_next.state(["disabled"])
        Showcase(self.body).start().pack(anchor="w", pady=(0, 10))
        self.lbl_step = self.text("Starting …", bold=True, size=11, pad=(0, 2))
        self.pb_all = ttk.Progressbar(self.body, maximum=1000)
        self.pb_all.pack(fill="x", pady=(0, 2))
        self.lbl_file = self.text("", fg=DIM, pad=(0, 6))
        self.lbl_dl = self.text("", bold=True, pad=(4, 2))
        self.pb_dl = ttk.Progressbar(self.body, maximum=1000, style="Dl.Horizontal.TProgressbar")
        self.lbl_dl2 = self.text("", fg=DIM, pad=(2, 4))
        self._log_open = tk.BooleanVar(value=False)
        self.btn_log = ttk.Button(self.body, text="Show details ▾", command=self.toggle_log)
        self.btn_log.pack(anchor="w", pady=(4, 0))
        self.logbox = tk.Text(self.body, bg=PANEL, fg=DIM, relief="flat", font=("Consolas", 9), wrap="none", height=9,
                              highlightthickness=1, highlightbackground=LINE)
        self._ended = False
        self._step = (0, "", 0.0, 0.0)
        self.inst = Installer(self.options(), lambda k, v: self.q.put((k, v)))
        threading.Thread(target=self.inst.run, daemon=True).start()
        self.after(100, self.pump)

    def toggle_log(self):
        if self.logbox.winfo_ismapped():
            self.logbox.pack_forget()
            self.btn_log.config(text="Show details ▾")
        else:
            self.logbox.pack(fill="both", expand=True, pady=(6, 0))
            self.logbox.see("end")
            self.btn_log.config(text="Hide details ▴")

    def pump(self):
        try:
            while True:
                k, v = self.q.get_nowait()
                if k == "log":
                    self.logbox.insert("end", v + "\n")
                    if int(self.logbox.index("end-1c").split(".")[0]) > 1500:
                        self.logbox.delete("1.0", "500.0")
                    self.logbox.see("end")
                elif k == "step":
                    self._step = v
                    self.lbl_step.config(text=v[1])
                    self.pb_all["value"] = v[2] * 1000
                elif k == "overall_sub":
                    self.lbl_step.config(text="%s — %s" % (self._step[1], v))
                elif k == "file":
                    label, have, total, rate = v
                    frac = have / total if total else 0
                    eta = (" · %s left" % self.fmt_eta((total - have) / rate)) if rate > 0 else ""
                    self.lbl_file.config(text="%s   %.2f / %.2f GB%s%s" % (
                        label, have / GB, total / GB, ("   %.0f MB/s" % (rate / 1e6)) if rate else "", eta)
                        if frac < 1 else "")
                elif k == "dl":
                    done, total, bps, fdone, ftotal = v
                    if not self.pb_dl.winfo_ismapped():
                        self.pb_dl.pack(fill="x", after=self.lbl_dl)
                    self.pb_dl["value"] = done / total * 1000 if total else 1000
                    self.lbl_dl.config(text="AI models — %d of %d files" % (fdone, ftotal) if fdone < ftotal
                                       else "AI models — all %d downloaded" % ftotal)
                    eta = (" · about %s left" % self.fmt_eta((total - done) / bps)) if bps > 0 and done < total else ""
                    self.lbl_dl2.config(text="%.1f / %.1f GB%s%s   (%d at a time)" % (
                        done / GB, total / GB, ("  ·  %.0f MB/s" % (bps / 1e6)) if bps else "", eta, PARALLEL_DOWNLOADS))
                    if self._step[1].startswith("Finishing model"):
                        self.pb_all["value"] = (self._step[2] + self._step[3] * (done / total if total else 1)) * 1000
                elif k == "done":
                    self._ended = True
                    if self.update_mode:                   # relaunch the updated app and get out of the way
                        self.lbl_step.config(text="Updated to v%s — restarting MIR MEDIA LABS …" % VERSION)
                        self.launch(server_only=True)
                        self.after(2500, self.destroy)
                        return
                    self.idx = 5
                    self.show()
                    return
                elif k == "failed":
                    self._ended = True
                    self.lbl_step.config(text="Stopped: " + v[:300], fg=BAD)
                    if not self.logbox.winfo_ismapped():
                        self.toggle_log()
                    self.btn_next.config(text="Retry")
                    self.btn_next.state(["!disabled"])
                    self.btn_next.config(command=self.retry)
                    return
        except queue.Empty:
            pass
        self.after(120, self.pump)

    @staticmethod
    def fmt_eta(sec):
        m = int(sec // 60)
        if m < 1:
            return "under a minute"
        return "%d h %02d min" % (m // 60, m % 60) if m >= 60 else "%d min" % m

    def retry(self):
        self.btn_next.config(command=self.next)
        self.idx = 4
        self.show()

    def page_finish(self):
        self.head("You're all set", "MIR MEDIA LABS is installed")
        self.btn_cancel.pack_forget()
        o = self.options()
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        left = tk.Frame(row, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self.text("Open it from the desktop or the Start menu — and pin it to the taskbar if you like.", size=11, bold=True,
                  parent=left, wrap=430)
        self.text("The first render of each model loads it into memory and takes longer; after that it's quick. "
                  "Type an idea in the chat, or tap a Skill.", fg=DIM, parent=left, wrap=430)
        ip = run_quiet(["powershell", "-NoProfile", "-Command",
                        "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -eq 'Dhcp' } | "
                        "Select-Object -First 1).IPAddress"])
        self.v_launch = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Open MIR MEDIA LABS now", variable=self.v_launch).pack(anchor="w", pady=(4, 12))
        tips = self.card(left, title="Things to try first")
        for cmd, what in (("/video a lighthouse at dusk, slow crane up --8s", "a video with sound"),
                          ("/song upbeat synthwave about city lights --90s", "a full vocal song"),
                          ("/skill product a red sneaker", "a studio product shot"),
                          ("/pipe musicvideo neon city synthwave", "song → cover art → music video"),
                          ("/help", "every command, skill and pipeline")):
            r = tk.Frame(tips, bg=PANEL)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=cmd, bg=PANEL, fg=ACCENT, font=("Consolas", 9)).pack(side="left")
            tk.Label(r, text="  " + what, bg=PANEL, fg=DIM, font=("Segoe UI", 9)).pack(side="left")

        # mobile companion: the same studio on phone + Android TV
        mob = self.card(row, title="Mobile companion · phone + TV", side="left")
        try:
            hi = float(self.tk.call("tk", "scaling")) / (96 / 72) >= 1.4
            self._qr = tk.PhotoImage(file=resource(os.path.join("showcase", "qr_%s.png" % ("2x" if hi else "1x"))))
            tk.Label(mob, image=self._qr, bg=PANEL).pack(anchor="w", pady=(2, 6))
        except tk.TclError:
            pass
        self.text("Scan to get the free Android app (one APK for phones and Android TV).", parent=mob, bg=PANEL,
                  wrap=300, pad=(0, 4))
        if o["lan"] and ip:
            self.text("Then connect it to  http://%s:5400  with a key from the People menu in the app." % ip,
                      parent=mob, bg=PANEL, fg=DIM, wrap=300, pad=(0, 2))
        else:
            self.text("Then connect it to this PC's address (port 5400) with a key from the People menu.",
                      parent=mob, bg=PANEL, fg=DIM, wrap=300, pad=(0, 2))
        self.btn_next.config(text="Finish")
        self.btn_back.state(["disabled"])

    def launch(self, server_only=False):
        exe = app_exe(self.options()["dir"])
        if os.path.isfile(exe):
            # clean environment: the one-file wizard's own variables must not leak into the app
            # (they made the app think it was the setup, so pinning it pinned the wizard)
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("NUITKA", "_MEI", "TCL_", "TK_"))}
            subprocess.Popen([exe] + (["--server-only"] if server_only else []), cwd=os.path.dirname(exe),
                             creationflags=0x00000008, env=env)

    def finish(self):
        if getattr(self, "v_launch", None) and self.v_launch.get():
            self.launch()
        self.destroy()


# ─────────────────────────────── uninstall ───────────────────────────────
def uninstall():
    root = tk.Tk()
    root.withdraw()
    d = registry_install_dir() or os.path.dirname(self_exe())
    if not os.path.isfile(os.path.join(d, "mml_config.json")):
        messagebox.showerror(APP, "No MIR MEDIA LABS install found.")
        return
    if not messagebox.askyesno(APP, "Remove MIR MEDIA LABS from\n%s ?\n\nThis deletes the app, engine and models." % d):
        return
    keep = messagebox.askyesno(APP, "Keep your library (renders, references, settings)?\n\n"
                                    "Yes = keep the data folder   ·   No = delete everything")
    Installer({"dir": d}, lambda k, v: None).stop_running()
    for lnk in (LNK_START, LNK_STARTUP, LNK_DESKTOP):
        try:
            os.remove(lnk)
        except OSError:
            pass
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if (keep and name == "data") or name.lower() == "mirmedialabs-setup.exe":
            continue
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else _rm(p)
    # this exe is still running → delete it (and the folder if empty) once we exit
    subprocess.Popen('cmd /c ping -n 3 127.0.0.1 >nul & del /f /q "%s" & rmdir "%s"'
                     % (os.path.join(d, "MirMediaLabs-Setup.exe"), d), creationflags=NO_WINDOW | 0x00000008)
    messagebox.showinfo(APP, "MIR MEDIA LABS was removed.%s\nOllama (if installed) stays — remove it from "
                             "Settings → Apps if you don't need it." % ("\nYour library is kept in " + os.path.join(d, "data")
                                                                       if keep else ""))


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:   # own taskbar identity: the setup must never group (or get pinned) as the app itself
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MirCorp.MirMediaLabs.Setup")
    except Exception:
        pass
    if "--uninstall" in sys.argv:
        uninstall()
    elif "--update" in sys.argv:
        a = sys.argv
        d = a[a.index("--dir") + 1] if "--dir" in a and a.index("--dir") + 1 < len(a) else registry_install_dir()
        Wizard(update_dir=d).mainloop() if d and read_config(d) else Wizard().mainloop()
    else:
        Wizard().mainloop()
