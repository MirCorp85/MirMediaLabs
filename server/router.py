"""MUSE Director — the thinking layer of MIR MEDIA LABS.

People shouldn't have to know which engine does what. In Auto mode every chat message goes to MUSE (the lab's local
Llama) first; it reads the message, the attachments and the last few turns, and decides what happens:

    chat      answer it as a conversation (general knowledge, questions, advice, writing help)
    render    one render on a role's engine (image · video · song · music) with a prompt written for that engine
    skill     a one-tap preset (e.g. product, animate, lofi, lyrics)
    pipeline  several renders in a row (e.g. musicvideo, productad)

The decision is plain JSON (Ollama format=json) and is validated against the live catalog; if the model is missing,
slow or returns nonsense, a keyword router decides instead, so Auto never blocks a request. Explicit slash commands
and a manually picked engine skip the Director entirely.
"""
import json
import re
import time

import core
import skills

ROUTER_CTX = 4096
KEEP_ALIVE = "3m"          # warm for the next message; renders evict Ollama anyway
TIMEOUT = 45

RENDER_ROLES = ("image", "video", "song", "music")
ROLE_WHAT = {
    "image": "pictures: photos, art, logos, posters, thumbnails, product shots; edits of attached pictures; background removal",
    "video": "video clips 4-15 s WITH sound (no separate audio needed); animating an attached picture",
    "song": "complete songs WITH sung vocals and lyrics, up to 5 min",
    "music": "instrumentals, beats, loops, jingles; remixing or covering an attached track; swapping a voice",
}


def _catalog_text():
    out = ["ROLES (action=render):"]
    out += ["- %s: %s" % (r, ROLE_WHAT[r]) for r in RENDER_ROLES]
    out.append("SKILLS (action=skill; tuned presets — prefer one when it clearly fits):")
    for s in skills.SKILLS:
        need = ", ".join("%d attached %s" % (n, k) for k, n in skills.needs_of(s).items())
        out.append("- %s [%s]%s: %s" % (s["id"], s["role"], " (needs %s)" % need if need else "", s["desc"]))
    out.append("PIPELINES = instruction manuals (action=pipeline; several renders in a fixed order). Pick one when its"
               " WHEN matches, then write one prompt per step in \"steps\":")
    for p in skills.PIPELINES:
        need = ", ".join("%d attached %s" % (n, k) for k, n in skills.needs_of(p).items())
        out.append("- %s: %s. WHEN: %s.%s" % (p["id"], p["name"], p.get("when") or p["desc"], (" NEEDS: " + need + ".") if need else ""))
        out += ["    " + s for s in skills.manual_text(p)]
    return "\n".join(out)


