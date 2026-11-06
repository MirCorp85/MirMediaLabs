"""MIR EXPLAINED episode builder — every generative asset from the lab itself (MIR_LAB_API, default 127.0.0.1:5400).

  python -I explained_build.py <slug> [vo|assets|resolve|all] [--plan-only]

episodes/<slug>/episode.json  ->  public/episodes/<slug>/ (VO, stills, H3 plates, music, SFX)
                              ->  src/explained/episodes/<slug>.json (resolved timeline the Remotion Episode renders)
Cached: anything already on disk is skipped, so re-running after a script edit only re-voices changed lines."""
import hashlib, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid, wave

# Clock times as SPOKEN words (Oct 29 2026, user: the narrator said "three thousand and seven AM" for 3:07 AM). Same rule as
# server/motion_wizard.py speakable() - this script runs isolated (python -I), so it keeps its own copy. On-screen text is
# untouched; only what the narrator reads changes (and the VO hash covers it, so only lines with times are re-recorded).
_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}
def _num_words(n):
    return _ONES[n] if n < 20 else _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
def speakable(text):
    def ampm(m):
        end = "." if (m or "").endswith(".") else ""; x = (m or "").lower().replace(".", "").replace(" ", "")
        return (" AM" if x == "am" else " PM" if x == "pm" else "") + end          # (a sentence-ending "A.M." keeps its full stop) Kokoro reads "AM" cleanly ("A.M." comes out as "A, M")
    def clock(m):
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59: return m.group(0)
        if mi == 0: return _num_words(h) + (ampm(m.group(3)) or " o'clock")
        return _num_words(h) + (" oh " + _ONES[mi] if mi < 10 else " " + _num_words(mi)) + ampm(m.group(3))
    text = re.sub(r"\b(\d{1,2}):(\d{2})(?:\s*([AaPp]\.?\s?[Mm]\.?))?(?![\d:])", clock, str(text or ""))
    return re.sub(r"\b(\d{1,2})\s*([AaPp]\.?\s?[Mm]\.?)(?=[\s,.;:!?]|$)", lambda m: (_num_words(int(m.group(1))) if int(m.group(1)) <= 24 else m.group(1)) + ampm(m.group(2)), text)

ROOT = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("MIR_LAB_API") or "http://127.0.0.1:5400"
LIB = os.environ.get("MIR_LIB") or os.path.join(os.path.dirname(ROOT), "data", "library")
_COMP = os.path.join(ROOT, "node_modules", "@remotion", "compositor-win32-x64-msvc" if os.name == "nt" else "compositor-linux-x64-gnu")
_EXE = ".exe" if os.name == "nt" else ""
FF = os.path.join(_COMP, "ffmpeg" + _EXE)
FP = os.path.join(_COMP, "ffprobe" + _EXE)
FULLFF = os.environ.get("MIR_FFMPEG") or ""   # the lab's full ffmpeg (Remotion's has no blur/overlay)
FFX = FULLFF if os.path.exists(FULLFF) else FF
MAX_REFS = 20                                                 # real reference photos per episode (more = fewer repeats)
SHARED = os.path.join(ROOT, "public", "explained")          # series-wide: ref photos, SFX library, sample plates
VO_GAIN_DB = 3.2                                              # Kokoro sits ~-24 dB RMS; lift it over the bed
PLAN = "--plan-only" in sys.argv
JSONP = "--json" in sys.argv
LINEART = ("Redraw this exact image as a precise technical line drawing: thin clean silver-white lines on a pure black background, every edge, panel line and component outlined, no shading, no color, no text, same framing and proportions, 16:9")


def prog(stage, item, ok=True, **kw):
    if JSONP:
        print("@@" + json.dumps(dict(stage=stage, item=item, ok=ok, t=time.time(), **kw)), flush=True)


def call(path, body=None, raw=False):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read() if raw else json.loads(r.read())


