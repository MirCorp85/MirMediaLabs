"""CAST — the lab's character-sheet builder.

A character PACK is a saved character asset (series_assets layout, so Series ⇄ CAST share one store):

    data/assets/<user>/characters/<slug>-<id>/
        character.json   v2 meta (name, desc, style, files, scores, cast_text, lora, build state, nc)
        hero.png         the master design every other picture is drawn from
        front.png back.png  full-body views (one person per picture)
        face.png            head-and-shoulders close-up
        ref_sheet.png       THE character sheet: headless front (outfit) · back · face close-up
        copycat.png      CopyCat kit: ONE person head-to-shoes on plain grey, 768×1344 (H3's reference ceiling)
        copycat_face.png Fix-faces photo (head-and-shoulders)
        copycat.txt      locked casting description in Openjutsu's describer format
        photos/          the person's own uploads (likeness source)

Only the 3 views the reference sheet needs are drawn — no
3/4, side, face-3/4, expression or turnaround pictures. The sheet shows ONE face (the close-up), so tools don't read it as
several people; CopyCat A/B on one clip: sheet 0.66 vs single full-body 0.59 ArcFace. copycat.png / copycat_face.png are
cut from the same front/face views (no extra render) for the single-view option and Fix faces.

Identity QA (optional) uses InsightFace ArcFace (char_faceid.py, run by a separate Python that has insightface +
onnxruntime + opencv installed; set it in Settings or MML_FACE_PYTHON). Non-commercial licence; packs it touched get
nc:true. Without it the pack is still built, only the identity scores are skipped.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time
import zlib

import core
import series_assets as sa

KIND = "characters"
FACE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "char_faceid.py")
CONSISTENCY_LORA = "qwen-image-2.1-consistency.safetensors"
KIT_W, KIT_H = 768, 1344
CANDIDATES = 4

# Openjutsu's own describer prompt (workflows/simple.api.json) — copycat.txt answers it once, then stays locked.
CASTING_Q = ("Describe the person in this picture for a casting sheet, in one sentence of about 40 words: apparent age and "
             "gender, hair, facial hair, skin tone, build, and their complete outfit including footwear. No preamble, no "
             "background.")

# The edit engine invents tattoos
# on skin it can't see and mirrors the photo. So the hero gets an explicit inventory read from the photo itself.
# Sides: right/left always mean the CHARACTER'S own. A mirror selfie shows the person's own right on the picture's
# right; a normal photo of someone facing the camera shows their right on the picture's left. The vision model only
# reports picture sides + whether it's a mirror shot; the code turns that into the character's own sides.
MARKS_Q = ("First line: 'MIRROR: yes' if this is a photo taken in a mirror (a reflection, e.g. a mirror selfie with the "
           "phone visible), else 'MIRROR: no'. Then list every tattoo, birthmark and piercing on the person, one per line, "
           "each with its exact place on the body and which side of the PICTURE it is on, written as 'picture-left' or "
           "'picture-right' (or 'center'), e.g. 'large black tribal tattoo on the shoulder and upper arm, picture-left'. "
           "If there are none, write 'none'. No preamble.")

STYLES = {
    "photo": "Photorealistic studio photograph, natural skin texture and pores, sharp focus, 85mm lens, soft even key light.",
    "cinematic": "Cinematic film still look, photoreal, subtle film grain, soft studio light, true-to-life colours.",
    "pixar": "Stylised 3D animated feature-film character, soft subsurface skin, appealing proportions, clean studio render.",
    "anime": "Clean modern anime character art, crisp line art, cel shading, flat studio background.",
    "cartoon": "Bright 2D cartoon character design, bold clean outlines, flat colours, friendly shapes.",
}
SAME = ("Exactly the same person as in picture 1: identical face, facial features, skin tone, hair, body shape, outfit, "
        "accessories and footwear. One single person only, no other people, no text, no labels, no props.")
BG = "Plain light-grey seamless studio background, soft even lighting, no shadows on the wall."

# key → (label, aspect, prompt). Every view is redrawn FROM the hero (picture 1), one person per picture.
# Panels must follow the hero exactly (no invented outfits).
# So: the FRONT panel IS the hero (copied, never redrawn), and back / close-up are strict EDITS of the hero that change
# only the camera angle or framing. No wording that names clothing to "keep" (it made the model dress people) and no
# studio-background instruction (it restaged the picture) — everything else must stay exactly as in picture 1.
KEEP = ("Keep everything else exactly as it is in picture 1: the same person, face, hair, skin, the same tattoos only "
        "(add no new tattoos or marks), body shape, and exactly "
        "what they are wearing or not wearing as shown - add nothing, remove nothing, change nothing. Same art style, "
        "colours, lighting and background as picture 1. One single person only, no text.")
VIEWS = [
    ("front", "Front", "3:4", None),                     # = hero.png itself
    ("back", "Back", "9:16", "Show this exact same person from directly behind (back view), with the same framing and "
                             "crop as picture 1 and the same standing pose. Change ONLY the camera angle. " + KEEP),
    ("face", "Close-up", "1:1", "Zoom in to a close-up portrait of this exact same person: head and shoulders, facing the "
                                "camera, the face sharp and filling the frame. Change ONLY the framing. " + KEEP),
]
VIEW_KEYS = [v[0] for v in VIEWS]
HERO_TXT = ("Full-body character design of {who}: {desc}. Standing in a neutral relaxed pose facing the camera, head to shoes "
            "fully in frame, one single person only. " + BG)
HERO_PHOTO = ("Full-body picture of the person in the picture{s} as {who}: keep their exact face, facial features, likeness, "
              "skin tone and hair{desc}. Standing in a neutral relaxed pose facing the camera, head to shoes fully in frame, "
              "one single person only. " + BG)
# The hero is the base version of the original photo (e.g. a mirror selfie leaning forward) turned into a standing
# forward full-body pose the other panels are based on; highest resolution, every detail and likeness kept. So: a strict POSE edit of photo 1 - nothing about clothing or the description is in the
# prompt (the old "put a nice t-shirt" description is what dressed people), only the pose/framing changes.
HERO_POSE = ("Picture 1 shows {who}. Redraw this exact same person as a full-body picture standing upright and facing the "
             "camera straight on: not leaning, shoulders level, both arms relaxed at the sides with empty hands (no phone), "
             "feet slightly apart, the whole body from the top of the head down to the feet in frame with a little floor "
             "visible below the feet (the feet are never cut off), filling the whole "
             "picture (no borders or bars). Change ONLY the pose and the camera framing. Keep the exact same face and "
             "likeness, hair, skin, every tattoo and mark, body shape, and exactly the same clothing as shown, with the same "
             "length, cut, colour, logos and print - add no clothing items and remove none. Do not add shoes, socks, "
             "jewellery or any accessory that is not visible in picture 1: parts of the body hidden in picture 1 (such as "
             "legs or feet) continue exactly what is visible and stay bare where nothing is shown. Same art style (a photo stays a photo, a drawing stays a drawing), colours and "
             "lighting as picture 1, plain neutral background, no mirror. Sharp, high detail. One single person only, no text.")
UPSCALE = "2"           # SeedVR2 2x after every CAST render: the edit engine outputs ~1 MP, this makes it ~4 MP
SHEET_H = 2048          # reference-sheet height (px)
# QA: ArcFace cosine vs the reference face.
QA_MIN = {"hero": 0.5, "front": 0.5, "face": 0.55}          # back views carry no face
QA_MIN_STYLISED = 0.35
ALL_STEPS = ["hero", "views", "kit", "qa"]

_LOCK = threading.Lock()
_ACTIVE = {}            # aid → {"thread", "cancel", "job"}
_HK = {}


# ── store ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _folder(uid, aid):
    return sa._folder(uid, aid)


def read(uid, aid):
    p = _folder(uid, aid)
    m = sa._read(p, KIND) if p else None
    return p, m


def write(p, m):
    return sa._write(p, KIND, m)


def _update(uid, aid, **kw):
    with _LOCK:
        p, m = read(uid, aid)
        if not m:
            return None
        for k, v in kw.items():
            if k == "files":
                m.setdefault("files", {}).update(v)
            elif k == "scores":
                m.setdefault("scores", {}).update(v)
            elif k == "build":
                m["build"] = dict(m.get("build") or {}, **v)
            else:
                m[k] = v
        write(p, m)
        return m


def _log(uid, aid, msg):
    with _LOCK:
        p, m = read(uid, aid)
        if not m:
            return
        b = m.setdefault("build", {})
        b["log"] = (b.get("log") or [])[-60:] + ["%s  %s" % (time.strftime("%H:%M:%S"), msg)]
        b["msg"] = msg
        write(p, m)


def style_text(m):
    return (m.get("style_prompt") or "").strip() if m.get("style") == "custom" else STYLES.get(m.get("style") or "photo", "")


def is_photo_style(m):
    return (m.get("style") or "photo") in ("photo", "cinematic")


def card(uid, aid):
    p, m = read(uid, aid)
    if not m:
        return None
    files = {k: v for k, v in (m.get("files") or {}).items() if v and os.path.isfile(os.path.join(p, v))}
    b = dict(m.get("build") or {})
    if b.get("state") == "running" and aid not in _ACTIVE:      # the lab restarted mid-build
        b["state"] = "stopped"
    scores = m.get("scores") or {}
    face_scores = [v for k, v in scores.items() if k in QA_MIN and isinstance(v, (int, float))]
    return {"id": aid, "name": m.get("name") or "", "desc": m.get("desc") or "", "style": m.get("style") or "",
            "style_prompt": m.get("style_prompt") or "", "source": m.get("source") or "series", "v": m.get("v") or 1,
            "files": files, "scores": scores, "score": round(min(face_scores), 3) if face_scores else None,
            "cast_text": m.get("cast_text") or "", "lora": m.get("lora") or {}, "nc": bool(m.get("nc")),
            "kit": bool(files.get("copycat")), "build": {k: b.get(k) for k in ("state", "step", "msg", "log", "cands", "error",
                                                                                 "flags", "t")},
            "photos": m.get("photos") or [], "ref_panels": m.get("ref_panels") or [], "from": m.get("series"), "created": m.get("created"), "updated": m.get("updated")}


def listing(uid):
    out = [card(uid, r["id"]) for r in sa.listing(uid, KIND)]
    return [c for c in out if c]


# ── @Name calling (like Higgsfield Elements): "@Coach walks into the cafe" in ANY lab prompt ──────────────────────────
# The mention becomes the character's name, the pack's reference sheet is attached as a picture, and the locked casting
# description says who that picture is. Unknown @words (emails, handles) are left exactly as typed.
_MENTION = None


def _mkey(s):
    import re
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def expand_mentions(uid, prompt, start_index=0):
    """→ (prompt, [(picture_path, name)]). Pictures are numbered after the person's own attachments (start_index)."""
    global _MENTION
    import re
    if not prompt or "@" not in prompt:
        return prompt, []
    if _MENTION is None:
        _MENTION = re.compile(r"(?<![\w.@/])@([A-Za-z][\w-]{0,40})")
    packs = {}
    for c in listing(uid):
        if c.get("name"):
            packs.setdefault(_mkey(c["name"]), c)
    if not packs:
        return prompt, []
    found = []                                               # [(card, picture file)] in mention order, once each

    def sub(mt):
        c = packs.get(_mkey(mt.group(1)))
        if not c:
            return mt.group(0)
        if not any(x[0]["id"] == c["id"] for x in found):
            f = c["files"]
            found.append((c, next((k for k in ("ref_sheet", "copycat", "front", "hero") if f.get(k)), None)))
        return c["name"]

    text = _MENTION.sub(sub, prompt)
    refs, notes = [], []
    for c, key in found:
        desc = (c.get("cast_text") or c.get("desc") or "").strip()
        if key:
            p, _ = read(uid, c["id"])
            refs.append((os.path.join(p, c["files"][key]), c["name"]))
            n = start_index + len(refs)
            if key == "ref_sheet":
                what = ("a character reference sheet of %s (outfit, back view, face close-up) - draw ONE %s with that "
                        "face, outfit and build, never the sheet layout itself" % (c["name"], c["name"]))
            else:
                what = c["name"]
            notes.append("Picture %d is %s.%s" % (n, what, (" %s: %s" % (c["name"], desc)) if desc else ""))
        elif desc:
            notes.append("%s: %s" % (c["name"], desc))
    return (text + ("\n\n" + " ".join(notes) if notes else "")), refs


