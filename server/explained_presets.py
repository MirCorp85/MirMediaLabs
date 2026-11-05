"""MIR EXPLAINED structure presets (Oct 24 2026, user: "videos are becoming repetitive, same structure").

Every episode used to copy ONE arc (cold open → brand → 6-9 chapters → midroll → recap → endcard) from the SCRIPT_PROMPT
and the Roadster example. A preset now owns the episode's STRUCTURE: the arc the writer follows ({structure} in
SCRIPT_PROMPT), the runtime window, and the validator checks that make the shape real (a countdown that isn't counted
down fails validation and goes back to the writer like any other problem). The example episode only lends voice,
JSON format and asset style. Only the generic engine's visual types are used — no Remotion changes.

"auto" (the default) picks the least-recently-used preset that fits the topic, so back-to-back episodes differ.
"""
import re

# shared by every preset — the permanent rules (outro rule: midroll ~40% + endcard with like/subscribe/MML app)
_BASE = """  - Every beat: id, ch, mode (studio|hud|card|photo|brand|end), v {{c: visual type}}, cap (on-screen caption, plain
    sentence), say (TTS text: numbers, units and symbols written out in words). Optional plate, pad (extra seconds).
  - Chapter 0 always has the cold open + one "brand" beat; every later chapter opens with a "chapter" beat. One
    "midroll" beat (like + subscribe) around 40%, and the episode always ends with an "endcard" beat.
  - Never more than 3 beats in a row of the same visual type."""

