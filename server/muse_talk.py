"""MUSE talk — the built-in voice brain (Oct 18 2026).

Before, every spoken turn on such a PC became a MirAI chat job (/api/generate model auto): a chat bubble per sentence and
a full Director pass before she answered. Now a turn is a short spoken conversation:
  heard text -> quick intent routes (open a tab, status, cancel, news, web facts, make something, hand MirAI a long task)
             -> otherwise the local brain answers in one to three spoken sentences, with its own short memory.
Only real work (a render, a long writing task) still goes to the chat as a job.
"""
import html
import re
import threading
import time
from urllib.parse import quote

import requests

import core

PERSONA = """You are MUSE, the voice and creative director of MIR MEDIA LABS, a studio on the person's own PC that makes \
pictures, characters, video clips, music and songs. You are talking out loud, in real time, with the person using it.

How you sound: warm, quick, a little playful, full of creative ideas, confident, never robotic. This is a spoken \
conversation, not a document. Keep turns short, one to three sentences, unless they ask you to explain or tell a story. \
Use contractions and react to what they said. Answer what they asked and stop; don't pitch projects they didn't ask \
about. Only sometimes end with a short follow-up question, when it really helps. To make something they just say \
"make a picture of..." (or video, song, music, character) and the studio starts it.

Hard rules: never output markdown, lists, headings, code, file paths, links or emoji; everything you write is read aloud. \
Never invent facts about renders, the library, news or anything you did. You only know the live lab facts below, any web \
results given to you, and this conversation. When a render is started, the studio tells you; never claim one yourself. \
You know nothing about the person's money, email or other apps."""

_MEM = {}                    # uid -> {"t": last turn time, "h": [{"role","content"}]}
_LOCK = threading.Lock()
IDLE_S = 1800                # a conversation idle this long starts fresh
KEEP = 16                    # messages kept (8 exchanges)
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

_LEAD = r"^\W*(?:(?:hey|ok(?:ay)?|so|um+|uh+|muse|please|can you|could you|would you|will you|i(?:'d| would) like you to)\W+)*"
_MAKE = re.compile(_LEAD + r"(?:i (?:want|wanna|need) (?:you )?(?:to )?|let'?s |go |)"
                   r"(create|make|generate|render|draw|paint|design|imagine|compose|produce|animate|film|shoot|sing)\b", re.I)
_MEDIA = re.compile(r"\b(picture|image|photo|portrait|poster|logo|drawing|painting|art|character|video|clip|scene|shot|"
                    r"animation|film|movie|song|music|track|beat|tune|melody|soundtrack|jingle|it|one|that|this|another|"
                    r"version|again)\b", re.I)
# create requests that don't START with the verb ("so for the intro, can you make a video…", "I want a picture of…",
# "can I get a song about…") — before, these fell to the talker, which only SAID it sent them to the lab (Oct 18 fix)
_VERB_ANY = re.compile(r"\b(create|make|generate|render|draw|paint|design|compose|produce|animate|film)\b", re.I)
_WANT = re.compile(r"\b(i (?:want|need|wanna)|i'?d (?:like|love)|i would (?:like|love)|give me|show me|get me|"
                   r"can (?:i|we|you) (?:get|have|see|do)|let'?s (?:do|get|see|try|have)|how about|"
                   r"(?:i'?m|i am) (?:thinking|looking for))\b", re.I)
_NOUN = re.compile(r"\b(picture|image|photo|portrait|poster|logo|drawing|painting|artwork|character|video|clip|scene|"
                   r"animation|movie|song|music|track|beat|melody|soundtrack|jingle|wallpaper|thumbnail|cover)s?\b", re.I)
_HOWTO = re.compile(r"^\W*(?:how|why|what|which|when|where|who|is|are|does|do you know|tell me|explain)\b", re.I)
_AFFIRM = re.compile(r"^\W*(yes|yeah|yep|yup|sure|ok(?:ay)?|go ahead|go for it|do it|please do|let'?s do it|make it|"
                     r"start it|sounds good|perfect)\b", re.I)