def create(uid, name, desc="", style="photo", style_prompt="", photos=(), hero_upload=False):
    """New pack. photos = [(filename, bytes)] (≤4). hero_upload → the first photo IS the design (already drawn)."""
    aid, p = sa._new(uid, KIND, name or "character")
    saved = []
    if photos:
        os.makedirs(os.path.join(p, "photos"), exist_ok=True)
        for i, (fn, data) in enumerate(list(photos)[:4], 1):
            ext = os.path.splitext(fn or "")[1].lower()
            ext = ext if ext in (".png", ".jpg", ".jpeg", ".webp") else ".png"
            rel = "photos/p%d%s" % (i, ext)
            with open(os.path.join(p, rel), "wb") as f:
                f.write(data)
            saved.append(rel)
    m = {"v": 2, "name": (name or "").strip()[:80] or "Character", "desc": (desc or "").strip()[:1200],
         "style": style if style in STYLES or style == "custom" else "photo", "style_prompt": (style_prompt or "")[:800],
         "source": "photos" if saved else "text", "photos": saved, "files": {}, "scores": {}, "cast_text": "",
         "lora": {}, "build": {"state": "idle", "log": []}, "traits": {}, "voice": "", "built": ""}
    # hero_upload = the picture is already a finished full-body design: use it as the hero untouched. Otherwise the hero
    # step re-poses the photo (standing forward, full body) and changes nothing else - see HERO_POSE.
    if saved and hero_upload:
        hero = _to_png(os.path.join(p, saved[0]), os.path.join(p, "hero.png"))
        if hero:
            m["files"]["hero"] = "hero.png"
            m["source"] = "upload"
            m["hero_mode"] = "upload"
    write(p, m)
    return aid


