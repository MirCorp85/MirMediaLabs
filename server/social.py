"""
social.py — MIR MEDIA LABS · SOCIAL panel engine + VIRAL-Ω growth agent.
═══════════════════════════════════════════════════════════════════════════════
IDENTICAL in both copies (standalone server/social.py and MirOS aimr-trading/miros_mlab/social.py) —
the media-lab sync rule: copy, never import across. Each copy wires it in with
    social.register(app, hooks)
hooks: uid, is_owner, my_file, push(user, etype, title, body), public_base() -> https base or "".

Accounts: @mirmedialabs Instagram (official API — Instagram Login token "IG…" or the older Facebook-Page token),
YouTube (Data API v3) and TikTok (Content Posting API, Login Kit OAuth; opt-in per post).
Nothing is ever published without the owner pressing APPROVE — enforced here, server side.

  posts      data/social/posts.json   draft → approved/scheduled → publishing → published | failed | rejected
  accounts   data/social/accounts.json (owner only, gitignored with data/)
  format     ffmpeg: 1080x1920 9:16 reframe, loudnorm -14 LUFS, H.264/AAC faststart, cover frame
  agent      VIRAL-Ω — captions, hooks, hashtags, titles, best times, ideas, weekly report (cloud brain or local)
  scheduler  daemon thread: publish at slot time, pull metrics at +1h/+6h/+24h/+72h/+7d, refresh tokens
"""
import hashlib
import hmac
import json
import os
import re
import subprocess
import threading
import time
import uuid

import requests

try:
    from . import core
except ImportError:
    import core

SD = os.path.join(core.DATA, "social")
OUT = os.path.join(SD, "media")
os.makedirs(OUT, exist_ok=True)
POSTS_FILE = os.path.join(SD, "posts.json")
ACC_FILE = os.path.join(SD, "accounts.json")
SOUL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viral_soul.md")

AGENT = "VIRAL-Ω"
PLATFORMS = ("instagram", "youtube")   # default targets of a new draft; TikTok is opt-in per post (needs its own settings)
ALL_PLATFORMS = ("instagram", "youtube", "tiktok")
GRAPH = "https://graph.facebook.com/v21.0"
IG_GRAPH = "https://graph.instagram.com/v21.0"   # "Instagram API with Instagram Login" (Meta's current setup)
IG_DAILY_CAP = 25                      # IG API allows 50/24h; stay well under it (account health)
TT_API = "https://open.tiktokapis.com/v2"
TT_SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.publish,video.list"
TT_DAILY_CAP = 10                      # TikTok caps API posts per creator per day; stay under it
TT_PRIVACY = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
METRIC_AT = (3600, 6 * 3600, 86400, 3 * 86400, 7 * 86400)
_LOCK = threading.RLock()
_HK = {}


def _log(msg):
    try:
        print(msg)
    except Exception:
        pass


# ── store ────────────────────────────────────────────────────────────────────────────────────
def posts():
    return core.load_json(POSTS_FILE, [])


def _save(ps):
    core.save_json(POSTS_FILE, ps)


def get(pid):
    return next((p for p in posts() if p["id"] == pid), None)


def update(pid, **kw):
    with _LOCK:
        ps = posts()
        for p in ps:
            if p["id"] == pid:
                p.update(kw)
                p["updated"] = time.time()
                _save(ps)
                return p
    return None


def accounts():
    return core.load_json(ACC_FILE, {"instagram": {}, "youtube": {}, "handle": "@mirmedialabs"})


def save_accounts(a):
    core.save_json(ACC_FILE, a)


def _secret():
    a = accounts()
    if not a.get("_sig"):
        a["_sig"] = uuid.uuid4().hex + uuid.uuid4().hex
        save_accounts(a)
    return a["_sig"].encode()


def public_accounts():
    a = accounts()
    ig, yt, tt = a.get("instagram") or {}, a.get("youtube") or {}, a.get("tiktok") or {}
    return {"handle": a.get("handle", "@mirmedialabs"),
            "instagram": {"connected": bool(ig.get("token") and ig.get("user_id")), "username": ig.get("username", ""),
                          "expires": ig.get("expires", 0), "api": ig.get("api", "fb" if ig.get("token") else "")},
            "youtube": {"connected": bool(yt.get("refresh_token")), "channel": yt.get("channel", ""),
                        "has_client": bool(yt.get("client_id"))},
            "tiktok": {"connected": bool(tt.get("refresh_token")), "username": tt.get("username", ""),
                       "has_client": bool(tt.get("client_key")), "expires": tt.get("refresh_exp", 0),
                       "base": ((_HK.get("public_base") or (lambda: ""))() or "").rstrip("/")}}


# ── formatter (ffmpeg) ───────────────────────────────────────────────────────────────────────
def _ff(args, timeout=900):
    return subprocess.run([core.FFMPEG, "-hide_banner", "-y"] + args, capture_output=True, text=True,
                          timeout=timeout, creationflags=getattr(core, "NO_WINDOW", 0))


def probe(path):
    r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                       creationflags=getattr(core, "NO_WINDOW", 0))
    t = r.stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    s = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", t)
    return {"duration": dur, "w": int(s.group(1)) if s else 0, "h": int(s.group(2)) if s else 0,
            "audio": "Audio:" in t}


def format_vertical(src, pid, fit="crop"):
    """Any library video/image → 1080x1920 H.264 + AAC, -14 LUFS, faststart; plus a cover JPG."""
    out = os.path.join(OUT, pid + ".mp4")
    cover = os.path.join(OUT, pid + ".jpg")
    info = probe(src)
    is_img = core.kind_of(os.path.basename(src)) == "image"
    if fit == "crop":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:   # blurred backdrop, whole frame visible
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg];"
              "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    vf += ",fps=30,format=yuv420p"
    if is_img:
        args = ["-loop", "1", "-t", "8", "-i", src, "-f", "lavfi", "-t", "8", "-i", "anullsrc=r=48000:cl=stereo",
                "-filter_complex", "[0:v]" + vf + "[v]", "-map", "[v]", "-map", "1:a"]
    elif info["audio"]:
        args = ["-i", src, "-filter_complex", "[0:v]" + vf + "[v];[0:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        args = ["-i", src, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", "[0:v]" + vf + "[v]",
                "-map", "[v]", "-map", "1:a", "-shortest"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "-t", "180", out]
    r = _ff(args)
    if r.returncode or not os.path.isfile(out):
        raise RuntimeError("format failed: " + r.stderr[-400:])
    _ff(["-ss", "0.5", "-i", out, "-frames:v", "1", "-q:v", "2", cover], timeout=60)
    i = probe(out)
    return {"file": os.path.basename(out), "cover": os.path.basename(cover), "duration": round(i["duration"], 2),
            "short": i["duration"] <= 60}


def set_cover(pid, at):
    p = get(pid)
    if not p or not p.get("media"):
        return None
    src = os.path.join(OUT, p["media"]["file"])
    _ff(["-ss", str(max(0.0, float(at))), "-i", src, "-frames:v", "1", "-q:v", "2", os.path.join(OUT, pid + ".jpg")], 60)
    return update(pid, cover_at=float(at))


