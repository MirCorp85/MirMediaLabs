"""Custom ComfyUI workflows (the ⚙ "ComfyUI workflow" picker) — your own node graphs run as a lab model.

The host saves a workflow exported from ComfyUI with Workflow → Export (API). It is stored per model in
data/workflows/<model>__<slug>.json. On a render the lab fills these placeholders anywhere in the graph and queues it
on the same ComfyUI the built-in graphs use (outputs land in the library like any other render):

  {{prompt}} {{negative}} {{seed}} {{width}} {{height}} {{length}} {{seconds}} {{steps}} {{fps}}
  {{image1}}…{{image9}} {{video1}}…{{video3}} {{audio1}}…{{audio3}}   (attachments, uploaded to ComfyUI's input folder)

A string that is exactly one placeholder becomes the typed value (a number stays a number); placeholders inside longer
strings are replaced as text. Only the host can add or remove workflows; people need the "workflows" right to pick one.
"""
import json
import os
import re
import time

try:
    from . import comfy, core
except ImportError:
    import comfy
    import core

DIR = os.path.join(core.DATA, "workflows")
KIND = {"h3": "video", "qimg": "image", "music3": "audio", "ace": "audio"}
_TOKEN = re.compile(r"\{\{\s*([a-z_]+\d?)\s*\}\}")


def _slug(name):
    return re.sub(r"[^a-z0-9_-]+", "-", str(name or "").lower()).strip("-")[:40] or "workflow"


def _path(wid):
    if not re.fullmatch(r"[a-z0-9]+__[a-z0-9_-]{1,40}", str(wid or "")):
        return None
    return os.path.join(DIR, wid + ".json")


def items(model=None):
    out = []
    try:
        names = sorted(os.listdir(DIR))
    except OSError:
        return out
    for n in names:
        if not n.endswith(".json") or "__" not in n:
            continue
        wid = n[:-5]
        mdl = wid.split("__", 1)[0]
        if model and mdl != model:
            continue
        meta = {}
        try:
            with open(os.path.join(DIR, n), encoding="utf-8") as f:
                meta = (json.load(f) or {}).get("_mml") or {}
        except Exception:
            continue
        out.append({"id": wid, "model": mdl, "label": meta.get("label") or wid.split("__", 1)[1],
                    "tokens": meta.get("tokens") or [], "added": meta.get("added") or 0})
    return out


def options(model):
    """[[id, label]] for the ⚙ picker."""
    return [[w["id"], "custom · " + w["label"]] for w in items(model)]


def save(model, label, graph):
    """Store an API-format graph. → (item, None) or (None, reason)."""
    if model not in KIND:
        return None, "workflows run on the media engines only (video, image, song, music)"
    if isinstance(graph, str):
        try:
            graph = json.loads(graph)
        except ValueError:
            return None, "that file isn't JSON"
    if not isinstance(graph, dict):
        return None, "that file isn't a ComfyUI workflow"
    if "nodes" in graph and "links" in graph:
        return None, "that's the editor format — in ComfyUI use Workflow → Export (API) and add that file"
    graph = {k: v for k, v in graph.items() if k != "_mml"}
    if not graph or not all(isinstance(v, dict) and v.get("class_type") for v in graph.values()):
        return None, "no nodes found — export the workflow with Workflow → Export (API)"
    raw = json.dumps(graph)
    tokens = sorted(set(_TOKEN.findall(raw)))
    if "prompt" not in tokens:
        return None, "put {{prompt}} into the text box of the workflow's prompt node, then export it again"
    os.makedirs(DIR, exist_ok=True)
    wid = "%s__%s" % (model, _slug(label))
    graph["_mml"] = {"label": str(label or wid)[:60], "model": model, "tokens": tokens, "added": time.time(),
                     "nodes": len(graph) - 1}
    with open(core.safe_path(os.path.join(DIR, wid + ".json")), "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1)
    return {"id": wid, "model": model, "label": graph["_mml"]["label"], "tokens": tokens}, None


def remove(wid):
    p = _path(wid)
    if not p or not os.path.isfile(p):
        return False
    os.remove(p)
    return True


def _fill(node, values):
    if isinstance(node, dict):
        return {k: _fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, values) for v in node]
    if isinstance(node, str):
        m = _TOKEN.fullmatch(node.strip())
        if m and m.group(1) in values:
            return values[m.group(1)]
        return _TOKEN.sub(lambda t: str(values.get(t.group(1), t.group(0))), node)
    return node


def run(job, wid, values, refs, log):
    """Queue the custom graph → (output entry, seconds). refs = {"image": [...], "video": [...], "audio": [...]}."""
    p = _path(wid)
    if not p or not os.path.isfile(p):
        raise RuntimeError("the custom workflow '%s' is no longer on the lab — pick another in ⚙" % wid)
    with open(p, encoding="utf-8") as f:
        graph = json.load(f)
    meta = graph.pop("_mml", {}) or {}
    model = meta.get("model") or wid.split("__", 1)[0]
    vals = dict(values)
    for kind, n in (("image", 9), ("video", 3), ("audio", 3)):
        for i, path in enumerate((refs.get(kind) or [])[:n]):
            vals["%s%d" % (kind, i + 1)] = comfy.upload(path)
    missing = [t for t in (meta.get("tokens") or []) if t not in vals]
    need = [t for t in missing if re.fullmatch(r"(image|video|audio)\d", t)]
    if need:
        raise RuntimeError("this workflow needs %s attached (%s)" % (", ".join(need), meta.get("label", wid)))
    graph = _fill(graph, vals)
    log(job, "custom workflow · %s · %d nodes" % (meta.get("label", wid), len(graph)))
    return comfy.run(graph, KIND.get(model, "video"), job)
