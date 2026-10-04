<p align="center"><img src="MirMediaLabs-icon-1024.png" width="140" alt="MIR MEDIA LABS"></p>

<h1 align="center">MIR MEDIA LABS</h1>
<p align="center"><b>A free, open-source AI media studio that runs on your own GPU.</b><br>
Video, music and images, made locally and privately, controlled from your PC, phone or Android TV.</p>

<p align="center">
<a href="https://www.patreon.com/MirCorp"><img src="https://img.shields.io/badge/Support-Patreon-f96854?logo=patreon&logoColor=white" alt="Patreon"></a>
<img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="GPL-3.0">
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20Android-informational" alt="platforms">
</p>

## What it does
| Model | Makes |
|---|---|
| **MiniMax H3** | video with native audio: text-to-video, image-to-video, first and last frame, reference-to-video |
| **MiniMax Music 3.0** | full songs with vocals, up to 5 minutes |
| **Qwen-Image** | text-to-image, multi-picture edits, background removal |
| **ACE-Step 1.5 XL** | fast tracks, remix, cover, voice swap |

Plus a shared library, references (image, video, audio and text), LoRA browsing, skills and pipelines, per-user access keys, and themes.

## Download
Grab the latest release from the [**Releases page**](../../releases):
- **`MirMediaLabs-Setup.exe`** is the Windows host. It checks your GPU, then installs the app, the render engine and the models you choose.
- **`MirMediaLabs.apk`** is the Android phone and TV remote. It connects to your PC.

Each release lists SHA-256 checksums. Only download from this repository.

## Requirements
- Windows 10/11 with an NVIDIA GPU. The setup wizard checks your GPU, RAM and disk space before it installs anything.
- Android 7.0+ for the app

## Quick start
1. Run `MirMediaLabs-Setup.exe` and follow the wizard.
2. Open **MIR MEDIA LABS** from the desktop.
3. On your phone, install the APK and enter the PC address shown in **Settings**, plus your access key.

## Run from source
```
cd server
pip install flask requests
python medialab.py        # http://127.0.0.1:5400
```
Android: open `app/` in Android Studio, or run `powershell -File build_apk.ps1`.

## Support development
MIR MEDIA LABS is free. If it's useful to you, please consider supporting it on **[Patreon](https://www.patreon.com/MirCorp)**. It funds new models, features and testing hardware.

## Feedback and bugs
- In the app: **About > Report a bug** or **Send feedback**
- Email: **mirmedialabs@gmail.com**
- Or [open an issue](../../issues/new/choose)

## License and ownership
Copyright (C) 2026 **MirCorp**. Licensed under the [GNU GPL v3.0](LICENSE): you may use, study, modify and share the code, but modified versions you distribute must also be open source under GPL-3.0.

"MirCorp" and "MIR MEDIA LABS" are trademarks of MirCorp. See [TRADEMARK.md](TRADEMARK.md), [NOTICE](NOTICE), [PRIVACY.md](PRIVACY.md) and [SECURITY.md](SECURITY.md).

AI models are downloaded separately and are subject to their own licenses.
