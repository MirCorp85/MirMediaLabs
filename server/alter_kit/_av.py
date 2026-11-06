"""Shared ffmpeg/ffprobe helpers for the ALTER scripts. Local only: no network."""
import json
import os
import shutil
import subprocess

import numpy as np

HDR_TRANSFERS = {'arib-std-b67': 'HLG', 'smpte2084': 'PQ'}


def need_ffmpeg():
    for tool in ('ffmpeg', 'ffprobe'):
        if shutil.which(tool) is None:
            raise SystemExit(f'{tool} not found on PATH. Install ffmpeg first (macOS: brew install ffmpeg).')


def guard(path, force):
    """Refuse to overwrite an existing output unless --force was given."""
    if os.path.exists(path) and not force:
        raise SystemExit(f'{path} already exists. Pick another path or pass --force to replace it.')


def _rate(s):
    num, den = (int(x) for x in (s or '0/1').split('/'))
    return num / den if den else 0.0


def probe(path, count=True):
    """Return dict: duration, width, height, fps, frames, has_audio, hdr, rotation, vfr, codec."""
    need_ffmpeg()
    if not os.path.exists(path):
        raise SystemExit(f'{path}: file not found')
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f'{path}: ffprobe could not read it ({out.stderr.strip()[:200]})')
    j = json.loads(out.stdout)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
    if v is None:
        raise SystemExit(f'{path}: no video stream')
    # r_frame_rate is the stream's real cadence; avg_frame_rate drifts on concatenated or VFR-muxed files
    r, avg = _rate(v.get('r_frame_rate')), _rate(v.get('avg_frame_rate'))
    fps = r if 0 < r <= 120 else avg
    dur = float(j['format'].get('duration') or v.get('duration') or 0)
    frames = round(dur * fps)
    if count:
        # exact decoded frame count (container estimates are off by a frame or two on many files)
        cnt = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                              'stream=nb_read_frames', '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip()
        frames = int(cnt) if cnt.isdigit() else frames
    rotation = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd:
            rotation = int(round(float(sd['rotation']))) % 360
    if 'rotate' in (v.get('tags') or {}):
        rotation = int(v['tags']['rotate']) % 360
    w, h = int(v['width']), int(v['height'])
    if rotation in (90, 270):
        w, h = h, w   # the picture as displayed
    return {'duration': dur, 'width': w, 'height': h, 'fps': fps, 'frames': frames,
            'has_audio': any(s['codec_type'] == 'audio' for s in j['streams']),
            'hdr': HDR_TRANSFERS.get(v.get('color_transfer', '')), 'rotation': rotation,
            'vfr': bool(r and avg and abs(r - avg) > 0.05 * r), 'codec': v.get('codec_name'),
            'pix_fmt': v.get('pix_fmt'), 'size_mb': os.path.getsize(path) / 1e6}


def read_frames(path, width=None, height=None, gray=False, fps=None):
    """Decode a whole clip to a uint8 array (N, H, W[, 3]). Scale down for analysis to keep memory small."""
    info = probe(path, count=False)
    w = width or info['width']
    h = height or (round(info['height'] * w / info['width'] / 2) * 2 if width else info['height'])
    vf = [f'scale={w}:{h}:flags=area']
    if fps:
        vf.insert(0, f'fps={fps}')
    fmt, ch = ('gray', 1) if gray else ('rgb24', 3)
    # passthrough: one decoded picture per stored frame, never duplicated or dropped (unless resampling to fps)
    sync = [] if fps else ['-fps_mode', 'passthrough']
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-vf', ','.join(vf), *sync,
                          '-f', 'rawvideo', '-pix_fmt', fmt, '-'], capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8)
    n = arr.size // (w * h * ch)
    arr = arr[:n * w * h * ch]
    return arr.reshape(n, h, w) if gray else arr.reshape(n, h, w, 3)


def run(cmd):
    subprocess.run(cmd, check=True)


def stream_frames(path, width, height):
    """Yield RGB frames one at a time at width x height (memory-flat for long clips)."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-vf', f'scale={width}:{height}:flags=lanczos',
                          '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    size = width * height * 3
    try:
        while True:
            b = p.stdout.read(size)
            if len(b) < size:
                break
            yield np.frombuffer(b, np.uint8).reshape(height, width, 3)
    finally:
        # closed early (a reel cut short with --frames): stop the decoder instead of letting it hit a broken pipe
        if p.poll() is None:
            p.kill()
        p.stdout.close(); p.wait()


def frame_at(path, index):
    """One full-resolution RGB frame by index."""
    info = probe(path, count=False)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-vf', f'select=eq(n\\,{index})',
                          '-fps_mode', 'passthrough', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(info['height'], info['width'], 3)