def _to_png(src, dst, fit=None):
    from PIL import Image
    try:
        im = Image.open(src)
        im = im.convert("RGB")
        if fit:
            im = _fit(im, *fit)
        im.save(dst, "PNG")
        return dst
    except Exception:
        return None


def _fit(im, w, h):
    """Letterbox into w×h with the picture's own corner colour (the plain studio grey)."""
    from PIL import Image
    corner = im.getpixel((2, 2))
    s = min(w / im.width, h / im.height)
    r = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    out = Image.new("RGB", (w, h), corner)
    out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return out


def _pose_canvas(src, dst):
    """The photo on a 2:3 (full-body) canvas. Edits keep the input's shape, so a waist-up selfie needs room below for
    the legs/feet: the photo goes at the top, plain neutral grey fills the rest (the edit repaints it)."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = im.size
    if h >= w * 1.5:                                    # already tall: widen to 2:3
        W, H = int(h / 1.5), h
        out = Image.new("RGB", (W, H), (200, 200, 200))
        out.paste(im, ((W - w) // 2, 0))
    else:                                               # extend downwards
        W, H = w, int(w * 1.5)
        out = Image.new("RGB", (W, H), (200, 200, 200))
        out.paste(im, (0, 0))
    out.save(dst, "PNG")
    return dst


# ── render through the lab queue (same path as the Series runner) ────────────────────────────────────────────────────
class Cancelled(Exception):
    pass


def _ref_of(uid, p, rel):
    """A pack file → a ref the lab can attach (copied, owned by the person)."""
    src = os.path.join(p, rel)
    if not os.path.isfile(src):
        raise ValueError("missing %s" % rel)
    name = _HK["store_ref"]("cast_" + os.path.splitext(os.path.basename(rel))[0], os.path.splitext(rel)[1].lower(), uid)
    shutil.copy2(src, os.path.join(core.REFS, name))
    return name


def _render(uid, aid, prompt, refs, aspect, seed=None, lora=False, size="hd", upscale=None):
    # NB: a single-picture "qimg" edit is routed to FLUX-3 Klein (Studio edit app), which ignores LoRAs — so the Qwen
    # consistency LoRA only matters for multi-picture edits (e.g. a hero drawn from several photos).
    """Submit one Qwen-Image render and wait. → path of the finished picture (unwatermarked copy when there is one)."""
    st = _ACTIVE.get(aid) or {}
    over = {"mode": "edit" if refs else "generate", "aspect": aspect, "size": size, "model": "base"}
    if seed is not None:
        over["seed"] = int(seed) % 4294967295
    if upscale:
        over["upscale"] = upscale
    # internal + clean: a building block, not a finished piece — no chat card, no watermark, and _take() pulls it out
    # of the library (only the final 3-view sheet goes to the library)
    req = {"model": "qimg", "prompt": prompt, "refs": refs, "override": over, "literal": True, "internal": True, "clean": True}
    if lora and refs:
        req["loras"] = [{"file": CONSISTENCY_LORA, "strength": 0.8}]
    while True:
        if st.get("cancel"):
            raise Cancelled()
        j, err, busy = _HK["submit"](uid, req)
        if busy:
            time.sleep(5)
            continue
        if err:
            raise RuntimeError(err)
        break
    jid = j["id"]
    st["job"] = jid
    while True:
        if st.get("cancel"):
            _HK["cancel"](jid)
            raise Cancelled()
        s = _HK["job"](jid) or {}
        if s.get("status") == "done":
            break
        if s.get("status") in ("error", "cancelled"):
            raise RuntimeError(s.get("error") or s.get("status"))
        time.sleep(2)
    st["job"] = None
    pics = [str(f).split("/")[-1] for f in s.get("files") or [] if str(f).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    if not pics:
        raise RuntimeError("the render made no picture")
    return _take(uid, aid, pics)


def _take(uid, aid, names):
    """Move a CAST render out of the lab library into the pack's .work folder (it is a building block, not a
    finished piece). → path of the first picture, preferring the unwatermarked copy."""
    p, _ = read(uid, aid)
    work = os.path.join(p, ".work")
    os.makedirs(work, exist_ok=True)
    first = None
    ix = core.index()
    for n in names:
        lib, clean = os.path.join(core.LIB, n), os.path.join(core.REFS, "ref_clean_" + n)
        dst = os.path.join(work, n)
        if os.path.isfile(clean):                      # unwatermarked copy wins
            shutil.move(clean, dst)
            if os.path.isfile(lib):
                os.remove(lib)
        elif os.path.isfile(lib):
            shutil.move(lib, dst)
        ix.pop(n, None)
        first = first or (dst if os.path.isfile(dst) else None)
    core.save_json(core.INDEX_FILE, ix)
    if not first:
        raise RuntimeError("the render's picture is missing")
    return first


def _lib_put(uid, aid, m, key, src, what):
    """One library copy per pack and kind (key "lib_sheet" / "lib_hero"); a rebuild/redo replaces the previous one."""
    old = m.get(key)
    if old and os.path.isfile(os.path.join(core.LIB, old)):
        shutil.move(os.path.join(core.LIB, old), core.safe_path(os.path.join(core.TRASH, old)))   # recoverable
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", (m.get("name") or "char").lower()).strip("_") or "char"
    name = core.new_name("cast_%s%s" % (slug, "_hero" if key == "lib_hero" else ""), ".png")
    shutil.copyfile(src, os.path.join(core.LIB, name))      # new file date: the library sorts by it
    core.index_add(name, {"model": "cast", "prompt": "%s - %s" % (m.get("name") or "", what),
                          "created": time.time(), "user": uid or "owner", "mode": "cast", "cast": aid})
    _update(uid, aid, **{key: name})


def _to_library(uid, aid, p, m, only=None):
    """What a pack puts in the library: its finished 3-view sheet AND its hero as a separate picture."""
    f = m.get("files") or {}
    if only in (None, "sheet") and os.path.isfile(os.path.join(p, "ref_sheet.png")):
        _lib_put(uid, aid, m, "lib_sheet", os.path.join(p, "ref_sheet.png"),
                 "character sheet (front without the head, back, close-up)")
        m = read(uid, aid)[1]
    hero = f.get("hero") or f.get("front")
    if only in (None, "hero") and hero and os.path.isfile(os.path.join(p, hero)):
        _lib_put(uid, aid, m, "lib_hero", os.path.join(p, hero), "hero (full body)")


def _seed(aid, salt=0):
    return (zlib.crc32(aid.encode()) + salt * 7919) % 4294967295


# ── build steps ────────────────────────────────────────────────────────────────────────────────────────────────────
def _who(m):
    return m.get("name") or "the character"


def step_hero(uid, aid, p, m):
    if (m.get("files") or {}).get("hero"):
        _log(uid, aid, "hero already set — keeping it")
        return True
    st = style_text(m)
    photos = [x for x in m.get("photos") or [] if os.path.isfile(os.path.join(p, x))]
    if photos:                                          # base version: the photo re-posed standing forward, nothing else
        canvas = _pose_canvas(os.path.join(p, photos[0]), os.path.join(p, ".pose_in.png"))
        ref = _ref_of(uid, p, os.path.relpath(canvas, p))
        marks, own = marks_text(os.path.join(p, photos[0]))
        _log(uid, aid, "marks in your photo (character's own sides): %s" % (own or "(couldn't read)"))
        prompt = HERO_POSE.format(who=_who(m))
        if marks == "none":
            prompt += " The person has NO tattoos: all skin is bare."
        elif marks:
            prompt += (" Tattoos and marks - ONLY these, nothing else: %s. Every other part of the skin (the other arm, "
                       "any forearm not listed, both legs, the torso) is bare skin with no tattoo." % marks)
        _update(uid, aid, marks=own)
        _log(uid, aid, "hero: your photo re-posed standing forward, full body (same face, body and clothes) + 2x upscale")
        out = _render(uid, aid, prompt, [ref], "2:3", _seed(aid), upscale=UPSCALE)
        _to_png(out, os.path.join(p, "hero.png"))
        try:
            os.remove(canvas)
        except OSError:
            pass
        _update(uid, aid, files={"hero": "hero.png"}, hero_mode="pose")
        return True
    if not m.get("desc"):
        raise ValueError("describe the character (or drop photos) first")
    cands = []
    for i in range(CANDIDATES):
        _log(uid, aid, "hero candidate %d/%d" % (i + 1, CANDIDATES))
        out = _render(uid, aid, HERO_TXT.format(who=_who(m), desc=m["desc"]) + " " + st, [], "3:4", _seed(aid, i))
        rel = "cand_%d.png" % (i + 1)
        _to_png(out, os.path.join(p, rel))
        cands.append(rel)
        _update(uid, aid, build={"cands": cands})
    _update(uid, aid, build={"state": "pick", "msg": "pick the hero you like — the rest builds from it"})
    return False                                            # stop: the person picks, then the build resumes


def _view(uid, aid, p, m, key, salt=0):
    label, aspect, tpl = next((v[1], v[2], v[3]) for v in VIEWS if v[0] == key)
    if tpl is None:                                     # front = the hero itself: exactly how the hero looks
        _log(uid, aid, "view: %s (the hero itself)" % label)
        _to_png(os.path.join(p, m["files"]["hero"]), os.path.join(p, key + ".png"))
        _update(uid, aid, files={key: key + ".png"})
        return
    hero = _ref_of(uid, p, m["files"]["hero"])
    _log(uid, aid, "view: %s%s" % (label, " (retry)" if salt else ""))
    out = _render(uid, aid, "Picture 1 shows %s. " % _who(m) + tpl, [hero], aspect, _seed(aid, 10 + salt), upscale=UPSCALE)
    _to_png(out, os.path.join(p, key + ".png"))
    _update(uid, aid, files={key: key + ".png"})


def step_views(uid, aid, p, m, only=None):
    if not (m.get("files") or {}).get("hero"):
        raise ValueError("make the hero first")
    for key in only or VIEW_KEYS:
        _view(uid, aid, p, m, key)
    return True


def _face_py():
    """The Python that runs char_faceid.py (needs insightface + onnxruntime + opencv). '' = identity check off."""
    p = str(os.environ.get("MML_FACE_PYTHON") or core.prefs().get("face_python") or "").strip().strip('"')
    return p if p and os.path.isfile(p) else ""


def face_box(path):
    FACE_PY = _face_py()
    if not FACE_PY:
        return None                                   # no face helper: the sheet keeps the full front panel
    r = subprocess.run([FACE_PY, FACE_SCRIPT, "box", "--img", path], capture_output=True, text=True, timeout=300,
                       creationflags=core.NO_WINDOW)
    res = json.loads(((r.stdout or "").strip().splitlines() or ["{}"])[-1])
    return res.get("box") if res.get("ok") else None


def compose_refsheet(p, m):
    """3-panel reference sheet: headless front (outfit) · back · face close-up (identity). ONE face in the picture, so
    identity comes from the big sharp portrait, not averaged with a small full-body face. THE pack's character sheet."""
    from PIL import Image
    f = m.get("files") or {}
    if not (f.get("front") and f.get("back") and f.get("face")):
        return None
    front = Image.open(os.path.join(p, f["front"])).convert("RGB")
    box = face_box(os.path.join(p, f["front"]))
    if box:                                             # cut just under the chin, keep the neckline
        front = front.crop((0, min(front.height - 10, int(box[3] + (box[3] - box[1]) * 0.12)), front.width, front.height))
    back = Image.open(os.path.join(p, f["back"])).convert("RGB")
    face = Image.open(os.path.join(p, f["face"])).convert("RGB")
    H, gap = SHEET_H, 6
    panels = [front, back, face]
    panels = [im.resize((max(1, int(im.width * H / im.height)), H), Image.LANCZOS) for im in panels]
    w = sum(im.width for im in panels) + gap * 2
    out = Image.new("RGB", (w, H), (235, 235, 235))
    x, spans = 0, []
    for key, im in zip(("front", "back", "face"), panels):
        out.paste(im, (x, 0))
        spans.append({"view": key, "x0": round(x / w, 4), "x1": round((x + im.width) / w, 4)})   # for per-panel Redo
        x += im.width + gap
    out.save(os.path.join(p, "ref_sheet.png"), "PNG")
    return "ref_sheet.png", spans


