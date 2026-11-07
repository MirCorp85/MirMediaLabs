"""CAST face identity helper — runs in its own Python (insightface + onnxruntime + opencv), never imported by the lab.

InsightFace buffalo_l (ArcFace) — NON-COMMERCIAL licence (optional; packs touched by it carry nc:true).

    python char_faceid.py score --ref a.png[,b.png] --imgs x.png,y.png [--emb out.npy]
        → {"ok":true, "ref_faces":n, "scores":{"x.png":0.71,"y.png":null}}   (null = no face found)
        --best  → score the best-matching face in each picture (multi-person video frames)
    python char_faceid.py box --img in.png  → {"ok":true, "box":[x0,y0,x1,y1]}   (raw face box)
    python char_faceid.py crop --img in.png --out face.png [--pad 0.9]
        → {"ok":true, "box":[x0,y0,x1,y1]}

Score = cosine similarity of the biggest face's ArcFace embedding vs the mean reference embedding
(same person ≈ 0.55-0.85, look-alikes ≈ 0.3-0.5, strangers < 0.2). One JSON line on stdout.
"""
import argparse
import json
import os
import sys

# InsightFace model cache (buffalo_l downloads here on first use); default = ~/.insightface like insightface itself
MODELS = os.environ.get("MML_FACE_MODELS") or os.path.join(os.path.expanduser("~"), ".insightface")

_APP = []


def app():
    if not _APP:
        from insightface.app import FaceAnalysis
        import onnxruntime as ort
        prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        a = FaceAnalysis(name="buffalo_l", root=MODELS, providers=prov, allowed_modules=["detection", "recognition"])
        a.prepare(ctx_id=0, det_size=(640, 640))
        _APP.append(a)
    return _APP[0]


def read(path):
    import cv2
    import numpy as np
    data = np.fromfile(path, dtype=np.uint8)          # unicode-safe on Windows
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def biggest(img):
    faces = app().get(img) if img is not None else []
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def embed(path):
    f = biggest(read(path))
    return None if f is None else f.normed_embedding


def best_match(path, ref):
    """Highest similarity among ALL faces in the picture (multi-person frames: find our character, not the biggest face)."""
    import numpy as np
    img = read(path)
    faces = app().get(img) if img is not None else []
    return None if not faces else max(float(np.dot(ref, f.normed_embedding)) for f in faces)


def cmd_score(a):
    import numpy as np
    refs = [e for e in (embed(p) for p in a.ref.split(",") if p) if e is not None]
    if not refs:
        return {"ok": False, "error": "no face found in the reference picture"}
    ref = np.mean(refs, axis=0)
    ref = ref / (np.linalg.norm(ref) or 1)
    if a.emb:
        np.save(a.emb, ref)
    out = {}
    for p in [x for x in (a.imgs or "").split(",") if x]:
        if a.best:
            v = best_match(p, ref)
            out[os.path.basename(p)] = None if v is None else round(v, 4)
            continue
        e = embed(p)
        out[os.path.basename(p)] = None if e is None else round(float(np.dot(ref, e)), 4)
    return {"ok": True, "ref_faces": len(refs), "scores": out}


def cmd_crop(a):
    import cv2
    img = read(a.img)
    f = biggest(img)
    if f is None:
        return {"ok": False, "error": "no face found"}
    h, w = img.shape[:2]
    x0, y0, x1, y1 = [float(v) for v in f.bbox]
    cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2 - (y1 - y0) * 0.08, max(x1 - x0, y1 - y0) * (1 + 2 * a.pad)
    bx0, by0 = int(max(0, cx - s / 2)), int(max(0, cy - s / 2))
    bx1, by1 = int(min(w, cx + s / 2)), int(min(h, cy + s / 2))
    crop = img[by0:by1, bx0:bx1]
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return {"ok": False, "error": "encode failed"}
    buf.tofile(a.out)
    return {"ok": True, "box": [bx0, by0, bx1, by1]}


def cmd_box(a):
    f = biggest(read(a.img))
    return {"ok": False, "error": "no face found"} if f is None else {"ok": True, "box": [round(float(v)) for v in f.bbox]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("score")
    s.add_argument("--ref", required=True)
    s.add_argument("--imgs", default="")
    s.add_argument("--emb", default="")
    s.add_argument("--best", action="store_true")             # best-matching face, not the biggest
    c = sub.add_parser("crop")
    c.add_argument("--img", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--pad", type=float, default=0.9)
    b = sub.add_parser("box")
    b.add_argument("--img", required=True)
    a = ap.parse_args()
    try:
        res = cmd_score(a) if a.cmd == "score" else cmd_crop(a) if a.cmd == "crop" else cmd_box(a) if a.cmd == "box" else {"ok": False, "error": "no command"}
    except Exception as e:                                # always one JSON line, never a traceback on stdout
        res = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:300])}
    sys.stdout.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
