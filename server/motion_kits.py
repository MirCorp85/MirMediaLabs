"""Diorama place kits: the library of extra places (beyond the six built-ins) and the AI set designer.

A film's location scout picks the extra places the story needs. A library kit is used when one fits (by id, or by its tags);
only when none does, the set designer draws a new kit in the engine's prop vocabulary. That kit is cleaned up and saved back to
the library, so every later film can reuse it. Kits live in <MG>/diorama_kits/<id>.json; the engine draws them
(TOOLS/MirRemotion/src/mg/diorama_engine.ts → kitPlace / PROP_TYPES / FLOOR_KINDS)."""
import json
import os
import re
import time

BUILTIN = {"apartment": "home, night, waking up, private moments; \"sleep\" only at the bed","office": "work, meetings, data on the big screen, decisions",
           "lab": "science, experiments, technology, how things work", "cafe": "people, conversation, social life, everyday moments",
           "street": "outside, traffic, crowds, the city at ground level", "rooftop": "big picture, signals, the whole city below, endings"}
PROPS = ["box", "table", "desk", "counter", "shelf", "bed", "chair", "sofa", "bench", "screen", "board", "window", "rack", "machine", "console", "tank", "pillar",
         "pipe", "lamp", "light", "plant", "tree", "bush", "rail", "sign", "sphere", "crate", "stage", "podium", "ring", "dish", "car", "boat", "patch", "court",
         # world scenery (Oct 29) - diorama_engine.ts worldProp
         "rock", "cactus", "palm", "pine", "tent", "campfire", "fence", "hay", "barrel", "crater", "wire", "sandbag", "ruin", "dome", "rocket", "flag", "torch", "well",
         "cart", "log", "hut", "house", "tower", "wallc", "snowman", "parasol", "crop", "ship", "fountain", "stump", "mushroom", "dune", "armor", "stall", "statue",
         "iceberg", "lighthouse", "windmill", "temple", "bigtree"]
WALL_ONLY = ("board", "window")
FLOORS = ["tile", "wood", "carpet", "concrete", "grass", "sand", "water", "mud", "snow", "dirt", "cobble", "moon", "ice", "leaf", "deck"]
WALLS = ["both", "back", "left", "none"]
COLS = ["char0", "char1", "graph", "graph2", "steel", "steel2", "silver", "silver2", "bronze", "brass", "gold", "champ", "pale", "ember", "olive", "olive2", "red"]
POSES = ["stand", "explain", "type", "think", "listen", "celebrate", "wave", "point", "shrug"]
SLOTS = [(3, 2), (2, 3), (4, 3), (3, 4), (1, 2), (2, 1), (5, 4), (4, 5)]      # city lots (grid cells) for a film's extra places
MAX_EXTRA = 4
# WORLDS (Oct 29, user: "the videos need other places than just the city") - must match diorama_engine.ts WORLDS. The tags pick
# the world from a premise; outside the city the six city places are not on the map, so a film's places are its world's kits.
WORLDS = {
    "city": ("Night city", "a tiny night city: towers, streets, home, office, lab, cafe, rooftop", "city town office work tech technology startup money job apartment downtown modern street urban school hospital"),
    "countryside": ("Countryside", "farmland at dusk: fields, barns, hay, windmills, a farmhouse, cows and chickens", "farm farmer countryside village rural harvest crops cow cows tractor barn field fields ranch chicken"),
    "forest": ("Forest", "a deep forest at night: pines, a river, a campsite, a cabin, deer, owls, fireflies", "forest woods camping camp cabin hike wilderness wolf bear deer lost survival hunter trees"),
    "beach": ("Beach & coast", "a sunset coast: sand, sea, palms, parasols, a lighthouse, boats", "beach sea coast summer holiday vacation surf swim lighthouse shore tropical"),
    "desert": ("Desert", "a desert at golden hour: dunes, cacti, an oasis, a highway, tents, camels", "desert sand dunes camel oasis sahara egypt pyramid cactus thirst caravan"),
    "snow": ("Snowy mountains", "winter mountains: snowy pines, a ski lodge, cabins, a frozen lake, summits", "snow winter ski mountain mountains everest climb cold ice arctic christmas frozen"),
    "war": ("Battlefield", "a war-torn battlefield: trenches, craters, ruins, barbed wire, tanks, smoke", "war battle soldier soldiers army trench ww1 ww2 world military invasion front tank combat"),
    "moon": ("Moon base", "the moon: grey dust, craters, domes, a rocket, Earth in the sky, astronauts", "moon space astronaut astronauts rocket nasa mars planet lunar galaxy alien spaceship orbit"),
    "medieval": ("Medieval kingdom", "a medieval town: cottages, a castle, a market, a tavern, knights and villagers", "medieval castle king queen knight knights kingdom dragon middle ages prince princess sword"),
    "jungle": ("Jungle", "a steamy jungle: giant trees, a river, temple ruins, monkeys, parrots, tigers", "jungle rainforest amazon temple explorer expedition treasure ruins tiger monkey tribe"),
    "ocean": ("Open ocean", "the open sea: islands, a ship deck, icebergs, whales", "ocean sea ship pirate pirates sailor sailing voyage island castaway shipwreck whale titanic"),
}
WORLD_SYS = """Pick the ONE world a narrated animated film is set in. Worlds:
WORLDS
Choose the world where MOST of the story happens (a story about farming = countryside, about soldiers = war, about astronauts = moon;
everyday modern life, work, money, technology = city). If the story clearly happens somewhere NONE of these can show (under the sea, inside the
human body, a volcano, the age of dinosaurs, an alien planet, a candy land…), reply "new". Reply JSON: {"world": "<id>|new"}"""


