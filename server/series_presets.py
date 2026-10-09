"""SERIES presets — the configuration menu's vocabulary: video styles, episode structures, the character builder's
options and the song options. Data only (plus compose helpers). Identical in the MirOS copy (miros_mlab) — copy, never
import across. Engine names never appear in anything a person reads."""
import os
import re

# ── video styles ─────────────────────────────────────────────────────────────────────────────────────────────────────
# style_prompt seeds the series' style bible · camera = shot-writer grammar · look = the video look dial · sample = tile
STYLES = [
    {"id": "musical", "name": "Musical video", "blurb": "Bright stage-show colour, dancing, singing straight to camera.",
     "style_prompt": "Vibrant children's musical-video look: saturated candy palette, soft stage lighting with coloured rim "
                     "lights, glossy rounded 3D characters with big expressive eyes and wide mouths made for singing, "
                     "simple bold set pieces, confetti and sparkle accents, clean uncluttered backgrounds, cheerful energy.",
     "camera": "music-video grammar: on-beat push-ins, sweeping arcs around the singer, low-angle hero shots on the chorus, "
               "wide group shots for dance breaks; singer often faces camera", "look": "music_video", "aspect": "16:9"},
    {"id": "animated3d", "name": "3D animated", "blurb": "Soft pre-school 3D — rounded shapes, gentle light.",
     "style_prompt": "Soft pre-school 3D animation look: rounded chunky proportions, oversized heads and eyes, smooth matte "
                     "materials with subtle subsurface glow, warm pastel palette, soft global illumination, gentle ambient "
                     "occlusion, simple readable silhouettes, tidy cosy sets with few props, friendly expressions.",
     "camera": "calm and readable: static or slow push-in, eye-level with the characters, gentle pans", "look": "3d", "aspect": "16:9"},
    {"id": "cartoon2d", "name": "2D cartoon", "blurb": "Flat colours, bold outlines, squash and stretch.",
     "style_prompt": "Classic 2D cartoon look: flat cel colours, bold clean dark outlines, exaggerated squash-and-stretch "
                     "poses, big round eyes, simple painted backgrounds with soft gradients, high-contrast cheerful palette, "
                     "snappy expressive animation.",
     "camera": "cartoon staging: flat side-on and front-on compositions, quick zoom-ins on reactions, whip pans", "look": "auto", "aspect": "16:9"},
    {"id": "clay", "name": "Claymation", "blurb": "Hand-made clay figures, stop-motion charm.",
     "style_prompt": "Stop-motion claymation look: hand-sculpted plasticine characters with visible fingerprints and soft "
                     "tool marks, slightly uneven surfaces, miniature handmade sets of felt, card and wood, warm tungsten "
                     "practical lighting, shallow depth of field like a tabletop miniature.",
     "camera": "tabletop miniature: locked-off camera, small slider moves, shallow focus", "look": "claymation", "aspect": "16:9"},
    {"id": "anime", "name": "Anime", "blurb": "Big sparkling eyes, dynamic poses, painted skies.",
     "style_prompt": "Bright kids' anime look: large sparkling eyes, clean line art, cel shading with soft gradients, "
                     "vivid painted skies and backgrounds, dynamic poses, speed-line accents for excitement, warm sunlight.",
     "camera": "anime staging: dramatic low angles, quick dolly-ins on emotion, sweeping sky pans", "look": "anime", "aspect": "16:9"},
    {"id": "storybook", "name": "Storybook", "blurb": "Watercolour picture-book pages come alive.",
     "style_prompt": "Picture-book watercolour look: soft watercolour washes, visible paper texture, delicate coloured-pencil "
                     "outlines, gentle muted pastel palette, airy white space, hand-painted backgrounds, cosy bedtime warmth.",
     "camera": "slow and gentle like turning pages: slow pans across scenes, soft zooms", "look": "watercolor", "aspect": "16:9"},
    {"id": "papercut", "name": "Paper cut-out", "blurb": "Layered craft paper with real shadows.",
     "style_prompt": "Layered paper cut-out look: characters and sets made of coloured craft paper and card, visible paper "
                     "fibres and torn edges, layered depth with soft drop shadows between layers, bright primary colours.",
     "camera": "layered parallax: slow side pans revealing depth, gentle push-ins", "look": "auto", "aspect": "16:9"},
    {"id": "puppet", "name": "Puppet show", "blurb": "Felt puppets on a bright TV set.",
     "style_prompt": "Felt puppet TV-show look: soft fuzzy felt and foam puppets with ping-pong-ball eyes and big hinged "
                     "mouths, bright studio set with primary-colour props, even TV lighting, playful handmade charm.",
     "camera": "TV studio: medium shots at puppet height, simple cuts, occasional close-ups on the mouth", "look": "auto", "aspect": "16:9"},
    {"id": "realistic", "name": "Realistic", "blurb": "Live-action look — real kids, real places.",
     "style_prompt": "Bright live-action family film look: natural daylight, true-to-life skin and fabric textures, shallow "
                     "depth of field, clean colourful real locations, warm positive grade, 35 mm lens perspective.",
     "camera": "live-action coverage: handheld-steady medium shots, over-shoulder angles, natural eye-level framing",
     "look": "photoreal", "aspect": "16:9"},
    {"id": "cinematic", "name": "Cinematic", "blurb": "Big-screen lighting, depth and scale.",
     "style_prompt": "Cinematic feature-film look: anamorphic widescreen framing, dramatic golden-hour and volumetric "
                     "lighting, rich colour grade with deep shadows and warm highlights, atmospheric haze, epic sense of "
                     "scale, polished feature-animation detail.",
     "camera": "feature-film grammar: slow dolly and crane moves, wide establishing shots, rack focus, hero close-ups",
     "look": "cinematic", "aspect": "21:9"},
    {"id": "shortfilm", "name": "Short film", "blurb": "Indie festival short — moody, intimate, honest.",
     "style_prompt": "Indie short-film look: naturalistic soft light, muted filmic palette with one accent colour, gentle "
                     "film grain, intimate framing, quiet emotional moments, considered composition with negative space.",
     "camera": "auteur restraint: long held shots, slow push-ins on feeling, symmetrical compositions", "look": "vintage", "aspect": "16:9"},
]

