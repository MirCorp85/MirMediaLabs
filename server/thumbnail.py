"""
thumbnail.py — VIRAL-Ω's click-through thumbnail maker (1280x720 YouTube JPG).
═══════════════════════════════════════════════════════════════════════════════
What makes a thumbnail get clicked, applied mechanically:
  frame     sample the video, skip intro/end card, score each still (sharpness + contrast + colour + a bright subject)
            → the strongest frame, not frame 0.5 s
  grade     punch-in crop, saturation/contrast lift, dark vignette on the text side so words never fight the art
  words     2-4 words, HUGE (fills ~half the width), Impact with a thick black stroke + shadow, one accent word in
            amber; text says what the TITLE doesn't (curiosity gap), never repeats it
  ≤ 2 MB    YouTube's limit; JPG q≈90

make(video, out, text=..., accent=...) works on any file; viral.thumbnail(pid) wires it to a post.
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

W, H = 1280, 720
AMBER = (255, 176, 0)
FONT = next((f for f in (r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\ariblk.ttf",
                         "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.isfile(f)), None)
try:
    import core
    FFMPEG = core.FFMPEG or "ffmpeg"
except Exception:
    FFMPEG = "ffmpeg"
_probe = os.path.join(os.path.dirname(FFMPEG), "ffprobe" + (".exe" if FFMPEG.lower().endswith(".exe") else ""))
FFPROBE = _probe if os.path.isfile(_probe) else "ffprobe"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _duration(src):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True, timeout=60, creationflags=NOWIN)
    return float(r.stdout.strip() or 0)


def _grab(src, at, path):
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % at, "-i", src, "-frames:v", "1", "-q:v", "2", path],
                   capture_output=True, timeout=60, creationflags=NOWIN)
    return os.path.isfile(path)


def score(img):
    """Higher = a stronger thumbnail still: sharp edges, contrast, colour, and a bright focal area."""
    g = img.convert("L").resize((320, 180))
    sharp = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0] ** .5
    contrast = ImageStat.Stat(g).stddev[0]
    rg = ImageStat.Stat(img.convert("RGB").resize((160, 90)).convert("HSV").split()[1]).mean[0]   # saturation
    bright = sorted(g.getdata())[-len(g.getdata()) // 20]          # the top 5% = is there a lit subject at all
    return sharp * 1.2 + contrast + rg * .4 + bright * .15


def best_frames(src, n=3, samples=24, skip_start=0.04, skip_end=0.10):
    """Top-n (time, score) stills, spread apart so variants differ."""
    dur = _duration(src) or 10
    t0, t1 = dur * skip_start, dur * (1 - skip_end)
    tmp = tempfile.mkdtemp(prefix="thumb_")
    cands = []
    for i in range(samples):
        at = t0 + (t1 - t0) * (i + .5) / samples
        p = os.path.join(tmp, "s%02d.jpg" % i)
        if _grab(src, at, p):
            with Image.open(p) as im:
                cands.append((at, score(im)))
            os.remove(p)
    os.rmdir(tmp)
    cands.sort(key=lambda c: -c[1])
    picked, gap = [], (t1 - t0) / max(n * 2, 1)
    for at, s in cands:
        if all(abs(at - q) > gap for q, _ in picked):
            picked.append((at, s))
        if len(picked) == n:
            break
    return picked


def _fit_font(draw, words, max_w, max_h, start=260):
    size = start
    while size > 40:
        f = ImageFont.truetype(FONT, size)
        lines = [" ".join(l) for l in words]
        ws = [draw.textbbox((0, 0), l, font=f, stroke_width=size // 14)[2] for l in lines]
        if max(ws) <= max_w and size * 1.02 * len(lines) <= max_h:
            return f
        size -= 8
    return ImageFont.truetype(FONT, 40)


def _split(words):
    """1-2 words → one line; more → two lines balanced by character width, not word count ("I / HEAR EVERYTHING")."""
    if len(words) <= 2:
        return [words]
    best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
    return [words[:best], words[best:]]


def compose(frame, text, accent=None, side="left", sub=None, zoom=1.12, crop_bottom=0.0):
    """frame (PIL) + 2-4 words → finished 1280x720 thumbnail. crop_bottom drops a burned-in caption band."""
    img = frame.convert("RGB")
    if crop_bottom:
        img = img.crop((0, 0, img.width, int(img.height * (1 - crop_bottom))))
    s = max(W / img.width, H / img.height) * zoom                   # punch-in: tighter = bigger subject
    img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    ox = (img.width - W) // 2 + (int(W * (zoom - 1) / 2) if side == "left" else -int(W * (zoom - 1) / 2))
    ox = max(0, min(img.width - W, ox))
    img = img.crop((ox, (img.height - H) // 2, ox + W, (img.height - H) // 2 + H))
    img = ImageEnhance.Color(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Sharpness(img).enhance(1.4)

    shade = Image.new("L", (W, H), 0)                               # dark gradient behind the words
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        f = (1 - x / (W * .62)) if side == "left" else ((x - W * .38) / (W * .62))
        sd.line([(x, 0), (x, H)], fill=int(235 * max(0, min(1, f)) ** 1.2))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * .25, -H * .35, W * 1.25, H * 1.35), fill=255)
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vig.filter(ImageFilter.GaussianBlur(120)))

    words = text.upper().split()
    lines = _split(words)
    d = ImageDraw.Draw(img)
    box_w, box_h = int(W * .56), int(H * (.62 if sub else .78))
    f = _fit_font(d, lines, box_w, box_h)
    sw = max(6, f.size // 14)
    acc = (accent or words[0]).upper()
    lh = int(f.size * 1.02)
    y = (H - lh * len(lines) - (70 if sub else 0)) // 2
    x0 = 56 if side == "left" else W - 56 - box_w

    def start(line):        # right side → right-aligned against the edge
        if side == "left":
            return x0
        return W - 56 - d.textbbox((0, 0), " ".join(line), font=f, stroke_width=sw)[2]
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for li, line in enumerate(lines):
        x = start(line)
        for w in line:
            col = AMBER if w == acc or acc in w else (255, 255, 255)
            if col == AMBER:
                gd.text((x, y + li * lh), w, font=f, fill=AMBER + (200,))
            x += d.textbbox((0, 0), w + " ", font=f, stroke_width=sw)[2]
    img.paste(glow.filter(ImageFilter.GaussianBlur(28)), (0, 0), glow.filter(ImageFilter.GaussianBlur(28)))
    for li, line in enumerate(lines):
        x = start(line)
        for w in line:
            col = AMBER if w == acc or acc in w else (255, 255, 255)
            d.text((x + 8, y + li * lh + 10), w, font=f, fill=(0, 0, 0), stroke_width=sw, stroke_fill=(0, 0, 0))
            d.text((x, y + li * lh), w, font=f, fill=col, stroke_width=sw, stroke_fill=(0, 0, 0))
            x += d.textbbox((0, 0), w + " ", font=f, stroke_width=sw)[2]
    if sub:
        sf = ImageFont.truetype(FONT, 54)
        sy = y + lh * len(lines) + 14
        tw = d.textbbox((0, 0), sub.upper(), font=sf)[2]
        sx = x0 if side == "left" else W - 56 - tw - 16
        d.rectangle((sx - 6, sy - 4, sx + tw + 22, sy + 66), fill=AMBER)
        d.text((sx + 8, sy), sub.upper(), font=sf, fill=(0, 0, 0))
    return img


def make(src, out, text, accent=None, side="left", sub=None, at=None, crop_bottom=0.0):
    """One thumbnail from a video (or an image). at=None → the best-scoring frame."""
    if src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        frame = Image.open(src)
    else:
        at = at if at is not None else best_frames(src, 1)[0][0]
        tmp = out + ".frame.jpg"
        _grab(src, at, tmp)
        frame = Image.open(tmp)
    img = compose(frame, text, accent, side, sub, crop_bottom=crop_bottom)
    frame.close()
    if os.path.isfile(out + ".frame.jpg"):
        os.remove(out + ".frame.jpg")
    img.save(out, "JPEG", quality=90, optimize=True)
    return {"file": out, "at": at, "text": text}


def variants(src, out_base, texts, n=3, crop_bottom=0.0):
    """n best frames × the given texts → A/B candidates (YouTube 'Test & compare' takes up to 3)."""
    frames = best_frames(src, n)
    outs = []
    for i, (at, _s) in enumerate(frames):
        t = texts[i % len(texts)]
        t, acc, sub = (t.get("text"), t.get("accent"), t.get("sub")) if isinstance(t, dict) else (t, None, None)
        outs.append(make(src, "%s_%d.jpg" % (out_base, i + 1), t, acc, "left" if i % 2 == 0 else "right", sub, at,
                         crop_bottom))
    return outs
