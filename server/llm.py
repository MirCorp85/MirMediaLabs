"""MUSE — the writer-in-residence of MIR MEDIA LABS (standalone only; not in the MirOS copy).

General chat + creative writing on a local Ollama model (today: Llama 3.1 8B). Runs as a normal lab job: it waits
its turn in the one-at-a-time GPU queue, frees ComfyUI's VRAM first, and streams its reply into job['output'].

Its system prompt has three layers:
  1. SOUL       — muse_soul.md: identity, purpose, values, voice, boundaries (plain text, edit freely; re-read
                  every reply, no restart needed).
  2. KNOWLEDGE  — built live from the lab catalog (skills.ROLES / params.MODELS / skills / pipelines / commands),
                  so swapping an engine updates what MUSE knows. Per-engine prompt craft lives in CRAFT, keyed by
                  engine id (back end specific; MUSE talks about roles, not engine names).
  3. SESSION    — who is talking (owner / guest name), today's date, the engine under MUSE, the mode.
"""
import json
import re
import os
import time

import comfy
import core
import params
import skills

MODEL_TAG = "llama3.1:8b"
PERSONA = "MUSE"
SOUL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muse_soul.md")
NUM_CTX = 16384
HISTORY_CHARS = 24000          # newest turns first, within the context budget
LENGTH = {"short": 450, "medium": 1200, "long": 2800}

MODE = {
    "chat": "Mode: conversation. Be clear, warm and concise; lead with the answer.",
    "creative": ("Mode: creative writing. Deliver the finished piece itself — vivid, original, polished — with a title when it "
                 "fits and no preamble or commentary; at most one short line afterwards about the next step in the lab."),
}

# How to write for each engine — distilled from the official prompt guides in prompts.py. Keyed by ENGINE id:
# when a role gets a new engine, add its entry here (a missing entry falls back to GENERIC by output kind).
CRAFT = {
    "qimg": ("Describe the finished picture as an observer: open with format, style and subject; place each element "
             "(upper-left, centre, lower third...); colours with modifiers and materials; one sentence on the light. Text "
             "that must appear goes in double quotes. Say vertical, wide or square (or 9:16, 16:9, 1:1). Optional flags: "
             "--hd larger, --hq more detail, --raw skips the lab's prompt rewriter. Attach pictures to edit or restyle them; "
             "with several, say picture 1, picture 2."),
    "h3": ("Whole scene first; then the action in time order (e.g. [0-3s] ... [3-6s] ...); exactly ONE camera move "
           "(slow dolly-in, orbit, crane up, tracking shot, handheld follow, or a locked-off static shot); the light and "
           "look; the sounds you would hear (it makes native audio). Describe only what IS there - it cannot take 'no X'. "
           "On-screen text in double quotes. Length 4-15 s: write 8s or --8s. Optional: vertical, square or wide, --silent, "
           "--best (full quality, slower), --hd. Attach a picture and start with 'animate' to bring a picture to life."),
    "music3": ("Request: genre, mood, tempo feel, vocal type and instruments. Lyrics: section tags alone on their own line "
               "([Intro] [Verse] [Pre-Chorus] [Chorus] [Post-Chorus] [Bridge] [Outro]), a blank line between sections, "
               "6-10 syllables per line with steady lengths, backing vocals in (parentheses), only singable words. About "
               "30 s = one verse + chorus; 2 min = two verses and choruses; longer adds a bridge. Length works only as a flag: --90s "
               "(10-300 s); --instrumental for no vocals."),
    "ace": ("One line of style tags: genre, era, mood, 3-6 specific instruments, texture (warm, crisp, punchy), vocal type "
            "or 'instrumental', production style. Tempo and length work only as flags: --bpm 120 --30s (5-600 s); plain words like '100 bpm' or '30s' are ignored. Lyrics use the same "
            "section tags as Song. Attach a track to remix it (--strength 0.6 sets how far it moves) or cover it; attach a "
            "song plus a voice recording to swap the voice."),
}
GENERIC = {"image": "Describe subject, style, composition, light and colours; quote any text that must appear.",
           "video": "Scene, the action over time, one camera move, the light and the sound.",
           "audio": "Genre, mood, tempo, instruments and vocals."}

AROUND = """Around the lab:
- Attach button (paperclip): add pictures, clips, songs or text to a request. Parameters button (sliders): settings for the selected engine. On phones both live under the + button.
- Library: every result, with Download and Use as ref (feeds a result into the next request, e.g. picture -> video).
- Use as text ref (under your replies): attaches your text to the next request - lyrics to Song, a script to Video.
- LoRA samples: community style adapters for Image, Video and Music; picked ones apply to the next renders and add their trigger words automatically.
- The camcorder in the chat corner shows the lab's state: Standby (ready), STBY #n (waiting in line), REC with a timer (rendering), Cut - done, Tape error (failed), Off air (GPU engine down).
- Each person's results are private to them; the owner can see everything.
What the lab CANNOT do (say so plainly first, then offer the closest thing it can do): make 3D models or anything you can rotate or play with, edit or cut existing footage on a timeline (a clip can only guide motion as a reference), make videos longer than 15 s in one request, browse the internet, or remember other conversations. You yourself cannot see pictures or hear audio."""


