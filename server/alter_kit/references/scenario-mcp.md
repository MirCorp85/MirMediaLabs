# Running ALTER on the Scenario MCP

## Connect and choose where to work

1. `teams_list` (free). If several teams or projects come back, ask the user which to use, and pass `team_id` and
   `project_id` on every call.
2. Find each model by name with `search` (`{"target": "models", "public": true, "query": "..."}`) and skip entries
   tagged Deprecated. Read `model_schema_get` once per session; parameters change.
   - The edit: "Seedance 2.5" (the plain entry; edit mode is inferred from a reference video plus the prompt).
   - Finalising a draft: "Seedance 2.5 Draft Complete" (one input, `draftVideo`).
   - Target frames: "Gemini 3.0 Pro" (image editing, up to 14 reference images).
   - Ambience: "ElevenLabs Sound Effects".
3. `recommend` with `video2video` also ranks other edit models. The presets keep their structure on them, but their
   wording was tuned on the route above; check the first run with `alter_check.py`.

## Upload

`upload_asset` with `file_name`, `content_type`, `kind` and `file_size` (never base64 for video). The reply lists one
presigned URL per part and the part size. Split the file at that size (`split -b <part_size> file part_`), PUT each
part to its own URL with the raw bytes and no extra headers (`curl -fS -X PUT -T part_aa '<url>'`), then
`upload_asset_complete` with the `upload_id`. An 11.5 MB prepared 8-second 1080p clip took two parts.

Upload the prepared clip (`alter_prep.py`), not the camera original: SDR, upright, constant frame rate, H.264.

## Price, run, wait

- `model_run` with `dry_run: true` returns the price without running. Tell the user each step and the total.
- Draft (`draft: true`) every edit: a cheap 480p preview that stays valid for 7 days and can be finalised to 1080p
  with the same motion, framing and sound. On the measured route a draft cost about a fifth of a direct 1080p edit,
  and a draft plus its finalising cost about 2% more than the direct edit: a kept take costs a little more, every
  rejected take far less.
- Finalising cannot be dry-run until its draft exists (the dry run answers that the draft cannot be finalised).
  Quote it up front with a dry run of the same parameters at `resolution: "1080p"` without `draft`.
- Reference videos may be 2 to 30 seconds in the schema; edit runs under 4 seconds were not tested, so the scripts
  ask for at least 4.
- Run with `wait: false`, collect job ids, then `jobs_wait` (re-call with `pending_job_ids` until done). Never launch a
  duplicate while one is pending.
- At most five jobs at a time. About 28 edit jobs in 30 minutes once triggered a multi-hour cooldown.
- A job that sits at the same percentage for 15 minutes is usually dead: relaunch once, keep whichever finishes.
- `duration: -1` in edit mode: the output follows the source (every output in the 21 Oct run had the source's exact
  193 frames).

## Download

`asset_download` returns a signed URL. Save it with `curl -sL -o file "<url>"`. Finalised videos come back as 1080p
MOV (10-bit); `alter_finish.py` conforms them to the source and encodes H.264.

## Filters and teams

- A 422 or a policy rejection names a character, a brand or a real person (logos on clothes in the input video
  count). Do not reword the prompt to slip past it. Change the input or ask the user.
- Assets belong to a team: another team's project cannot read them (403). Download and upload again if the user
  moves work between teams.
- A plan limit error stops every run under that login. Stop paid work, list what is missing, and let the user decide.
