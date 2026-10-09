"""SERIES assets — a person's own library of finished building blocks, reusable in any series:
characters (hero · turnaround · expressions + every builder choice + voice), locations, style bibles and songs
(audio + recognised lyrics). A real folder per asset, so it can be browsed and backed up outside the lab:

    data/assets/<user>/characters/<name>-<id>/   character.json  hero.png  sheet.png  expr.png
    data/assets/<user>/locations/<name>-<id>/    location.json   image.png
    data/assets/<user>/objects/<name>-<id>/      object.json     hero.png  sheet.png  detail.png
    data/assets/<user>/styles/<name>-<id>/       style.json      sample.png
    data/assets/<user>/songs/<name>-<id>/        song.json       song.mp3   vocal.wav

Using an asset in a series COPIES it in (pictures go into the person's refs), so editing or deleting either side never
breaks the other. Identical in the MirOS copy (miros_mlab) — copy, never import across.
"""
import json
import os
import re
import shutil
import time
import uuid

try:
    from . import core, series
except ImportError:
    import core
    import series

ROOT = os.path.join(core.DATA, "assets")
KINDS = {"characters": "character", "locations": "location", "objects": "object", "styles": "style", "songs": "song"}
_ID_RE = re.compile(r"^(characters|locations|objects|styles|songs)/[a-z0-9-]{1,60}-[a-f0-9]{8}$")


def _udir(uid):
    d = os.path.join(ROOT, re.sub(r"[^A-Za-z0-9_-]", "_", str(uid or "owner")))
    os.makedirs(d, exist_ok=True)
    return d


def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", str(t or "").lower()).strip("-")[:40] or "untitled"


def _folder(uid, aid):
    if not _ID_RE.match(str(aid or "")):
        return None
    p = os.path.join(_udir(uid), *aid.split("/"))
    return p if os.path.isdir(p) else None


def _meta_name(kind):
    return KINDS[kind] + ".json"


def _new(uid, kind, name):
    aid = "%s/%s-%s" % (kind, _slug(name), uuid.uuid4().hex[:8])
    p = os.path.join(_udir(uid), *aid.split("/"))
    os.makedirs(p, exist_ok=True)
    return aid, p


def _copy_ref(ref, folder, base):
    """A ref picture/audio → <folder>/<base><ext>. → file name or None."""
    src = core.in_dir(core.REFS, os.path.basename(str(ref or "")))
    if not src or not os.path.isfile(src):
        return None
    name = base + os.path.splitext(src)[1].lower()
    shutil.copy2(src, os.path.join(folder, name))
    return name


