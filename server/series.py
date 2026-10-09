"""SERIES — build an animated (kids') series the way a studio does: one style bible → a cast of characters with
turnaround sheets → a height lineup → locations in the same world → episodes (idea → timestamped shot list →
reference-to-video scenes) → an original song → an episode edit in the timeline editor.

This module never renders by itself. /api/series/<id>/plan returns a ready request for /api/generate (prompt + the
right reference pictures + one-off engine overrides), so the queue, permissions, one-request-at-a-time rule and the
GPU slot all stay where they are. When that job finishes, /api/series/<id>/attach files its output back into the
series (copied into the person's refs, so it can be reused as a reference on every later shot).

Data: data/series/<user>/<id>.json. Identical in the MirOS copy (miros_mlab) — copy, never import across.
"""
import json
import os
import re
import shutil
import threading
import time
import uuid

try:
    from . import core, prompts, series_presets as presets
except ImportError:
    import core
    import prompts
    import series_presets as presets

SER = os.path.join(core.DATA, "series")
_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
MAX_CAST, MAX_LOCS, MAX_EPS, MAX_OBJS = 12, 16, 60, 24
MAX_PROPS = 4                                          # objects sent as references with one shot
H3_MAX_IMAGES = 9

# ── fixed prompt pieces ─────────────────────────────────────────────────────────────────────────────────────────────
STYLE_SYS = """You are an animation art director for pre-school children's television.
You are shown frames from children's shows the user admires. Work out WHY this visual style works for young children
(shape language, proportions, palette, lighting, texture, line, readability, expressions, background simplicity).
Then write ONE reusable STYLE PROMPT (120-220 words) that an image model can append to any character or location
prompt to reproduce this look consistently. Describe the look only - never name any existing show, studio, brand,
character or artist. Return JSON: {"analysis": "<3-6 short bullet lines>", "style_prompt": "<the style prompt>"}"""

SHEET_TPL = ("Character turnaround reference sheet of {who}: {desc}. One single character only, shown full body in a "
             "clean row: front view, three-quarter view, side profile, back view, plus a small row of facial "
             "expressions (happy, surprised, sad, laughing). Same outfit, same proportions and same colours in every "
             "view. Plain light background, even lighting, no text labels, no props. {style}")
HERO_TPL = "Full-body character design of {who}: {desc}. Friendly, appealing, standing in a neutral pose on a plain background. {style}"
CHAR_TPL = ("In exactly the same art style as the reference picture, design a new character: {who} - {desc}. "
            "Full body, standing, neutral pose, plain background, no clothes or accessories unless described. {style}")
LINEUP_TPL = ("Cast lineup: all of these characters standing side by side in one row, at their correct relative heights, "
              "one of each, facing camera, plain light background, no text. Characters from left to right: {names}. {style}")
# Objects (props, vehicles, animals, plants …): one design, then a turnaround and a detail sheet drawn FROM it
OBJ_TPL = ("Prop design of {who}: {desc}. One single object shown whole and centred in a clear three-quarter view, "
           "standing on a plain light background with a soft ground shadow, even lighting. No people or characters, "
           "no other objects, no text or logos. {style}")
OBJ_STYLED_TPL = ("Copy ONLY the art style, colours and rendering of the reference picture - do NOT draw anything that is in "
                  "it. ") + OBJ_TPL
OBJ_SHEET_TPL = ("Object turnaround reference sheet of {who}: {desc}. The SAME object as in the picture, shown on one clean "
                 "sheet in a row of views: front view, three-quarter view, side view, back view and top view. Same shape, "
                 "proportions, colours, materials and details in every view. Plain light background, even lighting, no "
                 "people or characters, no text labels. {style}")
OBJ_DETAIL_TPL = ("Detail sheet of {who}: {desc}. A 2 by 2 grid of the SAME object as in the picture: a close-up of its "
                  "most important detail, a close-up of its material and texture, the object {move}, and the object at "
                  "night with its lights or glow (or in soft moonlight). Identical design, colours and proportions in every "
                  "panel. Plain backgrounds, no people or characters, no text. {style}")
LOC_TPL = ("Empty environment design (no characters): {who} - {desc}. Wide establishing view, readable layout with "
           "clear floor space for characters to stand and play. {style}")

# Architectural views of a location, all redrawn from its picture (Qwen edit) so the layout, furniture and colours match.
# Order = the index stored with each render (attach i); the World tab shows them in this order.
LOC_SHEET_TPL = ("Location turnaround reference sheet of {who}: {desc}. The SAME place as in the picture, shown on one clean "
                 "sheet as a 3D cutaway miniature (roof and ceiling removed, walls cut at waist height) in a clean row of four "
                 "views: front view, right side view, back view, left side view, plus a small top-down floor plan in the "
                 "corner. Same layout, same furniture in the same places, same colours and materials in every view. Plain "
                 "light-grey background, even lighting, no characters or people, no text labels. {style}")
LOC_VIEWS = [
    ("cutaway", "3D cutaway", "16:9",
     "Turn the place in the picture into a 3D architectural cutaway model, seen from high above at a 45-degree isometric "
     "angle from the front-left corner: the roof and ceiling removed and the walls cut at waist height, so every room, "
     "doorway and piece of furniture is visible at once, like a detailed dollhouse miniature of the whole layout. If the "
     "place is outdoors, show the whole area as a miniature diorama block. Soft even studio lighting, clean light-grey "
     "background around the model."),
    ("cutaway2", "Opposite corner", "16:9",
     "Picture 1 is a 3D cutaway model of a place, picture 2 shows how the place really looks. Show the SAME cutaway model "
     "turned around 180 degrees, seen from high above at a 45-degree isometric angle from the opposite (back-right) corner: "
     "roof and ceiling removed, walls cut at waist height, so the walls and furniture that were at the back of picture 1 "
     "are now nearest the viewer. Every piece of furniture keeps its place in the room. Same miniature model look, soft "
     "even studio lighting and clean light-grey background as picture 1, the colours and materials of picture 2."),
    ("top", "Top view", "1:1",
     "Picture 1 is a 3D cutaway model of a place, picture 2 shows how the place really looks. Draw the same place from "
     "directly overhead, the camera pointing straight down at 90 degrees with the roof and ceiling removed: a clear top-down "
     "floor-plan view of the whole layout, every wall, doorway and piece of furniture in exactly the position it has in "
     "picture 1, in the colours, materials and art style of picture 2."),
]
LOC_VIEW_RULES = (" Keep the exact same layout, furniture, objects, colours, materials, lighting and art style as the picture; "
                  "do not add or remove anything. No characters or people, no text, labels or measurements. {style}")

SCENE_SYS = """You write shot lists for MiniMax H3 reference-to-video, a model that animates characters from reference pictures.
Write ONE continuous scene of {secs} seconds for a pre-school animated series. Rules:
- Break it into timestamped shots: "[0-3s] <framing>, <camera move>. <action>. <Name>: \\"<line>\\"" - 2 to 5 shots.
- Name characters exactly as given; describe them by name only (the reference pictures carry their look).
- Short, simple, warm dialogue a 3-year-old understands; one lesson; end on a happy, celebratory beat.
- Concrete physical action and expressions, gentle camera moves (slow push-in, static, gentle pan). No cuts to new places.
- Never name existing shows or characters. Output only the shot list, nothing else."""

SONG_SYS = """You write original nursery-rhyme songs for pre-school children. Simple words, lots of repetition, a chorus
a toddler can sing back, an action or lesson in every verse. Return JSON:
{"title": "...", "caption": "<music style caption: genre, tempo ~100 BPM, instruments, bright cheerful children's vocals>",
 "lyrics": "<lyrics with [Verse] [Chorus] tags on their own lines>"}"""

NO_MUSIC = " Audio: character dialogue and natural sound effects only - no background music, no singing."

EXPR_TPL = ("Facial expression sheet of {who}: {desc}. A 3 by 3 grid of head-and-shoulders portraits of the SAME character: "
            "happy, laughing, singing with mouth wide open, singing 'oo' with rounded lips, surprised, sad, pouting, sleepy, "
            "winking. Identical face, colours and proportions in every panel. Plain light background, no text. {style}")
KEY_TPL = ("First frame of one shot from a children's musical video. {legend}. {shot} Every character and object looks "
           "exactly as in its reference picture (same face, colours, outfit, shape, proportions). Clear readable staging, faces visible, "
           "{aspect} framing, no text, no logos. {style}")

MUSICAL_SYS = """You write original songs for children's musical videos and plan their structure.
The song follows these sections in this order: {beats}.
Total length about {secs} seconds at {bpm} BPM. Music style: {genre}. Who sings: {vocal}. Language: {lang}.
Rules:
- Simple words, lots of repetition, a chorus a child can sing back after one listen, one gentle lesson.
- Sections whose kind is "action" or "establish" are instrumental: give them an empty "lines" list.
- Each sung section has 2-6 short lines (about one line per two bars). Repeat the chorus words exactly each time.
- Give every sung section a singer: one cast name, or "all".
- Give every section a one-sentence visual idea: where we are and what the characters do.
- Never name existing shows, songs, brands or characters.
Return JSON only: {{"title": "...", "sections": [{{"tag": "<section name>", "kind": "sing|action|establish", "singer": "<name or all>", "lines": ["..."], "idea": "..."}}]}}"""

CHUNKS_SYS = """You direct a children's musical video shot by shot. Every chunk below is one continuous shot of the given
length; the picture is generated to the real song audio, so mouths follow the vocal automatically.
For each chunk write:
- "shot": one compact paragraph - framing, camera move, what each character does ON THE BEAT. For sung chunks say who
  sings and to whom (camera, each other); for instrumental chunks say they dance or act with mouths closed.
- "link": "continue" when the camera keeps rolling from the previous chunk (same place, same moment) or "cut" for a
  new angle or place. Cut at most section changes and at least every 3 chunks; the first chunk is always "cut".
- "singer": who sings in this chunk ("" if nobody).
The picture must illustrate what the words in that chunk say (literally or playfully), and the shots together must tell
the story of the whole song from first line to last.
Camera grammar for this style: {camera}.
Describe characters by NAME only (their pictures carry the look). Locations available: {locs}.
Never name existing shows or characters. Return JSON only: {{"chunks": [{{"i": 0, "shot": "...", "link": "cut", "singer": "..."}}]}}"""