LYRIC_TAGS = {"intro": "Intro", "verse": "Verse", "pre-chorus": "Pre-Chorus", "prechorus": "Pre-Chorus", "chorus": "Chorus",
              "post-chorus": "Post-Chorus", "postchorus": "Post-Chorus", "bridge": "Bridge", "outro": "Outro",
              "instrumental": "Instrumental", "solo": "Solo", "hook": "Chorus", "refrain": "Chorus"}
_TAG = re.compile(r"^\[\s*([A-Za-z-]+)(?:\s*\d+)?(?:\s*[-:–]\s*[^\]]{1,30})?\s*\]$")
_DIRECTION = re.compile(r"^\((?:soft|softly|whisper|whispered|whispering|spoken|speaking|quiet|quietly|gently|loud|loudly|shout|"
                        r"shouted|fade|fading|echo|echoing|repeat|humming|hum|ad-?libs?|x\s*\d)[^)]*\)\s*", re.I)


def _tag(line):
    m = _TAG.match(line)
    return "[%s]" % LYRIC_TAGS[m.group(1).lower()] if m and m.group(1).lower() in LYRIC_TAGS else None


def sanitize_lyrics(text):
    """Make lyrics exactly what the Song engine should sing: known section tags only (no numbers/modifiers), no stage
    directions in [brackets] or (delivery notes), nothing before the first section, one blank line between sections."""
    lines = [l.strip() for l in (text or "").replace("\r", "").split("\n")]
    if not any(_tag(l) for l in lines):
        return (text or "").strip()
    out = []
    for l in lines:
        t = _tag(l)
        if t:
            if out and out[-1] != "":
                out.append("")
            out.append(t)
            continue
        if not out:
            continue                                   # title / chatter before the first section
        if re.match(r"^\[.*\]$", l) or re.search(r"use as text ref", l, re.I) or l.startswith("/"):
            continue                                   # stage directions, hand-off hints, commands
        l = _DIRECTION.sub("", l).strip()
        if not l:
            if out[-1] != "" and not _tag(out[-1]):
                out.append("")
            continue
        out.append(l)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def clean_for_ref(text):
    """MUSE text attached with 'Use as text ref': lyrics → sanitized; anything else → minus the hand-off hint line."""
    if any(_tag(l.strip()) for l in (text or "").split("\n")):
        return sanitize_lyrics(text)
    return "\n".join(l for l in (text or "").split("\n") if not re.search(r"use as text ref", l, re.I)).strip()


def ready(tags):
    return any(t == MODEL_TAG or t.startswith(MODEL_TAG + "-") for t in tags or [])


# ── system prompt ──────────────────────────────────────────────────────────
def _soul():
    try:
        return open(SOUL_FILE, encoding="utf-8").read().strip()
    except OSError:
        return ("You are %s, the writer-in-residence of MIR MEDIA LABS, a private local creative studio. Help people write "
                "lyrics, stories, scripts and prompts for the lab's Image, Video, Song and Music engines. Be honest, "
                "original, warm and concise. Never use emoji." % PERSONA)


def _primary_cmd(role):
    return next((c for c, r in skills.ROLE_CMDS.items() if r == role), role)


def knowledge():
    """The lab as it is right now — generated from the catalog, never hard-coded engine names."""
    out = ["## Lab knowledge (live from the lab's catalog)",
           "Engines - talk about them by role; name the engine only if the person does:"]
    for role, r in skills.ROLES.items():
        eng = r["model"]
        m = params.MODELS.get(eng) or {}
        if role == "text":
            out.append("- %s (/chat, /write) - you." % r["label"])
            continue
        acc = "; ".join("%s = %s" % (k, v) for k, v in (m.get("accepts") or {}).items())
        out.append("- %s (/%s) - current engine: %s - %s.%s" % (r["label"], _primary_cmd(role), m.get("label", eng),
                                                                m.get("desc", ""), (" Accepts: " + acc + ".") if acc else ""))
        out.append("  How to write for it: " + CRAFT.get(eng, GENERIC.get(m.get("kind"), "")))
    out.append("Skills (one-tap presets; type /<name> <idea>):")
    for s in skills.SKILLS:
        out.append("- /%s - %s (%s)%s: %s" % (s["id"], s["name"], skills.ROLES[s["role"]]["label"],
                                             (" needs " + ", ".join("%d attached %s" % (n, k) for k, n in skills.needs_of(s).items())) if s.get("needs") else "", s["desc"]))
    out.append("Pipelines = step-by-step manuals (one request, several tools in a fixed order; type /<name> <idea>, or just"
               " describe it in Auto mode and the Director follows the manual). Each step gets its own inputs and"
               " carries the song's lyrics / tempo / key forward:")
    for p in skills.PIPELINES:
        need = ", ".join("%d attached %s" % (n, k) for k, n in skills.needs_of(p).items())
        out.append("- /%s - %s: %s. Use when: %s.%s" % (p["id"], p["name"], p["desc"], p.get("when", ""),
                                                      (" Needs " + need + " (the mic in the message box records one).") if need else ""))
        out += ["    " + s for s in skills.manual_text(p)]
        if p.get("knobs"):
            out.append("    Dials in the message box: " + ", ".join(k["label"] for k in p["knobs"]))
    out.append("Commands: " + "; ".join("%s %s = %s" % (c["cmd"], c["args"], c["desc"]) for c in skills.COMMANDS))
    out.append(AROUND)
    return "\n".join(out)