def _write(folder, kind, meta):
    meta.setdefault("created", time.time())
    meta["updated"] = time.time()
    with open(os.path.join(folder, _meta_name(kind)), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    return meta


def _read(folder, kind):
    try:
        with open(os.path.join(folder, _meta_name(kind)), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── save from a series ────────────────────────────────────────────────────────────────────────────────────────────
def save(uid, d, kind, target=None):
    """Copy one building block of series d into the asset library. → the new asset's listing row."""
    st = (d.get("setup") or {}).get("style")
    origin = {"series": d.get("name"), "series_id": d.get("id"), "style": st}
    if kind == "characters":
        c = series._find(d, "characters", target)
        if not c:
            raise ValueError("pick a character")
        if not (c.get("hero") or c.get("sheet")):
            raise ValueError("draw the character first — an asset needs its pictures")
        aid, p = _new(uid, kind, c.get("name") or "character")
        files = {k: _copy_ref(c.get(k), p, k) for k in ("hero", "sheet", "expr")}
        _write(p, kind, dict(origin, name=c.get("name") or "", desc=c.get("desc") or "", traits=c.get("traits") or {},
                             voice=c.get("voice") or "", built=c.get("built") or "", style_prompt=d.get("style_prompt") or "",
                             files={k: v for k, v in files.items() if v}))
    elif kind == "locations":
        loc = series._find(d, "locations", target)
        if not loc or not loc.get("image"):
            raise ValueError("draw the location first")
        aid, p = _new(uid, kind, loc.get("name") or "location")
        img = _copy_ref(loc.get("image"), p, "image")
        _write(p, kind, dict(origin, name=loc.get("name") or "", desc=loc.get("desc") or "", files={"image": img}))
    elif kind == "objects":
        o = series._find(d, "objects", target)
        if not o or not (o.get("hero") or o.get("sheet")):
            raise ValueError("draw the object first — an asset needs its pictures")
        aid, p = _new(uid, kind, o.get("name") or "object")
        files = {k: _copy_ref(o.get(k), p, k) for k in ("hero", "sheet", "detail")}
        _write(p, kind, dict(origin, name=o.get("name") or "", desc=o.get("desc") or "", traits=o.get("traits") or {},
                             built=o.get("built") or "", style_prompt=d.get("style_prompt") or "",
                             files={k: v for k, v in files.items() if v}))
    elif kind == "styles":
        if not (d.get("style_prompt") or st):
            raise ValueError("this series has no style yet")
        aid, p = _new(uid, kind, d.get("name") or "style")
        pic = next((c.get("sheet") or c.get("hero") for c in d.get("characters") or [] if c.get("sheet") or c.get("hero")), None)
        sample = _copy_ref(d.get("lineup") or pic, p, "sample")
        _write(p, kind, dict(origin, name=(d.get("name") or "Style") + " look", style_prompt=d.get("style_prompt") or "",
                             analysis=d.get("style_analysis") or "", setup=d.get("setup") or {},
                             files={"sample": sample} if sample else {}))
    elif kind == "songs":
        ep = series._find(d, "episodes", target)
        song = ep and core.in_dir(core.LIB, ep.get("song") or "")
        if not song or not os.path.isfile(song):
            raise ValueError("that episode has no song yet")
        aid, p = _new(uid, kind, (ep.get("song_text") or {}).get("title") or ep.get("title") or "song")
        name = "song" + os.path.splitext(song)[1].lower()
        shutil.copy2(song, os.path.join(p, name))
        files = {"song": name}
        vocal = _copy_ref(ep.get("vocal"), p, "vocal")
        if vocal:
            files["vocal"] = vocal
        _write(p, kind, dict(origin, name=(ep.get("song_text") or {}).get("title") or ep.get("title") or "Song",
                             song_text=ep.get("song_text") or {}, words=ep.get("words") or [], sections=ep.get("sections") or [],
                             lang=ep.get("lang"), secs=ep.get("song_secs"), source=ep.get("song_source") or "made", files=files))
    else:
        raise ValueError("unknown asset type")
    return row(uid, aid)


def row(uid, aid):
    p = _folder(uid, aid)
    kind = aid.split("/")[0]
    m = _read(p, kind) if p else None
    if not m:
        return None
    files = m.get("files") or {}
    thumb = files.get("hero") or files.get("sheet") or files.get("image") or files.get("sample")
    return {"id": aid, "kind": kind, "name": m.get("name"), "from": m.get("series"), "style": m.get("style"),
            "created": m.get("created"), "files": files, "thumb": thumb, "built": m.get("built"),
            "secs": m.get("secs"), "lyrics": ((m.get("song_text") or {}).get("lyrics") or "")[:400],
            "desc": (m.get("desc") or m.get("style_prompt") or "")[:300]}


def listing(uid, kind=None):
    out = []
    base = _udir(uid)
    for k in KINDS:
        if kind and k != kind:
            continue
        kd = os.path.join(base, k)
        if not os.path.isdir(kd):
            continue
        for f in os.listdir(kd):
            r = row(uid, "%s/%s" % (k, f))
            if r:
                out.append(r)
    out.sort(key=lambda x: -(x.get("created") or 0))
    return out


# ── use in a series (copied in) ───────────────────────────────────────────────────────────────────────────────────
def _to_ref(folder, fname, store_ref, stem):
    if not fname:
        return None
    src = os.path.join(folder, os.path.basename(fname))
    if not os.path.isfile(src):
        return None
    ref = store_ref(stem, os.path.splitext(fname)[1].lower())
    shutil.copy2(src, os.path.join(core.REFS, ref))
    return ref


def use(uid, d, aid, store_ref, episode=None, seconds_of=None):
    """Copy an asset into series d. → d (saved by the caller)."""
    p = _folder(uid, aid)
    kind = aid.split("/")[0] if p else None
    m = _read(p, kind) if p else None
    if not m:
        raise ValueError("that asset is gone")
    files = m.get("files") or {}
    if kind == "characters":
        if len(d.get("characters") or []) >= series.MAX_CAST:
            raise ValueError("this series already has a full cast")
        c = {"id": series.new_id(), "name": m.get("name") or "", "desc": m.get("desc") or "", "voice": m.get("voice") or "",
             "traits": m.get("traits") or {}, "asset": aid}
        c["built"] = series.presets.compose_desc(c["traits"]) if c["traits"] else ""
        c["voice_desc"] = series.presets.voice_desc(c["traits"])
        for k in ("hero", "sheet", "expr"):
            r = _to_ref(p, files.get(k), store_ref, "%s_%s" % (_slug(m.get("name")), k))
            if r:
                c[k] = r
        d.setdefault("characters", []).append(c)
    elif kind == "locations":
        if len(d.get("locations") or []) >= series.MAX_LOCS:
            raise ValueError("this series already has the most locations")
        d.setdefault("locations", []).append({"id": series.new_id(), "name": m.get("name") or "", "desc": m.get("desc") or "",
                                              "image": _to_ref(p, files.get("image"), store_ref, _slug(m.get("name"))),
                                              "asset": aid})
    elif kind == "objects":
        if len(d.get("objects") or []) >= series.MAX_OBJS:
            raise ValueError("this series already has the most objects")
        o = {"id": series.new_id(), "name": m.get("name") or "", "desc": m.get("desc") or "", "traits": m.get("traits") or {},
             "asset": aid}
        o["built"] = series.presets.compose_obj_desc(o["traits"]) if o["traits"] else ""
        for k in ("hero", "sheet", "detail"):
            r = _to_ref(p, files.get(k), store_ref, "%s_%s" % (_slug(m.get("name")), k))
            if r:
                o[k] = r
        d.setdefault("objects", []).append(o)
    elif kind == "styles":
        d["style_prompt"] = m.get("style_prompt") or d.get("style_prompt") or ""
        if m.get("analysis"):
            d["style_analysis"] = m["analysis"]
        su = dict(d.get("setup") or {})
        for k in ("style", "aspect", "res"):
            if (m.get("setup") or {}).get(k):
                su[k] = m["setup"][k]
        d["setup"] = series._setup(su)
    elif kind == "songs":
        ep = series._find(d, "episodes", episode)
        if not ep:
            raise ValueError("pick the episode the song is for")
        src = os.path.join(p, files.get("song") or "")
        if not os.path.isfile(src):
            raise ValueError("the song file is gone")
        name = core.new_name("song", os.path.splitext(src)[1].lower())
        shutil.copy2(src, os.path.join(core.LIB, name))
        core.index_add(name, {"model": "asset", "prompt": "song asset " + (m.get("name") or ""), "created": time.time(),
                              "user": uid or "owner", "mode": "song"})
        series.use_song(d, ep, name, seconds_of, source=m.get("source") or "made")
        if m.get("words"):                             # recognised before: no need to listen again
            ep["words"], ep["sections"], ep["lang"] = m["words"], m.get("sections") or [], m.get("lang")
            ep["vocal"] = _to_ref(p, files.get("vocal"), store_ref, "vocal")
            ep["chunks"] = series.song_map(d, ep, float(ep.get("song_secs") or 60))
        if m.get("song_text"):
            ep["song_text"] = dict(m["song_text"])
    else:
        raise ValueError("unknown asset type")
    return d


def delete(uid, aid):
    p = _folder(uid, aid)
    if p:
        os.makedirs(core.TRASH, exist_ok=True)
        shutil.move(p, os.path.join(core.TRASH, "asset_%s_%d" % (aid.replace("/", "_"), int(time.time()))))


def rename(uid, aid, name):
    p = _folder(uid, aid)
    kind = aid.split("/")[0] if p else None
    m = _read(p, kind) if p else None
    if not m:
        raise ValueError("that asset is gone")
    m["name"] = str(name or "").strip()[:80] or m.get("name")
    _write(p, kind, m)
    return row(uid, aid)


# ── Flask wiring (series.register calls this) ─────────────────────────────────────────────────────────────────────
def register(app, hk):
    from flask import request, jsonify, abort, send_file

    def U():
        return hk["uid"]()

    def body():
        return request.get_json(silent=True) or {}

    def oops(e, code=400):
        return jsonify({"error": str(e)[:400]}), code

    @app.route("/api/assets")
    def as_list():
        k = request.args.get("kind")
        return jsonify({"assets": listing(U(), k if k in KINDS else None), "root": _udir(U())})

    @app.route("/api/assets/save", methods=["POST"])
    def as_save():
        b = body()
        d = series.load(U(), b.get("series"))
        if not d:
            return oops("no such series", 404)
        try:
            if b.get("kind") == "cast":                # every drawn character of the series at once
                rows = [save(U(), d, "characters", c["id"]) for c in d.get("characters") or [] if c.get("hero") or c.get("sheet")]
                if not rows:
                    return oops("draw the cast first")
                series.log_event(U(), d["id"], "assets-saved", kind="cast", n=len(rows))
                return jsonify({"saved": rows})
            r = save(U(), d, b.get("kind"), b.get("target"))
        except Exception as e:
            return oops(e)
        series.log_event(U(), d["id"], "assets-saved", kind=b.get("kind"), name=r and r.get("name"))
        return jsonify({"saved": [r]})

    @app.route("/api/assets/use", methods=["POST"])
    def as_use():
        b = body()
        with series.locked(U(), b.get("series")):
            d = series.load(U(), b.get("series"))
            if not d:
                return oops("no such series", 404)
            try:
                use(U(), d, str(b.get("asset") or ""), hk["store_ref"], b.get("episode"), hk["seconds_of"])
            except Exception as e:
                return oops(e)
            series.save(U(), d)
            series.checkpoint(U(), d, "asset added")
        series.log_event(U(), d["id"], "asset-used", asset=b.get("asset"))
        return jsonify(d)

    @app.route("/api/assets/delete", methods=["POST"])
    def as_delete():
        delete(U(), str(body().get("asset") or ""))
        return jsonify({"ok": True})

    @app.route("/api/assets/rename", methods=["POST"])
    def as_rename():
        b = body()
        try:
            return jsonify(rename(U(), str(b.get("asset") or ""), b.get("name")))
        except Exception as e:
            return oops(e)

    @app.route("/api/assets/file")
    def as_file():
        aid, fn = request.args.get("id"), os.path.basename(request.args.get("f") or "")
        p = _folder(U(), aid)
        f = p and os.path.join(p, fn)
        if not f or not fn or fn.endswith(".json") or not os.path.isfile(f):
            abort(404)
        return send_file(f, conditional=True)