ANCHOR = 22                                            # frames of the previous clip a "continue" chunk starts on
MAX_CHUNK = 13.0                                       # longest single performance clip (s)


# ── storage ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _dir(uid):
    d = os.path.join(SER, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "owner")))
    os.makedirs(d, exist_ok=True)
    return d


def _path(uid, sid):
    return os.path.join(_dir(uid), sid + ".json") if _ID_RE.match(str(sid or "")) else None


def load(uid, sid):
    p = _path(uid, sid)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(uid, d):
    d["updated"] = time.time()
    p = _path(uid, d["id"])
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, p)
    return d


def new_id():
    return uuid.uuid4().hex[:12]


def _clean(s, n=2000):
    return str(s or "").strip()[:n]


def _item(src, keep, fields):
    """One cast / location / episode entry from the client, keeping server-owned fields from the stored copy."""
    it = {"id": src.get("id") if _ID_RE.match(str(src.get("id") or "")) else new_id()}
    for k, n in fields.items():
        it[k] = _clean(src.get(k), n)
    for k in keep:
        if k in src:
            it[k] = src[k]
    return it


def merge(old, body):
    """Validated update from the client. Pictures / renders are only set by attach(), never by the client."""
    d = dict(old or {"id": new_id(), "created": time.time(), "characters": [], "locations": [], "episodes": [], "objects": []})
    for k, n in (("name", 120), ("style_prompt", 4000), ("audience", 200)):
        if k in body:
            d[k] = _clean(body[k], n)
    if isinstance(body.get("setup"), dict):
        d["setup"] = _setup(body["setup"])
    owned = {"characters": ("hero", "sheet", "expr"), "locations": ("image", "sheet", "views"), "objects": ("hero", "sheet", "detail"),
             "episodes": ("scenes", "song", "project", "shots", "song_text", "sections", "chunks", "final", "song_secs")}
    shapes = {"characters": {"name": 60, "desc": 1200, "voice": 40},
              "locations": {"name": 60, "desc": 1200},
              "objects": {"name": 60, "desc": 1200},
              "episodes": {"title": 120, "idea": 3000, "location": 40, "lesson": 300}}
    caps = {"characters": MAX_CAST, "locations": MAX_LOCS, "episodes": MAX_EPS, "objects": MAX_OBJS}
    for key, fields in shapes.items():
        if not isinstance(body.get(key), list):
            continue
        prev = {x.get("id"): x for x in d.get(key) or []}
        out = []
        for src in body[key][:caps[key]]:
            if not isinstance(src, dict):
                continue
            it = _item(src, (), fields)
            for k in owned[key]:                       # server-owned: carried over from the stored entry
                if k in (prev.get(it["id"]) or {}):
                    it[k] = prev[it["id"]][k]
            if key in ("characters", "objects") and isinstance(src.get("traits"), dict):
                it["traits"] = _traits(src["traits"], presets.OBJECT if key == "objects" else presets.CHARACTER)
            elif key in ("characters", "objects") and "traits" in (prev.get(it["id"]) or {}):
                it["traits"] = prev[it["id"]]["traits"]
            if key == "objects":
                it["built"] = presets.compose_obj_desc(it.get("traits")) if it.get("traits") else ""
            if key == "characters":
                it["built"] = presets.compose_desc(it.get("traits")) if it.get("traits") else ""
                it["voice_desc"] = presets.voice_desc(it.get("traits"))
            if key == "episodes":
                _edit_musical(it, src)
                it["cast"] = [str(c) for c in (src.get("cast") or [])][:8]
                it["props"] = [str(o) for o in (src.get("props") or [])][:MAX_PROPS]
                it["seconds"] = max(4, min(15, int(src.get("seconds") or 10)))
                if "shots" in src:                     # the shot list is editable by the person
                    it["shots"] = _clean(src.get("shots"), 4000)
            out.append(it)
        d[key] = out
    return d


def _setup(b):
    """The configuration menu's choices (structure, style, length, aspect, song), validated against the presets."""
    st = b.get("structure") if presets.structure(b.get("structure")) else "musical"
    out = {"structure": st, "style": b.get("style") if presets.style(b.get("style")) else "animated3d",
           "length": max(20, min(180, int(b.get("length") or 120))),
           "aspect": b.get("aspect") if b.get("aspect") in presets.ASPECTS else "16:9",
           "clip": max(6, min(12, int(b.get("clip") or presets.CLIP_SECS))), "song": {},
           "res": b.get("res") if b.get("res") in ("draft", "standard", "high", "max") else "standard",
           "join": b.get("join") if b.get("join") in ("cut", "soft") else "soft"}
    sg = b.get("song") if isinstance(b.get("song"), dict) else {}
    for f in presets.SONG:
        v = sg.get(f["k"])
        if f["type"] == "range":
            lo, hi, df = f["range"]
            out["song"][f["k"]] = max(lo, min(hi, int(v or df)))
        elif v in f["opts"]:
            out["song"][f["k"]] = v
    if st == "custom" and isinstance(b.get("beats"), list):     # [[name, share, kind], …] from the beat builder
        beats = []
        for x in b["beats"][:16]:
            if isinstance(x, (list, tuple)) and len(x) == 3 and x[2] in ("sing", "action", "establish", "dialogue"):
                beats.append([_clean(x[0], 40), max(0.02, min(1.0, float(x[1] or 0.1))), x[2]])
        out["beats"] = beats
    return out


def _traits(t, spec=None):
    """Character- (or object-) builder answers, kept only where they match an offered option."""
    out = {}
    for f in spec or presets.CHARACTER:
        v = t.get(f["k"])
        if v in (None, "", []):
            continue
        if f["type"] == "many":
            vs = [x for x in (v if isinstance(v, list) else []) if x in f["opts"]][:6]
            if vs:
                out[f["k"]] = vs
        elif f["type"] == "range":
            lo, hi, _ = f["range"]
            try:
                out[f["k"]] = max(lo, min(hi, int(v)))
            except (TypeError, ValueError):
                pass
        elif f["type"] == "text":
            out[f["k"]] = _clean(v, 80)
        elif v in f["opts"]:
            out[f["k"]] = v
    return out


def _edit_musical(it, src):
    """The parts of a musical episode the person may edit: lyrics, section lines/ideas, and each chunk's shot + cut."""
    if isinstance(src.get("song_text"), dict):
        st = src["song_text"]
        it["song_text"] = {"title": _clean(st.get("title"), 120), "caption": _clean(st.get("caption"), 600),
                           "lyrics": _clean(st.get("lyrics"), 4000)}
    if isinstance(src.get("chunk_edits"), dict) and isinstance(it.get("chunks"), list):
        for c in it["chunks"]:
            e = src["chunk_edits"].get(str(c.get("i")))
            if isinstance(e, dict):
                if "shot" in e:
                    c["shot"] = _clean(e["shot"], 1500)
                if e.get("link") in ("continue", "cut"):
                    c["link"] = e["link"]
                if "singer" in e:
                    c["singer"] = _clean(e["singer"], 60)


def listing(uid):
    out = []
    for f in os.listdir(_dir(uid)):
        if f.endswith(".json"):
            d = load(uid, f[:-5])
            if d:
                cover = next((c.get("sheet") or c.get("hero") for c in d.get("characters") or [] if c.get("sheet") or c.get("hero")), None)
                out.append({"id": d["id"], "name": d.get("name") or "Untitled series", "updated": d.get("updated"),
                            "cast": len(d.get("characters") or []), "episodes": len(d.get("episodes") or []), "cover": cover})
    out.sort(key=lambda x: -(x.get("updated") or 0))
    return out


# ── planning: the request the client sends to /api/generate ────────────────────────────────────────────────────────
def _find(d, key, iid):
    return next((x for x in d.get(key) or [] if x.get("id") == iid), None)


def _style(d):
    ps = presets.style((d.get("setup") or {}).get("style"))
    return d.get("style_prompt") or (ps and ps["style_prompt"]) or         "Soft rounded 3D children's animation look, bright friendly palette, gentle lighting."


def _desc(c):
    """Builder choices + the person's own words (their words win where they disagree, so they come last)."""
    built = presets.compose_desc(c.get("traits")) if c.get("traits") else ""
    own = (c.get("desc") or "").strip()
    return "; ".join(x for x in (built, own) if x)


def _odesc(o):
    """Object-builder choices + the person's own words (theirs win, so they come last)."""
    built = presets.compose_obj_desc(o.get("traits")) if o.get("traits") else ""
    own = (o.get("desc") or "").strip()
    return "; ".join(x for x in (built, own) if x) or (o.get("name") or "an object")


def _props_of(d, ep):
    """The episode's objects that have a picture to send as a reference."""
    return [o for o in (_find(d, "objects", oid) for oid in (ep or {}).get("props") or []) if o and _ref(o.get("hero") or o.get("sheet"))]


def _aspect(d, default="16:9"):
    return (d.get("setup") or {}).get("aspect") or default


def _ref(r):
    return r if r and os.path.isfile(os.path.join(core.REFS, r)) else None