# ── episode structures (beats in order: role, share of the runtime, kind) ──────────────────────────────────────────────
# kind: sing (lip-synced to the song) · dialogue (spoken lines) · action (no singing, music plays) · establish (wide intro)
STRUCTURES = [
    {"id": "musical", "name": "Musical video", "blurb": "The song drives every shot — verse, chorus, dance break.",
     "song_led": True, "beats": [["Intro", .08, "establish"], ["Verse 1", .17, "sing"], ["Chorus", .17, "sing"],
                                  ["Verse 2", .17, "sing"], ["Dance break", .08, "action"], ["Final chorus", .25, "sing"],
                                  ["Outro", .08, "action"]]},
    {"id": "singalong", "name": "Sing-along / learning song", "blurb": "Repeat-after-me chorus three times, one lesson.",
     "song_led": True, "beats": [["Hello", .1, "sing"], ["Chorus", .2, "sing"], ["Learn it", .2, "sing"],
                                  ["Chorus again", .2, "sing"], ["Everyone together", .2, "sing"], ["Bye-bye", .1, "action"]]},
    {"id": "story", "name": "Story episode", "blurb": "A problem, a try, a song break, a happy fix.",
     "song_led": False, "beats": [["Cold open", .1, "establish"], ["The problem", .15, "dialogue"], ["First try", .15, "dialogue"],
                                   ["Oops", .1, "action"], ["Song break", .3, "sing"], ["The fix", .1, "dialogue"],
                                   ["Celebration", .1, "sing"]]},
    {"id": "hybrid", "name": "Music + story", "blurb": "Talk, sing, talk, sing — a mini musical.",
     "song_led": True, "beats": [["Set-up", .12, "dialogue"], ["Verse", .18, "sing"], ["Twist", .12, "dialogue"],
                                  ["Chorus", .2, "sing"], ["Resolution", .13, "dialogue"], ["Final chorus", .25, "sing"]]},
    {"id": "shortfilm", "name": "Short film", "blurb": "Three acts, little dialogue, music under the picture.",
     "song_led": False, "beats": [["Act 1 — want", .25, "establish"], ["Act 2 — obstacle", .4, "action"],
                                   ["Act 3 — change", .25, "action"], ["Final image", .1, "action"]]},
    {"id": "lullaby", "name": "Lullaby", "blurb": "Slow, soft, bedtime — one gentle song.",
     "song_led": True, "beats": [["Nightfall", .15, "establish"], ["Verse", .3, "sing"], ["Chorus", .3, "sing"],
                                  ["Sleepy end", .25, "action"]]},
    {"id": "custom", "name": "Custom", "blurb": "Build your own beat list.", "song_led": True, "beats": []},
]

