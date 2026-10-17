"""The four generators. Graph logic is ported from MirOS (same verified node graphs),
re-homed so every input comes from data/refs and every output lands in data/library.

Each run_<model>(job) reads job['prompt'], job['refs'] (names in data/refs) and
job['params'] (resolved ⚙ values) and returns {"files": [...], "text": summary}.
"""
import json
import os
import re
import subprocess
import time

import comfy
import core
import params
import prompts
import console
import workflows

# ── shared helpers ─────────────────────────────────────────────────────────


def log(job, msg):
    job["log"] = (job.get("log") or "") + msg + "\n"
    job["stage"] = msg
    console.emit(_SRC.get(job.get("model"), "LAB"), msg, job)


def guide_note(job, key, c):
    """Log where the panel differs from the official Comfy guide's recommended settings — advisory only,
    the user's panel/saved-mode values always render."""
    diff = ["%s %s (guide %s)" % (k, c.get(k), v) for k, v in prompts.settings_for(key).items()
            if k in c and str(c.get(k)) != str(v)]
    if diff:
        job["log"] = (job.get("log") or "") + "official guide differs: " + ", ".join(diff) + "\n"


_SRC = {"h3": "VID", "music3": "SONG", "qimg": "IMG", "ace": "SONG", "llama": "MirAI"}


def _purge_frames():
    """Grabbed stills (_frame_*) are per-render scratch: drop ones older than 6 h."""
    try:
        for n in os.listdir(core.REFS):
            p = os.path.join(core.REFS, n)
            if n.startswith(("_frame_", "_prep_")) and time.time() - os.path.getmtime(p) > 6 * 3600:
                os.remove(p)
    except OSError:
        pass


def split_refs(job):
    _purge_frames()
    out = {"image": [], "video": [], "audio": [], "text": []}
    for n in (job.get("refs") or [])[:16]:
        p = core.in_dir(core.REFS, n)
        if not p or not os.path.isfile(p):      # never quietly render without what the person attached
            raise RuntimeError("the attachment %s is no longer on the lab — attach it again" % n.split("_", 2)[-1])
        k = core.kind_of(n)
        if k:
            out[k].append(p)
    if any(out.values()):
        log(job, "attachments: " + " · ".join("%d %s%s" % (len(v), k, "" if len(v) == 1 else "s") for k, v in out.items() if v))
    return out


def attached_text(paths):
    return "\n\n".join(t for t in (core.read_text(p) for p in paths) if t)


def ffmpeg(args, timeout=300):
    if not os.path.isfile(core.FFMPEG):
        raise RuntimeError("ffmpeg not found at %s" % core.FFMPEG)
    r = subprocess.run([core.FFMPEG, "-y", "-v", "error"] + args, capture_output=True, text=True,
                       timeout=timeout, creationflags=core.NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: %s" % (r.stderr or "")[-300:])


def video_frame(path, at=1.0):
    """Grab one still from a clip (for image-only models)."""
    out = os.path.join(core.REFS, "_frame_%d.png" % int(time.time() * 1000))
    try:
        core.still(path, out, at=at)
    except RuntimeError:
        core.still(path, out)                  # clip shorter than `at`
    return out


def media_seconds(path):
    try:
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                           timeout=30, creationflags=core.NO_WINDOW)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def describe(paths, job):
    """Vision engine → one mood sentence per picture (music models can't see images)."""
    if not paths:
        return ""
    if not core.can_see():       # no vision engine installed at all (MirAI / Llama 3.1): no guessing about pictures it can't see
        log(job, "engine can't see pictures — reference picture%s skipped for the mood" % ("" if len(paths) == 1 else "s"))
        return ""
    log(job, "engine looking at %d reference picture%s …" % (len(paths), "" if len(paths) == 1 else "s"))
    try:
        imgs = [prompts._b64(p, 640) for p in paths[:4]]
        return core.ask("Describe the mood, atmosphere, colours and story of these pictures in 2 sentences, "
                        "as inspiration for a piece of music. No preamble.", "You are a concise art director.",
                        timeout=180, images=imgs)
    except Exception:
        return ""


def seed_of(v):
    try:
        s = int(v)
        if s >= 0:
            return s
    except (TypeError, ValueError):
        pass
    return int(time.time() * 1000) % 2 ** 31


def save(entry, prefix, ext, job, extra=None):
    name = core.new_name(prefix, ext)
    comfy.fetch(entry, os.path.join(core.LIB, name))
    meta = {"model": job["model"], "prompt": (job.get("prompt") or "")[:2000], "job": job["id"], "created": time.time(),
            "user": job.get("user") or "owner"}
    if job.get("session"):                          # the chat session (project) it was asked for in
        meta["session"] = job["session"]
    meta.update(extra or {})
    core.index_add(name, meta)
    return name


def prepare_gpu(job):
    log(job, "freeing VRAM …")
    core.render_lock(job.get("id", ""))      # render priority: no AI model may load until this job ends
    core.evict_ollama()
    comfy.ensure()
    comfy.free()


def flag(text, pat, cast=str):
    """Pull one --flag value out of the prompt → (value|None, text)."""
    m = re.search(pat, text, re.I)
    if not m:
        return None, text
    return cast(m.group(1)), (text[:m.start()] + text[m.end():])


def music_len(raw):
    """Length for the music engines from plain words when no --Ns flag was given: '45 sec', '2 min', '1:30', or a bare
    '40s' standing alone between commas ('80s synthwave' stays a decade). → (seconds|None, text)."""
    for pat, mul in ((r"\b(\d{1,3})\s*(?:sec|secs|second|seconds)\b", 1),
                     (r"\b(\d{1,2})\s*(?:min|mins|minute|minutes)\b", 60),
                     (r"(?:^|(?<=,))\s*(\d{1,3})\s*s\s*(?=,|$)", 1)):
        v, out = flag(raw, pat, float)
        if v:
            if "sec" not in pat and mul == 1 and v in (20, 30, 40, 50, 60, 70, 80, 90):
                return v, raw             # ", 90s" may also mean the decade: use it as length, keep the word as style
            return v * mul, out
    m = re.search(r"\b(\d{1,2}):([0-5]\d)\b(?!\s*(?:am|pm))", raw, re.I)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)), raw[:m.start()] + raw[m.end():]
    return None, raw


# ══ MINIMAX H3 — video + native audio ══════════════════════════════════════
def song_meta(caption, lyrics):
    """Tempo / key / style out of a song description, so the next pipeline step can keep them."""
    m = re.search(r"\b(\d{2,3})\s*BPM\b", caption or "", re.I)
    k = re.search(r"\b([A-G])(?:[- ]?(flat|sharp)|([#b]))?\s+(major|minor)\b", caption or "")
    key = None
    if k:
        acc = {"flat": "b", "sharp": "#"}.get((k.group(2) or "").lower(), k.group(3) or "")
        key = "%s%s %s" % (k.group(1), acc, k.group(4).lower())
    style = re.sub(r"(?m)^(Global Metadata|Vocal Details|Arrangement):\s*", "", (caption or "").strip())
    style = " ".join(style.split("\n")[:2])[:500]
    return {"lyrics": lyrics, "style": style, "bpm": int(m.group(1)) if m else None, "key": key}


H3 = {"unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
      "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
      "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
      "r2v_unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
      "r2v_lora": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
      "cn_patch": "minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors",
      "sam3": "sam3.1_multiplex_fp16.safetensors"}
H3_REF_MODES = ("r2v", "keyframes", "control")          # modes that run on MiniMaxH3ReferenceToVideo
H3_FLF_LORA = {"turbo4": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
               "turbo8": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"}
core.apply_model_overrides(H3)
core.apply_model_overrides(H3_FLF_LORA)
H3_ASPECTS = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "21:9": 21 / 9}
H3_RES = {"draft": 0.25, "standard": 0.4, "high": 0.6, "max": 0.98}
H3_STEPS = {"turbo4": 4, "turbo8": 8, "full": 20}
H3_SHORT = {"vertical": ("aspect", "9:16"), "portrait": ("aspect", "9:16"), "square": ("aspect", "1:1"),
            "landscape": ("aspect", "16:9"), "wide": ("aspect", "16:9"), "cinema": ("aspect", "21:9"),
            "silent": ("audio", "off"), "mute": ("audio", "off"), "fast": ("quality", "turbo4"),
            "turbo4": ("quality", "turbo4"), "turbo8": ("quality", "turbo8"), "full": ("quality", "full"),
            "best": ("quality", "full"), "draft": ("res", "draft"), "hd": ("res", "high"), "max768": ("res", "max"),
            "t2v": ("mode", "t2v"), "i2v": ("mode", "i2v"), "sing": ("mode", "sing"), "lipsync": ("mode", "sing"), "flf2v": ("mode", "flf2v"), "r2v": ("mode", "r2v"),
            "raw": ("enhance", "off"), "handheld": ("steady", "off"), "story": ("mode", "story"),
            "storyboard": ("mode", "story"), "slowmo": ("speed", "0.5"), "smooth": ("fps", "60"), "boomerang": ("loop", "boomerang"),
            "bw": ("grade", "bw"), "grain": ("grain", "light"), "xfade": ("join", "xfade")}
H3_VALUE = {"seconds", "aspect", "res", "quality", "steps", "sampler", "scheduler", "seed", "style", "trim", "mode",
            "lora_strength", "ref_size", "extend", "extend_anchor", "story_secs", "camera", "shot", "motion", "look", "scene_fx",
            "lighting", "grade", "fps", "speed", "upscale", "fade", "shift_video", "shift_audio", "denoise", "ref_role",
            "lip", "sing_max"}
DUR_WORD = r"(?<![-–\d.:])\b(\d{1,2})\s*(s|sec|secs|second|seconds)\b(?!\s*[-–)])"


def h3_settings(raw, cfg):
    """Panel values (cfg) < words in the prompt (only where the panel is still default) < --flags."""
    flags, keep, pos = {}, [], 0
    for m in re.finditer(r'--([A-Za-z_0-9]+)(?:[= ]("[^"]*"|[^\s,-][^\s,]*))?', raw):
        keep.append(raw[pos:m.start()])
        pos = m.end()
        k, v = m.group(1).lower(), m.group(2)
        d = re.fullmatch(r"(\d{1,2})s", k)
        if d:
            flags["seconds"] = d.group(1)
            if v:
                keep.append(" " + v)
        elif k in H3_SHORT:
            flags[H3_SHORT[k][0]] = H3_SHORT[k][1]
            if v:
                keep.append(" " + v)
        elif k in H3_VALUE and v:
            flags[k] = v.strip('"')
        elif v:
            keep.append(" " + v)       # unknown --word: drop the flag, keep the prompt text after it
    keep.append(raw[pos:])
    text = "".join(keep)
    words = {}
    if re.match(r"^\s*animate\b[:,]?", text, re.I):
        words["mode"] = "i2v"
        text = re.sub(r"^\s*animate\b[:,]?\s*", "", text, flags=re.I)
    if re.search(r"\b(vertical|portrait|9:16|reel|tiktok|story)\b", text, re.I):
        words["aspect"] = "9:16"
    elif re.search(r"\b(square|1:1)\b", text, re.I):
        words["aspect"] = "1:1"
    elif re.search(r"\b(widescreen|16:9)\b", text, re.I):
        words["aspect"] = "16:9"
    m = re.search(DUR_WORD, text, re.I)
    if m:
        words["seconds"] = m.group(1)
        text = re.sub(DUR_WORD + r"( long)?", "", text, count=1, flags=re.I)
    defaults = {f["k"]: f["def"] for f in params.MODELS["h3"]["fields"]}
    merged = dict(cfg)
    for k, v in words.items():
        if str(cfg.get(k)) == str(defaults.get(k)):
            merged[k] = v
    merged.update(flags)
    c = params._clean("h3", merged)
    q = c["quality"]
    c["mp"] = H3_RES[c["res"]]
    c["steps"] = int(c["steps"]) if c["steps"] != "" else H3_STEPS[q]
    return core.clean_ws(text), c


def h3_dims(mp, aspect):
    ar = H3_ASPECTS[aspect]
    w = (mp * 1_000_000 * ar) ** 0.5
    return max(256, int(round(w / 32)) * 32), max(256, int(round(w / ar / 32)) * 32)


def h3_frames(secs):
    n = max(5, round(secs * 24))
    return n + (5 - n % 17) % 17          # H3's 17k+5 frame grid @ 24 fps


def aspect_of(media, default):
    """Nearest H3 aspect of a picture OR clip, upright (phone EXIF / rotation applied). ffmpeg — no Pillow."""
    wh = core.media_size(media)
    if not wh or not wh[1]:
        return default
    return min(H3_ASPECTS, key=lambda a: abs(H3_ASPECTS[a] - wh[0] / wh[1]))


H3_CAMERA = {"static": "a locked-off static shot", "dolly_in": "a slow dolly-in toward the subject",
             "dolly_out": "a slow dolly-out that reveals the surroundings", "orbit": "a smooth orbit around the subject",
             "crane_up": "a crane up reveal", "crane_down": "a crane down from above", "tracking": "a tracking shot that follows the subject",
             "handheld": "a handheld follow shot with natural sway", "pan_left": "a slow pan to the left",
             "pan_right": "a slow pan to the right", "tilt_up": "a tilt up from the ground to the sky", "zoom_in": "a slow zoom-in",
             "fpv": "an FPV drone fly-through", "aerial": "an aerial establishing shot", "pov": "a first-person POV shot"}
H3_SHOT = {"extreme_wide": "extreme wide shot", "wide": "wide shot", "medium": "medium shot", "close": "close-up",
           "extreme_close": "extreme close-up", "low_angle": "low-angle shot", "high_angle": "high-angle shot",
           "overhead": "top-down overhead shot"}
