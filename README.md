<p align="center"><img src="MirMediaLabs-icon-1024.png" width="140" alt="MIR MEDIA LABS"></p>

<h1 align="center">MIR MEDIA LABS</h1>
<p align="center"><b>An independent, open-source AI agent front end for generative models.</b><br>
Describe what you want in plain language. The agent picks the model, writes the prompt, sets the parameters and renders it on <b>your own GPU</b>.<br>
Video, songs, music, images and writing, controlled from your PC, phone or Android TV.</p>

<p align="center">
<a href="../../releases/latest"><img src="https://img.shields.io/github/v/release/MirCorp85/MirMediaLabs?label=download&color=ff5a1f" alt="Download"></a>
<a href="https://www.patreon.com/MirCorp"><img src="https://img.shields.io/badge/Support-Patreon-f96854?logo=patreon&logoColor=white" alt="Patreon"></a>
<img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="GPL-3.0">
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20Android%20%7C%20Android%20TV-informational" alt="platforms">
<img src="https://img.shields.io/badge/runs-100%25%20local-5ee08a" alt="100% local">
</p>

---

## Why MIR MEDIA LABS
- **One agent, many models.** You ask for an image, video, song, beat or story. MML routes it to the right engine, so you never deal with node graphs or model-specific settings.
- **Prompts written for you.** A local LLM, the *Prompt director*, rewrites your idea in each model's official prompt style before rendering.
- **Fully local and private.** Everything renders on your machine. No cloud, no subscriptions, no per-render credits, no data collection.
- **Model-agnostic by design.** Skills, pipelines and commands name a *role* (image, video, song, music, writing), never a specific model. When a better model comes out, it slots in behind the same front end.
- **Use it from anywhere in the house.** The PC does the work. Your phone and TV are remotes with the full feature set.

## What it can make
| Role | Engine today | What you get |
|---|---|---|
| **Video** | MiniMax H3 | Video **with native audio**: text-to-video, image-to-video (*animate:*), first + last frame, reference-to-video (identity and motion refs), 4–15 s, vertical, square or widescreen, style presets, an attached soundtrack muxed in |
| **Song** | MiniMax Music 3.0 | Full vocal songs **up to 5 minutes**, from your lyrics or auto-written ones, mood from an image or video reference |
| **Image** | Qwen-Image 2.1 | Text-to-image, **multi-picture edit (up to 10 inputs)**, background removal and cutouts, HD/HQ modes |
| **Music** | ACE-Step 1.5 XL | Fast tracks and beats, **remix, cover and voice swap**, plus BPM, key and strength control |
| **Writing** | MUSE (local Llama 3.1) | MML's writer: chat, stories, lyrics, video scripts, poems, ad copy and prompts, written to feed straight into the other models |

## Features

### Agent console
- A chat-style **Lab chat** where every request becomes a job with a live log, stage and progress
- **Slash commands**: `/image`, `/video`, `/song`, `/music`, `/write`, `/chat`, `/skill`, `/pipe`, `/help` (with a built-in command book)
- **Inline prompt flags**: e.g. `--8s --vertical --hd --seed 42`, `--90s --instrumental`, `--bpm 120 'A minor'`
- **References** for every model: attach images, video, audio or text (paste lyrics or scripts), or share them from your phone's other apps
- **Per-model parameters** (⚙): mode, aspect, resolution, steps, sampler, scheduler, CFG, seed, audio options and more, saved per model
- One-at-a-time **GPU queue** that persists across restarts, with **cancel** and **re-run**

### Skills and pipelines
- **21 one-tap skills** with tuned prompts and settings:
  - **Image:** Product Shot, Portrait Pro, Thumbnail, Logo Mark, Restyle Photo, Cutout
  - **Video:** Cinematic Shot, Animate Photo, Social Reel, Product Spin
  - **Song and music:** Full Song, Instrumental Beat, Jingle, Lo-fi Loop
  - **Writing:** Short Story, Song Lyrics, Video Script, Poem, Ad Copy, Creative Writing, Prompt Writer
- **Multi-model pipelines** that chain renders in one request, with each step's output feeding the next:
  - **Poster → Motion**: design a key image, then animate it
  - **Product Ad**: studio packshot to a vertical 9:16 ad clip
  - **Character Clip**: a portrait that then moves and speaks
  - **Music Video**: song to cover art to a video scored with that song
  - **Album Pack**: a full song plus matching cover art

