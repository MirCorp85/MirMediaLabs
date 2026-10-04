"""MIR MEDIA LABS skills, pipelines and the chat command book.

Media Labs only — nothing here touches MirOS. A SKILL is one render with a tuned prompt template and
parameter overrides. A PIPELINE chains renders in ONE job (it still holds the single GPU slot, so the
one-request-at-a-time rule covers the whole chain): each step's output is fed into the next as a reference.
"{input}" in a template is replaced by what the user typed.

GENERIC FRONT, SPECIFIC BACK: skills / pipelines / commands only name a ROLE (image · video · song · music).
ROLES below is the ONE place that says which engine fills each role today. Parameter overrides are keyed by
engine id, so swapping an engine = change ROLES[role]["model"] and add that engine's overrides next to the old
ones (an engine with no entry just runs on its own saved defaults). Nothing user-facing names an engine.
"""

ROLES = {
    "image": {"label": "Image", "icon": "image", "model": "qimg"},
    "video": {"label": "Video", "icon": "video", "model": "h3"},
    "song":  {"label": "Song",  "icon": "mic", "model": "music3"},   # vocal song with lyrics
    "music": {"label": "Music", "icon": "music", "model": "ace"},      # tracks / beats / instrumentals
    "text":  {"label": "Writing", "icon": "type", "model": "llama"},   # chat + creative writing (standalone only)
}


def model_for(role):
    return ROLES[role]["model"]


def overrides(entry, model):
    """Engine-specific param overrides for this skill/step: {"params": {"<engine id>": {...}}}."""
    return dict((entry.get("params") or {}).get(model) or {})

