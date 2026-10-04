"""Live PC performance for the desktop client's perf card (no extra dependencies).

CPU and RAM come from the Win32 API (/proc on Linux), the GPU from nvidia-smi (amdgpu sysfs on Linux). A background sampler refreshes
every 1.5 s only while someone is watching (the card polls /api/perf), so it costs nothing
when the card is closed.
"""
import ctypes
import os
import shutil
import subprocess
import threading
import time

import core

if core.IS_WIN:
    from ctypes import wintypes

_LOCK = threading.Lock()
_STATE = {"v": None, "seen": 0.0, "running": False}
_SMI = shutil.which("nvidia-smi")


if core.IS_WIN:
    class _MEM(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _ft(f):
    return (f.dwHighDateTime << 32) | f.dwLowDateTime


def _cpu_times():
    if not core.IS_WIN:                               # /proc/stat: user nice system idle iowait ...
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
        return v[3] + (v[4] if len(v) > 4 else 0), sum(v)
    idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    return _ft(idle), _ft(kern) + _ft(user)       # kernel time includes idle


def _ram():
    if not core.IS_WIN:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        total = info.get("MemTotal", 1)
        used = total - info.get("MemAvailable", info.get("MemFree", 0))
        return {"used": used, "total": total, "pct": round(100.0 * used / max(1, total), 1)}
    m = _MEM()
    m.dwLength = ctypes.sizeof(_MEM)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    used = m.ullTotalPhys - m.ullAvailPhys
    return {"used": used, "total": m.ullTotalPhys, "pct": round(100.0 * used / max(1, m.ullTotalPhys), 1)}


def _amd_gpu():
    """AMD on Linux via the amdgpu sysfs files (no rocm-smi needed)."""
    import glob
    for dev in sorted(glob.glob("/sys/class/drm/card*/device")):
        def rd(name, d=dev):
            try:
                with open(os.path.join(d, name)) as f:
                    return f.read().strip()
            except OSError:
                return ""
        total = rd("mem_info_vram_total")
        if not total.isdigit() or int(total) < (1 << 30):
            continue
        used = int(rd("mem_info_vram_used") or 0)
        busy = rd("gpu_busy_percent")
        temp = power = 0.0
        for h in glob.glob(os.path.join(dev, "hwmon", "hwmon*")):
            t = rd("temp1_input", h) or rd("temp2_input", h)
            temp = int(t) / 1000.0 if t.isdigit() else temp
            pw = rd("power1_average", h) or rd("power1_input", h)
            power = int(pw) / 1e6 if pw.isdigit() else power
        name = rd("product_name") or "AMD GPU"
        return {"name": name, "util": float(busy) if busy.isdigit() else 0.0, "vram_used": used,
                "vram_total": int(total), "vram_pct": round(100.0 * used / int(total), 1), "temp": temp,
                "power": power, "power_limit": 0.0, "throttle": ""}
    return None


def _gpu():
    if not _SMI:
        return None if core.IS_WIN else _amd_gpu()
    try:
        out = subprocess.run([_SMI, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,"
                                    "power.draw,power.limit,clocks_throttle_reasons.active",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4,
                             creationflags=core.NO_WINDOW).stdout.strip().splitlines()[0]
        f = [x.strip() for x in out.split(",")]
        num = lambda s: float(s) if s.replace(".", "", 1).isdigit() else 0.0
        return {"name": f[0], "util": num(f[1]), "vram_used": num(f[2]) * 1048576, "vram_total": num(f[3]) * 1048576,
                "vram_pct": round(100.0 * num(f[2]) / max(1.0, num(f[3])), 1), "temp": num(f[4]),
                "power": num(f[5]), "power_limit": num(f[6]),
                "throttle": f[7] if len(f) > 7 and f[7] not in ("0x0000000000000000", "[N/A]") else ""}
    except Exception:
        return None


def _verdict(cpu, ram, gpu, rendering):
    """Plain-language bottleneck, worst first."""
    if gpu and gpu["vram_pct"] >= 97:
        return "warn", "VRAM full — the engine is offloading to RAM (slow). Try a smaller size, fewer frames or --fast."
    if ram["pct"] >= 92:
        return "warn", "System RAM almost full — close other apps; the page file is slowing renders."
    if gpu and gpu["temp"] >= 85:
        return "warn", "GPU is hot (%d°C) — it may slow itself down. Improve airflow." % gpu["temp"]
    if gpu and gpu.get("throttle") and rendering and 50 <= gpu["util"] < 90:
        return "info", "GPU is power/thermal limited right now."
    if rendering and gpu and gpu["util"] < 40 and cpu >= 85:
        return "warn", "CPU-bound — the GPU is waiting on the CPU (loading models / encoding)."
    if rendering and gpu and gpu["util"] < 40:
        return "info", "GPU mostly idle — loading models or saving; normal between steps."
    if rendering:
        return "ok", "GPU working at full speed — no bottleneck."
    return "ok", "Idle."


def _sample_loop():
    prev = _cpu_times()
    while True:
        time.sleep(1.5)
        if time.time() - _STATE["seen"] > 10:          # nobody watching → stop sampling
            with _LOCK:
                _STATE["running"] = False
            return
        cur = _cpu_times()
        di, dt = cur[0] - prev[0], cur[1] - prev[1]
        prev = cur
        cpu = round(100.0 * (1 - di / dt), 1) if dt > 0 else 0.0
        ram, gpu = _ram(), _gpu()
        with _LOCK:
            _STATE["v"] = {"cpu": cpu, "cores": os.cpu_count(), "ram": ram, "gpu": gpu, "t": time.time()}


def snapshot(rendering=False):
    with _LOCK:
        _STATE["seen"] = time.time()
        if not _STATE["running"]:
            _STATE["running"] = True
            threading.Thread(target=_sample_loop, daemon=True, name="mml-perf").start()
        v = dict(_STATE["v"] or {"cpu": 0.0, "cores": os.cpu_count(), "ram": _ram(), "gpu": _gpu(), "t": time.time()})
    level, msg = _verdict(v["cpu"], v["ram"], v["gpu"], rendering)
    v.update(rendering=rendering, level=level, verdict=msg)
    return v
