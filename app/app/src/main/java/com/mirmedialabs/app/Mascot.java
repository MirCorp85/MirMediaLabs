package com.mirmedialabs.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

/** Liquid-flask mascot (the lab icon) — same states as the web studio's #mascot: idle · queued · render · done · error · offline. */
final class Mascot extends View {
    private static final int YEL = 0xFFFFC21A, RED = 0xFFFF3B5C, GRN = 0xFF5EE08A;
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF r = new RectF();
    private String drawn = "";
    private long since;
    private final Map<String, String> lastSeen = new HashMap<>();
    private String state = "idle", title = "Ready", sub = "lab ready";
    private String flashState, flashTitle, flashSub;
    private long flashUntil;
    private JSONArray jobs = new JSONArray();
    private JSONObject status = new JSONObject();
    private final float camW, camH;

    // flask geometry (viewBox 120x130), same path as the web mascot
    private final android.graphics.Path flaskLine = new android.graphics.Path(), flaskFill = new android.graphics.Path(),
            mLine = new android.graphics.Path(), wave = new android.graphics.Path();
    private float level = 28, pct = -1;

    private void buildFlask() {
        flaskLine.moveTo(51, 10); flaskLine.lineTo(69, 10);
        flaskLine.moveTo(55, 11); flaskLine.lineTo(55, 30);
        flaskLine.cubicTo(38, 36, 18, 54, 18, 80); flaskLine.cubicTo(18, 104, 37, 118, 60, 118);
        flaskLine.cubicTo(83, 118, 102, 104, 102, 80); flaskLine.cubicTo(102, 54, 82, 36, 65, 30); flaskLine.lineTo(65, 11);
        flaskFill.moveTo(55, 11); flaskFill.lineTo(55, 30);
        flaskFill.cubicTo(38, 36, 18, 54, 18, 80); flaskFill.cubicTo(18, 104, 37, 118, 60, 118);
        flaskFill.cubicTo(83, 118, 102, 104, 102, 80); flaskFill.cubicTo(102, 54, 82, 36, 65, 30); flaskFill.lineTo(65, 11); flaskFill.close();
        mLine.moveTo(34, 102); mLine.lineTo(34, 66); mLine.lineTo(60, 90); mLine.lineTo(86, 66); mLine.lineTo(86, 102);
    }

    Mascot(Context c) {
        super(c);
        buildFlask();
        setLayerType(LAYER_TYPE_SOFTWARE, null);   // shadow-layer glow on strokes
        boolean tv = Tv.is(c);
        camW = Ui.dp(tv ? 56 : 34);
        camH = camW * 130f / 120f;
        setClickable(false);
        setFocusable(false);
    }

    @Override protected void onMeasure(int w, int h) {
        setMeasuredDimension((int) (camW + Ui.dp(Tv.is(getContext()) ? 232 : 168)), (int) (camH + Ui.dp(8)));
    }

    void update(JSONArray j, JSONObject s) {
        if (j != null) {
            jobs = j;
            for (int i = 0; i < j.length(); i++) {
                JSONObject o = j.optJSONObject(i);
                String id = o.optString("id"), st = o.optString("status"), prev = lastSeen.get(id);
                if (prev != null && !prev.equals(st) && ("running".equals(prev) || "queued".equals(prev))) {
                    if ("done".equals(st)) flash("done", "Done", MainActivity.shortName(o.optString("model")) + " saved", 6000);
                    else if ("error".equals(st)) flash("error", "Error", "render failed", 8000);
                }
                lastSeen.put(id, st);
            }
        }
        if (s != null) status = s;
        pct = -1;
        for (int i = 0; jobs != null && i < jobs.length(); i++) {
            JSONObject o = jobs.optJSONObject(i), pg = o == null ? null : o.optJSONObject("progress");
            if (o != null && "running".equals(o.optString("status")) && pg != null && pg.optInt("max") > 0) pct = pg.optInt("pct");
        }
        resolve();
        invalidate();
    }

    private void flash(String s, String t, String sb, long ms) { flashState = s; flashTitle = t; flashSub = sb; flashUntil = System.currentTimeMillis() + ms; }

