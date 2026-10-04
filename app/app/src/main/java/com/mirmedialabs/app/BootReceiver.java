package com.mirmedialabs.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** After a reboot or a self-update: put the notification schedule back (and Instant delivery, if on). */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        if (!Prefs.configured(c)) return;
        Push.channels(c);
        PushJob.schedule(c);
        if (Intent.ACTION_MY_PACKAGE_REPLACED.equals(i.getAction())) Push.updated(c);
        if (Push.instant(c)) PushService.start(c);
    }
}
