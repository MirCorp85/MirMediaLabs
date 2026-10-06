"""MIR MEDIA LABS users — every person gets their OWN access key.

  * owner  = you. The original key in data/access_key.txt; sees everything.
  * user   = an invited person. Generates media, sees only their own jobs, library and references.

Access is managed ONLY from the host PC (the machine with the GPU, in the MIR MEDIA LABS desktop app):
grant a key, choose which engines a person may use, a daily request limit and an expiry date, revoke or
restore access, rotate keys, and read the access log. Keys are random `mml-…` tokens generated here.
Presence is tracked per device so the host can see who is live.
"""
import secrets
import threading
import time

import core

USERS_FILE = core.os.path.join(core.DATA, "users.json")
LOG_FILE = core.os.path.join(core.DATA, "access_log.json")
LIVE_S = 90                     # seen within this many seconds = live
_LOCK = threading.Lock()
_USERS = []                     # [{id, name, key, role, enabled, created, last_seen, last_ip, jobs, allow, daily, expires, today}]
_SESS = {}                      # (uid, ip, device) -> {first, last, hits, path}
_DIRTY = {"t": 0}
ENGINES = ("h3", "music3", "qimg", "ace", "llama")    # what "allow" can list (Auto routes into these)


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


# ── access log (host panel → Activity) ──────────────────────────────────────
def log(event, who=""):
    with _LOCK:
        items = core.load_json(LOG_FILE, [])
        items.append({"t": time.time(), "event": event, "who": who})
        core.save_json(LOG_FILE, items[-300:])


def recent_log(n=60):
    return list(reversed(core.load_json(LOG_FILE, [])[-n:]))


def owner():
    return next(u for u in _USERS if u.get("role") == "owner")


def expired(u):
    return bool(u.get("expires")) and time.time() > float(u["expires"])


def by_key(key):
    if not key:
        return None
    for u in _USERS:
        if u.get("enabled") and secrets.compare_digest(str(u.get("key", "")), str(key)) and not expired(u):
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


# ── one device per key ─────────────────────────────────────────────────────
SETUP_S = 30 * 60               # first 30 min after locking: the same KIND of device may take the key over
                                # (iPhone Safari → its Home-Screen app keeps separate cookies; a re-install)


def bind_device(u, dev, kind):
    """A person's key works on ONE device: the first one that uses it. None = allowed, else the reason.
    The owner's master key is never locked. The host frees a key with 'Reset device' (or a new key)."""
    if u.get("role") == "owner":
        return None
    now = time.time()
    with _LOCK:
        b = u.get("device")
        if not b:
            u["device"] = {"id": dev, "kind": kind, "since": now, "seen": now}
            _save()
            what = "key locked to this person's %s" % kind
        elif b["id"] == dev:
            if now - b.get("seen", 0) > 300:
                b["seen"] = now
                _save()
            return None
        elif kind == b.get("kind") and now - b.get("since", 0) < SETUP_S:
            u["device"] = {"id": dev, "kind": kind, "since": b["since"], "seen": now}
            _save()
            what = "key moved to the same person's new %s (setup window)" % kind
        else:
            return ("this key is already in use on another device (%s). Each key works on one device — ask the host "
                    "for your own key, or to reset this one" % b.get("kind", "device"))
    log(what, u["name"])
    return None


# ── permissions ────────────────────────────────────────────────────────────
def _day():
    return time.strftime("%Y-%m-%d")


def used_today(u):
    t = u.get("today") or {}
    return int(t.get("n") or 0) if t.get("day") == _day() else 0


ENGINE_NAMES = {"h3": "Video", "music3": "Song", "qimg": "Image", "ace": "Music", "llama": "Chat / writing"}


def can_use(u, engine):
    """None if allowed, else the reason (shown to the person)."""
    if u.get("role") == "owner":
        return None
    allow = u.get("allow")
    if allow and engine in ENGINES and engine not in allow:
        return "your access doesn't include %s — ask the host to add it" % ENGINE_NAMES.get(engine, engine)
    return None


