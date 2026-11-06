"""FREEFIELD STUDIO — neuregex/freefield's 120 Higgsfield-style apps, run natively on the lab's local ComfyUI.

Every app is a folder in <freefield>/apps (engines.freefield(), downloaded by Setup) with an app.json manifest + a ComfyUI API-format workflow. The manifest
says where each form value goes (bind: node + field, optional {template}); select options and presets carry extra
`sets` (the LoRA file that goes with a style...). This module is a Python port of freefield's server/runner.ts —
no Node server, Comfy SDK, Modal gateway or proxy: the graph goes straight to ComfyUI :8188 through comfy.py.

Results land in the lab library (core.LIB + core.index_add) like any other render. GPU etiquette: one job at a
time, waits while another render owns the GPU (core.rendering), takes the render lock, frees VRAM when the app's
model set changes (what freefield's gateway /prepare did).
"""
import copy
import json
import os
import random
import re
import shutil
import threading
import time
import uuid

import requests

import comfy
import console
import core

import engines

ROOT = (core.CONFIG.get("freefield_root") if isinstance(core.CONFIG, dict) else None) or engines.freefield()
APPS_DIR = os.path.join(ROOT, "apps")
# The lab's own app packs (never inside the freefield download, so updating it never clashes): OpenField's Object/Stage/
# Seam Doctor/Era/Scene live in server/studio_packs/openfield/apps. A pack app id must not repeat a freefield id.
PACKS_ROOT = engines.studio_packs()
EXTRA_APP_DIRS = [os.path.join(PACKS_ROOT, "openfield", "apps")]
DATA = os.path.join(core.DATA, "freefield")
INBOX = os.path.join(DATA, "in")              # uploads for a run (ComfyUI copies them into its input dir)
JOBS_FILE = os.path.join(DATA, "jobs.json")
GRAPHS = os.path.join(DATA, "graphs")         # the exact API graph of every run ("Download workflow" / "Open in ComfyUI")
MODELS3D = os.path.join(DATA, "models3d")     # GLBs from Object (the library only holds image/video/audio)
def _models_root():
    """Where ComfyUI reads model weights: mml_config "comfy_models", Comfy Desktop's shared folder, else the engine's own."""
    c = core.CONFIG.get("comfy_models") if isinstance(core.CONFIG, dict) else None
    if c:
        return c
    shared = os.path.join(comfy.COMFY_SHARED, "models")
    own = os.path.join(comfy.COMFY_ROOT, "ComfyUI", "models")
    return shared if os.path.isdir(shared) or not os.path.isdir(own) else own


MODELS_ROOT = _models_root()
MODEL_DIRS = {"diffusion_models", "text_encoders", "vae", "loras", "checkpoints", "clip_vision", "latent_upscale_models",
              "upscale_models", "model_patches", "geometry_estimation", "background_removal", "frame_interpolation",
              "audio_encoders", "embeddings", "detection"}
FILE_TYPES = ("image", "video", "audio")
HEAVY_GB = 8                                  # apps above this evict the Ollama brain before rendering
for _d in (DATA, INBOX, GRAPHS, MODELS3D):
    os.makedirs(_d, exist_ok=True)


class InputError(ValueError):
    pass


# ── one feature, one place ────────────────────────────────────────────────────────────────────────────────────────
# Studio apps that duplicate a lab tool on the SAME model, where the lab's version does more → hidden from Studio.
SUPERSEDED = {
    "h3-video": "Media Lab → Video (MiniMax H3: same model, plus r2v, story, sing, swap, control, extend)",
    "h3-photo": "Media Lab → Animate Photo (MiniMax H3 image → video)",
    "extend-video": "Media Lab → Continue My Clip (MiniMax H3 extend, multi-beat)",
    "music": "Media Lab → Song (MiniMax Music 3 with lyric writing)",
}
DEV_ONLY = {"smoke", "smoke-invert"}          # pipeline tests, not features (?dev=1 shows them)
# Studio engines that REPLACED a weaker built-in lab step (the lab calls them through run_inline; fallback = old way).
POWERS = {
    "remove-bg": "the lab's Cutout / “remove the background” (was a Qwen-Image diffusion edit)",
    "upscale": "the lab's image Upscale option (was a plain lanczos resize)",
    "upscale-video": "the lab's video Upscale option (was a plain lanczos resize)",
    "smooth": "the lab's 48 / 60 fps smooth option (was ffmpeg motion interpolation)",
    "recast": "the lab's Put Me In This Clip (was Wan VACE swap); long clips run in 5 s passes",
    "motion-transfer": "the lab's Copy The Movement when one character picture is attached (was H3 pose control)",
    "talking": "the lab's Talking Photo for recordings up to 20 s (was H3 speak)",
    "camera-copy": "the lab's Copy This Camera Move (was H3 reference video)",
    "mixed-media": "the lab's Re-imagine My Clip when you name one of its looks (was H3 canny control)",
    "edit": "the lab's Restyle Photo and single-photo edits (was Qwen-Image edit)",
}


def visible(app_id, dev=False):
    return app_id not in SUPERSEDED and (dev or app_id not in DEV_ONLY)


# ── catalog ──────────────────────────────────────────────────────────────────────────────────────────────────────
_CAT = {"sig": None, "apps": {}}
_CAT_LOCK = threading.Lock()


def _app_dirs():
    return [APPS_DIR] + [d for d in EXTRA_APP_DIRS if os.path.isdir(d)]


def _sig():
    sig = []
    for root in _app_dirs():
        try:
            sig.append(max(os.path.getmtime(os.path.join(root, d, "app.json")) for d in os.listdir(root)
                           if os.path.isfile(os.path.join(root, d, "app.json"))))
        except (OSError, ValueError):
            sig.append(None)
    return tuple(sig)


def apps():
    """id → manifest (+ _dir). Reloaded when any app.json changes (git pull / pack edit). freefield first; a pack app
    never replaces a freefield app with the same id."""
    with _CAT_LOCK:
        s = _sig()
        if s != _CAT["sig"]:
            out = {}
            for root in _app_dirs():
                for d in sorted(os.listdir(root)) if os.path.isdir(root) else []:
                    p = os.path.join(root, d, "app.json")
                    try:
                        with open(p, encoding="utf-8") as f:
                            a = json.load(f)
                    except (OSError, ValueError):
                        continue
                    if a.get("id") == d and d not in out:
                        a["_dir"] = os.path.join(root, d)
                        out[d] = a
            _CAT.update(sig=s, apps=out)
        return _CAT["apps"]


