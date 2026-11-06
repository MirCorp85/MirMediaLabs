"""DESIGN: ComfyArt (jtydhr88, MIT; canvas = tldraw SDK, own licence, dev mode on localhost / plain http) inside the lab.

ComfyArt is a ComfyUI custom node (custom_nodes/ComfyArt — Setup installs it) that serves its app at :8188/comfyart/
with ROOT paths (/api, /comfyart, /view_metadata, /ws). Phones only reach the lab's port, so this module mounts the
whole ComfyUI origin at /design/* (owner only):
  * text assets (html/js/css) get their root-path string literals prefixed with /design (cached per asset);
  * index.html gets a tiny shim that prefixes the same paths at runtime (fetch/XHR/WebSocket/EventSource/src/href),
    which covers image URLs stored inside projects (/api/view?...) and URLs the agent returns;
  * /design/ws is bridged to ComfyUI's /ws by medialab.py (flask-sock, when installed) via ws_bridge().
ComfyArt's own Agent stays OFF (MirAI is the agent). A POST /api/prompt takes the lab's GPU handoff (render lock +
Ollama eviction) like CopyCat, released when the prompt leaves ComfyUI's queue."""
import re
import threading
import time
from urllib.parse import urlencode

import requests
from flask import Response, jsonify, redirect, request, stream_with_context

COMFY = "http://127.0.0.1:8188"
BASE = "/design"
ENTRY = BASE + "/comfyart/"
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
        "upgrade", "host", "content-length", "cookie", "authorization", "origin", "referer", "x-forwarded-for",
        "x-forwarded-host", "x-forwarded-proto", "accept-encoding", "content-encoding"}
_S = requests.Session()
_S.trust_env = False
_LOCK = threading.Lock()
_CACHE = {}                    # hashed asset path -> rewritten bytes
_ACTIVE = set()                # prompt ids holding the GPU handoff
_PARKED = []
_STARTING = []

# root-path string literals in ComfyArt's bundle: "/api…", '/comfyart…', `/view_metadata…`, url(/comfyart…), '/ws'
_LIT = re.compile(r"""(["'`(])/(api|comfyart|view_metadata)(?=[/?$"'`)])""")
_WS = re.compile(r"""(["'`])/ws\1""")

SHIM = r"""<script>(function(){var P='%s',R=/^\/(api|comfyart|view_metadata|ws)(\/|\?|$)/;
function fx(u){try{if(u==null)return u;var s=String(u);if(s.charAt(0)==='/'&&s.charAt(1)!=='/'){return R.test(s)?P+s:s}
var x=new URL(s,location.href);if(x.host===location.host&&R.test(x.pathname)){x.pathname=P+x.pathname;return x.href}}catch(e){}return u}
var F=window.fetch;window.fetch=function(i,o){if(i instanceof Request){var n=fx(i.url);if(n!==i.url)i=new Request(n,i)}else i=fx(i);return F.call(this,i,o)};
var XO=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){arguments[1]=fx(u);return XO.apply(this,arguments)};
var W=window.WebSocket;function WS(u,p){return p===undefined?new W(fx(u)):new W(fx(u),p)}WS.prototype=W.prototype;['CONNECTING','OPEN','CLOSING','CLOSED'].forEach(function(k){WS[k]=W[k]});window.WebSocket=WS;
if(window.EventSource){var E=window.EventSource;var ES=function(u,o){return new E(fx(u),o)};ES.prototype=E.prototype;window.EventSource=ES}
var SA=Element.prototype.setAttribute;Element.prototype.setAttribute=function(n,v){var k=String(n).toLowerCase();if(k==='src'||k==='href'||k==='poster')v=fx(v);return SA.call(this,n,v)};
[[HTMLImageElement,'src'],[HTMLMediaElement,'src'],[HTMLSourceElement,'src'],[HTMLAnchorElement,'href'],[HTMLLinkElement,'href'],[HTMLVideoElement,'poster'],[HTMLScriptElement,'src']].forEach(function(p){
var d=Object.getOwnPropertyDescriptor(p[0].prototype,p[1]);if(!d||!d.set)return;Object.defineProperty(p[0].prototype,p[1],{configurable:true,enumerable:d.enumerable,get:d.get,set:function(v){d.set.call(this,fx(v))}})});
var WO=window.open;window.open=function(u){arguments[0]=fx(u);return WO.apply(this,arguments)};
})();</script>""" % BASE

