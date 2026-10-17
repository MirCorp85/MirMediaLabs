"""Cloud brains — Claude (Anthropic), GPT (OpenAI) or GLM (Fireworks) as MirAI, the Director and the prompt writer.

OWNER ONLY: every call is billed to the owner's own API key (stored in data/prefs.json, never sent to any
client, never committed). Invited people always stay on the free local engine. A monthly $ cap switches the
owner back to local when reached. Both SDKs are imported lazily — a build without them simply has no cloud.

The worker thread activates the brain for the job it runs (activate / active), so core.ask, MirAI chat and
the Director all follow the same per-job choice without extra plumbing.
"""
import json
import os
import re
import threading
import time

import core

# price per 1M tokens (input, output) in USD
CLAUDE = [
    {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "price": (4.0, 20.0), "note": "recommended · newest Opus"},
    {"id": "claude-opus-5", "label": "Claude Opus 5", "price": (5.0, 25.0), "note": ""},
    {"id": "claude-fable-5-1", "label": "Claude Fable 5.1", "price": (10.0, 50.0), "note": "most capable · slower"},
    {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "price": (2.0, 10.0), "note": "fast · cheaper"},
]
# OpenAI ids come from the live model list when the key is saved; prices matched by family
GPT_PRICES = [("6-astra", (10.0, 50.0)), ("6-luna", (0.1, 0.5)), ("5.6-sol", (4.0, 20.0)), ("5.6-terra", (2.0, 12.0)),
              ("5.6-luna", (0.2, 1.2)), ("5.5-pro", (30.0, 180.0)), ("5.5", (5.0, 30.0)), ("5.4-mini", (0.75, 4.5)),
              ("5.4-nano", (0.2, 1.25)), ("5.4", (2.5, 15.0))]
# Fireworks (OpenAI-compatible API) — open-weight models; GLM is text-only, so pictures stay out of its prompts
FIREWORKS = [
    {"id": "accounts/fireworks/models/glm-5p3", "label": "GLM 5.3", "price": (1.40, 4.40), "note": "Zhipu GLM via Fireworks · price est. (5.2 rates)"},
    {"id": "accounts/fireworks/routers/glm-5p3-fast", "label": "GLM 5.3 Fast", "price": (2.10, 6.60), "note": "faster replies · price est."},
    {"id": "accounts/fireworks/models/glm-5p3-flash", "label": "GLM 5.3 Flash", "price": (1.40, 4.40), "note": "lighter · price est. (cap counts high)"},
    {"id": "accounts/fireworks/routers/glm-5p2-fast", "label": "GLM 5.2 Fast", "price": (2.10, 6.60), "note": "older"},
]
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1"
PROVIDERS = ("anthropic", "openai", "fireworks")
NAMES = {"anthropic": "Anthropic", "openai": "OpenAI", "fireworks": "Fireworks"}
UNKNOWN_PRICE = (10.0, 50.0)          # conservative when a model isn't in the table
FALLBACKS_OK = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
USAGE_FILE = core.os.path.join(core.DATA, "cloud_usage.json")
DEFAULT_CAP = 20.0
_T = threading.local()
_ULOCK = threading.Lock()


class CloudError(RuntimeError):
    pass


# ── settings (owner) ─────────────────────────────────────────────────────────
def keys():
    p = core.prefs()
    return {k: p.get(k + "_key") or "" for k in PROVIDERS}


def brain():
    b = core.prefs().get("brain") or {}
    prov = b.get("provider") if b.get("provider") in PROVIDERS else "local"
    return {"provider": prov, "model": b.get("model") or ""}


def cap():
    try:
        return max(0.0, float(core.prefs().get("cloud_cap", DEFAULT_CAP)))
    except (TypeError, ValueError):
        return DEFAULT_CAP


def gpt_models():
    return core.prefs().get("openai_models") or []


