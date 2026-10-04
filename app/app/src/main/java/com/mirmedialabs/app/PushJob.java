package com.mirmedialabs.app;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

/**
 * Background catch-up, every ~15 min when the phone has a network (Android may stretch it in Doze):
 * delivers anything the lab queued for you, notices a render you started from another device and waits
 * for it (up to ~8 min per run), and checks for app updates twice a day.
 */
public class PushJob extends JobService {
    static final int ID = 4100;
    private volatile boolean stop = false;

    static void schedule(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        for (JobInfo j : js.getAllPendingJobs()) if (j.getId() == ID) return;
        JobInfo.Builder b = new JobInfo.Builder(ID, new ComponentName(c, PushJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(15 * 60_000L);
        try { js.schedule(b.build()); } catch (Exception ignored) { }
    }

    @Override public boolean onStartJob(JobParameters p) {
        if (!Prefs.configured(this)) return false;
        new Thread(() -> {
            try {
                new Api(this).probeSync();
                try { Updater.backgroundCheck(this); } catch (Exception ignored) { }
                if (PushService.running) return;
                if (Push.instant(this)) { PushService.start(this); return; }
                long until = System.currentTimeMillis() + 8 * 60_000L;
                boolean legacy = false;
                while (!stop) {
                    if (legacy) Push.legacyPoll(this);
                    else if (Push.poll(this, 0) == Push.LEGACY) { legacy = true; Push.legacyPoll(this); }
                    Object[] act = Push.active(this);
                    if ((Integer) act[0] <= 0 || System.currentTimeMillis() > until) break;
                    if (legacy) Thread.sleep(8000);
                    else Push.poll(this, 25);
                }
            } catch (Exception ignored) {
            } finally {
                jobFinished(p, false);
            }
        }, "mml-push-job").start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { stop = true; return true; }
}