H3_MOTION = {"subtle": "Movement is subtle and gentle.", "natural": "Movement is natural and realistic.",
             "dynamic": "Movement is dynamic and energetic.", "extreme": "Fast, intense, high-action movement."}
H3_LOOK = {"cinematic": "Cinematic film look, shallow depth of field, anamorphic feel.",
           "photoreal": "Photorealistic smartphone video, natural colours.", "documentary": "Documentary look, natural light, observational.",
           "commercial": "Glossy high-end commercial look, crisp and polished.", "music_video": "Stylised music-video look, bold colours.",
           "anime": "Anime style, clean line art, cel shading.", "3d": "Stylised 3D animated film look, soft global illumination.",
           "claymation": "Claymation stop-motion look, handmade clay textures.", "noir": "Black-and-white film noir, hard shadows.",
           "vintage": "Vintage 16 mm film look, warm faded colours, soft grain.", "vhs": "1990s VHS camcorder look, soft and slightly smeared.",
           "cyberpunk": "Cyberpunk look, neon magenta and cyan, wet reflective streets.",
           "watercolor": "Animated watercolour painting, soft bleeding pigments on paper."}
H3_FX = {"rain": "Rain falls steadily through the scene.", "snow": "Snow falls softly through the air.",
         "fog": "Thin fog drifts through the scene.", "smoke": "Smoke drifts slowly through the light.",
         "sparks": "Glowing fire sparks and embers float upward.", "dust": "Dust motes glitter in beams of light.",
         "petals": "Flower petals drift down through the frame.", "confetti": "Colourful confetti rains down.",
         "lightning": "Lightning flashes across a stormy sky.", "particles": "Glowing magic particles swirl around the subject.",
         "bubbles": "Iridescent bubbles float through the air.", "underwater": "Underwater, with rippling light caustics.",
         "explosion": "A burst of debris and fire erupts in the background.", "timelapse": "Clouds race across the sky in timelapse.",
         "slowmo": "The action unfolds in dramatic slow motion."}
H3_LIGHT = {"golden": "Warm golden-hour sunlight.", "blue_hour": "Cool blue-hour twilight.", "night": "Night, lit by city lights.",
            "neon": "Neon lighting in saturated colours.", "studio": "Soft, even studio lighting.", "harsh": "Harsh midday sun, crisp shadows.",
            "candle": "Warm flickering candlelight.", "backlit": "Strong backlight with a glowing rim around the subject.",
            "moody": "Low-key moody lighting, deep shadows.", "overcast": "Soft overcast daylight."}
H3_REF_ROLE = {
    "identity": "Use {p} as the visual references for the exact identity and appearance of the subjects (match faces, hair "
                "and features precisely; treat them as subject references, not as the background or pose).",
    "style": "Use {p} as the reference for the visual style, colour palette and look only — not for the people or the layout.",
    "scene": "Use {p} as the reference for the location and setting.",
    "all": "Use {p} as the references for the subjects, their outfits and the setting — match all of them closely."}


def h3_direction(c):
    """The ⚙ camera / look / scene choices as positive sentences (H3 has no negative branch)."""
    out = []
    if c.get("shot", "auto") in H3_SHOT or c.get("camera", "auto") in H3_CAMERA:
        out.append("Camera: %s%s." % (H3_SHOT.get(c.get("shot"), ""), ((", " if c.get("shot") in H3_SHOT else "")
                                                                     + H3_CAMERA[c["camera"]]) if c.get("camera") in H3_CAMERA else ""))
    for table, k in ((H3_MOTION, "motion"), (H3_LOOK, "look"), (H3_LIGHT, "lighting"), (H3_FX, "scene_fx")):
        if c.get(k) in table:
            out.append(table[c[k]])
    if str(c.get("fx_text") or "").strip():
        out.append(str(c["fx_text"]).strip().rstrip(".") + ".")
    return " ".join(out)


def mask_nodes(frames, c, p="msk"):
    """SAM3.1 text-prompted subject masks for every frame (official 'Video Segment (SAM3)' recipe) → grown + feathered.
    The last node is <p>f (MASK batch, 1 = regenerate)."""
    grow, fe = int(c.get("mask_grow") or 0), int(c.get("mask_feather") or 0)
    return {p + "m": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": H3["sam3"]}},
            p + "t": {"class_type": "CLIPTextEncode", "inputs": {"clip": [p + "m", 1], "text": str(c.get("mask_what") or "person")[:120]}},
            p + "d": {"class_type": "SAM3_Detect", "inputs": {"model": [p + "m", 0], "image": frames, "conditioning": [p + "t", 0],
                                                            "threshold": 0.5, "refine_iterations": 2, "individual_masks": False}},
            p + "g": {"class_type": "GrowMask", "inputs": {"mask": [p + "d", 0], "expand": grow, "tapered_corners": True}},
            p + "f": {"class_type": "FeatherMask", "inputs": {"mask": [p + "g", 0], "left": fe, "top": fe, "right": fe, "bottom": fe}}}


def control_preview(ref_path, c, job):
    """Pose Preview: what H3 motion control will follow (SDPose stick figures or Canny edges), no H3 render.
    Source | control side by side, 12 fps, up to 10 s → library mp4 name."""
    src = _tmp("ctlprev_src")
    ffmpeg(["-i", ref_path, "-t", "10", "-vf", "scale=480:-2,fps=12", "-an", "-c:v", "libx264", "-crf", "18",
            "-pix_fmt", "yuv420p", src], 120)
    g = {"v": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(src)}},
         "vc": {"class_type": "GetVideoComponents", "inputs": {"video": ["v", 0]}}}
    what = c.get("control") if c.get("control") in ("pose", "canny") else "pose"
    if what == "pose":
        g["pm"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}}
        g["dm"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors", "weight_dtype": "default"}}
        g["det"] = {"class_type": "RTDETR_detect", "inputs": {"model": ["dm", 0], "image": ["vc", 0], "threshold": 0.5,
                    "class_name": "person", "max_detections": int(c.get("control_people") or 2)}}
        g["kp"] = {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["pm", 0], "vae": ["pm", 2], "image": ["vc", 0],
                   "batch_size": 16, "bboxes": ["det", 0]}}
        g["out"] = {"class_type": "SDPoseDrawKeypoints", "inputs": {"keypoints": ["kp", 0], "draw_body": True, "draw_hands": True,
                    "draw_face": True, "draw_feet": True, "stick_width": 4, "face_point_size": 2, "score_threshold": 0.5, "draw_head": True}}
    else:
        g["out"] = {"class_type": "Canny", "inputs": {"image": ["vc", 0], "low_threshold": 0.4, "high_threshold": 0.8}}
    g["cv"] = {"class_type": "CreateVideo", "inputs": {"images": ["out", 0], "fps": 12}}
    g["save"] = {"class_type": "SaveVideo", "inputs": {"video": ["cv", 0], "filename_prefix": comfy.OUT_PREFIX + "/ctlprev",
                                                       "format": "auto", "codec": "auto"}}
    entry, _ = comfy.run(g, "video", job, 15 * 60)
    m = _tmp("ctlprev_m")
    comfy.fetch(entry, m)
    name = core.new_name("posecheck", ".mp4")
    ffmpeg(["-i", src, "-i", m, "-filter_complex", "[1:v][0:v]scale2ref[c][s];[s][c]hstack=inputs=2,format=yuv420p[o]",
            "-map", "[o]", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", os.path.join(core.LIB, name)], 300)
    core.index_add(name, {"model": "h3", "prompt": "pose preview (%s)" % what, "job": job["id"], "created": time.time(),
                          "user": job.get("user") or "owner", **({"session": job["session"]} if job.get("session") else {})})
    for p_ in (src, m):
        try:
            os.remove(p_)
        except OSError:
            pass
    return name


def mask_preview(ref_path, c, job):
    """Fast check of WHO gets replaced: SAM3 only (no H3), the mask tinted over the clip → mp4 path."""
    w, h = 480, 0
    src = _tmp("mskprev_src")
    ffmpeg(["-i", ref_path, "-t", "6", "-vf", "scale=480:-2,fps=12", "-an", "-c:v", "libx264", "-crf", "18",
            "-pix_fmt", "yuv420p", src], 120)
    g = {"v": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(src)}},
         "vc": {"class_type": "GetVideoComponents", "inputs": {"video": ["v", 0]}}}
    g.update(mask_nodes(["vc", 0], c))
    g["mi"] = {"class_type": "MaskToImage", "inputs": {"mask": ["mskf", 0]}}
    g["mv"] = {"class_type": "CreateVideo", "inputs": {"images": ["mi", 0], "fps": 12}}
    g["save"] = {"class_type": "SaveVideo", "inputs": {"video": ["mv", 0], "filename_prefix": comfy.OUT_PREFIX + "/maskprev",
                                                       "format": "auto", "codec": "auto"}}
    entry, _ = comfy.run(g, "video", job, 15 * 60)
    m = _tmp("mskprev_m")
    comfy.fetch(entry, m)
    name = core.new_name("maskcheck", ".mp4")
    out = os.path.join(core.LIB, name)
    ffmpeg(["-i", src, "-i", m, "-filter_complex",
            "[1:v][0:v]scale2ref[mk][base];[mk]format=gray,lut=y=val*0.6[a];"
            "color=c=0xff2040:s=16x16[c];[c][base]scale2ref[cr][b2];[cr][a]alphamerge[red];"
            "[b2][red]overlay=shortest=1,format=yuv420p[o]", "-map", "[o]", "-c:v", "libx264",
            "-crf", "20", "-movflags", "+faststart", out], 300)
    for p_ in (src, m):
        try:
            os.remove(p_)
        except OSError:
            pass
    return name


def h3_graph(cond_node, unet, lora, c, seed, sched, silent, guide=None, cn=None):
    g = dict(cond_node)
    g["unet"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
    model = ["unet", 0]
    if lora and c["lora_strength"] > 0:
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": lora,
                                                                     "strength_model": c["lora_strength"]}}
        model = ["lora", 0]
    if c.get("shift_video") not in ("", None) or c.get("shift_audio") not in ("", None):
        g["shift"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": model,
                      "shift_video": float(c["shift_video"]) if c.get("shift_video") not in ("", None) else 12.0,
                      "shift_audio": float(c["shift_audio"]) if c.get("shift_audio") not in ("", None) else 3.0}}
        model = ["shift", 0]
    if cn:                         # Fun ControlNet-Union as a model patch: the clip follows the control video
        g["cnpatch"] = {"class_type": "ModelPatchLoader", "inputs": {"name": H3["cn_patch"]}}
        g["cnapply"] = {"class_type": "MiniMaxH3FunControlNetApply", "inputs": {
            "model": model, "model_patch": ["cnpatch", 0], "vae": ["vvae", 0], "strength": cn["strength"],
            "start_percent": 0.0, "end_percent": 1.0, "control_video": cn["video"]}}
        if cn.get("mask"):           # ControlNet inpaint keeps the new person aligned with the masked one
            g["cnapply"]["inputs"].update(mask=cn["mask"], source_video=cn["source"])
        model = ["cnapply", 0]
    g["clip"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": H3["clip"], "type": "minimax", "device": "default"}}
    g["vvae"] = {"class_type": "VAELoader", "inputs": {"vae_name": H3["vae"]}}
    g["avae"] = {"class_type": "VAELoader", "inputs": {"vae_name": H3["audio_vae"]}}
    cond = ["cond", 0]
    if guide:                      # anchor frames of the previous clip at frame 0 → this clip continues it
        g.update(guide)
        cond = ["guide", 0]
    g["guider"] = {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": cond}}
    g["noise"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    g["sampler"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": c["sampler"]}}
    g["sched"] = {"class_type": "BasicScheduler", "inputs": {"model": model, "scheduler": sched,
                                                             "steps": c["steps"], "denoise": float(c.get("denoise") or 1.0)}}
    g["sample"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise", 0], "guider": ["guider", 0],
                   "sampler": ["sampler", 0], "sigmas": ["sched", 0], "latent_image": ["cond", 1]}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vvae", 0]}}
    vin = {"images": ["dec", 0], "fps": 24}
    if cn and cn.get("mask"):      # masked replacement: H3's subject pasted onto the ORIGINAL frames — the rest stays pixel-exact
        g["comp"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": cn["source"], "source": ["dec", 0], "x": 0, "y": 0,
                                                                     "resize_source": True, "mask": cn["mask"]}}
        vin["images"] = ["comp", 0]
    if not silent:
        g["deca"] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["sample", 0], "vae": ["avae", 0]}}
        vin["audio"] = ["deca", 0]
    g["video"] = {"class_type": "CreateVideo", "inputs": vin}
    g["save"] = {"class_type": "SaveVideo", "inputs": {"video": ["video", 0], "filename_prefix": comfy.OUT_PREFIX + "/h3",
                                                       "format": "auto", "codec": "auto"}}
    return g


def has_audio(path):
    try:
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                           timeout=30, creationflags=core.NO_WINDOW)
        return "Audio:" in r.stderr
    except Exception:
        return False


def _tmp(tag, ext=".mp4"):
    return os.path.join(core.REFS, "_prep_%s_%d%s" % (tag, int(time.time() * 1000), ext))


def _job_caps(job):
    c = job.get("caps")
    return None if c is None else set(c)          # None = the owner / an internal job: everything


def _need_cap(job, cap, what):
    caps = _job_caps(job)
    if caps is not None and cap not in caps:
        raise RuntimeError("%s isn't included in your access — ask the host to add it" % what)


