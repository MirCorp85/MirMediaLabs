"""Render the ⚙ option previews shown in the settings panels (static/fx/ + manifest.json).

One base scene, one fixed seed, ONE option changed per preview — so the tiles compare like for like.
  · H3 clips   — camera / shot / motion / scene effect / signature effect (via the lab's own /api/generate,
                 so a preview is exactly what a user would get)
  · Qwen stills — H3 look + lighting (the same sentence H3 receives, drawn by Qwen-Image: fast)
  · post FX     — grade / grain / vignette / sharpen / fade / fps / speed / loop: ffmpeg on the base clip
                 through renderers.post_video (identical filters, no GPU)

Resumable (existing files are skipped) and polite: a request on the lab always goes first, and your
saved ⚙ values are put back after every job (/api/generate saves the params it is given).

    python tools\\make_param_previews.py                 # everything
    python tools\\make_param_previews.py --only h3.camera --limit 3
    python tools\\make_param_previews.py --list
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "server")
sys.path.insert(0, SERVER)
import core          # noqa: E402
import renderers     # noqa: E402

LAB = "http://127.0.0.1:%d" % core.PORT          # loopback = the host, no key needed
FX = os.path.join(SERVER, "static", "fx")
MIRRORS = [r"C:\AiMir-Tools\MirOSMediaLab\server\static\fx"]   # MirOS /mlab serves its own static copy
SEED = 424242
SCENE = ("A young woman in a long red wool coat walks slowly across a rain-wet city plaza at dusk, "
         "warm shop windows glowing behind her, a few pedestrians in the distance")
H3_BASE = {"mode": "t2v", "aspect": "16:9", "res": "draft", "seconds": 4, "quality": "turbo4", "seed": SEED,
           "enhance": "off", "audio": "off", "camera": "auto", "shot": "auto", "motion": "auto", "look": "auto",
           "lighting": "auto", "scene_fx": "none", "style": "none", "steady": "on", "speed": "1", "grade": "none",
           "grain": "off", "vignette": "off", "sharpen": "off", "fade": "none", "fps": "24", "upscale": "off",
           "loop": "off", "extend": 0, "workflow": "builtin"}
QIMG_BASE = {"mode": "generate", "aspect": "16:9", "size": "standard", "enhance": "off", "seed": SEED,
             "upscale": "off", "workflow": "builtin"}
H3_CLIPS = ("camera", "shot", "motion", "scene_fx", "style")
STILLS = {"look": renderers.H3_LOOK, "lighting": renderers.H3_LIGHT}
POST = ("grade", "grain", "vignette", "sharpen", "fade", "fps", "speed", "loop")
SKIP = {"auto", "none", "off", "1", "24"}


def opts(field):
    f = next(x for x in __import__("params").MODELS["h3"]["fields"] if x["k"] == field)
    return [str(o[0] if isinstance(o, list) else o) for o in f["opts"] if str(o[0] if isinstance(o, list) else o) not in SKIP]


def plan():
    jobs = [("h3", "_base", "base")]
    jobs += [("h3", k, v) for k in H3_CLIPS for v in opts(k)]
    jobs += [("still", k, v) for k in STILLS for v in opts(k)]
    jobs += [("post", k, v) for k in POST for v in opts(k)]
    return jobs


def out_paths(field, val):
    d = os.path.join(FX, "h3", field)
    return os.path.join(d, val + ".mp4"), os.path.join(d, val + ".jpg")


def ff(*args):
    subprocess.run([core.FFMPEG, "-y", "-v", "error", *args], check=True, creationflags=core.NO_WINDOW)


def small_clip(src, mp4, jpg, keep_fps=False):
    """360p, muted, ~200 KB loop + poster frame (keep_fps for the frame-rate previews)."""
    os.makedirs(os.path.dirname(mp4), exist_ok=True)
    ff("-i", src, "-vf", "scale=-2:360" + ("" if keep_fps else ",fps=24"), "-an", "-c:v", "libx264", "-crf", "30", "-preset", "slow",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4)
    ff("-ss", "1.5", "-i", mp4, "-frames:v", "1", "-q:v", "4", jpg)


def small_still(src, jpg):
    os.makedirs(os.path.dirname(jpg), exist_ok=True)
    ff("-i", src, "-vf", "scale=-2:360", "-q:v", "4", jpg)


def lab_idle():
    try:
        st = requests.get(LAB + "/api/status", timeout=5).json()
        return not st.get("running") and not st.get("queued")
    except requests.RequestException:
        return False


def render(model, params, prompt):
    """Submit through the lab, wait, return the output file path. Restores the person's saved ⚙ values."""
    saved = requests.get(LAB + "/api/params/" + model, timeout=10).json()
    saved = saved.get("values", saved)
    try:
        while True:
            while not lab_idle():
                time.sleep(20)                       # someone is rendering — they go first
            r = requests.post(LAB + "/api/generate", json={"model": model, "prompt": prompt, "params": params}, timeout=30)
            if r.status_code != 409:
                break
            time.sleep(30)
        r.raise_for_status()
        jid = r.json()["id"]
    finally:
        requests.post(LAB + "/api/params/" + model, json={"values": saved}, timeout=10)   # put the panel back
    while True:
        time.sleep(10)
        j = requests.get(LAB + "/api/jobs/" + jid, timeout=10).json()
        if j.get("status") in ("done", "error", "failed", "cancelled"):
            break
    if j.get("status") != "done" or not j.get("files"):
        raise RuntimeError("%s: %s" % (j.get("status"), (j.get("output") or j.get("log") or "")[-300:]))
    return os.path.join(core.LIB, j["files"][0])


