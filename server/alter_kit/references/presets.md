# ALTER presets

`scripts/alter_prompt.py` builds every prompt from `presets.json`: the mode's opening block, the preset's change line,
then the close block. This page explains the rules behind them and lists every preset. Run
`python3 scripts/alter_prompt.py --show <preset>` for one preset in full.

## The opening block decides what may change

- **O, swap: keep everything.** "Edit @video1. Keep absolutely everything exactly the same, frame for frame: {who}
  (face, body, every movement and expression), the camera movement, framing and lens, the set, the light and the
  timing." Then the one change. `{who}` describes the person without the thing that changes.
- **M, motion transfer: keep the performance and the camera.** "Edit @video1. Keep exactly the same camera movement,
  framing, timing and every movement, gesture and expression of {who}, frame for frame." Then who or where changes,
  and what else stays (the clothes, the set and the light for a recast; the performer for a new place).
- **R, restyle: keep motion and composition only.** "Restyle @video1 completely into {style}. Redraw every part of every
  frame in this style, {who} and the whole background alike; nothing may stay photographic ... Keep exactly the same
  camera movement, framing, timing and every movement of {who}, frame for frame." Then the people and the background
  described as they look in the style, and "It must look like a version of the shot made from scratch in this style,
  not a filter over the video."
  - Never put "keep the light / keep the set / keep everything" in a restyle: the model returns the source unchanged
    (tested 13 Oct). The builder refuses it.
  - Describe the background as art ("hand-painted anime background art with flat colour areas and painted clouds").
    A restyle that only described the people drew the people and left the sea and sky photographic (21 Oct, at 480p
    and at 720p alike, so it was the prompt and not the resolution).
  - Noir and animation-to-live keep a photographic result, so they use a shorter opening without "nothing may stay
    photographic".

Every prompt ends with the close block: "Nothing else changes. No text, no letters, no logos, no watermarks." (for
restyles: the "not a filter" line and "No text, no letters, no logos.").

## Binding the references

- `@image1` is always the most specific reference: the target frame (a frame of this shot with the change done) for
  swaps, outfits, recasts and new places.
- Further references follow as `@image2...` and are bound in a sentence (`--extra "@image2 shows the same can alone,
for its design from every side"`).
- **Restyles: prompt first, then a target frame.** With `--image`, the builder binds the image as "@image1 is the first
  frame of the result: every frame must look exactly like it." That is this shot's first frame redrawn in the style
  (Gemini, same composition). Measured on 21 Oct on one take:

  | Restyle          | Prompt only                                             | With the redrawn first frame                                     |
  | ---------------- | ------------------------------------------------------- | ---------------------------------------------------------------- |
  | Hand-drawn anime | people drawn, sea and sky photographic (structure 0.72) | everything drawn (0.55)                                          |
  | 3D feature       | fully converted with the strong prompt (0.22)           | not needed                                                       |
  | Claymation       | stayed photoreal on 13 Oct (2 of 2)                     | puppet, sculpted sea, cotton-wool clouds (0.25)                  |
  | Watercolour      | sky painted, man photographic (0.87)                    | better as a draft (0.58), sharpened back after finalising (0.75) |

  On 13 Oct a style frame cut from the same shot anchored the model to the photo (2 of 2). The difference on 21 Oct
  was the binding ("the first frame of the result") together with the stronger opening. A style image of a different
  scene (`--style-image`) added little.

## Presets

### Products and props

