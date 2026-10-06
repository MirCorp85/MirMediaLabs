package com.mirmedialabs.app;

import android.content.Context;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Lab palette (obsidian + per-model accents) and view helpers. */
final class Ui {
    // Atom Reactor palette (matches the app icon): ember black, orange glow, yellow core, teal electrons
    // themeable (MIR MEDIA LABS themes — same five palettes as the web): set by theme() before any view is built
    static int BG = 0xFF0D0806, BAR = 0xFF140C08, CARD = 0x0BFFBE8C, CARD2 = 0x14FFBE8C;
    static int LINE = 0x24FF783C, LINE2 = 0x42FF8C46;
    static int INK = 0xFFFFF4E8, DIM = 0xFFDCC2AA, FAINT = 0xFFA88C78;
    static int VIO = 0xFFFF5A1F;
    static final int AMB = 0xFFFFC21A, CYA = 0xFF1FC8DC, EMR = 0xFF5EE08A, RED = 0xFFFF3B5C, GRN = 0xFF5EE08A;
    static boolean LIGHT = false;
    /** p = {bg, bar, card, card2, line, line2, ink, dim, faint, accent} */
    static void theme(int[] p) {
        if (p == null || p.length < 10) return;
        BG = p[0]; BAR = p[1]; CARD = p[2]; CARD2 = p[3]; LINE = p[4]; LINE2 = p[5]; INK = p[6]; DIM = p[7]; FAINT = p[8]; VIO = p[9];
        LIGHT = (Color.red(BG) + Color.green(BG) + Color.blue(BG)) > 3 * 160;
    }
    /** Palette for the shared bottom-sheet menus. */
    static Sheet.Pal pal() { return new Sheet.Pal(BG, CARD2, LINE2, INK, DIM, VIO); }

    static float density = 3f;
    static void init(Context c) { density = c.getResources().getDisplayMetrics().density; }
    static int dp(float v) { return Math.round(v * density); }

    /** Android 15+ draws every app edge-to-edge (status bar, nav bar and keyboard overlap the window).
     *  Pad a screen's root by those insets on top of its own padding; older Android lays out as before. */
    static void insets(View v) {
        if (android.os.Build.VERSION.SDK_INT < 35) return;
        final int l = v.getPaddingLeft(), t = v.getPaddingTop(), r = v.getPaddingRight(), b = v.getPaddingBottom();
        v.setOnApplyWindowInsetsListener((view, wi) -> {
            android.graphics.Insets bars = wi.getInsets(android.view.WindowInsets.Type.systemBars() | android.view.WindowInsets.Type.displayCutout());
            android.graphics.Insets ime = wi.getInsets(android.view.WindowInsets.Type.ime());
            view.setPadding(l + bars.left, t + bars.top, r + bars.right, b + Math.max(bars.bottom, ime.bottom));
            return wi;
        });
        v.requestApplyInsets();
    }

    static final Typeface MONO = Typeface.MONOSPACE;
    static Typeface BOLD = Typeface.create("sans-serif", Typeface.BOLD);
    /** Picked MIR typeface (assets/fonts/<id>.ttf), null = system sans. Set by Fonts.apply() before any view is built. */
    static Typeface FONT = null;
    static void setFont(Typeface f) {
        FONT = f;
        BOLD = f != null ? Typeface.create(f, Typeface.BOLD) : Typeface.create("sans-serif", Typeface.BOLD);
    }
    static final Typeface MED = Typeface.create("sans-serif-medium", Typeface.NORMAL);

    static int color(String hex, int def) {
        try { return Color.parseColor(hex); } catch (Exception e) { return def; }
    }

