package com.mirmedialabs.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** MUSE bubble — same as the web studio's: a ring dial (one segment per step), MUSE's status line, ONE live backend
 *  line (newest engine / MUSE / worker event), and the step timeline whose live step is a twisting DNA helix bar.
 *  Built once per job; update() patches the timer, ring, helix and step text in place (no rebuild, no flicker). */
final class MuseBubble extends LinearLayout {
    static final int ORG = 0xFFFF5A1F, ORG_D = 0xFFC2410C, YEL = 0xFFFFC21A;
    private final MainActivity m;
    final String id;
    private final Ring ring;
    private final TextView timer, status;
    private TextView liveSrc, liveText;
    private View liveDot;
    private final List<TextView> subs = new ArrayList<>();
    private final List<Helix> helixes = new ArrayList<>();
    private final LinearLayout steps, tags;
    private boolean fold;
    // live ComfyUI render viewer: the sampler's newest preview frame, polled while the job runs (204 = no new frame)
    private android.widget.ImageView pv;
    private String pvN = "";
    private boolean pvRun, pvBusy;
    private final Runnable pvPoll = this::pollPv;

    MuseBubble(MainActivity a, JSONObject j) {
        super(a);
        m = a;
        id = j.optString("id");
        setOrientation(VERTICAL);
        String st = j.optString("status");
        boolean live = "running".equals(st) || "queued".equals(st);
        int c = "done".equals(st) ? Ui.GRN : "error".equals(st) ? Ui.RED : YEL;

        LinearLayout h = Ui.hbox(a);
        h.setGravity(Gravity.CENTER_VERTICAL);
        ring = new Ring(a);
        h.addView(ring, Ui.lp(Ui.dp(60), Ui.dp(60)));
        LinearLayout tx = Ui.vbox(a);
        LinearLayout who = Ui.hbox(a);
        who.setGravity(Gravity.CENTER_VERTICAL);
        TextView av = Ui.text(a, "[[lab]]", 10, 0xFF0D0806);
        Icons.set(av, "[[lab]]");
        av.setGravity(Gravity.CENTER);
        av.setBackground(Ui.box(9, c, 0));
        who.addView(av, Ui.lp(Ui.dp(18), Ui.dp(18)));
        String brain = j.isNull("brain") ? "" : j.optString("brain");         // owner's cloud brain (Claude / GPT)
        TextView nm = Ui.bold(a, brain.isEmpty() ? "MUSE" : "MUSE · " + brain, 12.5f, c);
        who.addView(nm, Ui.margins(new LayoutParams(0, Ui.WRAP, 1), 6, 0, 6, 0));
        timer = Ui.mono(a, "", 11, "done".equals(st) ? Ui.GRN : "error".equals(st) ? Ui.RED : "queued".equals(st) ? YEL : ORG);
        who.addView(timer);
        tx.addView(who);
        status = Ui.text(a, "", 13.5f, Ui.INK);
        tx.addView(status, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 3, 0, 0));
        h.addView(tx, Ui.margins(new LayoutParams(0, Ui.WRAP, 1), 12, 0, 0, 0));
        addView(h);

