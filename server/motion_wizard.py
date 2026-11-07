r"""MOTION STUDIO — the step-by-step producer behind /mlab/motion (static/motion.html), modelled on a step-by-step
REEL producers: one project per video, a pipeline with checkpoints, every step redoable, and ONE setting that changes the
whole look — the motion STYLE (signature / grid / liquid / paper, tokens in motion/mg_assets/styles.json).

  script      brief → the writer brain writes the beats: one narration line each, a beat kind, and the VISUALS cued to words   [checkpoint]
  voice       Kokoro reads every line → Whisper word timings → each visual's `at` = the start of its cue word
  assets      every visual resolves to a styled picture: AI cut-out (public/mg/art) → styled vector (public/mg/vec, 1,539
              shapes, every word covered) → a Lucide line icon → styled text. Missing hero art is generated on demand.  [checkpoint]
  render      MIR MOTION project (mg-* scenes + VO track + optional music bed) saved in Motion Studio → library render  [checkpoint]
              a copy lands in the optional export folder (motion_export_dir)
  publish     optional Social draft (approve-only in Social as always)

Projects: data/motion_wizard/<uid>/<id>.json. Reuses remotion.py (save_project / start_job / clean), tts.py, series_audio
(Whisper) and motion_util._to_lib. Automatic mode runs through to the final cut without stopping.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

import core, motion_mint, motion_kits, motion_library, motion_util, remotion

D = os.path.join(core.DATA, "motion_wizard")
import engines

OUT_DIR = engines.path("motion_export_dir", "MML_MOTION_EXPORT", "")   # optional: a folder that also gets every finished film
ENGINE = remotion.ENGINE
MG = os.path.join(ENGINE, "public", "mg")
ART_PY = engines.path("mg_art_python", "MML_ART_PY", "")   # optional venv with rembg (AI cut-outs); empty = vector art only
STAGES = ["script", "voice", "assets", "render", "publish", "done"]
KINDS = {"diorama": 0, "title": 4.5, "stat": 4.5, "visuals": 4, "relation": 5, "action": 5.5, "list": 6, "compare": 5, "quote": 5, "endcard": 6}
# animated characters (src/mg/puppet.tsx ACTIONS) — keep in sync
ACTIONS = {"speech": "gives a speech at a podium (politicians, leaders, historic speeches)", "talk": "talks / explains with gestures",
           "wave": "waves hello", "point": "presents, pointing at a rising chart", "walk": "walks", "run": "runs fast",
           "score": "runs in and scores a soccer goal", "shoot": "jump-shoots a basketball", "throw": "throws a ball",
           "celebrate": "celebrates, arms up, confetti", "jump": "jumps for joy", "dance": "dances", "think": "thinks, hand on chin",
           "read": "reads a book", "type": "types at a laptop (coding, writing, work)", "lift": "lifts weights",
           "sad": "is sad, head down", "handshake": "two people shake hands (deal, treaty)", "chat": "two people talk",
           "evolve": "humans evolving - a march of progress from hunched cave people in furs to upright modern people",
           "catch": "catches something flying at them, lightning fast (reflexes, saves)", "react": "startled - steps back, hands up, surprised"}
OUTFITS = ["suit", "jersey", "casual", "dress", "lab", "fur", "robe", "space"]
HAIRS = ["short", "side", "long", "curly", "bun", "bald"]
ACCESSORIES = ["", "tie", "glasses", "cap", "crown", "tophat", "helmet"]
# what a picture DOES once it lands (src/mg/kit.tsx idle()) — picked from the concept
MOTION_FOR = [("fly", "rocket plane airplane bird satellite spaceship drone balloon jet"), ("spin", "earth globe planet atom gear gears sun moon coin crypto bitcoin wheel fan galaxy orbit"),
              ("pulse", "heart brain lightbulb idea battery signal star alert love"), ("swing", "clock hourglass bell pendulum time"),
              ("bounce", "ball money cash dollar gift trophy medal basketball soccer"), ("drive", "car truck train ship bus bike boat"),
              ("sway", "tree plant flower flag forest"), ("flicker", "fire flame lightning zap energy volcano"), ("grow", "chart growth rise stock market profit city"),
              ("shake", "warning danger alert risk earthquake crash"), ("wobble", "robot dinosaur jelly question")]
_LOCKS = {}
_ID = re.compile(r"^[a-z0-9]{8,16}$")
_CACHE = {}


def styles():
    try:
        return json.load(open(os.path.join(ENGINE, "mg_assets", "styles.json"), encoding="utf-8"))
    except Exception:
        return {}


def _jload(path, key):
    try:
        m = os.path.getmtime(path)
        if _CACHE.get(key, (0,))[0] != m:
            _CACHE[key] = (m, json.load(open(path, encoding="utf-8")))
        return _CACHE[key][1]
    except Exception:
        return {}


def icons():
    return _jload(os.path.join(MG, "icons.json"), "icons")


def art():
    return _jload(os.path.join(MG, "art", "manifest.json"), "art")


def concepts():
    return _jload(os.path.join(ENGINE, "mg_assets", "concepts.json"), "concepts")


# ── storage ────────────────────────────────────────────────────────────────────────────────────────────────
def _dir(uid):
    d = os.path.join(D, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid)))
    os.makedirs(d, exist_ok=True)
    return d


def _lock(pid):
    return _LOCKS.setdefault(pid, threading.Lock())


def load(uid, pid):
    if not _ID.match(str(pid)):
        return None
    try:
        with open(os.path.join(_dir(uid), pid + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _name_session(p):
    """Keep the video's own session named "Motion · <title>" (Media Lab chat + library shelf for this video)."""
    t = (p.get("title") or "").strip()
    if not (p.get("session") and t) or p.get("_sess_named") == t:
        return
    try:
        import sessions
        with sessions._LOCK:
            d = sessions.load(p["user"])
            for x in d["sessions"]:
                if x["id"] == p["session"]:
                    x["name"] = sessions._clean_name("Motion · " + t)
            sessions._save(p["user"], d)
        p["_sess_named"] = t
    except Exception:
        pass


def new_session(uid, label):
    import sessions
    try:
        return sessions.create(uid, "Motion · " + (label or "new video")[:48])["id"]
    except Exception:
        return ""


def save(p):
    _name_session(p)
    p["updated"] = time.time()
    path = os.path.join(_dir(p["user"]), p["id"] + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)
    for i in range(40):            # Windows: replace fails while the page's poll has the file open — retry, never kill the worker
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 + 0.01 * i)
    os.replace(tmp, path)


def log(p, msg, lvl="info"):
    p.setdefault("log", []).append({"t": time.time(), "msg": str(msg)[:300], "lvl": lvl})
    p["log"] = p["log"][-150:]


def listing(uid):
    out = []
    for f in os.listdir(_dir(uid)):
        if _ID.match(f[:-5]) and f.endswith(".json"):          # real projects only (not backups / trash)
            try:
                with open(os.path.join(_dir(uid), f), encoding="utf-8") as fh:
                    p = json.load(fh)
                out.append({"id": p["id"], "title": p.get("title") or p.get("brief"), "state": p.get("state"), "stage": p.get("stage"),
                            "style": p.get("style"), "created": p.get("created"), "updated": p.get("updated"),
                            "src": (p.get("render") or {}).get("src", ""), "beats": len(p.get("beats") or []), "posted": len(p.get("posts") or ([1] if p.get("post") else [])),
                            "session": p.get("session") or "", "format": p.get("format"), "aspect": p.get("aspect"), "wait": p.get("wait"),
                            "error": p.get("error") if p.get("state") == "error" else "",
                            "progress": progress(p, light=True) if p.get("state") in ("running", "waiting", "error") or time.time() - (p.get("updated") or 0) < 1800 else None})
            except Exception:
                pass
    return sorted(out, key=lambda r: -(r.get("updated") or 0))


STEP_LABELS = {"script": ("Write the story", "Writing the story and planning every scene", "note"),
               "voice": ("Record the voice", "Recording the narration and timing every word", "mic"),
               "pictures": ("Pick the pictures", "Choosing a styled picture for every phrase", "image"),
               "scenes": ("AI-animate key moments", "Drawing the cast, then animating the key moments with AI", "wand"),
               "score": ("Score the music", "Composing music for every chapter and placing the sound effects", "music"),
               "render": ("Render the video", "Putting it all together into the final video", "video")}
_WEIGHT = {"script": 8, "voice": 17, "pictures": 10, "scenes": 40, "score": 12, "render": 25}


def _lab_job(p):
    """The Media Lab job this video is waiting on right now (AI scene keyframe / animation) → id, model, stage, steps."""
    import sys as _sys
    bp = _sys.modules.get(__package__ + ".blueprint")
    if not bp or not p.get("session"):
        return None
    try:
        js = [j for j in list(bp.JOBS.values()) if j.get("internal") and j.get("session") == p["session"] and j.get("status") in ("running", "queued")]
    except Exception:
        return None
    if not js:
        return None
    j = sorted(js, key=lambda j: j.get("status") != "running")[0]
    pg = j.get("progress") or {}
    return {"id": j.get("id"), "model": j.get("model"), "status": j.get("status"), "stage": str(j.get("stage") or "")[:80],
            "value": pg.get("value"), "max": pg.get("max"), "started": j.get("started")}


def progress(p, light=False):
    """Where a video is: the steps (done / working / to do, with counts), overall %, what's happening now, a rough time left,
    and (full mode) the AI-scene cast + keyframes so the page can show them as they appear."""
    beats = p.get("beats") or []
    ai = (p.get("ai_scenes") or ("key" if p.get("format") == "story" else "off")) == "key"
    sc = p.get("format") == "diorama" and p.get("score", "on") != "off"
    order = ["script", "voice", "pictures"] + (["scenes"] if ai else []) + (["score"] if sc else []) + ["render"]
    st, state, note = p.get("stage") or "script", p.get("state"), p.get("stage_note") or ""
    if st == "assets":
        cur = "scenes" if ai and (note.startswith("AI scene") or note.startswith("drawing the cast")) else "score" if sc and (note.startswith("scoring") or note.startswith("mixing")) else "pictures"
    else:
        cur = {"script": "script", "voice": "voice", "render": "render"}.get(st, "render" if st in ("publish", "done") else "script")
    if st in ("publish", "done"):                  # an older finished cut doesn't count while the video is being remade
        reached = len(order)
    else:
        reached = order.index(cur) if cur in order else 0
    nv = sum(1 for b in beats if b.get("line"))
    dv = sum(1 for b in beats if b.get("line") and b.get("vo") and b.get("vo_line") == b["line"])
    vis = [v for b in beats for v in (b.get("visuals") or [])] + [b["panel"] for b in beats if isinstance(b.get("panel"), dict)]
    dp = sum(1 for v in vis if v.get("kind"))
    plan = p.get("scenes_plan") or {}
    sk = [i for i in plan.get("beats") or [] if i < len(beats)] or [i for i, b in enumerate(beats) if b.get("plate_auto")]
    ds = sum(1 for i in sk if beats[i].get("plate"))
    dk = sum(1 for i in sk if beats[i].get("plate") or beats[i].get("kf_live") or beats[i].get("keyframe"))   # keyframes drawn
    rp = float((p.get("render") or {}).get("pct") or 0)
    sub = 0.0
    if note.startswith("AI scene"):
        sub = 0.12 if "keyframe" in note else 0.85 if "smoothing" in note else 0.45
    counts = {"script": (1 if beats else 0, 1), "voice": (dv, nv), "pictures": (dp, len(vis)), "scenes": (ds, len(sk)),
              "score": (len([1 for x in [p.get("score_lib")] if x]), 1), "render": (1 if st in ("publish", "done") else 0, 1)}
    mch = re.match(r"writing chapter (\d+)/(\d+)", note)
    frac = {"script": (int(mch.group(1)) - 1) / int(mch.group(2)) if mch and st == "script" else 1.0 if beats and st != "script" else 0.4 if not beats else .9, "voice": dv / nv if nv else 0, "pictures": dp / len(vis) if vis else 1,
            "score": .5 if note.startswith("scoring") else .9 if note.startswith("mixing") else (1.0 if p.get("score_lib") else 0),
            "scenes": (0.15 * dk + 0.85 * ds + (0.85 * (sub - 0.12) / 0.88 if sub > 0.12 else 0)) / len(sk) if sk else 0, "render": rp / 100.0}
    steps, tot, got = [], 0, 0.0
    for k, sid_ in enumerate(order):
        if k < reached:
            stt, f = "done", 1.0
        elif k == reached and st not in ("publish", "done"):
            stt, f = ("working" if state == "running" else "waiting" if state == "waiting" else "stopped"), min(1.0, frac[sid_])
        else:
            stt, f = "todo", 0.0
        d_, t_ = counts[sid_]
        steps.append({"id": sid_, "label": STEP_LABELS[sid_][0], "icon": STEP_LABELS[sid_][2], "state": stt, "done": d_, "total": t_,
                      "pct": round(f * 100), **({"drawn": dk} if sid_ == "scenes" else {})})
        tot += _WEIGHT[sid_]
        got += _WEIGHT[sid_] * f
    pct = 100 if st == "done" or (st == "publish" and state != "running") else round(got / tot * 100)
    eta = 0
    if state == "running":
        left = {"score": 0 if p.get("score_lib") else 300, "script": (int(mch.group(2)) - int(mch.group(1)) + 1) * 35 if mch else 60, "voice": max(0, nv - dv) * 12, "pictures": 30, "scenes": max(0, len(sk) - ds) * 480 - sub * 480,
                "render": 0}
        if cur == "render":
            el = time.time() - float((p.get("render") or {}).get("started") or time.time())
            eta = int(el / max(0.05, rp / 100.0) - el) if rp > 3 else 300
        else:
            eta = int(sum(left[x] for x in order[order.index(cur):] if x in left) + (300 if "render" in order else 0))
    now = STEP_LABELS.get(cur, ("", "", ""))[1]
    out = {"pct": pct, "steps": steps, "current": cur, "now": now if state == "running" else "", "detail": note, "eta": max(0, eta),
           "state": state, "lines": [nv, dv], "render_pct": round(rp)}
    if state == "running":
        out["job"] = _lab_job(p)
    if light:
        return out
    d = os.path.join(core.DATA, "motion_wizard", "scenes", p["id"])
    names = set(os.listdir(d)) if os.path.isdir(d) else set()
    cast = {c["id"]: c for c in p.get("cast") or []}
    out["cast"] = [{"id": cid, "name": (cast.get(cid) or {}).get("name") or cid, "img": "api/mg/%s/scene/%s" % (p["id"], f)}
                   for cid, f in (p.get("cast_sheets") or {}).items() if f in names]
    out["scenes"] = []
    for k, i in enumerate(sk):
        b = beats[i]
        kf = b.get("keyframe") or b.get("kf_live")
        working = state == "running" and cur == "scenes" and not b.get("plate") and note.startswith("AI scene %d/" % (k + 1))
        out["scenes"].append({"n": i, "line": (b.get("line") or "")[:120], "state": "ready" if b.get("plate") else "working" if working else "todo",
                              "img": "api/mg/%s/scene/%s" % (p["id"], kf) if kf and kf in names else "",
                              "plate": (b.get("plate") or "").split(":", 1)[-1]})
    return out


# ── brain ──────────────────────────────────────────────────────────────────────────────────────────────────
def _ask_json(prompt, system, ask):
    txt = None
    try:
        import viral
        txt = viral.brain_ask(prompt, system, timeout=300)
    except Exception:
        txt = None
    if txt is None and ask:
        r = ask(prompt, system)
        if isinstance(r, dict):
            return r
        txt = r
    m = re.search(r"\{.*\}", str(txt or ""), re.S)
    if not m:
        raise RuntimeError("the writer returned nothing usable")
    return json.loads(m.group(0))


LENGTHS = {"short": (6, 9, "a 30-45 second Short"), "medium": (10, 16, "a 60-90 second video"), "long": (18, 28, "a 2-3 minute video")}

SCRIPT_SYS = """You are the director of a fully animated MOTION-GRAPHICS explainer (no footage, no presenter): every spoken phrase is
shown as a picture, number or word that animates on screen the moment it is said. Write the script as BEATS. One beat = one
short spoken line (8-22 words, conversational, concrete) + the picture plan for it.

Beat kinds and their extra fields:
- title     {kicker, title (2-5 words), sub}                      opening card; also use for chapter changes
- stat      {kicker, value (number), prefix, suffix, label}      one big number counting up
- visuals   {headline}                                           1-4 pictures popping in one per phrase (the default kind)
- relation  {headline, link}                                     A → B with a labelled connector (cause→effect, distance, flow, before→after in time)
- list      {headline, items:[{text, cue}]}                      3-5 short points, each cued to a word
- compare   {headline, a, aval, b, bval}                         two things side by side with values
- quote     {text, by}                                           a short quotation
- action    {action, who, headline, figure, figure2?}            an ANIMATED CHARACTER doing something while the line is spoken -
            use it whenever the line is about a person (or people) doing something: a leader giving a speech, a player scoring,
            someone running, inventing, celebrating, shaking hands. action is one of: ACTION_LIST.
            figure = how the person looks: {"outfit": suit|jersey|casual|dress|lab|fur (prehistoric)|robe (ancient)|space (astronaut), "hair": short|side|long|curly|bun|bald,
            "hairColor": "#hex", "skin": "#hex", "accessory": tie|glasses|cap|crown|tophat|helmet|"", "number": jersey number,
            "color": "#hex" main clothing colour, "beard": true|false}. who = the tag shown (e.g. "John F. Kennedy · 1963").
            figure2 = the second person for handshake / chat. visuals: 0-1 (a supporting object shown beside the character).
- endcard   {title, line1, line2}                                closing card (always the LAST beat; the like/subscribe + MIR
            MEDIA LABS GitHub card is drawn automatically, the line is the spoken goodbye)

Every beat has "visuals": 1-4 entries (0 for endcard) = {"concept": a concrete, drawable noun (rocket, brain, coin, clock, handshake,
city, dna, shield — never abstract words like 'quality'), "label": 1-2 words shown under it, "cue": the EXACT word from this beat's
line on which it should appear}. relation needs exactly 2 visuals, compare exactly 2, stat 0-1, title 0-2. Spread cues across the
line so pictures arrive while the words are spoken. Prefer common nouns that exist as icons. Use 'action' beats generously - about
one in three beats when the topic involves people, so the video is full of characters DOING things, not just pictures.
A MIR MEDIA LABS intro sting is added before the first beat automatically - do not write one.
CONTINUOUS SHOTS: the video should feel like a few LONG camera moves, not a slideshow. Give every beat "shot": an integer -
consecutive beats with the same number are ONE continuous shot (the camera glides from beat to beat, earlier graphics slide
away, the scene keeps evolving). Keep 2-5 beats per shot and start a new shot ONLY when the topic or place really changes
(the endcard is always its own shot). Give the first beat of each shot "move": pan (moving forward through time/steps) |
crane (rising, growing, going up) | push (diving deeper into one idea). When a shot is a journey through time or steps
(evolution, history, a process), give each of its beats "mark": a 1-3 word label shown on the shot's timeline
("2M years ago", "3000 BC", "1800s", "Today", "Step 1").
Reply with ONE JSON object only:
{"title": "...", "beats": [{"kind": "...", "line": "...", ...fields, "visuals": [...]}]}"""



STORY_SYS = """You write and direct a fully animated STORY film in the style of popular "What if…?" animated YouTube videos: the viewer
is the hero ("you"), every line is SHOWN as a scene with characters acting in real places, and the facts and numbers appear
INSIDE the scenes. Narration is second person, present tense, short and punchy ("A fly buzzes past your face. You don't even
think. You just catch it."). Open with a cold-open scene that shows the premise in action, then the title beat, then escalate
through vivid everyday → social → sports/extreme → consequences, and end on a twist or a thought. Mix narration with SHORT
dialogue lines spoken by characters ("How did you do that?", "They think I'm cheating."). A character SAYING a line uses
action "talk" (or react/celebrate/sad for emotion) — "speech" is ONLY a formal public speech at a podium on the "stage" set.

CAST: invent 2-4 recurring characters. cast = [{"id": "hero", "name": "You", "voice": VOICE, "look": FIGURE}, …]. The hero is
always id "hero". VOICE is one of: VOICE_LIST. FIGURE = {"outfit": suit|jersey|casual|dress|lab|fur|robe|space, "hair":
short|side|long|curly|bun|bald, "accessory": tie|glasses|cap|crown|tophat|helmet|"", "color": "#hex" clothing colour (make each
character a different bold colour), "number": jersey number or ""}.

BEATS: one line each (6-20 words). Most beats are kind "action": {"kind": "action", "line": "...", "speaker": "narrator" or a
cast id (the line is then that character's dialogue), "actor": cast id who is on screen, "action": ACTION_LIST,
"set": SET_LIST, "shot": wide|medium|close|xclose (vary them like a film: establish wide, then medium, close-ups on faces for
reactions and dialogue, xclose for tiny details), "mood": happy|surprised|angry|determined|sad|scared, "headline": optional
2-5 words, "who": optional tag, "overlay": optional in-scene data {"type": "timer", "value": 0.2, "unit": "s", "label": "..."} |
{"type": "distance", "label": "11 m"} | {"type": "score", "a": "21", "b": "0"} | {"type": "gauge", "a": "Normal", "av": "30 cm",
"b": "You", "bv": "3 mm", "ratio": 0.1} | {"type": "chain", "items": ["Eyes", "Brain", "Muscles"]} | {"type": "label", "text":
"x10"}, "fx": optional slowmo|impact|freeze|flash for the big moments, "visuals": optional 0-1 object {"concept", "label",
"cue"}}. You may also use kind "title" ({kicker, title, sub}) once after the cold open, and kind "stat" for one huge number.
Use REAL numbers. Put an overlay on about one in three beats.
KEY MOMENTS: mark "key": true on the most important third of the scenes (the cold open, big reveals, action peaks, the emotional
turn) - those are animated by an AI video model with full detail; the rest are drawn as motion graphics.

SHOTS: give every beat "shot_id" (an integer): consecutive beats in the same place share a shot_id and the camera glides
between them; change shot_id when the place changes. Last beat: kind "endcard" (spoken goodbye).
Reply with ONE JSON object only: {"title": "...", "cast": [...], "beats": [...]}"""


