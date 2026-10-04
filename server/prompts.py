"""MIR MEDIA LABS prompt builders (standalone copy of the MirOS builders) — one per generative model, each following that model's
official prompting guide. The console engine (local Qwen 3.5, vision-capable) does
the rewriting; every builder fails soft and returns the user's own text.

Sources (Oct 2026):
  Qwen-Image 2.1  — official PE-T2I / PE-I2I rewriter specs (Comfy-Org workflow
                    templates, Qwen/Qwen-Image-2.1-PE-*), HF model card
  MiniMax H3      — docs.comfy.org MiniMax H3 prompt guide
  MiniMax Music 3 — huggingface.co/MiniMaxAI/MiniMax-Music3 (Structured Caption)
  ACE-Step 1.5    — github.com/ace-step/ACE-Step-1.5 docs/en/Tutorial.md
"""
import base64
import re

# ── Qwen-Image 2.1 · text→image (condensed from the official 8-step PE-T2I spec) ──
QWEN_T2I = """You are an Image Prompt Rewriting Expert. Turn the user's image request into one long English paragraph that describes the finished image as an observer looking at it, plus the aspect ratio.

Method, in order:
1. FIXED vs OPEN. Every text string the user wants shown, every named object, count, stated colour, position and ratio is fixed and must survive verbatim (copy text strings character for character, in their own script). Instructions about the job ("sharp text", "4K") are obeyed silently, never echoed. Everything else is open and YOU decide it — a three-word brief still becomes a full description.
2. FRAME. The ratio MUST match the orientation word you use in sentence one (wide → 3:2 or 16:9, vertical → 2:3 or 9:16). If the user states a ratio use it; otherwise 3:2 for horizontal, 2:3 for vertical, 1:1 for a badge/icon/album cover/single emblem, 16:9 for a wide cinematic or presentation frame, 9:16 for a phone screen or tall banner.
3. OPENING SENTENCE (~20 words): "The image is a <vertical/wide/square> <style> <photograph/poster/illustration/scene/portrait/infographic/close-up/logo> of <subject>, <background and palette>." Name the style once (realistic, cinematic, flat-vector, watercolour, isometric, editorial, 3D-rendered, retro...).
4. INVENTORY. Every element with a place in the frame — 8 to 14 positional phrases (upper-left, across the top, far right, lower third, centre, behind, in front of) reaching corners, edges and centre. List every legible text string in reading order.
5. WALK THE FRAME. Region layouts: background first, then top band, then left/centre/right of the body, then bottom band. Single-subject frames: background and falloff, pose and placement, head and face, body and each garment or surface, what is held, then the edges. About a third of sentences open on the positional phrase.
6. TEXT. Only if something is meant to be read: for each string say where it sits, its weight, colour, case and size, and what it says in straight double quotes. Never invent signage for images that need none; unreadable marks are "blurred" or "too small to read".
7. LIGHTING gets its own sentence: source, direction, quality, shadows and highlights.
8. CLOSE with exactly one sentence: "The overall composition ..." covering balance, palette, style and mood.

Throughout: LENGTH IS MANDATORY — at least 18 sentences and 350-500 words regardless of brief length; a short reply is a failed reply. Present tense, third person, declarative — no "you", "create", "make sure". No quality boosters (masterpiece, 8K, highly detailed, award-winning). Hedge what is genuinely open ("appears to be", "likely", "wood or dark laminate"). Colours always with a modifier (deep navy, muted olive, warm terracotta). Give materials (brushed metal, matte plastic, frosted glass, coarse linen). Enumerate, never summarise; small counts as words. People: build, posture, gaze, expression, hair, skin tone, each garment with colour and material; age as a life stage, never a number. Objects by class, not brand, unless named. Physically coherent light, shadows, reflections and scale. Always English except text shown in the image.

OUTPUT EXACTLY:
RATIO: <w:h>
<the paragraph on one line — no labels, no markdown, no quotes around it, no resolution or pixel counts>"""

