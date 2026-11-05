"""Seed place kits for the Diorama WORLDS (Oct 29 2026, user: "the videos need other places than just the city").
Each kit carries "world" (diorama_engine.ts WORLDS: countryside forest beach desert snow war moon medieval jungle ocean); the
location scout prefers kits of the film's world. Re-run to rewrite these seed files; generated kits are never touched.
Coordinates: inside the 4x4 floor, origin = the back corner (as in _seed_kits.py)."""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def K(**kw):
    return kw


def P(t, x=0, y=0, **o):
    return dict(t=t, x=x, y=y, **o)


KITS = [
    # ── countryside ──
    K(id="wheat_field", world="countryside", name="Wheat field", about="open farmland with crops, a fence, hay bales and a windmill - farming, harvest, hard work, rural life",
      tags=["farm", "field", "harvest", "crops", "wheat", "farmer", "rural", "countryside", "village", "tractor"], floor="dirt", walls="none",
      props=[P("crop", .2, .2, w=2.4, d=1.6), P("windmill", 3.0, .2), P("hay", 2.9, 2.0), P("hay", 3.3, 2.6), P("fence", 0, 3.85, w=4), P("cart", .4, 2.5)],
      st={"field": [[1.4, 2.1], -1, [1.2, 1.0, .3]], "windmill": [[2.9, 1.4], -1, [3.4, .6, 1.8]], "hay": [[2.6, 2.9], 1, [3.1, 2.3, .5]], "cart": [[1.4, 3.2], -1, [.9, 2.8, .6]], "center": [[2.2, 3.4], 1, None]},
      guests=[[1.0, 1.9], [2.4, 2.0], [3.2, 3.3], [.6, 3.5]], regulars=[[0, "dig", {"gender": "man", "outfit": "overalls", "hat": "cowboy", "skin": "tan"}]],
      animals=[["cow", 3.4, 3.3, "eat"], ["chicken", .6, 1.9, "eat"], ["chicken", .9, 2.1, "walk"]]),
    K(id="farmhouse", world="countryside", name="Farmhouse kitchen", about="a warm farmhouse kitchen with a wooden table, a stove and a window on the fields - family, home cooking, mornings",
      tags=["farmhouse", "kitchen", "home", "family", "grandma", "breakfast", "cook", "cooking", "dinner", "rural"], floor="wood", walls="both",
      props=[P("counter", .3, .2, w=2.0, d=.55, col="bronze"), P("machine", 2.5, .2, w=.8, d=.6, h=1.0, col="steel"), P("window", wall="left", y=1.0, w=1.6), P("table", 1.2, 1.8, w=1.4, d=.9, col="brass"),
             P("chair", 1.0, 2.9), P("chair", 2.4, 2.9), P("shelf", 3.4, 1.4, w=.45, d=.4, h=1.6), P("plant", 3.5, 3.4), P("light", 1.9, 2.2, z=2.2)],
      st={"stove": [[2.9, 1.2], -1, [2.9, .5, 1.1]], "table": [[1.9, 3.1], -1, [1.9, 2.2, .8]], "window": [[.7, 1.8], -1, [0, 1.8, 1.4]], "counter": [[1.3, 1.1], -1, [1.3, .5, 1.1]], "center": [[2.8, 2.6], 1, None]},
      guests=[[1.0, 2.6], [2.6, 2.4], [3.3, 2.9], [1.4, 3.6]], regulars=[[1, "cook", {"gender": "woman", "outfit": "apron", "age": "older", "hair": "bun", "skin": "light"}]],
      animals=[["cat", 3.3, 3.5, "sleep"]]),
    # ── forest ──
    K(id="campsite", world="forest", name="Forest campsite", about="a campsite in a pine forest at night: a tent, a campfire, logs to sit on, a lantern - camping, stories, survival, friends",
      tags=["camp", "camping", "campfire", "tent", "forest", "woods", "night", "survival", "scouts", "hike", "wilderness"], floor="leaf", walls="none",
      props=[P("tent", .3, .3, col="olive2"), P("campfire", 1.9, 1.9), P("log", 1.2, 2.6, w=1.2, d=.3), P("log", 2.7, 1.5, w=.3, d=1.0), P("pine", 3.2, .2, w=.8, h=2.6), P("pine", .2, 3.1, w=.7, h=2.2),
             P("stump", 3.3, 3.2), P("mushroom", .6, 2.2), P("barrel", 1.9, .4, col="bronze")],
      st={"fire": [[2.0, 2.7], -1, [2.2, 2.2, .4]], "tent": [[1.1, 1.8], -1, [1.0, .9, .8]], "log": [[1.8, 3.2], -1, [1.8, 2.75, .3]], "trees": [[3.0, 1.0], 1, [3.6, .6, 1.8]], "center": [[2.8, 3.0], 1, None]},
      guests=[[1.2, 2.9], [3.0, 2.2], [2.6, 3.4], [.8, 2.6]], regulars=[[1, "campfire", {"gender": "man", "outfit": "coat", "color": "olive", "beard": True}]],
      animals=[["owl", 3.4, .5, "idle"], ["rabbit", .5, 3.5, "eat"]]),
    K(id="forest_cabin", world="forest", name="Log cabin", about="a cosy wooden cabin in the woods: fireplace, bed, table, window to the trees - hiding away, writing, winter nights, mystery",
      tags=["cabin", "woods", "lodge", "fireplace", "hideout", "retreat", "writer", "mystery", "hunter"], floor="wood", walls="both", wallH=2.4,
      props=[P("bed", .25, .25, w=1.7, d=.9, col="bronze"), P("campfire", 3.0, .3), P("table", 1.4, 1.9, w=1.0, d=.8, col="brass"), P("chair", 1.2, 2.8), P("window", wall="left", y=1.4, w=1.3),
             P("shelf", 3.4, 1.5, w=.45, d=.4, h=1.5), P("barrel", 3.4, 3.2), P("light", 1.9, 2.3, z=2.0)],
      st={"bed": [[1.2, 1.5], 1, [1.0, .7, .6]], "fire": [[2.9, 1.2], -1, [3.3, .6, .5]], "table": [[2.0, 3.0], -1, [1.9, 2.3, .8]], "window": [[.6, 2.1], -1, [0, 2.0, 1.4]], "center": [[2.7, 2.6], 1, None]},
      guests=[[2.4, 2.0], [1.0, 3.1], [3.2, 2.4]], regulars=[], animals=[["dog", 3.0, 2.0, "sleep"]]),
    K(id="river_bank", world="forest", name="River bank", about="a forest river with rocks, reeds and a fallen log bridge - fishing, crossing, nature, calm, danger in the water",
      tags=["river", "stream", "fishing", "water", "bridge", "nature", "forest", "crossing", "bear", "salmon"], floor="grass", walls="none",
      props=[P("patch", .0, 1.3, kind="water", w=4, d=1.3), P("log", .6, 1.2, w=.3, d=1.5), P("rock", 2.4, 1.6), P("rock", 3.2, 2.0, w=.5), P("pine", .3, .2, w=.8, h=2.4), P("pine", 3.1, .3, w=.8, h=2.2),
             P("bush", 1.6, 3.2), P("stump", 3.3, 3.3)],
      st={"shore": [[2.0, 3.0], -1, [2.0, 2.2, .1]], "log": [[.75, 3.0], -1, [.75, 1.9, .3]], "rocks": [[2.9, 2.9], -1, [2.6, 1.8, .4]], "trees": [[1.5, .9], 1, [.7, .6, 1.6]], "center": [[2.4, 3.5], 1, None]},
      guests=[[1.2, 3.4], [3.0, 3.6], [1.6, .9]], animals=[["fish", 1.8, 1.9, "swim"], ["deer", 2.8, .9, "eat"], ["frog", 3.0, 2.7, "idle"]]),
    # ── beach ──
    K(id="beach_shore", world="beach", name="Beach", about="a sunny beach: sand, waves, parasols, towels, a lifeguard tower and palms - holidays, summer, swimming, freedom",
      tags=["beach", "sea", "ocean", "summer", "holiday", "vacation", "swim", "surf", "sand", "coast", "waves", "sun"], floor="sand", walls="none",
      props=[P("patch", .0, .0, kind="water", w=4, d=1.2), P("parasol", 1.3, 1.9, col="gold"), P("patch", 1.0, 2.3, kind="tile", w=.5, d=1.0), P("parasol", 2.8, 2.6, col="ember"), P("palm", .3, 3.0, h=2.6),
             P("tower", 3.3, 1.4, w=.5, d=.5, h=1.6, col="silver"), P("crate", 2.2, 3.4, w=.4, d=.4, h=.3)],
      st={"water": [[2.0, 1.4], 1, [2.0, .5, .1]], "parasol": [[1.8, 2.5], -1, [1.3, 1.9, 1.3]], "tower": [[3.0, 2.0], -1, [3.5, 1.6, 1.6]], "palm": [[.9, 3.1], 1, [.5, 3.1, 2]], "center": [[2.4, 3.2], 1, None]},
      guests=[[1.2, 2.8], [2.6, 1.6], [3.4, 3.2], [.8, 1.8]], regulars=[[0, "stand", {"gender": "woman", "outfit": "tshirt", "color": "gold", "skin": "tan"}], [2, "sit", {"gender": "man", "outfit": "tshirt", "color": "teal", "skin": "deep"}]],
      animals=[["pigeon", 2.2, 2.2, "eat"], ["dog", 3.0, 3.5, "run"]]),
    K(id="lighthouse_point", world="beach", name="Lighthouse point", about="a rocky point with a lighthouse over the sea - storms, warnings, keeping watch, lonely nights, ships far out",
      tags=["lighthouse", "storm", "coast", "cliff", "keeper", "ship", "sea", "rocks", "warning", "watch"], floor="concrete", walls="none",
      props=[P("patch", 2.6, .0, kind="water", w=1.4, d=4), P("lighthouse", 1.0, .6), P("rock", 2.3, 1.0, w=.8), P("rock", 2.2, 2.6, w=.7), P("rail", .2, 3.6, w=2.0), P("hut", .3, 2.2, w=1.1, d=1.0, h=1.4)],
      st={"lighthouse": [[1.5, 1.9], -1, [1.4, 1.0, 2.5]], "edge": [[2.0, 3.3], 1, [2.6, 3.3, .1]], "hut": [[1.3, 3.1], -1, [.8, 2.7, .7]], "center": [[1.8, 2.6], 1, None]},
      guests=[[.9, 3.3], [2.0, 2.0], [1.6, 3.6]], animals=[["pigeon", 2.4, 2.3, "idle"]]),
    # ── desert ──
    K(id="oasis", world="desert", name="Desert oasis", about="a palm oasis around a pool in the dunes - thirst, rescue, travellers, caravans, mirages",
      tags=["oasis", "desert", "water", "palm", "caravan", "travel", "camel", "thirst", "mirage", "sand"], floor="sand", walls="none",
      props=[P("patch", 1.1, 1.1, kind="water", w=1.6, d=1.3), P("palm", .5, .5, h=2.6), P("palm", 2.9, .7, h=2.3), P("palm", .6, 2.8, h=2.2), P("tent", 2.6, 2.4, col="champ"), P("barrel", 2.3, 3.5), P("dune", 3.0, .0, w=1.0, h=.5)],
      st={"pool": [[1.9, 2.7], -1, [1.9, 1.7, .1]], "tent": [[2.5, 3.6], -1, [3.2, 2.9, .8]], "palms": [[1.2, 1.0], 1, [.7, .7, 2]], "center": [[1.5, 3.4], 1, None]},
      guests=[[1.0, 2.4], [3.0, 1.9], [1.8, 3.6]], regulars=[[1, "stand", {"gender": "man", "outfit": "robe", "color": "champagne", "skin": "tan", "beard": True}]],
      animals=[["camel", 3.4, 1.4, "idle"]]),
    K(id="desert_road", world="desert", name="Desert highway", about="an empty highway through the desert with a gas pump, a sign and cacti - road trips, breakdowns, the middle of nowhere",
      tags=["road", "highway", "road trip", "desert", "car", "gas", "nowhere", "drive", "route", "breakdown"], floor="sand", walls="none",
      props=[P("patch", .0, 1.5, kind="concrete", w=4, d=1.0), P("car", 1.6, 1.3, w=.7, d=1.6, col="ember"), P("sign", 3.2, .6, h=1.8, col="gold"), P("machine", .4, .4, w=.5, d=.5, h=1.2, col="ember"),
             P("cactus", 3.2, 3.1), P("cactus", .5, 3.3, h=1.0), P("rock", 2.6, 3.4)],
      st={"road": [[2.6, 2.0], 1, [2.5, 2.0, .1]], "car": [[1.3, 2.4], 1, [1.9, 2.0, .7]], "pump": [[.9, 1.2], -1, [.6, .6, 1.0]], "sign": [[3.0, 1.3], -1, [3.2, .6, 1.6]], "center": [[2.0, 3.3], 1, None]},
      guests=[[2.4, 3.0], [3.4, 2.6], [.8, 2.9]], animals=[["snake", 2.8, 3.5, "walk"]]),
    # ── snow ──
    K(id="ski_lodge", world="snow", name="Ski lodge", about="a warm ski lodge with a fireplace, sofas, hot drinks and big windows on the snowy slopes - winter holidays, warming up",
      tags=["ski", "lodge", "winter", "snow", "chalet", "fireplace", "hot chocolate", "holiday", "mountain"], floor="wood", walls="both",
      props=[P("campfire", 2.9, .3), P("sofa", .4, 1.8, w=1.4, d=.6, col="ember"), P("table", .8, 2.7, w=.8, d=.5, col="brass"), P("window", wall="left", y=.4, w=2.6, z=.6, h=1.6),
             P("counter", 1.6, .2, w=1.0, d=.5, col="bronze"), P("shelf", 3.4, 1.6, w=.45, d=.4, h=1.4), P("plant", 3.5, 3.4)],
      st={"fire": [[3.0, 1.3], -1, [3.3, .6, .5]], "sofa": [[1.3, 3.3], -1, [1.1, 2.1, .6]], "window": [[.7, 1.3], -1, [0, 1.6, 1.4]], "bar": [[2.0, 1.2], -1, [2.1, .5, 1.1]], "center": [[2.6, 2.6], 1, None]},
      guests=[[1.8, 2.4], [2.8, 3.2], [3.2, 2.2]], regulars=[[2, "drink", {"gender": "woman", "outfit": "coat", "hat": "beanie", "color": "ember", "skin": "light"}]]),
    K(id="mountain_peak", world="snow", name="Mountain summit", about="a snowy summit with a flag, rocks and a sheer drop - climbing, goals, reaching the top, danger, the view",
      tags=["mountain", "summit", "peak", "climb", "climbing", "everest", "top", "goal", "expedition", "snow"], floor="snow", walls="none",
      props=[P("rock", .4, .4, w=1.0, h=.9), P("rock", 2.6, .3, w=1.2, h=1.2), P("rock", .3, 2.6, w=.9, h=.7), P("flag", 2.0, 1.6, h=1.6, col="ember"), P("tent", 2.7, 2.6, col="ember"), P("pine", 3.5, 3.4, w=.5, h=1.4)],
      st={"flag": [[2.3, 2.2], -1, [2.0, 1.6, 1.4]], "edge": [[1.0, 1.8], -1, [.4, 1.6, .1]], "tent": [[2.6, 3.5], -1, [3.2, 3.0, .8]], "center": [[1.8, 3.0], 1, None]},
      guests=[[1.4, 2.6], [3.2, 1.8], [.9, 3.3]], regulars=[[0, "stretch", {"gender": "woman", "outfit": "coat", "hat": "beanie", "color": "gold"}]]),
    # ── battlefield ──
    K(id="trench_line", world="war", name="Trench", about="a muddy front-line trench with sandbags, barbed wire and smoke - war, soldiers, waiting for the order, fear, courage",
      tags=["war", "trench", "ww1", "ww2", "world war", "soldier", "soldiers", "army", "battle", "front", "frontline", "military", "combat"], floor="mud", walls="none",
      props=[P("patch", .0, 1.6, kind="mud", w=4, d=.9), P("sandbag", .0, 1.25, w=4), P("wire", .2, .4, w=3.6), P("crater", 2.6, 2.7, w=1.0, d=1.0), P("barrel", 3.4, 3.4), P("flag", .4, 3.2, col="olive2"), P("crate", 1.6, 3.2, w=.5, d=.5, h=.4)],
      st={"trench": [[1.8, 2.05], 1, [1.8, 1.3, .5]], "wire": [[2.6, 1.0], 1, [2.0, .45, .4]], "crates": [[1.2, 3.0], -1, [1.8, 3.4, .4]], "center": [[2.4, 3.5], 1, None]},
      guests=[[.8, 2.1], [3.0, 2.0], [2.8, 3.3], [.7, 3.6]], regulars=[[0, "soldier", {"gender": "man", "outfit": "military", "hat": "helmet", "skin": "tan"}], [1, "fire", {"gender": "man", "outfit": "military", "hat": "helmet", "skin": "light"}]]),
    K(id="ruined_town", world="war", name="Ruined town", about="a bombed town street with broken buildings, rubble, a tank and fires - occupation, escape, civilians, liberation",
      tags=["ruins", "bombed", "war", "town", "tank", "rubble", "liberation", "invasion", "escape", "refugee", "civilians"], floor="cobble", walls="none",
      props=[P("ruin", .2, .2, w=1.6, d=1.2, h=2.0), P("ruin", 2.6, .3, w=1.2, d=1.0, h=1.4), P("armor", 2.3, 1.7), P("rock", 1.0, 2.0, w=.6), P("rock", 1.4, 2.4, w=.4), P("crater", .4, 2.9, w=.9, d=.9), P("campfire", 3.4, 3.4)],
      st={"ruins": [[1.2, 1.9], 1, [1.0, .8, 1.4]], "tank": [[1.8, 3.0], 1, [2.9, 2.6, .8]], "rubble": [[.9, 3.3], -1, [1.2, 2.2, .3]], "center": [[2.6, 3.6], 1, None]},
      guests=[[1.4, 3.6], [3.2, 2.0], [.6, 2.3]], regulars=[[1, "march", {"gender": "man", "outfit": "military", "hat": "helmet"}]]),
    K(id="field_hospital", world="war", name="Field hospital", about="a canvas field hospital tent with cots, a medic table and supplies - the wounded, nurses, doctors, letters home",
      tags=["field hospital", "medic", "wounded", "nurse", "war", "army", "doctor", "triage", "red cross"], floor="dirt", walls="back",
      props=[P("bed", .3, .4, w=1.6, d=.7, col="olive2"), P("bed", .3, 1.5, w=1.6, d=.7, col="olive2"), P("table", 2.5, .5, w=1.0, d=.6, col="steel"), P("crate", 3.3, 2.0, w=.5, d=.5, h=.5), P("light", 1.8, 1.8, z=2.0), P("barrel", 3.4, 3.2)],
      st={"cots": [[1.3, 2.6], -1, [1.1, 1.8, .6]], "table": [[2.9, 1.5], -1, [3.0, .8, .8]], "supplies": [[2.8, 2.7], 1, [3.5, 2.2, .5]], "center": [[2.2, 3.4], 1, None]},
      guests=[[2.0, 1.4], [1.0, 3.2], [3.3, 3.6]], regulars=[[0, "explain", {"gender": "woman", "outfit": "scrubs", "color": "white", "hair": "bun"}]]),
    # ── moon ──
    K(id="moon_base", world="moon", name="Moon base", about="the inside of a lunar base: consoles, screens, an airlock, a window on the grey surface and Earth - astronauts, missions, isolation",
      tags=["moon", "lunar", "base", "astronaut", "space", "mission", "nasa", "mars", "station", "colony", "airlock"], floor="tile", walls="both",
      props=[P("console", .3, .3, w=1.6, d=.6), P("screen", wall="back", x=2.2, w=1.4, z=1.1, h=.8), P("window", wall="left", y=1.2, w=1.8), P("tank", 3.3, 2.2, w=.6, d=.6, h=1.6, col="silver"),
             P("rack", 3.4, .4, w=.5, d=.5, h=1.8), P("table", 1.4, 2.0, w=1.0, d=.7), P("ring", 2.4, 3.6, w=1.0, d=.3, h=1.5)],
      st={"console": [[1.1, 1.3], -1, [1.1, .5, 1.0]], "screen": [[2.9, 1.2], -1, [2.9, 0, 1.5]], "window": [[.6, 2.1], -1, [0, 2.1, 1.4]], "airlock": [[2.6, 3.0], 1, [2.9, 3.7, 1]], "center": [[1.8, 3.0], 1, None]},
      guests=[[1.6, 1.4], [2.2, 2.6], [1.0, 3.4]], regulars=[[0, "type", {"gender": "woman", "outfit": "space", "hat": "", "skin": "medium"}]]),
    K(id="launch_pad", world="moon", name="Launch site", about="a rocket on its launch pad on the moon with a flag and a rover - launches, countdowns, leaving, coming home",
      tags=["rocket", "launch", "countdown", "liftoff", "lander", "rover", "flag", "moon landing", "space", "spaceship"], floor="moon", walls="none",
      props=[P("rocket", 1.6, .6, w=.8, d=.8, h=3.4), P("patch", 1.2, .2, kind="concrete", w=1.6, d=1.6), P("flag", .4, 2.4, col="gold"), P("car", 2.8, 2.2, w=.6, d=1.0, h=.6, col="silver"), P("crater", .4, .4, w=.8, d=.8), P("dish", 3.3, .5)],
      st={"rocket": [[2.0, 2.3], -1, [2.0, 1.0, 2]], "flag": [[1.0, 3.0], -1, [.45, 2.45, 1.4]], "rover": [[2.6, 3.4], 1, [3.1, 2.7, .5]], "center": [[1.6, 3.5], 1, None]},
      guests=[[1.2, 2.2], [3.0, 1.6], [2.2, 3.7]], regulars=[[1, "wave", {"gender": "man", "outfit": "space"}]]),
    # ── medieval ──
    K(id="castle_hall", world="medieval", name="Castle great hall", about="a castle's great hall with a throne, banners, torches and a long table - kings and queens, knights, feasts, plots",
      tags=["castle", "king", "queen", "throne", "knight", "knights", "medieval", "royal", "kingdom", "feast", "prince", "princess", "court"], floor="cobble", walls="both", wallH=3,
      props=[P("stage", 1.2, .2, w=1.6, d=.8, h=.3), P("podium", 1.75, .35, w=.5, d=.4, h=1.3, col="gold"), P("torch", .3, .3), P("torch", 3.5, .3), P("table", .6, 2.0, w=2.6, d=.7, col="bronze"),
             P("chair", .8, 2.9), P("chair", 2.6, 2.9), P("flag", 3.4, 1.6, col="ember"), P("pillar", .3, 1.6, w=.35, d=.35, h=2.8, col="steel")],
      st={"throne": [[2.0, 1.4], 1, [2.0, .55, 1.4]], "table": [[1.8, 3.3], -1, [1.9, 2.3, .8]], "torches": [[.8, 1.0], 1, [.35, .35, 1.4]], "center": [[3.0, 2.4], 1, None]},
      guests=[[1.2, 1.4], [2.8, 1.4], [1.0, 3.5], [3.2, 3.2]], regulars=[[0, "stand", {"gender": "man", "outfit": "military", "color": "steel", "hat": "helmet"}], [1, "stand", {"gender": "man", "outfit": "military", "color": "steel", "hat": "helmet"}]]),
    K(id="village_square", world="medieval", name="Village square", about="a medieval market square with stalls, a well, cottages, a cart and torches - markets, news, crowds, gossip, festivals",
      tags=["village", "market", "square", "medieval", "town", "merchant", "festival", "peasant", "crowd", "town crier"], floor="cobble", walls="none",
      props=[P("stall", .3, .3, col="ember"), P("stall", 1.8, .3, col="gold"), P("well", 1.6, 1.6), P("house", 3.0, .2, w=1.0, d=1.2, h=2.0), P("cart", .4, 2.6), P("torch", 3.4, 2.2), P("barrel", 2.9, 3.4)],
      st={"stall": [[1.0, 1.5], -1, [.9, .7, 1]], "well": [[2.6, 2.4], -1, [2.0, 2.0, .8]], "cart": [[1.3, 3.2], -1, [.9, 2.9, .5]], "center": [[2.4, 3.4], 1, None]},
      guests=[[2.2, 1.3], [.8, 2.2], [3.2, 2.9], [1.8, 3.6]], regulars=[[0, "explain", {"gender": "woman", "outfit": "apron", "color": "bronze", "hair": "bun"}], [2, "stand", {"gender": "man", "outfit": "robe", "color": "bronze", "beard": True}]],
      animals=[["horse", 3.5, 1.6, "idle"], ["chicken", 1.1, 3.6, "eat"]]),
    K(id="tavern", world="medieval", name="Tavern", about="a medieval tavern: barrels, a bar, candle-lit tables and a fireplace - travellers, quests, songs, secrets",
      tags=["tavern", "inn", "pub", "bar", "medieval", "quest", "adventurer", "bard", "ale", "fantasy"], floor="wood", walls="both",
      props=[P("counter", .3, .3, w=2.2, d=.5, col="bronze"), P("barrel", 2.8, .3), P("barrel", 3.3, .5), P("campfire", 3.3, 2.0), P("table", .8, 2.0, w=.9, d=.7, col="brass"), P("table", 2.0, 2.8, w=.9, d=.7, col="brass"), P("light", 1.3, 2.2, z=2.0)],
      st={"bar": [[1.4, 1.3], -1, [1.4, .55, 1.1]], "fire": [[3.0, 2.8], -1, [3.5, 2.2, .5]], "table": [[1.3, 3.0], -1, [1.2, 2.3, .8]], "center": [[2.6, 2.0], 1, None]},
      guests=[[.6, 2.9], [2.0, 2.0], [3.2, 3.4], [2.6, 3.7]], regulars=[[0, "sing", {"gender": "man", "outfit": "robe", "color": "ember"}], [1, "drink", {"gender": "man", "outfit": "military", "color": "steel", "beard": True}]]),
    # ── jungle ──
    K(id="temple_ruins", world="jungle", name="Temple ruins", about="an ancient stepped temple swallowed by the jungle, vines and statues - explorers, treasure, lost civilisations, traps",
      tags=["temple", "ruins", "ancient", "maya", "aztec", "treasure", "explorer", "archaeology", "lost city", "jungle", "adventure"], floor="leaf", walls="none",
      props=[P("temple", .5, .3, w=2.4, d=2.0, h=2.2), P("statue", 3.2, .6), P("bigtree", 3.0, 2.4, w=1.0, h=3.0), P("bush", .3, 2.8), P("rock", 1.4, 3.2), P("torch", 2.9, 1.5)],
      st={"temple": [[1.7, 2.8], -1, [1.7, 1.3, 1.4]], "statue": [[2.9, 1.3], -1, [3.5, .9, 1.6]], "tree": [[2.4, 3.5], 1, [3.5, 2.9, 2]], "center": [[1.0, 3.5], 1, None]},
      guests=[[.6, 2.4], [2.4, 2.3], [3.3, 3.6]], animals=[["monkey", 3.4, 3.0, "idle"], ["parrot", 3.6, 1.0, "idle"], ["snake", 1.0, 3.0, "walk"]]),
    K(id="jungle_camp", world="jungle", name="Jungle camp", about="an explorers' camp by a jungle river: tents, crates, a map table and a fire - expeditions, discovery, wildlife",
      tags=["expedition", "camp", "jungle", "amazon", "explorer", "river", "safari", "wildlife", "rainforest", "discovery"], floor="leaf", walls="none",
      props=[P("patch", 2.8, .0, kind="water", w=1.2, d=4), P("tent", .3, .3, col="champ"), P("table", .5, 2.1, w=1.0, d=.6, col="brass"), P("crate", 1.8, .4, w=.5, d=.5, h=.5), P("campfire", 1.8, 2.6), P("palm", 2.2, .2, h=2.4), P("bigtree", .2, 3.1, w=.8, h=2.6)],
      st={"map": [[1.0, 3.0], -1, [1.0, 2.4, .8]], "tent": [[1.4, 1.6], -1, [1.0, .9, .8]], "river": [[2.4, 2.0], 1, [3.2, 2.0, .1]], "fire": [[2.0, 3.4], -1, [2.0, 2.8, .4]], "center": [[1.6, 3.6], 1, None]},
      guests=[[.7, 2.9], [2.2, 1.3], [2.5, 3.5]], regulars=[[0, "read", {"gender": "woman", "outfit": "tshirt", "color": "olive", "hat": "cowboy"}]], animals=[["parrot", 1.9, .6, "idle"], ["frog", 2.6, 3.1, "idle"]]),
    # ── ocean ──
    K(id="ship_deck", world="ocean", name="Ship deck", about="the wooden deck of a sailing ship at sea: masts, wheel, barrels, ropes - sailors, pirates, voyages, storms",
      tags=["ship", "sailing", "boat", "pirate", "pirates", "sailor", "voyage", "captain", "sea", "ocean", "deck", "navy", "storm"], floor="deck", walls="none",
      props=[P("pillar", 1.8, 1.0, w=.25, d=.25, h=3.4, col="bronze"), P("pillar", 1.8, 2.8, w=.2, d=.2, h=2.8, col="bronze"), P("barrel", .4, .4), P("barrel", .8, .5), P("crate", 3.2, .4, w=.5, d=.5, h=.4),
             P("rail", .0, 3.9, w=4), P("rail", 3.9, .0, w=.06, d=4), P("ring", 2.9, 2.2, w=.6, d=.2, h=.7), P("flag", 1.75, .9, z=3.3, col="char0")],
      st={"wheel": [[2.9, 2.9], -1, [2.95, 2.25, .6]], "mast": [[2.3, 1.7], -1, [1.9, 1.1, 1.6]], "rail": [[1.0, 3.4], 1, [1.0, 3.9, .5]], "barrels": [[1.1, 1.3], -1, [.6, .5, .5]], "center": [[2.4, 3.4], 1, None]},
      guests=[[1.2, 2.4], [3.2, 1.4], [.8, 3.2], [2.6, 1.0]], regulars=[[0, "pull", {"gender": "man", "outfit": "tshirt", "color": "navy", "beard": True}]], animals=[["parrot", 3.3, .5, "idle"]]),
    K(id="desert_island", world="ocean", name="Desert island", about="a tiny island with a palm, a hut and a signal fire in the open sea - castaways, survival, rescue, loneliness",
      tags=["island", "castaway", "stranded", "shipwreck", "survival", "rescue", "tropical", "alone", "sos"], floor="sand", walls="none",
      props=[P("patch", .0, .0, kind="water", w=4, d=.8), P("patch", .0, .0, kind="water", w=.8, d=4), P("palm", 1.5, 1.2, h=2.6), P("hut", 2.6, 1.0, w=1.0, d=.9, h=1.2), P("campfire", 2.0, 2.7), P("log", 1.0, 3.0), P("sign", 3.3, 3.2, h=1.0, col="champ")],
      st={"palm": [[1.9, 2.0], -1, [1.7, 1.4, 2]], "hut": [[2.8, 2.3], -1, [3.1, 1.4, .7]], "fire": [[1.7, 3.3], 1, [2.1, 2.8, .4]], "shore": [[1.3, 1.0], 1, [.6, .6, .1]], "center": [[2.6, 3.4], 1, None]},
      guests=[[1.0, 2.2], [3.0, 3.0]], animals=[["pigeon", 3.0, 2.0, "eat"]]),
]

if __name__ == "__main__":
    day = time.strftime("%Y-%m-%d")
    for k in KITS:
        k = dict(k, source="seed", created=day)
        with open(os.path.join(HERE, k["id"] + ".json"), "w", encoding="utf-8") as fh:
            json.dump(k, fh, indent=1)
    for f in ("farm_barn.json",):                                  # an older generated kit that belongs to a world
        path = os.path.join(HERE, f)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                j = json.load(fh)
            j.setdefault("world", "countryside")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(j, fh, indent=1)
    print("wrote %d world kits" % len(KITS))
