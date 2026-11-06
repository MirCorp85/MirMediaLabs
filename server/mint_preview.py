"""MOTION MINT previews + visual review (Nov 2 2026, user on the first minted samples: "they look completely wrong").

A minted asset used to go straight into films without anyone LOOKING at it. Now every design is drawn by the real Diorama engine
(src/mg/diorama_engine.ts bundled with esbuild, run in headless Edge - the same path as the library thumbnails) as a contact
sheet: a movement as frames over its loop on a person, an object alone + held, a hat worn, an animal idle/walking beside a
person for scale, scenery standing in a place next to a person, a world from the air and at ground level. review() hands the
sheet to the lab's brain with eyes (cloud vision brain, else the local vision engine) with what the asset must show; it answers ok, or the
problems + a corrected spec, and motion_mint.design() loops until it passes (or keeps the best try)."""
import base64
import glob
import json
import os
import re
import subprocess
import tempfile
import uuid

import engines

ROOT = engines.motion()
ESBUILD = [engines.node(), os.path.join(ROOT, "node_modules", "esbuild", "bin", "esbuild")]


def _browser():
    import kinetic
    return kinetic.chrome()
WORK = os.path.join(tempfile.gettempdir(), "motion_mint_preview")
_JS = {"sig": None}


def engine_js():
    """The engine bundled for the browser (rebuilt when any src/mg/*.ts|tsx changes)."""
    os.makedirs(WORK, exist_ok=True)
    srcs = glob.glob(os.path.join(ROOT, "src", "mg", "*.ts")) + glob.glob(os.path.join(ROOT, "src", "mg", "*.json"))
    sig = max(os.path.getmtime(f) for f in srcs)
    js = os.path.join(WORK, "dio.js")
    if _JS["sig"] != sig or not os.path.exists(js):
        subprocess.run(ESBUILD + [os.path.join(ROOT, "src", "mg", "diorama_engine.ts"), "--bundle", "--format=iife", "--global-name=DIO", "--outfile=" + js, "--log-level=error"],
                       check=True, cwd=ROOT, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _JS["sig"] = sig
    return js


# one panel = {label, item (drawLibItem) | scene (drawDiorama props), t}
PAGE = r"""<!doctype html><meta charset="utf-8"><body><pre id="out"></pre><script src="dio.js"></script><script>
const JOBS = __JOBS__, out = {};
DIO.setSpriteResolver((u) => u);
(async () => {for (const [name, job] of Object.entries(JOBS)) {
	try {await DIO.preloadMint(job.mint || {}); DIO.registerMint(job.mint || {}); const pw = job.w || 340, ph = job.h || 340, n = job.panels.length, cv = document.createElement('canvas'); cv.width = pw * n; cv.height = ph + 30; const c = cv.getContext('2d');
		c.fillStyle = '#0B0B0D'; c.fillRect(0, 0, cv.width, cv.height);
		job.panels.forEach((P, i) => {const pc = document.createElement('canvas'); pc.width = pw; pc.height = ph; const q = pc.getContext('2d');
			if (P.scene) DIO.drawDiorama(q, pw, ph, P.t, {...P.scene, mint: job.mint || {}}); else DIO.drawLibItem(q, pw, ph, P.t, P.item);
			c.drawImage(pc, i * pw, 0); c.strokeStyle = '#2A2D34'; c.strokeRect(i * pw + .5, .5, pw - 1, ph - 1);
			c.fillStyle = '#D8DCE2'; c.font = '600 15px sans-serif'; c.fillText(P.label || '', i * pw + 8, ph + 20);});
		out[name] = cv.toDataURL('image/png');} catch (e) {out[name] = 'ERR ' + (e && e.stack || e);}}
document.getElementById('out').textContent = JSON.stringify(out);})();
</script>"""


def _inline_sprites(jobs):
    """Sprite PNGs as data: URLs (a file:// image would taint the canvas and toDataURL would throw)."""
    jobs, seen = json.loads(json.dumps(jobs)), {}
    for job in jobs.values():
        for k in ("items", "props", "species"):
            for D in ((job.get("mint") or {}).get(k) or {}).values():
                src = ((D or {}).get("sprite") or {}).get("src")
                if src and not src.startswith("data:"):
                    if src not in seen:
                        f = os.path.join(ROOT, "public", src.replace("/", os.sep))
                        seen[src] = "data:image/png;base64," + base64.b64encode(open(f, "rb").read()).decode() if os.path.isfile(f) else src
                    D["sprite"]["src"] = seen[src]
    return jobs


def render(jobs, out_dir=None):
    """jobs {name: {mint, panels, w?, h?}} → {name: png path | 'ERR …'} (one headless Edge run for all)."""
    js = engine_js()
    jobs = _inline_sprites(jobs)
    out_dir = out_dir or os.path.join(WORK, "sheets")
    os.makedirs(out_dir, exist_ok=True)
    html = os.path.join(WORK, "sheet_%s.html" % uuid.uuid4().hex[:6])
    open(html, "w", encoding="utf-8").write(PAGE.replace("__JOBS__", json.dumps(jobs)).replace('src="dio.js"', 'src="%s"' % ("file:///" + js.replace("\\", "/"))))
    try:
        r = subprocess.run([_browser(), "--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=60000", "--dump-dom", "file:///" + html.replace("\\", "/")],
                           capture_output=True, text=True, timeout=300, encoding="utf-8", errors="ignore", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        try:
            os.remove(html)
        except OSError:
            pass
    m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout or "", re.S)
    if not m:
        raise RuntimeError("preview page produced nothing: " + (r.stderr or "")[-300:])
    import html as H
    got, res = json.loads(H.unescape(m.group(1))), {}
    for name, data in got.items():
        if not str(data).startswith("data:image"):
            res[name] = str(data)[:400]
            continue
        fn = os.path.join(out_dir, re.sub(r"[^a-zA-Z0-9_.-]", "_", name) + ".png")
        open(fn, "wb").write(base64.b64decode(data.split(",", 1)[1]))
        res[name] = fn
    return res


def _kit(world, props, floor=None):
    """A bare place to stand things in (no walls), at the slot the engine uses for a film's first extra place."""
    return {"id": "mintpv", "name": "preview", "floor": floor or "grass", "walls": "none", "props": props, "st": {"center": [[1.2, 2.6], 1, None], "side": [[2.6, 2.4], -1, None]},
            "world": world, "o": [12, 8], "door": [15.5, 11.5]}


def _scene(world, kit, pose="stand", camera="medium", hero=None, animals=None, t=2.0):
    return {"world": world, "kits": [kit] if kit else [], "cast": [], "words": [], "captions": False, "hero": hero or {}, "scenery": [],
            "beats": [{"t0": 0, "t1": 30, "place": kit["id"] if kit else "street", "station": "center", "pose": pose, "camera": camera, "mood": "neutral", **({"animals": animals} if animals else {})}]}


def sheet_job(kind, spec, mint, look=None, world="city", floor=None):
    """The contact sheet for one asset (see the module doc)."""
    i, look = spec["id"], look or {}
    if kind == "acts":
        span = float(spec.get("loop") or 1.6)
        ts = [span * k / 5 for k in range(6)] if spec.get("once") or spec.get("pingpong") else [span * k / 6 for k in range(6)]
        return {"mint": mint, "panels": [{"label": "t=%.1fs" % t, "t": t, "item": {"type": "act", "act": i, "look": look}} for t in ts]}
    if kind == "items":
        acts = {"__pv_hold": {"keys": [{"u": 0, "far": [-58, -188], "near": [74, -262]}], "hold": [None, i]},
                "__pv_two": {"keys": [{"u": 0, "far": [-6, -262], "near": [44, -262]}], "two": i}}
        m = dict(mint, acts=dict(mint.get("acts") or {}, **acts))
        return {"mint": m, "panels": [{"label": "object", "t": 1, "item": {"type": "obj", "name": i}}, {"label": "held in one hand", "t": 1, "item": {"type": "act", "act": "__pv_hold", "look": look}},
                                      {"label": "held in both hands", "t": 1, "item": {"type": "act", "act": "__pv_two", "look": look}}]}
    if kind == "hats":
        lk = dict(look, hat=i)
        return {"mint": mint, "panels": [{"label": a, "t": 1.2, "item": {"type": "act", "act": a, "look": lk}} for a in ("stand", "wave", "think")]}
    if kind == "pieces":
        acts = {"__pv_piece": {"keys": [{"u": 0, "far": [-58, -188], "near": [58, -188]}], "piece": i}}
        m = dict(mint, acts=dict(mint.get("acts") or {}, **acts))
        return {"mint": m, "panels": [{"label": "beside a person", "t": 1, "item": {"type": "act", "act": "__pv_piece", "look": look}}]}
    if kind == "species":
        kit = _kit(world, [], floor)
        return {"mint": mint, "panels": [{"label": "idle", "t": 1, "item": {"type": "animal", "kind": i, "act": "idle"}}, {"label": "walking", "t": .35, "item": {"type": "animal", "kind": i, "act": "walk"}},
                                         {"label": "walking (later)", "t": .7, "item": {"type": "animal", "kind": i, "act": "walk"}},
                                         {"label": "beside a person (scale)", "t": 2, "scene": _scene(world, kit, animals=[{"kind": i, "act": "idle"}], camera="close")}]}
    if kind == "props":
        kit = _kit(world, [{"t": i, "x": 2.0, "y": 0.9, "w": spec.get("w", 1), "d": spec.get("d", 1), "h": spec.get("h", 1)}], floor)
        return {"mint": mint, "w": 400, "panels": [{"label": "alone", "t": 1, "item": {"type": "prop", "id": i}}, {"label": "in a place, next to a person", "t": 2, "scene": _scene(world, kit, camera="medium")},
                                                   {"label": "wide", "t": 2, "scene": _scene(world, kit, camera="wide")}]}
    if kind == "worlds":
        kit = _kit(i, [], (spec.get("o") or {}).get("floor"))
        return {"mint": mint, "w": 480, "h": 300, "panels": [{"label": "from the air", "t": 3, "scene": _scene(i, kit, camera="city", hero=look)}, {"label": "aerial", "t": 3, "scene": _scene(i, kit, camera="aerial", hero=look)},
                                                             {"label": "ground level", "t": 3, "scene": _scene(i, kit, camera="wide", hero=look)}]}
    raise ValueError(kind)


# ── visual review: the brain with eyes looks at the sheet ──
REVIEW_SYS = """You are the art director of the Diorama: narrated animated films of small, professional, clean-shaded characters in a tiny
isometric world (charcoal, brushed metal and gold; other colours only where a thing needs them). Read the contact sheet image you are given
and judge ONE newly made asset against what it must show.
Be strict about: does it READ instantly as the thing at a glance (silhouette, key features); body mechanics of movements (hands where the
action happens, no arm bending backwards or through the head, the object held at the hand, a clear start-to-end motion, feet on the ground
unless jumping); scale against the person; drawing quality (no stray floating shapes, no shapes reading as bones/ribs/skeleton unless
meant, pieces attached to each other); colours in the house look.
Reply JSON only: {"ok": true|false, "score": 0-10, "problems": ["…"], "fix": "<concrete instructions for the designer: which parts to move /
add / remove, with numbers in the asset's own coordinates>"}. ok = score >= 7 and nothing reads wrong."""


def vision_ask(prompt, image, system, timeout=300, model=None):
    """One answer from the lab's brain with eyes (the owner's cloud brain when it reads pictures, else the local vision
    engine) about the contact sheet → dict. `model` is ignored (kept for callers)."""
    import remix
    txt = remix.brain_see(prompt + "\n\nThe picture is the contact sheet.", [image], system, timeout=timeout)
    m = re.search(r"\{.*\}", str(txt or ""), re.S)
    if not m:
        raise RuntimeError("visual review: no JSON")
    return json.loads(m.group(0))