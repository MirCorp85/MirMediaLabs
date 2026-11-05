# Sound

The edit keeps the source's motion frame for frame, so the source's sound still fits: lips, footsteps, a cup set down.
Keep the model from making new sound and put the original back.

## Rules

- **`generateAudio: false` on every edit.** On 21 Oct both new-place edits run with it on came back with murmured
  speech that nobody asked for (a transcriber read whole phrases out of it), on top of ambience that ignored the
  footsteps. The builder sets it off unless you pass `--new-audio`.
- **Same place, same sound.** Swaps, outfits, recasts and restyles: `alter_finish.py source output --out final.mp4`
  lays the source sound back, cut to the same frames when you trim.
- **New place, new ambience.** Make an ambience bed with a sound-effects model (prompt the place, "recorded on a
  phone", and end with "no voices, no music"; `loop: true`; a little longer than the clip), then
  `alter_finish.py source output --out final.mp4 --audio bed.mp3`. The bed loops if it is shorter than the picture.
  If the source has dialogue, mix the dialogue over the new bed in an editor instead; do not lose the words.
- **A recast to a different voice.** The source voice no longer fits a new face of another age or gender. Keep the
  words and timing by running the source line through a voice changer (speech to speech) with a voice that fits, then
  lay that. Text-to-speech re-reads the line with new timing and the lips stop matching.
- **Variants reel.** `alter_versions.py` lays the source sound under every version, which is right while the place
  stays the same.

## Check

- Listen once at the end, or at least transcribe it: a sound bed with words in it is a fail.
- Compare loudness between versions shown together; keep beds about as loud as the source ambience.