def kit_world(k):
    return k.get("world") if k.get("world") in WORLDS else "city"


def pick_world(brief, ask=None, log=lambda m, l="info": None, want=None, mint=None):
    """The world a premise is set in: an explicit choice, else keywords, else the writer brain (which may say no world fits →
    mint(brief) designs a new one, motion_mint.design_world), else the city."""
    if want in WORLDS:
        return want
    ws = _words(brief)
    score = {w: len(ws & set(v[2].split())) for w, v in WORLDS.items()}
    best = max(score, key=score.get)
    rest = sorted(score.values())[-2]
    if score[best] >= 2 and score[best] > rest:
        return best
    if ask or mint:                      # mint on → always ask the brain (Claude via ask_json), so "no world fits" can be heard
        try:
            j = ask_json("Premise: %s" % brief, WORLD_SYS.replace("WORLDS", "\n".join("  %s: %s" % (k, v[1]) for k, v in WORLDS.items())), ask)
            if j.get("world") in WORLDS:
                return j["world"]
            if j.get("world") == "new" and mint:
                w = mint(brief)
                if w in WORLDS:
                    return w
        except Exception as e:
            log("the world picker failed (%s) - using keywords" % str(e)[:60], "warn")
    return best if score[best] else "city"
_ID = re.compile(r"^[a-z][a-z0-9_]{2,23}$")
_CACHE = {"sig": None, "kits": {}}


def kits_dir(mg):
    d = os.path.join(mg, "diorama_kits")
    os.makedirs(d, exist_ok=True)
    return d


def library(mg):
    """{id: kit} for every kit in the library (re-read when a file changes)."""
    d = kits_dir(mg)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".json") and not f.startswith("_"))
    sig = tuple((f, os.path.getmtime(os.path.join(d, f))) for f in fs)
    if sig != _CACHE["sig"]:
        kits = {}
        for f in fs:
            try:
                k = json.load(open(os.path.join(d, f), encoding="utf-8"))
                if isinstance(k, dict) and _ID.match(str(k.get("id") or "")) and k["id"] not in BUILTIN:
                    kits[k["id"]] = k
            except Exception:
                pass
        _CACHE.update(sig=sig, kits=kits)
    return _CACHE["kits"]