SYSTEM = """You are MUSE Director, the router inside MIR MEDIA LABS, a local AI media studio. You never answer the
person yourself. You read their message and decide which tool handles it, then output ONE JSON object.

{catalog}

ACTIONS
- "chat": conversation, questions, general knowledge, advice, explanations, how-to, opinions, greetings, AND any request
  to WRITE text (lyrics, a story, a script, a poem, a caption, ideas, a plan). Text is written by MUSE in the chat.
- "render": the person wants an image, a video, a song or music MADE now. Pick the role.
- "skill": like render, but one of the SKILLS above clearly matches (e.g. "product photo of ..." -> product,
  "make this photo move" with a picture attached -> animate, "lofi beat" -> lofi, "logo for ..." -> logo).
- "pipeline": when the person's request needs several tools in a row and a PIPELINE's WHEN matches (e.g. "a music
  video for a synthwave song" -> musicvideo; a voice recording attached + "make a song about X with my voice" ->
  myvoice). Follow the manual: "steps" holds one prompt per step, in order, each written for THAT step's tool.
  For myvoice: step 1 = the full song brief (topic, genre, rhythm/BPM, mood, any lyrics the person gave);
  step 2 = only the singing style (e.g. "warm intimate lead vocal"), never the topic again.

RULES
- If in doubt between chat and making something: the person must clearly ask for a picture/video/song/beat to be MADE.
  Questions ABOUT media ("how do I write a good chorus?") are chat.
- A song WITH singing = role song. Instrumental / beat / background music = role music.
- "prompt": for render/skill/pipeline, rewrite the request as a clear, vivid description for that tool, in the
  person's language, keeping every concrete detail they gave. Copy any flags (words starting with --) and any
  lyrics exactly. Do not invent a different subject. For chat, "prompt" is the person's message unchanged.
- "use_previous": true when the person refers to the previous result ("animate it", "now make a song for that",
  "same but vertical") so it is attached as a reference; otherwise false.
- "why": at most 8 words, plain, shown to the person (e.g. "you asked for a short clip with sound").
- A bare description of a scene or subject with no mention of video, motion, seconds, animation, a song or music is a
  PICTURE (role image) - even if it says "cinematic".

EXAMPLES
"a cat astronaut floating in space, cinematic" -> render, role image
"waves crashing on rocks, 8 second clip" -> render, role video
"design a logo for my bakery" -> skill logo
"remove the background" (picture attached) -> skill cutout
"lofi beat for studying" -> skill lofi
"how do I write a good hook?" -> chat
"make a slow reggae song about my hometown using my voice" (audio attached) -> pipeline myvoice,
  steps ["Roots reggae song about growing up in my hometown, slow 75 BPM one-drop groove, warm nostalgic mood",
         "warm, relaxed lead vocal"]

Output ONLY this JSON ("steps" only for a pipeline, else []; "knobs" only numbers the person actually said, e.g.
{{"bpm": "85", "len": "60"}}, else {{}}):
{{"action": "chat|render|skill|pipeline", "role": "image|video|song|music|", "skill": "", "pipeline": "",
  "prompt": "...", "steps": [], "knobs": {{}}, "use_previous": false, "why": "..."}}"""


def _context(history, refs):
    lines = []
    if history:
        lines.append("Recent turns (oldest first):")
        for h in history[-4:]:
            made = (" -> made %s" % h["made"]) if h.get("made") else ""
            lines.append("- person: %s | handled by: %s%s" % (h["q"][:300], h["tool"], made))
    kinds = [core.kind_of(r) for r in refs or []]
    if kinds:
        lines.append("Attached to this message: " + ", ".join("%d %s" % (kinds.count(k), k) for k in sorted(set(kinds)) if k))
    else:
        lines.append("Nothing is attached to this message.")
    return "\n".join(lines)


def _valid(d, refs):
    """Normalise a model decision against the live catalog; None if unusable."""
    if not isinstance(d, dict):
        return None
    act = str(d.get("action") or "").lower().strip()
    out = {"action": act, "prompt": str(d.get("prompt") or "").strip(), "why": str(d.get("why") or "").strip()[:80],
           "use_previous": bool(d.get("use_previous")),
           "knobs": {str(k): str(v) for k, v in (d.get("knobs") or {}).items()} if isinstance(d.get("knobs"), dict) else {}}
    if act == "skill":
        s = skills.skill(str(d.get("skill") or "").lower().strip())
        if not s:
            return None
        if skills.missing(s, [core.kind_of(r) for r in refs or []]) and not out["use_previous"]:
            # the preset needs an attachment the person didn't give: fall back to a plain render of that role
            if s["role"] == "text":
                return dict(out, action="chat")
            return dict(out, action="render", role=s["role"])
        return dict(out, skill=s["id"], role=s["role"])
    if act == "pipeline":
        p = skills.pipeline(str(d.get("pipeline") or "").lower().strip())
        if not p:
            return None
        if skills.missing(p, [core.kind_of(r) for r in refs or []]) and not out["use_previous"]:
            # the manual needs an attachment the person didn't give: do its first step alone and say why
            return dict(out, action="render", role=p["steps"][0]["role"],
                        why=skills.missing(p, [core.kind_of(r) for r in refs or []])[:80])
        steps = [str(x).strip()[:2000] for x in (d.get("steps") or []) if isinstance(x, (str, int, float))]
        return dict(out, pipeline=p["id"], steps=steps[:len(p["steps"])])
    if act == "render":
        role = str(d.get("role") or "").lower().strip()
        return dict(out, role=role) if role in RENDER_ROLES else None
    if act == "chat":
        return out
    return None