def plan(d, kind, target=None, extra=None):
    """→ {"model", "prompt", "refs", "override", "attach": {"kind", "target"}} or {"error"}."""
    extra = extra or {}
    st = _style(d)
    if kind in ("hero", "sheet", "character"):
        c = _find(d, "characters", target)
        if not c:
            return {"error": "pick a character"}
        who, desc = c.get("name") or "the character", _desc(c)
        if kind == "hero":
            photo = _ref(extra.get("photo"))
            p = HERO_TPL.format(who=who, desc=desc, style=st)
            if photo:
                ps = presets.style((d.get("setup") or {}).get("style")) or {}
                if ps.get("id") in ("realistic", "cinematic", "shortfilm"):
                    p = ("Full-body photograph of the person in the picture as %s: keep their exact face, likeness, skin tone "
                         "and hair; %s. Natural pose, plain background. %s" % (who, desc, st))
                else:
                    p = ("Turn the person in the picture into a %s character, keeping their face shape, hair, skin tone and "
                         "likeness recognisable. " % (ps.get("name") or "cartoon").lower()) + p
            refs = [photo] if photo else []
            if photo:                                  # any cast member, not just the lead: match the lead's drawn style
                lead = next((_ref(x.get("hero")) for x in d.get("characters") or []
                             if x["id"] != c["id"] and _ref(x.get("hero"))), None)
                if lead:
                    refs.append(lead)
                    p += (" Draw them in exactly the same art style, rendering, proportions and colour treatment as the "
                          "character in picture 2 (only the style — not that character's look).")
            return {"model": "qimg", "prompt": p, "refs": refs,
                    "override": {"mode": "edit" if photo else "auto", "aspect": "3:4"}, "attach": {"kind": "hero", "target": c["id"]}}
        if kind == "character":                        # new character drawn in the art style of the lead's hero
            lead = next((_ref(x.get("hero") or x.get("sheet")) for x in d.get("characters") or []
                         if x["id"] != c["id"] and (x.get("hero") or x.get("sheet"))), None)
            if not lead:
                return {"error": "make the first character's hero picture first — new characters copy its style"}
            return {"model": "qimg", "prompt": CHAR_TPL.format(who=who, desc=desc, style=st), "refs": [lead],
                    "override": {"mode": "edit", "aspect": "3:4"}, "attach": {"kind": "hero", "target": c["id"]}}
        hero = _ref(c.get("hero"))
        if not hero:
            return {"error": "make %s's hero picture first" % who}
        return {"model": "qimg", "prompt": SHEET_TPL.format(who=who, desc=desc, style=st), "refs": [hero],
                "override": {"mode": "edit", "aspect": "16:9"}, "attach": {"kind": "sheet", "target": c["id"]}}
    if kind in ("object", "objsheet", "objdetail"):
        o = _find(d, "objects", target)
        if not o:
            return {"error": "pick an object"}
        who, desc = o.get("name") or "the object", _odesc(o)
        if kind == "object":
            photo = _ref(extra.get("photo"))
            ps = presets.style((d.get("setup") or {}).get("style")) or {}
            if photo:
                if ps.get("id") in ("realistic", "cinematic", "shortfilm"):
                    p = ("Product photograph of the object in the picture as %s: keep its exact shape, details and colours; %s. "
                         "Whole object, centred, plain background, soft studio light, no people. %s" % (who, desc, st))
                else:
                    p = ("Turn the object in the picture into a %s prop, keeping its shape, details and colours recognisable. "
                         % (ps.get("name") or "cartoon").lower()) + OBJ_TPL.format(who=who, desc=desc, style=st)
                refs = [photo]
                sref = next((_ref(c.get("hero")) for c in d.get("characters") or [] if _ref(c.get("hero"))), None) or \
                    next((_ref(x.get("hero")) for x in d.get("objects") or [] if x["id"] != o["id"] and _ref(x.get("hero"))), None)
                if sref:                               # keep every object in the series' drawn style
                    refs.append(sref)
                    p += (" Match the art style, rendering and colour treatment of picture 2 exactly "
                          "(only the style — not what is in it).")
                return {"model": "qimg", "prompt": p, "refs": refs, "override": {"mode": "edit", "aspect": "1:1"},
                        "attach": {"kind": "object", "target": o["id"]}}
            style_ref = next((_ref(c.get("hero")) for c in d.get("characters") or [] if _ref(c.get("hero"))), None) or \
                next((_ref(x.get("hero")) for x in d.get("objects") or [] if x["id"] != o["id"] and _ref(x.get("hero"))), None)
            return {"model": "qimg", "prompt": (OBJ_STYLED_TPL if style_ref else OBJ_TPL).format(who=who, desc=desc, style=st),
                    "refs": [style_ref] if style_ref else [], "override": {"mode": "edit" if style_ref else "auto", "aspect": "1:1"},
                    "attach": {"kind": "object", "target": o["id"]}}
        hero = _ref(o.get("hero"))
        if not hero:
            return {"error": "draw %s first — the sheets are built from it" % who}
        if kind == "objsheet":
            return {"model": "qimg", "prompt": OBJ_SHEET_TPL.format(who=who, desc=desc, style=st), "refs": [hero],
                    "override": {"mode": "edit", "aspect": "16:9"}, "attach": {"kind": "objsheet", "target": o["id"]}}
        mv = str((o.get("traits") or {}).get("o_move") or "")
        return {"model": "qimg", "prompt": OBJ_DETAIL_TPL.format(who=who, desc=desc, style=st,
                                                                 move=(mv if mv and mv != "stays still" else "in use")),
                "refs": [hero], "override": {"mode": "edit", "aspect": "1:1"}, "attach": {"kind": "objdetail", "target": o["id"]}}
    if kind == "lineup":
        cast = [c for c in d.get("characters") or [] if _ref(c.get("sheet") or c.get("hero"))]
        if len(cast) < 2:
            return {"error": "the lineup needs at least two characters with pictures"}
        refs = [_ref(c.get("sheet") or c.get("hero")) for c in cast][:prompts.QWEN_MAX_REFS]
        names = ", ".join("%s (picture %d)" % (c.get("name"), i + 1) for i, c in enumerate(cast[:len(refs)]))
        return {"model": "qimg", "prompt": LINEUP_TPL.format(names=names, style=st), "refs": refs,
                "override": {"mode": "edit", "aspect": "16:9"}, "attach": {"kind": "lineup", "target": None}}
    if kind == "location":
        loc = _find(d, "locations", target)
        if not loc:
            return {"error": "pick a location"}
        style_ref = _ref(d.get("lineup")) or next((_ref(c.get("hero")) for c in d.get("characters") or [] if c.get("hero")), None)
        p = LOC_TPL.format(who=loc.get("name") or "a place", desc=loc.get("desc") or "", style=st)
        if style_ref:
            p = ("Copy ONLY the art style, colours and rendering of the reference picture. The reference shows a character - "
                 "do NOT draw that character or anyone else: this is an EMPTY place with no characters, people or animals. ") + p
        return {"model": "qimg", "prompt": p, "refs": [style_ref] if style_ref else [],
                "override": {"mode": "edit" if style_ref else "auto", "aspect": "16:9"},
                "attach": {"kind": "location", "target": loc["id"]}}
    if kind == "locsheet":
        loc = _find(d, "locations", target)
        if not loc:
            return {"error": "pick a location"}
        base = _ref(loc.get("image"))
        if not base:
            return {"error": "draw %s first — the turnaround is built from it" % (loc.get("name") or "the location")}
        return {"model": "qimg", "prompt": LOC_SHEET_TPL.format(who=loc.get("name") or "the place", desc=loc.get("desc") or "", style=st),
                "refs": [base], "override": {"mode": "edit", "aspect": "16:9"}, "attach": {"kind": "locsheet", "target": loc["id"]}}
    if kind == "locview":
        loc = _find(d, "locations", target)
        if not loc:
            return {"error": "pick a location"}
        base = _ref(loc.get("image"))
        if not base:
            return {"error": "draw %s first — the 3D views are built from it" % (loc.get("name") or "the location")}
        i = extra.get("i")
        if not isinstance(i, int) or not 0 <= i < len(LOC_VIEWS):
            return {"error": "unknown view"}
        key, label, aspect, view = LOC_VIEWS[i]
        cut = _ref((loc.get("views") or {}).get("cutaway")) if i else None
        if i and not cut:                              # no model yet: work from the picture alone
            view = re.sub(r"^Picture 1 is a 3D cutaway model of a place, picture 2 shows how the place really looks\. ", "", view)
            view = view.replace("of the model in picture 1", "of the place in the picture").replace("picture 1", "the picture") \
                       .replace("picture 2", "the picture")
        p = view + LOC_VIEW_RULES.format(style=st) + (" The place: %s - %s." % (loc.get("name") or "", loc.get("desc") or "")).rstrip(" -.") + "."
        return {"model": "qimg", "prompt": p, "refs": [cut, base] if cut else [base], "override": {"mode": "edit", "aspect": aspect},
                "attach": {"kind": "locview", "target": loc["id"], "i": i}}
    if kind == "scene":
        ep = _find(d, "episodes", target)
        if not ep:
            return {"error": "pick an episode"}
        if not (ep.get("shots") or "").strip():
            return {"error": "write the shot list first"}
        cast = [c for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c and _ref(c.get("sheet") or c.get("hero"))]
        loc = _find(d, "locations", ep.get("location"))
        refs, legend = [], []
        for c in cast[:H3_MAX_IMAGES - 1]:
            refs.append(_ref(c.get("sheet") or c.get("hero")))
            legend.append("%s is <Picture %d>" % (c.get("name"), len(refs)))
        for o in _props_of(d, ep)[:max(0, H3_MAX_IMAGES - 1 - len(refs))]:
            refs.append(_ref(o.get("hero") or o.get("sheet")))
            legend.append("the %s is <Picture %d>" % (o.get("name") or "object", len(refs)))
        if loc and _ref(loc.get("image")):
            refs.append(_ref(loc["image"]))
            legend.append("the setting is <Picture %d> (%s)" % (len(refs), loc.get("name")))
        if not refs:
            return {"error": "the episode's cast needs character pictures first"}
        p = ("Animated children's series scene. " + "; ".join(legend) + ". Keep every character and object exactly as in its picture. "
             + _clean(ep["shots"], 3000) + " Style: " + st[:600] + NO_MUSIC)
        return {"model": "h3", "prompt": p, "refs": refs,
                "override": {"mode": "r2v", "aspect": "16:9", "ref_role": "identity", "seconds": ep.get("seconds") or 10,
                             "audio": "custom", "audio_text": "character dialogue and natural sound effects only, no music"},
                "attach": {"kind": "scene", "target": ep["id"]}}
    if kind == "song":
        ep = _find(d, "episodes", target)
        if not ep or not ep.get("song_text"):
            return {"error": "write the song first"}
        s = ep["song_text"]
        secs = int((d.get("setup") or {}).get("length") or 0)
        return {"model": "music3", "prompt": "%s%s\n| lyrics:\n%s" % (
                    s.get("caption") or "children's nursery rhyme, bright, 100 BPM", (" --%ds" % secs) if secs else "",
                    s.get("lyrics") or ""),
                "refs": [], "override": {}, "attach": {"kind": "song", "target": ep["id"]}}
    if kind == "expr":
        c = _find(d, "characters", target)
        if not c or not _ref(c.get("hero")):
            return {"error": "make the hero picture first"}
        return {"model": "qimg", "prompt": EXPR_TPL.format(who=c.get("name") or "the character", desc=_desc(c), style=st),
                "refs": [_ref(c["hero"])], "override": {"mode": "edit", "aspect": "1:1"},
                "attach": {"kind": "expr", "target": c["id"]}}
    if kind in ("keyframe", "chunk"):
        ep = _find(d, "episodes", target)
        ch = _chunk(ep, extra.get("i"))
        if not ch:
            return {"error": "map the song into shots first"}
        aspect = _aspect(d)
        if kind == "keyframe":
            refs, legend = [], []
            props = _props_of(d, ep)[:MAX_PROPS]
            for c in _cast_of(d, ep, ch)[:prompts.QWEN_MAX_REFS - 1 - len(props)]:
                refs.append(_ref(c.get("sheet") or c.get("hero")))
                legend.append("%s is picture %d" % (c.get("name"), len(refs)))
            for o in props:
                refs.append(_ref(o.get("hero") or o.get("sheet")))
                legend.append("the %s is picture %d" % (o.get("name") or "object", len(refs)))
            loc = _find(d, "locations", ep.get("location")) or next((l for l in d.get("locations") or [] if _ref(l.get("image"))), None)
            if loc and _ref(loc.get("image")):
                refs.append(_ref(loc["image"]))
                legend.append("the place is picture %d (%s)" % (len(refs), loc.get("name")))
            if not refs:
                return {"error": "draw the cast first (hero or turnaround pictures)"}
            return {"model": "qimg", "prompt": KEY_TPL.format(legend="; ".join(legend), shot=_clean(ch.get("shot") or ch.get("idea"), 1200),
                                                               aspect=aspect, style=st),
                    "refs": refs, "override": {"mode": "edit", "aspect": aspect},
                    "attach": {"kind": "keyframe", "target": ep["id"], "i": ch["i"]}}
        if not _ref(ch.get("audio")):
            return {"error": "the song chunk isn't cut yet"}
        prev = _chunk(ep, ch["i"] - 1)
        if ch.get("link") == "continue" and prev and _ref(prev.get("clipref")):
            start = _ref(prev["clipref"])
        elif _ref(ch.get("key")):
            start = _ref(ch["key"])
        else:
            return {"error": "shot %d needs its first frame (or the previous shot rendered)" % (ch["i"] + 1)}
        ps = presets.style((d.get("setup") or {}).get("style")) or {}
        who = ch.get("singer") or ""
        line = " / ".join(ch.get("lines") or [])
        p = _clean(ch.get("shot") or ch.get("idea"), 1500)
        if who and line:
            p += ' %s sings: "%s".' % (who, line[:400])
        p += " Style: " + st[:500]
        return {"model": "h3", "prompt": p, "refs": [start, _ref(ch["audio"])],
                "override": {"mode": "sing", "aspect": aspect, "extend_anchor": str(ANCHOR), "look": ps.get("look") or "auto",
                             "res": (d.get("setup") or {}).get("res") or "standard",
                             "camera": "auto", "trim": 0, "extend": 0},
                "attach": {"kind": "chunk", "target": ep["id"], "i": ch["i"]}}
    return {"error": "unknown step"}