def catalog(mg):
    return [{"id": k["id"], "name": k.get("name") or k["id"], "about": k.get("about") or "", "source": k.get("source") or "seed", "world": kit_world(k),
             "tags": k.get("tags") or [], "stations": list((k.get("st") or {}).keys())} for k in library(mg).values()]


# ── the location scout ──
SCOUT_SYS = """You are the location scout for a Diorama film: a narrated animated film in a tiny isometric night city.
The city ALWAYS has these six places:
BUILTIN
The PLACE LIBRARY also has ready-made places:
LIBRARY
Pick the EXTRA places this story needs (0 to 4) so that every scenario happens somewhere that fits it - a hospital story needs
a hospital ward, a space story a mission control room, a sports story a stadium. Prefer the six and the library: use a library
id whenever it fits. Only when the story truly needs a setting that none of them can stand in for, describe a NEW place.
Never add an extra place that one of the six already covers (home, office, lab, cafe, street, rooftop). Most everyday stories
need 0 or 1 extra place.
Reply JSON: {"places": [{"id": "<library id>"} or {"new": "short_snake_case_id", "name": "Name", "about": "what stories it fits, one line",
"look": "what is in it, 1-2 sentences"}]}"""


def _words(s):
    return {w for w in re.findall(r"[a-z]+", str(s or "").lower()) if len(w) > 2}


def match(mg, text, exclude=()):
    """The library kit whose id/name/tags best match a description (needs two hits), else None."""
    want, best, score = _words(text), None, 1
    for k in library(mg).values():
        if k["id"] in exclude:
            continue
        have = _words(" ".join([k["id"].replace("_", " "), k.get("name") or ""] + list(k.get("tags") or [])))
        s = len(want & have)
        if s > score:
            best, score = k["id"], s
    return best


SCOUT_WORLD_SYS = """You are the location scout for a Diorama film: a narrated animated film in a tiny isometric world.
This film is set in the WORLD: WNAME - WABOUT. There is no city here: every scene happens in a place of this world.
The PLACE LIBRARY has ready-made places (the ones of this world first):
LIBRARY
Pick the 2 to 5 places this story needs so that every scenario happens somewhere that fits it. Use a library id whenever it
fits; only when the story truly needs a setting none of them can stand in for, describe a NEW place of this world.
Reply JSON: {"places": [{"id": "<library id>"} or {"new": "short_snake_case_id", "name": "Name", "about": "what stories it fits, one line",
"look": "what is in it, 1-2 sentences"}]}"""


def scout(mg, brief, ask, log=lambda m, l="info": None, world="city"):
    """→ [kit ids] for this film (library first, newly designed kits saved to the library). Outside the city every place comes
    from the kits (this world's first) and a film has up to six of them."""
    lib, world = library(mg), world if world in WORLDS else "city"
    mx = MAX_EXTRA if world == "city" else 6
    if world == "city":
        sys_ = SCOUT_SYS.replace("BUILTIN", "\n".join("  %s: %s" % kv for kv in BUILTIN.items())).replace(
            "LIBRARY", "\n".join("  %s: %s" % (k["id"], k.get("about") or k.get("name")) for k in lib.values() if kit_world(k) == "city") or "  (empty)")
    else:
        mine = [k for k in lib.values() if kit_world(k) == world] + [k for k in lib.values() if kit_world(k) != world]
        sys_ = SCOUT_WORLD_SYS.replace("WNAME", WORLDS[world][0]).replace("WABOUT", WORLDS[world][1]).replace(
            "LIBRARY", "\n".join("  %s: %s%s" % (k["id"], k.get("about") or k.get("name"), "" if kit_world(k) == world else "  [%s]" % kit_world(k)) for k in mine) or "  (empty)")
    j = ask_json("Premise: %s" % brief, sys_, ask)
    out = []
    for pk in (j.get("places") or [])[:mx + 2]:
        if len(out) >= mx or not isinstance(pk, dict):
            continue
        pid = str(pk.get("id") or "").lower().strip()
        if pid in BUILTIN:
            continue
        if pid in lib:
            if pid not in out:
                out.append(pid)
                log("place · %s (from the library)" % pid, "done")
            continue
        desc = " ".join(str(pk.get(x) or "") for x in ("new", "id", "name", "about", "look"))
        hit = match(mg, desc, out)
        if hit:
            out.append(hit)
            log("place · %s (from the library, for %s)" % (hit, pk.get("name") or pk.get("new") or pid), "done")
            continue
        try:
            kit = design(mg, pk, ask, world)
            out.append(kit["id"])
            log("place · %s (new - designed and saved to the library)" % kit["id"], "done")
        except Exception as e:
            log("couldn't design the place %s: %s" % (pk.get("name") or pk.get("new"), str(e)[:100]), "warn")
    if world != "city" and len(out) < 2:              # a world film always has places of its own
        for k in lib.values():
            if kit_world(k) == world and k["id"] not in out and len(out) < 3:
                out.append(k["id"])
                log("place · %s (from the %s world)" % (k["id"], world), "done")
    return out


