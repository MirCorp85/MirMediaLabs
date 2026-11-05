"""Cut between frame-aligned versions of one take on a fixed beat (the "one take, many versions" edit).

Usage: python3 alter_versions.py source.mp4 v1.mp4 v2.mp4 [v3.mp4 ...] --out reel.mp4 [--every 12] [--with-source]
       [--frames N] [--force]
Every version must come from the same source through edit mode (same length and motion). The reel switches to the
next version every N frames on the source's clock, so the performance never jumps, and lays the source audio.
"""
import argparse
import os
import subprocess

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe, stream_frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source')
    ap.add_argument('versions', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--every', type=int, default=12, help='frames per version before switching (12 = 0.5 s at 24 fps)')
    ap.add_argument('--with-source', action='store_true', help='include the original take in the rotation, first')
    ap.add_argument('--frames', type=int, default=None, help='stop after N frames (e.g. before a tail drift)')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    guard(a.out, a.force)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    si = probe(a.source)
    W, H, fps, n = si['width'], si['height'], si['fps'], si['frames']
    for c in a.versions:
        got = probe(c)['frames']
        if abs(got - si['frames']) > 2:
            print(f'  warning: {c} has {got} frames vs source {si["frames"]}; it may not be frame-aligned')
    if a.frames:
        n = min(n, a.frames)
    clips = ([a.source] if a.with_source else []) + a.versions
    streams = [stream_frames(c, W, H) for c in clips]
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f'{fps}', '-i', '-']
    if si['has_audio']:
        cmd += ['-i', a.source, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k']
    cmd += ['-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-t', f'{n / fps:.4f}', '-movflags', '+faststart', a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        frames = []
        for s in streams:
            try:
                frames.append(next(s))
            except StopIteration:
                frames.append(None)
        pick = frames[(i // a.every) % len(frames)]
        if pick is None:
            pick = next(f for f in frames if f is not None)
        p.stdin.write(pick.tobytes())
    p.stdin.close(); p.wait()
    for s in streams:
        s.close()
    src = ' plus the source' if a.with_source else ''
    print(f'wrote {a.out}: {len(a.versions)} versions{src}, switching every {a.every} frames, {n} frames, {n / fps:.2f} s')


if __name__ == '__main__':
    main()
