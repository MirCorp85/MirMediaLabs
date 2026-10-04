package com.mirmedialabs.app;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.Base64;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/**
 * Self-update, same trust model as the PC edition (server/pcupdate.py):
 *   • manifest android.json is Ed25519-signed (android.json.sig) with the MirCorp update key; the public key
 *     below is compiled in, so a hijacked DNS name, router or mirror can't push anything
 *   • the APK must match the manifest's SHA-256 + size, be strictly newer, and carry the same signing
 *     certificate as this install (checked before Android's own installer is even asked)
 * Two channels, both signed:
 *   GitHub releases  https://github.com/<repo>/releases  (official, MirCorp-signed builds)
 *   your lab server  <server>/updates/android.json      (builds the lab owner publishes with build_apk.ps1)
 * The newest build whose certificate matches this install wins.
 */
final class Updater {
    static final String REPO = "MirCorp85/MirMediaLabs";
    static final String PUBKEY = "XqVTxYoM51Xyw1QTX06kbrG6hu+5qqLnNyYT54gJw8c=";
    static final String MANIFEST = "android.json";
    static final long EVERY = 12 * 3600_000L;

    static String releasesPage() { return "https://github.com/" + REPO + "/releases/latest"; }

    static long installedCode(Context c) {
        try {
            PackageInfo pi = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
        } catch (Exception e) { return 0; }
    }
    static String installedName(Context c) {
        try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName; } catch (Exception e) { return "?"; }
    }

    // ── signing certificates ─────────────────────────────────────────────
    @SuppressWarnings("deprecation")
    static Set<String> certs(PackageInfo pi) {
        Set<String> out = new HashSet<>();
        if (pi == null) return out;
        Signature[] sigs = null;
        if (Build.VERSION.SDK_INT >= 28 && pi.signingInfo != null) {
            SigningInfo si = pi.signingInfo;
            sigs = si.hasMultipleSigners() ? si.getApkContentsSigners() : si.getSigningCertificateHistory();
        }
        if (sigs == null) sigs = pi.signatures;
        if (sigs != null) for (Signature s : sigs) out.add(sha256(s.toByteArray()));
        return out;
    }
    @SuppressWarnings("deprecation")
    static Set<String> installedCerts(Context c) {
        try {
            int fl = Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
            return certs(c.getPackageManager().getPackageInfo(c.getPackageName(), fl));
        } catch (Exception e) { return new HashSet<>(); }
    }

    static String sha256(byte[] b) {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(b)); } catch (Exception e) { return ""; }
    }
    static String hex(byte[] d) {
        StringBuilder s = new StringBuilder();
        for (byte x : d) s.append(String.format("%02x", x));
        return s.toString();
    }

    // ── channels ─────────────────────────────────────────────────────────
    private static HttpURLConnection open(String url, boolean lab, Context c) throws Exception {
        HttpURLConnection h = (HttpURLConnection) new URL(url).openConnection();
        h.setConnectTimeout(8000);
        h.setReadTimeout(20000);
        h.setInstanceFollowRedirects(true);
        h.setRequestProperty("User-Agent", "MirMediaLabs-Android/" + installedName(c));
        if (lab) h.setRequestProperty("X-MML-Key", Prefs.key(c));
        else h.setRequestProperty("Accept", "application/vnd.github+json, application/octet-stream, */*");
        return h;
    }

    private static byte[] fetch(String url, boolean lab, Context c) throws Exception {
        HttpURLConnection h = open(url, lab, c);
        try {
            int code = h.getResponseCode();
            if (code != 200) throw new Exception("HTTP " + code);
            return Api.readAll(h.getInputStream());
        } finally { h.disconnect(); }
    }

    /** Signed manifest → JSONObject with "_apk" (absolute download URL) + "_src"; null if absent / invalid. */
    private static JSONObject verified(byte[] raw, byte[] sigB64, String apkBase, String src, Context c) throws Exception {
        byte[] sig = Base64.decode(new String(sigB64, StandardCharsets.US_ASCII).trim(), Base64.DEFAULT);
        if (!Ed25519.verify(Base64.decode(PUBKEY, Base64.DEFAULT), raw, sig))
            throw new Exception("signature check failed — update refused");
        JSONObject j = new JSONObject(new String(raw, StandardCharsets.UTF_8));
        if (!c.getPackageName().equals(j.optString("app", c.getPackageName()))) throw new Exception("manifest is for another app");
        String apk = j.optString("apk", "");
        if (apk.isEmpty() || j.optLong("versionCode") <= 0 || j.optString("sha256").length() != 64)
            throw new Exception("incomplete manifest");
        if (!apk.startsWith("https://")) {
            if (apk.contains("/") || apk.contains("\\") || !apk.toLowerCase().endsWith(".apk")) throw new Exception("bad file name in manifest");
            apk = apkBase + apk;
        }
        j.put("_apk", apk);
        j.put("_src", src);
        return j;
    }

    static JSONObject github(Context c) throws Exception {
        String base = "https://github.com/" + REPO + "/releases/latest/download/";
        try {
            byte[] raw = fetch(base + MANIFEST, false, c);
            byte[] sig = fetch(base + MANIFEST + ".sig", false, c);
            JSONObject j = new JSONObject(new String(raw, StandardCharsets.UTF_8));
            String tag = j.optString("tag", "");
            String apkBase = tag.isEmpty() ? base : "https://github.com/" + REPO + "/releases/download/" + tag + "/";
            return verified(raw, sig, apkBase, "GitHub", c);
        } catch (Exception latestMissing) {
            // the newest release may be PC-only: walk the release list for the newest one with an Android manifest
            JSONArray rels = new JSONArray(new String(fetch("https://api.github.com/repos/" + REPO + "/releases?per_page=12", false, c),
                    StandardCharsets.UTF_8));
            for (int i = 0; i < rels.length(); i++) {
                JSONObject r = rels.optJSONObject(i);
                if (r == null || r.optBoolean("draft") || r.optBoolean("prerelease")) continue;
                JSONArray as = r.optJSONArray("assets");
                String man = null, sig = null;
                for (int k = 0; as != null && k < as.length(); k++) {
                    JSONObject a = as.optJSONObject(k);
                    if (MANIFEST.equals(a.optString("name"))) man = a.optString("browser_download_url");
                    if ((MANIFEST + ".sig").equals(a.optString("name"))) sig = a.optString("browser_download_url");
                }
                if (man == null || sig == null) continue;
                String apkBase = man.substring(0, man.lastIndexOf('/') + 1);
                return verified(fetch(man, false, c), fetch(sig, false, c), apkBase, "GitHub", c);
            }
            return null;
        }
    }

    static JSONObject lab(Context c) throws Exception {
        String base = Prefs.activeUrl(c);
        if (base.isEmpty()) return null;
        base += "/updates/";
        byte[] raw;
        try { raw = fetch(base + MANIFEST, true, c); } catch (Exception e) { return null; }   // lab doesn't publish one
        return verified(raw, fetch(base + MANIFEST + ".sig", true, c), base, "your Media Lab", c);
    }

    /** Result of a check: the build to install (if any) + what went wrong where. */
    static final class Check {
        JSONObject best, foreign;
        String err = "";
        boolean upToDate() { return best == null; }
    }

    /** Blocking. Newest signed build per channel; keeps only builds this install can accept. */
    static Check run(Context c) {
        Check out = new Check();
        long have = installedCode(c);
        Set<String> mine = installedCerts(c);
        for (int ch = 0; ch < 2; ch++) {
            try {
                JSONObject j = ch == 0 ? github(c) : lab(c);
                if (j == null || j.optLong("versionCode") <= have) continue;
                if (j.optInt("minSdk", 1) > Build.VERSION.SDK_INT) continue;
                String cert = j.optString("cert", "").toLowerCase().replace(":", "");
                if (!cert.isEmpty() && !mine.isEmpty() && !mine.contains(cert)) {
                    if (out.foreign == null || j.optLong("versionCode") > out.foreign.optLong("versionCode")) out.foreign = j;
                    continue;
                }
                if (out.best == null || j.optLong("versionCode") > out.best.optLong("versionCode")) out.best = j;
            } catch (Exception e) {
                String why = e instanceof java.io.IOException || e.getMessage() == null ? Api.explain(e) : e.getMessage();
                out.err += (out.err.isEmpty() ? "" : "\n") + (ch == 0 ? "GitHub: " : "Lab server: ") + why;
            }
        }
        Prefs.put(c, "upd_last", System.currentTimeMillis());
        return out;
    }

    // ── UI ───────────────────────────────────────────────────────────────
    /** Launch check (at most every 12 h) or manual check from the menu / an update notification. */
    static void check(Activity a, boolean manual) {
        if (!manual && (!Prefs.bool(a, "upd_auto", true) || System.currentTimeMillis() - Prefs.lng(a, "upd_last", 0) < EVERY)) return;
        Sheet wait = null;
        if (manual) {
            wait = new Sheet(a, "Checking for updates", "refresh", Ui.pal());
            wait.note("Asking GitHub and your Media Lab for a newer signed build…");
            wait.show();
        }
        final Sheet w = wait;
        Api.POOL.execute(() -> {
            Check ck = run(a);
            Api.MAIN.post(() -> {
                if (w != null) w.dismiss();
                if (a.isFinishing()) return;
                if (ck.best != null) offer(a, ck.best);
                else if (ck.foreign != null && (manual || Prefs.lng(a, "upd_foreign", 0) != ck.foreign.optLong("versionCode"))) {
                    Prefs.put(a, "upd_foreign", ck.foreign.optLong("versionCode"));
                    foreign(a, ck.foreign);
                } else if (manual) {
                    Sheet sh = new Sheet(a, ck.err.isEmpty() ? "You're up to date" : "Couldn't check everywhere", ck.err.isEmpty() ? "check-circle" : "warn", Ui.pal());
                    sh.note("Installed: MIR MEDIA LABS v" + installedName(a) + " (" + installedCode(a) + ")\n\nChecked: GitHub releases"
                            + (Prefs.activeUrl(a).isEmpty() ? "" : " + your Media Lab") + (ck.err.isEmpty() ? "" : "\n\n" + ck.err));
                    sh.toggle("refresh", "Check automatically", "on launch and in the background, twice a day", Prefs.bool(a, "upd_auto", true),
                            on -> Prefs.put(a, "upd_auto", on));
                    sh.row("external", "Release notes", "github.com/" + REPO + "/releases", () -> view(a, "https://github.com/" + REPO + "/releases"));
                    sh.show();
                }
            });
        });
    }

    static void offer(Activity a, JSONObject j) {
        String notes = j.optString("notes", "");
        long size = j.optLong("size", 0);
        Sheet sh = new Sheet(a, "Update available", "download", Ui.pal());
        sh.note("MIR MEDIA LABS v" + j.optString("versionName") + (size > 0 ? "  ·  " + mb(size) : "") + "\nYou have v" + installedName(a)
                + "\n\nFrom " + j.optString("_src") + " · signature verified · same signing key as this app"
                + (notes.isEmpty() ? "" : "\n\nWhat's new\n" + notes));
        sh.button("download", "Update now", true, () -> download(a, j));
        sh.button("clock", "Later", false, () -> {});
        sh.show();
    }

    private static void foreign(Activity a, JSONObject j) {
        Sheet sh = new Sheet(a, "Official build available", "shield", Ui.pal());
        sh.note("v" + j.optString("versionName") + " is on " + j.optString("_src") + ", but this phone has a copy of the app signed with a "
                + "different key, so Android won't update it in place.\n\nSwitch once: uninstall this app, then install MirMediaLabs.apk from "
                + "the GitHub release. Your creations stay on your lab — just scan your invite again. After that, updates install by themselves.");
        sh.button("external", "Open the GitHub release", true, () -> view(a, releasesPage()));
        sh.button("clock", "Not now", false, () -> {});
        sh.show();
    }

    static void view(Activity a, String url) {
        try { a.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { }
    }

    static String mb(long b) { return String.format(java.util.Locale.US, "%.1f MB", b / 1048576.0); }

    private static void download(Activity a, JSONObject j) {
        if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
            Sheet sh = new Sheet(a, "Allow updates", "lock", Ui.pal());
            sh.note("Android needs a one-time permission: turn on \"Allow from this source\" for MIR MEDIA LABS, then come back and tap Update again.");
            sh.button("gear", "Open setting", true, () -> a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + a.getPackageName()))));
            sh.show();
            return;
        }
        Sheet sh = new Sheet(a, "Updating MIR MEDIA LABS", "download", Ui.pal());
        sh.d.setCancelable(false);
        TextView msg = Ui.mono(a, "connecting…", 13, Ui.INK);
        ProgressBar bar = new ProgressBar(a, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.VIO));
        LinearLayout box = sh.body();
        box.addView(msg, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 4, 12, 4, 6));
        box.addView(bar, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(10)), 4, 4, 4, 10));
        sh.show();
        Api.POOL.execute(() -> {
            String err = null;
            try {
                File apk = fetchApk(a, j, (pct, line) -> Api.MAIN.post(() -> { msg.setText(line); if (pct >= 0) bar.setProgress(pct); }));
                Api.MAIN.post(() -> msg.setText("installing — the app closes for a second; reopen it from the notification or your home screen"));
                // written synchronously: the install replaces this process right after commit
                Prefs.sp(a).edit().putString("upd_notes", "v" + j.optString("versionName") + "\n" + j.optString("notes", "")).commit();
                Thread.sleep(1200);
                install(a, apk);
            } catch (Exception e) { err = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage(); }
            final String fe = err;
            Api.MAIN.post(() -> {
                if (fe == null) return;
                sh.dismiss();
                Sheet f = new Sheet(a, "Update failed", "warn", Ui.pal());
                f.note(fe + "\n\nNothing was changed. You can try again, or install it by hand from the GitHub release.");
                f.button("refresh", "Try again", true, () -> download(a, j));
                f.button("external", "Open the GitHub release", false, () -> view(a, releasesPage()));
                f.show();
            });
        });
    }

    interface Prog { void on(int pct, String line); }

    /** Resumable download into the app's cache, then every check the manifest promises. */
    static File fetchApk(Context c, JSONObject j, Prog prog) throws Exception {
        File dir = new File(c.getCacheDir(), "updates");
        dir.mkdirs();
        long code = j.optLong("versionCode"), size = j.optLong("size", -1);
        File f = new File(dir, "mml-" + code + ".apk");
        File[] old = dir.listFiles();
        if (old != null) for (File o : old) if (!o.getName().startsWith("mml-" + code + ".")) o.delete();
        File part = new File(dir, "mml-" + code + ".apk.part");
        boolean lab = !"GitHub".equals(j.optString("_src"));
        String want = j.optString("sha256").toLowerCase();
        if (!(f.isFile() && want.equals(fileSha(f)))) {
            for (int attempt = 1; ; attempt++) {
                long have = part.isFile() ? part.length() : 0;
                HttpURLConnection h = open(j.getString("_apk"), lab, c);
                h.setReadTimeout(45000);
                if (have > 0) h.setRequestProperty("Range", "bytes=" + have + "-");
                try {
                    int rc = h.getResponseCode();
                    if (rc == 200) have = 0;                    // server ignored the range: start over
                    else if (rc == 416) { part.delete(); have = 0; continue; }
                    else if (rc != 206) throw new Exception("download failed (HTTP " + rc + ")");
                    long total = size > 0 ? size : (rc == 206 ? have + h.getContentLengthLong() : h.getContentLengthLong());
                    try (InputStream in = h.getInputStream(); OutputStream out = new FileOutputStream(part, have > 0)) {
                        byte[] buf = new byte[65536];
                        long done = have; int n, last = -2;
                        while ((n = in.read(buf)) > 0) {
                            out.write(buf, 0, n); done += n;
                            int pct = total > 0 ? (int) (done * 100 / total) : -1;
                            if (pct != last && prog != null) { last = pct; prog.on(pct, "downloading… " + (pct >= 0 ? pct + "%  ·  " : "") + mb(done)); }
                        }
                    }
                    break;
                } catch (java.io.IOException io) {
                    if (attempt >= 4) throw new Exception("download interrupted — " + Api.explain(io));
                    if (prog != null) prog.on(-1, "connection dropped — resuming (" + attempt + "/3)…");
                    Thread.sleep(1500L * attempt);
                } finally { h.disconnect(); }
            }
            if (size > 0 && part.length() != size) { part.delete(); throw new Exception("download size doesn't match the signed manifest — refused"); }
            if (!want.equals(fileSha(part))) { part.delete(); throw new Exception("checksum doesn't match the signed manifest — refused"); }
            if (!part.renameTo(f)) throw new Exception("couldn't store the update");
        }
        if (prog != null) prog.on(100, "verifying…");
        PackageInfo pi = c.getPackageManager().getPackageArchiveInfo(f.getPath(),
                Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES);
        if (pi != null) {
            long vc = Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
            if (!c.getPackageName().equals(pi.packageName) || vc != code) throw new Exception("the file isn't the promised build — refused");
            Set<String> got = certs(pi), mine = installedCerts(c);
            if (!got.isEmpty() && !mine.isEmpty()) {
                got.retainAll(mine);
                if (got.isEmpty()) throw new Exception("this build is signed with a different key than your app — Android would refuse it");
            }
        }
        return f;
    }

    static String fileSha(File f) {
        try (InputStream in = new FileInputStream(f)) {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] buf = new byte[65536];
            for (int n; (n = in.read(buf)) > 0; ) md.update(buf, 0, n);
            return hex(md.digest());
        } catch (Exception e) { return ""; }
    }

    static void install(Context c, File apk) throws Exception {
        PackageInstaller pi = c.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams sp = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        sp.setAppPackageName(c.getPackageName());
        sp.setSize(apk.length());
        // Android 12+: once this app installed itself, later updates need no extra tap (falls back to the prompt otherwise)
        if (Build.VERSION.SDK_INT >= 31) sp.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int sid = pi.createSession(sp);
        try (PackageInstaller.Session s = pi.openSession(sid)) {
            try (InputStream in = new FileInputStream(apk); OutputStream out = s.openWrite("MirMediaLabs.apk", 0, apk.length())) {
                byte[] buf = new byte[65536];
                for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
                s.fsync(out);
            }
            Intent cb = new Intent(c, InstallReceiver.class);
            int fl = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
            s.commit(PendingIntent.getBroadcast(c, sid, cb, fl).getIntentSender());
        }
    }

    /** Background (PushJob): notify once per new build, twice a day at most. */
    static void backgroundCheck(Context c) {
        if (!Prefs.bool(c, "upd_auto", true) || System.currentTimeMillis() - Prefs.lng(c, "upd_last", 0) < EVERY) return;
        Check ck = run(c);
        if (ck.best != null && Prefs.lng(c, "upd_notified", 0) != ck.best.optLong("versionCode")) {
            Prefs.put(c, "upd_notified", ck.best.optLong("versionCode"));
            Push.update(c, ck.best);
        }
    }
}
