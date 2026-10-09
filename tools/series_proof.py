"""End-to-end proof of the musical pipeline through the running lab's own API (loopback = owner):
series → character hero → an existing sung track filed as the song (cut into shots) → shot writing → first frame →
shot 1 sung from the picture → shot 2 continued from shot 1's last frames → assembled under the song.

    python tools/series_proof.py <song file in the library> [--secs 20]
"""
import json
import sys
import time
import urllib.error
import urllib.request

LAB = "http://127.0.0.1:5400"


def api(path, body=None, timeout=600):
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return dict(json.loads(e.read().decode("utf-8") or "{}"), http=e.code)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def job(sid, kind, target, extra=None):
    p = api("/api/series/%s/plan" % sid, {"kind": kind, "target": target, "extra": extra or {}})
    if p.get("error"):
        raise SystemExit("plan %s: %s" % (kind, p["error"]))
    while True:
        j = api("/api/generate", {"model": p["model"], "prompt": p["prompt"], "refs": p["refs"], "override": p["override"], "series": True})
        if j.get("http") == 409:
            time.sleep(10)
            continue
        if j.get("error"):
            raise SystemExit("generate %s: %s" % (kind, j["error"]))
        break
    log("queued", kind, j["id"])
    t0 = time.time()
    while True:
        time.sleep(5)
        s = api("/api/jobs/" + j["id"])
        if s["status"] not in ("queued", "running"):
            break
    if s["status"] != "done":
        raise SystemExit("%s failed: %s" % (kind, s.get("error")))
    f = [x for x in s.get("files") or []][0].split("/")[-1]
    log("done", kind, f, "%.1f min" % ((time.time() - t0) / 60))
    d = api("/api/series/%s/attach" % sid, dict(p["attach"], file=f))
    if d.get("error"):
        raise SystemExit("attach %s: %s" % (kind, d["error"]))
    return d, f


def main():
    song = sys.argv[1]
    d = api("/api/series", {"name": "Proof — Pip sings", "setup": {"structure": "musical", "style": "animated3d", "length": 20,
                                                                  "aspect": "16:9", "clip": 10, "song": {"bpm": 120}}})
    sid = d["id"]
    log("series", sid)
    d["style_prompt"] = ""
    d["characters"] = [{"id": "pipfox000001", "name": "Pip", "desc": "",
                        "traits": {"kind": "fox", "gender": "girl", "height": 3, "build": "round and chubby", "skin": "#ff9a3c",
                                   "eyes": "big round", "eyecolor": "green", "top": "raincoat", "shoes": "rain boots",
                                   "accent": "#ffcf3f", "traits": ["curious", "brave"]}}]
    d["episodes"] = [{"id": "proofep00001", "title": "Pip sings in the rain", "idea": "Pip sings and dances on a rainy village street, splashing in puddles",
                      "lesson": "rainy days can be fun", "cast": ["pipfox000001"], "seconds": 10}]
    d = api("/api/series", d)
    log("character:", d["characters"][0].get("built"))
    d, _ = job(sid, "hero", "pipfox000001")
    # the song: an existing sung track from the library, filed exactly like a finished song render
    d = api("/api/series/%s/attach" % sid, {"file": song, "kind": "song", "target": "proofep00001"})
    if d.get("error"):
        raise SystemExit("song attach: " + d["error"])
    ep = d["episodes"][0]
    log("song", ep["song_secs"], "s →", [(c["i"], c["start"], c["end"], c["link"]) for c in ep["chunks"]])
    d = api("/api/series/%s/write" % sid, {"episode": "proofep00001", "what": "chunks"})
    if d.get("error"):
        raise SystemExit("write chunks: " + d["error"])
    ep = d["episodes"][0]
    if len(ep["chunks"]) > 1:      # the proof is about continuity: shot 2 continues shot 1
        ep["chunk_edits"] = {str(c["i"]): {"shot": c["shot"], "singer": c["singer"], "link": "cut" if c["i"] == 0 else "continue"}
                             for c in ep["chunks"]}
        d = api("/api/series", d)
    for c in d["episodes"][0]["chunks"]:
        log("shot", c["i"], c["link"], "|", c["shot"][:160])
    for c in d["episodes"][0]["chunks"]:
        if c["link"] == "cut":
            d, f = job(sid, "keyframe", "proofep00001", {"i": c["i"]})
        d, f = job(sid, "chunk", "proofep00001", {"i": c["i"]})
    d = api("/api/series/%s/episode/proofep00001/assemble" % sid, {})
    if d.get("error"):
        raise SystemExit("assemble: " + d["error"])
    ep = d["episodes"][0]
    log("FINAL", ep["final"], "clips", [c["clip"] for c in ep["chunks"]], "key", [c.get("key") for c in ep["chunks"]],
        "hero", d["characters"][0].get("hero"))


if __name__ == "__main__":
    main()