### LoRA browser
- Browse community LoRAs with sample previews, then **install and apply in one click**
- Optional Civitai key support, and install/remove management

### Library
- Every output is saved with its prompt, model and settings
- Image, video and audio filters, thumbnails, a full-screen viewer, download, **"use as reference"**, and trash

### Desktop app (Windows)
- Native compiled app (`MirMediaLabs.exe`) with its **own taskbar identity**, so you can pin it like any app
- **Live PC performance card**: CPU, RAM, GPU, VRAM, temperature and power, with plain-language bottleneck hints while rendering ("VRAM full", "CPU-bound", "GPU at full speed")
- **Guided installer**:
  - checks GPU, driver, RAM, page file, disk and network
  - installs a private Python/PyTorch runtime, the ComfyUI render engine and only the models you pick
  - optionally installs Ollama for the prompt engine
  - downloads resume, and re-running it offers Modify and Repair
- **Signed auto-updates**: Ed25519-verified manifests, with SHA-256 checks and downgrade protection

### Android app (phone and TV)
- **One APK for phones and Android TV**, with a lightweight native app (plain Java, no frameworks)
- Uses your home Wi-Fi when available and falls back to a remote address
- **Share to MML** from any app (photos, clips, songs, text) to use as references
- Full console, skills, pipelines, LoRAs, library and viewer
- 5 themes and 10 original **MIR FONTS**, synced with the desktop

### Multi-user and security
- **Per-person access keys**: invite family or a team. Each user sees only their own jobs, and the owner sees everything.
- Lockout after repeated wrong keys, security headers, and a sandboxed file system (the app only touches its own folders)
- Isolation audit built in (`/api/isolation`)
- Owner-only machine stats: the performance card is only served to the PC itself

### Design
- Custom **MIR ICONS** and **MIR FONTS** across desktop, web, phone and TV
- An animated studio mascot that shows lab status, plus themes from dark to paper-light

## Download
Get the latest version from the [**Releases page**](../../releases/latest):
- **`MirMediaLabs-Setup.exe`**: the Windows host (installer and app)
- **`MirMediaLabs.apk`**: the Android phone and TV remote, signed by MirCorp
- **`SHA256SUMS.txt`**: checksums. Verify with `certutil -hashfile MirMediaLabs-Setup.exe SHA256`.

Only download from this repository. Windows SmartScreen may warn about the unsigned installer: click **More info > Run anyway**.

## Requirements
- **PC:** Windows 10/11 with an NVIDIA GPU. The setup wizard checks your GPU, RAM and disk space before installing anything.
- **Phone/TV:** Android 7.0 or later, on the same network as the PC (or via your own remote address)

## Quick start
1. Run **`MirMediaLabs-Setup.exe`**, pick your models, and let it install.
2. Open **MIR MEDIA LABS** from the desktop or Start menu, then pin it to the taskbar if you like.
3. Type an idea, e.g. `/video a neon city at night, slow drone shot --vertical`, or tap a **Skill**.
4. **Phone/TV:** install the APK, then enter the PC address from **Settings** and your access key.

## Run from source
```
cd server
pip install flask requests
python medialab.py        # http://127.0.0.1:5400
```
Rendering needs a local [ComfyUI](https://github.com/comfyanonymous/ComfyUI) with the models installed. The prompt engine and MUSE need [Ollama](https://ollama.com).
Android: open `app/` in Android Studio, or run `powershell -File build_apk.ps1`.

## Support development
MIR MEDIA LABS is free and always will be. If it's useful to you, please support it on **[Patreon](https://www.patreon.com/MirCorp)**. Your support funds new models, features and testing hardware. You can also use the **Support** button inside the app.

## Feedback and bugs
- In the app: **About > Report a bug** or **Send feedback**
- Email: **mirmedialabs@gmail.com**
- Or [open an issue](../../issues/new/choose). For security issues, see [SECURITY.md](SECURITY.md).

## License and ownership
Copyright (C) 2026 **MirCorp**. Licensed under the [GNU GPL v3.0](LICENSE): you may use, study, modify and share the code, but modified versions you distribute must also be open source under GPL-3.0.

"MirCorp" and "MIR MEDIA LABS" are trademarks of MirCorp. See [TRADEMARK.md](TRADEMARK.md), [NOTICE](NOTICE) and [PRIVACY.md](PRIVACY.md).

AI models (MiniMax, Qwen, ACE-Step, Llama, ComfyUI) are third-party works, downloaded separately and subject to their own licenses.