SKILLS = [
    # ── images (Qwen) ──
    {"id": "product", "name": "Product Shot", "icon": "box", "role": "image",
     "desc": "Clean studio packshot, soft shadows, e-commerce ready",
     "tpl": "Professional studio product photograph of {input}. Seamless light backdrop, soft key light with gentle rim light, "
            "subtle reflection, crisp focus, commercial e-commerce quality.", "params": {"qimg": {"aspect": "1:1", "mode": "auto"}}},
    {"id": "portrait", "name": "Portrait Pro", "icon": "mic", "role": "image",
     "desc": "Editorial headshot, 85mm look, cinematic light",
     "tpl": "Editorial portrait of {input}. 85mm lens look, shallow depth of field, cinematic Rembrandt lighting, "
            "natural skin texture, magazine cover quality.", "params": {"qimg": {"aspect": "4:5", "mode": "auto"}}},
    {"id": "thumbnail", "name": "Thumbnail", "icon": "image", "role": "image",
     "desc": "Bold 16:9 YouTube-style thumbnail with big title text",
     "tpl": "Eye-catching 16:9 video thumbnail about {input}. Bold large readable title text, high contrast, vivid colors, "
            "one clear focal subject, dramatic lighting.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
    {"id": "logo", "name": "Logo Mark", "icon": "sparkle", "role": "image",
     "desc": "Flat vector-style logo on a plain background",
     "tpl": "Minimal flat vector logo mark for {input}. Simple geometric shapes, 2-3 colors, centered on a plain white "
            "background, no mockup, no extra text.", "params": {"qimg": {"aspect": "1:1", "mode": "auto"}}},
    {"id": "restyle", "name": "Restyle Photo", "icon": "palette", "role": "image", "needs": "image",
     "desc": "Edit the attached picture into a new style",
     "tpl": "Restyle this image: {input}. Keep the composition and subject identity.", "params": {"qimg": {"mode": "edit"}}},
    {"id": "cutout", "name": "Cutout", "icon": "scissors", "role": "image", "needs": "image",
     "desc": "Remove the background from the attached picture",
     "tpl": "Cut out the main subject {input}", "params": {"qimg": {"mode": "cutout"}}},
    # ── video (H3) ──
    {"id": "cinematic", "name": "Cinematic Shot", "icon": "video", "role": "video",
     "desc": "Film-look 16:9 shot with camera move and sound",
     "tpl": "Cinematic film shot: {input}. Anamorphic 16:9 look, slow dolly camera move, volumetric light, "
            "shallow depth of field, rich color grade.", "params": {"h3": {"aspect": "16:9", "mode": "auto"}}},
    {"id": "animate", "name": "Animate Photo", "icon": "wand", "role": "video", "needs": "image",
     "desc": "Bring the attached picture to life",
     "tpl": "Bring this image to life: {input}. Natural subtle motion, gentle camera push-in.", "params": {"h3": {"mode": "i2v"}}},
    {"id": "reel", "name": "Social Reel", "icon": "phone", "role": "video",
     "desc": "Vertical 9:16 punchy clip for Reels / TikTok / Shorts",
     "tpl": "Vertical social media clip: {input}. Dynamic handheld energy, fast punchy motion, bright vivid look.",
     "params": {"h3": {"aspect": "9:16", "mode": "auto"}}},
    {"id": "spin", "name": "Product Spin", "icon": "refresh", "role": "video",
     "desc": "Slow turntable orbit around a product",
     "tpl": "Slow 360 degree turntable orbit around {input} on a clean studio pedestal, soft reflections, premium commercial look.",
     "params": {"h3": {"aspect": "1:1", "mode": "auto"}}},
    # ── audio ──
    {"id": "song", "name": "Full Song", "icon": "mic", "role": "song",
     "desc": "Complete vocal song with written lyrics",
     "tpl": "{input}", "params": {"music3": {"lyrics": "auto"}}},
    # ── writing (text model) ──
    {"id": "story", "name": "Short Story", "icon": "book", "role": "text",
     "desc": "Original short story with a clear arc",
     "tpl": "Write an original short story: {input}. Give it a title, a strong opening line, a clear arc and a resonant ending.",
     "params": {"llama": {"mode": "creative", "length": "long", "temperature": 0.9}}},
    {"id": "lyrics", "name": "Song Lyrics", "icon": "mic", "role": "text",
     "desc": "Verse / chorus lyrics ready for the Song model",
     "tpl": "Write original song lyrics about {input}. Use section tags alone on their own line - [Intro] [Verse] [Pre-Chorus] [Chorus] [Verse] [Chorus] [Bridge] [Chorus] [Outro] - with a blank line between sections, 6-10 syllables per line, backing vocals in (parentheses), only singable words and a memorable hook in the chorus. Output only the lyrics, no title.",
     "params": {"llama": {"mode": "creative", "length": "medium", "temperature": 0.85}}},
    {"id": "script", "name": "Video Script", "icon": "film", "role": "text",
     "desc": "Short scene-by-scene script / shot list",
     "tpl": "Write a short video script for {input} as ready-to-send shots for the Video engine: one line per shot, each starting with /video and describing the scene, the action, exactly one camera move, the light and the sound, ending with its length (4-15 s, e.g. 6s). Then one line suggesting music for the edit, starting with /music.",
     "params": {"llama": {"mode": "creative", "length": "medium", "temperature": 0.75}}},
    {"id": "poem", "name": "Poem", "icon": "note", "role": "text",
     "desc": "Free-verse or rhymed poem",
     "tpl": "Write a poem about {input}. Fresh images, musical lines, no clichés.",
     "params": {"llama": {"mode": "creative", "length": "short", "temperature": 0.95}}},
    {"id": "adcopy", "name": "Ad Copy", "icon": "bolt", "role": "text",
     "desc": "Headline, tagline and short ad text",
     "tpl": "Write ad copy for {input}: 3 headline options, 2 taglines, and a 60-word ad body with a call to action.",
     "params": {"llama": {"mode": "creative", "length": "short", "temperature": 0.8}}},
    {"id": "write", "name": "Creative Writing", "icon": "type", "role": "text",
     "desc": "Anything creative — the writer picks the best form",
     "tpl": "{input}", "params": {"llama": {"mode": "creative", "temperature": 0.9}}},
    {"id": "promptcraft", "name": "Prompt Writer", "icon": "wand", "role": "text",
     "desc": "Turns an idea into strong image / video / music prompts",
     "tpl": "Turn this idea into three ready-to-send requests, each on its own line starting with its command: one /image, one /video (one camera move, sound, a length like 8s) and one /music (genre, mood, instruments). Idea: {input}",
     "params": {"llama": {"mode": "chat", "length": "medium", "temperature": 0.7}}},
    {"id": "beat", "name": "Instrumental Beat", "icon": "drum", "role": "music",
     "desc": "Instrumental track, no vocals",
     "tpl": "Instrumental, no vocals. {input}", "params": {"ace": {"mode": "text", "duration": 60}}},
    {"id": "jingle", "name": "Jingle", "icon": "bell", "role": "music",
     "desc": "30-second catchy ad jingle",
     "tpl": "Short catchy upbeat advertising jingle, memorable hook, for {input}", "params": {"ace": {"mode": "text", "duration": 30}}},
    {"id": "lofi", "name": "Lo-fi Loop", "icon": "coffee", "role": "music",
     "desc": "Chill lo-fi hip-hop background loop",
     "tpl": "Instrumental lo-fi hip-hop loop, dusty vinyl, mellow keys, soft boom-bap drums. Mood: {input}",
     "params": {"ace": {"mode": "text", "duration": 90}}},
]

# use: which earlier outputs ride into the step as references — "prev" (last step) or "all" (every earlier step)
PIPELINES = [
    {"id": "poster2motion", "name": "Poster → Motion", "icon": "layers",
     "desc": "Design a key image, then animate it into a video",
     "steps": [{"role": "image", "tpl": "Striking cinematic key art of {input}. Rich lighting, strong composition.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "tpl": "Bring this image to life: {input}. Smooth camera push-in, natural motion.", "params": {"h3": {"mode": "i2v"}}, "use": "prev"}]},
    {"id": "productad", "name": "Product Ad", "icon": "layers",
     "desc": "Studio packshot → vertical 9:16 ad clip",
     "steps": [{"role": "image", "tpl": "Professional studio product photograph of {input}, clean backdrop, premium lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "video", "tpl": "Premium product ad: {input}. Slow orbiting camera, light sweeps across the product.", "params": {"h3": {"mode": "i2v", "aspect": "9:16"}}, "use": "prev"}]},
    {"id": "character", "name": "Character Clip", "icon": "layers",
     "desc": "Create a character portrait, then make them move and speak",
     "steps": [{"role": "image", "tpl": "Character portrait: {input}. Detailed, expressive, cinematic lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "video", "tpl": "The character comes alive: {input}. Natural expressions and subtle movement.", "params": {"h3": {"mode": "i2v"}}, "use": "prev"}]},
    {"id": "musicvideo", "name": "Music Video", "icon": "layers",
     "desc": "Song → cover art → video scored with that song",
     "steps": [{"role": "music", "tpl": "{input}", "params": {"ace": {"mode": "text", "duration": 30}}},
               {"role": "image", "tpl": "Album cover art for a song about {input}. Bold artistic, no text.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "tpl": "Music video scene for {input}. Rhythmic camera motion, atmospheric light.", "params": {"h3": {"mode": "i2v", "soundtrack": "replace", "seconds": 10}}, "use": "all"}]},
    {"id": "albumpack", "name": "Album Pack", "icon": "disc",
     "desc": "A full song plus matching square cover art",
     "steps": [{"role": "song", "tpl": "{input}", "params": {}},
               {"role": "image", "tpl": "Square album cover art for: {input}. Artistic, striking, no text.", "params": {"qimg": {"aspect": "1:1", "mode": "auto"}}}]},
]

# ── chat command book ──
ROLE_CMDS = {"image": "image", "img": "image", "picture": "image", "video": "video", "vid": "video", "clip": "video",
             "song": "song", "music": "music", "track": "music", "beat": "music",
             "chat": "text", "ask": "text", "write": "text"}

COMMANDS = [
    {"cmd": "/help", "args": "", "desc": "Open this command book"},
    {"cmd": "/image", "args": "<idea>", "desc": "Make a picture  (alias /img)"},
    {"cmd": "/video", "args": "<idea>", "desc": "Make a video clip  (alias /vid)"},
    {"cmd": "/song", "args": "<idea>", "desc": "Make a full vocal song"},
    {"cmd": "/chat", "args": "<message>", "desc": "Talk to MUSE, the lab's writer  (alias /ask)"},
    {"cmd": "/write", "args": "<idea>", "desc": "MUSE writes it - stories, lyrics, scripts, poems"},
    {"cmd": "/music", "args": "<idea>", "desc": "Make a music track / beat  (alias /track)"},
    {"cmd": "/skill", "args": "<name> <idea>", "desc": "Run a skill, e.g.  /skill product red sneaker"},
    {"cmd": "/pipe", "args": "<name> <idea>", "desc": "Run a pipeline, e.g.  /pipe musicvideo neon city synthwave"},
    {"cmd": "/skills", "args": "", "desc": "Open the Skills panel"},
    {"cmd": "/clear", "args": "", "desc": "Remove your finished messages from the chat"},
]

TIPS = [
    "One request at a time — the SEND button unlocks when your current render finishes.",
    "Attach pictures / clips / songs / text with 📎; skills marked 📎 need one.",
    "Any finished result → ↻ Use as ref to feed it into the next request.",
    "⚙ sets this model's parameters; skills only override what they need.",
    "Ctrl+Enter sends (web).",
]


def skill(sid):
    return next((s for s in SKILLS if s["id"] == sid), None)


def pipeline(pid):
    return next((p for p in PIPELINES if p["id"] == pid), None)


REF_HINT = " Use the attached picture(s) as the reference: keep the exact logo / design / subject from them."


def fill(tpl, text, has_image=False):
    if has_image and "{input}" in tpl:   # a picture is attached: make the rewrite honour it, not invent a new one
        tpl += REF_HINT
    text = (text or "").strip()
    return tpl.replace("{input}", text) if text else tpl.replace("{input}", "").strip(" .:")


def parse(prompt):
    """Slash command → {model|skill|pipeline, prompt} or None (plain message). Unknown command → {"error"}."""
    p = (prompt or "").strip()
    if not p.startswith("/"):
        return None
    head, _, rest = p[1:].partition(" ")
    head, rest = head.lower(), rest.strip()
    if head in ROLE_CMDS and not skill(head):
        return {"model": model_for(ROLE_CMDS[head]), "prompt": rest}
    if head in ("skill", "pipe", "pipeline"):
        name, _, text = rest.partition(" ")
        if head == "skill":
            return {"skill": name.lower(), "prompt": text.strip()} if skill(name.lower()) else {"error": "no skill '%s' — try /skills" % name}
        return {"pipeline": name.lower(), "prompt": text.strip()} if pipeline(name.lower()) else {"error": "no pipeline '%s' — try /skills" % name}
    if skill(head):          # shorthand: /product red sneaker
        return {"skill": head, "prompt": rest}
    if pipeline(head):
        return {"pipeline": head, "prompt": rest}
    return {"error": "unknown command /%s — type /help" % head}


def _pub_role(role):
    r = ROLES[role]
    return {"role": role, "label": r["label"], "icon": r["icon"], "model": r["model"]}   # model = internal id, never shown


def catalog():
    """Front-end view: roles only (the engine id rides along so the client can select it, but is never displayed)."""
    sk = [dict(_pub_role(s["role"]), **{k: v for k, v in s.items() if k not in ("tpl", "params")}) for s in SKILLS]
    pl = [dict({k: v for k, v in p.items() if k != "steps"}, steps=[_pub_role(x["role"]) for x in p["steps"]]) for p in PIPELINES]
    return {"roles": {k: _pub_role(k) for k in ROLES}, "skills": sk, "pipelines": pl, "commands": COMMANDS, "tips": TIPS}
