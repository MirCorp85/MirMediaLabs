"""MIR EXPLAINED research desk on the free engines.

The lab does the legwork itself (search, open and read the sources, collect real photo candidates) and the
model only reads + writes research.md / episode.json. Engine order: your own optional research engine
(Settings → AI → Research engine: any OpenAI-compatible URL + key you run, e.g. a Kaggle notebook), then the
cloud brain if one is on, then the local engine. Nothing is bundled and no key ships with the app.
"""
import html as _html
import json
import re
import time
import urllib.parse

import requests

try:
    import core
except ImportError:
    import core

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36 MIR-MEDIA-LABS-Research/1.0"}
MAX_PAGES = 14
PAGE_CHARS = 14000          # per source; ~14 pages ≈ 50K tokens — fits a 128K+ context
LOCAL_PAGE_CHARS = 5000     # local fallback runs at a smaller context
BOOT_WAIT = 55 * 60         # (unused: the research engine is yours and already running)
SKIP_HOSTS = ("youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com",
              "reddit.com", "pinterest.", "linkedin.com", "duckduckgo.com", "bing.com", "google.")


# ── 1. gather ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _get(url, timeout=15, **kw):
    return requests.get(url, headers=UA, timeout=timeout, **kw)


def _gnews_decode(link):
    """news.google.com/rss/articles/<id> → the outlet's real URL (Google's own batchexecute decoder)."""
    aid = link.split("/articles/")[1].split("?")[0]
    pg = _get("https://news.google.com/rss/articles/" + aid).text
    sg, ts = re.search(r'data-n-a-sg="([^"]+)"', pg), re.search(r'data-n-a-ts="([^"]+)"', pg)
    if not (sg and ts):
        return None
    req = [[["Fbv4je", '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                       '"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]' % (aid, ts.group(1), sg.group(1)), None, "generic"]]]
    r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=15,
                      headers=dict(UA, **{"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}),
                      data="f.req=" + urllib.parse.quote(json.dumps(req)))
    return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]


def _gnews(q, n, hits, need):
    """Google News RSS search → decoded article URLs whose headline matches the topic."""
    out = []
    try:
        r = _get("https://news.google.com/rss/search", params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        for title, link in re.findall(r"(?s)<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", r.text):
            if hits(title) < need:
                continue
            try:
                u = _gnews_decode(link)
            except Exception:
                u = None
            if u and u.startswith("http") and not any(h in u for h in SKIP_HOSTS) and u not in out:
                out.append(u)
            if len(out) >= n:
                break
    except Exception:
        pass
    return out


def _wiki_refs(title, hits, n=12):
    """External sources cited by the Wikipedia article — ranked by how much of the topic their citation text names."""
    try:
        d = _get("https://en.wikipedia.org/w/api.php", params={"action": "parse", "page": title, "prop": "text",
                                                               "format": "json", "redirects": 1}).json()
        h = ((d.get("parse") or {}).get("text") or {}).get("*") or ""
        cands = []
        for href, txt in re.findall(r'(?s)<a rel="nofollow" class="external text" href="([^"]+)">(.*?)</a>', h):
            u = _html.unescape(href)
            if "archive.org" in u or any(s in u for s in SKIP_HOSTS) or u.lower().endswith(".pdf"):
                continue
            score = hits(re.sub(r"<[^>]+>", "", txt))
            cands.append((score, u))
        cands.sort(key=lambda x: -x[0])
        return list(dict.fromkeys(u for s, u in cands if s > 0))[:n]
    except Exception:
        return []


def _bing(q, n=8):
    """Bing web results (DuckDuckGo answers bots with a challenge page). /ck/a redirect links carry the real URL
    base64url-encoded in u=a1…"""
    import base64
    try:
        r = _get("https://www.bing.com/search", params={"q": q, "setlang": "en", "cc": "US"})
        out = []
        for blk in re.findall(r'(?s)<li class="b_algo.*?</h2>', r.text):
            m = re.search(r'<a[^>]+href="([^"]+)"', blk)
            if not m:
                continue
            u = _html.unescape(m.group(1))
            if "bing.com/ck/a" in u:
                k = re.search(r"[?&]u=a1([^&]+)", u)
                if not k:
                    continue
                try:
                    u = base64.urlsafe_b64decode(k.group(1) + "=" * (-len(k.group(1)) % 4)).decode("utf-8", "ignore")
                except Exception:
                    continue
            if u.startswith("http") and not any(h in u for h in SKIP_HOSTS) and u not in out:
                out.append(u)
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


def _ddg(q, n=8):
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q}, headers=UA, timeout=15)
        out = []
        for href in re.findall(r'class="result__a"[^>]*href="([^"]+)"', r.text):
            href = _html.unescape(href)
            m = re.search(r"[?&]uddg=([^&]+)", href)
            u = urllib.parse.unquote(m.group(1)) if m else href
            if u.startswith("http") and not any(h in u for h in SKIP_HOSTS) and u not in out:
                out.append(u)
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


def _wiki(q, n=2):
    out = []
    try:
        s = _get("https://en.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": q,
                                                                "srlimit": n, "format": "json"}).json()
        for hit in (s.get("query") or {}).get("search") or []:
            t = hit["title"]
            e = _get("https://en.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts", "explaintext": 1,
                                                                    "titles": t, "format": "json", "redirects": 1}).json()
            page = next(iter(((e.get("query") or {}).get("pages") or {}).values()), {})
            txt = page.get("extract") or ""
            if len(txt) > 800:
                out.append({"title": t + " — Wikipedia", "publisher": "Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_")), "text": txt})
    except Exception:
        pass
    return out


