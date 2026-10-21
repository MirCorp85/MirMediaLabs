"""MIR MEDIA LABS — setup wizard for a cloned repository (Windows; run by Setup.bat at the repo root).

Turns a fresh `git clone` into a working studio, inside the clone:
  runtime\\app            the app's own Python venv (Flask server + yt-dlp + cloud-brain SDKs)
  runtime\\venv           the render engine's Python 3.13 + PyTorch CUDA (managed by uv)
  engine\\ComfyUI         headless ComfyUI (pinned release) + the models you pick
  Ollama + MirAI          optional: chat, prompt building, Auto-mode model picker (never renders)
  mml_config.json        engine paths for the server (machine-specific, never committed)

It reuses the engine steps of the Windows installer (installer/setup_wizard.py), so a source install and a
Setup.exe install end up identical. Re-run it any time to add models or repair: finished downloads are kept.

  Setup.bat                      guided setup (asks a few questions)
  Setup.bat --yes                recommended choices for this PC, no questions
  Setup.bat --components image,ace --engine none --no-shortcuts
"""
import argparse
import os
import subprocess
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def _stub_tk():
    """setup_wizard builds its GUI on tkinter; this wizard never opens a window, so a Python without tk still works."""
    class _Any:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, _n):
            return _Any

    mod = types.ModuleType("tkinter")
    mod.__getattr__ = lambda _n: _Any
    for name in ("tkinter", "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk"):
        sys.modules[name] = mod
    mod.filedialog = mod.messagebox = mod.ttk = mod


try:
    import tkinter  # noqa: F401
except ImportError:
    _stub_tk()

import setup_wizard as W  # noqa: E402

APP_VENV = os.path.join(ROOT, "runtime", "app")
APP_PY = os.path.join(APP_VENV, "Scripts", "python.exe")
START_BAT = os.path.join(ROOT, "Start-MirMediaLabs.bat")


# ── console helpers ──────────────────────────────────────────────────────────────────────────────────────────
os.system("")                                       # turn on ANSI colours in the Windows console
C = {"acc": "\033[38;5;214m", "dim": "\033[2m", "ok": "\033[32m", "bad": "\033[31m", "b": "\033[1m", "x": "\033[0m"}


def say(msg="", c=None):
    print((C[c] + msg + C["x"]) if c else msg, flush=True)


def ask(q, default=True):
    if ARGS.yes:
        return default
    a = input("%s %s " % (q, "[Y/n]" if default else "[y/N]")).strip().lower()
    return default if not a else a.startswith("y")


def choose(q, options, default):
    """options: [(key, label)] → key."""
    if ARGS.yes:
        return default
    say(q, "b")
    for i, (k, lab) in enumerate(options, 1):
        say("  %d) %s%s" % (i, lab, "  (default)" if k == default else ""))
    while True:
        a = input("Pick 1-%d [Enter = default]: " % len(options)).strip()
        if not a:
            return default
        if a.isdigit() and 1 <= int(a) <= len(options):
            return options[int(a) - 1][0]


def gb(n):
    return "%.1f GB" % (n / W.GB)


# ── the installer, in source-checkout mode ───────────────────────────────────────────────────────────────────
class SourceInstaller(W.Installer):
    """W.Installer with the compiled-app steps swapped: no payload to unpack, no registry entry; the app runs from
    server/ on its own small venv, and shortcuts point at Start-MirMediaLabs.bat."""

    def steps(self):
        steps = super().steps()
        steps[0] = ("App packages (server)", self.step_app, 2)
        if ARGS.no_shortcuts:
            self.o["desktop"] = self.o["autostart"] = False
        return steps

    def step_app(self):
        for d in ("data", "data/logs", "engine/shared/input", "engine/shared/output"):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        self.step_python()                            # uv + the engine venv (idempotent; the next step skips)
        if not os.path.isfile(APP_PY):
            self.sh([self.uv, "venv", APP_VENV, "--python", W.PY_VER, "--managed-python"], retries=3)
        self.sh([self.uv, "pip", "install", "--python", APP_PY, "-r", os.path.join(self.dir, "requirements.txt")],
                retries=3)

    def shortcuts(self):
        ico = os.path.join(self.dir, "MirMediaLabs.ico")
        links = [(W.LNK_START, "")]
        if self.o.get("desktop"):
            links.append((W.LNK_DESKTOP, ""))
        if self.o.get("autostart"):
            links.append((W.LNK_STARTUP, "--server-only"))
        elif os.path.exists(W.LNK_STARTUP):
            os.remove(W.LNK_STARTUP)
        for path, extra in links:
            ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{t}';"
                  "$s.Arguments='{x}';$s.WorkingDirectory='{w}';$s.IconLocation='{i}';$s.WindowStyle=7;$s.Save()").format(
                lnk=path.replace("'", "''"), t=START_BAT.replace("'", "''"), x=extra,
                w=self.dir.replace("'", "''"), i=ico.replace("'", "''"))
            W.run_quiet(["powershell", "-NoProfile", "-Command", ps])

    def register(self):
        pass                                          # a clone is not an installed program (no Apps & features entry)


