"""MOTION LIBRARY (Oct 29 2026, user: "a complete library … places, characters, objects, animals — the explained editor and
the motion editor can share the same library since they use the same motion assets").

One catalog for every editor: Motion Studio (Diorama pickers, Explainer pictures)
and the agents. The vocabulary is dumped from the engine itself (TOOLS/MirRemotion/mg_assets/build_library.py →
public/mg/library/vocab.json + characters.json + thumbs/*.webp), the places come from the kit library (motion_kits.py), so the
server never offers something the renderer cannot draw.

Item ids (used by the "dio" picture kind and EXPLAINED's lib: figures):  act:<name> · char:<id> · animal:<kind> · obj:<item>
· prop:<type> · place:<id> · world:<id> · ride:<act>"""
import json
import os
import time

import motion_kits

_C = {"sig": None}


def _mg():
    from motion_wizard import MG
    return MG


def _load(name, d):
    path = os.path.join(_mg(), "library", name)
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return d


def builtin_vocab():
    """The engine's own vocabulary (vocab.json, cached until it changes) - without the minted additions."""
    path = os.path.join(_mg(), "library", "vocab.json")
    sig = os.path.getmtime(path) if os.path.exists(path) else 0
    if _C["sig"] != sig:
        _C.update(sig=sig, v=_load("vocab.json", {}), chars=_load("characters.json", []), fsig=None)
    return _C["v"]


def vocab():
    """builtin_vocab() + everything the MINT designed (motion_mint.py, Nov 2 2026), so every validator and writer prompt knows it."""
    import motion_mint
    B = builtin_vocab()
    if _C.get("vf") is not None and _C.get("fsig") and time.time() - _C.get("ft", 0) < 5:      # the mint folders are re-listed at most every 5 s
        return _C["vf"]
    X = motion_mint.vocab_extra()
    fsig = json.dumps({k: sorted(v) for k, v in X.items()}, sort_keys=True)
    _C["ft"] = time.time()
    if _C.get("fsig") != fsig or _C.get("vf") is None:
        V = dict(B)
        for k in ("acts", "species", "worlds"):
            V[k] = dict(B.get(k) or {}, **X[k])
        for k in ("items", "pieces", "hats", "props"):
            V[k] = list(B.get(k) or []) + [x for x in X[k] if x not in (B.get(k) or [])]
        lk = dict(B.get("looks") or {})
        lk["hat"] = list(lk.get("hat") or []) + [x for x in X["hats"] if x not in (lk.get("hat") or [])]
        V["looks"] = lk
        _C.update(fsig=fsig, vf=V)
        motion_mint.sync_worlds()
    return _C["vf"]


def characters():
    builtin_vocab()
    return _C["chars"]


def thumb(cat, i):
    f = "%s_%s.webp" % (cat, i)
    return "mg/library/thumbs/" + f if os.path.exists(os.path.join(_mg(), "library", "thumbs", f)) else ""


BUILTIN_NAMES = {"apartment": "Apartment", "office": "Office", "lab": "Lab", "cafe": "Cafe", "street": "Street corner", "rooftop": "Rooftop"}


def catalog():
    """{category: [items]} - every item {id, name, desc, tags, thumb, ...}; ids are "<cat>:<name>"."""
    v = vocab()
    out = {"worlds": [], "places": [], "characters": [], "animals": [], "actions": [], "rides": [], "vfx": [], "objects": [], "props": []}
    for w, e in (v.get("worlds") or {}).items():
        out["worlds"].append({"id": "world:" + w, "key": w, "name": e["name"], "desc": e["about"], "tags": motion_kits.WORLDS.get(w, ("", "", ""))[2].split()[:12], "thumb": thumb("world", w)})
    for k, sts in (v.get("places") or {}).items():
        out["places"].append({"id": "place:" + k, "key": k, "name": BUILTIN_NAMES.get(k, k), "desc": motion_kits.BUILTIN.get(k, ""), "world": "city", "stations": sts, "thumb": thumb("place", k), "builtin": True})
    for k in motion_kits.catalog(_mg()):
        out["places"].append({"id": "place:" + k["id"], "key": k["id"], "name": k["name"], "desc": k["about"], "world": k["world"], "stations": k["stations"], "tags": k["tags"],
                              "source": k["source"], "thumb": thumb("place", k["id"])})
    for c in characters():
        out["characters"].append({"id": "char:" + c["id"], "key": c["id"], "name": c["name"], "desc": c["role"], "look": c["look"], "act": c["act"], "thumb": thumb("char", c["id"])})
    for k, e in (v.get("species") or {}).items():
        out["animals"].append({"id": "animal:" + k, "key": k, "name": e["name"], "desc": e.get("type", ""), "tags": str(e.get("tags") or "").split(), "thumb": thumb("animal", k)})
    for k, e in (v.get("acts") or {}).items():
        row = {"id": "act:" + k, "key": k, "name": k, "desc": e["desc"], "cat": e["cat"], "thumb": thumb("act", k)}
        (out["rides"] if e["cat"] == "ride" else out["actions"]).append(row)
    for k, e in (v.get("vfx") or {}).items():
        out["vfx"].append({"id": "vfx:" + k, "key": k, "name": k, "desc": e.get("desc") or "", "thumb": thumb("vfx", k)})
    for k in v.get("items") or []:
        out["objects"].append({"id": "obj:" + k, "key": k, "name": k, "desc": "held object", "thumb": thumb("obj", k)})
    for k in v.get("props") or []:
        if k not in ("patch", "court", "board", "window"):
            out["props"].append({"id": "prop:" + k, "key": k, "name": k, "desc": "scenery / furniture", "thumb": thumb("prop", k)})
    return out


