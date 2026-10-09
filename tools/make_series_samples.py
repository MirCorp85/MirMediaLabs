"""SERIES sample tiles: one picture per video style (the same test character, so styles compare cleanly) plus a preview
for every builder / song / Setup option. Queues through the running lab (loopback = owner), one request at a time, and
saves server/static/series/samples/<name>.<jpg|mp4|mp3> (the page shows a file once it exists), mirrored to MirOS /mlab.

    python tools/make_series_samples.py [styles|builder|options|stylevideos|objects|moves|voices|songs|setup|all]
                                         [--only id,id]

  styles       one still per video style (style_<id>.jpg)
  stylevideos  a 4 s looping clip per style, animated from its still (style_<id>.mp4 — tiles prefer video)
  options      one thumbnail per character-builder option: the same base character, ONE option changed
               (<field>__<option-slug>.jpg — the builder chips show them automatically)
  objects      one thumbnail per object-builder option (o_<field>__<option>.jpg)
  moves        a short looping clip per "how they move" option (move__*.mp4, o_move__*.mp4)
  voices       a ~18 s sung example per singing voice / voice character / accent (range__*.mp3 …)
  songs        a ~18 s example per music style / mood / who sings / language (genre__*.mp3 …)
  setup        Setup-tab previews: picture shapes (aspect__*), quality (res__*), shot joins (join__*)
Existing files are skipped (resumable). A request someone makes in the lab always goes first.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "server")
sys.path.insert(0, SERVER)
import series_help  # noqa: E402
import series_presets as P  # noqa: E402

LAB = "http://127.0.0.1:5400"
OUT = os.path.join(SERVER, "static", "series", "samples")
LIB = os.path.join(HERE, "..", "data", "library")
MIRRORS = [p for p in os.environ.get("MML_SAMPLES_MIRROR", "").split(";") if p]   # optional local mirror copies (env var, never a hardcoded path)
TEST = ("a small fox girl in a yellow raincoat and red rain boots, holding a ukulele, singing happily with her mouth open, "
        "standing on a puddle-dotted village street with colourful houses")
FOX_MOTION = "The fox girl sings happily and strums the ukulele, bouncing to the beat, raindrops sparkling. Gentle camera push-in."

BUILDER = {
    "kind_kid": {"kind": "kid", "age": 6, "gender": "boy", "hair": "curly afro", "haircolor": "black", "skin": "#8d5a3b",
                 "top": "striped jumper", "bottom": "shorts", "shoes": "light-up shoes", "accent": "#41c48a", "traits": ["curious", "energetic"]},
    "kind_bunny": {"kind": "bunny", "gender": "girl", "height": 3, "build": "round and chubby", "skin": "#ffffff", "eyes": "sparkly",
                   "face": ["rosy cheeks"], "top": "dress", "accent": "#ff8fb8", "accessory": ["bow"], "traits": ["shy", "kind"]},
    "kind_robot": {"kind": "robot", "height": 7, "build": "bean-shaped", "skin": "#5aa9ff", "eyes": "one big eye", "top": "none",
                   "accessory": ["headphones"], "item": "microphone", "traits": ["silly", "clever"]},
    "kind_dino": {"kind": "dinosaur", "height": 9, "build": "sturdy and strong", "skin": "#41c48a", "eyes": "big round",
                  "top": "overalls", "accent": "#ffcf3f", "item": "ball", "traits": ["gentle", "clumsy"]},
}

OPTION_BASE = {"kind": "kid", "gender": "girl", "age": 6, "skin": "#e8b896", "hair": "two pigtails", "haircolor": "brown",
               "eyes": "big round", "top": "t-shirt", "bottom": "shorts", "shoes": "sneakers", "accent": "#5aa9ff"}
CLOSE = ("Extreme close-up headshot: only the head and face fill the whole frame, no body visible, so the {what} is "
         "large and obvious. ")
OPTION_FRAME = {"hair": "Head-and-shoulders portrait so the hairstyle is clearly visible. ",
                "haircolor": "Head-and-shoulders portrait so the hair colour is clearly visible. ",
                "eyes": CLOSE.format(what="eye shape"), "eyecolor": CLOSE.format(what="eye colour"),
                "face": CLOSE.format(what="facial detail"), "accessory": "Upper-body portrait so the accessory is clearly visible. ",
                "shoes": "Full body, low camera angle, the feet and shoes large and clearly visible. ",
                "bottom": "Full body so the clothing on the legs is clearly visible. "}
# the option decides the base: a grandparent isn't the 6-year-old girl, a beak belongs on a bird, one big eye on a monster
KIND_BASE = {"toddler": {"age": 2}, "grown-up": {"age": 35, "hair": "ponytail"},
             "grandparent": {"age": 72, "hair": "top bun", "haircolor": "white", "top": "striped jumper", "bottom": "trousers"}}
OPT_BASE = {("gender", "boy"): {"hair": "short spiky"}, ("gender", "neither"): {"hair": "bob cut", "accent": "#ffcf3f"},
            ("face", "a little beak"): {"kind": "duck"}, ("face", "whiskers"): {"kind": "kitten"},
            ("eyes", "one big eye"): {"kind": "monster"}, ("eyecolor", "violet"): {}}
ROLE_SCENE = {   # role is about the story, so each one is staged as a moment that shows it
    "lead": ({}, "standing proudly front and centre in a confident hero pose, a soft spotlight on her"),
    "best friend": ({}, "smiling warmly and holding out half of her sandwich to share, as if to a friend just off-frame"),
    "sidekick": ({"kind": "puppy"}, "an eager little helper running along carrying a backpack full of tools"),
    "mentor": ({"kind": "grown-up", "age": 45, "eyes": "with glasses", "top": "lab coat", "hair": "bob cut"},
               "a kind teacher pointing to a small chalkboard, explaining something patiently"),
    "comic relief": ({}, "slipping comically on a banana peel with a funny surprised face"),
    "little sibling": ({"kind": "toddler", "age": 2}, "a tiny toddler hugging a teddy and copying a big kid's pose"),
    "grumpy-but-kind": ({}, "arms crossed with a grumpy frown while secretly holding out a flower"),
    "narrator": ({"kind": "grandparent", "age": 72, "hair": "top bun", "haircolor": "white", "bottom": "trousers"},
                 "sitting in a cosy armchair with an open storybook, telling the story to the viewer")}
SKIP_FIELDS = ("skin", "accent", "age", "height", "catch", "range", "tone", "vaccent", "move")   # swatch/slider/text/audio/motion

OBJ_FIELDS = ["o_kind", "o_era", "o_shape", "o_material", "o_finish", "o_parts", "o_face", "o_mood"]
OBJ_BASE = {"o_kind": "car", "o_color": "#e94b3c", "o_accent": "#ffffff", "o_material": "painted metal",
            "o_shape": "rounded and bubbly", "o_face": "no face (a real object)", "o_mood": "friendly"}
OBJ_TPL = ("Prop design of {d}. One single object shown whole and centred in a clear three-quarter view, standing on a "
           "plain light background with a soft ground shadow, even lighting. No people, no text. {style}")
OBJ_FOR_MOVE = {"rolls along": "car", "zooms": "race car", "flies": "airplane", "floats": "hot-air balloon", "sails": "boat",
                "hops": "frog", "gallops": "horse", "sways in the wind": "palm tree", "spins": "toy", "bounces": "ball",
                "chugs and puffs": "train", "stays still": "house"}
MADE_OBJECTS = ("car", "race car", "truck", "fire engine", "bus", "tractor", "digger", "motorbike", "bicycle", "train",
                "airplane", "helicopter", "rocket", "boat", "pirate ship", "submarine", "toy", "ball", "house")

SONG_LYRICS = ("[verse]\nClap your hands and stamp your feet,\nwe can dance to any beat!\n"
               "[chorus]\nLa la la, sing along with me,\nla la la, as happy as can be!")
SONG_LYRICS_LANG = {
    "Spanish": "[verse]\nAplaude fuerte, salta ya,\nbaila, baila sin parar!\n[chorus]\nLa la la, canta junto a mi,\nla la la, que feliz!",
    "French": "[verse]\nTape des mains, tape des pieds,\non va danser, on va chanter!\n[chorus]\nLa la la, chante avec moi,\nla la la, quelle joie!",
    "Portuguese": "[verse]\nBata palmas, bata o pe,\nvamos dancar, venha ver!\n[chorus]\nLa la la, canta comigo,\nla la la, meu amigo!",
    "bilingual EN/ES": "[verse]\nClap your hands, aplaude ya,\nlet's all dance, a bailar!\n[chorus]\nLa la la, sing with me,\nla la la, canta feliz!"}
SONG_BASE = {"genre": "nursery rhyme", "bpm": 100, "mood": "happy", "vocal": "solo lead", "lang": "English"}

try:
    import core
    FFMPEG, NOWIN = core.FFMPEG, getattr(core, "NO_WINDOW", 0)
except Exception:
    FFMPEG, NOWIN = "ffmpeg", 0


def api(path, body=None, timeout=60):
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ff(*args, timeout=120):
    subprocess.run([FFMPEG, "-hide_banner", "-y", *args], capture_output=True, timeout=timeout, creationflags=NOWIN)


def lab_idle():
    try:
        st = api("/api/status", timeout=10)
        return not st.get("running") and not st.get("queued")
    except Exception:
        return False


def have(name, ext):
    return os.path.isfile(os.path.join(OUT, name + ext))


def mirror(path):
    for m in MIRRORS:
        if os.path.isdir(os.path.dirname(m)):
            os.makedirs(m, exist_ok=True)
            shutil.copy2(path, os.path.join(m, os.path.basename(path)))


def render(prompt, aspect, name, size=None, model="qimg", refs=None, override=None, ext=".jpg"):
    dst = os.path.join(OUT, name + ext)
    if os.path.isfile(dst):
        print("  have", name + ext)
        return dst
    while not lab_idle():                              # someone is rendering — they go first
        time.sleep(20)
    while True:
        try:
            ov = override if override is not None else dict({"mode": "generate", "aspect": aspect, "enhance": "off"},
                                                            **({"size": size} if size else {}))
            j = api("/api/generate", {"model": model, "prompt": prompt, "refs": refs or [], "override": ov, "internal": True})
            break
        except urllib.error.HTTPError as e:
            if e.code == 409:
                time.sleep(15)
                continue
            raise
    jid = j["id"]
    while True:
        time.sleep(4)
        s = api("/api/jobs/" + jid)
        if s["status"] not in ("queued", "running"):
            break
    if s["status"] != "done":
        print("  FAILED", name, s.get("error"), flush=True)
        return None
    f = next((x for x in s.get("files") or []
              if x.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mp3", ".flac", ".wav"))), None)
    if not f:
        print("  FAILED", name, "no file", flush=True)
        return None
    src = os.path.join(LIB, os.path.basename(f))
    if ext == ".mp4":                                  # small silent looping preview
        ff("-i", src, "-an", "-vf", "scale=480:-2", "-c:v", "libx264", "-crf", "26", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", dst)
    elif ext == ".mp3":                                # a short example: first ~18 s, soft fade out, small file
        ff("-i", src, "-t", "18", "-af", "afade=t=out:st=16:d=2", "-c:a", "libmp3lame", "-b:a", "96k", dst)
    else:                                              # downsized jpeg for the tile
        ff("-i", src, "-vf", "scale=720:-2", "-q:v", "4", dst, timeout=60)
    if not os.path.isfile(dst):
        shutil.copy2(src, dst)
    print("  saved", dst, flush=True)
    _tidy(f)
    mirror(dst)
    return dst


def _tidy(f):
    """The tile copy is what the page uses; the library copy goes to the lab's trash (recoverable, not deleted)."""
    try:
        api("/api/library/%s/delete" % urllib.parse.quote(os.path.basename(f)), {})
    except Exception as e:
        print("  (library copy kept: %s)" % e)


