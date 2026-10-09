"""Build helper for the compiled PC edition (run by build.ps1 with the build venv's python).

  build_tool.py keys                       create the Ed25519 update-signing key + channel token (once)
  build_tool.py stage <src_dir> <url>      copy server code → src_dir, add _buildinfo.py + _assets.py
  build_tool.py publish <setup.exe> <notes>  sign + copy into updates\\pc\\ (served at /updates/pc/)
  build_tool.py publish-linux <tar.gz> <notes>  same channel, Linux manifest (linux.json + .sig)

The signing key (installer\\signing\\update_ed25519.key) must never ship and must be backed up:
without it, already-installed copies can't receive updates.
"""
import base64
import glob
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIGN = os.path.join(HERE, "signing")
KEY = os.path.join(SIGN, "update_ed25519.key")
TOKEN = os.path.join(SIGN, "update_token.txt")
VERSION_FILE = os.path.join(HERE, "pc_version.json")


def version():
    return json.load(open(VERSION_FILE, encoding="utf-8"))["version"]


def _priv():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(KEY).read().strip()))


def keys():
    os.makedirs(SIGN, exist_ok=True)
    if not os.path.isfile(KEY):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        raw = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                         serialization.NoEncryption())
        open(KEY, "w").write(base64.b64encode(raw).decode())
        print("NEW signing key:", KEY, "— back it up somewhere safe")
    if not os.path.isfile(TOKEN):
        open(TOKEN, "w").write(secrets.token_urlsafe(24))
    # the publishing server (this PC) checks the channel token from its private data folder
    shutil.copy2(TOKEN, os.path.join(ROOT, "data", "pc_update_token.txt"))


def _pub_b64():
    from cryptography.hazmat.primitives import serialization
    return base64.b64encode(_priv().public_key().public_bytes(serialization.Encoding.Raw,
                                                              serialization.PublicFormat.Raw)).decode()


def _minify_js(code):
    """terser (compress + local-name mangling; globals untouched so inline handlers keep working)."""
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        return code
    r = subprocess.run([npx, "--yes", "terser", "--compress", "--mangle", "--ecma", "2020"], input=code,
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    if r.returncode != 0 or not r.stdout.strip():
        print("  terser failed, keeping original:", r.stderr[-300:])
        return code
    return r.stdout


def stage(src, url):
    public = url == "-"          # GitHub release build: auto-update off, no private channel token
    if public:
        url = ""
    shutil.rmtree(src, ignore_errors=True)
    os.makedirs(src)
    for f in glob.glob(os.path.join(ROOT, "server", "*.py")):
        shutil.copy2(f, src)
    open(os.path.join(src, "_buildinfo.py"), "w", encoding="utf-8").write(
        "INFO = %r\n" % {"version": version(), "update_url": url, "update_token": "" if public else open(TOKEN).read().strip(),
                         "update_pubkey": _pub_b64(), "built": time.strftime("%Y-%m-%d %H:%M")})
    static = os.path.join(ROOT, "server", "static")
    files, raw_total = {}, 0
    for dp, _, fns in os.walk(static):
        for fn in fns:
            if ".bak" in fn or fn.endswith(".src.mp4") or (fn.startswith("_obase_")):
                continue                                # backups + preview-generator scratch files
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, static).replace("\\", "/")
            data = open(p, "rb").read()
            if fn.endswith(".js"):
                data = _minify_js(data.decode("utf-8")).encode("utf-8")
            elif fn == "index.html":
                html = data.decode("utf-8")
                html = re.sub(r"<script>(.*?)</script>", lambda m: "<script>" + _minify_js(m.group(1)) + "</script>",
                              html, flags=re.S)
                data = html.encode("utf-8")
            raw_total += len(data)
            files[rel] = zlib.compress(data, 9)
    for md in glob.glob(os.path.join(ROOT, "server", "*.md")):     # agent briefs (MUSE soul, VIRAL-Ω soul)
        data = open(md, "rb").read()
        raw_total += len(data)
        files["_md/" + os.path.basename(md)] = zlib.compress(data, 9)
    with open(os.path.join(src, "_assets.py"), "w", encoding="utf-8") as f:
        f.write("FILES = {\n")
        for k, v in sorted(files.items()):
            f.write("    %r: %r,\n" % (k, v))
        f.write("}\n")
    print("staged %d py files, %d embedded assets (%.0f KB)" % (len(glob.glob(os.path.join(src, "*.py"))),
                                                               len(files), raw_total / 1024))