def get(app_id):
    a = apps().get(str(app_id or ""))
    if not a:
        raise InputError("no such app: %s" % app_id)
    return a


def workflow(a):
    if not a.get("workflow"):
        raise InputError("%s has no workflow yet" % a["id"])
    with open(os.path.join(a["_dir"], a["workflow"]), encoding="utf-8") as f:
        return json.load(f)


# ── readiness: are the models + node classes on this PC's ComfyUI? ─────────────────────────────────────────────────
_QUANT = re.compile(r"[_-](int8_convrot|int8|fp8_e4m3fn_scaled|fp8_e4m3fn|fp8_scaled|fp8_mixed|fp8|nvfp4_awq|nvfp4|"
                    r"bf16|fp16|fp32|w4a8_gptq|w4a8|gguf|q[0-9]_k_[ms]|pruned)", re.I)
_ENGINE = {"t": 0, "nodes": None, "models": {}, "version": None}
_ENGINE_TTL = 60


def _stem(name):
    n = os.path.splitext(os.path.basename(name))[0].lower()
    return _QUANT.sub("", n)


def _engine(refresh=False):
    if not refresh and time.time() - _ENGINE["t"] < _ENGINE_TTL and _ENGINE["nodes"] is not None:
        return _ENGINE
    if not comfy.up():
        _ENGINE.update(t=time.time(), nodes=None, models={}, version=None)
        return _ENGINE
    try:
        nodes = set(requests.get(comfy.BASE + "/object_info", timeout=60).json())
    except Exception:
        nodes = None
    try:
        ver = (requests.get(comfy.BASE + "/system_stats", timeout=6).json().get("system") or {}).get("comfyui_version")
    except Exception:
        ver = None
    _ENGINE.update(t=time.time(), nodes=nodes, models={}, version=ver)
    return _ENGINE


def _have(folder):
    m = _ENGINE["models"]
    if folder not in m:
        m[folder] = {x.replace("\\", "/").split("/")[-1]: x for x in comfy.models(folder)}
    return m[folder]


def resolve_model(mdl):
    """→ (name ComfyUI knows it by, how) — how: 'exact' | 'override' | 'alias' (same model, other quant) | None."""
    base = mdl["file"].split("/")[-1]
    have = _have(mdl["dir"])
    if base in have:
        return have[base], "exact"
    ov = core.MODEL_OVERRIDES.get(base)
    if ov and ov in have:
        return have[ov], "override"
    st = _stem(base)
    for k, v in have.items():
        if _stem(k) == st:
            return v, "alias"
    return None, None


def readiness(a, refresh=False):
    e = _engine(refresh)
    if e["nodes"] is None:
        return {"state": "engine_down", "label": "ComfyUI is off", "missing": [], "gb": 0, "nodes": [], "aliases": {}}
    missing, aliases = [], {}
    wf_text = None
    for m in a.get("models") or []:
        name, how = resolve_model(m)
        if not name:
            if m.get("optional") and wf_text is None:
                try:
                    with open(os.path.join(a["_dir"], a.get("workflow") or ""), encoding="utf-8") as f:
                        wf_text = f.read()
                except OSError:
                    wf_text = ""
            # "optional" (e.g. the Gemma prompt enhancer, off by default) still has a loader in the graph, and ComfyUI
            # validates every loader → it is needed whenever the workflow names the file
            if not m.get("optional") or m["file"].split("/")[-1] in wf_text:
                missing.append({"repo": m["repo"], "file": m["file"], "dir": m["dir"], "gb": m["gb"],
                                "license": m.get("license", ""), "gated": bool(m.get("gated"))})
        elif how != "exact":
            aliases[m["file"].split("/")[-1]] = name
    nodes = []
    if a.get("workflow"):
        try:
            nodes = sorted({n.get("class_type") for n in workflow(a).values() if n.get("class_type") not in e["nodes"]})
        except (OSError, ValueError):
            nodes = ["(workflow unreadable)"]
    if a.get("native"):                           # pack apps that build graphs in Python: declared nodes + bundled graphs
        need = set(a.get("requires_nodes") or [])
        for gf in a.get("graphs") or []:
            try:
                with open(os.path.join(a["_dir"], gf), encoding="utf-8") as f:
                    need |= {n.get("class_type") for n in json.load(f).values()}
            except (OSError, ValueError):
                need.add("(%s unreadable)" % gf)
        nodes = sorted(set(nodes) | {n for n in need if n and n not in e["nodes"]})
    gb = round(sum(m["gb"] for m in missing), 2)
    if a.get("status") != "ready":
        state, label = "draft", "draft"
    elif nodes:
        pack = any(n.startswith(("LTX", "CrossView", "VHS_")) for n in nodes)
        state, label = ("needs_nodes", "needs node pack") if pack else ("needs_engine", "needs ComfyUI update")
    elif missing:
        state, label = "needs_models", "needs %.1f GB" % gb
    else:
        state, label = "ready", "ready"
    return {"state": state, "label": label, "missing": missing, "gb": gb, "nodes": nodes, "aliases": aliases}


def summary(a, ready=None):
    """The card the grid draws."""
    r = ready or readiness(a)
    vram = a.get("vram") or {}
    return {"id": a["id"], "name": a["name"], "section": a["section"], "summary": a.get("summary", ""),
            "rebuilds": a.get("higgsfield_feature", ""), "pack": a["pack"], "status": a["status"],
            "modes": a.get("modes"), "mode_label": a.get("mode_label"),
            "inputs": [i["type"] for i in a.get("inputs") or []],
            "outputs": [o["type"] for o in a.get("outputs") or []],
            "model": _model_line(a), "peak_gb": vram.get("peak_gb"), "download_gb": round(sum(m["gb"] for m in a.get("models") or []), 1),
            "ready": r, "est_s": estimate(a["id"]), "origin": a.get("origin", "freefield"), "page": a.get("page")}


# ── render-time estimates (OpenField estimate.ts): the median of this PC's own finished runs of the same app ─────────
def estimate(app_id, preset=None):
    """Median GPU seconds of the last finished runs of this app (same preset when there are ≥2 of those). None = no runs yet."""
    with _JLOCK:
        done = [JOBS[i] for i in ORDER[-400:] if JOBS.get(i, {}).get("app") == app_id and JOBS[i].get("status") == "done" and JOBS[i].get("secs")]
    same = [j for j in done if (j.get("preset") or None) == (preset or None)]
    pool = (same if len(same) >= 2 else done)[-9:]
    if not pool:
        return None
    s = sorted(j["secs"] for j in pool)
    m = len(s) // 2
    return round(s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2)