LENGTHS = [30, 60, 90, 120, 150, 180]
ASPECTS = ["16:9", "9:16", "1:1", "21:9"]
CLIP_SECS = 10                                      # one performance clip ≈ one musical phrase

# ── the character builder ─────────────────────────────────────────────────────────────────────────────────────────────
# type: one (single choice) · many (multi) · swatch (colours) · range (slider: [min, max, default, unit labels])
CHARACTER = [
    {"k": "kind", "label": "What are they", "group": "Who", "type": "one",
     "opts": ["kid", "toddler", "grown-up", "grandparent", "bunny", "bear cub", "fox", "puppy", "kitten", "duck",
              "elephant", "lion cub", "crocodile", "dinosaur", "penguin", "owl", "monkey", "unicorn", "dragon",
              "robot", "alien", "monster", "fairy", "talking toy", "talking fruit", "talking car"]},
    {"k": "gender", "label": "Boy / girl", "group": "Who", "type": "one", "opts": ["any", "boy", "girl", "neither"]},
    {"k": "age", "label": "Age", "group": "Who", "type": "range", "range": [2, 70, 5], "unit": "years"},
    {"k": "role", "label": "Role in the show", "group": "Who", "type": "one",
     "opts": ["lead", "best friend", "sidekick", "mentor", "comic relief", "little sibling", "grumpy-but-kind", "narrator"]},
    {"k": "height", "label": "Height (for the lineup)", "group": "Body", "type": "range", "range": [1, 10, 5],
     "unit": "tiny … tall"},
    {"k": "build", "label": "Body shape", "group": "Body", "type": "one",
     "opts": ["round and chubby", "small and slim", "tall and lanky", "sturdy and strong", "pear-shaped", "bean-shaped"]},
    {"k": "head", "label": "Head size", "group": "Body", "type": "one", "opts": ["normal", "big", "very big (chibi)"]},
    {"k": "skin", "label": "Skin / fur colour", "group": "Colours", "type": "swatch",
     "opts": ["#f6d7c3", "#e8b896", "#c68e63", "#8d5a3b", "#5a3825", "#ffffff", "#f2e6d0", "#ffcf3f", "#ff9a3c",
              "#e94b3c", "#ff8fb8", "#b48cff", "#5aa9ff", "#41c48a", "#8b8b8b", "#3a3a3a"]},
    {"k": "accent", "label": "Signature colour", "group": "Colours", "type": "swatch",
     "opts": ["#e94b3c", "#ff9a3c", "#ffcf3f", "#41c48a", "#2bb5b0", "#5aa9ff", "#3657d6", "#b48cff", "#ff8fb8", "#ffffff", "#222222"]},
    {"k": "eyes", "label": "Eyes", "group": "Face", "type": "one",
     "opts": ["big round", "sparkly", "sleepy half-closed", "button dots", "almond", "with glasses", "one big eye"]},
    {"k": "eyecolor", "label": "Eye colour", "group": "Face", "type": "one", "opts": ["brown", "blue", "green", "hazel", "black", "violet"]},
    {"k": "face", "label": "Face details", "group": "Face", "type": "many",
     "opts": ["freckles", "rosy cheeks", "gap tooth", "dimples", "bushy eyebrows", "whiskers", "a little beak", "big ears"]},
    {"k": "hair", "label": "Hair", "group": "Hair", "type": "one",
     "opts": ["none", "short spiky", "curly afro", "two pigtails", "long straight", "ponytail", "bob cut", "messy mop",
              "braids", "top bun", "mohawk", "fluffy tuft"]},
    {"k": "haircolor", "label": "Hair colour", "group": "Hair", "type": "one",
     "opts": ["black", "brown", "blonde", "ginger", "white", "pink", "blue", "green", "purple"]},
    {"k": "top", "label": "Top", "group": "Outfit", "type": "one",
     "opts": ["t-shirt", "hoodie", "striped jumper", "dungarees", "raincoat", "dress", "overalls", "lab coat",
              "superhero cape", "sports jersey", "pyjamas", "none"]},
    {"k": "bottom", "label": "Bottom", "group": "Outfit", "type": "one",
     "opts": ["shorts", "jeans", "skirt", "leggings", "trousers", "tutu", "none"]},
    {"k": "shoes", "label": "Shoes", "group": "Outfit", "type": "one",
     "opts": ["sneakers", "rain boots", "sandals", "light-up shoes", "slippers", "barefoot"]},
    {"k": "accessory", "label": "Accessories", "group": "Outfit", "type": "many",
     "opts": ["backpack", "cap", "bow", "scarf", "crown", "headphones", "bandana", "star badge", "watch", "flower"]},
    {"k": "item", "label": "Signature item", "group": "Outfit", "type": "one",
     "opts": ["none", "ukulele", "microphone", "magnifying glass", "toy rocket", "paintbrush", "teddy", "ball", "magic wand", "book"]},
    {"k": "traits", "label": "Personality", "group": "Personality", "type": "many",
     "opts": ["curious", "brave", "shy", "silly", "kind", "bossy", "dreamy", "energetic", "clumsy", "clever", "cheeky", "gentle"]},
    {"k": "move", "label": "How they move", "group": "Personality", "type": "one",
     "opts": ["bouncy", "graceful", "waddling", "zooming", "tiptoe", "stomping", "wiggly dancer"]},
    {"k": "catch", "label": "Catchphrase", "group": "Personality", "type": "text", "ph": "e.g. \"Let's go-go-go!\""},
    {"k": "range", "label": "Singing voice", "group": "Voice", "type": "one",
     "opts": ["high and bright", "sweet middle", "warm low", "squeaky", "raspy", "deep and booming"]},
    {"k": "tone", "label": "Voice character", "group": "Voice", "type": "one",
     "opts": ["cheerful", "gentle", "excited", "sleepy", "funny", "confident"]},
    {"k": "vaccent", "label": "Accent", "group": "Voice", "type": "one",
     "opts": ["neutral", "American", "British", "Irish", "Australian", "Spanish", "Southern"]},
]