def over_limit(u):
    if u.get("role") == "owner" or not int(u.get("daily") or 0):
        return None
    if used_today(u) >= int(u["daily"]):
        n = int(u["daily"])
        return "you've reached today's limit of %d request%s — it resets at midnight" % (n, "" if n == 1 else "s")
    return None


def count_job(u):
    with _LOCK:
        u["jobs"] = int(u.get("jobs") or 0) + 1
        u["today"] = {"day": _day(), "n": used_today(u) + 1}
        _save()


def _clean_allow(allow):
    if not allow:
        return None                                   # None = every engine
    a = [e for e in allow if e in ENGINES]
    return a if a and len(a) < len(ENGINES) else None


def _expiry(days):
    try:
        d = float(days or 0)
    except (TypeError, ValueError):
        d = 0
    return time.time() + d * 86400 if d > 0 else 0


def create(name, allow=None, daily=0, expires_days=0):
    with _LOCK:
        u = {"id": "u" + secrets.token_hex(4), "name": (name or "guest").strip()[:40] or "guest", "key": _new_key(),
             "role": "user", "enabled": True, "created": time.time(), "last_seen": 0, "last_ip": "", "jobs": 0,
             "allow": _clean_allow(allow), "daily": max(0, int(daily or 0)), "expires": _expiry(expires_days)}
        _USERS.append(u)
        _save()
    log("granted access", u["name"])
    return u


def update(uid, action, data=None):
    data = data or {}
    with _LOCK:
        u = by_id(uid)
        if not u:
            return None, "no such user"
        if u["role"] == "owner" and action in ("disable", "delete", "settings"):
            return None, "the owner always has full access"
        if action == "disable":
            u["enabled"] = False
            what = "revoked access"
        elif action == "enable":
            u["enabled"] = True
            what = "restored access"
        elif action == "unbind":
            if u["role"] == "owner":
                return None, "the master key isn't locked to a device"
            u.pop("device", None)
            for k in [k for k in _SESS if k[0] == uid]:
                _SESS.pop(k, None)
            what = "reset the device lock (the next device that signs in gets the key)"
        elif action == "newkey":
            u["key"] = _new_key()
            u.pop("device", None)                         # a fresh key locks to the next device that uses it
            for k in [k for k in _SESS if k[0] == uid]:   # old devices drop off the live list
                _SESS.pop(k, None)
            what = "issued a new key (the old one stopped working)"
        elif action == "delete":
            _USERS.remove(u)
            for k in [k for k in _SESS if k[0] == uid]:
                _SESS.pop(k, None)
            what = "removed"
        elif action == "settings":
            if "name" in data:
                u["name"] = (str(data["name"]).strip()[:40]) or u["name"]
            if "allow" in data:
                u["allow"] = _clean_allow(data["allow"])
            if "daily" in data:
                u["daily"] = max(0, int(data.get("daily") or 0))
            if "expires_days" in data:
                u["expires"] = _expiry(data["expires_days"])
            what = "changed access settings"
        else:
            return None, "unknown action"
        _save()
    log(what, u["name"])
    return u, None


def summary(include_keys=False, running_by_user=None):
    """Who has access, their limits, their devices, and who is live right now."""
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
                   "live": any(d["live"] for d in devs), "devices": devs, "allow": u.get("allow"),
                   "daily": int(u.get("daily") or 0), "today": used_today(u), "expires": u.get("expires") or 0,
                   "expired": expired(u),
                   "locked": None if u["role"] == "owner" or not u.get("device") else
                   {"kind": u["device"].get("kind", "device"), "since": u["device"].get("since", 0),
                    "seen": u["device"].get("seen", 0)}}
            if include_keys:
                row["key"] = u["key"]
            out.append(row)
    return {"total": len(out), "enabled": sum(1 for u in out if u["enabled"] and not u["expired"]),
            "live": sum(1 for u in out if u["live"]), "live_devices": sum(1 for u in out for d in u["devices"] if d["live"]),
            "today": sum(u["today"] for u in out), "users": out, "ts": now}
