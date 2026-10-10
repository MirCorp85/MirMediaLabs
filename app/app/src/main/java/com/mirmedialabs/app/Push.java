package com.mirmedialabs.app;

import android.Manifest;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashSet;
import java.util.Set;

/**
 * Notifications, pushed by your own lab — no Firebase, no Google services, nothing leaves your setup.
 * The lab keeps a per-person feed (server/events.py); the app holds a long-poll on GET /api/events, so a
 * "your video is ready" arrives the moment the render ends:
 *   • while a render of yours is queued or running → PushService (foreground, shows live progress)
 *   • "Instant delivery" on → PushService stays connected all the time (host messages arrive instantly too)
 *   • otherwise → PushJob checks every ~15 min (Android decides the exact time in battery saver / Doze)
 * Servers older than the feed are still covered: the app diffs /api/jobs instead.
 */
final class Push {
    static final String CH_DONE = "renders", CH_PROG = "progress", CH_NOTICE = "notices", CH_UPD = "updates", CH_LINK = "connection";
    static final int ID_ONGOING = 1, ID_UPDATE = 2, ID_UPDATED = 3;
    static final int LEGACY = -1, FAIL = -2;

    /** MainActivity in front → render results show in the chat instead of the shade. */
    static volatile boolean appVisible = false;

    static void channels(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        NotificationChannel done = new NotificationChannel(CH_DONE, "Finished renders", NotificationManager.IMPORTANCE_HIGH);
        done.setDescription("Your image, video, song or MirAI reply is ready (or failed)");
        NotificationChannel prog = new NotificationChannel(CH_PROG, "Render in progress", NotificationManager.IMPORTANCE_LOW);
        prog.setDescription("Live status while the lab works on your request");
        prog.setShowBadge(false);
        NotificationChannel notice = new NotificationChannel(CH_NOTICE, "Messages from the lab host", NotificationManager.IMPORTANCE_DEFAULT);
        NotificationChannel upd = new NotificationChannel(CH_UPD, "App updates", NotificationManager.IMPORTANCE_DEFAULT);
        NotificationChannel link = new NotificationChannel(CH_LINK, "Instant delivery connection", NotificationManager.IMPORTANCE_MIN);
        link.setDescription("Quiet, always-on connection to your lab (only when Instant delivery is on)");
        link.setShowBadge(false);
        for (NotificationChannel ch : new NotificationChannel[]{done, prog, notice, upd, link}) nm.createNotificationChannel(ch);
    }