def _readable(raw):
    """HTML → (title, date, text, og_image) with stdlib regexes — good enough for article bodies."""
    title = _html.unescape((re.search(r"(?is)<title[^>]*>(.*?)</title>", raw) or [None, ""])[1]).strip()
    og = (re.search(r'(?i)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', raw) or [None, ""])[1]
    date = (re.search(r'(?i)<meta[^>]+(?:article:published_time|datePublished|pubdate)["\'][^>]+content=["\']([^"\']+)', raw)
            or re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw) or [None, ""])[1][:10]
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|aside|form)[^>]*>.*?</\1>", " ", raw)
    paras = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"(?s)<[^>]+>", " ", p))).strip()
             for p in re.findall(r"(?is)<(?:p|h[1-4]|li|td|th|figcaption)[^>]*>(.*?)</(?:p|h[1-4]|li|td|th|figcaption)>", body)]
    text = "\n".join(p for p in paras if len(p) > 40)
    return title, date, text, og


def _open(url):
    try:
        r = _get(url, timeout=20)
        if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html"):
            return None
        title, date, text, og = _readable(r.text[:3_000_000])
        if len(text) < 600:
            return None
        host = urllib.parse.urlparse(r.url).netloc.replace("www.", "")
        return {"title": title[:160] or host, "publisher": host, "url": r.url, "date": date, "text": text, "og": og}
    except Exception:
        return None


def _commons(q, n=20):
    out = []
    try:
        d = _get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": q + " filetype:bitmap",
            "gsrlimit": n, "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600, "format": "json"}).json()
        for pg in ((d.get("query") or {}).get("pages") or {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]
            if (ii.get("width") or 0) < 900:
                continue
            md = ii.get("extmetadata") or {}
            strip = lambda v: re.sub(r"<[^>]+>", "", _html.unescape(str((md.get(v) or {}).get("value") or ""))).strip()
            out.append({"url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl") or "",
                        "what": (strip("ImageDescription") or pg.get("title", ""))[:140],
                        "text": " ".join((pg.get("title", ""), strip("ObjectName"), strip("Categories"), strip("ImageDescription")[:300])),
                        "credit": (strip("Artist") or "Wikimedia Commons")[:80] + " / Wikimedia Commons"})
    except Exception:
        pass
    return out


