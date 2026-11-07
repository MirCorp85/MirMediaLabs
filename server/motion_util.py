"""Small helpers shared by Motion Studio (motion_wizard): number clamping, WAV length and saving a voice-over to the library."""
import os
import shutil
import time
import wave

import core

DEF_VOICE = "am_michael"        # default narrator voice (Kokoro)


def _f(v, d, lo, hi):
    """float(v) clamped to [lo, hi]; d when v isn't a number."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = d
    return max(lo, min(hi, v))


def _wav_secs(p):
    try:
        with wave.open(p) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def _to_lib(src_path, uid, sid, prompt):
    """Copy a narration WAV into the library and index it under the user's session."""
    name = core.new_name("motionvo", ".wav")
    shutil.copy2(src_path, os.path.join(core.LIB, name))
    meta = {"user": uid, "model": "kokoro", "mode": "motion-vo", "prompt": prompt[:300], "created": time.time()}
    if sid:
        meta["session"] = sid
    core.index_add(name, meta)
    return name