def models():
    """Every pickable cloud model with its price (for the Settings picker)."""
    out = [dict(m, provider="anthropic", price=list(m["price"])) for m in CLAUDE]
    for mid in gpt_models():
        out.append({"id": mid, "label": mid.replace("gpt-", "GPT-"), "provider": "openai",
                    "price": list(price_of(mid)), "note": ""})
    live = core.prefs().get("fireworks_models")          # ids that answered when the key was saved
    out += [dict(m, provider="fireworks", price=list(m["price"])) for m in FIREWORKS if not live or m["id"] in live]
    for m in out:
        m["ctx"] = CTX[m["provider"]]
        m["vision"] = m["provider"] != "fireworks"
        m["params"] = params().get(m["id"]) or {}
    return out


CTX = {"anthropic": 1000000, "openai": 400000, "fireworks": 202752}
EFFORTS = ("auto", "low", "medium", "high")


def params():
    """Per-model tuning saved from the model picker: {model_id: {max_out, temperature, effort}}."""
    return core.prefs().get("brain_params") or {}


def param_of(model, key, default=None):
    v = (params().get(model) or {}).get(key)
    return default if v in (None, "", "auto") else v


def set_params(model, p):
    allp = params()
    if not p:
        allp.pop(model, None)
    else:
        clean = {}
        try:
            if p.get("max_out") not in (None, ""):
                clean["max_out"] = max(256, min(int(p["max_out"]), 64000))
            if p.get("temperature") not in (None, ""):
                clean["temperature"] = round(max(0.0, min(float(p["temperature"]), 2.0)), 2)
        except (TypeError, ValueError):
            raise CloudError("max output and temperature must be numbers")
        if p.get("effort") in EFFORTS:
            clean["effort"] = p["effort"]
        allp[model] = clean
    core.save_pref("brain_params", allp)


def price_of(model):
    for m in CLAUDE + FIREWORKS:
        if m["id"] == model:
            return m["price"]
    k = model.lower().replace("gpt-", "")
    for fam, pr in GPT_PRICES:
        if k.startswith(fam):
            return pr
    return UNKNOWN_PRICE


def label_of(b):
    if not b or b.get("provider") == "local":
        return ""
    return next((m["label"] for m in CLAUDE + FIREWORKS if m["id"] == b["model"]), b["model"])


def sees(b):
    """Can this brain look at pictures? (GLM 5.2 is text-only)"""
    return bool(b) and b.get("provider") in ("anthropic", "openai")


# ── per-job activation (owner only) ─────────────────────────────────────────
def for_job(job):
    """The cloud brain this job should use, or None (local). Owner's jobs only; cap enforced."""
    if (job.get("user") or "owner") != "owner":
        return None
    b = brain()
    if b["provider"] == "local" or not b["model"] or not keys().get(b["provider"]):
        return None
    if spent() >= cap():
        return None
    return b


def activate(b):
    _T.brain = b


def active():
    return getattr(_T, "brain", None)


# ── usage / cost ─────────────────────────────────────────────────────────────
def _month():
    return time.strftime("%Y-%m")


def usage():
    u = core.load_json(USAGE_FILE, {})
    return u if u.get("month") == _month() else {"month": _month(), "usd": 0.0, "calls": 0, "in": 0, "out": 0}


def spent():
    return float(usage().get("usd") or 0.0)


def _record(model, tin, tout):
    core.tok_add(tin, tout)
    pi, po = price_of(model)
    with _ULOCK:
        u = usage()
        u["usd"] = round(float(u.get("usd") or 0) + tin * pi / 1e6 + tout * po / 1e6, 6)
        u["calls"] = int(u.get("calls") or 0) + 1
        u["in"] = int(u.get("in") or 0) + int(tin or 0)
        u["out"] = int(u.get("out") or 0) + int(tout or 0)
        core.save_json(USAGE_FILE, u)


# ── helpers ──────────────────────────────────────────────────────────────────
def _mime(b64):
    head = b64[:12]
    return "image/png" if head.startswith("iVBOR") else "image/webp" if head.startswith("UklGR") else "image/jpeg"


def _effort(role, model=""):
    e = param_of(model, "effort")
    if e:
        return e
    return {"director": "low", "prompt": "medium", "chat": "medium", "long": "high"}.get(role, "medium")