_CLAIMS = re.compile(r"\b(sending|sent|passing|starting|started|creating|generating|rendering|making|queu(?:e|ed|ing)|"
                     r"kick(?:ing|ed) off|firing up|working on)\b.{0,60}\b(it|that|this|request|render|picture|image|video|"
                     r"song|track|music|media lab|lab|studio)\b|\b(on it|i'?ll (?:create|make|render|generate|start))\b", re.I)


def _wants_make(said, prev_a):
    """-> the prompt to render, or None."""
    if _MAKE.search(said) and _MEDIA.search(said):
        return said
    if _NOUN.search(said) and not _HOWTO.match(said) and (_VERB_ANY.search(said) or _WANT.search(said)):
        return said
    if _AFFIRM.match(said) and prev_a and _NOUN.search(prev_a) and (prev_a.rstrip().endswith("?") or _CLAIMS.search(prev_a)):
        return prev_a                                     # "yes" to her offer: render what she described
    return None


_LONG = re.compile(r"\b(ask mirai|tell mirai|have mirai|mirai,|write (?:me )?(?:a |an |the )?(?:full )?(?:script|screenplay|"
                   r"lyrics|outline|treatment|story plan|episode plan|series plan|plan))\b", re.I)
_TAB = re.compile(r"^\W*(?:ok(?:ay)?\W+)?(?:open|show(?: me)?|go to|take me to|switch to)\s+(?:the\s+|my\s+)?(chat|library|"
                  r"projects|productions?|editor|video editor|series studio|series|motion studio|motion|node flow|flow|"
                  r"downloader|social)\b", re.I)
_TABW = {"chat": "create", "video editor": "editor", "series studio": "series", "motion studio": "motion",
         "node flow": "flow", "production": "projects", "productions": "projects"}
_STATUS = re.compile(r"\b(what are you (?:working on|doing|making)|status|is it (?:done|ready|finished)|done yet|how(?:'s| is) "
                     r"(?:it|the render) (?:going|coming)|progress|what'?s rendering|anything running)\b", re.I)
_CANCEL = re.compile(r"^\W*(?:please\W+)?(?:cancel|stop|abort|kill)\s+(?:the\s+|that\s+|my\s+|this\s+)?"
                     r"(render|job|video|picture|image|song|it|that)\b", re.I)
_NEWS = re.compile(r"\b(news|headlines?)\b", re.I)
_NEWS_TOPIC = re.compile(r"\b(?:news|headlines?)\s+(?:about|on|from|in|for)\s+(.+?)[?.!]*$", re.I)
_FACT = re.compile(r"\b(weather|forecast|temperature|raining|snowing|score|who won|stock price|price of|how much (?:is|does)|"
                   r"what time is it in|look (?:it )?up|search (?:for|the web)|google|release date|when (?:is|does|did) "
                   r"(?:the )?\w+ (?:come out|release|start|open)|today|tonight|this week|latest|right now|currently)\b", re.I)
_RESET = re.compile(r"\b(start over|new conversation|forget (?:everything|that)|clear (?:the )?(?:chat|conversation))\b", re.I)


def _mem(user):
    with _LOCK:
        m = _MEM.get(user)
        if not m or time.time() - m["t"] > IDLE_S:
            m = _MEM[user] = {"t": time.time(), "h": []}
        return m


def _remember(user, said, reply):
    m = _mem(user)
    with _LOCK:
        m["h"] += [{"role": "user", "content": said}, {"role": "assistant", "content": reply}]
        m["h"] = m["h"][-KEEP:]
        m["t"] = time.time()


def _strip(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


def _news(topic):
    url = ("https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en" % quote(topic)) if topic else \
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    x = requests.get(url, headers=_UA, timeout=10).text
    items = [_strip((re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1])
             for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:6]]
    items = [re.sub(r"\s+-\s+[^-]{2,40}$", "", t) for t in items if t]       # drop the " - Source" tail
    return "Latest headlines%s:\n%s" % ((" about " + topic) if topic else "", "\n".join(items)) if items else ""