def _nasa(q, n=15):
    out = []
    try:
        d = _get("https://images-api.nasa.gov/search", params={"q": q, "media_type": "image"}).json()
        for it in ((d.get("collection") or {}).get("items") or [])[:n]:
            dat = (it.get("data") or [{}])[0]
            nid = dat.get("nasa_id")
            if not nid:
                continue
            out.append({"url": "https://images-assets.nasa.gov/image/%s/%s~orig.jpg" % (nid, nid),
                        "page": "https://images.nasa.gov/details/" + nid, "what": (dat.get("title") or "")[:140],
                        "text": " ".join((dat.get("title") or "", " ".join(dat.get("keywords") or []), (dat.get("description") or "")[:300])),
                        "credit": "NASA" + (" / " + dat["photographer"] if dat.get("photographer") else "")})
    except Exception:
        pass
    return out


# subject words only — framing words ("became", "superpower", "rise", "fix") let gold / seafood / car pages through
_STOP = {"the", "and", "for", "with", "how", "why", "what", "explained", "from", "into", "its", "new", "vs", "became",
         "become", "becomes", "superpower", "rise", "rising", "really", "truth", "behind", "could", "cost", "inside",
         "story", "history", "record", "fix", "big", "real", "world", "global", "biggest", "secret", "next", "future",
         "makes", "made", "can", "will", "this", "that", "are", "was", "has", "have", "does", "did", "more", "most",
         "top", "best", "first", "ever", "actually", "explain", "about", "all", "you", "your", "our", "who"}