def _anthropic():
    try:
        import anthropic
    except ImportError:
        raise CloudError("this build has no Anthropic support (anthropic package missing)")
    return anthropic, anthropic.Anthropic(api_key=keys()["anthropic"], max_retries=2)


def _openai(provider="openai", key=None):
    """OpenAI SDK client — for OpenAI itself, or Fireworks' OpenAI-compatible endpoint."""
    try:
        import openai
    except ImportError:
        raise CloudError("this build has no OpenAI-compatible support (openai package missing)")
    kw = {"base_url": FIREWORKS_URL} if provider == "fireworks" else {}
    return openai, openai.OpenAI(api_key=key or keys()[provider], max_retries=2, **kw)


def _tok(provider, n):
    # Fireworks takes max_tokens; OpenAI's newer models want max_completion_tokens
    return {"max_tokens": n} if provider == "fireworks" else {"max_completion_tokens": n}


def _temp(model):
    t = param_of(model, "temperature")
    return {"temperature": t} if t is not None else {}


def _a_extra(model):
    # opt into server-side refusal fallback by default: a declined request is re-run on Anthropic's pick
    return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACKS_OK else {}


def _a_text(resp):
    if resp.stop_reason == "refusal":
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        raise CloudError("Claude declined this request%s" % (" (%s)" % cat if cat else ""))
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _a_err(anthropic, e):
    if isinstance(e, anthropic.AuthenticationError):
        return CloudError("Anthropic rejected the API key — check it in Settings → Cloud brain")
    if isinstance(e, anthropic.PermissionDeniedError):
        return CloudError("this Anthropic key can't use that model")
    if isinstance(e, anthropic.NotFoundError):
        return CloudError("Anthropic doesn't know that model id")
    if isinstance(e, anthropic.RateLimitError):
        ra = e.response.headers.get("retry-after", "") if getattr(e, "response", None) is not None else ""
        return CloudError("Anthropic rate limit — try again%s" % (" in %ss" % ra if ra else " shortly"))
    if isinstance(e, anthropic.APIStatusError):
        return CloudError("Anthropic error %s: %s" % (e.status_code, getattr(e, "message", e)))
    if isinstance(e, anthropic.APIConnectionError):
        return CloudError("can't reach Anthropic — check the internet connection")
    return CloudError(str(e))


def _o_err(openai, e, provider="openai"):
    n = NAMES.get(provider, "OpenAI")
    if isinstance(e, openai.AuthenticationError):
        return CloudError("%s rejected the API key — check it in Settings → Cloud brain" % n)
    if isinstance(e, openai.RateLimitError):
        return CloudError("%s rate limit or out of credit — check your %s billing" % (n, n))
    if isinstance(e, openai.NotFoundError):
        return CloudError("%s doesn't know that model id" % n)
    if isinstance(e, openai.APIStatusError):
        return CloudError("%s error %s: %s" % (n, e.status_code, getattr(e, "message", e)))
    if isinstance(e, openai.APIConnectionError):
        return CloudError("can't reach %s — check the internet connection" % n)
    return CloudError(str(e))