def run(body, label):
    body = dict(body, internal=True, fresh=True)
    if os.environ.get("EXPLAINED_SESSION"):          # the project's own Media Lab chat session (never the open one)
        body["session"] = os.environ["EXPLAINED_SESSION"]
    while True:
        try:
            j = call("/api/generate", body); break
        except urllib.error.HTTPError as e:
            if e.code == 409: time.sleep(10); continue
            raise RuntimeError("%s: %s" % (label, e.read()[:300]))
    jid, t0 = j["id"], time.time()
    while True:
        time.sleep(5)
        j = call("/api/jobs/" + jid)
        if j["status"] in ("done", "error", "cancelled"):
            break
    print("%-12s %s %.0fs %s" % (label, j["status"], time.time() - t0, j.get("files")), flush=True)
    if j["status"] != "done" or not j.get("files"):
        raise RuntimeError(label + " failed: " + str(j.get("log", ""))[-400:])
    return j["files"]


def pick(files, exts):
    return next(f for f in files if os.path.splitext(f)[1].lower() in exts)


_UP = {}
def upload(path):
    if path in _UP: return _UP[path]
    b = uuid.uuid4().hex
    ext = os.path.splitext(path)[1].lower()
    ctype = {".webp": "image/webp", ".png": "image/png"}.get(ext, "image/jpeg")
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API + "/api/upload", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b}, method="POST")
    _UP[path] = json.loads(urllib.request.urlopen(req, timeout=60).read())["name"]
    return _UP[path]


# ── 16:9 guard (Oct 17: a portrait ref → portrait Qwen still → H3 squeezed it into 16:9 = stretched engineer).
# Qwen edit keeps the FIRST ref's shape, H3 i2v forces 16:9, so: refs are padded to 16:9 before Qwen, and every still
# and plate is checked afterwards — never stretched, only cropped (close to 16:9) or blur-padded (far from it).
W169, H169 = 1920, 1080
COVER = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1" % (W169, H169, W169, H169)
BLURPAD = ("split[a][b];[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=40:3,eq=brightness=-0.12[bg];"
           "[b]scale=%d:%d:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
           % (W169, H169, W169, H169, W169, H169))
OUTPAINT = (" The input has blurred side areas: extend the real scene naturally into them so the whole wide 16:9 frame is"
            " sharp and photographic — no blur, no borders, no stretching, keep every subject's true proportions.")


def dims(path):
    """(w, h) of an image or video's first stream, display-aspect corrected."""
    out = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,sample_aspect_ratio",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(out[0]), int(out[1])
    if len(out) > 2 and ":" in out[2] and out[2] not in ("1:1", "0:1", "N/A"):
        a, b = (int(x) for x in out[2].split(":"))
        w = round(w * a / b)
    return w, h


def off169(path, tol=0.03):
    w, h = dims(path)
    return abs((w / h) / (16 / 9) - 1) > tol


def fit169(src, dst=None, pad=None):
    """Make src exactly 16:9 without distortion: centre-crop when it's close (1.45-2.2), else blur-pad. In place by default."""
    dst = dst or src
    w, h = dims(src)
    r = w / h
    if pad is None:
        pad = not 1.45 <= r <= 2.2
    vf = BLURPAD if pad else COVER
    tmp = dst + ".fit" + os.path.splitext(dst)[1]
    video = os.path.splitext(src)[1].lower() in (".mp4", ".webm", ".mov")
    cmd = [FFX if pad else FF, "-v", "error", "-y", "-i", src] + (["-filter_complex" if pad else "-vf", vf])
    cmd += (["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-an"] if video else ["-frames:v", "1"])
    subprocess.run(cmd + [tmp], check=True)
    os.replace(tmp, dst)
    print("16:9 fix %s: %dx%d (%.2f) -> %s" % (os.path.basename(dst), w, h, r, "blur-pad" if pad else "crop"), flush=True)
    return dst


def ref169(path):
    """A 16:9 copy of a reference photo for Qwen (blur-padded), so the still comes out wide instead of following the ref."""
    if not off169(path):
        return path, False
    d = os.path.join(os.path.dirname(path), "_169")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, os.path.splitext(os.path.basename(path))[0] + ".png")
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(path):
        fit169(path, dst, pad=True)
    return dst, True


