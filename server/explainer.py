"""EXPLAINED PRODUCER — MirAI's "MIR EXPLAINED" pipeline: what's trending → a researched, scripted episode in the
permanent Signature style → Media Lab assets → Remotion render → VIRAL-Ω post + 3 Shorts.
This module owns stages 1-5; later stages plug in through STAGE_HANDLERS (built in their own pass):
  trends          collect >=15 candidate topics (Google Trends RSS, Google News, YouTube trending, Reddit hot)
  pick_topic      Claude proposes 3 angles → the person picks (or "Fully automatic" takes #1)
  research        a one-shot headless Claude Code job (web search) writes episodes/<slug>/research.md
  script          a second one-shot job turns research.md into episodes/<slug>/episode.json (validated vs _schema.json)
  approve_script  the person approves or asks for a rewrite with a note → stage "assets" (next pass)
Writers are one-shot calls on the cloud brain or the local engine (never the user's chat session).

Same shape as producer.py: state in data/explained/<user>/<id>.json written after every change, a loop that ticks
running runs (each tick on its own worker thread so a 20-minute research job never blocks the others), self-healing
retries (_diagnose/_heal), runs resume after a restart, every event → /api/explained/feed.
"""
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse as _uparse
import urllib.request as _urequest
import uuid
import xml.etree.ElementTree as ET

try:
    import core
    import explained_presets as PR
except ImportError:
    import core
    import explained_presets as PR

RUNS = os.path.join(core.DATA, "explained")
import engines
REMOTION = engines.motion()
EPISODES = os.path.join(REMOTION, "episodes")
EXAMPLE = os.path.join(EPISODES, "roadster", "episode.json")
SCHEMA = os.path.join(EPISODES, "_schema.json")
TICK = 4.0
MAX_HEAL = 3
COOL = {"auth": 600, "limit": 180, "stall": 30, "net": 60, "default": 45}
ROLE = ("You are a member of the MIR EXPLAINED editorial team (a YouTube explainer channel owned by the user). "
        "You do editorial work — topic selection, factual web research, script writing — not software engineering. "
        "Follow the task exactly, never invent facts or URLs, and finish with the requested reply format.")
TIMEOUT = {"topics": 8 * 60, "research": 35 * 60, "script": 30 * 60, "photos": 20 * 60}
MODEL = {"topics": "sonnet", "research": "opus", "script": "opus", "photos": "sonnet"}
# research + script + photo hunt run on the free desk (kaggle_research.py: your research engine → cloud brain → local).
RESEARCH_ENGINE = lambda p: "free"
SCRIPT_ENGINE = lambda p: "free"
MAX_REFS = 20          # real reference photos per episode — one still each, so the video never has to repeat a picture
NARRATOR = "am_michael"   # house narrator (Oct 17); per-run p["voice"] picks any Kokoro voice (Oct 24, user: "pick different voices")


def _voices():
    try:
        import tts
    except ImportError:
        import tts
    return tts.VOICES
MIN_CANDIDATES = 15
STAGES = ("trends", "pick_topic", "research", "script", "approve_script",
          "assets", "render", "approve_final", "publish", "done")
LABEL = {"trends": "collecting what's trending", "pick_topic": "choosing the topic", "research": "researching",
         "script": "writing the script", "approve_script": "waiting for you to approve the script",
         "assets": "making the Media Lab assets", "render": "rendering the video",
         "approve_final": "waiting for you to approve the final cut", "publish": "preparing the posts",
         "done": "finished"}
CHECKPOINTS = ("pick_topic", "approve_script", "approve_final")
STAGE_HANDLERS = {}      # later passes: STAGE_HANDLERS["assets"] = fn(p) -> None (mutate via _mut, set next stage)
HK = {}
_ACTIVE = set()
_BUSY = set()
_PROCS = {}              # pid -> running claude Popen (so Cancel can kill it)
_GUARD = threading.Lock()
_LOCKS = {}
_STARTED = False
_NOWIN = 0x08000000 if os.name == "nt" else 0
UA = "MIR-MEDIA-LABS-Explained/1.0 (+https://github.com/MirCorp85/MirMediaLabs)"


# ── storage ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _dir(uid):
    d = os.path.join(RUNS, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "owner")))
    os.makedirs(d, exist_ok=True)
    return d