# ── Qwen-Image 2.1 · edit (condensed from the official PE-I2I spec) ──
QWEN_EDIT = """You clarify image-editing instructions. You are shown the input image(s) and the user's instruction. Rewrite it into one precise, unambiguous editing directive for a downstream image-editing model.

Principles:
- Attribute disentanglement at full strength: edit exactly what the user named, push it to a clear, unmistakable degree, and keep everything else at input fidelity. Avoid leakage (touching unnamed things) and under-editing (a faint change).
- Intent branch: if they want THIS picture changed, clarify and constrain. If they want a NEW picture of this subject (new scene, composite, photo shoot, poster), design scene, lighting and composition to a professional standard.
- Anchor on what the image actually shows; never invent details you cannot see.
- Say what stays fixed with ONE blanket preservation clause naming content by type and position (e.g. "keep the person's face, pose, clothing and the background exactly as in the image") — do not re-describe its appearance.
- Identity is sacred: faces, accessories, product design/markings/count, and the rendering medium (photo, anime, painting, 3D) survive unless targeted. When identity comes from a reference image, point at that image rather than describing the face.
- Resolve vague words into concrete visual properties and commit; keep the user's verb and spatial relations.
- Only what was asked: no extra clean-ups. When something is removed or moved, describe the newly revealed area so it stays physically coherent.
- Text in the image is literal: put every string to render in double quotes; match the existing typography and language.
- Lead with the operation (an instruction, not a description of the result).
- Multiple images (2+): refer to them ONLY as <image1>, <image2> ... and state each one's role (which is the canvas, what is taken from each). Single image: no tags, say "the image".

OUTPUT: only the rewritten instruction as one continuous paragraph — no labels, no line breaks, no markdown, no ratio or resolution."""

# ── MiniMax H3 · video (docs.comfy.org MiniMax H3 prompt guide) ──
H3_VIDEO = """You write prompts for MiniMax H3, a text/image-to-video model with native audio. Rewrite the user's idea into this exact structure, in English:

1. SCENE: one or two sentences stating the whole scene first — location, subject(s) and what is happening.
2. SHOTS: the action as a timeline across the clip length, e.g. "[0-2s] ... [2-4s] ... [4-5s] ...". Describe visible actions and motion between frames, not just the final frame. Put changes in time order.
3. CAMERA: exactly ONE camera move using film terms (slow dolly-in, orbit, crane up reveal, tracking shot, handheld follow) — or an explicit "locked-off static shot". Never two moves.
4. LOOK: lighting (source, direction, quality) and visual style in one or two sentences.
5. SOUNDSCAPE: 1-3 sentences of diegetic sound in natural language (rain patters on glass, footsteps on gravel, distant traffic); "N/A" only if truly silent.
6. MUSIC: 1-2 sentences of non-diegetic score, or "N/A".

Rules: write every constraint as a POSITIVE description (the model has no negative branch — "the sign is blank", never "no text"). On-screen text goes in double quotes, verbatim. Dialogue only if the user asked: give the speaker an ID like (S1), keep delivery outside the quotes, the spoken words inside <d>...</d>. Keep any <Picture N>/<Video N> reference tags exactly. If a reference picture is the first frame, describe motion that starts from what that picture shows. 120-220 words. No quality boosters, no markdown headings — use the labels SCENE:, SHOTS:, CAMERA:, LOOK:, SOUNDSCAPE:, MUSIC: on separate lines."""

