package com.mirmedialabs.app;

import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** MUSE voice — same as the web studio's: her replies are read aloud sentence by sentence as they stream in, in a
 *  natural voice made on the lab PC (Kokoro, /api/tts). Voice + speed + on/off sync through /api/miros-prefs {voice}. */
final class MuseVoice {
    static final String[] IDS = {"af_bella", "af_heart", "af_nicole", "af_sky", "bf_emma", "am_michael", "am_fenrir", "bm_george"};
    static final String[] NAMES = {"Bella · American, bright", "Heart · American, warm", "Nicole · American, soft", "Sky · American, light",
            "Emma · British, calm", "Michael · American male", "Fenrir · American male, deep", "George · British male"};
    private static final Pattern END = Pattern.compile("[.!?]+[\"')\\]]?(?=\\s)|\\n\\s*\\n");
    private static final Pattern ABBR = Pattern.compile("(?i)\\b(e\\.g|i\\.e|mr|mrs|ms|dr|vs|etc|st|no)\\.$");

    private final MainActivity m;
    private final Map<String, Integer> pos = new HashMap<>();     // job id -> chars already queued (MAX = done / history)
    private final LinkedBlockingQueue<String> q = new LinkedBlockingQueue<>();
    private boolean seeded;
    /** Replies to messages sent FROM THIS DEVICE - only those are read aloud automatically, so a PC, a phone and a TV
     *  watching the same chat never all talk at once (any device can still tap Listen). */
    private final java.util.Set<String> mine = java.util.Collections.synchronizedSet(new java.util.LinkedHashSet<>());

    void mine(String id) { if (id != null && !id.isEmpty()) mine.add(id); }
    private volatile MediaPlayer cur;
    private volatile int gen;                                    // bumped by stop(): drops sentences already fetched
    boolean on = true;
    /** The finished reply being read by its Listen button (null = none) - the button shows Stop while set. */
    volatile String replyId;
    String voice = "af_bella";
    float speed = 1f;

    MuseVoice(MainActivity a) {
        m = a;
        on = !"0".equals(Prefs.str(a, "voice_on", "1"));
        voice = Prefs.str(a, "voice_id", voice);
        try { speed = Float.parseFloat(Prefs.str(a, "voice_speed", "1")); } catch (Exception ignored) { }
        Thread t = new Thread(this::loop, "muse-voice");
        t.setDaemon(true);
        t.start();
    }

    /** Pull the shared pick (voice / speed / on) from the lab. */
    void sync() {
        m.api.get("/api/miros-prefs", r -> {
            JSONObject v = r.ok() ? r.obj().optJSONObject("voice") : null;
            if (v == null) return;
            voice = v.optString("id", voice);
            speed = (float) v.optDouble("speed", speed);
            on = v.optBoolean("on", on);
            persist(false);
            m.voiceIcon();
        });
    }

    void persist(boolean push) {
        Prefs.put(m, "voice_on", on ? "1" : "0");
        Prefs.put(m, "voice_id", voice);
        Prefs.put(m, "voice_speed", String.valueOf(speed));
        if (push) {
            try {
                m.api.post("/api/miros-prefs", Api.obj("key", "voice", "value",
                        new JSONObject().put("id", voice).put("speed", speed).put("on", on)), null);
            } catch (Exception ignored) { }
        }
    }

    void toggle() {
        on = !on;
        if (!on) stop();
        persist(true);
        m.voiceIcon();
        m.toast(on ? "MUSE will speak her replies" : "MUSE voice muted");
    }

    void stop() {
        gen++;
        if (replyId != null) { replyId = null; idle(); }
        q.clear();
        MediaPlayer p = cur;
        if (p != null) try { p.stop(); } catch (Exception ignored) { }
    }

    void say(String text, boolean force) {
        if (!on && !force) return;
        String t = text == null ? "" : text.trim();
        if (t.replaceAll("[^A-Za-z0-9]", "").length() < 2) return;
        while (t.length() > 380) { int k = t.lastIndexOf(' ', 380); if (k < 50) k = 380; q.add(t.substring(0, k)); t = t.substring(k).trim(); }
        q.add(t);
    }

    /** The Listen button: on/off. Tapping the reply being read stops it; tapping another starts that one. */
    void sayAll(String id, String text) {
        boolean was = id.equals(replyId);
        stop();
        if (was) return;
        replyId = id;
        idle();
        for (String s : take(text, 0, true).sentences) say(s, true);
    }

    boolean speaking(String id) { return id != null && id.equals(replyId); }

    private void idle() { m.runOnUiThread(() -> { if (m.create != null) m.create.paintListen(); }); }

    /** New sentences from streaming MUSE replies. History (replies already finished when the app opened) is never re-read. */
    void jobs(JSONArray js) {
        for (int i = 0; i < js.length(); i++) {
            JSONObject j = js.optJSONObject(i);
            if (j == null || !"llama".equals(j.optString("model")) || (j.has("mine") && !j.optBoolean("mine", true))) continue;
            if (!mine.contains(j.optString("id"))) continue;           // sent from another device: stay quiet
            String id = j.optString("id"), st = j.optString("status");
            boolean live = "running".equals(st) || "queued".equals(st);
            if (!seeded && !live) { pos.put(id, Integer.MAX_VALUE); continue; }
            int p = pos.containsKey(id) ? pos.get(id) : 0;
            if (p == Integer.MAX_VALUE) continue;
            if ("error".equals(st) || "cancelled".equals(st)) { pos.put(id, Integer.MAX_VALUE); continue; }
            boolean fin = "done".equals(st);
            Taken t = take(j.isNull("output") ? "" : j.optString("output"), p, fin);
            pos.put(id, fin ? Integer.MAX_VALUE : t.pos);
            for (String s : t.sentences) say(s, false);
        }
        seeded = true;
    }

