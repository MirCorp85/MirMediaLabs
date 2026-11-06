# The spec and the blocks

## spec.js

```js
import { Words, Strike, Graph, Hero, Prompt, Stretch, Fly, Notes, Counters, Progress, Chain, Rewind, Picture, Logo } from './blocks.js';
export default {
  title: 'My film',
  bpm: 172, beats: 68, fps: 60,                      // the film is `beats` beats long
  palette: { bg: '#0B1020', paper: '#F3EEE3', accent: '#FFC21A', hot: '#FF8A1F', ink: '#14120E' },
  hud: 'MY FILM  ·  TEASER', hudOut: [65, 67],        // corner brackets, frame counter, REC, timecode; false hides it
  logo: 'logo.svg',                                   // optional; without it the Logo block types a wordmark
  music: { file: 'audio/music.mp3', offset: 7.95, stopBeat: 58, gain: -7 },   // offset: seconds into the track at beat 0
  sounds: { stomp: -1, hit: 1 },                      // level in dB per sound name (custom sounds, or retune a kit sound)
  cues: [[5.5, 'stomp', 1]],                          // extra sounds at beats: [beat, name, gain]
  scenes: [ [Block, startBeat, endBeat, options], ... ],
  captions: [ [startBeat, endBeat, [['Every', 1], ['frame', 2], ...]], ... ],   // optional karaoke caption, top left
};
```

Palette names (`'bg'`, `'paper'`, `'accent'`, `'hot'`, `'ink'`) work anywhere a colour does; any CSS colour
also works. `bg` is the dark ground, `paper` the light ground and light type, `ink` type on light grounds,
`accent` the brand colour. Grounds that are not `bg` switch the HUD and caption to ink.

Blocks with a nominal length (N beats) scale their internal timing to the span you give them; keep close
to N. Every block accepts `whipIn: [dx, dy, dur, roll]` and `whipOut: [...]` (a whip pan of the camera with
a long-shutter smear and a whoosh, landing or leaving the block) and `dir: -1` to mirror its camera roll.

## Words (sequencer, absolute beats)

Kinetic type, one shot per beat or half beat.

```js
[Words, 0, 9, { charge: true, shots: [ { at: 1, style: 'punch3d', text: 'EVERY', fx: 'punch' }, ... ],
                exit: { type: 'zoom', at: 8.1, char: 1 } }]
```

| Shot option | Meaning |
| --- | --- |
| `at` | beat the shot starts (absolute) |
| `style` | `punch3d` extruded word from depth with an echo trail; `slam` huge word, letters tumble in, ghost rows scroll above and below; `stack` `[kicker, word]` the word slams `second` beats later with an accent bar; `pair` `[line1, line2]` from both sides; `split` `[small, big]` the big word slams from the right `second` beats later; `cut` a hard-cut word (for beat cuts) |
| `ground`, `color` | background for the shot (palette name), type colour (defaults to readable on the ground) |
| `size`, `wdth`, `y`, `dy`, `rot` | type size in px, width axis 62 to 125, vertical position, offset, rotation (cut) |
| `in` | `cut` (default), `whipX`, `whipXr`, `whipY` |
| `fx` | `punch` rays, ring, sparks, flash, shake; `hit` flash and shake; `beat` shake and bump only (for runs of cuts); `none` |
| `cue`, `gain`, `big` | sound on the hit (default from `fx`), its gain, `big: true` for the heavier impact |
| `second` | for stack, pair, split: beats until the second element |
| `scramble: [a, b]`, `glitch`, `inverts: [..]` | glyph scramble between beats a and b (relative), an RGB glitch, invert flashes |
| `flip: { at, ground, color }` | change ground and colour mid-shot (relative beat) |
| `dot`, `glyphs`, `code`, `note`, `noteAt` | accent the last character; a burst of code glyphs; the film's source as a backdrop (split); a mono line typed under the word |
| `echo: false`, `tumble: false`, `from` | no ghost rows; no letter tumble; starting scale of the slam |

`charge: true` draws converging speed lines into a glowing point before the first shot. `exit`: `zoom`
(the camera flies through the counter of letter `char` of the last shot: pick a letter with a hole, O, D, 0,
A, B, P, R), `collapse` (`at`, `end`: everything shrinks into the point a logo line can grow from),
`flash` (to white).

## Strike (sequencer)

"NO <thing>." over a mock of the thing, then the thing dies.

```js
[Strike, 9, 19, { no: 'NO', items: [
  { at: 9, word: 'TIMELINE.', ui: { type: 'timeline', title: 'sequence_final_v12', tag: 'EXPORTING 3%' } },
  { at: 12, word: 'PLUGINS.', ground: 'paper', ui: { type: 'tiles', tiles: [['GLOW', '☀', 'PLUG-IN · v2.0'], ...] } },
  { at: 15, word: 'RENDER FARM.', ui: { type: 'rack', rows: ['NODE 01', 'NODE 02', 'NODE 03'] } } ] }]
```

Per item: the mock enters, NO slams at +1 beat, the word fills at +1.5, the mock dies at +2 (`timeline`
is split by a slash, `tiles` topple, `rack` powers down at +2.5). Items after the first whip in. The last
item ends in a TV switch-off point (`tvOff: false` to skip). 3 to 4 beats per item.

## Graph (N = 6)

`{ number: '0', label: 'KEYFRAMES', sub: 'DRAGGED BY HAND', ground: 'paper', ticks: i => i * 4 + 'f', portal: true }`.
Two comets draw axes out of the switch-off point, the camera rides the comet that draws a curve, the
keyframes pop, the graph folds, the number lands with echo rings, and the camera flies through its
counter (a dark portal) into the next block. Use a number with a hole for the portal, or `portal: false`.

