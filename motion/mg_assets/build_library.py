"""MOTION LIBRARY builder (Oct 29 2026) - the ONE library the Motion Studio (Diorama + Explainer) and MIR EXPLAINED share.

  python -I mg_assets/build_library.py            vocab.json + characters.json + every thumbnail
  python -I mg_assets/build_library.py --vocab    vocab only (seconds)

vocab.json is dumped straight from the engine (src/mg/dio_lib.ts + diorama_engine.ts), so the server never drifts from what the
renderer can draw. Thumbnails are drawn by the same engine in headless Edge (canvas → webp) into public/mg/library/thumbs/."""
import base64
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "public", "mg", "library")
THUMBS = os.path.join(LIB, "thumbs")
KITS = os.path.join(ROOT, "public", "mg", "diorama_kits")
ESBUILD = os.path.join(ROOT, "node_modules", ".bin", "esbuild.cmd" if os.name == "nt" else "esbuild")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# ready-made characters: a look + what they usually do. ids are stable (the editors and the writer reference them).
CHARACTERS = [
    ("doctor", "Doctor", "medicine, hospitals", {"gender": "woman", "outfit": "labcoat", "hair": "bun", "skin": "medium", "glasses": True}, "explain"),
    ("nurse", "Nurse", "care, hospitals", {"gender": "woman", "outfit": "scrubs", "hair": "ponytail", "skin": "deep"}, "stand"),
    ("surgeon", "Surgeon", "operations", {"gender": "man", "outfit": "scrubs", "hat": "cap", "skin": "light"}, "think"),
    ("scientist", "Scientist", "labs, discoveries", {"gender": "man", "outfit": "labcoat", "hair": "bald", "age": "older", "glasses": True, "skin": "tan"}, "point"),
    ("engineer", "Engineer", "building, machines", {"gender": "woman", "outfit": "overalls", "hat": "hardhat", "skin": "tan"}, "build"),
    ("builder", "Construction worker", "sites, building", {"gender": "man", "outfit": "overalls", "hat": "hardhat", "skin": "deep", "beard": True}, "carry"),
    ("police", "Police officer", "law, safety", {"gender": "man", "outfit": "uniform", "hat": "police", "skin": "medium"}, "hips"),
    ("firefighter", "Firefighter", "rescue, fire", {"gender": "man", "outfit": "coat", "color": "ember", "hat": "hardhat", "skin": "light"}, "pull"),
    ("soldier", "Soldier", "war, the army", {"gender": "man", "outfit": "military", "hat": "helmet", "skin": "tan"}, "soldier"),
    ("general", "General", "command, strategy", {"gender": "man", "outfit": "military", "hat": "police", "age": "older", "beard": True}, "salute"),
    ("pilot", "Pilot", "planes, flying", {"gender": "woman", "outfit": "uniform", "hat": "police", "hair": "bun", "skin": "light"}, "fly"),
    ("astronaut", "Astronaut", "space, the moon", {"gender": "man", "outfit": "space", "skin": "medium"}, "wave"),
    ("chef", "Chef", "kitchens, food", {"gender": "man", "outfit": "chef", "skin": "light", "beard": True}, "cook"),
    ("waiter", "Barista / waiter", "cafes, service", {"gender": "woman", "outfit": "apron", "color": "champagne", "hair": "ponytail", "skin": "medium"}, "give"),
    ("teacher", "Teacher", "school, lessons", {"gender": "woman", "outfit": "sweater", "color": "bronze", "glasses": True, "skin": "light"}, "present"),
    ("student", "Student", "school, studying", {"gender": "child", "outfit": "hoodie", "color": "steel", "skin": "deep"}, "read"),
    ("kid", "Kid", "children, family", {"gender": "child", "outfit": "tshirt", "color": "gold", "hair": "curly", "skin": "tan"}, "jump"),
    ("teen", "Teenager", "youth, phones", {"gender": "man", "outfit": "hoodie", "color": "charcoal", "hair": "spiky", "skin": "light"}, "text"),
    ("mom", "Mom", "family, home", {"gender": "woman", "outfit": "sweater", "color": "champagne", "hair": "long", "skin": "medium"}, "phone"),
    ("dad", "Dad", "family, home", {"gender": "man", "outfit": "sweater", "color": "steel", "skin": "tan", "beard": True}, "hug"),
    ("grandma", "Grandma", "family, wisdom", {"gender": "woman", "outfit": "dress", "color": "bronze", "hair": "bun", "age": "older", "glasses": True, "skin": "light"}, "sit"),
    ("grandpa", "Grandpa", "family, memories", {"gender": "man", "outfit": "coat", "color": "graphite", "hair": "bald", "age": "older", "skin": "deep"}, "think"),
    ("ceo", "CEO", "business, money", {"gender": "woman", "outfit": "suit", "color": "charcoal", "hair": "bun", "skin": "light"}, "present"),
    ("businessman", "Businessman", "deals, offices", {"gender": "man", "outfit": "suit", "skin": "medium"}, "handshake"),
    ("programmer", "Programmer", "code, tech", {"gender": "man", "outfit": "hoodie", "color": "graphite", "glasses": True, "skin": "tan"}, "sitdesk"),
    ("reporter", "Reporter", "news, TV", {"gender": "woman", "outfit": "blazer", "color": "gold", "hair": "long", "skin": "deep"}, "sing"),
    ("judge", "Judge", "courts, law", {"gender": "man", "outfit": "robe", "age": "older", "glasses": True, "skin": "light"}, "think"),
    ("lawyer", "Lawyer", "courts, cases", {"gender": "woman", "outfit": "suit", "color": "graphite", "hair": "ponytail", "skin": "medium"}, "point"),
    ("farmer", "Farmer", "farms, harvest", {"gender": "man", "outfit": "overalls", "hat": "cowboy", "skin": "tan", "beard": True}, "dig"),
    ("athlete", "Footballer", "soccer, sport", {"gender": "man", "outfit": "jersey", "num": "10", "skin": "deep"}, "kick"),
    ("runner", "Runner", "races, fitness", {"gender": "woman", "outfit": "jersey", "num": "7", "hair": "ponytail", "skin": "medium"}, "run"),
    ("boxer", "Boxer", "fights, training", {"gender": "man", "outfit": "tshirt", "color": "ember", "hair": "bald", "skin": "tan"}, "box"),
    ("king", "King", "kingdoms, history", {"gender": "man", "outfit": "robe", "color": "gold", "hat": "crown", "beard": True, "age": "older"}, "explain"),
    ("queen", "Queen", "kingdoms, history", {"gender": "woman", "outfit": "gown", "hat": "crown", "hair": "long", "skin": "light"}, "wave"),
    ("knight", "Knight", "castles, battles", {"gender": "man", "outfit": "military", "color": "steel", "hat": "helmet"}, "sword"),
    ("pirate", "Pirate", "ships, treasure", {"gender": "man", "outfit": "coat", "color": "bronze", "hat": "tophat", "beard": True}, "point"),
    ("explorer", "Explorer", "jungles, expeditions", {"gender": "woman", "outfit": "tshirt", "color": "olive", "hat": "cowboy", "skin": "tan"}, "look"),
    ("detective", "Detective", "mysteries, clues", {"gender": "man", "outfit": "coat", "color": "champagne", "hat": "tophat"}, "search"),
    ("artist", "Artist", "painting, studios", {"gender": "woman", "outfit": "apron", "color": "steel", "hair": "afro", "skin": "deep"}, "paint"),
    ("musician", "Musician", "music, stages", {"gender": "man", "outfit": "tshirt", "color": "charcoal", "hair": "long", "skin": "light"}, "guitar"),
    ("driver", "Driver", "cars, deliveries", {"gender": "man", "outfit": "tshirt", "color": "navy", "hat": "cap", "skin": "medium"}, "drive"),
    ("graduate", "Graduate", "school, success", {"gender": "woman", "outfit": "robe", "hat": "grad", "hair": "long", "skin": "tan"}, "cheer"),
    ("villager", "Villager", "medieval towns", {"gender": "woman", "outfit": "apron", "color": "bronze", "hair": "braids", "skin": "light"}, "carry"),
    ("camper", "Camper", "forests, camping", {"gender": "man", "outfit": "coat", "color": "olive", "hat": "beanie", "beard": True}, "campfire"),
]