# ── writing (the series' prompt writer — cloud brain, local engine fallback) ─────────────────────────────────────
def analyse_style(d, ref_names, extra=""):
    imgs = [prompts._b64(os.path.join(core.REFS, r), 1024) for r in ref_names if _ref(r) and core.kind_of(r) == "image"][:8]
    if not imgs:
        raise ValueError("attach a few frames from shows you like")
    raw = _ask("Analyse these reference frames. " + _clean(extra, 500), STYLE_SYS, images=imgs, want_json=True, role="director", timeout=300)
    j = _json(raw)
    return {"analysis": _clean(j.get("analysis"), 3000), "style_prompt": _clean(j.get("style_prompt") or raw, 4000)}


def write_shots(d, ep):
    cast = [c for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c]
    loc = _find(d, "locations", ep.get("location"))
    objs = [o for o in (_find(d, "objects", oid) for oid in ep.get("props") or []) if o]
    ask = ("Episode idea: %s\nLesson: %s\nCharacters: %s\nSetting: %s%s"
           % (ep.get("idea") or "", ep.get("lesson") or "",
              "; ".join("%s - %s" % (c.get("name"), _desc(c)[:200]) for c in cast) or "the lead",
              (loc.get("name") + " - " + (loc.get("desc") or "")[:200]) if loc else "a cosy playroom",
              ("\nObjects in the scene (name them; their pictures carry the look): " +
               "; ".join("%s - %s" % (o.get("name"), _odesc(o)[:160]) for o in objs)) if objs else ""))
    return _clean(_ask(ask, SCENE_SYS.format(secs=ep.get("seconds") or 10), role="director", timeout=300), 4000)


def write_song(d, ep):
    cast = ", ".join(c.get("name") for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c)
    raw = _ask("Song for an episode of '%s'. Idea: %s. Lesson: %s. Characters: %s."
                   % (d.get("name") or "our series", ep.get("idea") or "", ep.get("lesson") or "", cast or "the lead"),
                   SONG_SYS, want_json=True, role="director", timeout=300)
    j = _json(raw)
    if not j.get("lyrics"):
        raise ValueError("the writer didn't return lyrics — try again")
    return {"title": _clean(j.get("title"), 120), "caption": _clean(j.get("caption"), 600), "lyrics": _clean(j.get("lyrics"), 4000)}


def _ask(prompt, system, images=None, want_json=False, role="director", timeout=300):
    """core.ask in both copies (the MirOS copy's ask has no cloud brain → no want_json / role)."""
    try:
        return core.ask(prompt, system, images=images, want_json=want_json, role=role, timeout=timeout)
    except TypeError:
        return core.ask(prompt + ("\n\nReply with one JSON object only." if want_json else ""), system, timeout=timeout, images=images)


