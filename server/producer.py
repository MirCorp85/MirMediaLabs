"""PRODUCER — MirAI's one-sentence pipeline: "make a kids musical about …" → a finished episode + a YouTube post
waiting for approval. It never renders by itself; it drives the studios that already do, in order:
  brief (cloud brain → cast of 2-5, 1-3 places, song idea) → a new SERIES with that cast →
  picture queue (hero + turnaround per character, place + place sheet, cast lineup) →
  [optional gate: the person approves the look before the costly video] →
  the SERIES runner renders the episode (song → shots → first frames → shots → assemble) →
  a VIRAL-Ω draft (title / description / tags, made-for-kids) that still needs Approve.
Longer-than-one-clip pieces come out seamless because the series director chains "continue" shots off the exact
last frame the edit cuts on (series.slot_copy + the H3 extend anchor) and only cuts on purpose.

A production is a PROJECT: /api/produce/<id>/project groups everything it made (cast, world, song, shots, final,
post) and lays out its step timeline. It is crash-proof and self-healing:
  • state lives in data/produce/<user>/<id>.json, written after every change; on start the lab picks every running
    production back up (the series runner re-derives the next step from what is SAVED, so nothing is redone);
  • a watchdog narrates each finished step, diagnoses failures (GPU out of memory → free VRAM, ComfyUI down → wait
    for it, step stuck → restart that step, engine/network hiccup → retry) and carries on by itself; only after
    MAX_HEAL attempts on the same problem does it stop and ask the person;
  • every event goes to /api/produce/feed, which MirAI's voice, the MirOS app and the Production tab read.

Identical in the MirOS copy (miros_mlab) — copy, never import across.
"""
import json
import os
import re
import threading
import time
import traceback
import uuid

try:
    from . import core, series, series_run as runner, series_presets as presets, comfy
except ImportError:
    import core
    import series
    import series_run as runner
    import series_presets as presets
    import comfy

PROD = os.path.join(core.DATA, "produce")
MAX_CAST, MAX_LOCS = 5, 3
TICK = 5.0
MAX_HEAL = 4                          # self-fix attempts on the same problem before asking the person
STALL_S = {"chunk": 50 * 60, "keyframe": 20 * 60, "song": 30 * 60, "default": 40 * 60}
COOL = {"memory": 90, "comfy": 60, "stall": 20, "default": 45}
STAGES = ("brief", "series", "pictures", "approve_look", "episode", "publish", "done")
LABEL = {"brief": "writing the brief", "series": "setting up the series", "pictures": "drawing the cast and the world",
         "approve_look": "waiting for you to approve the look", "episode": "rendering the episode",
         "publish": "preparing the YouTube post", "done": "finished"}
HK = {}
_ACTIVE = set()
_GUARD = threading.Lock()
_STARTED = False

BRIEF_SYS = """You are the showrunner of a children's music-video studio. Turn the request into a production brief.
Rules: {cast_min}-{cast_max} characters (use the number asked for if given), 1-{locs} locations, one original song idea,
pre-school friendly, no existing brands / shows / characters / artists. Return ONE JSON object:
{{"title": "<show title, <=60 chars>", "premise": "<2 sentences>", "lesson": "<one gentle lesson>",
  "style": "<one of: {styles}>", "structure": "<one of: {structures}>", "aspect": "16:9" or "9:16",
  "length": <seconds 40-150>,
  "characters": [{{"name": "<short>", "desc": "<look: species/body, colours, outfit, one signature detail; 40-90 words>",
                   "voice": "<voice in <=6 words>"}}],
  "locations": [{{"name": "<short>", "desc": "<the place, 30-70 words>"}}],
  "episode": {{"title": "<episode title>", "idea": "<what happens across the song, 3-5 sentences, who sings what>"}},
  "youtube_keywords": ["<5-8 search keywords>"]}}"""


# ── storage ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _dir(uid):
    d = os.path.join(PROD, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "owner")))
    os.makedirs(d, exist_ok=True)
    return d