ENTRY = r"""
import * as L from '%(lib)s';
import * as E from '%(eng)s';
import * as X from '%(vfx)s';
const acts = Object.fromEntries(L.ACT_NAMES.map((k) => [k, {cat: L.ACTS[k].cat, desc: L.ACTS[k].desc}]));
const species = Object.fromEntries(L.SPECIES_NAMES.map((k) => [k, {name: L.SPECIES[k].name, type: L.SPECIES[k].type, tags: L.SPECIES[k].tags || ''}]));
const worlds = Object.fromEntries(E.WORLD_IDS.map((k) => [k, {name: E.WORLDS[k].name, about: E.WORLDS[k].about}]));
console.log(JSON.stringify({acts, act_cats: L.ACT_CATS, species, animal_acts: L.ANIMAL_ACTS, items: L.ITEM_NAMES, rides: L.RIDE_NAMES, pieces: L.PIECE_NAMES, hats: L.HAT_NAMES,
	ambients: L.AMBIENTS, vfx: Object.fromEntries(X.VFX_NAMES.map((k) => [k, {desc: X.VFX[k].desc, once: X.VFX[k].once || 0}])), looks: E.LOOK_VOCAB, worlds, props: E.PROP_TYPES, floors: Object.keys(E.FLOOR_KINDS), places: E.PLACES}));
"""