# ── keyword fallback (no model / bad answer) ─────────────────────────────────
_KW = [
    ("video", r"\b(video|clip|animate|animation|footage|movie|film|reel|tiktok|short|scene)\b"),
    ("song", r"\b(song|sing|singing|vocals?|ballad|anthem|track with lyrics)\b"),
    ("music", r"\b(beat|instrumental|loop|jingle|lo-?fi|music|soundtrack|melody|remix|cover)\b"),
    ("image", r"\b(image|picture|photo|pic|drawing|draw|paint|painting|illustration|logo|poster|wallpaper|art|render|thumbnail)\b"),
]
_MAKE = r"\b(make|create|generate|render|draw|paint|design|produce|compose|give me|show me|i want|i need|can you (make|create|do))\b"


def fallback(prompt, refs):
    p = (prompt or "").lower()
    kinds = {core.kind_of(r) for r in refs or []}
    if "?" in p and not re.search(_MAKE, p):
        return {"action": "chat", "prompt": prompt, "why": "sounds like a question", "use_previous": False}
    if re.search(r"\b(write|lyrics|story|poem|script|caption|explain|what is|who is|how (do|does|to))\b", p) and not re.search(_MAKE, p):
        return {"action": "chat", "prompt": prompt, "why": "writing or a question", "use_previous": False}
    if "image" in kinds and re.search(r"\b(animate|move|bring .* to life|make it move)\b", p):
        return {"action": "skill", "skill": "animate", "role": "video", "prompt": prompt, "why": "animate the attached picture",
                "use_previous": False}
    if re.search(r"\bmusic video\b", p):
        return {"action": "pipeline", "pipeline": "musicvideo", "prompt": prompt, "why": "a song with a video", "use_previous": False}
    for role, rx in _KW:
        if re.search(rx, p):
            return {"action": "render", "role": role, "prompt": prompt, "why": "you asked for %s" % skills.ROLES[role]["label"].lower(),
                    "use_previous": False}
    if "image" in kinds:
        return {"action": "render", "role": "image", "prompt": prompt, "why": "edit the attached picture", "use_previous": False}
    if "audio" in kinds:
        return {"action": "render", "role": "music", "prompt": prompt, "why": "work with the attached track", "use_previous": False}
    if re.search(_MAKE, p):
        return {"action": "render", "role": "image", "prompt": prompt, "why": "a picture fits best", "use_previous": False}
    talk = r"^(hi|hey|hello|thanks|thank you|ok|okay|yes|no|what|why|how|who|when|where|which|can you|could you|tell me|explain|do you|are you|is it|i think|i feel)\b"
    if len(p.split()) <= 30 and not re.search(talk, p.strip()):
        return {"action": "render", "role": "image", "prompt": prompt, "why": "a description reads as a picture", "use_previous": False}
    return {"action": "chat", "prompt": prompt, "why": "conversation", "use_previous": False}


# Presets the person's own words point at unmistakably. Applied after the model (or the keyword router) picked a role,
# so "logo for my bakery" gets the Logo Mark preset instead of a generic picture.
_SKILL_KW = [
    ("cutout", "image", r"remove (the )?background|cut ?out|transparent background|no background", "image"),
    ("restyle", "image", r"\brestyle\b|in the style of|make (it|this) look like|turn (it|this|me) into", "image"),
    ("animate", "video", r"\banimate\b|\bmake\b.{0,25}\bmove\b|\bbring\b.{0,25}\bto life\b", "image"),
    ("logo", "image", r"\blogo\b", None),
    ("product", "image", r"product (photo|shot|image)|packshot|e-?commerce", None),
    ("thumbnail", "image", r"\bthumbnail\b", None),
    ("portrait", "image", r"\bheadshot\b|\bportrait\b", None),
    ("reel", "video", r"\breels?\b|tiktok|\bshorts\b", None),
    ("spin", "video", r"turntable|\b360\b|spinning product|product spin", None),
    ("lofi", "music", r"\blo-?fi\b", None),
    ("jingle", "music", r"\bjingle\b", None),
    ("remix", "music", r"\bremix\b|\brework\b", "audio"),
    ("morph", "video", r"\bmorph\b|\btransform(s|ing)? (from )?.{0,40}\binto\b|\btransition from\b", "image"),
]
_VIDEO_WORDS = r"video|clip|animat|movie|film|footage|motion|moving|\b\d+\s*(s|sec|secs|seconds)\b|--\d+s|reel|tiktok|timelapse"


