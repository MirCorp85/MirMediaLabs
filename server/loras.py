"""LoRA SAMPLES — browse the public Civitai LoRA catalog for our engines, install picks into ComfyUI's
loras folder, and apply installed LoRAs to a render as a strong style / identity reference.

  role  → engine        catalog filter
  video → MiniMax H3    baseModels = "MiniMax H3"
  image → Qwen-Image    baseModels = "Qwen 2.1"
  music → ACE-Step      query      = "ACE-Step"   (base tags vary on Civitai — compatibility may vary)

Only SFW previews are shown (nsfw=false, browsingLevel=1, per-image nsfwLevel ≤ 1). Installing downloads
the .safetensors straight into ComfyUI's loras folder (resumable, progress in DL). A render applies its
LoRAs by chaining LoraLoaderModelOnly nodes right after the final model loader (apply()).
Used by both the standalone server and the MirOS copy (miros_mlab) — keep the two files identical
apart from the import line.
"""
import json
import os
import re
import struct
import threading
import time

import requests

try:
    from . import comfy, core          # MirOS copy (package)
except ImportError:
    import comfy                       # standalone
    import core

CIVITAI = "https://civitai.com/api/v1/models"
ROLES = {
    "video": {"label": "Video", "engine": "h3", "params": {"baseModels": "MiniMax H3"}},
    "image": {"label": "Image", "engine": "qimg", "params": {"baseModels": "Qwen 2.1"}},
    "music": {"label": "Music", "engine": "ace", "params": {"query": "ACE-Step"}},
}
# LoRA-capable engines only, derived from ROLES. "music" LoRAs are ACE-Step LoRAs: MiniMax Music 3 (songs) can't load
# them — mapping it to "music" made them "attach" and silently do nothing. Engines missing here take no LoRAs.
ENGINE_ROLE = {v["engine"]: k for k, v in ROLES.items()}
SORTS = {"popular": "Most Downloaded", "rated": "Highest Rated", "new": "Newest"}
INDEX = os.path.join(core.DATA, "loras.json")
LOADERS = {"UNETLoader", "LoraLoaderModelOnly", "CheckpointLoaderSimple", "UnetLoaderGGUF"}
_CACHE, _LOCK, DL = {}, threading.Lock(), {}


# ── where ComfyUI looks for LoRAs ──────────────────────────────────────────
def loras_dir():
    """Resolve ComfyUI's loras folder from its model-paths yaml (Comfy Desktop / installer config)."""
    try:
        y = comfy._model_paths_yaml()
        if y and os.path.isfile(y):
            base, sub = None, None
            for ln in open(y, encoding="utf-8", errors="ignore"):
                m = re.match(r"\s*'?base_path'?\s*:\s*'?([^'\n]+?)'?\s*$", ln)
                if m and base is None:
                    base = m.group(1).strip()
                m = re.match(r"\s*'?loras'?\s*:\s*'?([^'\n|]+?)'?\s*$", ln)
                if m and sub is None:
                    sub = m.group(1).strip()
            if base:
                d = os.path.join(base, sub or "loras")
                os.makedirs(d, exist_ok=True)
                return d
    except Exception:
        pass
    eng = core.CONFIG.get("comfy_dir") if hasattr(core, "CONFIG") else None
    d = os.path.join(eng, "models", "loras") if eng else os.path.join(core.DATA, "loras")
    os.makedirs(d, exist_ok=True)
    return d


def _index():
    return core.load_json(INDEX, {})


def _save_index(ix):
    core.save_json(INDEX, ix)


# ── catalog ────────────────────────────────────────────────────────────────
def _previews(version, n=4):
    out = []
    for im in version.get("images") or []:
        if (im.get("nsfwLevel") or 1) > 1 or im.get("nsfw") in (True, "Mature", "X"):
            continue
        url = im.get("url") or ""
        if not url:
            continue
        kind = "video" if im.get("type") == "video" or url.endswith((".mp4", ".webm")) else "image"
        tr = lambda t: url.replace("original=true", t) if "original=true" in url else url
        out.append({"url": tr("width=720" if kind == "image" else "transcode=true,width=720"), "kind": kind,
                    "thumb": tr("anim=false,width=360"),                     # small still (jpeg) — tiles + native app
                    "small": tr("transcode=true,width=360") if kind == "video" else tr("width=360"),
                    "w": im.get("width"), "h": im.get("height")})
        if len(out) >= n:
            break
    return out


