r"""MOTION STUDIO — HYBRID AI SCENES (user, Oct 28 2026: story films "look robotic … the reference has a lot more animation and
more detailed models" → chose HYBRID: AI-animated shots for the key moments, code-drawn puppets for the rest).

For a story project:
  1. CAST SHEETS   one character-design image per cast member, in the project's style (Qwen-Image, local GPU)
  2. KEY MOMENTS   the writer's `key` beats (else: the cold open, FX moments, big actions) — about a third of the scenes
  3. KEYFRAME      Qwen-Image EDIT: the cast sheet(s) of who is on screen → that exact moment, place and framing (16:9)
  4. ANIMATE       MiniMax H3 image→video (6 s), prompted with the action of the line
  5. SMOOTH        ffmpeg motion interpolation to 30 fps and the beat's length (smooth-plate method)
The beat gets `plate` = "lib:<file>.mp4"; Remotion (scenes.tsx StoryShot) plays it full-frame under the captions, data
overlay and FX. Everything goes through the Media Lab queue (:5000/mlab/api/generate), so it waits its turn on the GPU.
Every file lands in data/motion_wizard/scenes/<project>/ and is reused (a redo only remakes what's missing or changed).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import core

API = "http://127.0.0.1:5400"
FFX = core.FFMPEG or "ffmpeg"
FFP = (os.path.join(os.path.dirname(FFX), "ffprobe" + (".exe" if os.name == "nt" else "")) if os.path.dirname(FFX) else "ffprobe")
if not os.path.isfile(FFP):
    import shutil as _sh
    FFP = _sh.which("ffprobe") or FFP
MINTERP = "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
MAX_SLOW = 3.0
DYNAMIC = {"score", "catch", "celebrate", "react", "run", "shoot", "throw", "dance", "jump", "evolve", "lift", "handshake"}

# how each style looks when a scene is painted + animated by AI (kept close to the puppets, so cuts between them hold)
SCENE_LOOK = {
    "dusk": ("stylized 3D animated short film. Original characters: simple rounded figures with smooth matte charcoal-black heads "
             "and large glossy white expressive eyes, bold coloured clothing. Deep teal night world lit by warm ember-orange practical "
             "lights (windows, street lamps), cream highlights, soft ember rim light on the characters, cinematic depth of field, "
             "subtle film grain"),
    "signature": ("cinematic 3D animation in a dark charcoal studio world, sculpted graphite and brushed-silver characters and props, "
                  "a single warm amber accent light, glossy reflections, soft top light, film grain"),
    "grid": ("flat 2D Swiss-poster animation: off-white paper background, bold black geometric shapes, one vermilion-red accent, "
             "crisp edges, halftone texture, pictogram-like characters"),
    "liquid": ("glossy pastel 3D toy-world animation: soft rounded inflated shapes, violet, pink, gold and mint gradients, deep "
               "indigo night sky with glowing light, cute expressive characters with big eyes"),
    "paper": ("handmade cut-paper stop-motion animation: layered paper characters and sets with visible fibre texture and hard "
              "paper shadows, tomato red, deep blue, mustard yellow and cream on kraft paper"),
}
SET_DESC = {"street": "an evening city street with houses, lit windows and street lamps", "cafe": "a street café terrace with a big lit window and small tables",
            "room": "a bedroom with a desk, a glowing monitor and a big window over the city", "lab": "a science lab with benches, flasks and a big window",
            "field": "an outdoor soccer pitch with a goal and a tree line", "stadium": "a packed stadium at night under floodlights",
            "track": "an athletics track with stands", "city": "a city skyline at night", "nature": "rolling hills with trees at dusk",
            "space": "outer space with stars and a planet", "stage": "a theatre stage under a spotlight"}
SHOT_DESC = {"wide": "wide establishing shot, full body, the place clearly visible", "medium": "medium shot from the waist up",
             "close": "close-up on the face, emotional", "xclose": "extreme close-up on the eyes / a tiny detail"}
MOOD_DESC = {"happy": "happy, smiling", "surprised": "surprised, wide eyes, open mouth", "angry": "angry, frowning", "determined": "determined, focused",
             "sad": "sad, head down", "scared": "scared, flinching"}
ACT_MOTION = {"speech": "gives a passionate speech, gesturing", "talk": "talks expressively, hands gesturing", "wave": "waves hello",
              "point": "points and explains", "walk": "walks forward", "run": "sprints fast", "score": "runs in and kicks the ball into the goal, then celebrates",
              "shoot": "jumps and shoots a basketball into the hoop", "throw": "throws a ball hard", "celebrate": "jumps and celebrates with arms up",
              "jump": "jumps for joy", "dance": "dances", "think": "thinks, hand on chin", "read": "reads a book", "type": "types fast on a laptop",
              "lift": "lifts a heavy barbell", "sad": "slumps sadly", "handshake": "two people shake hands", "chat": "two people talk",
              "evolve": "a line of humans evolving from hunched cave people to upright modern people, walking forward",
              "catch": "snatches something flying past out of the air, lightning fast", "react": "jumps back, startled"}


# ── Media Lab calls  ──
def _call(path, body=None, timeout=180):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _upload(path):
    b = uuid.uuid4().hex
    ext = os.path.splitext(path)[1].lower()
    ctype = {".webp": "image/webp", ".png": "image/png"}.get(ext, "image/jpeg")
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API + "/api/upload", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["name"]


def _run(body, stop, label, sid=""):
    """Queue one Media Lab job and wait for it → library file paths. stop() → True aborts (the job is cancelled)."""
    body = dict(body, internal=True, fresh=True, clean=True)       # no lab watermark on cast sheets / keyframes / plates
    if sid:
        body["session"] = sid
    while True:
        if stop():
            raise InterruptedError()
        try:
            j = _call("/api/generate", body)
            break
        except urllib.error.HTTPError as e:
            if e.code == 409:                       # GPU queue busy — wait our turn
                time.sleep(8)
                continue
            raise RuntimeError("%s: %s" % (label, e.read()[:300]))
    jid = j["id"]
    while True:
        time.sleep(4)
        if stop():
            try:
                _call("/api/jobs/%s/cancel" % jid, {})
            except Exception:
                pass
            raise InterruptedError()
        j = _call("/api/jobs/" + jid)
        if j["status"] in ("done", "error", "cancelled"):
            break
    if j["status"] != "done" or not j.get("files"):
        raise RuntimeError("%s failed: %s" % (label, str(j.get("log", ""))[-300:]))
    return [os.path.join(core.LIB, os.path.basename(f)) for f in j["files"]]


def _dur(p):
    try:
        return float(subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip() or 0)
    except Exception:
        return 0.0


def _secs(path):
    """A clip's real length (the renderer loops it within this, never past its last frame)."""
    try:
        out = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return round(float(out.strip()), 3)
    except Exception:
        return 0