# ── your own LoRAs (OpenField loras.ts): a file's family comes from its tensor keys, not its name ───────────────────
LORA_MAX = 4
_TASK_LORA = re.compile(r"ic-lora|lightning|turbo|lightx2v|distill|fasth3|marigold|multiple-angles|causvid|dpo|critic|consistency", re.I)
_LORA_CACHE = {}
FAMILY_LABEL = {"ltx": "LTX", "qwen": "Qwen-Image", "flux2": "FLUX.2 / Klein", "flux": "FLUX.1", "wan": "Wan", "h3": "MiniMax H3", "other": "another model"}


def _lora_family(keys, name=""):
    lora = any(re.search(r"\.(lora_[AB]|lora_up|lora_down|lora\.(up|down))(\.[a-z]+)?\.weight$", k) or k.endswith(".alpha") for k in keys)
    if not lora:
        return "not-lora"
    has = lambda rx: any(re.search(rx, k) for k in keys)
    if re.search(r"minimax[_-]?h3|mmh3", name, re.I):
        return "h3"
    if has(r"(double|single)_stream_modulation"):
        return "flux2"
    if has(r"double_blocks[._]\d+[._]"):
        return "flux"
    if has(r"transformer_blocks[._]\d+[._](attn[._]add_[qkv]_proj|img_mlp|txt_mlp|img_mod)"):
        return "qwen"
    if has(r"transformer_blocks[._]\d+[._](attn1|attn2|audio_attn|ff)[._]"):
        return "ltx"
    if has(r"(^|[._])blocks[._]\d+[._](cross_attn|self_attn)[._]"):
        return "wan"
    return "other"


def _lora_header(path):
    import struct
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n <= 0 or n > 100 * 1024 * 1024:
            raise ValueError("bad header")
        h = json.loads(f.read(n))
    meta = h.pop("__metadata__", {}) or {}
    trig = None
    try:
        freq = json.loads(meta.get("ss_tag_frequency") or "{}")
        tags = sorted((kv for t in freq.values() for kv in t.items()), key=lambda kv: -kv[1])
        trig = tags[0][0].strip() if tags and len(tags[0][0].strip()) <= 40 else None
    except Exception:
        pass
    return list(h.keys()), trig


def user_loras():
    """Every LoRA in ComfyUI's loras folder that is yours to add (task LoRAs like IC-LoRAs / distills left out) + family."""
    out = []
    root = os.path.join(MODELS_ROOT, "loras")
    for name in sorted(comfy.models("loras")):
        base = name.replace("\\", "/").split("/")[-1]
        if _TASK_LORA.search(base) or not base.lower().endswith(".safetensors"):
            continue
        p = os.path.join(root, name)
        try:
            st = os.stat(p)
        except OSError:
            out.append({"name": name, "family": None})
            continue
        hit = _LORA_CACHE.get(p)
        if not hit or hit[0] != st.st_mtime:
            try:
                keys, trig = _lora_header(p)
                hit = (st.st_mtime, _lora_family(keys, base), trig)
            except Exception:
                hit = (st.st_mtime, None, None)
            _LORA_CACHE[p] = hit
        if hit[1] == "not-lora":
            continue
        out.append({"name": name, "family": hit[1], **({"trigger": hit[2]} if hit[2] else {})})
    return out


def app_family(a):
    """The model family an app's own LoRAs must match (None = this app takes no extra LoRAs)."""
    if a.get("native") or not a.get("workflow"):
        return None
    for m in a.get("models") or []:
        if m["dir"] != "diffusion_models":
            continue
        f = m["file"].split("/")[-1].lower()
        for k, fam in (("ltx", "ltx"), ("qwen_image", "qwen"), ("flux", "flux2"), ("klein", "flux2"), ("minimax_h3", "h3"), ("wan", "wan")):
            if k in f:
                return fam
    return None


def apply_loras(a, graph, picks):
    """Chain LoraLoaderModelOnly after every UNETLoader of the app's model (OpenField's 'Your LoRAs'). Refuses a LoRA
    made for another family with a readable error — loaded on the wrong model it would silently do nothing."""
    if not picks:
        return graph
    fam = app_family(a)
    if not fam:
        raise InputError("%s takes no extra LoRAs" % a["name"])
    if not isinstance(picks, list) or len(picks) > LORA_MAX:
        raise InputError("up to %d of your own LoRAs per run" % LORA_MAX)
    known = {l["name"]: l for l in user_loras()}
    chain = []
    for p in picks:
        name = str((p or {}).get("name") or "")
        if not name:
            continue
        l = known.get(name)
        if not l:
            raise InputError("ComfyUI has no LoRA named %s (put it in models/loras)" % name)
        if l["family"] and l["family"] != fam:
            raise InputError("%s is made for %s; %s runs %s, so it would do nothing there" % (name, FAMILY_LABEL.get(l["family"], l["family"]), a["name"], FAMILY_LABEL[fam]))
        try:
            s = max(-2.0, min(2.0, float(p.get("strength", 1))))
        except (TypeError, ValueError):
            s = 1.0
        chain.append((name, s))
    if not chain:
        return graph
    unets = [k for k, n in graph.items() if n.get("class_type") == "UNETLoader"]
    if not unets:
        raise InputError("%s has no model loader to add a LoRA to" % a["name"])
    for u in unets:
        prev = [u, 0]
        for i, (name, s) in enumerate(chain):
            nid = "%s_ulora%d" % (u, i)
            graph[nid] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": prev, "lora_name": name, "strength_model": s}}
            prev = [nid, 0]
        first = "%s_ulora0" % u
        for k, n in graph.items():
            if k.startswith(u + "_ulora"):
                continue
            for f, v in (n.get("inputs") or {}).items():
                if isinstance(v, list) and len(v) == 2 and v[0] == u and v[1] == 0:
                    n["inputs"][f] = prev
        graph[first]["inputs"]["model"] = [u, 0]
    return graph


def _model_line(a):
    names = []
    for m in a.get("models") or []:
        if m["dir"] in ("diffusion_models", "checkpoints"):
            n = re.sub(r"[_-](int8|fp8|bf16|fp16|convrot|scaled|e4m3fn|distilled|transformer|comfy).*$", "", os.path.splitext(m["file"].split("/")[-1])[0], flags=re.I)
            if n not in names:
                names.append(n)
    return " + ".join(names[:2])