    static boolean allowed(Context c) {
        if (Build.VERSION.SDK_INT >= 33 && c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false;
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        return nm == null || Build.VERSION.SDK_INT < 24 || nm.areNotificationsEnabled();
    }

    static boolean on(Context c, String what) { return Prefs.bool(c, "n_" + what, true); }
    static boolean instant(Context c) { return Prefs.bool(c, "n_instant", false); }

    @SuppressWarnings("deprecation")
    static Notification.Builder builder(Context c, String ch) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, ch) : new Notification.Builder(c);
        b.setSmallIcon(R.drawable.ic_stat).setColor(Theme.palette(c)[9]).setShowWhen(true);
        if (Build.VERSION.SDK_INT < 26) b.setPriority(CH_DONE.equals(ch) ? Notification.PRIORITY_HIGH : CH_LINK.equals(ch) ? Notification.PRIORITY_MIN : Notification.PRIORITY_DEFAULT);
        return b;
    }

    static PendingIntent open(Context c, int req, Intent extras) {
        Intent i = new Intent(c, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (extras != null) i.putExtras(extras);
        return PendingIntent.getActivity(c, req, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void post(Context c, int id, Notification n) {
        if (!allowed(c)) return;
        try { ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).notify(id, n); } catch (SecurityException ignored) { }
    }

    // ── the feed ─────────────────────────────────────────────────────────
    /** One long-poll round. Returns the number of events handled, LEGACY (server has no feed) or FAIL (offline). */
    static int poll(Context c, int waitSec) {
        Api api = new Api(c);
        long since = Prefs.lng(c, "ev_last", 0);
        Api.Resp r = api.getSync("/api/events?since=" + since + "&wait=" + (since <= 0 ? 0 : waitSec), (waitSec + 20) * 1000);
        if (r.status == 404) return LEGACY;
        if (!r.ok()) return FAIL;
        JSONObject o = r.obj();
        JSONArray evs = o.optJSONArray("events");
        int n = 0;
        for (int i = 0; evs != null && i < evs.length(); i++) {
            JSONObject ev = evs.optJSONObject(i);
            if (ev == null) continue;
            handle(c, api, ev);
            n++;
        }
        long last = o.optLong("last", since);
        if (last > 0) Prefs.put(c, "ev_last", last);
        return n;
    }

    static void handle(Context c, Api api, JSONObject ev) {
        String type = ev.optString("type");
        if ("job".equals(type)) {
            if (!on(c, "done") || appVisible) return;
            job(c, api, ev.optString("job"), ev.optString("status"), ev.optString("title"), ev.optString("body"),
                    ev.optJSONArray("files"), ev.optString("model"), ev.optString("kind"));
        } else if ("notice".equals(type)) {
            if (!on(c, "notice") && !ev.optBoolean("test")) return;
            Notification.Builder b = builder(c, CH_NOTICE).setContentTitle(ev.optString("title", "MIR MEDIA LABS"))
                    .setContentText(ev.optString("body")).setStyle(new Notification.BigTextStyle().bigText(ev.optString("body")))
                    .setAutoCancel(true).setContentIntent(open(c, 900, null));
            post(c, (int) (ev.optLong("id") % 100000) + 1000, b.build());
        }
    }

    private static void job(Context c, Api api, String jid, String status, String title, String body, JSONArray files, String model, String kind) {
        boolean ok = "done".equals(status);
        String file = files != null && files.length() > 0 ? files.optString(0) : "";
        Intent ex = new Intent();
        if (ok && !file.isEmpty() && !"llama".equals(model)) ex.putExtra("open_file", file).putExtra("open_model", model);
        int id = 2000 + Math.abs(jid.hashCode() % 90000);
        Notification.Builder b = builder(c, CH_DONE).setContentTitle(title).setContentText(body)
                .setAutoCancel(true).setContentIntent(open(c, id, ex)).setCategory(Notification.CATEGORY_STATUS);
        Bitmap pic = null;
        if (ok && ("image".equals(kind) || "video".equals(kind)) && !file.isEmpty()) {
            Api.Resp t = api.bytesSync("/thumb/" + Api.enc(file));
            if (t.ok() && t.bytes != null) pic = BitmapFactory.decodeByteArray(t.bytes, 0, t.bytes.length);
        }
        if (pic != null) b.setLargeIcon(pic).setStyle(new Notification.BigPictureStyle().bigPicture(pic).bigLargeIcon((Bitmap) null).setSummaryText(body));
        else b.setStyle(new Notification.BigTextStyle().bigText(body));
        post(c, id, b.build());
    }

    // ── servers without the feed: diff the job list ──────────────────────
    static void legacyPoll(Context c) {
        Api api = new Api(c);
        Api.Resp r = api.getSync("/api/jobs?limit=30");
        if (!r.ok()) return;
        Set<String> watch = new HashSet<>(Prefs.sp(c).getStringSet("watch", new HashSet<>()));
        JSONArray js = r.arr();
        for (int i = 0; i < js.length(); i++) {
            JSONObject j = js.optJSONObject(i);
            if (j == null || (j.has("mine") && !j.optBoolean("mine"))) continue;
            String id = j.optString("id"), st = j.optString("status");
            if ("queued".equals(st) || "running".equals(st)) watch.add(id);
            else if (watch.remove(id) && on(c, "done") && !appVisible) {
                JSONArray f = j.optJSONArray("files");
                String k = f != null && f.length() > 0 ? Ui.kindOf(f.optString(0)) : "";
                String what = "llama".equals(j.optString("model")) ? null : "video".equals(k) ? "video" : "image".equals(k) ? "image" : "audio".equals(k) ? "track" : "result";
                job(c, api, id, st, "done".equals(st) ? (what == null ? "MirAI replied" : "Your " + what + " is ready") : "Request failed",
                        "done".equals(st) ? j.optString("input", j.optString("prompt")) : j.optString("error"), f, j.optString("model"), k);
            }
        }
        Prefs.sp(c).edit().putStringSet("watch", watch).apply();
    }

    /** My queued + running requests: {count, line for the ongoing notification}. Blocking. */
    static Object[] active(Context c) {
        Api.Resp r = new Api(c).getSync("/api/jobs?limit=20");
        if (!r.ok()) return new Object[]{-1, ""};
        JSONArray js = r.arr();
        int n = 0;
        String line = "";
        for (int i = 0; i < js.length(); i++) {
            JSONObject j = js.optJSONObject(i);
            if (j == null || (j.has("mine") && !j.optBoolean("mine"))) continue;
            String st = j.optString("status");
            if (!"queued".equals(st) && !"running".equals(st)) continue;
            n++;
            if ("running".equals(st) || line.isEmpty()) {
                String stage = j.optString("stage", "");
                String step = j.optString("step", "");
                double started = j.optDouble("started", 0);
                line = ("running".equals(st) ? (stage.isEmpty() ? "Rendering" : cap(stage)) : "Waiting in the queue")
                        + (step.isEmpty() ? "" : " · step " + step)
                        + (started > 0 && "running".equals(st) ? " · " + Ui.dur(started, System.currentTimeMillis() / 1000.0) : "");
            }
        }
        return new Object[]{n, line};
    }

    static String cap(String s) { return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1); }

    // ── updates ──────────────────────────────────────────────────────────
    static void update(Context c, JSONObject j) {
        if (!on(c, "update")) return;
        Intent ex = new Intent().putExtra("check_update", true);
        String notes = j.optString("notes", "");
        Notification.Builder b = builder(c, CH_UPD).setContentTitle("MIR MEDIA LABS v" + j.optString("versionName") + " is available")
                .setContentText(notes.isEmpty() ? "Tap to update — signed by MirCorp, verified" : notes)
                .setStyle(new Notification.BigTextStyle().bigText(notes.isEmpty() ? "Tap to update." : notes))
                .setAutoCancel(true).setContentIntent(open(c, ID_UPDATE, ex));
        post(c, ID_UPDATE, b.build());
    }

    /** After a self-update (BootReceiver on MY_PACKAGE_REPLACED). */
    static void updated(Context c) {
        String notes = Prefs.str(c, "upd_notes", "");
        if (notes.isEmpty()) return;
        Prefs.put(c, "upd_notes", "");
        Notification.Builder b = builder(c, CH_UPD).setContentTitle("Updated to MIR MEDIA LABS v" + Updater.installedName(c))
                .setContentText("Tap to open").setStyle(new Notification.BigTextStyle().bigText(notes))
                .setAutoCancel(true).setContentIntent(open(c, ID_UPDATED, null));
        post(c, ID_UPDATED, b.build());
    }

    // ── settings sheet (⋮ → Notifications) ───────────────────────────────
    static void settings(Activity a) {
        Sheet sh = new Sheet(a, "Notifications", "bell", Ui.pal());
        if (!allowed(a)) {
            sh.note("Notifications are off for MIR MEDIA LABS on this phone.");
            sh.row("bell", "Turn notifications on", "Android settings", () -> systemSettings(a));
        }
        sh.section("Tell me when");
        sh.toggle("check-circle", "A render finishes", "image, video, song or MirAI reply — with a preview", on(a, "done"), v -> Prefs.put(a, "n_done", v));
        sh.toggle("mail", "The lab host sends a message", "maintenance, new features, invites", on(a, "notice"), v -> Prefs.put(a, "n_notice", v));
        sh.toggle("download", "An app update is out", "signed builds from GitHub or your lab", on(a, "update"), v -> Prefs.put(a, "n_update", v));
        sh.section("Delivery");
        sh.toggle("bolt", "Instant delivery", "stay connected to the lab so messages arrive the second they happen (small battery cost; "
                + "otherwise Android checks every ~15 min while no render is running)", instant(a), v -> {
            Prefs.put(a, "n_instant", v);
            if (v) PushService.start(a); else PushService.stopIfIdle(a);
        });
        sh.section("Check");
        sh.rowStay("send", "Send a test notification", "the lab pushes one to this phone", () -> new Api(a).post("/api/events/test", null, r -> {
            if (!r.ok()) { android.widget.Toast.makeText(a, r.status == 404 ? "Your lab is older — update MIR MEDIA LABS on the PC for push" : r.err(), android.widget.Toast.LENGTH_LONG).show(); return; }
            android.widget.Toast.makeText(a, "Sent — it arrives in a few seconds", android.widget.Toast.LENGTH_SHORT).show();
            appVisibleBypass(a);
        }));
        sh.row("gear", "Android notification settings", "sounds, importance, per-category", () -> systemSettings(a));
        sh.show();
    }

    /** The test should show even though the app is open: fetch it now, outside the visible-app filter. */
    private static void appVisibleBypass(Context c) {
        new Thread(() -> {
            try { Thread.sleep(800); } catch (InterruptedException ignored) { }
            poll(c, 5);
        }, "mml-push-test").start();
    }

    static void systemSettings(Activity a) {
        try {
            Intent i = Build.VERSION.SDK_INT >= 26 ? new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, a.getPackageName())
                    : new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, android.net.Uri.parse("package:" + a.getPackageName()));
            a.startActivity(i);
        } catch (Exception ignored) { }
    }
}
