package com.mirmedialabs.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.Application;
import android.content.Intent;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.widget.FrameLayout;

/** Floating MUSE — her 3D look on top of EVERY screen of the app (chat, editor, series, downloader, social), same as the
 *  web studio's #muse-float. Drag her anywhere (position shared by all screens), tap to talk: on the main screen that
 *  starts live voice; elsewhere it jumps back to the chat and starts there (MirAI lives in the chat). */
final class FloatingMuse implements Application.ActivityLifecycleCallbacks {
    private static boolean installed;
    static WebView current;            // the floating orb of the screen in front (MuseLive mirrors her state onto it)

    static void install(MainActivity m) {
        if (installed) return;
        installed = true;
        m.getApplication().registerActivityLifecycleCallbacks(new FloatingMuse());
    }

    static boolean on(Activity a) { return !"0".equals(Prefs.str(a, "muse_float", "1")); }

    static void set(Activity a, boolean v) {
        Prefs.put(a, "muse_float", v ? "1" : "0");
        if (v) attach(a); else detach(a);
    }

    @Override public void onActivityResumed(Activity a) { attach(a); }
    @Override public void onActivityPaused(Activity a) { }
    @Override public void onActivityCreated(Activity a, Bundle b) { }
    @Override public void onActivityStarted(Activity a) { }
    @Override public void onActivityStopped(Activity a) { }
    @Override public void onActivitySaveInstanceState(Activity a, Bundle b) { }
    @Override public void onActivityDestroyed(Activity a) { if (current != null && current.getContext() == a) current = null; }

    private static boolean wanted(Activity a) {
        return on(a) && !(a instanceof SetupActivity) && !(a instanceof QrScanActivity) && !Prefs.key(a).isEmpty();
    }

    private static void detach(Activity a) {
        View v = a.getWindow().getDecorView().findViewWithTag("muse-float");
        if (v != null) {
            ((ViewGroup) v.getParent()).removeView(v);
            WebView w = (WebView) ((ViewGroup) v).getChildAt(0);
            if (w == current) current = null;
            w.destroy();
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    static void attach(Activity a) {
        FrameLayout content = a.findViewById(android.R.id.content);
        if (content == null) return;
        View old = content.findViewWithTag("muse-float");
        if (!wanted(a)) { if (old != null) detach(a); return; }
        if (old != null) { current = (WebView) ((ViewGroup) old).getChildAt(0); old.bringToFront(); return; }
        MuseLive ml = a instanceof MainActivity ? ((MainActivity) a).muse : null;
        if (ml != null) ml.style = Prefs.str(a, "muse_style", ml.style);
        String style = ml != null ? ml.style : Prefs.str(a, "muse_style", "pearl");
        WebView w = MuseLive.orb(a, style, true, "idle", null);
        FrameLayout box = new FrameLayout(a);
        box.setTag("muse-float");
        box.addView(w, new FrameLayout.LayoutParams(-1, -1));
        View touch = new View(a);                                  // drag / tap layer over the WebView
        box.addView(touch, new FrameLayout.LayoutParams(-1, -1));
        int size = Ui.dp(64);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(size, size);
        content.addView(box, lp);
        box.setElevation(Ui.dp(30));
        content.post(() -> {
            float fx = Float.parseFloat(Prefs.str(a, "muse_fx", "0.86")), fy = Float.parseFloat(Prefs.str(a, "muse_fy", "0.74"));
            box.setX(clamp(fx * content.getWidth() - size / 2f, content.getWidth() - size));
            box.setY(clamp(fy * content.getHeight() - size / 2f, content.getHeight() - size));
        });
        final float[] d = new float[3];
        touch.setOnTouchListener((v, e) -> {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    d[0] = e.getRawX() - box.getX(); d[1] = e.getRawY() - box.getY(); d[2] = 0;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    float nx = e.getRawX() - d[0], ny = e.getRawY() - d[1];
                    d[2] += Math.abs(nx - box.getX()) + Math.abs(ny - box.getY());
                    if (d[2] > Ui.dp(6)) {
                        box.setX(clamp(nx, content.getWidth() - size));
                        box.setY(clamp(ny, content.getHeight() - size));
                    }
                    return true;
                case MotionEvent.ACTION_UP:
                    if (d[2] > Ui.dp(6)) {
                        Prefs.put(a, "muse_fx", String.valueOf((box.getX() + size / 2f) / content.getWidth()));
                        Prefs.put(a, "muse_fy", String.valueOf((box.getY() + size / 2f) / content.getHeight()));
                    } else tap(a);
                    return true;
            }
            return false;
        });
        current = w;
    }

    private static float clamp(float v, float max) { return Math.max(0, Math.min(max, v)); }

    private static void tap(Activity a) {
        if (a instanceof MainActivity) { ((MainActivity) a).muse.toggle(); return; }
        Intent i = new Intent(a, MainActivity.class).putExtra("muse", true)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        a.startActivity(i);
    }
}