DIORAMA_SYS = """You write and direct an animated film in the Diorama style: ONE continuous shot of a tiny isometric
world in charcoal, brushed metal and gold, with an acting main character, and the camera glides between places. Every line is part
of ONE story told by ONE narrator.
THE WORLD of this film: WORLD_LINE

WRITE IT LIKE A GREAT NARRATED FILM, NOT A LIST OF FACTS:
- One throughline. Hook early (a question, a moment, a surprise); pay it off at the end (a twist, a takeaway, a callback).
- Every line CONTINUES the previous one: use connectors and consequences ("But…", "So…", "Which means…", "And then…", "Now…",
  "That's why…", "Meanwhile…"). A viewer should never feel a jump. No two lines may be interchangeable.
- Spoken English, vivid and concrete, 6 to 18 words per line, never under 5. Real numbers where they help. No headings, no
  "in this video", no emoji, no stage directions in the line. Second person ("you") for what-if stories; a warm curious narrator
  for explainers. Show scenarios: specific situations with people, places and moments, not abstractions.

THE PLACES of this film, each with its own spots (station):
PLACE_TABLE
Changing place = the character travels there in one continuous move (walking, or riding when the pose is a vehicle). Change place
when the story's scenario changes - not every line. Stay in a place for a run of lines and use its spots.

DIRECT EVERY LINE (the animation is built from these fields - the character must DO what the narrator says):
- place + station (from the table above).
- pose: the main character's movement, from this library:
ACT_LIST
  Pick the pose that ACTS the line literally: "you drive to work" = drive, "she calls you" = phone, "you sip your coffee" = drink,
  "you score" = kick, "the soldiers charge" = charge, "you read the letter" = read. Never "explain" or "stand" when the line names
  an action.
- mood: neutral | surprised | stressed | happy | calm | wonder | focused | sad | scared | angry (face + voice).
- camera: close (face, emotion) | medium (character + nearby object) | wide (the whole place) | aerial (the place and its
  surroundings, for distance or "out there") | city (the whole world from above, for "everyone", scale, endings). Never the same
  camera more than 3 lines in a row; aerial/city for real scale moments only.
- panel (optional, about every other line): a gold info card beside the character - {"label": 1-3 words, "value": a short
  number or fact like "90 m", "x10", "1,000,000", "3 AM" (or ""), "icon": one simple noun}. Use it when the line states a
  number, a name or a key fact. Never repeat the line's text.
- sfx (optional, at most one line in three): a short sound word like HUMMMM, TICK, BOOM, WHOOSH, BA-DUM, !?
- fx (optional): shake (the place rattles) | spin (a gold turbine - engines, power) | impact (the frame jolts on a hit) |
  route (a gold signal travels to the character - messages, distance). rings (optional): sound | pulse.
- amb (optional): AMBIENTS - weather or atmosphere over the frame (rain, snow, war smoke + flashes, party confetti, speed
  streaks, fireflies). The world already has its own default; set it only when this moment changes it.
- vfx (optional): visual effects in the moment - [{"kind": "VFX_LIST", "at": "hero|place|far|<station>"}]: an explosion
  when a shell lands, fire when something burns, smoke, a flood when water rises, lightning in a storm, sparks, dust when
  something collapses, a splash, fireworks, a tornado, a meteor, magic, steam, an earthquake (quake), bubbles. at = where:
  next to the character (hero), over the whole place (place), in the distance (far) or at one of the place's spots.
- cue: the word in the line where the panel / sound word / effect should land.
- with: the ids of the story's people who are PHYSICALLY THERE, in the same place, in this line (up to 3).
- remote: people the line involves who are NOT physically there - [{"id": "mom", "how": "phone|video|tv|far|heard|thought"}].
  phone = you talk on the phone / they call / you text them (video = a video call); tv = on a screen or the news; far = seen far
  away, across the street, in the distance; heard = only their voice, from another room or off-frame; thought = remembered,
  imagined, missed, dreamed of. NEVER put such a person in "with" - they must not appear in the room like a ghost.
- talker: the id of the person who speaks in this line (here or remote), else "".
- acts (optional): what the people in "with" do when it differs from just standing - {"dana": "drink"} (any pose above).
- animals (optional): animals in the moment with the character - [{"kind": "dog", "act": "follow|idle|walk|run|sit|sleep|eat|speak|fly"}].
  Kinds: ANIMALS. A recurring named pet belongs in the cast instead (look.species).
- extras (optional): an unnamed group in the moment - {"n": 1-4, "act": "<pose>", "look": {"outfit": "...", "hat": "..."}} - soldiers
  beside you, a cheering crowd, teammates, villagers.

THE MAIN CHARACTER ("hero"): one look for the whole film that fits the world and the story - {"gender": "man|woman", "skin": "...",
"hair": "...", "color": "...", "outfit": "...", "hat": ""} (a soldier in a war story, an astronaut on the moon, a farmer on a farm).

THE PEOPLE: a cast of 2 to 8 people and animals (never the protagonist), each with a fixed look - the recurring named ones AND
anyone else who is part of a moment, even unnamed (a kid at the crossing, a bus driver: id "kid", name "Kid"). Children are
gender "child". Everyone the narration shows doing something must be in the cast and in that line's "with" (or "remote"):
{"id": "dana", "name": "Dana", "role": "...", "look": {"gender": "man|woman|child", "skin": "light|medium|tan|deep",
"hair": "HAIRS", "color": "COLORS", "outfit": "OUTFITS", "hat": "HATS or empty", "age": "young|adult|older", "glasses": true/false,
"beard": true/false}}. A pet or animal character: {"id": "max", "name": "Max", "role": "the dog", "look": {"species": "dog"}}.
Give them distinct looks that fit the world. If a cast list is given below, use exactly those ids; otherwise invent the cast.

Reply JSON: {"title": "...", "hero": {...}, "cast": [...], "beats": [{"line": "...", "place": "...", "station": "...", "pose": "...", "mood": "...",
"camera": "...", "panel": {"label": "...", "value": "...", "icon": "..."} or null, "sfx": "", "fx": "", "rings": "", "amb": "", "cue": "...",
"with": ["dana"], "remote": [], "talker": "", "acts": {}, "animals": [], "extras": null, "vfx": []}]}"""

OUTLINE_SYS = """You plan a long narrated animated film in the Diorama style (one character in a tiny isometric world -
WORLD_LINE - with these places: PLACE_LIST - the character travels between them). Plan it as CHAPTERS: each chapter is one
scenario - a specific situation in one place (it may end by moving on). Together they form ONE story with an arc: a hook, rising
stakes, a turn, and a payoff that calls back to the opening. Vary the places (use at least four different places; this film's extra places are there because its story needs them - use them), give every chapter
its own concrete moments, numbers and people, and make each chapter lead into the next.
Also create the CAST: 2 to 8 people (never the protagonist) who appear in the chapters - colleagues, friends, an expert, AND the
unnamed people the story shows (a kid at the crossing, a driver, a stranger; children have gender "child") - each with a fixed,
distinct look (see the look fields below). Name who appears in each chapter.
Reply JSON: {"title": "...", "logline": "one sentence", "cast": [{"id": "dana", "name": "Dana", "role": "...", "look": {"gender": "man|woman|child",
"skin": "light|medium|tan|deep", "hair": "HAIRS", "color": "COLORS", "outfit": "OUTFITS", "hat": "HATS or empty", "age": "young|adult|older", "glasses": false,
"beard": false}} or an animal character {"id": "max", "name": "Max", "role": "the dog", "look": {"species": "dog"}}],
"hero": {"gender": "man|woman", "outfit": "...", "color": "...", "hat": ""} (the main character's look, fitting the world),
"chapters": [{"title": "...", "place": "PLACE_ENUM", "lines": <how many spoken lines>, "people": ["dana"],
"goal": "what this chapter does for the story", "summary": "2-3 sentences of what happens"}]}"""


def _dio_beats(j, default_place):
    out = []
    for b in j.get("beats") or []:
        if isinstance(b, dict) and b.get("line"):
            b = dict(b, kind="diorama")
            if b.get("place") not in dio_places():
                b["place"] = default_place
            out.append(b)
    return out


