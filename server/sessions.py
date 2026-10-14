"""
sessions.py — chat sessions (projects) for MIR MEDIA LABS: every chat request and every file it makes belongs to one,
so the chat and the library can be split by project.
═══════════════════════════════════════════════════════════════════════════════
IDENTICAL in both copies (standalone server/sessions.py and the other copy's sessions.py) — copy, never
import across. Each copy wires it in with
    sessions.register(app, hooks)
where hooks = {"uid": uid(), "move": move(uid, from_sid, to_sid) → re-files that session's chats + media}.

"General" is the built-in session (id ""): everything made before sessions existed, and anything sent without one.
Old apps send no session and keep seeing everything, so nothing breaks for them.

  • GET  /api/sessions                 {sessions: [{id, name, created}], last}
  • POST /api/sessions                 {name}            → new session (also becomes "last")
  • POST /api/sessions/<id>            {name} rename · {last: true} remember it as the open one
  • POST /api/sessions/<id>/delete     the session goes; its chats + media move to General (nothing is deleted)
"""
import os
import re
import threading
import time
import uuid

try:                      # package copy lives in the package copy
    from . import core
except ImportError:       # standalone server runs its modules flat
    import core

SD = os.path.join(core.DATA, "sessions")
MAX = 200
_LOCK = threading.Lock()
_ID = re.compile(r"^[a-z0-9]{8,16}$")


def _path(uid):
    return os.path.join(SD, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "owner")) + ".json")


def load(uid):
    d = core.load_json(_path(uid), {})
    return {"sessions": [s for s in d.get("sessions") or [] if isinstance(s, dict) and _ID.match(str(s.get("id") or ""))],
            "last": d.get("last") or ""}


def _save(uid, d):
    os.makedirs(SD, exist_ok=True)
    core.save_json(_path(uid), d)


def valid(uid, sid):
    """sid when it is one of this person's sessions, else "" (General)."""
    sid = str(sid or "")
    return sid if sid and any(s["id"] == sid for s in load(uid)["sessions"]) else ""


def name_of(uid, sid):
    return next((s["name"] for s in load(uid)["sessions"] if s["id"] == sid), "General")


def _clean_name(n):
    return re.sub(r"\s+", " ", str(n or "")).strip()[:60]


def create(uid, name):
    """A new session that also becomes the open one ("last") — a new project starts its own chat + media shelf."""
    with _LOCK:
        d = load(uid)
        if len(d["sessions"]) >= MAX:
            d["sessions"] = d["sessions"][-(MAX - 1):]
        s = {"id": uuid.uuid4().hex[:12], "name": _clean_name(name) or time.strftime("Project %b %d"), "created": time.time()}
        d["sessions"].append(s)
        d["last"] = s["id"]
        _save(uid, d)
    return s


def register(app, hk):
    from flask import request, jsonify

    def U():
        return str(hk["uid"]())

    def body():
        return request.get_json(silent=True) or {}

    @app.route("/api/sessions", methods=["GET", "POST"])
    def sessions_list():
        uid = U()
        if request.method == "GET":
            return jsonify(load(uid))
        name = _clean_name(body().get("name")) or time.strftime("Session %b %d")
        with _LOCK:
            d = load(uid)
            if len(d["sessions"]) >= MAX:
                return jsonify({"error": "that's %d sessions — delete an old one first" % MAX}), 400
            s = {"id": uuid.uuid4().hex[:12], "name": name, "created": time.time()}
            d["sessions"].append(s)
            d["last"] = s["id"]
            _save(uid, d)
        return jsonify(dict(d, session=s))

    @app.route("/api/sessions/<sid>", methods=["POST"])
    def sessions_edit(sid):
        uid, b = U(), body()
        sid = "" if sid == "_" else sid               # "_" = General (it has no id)
        with _LOCK:
            d = load(uid)
            s = next((x for x in d["sessions"] if x["id"] == sid), None)
            if sid and not s:
                return jsonify({"error": "no such session"}), 404
            if s and _clean_name(b.get("name")):
                s["name"] = _clean_name(b["name"])
            if b.get("last"):
                d["last"] = sid
            _save(uid, d)
        return jsonify(d)

    @app.route("/api/sessions/<sid>/delete", methods=["POST"])
    def sessions_delete(sid):
        uid = U()
        with _LOCK:
            d = load(uid)
            if not any(x["id"] == sid for x in d["sessions"]):
                return jsonify({"error": "no such session"}), 404
            d["sessions"] = [x for x in d["sessions"] if x["id"] != sid]
            if d["last"] == sid:
                d["last"] = ""
            _save(uid, d)
        moved = hk["move"](uid, sid, "")              # its chats + media go to General — nothing is deleted
        return jsonify(dict(d, moved=moved))


# ── library folders: data/library/Sessions/<session name>/ ───────────────────────────────────────────────
# Every library item also appears inside a folder named after its session (hardlinks: same file, no extra disk,
# nothing in the app changes — it still reads the flat library). Kept in step every 30 s: new items, moves
# between sessions, renames and deletions all show up. "General" holds items with no session.
FOLDERS = os.path.join(core.LIB, "Sessions")


def _fname(n):
    return re.sub(r'[<>:"/\|?*\x00-\x1f]', "_", str(n or "General")).strip(" .")[:80] or "General"


def sync_folders():
    import json as _j
    names = {}
    for f in (os.listdir(SD) if os.path.isdir(SD) else []):
        if f.endswith(".json"):
            try:
                for s in _j.load(open(os.path.join(SD, f), encoding="utf-8")).get("sessions", []):
                    names[s["id"]] = s.get("name") or s["id"]
            except Exception:
                pass
    want = {}
    for name, meta in core.index().items():
        src = os.path.join(core.LIB, name)
        if os.path.isfile(src):
            sid = (meta or {}).get("session") if isinstance(meta, dict) else None
            want[os.path.join(FOLDERS, _fname(names.get(sid, "General") if sid else "General"), name)] = src
    for dst, src in want.items():
        try:
            if os.path.exists(dst) and os.path.samefile(dst, src):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                os.remove(dst)
            os.link(src, dst)
        except OSError:
            pass
    if os.path.isdir(FOLDERS):                       # drop links for deleted / moved items, then empty folders
        for root, dirs, files in os.walk(FOLDERS, topdown=False):
            for f in files:
                p = os.path.join(root, f)
                if p not in want:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            if root != FOLDERS and not os.listdir(root):
                try:
                    os.rmdir(root)
                except OSError:
                    pass


def start_folders():
    import threading

    def loop():
        while True:
            try:
                sync_folders()
            except Exception:
                pass
            time.sleep(30)
    threading.Thread(target=loop, daemon=True, name="lib-folders").start()
