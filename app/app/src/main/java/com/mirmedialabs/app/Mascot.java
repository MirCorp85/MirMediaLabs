package com.mirmedialabs.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

/** Broadcast-camcorder mascot — same states as the web studio's #mascot: idle · queued · render · done · error · offline. */
final class Mascot extends View {
    private static final int TEAL = 0xFF1FC8DC, YEL = 0xFFFFC21A, RED = 0xFFFF3B5C, GRN = 0xFF5EE08A, ORA = 0xFFFF5A1F;
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF r = new RectF();
    private final Path body = new Path();
    private final Map<String, String> lastSeen = new HashMap<>();
    private String state = "idle", title = "Standby", sub = "lab ready";
    private String flashState, flashTitle, flashSub;
    private long flashUntil;
    private JSONArray jobs = new JSONArray();
    private JSONObject status = new JSONObject();
    private final float camW, camH;

    Mascot(Context c) {
        super(c);
        boolean tv = Tv.is(c);
        camW = Ui.dp(tv ? 56 : 34);
        camH = camW * 56f / 80f;
        setClickable(false);
        setFocusable(false);
    }

    @Override protected void onMeasure(int w, int h) {
        setMeasuredDimension((int) (camW + Ui.dp(Tv.is(getContext()) ? 210 : 150)), (int) (camH + Ui.dp(8)));
    }

    void update(JSONArray j, JSONObject s) {
        if (j != null) {
            jobs = j;
            for (int i = 0; i < j.length(); i++) {
                JSONObject o = j.optJSONObject(i);
                String id = o.optString("id"), st = o.optString("status"), prev = lastSeen.get(id);
                if (prev != null && !prev.equals(st) && ("running".equals(prev) || "queued".equals(prev))) {
                    if ("done".equals(st)) flash("done", "Cut — done", MainActivity.shortName(o.optString("model")) + " saved", 6000);
                    else if ("error".equals(st)) flash("error", "Tape error", "render failed", 8000);
                }
                lastSeen.put(id, st);
            }
        }
        if (s != null) status = s;
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
        if (comfy != null && !comfy.optBoolean("up", true) && run == null) { set("offline", "Off air", "gpu engine down"); return; }
        if (run != null) {
            double now = System.currentTimeMillis() / 1000.0;
            String stg = CreatePage.str(run, "stage");
            String s2 = MainActivity.shortName(run.optString("model")) + " · " + (stg.isEmpty() ? "rendering" : stg);
            set("render", "Rec · " + Ui.dur(run.optDouble("started", now), now), s2.length() > 30 ? s2.substring(0, 30) + "…" : s2);
            return;
        }
        if (q != null) {
            JSONArray qs = status.optJSONArray("queued");
            int pos = -1;
            for (int i = 0; qs != null && i < qs.length(); i++) if (q.optString("id").equals(qs.optString(i))) pos = i + 1;
            if (pos > 0 && !status.isNull("running") && status.has("running")) pos++;
            set("queued", "Standby" + (pos > 0 ? " · #" + pos : ""), "waiting for the gpu");
            return;
        }
        if (status.has("running") && !status.isNull("running")) { set("queued", "Busy", "gpu on another job"); return; }
        set("idle", "Standby", "lab ready");
    }

    private void set(String s, String t, String sb) { state = s; title = t; sub = sb; }

