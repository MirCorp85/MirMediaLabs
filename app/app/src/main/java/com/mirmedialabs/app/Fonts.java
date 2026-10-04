package com.mirmedialabs.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Typeface;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

/** MIR FONTS — the 10 MirOS typefaces (assets/fonts/<id>.ttf, copied from the MirOS app; same designs as the web
 *  /static/fonts/miros/*.woff2). The pick lives in this Media Lab's own /api/miros-prefs {font:{id}} (per user),
 *  so desktop web, phone web and this app follow one choice. Never talks to MirOS. */
final class Fonts {
    static final String[] IDS = {"", "orbit", "vector", "horizon", "bastion", "stencil", "pixel", "matrix", "velocity", "hollow", "quill"};
    static final String[] NAMES = {"Default", "Mir Orbit", "Mir Vector", "Mir Horizon", "Mir Bastion", "Mir Stencil",
            "Mir Pixel", "Mir Matrix", "Mir Velocity", "Mir Hollow", "Mir Quill"};
    static final String[] DESC = {"System sans", "Round monoline geometric", "Square-cut technical", "Extended hairline",
            "Condensed heavy", "Military stencil", "8-bit pixel grid", "LED dot-matrix", "Forward-slanted speed",
            "Outlined neon-tube", "Broad-nib contrast"};

    static String current(Context c) { return Prefs.str(c, "font", ""); }

    static Typeface load(Context c, String id) {
        if (id == null || id.isEmpty()) return null;
        try { return Typeface.createFromAsset(c.getAssets(), "fonts/" + id + ".ttf"); } catch (Exception e) { return null; }
    }

    /** Call before building any view. */
    static void apply(Context c) { Ui.setFont(load(c, current(c))); }

    /** Pull the shared pick; rebuild only when it changed on another device. */
    static void sync(Activity a, Api api) {
        api.get("/api/miros-prefs", r -> {
            if (!r.ok()) return;
            JSONObject f = r.obj().optJSONObject("font");
            String id = f == null ? "" : f.optString("id", "");
            if (!id.equals(current(a))) { Prefs.put(a, "font", id); a.recreate(); }
        });
    }

    static void pick(Activity a, Api api) {
        String cur = current(a);
        Sheet sh = new Sheet(a, "MIR FONTS", "type", Ui.pal());
        sh.note("Ten original typefaces — the web studio and this app follow one pick.");
        for (int i = 0; i < IDS.length; i++) {
            final int k = i;
            LinearLayout r = sh.row(IDS[i].equals(cur) ? "check" : "type", NAMES[i] + "   Aa 4,561", DESC[i], () -> {
                Prefs.put(a, "font", IDS[k]);
                api.post("/api/miros-prefs", Api.obj("key", "font", "value", Api.obj("id", IDS[k])), null);
                a.recreate();
            });
            Typeface tf = load(a, IDS[i]);
            TextView t = (TextView) ((LinearLayout) r.getChildAt(1)).getChildAt(0);
            if (tf != null) t.setTypeface(tf);
            t.setTextSize(18);
        }
        sh.show();
    }
}