def write_diorama(p, ask):
    lo, hi, desc, chapters = DIO_LENGTHS.get(p.get("length") or "medium", DIO_LENGTHS["medium"])
    if p.get("dio_world") not in motion_kits.WORLDS:   # the world the film is set in (the user's pick, else read from the premise)
        lg = lambda m, l="info": log(p, m, l)
        p["dio_world"] = motion_kits.pick_world(p["brief"], ask, lg, want=p.get("world"),          # no world fits → the MINT designs one (Nov 2 2026)
                                                mint=(lambda br: motion_mint.design_world(br, ask, lg)) if p.get("mint", True) else None)
        log(p, "world · %s" % motion_kits.WORLDS[p["dio_world"]][0], "done")
    world = p["dio_world"]
    if "dio_kits" not in p:                        # the location scout: the places this story needs (library first, else designed + saved)
        p["stage_note"] = "scouting the places"
        save(p)
        try:
            p["dio_kits"] = motion_kits.scout(MG, p["brief"], ask, lambda m, l="info": log(p, m, l), world=world)
        except Exception as e:
            log(p, "the location scout failed (%s) - using the world's own places" % str(e)[:80], "warn")
            p["dio_kits"] = [k["id"] for k in motion_kits.catalog(MG) if k["world"] == world][:3] if world != "city" else []
    kits = p.get("dio_kits") or []
    pls = dio_places(kits, world)
    dsys, osys = dio_prompts(world, kits, pls)
    extra = []
    if p.get("aspect") == "9:16":
        extra.append("Vertical 9:16: favour close and medium.")
    if p.get("audience"):
        extra.append("Audience: %s." % p["audience"])
    if p.get("tone"):
        extra.append("Tone: %s." % p["tone"])
    if chapters <= 1:
        j = _ask_json("Topic / premise: %s\nLength: %s - %d to %d lines.\n%s" % (p["brief"], desc, lo, hi, " ".join(extra)), dsys, ask)
        beats = _dio_beats(j, next(iter(pls), "apartment"))[:hi + 6]
        title = j.get("title")
        p["dio_cast"] = dio_cast(j.get("cast"))
        p["dio_hero"] = dio_hero(j.get("hero"), world)
    else:
        p["stage_note"] = "planning the chapters"
        save(p)
        o = _ask_json("Topic / premise: %s\nTotal length: %s - about %d spoken lines in %d chapters.\n%s" % (p["brief"], desc, (lo + hi) // 2, chapters, " ".join(extra)), osys, ask)
        chs = [c for c in o.get("chapters") or [] if isinstance(c, dict) and c.get("title")][:chapters + 3]
        if len(chs) < 3:
            raise RuntimeError("the writer couldn't plan the chapters - try a clearer premise")
        per = max(6, round(((lo + hi) / 2) / len(chs)))
        p["dio_cast"] = dio_cast(o.get("cast"))
        p["dio_hero"] = dio_hero(o.get("hero"), world)
        castline = "; ".join("%s = %s (%s)" % (c["id"], c["name"], c["role"]) for c in p["dio_cast"]) or "(none)"
        p["outline"] = {"title": o.get("title") or "", "logline": str(o.get("logline") or "")[:300],
                        "chapters": [{"title": str(c.get("title"))[:80], "place": c.get("place") if c.get("place") in pls else next(iter(pls), "apartment"),
                                      "summary": str(c.get("summary") or "")[:400]} for c in chs]}
        plan = "\n".join("%d. %s (%s): %s" % (i + 1, c["title"], c["place"], c["summary"]) for i, c in enumerate(p["outline"]["chapters"]))
        beats, title = [], o.get("title")
        for k, c in enumerate(p["outline"]["chapters"]):
            check(p)
            p["stage_note"] = "writing chapter %d/%d · %s" % (k + 1, len(chs), c["title"])
            save(p)
            n = int(chs[k].get("lines") or per) if str(chs[k].get("lines") or "").isdigit() else per
            n = max(6, min(22, n))
            prev = "\n".join(b["line"] for b in beats[-8:]) or "(this is the opening - start with the hook)"
            nxt = p["outline"]["chapters"][k + 1]["title"] if k + 1 < len(chs) else "(this is the last chapter - land the payoff)"
            who = ", ".join(x for x in (chs[k].get("people") or []) if isinstance(x, str)) or "anyone from the cast who fits"
            prompt = ("CAST (use these ids in \"with\" / \"talker\"; the cast is fixed): %s\nIn this chapter: %s\n" % (castline, who)) + ("FILM: %s - %s\nPremise: %s\n%s\nTHE CHAPTERS:\n%s\n\nNOW WRITE CHAPTER %d of %d: %s (place: %s)\nWhat happens: %s\n"
                      "Write %d to %d lines. The FIRST line must continue straight on from the story so far; the LAST line must lead into: %s\n"
                      "STORY SO FAR (last lines):\n%s") % (title or p["brief"][:80], p["outline"]["logline"], p["brief"], " ".join(extra), plan,
                                                           k + 1, len(chs), c["title"], c["place"], c["summary"], n - 1, n + 1, nxt, prev)
            try:
                j = _ask_json(prompt, dsys, ask)
            except Exception as e:
                log(p, "chapter %d: the writer failed (%s) - trying once more" % (k + 1, str(e)[:80]), "warn")
                j = _ask_json(prompt, dsys, ask)
            cb = [dict(b, ch=k) for b in _dio_beats(j, c["place"])[:n + 4]]
            if cb and not beats:
                pass
            beats += cb
            p["beats"] = [_beat(i, b) for i, b in enumerate(beats)]
            log(p, "chapter %d/%d written · %s · %d lines" % (k + 1, len(chs), c["title"], len(cb)), "done")
            save(p)
    if len(beats) < 4:
        raise RuntimeError("the writer returned fewer than 4 lines - try a clearer premise")
    p["title"] = p.get("title") or str(title or p["brief"])[:100]
    p["beats"] = [_beat(i, b) for i, b in enumerate(beats)]
    direct_all(p)
    p["beats"].append(_beat(len(p["beats"]), {"kind": "endcard", "line": "Thanks for watching. Like and subscribe for more.", "visuals": []}))
    p["stage_note"] = ""


def write_script(p, ask):
    if p.get("format") == "diorama":
        return write_diorama(p, ask)
    if p.get("format") == "story":
        return write_story(p, ask)
    lo, hi, desc = LENGTHS.get(p.get("length") or "medium", LENGTHS["medium"])
    extra = []
    if p.get("aspect") == "9:16":
        extra.append("Vertical 9:16 Short: punchy, a hook in the first beat, max 2 visuals per beat.")
    if p.get("audience"):
        extra.append("Audience: %s." % p["audience"])
    if p.get("tone"):
        extra.append("Tone: %s." % p["tone"])
    prompt = "Topic / brief: %s\nLength: %s — %d to %d beats, first beat kind title, last beat endcard.\n%s" % (p["brief"], desc, lo, hi, " ".join(extra))
    j = _ask_json(prompt, SCRIPT_SYS.replace("ACTION_LIST", ", ".join("%s (%s)" % kv for kv in ACTIONS.items())), ask)
    beats = [b for b in j.get("beats") or [] if isinstance(b, dict) and b.get("line")][:hi + 4]
    if len(beats) < 3:
        raise RuntimeError("the writer returned fewer than 3 beats — try a clearer brief")
    p["title"] = p.get("title") or str(j.get("title") or p["brief"])[:100]
    p["beats"] = [_beat(i, b) for i, b in enumerate(beats)]
    shots_from_writer(p["beats"])
    if p["beats"][-1]["kind"] != "endcard":
        p["beats"].append(_beat(len(p["beats"]), {"kind": "endcard", "line": "Thanks for watching.", "title": "Thanks for watching",
                                                    "line1": "Like · Subscribe", "line2": "Download the MIR MEDIA LABS app", "visuals": []}))


def write_story(p, ask):
    import tts
    lo, hi, desc = LENGTHS.get(p.get("length") or "medium", LENGTHS["medium"])
    lo, hi = int(lo * 1.6), int(hi * 1.8)                     # story beats are shorter and faster than explainer beats
    sys_ = (STORY_SYS.replace("VOICE_LIST", ", ".join("%s (%s)" % kv for kv in tts.VOICES.items()))
            .replace("ACTION_LIST", "|".join(ACTIONS)).replace("SET_LIST", "|".join(SETS)))
    extra = []
    if p.get("aspect") == "9:16":
        extra.append("Vertical 9:16: favour medium and close shots.")
    if p.get("audience"):
        extra.append("Audience: %s." % p["audience"])
    if p.get("tone"):
        extra.append("Tone: %s." % p["tone"])
    j = _ask_json("Premise / brief: %s\nLength: %s - %d to %d beats.\n%s" % (p["brief"], desc, lo, hi, " ".join(extra)), sys_, ask)
    cast = []
    for c in (j.get("cast") or [])[:5]:
        if isinstance(c, dict) and c.get("id"):
            cast.append({"id": re.sub(r"[^a-z0-9_]", "", str(c["id"]).lower())[:16] or "c%d" % len(cast), "name": str(c.get("name") or c["id"])[:30],
                         "voice": c.get("voice") if c.get("voice") in tts.VOICES else "", "look": _figure(c.get("look") or c.get("figure"))})
    if not any(c["id"] == "hero" for c in cast):
        cast.insert(0, {"id": "hero", "name": "You", "voice": "", "look": _figure({"outfit": "casual", "color": "#E5484D"})})
    p["cast"] = cast
    beats = [b for b in j.get("beats") or [] if isinstance(b, dict) and b.get("line")][:hi + 6]
    if len(beats) < 4:
        raise RuntimeError("the writer returned fewer than 4 scenes - try a clearer premise")
    for b in beats:                                   # story "shot" = camera framing; the continuous-shot group id is "shot_id"
        if b.get("shot") in SHOTS:
            b["frame"] = b.pop("shot")
        if b.get("shot_id") not in (None, ""):
            b["shot"] = b["shot_id"]
    p["title"] = p.get("title") or str(j.get("title") or p["brief"])[:100]
    p["beats"] = [_beat(i, b) for i, b in enumerate(beats)]
    shots_from_writer(p["beats"])
    if p["beats"][-1]["kind"] != "endcard":
        p["beats"].append(_beat(len(p["beats"]), {"kind": "endcard", "line": "Thanks for watching.", "visuals": []}))
        p["beats"][-1]["cut"] = True


def _dio_fields(out, b):
    """Validate a diorama beat's direction (station, pose, mood, camera, panel, sound word, effect, rings, cue)."""
    def pick(k, opts, d):
        v = str(b.get(k) or "").lower().strip()
        out[k] = v if v in opts else d
    pl = str(b.get("place") or "apartment").lower().strip()
    pls = dio_places()
    out["place"] = pl if pl in pls else "apartment"
    pick("station", pls[out["place"]], "center")
    pick("pose", list(motion_library.vocab().get("acts") or {}) or DIO_POSES, "explain")
    pick("mood", DIO_MOODS, "neutral")
    if str(b.get("camera") or "").lower() == "street":          # the old name of the aerial camera
        b = dict(b, camera="aerial")
    pick("camera", DIO_CAMS, "medium")
    for k, opts in (("fx", DIO_FX), ("rings", DIO_RINGS)):
        v = str(b.get(k) or "").lower().strip()
        if v in opts:
            out[k] = v
    if b.get("sfx"):
        out["sfx"] = re.sub(r"\s+", " ", str(b["sfx"])).strip()[:14]
    if b.get("cue"):
        out["cue"] = str(b["cue"])[:30]
    pn = b.get("panel")
    if isinstance(pn, dict) and (pn.get("label") or pn.get("value")):
        np_ = {"label": str(pn.get("label") or "")[:24], "value": str(pn.get("value") or "")[:12], "icon": str(pn.get("icon") or pn.get("label") or "")[:30]}
        for k in ("iconId", "kind"):                      # the icon already chosen survives a script edit
            if pn.get(k):
                np_[k] = pn[k]
        out["panel"] = np_
    if (out["place"], out["station"]) != ("apartment", "bed") and out["pose"] == "sleep":
        out["pose"] = "stand"
    w_ = b.get("with")
    if isinstance(w_, str):
        w_ = [x.strip() for x in w_.split(",")]
    if isinstance(w_, list):
        ids = [re.sub(r"[^a-z0-9_]", "", str(x).lower())[:16] for x in w_]
        out["with"] = [x for x in ids if x and x not in ("hero", "you")][:3]
    if b.get("talker"):
        out["talker"] = re.sub(r"[^a-z0-9_]", "", str(b["talker"]).lower())[:16]
    V = motion_library.vocab()
    acts_v, species_v = V.get("acts") or {}, V.get("species") or {}
    cid = lambda x: re.sub(r"[^a-z0-9_]", "", str(x).lower())[:16]
    rem = []
    for r in (b.get("remote") or [])[:3] if isinstance(b.get("remote"), list) else []:
        if isinstance(r, dict) and cid(r.get("id")) and str(r.get("how")) in REMOTE_HOWS:
            rem.append({"id": cid(r["id"]), "how": str(r["how"]), **({"act": str(r["act"])} if str(r.get("act") or "") in acts_v else {})})
    if rem:
        out["remote"] = rem
        out["with"] = [x for x in out.get("with") or [] if x not in {r["id"] for r in rem}]
    if isinstance(b.get("acts"), dict):
        a_ = {cid(k): str(v) for k, v in b["acts"].items() if str(v) in acts_v}
        if a_:
            out["acts"] = dict(list(a_.items())[:4])
    an = []
    for a in (b.get("animals") or [])[:3] if isinstance(b.get("animals"), list) else []:
        if isinstance(a, dict) and str(a.get("kind") or "").lower() in species_v:
            an.append({"kind": str(a["kind"]).lower(), "act": str(a.get("act") or "follow") if str(a.get("act") or "") in ANIMAL_ACTS else "follow"})
    if an:
        out["animals"] = an
    ex = b.get("extras")
    if isinstance(ex, dict) and ex.get("n"):
        out["extras"] = {"n": max(1, min(4, int(motion_util._f(ex.get("n"), 2, 1, 4)))), "act": str(ex.get("act")) if str(ex.get("act")) in acts_v else "stand",
                         "look": _look(ex.get("look") if isinstance(ex.get("look"), dict) else {})}
    vf = []
    for v in (b.get("vfx") or [])[:3] if isinstance(b.get("vfx"), list) else []:
        if isinstance(v, dict) and str(v.get("kind") or "").lower() in (V.get("vfx") or {}):
            q = {"kind": str(v["kind"]).lower(), "at": re.sub(r"[^a-z0-9_]", "", str(v.get("at") or "hero").lower())[:16] or "hero"}
            if v.get("t") not in (None, ""):
                q["t"] = motion_util._f(v["t"], 0, 0, 30)
            vf.append(q)
    if vf:
        out["vfx"] = vf
    if str(b.get("amb") or "") in (V.get("ambients") or []):
        out["amb"] = b["amb"]
    if isinstance(b.get("at"), dict):                 # a cast member standing at one of the place's spots this line
        sts = (dio_places().get(out["place"]) or [])
        a2 = {cid(k): str(v) for k, v in b["at"].items() if str(v) in sts}
        if a2:
            out["at"] = a2
    for k in ("auto_dir", "flash", "auto_vfx"):
        if b.get(k):
            out[k] = b[k]
    if isinstance(b.get("ch"), int):
        out["ch"] = b["ch"]


def _beat(i, b):
    kind = b.get("kind") if b.get("kind") in KINDS else "visuals"
    vs = []
    for v in (b.get("visuals") or [])[:4]:
        if isinstance(v, dict) and (v.get("concept") or v.get("label")):
            nv = {"concept": str(v.get("concept") or v.get("label"))[:60], "label": str(v.get("label") or v.get("concept"))[:30],
                  "cue": str(v.get("cue") or "")[:30]}
            for k in ("kind", "id", "pick", "text"):          # the picture already chosen survives a script edit
                if v.get(k) not in (None, ""):
                    nv[k] = str(v[k])[:120]
            if v.get("at_manual") not in (None, ""):
                nv["at_manual"] = motion_util._f(v["at_manual"], 0, 0, 60)
            vs.append(nv)
    out = {"n": i, "kind": kind, "line": str(b["line"])[:300], "visuals": vs, "status": "todo", "pad": motion_util._f(b.get("pad"), 0, -2, 10),
           "mark": str(b.get("mark") or "")[:24], "cut": bool(b.get("cut")), "move": b.get("move") if b.get("move") in MOVES else ""}
    if b.get("shot") not in (None, ""):
        out["shot"] = str(b["shot"])[:8]
    for k in ("kicker", "title", "sub", "value", "prefix", "suffix", "label", "headline", "link", "a", "aval", "b", "bval", "text", "by", "line1", "line2"):
        if b.get(k) not in (None, ""):
            out[k] = b[k] if k == "value" else str(b[k])[:200]
    if kind == "list":
        out["items"] = []
        for it in (b.get("items") or [])[:6]:
            if isinstance(it, dict) and it.get("text"):
                ni = {"text": str(it.get("text") or "")[:90], "cue": str(it.get("cue") or "")[:30], "concept": str(it.get("concept") or "")[:60]}
                for k in ("pick", "visual"):
                    if it.get(k):
                        ni[k] = it[k]
                if it.get("at_manual") not in (None, ""):
                    ni["at_manual"] = motion_util._f(it["at_manual"], 0, 0, 60)
                out["items"].append(ni)
    if kind == "quote" and not out.get("text"):
        out["text"] = out["line"]
    if b.get("key"):
        out["key"] = True
    for k in ("plate", "plate_sig", "plate_auto", "plate_dur", "keyframe"):   # an AI-animated shot survives script edits
        if b.get(k):
            out[k] = b[k]
    if b.get("speaker"):
        out["speaker"] = re.sub(r"[^a-z0-9_]", "", str(b["speaker"]).lower())[:16] or "narrator"
    if kind == "diorama":
        _dio_fields(out, b)
    if kind == "action":
        if b.get("set") in SETS:
            out["set"] = b["set"]
        fr = b.get("frame") or (b.get("shot") if b.get("shot") in SHOTS else None)
        if fr in SHOTS:
            out["frame"] = fr
        if b.get("mood") in MOODS:
            out["mood"] = b["mood"]
        if b.get("fx") in FXS:
            out["fx"] = b["fx"]
            out["fxAt"] = motion_util._f(b.get("fxAt"), 0.9, 0, 30)
        ov = b.get("overlay")
        if isinstance(ov, dict) and ov.get("type") in OVERLAYS:
            o = {"type": ov["type"]}
            for k in ("unit", "label", "a", "b", "av", "bv", "text"):
                if ov.get(k) not in (None, ""):
                    o[k] = str(ov[k])[:40]
            for k in ("value", "ratio", "at"):
                if ov.get(k) not in (None, ""):
                    o[k] = motion_util._f(ov[k], 0, -1e9, 1e9)
            if isinstance(ov.get("items"), list):
                o["items"] = [str(x)[:20] for x in ov["items"][:5]]
            out["overlay"] = o
        if b.get("actor"):
            out["actor"] = re.sub(r"[^a-z0-9_]", "", str(b["actor"]).lower())[:16]
    if kind == "action":
        out["action"] = b.get("action") if b.get("action") in ACTIONS else "talk"
        for k in ("who", "headline"):
            if b.get(k):
                out[k] = str(b[k])[:120]
        out["figure"] = _figure(b.get("figure"))
        if b.get("figure2") or out["action"] in ("handshake", "chat"):
            out["figure2"] = _figure(b.get("figure2") or {"outfit": "casual", "hair": "long"})
    for nv, ov in zip(out["visuals"], (b.get("visuals") or [])[:4]):
        if isinstance(ov, dict) and ov.get("motion") in MOTIONS:
            nv["motion"] = ov["motion"]
    return out


MOVES = ["pan", "crane", "push"]
SETS = ["street", "cafe", "room", "lab", "field", "stadium", "track", "city", "nature", "space", "stage"]   # src/mg/sets.tsx
SHOTS = ["wide", "medium", "close", "xclose"]
MOODS = ["happy", "surprised", "angry", "determined", "sad", "scared"]
OVERLAYS = ["timer", "distance", "score", "gauge", "chain", "label"]
FXS = ["slowmo", "impact", "freeze", "flash"]
FORMATS = {"explainer": "Explainer", "story": "Story (what-if)", "diorama": "Diorama"}
# DIORAMA (user's pick Oct 28 2026): one continuous isometric shot, an acting professional character, house palette.
# The vocabulary below is what src/mg/diorama_engine.ts understands.
DIO_PLACES = {"apartment": ["bed", "desk", "fridge", "clock", "window", "center"],
              "office": ["desk", "screen", "table", "coffee", "window", "center"],
              "lab": ["bench", "microscope", "machine", "screen", "center"],
              "cafe": ["counter", "table", "window", "center"],
              "street": ["lamp", "car", "bench", "crossing", "stop", "center"],
              "rooftop": ["edge", "dish", "tank", "center"]}
DIO_STATIONS = sorted({s_ for v in DIO_PLACES.values() for s_ in v})


def dio_places(kits=None, world="city"):
    """{place: [stations]}: the six built-ins (city films) + library kits (the given ids, or the whole library) - motion_kits.py."""
    return motion_kits.places(MG, kits, world)


def dio_prompts(world, kits, pls):
    """The writer + outline prompts for this film's world, places and the shared motion library."""
    L = motion_library.brief_for_writer(world)
    wl = "%s - %s" % motion_kits.WORLDS.get(world, motion_kits.WORLDS["city"])[:2]
    fill = lambda t: (t.replace("WORLD_LINE", wl).replace("ACT_LIST", L["acts"]).replace("ANIMALS", L["animals"]).replace("AMBIENTS", L["ambients"] or "rain|snow").replace("VFX_LIST", L.get("vfx") or "explosion|fire|smoke|flood")
                      .replace("OUTFITS", L["outfits"]).replace("HATS", L["hats"]).replace("COLORS", L["colors"]).replace("HAIRS", L["hairs"]))
    return (fill(DIORAMA_SYS).replace("PLACE_TABLE", motion_kits.table(MG, kits, world)),
            fill(OUTLINE_SYS).replace("PLACE_LIST", ", ".join(pls)).replace("PLACE_ENUM", "|".join(pls)))


HERO_BY_WORLD = {"war": {"outfit": "military", "hat": "helmet"}, "moon": {"outfit": "space", "hat": "bubble"}, "medieval": {"outfit": "robe", "color": "bronze"},
                 "snow": {"outfit": "coat", "hat": "beanie", "color": "ember"}, "beach": {"outfit": "tshirt", "color": "gold"}, "desert": {"outfit": "coat", "color": "champagne"},
                 "forest": {"outfit": "coat", "color": "olive"}, "jungle": {"outfit": "tshirt", "color": "olive", "hat": "cowboy"}, "countryside": {"outfit": "overalls"},
                 "ocean": {"outfit": "coat", "color": "navy"}}


def _look(lk):
    V = motion_library.vocab().get("looks") or {}
    keys = {"gender": ["man", "woman", "child"], "skin": V.get("skin") or ["light", "medium", "tan", "deep"], "hair": V.get("hair") or DIO_LOOK["hair"],
            "color": V.get("color") or DIO_LOOK["color"], "outfit": V.get("outfit") or DIO_LOOK["outfit"], "hat": V.get("hat") or [], "age": ["young", "adult", "older"],
            "hairColor": ["black", "brown", "blonde", "red"]}
    out = {k: str(lk.get(k)).lower() for k in keys if str(lk.get(k) or "").lower() in keys[k]}
    for k in ("glasses", "beard"):
        if lk.get(k):
            out[k] = True
    if str(lk.get("species") or "").lower() in (motion_library.vocab().get("species") or {}):
        out["species"] = str(lk["species"]).lower()
    if lk.get("num"):
        out["num"] = re.sub(r"[^0-9]", "", str(lk["num"]))[:2]
    return out


def dio_hero(raw, world="city"):
    """The main character's look: the writer's pick (fitted to the world), else the world's default, else the house blazer."""
    lk = _look(raw if isinstance(raw, dict) else {})
    lk.pop("species", None)
    if world != "city" and not lk.get("outfit"):
        mw = motion_mint.library("worlds").get(world) or {}          # a minted world says what the hero wears there, else its base world does
        dress = HERO_BY_WORLD.get(world) or mw.get("hero") or HERO_BY_WORLD.get(mw.get("base"), {})
        lk.update({k: v for k, v in dress.items() if k not in lk})
    if lk.get("outfit") == "space":              # an astronaut wears the space bubble, never the army helmet
        lk["hat"] = "bubble"
    return lk
DIO_LOOK = {"gender": ["man", "woman", "child"], "skin": ["light", "medium", "tan", "deep"], "hair": ["short", "long", "bun", "curly", "bald", "ponytail"],
            "color": ["graphite", "steel", "silver", "bronze", "champagne", "gold", "charcoal"], "outfit": ["blazer", "suit", "dress", "labcoat", "apron", "hoodie", "sweater"],
            "age": ["young", "adult", "older"]}


def dio_cast(raw):
    """Validate the recurring cast: [{id, name, role, look}] (the protagonist is not in it)."""
    out, seen = [], set()
    for c in (raw or [])[:8]:
        if not isinstance(c, dict) or not (c.get("id") or c.get("name")):
            continue
        cid = re.sub(r"[^a-z0-9_]", "", str(c.get("id") or c.get("name")).lower())[:16] or "p%d" % len(out)
        if cid in seen or cid in ("hero", "you", "narrator"):
            continue
        seen.add(cid)
        lk = c.get("look") if isinstance(c.get("look"), dict) else {}
        look = _look(lk)
        out.append({"id": cid, "name": str(c.get("name") or cid)[:30], "role": str(c.get("role") or "")[:60], "look": look})
    return out
# diorama lengths: (min lines, max lines, how long, chapters) — 5-10 minute films are written chapter by chapter
DIO_LENGTHS = {"short": (22, 30, "about 2 minutes", 1), "medium": (72, 84, "about 5 minutes", 7), "long": (130, 150, "about 9 to 10 minutes", 12)}
DIO_POSES = ["stand", "sleep", "shock", "listen", "ears", "cover", "flinch", "heart", "point", "think", "explain", "celebrate", "type", "shrug", "wave"]
DIO_MOODS = ["neutral", "surprised", "stressed", "happy", "calm", "wonder", "focused", "sad", "scared", "angry"]
DIO_CAMS = ["close", "medium", "wide", "aerial", "city"]
DIO_FX = ["shake", "spin", "impact", "route"]
DIO_RINGS = ["sound", "pulse"]
REMOTE_HOWS = ["phone", "video", "tv", "far", "heard", "thought", "mention"]
ANIMAL_ACTS = ["idle", "walk", "run", "sit", "sleep", "eat", "speak", "wag", "jump", "fly", "swim", "follow", "beg"]
GENERIC_POSES = {"stand", "explain", "talk", ""}

# ── NARRATION → ACTION (Oct 29, user: "the character actions still need to do what the narrator is saying"; "the hero talking on
#    the phone or hearing / seeing someone far away … they just appear like a ghost"). The writer directs every line; this pass
#    reads the line itself and (1) moves anyone the line only calls / hears / sees far away / remembers OUT of the room into
#    "remote", (2) replaces a generic pose with the verb the narrator actually says, (3) gives cast members their own verbs,
#    (4) adds animals, crowds and weather the line mentions. It never overrides a specific pose the writer chose (except rides,
#    which are unmistakable), and a line edited by hand is re-directed on the next build. ──
_W = r"\b"
ACT_RULES = [(re.compile(x, re.I), a) for x, a in [
    (r"behind the wheel|\b(driv(es|e|ing)|drove)\b[^.]{0,40}\b(car|truck|van|road|highway|home|town|city|work|traffic|lane)", "drive"),
    (r"\b(bike|bicycle|cycl(es|ing)|pedal(s|ing)?)\b", "bike"), (r"\b(motorbike|motorcycle)\b", "moto"), (r"\b(kick scooter|scooter)\b", "scooter"),
    (r"\b(rides? (a|the|his|her|your) horse|on horseback|gallop(s|ing)?|saddle)\b", "horse"), (r"\b(rows?|rowing|paddl(es|ing)|canoe|kayak)\b", "row"),
    (r"\bskateboard", "skate"), (r"\b(on|takes|catches|rides) (a|the) (bus|train|subway|metro|tram)\b", "bus"), (r"\b(fly(ing)? (a|the) plane|cockpit|pilots? (a|the) plane)\b", "fly"),
    (r"\bwheelchair\b", "wheelchair"), (r"\b(dribbl\w*)\b", "dribble"), (r"\b(scor(es|e|ed|ing)|kicks? (it|the ball)|penalty|shoots? (for|at) (the )?goal)\b", "kick"),
    (r"\b(basketball|hoop|dunk(s|ed)?)\b", "shoot"), (r"\b(box(es|ing)|punch(es|ed|ing)?)\b", "box"), (r"\b(sword|duel(s|ing)?|fencing)\b", "sword"),
    (r"\b(charg(es|e|ed|ing) (in|into|across|forward|the)|storm(s|ed)? the|over the top)\b", "charge"),
    (r"\b(take[s]? cover|duck(s|ed)? (for cover|down)|shell(s|ing)|explosions?|artillery|bombs? (fall|drop))\b", "takecover"),
    (r"\b(aims?|aiming|takes aim)\b", "aim"),
    (r"\b(rifles?|guns?|gunfire|fires? (a|the|his|her|your) (rifle|gun|weapon)|shoots? at)\b", "fire"), (r"\bmarch(es|ed|ing)?\b", "march"),
    (r"\b(soldiers?|troops|platoon|in the army|the front line|trench(es)?)\b", "soldier"), (r"\b(swim(s|ming)?|swam|dives? in)\b", "swim"),
    (r"\bjog(s|ging)?\b", "jog"), (r"\b(runs?|running|ran|sprint(s|ing)?|races?|chas(es|ing)|flee(s|ing)?|rush(es|ed)? (to|out|home|in))\b", "run"),
    (r"\b(jump(s|ed|ing)?|leap(s|t)?)\b", "jump"), (r"\b(danc(e|es|ed|ing))\b", "dance"), (r"\bguitar\b", "guitar"), (r"\b(sing(s|ing)?|sang)\b", "sing"),
    (r"\b(wakes?( up)?|waking|woke( up)?)\b", "stretch"), (r"\b(paint(s|ed|ing)? (a|the|his|her|your)|paintbrush|easel)\b", "paint"), (r"\bselfie\b", "selfie"), (r"\b(takes? a (photo|picture)|camera|snaps? a)\b", "photo"),
    (r"\b(text(s|ed|ing)?|messag(es|ed|ing)|types? (a|the) message)\b", "text"), (r"\bscroll(s|ed|ing)?\b", "scroll"),
    (r"\b(phones?|telephone|calls? (you|him|her|them|me|back|home|mom|dad)|called (you|him|her|them|me|home)|calling (you|him|her|them|me|home)|dial(s|ed)?|rings? (you|him|her|me)|voicemail|on the line|hangs? up|picks? up the phone)\b", "phone"),
    (r"\b(drink(s|ing)?|drank|sip(s|ped)?|coffee|tea|a glass of)\b", "drink"), (r"\b(eat(s|ing)?|ate|lunch|dinner|breakfast|a bite|bread|crumbs?|crusts?|food|meal|soup|rations?|chews?|munch\w*)\b", "eat"),
    (r"\b(cook(s|ed|ing)?|fry(ing)?|stove)\b", "cook"), (r"\b(read(s|ing)?|book|novel|newspaper)\b", "read"),
    (r"\b(writ(es|e|ing)|wrote|diary|journal|notebook|signs? the)\b", "write"), (r"\b(typ(es|e|ed|ing)|keyboard|laptop|coding)\b", "type"),
    (r"\b(carr(y|ies|ied|ying)|hauls?)\b", "carry"), (r"\b(lift(s|ed|ing)? weights|barbell|bench press)\b", "lift"), (r"\bpush(es|ed|ing)?\b", "push"),
    (r"\b(pull(s|ed|ing)?|rope)\b", "pull"), (r"\bknock(s|ed|ing)?\b", "knock"), (r"\b(opens? the door|open(s|ed)? the gate)\b", "open"),
    (r"\b(searche?s?|searching|looks? for|hunts? for)\b", "search"),
    (r"\b(look(s|ed|ing)? (out|up|far|across|into the distance)|stares?|gaz(es|e|ing)|horizon|watch(es|ed|ing)?|spot(s|ted)?|sees?|saw|notic(es|e|ed))\b", "look"),
    (r"\b(clap(s|ped|ping)?|applau\w*)\b", "clap"), (r"\bcelebrat\w*", "celebrate"), (r"\b(cheer(s|ed|ing)?|victory|wins?|won)\b", "cheer"),
    (r"\b(curl(s|ed|ing)? (up|in)|huddl\w*|cower\w*|crouch\w*)\b", "crouch"), (r"\b(crawl(s|ed|ing)?|on (his|her|their|your) belly|army.crawl\w*)\b", "crawl"), (r"\b(creep(s|ing)?|crept)\b", "sneak"),
    (r"\b(climb\w* (up |down |over |onto |into |out of |through )?(the|a|an|his|her|your|their) (stairs|steps|ladder|wall|tree|hill|mountain|rope|fence|roof|rocks?|cliff|tower|ladder)|climbs? (up|down|over|onto|aboard)|scal(es|ed|ing) the|up the ladder)\b", "climb"), (r"\b(lies? (down|still|on the|in the)|lying (on|in|there|still)|lay (on|in|still)|collaps(es|ed) (on|to|into))\b", "lie"),
    (r"\b(limp(s|ed|ing)?|hobbl\w*|staggers?|stumbl\w*)\b", "limp"), (r"\b(wounded|bleed\w*|is hit|gets hit|was hit|injur\w*|in pain|clutch\w*)\b", "wounded"),
    (r"\b(aims?|aiming|takes aim|sights?)\b", "aim"), (r"\b(ducks?|ducking)\b", "duck"), (r"\b(sleeps? (on|in) the (ground|mud|floor|grass|sand))\b", "sleepground"),
    (r"\b(sits?|sitting|sat|seated)\b", "sit"), (r"\b(kneel(s|ing)?|knelt)\b", "kneel"), (r"\b(hid(es|e|ing)|hidden)\b", "hide"), (r"\b(sneak(s|ing)?|tiptoe\w*)\b", "sneak"),
    (r"\b(cr(ies|y|ied|ying)|tears\b(?!\s+(free|off|open|apart|through|down|up|at|into|away))|in tears|sob(s|bing)?)\b", "cry"), (r"\blaugh(s|ed|ing)?\b", "laugh"), (r"\bpanic\w*", "panic"),
    (r"\b(worr(y|ies|ied)|anxious|nervous)\b", "worry"), (r"\b(tired|exhausted|yawn(s|ed)?)\b", "tired"), (r"\b(stretch(es|ed)?|wakes? up|woke up)\b", "stretch"),
    (r"\bpray(s|ed|ing)?\b", "pray"), (r"\b(hug(s|ged|ging)?|embrac\w*)\b", "hug"), (r"\b(shakes? hands|handshake)\b", "handshake"),
    (r"\b(gives?|hands? (it|him|her|them|over))\b", "give"), (r"\b(throws?|threw|toss(es)?)\b", "throw"), (r"\b(catch(es|ing)?|caught)\b", "catch"),
    (r"\bsalut\w*", "salute"), (r"\bbow(s|ed)?\b", "bow"), (r"\b(falls? (down|over|off|flat|to the (ground|floor)|on (his|her|their|your) (face|back))|fell (down|over|off|flat|to the (ground|floor))|trips? (over|on)|tripped (over|on)|slips? on|slipped on|loses? (his|her|your|their) footing)\b", "fall"), (r"\bwav(es|e|ed|ing)\b", "wave"),
    (r"\bpoint(s|ed|ing)?\b", "point"), (r"\b(campfire|around the fire)\b", "campfire"), (r"\bfish(es|ed|ing)\b", "fish"), (r"\b(dig(s|ging)?|dug|shovel)\b", "dig"),
    (r"\b(hammer(s|ing)?|builds? (a|the)|building (a|the))\b", "build"), (r"\b(waters? the|gardening)\b", "water"), (r"\bumbrella\b", "umbrella"),
    (r"\b(shiver(s|ing)?|freezing)\b", "shiver"), (r"\b(pets? the|strokes? the)\b", "pet"), (r"\b(presents?|slides?|pitch(es)?)\b", "present"),
    (r"\b(giggl\w*|grin(s|ning|ned)?|smil(es|e|ing|ed)|chuckl\w*)\b", "laugh"), (r"\b(brings?|brought|offers?|shares?|hands? (you|him|her|them|me))\b", "give"),
    (r"\b(shouts?|yells?|orders?|commands?|calls? out)\b", "explain"), (r"\b(checks?|checking|inspects?|examines?)\b", "search"),
    (r"\b(count(s|ing)|calculat\w*|planning)\b", "think"), (r"\b(nods?|nodding|agrees?)\b", "nod"),
    (r"\b(think(s|ing)?|wonder(s|ing)?|imagin\w*)\b", "think"), (r"\bshrug\w*", "shrug"),
]]
DRAMA_POSES = {"fall", "climb", "lie", "crawl", "swim", "phone", "sleepground", "wounded", "limp"}   # never without the words for it
STRONG_ACTS = {"crawl", "climb", "swim", "run", "jump", "fall", "lie", "charge", "dance", "fight", "box", "kick", "throw", "hug", "cry", "limp"}   # unmistakable body movement
RIDE_ACTS = {"drive", "bike", "moto", "scooter", "horse", "row", "skate", "bus", "fly", "wheelchair"}
REM_PHONE = re.compile(r"\b(phones?|telephone|on the line|voicemail|dial(s|ed|ing)?|rings? (you|him|her|me)|hangs? up|picks? up|texts? (you|him|her|me|them)|texted|messag(es|ed) (you|him|her|me)|facetime|video call|zoom call|calls? (you|him|her|me|them|back|home)|called (you|him|her|me|them|back|home)|calling (you|him|her|me|them|home))\b", re.I)
REM_VIDEO = re.compile(r"\b(video call|facetime|zoom|webcam)\b", re.I)
REM_TV = re.compile(r"\bon (the )?(tv|television|news|screen|big screen|stream|livestream)\b", re.I)
REM_HEARD_FROM = re.compile(r"\b(shout\w*|yell\w*|call\w* out|scream\w*|voice\w*)\b[^.]{0,30}\bfrom (the )?(next room|other room|downstairs|upstairs|outside|hallway|kitchen|garden|other side)|\bfrom (downstairs|upstairs|the next room|the other room|behind the door)\b", re.I)
REM_MEMORY = re.compile(r"\b(remember\w*|memory|memories|dream\w* of|miss(es|ed)?|used to)\b", re.I)
REM_HEARD = re.compile(r"\b(hears?|heard|hearing|voice|shouts? from|yells? from|calls? out|from (the )?(next room|other room|downstairs|upstairs|outside|hallway|behind the door))\b", re.I)
REM_FAR = re.compile(r"\b(\w+ (meters|metres|feet|yards|kilometers|kilometres|km|miles|blocks|floors) (away|off|below|above)|next door|across the (courtyard|hall|way|block|bay|harbour|harbor|park|plaza)|(his|her|their)'?s? window|in the next building|far away|far off|in the distance|across the (street|room|road|field|square|river|valley|lake|town|city|yard|pitch)|from afar|on the horizon|from the window|down the (street|road|hall)|miles away|on the other side|from the (hill|top|roof|balcony|tower))\b", re.I)
REM_THOUGHT = re.compile(r"\b(remember(s|ed)?|recalls?|thinks? (of|about)|thought (of|about)|imagin(e|es|ed)|dream(s|ed|t)? (of|about)|miss(es|ed)?|memory of|pictures?)\b", re.I)
SPECIES_WORDS = {"dogs": "dog", "puppies": "puppy", "cats": "cat", "kitten": "cat", "horses": "horse", "cows": "cow", "sheep": "sheep", "lamb": "sheep", "pigs": "pig",
                 "chickens": "chicken", "hen": "chicken", "rooster": "chicken", "ducks": "duck", "birds": "bird", "pigeons": "pigeon", "owls": "owl", "wolves": "wolf",
                 "deer": "deer", "foxes": "fox", "rabbits": "rabbit", "bunny": "rabbit", "mice": "mouse", "bears": "bear", "lions": "lion", "tigers": "tiger",
                 "elephants": "elephant", "monkeys": "monkey", "camels": "camel", "fish": "fish", "sharks": "shark", "whales": "whale", "snakes": "snake",
                 "frogs": "frog", "penguins": "penguin", "parrots": "parrot", "eagles": "eagle", "goats": "goat", "butterflies": "butterfly", "bees": "bee", "dragons": "dragon"}


VFX_RULES = [(re.compile(x, re.I), k, at) for x, k, at in [
    (r"\b(meteor|asteroid|comet)\w*", "meteor", "far"),
    (r"\b(explo(de|des|ded|sion|sions)|blast(s|ed)?|bomb(s|ed|ing)?|shells? (burst|land|lands|explode|hit)|grenade|detonat\w*|kaboom|boom)\b", "explosion", "far"),
    (r"\b(flood(s|ed|ing)?|water (rises|rose|pours|floods)|tsunami|the river bursts)\b", "flood", "place"),
    (r"\b(on fire|fire spreads|flames?|burn(s|ing|ed)|blaze|ablaze|inferno|wildfire)\b", "fire", "far"),
    (r"\b(smoke|smoking|smoulder\w*|smolder\w*)\b", "smoke", "far"),
    (r"\b(lightning|thunder(storm)?)\b", "lightning", "far"),
    (r"\b(sparks?|short.circuit\w*|welding|electric shock)\b", "sparks", "hero"),
    (r"\b(collaps\w*|crumbl\w*|cave.in|rubble|stampede|dust cloud)\b", "dust", "far"),
    (r"\b(splash\w*|dives? into the (water|sea|lake|river|pool)|jumps? into the (water|sea|lake|river|pool))\b", "splash", "hero"),
    (r"\b(fireworks?)\b", "fireworks", "place"),
    (r"\b(tornado|twister|whirlwind|hurricane)\b", "tornado", "far"),
    (r"\b(magic|spell|enchant\w*|wizard|sparkl\w*)\b", "magic", "hero"),
    (r"\b(steam(ing)?|mist|fog)\b", "steam", "hero"),
    (r"\b(earthquake|quake|tremor|the ground (shakes|heaves|trembles))\b", "quake", "place"),
    (r"\b(bubbl\w*|underwater)\b", "bubbles", "hero"),
]]


def verb_act(text):
    for rx, a in ACT_RULES:
        if rx.search(text):
            return a
    return ""


FIGURE = re.compile(r"\b(like|as if|as though|so-called|so to speak)\b[^.,;:!?]*", re.I)     # similes never drive the animation ("like one desk answering a thousand phones")


def direct_line(b, cast, world="city", prev_with=()):
    """Re-read one diorama line and make the animation do what the narrator says (see the block comment above)."""
    line = str(b.get("line") or "")
    if not line or b.get("kind") != "diorama":
        return b
    low = FIGURE.sub(" ", line.lower())
    names = cast_names(cast)
    # old saved choices are re-checked against the line before anything else (Oct 29, "Ten Times Louder")
    if b.get("remote"):
        b["remote"] = [r for r in b["remote"] if r.get("how") not in ("phone", "video") or REM_PHONE.search(low) or b.get("pose") in ("phone", "text") and not b.get("auto_dir")]
        if not b["remote"]:
            b.pop("remote")
    _l = low
    if b.get("amb") == "rain" and not re.search(r"\b(rain(s|ing|y|drops)?|downpour|drizzl\w*)\b", _l) or b.get("amb") == "snow" and not re.search(r"\b(snow\w*|blizzard|flakes)\b", _l) \
            or b.get("amb") == "confetti" and not re.search(r"\b(party(?![- ]effect)|confetti|fireworks|celebrat\w*)\b", _l):
        b.pop("amb", None)
    if b.get("pose") in DRAMA_POSES and not b.get("auto_dir") and not (b.get("pose") == "phone" and any(r.get("how") in ("phone", "video") for r in b.get("remote") or [])):
        rx = [r for r, a in ACT_RULES if a == b["pose"]]
        if rx and not any(r.search(_l) for r in rx):
            b["pose"], b["auto_dir"] = "stand", "pose"           # the line never says it: re-read below
    hit = {cid for n, cid in names.items() if re.search(r"\b%s\b" % re.escape(n), low)}
    if b.get("talker"):
        hit.add(b["talker"])
    with_ = [x for x in b.get("with") or []]
    rem = {r["id"]: r["how"] for r in b.get("remote") or []}
    if b.get("auto_vfx"):
        b.pop("vfx", None)
    pose = "" if b.get("auto_dir") == "pose" else (b.get("pose") or "")     # a pose this pass chose before is re-read from the line
    phone_pose = pose in ("phone", "text", "scroll", "selfie")
    for cid in hit:
        if cid in rem:
            continue
        how = ""
        if REM_PHONE.search(low) or (phone_pose and (cid == b.get("talker") or cid in with_)):
            how = "video" if REM_VIDEO.search(low) else "phone"
        elif REM_TV.search(low):
            how = "tv"
        elif REM_FAR.search(low):
            how = "far"
        elif cid in prev_with and not REM_HEARD_FROM.search(low):
            how = ""                                   # in the room the line before: still here (no "voice" bubble mid-conversation)
        elif REM_HEARD_FROM.search(low) or (REM_HEARD.search(low) and cid not in with_):
            how = "heard"
        elif REM_THOUGHT.search(low) and (cid not in with_ or REM_MEMORY.search(low)) and cid not in prev_with:
            how = "thought"
        if how:
            rem[cid] = how
    # a pet the line mentions by its kind ("your dog barks") is the cast's pet, on screen with the hero
    for c in cast:
        sp = (c.get("look") or {}).get("species")
        words = [w for w, k in SPECIES_WORDS.items() if k == sp] + [sp] if sp else []
        if sp and c["id"] not in rem and c["id"] not in with_ and re.search(r"\b(your|my|his|her|the|their|our) (%s)\b" % "|".join(map(re.escape, words)), low):
            with_.append(c["id"])
            b["with"] = with_
            if re.search(r"\b(bark|meow|moo|roar|howl|growl|purr|chirp)", low):
                b["acts"] = dict(b.get("acts") or {}, **{c["id"]: "speak"})
    if rem:
        b["remote"] = [{"id": k, "how": v} for k, v in rem.items()][:3]
        b["with"] = [x for x in with_ if x not in rem]
    # the hero's verb: read the line without the clauses whose subject is another person ("Dana sips her tea" is Dana's)
    hero_txt, acts = low, dict(b.get("acts") or {})
    for n, cid in names.items():
        m = re.search(r"\b%s\b((?:\W+\w+){1,7})" % re.escape(n), low)
        if m:
            clause = re.split(r"[,;]|\b(?:and|while|as|but|then|so|when|until)\s+(?:you|your|i|we)\b", m.group(1))[0]   # "Dana hands you the keys and you drive"
            a = verb_act(clause)
            if cid in with_ and (next((c for c in cast if c["id"] == cid), {}).get("look") or {}).get("species"):
                a = "speak" if re.search(r"\b(bark|meow|moo|roar|howl|growl|purr|chirp)", clause) else "sleep" if "sleep" in clause else "run" if re.search(r"\b(run|chase)", clause) else ""
                if a:
                    acts[cid] = a
                hero_txt = hero_txt.replace(n + clause, " ")
                continue
            here = not any(r["id"] == cid for r in b.get("remote") or [])
            if a and here and a not in RIDE_ACTS and cid not in (b.get("with") or []) and a not in ("think", "look") and len(b.get("with") or []) < 3:
                b["with"] = (b.get("with") or []) + [cid]          # the script shows them DOING something here: they are in the scene
                with_ = b["with"]
            if a and cid in (b.get("with") or []) and (cid not in acts or acts[cid] in GENERIC_POSES) and a not in RIDE_ACTS:
                acts[cid] = a                                      # the narrated verb beats a generic stand / explain
            if here and not b.get("talker") and SPEECH.search(clause) and cid in (b.get("with") or []):
                b["talker"] = cid
            if a and a not in RIDE_ACTS:                      # what a far-away / on-screen person does inside their bubble
                for r in b.get("remote") or []:
                    if r["id"] == cid and not r.get("act") and r["how"] != "heard":
                        r["act"] = a
            hero_txt = hero_txt.replace(n + clause, " ")
    va = verb_act(hero_txt)
    if not pose and b.get("auto_dir") == "pose" and not va and b.get("pose") not in GENERIC_POSES and b.get("pose") not in ("look", "listen", "think") and not (b.get("pose") in ("phone", "text") and b.get("remote")):
        b["pose"] = "stand"                     # a pose this pass once chose that the line no longer supports
    # Oct 29 (user: "a soldier eating his last crumbs of bread shows the hero eating instead"): a pose whose words only appear
    # in ANOTHER character's clause belongs to them - the hero watches (or does their own verb) instead
    cur = b.get("pose") or ""
    if cur and cur not in GENERIC_POSES:
        rx = [r for r, a in ACT_RULES if a == cur]
        if rx and any(r.search(low) for r in rx) and not any(r.search(hero_txt) for r in rx):
            for cid in (b.get("with") or []):
                ns = [n for n, i in names.items() if i == cid]
                m2 = ns and re.search(r"\b(%s)\b((?:\W+\w+){1,9})" % "|".join(map(re.escape, ns)), low)
                if m2 and any(r.search(m2.group(2)) for r in rx):
                    acts[cid] = cur
                    break
            b["pose"], b["auto_dir"], pose = (va or "stand"), "pose", ""
    if acts:
        b["acts"] = {k: v for k, v in acts.items() if k in (b.get("with") or [])}
    prx = [r for r, a in ACT_RULES if a == pose] if pose else []
    unsupported = bool(prx) and not any(r.search(hero_txt) for r in prx)
    if va and (pose in GENERIC_POSES or (unsupported and va in STRONG_ACTS) or (va in RIDE_ACTS and pose not in RIDE_ACTS) or (va in STRONG_ACTS and pose not in STRONG_ACTS) or (pose in ("think", "listen") and va in ("phone", "text"))):
        b["pose"], b["auto_dir"] = va, "pose"
    if rem and b.get("pose") in GENERIC_POSES:
        h = next(iter(rem.values()))
        b["pose"] = {"phone": "phone", "video": "text", "far": "look", "heard": "listen", "thought": "think", "tv": "stand"}.get(h, b["pose"])
    if b.get("pose") == "sleep" and (b.get("place"), b.get("station")) != ("apartment", "bed"):
        b["pose"] = "tired"
    # animals, crowds, weather the line mentions
    species = motion_library.vocab().get("species") or {}
    pets = {c["look"].get("species") for c in cast if c.get("look", {}).get("species")}
    if not b.get("animals"):
        an = []
        for w in re.findall(r"[a-z]+", low):
            k = SPECIES_WORDS.get(w, w)
            if k in species and k not in pets and k not in [a["kind"] for a in an] and not (k == "horse" and b.get("pose") == "horse"):
                act = "speak" if re.search(r"\b(bark|meow|moo|roar|sing|chirp|howl)", low) else "sleep" if re.search(r"\bsleep", low) else "run" if re.search(r"\b(run|chase|race)", low) else "follow"
                an.append({"kind": k, "act": act})
        if an:
            b["animals"] = an[:2]
    from motion_library import vocab as _v
    acts_v = _v().get("acts") or {}
    cat = (acts_v.get(b.get("pose")) or {}).get("cat")
    gm = GROUP_RE.search(low)                                  # "the soldiers cheer": the crowd does what the line says
    if gm:
        ga = verb_act(re.split(r"[,;]", gm.group(2))[0])
        if ga and ga not in RIDE_ACTS:
            ex = dict(b.get("extras") or {"n": 3, "look": {"outfit": "military", "hat": "helmet"} if world == "war" or cat == "war" else {}})
            if not ex.get("act") or ex["act"] in GENERIC_POSES or ex["act"] == "soldier":
                ex["act"] = ga
            b["extras"] = ex
    if not b.get("extras") and not b.get("with"):
        if cat == "war" or (world == "war" and re.search(r"\b(soldiers|troops|we|platoon|men|comrades)\b", low)):
            b["extras"] = {"n": 2, "act": "charge" if b.get("pose") == "charge" else "soldier", "look": {"outfit": "military", "hat": "helmet"}}
        elif re.search(r"\b(crowd|everyone cheers|fans|audience|the whole (town|village|team))\b", low):
            b["extras"] = {"n": 3, "act": "cheer" if re.search(r"cheer|celebrat|win|won|goal", low) else "clap", "look": {}}
        elif re.search(r"\b(team|teammates)\b", low) and cat == "sport":
            b["extras"] = {"n": 2, "act": "cheer", "look": {"outfit": "jersey"}}
    if not b.get("vfx"):
        fx = []
        for rx, kind, at in VFX_RULES:
            if rx.search(low) and kind not in [f["kind"] for f in fx]:
                fx.append({"kind": kind, "at": at})
        if fx:
            b["vfx"], b["auto_vfx"] = fx[:2], True
    if not b.get("amb"):
        if re.search(r"\b(rain(s|ing|y|drops)?|downpour|drizzl\w*|pouring rain)\b", low):
            b["amb"] = "rain"
        elif re.search(r"\b(snow(s|ing|y)?|blizzard)\b", low) and world != "snow":
            b["amb"] = "snow"
        elif re.search(r"\b(party(?![- ]effect)|confetti|fireworks)\b", low):
            b["amb"] = "confetti"
    return b


STATION_WORDS = {"stove": "stove kitchen oven", "window": "window windows", "table": "table dinner", "counter": "counter bar", "bed": "bed", "desk": "desk",
                  "fridge": "fridge", "door": "door gate", "fire": "fire fireplace", "cots": "cot cots bed", "wire": "wire", "tent": "tent"}


NAME_STOP = {"the", "old", "young", "little", "big", "his", "her", "their", "your", "our", "friend", "person", "man", "woman", "girl", "boy", "kid", "child",
             "mr", "mrs", "ms", "dr", "who", "and", "of", "a", "an", "one", "other", "main", "best", "new",
             "platoon", "farm", "family", "team", "army", "home", "house", "town", "village", "hospital", "school", "office", "city", "war", "front", "crew", "unit"}


def cast_names(cast):
    """Every way the narration can name a cast member -> its id (Oct 29, user: "if NPCs are mentioned in the script, their actions
    need to match what the script is saying"): the id, the full name, each name word ("Sergeant Cole" -> sergeant, cole) and the
    role words ("the nurse", "the sheepdog"). A word two people share is dropped. Longest first, so "nurse ellis" wins."""
    seen = {}
    for c in cast:
        toks = {c["id"], str(c.get("name") or "").lower()} | set(re.findall(r"[a-z]{3,}", str(c.get("name") or "").lower())) | \
            set(re.findall(r"[a-z]{4,}", re.split(r"\b(?:who|that|which|at|in|on|of|from|across|with|for|to|and|whose)\b|[,;(]", str(c.get("role") or "").lower())[0])[-1:])      # a role's head noun only ("field hospital NURSE")
        sp = (c.get("look") or {}).get("species")
        if sp:
            toks |= {sp} | {w for w, k in SPECIES_WORDS.items() if k == sp}
        for n in toks:
            n = n.strip()
            if n and len(n) > 1 and n not in NAME_STOP:
                seen.setdefault(n, set()).add(c["id"])
    out = {n: next(iter(ids)) for n, ids in seen.items() if len(ids) == 1}
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0])))