PRESETS = [
    {"id": "classic", "name": "Classic Deep Dive", "icon": "film",
     "tag": "The original: surprising fact, then a chapter-by-chapter tour of the whole subject.",
     "secs": (290, 500), "words": "750-1150", "beats": "30-55", "chapters": (6, 9),
     "arc": """  - 6-9 chapters. Chapter 0 = cold open with the single most surprising fact in the first 5 seconds, then the
    "brand" beat. Then a broad tour: what it is, how it came to be, how it works, the numbers, the competition, the
    catch, what's next. A "recap" before the "endcard".
  - Mix it: at least 1 timeline, 1 compare or spec, 2 bignum, 1 diagram, 1 formula or gbars (our own check,
    labelled OUR ESTIMATE where it is ours).""",
     "need": {}},

    {"id": "countdown", "name": "Countdown", "icon": "star",
     "tag": "Top 5 facts, counted down from #5 to the jaw-dropper at #1.",
     "secs": (290, 480), "words": "750-1100", "beats": "30-50", "chapters": (6, 8),
     "arc": """  - A COUNTDOWN of the 5 most surprising facts / reasons / features from research.md. Chapter 0 = cold open
    that TEASES #1 without revealing it ("number one changes everything") + the "brand" beat.
  - Chapters 1-5 are the items, counted DOWN: chapter titles MUST start with the rank — "#5 — …", "#4 — …", "#3 — …",
    "#2 — …", "#1 — …". Each item: its "chapter" beat, then 4-6 beats that prove it (at least one bignum, spec,
    gbars, compare or timeline per item), ending on one line of why it matters. Build: #1 is the biggest payoff.
  - The midroll sits right after #3. A final short chapter (optional) or the last beats: a "recap" whose items are
    the five, in countdown order, then the "endcard".""",
     "need": {"bignum": 2, "recap": 1},
     "check": "countdown"},

    {"id": "story", "name": "The Story Of", "icon": "clock",
     "tag": "A chronological documentary: start at the climax, flash back, walk the years to today.",
     "secs": (300, 500), "words": "780-1150", "beats": "30-55", "chapters": (6, 9),
     "arc": """  - A DOCUMENTARY told in time order. Chapter 0 = cold open dropped into the most dramatic present-day moment,
    ending on "How did we get here?" + the "brand" beat.
  - Chapters 1..n-1 walk forward through history: origins → turning points → setbacks → breakthrough → today.
    At least 3 chapter titles carry their year or date (e.g. "2014 — The first prototype"). Name real people,
    places and dates from research.md; show photos of the real thing.
  - Use a "timeline" early (the backstory, kind past) and another near the end (now + future/claim events).
  - Last chapter = "What happens next": the open questions and dated claims, then the "endcard".""",
     "need": {"timeline": 2},
     "check": "story"},

    {"id": "myth", "name": "Myth vs Fact", "icon": "check-circle",
     "tag": "The viral claims, each one tested against the evidence, with a verdict.",
     "secs": (290, 480), "words": "750-1100", "beats": "30-50", "chapters": (6, 8),
     "arc": """  - A FACT-CHECK. Chapter 0 = cold open with the most viral claim about the topic as the caption, then
    "So is it true?" + the "brand" beat.
  - Chapters 1-5 (4-6 of them) each test ONE claim people make about the topic. Chapter titles MUST start with
    "Myth:" (e.g. "Myth: It can fly in the rain"). Each myth: the claim as people say it → why people believe it →
    the evidence (bignum / spec / gbars / timeline from research.md) → the verdict as a "compare" beat
    {{left: "The claim", right: "The facts", rows: [[point, what people say, what's true]]}}. Verdicts can be
    TRUE, FALSE or HALF-TRUE — say which out loud.
  - Final chapter "The real story": a "recap" whose items are the verdicts, then the "endcard".""",
     "need": {"compare": 3},
     "check": "myth"},

    {"id": "showdown", "name": "Showdown", "icon": "bolt",
     "tag": "Head-to-head rounds against its biggest rival, scored, with a final verdict.",
     "secs": (290, 480), "words": "750-1100", "beats": "30-50", "chapters": (6, 8),
     "arc": """  - A HEAD-TO-HEAD. If the topic names two things, they are the contenders; if it names one, pit it against
    its closest rival or predecessor found in research.md (say who and why in the cold open).
  - Chapter 0 = cold open with the matchup and the stakes + the "brand" beat. Chapter 1 "Tale of the tape": one
    "spec" beat per contender.
  - Then 4-5 rounds. Chapter titles MUST start with "Round" (e.g. "Round 1: Price", "Round 2: Range"). Each round:
    the "chapter" beat, the evidence, and a "compare" beat {{left: contender A, right: contender B,
    rows: [[metric, A, B]]}}, ending with a line naming the round's winner.
  - Final chapter "The verdict": a "gbars" scoreboard (rounds won per contender) and the overall winner — and who
    should pick which — then the "endcard".""",
     "need": {"compare": 4, "spec": 2, "gbars": 1},
     "check": "showdown"},

    {"id": "howitworks", "name": "How It Works", "icon": "gear",
     "tag": "An engineering teardown: the problem, the big idea, inside every part, the catch.",
     "secs": (290, 480), "words": "750-1100", "beats": "30-50", "chapters": (6, 8),
     "arc": """  - A TEARDOWN of the mechanism. Chapter 0 = cold open with the thing that seems impossible + the "brand" beat.
  - Chapter order: "The problem" (what had to be solved) → "The big idea" (the core principle, with a "formula"
    beat) → 2-3 "Inside …" chapters, each built around a "diagram" beat with callouts on the real hardware /
    system, explained part by part → "By the numbers" (spec / gbars / bignum) → "The catch" (limits, costs, risks)
    → "What's next", then the "endcard".
  - At least 3 diagram beats in total. Explain like a great teacher: one idea per beat, cause → effect.""",
     "need": {"diagram": 3, "formula": 1},
     "check": None},

    {"id": "quick", "name": "Quick Hit", "icon": "forward",
     "tag": "3-4 fast minutes: only the essentials, punchy lines, no slow build.",
     "secs": (170, 270), "words": "420-650", "beats": "20-30", "chapters": (4, 5),
     "arc": """  - A FAST episode: 3-4 minutes, 420-650 spoken words, 20-30 beats, 4-5 chapters. Every caption 14 words or
    fewer; no wind-up, no filler, no repetition.
  - Chapter 0 = a one-line hook (the most surprising number, as a "bignum") + the "brand" beat. Then: "What it is"
    → "Why it matters" → "The numbers" → "The catch / what's next". A short "recap" (3 items), then the "endcard".
  - Keep the midroll beat, but make it a single short line.""",
     "need": {"bignum": 2},
     "check": None},

    {"id": "question", "name": "The Big Question", "icon": "search",
     "tag": "Opens on the burning questions, follows the clues, saves the answer for the end.",
     "secs": (290, 480), "words": "750-1100", "beats": "30-50", "chapters": (6, 8),
     "arc": """  - A MYSTERY built on curiosity. Chapter 0 = cold open with a "questions" beat (the 3 burning questions
    viewers have about the topic) + the "brand" beat.
  - Each following chapter chases one clue toward the big answer; chapter titles are questions (end with "?").
    End every chapter on a small cliffhanger line that leads into the next.
  - HOLD BACK the main answer until the final chapter ("The answer"), where it lands with a "bignum" or "compare",
    followed by a "recap" whose items answer the 3 opening questions, then the "endcard".""",
     "need": {"questions": 1, "recap": 1},
     "check": "question"},
]
BY_ID = {p["id"]: p for p in PRESETS}
DEFAULT = "classic"