_SONGY = r"\b(song|sing|sings|singing|sung|track|tune|ballad|anthem|chorus|verse|lyrics|rap|cover)\b"
_VOICE_PHRASE = (r"\b(sung\s+|sing\s+it\s+)?(using|with|in|from|use)\s+(the\s+)?(voice|vocals?|singing)?\s*(of|in|on|from)?\s*(the\s+)?"
                 r"(my|this|that|the|attached|recorded)\s+(own\s+)?(voice|vocals?|recording|singing|clip|audio)"
                 r"(\s+(in|from|on)\s+(my|the|this)\s+(recording|clip|audio|file))?\b|\b(sung|sing it)\s+(like|as)\s+me\b")


def _manual_rule(d, prompt, refs):
    """Manuals the person's own words + attachments point at unmistakably (the 8B model can miss these)."""
    p = (prompt or "").lower()
    kinds = [core.kind_of(r) for r in refs or []]
    if d["action"] == "chat" and not re.search(_MAKE, p) and not re.search(r"\b(sing|sung|perform)\b", p):
        return d
    if d["action"] == "pipeline" and d.get("pipeline") in _RULE_ORDER:
        return d
    for pid in _RULE_ORDER:                      # most specific first
        man = skills.pipeline(pid)
        if not man or skills.missing(man, kinds) or not re.search(man["triggers"], p, re.I):
            continue
        if man.get("also") and not re.search(man["also"], p, re.I):
            continue
        if pid in ("myvoice", "myvoicevideo") and not re.search(_SONGY, p):
            continue
        voice = pid in ("myvoice", "myvoicevideo")
        brief = core.clean_ws(re.sub(_VOICE_PHRASE, "", prompt or "", flags=re.I)).strip(" ,.") if voice else ""
        return {"action": "pipeline", "pipeline": pid, "prompt": prompt, "steps": [brief] if brief else [],
                "knobs": d.get("knobs") or {}, "use_previous": False, "why": _RULE_WHY.get(pid, man["desc"][:60])}
    return d


_RULE_ORDER = ("coverme", "myvoicevideo", "myvoice", "visualizer", "productstudio", "singer", "lyricsong", "adspot")
_RULE_WHY = {"coverme": "re-sing that song in your voice", "myvoice": "a song, re-sung in your recorded voice",
             "myvoicevideo": "your-voice song plus a music video", "visualizer": "a video scored with your track",
             "productstudio": "your product in a new scene, then moving", "singer": "a character performing their song",
             "lyricsong": "lyrics written first, then sung", "adspot": "packshot, jingle and the ad clip"}


def _refine(d, prompt, refs):
    d = _manual_rule(d, prompt, refs)
    p = (prompt or "").lower()
    kinds = {core.kind_of(r) for r in refs or []}
    if d["action"] == "render" and d.get("role") == "video" and not re.search(_VIDEO_WORDS, p) \
            and "image" not in kinds and not d.get("use_previous"):
        d = dict(d, role="image", why=d.get("why") or "a picture of that scene")    # no motion asked for → a picture
    if d["action"] in ("render", "skill"):
        for sid, role, rx, needs in _SKILL_KW:
            if not re.search(rx, p):
                continue
            if needs and needs not in kinds and not d.get("use_previous"):
                continue
            if d["action"] == "skill" and d.get("skill") == sid:
                break
            if d["action"] == "render" and d.get("role") not in (role, None) and not (sid in ("animate", "morph") and d.get("role") == "image"):
                continue                                   # the words point at a preset of another role: keep the model's call
            s = skills.skill(sid)
            if s and skills.missing(s, [core.kind_of(r) for r in refs or []]) and not d.get("use_previous"):
                continue                                   # e.g. morph wants TWO pictures
            if s:
                d = dict(d, action="skill", skill=sid, role=s["role"])
            break
    return d


