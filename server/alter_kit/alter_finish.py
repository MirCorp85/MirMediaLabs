"""Deliver an ALTER output: conform it to the source, lay the source audio back, optionally export before/afters.

Usage: python3 alter_finish.py source.mp4 output.mp4 --out final.mp4 [--compare] [--audio other.wav]
       [--trim-head N] [--trim-tail N] [--labels "ORIGINAL,ALTER"] [--keep-size] [--force]
--trim-head / --trim-tail cut N frames from the start or end of the picture and the sound together (a recast that
opens on the reference's expression; the last frames that alter_check.py reports as tail drift).
--audio lays another track instead of the source sound (an ambience made for a new world); it loops when shorter.
--compare also writes final_side.mp4 (side by side) and final_wipe.mp4 (one left-to-right wipe from the source to
the output, eased, no back-and-forth). Never overwrites without --force.
"""
import argparse
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import guard, probe, stream_frames

FONTS = [r'C:\Windows\Fonts\arialbd.ttf', r'C:\Windows\Fonts\segoeuib.ttf',
         '/System/Library/Fonts/Helvetica.ttc', '/System/Library/Fonts/SFNS.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
    return ImageFont.load_default()


def label(img, text, xy, size, anchor='la'):
    d = ImageDraw.Draw(img)
    f = font(size)
    x, y = xy
    for dx, dy in ((2, 2), (1, 1)):
        d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0), anchor=anchor)
    d.text((x, y), text, font=f, fill=(255, 255, 255), anchor=anchor)


def conform(src_info, output, path, keep_size, n_frames, head=0):
    """Output at the source's rate and size, frames [head, head + n_frames) of the source's clock."""
    fps = src_info['fps']
    vf = f'fps={fps},'
    if not keep_size:
        vf += f"scale={src_info['width']}:{src_info['height']}:flags=lanczos,setsar=1,"
    vf += f'tpad=stop_mode=clone:stop=2,trim=start_frame={head}:end_frame={head + n_frames},setpts=PTS-STARTPTS'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', output, '-vf', vf, '-an', '-c:v', 'libx264', '-crf', '12',
                    '-pix_fmt', 'yuv420p', path], check=True)


def trim_source(source, path, head, n_frames, fps):
    """The source cut to the same frames, so side by side and wipe stay aligned after a trim."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', source, '-vf',
                    f'trim=start_frame={head}:end_frame={head + n_frames},setpts=PTS-STARTPTS', '-an',
                    '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', path], check=True)


def audio_inputs(audio_src, start, loop):
    if not audio_src:
        return []
    return (['-stream_loop', '-1'] if loop else []) + ['-ss', f'{start:.4f}', '-i', audio_src]


def mux(video, audio_src, dur, out, start=0.0, loop=False):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', video]
    if audio_src:
        cmd += audio_inputs(audio_src, start, loop) + ['-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k']
    cmd += ['-c:v', 'copy', '-t', f'{dur:.4f}', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)


def write_frames(frames_iter, w, h, fps, audio_src, dur, out, start=0.0, loop=False):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', f'{fps}',
           '-i', '-']
    if audio_src:
        cmd += audio_inputs(audio_src, start, loop) + ['-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k']
    cmd += ['-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-t', f'{dur:.4f}', '-movflags', '+faststart', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames_iter:
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source'); ap.add_argument('output')
    ap.add_argument('--out', required=True)
    ap.add_argument('--audio', default=None, help='audio file to lay instead of the source audio (loops if shorter)')
    ap.add_argument('--trim-head', type=int, default=0, help='frames to drop at the start, picture and sound')
    ap.add_argument('--trim-tail', type=int, default=0, help='frames to drop at the end, picture and sound')
    ap.add_argument('--compare', action='store_true')
    ap.add_argument('--labels', default='ORIGINAL,ALTER')
    ap.add_argument('--keep-size', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    base = os.path.splitext(a.out)[0]
    for path in [a.out] + ([base + '_side.mp4', base + '_wipe.mp4'] if a.compare else []):
        guard(path, a.force)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    si = probe(a.source)
    head, tail = max(a.trim_head, 0), max(a.trim_tail, 0)
    n = si['frames'] - head - tail
    if n < 1:
        raise SystemExit('nothing left after the trims')
    fps = si['fps']
    dur = n / fps
    start = head / fps if not a.audio else 0.0
    audio = a.audio or (a.source if si['has_audio'] else None)
    loop = bool(a.audio)
    got = round(probe(a.output)['duration'] * fps)
    if abs(got - si['frames']) > 2:
        print(f'  warning: output {got} frames vs source {si["frames"]}; the audio will drift. Re-run the edit with duration -1.')
    tmp = tempfile.mkdtemp(prefix='alter_fin_')
    conf = os.path.join(tmp, 'conf.mp4')
    conform(si, a.output, conf, a.keep_size, n, head)
    mux(conf, audio, dur, a.out, start, loop)
    trims = f', trimmed {head} head / {tail} tail frames' if head or tail else ''
    print(f'wrote {a.out} ({n} frames, {dur:.3f} s, {"source" if not a.audio else "given"} audio{trims})')
    if not a.compare:
        return
    src = a.source
    if head or tail:
        src = os.path.join(tmp, 'src.mp4')
        trim_source(a.source, src, head, n, fps)
    left, right = a.labels.split(',')
    W, H = si['width'], si['height']
    m = n
    # side by side: two panes on a black frame, labels under each
    pw = (W - W // 40 * 3) // 2
    ph = round(pw * H / W)
    gap = W // 40
    y0 = (H - ph) // 2

    def side():
        for s_fr, o_fr in zip(stream_frames(src, pw, ph), stream_frames(conf, pw, ph)):
            canvas = Image.new('RGB', (W, H))
            canvas.paste(Image.fromarray(s_fr), (gap, y0))
            canvas.paste(Image.fromarray(o_fr), (gap * 2 + pw, y0))
            label(canvas, left, (gap, y0 + ph + H // 40), H // 28)
            label(canvas, right, (gap * 2 + pw, y0 + ph + H // 40), H // 28)
            yield np.asarray(canvas)
    write_frames(side(), W, H, fps, audio, dur, base + '_side.mp4', start, loop)

    def wipe():
        for i, (s_fr, o_fr) in enumerate(zip(stream_frames(src, W, H), stream_frames(conf, W, H))):
            u = smooth((i / max(m - 1, 1) - 0.15) / 0.7)
            x = int(round(W * u))
            fr = s_fr.copy()
            fr[:, :x] = o_fr[:, :x]
            img = Image.fromarray(fr)
            d = ImageDraw.Draw(img)
            if 0 < x < W:
                d.rectangle([x - 1, 0, x + 1, H], fill=(255, 255, 255))
            if x > W * 0.12:
                label(img, right, (W // 40, H // 30), H // 26)
            if x < W * 0.88:
                label(img, left, (W - W // 40, H // 30), H // 26, anchor='ra')
            yield np.asarray(img)
    write_frames(wipe(), W, H, fps, audio, dur, base + '_wipe.mp4', start, loop)
    print(f'wrote {base}_side.mp4 and {base}_wipe.mp4')


if __name__ == '__main__':
    main()
