package com.mirmedialabs.app;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** Proper app menus — a themed bottom sheet with a header, sections, icon rows, toggles, icon-button grids,
 *  command rows and a live search. Replaces the plain-text AlertDialog lists (settings, command book, skills,
 *  attach, Media Lab menu). Icons come from MIR ICONS. Same file (package renamed) in the standalone app. */
public final class Sheet {
    /** Colours for one surface (MirOS gold, or the current Media Lab theme). */
    public static final class Pal {
        public final int bg, card, line, ink, dim, acc;
        public Pal(int bg, int card, int line, int ink, int dim, int acc) { this.bg = bg; this.card = card; this.line = line; this.ink = ink; this.dim = dim; this.acc = acc; }
    }
    public interface Act { void run(); }
    public interface Toggle { void set(boolean on); }
    public interface Pick { void on(int i); }

    public static Pal MIROS = new Pal(0xFF15130E, 0xFF1F1C15, 0x22FFE28C, 0xFFF4F1EA, 0xFFCFC6AE, 0xFFFFD34D);

    final Activity a; final Pal p; final Dialog d; final LinearLayout body; final float den;
    private final List<View[]> searchable = new ArrayList<>();   // {row, sectionHeader} + its text in tag

    public Sheet(Activity a, String title, String icon) { this(a, title, icon, MIROS); }
    public Sheet(Activity a, String title, String icon, Pal p) {
        this.a = a; this.p = p; den = a.getResources().getDisplayMetrics().density;
        d = new Dialog(a);
        d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root = new LinearLayout(a);
        root.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(p.bg);
        bg.setCornerRadii(new float[]{dp(18), dp(18), dp(18), dp(18), 0, 0, 0, 0});
        root.setBackground(bg);
        // grab handle
        View h = new View(a);
        GradientDrawable hb = new GradientDrawable(); hb.setColor((p.dim & 0x00FFFFFF) | 0x55000000); hb.setCornerRadius(dp(3));
        h.setBackground(hb);
        LinearLayout.LayoutParams hp = new LinearLayout.LayoutParams(dp(38), dp(4)); hp.gravity = Gravity.CENTER_HORIZONTAL; hp.setMargins(0, dp(8), 0, dp(4));
        root.addView(h, hp);
        // header
        LinearLayout head = new LinearLayout(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.setPadding(dp(18), dp(6), dp(10), dp(10));
        head.addView(badge(icon, p.acc, 30), new LinearLayout.LayoutParams(dp(30), dp(30)));
        TextView t = txt(title, 16.5f, p.ink, true);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(0, -2, 1); tp.setMargins(dp(12), 0, 0, 0);
        head.addView(t, tp);
        ImageView x = icon("close", p.dim, 22);
        x.setPadding(dp(8), dp(8), dp(8), dp(8));
        x.setOnClickListener(v -> d.dismiss());
        head.addView(x, new LinearLayout.LayoutParams(dp(40), dp(40)));
        root.addView(head);
        View rule = new View(a); rule.setBackgroundColor(p.line);
        root.addView(rule, new LinearLayout.LayoutParams(-1, Math.max(1, dp(1))));
        ScrollView sv = new ScrollView(a);
        body = new LinearLayout(a);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(14), dp(6), dp(14), dp(22));
        sv.addView(body);
        root.addView(sv, new LinearLayout.LayoutParams(-1, 0, 1));
        d.setContentView(root);
        Window w = d.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new ColorDrawable(0));
            w.setGravity(Gravity.BOTTOM);
            int sw = a.getResources().getDisplayMetrics().widthPixels, sh = a.getResources().getDisplayMetrics().heightPixels;
            boolean wide = sw > dp(720);
            w.setLayout(wide ? Math.min(sw, dp(640)) : sw, (int) (sh * 0.82f));
            w.setDimAmount(0.55f);
            w.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        }
    }

    public Sheet show() { d.show(); return this; }
    public void dismiss() { d.dismiss(); }
    public LinearLayout body() { return body; }

    // ── building blocks ──
    public Sheet section(String label) {
        TextView t = txt(label.toUpperCase(), 10.5f, p.dim, true);
        t.setLetterSpacing(.14f);
        t.setPadding(dp(4), dp(16), 0, dp(6));
        body.addView(t);
        return this;
    }
    public Sheet note(String s) {
        TextView t = txt(s, 12.5f, p.dim, false);
        t.setLineSpacing(0, 1.25f);
        t.setPadding(dp(4), dp(4), dp(4), dp(4));
        body.addView(t);
        return this;
    }
    /** Icon · title · subtitle · chevron row. */
    public LinearLayout row(String icon, String title, String sub, Act act) { return row(icon, title, sub, p.acc, act); }
    public LinearLayout row(String icon, String title, String sub, int tint, Act act) {
        LinearLayout r = card();
        r.addView(badge(icon, tint, 34), new LinearLayout.LayoutParams(dp(34), dp(34)));
        LinearLayout tx = new LinearLayout(a);
        tx.setOrientation(LinearLayout.VERTICAL);
        tx.addView(txt(title, 14.5f, p.ink, true));
        if (sub != null && !sub.isEmpty()) { TextView s = txt(sub, 12, p.dim, false); s.setPadding(0, dp(2), 0, 0); tx.addView(s); }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1); lp.setMargins(dp(12), 0, dp(6), 0);
        r.addView(tx, lp);
        if (act != null) {
            r.addView(icon("chevron-right", p.dim, 18), new LinearLayout.LayoutParams(dp(18), dp(18)));
            r.setOnClickListener(v -> { d.dismiss(); act.run(); });
        }
        add(r, title + " " + (sub == null ? "" : sub));
        return r;
    }
    /** Row that keeps the sheet open (e.g. picks inside the sheet). */
    public LinearLayout rowStay(String icon, String title, String sub, Act act) {
        LinearLayout r = row(icon, title, sub, null);
        r.addView(icon("chevron-right", p.dim, 18), new LinearLayout.LayoutParams(dp(18), dp(18)));
        r.setOnClickListener(v -> act.run());
        return r;
    }
    public Switch toggle(String icon, String title, String sub, boolean on, Toggle t) {
        LinearLayout r = row(icon, title, sub, null);
        Switch s = new Switch(a);
        s.setChecked(on);
        s.setOnCheckedChangeListener((b, c) -> t.set(c));
        r.addView(s);
        r.setOnClickListener(v -> s.toggle());
        return s;
    }
    /** Monospace command + description (command book). */
    public LinearLayout cmd(String icon, String cmd, String desc, String ex, Act act) {
        LinearLayout r = card();
        r.setGravity(Gravity.TOP);
        r.addView(badge(icon, p.acc, 28), new LinearLayout.LayoutParams(dp(28), dp(28)));
        LinearLayout tx = new LinearLayout(a);
        tx.setOrientation(LinearLayout.VERTICAL);
        TextView c = txt(cmd, 13.5f, p.acc, true);
        c.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
        tx.addView(c);
        TextView ds = txt(desc, 12.5f, p.ink, false); ds.setPadding(0, dp(3), 0, 0); tx.addView(ds);
        if (ex != null && !ex.isEmpty()) { TextView e = txt("e.g. " + ex, 11.5f, p.dim, false); e.setTypeface(Typeface.MONOSPACE); e.setPadding(0, dp(3), 0, 0); tx.addView(e); }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1); lp.setMargins(dp(12), 0, 0, 0);
        r.addView(tx, lp);
        if (act != null) r.setOnClickListener(v -> { d.dismiss(); act.run(); });
        add(r, cmd + " " + desc + " " + (ex == null ? "" : ex));
        return r;
    }
    /** Grid of big icon buttons. items = {{icon, label}, …}. */
    public Sheet grid(String[][] items, int cols, Pick pick) {
        LinearLayout row = null;
        for (int i = 0; i < items.length; i++) {
            if (i % cols == 0) { row = new LinearLayout(a); body.addView(row, mlp(0, 6, 0, 0)); }
            final int k = i;
            LinearLayout b = new LinearLayout(a);
            b.setOrientation(LinearLayout.VERTICAL);
            b.setGravity(Gravity.CENTER);
            b.setPadding(dp(6), dp(14), dp(6), dp(12));
            b.setBackground(box(p.card, p.line, 14));
            b.addView(icon(items[i][0], p.acc, 26), new LinearLayout.LayoutParams(dp(26), dp(26)));
            TextView l = txt(items[i][1], 12, p.ink, true);
            l.setGravity(Gravity.CENTER);
            l.setPadding(0, dp(8), 0, 0);
            b.addView(l);
            b.setOnClickListener(v -> { d.dismiss(); pick.on(k); });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1);
            lp.setMargins(i % cols == 0 ? 0 : dp(4), 0, i % cols == cols - 1 ? 0 : dp(4), 0);
            row.addView(b, lp);
        }
        for (int k = items.length % cols; row != null && k > 0 && k < cols; k++) {
            View g = new View(a); LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, 1, 1); lp.setMargins(dp(4), 0, 0, 0); row.addView(g, lp);
        }
        return this;
    }
    /** Live filter over every row added after this call. */
    public EditText search(String hint) {
        LinearLayout r = new LinearLayout(a);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(12), 0, dp(12), 0);
        r.setBackground(box(p.card, p.line, 12));
        r.addView(icon("search", p.dim, 18), new LinearLayout.LayoutParams(dp(18), dp(18)));
        EditText e = new EditText(a);
        e.setHint(hint); e.setHintTextColor(p.dim); e.setTextColor(p.ink); e.setTextSize(14);
        e.setBackground(null); e.setSingleLine(true);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(44), 1); lp.setMargins(dp(8), 0, 0, 0);
        r.addView(e, lp);
        body.addView(r, mlp(0, 8, 0, 4));
        e.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int st, int c, int af) {}
            public void onTextChanged(CharSequence s, int st, int b, int c) {}
            public void afterTextChanged(Editable ed) {
                String q = ed.toString().trim().toLowerCase();
                for (View[] v : searchable) v[0].setVisibility(q.isEmpty() || String.valueOf(v[0].getTag()).contains(q) ? View.VISIBLE : View.GONE);
            }
        });
        return e;
    }
    public TextView button(String icon, String label, boolean primary, Act act) {
        TextView t = txt(label, 14, primary ? 0xFF1A1206 : p.ink, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(14), dp(13), dp(14), dp(13));
        t.setBackground(box(primary ? p.acc : p.card, primary ? 0 : p.line, 12));
        t.setCompoundDrawablePadding(dp(8));
        Icons.Icon ic = Icons.drawable(icon, primary ? 0xFF1A1206 : p.acc, dp(18));
        t.setCompoundDrawables(ic, null, null, null);
        t.setOnClickListener(v -> { d.dismiss(); act.run(); });
        body.addView(t, mlp(0, 10, 0, 0));
        return t;
    }
    public void add(View v) { body.addView(v, mlp(0, 6, 0, 0)); }

    // ── helpers ──
    private void add(LinearLayout r, String key) {
        r.setTag(key.toLowerCase());
        searchable.add(new View[]{r});
        body.addView(r, mlp(0, 6, 0, 0));
    }
    private LinearLayout card() {
        LinearLayout r = new LinearLayout(a);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(12), dp(11), dp(12), dp(11));
        r.setBackground(box(p.card, p.line, 14));
        r.setClickable(true);
        return r;
    }
    private View badge(String icon, int tint, int sizeDp) {
        FrameLayout f = new FrameLayout(a);
        f.setBackground(box((tint & 0x00FFFFFF) | 0x24000000, 0, 10));
        ImageView i = icon(icon, tint, (int) (sizeDp * 0.56f));
        f.addView(i, new FrameLayout.LayoutParams(dp(sizeDp * 0.56f), dp(sizeDp * 0.56f), Gravity.CENTER));
        return f;
    }
    private ImageView icon(String name, int color, float sizeDp) {
        ImageView i = new ImageView(a);
        i.setImageDrawable(Icons.drawable(name, color, dp(sizeDp)));
        return i;
    }
    private TextView txt(String s, float sp, int color, boolean bold) {
        TextView t = new TextView(a);
        t.setText(s); t.setTextSize(sp); t.setTextColor(color);
        if (bold) t.setTypeface(t.getTypeface(), Typeface.BOLD);
        return t;
    }
    private GradientDrawable box(int fill, int stroke, float r) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill); g.setCornerRadius(dp(r));
        if (stroke != 0) g.setStroke(Math.max(1, dp(1)), stroke);
        return g;
    }
    private LinearLayout.LayoutParams mlp(int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(dp(l), dp(t), dp(r), dp(b));
        return lp;
    }
    int dp(float v) { return Math.round(v * den); }
}