        if (live) {                                          // the one live console line
            LinearLayout ll = Ui.hbox(a);
            ll.setGravity(Gravity.CENTER_VERTICAL);
            ll.setPadding(Ui.dp(8), Ui.dp(5), Ui.dp(8), Ui.dp(5));
            ll.setBackground(Ui.box(6, 0xFF0A0605, 0));
            liveDot = new View(a);
            liveDot.setBackground(Ui.box(3, ORG, 0));
            ll.addView(liveDot, Ui.lp(Ui.dp(6), Ui.dp(6)));
            liveSrc = Ui.mono(a, "LAB", 10.5f, ORG);
            liveSrc.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
            ll.addView(liveSrc, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 7, 0, 7, 0));
            liveText = Ui.mono(a, "queued".equals(st) ? "waiting for the GPU" : CreatePage.str(j, "stage"), 10.5f, Ui.DIM);
            liveText.setSingleLine(true);
            liveText.setEllipsize(android.text.TextUtils.TruncateAt.END);
            ll.addView(liveText, new LayoutParams(0, Ui.WRAP, 1));
            addView(ll, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 8, 0, 0));
            android.animation.ObjectAnimator pa = android.animation.ObjectAnimator.ofFloat(liveDot, "alpha", 1f, .3f);
            pa.setDuration(500); pa.setRepeatMode(android.animation.ValueAnimator.REVERSE); pa.setRepeatCount(android.animation.ValueAnimator.INFINITE); pa.start();
        }
        if (live && !"llama".equals(j.optString("model")) && !"ace".equals(j.optString("model")) && !"music3".equals(j.optString("model"))
                || live && j.optJSONArray("plan") != null) {
            pv = new android.widget.ImageView(a);
            pv.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
            pv.setBackground(Ui.box(10, 0xFF000000, Ui.LINE2));
            pv.setClipToOutline(true);
            pv.setVisibility(GONE);                          // until the first frame arrives (audio steps never send one)
            pv.setOnClickListener(v -> fullPv());
            addView(pv, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(190)), 0, 8, 0, 0));
        }

        steps = Ui.vbox(a);
        tags = Ui.hbox(a);
        if (live || "error".equals(st)) {
            JSONArray pl = plan(j);
            for (int i = 0; i < pl.length(); i++) {
                JSONObject r = pl.optJSONObject(i);
                String s = r.optString("status");
                boolean last = i == pl.length() - 1;
                LinearLayout row = Ui.hbox(a);
                Node n = new Node(a, s, i + 1, !last, "done".equals(s));
                row.addView(n, new LayoutParams(Ui.dp(22), Ui.MATCH));
                LinearLayout bd = Ui.vbox(a);
                bd.setPadding(0, Ui.dp(1), 0, Ui.dp(10));
                int lc = "done".equals(s) ? Ui.DIM : "running".equals(s) ? Ui.INK : "error".equals(s) ? Ui.RED : Ui.FAINT;
                TextView lb = "running".equals(s) || "error".equals(s) ? Ui.bold(a, r.optString("label"), 13.5f, lc) : Ui.text(a, r.optString("label"), 13.5f, lc);
                bd.addView(lb);
                TextView sub = Ui.text(a, sub(j, r), 11, Ui.FAINT);
                sub.setSingleLine(true);
                sub.setEllipsize(android.text.TextUtils.TruncateAt.END);
                sub.setTag(i);
                subs.add(sub);
                bd.addView(sub);
                if ("running".equals(s)) {
                    Helix hx = new Helix(a);
                    helixes.add(hx);
                    bd.addView(hx, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(40)), 0, 6, 0, 0));
                }
                row.addView(bd, Ui.margins(new LayoutParams(0, Ui.WRAP, 1), 10, 0, 0, 0));
                steps.addView(row, Ui.lp(Ui.MATCH, Ui.WRAP));
            }
            addView(steps, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 0));
            if (live) {
                for (String t : StatusCard.tags(j)) {
                    if (tags.getChildCount() >= 4) break;
                    TextView tv = Ui.text(a, t, 10.5f, Ui.DIM);
                    Icons.set(tv, t);
                    tv.setPadding(Ui.dp(6), Ui.dp(2), Ui.dp(6), Ui.dp(2));
                    tv.setBackground(Ui.box(6, Ui.BAR | 0xFF000000, 0));
                    tv.setSingleLine(true);
                    tags.addView(tv, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 4, 0));
                }
                if (tags.getChildCount() > 0) addView(tags, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 0, 2));
            }
        }
        if (live) {
            fold = folded().contains(id);
            applyFold();
            h.setOnClickListener(v -> {
                fold = !fold;
                java.util.Set<String> f = folded();
                if (fold) f.add(id); else f.remove(id);
                Prefs.put(m, "mbfold", android.text.TextUtils.join(",", f));
                applyFold();
            });
        }
        update(j);
    }

    private void pollPv() {
        if (!pvRun || pv == null || !isAttachedToWindow() || pvBusy) { if (pvRun) postDelayed(pvPoll, 700); return; }
        pvBusy = true;
        m.api.bytes("/api/jobs/" + id + "/preview?n=" + pvN, r -> {
            pvBusy = false;
            if (r.ok() && r.status == 200 && r.bytes != null && r.bytes.length > 0) {
                android.graphics.Bitmap b = android.graphics.BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length);
                if (b != null) { pv.setImageBitmap(b); pv.setVisibility(VISIBLE); }
                if (r.body != null) pvN = r.body;
            }
            if (pvRun) postDelayed(pvPoll, 700);
        });
    }

    /** Tap the live frame: watch it full screen (pinch to zoom). */
    private void fullPv() {
        android.graphics.drawable.Drawable d = pv.getDrawable();
        if (!(d instanceof android.graphics.drawable.BitmapDrawable)) return;
        android.app.Dialog dl = new android.app.Dialog(m, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        ZoomImageView z = new ZoomImageView(m);
        z.setImageBitmap(((android.graphics.drawable.BitmapDrawable) d).getBitmap());
        z.setOnClickListener(v -> dl.dismiss());
        dl.setContentView(z);
        dl.show();
    }

    @Override protected void onDetachedFromWindow() { removeCallbacks(pvPoll); super.onDetachedFromWindow(); }

    private java.util.Set<String> folded() {
        java.util.Set<String> s = new java.util.LinkedHashSet<>();
        for (String x : Prefs.str(m, "mbfold", "").split(",")) if (!x.isEmpty()) s.add(x);
        while (s.size() > 50) s.remove(s.iterator().next());
        return s;
    }

    private void applyFold() {
        steps.setVisibility(fold ? GONE : VISIBLE);
        tags.setVisibility(fold ? GONE : VISIBLE);
    }

    /** The job's steps (a plain job = one step named after its model). */
    private JSONArray plan(JSONObject j) {
        JSONArray pl = j.optJSONArray("plan");
        String st = j.optString("status");
        if (pl != null && pl.length() > 0) {
            if ("done".equals(st)) {
                JSONArray out = new JSONArray();
                for (int i = 0; i < pl.length(); i++) try { out.put(new JSONObject(pl.optJSONObject(i).toString()).put("status", "done")); } catch (Exception ignored) { }
                return out;
            }
            return pl;
        }
        JSONArray one = new JSONArray();
        try {
            one.put(new JSONObject().put("label", m.model(j.optString("model")).optString("label", j.optString("model")))
                    .put("model", j.optString("model")).put("status", "running".equals(st) ? "running" : st));
        } catch (Exception ignored) { }
        return one;
    }

    private String sub(JSONObject j, JSONObject r) {
        String s = r.optString("status"), md = r.has("model") ? r.optString("model") : j.optString("model");
        String nm = MainActivity.shortName(md.isEmpty() ? j.optString("model") : md);
        if ("done".equals(s)) return nm + " · done";
        if ("error".equals(s)) { String e = CreatePage.str(j, "error"); return e.isEmpty() ? "failed" : e; }
        if ("running".equals(s)) {
            JSONObject pg = j.optJSONObject("progress");
            String stg = CreatePage.str(j, "stage");
            if (pg != null && pg.optInt("max") > 0) return nm + " · " + pg.optString("what", "rendering") + " " + pg.optInt("value") + " / " + pg.optInt("max");
            return nm + " · " + (stg.isEmpty() ? "rendering" : stg);
        }
        return nm + ("queued".equals(j.optString("status")) ? " · waiting" : " · up next");
    }

    /** Patch the live bits in place. */
    void update(JSONObject j) {
        String st = j.optString("status");
        boolean was = pvRun;
        pvRun = pv != null && "running".equals(st);
        if (pvRun && !was) post(pvPoll);
        if (!pvRun && pv != null) { removeCallbacks(pvPoll); if (!"running".equals(st) && !"queued".equals(st)) pv.setVisibility(GONE); }
        double now = System.currentTimeMillis() / 1000.0;
        timer.setText("running".equals(st) ? Ui.dur(j.optDouble("started", now), now)
                : j.has("finished") && !j.isNull("finished") && !j.isNull("started") ? Ui.dur(j.optDouble("started"), j.optDouble("finished")) : "");
        JSONArray pl = plan(j);
        JSONObject pg = j.optJSONObject("progress");
        float pct = pg != null && pg.optInt("max") > 0 ? pg.optInt("pct") / 100f : -1;
        String run = "", err = "";
        int n = pl.length(), cur = n;
        float done = 0;
        int[] state = new int[n];
        for (int i = 0; i < n; i++) {
            String s = pl.optJSONObject(i).optString("status");
            state[i] = "done".equals(s) ? 2 : "error".equals(s) ? 3 : "running".equals(s) ? 1 : 0;
            if (state[i] == 2) done += 1;
            if (state[i] == 1) { done += Math.max(0, pct); run = pl.optJSONObject(i).optString("label"); cur = i + 1; }
            if (state[i] == 3) { err = pl.optJSONObject(i).optString("label"); cur = i + 1; }
        }
        ring.set(st, state, Math.max(0, pct), Math.round(done / Math.max(1, n) * 100), cur + "/" + n, queuePos(j));
        for (Helix hx : helixes) hx.pct = pct;
        for (TextView sub : subs) {
            int i = (int) sub.getTag();
            if (i < n) { String t = sub(j, pl.optJSONObject(i)); if (!t.contentEquals(sub.getText())) sub.setText(t); }
        }
        String msg;
        if ("queued".equals(st)) msg = queuePos(j) > 0 ? "Got it — you're #" + queuePos(j) + " in line" : "Got it — starting now";
        else if ("running".equals(st)) msg = "Making your " + (run.isEmpty() ? MainActivity.shortName(j.optString("model")) : run).toLowerCase(java.util.Locale.US) + " now …";
        else if ("error".equals(st)) msg = "Something went wrong" + (err.isEmpty() ? "" : " on the " + err.toLowerCase(java.util.Locale.US));
        else if ("cancelled".equals(st)) msg = "Cancelled";
        else msg = "All done — saved to your library";
        if (!msg.contentEquals(status.getText())) status.setText(msg);
    }

    private int queuePos(JSONObject j) {
        JSONArray q = m.status == null ? null : m.status.optJSONArray("queued");
        for (int i = 0; q != null && i < q.length(); i++)
            if (id.equals(q.optString(i))) return i + 1 + (m.status.isNull("running") || !m.status.has("running") ? 0 : 1);
        return 0;
    }

    /** One live backend line: src (COMFY · MUSE · LAB …), text, level (info · warn · error). */
    void setLine(String src, String text, String level) {
        if (liveText == null) return;
        int c = "error".equals(level) ? Ui.RED : "warn".equals(level) ? YEL : ORG;
        liveSrc.setText(src);
        liveSrc.setTextColor(c);
        liveDot.setBackground(Ui.box(3, c, 0));
        if (!text.contentEquals(liveText.getText())) liveText.setText(text);
    }

    // ── ring dial: one segment per step ──────────────────────────────────────────────────────────────
    static final class Ring extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF r = new RectF();
        private String st = "", center = "", sub = "";
        private int[] state = new int[0];
        private float pct;
        private int qpos;

        Ring(Context c) { super(c); }

        void set(String status, int[] s, float stepPct, int total, String step, int q) {
            st = status; state = s; pct = stepPct; qpos = q;
            center = "done".equals(st) ? "✓" : "error".equals(st) ? "!" : "queued".equals(st) ? (q > 0 ? "#" + q : "…") : total + "%";
            sub = "queued".equals(st) ? "IN LINE" : "done".equals(st) ? "" : "STEP " + step;
            invalidate();
        }

        @Override protected void onDraw(Canvas c) {
            float w = getWidth(), sw = Ui.dp(5.5f), R = w / 2f - sw;
            r.set(w / 2 - R, w / 2 - R, w / 2 + R, w / 2 + R);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(sw); p.setStrokeCap(Paint.Cap.BUTT);
            int track = Ui.LINE2 | 0xFF000000;
            if ("queued".equals(st)) {
                p.setColor(track); c.drawArc(r, 0, 360, false, p);
                p.setColor(YEL); p.setStrokeCap(Paint.Cap.ROUND);
                c.drawArc(r, (System.currentTimeMillis() % 3000) / 3000f * 360f - 90, 66, false, p);
                if (isShown()) postInvalidateOnAnimation();
            } else {
                int n = Math.max(1, state.length);
                float gap = n > 1 ? 9 : 0, seg = 360f / n;
                for (int i = 0; i < n; i++) {
                    float a0 = -90 + i * seg, len = seg - gap;
                    p.setColor(track); c.drawArc(r, a0, len, false, p);
                    int s = i < state.length ? state[i] : 0;
                    float fr = s >= 2 ? 1 : s == 1 ? pct : 0;
                    if (fr > 0) { p.setColor(s == 2 ? Ui.GRN : s == 3 ? Ui.RED : ORG); c.drawArc(r, a0, len * fr, false, p); }
                }
            }
            p.setStyle(Paint.Style.FILL);
            p.setTextAlign(Paint.Align.CENTER);
            p.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
            p.setColor("done".equals(st) ? Ui.GRN : "error".equals(st) ? Ui.RED : "queued".equals(st) ? YEL : Ui.INK);
            p.setTextSize(Ui.dp(sub.isEmpty() ? 17 : 13.5f));
            c.drawText(center, w / 2, w / 2 + (sub.isEmpty() ? Ui.dp(6) : Ui.dp(3)), p);
            if (!sub.isEmpty()) {
                p.setColor(Ui.FAINT); p.setTextSize(Ui.dp(6.5f));
                c.drawText(sub, w / 2, w / 2 + Ui.dp(13), p);
            }
        }
    }

    // ── timeline node + connector ───────────────────────────────────────────────────────────────────
    static final class Node extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final String s; private final int n; private final boolean line, lineOn;

        Node(Context c, String status, int num, boolean line, boolean lineOn) { super(c); s = status; n = num; this.line = line; this.lineOn = lineOn; }

        @Override protected void onDraw(Canvas c) {
            float cx = getWidth() / 2f, R = Ui.dp(10), cy = R;
            if (line) { p.setColor(lineOn ? Ui.GRN : Ui.LINE2 | 0xFF000000); p.setStrokeWidth(Ui.dp(2)); c.drawLine(cx, cy + R, cx, getHeight(), p); }
            boolean dn = "done".equals(s), er = "error".equals(s), rn = "running".equals(s);
            p.setStyle(Paint.Style.FILL);
            p.setColor(dn ? Ui.GRN : er ? Ui.RED : Ui.BAR | 0xFF000000);
            c.drawCircle(cx, cy, R, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(Ui.dp(2));
            float a = rn ? (float) (0.55 + 0.45 * Math.sin(System.currentTimeMillis() / 220.0)) : 1;
            p.setColor(dn ? Ui.GRN : er ? Ui.RED : rn ? ORG : Ui.LINE2 | 0xFF000000);
            p.setAlpha((int) (255 * a));
            c.drawCircle(cx, cy, R - Ui.dp(1), p);
            p.setAlpha(255);
            p.setStyle(Paint.Style.FILL);
            p.setTextAlign(Paint.Align.CENTER);
            p.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
            p.setTextSize(Ui.dp(9.5f));
            p.setColor(dn ? 0xFF0D0806 : er ? 0xFFFFFFFF : rn ? ORG : Ui.FAINT);
            c.drawText(dn ? "✓" : er ? "!" : String.valueOf(n), cx, cy + Ui.dp(3.5f), p);
            if (rn && isShown()) postInvalidateDelayed(60);
        }
    }

    // ── DNA helix progress bar: twisting strand, rungs light up as the step fills ─────────────────────
    static final class Helix extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        float pct = -1;           // -1 = unknown: a lit band travels along the strand

        Helix(Context c) { super(c); }

        @Override protected void onDraw(Canvas c) {
            float w = getWidth(), h = getHeight(), cy = h / 2, A = h / 2 - Ui.dp(6), t = (System.currentTimeMillis() % 100000) / 1000f;
            int n = Math.max(16, (int) (w / Ui.dp(9)));
            int off = Ui.LINE2 | 0xFF000000;
            p.setStrokeWidth(Ui.dp(2));
            for (int i = 0; i < n; i++) {
                float x = Ui.dp(4) + i * (w - Ui.dp(8)) / (n - 1), ph = i * .45f + t * 2.2f;
                float s = (float) Math.sin(ph), z = (float) Math.cos(ph), y1 = cy + s * A, y2 = cy - s * A;
                boolean on = pct < 0 ? ((i / (float) n + t * .25f) % 1f) < .18f : i / (float) n < pct;
                p.setStyle(Paint.Style.STROKE);
                p.setColor(on ? (z > 0 ? ORG : ORG_D) : off);
                c.drawLine(x, y1, x, y2, p);
                p.setStyle(Paint.Style.FILL);
                p.setColor(on ? YEL : 0xFF5A4334);
                c.drawCircle(x, y1, Ui.dp(z > 0 ? 3 : 2), p);
                p.setColor(on ? ORG : 0xFF4A372A);
                c.drawCircle(x, y2, Ui.dp(z < 0 ? 3 : 2), p);
            }
            if (isShown()) postInvalidateOnAnimation();
        }
    }
}
