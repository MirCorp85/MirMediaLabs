"""Split a long clip at real shot changes into segments of 4-30 s for Seedance edit mode.

Usage: python3 alter_split.py long.mp4 --out segs/ [--max 30] [--min 4] [--force]
Writes segs/seg_000.mp4 ... and segs/manifest.json (frame-exact boundaries, the source path, and an 'out' path per
segment where the edited result should be saved for alter_assemble.py).
"""
import argparse
import json
import os

import numpy as np

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe, read_frames, run


def find_cuts(path, fps):
    g = read_frames(path, width=160, gray=True).astype(np.float32)
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
    med = np.median(d) + 1e-3
    # a cut is a spike well above both the local motion level and an absolute floor
    cuts = []
    for i, v in enumerate(d):
        lo, hi = max(0, i - 12), min(len(d), i + 13)
        local = np.median(np.r_[d[lo:i], d[i + 1:hi]]) + 1e-3
        if v > 18 and v > 4 * local and v > 3 * med:
            cuts.append(i + 1)
    return cuts, d


def pack(n, cuts, fps, max_s, min_s, energy):
    shots = []
    edges = [0] + cuts + [n]
    for a, b in zip(edges, edges[1:]):
        if b > a:
            shots.append([a, b])
    maxf, minf = int(max_s * fps), int(np.ceil(min_s * fps))
    # a shot longer than max: split at its calmest frame (least motion), never mid-move if avoidable
    out = []
    for a, b in shots:
        while b - a > maxf:
            lo, hi = a + minf, a + maxf
            k = lo + int(np.argmin(energy[lo - 1:hi - 1]))
            print(f'  warning: shot {a}-{b} is longer than {max_s} s; splitting inside it at frame {k} (calmest frame)')
            out.append([a, k])
            a = k
        out.append([a, b])
    # greedy pack consecutive shots into segments up to max
    segs = []
    for a, b in out:
        if segs and (b - segs[-1][0]) <= maxf:
            segs[-1][1] = b
        else:
            segs.append([a, b])
    # merge any segment shorter than min into a neighbour
    i = 0
    while i < len(segs):
        a, b = segs[i]
        if b - a < minf and len(segs) > 1:
            j = i - 1 if i > 0 and (b - segs[i - 1][0]) <= maxf else i + 1
            if j < len(segs) and (max(b, segs[j][1]) - min(a, segs[j][0])) <= maxf:
                segs[j] = [min(a, segs[j][0]), max(b, segs[j][1])]
                segs.pop(i)
                i = 0
                continue
            print(f'  warning: segment {a}-{b} is under {min_s} s and cannot merge; extend it or drop it')
        i += 1
    return segs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('clip')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max', type=float, default=30.0)
    ap.add_argument('--min', type=float, default=4.0)
    ap.add_argument('--force', action='store_true', help='replace an existing manifest and segments in --out')
    a = ap.parse_args()
    guard(os.path.join(a.out, 'manifest.json'), a.force)
    info = probe(a.clip)
    fps = info['fps']
    cuts, energy = find_cuts(a.clip, fps)
    n = len(energy) + 1
    segs = pack(n, cuts, fps, a.max, a.min, energy)
    os.makedirs(a.out, exist_ok=True)
    man = {'source': os.path.abspath(a.clip), 'fps': fps, 'frames': n, 'width': info['width'],
           'height': info['height'], 'cuts': cuts, 'segments': []}
    for k, (s, e) in enumerate(segs):
        f = os.path.join(a.out, f'seg_{k:03d}.mp4')
        vf = f'trim=start_frame={s}:end_frame={e},setpts=PTS-STARTPTS'
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', a.clip, '-vf', vf]
        if info['has_audio']:
            cmd += ['-af', f'atrim=start={s / fps}:end={e / fps},asetpts=PTS-STARTPTS', '-c:a', 'aac', '-b:a', '256k']
        cmd += ['-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', f]
        run(cmd)
        man['segments'].append({'index': k, 'start_frame': s, 'end_frame': e, 'start': s / fps, 'end': e / fps,
                                'seconds': (e - s) / fps, 'file': os.path.abspath(f),
                                'out': os.path.abspath(os.path.join(a.out, f'seg_{k:03d}_alter.mp4'))})
        print(f'segment {k}: frames {s}-{e} ({(e - s) / fps:.2f} s) -> {f}')
    with open(os.path.join(a.out, 'manifest.json'), 'w') as fh:
        json.dump(man, fh, indent=1)
    print(f'{len(cuts)} cuts found, {len(segs)} segments; manifest {os.path.join(a.out, "manifest.json")}')
    print("Run each segment through the same preset; save each result at the segment's 'out' path.")


if __name__ == '__main__':
    main()