# ── the set designer ──
KIT_SYS = """You are the set designer for the Diorama: a tiny isometric night city in charcoal, brushed metal and gold.
Design ONE place as a kit on a 4 x 4 floor tile.
COORDINATES: x and y run from 0 to 4. (0,0) is the BACK corner, furthest from the camera; x runs toward the lower right of the
screen, y toward the lower left; (4,4) is the front corner nearest the camera. The back walls run along y=0 (the "back" wall) and
x=0 (the "left" wall). Put big and tall things near the back walls (small x or small y); keep the middle and the front
(x + y > 4.5) open for people. A prop's footprint is x..x+w, y..y+d and must stay inside 0.1..3.9.
PROPS ("t", then w = size along x, d = size along y, h = height; defaults in brackets):
  box [.8 .8 .8] a generic block | table [1.2 .8 .72] | desk [1.1 .6 .74] desk with a monitor | counter [2 .6 1] | shelf [1.2 .4 1.8]
  full of books/items | bed [1.9 1 .55] | chair | sofa [1.4 .6] | bench [1 .35] | screen [1.2 .1 .8] a display: with "wall": "back"
  or "left" it hangs on that wall at height z (back wall: placed by x, left wall: placed by y; w = its width), otherwise it stands
  on a pole at height z | board (wall only) whiteboard/chalkboard | window (wall only) | rack [.6 .6 2] blinking server rack |
  machine [1 .8 1.4] industrial machine with lights | console [1.4 .6 .9] control desk with lit buttons | tank [.8 .8 1.6] vertical
  cylinder | pillar [.3 .3 2.6] | pipe [2 .15] horizontal at height z | lamp [.3 .3 1.8] floor lamp | light hanging light at
  height z | plant | tree [.8 .8 2.2] | bush | rail [2 .06 .5] railing along its long side (also a goal/fence) | sign [.6 .1 1.6]
  post with a gold sign | sphere [.6] ball/globe/planet, z = height above the floor | crate [.5 .5 .5] | stage [2 1.2 .25] low
  platform | podium [.5 .4 1.1] | ring [1.2 .3 1.4] standing ring: scanner, portal, hoop | dish [.8 .8 1.2] antenna | car [.7 1.6 .9]
  | boat [.9 2.2 .6] | patch [1.5 1.5] a floor area, "kind": grass|water|sand|wood|carpet|mud|snow|dirt|cobble|ice | court [3 3] gold field lines.
  WORLD SCENERY: rock [.6 .5 .45] | cactus [.3 .3 1.4] | palm [.5 .5 2.4] | pine [.8 .8 2.2] | bigtree [1.4 1.4 3.4] jungle/old tree |
  tent [1.4 1.2 1.1] | campfire [.6 .6] | fence [2 .08 .5] | hay [.6 .8 .6] bale | barrel [.4 .4 .6] | crater [1.4 1.4] | wire [2 .2 .45]
  barbed wire | sandbag [1.6 .4 .5] wall | ruin [1.6 1.4 1.8] bombed building | armor [1.4 2 .9] army tank | dome [1.6 1.6 .9] |
  rocket [.6 .6 3] | flag [.4 .1 1.8] | torch [.12 .12 1.3] | well [.8 .8 1] | cart [1 .6 .6] | log [1.2 .3 .3] | stump | mushroom |
  hut [1.4 1.2 1.4] | house [1.8 1.4 2.2] cottage with a roof | tower [1 1 3.4] castle tower | wallc [2.4 .4 1.4] castle wall |
  snowman | parasol [.9 .9 1.4] | crop [2 1.6 .25] field rows | ship [1.1 3 1] sailing ship | fountain [1.2 1.2 .9] | dune [2.4 2 .7] |
  stall [1.2 .8 1.5] market stall | statue [.6 .6 2] | iceberg | lighthouse [.9 .9 4] | windmill [1 1 2.6] | temple [2.4 2.4 2].
  Optional "col": char0 char1 graph graph2 steel steel2 silver silver2 bronze brass gold champ pale ember olive olive2 red.
  ANIMALS (optional, 0 to 4): [[species, x, y, act]] - species dog cat horse cow sheep pig goat chicken duck fox wolf deer rabbit bear
  lion tiger elephant giraffe zebra monkey camel owl eagle parrot penguin pigeon fish frog snake turtle; act idle|walk|sit|sleep|eat.
FLOOR: tile|wood|carpet|concrete|grass|sand|water|mud|snow|dirt|cobble|moon|ice|leaf|deck. WALLS: both|back|left|none (outdoors: none). wallH 2.2 to 3.
STATIONS ("st"): 3 to 5 named spots where the main character stands to act: {"name": [[x, y], dir, [fx, fy, fz]]}. The spot is on
open floor (at least .3 away from every prop), [fx, fy, fz] is the point they look at (the prop and its height), dir 1 = facing
right on screen, -1 = facing left. Always add "center": [[x, y], 1, null] in the open front area.
GUESTS: 3 to 4 open-floor spots [x, y] for other people (not on a station, not on a prop).
REGULARS: 0 to 2 people who belong there: [guestIndex, pose, look] - pose stand|explain|type|think|listen|celebrate|wave; look
{"gender": "man|woman|child", "outfit": "blazer|suit|dress|labcoat|apron|hoodie|sweater", "color": "graphite|steel|silver|bronze|champagne|gold|charcoal",
"skin": "light|medium|tan|deep", "hair": "short|long|bun|curly|bald|ponytail"}.
Use 6 to 16 props. The place must be instantly recognisable.
EXAMPLE (a hospital ward):
EXAMPLE_KIT
Reply JSON: {"id": "snake_case", "name": "...", "about": "what stories it fits, one line", "tags": [6 to 12 single words],
"floor": "...", "walls": "...", "wallH": 2.6, "props": [...], "st": {...}, "guests": [...], "regulars": [...], "animals": [...]}
The place belongs to this WORLD: WORLD_LINE - use its scenery and floor."""


