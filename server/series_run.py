"""SERIES runner — a whole episode rendered in the background, step by step, surviving crashes.

The next step is always worked out from what is already SAVED in the series (song made? shots written? which shots
have a picture?), so nothing is ever rendered twice and a crash costs at most the step that was running:
  write song → record song (or: uploaded song → recognise its words) → write shots → for every shot: first frame
  (cut shots) + the shot itself → assemble.
The run's own state (running / paused / done, the step in flight + its job, attempts, history) is one small file per
series: data/series/<user>/<id>.run.json, written after every change. When the lab starts again it reads those files
and carries on (auto-resume): a step that was interrupted is simply submitted again; a step that FAILS is retried once
and then the run pauses with the reason. Every event also goes to the series' event log (series.log_event).

GPU steps go through the lab's own /api/generate (hk["submit"] — same queue, rights and one-at-a-time rule as the
page), so a person working in the lab at the same time is never pushed aside: the runner simply waits its turn.
Identical in the MirOS copy (miros_mlab) — copy, never import across.
"""
import json
import os
import re
import threading
import time
import traceback

try:
    from . import core, series
except ImportError:
    import core
    import series

HK = {}
TICK = 3.0
MAX_ATTEMPTS = 2                                       # first failure → retry once; second → pause and say why
MAX_TRANSIENT = 4                                      # GPU out of memory / ComfyUI busy or restarting: more patience
COOL_DOWN = 60                                         # seconds before retrying a transient failure
TRANSIENT = re.compile(r"memory|out of memory|oom|timed out|timeout|connection|refused|restart|engine|aborted|"
                       r"lost|unreachable|cuda", re.I)
GPU_KINDS = ("song", "keyframe", "chunk")
CPU_KINDS = ("write", "transcribe", "shots", "assemble")
LABEL = {"write": "write the song", "song": "record the song", "transcribe": "recognise the lyrics",
         "shots": "write the shots", "keyframe": "first frame", "chunk": "shot", "assemble": "assemble the episode"}

_ACTIVE = set()                                        # (uid, sid) with a run worth ticking
_GUARD = threading.Lock()
_CPU = {}                                              # (uid, sid) → {"thread", "result": None | (ok, msg)}
_RECOG = {}                                            # (uid, sid, eid) → {"state", "msg", "error"} (manual "recognise")
_STARTED = False


def setup(hk):
    global _STARTED
    HK.update(hk)
    if not _STARTED:
        _STARTED = True
        threading.Thread(target=_loop, daemon=True, name="series-runner").start()


# ── the run file ──────────────────────────────────────────────────────────────────────────────────────────────────
def _rpath(uid, sid):
    return os.path.join(series._dir(uid), sid + ".run.json")


def load_run(uid, sid):
    p = _rpath(uid, sid)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_run(uid, sid, r):
    r["updated"] = time.time()
    r["done"] = (r.get("done") or [])[-500:]
    p = _rpath(uid, sid)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(r, f)
    os.replace(p + ".tmp", p)
    return r


def _store(uid):
    return lambda stem, ext: HK["store_ref"](stem, ext, uid)


def _say(uid, sid, ev, **kw):
    return series.log_event(uid, sid, ev, **kw)


# ── what's next (derived from the saved series, so a crash never loses or repeats finished work) ──────────────────
def next_step(d, ep, run):
    skipped = set(run.get("skipped") or [])
    chunks = ep.get("chunks") or []
    if not ep.get("song"):
        if ep.get("song_source") == "upload":
            return "blocked", "the uploaded song file is missing"
        if not ((ep.get("song_text") or {}).get("lyrics")):
            return ("write", None) if (ep.get("idea") or ep.get("title")) else ("blocked", "give the episode an idea first")
        return "song", None
    if ep.get("song_source") == "upload" and not ep.get("words") and "transcribe:None" not in skipped:
        return "transcribe", None
    if not chunks:
        return "blocked", "the song has no shots — re-cut the song into shots"
    if any(not (c.get("shot") or "").strip() for c in chunks) and "shots:None" not in skipped:
        return "shots", None
    for c in chunks:
        if "chunk:%d" % c["i"] in skipped or (c.get("clip") and not c.get("stale")):
            continue
        prev = chunks[c["i"] - 1] if c["i"] else None
        needs_key = c.get("link") == "cut" or c["i"] == 0 or not (prev and prev.get("clipref"))
        if needs_key and not c.get("key"):
            return "keyframe", c["i"]
        return "chunk", c["i"]
    if not ep.get("final"):
        return "assemble", None
    return "done", None


