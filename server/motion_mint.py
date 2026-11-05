"""Diorama MINT - new motion assets made to fit the narration (Nov 2 2026).

User: "the motion videos keep making motions that have nothing to do with what the narrator is saying, we have to create a system
where if there are no motion samples that can be used from the assets, it should be able to create new ones customized to the
video's words and topics, including new characters, new worlds, new objects or new scenes".

The narration pass (motion_wizard.direct_line) can only pick from the fixed library, so a line whose verb, object or animal is not
in it falls back to "stand" / "explain". The mint closes that gap:
  1. audit()  - the brain reads every line beside what the animation currently shows + the whole library, and returns
                fixes (a library entry that DOES fit) and needs (nothing fits: a new act / item / hat / piece / animal / prop).
  2. design() - each need is designed as DATA in the engine's mint format (src/mg/dio_mint.ts): keyframes for movements, shape
                lists for objects, overrides of a built-in animal, sanitized here and saved to <MG>/library/mint/<kind>/<id>.json,
                so every later film reuses it (the library only grows).
  3. reapply() - after every narration pass the minted choices are put back on their lines (they are stored on the beat as
                b["mint"], keyed by the line text: an edited line is audited again).
  4. bundle() - the minted specs a film uses (+ what they depend on) ride along as the mg-diorama prop `mint`.
New WORLDS are designed by design_world() when the world picker finds no world that fits the premise."""
import glob
import hashlib
import json
import os
import re
import subprocess
import time

KINDS = ["acts", "items", "hats", "pieces", "species", "props", "worlds"]
_ID = re.compile(r"^[a-z][a-z0-9_]{2,23}$")
_CACHE = {}
LEGS = ["stand", "walk", "run", "step", "sit", "kneel", "crouch", "jump", "pedal", "straddle", "hidden", "tiptoe"]
EYES = ["closed", "laugh", "wide", "squint"]
SHAPES = ["rect", "circle", "ellipse", "poly", "line", "curve", "arc", "text"]
ANIMS = ["spin", "bob", "sway", "pulse", "flicker", "blink", "flow"]
PALETTE = ["char0", "char1", "graph", "graph2", "steel", "steel2", "silver", "silver2", "bronze", "brass", "gold", "champ", "pale", "white", "ember", "olive", "olive2",
           "red", "leaf", "leaf2", "wood", "wood2", "stone", "stone2", "sand", "sky", "water", "blue", "green", "purple", "pink", "black", "glass", "fire", "light"]
RECIPES = ["field", "farm", "trees", "hay", "windmill", "pond", "lake", "pines", "rocks", "clearing", "beach", "palms", "lighthouse", "dunes", "cacti", "camp", "cabins",
           "snowmen", "ruins", "craters", "trench", "armor", "domes", "rocket", "village", "castle", "market", "jungle", "temple", "river", "island", "ships", "icebergs", "sea"]
SP_NUM = {"len": (10, 400), "h": (6, 260), "leg": (0, 260), "head": (6, 90), "neck": (0, 260), "snout": (0, 80), "size": (6, 300)}
SP_FLAGS = ["horns", "antlers", "mane", "wool", "hop", "beard", "lionmane", "trunk", "tusks", "ossicones", "hump", "wings", "biped", "horn", "comb", "flat", "owl", "white",
            "penguin", "fin", "whale", "bee", "ground"]
SP_COLS = ["c0", "c1", "belly", "face", "beak", "stripes", "patches", "spots"]
SP_EAR = ["flop", "point", "side", "long", "round", "big", "horn", "none"]
ANIMAL_ACTS = ["idle", "walk", "run", "sit", "sleep", "eat", "speak", "wag", "jump", "fly", "swim", "follow", "beg"]
SPRITE_MOVES = ["body", "legA", "legB", "head", "jaw", "tail", "wing", "fin", "none"]
SP_TAIL = ["wag", "curl", "long", "tuft", "short", "bushy", "puff", "thin"]


def _mg():
    from motion_wizard import MG
    return MG


def _dir(kind):
    d = os.path.join(_mg(), "library", "mint", kind)
    os.makedirs(d, exist_ok=True)
    return d


def library(kind):
    """{id: spec} of one minted kind (re-read when a file changes)."""
    d = _dir(kind)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    sig = tuple((f, os.path.getmtime(os.path.join(d, f))) for f in fs)
    c = _CACHE.get(kind)
    if not c or c[0] != sig:
        out = {}
        for f in fs:
            try:
                j = json.load(open(os.path.join(d, f), encoding="utf-8"))
                if isinstance(j, dict) and _ID.match(str(j.get("id") or "")):
                    out[j["id"]] = j
            except Exception:
                pass
        _CACHE[kind] = c = (sig, out)
    return c[1]