| Preset            | Mode  | Fill                            | Change line                                                                                                                                                                                                     |
| ----------------- | ----- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `product-swap`    | O, TF | who, object, product            | Change only the {object} in the hand: it becomes the {product} from @image1, held exactly the same way at the same size, printed and lit exactly as in @image1.                                                 |
| `label-redesign`  | O, TF | who, container                  | Change only the printed artwork on the {container}: it looks exactly like @image1, printed for real on the material, following its curve, with the same highlights, condensation and frost on top of the print. |
| `colourway`       | O, TF | who, object, colour             | Change only the colour of the {object} to {colour}, same material, same finish, same reflections, as in @image1.                                                                                                |
| `de-logo`         | O     | who, object                     | Remove every logo, brand mark, word and number from the {object}; the surfaces stay plain, same material and colour.                                                                                            |
| `prop-swap`       | O     | who, prop, new_prop             | The {prop} becomes the {new_prop} from @image1, same size in the hand, moving exactly as the original does.                                                                                                     |
| `device-swap`     | O, TF | who, device, new_device, screen | The {device} becomes the {new_device} from @image1, same grip, same screen angle; the screen shows {screen}.                                                                                                    |
| `food-drink-swap` | O, TF | who, food, new_food             | The {food} becomes the {new_food} from @image1, same portion size, same steam or condensation, same way of eating or drinking.                                                                                  |
| `vehicle-swap`    | O     | who, vehicle, new_vehicle       | The {vehicle} becomes the {new_vehicle} from @image1, same path, speed, lane and reflections; no badges, no plate text.                                                                                         |
| `shoe-swap`       | O, TF | who, shoes                      | The shoes become the {shoes} from @image1, plain uppers with no logos, stars, stripes or patches, same steps and ground contact.                                                                                |
| `accessory-swap`  | O     | who, accessory                  | Add or change only the {accessory} to the one in @image1, sitting naturally and moving with the body.                                                                                                           |

### Wardrobe and look

| Preset          | Mode  | Fill                 | Change line                                                                                                                                                                         |
| --------------- | ----- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `outfit`        | O, TF | who, outfit          | Change only the clothes to the outfit in @image1, which is a frame of this same shot: {outfit}. Same fit to the body, the fabric moving and creasing naturally with every movement. |
| `costume`       | O, TF | who, costume         | The clothes become {costume} as in @image1, worn naturally, same movement.                                                                                                          |
| `season-outfit` | O     | who, season, clothes | Dress {who} for {season}: {clothes}, same movement; the set and light stay as they are.                                                                                             |
| `hair-makeup`   | O, TF | who, hair, makeup    | Change only the hair to {hair} and the makeup to {makeup}, as in @image1; face, expression and identity unchanged.                                                                  |

### Cast and character

| Preset           | Mode  | Fill                    | Change line                                                                                                                                                                                               |
| ---------------- | ----- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `recast`         | M, TF | who, new_person         | The person becomes the person in @image1, which is a frame of this same shot: {new_person}. Same movements, expressions and lip movements; the clothes, the set and the light stay exactly as in @video1. |
| `creature`       | M     | who, creature           | {who} becomes {creature} from @image1, real anatomy and weight, matching every movement and timing.                                                                                                       |
| `animal-swap`    | M     | who, animal, new_animal | The {animal} becomes a {new_animal} from @image1, real fur and anatomy, same run, same path, same timing.                                                                                                 |
| `mascot-3d`      | M     | who                     | {who} becomes the 3D animated character in @image1, feature-film rendering, same performance.                                                                                                             |
| `game-character` | M     | who                     | {who} becomes the game character in @image1 (exact costume, colours, proportions), performing exactly the same movements.                                                                                 |
| `my-character`   | M     | who                     | {who} becomes the recurring character in @image1, identical face and outfit as in @image1, same performance.                                                                                              |

### World and time

| Preset         | Mode  | Fill          | Change line                                                                                                                                                                                                                                   |
| -------------- | ----- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `new-location` | M, TF | who, location | Move the whole scene to {location} as in @image1, which is a frame of this same shot in the new place: new ground, walls, sky and background; same performer, same clothes, same movements and camera path, light motivated by the new place. |
| `time-of-day`  | M     | who, time     | Same place at {time}; the light direction and shadows change, nothing else.                                                                                                                                                                   |
| `weather`      | M     | who, weather  | Same place in {weather}: wet surfaces and reflections, the clothes reacting to it; same movements.                                                                                                                                            |
| `era`          | M     | who, era      | The scene becomes {era}: set, clothes, props and film look of the period; same movements and camera.                                                                                                                                          |
| `sci-fi`       | M, TF | who, world    | The scene becomes {world} as in @image1, same performer and movements, light from the new world.                                                                                                                                              |
| `game-level`   | M     | who           | The scene becomes the game environment in @image1 (exact architecture and palette), same performer, movements and camera path.                                                                                                                |

