package com.mirmedialabs.app;

import android.annotation.SuppressLint;
import android.app.Dialog;
import android.graphics.Color;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.audiofx.AcousticEchoCanceler;
import android.media.audiofx.NoiseSuppressor;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;

/** MUSE live voice — hands-free talk with the lab, same as the web studio (static/muse_voice.js).
 *  Mic (energy VAD + barge-in) -> /api/voice/hear (whisper on the lab PC) -> /api/generate model auto (MirAI chats or
 *  renders) -> the reply is spoken by MuseVoice (Kokoro). Her 3D look (4 styles) is the lab's muse_orb.html in a
 *  transparent WebView: the header button, the live card and the MUSE look picker. */
final class MuseLive {
    static final String[] LOOKS = {"pearl", "halo", "particles", "crystal"};
    static final String[] LOOK_NAMES = {"Liquid Pearl", "Neural Halo", "Particle Soul", "Crystal Muse"};
    private static final int SR = 16000, FRAME = 320;                      // 20 ms frames
    private static final float START = 2.6f;
    private static final int STOP_MS = 900, MIN_MS = 350, MAX_MS = 30000;

    private final MainActivity m;
    String style;
    WebView mini;                       // header button
    private WebView big;
    private FrameLayout card;
    private TextView stTxt, youTxt;
    private volatile boolean on;
    private volatile String state = "idle";
    private volatile long thinkingSince;
    private boolean prevVoiceOn;
    private Thread th;

    MuseLive(MainActivity a) {
        m = a;
        style = Prefs.str(a, "muse_style", "pearl");
    }

    void sync() {
        m.api.get("/api/miros-prefs", r -> {
            String s = r.ok() ? r.obj().optString("musestyle", "") : "";
            if (!s.isEmpty() && !s.equals(style)) setStyle(s, false);
        });
    }

    // ── the 3D look ────────────────────────────────────────────────────────────────────────────
    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    WebView orb(String look, boolean small, String st, Runnable tap) { return orb(m, look, small, st, tap); }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    static WebView orb(android.app.Activity m, String look, boolean small, String st, Runnable tap) {
        WebView w = new WebView(m);
        w.setBackgroundColor(Color.TRANSPARENT);
        w.getSettings().setJavaScriptEnabled(true);
        w.getSettings().setMediaPlaybackRequiresUserGesture(false);
        w.setVerticalScrollBarEnabled(false);
        w.setHorizontalScrollBarEnabled(false);
        w.setOverScrollMode(View.OVER_SCROLL_NEVER);
        String base = Prefs.activeUrl(m);
        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setCookie(base, "mml_key=" + Prefs.key(m) + "; path=/");
        cm.setCookie(base, "mml_dev=" + Prefs.deviceId(m) + "; path=/");
        w.addJavascriptInterface(new Object() {
            @JavascriptInterface public void tap() { if (tap != null) Api.MAIN.post(tap); }
        }, "MuseApp");
        w.loadUrl(base + "/static/muse_orb.html?style=" + look + "&state=" + st + (small ? "&small=1" : ""));
        return w;
    }

    private void js(WebView w, String code) { if (w != null) w.post(() -> w.evaluateJavascript("window.orb&&" + code, null)); }

    private void look(String st, float level) {
        String s = "starting".equals(st) ? "thinking" : st;
        String c = "(orb.state('" + s + "'),orb.level(" + level + "))";
        js(mini, c);
        js(big, c);
        js(FloatingMuse.current, c);
    }

    void setStyle(String s, boolean push) {
        boolean ok = false;
        for (String l : LOOKS) ok |= l.equals(s);
        if (!ok) return;
        style = s;
        Prefs.put(m, "muse_style", s);
        js(mini, "orb.style('" + s + "')");
        js(big, "orb.style('" + s + "')");
        js(FloatingMuse.current, "orb.style('" + s + "')");
        if (push) try {
            m.api.post("/api/miros-prefs", Api.obj("key", "musestyle", "value", s), null);
        } catch (Exception ignored) { }
    }

