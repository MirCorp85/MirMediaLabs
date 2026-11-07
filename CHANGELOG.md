# Changelog

## Unreleased - Cast, Motion fix, EXPLAINED and Rank Reel removed
- **Cast** (`/cast`, Tools → Cast, dock): character packs. Drop photos or describe someone and the lab draws a hero, back view and face close-up and puts them on ONE reference sheet. Type `@Name` in any lab prompt and the pack's sheet + locked description go with the request. "Use in CopyCat" opens CopyCat. Optional identity scores use InsightFace ArcFace (non-commercial) through a separate Python you set as `face_python` (or `MML_FACE_PYTHON`); without it packs still build.
- **Fix: Motion Studio and the Kinetic editor showed a black screen in the installed app.** The lab loaded these add-ons with a string import the compiler can't see, so v1.0.39's .exe was built without them and `/motion` returned 404 inside a black frame. Add-ons are now plain imports and the build fails if any add-on module is missing from the compiled app.
- **Removed:** MIR EXPLAINED and Rank Reel (panels, routes, server modules, research-engine setting, motion compositions). Motion Studio's own explainer format stays.
- **Android app:** Cast replaces MIR EXPLAINED and Rank reel in the Media Lab menu, the + menu and the tablet side column.

## PC setup v1.0.39 + Android app 2.38 - Studio, Kinetic, MIR EXPLAINED, Rank Reel, CopyCat, Design
- **Studio:** 100+ one-tap apps (relight, restyle, camera moves, talking photos, upscale, cutouts…) from the freefield catalogue plus the OpenField pack, run on your own ComfyUI. Missing models download from inside each app; gated ones use your Hugging Face token (Settings → AI).
- **Motion Studio wizard:** one sentence → a narrated Diorama / Signature film, with the shared **Motion Library** (places, characters, objects, animals) at `/motion/library`.
- **Kinetic editor** (`/motion/editor`): beat-synced kinetic type with film effects, rendered locally in headless Chrome.
- **MIR EXPLAINED:** topic → research → script → assets → render → posts. Research runs on your own optional research engine (any OpenAI-compatible URL + key you run, e.g. a Kaggle notebook), else the cloud brain, else the local engine. Nothing is bundled.
- **Rank Reel:** top-N countdown Shorts built from real clips, each checked by the vision brain before use.
- **CopyCat:** swap the people or things in any video (Openjutsu, MIT), installed and built by Setup; Fix faces is not included.
- **Design:** ComfyArt layered canvas inside the lab, with live progress.
- **Setup:** ComfyUI 0.42.5; new optional model sets FLUX Klein, LTX-2.5 (both gated: paste your Hugging Face token) and Qwen-Image-Layered + BiRefNet; Studio / Design / CopyCat node packs; the vector art library is built at install.
- **Settings → AI:** Hugging Face token and research engine fields (secrets are never shown again).
- Every add-on engine path is configurable (`mml_config.json` / Settings: `freefield_dir`, `copycat_dir`, `kinetic_dir`, `motion_dir`, `sfx_dir`, `expressive_python`, export folders).
- **Fix:** the first v1.0.39 Setup.exe could close at once on some PCs (a DLL was left out of the build). The build now refuses to finish if any DLL is missing and test-starts the setup before publishing.
- **Android app 2.38:** Studio, Kinetic editor, MIR EXPLAINED, Rank reel, CopyCat and Design in the Media Lab menu, the + menu and the tablet side column.

## PC setup v1.0.38 + Android app 2.37 - new engines, ALTER, library hub
- **New models in the picker:** FLUX-3 Klein (fast images and edits), LTX-2.5 (video with sound, talking pictures) and Qwen-Image-Layered (split a picture into transparent layers). They appear as soon as their weights are in ComfyUI's models folder; without them the lab works as before.
- **Qwen-Image Turbo:** an 8-step quick-draft model next to Base (Image settings → Model). Falls back to Base when the Turbo weights are missing.
- **EasyCache** speed boost for long video renders (Video settings → Speed boost).
- **ALTER pipelines:** change one thing in your clip and keep the performance. *Swap One Thing* (a product, prop or outfit), *Recast* (someone else performs it), *New Place* and *Restyle* (anime, 3D, clay, comic…). Every result is checked against your clip, the drifted tail is trimmed, your clip's own sound goes back on, and you get a side-by-side plus QA crops. Scripts from the MIT `scenario-alter` kit.
- **Library hub** (desktop): the Library tab opens a full page with categories, live stats and charts, search, sort and grid/list views. While Motion Studio is open the library pins beside it: drag or click a tile to add it.
- **Social / VIRAL-Ω:** tabs grouped into Publish · Grow · Measure · Setup; YouTube sign-in expiry is detected and asks you to reconnect; 16:9 YouTube uploads go up as 1440p (sharper playback from day one); posts can carry the video's real story so titles and descriptions describe the content; TikTok inbox uploads and per-post TikTok choices on Repost; A/B YouTube thumbnails (source installs).
- **Hooks and captions are now opt-in** in VIRAL-Ω (they used to run on every draft). Editing a hook re-burns the on-screen hook text.
- **Downloader:** Instagram share links, carousels (picks the video slide) and optional cookies for private posts; finds Deno installed by winget.
- **Motion engine:** more patient with a busy render daemon instead of failing.
- Touch: pinch to zoom the editor timeline; long-press deletes markers and keyframes in Motion Studio.
- **Android app 2.37:** FLUX-3 Klein, LTX-2.5 and Qwen layers in the model picker and job cards.