def load(uid, pid):
    if not re.match(r"^[a-f0-9]{12}$", str(pid or "")):
        return None
    try:
        with open(os.path.join(_dir(uid), pid + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(uid, p):
    p["updated"] = time.time()
    path = os.path.join(_dir(uid), p["id"] + ".json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(path + ".tmp", path)
    return p


def _lock(pid):
    with _GUARD:
        return _LOCKS.setdefault(pid, threading.RLock())


def _mut(uid, pid, fn):
    """Reload → fn(p) → save, under the run's lock. Worker threads and control() both go through here, so a
    cancel / pick that lands while a 20-minute Claude job runs is never overwritten by the job's result."""
    with _lock(pid):
        p = load(uid, pid)
        if not p:
            return None
        if fn(p) is False:
            return p
        return save(uid, p)


def _all(uid):
    out = []
    for n in os.listdir(_dir(uid)):
        if n.endswith(".json"):
            p = load(uid, n[:-5])
            if p:
                out.append(p)
    return sorted(out, key=lambda p: -p.get("created", 0))


def listing(uid):
    return [public(p, brief=True) for p in _all(uid)]


def _title(p):
    t = (p.get("topic") or {}).get("topic") or p.get("niche") or "MIR EXPLAINED"
    return str(t)[:70]


def _log(p, msg, lvl="info"):
    """lvl: info · done (milestone) · warn (fixing it) · error (needs the person) · need (waiting for a decision)."""
    now = time.time()
    p.setdefault("log", []).append({"t": now, "seq": int(now * 1000), "msg": str(msg)[:400], "lvl": lvl})
    p["log"] = p["log"][-200:]
    if lvl != "info":
        try:
            (HK.get("push") or (lambda *a, **k: None))(p["uid"], "explained", "%s — %s" % (_title(p), lvl.upper()),
                                                         str(msg)[:160], run=p["id"])
        except Exception:
            pass


def feed(uid, since=0):
    out = []
    for p in _all(uid):
        for e in p.get("log") or []:
            if e.get("seq", 0) > since:
                out.append(dict(e, run=p["id"], title=_title(p), state=p.get("state"), stage=p.get("stage")))
    return sorted(out, key=lambda e: e["seq"])[-100:]


def _folder(p):
    slug = (p.get("topic") or {}).get("slug")
    return os.path.join(EPISODES, slug) if slug else None


def steps(p):
    order = STAGES.index(p["stage"]) if p.get("stage") in STAGES else 0
    rows = []
    for i, s in enumerate(STAGES[:-1]):
        if i < order or p.get("stage") == "done":
            st = "done"
        elif i == order:
            st = {"waiting": "wait", "paused": "fail", "cancelled": "fail"}.get(p.get("state"), "now")
        else:
            st = "todo"
        rows.append({"key": s, "label": LABEL[s], "state": st, "checkpoint": s in CHECKPOINTS})
    return rows


def public(p, brief=False):
    out = {k: p.get(k) for k in ("id", "state", "stage", "error", "created", "updated", "niche", "auto", "topic",
                                 "cost", "validation", "rewrite_note", "progress", "renders", "mix", "posts", "awaiting",
                                 "length", "asset_fails", "session", "structure", "structure_pick", "voice")}
    out["voice"] = out["voice"] or NARRATOR
    out["structure"] = out["structure"] or "auto"
    out["title"] = _title(p)
    out["label"] = LABEL.get(p.get("stage"), p.get("stage"))
    out["heals"] = sum((p.get("heals") or {}).values())
    out["n_candidates"] = len(p.get("candidates") or [])
    out["sources"] = sorted({c["source"].split(":")[0] for c in p.get("candidates") or []})
    f = _folder(p)
    out["folder"] = f
    out["has_research"] = bool(f and os.path.isfile(os.path.join(f, "research.md")))
    out["has_episode"] = bool(f and os.path.isfile(os.path.join(f, "episode.json")))
    if brief:
        return out
    out["steps"] = steps(p)
    if p.get("stage") == "assets" and f:     # Oct 19: counted from the files on disk, so a resumed run shows what's already made
        try:
            import explainer_back as XB
            with open(os.path.join(f, "episode.json"), encoding="utf-8") as fh:
                snap = XB._asset_snapshot(p, json.load(fh), (p.get("progress") or {}).get("phase") if
                                          (p.get("progress") or {}).get("phase") in ("timeline", "done") else None)
            out["progress"] = dict(p.get("progress") or {}, **snap)
        except Exception:
            pass
    out["proposals"] = p.get("proposals") or []
    out["candidates"] = (p.get("candidates") or [])[:60]
    out["log"] = (p.get("log") or [])[-40:]
    try:
        out["redo"] = redo_items(p)
    except Exception:
        out["redo"] = {"steps": []}
    return out


# ── stage 1: trends (stdlib only, like src/news_agent.py) ──────────────────────────────────────────────────────────
def _get(url, headers=None, timeout=20):
    req = _urequest.Request(url, headers=dict({"User-Agent": UA, "Accept": "*/*"}, **(headers or {})))
    with _urequest.urlopen(req, timeout=timeout) as r:
        return r.read()


def _strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def _num(s):
    try:
        return int(re.sub(r"[^\d]", "", str(s or "")) or 0)
    except ValueError:
        return 0


def _rss_items(raw):
    root = ET.fromstring(raw)
    for it in root.iter():
        if it.tag.split("}")[-1] != "item":
            continue
        d = {}
        for ch in it:
            k = ch.tag.split("}")[-1]
            if k not in d:                       # first news_item_* wins
                d[k] = (ch.text or "").strip()
            if k == "news_item":
                for sub in ch:
                    kk = sub.tag.split("}")[-1]
                    d.setdefault(kk, (sub.text or "").strip())
        yield d


def _google_trends():
    out = []
    for url in ("https://trends.google.com/trending/rss?geo=US",
                "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"):
        try:
            for d in _rss_items(_get(url)):
                out.append({"title": d.get("title", ""), "source": "google_trends",
                            "url": d.get("news_item_url") or d.get("link") or "",
                            "detail": _strip(d.get("news_item_title")), "score": _num(d.get("approx_traffic"))})
            if out:
                break
        except Exception:
            continue
    return out


GNEWS = {"Technology": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
         "Science": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en",
         "Autos": "https://news.google.com/rss/search?q=" + _uparse.quote("cars OR EV OR automaker OR supercar when:2d")
                  + "&hl=en-US&gl=US&ceid=US:en"}


def _google_news(niche=""):
    feeds = dict(GNEWS)
    if niche:
        feeds["Niche"] = ("https://news.google.com/rss/search?q=" + _uparse.quote(niche + " when:3d")
                          + "&hl=en-US&gl=US&ceid=US:en")
    out = []
    for name, url in feeds.items():
        try:
            for i, d in enumerate(list(_rss_items(_get(url)))[:12]):
                out.append({"title": _strip(d.get("title")), "source": "google_news:" + name, "url": d.get("link", ""),
                            "detail": _strip(d.get("source")) or _strip(d.get("description"))[:160],
                            "score": 12 - i, "date": d.get("pubDate", "")})
        except Exception:
            continue
    return out


def _youtube():
    try:
        import social
        tok = social._yt_token()
    except Exception:
        return []
    out = []
    for cat, name in (("28", "Science & Technology"), ("2", "Autos & Vehicles")):
        try:
            q = _uparse.urlencode({"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "US",
                                   "videoCategoryId": cat, "maxResults": 15})
            j = json.loads(_get("https://www.googleapis.com/youtube/v3/videos?" + q,
                                {"Authorization": "Bearer " + tok, "Accept": "application/json"}))
            for v in j.get("items") or []:
                sn = v.get("snippet") or {}
                out.append({"title": sn.get("title", ""), "source": "youtube:" + name,
                            "url": "https://www.youtube.com/watch?v=" + v.get("id", ""),
                            "detail": sn.get("channelTitle", ""), "score": _num((v.get("statistics") or {}).get("viewCount"))})
        except Exception:
            continue
    return out


SUBS = ("technology", "space", "cars", "Futurology")


def _reddit():
    """One multireddit request (Reddit 429s a burst of per-sub calls from one IP); JSON first, RSS as the fallback."""
    multi = "+".join(SUBS)
    for base in ("https://www.reddit.com", "https://old.reddit.com"):
        try:
            j = json.loads(_get("%s/r/%s/hot.json?limit=60&raw_json=1" % (base, multi), {"Accept": "application/json"}))
            out = []
            for c in (j.get("data") or {}).get("children") or []:
                d = c.get("data") or {}
                if not d.get("stickied"):
                    out.append({"title": d.get("title", ""), "source": "reddit:r/" + d.get("subreddit", "?"),
                                "url": "https://www.reddit.com" + d.get("permalink", ""),
                                "detail": d.get("url", ""), "score": int(d.get("ups") or 0)})
            if out:
                return out
        except Exception:
            continue
    try:
        root = ET.fromstring(_get("https://www.reddit.com/r/%s/hot/.rss?limit=60" % multi))
        out = []
        for e in [x for x in root.iter() if x.tag.split("}")[-1] == "entry"]:
            t = next((x.text for x in e if x.tag.endswith("title")), "")
            ln = next((x.get("href") for x in e if x.tag.endswith("link")), "") or ""
            cat = next((x.get("term") for x in e if x.tag.endswith("category")), "") or "?"
            out.append({"title": t or "", "source": "reddit:r/" + cat, "url": ln, "detail": "", "score": 0})
        return out
    except Exception:
        return []


def collect_trends(niche=""):
    """→ (candidates, per-source counts). Each candidate: {title, source, url, detail, score}."""
    res = {}

    def run(name, fn, *a):
        try:
            res[name] = fn(*a)
        except Exception:
            res[name] = []
    ts = [threading.Thread(target=run, args=a, daemon=True) for a in
          (("google_trends", _google_trends), ("google_news", _google_news, niche), ("youtube", _youtube),
           ("reddit", _reddit))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    seen, out = set(), []
    for name in ("google_trends", "google_news", "youtube", "reddit"):
        for c in res.get(name) or []:
            key = re.sub(r"[^a-z0-9]", "", c["title"].lower())[:60]
            if c["title"] and key not in seen:
                seen.add(key)
                out.append(c)
    return out, {k: len(v or []) for k, v in res.items()}


# ── one-shot writer (cloud brain → local engine) ───────────────────────────────────────────────────────────────────
def claude_job(pid, prompt, cwd, kind, tools=(), add_dirs=()):
    """ONE writer call → (result_text, cost_usd). Runs on the owner's cloud brain when one is on, else the local engine.
    (The name is kept for the stage code; nothing here starts a CLI.) Raises on failure."""
    import kaggle_research as KR
    os.makedirs(cwd, exist_ok=True)
    txt, _used = KR._chat_local(ROLE, prompt)
    if not str(txt or "").strip():
        raise RuntimeError("the %s writer returned nothing" % kind)
    return str(txt), 0.0


def _kill(proc):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=_NOWIN) if os.name == "nt" else proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _json_from(text):
    t = str(text or "")
    m = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", t, re.S)
    if m:
        t = m.group(1)
    for a, b in (("{", "}"), ("[", "]")):
        i, k = t.find(a), t.rfind(b)
        if i >= 0 and k > i:
            try:
                return json.loads(t[i:k + 1])
            except Exception:
                continue
    raise RuntimeError("Claude returned no usable JSON")


# ── stage 2: pick_topic ────────────────────────────────────────────────────────────────────────────────────────────
TOPIC_PROMPT = """You are the showrunner of MIR EXPLAINED, a YouTube channel of 5-8 minute cinematic explainers
(think: "The Tesla Roadster, explained" — real engineering, a physics check, what's verified vs claimed).
Today is {today}.{niche}{covered}
Below are {n} things trending right now (source · title · signal). Pick the THREE best episode topics: big search
interest right now, a concrete THING (product, mission, discovery, machine, technology) with real numbers and
mechanisms to explain, real photos available, evergreen enough to keep getting views for months. Avoid politics,
celebrity gossip, crime, tragedies, and sports scores.

{lines}

Reply with ONLY a JSON array of exactly 3 objects, best first:
[{{"topic": "<the thing, <=60 chars>", "angle": "<the episode's hook / question in one sentence>",
   "why_trending": "<what happened, with the source names>", "search_interest": "<high|medium|low + the signal>",
   "slug": "<lowercase-ascii-hyphen slug, <=24 chars>"}}]"""


def _slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:24].strip("-")
    return s or "episode"


def _unique_slug(s, pid):
    base, n = _slug(s), 1
    slug = base
    while True:
        f = os.path.join(EPISODES, slug)
        own = os.path.isfile(os.path.join(f, ".run")) and open(os.path.join(f, ".run")).read().strip() == pid
        if not os.path.exists(f) or own:
            return slug
        n += 1
        slug = "%s-%d" % (base, n)


def covered_topics():
    """Subjects the channel already has an episode for (episode.json written) — never propose them again."""
    out = []
    for d in sorted(os.listdir(EPISODES)) if os.path.isdir(EPISODES) else []:
        f = os.path.join(EPISODES, d, "episode.json")
        if d.startswith("_") or not os.path.isfile(f):
            continue
        try:
            m = json.load(open(f, encoding="utf-8")).get("meta") or {}
            out.append(str(m.get("title") or d))
        except Exception:
            out.append(d)
    extra = os.path.join(EPISODES, "_covered.txt")            # hand-added subjects ("we already did X")
    if os.path.isfile(extra):
        out += [x.strip() for x in open(extra, encoding="utf-8") if x.strip()]
    return out


def _propose(p):
    cands = sorted(p.get("candidates") or [], key=lambda c: c["source"])
    lines = "\n".join("%s · %s · %s%s" % (c["source"], c["title"][:140], c.get("score") or "-",
                                         (" · " + c["detail"][:80]) if c.get("detail") else "") for c in cands[:90])
    prompt = TOPIC_PROMPT.format(today=time.strftime("%B %d, %Y"), n=len(cands[:90]), lines=lines,
                                 niche=("\nThe owner wants this niche: %s. Prefer topics inside it." % p["niche"])
                                 if p.get("niche") else "",
                                 covered=("\nALREADY COVERED by the channel — never propose these subjects again, nor a close "
                                          "variant or follow-up of them: %s." % "; ".join(covered_topics())) if covered_topics() else "")
    text, cost = claude_job(p["id"], prompt, os.path.join(_dir(p["uid"]), "_work"), "topics")
    j = _json_from(text)
    props = []
    for x in (j if isinstance(j, list) else j.get("proposals") or [])[:3]:
        if isinstance(x, dict) and x.get("topic"):
            props.append({k: str(x.get(k) or "")[:300] for k in ("topic", "angle", "why_trending", "search_interest")}
                         | {"slug": _slug(x.get("slug") or x["topic"])})
    if len(props) < 3:
        raise RuntimeError("engine returned %d topic proposals, need 3" % len(props))
    return props, cost


def _choose(p, topic):
    """Lock in the topic: unique episode folder, marked with this run's id."""
    t = dict(topic)
    t["slug"] = _unique_slug(t.get("slug") or t["topic"], p["id"])
    f = os.path.join(EPISODES, t["slug"])
    os.makedirs(f, exist_ok=True)
    with open(os.path.join(f, ".run"), "w") as h:
        h.write(p["id"])
    p["topic"] = t
    p.update(stage="research", state="running", error=None, heals={})
    session_for(p)
    _log(p, "Topic locked: “%s” — %s. Researching it now (folder episodes/%s)." % (t["topic"], t.get("angle", ""), t["slug"]),
         "done")


def session_for(p):
    """Oct 19 2026 (user rule): every EXPLAINED project has its own Media Lab chat session named after it — every
    still / plate / music bed / narration line / render it makes is filed there, not in whatever chat is open.
    Made when the topic is locked (also becomes the open session); older runs get one on their next asset pass."""
    sid = p.get("session") or ""
    try:
        import sessions as S
        if sid and S.valid(p["uid"], sid):
            return sid
        sid = S.create(p["uid"], "EXPLAINED · " + _title(p))["id"]
        p["session"] = sid
        _log(p, "Opened a Media Lab chat session for this project: “EXPLAINED · %s” — its assets and videos go there." % _title(p))
    except Exception as e:
        print("[explained] session for project failed:", e)
    return sid


# ── stage 3: research ──────────────────────────────────────────────────────────────────────────────────────────────
RESEARCH_PROMPT = """You are the research desk of MIR EXPLAINED (cinematic 5-8 minute YouTube explainers). Today is {today}.
Episode topic: {topic}
Angle: {angle}
Why it is trending: {why}

Research it properly with WebSearch and WebFetch: open primary sources (the maker / agency / paper / filing / official
livestream write-up) and at least 3 independent quality outlets. Prefer numbers you can cite. Separate what is
VERIFIED (measured, documented, demonstrated) from what is only CLAIMED (promises, targets, rumours) — and do your own
back-of-envelope physics/maths check where a headline number allows it (state assumptions).

Then use the Write tool to write the file research.md in the current folder ({folder}), in English Markdown:

# <Topic> — research
## Lead
<3-5 sentences: what it is, why now, the one surprising fact>
## <5-8 sections, one per chapter-worthy idea: history/timeline, how it works, the key numbers, competition/context,
   physics or maths check, price/availability/regulation, open questions> — each with concrete numbers + inline [n] refs
## Verified vs claimed
| Claim | Status (VERIFIED / CLAIMED / DISPUTED) | Evidence | Source [n] |
(at least 8 rows)
## Key numbers
- bullet list of every number worth putting on screen, with unit, date and [n]
## Timeline
- YYYY-MM-DD — event [n]  (at least 5 dated events)
## Reference photos
| # | Image URL (direct .jpg/.png/.webp) | Source page | What it shows | Credit |
(as MANY real photos as you can find — aim for 12-20, never more than 20 — of the actual subject, found on pages
you opened: official press kits / image galleries first (e.g. images.nasa.gov, maker newsrooms, Wikimedia Commons).
Every row must show something DIFFERENT — another angle, detail, person, place or moment — because each one becomes
its own shot in the video and we never repeat a picture. We use them as references to recreate stills, never as-is.)
## Sources
[n] Title — Publisher — URL — date — (ONLY pages you actually opened with WebFetch)

Rules: never invent a source, URL, number or quote. If something can't be confirmed, say so in the table.
When the file is written, reply with one line: DONE <number of sources>."""


def _research(p):
    f = _folder(p)
    t = p["topic"]
    prompt = RESEARCH_PROMPT.format(today=time.strftime("%B %d, %Y"), topic=t["topic"], angle=t.get("angle") or "(find the best one)",
                                    why=t.get("why_trending") or "(find out)", folder=f)
    if p.get("research_note"):
        prompt += "\n\nThis is a REDO of the research. The owner's direction: \"%s\"" % p["research_note"]
    if RESEARCH_ENGINE(p) == "claude":
        text, cost = claude_job(p["id"], prompt, f, "research", tools=("WebSearch", "WebFetch", "Read", "Write"))
    else:   # Oct 17 2026: free research — the lab opens the web itself, the research engine (cloud / local fallback) writes
        import kaggle_research as KR
        uid, pid = p["uid"], p["id"]
        say = lambda m: _mut(uid, pid, lambda q: _log(q, m))
        gone = lambda: (load(uid, pid) or {}).get("state") == "cancelled"
        used, _n, _c = KR.write(p, f, prompt, say, gone)
        text, cost = "DONE (%s)" % used, 0.0
    path = os.path.join(f, "research.md")
    if not os.path.isfile(path):
        raise RuntimeError("the research job finished without writing research.md (%s)" % text[:160])
    md = open(path, encoding="utf-8").read()
    missing = [h for h in ("verified vs claimed", "sources", "reference photos") if h not in md.lower()]
    if len(md) < 2500 or missing:
        raise RuntimeError("research.md is incomplete (%d chars, missing: %s)" % (len(md), ", ".join(missing) or "length"))
    n_src = len(re.findall(r"^\s*\[\d+\]", md.split("## Sources")[-1], re.M))
    return cost, n_src, len(md)


# ── stage 4: script + validation ───────────────────────────────────────────────────────────────────────────────────
SCRIPT_PROMPT = """You are the head writer of MIR EXPLAINED. Turn research.md (in this folder) into the episode file
episode.json (write it here with the Write tool). Read these first:
  - research.md                                  (the facts — use ONLY these; keep the [n] refs out of the captions)
  - {example}   (a finished, approved episode: copy its voice, caption style, JSON format and asset style — NOT its
                  chapter structure: the STRUCTURE section below decides the shape of THIS episode)
  - {schema}    (the JSON schema the file MUST pass)

{structure}

Episode rules (the permanent Signature cinematic-studio style):
  - Visual types and their data: plate · bignum {{value, decimals, unit, label, sub}} · chapter · brand ·
    photo {{credit}} (beat.photo = ref file) · spec {{title, rows:[[k,v,(highlight)]]}} · gbars {{title, bars:[[label,
    value,color]], max, unit, stamp}} · trims {{cards:[{{name, price, lines:[...]}}]}} · questions {{items}} ·
    recap {{items}} · formula {{lines, note|stamp}} · midroll · endcard · timeline {{events:[{{at,label,kind}}]}}
    (kind: past|now|future|claim) · compare {{rows:[[k,old,new]], left, right}} ·
    diagram {{plate, callouts:[{{x,y,title,sub,color}}]}} (x,y = 0..1 fractions of the frame).
    Use only these types. Colours: cyan|amber|ink|red|green.
  - assets: ONE still per reference photo (use every usable photo in research.md, up to 20) plus motion plates for
    most of them. Stills "st_*": {{"model":"qimg","refs":[ref files],"prompt": recreate the REAL subject from the refs
    in a dark charcoal studio / its real setting, wide 16:9 landscape composition, photorealistic, no text, no
    watermark}}. Motion plates "pl_*": {{"model":"h3","from":"st_…","prompt": one calm continuous camera move / action,
    "seconds": 6}}. Refs are the local file names the reference photos will be downloaded to (e.g. "front.jpg").
  - NO REPEATS: every studio / card / photo / end beat shows a DIFFERENT still, plate or photo — never reuse a visual,
    and don't put a still and the plate made from it close together. More photos = more distinct shots.
  - ref_urls: one entry per ref file used (max 20): {{"url": direct image URL from research.md, "source": the page,
    "use": "<ref file name> — what it shows"}}. Never invent URLs.
  - voice {{"id":"am_michael","speed":1.0}}; music: 2 beds like the example (instrumental, no vocals).
  - meta: slug "{slug}", title, series "MIR EXPLAINED", asOf "{today}", sources (publisher — title — date).
  - shorts: exactly 3 vertical cuts {{ids: [consecutive beat ids, 20-55 s], hook (first line on screen), title}}.
  - youtube: title <=70 chars, keyword first ("<Topic> Explained: …"), description (hook, 3-line summary, chapter
    timestamps placeholder "{{chapters}}", sources list), tags (12-20), pinned_comment (a question to the viewers).
  - thumbnail: {{plate: asset key, number: the hero number as text, unit, hook: <=4 words}}.
Write facts exactly as research.md has them; mark claims as claims ("Tesla says", "according to").
{extra}
When episode.json is written, reply with one line: DONE <beats> beats."""

VISUALS = ("plate", "bignum", "chapter", "brand", "photo", "spec", "gbars", "trims", "questions", "recap", "formula",
           "midroll", "endcard", "timeline", "compare", "diagram")


def _vdef(c, props=None, req=()):
    return {"type": "object", "required": ["c"] + list(req),
            "properties": dict({"c": {"const": c}}, **(props or {}))}


def schema():
    S, N, A = {"type": "string"}, {"type": "number"}, {"type": "array"}
    strs = {"type": "array", "items": S, "minItems": 1}
    color = {"enum": ["cyan", "amber", "ink", "red", "green"]}
    v = {
        "plate": _vdef("plate"), "chapter": _vdef("chapter"), "brand": _vdef("brand"), "midroll": _vdef("midroll"),
        "endcard": _vdef("endcard"),
        "bignum": _vdef("bignum", {"value": N, "decimals": {"type": "integer", "minimum": 0, "maximum": 3}, "unit": S,
                                   "label": S, "sub": S}, ["value", "label"]),
        "photo": _vdef("photo", {"credit": S}, ["credit"]),
        "spec": _vdef("spec", {"title": S, "rows": {"type": "array", "minItems": 1,
                                                    "items": {"type": "array", "minItems": 2, "maxItems": 3}}},
                      ["title", "rows"]),
        "gbars": _vdef("gbars", {"title": S, "bars": {"type": "array", "minItems": 2, "items": {
            "type": "array", "minItems": 2, "maxItems": 3}}, "max": N, "unit": S, "stamp": S}, ["title", "bars"]),
        "trims": _vdef("trims", {"cards": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["name"], "properties": {"name": S, "price": S, "lines": {"type": "array", "items": S}}}}},
            ["cards"]),
        "questions": _vdef("questions", {"items": strs}, ["items"]),
        "recap": _vdef("recap", {"items": strs}, ["items"]),
        "formula": _vdef("formula", {"lines": strs, "note": S, "stamp": S}, ["lines"]),
        "timeline": _vdef("timeline", {"events": {"type": "array", "minItems": 2, "items": {
            "type": "object", "required": ["at", "label"], "properties": {
                "at": S, "label": S, "kind": {"enum": ["past", "now", "future", "claim"]}}}}}, ["events"]),
        "compare": _vdef("compare", {"left": S, "right": S, "rows": {"type": "array", "minItems": 2, "items": {
            "type": "array", "minItems": 3, "maxItems": 3}}}, ["rows"]),
        "diagram": _vdef("diagram", {"plate": S, "callouts": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["x", "y", "title"], "properties": {
                "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1},
                "title": S, "sub": S, "color": color}}}}, ["plate", "callouts"]),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "mir-explained/episode.schema.json",
        "title": "MIR EXPLAINED episode",
        "description": "Written by server/explainer.py (script stage). Visual types = the generic Remotion engine's vocabulary.",
        "type": "object",
        "required": ["meta", "voice", "music", "assets", "chapters", "beats", "shorts", "youtube", "thumbnail", "ref_urls"],
        "properties": {
            "meta": {"type": "object", "required": ["slug", "title", "series", "asOf", "sources"], "properties": {
                "slug": {"type": "string", "pattern": "^[a-z0-9-]{1,40}$"}, "title": S, "series": {"const": "MIR EXPLAINED"},
                "asOf": S, "sources": strs}},
            "voice": {"type": "object", "required": ["id"], "properties": {"id": {"enum": list(_voices())}, "speed": N}},
            "music": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["name", "fromChapter", "prompt", "seconds"],
                                                                "properties": {"name": S, "fromChapter": {"type": "integer"},
                                                                               "prompt": S, "seconds": N}}},
            "assets": {"type": "object", "minProperties": 4, "additionalProperties": {
                "type": "object", "required": ["model", "prompt"], "properties": {
                    "model": {"enum": ["qimg", "h3"]}, "prompt": S, "refs": {"type": "array", "items": S}, "from": S,
                    "seconds": N}}},
            "chapters": {"type": "array", "minItems": 4, "items": {"type": "object", "required": ["n", "title"],
                                                                   "properties": {"n": {"type": "integer"}, "title": S}}},
            "beats": {"type": "array", "minItems": 20, "items": {
                "type": "object", "required": ["id", "ch", "mode", "v", "cap"], "properties": {
                    "id": S, "ch": {"type": "integer"}, "mode": {"enum": ["studio", "hud", "card", "photo", "brand", "end"]},
                    "plate": S, "photo": S, "cap": S, "say": S, "pad": N,
                    "v": {"oneOf": [{"$ref": "#/$defs/v_" + c} for c in VISUALS]}}}},
            "shorts": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
                "type": "object", "required": ["ids", "hook", "title"], "properties": {
                    "ids": {"type": "array", "minItems": 1, "items": S}, "hook": S, "title": S}}},
            "youtube": {"type": "object", "required": ["title", "description", "tags", "pinned_comment"], "properties": {
                "title": {"type": "string", "maxLength": 70}, "description": S,
                "tags": {"type": "array", "minItems": 5, "items": S}, "pinned_comment": S}},
            "thumbnail": {"type": "object", "required": ["plate", "number", "unit", "hook"], "properties": {
                "plate": S, "number": S, "unit": S, "hook": S}},
            "ref_urls": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["url", "source", "use"],
                                                                   "properties": {"url": {"type": "string", "pattern": "^https?://"},
                                                                                  "source": S, "use": S}}},
        },
        "$defs": {"v_" + k: d for k, d in v.items()},
    }