SPEECH = re.compile(r"\b(says?|said|asks?|asked|tells?|told|whispers?|whispered|shouts?|shouted|yells?|yelled|calls? out|replies|answers?|promis\w*|jok(es|ing)|sings?)\b")
GROUP_RE = re.compile(r"\b(soldiers|troops|the men|platoon|crowd|fans|people|villagers|kids|children|players|teammates|the team|nurses|workers|customers|guests|everyone|townsfolk|students|passengers)\b((?:\W+\w+){1,6})")


def who_goes_where(b, cast, stations, prev):
    """The line's SUBJECT goes to the spot (Oct 29, user: "when it says father goes to the window the hero goes to the window
    instead"). The writer gives one station per line and it moves the HERO; when the station word sits in a cast member's own
    clause ("Father is at the window…"), that person stands at the spot (beat.at) and the hero stays where they were."""
    if not stations:
        return
    low = str(b.get("line") or "").lower()
    names = cast_names(cast)
    at, hero_txt = {}, low
    for n, cid in names.items():
        m = re.search(r"\b%s\b((?:\W+\w+){1,8})" % re.escape(n), low)
        if not m:
            continue
        clause = re.split(r"[,;]|\b(?:and|while|as|but|then|so|when|until)\s+(?:you|your|i|we|he|she)\b", m.group(1))[0]
        hero_txt = hero_txt.replace(n + clause, " ")
        for st in stations:
            if st == "center":
                continue
            words = (STATION_WORDS.get(st, "") + " " + st.replace("_", " ")).split()
            if any(re.search(r"\b%s\b" % re.escape(w), clause) for w in words):
                at[cid] = st
                break
    if not at:
        b.pop("at", None)
        return
    b["at"] = at
    for cid in at:
        if cid not in (b.get("with") or []) and not any(r["id"] == cid for r in b.get("remote") or []):
            b["with"] = ((b.get("with") or []) + [cid])[:3]
    hero_named = any(re.search(r"\b%s\b" % re.escape(w), hero_txt) for w in (STATION_WORDS.get(b.get("station"), "") + " " + str(b.get("station") or "")).split() if w)
    if b.get("station") in at.values() and not hero_named:      # the spot belongs to them this line: the hero stays where they were
        b["station"] = prev["station"] if prev and prev.get("place") == b.get("place") and prev.get("station") not in at.values() else "center"


