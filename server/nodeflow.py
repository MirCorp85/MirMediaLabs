r"""NODE FLOW — a ComfyUI-style wire editor built on MIR MEDIA LABS building blocks (not raw ComfyUI nodes).

Page: /flow (static/flow.html + flow.js + flow.css). A graph = {id, name, nodes:[{id,type,x,y,values}],
links:[{id, from:[node,port], to:[node,port]}]}. Ports are typed (video / image / audio / text); a value flowing on a
wire is a LIST of items ({"path": abs file} or {"text": str}) — Split makes several, Join folds them back, and an engine
fed a list runs once per item (other inputs broadcast). Engines submit through the lab's own /api/generate on the
direct-model path (model + refs + override — every ⚙ value honoured; the skill path is NOT used, it drops overrides),
one job at a time, as the graph's owner. Tools (trim/split/join/audio/upscale/side-by-side/TTS) run here with ffmpeg.
Graphs: data/flows/<user>/<id>.json. Run work files: data/flows/<user>/runs/<run>/ (Save copies into the library).
"""
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

try:
    from . import core
    from . import params
    from . import renderers
    from . import node_docs
except ImportError:
    import core
    import params
    import renderers
    import node_docs

FLOWS = os.path.join(core.DATA, "flows")
V, I, A, T = "video", "image", "audio", "text"