# Civitai's nsfw=false only filters preview IMAGES; adult models still come through by name/tags — hide them
ADULT = re.compile(r"porn|nsfw|nude|naked|hentai|sex|xxx|lewd|erotic|onlyfans|nipple|breast|boob|genital|pussy|penis|"
                   r"fetish|bdsm|undress|topless|bikini|lingerie|voluptuous|seductive|age slider|loli|shota|ahegao|futa", re.I)


def _item(m, role, have):
    if m.get("nsfw") or m.get("minor") or ADULT.search((m.get("name") or "") + " " + " ".join(m.get("tags") or [])):
        return None
    vs = m.get("modelVersions") or []
    if not vs:
        return None
    v = vs[0]
    files = [f for f in (v.get("files") or []) if str(f.get("name", "")).endswith(".safetensors")]
    if not files:
        return None
    f = next((x for x in files if x.get("primary")), files[0])
    pv = _previews(v)
    if not pv:
        return None
    st = m.get("stats") or {}
    return {"id": m.get("id"), "version_id": v.get("id"), "name": m.get("name", "")[:80],
            "creator": (m.get("creator") or {}).get("username", ""), "base": v.get("baseModel", ""),
            "role": role, "file": f.get("name"), "size_mb": round((f.get("sizeKB") or 0) / 1024, 1),
            "download": f.get("downloadUrl") or v.get("downloadUrl"), "triggers": (v.get("trainedWords") or [])[:6],
            "downloads": st.get("downloadCount", 0), "likes": st.get("thumbsUpCount", 0),
            "tags": (m.get("tags") or [])[:5], "previews": pv, "installed": f.get("name") in have,
            "page": "https://civitai.com/models/%s" % m.get("id")}


def catalog(role="video", q="", sort="popular", cursor=None):
    role = role if role in ROLES else "video"
    key = (role, q, sort, cursor)
    with _LOCK:
        c = _CACHE.get(key)
        if c and time.time() - c[0] < 600:
            data = c[1]
            have = set(installed_files())
            for it in data["items"]:
                it["installed"] = it["file"] in have
            return data
    p = {"types": "LORA", "limit": 24, "nsfw": "false", "sort": SORTS.get(sort, "Most Downloaded")}
    p.update(ROLES[role]["params"])
    if q:
        p["query"] = (q + " " + p["query"]) if "query" in p and p["query"] not in q else q
    if cursor:
        p["cursor"] = cursor
    r = requests.get(CIVITAI, params=p, timeout=25, headers={"User-Agent": "MirMediaLabs/1.0"})
    r.raise_for_status()
    d = r.json()
    have = set(installed_files())
    items = [x for x in (_item(m, role, have) for m in d.get("items") or []) if x]
    data = {"role": role, "items": items, "next": (d.get("metadata") or {}).get("nextCursor")}
    with _LOCK:
        _CACHE[key] = (time.time(), data)
    return data


# ── Civitai API key (most LoRA downloads need one; free at civitai.com/user/account → API Keys) ──
def check_token(token):
    """Ask Civitai who this key belongs to. Returns the username; raises if the key is rejected."""
    r = requests.get("https://civitai.com/api/v1/me", timeout=20,
                     headers={"Authorization": "Bearer " + token, "User-Agent": "MirMediaLabs/1.0"})
    if r.status_code in (401, 403):
        raise ValueError("Civitai rejected that key — copy it again from civitai.com/user/account → API Keys")
    r.raise_for_status()
    d = r.json() or {}
    return d.get("username") or d.get("name") or "ok"


# ── installed ──────────────────────────────────────────────────────────────
def installed_files():
    try:
        return sorted(os.listdir(loras_dir()))
    except OSError:
        return []


def installed():
    ix = _index()
    out = []
    for fn in installed_files():
        if not fn.endswith(".safetensors"):
            continue
        meta = ix.get(fn) or {}
        role = meta.get("role") or ""
        out.append({"file": fn, "name": meta.get("name") or os.path.splitext(fn)[0], "role": role,
                    "triggers": meta.get("triggers") or [], "preview": meta.get("preview"), "page": meta.get("page"),
                    "ours": fn in ix, "builtin": fn.startswith("minimax_h3_"),
                    "fits": fits(fn, ROLES[role]["engine"]) if role in ROLES else None})
    return out