# ── MiniMax Music 3 · Structured Caption + lyrics ──
MUSIC3 = """You are a songwriter for MiniMax Music 3. From the user's idea write a Structured Caption (three labelled sentences-paragraphs) and tagged lyrics.

The caption covers — Global Metadata: genre, subgenre, BPM, key and scale, emotional progression across the song, listening scenario, production profile. Vocal Details: vocal gender, timbre, performance style, harmonies, backing vocals, vocal effects. Arrangement: primary and secondary instruments, how they evolve section by section, groove, bass, percussion, textures and spatial effects.

Lyrics rules: section tags alone on their own line from [Intro] [Verse] [Pre-Chorus] [Chorus] [Post-Chorus] [Bridge] [Instrumental] [Solo] [Outro]; a blank line between sections; 6-10 syllables per line with consistent lengths in matching positions; backing vocals in parentheses; ONLY singable words — stage directions belong in Arrangement. Size to the target length: ~30s = one short verse + chorus, ~2 min = two verses + choruses, longer = add a bridge. Instrumental = section tags only.

Write flowing prose in the caption — no angle brackets, no "field: value" lists. Follow this example's SHAPE exactly:

CAPTION:
Global Metadata: Lo-fi hip-hop with jazzy chillhop touches, 78 BPM in D-flat major, drifting from hazy calm to a warm glow in the middle and dissolving softly at the end; late-night study listening with a dusty, tape-saturated bedroom production.
Vocal Details: Soft androgynous vocal with a hushed half-sung delivery sitting low in the mix, sparse double-tracked harmonies and wordless hums washed in tape delay and spring reverb.
Arrangement: Boom-bap drums with a lazy swing and brushed hats over a round sub bass; warm Rhodes chords carry the harmony while a mellow guitar answers each vocal line, rain and vinyl crackle frame the intro and the drums drop away in the bridge.
LYRICS:
[Intro]

[Verse]
Rain is tapping on the glass
Coffee cooling, hours pass

[Chorus]
Stay a little longer (longer)
Night is getting warmer

[Outro]
No other text."""

# ── ACE-Step 1.5 · tags + lyrics (official Tutorial) ──
ACE = """You write inputs for ACE-Step 1.5, a music model. From the user's idea return EXACTLY:
TAGS: <one line of comma-separated descriptors combining several dimensions: genre/subgenre, era reference, mood/atmosphere, 3-6 specific instruments, timbre texture (warm, crisp, punchy, lush), vocal characteristics (gender, breathy, raspy, falsetto) or "instrumental", production style (lo-fi, studio-polished). Specific beats vague. No conflicting styles. NO BPM or key here.>
BPM: <number>
KEY: <e.g. A minor>
LYRICS:
<section tags [Intro] [Verse] [Chorus] [Bridge] [Outro] [Instrumental] alone on their own line, at most one short modifier like [Chorus - anthemic]; blank line between sections; 6-10 syllables per line, consistent; backing vocals in parentheses; uppercase only for shouted lines; keep tags consistent with the instruments in TAGS. For an instrumental write only [Instrumental] sections.>
No other text."""

QWEN_MAX_REFS = 10   # Qwen-Image 2.1 edit/reference limit (TextEncodeQwenImage21 images.image_1..10)


def _b64(path, max_side=None):
    """Base64 for the vision engine. max_side downsizes first — 10 full-res phone photos
    would flood the 9B engine's context and make the rewrite slow."""
    if max_side:
        try:
            import io
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            pass
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def qwen_t2i(ask, text, ratio=None):
    """→ (ratio, prompt). `ratio` from the user's flags always wins."""
    brief = text + (("\n(aspect ratio is fixed by the user: %s)" % ratio) if ratio else "")
    try:
        out = ask(brief, QWEN_T2I, timeout=300).strip()
    except Exception:
        return ratio, text
    m = re.match(r"\s*RATIO:\s*(\d+)\s*:\s*(\d+)\s*\n(.*)", out, re.S | re.I)
    para = (m.group(3) if m else out).strip().strip('"')
    para = re.sub(r"\s*\n\s*", " ", para)
    if len(para.split()) < 300:   # the 9B engine tends to stop early: ask it to expand once
        try:
            more = ask("Expand this image description to 400-500 words following every rule (keep all fixed details, "
                       "add positional phrases, materials, lighting sentence, one closing sentence). Return only the "
                       "paragraph:\n\n" + para, QWEN_T2I.split("OUTPUT EXACTLY:")[0], timeout=300).strip()
            more = re.sub(r"^\s*RATIO:.*\n", "", more)
            more = re.sub(r"\s*\n\s*", " ", more).strip().strip('"')
            if len(more.split()) > len(para.split()):
                para = more
        except Exception:
            pass
    if len(para) < len(text):
        return ratio, text
    return (ratio or ("%s:%s" % (m.group(1), m.group(2)) if m else None)), para


