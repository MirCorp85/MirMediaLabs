# Check before anyone sees it

Run `python3 scripts/alter_check.py source.mp4 output.mp4 --out qa/ --mode swap|recast|motion|restyle`. It writes
`qa/report.json`, `qa/sheet.jpg` (source over output at 8 moments, each labelled with its structure score) and
`qa/crops.jpg` (100% crops of where the edit changed the picture most, at four moments), and prints PASS or CHECK.
Then look at the crops. The numbers find broken edits; only eyes find brand marks, extra fingers and stray letters.

## What it measures

- **Length.** Output frames against source frames. Edit mode returns the source's exact frame count.
- **Change.** The share of the frame that visibly differs from the source.
  - Swap: 0.4% to 55%. Zero means the swap did not happen. A product in a hand is small for most of a clip (1.9% for
    the cup-to-can swap), so a low number is normal; look at the crops.
  - Recast: at least 1% (a face in a wide shot is a few percent whether or not the new identity took). Identity is
    not measured: compare the faces.
  - Motion transfer: at least 5%. A new place changes most of the frame (82% measured).
  - Restyle: at least 15%. A faithful restyle keeps the scene's colours, so its pixel change can be modest.
- **Structure.** Per frame, the correlation between the source's and the output's edge maps. For a restyle the median
  must be 0.65 or lower: above that, the source's surface detail survived (a re-grade, or people drawn over a
  photographic background). For a swap or recast a low median means the edit rebuilt more than the one element.
- **Motion match.** Correlation of frame-to-frame change, measured on a coarse 40 px grid so that rain, neon and water
  shimmer in a new world do not count. Below 0.60 the output was re-timed or frozen.
- **Jumps.** Between two frames the output changes far more than the source did: a pose reset, a cut, a morph.
  Tested on a source with ten frames spliced in from earlier: both splice points found, nothing else.
- **Tail drift.** A run of lost structure that ends on the last frame: the edit settles differently in the last third
  of a second when the source ends on a fast move. The report says how many frames to trim
  (`alter_finish.py --trim-tail N`). Trim the same number from every version of a set so they loop together.
- **Drift (swaps only).** Six or more frames in a row (a quarter second at 24 fps) that lose the source structure
  mid-clip. Shorter dips happen when the new object has a different outline (a slim can replacing a short cup dipped
  for 3 frames while matching the source by eye). In other modes new hair, worlds and styles move edges without
  anything being wrong. Short dips are listed in `report.json` as `minor_structure_dips` and not reported.
- **Frozen frames.** Runs where the output stands still while the source moves.

## Calibration

| Case (date)                                                 | Changed | Structure | Motion                       | Verdict                                                                |
| ----------------------------------------------------------- | ------- | --------- | ---------------------------- | ---------------------------------------------------------------------- |
| Cup to can with a target frame (21 Oct)                     | 1.9%    | 0.76      | 0.90                         | PASS after trimming 9 tail frames                                      |
| Three outfits with target frames (21 Oct)                   | 8-12%   | 0.68-0.72 | 0.93-0.97                    | PASS (two needed tail trims)                                           |
| Recast to a grandmother, target frame (21 Oct)              | 6.2%    | 0.53      | 0.98                         | PASS, identity checked by eye                                          |
| Recast to a young woman with long braids (21 Oct)           | 2.2%    | 0.75      | 0.98                         | PASS after a tail trim; mid-clip dips were the braids, listed as minor |
| New place, snowy village (21 Oct)                           | 82%     | 0.30      | 0.90                         | PASS                                                                   |
| New place, night street with neon and rain (21 Oct)         | 83%     | 0.14      | 0.86 (0.58 on the fine grid) | PASS: the coarse grid ignores the shimmer                              |
| Anime, prompt only (21 Oct)                                 | 23%     | 0.69      | 0.91                         | CHECK: people drawn, background photographic                           |
| Anime, redrawn first frame (21 Oct)                         | 27%     | 0.55      | 0.80                         | PASS                                                                   |
| 3D feature, prompt only, strong opening (21 Oct)            | 32%     | 0.22      | 0.94                         | PASS                                                                   |
| 3D feature, prompt describing people only (21 Oct)          | 2.6%    | 0.83      | 0.98                         | CHECK: only the face turned cartoon                                    |
| Claymation, redrawn first frame (21 Oct)                    | 56%     | 0.25      | 0.89                         | PASS                                                                   |
| Watercolour, redrawn first frame, after finalising (21 Oct) | 53%     | 0.75      | 0.91                         | CHECK: finalising sharpened it back toward the photo                   |
| Bottle swap with a target frame (13 Oct)                    | 7.2%    | 0.74      | 0.99                         | PASS                                                                   |
| Warm re-grade instead of a 3D restyle (13 Oct)              | 57%     | 0.87      | 0.99                         | CHECK                                                                  |
| Ten frames spliced in from earlier (synthetic)              | 0%      | 1.00      | 0.45                         | CHECK: jumps at both splice points                                     |

## What only eyes catch (look at the crops)

- Real-brand marks on sportswear and shoes (stripes down a sleeve, a tick, a star patch), even under "no logos".
- The first frames of a recast opening on the reference's expression; trim them (`--trim-head`).
- Invented props when the model could not see a reference.
- Hands: finger count, the grip on a swapped object, the object passing through fingers.
- Letters on signs, screens and products, especially in a new city street.
- Continuity across a set: the same product, the same wardrobe, the same liquid colour.

## When it fails

- Re-run the same prompt once; takes vary.
- Strengthen or replace the target frame, or narrow the change to one element.
- A restyle that stays photographic: add the redrawn first frame (`references/presets.md`).
- Keep the better take per shot. A continuous action is one generation; never stitch two takes mid-action.
