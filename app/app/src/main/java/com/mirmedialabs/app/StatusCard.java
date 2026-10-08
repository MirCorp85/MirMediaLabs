package com.mirmedialabs.app;

import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The mascot's status card — same as the web studio's: the model's own icon + colour, MUSE's pick, the pipeline's
 *  steps, the live stage and every tag the prompt is using. Shown while a job is queued / running; tap to hide. */
final class StatusCard extends LinearLayout {
    private final MainActivity m;
    private String sig = "";
    private TextView elapsedTv, progTv;   // live bits updated in place - no rebuild, no flicker
    private android.view.View progFill, progRest;
    private boolean hidden;
    // live ComfyUI render viewer: newest sampler preview of the running job (h3 / qimg), polled while shown
    private android.widget.ImageView livePv;
    private String liveJob = "", liveN = "";
    private android.graphics.Bitmap liveBmp;             // kept across card rebuilds (stage text changes) - no blank flash
    private final Runnable livePoll = this::pollLive;

    StatusCard(MainActivity a) {
        super(a);
        m = a;
        setOrientation(VERTICAL);
        setPadding(Ui.dp(10), Ui.dp(8), Ui.dp(10), Ui.dp(8));
        setVisibility(GONE);
        hidden = "1".equals(Prefs.str(a, "mchide", ""));
        android.animation.LayoutTransition lt = new android.animation.LayoutTransition();
        lt.enableTransitionType(android.animation.LayoutTransition.CHANGING);     // rows grow / shrink smoothly
        lt.setDuration(260);
        setLayoutTransition(lt);
    }

    /** Tap the mascot (or the card): orbit reveal — a circle wipe opening from / closing into the top corner. */
    boolean isHidden() { return hidden; }

    void toggle() {
        hidden = !hidden;
        Prefs.put(m, "mchide", hidden ? "1" : "");
        if (hidden) setVisibility(GONE);
        else {
            sig = "";
            update(last);                                  // a running job → appears through reveal(true)
        }
    }

    private android.animation.Animator anim;