# ── does a LoRA fit the model version that's installed? ─────────────────────
# Civitai mixes model generations under one name (e.g. ACE-Step v1 LoRAs vs our ACE-Step 1.5): ComfyUI then
# loads them with "lora key not loaded" for every layer — nothing applies. Compare the LoRA's layer names with
# the model file's (safetensors headers only: no GPU, no ComfyUI, ~ms once cached).
_FIT, _MODS = {}, {}
_PRE = ("model.diffusion_model.", "diffusion_model.", "transformer.", "base_model.model.", "unet.", "model.")
_SUF = re.compile(r"\.(lora_[AB]|lora_down|lora_up|lora\.down|lora\.up|lora_mid|alpha|dora_scale|diff|diff_b|"
                  r"hada_w[12]_[ab]|lokr_w[12](_[ab])?|w_norm|b_norm)(\.weight)?$")


def _st_keys(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n > 64 * 1024 * 1024:
            raise ValueError("header too large")
        return [k for k in json.loads(f.read(n)) if k != "__metadata__"]


def _strip(k):
    for p in _PRE:
        if k.startswith(p):
            return k[len(p):]
    return k


def _engine_file(engine):
    try:
        from . import renderers as R          # MirOS copy (package)
    except ImportError:
        import renderers as R                  # standalone
    f = {"h3": R.H3.get("unet"), "qimg": R.QIMG.get("dit"), "ace": R.ACE.get("dit")}.get(engine)
    return f[0] if isinstance(f, list) else f


def _model_path(name):
    roots = [os.path.dirname(loras_dir().rstrip("/\\"))]
    root = getattr(comfy, "COMFY_ROOT", "") or ""
    roots += [os.path.join(root, "ComfyUI", "models"), os.path.join(root, "models")]
    for r in roots:
        for sub in ("diffusion_models", "unet"):
            p = os.path.join(r, sub, name)
            if os.path.isfile(p):
                return p
    return None


def fits(file, engine):
    """True / False: does this LoRA's layer layout match the engine's installed model? None = can't tell."""
    lp = os.path.join(loras_dir(), os.path.basename(str(file)))
    mf = _engine_file(engine)
    mp = _model_path(mf) if mf else None
    if not mp or not os.path.isfile(lp):
        return None
    key = (lp, os.path.getmtime(lp), mp)
    if key not in _FIT:
        try:
            if mp not in _MODS:
                _MODS[mp] = {_strip(k).rsplit(".", 1)[0] for k in _st_keys(mp)}
            mods = _MODS[mp]
            under = {m.replace(".", "_") for m in mods}
            lmods = {m for m in (_SUF.sub("", k) for k in _st_keys(lp)) if m}
            lmods = {m for m in lmods if m not in ("", None)}
            hit = sum(1 for m in lmods if _strip(m) in mods or _strip(m).replace(".", "_") in under
                      or (_strip(m).startswith("lora_unet_") and _strip(m)[10:] in under))
            _FIT[key] = None if not lmods else hit / len(lmods) >= 0.5
        except Exception:
            _FIT[key] = None
    return _FIT[key]


def install(item, token=""):
    """Download a catalog item into the loras folder in the background. Returns the download key."""
    url, fn = item.get("download"), os.path.basename(str(item.get("file") or ""))
    if not url or not fn.endswith(".safetensors") or not str(url).startswith("https://civitai.com/"):
        raise ValueError("not a Civitai .safetensors LoRA")
    key = str(item.get("version_id"))
    if DL.get(key, {}).get("state") == "downloading":
        return key
    DL[key] = {"state": "downloading", "pct": 0, "file": fn, "name": item.get("name"), "error": "", "need_key": False}

    def run():
        dst = os.path.join(loras_dir(), fn)
        tmp = dst + ".part"
        try:
            have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            hdr = {"User-Agent": "MirMediaLabs/1.0"}
            if token:   # header, not query: requests drops it on the redirect to Civitai's file CDN
                hdr["Authorization"] = "Bearer " + token
            if have:
                hdr["Range"] = "bytes=%d-" % have
            with requests.get(url, headers=hdr, stream=True, timeout=(15, 120), allow_redirects=True) as r:
                if r.status_code in (401, 403):
                    DL[key]["need_key"] = True
                    raise RuntimeError("Civitai rejected the saved key — update it in Settings → Civitai key" if token else
                                       "This LoRA needs a free Civitai API key — add it in Settings → Civitai key")
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0) + (have if r.status_code == 206 else 0)
                mode = "ab" if r.status_code == 206 else "wb"
                done = have if r.status_code == 206 else 0
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            DL[key]["pct"] = int(done * 100 / total)
            os.replace(tmp, dst)
            ix = _index()
            ix[fn] = {"name": item.get("name"), "role": item.get("role"), "triggers": item.get("triggers") or [],
                      "preview": (item.get("previews") or [{}])[0], "page": item.get("page"),
                      "version_id": item.get("version_id"), "installed": time.time()}
            _save_index(ix)
            DL[key].update(state="done", pct=100)
            with _LOCK:
                _CACHE.clear()
        except Exception as e:
            DL[key].update(state="error", error=str(e)[:200])

    threading.Thread(target=run, daemon=True, name="lora-dl").start()
    return key


