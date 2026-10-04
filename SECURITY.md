# Security Policy

## Reporting a vulnerability
**Please do not open a public GitHub issue for security problems.**

Email **mirmedialabs@gmail.com** with the subject `[MML SECURITY]` and include:
- the version (About menu) and platform (Windows / Android)
- steps to reproduce, and what an attacker could do

You'll get a reply within 7 days. Please allow up to 90 days for a fix before you disclose publicly. Reporters are credited in the changelog unless they ask not to be.

## Supported versions
Only the latest release receives security fixes.

## Security model, in brief
- The server listens on port 5400. Every request from another device needs a per-user access key (random, 144-bit). Requests from the PC itself (loopback) are treated as the owner.
- After 10 wrong keys, an address is locked out for 15 minutes.
- File access is sandboxed to the app's own `data/`, `updates/` and static folders.
- PC updates are verified against an **Ed25519 signature** and a SHA-256 hash before they install. Unsigned or altered manifests, and downgrades, are refused.
- Android releases are signed with the MirCorp release key. Only install APKs from the official GitHub Releases page.
- **Do not expose port 5400 directly to the internet** without HTTPS (for example a reverse proxy or a VPN such as Tailscale). If you run it behind a reverse proxy *on the same PC*, every request looks like loopback (owner), so require authentication at the proxy.
