"""Per-model parameter schemas (the ⚙ button). One schema feeds the web UI and the
Android app; saved values live in data/prefs.json so desktop and phone share them.
Inline --flags typed in a prompt still win over the panel for that one run."""
import core

SAMPLERS = ["euler", "euler_ancestral", "res_multistep", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_sde", "uni_pc", "heun", "lcm"]
SCHEDS = ["simple", "normal", "karras", "exponential", "sgm_uniform", "beta", "linear_quadratic"]
H3_SAMPLERS = ["res_multistep", "euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_sde", "er_sde", "lcm", "deis"]
H3_STYLES = ["art_is_explosion", "blooming_flowers", "bullet_time", "dark_magic", "fire_breath",
             "four_seasons", "kiss_camera", "spiral_ascent", "storm_magic", "truman_show"]
KEYS = [["auto", "auto"]] + ["%s %s" % (r, q) for q in ("major", "minor")
                             for r in ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")]

MODELS = {
    "h3": {
        "label": "MINIMAX H3", "kind": "video", "color": "#ff5a1f",
        "desc": "Text / image / reference → video with native audio",
        "accepts": {"image": "first frame (1) · first+last (2) · identity refs (r2v, up to 9)",
                    "video": "motion / camera reference (r2v, up to 3)",
                    "audio": "soundtrack — muxed onto the finished clip",
                    "text": "script / shot list — added to the prompt"},
        "fields": [
            {"k": "mode", "label": "Mode", "type": "select", "def": "auto",
             "opts": [["auto", "auto (refs → r2v, else t2v)"], ["t2v", "text → video"], ["i2v", "image → video (1st picture)"],
                      ["flf2v", "first + last frame (2 pictures)"], ["r2v", "reference → video"]]},
            {"k": "aspect", "label": "Aspect", "type": "select", "def": "auto",
             "opts": [["auto", "auto (picture shape or 16:9)"], "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]},
            {"k": "res", "label": "Resolution", "type": "select", "def": "standard",
             "opts": [["draft", "draft 0.25 MP"], ["standard", "standard 0.4 MP"], ["high", "high 0.6 MP"], ["max", "max 768p 0.98 MP"]]},
            {"k": "seconds", "label": "Length (s)", "type": "number", "def": 5, "min": 4, "max": 15},
            {"k": "quality", "label": "Quality", "type": "select", "def": "turbo8",
             "opts": [["turbo4", "turbo 4-step (fastest)"], ["turbo8", "turbo 8-step"], ["full", "full 20-step (no LoRA, slow)"]]},
            {"k": "steps", "label": "Steps (blank = preset)", "type": "number", "def": "", "min": 1, "max": 60},
            {"k": "sampler", "label": "Sampler", "type": "select", "def": "res_multistep", "opts": H3_SAMPLERS},
            {"k": "scheduler", "label": "Scheduler", "type": "select", "def": "auto", "opts": [["auto", "auto"]] + SCHEDS},
            {"k": "ref_size", "label": "Reference size (r2v)", "type": "select", "def": "max", "opts": ["max", "match"]},
            {"k": "lora_strength", "label": "Turbo LoRA strength", "type": "number", "def": 1.0, "min": 0.0, "max": 1.5, "step": 0.05},
            {"k": "audio", "label": "Native audio", "type": "select", "def": "auto",
             "opts": [["auto", "auto (fitting sound + music)"], ["off", "off (silent)"], ["custom", "custom → text below"]]},
            {"k": "audio_text", "label": "Custom audio description", "type": "text", "def": ""},
            {"k": "soundtrack", "label": "Attached audio", "type": "select", "def": "replace",
             "opts": [["replace", "replace the clip's audio"], ["mix", "mix with native audio"], ["ignore", "ignore"]]},
            {"k": "style", "label": "Style embedding", "type": "select", "def": "none", "opts": [["none", "none"]] + H3_STYLES},
            {"k": "steady", "label": "Steady camera", "type": "select", "def": "on", "opts": ["on", "off"]},
            {"k": "trim", "label": "Trim first N frames", "type": "number", "def": 0, "min": 0, "max": 96},
            {"k": "enhance", "label": "Prompt director", "type": "select", "def": "on",
             "opts": [["on", "on — engine writes SCENE/SHOTS/CAMERA/SOUND"], ["off", "off — my words (= --raw)"]]},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
    "music3": {
        "label": "MINIMAX MUSIC 3.0", "kind": "audio", "color": "#ffc21a",
        "desc": "Full songs with vocals — caption + lyrics, up to 5 min",
        "accepts": {"text": "your lyrics (section tags like [Verse] [Chorus])",
                    "image": "mood reference — the engine looks at it",
                    "video": "mood reference — a frame is described"},
        "fields": [
            {"k": "duration", "label": "Max duration (s)", "type": "number", "def": 120, "min": 10, "max": 300},
            {"k": "lyrics", "label": "Lyrics", "type": "select", "def": "auto",
             "opts": [["auto", "auto — engine writes them"], ["instrumental", "instrumental"]]},
            {"k": "steps", "label": "Diffusion steps", "type": "number", "def": 30, "min": 8, "max": 80},
            {"k": "cfg", "label": "Diffusion CFG", "type": "number", "def": 1.7, "min": 1.0, "max": 6.0, "step": 0.1},
            {"k": "lm_cfg", "label": "Composer CFG", "type": "number", "def": 1.7, "min": 1.0, "max": 6.0, "step": 0.1},
            {"k": "top_k", "label": "Composer top-k", "type": "number", "def": 50, "min": 1, "max": 500},
            {"k": "sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "model", "label": "DiT precision", "type": "select", "def": "fp16", "opts": [["fp16", "fp16 (best)"], ["int8", "int8 (lighter)"]]},
            {"k": "decode", "label": "Decode", "type": "select", "def": "tiled", "opts": [["tiled", "tiled (low VRAM)"], ["full", "full"]]},
            {"k": "quality", "label": "MP3 quality", "type": "select", "def": "V0", "opts": [["V0", "V0 VBR (best)"], "320k", "128k"]},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
    "qimg": {
        "label": "QWEN IMAGE 2.1", "kind": "image", "color": "#1fc8dc",
        "desc": "Text → image · multi-picture edit · background removal",
        "accepts": {"image": "edit inputs (up to 10) — say picture 1, picture 2…",
                    "video": "a frame is grabbed and used as an edit input",
                    "text": "prompt text — added to the prompt"},
        "fields": [
            {"k": "mode", "label": "Mode", "type": "select", "def": "auto",
             "opts": [["auto", "auto (pictures → edit)"], ["generate", "text → image"], ["edit", "edit attached pictures"],
                      ["cutout", "remove background"]]},
            {"k": "aspect", "label": "Aspect", "type": "select", "def": "auto",
             "opts": [["auto", "auto (engine picks)"], "1:1", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4", "4:5", "5:4", "21:9", "2:1", "1:2"]},
            {"k": "size", "label": "Size", "type": "select", "def": "standard",
             "opts": [["standard", "standard ~1 MP"], ["hd", "HD ~2 MP"], ["max", "max ~4 MP (slow)"]]},
            {"k": "steps", "label": "Steps", "type": "number", "def": 25, "min": 4, "max": 60},
            {"k": "cfg", "label": "CFG", "type": "number", "def": 1.0, "min": 1.0, "max": 8.0, "step": 0.1},
            {"k": "sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "enhance", "label": "Prompt rewriter", "type": "select", "def": "on",
             "opts": [["on", "on — official rewriter"], ["off", "off — my words (= --raw)"]]},
            {"k": "edit_res", "label": "Reference resolution", "type": "select", "def": "auto",
             "opts": [["auto", "auto (scales with picture count)"], "512", "768", "1024", "1536"]},
            {"k": "cache", "label": "Feature cache", "type": "select", "def": "auto", "opts": ["auto", "gpu", "cpu", "off"]},
            {"k": "negative", "label": "Negative prompt (CFG > 1)", "type": "text", "def": ""},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
    "ace": {
        "label": "ACE-STEP 1.5", "kind": "audio", "color": "#ff3b5c",
        "desc": "Fast beats & tracks · remix / cover / voice-swap an attached track",
        "accepts": {"audio": "audio 1 = source track · audio 2 = voice/timbre (voice mode)",
                    "text": "your lyrics",
                    "image": "mood reference (text mode)", "video": "mood reference (text mode)"},
        "fields": [
            {"k": "mode", "label": "Mode", "type": "select", "def": "auto",
             "opts": [["auto", "auto (audio → remix, else text)"], ["text", "text → music"], ["remix", "remix attached track"],
                      ["cover", "cover (keep its timbre)"], ["voice", "voice swap (audio 1 song + audio 2 voice)"]]},
            {"k": "duration", "label": "Duration (s, text mode)", "type": "number", "def": 60, "min": 5, "max": 600},
            {"k": "steps", "label": "Steps", "type": "number", "def": 8, "min": 4, "max": 60},
            {"k": "shift", "label": "Shift", "type": "number", "def": 3.0, "min": 1.0, "max": 6.0, "step": 0.5},
            {"k": "cfg", "label": "Diffusion CFG", "type": "number", "def": 1.0, "min": 1.0, "max": 8.0, "step": 0.1},
            {"k": "lm_cfg", "label": "LM CFG", "type": "number", "def": 2.0, "min": 0.0, "max": 10.0, "step": 0.1},
            {"k": "temperature", "label": "LM temperature", "type": "number", "def": 0.85, "min": 0.0, "max": 2.0, "step": 0.05},
            {"k": "top_p", "label": "LM top-p", "type": "number", "def": 0.9, "min": 0.0, "max": 1.0, "step": 0.05},
            {"k": "top_k", "label": "LM top-k (0 = off)", "type": "number", "def": 0, "min": 0, "max": 100},
            {"k": "min_p", "label": "LM min-p", "type": "number", "def": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
            {"k": "codes", "label": "Audio-code LM", "type": "select", "def": "auto",
             "opts": [["auto", "auto (text mode only)"], ["on", "always"], ["off", "never"]]},
            {"k": "bpm", "label": "BPM (blank = auto)", "type": "number", "def": "", "min": 40, "max": 240},
            {"k": "key", "label": "Key", "type": "select", "def": "auto", "opts": KEYS},
            {"k": "timesig", "label": "Time signature", "type": "select", "def": "4", "opts": [["4", "4/4"], ["3", "3/4"], ["6", "6/8"], ["2", "2/4"]]},
            {"k": "language", "label": "Lyrics language", "type": "select", "def": "en",
             "opts": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ru", "ar", "hi", "nl", "sv", "pl", "tr", "unknown"]},
            {"k": "remix", "label": "Remix strength", "type": "number", "def": 0.55, "min": 0.05, "max": 1.0, "step": 0.05},
            {"k": "cover", "label": "Cover strength", "type": "number", "def": 0.75, "min": 0.05, "max": 1.0, "step": 0.05},
            {"k": "voice", "label": "Voice-swap strength", "type": "number", "def": 0.65, "min": 0.3, "max": 0.95, "step": 0.05},
            {"k": "sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "quality", "label": "MP3 quality", "type": "select", "def": "V0", "opts": [["V0", "V0 VBR (best)"], "320k", "128k"]},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
    "llama": {
        "label": "MUSE · LLAMA 3.1 8B", "kind": "text", "color": "#5ee08a",
        "desc": "MUSE, the lab's writer — chat, ideas, lyrics, scripts and prompts for the other engines",
        "accepts": {"text": "notes, drafts or lyrics to work from"},
        "fields": [
            {"k": "mode", "label": "Mode", "type": "select", "def": "chat",
             "opts": [["chat", "general chat (clear, concise)"], ["creative", "creative writing (vivid, original)"]]},
            {"k": "length", "label": "Reply length", "type": "select", "def": "medium",
             "opts": [["short", "short (~300 words)"], ["medium", "medium (~800 words)"], ["long", "long (~2000 words)"]]},
            {"k": "temperature", "label": "Creativity (temperature)", "type": "number", "def": 0.7, "min": 0.0, "max": 1.5, "step": 0.05},
            {"k": "memory", "label": "Conversation memory (turns)", "type": "number", "def": 6, "min": 0, "max": 12},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
}


def _clean(model, saved):
    out = {}
    for f in MODELS[model]["fields"]:
        k, v = f["k"], (saved or {}).get(f["k"], f["def"])
        if f["type"] == "number":
            if v in ("", None):
                v = f["def"]
            if v != "":
                try:
                    v = float(v)
                    v = max(f.get("min", v), min(f.get("max", v), v))
                    if f.get("step") is None:
                        v = int(v)
                except (TypeError, ValueError):
                    v = f["def"]
        elif f["type"] == "select":
            allowed = [o[0] if isinstance(o, list) else o for o in f["opts"]]
            v = str(v) if str(v) in allowed else f["def"]
        else:
            v = str(v)[:1000]
        out[k] = v
    return out


def _store_key(uid):
    return "params" if uid in (None, "owner") else "params_" + uid      # each user has their own ⚙ values


def get(model, override=None, uid="owner"):
    """Saved panel values (this user's) merged over defaults, plus an optional one-run override."""
    saved = dict((core.prefs().get(_store_key(uid)) or {}).get(model) or {})
    if override:
        saved.update({k: v for k, v in override.items() if v is not None})
    return _clean(model, saved)


def save(model, values, uid="owner"):
    key = _store_key(uid)
    p = core.prefs().get(key) or {}
    p[model] = _clean(model, values)
    core.save_pref(key, p)
    return p[model]
