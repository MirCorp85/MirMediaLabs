"""EXPLAINED Producer — back half (stages 6-10), installed into explainer.STAGE_HANDLERS.

  assets         normalize the writer's episode.json to the engine's beat vocabulary, then run
                 MirRemotion/explained_build.py <slug> all --json  (reference photos → Qwen stills + line-art passes →
                 H3 plates → Music 3 beds → Kokoro narration → resolved timeline), progress parsed from "@@{json}" lines
  render         Remotion: ExplainedEpisode (16:9) + ExplainedThumb + 3× ExplainedShort (9:16), audio level check
  approve_final  checkpoint (skipped when Fully automatic)
  publish        VIRAL-Ω drafts: main video (fit=keep, title/description with real chapter timestamps, tags, pinned
                 comment, custom thumbnail as cover, AI-content disclosure is set by the uploader) + 3 Shorts (fit=crop,
                 YouTube Short + Instagram Reel). The person approves the MAIN video in Social (agents never publish);
                 once they do, the Shorts follow automatically 1/day at 6 PM — that one approval covers the batch.
  done           summary

Identical in spirit to producer.py: everything is resumable from the saved state, cancel kills the running job."""
import array
import json
from collections import Counter
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from datetime import datetime, timedelta

try:
    import core, explainer as X
except ImportError:          # pragma: no cover
    import core
    import explainer as X

REMOTION = X.REMOTION
BUILD = os.path.join(REMOTION, "explained_build.py")
FF = core.FFMPEG or "ffmpeg"
import sys
import engines
PY = engines.art_python()          # a real Python (the compiled lab's sys.executable is the app itself)
RCLI = [engines.node(), os.path.join(REMOTION, "node_modules", "@remotion", "cli", "remotion-cli.js")]
SHORT_HOUR = 18                    # Shorts go out at 6 PM local, one per day after the main video
ASSET_TIMEOUT = 4 * 3600
RENDER_TIMEOUT = 2 * 3600


# ── helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _commit(p, fn):
    uid, pid, st, epoch = p["uid"], p["id"], p["stage"], p.get("epoch", 0)

    def g(q):
        if q.get("epoch", 0) != epoch or q.get("stage") != st or q.get("state") != "running":
            return False
        fn(q)
    return X._mut(uid, pid, g)


def _alive(p):
    q = X.load(p["uid"], p["id"])
    return bool(q) and q.get("state") == "running" and q.get("epoch", 0) == p.get("epoch", 0) and q.get("stage") == p["stage"]


def _slug(p):
    return (p.get("topic") or {}).get("slug")


def _ep_dir(p):
    return os.path.join(X.EPISODES, _slug(p))


def _pub_dir(p):
    return os.path.join(REMOTION, "public", "episodes", _slug(p))


def _out_dir(p):
    d = os.path.join(REMOTION, "out", _slug(p))
    os.makedirs(d, exist_ok=True)
    return d