    private void reveal(boolean show) {
        if (anim != null) anim.cancel();
        if (!isAttachedToWindow() || getWidth() == 0) {
            if (show) post(() -> reveal(true)); else setVisibility(INVISIBLE);
            return;
        }
        int cx = getWidth() - Ui.dp(22), cy = 0;
        float full = (float) Math.hypot(getWidth(), getHeight());
        setVisibility(VISIBLE);
        anim = android.view.ViewAnimationUtils.createCircularReveal(this, cx, cy, show ? 0 : full, show ? full : 0);
        anim.setDuration(show ? 520 : 380);
        anim.setInterpolator(new android.view.animation.PathInterpolator(0.4f, 0f, 0.2f, 1f));
        if (!show) anim.addListener(new android.animation.AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(android.animation.Animator a) { if (hidden) setVisibility(INVISIBLE); }
        });
        anim.start();
    }

    /** Glass card: model-tinted gradient, coloured edge light, deep shadow. */
    private void skin(int col) {
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(0x00000000);
        setBackground(new android.graphics.drawable.LayerDrawable(new android.graphics.drawable.Drawable[]{g}));
    }

    private void pollLive() {
        if (livePv == null || !isAttachedToWindow() || getVisibility() != VISIBLE) return;
        final android.widget.ImageView iv = livePv;
        m.api.bytes("/api/jobs/" + liveJob + "/preview?n=" + liveN, r -> {
            if (r.ok() && r.status == 200 && r.bytes != null && r.bytes.length > 0 && iv == livePv) {
                android.graphics.Bitmap b = android.graphics.BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length);
                if (b != null) { liveBmp = b; iv.setImageBitmap(b); iv.setVisibility(VISIBLE); }
                if (r.body != null) liveN = r.body;
            }
            if (iv == livePv) postDelayed(livePoll, 600);
        });
    }

    @Override protected void onDetachedFromWindow() { removeCallbacks(livePoll); super.onDetachedFromWindow(); }

    static int mix(int a, int b, float t) {
        int r = (int) (((a >> 16) & 255) * t + ((b >> 16) & 255) * (1 - t)), gg = (int) (((a >> 8) & 255) * t + ((b >> 8) & 255) * (1 - t)),
            bl = (int) ((a & 255) * t + (b & 255) * (1 - t));
        return 0xF0000000 | (r << 16) | (gg << 8) | bl;
    }

    static String icon(String model) {
        switch (model) {
            case "h3": return "film";
            case "music3": return "mic";
            case "qimg": return "image";
            case "ace": return "drum";
            case "llama": return "type";
            default: return "sparkle";
        }
    }

    static String roleIcon(String role) {
        switch (role) {
            case "image": return "image";
            case "video": return "film";
            case "song": return "mic";
            case "music": return "drum";
            case "text": return "type";
            default: return "dot";
        }
    }

    private JSONArray last = new JSONArray();

    void update(JSONArray jobs) {
        if (jobs == null) return;
        last = jobs;
        JSONObject run = null, q = null;
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject o = jobs.optJSONObject(i);
            if (run == null && "running".equals(o.optString("status"))) run = o;
            if (q == null && "queued".equals(o.optString("status"))) q = o;
        }
        JSONObject j = run != null ? run : q;
        if (j == null || hidden) removeCallbacks(livePoll);
        if (j == null) { setVisibility(GONE); sig = ""; return; }
        if (hidden) { setVisibility(GONE); return; }
        double now = System.currentTimeMillis() / 1000.0;
        String elapsed = run != null ? Ui.dur(j.optDouble("started", now), now) : "queued";
        JSONObject pg0 = j.optJSONObject("progress");
        boolean hasPg = run != null && pg0 != null && pg0.optInt("max") > 0;
        String s = j.optString("id") + j.optString("status") + j.optString("stage") + j.optString("step") + hasPg + String.valueOf(j.opt("plan"));
        if (s.equals(sig) && getVisibility() == VISIBLE) {      // same layout: just tick the timer + bar
            if (elapsedTv != null) elapsedTv.setText(elapsed);
            if (hasPg && progFill != null) {
                int pct = Math.max(1, Math.min(100, pg0.optInt("pct")));
                ((LayoutParams) progFill.getLayoutParams()).weight = pct;
                ((LayoutParams) progRest.getLayoutParams()).weight = 100 - pct;
                progFill.requestLayout();
                progTv.setText(pg0.optString("what") + "   " + pg0.optInt("value") + " / " + pg0.optInt("max"));
            }
            return;
        }
        elapsedTv = progTv = null; progFill = progRest = null;
        boolean appearing = getVisibility() != VISIBLE;
        sig = s;
        setVisibility(VISIBLE);
        removeAllViews();
        String model = j.optString("model");
        JSONObject md = m.model(model);
        int col = m.colorOf(model);
        skin(col);
        // header: model icon tile · name + step · stage · elapsed
        LinearLayout h = Ui.hbox(m);
        h.setGravity(Gravity.CENTER_VERTICAL);
        TextView ic = Ui.text(m, "[[" + icon(model) + "]]", 18, col);
        ic.setGravity(Gravity.CENTER);
        android.graphics.drawable.GradientDrawable ig = new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TL_BR, new int[]{col, col});
        ig.setCornerRadius(Ui.dp(13));
        ic.setBackground(ig);
        ic.setTextColor(0xFFFFFFFF);
        
        Icons.set(ic, "[[" + icon(model) + "]]");
        h.addView(ic, Ui.margins(Ui.lp(Ui.dp(42), Ui.dp(42)), 0, 0, 0, 4));
        LinearLayout tt = Ui.vbox(m);
        String step = CreatePage.str(j, "step");
        JSONArray plan = j.optJSONArray("plan");
        tt.addView(Ui.mono(m, md.optString("label", model) + (plan != null && plan.length() > 0 && !step.isEmpty() ? " · STEP " + step : ""), 10.5f, Ui.INK));
        String stg = CreatePage.str(j, "stage");
        TextView sv = Ui.text(m, run == null ? "waiting for the GPU" : stg.isEmpty() ? "rendering" : stg, 11.5f, Ui.DIM);
        sv.setSingleLine(true);
        sv.setEllipsize(android.text.TextUtils.TruncateAt.END);
        tt.addView(sv);
        h.addView(tt, Ui.margins(new LayoutParams(0, Ui.WRAP, 1), 9, 0, 6, 0));
        elapsedTv = Ui.mono(m, elapsed, 11, col);
        // the header already shows the timer: keep the view (patched in place) but out of sight
        elapsedTv.setVisibility(GONE);
        h.addView(elapsedTv);
        addView(h);
        removeCallbacks(livePoll);
        livePv = null;
        if (run != null && ("h3".equals(model) || "qimg".equals(model))) {
            livePv = new android.widget.ImageView(m);
            livePv.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
            livePv.setBackground(Ui.box(10, 0xFF000000, Ui.LINE2));
            livePv.setClipToOutline(true);
            if (!j.optString("id").equals(liveJob)) { liveJob = j.optString("id"); liveN = ""; liveBmp = null; }
            if (liveBmp != null) livePv.setImageBitmap(liveBmp);
            livePv.setVisibility(liveBmp != null ? VISIBLE : GONE);   // until the first frame arrives
            addView(livePv, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(170)), 0, 8, 0, 0));
            post(livePoll);
        }
        JSONObject pg = j.optJSONObject("progress");      // real engine progress: step n of max
        if (run != null && pg != null && pg.optInt("max") > 0) {
            int pct = Math.max(1, Math.min(100, pg.optInt("pct")));
            LinearLayout bar = Ui.hbox(m);
            bar.setBackground(Ui.box(3, Ui.LINE2, 0));
            android.view.View fill = new android.view.View(m);
            fill.setBackground(Ui.box(3, col, 0));
            bar.addView(fill, new LayoutParams(0, Ui.dp(5), pct));
            progFill = fill; progRest = new android.view.View(m);
            bar.addView(progRest, new LayoutParams(0, Ui.dp(5), 100 - pct));
            addView(bar, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(5)), 0, 8, 0, 0));
            progTv = Ui.mono(m, pg.optString("what") + "   " + pg.optInt("value") + " / " + pg.optInt("max"), 9.5f, Ui.FAINT);
            addView(progTv,
                    Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 3, 0, 0));
        }
        JSONObject route = j.optJSONObject("route");
        if (route != null) {
            String why = CreatePage.str(route, "why");
            addView(Ui.text(m, "[[sparkle]] MUSE chose " + CreatePage.str(route, "label") + (why.isEmpty() ? "" : " — " + why), 11, Ui.DIM),
                    Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 7, 0, 0));
        }
        if (plan != null && plan.length() > 0) {             // step pills
            StringBuilder sb = new StringBuilder();
            for (int k = 0; k < plan.length(); k++) {
                JSONObject r = plan.optJSONObject(k);
                String st = r.optString("status");
                String i2 = "done".equals(st) ? "check" : "error".equals(st) ? "close" : "running".equals(st) ? "hourglass" : roleIcon(r.optString("role"));
                sb.append(k > 0 ? "   ›   " : "").append("[[").append(i2).append("]] ").append(r.optString("label"));
            }
            addView(Ui.text(m, sb.toString(), 11.5f, Ui.INK), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 7, 0, 0));
        }
        List<String> tags = tags(j);
        if (!tags.isEmpty())
            addView(Ui.text(m, String.join("    ", tags), 10.5f, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 7, 0, 0));
    }

    private static final Pattern FLAG = Pattern.compile("--[\\w-]+(?:\\s+\\d+(?:\\.\\d+)?)?");
    private static final Pattern BPM = Pattern.compile("\\b(\\d{2,3})\\s*BPM\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern KEY = Pattern.compile("\\b([A-G][#b]?)\\s+(major|minor)\\b");

    /** "[[icon]] value" tags: the engine's live settings, flags, tempo / key, dials, LoRAs, attachments. */
    static List<String> tags(JSONObject j) {
        Set<String> seen = new LinkedHashSet<>();
        List<String> out = new ArrayList<>();
        JSONObject p = j.optJSONObject("params");
        if (p == null) p = new JSONObject();
        String m = j.optString("model");
        java.util.function.BiConsumer<String, String> add = (ic, v) -> {
            if (v == null) return;
            v = v.trim();
            if (v.isEmpty() || v.matches("(?i)auto|none|null|s") || !seen.add(v.toLowerCase())) return;
            out.add("[[" + ic + "]] " + v);
        };
        String pl = CreatePage.str(j, "pipeline"), sk = CreatePage.str(j, "skill");
        if (!pl.isEmpty()) add.accept("chain", pl); else if (!sk.isEmpty()) add.accept("sparkle", sk);
        String mode = p.optString("mode");
        switch (m) {
            case "h3":
                add.accept("wand", mode); add.accept("expand", p.optString("aspect"));
                add.accept("clock", p.optString("seconds").isEmpty() ? "" : p.optString("seconds") + "s"); add.accept("bolt", p.optString("quality"));
                break;
            case "music3":
                add.accept("clock", p.optString("duration").isEmpty() ? "" : "up to " + p.optString("duration") + "s");
                add.accept("note", "instrumental".equals(p.optString("lyrics")) ? "instrumental" : "lyrics " + p.optString("lyrics"));
                break;
            case "qimg":
                add.accept("wand", mode); add.accept("expand", p.optString("aspect")); add.accept("image", p.optString("size"));
                break;
            case "ace":
                add.accept("wand", "voice".equals(mode) ? "voice swap" : mode);
                if ("text".equals(mode)) add.accept("clock", p.optString("duration") + "s");
                add.accept("drum", p.optString("bpm").isEmpty() ? "" : p.optString("bpm") + " BPM"); add.accept("music", p.optString("key"));
                if ("voice".equals(mode)) add.accept("mic", String.format(java.util.Locale.US, "voice match %.2f", p.optDouble("voice", 0.65)));
                break;
            case "llama":
                add.accept("type", mode); add.accept("note", p.optString("length"));
                break;
        }
        String pr = j.optString("prompt");
        Matcher f = FLAG.matcher(pr);
        while (f.find()) add.accept("command", f.group());
        Matcher b = BPM.matcher(pr);
        if (b.find()) add.accept("drum", b.group(1) + " BPM");
        Matcher k = KEY.matcher(pr);
        if (k.find()) add.accept("music", k.group());
        if (pr.matches("(?is).*\\|\\s*lyrics\\s*:.*")) add.accept("note", "lyrics carried");
        JSONObject kn = j.optJSONObject("knobs");
        for (Iterator<String> it = kn == null ? null : kn.keys(); it != null && it.hasNext(); ) { String kk = it.next(); add.accept("sliders", kk + " " + kn.optString(kk)); }
        JSONArray lo = j.optJSONArray("loras");
        for (int i = 0; lo != null && i < lo.length(); i++) { JSONObject l = lo.optJSONObject(i); if (l != null) add.accept("layers", l.optString("name", l.optString("file"))); }
        JSONArray refs = j.optJSONArray("refs");
        int[] n = new int[4];
        String[] kinds = {"image", "video", "audio", "text"};
        for (int i = 0; refs != null && i < refs.length(); i++) {
            String kd = Ui.kindOf(refs.optString(i));
            for (int x = 0; x < 4; x++) if (kinds[x].equals(kd)) n[x]++;
        }
        String[] ics = {"image", "film", "music", "note"}, words = {"picture", "clip", "audio", "text"};
        for (int x = 0; x < 4; x++) if (n[x] > 0) add.accept(ics[x], n[x] + " " + words[x] + (n[x] > 1 && x != 2 ? "s" : "") + " in");
        return out.size() > 14 ? out.subList(0, 14) : out;
    }
}