# ── the node catalog (shared by the page and the runner) ─────────────────────
# ins: [id, type, label, multi]   outs: [id, type, label]   model/fixed: engine path   form: own fields (tools/inputs)
CATALOG = {
    # inputs
    "in_video": {"cat": "Inputs", "label": "Video", "icon": "video", "outs": [["out", V, "video"]], "form": "file", "accept": V,
                 "desc": "Upload a clip or pick one from your library."},
    "in_image": {"cat": "Inputs", "label": "Picture", "icon": "image", "outs": [["out", I, "picture"]], "form": "file", "accept": I,
                 "desc": "Upload a picture or pick one from your library."},
    "in_audio": {"cat": "Inputs", "label": "Audio", "icon": "music", "outs": [["out", A, "audio"]], "form": "file", "accept": A,
                 "desc": "Upload a song / voice or pick one from your library."},
    "in_text": {"cat": "Inputs", "label": "Text prompt", "icon": "type", "outs": [["out", T, "text"]],
                "fields": [{"k": "text", "label": "Text", "type": "textarea", "def": "", "desc": "What you want — a prompt, lyrics or a line to speak."}],
                "desc": "A prompt, lyrics or script."},
    "in_library": {"cat": "Inputs", "label": "Library item", "icon": "grid", "outs": [["out", "any", "file"]], "form": "file", "accept": "any",
                   "desc": "Any finished piece from your library — its port takes the item's type."},
    # engines (direct model path through /api/generate)
    "h3_gen": {"cat": "Engines", "label": "H3 · generate", "icon": "film", "model": "h3", "fixed": {"mode": "auto"},
               "ins": [["prompt", T, "prompt", 0], ["images", I, "pictures", 1], ["audio", A, "soundtrack", 0]], "outs": [["out", V, "clip"]],
               "desc": "Text (+ optional pictures) → video with sound."},
    "h3_i2v": {"cat": "Engines", "label": "H3 · picture → video", "icon": "film", "model": "h3", "fixed": {"mode": "i2v"},
               "ins": [["image", I, "first frame", 0], ["prompt", T, "prompt", 0]], "outs": [["out", V, "clip"]],
               "desc": "Animate a picture."},
    "h3_control": {"cat": "Engines", "label": "H3 · motion control", "icon": "film", "model": "h3", "fixed": {"mode": "control"},
                   "ins": [["video", V, "motion clip", 0], ["images", I, "cast pictures", 1], ["prompt", T, "prompt", 0]],
                   "outs": [["out", V, "clip"]], "fit": True,
                   "desc": "Follow the clip's pose / edges with a new cast. Max 15 s per clip — put a Split before it for longer clips."},
    "h3_extend": {"cat": "Engines", "label": "H3 · extend clip", "icon": "film", "model": "h3", "fixed": {"mode": "extend"},
                  "ins": [["video", V, "clip", 0], ["prompt", T, "what happens next", 0]], "outs": [["out", V, "longer clip"]],
                  "desc": "Continue a clip from its last frames."},
    "h3_sing": {"cat": "Engines", "label": "H3 · sing / lip-sync", "icon": "mic", "model": "h3", "fixed": {"mode": "sing"},
                "ins": [["image", I, "singer", 0], ["audio", A, "vocal", 0], ["prompt", T, "prompt", 0]], "outs": [["out", V, "clip"]],
                "desc": "A picture sings or talks to the audio."},
    "vace_swap": {"cat": "Engines", "label": "VACE · swap person", "icon": "users", "model": "vace", "fixed": {},
                  "ins": [["video", V, "clip", 0], ["image", I, "new person", 0], ["prompt", T, "prompt", 0]], "outs": [["out", V, "clip"]],
                  "desc": "Replace the masked person in a clip with the one in the picture."},
    "qimg": {"cat": "Engines", "label": "Qwen-Image", "icon": "image", "model": "qimg", "fixed": {},
             "ins": [["prompt", T, "prompt", 0], ["images", I, "pictures to edit", 1]], "outs": [["out", I, "picture"]],
             "desc": "Text → picture, or edit attached pictures."},
    "music3": {"cat": "Engines", "label": "Music 3", "icon": "music", "model": "music3", "fixed": {},
               "ins": [["prompt", T, "style", 0], ["lyrics", T, "lyrics", 0]], "outs": [["out", A, "song"]],
               "desc": "A full song from a style + lyrics."},
    "ace": {"cat": "Engines", "label": "ACE-Step", "icon": "disc", "model": "ace", "fixed": {},
            "ins": [["prompt", T, "style", 0], ["audio", A, "audio to remix", 0]], "outs": [["out", A, "song"]],
            "desc": "Songs, remixes and covers."},
    "tts": {"cat": "Engines", "label": "Voice (TTS)", "icon": "volume", "ins": [["text", T, "words", 0]], "outs": [["out", A, "voice"]],
            "fields": [{"k": "voice", "label": "Voice", "type": "select", "def": "", "opts": [], "desc": "Local Kokoro voice."},
                       {"k": "speed", "label": "Speed", "type": "number", "def": 1.0, "min": 0.7, "max": 1.3, "step": 0.05}],
            "desc": "Speak the text with a natural local voice."},
    # tools (ffmpeg, no GPU)
    "trim": {"cat": "Tools", "label": "Trim clip", "icon": "scissors", "ins": [["video", V, "clip", 0]], "outs": [["out", V, "clip"]],
             "fields": [{"k": "start", "label": "Start (s)", "type": "number", "def": 0, "min": 0, "step": 0.1},
                        {"k": "end", "label": "End (s, 0 = to the end)", "type": "number", "def": 0, "min": 0, "step": 0.1}],
             "desc": "Keep only part of a clip."},
    "crop": {"cat": "Tools", "label": "Crop / focus", "icon": "scan", "ins": [["video", V, "clip", 0]], "outs": [["out", V, "clip"]],
             "fields": [{"k": "preset", "label": "Area", "type": "select", "def": "full",
                         "opts": [["full", "whole frame"], ["center80", "centre 80%"], ["center60", "centre 60% (tight on the action)"],
                                  ["left", "left half"], ["right", "right half"], ["top", "top two thirds"], ["custom", "custom (below)"]],
                         "desc": "Tighter framing = bigger bodies = a cleaner skeleton / depth map."},
                        {"k": "x", "label": "Custom left (0-1)", "type": "number", "def": 0, "min": 0, "max": 1, "step": 0.01},
                        {"k": "y", "label": "Custom top (0-1)", "type": "number", "def": 0, "min": 0, "max": 1, "step": 0.01},
                        {"k": "w", "label": "Custom width (0-1)", "type": "number", "def": 1, "min": 0.05, "max": 1, "step": 0.01},
                        {"k": "h", "label": "Custom height (0-1)", "type": "number", "def": 1, "min": 0.05, "max": 1, "step": 0.01},
                        {"k": "speed", "label": "Speed", "type": "select", "def": "1",
                         "opts": [["1", "normal"], ["0.75", "0.75x (slower)"], ["0.5", "0.5x - fast punches / kicks stay sharp"]],
                         "desc": "Slowing down gives the control more frames per move. Speed the result back up later if you want."}],
             "desc": "Crop the clip to the action and optionally slow it down (24 fps out)."},
    "pose_preview": {"cat": "Tools", "label": "Pose preview", "icon": "eye", "ins": [["video", V, "clip", 0]], "outs": [["out", V, "preview"]],
                     "fields": [{"k": "control", "label": "Preview", "type": "select", "def": "pose",
                                 "opts": [["pose", "pose skeleton (SDPose)"], ["depth", "depth map (Depth Anything V2)"], ["canny", "edges (canny)"]],
                                 "desc": "Clip on the left, what motion control follows on the right. Check it BEFORE a full render: "
                                         "merged / swapped limbs = jitter."},
                                {"k": "control_people", "label": "People to track (pose)", "type": "number", "def": 2, "min": 1, "max": 6}],
                     "desc": "Quick look at the control video H3 would follow - seconds, no H3 render."},
    "split": {"cat": "Tools", "label": "Split clip", "icon": "scissors", "ins": [["video", V, "clip", 0]], "outs": [["out", V, "pieces"]],
              "fields": [{"k": "max", "label": "Longest piece (s)", "type": "number", "def": 15, "min": 4, "max": 60, "step": 0.5,
                          "desc": "Cut into equal pieces no longer than this. H3 renders at most 15 s at a time."},
                         {"k": "overlap", "label": "Overlap (s)", "type": "number", "def": 0, "min": 0, "max": 2, "step": 0.1,
                          "desc": "Each piece repeats the end of the one before by this much, so Join can crossfade the seam "
                                  "instead of a hard motion reset. 0.5 s is a good start."}],
              "desc": "Cut a long clip into equal pieces — the next engine runs once per piece."},
    "join": {"cat": "Tools", "label": "Join clips", "icon": "layers", "ins": [["clips", V, "clips (in order)", 1]], "outs": [["out", V, "clip"]],
             "fields": [{"k": "fps", "label": "Frame rate", "type": "select", "def": "24", "opts": ["24", "25", "30"]},
                        {"k": "xfade", "label": "Seams", "type": "select", "def": "auto",
                         "opts": [["auto", "crossfade over the Split overlap (cut if none)"], ["cut", "hard cut"],
                                  ["fade", "always crossfade (length below)"]]},
                        {"k": "xfade_secs", "label": "Crossfade length (s)", "type": "number", "def": 0.5, "min": 0.1, "max": 2, "step": 0.05}],
             "desc": "Glue all pieces back into one clip (sized like the first)."},
    "extract_audio": {"cat": "Tools", "label": "Take audio", "icon": "volume", "ins": [["video", V, "clip", 0]], "outs": [["out", A, "audio"]],
                      "desc": "The sound of a clip — e.g. keep the original audio for the final cut."},
    "set_audio": {"cat": "Tools", "label": "Replace audio", "icon": "music", "ins": [["video", V, "clip", 0], ["audio", A, "audio", 0]],
                  "outs": [["out", V, "clip"]],
                  "fields": [{"k": "how", "label": "How", "type": "select", "def": "replace",
                              "opts": [["replace", "replace the clip's sound"], ["mix", "mix with the clip's sound"]]},
                             {"k": "vol", "label": "New audio volume", "type": "number", "def": 1.0, "min": 0, "max": 2, "step": 0.05}],
                  "desc": "Put a soundtrack / the original audio on a clip."},
    "upscale": {"cat": "Tools", "label": "Upscale", "icon": "expand", "ins": [["media", "visual", "picture or clip", 0]],
                "outs": [["out", "same", "bigger"]],
                "fields": [{"k": "factor", "label": "Size", "type": "select", "def": "2", "opts": [["1.5", "1.5×"], ["2", "2×"], ["3", "3×"]]}],
                "desc": "Sharp lanczos resize of a picture or clip."},
    "sbs": {"cat": "Tools", "label": "Side-by-side cast", "icon": "users", "ins": [["images", I, "pictures (left → right)", 1]],
            "outs": [["out", I, "cast sheet"]],
            "fields": [{"k": "height", "label": "Height (px)", "type": "number", "def": 768, "min": 256, "max": 2048}],
            "desc": "Put several character pictures in one row — one cast picture for multi-person motion control."},
    # output
    "save": {"cat": "Output", "label": "Save to library", "icon": "download", "ins": [["media", "any", "result", 1]], "outs": [],
             "fields": [{"k": "name", "label": "Name", "type": "text", "def": "", "desc": "Optional — used in the file name."}],
             "desc": "Put the result in your library (current session)."},
}