# ── progress printer ─────────────────────────────────────────────────────────────────────────────────────────
class Printer:
    def __init__(self):
        self.lock = threading.Lock()
        self.line = False
        self.last = 0.0
        self.result = None
        self.done = threading.Event()

    def _bar(self, text):
        with self.lock:
            sys.stdout.write("\r" + text[:118].ljust(118))
            sys.stdout.flush()
            self.line = True

    def _end(self):
        if self.line:
            sys.stdout.write("\n")
            self.line = False

    def __call__(self, kind, v):
        if kind == "step":
            i, name, *_ = v
            with self.lock:
                self._end()
            if name != "Done":
                say("\n[%d] %s" % (i + 1, name), "acc")
        elif kind == "log":
            if ARGS.verbose or "!!" in v:
                with self.lock:
                    self._end()
                    print(C["dim"] + v + C["x"], flush=True)
        elif kind == "dl":
            done, total, bps, nf, tf = v
            if time.time() - self.last > 0.5 or done >= total:
                self.last = time.time()
                eta = (total - done) / bps if bps else 0
                self._bar("  models  %s / %s  ·  %d/%d files  ·  %s/s%s" % (
                    gb(done), gb(total), nf, tf, gb(bps), ("  ·  ~%d min left" % (eta / 60 + 1)) if eta else ""))
        elif kind == "file":
            label, have, total, rate = v
            if time.time() - self.last > 0.5 or have >= total:
                self.last = time.time()
                self._bar("  %s  %s / %s" % (label[:50], gb(have), gb(total)) if total > 1 else "  " + label)
        elif kind in ("done", "failed"):
            with self.lock:
                self._end()
            self.result = (kind, v)
            self.done.set()


