#!/usr/bin/env python3
"""MIR MEDIA LABS — Linux engine installer (stdlib only; run by install.sh --engine).

Sets up everything the studio renders with, inside the install folder:
  <dir>/runtime/       uv + a managed Python 3.13 venv (the engine's PyTorch lives here)
  <dir>/engine/ComfyUI headless ComfyUI (pinned release), started on demand by the server
  models               the chosen components, downloaded from Hugging Face (resumable)
  Ollama               system install via ollama.com/install.sh (asks for sudo) + the MUSE model
and writes the engine paths, GPU env and model swaps into <dir>/mml_config.json.

GPU support: NVIDIA (CUDA wheels) or AMD RDNA2+ (ROCm wheels). Minimum 12 GB VRAM, 32 GB RAM.

  python3 engine_setup.py --dir ~/.local/share/MirMediaLabs [--components video,music,image,ace]
                          [--muse llama3.1:8b|none] [--no-ollama] [--skip-models] [--yes]
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

# keep in step with installer/setup_wizard.py (COMFY_TAG, PY_VER, COMPONENTS, MUSE_TAG)
COMFY_TAG = "0.38.2"
PY_VER = "3.13"
UV_URL = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
COMFY_URL = "https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v%s.tar.gz" % COMFY_TAG
OLLAMA_SH = "https://ollama.com/install.sh"
MUSE_TAG = "llama3.1:8b"
ROCM_INDEX = "https://download.pytorch.org/whl/rocm6.4"
CUDA_BACKEND = "cu128"
GB = 1024 ** 3
HF = "https://huggingface.co/"
H3, M3, QI, ACE = (HF + "Comfy-Org/MiniMax-H3/resolve/main/", HF + "Comfy-Org/MiniMax-Music-3/resolve/main/",
                   HF + "Comfy-Org/Qwen-Image-2.1/resolve/main/",
                   HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/")
STYLES = ["art_is_explosion", "blooming_flowers", "bullet_time", "dark_magic", "fire_breath", "four_seasons",
          "kiss_camera", "spiral_ascent", "storm_magic", "truman_show"]
NVFP4_ONLY = {"text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"}   # needs NVIDIA Blackwell (RTX 50)
# portable stand-ins for NVFP4 files: same model, int8_convrot (native in ComfyUI on NVIDIA + AMD RDNA3/4;
# RDNA2 gets the INT8 kernel node below). Bigger, so on 12 GB cards it encodes from system RAM.
PORTABLE = {"text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors":
            ("text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors", H3, 27141342152)}
# RDNA2: ROCm's hipBLASLt has no int8 GEMM there → int8 models fail with HIPBLAS_STATUS_INVALID_VALUE
INT8_ROCM_NODE = ("ComfyUI-INT8-Fast-ROCM", "https://github.com/patientx/ComfyUI-INT8-Fast-ROCM")
COMPONENTS = {
    "video": [
        ("diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", H3, 20970379616),
        ("text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", H3, 15687142551),
        ("vae/minimax_h3_video_vae_int8_convrot.safetensors", H3, 2811065184),
        ("vae/minimax_h3_audio_vae_fp32.safetensors", H3, 605254808),
        ("loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", H3, 1956192992),
        ("loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", H3, 1956193000),
    ] + [("embeddings/minimaxh3_%s.safetensors" % s, H3, 0) for s in STYLES],
    "video_ref": [
        ("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", H3, 20970379616),
        ("loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", H3, 1956193000),
    ],
    "music": [
        ("diffusion_models/minimax_music3_dit_fp16.safetensors", M3, 4914197682),
        ("text_encoders/minimax_music3_text_encoder_pruned_int8_convrot.safetensors", M3, 9196611886),
        ("vae/minimax_music3_dav.safetensors", M3, 216696128),
    ],
    "image": [
        ("diffusion_models/qwen_image_2.1_int8_convrot.safetensors", QI, 7256783064),
        ("text_encoders/qwen3vl_8b_int8_convrot.safetensors", QI, 9350798360),
        ("vae/qwen_image_2.1_vae_bf16.safetensors", QI, 675509688),
    ],
    "ace": [
        ("diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors", ACE, 9974719892),
        ("text_encoders/qwen_0.6b_ace15.safetensors", ACE, 1191588248),
        ("text_encoders/qwen_4b_ace15.safetensors", ACE, 8379154232),
        ("vae/ace_1.5_vae.safetensors", ACE, 337431732),
    ],
}
# RDNA chips ROCm doesn't ship kernels for, mapped to the nearest supported ISA (the usual community override)
GFX_OVERRIDE = {"gfx1031": "10.3.0", "gfx1032": "10.3.0", "gfx1034": "10.3.0", "gfx1035": "10.3.0",
                "gfx1036": "10.3.0", "gfx1101": "11.0.0", "gfx1102": "11.0.0", "gfx1103": "11.0.0"}
UA = {"User-Agent": "MirMediaLabs-EngineSetup"}


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    print(line.encode(enc, "replace").decode(enc), flush=True)        # C/POSIX locales can't print arrows


def run(cmd, env=None, cwd=None, check=True):
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, env=env, cwd=cwd)
    if check and r.returncode != 0:
        raise SystemExit("command failed (%d): %s" % (r.returncode, cmd[0]))
    return r.returncode


def quiet(cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


# ── system check ────────────────────────────────────────────────────────────
def gpu_info():
    """{'vendor','name','vram_gb', 'gfx'?} for the biggest GPU, or None."""
    if shutil.which("nvidia-smi"):
        out = quiet(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        if out:
            name, mem, drv = [x.strip() for x in out.splitlines()[0].split(",")[:3]]
            return {"vendor": "nvidia", "name": name, "vram_gb": round(float(mem) / 1024, 1), "driver": drv}
    best = None
    for dev in glob.glob("/sys/class/drm/card*/device"):
        try:
            if open(os.path.join(dev, "vendor")).read().strip() != "0x1002":
                continue
            vram = int(open(os.path.join(dev, "mem_info_vram_total")).read())
        except (OSError, ValueError):
            continue
        if not best or vram > best["vram"]:
            name = ""
            try:
                name = open(os.path.join(dev, "product_name")).read().strip()
            except OSError:
                pass
            best = {"vendor": "amd", "name": name or "AMD GPU", "vram": vram, "vram_gb": round(vram / GB, 1)}
    if best:
        m = re.search(r"\bgfx1[0-9a-f]{3}\b", quiet(["rocminfo"]) or "")
        best["gfx"] = m.group(0) if m else ""
        best.pop("vram", None)
    return best


def ram_gb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024 / 1024, 1)
    return 0


def free_gb(path):
    while not os.path.exists(path):
        path = os.path.dirname(path)
    return shutil.disk_usage(path).free / GB


# ── downloads ───────────────────────────────────────────────────────────────
def download(url, dest, size=0, label=None):
    """Resumable download with a one-line progress readout."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isfile(dest) and (not size or os.path.getsize(dest) == size):
        return dest
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    for attempt in range(6):
        try:
            hdr = dict(UA, **({"Range": "bytes=%d-" % have} if have else {}))
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
                if have and r.status != 206:
                    have = 0                                   # server ignored the range → restart
                total = size or (have + int(r.headers.get("Content-Length") or 0))
                t0, last = time.time(), 0.0
                with open(part, "ab" if have else "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        if time.time() - last > 1 and sys.stdout.isatty():
                            last = time.time()
                            pct = 100.0 * have / total if total else 0
                            rate = have / max(1e-3, last - t0) / 1e6
                            print("\r  %s  %5.1f%%  %.1f/%.1f GB  %.0f MB/s   " % (
                                label or os.path.basename(dest), pct, have / GB, total / GB, rate), end="", flush=True)
            if sys.stdout.isatty():
                print()
            if size and have != size:
                raise IOError("size mismatch (%d != %d)" % (have, size))
            os.replace(part, dest)
            return dest
        except Exception as e:
            log("  retry %d for %s: %s" % (attempt + 1, label or url, e))
            time.sleep(min(30, 3 * (attempt + 1)))
            have = os.path.getsize(part) if os.path.isfile(part) else 0
    raise SystemExit("download failed: " + url)


# ── steps ───────────────────────────────────────────────────────────────────
class Setup:
    def __init__(self, a, gpu):
        self.a, self.gpu = a, gpu
        self.dir = os.path.abspath(os.path.expanduser(a.dir))
        self.rt = os.path.join(self.dir, "runtime")
        self.venv = os.path.join(self.rt, "venv")
        self.py = os.path.join(self.venv, "bin", "python")
        self.uv = os.path.join(self.rt, "uv")
        self.engine = os.path.join(self.dir, "engine")
        self.comfy = os.path.join(self.engine, "ComfyUI")
        self.models = os.path.join(self.comfy, "models")
        self.cache = os.path.join(self.rt, "cache")

    def env(self):
        e = dict(os.environ, UV_PYTHON_INSTALL_DIR=os.path.join(self.rt, "python"), UV_CACHE_DIR=self.cache,
                 UV_LINK_MODE="copy", UV_HTTP_TIMEOUT="300", PYTHONUTF8="1")
        e.update(self.gpu_env())
        return e

    def gpu_env(self):
        g = self.gpu or {}
        if g.get("vendor") == "amd" and g.get("gfx") in GFX_OVERRIDE:
            return {"HSA_OVERRIDE_GFX_VERSION": GFX_OVERRIDE[g["gfx"]]}
        return {}

    def python(self):
        if not os.path.isfile(self.uv):
            tgz = download(UV_URL, os.path.join(self.cache, "uv.tar.gz"), label="uv")
            with tarfile.open(tgz) as t:
                m = next(m for m in t.getmembers() if m.name.endswith("/uv") or m.name == "uv")
                with t.extractfile(m) as s, open(self.uv, "wb") as d:
                    shutil.copyfileobj(s, d)
            os.chmod(self.uv, 0o755)
        if not os.path.isfile(self.py):
            run([self.uv, "venv", self.venv, "--python", PY_VER, "--managed-python"], env=self.env())

    def comfyui(self):
        verf = os.path.join(self.comfy, "comfyui_version.py")
        if os.path.isfile(verf) and COMFY_TAG in open(verf, encoding="utf-8").read():
            log("ComfyUI %s already installed" % COMFY_TAG)
            return
        tgz = download(COMFY_URL, os.path.join(self.cache, "comfyui-%s.tar.gz" % COMFY_TAG), label="ComfyUI")
        tmp = os.path.join(self.engine, "_new")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        with tarfile.open(tgz) as t:
            safe = [m for m in t.getmembers() if not (m.name.startswith("/") or ".." in m.name.split("/"))]
            t.extractall(tmp, members=safe)
        src = os.path.join(tmp, os.listdir(tmp)[0])
        if os.path.isdir(self.comfy):                          # upgrade: keep downloaded models
            if os.path.isdir(self.models):
                shutil.rmtree(os.path.join(src, "models"), ignore_errors=True)
                shutil.move(self.models, os.path.join(src, "models"))
            shutil.rmtree(self.comfy, ignore_errors=True)
        shutil.move(src, self.comfy)
        shutil.rmtree(tmp, ignore_errors=True)
        for d in ("shared/input", "shared/output"):
            os.makedirs(os.path.join(self.engine, d), exist_ok=True)

    def packages(self):
        base = [self.uv, "pip", "install", "--python", self.py]
        v = (self.gpu or {}).get("vendor")
        if v == "amd":
            log("PyTorch backend: ROCm (%s)" % ROCM_INDEX.rsplit("/", 1)[-1])
            run(base + ["--index-url", ROCM_INDEX, "--extra-index-url", "https://pypi.org/simple",
                        "torch", "torchvision", "torchaudio"], env=self.env())
        elif v == "nvidia":
            log("PyTorch backend: CUDA (%s)" % CUDA_BACKEND)
            run(base + ["--torch-backend", CUDA_BACKEND, "torch", "torchvision", "torchaudio"], env=self.env())
        else:
            log("PyTorch backend: CPU (no supported GPU found — renders will be very slow)")
            run(base + ["--torch-backend", "cpu", "torch", "torchvision", "torchaudio"], env=self.env())
        # ComfyUI deps; keep the GPU torch we just installed
        req = os.path.join(self.comfy, "requirements.txt")
        reqs = [l for l in open(req).read().splitlines() if not re.match(r"\s*torch(vision|audio)?\b", l)]
        tmp = os.path.join(self.cache, "comfy-req.txt")
        open(tmp, "w").write("\n".join(reqs) + "\n")
        run(base + ["-r", tmp, "imageio-ffmpeg"], env=self.env())

    def gpu_check(self):
        out = quiet([self.py, "-c", "import torch;print(torch.__version__, torch.cuda.is_available(), "
                                    "torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"], 300)
        log("PyTorch check: " + (out or "no output"))
        if (self.gpu or {}).get("vendor") in ("amd", "nvidia") and "True" not in out:
            hint = ("install ROCm 6.4+ (amdgpu-install --usecase=rocm) and add your user to the 'render' and "
                    "'video' groups, then log out/in" if self.gpu["vendor"] == "amd" else "update the NVIDIA driver")
            raise SystemExit("PyTorch can't see the GPU — %s, then re-run with --engine." % hint)

    def ollama(self):
        tag = self.a.muse
        if self.a.no_ollama or tag == "none":
            return
        if not shutil.which("ollama"):
            log("Ollama isn't installed — running the official installer (it asks for your sudo password)")
            if not self.a.yes and input("Install Ollama system-wide now? [Y/n] ").strip().lower() in ("n", "no"):
                log("skipped Ollama — MUSE chat/Auto mode stay off until it's installed")
                return
            sh = download(OLLAMA_SH, os.path.join(self.cache, "ollama-install.sh"), label="Ollama installer")
            run(["sh", sh])
        for i in range(30):
            try:
                urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3).read()
                break
            except Exception:
                if i == 3:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
                time.sleep(2)
        else:
            raise SystemExit("Ollama didn't start (systemctl status ollama)")
        run(["ollama", "pull", tag])
        prefs_f = os.path.join(self.dir, "data", "prefs.json")
        prefs = {}
        try:
            prefs = json.load(open(prefs_f, encoding="utf-8"))
        except (OSError, ValueError):
            pass
        prefs["engine_model"] = tag
        os.makedirs(os.path.dirname(prefs_f), exist_ok=True)
        json.dump(prefs, open(prefs_f, "w", encoding="utf-8"), indent=1)

    def model_list(self):
        files = [f for k in self.a.components for f in COMPONENTS[k]]
        if not self.needs_portable():
            return files
        out = []
        for f in files:
            if f[0] in PORTABLE:
                log("NOTE: %s needs NVIDIA Blackwell -> using %s" % (os.path.basename(f[0]),
                                                                   os.path.basename(PORTABLE[f[0]][0])))
                f = PORTABLE[f[0]]
            out.append(f)
        return out

    def portable_overrides(self):
        """mml_config model_overrides: shipped NVFP4 name -> the portable file actually downloaded."""
        if not self.needs_portable():
            return {}
        return {os.path.basename(k): os.path.basename(v[0]) for k, v in PORTABLE.items()}

    def rdna2(self):
        g = self.gpu or {}
        return g.get("vendor") == "amd" and g.get("gfx", "").startswith("gfx103")

    def custom_nodes(self):
        if not self.rdna2():
            return
        name, url = INT8_ROCM_NODE
        dest = os.path.join(self.comfy, "custom_nodes", name)
        if os.path.isdir(dest):
            log("%s already installed" % name)
            return
        if not shutil.which("git"):
            raise SystemExit("git is needed to add %s for your RDNA2 card (int8 models)" % name)
        log("RDNA2 card: adding community node %s (int8 kernels; ROCm lacks them on RDNA2)" % name)
        run(["git", "clone", "--depth", "1", url, dest])
        req = os.path.join(dest, "requirements.txt")
        if os.path.isfile(req):
            run([self.uv, "pip", "install", "--python", self.py, "-r", req], env=self.env())

    def needs_portable(self):
        g = self.gpu or {}
        if g.get("vendor") != "nvidia":
            return True
        return not re.search(r"RTX\s*5\d{2}|RTX PRO|B\d{3}|GB\d{3}", g.get("name", ""))

    def cfg_overrides(self):
        return (read_config(self.dir).get("model_overrides") or {})

    def models_dl(self):
        if self.a.skip_models:
            return
        todo = [f for f in self.model_list()
                if not (os.path.isfile(os.path.join(self.models, f[0])) and
                        (not f[2] or os.path.getsize(os.path.join(self.models, f[0])) == f[2]))]
        need = sum(s for _, _, s in todo) / GB
        if need and free_gb(self.models) < need + 5:
            raise SystemExit("not enough disk: need %.0f GB for models, %.0f GB free" % (need + 5, free_gb(self.models)))
        log("%d model files to download (%.1f GB)" % (len(todo), need))
        for i, (rel, base, size) in enumerate(sorted(todo, key=lambda x: -x[2]), 1):
            download(base + rel, os.path.join(self.models, rel), size, "[%d/%d] %s" % (i, len(todo), rel.split("/")[-1]))

    def write_config(self):
        cfg = read_config(self.dir)
        vram = (self.gpu or {}).get("vram_gb", 0)
        args = list(cfg.get("comfy_args") or [])
        if vram and vram < 16 and "--lowvram" not in args and "--normalvram" not in args:
            args.append("--lowvram")                           # 12 GB cards: stream weights from system RAM
        env = dict(cfg.get("comfy_env") or {})
        env.update(self.gpu_env())
        if (self.gpu or {}).get("vendor") == "amd":
            env.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")
        ff = quiet([self.py, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], 60)
        cfg.update({"comfy_root": self.engine, "comfy_python": self.py,
                    "comfy_shared": os.path.join(self.engine, "shared"), "comfy_model_paths": None,
                    "comfy_args": args, "comfy_env": env, "gpu": self.gpu,
                    "ffmpeg": cfg.get("ffmpeg") or (ff.splitlines()[-1] if ff else None),
                    "components": self.a.components, "engine": None if self.a.muse == "none" else self.a.muse,
                    "engine_installed": time.strftime("%Y-%m-%d %H:%M")})
        overrides = dict(cfg.get("model_overrides") or {})
        for k, v in self.portable_overrides().items():
            overrides.setdefault(k, v)                         # user's own swaps win
        cfg["model_overrides"] = overrides
        cfg.setdefault("port", 5400)
        json.dump(cfg, open(os.path.join(self.dir, "mml_config.json"), "w", encoding="utf-8"), indent=1)
        log("wrote %s" % os.path.join(self.dir, "mml_config.json"))