def wav_len(p):
    w = wave.open(p); return w.getnframes() / w.getframerate()


def free_comfy():
    """Unload ComfyUI's cached models so the Remotion render has RAM (Oct 17: 26 GB held -> commit-limit crash)."""
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8188/free", data=b'{"unload_models":true,"free_memory":true}',
                                                      headers={"Content-Type": "application/json"}, method="POST"), timeout=20)
        print("comfy models unloaded", flush=True)
    except Exception as e:
        print("comfy free skipped:", e, flush=True)


# ── smooth plates (Oct 18: H3 plates are ~6.6 s at 24 fps but a beat runs 14-22 s, so the player slowed them to 0.45x =
# ~11 fps on screen, then froze on the last frame). Each plate is motion-interpolated (ffmpeg minterpolate, MCI) to a
# real 30 fps slow-mo that lasts the whole beat; past MAX_SLOW it ping-pongs instead of freezing. Cached per factor.
MAX_SLOW = 3.0
MINTERP = "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"


def vid_len(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip() or 0)


def smooth_plate(src, need):
    """src plate (.mp4) -> '<key>.s<pct>.mp4' beside it: 30 fps, motion-interpolated, at least `need` seconds long."""
    clip = vid_len(src)
    if clip <= 0:
        return None
    slow = round(min(MAX_SLOW, max(1.0, need / clip)), 2)
    pong = clip * slow < need - 0.05
    dst = os.path.splitext(src)[0] + ".s%d%s.mp4" % (round(slow * 100), "p" if pong else "")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    vf = "setpts=%.3f*PTS,%s" % (slow, MINTERP)
    vf = ("[0:v]%s,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0" % vf) if pong else vf
    tmp = dst + ".tmp.mp4"
    t0 = time.time()
    subprocess.run([FFX, "-v", "error", "-y", "-i", src, "-filter_complex" if pong else "-vf", vf, "-an", "-c:v", "libx264",
                    "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", tmp], check=True)
    os.replace(tmp, dst)
    print("smooth %s x%.2f%s -> %s (%.0fs)" % (os.path.basename(src), slow, " ping-pong" if pong else "",
                                                os.path.basename(dst), time.time() - t0), flush=True)
    return dst


# ── SFX pool (Oct 18, user: "change the sound effects every time a scene changes" + redo them). Each episode gets its
# own set of distinct takes per kind; the Remotion Episode deals them out so two cuts in a row never sound the same.
# sfx_seed (episode.json) picks which prompts are made and how they're dealt; "Redo sound effects" = new seed + new takes.
SFX_KINDS = {   # kind: (takes, seconds, loudness LUFS ~ the v1 library, prompts)
    "whoosh": (5, 3, -13.3, [
        "sound effect only: a single fast cinematic air whoosh passing by, clean, no music, no rhythm",
        "sound effect only: a short airy swoosh transition with a soft reverb tail, clean, no music",
        "sound effect only: a deep low-frequency whoosh sweeping past, cinematic trailer transition, no music",
        "sound effect only: a quick metallic swish, like a blade cutting the air, clean, no music",
        "sound effect only: a soft digital glitch swipe transition, short, clean, no music",
        "sound effect only: a rising reverse-cymbal swell that ends abruptly, short, no music",
        "sound effect only: a fast cloth flutter whoosh, close and crisp, no music",
        "sound effect only: a smooth wind gust sweep from left to right, short, no music"]),
    "boom": (3, 4, -11.7, [
        "sound effect only: one deep cinematic sub-bass impact boom with a short tail, no music",
        "sound effect only: a heavy cinematic hit with a metallic ring-out, single impact, no music",
        "sound effect only: one big low drum boom in a large hall, short decay, no music",
        "sound effect only: a dark trailer braam impact, short, single hit, no music",
        "sound effect only: a punchy low thud impact with a subtle reverse swell before it, no music"]),
    "tick": (2, 2, -15.2, [
        "sound effect only: soft digital interface ticks and clicks, data readout, no music",
        "sound effect only: a single clean UI click, crisp and short, no music",
        "sound effect only: a soft mechanical switch click, short, no music",
        "sound effect only: a gentle digital blip confirmation sound, short, no music"]),
}
SFX_TRIM = "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.02,atrim=0:%.2f,afade=t=out:st=%.2f:d=%.2f,loudnorm=I=%.1f:TP=-1:LRA=11"