def write_schema():
    os.makedirs(EPISODES, exist_ok=True)
    with open(SCHEMA, "w", encoding="utf-8") as f:
        json.dump(schema(), f, indent=2)
    return SCHEMA


_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}


def _check(x, s, root, path, errs):
    """A small JSON-Schema subset validator (type/required/properties/additionalProperties/items/enum/const/
    min/maxItems/minProperties/maxLength/pattern/minimum/maximum/$ref/oneOf) — no third-party dependency."""
    if len(errs) > 40:
        return
    if "$ref" in s:
        s = root["$defs"][s["$ref"].split("/")[-1]]
    if "oneOf" in s:
        branches = [root["$defs"][b["$ref"].split("/")[-1]] if "$ref" in b else b for b in s["oneOf"]]
        c = x.get("c") if isinstance(x, dict) else None
        hit = [b for b in branches if b.get("properties", {}).get("c", {}).get("const") == c]
        if not hit:
            errs.append("%s: visual type %r is not allowed (use one of %s)" % (path, c, ", ".join(VISUALS)))
            return
        return _check(x, hit[0], root, path, errs)
    t = s.get("type")
    if t:
        ok = isinstance(x, _TYPES[t]) and not (t in ("integer", "number") and isinstance(x, bool))
        if not ok:
            errs.append("%s: expected %s, got %s" % (path, t, type(x).__name__))
            return
    if "const" in s and x != s["const"]:
        errs.append("%s: must be %r" % (path, s["const"]))
    if "enum" in s and x not in s["enum"]:
        errs.append("%s: %r not in %s" % (path, x, s["enum"]))
    if isinstance(x, str):
        if "maxLength" in s and len(x) > s["maxLength"]:
            errs.append("%s: %d chars, max %d" % (path, len(x), s["maxLength"]))
        if "pattern" in s and not re.search(s["pattern"], x):
            errs.append("%s: %r doesn't match %s" % (path, x[:60], s["pattern"]))
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if "minimum" in s and x < s["minimum"]:
            errs.append("%s: %s < %s" % (path, x, s["minimum"]))
        if "maximum" in s and x > s["maximum"]:
            errs.append("%s: %s > %s" % (path, x, s["maximum"]))
    if isinstance(x, list):
        if len(x) < s.get("minItems", 0):
            errs.append("%s: needs at least %d items (has %d)" % (path, s["minItems"], len(x)))
        if "maxItems" in s and len(x) > s["maxItems"]:
            errs.append("%s: at most %d items (has %d)" % (path, s["maxItems"], len(x)))
        if "items" in s:
            for i, y in enumerate(x):
                _check(y, s["items"], root, "%s[%d]" % (path, i), errs)
    if isinstance(x, dict):
        for k in s.get("required", []):
            if k not in x:
                errs.append("%s: missing %r" % (path, k))
        if len(x) < s.get("minProperties", 0):
            errs.append("%s: needs at least %d entries" % (path, s["minProperties"]))
        props = s.get("properties", {})
        for k, y in x.items():
            if k in props:
                _check(y, props[k], root, "%s.%s" % (path, k), errs)
            elif isinstance(s.get("additionalProperties"), dict):
                _check(y, s["additionalProperties"], root, "%s.%s" % (path, k), errs)