_WX = re.compile(r"\b(?:weather|forecast|temperature|raining|snowing)\b(?:.*?\b(?:in|for|at)\s+([a-z .,'-]+?))?\s*(?:today|tonight|"
                 r"tomorrow|right now|now|this week)?[?.!]*$", re.I)


def _weather(said):
    """Live weather (wttr.in, no key). No place named -> wttr's guess from this PC's IP."""
    m = _WX.search(said)
    place = (m.group(1) or "").strip(" ,.") if m else ""
    d = requests.get("https://wttr.in/%s?format=j1" % quote(place), headers=_UA, timeout=10).json()
    c = d["current_condition"][0]
    a = (d.get("nearest_area") or [{}])[0]
    where = ", ".join(x[0]["value"] for x in (a.get("areaName"), a.get("region")) if x) or place
    days = ["%s: %s, high %s F, low %s F" % (w["date"], (w["hourly"][4]["weatherDesc"][0]["value"]), w["maxtempF"], w["mintempF"])
            for w in d.get("weather", [])[:3]]
    return ("Live weather for %s: now %s F (feels %s F), %s, humidity %s%%, wind %s mph.\nForecast:\n%s"
            % (where, c["temp_F"], c["FeelsLikeF"], c["weatherDesc"][0]["value"], c["humidity"], c["windspeedMiles"],
               "\n".join(days)))


def _search(query):
    """Bing first (DuckDuckGo's html page now answers bots with a 202 challenge), DuckDuckGo as the fallback."""
    rows = []
    try:
        x = requests.get("https://www.bing.com/search?setlang=en&cc=US&q=" + quote(query), headers=_UA, timeout=10).text
        for blk in re.findall(r'<li class="b_algo"(.*?)</li>', x, re.S)[:5]:
            t = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
            p = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
            if t:
                rows.append("%s: %s" % (_strip(t.group(1)), _strip(p.group(1)) if p else ""))
    except Exception:
        pass
    if not rows:
        x = requests.get("https://html.duckduckgo.com/html/?q=" + quote(query), headers=_UA, timeout=10).text
        titles = [_strip(t) for t in re.findall(r'class="result__a"[^>]*>(.*?)</a>', x, re.S)]
        snips = [_strip(t) for t in re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', x, re.S)]
        rows = ["%s: %s" % (t, snips[i] if i < len(snips) else "") for i, t in enumerate(titles[:5]) if t]
    return ("Web results for \"%s\":\n" % query) + "\n".join(r[:300] for r in rows) if rows else ""


def _jobs_line(jobs):
    run = [j for j in jobs if j.get("status") in ("running", "queued") and j.get("model") != "llama"]
    if not run:
        last = next((j for j in jobs if j.get("status") == "done" and j.get("model") != "llama"), None)
        return "Nothing is rendering right now." + (" The last thing made was a %s." % _kind(last) if last else "")
    return "Rendering now: " + "; ".join("%s, %s" % (_kind(j), str(j.get("stage") or j.get("status"))[:60]) for j in run[:3])


def _kind(j):
    m = (j or {}).get("model") or ""
    return {"qimg": "picture", "h3": "video clip", "music3": "music track", "ace": "song"}.get(m, j.get("skill") or
                                                                                              j.get("pipeline") or "render")


def _voice_model():
    """The brain MUSE talks with: Settings' voice pick (pref voice_model) if installed, else MirAI's engine (already
    loaded, so no second model fights for VRAM)."""
    want = (core.prefs().get("voice_model") or "").strip()
    if want:
        try:
            tags = [m["name"] for m in requests.get(core.OLLAMA + "/api/tags", timeout=3).json().get("models", [])]
            if want in tags:
                return want
        except Exception:
            pass
    return core.engine_model()


def _chat(user, said, facts, name, extra=None):
    m = _mem(user)
    sys = PERSONA + ("\n\nThe person's name is %s; use it rarely." % name if name else "")
    msgs = [{"role": "system", "content": sys}] + list(m["h"])
    # the truth for THIS turn sits right before it (small brains follow the last thing they read)
    now = "Right now in the lab: " + facts + " This is the only truth about renders; you are not making anything " \
          "unless it is listed here. " + ("Tell it fully but keep it spoken and natural." if re.search(
              r"\b(story|explain|describe|tell me (?:about|more)|poem|lyrics|walk me through)\b", said, re.I) else
              "Reply in at most three short spoken sentences, and don't suggest projects.")
    msgs.append({"role": "system", "content": now + ("\n\n" + extra if extra else "")})
    msgs.append({"role": "user", "content": said})
    core.ensure_ollama(wait=30)
    model = _voice_model()
    body = {"model": model, "messages": msgs, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"num_predict": 260, "temperature": 0.8, "num_ctx": int(core.engine_window(model) or 8192)}}
    r = core.engine_post("/api/chat", body, timeout=120)
    r.raise_for_status()
    d = r.json().get("message") or {}
    out = (d.get("content") or "").strip()
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S)
    out = re.sub(r"[*#`_>|]+", "", out)                      # speech only: no markdown
    out = re.sub(r"https?://\S+", "", out).strip()
    return out or "Sorry, I lost my train of thought. Say that again?"


