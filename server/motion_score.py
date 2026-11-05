r"""MOTION SCORE — the music bed + soft sound effects under a Diorama film (user ask Oct 28 2026).

One instrumental cue per chapter from ACE-Step 1.5 (local, through the Media Lab queue), all in one key, crossfaded on the
chapter boundaries. The bed sits low under the narrator, swells gently when the story changes place, and plays fuller over the
intro and the end card. The gold sound words (BOOM, WHOOSH, TICK…), the walks across town, shocks and the gold panels get soft
effects from the bundled royalty-free Pixabay set (SYSTEM\claude-skills\hyperframes-media\assets\sfx, Pixabay Content License).
Everything is pre-mixed into ONE track (library mgscore_*.mp3) that motion_wizard.build_dio_project lays under the voice.
Cues are cached per chapter (prompt + length), so re-timing a film only re-runs the fast ffmpeg mix.
"""
import hashlib
import os
import re
import shutil
import subprocess
import time

import core

import engines
SFX_DIR = engines.sfx() or ""      # optional: your own sound-effect folder; empty = music bed only
FF = core.FFMPEG
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
KEYS = ["D minor", "A minor", "E minor", "C minor", "F major", "G major"]
MOOD_MUSIC = {"calm": "slow ambient piano, soft warm pads, gentle, 72 bpm", "sad": "slow melancholic piano, soft strings, 68 bpm",
              "wonder": "light pizzicato strings, glassy synth arpeggio, warm pads, curious and uplifting, 92 bpm",
              "happy": "light plucked guitar, soft marimba, warm pads, gently upbeat, 98 bpm",
              "stressed": "tense pulsing synth bass, low string ostinato, soft ticking percussion, suspense, 108 bpm",
              "scared": "dark drones, low pulsing strings, sparse percussion hits, suspense, 100 bpm",
              "angry": "driving low strings, tense pulses, muted drums, 112 bpm", "surprised": "suspenseful pulses, rising strings, 104 bpm",
              "focused": "minimal electronic underscore, soft arpeggio, steady pulse, documentary, 90 bpm",
              "neutral": "minimal cinematic underscore, soft piano and pads, steady, 88 bpm"}
PLACE_MUSIC = {"apartment": "late-night lo-fi texture, intimate", "office": "modern corporate minimal, clean", "lab": "clean electronic textures, subtle glitches",
               "cafe": "warm jazzy brushes and upright bass", "street": "urban downtempo groove, city ambience", "rooftop": "wide cinematic strings, hopeful swell"}
SFX_WORDS = [(r"BOOM|BAM|BANG|BONK|SLAM|THUD|CRASH|POW|SMASH", "impact-bass-1", .55), (r"BA-?DUM|THUMP|DUM", "impact-bass-2", .4),
             (r"WHOO+SH|SWOO+SH|ZOOM|WHIZ|VROOM", "whoosh-short", .55), (r"TICK|TOCK|CLICK|CLACK|TAP", "click-soft", .6),
             (r"DING|CHIME|BELL", "chime", .45), (r"BEEP|PING|BLIP", "ping", .45), (r"TYPE|TAP-?TAP|CLACK", "typing", .45),
             (r"HUM+|BUZZ+|DRONE", "riser", .18), (r"!|\?|GASP|WOW|HUH|OH", "pop", .45)]


def chapters(p):
    """The film's chapters (the writer's, or runs of lines in one place) with their timing, mood and place."""
    beats = [b for b in p["beats"] if b["kind"] != "endcard" and b.get("t1") is not None]
    if not beats:
        return []
    groups, cur = [], [beats[0]]
    for b in beats[1:]:
        same = (b.get("ch") == cur[-1].get("ch")) if b.get("ch") is not None and cur[-1].get("ch") is not None else b.get("place") == cur[-1].get("place")
        if same or len(cur) < 4:
            cur.append(b)
        else:
            groups.append(cur)
            cur = [b]
    groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        moods, places = {}, {}
        for b in g:
            moods[b.get("mood") or "neutral"] = moods.get(b.get("mood") or "neutral", 0) + 1
            places[b.get("place") or "apartment"] = places.get(b.get("place") or "apartment", 0) + 1
        out.append({"i": i, "t0": float(g[0]["t0"]), "t1": float(g[-1]["t1"]), "mood": max(moods, key=moods.get), "place": max(places, key=places.get),
                    "last": i == len(groups) - 1, "first": i == 0})
    return out