def keep_present(beats):
    """Someone in the room the line before AND the line after (same place) stays for the line between, unless that line puts them
    somewhere else - no one-line vanish-and-reappear (Varga in "She calls it the cocktail-party effect")."""
    ds = [b for b in beats if b.get("kind") == "diorama"]
    for i in range(1, len(ds) - 1):
        a, b, c = ds[i - 1], ds[i], ds[i + 1]
        if not (a.get("place") == b.get("place") == c.get("place")) or b.get("flash") != a.get("flash"):
            continue
        away = {r["id"] for r in b.get("remote") or []}
        for cid in set(a.get("with") or []) & set(c.get("with") or []):
            if cid not in (b.get("with") or []) and cid not in away and len(b.get("with") or []) < 3:
                b["with"] = (b.get("with") or []) + [cid]


FLASH_CUE = re.compile(r"\b(he|she|you|i|they) (is|are|am|was|were) (back )?home\b|\bback home\b|\bin (his|her|your|my|their) (mind|memory|head)\b|\bremember\w*|\bmemor(y|ies)\b|"
                       r"\bflash(es)? back\b|\bfalls? away\b|\bdream\w*", re.I)


PRESENT_RE = re.compile(r"\b(with you|beside you|next to you|in front of you|behind you|to you|at you|hands you|gives you|shows you|tells you|asks you|meets you|greets you|seats you|leads you|walks in|comes in|arrives|joins you|enters|turns to|sits down|stands up|in the room|across the table|her door|his door|their door)\b")


def mention_only(b, cast, prev_with, prev_rem=None):
    """A cast member in `with` whom the line only MENTIONS - a name that stands out, a source, a person talked about - with no sign
    they are physically there (no action of their own, nothing they do to you, not here the line before) is shown in a
    'mentioned' bubble instead of popping into the room like a ghost."""
    names = cast_names(cast)
    low = str(b.get("line") or "").lower()
    keep, rem = [], list(b.get("remote") or [])
    for cid in b.get("with") or []:
        c = next((x for x in cast if x["id"] == cid), {})
        ns = [n for n, i in names.items() if i == cid]
        m = ns and re.search(r"\b(%s)\b((?:\W+\w+){1,8})" % "|".join(map(re.escape, ns)), low)
        if (c.get("look") or {}).get("species"):
            keep.append(cid)
            continue
        if not m:                                  # listed but not named in the line: carry on how they were, else read the line, else not here
            was = (prev_rem or {}).get(cid)
            how = was if was in ("far", "phone", "video", "tv", "heard") else "far" if REM_FAR.search(low) else "heard" if REM_HEARD_FROM.search(low) else ""
            if how and not any(r["id"] == cid for r in rem):
                rem.append({"id": cid, "how": how})
            elif not how and (cid in prev_with or cid == b.get("talker") or PRESENT_RE.search(low)):
                keep.append(cid)
            continue
        clause = re.split(r"[,;:]|\b(?:and|while|as|but|then|so|when|until)\s+(?:you|your|i|we|he|she)\b", m.group(2))[0]
        acted = bool(verb_act(clause)) or bool(re.search(r"\b(%s)\b\W+\w+s (you|him|her)\b" % "|".join(map(re.escape, ns)), low))
        present = acted or PRESENT_RE.search(low) or cid in prev_with or cid == b.get("talker") and re.search(r"['\"\u201c]", low)
        if present:
            keep.append(cid)
        elif not any(r["id"] == cid for r in rem):
            rem.append({"id": cid, "how": "mention"})
    b["with"] = keep
    if rem:
        b["remote"] = rem[:3]


def direct_all(p):
    """Run the narration pass over every diorama line of a film, then mark FLASHBACKS (Oct 29, first war test film: "he is home"
    walked the hero across the battlefield to the farmhouse, and the family there was drawn as thought bubbles). A run of lines
    that leaves the real place on a memory cue is a flashback: the hero CUTS there (no walk), the people of the memory are in the
    room, and the engine tints it as a memory; it ends when the story comes back to the real place."""
    cast, world = p.get("dio_cast") or [], p.get("dio_world") or "city"
    pets = {c["look"].get("species") for c in cast if (c.get("look") or {}).get("species")}
    real, flash = None, False
    try:
        pls = dio_places(p.get("dio_kits") or [], world)
    except Exception:
        pls = {}
    prev = None
    for b in p.get("beats") or []:
        direct_line(b, cast, world, (prev or {}).get("with") or [] if prev and prev.get("place") == b.get("place") else [])
        if b.get("kind") == "diorama":
            same = bool(prev) and prev.get("place") == b.get("place")
            mention_only(b, cast, (prev.get("with") or []) if same else [], {r["id"]: r["how"] for r in (prev.get("remote") or [])} if same else {})
            who_goes_where(b, cast, pls.get(b.get("place")) or [], prev)
            prev = b
        if b.get("kind") != "diorama":
            continue
        pl, rem = b.get("place"), b.get("remote") or []
        if real is None:
            real = pl
        if pl != real and (flash or FLASH_CUE.search(b.get("line") or "") or (rem and all(r["how"] == "thought" for r in rem))):
            flash = True
        else:
            flash, real = False, pl
        if flash:
            b["flash"] = True
            if b.get("auto_vfx"):                          # a memory is quiet: no shells in mother's kitchen
                b.pop("vfx", None)
            th = [r["id"] for r in rem if r["how"] == "thought"]
            acts = dict(b.get("acts") or {}, **{r["id"]: r["act"] for r in rem if r["how"] == "thought" and r.get("act")})     # what they do in the memory
            if acts:
                b["acts"] = acts
            b["with"] = ((b.get("with") or []) + [x for x in th if x not in (b.get("with") or [])])[:3]
            b["remote"] = [r for r in rem if r["how"] != "thought"]
            if not b["remote"]:
                b.pop("remote")
            if b.get("animals"):
                b["animals"] = [a for a in b["animals"] if a["kind"] not in pets] or None
                if not b["animals"]:
                    b.pop("animals")
        else:
            b.pop("flash", None)
    keep_present(p.get("beats") or [])
clamp = lambda x, a=0.0, b=1.0: a if x < a else b if x > b else x
DIO_EX = {"neutral": .5, "calm": .42, "happy": .62, "surprised": .8, "stressed": .72, "wonder": .6, "focused": .52, "sad": .45, "scared": .85, "angry": .82}
MOTIONS = ["none", "float", "fly", "spin", "pulse", "swing", "bounce", "drive", "sway", "flicker", "grow", "shake", "orbit", "wobble"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def shots_from_writer(beats):
    """Writer's shot numbers → cut flags (a cut starts a new continuous shot). No numbers → cut at titles and every 4 beats."""
    shots = [b.get("shot") for b in beats]                 # read them all first: the loop removes the field as it goes
    have = any(shots)
    run = 0
    for i, b in enumerate(beats):
        if have:
            b["cut"] = i == 0 or shots[i] != shots[i - 1] or b["kind"] == "endcard"
        else:
            b["cut"] = i == 0 or b["kind"] in ("title", "endcard") or run >= 4
        run = 1 if b["cut"] else run + 1
        b.pop("shot", None)


def shot_groups(beats, continuous=True):
    """Consecutive beats between cuts = one continuous shot (max 6 stations; the end card always stands alone)."""
    groups = []
    for b in beats:
        new = (not continuous or b.get("cut") or b["kind"] == "endcard" or not groups or groups[-1][-1]["kind"] == "endcard"
               or len(groups[-1]) >= 6)
        if new:
            groups.append([b])
        else:
            groups[-1].append(b)
    return groups


def _figure(f):
    f = f if isinstance(f, dict) else {}
    out = {"outfit": f.get("outfit") if f.get("outfit") in OUTFITS else "casual", "hair": f.get("hair") if f.get("hair") in HAIRS else "short",
           "accessory": f.get("accessory") if f.get("accessory") in ACCESSORIES else "", "beard": bool(f.get("beard"))}
    for k in ("skin", "hairColor", "color", "color2"):
        if _HEX.match(str(f.get(k) or "")):
            out[k] = f[k]
    if str(f.get("number") or "").strip():
        out["number"] = str(f["number"])[:2]
    return out


def motion_for(concept):
    ks = _keys(concept)
    for m, words in MOTION_FOR:
        ws = words.split()
        if any(k in ws for k in ks):
            return m
    return "float"


# ── stop: any step can be halted; the work done so far is kept and the project waits at the nearest checkpoint ──
_STOP = {}


class Stopped(Exception):
    pass


def check(p):
    if _STOP.get(p["id"]):
        raise Stopped()


# where a stopped step leaves the project: everything before it is kept, so continuing never redoes finished work
CHECKPOINT = {"script": "script", "voice": "script", "assets": "assets", "render": "assets", "publish": "final"}


# ── voice + word cues ──────────────────────────────────────────────────────────────────────────────────────
VO_TIMEOUT = 120
VO_TIMEOUT_EXPRESSIVE = 300          # the first line also loads the model (~30-60 s)
VOICE_ENGINES = ["chatterbox", "kokoro"]       # chatterbox = acted narration (GPU), kokoro = fast + flat (CPU, the fallback)
INTENSITIES = {"calm": (0.75, 0.5), "balanced": (1.0, 0.4), "dramatic": (1.3, 0.3)}     # (emotion scale, cfg: lower = slower/more deliberate)
MOOD_EX = {"happy": 0.7, "surprised": 0.85, "angry": 0.9, "determined": 0.65, "sad": 0.45, "scared": 0.9}


def acting(p, b):
    """How hard a line is acted: the scene's mood sets the emotion, the project's intensity scales it."""
    scale, cfg = INTENSITIES.get(p.get("voice_intensity") or "dramatic", INTENSITIES["dramatic"])
    ex = MOOD_EX.get(b.get("mood") or "", 0.55) * scale
    if b.get("mood") == "sad":
        cfg = min(cfg, 0.3)                                   # sad lines: slow and heavy
    return round(max(0.25, min(1.0, ex)), 2), cfg


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}


def _num_words(n):
    return _ONES[n] if n < 20 else _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])


def speakable(text, kokoro=False):
    """What the narrator SAYS (Oct 29, user: "every time the narrator mentions the time it says three thousand and seven AM instead
    of three oh seven"): clock times become words before the voice reads them - 3:07 AM -> "three oh seven A.M.", 3:40 -> "three
    forty", 3:00 -> "three o'clock", 3 AM -> "three A.M.". The captions keep the digits (align_words maps the spoken words back)."""
    def ampm(m):
        end = "." if (m or "").endswith(".") else ""; x = (m or "").lower().replace(".", "").strip()
        return ((" AM" + end if kokoro else " A.M.") if x == "am" else (" PM" + end if kokoro else " P.M.") if x == "pm" else "")     # Kokoro: "A.M." comes out "A, M"

    def clock(m):
        h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if h > 24 or mi > 59:
            return m.group(0)
        hw = _num_words(h) if h < 60 else str(h)
        if mi == 0:
            return hw + (ampm(ap) or " o'clock")
        return hw + (" oh " + _ONES[mi] if mi < 10 else " " + _num_words(mi)) + ampm(ap)
    text = re.sub(r"\b(\d{1,2}):(\d{2})(?:\s*([AaPp]\.?\s?[Mm]\.?))?(?![\d:])", clock, str(text or ""))
    text = re.sub(r"\b(\d{1,2})\s*([AaPp]\.?\s?[Mm]\.?)(?=[\s,.;:!?]|$)", lambda m: (_num_words(int(m.group(1))) if int(m.group(1)) <= 24 else m.group(1)) + ampm(m.group(2)), text)
    return text


def _say(text, voice, engine="kokoro", ex=0.6, cfg=0.4):
    """→ (wav, engine actually used). Chatterbox first when asked; Kokoro whenever it fails or hangs."""
    import tts
    raw, text = text, speakable(text)
    box = {}

    def go(fn):
        try:
            box["wav"] = fn()
        except Exception as e:
            box["err"] = e

    if engine == "chatterbox":
        import tts_expressive
        if tts_expressive.available():
            t = threading.Thread(target=go, args=(lambda: tts_expressive.say(text, voice, ex, cfg),), daemon=True, name="mg-vo-x")
            t.start()
            t.join(VO_TIMEOUT_EXPRESSIVE)
            if not t.is_alive() and box.get("wav"):
                return box["wav"], "chatterbox"
            box.clear()
    t = threading.Thread(target=go, args=(lambda: tts.say(speakable(raw, kokoro=True), voice, 1.0),), daemon=True, name="mg-vo")
    t.start()
    t.join(VO_TIMEOUT)
    if t.is_alive() or "err" in box:
        return None, ""
    return box.get("wav"), "kokoro"