# ── the object builder: vehicles, animals, plants, buildings, props … (same field types as the character builder) ──
# keys start with "o_" so their option previews (o_kind__car.jpg …) never collide with the character builder's
OBJECT = [
    {"k": "o_kind", "label": "What is it", "group": "What", "type": "one",
     "opts": ["car", "race car", "truck", "fire engine", "bus", "tractor", "digger", "motorbike", "bicycle", "train",
              "airplane", "helicopter", "rocket", "boat", "pirate ship", "submarine", "hot-air balloon",
              "horse", "dog", "cat", "bird", "fish", "butterfly", "cow", "sheep", "frog",
              "tree", "palm tree", "flower", "cactus", "mushroom", "potted plant", "vegetable patch",
              "house", "castle", "treehouse", "tent", "toy", "ball", "kite", "teddy bear", "cake", "fruit basket",
              "lamp", "chair", "bed", "treasure chest", "magic wand", "musical instrument", "gadget"]},
    {"k": "o_era", "label": "Style / era", "group": "What", "type": "one",
     "opts": ["modern", "vintage", "classic 1950s", "futuristic", "fantasy", "steampunk", "toy-like", "storybook"]},
    {"k": "o_size", "label": "Size (next to the cast)", "group": "What", "type": "range", "range": [1, 10, 5],
     "unit": "tiny … huge"},
    {"k": "o_shape", "label": "Shape", "group": "Shape", "type": "one",
     "opts": ["rounded and bubbly", "sleek and streamlined", "boxy", "chunky and sturdy", "tall and thin", "long and low",
              "squashy and soft", "spiky", "wobbly and hand-made"]},
    {"k": "o_color", "label": "Main colour", "group": "Colours", "type": "swatch",
     "opts": ["#e94b3c", "#ff9a3c", "#ffcf3f", "#41c48a", "#2bb5b0", "#5aa9ff", "#3657d6", "#b48cff", "#ff8fb8",
              "#ffffff", "#f2e6d0", "#c68e63", "#8d5a3b", "#8b8b8b", "#3a3a3a", "#222222"]},
    {"k": "o_accent", "label": "Accent colour", "group": "Colours", "type": "swatch",
     "opts": ["#e94b3c", "#ff9a3c", "#ffcf3f", "#41c48a", "#2bb5b0", "#5aa9ff", "#3657d6", "#b48cff", "#ff8fb8", "#ffffff", "#222222"]},
    {"k": "o_material", "label": "Made of", "group": "Material", "type": "one",
     "opts": ["painted metal", "chrome", "wood", "plastic", "glass", "fabric", "stone", "fur", "feathers", "scales",
              "leaves and bark", "rubber", "candy", "crystal", "paper and cardboard", "knitted wool"]},
    {"k": "o_finish", "label": "Finish", "group": "Material", "type": "many",
     "opts": ["shiny", "matte", "glowing", "sparkly", "rusty", "worn and old", "brand new", "muddy", "stripes",
              "polka dots", "painted flames", "stars", "patchwork"]},
    {"k": "o_parts", "label": "Details", "group": "Details", "type": "many",
     "opts": ["big wheels", "whitewall tyres", "wings", "propeller", "headlights", "round windows", "antenna", "flag",
              "chimney", "sails", "rocket boosters", "a bell", "a long tail", "horns", "big paws", "flowers", "fruit",
              "a number on the side", "a little door", "stickers", "a basket", "a roof rack"]},
    {"k": "o_face", "label": "Alive?", "group": "Personality", "type": "one",
     "opts": ["no face (a real object)", "cute eyes", "full cartoon face", "eyes in the headlights / windows"]},
    {"k": "o_mood", "label": "Feel", "group": "Personality", "type": "one",
     "opts": ["friendly", "cosy", "heroic", "magical", "silly", "spooky-cute", "sleek and cool", "sleepy"]},
    {"k": "o_move", "label": "How it moves", "group": "Personality", "type": "one",
     "opts": ["stays still", "rolls along", "zooms", "flies", "floats", "sails", "hops", "gallops", "sways in the wind",
              "spins", "bounces", "chugs and puffs"]},
]