### Restyle

| Preset              | Mode                | Fill               | Change line                                                                                                                                                                                                                                                                                                                                                             |
| ------------------- | ------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `anime`             | R, (TF)             | who, place         | style: a hand-drawn 2D anime feature film: clean ink lines, flat cel shading with one shadow tone, painted backgrounds. {who} is a hand-drawn anime character with the same hair and clothes. The background ({place}) is hand-painted anime background art with flat colour areas and painted clouds.                                                                  |
| `clay`              | R, (TF), unreliable | who, place         | style: stop-motion claymation: plasticine puppets with thumbprints, a handmade miniature set. {who} is a plasticine puppet with the same hair and clothes. The background ({place}) is a handmade miniature set of clay, card and felt.                                                                                                                                 |
| `3d-feature`        | R, (TF)             | who, place         | style: a 3D animated feature film: stylised characters with slightly larger heads and hands, smooth stylised skin and sculpted hair, soft global illumination, a stylised 3D set. {who} is a stylised 3D animated character with the same hair and clothes. The background ({place}) is a stylised 3D set: soft rounded shapes, sculpted clouds, clean simple surfaces. |
| `painterly`         | R, (TF)             | who, medium, place | style: a moving {medium} painting on textured paper or canvas: visible brush strokes that follow the motion. {who} is painted with soft edges and a little underdrawing. The background ({place}) is loose {medium} washes and a few confident strokes.                                                                                                                 |
| `noir`              | R, (TF)             | who                | style: 1940s black-and-white film noir: hard key light, deep shadows, venetian-blind light, heavy grain. {who} wears the same clothes, lit like a 1940s studio picture.                                                                                                                                                                                                 |
| `pixel-retro`       | R, (TF)             | who, retro, place  | style: {retro}: crisp pixels, a limited palette. {who} and the background ({place}) are drawn in this style.                                                                                                                                                                                                                                                            |
| `comic-ink`         | R, (TF)             | who, place         | style: inked comic-book art: bold outlines, halftone shading, flat colour. {who} and the background ({place}) are inked in this style.                                                                                                                                                                                                                                  |
| `animation-to-live` | R, (TF)             | who                | style: photoreal live action: real people, real materials and real light. {who} is a real person with the same hair and clothes; every surface is real.                                                                                                                                                                                                                 |

### Ads and repurposing

| Preset            | Mode  | Fill                 | Change line                                                                                                                                                                |
| ----------------- | ----- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `market-variant`  | M, TF | who, market, setting | Recast for {market}: the person becomes the person in @image1 and the setting becomes {setting} as in @image2; same action, timing and product handling; no signs or text. |
| `phone-to-studio` | M     | who                  | Make it look shot by a film crew: clean motivated light, a cinema lens, graded colour; same people, framing and timing.                                                    |

TF: the preset works best with a target frame (`references/realism-pass.md`). (TF): optional, for restyles whose
background stays photographic.

## Notes

- One preset per run. For two changes, run the second on the first's output.
- `recast`: the reference must wear the source's clothes, or its own clothes leak in. A bare face crop under a beanie
  and glasses only aged the original face (13 Oct). The first two or three frames can open on the reference's
  expression: trim them with `alter_finish.py --trim-head`.
- `new-location`: keep the performer at the same size and position as in the source frame. A world change rebuilds
  almost every edge, so its structure score is low by nature; judge it on the motion match.
- `market-variant` changes two things at once on purpose (person and setting): check it twice as carefully.
- Real people: recast only with references the user has the right to use. Never recreate a real person from memory.
- IP and content filters return a 422 or a policy error for some characters, brands and logos, including logos on
  clothes in the input video. Do not reword around them; change the input or ask the user.