def _tail(path, frames, w, h):
    """The last `frames` frames of a clip (sound included) as a small mp4 to anchor the next clip on."""
    secs = media_seconds(path) or 5.0
    out = _tmp("tail")
    vf = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=24" % (w, h, w, h)
    ffmpeg(["-ss", "%.3f" % max(0.0, secs - frames / 24.0 - 0.02), "-i", path, "-frames:v", str(max(1, frames)), "-vf", vf,
            "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out], 180)
    return out


def _join(paths, drops, out, silent, xfade=False):
    """Join clips; drops[i] = frames to drop at the start of clip i (the anchored overlap)."""
    n = len(paths)
    if n == 1:
        os.replace(paths[0], out)
        return
    audio = not silent and all(has_audio(p) for p in paths)
    args, fc = [], []
    for i, p in enumerate(paths):
        args += ["-i", p]
        d = drops[i] / 24.0
        fc.append("[%d:v]trim=start=%.4f,setpts=PTS-STARTPTS,fps=24,format=yuv420p,setsar=1[v%d]" % (i, d, i))
        if audio:
            fc.append("[%d:a]atrim=start=%.4f,asetpts=PTS-STARTPTS,aresample=48000[a%d]" % (i, d, i))
    if xfade:
        lens = [max(0.3, media_seconds(p) - drops[i] / 24.0) for i, p in enumerate(paths)]
        cur, acc, t = "v0", lens[0], 0.25
        for i in range(1, n):
            nxt = "x%d" % i
            fc.append("[%s][v%d]xfade=transition=fade:duration=%.2f:offset=%.3f[%s]" % (cur, i, t, acc - t, nxt))
            cur, acc = nxt, acc + lens[i] - t
        vmap = "[%s]" % cur
        if audio:
            ca = "a0"
            for i in range(1, n):
                fc.append("[%s][a%d]acrossfade=d=%.2f[ax%d]" % (ca, i, t, i))
                ca = "ax%d" % i
            amap = "[%s]" % ca
    else:
        fc.append("".join("[v%d]%s" % (i, "[a%d]" % i if audio else "") for i in range(n)) +
                  "concat=n=%d:v=1:a=%d[vo]%s" % (n, 1 if audio else 0, "[ao]" if audio else ""))
        vmap, amap = "[vo]", "[ao]"
    args += ["-filter_complex", ";".join(fc), "-map", vmap] + (["-map", amap, "-c:a", "aac"] if audio else []) + \
        ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    ffmpeg(args, 900)


_GRADE = {"warm": "colorbalance=rs=.08:gs=.02:bs=-.08:rm=.05:bm=-.05", "cool": "colorbalance=rs=-.06:bs=.08:rm=-.04:bm=.06",
          "teal_orange": "colorbalance=rs=-.08:bs=.1:rh=.1:gh=.02:bh=-.1", "bw": "hue=s=0",
          "vintage": "curves=preset=vintage", "vivid": "eq=saturation=1.35:contrast=1.06", "contrast": "eq=contrast=1.25"}


def post_video(job, path, c):
    """⚙ Post effects with ffmpeg, in place. Every choice at its default = untouched."""
    speed = float(c.get("speed") or 1)
    vf, af = [], []
    if speed != 1:
        vf.append("setpts=PTS/%.3f" % speed)
        af.append("atempo=%.3f" % speed)
    if c.get("grade") in _GRADE:
        vf.append(_GRADE[c["grade"]])
    if c.get("sharpen") in ("light", "strong"):
        vf.append("unsharp=5:5:%s" % ("0.6" if c["sharpen"] == "light" else "1.2"))
    if c.get("grain") in ("light", "heavy"):
        vf.append("noise=alls=%d:allf=t" % (7 if c["grain"] == "light" else 16))
    if c.get("vignette") == "on":
        vf.append("vignette=PI/5")
    if c.get("upscale") in ("1.5", "2"):
        k = float(c["upscale"])
        vf.append("scale=trunc(iw*%.2f/2)*2:trunc(ih*%.2f/2)*2:flags=lanczos" % (k, k))
    fps = str(c.get("fps") or "24")
    if fps == "30":
        vf.append("fps=30")
    elif fps in ("48", "60"):
        vf.append("minterpolate=fps=%s:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" % fps)
    fade = c.get("fade", "none")
    if fade != "none":
        dur = (media_seconds(path) or 5.0) / speed
        d = min(0.8, dur / 4)
        if fade in ("in", "both"):
            vf.append("fade=t=in:st=0:d=%.2f" % d)
            af.append("afade=t=in:st=0:d=%.2f" % d)
        if fade in ("out", "both"):
            vf.append("fade=t=out:st=%.2f:d=%.2f" % (max(0.0, dur - d), d))
            af.append("afade=t=out:st=%.2f:d=%.2f" % (max(0.0, dur - d), d))
    loop = c.get("loop") == "boomerang"
    if not vf and not loop:
        return []
    audio = has_audio(path)
    done = []
    if vf:
        log(job, "post effects: %s …" % ", ".join(sorted(k for k in ("speed", "grade", "sharpen", "grain", "vignette", "upscale",
                                                                       "fps", "fade") if str(c.get(k)) not in
                                                         ("1", "none", "off", "24", "", "None"))))
        tmp = path + ".fx.mp4"
        ffmpeg(["-i", path, "-vf", ",".join(vf)] + (["-af", ",".join(af)] if audio and af else []) +
               ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if audio else ["-an"]) +
               ["-movflags", "+faststart", tmp], 1800)
        os.replace(tmp, path)
        done.append("effects")
    if loop:
        log(job, "boomerang loop …")
        tmp = path + ".loop.mp4"
        fc = "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]"
        if audio:
            fc += ";[0:a]asplit[x][y];[y]areverse[ry];[x][ry]concat=n=2:v=0:a=1[au]"
        ffmpeg(["-i", path, "-filter_complex", fc, "-map", "[v]"] + (["-map", "[au]", "-c:a", "aac"] if audio else []) +
               ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp], 900)
        os.replace(tmp, path)
        done.append("boomerang")
    return done


def custom_workflow(job, model, prompt, c, refs, w=0, h=0, length=0, steps=0):
    """⚙ ComfyUI workflow ≠ built-in → the person's own node graph. → result dict or None."""
    wid = c.get("workflow") or "builtin"
    if wid == "builtin":
        return None
    _need_cap(job, "workflows", "Custom ComfyUI workflows")
    seed = seed_of(c.get("seed"))
    vals = {"prompt": prompt, "negative": c.get("negative", ""), "seed": seed, "width": w or 1024, "height": h or 1024,
            "length": length or 121, "seconds": c.get("seconds") or c.get("duration") or 5, "steps": steps or c.get("steps") or 20,
            "fps": 24}
    prepare_gpu(job)
    entry, dt = workflows.run(job, wid, vals, refs, log)
    kind = workflows.KIND.get(model, "video")
    ext = {"video": ".mp4", "image": ".png", "audio": os.path.splitext(entry.get("filename", "x.mp3"))[1] or ".mp3"}[kind]
    name = save(entry, model + "_wf", ext, job, {"workflow": wid, "seed": seed})
    return {"files": [name], "text": "Custom workflow %s · seed %d · %.1f min\n\nPROMPT:\n%s" % (wid.split("__", 1)[1], seed,
                                                                                               dt / 60, prompt[:3000])}


