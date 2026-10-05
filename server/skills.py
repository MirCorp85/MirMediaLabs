"""MIR MEDIA LABS skills, pipelines and the chat command book.

Media Labs only — nothing here touches MirOS. A SKILL is one render with a tuned prompt template and
parameter overrides. A PIPELINE is a MANUAL: ordered steps in ONE job (it still holds the single GPU slot, so the
one-request-at-a-time rule covers the whole chain); each step names its inputs (the person's attachments and/or
earlier steps' outputs, in order) and what it carries forward (lyrics, tempo, key, style). MUSE reads the manuals,
picks one and writes a prompt per step.
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
    {"id": "remix", "name": "Remix Track", "icon": "refresh", "role": "music", "needs": "audio",
     "desc": "Rework the attached track into a new style",
     "tpl": "{input}", "params": {"ace": {"mode": "remix"}}},
    {"id": "restyle_song", "name": "Restyle Song", "icon": "palette", "role": "music", "needs": "audio",
     "desc": "Same song and singer, new genre / arrangement",
     "tpl": "{input}", "params": {"ace": {"mode": "cover"}}},
    {"id": "morph", "name": "Morph A → B", "icon": "wand", "role": "video", "needs": {"image": 2},
     "desc": "A clip that travels from picture 1 to picture 2",
     "tpl": "Smooth continuous transformation from the first picture into the last picture: {input}",
     "params": {"h3": {"mode": "flf2v"}}},
]

# ── PIPELINES = MANUALS ────────────────────────────────────────────────────────────────────────────────────────────
# A pipeline is an instruction manual MUSE follows: ordered steps, each saying which ROLE renders, what the step DOES
# (plain words MUSE and the person read), which INPUTS it gets and what it CARRIES forward from earlier steps.
#   when     — when MUSE should pick this manual (read by the Director)
#   needs    — attachments the manual requires, e.g. {"audio": 1}; checked before anything renders
#   triggers — regex on the person's words that makes the quick rules pick this manual even if the model misses it
#   knobs    — dials shown in the composer (see below)
# step fields:
#   inputs   — ordered reference list: "user:<kind>" (the person's attachments of that kind; "user:audio>len" = longest
#              first), "prev[:kind]", "stepN[:kind]", "all". Absent → old behaviour: the person's attachments + "use".
#   use      — legacy: "prev" | "all" earlier outputs appended after the person's attachments
#   carry    — data handed forward from earlier steps: style (the song's own description) · lyrics · bpm · key
#   mode     — forces the engine's mode for this step (e.g. the music role's voice swap)
#   add      — text / flags always appended to this step's prompt (e.g. "--15s" so a song fits a 15 s clip)
#   also     — (manual) extra regex the person's words must match for the quick rules to pick it (e.g. video words)
# KNOBS: {"k", "label", "type": range|select, "def", min/max/step | opts, "to": {"step": n, "param": p} or {"step": n, "add": "..{v}.."}}
#   "param" sets that step's engine parameter by its generic name (mapped per engine in PARAM_MAP, clamped by params);
#   "add" appends text / flags to the step prompt. An empty value ("") = leave it to MUSE / the engine.
#   Skills take the same knobs without "step".
_LEN = {"k": "len", "label": "Length", "type": "select", "def": "", "opts": [["", "auto"], ["30", "30 s"], ["60", "1 min"],
        ["90", "1.5 min"], ["120", "2 min"], ["180", "3 min"]], "to": {"step": 1, "add": "--{v}s"}}
_BPM = {"k": "bpm", "label": "Tempo", "type": "select", "def": "", "opts": [["", "auto"], ["70", "70 slow"], ["85", "85"],
        ["100", "100"], ["120", "120"], ["140", "140 fast"], ["170", "170"]], "to": {"step": 1, "add": "{v} BPM"}}
_MATCH = {"k": "match", "label": "Voice match", "type": "range", "def": 0.65, "min": 0.3, "max": 0.95, "step": 0.05,
          "to": {"step": 2, "param": "voice_strength"}}
_SECS = {"k": "secs", "label": "Clip length", "type": "select", "def": "", "opts": [["", "auto"], ["5", "5 s"], ["8", "8 s"],
         ["10", "10 s"], ["15", "15 s"]], "to": {"step": 2, "add": "--{v}s"}}

# generic knob param → engine param (front-ends never see engine names; swapping an engine = add its row here)
PARAM_MAP = {"voice_strength": {"ace": "voice"}, "remix_strength": {"ace": "remix"}, "cover_strength": {"ace": "cover"},
             "aspect": {"qimg": "aspect", "h3": "aspect"}}
_VIDEO_WORDS = r"\b(video|clip|visuali[sz]er|music video|animate|footage|reel)\b"

PIPELINES = [
    {"id": "myvoice", "name": "Sing It In My Voice", "icon": "mic",
     "desc": "Compose a full song on your topic and rhythm, then re-sing it with your recorded voice",
     "when": "a voice / audio recording is attached AND the person wants a NEW song sung with that voice",
     "needs": {"audio": 1}, "slotnames": {"audio": ["Your voice"]},
     "triggers": r"\b(my|this|that|the|attached|recorded)\s+(own\s+)?(voice|vocals?|recording|singing)\b|\bsing(s|ing)? (it )?(like|as) me\b|\bwith me singing\b",
     "knobs": [_LEN, _BPM, _MATCH],
     "steps": [{"role": "song", "does": "Compose and sing the complete song: topic, genre, rhythm / BPM, mood and lyrics.",
                "tpl": "{input}", "inputs": ["user:text", "user:image", "user:video"],
                "params": {"music3": {"lyrics": "auto"}}},
               {"role": "music", "mode": "voice", "does": "Re-sing the step 1 song with the attached voice, keeping its words, tempo and key.",
                "tpl": "", "inputs": ["step1:audio", "user:audio"], "carry": ["style", "bpm", "key", "lyrics"],
                "params": {"ace": {"mode": "voice"}}}]},
    {"id": "coverme", "name": "Cover In My Voice", "icon": "mic",
     "desc": "Re-sing an attached song with an attached voice recording",
     "when": "TWO audio files are attached (a song and a voice) and the person wants that song sung in that voice",
     "needs": {"audio": 2}, "slotnames": {"audio": ["Song (longer)", "Voice (shorter)"]},
     "triggers": r"\b(cover|re-?sing|swap the voice|replace the (voice|vocals?|singer)|in my voice|with my voice)\b",
     "knobs": [dict(_MATCH, to={"step": 1, "param": "voice_strength"})],
     "steps": [{"role": "music", "mode": "voice", "does": "Re-sing the longer attached track (the song) with the shorter one (the voice).",
                "tpl": "{input}", "inputs": ["user:audio>len", "user:text"], "params": {"ace": {"mode": "voice"}}}]},
    {"id": "myvoicevideo", "name": "My Voice Music Video", "icon": "film",
     "desc": "Song on your topic, re-sung in your voice, then a music video scored with it",
     "when": "a voice recording is attached AND the person wants a song in that voice WITH a video / music video",
     "needs": {"audio": 1}, "slotnames": {"audio": ["Your voice"]}, "also": _VIDEO_WORDS,
     "triggers": r"\b(my|this|that|the|attached|recorded)\s+(own\s+)?(voice|vocals?|recording|singing)\b|\bin my voice\b",
     "knobs": [_BPM, _MATCH],
     "steps": [{"role": "song", "does": "Compose and sing the song: topic, genre, rhythm / BPM, mood and lyrics.",
                "tpl": "{input}", "add": "--30s", "inputs": ["user:text", "user:image"], "params": {"music3": {"lyrics": "auto"}}},
               {"role": "music", "mode": "voice", "does": "Re-sing the step 1 song with the attached voice.",
                "tpl": "", "inputs": ["step1:audio", "user:audio"], "carry": ["style", "bpm", "key", "lyrics"],
                "params": {"ace": {"mode": "voice"}}},
               {"role": "image", "does": "Paint cover art that matches the song.", "inputs": ["user:image"], "carry": ["style"],
                "tpl": "Album cover art for a song about {input}. Bold, cinematic, no text.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "does": "Animate the cover art, scored with the step 2 song in your voice.", "inputs": ["step3:image", "step2:audio"],
                "tpl": "Music video scene for {input}. Rhythmic camera motion, atmospheric light.",
                "params": {"h3": {"mode": "i2v", "soundtrack": "replace", "seconds": 15}}}]},
    {"id": "visualizer", "name": "Track Visualizer", "icon": "film",
     "desc": "Cover art for your attached track, animated and scored with it",
     "when": "an audio track is attached and the person wants a video / visualiser / music video FOR that track",
     "needs": {"audio": 1}, "slotnames": {"audio": ["Your track"]}, "also": _VIDEO_WORDS,
     "triggers": r"\bvisuali[sz]er\b|\b(video|clip|visuals?)\s+(for|to|with)\s+(my|this|the|that|attached)\s+(song|track|beat|music|audio)\b|\bmusic video\b",
     "knobs": [_SECS],
     "steps": [{"role": "image", "does": "Paint cover art for the track.", "inputs": ["user:image", "user:text"],
                "tpl": "Album cover art for {input}. Bold, cinematic, no text.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "does": "Animate the cover art, scored with your attached track.", "inputs": ["step1:image", "user:audio"],
                "tpl": "Music video scene for {input}. Rhythmic camera motion, atmospheric light.",
                "params": {"h3": {"mode": "i2v", "soundtrack": "replace", "seconds": 15}}}]},
    {"id": "lyricsong", "name": "Write → Sing", "icon": "note",
     "desc": "MUSE writes the lyrics first, then the song sings them word for word",
     "when": "the person wants a song AND cares about the words (\"write lyrics and sing them\", a story told in a song)",
     "triggers": r"\b(write|pen)\b.{0,40}\blyrics\b.{0,60}\b(sing|sung|song|perform|record)\b|\bstory\b.{0,30}\b(as|in|into) a song\b",
     "knobs": [dict(_LEN, to={"step": 2, "add": "--{v}s"}), dict(_BPM, to={"step": 2, "add": "{v} BPM"})],
     "steps": [{"role": "text", "does": "Write the lyrics: verses, a strong chorus hook, a bridge.", "inputs": [],
                "tpl": "Write original song lyrics about {input}. Use section tags alone on their own line - [Intro] [Verse] [Pre-Chorus] [Chorus] [Verse] [Chorus] [Bridge] [Chorus] [Outro] - with a blank line between sections, 6-10 syllables per line, backing vocals in (parentheses), only singable words and a memorable hook in the chorus. Output only the lyrics, no title.",
                "params": {"llama": {"mode": "creative", "length": "medium", "temperature": 0.85}}},
               {"role": "song", "does": "Compose and sing those exact lyrics.", "inputs": ["user:image"], "carry": ["lyrics"],
                "tpl": "{input}", "params": {"music3": {"lyrics": "auto"}}}]},
    {"id": "adspot", "name": "Ad Spot + Jingle", "icon": "bell",
     "desc": "Vertical packshot → jingle → 9:16 ad clip scored with the jingle",
     "when": "a complete ad / commercial / promo for a product WITH music or a jingle",
     "triggers": r"\b(ad|advert|commercial|promo)\b", "also": r"\b(jingle|music|song|soundtrack)\b",
     "steps": [{"role": "image", "does": "Shoot a vertical studio packshot.", "inputs": ["user:image", "user:text"],
                "tpl": "Professional studio product photograph of {input}, clean backdrop, premium lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "music", "does": "Write a catchy 15-second jingle.", "inputs": [],
                "tpl": "Short catchy upbeat advertising jingle, memorable hook, for {input}", "add": "--15s", "params": {"ace": {"mode": "text", "duration": 15}}},
               {"role": "video", "does": "Animate the packshot into an ad clip scored with the jingle.", "inputs": ["step1:image", "step2:audio"],
                "tpl": "Premium product ad: {input}. Slow orbiting camera, light sweeps across the product.",
                "params": {"h3": {"mode": "i2v", "aspect": "9:16", "soundtrack": "replace", "seconds": 15}}}]},
    {"id": "productstudio", "name": "Product Studio", "icon": "box",
     "desc": "Your product photo → cut out → placed in a styled scene → turntable clip",
     "when": "a product photo is attached and the person wants it in a new scene / setting AND moving",
     "needs": {"image": 1}, "slotnames": {"image": ["Your product"]},
     "triggers": r"\b(scene|setting|backdrop|background|studio|place (it|this)|put (it|this))\b",
     "also": r"\b(spin|orbit|turntable|video|clip|animate|moving|360)\b",
     "knobs": [dict(_SECS, to={"step": 3, "add": "--{v}s"})],
     "steps": [{"role": "image", "does": "Cut the product out of its background.", "inputs": ["user:image"],
                "tpl": "Cut out the main product", "params": {"qimg": {"mode": "cutout"}}},
               {"role": "image", "does": "Place the product into the scene you describe.", "inputs": ["step1:image"],
                "tpl": "Place this exact product in a new scene: {input}. Keep the product's shape, colours, logo and text exactly.",
                "params": {"qimg": {"mode": "edit"}}},
               {"role": "video", "does": "Slow orbit around the product in its new scene.", "inputs": ["step2:image"],
                "tpl": "Slow orbiting camera around the product: {input}. Premium commercial look, light sweeps.",
                "params": {"h3": {"mode": "i2v"}}}]},
    {"id": "singer", "name": "Singing Character", "icon": "user",
     "desc": "Design a character, write them a song, then a clip of them performing to it",
     "when": "a character / avatar / mascot who sings or performs a song",
     "triggers": r"\b(character|avatar|mascot|cartoon|robot|creature)\b.{0,40}\b(sing|sings|singing|performs?|performing)\b|\bsinging (character|avatar|mascot)\b",
     "steps": [{"role": "image", "does": "Design the character portrait.", "inputs": ["user:image", "user:text"],
                "tpl": "Character portrait of {input}, singing on stage, expressive, cinematic lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "song", "does": "Write and sing a short song for the character.", "inputs": [],
                "tpl": "{input}", "add": "--15s", "params": {"music3": {"lyrics": "auto"}}},
               {"role": "video", "does": "The character performs, scored with the step 2 song.", "inputs": ["step1:image", "step2:audio"],
                "tpl": "The character sings and performs with emotion: {input}. Expressive face, subtle body movement, stage light.",
                "params": {"h3": {"mode": "i2v", "soundtrack": "replace", "seconds": 15}}}]},
    {"id": "poster2motion", "name": "Poster → Motion", "icon": "layers",
     "desc": "Design a key image, then animate it into a video",
     "when": "the person wants a still key visual AND that same visual moving",
     "knobs": [_SECS],
     "steps": [{"role": "image", "does": "Design the key art.", "inputs": ["user:image", "user:text"],
                "tpl": "Striking cinematic key art of {input}. Rich lighting, strong composition.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "does": "Animate the step 1 key art.", "inputs": ["step1:image"],
                "tpl": "Bring this image to life: {input}. Smooth camera push-in, natural motion.", "params": {"h3": {"mode": "i2v"}}}]},
    {"id": "productad", "name": "Product Ad", "icon": "layers",
     "desc": "Studio packshot → vertical 9:16 ad clip",
     "when": "an ad / promo clip for a product",
     "knobs": [_SECS],
     "steps": [{"role": "image", "does": "Shoot a vertical studio packshot of the product.", "inputs": ["user:image", "user:text"],
                "tpl": "Professional studio product photograph of {input}, clean backdrop, premium lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "video", "does": "Turn the packshot into an orbiting ad clip.", "inputs": ["step1:image"],
                "tpl": "Premium product ad: {input}. Slow orbiting camera, light sweeps across the product.", "params": {"h3": {"mode": "i2v", "aspect": "9:16"}}}]},
    {"id": "character", "name": "Character Clip", "icon": "layers",
     "desc": "Create a character portrait, then make them move and speak",
     "when": "invent a character and see them come alive",
     "knobs": [_SECS],
     "steps": [{"role": "image", "does": "Design the character portrait.", "inputs": ["user:image", "user:text"],
                "tpl": "Character portrait: {input}. Detailed, expressive, cinematic lighting.", "params": {"qimg": {"aspect": "9:16", "mode": "auto"}}},
               {"role": "video", "does": "Bring the character to life with expressions and movement.", "inputs": ["step1:image"],
                "tpl": "The character comes alive: {input}. Natural expressions and subtle movement.", "params": {"h3": {"mode": "i2v"}}}]},
    {"id": "musicvideo", "name": "Music Video", "icon": "layers",
     "desc": "Track → cover art → video scored with that track",
     "when": "a music video / visualiser: a track AND moving pictures that go with it",
     "knobs": [_BPM],
     "steps": [{"role": "music", "does": "Make the track.", "inputs": ["user:text", "user:image"],
                "tpl": "{input}", "params": {"ace": {"mode": "text", "duration": 30}}},
               {"role": "image", "does": "Paint the cover art for the track.", "inputs": ["user:image"], "carry": ["style"],
                "tpl": "Album cover art for a song about {input}. Bold artistic, no text.", "params": {"qimg": {"aspect": "16:9", "mode": "auto"}}},
               {"role": "video", "does": "Animate the cover art, scored with the step 1 track.", "inputs": ["step2:image", "step1:audio"],
                "tpl": "Music video scene for {input}. Rhythmic camera motion, atmospheric light.", "params": {"h3": {"mode": "i2v", "soundtrack": "replace", "seconds": 10}}}]},
    {"id": "albumpack", "name": "Album Pack", "icon": "disc",
     "desc": "A full song plus matching square cover art",
     "when": "a finished song AND its cover / artwork",
     "knobs": [_LEN, _BPM],
     "steps": [{"role": "song", "does": "Compose and sing the full song.", "inputs": ["user:text", "user:image"], "tpl": "{input}", "params": {}},
               {"role": "image", "does": "Paint square cover art that matches the song.", "inputs": ["user:image"], "carry": ["style"],
                "tpl": "Square album cover art for: {input}. Artistic, striking, no text.", "params": {"qimg": {"aspect": "1:1", "mode": "auto"}}}]},
]

def _nostep(k):
    return dict(k, to={x: y for x, y in k["to"].items() if x != "step"})


_SKILL_KNOBS = {"song": [_LEN, _BPM], "beat": [_LEN, _BPM], "lofi": [_LEN, _BPM], "jingle": [_BPM],
                "cinematic": [_SECS], "animate": [_SECS], "reel": [_SECS], "spin": [_SECS]}
for _s in SKILLS:
    if _s["id"] in _SKILL_KNOBS:
        _s["knobs"] = [_nostep(k) for k in _SKILL_KNOBS[_s["id"]]]

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
    {"cmd": "/myvoice", "args": "<song idea>", "desc": "Song on your topic + rhythm, re-sung in your attached voice recording"},
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


# ── manuals: reading, checking and wiring ──────────────────────────────────────────────────────────────────────────
def manual_text(p):
    """A manual as numbered plain-English steps (Director, MUSE and the UI all read this)."""
    lines = []
    for i, st in enumerate(p["steps"], 1):
        lines.append("%d. %s: %s" % (i, step_label(st), st.get("does") or p.get("desc", "")))
    return lines


def step_label(st):
    return "Voice swap" if st.get("mode") == "voice" else ROLES[st["role"]]["label"]


def needs_of(entry):
    """{"audio": 1} for manuals; skills' single "needs" kind → {kind: 1}."""
    n = entry.get("needs")
    if isinstance(n, dict):
        return dict(n)
    return {n: 1} if n else {}


