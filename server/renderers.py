"""The four generators. Graph logic is ported from MirOS (same verified node graphs),
re-homed so every input comes from data/refs and every output lands in data/library.

Each run_<model>(job) reads job['prompt'], job['refs'] (names in data/refs) and
job['params'] (resolved ⚙ values) and returns {"files": [...], "text": summary}.
"""
import os
import re
import subprocess
import time

import comfy
import core
import params
import prompts

# ── shared helpers ─────────────────────────────────────────────────────────


def log(job, msg):
    job["log"] = (job.get("log") or "") + msg + "\n"
    job["stage"] = msg


def split_refs(job):
    out = {"image": [], "video": [], "audio": [], "text": []}
    for n in (job.get("refs") or [])[:16]:
        p = core.in_dir(core.REFS, n)
        k = core.kind_of(n) if p else None
        if k:
            out[k].append(p)
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
        ffmpeg(["-ss", "%.2f" % at, "-i", path, "-frames:v", "1", out], 60)
    except RuntimeError:
        ffmpeg(["-i", path, "-frames:v", "1", out], 60)
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
    if not core.engine_sees():       # text-only engine (MUSE / Llama 3.1): no guessing about pictures it can't see
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
    meta.update(extra or {})
    core.index_add(name, meta)
    return name


def prepare_gpu(job):
    log(job, "freeing VRAM …")
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
H3 = {"unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
      "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
      "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
      "r2v_unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
      "r2v_lora": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"}
H3_FLF_LORA = {"turbo4": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
               "turbo8": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"}
H3_ASPECTS = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "21:9": 21 / 9}
H3_RES = {"draft": 0.25, "standard": 0.4, "high": 0.6, "max": 0.98}
H3_STEPS = {"turbo4": 4, "turbo8": 8, "full": 20}
H3_SHORT = {"vertical": ("aspect", "9:16"), "portrait": ("aspect", "9:16"), "square": ("aspect", "1:1"),
            "landscape": ("aspect", "16:9"), "wide": ("aspect", "16:9"), "cinema": ("aspect", "21:9"),
            "silent": ("audio", "off"), "mute": ("audio", "off"), "fast": ("quality", "turbo4"),
            "turbo4": ("quality", "turbo4"), "turbo8": ("quality", "turbo8"), "full": ("quality", "full"),
            "best": ("quality", "full"), "draft": ("res", "draft"), "hd": ("res", "high"), "max768": ("res", "max"),
            "t2v": ("mode", "t2v"), "i2v": ("mode", "i2v"), "flf2v": ("mode", "flf2v"), "r2v": ("mode", "r2v"),
            "raw": ("enhance", "off"), "handheld": ("steady", "off")}
H3_VALUE = {"seconds", "aspect", "res", "quality", "steps", "sampler", "scheduler", "seed", "style", "trim", "mode",
            "lora_strength", "ref_size"}
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


def aspect_of(img, default):
    try:
        from PIL import Image
        iw, ih = Image.open(img).size
        return min(H3_ASPECTS, key=lambda a: abs(H3_ASPECTS[a] - iw / ih))
    except Exception:
        return default


def h3_graph(cond_node, unet, lora, c, seed, sched, silent):
    g = dict(cond_node)
    g["unet"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
    model = ["unet", 0]
    if lora and c["lora_strength"] > 0:
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": lora,
                                                                     "strength_model": c["lora_strength"]}}
        model = ["lora", 0]
    g["clip"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": H3["clip"], "type": "minimax", "device": "default"}}
    g["vvae"] = {"class_type": "VAELoader", "inputs": {"vae_name": H3["vae"]}}
    g["avae"] = {"class_type": "VAELoader", "inputs": {"vae_name": H3["audio_vae"]}}
    g["guider"] = {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": ["cond", 0]}}
    g["noise"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    g["sampler"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": c["sampler"]}}
    g["sched"] = {"class_type": "BasicScheduler", "inputs": {"model": model, "scheduler": sched,
                                                             "steps": c["steps"], "denoise": 1.0}}
    g["sample"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise", 0], "guider": ["guider", 0],
                   "sampler": ["sampler", 0], "sigmas": ["sched", 0], "latent_image": ["cond", 1]}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vvae", 0]}}
    vin = {"images": ["dec", 0], "fps": 24}
    if not silent:
        g["deca"] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["sample", 0], "vae": ["avae", 0]}}
        vin["audio"] = ["deca", 0]
    g["video"] = {"class_type": "CreateVideo", "inputs": vin}
    g["save"] = {"class_type": "SaveVideo", "inputs": {"video": ["video", 0], "filename_prefix": comfy.OUT_PREFIX + "/h3",
                                                       "format": "auto", "codec": "auto"}}
    return g


def run_h3(job):
    refs = split_refs(job)
    text, c = h3_settings(job.get("prompt") or "", job["params"])
    script = attached_text(refs["text"])
    if script:
        text = (text + "\n" + script).strip()
    text = text or "a slow cinematic flight through a glowing neon city at night"
    imgs, vids, auds = refs["image"], refs["video"], refs["audio"]
    mode = c["mode"]
    if mode == "auto":
        mode = "r2v" if (imgs or vids) else "t2v"
    log(job, "MiniMax H3 · %s" % mode)
    comfy.ensure()
    first = last = src = None
    img_names, vid_names, prepped = [], [], []
    aspect = "" if c["aspect"] == "auto" else c["aspect"]
    if mode == "i2v":
        if not imgs:
            raise RuntimeError("image → video needs a picture — attach one with 📎")
        src = imgs[0]
        aspect = aspect or aspect_of(src, "16:9")
    elif mode == "flf2v":
        if len(imgs) < 2:
            raise RuntimeError("first + last frame needs 2 attached pictures (picture 1 = first, picture 2 = last)")
        src = imgs[0]
        aspect = aspect or aspect_of(src, "16:9")
    elif mode == "r2v":
        if not (imgs or vids):
            raise RuntimeError("reference mode needs attached pictures or clips — use 📎")
        if H3["r2v_unet"] not in comfy.models("diffusion_models"):
            raise RuntimeError("reference mode needs %s in ComfyUI" % H3["r2v_unet"])
        if not aspect and imgs and not vids:
            aspect = aspect_of(imgs[0], "16:9")
    aspect = aspect or "16:9"
    sched = c["scheduler"] if c["scheduler"] != "auto" else ("beta" if mode == "r2v" and c["quality"] == "full" else "simple")
    w, h = h3_dims(c["mp"], aspect)
    length = h3_frames(c["seconds"])
    soundtrack = auds[0] if (auds and c["soundtrack"] != "ignore") else None
    silent = c["audio"] == "off" or (soundtrack and c["soundtrack"] == "replace")

    built = None
    if c["enhance"] == "on" and mode != "r2v":
        log(job, "engine directing the shot list …")
        built = prompts.h3(core.ask, text, int(c["seconds"]), first_frame=src)
    steady = c["steady"] == "on"
    prompt = "Cinematic, photorealistic, smooth natural motion, detailed lighting. "
    if steady:
        prompt += "Steady camera, level horizon, upright framing. "
    if mode == "r2v":
        if not re.search(r"<(Picture|Video)\s*\d+>", text, re.I):
            tags = []
            if imgs:
                tags.append("Use %s as the visual references for the exact identity and appearance of the subjects "
                            "(match faces, hair and features precisely; treat them as subject references, not as the "
                            "background or pose)." % ", ".join("<Picture %d>" % (i + 1) for i in range(min(9, len(imgs)))))
            if vids:
                tags.append("Use %s as the reference for motion, camera movement, framing and scene."
                            % ", ".join("<Video %d>" % (i + 1) for i in range(min(3, len(vids)))))
            prompt += " ".join(tags) + " "
        prompt += text + ". Keep every face stable, sharp and undistorted in every frame."
    elif built:
        prompt = built + ("\nCAMERA NOTE: steady camera, level horizon, upright framing." if steady else "")
    else:
        prompt += text + "."
    if not silent:
        if c["audio"] == "custom" and c["audio_text"].strip():
            prompt += " AUDIO: " + c["audio_text"].strip() + "."
        elif not built and not re.search(r"\b(audio|sound|music|voice|silent)\b", text, re.I):
            prompt += " AUDIO: fitting ambient sound effects and subtle music."
    if c["style"] != "none":
        prompt += " embedding:minimaxh3_" + c["style"]

    prepare_gpu(job)
    try:
        if mode == "r2v":
            log(job, "uploading references …")
            img_names = [comfy.upload(p) for p in imgs[:9]]
            for p in vids[:3]:
                pp = os.path.join(core.REFS, "_prep_%d.mp4" % int(time.time() * 1000))
                vf = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=24" % (w, h, w, h)
                ffmpeg(["-i", p, "-t", str(min(10, c["seconds"] + 1)), "-vf", vf, "-c:v", "libx264", "-crf", "16",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", pp], 180)
                prepped.append(pp)
                vid_names.append(comfy.upload(pp))
            node = {"cond": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
                "clip": ["clip", 0], "vae": ["vvae", 0], "audio_vae": ["avae", 0], "prompt": prompt,
                "width": w, "height": h, "length": length, "ref_image_size": c["ref_size"]}}}
            for i, n in enumerate(img_names):
                node["img%d" % i] = {"class_type": "LoadImage", "inputs": {"image": n}}
                node["cond"]["inputs"]["ref_images.ref_image_%d" % i] = ["img%d" % i, 0]
            for i, n in enumerate(vid_names):
                node["vid%d" % i] = {"class_type": "LoadVideo", "inputs": {"file": n}}
                node["vparts%d" % i] = {"class_type": "GetVideoComponents", "inputs": {"video": ["vid%d" % i, 0]}}
                node["cond"]["inputs"]["ref_videos.ref_video_%d" % i] = ["vparts%d" % i, 0]
            unet, lora = H3["r2v_unet"], (H3["r2v_lora"] if c["quality"] != "full" else None)
        else:
            node = {"cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                "clip": ["clip", 0], "vae": ["vvae", 0], "prompt": prompt, "width": w, "height": h, "length": length}}}
            if mode in ("i2v", "flf2v"):
                node["ff"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(imgs[0])}}
                node["cond"]["inputs"]["first_frame"] = ["ff", 0]
            if mode == "flf2v":
                node["lf"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(imgs[1])}}
                node["cond"]["inputs"]["last_frame"] = ["lf", 0]
            unet, lora = H3["unet"], H3_FLF_LORA.get(c["quality"])
        seed = seed_of(c["seed"])
        log(job, "rendering %dx%d · %.1fs · %s %d steps …" % (w, h, length / 24, c["quality"], c["steps"]))
        entry, dt = comfy.run(h3_graph(node, unet, lora, c, seed, sched, silent), "video", job)
        name = save(entry, "h3", ".mp4", job, {"mode": mode, "seed": seed, "size": "%dx%d" % (w, h)})
        path = os.path.join(core.LIB, name)
        if c["trim"] > 0:
            tmp = path + ".trim.mp4"
            ffmpeg(["-ss", "%.3f" % (c["trim"] / 24.0), "-i", path, "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", tmp], 180)
            os.replace(tmp, path)
        if soundtrack:
            log(job, "adding the attached soundtrack …")
            tmp = path + ".mux.mp4"
            if c["soundtrack"] == "mix" and not silent:
                ffmpeg(["-i", path, "-i", soundtrack, "-filter_complex",
                        "[0:a][1:a]amix=inputs=2:duration=first:weights=0.5 1[a]", "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", tmp], 180)
            else:
                ffmpeg(["-i", path, "-i", soundtrack, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                        "-shortest", tmp], 180)
            os.replace(tmp, path)
    finally:
        for p in prepped:
            try:
                os.remove(p)
            except OSError:
                pass
    label = {"t2v": "text → video", "i2v": "image → video", "flf2v": "first + last frame → video",
             "r2v": "reference → video (%d picture%s, %d clip%s)" % (len(img_names), "" if len(img_names) == 1 else "s",
                                                                      len(vid_names), "" if len(vid_names) == 1 else "s")}[mode]
    return {"files": [name], "text": "MiniMax H3 %s · %.1fs · %dx%d (%s) · %s %d steps · %s/%s · seed %d%s%s · %.1f min\n\nPROMPT:\n%s" % (
        label, max(0, length - c["trim"]) / 24, w, h, aspect, c["quality"], c["steps"], c["sampler"], sched, seed,
        " · style " + c["style"] if c["style"] != "none" else "",
        " · soundtrack " + os.path.basename(soundtrack).split("_", 2)[-1] if soundtrack else "",
        dt / 60, prompt[:3000])}


# ══ MINIMAX MUSIC 3.0 — full songs ═════════════════════════════════════════
MUSIC = {"dit": ["minimax_music3_dit_fp16.safetensors", "minimax_music3_dit_int8_convrot.safetensors"],
         "te": "minimax_music3_text_encoder_pruned_int8_convrot.safetensors", "vae": "minimax_music3_dav.safetensors"}


def run_music3(job):
    refs = split_refs(job)
    c = job["params"]
    raw = job.get("prompt") or ""
    secs, raw = flag(raw, r"--(\d{1,3})\s*s\b", float)
    if secs is None:
        secs, raw = music_len(raw)
    secs = max(10.0, min(300.0, secs or float(c["duration"])))
    s, raw = flag(raw, r"--seed\s+(\d+)", int)
    seed = seed_of(s if s is not None else c["seed"])
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
    if not lyrics or instr:
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
              "seed": seed, "max_duration": secs, "cfg_scale": float(c["lm_cfg"]), "top_k": int(c["top_k"])}},
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
    return {"files": [name], "text": "MiniMax Music 3 (%s) · up to %ds · seed %d · %.1f min\n\nCAPTION:\n%s\n\nLYRICS:\n%s" % (
        "fp16" if "fp16" in dit else "int8", secs, seed, dt / 60, caption, lyrics)}