def detail(a):
    """Everything the app panel needs (inputs with options, presets, models, credits)."""
    # deep copy: the pops below must never touch the cached manifest (they once stripped every bind → runs used the
    # template's sample inputs after anyone opened the app panel)
    d = copy.deepcopy({k: v for k, v in a.items() if not k.startswith("_") and k not in ("test", "source")})
    d["ready"] = readiness(a)
    d["source"] = a.get("source")
    d["powers"] = POWERS.get(a["id"])
    d["superseded"] = SUPERSEDED.get(a["id"])
    d["est_s"] = estimate(a["id"])
    fam = app_family(a)
    d["lora_family"] = fam
    d["lora_label"] = FAMILY_LABEL.get(fam) if fam else None
    d.pop("graphs", None)
    d.pop("native", None)
    for i in d.get("inputs") or []:
        i.pop("bind", None)
        for o in i.get("options") or []:
            o.pop("sets", None)
    for p in d.get("presets") or []:
        p.pop("sets", None)
    return d


# ── the runner (port of server/runner.ts) ──────────────────────────────────────────────────────────────────────────
def _num(i, raw):
    try:
        n = float(raw)
    except (TypeError, ValueError):
        raise InputError("%s: expected a number" % i["id"])
    if n != n or n in (float("inf"), float("-inf")):
        raise InputError("%s: expected a number" % i["id"])
    if i.get("min") is not None and n < i["min"]:
        raise InputError("%s: must be ≥ %s" % (i["id"], i["min"]))
    if i.get("max") is not None and n > i["max"]:
        raise InputError("%s: must be ≤ %s" % (i["id"], i["max"]))
    if i["type"] == "seed" or (float(n).is_integer() and isinstance(i.get("default"), int) and not isinstance(i.get("default"), bool)):
        return int(n)
    return n


def _picks(i, raw):
    if isinstance(raw, list):
        lst = raw
    elif isinstance(raw, str) and raw.strip().startswith("["):
        try:
            lst = json.loads(raw)
        except ValueError:
            raise InputError("%s: expected a list" % i["id"])
    else:
        lst = [] if raw in ("", None) else [raw]
    out = []
    for r in lst:
        hit = next((o for o in i.get("options") or [] if str(o["value"]) == str(r)), None)
        if not hit:
            raise InputError('%s: "%s" is not one of the options' % (i["id"], r))
        v = str(hit["value"])
        if v and v not in out:
            out.append(v)
    mx = (i.get("multiple") or {}).get("max")
    if mx and len(out) > mx:
        raise InputError("%s: at most %d" % (i["id"], mx))
    return out


def _coerce(i, raw):
    t = i["type"]
    if t in ("number", "slider", "seed"):
        return _num(i, raw)
    if t == "toggle":
        return raw is True or str(raw).lower() in ("true", "1", "on")
    if t == "select":
        if i.get("multiple"):
            return _picks(i, raw)
        hit = next((o for o in i.get("options") or [] if o["value"] == raw or str(o["value"]) == str(raw)), None)
        if not hit:
            raise InputError('%s: "%s" is not one of the options' % (i["id"], raw))
        return hit["value"]
    return raw if raw is None else str(raw)


def resolve_values(a, values):
    """Defaults, seed −1 → random, types, required. File inputs stay {'path': ...} dicts."""
    out = {}
    for i in a.get("inputs") or []:
        v = values.get(i["id"])
        empty_is_option = i["type"] == "select" and (bool(i.get("multiple")) or any(o.get("value") == "" for o in i.get("options") or []))
        if v is None or (v == "" and not empty_is_option):
            v = i.get("default")
        if i["type"] == "seed" and (v is None or str(v) == "-1"):
            v = random.randrange(2 ** 48)
        if v is None:
            if i.get("required") or i["type"] in FILE_TYPES:
                raise InputError("%s (%s): required" % (i.get("label", i["id"]), i["id"]))
            continue
        if i["type"] in FILE_TYPES:
            if not (isinstance(v, dict) and v.get("path") and os.path.isfile(v["path"])):
                raise InputError("%s: expected a file" % i["id"])
            mx = (i.get("limits") or {}).get("max_mb")
            if mx and os.path.getsize(v["path"]) > mx * 1e6:
                raise InputError("%s: file is over %s MB" % (i["id"], mx))
            out[i["id"]] = v
        else:
            out[i["id"]] = _coerce(i, v)
    return out


def join_picks(i, lst):
    items = [str(x) for x in (lst if isinstance(lst, list) else []) if str(x)]
    if not items:
        return ""
    m = i.get("multiple") or {}
    return "%s%s%s" % (m.get("prefix", ""), m.get("join", ", ").join(items), m.get("suffix", ""))


def text_values(a, values):
    out = dict(values)
    for i in a.get("inputs") or []:
        if i.get("multiple") and i["id"] in values:
            out[i["id"]] = join_picks(i, values[i["id"]])
    return out


_PH = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def render_template(tpl, values):
    def sub(m):
        v = values.get(m.group(1))
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, dict):
            return v.get("name", "")
        return str(v)
    s = _PH.sub(sub, tpl)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return re.sub(r",$", "", s)


def set_value(v, values):
    return render_template(v, values) if isinstance(v, str) and _PH.search(v) else v


def _set(graph, node, field, value):
    n = graph.get(str(node))
    if not n:
        raise InputError("workflow has no node %s" % node)
    n.setdefault("inputs", {})[field] = value


def apply_inputs(a, values, graph, asset, preset=None):
    """Fill graph from resolved values (+ a preset). asset(file dict) → the name ComfyUI loads."""
    values = text_values(a, values)
    files = {k: asset(v) for k, v in values.items() if isinstance(v, dict) and v.get("path")}
    tv = dict(values, **files)
    for i in a.get("inputs") or []:
        v = tv.get(i["id"])
        if v is None:
            continue
        for b in i.get("bind") or []:
            _set(graph, b["node"], b["field"], render_template(b["template"], tv) if b.get("template") else v)
        if i["type"] == "select" and not i.get("multiple"):
            hit = next((o for o in i.get("options") or [] if o["value"] == values.get(i["id"])), None)
            for s in (hit or {}).get("sets") or []:
                _set(graph, s["node"], s["field"], set_value(s["value"], tv))
    if preset:
        p = next((p for p in a.get("presets") or [] if p["id"] == preset), None)
        if not p:
            raise InputError('preset "%s" does not exist in %s' % (preset, a["id"]))
        for s in p["sets"]:
            _set(graph, s["node"], s["field"], set_value(s["value"], tv))
    return graph