def _mins(p):
    return "%d-%d min" % (round(p["secs"][0] / 60), round(p["secs"][1] / 60))


def get(pid):
    return BY_ID.get(str(pid or "").lower()) or BY_ID[DEFAULT]


def public():
    """For the page / tools: id, name, icon, tag, length."""
    return [{"id": p["id"], "name": p["name"], "icon": p["icon"], "tag": p["tag"],
             "length": _mins(p)} for p in PRESETS]


def fits(pid, topic):
    if pid == "showdown":       # a rival can always be found, but auto only picks it when the topic IS a matchup
        return bool(re.search(r"(?i)\bvs\.?\b|\bversus\b|\bor\b.+\?|\bcompared\b|\bagainst\b", topic or ""))
    return True


def pick_auto(topic, recent):
    """Least-recently-used preset that fits. recent: preset ids of earlier runs, newest first."""
    pool = [p["id"] for p in PRESETS if fits(p["id"], topic)]
    if fits("showdown", topic):
        return "showdown"
    last = {pid: i for i, pid in reversed(list(enumerate(recent)))}     # index of newest use
    return max(pool, key=lambda pid: (last.get(pid, 10 ** 6), -pool.index(pid)))


def structure(pid):
    """The {structure} block for SCRIPT_PROMPT."""
    p = get(pid)
    return ("STRUCTURE — \"%s\" (%s):\n  - %s of narration: ~%s spoken words over %s beats, %d-%d chapters.\n%s\n%s"
            % (p["name"], p["tag"], _mins(p).replace("min", "minutes"), p["words"],
               p["beats"], p["chapters"][0], p["chapters"][1], p["arc"], _BASE))


def check(ep, pid):
    """Preset-specific validation → list of errors (the writer gets them back like any schema problem)."""
    p = get(pid)
    beats, chs = ep.get("beats") or [], ep.get("chapters") or []
    errs, kinds = [], [((b.get("v") or {}).get("c")) for b in beats]
    lo, hi = p["chapters"]
    if not lo <= len(chs) <= hi:
        errs.append("%s structure needs %d-%d chapters (has %d)" % (p["name"], lo, hi, len(chs)))
    for c, n in p["need"].items():
        if kinds.count(c) < n:
            errs.append("%s structure needs at least %d '%s' beat(s) (has %d)" % (p["name"], n, c, kinds.count(c)))
    titles = [str(c.get("title") or "") for c in chs]
    k = p.get("check")
    if k == "countdown":
        ranks = [int(m.group(1)) for t in titles for m in [re.match(r"\s*#\s*(\d+)", t)] if m]
        if len(ranks) < 5 or ranks[:5] != sorted(ranks[:5], reverse=True) or ranks[4] != 1:
            errs.append("Countdown: chapter titles must count down '#5 — …' to '#1 — …' in order (found ranks %s)" % ranks)
    elif k == "story":
        if sum(1 for t in titles if re.search(r"\b(1[5-9]|20)\d\d\b", t)) < 3:
            errs.append("The Story Of: at least 3 chapter titles must carry their year (e.g. '2014 — The first prototype')")
    elif k == "myth":
        if sum(1 for t in titles if re.match(r"\s*myth\b", t, re.I)) < 4:
            errs.append("Myth vs Fact: at least 4 chapter titles must start with 'Myth:'")
    elif k == "showdown":
        if sum(1 for t in titles if re.match(r"\s*round\b", t, re.I)) < 4:
            errs.append("Showdown: at least 4 chapter titles must start with 'Round'")
    elif k == "question":
        if "questions" not in kinds[:5]:
            errs.append("The Big Question: the cold open (first 5 beats) must include the 'questions' beat")
        if sum(1 for t in titles[1:-1] if t.strip().endswith("?")) < 3:
            errs.append("The Big Question: the clue chapters' titles must be questions ending with '?'")
    return errs
