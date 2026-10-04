package com.mirmedialabs.app;

import android.net.Uri;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * An invite from the lab host (Host Control → Invite / QR), pasted or scanned:
 *   http://192.168.0.50:5400/?key=mml-…&away=http%3A%2F%2Fmy-lab.duckdns.org%3A5400
 *   mirmedialabs://join?url=…&key=…&away=…
 *   or just the key (mml-…).
 * Surrounding chat text is fine — the first link / key in it is used.
 */
final class Invite {
    String lan = "", away = "", key = "";

    boolean complete() { return !key.isEmpty() && !(lan.isEmpty() && away.isEmpty()); }

    private static final Pattern LINK = Pattern.compile("(?i)(https?://|mirmedialabs://)[^\\s\"'<>]+");
    private static final Pattern KEY = Pattern.compile("mml-[A-Za-z0-9_-]{8,}");

    static Invite parse(String text) {
        if (text == null) return null;
        String t = text.trim();
        if (t.isEmpty()) return null;
        Invite inv = new Invite();
        Matcher m = LINK.matcher(t);
        if (m.find()) {
            String link = m.group().replaceAll("[).,;!]+$", "");
            Uri u;
            try { u = Uri.parse(link); } catch (Exception e) { return null; }
            String base, away;
            if ("mirmedialabs".equalsIgnoreCase(u.getScheme())) {
                base = Prefs.normalize(q(u, "url"));
                away = Prefs.normalize(q(u, "away"));
            } else {
                base = Prefs.normalize(link);
                away = Prefs.normalize(q(u, "away"));
            }
            inv.key = q(u, "key").trim();
            if (!base.isEmpty()) {
                if (isLocal(base)) inv.lan = base;
                else if (away.isEmpty()) away = base;     // a public link is the away address
                else inv.lan = base;
            }
            inv.away = away.equals(inv.lan) ? "" : away;
        }
        if (inv.key.isEmpty()) {
            Matcher k = KEY.matcher(t);
            if (k.find()) inv.key = k.group();
        }
        return inv.key.isEmpty() && inv.lan.isEmpty() && inv.away.isEmpty() ? null : inv;
    }

    private static String q(Uri u, String name) {
        try { String v = u.getQueryParameter(name); return v == null ? "" : v; } catch (Exception e) { return ""; }
    }

    /** Home-network address (only reachable on the same Wi-Fi). */
    static boolean isLocal(String url) {
        String h;
        try { h = Uri.parse(url).getHost(); } catch (Exception e) { return false; }
        if (h == null) return false;
        h = h.toLowerCase();
        if (h.endsWith(".local") || h.endsWith(".lan") || h.endsWith(".home") || h.endsWith(".internal") || !h.contains(".")) return true;
        if (h.startsWith("10.") || h.startsWith("192.168.") || h.startsWith("169.254.") || h.equals("127.0.0.1")) return true;
        if (h.matches("172\\.(1[6-9]|2\\d|3[01])\\..*")) return true;
        return h.startsWith("[fd") || h.startsWith("[fe80");
    }
}