# ── VIRAL-Ω agent ────────────────────────────────────────────────────────────────────────────
def _soul():
    try:
        with open(SOUL_FILE, encoding="utf-8") as f:
            return f.read()
    except OSError:
        b = getattr(core, "asset", lambda _n: None)("_md/viral_soul.md")     # compiled PC edition: embedded
        return b.decode("utf-8") if b else "You are VIRAL-Ω, the social growth agent for @mirmedialabs."


def _perf_digest(n=12):
    rows = []
    for p in sorted([p for p in posts() if p["status"] == "published"], key=lambda x: -x.get("published_at", 0))[:n]:
        m = {}
        for plat, h in (p.get("metrics") or {}).items():
            if h:
                m[plat] = h[-1]
        rows.append({"hook": p.get("hook", ""), "caption": (p.get("caption") or "")[:120], "pillar": p.get("pillar", ""),
                     "posted": time.strftime("%a %H:%M", time.localtime(p.get("published_at", 0))), "metrics": m})
    return rows


def _brain():
    """VIRAL-Ω prefers Claude (best copywriting) when a key exists; else the lab's chosen cloud brain; else local."""
    pick = accounts().get("brain", "auto")
    if pick == "local":
        return None
    try:
        import cloud
        k = cloud.keys()
        if k.get("anthropic") and pick in ("auto", "claude"):
            return {"provider": "anthropic", "model": accounts().get("claude_model") or cloud.CLAUDE[0]["id"]}
        b = cloud.brain()
        return b if b.get("provider") != "local" and k.get(b["provider"]) else None
    except Exception:
        return None


def ask_agent(task, data, want_json=True, local=False):
    system = _soul()
    prompt = "TASK: %s\n\nDATA:\n%s\n\nRecent performance of our posts:\n%s" % (
        task, json.dumps(data, ensure_ascii=False)[:6000], json.dumps(_perf_digest(), ensure_ascii=False)[:4000])
    if want_json:
        prompt += "\n\nReply with ONLY valid JSON."
    if local:   # cheap tasks stay on the local engine even when a cloud brain is active
        core.ensure_ollama()
        body = {"model": core.engine_model(), "prompt": prompt, "system": system, "stream": False, "think": False,
                **({"format": "json"} if want_json else {})}
        r = requests.post(core.OLLAMA + "/api/generate", timeout=240, json=body)
        if r.status_code >= 500:            # ComfyUI still holds the GPU: free it once and retry
            try:
                try:
                    from . import comfy as _c
                except ImportError:
                    import comfy as _c
                requests.post(_c.BASE + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)
                time.sleep(3)
            except Exception:
                pass
            r = requests.post(core.OLLAMA + "/api/generate", timeout=240, json=body)
        r.raise_for_status()
        txt = r.json().get("response", "")
    else:
        txt = None
        b = _brain()
        if b:
            import cloud
            try:
                txt = cloud.ask(b, prompt, system, want_json=want_json, role="social")
            except Exception as e:
                _log("[social] cloud brain %s: %s — using the local engine" % (b.get("model"), e))
        if txt is None:
            return ask_agent(task, data, want_json, local=True)
    if not want_json:
        return txt
    if isinstance(txt, dict):
        return txt
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def draft_copy(p):
    meta = core.index().get(p.get("library_ref", ""), {})
    d = ask_agent("Write the post package for this new piece of content. Return JSON: "
                  '{"hook": on-screen first-second hook text (<=7 words), "caption": Instagram caption (hook line, '
                  'value/story line, CTA; <=2200 chars, line breaks ok, no hashtags inside), "hashtags": [3-5 niche + '
                  '0-2 broad, no #], "yt_title": YouTube Shorts title <=70 chars with the search keyword first, '
                  '"yt_description": 2-4 lines + CTA, "yt_tags": [8-15], "pillar": content pillar name, '
                  '"best_time": "HH:MM" local, "why": one sentence on why this will travel}',
                  {"prompt": meta.get("prompt") or p.get("brief", ""), "model": meta.get("model", ""),
                   "duration": (p.get("media") or {}).get("duration"), "brief": p.get("brief", ""),
                   "platforms": p.get("platforms")})
    kw = {k: d[k] for k in ("hook", "caption", "hashtags", "yt_title", "yt_description", "yt_tags", "pillar", "why",
                            "best_time") if d.get(k)}
    if isinstance(kw.get("hashtags"), list):
        kw["hashtags"] = [re.sub(r"[^\w]", "", str(h)) for h in kw["hashtags"]][:8]
    return kw