def _remaining(ep):
    """Steps still to go (for the progress bar / ETA)."""
    n = 0
    chunks = ep.get("chunks") or []
    for c in chunks:
        if c.get("clip") and not c.get("stale"):
            continue
        n += 1
        if (c.get("link") == "cut" or c["i"] == 0) and not c.get("key"):
            n += 1
    if not ep.get("song"):
        n += 2
    if any(not (c.get("shot") or "").strip() for c in chunks):
        n += 1
    return n + (0 if ep.get("final") else 1)


# ── control (the page's buttons) ──────────────────────────────────────────────────────────────────────────────────
def control(uid, sid, action, eid=None):
    with series.locked(uid, sid):
        run = load_run(uid, sid)
        if action == "start":
            d = series.load(uid, sid)
            if not series._find(d, "episodes", eid):
                raise ValueError("pick an episode")
            if run and run.get("state") == "running" and run.get("ep") != eid:
                raise ValueError("another episode of this series is rendering — pause it first")
            keep = run if (run and run.get("ep") == eid) else {}
            run = {"sid": sid, "uid": uid, "ep": eid, "state": "running", "step": keep.get("step"), "attempts": {},
                   "skipped": [], "done": keep.get("done") or [], "error": None,
                   "started": keep.get("started") or time.time()}
            _say(uid, sid, "run-start", ep=eid)
        elif not run:
            raise ValueError("nothing is running")
        elif action == "pause":
            run["state"] = "paused"
            _say(uid, sid, "run-pause", why="you paused it")
        elif action in ("resume", "retry"):
            run.update(state="running", error=None)
            if action == "retry":
                run["attempts"] = {}
            _say(uid, sid, "run-" + action)
        elif action == "skip":
            d = series.load(uid, sid)
            kind, i = next_step(d, series._find(d, "episodes", run["ep"]) or {}, run)
            if kind in ("done", "blocked"):
                raise ValueError("nothing to skip")
            run.setdefault("skipped", []).append("%s:%s" % (kind, i))
            run.update(state="running", error=None)
            _say(uid, sid, "run-skip", step=kind, i=i)
        elif action in ("cancel", "stop"):
            st = run.get("step") or {}
            if st.get("job") and HK.get("cancel"):
                HK["cancel"](st["job"])                # stop the GPU render itself, not just the bookkeeping
            run["step"] = None
            if action == "cancel":                     # this step only: the run waits (Resume redoes it, Skip moves on)
                run.update(state="paused", error=None)
                _say(uid, sid, "step-cancelled", step=st.get("kind"), i=st.get("i"))
            else:
                run["state"] = "stopped"
                _say(uid, sid, "run-stop")
        else:
            raise ValueError("unknown action")
        save_run(uid, sid, run)
    with _GUARD:
        _ACTIVE.add((uid, sid))
    return status(uid, sid)


def pause(uid, sid, why):
    with series.locked(uid, sid):
        run = load_run(uid, sid)
        if run and run.get("state") == "running":
            run["state"] = "paused"
            save_run(uid, sid, run)
            _say(uid, sid, "run-pause", why=why)


def stop(uid, sid):
    run = load_run(uid, sid)
    if run:
        run["state"] = "stopped"
        save_run(uid, sid, run)


def status(uid, sid):
    run = load_run(uid, sid) or {}
    d = series.load(uid, sid) or {}
    ep = series._find(d, "episodes", run.get("ep")) if run else None
    out = {"run": run or None, "recognising": {k[2]: v for k, v in _RECOG.items() if k[:2] == (uid, sid)}}
    if run and ep:
        took = {}
        for x in run.get("done") or []:
            took.setdefault(x["kind"], []).append(x.get("secs") or 0)
        avg = {k: sum(v) / len(v) for k, v in took.items() if v}
        per = avg.get("chunk", 240) + avg.get("keyframe", 50) * 0.4
        left = _remaining(ep)
        out["progress"] = {"done": len(run.get("done") or []), "left": left, "eta": round(left * per),
                           "elapsed": round(time.time() - (run.get("started") or time.time()))}
        if run.get("state") == "running" and not run.get("step"):
            k, i = next_step(d, ep, run)
            out["next"] = {"kind": k, "i": i, "label": LABEL.get(k, k)}
    return out