    static final class Taken { final java.util.List<String> sentences = new java.util.ArrayList<>(); int pos; }

    static Taken take(String txt, int from, boolean fin) {
        Taken t = new Taken();
        String rest = from < txt.length() ? txt.substring(from) : "";
        int last = 0;
        Matcher mt = END.matcher(rest);
        while (mt.find()) {
            String seg = rest.substring(last, mt.end());
            if (ABBR.matcher(seg.trim()).find()) continue;
            if (seg.trim().length() > 1) t.sentences.add(seg);
            last = mt.end();
        }
        if (fin && !rest.substring(last).trim().isEmpty()) { t.sentences.add(rest.substring(last)); last = rest.length(); }
        t.pos = from + last;
        return t;
    }

    // ── player: fetch the next sentence while the current one plays ───────────────────────────────────
    private void loop() {
        File next = null;
        int nextGen = -1;
        while (true) {
            try {
                File f;
                int g;
                if (next != null && nextGen == gen) { f = next; g = nextGen; next = null; }
                else { String s = q.take(); g = gen; f = fetch(s); }
                if (f == null || g != gen) continue;
                String peek = q.poll();
                Thread pre = null;
                final File[] pf = new File[1];
                if (peek != null) {
                    final String ps = peek;
                    pre = new Thread(() -> pf[0] = fetch(ps));
                    pre.start();
                }
                play(f, g);
                if (pre != null) { pre.join(); next = pf[0]; nextGen = g; }
                if (next == null && q.isEmpty() && replyId != null) { replyId = null; idle(); }   // finished reading
            } catch (InterruptedException e) {
                return;
            } catch (Exception ignored) { }
        }
    }

    private File fetch(String s) {
        Api.Resp r = m.api.bytesSync("/api/tts?text=" + Api.enc(s) + "&voice=" + voice + "&speed=" + speed);
        if (!r.ok() || r.bytes == null || r.bytes.length < 100) return null;
        try {
            File f = File.createTempFile("muse", ".wav", m.getCacheDir());
            try (FileOutputStream o = new FileOutputStream(f)) { o.write(r.bytes); }
            return f;
        } catch (Exception e) { return null; }
    }

    private void play(File f, int g) throws InterruptedException {
        final Object done = new Object();
        final boolean[] fin = {false};
        AudioManager am = (AudioManager) m.getSystemService(android.content.Context.AUDIO_SERVICE);
        AudioAttributes aa = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
        AudioFocusRequest fr = null;
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            fr = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK).setAudioAttributes(aa).build();
            am.requestAudioFocus(fr);
        }
        MediaPlayer p = new MediaPlayer();
        try {
            p.setAudioAttributes(aa);
            p.setDataSource(f.getAbsolutePath());
            p.setOnCompletionListener(x -> { synchronized (done) { fin[0] = true; done.notifyAll(); } });
            p.setOnErrorListener((x, w, e) -> { synchronized (done) { fin[0] = true; done.notifyAll(); } return true; });
            p.prepare();
            if (g != gen) return;
            cur = p;
            p.start();
            synchronized (done) { while (!fin[0] && g == gen && p.isPlaying()) done.wait(200); }
        } catch (Exception ignored) {
        } finally {
            cur = null;
            try { p.release(); } catch (Exception ignored) { }
            if (fr != null && q.isEmpty()) am.abandonAudioFocusRequest(fr);
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }

    /** Settings → Look → MUSE voice: pick a voice (plays a preview), then a speed. */
    void pick() {
        int sel = java.util.Arrays.asList(IDS).indexOf(voice);
        new android.app.AlertDialog.Builder(m)
                .setTitle("MUSE voice")
                .setSingleChoiceItems(NAMES, sel, (d, k) -> {
                    voice = IDS[k];
                    on = true;
                    persist(true);
                    m.voiceIcon();
                    stop();
                    say("Hi, I'm MUSE. This is how I'll sound when I answer you.", true);
                })
                .setNeutralButton("Speed", (d, w) -> speedPick())
                .setPositiveButton("Done", null)
                .show();
    }

    private void speedPick() {
        String[] lbl = {"Relaxed · 0.9×", "Natural · 1.0×", "Brisk · 1.1×", "Fast · 1.2×"};
        float[] v = {0.9f, 1f, 1.1f, 1.2f};
        int sel = 1;
        for (int i = 0; i < v.length; i++) if (Math.abs(v[i] - speed) < .01) sel = i;
        new android.app.AlertDialog.Builder(m).setTitle("MUSE speed").setSingleChoiceItems(lbl, sel, (d, k) -> {
            speed = v[k];
            persist(true);
            stop();
            say("Is this a good speed?", true);
        }).setPositiveButton("Done", null).show();
    }
}
