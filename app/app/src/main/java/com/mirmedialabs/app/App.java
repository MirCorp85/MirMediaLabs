package com.mirmedialabs.app;

import android.app.Application;
import android.net.ConnectivityManager;
import android.net.Network;

/** Process-wide setup: crash capture, notification channels + schedule, and route re-check on network change. */
public class App extends Application {
    @Override public void onCreate() {
        super.onCreate();
        Crash.install(this);
        Push.channels(this);
        if (Prefs.configured(this)) PushJob.schedule(this);
        try {
            ConnectivityManager cm = getSystemService(ConnectivityManager.class);
            cm.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback() {
                private Network last;
                @Override public void onAvailable(Network n) {
                    if (last != null && !last.equals(n) && Prefs.configured(App.this)) Api.networkChanged(App.this);
                    last = n;
                }
            });
        } catch (Exception ignored) { }
    }
}