SONG = [
    {"k": "genre", "label": "Music style", "type": "one",
     "opts": ["nursery rhyme", "bubblegum pop", "rock", "lullaby", "reggae", "kids hip-hop", "marching band",
              "Latin pop", "country", "disco", "Broadway show tune", "electronic dance"]},
    {"k": "bpm", "label": "Tempo (BPM)", "type": "range", "range": [60, 150, 100]},
    {"k": "mood", "label": "Mood", "type": "one", "opts": ["happy", "silly", "brave", "calm", "dreamy", "triumphant"]},
    {"k": "vocal", "label": "Who sings", "type": "one",
     "opts": ["solo lead", "duet", "call and response", "kids choir", "whole cast"]},
    {"k": "lang", "label": "Language", "type": "one", "opts": ["English", "Spanish", "French", "Portuguese", "bilingual EN/ES"]},
]

GENRE_CAPTION = {
    "nursery rhyme": "classic nursery rhyme, ukulele, glockenspiel, hand claps, bouncy bass",
    "bubblegum pop": "bubblegum kids pop, bright synths, punchy drums, catchy hook",
    "rock": "kids pop-rock, crunchy friendly guitars, live drums, big singalong chorus",
    "lullaby": "gentle lullaby, music box, soft piano, warm strings, slow and calm",
    "reggae": "sunny kids reggae, offbeat guitar skank, steel drums, relaxed groove",
    "kids hip-hop": "playful kids hip-hop, boom-bap beat, scratches, call-and-response hook",
    "marching band": "marching band, brass, snare rolls, cymbals, stomping beat",
    "Latin pop": "Latin kids pop, congas, maracas, nylon guitar, dance rhythm",
    "country": "kids country, banjo, fiddle, acoustic guitar, foot-stomp beat",
    "disco": "kids disco, four-on-the-floor, funky bass, strings, handclaps",
    "Broadway show tune": "Broadway show tune, orchestra, piano, big theatrical finish",
    "electronic dance": "kids electronic dance, bouncy synth bass, sparkling arps, drop on the chorus",
}


