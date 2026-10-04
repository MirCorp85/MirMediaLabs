package com.mirmedialabs.app;

import android.content.Context;
import android.content.SharedPreferences;

/** Media Lab server addresses + its own access key (unrelated to MirOS). */
final class Prefs {
    static final String DEFAULT_LAN = "";
    static final String DEFAULT_REMOTE = "";
    private static final String NAME = "mml_prefs";

    static SharedPreferences sp(Context c) {
        return c.getApplicationContext().getSharedPreferences(NAME, Context.MODE_PRIVATE);
    }

    static String lanUrl(Context c) { return trim(sp(c).getString("lan_url", DEFAULT_LAN)); }
    static String remoteUrl(Context c) { return trim(sp(c).getString("remote_url", DEFAULT_REMOTE)); }
    static String key(Context c) { return sp(c).getString("access_key", ""); }
    static boolean configured(Context c) { return !key(c).isEmpty(); }

    static void save(Context c, String lan, String remote, String key) {
        sp(c).edit().putString("lan_url", trim(lan)).putString("remote_url", trim(remote)).putString("access_key", key.trim()).apply();
        active = null;
    }

    /** Route in use: home Wi-Fi address when it answers, else the remote one. */
    static volatile String active = null;
    static String activeUrl(Context c) { return active != null ? active : lanUrl(c); }
    static boolean onLan(Context c) { return active != null && active.equals(lanUrl(c)); }

    static String trim(String u) {
        u = u == null ? "" : u.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        return u;
    }

    static String str(Context c, String k, String def) { return sp(c).getString(k, def); }
    static void put(Context c, String k, String v) { sp(c).edit().putString(k, v).apply(); }
    static long lng(Context c, String k, long def) { return sp(c).getLong(k, def); }
    static void put(Context c, String k, long v) { sp(c).edit().putLong(k, v).apply(); }
}