def _json(raw):
    if isinstance(raw, dict):
        return raw
    s = str(raw or "")
    m = re.search(r"\{.*\}", s, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


# ── the musical: song-first episodes cut into performance chunks ─────────────────────────────────────────────────
def _chunk(ep, i):
    try:
        i = int(i)
    except (TypeError, ValueError):
        return None
    return next((c for c in (ep or {}).get("chunks") or [] if c.get("i") == i), None)


def _cast_of(d, ep, ch=None):
    """Characters with pictures for a chunk: its singer first, then the rest of the episode's cast."""
    cast = [c for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c and _ref(c.get("sheet") or c.get("hero"))]
    if not cast:
        cast = [c for c in d.get("characters") or [] if _ref(c.get("sheet") or c.get("hero"))]
    who = ((ch or {}).get("singer") or "").lower()
    cast.sort(key=lambda c: 0 if (c.get("name") or "").lower() in who else 1)
    return cast


def _beats(d):
    setup = d.get("setup") or {}
    st = presets.structure(setup.get("structure")) or presets.structure("musical")
    beats = setup.get("beats") if setup.get("structure") == "custom" and setup.get("beats") else st["beats"]
    return beats or presets.structure("musical")["beats"]


def write_musical(d, ep):
    """Lyrics laid out on the structure's beats + who sings each section + a visual idea per section."""
    setup = d.get("setup") or {}
    sg = setup.get("song") or {}
    beats = _beats(d)
    cast = [c for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c] or (d.get("characters") or [])[:3]
    sys_ = MUSICAL_SYS.format(beats="; ".join("%s (%s)" % (b[0], b[2]) for b in beats), secs=setup.get("length") or 120,
                              bpm=sg.get("bpm") or 100, genre=sg.get("genre") or "nursery rhyme",
                              vocal=sg.get("vocal") or "solo lead", lang=sg.get("lang") or "English")
    ask = ("Series: %s\nEpisode idea: %s\nLesson: %s\nCast: %s"
           % (d.get("name") or "our series", ep.get("idea") or "", ep.get("lesson") or "",
              "; ".join("%s - %s" % (c.get("name"), _desc(c)[:160]) for c in cast) or "the lead"))
    j = _json(_ask(ask, sys_, want_json=True, role="director", timeout=300))
    secs = []
    for i, x in enumerate(j.get("sections") or []):
        if not isinstance(x, dict):
            continue
        k = x.get("kind") if x.get("kind") in ("sing", "action", "establish") else (beats[i][2] if i < len(beats) else "sing")
        lines = [_clean(l, 160) for l in (x.get("lines") or []) if str(l).strip()][:8] if k == "sing" else []
        secs.append({"tag": _clean(x.get("tag") or (beats[i][0] if i < len(beats) else "Verse"), 40), "kind": k,
                     "singer": _clean(x.get("singer"), 60), "lines": lines, "idea": _clean(x.get("idea"), 400)})
    if not any(s_["lines"] for s_ in secs):
        raise ValueError("the writer didn't return lyrics — try again")
    lyrics = "\n\n".join("[%s]\n%s" % (s_["tag"], "\n".join(s_["lines"])) if s_["lines"] else "[%s]" % s_["tag"] for s_ in secs)
    voices = "; ".join("%s: %s" % (c.get("name"), presets.voice_desc(c.get("traits"))) for c in cast if presets.voice_desc(c.get("traits")))
    ep["sections"] = secs
    ep["song_text"] = {"title": _clean(j.get("title") or ep.get("title") or "Our song", 120),
                       "caption": presets.song_caption(sg, voices)[:600], "lyrics": lyrics[:4000]}
    ep.pop("chunks", None)                              # a new song invalidates the old shot map
    return ep


def _sections_from_lyrics(lyrics):
    out, cur = [], None
    for line in str(lyrics or "").splitlines():
        m = re.match(r"^\s*\[([^\]]{1,40})\]\s*$", line)
        if m:
            cur = {"tag": m.group(1), "kind": "sing", "singer": "", "lines": [], "idea": ""}
            out.append(cur)
        elif line.strip():
            if not cur:
                cur = {"tag": "Verse", "kind": "sing", "singer": "", "lines": [], "idea": ""}
                out.append(cur)
            cur["lines"].append(line.strip())
    for x in out:
        if not x["lines"]:
            x["kind"] = "action"
    return out


def _gap_edge(t, words, lo, hi):
    """A cut time near t that doesn't split a sung word: inside a word → the middle of the nearest gap between words."""
    hit = next((w for w in words if w["s"] < t < w["e"]), None)
    if not hit:
        return t
    gaps = [((a["e"] + b["s"]) / 2.0) for a, b in zip(words, words[1:]) if lo + 2.0 < (a["e"] + b["s"]) / 2.0 < hi - 2.0]
    return min(gaps, key=lambda g: abs(g - t)) if gaps else t


def _word_map(d, ep, secs):
    """Uploaded song: sections from the recognised words (real times); cuts fall in gaps between words; every shot
    carries exactly the words sung inside it."""
    target = float((d.get("setup") or {}).get("clip") or presets.CLIP_SECS)
    words = ep.get("words") or []
    chunks = []
    for x in ep.get("sections") or []:
        a, b = float(x["start"]), float(x["end"])
        if b - a < 1.0:
            continue
        n = max(1, int(round((b - a) / target)))
        while (b - a) / n > MAX_CHUNK:
            n += 1
        edges = [a] + [_gap_edge(a + (b - a) * k / n, words, a, b) for k in range(1, n)] + [b]
        for k in range(n):
            s0, s1 = edges[k], edges[k + 1]
            if s1 - s0 < 1.0:
                continue
            inside = [w["w"] for w in words if s0 <= (w["s"] + w["e"]) / 2.0 < s1]
            chunks.append({"i": len(chunks), "start": round(s0, 3), "end": round(s1, 3), "section": x.get("tag"),
                           "kind": "sing" if inside else "action", "singer": (x.get("singer") or "") if inside else "",
                           "lines": [" ".join(inside)] if inside else [], "idea": x.get("idea") or "",
                           "link": "cut" if (k == 0 or not chunks) else "continue", "shot": ""})
    return chunks


def song_map(d, ep, secs):
    """The finished song (secs long) → bar-aligned chunks of ~setup.clip seconds, section by section."""
    if ep.get("words") and ep.get("sections") and all("start" in x for x in ep["sections"]):
        return _word_map(d, ep, secs)
    setup = d.get("setup") or {}
    bpm = int((setup.get("song") or {}).get("bpm") or 100)
    bar = 240.0 / max(40, bpm)
    target = float(setup.get("clip") or presets.CLIP_SECS)
    sections = ep.get("sections") or _sections_from_lyrics((ep.get("song_text") or {}).get("lyrics"))
    if not sections:
        sections = [{"tag": "Song", "kind": "sing", "singer": "", "lines": [], "idea": ep.get("idea") or ""}]
    beats = _beats(d)
    if len(beats) == len(sections):
        shares = [float(b[1]) for b in beats]
    else:                                               # weigh by sung lines (instrumental ≈ two lines' worth)
        shares = [max(2, len(x.get("lines") or [])) for x in sections]
    tot = sum(shares) or 1.0
    snap = lambda t: round(t / bar) * bar
    bounds, acc = [0.0], 0.0
    for sh in shares[:-1]:
        acc += sh / tot * secs
        bounds.append(min(secs, max(bounds[-1] + bar, snap(acc))))
    bounds.append(secs)
    chunks = []
    for si, x in enumerate(sections):
        a, b = bounds[si], bounds[si + 1]
        if b - a < 1.0:
            continue
        n = max(1, int(round((b - a) / target)))
        while (b - a) / n > MAX_CHUNK:
            n += 1
        edges = [a] + [min(b, snap(a + (b - a) * k / n)) for k in range(1, n)] + [b]
        lines = x.get("lines") or []
        for k in range(n):
            s0, s1 = edges[k], edges[k + 1]
            if s1 - s0 < 1.0:
                continue
            part = lines[len(lines) * k // n: len(lines) * (k + 1) // n] if lines else []
            chunks.append({"i": len(chunks), "start": round(s0, 3), "end": round(s1, 3), "section": x.get("tag"),
                           "kind": x.get("kind") or "sing", "singer": x.get("singer") or "", "lines": part,
                           "idea": x.get("idea") or "", "link": "cut" if (k == 0 or not chunks) else "continue", "shot": ""})
    return chunks


def write_chunks(d, ep):
    """One shot paragraph + cut/continue decision per chunk (the director), with a plain fallback."""
    chunks = ep.get("chunks") or []
    if not chunks:
        raise ValueError("make the song first — the shots are cut to it")
    ps = presets.style((d.get("setup") or {}).get("style")) or {}
    cast = _cast_of(d, ep) or [c for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c]
    lyr = (ep.get("song_text") or {}).get("lyrics") or ""
    objs = [o for o in (_find(d, "objects", oid) for oid in ep.get("props") or []) if o]
    ask = "Episode: %s\nWhole song lyrics:\n%s\nCast: %s%s\nChunks:\n%s" % (
        ep.get("idea") or ep.get("title") or "", lyr[:3000] or "(instrumental)",
        ", ".join(c.get("name") or "" for c in cast) or "the lead",
        ("\nObjects that can appear (by name): " + ", ".join("%s (%s)" % (o.get("name"), _odesc(o)[:80]) for o in objs)) if objs else "",
        "\n".join("%d. [%.1f-%.1fs, %s, %s%s] idea: %s | lyrics: %s" % (
            c["i"], c["start"], c["end"], c["section"], c["kind"], (", singer " + c["singer"]) if c.get("singer") else "",
            c.get("idea") or "-", " / ".join(c.get("lines") or []) or "(instrumental)") for c in chunks))
    sys_ = CHUNKS_SYS.format(camera=ps.get("camera") or "gentle, readable children's TV framing",
                             locs=", ".join(l.get("name") or "" for l in d.get("locations") or []) or "one cosy set")
    got = {}
    try:
        for x in (_json(_ask(ask, sys_, want_json=True, role="director", timeout=300)).get("chunks") or []):
            if isinstance(x, dict) and str(x.get("i", "")).isdigit():
                got[int(x["i"])] = x
    except Exception:
        got = {}
    for c in chunks:
        x = got.get(c["i"]) or {}
        c["shot"] = _clean(x.get("shot"), 1500) or (
            "%s. %s" % (c.get("idea") or "The cast performs together",
                        ("%s sings to camera with big expressive mouth shapes." % c["singer"]) if c["kind"] == "sing" and c.get("singer")
                        else "Everyone dances on the beat, mouths closed."))
        if x.get("link") in ("continue", "cut"):
            c["link"] = x["link"]
        if x.get("singer") is not None and c["kind"] == "sing":
            c["singer"] = _clean(x.get("singer"), 60) or c.get("singer")
        if c["kind"] == "sing" and not c.get("singer") and cast:
            c["singer"] = cast[0].get("name") or ""
        if re.match(r"\s*(cut to|new angle|meanwhile|later)\b", c["shot"], re.I):
            c["link"] = "cut"                          # the writer asked for a new angle: honour it
    chunks[0]["link"] = "cut"
    run = 0
    for c in chunks:                                   # never more than 3 "continue" shots in a row: a cut re-anchors
        run = run + 1 if c["link"] == "continue" else 0 # the character on its sheets, so it can't slowly drift
        if run > 3:
            c["link"], run = "cut", 0
    return ep


def _ff(args, timeout=300):
    import subprocess
    r = subprocess.run([core.FFMPEG, "-hide_banner", "-y"] + args, capture_output=True, timeout=timeout,
                       creationflags=getattr(core, "NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + (r.stderr or b"").decode("utf-8", "replace")[-400:])


def cut_chunk_audio(ep, ch, store_ref):
    """This chunk's slice of the song (a wav ref). A "continue" chunk also gets the ANCHOR frames before it, because
    the clip it is generated as starts on the previous clip's last frames — those are trimmed off after rendering."""
    pre = (ANCHOR / 24.0) if (ch.get("link") == "continue" and ch["i"] > 0) else 0.0
    if _ref(ch.get("audio")) and abs(float(ch.get("pre") or 0) - pre) < 1e-3:
        return ch["audio"]
    src = core.in_dir(core.LIB, ep.get("song") or "")
    if not src or not os.path.isfile(src):
        raise ValueError("the song file is gone — make the song again")
    name = store_ref("chunk%02d" % ch["i"], ".wav")
    s0 = max(0.0, ch["start"] - pre)
    _ff(["-ss", "%.3f" % s0, "-t", "%.3f" % (ch["end"] - s0), "-i", src, "-ac", "2", "-ar", "44100",
         os.path.join(core.REFS, name)], 120)
    ch["audio"], ch["pre"] = name, pre
    return name


def slot_copy(ch, store_ref):
    """The rendered clip of chunk ch cut to exactly its slot in the song — what the assembled episode shows. H3 renders
    on a 17k+5 frame grid, so a clip runs up to ~0.7 s past its slot; the next "continue" shot must grow out of the
    frame the edit cuts on, not out of the discarded overrun, or every continue join jumps. → ref name"""
    src = os.path.join(core.REFS, ch.get("clipref") or "")
    name = store_ref("slot%02d" % ch["i"], ".mp4")
    _ff(["-i", src, "-vf", "fps=24,tpad=stop_mode=clone:stop_duration=2,trim=duration=%.4f,setpts=PTS-STARTPTS"
         % (ch["end"] - ch["start"]), "-an", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
         os.path.join(core.REFS, name)], 300)
    return name


def _lib(name):
    p = core.in_dir(core.LIB, name or "")
    return p if p and os.path.isfile(p) else None


def assemble(d, ep, uid):
    """All rendered chunks, each trimmed to its slot, joined in order, under the ONE continuous master song. → lib name"""
    chunks = ep.get("chunks") or []
    missing = [c["i"] + 1 for c in chunks if not _lib(c.get("clip"))]
    if missing:
        raise ValueError("shots still to render: " + ", ".join(map(str, missing[:20])))
    song = _lib(ep.get("song"))
    if not song:
        raise ValueError("the song file is gone")
    w, h = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960), "21:9": (1680, 720)}.get(_aspect(d), (1280, 720))
    soft = (d.get("setup") or {}).get("join", "soft") == "soft"
    xd = 0.3                                           # dissolve length on a cut (s)
    args, fc = [], []
    for k, c in enumerate(chunks):
        ln = c["end"] - c["start"]
        nxt = chunks[k + 1] if k + 1 < len(chunks) else None
        # a dissolve borrows xd s of this clip's own overrun (or a held last frame), so every shot still starts
        # exactly on its beat and the picture never drifts from the song
        ext = xd if (soft and nxt and nxt.get("link") != "continue") else 0.0
        args += ["-i", _lib(c["clip"])]
        fc.append("[%d:v]fps=24,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,format=yuv420p,"
                  "tpad=stop_mode=clone:stop_duration=2,trim=duration=%.4f,setpts=PTS-STARTPTS,settb=1/24[v%d]"
                  % (k, w, h, w, h, ln + ext, k))
    cur, acc = "v0", chunks[0]["end"] - chunks[0]["start"]
    for k in range(1, len(chunks)):
        out = "j%d" % k if k < len(chunks) - 1 else "vout"
        if soft and chunks[k].get("link") != "continue":
            fc.append("[%s][v%d]xfade=transition=fade:duration=%.2f:offset=%.4f[%s]" % (cur, k, xd, acc, out))
        else:
            fc.append("[%s][v%d]concat=n=2:v=1:a=0,settb=1/24[%s]" % (cur, k, out))   # concat resets the timebase
        cur, acc = out, acc + chunks[k]["end"] - chunks[k]["start"]
    if len(chunks) == 1:
        fc[-1] = fc[-1][:fc[-1].rindex("[")] + "[vout]"
    args += ["-i", song]
    name = core.new_name("series", ".mp4")
    out = os.path.join(core.LIB, name)
    _ff(args + ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "%d:a" % len(chunks), "-c:v", "libx264",
                "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", out], 1800)
    core.index_add(name, {"model": "series", "prompt": "%s — %s" % (d.get("name") or "Series", ep.get("title") or "Episode"),
                          "created": time.time(), "user": uid or "owner", "mode": "musical", "clips": len(chunks)})
    return name


def musical_project(d, ep):
    """Editor project for a musical: every chunk on V1 at its song position (trimmed to its slot), master song on A1."""
    clips = []
    for c in ep.get("chunks") or []:
        if c.get("clip"):
            clips.append({"id": uuid.uuid4().hex[:8], "type": "video", "src": "lib:" + c["clip"], "start": c["start"], "in": 0,
                          "out": round(c["end"] - c["start"], 3), "volume": 0.0, "fade_in": 0, "fade_out": 0})
    tracks = [{"id": "t1", "kind": "text", "name": "Titles", "clips": []}, {"id": "v1", "kind": "video", "name": "Shots", "clips": clips}]
    if ep.get("song"):
        tracks.append({"id": "a1", "kind": "audio", "name": "Song", "clips": [{"id": uuid.uuid4().hex[:8], "type": "audio",
                       "src": "lib:" + ep["song"], "start": 0, "in": 0, "out": float(ep.get("song_secs") or 120), "volume": 1.0,
                       "fade_out": 1.0}]})
    w, h = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960), "21:9": (1680, 720)}.get(_aspect(d), (1280, 720))
    return {"name": "%s — %s" % (d.get("name") or "Series", ep.get("title") or "Musical"), "w": w, "h": h, "fps": 24,
            "tracks": tracks, "cover": clips[0]["src"] if clips else None}