try:                                                   # each lab copy serves its own static folder
    try:
        from . import core as _core
    except ImportError:
        import core as _core
    SAMPLES = os.path.join(_core.STATIC, "series", "samples")
except Exception:
    SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "series", "samples")


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", str(v).lower()).strip("-")


def previews():
    """{"style_musical": "style_musical.jpg", "kind__fox": "kind__fox.jpg", "hair__curly-afro": "…mp4"} — an option only
    shows a preview once its file exists (tools/make_series_samples.py renders them; video wins over a still)."""
    out = {}
    try:
        names = sorted(os.listdir(SAMPLES))
    except OSError:                                    # compiled PC edition: the samples live inside the binary
        names = sorted(k[len("series/samples/"):] for k in (getattr(_core, "ASSETS", None) or {}) if k.startswith("series/samples/"))
    try:
        for f in names:
            stem, ext = os.path.splitext(f)
            if stem.startswith("_"):                       # generator working files (base stills)
                continue
            if ext.lower() in (".jpg", ".png", ".webp", ".mp4", ".mp3") and (stem not in out or ext.lower() == ".mp4"):
                out[stem] = f
    except OSError:
        pass
    return out


def catalog():
    try:
        from . import series_help as _h
    except ImportError:
        import series_help as _h
    fields = {f["k"]: f for f in CHARACTER + OBJECT + SONG}
    return {"styles": STYLES, "structures": STRUCTURES, "lengths": LENGTHS, "aspects": ASPECTS, "clip_secs": CLIP_SECS,
            "character": CHARACTER, "object": OBJECT, "song": SONG, "previews": previews(),
            "help": _h.help_for(fields, colour)}


def style(sid):
    return next((s for s in STYLES if s["id"] == sid), None)


def structure(sid):
    return next((s for s in STRUCTURES if s["id"] == sid), None)