def _minted_props():
    """Scenery designed by MOTION MINT (kelp, coral, clam…) - places may use it like a built-in prop."""
    try:
        import motion_mint
        return motion_mint.library("props")
    except Exception:
        return {}


def _costume(world):
    """What people wear in this world (a minted world's walkers / hero, else the wizard's per-world dress) → applied to regulars."""
    try:
        import motion_mint
        from motion_wizard import HERO_BY_WORLD
        mw = motion_mint.library("worlds").get(world) or {}
        return dict(HERO_BY_WORLD.get(world) or HERO_BY_WORLD.get(mw.get("base"), {}) if not mw else ((mw.get("o") or {}).get("walk") or {}).get("look") or mw.get("hero") or {})
    except Exception:
        return {}


def ask_json(prompt, system, ask):
    from motion_wizard import _ask_json          # same brain as the writer (Claude first, then the local engine)
    return _ask_json(prompt, system, ask)


def design(mg, pk, ask, world="city"):
    lib, world = library(mg), world if world in WORLDS else "city"
    ex = lib.get("hospital_ward") or next(iter(lib.values()), None)
    ex_txt = json.dumps({k: ex[k] for k in ("id", "name", "floor", "walls", "props", "st", "guests", "regulars") if k in ex}) if ex else "(none)"
    want = re.sub(r"[^a-z0-9_]", "", str(pk.get("new") or pk.get("id") or pk.get("name") or "place").lower().replace(" ", "_"))[:24]
    prompt = "Design this place: %s\nid: %s\nWhat it is for: %s\nWhat is in it: %s" % (pk.get("name") or want, want, pk.get("about") or "", pk.get("look") or "")
    mp = _minted_props()
    if mp:
        prompt += "\nEXTRA SCENERY props for this world (use them by id like any prop, w/d/h in tiles): " + "; ".join(
            "%s (%s, w%s d%s h%s)" % (k, v.get("name", k), v.get("w", 1), v.get("d", 1), v.get("h", 1)) for k, v in mp.items())
        prompt += "\nOnly use props that really exist in this world (no palm trees under the sea, no desks on the moon)."
    raw = ask_json(prompt, KIT_SYS.replace("EXAMPLE_KIT", ex_txt).replace("WORLD_LINE", "%s (%s)" % (WORLDS[world][0], WORLDS[world][1])), ask)
    raw["id"] = want or raw.get("id")
    raw.setdefault("name", pk.get("name"))
    raw.setdefault("about", pk.get("about"))
    kit = sanitize(raw, set(lib) | set(BUILTIN))
    kit.update(source="generated", created=time.strftime("%Y-%m-%d"), world=world)
    cos = _costume(world)
    for r in kit.get("regulars") or []:                   # the people who belong here dress for this world (divers, astronauts…)
        r[2].update({k: v for k, v in cos.items() if k in ("outfit", "hat", "color")})
    with open(os.path.join(kits_dir(mg), kit["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(kit, f, indent=1)
    return kit


def _num(v, d, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = d
    return round(min(hi, max(lo, v)), 2)


def sanitize(raw, taken=()):
    """Make a designed kit safe for the engine: known types/colors only, everything inside the floor, people on open floor."""
    kid = re.sub(r"[^a-z0-9_]", "", str(raw.get("id") or "place").lower())[:24] or "place"
    if not kid[0].isalpha():
        kid = "p_" + kid
    base, n = kid, 2
    while kid in taken:
        kid, n = "%s_%d" % (base[:21], n), n + 1
    floor = raw.get("floor") if raw.get("floor") in FLOORS else "tile"
    walls = raw.get("walls") if raw.get("walls") in WALLS else ("none" if floor in ("grass", "sand", "water") else "both")
    props = []
    for p in raw.get("props") or []:
        if not isinstance(p, dict) or (p.get("t") not in PROPS and p.get("t") not in _minted_props()) or len(props) >= 18:
            continue
        q = {"t": p["t"]}
        wall = p.get("wall") if p.get("wall") in ("back", "left") else None
        if p["t"] in WALL_ONLY and not wall:
            continue
        if wall and walls != "none" and p["t"] in ("screen",) + WALL_ONLY:
            q["wall"] = wall
            q["w"] = _num(p.get("w"), 1.2, .3, 3.8)
            key = "y" if wall == "left" else "x"
            q[key] = _num(p.get(key), .3, .05, 4 - q["w"] - .05)
            q["z"] = _num(p.get("z"), 1.0, .1, 2.2)
            q["h"] = _num(p.get("h"), .8, .2, 1.8)
        elif wall:
            continue
        else:
            for k, d, lo, hi in (("w", None, .05, 3.8), ("d", None, .05, 3.8), ("h", None, 0, 3.2)):
                if p.get(k) is not None:
                    q[k] = _num(p[k], .8, lo, hi)
            q["x"] = _num(p.get("x"), 1, .05, 3.9 - q.get("w", .3))
            q["y"] = _num(p.get("y"), 1, .05, 3.9 - q.get("d", .3))
            if p.get("z") is not None:
                q["z"] = _num(p["z"], 0, 0, 2.6)
        if p.get("col") in COLS:
            q["col"] = p["col"]
        if p["t"] == "patch":
            q["kind"] = p.get("kind") if p.get("kind") in FLOORS else "grass"
        props.append(q)
    DEF = {"bed": (1.9, 1), "table": (1.2, .8), "desk": (1.1, .6), "counter": (2, .6), "shelf": (1.2, .4), "rack": (.6, .6), "machine": (1, .8), "console": (1.4, .6),
           "tank": (.8, .8), "car": (.7, 1.6), "boat": (.9, 2.2), "stage": (2, 1.2), "sofa": (1.4, .6), "bench": (1, .35), "box": (.8, .8), "tree": (.8, .8)}
    feet = [(p["x"], p["y"], p["x"] + p.get("w", DEF.get(p["t"], (.4, .4))[0]), p["y"] + p.get("d", DEF.get(p["t"], (.4, .4))[1]))
            for p in props if "wall" not in p and p["t"] not in ("patch", "court", "light", "pipe", "rail")]
    used = []

    def free(x, y):
        return all(not (a - .28 < x < c + .28 and b - .28 < y < d + .28) for a, b, c, d in feet) and all(abs(x - u) + abs(y - v) > .7 for u, v in used)

    def near(x, y):
        if free(x, y):
            return x, y
        cands = [(i / 10, j / 10) for i in range(4, 37) for j in range(4, 37) if free(i / 10, j / 10)]
        return min(cands, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2) if cands else (x, y)

    st = {}
    for name, s in list((raw.get("st") or {}).items())[:6]:
        nm = re.sub(r"[^a-z0-9_]", "", str(name).lower())[:14]
        if not nm or not isinstance(s, list) or not s or not isinstance(s[0], list) or len(s[0]) < 2:
            continue
        x, y = near(_num(s[0][0], 2, .35, 3.65), _num(s[0][1], 2, .35, 3.65))
        used.append((x, y))
        fo = s[2] if len(s) > 2 and isinstance(s[2], list) and len(s[2]) >= 3 else None
        st[nm] = [[round(x, 2), round(y, 2)], -1 if len(s) > 1 and s[1] == -1 else 1, [_num(fo[0], 2, 0, 4), _num(fo[1], 2, 0, 4), _num(fo[2], 1, 0, 3)] if fo else None]
    if "center" not in st:
        x, y = near(2.6, 2.9)
        used.append((x, y))
        st["center"] = [[round(x, 2), round(y, 2)], 1, None]
    guests = []
    for g in raw.get("guests") or []:
        if isinstance(g, list) and len(g) >= 2 and len(guests) < 5:
            x, y = near(_num(g[0], 2, .3, 3.7), _num(g[1], 2, .3, 3.7))
            used.append((x, y))
            guests.append([round(x, 2), round(y, 2)])
    for x0, y0 in ((3.3, 1.4), (1.4, 3.3), (3.4, 3.2)):
        if len(guests) >= 3:
            break
        x, y = near(x0, y0)
        used.append((x, y))
        guests.append([round(x, 2), round(y, 2)])
    look_keys = {"gender": ["man", "woman", "child"], "outfit": ["blazer", "suit", "dress", "labcoat", "apron", "hoodie", "sweater", "tshirt", "jersey", "scrubs",
                 "uniform", "chef", "overalls", "coat", "robe", "military", "space", "gown"], "hat": ["helmet", "hardhat", "cap", "chef", "police", "beanie", "tophat", "crown", "cowboy", "grad", "bubble"],
                 "color": ["graphite", "steel", "silver", "bronze", "champagne", "gold", "charcoal", "olive", "teal", "navy", "ember", "white"], "skin": ["light", "medium", "tan", "deep"],
                 "hair": ["short", "long", "bun", "curly", "bald", "ponytail"], "age": ["young", "adult", "older"]}
    regs = []
    for r in raw.get("regulars") or []:
        if isinstance(r, list) and len(r) >= 3 and isinstance(r[0], int) and 0 <= r[0] < len(guests) and len(regs) < 2:
            lk = r[2] if isinstance(r[2], dict) else {}
            regs.append([r[0], r[1] if r[1] in POSES or r[1] in _acts() else "stand", {k: lk[k] for k in look_keys if lk.get(k) in look_keys[k]}])
    animals = [[a[0], _num(a[1], 2, .3, 3.7), _num(a[2], 2, .3, 3.7), a[3] if len(a) > 3 and a[3] in ("idle", "walk", "sit", "sleep", "eat", "run") else "idle"]
               for a in (raw.get("animals") or []) if isinstance(a, list) and len(a) >= 3 and a[0] in _species()][:4]
    tags = [w for w in (re.sub(r"[^a-z ]", "", str(t).lower()).strip() for t in raw.get("tags") or []) if w][:14]
    return {"id": kid, "name": str(raw.get("name") or kid.replace("_", " ").title())[:40], "about": str(raw.get("about") or "")[:160], "tags": tags,
            "floor": floor, "walls": walls, "wallH": _num(raw.get("wallH"), 2.6, 2.2, 3), "props": props, "st": st, "guests": guests, "regulars": regs, "animals": animals}


def _acts():
    import motion_library
    return motion_library.vocab().get("acts", {})


def _species():
    import motion_library
    return motion_library.vocab().get("species", {})


# ── the film's places ──
def places(mg, ids=None, world="city"):
    """{place: [stations]} - the six (in the city, or always when ids is None, for validation), plus the given library kits
    (all of them when ids is None)."""
    from motion_wizard import DIO_PLACES
    lib = library(mg)
    out = dict(DIO_PLACES) if (ids is None or world == "city" or world not in WORLDS) else {}
    for k in (lib.values() if ids is None else [lib[i] for i in ids if i in lib]):
        out[k["id"]] = list((k.get("st") or {}).keys())
    return out


def table(mg, ids, world="city"):
    """The place table for the writer: the six (city films only) + this film's places, with their spots and what they are for."""
    from motion_wizard import DIO_PLACES
    lib = library(mg)
    rows = ["  %s: %s   (%s)" % (k, " | ".join(v), BUILTIN[k]) for k, v in DIO_PLACES.items()] if world == "city" or world not in WORLDS else []
    rows += ["  %s: %s   (%s)" % (i, " | ".join((lib[i].get("st") or {}).keys()), lib[i].get("about") or lib[i].get("name")) for i in ids or [] if i in lib]
    return "\n".join(rows)


def for_project(mg, beats):
    """The kits a film's beats use, each with its city slot (origin + door), in order of first appearance."""
    lib, out = library(mg), []
    for b in beats:
        pl = b.get("place")
        if pl in lib and pl not in [k["id"] for k in out] and len(out) < len(SLOTS):
            i, j = SLOTS[len(out)]
            k = {x: v for x, v in lib[pl].items() if x in ("id", "name", "floor", "walls", "wallH", "props", "st", "guests", "regulars", "animals", "world")}
            k.update(o=[i * 4, j * 4], door=[i * 4 + 3.5, j * 4 + 3.5])
            out.append(k)
    return out
