"""ALTER — change one thing in a clip, keep the performance (local engines only, no API).

Method adapted from the scenario-alter skill (MIT, alter_kit/ holds its scripts unchanged except a Windows font path):
  1. prep    : the clip made edit-ready (HDR→SDR, rotation baked, constant fps, size bounds) and cut to the span
  2. frame   : its FIRST frame grabbed — the target-frame step (Qwen edit) changes only the one thing in it, so the
               video engine copies a finished, photographed example instead of guessing from a flat product shot
  3. render  : the pipeline's own steps (Qwen target frame → H3 / Wan VACE local render)
  4. check   : alter_check.py scores the render against the clip (change area, structure, motion, jumps, tail drift)
               and writes a contact sheet + 100% crops of what changed
  5. finish  : alter_finish.py conforms the render to the clip's clock, trims the drifted tail, lays the clip's own
               sound back (lips / steps stay in sync because the motion is the clip's) and writes a side-by-side.
The scripts run as a child process with the lab's ffmpeg on PATH; nothing here touches the network.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

import core

KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alter_kit")
WORK = os.path.join(core.DATA, "alter_work")
MIN_S, MAX_S = 4.0, 10.0          # one local render pass (Wan VACE / H3 control) holds ~10 s well


def _env():
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(core.FFMPEG) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _python():
    """Python with numpy + Pillow for the kit's scripts: this interpreter on a source install, else the engine's
    (ComfyUI venv) Python — never sys.executable in the compiled PC edition (that is MirMediaLabs.exe)."""
    if not getattr(sys, "frozen", False) and "__compiled__" not in globals():
        exe = sys.executable
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        exe = alt if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(alt) else exe
        try:
            import numpy  # noqa: F401
            import PIL  # noqa: F401
            return exe
        except ImportError:
            pass
    import comfy
    if comfy.COMFY_PY and os.path.isfile(comfy.COMFY_PY):
        return comfy.COMFY_PY
    raise RuntimeError("ALTER needs the engine's Python (numpy + Pillow) — run Setup → Repair")


def _run(script, args, timeout=1800):
    r = subprocess.run([_python(), os.path.join(KIT, script)] + [str(a) for a in args], capture_output=True,
                       text=True, timeout=timeout, env=_env(), creationflags=getattr(core, "NO_WINDOW", 0))
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode, out


def workdir(job):
    d = os.path.join(WORK, job.get("id") or ("j%d" % int(time.time() * 1000)))
    os.makedirs(d, exist_ok=True)
    return d


def prep(job, src, seconds, log):
    """→ (prepared clip path, first-frame png path). Clips under 4 s skip the prep script (it needs 4 s) but still
    get their first frame."""
    d = workdir(job)
    import renderers
    dur = renderers.media_seconds(src) or 0
    span = max(1.0, min(float(seconds or MAX_S), MAX_S, dur or MAX_S))
    clip = os.path.join(d, "source.mp4")
    if dur >= MIN_S and span >= MIN_S:
        code, out = _run("alter_prep.py", [src, "--out", clip, "--end", "%.3f" % span, "--force"], 900)
        if code != 0 or not os.path.isfile(clip):
            raise RuntimeError("ALTER prep failed: " + out[-400:])
        log("ALTER prep · " + " · ".join(l.strip(" -") for l in out.splitlines()[:4] if l.strip()))
    else:
        renderers.ffmpeg(["-i", src, "-t", "%.3f" % span, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-movflags", "+faststart", clip], 300)
        log("ALTER prep · short clip (%.1fs) — re-encoded only" % span)
    clip = _one_shot(clip, d, log)
    frame = os.path.join(d, "frame0.png")
    code, out = _run("alter_frame.py", [clip, "--t", "0", "--out", frame, "--force"], 300)
    if code != 0 or not os.path.isfile(frame):
        raise RuntimeError("ALTER frame grab failed: " + out[-300:])
    log("ALTER target frame source · first frame of the clip")
    return clip, frame


_CUTS = ("import sys, json; sys.path.insert(0, sys.argv[1]); from alter_split import find_cuts; from _av import probe; "
         "i = probe(sys.argv[2]); c, e = find_cuts(sys.argv[2], i['fps']); "
         "print(json.dumps({'cuts': c, 'frames': len(e) + 1, 'fps': i['fps'], 'audio': i['has_audio']}))")


def _one_shot(clip, d, log):
    """One render pass must not run across a cut (the target frame only matches the first shot, and the engine
    morphs between shots). A clip with cuts is cut down to its longest continuous shot."""
    r = subprocess.run([_python(), "-c", _CUTS, KIT, clip], capture_output=True, text=True, timeout=300,
                       env=_env(), creationflags=getattr(core, "NO_WINDOW", 0))
    try:
        info = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return clip
    cuts, n, fps = info["cuts"], info["frames"], info["fps"] or 24.0
    if not cuts:
        return clip
    edges = [0] + cuts + [n]
    a, b = max(zip(edges, edges[1:]), key=lambda s: s[1] - s[0])
    if (b - a) / fps < 1.0:
        log("ALTER: your clip has %d cut%s and no shot over 1 s — rendering it as is" % (len(cuts), "" if len(cuts) == 1 else "s"))
        return clip
    out = os.path.join(d, "shot.mp4")
    import renderers
    args = ["-i", clip, "-vf", "trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS" % (a, b)]
    if info.get("audio"):
        args += ["-af", "atrim=start=%.4f:end=%.4f,asetpts=PTS-STARTPTS" % (a / fps, b / fps), "-c:a", "aac", "-b:a", "192k"]
    renderers.ffmpeg(args + ["-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], 300)
    log("ALTER: your clip has %d cut%s — one shot per render, using the longest (%.1fs → %.1fs)" % (
        len(cuts), "" if len(cuts) == 1 else "s", a / fps, b / fps))
    return out


def _tail_trim(issues):
    for s in issues or []:
        m = re.search(r"--trim-tail (\d+)", s)
        if m:
            return int(m.group(1))
    return 0


def finish(job, clip, render, mode, log, audio=None):
    """QA + deliver. → (library files, report text). The render itself stays in the library too (the raw take)."""
    d = workdir(job)
    qa = os.path.join(d, "qa")
    code, out = _run("alter_check.py", [clip, render, "--out", qa, "--mode", mode, "--force"], 1200)
    rep = {}
    try:
        with open(os.path.join(qa, "report.json"), encoding="utf-8") as f:
            rep = json.load(f)
    except Exception:
        log("ALTER check could not finish: " + out[-300:])
    trim = min(_tail_trim(rep.get("issues")), 24)
    final = os.path.join(d, "final.mp4")
    args = [clip, render, "--out", final, "--compare", "--force"]
    if trim:
        args += ["--trim-tail", trim]
    if audio:
        args += ["--audio", audio]
    code2, out2 = _run("alter_finish.py", args, 1800)
    if code2 != 0 or not os.path.isfile(final):
        raise RuntimeError("ALTER finish failed: " + out2[-400:])
    files = []
    stamp = time.strftime("%Y%m%d_%H%M%S")
    meta = {"model": "alter", "prompt": (job.get("prompt") or "")[:2000], "job": job.get("id"), "created": time.time(),
            "user": job.get("user") or "owner", "mode": "alter-" + mode,
            **({"session": job["session"]} if job.get("session") else {})}
    for src, prefix, ext in ((final, "alter", ".mp4"), (os.path.splitext(final)[0] + "_side.mp4", "alter_compare", ".mp4"),
                             (os.path.join(qa, "crops.jpg"), "alter_qa_crops", ".jpg"),
                             (os.path.join(qa, "sheet.jpg"), "alter_qa_sheet", ".jpg")):
        if os.path.isfile(src):
            name = "%s_%s%s" % (prefix, stamp, ext)
            shutil.copy2(src, os.path.join(core.LIB, name))
            core.index_add(name, dict(meta))
            files.append(name)
    shutil.rmtree(d, ignore_errors=True)
    verdict = rep.get("verdict") or "UNCHECKED"
    lines = ["ALTER QA · %s · %s" % (verdict, mode),
             "changed %.1f%% of the frame · structure %.2f · motion match %.2f" % (
                 100 * float(rep.get("changed_area") or 0), float(rep.get("structure_median") or 0),
                 float(rep.get("motion_correlation") or 0))]
    if trim:
        lines.append("trimmed %d drifted frames at the end" % trim)
    lines += ["· " + s for s in rep.get("issues") or [] if "--trim-tail" not in s]
    lines.append("Look at the QA crops at 100%: logos, hands, letters and invented props show up there.")
    log(lines[0] + " · " + lines[1])
    return files, "\n".join(lines)