def cue_prompt(ch, key):
    mood = MOOD_MUSIC.get(ch["mood"], MOOD_MUSIC["neutral"])
    arc = " Builds slowly, then resolves warmly, emotional ending." if ch["last"] else " Opens softly." if ch["first"] else ""
    return ("Instrumental cinematic underscore for a narrated animated film, no vocals, soft and sparse so a voice sits on top. %s. %s. "
            "In %s.%s" % (mood, PLACE_MUSIC.get(ch["place"], ""), key, arc))


def sfx_events(p, intro):
    """(time, sound, volume) for the film: sound words, shocks, walks across town, panel pop-ins."""
    ev, beats = [], [b for b in p["beats"] if b["kind"] != "endcard" and b.get("t1") is not None]
    for i, b in enumerate(beats):
        cue = float(b.get("cue_t") if b.get("cue_t") is not None else b["t0"] + .25)
        if b.get("sfx"):
            w = str(b["sfx"]).upper()
            for pat, snd, vol in SFX_WORDS:
                if re.search(pat, w):
                    ev.append((intro + cue, snd, vol))
                    break
        if b.get("fx") == "impact":
            ev.append((intro + cue, "impact-bass-2", .5))
        if b.get("fx") == "route":
            ev.append((intro + b["t0"], "sparkle", .35))
        if i and b.get("place") != beats[i - 1].get("place"):           # the walk across town
            ev.append((intro + max(0, b["t0"] - .4), "whoosh-cinematic", .28))
        if b.get("panel") and i % 2 == 0:                              # a soft click on every other gold panel
            ev.append((intro + cue + .05, "click-soft", .22))
    return ev