def next_slot(best="18:00"):
    try:
        hh, mm = [int(x) for x in str(best).split(":")[:2]]
    except ValueError:
        hh, mm = 18, 0
    t = time.localtime()
    ts = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hh, mm, 0, 0, 0, -1))
    taken = {int(p.get("schedule_at", 0)) // 1800 for p in posts() if p["status"] in ("scheduled", "approved")}
    while ts < time.time() + 600 or int(ts) // 1800 in taken:
        ts += 86400 if ts < time.time() + 600 else 1800
    return ts


# ── create / workflow ────────────────────────────────────────────────────────────────────────
def create_draft(library_ref, platforms=PLATFORMS, brief="", owner="owner", fit="crop", auto_copy=True):
    src = core.in_dir(core.LIB, os.path.basename(library_ref))
    if not src or not os.path.isfile(src):
        raise ValueError("library item not found")
    pid = uuid.uuid4().hex[:12]
    p = {"id": pid, "owner": owner, "library_ref": os.path.basename(library_ref), "platforms": list(platforms),
         "brief": brief, "status": "preparing", "created": time.time(), "updated": time.time(),
         "caption": "", "hashtags": [], "metrics": {}, "remote": {}, "log": []}
    with _LOCK:
        ps = posts()
        ps.append(p)
        _save(ps)

    def prep():
        try:
            media = format_vertical(src, pid, fit)
            update(pid, media=media)
            kw = draft_copy(get(pid)) if auto_copy else {}
            update(pid, status="draft", **kw)
            _push(owner, "social_draft", "%s: new post ready to approve" % AGENT,
                  (kw.get("hook") or kw.get("caption") or "")[:120], post=pid)
        except Exception as e:
            update(pid, status="failed", error=str(e)[:500])
    threading.Thread(target=prep, daemon=True, name="social-prep").start()
    return p


def on_job_done(job):
    """Chat → Lab → Social: a generation job carrying social={platforms:[...]} becomes a draft automatically."""
    s = job.get("social")
    if not s or job.get("status") != "done":
        return
    for f in job.get("files") or []:
        if core.kind_of(f) in ("video", "image"):
            try:
                create_draft(f, s.get("platforms") or PLATFORMS, brief=job.get("prompt", ""), owner=job.get("user") or "owner")
            except Exception as e:
                _log("[social] auto-draft failed: %s" % e)
            break


def approve(pid, when=None):
    p = get(pid)
    if not p or p["status"] not in ("draft", "failed", "rejected", "scheduled"):
        raise ValueError("post is not awaiting approval")
    if "tiktok" in (p.get("platforms") or []):
        tt_check(p.get("tiktok") or {})
    ts = float(when) if when else next_slot(p.get("best_time") or "18:00")
    return update(pid, status="scheduled", schedule_at=ts, approved_at=time.time(), error="")


# ── public media links (Instagram fetches the video from a public https URL) ───────────────────
def sign(name, ttl=6 * 3600):
    exp = int(time.time() + ttl)
    sig = hmac.new(_secret(), ("%s|%d" % (name, exp)).encode(), hashlib.sha256).hexdigest()[:32]
    return "/social/pub/%s?e=%d&s=%s" % (name, exp, sig)


def check_sig(name, exp, sig):
    try:
        if int(exp) < time.time():
            return False
    except (TypeError, ValueError):
        return False
    want = hmac.new(_secret(), ("%s|%s" % (name, exp)).encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(want, str(sig or ""))


# ── Instagram Graph API ──────────────────────────────────────────────────────────────────────
class PubError(Exception):
    pass


def _ig():
    ig = accounts().get("instagram") or {}
    if not ig.get("token") or not ig.get("user_id"):
        raise PubError("Instagram not connected")
    return ig


def _g(method, path, base=None, **kw):
    if base is None:     # Instagram-Login tokens talk to graph.instagram.com, Facebook-Page tokens to graph.facebook.com
        base = IG_GRAPH if (accounts().get("instagram") or {}).get("api") == "ig" else GRAPH
    r = requests.request(method, base + path, timeout=60, **kw)
    try:
        d = r.json() if r.content else {}
    except ValueError:
        d = {"error": {"message": r.text[:300]}}
    if r.status_code >= 400 or "error" in d:
        e = d.get("error")
        raise PubError((e.get("message") if isinstance(e, dict) else e) or r.text[:300])
    return d


def ig_connect(token, app_id="", app_secret=""):
    """Instagram-Login token ("IG…", from the Meta dashboard's 'Generate token') or a Facebook user token →
    long-lived token + the Instagram professional account id."""
    if token.startswith("IG"):
        exp = time.time() + 5184000           # dashboard tokens are already 60-day tokens
        if app_secret:                        # a 1-hour token from a login flow → swap for a 60-day one
            try:
                d = _g("GET", "/access_token", base="https://graph.instagram.com",
                       params={"grant_type": "ig_exchange_token", "client_secret": app_secret, "access_token": token})
                token, exp = d["access_token"], time.time() + int(d.get("expires_in", 5184000))
            except PubError:
                pass                          # it was already long-lived
        me = _g("GET", "/me", base=IG_GRAPH, params={"fields": "user_id,username,account_type", "access_token": token})
        a = accounts()
        a["instagram"] = {"api": "ig", "token": token, "user_id": str(me.get("user_id") or me["id"]),
                          "username": me.get("username", ""), "expires": exp, "app_id": app_id, "app_secret": app_secret}
        save_accounts(a)
        return public_accounts()
    if app_id and app_secret:
        d = _g("GET", "/oauth/access_token", base=GRAPH, params={"grant_type": "fb_exchange_token", "client_id": app_id,
                                                      "client_secret": app_secret, "fb_exchange_token": token})
        token, exp = d["access_token"], time.time() + int(d.get("expires_in", 5184000))
    else:
        exp = time.time() + 5184000
    pages = _g("GET", "/me/accounts", base=GRAPH, params={"fields": "instagram_business_account{id,username},name",
                                                           "access_token": token}).get("data", [])
    acct = next((pg["instagram_business_account"] for pg in pages if pg.get("instagram_business_account")), None)
    if not acct:
        raise PubError("no Instagram Creator/Business account linked to your Facebook Pages")
    a = accounts()
    a["instagram"] = {"api": "fb", "token": token, "user_id": acct["id"], "username": acct.get("username", ""),
                      "expires": exp, "app_id": app_id, "app_secret": app_secret}
    save_accounts(a)
    return public_accounts()


def ig_refresh():
    a = accounts()
    ig = a.get("instagram") or {}
    if ig.get("api") == "ig" and ig.get("token"):
        # Instagram-Login tokens refresh themselves (no app secret); allowed once the token is a day old
        if ig.get("expires", 0) - time.time() > 30 * 86400:
            return
        d = _g("GET", "/refresh_access_token", base="https://graph.instagram.com",
               params={"grant_type": "ig_refresh_token", "access_token": ig["token"]})
        ig["token"], ig["expires"] = d["access_token"], time.time() + int(d.get("expires_in", 5184000))
        save_accounts(a)
        return
    if not (ig.get("token") and ig.get("app_id") and ig.get("app_secret")):
        return
    if ig.get("expires", 0) - time.time() > 10 * 86400:
        return
    d = _g("GET", "/oauth/access_token", base=GRAPH,
           params={"grant_type": "fb_exchange_token", "client_id": ig["app_id"],
                   "client_secret": ig["app_secret"], "fb_exchange_token": ig["token"]})
    ig["token"], ig["expires"] = d["access_token"], time.time() + int(d.get("expires_in", 5184000))
    save_accounts(a)


def ig_publish(p):
    ig = _ig()
    base = (_HK.get("public_base") or (lambda: ""))()
    if not base.startswith("https://"):
        raise PubError("Instagram needs a public https address for the lab (set it in Social → Accounts)")
    url = base.rstrip("/") + sign(p["media"]["file"])
    cap = (p.get("caption") or "").strip()
    if p.get("hashtags"):
        cap += "\n\n" + " ".join("#" + h for h in p["hashtags"])
    c = _g("POST", "/%s/media" % ig["user_id"], data={"media_type": "REELS", "video_url": url, "caption": cap[:2200],
                                                       "share_to_feed": "true", "thumb_offset": int(p.get("cover_at", 0.5) * 1000),
                                                       "access_token": ig["token"]})
    cid = c["id"]
    for _ in range(90):                          # Reels processing: poll up to ~15 min
        s = _g("GET", "/" + cid, params={"fields": "status_code,status", "access_token": ig["token"]})
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise PubError("Instagram processing failed: %s" % s.get("status", ""))
        time.sleep(10)
    else:
        raise PubError("Instagram processing timed out")
    m = _g("POST", "/%s/media_publish" % ig["user_id"], data={"creation_id": cid, "access_token": ig["token"]})
    link = _g("GET", "/" + m["id"], params={"fields": "permalink", "access_token": ig["token"]}).get("permalink", "")
    return {"id": m["id"], "url": link}


def ig_metrics(mid):
    ig = _ig()
    d = _g("GET", "/%s/insights" % mid, params={"metric": "views,reach,likes,comments,shares,saved,total_interactions",
                                                 "access_token": ig["token"]})
    return {x["name"]: (x.get("values") or [{}])[0].get("value", 0) for x in d.get("data", [])}


def ig_account():
    ig = _ig()
    return _g("GET", "/" + ig["user_id"], params={"fields": "followers_count,media_count,username",
                                                  "access_token": ig["token"]})


# ── YouTube Data API v3 (raw REST, no extra deps) ─────────────────────────────────────────────
YT_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly " \
            "https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.force-ssl"


def yt_auth_url(redirect):
    yt = accounts().get("youtube") or {}
    if not yt.get("client_id"):
        raise PubError("add the Google OAuth client id/secret first")
    from urllib.parse import urlencode
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": yt["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": YT_SCOPES,
        "access_type": "offline", "prompt": "consent"})