# ── episode → timeline-editor project ───────────────────────────────────────────────────────────────────────────
def episode_project(d, ep, seconds_of):
    """Scenes in order on V1 (their own dialogue audio kept), the song on A1 after them. → editor project dict."""
    clips, t = [], 0.0
    for name in ep.get("scenes") or []:
        ln = seconds_of("lib:" + name) or float(ep.get("seconds") or 10)
        clips.append({"id": uuid.uuid4().hex[:8], "type": "video", "src": "lib:" + name, "start": round(t, 3), "in": 0, "out": round(ln, 3),
                      "volume": 1.0, "fade_in": 0, "fade_out": 0})
        t += ln
    tracks = [{"id": "t1", "kind": "text", "name": "Titles", "clips": []}, {"id": "v1", "kind": "video", "name": "Scenes", "clips": clips}]
    if ep.get("song"):
        sl = seconds_of("lib:" + ep["song"]) or 30.0
        tracks.append({"id": "a2", "kind": "audio", "name": "Song", "clips": [{"id": uuid.uuid4().hex[:8], "type": "audio", "src": "lib:" + ep["song"], "start": round(t, 3),
                                                                   "in": 0, "out": round(sl, 3), "volume": 1.0, "fade_out": 1.0}]})
    first = (ep.get("scenes") or [None])[0]
    return {"name": "%s — %s" % (d.get("name") or "Series", ep.get("title") or "Episode"), "w": 1280, "h": 720, "fps": 30,
            "tracks": tracks, "cover": ("lib:" + first) if first else None}


def _unmarked(src, dst):
    """Reference copy without the lab's corner watermark: trim the bottom strip it sits in. ffmpeg only."""
    try:
        try:
            from . import watermark
        except ImportError:
            import watermark
        if not watermark.enabled() or os.path.splitext(src)[1].lower() not in watermark.IMAGE:
            return False
        import subprocess
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-y", "-i", src, "-vf", "crop=iw:trunc(ih*0.93/2)*2:0:0", dst],
                           capture_output=True, timeout=60, creationflags=getattr(core, "NO_WINDOW", 0))
        return r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0
    except Exception:
        return False


# ── concurrency: the background runner and the page both write the same series file ───────────────────────────────
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def locked(uid, sid):
    with _LOCKS_GUARD:
        return _LOCKS.setdefault((str(uid), str(sid)), threading.RLock())


# ── tracking: append-only event log + checkpoints (walk back) ─────────────────────────────────────────────────────
MAX_VERSIONS = 200