def sfx_plan(seed):
    """seed -> [(file name, kind, prompt)] — which takes this episode's pool is made of."""
    import random
    rnd, out = random.Random("sfx%s" % seed), []
    for kind, (n, _secs, _lufs, prompts) in SFX_KINDS.items():
        for i, pr in enumerate(rnd.sample(prompts, min(n, len(prompts)))):
            out.append(("sfx_%s_%d.mp3" % (kind, i + 1), kind, pr))
    return out


class Ep:
    def __init__(self, slug):
        self.slug = slug
        self.spec = json.load(open(os.path.join(ROOT, "episodes", slug, "episode.json"), encoding="utf-8"))
        self.out = os.path.join(ROOT, "public", "episodes", slug)
        os.makedirs(self.out, exist_ok=True)

    def p(self, name): return os.path.join(self.out, name)
    def has(self, name): return os.path.exists(self.p(name))

    def find(self, name):
        """An asset key ('st_track') or a file ('studio_rear.png') -> local path (episode dir first, then shared)."""
        for cand in ([name] if "." in name else [name + ".png", name + ".mp4"]):
            for d in (self.out, os.path.join(SHARED, "sample"), os.path.join(SHARED, "ref")):
                if os.path.exists(os.path.join(d, cand)): return os.path.join(d, cand)
        return None

    # ── narration
    def vo(self):         # clock times are read as times ("3:07 AM" -> "three oh seven A.M."), see speakable() below
        v = self.spec["voice"]
        for b in self.spec["beats"]:
            text = speakable((b.get("say") or b.get("cap") or "").strip())
            if not text: continue
            h = hashlib.sha1(("%s|%s|%s" % (v["id"], v.get("speed", 1), text)).encode()).hexdigest()[:8]
            name = "vo_%s_%s.wav" % (b["id"], h)                 # hash in the name = edited lines re-voice, others cached
            if self.has(name): continue
            if PLAN: print("PLAN tts", b["id"], text[:60]); continue
            raw = self.p("raw_" + name)
            q = urllib.parse.urlencode({"text": text, "voice": v["id"], "speed": v.get("speed", 1)})
            open(raw, "wb").write(call("/api/tts?" + q, raw=True))
            subprocess.run([FF, "-v", "error", "-y", "-i", raw, "-af", "volume=%sdB" % VO_GAIN_DB, "-c:a", "pcm_s16le", self.p(name)], check=True)
            os.remove(raw)
            print("tts", b["id"], "%.2fs" % wav_len(self.p(name)), flush=True)
            prog("vo", b["id"])

    # ── real reference photos the research/script step found (logged with their source page for on-screen credits)
    def fetch_refs(self):
        refs = (self.spec.get("ref_urls") or [])[:MAX_REFS]
        if not refs: return
        d = os.path.join(self.out, "ref")
        os.makedirs(d, exist_ok=True)
        log_p = os.path.join(d, "sources.json")
        log = json.load(open(log_p, encoding="utf-8")) if os.path.exists(log_p) else {}
        for i, r in enumerate(refs):
            url = r.get("url") if isinstance(r, dict) else str(r)
            name = (r.get("name") if isinstance(r, dict) else None) or "ref%02d%s" % (i + 1, os.path.splitext(url.split("?")[0])[1][:5] or ".jpg")
            if os.path.exists(os.path.join(d, name)) or PLAN: continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36"})
                data = urllib.request.urlopen(req, timeout=40).read()
                if len(data) < 5000 or len(data) > 60_000_000: raise ValueError("unexpected size %d" % len(data))
                if data[:4] == b"GIF8" or (isinstance(r, dict) and r.get("convert") == "first_frame"):
                    tmp = os.path.join(d, "_dl_" + name + ".gif")          # Media Lab takes png/jpg/webp: keep the first frame
                    open(tmp, "wb").write(data)
                    subprocess.run([FF, "-v", "error", "-y", "-i", tmp, "-frames:v", "1", os.path.join(d, name)], check=True)
                    os.remove(tmp)
                else:
                    open(os.path.join(d, name), "wb").write(data)
                log[name] = {"url": url, "source": r.get("source", "") if isinstance(r, dict) else "", "use": r.get("use", "") if isinstance(r, dict) else ""}
                prog("ref", name)
            except Exception as e:
                print("REF FAILED", url[:120], str(e)[:120], flush=True)
                prog("ref", name, False, why=str(e)[:160])
        json.dump(log, open(log_p, "w", encoding="utf-8"), indent=1)

    def find_ref(self, name):
        for d in (os.path.join(self.out, "ref"), os.path.join(SHARED, "ref"), self.out):
            if os.path.exists(os.path.join(d, name)): return os.path.join(d, name)
        print("ref not found:", name, flush=True)
        return None

    # ── stills, plates, music, shared SFX
    def assets(self):
        for f in os.listdir(os.path.join(SHARED, "sample")):          # reuse the sample's real-car plates + SFX library v1
            # SFX library v1 is series-wide; the sample's car plates belong to the Roadster episode only
            if (f.startswith("sfx_") or (self.slug == "roadster" and f in ("studio.png", "studio_rear.png", "launch.mp4"))) and not self.has(f):
                shutil.copy2(os.path.join(SHARED, "sample", f), self.p(f))
        self.fetch_refs()
        A = self.spec["assets"]
        derived = lambda a: a.get("lineart_of") or a.get("from")
        # stills: independent ones first, then edits of other stills (line-art passes, re-framings)
        for wave in (False, True):
            for key, a in A.items():
                if a["model"] != "qimg" or self.has(key + ".png") or bool(derived(a)) != wave: continue
                if PLAN: print("PLAN still", key); continue
                try:
                    paths = [x for x in (self.find_ref(r) for r in a.get("refs", [])) if x]
                    if derived(a):
                        srcp = self.find(derived(a))
                        if not srcp: print("skip still (no source)", key); prog("still", key, False, why="no source"); continue
                        paths = [srcp] + paths
                    padded = False
                    if paths:                                       # Qwen edit follows the FIRST ref's shape → make it 16:9
                        paths[0], padded = ref169(paths[0])
                    refs = [upload(x) for x in paths]
                    prompt = LINEART if a.get("lineart_of") and not a.get("prompt") else a["prompt"]
                    if padded:
                        prompt += OUTPAINT
                    f = run({"model": "qimg", "prompt": prompt, "refs": refs,
                             "override": {"mode": "edit" if refs else "generate", "aspect": "16:9", "size": "hd", "enhance": "off"}}, key)
                    shutil.copy2(os.path.join(LIB, os.path.basename(pick(f, (".png", ".jpg", ".jpeg", ".webp")))), self.p(key + ".png"))
                    if off169(self.p(key + ".png")):
                        fit169(self.p(key + ".png"))
                    prog("still", key)
                except Exception as e:
                    print("STILL FAILED", key, str(e)[:200], flush=True)
                    prog("still", key, False, why=str(e)[:200])
        for key, a in A.items():
            if a["model"] != "h3" or self.has(key + ".mp4"): continue
            src = self.find(a["from"])
            if not src: print("skip plate (no source still)", key); continue
            if PLAN: print("PLAN plate", key, "<-", os.path.basename(src)); continue
            try:
                if off169(src):                                     # H3 i2v forces 16:9: a non-16:9 source = stretched plate
                    src = fit169(src, os.path.join(self.out, "_169_" + os.path.splitext(os.path.basename(src))[0] + ".png"))
                ref = upload(src)
                f = run({"model": "h3", "prompt": a["prompt"], "refs": [ref],
                         "override": {"mode": "i2v", "aspect": "16:9", "res": "high", "seconds": a.get("seconds", 6), "quality": "turbo8"}}, key)
                shutil.copy2(os.path.join(LIB, os.path.basename(pick(f, (".mp4", ".webm", ".mov")))), self.p(key + ".mp4"))
                if off169(self.p(key + ".mp4")):
                    fit169(self.p(key + ".mp4"))
                prog("plate", key)
            except Exception as e:
                print("PLATE FAILED", key, str(e)[:200], flush=True)
                prog("plate", key, False, why=str(e)[:200])
        for m in self.spec.get("music", []):
            if self.has(m["name"] + ".mp3"): continue
            if PLAN: print("PLAN music", m["name"]); continue
            try:
                f = run({"model": "music3", "prompt": m["prompt"], "override": {"duration": m.get("seconds", 240), "lyrics": "instrumental"}}, m["name"])
                shutil.copy2(os.path.join(LIB, os.path.basename(pick(f, (".mp3", ".wav", ".flac")))), self.p(m["name"] + ".mp3"))
            except Exception as e:
                print("MUSIC FAILED", m["name"], str(e)[:200], flush=True)
        self.sfx()
        if not PLAN: free_comfy()

    def sfx(self):
        """This episode's own SFX takes (ACE), trimmed to the hit and levelled to the v1 library's loudness."""
        keep = {"whoosh": (1.6, 0.5), "boom": (2.4, 0.9), "tick": (0.5, 0.15)}
        for name, kind, prompt in sfx_plan(self.spec.get("sfx_seed", 0)):
            if self.has(name): continue
            if PLAN: print("PLAN sfx", name); continue
            try:
                f = run({"model": "ace", "prompt": prompt, "literal": True, "override": {"duration": SFX_KINDS[kind][1]}}, name)
                raw = os.path.join(LIB, os.path.basename(pick(f, (".mp3", ".wav", ".flac"))))
                k, fd = keep[kind]
                subprocess.run([FFX, "-v", "error", "-y", "-i", raw, "-af", SFX_TRIM % (k, k - fd, fd, SFX_KINDS[kind][2]),
                                "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "2", self.p(name)], check=True)
                prog("sfx", name)
            except Exception as e:
                print("SFX FAILED", name, str(e)[:200], flush=True)
                prog("sfx", name, False, why=str(e)[:200])

    # ── resolved timeline for Remotion
    def resolve(self):
        v, t, beats = self.spec["voice"], 0.0, []
        for b in self.spec["beats"]:
            text = (b.get("say") or b.get("cap") or "").strip()
            vo, dur = None, float(b.get("pad", 0))
            if text:
                h = hashlib.sha1(("%s|%s|%s" % (v["id"], v.get("speed", 1), text)).encode()).hexdigest()[:8]
                n = "vo_%s_%s.wav" % (b["id"], h)
                if self.has(n):
                    vo = n
                    dur = max(dur, wav_len(self.p(n)) + 0.55)       # breathing room after each line
                else:
                    dur = max(dur, len(text.split()) / 2.9 + 0.55)  # estimate until voiced
            lead = 0.35 if text else 0.0                            # narration starts a beat after the cut
            beats.append(dict(b, start=round(t, 3), dur=round(dur + lead, 3), vo=vo, voAt=lead))
            t += dur + lead
        for n in sorted(os.listdir(self.out)):                    # last line of defence: every still/plate on disk is 16:9
            if n.startswith(("st_", "pl_")) and n.endswith((".png", ".mp4")) and not n.endswith(".fit.png"):
                try:
                    if off169(self.p(n)): fit169(self.p(n))
                except Exception as e:
                    print("16:9 check failed", n, e, flush=True)
        self.prefer_video(beats)
        if not PLAN:
            self.smooth(beats)
            self.fallback_missing(beats)
        files = set(os.listdir(self.out))
        seed = self.spec.get("sfx_seed", 0)
        pool = {k: sorted(n for n in files if n.startswith("sfx_%s_" % k) and n.endswith(".mp3")) for k in SFX_KINDS}
        res = {"meta": self.spec["meta"], "chapters": self.spec["chapters"], "music": self.spec.get("music", []),
               "beats": beats, "total": round(t, 3), "base": "episodes/%s/" % self.slug, "files": sorted(files),
               "sfxSeed": seed, "sfxPool": pool}
        dst = os.path.join(ROOT, "src", "explained", "episodes", self.slug + ".json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(res, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("resolved %d beats, %.1f s (%.1f min) -> %s" % (len(beats), t, t / 60, dst), flush=True)

    def prefer_video(self, beats):
        """A beat showing a still that an H3 plate was made from shows the plate instead (Oct 18: 4 of 11 China plates
        were never used — diversify() had handed out their source stills). Only when no other beat already plays it."""
        A = self.spec.get("assets") or {}
        vid = {a["from"]: k for k, a in A.items() if a.get("model") == "h3" and a.get("from") and self.has(k + ".mp4")}
        base = lambda n: os.path.splitext(str(n or ""))[0]
        used = {base(b.get("plate")) for b in beats}
        for b in beats:
            k = vid.get(base(b.get("plate")))
            if k and k not in used and not str(b.get("plate", "")).endswith(".mp4"):
                print("video for still: %s %s -> %s" % (b["id"], b["plate"], k), flush=True)
                b["plate"], b["stillOf"] = k, b["plate"]
                used.add(k)

    def fallback_missing(self, beats):
        """A beat whose visual never got made shows what it was made FROM (Oct 24: H3 failed on pl_xpeng_aeroht and the
        beat played the empty studio for 11 s at 1:22 — the renderer's last resort). plate → its still → its ref photo."""
        A = self.spec.get("assets") or {}
        on_disk = lambda n: self.has(n) or self.has(n + ".mp4") or self.has(n + ".png")
        for b in beats:
            k = str(b.get("plate") or "")
            if not k or on_disk(k):
                continue
            seen, cur, pick = set(), os.path.splitext(k)[0], None
            while cur and cur not in seen and not pick:
                seen.add(cur)
                a = A.get(cur) or {}
                src = a.get("from") or a.get("lineart_of")
                if src and on_disk(src):
                    pick = src
                elif not src and a.get("refs") and self.has("ref/" + a["refs"][0]):
                    pick = "ref/" + a["refs"][0]
                cur = src
            print("missing visual: %s %s -> %s" % (b["id"], k, pick or "(none)"), flush=True)
            prog("fallback", k, bool(pick), why="shows %s instead" % pick if pick else "nothing to fall back to")
            if pick:
                b["plate"], b["stillOf"] = pick, k
            else:
                b.pop("plate", None)

    def smooth(self, beats):
        """Every beat that plays a plate gets a smooth 30 fps copy as long as the beat (see smooth_plate)."""
        for b in beats:
            n = base = os.path.splitext(str(b.get("plate") or ""))[0]
            if not n or ".s" in n or not self.has(n + ".mp4"):
                continue
            try:
                out = smooth_plate(self.p(n + ".mp4"), float(b["dur"]) + 0.3)
                if out:
                    b["plate"], b["plateSrc"] = os.path.basename(out), base
                    prog("smooth", base)
            except Exception as e:
                print("SMOOTH FAILED", n, str(e)[:200], flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ep, stage = Ep(args[0]), (args[1] if len(args) > 1 else "all")
    if stage == "refs": ep.fetch_refs()                      # Producer: download first, then plan shots around what arrived
    if stage in ("vo", "all"): ep.vo()
    if stage in ("assets", "all"): ep.assets()
    if stage in ("resolve", "vo", "all") and not PLAN: ep.resolve()