def marks_text(path):
    """Tattoo / mark inventory of the source photo in the CHARACTER'S own sides, plus where each lands in a camera-facing
    hero. → ('none' | 'a; b; ...' | '', own_sides_summary). '' when the vision model fails."""
    try:
        with open(path, "rb") as h:
            b64 = base64.b64encode(h.read()).decode()
        t = str(core.ask(MARKS_Q, "You inspect photos precisely.", timeout=240, images=[b64]) or "")
    except Exception:
        return "", ""
    lines = [l.strip(" -*.") for l in t.splitlines() if l.strip(" -*.")]
    mirror = bool(lines and re.match(r"(?i)mirror\s*:\s*yes", lines[0]))
    lines = [l for l in lines if not re.match(r"(?i)mirror\s*:", l)]
    if not lines or all(l.lower() == "none" for l in lines):
        return "none", "none"
    out, own = [], []
    for l in lines:
        if l.lower().startswith("none"):
            continue
        m = re.search(r"(?i)picture[- ](left|right)", l)
        if not m:
            out.append(l)
            own.append(l)
            continue
        pic = m.group(1).lower()
        side = pic if mirror else ("left" if pic == "right" else "right")        # the character's own side
        hero_pic = "right" if side == "left" else "left"                         # facing the camera in the hero
        body = re.sub(r"(?i),?\s*(on the\s+)?picture[- ](left|right)(\s+side)?", "", l).strip(" ,")
        out.append("%s on the person's own %s side (seen on the picture's %s in this front view)" % (body, side.upper(), hero_pic))
        own.append("%s, own %s" % (body, side))
    return "; ".join(out)[:600], "; ".join(own)[:400]