def yt_callback(code, redirect):
    a = accounts()
    yt = a.setdefault("youtube", {})
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "code": code, "client_id": yt["client_id"], "client_secret": yt["client_secret"], "redirect_uri": redirect,
        "grant_type": "authorization_code"}).json()
    if "refresh_token" not in r:
        raise PubError(r.get("error_description") or "Google did not return a refresh token")
    yt.update(refresh_token=r["refresh_token"], access=r["access_token"], access_exp=time.time() + r.get("expires_in", 3600) - 60)
    save_accounts(a)
    try:
        ch = _yt("GET", "/youtube/v3/channels", params={"part": "snippet", "mine": "true"})["items"][0]
        a = accounts()
        a["youtube"]["channel"] = ch["snippet"]["title"]
        a["youtube"]["channel_id"] = ch["id"]
        save_accounts(a)
    except Exception:
        pass
    return public_accounts()


def _yt_token():
    a = accounts()
    yt = a.get("youtube") or {}
    if not yt.get("refresh_token"):
        raise PubError("YouTube not connected")
    if yt.get("access") and yt.get("access_exp", 0) > time.time():
        return yt["access"]
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": yt["client_id"], "client_secret": yt["client_secret"], "refresh_token": yt["refresh_token"],
        "grant_type": "refresh_token"}).json()
    if "access_token" not in r:
        raise PubError(r.get("error_description") or "YouTube token refresh failed")
    yt["access"], yt["access_exp"] = r["access_token"], time.time() + r.get("expires_in", 3600) - 60
    save_accounts(a)
    return yt["access"]


def _yt(method, path, base="https://www.googleapis.com", **kw):
    r = requests.request(method, base + path, timeout=120, headers={"Authorization": "Bearer " + _yt_token()}, **kw)
    if r.status_code >= 400:
        raise PubError("YouTube: " + r.text[:300])
    return r.json() if r.content else {}


def yt_publish(p, privacy="public"):
    path = os.path.join(OUT, p["media"]["file"])
    title = (p.get("yt_title") or p.get("hook") or "MIR MEDIA LABS")[:95]
    if p["media"].get("short") and "#shorts" not in title.lower():
        title = (title[:86] + " #Shorts")
    body = {"snippet": {"title": title, "description": (p.get("yt_description") or p.get("caption") or "")[:4900],
                        "tags": (p.get("yt_tags") or p.get("hashtags") or [])[:30], "categoryId": "24"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}
    size = os.path.getsize(path)
    init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                         timeout=60, json=body, headers={"Authorization": "Bearer " + _yt_token(),
                                                         "X-Upload-Content-Type": "video/mp4",
                                                         "X-Upload-Content-Length": str(size)})
    if init.status_code >= 400:
        raise PubError("YouTube: " + init.text[:300])
    with open(path, "rb") as f:
        up = requests.put(init.headers["Location"], data=f, timeout=1800,
                          headers={"Authorization": "Bearer " + _yt_token(), "Content-Type": "video/mp4"})
    if up.status_code >= 400:
        raise PubError("YouTube upload: " + up.text[:300])
    vid = up.json()["id"]
    cover = os.path.join(OUT, p["id"] + ".jpg")
    if os.path.isfile(cover):
        try:
            with open(cover, "rb") as f:
                requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + vid, data=f,
                              timeout=120, headers={"Authorization": "Bearer " + _yt_token(), "Content-Type": "image/jpeg"})
        except Exception:
            pass          # custom thumbnails need a verified channel; never fail the post for it
    return {"id": vid, "url": ("https://youtube.com/shorts/" if p["media"].get("short") else "https://youtu.be/") + vid}


def yt_metrics(vid):
    it = _yt("GET", "/youtube/v3/videos", params={"part": "statistics", "id": vid}).get("items") or [{}]
    s = it[0].get("statistics", {})
    return {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))}


def yt_account():
    it = _yt("GET", "/youtube/v3/channels", params={"part": "statistics,snippet", "mine": "true"}).get("items") or [{}]
    s = it[0].get("statistics", {})
    return {"subscribers": int(s.get("subscriberCount", 0)), "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)), "channel": it[0].get("snippet", {}).get("title", "")}


# ── TikTok Content Posting API (Login Kit OAuth, Direct Post via FILE_UPLOAD) ─────────────────
# TikTok rules this follows: read creator_info before every post, owner picks the privacy level (no default),
# comment/duet/stitch are off unless the owner turns them on, commercial-content disclosure, AI-content label.
# Until TikTok audits the app, posts only work as SELF_ONLY on a PRIVATE TikTok account.
def tt_redirect():
    base = (_HK.get("public_base") or (lambda: ""))()
    if not base.startswith("https://"):
        raise PubError("TikTok needs the lab's public https address (Social → Accounts)")
    return base.rstrip("/") + "/social/tiktok/callback"


def tt_auth_url():
    a = accounts()
    tt = a.get("tiktok") or {}
    if not tt.get("client_key"):
        raise PubError("add the TikTok client key and secret first")
    from urllib.parse import urlencode
    tt["state"], tt["state_exp"] = uuid.uuid4().hex, time.time() + 900
    a["tiktok"] = tt
    save_accounts(a)
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": tt["client_key"], "scope": TT_SCOPES, "response_type": "code",
        "redirect_uri": tt_redirect(), "state": tt["state"]})


def _tt_store(tt, r):
    now = time.time()
    tt.update(access=r["access_token"], access_exp=now + int(r.get("expires_in", 86400)) - 120,
              refresh_token=r.get("refresh_token") or tt.get("refresh_token"),
              refresh_exp=now + int(r.get("refresh_expires_in", 31536000)), open_id=r.get("open_id", tt.get("open_id", "")),
              scope=r.get("scope", tt.get("scope", "")))