def _free_comfy():
    """Ask ComfyUI to drop its models so the narrator fits on the GPU (it reloads them on its next job)."""
    try:
        import urllib.request
        rq = urllib.request.Request("http://127.0.0.1:8188/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                    headers={"Content-Type": "application/json"})
        urllib.request.urlopen(rq, timeout=10).read()
    except Exception:
        pass


_norm = lambda w: re.sub(r"[^a-z0-9]", "", str(w or "").lower())


def align_words(line, words):
    """Captions + cues use the SCRIPT's words with the recogniser's timings: an acted read is sometimes misheard ("fridge" →
    "fringe", "Ninety" → "90"), so matched words keep their timing, misheard ones are swapped for the script's word, and words
    the recogniser dropped share the gap they fall in."""
    import difflib
    toks = [t for t in str(line or "").split() if _norm(t)]
    ws = [x for x in words or [] if _norm(x.get("w"))]
    if not toks or not ws:
        return words or []
    out = []
    sm = difflib.SequenceMatcher(a=[_norm(t) for t in toks], b=[_norm(x["w"]) for x in ws], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":                                   # script words never heard: placed later, between neighbours
            out += [{"w": t, "s": None, "e": None} for t in toks[i1:i2]]
            continue
        if op == "insert":                                   # extra recognised words (fillers): dropped
            continue
        seg = ws[j1:j2]
        if op == "equal" or i2 - i1 == j2 - j1:
            out += [{"w": t, "s": x["s"], "e": x["e"]} for t, x in zip(toks[i1:i2], seg)]
        else:                                                # n script words over m heard words: share that time span
            s0, e0, n = float(seg[0]["s"]), float(seg[-1]["e"]), i2 - i1
            out += [{"w": t, "s": round(s0 + (e0 - s0) * k / n, 2), "e": round(s0 + (e0 - s0) * (k + 1) / n, 2)} for k, t in enumerate(toks[i1:i2])]
    k = 0
    while k < len(out):                                      # fill unheard words evenly inside their gap
        if out[k]["s"] is None:
            j = k
            while j < len(out) and out[j]["s"] is None:
                j += 1
            a_ = float(out[k - 1]["e"]) if k else float(ws[0]["s"])
            b_ = float(out[j]["s"]) if j < len(out) else float(ws[-1]["e"])
            b_ = max(b_, a_ + 0.1 * (j - k))
            for m in range(k, j):
                out[m]["s"] = round(a_ + (b_ - a_) * (m - k) / (j - k), 2)
                out[m]["e"] = round(a_ + (b_ - a_) * (m - k + 1) / (j - k), 2)
            k = j
        k += 1
    return out


def cue_time(words, cue, fallback):
    """Start time of the first spoken word matching the cue (exact, then prefix), else the fallback spread."""
    c = _norm(cue)
    if c and words:
        for w in words:
            if _norm(w.get("w")) == c:
                return round(float(w.get("s") or 0), 2)
        for w in words:
            n = _norm(w.get("w"))
            if n and (n.startswith(c) or c.startswith(n) and len(n) > 3):
                return round(float(w.get("s") or 0), 2)
    return fallback


def step_voice_dio(p, hk, sid=""):
    """Diorama narration: consecutive lines are read in ONE take (~25 s each) so the delivery flows; the takes play back to
    back and every scene lasts exactly as long as its words (no fixed minimum = no dead air)."""
    import hashlib
    import tts
    p["stage"] = "voice"
    voice = p.get("voice") if p.get("voice") in tts.VOICES else motion_util.DEF_VOICE
    engine = p.get("voice_engine") if p.get("voice_engine") in VOICE_ENGINES else "chatterbox"
    scale, cfg = INTENSITIES.get(p.get("voice_intensity") or "dramatic", INTENSITIES["dramatic"])
    beats = [b for b in p["beats"] if b["kind"] != "endcard"]
    groups, cur, n = [], [], 0
    for b in beats:
        if cur and n + len(b["line"]) > 360:
            groups.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b["line"]) + 1
    if cur:
        groups.append(cur)
    old = {t.get("sig"): t for t in p.get("takes") or []}
    takes, gpu = [], False
    try:
        for gi, g in enumerate(groups):
            text = " ".join(b["line"].strip() for b in g)
            ex = round(clamp(sum(DIO_EX.get(b.get("mood"), .5) for b in g) / len(g) * scale, .25, 1.0), 2) if engine == "chatterbox" else 0
            sig = hashlib.sha1(("%s|%s|%s|%.2f|%.2f" % (speakable(text), voice, engine, ex, cfg)).encode("utf-8")).hexdigest()[:16]
            tk = old.get(sig)
            if not (tk and tk.get("vo") and os.path.isfile(os.path.join(core.LIB, tk["vo"]))):
                check(p)
                p["stage_note"] = "voice take %d/%d" % (gi + 1, len(groups))
                save(p)
                if engine == "chatterbox" and not gpu:
                    import tts_expressive
                    tts_expressive.gpu_lock(True)
                    _free_comfy()
                    gpu = True
                    log(p, "expressive narrator (Chatterbox) warming up on the GPU…", "info")
                wav, used = _say(text, voice, engine, ex, cfg)
                if not wav:
                    raise RuntimeError("the narrator didn't answer on take %d" % (gi + 1))
                name = motion_util._to_lib(wav, p["user"], sid, text[:300])
                try:
                    core.index_add(name, dict(core.index().get(name) or {}, model=used, mode="motion-vo"))
                except Exception:
                    pass
                tk = {"sig": sig, "vo": name, "dur": round(motion_util._wav_secs(wav), 2), "words": None, "engine": used}
                log(p, "take %d/%d · %d lines · %.1f s%s" % (gi + 1, len(groups), len(g), tk["dur"], "" if used == engine else " (fast voice)"), "done")
            takes.append(dict(tk, text=text))
            for b in g:
                b.update(vo=tk["vo"], vo_line=b["line"], vo_sig=sig)
    finally:
        if gpu:
            import tts_expressive
            tts_expressive.unload()
            tts_expressive.gpu_lock(False)
    # word timings AFTER the narrator has let go of the GPU (running both at once made the recogniser fail silently)
    for gi, tk in enumerate(takes):
        text = tk.pop("text")
        toks = [x for x in text.split() if _norm(x)]
        if tk.get("words") is None or len(tk["words"]) != len(toks):
            check(p)
            p["stage_note"] = "timing take %d/%d" % (gi + 1, len(takes))
            save(p)
            try:
                heard = [{"w": w.get("w"), "s": round(float(w.get("s") or 0), 2), "e": round(float(w.get("e") or 0), 2)} for w in hk["words"](os.path.join(core.LIB, tk["vo"]))]
            except Exception:
                heard = []
            words = align_words(text, heard) if heard else []
            if len(words) != len(toks):                        # nothing recognised: spread the words over the take by length
                dur, tot, acc, words = tk["dur"], sum(len(x) + 1 for x in toks) or 1, 0.0, []
                for x in toks:
                    a = .15 + (dur - .3) * acc / tot
                    acc += len(x) + 1
                    words.append({"w": x, "s": round(a, 2), "e": round(.15 + (dur - .3) * acc / tot, 2)})
                log(p, "take %d: no word timings - spread evenly" % (gi + 1), "warn")
            tk["words"] = words
    for g, tk in zip(groups, takes):
        k = 0
        for b in g:                                                # the take's words, handed out line by line
            nt = len([x for x in b["line"].split() if _norm(x)])
            b["_tw"] = tk["words"][k:k + nt]
            k += nt
    off = 0.0
    for g, tk in zip(groups, takes):
        tk["at"] = round(off, 2)
        for b in g:
            b["words"] = [{"w": w["w"], "s": round(float(w["s"]) + off, 2), "e": round(float(w["e"]) + off, 2)} for w in b.pop("_tw", [])]
        off += tk["dur"] + 0.18
    p["takes"] = takes
    for i, b in enumerate(beats):                                  # a scene starts just before its first word…
        s0 = b["words"][0]["s"] if b["words"] else (beats[i - 1]["t0"] + .6 if i else 0)
        b["t0"] = round(max(0.0, s0 - 0.12), 2)
    for i, b in enumerate(beats):                                  # …and runs until the next one starts
        b["t1"] = beats[i + 1]["t0"] if i + 1 < len(beats) else round((b["words"][-1]["e"] if b["words"] else b["t0"] + 2) + 0.8, 2)
        b["t1"] = max(b["t1"], b["t0"] + .4)
        b["dur"] = round(b["t1"] - b["t0"], 2)
        b["cue_t"] = cue_time(b["words"], b.get("cue"), round(b["t0"] + .25, 2))
    for i, b in enumerate(p["beats"]):                              # the end card has its own short line
        if b["kind"] == "endcard" and not (b.get("vo") and b.get("vo_line") == b["line"]):
            wav, used = _say(b["line"], voice, "kokoro" if engine != "chatterbox" else engine, .5, cfg)
            if used == "chatterbox":
                import tts_expressive
                tts_expressive.unload()                            # let go of the GPU before the recogniser times the line
            if wav:
                _voice_take(p, b, i, wav, hk, sid)
    retime(p)
    save(p)


def step_voice(p, hk, sid=""):
    import tts
    if p.get("format") == "diorama":
        return step_voice_dio(p, hk, sid)
    p["stage"] = "voice"
    voice0 = p.get("voice") if p.get("voice") in tts.VOICES else motion_util.DEF_VOICE
    cast = {c["id"]: c for c in p.get("cast") or []}
    beats = p["beats"]
    engine = p.get("voice_engine") if p.get("voice_engine") in VOICE_ENGINES else "chatterbox"
    gpu = False
    try:
        for i, b in enumerate(beats):
            sp = cast.get(b.get("speaker") or "")
            voice = sp["voice"] if sp and sp.get("voice") in tts.VOICES else voice0    # dialogue lines use the character's voice
            ex, cfg = acting(p, b) if engine == "chatterbox" else (0, 0)
            sig = "%s|%s|%.2f|%.2f" % (voice, engine, ex, cfg) if engine == "chatterbox" else "%s|kokoro" % voice
            if b.get("vo") and b.get("vo_line") == b["line"] and b.get("vo_sig", "%s|kokoro" % b.get("vo_voice", voice)) == sig:
                continue                                              # unchanged line + voice + acting: keep its take and timings
            b["vo_voice"] = voice
            check(p)
            p["stage_note"] = "voice %d/%d" % (i + 1, len(beats))
            save(p)
            if engine == "chatterbox" and not gpu:
                import tts_expressive
                tts_expressive.gpu_lock(True)                         # the art batch waits; ComfyUI lets go of its models
                _free_comfy()
                gpu = True
                log(p, "expressive narrator (Chatterbox) warming up on the GPU…", "info")
            wav, used = _say(b["line"], voice, engine, ex, cfg)
            if not wav:
                log(p, "beat %d: voice engine didn't answer — no narration on this beat" % (i + 1), "warn")
                b.update(vo="", vo_dur=0, words=[])
                continue
            if used != engine:
                log(p, "beat %d: expressive narrator failed — used the fast voice" % (i + 1), "warn")
            b["vo_sig"] = sig if used == engine else "%s|kokoro" % voice
            _voice_take(p, b, i, wav, hk, sid)
    finally:
        if gpu:
            import tts_expressive
            tts_expressive.unload()                                   # hand the GPU back for the AI scenes / art
            tts_expressive.gpu_lock(False)
    retime(p)
    save(p)


def _voice_take(p, b, i, wav, hk, sid):
    """Store one recorded line in the library + its word timings (drive cues, captions and mouths)."""
    b["vo"] = motion_util._to_lib(wav, p["user"], sid, b["line"])
    if "chatterbox" in (b.get("vo_sig") or ""):
        try:
            core.index_add(b["vo"], dict(core.index().get(b["vo"]) or {}, model="chatterbox", mode="motion-vo"))
        except Exception:
            pass
    b["vo_dur"] = round(motion_util._wav_secs(wav), 2)
    b["vo_line"] = b["line"]
    try:
        b["words"] = align_words(b["line"], [{"w": w.get("w"), "s": round(float(w.get("s") or 0), 2), "e": round(float(w.get("e") or 0), 2)}
                                             for w in hk["words"](wav)])
    except Exception as e:
        log(p, "beat %d: no word timings (%s) — visuals spread evenly" % (i + 1, str(e)[:80]), "warn")
        b["words"] = []
    log(p, "beat %d voiced · %.1f s · %d words" % (i + 1, b["vo_dur"], len(b["words"])), "done")


def retime(p):
    """Beat lengths + visual cue times from the voice (or the style's defaults when a beat has no narration)."""
    if p.get("format") == "diorama":
        for b in p["beats"]:
            if b["kind"] == "endcard":
                b["dur"] = round(max(5.0, (b.get("vo_dur") or 0) + 1.2), 2)
            elif b.get("t1") is not None:
                b["dur"] = round(max(.4, b["t1"] - b["t0"]), 2)
            else:
                b["dur"] = 3.0
        return
    for b in p["beats"]:
        base = KINDS.get(b["kind"], 4)
        b["dur"] = round(max(1.5, max(base, (b.get("vo_dur") or 0) + 1.1) + float(b.get("pad") or 0)), 2)
        words, n = b.get("words") or [], len(b.get("visuals") or [])
        for k, v in enumerate(b.get("visuals") or []):
            spread = round(0.35 + (b["dur"] - 1.6) * (k + 0.5) / max(1, n), 2)
            v["at"] = round(float(v["at_manual"]), 2) if v.get("at_manual") is not None else cue_time(words, v.get("cue"), spread)
        for k, it in enumerate(b.get("items") or []):
            it["at"] = round(float(it["at_manual"]), 2) if it.get("at_manual") is not None else cue_time(words, it.get("cue"), round(0.4 + k * 0.6, 2))


# ── assets: concept → picture ──────────────────────────────────────────────────────────────────────────────
STOP = {"the", "a", "an", "of", "and", "to", "in", "on", "with", "for", "is", "are", "big", "small", "little", "huge", "giant", "old", "new", "your", "my", "our", "its"}


def _keys(concept):
    ws = [_norm(w) for w in re.split(r"[\s/,_-]+", str(concept or "")) if _norm(w) and _norm(w) not in STOP]
    out = []
    for w in ws:                                   # crude singulars so "rockets" finds "rocket"
        out.append(w)
        if w.endswith("ies"):
            out.append(w[:-3] + "y")
        elif w.endswith("es") and len(w) > 4:
            out.append(w[:-2])
        if w.endswith("s") and len(w) > 3:
            out.append(w[:-1])
    return out


def find_art(style, concept):
    """AI cut-out for this concept in this style (manifest tag match) → concept id or None."""
    m = (art().get(style) or {})
    keys = _keys(concept)
    for k in keys:
        if k in m:
            return k
    for cid, e in m.items():
        tags = [_norm(t) for t in e.get("tags") or []]
        if any(k in tags for k in keys):
            return cid
    return None


# spoken words → the Lucide shape that reads best on screen (checked before the tag search)
SYN = {"time": "clock", "minute": "timer", "minutes": "timer", "second": "timer", "seconds": "timer", "hour": "clock", "light": "lightbulb",
       "energy": "zap", "lightning": "zap", "electricity": "zap", "power": "zap", "fast": "gauge", "speed": "gauge", "faster": "gauge",
       "heavy": "weight", "heavier": "weight", "mass": "weight", "weight": "weight", "universe": "orbit", "space": "orbit", "galaxy": "orbit",
       "cosmos": "orbit", "planet": "earth", "earth": "earth", "world": "globe", "money": "banknote", "cash": "banknote", "price": "tag",
       "idea": "lightbulb", "think": "brain", "mind": "brain", "people": "users", "person": "user", "team": "users", "love": "heart",
       "health": "heart-pulse", "growth": "trending-up", "rise": "trending-up", "fall": "trending-down", "drop": "trending-down",
       "danger": "triangle-alert", "warning": "triangle-alert", "risk": "triangle-alert", "safe": "shield-check", "security": "shield",
       "win": "trophy", "winner": "trophy", "goal": "target", "data": "database", "computer": "monitor", "ai": "bot", "robot": "bot",
       "law": "scale", "rule": "scale", "reality": "box", "limit": "octagon-x", "infinite": "infinity", "infinity": "infinity",
       "push": "hand", "build": "hammer", "city": "building-2", "home": "house", "house": "house", "car": "car", "phone": "smartphone",
       "music": "music", "sound": "volume-2", "water": "droplet", "fire": "flame", "food": "utensils", "book": "book-open", "learn": "graduation-cap",
       "school": "school", "science": "flask-conical", "chemistry": "flask-conical", "experiment": "flask-conical", "question": "circle-help",
       "yes": "circle-check", "no": "circle-x", "clock": "clock", "travel": "plane", "journey": "route", "map": "map", "chart": "chart-column"}


def find_icon(concept):
    """Lucide shape name for a concept: synonym → exact name → tag/name score. None when nothing really fits."""
    ic = icons()
    keys = _keys(concept)
    for k in keys:
        if SYN.get(k) in ic:
            return SYN[k]
    for k in keys:
        if k in ic:
            return k
    joined = "-".join(keys)
    if joined in ic:
        return joined
    best = None
    for name, e in ic.items():
        tags = [_norm(t) for t in e.get("t") or []]
        hit = sum(2 for k in keys if k in tags) + sum(1 for k in keys if k in name.split("-"))
        if not hit:
            continue
        score = hit - (1.5 if re.search(r"-(off|x|minus|slash|dot|fill|2|plus|check|question)$", name) else 0) - 0.02 * name.count("-")
        if score > 0 and (best is None or score > best[0]):
            best = (score, name)
    return best[1] if best else None


def make_art(style, concept, label, p=None):
    """Generate a hero cut-out on demand (Qwen-Image + BiRefNet, ~1 min warm). Returns the concept id or None."""
    if not ART_PY or not os.path.isfile(ART_PY):
        return None
    cid = re.sub(r"[^a-z0-9]+", "_", str(concept).lower()).strip("_")[:40]
    tags = ",".join(dict.fromkeys(_keys(concept) + _keys(label)))
    try:
        pr = subprocess.Popen([ART_PY, "-I", os.path.join(ENGINE, "mg_assets", "build_art.py"), "--style", style, "--concept", concept, "--tags", tags],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                              cwd=os.path.join(ENGINE, "mg_assets"))
        t0 = time.time()
        while pr.poll() is None:
            if (p is not None and _STOP.get(p["id"])) or time.time() - t0 > 900:
                pr.kill()
                if p is not None:
                    check(p)
                return None
            time.sleep(1)
        if pr.returncode == 0 and os.path.isfile(os.path.join(MG, "art", style, cid + ".png")):
            _CACHE.pop("art", None)
            return cid
    except Stopped:
        raise
    except Exception:
        pass
    return None


def resolve_visual(p, v, want_art):
    """Fill v.kind/id for the project's style: art → (generate art) → vec → icon → text. Also what the picture DOES (v.motion)."""
    style = p.get("style") or "signature"
    if not v.get("motion"):
        v["motion"] = motion_for(v.get("concept") or v.get("label"))
    if v.get("pick"):                               # the person picked a specific asset in the Assets step
        kind, _, vid = v["pick"].partition(":")
        v.update(kind=kind, id=vid)
        return
    cid = find_art(style, v.get("concept"))
    if cid:
        v.update(kind="art", id=cid)
        return
    lid = motion_library.match(v.get("concept") or v.get("label"))      # an animal / character / object that MOVES beats a still icon
    if lid:
        v.update(kind="dio", id=lid)
        return
    if want_art == "all":
        cid = make_art(style, v.get("concept"), v.get("label"), p)
        if cid:
            v.update(kind="art", id=cid)
            return
    name = find_icon(v.get("concept")) or find_icon(v.get("label"))
    if name:
        v.update(kind="vec", id=name)
        return
    v.update(kind="text", id="", text=v.get("label") or v.get("concept"))


CAST_SYS = """You read the narration of an animated film and cast it. List the people in it (never the protagonist / "you"): the
named ones AND anyone unnamed who is part of a moment (a little kid at the crossing -> id "kid", gender "child"; a driver, a
stranger), each with a fixed distinct look, and for every numbered line say which of them are ON SCREEN (up to 3: anyone part
of the moment) and who speaks (if the line quotes or describes them talking - counting out loud, shouting, whispering). Look fields: gender man|woman|child, skin
light|medium|tan|deep, hair short|long|bun|curly|bald|ponytail, color graphite|steel|silver|bronze|champagne|gold|charcoal,
outfit blazer|suit|dress|labcoat|apron|hoodie|sweater, age young|adult|older, glasses, beard.
Reply JSON: {"cast": [{"id": "dana", "name": "Dana", "role": "...", "look": {...}}], "lines": [{"n": 1, "with": ["dana"], "talker": ""}]}"""


def cast_backfill(p, ask, extend=False):
    """A diorama film written before the cast existed: cast it from its own lines (one call), keep every line and take.
    extend=True: keep the existing cast exactly (ids, names, looks) and only add the people it missed."""
    beats = [b for b in p["beats"] if b["kind"] == "diorama"]
    if not beats or not ask or (p.get("dio_cast") is not None and not extend):
        return
    p["stage_note"] = "casting the characters"
    save(p)
    keep = (p.get("dio_cast") or []) if extend else []
    head = ("EXISTING CAST - keep these ids, names and looks exactly; add anyone missing:\n%s\n\n" % json.dumps(keep, ensure_ascii=False)) if keep else ""
    j = _ask_json(head + "\n".join("%d. %s" % (i + 1, b["line"]) for i, b in enumerate(beats)), CAST_SYS, ask)
    new = dio_cast(j.get("cast"))
    ids0 = {c["id"] for c in keep}
    p["dio_cast"] = keep + [c for c in new if c["id"] not in ids0] if keep else new
    ids = {c["id"] for c in p["dio_cast"]}
    for r in j.get("lines") or []:
        try:
            b = beats[int(r.get("n")) - 1]
        except (TypeError, ValueError, IndexError):
            continue
        w_ = [re.sub(r"[^a-z0-9_]", "", str(x).lower()) for x in (r.get("with") or []) if isinstance(x, str)]
        b["with"] = [x for x in w_ if x in ids][:3]
        tk = re.sub(r"[^a-z0-9_]", "", str(r.get("talker") or "").lower())
        if tk in ids:
            b["talker"] = tk
    log(p, "cast · " + ", ".join(c["name"] for c in p["dio_cast"]), "done")


def dio_icon(pn):
    name = find_icon(pn.get("icon")) or find_icon(pn.get("label")) or "sparkles"
    pn.update(iconId=name, kind="icon")


def step_assets(p, hk, sid=""):
    p["stage"] = "assets"
    if p.get("format") == "diorama":
        try:
            cast_backfill(p, hk.get("ask"))
        except Exception as e:
            log(p, "couldn't cast the characters: %s" % str(e)[:120], "warn")
            p["dio_cast"] = []
        if p.get("mint", True):                  # MINT: lines whose action / object / animal the library can't show get new ones designed
            mint_step(p, hk.get("ask"))
        n = 0
        for b in p["beats"]:
            if isinstance(b.get("panel"), dict):
                dio_icon(b["panel"])
                n += 1
            b["status"] = "ready"
        log(p, "info panels ready · %d icons" % n, "done")
        p["stage_note"] = ""
        save(p)
        return
    want = p.get("art") or "library"              # library = existing cut-outs only · all = generate missing hero art
    beats = p["beats"]
    tot = sum(len(b.get("visuals") or []) + len([it for it in b.get("items") or [] if it.get("visual") or it.get("concept")]) for b in beats)
    k = 0
    for i, b in enumerate(beats):
        for v in b.get("visuals") or []:
            k += 1
            check(p)
            p["stage_note"] = "picture %d/%d · %s" % (k, tot, v.get("concept") or "")
            save(p)
            resolve_visual(p, v, want)
        for it in b.get("items") or []:
            if it.get("concept"):
                check(p)
                k += 1
                vv = {"concept": it["concept"], "label": it.get("text"), "pick": it.get("pick")}
                resolve_visual(p, vv, want)
                it["visual"] = {"kind": vv["kind"], "id": vv["id"], "text": vv.get("text")}
        b["status"] = "ready"
        save(p)
    kinds = {}
    for b in beats:
        for v in b.get("visuals") or []:
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    log(p, "pictures ready · " + ", ".join("%d %s" % (n, {"art": "AI cut-outs", "vec": "styled vectors", "icon": "icons", "text": "words"}.get(k, k)) for k, n in kinds.items()), "done")
    p["stage_note"] = ""


# ── render ─────────────────────────────────────────────────────────────────────────────────────────────────
ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}


def _visual_props(v, style=None):
    out = {"kind": v.get("kind") or "text", "id": v.get("id") or "", "label": v.get("label") or "", "at": float(v.get("at") or 0), "motion": v.get("motion") or motion_for(v.get("concept") or v.get("label"))}
    if out["kind"] == "art" and not os.path.isfile(os.path.join(MG, "art", style or "signature", out["id"] + ".png")):
        out["kind"], out["id"] = "vec", find_icon(v.get("concept") or out["id"]) or "sparkles"     # a missing cut-out would stall the render
    if out["kind"] == "icon":
        out["nodes"] = (icons().get(out["id"]) or {}).get("n") or []
    if out["kind"] == "text":
        out["text"] = v.get("text") or v.get("label") or v.get("concept") or ""
    if out["kind"] == "lib":                         # a picture from the person's own Media Lab library
        out["src"] = "lib:" + out["id"]
    if out["kind"] == "dio":                         # a moving item from the shared motion library (places need their kit)
        it = motion_library.item(out["id"])
        if not it:
            out.update(kind="text", text=v.get("label") or v.get("concept") or "")
        elif it.get("type") == "place":
            out["item"] = it
    return out


def mint_step(p, ask, force=False):
    """The MINT pass (motion_mint.py): audit every changed line against the library, design what is missing, put it on the lines."""
    p["stage_note"] = "minting new motions for the narration"
    save(p)
    try:
        r = motion_mint.audit(p, ask, lambda m, l="info": log(p, m, l), force=force)
        if r["checked"]:
            log(p, "mint · %d lines checked · %d re-matched from the library · %d new assets designed" % (r["checked"], r["fixed"], r["minted"]), "done")
    except Exception as e:
        log(p, "mint skipped: %s" % str(e)[:120], "warn")
    p["stage_note"] = ""
    save(p)