    private void resolve() {
        if (System.currentTimeMillis() < flashUntil) { set(flashState, flashTitle, flashSub); return; }
        JSONObject run = null, q = null;
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject o = jobs.optJSONObject(i);
            String st = o.optString("status");
            if (run == null && "running".equals(st)) run = o;
            if (q == null && "queued".equals(st)) q = o;
        }
        JSONObject comfy = status.optJSONObject("comfy");
        if (comfy != null && !comfy.optBoolean("up", true) && run == null) { set("offline", "Offline", "gpu engine down"); return; }
        if (run != null) {
            double now = System.currentTimeMillis() / 1000.0;
            String stg = CreatePage.str(run, "stage");
            String s2 = MainActivity.shortName(run.optString("model")) + " · " + (stg.isEmpty() ? "rendering" : stg);
            set("render", "Rendering · " + Ui.dur(run.optDouble("started", now), now), s2.length() > 30 ? s2.substring(0, 30) + "…" : s2);
            return;
        }
        if (q != null) {
            JSONArray qs = status.optJSONArray("queued");
            int pos = -1;
            for (int i = 0; qs != null && i < qs.length(); i++) if (q.optString("id").equals(qs.optString(i))) pos = i + 1;
            if (pos > 0 && !status.isNull("running") && status.has("running")) pos++;
            set("queued", "Queued" + (pos > 0 ? " · #" + pos : ""), "waiting for the gpu");
            return;
        }
        if (status.has("running") && !status.isNull("running")) { set("queued", "Busy", "gpu on another job"); return; }
        set("idle", "Ready", "lab ready");
    }

    private void set(String s, String t, String sb) { state = s; title = t; sub = sb; }

    /** 55% a + 45% b — the web's color-mix(--fc 55%, --ink) for the coloured title. */
    private static int mix(int a, int b) {
        int r = (int) (((a >> 16) & 255) * .55f + ((b >> 16) & 255) * .45f), g = (int) (((a >> 8) & 255) * .55f + ((b >> 8) & 255) * .45f),
            bl = (int) ((a & 255) * .55f + (b & 255) * .45f);
        return 0xFF000000 | (r << 16) | (g << 8) | bl;
    }

    @Override protected void onDraw(Canvas c) {
        long t = System.currentTimeMillis();
        if (t % 1000 < 20) resolve();
        float sec = (t % 100000) / 1000f;
        if (!state.equals(drawn)) { drawn = state; since = t; }
        float ds = (t - since) / 1000f;

        int col = "queued".equals(state) ? YEL : "done".equals(state) ? GRN : "error".equals(state) ? RED : "offline".equals(state) ? 0xFF5A4A40 : Ui.VIO;
        boolean ren = "render".equals(state), fx = ren || "done".equals(state), off = "offline".equals(state);
        int rgb = col & 0x00FFFFFF;

        // status-tinted glass capsule (same as the web bubble): tint gradient, coloured edge, lit orb behind the flask
        float hh = getHeight() / 2f;
        r.set(0, 0, getWidth(), getHeight());
        p.setStyle(Paint.Style.FILL);
        p.setShader(new android.graphics.LinearGradient(0, 0, getWidth(), getHeight(),
                new int[]{0xE6140D0A, 0xE60E0A08, 0xE60A0807}, null, android.graphics.Shader.TileMode.CLAMP));
        c.drawRoundRect(r, hh, hh, p);
        p.setShader(new android.graphics.LinearGradient(0, 0, getWidth(), 0, 0x38000000 | rgb, 0x0A000000 | rgb, android.graphics.Shader.TileMode.CLAMP));
        c.drawRoundRect(r, hh, hh, p);
        p.setShader(null);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(Math.max(1, Ui.dp(1)));
        p.setColor(0x73000000 | rgb);
        r.inset(p.getStrokeWidth() / 2, p.getStrokeWidth() / 2);
        c.drawRoundRect(r, hh, hh, p);
        float ox = Ui.dp(4) + camW / 2f, orr = hh - Ui.dp(3);
        float pulse = ren ? (float) (0.5 + 0.5 * Math.sin(sec * 3.5)) : 0;
        p.setStyle(Paint.Style.FILL);
        p.setShader(new android.graphics.RadialGradient(ox, hh * .76f, orr, 0x4D000000 | rgb, 0x59000000, android.graphics.Shader.TileMode.CLAMP));
        c.drawCircle(ox, hh, orr, p);
        p.setShader(null);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(Ui.dp(3 + 2 * pulse)); p.setColor(((int) (36 + 30 * pulse) << 24) | rgb);
        c.drawCircle(ox, hh, orr, p);
        p.setStrokeWidth(Ui.dp(1.5f)); p.setColor(0xB3000000 | rgb);
        c.drawCircle(ox, hh, orr, p);

        // liquid flask (the lab icon, viewBox 120x130, same motion as the web #mascot): the level follows the render's
        // real progress; rendering sloshes, splashes out of the neck, spills down the sides and drips; error shakes + smokes
        float target = "done".equals(state) ? 100 : "error".equals(state) ? 6 : off ? 10 : ren ? (pct >= 0 ? pct : 35) : "queued".equals(state) ? 20 : 28;
        level += (target - level) * 0.06f;
        float k = camW / 120f;
        c.save();
        c.translate(Ui.dp(4), (getHeight() - 130 * k) / 2f);
        c.scale(k, k);
        float sh = "error".equals(state) ? (float) Math.sin(sec * 40) * 2.5f : 0;
        float bob = off ? 0 : (float) Math.sin(sec * (ren ? 6 : 1.9f)) * (ren ? 1.6f : 1.2f);
        if (fx) {                                                       // puddle at the base
            p.setStyle(Paint.Style.FILL); p.setColor(col);
            for (int i = 0; i < 2; i++) {
                float ph = (float) (0.5 + 0.5 * Math.sin(sec * 3 + i * 2));
                p.setAlpha((int) (60 + 70 * ph));
                float w = 7 + 4 * ph;
                r.set((i == 0 ? 40 : 80) - w, 122, (i == 0 ? 40 : 80) + w, 126); c.drawOval(r, p);
            }
        }
        c.translate(sh, -bob);
        c.rotate(off ? 0 : (float) Math.sin(sec * (ren ? 6 : 1.7f)) * (ren ? 1.5f : 1.2f), 60, 112);
        // liquid, clipped to the flask
        c.save();
        c.clipPath(flaskFill);
        float ly = 118 - level / 100f * 100;                            // surface height
        float tilt = off ? 0 : (float) Math.sin(sec * (ren ? 6.3f : 2.1f)) * (ren ? 12 : 5);
        c.rotate(tilt, 60, 80);
        for (int L = 0; L < 2; L++) {
            wave.reset();
            float amp = ren ? 4.5f : 2.5f, sp = (ren ? 9 : 3) * (L == 0 ? 1 : -0.7f), base = ly + L * 2;
            wave.moveTo(-20, 140);
            for (int x = -20; x <= 140; x += 4)
                wave.lineTo(x, base + (float) Math.sin(x / 7f + sec * sp + L) * amp);
            wave.lineTo(140, 140); wave.close();
            p.setStyle(Paint.Style.FILL); p.setColor(col); p.setAlpha(L == 0 ? 120 : 70);
            c.drawPath(wave, p);
        }
        if (!"error".equals(state) && !off) {                          // bubbles
            p.setAlpha(230);
            float per = ren ? .9f : 2.6f;
            for (int i = 0; i < 5; i++) {
                float ph = ((sec + i * per / 5f) % per) / per;
                float bx = 38 + i * 11 + (float) Math.sin(ph * 6 + i) * 3, by = 112 - ph * 46;
                if (by > ly) c.drawCircle(bx, by, (2.6f - i * .25f) * (.5f + ph * .7f), p);
            }
        }
        c.restore();
        // flask outline + big M, with glow
        float gl = off ? 0 : (float) (0.5 + 0.5 * Math.sin(sec * (ren ? 9 : 2.4f)));
        p.setStyle(Paint.Style.STROKE); p.setStrokeCap(Paint.Cap.ROUND); p.setStrokeJoin(Paint.Join.ROUND); p.setColor(col);
        p.setShadowLayer(2 + gl * 7, 0, 0, col);
        p.setStrokeWidth(3); c.drawPath(flaskLine, p);
        p.setStrokeWidth(5.2f); p.setAlpha((int) (215 + 40 * gl)); c.drawPath(mLine, p);
        p.clearShadowLayer(); p.setAlpha(255);
        p.setStyle(Paint.Style.FILL);
        if (ren) for (int i = 0; i < 4; i++) {                          // splash droplets out of the neck
            float ph = ((sec + i * .25f) % 1f);
            float sx = new float[]{-14, 12, 2, -6}[i], sy = new float[]{-18, -22, -28, -24}[i];
            p.setAlpha((int) (255 * (1 - ph)));
            c.drawCircle(60 + sx * ph, 10 + sy * ph, (2.4f - i * .2f) * (.4f + ph * .6f), p);
        }
        if (fx) for (int i = 0; i < 4; i++) {                           // overflow spilling down both sides + drips
            float ph = ((sec + i * .4f) % 1.6f) / 1.6f;
            int sd = i % 2 == 0 ? -1 : 1;
            float dx = ph < .45f ? 9 * ph / .45f : 9 + 4 * (ph - .45f) / .55f, dy = ph < .45f ? 6 * ph / .45f : 6 + 58 * (ph - .45f) / .55f;
            p.setAlpha((int) (255 * (ph < .1f ? ph * 10 : 1 - ph)));
            c.drawCircle(60 + sd * 6 + sd * dx, 10 + dy, i < 2 ? 2.4f : 1.8f, p);
            float dp = ((sec + i * .45f) % 1.8f) / 1.8f;
            p.setAlpha((int) (255 * (dp < .3f ? dp / .3f : 1 - dp)));
            float dxp = i % 2 == 0 ? 50 : 70, dyp = 33 + (dp > .3f ? (dp - .3f) / .7f * 18 : 0);
            r.set(dxp - 1.5f, dyp, dxp + 1.5f, dyp + Math.min(1, dp / .3f) * 8); c.drawOval(r, p);
        }
        if ("error".equals(state)) for (int i = 0; i < 3; i++) {        // smoke
            float ph = ((sec + i * .5f) % 1.5f) / 1.5f;
            p.setAlpha((int) (150 * (1 - ph)));
            c.drawCircle(60 + (i - 1) * 6 * ph, 8 - 34 * ph, (4 - i * .5f) * (.5f + ph * 1.3f), p);
        }
        c.restore();
        p.setAlpha(255);

        // label
        p.setAlpha(255);
        p.setStyle(Paint.Style.FILL);
        float tx = camW + Ui.dp(12), mid = getHeight() / 2f;
        float da = ren || "queued".equals(state) ? (float) (0.55 + 0.45 * Math.sin(sec * 5.2)) : 1;   // live status dot
        p.setColor(col); p.setAlpha((int) (255 * da));
        p.setShadowLayer(Ui.dp(3), 0, 0, col);
        c.drawCircle(tx + Ui.dp(3), mid - Ui.dp(4), Ui.dp(3), p);
        p.clearShadowLayer(); p.setAlpha(255);
        tx += Ui.dp(10);
        p.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
        p.setTextSize(Ui.dp(Tv.is(getContext()) ? 11.5f : 9f));
        p.setColor("idle".equals(state) ? Ui.INK : mix(col, Ui.INK));
        c.drawText(title.toUpperCase(), tx, mid - Ui.dp(1), p);
        p.setTypeface(Typeface.MONOSPACE);
        p.setTextSize(Ui.dp(Tv.is(getContext()) ? 10 : 8f));
        p.setColor(Ui.DIM);
        c.drawText(sub.toUpperCase(), tx, mid + Ui.dp(9), p);

        if (isShown()) postInvalidateDelayed("idle".equals(state) || "offline".equals(state) ? 50 : 33);
    }
}
