"""PC self-update for installed (compiled) copies of MIR MEDIA LABS.

Channel = <update_url>/version.json + version.json.sig + MirMediaLabs-Setup.exe, published by
installer\\build.ps1 -Publish on the owner's PC and served by its /updates/pc/ route.
Linux copies read linux.json + linux.json.sig + MirMediaLabs-<ver>-linux-x86_64.tar.gz from the same
channel (build_tool.py publish-linux), so Windows clients never see the Linux files and vice versa.

Security:
  * version.json is signed with Ed25519. The private key never leaves the publishing PC; the
    public key is compiled into every build, so a hijacked DNS name / router / mirror can't
    push code — an unsigned or altered manifest is rejected.
  * the manifest carries the setup exe's SHA-256 + size; the download must match exactly.
  * only strictly newer versions are accepted (no downgrade / replay of an old release).
  * the channel also needs the build's update token, so random scanners can't fetch the installer.
"""
import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tarfile
import threading
import time

import requests

import core
import platform_util

PUBKEY = core.BUILD.get("update_pubkey", "")
TOKEN = core.BUILD.get("update_token", "")
URL = (core.CONFIG.get("update_url") or core.BUILD.get("update_url") or "").rstrip("/") + "/"
ENABLED = bool(PUBKEY and URL.strip("/"))
EVERY = 6 * 3600
DL_DIR = os.path.join(core.DATA, "updates")
IS_WIN = platform_util.IS_WIN
MANIFEST = "version.json" if IS_WIN else "linux.json"
ARTIFACT_EXT = ".exe" if IS_WIN else ".tar.gz"
STATE = {"enabled": ENABLED, "current": core.APP_VERSION, "available": None, "checked": None,
         "error": None, "busy": False, "progress": 0}
_LOCK = threading.Lock()


# ── publisher side (the owner's PC serves /updates/pc/) ─────────────────────
def publisher_ok(req):
    """The channel token, if this PC publishes one; nothing published → nothing to protect."""
    try:
        want = open(os.path.join(core.DATA, "pc_update_token.txt"), encoding="utf-8").read().strip()
    except OSError:
        return True
    return hmac.compare_digest(want, req.headers.get("X-MML-Update", ""))


# ── client side ─────────────────────────────────────────────────────────────
def _ver(v):
    return tuple(int(x) for x in str(v).split(".") if x.isdigit())


def _get(name, stream=False, timeout=20):
    r = requests.get(URL + name, headers={"X-MML-Update": TOKEN, "User-Agent": "MirMediaLabs/" + core.APP_VERSION},
                     stream=stream, timeout=timeout)
    r.raise_for_status()
    return r


def _verified_manifest():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = _get(MANIFEST).content
    sig = base64.b64decode(_get(MANIFEST + ".sig").content.strip())
    Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBKEY)).verify(sig, raw)   # raises InvalidSignature
    man = json.loads(raw)
    for k in ("version", "file", "sha256", "size"):
        if k not in man:
            raise ValueError("manifest missing " + k)
    if "/" in man["file"] or "\\" in man["file"] or not man["file"].lower().endswith(ARTIFACT_EXT):
        raise ValueError("bad file name in manifest")
    return man


def check():
    if not ENABLED:
        return STATE
    try:
        man = _verified_manifest()
        newer = _ver(man["version"]) > _ver(core.APP_VERSION)
        STATE["available"] = ({"version": man["version"], "notes": man.get("notes", ""), "size": man["size"],
                               "published": man.get("published")} if newer else None)
        STATE["error"] = None
    except Exception as e:
        STATE["error"] = "%s: %s" % (type(e).__name__, str(e)[:200] or "signature check failed")
    STATE["checked"] = time.strftime("%Y-%m-%d %H:%M")
    return STATE


def loop():
    if not ENABLED:
        return
    time.sleep(20)
    while True:
        check()
        time.sleep(EVERY)


def apply():
    """Download the newer signed setup (Windows) / tarball (Linux), verify it, hand over to it and exit.
    Returns an error or None."""
    with _LOCK:
        if STATE["busy"]:
            return "update already running"
        STATE["busy"], STATE["progress"] = True, 0
    try:
        man = _verified_manifest()
        if _ver(man["version"]) <= _ver(core.APP_VERSION):
            return "already up to date"
        os.makedirs(DL_DIR, exist_ok=True)
        dest = os.path.join(DL_DIR, ("MirMediaLabs-Setup-%s.exe" if IS_WIN else "MirMediaLabs-%s-linux.tar.gz")
                            % man["version"])
        h, n = hashlib.sha256(), 0
        with _get(man["file"], stream=True, timeout=60) as r, open(dest + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
                STATE["progress"] = n / max(1, man["size"])
        if n != man["size"] or not hmac.compare_digest(h.hexdigest(), man["sha256"].lower()):
            os.remove(dest + ".part")
            return "download didn't match the signed manifest — update refused"
        os.replace(dest + ".part", dest)
        if IS_WIN:
            subprocess.Popen([dest, "--update", "--dir", core.ROOT], cwd=DL_DIR,
                             **platform_util.detached_kwargs(hide=False, new_group=True))   # detached, own process group
        else:
            _hand_over_linux(dest)
        threading.Timer(1.5, lambda: os._exit(0)).start()               # setup restarts the app when done
        return None
    except Exception as e:
        return "%s: %s" % (type(e).__name__, str(e)[:300])
    finally:
        STATE["busy"] = False


def _hand_over_linux(tgz):
    """Unpack the verified tarball and run its install.sh --update outside our own process tree."""
    stage = os.path.join(DL_DIR, "stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    root = os.path.realpath(stage) + os.sep
    with tarfile.open(tgz, "r:gz") as t:
        for m in t.getmembers():                      # no absolute paths / .. / links out of stage
            p = os.path.realpath(os.path.join(stage, m.name))
            if not p.startswith(root) or m.issym() or m.islnk() or m.isdev():
                raise ValueError("unsafe path in update archive: %s" % m.name)
        t.extractall(stage)
    pkg = os.path.join(stage, "MirMediaLabs")
    inst = os.path.join(pkg, "install.sh")
    os.chmod(inst, 0o755)
    os.chmod(os.path.join(pkg, "app", "MirMediaLabs"), 0o755)
    cmd = [inst, "--update", "--dir", core.ROOT]
    # under systemd our whole cgroup dies with us → run the installer as its own transient unit
    if os.environ.get("INVOCATION_ID") and shutil.which("systemd-run"):
        cmd = ["systemd-run", "--user", "--collect", "--quiet", "--unit", "mml-update-%d" % int(time.time())] + cmd
    log = open(os.path.join(core.LOGS, "update_install.log"), "a")
    subprocess.Popen(cmd, cwd=stage, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                     **platform_util.detached_kwargs(hide=False, new_group=True))


def cleanup():
    """Remove downloaded setups of versions already installed."""
    try:
        for f in os.listdir(DL_DIR):
            if f.startswith("MirMediaLabs-Setup-") and _ver(f[19:-4]) <= _ver(core.APP_VERSION):
                os.remove(os.path.join(DL_DIR, f))
            elif f.endswith("-linux.tar.gz") and _ver(f[13:-13]) <= _ver(core.APP_VERSION):
                os.remove(os.path.join(DL_DIR, f))
        shutil.rmtree(os.path.join(DL_DIR, "stage"), ignore_errors=True)
    except OSError:
        pass