TEMPLATES = [
    {"id": "tpl_motioncopy", "name": "Motion copy long clip",
     "desc": "Clip → split ≤15 s → H3 motion control (pose, 2 people, cast picture, fixed seed) per piece → join → original audio → save",
     "nodes": [
         {"id": "n1", "type": "in_video", "x": 40, "y": 60, "values": {}},
         {"id": "n2", "type": "in_image", "x": 40, "y": 250, "values": {}},
         {"id": "n3", "type": "in_image", "x": 40, "y": 400, "values": {}},
         {"id": "n4", "type": "in_text", "x": 40, "y": 550, "values": {"text": "two cartoon characters boxing in a ring, same moves as the reference, clean 3D cartoon look"}},
         {"id": "n5", "type": "split", "x": 330, "y": 60, "values": {"max": 15}},
         {"id": "n6", "type": "sbs", "x": 330, "y": 300, "values": {"height": 768}},
         {"id": "n7", "type": "h3_control", "x": 620, "y": 200,
          "values": {"control": "pose", "control_people": 2, "seed": 777, "control_audio": "clip", "res": "standard", "quality": "turbo8"}},
         {"id": "n8", "type": "join", "x": 910, "y": 200, "values": {"fps": "24"}},
         {"id": "n9", "type": "extract_audio", "x": 620, "y": 20, "values": {}},
         {"id": "n10", "type": "set_audio", "x": 1180, "y": 120, "values": {"how": "replace", "vol": 1.0}},
         {"id": "n11", "type": "save", "x": 1450, "y": 140, "values": {"name": "motion copy"}}],
     "links": [["n1", "out", "n5", "video"], ["n2", "out", "n6", "images"], ["n3", "out", "n6", "images"],
               ["n5", "out", "n7", "video"], ["n6", "out", "n7", "images"], ["n4", "out", "n7", "prompt"],
               ["n7", "out", "n8", "clips"], ["n1", "out", "n9", "video"], ["n8", "out", "n10", "video"],
               ["n9", "out", "n10", "audio"], ["n10", "out", "n11", "media"]]},
    {"id": "tpl_mc_depth", "name": "Motion Copy - Accurate (Depth)",
     "desc": "Clip -> crop/focus -> split <=10 s with 0.5 s overlap -> H3 control on a DEPTH map (strength 1.4, full quality, fixed seed, "
             "cast picture) -> join with crossfades over the overlap -> original audio -> save. Best for fast / overlapping action.",
     "nodes": [
         {"id": "n1", "type": "in_video", "x": 40, "y": 60, "values": {}},
         {"id": "n2", "type": "in_image", "x": 40, "y": 260, "values": {}},
         {"id": "n3", "type": "in_image", "x": 40, "y": 410, "values": {}},
         {"id": "n4", "type": "in_text", "x": 40, "y": 560, "values": {"text": "two cartoon characters boxing in a ring, exact same moves as the reference, clean 3D cartoon look"}},
         {"id": "n5", "type": "crop", "x": 330, "y": 40, "values": {"preset": "full", "speed": "1"}},
         {"id": "n12", "type": "pose_preview", "x": 620, "y": -150, "values": {"control": "depth"}},
         {"id": "n6", "type": "split", "x": 620, "y": 60, "values": {"max": 10, "overlap": 0.5}},
         {"id": "n7", "type": "sbs", "x": 330, "y": 330, "values": {"height": 768}},
         {"id": "n8", "type": "h3_control", "x": 910, "y": 220,
          "values": {"control": "depth", "control_strength": 1.4, "seed": 4242, "quality": "full", "res": "standard", "control_audio": "clip"}},
         {"id": "n9", "type": "join", "x": 1200, "y": 220, "values": {"fps": "24", "xfade": "auto"}},
         {"id": "n10", "type": "extract_audio", "x": 910, "y": 0, "values": {}},
         {"id": "n11", "type": "set_audio", "x": 1470, "y": 140, "values": {"how": "replace", "vol": 1.0}},
         {"id": "n13", "type": "save", "x": 1740, "y": 160, "values": {"name": "motion copy depth"}}],
     "links": [["n1", "out", "n5", "video"], ["n5", "out", "n12", "video"], ["n5", "out", "n6", "video"], ["n2", "out", "n7", "images"],
               ["n3", "out", "n7", "images"], ["n6", "out", "n8", "video"], ["n7", "out", "n8", "images"], ["n4", "out", "n8", "prompt"],
               ["n8", "out", "n9", "clips"], ["n5", "out", "n10", "video"], ["n9", "out", "n11", "video"], ["n10", "out", "n11", "audio"],
               ["n11", "out", "n13", "media"]]},
    {"id": "tpl_swap_exact", "name": "Motion Swap - Exact (VACE mask)",
     "desc": "Clip -> split -> VACE swap (mask = person, both people replaced from the cast picture) -> join -> original audio -> save. "
             "Exact motion, but the bodies keep the original shapes.",
     "nodes": [
         {"id": "n1", "type": "in_video", "x": 40, "y": 60, "values": {}},
         {"id": "n2", "type": "in_image", "x": 40, "y": 260, "values": {}},
         {"id": "n3", "type": "in_image", "x": 40, "y": 410, "values": {}},
         {"id": "n4", "type": "in_text", "x": 40, "y": 560, "values": {"text": "two cartoon characters, clean 3D cartoon look"}},
         {"id": "n5", "type": "split", "x": 330, "y": 60, "values": {"max": 10, "overlap": 0.5}},
         {"id": "n6", "type": "sbs", "x": 330, "y": 330, "values": {"height": 768}},
         {"id": "n7", "type": "vace_swap", "x": 620, "y": 200, "values": {"mask_what": "person", "swap_secs": "10", "seed": 4242}},
         {"id": "n8", "type": "join", "x": 910, "y": 200, "values": {"fps": "24", "xfade": "auto"}},
         {"id": "n9", "type": "extract_audio", "x": 620, "y": 0, "values": {}},
         {"id": "n10", "type": "set_audio", "x": 1180, "y": 120, "values": {"how": "replace", "vol": 1.0}},
         {"id": "n11", "type": "save", "x": 1450, "y": 140, "values": {"name": "motion swap"}}],
     "links": [["n1", "out", "n5", "video"], ["n2", "out", "n6", "images"], ["n3", "out", "n6", "images"],
               ["n5", "out", "n7", "video"], ["n6", "out", "n7", "image"], ["n4", "out", "n7", "prompt"],
               ["n7", "out", "n8", "clips"], ["n1", "out", "n9", "video"], ["n8", "out", "n10", "video"],
               ["n9", "out", "n10", "audio"], ["n10", "out", "n11", "media"]]},
    {"id": "tpl_pic2clip", "name": "Picture → animated clip",
     "desc": "Prompt → Qwen-Image picture → H3 animates it → save both",
     "nodes": [
         {"id": "n1", "type": "in_text", "x": 40, "y": 80, "values": {"text": "a cozy cartoon fox reading under a tree, golden hour"}},
         {"id": "n2", "type": "qimg", "x": 330, "y": 40, "values": {}},
         {"id": "n3", "type": "h3_i2v", "x": 620, "y": 80, "values": {"seconds": 5}},
         {"id": "n4", "type": "save", "x": 910, "y": 80, "values": {"name": "fox"}}],
     "links": [["n1", "out", "n2", "prompt"], ["n2", "out", "n3", "image"], ["n1", "out", "n3", "prompt"],
               ["n2", "out", "n4", "media"], ["n3", "out", "n4", "media"]]},
    {"id": "tpl_songclip", "name": "Song + clip",
     "desc": "Style → Music 3 song; prompt → H3 clip; song laid on the clip → save",
     "nodes": [
         {"id": "n1", "type": "in_text", "x": 40, "y": 40, "values": {"text": "upbeat kids pop, ukulele, claps"}},
         {"id": "n2", "type": "in_text", "x": 40, "y": 240, "values": {"text": "cartoon animals dancing in a sunny meadow"}},
         {"id": "n3", "type": "music3", "x": 330, "y": 40, "values": {"duration": 30}},
         {"id": "n4", "type": "h3_gen", "x": 330, "y": 240, "values": {"seconds": 10}},
         {"id": "n5", "type": "set_audio", "x": 620, "y": 140, "values": {"how": "replace"}},
         {"id": "n6", "type": "save", "x": 900, "y": 140, "values": {"name": "song clip"}}],
     "links": [["n1", "out", "n3", "prompt"], ["n2", "out", "n4", "prompt"], ["n4", "out", "n5", "video"],
               ["n3", "out", "n5", "audio"], ["n5", "out", "n6", "media"]]},
]