    @Override protected void onDraw(Canvas c) {
        long t = System.currentTimeMillis();
        if (t % 1000 < 20) resolve();
        float sec = (t % 100000) / 1000f;
        boolean render = "render".equals(state), queued = "queued".equals(state);

        // glass pill behind
        p.setStyle(Paint.Style.FILL);
        p.setColor(0xB80D0806);
        r.set(0, 0, getWidth(), getHeight());
        c.drawRoundRect(r, Ui.dp(14), Ui.dp(14), p);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(Math.max(1, Ui.dp(1)));
        p.setColor(0x2EFF783C);
        c.drawRoundRect(r, Ui.dp(14), Ui.dp(14), p);

        c.save();
        float s = camW / 80f;
        float dx = 0, dy = 0;
        if ("idle".equals(state)) dy = (float) Math.sin(sec * Math.PI / 2) * -1f;
        else if ("done".equals(state)) dy = (float) Math.abs(Math.sin(sec * Math.PI / .6)) * -2f;
        else if ("error".equals(state)) dx = (float) Math.sin(sec * Math.PI * 6) * 1.5f;
        c.translate(Ui.dp(4) + dx * s, Ui.dp(4) + dy * s);
        c.scale(s, s);
        if ("offline".equals(state)) p.setAlpha(150);

        // viewfinder
        fillStroke(c, 14, 4, 36, 14, 2, 0xFF1C120D, 0xFF5A3A2A);
        fill(c, 16, 6, 34, 12, 1, 0xFF0B0503);
        if (render) { float y = 6 + (sec % 1.2f) / 1.2f * 5; fill(c, 16, y, 34, y + 1, 0, 0xCC1FC8DC); }
        // body
        body.reset();
        body.moveTo(8, 16); body.lineTo(52, 16); body.lineTo(58, 22); body.lineTo(58, 42);
        body.quadTo(58, 46, 54, 46); body.lineTo(8, 46); body.quadTo(4, 46, 4, 42); body.lineTo(4, 20); body.quadTo(4, 16, 8, 16); body.close();
        p.setStyle(Paint.Style.FILL); p.setColor(0xFF22160F); c.drawPath(body, p);
        p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(1f / s * Ui.dp(1) * .8f); p.setColor(0xFF6B4632); c.drawPath(body, p);
        fill(c, 10, 22, 32, 25, 1.5f, ORA);
        fill(c, 10, 28, 24, 30, 1, 0xFF5A3A2A);
        // REC / STBY
        boolean blinkOn = render ? (sec % 1f) < .5f : (sec % 1.6f) < 1f;
        p.setStyle(Paint.Style.FILL);
        p.setTypeface(Typeface.MONOSPACE);
        p.setTextSize(5);
        if (render && blinkOn) { p.setColor(RED); c.drawCircle(12, 38, 2.5f, p); c.drawText("REC", 17, 40, p); }
        if (queued && blinkOn) { p.setColor(YEL); c.drawText("STBY", 17, 40, p); }
        // lens barrel
        fillStroke(c, 58, 20, 68, 44, 2, 0xFF1C120D, 0xFF6B4632);
        fillStroke(c, 66, 16, 78, 48, 3, 0xFF2C1D14, 0xFF6B4632);
        p.setStyle(Paint.Style.FILL); p.setColor(0xFF0B0503); c.drawCircle(72, 32, 6, p);
        int lens = render || "error".equals(state) ? RED : queued ? YEL : "done".equals(state) ? GRN : "offline".equals(state) ? 0xFF444444 : TEAL;
        float lr = render ? 3.2f + .8f * (float) Math.cos(sec * Math.PI / .8) : 4;
        p.setColor(lens); c.drawCircle(72, 32, lr, p);
        // focus ring ticks rotate while working
        float deg = render ? sec * 330 : queued ? sec * 90 : 0;
        c.save(); c.rotate(deg, 72, 32);
        p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(1); p.setColor(0xFF6B4632);
        c.drawLine(72, 25, 72, 28, p); c.drawLine(72, 36, 72, 39, p);
        c.restore();
        c.restore();

        // label
        p.setAlpha(255);
        p.setStyle(Paint.Style.FILL);
        float tx = camW + Ui.dp(9), mid = getHeight() / 2f;
        p.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
        p.setTextSize(Ui.dp(Tv.is(getContext()) ? 11.5f : 9f));
        p.setColor(Ui.INK);
        c.drawText(title.toUpperCase(), tx, mid - Ui.dp(1), p);
        p.setTypeface(Typeface.MONOSPACE);
        p.setTextSize(Ui.dp(Tv.is(getContext()) ? 10 : 8f));
        p.setColor(Ui.DIM);
        c.drawText(sub.toUpperCase(), tx, mid + Ui.dp(9), p);

        if (isShown()) postInvalidateDelayed("idle".equals(state) ? 80 : 33);
    }

    private void fill(Canvas c, float l, float t, float rr, float b, float rad, int col) {
        p.setStyle(Paint.Style.FILL); p.setColor(col); r.set(l, t, rr, b); c.drawRoundRect(r, rad, rad, p);
    }

    private void fillStroke(Canvas c, float l, float t, float rr, float b, float rad, int col, int stroke) {
        fill(c, l, t, rr, b, rad, col);
        p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(.8f); p.setColor(stroke); c.drawRoundRect(r, rad, rad, p);
    }
}
