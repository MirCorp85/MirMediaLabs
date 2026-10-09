"""
sessions.py — chat sessions (projects) for MIR MEDIA LABS: every chat request and every file it makes belongs to one,
so the chat and the library can be split by project.
═══════════════════════════════════════════════════════════════════════════════
IDENTICAL in both copies (standalone server/sessions.py and MirOS aimr-trading/miros_mlab/sessions.py) — copy, never
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

try:                      # MirOS copy lives in the miros_mlab package
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
