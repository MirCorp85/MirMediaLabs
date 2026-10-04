package com.mirmedialabs.app;

import android.app.Notification;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * Live link to the lab while it matters: started when you send a request (or always, with Instant delivery).
 * Holds the /api/events long-poll so "your video is ready" lands the second the render ends, and keeps a
 * quiet progress notification up meanwhile. Stops by itself once nothing of yours is queued or running.
 */
public class PushService extends Service {
    static volatile boolean running = false;
    private volatile boolean stop = false;
    private Thread worker;

    /** Safe from anywhere: Android 12+ refuses background starts → the periodic PushJob covers it instead. */
    static void start(Context c) {
        if (!Prefs.configured(c)) return;
        try {
            Intent i = new Intent(c, PushService.class);
            if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i); else c.startService(i);
        } catch (Exception notAllowedNow) {
            PushJob.schedule(c);
        }
    }

    static void stopIfIdle(Context c) {
        if (running) c.startService(new Intent(c, PushService.class).putExtra("recheck", true));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        Push.channels(this);
        foreground(Push.instant(this) ? "Connected to your lab" : "Checking your request…", Push.instant(this));
        if (worker == null || !worker.isAlive()) {
            stop = false;
            worker = new Thread(this::loop, "mml-push");
            worker.start();
        }
        return START_STICKY;
    }

    private void foreground(String line, boolean idle) {
        Notification n = Push.builder(this, idle ? Push.CH_LINK : Push.CH_PROG)
                .setContentTitle(idle ? "MIR MEDIA LABS" : "MIR MEDIA LABS is working")
                .setContentText(line).setOngoing(true).setOnlyAlertOnce(true)
                .setContentIntent(Push.open(this, 1, null)).build();
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(Push.ID_ONGOING, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            else startForeground(Push.ID_ONGOING, n);
        } catch (Exception e) {
            stop = true;
            stopSelf();
        }
    }

    private void loop() {
        running = true;
        long backoff = 3000, failingSince = 0;
        boolean legacy = false;
        String lastLine = "";
        try {
            while (!stop) {
                Object[] act = Push.active(this);
                int n = (Integer) act[0];
                boolean instant = Push.instant(this);
                if (n < 0) {                                   // lab unreachable
                    if (failingSince == 0) failingSince = System.currentTimeMillis();
                    if (!instant && System.currentTimeMillis() - failingSince > 30 * 60_000L) break;
                    if (!lastLine.equals("offline")) { foreground("Can't reach your lab — retrying", true); lastLine = "offline"; }
                    sleep(backoff);
                    backoff = Math.min(backoff * 2, 120_000);
                    continue;
                }
                failingSince = 0;
                backoff = 3000;
                if (n == 0 && !instant) {
                    if (legacy) Push.legacyPoll(this); else Push.poll(this, 0);    // flush the final "done"
                    break;
                }
                String line = n == 0 ? "Connected to your lab" : (String) act[1] + (n > 1 ? "  (+" + (n - 1) + " more)" : "");
                if (!line.equals(lastLine)) { foreground(line, n == 0); lastLine = line; }
                if (legacy) {
                    Push.legacyPoll(this);
                    sleep(n > 0 ? 6000 : 30000);
                } else {
                    int r = Push.poll(this, n > 0 ? 15 : 50);
                    if (r == Push.LEGACY) legacy = true;
                    else if (r == Push.FAIL) sleep(4000);
                }
            }
        } finally {
            running = false;
            stopForeground(true);
            stopSelf();
        }
    }

    private void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException ignored) { } }

    @Override public void onDestroy() { stop = true; running = false; if (worker != null) worker.interrupt(); super.onDestroy(); }
    @Override public IBinder onBind(Intent i) { return null; }
}