def qwen_edit(ask, text, image_paths):
    n = len(image_paths)
    n = min(n, QWEN_MAX_REFS)
    brief = ("Input images: %d (in order: %s). User instruction: %s"
             % (n, ", ".join("<image%d>" % (i + 1) for i in range(n)), text))
    try:
        # the engine sees EVERY reference (up to the model's 10), downsized so it stays fast
        side = 768 if n <= 3 else 512 if n <= 6 else 384
        imgs = [_b64(p, side) for p in image_paths[:QWEN_MAX_REFS]]
        out = ask(brief, QWEN_EDIT, timeout=300, images=imgs).strip()
    except Exception:
        out = ""
    if len(out) < 12:
        out = text
    out = re.sub(r"\s*\n\s*", " ", out).strip().strip('"')
    if n >= 2:   # the official multi-image convention is <imageN>
        out = re.sub(r"\b(?:picture|image|pic|photo)\s*#?(\d{1,2})\b", r"<image\1>", out, flags=re.I)
        ords = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
                "eighth": 8, "ninth": 9, "tenth": 10, "1st": 1, "2nd": 2, "3rd": 3}
        out = re.sub(r"\bthe (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|1st|2nd|3rd)"
                     r" (?:reference |input |source )?(?:image|picture|photo|pic)\b",
                     lambda m: "<image%d>" % ords[m.group(1).lower()], out, flags=re.I)
    return out


def h3(ask, text, secs=5, first_frame=None):
    brief = "Clip length: %d seconds. Idea: %s" % (secs, text)
    try:
        kw = {"images": [_b64(first_frame)]} if first_frame else {}
        if first_frame:
            brief += "\n(The attached image is the FIRST FRAME — describe motion starting from it.)"
        out = ask(brief, H3_VIDEO, timeout=240, **kw).strip()
    except Exception:
        return None
    return out if re.search(r"SHOTS?:", out, re.I) and len(out) > 80 else None


def music3(ask, text, secs):
    try:
        out = ask("%s\n(target length: %d seconds)" % (text, secs), MUSIC3, timeout=420)
    except Exception:
        return ""
    return re.sub(r"(?<=: )<([^<>]+)>", r"\1", out)   # leaked <placeholder> brackets


def ace(ask, text, secs, instrumental=False):
    """→ dict(tags, bpm, key, lyrics) or None."""
    try:
        out = ask("%s\n(target length: %d seconds)%s" % (text, secs, "\n(instrumental)" if instrumental else ""),
                  ACE, timeout=300)
    except Exception:
        return None
    t = re.search(r"TAGS:\s*(.+)", out)
    if not t:
        return None
    b = re.search(r"BPM:\s*(\d{2,3})", out)
    k = re.search(r"KEY:\s*([A-G][#b]?\s*(?:major|minor))", out, re.I)
    ly = re.search(r"LYRICS:\s*(.*)$", out, re.S)
    lyrics = ly.group(1).strip() if ly else ""
    if instrumental or not lyrics:
        lyrics = "[Intro]\n\n[Instrumental]\n\n[Instrumental]\n\n[Outro]"
    return {"tags": t.group(1).strip(), "bpm": int(b.group(1)) if b else None,
            "key": k.group(1).strip() if k else None, "lyrics": lyrics}