# ══ QWEN IMAGE 2.1 — t2i · edit · cutout ═══════════════════════════════════
QIMG = {"dit": "qwen_image_2.1_int8_convrot.safetensors", "te": "qwen3vl_8b_int8_convrot.safetensors",
        "vae": "qwen_image_2.1_vae_bf16.safetensors"}
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
    rawmode = "--raw" in raw or c["enhance"] == "off"
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
    if mode in ("edit", "cutout") and not pics:
        raise RuntimeError("attach a picture with 📎 to %s" % ("edit" if mode == "edit" else "cut out"))
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
    head = {"generate": "Qwen-Image 2.1 · %s %dx%d" % (aspect, wh[0], wh[1]),
            "edit": "Qwen-Image 2.1 EDIT · %d input picture%s" % (len(pics), "" if len(pics) == 1 else "s"),
            "cutout": "Qwen-Image 2.1 · background removed"}[mode]
    note = ("\n⚠ %d extra picture(s) ignored — Qwen-Image takes max 10" % dropped) if dropped else ""
    return {"files": [name], "text": "%s · %d steps · seed %d · %.1f min%s\n\nPROMPT%s:\n%s" % (
        head, steps, seed, dt / 60, note, "" if rawmode or mode == "cutout" else " (rewritten by the engine)", prompt)}