def _secs(b):
    words = len(re.findall(r"[A-Za-z0-9']+", b.get("say") or b.get("cap") or ""))
    return words / 2.5 + float(b.get("pad") or (0 if words else 2.5)) + 0.4


def validate(ep, slug=None, preset=None):
    """Schema + the semantic rules the renderer relies on + the structure preset's shape → (errors, stats)."""
    sc = schema()
    errs = []
    _check(ep, sc, sc, "episode", errs)
    if not isinstance(ep, dict) or errs:
        return errs, {}
    beats, assets = ep["beats"], ep["assets"]
    ids = [b["id"] for b in beats]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append("duplicate beat ids: " + ", ".join(dup))
    chs = {c["n"] for c in ep["chapters"]}
    for b in beats:
        if b["ch"] not in chs:
            errs.append("beat %s: chapter %s doesn't exist" % (b["id"], b["ch"]))
        if b.get("cap") and not b.get("say") and re.search(r"\d", b["cap"]):
            errs.append("beat %s: caption has digits but no 'say' (TTS needs numbers spelled out)" % b["id"])
        for k in ("plate",):
            pv = b.get(k) or (b["v"].get("plate") if b["v"]["c"] == "diagram" else None)
            if pv and not re.search(r"\.(png|jpe?g|webp|mp4)$", pv, re.I) and pv not in assets:
                errs.append("beat %s: plate %r is neither an asset key nor a file" % (b["id"], pv))
        if b["v"]["c"] == "photo" and not b.get("photo"):
            errs.append("beat %s: photo beat needs beat.photo (a ref file)" % b["id"])
    for k, a in assets.items():
        if a["model"] == "h3" and a.get("from") not in assets and not re.search(r"\.(png|jpe?g|webp)$", a.get("from") or "", re.I):
            errs.append("asset %s: h3 'from' must name a qimg asset (or a still image file)" % k)
        if a["model"] == "qimg" and not a.get("refs"):
            errs.append("asset %s: qimg still needs refs (real photos)" % k)
    if len(ep["ref_urls"]) > MAX_REFS:
        errs.append("ref_urls has %d entries — use at most %d reference photos" % (len(ep["ref_urls"]), MAX_REFS))
    used = {r for a in assets.values() for r in a.get("refs") or []} | {b["photo"] for b in beats if b.get("photo")}
    named = " ".join(r["use"] for r in ep["ref_urls"])
    missing = sorted(r for r in used if r not in named)
    if missing:
        errs.append("ref files without a ref_urls entry (put the file name in 'use'): " + ", ".join(missing))
    for i, s in enumerate(ep["shorts"]):
        bad = [x for x in s["ids"] if x not in ids]
        if bad:
            errs.append("shorts[%d]: unknown beat ids %s" % (i, bad))
    if ep["thumbnail"]["plate"] not in assets and not re.search(r"\.(png|jpe?g|webp)$", ep["thumbnail"]["plate"]):
        errs.append("thumbnail.plate must be an asset key")
    if slug and ep["meta"]["slug"] != slug:
        errs.append("meta.slug must be %r" % slug)
    secs = sum(_secs(b) for b in beats)
    words = sum(len(re.findall(r"[A-Za-z0-9']+", b.get("say") or b.get("cap") or "")) for b in beats)
    sp = PR.get(preset)
    lo, hi = sp["secs"]
    if not lo <= secs <= hi:
        errs.append("estimated runtime %.0f s (%d words) — the %s structure must run %d-%d s (~%s words)"
                    % (secs, words, sp["name"], lo, hi, sp["words"]))
    errs += PR.check(ep, sp["id"])
    run, last = 1, None
    for b in beats:
        run = run + 1 if b["v"]["c"] == last else 1
        last = b["v"]["c"]
        if run > 3 and last not in ("plate",):
            errs.append("more than 3 '%s' beats in a row (at %s)" % (last, b["id"]))
            break
    return errs, {"beats": len(beats), "chapters": len(ep["chapters"]), "assets": len(assets), "words": words,
                  "est_secs": round(secs), "visuals": sorted({b["v"]["c"] for b in beats}), "structure": sp["id"]}


def _structure(p):
    """The run's structure preset id — 'auto' resolves ONCE per script (least-recently-used preset that fits)."""
    want = p.get("structure") or "auto"
    if want != "auto" and want in PR.BY_ID:
        return want
    if p.get("structure_pick") in PR.BY_ID and p.get("structure_auto_for") == (p.get("topic") or {}).get("slug"):
        return p["structure_pick"]
    recent = []
    try:
        d = _dir(p["uid"])
        runs = [json.load(open(os.path.join(d, n), encoding="utf-8")) for n in os.listdir(d) if n.endswith(".json")]
        recent = [r.get("structure_pick") or r.get("structure") for r in sorted(runs, key=lambda r: -r.get("created", 0))
                  if r.get("id") != p["id"] and (r.get("structure_pick") or r.get("structure")) in PR.BY_ID]
    except Exception:
        pass
    return PR.pick_auto((p.get("topic") or {}).get("topic", ""), recent)


def _script(p):
    f = _folder(p)
    slug = p["topic"]["slug"]
    write_schema()
    path = os.path.join(f, "episode.json")
    extra = ""
    if p.get("rewrite_note"):
        extra = ("\nREWRITE: episode.json already exists — revise it (Read it first, then Write the whole file again) "
                 "following the owner's note: \"%s\"" % p["rewrite_note"])
    sid = _structure(p)
    uid0, pid0 = p["uid"], p["id"]
    _mut(uid0, pid0, lambda q: (q.update(structure_pick=sid, structure_auto_for=(q.get("topic") or {}).get("slug")),
                                _log(q, "Structure: %s%s — %s" % (PR.get(sid)["name"], " (picked automatically)"
                                     if (q.get("structure") or "auto") == "auto" else "", PR.get(sid)["tag"]))))
    total, errs, stats = 0.0, [], {}
    for attempt in range(3):                              # first draft + max 2 corrective retries
        if attempt:
            extra = ("\nFIX: episode.json failed validation. Read it, fix EVERY problem below and Write the whole file "
                     "again (keep everything else):\n- " + "\n- ".join(errs[:30]))
            _mut(p["uid"], p["id"], lambda q: _log(q, "Script check found %d problem(s) — sending it back to the writer "
                                                       "(retry %d of 2)." % (len(errs), attempt), "warn"))
        prompt = SCRIPT_PROMPT.format(example=EXAMPLE, schema=SCHEMA, slug=slug, today=time.strftime("%Y-%m-%d"),
                                      extra=extra, structure=PR.structure(sid))
        if SCRIPT_ENGINE(p) == "claude":
            _, cost = claude_job(p["id"], prompt, f, "script", tools=("Read", "Write"), add_dirs=(EPISODES,))
            total += cost
        else:   # Oct 17 2026: same blueprint (prompt, Roadster example, schema, validator + 2 fixes) on the free desk
            import kaggle_research as KR
            uid, pid = p["uid"], p["id"]
            prev = None
            if attempt:
                for cand in (path, path + ".raw.txt"):
                    if os.path.isfile(cand):
                        prev = open(cand, encoding="utf-8").read()
                        break
            try:
                KR.write_script(p, f, prompt, EXAMPLE, SCHEMA, lambda m: _mut(uid, pid, lambda q: _log(q, m)),
                                lambda: (load(uid, pid) or {}).get("state") == "cancelled",
                                prev=prev, errs=errs if attempt else None)
            except ValueError as e:
                errs = [str(e)]
                continue
        try:
            with open(path, encoding="utf-8") as h:
                ep = json.load(h)
        except FileNotFoundError:
            errs = ["episode.json was not written"]
            continue
        except Exception as e:
            errs = ["episode.json is not valid JSON: %s" % e]
            continue
        errs, stats = validate(ep, slug, sid)
        if not errs:
            return total, stats, attempt
    raise RuntimeError("script failed validation after 2 retries: " + "; ".join(errs[:6]))


