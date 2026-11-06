---
name: scenario-alter
description: 'Use when changing what is in an existing video while keeping its performance, through the Scenario MCP: swap a product, prop or outfit in the take; recast who performs it; move the scene to a new place; restyle the footage (anime, 3D feature, claymation, comic); make wardrobe, cast or market variants of one take that stay frame-aligned; or alter clips longer than 30 seconds. Builds a photoreal target frame first so swaps look photographed rather than pasted, assembles every prompt from tested presets, drafts at 480p and finalises only the keepers, checks every output against the source (change, structure, motion, jumps, tail drift, 100% crops of what changed), puts the source sound back or lays a new ambience, and exports before/afters and a version reel. Also preps phone footage (HDR, rotation, variable frame rate). Keywords: ALTER, video to video, V2V, object swap, product swap, motion transfer, recast, restyle, wardrobe change, ad variants, change anything keep the performance.'
license: MIT
---

# ALTER: change anything in a video, keep the performance

## Overview

One source clip in, the same performance out with one thing changed: the product in a hand, the outfit, who is on screen, where they are, or the whole look. Motion, camera, timing and framing come from the source frame for frame, so several versions of one take can be cut together on one clock.

The route was built and tested on the Scenario MCP with Seedance 2.5 in edit mode (the change), its Draft Complete model (finalising a 480p draft to 1080p without regenerating), Gemini 3.0 Pro image editing (target frames) and a sound-effects model (ambience for a new place). Local scripts do everything else and never call the network. Find these models by name with `search` each session and stay on them: `recommend` for video2video ranks other edit models first, but the presets, the draft and finalise loop and the checker's thresholds were all measured on Seedance 2.5. Switch only if the user asks, and then re-check the first run with `alter_check.py`.

**Check the Scenario MCP first.** Call `teams_list` (a free read). If the tools are missing, stop and say how to connect: add `https://mcp.scenario.com` to the agent (Claude Code: `claude mcp add --transport http scenario https://mcp.scenario.com`) and sign in. If several teams or projects come back, ask which one to use.

**What it runs on.** Python 3.9 or newer with numpy and Pillow, and ffmpeg. HDR phone footage is tone-mapped with macOS `avconvert` when present, otherwise an ffmpeg build with zscale.

**The three modes.** The opening sentence of the prompt decides what the model may change, so each mode has its own:

| Mode                    | What is kept                            | What changes                                            | Reference that works best                                                                                    |
| ----------------------- | --------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Swap** (O)            | everything, exactly as shot             | one element: product, prop, outfit, hair, device, shoes | a target frame: a frame of this shot with the new element photographed in                                    |
| **Motion transfer** (M) | the performance, the camera, the timing | who performs it, or where it happens                    | a target frame with the new person (in the source's clothes) or the new place                                |
| **Restyle** (R)         | motion and composition only             | the whole rendering                                     | prompt alone first; if the background stays photographic, this shot's first frame fully redrawn in the style |

Related skills: `scenario` (connection and the core loop), `scenario-seedance` (modes and limits), `scenario-video-editing` (trims, grades), `scenario-elevenlabs` (ambience and sound), `scenario-identity-library` (one character across many videos). If one is missing, ask the user to install it (`npx skills add scenario-labs/skills --skill <name>`); unattended, work from the tool schemas and say so.

Work on footage the user owns or has the rights to, and recast only with people who agreed to it.

## Quick reference

```bash
S=~/.claude/skills/scenario-alter/scripts                     # wherever this skill is installed
python3 $S/alter_probe.py clip.MOV                            # limits, HDR, rotation, variable frame rate
python3 $S/alter_prep.py clip.MOV --out prepared.mp4 --start 2 --end 10   # fix all of that, trim to the moment
python3 $S/alter_frame.py prepared.mp4 --sheet moments.jpg    # pick the frame for the target frame
python3 $S/alter_frame.py prepared.mp4 --t 7.7 --out frame.png
python3 $S/alter_prompt.py --list                             # 36 presets, grouped by use, each with its mode
python3 $S/alter_prompt.py product-swap --who "the man with dark curly hair" \
    --set object="white paper coffee cup" --set product="slim cream drinks can" \
    --video asset_SOURCE --image asset_TARGET_FRAME --out run.json   # prompt + run parameters, 480p draft
python3 $S/alter_check.py prepared.mp4 draft.mp4 --out qa/ --mode swap   # swap|recast|motion|restyle
python3 $S/alter_finish.py prepared.mp4 final.mov --out out/final.mp4 --trim-tail 9 --compare
python3 $S/alter_versions.py prepared.mp4 v1.mp4 v2.mp4 v3.mp4 --out reel.mp4 --with-source --frames 184
python3 $S/alter_split.py long.mp4 --out segs/                # over 30 s; then alter_assemble.py segs/manifest.json
```

| Scenario MCP step        | Find the model with                                                     | Inputs (check `model_schema_get` every session)                                                                 |
| ------------------------ | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Connection               | `teams_list`, then `projects_list`                                      | none                                                                                                            |
| Upload source and frames | `upload_asset` with `file_size`, PUT each part, `upload_asset_complete` | parts of the size the reply gives; never add checksum headers                                                   |
| Target frame             | `search` "Gemini 3.0 Pro" (image editing)                               | `referenceImages: [frame, product or design]`, `aspectRatio` of the clip, `resolution: "2K"`, `numOutputs: 2`   |
| The edit, as a draft     | `search` "Seedance 2.5" (not the Draft Complete entry)                  | `prompt`, `referenceVideos: [source]`, `referenceImages`, `duration: -1`, `generateAudio: false`, `draft: true` |
| Finalise a keeper        | `search` "Seedance 2.5 Draft Complete"                                  | `draftVideo: <the draft's asset id>` (valid 7 days)                                                             |
| Ambience for a new place | `search` "ElevenLabs Sound Effects"                                     | `text` (say "no voices, no music"), `durationSeconds`, `loop: true`                                             |

Every paid step: `model_schema_get`, then `model_run` with `dry_run: true`; tell the user the price of each step and the total, then run with `wait: false` and `jobs_wait`. Finalising cannot be dry-run before its draft exists: quote it up front with a dry run of the same edit at `resolution: "1080p"` and no `draft` (finalising cost within about 2% of that on 21 Oct), then dry-run the real finalise once the draft is in. `asset_download` returns a signed URL: fetch it with `curl -sL`. More detail, including uploads and pacing: [references/scenario-mcp.md](references/scenario-mcp.md).

## Workflow

1. **Probe and prep.** `alter_probe.py` says what the clip needs; `alter_prep.py` fixes it: HDR to SDR, rotation baked in, constant frame rate, short side at least 480 px, long side at most 1920 px, trimmed to 4 to 30 seconds. Edit mode settles differently in the last third of a second when the action is fast at the very end (6 of 11 kept edits on 21 Oct, by 3 to 9 frames), so leave a held beat at the end of the span or plan to trim the tail.
2. **One change per run.** Pick one preset (`alter_prompt.py --list`). Two changes in one run ("new outfit and new place") drift more. Read what the user wants:
   - **A chain** ("give him a leather jacket, then make that anime"): run the second change on the first's finalised output. Run it through `alter_prep.py` first (finalised files come back as 10-bit MOV) and upload it as the new source.
   - **Versions** ("a leather jacket version, and also a comic version"): run each change on the original, in parallel. This is the default when the request is ambiguous; say which you chose.
3. **Make the reference a target frame.** Seedance copies an example of the finished look far better than it infers one. For swaps, outfits, recasts and new places, take the clearest frame (`alter_frame.py --sheet`, then `--t`), upload it, and have Gemini change only that element in that frame, photographed in that light. Generate two, look at both at 100%, keep one. Method and prompts: [references/realism-pass.md](references/realism-pass.md).
   - A recast reference wears the source's clothes, or the reference's own clothes leak into the shot.
   - A new place keeps the performer at the same size and position as in the source frame; it holds alignment.
4. **Build the prompt with `alter_prompt.py`.** It writes the mode's opening block, the preset's change line and the close block, binds `@image1`, refuses the combinations that failed in testing, and prints the matching check command. Put the user's words into `--set` slots, not into a rewritten prompt. `--who` describes the person without the thing you are changing ("the man with dark curly hair", not "the man in the olive hoodie" when the hoodie changes): the opening asks to keep everything about `--who`. Presets and rules: [references/presets.md](references/presets.md).
5. **Price, then run 480p drafts.** `dry_run` first. Launch at most five jobs at a time: about 28 jobs in 30 minutes once triggered a multi-hour rate-limit cooldown. A job stuck at the same percentage for 15 minutes is usually dead; relaunch once.
6. **Check every draft.** `alter_check.py source draft --out qa/ --mode ...`, then open `qa/crops.jpg` (100% crops of what changed) and `qa/sheet.jpg`. What it measures and how to read it: [references/qa.md](references/qa.md). Re-run a failed draft once (takes vary) or strengthen its target frame; never stitch two takes mid-action.
7. **Restyles: prompt first, then a target frame.** The default restyle prompt names the background as art ("hand-painted anime background art"). If the check still reports the background photographic (structure above 0.65), redraw this shot's first frame in the style with Gemini and pass it with `--image`: the builder binds it as "the first frame of the result". On 21 Oct that turned a half-converted anime (people drawn, sea and sky still a photo) into a fully drawn one.
8. **Finalise only the keepers** with Draft Complete (same motion, framing and sound, at 1080p), then check again: finalising can sharpen a soft painterly look back toward the photo (a watercolour went from structure 0.58 to 0.75).
9. **Sound.** Keep `generateAudio` off: with it on, both world edits on 21 Oct came back with murmured speech nobody asked for. `alter_finish.py` puts the source sound back (lips and footsteps stay in sync because the motion is the source's). For a new place, make an ambience bed with a sound-effects model and pass it with `--audio`; it loops if shorter. Recasting to a different voice type needs a voice changer on the source line: [references/sound.md](references/sound.md).
10. **Deliver.** `alter_finish.py --trim-tail N --compare` writes the final plus a side by side and a wipe. For variants, `alter_versions.py` cuts between frame-aligned versions on one clock with the source sound. Clips over 30 seconds: `alter_split.py` cuts at real shot changes, run every segment with the same preset and references, then `alter_assemble.py` joins them frame-exact under the original sound.

## Worked example: the cup becomes a can (Scenario MCP)

From the exploration's own run: an 8-second phone take (24 fps, 193 frames) of a man on a seaside promenade who walks, sips from a paper cup, spins and raises the cup to the lens.

```text
teams_list                                   -> pick team and project
upload_asset {file_name:"take.mp4", content_type:"video/mp4", kind:"video", file_size:11460004}
  -> two parts: split -b <part_size>, PUT each part to its URL, upload_asset_complete -> asset_SOURCE
alter_frame.py take.mp4 --t 7.7 --out toast.png  (the cup at its biggest) -> upload -> asset_FRAME
model_run <image model> {prompt:"Photo retouch. Keep the photograph @image1 exactly as it is ... Only the object
  in his hand changes: remove the white paper coffee cup completely and put the slim drinks can from @image2 in
  his hand instead ... It must look photographed, not pasted on. No text, no letters, no logos.",
  referenceImages:[asset_FRAME, asset_CAN_DESIGN], aspectRatio:"16:9", resolution:"2K", numOutputs:2}
  -> two target frames; the one with the sun highlight running down the can wins -> asset_TARGET
alter_prompt.py product-swap --who "the man in the olive hoodie" --set object="white paper coffee cup"
  --set product="slim cream drinks can with a blue circle and an orange quarter-circle"
  --extra "@image2 shows the same can alone, for its design from every side"
  --video asset_SOURCE --image asset_TARGET --image asset_CAN_DESIGN --out swap.json
model_run <edit model> swap.json parameters, dry_run:true -> price; then wait:false; jobs_wait -> draft
alter_check.py take.mp4 draft.mp4 --out qa/ --mode swap
  -> changed 1.9%, structure 0.76, motion 0.90, tail drift in the last 9 frames; crops: the can, not a cup
model_run <draft complete model> {draftVideo: <draft asset id>} -> 1080p final, same motion
alter_finish.py take.mp4 final.mov --out swap.mp4 --trim-tail 9 --compare
```

The same swap with only the flat product sheet as `@image1` kept the cup's tapered shape at the lips and printed the design onto it like a sticker; with the target frame he holds a slim can with the light running down it, from the first frame to the last.

## Common mistakes

- Handing the edit a flat product render for a swap: it reads as pasted on, and the old object's shape can survive. Build the target frame.
- Using one mode's opening in another: a swap's "keep absolutely everything (the light, the set)" inside a restyle makes the model return the source unchanged. The builder refuses it.
- A restyle prompt that only describes the people: they get drawn and the sky, sea and buildings stay a photo. Name the background as art; if it still stays a photo, add a redrawn first frame as the target.
- Leaving `generateAudio` on: the model invents a track (murmured voices included) and the lips and steps stop matching. Put the source sound back, or lay an ambience made for the new place.
- Two changes in one run. Chain runs instead.
- Judging a draft from its thumbnail. Open the 100% crops; models add real-brand marks to sportswear and shoes even under "no logos", invent props they cannot see, and add fingers.
- Showing the last frames untrimmed: when the source ends on a fast move, the edit's last third of a second leaves the source. Trim what `alter_check.py` reports as tail drift, on every version of a set, so they loop together.
- Finalising and shipping without a second check: finalising a restyle can pull detail back toward the photo.
- Recasting from a bare face crop: the model may only age the original face, and the reference's clothes leak in. Use a target frame of this shot with the new person in the source's clothes; trim the first frames if they open on the reference's expression.
- Rewording a prompt to get past a content or IP filter (a 422 or a policy rejection): do not. Change the input or ask the user.
- Speeding up or freezing people to fit a slot. Retime only camera-only moves, at exact integer speeds.
- Rendering text, prices or logos into references. Composite text in post.