# ══ ACE-STEP 1.5 XL TURBO — text→music · remix · cover · voice swap ═════════
ACE = {"dit": "acestep_v1.5_xl_turbo_bf16.safetensors", "te1": "qwen_0.6b_ace15.safetensors",
       "te2": "qwen_4b_ace15.safetensors", "vae": "ace_1.5_vae.safetensors"}


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
    raw = job.get("prompt") or ""
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
    rawmode = "--raw" in raw
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
    log(job, "rendering %s · %.0fs · %d BPM · %s …" % (mode, secs, bpm, key))
    entry, dt = comfy.run(ace_graph(c, tags, lyrics, seed, bpm, secs, key, codes, st, source, timbre), "audio", job, 60 * 60)
    name = save(entry, "ace_" + mode, ".mp3", job, {"mode": mode, "seed": seed, "lyrics": lyrics[:4000], "tags": tags[:1000]})
    label = {"text": "text → music", "remix": "REMIX of the attached track", "cover": "COVER (source timbre kept)",
             "voice": "VOICE SWAP (song re-sung with audio 2's voice)"}[mode]
    tip = "\nToo much of the original singer left? raise strength · structure drifting? lower it." if mode == "voice" else ""
    return {"files": [name], "text": "ACE-Step 1.5 XL Turbo · %s · %.0fs · %d BPM · %s · strength %.2f · seed %d · %.1f min%s\n\nTAGS:\n%s\n\nLYRICS:\n%s" % (
        label, secs, bpm, key, st, seed, dt / 60, tip, tags, lyrics)}


import llm   # noqa: E402  (text model — standalone only)

RUNNERS = {"h3": run_h3, "music3": run_music3, "qimg": run_qimg, "ace": run_ace, "llama": llm.run_llama}