def _free_engine():
    """Drop the image model before the video model loads (ComfyUI /free)."""
    try:
        rq = urllib.request.Request("http://127.0.0.1:8188/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                    headers={"Content-Type": "application/json"})
        urllib.request.urlopen(rq, timeout=15).read()
        time.sleep(3)
    except Exception:
        pass


def smooth(src, need, dst, vertical=False):
    """6 s H3 clip → 30 fps motion-interpolated, slowed (≤3×) or ping-ponged to `need` s; 9:16 projects get a centred crop."""
    clip = _dur(src)
    if clip <= 0:
        raise RuntimeError("the animated clip has no length")
    slow = round(min(MAX_SLOW, max(1.0, need / clip)), 2)
    pong = clip * slow < need - 0.05
    vf = "setpts=%.3f*PTS,%s" % (slow, MINTERP)
    if vertical:
        vf += ",crop=ih*9/16:ih"
    vf = ("[0:v]%s,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0" % vf) if pong else vf
    tmp = dst + ".tmp.mp4"
    subprocess.run([FFX, "-v", "error", "-y", "-i", src, "-filter_complex" if pong else "-vf", vf, "-an", "-c:v", "libx264", "-crf", "17",
                    "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-g", "15", "-bf", "0", "-movflags", "+faststart", tmp], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    os.replace(tmp, dst)
    return dst


# ── prompts ──
def look_text(f):
    f = f or {}
    out = {"suit": "a dark suit with a tie", "jersey": "a sports jersey" + (" number %s" % f["number"] if f.get("number") else ""), "casual": "a casual t-shirt",
           "dress": "a dress", "lab": "a white lab coat", "fur": "a prehistoric fur tunic", "robe": "an ancient robe", "space": "a white astronaut suit"}.get(f.get("outfit"), "casual clothes")
    hair = {"short": "short hair", "side": "side-parted hair", "long": "long hair", "curly": "curly hair", "bun": "hair in a bun", "bald": "bald"}.get(f.get("hair"), "")
    acc = {"tie": "", "glasses": "round glasses", "cap": "a baseball cap", "crown": "a crown", "tophat": "a top hat", "helmet": "a helmet"}.get(f.get("accessory") or "", "")
    col = (" in the colour %s" % f["color"]) if f.get("color") else ""
    return ", ".join(x for x in ("wearing " + out + col, hair, acc, "with a beard" if f.get("beard") else "") if x)


def key_beats(p, cap=None):
    """Which scenes get AI animation: the writer's `key` flags, else the cold open + FX moments + big actions (≈1/3, ≤10)."""
    beats = [b for b in p.get("beats") or [] if b.get("kind") == "action"]
    n = len(p.get("beats") or [])
    cap = cap or max(2, min(10, round(n / 3)))
    flagged = [b for b in beats if b.get("key")]
    if flagged:
        return flagged[:cap]
    score = lambda b: (2 if b.get("fx") else 0) + (2 if b.get("action") in DYNAMIC else 0) + (1 if b.get("frame") in ("close", "xclose") else 0) + (3 if b is beats[0] else 0)
    ranked = sorted(beats, key=lambda b: -score(b))
    pick = ranked[:cap]
    return [b for b in beats if b in pick]                     # keep story order


def _h(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:10]


def build(p, log, save, stop, sid=""):
    """Make cast sheets, keyframes and animated plates for the key scenes. Idempotent; stop() aborts between/inside jobs."""
    style = p.get("style") or "dusk"
    look = SCENE_LOOK.get(style, SCENE_LOOK["dusk"])
    d = os.path.join(core.DATA, "motion_wizard", "scenes", p["id"])
    os.makedirs(d, exist_ok=True)
    cast = {c["id"]: c for c in p.get("cast") or []}
    keys = key_beats(p)
    for b in p.get("beats") or []:
        if b not in keys and b.get("plate_auto"):
            b.pop("plate", None)
            b.pop("plate_auto", None)
    log(p, "AI scenes for %d key moments: %s" % (len(keys), ", ".join("#%d" % (p["beats"].index(b) + 1) for b in keys)))
    p["scenes_plan"] = {"beats": [p["beats"].index(b) for b in keys]}
    p.setdefault("cast_sheets", {})
    save(p)
    # 1 · cast sheets
    sheets = {}
    need = {b.get("actor") or "hero" for b in keys} | {"hero"}
    for cid in sorted(need):
        c = cast.get(cid) or {"id": cid, "name": cid, "look": {}}
        f = os.path.join(d, "cast_%s_%s_%s.png" % (cid, style, _h(c.get("look"), look)))
        if not os.path.isfile(f):
            p["stage_note"] = "drawing the cast: %s" % c.get("name") or cid
            save(p)
            prompt = ("Character design sheet of one original character named %s, %s. Front view and three-quarter view side by side, full body, "
                      "neutral standing pose, plain light grey background. Style: %s. No text, no labels." % (c.get("name") or cid, look_text(c.get("look")), look))
            out = _run({"model": "qimg", "prompt": prompt, "override": {"mode": "generate", "aspect": "16:9", "size": "standard", "enhance": "off"}},
                       stop, "cast " + cid, sid)
            shutil.copy2(out[0], f)
            log(p, "cast sheet ready: %s" % (c.get("name") or cid), "done")
        sheets[cid] = f
        p["cast_sheets"][cid] = os.path.basename(f)
    # 2 · every keyframe first (image model), then 3 · every animation (video model): one model swap instead of one per
    # scene — the two models together don't fit in RAM next to everything else on this PC (Oct 28: 'hostbuf read failed')
    vertical = p.get("aspect") == "9:16"
    todo = []
    for k, b in enumerate(keys):
        actor = b.get("actor") or "hero"
        cname = (cast.get(actor) or {}).get("name") or "the character"
        act = ACT_MOTION.get(b.get("action") or "talk", "acts")
        place = SET_DESC.get(b.get("set") or "street", "a city street at night")
        sig = _h(style, look, b.get("line"), b.get("action"), b.get("set"), b.get("frame"), b.get("mood"), (cast.get(actor) or {}).get("look"))
        kf = os.path.join(d, "kf_%d_%s.png" % (p["beats"].index(b), sig))
        raw = os.path.join(d, "anim_%d_%s.mp4" % (p["beats"].index(b), sig))
        if b.get("plate_sig") == sig and b.get("plate") and os.path.isfile(core.in_dir(core.LIB, b["plate"].split(":", 1)[-1]) or ""):
            continue
        if not os.path.isfile(kf):
            p["stage_note"] = "AI scene %d/%d · keyframe" % (k + 1, len(keys))
            save(p)
            prompt = ("Using the character from the reference sheet exactly (same design, same clothes), paint one cinematic film frame: %s %s in %s. "
                      "The moment: \"%s\". Mood: %s. Camera: %s. 16:9 frame, the character clearly visible. Style: %s. No text, no captions, no logos."
                      % (cname, act, place, b.get("line", "")[:200], MOOD_DESC.get(b.get("mood"), "expressive"), SHOT_DESC.get(b.get("frame") or "wide"), look))
            refs = [_upload(sheets.get(actor) or sheets["hero"])]
            out = _run({"model": "qimg", "prompt": prompt, "refs": refs, "override": {"mode": "edit", "aspect": "16:9", "size": "hd", "enhance": "off"}},
                       stop, "keyframe %d" % (k + 1), sid)
            shutil.copy2(out[0], kf)
            log(p, "keyframe %d/%d ready (#%d)" % (k + 1, len(keys), p["beats"].index(b) + 1), "done")
        b["kf_live"] = os.path.basename(kf)            # the progress view shows it right away
        save(p)
        todo.append((k, b, cname, act, sig, kf, raw))
    if todo:
        _free_engine()
    for k, b, cname, act, sig, kf, raw in todo:
        p["stage_note"] = "AI scene %d/%d · animating (≈ 6-9 min)" % (k + 1, len(keys))
        save(p)
        if not os.path.isfile(raw):
            motion = ("%s %s. %s. Smooth, expressive, natural character animation with clear body movement and facial acting; the camera "
                      "moves gently (slow push-in). Keep the character design exactly as in the first frame. No text." % (cname, act, b.get("line", "")[:160]))
            out = _run({"model": "h3", "prompt": motion, "refs": [_upload(kf)],
                        "override": {"mode": "i2v", "aspect": "16:9", "res": "high", "seconds": 6, "quality": "turbo8"}}, stop, "animate %d" % (k + 1), sid)
            vid = next((x for x in out if x.lower().endswith((".mp4", ".webm", ".mov"))), out[0])
            shutil.copy2(vid, raw)
        p["stage_note"] = "AI scene %d/%d · smoothing" % (k + 1, len(keys))
        save(p)
        name = core.new_name("mgscene", ".mp4")
        smooth(raw, float(b.get("dur") or 5) + 0.4, os.path.join(core.LIB, name), vertical)
        meta = {"user": p["user"], "model": "h3", "mode": "motion-scene", "prompt": b.get("line", "")[:300], "created": time.time()}
        if sid:
            meta["session"] = sid
        core.index_add(name, meta)
        b.update(plate="lib:" + name, plate_sig=sig, plate_auto=True, keyframe=os.path.basename(kf), plate_dur=_secs(os.path.join(core.LIB, name)))
        log(p, "AI scene %d/%d ready (#%d)" % (k + 1, len(keys), p["beats"].index(b) + 1), "done")
        save(p)
    p["stage_note"] = ""