def _tt_oauth(data):
    r = requests.post(TT_API + "/oauth/token/", timeout=30, data=data,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        d = r.json()
    except ValueError:
        raise PubError("TikTok: " + r.text[:300])
    if "access_token" not in d:
        raise PubError("TikTok: " + str(d.get("error_description") or d.get("error") or d)[:300])
    return d


def tt_callback(code, state):
    a = accounts()
    tt = a.get("tiktok") or {}
    if not state or not tt.get("state") or not hmac.compare_digest(str(state), str(tt["state"])) \
            or tt.get("state_exp", 0) < time.time():
        raise PubError("this sign-in link expired — start again from Social → Accounts")
    d = _tt_oauth({"client_key": tt["client_key"], "client_secret": tt.get("client_secret", ""), "code": code,
                   "grant_type": "authorization_code", "redirect_uri": tt_redirect()})
    _tt_store(tt, d)
    tt.pop("state", None)
    tt.pop("state_exp", None)
    a["tiktok"] = tt
    save_accounts(a)
    try:
        u = tt_account()
        a = accounts()
        a["tiktok"].update(username=u.get("username", ""), display_name=u.get("display_name", ""))
        save_accounts(a)
    except Exception as e:
        _log("[social] TikTok profile: %s" % e)
    return public_accounts()


def tt_refresh(force=False):
    a = accounts()
    tt = a.get("tiktok") or {}
    if not tt.get("refresh_token"):
        raise PubError("TikTok not connected")
    if not force and tt.get("access") and tt.get("access_exp", 0) > time.time():
        return tt["access"]
    d = _tt_oauth({"client_key": tt["client_key"], "client_secret": tt.get("client_secret", ""),
                   "grant_type": "refresh_token", "refresh_token": tt["refresh_token"]})
    _tt_store(tt, d)
    save_accounts(a)
    return tt["access"]


def _tt(method, path, **kw):
    r = requests.request(method, TT_API + path, timeout=60, headers={"Authorization": "Bearer " + tt_refresh(),
                                                                       "Content-Type": "application/json; charset=UTF-8"}, **kw)
    try:
        d = r.json()
    except ValueError:
        raise PubError("TikTok: " + r.text[:300])
    e = d.get("error") or {}
    if r.status_code >= 400 or (e.get("code") not in (None, "", "ok")):
        raise PubError("TikTok: %s" % (e.get("message") or e.get("code") or r.text[:300]))
    return d.get("data") or {}


def tt_creator():
    """What this creator may do right now: privacy options, whether comments/duet/stitch are disabled, max length."""
    return _tt("POST", "/post/publish/creator_info/query/", json={})


def tt_check(s, ci=None):
    if s.get("privacy_level") not in TT_PRIVACY:
        raise ValueError("TikTok: choose who can see this post (Edit → TikTok)")
    if not s.get("consent"):
        raise ValueError("TikTok: tick the Music Usage Confirmation agreement (Edit → TikTok)")
    if s.get("brand_content") and s["privacy_level"] == "SELF_ONLY":
        raise ValueError("TikTok: branded content can't be private (only me)")
    if s.get("disclose") and not (s.get("brand_content") or s.get("brand_organic")):
        raise ValueError("TikTok: commercial content is on — pick 'Your brand' and/or 'Branded content'")
    if ci and s["privacy_level"] not in (ci.get("privacy_level_options") or []):
        raise PubError("TikTok doesn't offer '%s' for this account right now (unaudited apps: private account + "
                       "'Only me')" % s["privacy_level"])


def tt_publish(p):
    s = p.get("tiktok") or {}
    ci = tt_creator()
    tt_check(s, ci)
    dur, maxd = (p.get("media") or {}).get("duration") or 0, ci.get("max_video_post_duration_sec") or 0
    if maxd and dur > maxd:
        raise PubError("TikTok: video is %ds, this account allows %ds" % (dur, maxd))
    path = os.path.join(OUT, p["media"]["file"])
    size = os.path.getsize(path)
    MB = 1024 * 1024
    chunk, n = (size, 1) if size <= 64 * MB else (10 * MB, size // (10 * MB))   # last chunk takes the remainder
    title = (p.get("caption") or p.get("hook") or "").strip()
    if p.get("hashtags"):
        title += "\n\n" + " ".join("#" + h for h in p["hashtags"])
    info = {"title": title[:2200], "privacy_level": s["privacy_level"],
            "disable_comment": bool(ci.get("comment_disabled") or not s.get("allow_comment")),
            "disable_duet": bool(ci.get("duet_disabled") or not s.get("allow_duet")),
            "disable_stitch": bool(ci.get("stitch_disabled") or not s.get("allow_stitch")),
            "video_cover_timestamp_ms": int(float(p.get("cover_at", 0.5)) * 1000),
            "brand_content_toggle": bool(s.get("brand_content")), "brand_organic_toggle": bool(s.get("brand_organic")),
            "is_aigc": True}
    d = _tt("POST", "/post/publish/video/init/", json={"post_info": info, "source_info": {
        "source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": n}})
    pub_id, up = d["publish_id"], d["upload_url"]
    with open(path, "rb") as f:
        for i in range(n):
            a = i * chunk
            b = size - 1 if i == n - 1 else a + chunk - 1
            f.seek(a)
            buf = f.read(b - a + 1)
            r = requests.put(up, data=buf, timeout=900, headers={"Content-Type": "video/mp4", "Content-Length": str(len(buf)),
                                                                 "Content-Range": "bytes %d-%d/%d" % (a, b, size)})
            if r.status_code not in (200, 201, 206):
                raise PubError("TikTok upload: %s %s" % (r.status_code, r.text[:200]))
    vid = ""
    for _ in range(90):                          # processing: poll up to ~15 min
        st = _tt("POST", "/post/publish/status/fetch/", json={"publish_id": pub_id})
        if st.get("status") == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
            vid = str(ids[0]) if ids else ""
            break
        if st.get("status") == "FAILED":
            raise PubError("TikTok processing failed: %s" % st.get("fail_reason", ""))
        time.sleep(10)
    else:
        raise PubError("TikTok processing timed out (publish id %s)" % pub_id)
    user = (accounts().get("tiktok") or {}).get("username", "")
    url = ("https://www.tiktok.com/@%s/video/%s" % (user, vid)) if vid and user else \
          ("https://www.tiktok.com/@%s" % user if user else "https://www.tiktok.com/")
    return {"id": vid or pub_id, "publish_id": pub_id, "url": url, "privacy": s["privacy_level"]}


def tt_metrics(vid):
    if not str(vid).isdigit():                   # private posts may not get a public video id
        return {}
    d = _tt("POST", "/video/query/", params={"fields": "id,view_count,like_count,comment_count,share_count"},
            json={"filters": {"video_ids": [str(vid)]}})
    v = (d.get("videos") or [{}])[0]
    return {"views": int(v.get("view_count", 0)), "likes": int(v.get("like_count", 0)),
            "comments": int(v.get("comment_count", 0)), "shares": int(v.get("share_count", 0))}


def tt_account():
    return _tt("GET", "/user/info/", params={"fields": "open_id,username,display_name,follower_count,video_count,likes_count"}
               ).get("user") or {}


# ── publish + scheduler ──────────────────────────────────────────────────────────────────────
def _today(plat):
    day = time.time() - 86400
    return sum(1 for p in posts() if (p.get("remote") or {}).get(plat) and p.get("published_at", 0) > day)


def publish(pid):
    p = get(pid)
    if not p or p["status"] not in ("scheduled", "approved") or not p.get("approved_at"):
        raise ValueError("only approved posts can be published")       # human approval is mandatory
    update(pid, status="publishing")
    remote, errs = dict(p.get("remote") or {}), []
    for plat in p["platforms"]:
        if plat in remote:
            continue
        try:
            if plat == "instagram":
                if _today("instagram") >= IG_DAILY_CAP:
                    raise PubError("daily Instagram cap reached")
                remote[plat] = ig_publish(p)
            elif plat == "youtube":
                remote[plat] = yt_publish(p)
            elif plat == "tiktok":
                if _today("tiktok") >= TT_DAILY_CAP:
                    raise PubError("daily TikTok cap reached")
                remote[plat] = tt_publish(p)
        except Exception as e:
            errs.append("%s: %s" % (plat, str(e)[:240]))
    st = "published" if remote and not errs else ("partial" if remote else "failed")
    upd = {"status": "published" if st == "partial" else st, "remote": remote, "error": "; ".join(errs)}
    if remote:
        upd["published_at"] = p.get("published_at") or time.time()
    update(pid, **upd)
    _push(p.get("owner", "owner"), "social_published" if remote else "social_failed",
          "%s: %s" % (AGENT, "posted" if remote else "post failed"), upd["error"] or " · ".join(r.get("url", "") for r in remote.values()), post=pid)
    return get(pid)


def pull_metrics(p):
    m = dict(p.get("metrics") or {})
    for plat, r in (p.get("remote") or {}).items():
        try:
            row = {"instagram": ig_metrics, "youtube": yt_metrics, "tiktok": tt_metrics}[plat](r["id"])
            if not row:
                continue
            row["t"] = time.time()
            m.setdefault(plat, []).append(row)
        except Exception as e:
            _log("[social] metrics %s: %s" % (plat, e))
    update(p["id"], metrics=m, metrics_n=p.get("metrics_n", 0) + 1)


def snapshot_accounts():
    hist = core.load_json(os.path.join(SD, "followers.json"), [])
    row = {"t": time.time()}
    try:
        row["instagram"] = ig_account().get("followers_count")
    except Exception:
        pass
    try:
        row["youtube"] = yt_account().get("subscribers")
    except Exception:
        pass
    if (accounts().get("tiktok") or {}).get("refresh_token"):
        try:
            row["tiktok"] = tt_account().get("follower_count")
        except Exception:
            pass
    if len(row) > 1:
        hist.append(row)
        core.save_json(os.path.join(SD, "followers.json"), hist[-2000:])
    return hist


def _loop():
    last_acct = last_tok = last_idea = 0
    while True:
        try:
            now = time.time()
            for p in posts():
                if p["status"] == "scheduled" and p.get("schedule_at", 0) <= now:
                    publish(p["id"])
                elif p["status"] == "published":
                    n = p.get("metrics_n", 0)
                    if n < len(METRIC_AT) and now - p.get("published_at", now) >= METRIC_AT[n]:
                        pull_metrics(p)
            if now - last_acct > 3 * 3600:
                last_acct = now
                snapshot_accounts()
            if now - last_tok > 86400:
                last_tok = now
                try:
                    ig_refresh()
                except Exception as e:
                    _log("[social] IG token refresh: %s" % e)
                if (accounts().get("tiktok") or {}).get("refresh_token"):
                    try:
                        tt_refresh(force=True)          # keeps the 1-year refresh token rolling
                    except Exception as e:
                        _log("[social] TikTok token refresh: %s" % e)
            if now - last_idea > 86400 and time.localtime().tm_hour >= 9 and accounts().get("daily_ideas", True)                     and any(v["connected"] for k, v in public_accounts().items() if isinstance(v, dict)):
                last_idea = now
                try:
                    ideas()
                except Exception as e:
                    _log("[social] ideas: %s" % e)
        except Exception as e:
            _log("[social] loop: %s" % e)
        time.sleep(30)


def ideas(n=3):
    d = ask_agent("Propose %d new short-form video ideas for @mirmedialabs that are most likely to go viral next, "
                  "based on what performed. Return JSON {\"ideas\": [{\"title\", \"hook\", \"why\", \"pillar\", "
                  "\"lab_prompt\": a ready-to-run MIR MEDIA LABS generation prompt (visual, motion, camera, mood), "
                  "\"duration\": seconds}]}" % n, {"handle": accounts().get("handle")})
    out = {"t": time.time(), "ideas": (d.get("ideas") or [])[:n]}
    core.save_json(os.path.join(SD, "ideas.json"), out)
    if out["ideas"]:
        _push("owner", "social_ideas", "%s: %d new ideas" % (AGENT, len(out["ideas"])), out["ideas"][0].get("title", ""))
    return out


def report():
    hist = core.load_json(os.path.join(SD, "followers.json"), [])
    return ask_agent("Write this week's growth report for @mirmedialabs: what worked (hooks, pillars, times), what "
                     "flopped and why, follower trend, and exactly 3 actions for next week. Plain text, short.",
                     {"followers": hist[-60:]}, want_json=False)


def _push(user, etype, title, body="", **extra):
    try:
        (_HK.get("push") or (lambda *a, **k: None))(user, etype, title, body, **extra)
    except Exception:
        pass


# ── analytics (graphs) ───────────────────────────────────────────────────────────────────────
def _views(row):
    return int(row.get("views") or row.get("plays") or 0)


def analytics():
    """Everything the charts need, computed from our own post history (no extra API calls)."""
    pub = [p for p in posts() if p["status"] == "published"]
    rows, hours, pillars, plat = [], [[0, 0] for _ in range(24)], {}, {}
    days = [[0, 0] for _ in range(7)]
    for p in pub:
        v = l = c = sh = sv = 0
        for pl, h in (p.get("metrics") or {}).items():
            if not h:
                continue
            x = h[-1]
            pv = _views(x)
            v += pv; l += int(x.get("likes", 0) or 0); c += int(x.get("comments", 0) or 0)
            sh += int(x.get("shares", 0) or 0); sv += int(x.get("saved", 0) or 0)
            a = plat.setdefault(pl, {"views": 0, "likes": 0, "posts": 0})
            a["views"] += pv; a["likes"] += int(x.get("likes", 0) or 0); a["posts"] += 1
        eng = (l + c + sh + sv) / v * 100 if v else 0
        lt = time.localtime(p.get("published_at", 0))
        hours[lt.tm_hour][0] += v; hours[lt.tm_hour][1] += 1
        days[lt.tm_wday][0] += v; days[lt.tm_wday][1] += 1
        k = p.get("pillar") or "—"
        pa = pillars.setdefault(k, {"views": 0, "posts": 0})
        pa["views"] += v; pa["posts"] += 1
        curve = {pl: [{"t": round((x["t"] - p["published_at"]) / 3600, 1), "views": _views(x)} for x in h]
                 for pl, h in (p.get("metrics") or {}).items() if h}
        rows.append({"id": p["id"], "hook": p.get("hook") or p.get("yt_title") or p["id"], "t": p.get("published_at"),
                     "views": v, "likes": l, "comments": c, "shares": sh, "saved": sv, "eng": round(eng, 2),
                     "pillar": k, "curve": curve, "cover": "api/social/media/%s.jpg" % p["id"]})
    rows.sort(key=lambda r: r["t"] or 0)
    med = sorted(r["views"] for r in rows)[len(rows) // 2] if rows else 0
    return {"posts": rows, "median_views": med,
            "hours": [{"h": i, "avg": round(a / n) if n else 0, "n": n} for i, (a, n) in enumerate(hours)],
            "days": [{"d": d, "avg": round(a / n) if n else 0, "n": n} for d, (a, n) in zip("MTWTFSS", days)],
            "pillars": [{"pillar": k, "avg": round(v["views"] / v["posts"]), "posts": v["posts"]} for k, v in
                        sorted(pillars.items(), key=lambda kv: -kv[1]["views"] / max(1, kv[1]["posts"]))],
            "platforms": plat, "followers": core.load_json(os.path.join(SD, "followers.json"), [])[-500:]}


# ── VIRAL-Ω skills (one-tap expert actions) ───────────────────────────────────────────────────
SKILLS = {
    "hook_doctor": ("Hook Doctor", "wand", "Rewrite the first-second hook 5 ways and rank them by scroll-stopping power.",
                    "For the post below, write 5 alternative on-screen hooks (<=7 words) using different angles (curiosity gap, "
                    "bold claim, question, number, 'POV'). Rank them and explain the winner in one line. JSON "
                    '{"hooks":[{"text","angle","score":1-10}],"pick":index,"why"}'),
    "caption_ab": ("Caption A/B", "type", "Two contrasting captions to test against each other.",
                   'Write 2 contrasting Instagram captions (A: story-driven, B: short + punchy CTA). JSON {"a","b","test_note"}'),
    "hashtag_lab": ("Hashtag Lab", "search", "Niche-first hashtag set split into reach tiers.",
                    'Build a hashtag set: 3 niche (<500k posts), 2 mid, 1 broad, plus #mirmedialabs. JSON {"niche":[],"mid":[],"broad":[],"note"}'),
    "trend_scout": ("Trend Scout", "radar", "Short-form formats trending now that fit an AI media studio.",
                    'List 5 current short-form video formats/trends that an AI art & video account can ride without copying anyone. '
                    'JSON {"trends":[{"name","how_we_do_it","lab_prompt"}]}'),
    "repurpose": ("Repurpose", "layers", "Turn one hit into a series: remix, sequel, carousel, YT long-form angle.",
                  'Turn our best-performing post into a series of 4 follow-ups. JSON {"series":[{"title","hook","lab_prompt","format"}]}'),
    "best_time": ("Best Time", "clock", "When to post, learned from our own numbers.",
                  'From the performance data (hours/days averages), recommend the 2 best posting slots per platform and why. '
                  'JSON {"instagram":["HH:MM"],"youtube":["HH:MM"],"tiktok":["HH:MM"],"why"}'),
    "comment_bait": ("Pinned Comment", "chain", "A pinned first comment that sparks replies.",
                     'Write 3 pinned-comment options that invite replies (question / choice / challenge). JSON {"comments":[],"pick"}'),
    "growth_plan": ("7-Day Plan", "finance", "A posting calendar for the next week with pillars and hooks.",
                    'Make a 7-day posting plan: per day platform, time, pillar, idea title, hook, lab_prompt. JSON {"days":[{"day","time","pillar","title","hook","lab_prompt"}]}'),
}


def run_skill(key, pid=None, note=""):
    if key not in SKILLS:
        raise ValueError("unknown skill")
    name, _ic, _d, task = SKILLS[key]
    data = {"note": note, "analytics": {k: v for k, v in analytics().items() if k in ("hours", "days", "pillars", "median_views")}}
    if pid and get(pid):
        p = get(pid)
        data["post"] = {k: p.get(k) for k in ("hook", "caption", "hashtags", "yt_title", "pillar", "brief")}
    out = ask_agent(task, data)
    out["_skill"] = name
    return out


# ── routes ───────────────────────────────────────────────────────────────────────────────────
_STARTED = []


def start():
    if not _STARTED:
        _STARTED.append(1)
        threading.Thread(target=_loop, daemon=True, name="social-scheduler").start()


def register(app, hk):
    from flask import request, jsonify, send_file, abort, redirect
    _HK.update(hk)

    def owner():
        if not hk["is_owner"]():
            abort(403)

    def body():
        return request.get_json(silent=True) or {}

    def out(p):
        if not p:
            return None
        d = dict(p)
        if d.get("media"):
            d["video_url"] = "api/social/media/" + d["media"]["file"]
            d["cover_url"] = "api/social/media/%s.jpg?v=%d" % (d["id"], int(d.get("updated", 0)))
        return d

    @app.get("/social")
    def social_page():
        owner()
        return hk["static"]("social.html")

    @app.get("/social/pub/<name>")
    def social_pub(name):                         # public, signed, expiring — for Instagram's fetcher only
        name = os.path.basename(name)
        if not check_sig(name, request.args.get("e"), request.args.get("s")):
            abort(403)
        p = core.in_dir(OUT, name)
        return send_file(p, mimetype="video/mp4") if p and os.path.isfile(p) else abort(404)

    @app.get("/api/social/media/<name>")
    def social_media(name):
        owner()
        p = core.in_dir(OUT, os.path.basename(name))
        return send_file(p) if p and os.path.isfile(p) else abort(404)

    @app.get("/api/social/posts")
    def social_posts():
        owner()
        st = request.args.get("status")
        ps = [out(p) for p in posts() if not st or p["status"] == st]
        return jsonify({"agent": AGENT, "posts": sorted(ps, key=lambda p: -p.get("created", 0))})

    @app.post("/api/social/draft")
    def social_draft():
        owner()
        b = body()
        try:
            p = create_draft(b.get("library_ref") or b.get("name"), b.get("platforms") or PLATFORMS, b.get("brief", ""),
                             owner=hk["uid"](), fit=b.get("fit", "crop"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(out(p))

    @app.post("/api/social/posts/<pid>")
    def social_edit(pid):
        owner()
        b = body()
        keep = {k: b[k] for k in ("caption", "hashtags", "hook", "yt_title", "yt_description", "yt_tags", "platforms",
                                  "schedule_at", "pillar") if k in b}
        if "platforms" in keep:
            keep["platforms"] = [x for x in keep["platforms"] if x in ALL_PLATFORMS]
        if isinstance(b.get("tiktok"), dict):
            t = b["tiktok"]
            keep["tiktok"] = {"privacy_level": t.get("privacy_level") if t.get("privacy_level") in TT_PRIVACY else "",
                              **{k: bool(t.get(k)) for k in ("allow_comment", "allow_duet", "allow_stitch", "disclose",
                                                              "brand_organic", "brand_content", "consent")}}
        if "cover_at" in b:
            set_cover(pid, b["cover_at"])
        return jsonify(out(update(pid, **keep)) or {"error": "not found"})

    @app.post("/api/social/posts/<pid>/rewrite")
    def social_rewrite(pid):
        owner()
        p = get(pid)
        if not p:
            abort(404)
        note = body().get("note", "")
        if note:
            p["brief"] = (p.get("brief", "") + "\nOwner direction: " + note).strip()
        kw = draft_copy(p)
        if p.get("media") and p["status"] in ("failed", "preparing"):
            kw.update(status="draft", error="")
        return jsonify(out(update(pid, **kw)))

    @app.post("/api/social/posts/<pid>/approve")
    def social_approve(pid):
        owner()
        try:
            return jsonify(out(approve(pid, body().get("when"))))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/social/posts/<pid>/publish-now")
    def social_now(pid):
        owner()
        try:
            approve(pid, time.time())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        threading.Thread(target=publish, args=(pid,), daemon=True).start()
        return jsonify(out(get(pid)))

    @app.post("/api/social/posts/<pid>/reject")
    def social_reject(pid):
        owner()
        return jsonify(out(update(pid, status="rejected")))

    @app.post("/api/social/posts/<pid>/delete")
    def social_delete(pid):
        owner()
        with _LOCK:
            _save([p for p in posts() if p["id"] != pid])
        for ext in (".mp4", ".jpg"):
            try:
                os.remove(os.path.join(OUT, pid + ext))
            except OSError:
                pass
        return jsonify({"ok": True})

    @app.post("/api/social/posts/<pid>/metrics")
    def social_pull(pid):
        owner()
        p = get(pid)
        if p:
            pull_metrics(p)
        return jsonify(out(get(pid)))

    @app.get("/api/social/stats")
    def social_stats():
        owner()
        ps = posts()
        pub = [p for p in ps if p["status"] == "published"]
        tot = {"views": 0, "likes": 0, "comments": 0, "shares": 0, "saved": 0}
        for p in pub:
            for h in (p.get("metrics") or {}).values():
                if h:
                    for k in tot:
                        tot[k] += int(h[-1].get(k, 0) or 0)
        return jsonify({"agent": AGENT, "accounts": public_accounts(),
                        "followers": core.load_json(os.path.join(SD, "followers.json"), [])[-500:],
                        "counts": {s: sum(1 for p in ps if p["status"] == s) for s in
                                   ("draft", "scheduled", "published", "failed", "preparing")},
                        "totals": tot, "ideas": core.load_json(os.path.join(SD, "ideas.json"), {})})

    @app.get("/api/social/analytics")
    def social_analytics():
        owner()
        return jsonify(analytics())

    @app.get("/api/social/skills")
    def social_skills():
        owner()
        return jsonify({"skills": [{"key": k, "name": v[0], "icon": v[1], "desc": v[2]} for k, v in SKILLS.items()]})

    @app.post("/api/social/skills/<key>")
    def social_skill(key):
        owner()
        b = body()
        try:
            return jsonify(run_skill(key, b.get("post"), b.get("note", "")))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/social/ideas")
    def social_ideas():
        owner()
        return jsonify(ideas(int(body().get("n", 3))))

    @app.post("/api/social/report")
    def social_report():
        owner()
        return jsonify({"report": report()})

    @app.post("/api/social/ask")
    def social_ask():
        owner()
        q = body().get("q", "")
        return jsonify({"agent": AGENT, "answer": ask_agent(
            "The owner asks: " + q + "\nAnswer as the growth strategist, concrete and short.", {"stats": public_accounts()},
            want_json=False, local=bool(body().get("local")))})

    @app.get("/api/social/accounts")
    def social_accounts():
        owner()
        a = public_accounts()
        a["public_base"] = accounts().get("public_base", "")
        return jsonify(a)

    @app.post("/api/social/accounts")
    def social_accounts_set():
        owner()
        b, a = body(), accounts()
        if "public_base" in b:
            a["public_base"] = str(b["public_base"]).strip().rstrip("/")
        if "handle" in b:
            a["handle"] = b["handle"]
        if b.get("yt_client_id"):
            yt = a.setdefault("youtube", {})
            yt["client_id"] = b["yt_client_id"].strip()
            if b.get("yt_client_secret", "").strip():          # an empty box keeps the saved secret
                yt["client_secret"] = b["yt_client_secret"].strip()
        if b.get("tt_client_key"):
            tt = a.setdefault("tiktok", {})
            tt["client_key"] = b["tt_client_key"].strip()
            if b.get("tt_client_secret", "").strip():
                tt["client_secret"] = b["tt_client_secret"].strip()
        save_accounts(a)
        if b.get("ig_token"):
            try:
                return jsonify(ig_connect(b["ig_token"].strip(), b.get("ig_app_id", "").strip(), b.get("ig_app_secret", "").strip()))
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        return jsonify(public_accounts())

    def _redirect():
        # Google "Desktop app" OAuth clients only accept a LOOPBACK return address, so sign-in must finish on the lab
        # PC itself (not a phone / the public domain / the MirOS proxy). Always hand Google the standalone lab's
        # loopback callback; the MirOS copy has no YouTube publishing of its own.
        return "http://127.0.0.1:%d/api/social/youtube/callback" % core.PORT

    @app.get("/api/social/youtube/connect")
    def social_yt_connect():
        owner()
        if request.remote_addr not in ("127.0.0.1", "::1") or request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
            return ("<body style='font:15px system-ui;background:#262624;color:#f5f4ef;padding:30px'>"
                    "<h3>Finish YouTube sign-in on the lab PC</h3><p>Google only returns to this lab on the PC it runs on. "
                    "On that PC, open <b>http://127.0.0.1:%d/social</b> &rarr; Accounts &rarr; Sign in with Google.</p></body>"
                    % core.PORT), 200
        try:
            return redirect(yt_auth_url(_redirect()))
        except PubError as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/social/youtube/callback")
    def social_yt_cb():
        owner()
        try:
            yt_callback(request.args.get("code", ""), _redirect())
        except Exception as e:
            return "YouTube connect failed: %s" % e, 400
        return redirect("/social?v=accounts")

    # ── TikTok ── sign-in returns to the PUBLIC https address (TikTok requires https), so the callback is
    # public (the host gate lets /social/tiktok/ through) and is protected by the one-time state instead.
    @app.get("/api/social/tiktok/connect")
    def social_tt_connect():
        owner()
        try:
            return redirect(tt_auth_url())
        except PubError as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/social/tiktok/callback")
    def social_tt_cb():
        if request.args.get("error"):
            msg = request.args.get("error_description") or request.args.get("error")
        else:
            try:
                tt_callback(request.args.get("code", ""), request.args.get("state", ""))
                msg = ""
            except Exception as e:
                msg = str(e)
        from html import escape
        return ("<body style='font:15px system-ui;background:#262624;color:#f5f4ef;padding:30px'><h3>%s</h3><p>%s</p></body>"
                % (("TikTok connected" if not msg else "TikTok sign-in failed"),
                   ("You can close this tab — the Social panel now shows TikTok as connected." if not msg else escape(msg)))), \
            (200 if not msg else 400)

    @app.get("/api/social/tiktok/creator")
    def social_tt_creator():
        owner()
        try:
            return jsonify(tt_creator())
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/social/tiktok/disconnect")
    def social_tt_off():
        owner()
        a = accounts()
        tt = a.get("tiktok") or {}
        a["tiktok"] = {k: tt[k] for k in ("client_key", "client_secret") if k in tt}
        save_accounts(a)
        return jsonify(public_accounts())

    @app.get("/social/tiktok/legal/<doc>")
    def social_tt_legal(doc):          # public Terms / Privacy pages the TikTok developer app asks for
        if doc not in ("terms", "privacy"):
            abort(404)
        h = accounts().get("handle", "@mirmedialabs")
        txt = {"terms": "MIR MEDIA LABS is a private publishing tool used only by the owner of %s to post their own "
                        "videos to their own TikTok, Instagram and YouTube accounts. It is not offered to other users. "
                        "Every post is reviewed and approved by the owner before it is published." % h,
               "privacy": "MIR MEDIA LABS connects only the owner's own %s accounts. It stores the access tokens and the "
                          "owner's own post statistics on the owner's PC, never sells or shares data, and uses the "
                          "TikTok, Instagram and YouTube APIs only to publish the owner's approved videos and read their "
                          "performance. Disconnecting in Social → Accounts deletes the stored tokens." % h}[doc]
        return ("<body style='font:15px/1.6 system-ui;max-width:720px;margin:40px auto;padding:0 16px'><h2>MIR MEDIA LABS — %s"
                "</h2><p>%s</p><p>Contact: via %s</p></body>" % ("Terms of Service" if doc == "terms" else "Privacy Policy", txt, h))

    start()
