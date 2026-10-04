package com.mirmedialabs.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;

import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** If the app ever crashes: keep the stack trace on the phone, and next launch offer to email it (nothing is sent by itself). */
final class Crash {
    private static final String FILE = "last_crash.txt";

    static void install(Context c) {
        final Context app = c.getApplicationContext();
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            try {
                StringWriter sw = new StringWriter();
                e.printStackTrace(new PrintWriter(sw));
                String report = "When: " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date())
                        + "\nApp: v" + Updater.installedName(app) + " (" + Updater.installedCode(app) + ")"
                        + "\nAndroid: " + Build.VERSION.RELEASE + " (SDK " + Build.VERSION.SDK_INT + ")"
                        + "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL + (Tv.is(app) ? " (TV)" : "")
                        + "\nThread: " + t.getName() + "\n\n" + sw;
                try (FileOutputStream o = new FileOutputStream(new File(app.getFilesDir(), FILE))) {
                    o.write(report.getBytes(StandardCharsets.UTF_8));
                }
            } catch (Throwable ignored) { }
            if (prev != null) prev.uncaughtException(t, e);
        });
    }

    static void offer(Activity a) {
        File f = new File(a.getFilesDir(), FILE);
        if (!f.isFile()) return;
        String report;
        try { report = new String(java.nio.file.Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8); }
        catch (Exception e) { report = ""; }
        f.delete();
        if (report.isEmpty()) return;
        final String r = report;
        Sheet sh = new Sheet(a, "Sorry — the app closed unexpectedly", "bug", Ui.pal());
        sh.note("A crash report was saved on this phone. Sending it helps fix the problem; you'll see the whole email "
                + "before anything is sent. It contains the error and your device model, nothing else.");
        sh.button("mail", "Email the report", true, () -> {
            Intent i = new Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:"));
            i.putExtra(Intent.EXTRA_EMAIL, new String[]{Creator.EMAIL});
            i.putExtra(Intent.EXTRA_SUBJECT, "[MML crash] v" + Updater.installedName(a));
            i.putExtra(Intent.EXTRA_TEXT, "What were you doing when it closed?\n\n\n---\n" + r);
            try { a.startActivity(Intent.createChooser(i, "Crash report")); } catch (Exception ignored) { }
        });
        sh.button("close", "Dismiss", false, () -> {});
        sh.show();
    }
}
