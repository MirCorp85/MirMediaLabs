"""Pick and extract the source frame for a target-frame (realism) pass.

Usage:
  python3 alter_frame.py clip.mp4 --sheet frames.jpg           # numbered sheet of 12 moments to choose from
  python3 alter_frame.py clip.mp4 --t 7.6 --out frame.png      # the moment you chose (seconds)
  python3 alter_frame.py clip.mp4 --best --out frame.png       # sharpest frame in the middle 60% of the clip

Choose the moment where the element you are changing is biggest, sharpest and least covered by hands. For a
recast, a frame where the face is front-on and the whole outfit shows. Never overwrites without --force.
"""
import argparse
import subprocess

import numpy as np
from PIL import Image, ImageDraw

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe, read_frames


def sharpness(g):
    g = g.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def write_sheet(clip, info, out, n=12, cols=4):
    frames = read_frames(clip, width=480)
    picks = np.linspace(0, len(frames) - 1, n).astype(int)
    h = frames.shape[1]
    sheet = Image.new('RGB', (480 * cols, h * ((n + cols - 1) // cols)))
    for k, i in enumerate(picks):
        im = Image.fromarray(frames[i])
        d = ImageDraw.Draw(im)
        label = f'{k + 1}  t={i / info["fps"]:.2f}s  f{i}'
        d.rectangle([0, 0, 8 * len(label) + 8, 18], fill=(0, 0, 0))
        d.text((4, 3), label, fill=(255, 255, 255))
        sheet.paste(im, ((k % cols) * 480, (k // cols) * h))
    sheet.save(out, quality=88)
    print(f'wrote {out}: {n} moments; pick one and run again with --t <seconds> --out frame.png')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('clip')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--best', action='store_true')
    g.add_argument('--t', type=float)
    g.add_argument('--sheet', metavar='SHEET.jpg')
    ap.add_argument('--out')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    info = probe(a.clip)
    if a.sheet:
        guard(a.sheet, a.force)
        write_sheet(a.clip, info, a.sheet)
        return
    if not a.out:
        ap.error('--out is required with --best or --t')
    guard(a.out, a.force)
    if a.best:
        fr = read_frames(a.clip, width=480, gray=True)
        n = len(fr)
        lo, hi = int(n * 0.2), max(int(n * 0.8), int(n * 0.2) + 1)
        scores = [sharpness(fr[i]) for i in range(lo, hi)]
        idx = lo + int(np.argmax(scores))
        t = idx / info['fps']
        print(f'sharpest frame {idx} at {t:.3f} s')
    else:
        want = round(a.t * info['fps'])
        idx = min(max(want, 0), info['frames'] - 1)
        t = idx / info['fps']
        if idx != want:
            print(f'warning: --t {a.t} is outside the clip ({info["duration"]:.2f} s); using frame {idx} ({t:.3f} s)')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.clip, '-vf', f'select=eq(n\\,{idx}),format=rgb24',
                    '-fps_mode', 'passthrough', '-frames:v', '1', '-update', '1', a.out], check=True)
    print(f'wrote {a.out} (frame {idx}, {t:.3f} s, {info["width"]}x{info["height"]}). Upload it with upload_asset.')


if __name__ == '__main__':
    main()
