package com.mirmedialabs.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.os.Build;
import android.widget.Toast;

/** PackageInstaller callback: shows Android's "Update?" confirmation (or a notification for it), reports failures. */
public class InstallReceiver extends BroadcastReceiver {
    @SuppressWarnings("deprecation")
    @Override public void onReceive(Context c, Intent i) {
        int st = i.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (st == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = Build.VERSION.SDK_INT >= 33 ? i.getParcelableExtra(Intent.EXTRA_INTENT, Intent.class) : i.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm == null) return;
            confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (Push.appVisible) {
                c.startActivity(confirm);
            } else {    // Android blocks pop-ups from the background: hand the confirmation over as a notification
                Notification n = Push.builder(c, Push.CH_UPD).setContentTitle("Tap to finish updating MIR MEDIA LABS")
                        .setContentText("Android asks you to confirm the update").setAutoCancel(true)
                        .setContentIntent(PendingIntent.getActivity(c, 7, confirm, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)).build();
                try { ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).notify(Push.ID_UPDATE, n); } catch (SecurityException ignored) { }
            }
        } else if (st != PackageInstaller.STATUS_SUCCESS) {
            String m = i.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
            String why = st == PackageInstaller.STATUS_FAILURE_ABORTED ? "cancelled"
                    : st == PackageInstaller.STATUS_FAILURE_CONFLICT ? "this build is signed differently from your app — install it from GitHub by hand"
                    : st == PackageInstaller.STATUS_FAILURE_STORAGE ? "not enough free space"
                    : st == PackageInstaller.STATUS_FAILURE_INCOMPATIBLE ? "not compatible with this device"
                    : m == null ? "status " + st : m;
            Toast.makeText(c, "Update not installed: " + why, Toast.LENGTH_LONG).show();
        }
    }
}