# ── manual "recognise the lyrics" (outside a run) ─────────────────────────────────────────────────────────────────
def recognise_async(uid, sid, eid):
    key = (uid, sid, eid)
    if (_RECOG.get(key) or {}).get("state") == "running":
        raise ValueError("already listening to this song")
    _RECOG[key] = {"state": "running", "msg": "starting …", "error": None}

    def go():
        try:
            series.transcribe(uid, sid, eid, _store(uid), lambda m: _RECOG[key].update(msg=m))
            _RECOG[key].update(state="done", msg="lyrics recognised")
        except Exception as e:
            _RECOG[key].update(state="error", error=str(e)[:300], msg="")
            _say(uid, sid, "transcribe-failed", ep=eid, error=str(e)[:300])
    threading.Thread(target=go, daemon=True, name="series-recognise").start()


# ── the picture queue: one-off cast / world pictures, attached by the SERVER ─────────────────────────────────────
# The page used to file a finished picture back itself, so closing the tab (or the phone app going to sleep) during a
# 1–3 min render lost it, and "build the character" was three separate taps. Now every one-off step is queued here:
# planned when it STARTS (so a turnaround is drawn from the hero that was just made), submitted through /api/generate,
# and attached on completion whether or not anybody is watching. One file per series: <sid>.queue.json.
Q_KINDS = ("hero", "character", "sheet", "expr", "lineup", "location", "locsheet", "locview", "scene", "song",
           "keyframe", "chunk", "object", "objsheet", "objdetail")
_QACTIVE = set()


def _qpath(uid, sid):
    return os.path.join(series._dir(uid), sid + ".queue.json")