def run_h3(job):
    refs = split_refs(job)
    text, c = h3_settings(job.get("prompt") or "", job["params"])
    guide_note(job, "h3", c)
    literal = bool(job.get("literal"))
    if literal:                            # My words: the prompt goes in as written (only ⚙ choices + ref tags are added)
        c["enhance"] = "off"
    script = attached_text(refs["text"])
    if script:
        text = (text + "\n" + script).strip()
    text = text or "a slow cinematic flight through a glowing neon city at night"
    imgs, vids, auds = refs["image"], refs["video"], refs["audio"]
    mode = c["mode"]
    if mode == "swap":                     # whole-body subject swap → the Wan VACE engine
        return run_vace_swap(job, c, text if not script else text, imgs, vids, literal)
    if job.get("ctlcheck"):                 # Pose Preview: the control video H3 would follow, no render
        if not vids:
            raise RuntimeError("attach the clip to preview the pose on")
        comfy.ensure()
        prepare_gpu(job)
        log(job, "extracting the %s control from your clip …" % c.get("control", "pose"))
        name = control_preview(vids[0], c, job)
        return {"files": [name], "text": "Control preview · left = your clip, right = what motion control follows. "
                "Broken or swapped limbs here = jitter in the render: crop tighter, slow it down, or use depth."}
    if (job.get("override") or {}).get("maskcheck") or job.get("maskcheck"):   # "who gets replaced?" — SAM3 only, seconds
        if not vids:
            raise RuntimeError("attach the clip to check the mask on")
        comfy.ensure()
        prepare_gpu(job)
        log(job, "SAM3 finding '%s' in your clip …" % (c.get("mask_what") or "person"))
        name = mask_preview(vids[0], c, job)
        return {"files": [name], "text": "Mask check · red = what gets replaced ('%s'). Not right? Describe them more exactly "
                "(e.g. 'man in red shorts:1') under ⚙ References → Masked subject." % (c.get("mask_what") or "person")}
    # attachments are always used: a mode that can't take them switches to one that can (it used to ignore them)
    if mode == "auto":
        mode = "r2v" if (imgs or vids) else "t2v"
    elif mode == "t2v" and (imgs or vids):
        log(job, "your %d attachment%s switch text → video to reference → video" % (len(imgs) + len(vids),
                                                                                    "" if len(imgs) + len(vids) == 1 else "s"))
        mode = "r2v"
    elif mode == "story" and len(imgs) < 2:
        mode = "i2v" if imgs else ("extend" if vids else "t2v")
        log(job, "storyboard needs 2+ pictures (keyframes) — using %s" % mode)
    elif mode in ("i2v", "flf2v") and not (imgs or vids):
        raise RuntimeError("%s needs a picture attached — attach one with 📎 (or pick text → video)"
                           % ("animate a picture" if mode == "i2v" else "start + end picture"))
    elif mode == "keyframes" and not imgs:
        mode = "r2v" if vids else "t2v"
        log(job, "keyframes need pictures — using %s" % mode)
    elif mode == "control" and not vids:
        raise RuntimeError("motion control needs the clip to follow — attach a video (pose / depth / any footage)")
    elif mode == "sing" and not auds:
        raise RuntimeError("sing mode needs the vocal / song chunk attached as audio")
    elif mode == "sing" and not (vids or imgs):
        raise RuntimeError("sing mode needs a picture to start from or the previous clip to continue")
    elif mode == "extend" and not vids:
        if not imgs:
            raise RuntimeError("extend needs the clip to continue — attach it (or a picture to start from)")
        mode = "i2v"
        log(job, "no clip attached to extend — starting from the picture instead")
    extra = 0 if mode == "sing" else int(c.get("extend") or 0)
    if mode in ("story", "extend") or extra:
        _need_cap(job, "extend", "Long videos (extend / storyboard)")
    wf = custom_workflow(job, "h3", text, c, refs, *h3_dims(c["mp"], c["aspect"] if c["aspect"] != "auto" else "16:9"),
                         h3_frames(c["seconds"]), c["steps"])
    if wf:
        return wf
    log(job, "MiniMax H3 · %s%s" % (mode, " + %d extension%s" % (extra, "" if extra == 1 else "s") if extra else ""))
    comfy.ensure()
    src = None
    img_names, vid_names, prepped = [], [], []
    aspect = "" if c["aspect"] == "auto" else c["aspect"]
    if mode in ("i2v", "flf2v") and vids and len(imgs) < (1 if mode == "i2v" else 2):
        # frame modes take pictures: an attached clip supplies its first / last frame instead of being ignored
        grab = [video_frame(vids[0], 0.0)]
        if mode == "flf2v" and not imgs:
            grab.append(video_frame(vids[0], max(0.0, media_seconds(vids[0]) - 0.15)))
        imgs = imgs + grab
        log(job, "using %d frame%s from the attached clip" % (len(grab), "" if len(grab) == 1 else "s"))
    if mode in ("i2v", "flf2v") and vids:
        log(job, "note: frame modes don't take motion from clips — use r2v for that")
    if mode == "flf2v" and len(imgs) < 2:
        mode = "i2v" if imgs else "t2v"
        log(job, "first + last frame needs 2 pictures — using %s" % mode)
    if mode in ("i2v", "flf2v", "story"):
        src = imgs[0]
        aspect = aspect or aspect_of(src, "16:9")
    elif mode == "extend":
        aspect = aspect or aspect_of(vids[0], "16:9")
    elif mode == "sing":
        aspect = aspect or aspect_of(vids[0] if vids else imgs[0], "16:9")
    elif mode in H3_REF_MODES:
        if H3["r2v_unet"] not in comfy.models("diffusion_models"):
            raise RuntimeError("reference mode needs %s in ComfyUI" % H3["r2v_unet"])
        if mode == "control" and H3["cn_patch"] not in comfy.models("model_patches"):
            raise RuntimeError("motion control needs %s in ComfyUI models/model_patches" % H3["cn_patch"])
        if mode == "control" and c.get("replace") == "masked" and H3["sam3"] not in comfy.models("checkpoints"):
            raise RuntimeError("masked replacement needs %s in ComfyUI models/checkpoints" % H3["sam3"])
        if mode == "control" and c.get("control") == "pose" and "sdpose_wholebody_fp16.safetensors" not in comfy.models("checkpoints"):
            log(job, "pose models missing in ComfyUI — following the clip's edges instead")
            c["control"] = "canny"
        if not aspect:                     # a portrait phone clip stays portrait
            aspect = aspect_of(vids[0] if vids else imgs[0], "16:9")
    aspect = aspect or "16:9"
    sched = c["scheduler"] if c["scheduler"] != "auto" else ("beta" if mode == "r2v" and c["quality"] == "full" else "simple")
    w, h = h3_dims(c["mp"], aspect)
    length = h3_frames(c["seconds"])
    # attached audio in a reference mode = an <Audio N> reference H3 hears and generates with (official ref2va), not a mux
    ref_auds = auds[:3] if (mode in H3_REF_MODES and c["soundtrack"] in ("auto", "reference")) else []
    if auds and c["soundtrack"] == "reference" and not ref_auds and mode != "sing":
        log(job, "audio as reference needs a reference mode — muxing it instead")
    soundtrack = auds[0] if (auds and not ref_auds and c["soundtrack"] != "ignore") else None
    sing_mux = False                       # a long song sung in pieces: the full song goes back on at the end
    silent = c["audio"] == "off" or (soundtrack and c["soundtrack"] in ("replace", "auto", "reference"))
    if mode == "sing":                     # the audio is the guide the picture is generated to, not a mux afterwards
        soundtrack, silent = None, False
        length = h3_frames(max(2.0, min(media_seconds(auds[0]), float(c.get("sing_max") or 60))))
    if mode == "control" and c.get("control_audio", "clip") == "clip" and vids and has_audio(vids[0]) and not soundtrack:
        soundtrack, silent = vids[0], True          # H3 makes the picture; the clip's real sound goes back on after
        c["soundtrack"] = "replace"
    direction = h3_direction(c)
    steady = c["steady"] == "on" and c.get("camera") not in ("handheld", "fpv")
    segs_text = [t.strip() for t in str(c.get("extend_prompt") or "").split("||") if t.strip()]

    def compose(idea, built, r2v=False, cont=False):
        """The final H3 prompt from the director's text (or the person's words) + the ⚙ direction + audio."""
        if built:
            p = built + ("\nCAMERA NOTE: steady camera, level horizon, upright framing." if steady else "")
        else:
            p = "" if literal else "Cinematic, photorealistic, smooth natural motion, detailed lighting. "
            if steady and not literal:
                p += "Steady camera, level horizon, upright framing. "
            if cont:
                p += "The shot continues seamlessly from its opening frames, same subjects, place and light. "
            if r2v:          # every attachment kind the person's words don't already tag gets its role line
                tags = []
                if imgs and not re.search(r"<Picture\s*\d+>", idea, re.I):
                    tags.append(H3_REF_ROLE.get(c.get("ref_role"), H3_REF_ROLE["identity"]).format(
                        p=", ".join("<Picture %d>" % (i + 1) for i in range(min(9, len(imgs))))))
                if vids and (mode == "control" or not re.search(r"<Video\s*\d+>", idea, re.I)):
                    tags.append("Follow the motion, poses and layout of the control video exactly." if mode == "control" else
                                "Use %s as the reference for motion, camera movement, framing and scene."
                                % ", ".join("<Video %d>" % (i + 1) for i in range(min(3, len(vids)))))
                if ref_auds and not re.search(r"<Audio\s*\d+>", idea, re.I):
                    tags.append("Use %s exactly as it is." % ", ".join("<Audio %d>" % (i + 1) for i in range(len(ref_auds))))
                p += " ".join(tags) + (" " if tags else "")
            p += idea.rstrip(". ") + "."
            if direction:
                p += " " + direction
            if r2v and not literal:
                p += " Keep every face stable, sharp and undistorted in every frame."
        if not silent:
            if c["audio"] == "custom" and c["audio_text"].strip():
                p += " AUDIO: " + c["audio_text"].strip() + "."
            elif not built and not literal and not ref_auds and not re.search(r"\b(audio|sound|music|voice|silent)\b", idea, re.I):
                p += " AUDIO: fitting ambient sound effects and subtle music."
        if c["style"] != "none":
            p += " embedding:minimaxh3_" + c["style"]
        return p

    def direct(idea, first=None, secs=None):
        if c["enhance"] != "on":
            return None
        log(job, "engine directing the shot list …")
        brief = idea + (("\n(Use this direction: %s)" % direction) if direction else "")
        return prompts.h3(core.ask, brief, int(secs or c["seconds"]), first_frame=first)

    flf = H3_FLF_LORA.get(c["quality"])
    segments, drops, prompts_used = [], [], []
    seed = seed_of(c["seed"])

    def render(node, unet, lora, guide=None, tag="seg"):
        entry, dt_ = comfy.run(h3_graph(node, unet, lora, c, seed + len(segments), sched, silent, guide), "video", job)
        out = _tmp(tag)
        comfy.fetch(entry, out)
        prepped.append(out)
        return out, dt_

    t_all = 0.0
    try:
        # ── the opening clip(s)
        if mode in H3_REF_MODES:
            linked = prompts.link_refs(text, len(imgs[:9]), 0 if mode == "control" else len(vids[:3]), len(ref_auds))
            keys = []
            if mode == "keyframes":            # official multiframe: every picture pinned at its moment of the one clip
                ks = imgs[:9]
                try:
                    tt = [float(x) for x in re.split(r"[,\s;]+", str(c.get("key_times") or "").strip()) if x]
                except ValueError:
                    tt = []
                end = (length - 1) / 24.0
                if len(tt) < len(ks):
                    tt = [round(end * i / max(1, len(ks) - 1), 2) for i in range(len(ks))] if len(ks) > 1 else [0.0]
                keys = [(p_, max(0.0, min(end, t))) for p_, t in zip(ks, tt)]
                linked = linked.rstrip(". ") + ". " + " ".join("<Picture %d> is the %s at %.1fs." % (i + 1, "first frame" if t == 0 else
                                                                             ("last frame" if t >= end - 0.05 else "keyframe"), t)
                                         for i, (_, t) in enumerate(keys))
            built = None
            if c["enhance"] == "on" and mode != "control":     # motion control: the clip already sets the action
                log(job, "engine studying your %d reference%s and directing …" % (len(imgs) + len(vids),
                                                                                 "" if len(imgs) + len(vids) == 1 else "s"))
                frames = [video_frame(v, 1.0) for v in vids[:2]]
                built = prompts.h3_refs(core.ask, linked + (("\n(Use this direction: %s)" % direction) if direction else ""),
                                        int(c["seconds"]), imgs[:9], frames, len(vids[:3]), c.get("ref_role", "identity"),
                                        len(ref_auds))
            if mode == "control" and c.get("replace") == "masked" and imgs and not literal and core.can_see():
                try:      # H3 takes the face from <Picture 1>, not the clothes: say the outfit in words so it is worn too
                    log(job, "engine reading the outfit in <Picture 1> …")
                    look = core.ask("In one short phrase, describe ONLY this person's clothing (colours, garment types) and any "
                                    "visible tattoos. No preamble, no face description.", "You are a precise costume designer.",
                                    timeout=120, images=[prompts._b64(imgs[0], 640)]).strip().rstrip(".")
                    if 3 < len(look) < 300:
                        linked += " The person from <Picture 1> wears exactly: %s." % look
                except Exception:
                    pass
            prompt = compose(linked, built, r2v=True)
            prepare_gpu(job)
            log(job, "uploading references …")
            img_names = [comfy.upload(p) for p in imgs[:9]]
            vid_audio = []
            for p in vids[:3]:
                pp = _tmp("ref")
                vf = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=24" % (w, h, w, h)
                if mode == "control":      # the control clip = exactly the output's frames (held on its last frame if short)
                    vf += ",tpad=stop_mode=clone:stop_duration=16,trim=end_frame=%d" % length
                ffmpeg(["-i", p, "-t", str(min(int(c.get("ref_secs") or 10), c["seconds"] + 1)) if mode != "control" else "%.3f" % (length / 24 + 1), "-vf", vf, "-c:v", "libx264",
                        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", pp], 180)
                prepped.append(pp)
                vid_names.append(comfy.upload(pp))
                vid_audio.append(has_audio(pp))
            node = {"cond": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
                "clip": ["clip", 0], "vae": ["vvae", 0], "audio_vae": ["avae", 0], "prompt": prompt,
                "width": w, "height": h, "length": length, "ref_image_size": c["ref_size"]}}}
            for i, n in enumerate(img_names):
                node["img%d" % i] = {"class_type": "LoadImage", "inputs": {"image": n}}
                node["cond"]["inputs"]["ref_images.ref_image_%d" % i] = ["img%d" % i, 0]
            for i, n in enumerate(vid_names):
                if mode == "control":       # the clip is the ControlNet input, not a <Video N> reference
                    break
                node["vid%d" % i] = {"class_type": "LoadVideo", "inputs": {"file": n}}
                node["vparts%d" % i] = {"class_type": "GetVideoComponents", "inputs": {"video": ["vid%d" % i, 0]}}
                node["cond"]["inputs"]["ref_videos.ref_video_%d" % i] = ["vparts%d" % i, 0]
                if vid_audio[i] and not silent:     # the clip's own soundtrack rides along as its <Video N> audio
                    node["cond"]["inputs"]["ref_video_audios.ref_video_audio_%d" % i] = ["vparts%d" % i, 1]
            for i, p in enumerate(ref_auds):
                node["aud%d" % i] = {"class_type": "LoadAudio", "inputs": {"audio": comfy.upload(p)}}
                node["cond"]["inputs"]["ref_audios.ref_audio_%d" % i] = ["aud%d" % i, 0]
            guide, prev = None, ["cond", 0]
            for i, (kp, t) in enumerate(keys):
                gid = "kf%d" % i
                guide = guide or {}
                guide[gid + "img"] = {"class_type": "LoadImage", "inputs": {"image": img_names[i]}}
                guide[gid] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
                    "positive": prev, "latent": ["cond", 1], "frame_idx": int(round(t * 24)), "vae": ["vvae", 0],
                    "audio_vae": ["avae", 0], "image": [gid + "img", 0]}}
                prev = [gid, 0]
            if guide:
                guide["guide"] = guide.pop("kf%d" % (len(keys) - 1))
            cn = None
            if mode == "control":
                cv = "ctlparts"
                node["ctlv"] = {"class_type": "LoadVideo", "inputs": {"file": vid_names[0]}}
                node[cv] = {"class_type": "GetVideoComponents", "inputs": {"video": ["ctlv", 0]}}
                src_ = [cv, 0]
                if c.get("control") == "pose":     # official Fun ControlNet pose prep: RT-DETR people → SDPose → stick figures
                    node["ctlpm"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}}
                    node["ctldm"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors",
                                                                            "weight_dtype": "default"}}
                    node["ctldet"] = {"class_type": "RTDETR_detect", "inputs": {"model": ["ctldm", 0], "image": src_, "threshold": 0.5,
                                      "class_name": "person", "max_detections": int(c.get("control_people") or 2)}}
                    node["ctlkp"] = {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["ctlpm", 0], "vae": ["ctlpm", 2],
                                     "image": src_, "batch_size": 16, "bboxes": ["ctldet", 0]}}
                    node["ctlpose"] = {"class_type": "SDPoseDrawKeypoints", "inputs": {"keypoints": ["ctlkp", 0], "draw_body": True,
                                       "draw_hands": True, "draw_face": True, "draw_feet": True, "stick_width": 4,
                                       "face_point_size": 2, "score_threshold": 0.5, "draw_head": True}}
                    src_ = ["ctlpose", 0]
                elif c.get("control", "canny") == "canny":
                    node["ctlcanny"] = {"class_type": "Canny", "inputs": {"image": src_, "low_threshold": 0.4,
                                                                          "high_threshold": 0.8}}
                    src_ = ["ctlcanny", 0]
                cn = {"strength": float(c.get("control_strength") or 1.0), "video": src_}
                if c.get("replace") == "masked":   # repaint only the subject SAM3 finds; every other pixel comes from the clip
                    node.update(mask_nodes([cv, 0], c))
                    cn.update(mask=["mskf", 0], source=[cv, 0])
                    log(job, "masked replacement: only '%s' is regenerated (grow %dpx · feather %dpx)" % (
                        c.get("mask_what") or "person", int(c.get("mask_grow") or 0), int(c.get("mask_feather") or 0)))
                log(job, "motion control: following <Video 1> (%s) · strength %.2f" % (c.get("control", "canny"), cn["strength"]))
            if keys:
                log(job, "keyframes: " + " · ".join("<Picture %d> @ %.1fs" % (i + 1, t) for i, (_, t) in enumerate(keys)))
            if ref_auds:
                log(job, "audio reference%s: %s" % ("" if len(ref_auds) == 1 else "s",
                                                    ", ".join("<Audio %d>" % (i + 1) for i in range(len(ref_auds)))))
            log(job, "rendering %dx%d · %.1fs · %s %d steps …" % (w, h, length / 24, c["quality"], c["steps"]))
            entry, dt = comfy.run(h3_graph(node, H3["r2v_unet"], H3["r2v_lora"] if c["quality"] != "full" else None, c, seed,
                                           sched, silent, guide, cn), "video", job)
            p_ = _tmp("seg")
            comfy.fetch(entry, p_)
            prepped.append(p_)
            segments.append(p_), drops.append(0), prompts_used.append(prompt)
            t_all += dt
        elif mode == "story":
            keys = imgs[:9]
            slen = h3_frames(int(c.get("story_secs") or c["seconds"]))
            for k in range(len(keys) - 1):
                idea = segs_text[k] if k < len(segs_text) else text
                built = direct(idea, keys[k], c.get("story_secs"))
                prompt = compose(idea, built)
                prepare_gpu(job)
                node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                    "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": prompt, "width": w, "height": h, "length": slen}},
                    "ff": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(keys[k])}},
                    "lf": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(keys[k + 1])}}}
                node["cond"]["inputs"]["first_frame"] = ["ff", 0]
                node["cond"]["inputs"]["last_frame"] = ["lf", 0]
                log(job, "storyboard %d/%d · keyframe %d → %d · %dx%d · %.1fs …" % (k + 1, len(keys) - 1, k + 1, k + 2, w, h,
                                                                                  slen / 24))
                p_, dt = render(node, H3["unet"], flf, tag="story")
                segments.append(p_), drops.append(1 if k else 0), prompts_used.append(prompt)
                t_all += dt
        elif mode == "extend":
            base = _tmp("base")
            vf = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=24" % (w, h, w, h)
            ffmpeg(["-i", vids[0], "-vf", vf, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "aac", base], 600)
            prepped.append(base)
            segments.append(base), drops.append(0), prompts_used.append("(your clip)")
            extra = max(1, extra)
        elif mode == "sing":
            # performance clip driven by a fixed vocal: the song chunk is anchored on the audio stream at frame 0 and the
            # picture is generated to it (mouths follow the real singing). With the previous clip attached, its last
            # frames are anchored too, so this clip continues it — the caller sends audio that starts `anchor` frames
            # before the new section, and those overlap frames are trimmed off the result.
            lip = c.get("lip") or "auto"
            if lip == "auto":         # do what the words say: "she talks / says / speaks" → speech, "he sings" → the lead sings
                if re.search(r"\b(speak|speaks|speaking|talk|talks|talking|says|saying|narrat\w*|explain\w*|tell\w*)\b", text, re.I):
                    lip = "speak"
                elif re.search(r"\b(sings?|singing|raps?|rapping)\b", text, re.I) and not re.search(r"\b[A-Z][\w' -]{0,40}? sings: \"", text):
                    lip = "lead"

            def sing_prompt(cont):
                p = "Animated musical performance. " if not (literal or lip == "speak" or re.search(
                    r"realistic|photoreal|live.action", text, re.I)) else ""
                if cont:
                    p += "The shot continues seamlessly from its opening frames: same characters, outfits, place and light. "
                p += text.rstrip(". ") + ". "
                if direction:
                    p += direction + " "
                sm = re.search(r"\b([A-Z][\w' -]{0,40}?) sings: \"", text)
                if sm or lip in ("lead", "all"):   # a sung chunk: only the named singer's (or the picture's) mouth follows the vocal
                    if sm:
                        who, poss = sm.group(1).strip(), sm.group(1).strip() + "'s"
                    elif lip == "all":
                        who, poss = "everyone in the picture", "Everyone's"
                    else:
                        who, poss = "the person in the picture", "The person in the picture's"
                    only = ("Everyone sings together. " if lip == "all" and not sm else
                            "Only %s sings: every other character keeps their mouth closed and just reacts. " % who)
                    p += ("%s lips, jaw and face move precisely in sync with every sung word of the soundtrack, opening on each "
                          "syllable and closing between phrases; the singer faces the camera so the mouth is clearly visible. %s"
                          "Mouths close during instrumental gaps; expressive, on-the-beat body movement. Keep every face stable "
                          "and undistorted. AUDIO: the given song only." % (poss, only))
                elif lip == "speak":
                    p += ("The person in the picture talks to the camera: lips, jaw and face move precisely in sync with every "
                          "spoken word of the soundtrack, natural conversational expressions, blinking and small head movements; "
                          "the mouth closes in the pauses. Keep the face stable and undistorted. AUDIO: the given voice only.")
                else:       # an instrumental / establishing chunk: nobody sings, so nobody mouths words
                    p += ("This part of the song is instrumental: nobody sings, talks or mouths words. Every character keeps their "
                          "mouth gently closed (a closed-mouth smile at most) for the whole clip and moves only with the music - "
                          "swaying, dancing, waving, splashing. Keep every face stable and undistorted. AUDIO: the given song only.")
                if c["style"] != "none":
                    p += " embedding:minimaxh3_" + c["style"]
                return p

            def sing_clip(audio, frames, prev, anc, tag):
                p = sing_prompt(bool(prev))
                prepare_gpu(job)
                node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                    "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": p, "width": w, "height": h, "length": frames}},
                    "song": {"class_type": "LoadAudio", "inputs": {"audio": comfy.upload(audio)}}}
                gin = {"positive": ["cond", 0], "latent": ["cond", 1], "frame_idx": 0, "audio_vae": ["avae", 0], "audio": ["song", 0]}
                if prev:
                    tail = _tail(prev, anc, w, h)
                    prepped.append(tail)
                    node["tailv"] = {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(tail)}}
                    node["tailc"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["tailv", 0]}}
                    gin.update(vae=["vvae", 0], image=["tailc", 0])
                else:
                    node["ff"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(imgs[0])}}
                    node["cond"]["inputs"]["first_frame"] = ["ff", 0]
                guide = {"guide": {"class_type": "MiniMaxH3AddGuide", "inputs": gin}}
                return render(node, H3["unet"], flf, guide, tag=tag) + (p,)

            song_s = min(media_seconds(auds[0]) or 0.0, float(c.get("sing_max") or 60))
            if vids or song_s <= 15.5:
                # one clip: the song chunk is anchored on the audio stream at frame 0 and the picture is generated to it
                # (mouths follow the real singing). With the previous clip attached, its last frames are anchored too, so this
                # clip continues it — the caller sends audio that starts `anchor` frames before the new section, and those
                # overlap frames are trimmed off the result.
                anchor = int(c.get("extend_anchor") or 22) if vids else 0
                log(job, "singing %dx%d · %.1fs to the attached vocal%s …" % (
                    w, h, length / 24, " · continuing the last %d frames" % anchor if vids else ""))
                p_, dt, p = sing_clip(auds[0], length, vids[0] if vids else None, anchor, "sing")
                segments.append(p_), drops.append(anchor), prompts_used.append(p)
                t_all += dt
            else:
                # a long song: ~10 s pieces, each continuing the last 22 frames of the one before (its audio starts 22 frames
                # early so the overlap lines up); every piece is cut to exactly the frames it owns and the full song is muxed
                # over the joined picture at the end, so lips stay on the words and there are no audio seams
                anc, first_n, next_n = 22, h3_frames(10), 17 * 14 - 17      # 243 new frames, then 238 new + 22 anchored
                total_n = int(round(song_s * 24))
                if song_s < (media_seconds(auds[0]) or 0) - 0.1:
                    log(job, "song is %.0fs — singing the first %.0fs (⚙ Sing: max length)" % (media_seconds(auds[0]), song_s))
                plan, done = [], 0
                while done < total_n:
                    new = first_n if not plan else next_n
                    plan.append((done, min(new, total_n - done)))
                    done += new
                if len(plan) > 1 and plan[-1][1] < 48:     # a tiny last piece: fold it into the one before
                    plan[-2] = (plan[-2][0], plan[-2][1] + plan[-1][1])
                    plan.pop()
                full = _tmp("song", ".wav")
                ffmpeg(["-i", auds[0], "-t", "%.3f" % song_s, "-ac", "2", "-ar", "48000", full], 120)
                prepped.append(full)
                for k, (start, n_new) in enumerate(plan):
                    if job.get("_cancel"):
                        raise comfy.Cancelled()
                    pre = 0 if k == 0 else anc
                    frames = h3_frames(max(2.0, (n_new + pre) / 24.0))
                    piece = _tmp("sing%d" % k, ".wav")
                    ffmpeg(["-ss", "%.4f" % ((start - pre) / 24.0), "-i", full, "-t", "%.4f" % ((n_new + pre) / 24.0), piece], 60)
                    prepped.append(piece)
                    log(job, "singing piece %d/%d · %.1fs → %.1fs · %dx%d …" % (k + 1, len(plan), start / 24.0,
                                                                             (start + n_new) / 24.0, w, h))
                    p_, dt, p = sing_clip(piece, frames, segments[-1] if segments else None, anc, "sing")
                    keep = _tmp("singk%d" % k)
                    ffmpeg(["-i", p_, "-frames:v", str(n_new + pre), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", keep], 300)
                    prepped.append(keep)
                    segments.append(keep), drops.append(pre), prompts_used.append(p)
                    t_all += dt
                soundtrack, sing_mux = full, True
        else:
            built = direct(text, src)
            prompt = compose(text, built)
            prepare_gpu(job)
            node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": prompt, "width": w, "height": h, "length": length}}}
            if mode in ("i2v", "flf2v"):
                node["ff"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(imgs[0])}}
                node["cond"]["inputs"]["first_frame"] = ["ff", 0]
            if mode == "flf2v":
                node["lf"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(imgs[1])}}
                node["cond"]["inputs"]["last_frame"] = ["lf", 0]
            log(job, "rendering %dx%d · %.1fs · %s %d steps …" % (w, h, length / 24, c["quality"], c["steps"]))
            p_, dt = render(node, H3["unet"], flf)
            segments.append(p_), drops.append(0), prompts_used.append(prompt)
            t_all += dt
        if c["trim"] > 0 and segments and mode not in ("extend", "sing"):
            drops[0] = int(c["trim"])
        # ── extensions: every new clip starts from the last frames of the one before (first frame → last frame chain)
        anchor = int(c.get("extend_anchor") or 22)
        base_n = len(segments)
        for e in range(extra):
            if job.get("_cancel"):
                raise comfy.Cancelled()
            prev = segments[-1]
            idx = (base_n + e) if mode == "story" else e
            idea = segs_text[idx] if 0 <= idx < len(segs_text) else text
            prompt = compose(idea, None, cont=True)
            prepare_gpu(job)
            if anchor == 1:
                last = video_frame(prev, max(0.0, media_seconds(prev) - 0.05))
                prepped.append(last)
                node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                    "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": prompt, "width": w, "height": h, "length": length}},
                    "ff": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(last)}}}
                node["cond"]["inputs"]["first_frame"] = ["ff", 0]
                guide = None
            else:
                tail = _tail(prev, anchor, w, h)
                prepped.append(tail)
                node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                    "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": prompt, "width": w, "height": h, "length": length}},
                    "tailv": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(tail)}},
                    "tailc": {"class_type": "GetVideoComponents", "inputs": {"video": ["tailv", 0]}}}
                gin = {"positive": ["cond", 0], "latent": ["cond", 1], "frame_idx": 0, "vae": ["vvae", 0], "image": ["tailc", 0]}
                if not silent and has_audio(tail):
                    gin.update(audio_vae=["avae", 0], audio=["tailc", 1])
                guide = {"guide": {"class_type": "MiniMaxH3AddGuide", "inputs": gin}}
            log(job, "extension %d/%d · continuing from the last %s · %.1fs …" % (
                e + 1, extra, "frame" if anchor == 1 else "%d frames" % anchor, length / 24))
            p_, dt = render(node, H3["unet"], flf, guide, tag="ext")
            segments.append(p_), drops.append(anchor), prompts_used.append(prompt)
            t_all += dt
        name = core.new_name("h3", ".mp4")
        path = os.path.join(core.LIB, name)
        if len(segments) > 1:
            log(job, "joining %d clips (%s s) …" % (len(segments), " + ".join("%.1f" % media_seconds(p_) for p_ in segments)))
        _join(segments, drops if len(segments) > 1 else [0], path + ".join.mp4", silent, c.get("join") == "xfade")
        if len(segments) == 1 and drops[0]:
            ffmpeg(["-ss", "%.3f" % (drops[0] / 24.0), "-i", path + ".join.mp4", "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", path], 300)
            os.remove(path + ".join.mp4")
        else:
            os.replace(path + ".join.mp4", path)
        if soundtrack:
            log(job, "adding the attached soundtrack …")
            tmp = path + ".mux.mp4"
            vol = float(c.get("track_vol") or 1.0)
            if c["soundtrack"] == "mix" and not silent and not sing_mux and has_audio(path):
                ffmpeg(["-i", path, "-i", soundtrack, "-filter_complex",
                        "[0:a][1:a]amix=inputs=2:duration=first:weights=0.5 %.2f[a]" % vol, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", tmp], 300)
            else:
                ffmpeg(["-i", path, "-i", soundtrack, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac"] +
                       (["-af", "volume=%.2f" % vol] if vol != 1.0 else []) + ["-shortest", tmp], 300)
            os.replace(tmp, path)
        fx = post_video(job, path, c)
        core.index_add(name, {"model": job["model"], "prompt": (job.get("prompt") or "")[:2000], "job": job["id"],
                              "created": time.time(), "user": job.get("user") or "owner", "mode": mode, "seed": seed,
                              "size": "%dx%d" % (w, h), "clips": len(segments), **({"session": job["session"]} if job.get("session") else {})})
    finally:
        for p in prepped:
            try:
                os.remove(p)
            except OSError:
                pass
    total = media_seconds(path)
    label = {"t2v": "text → video", "i2v": "image → video", "flf2v": "first + last frame → video",
             "story": "storyboard (%d keyframes)" % len(imgs[:9]), "extend": "extended clip",
             "sing": "sung to the vocal" + (" (continued)" if vids else ""),
             "keyframes": "keyframes (%d pictures pinned)" % len(img_names),
             "control": "motion control (%s)" % c.get("control", "canny"),
             "r2v": "reference → video (%d picture%s, %d clip%s)" % (len(img_names), "" if len(img_names) == 1 else "s",
                                                                      len(vid_names), "" if len(vid_names) == 1 else "s")}[mode]
    shown = prompts_used[0] if len(prompts_used) == 1 else "\n\n".join(
        "CLIP %d:\n%s" % (i + 1, p[:1500]) for i, p in enumerate(prompts_used))
    return {"files": [name], "text": "MiniMax H3 %s · %.1fs%s · %dx%d (%s) · %s %d steps · %s/%s · seed %d%s%s%s · %.1f min\n\nPROMPT:\n%s" % (
        label, total, " · %d clips joined" % len(segments) if len(segments) > 1 else "", w, h, aspect, c["quality"], c["steps"],
        c["sampler"], sched, seed, " · style " + c["style"] if c["style"] != "none" else "",
        " · soundtrack " + os.path.basename(soundtrack).split("_", 2)[-1] if soundtrack else "",
        " · " + " + ".join(fx) if fx else "", t_all / 60, shown[:6000])}



# ══ WAN 2.1 VACE 1.3B — masked subject swap (official "Wan2.1 VACE Inpainting" recipe) ══════════════════════════
# H3's Fun ControlNet inpaint paints the hole black, so whole-body replacement runs on VACE: SAM3 masks the subject,
# the masked area is blanked in the control video, VACE paints the person from the reference picture into it, and
# the result is pasted back onto the ORIGINAL frames — everything outside the mask stays pixel-exact.
VACE = {"unet": "wan2.1_vace_1.3B_fp16.safetensors", "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "vae": "wan_2.1_vae.safetensors", "lora": "Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors"}
core.apply_model_overrides(VACE)
VACE_NEG = ("过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
            "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，"
            "背景人很多，倒着走")
VACE_RES = {"draft": 0.25, "standard": 0.4, "high": 0.5, "max": 0.6}     # MP; 1.3B is trained at 480p (~0.4 MP)


def vace_dims(aspect, mp):
    ar = H3_ASPECTS.get(aspect, 16 / 9)
    w = (mp * 1_000_000 * ar) ** 0.5
    return max(256, int(round(w / 16)) * 16), max(256, int(round(w / ar / 16)) * 16)


def _gray_frames(path, w, h):
    """Decode a (mask) video to an (n, h, w) uint8 array — ffmpeg raw gray, no Pillow."""
    import numpy as np
    r = subprocess.run([core.FFMPEG, "-v", "error", "-i", path, "-vf", "scale=%d:%d,format=gray" % (w, h), "-f", "rawvideo", "-"],
                       capture_output=True, timeout=600, creationflags=core.NO_WINDOW)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    n = a.size // (w * h)
    return a[:n * w * h].reshape(n, h, w)


def _sam_masks(job, c, image_node, what, individual=False, tag="msk"):
    """SAM3 masks of an image / frame batch → an mp4 whose frames are the masks (one per frame, or per object)."""
    g = dict(image_node)
    g.update(mask_nodes([next(iter(image_node)), 0] if "vc" not in image_node else ["vc", 0],
                        dict(c, mask_what=what, mask_grow=c.get("_grow", 0), mask_feather=0)))
    g["mskd"]["inputs"]["individual_masks"] = bool(individual)
    g["mi"] = {"class_type": "MaskToImage", "inputs": {"mask": ["mskf", 0]}}
    g["mv"] = {"class_type": "CreateVideo", "inputs": {"images": ["mi", 0], "fps": 16}}
    g["save"] = {"class_type": "SaveVideo", "inputs": {"video": ["mv", 0], "filename_prefix": comfy.OUT_PREFIX + "/" + tag,
                                                       "format": "auto", "codec": "auto"}}
    entry, _ = comfy.run(g, "video", job, 15 * 60)
    out = _tmp(tag)
    comfy.fetch(entry, out)
    return out


def _faces(img):
    """Face boxes in a picture → [(x0, y0, x1, y1, score)]. No face detector ships with MIR MEDIA LABS: empty."""
    return []


def _clean_reference(job, c, img, prepped):
    """VACE wants ONE person on a plain background. A character sheet (front / side / back) or a busy photo is cut down
    to the person whose face is biggest + clearest (the front view), cropped to that figure and put on white."""
    import numpy as np
    wh = core.media_size(img) or (1024, 1024)
    W, H = wh
    faces = _faces(img)
    if not faces:
        log(job, "reference: no face found to pick a view — using the picture as it is")
        return img
    fx0, fy0, fx1, fy1, _ = max(faces, key=lambda f: (f[2] - f[0]) * (f[3] - f[1]) * f[4])
    fw, fh = fx1 - fx0, fy1 - fy0
    if len(faces) == 1 and fw > 0.22 * W:
        return img                                       # one person filling the picture: nothing to clean
    cw = int(min(W, fw * 3.8)) // 2 * 2
    x0 = int(max(0, min(W - cw, (fx0 + fx1) / 2 - cw / 2))) // 2 * 2
    y0 = int(max(0, fy0 - 0.7 * fh)) // 2 * 2
    ch = (H - y0) // 2 * 2
    out = os.path.join(core.REFS, "_refclean_%d.png" % int(time.time() * 1000))
    ffmpeg(["-i", img, "-vf", "crop=%d:%d:%d:%d" % (cw, ch, x0, y0), "-frames:v", "1", out], 60)
    prepped.append(out)
    log(job, "reference: kept only the front view (%d face%s in the picture)" % (len(faces), "" if len(faces) == 1 else "s"))
    return out


def face_pass(job, face_img, path, prepped):
    """Exact-face pass: not part of MIR MEDIA LABS (no face-swap model ships with it) — the VACE swap is the result."""
    return False


SWAP_MAX_S = 60


def run_vace_swap(job, c, text, imgs, vids, literal=False):
    """Any length up to SWAP_MAX_S: clips over 10 s are swapped in sections and joined (same picture + seed)."""
    want = float(c.get("swap_secs") if c.get("swap_secs") not in (None, "") else 5)
    if want <= 0:
        want = SWAP_MAX_S
    total = min(want, media_seconds(vids[0]) if vids else want, SWAP_MAX_S) if vids else want
    if not vids or total <= 10.5:
        return _vace_section(job, dict(c, seconds=total), text, imgs, vids, literal)
    n = int((total + 9.999) // 10)
    seg = total / n
    seed = seed_of(c.get("seed"))
    parts, t_all, last = [], 0.0, None
    log(job, "long swap: %.0fs in %d sections of ~%.1fs" % (total, n, seg))
    try:
        for i in range(n):
            if job.get("_cancel"):
                raise comfy.Cancelled()
            log(job, "▶ section %d/%d (%.1fs → %.1fs)" % (i + 1, n, i * seg, (i + 1) * seg))
            r = _vace_section(job, dict(c, seconds=seg, seed=seed, _start=i * seg, _chunk=True), text, imgs, vids, literal)
            parts.append(r["path"])
            t_all += r["dt"]
            last = r
        name = core.new_name("swap", ".mp4")
        path = os.path.join(core.LIB, name)
        lst = _tmp("swaplist", ".txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write("".join("file '%s'\n" % p_.replace("\\", "/") for p_ in parts))
        ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-movflags", "+faststart", path], 1200)
        os.remove(lst)
    finally:
        for p_ in parts:
            try:
                os.remove(p_)
            except OSError:
                pass
    core.index_add(name, {"model": job["model"], "prompt": (job.get("prompt") or "")[:2000], "job": job["id"],
                          "created": time.time(), "user": job.get("user") or "owner", "mode": "swap", "seed": seed,
                          "size": "%dx%d" % (last["w"], last["h"]), **({"session": job["session"]} if job.get("session") else {})})
    return {"files": [name], "text": "Wan VACE subject swap · %.1fs in %d sections · %dx%d · seed %d · %.1f min\n\nPROMPT:\n%s" % (
        media_seconds(path), n, last["w"], last["h"], seed, t_all / 60, last["prompt"][:3000])}


def _vace_section(job, c, text, imgs, vids, literal=False):
    import numpy as np
    if not vids or not imgs:
        raise RuntimeError("Put me in this clip needs your picture AND the clip — attach both")
    need = [(VACE["unet"], "diffusion_models"), (VACE["clip"], "text_encoders"), (VACE["vae"], "vae"),
            (H3["sam3"], "checkpoints")]
    miss = [n for n, f in need if comfy.models(f) and n not in comfy.models(f)]
    if miss:
        raise RuntimeError("the swap engine needs %s in ComfyUI" % ", ".join(miss))
    comfy.ensure()
    what = c.get("mask_what") or "person"
    secs = min(float(c.get("seconds") or 5), max(1.0, (media_seconds(vids[0]) or 5.0) - float(c.get("_start") or 0)), 10.0)
    length = max(5, int(secs * 16) // 4 * 4 + 1)                       # Wan: 4k+1 frames @ 16 fps
    turbo = c.get("swap_quality", "turbo") != "full" and VACE["lora"] in comfy.models("loras")
    steps = 8 if turbo else 20
    prepped = []
    # ── the clip at its own resolution (long side ≤ 1280), 16 fps — the frames the result is stitched back into
    W, H = core.media_size(vids[0]) or (720, 1280)
    k = min(1.0, 1280.0 / max(W, H))
    W, H = int(W * k) // 2 * 2, int(H * k) // 2 * 2
    full = _tmp("vace_full")
    ffmpeg(["-ss", "%.3f" % float(c.get("_start") or 0), "-i", vids[0], "-t", "%.3f" % (length / 16 + 0.5),
            "-vf", "scale=%d:%d,fps=16" % (W, H), "-frames:v", str(length),
            "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", full], 300)
    prepped.append(full)
    seed = seed_of(c.get("seed"))
    try:
        prepare_gpu(job)
        # ── pass 1: where is the subject? (SAM3 on the full frames)
        log(job, "finding '%s' in every frame …" % what)
        fmask = _sam_masks(job, dict(c, _grow=max(8, int(24 * W / 720))),
                           {"v": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(full)}},
                            "vc": {"class_type": "GetVideoComponents", "inputs": {"video": ["v", 0]}}}, what, False, "swapmask")
        prepped.append(fmask)
        ms = _gray_frames(fmask, W, H)
        on = ms > 127
        if not on.any():
            raise RuntimeError("couldn't find '%s' in the clip — describe them differently (e.g. 'man in red shorts')" % what)
        ys, xs = np.nonzero(on.any(axis=0))
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        # ── crop box: the subject's whole path + padding, at the render aspect, inside the frame (static = no jitter)
        bw, bh = (x1 - x0) * 1.24 + 16, (y1 - y0) * 1.16 + 16
        mp = VACE_RES.get(c.get("res"), 0.4)
        ar = bw / bh
        rw, rh = vace_dims(min(H3_ASPECTS, key=lambda a: abs(H3_ASPECTS[a] - ar)), mp)
        tar = rw / rh
        if bw / bh < tar:
            bw = bh * tar
        else:
            bh = bw / tar
        bw, bh = min(bw, W), min(bh, H)
        if bw / bh > tar + 1e-3:
            bw = bh * tar
        elif bw / bh < tar - 1e-3:
            bh = bw / tar
        cw, ch = int(bw) // 2 * 2, int(bh) // 2 * 2
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ox = int(max(0, min(W - cw, cx - cw / 2))) // 2 * 2
        oy = int(max(0, min(H - ch, cy - ch / 2))) // 2 * 2
        log(job, "subject crop %dx%d at %d,%d of %dx%d → rendered at %dx%d (%.1fx the pixels of a full-frame render)" % (
            cw, ch, ox, oy, W, H, rw, rh, (W * H) / float(cw * ch)))
        crop = _tmp("vace_crop")
        ffmpeg(["-i", full, "-vf", "crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos" % (cw, ch, ox, oy, rw, rh), "-an",
                "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", crop], 300)
        prepped.append(crop)
        ref = _clean_reference(job, c, imgs[0], prepped)
        # ── the prompt: who (from the picture, in words) doing what (from the clip)
        who, scene = "the person from the reference picture", ""
        if not literal and core.can_see():
            try:
                log(job, "engine reading your picture and the clip …")
                who = core.ask("Describe this person for a video model in one short phrase: gender, age range, hair, skin tone, "
                               "build, exact clothing (colours, garments) and visible tattoos. No preamble.",
                               "You are a precise casting director.", timeout=120,
                               images=[prompts._b64(ref, 640)]).strip().rstrip(".") or who
                scene = core.ask("Describe this video frame in one sentence: where it is and what the main person is doing. "
                                 "Call the main person 'the person'. No preamble.", "You are a precise film describer.",
                                 timeout=120, images=[prompts._b64(video_frame(full, min(1.0, secs / 2)), 640)]).strip().rstrip(".")
            except Exception:
                pass
        idea = (text or "").strip()
        p = ("%s. The person is %s, exactly as in the reference picture: same face, hair, clothing and tattoos. %s" % (
            scene or "The person performs the action of the original video", who, idea)).strip()
        if literal and idea:
            p = idea
        prepare_gpu(job)
        # ── pass 2: VACE paints the person into the enlarged crop
        g = {"v": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(crop)}},
             "vc": {"class_type": "GetVideoComponents", "inputs": {"video": ["v", 0]}},
             "fr": {"class_type": "ImageFromBatch", "inputs": {"image": ["vc", 0], "batch_index": 0, "length": length}},
             "ref": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(ref)}}}
        g.update(mask_nodes(["fr", 0], dict(c, mask_grow=max(16, int(c.get("mask_grow") or 20)), mask_feather=0)))
        g.update({
            "inv": {"class_type": "InvertMask", "inputs": {"mask": ["mskf", 0]}},
            "invi": {"class_type": "MaskToImage", "inputs": {"mask": ["inv", 0]}},
            "ctl": {"class_type": "ImageCompositeMasked", "inputs": {"destination": ["fr", 0], "source": ["invi", 0], "x": 0, "y": 0,
                                                                     "resize_source": True, "mask": ["mskf", 0]}},
            "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": VACE["unet"], "weight_dtype": "default"}},
            "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": VACE["clip"], "type": "wan", "device": "default"}},
            "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VACE["vae"]}},
            "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": p}},
            "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": VACE_NEG}},
            "vace": {"class_type": "WanVaceToVideo", "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "vae": ["vae", 0],
                     "width": rw, "height": rh, "length": length, "batch_size": 1, "strength": 1.0,
                     "control_video": ["ctl", 0], "control_masks": ["mskf", 0], "reference_image": ["ref", 0]}},
        })
        model = ["unet", 0]
        if turbo:
            g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": VACE["lora"], "strength_model": 0.7}}
            model = ["lora", 0]
        g.update({
            "shift": {"class_type": "ModelSamplingSD3", "inputs": {"model": model, "shift": 5.0}},
            "ks": {"class_type": "KSampler", "inputs": {"model": ["shift", 0], "positive": ["vace", 0], "negative": ["vace", 1],
                   "latent_image": ["vace", 2], "seed": seed, "steps": steps, "cfg": 1.0 if turbo else 6.0,
                   "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
            "trim": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["ks", 0], "trim_amount": ["vace", 3]}},
            "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["trim", 0], "vae": ["vae", 0]}},
            "out": {"class_type": "CreateVideo", "inputs": {"images": ["dec", 0], "fps": 16}},
            "save": {"class_type": "SaveVideo", "inputs": {"video": ["out", 0], "filename_prefix": comfy.OUT_PREFIX + "/vace_swap",
                                                           "format": "auto", "codec": "auto"}}})
        log(job, "swap engine (Wan VACE 1.3B) · %dx%d crop · %.1fs · %s %d steps · replacing '%s' …" % (
            rw, rh, length / 16, "turbo" if turbo else "full", steps, what))
        entry, dt = comfy.run(g, "video", job)
        raw = _tmp("vace_out")
        comfy.fetch(entry, raw)
        prepped.append(raw)
        # ── stitch: the render scaled back into its box, merged into the ORIGINAL full-res frames through the full mask
        name = core.new_name("swap", ".mp4")
        path = os.path.join(core.LIB, name)
        fc = ("[0:v]setsar=1,format=gbrp,split[b0][b1];[1:v]scale=%d:%d:flags=lanczos,setsar=1,format=gbrp[g];"
              "[b0][g]overlay=%d:%d:shortest=1,format=gbrp[ov];"
              "[2:v]scale=%d:%d,format=gray,boxblur=%d,format=gbrp,setsar=1[m];[b1][ov][m]maskedmerge,"
              "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,format=yuv420p[vo]") % (
            cw, ch, ox, oy, W, H, max(2, int(4 * W / 720)))
        args = ["-i", full, "-i", raw, "-i", fmask, "-filter_complex", fc, "-map", "[vo]"]
        args += (["-map", "0:a", "-c:a", "aac"] if has_audio(full) else []) + \
            ["-c:v", "libx264", "-crf", "15", "-shortest", "-movflags", "+faststart", path]
        ffmpeg(args, 1200)
        if c.get("face_pass", "off") == "on":
            face_pass(job, imgs[0], path, prepped)
        if c.get("_chunk"):
            return {"path": path, "prompt": p, "dt": dt, "w": W, "h": H}
        core.index_add(name, {"model": job["model"], "prompt": (job.get("prompt") or "")[:2000], "job": job["id"],
                              "created": time.time(), "user": job.get("user") or "owner", "mode": "swap", "seed": seed,
                              "size": "%dx%d" % (W, H), **({"session": job["session"]} if job.get("session") else {})})
    finally:
        for p_ in prepped:
            try:
                os.remove(p_)
            except OSError:
                pass
    return {"files": [name], "text": "Wan VACE subject swap · %.1fs · %dx%d output · subject rendered at %dx%d (crop %dx%d) · "
            "%s %d steps · seed %d · %.1f min\n\nPROMPT:\n%s" % (length / 16, W, H, rw, rh, cw, ch,
                                                              "turbo" if turbo else "full", steps, seed, dt / 60, p[:3000])}


