"""Upload-a-song path, driven through the lab API: a new episode on an existing series, the song uploaded as a
reference, filed as the episode's master song, then the background run started (it recognises the lyrics itself).

    python tools/series_upload_test.py <series id> <song file in the library> [res]
"""
import json
import os
import sys
import urllib.request
import uuid

LAB = "http://127.0.0.1:5400"
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "library")


def api(path, body=None):
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def upload(path):
    b = uuid.uuid4().hex
    head = ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: audio/mpeg\r\n\r\n'
            % (b, os.path.basename(path)))
    body = head.encode() + open(path, "rb").read() + ("\r\n--%s--\r\n" % b).encode()
    req = urllib.request.Request(LAB + "/api/upload", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + b})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))["name"]


sid, song = sys.argv[1], sys.argv[2]
res = sys.argv[3] if len(sys.argv) > 3 else "standard"
d = api("/api/series/" + sid)
d["setup"] = dict(d.get("setup") or {}, res=res, clip=10)
eid = "upload%06d" % (uuid.uuid4().int % 1000000)
d["episodes"].append({"id": eid, "title": "My hometown by the sea", "idea": "Pip remembers growing up in a seaside town",
                      "lesson": "", "cast": [c["id"] for c in d["characters"]], "seconds": 10})
d = api("/api/series", d)
ref = upload(os.path.join(LIB, song))
print("uploaded", ref)
d = api("/api/series/%s/episode/%s/usesong" % (sid, eid), {"ref": ref})
ep = next(e for e in d["episodes"] if e["id"] == eid)
print("song", ep["song"], ep["song_secs"], "s · provisional shots", len(ep.get("chunks") or []))
r = api("/api/series/%s/run" % sid, {"action": "start", "episode": eid})
print("run", json.dumps(r.get("run"), indent=0)[:400], "next", r.get("next"))
print("EPISODE", eid)
