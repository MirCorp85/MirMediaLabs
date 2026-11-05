"""Check a source clip against video edit-mode limits and say what to do.

Usage: python3 alter_probe.py clip.mp4
Exit code 0 = ready to upload as it is, 1 = run alter_prep.py (or alter_split.py) first.
"""
import sys

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import probe

MIN_S, MAX_S, MIN_SIDE = 4.0, 30.0, 480


def main(path):
    i = probe(path)
    short = min(i['width'], i['height'])
    print(f"{path}: {i['duration']:.2f} s, {i['width']}x{i['height']}, {i['fps']:.3f} fps, {i['frames']} frames, "
          f"{i['codec']}, {i['size_mb']:.1f} MB, audio {'yes' if i['has_audio'] else 'no'}")
    fix = []
    if i['hdr']:
        fix.append(f"HDR ({i['hdr']}): decoded as SDR it looks washed out, and the edit inherits that")
    if i['rotation']:
        fix.append(f"rotation metadata ({i['rotation']} degrees): the model may see the picture sideways")
    if i['vfr']:
        fix.append('variable frame rate: frame counts, QA and the source sound will not line up')
    if short < MIN_SIDE:
        fix.append(f'short side {short} px is under {MIN_SIDE} px: edit mode rejects it')
    if i['duration'] < MIN_S:
        fix.append(f'only {i["duration"]:.2f} s: edit mode needs at least {MIN_S:.0f} s; pick a longer span')
    for line in fix:
        print('  FIX:', line)
    if i['duration'] > MAX_S:
        print(f'  LONG: over {MAX_S:.0f} s for one run. Prep it, then alter_split.py, run every segment, alter_assemble.py.')
    if not i['has_audio']:
        print('  NOTE: no sound track; alter_finish.py delivers silent unless you pass --audio.')
    if fix:
        print('  Run: python3 alter_prep.py', path, '--out prepared.mp4')
        return 1
    if i['duration'] > MAX_S:
        return 1
    print('  OK for a single edit run. alter_prep.py still gives a clean, seekable upload copy.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
