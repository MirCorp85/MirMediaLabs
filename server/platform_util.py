"""OS shims so the same server runs on Windows and Linux (stdlib only).

Windows keeps the exact flags/behavior it always had; on Linux the Win32-only pieces become
POSIX equivalents (new session instead of DETACHED, /proc instead of Win32 process queries).
"""
import os
import re
import shutil
import signal
import subprocess
import sys

IS_WIN = sys.platform == "win32"
NO_WINDOW = 0x08000000 if IS_WIN else 0          # creationflags=0 is accepted on POSIX
DETACHED = 0x00000008 if IS_WIN else 0
NEW_GROUP = 0x00000200 if IS_WIN else 0


def detached_kwargs(hide=True, new_group=False):
    """Popen kwargs for a background process that outlives us."""
    if IS_WIN:
        return {"creationflags": DETACHED | (NO_WINDOW if hide else 0) | (NEW_GROUP if new_group else 0)}
    return {"start_new_session": True}


def venv_python(venv_dir):
    return os.path.join(venv_dir, "Scripts", "python.exe") if IS_WIN else os.path.join(venv_dir, "bin", "python")


def _proc_list():
    """[(pid, exe_path, cmdline)] for every process we can see."""
    if IS_WIN:
        try:
            import psutil
            return [(p.pid, p.info.get("exe") or "", " ".join(p.info.get("cmdline") or []))
                    for p in psutil.process_iter(["exe", "cmdline"])]
        except ImportError:                   # no psutil in this build → ask WMI (as before the port)
            import json
            ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath,CommandLine | "
                  "ConvertTo-Json -Compress")
            try:
                raw = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                                     capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW).stdout
                rows = json.loads(raw or "[]")
                rows = [rows] if isinstance(rows, dict) else rows
                return [(r["ProcessId"], r.get("ExecutablePath") or "", r.get("CommandLine") or "") for r in rows]
            except Exception:
                return None
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % d, "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            try:
                exe = os.readlink("/proc/%s/exe" % d)
            except OSError:
                exe = ""
            out.append((int(d), exe, cmd))
        except OSError:
            pass
    return out


def _norm(p):
    """Comparable path: absolute, case-folded, and on Windows with 8.3 short names like MIRMED~1 expanded."""
    p = os.path.abspath(p)
    if IS_WIN:
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(32768)
            if ctypes.windll.kernel32.GetLongPathNameW(p, buf, 32768):
                p = buf.value
        except Exception:
            pass
    return os.path.normcase(p)


def find_pids(cmd_regex=None, exe_prefixes=()):
    """PIDs whose command line matches cmd_regex or whose executable lives under one of exe_prefixes."""
    procs = _proc_list() or []
    rx = re.compile(cmd_regex) if cmd_regex else None
    pre = [_norm(p) + os.sep for p in exe_prefixes]
    me = os.getpid()
    return [pid for pid, exe, cmd in procs if pid != me and (
        (rx and rx.search(cmd)) or (exe and any(_norm(exe).startswith(p) for p in pre)))]


def kill_pids(pids):
    for pid in pids:
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                               timeout=30, creationflags=NO_WINDOW)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


def browser_app_cmd(url, profile):
    """Command opening url as a standalone app window, or None (caller falls back to webbrowser)."""
    flags = ["--app=" + url, "--window-size=1500,950", "--user-data-dir=" + profile,
             "--no-first-run", "--no-default-browser-check"]
    if IS_WIN:
        for base in (os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                exe = os.path.join(base, rel)
                if base and os.path.isfile(exe):
                    return [exe] + flags
        return None
    for name in ("microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser"):
        exe = shutil.which(name)
        if exe:
            return [exe] + flags
    return None