# ══ MINIMAX MUSIC 3.0 — full songs ═════════════════════════════════════════
MUSIC = {"dit": ["minimax_music3_dit_fp16.safetensors", "minimax_music3_dit_int8_convrot.safetensors"],
         "te": "minimax_music3_text_encoder_pruned_int8_convrot.safetensors", "vae": "minimax_music3_dav.safetensors"}
core.apply_model_overrides(MUSIC)


def run_music3(job):
    refs = split_refs(job)
    c = job["params"]
    guide_note(job, "music3", c)
    raw = job.get("prompt") or ""
    wf = custom_workflow(job, "music3", raw, c, refs)
    if wf:
        return wf
    secs, raw = flag(raw, r"--(\d{1,3})\s*s\b", float)
    if secs is None:
        secs, raw = music_len(raw)
    secs = max(10.0, min(300.0, secs or float(c["duration"])))
    cap = min(360.0, secs * 1.2 + 10)    # max_duration is a hard stop, not a target — headroom so the song ends, never cut off
    s, raw = flag(raw, r"--seed\s+(\d+)", int)
    seed = seed_of(s if s is not None else c["seed"])
    _ly = re.search(r"\|\s*lyrics\s*:(.*)$", raw, re.I | re.S)
    if _ly:            # the hard stop must fit the WORDS too: a 30 s target with ~55 s of lyrics was chopped at 46 s
        _t = _ly.group(1)
        sung = len([l for l in _t.splitlines() if l.strip() and not re.match(r"^\s*\[.*\]\s*$", l)])
        breaks = len(re.findall(r"^\s*\[[^\]]*\]\s*$", _t, re.M))
        need = sung * 5.0 + breaks * 3.0
        cap = min(360.0, max(cap, need * 1.5 + 20))
    instr = bool(re.search(r"--instrumental\b|\binstrumental\b", raw, re.I)) or c["lyrics"] == "instrumental"
    raw = re.sub(r"--instrumental\b", "", raw)
    lyrics = ""
    m = re.search(r"\|\s*lyrics\s*:(.*)$", raw, re.I | re.S)
    if m:
        lyrics, raw = m.group(1).strip(), raw[:m.start()]
    if not lyrics and refs["text"]:
        lyrics = attached_text(refs["text"])
    idea = core.clean_ws(raw) or "an uplifting synth-pop anthem about chasing a dream"
    pics = refs["image"] + [video_frame(v) for v in refs["video"][:2]]
    mood = describe(pics, job)
    if mood:
        idea += "\nMood reference from the attached pictures: " + mood
    caption = idea
    literal = bool(job.get("literal")) or "--raw" in raw
    idea = caption = core.clean_ws(caption.replace("--raw", ""))
    if literal and (lyrics or instr):
        log(job, "My words: your text is the caption, as written")
    elif literal:
        log(job, "My words: your text is the caption; the engine only writes lyrics for it …")
        out = prompts.music3(core.ask, idea, secs)
        mm = re.search(r"CAPTION:\s*(.*?)\s*LYRICS:\s*(.*)$", out or "", re.S | re.I)
        lyrics = (mm.group(2).strip() if mm else "") or "[Intro]\n\n[Verse]\n\n[Chorus]\n\n[Outro]"
    elif not lyrics or instr:
        log(job, "engine writing the caption%s …" % ("" if instr else " + lyrics"))
        out = prompts.music3(core.ask, idea + ("\n(instrumental — no sung words)" if instr else ""), secs)
        mm = re.search(r"CAPTION:\s*(.*?)\s*LYRICS:\s*(.*)$", out or "", re.S | re.I)
        if mm:
            caption = mm.group(1).strip()
            if not lyrics:
                lyrics = mm.group(2).strip()
        lyrics = lyrics or "[Intro]\n\n[Verse]\n\n[Chorus]\n\n[Outro]"
    else:
        log(job, "engine writing the caption around your lyrics …")
        out = prompts.music3(core.ask, idea + "\n(use these lyrics as written:)\n" + lyrics[:3000], secs)
        mm = re.search(r"CAPTION:\s*(.*?)\s*LYRICS:", out or "", re.S | re.I)
        if mm:
            caption = mm.group(1).strip()
    prepare_gpu(job)
    have = comfy.models("diffusion_models")
    order = MUSIC["dit"] if c["model"] == "fp16" else MUSIC["dit"][::-1]
    dit = next((d for d in order if d in have), None)
    if not dit:
        raise RuntimeError("MiniMax Music 3 weights missing in ComfyUI models/diffusion_models")
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": dit, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": MUSIC["te"], "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": MUSIC["vae"]}},
        "4": {"class_type": "MiniMaxMusic3TextEncode", "inputs": {"clip": ["2", 0], "caption": caption, "lyrics": lyrics,
              "seed": seed, "max_duration": cap, "cfg_scale": float(c["lm_cfg"]), "top_k": int(c["top_k"])}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyMiniMaxMusic3LatentAudio", "inputs": {"seconds": ["4", 1], "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
              "latent_image": ["6", 0], "seed": seed, "steps": int(c["steps"]), "cfg": float(c["cfg"]),
              "sampler_name": c["sampler"], "scheduler": c["scheduler"], "denoise": 1.0}},
        "8": ({"class_type": "VAEDecodeAudioTiled", "inputs": {"samples": ["7", 0], "vae": ["3", 0], "tile_size": 1536, "overlap": 64}}
              if c["decode"] == "tiled" else {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}}),
        "9": {"class_type": "SaveAudioMP3", "inputs": {"audio": ["8", 0], "filename_prefix": comfy.OUT_PREFIX + "/music3",
                                                       "quality": c["quality"]}},
    }
    log(job, "composing + singing (up to %ds) …" % secs)
    entry, dt = comfy.run(g, "audio", job, 60 * 60)
    name = save(entry, "music3", ".mp3", job, {"seed": seed, "lyrics": lyrics[:4000], "caption": caption[:2000]})
    return {"files": [name], "meta": song_meta(caption, lyrics), "text": "MiniMax Music 3 (%s) · up to %ds · seed %d · %.1f min\n\nCAPTION:\n%s\n\nLYRICS:\n%s" % (
        "fp16" if "fp16" in dit else "int8", secs, seed, dt / 60, caption, lyrics)}


