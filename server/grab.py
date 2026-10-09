"""
grab.py — MIR MEDIA LABS link downloader: YouTube (and any other yt-dlp site) → MP3 audio or MP4 video in the library.
═══════════════════════════════════════════════════════════════════════════════
IDENTICAL in both copies (standalone server/grab.py and MirOS aimr-trading/miros_mlab/grab.py) — copy, never import
across. Each copy wires it in with
    grab.register(app, hooks)
where hooks gives the copy's own helpers (uid, can_grab, static).

A finished download is an ordinary library item (index model "download"), so the timeline editor's media bin, the
Series studio's "From library" picker, "Use as ref" and every engine see it with no extra wiring.

  • POST /api/grab          {url, mode: mp3|video|both, quality, start, end, stills}  → job
  • GET  /api/grab          this person's recent downloads
  • GET  /api/grab/<id>     one job (status, pct, title, files)
  • POST /api/grab/<id>/cancel
  • POST /api/grab/probe    {url} → title / duration / thumbnail, nothing downloaded
  • POST /api/grab/convert  a file (upload, or {lib: name} from the library) → MP3 / M4A / WAV / MP4 → job
  • GET  /grab              the page (iframe overlay in both labs)

Only download what you have the rights to use (your own uploads, licensed / Creative Commons / public-domain media).
"""
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid

try:                      # MirOS copy lives in the miros_mlab package
    from . import core
except ImportError:       # standalone server runs its modules flat
    import core

GD = os.path.join(core.DATA, "grab")
TMP = os.path.join(GD, "tmp")
MAX_SECS = 4 * 3600                    # longest source accepted (a 4 h video)
KEEP = 40                              # jobs remembered per person
VIDEO_Q = {"360": 360, "480": 480, "720": 720, "1080": 1080, "1440": 1440, "2160": 2160, "best": 0}
AUDIO_Q = ("128", "192", "320")
CONVERT_TO = ("mp3", "m4a", "wav", "mp4")
IN_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp", ".ts",
          ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif")

JOBS = {}
# Every request the downloader makes carries this header. The lab's gate refuses any request that has it, so a link that
# (directly, by DNS or by redirect) points back at the lab can never be served with the host's loopback rights.
FETCH_HEADER = "X-MML-Fetch"
_LOCK = threading.Lock()
_SLOTS = threading.Semaphore(2)        # two downloads at a time; the rest wait their turn


def available():
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def _ff_location():
    d = os.path.dirname(core.FFMPEG or "")
    probe = os.path.join(d, "ffprobe.exe" if os.name == "nt" else "ffprobe")
    return d if d and os.path.isfile(probe) else core.FFMPEG


def _js_runtimes():
    """YouTube needs a JavaScript runtime for its player challenge — use whatever this PC has."""
    out = {}
    for name in ("deno", "node", "bun"):
        if shutil.which(name):
            out[name] = {}
    return out


def _clean_url(u):
    from urllib.parse import urlsplit
    u = str(u or "").strip()[:2000]
    if not re.match(r"^https?://", u, re.I):
        raise ValueError("paste a full link (https://…)")
    try:
        sp = urlsplit(u)
        host, port = sp.hostname, sp.port
    except ValueError:
        raise ValueError("that link doesn't look right")
    if not host or sp.username is not None or sp.password is not None:
        raise ValueError("that link doesn't look right")
    try:                                   # every address the name resolves to must be on the public internet
        addrs = {a[4][0] for a in socket.getaddrinfo(host, port or 443, proto=socket.IPPROTO_TCP)}
    except OSError:
        raise ValueError("couldn't find that website — check the link")
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("that link points at this network, not a website")
    return u


def _secs(v):
    """'1:23' / '83' / 83 → 83.0 (None when empty)."""
    if v in (None, ""):
        return None
    s = str(v).strip()
    try:
        parts = [float(p) for p in s.split(":")]
    except ValueError:
        raise ValueError("times look like 1:23 or 83")
    t = 0.0
    for p in parts:
        t = t * 60 + p
    return max(0.0, t)