def api_upload(path):
    """Upload a file as a reference (multipart, stdlib only) → its ref name."""
    import uuid as _u
    b = _u.uuid4().hex
    data = open(path, "rb").read()
    head = ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: image/jpeg\r\n\r\n'
            % (b, os.path.basename(path)))
    body = head.encode() + data + ('\r\n--%s--\r\n' % b).encode()
    req = urllib.request.Request(LAB + "/api/upload", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))["name"]


def opt_list(spec, keys):
    for fk in keys:
        f = next(x for x in spec if x["k"] == fk)
        for opt in f["opts"]:
            if opt != "none":
                yield f, opt


def h3_clip(prompt, still, name, aspect="1:1", res="draft"):
    """A 4 s i2v preview clip from a still (same seed every time, so options compare like for like)."""
    if have(name, ".mp4"):
        print("  have", name + ".mp4")
        return
    ov = {"mode": "i2v", "aspect": aspect, "res": res, "seconds": 4, "enhance": "off", "audio": "off", "seed": 424242}
    if res == "draft":
        ov["quality"] = "turbo4"
    render(prompt, None, name, model="h3", refs=[api_upload(still)], ext=".mp4", override=ov)


def obj_desc(t):
    if t.get("o_kind") not in MADE_OBJECTS:          # an animal or a plant isn't painted metal
        t = dict(t)
        t.pop("o_material", None)
    return P.compose_obj_desc(t)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "all"
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    want = lambda x: not only or x in only
    os.makedirs(OUT, exist_ok=True)
    style3d = P.style("animated3d")["style_prompt"]
    if what in ("styles", "all"):
        for s in P.STYLES:
            if want(s["id"]):
                print("style", s["id"])
                render("%s. %s" % (TEST, s["style_prompt"]), "4:3", "style_" + s["id"])
    if what in ("options", "all"):                      # every picture-able character field
        fields = [f["k"] for f in P.CHARACTER if f["type"] in ("one", "many") and f["k"] not in SKIP_FIELDS]
        for f, opt in opt_list(P.CHARACTER, fields):
            if not want(P.slug(opt)):
                continue
            fk = f["k"]
            t = dict(OPTION_BASE)
            scene = ""
            if fk == "kind":
                t.update(KIND_BASE.get(opt, {}))
                if opt not in P.PEOPLE:
                    for k in ("hair", "haircolor", "age", "gender"):
                        t.pop(k, None)
            if fk == "role":
                extra, scene = ROLE_SCENE[opt]
                t.update(extra)
                scene = " The character is %s." % scene
            t.update(OPT_BASE.get((fk, opt), {}))
            if t.get("kind") not in P.PEOPLE:
                for k in ("hair", "haircolor", "age", "gender"):
                    t.pop(k, None)
            t[fk] = [opt] if f["type"] == "many" else opt
            focus = ("" if fk in ("kind", "role") else " Most important: %s %s." % (f["label"].lower(), opt))
            print("option", fk, opt)
            render("%sCartoon character design of %s.%s%s Friendly, appealing, plain soft background, no text. %s"
                   % (OPTION_FRAME.get(fk, "Full body, centred. "), P.compose_desc(t), scene, focus, style3d), "1:1",
                   "%s__%s" % (fk, P.slug(opt)), size="standard")
    if what in ("objects", "all"):
        for f, opt in opt_list(P.OBJECT, OBJ_FIELDS):
            if not want(P.slug(opt)):
                continue
            t = dict(OBJ_BASE)
            t[f["k"]] = [opt] if f["type"] == "many" else opt
            print("object", f["k"], opt)
            render(OBJ_TPL.format(d=obj_desc(t), style=style3d), "1:1", "%s__%s" % (f["k"], P.slug(opt)), size="standard")
    if what in ("stylevideos", "all"):
        for st in P.STYLES:
            still = os.path.join(OUT, "style_%s.jpg" % st["id"])
            if want(st["id"]) and os.path.isfile(still):
                print("style video", st["id"])
                h3_clip(FOX_MOTION, still, "style_" + st["id"], aspect="4:3")
    if what in ("moves", "all"):                        # motion: a clip per option, animated from a base still
        base = os.path.join(OUT, "kind__kid.jpg")
        for opt in next(x for x in P.CHARACTER if x["k"] == "move")["opts"]:
            if want(P.slug(opt)) and os.path.isfile(base):
                print("move", opt)
                h3_clip("The little girl moves around a simple bright playroom: %s %s" % (opt, series_help.HELP["move"]["opts"][opt].lower())
                        + " The whole body stays in view. Camera holds steady.", base, "move__" + P.slug(opt))
        for opt in next(x for x in P.OBJECT if x["k"] == "o_move")["opts"]:
            if not want(P.slug(opt)) or have("o_move__" + P.slug(opt), ".mp4"):
                continue
            obj = OBJ_FOR_MOVE.get(opt, "car")
            still = render(OBJ_TPL.format(d=obj_desc(dict(OBJ_BASE, o_kind=obj)), style=style3d), "1:1",
                           "_obase_" + P.slug(obj), size="standard")
            if still:
                print("object move", opt)
                h3_clip("The %s %s — %s Simple bright outdoor setting, the whole %s stays in view. Camera holds steady."
                        % (obj, opt, series_help.HELP["o_move"]["opts"][opt].lower(), obj), still, "o_move__" + P.slug(opt))
    if what in ("voices", "all"):
        for f, opt in opt_list(P.CHARACTER, ("range", "tone", "vaccent")):
            if not want(P.slug(opt)):
                continue
            t = {"range": "sweet middle", "tone": "cheerful", "vaccent": "neutral"}
            t[f["k"]] = opt
            print("voice", f["k"], opt)
            render("children's song, solo singer with a %s voice, simple ukulele and hand claps, 100 BPM --20s\n| lyrics:\n%s"
                   % (P.voice_desc(t), SONG_LYRICS), None, "%s__%s" % (f["k"], P.slug(opt)), model="music3", ext=".mp3",
                   override={})
    if what in ("songs", "all"):
        for f, opt in opt_list(P.SONG, ("genre", "mood", "vocal", "lang")):
            if not want(P.slug(opt)):
                continue
            cfg = dict(SONG_BASE)
            cfg[f["k"]] = opt
            print("song", f["k"], opt)
            render("%s --20s\n| lyrics:\n%s" % (P.song_caption(cfg), SONG_LYRICS_LANG.get(cfg["lang"], SONG_LYRICS)),
                   None, "%s__%s" % (f["k"], P.slug(opt)), model="music3", ext=".mp3", override={})
    if what in ("setup", "all"):
        src = os.path.join(OUT, "style_animated3d.jpg")
        for a in P.ASPECTS:                             # picture shape: the same frame cropped to each shape
            dst = os.path.join(OUT, "aspect__%s.jpg" % P.slug(a))
            if os.path.isfile(src) and not os.path.isfile(dst):
                w, h = (int(x) for x in a.split(":"))
                ff("-i", src, "-vf", "crop='min(iw,ih*%d/%d)':'min(ih,iw*%d/%d)',scale=-2:240" % (w, h, h, w), "-q:v", "4", dst)
                print("  saved", dst)
                mirror(dst)
        if os.path.isfile(src):                         # picture quality: the same 4 s shot at each quality
            for r in ("draft", "standard", "high", "max"):
                print("quality", r)
                h3_clip(FOX_MOTION, src, "res__" + r, aspect="4:3", res=r)
        a1, a2 = os.path.join(OUT, "style_animated3d.mp4"), os.path.join(OUT, "style_cartoon2d.mp4")
        if os.path.isfile(a1) and os.path.isfile(a2):  # shot joins: two shots, dissolved vs hard cut
            norm = "trim=0:3,setpts=PTS-STARTPTS,fps=24,settb=1/24,scale=480:360,setsar=1"
            for j, fc in (("soft", "[0:v]%s[a];[1:v]%s[b];[a][b]xfade=transition=fade:duration=0.6:offset=2.4[v]" % (norm, norm)),
                          ("cut", "[0:v]%s[a];[1:v]%s[b];[a][b]concat=n=2:v=1:a=0[v]" % (norm, norm))):
                dst = os.path.join(OUT, "join__%s.mp4" % j)
                if not os.path.isfile(dst):
                    ff("-i", a1, "-i", a2, "-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "26",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst)
                    print("  saved", dst)
                    mirror(dst)
    if what in ("builder", "all"):
        for k, t in BUILDER.items():
            if want(k):
                print("builder", k)
                render("Full-body character design of %s. Friendly, appealing, standing in a neutral pose on a plain background. %s"
                       % (P.compose_desc(t), style3d), "3:4", k)


if __name__ == "__main__":
    main()