def remove(fn):
    fn = os.path.basename(str(fn))
    ix = _index()
    if fn not in ix:
        raise ValueError("only LoRAs installed from LoRA Samples can be removed here")
    try:
        os.remove(os.path.join(loras_dir(), fn))
    except OSError:
        pass
    ix.pop(fn, None)
    _save_index(ix)


# ── apply to a render ──────────────────────────────────────────────────────
def selection(wanted):
    """A request's LoRA picks, cleaned: [{file, strength}], at most 4."""
    out = []
    for w in (wanted or [])[:4]:
        fn = os.path.basename(str((w or {}).get("file") or "")) if isinstance(w, dict) else ""
        if fn:
            try:
                st = max(0.0, min(1.5, float(w.get("strength", 0.8))))
            except (TypeError, ValueError):
                st = 0.8
            out.append({"file": fn, "strength": st})
    return out


def pick(model, wanted, skipped=None):
    """Validate a request's [{file, strength}] against what's installed + what this engine can load.
    LoRAs that can't apply are left out and, when `skipped` is a list, reported there as {file, name, why}."""
    role = ENGINE_ROLE.get(model)
    have = {x["file"]: x for x in installed()}
    out = []
    for w in selection(wanted):
        fn = w["file"]
        meta = have.get(fn)
        if not meta or meta.get("builtin"):
            if not meta and skipped is not None:
                skipped.append({"file": fn, "name": fn, "why": "no longer installed"})
            continue
        if role is None or (meta.get("role") and meta["role"] != role):
            if skipped is not None:
                r = meta.get("role")
                skipped.append({"file": fn, "name": meta.get("name") or fn,
                                "why": ("made for %s" % {"image": "images"}.get(r, r)) if r in ROLES else "this model can't load LoRAs"})
            continue
        if meta.get("fits") is False:      # right kind, wrong model generation: ComfyUI would load none of its layers
            if skipped is not None:
                skipped.append({"file": fn, "name": meta.get("name") or fn, "why": "made for a different version of this model"})
            continue
        try:
            s = max(0.0, min(1.5, float((w or {}).get("strength", 0.8))))
        except (TypeError, ValueError):
            s = 0.8
        out.append({"file": fn, "strength": s, "name": meta["name"], "triggers": meta.get("triggers") or []})
    return out


def apply(graph, job):
    """Chain the job's LoRAs (LoraLoaderModelOnly) right after the final model loader."""
    ls = job.get("loras") or []
    if not ls:
        return graph
    loaders = {k for k, n in graph.items() if n.get("class_type") in LOADERS}
    fed = {v[0] for k, n in graph.items() if k in loaders for v in (n.get("inputs") or {}).values()
           if isinstance(v, list) and len(v) == 2 and v[0] in loaders}
    finals = [k for k in loaders if k not in fed]
    if not finals:
        return graph
    src = finals[0]
    prev = src
    chain = []
    for i, l in enumerate(ls):
        nid = "mml_lora_%d" % i
        graph[nid] = {"class_type": "LoraLoaderModelOnly",
                      "inputs": {"model": [prev, 0], "lora_name": l["file"], "strength_model": l["strength"]}}
        chain.append(nid)
        prev = nid
    for k, n in graph.items():
        if k in chain:
            continue
        for ik, v in (n.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) == 2 and v[0] == src and v[1] == 0:
                n["inputs"][ik] = [prev, 0]
    return graph