_HEX = {"#f6d7c3": "fair", "#e8b896": "light tan", "#c68e63": "tan", "#8d5a3b": "brown", "#5a3825": "dark brown",
        "#ffffff": "white", "#f2e6d0": "cream", "#ffcf3f": "sunny yellow", "#ff9a3c": "orange", "#e94b3c": "red",
        "#ff8fb8": "pink", "#b48cff": "lavender", "#5aa9ff": "sky blue", "#41c48a": "green", "#8b8b8b": "grey",
        "#3a3a3a": "charcoal", "#2bb5b0": "teal", "#3657d6": "royal blue", "#222222": "black"}


def colour(v):
    v = str(v or "").lower()
    return _HEX.get(v, v if re.fullmatch(r"[a-z \-]{2,24}", v) else "")


PEOPLE = ("kid", "toddler", "grown-up", "grandparent")
AGE_OK = {"kid": (4, 12), "toddler": (1, 3), "grown-up": (18, 60), "grandparent": (55, 95)}   # a slider left at a kid's age
GENDERED = {("kid", "boy"): "boy", ("kid", "girl"): "girl", ("toddler", "boy"): "toddler boy",         # never turns a grandparent
            ("toddler", "girl"): "toddler girl", ("grown-up", "boy"): "man", ("grown-up", "girl"): "woman",   # into a child
            ("grandparent", "boy"): "grandpa", ("grandparent", "girl"): "grandma"}
KIND_LOOK = {   # what makes each kind read as itself in a picture (said right after the kind)
    "grown-up": "an adult with grown-up proportions", "grandparent": "an elderly person with gentle wrinkles",
    "toddler": "a tiny two-year-old with a chubby baby face", "robot": "a robot made of metal and plastic panels with bolts, "
    "joints and glowing lights, no skin or hair", "alien": "an alien from another planet with antennae and non-human skin",
    "monster": "a cute furry monster with little horns and a big friendly mouth", "fairy": "a tiny fairy with sparkly see-through wings",
    "talking toy": "a living toy figure with visible plastic or wooden joints", "talking fruit":
    "a big piece of fruit with a cartoon face, tiny arms and legs", "talking car": "a cartoon car with big eyes in the windscreen "
    "and a smiling bumper mouth, no arms or legs", "dragon": "a small dragon with wings, scales and a tail",
    "unicorn": "a unicorn with a spiral horn and a flowing mane", "dinosaur": "a dinosaur with scales and a tail",
    "crocodile": "a green crocodile with a long snout and a tail", "duck": "a duck with a beak and feathers",
    "penguin": "a penguin with a beak and flippers", "owl": "an owl with feathers and big round eyes"}
NO_OUTFIT = ("talking car", "talking fruit")                 # nothing to dress: no clothes, shoes or hair


def compose_desc(t):
    """Builder choices → one English description for the picture prompts (the free-text desc is added after it)."""
    t = t or {}
    g = lambda k: (str(t.get(k) or "").strip() if not isinstance(t.get(k), list) else "")
    many = lambda k: [str(x) for x in (t.get(k) or []) if isinstance(t.get(k), list)][:6]
    kind = base = g("kind") or "kid"
    who = []
    age = t.get("age")
    lo, hi = AGE_OK.get(kind, (0, 0))
    if age and kind in PEOPLE and lo <= int(age) <= hi:
        who.append("%s-year-old" % int(age))
    elif kind not in PEOPLE:
        who.append("little" if (t.get("height") or 5) <= 4 else "")
    if g("gender") in ("boy", "girl") and base not in NO_OUTFIT:
        kind = GENDERED.get((kind, g("gender")), "%s %s" % ("male" if g("gender") == "boy" else "female", kind))
    who.append(kind)
    parts = [" ".join(w for w in who if w)]
    if KIND_LOOK.get(base):
        parts.append(KIND_LOOK[base])
    if g("build"):
        parts.append(g("build") + " body")
    if g("head") and g("head") != "normal":
        parts.append(g("head") + " head")
    if colour(t.get("skin")):
        parts.append(colour(t.get("skin")) + (" skin" if base in ("kid", "toddler", "grown-up", "grandparent") else " body" if base in ("robot", "alien", "talking toy", "talking fruit", "talking car") else " fur"))
    if g("eyes"):
        parts.append("%s %seyes" % (g("eyes"), (g("eyecolor") + " ") if g("eyecolor") else ""))
    if many("face"):
        parts.append(", ".join(many("face")))
    if g("hair") and g("hair") != "none" and base not in NO_OUTFIT and base != "robot":
        parts.append("%s %shair" % (g("hair"), (g("haircolor") + " ") if g("haircolor") else ""))
    outfit = [x for x in (g("top"), g("bottom"), g("shoes")) if x and x != "none" and base not in NO_OUTFIT]
    if outfit:
        acc = colour(t.get("accent"))
        parts.append("wearing " + (acc + " " if acc else "") + " and ".join([", ".join(outfit[:-1]), outfit[-1]] if len(outfit) > 1 else outfit))
    if many("accessory"):
        parts.append("with " + ", ".join(many("accessory")))
    if g("item") and g("item") != "none":
        parts.append("always carries a " + g("item"))
    if many("traits"):
        parts.append(" and ".join(many("traits")[:3]) + " personality")
    if g("move"):
        parts.append(g("move") + " way of moving")
    return ", ".join(p for p in parts if p)