def read_config(d):
    try:
        return json.load(open(os.path.join(d, "mml_config.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def default_components(vram):
    if vram >= 24:
        return list(COMPONENTS)
    if vram >= 11.5:
        return ["video", "music", "image", "ace"]
    return ["music", "image", "ace"]


def main():
    ap = argparse.ArgumentParser(description="MIR MEDIA LABS engine setup (Linux)")
    ap.add_argument("--dir", default=os.path.join(os.environ.get("XDG_DATA_HOME") or
                                                  os.path.expanduser("~/.local/share"), "MirMediaLabs"))
    ap.add_argument("--components", help="comma list of: " + ",".join(COMPONENTS))
    ap.add_argument("--muse", default=MUSE_TAG, help="Ollama model for MUSE, or 'none'")
    ap.add_argument("--no-ollama", action="store_true")
    ap.add_argument("--skip-models", action="store_true")
    ap.add_argument("--yes", "-y", action="store_true", help="don't ask")
    a = ap.parse_args()

    if platform.machine() != "x86_64":
        raise SystemExit("x86_64 only")
    gpu, ram = gpu_info(), ram_gb()
    log("GPU: %s" % (("%s %s · %.1f GB VRAM%s" % (gpu["vendor"].upper(), gpu["name"], gpu["vram_gb"],
                                                   (" · " + gpu["gfx"]) if gpu.get("gfx") else "")) if gpu else "none found"))
    log("RAM: %.1f GB" % ram)
    if not gpu or gpu["vram_gb"] < 11.5:
        log("WARNING: below the 12 GB VRAM minimum — video is disabled, other models may be slow")
    if ram < 30:
        log("WARNING: below the 32 GB RAM minimum — low-VRAM offloading needs system RAM")
    a.components = ([c.strip() for c in a.components.split(",") if c.strip()] if a.components
                    else default_components(gpu["vram_gb"] if gpu else 0))
    bad = [c for c in a.components if c not in COMPONENTS]
    if bad:
        raise SystemExit("unknown component(s): %s" % ", ".join(bad))
    log("components: %s" % ", ".join(a.components))

    s = Setup(a, gpu)
    os.makedirs(s.cache, exist_ok=True)
    if "video" in a.components and s.needs_portable() and ram < 40:
        log("WARNING: video on this GPU encodes prompts with a 27 GB model from system RAM; with %.0f GB RAM "
            "close other apps while rendering video (48 GB+ recommended)" % ram)
    for step in (s.python, s.comfyui, s.packages, s.custom_nodes, s.gpu_check, s.write_config, s.ollama,
                 s.models_dl):
        log("== " + step.__name__)
        step()
    shutil.rmtree(s.cache, ignore_errors=True)
    log("Engine ready. Start MIR MEDIA LABS — ComfyUI starts headless on 127.0.0.1:8188 when a render runs.")


if __name__ == "__main__":
    main()
