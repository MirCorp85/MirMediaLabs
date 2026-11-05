"""Where the add-on engines live (Studio apps, CopyCat, Kinetic, expressive voice, sound effects).

Every path can be set in mml_config.json (the key named below), with an environment variable, or in Settings
(data/prefs.json, same key). The defaults sit inside the install, where Setup puts them, so nothing here ever
points at one particular PC."""
import os
import shutil

import core

ENGINES = None      # set below


def _pref(key):
    try:
        return (core.prefs() or {}).get(key)
    except Exception:
        return None


def path(key, env, default):
    v = (core.CONFIG.get(key) if isinstance(core.CONFIG, dict) else None) or os.environ.get(env) or _pref(key)
    return os.path.abspath(os.path.expanduser(str(v))) if v else default


ENGINES = path("engines_dir", "MML_ENGINES_DIR", os.path.join(core.ROOT, "engines"))


def freefield():
    """neuregex/freefield (MIT) — the Studio app catalogue. Setup downloads it here."""
    return path("freefield_dir", "MML_FREEFIELD_DIR", os.path.join(ENGINES, "freefield"))


def studio_packs():
    """App packs that ship with the lab (OpenField, MIT) — never inside the freefield download."""
    d = os.path.join(core.SERVER, "studio_packs")              # source checkout
    if not os.path.isdir(d):
        d = os.path.join(core.ROOT, "studio_packs")            # compiled install (Setup puts it next to app\)
    return path("studio_packs_dir", "MML_STUDIO_PACKS", d)


def copycat():
    """D3voz/openjutsu (MIT) + the lab's overlay. Setup downloads, patches and builds it here."""
    return path("copycat_dir", "MML_COPYCAT_DIR", os.path.join(ENGINES, "copycat"))


def kinetic():
    """MIR KINETIC engine (kinetic type + OpenKatana effects, Apache-2.0). Ships with the lab."""
    return path("kinetic_dir", "MML_KINETIC_DIR", os.path.join(core.ROOT, "kinetic"))


def motion():
    """MIR MOTION (Remotion) engine folder — the same one remotion.py runs."""
    return path("motion_dir", "MML_MOTION_DIR", os.path.join(core.ROOT, "motion"))


def sfx():
    """Optional sound-effect folder for the Motion score (any .mp3/.wav you own the rights to). None = music bed only."""
    p = path("sfx_dir", "MML_SFX_DIR", os.path.join(core.DATA, "sfx"))
    return p if os.path.isdir(p) else None


def expressive_python():
    """Python of an optional Chatterbox (MIT) voice venv. Empty = the expressive voice is off, Kokoro speaks."""
    return path("expressive_python", "MML_EXPRESSIVE_PY", "")


def node():
    n = core.CONFIG.get("node") if isinstance(core.CONFIG, dict) else None
    return n or shutil.which("node") or (r"C:\Program Files\nodejs\node.exe" if os.name == "nt" else "node")


def art_python():
    """Python with numpy + Pillow for asset scripts: the engine's (ComfyUI venv) Python, else this interpreter."""
    try:
        import comfy
        if comfy.COMFY_PY and os.path.isfile(comfy.COMFY_PY):
            return comfy.COMFY_PY
    except Exception:
        pass
    import sys
    return sys.executable


def static_dir(rel):
    """A folder of server/static on disk. The compiled edition embeds static files in the binary, so tools that hand
    files to node / Chrome (fonts for Kinetic + Remotion) get them extracted once into data/_static/<rel>."""
    p = os.path.join(core.STATIC, rel)
    if os.path.isdir(p) or not getattr(core, "ASSETS", None):
        return p
    out = os.path.join(core.DATA, "_static", rel)
    pre = rel.replace("\\", "/").strip("/") + "/"
    try:
        for k in core.ASSETS:
            if k.startswith(pre):
                dst = os.path.join(out, *k[len(pre):].split("/"))
                data = core.asset(k)
                if data is not None and not (os.path.isfile(dst) and os.path.getsize(dst) == len(data)):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, "wb") as f:
                        f.write(data)
    except Exception:
        pass
    return out


def summary():
    return {"freefield": freefield(), "studio_packs": studio_packs(), "copycat": copycat(), "kinetic": kinetic(),
            "motion": motion(), "sfx": sfx() or "", "expressive_voice": bool(expressive_python())}