def log_event(uid, sid, ev, **kw):
    """One line per thing that happened — what a successor (or the person, after a crash) reads to pick up."""
    rec = dict(kw, t=round(time.time(), 3), ev=ev)
    try:
        with open(os.path.join(_dir(uid), sid + ".log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def read_log(uid, sid, limit=300):
    p = os.path.join(_dir(uid), sid + ".log.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def _vdir(uid, sid):
    d = os.path.join(_dir(uid), "versions", sid)
    os.makedirs(d, exist_ok=True)
    return d


def checkpoint(uid, d, label):
    """Snapshot of the whole series after a step. Media files are never deleted, so any snapshot can be restored."""
    name = "%d_%s.json" % (int(time.time() * 1000), re.sub(r"[^a-z0-9_-]+", "-", str(label).lower())[:48].strip("-") or "step")
    with open(os.path.join(_vdir(uid, d["id"]), name), "w", encoding="utf-8") as f:
        json.dump(d, f)
    vs = sorted(os.listdir(_vdir(uid, d["id"])))
    for old in vs[:-MAX_VERSIONS]:
        try:
            os.remove(os.path.join(_vdir(uid, d["id"]), old))
        except OSError:
            pass
    log_event(uid, d["id"], "checkpoint", label=label, version=name[:-5])
    return name[:-5]


def versions(uid, sid):
    out = []
    for f in sorted(os.listdir(_vdir(uid, sid)), reverse=True):
        if f.endswith(".json"):
            ts, _, label = f[:-5].partition("_")
            out.append({"version": f[:-5], "t": int(ts) / 1000.0 if ts.isdigit() else 0, "label": label.replace("-", " ")})
    return out


def restore(uid, sid, version):
    p = os.path.join(_vdir(uid, sid), os.path.basename(str(version)) + ".json")
    if not os.path.isfile(p):
        raise ValueError("no such checkpoint")
    with open(p, encoding="utf-8") as f:
        snap = json.load(f)
    cur = load(uid, sid)
    if cur:
        checkpoint(uid, cur, "before restore")        # restoring is itself undoable
    snap["id"] = sid
    save(uid, snap)
    log_event(uid, sid, "restore", version=version)
    return snap


# ── the steps, as plain functions (the page's routes and the background runner both call these) ───────────────────
def prepare(uid, d, kind, target, extra, store_ref):
    """→ the /api/generate request for one step (cuts the chunk's song slice first when needed)."""
    extra = dict(extra or {})
    if kind == "chunk":
        ep = _find(d, "episodes", target)
        ch = _chunk(ep, extra.get("i"))
        if ch:
            cut_chunk_audio(ep, ch, store_ref)
            save(uid, d)
    r = plan(d, kind, target, extra)
    if kind == "chunk" and not r.get("error"):
        ep = _find(d, "episodes", target)
        ch = _chunk(ep, extra.get("i"))
        prev = _chunk(ep, ch["i"] - 1) if ch else None
        if ch and ch.get("link") == "continue" and prev and r["refs"] and r["refs"][0] == _ref(prev.get("clipref")):
            r["refs"][0] = slot_copy(prev, store_ref)
    if not r.get("error"):
        r["series"] = True                             # the lab keeps an unmarked copy for the next shot to build on
        if extra.get("i") is not None:
            r["attach"]["i"] = extra["i"]
    return r


def attach_file(uid, d, name, kind, target, i=None, store_ref=None, seconds_of=None, my_ref=None):
    """A finished library file → its place in the series. → updated series (saved + checkpointed)."""
    src = core.in_dir(core.LIB, name)
    if not src or not os.path.isfile(src):
        raise ValueError("that render isn't in your library")
    clean = "ref_clean_" + name                        # the unmarked copy the lab kept for series renders
    clean = clean if os.path.isfile(os.path.join(core.REFS, clean)) and (not my_ref or my_ref(clean)) else None
    label = kind
    if kind in ("keyframe", "chunk"):
        ep = _find(d, "episodes", target)
        ch = _chunk(ep, i)
        if not ch:
            raise ValueError("that shot isn't in the episode any more")
        if kind == "chunk":
            ch["clip"], ch["clipref"] = name, clean
            ch.setdefault("takes", [])
            if not any(t.get("clip") == name for t in ch["takes"]):
                ch["takes"].append({"clip": name, "clipref": clean, "t": round(time.time())})
            _stale_after(ep, ch)
        else:
            if not clean:
                stem, ext = os.path.splitext(name)
                clean = store_ref(stem, ext.lower())
                if not _unmarked(src, os.path.join(core.REFS, clean)):
                    shutil.copy2(src, os.path.join(core.REFS, clean))
            ch["key"] = clean
        ep.pop("final", None)
        label = "%s %d" % ("shot" if kind == "chunk" else "first frame", ch["i"] + 1)
    elif kind == "song":
        ep = _find(d, "episodes", target)
        if not ep:
            raise ValueError("pick an episode")
        use_song(d, ep, name, seconds_of, source="made")
    elif kind == "scene":
        ep = _find(d, "episodes", target)
        if not ep:
            raise ValueError("pick an episode")
        ep["scenes"] = (ep.get("scenes") or []) + [name]
    else:
        if clean:
            ref = clean
        else:
            stem, ext = os.path.splitext(name)
            ref = store_ref(stem, ext.lower())
            dst = core.safe_path(os.path.join(core.REFS, ref))
            if not _unmarked(src, dst):                # the library copy keeps its watermark; the reference must not
                shutil.copy2(src, dst)                 # (or every sheet / scene drawn from it would copy the mark)
        if kind in ("hero", "sheet", "expr"):
            c = _find(d, "characters", target)
            if not c:
                raise ValueError("pick a character")
            c[kind] = ref
            label = "%s %s" % (c.get("name") or "character", kind)
        elif kind in ("object", "objsheet", "objdetail"):
            o = _find(d, "objects", target)
            if not o:
                raise ValueError("pick an object")
            o[{"object": "hero", "objsheet": "sheet", "objdetail": "detail"}[kind]] = ref
            label = "%s %s" % (o.get("name") or "object", {"object": "design", "objsheet": "turnaround", "objdetail": "details"}[kind])
        elif kind == "location":
            loc = _find(d, "locations", target)
            if not loc:
                raise ValueError("pick a location")
            loc["image"] = ref
        elif kind == "locsheet":
            loc = _find(d, "locations", target)
            if not loc:
                raise ValueError("pick a location")
            loc["sheet"] = ref
            label = "%s turnaround" % (loc.get("name") or "location")
        elif kind == "locview":
            loc = _find(d, "locations", target)
            if not loc:
                raise ValueError("pick a location")
            if not isinstance(i, int) or not 0 <= i < len(LOC_VIEWS):
                raise ValueError("unknown view")
            loc.setdefault("views", {})[LOC_VIEWS[i][0]] = ref
            label = "%s %s" % (loc.get("name") or "location", LOC_VIEWS[i][1].lower())
        elif kind == "lineup":
            d["lineup"] = ref
        else:
            raise ValueError("unknown step")
    save(uid, d)
    checkpoint(uid, d, label)
    return d


def _stale_after(ep, ch):
    """A new picture for shot N breaks the "continue" chain that grew out of it."""
    for later in ep.get("chunks") or []:
        if later["i"] > ch["i"] and later.get("link") == "continue":
            if later.get("clip"):
                later["stale"] = True
        elif later["i"] > ch["i"]:
            break
    ch.pop("stale", None)


def use_take(d, ep, i, clip):
    ch = _chunk(ep, i)
    t = next((x for x in (ch or {}).get("takes") or [] if x.get("clip") == clip), None)
    if not t:
        raise ValueError("no such take")
    ch["clip"], ch["clipref"] = t["clip"], t.get("clipref")
    _stale_after(ep, ch)
    ep.pop("final", None)


def use_song(d, ep, name, seconds_of, source="upload"):
    """The episode's master song (made here or uploaded). Re-cuts the shot map; uploaded songs get recognised later."""
    ep["song"] = name
    ep["song_source"] = source
    ep["song_secs"] = round((seconds_of("lib:" + name) if seconds_of else 0) or float((d.get("setup") or {}).get("length") or 60), 3)
    if source == "upload":
        for k in ("words", "vocal", "sections"):
            ep.pop(k, None)
        ep["song_text"] = {"title": ep.get("title") or "My song", "caption": "", "lyrics": ""}
    ep["chunks"] = song_map(d, ep, ep["song_secs"])
    ep.pop("final", None)


def finish(uid, d, ep, editor_dir):
    """Assemble + editor project (both the page and the runner)."""
    ep["final"] = assemble(d, ep, uid)
    proj = musical_project(d, ep)
    pid = ep.get("project") if _ID_RE.match(str(ep.get("project") or "")) else uuid.uuid4().hex[:12]
    proj.update(id=pid, created=time.time(), updated=time.time())
    with open(os.path.join(editor_dir, pid + ".json"), "w", encoding="utf-8") as f:
        json.dump(proj, f)
    ep["project"] = pid
    save(uid, d)
    checkpoint(uid, d, "episode assembled")
    return d


# ── hearing an uploaded song: vocal stem → words with times → lines / sections / shot map ─────────────────────────
def transcribe(uid, sid, eid, store_ref, progress=None):
    try:
        from . import series_audio as sa
    except ImportError:
        import series_audio as sa
    with locked(uid, sid):
        d = load(uid, sid)
        ep = _find(d, "episodes", eid)
        song = _lib((ep or {}).get("song"))
    if not song:
        raise ValueError("add the song first")
    say = progress or (lambda m: None)
    say("separating the vocal from the music …")
    out_dir = os.path.join(core.REFS, "_stems_%s" % eid)
    try:
        vocal_tmp = sa.vocal_stem(song, out_dir)
        vocal = store_ref("vocal_" + eid, ".wav")
        shutil.move(vocal_tmp, os.path.join(core.REFS, vocal))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    say("listening for the words …")
    got = sa.words_of(os.path.join(core.REFS, vocal))
    with locked(uid, sid):
        d = load(uid, sid)
        ep = _find(d, "episodes", eid)
        ep["vocal"], ep["words"], ep["lang"] = vocal, got["words"], got.get("lang")
        ep["sections"] = sa.sections_of(got["words"], float(ep.get("song_secs") or 60))
        lead = next((c.get("name") for c in (_find(d, "characters", cid) for cid in ep.get("cast") or []) if c), "") or \
            next((c.get("name") for c in d.get("characters") or []), "")
        for s_ in ep["sections"]:
            if s_["kind"] == "sing" and not s_.get("singer"):
                s_["singer"] = lead
        st = ep.get("song_text") or {}
        ep["song_text"] = {"title": st.get("title") or ep.get("title") or "My song", "caption": st.get("caption") or "",
                           "lyrics": sa.lyrics_text(ep["sections"])[:4000]}
        ep["chunks"] = song_map(d, ep, float(ep.get("song_secs") or 60))
        save(uid, d)
        checkpoint(uid, d, "lyrics recognised")
    log_event(uid, sid, "transcribed", ep=eid, words=len(got["words"]), lang=got.get("lang"))
    return d


# ── Flask wiring (both copies call register) ────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, my_file, my_ref, store_ref(stem, ext, owner=None), ref_info, can_attach, static, seconds_of(src)->float,
    editor_dir(uid=None)->path, submit(uid, request)->(job|error), job(jid)->dict|None."""
    from flask import request, jsonify, abort
    try:
        from . import series_run as runner, series_assets as assets
    except ImportError:
        import series_run as runner
        import series_assets as assets
    runner.setup(hk)
    assets.register(app, hk)

    def U():
        return hk["uid"]()

    def need(sid):
        d = load(U(), sid)
        if not d:
            abort(404)
        return d

    def body():
        return request.get_json(silent=True) or {}

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    def ep_of(d, eid):
        ep = _find(d, "episodes", eid)
        if not ep:
            abort(404)
        return ep

    @app.route("/series")
    def series_page():
        return hk["static"]("series.html")

    @app.route("/api/series/presets")
    def se_presets():
        return jsonify(presets.catalog())

    @app.route("/api/series")
    def se_list():
        return jsonify({"series": listing(U())})

    @app.route("/api/series", methods=["POST"])
    def se_save():
        b = body()
        if not b.get("id"):
            d = save(U(), merge(None, b))
            log_event(U(), d["id"], "created", name=d.get("name"))
            return jsonify(d)
        with locked(U(), b["id"]):
            old = load(U(), b.get("id"))
            if not old:
                return oops("no such series", 404)
            new = merge(old, b)
            if (old.get("setup") or {}) != (new.get("setup") or {}):
                log_event(U(), new["id"], "setup", setup=new.get("setup"))
            return jsonify(save(U(), new))

    @app.route("/api/series/<sid>")
    def se_get(sid):
        return jsonify(need(sid))

    @app.route("/api/series/<sid>/delete", methods=["POST"])
    def se_delete(sid):
        runner.stop(U(), sid)
        p = _path(U(), sid)
        if p and os.path.isfile(p):
            os.makedirs(core.TRASH, exist_ok=True)
            shutil.move(p, os.path.join(core.TRASH, "series_%s_%d.json" % (sid, int(time.time()))))
        return jsonify({"ok": True})

    @app.route("/api/series/<sid>/style", methods=["POST"])
    def se_style(sid):
        d = need(sid)
        refs = [os.path.basename(str(r)) for r in body().get("refs") or [] if hk["my_ref"](os.path.basename(str(r)))]
        try:
            got = analyse_style(d, refs, body().get("notes"))
        except Exception as e:
            return oops(e)
        with locked(U(), sid):
            d = need(sid)
            d.update(style_prompt=got["style_prompt"], style_analysis=got["analysis"])
            save(U(), d)
            checkpoint(U(), d, "style bible")
        return jsonify(d)

    @app.route("/api/series/<sid>/write", methods=["POST"])
    def se_write(sid):
        b = body()
        what = b.get("what") or "shots"
        d = need(sid)
        ep = _find(d, "episodes", b.get("episode"))
        if not ep:
            return oops("pick an episode")
        try:
            if what == "song":
                ep["song_text"] = write_song(d, ep)
            elif what == "musical":
                write_musical(d, ep)
            elif what == "chunks":
                write_chunks(d, ep)
            else:
                ep["shots"] = write_shots(d, ep)
        except Exception as e:
            log_event(U(), sid, "write-failed", what=what, error=str(e)[:200])
            return oops(e)
        with locked(U(), sid):                         # merge the writer's result onto the latest copy
            cur = need(sid)
            cep = _find(cur, "episodes", ep["id"])
            if cep is not None:
                cep.update({k: ep[k] for k in ("song_text", "sections", "chunks", "shots") if k in ep})
                if "chunks" not in ep:
                    cep.pop("chunks", None)
            save(U(), cur)
            checkpoint(U(), cur, {"song": "song lyrics", "musical": "song written", "chunks": "shots written"}.get(what, "shot list"))
        return jsonify(cur)

    @app.route("/api/series/<sid>/plan", methods=["POST"])
    def se_plan(sid):
        b = body()
        extra = dict(b.get("extra") or {})
        if extra.get("photo") and not hk["my_ref"](os.path.basename(str(extra["photo"]))):
            extra.pop("photo")
        with locked(U(), sid):
            try:
                r = prepare(U(), need(sid), str(b.get("kind") or ""), b.get("target"), extra, hk["store_ref"])
            except Exception as e:
                return oops(e)
        return oops(r["error"]) if r.get("error") else jsonify(r)

    @app.route("/api/series/<sid>/queue")
    def se_queue_get(sid):
        need(sid)
        return jsonify(runner.queue_status(U(), sid))

    @app.route("/api/series/<sid>/queue", methods=["POST"])
    def se_queue(sid):
        """One-off pictures (hero → turnaround → expressions, locations, lineup…) rendered and filed back by the
        server, so they land in the series even if the page is closed mid-render."""
        if hk["can_attach"]():
            return oops(hk["can_attach"](), 403)
        need(sid)
        b = body()
        if b.get("cancel"):
            return jsonify(runner.queue_cancel(U(), sid, str(b["cancel"])))
        steps = []
        for s in (b.get("steps") or [])[:6]:
            extra = dict(s.get("extra") or {})
            if extra.get("photo") and not hk["my_ref"](os.path.basename(str(extra["photo"]))):
                extra.pop("photo")
            steps.append({"kind": str(s.get("kind") or ""), "target": s.get("target"), "extra": extra, "label": s.get("label")})
        if not steps:
            return oops("nothing to do")
        try:
            return jsonify(runner.enqueue(U(), sid, steps))
        except Exception as e:
            return oops(e)

    @app.route("/api/series/<sid>/attach", methods=["POST"])
    def se_attach(sid):
        """A finished library file → this series (copied into the person's refs so it can be referenced later)."""
        if hk["can_attach"]():
            return oops(hk["can_attach"](), 403)
        b = body()
        name = os.path.basename(str(b.get("file") or ""))
        if not hk["my_file"](name):
            return oops("that render isn't in your library", 404)
        with locked(U(), sid):
            try:
                d = attach_file(U(), need(sid), name, b.get("kind"), b.get("target"), b.get("i"), hk["store_ref"],
                                hk["seconds_of"], hk["my_ref"])
            except Exception as e:
                return oops(e)
        log_event(U(), sid, "attached", kind=b.get("kind"), i=b.get("i"), file=name)
        return jsonify(d)

    @app.route("/api/series/<sid>/episode/<eid>/scene/remove", methods=["POST"])
    def se_scene_rm(sid, eid):
        with locked(U(), sid):
            d = need(sid)
            ep = ep_of(d, eid)
            name = os.path.basename(str(body().get("file") or ""))
            ep["scenes"] = [s for s in ep.get("scenes") or [] if s != name]
            return jsonify(save(U(), d))

    @app.route("/api/series/<sid>/episode/<eid>/remap", methods=["POST"])
    def se_remap(sid, eid):
        """Re-cut the song into shots (after a length / tempo / lyric change). Rendered shots are dropped from the map."""
        with locked(U(), sid):
            d = need(sid)
            ep = ep_of(d, eid)
            if not ep.get("song"):
                return oops("make the song first")
            ep["chunks"] = song_map(d, ep, float(ep.get("song_secs") or 60))
            save(U(), d)
            checkpoint(U(), d, "shots re-cut")
        return jsonify(d)

    @app.route("/api/series/<sid>/episode/<eid>/usesong", methods=["POST"])
    def se_usesong(sid, eid):
        """An uploaded song (a ref) becomes the episode's master track — then 'recognise' finds its words."""
        ref = os.path.basename(str(body().get("ref") or ""))
        p = core.in_dir(core.REFS, ref)
        if not p or not os.path.isfile(p) or not hk["my_ref"](ref) or core.kind_of(ref) != "audio":
            return oops("upload an audio file first")
        secs = hk["seconds_of"]("ref:" + ref)
        if secs > 600:
            return oops("songs up to 10 minutes")
        name = core.new_name("song", os.path.splitext(ref)[1].lower())
        shutil.copy2(p, os.path.join(core.LIB, name))
        core.index_add(name, {"model": "upload", "prompt": "uploaded song " + ref.split("_", 2)[-1], "created": time.time(),
                              "user": U() or "owner", "mode": "song"})
        with locked(U(), sid):
            d = need(sid)
            use_song(d, ep_of(d, eid), name, hk["seconds_of"], source="upload")
            save(U(), d)
            checkpoint(U(), d, "song uploaded")
        log_event(U(), sid, "song-uploaded", ep=eid, file=name, secs=secs)
        return jsonify(d)

    @app.route("/api/series/<sid>/episode/<eid>/recognise", methods=["POST"])
    def se_recognise(sid, eid):
        try:
            runner.recognise_async(U(), sid, eid)
        except Exception as e:
            return oops(e)
        return jsonify({"ok": True})

    @app.route("/api/series/<sid>/episode/<eid>/take", methods=["POST"])
    def se_take(sid, eid):
        b = body()
        with locked(U(), sid):
            d = need(sid)
            try:
                use_take(d, ep_of(d, eid), b.get("i"), os.path.basename(str(b.get("clip") or "")))
            except Exception as e:
                return oops(e)
            save(U(), d)
            checkpoint(U(), d, "shot %d take" % (int(b.get("i") or 0) + 1))
        return jsonify(d)

    @app.route("/api/series/<sid>/episode/<eid>/assemble", methods=["POST"])
    def se_assemble(sid, eid):
        with locked(U(), sid):
            d = need(sid)
            try:
                finish(U(), d, ep_of(d, eid), hk["editor_dir"](U()))
            except Exception as e:
                return oops(e)
        log_event(U(), sid, "assembled", ep=eid)
        return jsonify(d)

    @app.route("/api/series/<sid>/episode/<eid>/edit", methods=["POST"])
    def se_edit(sid, eid):
        """Assemble the episode into a timeline-editor project and return its id (opened at /editor?p=<id>)."""
        with locked(U(), sid):
            d = need(sid)
            ep = ep_of(d, eid)
            musical = any(c.get("clip") for c in ep.get("chunks") or [])
            if not (ep.get("scenes") or musical):
                return oops("render at least one scene first")
            proj = musical_project(d, ep) if musical else episode_project(d, ep, hk["seconds_of"])
            pid = ep.get("project") if _ID_RE.match(str(ep.get("project") or "")) else uuid.uuid4().hex[:12]
            proj.update(id=pid, created=time.time(), updated=time.time())
            with open(os.path.join(hk["editor_dir"](U()), pid + ".json"), "w", encoding="utf-8") as f:
                json.dump(proj, f)
            ep["project"] = pid
            save(U(), d)
        return jsonify({"project": pid})

    # ── tracking: history, checkpoints, the background run ──
    @app.route("/api/series/<sid>/log")
    def se_log(sid):
        need(sid)
        return jsonify({"events": read_log(U(), sid, int(request.args.get("limit") or 300))})

    @app.route("/api/series/<sid>/versions")
    def se_versions(sid):
        need(sid)
        return jsonify({"versions": versions(U(), sid)})

    @app.route("/api/series/<sid>/restore", methods=["POST"])
    def se_restore(sid):
        need(sid)
        b = body()
        runner.pause(U(), sid, "restoring a checkpoint")
        with locked(U(), sid):
            try:
                if b.get("back"):                      # walk back one step = the checkpoint before the latest
                    vs = versions(U(), sid)
                    if len(vs) < 2:
                        return oops("nothing earlier to go back to")
                    d = restore(U(), sid, vs[1]["version"])
                else:
                    d = restore(U(), sid, b.get("version"))
            except Exception as e:
                return oops(e)
        return jsonify(d)

    @app.route("/api/series/<sid>/run")
    def se_run_get(sid):
        need(sid)
        return jsonify(runner.status(U(), sid))

    @app.route("/api/series/<sid>/run", methods=["POST"])
    def se_run(sid):
        d, b = need(sid), body()
        try:
            r = runner.control(U(), sid, b.get("action"), b.get("episode"))
        except Exception as e:
            return oops(e)
        return jsonify(r)
