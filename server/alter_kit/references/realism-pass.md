# The target frame: show the model the finished look

## Why

Given a flat studio sheet of a new product, the edit lays the design on top of the footage. The print floats above
condensation, stops the highlights at its edge, and the old object's shape can survive under it. Viewers read that as
"pasted on" in a single frame, even when the motion is perfect.

The model copies an example of the finished look far better than it infers one. So first make one real frame of this
shot with the change already done, photographed in this light, and give the edit that frame as `@image1`.

Measured on 21 Oct, the same take and the same prompt, a paper cup swapped for a slim can:

| Reference                                                                                 | Result                                                                                                           |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| The flat product sheet only                                                               | the cup's tapered shape survived at the lips; the print sat on it like a sticker; the can was cup-sized          |
| A target frame (the toast frame with the can photographed in) plus the sheet as `@image2` | a slim can with the sun highlight running down the metal, the right proportions from the first frame to the last |

The same method made the outfit, recast and new-place references in that run, and it is what turns a restyle that
stayed half photographic into a full one (`references/presets.md`).

## Steps

1. **Pick the frame.** `python3 scripts/alter_frame.py source.mp4 --sheet moments.jpg` shows 12 moments; then
   `--t <seconds> --out frame.png`.
   - Swaps: where the element is biggest and least covered by hands.
   - Outfits, recasts, new places: a frame where the whole body and the face show, front-on (often the first frame).
   - Restyles: the first frame.
2. **Upload it** with `upload_asset` (multipart path, `references/scenario-mcp.md`).
3. **Edit it with the image model** (`aspectRatio` of the clip, `resolution: "2K"`, `numOutputs: 2`),
   `referenceImages: [frame, product or design sheet]`. If the user only describes the new thing in words, pass the
   frame alone and describe it fully in the prompt; if they need the same product across many shots, make a
   product sheet first and use it in every target frame. Prompt shapes that worked:
   - Swap: "Photo retouch. Keep the photograph @image1 exactly as it is: same framing, same person, same hand and
     fingers, same light, background, focus and grain. Only the {element} changes: remove the {old element}
     completely and put the {new element} from @image2 {in the hand / on the body} instead, held the same way. The
     {element} is a real object photographed in this light: {the print follows the curve / the sun puts a highlight
     down the metal / the fingers overlap the print}. It must look photographed, not pasted on. No text, no letters,
     no logos."
   - Outfit: "... Only his top changes: instead of the {old} he wears {new}. The fabric creases naturally with his
     stride, the low sun rims its shoulder exactly like the {old} before. It must look photographed, not pasted on."
   - Recast: "... Only the person changes: instead of the {old person} it is {new person}, wearing exactly the same
     {clothes}. Real skin texture, not retouched, an ordinary person, not a model."
   - New place: "Keep the {person} in @image1 exactly as they are: same face, clothes, pose and stride, same size and
     position in the frame, same camera height and lens. Change the whole place around them: {place}. Their light
     and shadows match the new place. No text, no signs, no letters, no logos."
   - Restyle: "Redraw the photograph @image1 completely as a frame of {style}. Same composition, same framing, same
     person in the same pose ... Everything is {drawn / painted / sculpted / rendered}: {how each part looks}.
     Nothing photographic remains."
4. **Pick the better of the two at 100%.** Light direction matches; texture, droplets and frost sit on top of a print;
   liquid colour and container shape are right; the person is the same size and in the same place as in the source
   frame (a new place that moves the performer costs alignment); no letters anywhere.
5. **Run the edit** with that frame as `@image1` (the builder binds it), the sheet as `@image2` if useful.

## Choosing per shot

- Use a target frame for every swap the viewer sees in close-up, every recast and every new place.
- On small, fast or motion-blurred shots a flat reference can be enough. Compare both and keep the one that holds
  continuity across the sequence.
- The edit can still drift: a drink changing colour, a print becoming an opaque sleeve. Keep the other take for that
  shot; consistency beats one better close-up.

## Cost

Two target frames cost a small fraction of one video edit, and the edit costs the same with or without them.
