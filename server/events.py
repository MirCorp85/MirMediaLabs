"""Notification feed for the phone / TV apps — self-hosted push, no Firebase or third-party service.

Each event goes to one person (their user id) or to everyone ("*"). Apps hold a long-poll on
GET /api/events?since=<id>&wait=<s>: the request returns the moment an event arrives, otherwise
after `wait` seconds with nothing. Ids are millisecond timestamps (monotonic), so a phone that
was offline across a server restart still resumes from where it was. The last 300 events are
kept in data/events.json so nothing is lost while a phone is asleep.
"""
import os
import threading
import time

import core

FILE = os.path.join(core.DATA, "events.json")
KEEP = 300
_EV = []
_COND = threading.Condition()
_last = [0]


def load():
    global _EV
    _EV = [e for e in core.load_json(FILE, []) if isinstance(e, dict) and "id" in e][-KEEP:]
    _last[0] = max([e["id"] for e in _EV] + [int(time.time() * 1000)])


def push(user, etype, title, body="", **extra):
    """Queue an event for `user` ("*" = everyone) and wake every waiting phone."""
    with _COND:
        _last[0] = max(_last[0] + 1, int(time.time() * 1000))
        ev = {"id": _last[0], "user": user, "type": etype, "title": str(title)[:120], "body": str(body)[:400],
              "t": time.time(), **extra}
        _EV.append(ev)
        del _EV[:-KEEP]
        snapshot = list(_EV)
        _COND.notify_all()
    try:
        core.save_json(FILE, snapshot)
    except Exception:
        pass
    return ev


def _for(uid, since):
    return [{k: v for k, v in e.items() if k != "user"} for e in _EV if e["id"] > since and e["user"] in (uid, "*")]


def wait(uid, since, timeout):
    """Events for `uid` newer than `since`; blocks up to `timeout` s while there are none.
    since <= 0 means a new device: no backlog, just the current cursor."""
    deadline = time.time() + max(0.0, min(float(timeout), 55.0))
    with _COND:
        while True:
            if since <= 0:
                return [], _last[0]
            out = _for(uid, since)
            left = deadline - time.time()
            if out or left <= 0:
                return out, _last[0]
            _COND.wait(left)


# ── job → notification text (role words, never engine names: the front-end stays engine-agnostic) ──
_WHAT = {"video": "video", "image": "image", "audio": "track"}


def job_event(job):
    who = job.get("user") or "owner"
    st = job.get("status")
    files = list(job.get("files") or [])
    kinds = [core.kind_of(f) for f in files]
    what = next((_WHAT[k] for k in ("video", "image", "audio") if k in kinds), None)
    if job.get("model") == "llama":
        what = "reply"
    prompt = (job.get("input") or job.get("prompt") or "").strip().replace("\n", " ")
    snippet = prompt[:140] + ("…" if len(prompt) > 140 else "")
    if st == "done":
        title = "MirAI replied" if what == "reply" else "Your %s is ready" % (what or "result")
        body = (job.get("output") or "")[:300] if what == "reply" else snippet
    elif st == "error":
        title, body = "Request failed", (job.get("error") or "")[:300]
    elif st == "cancelled" and (job.get("error") or "") != "cancelled":
        title, body = "Request stopped", job.get("error") or ""
    else:
        return None
    return push(who, "job", title, body, status=st, job=job.get("id"), model=job.get("model"),
                files=files[:4], kind=next((k for k in ("video", "image", "audio") if k in kinds), ""))