# ── control ────────────────────────────────────────────────────────────────────────────────────────────────────────
def start(uid, niche="", topic="", auto=False, structure="auto", voice=None):
    niche, topic = str(niche or "").strip()[:200], str(topic or "").strip()[:200]
    structure = structure if structure in PR.BY_ID else "auto"
    voice = voice if voice in _voices() else NARRATOR
    p = {"id": uuid.uuid4().hex[:12], "uid": uid, "niche": niche, "auto": bool(auto), "state": "running",
         "stage": "trends", "created": time.time(), "error": None, "log": [], "heals": {}, "cost": 0.0, "epoch": 0,
         "structure": structure, "voice": voice}
    _log(p, "EXPLAINED run started%s%s — structure: %s." % (
        (" — niche: " + niche) if niche else "",
        " (fully automatic)" if auto else " (I'll check in with you at each checkpoint)",
        PR.get(structure)["name"] if structure != "auto" else "Auto (a different one from the last episodes)"), "done")
    if topic:
        _choose(p, {"topic": topic, "angle": "", "why_trending": "chosen by you", "search_interest": "", "slug": _slug(topic)})
    save(uid, p)
    _activate(uid, p["id"])
    return public(p)


def control(uid, pid, action, body=None):
    body = body or {}

    def apply(p):
        p["epoch"] = p.get("epoch", 0) + 1                    # any in-flight worker result for the old epoch is dropped
        st = p["stage"]
        if action == "pick":
            if st != "pick_topic":
                raise ValueError("no topic choice is waiting")
            if body.get("topic"):
                t = str(body["topic"]).strip()[:200]
                _choose(p, {"topic": t, "angle": str(body.get("angle") or "")[:300], "why_trending": "chosen by you",
                            "search_interest": "", "slug": _slug(t)})
            else:
                n = int(body.get("n") or 1)
                props = p.get("proposals") or []
                if not 1 <= n <= len(props):
                    raise ValueError("pick 1-%d" % len(props))
                _choose(p, props[n - 1])
        elif action == "approve":
            if st == "approve_final":
                p.update(stage="publish", state="running", error=None, heals={})
                _log(p, "Video approved — putting the main video and the Shorts into Social as drafts.", "done")
            elif st != "approve_script":
                raise ValueError("nothing is waiting for your approval")
            else:
                _approved(p)
        elif action == "rewrite":
            if st not in ("approve_script", "script"):
                raise ValueError("there is no script to rewrite yet")
            p.update(stage="script", state="running", error=None, heals={},
                     rewrite_note=str(body.get("note") or "make it tighter and punchier").strip()[:1200])
            _log(p, "Rewriting the script with your note: " + p["rewrite_note"][:200], "done")
        elif action == "auto":
            p["auto"] = bool(body.get("on", not p.get("auto")))
            _log(p, "Fully automatic %s." % ("ON — I'll take the top topic and approve my own script; publishing still "
                                            "needs your Approve in Social" if p["auto"] else "OFF — I'll wait for you at each checkpoint"))
            if p["auto"] and p["state"] == "waiting" and st in ("pick_topic", "approve_script"):
                p["state"] = "running"
        elif action in ("retry", "resume"):
            if p["state"] == "done":                        # Oct 17 2026: a cancelled run can be picked back up
                raise ValueError("this run is done")
            p.update(state="waiting" if st in CHECKPOINTS and _ready_checkpoint(p) else "running", error=None,
                     retry_at=0, heals={})
            _log(p, "Resuming at %s." % LABEL.get(st, st))
        elif action == "structure":                   # before the script: just set it; after: rewrite the script in it
            s = str(body.get("structure") or "auto")
            if s != "auto" and s not in PR.BY_ID:
                raise ValueError("unknown structure — one of: auto, " + ", ".join(PR.BY_ID))
            p["structure"] = s
            p.pop("structure_pick", None)
            if STAGES.index(st) > STAGES.index("script") or (_folder(p) and os.path.isfile(os.path.join(_folder(p), "episode.json"))):
                _redo(p, "script")
            _log(p, "Structure set to %s." % (PR.get(s)["name"] if s != "auto" else "Auto"))
        elif action == "voice":                       # narrator: before the narration it's just set; after, it re-voices
            v = str(body.get("voice") or "")
            if v not in _voices():
                raise ValueError("unknown voice — one of: " + ", ".join(_voices()))
            if p.get("state") == "running" and st in ("assets", "render"):
                raise ValueError("The video is being made right now — change the voice once this step finishes (or pause it).")
            p["voice"] = v
            spec_path = os.path.join(_folder(p) or "", "episode.json")
            if os.path.isfile(spec_path):
                spec = json.load(open(spec_path, encoding="utf-8"))
                spec.setdefault("voice", {})["id"] = v
                with open(spec_path, "w", encoding="utf-8") as h:
                    json.dump(spec, h, indent=1, ensure_ascii=False)
            if STAGES.index(st) > STAGES.index("assets") or (st == "assets" and p.get("state") != "running"):
                _redo(p, "assets", ["vo"])           # new voice = new narration files (the hash has the voice) + re-render
            _log(p, "Narrator voice: %s." % _voices()[v].split(" · ")[0], "done")
        elif action == "redo":
            if body.get("structure"):                 # "rewrite in another structure" = redo the script with a new preset
                s = str(body["structure"])
                if s != "auto" and s not in PR.BY_ID:
                    raise ValueError("unknown structure — one of: auto, " + ", ".join(PR.BY_ID))
                p["structure"] = s
                p.pop("structure_pick", None)
            _redo(p, str(body.get("step") or ""), body.get("items"), str(body.get("note") or "").strip()[:1200])
        elif action == "scene":                   # edit (or just redo) one on-screen text scene, re-render what shows it
            if p.get("state") == "running" and st in ("research", "script", "assets"):
                raise ValueError("The episode is still being made (%s) — save this scene once that finishes." % LABEL.get(st, st))
            bid = str(body.get("beat") or "")
            names = _scene_edit(p, bid, body.get("v"), body.get("title"))
            _redo(p, "render", names)
            _log(p, "Scene %s %s - re-rendering %s." % (bid, "updated" if (body.get("v") or body.get("title")) else "redone",
                                                         ", ".join(names)), "done")
            _scene_preview(p, bid)
        elif action == "scene_preview":
            _scene_preview(p, str(body.get("beat") or ""))
            return
        elif action == "cancel":
            p["state"] = "cancelled"
            _log(p, "Cancelled. Everything written so far stays in episodes/%s." % ((p.get("topic") or {}).get("slug") or "—"))
        else:
            raise ValueError("unknown action")

    if action == "delete":
        with _lock(pid):
            path = os.path.join(_dir(uid), pid + ".json")
            if re.match(r"^[a-f0-9]{12}$", pid) and os.path.isfile(path):
                os.remove(path)
        return {"deleted": pid}
    with _lock(pid):
        p = load(uid, pid)
        if not p:
            raise ValueError("no such run")
        apply(p)
        save(uid, p)
    if action in ("cancel", "redo", "scene") and pid in _PROCS:      # a running render restarts with the new scene
        _kill(_PROCS[pid])
    _activate(uid, pid)
    return public(p)


def _ready_checkpoint(p):
    return (p["stage"] == "pick_topic" and p.get("proposals")) or p["stage"] in ("approve_script", "approve_final")


def _approved(p):
    p.pop("rewrite_note", None)
    try:
        _stale_after_script(p)
    except Exception as e:
        _log(p, "Couldn't compare the new script with the old one (%s) — keeping the existing assets." % str(e)[:160], "warn")
    p.update(stage="assets", error=None, heals={})
    if "assets" in STAGE_HANDLERS:
        p["state"] = "running"
        _log(p, "Script approved — making the Media Lab assets next.", "done")
    else:
        p["state"] = "waiting"
        _log(p, "Script approved — episodes/%s/episode.json is ready for the assets stage." % p["topic"]["slug"], "done")


# ── redo: any step, any single render ────────────────────────────────────────────────────────────────────────────────
# Nothing is deleted: everything a redo replaces is moved to a _redo/<time>-<step>/ folder next to it, so an old take can
# always be restored by hand. The asset builder (explained_build.py) skips any file that already exists, so moving one
# file aside = exactly that item is made again on the next assets pass; everything else is reused. The render stage
# likewise skips outputs that exist, so redoing one Short re-renders only that Short.
REDO_STEPS = ("trends", "pick_topic", "research", "script", "assets", "render", "publish")
RENDERS = ("main", "thumb", "short1", "short2", "short3")


def _pub(p):
    return os.path.join(REMOTION, "public", "episodes", p["topic"]["slug"])


def _outd(p):
    return os.path.join(REMOTION, "out", p["topic"]["slug"])


def _render_file(n):
    return n + (".jpg" if n == "thumb" else ".mp4")


def _stash(p, paths, step):
    """Move files aside into <their dir>/_redo/<stamp>-<step>/ -> list of moved names."""
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + step
    moved = []
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        d = os.path.join(os.path.dirname(path), "_redo", stamp)
        os.makedirs(d, exist_ok=True)
        for k in range(8):                  # Oct 18: a video still open in a player/stream is locked on Windows — wait it out
            try:
                os.replace(path, os.path.join(d, os.path.basename(path)))
                break
            except PermissionError:
                if k == 7:
                    raise ValueError("%s is open somewhere (a video player or the page playing it) — close it and try "
                                     "again" % os.path.basename(path))
                time.sleep(2)
        moved.append(os.path.basename(path))
    return moved


def _spec(p, name="episode.json"):
    try:
        with open(os.path.join(_folder(p), name), encoding="utf-8") as h:
            return json.load(h)
    except Exception:
        return None


