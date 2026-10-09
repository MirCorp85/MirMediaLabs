"""Per-model parameter schemas (the ⚙ button). One schema feeds the web UI and the
Android app; saved values live in data/prefs.json so desktop and phone share them.
Inline --flags typed in a prompt still win over the panel for that one run."""
import core
import param_docs

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
        "desc": "Text / image / reference → video with native audio · extend clips · storyboard · effects",
        "accepts": {"image": "first frame (1) · first+last (2) · storyboard keyframes (2-9) · identity refs (r2v, up to 9)",
                    "video": "motion / camera reference (r2v, up to 3) · a clip to extend",
                    "audio": "soundtrack — muxed onto the finished clip · in sing mode the vocal the mouths follow",
                    "text": "script / shot list — added to the prompt"},
        "fields": [
            # ── basics
            {"k": "mode", "label": "Mode", "type": "select", "def": "auto", "group": "Basics",
             "help": "Attachments are always used: a mode that can't take them switches to one that can.",
             "opts": [["auto", "auto (refs → r2v, else t2v)"], ["t2v", "text → video"], ["i2v", "image → video (1st picture)"],
                      ["flf2v", "first + last frame (2 pictures)"], ["r2v", "reference → video"],
                      ["story", "storyboard — pictures are keyframes (1→2→3…)"],
                      ["extend", "extend the attached clip"],
                      ["sing", "sing / lip-sync to the attached audio (picture or previous clip)"]]},
            {"k": "aspect", "label": "Aspect", "type": "select", "def": "auto", "group": "Basics",
             "opts": [["auto", "auto (picture shape or 16:9)"], "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]},
            {"k": "res", "label": "Resolution", "type": "select", "def": "standard", "group": "Basics",
             "opts": [["draft", "draft 0.25 MP"], ["standard", "standard 0.4 MP"], ["high", "high 0.6 MP"], ["max", "max 768p 0.98 MP"]]},
            {"k": "seconds", "label": "Length per clip (s)", "type": "number", "def": 5, "min": 4, "max": 15, "group": "Basics"},
            {"k": "quality", "label": "Quality", "type": "select", "def": "turbo8", "group": "Basics",
             "opts": [["turbo4", "turbo 4-step (fastest)"], ["turbo8", "turbo 8-step"], ["full", "full 20-step (no LoRA, slow)"]]},
            {"k": "seed", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0, "group": "Basics"},
            # ── extend / storyboard (first frame → last frame chaining)
            {"k": "extend", "label": "Extend: extra clips", "type": "number", "def": 0, "min": 0, "max": 8,
             "group": "Extend & storyboard", "cap": "extend",
             "help": "Each extra clip starts from the end of the one before (its last frames are anchored), then all are "
                     "joined. 5 s + 3 extra ≈ 19 s."},
            {"k": "extend_anchor", "label": "Continuity anchor", "type": "select", "def": "22", "group": "Extend & storyboard",
             "cap": "extend",
             "opts": [["22", "last 22 frames (smooth motion carry-over)"], ["5", "last 5 frames"],
                      ["1", "last frame only (first → last frame)"]]},
            {"k": "extend_prompt", "label": "What happens next (segments split by ||)", "type": "text", "def": "",
             "group": "Extend & storyboard", "cap": "extend",
             "help": "e.g. she turns to the camera || she walks into the sea. Blank = the same action continues."},
            {"k": "story_secs", "label": "Storyboard: seconds between keyframes", "type": "number", "def": 5, "min": 4, "max": 15,
             "group": "Extend & storyboard", "cap": "extend"},
            {"k": "join", "label": "Join clips", "type": "select", "def": "cut", "group": "Extend & storyboard", "cap": "extend",
             "opts": [["cut", "seamless cut (overlap dropped)"], ["xfade", "short crossfade (0.25 s)"]]},
            # ── camera & motion
            {"k": "camera", "label": "Camera move", "type": "select", "def": "auto", "group": "Camera & motion",
             "opts": [["auto", "auto (the director picks)"], ["static", "locked-off static"], ["dolly_in", "slow dolly-in"],
                      ["dolly_out", "dolly-out reveal"], ["orbit", "orbit around the subject"], ["crane_up", "crane up"],
                      ["crane_down", "crane down"], ["tracking", "tracking shot"], ["handheld", "handheld follow"],
                      ["pan_left", "pan left"], ["pan_right", "pan right"], ["tilt_up", "tilt up"], ["zoom_in", "slow zoom-in"],
                      ["fpv", "FPV drone fly-through"], ["aerial", "aerial establishing shot"], ["pov", "first-person POV"]]},
            {"k": "shot", "label": "Shot size", "type": "select", "def": "auto", "group": "Camera & motion",
             "opts": [["auto", "auto"], ["extreme_wide", "extreme wide"], ["wide", "wide"], ["medium", "medium"],
                      ["close", "close-up"], ["extreme_close", "extreme close-up"], ["low_angle", "low angle"],
                      ["high_angle", "high angle"], ["overhead", "top-down overhead"]]},
            {"k": "motion", "label": "Motion amount", "type": "select", "def": "auto", "group": "Camera & motion",
             "opts": [["auto", "auto"], ["subtle", "subtle"], ["natural", "natural"], ["dynamic", "dynamic"],
                      ["extreme", "extreme / action"]]},
            {"k": "steady", "label": "Steady camera", "type": "select", "def": "on", "opts": ["on", "off"], "group": "Camera & motion"},
            {"k": "speed", "label": "Playback speed", "type": "select", "def": "1", "group": "Camera & motion",
             "opts": [["0.5", "0.5× slow motion"], ["0.75", "0.75×"], ["1", "1× normal"], ["1.25", "1.25×"], ["1.5", "1.5×"],
                      ["2", "2× fast"]]},
            # ── scene & effects (written into the prompt as positive descriptions)
            {"k": "look", "label": "Look / style", "type": "select", "def": "auto", "group": "Scene & effects",
             "opts": [["auto", "auto"], ["cinematic", "cinematic film"], ["photoreal", "photoreal phone video"],
                      ["documentary", "documentary"], ["commercial", "glossy commercial"], ["music_video", "music video"],
                      ["anime", "anime"], ["3d", "3D animated"], ["claymation", "claymation"],
                      ["noir", "film noir B&W"], ["vintage", "vintage 16 mm film"], ["vhs", "VHS 90s camcorder"],
                      ["cyberpunk", "cyberpunk neon"], ["watercolor", "watercolour painting"]]},
            {"k": "scene_fx", "label": "Scene effect", "type": "select", "def": "none", "group": "Scene & effects",
             "opts": [["none", "none"], ["rain", "rain"], ["snow", "falling snow"], ["fog", "fog / mist"], ["smoke", "drifting smoke"],
                      ["sparks", "fire sparks / embers"], ["dust", "dust in light beams"], ["petals", "falling petals"],
                      ["confetti", "confetti"], ["lightning", "lightning storm"], ["particles", "glowing magic particles"],
                      ["bubbles", "floating bubbles"], ["underwater", "underwater caustics"], ["explosion", "explosion / debris"],
                      ["timelapse", "timelapse clouds"], ["slowmo", "slow-motion action"]]},
            {"k": "lighting", "label": "Lighting", "type": "select", "def": "auto", "group": "Scene & effects",
             "opts": [["auto", "auto"], ["golden", "golden hour"], ["blue_hour", "blue hour"], ["night", "night, city lights"],
                      ["neon", "neon"], ["studio", "soft studio"], ["harsh", "harsh midday sun"], ["candle", "candlelight"],
                      ["backlit", "backlit rim light"], ["moody", "low-key moody"], ["overcast", "soft overcast"]]},
            {"k": "style", "label": "Style embedding (H3 effect)", "type": "select", "def": "none", "group": "Scene & effects",
             "opts": [["none", "none"]] + H3_STYLES},
            {"k": "fx_text", "label": "Extra scene notes", "type": "text", "def": "", "group": "Scene & effects"},
            # ── post effects (ffmpeg, after the render)
            {"k": "grade", "label": "Colour grade", "type": "select", "def": "none", "group": "Post effects",
             "opts": [["none", "none"], ["warm", "warm"], ["cool", "cool"], ["teal_orange", "teal & orange"],
                      ["bw", "black & white"], ["vintage", "faded vintage"], ["vivid", "vivid"], ["contrast", "high contrast"]]},
            {"k": "grain", "label": "Film grain", "type": "select", "def": "off", "group": "Post effects",
             "opts": [["off", "off"], ["light", "light"], ["heavy", "heavy"]]},
            {"k": "vignette", "label": "Vignette", "type": "select", "def": "off", "opts": ["off", "on"], "group": "Post effects"},
            {"k": "sharpen", "label": "Sharpen", "type": "select", "def": "off", "opts": ["off", "light", "strong"],
             "group": "Post effects"},
            {"k": "fade", "label": "Fade", "type": "select", "def": "none", "group": "Post effects",
             "opts": [["none", "none"], ["in", "fade in"], ["out", "fade out"], ["both", "in + out"]]},
            {"k": "fps", "label": "Frame rate", "type": "select", "def": "24", "group": "Post effects",
             "opts": [["24", "24 fps (native)"], ["30", "30 fps"], ["48", "48 fps smooth (interpolated)"],
                      ["60", "60 fps smooth (interpolated)"]]},
            {"k": "upscale", "label": "Upscale", "type": "select", "def": "off", "group": "Post effects",
             "opts": [["off", "off"], ["1.5", "1.5× (lanczos)"], ["2", "2× (lanczos)"]]},
            {"k": "loop", "label": "Loop", "type": "select", "def": "off", "group": "Post effects",
             "opts": [["off", "off"], ["boomerang", "boomerang (forward + back)"]]},
            # ── audio
            {"k": "audio", "label": "Native audio", "type": "select", "def": "auto", "group": "Audio",
             "opts": [["auto", "auto (fitting sound + music)"], ["off", "off (silent)"], ["custom", "custom → text below"]]},
            {"k": "audio_text", "label": "Custom audio description", "type": "text", "def": "", "group": "Audio"},
            {"k": "soundtrack", "label": "Attached audio", "type": "select", "def": "replace", "group": "Audio",
             "opts": [["replace", "replace the clip's audio"], ["mix", "mix with native audio"], ["ignore", "ignore"]]},
            {"k": "track_vol", "label": "Attached audio volume (mix)", "type": "number", "def": 1.0, "min": 0.0, "max": 2.0,
             "step": 0.05, "group": "Audio"},
            # ── references
            {"k": "ref_role", "label": "Pictures are used as", "type": "select", "def": "identity", "group": "References",
             "opts": [["identity", "identity (faces, people, products)"], ["style", "style / look"],
                      ["scene", "location / scene"], ["all", "everything (identity + outfit + scene)"]]},
            {"k": "ref_size", "label": "Reference size (r2v)", "type": "select", "def": "max", "opts": ["max", "match"],
             "group": "References"},
            {"k": "ref_secs", "label": "Reference clip length (s)", "type": "number", "def": 10, "min": 2, "max": 15,
             "group": "References"},
            # ── engine & sampler
            {"k": "enhance", "label": "Prompt director", "type": "select", "def": "on", "group": "Engine & sampler",
             "opts": [["on", "on — engine writes SCENE/SHOTS/CAMERA/SOUND (sees your pictures)"], ["off", "off — my words (= --raw)"]]},
            {"k": "steps", "label": "Steps (blank = preset)", "type": "number", "def": "", "min": 1, "max": 60,
             "group": "Engine & sampler"},
            {"k": "sampler", "label": "Sampler", "type": "select", "def": "res_multistep", "opts": H3_SAMPLERS,
             "group": "Engine & sampler"},
            {"k": "scheduler", "label": "Scheduler", "type": "select", "def": "auto", "opts": [["auto", "auto"]] + SCHEDS,
             "group": "Engine & sampler"},
            {"k": "lora_strength", "label": "Turbo LoRA strength", "type": "number", "def": 1.0, "min": 0.0, "max": 1.5,
             "step": 0.05, "group": "Engine & sampler"},
            {"k": "shift_video", "label": "Sigma shift · video (blank = model default)", "type": "number", "def": "",
             "min": 0.5, "max": 30.0, "step": 0.5, "group": "Engine & sampler"},
            {"k": "shift_audio", "label": "Sigma shift · audio (blank = model default)", "type": "number", "def": "",
             "min": 0.5, "max": 30.0, "step": 0.5, "group": "Engine & sampler"},
            {"k": "denoise", "label": "Denoise", "type": "number", "def": 1.0, "min": 0.3, "max": 1.0, "step": 0.05,
             "group": "Engine & sampler"},
            {"k": "trim", "label": "Trim first N frames", "type": "number", "def": 0, "min": 0, "max": 96,
             "group": "Engine & sampler"},
            # ── custom ComfyUI workflow (nodes)
            {"k": "workflow", "label": "ComfyUI workflow", "type": "select", "def": "builtin", "group": "Workflow",
             "cap": "workflows", "dyn": "workflows", "opts": [["builtin", "built-in MiniMax H3 graph"]],
             "help": "Your own ComfyUI workflow, exported with Workflow → Export (API). Placeholders: {{prompt}} {{seed}} "
                     "{{width}} {{height}} {{length}} {{seconds}} {{steps}} {{image1}}…{{image9}} {{video1}} {{audio1}}."},
        ]},
    "music3": {
        "label": "MINIMAX MUSIC 3.0", "kind": "audio", "color": "#ffc21a",
        "desc": "Full songs with vocals — caption + lyrics, up to 5 min",
        "accepts": {"text": "your lyrics (section tags like [Verse] [Chorus])",
                    "image": "mood reference — the engine looks at it",
                    "video": "mood reference — a frame is described"},
        "fields": [
            {"k": "duration", "group": "Basics", "label": "Max duration (s)", "type": "number", "def": 120, "min": 10, "max": 300},
            {"k": "lyrics", "group": "Basics", "label": "Lyrics", "type": "select", "def": "auto",
             "opts": [["auto", "auto — engine writes them"], ["instrumental", "instrumental"]]},
            {"k": "steps", "group": "Engine & sampler", "label": "Diffusion steps", "type": "number", "def": 30, "min": 8, "max": 80},
            {"k": "cfg", "group": "Engine & sampler", "label": "Diffusion CFG", "type": "number", "def": 1.7, "min": 1.0, "max": 6.0, "step": 0.1},
            {"k": "lm_cfg", "group": "Engine & sampler", "label": "Composer CFG", "type": "number", "def": 1.7, "min": 1.0, "max": 6.0, "step": 0.1},
            {"k": "top_k", "group": "Engine & sampler", "label": "Composer top-k", "type": "number", "def": 50, "min": 1, "max": 500},
            {"k": "sampler", "group": "Engine & sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "group": "Engine & sampler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "model", "group": "Engine & sampler", "label": "DiT precision", "type": "select", "def": "fp16", "opts": [["fp16", "fp16 (best)"], ["int8", "int8 (lighter)"]]},
            {"k": "decode", "group": "Engine & sampler", "label": "Decode", "type": "select", "def": "tiled", "opts": [["tiled", "tiled (low VRAM)"], ["full", "full"]]},
            {"k": "quality", "group": "Basics", "label": "MP3 quality", "type": "select", "def": "V0", "opts": [["V0", "V0 VBR (best)"], "320k", "128k"]},
            {"k": "seed", "group": "Basics", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
            {"k": "workflow", "label": "ComfyUI workflow", "type": "select", "def": "builtin", "group": "Workflow",
             "cap": "workflows", "dyn": "workflows", "opts": [["builtin", "built-in Music 3 graph"]]},
        ]},
    "qimg": {
        "label": "QWEN IMAGE 2.1", "kind": "image", "color": "#1fc8dc",
        "desc": "Text → image · multi-picture edit · background removal",
        "accepts": {"image": "edit inputs (up to 10) — say picture 1, picture 2…",
                    "video": "a frame is grabbed and used as an edit input",
                    "text": "prompt text — added to the prompt"},
        "fields": [
            {"k": "mode", "group": "Basics", "label": "Mode", "type": "select", "def": "auto",
             "opts": [["auto", "auto (pictures → edit)"], ["generate", "text → image"], ["edit", "edit attached pictures"],
                      ["cutout", "remove background"]]},
            {"k": "aspect", "group": "Basics", "label": "Aspect", "type": "select", "def": "auto",
             "opts": [["auto", "auto (engine picks)"], "1:1", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4", "4:5", "5:4", "21:9", "2:1", "1:2"]},
            {"k": "size", "group": "Basics", "label": "Size", "type": "select", "def": "standard",
             "opts": [["standard", "standard ~1 MP"], ["hd", "HD ~2 MP"], ["max", "max ~4 MP (slow)"]]},
            {"k": "steps", "group": "Engine & sampler", "label": "Steps", "type": "number", "def": 25, "min": 4, "max": 60},
            {"k": "cfg", "group": "Engine & sampler", "label": "CFG", "type": "number", "def": 1.0, "min": 1.0, "max": 8.0, "step": 0.1},
            {"k": "sampler", "group": "Engine & sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "group": "Engine & sampler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "enhance", "group": "Basics", "label": "Prompt rewriter", "type": "select", "def": "on",
             "opts": [["on", "on — official rewriter"], ["off", "off — my words (= --raw)"]]},
            {"k": "edit_res", "group": "Engine & sampler", "label": "Reference resolution", "type": "select", "def": "auto",
             "opts": [["auto", "auto (scales with picture count)"], "512", "768", "1024", "1536"]},
            {"k": "cache", "group": "Engine & sampler", "label": "Feature cache", "type": "select", "def": "auto", "opts": ["auto", "gpu", "cpu", "off"]},
            {"k": "negative", "group": "Basics", "label": "Negative prompt (CFG > 1)", "type": "text", "def": ""},
            {"k": "seed", "group": "Basics", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
            {"k": "upscale", "label": "Upscale", "type": "select", "def": "off", "group": "Post effects",
             "opts": [["off", "off"], ["1.5", "1.5× (lanczos)"], ["2", "2× (lanczos)"]]},
            {"k": "workflow", "label": "ComfyUI workflow", "type": "select", "def": "builtin", "group": "Workflow",
             "cap": "workflows", "dyn": "workflows", "opts": [["builtin", "built-in Qwen-Image graph"]]},
        ]},
    "ace": {
        "label": "ACE-STEP 1.5", "kind": "audio", "color": "#ff3b5c",
        "desc": "Fast beats & tracks · remix / cover / voice-swap an attached track",
        "accepts": {"audio": "audio 1 = source track · audio 2 = voice/timbre (voice mode)",
                    "text": "your lyrics",
                    "image": "mood reference (text mode)", "video": "mood reference (text mode)"},
        "fields": [
            {"k": "mode", "group": "Basics", "label": "Mode", "type": "select", "def": "auto",
             "opts": [["auto", "auto (audio → remix, else text)"], ["text", "text → music"], ["remix", "remix attached track"],
                      ["cover", "cover (keep its timbre)"], ["voice", "voice swap (audio 1 song + audio 2 voice)"]]},
            {"k": "duration", "group": "Basics", "label": "Duration (s, text mode)", "type": "number", "def": 60, "min": 5, "max": 600},
            {"k": "steps", "group": "Engine & sampler", "label": "Steps", "type": "number", "def": 8, "min": 4, "max": 60},
            {"k": "shift", "group": "Engine & sampler", "label": "Shift", "type": "number", "def": 3.0, "min": 1.0, "max": 6.0, "step": 0.5},
            {"k": "cfg", "group": "Engine & sampler", "label": "Diffusion CFG", "type": "number", "def": 1.0, "min": 1.0, "max": 8.0, "step": 0.1},
            {"k": "lm_cfg", "group": "Engine & sampler", "label": "LM CFG", "type": "number", "def": 2.0, "min": 0.0, "max": 10.0, "step": 0.1},
            {"k": "temperature", "group": "Engine & sampler", "label": "LM temperature", "type": "number", "def": 0.85, "min": 0.0, "max": 2.0, "step": 0.05},
            {"k": "top_p", "group": "Engine & sampler", "label": "LM top-p", "type": "number", "def": 0.9, "min": 0.0, "max": 1.0, "step": 0.05},
            {"k": "top_k", "group": "Engine & sampler", "label": "LM top-k (0 = off)", "type": "number", "def": 0, "min": 0, "max": 100},
            {"k": "min_p", "group": "Engine & sampler", "label": "LM min-p", "type": "number", "def": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
            {"k": "codes", "group": "Engine & sampler", "label": "Audio-code LM", "type": "select", "def": "auto",
             "opts": [["auto", "auto (text mode only)"], ["on", "always"], ["off", "never"]]},
            {"k": "bpm", "group": "Basics", "label": "BPM (blank = auto)", "type": "number", "def": "", "min": 40, "max": 240},
            {"k": "key", "group": "Basics", "label": "Key", "type": "select", "def": "auto", "opts": KEYS},
            {"k": "timesig", "group": "Basics", "label": "Time signature", "type": "select", "def": "4", "opts": [["4", "4/4"], ["3", "3/4"], ["6", "6/8"], ["2", "2/4"]]},
            {"k": "language", "group": "Basics", "label": "Lyrics language", "type": "select", "def": "en",
             "opts": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ru", "ar", "hi", "nl", "sv", "pl", "tr", "unknown"]},
            {"k": "remix", "group": "Basics", "label": "Remix strength", "type": "number", "def": 0.55, "min": 0.05, "max": 1.0, "step": 0.05},
            {"k": "cover", "group": "Basics", "label": "Cover strength", "type": "number", "def": 0.75, "min": 0.05, "max": 1.0, "step": 0.05},
            {"k": "voice", "group": "Basics", "label": "Voice-swap strength", "type": "number", "def": 0.65, "min": 0.3, "max": 0.95, "step": 0.05},
            {"k": "sampler", "group": "Engine & sampler", "label": "Sampler", "type": "select", "def": "euler", "opts": SAMPLERS},
            {"k": "scheduler", "group": "Engine & sampler", "label": "Scheduler", "type": "select", "def": "simple", "opts": SCHEDS},
            {"k": "quality", "group": "Basics", "label": "MP3 quality", "type": "select", "def": "V0", "opts": [["V0", "V0 VBR (best)"], "320k", "128k"]},
            {"k": "seed", "group": "Basics", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
            {"k": "workflow", "label": "ComfyUI workflow", "type": "select", "def": "builtin", "group": "Workflow",
             "cap": "workflows", "dyn": "workflows", "opts": [["builtin", "built-in ACE-Step graph"]]},
        ]},
    "llama": {
        "label": "MUSE · GEMMA 4 12B", "kind": "text", "color": "#5ee08a",
        "desc": "MUSE, the lab's writer — chat, ideas, lyrics, scripts and prompts for the other engines",
        "accepts": {"text": "notes, drafts or lyrics to work from"},
        "fields": [
            {"k": "mode", "group": "Basics", "label": "Mode", "type": "select", "def": "chat",
             "opts": [["chat", "general chat (clear, concise)"], ["creative", "creative writing (vivid, original)"]]},
            {"k": "length", "group": "Basics", "label": "Reply length", "type": "select", "def": "medium",
             "opts": [["short", "short (~300 words)"], ["medium", "medium (~800 words)"], ["long", "long (~2000 words)"]]},
            {"k": "temperature", "group": "Engine & sampler", "label": "Creativity (temperature)", "type": "number", "def": 0.7, "min": 0.0, "max": 1.5, "step": 0.05},
            {"k": "memory", "group": "Basics", "label": "Conversation memory (turns)", "type": "number", "def": 6, "min": 0, "max": 12},
            {"k": "seed", "group": "Basics", "label": "Seed (blank = random)", "type": "number", "def": "", "min": 0},
        ]},
}


LOCK = None        # set by the server: LOCK(uid) → True = this person may not use custom ⚙ values (defaults only)
WORKFLOWS = None   # set by the server: WORKFLOWS(model) → [[id, label], …] (custom ComfyUI workflows)


def fields(model):
    """The model's fields with dynamic options (custom workflows) filled in."""
    out = []
    for f in MODELS[model]["fields"]:
        if f.get("dyn") == "workflows" and WORKFLOWS:
            try:
                f = dict(f, opts=list(f["opts"]) + [o for o in WORKFLOWS(model) if o[0] != "builtin"])
            except Exception:
                pass
        out.append(f)
    return out


def schema(model, caps=None):
    """What the ⚙ panels show. Fields that need a feature the person doesn't have are left out."""
    fs = [param_docs.apply(model, f) for f in fields(model) if caps is None or not f.get("cap") or f["cap"] in caps]
    adv = [f for f in fs if f.get("advanced")]          # expert knobs last, in their own folded group
    return dict(MODELS[model], fields=[f for f in fs if not f.get("advanced")] + adv)


def _clean(model, saved):
    out = {}
    for f in fields(model):
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
    if LOCK and LOCK(uid):
        saved = {}                          # no "Custom parameters" right: the defaults, whatever was saved before
    if override:
        saved.update({k: v for k, v in override.items() if v is not None})
    return _clean(model, saved)


def save(model, values, uid="owner"):
    key = _store_key(uid)
    p = core.prefs().get(key) or {}
    p[model] = _clean(model, values)
    core.save_pref(key, p)
    return p[model]