def load_queue(uid, sid):
    try:
        with open(_qpath(uid, sid), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": []}


def _save_queue(uid, sid, q):
    live = [x for x in q["items"] if x["state"] in ("queued", "running")]
    old = [x for x in q["items"] if x["state"] not in ("queued", "running")][-20:]
    q["items"] = sorted(old + live, key=lambda x: x["t"])
    p = _qpath(uid, sid)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(q, f)
    os.replace(p + ".tmp", p)
    return q


def enqueue(uid, sid, steps):
    """steps: [{kind, target, extra, label}] — run in order; a step whose plan fails (e.g. no hero yet) errors alone."""
    with series.locked(uid, sid):
        q = load_queue(uid, sid)
        now = time.time()
        for n, s in enumerate(steps):
            if s.get("kind") not in Q_KINDS:
                raise ValueError("unknown step")
            q["items"].append({"id": "q%d%02d" % (int(now * 1000), n), "kind": s["kind"], "target": s.get("target"),
                               "extra": s.get("extra") or {}, "label": str(s.get("label") or s["kind"])[:80],
                               "state": "queued", "t": now + n * 0.001})
        _save_queue(uid, sid, q)
    with _GUARD:
        _QACTIVE.add((uid, sid))
    return queue_status(uid, sid)


def queue_status(uid, sid):
    q = load_queue(uid, sid)
    items = []
    for x in q["items"]:
        y = {k: x.get(k) for k in ("id", "kind", "target", "label", "state", "job", "stage", "pct", "error", "t", "done_t")}
        y["i"] = (x.get("extra") or {}).get("i")
        if x["state"] == "running" and x.get("job"):
            j = HK["job"](x["job"]) if HK.get("job") else None
            if j:
                y["stage"], y["pct"] = j.get("stage"), (j.get("progress") or {}).get("pct")
                y["pv"] = (j.get("progress") or {}).get("pv")
        items.append(y)
    return {"items": items}


def queue_cancel(uid, sid, qid):
    with series.locked(uid, sid):
        q = load_queue(uid, sid)
        for x in q["items"]:
            if (x["id"] == qid or qid == "all") and x["state"] in ("queued", "running"):
                if x["state"] == "running" and x.get("job") and HK.get("cancel"):
                    HK["cancel"](x["job"])             # the picture rendering right now stops too
                x.update(state="cancelled", done_t=time.time())
        _save_queue(uid, sid, q)
    return queue_status(uid, sid)


def _qput(uid, sid, item):
    with series.locked(uid, sid):
        fresh = load_queue(uid, sid)                   # keep anything enqueued meanwhile
        fresh["items"] = [x if (x["id"] == item["id"] and x["state"] == "cancelled") else item if x["id"] == item["id"] else x
                          for x in fresh["items"]]     # a cancel that landed meanwhile wins
        _save_queue(uid, sid, fresh)


def _qtick(uid, sid):
    with series.locked(uid, sid):
        q = load_queue(uid, sid)
    cur = next((x for x in q["items"] if x["state"] == "running"), None)
    if cur:
        j = HK["job"](cur.get("job")) if cur.get("job") else None
        if not j or (j.get("status") == "error" and "restarted" in str(j.get("error") or "")):
            cur.update(state="queued", job=None)       # lab restarted under it: submit again
        elif j.get("status") in ("queued", "running"):
            return
        elif j.get("status") == "done":
            f = _media(j.get("files"))
            try:
                if not f:
                    raise ValueError("finished without a media file")
                a = cur.get("attach") or {}
                with series.locked(uid, sid):
                    series.attach_file(uid, series.load(uid, sid), f, a.get("kind") or cur["kind"],
                                       a.get("target") if "target" in a else cur.get("target"), a.get("i"),
                                       _store(uid), HK.get("seconds_of"))
                cur.update(state="done", out=f, done_t=time.time())
                _say(uid, sid, "attached", kind=a.get("kind") or cur["kind"], file=f)
            except Exception as e:
                cur.update(state="error", error=str(e)[:300], done_t=time.time())
        elif j.get("status") == "cancelled":
            cur.update(state="cancelled", done_t=time.time())
        else:
            cur.update(state="error", error=str(j.get("error") or j.get("status"))[:300], done_t=time.time())
        return _qput(uid, sid, cur)
    nxt = next((x for x in q["items"] if x["state"] == "queued"), None)
    if not nxt:
        with _GUARD:
            _QACTIVE.discard((uid, sid))
        return
    with series.locked(uid, sid):
        d = series.load(uid, sid)
        try:
            req = series.prepare(uid, d, nxt["kind"], nxt.get("target"), nxt.get("extra"), _store(uid)) if d \
                else {"error": "the series is gone"}
        except Exception as e:
            req = {"error": str(e)}
    if req.get("error"):
        nxt.update(state="error", error=str(req["error"])[:300], done_t=time.time())
    else:
        job, err, busy = HK["submit"](uid, req)
        if busy:
            return                                     # the person (or the episode runner) has the lab — wait our turn
        if err:
            nxt.update(state="error", error=str(err)[:300], done_t=time.time())
        else:
            nxt.update(state="running", job=job["id"], attach=req.get("attach"), started=time.time())
    _qput(uid, sid, nxt)


# ── the loop ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _loop():
    time.sleep(5)                                      # let the lab load its job list first
    _resume_all()
    while True:
        with _GUARD:
            qtodo = list(_QACTIVE)
        for uid, sid in qtodo:
            try:
                _qtick(uid, sid)
            except Exception:
                traceback.print_exc()
        with _GUARD:
            todo = list(_ACTIVE)
        for uid, sid in todo:
            try:
                _tick(uid, sid)
            except Exception as e:
                traceback.print_exc()
                try:
                    _say(uid, sid, "runner-error", error=str(e)[:300])
                except Exception:
                    pass
        time.sleep(TICK)


def _resume_all():
    """Lab (re)started: every run that was going carries on from where its files say it was."""
    if not os.path.isdir(series.SER):
        return
    for u in os.listdir(series.SER):
        udir = os.path.join(series.SER, u)
        if not os.path.isdir(udir):
            continue
        for f in os.listdir(udir):
            if f.endswith(".queue.json"):
                qsid = f[:-11]
                if any(x.get("state") in ("queued", "running") for x in load_queue(u, qsid)["items"]):
                    with _GUARD:
                        _QACTIVE.add((u, qsid))
                continue
            if not f.endswith(".run.json"):
                continue
            sid = f[:-9]
            run = load_run(u, sid)
            if run and (run.get("state") == "running" or run.get("step")):
                uid = run.get("uid") or u
                with _GUARD:
                    _ACTIVE.add((uid, sid))
                _say(uid, sid, "lab-restarted", state=run.get("state"),
                     step=(run.get("step") or {}).get("kind"), i=(run.get("step") or {}).get("i"))


def _media(files):
    return next((str(f).split("/")[-1] for f in files or []
                 if str(f).lower().endswith((".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".flac"))), None)


def _finish_step(uid, sid, run, st, ok, msg=None, out=None):
    if ok:
        run.setdefault("done", []).append({"key": st["key"], "kind": st["kind"], "i": st.get("i"), "out": out,
                                           "secs": round(time.time() - st.get("t0", time.time())), "t": round(time.time())})
        run["attempts"].pop(st["key"], None)
        _say(uid, sid, "step-done", step=st["kind"], i=st.get("i"), out=out, secs=round(time.time() - st.get("t0", time.time())))
    else:
        n = run.setdefault("attempts", {}).get(st["key"], 0) + 1
        run["attempts"][st["key"]] = n
        transient = bool(TRANSIENT.search(msg or ""))
        if transient and n < MAX_TRANSIENT:
            run["retry_at"] = time.time() + COOL_DOWN * n   # let the GPU / ComfyUI settle before trying again
            _say(uid, sid, "step-failed", step=st["kind"], i=st.get("i"), error=(msg or "")[:300], attempt=n, retry=True,
                 cooldown=COOL_DOWN * n)
        elif n >= (MAX_TRANSIENT if transient else MAX_ATTEMPTS):
            run["state"], run["error"] = "paused", "%s%s failed %d times: %s" % (
                LABEL.get(st["kind"], st["kind"]), "" if st.get("i") is None else " %d" % (st["i"] + 1), n, (msg or "")[:300])
            _say(uid, sid, "step-failed", step=st["kind"], i=st.get("i"), error=(msg or "")[:300], attempt=n, paused=True)
        else:
            _say(uid, sid, "step-failed", step=st["kind"], i=st.get("i"), error=(msg or "")[:300], attempt=n, retry=True)
    run["step"] = None


def _tick(uid, sid):
    with series.locked(uid, sid):
        run = load_run(uid, sid)
    if not run or run.get("state") not in ("running", "paused") or (run.get("state") == "paused" and not run.get("step")):
        with _GUARD:
            _ACTIVE.discard((uid, sid))
        return
    st = run.get("step")
    if st:
        return _watch(uid, sid, run, st)
    if run["state"] != "running" or time.time() < (run.get("retry_at") or 0):
        return
    with series.locked(uid, sid):
        d = series.load(uid, sid)
        ep = series._find(d, "episodes", run["ep"]) if d else None
        if not ep:
            run.update(state="stopped", error="the episode is gone")
            save_run(uid, sid, run)
            return
        kind, i = next_step(d, ep, run)
        if kind == "done":
            run.update(state="done", error=None)
            save_run(uid, sid, run)
            _say(uid, sid, "run-done", ep=run["ep"], final=ep.get("final"))
            return
        if kind == "blocked":
            run.update(state="paused", error=i)
            save_run(uid, sid, run)
            _say(uid, sid, "run-pause", why=i)
            return
        st = {"key": "%s:%s" % (kind, i), "kind": kind, "i": i, "t0": time.time()}
        if kind in CPU_KINDS:
            st["cpu"] = True
            run["step"] = st
            save_run(uid, sid, run)
            _start_cpu(uid, sid, run["ep"], kind)
            _say(uid, sid, "step-start", step=kind, i=i)
            return
        try:
            req = series.prepare(uid, d, kind, ep["id"], {"i": i} if i is not None else {}, _store(uid))
        except Exception as e:
            req = {"error": str(e)}
    if req.get("error"):
        _finish_step(uid, sid, run, st, False, req["error"])
        with series.locked(uid, sid):
            save_run(uid, sid, run)
        return
    job, err, busy = HK["submit"](uid, req)
    if busy:
        return                                         # the person (or another run) has the lab right now — wait
    if err:
        _finish_step(uid, sid, run, st, False, err)
    else:
        st.update(job=job["id"], attach=req.get("attach"))
        run["step"] = st
        _say(uid, sid, "step-queued", step=kind, i=i, job=job["id"])
    with series.locked(uid, sid):
        save_run(uid, sid, run)


def _watch(uid, sid, run, st):
    if st.get("cpu"):
        c = _CPU.get((uid, sid))
        if c and c["thread"].is_alive():
            return
        res = c and c.get("result")
        _CPU.pop((uid, sid), None)
        if not res:                                    # the lab restarted while it ran: just do it again
            _say(uid, sid, "step-interrupted", step=st["kind"], i=st.get("i"))
            run["step"] = None
        else:
            _finish_step(uid, sid, run, st, res[0], res[1])
        with series.locked(uid, sid):
            save_run(uid, sid, run)
        return
    j = HK["job"](st.get("job")) if st.get("job") else None
    if not j or (j.get("status") == "error" and "restarted" in str(j.get("error") or "")):
        _say(uid, sid, "step-interrupted", step=st["kind"], i=st.get("i"), job=st.get("job"))
        run["step"] = None                             # submitted again on the next tick (attempts not counted)
        with series.locked(uid, sid):
            save_run(uid, sid, run)
        return
    if j.get("status") in ("queued", "running"):
        pct = (j.get("progress") or {}).get("pct")
        if st.get("stage") != j.get("stage") or st.get("pct") != pct:
            st.update(stage=j.get("stage"), pct=pct)
            with series.locked(uid, sid):
                save_run(uid, sid, run)
        return
    if j.get("status") == "done":
        f = _media(j.get("files"))
        try:
            if not f:
                raise ValueError("finished without a media file")
            a = st.get("attach") or {}
            with series.locked(uid, sid):
                series.attach_file(uid, series.load(uid, sid), f, a.get("kind") or st["kind"], a.get("target") or run["ep"],
                                   st.get("i"), _store(uid), HK.get("seconds_of"))
            _finish_step(uid, sid, run, st, True, out=f)
        except Exception as e:
            _finish_step(uid, sid, run, st, False, str(e))
    elif j.get("status") == "cancelled":                # cancelled by hand (here or in the lab): not a failure
        with series.locked(uid, sid):
            run = load_run(uid, sid) or run            # the cancel itself may already have saved the run
            if run.get("step") and run["step"].get("job") == st.get("job"):
                run["step"] = None
                run.update(state="paused", error=None)
                _say(uid, sid, "step-cancelled", step=st["kind"], i=st.get("i"))
            save_run(uid, sid, run)
        return
    else:
        _finish_step(uid, sid, run, st, False, j.get("error") or j.get("status"))
    with series.locked(uid, sid):
        save_run(uid, sid, run)


def _start_cpu(uid, sid, eid, kind):
    box = {"result": None}

    def go():
        try:
            if kind == "transcribe":
                series.transcribe(uid, sid, eid, _store(uid))
            else:
                with series.locked(uid, sid):
                    d = series.load(uid, sid)
                    ep = series._find(d, "episodes", eid)
                if kind == "assemble":
                    with series.locked(uid, sid):
                        d = series.load(uid, sid)
                        series.finish(uid, d, series._find(d, "episodes", eid), HK["editor_dir"](uid))
                else:                                  # the writers take minutes: work on a copy, merge at the end
                    if kind == "write":
                        series.write_musical(d, ep)
                    else:
                        series.write_chunks(d, ep)
                    with series.locked(uid, sid):
                        cur = series.load(uid, sid)
                        cep = series._find(cur, "episodes", eid)
                        for k in ("song_text", "sections", "chunks"):
                            if k in ep:
                                cep[k] = ep[k]
                            elif k == "chunks":
                                cep.pop("chunks", None)
                        series.save(uid, cur)
                        series.checkpoint(uid, cur, "song written" if kind == "write" else "shots written")
            box["result"] = (True, None)
        except Exception as e:
            box["result"] = (False, str(e)[:400])
    th = threading.Thread(target=go, daemon=True, name="series-" + kind)
    box["thread"] = th
    _CPU[(uid, sid)] = box
    th.start()