    /** Settings → MUSE look: the 4 live styles, tap one to pick. */
    void pickLook() {
        Dialog d = new Dialog(m);
        LinearLayout box = Ui.vbox(m);
        box.setPadding(Ui.dp(16), Ui.dp(16), Ui.dp(16), Ui.dp(16));
        box.setBackground(Ui.box(20, Ui.BG, Ui.LINE));
        box.addView(Ui.bold(m, "MUSE LOOK", 16, Ui.INK));
        box.addView(Ui.text(m, "How MUSE looks in the header and while you talk with her. Drag to spin, tap to pick.", 12, Ui.DIM));
        android.widget.CheckBox fl = new android.widget.CheckBox(m);
        fl.setText("Floating MUSE on every screen (drag her anywhere, tap to talk)");
        fl.setTextColor(Ui.INK);
        fl.setChecked(FloatingMuse.on(m));
        fl.setOnCheckedChangeListener((b, v) -> FloatingMuse.set(m, v));
        box.addView(fl);
        GridLayout g = new GridLayout(m);
        g.setColumnCount(2);
        int cell = (Math.min(m.getResources().getDisplayMetrics().widthPixels, Ui.dp(520)) - Ui.dp(64)) / 2;
        TextView[] names = new TextView[LOOKS.length];
        for (int i = 0; i < LOOKS.length; i++) {
            final int k = i;
            LinearLayout c = Ui.vbox(m);
            c.setPadding(Ui.dp(6), Ui.dp(6), Ui.dp(6), Ui.dp(8));
            c.setBackground(Ui.box(14, Ui.CARD, LOOKS[i].equals(style) ? Ui.VIO : Ui.LINE));
            Runnable pick = () -> {
                setStyle(LOOKS[k], true);
                m.toast("MUSE look: " + LOOK_NAMES[k]);
                for (int j = 0; j < names.length; j++) ((View) names[j].getParent()).setBackground(Ui.box(14, Ui.CARD, j == k ? Ui.VIO : Ui.LINE));
            };
            c.addView(orb(LOOKS[i], false, LOOKS[i].equals(style) ? "speaking" : "listening", pick), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, cell - Ui.dp(30)));
            names[i] = Ui.bold(m, LOOK_NAMES[i], 13, Ui.INK);
            names[i].setGravity(Gravity.CENTER);
            c.addView(names[i]);
            c.setOnClickListener(v -> pick.run());
            GridLayout.LayoutParams lp = new GridLayout.LayoutParams();
            lp.width = cell;
            lp.setMargins(Ui.dp(4), Ui.dp(8), Ui.dp(4), 0);
            g.addView(c, lp);
        }
        box.addView(g);
        d.setContentView(box);
        if (d.getWindow() != null) d.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));
        d.setOnDismissListener(x -> destroyAll(g));
        d.show();
    }

    private static void destroyAll(ViewGroup g) {
        for (int i = 0; i < g.getChildCount(); i++) {
            View v = g.getChildAt(i);
            if (v instanceof WebView) ((WebView) v).destroy();
            else if (v instanceof ViewGroup) destroyAll((ViewGroup) v);
        }
    }

    // ── live conversation ──────────────────────────────────────────────────────────────────────
    void toggle() { if (on) stop(); else start(); }

    void start() {
        if (on) return;
        if (m.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            m.requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, 74);
            return;
        }
        on = true;
        prevVoiceOn = m.voice.on;
        m.voice.on = true;                 // MUSE always answers out loud while live
        showCard();
        set("starting");
        m.api.post("/api/voice/warm", null, r -> { if (!r.ok()) set("error", r.err()); });
        th = new Thread(this::loop, "muse-live");
        th.start();
    }

    void stop() {
        on = false;
        m.voice.on = prevVoiceOn;
        if (card != null) {
            ((ViewGroup) card.getParent()).removeView(card);
            if (big != null) big.destroy();
            big = null;
            card = null;
        }
        look("idle", 0);
    }

    private void showCard() {
        card = new FrameLayout(m);
        LinearLayout v = Ui.vbox(m);
        v.setPadding(Ui.dp(12), Ui.dp(8), Ui.dp(12), Ui.dp(12));
        v.setBackground(Ui.box(20, Ui.alpha(Ui.BG, .94f), Ui.LINE));
        big = orb(style, false, "thinking", null);
        big.setWebViewClient(new android.webkit.WebViewClient() {     // the page loads after the first state change
            @Override public void onPageFinished(WebView v, String u) { look(state, 0); }
        });
        v.addView(big, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(170)));
        LinearLayout row = Ui.hbox(m);
        row.addView(Ui.bold(m, "MUSE  ", 15, Ui.INK));
        stTxt = Ui.text(m, "starting…", 12, Ui.DIM);
        row.addView(stTxt, Ui.lpw(1));
        TextView x = Ui.text(m, "[[close]]", 18, Ui.DIM);
        Icons.set(x, "[[close]]");
        x.setPadding(Ui.dp(10), Ui.dp(4), Ui.dp(4), Ui.dp(4));
        x.setOnClickListener(z -> stop());
        row.addView(x);
        v.addView(row);
        youTxt = Ui.text(m, "", 13, Ui.INK);
        youTxt.setPadding(0, Ui.dp(6), 0, 0);
        v.addView(youTxt);
        v.addView(Ui.text(m, "Just talk — I'll answer out loud. Talk over me to interrupt. Say \"bye\" to end.", 11, Ui.DIM));
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(Math.min(Ui.dp(360), m.getResources().getDisplayMetrics().widthPixels - Ui.dp(24)),
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END);
        lp.setMargins(0, Ui.dp(64), Ui.dp(12), 0);
        card.addView(v, lp);
        m.addContentView(card, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        card.setClickable(false);
    }

    private static final java.util.Map<String, String> LABEL = new java.util.HashMap<>();
    static {
        LABEL.put("starting", "starting…"); LABEL.put("listening", "listening"); LABEL.put("hearing", "hearing you…");
        LABEL.put("thinking", "thinking…"); LABEL.put("speaking", "speaking"); LABEL.put("error", "problem");
    }

    private void set(String st) { set(st, null); }
    private void set(String st, String msg) {
        if (st.equals(state) && msg == null) return;
        state = st;
        if ("thinking".equals(st)) thinkingSince = System.currentTimeMillis();
        look(st, 0);
        Api.MAIN.post(() -> { if (stTxt != null) stTxt.setText(msg != null ? msg : LABEL.containsKey(st) ? LABEL.get(st) : st); });
    }

    @SuppressLint("MissingPermission")
    private void loop() {
        int min = Math.max(AudioRecord.getMinBufferSize(SR, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT), FRAME * 8);
        AudioRecord rec;
        try {
            rec = new AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, SR, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min);
            if (AcousticEchoCanceler.isAvailable()) { AcousticEchoCanceler e = AcousticEchoCanceler.create(rec.getAudioSessionId()); if (e != null) e.setEnabled(true); }
            if (NoiseSuppressor.isAvailable()) { NoiseSuppressor n = NoiseSuppressor.create(rec.getAudioSessionId()); if (n != null) n.setEnabled(true); }
            rec.startRecording();
        } catch (Exception e) {
            set("error", "couldn't open the microphone");
            return;
        }
        short[] buf = new short[FRAME];
        float floor = .008f;
        boolean talking = false;
        long startAt = 0, quietAt = 0, lastLook = 0;
        ByteArrayOutputStream pcm = new ByteArrayOutputStream();
        if ("starting".equals(state)) set("listening");
        try {
            while (on) {
                int n = rec.read(buf, 0, FRAME);
                if (n <= 0) continue;
                double s = 0;
                for (int i = 0; i < n; i++) { double v = buf[i] / 32768.0; s += v * v; }
                float r = (float) Math.sqrt(s / n);
                long now = System.currentTimeMillis();
                boolean speaking = m.voice.busy();
                float th = Math.max(.012f, floor * START) * (speaking ? 2.2f : 1f);   // her voice leaks back: stricter
                if (!talking) {
                    if (r < th) floor = floor * .995f + r * .005f;
                    if (r > th) {
                        talking = true; startAt = now; quietAt = 0; pcm.reset();
                        if (speaking) m.voice.stop();                              // barge-in
                        set("hearing");
                    } else if (!"thinking".equals(state) || now - thinkingSince > 90000) {
                        if (!"error".equals(state)) set(speaking ? "speaking" : "listening");
                    } else if (speaking) set("speaking");
                }
                if (talking) {
                    for (int i = 0; i < n; i++) { pcm.write(buf[i] & 0xff); pcm.write((buf[i] >> 8) & 0xff); }
                    if (r > th * .7f) quietAt = 0; else if (quietAt == 0) quietAt = now;
                    if (now - lastLook > 60) { look("hearing", Math.min(1f, r * 14)); lastLook = now; }
                    if ((quietAt > 0 && now - quietAt > STOP_MS) || now - startAt > MAX_MS) {
                        talking = false;
                        long ms = (quietAt > 0 ? quietAt : now) - startAt;
                        if (ms < MIN_MS) set("listening");
                        else send(wav(pcm.toByteArray()));
                    }
                }
            }
        } finally {
            try { rec.stop(); } catch (Exception ignored) { }
            rec.release();
        }
    }

    private static byte[] wav(byte[] pcm) {
        ByteArrayOutputStream o = new ByteArrayOutputStream(pcm.length + 44);
        int br = SR * 2;
        byte[] h = {'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ', 16, 0, 0, 0, 1, 0, 1, 0,
                (byte) SR, (byte) (SR >> 8), (byte) (SR >> 16), 0, (byte) br, (byte) (br >> 8), (byte) (br >> 16), 0, 2, 0, 16, 0,
                'd', 'a', 't', 'a', 0, 0, 0, 0};
        int len = pcm.length;
        h[4] = (byte) (len + 36); h[5] = (byte) ((len + 36) >> 8); h[6] = (byte) ((len + 36) >> 16); h[7] = (byte) ((len + 36) >> 24);
        h[40] = (byte) len; h[41] = (byte) (len >> 8); h[42] = (byte) (len >> 16); h[43] = (byte) (len >> 24);
        o.write(h, 0, 44);
        o.write(pcm, 0, len);
        return o.toByteArray();
    }

    private void send(byte[] wav) {
        set("thinking", "listening back…");
        Api.Resp r = m.api.postAudioSync("/api/voice/hear", wav);
        if (!on) return;
        if (!r.ok()) { set("error", r.err()); return; }
        String t = r.obj().optString("text", "").trim();
        if (t.isEmpty()) { set("listening"); return; }
        Api.MAIN.post(() -> { if (youTxt != null) youTxt.setText("“" + t + "”"); });
        String lc = t.toLowerCase().replaceAll("[.!?]+$", "");
        if (lc.matches("(bye|goodbye|bye muse|end (the )?conversation|that'?s all|stop listening)")) {
            m.voice.say("Okay, talk soon.", true);
            Api.MAIN.post(this::stop);
            return;
        }
        if (lc.matches("(stop|quiet|shush|be quiet)")) { m.voice.stop(); set("listening"); return; }
        set("thinking");
        JSONObject body = Api.obj("model", "auto", "prompt", t);
        try { body.put("session", Sessions.id); } catch (Exception ignored) { }
        Api.MAIN.post(() -> m.api.post("/api/generate", body, g -> {
            if (!g.ok()) {
                m.voice.say(g.err().contains("still working") ? "I'm still on your last request. Give me a moment." : "Sorry, that didn't go through.", true);
                set("listening");
                return;
            }
            m.voice.mine(g.obj().optString("id"));
            m.poll();
        }));
    }
}