def session(job):
    who = job.get("who") or {}
    name = (who.get("name") or "").strip()
    if who.get("role") == "owner" or not name:
        person = "the lab's owner - the person who built MIR MEDIA LABS"
    else:
        person = "%s, a guest of the lab (their work is private to them)" % name
    eng = params.MODELS.get(skills.ROLES.get("text", {}).get("model", "llama"), {}).get("label", MODEL_TAG)
    eng = eng.split(" · ", 1)[-1] if eng.startswith(PERSONA) else eng      # "MUSE · LLAMA 3.1 8B" → "LLAMA 3.1 8B"
    mode = (job.get("params") or {}).get("mode")
    return "\n".join(["## This session",
                      "- You are talking with %s." % person,
                      "- Today is %s." % time.strftime("%A, %B %d, %Y"),
                      "- The model under you: %s, running locally." % eng,
                      "- Auto mode: people simply say what they want and YOU route it - pictures, short videos with "
                      "sound, full songs and beats go to the right engine automatically, everything else you answer. "
                      "So when asked what you or the lab can do, say exactly that: just tell me what you want made, or "
                      "ask me anything. Never tell people they must pick a model or type commands.",
                      "- " + MODE.get(mode, MODE["chat"])])


def system_prompt(job):
    return "\n\n".join([_soul(), knowledge(), session(job)])


# ── conversation ───────────────────────────────────────────────────────────
def _attached_text(job):
    out = []
    for n in (job.get("refs") or [])[:8]:
        p = core.in_dir(core.REFS, n)
        if p and core.kind_of(n) == "text":
            try:
                out.append(open(p, encoding="utf-8", errors="ignore").read()[:12000])
            except OSError:
                pass
    return out


def _history(job, turns):
    """The newest `turns` exchanges that fit the character budget, oldest first."""
    if turns <= 0:
        return []
    picked, used = [], 0
    for t in reversed((job.get("history") or [])[-turns:]):
        size = len(t["q"]) + len(t["a"])
        if used + size > HISTORY_CHARS:
            break
        picked.append(t)
        used += size
    return list(reversed(picked))


def messages(job):
    c = job.get("params") or {}
    msgs = [{"role": "system", "content": system_prompt(job)}]
    for t in _history(job, int(c.get("memory") or 0)):
        msgs.append({"role": "user", "content": t["q"]})
        msgs.append({"role": "assistant", "content": t["a"]})
    user = job.get("prompt") or ""
    docs = _attached_text(job)
    if docs:
        user += "".join("\n\n--- attached text %d ---\n%s" % (i + 1, d) for i, d in enumerate(docs))
    if any(core.kind_of(n) in ("image", "video", "audio") for n in job.get("refs") or []):
        user += "\n\n(Note from the lab: pictures, clips and songs were attached, but MUSE can only read attached text.)"
    msgs.append({"role": "user", "content": user or "Hello"})
    return msgs


def run_llama(job):
    import renderers                            # late import: renderers imports this module
    c = job["params"]
    msgs = messages(job)
    renderers.log(job, "freeing VRAM for MUSE …")
    if comfy.up():
        comfy.free()                             # ComfyUI keeps ~10 GB loaded between renders
    if not core.ollama_up():
        renderers.log(job, "starting Ollama …")
        if not core.ensure_ollama():
            raise RuntimeError("Ollama isn't running and could not be started")
    renderers.log(job, "MUSE is writing …")
    opts = {"temperature": float(c.get("temperature") or 0.7), "num_ctx": NUM_CTX,
            "num_predict": LENGTH.get(c.get("length"), 1200)}
    if c.get("seed") not in ("", None):
        opts["seed"] = int(c["seed"])
    body = {"model": MODEL_TAG, "messages": msgs, "stream": True, "options": opts, "keep_alive": "5m"}
    job["output"] = ""
    with core.requests.post(core.OLLAMA + "/api/chat", json=body, stream=True, timeout=(10, 600)) as r:
        if r.status_code == 404:
            raise RuntimeError("Llama 3.1 8B isn't installed in Ollama — run:  ollama pull " + MODEL_TAG)
        r.raise_for_status()
        for line in r.iter_lines():
            if job.get("_cancel"):
                raise comfy.Cancelled()
            if not line:
                continue
            d = json.loads(line)
            job["output"] += (d.get("message") or {}).get("content", "")
            if d.get("done"):
                break
    if job.get("skill") == "Song Lyrics":            # the lyrics skill's reply goes straight to the Song engine
        job["output"] = sanitize_lyrics(job["output"])
    job["stage"] = ""
    return {"files": [], "text": job["output"].strip()}
