import type { NextConfig } from "next";

// Next reads this config before it starts telemetry, so this turns telemetry off for every npm script on any OS
// (a `NEXT_TELEMETRY_DISABLED=1 next ...` script prefix would fail in Windows cmd).
process.env.NEXT_TELEMETRY_DISABLED ??= "1";

// No full CSP: Next's inline scripts and the page's blob: video previews would need one written around them.
const securityHeaders = [
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'self'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  basePath: "/copycat",  // MIR MEDIA LABS: served at :5400/copycat
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
