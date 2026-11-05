"""Join edited segments back into one clip, frame-exact, with the original audio.

Usage: python3 alter_assemble.py segs/manifest.json --out final.mp4 [--force]
Each segment's edited file must be at its manifest 'out' path. Every segment is conformed to the source size and
frame rate and trimmed or padded (at most 2 frames, last frame held) to its exact source length, so the original
audio stays in sync across the joins.
"""
import argparse
import json
import os
import subprocess
import tempfile

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('manifest')
    ap.add_argument('--out', required=True)
    ap.add_argument('--crf', type=int, default=14)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    guard(a.out, a.force)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.manifest) as fh:
        m = json.load(fh)
    fps, W, H = m['fps'], m['width'], m['height']
    tmp = tempfile.mkdtemp(prefix='alter_asm_')
    parts = []
    for s in m['segments']:
        src = s['out']
        if not os.path.exists(src):
            raise SystemExit(f"missing edited segment {s['index']}: {src}")
        want = s['end_frame'] - s['start_frame']
        got = round(probe(src)['duration'] * fps)
        if abs(got - want) > 2:
            print(f"  warning: segment {s['index']} is {got} frames, source {want}; conforming anyway, check sync")
        p = os.path.join(tmp, f"p{s['index']:03d}.mp4")
        vf = (f'fps={fps},scale={W}:{H}:flags=lanczos,setsar=1,'
              f'tpad=stop_mode=clone:stop=2,trim=end_frame={want},setpts=PTS-STARTPTS')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', vf, '-an', '-c:v', 'libx264', '-crf',
                        str(a.crf), '-pix_fmt', 'yuv420p', p], check=True)
        parts.append(p)
    lst = os.path.join(tmp, 'list.txt')
    with open(lst, 'w') as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    total = sum(s['end_frame'] - s['start_frame'] for s in m['segments']) / fps
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst]
    if probe(m['source'])['has_audio']:
        start = m['segments'][0]['start']
        cmd += ['-ss', str(start), '-t', str(total), '-i', m['source'], '-map', '0:v', '-map', '1:a',
                '-c:a', 'aac', '-b:a', '256k']
    cmd += ['-c:v', 'copy', '-t', str(total), '-movflags', '+faststart', a.out]
    subprocess.run(cmd, check=True)
    print(f'wrote {a.out}: {len(parts)} segments, {total:.3f} s, original audio laid back')


if __name__ == '__main__':
    main()