def publish(setup, notes):
    out = os.path.join(ROOT, "updates", "pc")
    os.makedirs(out, exist_ok=True)
    dest = os.path.join(out, "MirMediaLabs-Setup.exe")
    shutil.copy2(setup, dest + ".tmp")
    data = open(dest + ".tmp", "rb").read()
    man = {"version": version(), "notes": notes, "file": "MirMediaLabs-Setup.exe", "size": len(data),
           "sha256": hashlib.sha256(data).hexdigest(), "published": time.strftime("%Y-%m-%d %H:%M")}
    raw = json.dumps(man, indent=1).encode("utf-8")
    sig = base64.b64encode(_priv().sign(raw))
    os.replace(dest + ".tmp", dest)                     # exe first, then the manifest that points at it
    open(os.path.join(out, "version.json.sig"), "wb").write(sig)
    open(os.path.join(out, "version.json"), "wb").write(raw)
    print("published v%s → %s" % (man["version"], out))


def publish_linux(tgz, notes):
    """Linux channel = linux.json(.sig) beside the Windows version.json; same key, same folder."""
    out = os.path.join(ROOT, "updates", "pc")
    os.makedirs(out, exist_ok=True)
    name = os.path.basename(tgz)
    if not name.endswith("-linux-x86_64.tar.gz"):
        raise SystemExit("expected MirMediaLabs-<ver>-linux-x86_64.tar.gz")
    dest = os.path.join(out, name)
    shutil.copy2(tgz, dest + ".tmp")
    data = open(dest + ".tmp", "rb").read()
    man = {"version": version(), "platform": "linux-x86_64", "notes": notes, "file": name, "size": len(data),
           "sha256": hashlib.sha256(data).hexdigest(), "published": time.strftime("%Y-%m-%d %H:%M")}
    raw = json.dumps(man, indent=1).encode("utf-8")
    sig = base64.b64encode(_priv().sign(raw))
    os.replace(dest + ".tmp", dest)                     # tarball first, then the manifest that points at it
    open(os.path.join(out, "linux.json.sig"), "wb").write(sig)
    open(os.path.join(out, "linux.json"), "wb").write(raw)
    for f in os.listdir(out):                           # keep only the published Linux tarball
        if f.endswith("-linux-x86_64.tar.gz") and f != name:
            os.remove(os.path.join(out, f))
    print("published Linux v%s → %s" % (man["version"], out))


def android(apk, code, name, cert, tag, outdir):
    """android.json + android.json.sig for the app's updater (GitHub release when tag is set, else the lab's /updates/).
    Same Ed25519 key as the PC channel; the app has the public key compiled in (Updater.PUBKEY)."""
    h = hashlib.sha256(open(apk, "rb").read()).hexdigest()
    man = {"app": "com.mirmedialabs.app", "versionCode": int(code), "versionName": name,
           "notes": os.environ.get("MML_NOTES", "").strip(), "apk": "MirMediaLabs.apk", "sha256": h,
           "size": os.path.getsize(apk), "cert": cert.lower().replace(":", ""), "minSdk": 24,
           "tag": "" if tag in ("", "-") else tag, "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    raw = json.dumps(man, indent=1, ensure_ascii=False).encode("utf-8")
    sig = base64.b64encode(_priv().sign(raw))
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, "android.json"), "wb").write(raw)
    open(os.path.join(outdir, "android.json.sig"), "wb").write(sig)
    print("signed android.json v%s (%s) sha256 %s… -> %s" % (name, code, h[:12], outdir))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "keys":
        keys()
    elif cmd == "stage":
        stage(sys.argv[2], sys.argv[3])
    elif cmd == "publish":
        publish(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "publish-linux":
        publish_linux(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "android":
        android(*sys.argv[2:8])
    elif cmd == "bump":
        v = [int(x) for x in version().split(".")]
        v[-1] += 1
        json.dump({"version": ".".join(map(str, v))}, open(VERSION_FILE, "w"), indent=1)
        print("version →", ".".join(map(str, v)))