def decide(prompt, refs=None, history=None, model=None):
    """→ {"action", "role"?, "skill"?, "pipeline"?, "prompt", "use_previous", "why", "by"}"""
    refs = refs or []
    if not (prompt or "").strip() and refs:
        kinds = {core.kind_of(r) for r in refs}
        role = "video" if "image" in kinds else "music" if "audio" in kinds else "image"
        return {"action": "render", "role": role, "prompt": "", "why": "attachment only", "use_previous": False, "by": "rules"}
    t0 = time.time()
    core.ensure_ollama()
    try:
        body = {"model": model, "stream": False, "format": "json", "keep_alive": KEEP_ALIVE,
                "options": {"temperature": 0.1, "num_ctx": ROUTER_CTX, "num_predict": 900},
                "messages": [{"role": "system", "content": SYSTEM.format(catalog=_catalog_text())},
                             {"role": "user", "content": _context(history, refs) + "\n\nMessage:\n" + prompt}]}
        r = core.requests.post(core.OLLAMA + "/api/chat", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        raw = (r.json().get("message") or {}).get("content", "")
        d = _valid(json.loads(raw), refs)
        if d:
            if not d["prompt"] or d["action"] == "chat":
                d["prompt"] = prompt                     # chat keeps the person's own words
            elif re.findall(r"--\w+", prompt):           # never lose the person's flags
                missing = [f for f in re.findall(r"--[\w-]+(?:\s+\d+)?", prompt) if f not in d["prompt"]]
                d["prompt"] = (d["prompt"] + " " + " ".join(missing)).strip()
            d = _refine(d, prompt, refs)
            if d["action"] == "pipeline" and d.get("steps") and re.findall(r"--\w+", prompt):
                missing = [f for f in re.findall(r"--[\w-]+(?:\s+\d+)?", prompt) if f not in d["steps"][0]]
                d["steps"][0] = (d["steps"][0] + " " + " ".join(missing)).strip()   # flags steer the first step
            d["by"], d["ms"] = "muse", int((time.time() - t0) * 1000)
            return d
    except Exception:
        pass
    d = _refine(fallback(prompt, refs), prompt, refs)
    d["by"] = "rules"
    return d


def label(d):
    """Short human line for the chat: 'MUSE → Video · Cinematic Shot'."""
    if d["action"] == "chat":
        return "Chat"
    if d["action"] == "pipeline":
        p = skills.pipeline(d["pipeline"])
        if not p:
            return "Pipeline · " + d["pipeline"]
        return "Pipeline · %s (%s)" % (p["name"], " → ".join(skills.step_label(s) for s in p["steps"]))
    role = skills.ROLES.get(d.get("role"), {}).get("label", d.get("role", ""))
    if d["action"] == "skill":
        s = skills.skill(d["skill"])
        return "%s · %s" % (role, s["name"] if s else d["skill"])
    return role


_FAKE = {"audio": "x.wav", "image": "x.png", "video": "x.mp4", "text": "x.txt"}


def preview(prompt, kinds):
    """Quick-rules guess (no model, a few ms) for the composer's 'MUSE will likely…' line."""
    refs = [_FAKE[k] for k in kinds if k in _FAKE]
    if not (prompt or "").strip() or (prompt or "").lstrip().startswith("/"):
        return None
    d = _refine(fallback(prompt, refs), prompt, refs)
    out = {"action": d["action"], "label": label(d), "why": d.get("why", "")}
    if d["action"] == "pipeline":
        out["pipeline"] = d["pipeline"]
    elif d["action"] == "skill":
        out["skill"] = d["skill"]
    return out