def casting_text(path):
    with open(path, "rb") as h:
        b64 = base64.b64encode(h.read()).decode()
    t = core.ask(CASTING_Q, "You describe people precisely for film casting.", timeout=240, images=[b64])
    return " ".join(str(t or "").split())[:600]


def step_kit(uid, aid, p, m):
    f = m.get("files") or {}
    src = f.get("front") or f.get("hero")
    if not src:
        raise ValueError("make the front view first")
    _to_png(os.path.join(p, src), os.path.join(p, "copycat.png"), fit=(KIT_W, KIT_H))
    files = {"copycat": "copycat.png"}
    try:
        rs = compose_refsheet(p, m)
        if rs:
            files["ref_sheet"] = rs[0]
            _update(uid, aid, ref_panels=rs[1])
            _to_library(uid, aid, p, read(uid, aid)[1])
    except Exception as e:
        _log(uid, aid, "reference sheet skipped (%s)" % str(e)[:120])
    if f.get("face"):
        _to_png(os.path.join(p, f["face"]), os.path.join(p, "copycat_face.png"))
        files["copycat_face"] = "copycat_face.png"
    _update(uid, aid, files=files)
    if not m.get("cast_locked"):
        _log(uid, aid, "writing the locked casting description")
        try:
            txt = casting_text(os.path.join(p, "copycat.png"))
            if txt:
                with open(os.path.join(p, "copycat.txt"), "w", encoding="utf-8") as h:
                    h.write(txt)
                _update(uid, aid, cast_text=txt, files={"copycat_txt": "copycat.txt"})
        except Exception as e:
            _log(uid, aid, "casting description skipped (%s) — CopyCat will describe the picture itself" % str(e)[:120])
    return True