def _tpl_graph(t):
    return {"id": "", "name": t["name"], "nodes": json.loads(json.dumps(t["nodes"])),
            "links": [{"id": "l%d" % i, "from": [a, b], "to": [c, d]} for i, (a, b, c, d) in enumerate(t["links"])]}


def catalog(models_schema=None):
    """Catalog + each engine's ⚙ fields (params.schema → friendly labels + plain descriptions from param_docs)."""
    out = {}
    for k, n in CATALOG.items():
        n = dict(n, **{"doc": node_docs.doc(k)})
        if n.get("model"):
            sch = params.schema(n["model"])
            n["fields"] = [f for f in sch["fields"] if f["k"] not in n["fixed"]]
            n["color"] = sch.get("color")
            if n.get("fit"):
                n["fields"] = [{"k": "_fit", "label": "Length = piece length", "type": "select", "def": "on",
                                "opts": [["on", "on — each render as long as its clip piece"], ["off", "off — use the length below"]],
                                "desc": "Sets the H3 length to each incoming clip's own length (4–15 s)."}] + n["fields"]
        if k == "h3_control":
            first = ("control", "control_strength", "control_people", "seed")
            top = []
            for kk in first:
                f = next((dict(x) for x in n["fields"] if x["k"] == kk), None)
                if not f:
                    continue
                f["group"] = "Motion control"
                if kk == "control":
                    f["label"] = "Follow"
                    f["opts"] = [["depth", "depth - fast / overlapping action (boxing, fights, dance pairs)"],
                                 ["pose", "pose skeleton - cleanest for one dancer"]] + [o for o in f["opts"] if o[0] not in ("pose", "depth")]
                    f["desc"] = ("depth = better for fast or overlapping action (no skeleton to break or swap limbs); "
                                 "pose = cleaner for a single dancer; edges keep the layout; 'my control video' = use the clip as is.")
                    f["odesc"] = dict(f.get("odesc") or {}, depth="Depth Anything V2 map of every frame (made locally) - follows "
                                      "body volume, survives motion blur and two fighters overlapping.")
                if kk == "control_strength":
                    f["label"] = "Strength (0-3)"
                    f["desc"] = "How closely to follow. 1 = normal; 1.3-1.6 for depth on fast action; too high looks stiff."
                top.append(f)
            n["fields"] = n["fields"][:1] + top + [x for x in n["fields"][1:] if x["k"] not in first]
        if k == "tts":
            try:
                try:
                    from . import tts
                except ImportError:
                    import tts
                n["fields"] = [dict(n["fields"][0], opts=[[v, l] for v, l in tts.VOICES.items()], **{"def": tts.DEFAULT_VOICE})] + n["fields"][1:]
            except Exception:
                pass
        out[k] = n
    return out


# ── storage ──────────────────────────────────────────────────────────────────
def _udir(u, *sub):
    d = os.path.join(FLOWS, re.sub(r"[^A-Za-z0-9_-]", "_", str(u or "owner")), *sub)
    os.makedirs(d, exist_ok=True)
    return d