def _orient_canvas(a, graph, vals):
    """LTX apps hard-code a 960×544 LANDSCAPE canvas. A portrait photo on it gets cropped to a band round the face and
    the model just pushes in (Nov 5: Talking Avatar 'zoomed into the face, lips never moved'). Match the canvas to the
    app's picture input — same pixel budget — unless the app lets the user set width/height themselves."""
    bound = {(str(b["node"]), b["field"]) for i in a.get("inputs") or []
             for b in (i.get("bind") or []) + [s for o in i.get("options") or [] for s in o.get("sets") or []]}
    bound |= {(str(s["node"]), s["field"]) for p in a.get("presets") or [] for s in p.get("sets") or []}
    pic = next((vals.get(i["id"]) for i in a.get("inputs") or [] if i["type"] == "image"
                and isinstance(vals.get(i["id"]), dict) and vals[i["id"]].get("path")), None)
    if not pic:
        return
    wh = core.media_size(pic["path"])
    if not wh:
        return
    r = wh[0] / float(wh[1] or 1)
    w, h = (960, 544) if r > 1.15 else ((544, 960) if r < 0.87 else (736, 736))
    for nid, n in graph.items():
        if n.get("class_type") == "EmptyLTXVLatentVideo" and not ({(nid, "width"), (nid, "height")} & bound) \
                and isinstance(n["inputs"].get("width"), int) and isinstance(n["inputs"].get("height"), int):
            n["inputs"]["width"], n["inputs"]["height"] = w, h


def build(a, values, preset=None, asset=None, aliases=None, loras=None):
    """→ (graph, resolved values). asset defaults to the file's base name (dry builds / tests)."""
    vals = resolve_values(a, values)
    g = apply_inputs(a, vals, workflow(a), asset or (lambda f: os.path.basename(f["path"])), preset)
    if aliases:                          # same model, other quant on this PC → point the loaders at it
        for n in g.values():
            for k, v in (n.get("inputs") or {}).items():
                if isinstance(v, str) and v in aliases:
                    n["inputs"][k] = aliases[v]
    apply_loras(a, g, loras)
    _orient_canvas(a, g, vals)
    if comfy.OUT_PREFIX:
        for n in g.values():
            if str(n.get("class_type", "")).startswith("Save") and isinstance((n.get("inputs") or {}).get("filename_prefix"), str):
                n["inputs"]["filename_prefix"] = "%s/ff_%s" % (comfy.OUT_PREFIX, a["id"])
    return g, vals


# ── jobs (one at a time; survive a restart as history) ─────────────────────────────────────────────────────────────
JOBS, ORDER = {}, []
_JLOCK = threading.Lock()
_WAKE = threading.Event()
_LAST_MODELS = [None]


def _public(j):
    return {k: v for k, v in j.items() if not k.startswith("_")}


def _persist():
    with _JLOCK:
        keep = [_public(JOBS[i]) for i in ORDER[-200:] if i in JOBS]
    try:
        core.save_json(JOBS_FILE, keep)
    except Exception:
        pass


def _load():
    for j in core.load_json(JOBS_FILE, []):
        if isinstance(j, dict) and j.get("id"):
            if j.get("status") in ("queued", "running"):
                j.update(status="error", error="the lab restarted during this run")
            JOBS[j["id"]] = j
            ORDER.append(j["id"])


def ready(app_id):
    """True when this Studio app can run on this PC now (used by the lab to pick the better engine)."""
    try:
        return readiness(get(app_id))["state"] == "ready"
    except InputError:
        return False


def run_inline(app_id, values, job, patch=None):
    """Run a Studio app INSIDE the lab's GPU worker (the caller already holds the render lock). values: file inputs as
    {'path': ...}. job: the lab job (progress, live preview and cancel work as for any lab render).
    → list of ComfyUI output entries (fetch them with comfy.fetch)."""
    a = get(app_id)
    r = readiness(a, refresh=True)
    if r["state"] != "ready":
        raise RuntimeError("Studio engine %s isn't ready: %s" % (app_id, r["label"]))
    graph, _ = build(a, values, asset=lambda f: comfy.upload(f["path"]), aliases=r["aliases"])
    if patch:                                     # caller tweaks the built graph (e.g. canvas orientation)
        patch(graph)
    outs, _ = _render(graph, a, job)
    hits = [e for o in a["outputs"] for k in ("images", "videos", "gifs", "audio")
            for e in (outs.get(str(o["node"])) or {}).get(k) or [] if e.get("type", "output") == "output"]
    if not hits:
        raise RuntimeError("%s produced no output" % a["name"])
    return hits


def submit(app_id, values, user="owner", session="", preset=None, loras=None):
    if app_id in SUPERSEDED:
        raise InputError("%s lives in the lab now: %s" % (app_id, SUPERSEDED[app_id]))
    a = get(app_id)
    r = readiness(a, refresh=True)
    if r["state"] == "draft" and not core.CONFIG.get("freefield_drafts"):
        raise InputError("%s is a draft (its workflow hasn't run on a GPU yet)" % a["id"])
    if r["state"] not in ("ready", "draft"):
        raise InputError("%s can't run here yet: %s" % (a["name"], r["label"] + (" — " + ", ".join(r["nodes"][:4]) if r["nodes"] else "")))
    loras = [l for l in (loras or []) if isinstance(l, dict) and l.get("name")]
    if a.get("native"):                                     # pack apps validate their own values
        import ffpack
        ffpack.validate(a, resolve_values(a, values))
    else:
        build(a, values, preset, aliases=r["aliases"], loras=loras)   # validate now, so the form gets the error, not the queue
    jid = "ff" + uuid.uuid4().hex[:10]
    j = {"id": jid, "app": a["id"], "name": a["name"], "section": a["section"], "user": user, "session": session or "",
         "preset": preset, "values": {k: (os.path.basename(v["path"]) if isinstance(v, dict) else v) for k, v in values.items()},
         "_values": values, "_aliases": r["aliases"], "_loras": loras, "loras": [l["name"] for l in loras],
         "status": "queued", "stage": "queued", "created": time.time(), "files": [], "graphs": []}
    with _JLOCK:
        JOBS[jid] = j
        ORDER.append(jid)
    _persist()
    console.emit("LAB", "Studio · %s queued" % a["name"], j)
    _WAKE.set()
    return _public(j)


def cancel(jid):
    j = JOBS.get(jid)
    if not j:
        return False
    if j["status"] == "queued":
        j.update(status="cancelled", stage="")
        _persist()
    elif j["status"] == "running":
        j["_cancel"] = True
    return True