    static GradientDrawable box(float radius, int fill, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(radius));
        g.setColor(fill);
        if (stroke != 0) g.setStroke(Math.max(1, dp(1)), stroke);
        return g;
    }
    static GradientDrawable card() { return box(16, CARD, LINE); }
    static GradientDrawable accent(int c, float radius) {
        GradientDrawable g = new GradientDrawable(); g.setColor(c);   // matte: flat fill
        g.setCornerRadius(dp(radius));
        return g;
    }
    static int mix(int a, int b, float t) {
        int r = (int) (Color.red(a) + (Color.red(b) - Color.red(a)) * t);
        int g = (int) (Color.green(a) + (Color.green(b) - Color.green(a)) * t);
        int bl = (int) (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * t);
        return Color.argb(255, r, g, bl);
    }
    static int alpha(int c, float a) { return Color.argb((int) (255 * a), Color.red(c), Color.green(c), Color.blue(c)); }

    static TextView text(Context c, CharSequence s, float sp, int color) {
        TextView t = new TextView(c);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setIncludeFontPadding(false);
        if (FONT != null) t.setTypeface(FONT);
        t.setText(Icons.apply(s, t.getTextSize(), color));   // [[name]] → MIR icon
        return t;
    }
    static TextView bold(Context c, CharSequence s, float sp, int color) { TextView t = text(c, s, sp, color); t.setTypeface(BOLD); return t; }
    static TextView mono(Context c, CharSequence s, float sp, int color) { TextView t = text(c, s, sp, color); t.setTypeface(MONO); return t; }
    static TextView label(Context c, String s) {
        TextView t = bold(c, s.toUpperCase(), 10.5f, DIM);
        t.setLetterSpacing(0.18f);
        return t;
    }
    static void gradientText(TextView t, int a, int b) {
        t.post(() -> {
            float w = t.getPaint().measureText(t.getText().toString());
            t.getPaint().setShader(new LinearGradient(0, 0, w, 0, a, b, Shader.TileMode.CLAMP));
            t.invalidate();
        });
    }

    static TextView chip(Context c, String s, int color) {
        TextView t = bold(c, s, 10f, 0xFF0A0A10);
        t.setLetterSpacing(0.1f);
        t.setPadding(dp(8), dp(3), dp(8), dp(3));
        t.setBackground(box(99, color, 0));
        return t;
    }

    static TextView button(Context c, String s, int color, boolean filled) {
        TextView b = bold(c, s, 12.5f, filled ? 0xFFFFFFFF : INK);
        b.setGravity(Gravity.CENTER);
        b.setLetterSpacing(0.06f);
        b.setPadding(dp(14), dp(10), dp(14), dp(10));
        b.setBackground(filled ? accent(color, 12) : box(12, CARD2, LINE2));
        b.setClickable(true);
        b.setFocusable(true);
        return b;
    }

    static LinearLayout vbox(Context c) { LinearLayout l = new LinearLayout(c); l.setOrientation(LinearLayout.VERTICAL); return l; }
    static LinearLayout hbox(Context c) {
        LinearLayout l = new LinearLayout(c); l.setOrientation(LinearLayout.HORIZONTAL); l.setGravity(Gravity.CENTER_VERTICAL); return l;
    }
    static LinearLayout.LayoutParams lp(int w, int h) { return new LinearLayout.LayoutParams(w, h); }
    static LinearLayout.LayoutParams lpw(float weight) { return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, weight); }
    static LinearLayout.LayoutParams margins(LinearLayout.LayoutParams p, int l, int t, int r, int b) {
        p.setMargins(dp(l), dp(t), dp(r), dp(b)); return p;
    }
    static View spacer(Context c, int w, int h) { View v = new View(c); v.setLayoutParams(lp(dp(w), dp(h))); return v; }
    static final int MATCH = LinearLayout.LayoutParams.MATCH_PARENT, WRAP = LinearLayout.LayoutParams.WRAP_CONTENT;

    static String icon(String kind) {
        if ("image".equals(kind)) return "[[image]]";
        if ("video".equals(kind)) return "[[video]]";
        if ("audio".equals(kind)) return "[[music]]";
        if ("text".equals(kind)) return "[[note]]";
        return "[[attach]]";
    }
    static String kindOf(String n) {
        n = n == null ? "" : n.toLowerCase();
        if (n.matches(".*\\.(png|jpe?g|webp)$")) return "image";
        if (n.matches(".*\\.(mp4|mov|webm|m4v|mkv)$")) return "video";
        if (n.matches(".*\\.(mp3|wav|flac|ogg|m4a|aac)$")) return "audio";
        if (n.matches(".*\\.(txt|md|lrc|srt|json|csv)$")) return "text";
        return "";
    }
    static String dur(double a, double b) {
        long s = Math.max(0, Math.round(b - a));
        return s < 60 ? s + "s" : (s / 60) + "m " + String.format("%02d", s % 60) + "s";
    }
}