def turn(user, said, jobs, name=""):
    """One spoken turn -> {"say": what MUSE says, "do": optional action for the page}."""
    said = (said or "").strip()
    if not said:
        return {"say": ""}
    if _RESET.search(said):
        with _LOCK:
            _MEM.pop(user, None)
        return {"say": "Fresh start. What are we making?"}
    t = _TAB.match(said)
    if t:
        w = t.group(1).lower()
        tab = _TABW.get(w, w)
        out = {"say": "Here's the %s." % w.replace("projects", "projects page"), "do": "tab", "tab": tab}
        _remember(user, said, out["say"])
        return out
    if _CANCEL.match(said):
        run = [j for j in jobs if j.get("status") in ("running", "queued")]
        out = {"say": "Stopped it." if run else "There's nothing running to stop.", "do": "cancel" if run else None,
               "job": run[0]["id"] if run else None}
        _remember(user, said, out["say"])
        return out
    if _LONG.search(said):
        out = {"say": "Passing that to MirAI now. Her full answer will be in the chat.", "do": "mirai", "prompt": said}
        _remember(user, said, out["say"])
        return out
    hist = _mem(user)["h"]
    prev_a = next((x["content"] for x in reversed(hist) if x["role"] == "assistant"), "")
    prev_u = next((x["content"] for x in reversed(hist) if x["role"] == "user"), "")
    make = _wants_make(said, prev_a)
    if make:
        out = {"say": "On it. I'm starting that now and I'll tell you when it's ready.", "do": "make", "prompt": make}
        _remember(user, said, out["say"])
        return out
    facts = _jobs_line(jobs)
    extra = None
    try:
        if _NEWS.search(said):
            n = _NEWS_TOPIC.search(said)
            web = _news(n.group(1) if n else "")
            extra = (web + "\n\nTell the person the top few headlines in your own spoken words.") if web else \
                "The news didn't load. Say so briefly."
        elif re.search(r"\b(weather|forecast|temperature|raining|snowing)\b", said, re.I):
            extra = _weather(said) + "\n\nAnswer the weather question in one or two spoken sentences (round the numbers)."
        elif _FACT.search(said):
            web = _search(said)
            extra = (web + "\n\nAnswer from these results in one to three spoken sentences. If they don't answer it, "
                     "say so.") if web else "The web search returned nothing. Say you couldn't find it."
    except Exception:
        extra = "You couldn't reach the internet just now. Say so briefly."
    if _STATUS.search(said):
        extra = (extra or "") + "\nAnswer ONLY from the live lab facts above (they are the truth right now), briefly."
    reply = _chat(user, said, facts, name, extra)
    _remember(user, said, reply)
    # she SAID she's sending / making it but no route fired -> really start it (never a claim without a job)
    if not extra and _CLAIMS.search(reply) and (_NOUN.search(said) or _NOUN.search(prev_u) or _AFFIRM.match(said)):
        what = said if _NOUN.search(said) else (prev_a if _AFFIRM.match(said) and _NOUN.search(prev_a or "") else prev_u)
        return {"say": reply, "do": "make", "prompt": what}
    return {"say": reply}