def jobs(user=None, limit=40):
    with _JLOCK:
        js = [JOBS[i] for i in ORDER if i in JOBS and (user is None or JOBS[i].get("user") == user)]
    return [_public(j) for j in js[-limit:]][::-1]


def _worker():
    while True:
        _WAKE.wait(5)
        _WAKE.clear()
        while True:
            with _JLOCK:
                jid = next((i for i in ORDER if JOBS.get(i, {}).get("status") == "queued"), None)
            if not jid:
                break
            _run(JOBS[jid])


def _run(j):
    a = get(j["app"])
    j.update(status="running", started=time.time(), stage="waiting for the GPU")
    _persist()
    t0 = time.time()
    while core.rendering() and time.time() - t0 < core.RENDER_LOCK_MAX_S and not j.get("_cancel"):
        time.sleep(3)
    try:
        if j.get("_cancel"):
            raise comfy.Cancelled()
        core.render_lock(j["id"])
        if not comfy.up():
            j["stage"] = "starting the render engine"
            comfy.ensure()
        heavy = sum(m["gb"] for m in a.get("models") or []) >= HEAVY_GB
        if heavy:
            j["stage"] = "freeing VRAM"
            core.evict_ollama()
        key = sorted(m["file"] for m in a.get("models") or [])
        if _LAST_MODELS[0] is not None and _LAST_MODELS[0] != key:
            comfy.free()                                  # different model set than the last studio run
        _LAST_MODELS[0] = key
        j["stage"] = "uploading inputs"
        if a.get("native"):                               # pack app: Python plans the graphs (OpenField ports)
            import ffpack
            vals = resolve_values(a, j["_values"])
            j["seed"] = next((v for i, v in vals.items() if any(x["id"] == i and x["type"] == "seed" for x in a["inputs"])), None)
            console.emit("LAB", "Studio · %s · rendering" % a["name"], j)
            t0r = time.time()
            j["files"] = ffpack.run(a, j, vals)
            j.update(status="done", secs=round(time.time() - t0r, 1))
        else:
            graph, vals = build(a, j["_values"], j.get("preset"), asset=lambda f: comfy.upload(f["path"]), aliases=j.get("_aliases"),
                                loras=j.get("_loras"))
            j["seed"] = next((v for i, v in vals.items() if any(x["id"] == i and x["type"] == "seed" for x in a["inputs"])), None)
            console.emit("LAB", "Studio · %s · rendering" % a["name"], j)
            outs, secs = _render(graph, a, j)
            j["files"] = _save(outs, a, j, vals)
            j.update(status="done", secs=round(secs, 1))
        try:
            import watermark
            if watermark.enabled() and j["files"]:
                watermark.apply(j["files"], lambda m: console.emit("LAB", m, j, "warn"))
        except Exception:
            pass
    except comfy.Cancelled:
        j.update(status="cancelled", error="cancelled")
    except Exception as e:
        j.update(status="error", error=str(e)[:1500])
    finally:
        core.render_unlock()
        j.update(finished=time.time(), stage="", progress=None)
        j.pop("_cancel", None)
        for k in ("_pv", "_pv_t", "_pv_n"):
            j.pop(k, None)
        console.emit("LAB", "Studio · %s · %s" % (a["name"], j["status"] if j["status"] != "error" else "stopped · " + j.get("error", "")[:80]), j)
        _persist()


def record_graph(j, graph, label=""):
    """Keep the exact API graph a run sent (OpenField 'Open in ComfyUI'): DATA/freefield/graphs/<job>_<n>.json."""
    try:
        n = len(j.setdefault("graphs", []))
        name = "%s_%d.json" % (j["id"], n)
        core.save_json(os.path.join(GRAPHS, name), graph)
        j["graphs"].append({"file": name, "label": label or j.get("name", "workflow")})
    except Exception:
        pass


def _render(graph, a, j, timeout_s=120 * 60, label=""):
    """Submit, follow live progress (comfy._Watch), wait, → ({node: [entries]}, seconds)."""
    if j.get("id"):
        record_graph(j, graph, label)
    watch = comfy._Watch(j, "", graph)
    watch.start()
    watch.ready.wait(3)
    try:
        r = requests.post(comfy.BASE + "/prompt", json={"prompt": graph, "client_id": watch.cid,
                                                        "extra_data": {"preview_method": comfy.preview_method()}}, timeout=30)
        d = r.json()
        if r.status_code != 200 or "prompt_id" not in d:
            try:                                          # keep the rejected graph for debugging
                core.save_json(os.path.join(os.path.dirname(JOBS_FILE), "last_reject.json"), {"app": a["id"], "reply": d, "graph": graph})
            except Exception:
                pass
            raise RuntimeError(_explain(a, d))
        pid, t0 = d["prompt_id"], time.time()
        j["comfy_pid"] = watch.pid = pid
        while True:
            time.sleep(2)
            if j.get("_cancel"):
                comfy.cancel(pid)
                raise comfy.Cancelled()
            if time.time() - t0 > timeout_s:
                comfy.cancel(pid)
                raise RuntimeError("timed out after %d min" % (timeout_s // 60))
            try:
                hist = requests.get(comfy.BASE + "/history/" + pid, timeout=30).json()
            except requests.exceptions.ConnectionError:
                raise comfy.EngineLost("ComfyUI stopped mid-run (crash / out of VRAM / restarted)")
            except Exception:
                continue
            if pid not in hist:
                pg = j.get("progress") or {}
                j["stage"] = "queued in ComfyUI" if comfy._pending(pid) else (
                    (pg.get("what") or "rendering") + (" · %d%%" % pg["pct"] if pg.get("max") else ""))
                continue
            st = hist[pid].get("status") or {}
            if st.get("status_str") != "success":
                if any(m[0] == "execution_interrupted" for m in st.get("messages", [])):
                    raise comfy.Cancelled()
                errs = [m[1] for m in st.get("messages", []) if m[0] == "execution_error"]
                e = errs[0] if errs else {}
                raise RuntimeError("ComfyUI error in %s: %s" % (e.get("node_type", "?"), str(e.get("exception_message", st))[:600]))
            outs = hist[pid].get("outputs") or {}
            return outs, time.time() - t0
    finally:
        watch.stop = True


def _explain(a, d):
    """ComfyUI's validation errors → lines a person can act on (port of explainSubmitError)."""
    files = {m["file"].split("/")[-1] for m in a.get("models") or []}
    lines, missing = [], False
    for node, ent in (d.get("node_errors") or {}).items():
        for x in (ent.get("errors") if isinstance(ent, dict) else ent) or []:
            got = (x.get("extra_info") or {}).get("received_value")
            if x.get("type") == "value_not_in_list" and isinstance(got, str) and got in files:
                missing = True
                lines.append("%s (node %s): model file %s is not installed" % (ent.get("class_type", "node"), node, got))
            else:
                lines.append("%s (node %s): %s %s" % (ent.get("class_type", "node") if isinstance(ent, dict) else "node", node,
                                                       x.get("message", x.get("type", "invalid")), str(x.get("details", ""))[:160]))
    if not lines:
        lines.append(json.dumps(d.get("error") or d)[:400])
    if missing:
        lines.append("Use “Get models” on the app card to download them.")
    return "ComfyUI rejected the workflow: " + " · ".join(lines)


def _save(outs, a, j, vals):
    """Copy every declared output into the lab library + index it."""
    names = []
    prompt = next((str(v) for i, v in vals.items() if isinstance(v, str) and len(v) > 12), a["name"])
    for o in a.get("outputs") or []:
        ent = outs.get(str(o["node"])) or {}
        for e in [x for k in ("images", "videos", "gifs", "audio") for x in ent.get(k) or []]:
            if e.get("type", "output") != "output":
                continue
            ext = os.path.splitext(e.get("filename", ""))[1].lower() or {"image": ".png", "video": ".mp4", "audio": ".flac"}[o["type"]]
            name = core.new_name("ff_%s" % a["id"].replace("-", "_"), ext)
            comfy.fetch(e, os.path.join(core.LIB, name))
            core.index_add(name, {"model": "ff:" + a["id"], "tool": "Studio · " + a["name"], "prompt": prompt[:2000], "job": j["id"],
                                  "created": time.time(), "user": j.get("user") or "owner", "seed": j.get("seed"),
                                  "output": o.get("label", o["type"]), **({"session": j["session"]} if j.get("session") else {})})
            names.append(name)
    if not names:
        raise RuntimeError("the run finished but saved nothing")
    return names


def stash_upload(fs):
    """A browser upload → a file in our inbox (comfy.upload sends it to ComfyUI at run time)."""
    ext = os.path.splitext(fs.filename or "")[1].lower()[:6] or ".bin"
    if not core.kind_of("x" + ext):
        raise InputError("unsupported file type " + ext)
    p = core.safe_path(os.path.join(INBOX, "%s_%s%s" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6], ext)))
    fs.save(p)
    return {"path": p, "name": os.path.basename(p)}


