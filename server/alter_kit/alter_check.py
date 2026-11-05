"""QA an ALTER output against its source.

Usage: python3 alter_check.py source.mp4 output.mp4 --out qa/ [--mode swap|recast|motion|restyle] [--force]
Writes qa/report.json, qa/sheet.jpg (source over output at 8 moments) and qa/crops.jpg (100% crops of the most
detailed regions of the output, for the logo, hand and text check). Exit code 0 = PASS, 1 = CHECK.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # works under python3 -I too
from _av import frame_at, guard, probe, read_frames

# median edge-structure correlation expected per mode (below = the edit rebuilt more than intended)
# a motion transfer that moves the whole scene somewhere new keeps almost no source edges (0.14 to 0.30 measured on
# 21 Oct for a snowy village and a night street that both tracked the performance exactly), so its floor only
# catches an output that has nothing to do with the source; the motion match below is what judges it
FLOOR = {'swap': 0.45, 'recast': 0.45, 'motion': 0.08, 'restyle': 0.12}
# share of the frame that must visibly differ from the source (pixel diff > 40/255 on a 160 px thumbnail)
# a recast of a face in a wide shot changes only 3-5% of the frame, whether or not the identity took, so the
# recast floor only catches a run that changed nothing; identity is judged on the crops
# a faithful restyle keeps the scene's colours, so its pixel change can be modest (27-32% for a full anime and a full
# 3D conversion on 21 Oct); its structure median is what tells a restyle from a re-grade (RESTYLE_MAX below)
CHANGED = {'swap': (0.004, 0.55), 'recast': (0.01, 0.55), 'motion': (0.05, 1.0), 'restyle': (0.15, 1.0)}
# structure median above this = the source's surface detail survived: a re-grade or a half restyle. Measured:
# full restyles 0.22-0.62; people drawn over a photographic background 0.69-0.72; colour re-grades 0.83-0.87
RESTYLE_MAX = 0.65


def edges(g):
    g = g.astype(np.float32)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    return np.hypot(gx, gy)


def pool(x, f=8):
    """Average f x f blocks: motion then follows bodies and the camera, not flickering lights or rain."""
    n, h, w = x.shape
    h2, w2 = h // f * f, w // f * f
    return x[:, :h2, :w2].reshape(n, h2 // f, f, w2 // f, f).mean(axis=(2, 4))


def corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source'); ap.add_argument('output')
    ap.add_argument('--out', required=True)
    ap.add_argument('--mode', choices=list(FLOOR), default='swap')
    ap.add_argument('--force', action='store_true', help='replace an existing report in --out')
    a = ap.parse_args()
    guard(os.path.join(a.out, 'report.json'), a.force)
    os.makedirs(a.out, exist_ok=True)
    si, oi = probe(a.source), probe(a.output)
    fps = si['fps']
    rs = fps if abs(oi['fps'] - fps) > 0.01 else None   # resample the output only if its rate differs
    S = read_frames(a.source, width=320, gray=True)
    O = read_frames(a.output, width=320, gray=True, fps=rs)
    h = min(S.shape[1], O.shape[1])
    S, O = S[:, :h], O[:, :h]
    n = min(len(S), len(O))
    issues = []
    if abs(len(S) - len(O)) > 1:
        issues.append(f'length: source {len(S)} frames, output {len(O)} frames at {fps:.3f} fps')
    struct = np.array([corr(edges(S[i]), edges(O[i])) for i in range(n)])
    med = float(np.median(struct))
    mad = float(np.median(np.abs(struct - med))) + 1e-3
    drops = [i for i in range(n) if struct[i] < med - 4 * mad and struct[i] < 0.75 * med]
    if a.mode == 'restyle' and med > RESTYLE_MAX:
        issues.append(f'restyle: structure median {med:.2f} > {RESTYLE_MAX}; the source surface detail survived (a re-grade, '
                      f'or people drawn over a photographic background). Re-run with a target frame: this shot\'s first '
                      f'frame fully redrawn, bound as the first frame of the result (references/presets.md)')
    if med < FLOOR[a.mode]:
        issues.append(f'structure: median {med:.2f} < {FLOOR[a.mode]} for a {a.mode}; the edit rebuilt too much')
    runs = []
    for i in drops:
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    tail_runs = [r for r in runs if r[-1] >= n - 2 and r[0] >= n - 12]
    mid_runs = [r for r in runs if r not in tail_runs]
    minor = []
    if tail_runs:
        t0 = tail_runs[0][0]
        issues.append(f'tail drift: frames {t0}-{n - 1} of {n} leave the source (edit mode often settles '
                      f'differently in the last half second). Trim them with alter_finish.py --trim-tail '
                      f'{n - t0}, or give the next source a held beat at the end')
    for r in mid_runs:
        # a swap should hold the frame still around the one element; elsewhere new hair, worlds and styles
        # move edges around without anything being wrong, so only a swap reports these
        if a.mode == 'swap' and len(r) >= 6:   # a quarter second; 3-frame dips came from a taller object, not drift
            issues.append(f'drift: frames {r[0]}-{r[-1]} lose the source structure (the edit rebuilt more than the '
                          f'element there); look at those frames')
        else:
            minor.append(f'{r[0]}-{r[-1]}' if len(r) > 1 else str(r[0]))
    # did the edit actually change anything, and about as much as the mode implies?
    Sc_ = read_frames(a.source, width=160).astype(np.int16)
    Oc_ = read_frames(a.output, width=160, fps=rs).astype(np.int16)
    hc = min(Sc_.shape[1], Oc_.shape[1]); m_ = min(len(Sc_), len(Oc_))
    dpx = np.abs(Sc_[:m_, :hc] - Oc_[:m_, :hc]).max(axis=3)
    area = float(np.median((dpx > 40).mean(axis=(1, 2))))
    lo, hi = CHANGED[a.mode]
    if area < lo:
        issues.append(f'change: only {area:.1%} of the frame differs from the source; the {a.mode} did not take '
                      f'(expected at least {lo:.1%}). Re-run with the mode\'s opening block (references/presets.md).')
    elif area > hi:
        issues.append(f'change: {area:.0%} of the frame differs; a {a.mode} should leave most of it alone')
    ms = np.abs(np.diff(S[:n].astype(np.float32), axis=0)).mean(axis=(1, 2))
    mo = np.abs(np.diff(O[:n].astype(np.float32), axis=0)).mean(axis=(1, 2))
    # motion match on a coarse grid (40 px wide): rain, neon and water shimmer in a new world no longer count as
    # motion; the fine-grid energies above are still used to find frozen frames
    msc = np.abs(np.diff(pool(S[:n].astype(np.float32)), axis=0)).mean(axis=(1, 2))
    moc = np.abs(np.diff(pool(O[:n].astype(np.float32)), axis=0)).mean(axis=(1, 2))
    motion = corr(msc, moc) if n > 3 else 1.0
    if motion < 0.6 and ms.std() > 0.3:
        issues.append(f'motion: source/output motion correlation {motion:.2f} < 0.60 (re-timed or frozen?)')
    # jumps: between two frames the output changes far more than the source did (a pose reset, a cut, a morph);
    # tested on a source with ten frames spliced in from earlier: both splice points found, nothing else
    mc = moc[:len(msc)]
    base = float(np.median(mc)) + 1e-3
    jumps = [i + 1 for i in range(len(mc)) if mc[i] > 3 * msc[i] + 2 and mc[i] > 3 * base]
    if jumps:
        issues.append(f'jump at frames {jumps[:10]}: the output changes far more than the source there '
                      f'(pose reset, cut or morph); a continuous action must be one generation')
    frozen, run_ = [], 0
    for i in range(len(mo)):
        run_ = run_ + 1 if (mo[i] < 0.25 and ms[i] > 1.2) else 0
        if run_ == 3:
            frozen.append(i - 2)
    if frozen:
        issues.append(f'frozen output while source moves, from frames {frozen[:10]}')
    # contact sheet: source over output
    picks = np.linspace(0, n - 1, 8).astype(int)
    Sc = read_frames(a.source, width=480); Oc = read_frames(a.output, width=480, fps=rs)
    hh = min(Sc.shape[1], Oc.shape[1])
    sheet = Image.new('RGB', (480 * 8, hh * 2))
    for k, i in enumerate(picks):
        sheet.paste(Image.fromarray(Sc[min(i, len(Sc) - 1), :hh]), (k * 480, 0))
        o = Image.fromarray(Oc[min(i, len(Oc) - 1), :hh]); d = ImageDraw.Draw(o)
        d.rectangle([0, 0, 120, 14], fill=(0, 0, 0)); d.text((3, 2), f'f{i} s={struct[i]:.2f}', fill=(255, 255, 0))
        sheet.paste(o, (k * 480, hh))
    sheet.save(os.path.join(a.out, 'sheet.jpg'), quality=88)
    # 100% crops where the edit changed the picture most (the swapped object, the new face, the hands), weighted by
    # detail, at four moments: this is where brand marks, extra fingers and stray letters show up
    cs = 360
    crops = []
    for i in np.linspace(0, min(oi['frames'], si['frames']) - 1, 4).astype(int):
        fr = frame_at(a.output, int(i))
        H, W = fr.shape[:2]
        src = np.asarray(Image.fromarray(frame_at(a.source, int(round(i * si['fps'] / oi['fps'])) if rs else int(i)))
                         .resize((W, H)), dtype=np.float32)
        change = np.abs(fr.astype(np.float32) - src).mean(axis=2)
        score = change * (1.0 + edges(fr.mean(axis=2)) / 64.0)
        cs_ = min(cs, H, W)
        best = []
        for y in range(0, H - cs_ + 1, cs_ // 2):
            for x in range(0, W - cs_ + 1, cs_ // 2):
                best.append((score[y:y + cs_, x:x + cs_].mean(), x, y))
        best.sort(reverse=True)
        taken = []
        for _, x, y in best:
            if all(abs(x - tx) >= cs_ or abs(y - ty) >= cs_ for tx, ty in taken):
                taken.append((x, y))
            if len(taken) == 2:
                break
        crops += [np.asarray(Image.fromarray(fr[y:y + cs_, x:x + cs_]).resize((cs, cs))) for x, y in taken]
    grid = Image.new('RGB', (cs * 4, cs * 2))
    for k, c in enumerate(crops[:8]):
        grid.paste(Image.fromarray(c), ((k % 4) * cs, (k // 4) * cs))
    grid.save(os.path.join(a.out, 'crops.jpg'), quality=90)
    verdict = 'PASS' if not issues else 'CHECK'
    rep = {'verdict': verdict, 'mode': a.mode, 'source': si, 'output': oi, 'frames_compared': n,
           'changed_area': round(area, 4), 'structure_median': round(med, 3), 'structure_min': round(float(struct.min()), 3),
           'motion_correlation': round(float(motion), 3), 'issues': issues, 'minor_structure_dips': minor,
           'look_at': ['crops.jpg: brand marks, hands, text, invented props', 'sheet.jpg: continuity']}
    with open(os.path.join(a.out, 'report.json'), 'w') as fh:
        json.dump(rep, fh, indent=1)
    print(f'{verdict}: changed {area:.1%} of frame, structure median {med:.2f} (min {struct.min():.2f}), motion {motion:.2f}')
    for s in issues:
        print('  -', s)
    if a.mode == 'recast':
        print('  identity is not measured: compare the faces in sheet.jpg at 100%; a run that only aged or regraded the '
              'original face is a fail (see references/qa.md)')
    print(f'  look at {os.path.join(a.out, "crops.jpg")} and {os.path.join(a.out, "sheet.jpg")} before showing anyone')
    return 0 if not issues else 1


if __name__ == '__main__':
    raise SystemExit(main())