def _opts(job, outdir, hook):
    o = {"quiet": True, "no_warnings": True, "noplaylist": True, "restrictfilenames": True, "windowsfilenames": True,
         "outtmpl": os.path.join(outdir, "src.%(ext)s"), "ffmpeg_location": _ff_location(), "progress_hooks": [hook],
         "socket_timeout": 30, "retries": 3, "http_headers": {FETCH_HEADER: "1"}, "concurrent_fragment_downloads": 4, "overwrites": True,
         "match_filter": lambda info, *a, **k: ("longer than 4 hours — too long to grab" if (info.get("duration") or 0) > MAX_SECS else None)}
    js = _js_runtimes()
    if js:
        o["js_runtimes"] = js
    if job["mode"] == "mp3":
        o["format"] = "bestaudio/best"
    else:
        h = VIDEO_Q.get(job["quality"], 1080)
        o["format"] = "bv*+ba/b"
        o["format_sort"] = (["res:%d" % h] if h else []) + ["vcodec:h264", "acodec:m4a", "ext:mp4"]
        o["merge_output_format"] = "mp4"
    return o


def _ffmpeg(args, timeout=1800):
    r = subprocess.run([core.FFMPEG, "-hide_banner", "-y", "-v", "error"] + args, capture_output=True, text=True,
                       timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError((r.stderr or "ffmpeg failed").strip().splitlines()[-1][:300])


def _cut(job):
    a = []
    if job.get("start") is not None:
        a += ["-ss", "%.3f" % job["start"]]
    if job.get("end") is not None:
        a += ["-to", "%.3f" % job["end"]]
    return a


def _save(job, src, ext, prefix, meta_extra=None):
    name = core.new_name(prefix, ext)
    dst = os.path.join(core.LIB, name)
    shutil.move(src, dst)
    if job.get("session"):                          # the session (project) the Downloader was used in
        meta_extra = dict(meta_extra or {}, session=job["session"])
    core.index_add(name, dict({"user": job["user"], "model": "download", "mode": job["mode"], "prompt": job.get("title") or job["url"],
                               "source": job["url"], "created": time.time()}, **(meta_extra or {})))
    job["files"].append(name)
    return dst


def _run(job):
    with _SLOTS:
        if job["status"] == "canceled":
            return
        job.update(status="running", stage="fetching the link")
        outdir = os.path.join(TMP, job["id"])
        os.makedirs(outdir, exist_ok=True)
        try:
            import yt_dlp

            def hook(d):
                if job["status"] == "canceled":
                    raise yt_dlp.utils.DownloadCancelled("canceled")
                if d.get("status") == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    job["pct"] = round(min(99.0, 100.0 * (d.get("downloaded_bytes") or 0) / tot), 1) if tot else job["pct"]
                    job["speed"] = d.get("speed")
                    job["eta"] = d.get("eta")
                    job["stage"] = "downloading"
                elif d.get("status") == "finished":
                    job["stage"] = "joining audio + video" if job["mode"] != "mp3" else "converting"

            with yt_dlp.YoutubeDL(_opts(job, outdir, hook)) as y:
                info = y.extract_info(job["url"], download=True)
            job["title"] = (info or {}).get("title") or job.get("title")
            job["duration"] = (info or {}).get("duration")
            got = [os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("src.") and not f.endswith((".part", ".ytdl"))]
            if not got:
                raise RuntimeError("the site sent nothing to save")
            src = max(got, key=os.path.getsize)
            stem = re.sub(r"[^A-Za-z0-9]+", "_", job.get("title") or "download").strip("_")[:28] or "download"
            cut = _cut(job)
            if job["mode"] in ("video", "both"):
                job["stage"] = "making the MP4"
                vout = os.path.join(outdir, "out.mp4")
                vc = _ffprobe_codecs(src)
                if not cut and src.lower().endswith(".mp4") and vc.get("v") == "h264" and vc.get("a") in ("aac", None):
                    shutil.copy2(src, vout)                       # already editor-friendly → no re-encode
                else:                                             # VP9/AV1/webm or a trim → H.264 + AAC the editor reads
                    _ffmpeg(cut + ["-i", src, "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                                   "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", vout])
                vpath = _save(job, vout, ".mp4", "dl_" + stem)
                if job.get("stills"):
                    job["stage"] = "saving stills"
                    _stills(job, vpath, stem, outdir)
            if job["mode"] in ("mp3", "both"):
                job["stage"] = "making the MP3"
                aout = os.path.join(outdir, "out.mp3")
                _ffmpeg(cut + ["-i", src, "-vn", "-c:a", "libmp3lame", "-b:a", job.get("abr", "192") + "k", aout])
                _save(job, aout, ".mp3", "dl_" + stem)
            job.update(status="done", pct=100, stage="in your library")
        except Exception as e:
            canceled = job["status"] == "canceled" or "cancel" in str(e).lower()
            msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
            job.update(status="canceled" if canceled else "failed", stage="", error=None if canceled else _friendly(msg))
        finally:
            job["ended"] = time.time()
            shutil.rmtree(outdir, ignore_errors=True)


def _convert(job, src):
    """A file on this PC → the chosen format, into the library (same job list as the downloads)."""
    with _SLOTS:
        if job["status"] == "canceled":
            return
        outdir = os.path.dirname(src)
        try:
            job.update(status="running", stage="converting", pct=5)
            codecs = _ffprobe_codecs(src)
            to, cut = job["to"], _cut(job)
            if to != "mp4" and not codecs.get("a"):
                raise RuntimeError("that file has no sound to turn into audio")
            if to == "mp4" and not codecs.get("v"):
                raise RuntimeError("that file has no picture — pick an audio format instead")
            out = os.path.join(outdir, "out." + to)
            if to == "mp3":
                args = ["-vn", "-c:a", "libmp3lame", "-b:a", job["abr"] + "k"]
            elif to == "m4a":
                args = ["-vn", "-c:a", "aac", "-b:a", job["abr"] + "k", "-movflags", "+faststart"]
            elif to == "wav":
                args = ["-vn", "-c:a", "pcm_s16le", "-ar", "44100"]
            else:                                           # any video → the H.264 / AAC MP4 every app and the editor read
                args = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
            _ffmpeg(cut + ["-i", src] + args + [out])
            if job["status"] == "canceled":
                raise RuntimeError("canceled")
            stem = re.sub(r"[^A-Za-z0-9]+", "_", os.path.splitext(job.get("title") or "file")[0]).strip("_")[:28] or "file"
            _save(job, out, "." + to, "cv_" + stem, {"mode": "convert", "source": job.get("title")})
            job.update(status="done", pct=100, stage="in your library")
        except Exception as e:
            canceled = job["status"] == "canceled" or "cancel" in str(e).lower()
            job.update(status="canceled" if canceled else "failed", stage="", error=None if canceled else str(e)[:300])
        finally:
            job["ended"] = time.time()
            shutil.rmtree(outdir, ignore_errors=True)


def _friendly(msg):
    m = msg.lower()
    if "private video" in m or "sign in" in m or "login" in m:
        return "that video is private or needs a sign-in — only public links work"
    if "age" in m and "confirm" in m:
        return "that video is age-restricted — it can't be grabbed without a sign-in"
    if "unsupported url" in m:
        return "that site isn't supported"
    if "not available" in m or "unavailable" in m:
        return "that video isn't available (removed, region-locked or a live stream that ended)"
    if "too long" in m or "4 hours" in m:
        return "longer than 4 hours — too long to grab"
    return msg[:300]


def _ffprobe_codecs(path):
    out = {}
    try:
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (r.stderr or "").splitlines():
            mv = re.search(r"Stream #.*Video: (\w+)", line)
            ma = re.search(r"Stream #.*Audio: (\w+)", line)
            if mv and "v" not in out:
                out["v"] = mv.group(1)
            if ma and "a" not in out:
                out["a"] = ma.group(1)
    except Exception:
        pass
    return out


def _stills(job, vpath, stem, outdir):
    """N evenly spaced frames → library pictures (style frames for a Series bible, keyframes, references)."""
    n = max(1, min(12, int(job.get("stills") or 0)))
    dur = 0.0
    try:
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", vpath], capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    except Exception:
        pass
    if dur <= 0:
        return
    for k in range(n):
        at = dur * (k + 0.5) / n
        p = os.path.join(outdir, "still_%02d.jpg" % k)
        try:
            _ffmpeg(["-ss", "%.3f" % at, "-i", vpath, "-frames:v", "1", "-q:v", "2", p], 120)
            _save(job, p, ".jpg", "dl_%s_still%d" % (stem[:20], k + 1), {"mode": "still"})
        except Exception:
            continue


def public(j):
    return {k: j.get(k) for k in ("id", "url", "mode", "quality", "status", "stage", "pct", "speed", "eta", "title", "duration",
                                  "thumb", "files", "error", "created", "ended", "start", "end", "stills", "to", "abr")}


def register(app, hk):
    """hk: uid() → person id, can_grab() → None or the reason it's not allowed, static(fn) → page response,
    lib_path(name) → the full path of one of this person's library files (None when it isn't theirs)."""
    from flask import request, jsonify, abort

    os.makedirs(TMP, exist_ok=True)
    shutil.rmtree(TMP, ignore_errors=True)            # leftovers from a restart mid-download
    os.makedirs(TMP, exist_ok=True)

    def U():
        return str(hk["uid"]())

    def body():
        return request.get_json(silent=True) or {}

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    def mine(jid):
        j = JOBS.get(jid)
        if not j or j["user"] != U():
            abort(404)
        return j

    @app.route("/grab")
    def grab_page():
        return hk["static"]("grab.html")

    @app.route("/api/grab", methods=["GET", "POST"])
    def grab_jobs():
        if request.method == "GET":
            mine_ = sorted((j for j in JOBS.values() if j["user"] == U()), key=lambda j: -j["created"])
            return jsonify({"available": available(), "jobs": [public(j) for j in mine_[:KEEP]]})
        if hk["can_grab"]():
            return oops(hk["can_grab"](), 403)
        if not available():
            return oops("the downloader (yt-dlp) isn't installed on the lab PC", 503)
        b = body()
        try:
            url = _clean_url(b.get("url"))
            start, end = _secs(b.get("start")), _secs(b.get("end"))
        except ValueError as e:
            return oops(e)
        if start is not None and end is not None and end <= start:
            return oops("the end time must be after the start")
        mode = b.get("mode") if b.get("mode") in ("mp3", "video", "both") else "mp3"
        q = str(b.get("quality") or ("192" if mode == "mp3" else "1080"))
        job = {"id": uuid.uuid4().hex[:10], "user": U(), "url": url, "mode": mode, "status": "queued", "stage": "waiting its turn",
               "session": hk["session"](b.get("session")) if hk.get("session") else "",
               "pct": 0, "files": [], "created": time.time(), "start": start, "end": end,
               "quality": q if q in VIDEO_Q else "1080", "abr": str(b.get("abr") or (q if q in AUDIO_Q else "192")),
               "stills": int(b.get("stills") or 0) if mode != "mp3" else 0, "title": str(b.get("title") or "")[:200] or None,
               "thumb": str(b.get("thumb") or "")[:500] or None}
        if job["abr"] not in AUDIO_Q:
            job["abr"] = "192"
        with _LOCK:
            JOBS[job["id"]] = job
            mine_ = sorted((j for j in JOBS.values() if j["user"] == job["user"]), key=lambda j: -j["created"])
            for old in mine_[KEEP:]:
                if old["status"] not in ("queued", "running"):
                    JOBS.pop(old["id"], None)
        threading.Thread(target=_run, args=(job,), daemon=True, name="mml-grab-" + job["id"]).start()
        return jsonify(public(job))

    @app.route("/api/grab/probe", methods=["POST"])
    def grab_probe():
        if hk["can_grab"]():
            return oops(hk["can_grab"](), 403)
        if not available():
            return oops("the downloader (yt-dlp) isn't installed on the lab PC", 503)
        try:
            url = _clean_url(body().get("url"))
            import yt_dlp
            o = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True, "socket_timeout": 20,
                 "http_headers": {FETCH_HEADER: "1"}}
            js = _js_runtimes()
            if js:
                o["js_runtimes"] = js
            with yt_dlp.YoutubeDL(o) as y:
                i = y.extract_info(url, download=False) or {}
        except Exception as e:
            return oops(_friendly(re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")))
        if i.get("_type") == "playlist":
            return oops("that's a playlist — paste a link to one video")
        return jsonify({"title": i.get("title"), "duration": i.get("duration"), "thumb": i.get("thumbnail"),
                        "uploader": i.get("uploader") or i.get("channel"), "site": i.get("extractor_key"),
                        "license": i.get("license"), "live": bool(i.get("is_live")),
                        "heights": sorted({f.get("height") for f in i.get("formats") or [] if f.get("height")})})

    @app.route("/api/grab/convert", methods=["POST"])
    def grab_convert():
        """Converter: an uploaded file (multipart "file") or a library file ({lib}) → to: mp3|m4a|wav|mp4."""
        if hk["can_grab"]():
            return oops(hk["can_grab"](), 403)
        b = request.form.to_dict() if request.files else body()
        to = str(b.get("to") or "mp3").lower()
        if to not in CONVERT_TO:
            return oops("pick MP3, M4A, WAV or MP4")
        try:
            start, end = _secs(b.get("start")), _secs(b.get("end"))
        except ValueError as e:
            return oops(e)
        if start is not None and end is not None and end <= start:
            return oops("the end time must be after the start")
        jid = uuid.uuid4().hex[:10]
        work = os.path.join(TMP, "cv_" + jid)
        os.makedirs(work, exist_ok=True)
        f = request.files.get("file")
        if f and f.filename:
            title = os.path.basename(f.filename)[:120]
            ext = os.path.splitext(title)[1].lower()
            if ext not in IN_EXT:
                shutil.rmtree(work, ignore_errors=True)
                return oops("that isn't a video or audio file this can read")
            src = os.path.join(work, "in" + ext)
            f.save(src)
        else:
            name = os.path.basename(str(b.get("lib") or ""))
            path = hk["lib_path"](name) if name and hk.get("lib_path") else None
            if not path or os.path.splitext(name)[1].lower() not in IN_EXT:
                shutil.rmtree(work, ignore_errors=True)
                return oops("pick a video or audio file first")
            title = (core.index().get(name) or {}).get("prompt") or name
            src = os.path.join(work, "in" + os.path.splitext(name)[1].lower())
            shutil.copy2(path, src)
        abr = str(b.get("abr") or "192")
        job = {"id": jid, "user": U(), "url": "", "mode": "convert", "to": to, "status": "queued", "stage": "waiting its turn",
               "pct": 0, "files": [], "created": time.time(), "start": start, "end": end, "title": str(title)[:200],
               "abr": abr if abr in AUDIO_Q else "192", "quality": "", "stills": 0,
               "session": hk["session"](b.get("session")) if hk.get("session") else ""}
        with _LOCK:
            JOBS[jid] = job
        threading.Thread(target=_convert, args=(job, src), daemon=True, name="mml-convert-" + jid).start()
        return jsonify(public(job))

    @app.route("/api/grab/<jid>")
    def grab_job(jid):
        return jsonify(public(mine(jid)))

    @app.route("/api/grab/<jid>/cancel", methods=["POST"])
    def grab_cancel(jid):
        j = mine(jid)
        if j["status"] in ("queued", "running"):
            j["status"] = "canceled"
        return jsonify(public(j))