def _gid(s):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(s or ""))[:40]


def list_graphs(u):
    out = []
    for fn in os.listdir(_udir(u)):
        if fn.endswith(".json"):
            g = core.load_json(os.path.join(_udir(u), fn), {})
            out.append({"id": g.get("id"), "name": g.get("name"), "updated": g.get("updated"), "nodes": len(g.get("nodes") or [])})
    return sorted(out, key=lambda x: -(x.get("updated") or 0))


def save_graph(u, g):
    gid = _gid(g.get("id")) or "f%d" % int(time.time() * 1000)
    g = {"id": gid, "name": str(g.get("name") or "Untitled flow")[:80], "nodes": g.get("nodes") or [], "links": g.get("links") or [],
         "updated": time.time()}
    core.save_json(os.path.join(_udir(u), gid + ".json"), g)
    return g


# ── runner ───────────────────────────────────────────────────────────────────
RUNS = {}
_RLOCK = threading.Lock()


class Stop(Exception):
    pass


def _kind(path):
    return core.kind_of(path) or "file"


def _has_audio(path):
    try:
        r = subprocess.run([core.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True, timeout=30,
                           creationflags=core.NO_WINDOW)
        return " Audio:" in r.stderr
    except Exception:
        return False


def topo(nodes, links):
    ids = [n["id"] for n in nodes]
    deps = {i: set() for i in ids}
    for l in links:
        if l["to"][0] in deps and l["from"][0] in deps:
            deps[l["to"][0]].add(l["from"][0])
    order, done = [], set()
    while len(order) < len(ids):
        ready = [i for i in ids if i not in done and deps[i] <= done]
        if not ready:
            raise ValueError("the wires make a loop — a node can't feed itself")
        for i in ready:
            order.append(i)
            done.add(i)
    return order


class Run:
    def __init__(self, h, user, session, graph):
        self.h, self.user, self.session, self.g = h, user, session, graph
        self.id = "r%d" % int(time.time() * 1000)
        self.dir = _udir(user, "runs", self.id)
        self.status, self.error, self.stop, self.job = "running", "", False, None
        self.nodes = {n["id"]: {"status": "waiting", "note": "", "outs": []} for n in graph["nodes"]}
        self.vals = {}
        self.started, self.finished = time.time(), None

    # -- helpers
    def url(self, item):
        p = item.get("path")
        if not p:
            return None
        if os.path.dirname(os.path.abspath(p)) == os.path.abspath(core.LIB):
            return "/media/" + os.path.basename(p)
        return "/flow/file/%s/%s" % (self.id, os.path.basename(p))

    def out(self, nid, items, note=""):
        self.vals[nid] = items
        self.nodes[nid].update(status="done", note=note,
                               outs=[{"kind": _kind(i["path"]) if i.get("path") else "text", "url": self.url(i),
                                      "text": (i.get("text") or "")[:300]} for i in items][:24])

    def tmp(self, ext):
        return os.path.join(self.dir, "%s%s" % (uuid.uuid4().hex[:10], ext))

    def check(self):
        if self.stop:
            raise Stop()

    def ins(self, node, port):
        items = []
        for l in self.g["links"]:
            if l["to"][0] == node["id"] and l["to"][1] == port:
                items += self.vals.get(l["from"][0]) or []
        return items

    # -- engines through /api/generate (direct model path: every override honoured)
    def engine(self, node, spec):
        vals = dict(node.get("values") or {})
        fit = vals.pop("_fit", "on") == "on" and spec.get("fit")
        ports = {p[0]: self.ins(node, p[0]) for p in spec.get("ins", [])}
        texts = [i["text"] for p in spec["ins"] if p[1] == T and p[0] != "lyrics" for i in ports[p[0]] if i.get("text")]
        lyrics = [i["text"] for i in ports.get("lyrics", []) if i.get("text")]
        media = [(p, ports[p[0]]) for p in spec["ins"] if p[1] != T and ports[p[0]]]
        n = max([len(v) for p, v in media if not p[3]] + [1])          # a list on a single port → one render per item
        out = []
        for k in range(n):
            self.check()
            refs, length, meta = [], None, {}
            depth = spec.get("fit") and vals.get("control") == "depth"
            for p, items in media:
                pick = items if p[3] else [items[min(k, len(items) - 1)]]
                for it in pick:
                    if it.get("path"):
                        path = it["path"]
                        if p[1] == V and length is None:
                            length = renderers.media_seconds(path)
                            meta = {kk: vv for kk, vv in it.items() if kk in ("overlap",)}
                            if depth:            # depth control = our own depth video, followed as-is by H3
                                self.nodes[node["id"]]["note"] = "render %d/%d - depth map" % (k + 1, n)
                                try:
                                    from . import depth as _depth
                                except ImportError:
                                    import depth as _depth
                                path = _depth.depth_video(path, self.tmp("_depth.mp4"), stop=lambda: self.stop)
                        refs.append(self.h["to_ref"](self.user, path))
            for t in lyrics:
                refs.append(self.h["text_ref"](self.user, t))
            over = {kk: vv for kk, vv in vals.items() if vv not in ("", None) and not kk.startswith("_")}
            over.update(spec["fixed"])
            if depth:
                over["control"] = "as_is"
            if fit and length:
                over["seconds"] = max(4, min(15, int(round(length))))
            body = {"model": spec["model"], "prompt": " ".join(texts).strip(), "refs": refs, "override": over, "session": self.session}
            self.nodes[node["id"]]["note"] = "render %d/%d · queued" % (k + 1, n)
            job = None
            while job is None:
                self.check()
                job, err, busy = self.h["submit"](self.user, body)
                if busy:
                    self.nodes[node["id"]]["note"] = "render %d/%d · waiting for the lab" % (k + 1, n)
                    time.sleep(5)
                elif err:
                    raise RuntimeError(err)
            self.job = job["id"]
            self.nodes[node["id"]]["job"] = job["id"]
            while True:
                time.sleep(2.5)
                j = self.h["job"](job["id"]) or {}
                st = j.get("status")
                pr = j.get("progress")
                self.nodes[node["id"]]["note"] = "render %d/%d · %s%s" % (k + 1, n, j.get("stage") or st,
                                                                         (" %s%%" % pr) if isinstance(pr, (int, float)) else "")
                if self.stop:
                    self.h["cancel"](job["id"])
                    raise Stop()
                if st == "done":
                    break
                if st in ("error", "cancelled"):
                    raise RuntimeError("render %d/%d: %s" % (k + 1, n, j.get("error") or st))
            self.job = None
            files = [f for f in (j.get("files") or []) if core.kind_of(f) in (V, I, A)]
            want = spec["outs"][0][1]
            pick = [f for f in files if core.kind_of(f) == want] or files
            if not pick:
                raise RuntimeError("render %d/%d finished without a %s" % (k + 1, n, want))
            out.append(dict(meta, path=os.path.join(core.LIB, pick[0])))
            self.out(node["id"], out, "render %d/%d done" % (k + 1, n))
            self.nodes[node["id"]]["status"] = "running"
        return out, "%d render%s" % (n, "s" if n > 1 else "")

    def _job(self, node, body, what, want):
        """Submit one lab job (waits its turn), follow it, return the library path of its first `want` file."""
        job = None
        while job is None:
            self.check()
            job, err, busy = self.h["submit"](self.user, body)
            if busy:
                self.nodes[node["id"]]["note"] = "%s · waiting for the lab" % what
                time.sleep(5)
            elif err:
                raise RuntimeError(err)
        self.job = job["id"]
        while True:
            time.sleep(2.5)
            j = self.h["job"](job["id"]) or {}
            self.nodes[node["id"]]["note"] = "%s · %s" % (what, j.get("stage") or j.get("status"))
            if self.stop:
                self.h["cancel"](job["id"])
                raise Stop()
            if j.get("status") == "done":
                break
            if j.get("status") in ("error", "cancelled"):
                raise RuntimeError("%s: %s" % (what, j.get("error") or j.get("status")))
        self.job = None
        files = [f for f in (j.get("files") or []) if core.kind_of(f) == want] or j.get("files") or []
        if not files:
            raise RuntimeError("%s finished without a result" % what)
        return os.path.join(core.LIB, files[0])

    # -- tools
    def tool(self, node, t):
        v = {f["k"]: f["def"] for f in CATALOG[t].get("fields") or []}
        v.update(node.get("values") or {})
        if t in ("in_video", "in_image", "in_audio", "in_library"):
            p = v.get("_path")
            if not p or not os.path.isfile(p):
                raise RuntimeError("no file chosen — upload one or pick from the library")
            return [{"path": p}], os.path.basename(p).split("_", 2)[-1]
        if t == "in_text":
            if not str(v.get("text") or "").strip():
                raise RuntimeError("empty text")
            return [{"text": str(v["text"]).strip()}], ""
        if t == "tts":
            try:
                from . import tts
            except ImportError:
                import tts
            words = " ".join(i["text"] for i in self.ins(node, "text") if i.get("text"))
            dst = self.tmp(".wav")
            shutil.copy2(tts.say(words, v.get("voice"), v.get("speed")), dst)
            return [{"path": dst}], ""
        src = [i for i in self.ins(node, (CATALOG[t]["ins"][0][0])) if i.get("path")]
        if not src:
            raise RuntimeError("nothing wired into '%s'" % CATALOG[t]["ins"][0][2])
        out = []
        if t == "trim":
            for i in src:
                d = self.tmp(".mp4")
                end = float(v.get("end") or 0)
                renderers.ffmpeg(["-ss", "%.3f" % float(v.get("start") or 0), "-i", i["path"]] +
                                 (["-t", "%.3f" % max(0.1, end - float(v.get("start") or 0))] if end > 0 else []) +
                                 ["-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "aac", d], 900)
                out.append({"path": d})
            return out, ""
        if t == "crop":
            pre = {"full": (0, 0, 1, 1), "center80": (.1, .1, .8, .8), "center60": (.2, .2, .6, .6), "left": (0, 0, .5, 1),
                   "right": (.5, 0, .5, 1), "top": (0, 0, 1, .667)}
            x, y, w, hh = pre.get(v.get("preset")) or (float(v.get("x") or 0), float(v.get("y") or 0), float(v.get("w") or 1), float(v.get("h") or 1))
            w, hh = min(w, 1 - x), min(hh, 1 - y)
            sp = float(v.get("speed") or 1)
            for i in src:
                d = self.tmp(".mp4")
                vf = "crop=trunc(iw*%.4f/2)*2:trunc(ih*%.4f/2)*2:iw*%.4f:ih*%.4f,setpts=PTS/%.3f,fps=24" % (w, hh, x, y, sp)
                aud = ["-af", "atempo=%.3f" % sp, "-c:a", "aac"] if _has_audio(i["path"]) else ["-an"]
                renderers.ffmpeg(["-i", i["path"], "-vf", vf] + aud + ["-c:v", "libx264", "-crf", "16", "-preset", "fast", d], 1800)
                out.append({"path": d})
            return out, "%s%s" % (v.get("preset"), "" if sp == 1 else " - %.2gx" % sp)
        if t == "pose_preview":
            for i in src:
                self.check()
                if v.get("control") == "depth":
                    try:
                        from . import depth as _depth
                    except ImportError:
                        import depth as _depth
                    dm = _depth.depth_video(i["path"], self.tmp("_depth.mp4"), stop=lambda: self.stop)
                    d = self.tmp(".mp4")
                    renderers.ffmpeg(["-i", i["path"], "-i", dm, "-filter_complex",
                                      "[0:v]scale=-2:480,setsar=1[a];[1:v]scale=-2:480,setsar=1[b];[a][b]hstack=inputs=2,format=yuv420p[o]",
                                      "-map", "[o]", "-an", "-c:v", "libx264", "-crf", "20", d], 600)
                    out.append({"path": d})
                    continue
                body = {"model": "h3", "prompt": "", "refs": [self.h["to_ref"](self.user, i["path"])], "ctlcheck": True, "session": self.session,
                        "override": {"control": v.get("control") or "pose", "control_people": v.get("control_people") or 2}}
                out.append({"path": self._job(node, body, "preview", V)})
            return out, "%d preview%s" % (len(out), "s" if len(out) > 1 else "")
        if t == "split":
            mx = max(4.0, float(v.get("max") or 15))
            ov = max(0.0, min(2.0, float(v.get("overlap") or 0)))
            for i in src:
                dur = renderers.media_seconds(i["path"])
                k = max(1, min(int(math.ceil((dur - ov) / max(0.5, mx - ov) - 1e-6)), int((dur - ov) // max(0.5, 4 - ov)) or 1))
                seg = (dur + (k - 1) * ov) / k            # every piece = seg long; piece n starts where piece n-1 ends minus ov
                for s in range(k):
                    self.check()
                    d = self.tmp("_%02d.mp4" % s)
                    renderers.ffmpeg(["-ss", "%.3f" % (s * (seg - ov)), "-i", i["path"], "-t", "%.3f" % seg, "-c:v", "libx264", "-crf", "16",
                                      "-preset", "fast", "-c:a", "aac", d], 900)
                    out.append({"path": d, "overlap": ov if k > 1 else 0})
            return out, "%d piece%s · %.1f s each%s" % (len(out), "s" if len(out) > 1 else "", seg, " · %.1f s overlap" % ov if ov and k > 1 else "")
        if t == "join":
            first = core.media_size(src[0]["path"]) or (1280, 720)
            w, hgt, fps = first[0] // 2 * 2, first[1] // 2 * 2, str(v.get("fps") or "24")
            parts = []
            for i in src:
                self.check()
                d = self.tmp("_n.mp4")
                a = [] if _has_audio(i["path"]) else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                renderers.ffmpeg(["-i", i["path"]] + a + ["-vf", "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=%s"
                                                         % (w, hgt, w, hgt, fps), "-map", "0:v:0", "-map", "%d:a:0" % (1 if a else 0),
                                                         "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
                                                         "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", d], 1800)
                parts.append(d)
            mode = v.get("xfade") or "auto"
            xf = float(v.get("xfade_secs") or 0.5) if mode == "fade" else (float(src[0].get("overlap") or 0) if mode == "auto" else 0)
            d = self.tmp(".mp4")
            if xf > 0 and len(parts) > 1:              # crossfade every seam over the overlap (video xfade + audio acrossfade)
                durs = [renderers.media_seconds(p) for p in parts]
                xf = min(xf, min(durs) / 2)
                args, fv, fa, off = [], [], [], 0.0
                for p in parts:
                    args += ["-i", p]
                lv, la = "[0:v]", "[0:a]"
                for k in range(1, len(parts)):
                    off += durs[k - 1] - xf
                    fv.append("%s[%d:v]xfade=transition=fade:duration=%.3f:offset=%.3f[v%d]" % (lv, k, xf, off, k))
                    fa.append("%s[%d:a]acrossfade=d=%.3f[a%d]" % (la, k, xf, k))
                    lv, la = "[v%d]" % k, "[a%d]" % k
                renderers.ffmpeg(args + ["-filter_complex", ";".join(fv + fa), "-map", lv, "-map", la, "-c:v", "libx264", "-crf", "16",
                                         "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", d], 1800)
                return [{"path": d}], "%d clips · %.2f s crossfades" % (len(parts), xf)
            lst = self.tmp(".txt")
            with open(lst, "w", encoding="utf-8") as f:
                f.write("".join("file '%s'\n" % p.replace("\\", "/") for p in parts))
            renderers.ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", d], 900)
            return [{"path": d}], "%d clips joined" % len(parts)
        if t == "extract_audio":
            for i in src:
                if not _has_audio(i["path"]):
                    raise RuntimeError("that clip has no sound")
                d = self.tmp(".m4a")
                renderers.ffmpeg(["-i", i["path"], "-vn", "-c:a", "aac", "-b:a", "192k", d], 600)
                out.append({"path": d})
            return out, ""
        if t == "set_audio":
            aud = [i for i in self.ins(node, "audio") if i.get("path")]
            if not aud:
                raise RuntimeError("nothing wired into 'audio'")
            vol = float(v.get("vol") or 1.0)
            for k, i in enumerate(src):
                a = aud[min(k, len(aud) - 1)]["path"]
                d = self.tmp(".mp4")
                if v.get("how") == "mix" and _has_audio(i["path"]):
                    renderers.ffmpeg(["-i", i["path"], "-i", a, "-filter_complex", "[1:a]volume=%.2f[b];[0:a][b]amix=inputs=2:duration=first[a]" % vol,
                                      "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", d], 900)
                else:
                    renderers.ffmpeg(["-i", i["path"], "-i", a, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                                      "-af", "volume=%.2f" % vol, "-shortest", d], 900)
                out.append({"path": d})
            return out, ""
        if t == "upscale":
            f = float(v.get("factor") or 2)
            for i in src:
                img = core.kind_of(i["path"]) == I
                d = self.tmp(".png" if img else ".mp4")
                renderers.ffmpeg(["-i", i["path"], "-vf", "scale=trunc(iw*%.2f/2)*2:trunc(ih*%.2f/2)*2:flags=lanczos" % (f, f)] +
                                 ([] if img else ["-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "copy"]) + [d], 1800)
                out.append({"path": d})
            return out, "%sx" % v.get("factor")
        if t == "sbs":
            hgt = int(v.get("height") or 768) // 2 * 2
            if len(src) == 1:
                return src, "one picture — passed through"
            d = self.tmp(".png")
            args, fl = [], []
            for k, i in enumerate(src):
                args += ["-i", i["path"]]
                fl.append("[%d:v]scale=-2:%d,setsar=1[v%d]" % (k, hgt, k))
            fl.append("%shstack=inputs=%d" % ("".join("[v%d]" % k for k in range(len(src))), len(src)))
            renderers.ffmpeg(args + ["-filter_complex", ";".join(fl), "-frames:v", "1", d], 300)
            return [{"path": d}], "%d pictures" % len(src)
        if t == "save":
            stem = re.sub(r"[^A-Za-z0-9_-]+", "_", str(v.get("name") or "flow"))[:30].strip("_") or "flow"
            for i in src:
                p = i["path"]
                if os.path.dirname(os.path.abspath(p)) != os.path.abspath(core.LIB):
                    name = core.new_name("flow_" + stem, os.path.splitext(p)[1].lower())
                    shutil.copy2(p, os.path.join(core.LIB, name))
                    core.index_add(name, {"model": "flow", "prompt": "Node Flow · %s" % self.g.get("name", ""), "job": self.id,
                                          "created": time.time(), "user": self.user or "owner",
                                          **({"session": self.session} if self.session else {})})
                    p = os.path.join(core.LIB, name)
                out.append({"path": p})
            return out, "%d saved" % len(out)
        raise RuntimeError("unknown node %s" % t)

    def go(self):
        try:
            order = topo(self.g["nodes"], self.g["links"])
            by = {n["id"]: n for n in self.g["nodes"]}
            for nid in order:
                self.check()
                node = by[nid]
                spec = CATALOG.get(node["type"])
                if not spec:
                    raise RuntimeError("unknown node type %s" % node["type"])
                self.nodes[nid].update(status="running", note="")
                try:
                    items, note = self.engine(node, spec) if spec.get("model") else self.tool(node, node["type"])
                except Stop:
                    raise
                except Exception as e:
                    self.nodes[nid].update(status="error", note=str(e)[:300])
                    raise RuntimeError("%s: %s" % (spec["label"], str(e)[:300]))
                self.out(nid, items, note)
            self.status = "done"
        except Stop:
            self.status = "stopped"
            for s in self.nodes.values():
                if s["status"] in ("running", "waiting"):
                    s["status"] = "stopped" if s["status"] == "running" else "waiting"
        except Exception as e:
            self.status, self.error = "error", str(e)[:400]
        self.finished = time.time()

    def public(self):
        return {"id": self.id, "status": self.status, "error": self.error, "nodes": self.nodes, "graph": self.g.get("id"),
                "name": self.g.get("name"), "started": self.started, "finished": self.finished}


def validate(g):
    by = {n["id"]: n for n in g.get("nodes") or []}
    for l in g.get("links") or []:
        a, b = by.get(l["from"][0]), by.get(l["to"][0])
        if not a or not b:
            raise ValueError("a wire points at a missing node")
    return True


def register(app, hk):
    """hk: uid, my_file(name), my_ref(name), static(fn), session(sid), submit(user, body)->(job, err, busy), job(jid),
    cancel(jid), to_ref(user, path)->ref name, text_ref(user, text)->ref name."""
    from flask import abort, jsonify, request, send_file

    @app.route("/flow")
    def flow_page():
        return hk["static"]("flow.html")

    @app.route("/api/flow/catalog")
    def flow_catalog():
        return jsonify({"nodes": catalog(), "templates": [dict(id=t["id"], name=t["name"], desc=t["desc"], graph=_tpl_graph(t)) for t in TEMPLATES]})

    @app.route("/api/flow/graphs", methods=["GET", "POST"])
    def flow_graphs():
        if request.method == "POST":
            g = request.get_json(silent=True) or {}
            try:
                validate(g)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            return jsonify(save_graph(hk["uid"](), g))
        return jsonify({"graphs": list_graphs(hk["uid"]())})

    @app.route("/api/flow/graphs/<gid>", methods=["GET"])
    def flow_graph(gid):
        p = os.path.join(_udir(hk["uid"]()), _gid(gid) + ".json")
        if not os.path.isfile(p):
            abort(404)
        return jsonify(core.load_json(p, {}))

    @app.route("/api/flow/graphs/<gid>/delete", methods=["POST"])
    def flow_graph_delete(gid):
        p = os.path.join(_udir(hk["uid"]()), _gid(gid) + ".json")
        if os.path.isfile(p):
            os.remove(p)
        return jsonify({"ok": True})

    @app.route("/api/flow/run", methods=["POST"])
    def flow_run():
        body = request.get_json(silent=True) or {}
        g = body.get("graph") or {}
        u = hk["uid"]()
        with _RLOCK:
            if any(r.user == u and r.status == "running" for r in RUNS.values()):
                return jsonify({"error": "a flow is already running — stop it or wait"}), 409
        try:
            validate(g)
            topo(g["nodes"], g["links"])
        except (ValueError, KeyError) as e:
            return jsonify({"error": str(e)}), 400
        for n in g["nodes"]:                    # resolve chosen files now (ownership checks need this request)
            vals = n.setdefault("values", {})
            src = vals.get("file")
            if CATALOG.get(n["type"], {}).get("form") == "file" and src:
                kind, _, name = str(src).partition(":")
                name = os.path.basename(name)
                if kind == "lib" and hk["my_file"](name):
                    vals["_path"] = core.in_dir(core.LIB, name)
                elif kind == "ref" and hk["my_ref"](name):
                    vals["_path"] = core.in_dir(core.REFS, name)
        r = Run(hk, u, hk["session"](body.get("session")), g)
        with _RLOCK:
            RUNS[r.id] = r
            for k in [k for k, x in RUNS.items() if x.finished and time.time() - x.finished > 86400]:
                RUNS.pop(k, None)
        threading.Thread(target=r.go, daemon=True, name="flow-" + r.id).start()
        return jsonify(r.public())

    @app.route("/api/flow/runs/<rid>")
    def flow_run_get(rid):
        r = RUNS.get(rid)
        if not r or r.user != hk["uid"]():
            abort(404)
        return jsonify(r.public())

    @app.route("/api/flow/runs")
    def flow_runs():
        u = hk["uid"]()
        return jsonify({"runs": [r.public() for r in sorted(RUNS.values(), key=lambda x: -x.started) if r.user == u][:10]})

    @app.route("/api/flow/runs/<rid>/stop", methods=["POST"])
    def flow_run_stop(rid):
        r = RUNS.get(rid)
        if not r or r.user != hk["uid"]():
            abort(404)
        r.stop = True
        if r.job:
            hk["cancel"](r.job)
        return jsonify(r.public())

    @app.route("/flow/file/<rid>/<name>")
    def flow_file(rid, name):
        r = RUNS.get(rid)
        if not r or r.user != hk["uid"]():
            abort(404)
        p = os.path.join(r.dir, os.path.basename(name))
        if not os.path.isfile(p):
            abort(404)
        return send_file(p, conditional=True)