def load(uid, pid):
    if not re.match(r"^[a-f0-9]{12}$", str(pid or "")):
        return None
    try:
        with open(os.path.join(_dir(uid), pid + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(uid, p):
    p["updated"] = time.time()
    path = os.path.join(_dir(uid), p["id"] + ".json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(p, f)
    os.replace(path + ".tmp", path)
    return p


def _all(uid):
    out = []
    for n in os.listdir(_dir(uid)):
        if n.endswith(".json"):
            p = load(uid, n[:-5])
            if p:
                out.append(p)
    return sorted(out, key=lambda p: -p.get("created", 0))


def listing(uid):
    return [public(p) for p in _all(uid)]


def _title(p):
    return ((p.get("brief") or {}).get("title") or p.get("prompt") or "production")[:60]


def _log(p, msg, lvl="info"):
    """lvl: info (narration) · done (milestone) · warn (MirAI is fixing something) · error (needs the person) ·
    need (waiting for the person's decision). Everything but info is an alert."""
    now = time.time()
    p.setdefault("log", []).append({"t": now, "seq": int(now * 1000), "msg": str(msg)[:400], "lvl": lvl})
    p["log"] = p["log"][-200:]
    try:
        if p.get("sid"):
            series.log_event(p["uid"], p["sid"], "producer", msg=str(msg)[:200], lvl=lvl)
    except Exception:
        pass
    if lvl != "info":
        try:
            (HK.get("push") or (lambda *a, **k: None))(p["uid"], "produce", "%s — %s" % (_title(p), lvl.upper()),
                                                         str(msg)[:160], production=p["id"])
        except Exception:
            pass


def feed(uid, since=0):
    """Every production event newer than `since` (ms), oldest first — for MirAI's voice, the app's alerts, the tab."""
    out = []
    for p in _all(uid):
        for e in p.get("log") or []:
            if e.get("seq", int(e.get("t", 0) * 1000)) > since:
                out.append(dict(e, seq=e.get("seq", int(e.get("t", 0) * 1000)), production=p["id"], title=_title(p),
                                state=p.get("state"), stage=p.get("stage")))
    return sorted(out, key=lambda e: e["seq"])[-100:]


# ── the project view: timeline + every piece of media, grouped ─────────────────────────────────────────────────────
def _series(p):
    try:
        d = series.load(p["uid"], p["sid"]) if p.get("sid") else None
    except Exception:
        d = None
    ep = series._find(d, "episodes", p.get("eid")) if d else None
    return d or {}, ep or {}


def steps(p):
    d, ep = _series(p)
    order = STAGES.index(p.get("stage")) if p.get("stage") in STAGES else 0
    pics = _pictures(p)
    chunks = ep.get("chunks") or []
    shots_done = sum(1 for c in chunks if c.get("clip") and not c.get("stale"))
    run = {}
    try:
        run = runner.load_run(p["uid"], p["sid"]) or {} if p.get("sid") else {}
    except Exception:
        pass
    cur = (run.get("step") or {})

    def st(done, active):
        if done:
            return "done"
        if active:
            return "fail" if p.get("state") in ("paused", "cancelled") else ("wait" if p.get("state") == "waiting" else "now")
        return "todo"
    rows = [
        {"key": "brief", "label": "Brief", "state": st(order > 0, order == 0),
         "detail": _title(p) if p.get("brief") else "writing it"},
        {"key": "pictures", "label": "Cast & world", "state": st(order > 2, order in (1, 2)),
         "detail": "%d / %d pictures" % (pics["done"], pics["total"]) if pics["total"] else ""},
        {"key": "approve_look", "label": "Approve the look", "state": st(order > 3, order == 3),
         "detail": "your call" if order == 3 else ""},
        {"key": "song", "label": "Song + vocals", "state": st(bool(ep.get("song")), order == 4 and not ep.get("song")),
         "detail": (cur.get("kind") in ("write", "song") and "recording now") or ("ready" if ep.get("song") else "")},
        {"key": "shots", "label": "Shots", "state": st(bool(chunks) and shots_done == len(chunks),
                                                      order == 4 and bool(ep.get("song")) and not ep.get("final")),
         "detail": ("%d / %d" % (shots_done, len(chunks)) if chunks else "") +
                   (" · now shot %d" % (cur["i"] + 1) if cur.get("kind") in ("chunk", "keyframe") and cur.get("i") is not None else "")},
        {"key": "assemble", "label": "Final edit", "state": st(bool(ep.get("final")), cur.get("kind") == "assemble"),
         "detail": ""},
        {"key": "publish", "label": "YouTube post", "state": st(order > 5, order == 5),
         "detail": "waiting for your Approve in Social" if p.get("post") else ""},
    ]
    return rows


def _pictures(p):
    try:
        items = [x for x in runner.queue_status(p["uid"], p["sid"])["items"] if x["id"] in (p.get("qids") or [])] \
            if p.get("sid") else []
    except Exception:
        items = []
    return {"done": sum(x["state"] == "done" for x in items), "total": len(items),
            "failed": [x["label"] for x in items if x["state"] == "error"]}


def project(p):
    """Everything this production made, grouped — refs are reference pictures (/refs, /refthumb), lib items are
    library files (/media, /thumb)."""
    d, ep = _series(p)

    def r(name, label):
        return {"kind": "ref", "name": name, "label": label} if name else None

    def lib(name, label):
        return {"kind": "lib", "name": name, "label": label} if name else None
    def tag(x, step, kind, xid):
        if x:
            x["redo"] = {"step": step, "target": {"kind": kind, "id": xid}}
        return x
    cast = []
    for c in d.get("characters") or []:
        cast += [x for x in (tag(r(c.get("hero"), c.get("name")), "cast", "hero", c["id"]),
                             tag(r(c.get("sheet"), (c.get("name") or "") + " · turnaround"), "cast", "sheet", c["id"])) if x]
    if d.get("lineup"):
        cast.append(r(d["lineup"], "cast lineup"))
    world = []
    for l in d.get("locations") or []:
        world += [x for x in (tag(r(l.get("image"), l.get("name")), "world", "location", l["id"]),
                              tag(r(l.get("sheet"), (l.get("name") or "") + " · sheet"), "world", "locsheet", l["id"])) if x]
    shots = []
    for c in ep.get("chunks") or []:
        if c.get("clip"):
            x = lib(c["clip"], "shot %d%s" % (c["i"] + 1, " (re-rendering)" if c.get("stale") else ""))
            x["redo"] = {"step": "shot", "target": c["i"]}
            shots.append(x)
        elif c.get("key"):
            shots.append(r(c["key"], "shot %d · first frame" % (c["i"] + 1)))
    groups = [{"title": "Cast", "items": cast}, {"title": "World", "items": world},
              {"title": "Song", "items": [dict(x, redo={"step": "song"}) for x in (lib(ep.get("song"), (ep.get("song_text") or {}).get("title") or "the song"),) if x]},
              {"title": "Shots", "items": shots},
              {"title": "Final", "items": [x for x in (lib(ep.get("final"), ep.get("title") or "episode"),) if x]}]
    out = public(p)
    out.update(steps=steps(p), groups=[g for g in groups if g["items"]], series=d.get("name"),
               chunks=[{"i": c["i"], "has": bool(c.get("clip")), "stale": bool(c.get("stale"))} for c in ep.get("chunks") or []])
    return out


def public(p):
    out = {k: p.get(k) for k in ("id", "prompt", "state", "stage", "error", "created", "updated", "sid", "eid",
                                 "brief", "post", "final", "checkpoints")}
    out["title"] = _title(p)
    out["label"] = LABEL.get(p.get("stage"), p.get("stage"))
    out["log"] = (p.get("log") or [])[-30:]
    out["heals"] = sum((p.get("heals") or {}).values())
    if p.get("sid") and p.get("stage") == "episode":
        try:
            out["run"] = runner.status(p["uid"], p["sid"]).get("progress")
        except Exception:
            pass
    if p.get("sid") and p.get("stage") == "pictures":
        out["pictures"] = _pictures(p)
    return out


# ── control ────────────────────────────────────────────────────────────────────────────────────────────────────────
def start(uid, prompt, cast_max=MAX_CAST, checkpoints=True, platforms=("youtube",)):
    prompt = series._clean(prompt, 2000)
    if not prompt:
        raise ValueError("tell me what to make")
    p = {"id": uuid.uuid4().hex[:12], "uid": uid, "prompt": prompt, "state": "running", "stage": "brief",
         "cast_max": max(1, min(MAX_CAST, int(cast_max or MAX_CAST))), "checkpoints": bool(checkpoints),
         "platforms": [x for x in platforms if x in ("youtube", "instagram", "tiktok", "facebook")] or ["youtube"],
         "created": time.time(), "error": None, "log": [], "heals": {}}
    _log(p, "Production started: " + prompt[:160], "done")
    save(uid, p)
    _activate(uid, p["id"])
    return public(p)


def delete(uid, pid, with_series=True):
    """Delete a project: stop anything it is rendering, then move its record (and, by default, its series) to the
    lab's trash. Library files it made stay in the library."""
    p = load(uid, pid)
    if not p:
        raise ValueError("no such production")
    import shutil
    os.makedirs(core.TRASH, exist_ok=True)
    if p.get("sid"):
        try:
            runner.queue_cancel(uid, p["sid"], "all")
            _stop_runner(p)
        except Exception:
            pass
        if with_series:
            sp = series._path(uid, p["sid"])
            if sp and os.path.isfile(sp):
                shutil.move(sp, os.path.join(core.TRASH, "series_%s_%d.json" % (p["sid"], int(time.time()))))
    shutil.move(os.path.join(_dir(uid), pid + ".json"), os.path.join(core.TRASH, "production_%s_%d.json" % (pid, int(time.time()))))
    with _GUARD:
        _ACTIVE.discard((uid, pid))
    return {"ok": True}


def control(uid, pid, action, body=None):
    body = body or {}
    if action == "delete":
        return delete(uid, pid, body.get("series", True) is not False)
    if action == "redo_step" and body.get("step") == "assemble":
        action, body = "redo", {}
    p = load(uid, pid)
    if not p:
        raise ValueError("no such production")
    if action == "approve":
        if p["stage"] != "approve_look":
            raise ValueError("nothing is waiting for approval")
        p.update(stage="episode", state="running", error=None)
        _log(p, "Look approved — I'm writing and recording the song next, then the shots.", "done")
    elif action == "pause":
        p["state"] = "paused"
        if p.get("sid") and p["stage"] == "episode":
            runner.pause(uid, p["sid"], "the producer was paused")
        _log(p, "Paused by you. Tap Resume and I carry on from exactly here.")
    elif action in ("resume", "retry"):
        p.update(state="running" if p["stage"] != "approve_look" else "waiting", error=None, retry_at=0)
        if action == "retry":
            p["heals"] = {}
        if p.get("sid") and p["stage"] == "episode" and (runner.load_run(uid, p["sid"]) or {}).get("state") in ("paused", "stopped"):
            runner.control(uid, p["sid"], "retry")
        _log(p, "Resuming from %s." % LABEL.get(p["stage"], p["stage"]))
    elif action == "redo":                         # re-render one shot (or the final edit) from its saved inputs
        d, ep = _series(p)
        i = body.get("i")
        if not ep:
            raise ValueError("the episode isn't set up yet")
        with series.locked(uid, p["sid"]):
            d = series.load(uid, p["sid"])
            ep = series._find(d, "episodes", p["eid"])
            if i is not None:
                ch = next((c for c in ep.get("chunks") or [] if c["i"] == int(i)), None)
                if not ch:
                    raise ValueError("no shot %s" % (int(i) + 1))
                ch["stale"] = True
            ep.pop("final", None)
            series.save(uid, d)
        if p.get("post"):
            p["post_old"] = p.pop("post")
        p.update(stage="episode", state="running", error=None, final=None, retry_at=0)
        if (runner.load_run(uid, p["sid"]) or {}).get("state") in ("paused", "stopped", "done", None):
            runner.control(uid, p["sid"], "start", p["eid"])
            p["seen_done"] = len((runner.load_run(uid, p["sid"]) or {}).get("done") or [])
        _log(p, ("Re-rendering shot %d, then a fresh final edit." % (int(i) + 1)) if i is not None
             else "Re-doing the final edit.", "done")
    elif action == "redo_step":
        _redo_step(p, str(body.get("step") or ""), body.get("target"), series._clean(body.get("note"), 600))
    elif action == "cancel":
        if p.get("sid"):
            runner.queue_cancel(uid, p["sid"], "all")
            if runner.load_run(uid, p["sid"]):
                runner.control(uid, p["sid"], "stop")
        p["state"] = "cancelled"
        _log(p, "Cancelled. Everything made so far stays in the project.")
    else:
        raise ValueError("unknown action")
    save(uid, p)
    _activate(uid, pid)
    return public(p)


def _stop_runner(p):
    """Stop the episode render (and its GPU job) before changing what it renders from."""
    if p.get("sid"):
        try:
            if (runner.load_run(p["uid"], p["sid"]) or {}).get("state") in ("running", "paused"):
                runner.control(p["uid"], p["sid"], "stop")
        except Exception:
            pass


def _redo_step(p, step, target, note):
    """Go back to one step and make it again, with the person's changes (note). Everything that depended on it
    is re-made after it; everything before it is kept."""
    uid = p["uid"]
    with_note = (" — with your changes: “%s”" % note) if note else ""
    if step == "brief":                                  # a new brief → a fresh series (the old one stays in Series)
        _stop_runner(p)
        if p.get("sid"):
            runner.queue_cancel(uid, p["sid"], "all")
        if note:
            p["prompt"] = (p["prompt"] + "\nChanges: " + note)[:2000]
        for k in ("brief", "sid", "eid", "qids", "final", "post", "pics_said", "pics_named", "pic_retried", "seen_done"):
            p.pop(k, None)
        p.update(stage="brief", state="running", error=None, heals={}, retry_at=0)
        _log(p, "Rewriting the brief from scratch%s. The old version stays in the Series studio." % with_note, "done")
        return
    if not p.get("sid"):
        raise ValueError("that step hasn't been made yet")
    d, ep = _series(p)
    if step in ("cast", "world", "pictures"):            # redraw one picture (target = {kind, id}) or all of them
        kinds = {"cast": ("hero", "sheet"), "world": ("location", "locsheet")}
        items = []
        with series.locked(uid, p["sid"]):
            d = series.load(uid, p["sid"])
            tgt = target or {}
            for key, pair in (("characters", kinds["cast"]), ("locations", kinds["world"])):
                if step == "cast" and key != "characters" or step == "world" and key != "locations":
                    continue
                for x in d.get(key) or []:
                    if tgt.get("id") and x["id"] != tgt["id"]:
                        continue
                    if note and (tgt.get("id") or step != "pictures"):
                        x["desc"] = series._clean((x.get("desc") or "") + " " + note, 1200)
                    want = pair if not tgt.get("kind") else ((tgt["kind"],) if tgt["kind"] in pair[1:] else pair)
                    items += [{"kind": k, "target": x["id"], "label": "%s · %s" % (x.get("name"), "turnaround" if k == "sheet" else
                               "sheet" if k == "locsheet" else "design")} for k in want]
            series.save(uid, d)
        if step != "world" and len(d.get("characters") or []) >= 2 and (not target or (target or {}).get("kind") in (None, "hero", "sheet")):
            items.append({"kind": "lineup", "label": "cast lineup"})
        if not items:
            raise ValueError("nothing to redraw there")
        before = {x["id"] for x in runner.queue_status(uid, p["sid"])["items"]}
        for k in range(0, len(items), 6):
            runner.enqueue(uid, p["sid"], items[k:k + 6])
        p["qids"] = [x["id"] for x in runner.queue_status(uid, p["sid"])["items"] if x["id"] not in before]
        p.update(stage="pictures", state="running", error=None, heals={}, retry_at=0, pics_said=0, pics_named=[], pic_retried=[])
        if ep.get("song") or ep.get("chunks"):
            _stop_runner(p)
        _log(p, "Redrawing %s%s. I'll ask you to approve the look again before any video." % (
            ", ".join(sorted({i["label"].split(" · ")[0] for i in items})), with_note), "done")
        return
    if step == "song":                                   # new lyrics + recording → the shots are re-cut to it
        _stop_runner(p)
        with series.locked(uid, p["sid"]):
            d = series.load(uid, p["sid"])
            e = series._find(d, "episodes", p["eid"])
            if note:
                e["idea"] = series._clean((e.get("idea") or "") + "\nSong changes: " + note, 3000)
            for k in ("song", "song_text", "sections", "chunks", "final", "words", "song_secs"):
                e.pop(k, None)
            series.save(uid, d)
        p.update(stage="episode", state="running", error=None, final=None, heals={}, retry_at=0)
        p.pop("post", None)
        _log(p, "Writing and recording a new song%s — then every shot is re-cut to it." % with_note, "done")
        return
    if step in ("shot", "shots"):                        # one shot (target = index) or every shot
        _stop_runner(p)
        with series.locked(uid, p["sid"]):
            d = series.load(uid, p["sid"])
            e = series._find(d, "episodes", p["eid"])
            chunks = e.get("chunks") or []
            pick = [c for c in chunks if target is None or c["i"] == int(target)]
            if not pick:
                raise ValueError("no such shot")
            for c in pick:
                if note:
                    c["shot"] = series._clean((c.get("shot") or "") + " Change: " + note, 1500)
                c["stale"] = True
                if c.get("link") == "cut" or c["i"] == 0:
                    c.pop("key", None)                   # its first frame is redrawn too
            e.pop("final", None)
            series.save(uid, d)
        p.update(stage="episode", state="running", error=None, final=None, heals={}, retry_at=0)
        p.pop("post", None)
        _log(p, ("Re-rendering shot %d%s, then a fresh final edit." % (int(target) + 1, with_note)) if target is not None
             else "Re-rendering every shot%s, then a fresh final edit." % with_note, "done")
        return
    if step == "publish":
        if p.get("post") and HK.get("social_rewrite"):
            HK["social_rewrite"](p["post"], note)
            _log(p, "Rewriting the post's title, description and tags%s. It's back in Social for your Approve." % with_note, "done")
        elif p.get("final"):
            p.pop("post", None)
            p.update(stage="publish", state="running", error=None, retry_at=0)
            if note:
                p.setdefault("brief", {})["post_note"] = note
            _log(p, "Drafting the post again%s." % with_note, "done")
        else:
            raise ValueError("the episode isn't finished yet")
        return
    raise ValueError("unknown step")


def _activate(uid, pid):
    global _STARTED
    with _GUARD:
        _ACTIVE.add((uid, pid))
        if not _STARTED:
            _STARTED = True
            threading.Thread(target=_loop, daemon=True, name="producer").start()


def setup(hk):
    HK.update(hk)
    for u in (os.listdir(PROD) if os.path.isdir(PROD) else []):     # carry on after a restart / crash
        for n in os.listdir(os.path.join(PROD, u)):
            if not n.endswith(".json"):
                continue
            p = load(u, n[:-5])
            if p and p.get("state") in ("running", "paused") and p.get("stage") not in ("done",):
                if p.get("state") == "running" or p.get("auto_paused"):
                    _log(p, "MirOS came back up — picking %s back up at %s, right where it stopped."
                         % (_title(p), LABEL.get(p.get("stage"), "")), "warn")
                    p.update(state="running", auto_paused=False, retry_at=time.time() + 20)
                    save(p["uid"], p)
                    _activate(p["uid"], p["id"])


def _loop():
    while True:
        time.sleep(TICK)
        with _GUARD:
            todo = list(_ACTIVE)
        for uid, pid in todo:
            try:
                p = load(uid, pid)
                if not p or p.get("state") != "running":
                    with _GUARD:
                        _ACTIVE.discard((uid, pid))
                    continue
                if p.get("retry_at", 0) > time.time():
                    continue
                _tick(p)
            except Exception as e:
                traceback.print_exc()
                p = load(uid, pid)
                if p:
                    _heal(p, str(e), where=LABEL.get(p.get("stage"), "this step"))
                    save(uid, p)


# ── self-healing ───────────────────────────────────────────────────────────────────────────────────────────────────
def _comfy_up():
    try:
        return core.requests.get(comfy.BASE + "/system_stats", timeout=5).ok
    except Exception:
        return False


def _free_gpu():
    try:
        core.requests.post(comfy.BASE + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
    except Exception:
        pass


def _diagnose(err):
    e = str(err or "").lower()
    if re.search(r"out of memory|oom|cuda|allocat", e):
        return "memory", "the GPU ran out of memory", "I freed the GPU memory and will try that step again"
    if re.search(r"refused|unreachable|comfy|connection|aborted|restart", e):
        return "comfy", "the render engine (ComfyUI) wasn't answering", "I'll wait for it and try again"
    if re.search(r"timed out|timeout|stuck|stall", e):
        return "stall", "the step took far too long", "I restarted that step"
    if re.search(r"llama-server|ollama|engine|11434|model", e):
        return "engine", "the writing engine hiccuped", "I'll retry with the fallback engine"
    if re.search(r"song file is gone|song .* missing", e):
        return "song", "the song file went missing", "I'll record the song again"
    return "default", "something went wrong (%s)" % str(err)[:140], "I'll try that step again"


def _heal(p, err, where="this step"):
    """Diagnose → fix → schedule a retry; after MAX_HEAL tries on the same kind of problem, stop and ask."""
    kind, why, fix = _diagnose(err)
    h = p.setdefault("heals", {})
    h[kind] = h.get(kind, 0) + 1
    if h[kind] > MAX_HEAL:
        p.update(state="paused", error=str(err)[:300], auto_paused=False)
        _log(p, "I couldn't get past %s on my own: %s, %d times in a row. I need you — check the Production tab, "
                "then tap Retry." % (where, why, MAX_HEAL), "error")
        return False
    if kind == "memory":
        _free_gpu()
    if kind == "song" and p.get("sid"):
        try:
            with series.locked(p["uid"], p["sid"]):
                d = series.load(p["uid"], p["sid"])
                ep = series._find(d, "episodes", p.get("eid"))
                if ep:
                    ep.pop("song", None)
                    series.save(p["uid"], d)
        except Exception:
            pass
    p.update(state="running", error=None, retry_at=time.time() + COOL.get(kind, COOL["default"]), heal_kind=kind)
    _log(p, "%s failed — %s. %s (fix %d of %d)." % (where[:1].upper() + where[1:], why, fix, h[kind], MAX_HEAL), "warn")
    return True


def _step_name(st):
    if not st:
        return "the next step"
    lbl = runner.LABEL.get(st.get("kind"), st.get("kind") or "step")
    return "%s %d" % (lbl, st["i"] + 1) if st.get("i") is not None else lbl


def _watch_episode(p, run, ep):
    """Narrate finished steps, spot failures and stalls, and fix them."""
    done = run.get("done") or []
    seen = p.get("seen_done", 0)
    total = len(ep.get("chunks") or [])
    for x in done[seen:]:
        what = _step_name(x)
        secs = x.get("secs") or 0
        extra = (" of %d" % total) if x.get("kind") == "chunk" and total else ""
        _log(p, "Finished %s%s%s." % (what, extra, (" (%d min)" % round(secs / 60)) if secs >= 60 else ""),
             "done" if x.get("kind") in ("song", "assemble") else "info")
    p["seen_done"] = len(done)
    if seen != len(done):
        p["heals"] = {k: v for k, v in (p.get("heals") or {}).items() if k in ("comfy",)}   # progress → fresh budget
    state, st = run.get("state"), run.get("step") or {}
    if p.pop("pending_retry", False) and state == "paused":      # the cool-down after a fix is over: go again
        runner.control(p["uid"], p["sid"], "retry")
        _log(p, "Trying %s again." % (_step_name(st) if st else "the episode"))
        return
    if state == "paused" and run.get("error"):
        if _heal(p, run["error"], where=_step_name(st) if st else "the episode"):
            p["pending_retry"] = True
        return
    if state != "running":
        return
    if st.get("kind") in runner.GPU_KINDS and not _comfy_up():
        if time.time() - p.get("comfy_down_said", 0) > 600:
            p["comfy_down_said"] = time.time()
            _log(p, "The render engine (ComfyUI) isn't answering. I'll keep waiting and carry on the moment it's back — "
                    "if it stays down, restart ComfyUI.", "warn")
        p["watch"] = None
        return
    if p.get("comfy_down_said"):
        p.pop("comfy_down_said")
        _log(p, "ComfyUI is back — carrying on with %s." % _step_name(st))
    pct = None
    if st.get("job") and HK.get("job"):
        j = HK["job"](st["job"]) or {}
        pct = (j.get("progress") or {}).get("pct")
    key = [len(done), st.get("kind"), st.get("i"), pct]
    w = p.get("watch") or {}
    if w.get("key") != key:
        p["watch"] = {"key": key, "t": time.time()}
        return
    limit = STALL_S.get(st.get("kind"), STALL_S["default"])
    if st.get("kind") and time.time() - w["t"] > limit:
        p["watch"] = None
        if st.get("job") and HK.get("cancel"):
            try:
                HK["cancel"](st["job"])
            except Exception:
                pass
        runner.control(p["uid"], p["sid"], "cancel")
        if _heal(p, "stuck: no progress for %d min" % (limit // 60), where=_step_name(st)):
            p["pending_retry"] = True


# ── the stages ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _brief(p):
    sys_ = BRIEF_SYS.format(cast_min=min(2, p["cast_max"]), cast_max=p["cast_max"], locs=MAX_LOCS,
                            styles=", ".join(s["id"] for s in presets.STYLES),
                            structures=", ".join(s["id"] for s in presets.STRUCTURES if s["id"] != "custom"))
    j = series._json(series._ask("Request: " + p["prompt"], sys_, want_json=True, role="director", timeout=300))
    chars = [c for c in j.get("characters") or [] if isinstance(c, dict) and c.get("name")][:p["cast_max"]]
    locs = [l for l in j.get("locations") or [] if isinstance(l, dict) and l.get("name")][:MAX_LOCS]
    if not chars:
        raise RuntimeError("the brief came back without characters (engine returned no usable JSON)")
    j["characters"], j["locations"] = chars, locs or [{"name": "Stage", "desc": "a bright, cosy stage set"}]
    return j


def _tick(p):
    uid, st = p["uid"], p["stage"]
    if st == "brief":
        p["brief"] = _brief(p)
        b = p["brief"]
        _log(p, "Brief ready: “%s” — %s, in %s." % (b.get("title"), ", ".join(c["name"] for c in b["characters"]),
                                                      " and ".join(l["name"] for l in b["locations"])), "done")
        p["stage"], p["heals"] = "series", {}
        save(uid, p)
    elif st == "series":
        b = p["brief"]
        chars = [{"id": series.new_id(), "name": c.get("name"), "desc": c.get("desc"), "voice": c.get("voice")}
                 for c in b["characters"]]
        locs = [{"id": series.new_id(), "name": l.get("name"), "desc": l.get("desc")} for l in b["locations"]]
        ep = b.get("episode") or {}
        eid = series.new_id()
        body = {"name": b.get("title") or "MirAI production", "audience": "pre-school",
                "setup": {"structure": b.get("structure") or "musical", "style": b.get("style") or "animated3d",
                          "aspect": b.get("aspect") or "16:9", "length": b.get("length") or 90},
                "characters": chars, "locations": locs,
                "episodes": [{"id": eid, "title": ep.get("title") or b.get("title"), "lesson": b.get("lesson") or "",
                              "idea": (ep.get("idea") or b.get("premise") or p["prompt"]),
                              "cast": [c["id"] for c in chars], "location": locs[0]["id"]}]}
        d = series.save(uid, series.merge(None, body))
        series.log_event(uid, d["id"], "created", name=d.get("name"), by="MirAI producer")
        p.update(sid=d["id"], eid=eid, stage="pictures")
        _log(p, "Project set up. Drawing the cast and their world now.")
        save(uid, p)
    elif st == "pictures":
        if not p.get("qids"):
            d = series.load(uid, p["sid"])
            steps_ = []
            for c in d.get("characters") or []:
                steps_ += [{"kind": "hero", "target": c["id"], "label": c["name"] + " · design"},
                           {"kind": "sheet", "target": c["id"], "label": c["name"] + " · turnaround"}]
            for l in d.get("locations") or []:
                steps_ += [{"kind": "location", "target": l["id"], "label": l["name"]},
                           {"kind": "locsheet", "target": l["id"], "label": l["name"] + " · sheet"}]
            if len(d.get("characters") or []) >= 2:
                steps_.append({"kind": "lineup", "label": "cast lineup"})
            before = {x["id"] for x in runner.queue_status(uid, p["sid"])["items"]}
            for k in range(0, len(steps_), 6):                  # the queue takes up to 6 per call
                runner.enqueue(uid, p["sid"], steps_[k:k + 6])
            p["qids"] = [x["id"] for x in runner.queue_status(uid, p["sid"])["items"] if x["id"] not in before]
            save(uid, p)
            return
        items = [x for x in runner.queue_status(uid, p["sid"])["items"] if x["id"] in p["qids"]]
        done_n = sum(x["state"] == "done" for x in items)
        if done_n != p.get("pics_said", 0):
            for x in items:
                if x["state"] == "done" and x["id"] not in (p.get("pics_named") or []):
                    p.setdefault("pics_named", []).append(x["id"])
                    _log(p, "Drew %s (%d of %d)." % (x["label"], done_n, len(items)))
            p["pics_said"] = done_n
            save(uid, p)
        if any(x["state"] in ("queued", "running") for x in items):
            return
        bad = [x for x in items if x["state"] != "done"]
        retried = set(p.get("pic_retried") or [])
        again = [x for x in bad if x["label"] not in retried]
        if again:                                              # one automatic redraw per failed picture
            _log(p, "%d picture%s failed (%s) — drawing %s again." % (
                len(again), "s" if len(again) > 1 else "", ", ".join(x["label"] for x in again[:4]),
                "them" if len(again) > 1 else "it"), "warn")
            if any(re.search(r"memory|cuda", str(x.get("error") or ""), re.I) for x in again):
                _free_gpu()
            runner.enqueue(uid, p["sid"], [{"kind": x["kind"], "target": x["target"], "label": x["label"]} for x in again][:6])
            p["pic_retried"] = list(retried | {x["label"] for x in again})
            p["qids"] = [i for i in p["qids"] if i not in {x["id"] for x in again}] + \
                [x["id"] for x in runner.queue_status(uid, p["sid"])["items"] if x["state"] == "queued" and x["id"] not in p["qids"]]
            save(uid, p)
            return
        must = [x["label"] for x in bad if x["kind"] in ("hero", "location")]
        if must:
            raise RuntimeError("couldn't draw: " + ", ".join(must[:5]))
        if p.get("checkpoints"):
            p.update(stage="approve_look", state="waiting")
            _log(p, "The cast and the world are ready. Have a look in the Production tab and approve them — "
                    "then I record the song and render the episode.", "need")
        else:
            p["stage"] = "episode"
        p["heals"] = {}
        save(uid, p)
    elif st == "episode":
        run = runner.load_run(uid, p["sid"])
        if not run or run.get("ep") != p["eid"] or run.get("state") == "stopped":
            runner.control(uid, p["sid"], "start", p["eid"])
            p["seen_done"] = len((runner.load_run(uid, p["sid"]) or {}).get("done") or [])   # don't re-announce old steps
            _log(p, "Episode render started — song first, then each shot (chained frame to frame), then the final edit.")
            save(uid, p)
            return
        ep = series._find(series.load(uid, p["sid"]), "episodes", p["eid"]) or {}
        if ep.get("final"):
            p.update(final=ep["final"], stage="publish", heals={})
            _log(p, "The episode is assembled. Writing the YouTube title, description and tags now.", "done")
            save(uid, p)
            return
        _watch_episode(p, run, ep)
        save(uid, p)
    elif st == "publish":
        b = p["brief"]
        brief = ("Children's musical episode (made for kids). Show: %s. Episode: %s. Premise: %s. Lesson: %s. "
                 "Keywords: %s. Write a long-form YouTube title (not a Short), a warm parent-friendly description "
                 "with the lesson and a sing-along invitation, and kid-safe tags."
                 % (b.get("title"), (b.get("episode") or {}).get("title"), b.get("premise"), b.get("lesson"),
                    ", ".join(b.get("youtube_keywords") or [])))
        if b.get("post_note"):
            brief += " Owner direction: " + b["post_note"]
        post = HK["social_draft"](p["final"], p["platforms"], brief, uid,
                                  "keep" if (b.get("aspect") or "16:9") != "9:16" else "crop", True)
        p.update(post=post.get("id"), stage="done", state="done")
        _log(p, "All done! The episode is finished and the post is waiting for your Approve in Social.", "need")
        save(uid, p)


# ── Flask wiring ───────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, can_produce()->error|None, push(user, type, title, body, **kw), job(jid)->dict|None, cancel(jid),
    social_draft(lib_name, platforms, brief, owner, fit, kids)->post, static(fn)."""
    from flask import request, jsonify
    setup(hk)

    def U():
        return hk["uid"]()

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    @app.route("/production")
    def pr_page():
        return hk["static"]("production.html")

    @app.route("/api/produce")
    def pr_list():
        return jsonify({"productions": listing(U())})

    @app.route("/api/produce/feed")
    def pr_feed():
        try:
            since = int(request.args.get("since") or 0)
        except ValueError:
            since = 0
        return jsonify({"events": feed(U(), since), "now": int(time.time() * 1000)})

    @app.route("/api/produce", methods=["POST"])
    def pr_start():
        err = hk["can_produce"]()
        if err:
            return oops(err, 403)
        b = request.get_json(silent=True) or {}
        try:
            return jsonify(start(U(), b.get("prompt"), b.get("cast_max") or MAX_CAST, b.get("checkpoints", True),
                                 b.get("platforms") or ("youtube",)))
        except Exception as e:
            return oops(e)

    @app.route("/api/produce/<pid>")
    def pr_get(pid):
        p = load(U(), pid)
        return jsonify(public(p)) if p else oops("no such production", 404)

    @app.route("/api/produce/<pid>/project")
    def pr_project(pid):
        p = load(U(), pid)
        return jsonify(project(p)) if p else oops("no such production", 404)

    @app.route("/api/produce/<pid>/<action>", methods=["POST"])
    def pr_control(pid, action):
        try:
            return jsonify(control(U(), pid, action, request.get_json(silent=True) or {}))
        except Exception as e:
            return oops(e)