# ══ QWEN IMAGE 2.1 — t2i · edit · cutout ═══════════════════════════════════
QIMG = {"dit": "qwen_image_2.1_int8_convrot.safetensors", "te": "qwen3vl_8b_int8_convrot.safetensors",
        "vae": "qwen_image_2.1_vae_bf16.safetensors"}
core.apply_model_overrides(QIMG)
QIMG_ASPECT = {"1:1": (1024, 1024), "16:9": (1344, 768), "9:16": (768, 1344), "4:3": (1152, 896), "3:4": (896, 1152),
               "3:2": (1216, 832), "2:3": (832, 1216), "21:9": (1536, 640), "2:1": (1440, 720), "1:2": (720, 1440),
               "4:5": (928, 1152), "5:4": (1152, 928)}
CUTOUT_PROMPT = "Remove the background, and output a PNG image"


def qimg_render(job, prompt, c, aspect, steps, seed, ref_imgs, tag):
    w, h = QIMG_ASPECT.get(aspect, (1024, 1024))
    scale = {"hd": 1.41, "max": 2.0}.get(c["size"], 1.0)
    if scale != 1.0:
        w, h = int(w * scale) // 32 * 32, int(h * scale) // 32 * 32
    n = len(ref_imgs or [])
    res = int(c["edit_res"]) if c["edit_res"] != "auto" else (1024 if n <= 2 else 896 if n <= 3 else 768 if n <= 5 else 640 if n <= 7 else 512)
    cfg = float(c["cfg"])
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": QIMG["dit"], "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": c["cache"], "dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": QIMG["te"], "type": "qwen_image", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": QIMG["vae"]}},
        "5": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["3", 0], "prompt": prompt,
              "negative_prompt": c["negative"] if cfg > 1.0 else "", "resolution": res}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": comfy.OUT_PREFIX + "/" + tag}},
    }
    if ref_imgs:
        g["5"]["inputs"]["vae"] = ["4", 0]
        for i, p in enumerate(ref_imgs[:prompts.QWEN_MAX_REFS]):
            g[str(20 + i)] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(p)}}
            g["5"]["inputs"]["images.image_%d" % (i + 1)] = [str(20 + i), 0]
        latent = ["5", 2]
        if job.get("keep_clean") and c.get("aspect") not in (None, "auto"):   # SERIES: the asked-for shape (16:9 location
            g["6"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}  # from a 3:4 hero)
            latent = ["6", 0]
    else:
        g["6"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
        latent = ["6", 0]
    g["7"] = {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["5", 0], "negative": ["5", 1],
              "latent_image": latent, "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": c["sampler"],
              "scheduler": c["scheduler"], "denoise": 1.0}}
    log(job, "rendering%s · %d steps …" % ("" if ref_imgs else " %dx%d" % (w, h), steps))
    entry, dt = comfy.run(g, "image", job, 30 * 60)
    comfy.free()
    return entry, dt, (w, h)