def vocab():
    tmp = tempfile.mkdtemp()
    src, out = os.path.join(tmp, "entry.ts"), os.path.join(tmp, "entry.cjs")
    fw = lambda p: p.replace("\\", "/")
    open(src, "w", encoding="utf-8").write(ENTRY % {"lib": fw(os.path.join(ROOT, "src", "mg", "dio_lib.ts")), "eng": fw(os.path.join(ROOT, "src", "mg", "diorama_engine.ts")), "vfx": fw(os.path.join(ROOT, "src", "mg", "dio_vfx.ts"))})
    subprocess.run([ESBUILD, src, "--bundle", "--format=cjs", "--platform=node", "--outfile=" + out, "--log-level=warning"], check=True, cwd=ROOT)
    v = json.loads(subprocess.run(["node", out], capture_output=True, text=True, check=True, cwd=ROOT).stdout)
    os.makedirs(LIB, exist_ok=True)
    json.dump(v, open(os.path.join(LIB, "vocab.json"), "w", encoding="utf-8"), indent=0)
    chars = [{"id": i, "name": n, "role": r, "look": lk, "act": a} for i, n, r, lk, a in CHARACTERS]
    json.dump(chars, open(os.path.join(LIB, "characters.json"), "w", encoding="utf-8"), indent=1)
    json.dump({c["id"]: {"look": c["look"], "act": c["act"]} for c in chars}, open(os.path.join(ROOT, "src", "mg", "lib_chars.json"), "w", encoding="utf-8"))   # DioItem's resolver
    print("vocab: %d acts · %d species · %d items · %d worlds · %d characters" % (len(v["acts"]), len(v["species"]), len(v["items"]), len(v["worlds"]), len(chars)))
    return v, chars


def kits():
    out = {}
    for f in glob.glob(os.path.join(KITS, "*.json")):
        try:
            k = json.load(open(f, encoding="utf-8"))
            if k.get("id"):
                out[k["id"]] = k
        except Exception:
            pass
    return out