def compose_obj_desc(t):
    """Object-builder choices → one English description for the picture prompts (the free-text desc is added after it)."""
    t = t or {}
    g = lambda k: (str(t.get(k) or "").strip() if not isinstance(t.get(k), list) else "")
    many = lambda k: [str(x) for x in (t.get(k) or []) if isinstance(t.get(k), list)][:6]
    n = int(t.get("o_size") or 5)
    size = "tiny" if n <= 2 else "small" if n <= 4 else "" if n <= 6 else "big" if n <= 8 else "huge"
    era = "" if g("o_era") in ("", "modern") else g("o_era")
    parts = [" ".join(w for w in (size, era, g("o_kind") or "object") if w)]
    if g("o_shape"):
        parts.append(g("o_shape") + " shape")
    body = " ".join(w for w in (colour(t.get("o_color")), g("o_material")) if w)
    if body:
        parts.append(body + ("" if g("o_material") in ("fur", "feathers", "scales", "leaves and bark") else " body"))
    if colour(t.get("o_accent")):
        parts.append(colour(t.get("o_accent")) + " accents")
    if many("o_finish"):
        parts.append(", ".join(many("o_finish")))
    if many("o_parts"):
        parts.append("with " + ", ".join(many("o_parts")))
    face = g("o_face")
    if face and not face.startswith("no face"):
        parts.append("with eyes in its headlights or windows" if face.startswith("eyes") else "with " + face)
    elif face:
        parts.append("a real object with no face")
    if g("o_mood"):
        parts.append(g("o_mood") + " feel")
    if g("o_move") and g("o_move") != "stays still":
        parts.append("it " + g("o_move"))
    return ", ".join(p for p in parts if p)


def voice_desc(t):
    t = t or {}
    bits = [str(t.get(k)) for k in ("range", "tone") if t.get(k)]
    if t.get("vaccent") and t.get("vaccent") != "neutral":
        bits.append(str(t["vaccent"]) + " accent")
    return ", ".join(bits)


def song_caption(cfg, singer_voices=""):
    cfg = cfg or {}
    genre = cfg.get("genre") or "nursery rhyme"
    bpm = int(cfg.get("bpm") or 100)
    vocal = cfg.get("vocal") or "solo lead"
    cap = "%s, %s, %d BPM, %s mood, %s children's vocals%s" % (
        genre, GENRE_CAPTION.get(genre, genre), bpm, cfg.get("mood") or "happy", vocal,
        (" (" + singer_voices + ")") if singer_voices else "")
    if cfg.get("lang") and cfg["lang"] != "English":
        cap += ", sung in " + cfg["lang"]
    return cap