STARTING_PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Design</title><body style="margin:0;height:100vh;display:grid;place-items:center;background:#08080A;color:#ccc;
font:15px system-ui"><div style="text-align:center"><div style="font-size:20px;color:#eee;margin-bottom:8px">Starting the
ComfyUI engine&hellip;</div><div>Design opens by itself in a moment.</div></div>
<script>setTimeout(function(){location.reload()},4000)</script></body>"""


def _core():
    import core
    return core


def _comfy():
    import comfy
    return comfy


def _start_bg():
    if _STARTING:
        return
    _STARTING.append(1)

    def go():
        try:
            _comfy().start(wait=True)
        except Exception:
            pass
        finally:
            _STARTING.clear()
    threading.Thread(target=go, daemon=True, name="design-comfy-start").start()


def installed():
    import os
    root = _comfy().COMFY_ROOT
    return any(os.path.isfile(os.path.join(root, *sub, "custom_nodes", "ComfyArt", "__init__.py")) for sub in (("ComfyUI",), ()))


def status():
    up = False
    try:
        up = _comfy().up()
    except Exception:
        pass
    return {"installed": installed(), "comfy_up": up, "starting": bool(_STARTING), "gpu_jobs": len(_ACTIVE)}


# ── GPU handoff (same rules as CopyCat: never steal from another lab render; ComfyUI queues us behind it) ──
def _gpu_take():
    core = _core()
    with _LOCK:
        held = core.rendering()
        if held and not str(held.get("job", "")).startswith("design"):
            return False
        first = not _ACTIVE
        core.render_lock("design")
    if first:
        try:
            parked = [(m["name"], m.get("context_length")) for m in
                      core.requests.get(core.OLLAMA + "/api/ps", timeout=5).json().get("models", [])]
        except Exception:
            parked = []
        _PARKED[:] = parked or _PARKED
        core.evict_ollama()
    return True


def _gpu_give():
    core = _core()
    with _LOCK:
        if _ACTIVE:
            return
        held = core.rendering()
        if held and str(held.get("job", "")).startswith("design"):
            core.render_unlock()
        parked, _PARKED[:] = list(_PARKED), []
    for name, ctx in parked:                       # the heart engine back as it was (pinned, keep_alive -1)
        body = {"model": name, "prompt": "", "keep_alive": -1}
        if ctx:
            body["options"] = {"num_ctx": int(ctx)}
        try:
            core.requests.post(core.OLLAMA + "/api/generate", json=body, timeout=180)
        except Exception:
            pass


def _watch(pid):
    t0 = time.time()
    try:
        while time.time() - t0 < 3 * 3600:
            time.sleep(5)
            try:
                q = _S.get(COMFY + "/queue", timeout=10).json()
                ids = {e[1] for e in (q.get("queue_running") or []) + (q.get("queue_pending") or []) if len(e) > 1}
            except Exception:
                continue
            if pid not in ids:
                break
    finally:
        with _LOCK:
            _ACTIVE.discard(pid)
        _gpu_give()


# ── the proxy ──
# workflow file -> lighter file Setup installed instead (16 GB card). Swapped only while the original is absent.
ALIASES = {"qwen_image_layered_bf16.safetensors": ("diffusion_models", "qwen_image_layered_fp8mixed.safetensors")}


def _alias(raw):
    import os
    try:
        root = os.path.join(_comfy().COMFY_SHARED, "models")
        for src, (folder, dst) in ALIASES.items():
            if src.encode() in raw and not os.path.isfile(os.path.join(root, folder, src)) \
                    and os.path.isfile(os.path.join(root, folder, dst)):
                raw = raw.replace(src.encode(), dst.encode())
    except Exception:
        pass
    return raw


def _rewrite(body, ctype):
    t = body.decode("utf-8", "replace")
    t = _LIT.sub(lambda m: m.group(1) + BASE + "/" + m.group(2), t)
    t = _WS.sub(lambda m: m.group(1) + BASE + "/ws" + m.group(1), t)
    if "html" in ctype:
        t = t.replace("<head>", "<head>" + SHIM, 1)
    return t.encode("utf-8")


def proxy(sub, hk):
    if not hk["is_owner"]():
        return jsonify({"error": "Design is owner-only."}), 403
    try:
        up_ = _comfy().up()
    except Exception:
        up_ = False
    if not up_:
        _start_bg()
        if request.method == "GET" and sub in ("comfyart/", "comfyart"):
            return Response(STARTING_PAGE, mimetype="text/html", headers={"Cache-Control": "no-cache"})
        return jsonify({"error": "ComfyUI is starting"}), 503
    if not installed():
        return jsonify({"error": "ComfyArt isn't installed yet: run Setup → Modify → Design canvas"}), 503
    key = sub if request.method == "GET" and sub.startswith("comfyart/assets/") else None
    if key and key in _CACHE:
        body, ctype = _CACHE[key]
        return Response(body, mimetype=None, headers={"Content-Type": ctype, "Cache-Control": "public, max-age=31536000"})
    hdr = {k: v for k, v in request.headers.items() if k.lower() not in _HOP}
    hdr["Host"] = "127.0.0.1:8188"
    hdr["Accept-Encoding"] = "identity"
    if request.headers.get("Origin"):
        hdr["Origin"] = COMFY                      # ComfyUI refuses Origin != Host; the lab's key gate already ran
    body = None
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        n = request.content_length
        if n:
            from copycat import _Sized
            body = _Sized(request.stream, n)
    submit = request.method == "POST" and sub.strip("/") == "api/prompt"
    if submit and request.content_length and request.content_length < 64 << 20:
        body = _alias(request.get_data())           # small JSON graph: swap model files we installed in a lighter variant
    took = False
    if submit:
        try:
            took = _gpu_take()
        except Exception:
            took = False
    try:
        r = _S.request(request.method, COMFY + "/" + sub, params=request.args, headers=hdr, data=body, stream=True,
                       allow_redirects=False, timeout=(10, 900))
    except requests.RequestException as e:
        if took:
            _gpu_give()
        return jsonify({"error": "ComfyUI unreachable: %s" % e}), 502
    except BaseException:
        if took:
            _gpu_give()
        raise
    ctype = r.headers.get("Content-Type", "")
    out = [(k, v) for k, v in r.raw.headers.items() if k.lower() not in _HOP]
    out = [(k, (BASE + v) if k.lower() == "location" and v.startswith("/") else v) for k, v in out]
    if submit:
        data = r.content
        pid = None
        try:
            pid = r.json().get("prompt_id") if r.ok else None
        except ValueError:
            pass
        if took:
            if pid:
                with _LOCK:
                    _ACTIVE.add(pid)
                threading.Thread(target=_watch, args=(pid,), daemon=True, name="design-gpu-" + pid[:8]).start()
            else:
                _gpu_give()
        return Response(data, status=r.status_code, headers=out)
    text = any(t in ctype for t in ("text/html", "javascript", "text/css"))
    if text and sub.startswith("comfyart"):
        data = _rewrite(r.content, ctype)
        r.close()
        if key and r.ok:
            _CACHE[key] = (data, ctype)
        if "html" in ctype:
            out = [(k, v) for k, v in out if k.lower() != "cache-control"] + [("Cache-Control", "no-cache")]
        return Response(data, status=r.status_code, headers=out)

    def gen():
        try:
            for ch in r.iter_content(chunk_size=None):
                if ch:
                    yield ch
        finally:
            r.close()
    cl = r.headers.get("Content-Length")
    if cl:
        out.append(("Content-Length", cl))
    return Response(stream_with_context(gen()) if request.method != "HEAD" else b"", status=r.status_code,
                    headers=out, direct_passthrough=True)


def ws_bridge(ws):
    """/design/ws <-> ComfyUI /ws (progress + executed events). Called from medialab.py's flask-sock route."""
    from websockets.sync.client import connect
    q = {k: v for k, v in request.args.items()}
    try:
        up = connect("ws://127.0.0.1:8188/ws?" + urlencode(q), max_size=None, open_timeout=5,
                     origin="http://127.0.0.1:8188")
    except Exception:
        return
    stop = threading.Event()

    def down():
        try:
            for m in up:
                ws.send(m)
        except Exception:
            pass
        finally:
            stop.set()
            try:
                ws.close()
            except Exception:
                pass
    threading.Thread(target=down, daemon=True, name="design-ws").start()
    try:
        while not stop.is_set():
            m = ws.receive(timeout=1)
            if m is not None:
                up.send(m)
    except Exception:
        pass
    finally:
        stop.set()
        try:
            up.close()
        except Exception:
            pass


def register(app, hk):
    M = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    @app.route("/design", methods=["GET"])
    @app.route("/design/", methods=["GET"])
    def design_root():
        return redirect(ENTRY)

    @app.route("/design/<path:sub>", methods=M)
    def design_sub(sub):
        if request.path.endswith("/") and not sub.endswith("/"):
            sub += "/"
        # ComfyArt's api() helper prepends "/api" to a path literal that was already prefixed
        # (`/api${'/design/comfyart/…'}`) — the prefix never belongs inside a ComfyUI path, so drop it
        # keep the path ENCODED: Flask decodes %2F, and ComfyUI's /api/userdata/comfyart%2Fx.json needs it as-is
        raw = (request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or "").split("?", 1)[0]
        i = raw.find(BASE + "/")
        if i >= 0 and "%2f" in raw.lower():
            sub = raw[i + len(BASE) + 1:]
        sub = sub.replace(BASE.strip("/") + "/", "")
        return proxy(sub, hk)

    @app.route("/api/design/status")
    def design_status():
        return jsonify(status())