def _save(kind, spec):
    spec.update(source="minted", created=time.strftime("%Y-%m-%d"))
    with open(os.path.join(_dir(kind), spec["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    _CACHE.pop(kind, None)
    return spec


def _builtin():
    """The engine's own vocabulary (vocab.json, built from dio_lib.ts) - never the minted additions."""
    import motion_library
    return motion_library.builtin_vocab()


def vocab_extra():
    """Minted entries in vocab.json's shapes, merged in by motion_library.vocab() so every validator accepts them."""
    return {"acts": {k: {"cat": v.get("cat") or "minted", "desc": v.get("desc") or k, "minted": True} for k, v in library("acts").items()},
            "species": {k: {"name": v.get("name") or k, "type": "minted", "tags": v.get("tags") or k, "minted": True} for k, v in library("species").items()},
            "items": list(library("items")), "hats": list(library("hats")), "pieces": list(library("pieces")), "props": list(library("props")),
            "worlds": {k: {"name": v.get("name") or k, "about": v.get("about") or "", "minted": True} for k, v in library("worlds").items()}}


def sync_worlds():
    """Minted worlds join motion_kits.WORLDS (name, about, tags) so the picker, scout and validators know them."""
    import motion_kits
    for k, v in library("worlds").items():
        if k not in motion_kits.WORLDS or motion_kits.WORLDS[k][2].startswith("minted "):
            motion_kits.WORLDS[k] = (v.get("name") or k, v.get("about") or "", "minted " + " ".join(v.get("tags") or []))


# ── sanitizers: the brain's JSON → only what dio_mint.ts can draw ──
def _n(v, lo, hi, d=0.0):
    try:
        x = float(v)
    except Exception:
        return d
    return round(min(hi, max(lo, x)), 3)


def _col(v):
    if isinstance(v, list) and len(v) == 2:
        a, b = _col(v[0]), _col(v[1])
        return [a, b] if a and b else a or b
    v = str(v or "").strip()
    if v in PALETTE or re.match(r"^#[0-9a-fA-F]{3,8}$", v) or re.match(r"^rgba?\([\d.,\s]+\)$", v):
        return v
    return None


def _id(v):
    return re.sub(r"[^a-z0-9_]", "", str(v or "").lower().replace(" ", "_").replace("-", "_"))[:24]


def shapes(raw, lim=600, n=70):
    out = []
    for s in (raw if isinstance(raw, list) else [])[:n]:
        if not isinstance(s, dict) or s.get("s") not in SHAPES:
            continue
        o = {"s": s["s"]}
        for k in ("x", "y", "w", "h", "r", "rx", "ry"):
            if k in s:
                o[k] = _n(s[k], -lim, lim)
        for k in ("rot", "a0", "a1"):
            if k in s:
                o[k] = _n(s[k], -7, 7)
        if isinstance(s.get("p"), list):
            o["p"] = [[_n(q[0], -lim, lim), _n(q[1], -lim, lim)] for q in s["p"][:40] if isinstance(q, (list, tuple)) and len(q) >= 2]
            if not o["p"]:
                continue
        for k in ("fill", "stroke"):
            c = _col(s.get(k)) if s.get(k) is not None else None
            if c:
                o[k] = c
        if "fill" not in o and "stroke" not in o:
            o["fill"] = "steel"
        if s.get("lw") is not None:
            o["lw"] = _n(s["lw"], .5, 40, 3)
        if s.get("a") is not None:
            o["a"] = _n(s["a"], 0, 1, 1)
        if s.get("close"):
            o["close"] = True
        if s["s"] == "text":
            o["text"], o["size"] = str(s.get("text") or "")[:24], _n(s.get("size"), 6, 120, 20)
        an = s.get("anim")
        if isinstance(an, dict) and an.get("k") in ANIMS:
            o["anim"] = {"k": an["k"], "sp": _n(an.get("sp"), .05, 6, 1), "amp": _n(an.get("amp"), 0, 4, 1), "px": _n(an.get("px"), -lim, lim), "py": _n(an.get("py"), -lim, lim)}
        out.append(o)
    return out


def _hand(v, d, sh=None):
    """A hand target, pulled back inside the arm's reach (150 from its shoulder) so the IK never snaps the elbow backwards."""
    h = [_n(v[0], -220, 280, d[0]), _n(v[1], -560, 40, d[1])] if isinstance(v, (list, tuple)) and len(v) >= 2 else list(d)
    if sh:
        dx, dy = h[0] - sh[0], h[1] - sh[1]
        r = (dx * dx + dy * dy) ** .5
        if r > 150:
            h = [round(sh[0] + dx * 150 / r, 1), round(sh[1] + dy * 150 / r, 1)]
    return h


def sanitize_act(raw, ids):
    keys = []
    for k in (raw.get("keys") or [])[:10]:
        if not isinstance(k, dict):
            continue
        o = {"u": _n(k.get("u"), 0, 1), "far": _hand(k.get("far"), (-58, -188), (-44, -306)), "near": _hand(k.get("near"), (58, -188), (44, -306))}
        for f, lo, hi in (("lean", -.8, .8), ("lift", 0, 220), ("drop", 0, 220), ("rot", -3.2, 3.2), ("tilt", -.5, .5), ("walk", 0, 1), ("shrug", 0, 20), ("shift", -200, 200)):
            if k.get(f) is not None:
                o[f] = _n(k[f], lo, hi)
        if isinstance(k.get("look"), (list, tuple)) and len(k["look"]) >= 2:
            o["look"] = [_n(k["look"][0], -4, 4), _n(k["look"][1], -4, 4)]
        if k.get("legs") in LEGS:
            o["legs"] = k["legs"]
        if isinstance(k.get("face"), dict):
            o["face"] = _face(k["face"])
        keys.append(o)
    if not keys:
        raise ValueError("a movement needs keyframes")
    keys.sort(key=lambda k: k["u"])
    out = {"id": raw["id"], "kind": "act", "cat": _id(raw.get("cat")) or "minted", "desc": str(raw.get("desc") or raw["id"])[:90],
           "loop": _n(raw.get("loop"), .3, 8, 1.6), "keys": keys, "tags": [t for t in (_id(x) for x in raw.get("tags") or []) if t][:10]}
    for f in ("once", "pingpong", "talk", "move"):
        if raw.get(f):
            out[f] = True
    if raw.get("legs") in LEGS:
        out["legs"] = raw["legs"]
    if raw.get("speed") is not None:
        out["speed"] = _n(raw["speed"], 0, 20, 6)
    hold = raw.get("hold")
    if isinstance(hold, list) and len(hold) == 2:
        out["hold"] = [h if h in ids["items"] else None for h in hold]
        if not any(out["hold"]):
            out.pop("hold")
    if isinstance(raw.get("hang"), (int, float)):
        out["hang"] = _n(raw["hang"], -3.2, 3.2, 0)
    for f, pool in (("two", "items"), ("piece", "pieces"), ("ride", "rides"), ("hat", "hats"), ("amb", "ambients")):
        if raw.get(f) in ids[pool]:
            out[f] = raw[f]
    if isinstance(raw.get("face"), dict):
        out["face"] = _face(raw["face"])
    return out


def _face(f):
    o = {k: _n(f[k], -1.5, 1.5) for k in ("o", "b", "f", "m") if f.get(k) is not None}
    if f.get("eyes") in EYES:
        o["eyes"] = f["eyes"]
    if f.get("tears"):
        o["tears"] = True
    return o


def sanitize_shapes_kind(raw, kind):
    out = {"id": raw["id"], "kind": kind[:-1], "name": str(raw.get("name") or raw["id"])[:40], "desc": str(raw.get("desc") or "")[:90],
           "tags": [t for t in (_id(x) for x in raw.get("tags") or []) if t][:10]}
    if kind == "pieces":
        out["shapes"], out["back"] = shapes(raw.get("shapes") or raw.get("front")), shapes(raw.get("back"))
    elif kind == "props":
        out.update(w=_n(raw.get("w"), .1, 4, 1), d=_n(raw.get("d"), .1, 4, 1), h=_n(raw.get("h"), .05, 5, 1), shapes=shapes(raw.get("shapes"), 700))
    else:
        out["shapes"] = shapes(raw.get("shapes"), 420 if kind == "items" else 220, 40)      # wide enough for a planted pole (a tight clamp chopped shafts)
    if not out["shapes"]:
        raise ValueError("nothing drawable came back")
    return out


def sanitize_species(raw, base_ids):
    if isinstance(raw.get("parts"), list) and raw["parts"]:                # B) a shape-drawn creature (dio_mint.ts drawSprite)
        parts = []
        for pt in raw["parts"][:24]:
            if not isinstance(pt, dict):
                continue
            sh = shapes(pt.get("shapes"), 700, 30)
            if sh:
                pv = pt.get("pivot") if isinstance(pt.get("pivot"), (list, tuple)) and len(pt.get("pivot")) >= 2 else [0, 0]
                parts.append({"move": pt.get("move") if pt.get("move") in SPRITE_MOVES else "none", "pivot": [_n(pv[0], -700, 700), _n(pv[1], -700, 700)], "shapes": sh})
        if not parts:
            raise ValueError("the creature has no drawable parts")
        tags = raw.get("tags") or ""
        tags = tags.split() if isinstance(tags, str) else [str(x) for x in tags] if isinstance(tags, list) else []
        out = {"id": raw["id"], "kind": "species", "name": str(raw.get("name") or raw["id"])[:30], "h": _n(raw.get("h"), 20, 700, 160), "len": _n(raw.get("len"), 20, 900, 200),
               "parts": parts, "tags": " ".join(t for t in (_id(x) for x in tags) if t)[:120] or raw["id"]}
        for f in ("swim", "fly"):
            if raw.get(f):
                out[f] = True
        if out.get("swim") or out.get("fly"):
            out["alt"] = _n(raw.get("alt"), 40, 300, 150)
        return out
    base = raw.get("base") if raw.get("base") in base_ids else "dog"
    o = {}
    src = raw.get("o") if isinstance(raw.get("o"), dict) else raw
    for k, (lo, hi) in SP_NUM.items():
        if src.get(k) is not None:
            o[k] = _n(src[k], lo, hi)
    for k in SP_FLAGS:
        if k in src:
            o[k] = bool(src[k])
    for k in SP_COLS:
        c = _col(src.get(k))
        if c and isinstance(c, str):
            o[k] = c
    if src.get("ear") in SP_EAR:
        o["ear"] = src["ear"]
    if src.get("tail") in SP_TAIL:
        o["tail"] = src["tail"]
    tags = raw.get("tags") or ""
    tags = tags.split() if isinstance(tags, str) else [str(x) for x in tags] if isinstance(tags, list) else []
    return {"id": raw["id"], "kind": "species", "name": str(raw.get("name") or raw["id"])[:30], "base": base, "o": o,
            "tags": " ".join(t for t in (_id(x) for x in tags) if t)[:120] or raw["id"]}


def sanitize_world(raw, ids):
    base = raw.get("base") if raw.get("base") in ids["worlds_builtin"] else "city"
    src = raw.get("o") if isinstance(raw.get("o"), dict) else raw
    o = {}
    for k in ("ground", "lot", "edge", "path", "haze"):
        c = _col(src.get(k))
        if c and isinstance(c, str):
            o[k] = c
    if isinstance(src.get("sky"), list) and len(src["sky"]) == 3 and all(isinstance(_col(x), str) for x in src["sky"]):
        o["sky"] = src["sky"]
    for k in ("sun", "moon", "planet"):
        if k in src:
            o[k] = bool(src[k])
    if src.get("stars") is not None:
        o["stars"] = int(_n(src["stars"], 0, 200, 40))
    fill = []
    for r in src.get("fill") or []:
        if r in RECIPES:
            fill.append(r)
        elif isinstance(r, str) and r.startswith("props:"):
            ks = [k for k in r[6:].split(",") if k in ids["props"]]
            if ks:
                fill.append("props:" + ",".join(ks[:4]))
    if fill:
        o["fill"] = fill[:10]
    w = src.get("walk") if isinstance(src.get("walk"), dict) else {}
    if w:
        wk = {"people": int(_n(w.get("people"), 0, 14, 4))}
        if isinstance(w.get("look"), dict):
            LK = _builtin().get("looks") or {}
            wk["look"] = {k: v for k, v in w["look"].items() if k in ("outfit", "hat", "color") and (v in (LK.get(k) or []) or k == "hat" and v in ids["hats"])}
        an = [a for a in w.get("animals") or [] if a in ids["species"]][:5]
        if an:
            wk["animals"] = an
        if w.get("act") in ids["acts"]:
            wk["act"] = w["act"]
        o["walk"] = wk
    if src.get("amb") in ids["ambients"]:
        o["amb"] = src["amb"]
    if src.get("floor") in ids["floors"]:
        o["floor"] = src["floor"]
    if o.get("path") and o.get("path") == o.get("lot"):          # no streets → no plot outlines either (one continuous landscape)
        o["edge"] = "rgba(0,0,0,0)"
    o["water"] = src["water"] if src.get("water") in ("edge", "all") else ""       # always explicit: else the base's sea (ocean = "all") leaks in
    LK = _builtin().get("looks") or {}
    hero = raw.get("hero") if isinstance(raw.get("hero"), dict) else {}
    hero = {k: v for k, v in hero.items() if k in ("outfit", "color", "hat") and (v in (LK.get(k) or []) or k == "hat" and v in ids["hats"])}
    return {"id": raw["id"], "kind": "world", "name": str(raw.get("name") or raw["id"])[:30], "hero": hero, "about": str(raw.get("about") or "")[:160], "base": base, "o": o,
            "tags": [t for t in (_id(x) for x in raw.get("tags") or []) if t][:16]}


def _ids():
    B = _builtin()
    X = vocab_extra()
    return {"items": set(B.get("items") or []) | set(X["items"]), "pieces": set(B.get("pieces") or []) | set(X["pieces"]), "rides": set(B.get("rides") or []),
            "hats": set(B.get("hats") or []) | set(X["hats"]), "ambients": set(B.get("ambients") or []), "acts": set(B.get("acts") or {}) | set(X["acts"]),
            "species": set(B.get("species") or {}) | set(X["species"]), "props": set(B.get("props") or []) | set(X["props"]), "floors": set(B.get("floors") or []),
            "worlds_builtin": set(B.get("worlds") or {}), "species_builtin": set(B.get("species") or {})}


# ── the designers ──
RIG = """RIG FRAME (people): feet at (0,0), up is NEGATIVE y, an adult is 400 units tall, the body faces +x. "near" = the arm in FRONT of the
body (drawn over it), "far" = the arm BEHIND the body. Shoulders: far (-44,-306), near (44,-306); each arm reaches at most 150 from its shoulder.
Landmarks: hands hanging at the sides far=[-58,-188] near=[58,-188] · hips y=-200 · chest y=-286 · mouth y=-370 · eyes/ear y=-392 · top of head
y=-430 · hands straight up y=-452 · reaching forward x=120..140 y=-290..-380 · hands down at knee height y=-120 (with drop 40-80 to crouch).
ARM RULES (they keep the drawing correct):
- Something at the MOUTH or EYES (horn, conch, binoculars, a drink, a camera): the NEAR hand holds it at about [30..50, -365] and set
  "hang" (usually 0) so it sits level instead of tilting with the forearm; the FAR hand stays at the side [-58,-188] (a far hand raised to the
  face draws as a bar behind the head). Never put the far hand above y=-345 with x > -20.
- Anything WORN on the face or head (mask, goggles, glasses, helmet, crown) is a HAT, not a held object: use "hat", don't hold it.
- Raising something overhead: both hands at x -40..+60, y -440..-460, lean -0.1..0, lift 0-15.
- Working at the ground (planting, digging, hammering a stake): drop 50-90, lean 0.25-0.45, hands at x 70..120, y -150..-200.
- "two" (a two-handed object) is drawn UPRIGHT, unrotated, with its grip point exactly HALFWAY between the two hands. So for anything with a
  vertical shaft (pole, flag, spade, staff, torch) give BOTH hands the SAME x (= where the shaft is) and different heights, 30-70 apart
  (e.g. far [80,-300], near [80,-240]); move the shaft by moving both hands together. For a box/tray/book, hands level, 40-60 apart in x.
  "lean" tips the whole upper body AND whatever it holds; set "hang": 0 to keep a pole / flag / spade plumb while the body leans.
  The ground under a held shaft: its tip is (tip offset below the grip) under the hands' midpoint, and "drop" lowers the hands by the same
  amount - so a planting pole (tip 130 below the grip) touches the ground when the hands' midpoint y = -130 - drop (drop 60 -> y -190).
  Keep the far hand's x >= the far shoulder's x - 10 (no arm thrown behind the back) and never more than 20 right of the near hand.
- Keep lean between -0.35 and 0.5; do not use "tiptoe" unless the line says so; face neutral unless the line gives an emotion or effort.
Built-in examples: wave = near hand [72+-26, -440]; drink = near hand [46,-252] -> [24,-370]; push = both hands [118,-292],[134,-282] lean .2;
lift = both hands [-46,-262] -> [-46,-452] holding a barbell; phone = far hand at the ear [-30,-386] (the ear is the ONE high far-hand target)."""

ACT_SYS = """You are the animator of the Diorama: a narrated animated film of tiny professional characters. Design ONE new movement set
(an "act") as KEYFRAMES so the character does EXACTLY what the narrator describes.
""" + RIG + """
Reply JSON only:
{"id": "<snake_case>", "cat": "work|sport|react|talk|food|fun|war|ride|basic|<new group>", "desc": "<what the body does, <=12 words>",
 "loop": <seconds for one cycle, 0.6-4>, "pingpong": true|false (go there and back), "once": true|false (play once and hold - e.g. sitting down),
 "legs": "LEGS", "talk": false, "move": false (true only if the body travels across the room while doing it),
 "hold": [<far hand item or null>, <near hand item or null>], "hang": <optional fixed angle of the held object in radians: 0 = exactly as drawn
   (upright), 0.3 = tipped forward/down, -0.3 = tipped back/up; omit and it tilts with the forearm>, "two": "<item held in both hands, or omit>", "piece": "<set piece beside them, or omit>",
 "hat": "<hat, or omit>", "face": {"m": -1..1 (mouth: -1 frown, 1 open smile), "b": -1..1 brows, "f": 0..1 effort/frown, "eyes": "closed|laugh|wide|squint"},
 "keys": [{"u": 0..1, "far": [x,y], "near": [x,y], "lean": -0.8..0.8 (forward +), "lift": 0..200 (body up), "drop": 0..200 (body down), "tilt": -0.5..0.5 (head),
           "look": [-4..4, -4..4] (eyes), "legs": "<optional per key>"}, ... 3 to 6 keys]}
Items you may hold: ITEMS. Set pieces: PIECES. Hats: HATS.
Make the motion READABLE from far away: big clear arm paths, a lean or lift where the body works, 3-6 keys, u from 0 to <1."""

SHAPE_GUIDE = """SHAPES (canvas, drawn in order, later on top): {"s":"rect","x","y","w","h","r"} {"s":"circle","x","y","r"} {"s":"ellipse","x","y","rx","ry","rot"}
{"s":"poly","p":[[x,y],...]} (filled) {"s":"line","p":[[x,y],...],"lw"} {"s":"curve","p":[[x0,y0],[cx,cy],[x1,y1],...]} {"s":"arc","x","y","r","a0","a1"} {"s":"text","x","y","text","size"}
each with "fill" and/or "stroke" (+ "lw"), optional "a" (alpha) and "anim": {"k": "spin|bob|sway|pulse|flicker|blink|flow", "sp": speed, "amp": amount,
"px","py": pivot}. Colours: house palette keys PALETTE, a hex, or ["top","bottom"] for a gradient. House look: charcoal + brushed metal + gold, clean
flat shapes, 1-2 highlight strokes; other colours only when the object needs them (a red apple, green leaves, blue water)."""

ITEM_SYS = """You draw props for the Diorama (tiny isometric animated films in charcoal, brushed metal and gold). Design ONE hand-held object.
""" + SHAPE_GUIDE + """
Frame: the hand grips at (0,0); up = -y. Put the GRIP where a hand really holds it: a phone/cup/conch is centred on the grip (about -45..45);
a sword or torch rises from the grip (y 0 -> -200); a pole / flag / spade / staff to be planted or dug with is gripped near its MIDDLE: the shaft
runs from about y +130 (the tip that goes into the ground) to y -170 (top), with any flag or blade at the right end. Objects are clean,
recognisable silhouettes at small size: few strong shapes, a light rim, no thin clutter.
Reply JSON only: {"id","name","desc","tags":[...],"shapes":[... 4-25 shapes]}"""

HAT_SYS = """You draw headwear / head pieces for the Diorama characters (charcoal, brushed metal and gold). Design ONE.
""" + SHAPE_GUIDE + """
Frame: head centre at (0,0), head radius ~40, the face looks to +x, up = -y (a cap sits at y -20..-55, a helmet covers -60..+10).
Reply JSON only: {"id","name","desc","tags":[...],"shapes":[... 3-18 shapes]}"""

PIECE_SYS = """You draw set pieces that stand beside a character in the Diorama (charcoal, brushed metal and gold). Design ONE.
""" + SHAPE_GUIDE + """
Frame: the character stands at x=0 (400 units tall, feet at y=0, up = -y, facing +x); the piece stands on the floor (y=0) in front of them at
x 100..380 (a stove is x 120..360, 230 tall; a door 470 tall). "back" shapes are drawn behind the character (e.g. a chair back), "shapes" in front.
Reply JSON only: {"id","name","desc","tags":[...],"shapes":[...4-30],"back":[...optional]}"""

PROP_SYS = """You draw scenery for the Diorama world map (tiny isometric world, charcoal, brushed metal and gold, other colours only when needed).
Design ONE scenery object drawn as a flat billboard standing on the ground.
""" + SHAPE_GUIDE + """
Frame: its base centre on the ground is (0,0), up = -y; 100 units = one floor tile; it is "w" tiles wide, "d" deep, "h" tall, so the shapes span
x about -50*w..50*w and y 0..-100*h (a person is 210 units tall here; a tree 180-340; a hut 140).
Reply JSON only: {"id","name","desc","tags":[...],"w":..,"d":..,"h":..,"shapes":[...5-35]}"""

SPECIES_SYS = """You design animals / creatures for the Diorama (small clean-shaded characters, charcoal + metal + gold house look, natural
colours for animals). Two ways - choose honestly:
A) ONLY when it is basically a recolour / resize of a built-in animal (panther = big black cat, pony = small horse): {"id","name","base":"<base>",
   "tags":"words","o":{overrides}}. Built-in animals: BASES. Overrides: len h leg head neck snout (numbers, a dog len 120, a horse 230), colours
   c0 c1 belly (hex), ear flop|point|side|long|round|big, tail wag|curl|long|tuft|short|bushy|puff|thin.
B) Everything else (dinosaurs, dolphins, octopus, robots, aliens, any creature whose SHAPE differs): DRAW it as moving parts:
   {"id","name","tags":"words","h": <height in units>, "len": <length>, "swim": bool, "fly": bool, "alt": <hover height if swim/fly, 120-220>,
    "parts": [{"move": "body|legA|legB|head|jaw|tail|wing|fin|none", "pivot": [x,y], "shapes": [...]}, ...]}
   Frame: feet on the ground at y=0, up = -y, the creature FACES +x (head on the right), an adult person is 400 tall (a dog ~110, a horse ~260,
   a triceratops ~260 tall and ~480 long, a dolphin ~300 long). Order = draw order: far legs first, then tail, body, near legs, head, jaw.
   legA and legB swing in opposite phase around their pivot (hip/shoulder) - give it 4 legs as 2 far (legB, legA) + 2 near (legA, legB),
   far legs a shade darker. head nods around the neck pivot; jaw opens around its hinge; tail/fin/wing sway around their root.
   Make it READ at a glance: the defining features big and clear (a triceratops: 3 horns + a big bony frill; a dolphin: beak snout, curved
   dorsal fin, tail flukes, pale belly), solid overlapping shapes with no gaps, an eye with a highlight, a soft belly shade.
""" + SHAPE_GUIDE + """
Reply JSON only (A or B)."""

WORLD_SYS = """You design a new WORLD for the Diorama: a tiny isometric world map where the whole film happens. Adapt the closest built-in world.
Built-in worlds (base): BASES
Lot recipes (what fills empty land): RECIPES, or "props:<id>,<id>" to scatter scenery props: PROPS.
Animals: SPECIES. Floors: FLOORS. Ambience: AMBIENTS.
What the main character wears here: "hero": {"outfit": OUTFITS, "color": COLORS, "hat": HATS} (e.g. a diver: tshirt + teal + a diving hat if one
exists; an astronaut: space).
Reply JSON only: {"id","name","about":"<one line: what is in this world>","base":"<base world id>","tags":[...12 premise words],"hero":{...},
 "o":{"ground":"#hex","lot":"#hex","path":"#hex","edge":"rgba(...)","sky":["#top","#mid","#horizon"],"haze":"rgba(...)","sun":bool,"moon":bool,"planet":bool,
      "stars":0-200,"fill":[...4-8 recipes],"walk":{"people":0-14,"look":{"outfit":"","hat":"","color":""},"animals":[...]},"amb":"","floor":"","water":"edge|all|"}}
The map is a 6x6 grid of square plots: "lot" = the plots, "path" = the strips BETWEEN plots (they read as STREETS), "ground" = beyond the map.
A world with no streets (sea floor, reef, forest, jungle, desert, moon, ice) sets "path" EQUAL to "lot" so the plots merge into one landscape.
"water": "all" = the open sea SURFACE (waves everywhere, ships, no ground); a sea floor / reef is NOT water - give it a sand/rock lot instead.
Passers-by ("walk"): people dressed for this place (use the hero's outfit/hat when everyone here would wear it, e.g. divers), or 0 people.
Keep the house mood: dark, rich, gold-lit; colours that make the place recognisable at a glance."""


def _brief_lists():
    i = _ids()
    return {"ITEMS": " ".join(sorted(i["items"])), "PIECES": " ".join(sorted(i["pieces"])), "HATS": " ".join(sorted(i["hats"])), "PALETTE": " ".join(PALETTE)}


def _fill(sys_, **kv):
    for k, v in kv.items():
        sys_ = sys_.replace(k, v)
    return sys_


MINT_MODEL = None         # the lab's own brain choice (Settings → brain) designs and judges


def _design_brain(prompt, system, ask):
    """The designer: the writer brain (motion_wizard._ask_json — the owner's cloud brain first, then the local engine)."""
    from motion_wizard import _ask_json
    return _ask_json(prompt, system, ask)


REVIEW_ROUNDS = 3        # design → render → art-director review → redesign with the notes; the best try is kept
NAMES = {"acts": "movement", "items": "object", "hats": "headwear", "pieces": "set piece", "species": "animal", "props": "scenery", "worlds": "world"}


def _deps(kind, spec):
    """The minted things a sheet needs beside the asset itself (an act's held object / piece / hat, a world's scenery + animals)."""
    out = {kind: {spec["id"]: spec}}
    if kind == "acts":
        for k, ids in (("items", (spec.get("hold") or []) + [spec.get("two")]), ("pieces", [spec.get("piece")]), ("hats", [spec.get("hat")])):
            for x in ids:
                if x and x in library(k):
                    out.setdefault(k, {})[x] = library(k)[x]
    if kind == "worlds":
        o = spec.get("o") or {}
        for r in o.get("fill") or []:
            if r.startswith("props:"):
                for x in r[6:].split(","):
                    if x in library("props"):
                        out.setdefault("props", {})[x] = library("props")[x]
        for a in (o.get("walk") or {}).get("animals") or []:
            if a in library("species"):
                out.setdefault("species", {})[a] = library("species")[a]
        if (spec.get("hero") or {}).get("hat") in library("hats"):
            out.setdefault("hats", {})[spec["hero"]["hat"]] = library("hats")[spec["hero"]["hat"]]
    return out


def look_check(kind, spec, need, log=lambda m, l="info": None):
    """Render the asset's contact sheet and have the art director judge it → (review dict, sheet path). Never raises."""
    import mint_preview as V
    world = need.get("world") or "city"
    look = dict((spec if kind == "worlds" else library("worlds").get(world) or {}).get("hero") or {}, **(need.get("look") or {}))      # a world is judged wearing its OWN hero look
    try:
        deps = _deps(kind, spec)
        if kind != "worlds" and world in library("worlds"):                # show it in its minted world (+ that world's own scenery)
            for k, v in _deps("worlds", library("worlds")[world]).items():
                deps.setdefault(k, {}).update(v)
        job = V.sheet_job(kind, spec, deps, look=look, world=world if kind != "worlds" else spec["id"])
        got = V.render({"%s_%s" % (kind, spec["id"]): job})
        sheet = next(iter(got.values()))
        if not str(sheet).endswith(".png"):
            return {"ok": False, "score": 0, "problems": ["the engine could not draw it: %s" % str(sheet)[:200]], "fix": "make every shape valid"}, None
    except Exception as e:
        log("mint: preview failed for %s (%s)" % (spec["id"], str(e)[:80]), "warn")      # never ship what nobody could look at
        return {"ok": False, "score": 0, "problems": ["the preview could not be drawn: %s" % str(e)[:200]], "fix": "use only valid shapes and fields"}, None
    spr = bool(spec.get("sprite"))          # an image sprite: judge the PICTURE (its shape list is only the fallback, never shown)
    shown = {k: v for k, v in spec.items() if k not in ("for", "source", "created", "review", "sprite_review") + (("shapes", "parts", "back", "front") if spr else ())}
    prompt = "Asset kind: %s\nid: %s\nIt must show: %s\nThe film's line(s): %s\nWorld: %s\nThe asset spec (JSON): %s%s" % (
        NAMES[kind], spec["id"], need.get("desc") or "", " / ".join(need.get("lines_text") or [])[:500], world, json.dumps(shown)[:6000],
        "\nTHIS ASSET IS AN IMAGE SPRITE (a generated cut-out picture drawn whole, gently bobbing/swaying; no moving parts). Judge only the picture "
        "as it appears on the sheet: does it read instantly, scale vs the person, style fit, clean cut-out edges, grounded at its base. Your fix = what to change "
        "in the picture (subject, pose, colours, view) in plain words." if spr else "")
    try:
        rv = V.vision_ask(prompt, sheet, V.REVIEW_SYS, model=MINT_MODEL)
        rv["score"] = float(rv.get("score") or 0)
        return rv, sheet
    except Exception as e:
        log("mint: visual review unavailable (%s)" % str(e)[:80], "warn")
        return None, sheet


def design(kind, need, ask, log=lambda m, l="info": None, review=True):
    """Design one missing thing ({id, desc, ...}), LOOK at it (mint_preview), redesign until the art director passes it, save the best
    to the library and return its spec (None on failure)."""
    from motion_wizard import _ask_json
    want = _id(need.get("id") or need.get("name") or need.get("desc"))
    if not _ID.match(want or ""):
        want = ("m_" + hashlib.md5(str(need).encode()).hexdigest()[:8])
    i, L = _ids(), _brief_lists()
    taken = {"acts": i["acts"], "items": i["items"], "hats": i["hats"], "pieces": i["pieces"], "species": i["species"], "props": i["props"],
             "worlds": i["worlds_builtin"] | set(library("worlds"))}[kind]
    if want in taken and not need.get("redo") and not (library(kind).get(want) or {}).get("unreviewed"):          # already in the library (a minted one from an earlier film, or a built-in)
        return library(kind).get(want) or {"id": want, "builtin": True}
    prompt = "Design: %s\nid: %s\nWhat it must show: %s\nThe film's line(s): %s\nWorld: %s" % (need.get("name") or want, want, need.get("desc") or "", " / ".join(need.get("lines_text") or [])[:600], need.get("world") or "")
    if kind == "acts" and need.get("item"):
        prompt += "\nIt holds the object: %s (use it in hold or two)" % need["item"]
    if kind == "acts" and need.get("piece"):
        prompt += "\nIt works at the set piece: %s (set \"piece\" to it; the piece stands in front of them at x 100..380)" % need["piece"]
    B = _builtin()
    LK = B.get("looks") or {}
    sys_ = {"acts": _fill(ACT_SYS, LEGS="|".join(LEGS), **L), "items": _fill(ITEM_SYS, **L), "hats": _fill(HAT_SYS, **L), "pieces": _fill(PIECE_SYS, **L), "props": _fill(PROP_SYS, **L),
            "species": SPECIES_SYS.replace("BASES", " ".join(sorted(i["species_builtin"]))).replace("PALETTE", L["PALETTE"]),
            "worlds": _fill(WORLD_SYS, BASES="; ".join("%s (%s)" % (k, v.get("about", "")[:70]) for k, v in (B.get("worlds") or {}).items()), RECIPES=" ".join(RECIPES),
                            PROPS=" ".join(sorted(i["props"])), SPECIES=" ".join(sorted(i["species"])), FLOORS=" ".join(sorted(i["floors"])), AMBIENTS=" ".join(sorted(i["ambients"])),
                            OUTFITS="|".join(LK.get("outfit") or []), COLORS="|".join(LK.get("color") or []), HATS="|".join(sorted(i["hats"])))}[kind]
    best, notes = None, ""
    for rnd in range(REVIEW_ROUNDS if review else 1):
        try:
            raw = _design_brain(prompt + notes, sys_, ask)
            raw["id"] = want
            spec = (sanitize_act(raw, i) if kind == "acts" else sanitize_species(raw, i["species_builtin"]) if kind == "species" else
                    sanitize_world(raw, i) if kind == "worlds" else sanitize_shapes_kind(raw, kind))
        except Exception as e:
            log("mint: couldn't design %s %s (%s)" % (NAMES[kind], want, str(e)[:80]), "warn")
            continue
        if not review:
            best = (spec, None)
            break
        rv, sheet = look_check(kind, spec, need, log)
        if rv is None:                                   # no reviewer available: keep this design, flagged so a later run re-judges it
            spec["unreviewed"] = True
            best = best or (spec, None)
            break
        spec["review"] = {"score": rv["score"], "round": rnd + 1, "problems": (rv.get("problems") or [])[:6]}
        if not best or rv["score"] > (best[1] or {}).get("score", -1):
            best = (spec, rv)
        log("mint: %s %s · look %d/10%s" % (NAMES[kind], want, rv["score"], "" if rv.get("ok") else " · " + "; ".join(rv.get("problems") or [])[:120]), "info")
        if rv.get("ok") and rv["score"] >= 7:
            break
        notes = ("\n\nYOUR PREVIOUS DESIGN (JSON):\n%s\n\nTHE ART DIRECTOR LOOKED AT IT RENDERED AND SAYS (score %d/10):\n- %s\nFIX: %s\nRedesign it fixing every point."
                 % (json.dumps({k: v for k, v in spec.items() if k not in ("review", "for")})[:7000], rv["score"], "\n- ".join(rv.get("problems") or []), rv.get("fix") or ""))
    if not best:
        return None
    spec = best[0]
    spec["for"] = str(need.get("desc") or "")[:160]
    log("mint: new %s · %s%s" % (NAMES[kind], want, " (look %d/10)" % spec["review"]["score"] if spec.get("review") else ""), "done")
    spec = _save(kind, spec)
    return spritify(kind, spec, need, log) if review else spec


# ── IMAGE SPRITES (Nov 2 2026, user-approved: LLM shape lists plateau ~5/10) ──
SPRITE_KINDS = ("items", "props", "species")
SPRITES = True           # False → shape lists only (the shapes are always kept as the fallback when generation is unavailable)


def _sprite_gen(sid, kind, subject, notes="", seed=None):
    """mg_assets/mint_sprite.py in the optional art venv (Qwen-Image 2.1 + BiRefNet) → {src, pw, ph} or None."""
    from motion_wizard import ART_PY, ENGINE
    if not os.path.isfile(ART_PY):
        return None
    cmd = [ART_PY, "-I", os.path.join(ENGINE, "mg_assets", "mint_sprite.py"), "--id", sid, "--kind", kind, "--subject", subject[:400]]
    if notes:
        cmd += ["--notes", notes[:500]]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, cwd=os.path.join(ENGINE, "mg_assets"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        line = [x for x in (r.stdout or "").splitlines() if x.startswith("{")]
        return json.loads(line[-1]) if line else None
    except Exception:
        return None


def _sprite_fit(kind, spec, g):
    """Size the picture in rig units from the shape design's own size, + its anchor (item: hand grip, prop/animal: ground point)."""
    asp = g["ph"] / max(1, g["pw"])
    if kind == "items":                         # hand-held: a fixed hand scale (a shape design's own extent is often oversized)
        big = 110
        if asp > 1.8:                           # poles / staffs / tall tools: at least about person height, gripped in the lower part
            big = max(big, 380)
        w, h = (big / asp, big) if asp >= 1 else (big, big * asp)
        return {"w": round(w, 1), "h": round(h, 1), "ax": .5, "ay": .74 if asp > 1.8 else .5}
    if kind == "props":
        w = 100 * max(float(spec.get("w") or 1), float(spec.get("d") or 1)) * 1.05
        h = min(w * asp, 100 * float(spec.get("h") or 1) * 1.6)
        return {"w": round(h / asp, 1), "h": round(h, 1), "ax": .5, "ay": .97, "sway": 1 if re.search(r"kelp|seaweed|tree|palm|grass|flag|plant|coral|anemone", spec["id"] + " " + str(spec.get("tags"))) else 0}
    w = float(spec.get("len") or 160) * 1.3    # the picture includes the tail tip / fins beyond the body length
    return {"w": round(w, 1), "h": round(w * asp, 1), "ax": .5, "ay": .97}


def spritify(kind, spec, need=None, log=lambda m, l="info": None, rounds=REVIEW_ROUNDS):
    """Give a designed item / prop / animal an image sprite, judged by the same art director (≥7 passes, else regenerate with its notes).
    The shape list stays in the spec as the fallback. Returns the spec (saved when a sprite was attached)."""
    if kind not in SPRITE_KINDS or not SPRITES:
        return spec
    need = need or {"id": spec["id"], "desc": spec.get("for") or spec.get("desc") or spec.get("name") or spec["id"]}
    subject = need.get("sprite_subject") or "%s: %s" % (spec.get("name") or spec["id"].replace("_", " "), spec.get("desc") or need.get("desc") or "")
    best, notes = None, ""
    for rnd in range(rounds):
        g = _sprite_gen(spec["id"] + ("" if rnd == 0 else "_r%d" % rnd), kind, subject, notes, seed=None if rnd == 0 else 77 * rnd + len(spec["id"]))
        if not g:
            log("mint: sprite generation unavailable for %s — keeping the shape drawing" % spec["id"], "warn")
            break
        trial = dict(spec, sprite=dict(_sprite_fit(kind, spec, g), src=g["src"]))
        rv, _ = look_check(kind, trial, need, log)
        sc = (rv or {}).get("score", 0)
        log("mint: %s %s sprite · look %d/10" % (NAMES[kind], spec["id"], sc), "info")
        if not best or sc > best[1]:
            best = (trial, sc, rv)
        if rv is None or (rv.get("ok") and sc >= 7) or sc >= 7:
            break
        notes = "Avoid: " + "; ".join((rv.get("problems") or [])[:4]) + ". " + str(rv.get("fix") or "")[:200]
    if not best:
        return spec
    trial, sc, rv = best
    final = os.path.join(_mg(), "library", "mint", "sprites", spec["id"] + ".png")
    src = os.path.join(_mg(), trial["sprite"]["src"].replace("mg/", "", 1).replace("/", os.sep))
    if os.path.abspath(src) != os.path.abspath(final):
        os.replace(src, final)
        trial["sprite"]["src"] = "mg/library/mint/sprites/%s.png" % spec["id"]
    for f in glob.glob(os.path.join(_mg(), "library", "mint", "sprites", spec["id"] + "_r*.png")):
        os.remove(f)
    trial["sprite_review"] = {"score": sc, "problems": ((rv or {}).get("problems") or [])[:6]}
    return _save(kind, trial)


def design_world(brief, ask, log=lambda m, l="info": None):
    """A new world for a premise no built-in or minted world fits; its scenery props are designed first when it asks for them."""
    from motion_wizard import _ask_json
    j = _ask_json("Premise: %s\nList up to 3 scenery objects this world needs that are NOT in: %s\nReply JSON {\"id\": \"<world id>\", \"name\": \"\", \"props\": [{\"id\", \"desc\"}]}"
                  % (brief, " ".join(sorted(_ids()["props"]))), "You plan a new world for a tiny isometric animated film. Be concrete.", ask)
    for pr in (j.get("props") or [])[:3]:
        if isinstance(pr, dict):
            design("props", pr, ask, log)
    w = design("worlds", {"id": j.get("id") or "world", "name": j.get("name") or "", "desc": brief[:300]}, ask, log)
    sync_worlds()
    return w["id"] if w and not w.get("builtin") else None


# ── the audit: does each line's animation show what the narrator says? ──
AUDIT_SYS = """You are the continuity supervisor of a Diorama film (narrated animation, tiny characters in a tiny world). For each LINE you get
what the animation currently shows. Your job: make the PICTURE DO WHAT THE NARRATOR SAYS.
LIBRARY (use these first):
  movements: ACTS
  held objects: ITEMS · set pieces: PIECES · hats: HATS
  animals: SPECIES
  scenery: PROPS
Rules:
- Only lines that describe something VISIBLE (a body action, an object handled, an animal, a creature, a costume) matter. Ideas, numbers, feelings
  with no action → leave them alone. Never follow similes ("like a rocket").
- If the current movement does not show it but a LIBRARY movement does → "fix" with that library id. An animal the line names that is
  in the LIBRARY but not shown → "fix" with "animal": "<species>" (and "anim": idle|walk|run|sit|sleep|eat|speak|swim|fly|follow).
- If NOTHING in the library shows it → "need" a new one: kind act (a body movement, may hold a NEW object: give "item"), item (a held object),
  hat (headwear / costume piece / anything WORN on the head or face: astronaut helmet, wizard hat, diving mask, goggles - never an item), piece (a big object beside the character: anvil, telescope, piano), animal
  (a creature / species not in the list: dinosaur kinds, robots dogs, aliens), prop (scenery in the world: volcano, spaceship, pyramid).
  Give a snake_case id that names it plainly (plant_flag, telescope, robot_dog) and a concrete desc of what must be SEEN.
- who = "hero" or the cast id who does it. One need can serve several lines (list them all). Re-use a need id across lines.
- Be economical: at most MAXN needs for this batch; prefer one versatile movement over three near-duplicates.
Reply JSON only: {"fix": [{"i": <line no>, "who": "hero|<cast id>", "act": "<library movement>"} or {"i": <line no>, "animal": "<species>", "anim": ""}],
 "need": [{"kind": "act|item|hat|piece|animal|prop", "id": "", "desc": "", "lines": [<line nos>], "who": "hero|<cast id>", "item": "<new or library object it holds, optional>"}]}"""


def _sig(b):
    return hashlib.md5(("%s|%s" % (b.get("line") or "", b.get("place") or "")).encode("utf-8")).hexdigest()[:10]


def _shows(b, cast_ids):
    s = "hero: %s" % (b.get("pose") or "stand")
    acts = b.get("acts") or {}
    others = ["%s: %s" % (c, acts.get(c, "stand")) for c in (b.get("with") or []) if c in cast_ids]
    if others:
        s += " · " + ", ".join(others)
    if b.get("animals"):
        s += " · animals: " + ", ".join("%s %s" % (a.get("kind"), a.get("act") or "") for a in b["animals"])
    return s


def audit(p, ask, log=lambda m, l="info": None, maxn=10, force=False):
    """Check every diorama line (only lines changed since the last audit unless force) and mint what is missing. Returns counts."""
    from motion_wizard import _ask_json
    import motion_library
    V = motion_library.vocab()
    cast = p.get("dio_cast") or []
    cids = {c["id"] for c in cast}
    beats = [b for b in p.get("beats") or [] if b.get("kind") == "diorama" and b.get("line")]
    todo = [b for b in beats if force or (b.get("mint") or {}).get("sig") != _sig(b)]
    if not todo:
        return {"checked": 0, "fixed": 0, "minted": 0}
    actlist = "; ".join("%s (%s)" % (k, (e.get("desc") or "")[:34]) for k, e in (V.get("acts") or {}).items())
    sys_ = _fill(AUDIT_SYS, ACTS=actlist, ITEMS=" ".join(V.get("items") or []), PIECES=" ".join(V.get("pieces") or []), HATS=" ".join(V.get("hats") or []),
                 SPECIES=" ".join((V.get("species") or {}).keys()), PROPS=" ".join(V.get("props") or []), MAXN=str(maxn))
    idx = {id(b): beats.index(b) for b in todo}
    fixed = minted = 0
    world = p.get("dio_world") or "city"
    cast_txt = "; ".join("%s = %s (%s)" % (c["id"], c.get("name"), c.get("role") or (c.get("look") or {}).get("species") or "") for c in cast) or "(only the hero)"
    for k in range(0, len(todo), 30):
        chunk = todo[k:k + 30]
        lines = "\n".join("%d | %s | shows -> %s" % (idx[id(b)], b["line"], _shows(b, cids)) for b in chunk)
        prompt = "Film: %s\nWorld: %s\nCast: %s\nLINES (no | narration | what the animation shows now):\n%s" % (p.get("title") or p.get("brief") or "", world, cast_txt, lines)
        try:
            j = _ask_json(prompt, sys_, ask)
        except Exception as e:
            log("mint: the audit failed (%s)" % str(e)[:80], "warn")
            continue
        acts_now = set((motion_library.vocab().get("acts") or {}))
        for fx in j.get("fix") or []:
            try:
                b = beats[int(fx.get("i"))]
            except Exception:
                continue
            if fx.get("act") in acts_now and _assign(b, fx.get("who") or "hero", "act", fx["act"], cids):
                fixed += 1
            sp = fx.get("animal")
            if sp in (motion_library.vocab().get("species") or {}) and sp not in [a.get("kind") for a in b.get("animals") or []]:
                b.setdefault("mint", {}).setdefault("pets", {})[sp] = fx.get("anim") if fx.get("anim") in ANIMAL_ACTS else "follow"
                _apply(b)
                fixed += 1
        for nd in (j.get("need") or [])[:maxn]:
            if not isinstance(nd, dict):
                continue
            kind = {"act": "acts", "item": "items", "hat": "hats", "piece": "pieces", "animal": "species", "prop": "props"}.get(nd.get("kind"))
            ls = [beats[int(x)] for x in nd.get("lines") or [] if str(x).lstrip("-").isdigit() and 0 <= int(x) < len(beats)]
            if not kind or not ls:
                continue
            nd.update(world=world, lines_text=[b["line"] for b in ls[:3]])
            item = nd.get("item")
            if kind == "acts" and item and _id(item) not in _ids()["items"]:
                design("items", {"id": item, "desc": "the object held while: " + (nd.get("desc") or "")}, ask, log)
                nd["item"] = _id(item)
            spec = design(kind, nd, ask, log)
            if not spec:
                continue
            minted += 0 if spec.get("builtin") else 1
            for b in ls:
                if kind == "acts":
                    _assign(b, nd.get("who") or "hero", "act", spec["id"], cids)
                elif kind == "items":          # an object on its own: the hero holds it out
                    hold = spec["id"] + "_hold"
                    if hold not in _ids()["acts"]:
                        _save("acts", {"id": hold, "kind": "act", "cat": "minted", "desc": "holds up the %s" % spec["id"].replace("_", " "), "loop": 2.4, "pingpong": True, "two": None,
                                       "hold": [None, spec["id"]], "keys": [{"u": 0, "far": [-58, -188], "near": [70, -262], "look": [1.5, 1]}, {"u": 1, "far": [-58, -192], "near": [84, -300], "look": [2, 0]}]})
                    _assign(b, nd.get("who") or "hero", "act", hold, cids)
                elif kind == "hats":           # a costume is worn for the whole film (the hero's / that cast member's look)
                    who = nd.get("who") or "hero"
                    c = next((c for c in cast if c["id"] == who), None)
                    (c.setdefault("look", {}) if c else p.setdefault("dio_hero", {}))["hat"] = spec["id"]
                elif kind == "pieces":         # a set piece is used through a movement at it
                    use = design("acts", {"id": "use_" + spec["id"], "desc": nd.get("desc") or "", "piece": spec["id"], "lines_text": nd["lines_text"], "world": world}, ask, log)
                    if use:
                        _assign(b, nd.get("who") or "hero", "act", use["id"], cids)
                elif kind == "species":
                    _assign(b, "", "animal", spec["id"], cids)
                elif kind == "props":
                    _assign(b, "", "prop", spec["id"], cids)
    for b in todo:
        b.setdefault("mint", {})["sig"] = _sig(b)
    p["mint_used"] = sorted(used(p))
    return {"checked": len(todo), "fixed": fixed, "minted": minted}


def _assign(b, who, what, val, cids):
    """Record a mint choice on the line (b["mint"]) and apply it now."""
    F = b.setdefault("mint", {})
    if what == "act":
        if who in ("hero", "", None) or who not in cids:
            F["hero"] = val
        else:
            F.setdefault("acts", {})[who] = val
    elif what == "animal":
        F["animals"] = sorted(set(F.get("animals") or []) | {val})
    elif what == "prop":
        F["props"] = sorted(set(F.get("props") or []) | {val})
    _apply(b)
    return True


def _apply(b):
    F = b.get("mint") or {}
    if F.get("sig") and F["sig"] != _sig(b):          # the line was edited since: its mint choices no longer apply (the next audit redoes it)
        return
    if F.get("hero"):
        b["pose"] = F["hero"]
        b.pop("auto_dir", None) if b.get("auto_dir") == "pose" else None
    if F.get("acts"):
        b["acts"] = dict(b.get("acts") or {}, **F["acts"])
        for cid in F["acts"]:
            if cid not in (b.get("with") or []) and cid not in [r.get("id") for r in b.get("remote") or []]:
                b["with"] = (b.get("with") or []) + [cid]
    pets = dict({a: "follow" for a in F.get("animals") or []}, **(F.get("pets") or {}))
    if pets:
        have = [a.get("kind") for a in b.get("animals") or []]
        b["animals"] = ((b.get("animals") or []) + [{"kind": a, "act": act} for a, act in pets.items() if a not in have])[:3]


def reapply(p):
    """Put the mint choices back after a narration pass (direct_all re-derives poses every build)."""
    for b in p.get("beats") or []:
        if b.get("mint"):
            _apply(b)


def used(p):
    out = set()
    for b in p.get("beats") or []:
        F = b.get("mint") or {}
        if F.get("sig") and F["sig"] != _sig(b):
            continue
        out |= {"props:" + a for a in F.get("props") or [] if a in library("props")}
        for a in (b.get("acts") or {}).values():
            if a in library("acts"):
                out.add("acts:" + a)
        if b.get("pose") in library("acts"):
            out.add("acts:" + b["pose"])
        for an in b.get("animals") or []:
            if an.get("kind") in library("species"):
                out.add("species:" + an["kind"])
    if (p.get("dio_hero") or {}).get("hat") in library("hats"):
        out.add("hats:" + p["dio_hero"]["hat"])
    if p.get("dio_world") in library("worlds"):
        out.add("worlds:" + p["dio_world"])
    for c in p.get("dio_cast") or []:
        lk = c.get("look") or {}
        if lk.get("species") in library("species"):
            out.add("species:" + lk["species"])
        if lk.get("hat") in library("hats"):
            out.add("hats:" + lk["hat"])
    return out


def scenery(p):
    """Minted scenery props the narration mentions: the engine puts them on some of the world's empty lots."""
    return sorted(u.split(":", 1)[1] for u in used(p) if u.startswith("props:"))


def bundle(p):
    """{kind: {id: spec}} for the mg-diorama prop `mint`: everything the film uses + what those depend on."""
    out = {k: {} for k in KINDS}
    todo = list(used(p))
    while todo:
        kind, i = todo.pop().split(":", 1)
        spec = library(kind).get(i)
        if not spec or i in out[kind]:
            continue
        out[kind][i] = spec
        if kind == "acts":
            for it in (spec.get("hold") or []) + [spec.get("two")]:
                if it and it in library("items"):
                    todo.append("items:" + it)
            if spec.get("piece") in library("pieces"):
                todo.append("pieces:" + spec["piece"])
            if spec.get("hat") in library("hats"):
                todo.append("hats:" + spec["hat"])
        if kind == "worlds":
            o = spec.get("o") or {}
            for r in o.get("fill") or []:
                if r.startswith("props:"):
                    todo += ["props:" + x for x in r[6:].split(",")]
            for a in (o.get("walk") or {}).get("animals") or []:
                todo.append("species:" + a)
    return {k: v for k, v in out.items() if v}


def catalog():
    """Minted entries for the shared library page: {kind: [{id, name, desc, created, for}]}."""
    return {k: [{"id": i, "name": s.get("name") or i, "desc": s.get("desc") or s.get("about") or "", "created": s.get("created"), "for": s.get("for") or ""}
                for i, s in library(k).items()] for k in KINDS}
