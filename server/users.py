"""MIR MEDIA LABS users — every person gets their OWN access key.

  * owner  = you. The original key in data/access_key.txt; manages users, sees everything.
  * user   = an invited person. Generates media, sees only their own jobs, library and references.

Keys are random `mml-…` tokens generated here and never derived from anything in MirOS
(this app can't even read MirOS files — see core.safe_path). Presence is tracked per
device so the owner (and the MirOS ACCESS panel, via loopback) can see who is live.
"""
import secrets
import threading
import time

import core

USERS_FILE = core.os.path.join(core.DATA, "users.json")
LIVE_S = 90                     # seen within this many seconds = live
_LOCK = threading.Lock()
_USERS = []                     # [{id, name, key, role, enabled, created, last_seen, last_ip, jobs}]
_SESS = {}                      # (uid, ip, device) -> {first, last, hits, path}
_DIRTY = {"t": 0}


def _new_key():
    return "mml-" + secrets.token_urlsafe(18)


def load():
    global _USERS
    _USERS = core.load_json(USERS_FILE, [])
    if not any(u.get("role") == "owner" for u in _USERS):
        _USERS.insert(0, {"id": "owner", "name": "Owner (this PC)", "key": core.access_key(), "role": "owner",
                          "enabled": True, "created": time.time(), "last_seen": 0, "last_ip": "", "jobs": 0})
        _save()


def _save():
    core.save_json(USERS_FILE, _USERS)
    _DIRTY["t"] = time.time()


def owner():
    return next(u for u in _USERS if u.get("role") == "owner")


def by_key(key):
    if not key:
        return None
    for u in _USERS:
        if u.get("enabled") and secrets.compare_digest(str(u.get("key", "")), str(key)):
            return u
    return None


def by_id(uid):
    return next((u for u in _USERS if u["id"] == uid), None)


def device_of(ua):
    ua = ua or ""
    if "MirMediaLabs-Android" in ua:
        return "Media Lab app"
    for k, v in (("Android", "Android browser"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows PC"),
                 ("Macintosh", "Mac"), ("Linux", "Linux"), ("curl", "script")):
        if k in ua:
            return v
    return "device"


def touch(u, ip, ua, path):
    now = time.time()
    dev = device_of(ua)
    with _LOCK:
        s = _SESS.setdefault((u["id"], ip, dev), {"first": now, "last": 0, "hits": 0, "path": ""})
        s["last"], s["path"] = now, path
        s["hits"] += 1
        u["last_seen"], u["last_ip"] = now, ip
        if now - _DIRTY["t"] > 60:          # persist last_seen at most once a minute
            _save()


def count_job(u):
    with _LOCK:
        u["jobs"] = int(u.get("jobs") or 0) + 1
        _save()


def create(name):
    with _LOCK:
        u = {"id": "u" + secrets.token_hex(4), "name": (name or "guest").strip()[:40] or "guest", "key": _new_key(),
             "role": "user", "enabled": True, "created": time.time(), "last_seen": 0, "last_ip": "", "jobs": 0}
        _USERS.append(u)
        _save()
        return u


def update(uid, action):
    with _LOCK:
        u = by_id(uid)
        if not u:
            return None, "no such user"
        if u["role"] == "owner" and action in ("disable", "delete"):
            return None, "the owner can't be disabled or deleted"
        if action == "disable":
            u["enabled"] = False
        elif action == "enable":
            u["enabled"] = True
        elif action == "newkey":
            u["key"] = _new_key()
        elif action == "delete":
            _USERS.remove(u)
            for k in [k for k in _SESS if k[0] == uid]:
                _SESS.pop(k, None)
        else:
            return None, "unknown action"
        _save()
        return u, None


def summary(include_keys=False, running_by_user=None):
    """Who has access, their devices, and who is live right now."""
    now = time.time()
    out = []
    with _LOCK:
        for u in _USERS:
            devs = [{"ip": k[1], "device": k[2], "first": v["first"], "last": v["last"], "hits": v["hits"],
                     "live": now - v["last"] < LIVE_S}
                    for k, v in _SESS.items() if k[0] == u["id"]]
            devs.sort(key=lambda d: -d["last"])
            row = {"id": u["id"], "name": u["name"], "role": u["role"], "enabled": u["enabled"],
                   "created": u["created"], "last_seen": u.get("last_seen") or 0, "last_ip": u.get("last_ip", ""),
                   "jobs": u.get("jobs") or 0, "running": (running_by_user or {}).get(u["id"], 0),
                   "live": any(d["live"] for d in devs), "devices": devs}
            if include_keys:
                row["key"] = u["key"]
            out.append(row)
    return {"total": len(out), "enabled": sum(1 for u in out if u["enabled"]),
            "live": sum(1 for u in out if u["live"]), "live_devices": sum(1 for u in out for d in u["devices"] if d["live"]),
            "users": out, "ts": now}