def build_dio_project(p, sid=""):
    w, h = ASPECTS.get(p.get("aspect") or "16:9", ASPECTS["16:9"])
    retime(p)
    direct_all(p)                       # lines edited by hand get the narration pass too
    motion_mint.reapply(p)             # ...then the minted movements / animals go back on their lines
    beats = [b for b in p["beats"] if b["kind"] != "endcard"]
    ends = [b for b in p["beats"] if b["kind"] == "endcard"]
    scene, audio, t = [], [], 0.0
    if p.get("intro", True):
        scene.append(remotion.scene("mg-intro", INTRO_DUR, {"style": "signature", "accent": "", "title": p.get("title") or ""}, start=0))
        t = INTRO_DUR
    total = float(beats[-1].get("t1") or 3) if beats else 3.0
    dbeats = []
    for b in beats:
        d = {"t0": b.get("t0", 0), "t1": b.get("t1", 1), "place": b.get("place") or "apartment", "station": b.get("station") or "center", "pose": b.get("pose") or "explain",
             "mood": b.get("mood") or "neutral", "camera": b.get("camera") or "medium"}
        for k in ("fx", "rings", "sfx"):
            if b.get(k):
                d[k] = b[k]
        cids = {c["id"] for c in p.get("dio_cast") or []}
        if b.get("with"):
            d["with"] = [x for x in b["with"] if x in cids]
        if b.get("talker") in cids:
            d["talker"] = b["talker"]
        for k in ("remote", "acts", "animals", "extras", "amb", "flash", "at", "vfx"):
            if b.get(k):
                d[k] = [r for r in b[k] if r.get("id") in cids] if k == "remote" else b[k]
        if b.get("cue_t") is not None:
            d["cue"] = b["cue_t"]
        pn = b.get("panel")
        if isinstance(pn, dict):
            if not pn.get("iconId"):
                dio_icon(pn)
            d["panel"] = {"label": pn.get("label") or "", "value": pn.get("value") or "", "nodes": (icons().get(pn.get("iconId") or "") or {}).get("n") or []}
        dbeats.append(d)
    words = [w for b in beats for w in b.get("words") or []]
    scene.append(remotion.scene("mg-diorama", round(total + .3, 2), {"beats": dbeats, "words": words, "captions": p.get("captions", True), "kits": motion_kits.for_project(MG, dbeats), "world": p.get("dio_world") or "city", "hero": p.get("dio_hero") or {},
                                                                      "mint": motion_mint.bundle(p), "scenery": motion_mint.scenery(p),
                                                                      "cast": [{"id": c["id"], "name": c["name"], "look": c["look"]} for c in p.get("dio_cast") or []]}, start=t))
    vol = float(p.get("vo_volume") or 1.4)
    for tk in p.get("takes") or []:
        audio.append(remotion.scene("audio", round(tk["dur"] + .1, 2), {"src": "lib:" + tk["vo"], "volume": vol}, start=t + float(tk.get("at") or 0)))
    t += total + .3
    for b in ends:
        scene.append(remotion.scene("mg-endcard", b.get("dur") or 6, {"style": "signature", "accent": "", "n": 0, "captions": p.get("captions", True), "brand": p.get("brand") or "MIR",
                                    "words": b.get("words") or [], "title": b.get("title") or "Thanks for watching", "line1": b.get("line1") or "Like · Subscribe",
                                    "line2": b.get("line2") or "Download the MIR MEDIA LABS app"}, start=t))
        if b.get("vo"):
            audio.append(remotion.scene("audio", min(b["dur"], (b.get("vo_dur") or b["dur"]) + .3), {"src": "lib:" + b["vo"], "volume": vol}, start=t + .35))
        t += b.get("dur") or 6
    tracks = [{"kind": "scene", "name": "Story", "clips": scene}, {"kind": "audio", "name": "Voice", "clips": audio}]
    if not p.get("music") and p.get("score", "on") != "off" and p.get("score_lib"):
        tracks.append({"kind": "audio", "name": "Score", "clips": [remotion.scene("audio", round(t, 2), {"src": "lib:" + p["score_lib"], "volume": float(p.get("score_volume") or 1.0)}, start=0)]})
    if p.get("music"):
        tracks.append({"kind": "audio", "name": "Music", "clips": [remotion.scene("audio", t, {"src": p["music"], "volume": float(p.get("music_volume") or 0.16), "fadeIn": 1.0})]})
    pj = remotion.project(p.get("title") or "Diorama", w, h, 30, tracks, palette={"bg": "#0B0B0D", "fg": "#F2F6FA", "acc": "#FFB547", "acc2": "#D8DCE2"}, font="", session=sid)
    pj["style"], pj["accent"], pj["_starts"] = "signature", "", [round((INTRO_DUR if p.get("intro", True) else 0) + float(b.get("t0") or 0), 2) for b in beats]
    return pj


def build_project(p, sid=""):
    if p.get("format") == "diorama":
        return build_dio_project(p, sid)
    w, h = ASPECTS.get(p.get("aspect") or "16:9", ASPECTS["16:9"])
    st = styles().get(p.get("style") or "signature") or {}
    pal = st.get("palette") or {}
    retime(p)
    scene, audio, t = [], [], 0.0
    if p.get("intro", True):                       # MIR MEDIA LABS intro sting in the video's style (user rule)
        scene.append(remotion.scene("mg-intro", INTRO_DUR, {"style": p.get("style") or "signature", "accent": p.get("accent") or "", "title": p.get("title") or ""}, start=0))
        t = INTRO_DUR
    starts = []
    if not p["beats"] or p["beats"][-1]["kind"] != "endcard":      # every video ends on the like/subscribe + GitHub card
        p["beats"].append(_beat(len(p["beats"]), {"kind": "endcard", "line": "Thanks for watching. Like and subscribe, and download the MIR MEDIA LABS app.", "visuals": []}))
        retime(p)
    def beat_props(i, b):
        props = {"style": p.get("style") or "signature", "accent": p.get("accent") or "", "n": i, "captions": p.get("captions", True),
                 "brand": p.get("brand") or "MIR", "words": b.get("words") or [], "visuals": [_visual_props(v, p.get("style")) for v in b.get("visuals") or []]}
        for k in ("kicker", "title", "sub", "value", "prefix", "suffix", "label", "headline", "link", "a", "aval", "b", "bval", "text", "by", "line1", "line2",
                  "action", "who", "figure", "figure2", "set", "mood", "overlay", "fx", "fxAt", "plate", "plate_dur"):
            if b.get(k) not in (None, ""):
                props[k] = b[k]
        if b.get("frame"):
            props["shot"] = b["frame"]                   # camera framing (wide/medium/close/xclose) for the scene
        castmap = {c["id"]: c for c in p.get("cast") or []}
        if b.get("actor") in castmap:                    # the on-screen character wears the cast member's look (a beat's own figure wins)
            props["figure"] = {**castmap[b["actor"]].get("look", {}), **(b.get("figure") or {})}
        if b["kind"] == "action":
            props["at"] = 0.1
        if b["kind"] == "list":
            props["items"] = [{"text": it.get("text"), "at": it.get("at"), "visual": _visual_props(it["visual"], p.get("style")) if it.get("visual") else None} for it in b.get("items") or []]
        if b["kind"] == "stat":
            try:
                props["value"] = float(str(b.get("value") or 0).replace(",", ""))
            except ValueError:
                props["value"] = 0
        return props

    if not any("cut" in b for b in p["beats"]):          # projects from before continuous shots: infer the cuts
        shots_from_writer(p["beats"])
    idx = {id(b): i for i, b in enumerate(p["beats"])}
    for g in shot_groups(p["beats"], p.get("continuous", True)):
        g0 = t
        if len(g) == 1:
            b = g[0]
            scene.append(remotion.scene("mg-" + b["kind"], b["dur"], beat_props(idx[id(b)], b), start=t))
        else:                                              # one continuous camera move across these beats
            sb = []
            for b in g:
                bp = beat_props(idx[id(b)], b)
                bp.update(kind=b["kind"], dur=b["dur"], mark=b.get("mark") or "")
                for k in ("style", "accent", "captions", "brand", "n"):
                    bp.pop(k, None)
                sb.append(bp)
            move = g[0].get("move") or "pan"
            scene.append(remotion.scene("mg-shot", round(sum(b["dur"] for b in g), 3), {"style": p.get("style") or "signature", "accent": p.get("accent") or "",
                                        "n": idx[id(g[0])], "captions": p.get("captions", True), "brand": p.get("brand") or "MIR", "move": move, "beats": sb}, start=g0))
        for b in g:
            starts.append(round(t, 2))
            if b.get("vo"):
                audio.append(remotion.scene("audio", min(b["dur"], (b.get("vo_dur") or b["dur"]) + 0.3), {"src": "lib:" + b["vo"], "volume": float(p.get("vo_volume") or 1.4)}, start=t + 0.35))
            t += b["dur"]
    tracks = [{"kind": "scene", "name": "Beats", "clips": scene}, {"kind": "audio", "name": "Voice", "clips": audio}]
    if p.get("music"):
        tracks.append({"kind": "audio", "name": "Music", "clips": [remotion.scene("audio", t, {"src": p["music"], "volume": float(p.get("music_volume") or 0.16), "fadeIn": 1.0})]})
    pj = remotion.project(p.get("title") or "Motion graphics", w, h, 30, tracks, palette={"bg": pal.get("bg", "#08080A"), "fg": pal.get("ink", "#F2F6FA"), "acc": pal.get("acc", "#FFB547"), "acc2": pal.get("acc2", "#E6EBF0")},
                          font="", session=sid)
    pj["style"] = p.get("style") or "signature"
    pj["accent"] = p.get("accent") or ""
    pj["_starts"] = starts
    return pj


INTRO_DUR = 3.4


def step_render(p, hk, sid=""):
    if p.get("format") == "diorama":
        step_score(p, hk, sid)                               # timing may have changed since the last mix (cached cues: seconds)
    p["stage"] = "render"
    for b in p["beats"]:                                     # a picture added after the Pictures step still gets a look
        for v in b.get("visuals") or []:
            if not v.get("kind"):
                resolve_visual(p, v, "library")
    check(p)
    pj = build_project(p, sid)
    pj.pop("_starts", None)
    if p.get("project"):
        pj["id"] = p["project"]
    p["project"] = remotion.save_project(p["user"], pj)
    pj["id"] = p["project"]
    p["stage_note"] = "rendering"
    log(p, "rendering %d beats · %s" % (len(p["beats"]), p.get("style")))
    save(p)
    mj = remotion.start_job(remotion.clean(pj), p["user"], sid, "mp4", 19, "motion-graphics", prefix="mg")
    p["render"] = {"job": mj["id"], "pct": 0}
    while mj.get("status") == "running":
        if _STOP.get(p["id"]):
            mj["status"] = "cancelled"                       # remotion.render() sees this and cancels the daemon job
            raise Stopped()
        p["render"]["pct"] = mj.get("pct") or 0
        p["stage_note"] = "rendering · %s" % (mj.get("stage") or "")
        save(p)
        time.sleep(1.5)
    if mj.get("status") == "cancelled":
        raise Stopped()
    if mj.get("status") != "done":
        raise RuntimeError(mj.get("error") or "render %s" % mj.get("status"))
    p["render"] = {"job": mj["id"], "pct": 100, "src": mj["src"], "url": mj["url"], "secs": mj.get("dur")}
    if OUT_DIR:                                              # optional export folder (mml_config / Settings)
      try:
          os.makedirs(OUT_DIR, exist_ok=True)
          import unicodedata
          plain = unicodedata.normalize("NFKD", p.get("title") or "motion").encode("ascii", "ignore").decode()
          slug = re.sub(r"[^A-Za-z0-9]+", "_", plain).strip("_")[:60] or "motion"
          dst = os.path.join(OUT_DIR, "%s_%s_%s.mp4" % (slug, p.get("style"), time.strftime("%Y%m%d_%H%M")))
          shutil.copy2(os.path.join(core.LIB, mj["src"].split(":", 1)[-1]), dst)
          p["render"]["copy"] = dst
      except Exception as e:
          log(p, "couldn't copy to the export folder: %s" % e, "warn")
    p["stage_note"] = ""
    log(p, "final cut ready", "done")
    p.update(state="waiting", wait="final")


# ── Social ──
def story_for_social(p):
    """What VIRAL needs to title and describe the video: what it is ABOUT (not 3 sampled frames) and how it was made."""
    beats = [b for b in p.get("beats") or [] if b.get("kind") != "endcard" and b.get("line")]
    said = " ".join(str(b["line"]).strip() for b in beats)
    if len(said) > 7000:                                      # long films: the opening, the turn and the ending survive
        said = said[:4200] + " [...] " + said[-2600:]
    ol = p.get("outline") or {}
    fmt = p.get("format") or "explainer"
    if fmt == "diorama":
        made = ("Animated in MIR MOTION (MIR MEDIA LABS' own animation engine) as a Diorama: a tiny isometric night city in "
                "charcoal, brushed metal and gold, with one character acting out the story. The animation is drawn by the engine, "
                "NOT AI video. The narration voice and the music score are AI-generated.")
        kind = "a narrated animated short film"
    else:
        ai = (p.get("ai_scenes") or ("key" if fmt == "story" else "off")) == "key"
        made = "Motion graphics animated in MIR MOTION (MIR MEDIA LABS). AI narration." + (" Some key scenes are AI-generated video." if ai else "")
        kind = "a narrated animated what-if story" if fmt == "story" else "a narrated motion-graphics explainer"
    out = {"title": p.get("title") or "", "premise": str(p.get("brief") or "")[:600], "kind": kind, "made_with": made, "narration": said}
    if ol.get("logline"):
        out["logline"] = ol["logline"]
    if ol.get("chapters"):
        out["chapters"] = ["%s: %s" % (c.get("title"), c.get("summary")) for c in ol["chapters"]][:14]
    if p.get("dio_cast"):
        out["cast"] = ["%s (%s)" % (c["name"], c.get("role") or "") for c in p["dio_cast"]]
    secs = (p.get("render") or {}).get("secs") or (beats[-1].get("t1") if beats else None)
    if secs:
        out["length"] = "%d:%02d" % divmod(int(float(secs)), 60)
    out["intro_secs"] = INTRO_DUR if p.get("intro", True) else 0     # VIRAL samples frames after our intro sting, not of it
    return out


def make_draft(p, platforms=None):
    """A Social draft of this video's latest render (approve-only in Social, as always). captions="none": the motion video
    already carries its own titles + word captions, so VIRAL must not burn a hook/caption layer on top (user, Oct 28)."""
    import social
    src = ((p.get("render") or {}).get("src") or "").split(":", 1)[-1]
    if not src:
        raise ValueError("render the video first")
    vert = p.get("aspect") == "9:16"
    plats = [x for x in (platforms or ["youtube", "instagram"]) if x in social.ALL_PLATFORMS] or ["youtube", "instagram"]
    post = social.create_draft(src, plats, brief="Motion video: %s" % (p.get("title") or p.get("brief") or "")[:300],
                               fit="crop" if vert else "keep", yt_format="short" if vert else None, captions="none", story=story_for_social(p))
    p["post"] = post["id"]
    p.setdefault("posts", []).append({"id": post["id"], "t": time.time(), "platforms": plats, "src": src})
    log(p, "Social draft made (%s) — approve it in Social to post" % ", ".join(plats), "done")
    return post


# ── workers ────────────────────────────────────────────────────────────────────────────────────────────────
def _run(uid, pid, fn):
    def go():
        with _lock(pid):
            p = load(uid, pid)
            if not p:
                return
            _STOP.pop(pid, None)
            prev = p.get("render") if (p.get("render") or {}).get("src") else None
            try:
                p["state"] = "running"
                save(p)
                fn(p)
            except Stopped:
                cp = CHECKPOINT.get(p.get("stage"), "script")
                if p.get("render") and not p["render"].get("src"):
                    p["render"] = prev                      # a cancelled re-render keeps the last finished cut
                if cp == "final" and not (p.get("render") or {}).get("src"):
                    cp = "assets"
                if cp == "script" and not p.get("beats"):
                    p.update(state="stopped", stage="script", wait="", stage_note="")
                else:
                    p.update(state="waiting", stage=cp, wait=cp, stage_note="")
                log(p, "stopped by you — everything done so far is kept; edit and continue whenever you like", "need")
            except Exception as e:
                p.update(state="error", error=str(e)[:400])
                log(p, "stopped: %s" % e, "error")
            _STOP.pop(pid, None)
            try:
                save(p)
            except Exception:
                time.sleep(1)
                save(p)
    threading.Thread(target=go, daemon=True, name="mg-" + pid).start()


def step_script(p, hk, sid=""):
    p["stage"] = "script"
    log(p, "writing the beats for “%s”" % p["brief"][:80])
    write_script(p, hk.get("ask"))
    check(p)                                         # stopped while the brain was writing → the draft is still kept
    retime(p)
    log(p, "%d beats ready" % len(p["beats"]), "done")
    _wait_or_go(p, "script", hk, sid)


def step_scenes(p, hk, sid=""):
    """HYBRID: AI-animated shots (cast sheet → keyframe → H3 → smoothed) for the key moments of a story (motion_scenes.py)."""
    if (p.get("ai_scenes") or ("key" if p.get("format") == "story" else "off")) == "off":
        return
    import motion_scenes
    p["stage"] = "assets"
    retime(p)
    try:
        motion_scenes.build(p, log, save, lambda: bool(_STOP.get(p["id"])), sid)
    except InterruptedError:
        raise Stopped()


def step_score(p, hk, sid=""):
    """Diorama: the music bed + soft sound effects (motion_score.py), pre-mixed into one track under the voice."""
    if p.get("format") != "diorama" or p.get("score", "on") == "off":
        return
    import motion_scenes, motion_score
    try:
        motion_score.build(p, log, save, lambda: bool(_STOP.get(p["id"])), sid, motion_scenes._run)
    except InterruptedError:
        raise Stopped()
    except Exception as e:                                  # a failed score never blocks the video
        log(p, "music skipped: %s" % str(e)[:160], "warn")
    p["stage_note"] = ""
    save(p)


def step_produce(p, hk, sid=""):
    """voice → assets (→ AI scenes for stories), then stop at the assets checkpoint (or roll on in automatic mode)."""
    step_voice(p, hk, sid)
    step_assets(p, hk, sid)
    step_scenes(p, hk, sid)
    step_score(p, hk, sid)
    _wait_or_go(p, "assets", hk, sid)


def _wait_or_go(p, stage, hk, sid):
    p["stage"] = stage
    if p.get("auto"):
        save(p)
        if stage == "script":
            return step_produce(p, hk, sid)
        if stage == "assets":
            return step_render(p, hk, sid)
    p.update(state="waiting", wait=stage)
    log(p, {"script": "check the script and the picture plan", "assets": "check the pictures"}[stage], "need")