def face_score(ref_paths, img_paths, emb=None):
    FACE_PY = _face_py()
    if not FACE_PY:
        raise RuntimeError("identity check needs the optional face helper (Settings → face_python)")
    cmd = [FACE_PY, FACE_SCRIPT, "score", "--ref", ",".join(ref_paths), "--imgs", ",".join(img_paths)]
    if emb:
        cmd += ["--emb", emb]
    core.gpu_wait("cast face check")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=core.NO_WINDOW)
    line = (r.stdout or "").strip().splitlines()[-1:] or ["{}"]
    res = json.loads(line[0])
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or (r.stderr or "")[-200:])
    return res["scores"]


def step_qa(uid, aid, p, m, retry=True):
    f = m.get("files") or {}
    photos = [os.path.join(p, x) for x in m.get("photos") or [] if os.path.isfile(os.path.join(p, x))]
    ref = photos if m.get("source") == "photos" and photos else [os.path.join(p, f["hero"])]
    keys = [k for k in QA_MIN if f.get(k)]
    if not _face_py():
        _log(uid, aid, "identity check skipped (optional InsightFace helper not set up)")
        return True
    _log(uid, aid, "identity check (ArcFace) on %d pictures" % len(keys))
    raw = face_score(ref, [os.path.join(p, f[k]) for k in keys], emb=os.path.join(p, "face.npy"))
    scores = {k: raw.get(os.path.basename(f[k])) for k in keys}
    _update(uid, aid, scores=scores, nc=True, files={"face_emb": "face.npy"})
    floor = (lambda k: QA_MIN[k]) if is_photo_style(m) else (lambda k: min(QA_MIN[k], QA_MIN_STYLISED))
    weak = [k for k in keys if k != "hero" and (scores[k] is None or scores[k] < floor(k))]
    if weak and retry:
        _log(uid, aid, "redrawing weak views: %s" % ", ".join(weak))
        for k in weak:
            old = scores[k]
            keep = os.path.join(p, k + ".prev.png")
            shutil.copy2(os.path.join(p, f[k]), keep)
            _view(uid, aid, p, read(uid, aid)[1], k, salt=1)
            new = face_score(ref, [os.path.join(p, k + ".png")]).get(k + ".png")
            if old is not None and (new is None or new < old):      # the retry is worse → keep the first one
                shutil.move(keep, os.path.join(p, k + ".png"))
                new = old
            elif os.path.isfile(keep):
                os.remove(keep)
            scores[k] = new
        _update(uid, aid, scores=scores)
        m = read(uid, aid)[1]
        step_kit(uid, aid, p, dict(m, cast_locked=True) if m.get("cast_text") else m)   # faces may have changed
    flags = [k for k in keys if k != "hero" and (scores.get(k) is None or scores[k] < floor(k))]
    _update(uid, aid, build={"flags": flags})
    _log(uid, aid, "identity: " + ", ".join("%s %s" % (k, "—" if scores.get(k) is None else "%.2f" % scores[k]) for k in keys))
    return True


# ── LoRA dataset: varied pictures of the SAME character, ArcFace-filtered, captioned with a trigger word ─────────────
# Trainer-agnostic folder (img + same-name .txt) — ai-toolkit / OneTrainer / kohya all read it.
DATASET_SHOTS = [
    ("walking towards the camera on a city street, daytime", "3:4"), ("sitting on a wooden chair, relaxed, indoors", "3:4"),
    ("laughing, close-up portrait, warm window light", "1:1"), ("arms crossed, confident, studio portrait", "3:4"),
    ("looking over the shoulder, three-quarter back view, park", "3:4"), ("serious expression, close-up, dramatic side light", "1:1"),
    ("waving hello, full body, sunny beach", "3:4"), ("reading a book on a sofa, cosy evening lamp light", "4:3"),
    ("running, full body, motion, sports field", "3:4"), ("smiling, medium shot, cafe background, soft light", "3:4"),
    ("profile view, looking left, neutral grey background", "1:1"), ("surprised expression, close-up, bright light", "1:1"),
    ("standing in the rain at night, neon street lights", "3:4"), ("cooking in a kitchen, medium shot", "4:3"),
    ("dancing, full body, colourful party lights", "3:4"), ("thoughtful, chin on hand, close-up, library", "1:1"),
    ("low angle full body, heroic pose, sky behind", "3:4"), ("high angle medium shot, looking up at the camera", "3:4"),
    ("sitting on stairs outdoors, golden hour", "3:4"), ("talking, mouth open mid-sentence, medium close-up", "1:1"),
]
DATASET_MIN = 0.5


def trigger_of(m, aid):
    import re
    return "cst" + re.sub(r"[^a-z0-9]", "", (m.get("name") or "char").lower())[:10] + aid[-4:]


