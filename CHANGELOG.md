# Changelog

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