def _subject(topic):
    """→ (words, keys, rx, need, hits): the topic's subject words, one stem regex each, how many a page must hit, hits()."""
    words = lambda t: [w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2 and w not in _STOP]
    keys = list(dict.fromkeys(words(topic))) or [topic.lower()]
    rx = [re.compile(r"\b" + re.escape(re.sub(r"(ing|es|s|ed)$", "", k) if len(k) > 4 else k) + r"\w{0,4}\b") for k in keys]
    need = len(keys) if len(keys) <= 3 else -(-len(keys) * 2 // 3)   # every subject word (⅔ when the title is long)
    hits = lambda t: sum(1 for r in rx if r.search(t.lower()))
    return words, keys, rx, need, hits


def gather(topic, angle="", note="", log=lambda m: None):
    """→ (sources, photos). sources: [{n,title,publisher,url,date,text}] — only pages actually opened."""
    queries = [topic, "%s %s" % (topic, angle) if angle else topic + " explained",
               topic + " official", topic + " numbers specifications", topic + " latest news " + time.strftime("%Y")]
    if note:
        queries.insert(1, "%s %s" % (topic, note[:80]))
    words, keys, rx, need, hits = _subject(topic)
    relevant = lambda s: hits(s["title"] + " " + s["text"][:20000]) >= need
    named = {w.lower() for w in re.findall(r"\b\w*[A-Z]\w*\b", angle[1:])}   # Nvidia, GPUs (not the sentence start)
    extra = [w for w in dict.fromkeys(words(angle)) if w not in keys and w not in
             {"built", "industry", "actually", "mean", "means", "they", "their", "get", "far", "cut", "off", "tier", "own"}
             and (w in named or len(w) >= 5)][:4]                     # e.g. nvidia, chips, gpus, engines
    queries = list(dict.fromkeys([" ".join(keys)] + [" ".join(keys + [w]) for w in extra] + queries))
    wiki = [w for w in _wiki(" ".join(keys)) + _wiki(topic) if relevant(w) and hits(w["title"])]
    wiki = list({w["url"]: w for w in wiki}.values())[:3]
    # 1) newest coverage: Google News (real outlet URLs, decoded)  2) the sources the Wikipedia article itself cites
    # 3) web search only as a last resort (Bing/DDG serve bots generic or challenge pages)
    urls = []
    for q in queries[:6]:
        for u in _gnews(q, 8, hits, need):
            if u not in urls:
                urls.append(u)
    for w in wiki[:1]:
        for u in _wiki_refs(w["title"].replace(" — Wikipedia", ""), hits):
            if u not in urls:
                urls.append(u)
    if len(urls) < 6:
        for q in queries:
            urls += [u for u in (_bing(q) or _ddg(q)) if u not in urls]
    log("Searched the web (Google News + Wikipedia's cited sources): %d candidate pages. Opening the best ones…" % len(urls))
    sources, hosts = wiki, {}
    for u in urls:
        if len(sources) >= MAX_PAGES:
            break
        h = urllib.parse.urlparse(u).netloc
        if hosts.get(h, 0) >= 2:              # max 2 pages per outlet → independent sources
            continue
        s = _open(u)
        if s and relevant(s):
            hosts[h] = hosts.get(h, 0) + 1
            sources.append(s)
    for i, s in enumerate(sources, 1):
        s["n"] = i
    photos, seen = [], set()
    for ph in _nasa(topic) + _commons(topic) + [{"url": s["og"], "page": s["url"], "what": s["title"], "credit": s["publisher"]}
                                                for s in sources if s.get("og")]:
        u = ph.get("url") or ""
        if u.startswith("http") and u not in seen and re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
            seen.add(u)
            photos.append(ph)
    log("Opened %d sources (%s) and found %d real photo candidates."
        % (len(sources), ", ".join(sorted({s["publisher"] for s in sources}))[:200], len(photos)))
    return sources, photos[:40]


# Engines, best first: (1) an optional research engine YOU run — any OpenAI-compatible server (a Kaggle / Colab
# notebook behind a tunnel, LM Studio, vLLM, llama.cpp …) saved in Settings → AI → Research engine with your own URL
# and key; nothing is bundled and nothing is sent anywhere else; (2) the owner's cloud brain (cloud.py); (3) the local
# engine. EXPLAINED_LOCAL_OK=0 makes research/script pause instead of falling back to the local engine.
import os as _os
LOCAL_OK = _os.environ.get("EXPLAINED_LOCAL_OK", "1") == "1"
KAGGLE_STAGES = ("research", "script")


def _endpoint():
    p = core.prefs() or {}
    url = str(p.get("research_url") or "").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        return None
    return {"url": url, "key": str(p.get("research_key") or ""), "model": str(p.get("research_model") or "")}


def _hdr(ep):
    return {"Authorization": "Bearer " + ep["key"]} if ep.get("key") else {}


def _why_not():
    return "no research engine is set (Settings → AI → Research engine) and no cloud brain is on"


def ensure_kaggle(log, cancelled=lambda: False, what="the research"):
    """Your research engine answers → True. Not set / not answering → False (cloud brain or local engine writes)."""
    ep = _endpoint()
    if not ep:
        return False
    try:
        r = requests.get(ep["url"] + "/models", headers=_hdr(ep), timeout=20)
        if r.status_code < 400:
            if not ep["model"]:
                try:
                    ep["model"] = (r.json().get("data") or [{}])[0].get("id") or ""
                except Exception:
                    pass
            log("Your research engine is up — writing %s on it." % what)
            return True
        log("Your research engine answered %s — writing %s on the next brain instead." % (r.status_code, what))
    except Exception as e:
        log("Your research engine didn't answer (%s) — writing %s on the next brain instead." % (str(e)[:100], what))
    return False


def watchdog(runs, log_run=None):
    """Nothing to switch off: the research engine is yours and you run it."""
    return


def _chat_kaggle(system, user, max_tokens=12000):
    """Your OpenAI-compatible research engine. Streams the reply, so a tunnel that cuts silent requests (HTTP 524 after
    100 s on free Cloudflare tunnels) stays open for the whole write."""
    ep = _endpoint()
    if not ep:
        raise RuntimeError("no research engine set")
    model = ep["model"]
    if not model:
        try:
            model = (requests.get(ep["url"] + "/models", headers=_hdr(ep), timeout=20).json().get("data") or [{}])[0].get("id") or ""
        except Exception:
            model = ""
    with requests.post(ep["url"] + "/chat/completions", timeout=(30, 300), stream=True, headers=_hdr(ep),
                       json={"model": model or "default", "temperature": 0.3, "top_p": 0.9,
                             "max_tokens": max_tokens, "stream": True, "chat_template_kwargs": {"enable_thinking": False},
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}) as r:
        if r.status_code >= 400:
            raise RuntimeError("research engine %s: %s" % (r.status_code, re.sub(r"\s+", " ", r.text)[:200]))
        r.encoding = "utf-8"                 # SSE has no charset header → requests guessed Latin-1 ("â€”" for "—")
        out = []
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ch = (json.loads(data).get("choices") or [{}])[0]
            except Exception:
                continue
            out.append((ch.get("delta") or {}).get("content") or "")
    txt = "".join(out)
    if not txt.strip():
        raise RuntimeError("the research engine returned an empty answer")
    return re.sub(r"(?s)<think>.*?</think>", "", txt).strip(), "research engine"


def _chat_cloud(system, user):
    """The owner's cloud brain (Claude / GPT / GLM via cloud.py) → (text, label), or None when none is on."""
    try:
        import cloud
        import social
        b = social._brain()
        if not b:
            return None
        txt = cloud.ask(b, user, system, role="explained", timeout=20 * 60) or ""
        if not str(txt).strip():
            return None
        return re.sub(r"(?s)<think>.*?</think>", "", str(txt)).strip(), "cloud:" + str(b.get("model") or "")
    except Exception as e:
        print("[explained] cloud brain: %s — using the local engine" % str(e)[:160])
        return None


def _chat_local(system, user, max_tokens=9000):
    c = _chat_cloud(system, user)
    if c:
        return c
    m = core.engine_model() if hasattr(core, "engine_model") else core.DEFAULT_ENGINE
    r = requests.post(core.OLLAMA + "/api/chat", timeout=40 * 60, json={
        "model": m, "stream": False, "think": False,
        "options": {"num_ctx": 65536, "temperature": 0.3, "num_predict": max_tokens},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    if r.status_code >= 400:
        raise RuntimeError("local engine %s: %s" % (r.status_code, r.text[:300]))
    txt = (r.json().get("message") or {}).get("content") or ""
    return re.sub(r"(?s)<think>.*?</think>", "", txt).strip(), "local:" + m


def screen(sources, topic, angle, log):
    """The engine reads each source's title + opening and keeps only the ones genuinely about the episode topic
    (word matching let 'NBA China Games' and 'Del Monte game changer' into a China-gaming episode). Renumbers [n]."""
    lines = "\n".join("[%d] %s — %s\n    %s" % (s["n"], s["title"], s["publisher"], re.sub(r"\s+", " ", s["text"][:600]))
                      for s in sources)
    ask = ("Episode topic: %s\nAngle: %s\n\nFor each numbered web source below, decide if it is genuinely ABOUT this topic "
           "(useful facts for this episode) — not just sharing a word with it. Answer with ONLY a JSON array of the numbers "
           "to keep, e.g. [1,3,4].\n\n%s" % (topic, angle, lines))
    try:
        txt, _ = _chat_kaggle("You screen sources for a factual explainer.", ask, 300)
        keep = {int(x) for x in json.loads(re.search(r"\[[\d,\s]*\]", txt).group(0))}
    except Exception as e:
        log("Source screening didn't answer cleanly (%s) — keeping every source." % str(e)[:80])
        return sources
    kept = [s for s in sources if s["n"] in keep]
    dropped = [s["publisher"] + ": " + s["title"][:50] for s in sources if s["n"] not in keep]
    for i, s in enumerate(kept, 1):
        s["n"] = i
    log("The engine screened the sources: kept %d, dropped %d off-topic%s." % (len(kept), len(dropped),
        (" (" + "; ".join(dropped[:5]) + ")") if dropped else ""))
    return kept


# ── 3. write research.md ───────────────────────────────────────────────────────────────────────────────────────────
WRITE_RULES = """You are given numbered SOURCES that the lab already opened on the web, and PHOTO CANDIDATES (real image
URLs). Write research.md from them ONLY — exactly in the format below, English Markdown, and nothing else (no preamble,
no code fences). Cite with [n] using ONLY the source numbers given. Never invent a source, URL, number or quote; if a
claim isn't backed by a source, mark it CLAIMED or DISPUTED in the table or leave it out. For "## Sources" just write
the heading — the lab fills the list itself. For "## Reference photos" pick 12-20 DIFFERENT photos from the candidates
(another angle, detail, person, place or moment each), copying their URL exactly."""


def _clean_body(md):
    md = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", md.strip())
    i = md.find("#")
    return md[i:] if i > 0 else md


def write(p, folder, research_prompt, log, cancelled=lambda: False):
    """Full free research run → (engine_used, n_sources, n_chars). Writes <folder>/research.md."""
    t = p["topic"]
    sources, photos = gather(t["topic"], t.get("angle") or "", p.get("research_note") or "", log)
    if len(sources) < 3:
        raise RuntimeError("only %d web sources could be opened — the search may be rate-limited; retrying later" % len(sources))
    on_kaggle = ensure_kaggle(log, cancelled)
    if not on_kaggle and not LOCAL_OK:
        raise RuntimeError("research engine needed for the research (%s)" % _why_not())
    if on_kaggle:
        before = {x["url"] for x in sources}
        sources = screen(sources, t["topic"], t.get("angle") or "", log)
        gone = before - {x["url"] for x in sources}
        photos = [ph for ph in photos if ph.get("page") not in gone]     # no pictures from off-topic pages
        if len(sources) < 3:
            raise RuntimeError("only %d of the sources found are really about this topic — retrying the search later" % len(sources))
    cap = PAGE_CHARS if on_kaggle else LOCAL_PAGE_CHARS
    src_txt = "\n\n".join("=== SOURCE [%d] %s — %s — %s%s ===\n%s" % (s["n"], s["title"], s["publisher"], s["url"],
                                                                       (" — " + s["date"]) if s.get("date") else "", s["text"][:cap])
                          for s in sources)
    ph_txt = "\n".join("- %s | page: %s | %s | credit: %s" % (ph["url"], ph["page"], ph["what"], ph["credit"]) for ph in photos)
    fmt = research_prompt.split("Then use the Write tool to write the file research.md", 1)[-1]
    fmt = fmt.split("Rules:", 1)[0]
    head = research_prompt.split("Research it properly", 1)[0]
    user = "%s\n%s\nFORMAT%s\nSOURCES\n%s\n\nPHOTO CANDIDATES\n%s" % (head, WRITE_RULES, fmt, src_txt, ph_txt or "(none found)")
    log("Writing research.md on the %s engine from %d sources (~%dK tokens of reading)…"
        % ("your research engine" if on_kaggle else "the lab brain", len(sources), len(user) // 4000))
    try:
        md, used = (_chat_kaggle if on_kaggle else _chat_local)("You are the MIR EXPLAINED research desk.", user)
    except Exception as e:
        if not on_kaggle or not LOCAL_OK:       # a failed call is retried on the same engine (self-heal) unless the fallback is allowed
            raise RuntimeError("Research engine call failed while writing the research: %s" % str(e)[:200])
        log("Research engine call failed (%s) — retrying on the local engine." % str(e)[:120])
        user = user.replace(src_txt, "\n\n".join("=== SOURCE [%d] %s — %s — %s ===\n%s" % (s["n"], s["title"], s["publisher"],
                                                                                            s["url"], s["text"][:LOCAL_PAGE_CHARS]) for s in sources))
        md, used = _chat_local("You are the MIR EXPLAINED research desk.", user)
    md = _clean_body(md)
    # citations: drop [n] that don't exist; Sources = exactly the pages the lab opened
    md = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(sources) else "", md)
    srcs = "\n".join("[%d] %s — %s — %s — %s" % (s["n"], s["title"], s["publisher"], s["url"], s.get("date") or "n.d.")
                     for s in sources)
    md = re.split(r"(?im)^##\s*Sources\s*$", md)[0].rstrip() + "\n\n## Sources\n" + srcs + "\n"
    # photos: keep only rows whose URL is a real candidate; top up from candidates when the model picked too few
    real = {ph["url"]: ph for ph in photos}
    parts = re.split(r"(?im)^(##\s*Reference photos\s*)$", md, maxsplit=1)
    if len(parts) == 3:
        before, hdr, rest = parts
        sec, nxt = (re.split(r"(?m)^(?=##\s)", rest, maxsplit=1) + [""])[:2]
        picked = [u for u in re.findall(r"https?://[^\s|)]+", sec) if u in real]
        picked = list(dict.fromkeys(picked))
        for u in real:
            if len(picked) >= 12:
                break
            if u not in picked:
                picked.append(u)
        rows = "\n".join("| %d | %s | %s | %s | %s |" % (i, u, real[u]["page"], real[u]["what"].replace("|", "/"),
                                                         real[u]["credit"].replace("|", "/")) for i, u in enumerate(picked[:20], 1))
        md = before + hdr + "\n| # | Image URL (direct .jpg/.png/.webp) | Source page | What it shows | Credit |\n|---|---|---|---|---|\n" \
            + rows + "\n\n" + nxt
    import os
    with open(os.path.join(folder, "research.md"), "w", encoding="utf-8") as f:
        f.write(md)
    return used, len(sources), len(md)


# ── 4. script (episode.json) — the Roadster blueprint, on the free engine ─────────────────────────────────────────
SCRIPT_RULES = """You are working WITHOUT file tools: research.md, the approved example episode (the Tesla Roadster
episode — copy its voice, caption style, JSON format and asset style; its chapter STRUCTURE does NOT apply: follow the
STRUCTURE section of the instructions) and the JSON schema are pasted
below. Wherever the instructions say Read / Write a file, use the pasted copy instead, and answer with ONLY the complete
episode.json content — one JSON object, no comments, no code fences, no text before or after it."""


def _json_out(txt):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip())
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("the engine did not answer with a JSON object")
    return json.loads(txt[a:b + 1])


def write_script(p, folder, prompt, example, schema, log, cancelled=lambda: False, prev=None, errs=None):
    """One draft/fix of episode.json on the research engine (cloud / local fallback) → writes <folder>/episode.json, returns engine used.
    prev/errs: the last draft + the validator's complaints for a corrective retry (same loop Claude ran)."""
    import os
    on_kaggle = ensure_kaggle(log, cancelled, "the script")
    if not on_kaggle and not LOCAL_OK:
        raise RuntimeError("research engine needed for the script (%s)" % _why_not())
    rd = lambda path: open(path, encoding="utf-8").read()
    parts = [prompt, SCRIPT_RULES,
             "=== research.md ===\n" + rd(os.path.join(folder, "research.md")),
             "=== EXAMPLE episode.json (%s) ===\n%s" % (example, rd(example)),
             "=== SCHEMA (%s) ===\n%s" % (schema, rd(schema))]
    cur = os.path.join(folder, "episode.json")
    if prev is None and p.get("rewrite_note") and os.path.isfile(cur):
        prev = rd(cur)
    if prev:
        parts.append("=== CURRENT episode.json (revise this one) ===\n" + (prev if isinstance(prev, str) else json.dumps(prev)))
    if errs:
        parts.append("=== VALIDATION PROBLEMS TO FIX (fix every one, keep everything else) ===\n- " + "\n- ".join(errs[:30]))
    user = "\n\n".join(parts)
    chat = _chat_kaggle if on_kaggle else _chat_local
    try:
        txt, used = chat("You are the head writer of MIR EXPLAINED.", user, 16000)
    except Exception as e:
        if not on_kaggle or not LOCAL_OK:
            raise RuntimeError("Research engine call failed while writing the script: %s" % str(e)[:200])
        log("Research engine call failed (%s) — writing the script on the local engine." % str(e)[:120])
        txt, used = _chat_local("You are the head writer of MIR EXPLAINED.", user, 16000)
    try:
        ep = _json_out(txt)
    except Exception as e:
        with open(cur + ".raw.txt", "w", encoding="utf-8") as f:     # keep it for the corrective retry
            f.write(txt)
        raise ValueError("episode.json is not valid JSON: %s" % e)
    with open(cur, "w", encoding="utf-8") as f:
        json.dump(ep, f, ensure_ascii=False, indent=1)
    return used


# ── 5. more reference photos (free replacement for the Claude photo hunt) ──────────────────────────────────────────
def _looks_on_topic(ph, topic):
    """The local engine LOOKS at the photo: YES only when it shows the real subject (the flying-car hunt also matched the
    Harry Potter Ford Anglia, a Disney ride and AI art on words alone). Fails closed — no answer = not used."""
    try:
        import base64, io
        m = core.engine_model()
        if hasattr(core, "engine_sees") and not core.engine_sees(m):
            return False
        raw = _get(ph["url"], timeout=25).content
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im.thumbnail((640, 640))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
            raw = buf.getvalue()
        except Exception:
            pass
        ask = ("Video topic: %s\nPhoto caption: %s\n\nLook at the photo. Would it be correct to show it while narrating this "
               "topic — does it show the actual real-world subject (or its maker / place / technology)? Answer NO for: a movie "
               "prop or film car, theme-park ride, toy, festival or parade, a portrait of a random person, crowds, old book or "
               "document scans, AI-generated art, or a different kind of thing that just shares a word with the topic. "
               "Reply with only YES or NO." % (topic, ph.get("what", "")[:200]))
        r = requests.post(core.OLLAMA + "/api/chat", timeout=120, json={
            "model": m, "stream": False, "think": False, "options": {"temperature": 0, "num_predict": 4},
            "messages": [{"role": "user", "content": ask, "images": [base64.b64encode(raw).decode()]}]})
        return (r.json().get("message") or {}).get("content", "").strip().upper().startswith("YES")
    except Exception:
        return False


def more_photos(topic, have_urls, want, angles=()):
    """Extra real photos from NASA Images + Wikimedia Commons (topic + angle words) → photos_more.json rows.
    Oct 24: a photo must be ABOUT the topic — the flying-car episode got a 1917 museum, a gun club, festival-goers and a
    stranger's portrait because search hits were taken unchecked. Its own title/description/categories must name the
    subject as a PHRASE ("flying car", "heat shield" — word-bag matching let Chinese-GP F1 shots through on
    "China … flying lap … car"; reversed only via a real connector, so "flower car of flying dragon" fails) in its
    title / categories / first 300 chars of description + all but one other subject word; book scans / letters never."""
    seen, out = set(have_urls), []
    _, keys, rx, need, hits = _subject(topic)
    need = max(1, len(keys) - 1) if len(keys) > 2 else len(keys)
    stem = lambda k: re.escape(re.sub(r"(ing|es|s|ed)$", "", k) if len(k) > 4 else k) + r"\w{0,4}"
    if len(keys) >= 2:                                                # modifier + head noun: "flying car" / "cars that fly"
        a, b = stem(keys[-2]), stem(keys[-1])
        subj = re.compile(r"\b%s[\s_-]+%s\b|\b%s\W+(?:that|which|who|in|can|to)\W+(?:\w+\W+)?%s\b" % (a, b, b, a))
    else:
        subj = rx[0]
    junk = re.compile(r"(?i)internet archive book|manuscript|\bletter\b|identifier:|\bDPLA\b|page \d+|portrait of")
    about = lambda ph: subj.search(ph.get("text", "").lower()) and hits(ph.get("text", "")) >= need \
        and not junk.search(ph.get("text", "") + " " + ph.get("credit", ""))
    qs = [" ".join(keys), " ".join(keys[-2:])] + [topic] + [" ".join(keys[-2:]) + " " + a for a in angles if a][:4] \
        + [" ".join(keys[-2:]) + " prototype", " ".join(keys[-2:]) + " photo"]
    for q in dict.fromkeys(qs):
        for ph in _nasa(q, 20) + _commons(q, 25):
            u = ph.get("url") or ""
            if u in seen or not re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I) or not about(ph):
                continue
            seen.add(u)
            if not _looks_on_topic(ph, topic):
                continue
            out.append({"url": u, "source": ph["page"], "use": "more%02d.jpg — %s" % (len(out) + 1, ph["what"]),
                        "credit": ph["credit"]})
            if len(out) >= want:
                return out
    return out
