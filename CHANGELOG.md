# Changelog

## Unreleased - first public release
- Open-sourced under GPL-3.0 by MirCorp.
- New **About** menu with creator info, **Report a bug** and **Send feedback** (email), Patreon and source links. Available on the web/PC UI and the Android app.
- Security:
  - lockout after 10 wrong access keys
  - security headers on every response
  - Android trusts only system CAs, and release builds are signed and R8-shrunk
- Personal machine settings moved to `data/local.json`. The LAN address is now auto-detected.