def from_library(name):
    p = core.in_dir(core.LIB, name)
    if not p:
        raise InputError("not in the library: %s" % name)
    return {"path": p, "name": os.path.basename(p)}


# ── model downloads (Hugging Face → ComfyUI-Shared\models\<dir>) ───────────────────────────────────────────────────
DL = {}
_DL_LOCK = threading.Lock()


def _hf_token():
    """The owner's own Hugging Face token: Settings (data/hf_token.txt), HF_TOKEN env, else the `huggingface-cli login`
    token file. Sent only to huggingface.co for gated model downloads; never logged or returned by any route."""
    t = core.read_text(os.path.join(core.DATA, "hf_token.txt"), 200)
    t = t or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if t:
        return t.strip()
    try:
        with open(os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "token"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _dest(m):
    if m["dir"] not in MODEL_DIRS:
        raise InputError("bad model folder")
    base = os.path.basename(m["file"])
    if not base or base.startswith(".") or "/" in base or "\\" in base:
        raise InputError("bad model file")
    return os.path.join(MODELS_ROOT, m["dir"], base)


def download(app_ids):
    """Queue every missing model of these apps (deduped). → status list."""
    want = {}
    for aid in app_ids:
        for m in readiness(get(aid), refresh=True)["missing"]:
            want[m["file"].split("/")[-1]] = m
    need = sum(m["gb"] for m in want.values()) * 1e9
    free = shutil.disk_usage(MODELS_ROOT if os.path.isdir(MODELS_ROOT) else os.path.dirname(MODELS_ROOT)).free
    if need > free - 20e9:
        raise InputError("not enough disk: need %.1f GB, %.1f GB free (keeping 20 GB spare)" % (need / 1e9, free / 1e9))
    with _DL_LOCK:
        for k, m in want.items():
            if DL.get(k, {}).get("status") in ("queued", "downloading"):
                continue
            DL[k] = dict(m, name=k, status="queued", done=0, total=int(m["gb"] * 1e9), error="")
    threading.Thread(target=_dl_worker, daemon=True, name="ff-dl").start()
    return dl_status()


_DL_RUN = threading.Lock()


def _dl_worker():
    if not _DL_RUN.acquire(blocking=False):
        return
    try:
        while True:
            with _DL_LOCK:
                d = next((v for v in DL.values() if v["status"] == "queued"), None)
            if not d:
                return
            for attempt in range(4):                      # CDN drops mid-file happen on 5-20 GB files: resume from .part
                _dl_one(d)
                if d["status"] != "error" or "refused" in d.get("error", "") or d.get("cancel"):
                    break
                d.update(status="queued", error="retry %d: %s" % (attempt + 1, d.get("error", "")))
                time.sleep(5 * (attempt + 1))
            _ENGINE["t"] = 0                              # re-scan models next time
    finally:
        _DL_RUN.release()


def _dl_one(d):
    dest = _dest(d)
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = "https://huggingface.co/%s/resolve/main/%s" % (d["repo"], "/".join(requests.utils.quote(p) for p in d["file"].split("/")))
    hdr = {"User-Agent": "mir-media-labs-studio/1.0"}
    tok = _hf_token()
    if tok:
        hdr["Authorization"] = "Bearer " + tok          # requests drops it on the cross-host redirect to HF's CDN
    d["status"] = "downloading"
    try:
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        if have:
            hdr["Range"] = "bytes=%d-" % have
        with requests.get(url, headers=hdr, stream=True, timeout=60, allow_redirects=True) as r:
            if r.status_code == 416:
                have = 0
            elif r.status_code in (401, 403):
                raise RuntimeError("Hugging Face refused (gated model? accept its license and set HF_TOKEN)")
            elif r.status_code not in (200, 206):
                raise RuntimeError("HTTP %d" % r.status_code)
            if r.status_code == 200:
                have = 0
            total = int(r.headers.get("Content-Length") or 0) + have
            d.update(total=total or d["total"], done=have)
            with open(part, "ab" if have else "wb") as f:
                for chunk in r.iter_content(4 << 20):
                    if d.get("cancel"):
                        raise RuntimeError("cancelled")
                    f.write(chunk)
                    d["done"] += len(chunk)
        os.replace(part, dest)
        d["status"] = "done"
    except Exception as e:
        d.update(status="cancelled" if str(e) == "cancelled" else "error", error=(str(e) or type(e).__name__)[:300])


def dl_status():
    with _DL_LOCK:
        return [{k: v for k, v in d.items() if k != "cancel"} for d in DL.values()]


def dl_cancel(name=None):
    with _DL_LOCK:
        for k, d in DL.items():
            if name in (None, k) and d["status"] in ("queued", "downloading"):
                d["cancel"] = True
                if d["status"] == "queued":
                    d["status"] = "cancelled"


# ── status for the page header / MCP ───────────────────────────────────────────────────────────────────────────────
def status(refresh=False):
    e = _engine(refresh)
    rows = [readiness(a) for a in apps().values() if visible(a["id"])]
    count = {}
    for r in rows:
        count[r["state"]] = count.get(r["state"], 0) + 1
    return {"root": ROOT, "apps": len(rows), "states": count, "engine": {"up": e["nodes"] is not None, "version": e["version"],
            "wants": "0.42.0"}, "running": next((_public(JOBS[i]) for i in ORDER if JOBS.get(i, {}).get("status") == "running"), None),
            "downloads": dl_status()}


# ── Flask routes ───────────────────────────────────────────────────────────────────────────────────────────────────
_STARTED = []


def start():
    if _STARTED:
        return
    _STARTED.append(1)
    _load()
    threading.Thread(target=_worker, daemon=True, name="ff-worker").start()


def register(app, hk):
    """hk: uid(), is_owner(), static(fn), session(sid) → valid sid."""
    from flask import Response, abort, jsonify, request
    start()

    def err(e, code=400):
        return jsonify({"error": str(e)}), code

    @app.route("/studio")
    def ff_page():
        return hk["static"]("studio.html")

    @app.route("/api/ff/status")
    def ff_status():
        return jsonify(status(bool(request.args.get("refresh"))))

    @app.route("/api/ff/apps")
    def ff_apps():
        if request.args.get("refresh"):
            _engine(True)
        dev = bool(request.args.get("dev"))
        return jsonify({"apps": [summary(a) for a in apps().values() if visible(a["id"], dev)], "engine": status()["engine"],
                        "merged": [{"id": k, "into": v} for k, v in SUPERSEDED.items()]})

    @app.route("/api/ff/app/<aid>")
    def ff_app(aid):
        try:
            return jsonify(detail(get(aid)))
        except InputError as e:
            return err(e, 404)

    @app.route("/api/ff/upload", methods=["POST"])
    def ff_upload():
        f = request.files.get("file")
        if not f:
            return err("no file")
        try:
            return jsonify(stash_upload(f))
        except InputError as e:
            return err(e)

    @app.route("/api/ff/run", methods=["POST"])
    def ff_run():
        b = request.get_json(silent=True) or {}
        vals = {}
        try:
            for k, v in (b.get("values") or {}).items():
                if isinstance(v, dict) and v.get("lib"):
                    vals[k] = from_library(v["lib"])
                elif isinstance(v, dict) and v.get("up"):
                    p = core.in_dir(INBOX, v["up"])
                    if not p:
                        raise InputError("%s: upload expired, add the file again" % k)
                    vals[k] = {"path": p, "name": os.path.basename(p)}
                else:
                    vals[k] = v
            j = submit(b.get("app"), vals, user=hk["uid"](), session=hk["session"](b.get("session")), preset=b.get("preset") or None,
                       loras=b.get("loras") if isinstance(b.get("loras"), list) else None)
            return jsonify(j)
        except InputError as e:
            return err(e)

    @app.route("/api/ff/loras")
    def ff_loras():
        fam = request.args.get("family")
        ls = user_loras()
        return jsonify({"loras": [l for l in ls if not fam or l["family"] in (fam, None)], "labels": FAMILY_LABEL, "max": LORA_MAX})

    @app.route("/api/ff/jobs/<jid>/workflow")
    def ff_workflow(jid):
        """The exact API graph(s) a run sent to ComfyUI — drop the file on the ComfyUI canvas to open it there."""
        j = JOBS.get(jid)
        if not j or not (hk["is_owner"]() or j.get("user") == hk["uid"]()):
            abort(404)
        gs = j.get("graphs") or []
        if not gs:
            abort(404)
        try:
            k = max(0, min(len(gs) - 1, int(request.args.get("n", len(gs) - 1))))
        except ValueError:
            k = len(gs) - 1
        p = core.in_dir(GRAPHS, gs[k]["file"])
        if not p:
            abort(404)
        with open(p, encoding="utf-8") as f:
            body = f.read()
        fn = "%s_%s%s.json" % (j.get("app", "studio"), jid, "_%d" % k if len(gs) > 1 else "")
        hdr = {"Cache-Control": "no-store"}
        if request.args.get("dl"):
            hdr["Content-Disposition"] = 'attachment; filename="%s"' % fn
        return Response(body, mimetype="application/json", headers=hdr)

    import ffpack
    ffpack.register(app, hk)

    @app.route("/api/ff/jobs")
    def ff_jobs():
        return jsonify({"jobs": jobs(None if hk["is_owner"]() else hk["uid"]())})

    @app.route("/api/ff/jobs/<jid>")
    def ff_job(jid):
        j = JOBS.get(jid)
        if not j or not (hk["is_owner"]() or j.get("user") == hk["uid"]()):
            abort(404)
        return jsonify(_public(j))

    @app.route("/api/ff/jobs/<jid>/preview")
    def ff_preview(jid):
        j = JOBS.get(jid)
        if not j or not j.get("_pv"):
            abort(404)
        return Response(j["_pv"], mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.route("/api/ff/jobs/<jid>/cancel", methods=["POST"])
    def ff_cancel(jid):
        j = JOBS.get(jid)
        if not j or not (hk["is_owner"]() or j.get("user") == hk["uid"]()):
            abort(404)
        return jsonify({"ok": cancel(jid)})

    @app.route("/api/ff/download", methods=["GET", "POST"])
    def ff_download():
        if request.method == "GET":
            return jsonify({"downloads": dl_status()})
        if not hk["is_owner"]():
            return err("only the owner can download models", 403)
        b = request.get_json(silent=True) or {}
        try:
            if b.get("cancel"):
                dl_cancel(b.get("name"))
                return jsonify({"downloads": dl_status()})
            return jsonify({"downloads": download([str(x) for x in b.get("apps") or []])})
        except InputError as e:
            return err(e)