def _asset_files(p, key):
    """Files on disk for one asset item. key: an asset key | vo:<beat> | vo | music:<name> | ref:<file> | refs."""
    pub = _pub(p)
    if not os.path.isdir(pub):
        return []
    names = os.listdir(pub)
    if key == "vo":
        return [os.path.join(pub, n) for n in names if n.startswith("vo_")]
    if key.startswith("vo:"):
        return [os.path.join(pub, n) for n in names if n.startswith("vo_%s_" % key[3:])]
    if key == "sfx":                                  # this episode's own SFX takes (explained_build sfx_plan)
        return [os.path.join(pub, n) for n in names if re.match(r"^sfx_[a-z]+_\d+\.mp3$", n)]
    if key == "refs" or key.startswith("ref:"):
        rd = os.path.join(pub, "ref")
        if not os.path.isdir(rd):
            return []
        return [os.path.join(rd, n) for n in os.listdir(rd) if os.path.isfile(os.path.join(rd, n))
                and n != "sources.json" and (key == "refs" or n == key[4:])]
    if key.startswith("music:"):
        key = key[6:]
    return [os.path.join(pub, n) for n in (key + ".png", key + ".mp4", key + ".mp3") if n in names]


def _dependents(spec, keys):
    """Stills/plates made FROM a redone still (line-art passes, H3 plates) are stale too."""
    A = (spec or {}).get("assets") or {}
    out, grow = set(keys), True
    while grow:
        grow = False
        for k, a in A.items():
            if k not in out and (a.get("from") in out or a.get("lineart_of") in out):
                out.add(k)
                grow = True
    return out


def _stale_posts(p):
    """Drafts made from an old cut must never be approved by mistake: still-draft posts are marked rejected."""
    posts = p.pop("posts", None) or {}
    p["awaiting"] = None
    if not posts:
        return
    p.setdefault("posts_old", []).append(posts)
    try:
        import social
        for sid in posts.values():
            if (social.get(sid) or {}).get("status") in ("draft", "failed"):
                social.update(sid, status="rejected", error="replaced by a redo in EXPLAINED")
    except Exception:
        pass


def _stale_renders(p, why):
    moved = _stash(p, [os.path.join(_outd(p), _render_file(n)) for n in RENDERS], why)
    p.pop("renders", None)
    p.pop("mix", None)
    _stale_posts(p)
    return moved


def _stale_after_script(p):
    """A new script was approved after a redo: move aside exactly the assets whose recipe changed."""
    prev_path = os.path.join(_folder(p), "episode.prev.json")
    prev = _spec(p, "episode.prev.json")
    if not prev:
        return
    cur = _spec(p) or {}
    A0, A1 = prev.get("assets") or {}, cur.get("assets") or {}
    sig = lambda a: json.dumps({k: a.get(k) for k in ("model", "prompt", "refs", "from", "seconds", "lineart_of")}, sort_keys=True)
    changed = {k for k in A0 if k not in A1 or sig(A0[k]) != sig(A1[k])} | {k for k in A1 if k not in A0}
    keys = list(_dependents(cur, changed) | changed)
    m0 = {m["name"]: m for m in prev.get("music") or []}
    keys += ["music:" + m["name"] for m in cur.get("music") or []
             if json.dumps(m0.get(m["name"]), sort_keys=True) != json.dumps(m, sort_keys=True)]
    if json.dumps(prev.get("ref_urls"), sort_keys=True) != json.dumps(cur.get("ref_urls"), sort_keys=True):
        keys.append("refs")
    moved = _stash(p, [f for k in keys for f in _asset_files(p, k)], "script")
    moved += _stale_renders(p, "script")
    _stash(p, [prev_path], "script")
    if moved:
        _log(p, "New script: %d file(s) whose recipe changed will be made again (unchanged assets and narration lines "
                "are reused): %s" % (len(moved), ", ".join(sorted(moved))[:240]))


def _prep_rescript(p, keep_text):
    """Before the writer runs again: keep what the assets were made from (episode.prev.json, compared on approval) and
    give the writer back its own version (the engine-normalized one is set aside)."""
    import shutil
    f = _folder(p)
    ep, orig, prev = (os.path.join(f, n) for n in ("episode.json", "episode.orig.json", "episode.prev.json"))
    base = orig if os.path.isfile(orig) else ep
    if os.path.isfile(base) and not os.path.isfile(prev) and (os.path.isfile(orig) or _pub_has(p)):
        shutil.copy2(base, prev)
    if os.path.isfile(orig):
        _stash(p, [ep], "script")
        if keep_text:
            os.replace(orig, ep)                      # a rewrite edits the writer's own version
        else:
            _stash(p, [orig], "script")
    elif not keep_text:
        _stash(p, [ep], "script")


def _pub_has(p):
    try:
        return bool(os.listdir(_pub(p)))
    except Exception:
        return False


def _redo(p, step, items=None, note=""):
    """Send the run back to `step`. items narrows assets/render to single pieces. Downstream outputs become stale."""
    if step not in REDO_STEPS:
        raise ValueError("redo which step? one of: " + ", ".join(REDO_STEPS))
    cur = p.get("stage") if p.get("stage") in STAGES else "trends"
    if STAGES.index(step) > STAGES.index(cur) and not (step == "publish" and p.get("posts")):
        raise ValueError("that step hasn't run yet")
    if step in ("research", "script", "assets", "render", "publish") and not (p.get("topic") or {}).get("slug"):
        raise ValueError("no topic chosen yet")
    items = [str(x) for x in (items or []) if str(x).strip()]
    p.update(state="running", error=None, heals={}, retry_at=0, awaiting=None)
    p.pop("progress", None)
    what = step
    if step == "trends":
        p.pop("candidates", None)
        p.pop("proposals", None)
        what = "the trends pull"
    elif step == "pick_topic":
        p.pop("proposals", None)
        what = "the topic proposals"
    elif step == "research":
        p["research_note"] = note or None
        _stash(p, [os.path.join(_folder(p), "research.md")], "research")
        _prep_rescript(p, keep_text=False)
        p.pop("validation", None)
        what = "the research" + (" (your note: %s)" % note[:120] if note else "")
    elif step == "script":
        p.pop("validation", None)
        if note:
            p["rewrite_note"] = note
        else:
            p.pop("rewrite_note", None)
        _prep_rescript(p, keep_text=bool(note))
        what = "the script" + (" with your note: %s" % note[:120] if note else " from scratch")
    elif step == "assets":
        spec = _spec(p) or {}
        A = spec.get("assets") or {}
        keys = items if items and items != ["all"] else \
            list(A) + ["vo", "refs", "sfx"] + ["music:" + m["name"] for m in spec.get("music") or []]
        bad = [k for k in keys if not (k in A or k in ("vo", "refs", "sfx") or k.split(":")[0] in ("vo", "ref", "music"))]
        if bad:
            raise ValueError("unknown asset item(s): " + ", ".join(bad))
        if "sfx" in keys:                             # new seed = different prompts made AND a different deal per cut
            import random
            spec["sfx_seed"] = random.randint(1, 10 ** 6)
            with open(os.path.join(_folder(p), "episode.json"), "w", encoding="utf-8") as h:
                json.dump(spec, h, indent=1, ensure_ascii=False)
        plain = [k for k in keys if k in A]
        keys = sorted(_dependents(spec, plain)) + [k for k in keys if k not in A]
        moved = _stash(p, [f for k in keys for f in _asset_files(p, k)], "assets")
        _stale_renders(p, "assets")
        what = ("%d asset file(s): %s" % (len(moved), ", ".join(sorted(moved))[:220])) if moved else "the assets"
    elif step == "render":
        names = list(RENDERS) if not items or items == ["all"] else items
        bad = [n for n in names if n not in RENDERS]
        if bad:
            raise ValueError("unknown render(s): %s - use %s" % (", ".join(bad), ", ".join(RENDERS)))
        _stash(p, [os.path.join(_outd(p), _render_file(n)) for n in names], "render")
        if p.get("renders"):
            p["renders"] = {k: v for k, v in p["renders"].items() if k not in names}
        _stale_posts(p)
        p.pop("mix", None)
        what = "the render of " + ", ".join(names)
    elif step == "publish":
        _stale_posts(p)
        what = "the Social drafts (the old drafts are marked rejected so they can't be approved)"
    p["stage"] = step
    _log(p, "Redoing %s. Everything it replaces is kept in a _redo folder." % what, "done")


def redo_items(p):
    """What can be redone right now, for the page: steps + every asset item + every render."""
    st = p.get("stage") if p.get("stage") in STAGES else "trends"
    idx = STAGES.index(st)
    out = {"steps": [s for s in REDO_STEPS if STAGES.index(s) <= idx or (s == "publish" and p.get("posts"))]}
    if not (p.get("topic") or {}).get("slug") or idx < STAGES.index("assets"):
        return out
    spec = _spec(p) or {}
    pub = _pub(p)
    have = set(os.listdir(pub)) if os.path.isdir(pub) else set()
    out["assets"] = [{"key": k, "model": a.get("model"), "file": next((n for n in (k + ".png", k + ".mp4") if n in have), None),
                      "prompt": str(a.get("prompt") or "")[:220]} for k, a in (spec.get("assets") or {}).items()]
    out["music"] = [{"key": "music:" + m["name"], "file": (m["name"] + ".mp3") if (m["name"] + ".mp3") in have else None,
                     "prompt": str(m.get("prompt") or "")[:160]} for m in spec.get("music") or []]
    vo = {n.split("_")[1]: n for n in have if n.startswith("vo_")}
    out["vo"] = [{"key": "vo:" + b["id"], "file": vo.get(b["id"]), "say": (b.get("say") or b.get("cap") or "")[:140]}
                 for b in spec.get("beats") or [] if (b.get("say") or b.get("cap"))]
    rd = os.path.join(pub, "ref")
    out["refs"] = [{"key": "ref:" + n, "file": "ref/" + n} for n in sorted(os.listdir(rd))
                   if n != "sources.json" and os.path.isfile(os.path.join(rd, n))] if os.path.isdir(rd) else []
    od = _outd(p)
    out["renders"] = [{"name": n, "file": _render_file(n) if os.path.isfile(os.path.join(od, _render_file(n))) else None}
                      for n in RENDERS]
    out["sfx"] = [{"file": n, "kind": n.split("_")[1]} for n in sorted(have) if re.match(r"^sfx_[a-z]+_\d+\.mp3$", n)]
    out["sfx_seed"] = spec.get("sfx_seed", 0)
    out["scenes"] = _scenes(p)
    return out


# ── Remotion scenes (Oct 18, user: "add the option to redo the remotion caption scene"): every on-screen text/graphic
# beat (title card, chapter cards, big numbers, timelines, tables, bars, lists, end card…) can be edited, previewed as
# a still, and re-rendered on its own. Editing writes the beat's data in BOTH episode.json and the resolved timeline
# (mtime kept, so only the renders that contain the beat are redone, not the whole set).
SCENE_KINDS = ("brand", "chapter", "bignum", "timeline", "spec", "gbars", "compare", "questions", "recap", "formula",
               "trims", "midroll", "endcard", "diagram", "photo")