def write_manifest():
    man = {}
    for root, _, files in os.walk(FX):
        for fn in files:
            if fn.endswith(".jpg") and not fn.startswith("_"):
                rel = os.path.relpath(os.path.join(root, fn), os.path.join(SERVER, "static")).replace("\\", "/")
                key = rel[3:-4]                                    # fx/h3/camera/orbit.jpg → h3/camera/orbit
                ent = {"poster": "static/" + rel}          # relative: the page lives at / (lab) or /mlab/ (MirOS)
                if os.path.isfile(os.path.join(root, fn[:-4] + ".mp4")):
                    ent["video"] = "static/" + rel[:-4] + ".mp4"
                man[key] = ent
    with open(os.path.join(FX, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    for m in MIRRORS:
        if os.path.isdir(os.path.dirname(m)):
            shutil.copytree(FX, m, dirs_exist_ok=True)
    return len(man)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="e.g. h3.camera or h3.camera=orbit")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    todo = plan()
    if a.only:
        f, _, v = a.only.partition("=")
        f = f.split(".")[-1]
        todo = [t for t in todo if t[1] in (f, "_base") and (not v or t[2] in (v, "base"))]
    todo = [t for t in todo if not os.path.isfile(out_paths(t[1], t[2])[1])]
    if a.limit:
        todo = todo[:a.limit + (1 if todo and todo[0][1] == "_base" else 0)]
    print("%d previews to make" % len(todo))
    if a.list:
        for t in todo:
            print("  %s %s=%s" % t)
        return
    renderers.log = lambda job, msg: None                         # post_video logs to the lab console
    base_mp4 = out_paths("_base", "base")[0]
    for i, (kind, field, val) in enumerate(todo, 1):
        mp4, jpg = out_paths(field, val)
        print("[%d/%d] %s %s=%s" % (i, len(todo), kind, field, val), flush=True)
        try:
            if kind == "h3":
                p = dict(H3_BASE, **({} if field == "_base" else {field: val}))
                small_clip(render("h3", p, SCENE), mp4, jpg)
            elif kind == "still":
                small_still(render("qimg", QIMG_BASE, SCENE + ". " + STILLS[field][val]), jpg)
            else:
                if not os.path.isfile(base_mp4):
                    raise RuntimeError("base clip missing — run the H3 base first")
                os.makedirs(os.path.dirname(mp4), exist_ok=True)
                tmp = mp4 + ".src.mp4"
                shutil.copy(base_mp4, tmp)
                renderers.post_video({}, tmp, dict(H3_BASE, **{field: val}))
                small_clip(tmp, mp4, jpg, keep_fps=field == "fps")
                os.remove(tmp)
        except Exception as e:                                      # one bad option never stops the night
            print("   failed: %s" % e, flush=True)
        write_manifest()
    print("manifest: %d previews" % write_manifest())


if __name__ == "__main__":
    main()