def step_dataset(uid, aid, p, m):
    f = m.get("files") or {}
    if not f.get("hero"):
        raise ValueError("make the hero first")
    trig = trigger_of(m, aid)
    ds = os.path.join(p, "lora_dataset")
    os.makedirs(ds, exist_ok=True)
    who = "%s person" % trig if is_photo_style(m) else "%s character" % trig
    kept = []
    for k in ("front", "face", "hero"):     # the pack's own clean views first
        if f.get(k):
            shutil.copy2(os.path.join(p, f[k]), os.path.join(ds, "%s.png" % k))
            open(os.path.join(ds, "%s.txt" % k), "w", encoding="utf-8").write("%s, %s view, plain grey background" % (who, k.replace("_", " ")))
            kept.append(k)
    hero = _ref_of(uid, p, f["hero"])
    ref = [os.path.join(p, x) for x in m.get("photos") or []] if m.get("source") == "photos" else [os.path.join(p, f["hero"])]
    for i, (shot, aspect) in enumerate(DATASET_SHOTS):
        _log(uid, aid, "dataset %d/%d: %s" % (i + 1, len(DATASET_SHOTS), shot))
        out = _render(uid, aid, "The same person as in picture 1, %s. %s %s" % (shot, SAME.split(".")[0] + ".", style_text(m)),
                      [hero], aspect, _seed(aid, 100 + i))
        name = "v%02d.png" % (i + 1)
        _to_png(out, os.path.join(ds, name))
        sc = face_score(ref, [os.path.join(ds, name)]).get(name)
        if sc is not None and sc < DATASET_MIN and "profile" not in shot and "back" not in shot:
            os.remove(os.path.join(ds, name))
            _log(uid, aid, "  dropped (identity %.2f)" % sc)
            continue
        open(os.path.join(ds, "v%02d.txt" % (i + 1)), "w", encoding="utf-8").write("%s, %s" % (who, shot))
        kept.append(name)
    _update(uid, aid, lora=dict(m.get("lora") or {}, trigger=trig, dataset="lora_dataset", images=len(kept), status="dataset"))
    _log(uid, aid, "LoRA dataset ready: %d pictures, trigger '%s'" % (len(kept), trig))
    return True


STEP_FN = {"hero": step_hero, "views": step_views, "kit": step_kit, "qa": step_qa, "dataset": step_dataset}


def _run(uid, aid, steps, only_views=None):
    try:
        for s in steps:
            _update(uid, aid, build={"state": "running", "step": s, "error": None, "t": time.time()})
            p, m = read(uid, aid)
            if not m:
                return
            ok = step_views(uid, aid, p, m, only_views) if s == "views" and only_views else STEP_FN[s](uid, aid, p, m)
            if ok is False:
                return
        _update(uid, aid, build={"state": "done", "step": None, "msg": "pack ready", "t": time.time()})
        _log(uid, aid, "pack ready")
    except Cancelled:
        _update(uid, aid, build={"state": "stopped", "msg": "stopped"})
    except Exception as e:
        _update(uid, aid, build={"state": "error", "error": str(e)[:400], "msg": "failed: %s" % str(e)[:160]})
    finally:
        _ACTIVE.pop(aid, None)
        try:                                            # renders already copied into the pack: drop the work folder
            work = os.path.join(read(uid, aid)[0], ".work")
            if os.path.basename(work) == ".work" and os.path.isdir(work):
                shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass


def start_build(uid, aid, steps=None, only_views=None):
    if aid in _ACTIVE:
        raise ValueError("already building")
    p, m = read(uid, aid)
    if not m:
        raise ValueError("no such character")
    steps = [s for s in (steps or ALL_STEPS) if s in STEP_FN]
    if not steps:
        raise ValueError("nothing to build")
    if m.get("v", 1) < 2:                                   # an older Series character: upgrade in place
        m.update(v=2, style=m.get("style") if m.get("style") in STYLES else "custom",
                 style_prompt=m.get("style_prompt") or "", source=m.get("source") or "series", photos=m.get("photos") or [])
        write(p, m)
    photos = [x for x in m.get("photos") or [] if os.path.isfile(os.path.join(p, x))]
    if m.get("source") == "photos" and photos and not only_views and "views" in steps and not m.get("hero_mode"):
        # a pack whose hero predates the strict pose-only hero (its clothes drifted): make the hero again from the photo
        # first. The old one is kept as hero_prev.png.
        hp = os.path.join(p, (m.get("files") or {}).get("hero") or "hero.png")
        if os.path.isfile(hp):
            shutil.copyfile(hp, os.path.join(p, "hero_prev.png"))
        with _LOCK:
            m = read(uid, aid)[1]
            (m.get("files") or {}).pop("hero", None)
            write(p, m)
        steps = ["hero"] + [s for s in steps if s != "hero"]
    st = {"cancel": False, "job": None}
    _ACTIVE[aid] = st
    _update(uid, aid, build={"state": "running", "step": steps[0], "error": None, "flags": [], "t": time.time()})
    st["thread"] = threading.Thread(target=_run, args=(uid, aid, steps, only_views), daemon=True, name="cast-" + aid[-8:])
    st["thread"].start()


def pick(uid, aid, cand):
    p, m = read(uid, aid)
    cands = (m or {}).get("build", {}).get("cands") or []
    if cand not in cands:
        raise ValueError("pick one of the candidates")
    shutil.copy2(os.path.join(p, cand), os.path.join(p, "hero.png"))
    _update(uid, aid, files={"hero": "hero.png"}, build={"state": "idle"})
    start_build(uid, aid, ["views", "kit", "qa"])


def cancel(aid):
    st = _ACTIVE.get(aid)
    if st:
        st["cancel"] = True
        if st.get("job"):
            _HK["cancel"](st["job"])


