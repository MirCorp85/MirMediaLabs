package com.mirmedialabs.app;

import android.app.Activity;
import android.content.Context;
import android.widget.LinearLayout;

import org.json.JSONObject;

/** MIR MEDIA LABS themes for the native Media Lab page — the same five palettes as the web (claude · graphite ·
 *  obsidian · midnight · paper). The pick lives in /api/miros-prefs {mltheme:{id}} so web + phone + TV follow one
 *  choice; a local copy makes it instant at launch. */
public final class Theme {
    public static final String[] IDS = {"claude", "graphite", "obsidian", "midnight", "paper"};
    public static final String[] NAMES = {"Claude Dark", "Graphite", "Obsidian Gold", "Midnight Studio", "Paper Light"};
    public static final String[] DESC = {"Warm charcoal, clay accent", "Neutral slate, indigo accent", "Near-black, MirOS gold",
            "Deep navy, teal accent", "Warm white, rust accent"};
    /** {bg, bar, card, card2, line, line2, ink, dim, faint, accent} */
    public static final int[][] P = {
            {0xFF262624, 0xFF1F1E1D, 0xFF30302E, 0xFF3A3936, 0x14FFFFFF, 0x26FFFFFF, 0xFFF5F4EF, 0xFFBFBDB1, 0xFF8B897F, 0xFFD97757},
            {0xFF111214, 0xFF0C0D0F, 0xFF18191C, 0xFF212327, 0x12FFFFFF, 0x24FFFFFF, 0xFFECEEF1, 0xFFA6AAB2, 0xFF6F737B, 0xFF7C8CFF},
            {0xFF0E0D0B, 0xFF0A0908, 0xFF171512, 0xFF211E19, 0x14FFECC8, 0x26FFECC8, 0xFFF3EEE4, 0xFFBCB19B, 0xFF7F7663, 0xFFE3A949},
            {0xFF0B1220, 0xFF080E19, 0xFF101929, 0xFF172236, 0x17A0BEFF, 0x2BA0BEFF, 0xFFE6ECF5, 0xFF9EABC0, 0xFF67768D, 0xFF3FB8C9},
            {0xFFF6F5F1, 0xFFEFEDE7, 0xFFFFFFFF, 0xFFF1EFE9, 0x1A1E1C16, 0x2E1E1C16, 0xFF1E1D1A, 0xFF5C5A54, 0xFF8E8B83, 0xFFC2582F}};

    static int index(String id) { for (int i = 0; i < IDS.length; i++) if (IDS[i].equals(id)) return i; return 0; }
    public static String current(Context c) { return Prefs.str(c, "mltheme", "claude"); }
    public static String label(Context c) { return NAMES[index(current(c))]; }
    public static int[] palette(Context c) { return P[index(current(c))]; }

    /** Call before any view is built. */
    static void apply(Context c) { Ui.theme(palette(c)); }

    /** Pull the shared pick; rebuild only when another device changed it. */
    static void sync(Activity a, Api api) {
        api.get("/api/miros-prefs", r -> {
            if (!r.ok()) return;
            JSONObject t = r.obj().optJSONObject("mltheme");
            String id = t == null ? "" : t.optString("id", "");
            if (!id.isEmpty() && !id.equals(current(a))) { Prefs.put(a, "mltheme", id); a.recreate(); }
        });
    }

    public static void pick(Activity a) {
        Sheet sh = new Sheet(a, "Theme", "palette", Ui.pal());
        sh.note("Same five themes as the web studio — your pick follows you to every device.");
        String cur = current(a);
        for (int i = 0; i < IDS.length; i++) {
            final int k = i;
            LinearLayout r = sh.row(IDS[i].equals(cur) ? "check" : "palette", NAMES[i], DESC[i], P[i][9], () -> {
                Prefs.put(a, "mltheme", IDS[k]);
                new Api(a).post("/api/miros-prefs", Api.obj("key", "mltheme", "value", Api.obj("id", IDS[k])), r2 -> a.recreate());
            });
            swatch(a, r, P[i]);
        }
        sh.show();
    }

    /** Little 4-colour swatch at the end of a theme row. */
    static void swatch(Activity a, LinearLayout row, int[] p) {
        LinearLayout sw = new LinearLayout(a);
        float d = a.getResources().getDisplayMetrics().density;
        for (int c : new int[]{p[0], p[2], p[6], p[9]}) {
            android.view.View v = new android.view.View(a);
            android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
            g.setColor(c); g.setCornerRadius(4 * d); g.setStroke(1, 0x33FFFFFF);
            v.setBackground(g);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams((int) (14 * d), (int) (22 * d));
            lp.setMargins((int) (2 * d), 0, 0, 0);
            sw.addView(v, lp);
        }
        row.addView(sw, row.getChildCount() - 1);
    }
}