# ── wizard ───────────────────────────────────────────────────────────────────────────────────────────────────
def main():
    say("\n  MIR MEDIA LABS — setup from source\n", "acc")
    say("  Installs into: %s" % ROOT, "dim")
    if os.name != "nt":
        say("This wizard is for Windows. On Linux run:  ./setup.sh", "bad")
        return 2

    say("\nChecking this PC …")
    gpu = W.gpu_info()
    if not gpu:
        say("  No NVIDIA GPU found (nvidia-smi). MIR MEDIA LABS renders on an NVIDIA GPU with 8 GB+ VRAM.", "bad")
        if not ask("Continue anyway?", False):
            return 1
        gpu = {"name": "unknown", "vram_gb": 0, "driver": "580"}
    else:
        say("  GPU   %s · %.0f GB VRAM · driver %s" % (gpu["name"], gpu["vram_gb"], gpu["driver"]))
    ram, _commit = W.ram_gb()
    say("  RAM   %.0f GB%s" % (ram, "" if ram >= 32 else "   (32 GB+ recommended for video)"))
    free = W.free_gb(ROOT)
    say("  Disk  %.0f GB free on %s" % (free, os.path.splitdrive(ROOT)[0] or ROOT))
    ok, why = W.net_check()
    if not ok:
        say("  Can't reach huggingface.co (%s) — models can't download." % why, "bad")
        if not ask("Continue anyway?", False):
            return 1

    # models
    if ARGS.components is not None:
        comps = [c for c in ARGS.components.split(",") if c in W.COMPONENTS]
    else:
        rec = W.preset_components("recommended", gpu.get("vram_gb") or 0)
        pick = choose("\nWhich models?", [("recommended", "Recommended for your GPU: " + ", ".join(sorted(rec))),
                                         ("all", "Everything"), ("light", "Light — images + beats"),
                                         ("custom", "Let me pick one by one"), ("none", "None for now (add later)")],
                      "recommended")
        if pick == "custom":
            comps = [k for k, (lab, desc, files) in W.COMPONENTS.items()
                     if ask("  %s — %s (%s)?" % (lab, desc, gb(W.comp_bytes(k))), k in rec)]
        elif pick == "none":
            comps = []
        else:
            comps = sorted(W.preset_components(pick, gpu.get("vram_gb") or 0))

    # reuse models already on this PC
    reuse = ARGS.reuse or ""
    if comps and not reuse:
        say("\nLooking for ComfyUI models already on this PC …", "dim")
        best, n, have_gb = W.find_existing_models(exclude=ROOT)
        if best and ask("Found %d model files (%.0f GB) in %s — use them instead of downloading?" % (n, have_gb, best)):
            reuse = best

    # MirAI engine
    if ARGS.engine is not None:
        engine = "" if ARGS.engine in ("", "none") else ARGS.engine
    else:
        engine = choose("\nMirAI (chat, prompt writing, Auto mode — runs in Ollama, never renders)?",
                        [(k, lab) for k, (lab, _gb) in W.ENGINES.items()], W.MUSE_TAG)

    files = {f[0]: f for k in comps for f in W.COMPONENTS[k][2]}.values()
    need = sum(sz for rel, _u, sz in files if not W.have_model(reuse, rel, sz)) / W.GB + W.RUNTIME_GB
    need += (W.ENGINES.get(engine) or ("", 0))[1]
    say("\nPlan: models %s · MirAI %s · needs about %.0f GB (%.0f GB free)" % (
        ", ".join(comps) or "none", engine or "off", need, free), "b")
    if need > free:
        say("Not enough disk space.", "bad")
        if not ask("Try anyway?", False):
            return 1

    opts = {"dir": ROOT, "gpu": gpu, "components": comps, "engine": engine, "reuse": reuse,
            "desktop": not ARGS.no_shortcuts and ask("Desktop shortcut?", True),
            "autostart": not ARGS.no_shortcuts and ask("Start the server when Windows starts?", False),
            "lan": ask("Allow phones/tablets on your Wi-Fi (opens port 5400 in the firewall)?", False)}
    if not ask("\nStart the install?", True):
        return 0

    pr = Printer()
    inst = SourceInstaller(opts, pr)
    t = threading.Thread(target=inst.run, daemon=True)
    t.start()
    try:
        while not pr.done.wait(0.5):
            pass
    except KeyboardInterrupt:
        say("\nStopping … (run Setup.bat again to resume — finished downloads are kept)", "bad")
        inst.cancel = True
        t.join(60)
        return 1
    kind, v = pr.result
    if kind == "failed":
        say("\nSetup stopped: %s" % v, "bad")
        say("Full log: %s" % os.path.join(ROOT, "data", "logs", "install.log"), "dim")
        return 1
    say("\nMIR MEDIA LABS is ready.", "ok")
    if v:
        say("Skipped (run Setup.bat again later): " + ", ".join(v), "bad")
    say("Start it with  Start-MirMediaLabs.bat  (or the Start-menu shortcut) → http://127.0.0.1:5400")
    if not ARGS.yes and ask("Open it now?", True):
        subprocess.Popen(["cmd", "/c", START_BAT], cwd=ROOT, creationflags=W.NO_WINDOW)
    return 0


ap = argparse.ArgumentParser(description="MIR MEDIA LABS setup from source (Windows)")
ap.add_argument("--yes", "-y", action="store_true", help="take the recommended answer to every question")
ap.add_argument("--components", help="comma list of: " + ",".join(W.COMPONENTS) + " ('' = none)")
ap.add_argument("--engine", help="Ollama model for MirAI (%s), or 'none'" % ", ".join(k for k in W.ENGINES if k))
ap.add_argument("--reuse", help="an existing ComfyUI models folder to use instead of downloading")
ap.add_argument("--no-shortcuts", action="store_true", help="no Start-menu / desktop / startup shortcuts")
ap.add_argument("--verbose", "-v", action="store_true", help="print every install command and its output")
ARGS = ap.parse_args()

if __name__ == "__main__":
    sys.exit(main())