def kit(uid, aid):
    """What CopyCat (and any tool) needs from a pack."""
    p, m = read(uid, aid)
    if not m:
        return None
    f = m.get("files") or {}
    url = lambda k: ("/mlab/api/assets/file?id=%s&f=%s&t=%d" % (aid, f[k], int(m.get("updated") or 0))) if f.get(k) else None
    cast = m.get("cast_text") or ""
    if not cast and os.path.isfile(os.path.join(p, "copycat.txt")):
        cast = open(os.path.join(p, "copycat.txt"), encoding="utf-8").read().strip()
    return {"id": aid, "name": m.get("name"), "hero": url("hero") or url("front"),     # thumbnail in tool UIs
            "picture": url("copycat") or url("front") or url("hero"),
            "face": url("copycat_face") or url("face"), "text": cast, "ref_sheet": url("ref_sheet"), "nc": bool(m.get("nc")),
            "score": card(uid, aid)["score"], "refs_h3": [u for u in (url("front"), url("face"), url("back"))
                                                          if u]}


# ── Flask ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    from flask import request, jsonify
    _HK.update(hk)

    def U():
        return hk["uid"]()

    def body():
        return request.get_json(silent=True) or {}

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    @app.route("/cast")
    def cast_page():
        return hk["static"]("cast.html")

    @app.route("/api/char")
    def ch_list():
        rows = listing(U())
        if request.args.get("kits"):
            rows = [r for r in rows if r["kit"] or r["files"].get("hero")]
        return jsonify({"characters": rows, "styles": list(STYLES) + ["custom"], "views": [[v[0], v[1]] for v in VIEWS]})

    @app.route("/api/char/get")
    def ch_get():
        c = card(U(), request.args.get("id"))
        return jsonify(c) if c else oops("no such character", 404)

    @app.route("/api/char/new", methods=["POST"])
    def ch_new():
        if request.files:
            fs = [f for f in request.files.getlist("photos") if f and f.filename][:4]
            photos = [(f.filename, f.read()) for f in fs]
            if sum(len(d) for _, d in photos) > 60 * 1024 * 1024:
                return oops("photos are too big (60 MB total)")
            fm = request.form
        else:
            photos, fm = [], body()
        name, desc = str(fm.get("name") or "").strip(), str(fm.get("desc") or "").strip()
        if not photos and not desc:
            return oops("drop photos or describe the character")
        aid = create(U(), name or "Character", desc, str(fm.get("style") or "photo"), str(fm.get("style_prompt") or ""),
                     photos, str(fm.get("hero_upload") or "") in ("1", "true", "on"))
        if str(fm.get("build", "1")) in ("1", "true", "on"):
            start_build(U(), aid)
        return jsonify(card(U(), aid))

    @app.route("/api/char/build", methods=["POST"])
    def ch_build():
        b = body()
        try:
            only = [k for k in (b.get("views") or []) if k in VIEW_KEYS] or None
            start_build(U(), str(b.get("id") or ""), b.get("steps"), only)
        except Exception as e:
            return oops(e)
        return jsonify(card(U(), b.get("id")))

    @app.route("/api/char/pick", methods=["POST"])
    def ch_pick():
        b = body()
        try:
            pick(U(), str(b.get("id") or ""), str(b.get("cand") or ""))
        except Exception as e:
            return oops(e)
        return jsonify(card(U(), b.get("id")))

    @app.route("/api/char/cancel", methods=["POST"])
    def ch_cancel():
        cancel(str(body().get("id") or ""))
        return jsonify({"ok": True})

    @app.route("/api/char/update", methods=["POST"])
    def ch_update():
        b = body()
        aid = str(b.get("id") or "")
        p, m = read(U(), aid)
        if not m:
            return oops("no such character", 404)
        kw = {}
        for k, n in (("name", 80), ("desc", 1200), ("style_prompt", 800)):
            if k in b:
                kw[k] = str(b[k] or "").strip()[:n]
        if b.get("style") in list(STYLES) + ["custom"]:
            kw["style"] = b["style"]
        if "cast_text" in b:                                   # the person's own casting words win and stay locked
            txt = " ".join(str(b["cast_text"] or "").split())[:600]
            kw.update(cast_text=txt, cast_locked=bool(txt))
            with open(os.path.join(p, "copycat.txt"), "w", encoding="utf-8") as h:
                h.write(txt)
        _update(U(), aid, **kw)
        return jsonify(card(U(), aid))

    @app.route("/api/char/hero", methods=["POST"])
    def ch_hero():
        """Replace the hero with an uploaded picture (an already-drawn design) or a library/ref picture."""
        aid = str(request.form.get("id") or "")
        p, m = read(U(), aid)
        f = request.files.get("file")
        if not m or not f:
            return oops("pick a character and a picture")
        tmp = os.path.join(p, "_upload" + (os.path.splitext(f.filename)[1].lower() or ".png"))
        f.save(tmp)
        ok = _to_png(tmp, os.path.join(p, "hero.png"))
        os.remove(tmp)
        if not ok:
            return oops("couldn't read that picture")
        _update(U(), aid, files={"hero": "hero.png"}, source=m.get("source") if m.get("photos") else "upload",
                hero_mode="upload")             # a hand-picked hero: Rebuild all never remakes it
        try:
            _to_library(U(), aid, p, read(U(), aid)[1], only="hero")
        except Exception as e:
            print("[cast] hero library copy failed: %s" % e)
        return jsonify(card(U(), aid))

    @app.route("/api/char/kit")
    def ch_kit():
        k = kit(U(), request.args.get("id"))
        return jsonify(k) if k else oops("no such character", 404)

    @app.route("/api/char/delete", methods=["POST"])
    def ch_delete():
        aid = str(body().get("id") or "")
        cancel(aid)
        sa.delete(U(), aid)
        return jsonify({"ok": True})