def run_qimg(job):
    refs = split_refs(job)
    c = job["params"]
    guide_note(job, "qwen_t2i", c)
    raw = job.get("prompt") or ""
    aspect, aspect_set = (c["aspect"], True) if c["aspect"] != "auto" else ("1:1", False)
    m = re.search(r"\b(1:1|16:9|9:16|4:3|3:4|3:2|2:3|21:9|2:1|1:2|4:5|5:4)\b", raw)
    if m:
        aspect, aspect_set, raw = m.group(1), True, raw.replace(m.group(0), "")
    elif re.search(r"\b(vertical|portrait|story|reel|phone wallpaper)\b", raw, re.I):
        aspect, aspect_set = "9:16", True
    elif re.search(r"\b(widescreen|landscape|banner|thumbnail)\b", raw, re.I):
        aspect, aspect_set = "16:9", True
    steps = int(c["steps"])
    if "--hq" in raw:
        steps, raw = 40, raw.replace("--hq", "")
    if "--hd" in raw:
        c = dict(c, size="hd")
        raw = raw.replace("--hd", "")
    s, raw = flag(raw, r"--steps\s+(\d{1,2})", int)
    steps = max(4, min(60, s or steps))
    s, raw = flag(raw, r"--seed\s+(\d+)", int)
    seed = seed_of(s if s is not None else c["seed"])
    rawmode = "--raw" in raw or c["enhance"] == "off" or bool(job.get("literal"))
    raw = raw.replace("--raw", "")
    text = core.clean_ws(raw)
    extra = attached_text(refs["text"])
    if extra:
        text = (text + "\n" + extra).strip()
    pics = refs["image"] + [video_frame(v) for v in refs["video"][:3]]
    dropped = max(0, len(pics) - prompts.QWEN_MAX_REFS)
    pics = pics[:prompts.QWEN_MAX_REFS]
    mode = c["mode"]
    if mode == "auto":
        cut = re.search(r"\b(remove|cut out|delete|transparent)\b.*\bbackground\b|\bremove bg\b|\bcutout\b", text, re.I)
        mode = ("cutout" if cut else "edit") if pics else "generate"
    if mode == "generate" and pics:
        log(job, "your %d attached picture%s switch text → image to edit (they're used, not ignored)"
            % (len(pics), "" if len(pics) == 1 else "s"))
        mode = "edit"
    if mode in ("edit", "cutout") and not pics:    # a saved edit/cut-out mode + no picture (/image, voice): make it from text
        log(job, "no picture attached — making it from your words (text → image)")
        mode = "generate"
    wf = custom_workflow(job, "qimg", text, c, {"image": pics, "video": refs["video"], "audio": refs["audio"]},
                         *QIMG_ASPECT.get(aspect, (1024, 1024)), 0, steps)
    if wf:
        return wf
    comfy.ensure()
    if comfy.models("diffusion_models") and QIMG["dit"] not in comfy.models("diffusion_models"):
        raise RuntimeError("Qwen-Image 2.1 weights missing in ComfyUI models/diffusion_models")
    if mode == "cutout":
        prompt, use = CUTOUT_PROMPT, pics[:1]
    elif mode == "edit":
        ask_ = text or "Improve this image: sharper detail, better lighting, keep the subject identical"
        if rawmode:
            prompt = ask_
        else:
            log(job, "engine studying your %d picture%s …" % (len(pics), "" if len(pics) == 1 else "s"))
            prompt = prompts.qwen_edit(core.ask, ask_, pics)
        use = pics
    else:
        if not text:
            raise RuntimeError("describe the image to generate")
        if rawmode:
            prompt = text
        else:
            log(job, "engine rewriting the prompt (official 8-step method) …")
            ratio, prompt = prompts.qwen_t2i(core.ask, text, aspect if aspect_set else None)
            if ratio in QIMG_ASPECT and not aspect_set:
                aspect = ratio
        use = None
    prepare_gpu(job)
    entry, dt, wh = qimg_render(job, prompt, c, aspect, steps, seed, use, {"generate": "qimg", "edit": "qimg_edit", "cutout": "qimg_cutout"}[mode])
    name = save(entry, {"generate": "qimg", "edit": "qimg_edit", "cutout": "qimg_cutout"}[mode], ".png", job,
                {"mode": mode, "seed": seed, "prompt_used": prompt[:3000]})
    if c.get("upscale") in ("1.5", "2"):
        log(job, "upscaling %s× …" % c["upscale"])
        p_ = os.path.join(core.LIB, name)
        k = float(c["upscale"])
        ffmpeg(["-i", p_, "-vf", "scale=trunc(iw*%.2f/2)*2:trunc(ih*%.2f/2)*2:flags=lanczos" % (k, k), p_ + ".up.png"], 300)
        os.replace(p_ + ".up.png", p_)
        wh = (int(wh[0] * k) // 2 * 2, int(wh[1] * k) // 2 * 2)
    head = {"generate": "Qwen-Image 2.1 · %s %dx%d" % (aspect, wh[0], wh[1]),
            "edit": "Qwen-Image 2.1 EDIT · %d input picture%s" % (len(pics), "" if len(pics) == 1 else "s"),
            "cutout": "Qwen-Image 2.1 · background removed"}[mode]
    note = ("\n⚠ %d extra picture(s) ignored — Qwen-Image takes max 10" % dropped) if dropped else ""
    return {"files": [name], "text": "%s · %d steps · seed %d · %.1f min%s\n\nPROMPT%s:\n%s" % (
        head, steps, seed, dt / 60, note, "" if rawmode or mode == "cutout" else " (rewritten by the engine)", prompt)}


# ══ ACE-STEP 1.5 XL TURBO — text→music · remix · cover · voice swap ═════════
ACE = {"dit": "acestep_v1.5_xl_turbo_bf16.safetensors", "te1": "qwen_0.6b_ace15.safetensors",
       "te2": "qwen_4b_ace15.safetensors", "vae": "ace_1.5_vae.safetensors"}
core.apply_model_overrides(ACE)


def ace_graph(c, tags, lyrics, seed, bpm, secs, key, codes, strength, source=None, timbre=None):
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": ACE["dit"], "weight_dtype": "default"}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": float(c["shift"])}},
        "3": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": ACE["te1"], "clip_name2": ACE["te2"],
                                                         "type": "ace", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": ACE["vae"]}},
        "5": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {
            "clip": ["3", 0], "tags": tags, "lyrics": lyrics, "seed": seed, "bpm": bpm, "duration": secs,
            "timesignature": c["timesig"], "language": c["language"], "keyscale": key, "generate_audio_codes": codes,
            "cfg_scale": float(c["lm_cfg"]), "temperature": float(c["temperature"]), "top_p": float(c["top_p"]),
            "top_k": int(c["top_k"]), "min_p": float(c["min_p"])}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveAudioMP3", "inputs": {"audio": ["9", 0], "filename_prefix": comfy.OUT_PREFIX + "/ace",
                                                        "quality": c["quality"]}},
    }
    positive = ["5", 0]
    if source:
        g["11"] = {"class_type": "LoadAudio", "inputs": {"audio": comfy.upload(source)}}
        g["7"] = {"class_type": "VAEEncodeAudio", "inputs": {"audio": ["11", 0], "vae": ["4", 0]}}
        if timbre == "self":
            g["12"] = {"class_type": "ReferenceTimbreAudio", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}}
            positive = ["12", 0]
        elif timbre:
            g["13"] = {"class_type": "LoadAudio", "inputs": {"audio": comfy.upload(timbre)}}
            g["14"] = {"class_type": "VAEEncodeAudio", "inputs": {"audio": ["13", 0], "vae": ["4", 0]}}
            g["12"] = {"class_type": "ReferenceTimbreAudio", "inputs": {"conditioning": ["5", 0], "latent": ["14", 0]}}
            positive = ["12", 0]
    else:
        g["7"] = {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": secs, "batch_size": 1}}
    g["8"] = {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": positive, "negative": ["6", 0],
              "latent_image": ["7", 0], "seed": seed, "steps": int(c["steps"]), "cfg": float(c["cfg"]),
              "sampler_name": c["sampler"], "scheduler": c["scheduler"], "denoise": strength}}
    return g


