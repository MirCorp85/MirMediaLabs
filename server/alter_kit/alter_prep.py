"""Prepare a source clip for an ALTER edit: SDR, upright, constant frame rate, edit-mode size and length.

Usage:
  python3 alter_prep.py clip.MOV --out prepared.mp4 [--start 2.0] [--end 14.5] [--force]

What it fixes (each step only when the clip needs it, and it says so):
- HDR phone footage (HLG or PQ) is tone-mapped to SDR BT.709. Decoded as SDR it looks washed out and the edit
  inherits that. Uses macOS avconvert when present, else an ffmpeg build with zscale; otherwise it stops and asks
  for an SDR export ("Most Compatible" in Photos or QuickTime).
- Rotation metadata is baked into the pixels, so the model sees the picture the way people see it.
- Variable frame rate becomes constant, so frame counts, QA and the source audio line up afterwards.
- A short side under 480 px is upscaled (edit mode rejects smaller sources); a long side over 1920 px is scaled
  down (4K adds upload time, not quality, at the edit's output sizes).
- --start/--end trim to the moment you want (edit mode takes 4 to 30 seconds per run; longer goes through
  alter_split.py).
Writes prepared.mp4 (H.264, BT.709 tags, faststart, a keyframe every second, AAC audio) and prepared.json with
the before and after facts. Never overwrites without --force.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe

MIN_SIDE, MAX_LONG, MIN_S, MAX_S = 480, 1920, 4.0, 30.0
STANDARD_RATES = (23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0, 59.94, 60.0)


def has_filter(name):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout
    return f' {name} ' in out


def nominal_rate(fps):
    return min(STANDARD_RATES, key=lambda r: abs(r - fps)) if fps else 30.0


def tone_map(src, dst, info):
    """HDR to SDR BT.709. Returns the path of an SDR intermediate."""
    if shutil.which('avconvert'):
        preset = 'Preset3840x2160' if max(info['width'], info['height']) >= 3000 else 'Preset1920x1080'
        subprocess.run(['avconvert', '--source', src, '--preset', preset, '--output', dst, '--replace'], check=True,
                       capture_output=True)
        return dst
    if has_filter('zscale'):
        vf = ('zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,'
              'zscale=t=bt709:m=bt709:r=tv,format=yuv420p')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', vf, '-c:v', 'libx264', '-crf', '12',
                        '-c:a', 'aac', '-b:a', '256k', dst], check=True)
        return dst
    raise SystemExit('This clip is HDR and no tone-mapper is available here (no avconvert, ffmpeg without zscale). '
                     'Export it as SDR first (Photos or QuickTime: "Most Compatible"), then run alter_prep.py again.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('clip')
    ap.add_argument('--out', required=True)
    ap.add_argument('--start', type=float, default=0.0, help='trim start, seconds')
    ap.add_argument('--end', type=float, default=None, help='trim end, seconds')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    guard(a.out, a.force)
    meta_path = os.path.splitext(a.out)[0] + '.json'
    guard(meta_path, a.force)
    before = probe(a.clip)
    notes = []
    src = a.clip
    tmp = tempfile.mkdtemp(prefix='alter_prep_')
    if before['hdr']:
        notes.append(f"HDR ({before['hdr']}) tone-mapped to SDR BT.709")
        src = tone_map(src, os.path.join(tmp, 'sdr.mov'), before)
    end = a.end if a.end is not None else before['duration']
    span = end - a.start
    if span < MIN_S:
        raise SystemExit(f'The selected span is {span:.2f} s; edit mode needs at least {MIN_S:.0f} s. Widen --start/--end.')
    if span > MAX_S:
        notes.append(f'{span:.1f} s is longer than one edit run ({MAX_S:.0f} s): run alter_split.py on the prepared file')
    w, h = before['width'], before['height']
    scale = 1.0
    if min(w, h) < MIN_SIDE:
        scale = MIN_SIDE / min(w, h)
        notes.append(f'short side {min(w, h)} px upscaled to {MIN_SIDE} px (edit mode rejects smaller sources)')
    elif max(w, h) > MAX_LONG:
        scale = MAX_LONG / max(w, h)
        notes.append(f'{w}x{h} scaled down to a {MAX_LONG} px long side')
    tw, th = (round(w * scale / 2) * 2, round(h * scale / 2) * 2)
    rate = nominal_rate(before['fps'])
    if before['vfr']:
        notes.append(f'variable frame rate made constant at {rate:g} fps')
    if before['rotation']:
        notes.append(f"rotation {before['rotation']} degrees baked into the pixels")
    vf = f'scale={tw}:{th}:flags=lanczos,setsar=1,format=yuv420p'
    gop = max(1, round(rate))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', f'{a.start:.3f}', '-i', src, '-t', f'{span:.3f}',
           '-map', '0:v:0', '-map', '0:a:0?', '-vf', vf, '-fps_mode', 'cfr', '-r', f'{rate:g}',
           '-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf), '-g', str(gop), '-pix_fmt', 'yuv420p',
           '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', a.out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    after = probe(a.out)
    with open(meta_path, 'w') as fh:
        json.dump({'source': os.path.abspath(a.clip), 'start': a.start, 'end': end, 'before': before, 'after': after,
                   'notes': notes}, fh, indent=1)
    print(f"wrote {a.out}: {after['duration']:.2f} s, {after['width']}x{after['height']}, {after['fps']:g} fps, "
          f"{after['frames']} frames, {after['size_mb']:.1f} MB, audio {'yes' if after['has_audio'] else 'no'}")
    for n in notes or ['nothing needed fixing; re-encoded for a clean, seekable upload']:
        print('  -', n)
    print(f'  facts in {meta_path}. Upload {a.out} with upload_asset.')


if __name__ == '__main__':
    main()