def thumbs(v, chars, only=None):
    tmp = tempfile.mkdtemp()
    js = os.path.join(tmp, "dio.js")
    subprocess.run([ESBUILD, os.path.join(ROOT, "src", "mg", "diorama_engine.ts"), "--bundle", "--format=iife", "--global-name=DIO", "--outfile=" + js, "--log-level=warning"], check=True, cwd=ROOT)
    K = kits()
    jobs = [("act_" + a, {"type": "act", "act": a}) for a in v["acts"]]
    jobs += [("animal_" + a, {"type": "animal", "kind": a, "act": "idle"}) for a in v["species"]]
    jobs += [("char_" + c["id"], {"type": "char", "look": c["look"], "act": c["act"]}) for c in chars]
    jobs += [("obj_" + i, {"type": "obj", "name": i}) for i in v["items"]]
    jobs += [("vfx_" + i, {"type": "vfx", "kind": i}) for i in v.get("vfx", {})]
    jobs += [("prop_" + i, {"type": "prop", "id": i}) for i in v["props"] if i not in ("patch", "court", "board", "window")]
    jobs += [("place_" + p, {"type": "place", "id": p}) for p in v["places"]]
    jobs += [("place_" + k, {"type": "place", "id": k, "kit": K[k]}) for k in K]
    worlds = {w: next((k for k in K.values() if k.get("world") == w), None) for w in v["worlds"]}
    jobs += [("world_" + w, {"type": "world", "world": w, "kit": kv}) for w, kv in worlds.items()]
    if only:
        jobs = [j for j in jobs if re.search(only, j[0])]
    page = """<!doctype html><meta charset="utf-8"><body><pre id="out"></pre><script src="dio.js"></script><script>
const JOBS = %s, out = {};
for (const [name, it] of JOBS) {const cv = document.createElement('canvas'), w = it.type === 'world' ? 480 : 256, h = it.type === 'world' ? 270 : 256; cv.width = w; cv.height = h; const c = cv.getContext('2d');
	try {if (it.type === 'world') {const kit = it.kit ? {...it.kit, o: [12, 8]} : null; DIO.drawDiorama(c, w, h, 3, {world: it.world, kits: kit ? [kit] : [], cast: [], words: [], captions: false,
			beats: [{t0: 0, t1: 9, place: kit ? kit.id : 'street', station: kit ? Object.keys(kit.st)[0] : 'center', pose: 'stand', camera: 'aerial'}]});}
		else DIO.drawLibItem(c, w, h, 1.3, it); out[name] = cv.toDataURL('image/webp', .86);} catch (e) {out[name] = 'ERR ' + e.message;}}
document.getElementById('out').textContent = JSON.stringify(out);
</script>""" % json.dumps(jobs)
    html = os.path.join(tmp, "thumbs.html")
    open(html, "w", encoding="utf-8").write(page)
    r = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=60000", "--dump-dom", "file:///" + html.replace("\\", "/")],
                       capture_output=True, text=True, timeout=600, encoding="utf-8", errors="ignore")
    m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
    if not m:
        raise SystemExit("thumbnail page produced nothing:\n" + r.stdout[-500:] + r.stderr[-500:])
    import html as H
    got = json.loads(H.unescape(m.group(1)))
    os.makedirs(THUMBS, exist_ok=True)
    bad = 0
    for name, data in got.items():
        if not str(data).startswith("data:image"):
            print("  ✗", name, str(data)[:120])
            bad += 1
            continue
        open(os.path.join(THUMBS, name + ".webp"), "wb").write(base64.b64decode(data.split(",", 1)[1]))
    print("thumbnails: %d written, %d failed -> %s" % (len(got) - bad, bad, THUMBS))


if __name__ == "__main__":
    v, chars = vocab()
    if "--vocab" not in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
        thumbs(v, chars, only)