SCENE_LBL = {"brand": "Title card", "chapter": "Chapter card", "bignum": "Big number", "timeline": "Timeline", "spec": "Table",
             "gbars": "Bar chart", "compare": "Comparison", "questions": "Open questions", "recap": "Recap list",
             "formula": "Formula", "trims": "Cards", "midroll": "Like & subscribe", "endcard": "End card",
             "diagram": "Diagram", "photo": "Photo credit"}


def _resolved_path(p):
    return os.path.join(REMOTION, "src", "explained", "episodes", p["topic"]["slug"] + ".json")


def _scene_dir(p):
    return os.path.join(_outd(p), "scenes")


def _scenes(p):
    try:
        with open(_resolved_path(p), encoding="utf-8") as h:
            ep = json.load(h)
    except Exception:
        return []
    spec = _spec(p) or {}
    shorts = spec.get("shorts") or []
    sd = _scene_dir(p)
    out = []
    for b in ep.get("beats") or []:
        c = (b.get("v") or {}).get("c")
        if c not in SCENE_KINDS:
            continue
        title = ep["meta"].get("title", "") if c in ("brand", "endcard") else \
            next((ch.get("title", "") for ch in ep.get("chapters") or [] if ch.get("n") == b.get("ch")), "") if c == "chapter" else None
        prev = os.path.join(sd, b["id"] + ".jpg")
        clip = os.path.join(sd, b["id"] + ".mp4")
        out.append({"id": b["id"], "kind": c, "label": SCENE_LBL.get(c, c), "start": b.get("start", 0), "dur": b.get("dur", 0),
                    "v": {k: v for k, v in (b.get("v") or {}).items() if k != "c"}, "title": title,
                    "preview": ("scenes/%s.jpg" % b["id"]) if os.path.isfile(prev) else None,
                    "clip": os.path.isfile(clip),
                    "preview_t": int(os.path.getmtime(prev)) if os.path.isfile(prev) else 0, "busy": (p.get("id"), b["id"]) in _SCENE_BUSY,
                    "shorts": ["short%d" % (i + 1) for i, s in enumerate(shorts[:3]) if b["id"] in (s.get("ids") or [])]})
    return out


def _scene_edit(p, bid, v=None, title=None):
    """Write a scene's new data into episode.json + the resolved timeline. -> the renders that contain it."""
    paths = [os.path.join(_folder(p), "episode.json"), _resolved_path(p)]
    hit = None
    for path in paths:
        if not os.path.isfile(path):
            continue
        st = os.stat(path)
        with open(path, encoding="utf-8") as h:
            ep = json.load(h)
        b = next((x for x in ep.get("beats") or [] if x.get("id") == bid), None)
        if not b:
            continue
        c = (b.get("v") or {}).get("c")
        if c not in SCENE_KINDS:
            raise ValueError("beat %s isn't an on-screen text scene" % bid)
        if isinstance(v, dict):
            b["v"] = dict(v, c=c)
        if title is not None and str(title).strip():
            if c in ("brand", "endcard"):
                ep.setdefault("meta", {})["title"] = str(title).strip()[:160]
            elif c == "chapter":
                for ch in ep.get("chapters") or []:
                    if ch.get("n") == b.get("ch"):
                        ch["title"] = str(title).strip()[:120]
        hit = c
        with open(path, "w", encoding="utf-8") as h:
            json.dump(ep, h, indent=1, ensure_ascii=False)
        if path == _resolved_path(p):
            os.utime(path, (st.st_atime, st.st_mtime))   # the timeline didn't change length: don't stale every render
    if not hit:
        raise ValueError("no scene %s" % bid)
    sc = next((s for s in _scenes(p) if s["id"] == bid), {})
    names = ["main"] + sc.get("shorts", [])
    if hit in ("brand", "endcard") and title:
        names = list(RENDERS)                         # the episode title shows up everywhere (thumb tag, Shorts end)
    return names


def _scene_preview(p, bid):
    """Queue a playable preview of one scene (or bid "all" = every scene): a half-size MP4 of the scene as it plays in the
    video — animation, narration, SFX, music — up to 8 s, plus a poster frame. One render at a time, in the background.
    -> out/<slug>/scenes/<id>.mp4 + <id>.jpg (Oct 18, user: "make sure the remotion scenes can be viewed in the editor")."""
    with open(_resolved_path(p), encoding="utf-8") as h:
        ep = json.load(h)
    ids = [x["id"] for x in ep["beats"] if (x.get("v") or {}).get("c") in SCENE_KINDS] if bid == "all" else [bid]
    if not ids or (bid != "all" and not any(x["id"] == bid for x in ep["beats"])):
        raise ValueError("no scene %s" % bid)
    for i in ids:
        if (p["id"], i) not in _SCENE_BUSY:
            _SCENE_BUSY.add((p["id"], i))
            _SCENE_Q.append((dict(p), i))
    global _SCENE_WORKER
    if not (_SCENE_WORKER and _SCENE_WORKER.is_alive()):
        _SCENE_WORKER = threading.Thread(target=_scene_worker, daemon=True, name="scene-previews")
        _SCENE_WORKER.start()


def _scene_worker():
    rcli = [engines.node(), os.path.join(REMOTION, "node_modules", "@remotion", "cli", "remotion-cli.js")]
    ff = core.FFMPEG or "ffmpeg"
    while _SCENE_Q:
        p, bid = _SCENE_Q.pop(0)
        try:
            with open(_resolved_path(p), encoding="utf-8") as h:
                ep = json.load(h)
            b = next((x for x in ep["beats"] if x["id"] == bid), None)
            if not b:
                continue
            sd = _scene_dir(p)
            os.makedirs(sd, exist_ok=True)
            props = os.path.join(sd, "_props.json")
            with open(props, "w", encoding="utf-8") as h:
                json.dump({"ep": ep}, h)
            a = int(round(b["start"] * 30))
            z = int(round((b["start"] + min(b["dur"], 8.0)) * 30)) - 1
            out = os.path.join(sd, bid + ".mp4")
            subprocess.run(rcli + ["render", "src/index.ts", "ExplainedEpisode", out + ".tmp.mp4", "--frames=%d-%d" % (a, z),
                            "--scale=0.5", "--codec=h264", "--crf=26", "--concurrency=4", "--props=" + props, "--log=error"],
                           cwd=REMOTION, capture_output=True, timeout=900, creationflags=_NOWIN)
            if os.path.isfile(out + ".tmp.mp4"):
                os.replace(out + ".tmp.mp4", out)
                pt = min(b["dur"], 8.0) * 0.6
                subprocess.run([ff, "-v", "error", "-y", "-ss", "%.2f" % pt, "-i", out, "-frames:v", "1", os.path.join(sd, bid + ".jpg")],
                               capture_output=True, timeout=60, creationflags=_NOWIN)
        except Exception:
            traceback.print_exc()
        finally:
            _SCENE_BUSY.discard((p["id"], bid))


_SCENE_BUSY = set()
_SCENE_Q = []
_SCENE_WORKER = None


def _activate(uid, pid):
    global _STARTED
    with _GUARD:
        _ACTIVE.add((uid, pid))
        if not _STARTED:
            _STARTED = True
            threading.Thread(target=_loop, daemon=True, name="explained").start()


def setup(hk):
    HK.update(hk)
    try:                                   # stages 6-10 (assets → render → approve_final → publish)
        import explainer_back
        explainer_back.install()
    except Exception:
        traceback.print_exc()
    try:
        write_schema()
    except Exception:
        pass
    for u in (os.listdir(RUNS) if os.path.isdir(RUNS) else []):        # carry on after a restart / crash
        if not os.path.isdir(os.path.join(RUNS, u)):
            continue
        for n in os.listdir(os.path.join(RUNS, u)):
            if not n.endswith(".json"):
                continue
            p = load(u, n[:-5])
            if p and p.get("state") == "running":
                def wake(q):
                    _log(q, "The lab came back up — picking this run back up at %s." % LABEL.get(q.get("stage"), ""), "warn")
                    q["retry_at"] = time.time() + 15
                _mut(p["uid"], p["id"], wake)
                _activate(p["uid"], p["id"])
            elif p and p.get("stage") in STAGE_HANDLERS and p.get("state") == "waiting" and p["stage"] not in CHECKPOINTS:
                _mut(p["uid"], p["id"], lambda q: q.update(state="running"))     # a later stage got installed
                _activate(p["uid"], p["id"])
    global _STARTED
    with _GUARD:                           # the loop also runs the research-engine watchdog (a no-op unless one is wired in)
        if not _STARTED:
            _STARTED = True
            threading.Thread(target=_loop, daemon=True, name="explained").start()


def _kaggle_watch():
    """Research-engine housekeeping every ~30 s (kaggle_research.watchdog — nothing to do for a user-run engine)."""
    try:
        import kaggle_research as KR
        runs = [p for u in (os.listdir(RUNS) if os.path.isdir(RUNS) else []) if os.path.isdir(os.path.join(RUNS, u))
                for p in _all(u)]
        last = max(runs, key=lambda p: p.get("updated", 0), default=None)
        KR.watchdog(runs, (lambda m: _mut(last["uid"], last["id"], lambda q: _log(q, m, "done"))) if last else None)
    except Exception:
        traceback.print_exc()


def _loop():
    n = 0
    while True:
        time.sleep(TICK)
        n += 1
        if n % 8 == 0:
            _kaggle_watch()
        with _GUARD:
            todo = list(_ACTIVE)
        for uid, pid in todo:
            p = load(uid, pid)
            if not p or p.get("state") != "running":
                with _GUARD:
                    _ACTIVE.discard((uid, pid))
                continue
            if p.get("retry_at", 0) > time.time() or pid in _BUSY:
                continue
            with _GUARD:
                _BUSY.add(pid)
            threading.Thread(target=_work, args=(p,), daemon=True, name="explained-" + pid).start()


def _work(p):
    uid, pid, epoch, stage = p["uid"], p["id"], p.get("epoch", 0), p["stage"]
    try:
        _tick(p)
    except Exception as e:
        traceback.print_exc()

        def fail(q):
            if q.get("epoch", 0) != epoch or q.get("stage") != stage or q.get("state") != "running":
                return False                                    # the person changed something meanwhile
            _heal(q, str(e), LABEL.get(stage, "this step"))
        _mut(uid, pid, fail)
    finally:
        with _GUARD:
            _BUSY.discard(pid)