def missing(entry, kinds):
    """Plain sentence for what's missing ('attach a voice recording'), or '' when the attachments satisfy the manual."""
    for k, n in needs_of(entry).items():
        have = sum(1 for x in kinds if x == k)
        if have < n:
            what = {"audio": "audio file", "image": "picture", "video": "clip", "text": "text file"}.get(k, k)
            if entry.get("id") == "myvoice":
                return "attach your voice recording (tap the mic) for %s" % entry["name"]
            return "%s needs %d attached %s%s" % (entry["name"], n, what, "s" if n > 1 else "")
    return ""


def resolve_inputs(st, user_refs, outs, kind_of, seconds_of=None):
    """Step's ordered reference list from its "inputs" tokens. outs = [[refs of step 1], [refs of step 2], …]."""
    toks = st.get("inputs")
    if toks is None:                                           # legacy pipelines: attachments + "use"
        use = st.get("use")
        extra = (outs[-1] if outs else []) if use == "prev" else [r for o in outs for r in o] if use == "all" else []
        return list(user_refs) + extra
    got = []
    for t in toks:
        src, _, kind = t.partition(":")
        order = None
        if ">" in kind:
            kind, _, order = kind.partition(">")
        if src == "user":
            pool = list(user_refs)
        elif src == "prev":
            pool = list(outs[-1]) if outs else []
        elif src.startswith("step") and src[4:].isdigit():
            i = int(src[4:]) - 1
            pool = list(outs[i]) if 0 <= i < len(outs) else []
        elif src == "all":
            pool = list(user_refs) + [r for o in outs for r in o]
        else:
            pool = []
        if kind:
            pool = [r for r in pool if kind_of(r) == kind]
        if order == "len" and seconds_of:
            pool.sort(key=lambda r: -(seconds_of(r) or 0))
        got += [r for r in pool if r not in got]
    return got