## Hero (N = 8)

`{ kicker: 'WRITTEN BY', title: 'OPUS 5.5', sub: 'in Claude Code', chevron: '> ', landZoom: 1.7 }`.
The kicker tumbles in, a comet spirals to the centre, the extruded title flies out of depth, orbits,
flips once, a light sweeps it twice, ghost copies fan out behind it, and the sub line types with a caret.

## Prompt (N = 19)

`{ label: 'BRIEF.md', text: [['plain '], ['keyword', 1], ...], unit: 'CHARS', doodles: true }`.
A comet draws the box, the text types itself while the camera follows the caret, keywords highlight and
pop, the camera pulls back, the keywords pulse, and the camera pushes into the Enter key through
converging speed lines until its accent colour fills the frame on the last beat: start the next block on
an accent ground and it reads as the drop. Typing always fills beats 1.3 to 11.4, whatever the length.

## Stretch (N = 8)

`{ word: 'ELASTIC.', grounds: [[0, 'accent'], [4, 'paper'], [5, 'accent']], code: true }`.
A word on the variable width axis: drop slam, elastic stretch, a weight dip, a squeeze, a stretch,
spreading letters, with ghost rows that lag, a live ruler and the CSS that drives it.

## Fly (N = 11)

`{ words: [['CAMERA', 'paper'], ['FLIES', 'accent'], ['THROUGH', 'paper'], ['THE TYPE.', 'accent']] }`.
Extruded words in depth inside chamfered portals; the camera flies through them with a banked roll and
tunnel dust, lands on the last word and orbits it. 3 to 5 words.

## Notes (N = 16)

`{ preview: 'ELASTIC.', notes: [['hotter orange', 'recolor'], ['cut the intro in half', 'trim'], ['more punch', 'punch']], segments: [['INTRO', 220], ...], tag, panel, file }`.
Three notes typed into a panel; the camera moves between the input, the preview and the timeline; each
note's effect plays (recolor the preview, halve the first segment with a slash, punch on every beat over a
starburst); the note being typed runs huge across the frame.

## Counters (N = 11)

`{ counters: [['1', 'WEB PAGE'], ['{lines}', 'LINES OF CODE'], ['{frames}', 'FRAMES. ALL CODE.']], title, source }`.
The film's own source (or `source` text) as a plane the camera flies over, and giant numbers on slot
reels, one every 3 beats.

## Progress (N = 9)

`{ lines: ['RENDERED', 'ON A LAPTOP.'], cards: [['EVERY', 'bg', 'paper'], ...], label, doneLabel, doneRight, ground: 'paper' }`.
Line 1 renders itself (outline, then a scan line fills it), line 2 slams, frames of the film ride a
conveyor past a render head (outlined until they pass it), a progress bar and a frame counter run to done.

## Chain (N = 12)

`{ nodes: [['BRIEF', 'brief.md · 142 chars'], ['CODE', 'film.js · {lines} lines'], ['FILM.', '4K · 60 FPS', 'accent']] }`.
Three words 2,000 px apart in one world; the camera rides the comet from node to node, each lands with a
ring, then the camera pulls back to show the chain and its trails.

## Rewind (N = 8)

`{ from: seconds, label: 'PLAYBACK' }`. The film so far plays backwards inside a tilting playback window
and lands on its first frame as the window fills the screen.

## Picture (N = 8)

```js
[Picture, 8, 16, { src: 'art/key1.png', words: [[1, 'MONSTERS'], [3, 'NEXT DOOR.', 'accent']], reveal: 'slash',
                   focus: [.55, .45], tint: .3, weather: 'rain', cutIns: [[5, 1.65, [.62, .2], 'stomp']], x: 1380, y: 560 }]
```

The image cuts in along a slash (or zooms in), pushes and pans with a slight 3D tilt, punches in on every
word, hard-cuts in to details (`cutIns: [[beat, scale, [fx, fy], cue]]`, positions 0 to 1 of the image), and
carries a weather layer (`rain`, `snow`, `dust`, or `null`). `tint` darkens it for type, `x`/`y` place the
words (off centre when a face is in the middle). Use images of at least 2048 px wide; cut-ins above 1.7x
look soft at 4K.

## Logo (N = 11)

`{ mark: ['id', ...], word: ['id', ...], tagline: 'Motion design, written in code.', small: 'MADE WITH ...', wordmark: 'NAME', width: 840 }`.
A line, a slash and a hit on beat 1 of the block; the SVG's `mark` paths drop in one by one and its `word`
paths wipe on (without ids the whole logo wipes on; without a logo file `wordmark` is typed); the tagline
and small line follow; then a slow push, drifting particles and a light sweep until the end. The music
should stop dead on beat 1 of this block (`music.stopBeat`).

## Writing a custom block

Copy the smallest block that is close, keep its shape: `build()` creates elements and registers effects
and cues on the film (`f.burst`, `f.ray`, `f.ring`, `f.slash`, `f.comet`, `f.flash`, `f.shake`, `f.bump`,
`f.ground`, `f.cut`, `f.fast`, `f.smear`, `f.cue`, `f.paint` for custom canvas drawing), `update(t)` sets
styles from `t` only, `cam(t)` returns `{ x, y, s, r }` for the camera. Use `set()` (it skips unchanged
values), `tw()` and the eases in `E`, `meas()` once at build time, `relPos()` instead of `offsetLeft`.
Register a `fast` window on fast moves so the renderer takes more motion-blur samples there.