# ── self-healing ───────────────────────────────────────────────────────────────────────────────────────────────────
def _diagnose(err):
    e = str(err or "").lower()
    if "research engine needed" in e:                 # research/script never fall back to the weak local model
        return "kaggle", str(err)[:240], "Set a research engine in Settings → AI, turn on a cloud brain, or allow the local engine, then tap Retry"
    if re.search(r"credit balance", e):
        return "auth", "the Anthropic API key is out of credits", "Top up the key or sign in to Claude Code (claude auth login), then tap Retry"
    if re.search(r"not logged in|auth|login|401", e):
        return "auth", "Claude Code isn't signed in", "I'll try again in a few minutes — sign in to Claude Code if it keeps failing"
    if re.search(r"rate.?limit|overloaded|529|429|usage limit", e):
        return "limit", "Claude is rate-limited right now", "I'll wait a few minutes and retry"
    if re.search(r"timed? ?out|timeout|stuck|stall", e):
        return "stall", "the job took far too long", "I restarted it"
    if re.search(r"urlopen|connection|network|resolve|unreachable|refused", e):
        return "net", "the network wasn't answering", "I'll retry in a minute"
    return "default", "something went wrong (%s)" % str(err)[:160], "I'll try that step again"


def _heal(p, err, where="this step"):
    kind, why, fix = _diagnose(err)
    h = p.setdefault("heals", {})
    h[kind] = h.get(kind, 0) + 1
    if kind == "kaggle":                            # nothing to retry until the person sets an engine — stop and ask
        p.update(state="paused", error=str(err)[:400])
        _log(p, "%s is waiting for the research engine: %s. %s." % (where[:1].upper() + where[1:], why, fix), "error")
        return False
    if h[kind] > MAX_HEAL:
        p.update(state="paused", error=str(err)[:400])
        _log(p, "I couldn't get past %s on my own: %s, %d times in a row. Check the EXPLAINED page, then tap Retry."
             % (where, why, MAX_HEAL), "error")
        return False
    p.update(state="running", error=None, retry_at=time.time() + COOL.get(kind, COOL["default"]))
    _log(p, "%s failed — %s. %s (fix %d of %d)." % (where[:1].upper() + where[1:], why, fix, h[kind], MAX_HEAL), "warn")
    return True


# ── the state machine ──────────────────────────────────────────────────────────────────────────────────────────────
def _tick(p):
    """Do the slow work for p's stage (no lock held), then commit through _mut only if nothing changed meanwhile."""
    uid, pid, st, epoch = p["uid"], p["id"], p["stage"], p.get("epoch", 0)

    def commit(fn):
        def g(q):
            if q.get("epoch", 0) != epoch or q.get("stage") != st or q.get("state") != "running":
                return False
            fn(q)
        return _mut(uid, pid, g)

    if st == "trends":
        cands, counts = collect_trends(p.get("niche") or "")
        live = [k for k, v in counts.items() if v]
        if len(cands) < MIN_CANDIDATES or len(live) < 2:
            raise RuntimeError("network: only %d trending candidates from %s" % (len(cands), live or "no source"))

        def ok(q):
            q.update(candidates=cands, trend_counts=counts, stage="pick_topic", heals={})
            _log(q, "Found %d trending candidates (%s). Asking Claude for the 3 best episode topics."
                 % (len(cands), ", ".join("%s %d" % kv for kv in counts.items())), "done")
        commit(ok)
    elif st == "pick_topic":
        if not p.get("proposals"):
            props, cost = _propose(p)

            def ok(q):
                q.update(proposals=props, cost=round(q.get("cost", 0) + cost, 4), heals={})
                if q.get("auto"):
                    _log(q, "Fully automatic: taking #1 — “%s”." % props[0]["topic"])
                    _choose(q, props[0])
                else:
                    q["state"] = "waiting"
                    _log(q, "3 topics ready: %s. Pick one (or give me your own)." %
                         " · ".join("%d. %s" % (i + 1, x["topic"]) for i, x in enumerate(props)), "need")
            commit(ok)
        elif p.get("auto"):
            commit(lambda q: _choose(q, q["proposals"][0]))
        else:
            commit(lambda q: q.update(state="waiting"))
    elif st == "research":
        commit(lambda q: _log(q, "Research job started (Claude Code + web search) — this usually takes 5-15 minutes."
                              if RESEARCH_ENGINE(q) == "claude" else
                              "Research started on the free desk: the lab searches + opens the sources, the research engine "
                              "writes research.md. ~10-25 min."))
        cost, n_src, size = _research(p)

        def ok(q):
            q.update(stage="script", cost=round(q.get("cost", 0) + cost, 4), heals={}, research={"sources": n_src, "chars": size})
            _log(q, "Research done: research.md, %d sources, %d chars. Writing the script next." % (n_src, size), "done")
        commit(ok)
    elif st == "script":
        commit(lambda q: _log(q, "Script job started — turning research.md into episode.json."))
        cost, stats, retries = _script(p)

        def ok(q):
            q.update(cost=round(q.get("cost", 0) + cost, 4), validation={"ok": True, "retries": retries, **stats}, heals={})
            q.pop("rewrite_note", None) if q.get("auto") else None
            q["stage"] = "approve_script"
            msg = ("Script ready: %d beats, %d chapters, ~%d:%02d, %d assets (passed validation%s)."
                   % (stats["beats"], stats["chapters"], stats["est_secs"] // 60, stats["est_secs"] % 60, stats["assets"],
                      " after %d fix%s" % (retries, "es" if retries > 1 else "") if retries else ""))
            if q.get("auto"):
                _log(q, msg + " Fully automatic: approving it myself.", "done")
                _approved(q)
            else:
                q["state"] = "waiting"
                _log(q, msg + " Approve it, or ask for a rewrite with a note.", "need")
        commit(ok)
    elif st == "approve_script":
        if p.get("auto"):
            commit(_approved)
        else:
            commit(lambda q: q.update(state="waiting"))
    elif st in STAGE_HANDLERS:
        STAGE_HANDLERS[st](p)
    else:
        commit(lambda q: (q.update(state="waiting"),
                          _log(q, "Stage '%s' isn't installed yet — the run is parked here." % st)))


# ── Flask wiring ───────────────────────────────────────────────────────────────────────────────────────────────────
def register(app, hk):
    """hk: uid, can_produce()->error|None, push(user, type, title, body, **kw), static(fn)."""
    from flask import request, jsonify, send_file
    setup(hk)

    def U():
        return hk["uid"]()

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    @app.route("/explained")
    def ex_page():
        return hk["static"]("explained.html")

    @app.route("/api/explained/runs")
    def ex_list():
        return jsonify({"runs": listing(U())})

    @app.route("/api/explained/feed")
    def ex_feed():
        try:
            since = int(request.args.get("since") or 0)
        except ValueError:
            since = 0
        return jsonify({"events": feed(U(), since), "now": int(time.time() * 1000)})

    @app.route("/api/explained/trends")
    def ex_trends():
        c, n = collect_trends(request.args.get("niche") or "")
        return jsonify({"candidates": c, "counts": n})

    @app.route("/api/explained/start", methods=["POST"])
    def ex_start():
        err = (hk.get("can_produce") or (lambda: None))()
        if err:
            return oops(err, 403)
        b = request.get_json(silent=True) or {}
        try:
            return jsonify(start(U(), b.get("niche"), b.get("topic"), bool(b.get("auto")), b.get("structure") or "auto", b.get("voice")))
        except Exception as e:
            return oops(e)

    @app.route("/api/explained/presets")
    def ex_presets():
        return jsonify({"presets": PR.public()})

    @app.route("/api/explained/<pid>")
    def ex_get(pid):
        p = load(U(), pid)
        return jsonify(public(p)) if p else oops("no such run", 404)

    @app.route("/api/explained/<pid>/file/<name>")
    def ex_file(pid, name):
        p = load(U(), pid)
        f = _folder(p) if p else None
        if not f or name not in ("research.md", "episode.json"):
            return oops("not found", 404)
        path = os.path.join(f, name)
        if not os.path.isfile(path):
            return oops("not written yet", 404)
        return send_file(path, mimetype="application/json" if name.endswith(".json") else "text/markdown; charset=utf-8",
                         max_age=0)

    @app.route("/api/explained/<pid>/render/<name>")
    def ex_render(pid, name):
        p = load(U(), pid)
        slug = ((p or {}).get("topic") or {}).get("slug")
        if not slug or not re.match(r"^(main|short[1-3])\.mp4$|^thumb\.jpg$", name):
            return oops("not found", 404)
        path = os.path.join(REMOTION, "out", slug, name)
        if not os.path.isfile(path):
            return oops("not rendered yet", 404)
        return send_file(path, mimetype="image/jpeg" if name.endswith(".jpg") else "video/mp4", conditional=True, max_age=0)

    @app.route("/api/explained/<pid>/scene/<name>")
    def ex_scene(pid, name):
        p = load(U(), pid)
        slug = ((p or {}).get("topic") or {}).get("slug")
        if not slug or not re.match(r"^[\w-]+\.(jpg|mp4)$", name):
            return oops("not found", 404)
        path = os.path.join(REMOTION, "out", slug, "scenes", name)
        if not os.path.isfile(path):
            return oops("no preview yet", 404)
        return send_file(path, mimetype="video/mp4" if name.endswith(".mp4") else "image/jpeg", conditional=True, max_age=0)

    @app.route("/api/explained/<pid>/asset/<path:name>")
    def ex_asset(pid, name):
        p = load(U(), pid)
        slug = ((p or {}).get("topic") or {}).get("slug")
        if not slug or ".." in name or not re.match(r"^(ref/)?[\w.-]+\.(png|jpe?g|webp|gif|mp4|mp3|wav)$", name):
            return oops("not found", 404)
        path = os.path.join(REMOTION, "public", "episodes", slug, name)
        if not os.path.isfile(path):
            return oops("not made yet", 404)
        if request.args.get("thumb") and re.search(r"\.(png|jpe?g|webp)$", name):     # progress tiles: small cached jpg
            th = os.path.join(REMOTION, "out", slug, "thumbs", name.replace("/", "_") + ".jpg")
            if not os.path.isfile(th) or os.path.getmtime(th) < os.path.getmtime(path):
                try:
                    from PIL import Image
                    os.makedirs(os.path.dirname(th), exist_ok=True)
                    im = Image.open(path).convert("RGB")
                    im.thumbnail((360, 360))
                    im.save(th, "JPEG", quality=78)
                except Exception:
                    return send_file(path, conditional=True, max_age=0)
            return send_file(th, mimetype="image/jpeg", conditional=True, max_age=3600)
        return send_file(path, conditional=True, max_age=0)

    @app.route("/api/explained/<pid>/<action>", methods=["POST"])
    def ex_control(pid, action):
        try:
            return jsonify(control(U(), pid, action, request.get_json(silent=True) or {}))
        except Exception as e:
            return oops(e)