def search(q="", cat="", world=""):
    q = str(q or "").lower().strip()
    cats = catalog()
    res = {}
    for c, items in cats.items():
        if cat and c != cat:
            continue
        rows = items
        if world and c == "places":
            rows = [r for r in rows if r.get("world") == world]
        if q:
            rows = [r for r in rows if q in (" ".join([r["name"], r.get("desc") or "", " ".join(r.get("tags") or []), r.get("cat") or ""])).lower()]
        res[c] = rows
    return res


def item(lid):
    """A library id → the engine item {type, …} (for the "dio" picture kind / EXPLAINED lib: figures)."""
    cat, _, key = str(lid or "").partition(":")
    if cat == "char":
        c = next((x for x in characters() if x["id"] == key), None)
        return {"type": "char", "look": c["look"], "act": c["act"]} if c else None
    if cat in ("act", "ride"):
        return {"type": "act", "act": key}
    if cat == "animal":
        return {"type": "animal", "kind": key, "act": "idle"}
    if cat == "obj":
        return {"type": "obj", "name": key}
    if cat == "vfx":
        return {"type": "vfx", "kind": key}
    if cat == "prop":
        return {"type": "prop", "id": key}
    if cat == "place":
        lib = motion_kits.library(_mg())
        return {"type": "place", "id": key, "kit": lib.get(key)} if key in lib else {"type": "place", "id": key}
    return None


def match(concept):
    """The library item a picture concept names exactly (an animal, a character role, a held object), else "" - used before the
    still-icon fallback so a "dog" or a "doctor" on screen is alive."""
    ws = [w for w in __import__("re").findall(r"[a-z]+", str(concept or "").lower()) if len(w) > 2]
    if not ws or len(ws) > 3:
        return ""
    v = vocab()
    from motion_wizard import SPECIES_WORDS
    for w in ws:
        k = SPECIES_WORDS.get(w, w)
        if k in (v.get("species") or {}):
            return "animal:" + k
    for c in characters():
        if any(w in (c["id"], c["name"].lower()) or w in c["name"].lower().split() for w in ws):
            return "char:" + c["id"]
    for w in ws:
        if w in (v.get("items") or []):
            return "obj:" + w
    return ""


def brief_for_writer(world="city"):
    """A compact list of the library for writer prompts (actions by group, animals, objects)."""
    v = vocab()
    groups = {}
    for k, e in (v.get("acts") or {}).items():
        groups.setdefault(e["cat"], []).append(k)
    acts = "\n".join("  %s: %s" % (g, " ".join(ks)) for g, ks in groups.items())
    return {"acts": acts, "animals": " ".join((v.get("species") or {}).keys()), "items": " ".join(v.get("items") or []),
            "ambients": "|".join(v.get("ambients") or []), "vfx": "|".join((v.get("vfx") or {}).keys()), "outfits": "|".join((v.get("looks") or {}).get("outfit") or []), "hats": "|".join((v.get("looks") or {}).get("hat") or []),
            "colors": "|".join((v.get("looks") or {}).get("color") or []), "hairs": "|".join((v.get("looks") or {}).get("hair") or [])}


def register(app, hk):
    from flask import jsonify, request

    @app.route("/motion/library")
    def mglib_page():
        """The library browser / picker page (motion/library?pick=characters,animals&for=<tag>)."""
        return hk["static"]("motion_library.html")

    @app.route("/api/mglib")
    def mglib_catalog():
        """The shared motion library: ?q= search · ?cat= one category · ?world= places of one world."""
        a = request.args
        return jsonify({"cats": search(a.get("q"), a.get("cat"), a.get("world")), "vocab": {k: vocab().get(k) for k in ("act_cats", "animal_acts", "ambients", "looks", "hats")}})

    @app.route("/api/mglib/item/<path:lid>")
    def mglib_item(lid):
        it = item(lid)
        return (jsonify(it), 200) if it else (jsonify({"error": "not in the library"}), 404)