def json_of(text):
    """First JSON object in a reply (models sometimes wrap it in prose or ``` fences)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise CloudError("the cloud brain didn't return JSON")
    return json.loads(m.group(0))


# ── one-shot ask (prompt writer, Director) ───────────────────────────────────
def ask(b, prompt, system, images=None, want_json=False, role="prompt", timeout=180, max_tokens=16000):
    if b["provider"] == "anthropic":
        anthropic, client = _anthropic()
        content = [{"type": "image", "source": {"type": "base64", "media_type": _mime(i), "data": i}} for i in (images or [])]
        content.append({"type": "text", "text": prompt + ("\n\nReply with one JSON object only." if want_json else "")})
        try:
            resp = client.with_options(timeout=timeout).beta.messages.create(
                model=b["model"], max_tokens=int(param_of(b["model"], "max_out", max_tokens)), system=system,
                output_config={"effort": _effort(role, b["model"])},
                messages=[{"role": "user", "content": content}], **_a_extra(b["model"]))
        except anthropic.APIError as e:
            raise _a_err(anthropic, e)
        _record(b["model"], resp.usage.input_tokens or 0, resp.usage.output_tokens or 0)
        return _a_text(resp)
    prov = b["provider"]
    openai, client = _openai(prov)
    pics = images if sees(b) else []
    content = [{"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (_mime(i), i)}} for i in (pics or [])]
    content.append({"type": "text", "text": prompt})
    kw = {"response_format": {"type": "json_object"}} if want_json else {}
    try:
        r = client.with_options(timeout=timeout).chat.completions.create(
            model=b["model"], **_tok(prov, int(param_of(b["model"], "max_out", max_tokens))), **_temp(b["model"]),
            messages=[{"role": "system", "content": system + ("\nReply in JSON." if want_json else "")},
                      {"role": "user", "content": content if pics else prompt}], **kw)
    except openai.APIError as e:
        raise _o_err(openai, e, prov)
    if r.usage:
        _record(b["model"], r.usage.prompt_tokens or 0, r.usage.completion_tokens or 0)
    return (r.choices[0].message.content or "").strip()


# ── streamed chat (MirAI) ─────────────────────────────────────────────────────
def chat_stream(b, msgs, on_text, cancelled, long=False, max_tokens=16000):
    """msgs: OpenAI-style [{"role": "system"|"user"|"assistant", "content": str}]. Calls on_text(chunk)."""
    system = "\n\n".join(m["content"] for m in msgs if m["role"] == "system")
    conv = [m for m in msgs if m["role"] != "system"]
    if b["provider"] == "anthropic":
        anthropic, client = _anthropic()
        try:
            with client.with_options(timeout=900).beta.messages.stream(
                    model=b["model"], max_tokens=int(param_of(b["model"], "max_out", max_tokens)), system=system,
                    output_config={"effort": _effort("long" if long else "chat", b["model"])},
                    messages=conv, **_a_extra(b["model"])) as stream:
                for text in stream.text_stream:
                    if cancelled():
                        raise _Stop()
                    on_text(text)
                final = stream.get_final_message()
        except _Stop:
            return
        except anthropic.APIError as e:
            raise _a_err(anthropic, e)
        _record(b["model"], final.usage.input_tokens or 0, final.usage.output_tokens or 0)
        if final.stop_reason == "refusal":
            raise CloudError("Claude declined to answer that")
        return
    prov = b["provider"]
    openai, client = _openai(prov)
    try:
        stream = client.with_options(timeout=900).chat.completions.create(
            model=b["model"], **_tok(prov, int(param_of(b["model"], "max_out", max_tokens))), **_temp(b["model"]), stream=True, stream_options={"include_usage": True},
            messages=([{"role": "system", "content": system}] if system else []) + conv)
        for ch in stream:
            if cancelled():
                stream.close()
                return
            if ch.choices and ch.choices[0].delta and ch.choices[0].delta.content:
                on_text(ch.choices[0].delta.content)
            if getattr(ch, "usage", None):
                _record(b["model"], ch.usage.prompt_tokens or 0, ch.usage.completion_tokens or 0)
    except openai.APIError as e:
        raise _o_err(openai, e, prov)


class _Stop(Exception):
    pass


# ── key check (Settings) ─────────────────────────────────────────────────────
def check_key(provider, key):
    """Validate a key with a free model-list call. → list of usable model ids (OpenAI) / [] (Anthropic)."""
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            raise CloudError("this build has no Anthropic support")
        try:
            anthropic.Anthropic(api_key=key, max_retries=1).with_options(timeout=20).models.list(limit=5)
        except anthropic.APIError as e:
            raise _a_err(anthropic, e)
        return []
    openai, client = _openai(provider, key)
    if provider == "fireworks":
        # 1-token call per GLM id: a bad key fails on the first one; "model not found / not deployed" only
        # means that id isn't served on a plain key (plain GLM 5.2 often isn't — the GLM 5.2 Fast router is)
        ok, last = [], None
        for m in FIREWORKS:
            try:
                client.with_options(timeout=30, max_retries=1).chat.completions.create(
                    model=m["id"], max_tokens=1, messages=[{"role": "user", "content": "hi"}])
                ok.append(m["id"])
            except (openai.AuthenticationError, openai.PermissionDeniedError, openai.APIConnectionError) as e:
                raise _o_err(openai, e, provider)
            except openai.APIError as e:
                last = e
        if not ok:
            raise CloudError("the key works, but Fireworks serves none of the GLM models to it (%s)"
                             % (getattr(last, "message", None) or last or "not deployed"))
        return ok
    try:
        ids = [m.id for m in client.with_options(timeout=20, max_retries=1).models.list()]
    except openai.APIError as e:
        raise _o_err(openai, e)
    skip = ("audio", "realtime", "tts", "transcribe", "image", "search", "embedding", "moderation", "instruct", "codex")
    chat = sorted({i for i in ids if i.startswith("gpt-") and not any(s in i for s in skip)
                   and not re.search(r"-\d{4}-\d{2}-\d{2}$", i)}, reverse=True)
    return chat[:20]


def _refresh_fireworks():
    """The GLM list changed since the key was checked (e.g. GLM 5.2 → 5.3): re-test it once, in the background."""
    ids = [m["id"] for m in FIREWORKS]
    p = core.prefs()
    if not p.get("fireworks_key") or p.get("fireworks_checked") == ids:
        return
    core.save_pref("fireworks_checked", ids)

    def run():
        try:
            ok = check_key("fireworks", p["fireworks_key"])
            core.save_pref("fireworks_models", ok)
            b0 = brain()
            if b0["provider"] == "fireworks" and b0["model"] not in ok:
                core.save_pref("brain", {"provider": "fireworks", "model": ok[0]})
        except Exception:
            pass
    threading.Thread(target=run, daemon=True, name="mml-fw-recheck").start()


def local_engines():
    """Every language model Ollama has on this PC, found automatically (nothing to configure): chat-capable ones only
    (embedding models are skipped), tested ones first, with vision / size / context from Ollama itself."""
    try:
        tags = core.requests.get(core.OLLAMA + "/api/tags", timeout=3).json().get("models", [])
    except Exception:
        tags = None
    want = core.prefs().get("engine_model") or core.DEFAULT_ENGINE
    names = [m["name"] for m in tags or []]
    out = [dict(e, ctx=16384, installed=None if tags is None else any(t == e["model"] or t.startswith(e["model"] + "-") for t in names),
                current=want == e["model"]) for e in core.LOCAL_ENGINES]
    known = {e["model"] for e in core.LOCAL_ENGINES}
    for m in tags or []:
        t, caps, det = m["name"], m.get("capabilities"), m.get("details") or {}
        if t in known:
            continue
        if caps is not None and "completion" not in caps:          # embedding / reranker models can't chat
            continue
        if caps is None and re.search(r"embed|bge|nomic|minilm|rerank", t, re.I):
            continue
        bits = [det.get("parameter_size"), det.get("quantization_level")]
        out.append({"model": t, "label": core.pretty_tag(t), "note": " · ".join(x for x in bits if x) or "installed on this PC",
                    "vision": bool(caps and "vision" in caps), "gb": round((m.get("size") or 0) / 1e9, 1) or None,
                    "ctx": min(int(det.get("context_length") or 16384), 131072), "installed": True, "current": want == t})
    return out


# GGUF model files other apps downloaded (LM Studio, Jan, GPT4All, KoboldCpp, Hugging Face...) — one click adds them to
# Ollama so MirAI can use them. Only files under these folders are ever offered or imported.
GGUF_DIRS = [os.path.join(os.path.expanduser("~"), *p) for p in (
    (".lmstudio", "models"), (".cache", "lm-studio", "models"), ("AppData", "Roaming", "Jan", "data", "models"),
    ("jan", "models"), ("AppData", "Local", "nomic.ai", "GPT4All"), (".cache", "huggingface", "hub"), ("models",),
    ("Documents", "models"), ("Downloads",))] + [p for p in (core.CONFIG.get("gguf_dirs") or []) if isinstance(p, str)]
_FOUND = {"t": 0, "rows": []}


def found_gguf(force=False):
    if not force and time.time() - _FOUND["t"] < 120:
        return _FOUND["rows"]
    try:
        have = {m["name"] for m in core.requests.get(core.OLLAMA + "/api/tags", timeout=3).json().get("models", [])}
    except Exception:
        have = set()
    rows, seen = [], set()
    for root in GGUF_DIRS:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            if dp[len(root):].count(os.sep) > 5:
                dn[:] = []
                continue
            dn[:] = [d for d in dn if not d.startswith(".") or d in (".internal",)]
            for f in fn:
                low = f.lower()
                if not low.endswith(".gguf") or "mmproj" in low or re.search(r"embed|bge|nomic|minilm|rerank", low) \
                        or re.search(r"-0000[2-9]-of-", low):
                    continue
                path = os.path.join(dp, f)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size < 300e6 or f in seen:
                    continue
                seen.add(f)
                name = import_name(path)
                rows.append({"path": path, "file": f, "gb": round(size / 1e9, 1), "name": name,
                             "label": core.pretty_tag(name.split("/")[-1]), "added": name in have or name + ":latest" in have,
                             "app": next((a for k, a in (("lmstudio", "LM Studio"), ("lm-studio", "LM Studio"), ("jan", "Jan"),
                                                         ("gpt4all", "GPT4All"), ("huggingface", "Hugging Face")) if k in path.lower()), "this PC")})
    _FOUND.update(t=time.time(), rows=rows)
    return rows


def import_name(path):
    base = re.sub(r"\.gguf$", "", os.path.basename(path), flags=re.I).lower()
    base = re.sub(r"[^a-z0-9._-]+", "-", base).strip("-.")[:60] or "model"
    return "mml-" + base


_IMPORT = {}


def import_gguf(path):
    """ollama create <name> from a found GGUF (runs in the background; poll found_gguf / summary)."""
    row = next((r for r in found_gguf(force=True) if os.path.normcase(r["path"]) == os.path.normcase(path)), None)
    if not row:
        raise ValueError("that file isn't one of the models found on this PC")
    if _IMPORT.get(row["name"]) == "running":
        return row["name"]
    import subprocess
    import tempfile

    def run():
        _IMPORT[row["name"]] = "running"
        mf = os.path.join(tempfile.gettempdir(), "mml_%s.Modelfile" % row["name"])
        try:
            with open(mf, "w", encoding="utf-8") as f:
                f.write('FROM "%s"\n' % row["path"])
            exe = core.CONFIG.get("ollama_exe") or "ollama"
            r = subprocess.run([exe, "create", row["name"], "-f", mf], capture_output=True, text=True, timeout=3600,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            _IMPORT[row["name"]] = "done" if r.returncode == 0 else ("error: " + (r.stderr or r.stdout)[-200:])
        except Exception as e:
            _IMPORT[row["name"]] = "error: " + str(e)[:200]
        finally:
            _FOUND["t"] = 0
            try:
                os.remove(mf)
            except OSError:
                pass
    threading.Thread(target=run, daemon=True, name="mml-gguf-import").start()
    return row["name"]


def summary():
    """Settings view — never contains a key."""
    _refresh_fireworks()
    k = keys()
    return {"keys": {p: bool(v) for p, v in k.items()}, "brain": brain(), "models": models(),
            "local": {"label": core.engine_label(), "model": core.engine_model(), "ctx": 16384,
                      "picked": core.prefs().get("engine_model") or core.DEFAULT_ENGINE},
            "locals": local_engines(),
            "found": [dict(r, importing=_IMPORT.get(r["name"])) for r in found_gguf()],
            "usage": usage(), "cap": cap(), "over_cap": spent() >= cap()}