def run_ace(job):
    refs = split_refs(job)
    c = job["params"]
    guide_note(job, "ace", c)
    raw = job.get("prompt") or ""
    wf = custom_workflow(job, "ace", raw, c, refs)
    if wf:
        return wf
    secs, raw = flag(raw, r"--(\d{1,3})\s*s\b", float)
    if secs is None:
        secs, raw = music_len(raw)
    secs = secs or float(c["duration"])
    strength, raw = flag(raw, r"--strength\s+([0-9.]+)", float)
    bpm, raw = flag(raw, r"--bpm\s+(\d{2,3})", int)
    if bpm is None:
        bpm, raw = flag(raw, r"\b(\d{2,3})\s*bpm\b", int)
    s, raw = flag(raw, r"--seed\s+(\d+)", int)
    seed = seed_of(s if s is not None else c["seed"])
    rawmode = "--raw" in raw or bool(job.get("literal"))
    raw = raw.replace("--raw", "")
    key = c["key"] if c["key"] != "auto" else None
    m = re.search(r"\b([A-G][#b]?)\s+(major|minor)\b", raw)
    if m and not key:
        key = "%s %s" % (m.group(1), m.group(2).lower())
    bpm = bpm or (int(c["bpm"]) if c["bpm"] != "" else None)
    m = re.search(r"\b(\d{2,3})\s*bpm\b", raw, re.I)
    if m and not bpm:
        bpm = int(m.group(1))
    lyrics = ""
    m = re.search(r"\|\s*lyrics\s*:(.*)$", raw, re.I | re.S)
    if m:
        lyrics, raw = m.group(1).strip(), raw[:m.start()]
    lyrics = lyrics or attached_text(refs["text"])
    auds = refs["audio"]
    mode = c["mode"]
    if mode == "auto":
        if len(auds) >= 2 and re.search(r"\b(voice|sing|sung|clone|vocal)\b", raw, re.I):
            mode = "voice"
        elif auds:
            mode = "cover" if re.search(r"\b(cover|timbre|same voice|sound like)\b", raw, re.I) else "remix"
        else:
            mode = "text"
    if mode != "text" and not auds:
        raise RuntimeError("%s mode needs an attached audio track — use 📎" % mode)
    if mode == "voice" and len(auds) < 2:
        raise RuntimeError("voice swap needs 2 audio files: audio 1 = the song, audio 2 = the voice sample (10–30 s, clean vocal)")
    text = core.clean_ws(raw)
    tags = text or "energetic electronic dance track, punchy drums, bright synth leads"
    instr = bool(re.search(r"\binstrumental\b|\bno vocals\b", text, re.I))
    if mode == "text" and not rawmode:
        pics = refs["image"] + [video_frame(v) for v in refs["video"][:2]]
        mood = describe(pics, job)
        log(job, "engine writing tags%s …" % ("" if lyrics else " + lyrics"))
        b = prompts.ace(core.ask, tags + (("\nMood reference: " + mood) if mood else ""), secs, instrumental=instr)
        if b:
            tags = b["tags"]
            lyrics = lyrics or b["lyrics"]
            bpm = bpm or b["bpm"]
            key = key or b["key"]
    elif mode != "text":
        tags = re.sub(r"\b(remix|restyle|transform|convert|rework|reimagine|cover)\b( it| this)?( into| as)?( a| an)?",
                      "", tags, flags=re.I).strip(" ,.") or "same song, polished studio mix"
    lyrics = lyrics or "[instrumental]"
    bpm, key = bpm or 120, key or "C major"
    source = auds[0] if auds else None
    if source:
        secs = min(media_seconds(source) or secs, 300.0)
    st = strength if strength is not None else {"text": 1.0, "remix": c["remix"], "cover": c["cover"], "voice": c["voice"]}[mode]
    st = max(0.05, min(1.0, float(st)))
    codes = (mode == "text") if c["codes"] == "auto" else c["codes"] == "on"
    prepare_gpu(job)
    if ACE["dit"] not in comfy.models("diffusion_models"):
        raise RuntimeError("ACE-Step 1.5 XL weights missing in ComfyUI models/diffusion_models")
    timbre = {"cover": "self", "voice": auds[1] if len(auds) > 1 else None}.get(mode)
    if mode == "voice":
        vs = media_seconds(auds[1]) or 0
        if 0 < vs < 6:
            log(job, "note: the voice sample is only %.0f s — 10–30 s of clean singing matches the voice much better" % vs)
        elif vs > 45:
            log(job, "note: the voice sample is %.0f s — a clean 10–30 s vocal works best" % vs)
    log(job, "rendering %s · %.0fs · %d BPM · %s …" % (mode, secs, bpm, key))
    entry, dt = comfy.run(ace_graph(c, tags, lyrics, seed, bpm, secs, key, codes, st, source, timbre), "audio", job, 60 * 60)
    name = save(entry, "ace_" + mode, ".mp3", job, {"mode": mode, "seed": seed, "lyrics": lyrics[:4000], "tags": tags[:1000]})
    label = {"text": "text → music", "remix": "REMIX of the attached track", "cover": "COVER (source timbre kept)",
             "voice": "VOICE SWAP (song re-sung with audio 2's voice)"}[mode]
    tip = "\nToo much of the original singer left? raise strength · structure drifting? lower it." if mode == "voice" else ""
    return {"files": [name], "meta": {"lyrics": "" if lyrics == "[instrumental]" else lyrics, "style": tags[:500], "bpm": bpm, "key": key},
            "text": "ACE-Step 1.5 XL Turbo · %s · %.0fs · %d BPM · %s · strength %.2f · seed %d · %.1f min%s\n\nTAGS:\n%s\n\nLYRICS:\n%s" % (
        label, secs, bpm, key, st, seed, dt / 60, tip, tags, lyrics)}


import llm   # noqa: E402  (text model — standalone only)

def run_vace(job):
    """WAN VACE SWAP as its own model: picture + clip → the person in the clip becomes the person in the picture."""
    refs = split_refs(job)
    c = job["params"]
    text = core.clean_ws(job.get("prompt") or "")
    return run_vace_swap(job, c, text, refs["image"], refs["video"], bool(job.get("literal")))


RUNNERS = {"vace": run_vace, "h3": run_h3, "music3": run_music3, "qimg": run_qimg, "ace": run_ace, "llama": llm.run_llama}
