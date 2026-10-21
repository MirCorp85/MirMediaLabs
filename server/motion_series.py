"""MIR MOTION × SERIES — the series' Motion pack (font, palette, intro/credits/lyrics/captions) and the episode polish
pass: the assembled episode is wrapped by Remotion in an intro title, karaoke lyrics over the song, and a credits roll.
The raw assembly is kept (ep["final_raw"]) so a failed polish never loses an episode."""
import os
import time

import core
import remotion

FONTS = ("bastion", "hollow", "horizon", "matrix", "orbit", "pixel", "quill", "stencil", "vector", "velocity")
LYRIC_STYLES = ("karaoke", "pop", "reveal", "box", "off")
DEFAULT = {"on": True, "font": "orbit", "palette": {"bg": "#0b0b10", "fg": "#f4f1ea", "acc": "#ffcc33", "acc2": "#ff5a8a"},
           "intro": True, "intro_anim": "word-pop", "credits": True, "lyrics": "karaoke", "trans": "fade", "logo": ""}


def clean_pack(b):
    b = b if isinstance(b, dict) else {}
    out = dict(DEFAULT)
    out["on"] = bool(b.get("on", True))
    out["font"] = b.get("font") if b.get("font") in FONTS else DEFAULT["font"]
    pal = b.get("palette") if isinstance(b.get("palette"), dict) else {}
    out["palette"] = {k: (pal.get(k) if isinstance(pal.get(k), str) and len(pal.get(k)) == 7 and pal[k].startswith("#") else v)
                      for k, v in DEFAULT["palette"].items()}
    out["intro"] = bool(b.get("intro", True))
    out["credits"] = bool(b.get("credits", True))
    out["lyrics"] = b.get("lyrics") if b.get("lyrics") in LYRIC_STYLES else "karaoke"
    out["intro_anim"] = str(b.get("intro_anim") or "word-pop")[:20]
    out["trans"] = str(b.get("trans") or "fade")[:20]
    out["logo"] = str(b.get("logo") or "")[:200] if str(b.get("logo") or "").startswith("lib:") else ""
    return out


def pack_of(d):
    return clean_pack((d.get("setup") or {}).get("motion"))


def episode_motion(d, ep, base_name, base_secs, w, h):
    """The motion project that wraps one assembled episode."""
    mp = pack_of(d)
    scene, caps, t = [], [], 0.0
    if mp["logo"]:
        scene.append(remotion.scene("logo", 2.5, {"src": mp["logo"], "text": ""}, t))
        t += 2.5
    if mp["intro"]:
        scene.append(remotion.scene("title", 4.0, {"text": d.get("name") or "Our series", "sub": ep.get("title") or "",
                                                   "anim": mp["intro_anim"]}, t, trans={"type": mp["trans"], "dur": 0.5} if t else None,
                                    out={"type": "fade", "dur": 0.5}))
        t += 4.0
    body = t
    scene.append(remotion.scene("media", base_secs, {"src": "lib:" + base_name, "kind": "video"}, t,
                                trans={"type": mp["trans"], "dur": 0.5} if t else None))
    t += base_secs
    words = ep.get("words") or []
    if mp["lyrics"] != "off" and words:
        ws = [{"w": x["w"], "s": float(x["s"]), "e": float(x["e"])} for x in words if x.get("w")]
        if ws:
            caps.append(remotion.scene("captions", min(base_secs, ws[-1]["e"] + 1.0),
                                       {"words": ws, "style": mp["lyrics"], "pos": "bottom", "perLine": 6, "size": 58}, body))
    if mp["credits"]:
        cast = [{"role": "Starring", "name": c.get("name")} for c in d.get("characters") or [] if c.get("name")][:12]
        cast.append({"role": "Made with", "name": "MIR MEDIA LABS"})
        scene.append(remotion.scene("credits", 8.0, {"title": ep.get("title") or d.get("name") or "Credits", "lines": cast}, t,
                                    trans={"type": "fade", "dur": 0.8}))
        t += 8.0
    tracks = [{"kind": "scene", "name": "Episode", "clips": scene}]
    if caps:
        tracks.append({"kind": "captions", "name": "Lyrics", "clips": caps})
    return remotion.project("%s — %s" % (d.get("name") or "Series", ep.get("title") or "Episode"), w, h, 24, tracks,
                            palette=mp["palette"], font=mp["font"])


def polish(d, ep, uid, w, h, seconds_of):
    """Wrap ep["final"] with the Motion pack. Returns the new library name (or None when the pack is off)."""
    mp = pack_of(d)
    base = ep.get("final")
    if not mp["on"] or not base:
        return None
    secs = float(seconds_of("lib:" + base) or ep.get("song_secs") or 0)
    if secs <= 0:
        return None
    proj = episode_motion(d, ep, base, secs, w, h)
    name = core.new_name("series", ".mp4")
    remotion.render_sync(proj, os.path.join(core.LIB, name), "mp4", 18)
    core.index_add(name, {"model": "series+motion", "prompt": proj["name"], "created": time.time(), "user": uid or "owner",
                          "mode": "musical", "base": base, "secs": round(remotion.duration(remotion.clean(proj)), 2)})
    return name