# ── Flask ──────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, static(fn), session(sid), ask(prompt, system), words(path), is_owner(), my_file(name)."""
    from flask import jsonify, request, send_from_directory

    U = lambda: hk["uid"]()
    motion_library.register(app, hk)            # the shared motion library (/api/mglib) for Motion Studio

    try:                         # a restart kills worker threads: runs left "running" would look busy forever
        for ud in os.listdir(D) if os.path.isdir(D) else []:
            for f in os.listdir(os.path.join(D, ud)) if os.path.isdir(os.path.join(D, ud)) else []:
                if f.endswith(".json"):
                    path = os.path.join(D, ud, f)
                    with open(path, encoding="utf-8") as fh:
                        p = json.load(fh)
                    if p.get("state") == "running":
                        p.update(state="error", error="the lab restarted while this step was running — press Try again.", stage_note="")
                        log(p, "interrupted by a lab restart", "warn")
                        save(p)
    except Exception:
        pass

    @app.route("/motion")
    def mw_page():
        return hk["static"]("motion.html")

    @app.route("/mg/<path:name>")
    def mw_asset(name):
        """Style asset library (icons, AI cut-outs, styled vectors) for the page and the in-browser player."""
        return send_from_directory(MG, name, max_age=3600)

    @app.route("/api/mg/styles")
    def mw_styles():
        a = art()
        return jsonify({"styles": styles(), "art": {k: len(v) for k, v in a.items()}, "vec": len(icons()), "actions": ACTIONS, "motions": MOTIONS, "moves": MOVES,
                        "sets": SETS, "shots": SHOTS, "moods": MOODS, "overlays": OVERLAYS, "fxs": FXS, "formats": FORMATS,
                        "outfits": OUTFITS, "hairs": HAIRS, "accessories": ACCESSORIES,
                        "dio": {"look": dict(DIO_LOOK, **(motion_library.vocab().get("looks") or {})), "worlds": {k: {"name": v[0], "about": v[1]} for k, v in motion_kits.WORLDS.items()},
                                "acts": motion_library.vocab().get("acts") or {}, "species": list((motion_library.vocab().get("species") or {}).keys()), "remote": REMOTE_HOWS,
                                "animal_acts": ANIMAL_ACTS, "ambients": motion_library.vocab().get("ambients") or [], "vfx": list((motion_library.vocab().get("vfx") or {}).keys()), "places": dio_places(), "kits": motion_kits.catalog(MG), "lengths": {k: v[2] for k, v in DIO_LENGTHS.items()}, "stations": DIO_STATIONS, "poses": DIO_POSES, "moods": DIO_MOODS, "cameras": DIO_CAMS, "fx": DIO_FX, "rings": DIO_RINGS}})

    @app.route("/api/mg/library")
    def mw_library():
        """Browse one style's pictures: AI cut-outs + styled vectors matching a query."""
        st = request.args.get("style") or "signature"
        q = _norm(request.args.get("q") or "")
        a = art().get(st) or {}
        out = [{"kind": "art", "id": cid, "tags": e.get("tags") or [], "thumb": "mg/art/%s/%s.webp" % (st, cid)} for cid, e in a.items()
               if not q or q in _norm(cid) or any(q in _norm(t) for t in e.get("tags") or [])]
        n = 0
        for name, e in icons().items():
            if n >= 120:
                break
            if not q or q in name.replace("-", "") or any(q in _norm(t) for t in e.get("t") or []):
                out.append({"kind": "vec", "id": name, "tags": e.get("t") or [], "thumb": "mg/vec/%s/%s.svg" % (st, name)})
                n += 1
        return jsonify({"items": out[:200]})

    @app.route("/api/mg/media")
    def mw_media():
        """The person's own library pictures / audio (for picture swaps and the music bed)."""
        kind = request.args.get("kind") or "image"
        q = _norm(request.args.get("q") or "")
        items = [m for m in (hk["lib_list"]() if hk.get("lib_list") else []) if m.get("kind") == kind and (not q or q in _norm(m["name"] + " " + (m.get("prompt") or "")))]
        return jsonify({"items": [{"name": m["name"], "prompt": (m.get("prompt") or "")[:120]} for m in items[:120]]})

    @app.route("/api/mg/<pid>/project")
    def mw_project(pid):
        """The MIR MOTION project as it would render now — for the page's live preview player."""
        p = load(U(), pid)
        if not p or not p.get("beats"):
            return jsonify({"error": "nothing to preview yet"}), 404
        q = json.loads(json.dumps(p))
        for b in q["beats"]:
            for v in b.get("visuals") or []:
                if not v.get("kind"):
                    resolve_visual(q, v, "library")
        pj = build_project(q)
        starts = pj.pop("_starts", [])
        return jsonify({"project": pj, "starts": starts, "dur": round(remotion.duration(pj), 2), "intro": INTRO_DUR if q.get("intro", True) else 0})

    @app.route("/api/mg/runs")
    def mw_runs():
        return jsonify({"runs": listing(U())})

    @app.route("/api/mg/start", methods=["POST"])
    def mw_new():
        b = request.get_json(silent=True) or {}
        brief = str(b.get("brief") or "").strip()[:1500]
        if not brief:
            return jsonify({"error": "say what the video is about"}), 400
        st = b.get("style") if b.get("style") in styles() else "signature"
        pid = uuid.uuid4().hex[:12]
        p = {"id": pid, "user": U(), "brief": brief, "title": "", "style": st, "accent": str(b.get("accent") or "")[:9],
             "aspect": b.get("aspect") if b.get("aspect") in ASPECTS else "16:9", "length": b.get("length") if b.get("length") in LENGTHS else "medium",
             "voice": b.get("voice") or motion_util.DEF_VOICE, "captions": bool(b.get("captions", True)), "art": b.get("art") if b.get("art") in ("library", "all") else "library",
             "music": "", "brand": str(b.get("brand") or "MIR")[:24], "tone": str(b.get("tone") or "")[:80], "audience": str(b.get("audience") or "")[:80],
             "auto": bool(b.get("auto")), "state": "running", "stage": "script", "beats": [], "created": time.time(), "log": [],
             "format": b.get("format") if b.get("format") in FORMATS else "explainer",
             "voice_engine": b.get("voice_engine") if b.get("voice_engine") in VOICE_ENGINES else "chatterbox",
             "voice_intensity": b.get("voice_intensity") if b.get("voice_intensity") in INTENSITIES else "dramatic",
             "world": b.get("world") if b.get("world") in motion_kits.WORLDS else "auto"}
        p["session"] = new_session(U(), brief.split("\n")[0])      # its own chat + library shelf in Media Lab
        save(p)
        sid = p["session"] or hk["session"](b.get("session")) or ""
        _run(U(), pid, lambda p: step_script(p, hk, sid))
        return jsonify(dict(p, progress=progress(p)))

    @app.route("/api/mg/<pid>")
    def mw_get(pid):
        p = load(U(), pid)
        return jsonify(dict(p, progress=progress(p))) if p else (jsonify({"error": "no such project"}), 404)

    @app.route("/api/mg/<pid>/scene/<fname>")
    def mw_scene_file(pid, fname):
        """A cast sheet / keyframe of this video's AI scenes (shown on the progress view as they appear)."""
        p = load(U(), pid)
        d = os.path.join(core.DATA, "motion_wizard", "scenes", str(pid))
        fname = os.path.basename(fname)
        if not p or not re.match(r"^[\w.-]+\.(png|jpg|webp)$", fname) or not os.path.isfile(os.path.join(d, fname)):
            return jsonify({"error": "not found"}), 404
        from flask import send_from_directory
        return send_from_directory(d, fname, max_age=3600)

    @app.route("/api/mg/<pid>/<action>", methods=["POST"])
    def mw_act(pid, action):
        uid = U()
        p = load(uid, pid)
        if not p:
            return jsonify({"error": "no such project"}), 404
        b = request.get_json(silent=True) or {}
        if action == "stop":
            if p.get("state") != "running":
                return jsonify(p)
            _STOP[pid] = True
            for j in remotion.JOBS.values():                   # a render in flight is cancelled right away
                if j.get("id") == (p.get("render") or {}).get("job") and j.get("status") == "running":
                    j["status"] = "cancelled"
            p["stage_note"] = "stopping…"
            log(p, "stop requested", "warn")
            return jsonify(p)
        if p.get("state") == "running" and action != "delete":
            return jsonify({"error": "still working — press Stop first, then edit"}), 409
        if action == "session":                    # give an older video its own session and move its media there
            if not hk["session"](p.get("session")):
                p["session"] = new_session(uid, p.get("title") or p.get("brief") or "")
                p.pop("_sess_named", None)
            names = [b_.get("vo") for b_ in p.get("beats") or []] + [(b_.get("plate") or "").split(":", 1)[-1] for b_ in p.get("beats") or []]
            names += [os.path.basename(str((p.get("render") or {}).get("src") or "").split("?")[0])]
            idx, n = core.index(), 0
            for nm in names:
                if nm and nm in idx and isinstance(idx[nm], dict):
                    core.index_add(nm, dict(idx[nm], session=p["session"]))
                    n += 1
            save(p)
            return jsonify(dict(load(uid, pid), moved=n, progress=progress(p)))
        sid = hk["session"](p.get("session")) or hk["session"](b.get("session")) or ""

        def edits(p):
            for k in ("title", "accent", "voice", "brand", "music", "tone", "audience"):
                if k in b:
                    p[k] = str(b[k])[:120]
            if "brief" in b:
                p["brief"] = str(b["brief"])[:1500]
            if b.get("length") in LENGTHS:
                p["length"] = b["length"]
            if "auto" in b:
                p["auto"] = bool(b["auto"])
            if "vo_volume" in b:
                p["vo_volume"] = motion_util._f(b["vo_volume"], 1.4, 0, 3)
            if b.get("style") in styles():
                p["style"] = b["style"]
            if b.get("aspect") in ASPECTS:
                p["aspect"] = b["aspect"]
            if "captions" in b:
                p["captions"] = bool(b["captions"])
            if "intro" in b:
                p["intro"] = bool(b["intro"])
            if "continuous" in b:
                p["continuous"] = bool(b["continuous"])
            if b.get("format") in FORMATS:
                p["format"] = b["format"]
            old = (p.get("voice_engine") or "chatterbox", p.get("voice_intensity") or "dramatic")
            if isinstance(b.get("dio_cast"), list):
                p["dio_cast"] = dio_cast(b["dio_cast"])
            if isinstance(b.get("dio_hero"), dict):
                p["dio_hero"] = dio_hero(b["dio_hero"], p.get("dio_world") or "city")
            if b.get("world") in motion_kits.WORLDS and b.get("world") != p.get("dio_world"):
                p["world"] = p["dio_world"] = b["world"]        # a new world: the next script pass re-scouts its places
                p.pop("dio_kits", None)
            if b.get("score") in ("on", "off"):
                p["score"] = b["score"]
            if "score_sfx" in b:
                p["score_sfx"] = bool(b["score_sfx"])
                p.pop("score_sig", None)
            if "score_volume" in b:
                p["score_volume"] = motion_util._f(b["score_volume"], 1.0, 0, 2.5)
            if b.get("voice_engine") in VOICE_ENGINES:
                p["voice_engine"] = b["voice_engine"]
            if b.get("voice_intensity") in INTENSITIES:
                p["voice_intensity"] = b["voice_intensity"]
            if (p.get("voice_engine") or "chatterbox", p.get("voice_intensity") or "dramatic") != old:
                for bt in p.get("beats") or []:                 # new acting → every line counts as changed (re-recorded on Continue)
                    bt.pop("vo_line", None)
            if b.get("ai_scenes") in ("off", "key"):
                p["ai_scenes"] = b["ai_scenes"]
            if isinstance(b.get("cast"), list):                # cast editor: names, voices, looks
                import tts
                p["cast"] = [{"id": re.sub(r"[^a-z0-9_]", "", str(c.get("id") or "").lower())[:16] or "c%d" % k, "name": str(c.get("name") or "")[:30],
                              "voice": c.get("voice") if c.get("voice") in tts.VOICES else "", "look": _figure(c.get("look"))}
                             for k, c in enumerate(b["cast"][:6]) if isinstance(c, dict)]
            if b.get("art") in ("library", "all"):
                p["art"] = b["art"]
            if "music_volume" in b:
                p["music_volume"] = motion_util._f(b["music_volume"], 0.16, 0, 1)
            if isinstance(b.get("beats"), list):              # edited beat list (script step): lines, kinds, fields, visuals
                incoming = [x for x in b["beats"][:220] if isinstance(x, dict) and x.get("line")]   # was [:40] — it cut 80-line films in half
                if len(incoming) < len(p["beats"]) - 3 and not b.get("shrink_ok"):
                    return jsonify({"error": "that save would delete %d lines at once - reload the page and try again" % (len(p["beats"]) - len(incoming))}), 409
                p["beats"] = [_beat(i, x) for i, x in enumerate(incoming)]
                for nb, ob in zip(p["beats"], b["beats"]):   # keep takes whose line didn't change
                    for k in ("vo", "vo_dur", "vo_line", "words", "vo_voice", "vo_sig", "plate", "plate_sig", "plate_auto", "plate_dur", "keyframe"):
                        if ob.get(k) is not None:
                            nb[k] = ob[k]
                    for nv, ov in zip(nb["visuals"], ob.get("visuals") or []):
                        for k in ("kind", "id", "pick", "at"):
                            if isinstance(ov, dict) and ov.get(k) is not None:
                                nv[k] = ov[k]
                retime(p)
            for e in b.get("visual") and [b["visual"]] or []:
                # one picture edited in the Pictures step: {beat, i, pick?, label?, concept?, cue?, at?(null = follow the word),
                # remove?} — i = len(visuals) with add:true appends a new one
                try:
                    bt = p["beats"][int(e["beat"])]
                    vs = bt.setdefault("visuals", [])
                    i = int(e.get("i", len(vs)))
                    if e.get("add") and len(vs) < 4:
                        vs.append({"concept": str(e.get("concept") or "star")[:60], "label": str(e.get("label") or "")[:30], "cue": str(e.get("cue") or "")[:30]})
                        resolve_visual(p, vs[-1], "library")
                    elif e.get("remove"):
                        vs.pop(i)
                    else:
                        v = vs[i]
                        for k, n in (("label", 30), ("concept", 60), ("cue", 30)):
                            if k in e:
                                v[k] = str(e[k] or "")[:n]
                        if e.get("motion") in MOTIONS:
                            v["motion"] = e["motion"]
                        if "at" in e:
                            if e["at"] in (None, ""):
                                v.pop("at_manual", None)
                            else:
                                v["at_manual"] = motion_util._f(e["at"], 0, 0, 60)
                        if e.get("pick"):
                            v["pick"] = str(e["pick"])[:160]
                            resolve_visual(p, v, "library")
                        elif "concept" in e:              # new concept → find a new picture for it
                            v.pop("pick", None)
                            resolve_visual(p, v, "library")
                except (IndexError, ValueError, KeyError, TypeError):
                    pass
            for e in b.get("beat") and [b["beat"]] or []:
                # one beat edited outside the Script step: {n, pad?, line?, <kind fields>}; a changed line is re-voiced on Continue
                try:
                    bt = p["beats"][int(e["n"])]
                    if "pad" in e:
                        bt["pad"] = motion_util._f(e["pad"], 0, -2, 10)
                    if e.get("line"):
                        bt["line"] = str(e["line"])[:300]
                    for k in ("kicker", "title", "sub", "value", "prefix", "suffix", "label", "headline", "link", "a", "aval", "b", "bval", "text", "by", "line1", "line2", "who"):
                        if k in e:
                            bt[k] = e[k] if k == "value" else str(e[k] or "")[:200]
                    if bt.get("kind") == "diorama":
                        pls = dio_places()
                        if e.get("place") in pls:
                            bt["place"] = e["place"]
                            if bt.get("station") not in pls[bt["place"]]:
                                bt["station"] = "center"
                        for k, opts in (("station", pls.get(bt.get("place") or "apartment", DIO_STATIONS)), ("pose", DIO_POSES), ("mood", DIO_MOODS), ("camera", DIO_CAMS), ("fx", DIO_FX), ("rings", DIO_RINGS)):
                            if k in e:
                                if e[k] in opts:
                                    bt[k] = e[k]
                                elif e[k] in ("", None) and k in ("fx", "rings"):
                                    bt.pop(k, None)
                        if "with" in e:
                            w_ = e["with"] if isinstance(e["with"], list) else str(e["with"] or "").split(",")
                            bt["with"] = [re.sub(r"[^a-z0-9_]", "", str(x).lower())[:16] for x in w_ if str(x).strip()][:3]
                        if "talker" in e:
                            if e["talker"]:
                                bt["talker"] = re.sub(r"[^a-z0-9_]", "", str(e["talker"]).lower())[:16]
                            else:
                                bt.pop("talker", None)
                        for k, n in (("sfx", 14), ("cue", 30)):
                            if k in e:
                                if e[k]:
                                    bt[k] = str(e[k])[:n]
                                else:
                                    bt.pop(k, None)
                        if "panel" in e:
                            pe = e["panel"]
                            if isinstance(pe, dict) and (pe.get("label") or pe.get("value")):
                                np_ = {"label": str(pe.get("label") or "")[:24], "value": str(pe.get("value") or "")[:12], "icon": str(pe.get("icon") or pe.get("label") or "")[:30]}
                                dio_icon(np_)
                                bt["panel"] = np_
                            else:
                                bt.pop("panel", None)
                        e = {k: v for k, v in e.items() if k not in ("mood", "fx")}
                    for k, opts in (("set", SETS), ("frame", SHOTS), ("mood", MOODS), ("fx", FXS)):
                        if k in e:
                            if e[k] in opts:
                                bt[k] = e[k]
                            elif e[k] in ("", None):
                                bt.pop(k, None)
                    if "key" in e:
                        bt["key"] = bool(e["key"])
                        if not e["key"]:
                            for k in ("plate", "plate_sig", "plate_auto", "plate_dur"):
                                bt.pop(k, None)
                    if "speaker" in e:
                        bt["speaker"] = re.sub(r"[^a-z0-9_]", "", str(e["speaker"] or "narrator").lower())[:16] or "narrator"
                    if "actor" in e:
                        bt["actor"] = re.sub(r"[^a-z0-9_]", "", str(e["actor"] or "").lower())[:16]
                    if "overlay" in e:
                        ov = e["overlay"]
                        if isinstance(ov, dict) and ov.get("type") in OVERLAYS:
                            bt["overlay"] = _beat(0, {"kind": "action", "line": "x", "overlay": ov}).get("overlay")
                        else:
                            bt.pop("overlay", None)
                    if "mark" in e:
                        bt["mark"] = str(e["mark"] or "")[:24]
                    if "cut" in e:
                        bt["cut"] = bool(e["cut"])
                    if e.get("move") in MOVES or e.get("move") == "":
                        bt["move"] = e["move"]
                    if e.get("action") in ACTIONS:
                        bt["action"] = e["action"]
                        if e["action"] in ("handshake", "chat") and not bt.get("figure2"):
                            bt["figure2"] = _figure({"outfit": "casual", "hair": "long"})
                    for fk in ("figure", "figure2"):
                        if isinstance(e.get(fk), dict):
                            bt[fk] = _figure({**(bt.get(fk) or {}), **e[fk]})
                except (IndexError, ValueError, KeyError, TypeError):
                    pass
            if b.get("visual") or b.get("beat"):
                retime(p)

        if action == "edit":
            with _lock(pid):
                p = load(uid, pid)
                edits(p)
                save(p)
            return jsonify(p)
        if action == "delete":                     # recoverable: the project moves to _trash/ (never erased), and never mid-production
            if p.get("state") == "running":
                return jsonify({"error": "this video is still being made - press Stop first, then delete"}), 409
            try:
                td = os.path.join(_dir(uid), "_trash")
                os.makedirs(td, exist_ok=True)
                os.replace(os.path.join(_dir(uid), pid + ".json"), os.path.join(td, "%s_%s.json" % (pid, time.strftime("%Y%m%d_%H%M%S"))))
            except OSError:
                pass
            return jsonify({"ok": True})

        edits(p)
        p["error"] = ""
        save(p)
        if action == "approve":
            w = p.get("wait") or p["stage"]
            if w == "script":
                _run(uid, pid, lambda p: step_produce(p, hk, sid))
            elif w == "assets":
                _run(uid, pid, lambda p: step_render(p, hk, sid))
            elif w == "final":
                owner = bool(hk["is_owner"]())      # resolved HERE: is_owner reads flask.g, which the worker thread has no access to
                def publish(p):
                    p["stage"] = "publish"
                    if b.get("draft") and not owner:
                        log(p, "Social drafts are owner-only — finished without one", "warn")
                    if b.get("draft") and owner:
                        try:
                            make_draft(p, b.get("platforms"))
                        except Exception as e:           # back to the final cut (not a dead end whose "Try again" re-renders)
                            p.update(stage="render", state="waiting", wait="final", error="")
                            log(p, "couldn't make the Social draft: %s — the video is safe, press Make Social draft to try again" % str(e)[:200], "error")
                            return
                    p.update(stage="done", state="done", wait="")
                    log(p, "done", "done")
                _run(uid, pid, publish)
            else:
                return jsonify({"error": "nothing to approve"}), 400
        elif action == "back":
            step = b.get("step")
            if step not in ("script", "assets"):
                return jsonify({"error": "can only go back to script or assets"}), 400
            p.update(stage=step, state="waiting", wait=step)
            log(p, "back to the %s" % step, "need")
            save(p)
        elif action == "redo":
            step = b.get("step")
            fn = {"script": lambda p: (p.update(title="", beats=[]), step_script(p, hk, sid)),
                  "voice": lambda p: step_produce(p, hk, sid),
                  "assets": lambda p: (step_assets(p, hk, sid), _wait_or_go(p, "assets", hk, sid)),
                  "render": lambda p: step_render(p, hk, sid)}.get(step)
            if not fn:
                return jsonify({"error": "unknown step"}), 400
            if step == "voice":
                for bt in p["beats"]:
                    bt.pop("vo_line", None)
            if step == "assets":
                for bt in p["beats"]:
                    for v in bt.get("visuals") or []:
                        v.pop("pick", None)
            save(p)
            _run(uid, pid, fn)
        elif action == "revoice":                  # record changed (or one chosen) lines again, keep everything else
            if b.get("n") is not None:
                try:
                    p["beats"][int(b["n"])].pop("vo_line", None)
                except (IndexError, ValueError):
                    pass
            back = p.get("wait") or "assets"
            save(p)

            def revoice(p):
                step_voice(p, hk, sid)
                for bt in p["beats"]:
                    for v in bt.get("visuals") or []:
                        if not v.get("kind"):
                            resolve_visual(p, v, "library")
                p.update(state="waiting", stage=CHECKPOINT.get(back, back) if back != "final" else "assets", wait=back if back != "final" else "assets")
                log(p, "voice updated", "done")
            _run(uid, pid, revoice)
        elif action == "gen_art":                  # make an AI cut-out for one picture in this project's style (~1 min)
            try:
                v = p["beats"][int(b["beat"])]["visuals"][int(b["i"])]
            except (IndexError, ValueError, KeyError, TypeError):
                return jsonify({"error": "no such picture"}), 404
            if b.get("concept"):
                v["concept"] = str(b["concept"])[:60]
            back = p.get("wait") or "assets"
            bi, vi = int(b["beat"]), int(b["i"])
            save(p)

            def gen(p):
                v = p["beats"][bi]["visuals"][vi]
                p["stage"] = "assets"
                p["stage_note"] = "drawing “%s” in %s style" % (v.get("concept"), p.get("style"))
                save(p)
                cid = make_art(p.get("style") or "signature", v.get("concept"), v.get("label"), p)
                if cid:
                    v["pick"] = "art:" + cid
                    resolve_visual(p, v, "library")
                    log(p, "new AI picture: %s" % cid, "done")
                else:
                    log(p, "couldn't draw that one (is ComfyUI running?) — the old picture stays", "warn")
                p.update(state="waiting", stage="assets" if back != "final" else "assets", wait="assets" if back != "final" else "final", stage_note="")
            _run(uid, pid, gen)
        elif action == "post":                     # Post button on a finished video → a fresh Social draft of its latest render
            if not hk["is_owner"]():
                return jsonify({"error": "posting to Social is owner-only"}), 403
            try:
                with _lock(pid):
                    p = load(uid, pid)
                    post = make_draft(p, b.get("platforms"))
                    save(p)
            except Exception as e:
                return jsonify({"error": str(e)[:300]}), 400
            out = load(uid, pid)
            out["new_post"] = post["id"]
            return jsonify(out)
        elif action == "mint":                    # re-run the MINT over every line (b.all) or only changed lines, then back to the pictures checkpoint
            def mint(p):
                mint_step(p, hk.get("ask"), force=bool(b.get("all")))
                p.update(state="waiting", stage="assets", wait="assets")
            _run(uid, pid, mint)
        elif action == "scenes":                   # (re)make the AI-animated key scenes, then back to the pictures checkpoint
            def scenes(p):
                step_scenes(p, hk, sid)
                p.update(state="waiting", stage="assets", wait="assets")
                log(p, "AI scenes done", "done")
            _run(uid, pid, scenes)
        elif action == "continue":                 # after a stop / crash / lab restart: pick up where it broke off
            if not p.get("beats"):
                _run(uid, pid, lambda p: step_script(p, hk, sid))
            elif p.get("stage") == "render":
                _run(uid, pid, lambda p: step_render(p, hk, sid))
            else:                                  # voice / pictures / AI scenes: finished takes, pictures and shots are kept
                _run(uid, pid, lambda p: step_produce(p, hk, sid))
        elif action == "restyle":                  # change the style of a finished / waiting project and re-resolve pictures
            if b.get("style") not in styles():
                return jsonify({"error": "unknown style"}), 400
            for bt in p["beats"]:
                for v in bt.get("visuals") or []:
                    v.pop("pick", None)
            save(p)
            _run(uid, pid, lambda p: (step_assets(p, hk, sid), _wait_or_go(p, "assets", hk, sid)))
        else:
            return jsonify({"error": "unknown action"}), 400
        return jsonify(load(uid, pid))
