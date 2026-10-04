package com.mirmedialabs.app;

import android.app.Activity;
import android.app.UiModeManager;
import android.content.Context;
import android.content.res.Configuration;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.GridView;

/** Android TV support for the same APK: detection, D-pad focusable controls and a visible focus ring. */
final class Tv {
    private static Boolean tv;

    static boolean is(Context c) {
        if (tv == null) {
            UiModeManager um = (UiModeManager) c.getSystemService(Context.UI_MODE_SERVICE);
            tv = um != null && um.getCurrentModeType() == Configuration.UI_MODE_TYPE_TELEVISION;
        }
        return tv;
    }

    /** Glowing ring + slight zoom on whatever the remote is focused on. */
    static void install(Activity a) {
        if (!is(a)) return;
        a.getWindow().getDecorView().getViewTreeObserver().addOnGlobalFocusChangeListener((old, now) -> {
            if (old != null) { old.setScaleX(1f); old.setScaleY(1f); old.setForeground(null); }
            if (now != null && !(now instanceof EditText) && !(now instanceof GridView)) {
                now.setScaleX(1.04f); now.setScaleY(1.04f);
                GradientDrawable ring = new GradientDrawable();
                ring.setCornerRadius(Ui.dp(12));
                ring.setStroke(Ui.dp(3), Ui.AMB);
                now.setForeground(ring);
            }
        });
    }

    /** Every clickable view becomes reachable with the D-pad. Call after (re)building a view tree. */
    static void focusify(View v) {
        if (tv == null || !tv) return;
        if (v.isClickable() || v.isLongClickable()) v.setFocusable(true);
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) focusify(g.getChildAt(i));
        }
    }
}