def knob_values(entry, raw):
    """Validate the composer's knob values against the entry's knob list → {k: value} (blank = untouched)."""
    out = {}
    for kb in entry.get("knobs") or []:
        v = (raw or {}).get(kb["k"])
        if v in (None, ""):
            continue
        if kb["type"] == "range":
            try:
                out[kb["k"]] = max(kb["min"], min(kb["max"], float(v)))
            except (TypeError, ValueError):
                pass
        else:
            allowed = [str(o[0] if isinstance(o, list) else o) for o in kb.get("opts") or []]
            if str(v) in allowed:
                out[kb["k"]] = str(v)
    return out


def knob_effects(entry, values, step_no, model):
    """→ (param overrides for this engine, text to add to the prompt) for one step (step_no None = a skill)."""
    over, add = {}, []
    for kb in entry.get("knobs") or []:
        if kb["k"] not in values:
            continue
        to = kb.get("to") or {}
        if step_no is not None and to.get("step", 1) != step_no:
            continue
        v = values[kb["k"]]
        if to.get("param"):
            p = (PARAM_MAP.get(to["param"]) or {}).get(model, to["param"])
            over[p] = v
        if to.get("add"):
            add.append(to["add"].replace("{v}", ("%g" % v) if isinstance(v, float) else str(v)))
    return over, " ".join(add)