def _run(p, cmd, timeout, on_line=None, cwd=REMOTION):
    """Run a long tool as a cancellable child; returns (code, tail of output)."""
    env = dict(os.environ, EXPLAINED_SESSION=p.get("session") or "")       # explained_build files its Media Lab jobs here
    env.update(MIR_LAB_API="http://127.0.0.1:%d" % core.PORT, MIR_LIB=core.LIB, MIR_FFMPEG=core.FFMPEG or "")
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            encoding="utf-8", errors="replace", creationflags=X._NOWIN, env=env)
    X._PROCS[p["id"]] = proc
    tail, t0, last_check = [], time.time(), 0.0
    try:
        for line in proc.stdout:
            line = line.rstrip()
            tail = (tail + [line])[-40:]
            if on_line:
                on_line(line)
            if time.time() - last_check > 20:
                last_check = time.time()
                if not _alive(p):
                    X._kill(proc)
                    raise RuntimeError("cancelled")
            if time.time() - t0 > timeout:
                X._kill(proc)
                raise RuntimeError("timed out after %d min" % (timeout // 60))
        proc.wait(timeout=60)
    finally:
        X._PROCS.pop(p["id"], None)
    return proc.returncode, "\n".join(tail)


# ── stage 6a: normalize the writer's file to the engine vocabulary ───────────────────────────────────────────────────
def normalize(ep):
    """Map the script writer's schema onto the renderer: ref names, line-art passes for diagrams, card/compare fields,
    ref-file paths for photos/plates. Returns (ep, notes)."""
    notes = []
    refs = []
    for r in ep.get("ref_urls") or []:
        if isinstance(r, str):
            r = {"url": r}
        name = r.get("name") or re.split(r"\s+[—-]\s+", str(r.get("use") or ""))[0].strip()
        if not re.match(r"^[\w.-]+\.(jpe?g|png|webp)$", name or "", re.I):
            name = "ref%02d%s" % (len(refs) + 1, os.path.splitext(str(r.get("url", "")).split("?")[0])[1][:5] or ".jpg")
        refs.append(dict(r, name=name))
    # Media Lab (Qwen edit) takes png/jpg/webp only: GIF refs (e.g. Wikimedia rover selfies) become PNG first frames
    rename = {}
    for r in refs:
        if r["name"].lower().endswith(".gif"):
            new = r["name"][:-4] + ".png"
            rename[r["name"]] = new
            r["name"] = new
            r["convert"] = "first_frame"
    if rename:
        notes.append("GIF refs → PNG: " + ", ".join(rename.values()))
        for a in ep.get("assets", {}).values():
            if a.get("refs"):
                a["refs"] = [rename.get(x, x) for x in a["refs"]]
        for b in ep.get("beats") or []:
            for k in ("photo", "plate"):
                if b.get(k) in rename:
                    b[k] = rename[b[k]]
            if (b.get("v") or {}).get("plate") in rename:
                b["v"]["plate"] = rename[b["v"]["plate"]]
    ep["ref_urls"] = refs
    ref_names = {r["name"] for r in refs}
    assets = ep.setdefault("assets", {})

    def refpath(n):
        return ("ref/" + n) if n in ref_names else n

    for b in ep.get("beats") or []:
        v = b.setdefault("v", {})
        if b.get("photo"):
            b["photo"] = refpath(b["photo"])
        if b.get("plate") and b["plate"] in ref_names:
            b["plate"] = refpath(b["plate"])
        c = v.get("c")
        if c == "diagram":
            src = v.get("plate") or b.get("plate")
            if src:
                key = "la_" + re.sub(r"[^\w]", "_", os.path.splitext(os.path.basename(src))[0])
                if key not in assets:
                    assets[key] = {"model": "qimg", "lineart_of": src if src in assets else refpath(src)}
                    notes.append("line-art pass %s ← %s" % (key, src))
                v["art"] = key + ".png"
        elif c == "trims" and isinstance(v.get("cards"), list):
            v["cards"] = [x if "line1" in x else {"name": x.get("name", ""), "tag": x.get("tag", ""),
                          "line1": (x.get("lines") or [""])[0], "line2": " · ".join((x.get("lines") or [])[1:3]),
                          "label": x.get("label", "PRICE"), "value": x.get("price", x.get("value", "")),
                          "foot": x.get("foot", ""), "color": x.get("color", ["cyan", "amber", "red"][i % 3])}
                          for i, x in enumerate(v["cards"])]
        elif c == "compare" and not v.get("cols") and (v.get("left") or v.get("right")):
            v["cols"] = [str(v.get("left") or "").upper(), str(v.get("right") or "").upper()]
    # derived stills must reference their source: explained_build resolves "lineart_of" via Ep.find (episode dir first)
    for k, a in assets.items():
        if a.get("lineart_of", "").startswith("ref/"):
            a["lineart_of"] = a["lineart_of"]
    th = ep.get("thumbnail") or {}
    if th.get("plate") and th["plate"] in ref_names:
        th["plate"] = refpath(th["plate"])
    return ep, notes

# ── reference photos: top-up + no-repeat shot plan (Oct 17: Artemis had 7 refs → 5 plates looped all video long) ────
MIN_REFS = 12                     # fewer than this → a photo-hunt job looks for more before the assets are made
MAX_STILLS, MAX_PLATES = 32, 14   # GPU budget for the shot plan (H3 plates are the slow part)
SLOT_VISUALS = ("plate", "bignum", "midroll", "chapter", "endcard")
VARIANTS = ("a tight close-up on the most telling detail", "a wide establishing shot showing the whole scene and its setting",
            "a low, dramatic three-quarter angle", "a calm side-on profile view", "a high angle looking down on the scene")
PHOTOS_PROMPT = """You are the photo desk of MIR EXPLAINED. Read research.md and episode.json in this folder. The episode
already has {have} reference photos (episode.json → ref_urls). Find up to {want} MORE real photos of this exact subject
with WebSearch + WebFetch — official image galleries and press kits first (images.nasa.gov, maker newsrooms, agency
flickr, Wikimedia Commons), then quality outlets. Each must show something DIFFERENT from the existing ones and from
each other (another angle, detail, person, place or moment): every photo becomes its own shot in the video.
Only DIRECT image URLs (.jpg/.jpeg/.png/.webp) that you saw on a page you actually opened; never invent a URL;
skip images smaller than ~800 px wide, logos, charts with lots of text, and anything already in ref_urls.
Write photos_more.json in this folder: a JSON array of {{"url": "...", "source": "<publisher> — <page title>",
"use": "<short_snake_name>.jpg — what it shows", "credit": "<credit line>"}} (names unique, not already used).
Reply with one line: DONE <count>."""


def _more_refs(p, ep):
    """Ask Claude for more reference photos (up to MAX_REFS) when the script used fewer than MIN_REFS. Never fatal."""
    have = len(ep.get("ref_urls") or [])
    if have >= MIN_REFS:
        return 0
    f = _ep_dir(p)
    out = os.path.join(f, "photos_more.json")
    _commit(p, lambda q: X._log(q, "Only %d reference photos — looking for up to %d more so no picture has to repeat."
                                % (have, X.MAX_REFS - have)))
    try:
        if X.RESEARCH_ENGINE(p) == "claude":
            X.claude_job(p["id"], PHOTOS_PROMPT.format(have=have, want=X.MAX_REFS - have), f, "photos",
                         tools=("WebSearch", "WebFetch", "Read", "Write"))
            extra = json.load(open(out, encoding="utf-8"))
        else:   # free: NASA Images + Wikimedia Commons (no model needed — this runs in the assets stage)
            import kaggle_research as KR
            t = p.get("topic") or {}
            extra = KR.more_photos(t.get("topic") or ep.get("meta", {}).get("title", ""),
                                   [r.get("url") for r in ep.get("ref_urls") or []], X.MAX_REFS - have,
                                   [t.get("angle", "")] + [b.get("cap", "") for b in ep.get("beats", []) if b.get("v", {}).get("c") == "chapter"])
            with open(out, "w", encoding="utf-8") as h:
                json.dump(extra, h, indent=1)
    except Exception as e:
        _commit(p, lambda q: X._log(q, "Photo hunt didn't work (%s) — going on with %d photos." % (str(e)[:120], have), "warn"))
        return 0
    urls = {r.get("url") for r in ep["ref_urls"]}
    names = {r.get("name") for r in ep["ref_urls"]}
    added = 0
    for r in extra if isinstance(extra, list) else []:
        if len(ep["ref_urls"]) >= X.MAX_REFS:
            break
        url = str(r.get("url") or "")
        if not re.match(r"^https?://", url) or url in urls:
            continue
        n = re.split(r"\s+[—-]\s+", str(r.get("use") or ""))[0].strip()
        if not re.match(r"^[\w.-]+\.(jpe?g|png|webp)$", n, re.I) or n in names:
            n = "more%02d%s" % (added + 1, os.path.splitext(url.split("?")[0])[1][:5] or ".jpg")
        if n in names:
            continue
        ep["ref_urls"].append({"url": url, "source": r.get("source", ""), "use": "%s — %s" % (n, re.split(r"\s+[—-]\s+", str(r.get("use") or ""), 1)[-1]),
                               "credit": r.get("credit", ""), "name": n})
        urls.add(url)
        names.add(n)
        added += 1
    _commit(p, lambda q: X._log(q, "Found %d more reference photos (%d in total)." % (added, len(ep["ref_urls"])), "done"))
    return added


def _prune_refs(p, ep):
    """Drop reference photos that didn't download (and the stills that only had them), so no beat points at nothing."""
    rd = os.path.join(_pub_dir(p), "ref")
    ok = {r["name"] for r in ep.get("ref_urls") or [] if os.path.isfile(os.path.join(rd, r["name"]))}
    if len(ok) < max(1, len(ep.get("ref_urls") or []) // 2):      # mostly missing = a network problem, not bad URLs
        return []
    gone = [r["name"] for r in ep["ref_urls"] if r["name"] not in ok]
    if not gone:
        return []
    ep["ref_urls"] = [r for r in ep["ref_urls"] if r["name"] in ok]
    A = ep["assets"]
    dead = {k for k, a in A.items() if a.get("model") == "qimg" and a.get("refs") and not any(r in ok for r in a["refs"])}
    for k, a in A.items():
        if a.get("refs"):
            a["refs"] = [r for r in a["refs"] if r in ok] or a["refs"]
    grow = True
    while grow:
        grow = False
        for k, a in A.items():
            if k not in dead and (a.get("from") in dead or a.get("lineart_of") in dead):
                dead.add(k)
                grow = True
    for k in dead:
        A.pop(k, None)
    for b in ep["beats"]:
        if b.get("photo") and os.path.basename(b["photo"]) not in ok:
            b.pop("photo")
            b["v"] = {"c": "plate"}
            b["mode"] = "studio"
        if b.get("plate") in dead:
            b.pop("plate")
    return gone


def _vkey(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:22] or "shot"


def diversify(ep):
    """Shot plan: one still per reference photo, and every studio / card / photo / end beat gets a visual nobody else
    uses — the writer's pick when it's free, else an unused still/plate (other subjects first), else a new
    alternate-angle variant of the least-used photo. Idempotent. Returns notes."""
    A, beats = ep["assets"], ep["beats"]
    refs = [r["name"] for r in ep.get("ref_urls") or []][:X.MAX_REFS]
    what = {r["name"]: re.split(r"\s+[—-]\s+", str(r.get("use") or ""), 1)[-1] for r in ep.get("ref_urls") or []}
    notes = []

    def fam(k, depth=0):
        a = A.get(k)
        if a is None or depth > 6:
            return os.path.basename(str(k))
        if a.get("refs"):
            return os.path.basename(a["refs"][0])
        src = a.get("from") or a.get("lineart_of")
        return fam(src, depth + 1) if src else k

    is_vis = lambda k: k in A and A[k].get("model") in ("qimg", "h3") and not k.startswith("la_") and not A[k].get("lineart_of")
    is_vid = lambda k: (k in A and A[k].get("model") == "h3") or str(k).endswith(".mp4")
    count = lambda m: sum(1 for a in A.values() if a.get("model") == m)

    # 1. a still for every reference photo
    with_still = {fam(k) for k in A if is_vis(k) and A[k]["model"] == "qimg"}
    new_st = []
    for r in refs:
        if r in with_still or count("qimg") >= MAX_STILLS:
            continue
        k = "st_" + _vkey(os.path.splitext(r)[0])
        while k in A:
            k += "_b"
        A[k] = {"model": "qimg", "refs": [r], "prompt": "Recreate the real subject of the reference photo (%s) as a "
                "photorealistic wide 16:9 cinematic shot in its real setting, moody charcoal studio lighting, true "
                "proportions, no text, no watermark." % what.get(r, "")}
        new_st.append(k)
    if new_st:
        notes.append("%d new stills so every reference photo is used" % len(new_st))

    # 2. hand out visuals beat by beat. A "picture" is a still (a plate shows its source still's picture, a photo beat
    #    its ref): no picture twice, and the same subject (reference photo) never within GAP shots of itself.
    GAP = 3
    order = {k: i for i, k in enumerate(A)}
    used, fu, recent, vn = set(), Counter(), [], Counter()
    swaps, made = 0, []
    pic = lambda k: (A[k].get("from") if A[k].get("model") == "h3" else k) if k in A else "ref:" + os.path.basename(str(k))
    near = lambda f: f in recent[-GAP:]

    def plate_from(st):
        if count("h3") >= MAX_PLATES:
            return None
        k = "pl_" + st[3:] if st.startswith("st_") else "pl_" + st
        while k in A:
            k += "_b"
        A[k] = {"model": "h3", "from": st, "prompt": "one slow, calm continuous camera push-in with gentle parallax; "
                "subtle natural motion only, nothing changes shape", "seconds": 6}
        order[k] = len(order)
        made.append(k)
        return k

    def variant(want_vid):
        if count("qimg") >= MAX_STILLS or not refs:
            return None
        r = min(refs, key=lambda x: (near(x), fu[x], vn[x], refs.index(x)))
        vn[r] += 1
        n = 2
        while "st_%s_v%d" % (_vkey(os.path.splitext(r)[0]), n) in A:
            n += 1
        k = "st_%s_v%d" % (_vkey(os.path.splitext(r)[0]), n)
        A[k] = {"model": "qimg", "refs": [r], "prompt": "Recreate the real subject of the reference photo (%s) as %s — a "
                "DIFFERENT framing from the original photo; photorealistic wide 16:9 cinematic shot, true proportions, "
                "no text, no watermark." % (what.get(r, ""), VARIANTS[(n - 2) % len(VARIANTS)])}
        order[k] = len(order)
        made.append(k)
        return (plate_from(k) if want_vid else None) or k

    def take(k, f):
        used.add(pic(k))
        fu[f] += 1
        recent.append(f)

    for b in beats:
        c = (b.get("v") or {}).get("c")
        if c == "photo" and b.get("photo"):
            cur = os.path.basename(b["photo"])
            if "ref:" + cur in used:                                   # the writer's photo matches the narration: keep it
                alt = sorted((r for r in refs if "ref:" + r not in used), key=lambda r: (near(r), fu[r], refs.index(r)))
                if alt and alt[0] != cur:                              # ...unless that exact photo was already shown
                    b["photo"] = "ref/" + alt[0]
                    src = next((x for x in ep["ref_urls"] if x["name"] == alt[0]), {})
                    b["v"]["credit"] = src.get("credit") or (src.get("source") or "").split(" — ")[0] or b["v"].get("credit", "")
                    cur = alt[0]
                    swaps += 1
            take("ref/" + cur, cur)
            continue
        if b.get("mode") == "hud" or c == "diagram" or (c not in SLOT_VISUALS and not b.get("plate")):
            continue
        cur = b.get("plate")
        want_vid = (is_vid(cur) if cur else False) or c in ("plate", "bignum", "midroll")   # these always want motion (Oct 18)
        if cur and is_vis(cur) and pic(cur) not in used and not near(fam(cur)):
            pick = cur
        else:
            pool = [k for k in A if is_vis(k) and pic(k) not in used]
            best = min(pool, key=lambda k: (near(fam(k)), fu[fam(k)] > 0, is_vid(k) != want_vid, order[k])) if pool else None
            if best is None or near(fam(best)) or (fu[fam(best)] > 0 and any(fu[r] == 0 for r in refs)):
                best = variant(want_vid) or best
            if best and want_vid and not is_vid(best):                # a free still where motion was wanted → animate it
                best = next((k for k, a in A.items() if a.get("model") == "h3" and a.get("from") == best), None) \
                    or plate_from(best) or best
            pick = best or cur
            if pick != cur:
                swaps += 1
        if pick and pick in A and not is_vid(pick):                    # Oct 18: a still whose video exists plays the video;
            vid = next((k for k, a in A.items() if a.get("model") == "h3" and a.get("from") == pick), None)  # a motion beat
            pick = vid or (plate_from(pick) if want_vid else None) or pick                                   # gets one made
        if pick:
            b["plate"] = pick
            take(pick, fam(pick))
    if swaps or made:
        notes.append("no-repeat shot plan: %d beats re-assigned, %d new stills/plates (%d stills, %d plates in total)"
                     % (swaps, len(made), count("qimg"), count("h3")))
    th = ep.get("thumbnail") or {}
    if th.get("plate") and th["plate"] not in A and not str(th["plate"]).startswith("ref/"):
        th["plate"] = next((k for k in A if is_vis(k) and A[k]["model"] == "qimg"), th["plate"])
    return notes



NOUN = {"vo": "narration lines", "ref": "photos", "still": "stills", "plate": "video plates", "music": "music beds"}


def _asset_snapshot(p, ep, phase=None):
    """Progress straight from the files on disk (Oct 19: a resumed run counted from 0 and never showed the 10 plates
    already made the night before — explained_build skips cached files silently). Order = explained_build's: narration →
    photos → stills → plates → music → timeline. `shots` = every still/plate with done/now so the page can draw tiles."""
    d = _pub_dir(p)
    files = set(os.listdir(d)) if os.path.isdir(d) else set()
    rd = os.path.join(d, "ref")
    rfiles = set(os.listdir(rd)) if os.path.isdir(rd) else set()
    A = ep.get("assets") or {}
    refs = list(dict.fromkeys(r["name"] for r in ep.get("ref_urls") or []))[:X.MAX_REFS]
    vo_ids = [b["id"] for b in ep.get("beats") or [] if (b.get("say") or b.get("cap"))]
    vo_have = {n.split("_")[1] for n in files if n.startswith("vo_") and n.endswith(".wav")}
    stills = [k for k, a in A.items() if a.get("model") == "qimg"]
    plates = [k for k, a in A.items() if a.get("model") == "h3"]
    music = [m["name"] for m in ep.get("music") or []]
    total = {"vo": len(vo_ids), "ref": len(refs), "still": len(stills), "plate": len(plates), "music": len(music)}
    done = {"vo": sum(1 for i in vo_ids if i in vo_have), "ref": sum(1 for r in refs if r in rfiles),
            "still": sum(1 for k in stills if k + ".png" in files), "plate": sum(1 for k in plates if k + ".mp4" in files),
            "music": sum(1 for m in music if m + ".mp3" in files)}
    if phase is None:                     # the first kind with work left (refs that won't download don't hold it up)
        phase = next((k for k in ("vo", "still", "plate", "music") if done[k] < total[k]), "timeline")
    shots, now = [], None
    for kind, keys, ext in (("still", stills, ".png"), ("plate", plates, ".mp4")):
        for k in keys:
            ok = (k + ext) in files
            if not ok and now is None and phase == kind:
                now = k
            shots.append({"k": k, "kind": kind, "done": ok, "src": A[k].get("from") or A[k].get("lineart_of") or ""})
    return {"total": total, "done": done, "phase": phase, "now": now, "shots": shots, "at": time.time()}


def _assets(p):
    slug = _slug(p)
    if not p.get("session"):                         # runs from before Oct 19: give them their own session now
        _commit(p, X.session_for)
        p["session"] = (X.load(p["uid"], p["id"]) or {}).get("session") or ""
    ep_path = os.path.join(_ep_dir(p), "episode.json")
    ep = json.load(open(ep_path, encoding="utf-8"))
    if p.get("voice") and (ep.get("voice") or {}).get("id") != p["voice"]:     # Oct 24: the narrator picked on the page
        ep.setdefault("voice", {})["id"] = p["voice"]
        json.dump(ep, open(ep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if not ep.get("_normalized"):
        orig = os.path.join(_ep_dir(p), "episode.orig.json")
        if not os.path.exists(orig):
            shutil.copy2(ep_path, orig)
        ep, notes = normalize(ep)
        ep["_normalized"] = time.time()
        json.dump(ep, open(ep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        if notes:
            _commit(p, lambda q: X._log(q, "Prepared the script for the engine: " + "; ".join(notes)[:300]))
    # more reference photos → download them → drop the dead ones → no-repeat shot plan (re-run safely on every pass)
    if not ep.get("_refs_topped"):
        _more_refs(p, ep)
        ep["_refs_topped"] = time.time()
        json.dump(ep, open(ep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    _run(p, [PY, "-I", BUILD, slug, "refs", "--json"], 15 * 60)
    notes = ["dropped %d photos that wouldn't download (%s)" % (len(g), ", ".join(g)[:120]) for g in [_prune_refs(p, ep)] if g]
    notes += diversify(ep)
    json.dump(ep, open(ep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if notes:
        _commit(p, lambda q: X._log(q, "Shot plan: " + "; ".join(notes)[:300]))
    fails = []
    snap = lambda phase=None: _asset_snapshot(p, ep, phase)
    first = snap()
    total, cached = first["total"], dict(first["done"])
    first["cached"] = cached
    first["started"] = time.time()
    left = {k: total[k] - cached[k] for k in total}
    _commit(p, lambda q: (q.update(progress=first),
                          X._log(q, ("Making the assets in Media Lab: %d reference photos, %d stills, %d video plates, %d music "
                                     "beds, %d narration lines. This is the long part (~1-2 h on the GPU)."
                                     % (total["ref"], total["still"], total["plate"], total["music"], total["vo"]))
                                 if not any(cached.values()) else
                                 ("Picking up where it left off — already made: %s. Still to make: %s."
                                  % (", ".join("%d %s" % (cached[k], NOUN[k]) for k in total if cached[k]) or "nothing",
                                     ", ".join("%d %s" % (left[k], NOUN[k]) for k in total if left[k] > 0) or "nothing — just the timeline")),
                                 "done" if any(cached.values()) else "info")))
    last, phase = [0.0], [None]

    def on_line(line):
        if line.startswith("@@"):
            try:
                e = json.loads(line[2:])
            except Exception:
                return
            if e.get("stage") == "smooth":
                phase[0] = "timeline"
            elif not e.get("ok", True):
                fails.append("%s %s: %s" % (e.get("stage"), e.get("item"), e.get("why", "")[:80]))
        elif line.startswith("resolved "):
            phase[0] = "timeline"
        if line.startswith(("@@", "resolved ")) or time.time() - last[0] > 6:      # a finished item always shows
            last[0] = time.time()
            s = snap(phase[0])
            _commit(p, lambda q: q.update(progress=dict(q.get("progress") or {}, **s, fails=len(fails))))

    code, tail = _run(p, [PY, "-I", BUILD, slug, "all", "--json"], ASSET_TIMEOUT, on_line)
    if code != 0:
        raise RuntimeError("asset build failed (exit %s): %s" % (code, tail[-400:]))
    res = os.path.join(REMOTION, "src", "explained", "episodes", slug + ".json")
    if not os.path.isfile(res):
        raise RuntimeError("asset build finished but no resolved timeline was written")
    r = json.load(open(res, encoding="utf-8"))
    missing = [b["id"] for b in r["beats"] if (b.get("say") or b.get("cap")) and not b.get("vo")]
    if missing:
        raise RuntimeError("narration missing for %d beats (%s)" % (len(missing), ", ".join(missing[:6])))

    def ok(q):
        q.update(stage="render", heals={}, progress=dict(q.get("progress") or {}, **snap("done")),
                 length=round(r["total"], 1), asset_fails=fails[:20])
        X._log(q, "Assets done — %d:%02d of narration%s. Rendering the video, the thumbnail and the 3 Shorts next."
               % (int(r["total"]) // 60, int(r["total"]) % 60, (" (%d items fell back: %s)" % (len(fails), "; ".join(fails[:3]))) if fails else ""), "done")
    _commit(p, ok)


# ── stage 7: render ────────────────────────────────────────────────────────────────────────────────────────────────
def _loudness(path):
    tmp = os.path.join(tempfile.gettempdir(), "explained_mix_%d.wav" % os.getpid())
    subprocess.run([FF, "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", tmp],
                   creationflags=X._NOWIN, timeout=600)
    w = wave.open(tmp)
    a = array.array("h")
    a.frombytes(w.readframes(w.getnframes()))
    w.close()
    os.remove(tmp)
    blk = [a[i:i + 4000] for i in range(0, len(a), 4000)]
    db = [20 * math.log10(max(1e-9, math.sqrt(sum(x * x for x in b) / max(1, len(b))) / 32768)) for b in blk if b]
    return round(max(db), 1), round(sorted(db)[len(db) // 2], 1)


def _render(p):
    slug = _slug(p)
    res_path = os.path.join(REMOTION, "src", "explained", "episodes", slug + ".json")
    ep = json.load(open(res_path, encoding="utf-8"))
    files = set(ep.get("files") or [])
    spec = json.load(open(os.path.join(_ep_dir(p), "episode.json"), encoding="utf-8"))
    out = _out_dir(p)
    props_dir = os.path.join(out, "props")
    os.makedirs(props_dir, exist_ok=True)

    def asset_file(key):
        for n in ([key] if "." in key else [key + ".png", key + ".mp4"]):
            if n in files or os.path.isfile(os.path.join(_pub_dir(p), n)):
                return n
        return None

    stills = [k for k, a in spec["assets"].items() if a.get("model") == "qimg" and not k.startswith("la_") and asset_file(k)]
    tail = asset_file(stills[-1]) if stills else None
    ep["tailPlate"] = tail or ""
    jobs = []
    mp = os.path.join(props_dir, "main.json")
    json.dump({"ep": ep}, open(mp, "w", encoding="utf-8"))
    jobs.append(("main", ["render", "src/index.ts", "ExplainedEpisode", os.path.join(out, "main.mp4"), "--codec=h264", "--crf=18",
                          "--concurrency=6", "--props=" + mp]))
    th = spec.get("thumbnail") or {}
    plate = asset_file(th.get("plate") or "") or (asset_file(stills[0]) if stills else "")
    tp = os.path.join(props_dir, "thumb.json")
    json.dump({"base": ep["base"], "plate": plate if plate and plate.endswith((".png", ".jpg", ".jpeg", ".webp")) else (stills and asset_file(stills[0])) or "",
               "number": str(th.get("number", "")), "unit": str(th.get("unit", "")), "hook": str(th.get("hook", spec["meta"].get("title", ""))),
               "tag": "%s · EXPLAINED" % str(spec["meta"].get("title", "")).upper()[:34]}, open(tp, "w", encoding="utf-8"))
    jobs.append(("thumb", ["still", "src/index.ts", "ExplainedThumb", os.path.join(out, "thumb.jpg"), "--image-format=jpeg",
                           "--jpeg-quality=92", "--props=" + tp]))
    ids = {b["id"] for b in ep["beats"]}
    for i, s in enumerate((spec.get("shorts") or [])[:3]):
        cut = {"ids": [x for x in s.get("ids", []) if x in ids], "hook": s.get("hook") or s.get("title") or "", "tail": tail or ""}
        if len(cut["ids"]) < 1:
            continue
        sp = os.path.join(props_dir, "short%d.json" % (i + 1))
        json.dump({"ep": ep, "cut": cut}, open(sp, "w", encoding="utf-8"))
        jobs.append(("short%d" % (i + 1), ["render", "src/index.ts", "ExplainedShort", os.path.join(out, "short%d.mp4" % (i + 1)),
                                           "--codec=h264", "--crf=20", "--concurrency=6", "--props=" + sp]))
    try:   # give Chrome the RAM ComfyUI was holding (Oct 17: 26 GB cache → commit-limit crash)
        import urllib.request
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8188/free", data=b'{"unload_models":true,"free_memory":true}',
                                                      headers={"Content-Type": "application/json"}, method="POST"), timeout=20)
    except Exception:
        pass
    made = {}
    for name, args in jobs:
        if (os.path.isfile(args[3]) and os.path.getsize(args[3]) > 0
                and os.path.getmtime(args[3]) > os.path.getmtime(res_path)):  # rendered after the last asset/VO change:
            made[name] = args[3]                                              # keep it (a redo moves aside what it replaces)
            continue
        _commit(p, lambda q, n=name: X._log(q, "Rendering %s…" % {"main": "the main video", "thumb": "the thumbnail"}.get(n, "Short " + n[-1])))
        code, tl = _run(p, RCLI + args + ["--log=error"], RENDER_TIMEOUT)
        path = args[3]
        if code != 0 or not os.path.isfile(path):
            raise RuntimeError("render %s failed (exit %s): %s" % (name, code, tl[-300:]))
        made[name] = path
    peak, med = _loudness(made["main"])
    if peak > -12:
        raise RuntimeError("mix check failed: peaks at %.1f dB (something is drowning the narrator)" % peak)

    try:   # Oct 17 2026: the full video + Shorts land in the Media Lab library as soon as they're rendered
        spec = json.load(open(os.path.join(_ep_dir(p), "episode.json"), encoding="utf-8"))
        ttl = (spec.get("meta") or {}).get("title") or _slug(p)
        sh = spec.get("shorts") or []
        lib = {}
        for k, path in made.items():
            if k == "thumb":
                continue
            i = int(k[-1]) - 1 if k.startswith("short") else -1
            lbl = ("MIR EXPLAINED: " + ttl) if k == "main" else                 "MIR EXPLAINED Short: " + ((sh[i].get("title") or sh[i].get("hook")) if 0 <= i < len(sh) else ttl)
            lib[k] = _to_library(path, lbl, p["uid"], p.get("session"))
    except Exception as e:
        lib = {}
        _commit(p, lambda q: X._log(q, "Couldn't copy the renders into the library (%s)." % str(e)[:120], "warn"))

    def ok(q):
        q.update(renders={k: os.path.basename(v) for k, v in made.items()}, mix={"peak_db": peak, "median_db": med}, heals={},
                 stage="approve_final", library=lib)
        msg = "Rendered: main video (%d:%02d), thumbnail and %d Shorts. Mix peaks %.0f dB with the narrator on top." % (
            int(q.get("length", 0)) // 60, int(q.get("length", 0)) % 60, sum(1 for k in made if k.startswith("short")), peak)
        if q.get("auto"):
            X._log(q, msg + " Fully automatic: moving straight to the posts.", "done")
            q["stage"] = "publish"
        else:
            q["state"] = "waiting"
            X._log(q, msg + " Watch it on the EXPLAINED page, then approve it (or ask for changes).", "need")
    _commit(p, ok)


# ── stage 9: publish (drafts → the person approves the main video in Social → Shorts follow) ──────────────────────────
def _chapters(ep):
    out, seen = [], set()
    for b in ep["beats"]:
        if b.get("mode") == "card" or (b["ch"] not in seen and b["ch"] == 0):
            ch = next((c for c in ep["chapters"] if c["n"] == b["ch"]), None)
            if ch and b["ch"] not in seen:
                seen.add(b["ch"])
                t = int(b["start"])
                out.append("%d:%02d %s" % (t // 60, t % 60, ch["title"] if b["ch"] else "Intro"))
    return "\n".join(out)


def _lib_copy(p, key):
    """The library copy made right after the render (reused for the Social draft instead of a second copy)."""
    n = (p.get("library") or {}).get(key)
    return n if n and os.path.isfile(os.path.join(core.LIB, n)) else None


def _to_library(path, prompt, uid, session=""):
    name = core.new_name("explained", os.path.splitext(path)[1])
    shutil.copy2(path, os.path.join(core.LIB, name))
    core.index_add(name, {"prompt": prompt, "model": "explained", "created": time.time(), "user": uid, "source": "explained",
                          **({"session": session} if session else {})})
    return name


def _publish(p):
    import social
    slug, uid = _slug(p), p["uid"]
    out = _out_dir(p)
    spec = json.load(open(os.path.join(_ep_dir(p), "episode.json"), encoding="utf-8"))
    ep = json.load(open(os.path.join(REMOTION, "src", "explained", "episodes", slug + ".json"), encoding="utf-8"))
    posts = dict(p.get("posts") or {})
    yt = spec.get("youtube") or {}
    title = spec["meta"].get("title", slug)
    if not posts.get("main"):
        lib = _lib_copy(p, "main") or _to_library(os.path.join(out, "main.mp4"), "MIR EXPLAINED: " + title, uid, p.get("session"))
        d = social.create_draft(lib, ["youtube"], "MIR EXPLAINED long-form 16:9 YouTube video (NOT a Short): " + title,
                                owner=uid, fit="keep", auto_copy=False)
        desc = str(yt.get("description") or "").replace("{chapters}", _chapters(ep)).replace("{{chapters}}", _chapters(ep))
        if "MIR MEDIA LABS" not in desc:
            desc += "\n\nMade with MIR MEDIA LABS: https://github.com/MirCorp85/MirMediaLabs"
        if "AI-generated" not in desc:
            desc += "\nVisuals are AI-generated recreations based on real reference photos."
        social.update(d["id"], yt_format="video", yt_title=str(yt.get("title") or title)[:95], yt_description=desc[:4900],
                      yt_tags=list(yt.get("tags") or [])[:30], pinned_comment=str(yt.get("pinned_comment") or ""),
                      hook=str((spec.get("thumbnail") or {}).get("hook") or ""))
        posts["main"] = d["id"]
        _commit(p, lambda q: q.update(posts=dict(posts)))
    shorts = list((spec.get("shorts") or [])[:3])
    for i, s in enumerate(shorts):
        key = "short%d" % (i + 1)
        f = os.path.join(out, key + ".mp4")
        if posts.get(key) or not os.path.isfile(f):
            continue
        lib = _lib_copy(p, key) or _to_library(f, "MIR EXPLAINED Short: " + (s.get("title") or s.get("hook") or title), uid, p.get("session"))
        d = social.create_draft(lib, ["youtube", "instagram"], "MIR EXPLAINED YouTube Short + Instagram Reel (9:16)",
                                owner=uid, fit="crop", auto_copy=False)
        ttl = str(s.get("title") or s.get("hook") or title)
        social.update(d["id"], yt_format="short", yt_title=(ttl if "#shorts" in ttl.lower() else ttl + " #Shorts")[:95],
                      yt_description=(s.get("hook", "") + "\n\nFull breakdown on the channel: MIR MEDIA LABS\n"
                                      "Visuals are AI-generated recreations based on real reference photos.\n\n#Shorts")[:4900],
                      caption=(s.get("hook", "") + "\n\nFull breakdown on our YouTube (link in bio)."),
                      hashtags=[re.sub(r"\W", "", t.lower()) for t in (yt.get("tags") or [])[:8] if re.sub(r"\W", "", t)] + ["mirexplained", "mirmedialabs"],
                      yt_tags=list(yt.get("tags") or [])[:20], pinned_comment="Full breakdown on the channel.")
        posts[key] = d["id"]
        _commit(p, lambda q: q.update(posts=dict(posts)))
    # wait for Social to finish preparing, then set the custom thumbnail as the main video's cover
    deadline = time.time() + 900
    while time.time() < deadline:
        st = {k: (social.get(v) or {}).get("status") for k, v in posts.items()}
        if all(x in ("draft", "scheduled", "published", "failed") for x in st.values()):
            break
        if not _alive(p):
            return
        time.sleep(10)
    th = os.path.join(out, "thumb.jpg")
    main = social.get(posts["main"]) or {}
    if os.path.isfile(th) and main.get("media"):
        shutil.copy2(th, os.path.join(social.OUT, posts["main"] + ".jpg"))
    failed = [k for k, v in posts.items() if (social.get(v) or {}).get("status") == "failed"]
    if failed:
        raise RuntimeError("Social couldn't prepare %s" % ", ".join(failed))

    def ok(q):
        q.update(stage="done", state="waiting", awaiting="social_approval", posts=dict(posts), heals={})
        X._log(q, "Drafts are in Social: the main video + %d Shorts (YouTube + Instagram). Approve the MAIN video in Social to "
                  "publish it — the Shorts then go out one per day at 6 PM by themselves." % (len(posts) - 1), "need")
    _commit(p, ok)


def _approve_final(p):
    if p.get("auto"):
        _commit(p, lambda q: q.update(stage="publish"))
    else:
        _commit(p, lambda q: q.update(state="waiting"))


# ── after the person approves the main video in Social: schedule the Shorts (the one approval covers the batch) ────
def _follow_social():
    import social
    while True:
        time.sleep(60)
        try:
            for u in (os.listdir(X.RUNS) if os.path.isdir(X.RUNS) else []):
                d = os.path.join(X.RUNS, u)
                if not os.path.isdir(d):
                    continue
                for n in os.listdir(d):
                    if not n.endswith(".json"):
                        continue
                    p = X.load(u, n[:-5])
                    if not p or p.get("awaiting") != "social_approval":
                        continue
                    posts = p.get("posts") or {}
                    main = social.get(posts.get("main", "")) or {}
                    if main.get("status") not in ("scheduled", "published") or not main.get("approved_at"):
                        continue
                    base = datetime.fromtimestamp(max(time.time(), main.get("schedule_at") or time.time()))
                    day0 = base.replace(hour=SHORT_HOUR, minute=0, second=0, microsecond=0)
                    if day0 <= base:
                        day0 += timedelta(days=1)
                    when = []
                    for i, k in enumerate(sorted(x for x in posts if x.startswith("short"))):
                        sp = social.get(posts[k]) or {}
                        if sp.get("status") == "draft":
                            ts = (day0 + timedelta(days=i)).timestamp()
                            social.approve(posts[k], ts)
                            when.append("%s %s" % (k, time.strftime("%a %I %p", time.localtime(ts))))

                    def fin(q):
                        q.update(awaiting=None, state="done")
                        X._log(q, "You approved the main video — the Shorts are scheduled: %s. That's the whole episode."
                               % (", ".join(when) or "already handled"), "done")
                    X._mut(u, p["id"], fin)
        except Exception as e:      # never let the follower die
            print("[explained] follow_social:", e)


_FOLLOW = {"on": False}


def _backfill_library():
    """Runs rendered before Oct 17 2026 only reached the library at publish — copy their main video + Shorts in now."""
    for u in (os.listdir(X.RUNS) if os.path.isdir(X.RUNS) else []):
        if not os.path.isdir(os.path.join(X.RUNS, u)):
            continue
        for p in X._all(u):
            if not p.get("renders") or p.get("library") or not (p.get("topic") or {}).get("slug"):
                continue
            try:
                spec = json.load(open(os.path.join(_ep_dir(p), "episode.json"), encoding="utf-8"))
                ttl, sh, lib = (spec.get("meta") or {}).get("title") or _slug(p), spec.get("shorts") or [], {}
                for k, fn in p["renders"].items():
                    path = os.path.join(_out_dir(p), fn)
                    if k == "thumb" or not os.path.isfile(path):
                        continue
                    i = int(k[-1]) - 1 if k.startswith("short") else -1
                    lib[k] = _to_library(path, ("MIR EXPLAINED: " + ttl) if k == "main" else "MIR EXPLAINED Short: "
                                         + ((sh[i].get("title") or sh[i].get("hook")) if 0 <= i < len(sh) else ttl), p["uid"], p.get("session"))
                X._mut(p["uid"], p["id"], lambda q: q.update(library=lib))
            except Exception as e:
                print("[EXPLAINED] library backfill failed for", p.get("id"), e)


def install():
    X.STAGE_HANDLERS.update(assets=_assets, render=_render, approve_final=_approve_final, publish=_publish)
    threading.Thread(target=_backfill_library, daemon=True, name="explained-libfill").start()
    if not _FOLLOW["on"]:
        _FOLLOW["on"] = True
        threading.Thread(target=_follow_social, daemon=True, name="explained-social").start()