## Unreleased - VIRAL-Ω research desk + setup from source
- **Setup from source:** clone the repo and run `Setup.bat` (Windows) or `./setup.sh` (Linux, beta). The wizard checks the PC, suggests models for your GPU, reuses ComfyUI models you already have, and installs the app's Python, PyTorch, a headless ComfyUI, the models, MirAI (optional), the voice and the motion engine, all inside the clone. `Setup.bat --yes` installs unattended. App packages are listed in `requirements.txt`.
- **Social → Trends:** a live trend radar (YouTube niche outliers and trending, Google Trends, Google News, and Reddit with a free app key), scored for your account, with ready-to-run lab prompts.
- **Social → Hook Lab:** write-then-judge hooks and a library of your own hooks ranked by results.
- **Social → Remix:** study a viral video and make an original version of it in the lab, judged against the source, with automatic retries.
- **Social → Planner:** ideas, drafts, scheduled and live posts on one board.
- Burned-in on-screen hooks and word captions (motion engine), with the original video kept. Weekly lessons from your own numbers (hold rate, shares, saves, YouTube retention).
- **Send to VIRAL-Ω** from the library: a dialog that formats the video for each platform and writes the full post package, ready to copy, rewrite or approve.
- **Repost** a published video to other platforms, and **Refresh all stats** in one click.
- Library: smaller icon-only REF / VIRAL-Ω buttons on thumbnails, and the player centres videos correctly.
- Fallback, vision and stand-in engines are now settings (`fallback_engine`, `vision_pref`, `engine_twins` in `mml_config.json`), with defaults that work on a fresh install.

## v1.0.7 - Windows setup + LoRA fixes
- **Setup wizard:** the language-model choice is now **MUSE · Llama 3.1 8B** (Qwen 3.5 removed). MUSE is the lab's general-purpose model for conversation, prompt building and the Auto-mode model picker. It never renders anything. Upgrades from Qwen 3.5 installs switch to MUSE.
- The prompt engine defaults to Llama 3.1 8B. Pictures are only sent to engines that can see them, instead of failing on text-only models.
- **LoRA fixes:**
  - LoRAs from the library's music section are ACE-Step LoRAs. They were also sent to MiniMax Music 3 (songs), which can't load them, so they "attached" and did nothing.
  - LoRAs made for another version of a model (for example ACE-Step v1 LoRAs on ACE-Step 1.5) load no layers in ComfyUI. The lab now checks each LoRA's layers against your installed model, marks mismatches as "won't load" in the LoRA library, and skips them.
  - Every result card shows **which LoRA was applied** and which ones weren't used, and why. Nothing is dropped silently anymore.
  - Auto mode: a song request switches to the music engine when your selected LoRA only fits there.
  - Pipelines pick LoRAs per step. Before, the first step's LoRA was also chained into later steps that use a different engine.

## Android app 2.1 (includes 2.0)
- **New sign-in**: scan the host's invite QR code (camera, or a photo or screenshot of it), paste the invite link, or let the app pick it up from the clipboard. Typing the address and key by hand is still available.
- **Fixed "offline - MalformedURLException"** when an address was typed without `http://`. Addresses are cleaned up automatically (`192.168.0.50` becomes `http://192.168.0.50:5400`), and addresses saved by older versions repair themselves.
- **Connection doctor**: each address is tested separately, with clear reasons and fixes (refused, timed out, unknown name, not a Media Lab, key rejected, locked out, remote access paused).
- **Away-from-home guide**: router port forwarding, firewall, dynamic DNS, a mobile-data test, and the CGNAT/VPN fallback.
- **Push notifications from your own lab** (no Firebase): render finished or failed (with a preview), host messages, and app updates. Live progress shows while a render runs. Optional *Instant delivery*. Server: `GET /api/events` long-poll feed (`server/events.py`).
- **Signed self-updates from GitHub Releases** and from your own lab, using the same Ed25519 key as the PC edition. The app checks the SHA-256, size, version and signing certificate, and resumes interrupted downloads. Android 12+ installs later updates without extra taps.
- Crash reports are saved on the phone and offered by email on the next launch.
- Readable network errors everywhere, and the app re-checks the route right away when you switch between Wi-Fi and mobile data.
- **Host Control > Phones** (desktop): set the away-from-home address that invites and QR codes carry, and push a notice to every signed-in phone.

## Unreleased - first public release
- Open-sourced under GPL-3.0 by MirCorp.
- New **About** menu with creator info, **Report a bug** and **Send feedback** (email), Patreon and source links. Available on the web/PC UI and the Android app.
- Security:
  - lockout after 10 wrong access keys
  - security headers on every response
  - Android trusts only system CAs, and release builds are signed and R8-shrunk
- Personal machine settings moved to `data/local.json`. The LAN address is now auto-detected.