def carry_text(st, meta, model):
    """Prompt pieces handed forward from earlier steps: (prefix, suffix). Lyrics go LAST (engines read '| lyrics:' to the end)."""
    want = st.get("carry") or []
    pre, mid, lyr = "", [], ""
    if "style" in want and meta.get("style"):
        pre = meta["style"]
    if "bpm" in want and meta.get("bpm"):
        mid.append("--bpm %d" % meta["bpm"] if model == "ace" else "%d BPM" % meta["bpm"])
    if "key" in want and meta.get("key"):
        mid.append("in %s" % meta["key"])
    if "lyrics" in want and meta.get("lyrics"):
        lyr = "\n| lyrics:\n" + meta["lyrics"]
    return pre, (" " + " ".join(mid) if mid else "") + lyr


def plan_for(p, prompts=None):
    """The live checklist a pipeline job carries (clients render it; the runner updates status per step)."""
    prompts = prompts or []
    return [{"n": i, "role": st["role"], "label": step_label(st), "icon": ROLES[st["role"]]["icon"],
             "does": st.get("does", ""), "prompt": (prompts[i - 1] if i - 1 < len(prompts) else "") or "",
             "status": "waiting", "inputs": [], "files": []}
            for i, st in enumerate(p["steps"], 1)]


def _pub_role(role):
    r = ROLES[role]
    return {"role": role, "label": r["label"], "icon": r["icon"], "model": r["model"]}   # model = internal id, never shown


def catalog():
    """Front-end view: roles only (the engine id rides along so the client can select it, but is never displayed)."""
    sk = [dict(_pub_role(s["role"]), **{k: v for k, v in s.items() if k not in ("tpl", "params")}) for s in SKILLS]
    pl = [dict({k: v for k, v in p.items() if k not in ("steps", "triggers", "also")}, need=needs_of(p), manual=manual_text(p),
               steps=[dict(_pub_role(x["role"]), label=step_label(x), does=x.get("does", ""),
                           slots=[t.split(":")[1].split(">")[0] for t in x.get("inputs") or [] if t.startswith("user:")])
                      for x in p["steps"]]) for p in PIPELINES]
    for x in sk:
        x["need"] = needs_of(x)
    return {"roles": {k: _pub_role(k) for k in ROLES}, "skills": sk, "pipelines": pl, "commands": COMMANDS, "tips": TIPS}
