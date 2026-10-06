package com.mirmedialabs.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;

/** Media Lab server addresses + its own access key (unrelated to MirOS). */
final class Prefs {
    static final String DEFAULT_LAN = "";
    static final String DEFAULT_REMOTE = "";
    static final int DEFAULT_PORT = 5400;
    private static final String NAME = "mml_prefs";

    static SharedPreferences sp(Context c) {
        return c.getApplicationContext().getSharedPreferences(NAME, Context.MODE_PRIVATE);
    }

    // stored values are normalized on read too, so an address saved by an older build ("192.168.0.50:5400",
    // no scheme → MalformedURLException) heals itself
    static String lanUrl(Context c) { return normalize(sp(c).getString("lan_url", DEFAULT_LAN)); }
    static String remoteUrl(Context c) { return normalize(sp(c).getString("remote_url", DEFAULT_REMOTE)); }
    static String key(Context c) { return sp(c).getString("access_key", ""); }
    /** This install's device id — a person's key works on ONE device (the lab locks it to the first one). */
    static String deviceId(Context c) {
        String d = sp(c).getString("device_id", "");
        if (d.isEmpty()) {
            d = "a" + java.util.UUID.randomUUID().toString().replace("-", "");
            sp(c).edit().putString("device_id", d).apply();
        }
        return d;
    }
    static boolean configured(Context c) { return !key(c).isEmpty() && !(lanUrl(c).isEmpty() && remoteUrl(c).isEmpty()); }

    static void save(Context c, String lan, String remote, String key) {
        sp(c).edit().putString("lan_url", normalize(lan)).putString("remote_url", normalize(remote))
                .putString("access_key", key == null ? "" : key.trim()).apply();
        active = null;
    }

    /** Route in use: home Wi-Fi address when it answers, else the remote one. */
    static volatile String active = null;
    static String activeUrl(Context c) {
        String a = active;
        if (a != null && !a.isEmpty()) return a;
        String lan = lanUrl(c);
        return lan.isEmpty() ? remoteUrl(c) : lan;
    }
    static boolean onLan(Context c) { return active != null && active.equals(lanUrl(c)); }

    /**
     * Whatever the person typed or pasted → "scheme://host[:port]", or "" when it can't be an address.
     * "192.168.0.50" → http://192.168.0.50:5400 · "lab.duckdns.org:8080" → http://lab.duckdns.org:8080 ·
     * "https://lab.example.com/?key=…" → https://lab.example.com (paths / queries dropped).
     * A bare host gets the Media Lab port; an explicit http(s):// keeps the scheme's default port.
     */
    static String normalize(String raw) {
        String u = raw == null ? "" : raw.trim().replaceAll("\\s+", "");
        if (u.isEmpty()) return "";
        u = u.replaceFirst("(?i)^(https?)//", "$1://").replaceFirst("(?i)^(https?):/(?!/)", "$1://");
        boolean typedScheme = u.matches("(?i)^[a-z][a-z0-9+.-]*://.*");
        if (!typedScheme) u = "http://" + u;
        Uri p;
        try { p = Uri.parse(u); } catch (Exception e) { return ""; }
        String scheme = p.getScheme() == null ? "http" : p.getScheme().toLowerCase();
        if (!scheme.equals("http") && !scheme.equals("https")) return "";
        String host = p.getHost();
        if (host == null) return "";
        host = host.toLowerCase();
        boolean v6 = host.contains(":");
        if (v6 && !host.startsWith("[")) host = "[" + host + "]";
        if (!v6 && !host.matches("[a-z0-9_]([a-z0-9_-]*[a-z0-9])?(\\.[a-z0-9_]([a-z0-9_-]*[a-z0-9])?)*")) return "";
        int port = p.getPort();
        if (port < 0 && !typedScheme) port = DEFAULT_PORT;
        if (port > 65535) return "";
        return scheme + "://" + host + (port > 0 ? ":" + port : "");
    }

    static String str(Context c, String k, String def) { return sp(c).getString(k, def); }
    static void put(Context c, String k, String v) { sp(c).edit().putString(k, v).apply(); }
    static long lng(Context c, String k, long def) { return sp(c).getLong(k, def); }
    static void put(Context c, String k, long v) { sp(c).edit().putLong(k, v).apply(); }
    static boolean bool(Context c, String k, boolean def) { return sp(c).getBoolean(k, def); }
    static void put(Context c, String k, boolean v) { sp(c).edit().putBoolean(k, v).apply(); }
}
