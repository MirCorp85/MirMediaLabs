package com.mirmedialabs.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

/**
 * Self-update from the Media Lab's OWN update server: <server>/updates/version.json
 * ({versionCode, versionName, notes, apk, sha256}) + the APK, published by build_apk.ps1.
 * SHA-256 is verified before Android's own "Update?" prompt is shown.
 */
final class Updater {
    static String server(Context c) { return Prefs.activeUrl(c) + "/updates"; }

    static long installedCode(Context c) {
        try {
            PackageInfo pi = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
        } catch (Exception e) { return 0; }
    }
    static String installedName(Context c) {
        try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName; } catch (Exception e) { return "?"; }
    }

    static JSONObject fetchNewer(Context c) {
        HttpURLConnection h = null;
        try {
            h = (HttpURLConnection) new URL(server(c) + "/version.json?t=" + System.currentTimeMillis()).openConnection();
            h.setConnectTimeout(6000); h.setReadTimeout(10000);
            h.setRequestProperty("X-MML-Key", Prefs.key(c));
            if (h.getResponseCode() != 200) return null;
            JSONObject j = new JSONObject(new String(Api.readAll(h.getInputStream()), "UTF-8"));
            return j.optLong("versionCode") > installedCode(c) ? j : null;
        } catch (Exception e) { return null; }
        finally { if (h != null) h.disconnect(); }
    }

    /** Launch check (at most every 6 h) or manual check from the menu. */
    static void check(Activity a, boolean manual) {
        if (!manual && System.currentTimeMillis() - Prefs.lng(a, "upd_last", 0) < 6 * 3600_000L) return;
        Prefs.put(a, "upd_last", System.currentTimeMillis());
        Api.POOL.execute(() -> {
            JSONObject j = fetchNewer(a);
            Api.MAIN.post(() -> {
                if (a.isFinishing()) return;
                if (j == null) {
                    if (manual) new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                            .setTitle("MIR MEDIA LABS is up to date")
                            .setMessage("Installed: v" + installedName(a) + " (" + installedCode(a) + ")\nUpdate server: " + server(a))
                            .setPositiveButton("OK", null).show();
                    return;
                }
                String notes = j.optString("notes", "");
                new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                        .setTitle("MIR MEDIA LABS v" + j.optString("versionName") + " available")
                        .setMessage("You have v" + installedName(a) + ".\n\n" + (notes.isEmpty() ? "New build ready." : notes))
                        .setPositiveButton("Update now", (d, w) -> download(a, j))
                        .setNegativeButton("Later", null).show();
            });
        });
    }

    private static void download(Activity a, JSONObject j) {
        if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                    .setTitle("Allow updates")
                    .setMessage("Android needs a one-time permission: turn on \"Allow from this source\" for MIR MEDIA LABS, then come back and tap Update again.")
                    .setPositiveButton("Open setting", (d, w) -> a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:" + a.getPackageName()))))
                    .setNegativeButton("Cancel", null).show();
            return;
        }
        TextView msg = Ui.mono(a, "downloading…", 13, Ui.INK);
        msg.setPadding(Ui.dp(22), Ui.dp(14), Ui.dp(22), Ui.dp(6));
        AlertDialog dlg = new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Updating MIR MEDIA LABS").setView(msg).setCancelable(false).show();
        Api.POOL.execute(() -> {
            String err = null;
            HttpURLConnection h = null;
            try {
                String apk = j.optString("apk", "MirMediaLabs.apk");
                String url = apk.startsWith("http") ? apk : server(a) + "/" + apk;
                h = (HttpURLConnection) new URL(url).openConnection();
                h.setConnectTimeout(8000); h.setReadTimeout(60000);
                h.setRequestProperty("X-MML-Key", Prefs.key(a));
                if (h.getResponseCode() != 200) throw new Exception("HTTP " + h.getResponseCode());
                long total = h.getContentLengthLong();
                PackageInstaller pi = a.getPackageManager().getPackageInstaller();
                PackageInstaller.SessionParams sp = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
                sp.setAppPackageName(a.getPackageName());
                if (total > 0) sp.setSize(total);
                int sid = pi.createSession(sp);
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                try (PackageInstaller.Session s = pi.openSession(sid)) {
                    try (InputStream in = h.getInputStream(); OutputStream out = s.openWrite("MirMediaLabs.apk", 0, total > 0 ? total : -1)) {
                        byte[] buf = new byte[65536]; long done = 0; int n, last = -1;
                        while ((n = in.read(buf)) > 0) {
                            out.write(buf, 0, n); md.update(buf, 0, n); done += n;
                            int pct = total > 0 ? (int) (done * 100 / total) : -1;
                            if (pct != last) { last = pct; final long dd = done;
                                Api.MAIN.post(() -> msg.setText(pct >= 0 ? "downloading… " + pct + "%" : "downloading… " + dd / 1024 + " KB")); }
                        }
                        s.fsync(out);
                    }
                    String want = j.optString("sha256", "").toLowerCase();
                    StringBuilder got = new StringBuilder();
                    for (byte b : md.digest()) got.append(String.format("%02x", b));
                    if (!want.isEmpty() && !want.equals(got.toString())) { s.abandon(); throw new Exception("checksum mismatch — not installed"); }
                    Intent cb = new Intent(a, InstallReceiver.class);
                    int fl = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
                    s.commit(PendingIntent.getBroadcast(a, sid, cb, fl).getIntentSender());
                }
            } catch (Exception e) { err = e.getMessage(); }
            finally { if (h != null) h.disconnect(); }
            final String fe = err;
            Api.MAIN.post(() -> {
                dlg.dismiss();
                if (fe != null) new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                        .setTitle("Update failed").setMessage(fe).setPositiveButton("OK", null).show();
            });
        });
    }
}
