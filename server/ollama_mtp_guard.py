"""Strip the MTP draft model from local gemma4 tags.

Ollama 0.40's Gemma4 MTP draft crashes on load ("Gemma4Assistant requires
ctx_other ... error loading model: vector") and Ollama retries forever, so the
model looks stuck. A re-pull of gemma4:12b brings the DRAFT back; this runs at
startup (and periodically) and rebuilds any affected tag without it.
"""
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _tags():
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=5) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def _modelfile(name):
    return subprocess.run(["ollama", "show", "--modelfile", name], capture_output=True,
                          text=True, encoding="utf-8", timeout=60, creationflags=_NOWIN).stdout


def fix_once(log=print):
    fixed = []
    for name in _tags():
        if "gemma4" not in name:
            continue
        mf = _modelfile(name)
        if not any(l.startswith("DRAFT ") for l in mf.splitlines()):
            continue
        clean = "\n".join(l for l in mf.splitlines()
                          if not l.startswith("DRAFT ") and "draft_num_predict" not in l)
        with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False, encoding="utf-8") as f:
            f.write(clean)
        try:
            r = subprocess.run(["ollama", "create", name, "-f", f.name], capture_output=True,
                               text=True, timeout=600, creationflags=_NOWIN)
            ok = r.returncode == 0
        finally:
            os.unlink(f.name)
        log("[mtp-guard] %s: stripped MTP draft (%s)" % (name, "ok" if ok else "FAILED"))
        if ok:
            fixed.append(name)
    return fixed


def _loop(interval):
    while True:
        try:
            fix_once()
        except Exception as e:  # Ollama down / CLI missing: try again later
            print("[mtp-guard] skipped: %s" % e)
        time.sleep(interval)


def start(interval=1800):
    threading.Thread(target=_loop, args=(interval,), daemon=True, name="ollama-mtp-guard").start()


if __name__ == "__main__":
    print(fix_once() or "nothing to fix")