def _len(path):
    try:
        out = subprocess.run([core.FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, creationflags=NO_WINDOW).stdout
        return float(out.strip() or 0)
    except Exception:
        return 0.0


def build(p, log, save, stop, sid, run_job):
    """Compose (or reuse) a cue per chapter, then mix cues + effects into one score track → p["score_lib"]."""
    import motion_wizard as w
    chs = chapters(p)
    if not chs:
        return
    intro = w.INTRO_DUR if p.get("intro", True) else 0.0
    story = max(float(b.get("t1") or 0) for b in p["beats"] if b["kind"] != "endcard")
    ends = sum(float(b.get("dur") or 6) for b in p["beats"] if b["kind"] == "endcard")
    total = intro + story + .3 + ends
    d = os.path.join(core.DATA, "motion_wizard", "score", p["id"])
    os.makedirs(d, exist_ok=True)
    key = p.get("score_key") or KEYS[int(hashlib.sha1(p["id"].encode()).hexdigest(), 16) % len(KEYS)]
    p["score_key"] = key
    cues = []
    for ch in chs:
        a = 0.0 if ch["first"] else intro + ch["t0"] - 1.2               # each cue starts a beat early to crossfade
        b = total if ch["last"] else intro + ch["t1"] + 1.5
        need = max(12.0, b - a)
        secs = int(min(240, need + 6))
        prompt = cue_prompt(ch, key)
        sig = hashlib.sha1(("%s|%d" % (prompt, round(secs / 10))).encode()).hexdigest()[:12]
        f = os.path.join(d, "cue_%d_%s.mp3" % (ch["i"], sig))
        if not os.path.isfile(f):
            if stop():
                raise InterruptedError()
            p["stage_note"] = "scoring chapter %d/%d · %s" % (ch["i"] + 1, len(chs), ch["mood"])
            save(p)
            out = run_job({"model": "ace", "prompt": prompt, "override": {"mode": "text", "duration": secs}}, stop, "music %d" % (ch["i"] + 1), sid)
            src = next((x for x in out if x.lower().endswith((".mp3", ".wav", ".flac", ".ogg"))), out[0])
            shutil.copy2(src, f)
            log(p, "music for chapter %d/%d ready · %s, %s" % (ch["i"] + 1, len(chs), ch["mood"], ch["place"]), "done")
        cues.append({"f": f, "a": a, "b": b, "first": ch["first"], "last": ch["last"]})
    # ── the mix: cues crossfaded, the bed ducked under the narrator, effects on top (skipped when nothing changed) ──
    ev0 = sfx_events(p, intro) if p.get("score_sfx", True) else []
    msig = hashlib.sha1(repr(([(c["f"], round(c["a"], 2), round(c["b"], 2)) for c in cues], [(round(a_, 2), s_, v_) for a_, s_, v_ in ev0], round(total, 2))).encode()).hexdigest()[:16]
    if p.get("score_sig") == msig and p.get("score_lib") and os.path.isfile(os.path.join(core.LIB, p["score_lib"])):
        return
    p["stage_note"] = "mixing the score"
    save(p)
    base, full = .15, .8
    bounds = [intro + ch["t0"] for ch in chs[1:]]
    swell = "+".join("0.22*exp(-pow((t-%.2f)/1.1,2))" % c for c in bounds) or "0"
    end = intro + story + .3
    vol = ("if(lt(t,%.2f),%.2f,if(lt(t,%.2f),%.2f-(%.2f)*(t-%.2f)/1.4,if(gt(t,%.2f),min(%.2f,%.2f+(t-%.2f)*0.5),%.2f+%s)))"
           % (intro - .6, full, intro + .8, full, full - base, intro - .6, end, full, base, end, base, swell))
    args, fil, labels = [FF, "-v", "error", "-y"], [], []
    for i, c in enumerate(cues):
        args += ["-stream_loop", "-1", "-i", c["f"]]
        ln = c["b"] - c["a"]
        fi, fo = (.05 if c["first"] else 1.6), (3.0 if c["last"] else 1.8)
        fil.append("[%d:a]atrim=0:%.2f,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-20:TP=-2:LRA=11,"
                   "afade=t=in:st=0:d=%.2f,afade=t=out:st=%.2f:d=%.2f,adelay=%d|%d[c%d]" % (i, ln, fi, max(0, ln - fo), fo, int(c["a"] * 1000), int(c["a"] * 1000), i))
        labels.append("[c%d]" % i)
    fil.append("%samix=inputs=%d:normalize=0,volume='%s':eval=frame[mus]" % ("".join(labels), len(labels), vol))
    ev = sfx_events(p, intro) if p.get("score_sfx", True) else []
    files = sorted({s for _, s, _ in ev if os.path.isfile(os.path.join(SFX_DIR, s + ".mp3"))})
    n0, mixl = len(cues), ["[mus]"]
    for k, s in enumerate(files):
        args += ["-i", os.path.join(SFX_DIR, s + ".mp3")]
        evs = [e for e in ev if e[1] == s]
        fil.append("[%d:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit=%d%s" % (n0 + k, len(evs), "".join("[s%d_%d]" % (k, j) for j in range(len(evs)))) if len(evs) > 1
                   else "[%d:a]aformat=sample_rates=44100:channel_layouts=stereo[s%d_0]" % (n0 + k, k))
        for j, (tt, _, v) in enumerate(evs):
            fil.append("[s%d_%d]volume=%.2f,adelay=%d|%d[e%d_%d]" % (k, j, v, int(tt * 1000), int(tt * 1000), k, j))
            mixl.append("[e%d_%d]" % (k, j))
    fil.append("%samix=inputs=%d:normalize=0,alimiter=limit=0.9[out]" % ("".join(mixl), len(mixl)))
    name = core.new_name("mgscore", ".mp3")
    dst = os.path.join(core.LIB, name)
    script = os.path.join(d, "mix.txt")
    open(script, "w", encoding="utf-8").write(";\n".join(fil))
    r = subprocess.run(args + ["-filter_complex_script", script, "-map", "[out]", "-t", "%.2f" % total, "-c:a", "libmp3lame", "-b:a", "192k", dst],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError("score mix failed: %s" % (r.stderr or "")[-300:])
    meta = {"user": p["user"], "model": "ace", "mode": "motion-score", "prompt": "score · " + (p.get("title") or "")[:200], "created": time.time()}
    if sid:
        meta["session"] = sid
    core.index_add(name, meta)
    old = p.get("score_lib")
    p["score_lib"] = name
    p["score_info"] = {"cues": len(cues), "sfx": len(ev), "key": key, "secs": round(total, 1)}
    p["score_sig"] = msig
    if old and old != name:                                             # the previous mix is replaced, not kept around
        try:
            os.remove(os.path.join(core.LIB, old))
            ix = core.index()
            if ix.pop(old, None) is not None:
                core.save_json(core.INDEX_FILE, ix)
        except Exception:
            pass
    log(p, "score mixed · %d music cues in %s · %d sound effects" % (len(cues), key, len(ev)), "done")
    p["stage_note"] = ""
