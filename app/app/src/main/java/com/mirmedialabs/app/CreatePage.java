package com.mirmedialabs.app;

import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

/** CHAT: model picker on top · lab chat thread (your prompts → results as bubbles) · composer pinned at the bottom. */
final class CreatePage extends LinearLayout {
    private final MainActivity m;
    private final LinearLayout modelRow, attRow, thread;
    private final ScrollView scroll;
    private final java.util.Map<String, MuseBubble> bubbles = new java.util.HashMap<>();
    private final java.util.Map<String, TextView> listenBtns = new java.util.HashMap<>();

    /** Listen buttons: "Stop" on the reply MUSE is reading, "Listen" on the rest. */
    void paintListen() {
        for (java.util.Map.Entry<String, TextView> e : listenBtns.entrySet()) {
            String t = m.voice.speaking(e.getKey()) ? "[[stop]] Stop" : "[[volume]] Listen";
            e.getValue().setText(Icons.apply(t, e.getValue().getTextSize(), Ui.AMB));
        }
    }
    private final TextView goBtn;
    private final EditText prompt;
    private String sig = "";
    String lastResult, lastModel;

    CreatePage(MainActivity a) {
        super(a);
        m = a;
        setOrientation(VERTICAL);

        if (a.wide) {                                   // tablet: the model list lives in the left column
            modelRow = Ui.vbox(a);
        } else {
            HorizontalScrollView hs = new HorizontalScrollView(a);
            hs.setHorizontalScrollBarEnabled(false);
            modelRow = Ui.hbox(a);
            modelRow.setPadding(Ui.dp(10), Ui.dp(2), Ui.dp(10), Ui.dp(5));
            hs.addView(modelRow);
            addView(hs);
        }

        scroll = new ScrollView(a);
        scroll.setFillViewport(true);
        thread = Ui.vbox(a);
        thread.setPadding(Ui.dp(12), Ui.dp(6), Ui.dp(12), Ui.dp(14));
        scroll.addView(thread);
        FrameLayout stage = new FrameLayout(a);
        stage.addView(scroll, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
        addView(stage, new LayoutParams(Ui.MATCH, 0, 1));

        LinearLayout comp = Ui.vbox(a);
        comp.setPadding(Ui.dp(10), Ui.dp(5), Ui.dp(10), Ui.dp(6));
        comp.setBackground(Ui.box(0, 0x33000000, 0));
        recipeBar = Ui.vbox(a);            // the skill / manual typed as "/id …": its steps, which attachment feeds it, its dials
        recipeBar.setPadding(Ui.dp(10), Ui.dp(7), Ui.dp(10), Ui.dp(7));
        recipeBar.setBackground(Ui.box(14, 0x14FFC21A, 0x73FFC21A));
        recipeBar.setVisibility(GONE);
        comp.addView(recipeBar, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 6));
        HorizontalScrollView as = new HorizontalScrollView(a);
        as.setHorizontalScrollBarEnabled(false);
        attRow = Ui.hbox(a);
        as.addView(attRow);
        comp.addView(as);
        LinearLayout row = Ui.hbox(a);
        row.setGravity(Gravity.BOTTOM);
        // WhatsApp-style composer: one rounded pill holding the tools + a round send / mic button beside it
        pill = Ui.hbox(a);
        pill.setGravity(Gravity.CENTER_VERTICAL);
        pill.setPadding(Ui.dp(4), Ui.dp(2), Ui.dp(4), Ui.dp(2));
        pill.setBackground(Ui.box(24, 0x66000000, Ui.LINE2));
        boolean compact = !Tv.is(a);      // phones: tools collapse into one [+] menu → more room to type
        if (compact) pill.addView(tool(a, "[[plus]]", v -> m.toolsMenu()), Ui.lp(Ui.dp(38), Ui.dp(38)));
        prompt = new EditText(a);
        prompt.setMinHeight(Ui.dp(38));
        prompt.setMaxLines(6);
        prompt.setTextColor(Ui.INK);
        prompt.setHintTextColor(Ui.FAINT);
        prompt.setTextSize(14f);
        prompt.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        prompt.setPadding(Ui.dp(6), Ui.dp(8), Ui.dp(6), Ui.dp(8));
        prompt.setBackground(null);
        prompt.setText(Prefs.str(a, "draft", ""));
        pill.addView(prompt, new LayoutParams(0, Ui.WRAP, 1));
        pill.addView(tool(a, "[[attach]]", v -> m.attachMenu()), Ui.lp(Ui.dp(38), Ui.dp(38)));
        if (!compact) {                    // TV: every tool stays one D-pad step away
            pill.addView(tool(a, "[[gear]]", v -> m.openParams(m.cur)), Ui.lp(Ui.dp(38), Ui.dp(38)));
            TextView sk = tool(a, "[[sparkle]]", v -> m.skillsMenu());   // skills · pipelines · command book
            sk.setOnLongClickListener(v -> { m.commandBook(); return true; });
            pill.addView(sk, Ui.lp(Ui.dp(38), Ui.dp(38)));
            pill.addView(tool(a, "[[layers]]", v -> m.loras.browse(Loras.roleOf(m.cur), "")), Ui.lp(Ui.dp(38), Ui.dp(38)));
        }
        recBar = Ui.hbox(a);               // shown instead of the tools while recording
        TextView dot = Ui.text(a, "●", 14, Ui.RED);
        recTime = Ui.mono(a, "0:00", 13, Ui.INK);
        recBar.addView(dot, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 8, 0));
        recBar.addView(recTime, new LayoutParams(0, Ui.WRAP, 1));
        recBar.addView(tool(a, "[[trash]]", v -> stopRec(false)), Ui.lp(Ui.dp(38), Ui.dp(38)));
        recBar.setVisibility(GONE);
        pill.addView(recBar, new LayoutParams(0, Ui.dp(38), 1));
        row.addView(pill, new LayoutParams(0, Ui.WRAP, 1));
        goBtn = Ui.button(a, "[[send]]", Ui.VIO, true);
        goBtn.setTextSize(17);
        goBtn.setPadding(0, 0, 0, 0);
        goBtn.setOnClickListener(v -> {
            if (rec != null) stopRec(true);
            else if (micMode()) startRec();
            else m.generate(prompt.getText().toString().trim());
        });
        row.addView(goBtn, Ui.margins(Ui.lp(Ui.dp(46), Ui.dp(46)), 6, 0, 0, 0));
        comp.addView(row, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 4, 0, 0));
        prompt.addTextChangedListener(new android.text.TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a1, int b1, int c1) { }
            public void onTextChanged(CharSequence s, int a1, int b1, int c1) { }
            public void afterTextChanged(android.text.Editable e) { mode(); }
        });
        addView(comp);
    }

    // ── composer: round button = mic while empty (record a sound reference), send once there's something ──
    private LinearLayout pill, recBar;
    private TextView recTime;
    private android.media.MediaRecorder rec;
    private java.io.File recFile;
    private long recT0;
    private final android.os.Handler rh = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable recTick = new Runnable() { public void run() {
        if (rec == null) return;
        long s = (System.currentTimeMillis() - recT0) / 1000;
        recTime.setText((s / 60) + ":" + String.format("%02d", s % 60) + "   recording…");
        if (s >= 300) stopRec(true); else rh.postDelayed(this, 250);
    } };

    private TextView tool(android.content.Context a, String icon, View.OnClickListener l) {
        TextView t = Ui.text(a, icon, 18, Ui.DIM);
        t.setGravity(Gravity.CENTER);
        t.setClickable(true);
        t.setFocusable(true);
        t.setBackground(Ui.box(19, 0, 0));
        t.setOnClickListener(l);
        return t;
    }

    private boolean micMode() { return prompt.getText().toString().trim().isEmpty() && m.atts.isEmpty(); }

    void mode() {
        renderRecipe();
        if (rec != null || goBtn == null) return;
        Icons.set(goBtn, micMode() ? "[[mic]]" : "[[send]]");
        goBtn.setBackground(Ui.box(23, m.accent(), 0));
    }

    // ── recipe bar ──
    private LinearLayout recipeBar;
    private boolean recipeLoading;
    private String recipeSig = "";

    void renderRecipe() {
        if (recipeBar == null || prompt == null) return;
        String p = prompt.getText().toString();
        JSONObject rc = m.recipeOf(p);
        if (rc == null && p.startsWith("/") && !recipeLoading) {        // catalog not loaded yet: fetch once, then redraw
            recipeLoading = true;
            m.withSkills(() -> { recipeLoading = false; recipeSig = ""; renderRecipe(); });
        }
        String sig = rc == null ? "" : rc.optString("id") + m.atts.size() + m.knobs.toString();
        for (JSONObject a : m.atts) sig += a.optBoolean("uploading");
        if (sig.equals(recipeSig)) return;
        recipeSig = sig;
        recipeBar.removeAllViews();
        if (rc == null) { recipeBar.setVisibility(GONE); return; }
        recipeBar.setVisibility(VISIBLE);
        boolean pipe = "pipeline".equals(rc.optString("type"));
        StringBuilder flow = new StringBuilder();
        JSONArray st = rc.optJSONArray("steps");
        for (int k = 0; st != null && k < st.length(); k++) flow.append(k > 0 ? "  →  " : "").append(st.optJSONObject(k).optString("label"));
        LinearLayout head = Ui.hbox(m);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(Ui.text(m, "[[" + (pipe ? "chain" : rc.optString("icon", "sparkle")) + "]] " + rc.optString("name"), 13, 0xFFFFC21A), new LayoutParams(0, Ui.WRAP, 1));
        if (rc.optJSONArray("knobs") != null && rc.optJSONArray("knobs").length() > 0) {
            TextView dials = Ui.text(m, "[[sliders]] Dials", 12, Ui.INK);
            dials.setPadding(Ui.dp(8), Ui.dp(4), Ui.dp(8), Ui.dp(4));
            dials.setBackground(Ui.box(12, Ui.CARD2, Ui.LINE2));
            dials.setFocusable(true);
            dials.setOnClickListener(v -> m.knobSheet(rc));
            head.addView(dials, Ui.lp(Ui.WRAP, Ui.WRAP));
        }
        recipeBar.addView(head);
        if (flow.length() > 0) recipeBar.addView(Ui.text(m, flow.toString(), 11.5f, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 3, 0, 0));
        JSONArray man = rc.optJSONArray("manual");
        for (int k = 0; man != null && k < man.length(); k++)
            recipeBar.addView(Ui.text(m, man.optString(k), 11, Ui.FAINT), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 2, 0, 0));
        // slots: which attachment feeds the manual; a missing voice → tap to record
        JSONObject need = rc.optJSONObject("need");
        JSONObject names = rc.optJSONObject("slotnames");
        for (java.util.Iterator<String> it = need == null ? null : need.keys(); it != null && it.hasNext(); ) {
            final String kind = it.next();
            java.util.List<JSONObject> have = new java.util.ArrayList<>();
            for (JSONObject a : m.atts) if (!a.optBoolean("uploading") && kind.equals(a.optString("kind"))) have.add(a);
            for (int s = 0; s < need.optInt(kind, 1); s++) {
                JSONArray nm = names == null ? null : names.optJSONArray(kind);
                String label = nm != null && s < nm.length() ? nm.optString(s) : kind;
                boolean ok = s < have.size();
                TextView slot = Ui.text(m, ok ? "[[check]] " + label + ":  " + have.get(s).optString("label")
                        : "[[" + ("audio".equals(kind) ? "mic" : "attach") + "]] " + label + " — " + ("audio".equals(kind) ? "tap here to record, or attach" : "attach one"),
                        11.5f, ok ? Ui.GRN : Ui.RED);
                if (!ok) {
                    slot.setFocusable(true);
                    slot.setOnClickListener(v -> { if ("audio".equals(kind)) startRec(); else m.attachMenu(); });
                }
                recipeBar.addView(slot, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 5, 0, 0));
            }
        }
        JSONArray ks = rc.optJSONArray("knobs");
        if (ks != null && m.knobs.length() > 0) {
            StringBuilder kv = new StringBuilder();
            for (int k = 0; k < ks.length(); k++) {
                JSONObject kb = ks.optJSONObject(k);
                if (m.knobs.has(kb.optString("k"))) kv.append(kv.length() > 0 ? "  ·  " : "").append(kb.optString("label")).append(" ").append(m.knobs.optString(kb.optString("k")));
            }
            recipeBar.addView(Ui.text(m, "[[sliders]] " + kv, 11, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 5, 0, 0));
        }
    }

    private void startRec() {
        if (m.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            m.requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, 73);
            m.toast("Allow the microphone, then tap the mic again");
            return;
        }
        try {
            recFile = new java.io.File(m.getCacheDir(), "recording_" + new java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.US).format(new java.util.Date()) + ".m4a");
            rec = android.os.Build.VERSION.SDK_INT >= 31 ? new android.media.MediaRecorder(m) : new android.media.MediaRecorder();
            rec.setAudioSource(android.media.MediaRecorder.AudioSource.MIC);
            rec.setOutputFormat(android.media.MediaRecorder.OutputFormat.MPEG_4);
            rec.setAudioEncoder(android.media.MediaRecorder.AudioEncoder.AAC);
            rec.setAudioSamplingRate(44100);
            rec.setAudioEncodingBitRate(128000);
            rec.setOutputFile(recFile.getAbsolutePath());
            rec.prepare();
            rec.start();
        } catch (Exception e) {
            if (rec != null) rec.release();
            rec = null;
            m.toast("Couldn't start recording: " + e.getMessage());
            return;
        }
        recT0 = System.currentTimeMillis();
        for (int i = 0; i < pill.getChildCount(); i++) pill.getChildAt(i).setVisibility(pill.getChildAt(i) == recBar ? VISIBLE : GONE);
        Icons.set(goBtn, "[[check]]");
        goBtn.setBackground(Ui.box(23, Ui.RED, 0));
        rh.post(recTick);
    }

    private void stopRec(boolean keep) {
        if (rec == null) return;
        boolean ok = true;
        try { rec.stop(); } catch (Exception e) { ok = false; }     // stop() throws when nothing was captured
        rec.release();
        rec = null;
        rh.removeCallbacks(recTick);
        for (int i = 0; i < pill.getChildCount(); i++) pill.getChildAt(i).setVisibility(pill.getChildAt(i) == recBar ? GONE : VISIBLE);
        boolean longEnough = System.currentTimeMillis() - recT0 > 600;
        if (keep && ok && longEnough && recFile.length() > 0) m.upload(android.net.Uri.fromFile(recFile));
        else if (keep) m.toast("Too short — hold on a little longer");
        mode();
    }

    void setPrompt(String s) { prompt.setText(s); prompt.setSelection(s.length()); prompt.requestFocus(); }
    void clearPrompt() { prompt.setText(""); Prefs.put(m, "draft", ""); }

    void render() {
        renderModels();
        renderAtts();
        mode();
        prompt.setHint(placeholder(m.cur));
    }

    static String placeholder(String k) {
        switch (k) {
            case "auto": return "Just say what you want — MUSE picks the tool…";
            case "h3": return "Ask H3 for a video…";
            case "music3": return "Ask Music 3 for a song…";
            case "qimg": return "Ask Qwen for an image…";
            case "ace": return "Ask ACE for a track…";
            case "llama": return "Talk to MUSE — ideas, lyrics, scripts…";
            default: return "Message the lab…";
        }
    }

    private String modelSig = "";

    /** Tablet: the vertical model list for the left column. */
    View modelPane() { return modelRow; }

    void renderModels() {
        JSONObject comfy = m.status.optJSONObject("comfy");
        JSONObject ready = comfy == null ? null : comfy.optJSONObject("models");
        String ms = m.cur + "|" + ready + "|" + m.models.length();
        if (ms.equals(modelSig) && modelRow.getChildCount() > 0) return;   // keeps D-pad focus on TV
        modelSig = ms;
        modelRow.removeAllViews();
        for (String k : MainActivity.ORDER) {
            JSONObject md = m.model(k);
            if (md.length() == 0) continue;
            int c = m.colorOf(k);
            boolean on = k.equals(m.cur);
            LinearLayout card = Ui.hbox(m);
            card.setPadding(Ui.dp(10), Ui.dp(6), Ui.dp(11), Ui.dp(6));
            GradientDrawable bg = new GradientDrawable();     // themed: selected = raised card + accent edge, no glow
            bg.setCornerRadius(Ui.dp(10));
            bg.setColor(on ? Ui.CARD2 : 0);
            bg.setStroke(Math.max(1, Ui.dp(1)), on ? Ui.VIO : Ui.LINE);
            card.setBackground(bg);
            View dot = new View(m);
            Object r = ready == null ? null : ready.opt(k);
            dot.setBackground(Ui.box(99, Ui.RED, 0));           // only a problem gets a marker (weights missing)
            if (Boolean.FALSE.equals(r)) card.addView(dot, Ui.margins(Ui.lp(Ui.dp(6), Ui.dp(6)), 0, 0, 6, 0));
            if (m.wide) card.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
            TextView name = Ui.bold(m, md.optString("label"), m.wide ? 12.5f : 11, on ? Ui.INK : Ui.DIM);
            name.setLetterSpacing(0.05f);
            card.addView(name, Ui.lp(Ui.WRAP, Ui.WRAP));
            card.setOnClickListener(v -> m.setModel(k));
            card.setOnLongClickListener(v -> { m.openParams(k); return true; });
            card.setFocusable(Tv.is(m));
            if (m.wide) {                                // full-width row with the model colour edge
                View edge = new View(m);
                edge.setBackground(Ui.box(2, c, 0));
                card.addView(edge, 0, Ui.margins(Ui.lp(Ui.dp(3), Ui.dp(16)), 0, 0, 9, 0));
                card.setGravity(Gravity.CENTER_VERTICAL);
                modelRow.addView(card, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 6));
            } else modelRow.addView(card, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 8, 0));
        }
    }

    void renderAtts() {
        attRow.removeAllViews();
        mode();
        JSONObject acc = m.model(m.cur).optJSONObject("accepts");
        for (int i = 0; i < m.atts.size(); i++) {
            JSONObject a = m.atts.get(i);
            final int ix = i;
            boolean up = a.optBoolean("uploading");
            String kind = a.optString("kind");
            LinearLayout chip = Ui.hbox(m);
            chip.setPadding(Ui.dp(6), Ui.dp(5), Ui.dp(4), Ui.dp(5));
            chip.setBackground(Ui.box(10, Ui.CARD2, Ui.LINE2));
            chip.setAlpha(up || (acc != null && !acc.has(kind)) ? 0.5f : 1f);
            if ("image".equals(kind)) {
                ImageView iv = new ImageView(m);
                iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
                iv.setClipToOutline(true);
                iv.setBackground(Ui.box(6, Ui.CARD, 0));
                Thumbs.load(m, iv, a.optString("url"));
                chip.addView(iv, Ui.lp(Ui.dp(26), Ui.dp(26)));
            } else chip.addView(Ui.text(m, up ? "[[hourglass]]" : Ui.icon(kind), 14, Ui.INK));
            String lbl = up ? "uploading " + a.optInt("pct") + "%" : a.optString("label");
            chip.addView(Ui.text(m, lbl.length() > 22 ? lbl.substring(0, 21) + "…" : lbl, 11.5f, Ui.INK), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 7, 0, 4, 0));
            if (!up) {
                TextView x = Ui.text(m, "[[close]]", 13, Ui.DIM);
                x.setPadding(Ui.dp(6), Ui.dp(2), Ui.dp(6), Ui.dp(2));
                x.setOnClickListener(v -> { m.atts.remove(ix); m.saveAtts(); renderAtts(); });
                chip.addView(x);
            }
            attRow.addView(chip, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 6, 6));
        }
        org.json.JSONArray ls = m.loras == null ? new org.json.JSONArray() : m.loras.sel();
        String role = Loras.roleOf(m.cur);
        for (int i = 0; i < ls.length(); i++) {        // LoRAs applied to the next renders
            org.json.JSONObject l = ls.optJSONObject(i);
            final String file = l.optString("file");
            LinearLayout chip = Ui.hbox(m);
            chip.setPadding(Ui.dp(8), Ui.dp(5), Ui.dp(4), Ui.dp(5));
            chip.setBackground(Ui.box(10, Ui.alpha(Ui.VIO, .14f), Ui.VIO));
            String can = Loras.canOf(m.cur);              // Auto: MUSE's pick decides, so nothing is greyed out
            chip.setAlpha("auto".equals(m.cur) || (can != null && (l.optString("role").isEmpty() || can.equals(l.optString("role")))) ? 1f : .45f);
            chip.addView(Ui.text(m, "[[layers]]", 13, Ui.VIO));
            String nm = l.optString("name");
            chip.addView(Ui.text(m, (nm.length() > 18 ? nm.substring(0, 17) + "…" : nm) + String.format(java.util.Locale.US, " · %.2f", l.optDouble("strength", .8)), 11.5f, Ui.INK),
                    Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 6, 0, 4, 0));
            TextView x = Ui.text(m, "[[close]]", 13, Ui.DIM);
            x.setPadding(Ui.dp(6), Ui.dp(2), Ui.dp(6), Ui.dp(2));
            x.setOnClickListener(v -> m.loras.setSel(file, null, null, null));
            chip.addView(x);
            chip.setOnClickListener(v -> m.loras.browse(Loras.roleOf(m.cur), ""));
            attRow.addView(chip, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 6, 6));
        }
    }

    /** Which LoRAs a request really used, and which it couldn't (wrong kind of model) — from the server's job record. */
    private android.view.View loraLine(JSONObject j) {
        org.json.JSONArray on = j.optJSONArray("loras"), off = j.optJSONArray("loras_skipped");
        int n = on == null ? 0 : on.length(), k = off == null ? 0 : off.length();
        if (n == 0 && k == 0) return null;
        StringBuilder s = new StringBuilder("[[layers]] ");
        for (int i = 0; i < n; i++) {
            JSONObject l = on.optJSONObject(i);
            if (l != null) s.append(i > 0 ? ", " : "LoRA ").append(l.optString("name"))
                    .append(String.format(java.util.Locale.US, " · %.2f", l.optDouble("strength", .8)));
        }
        if (k > 0) {
            s.append(n > 0 ? "  ·  " : "").append("not used for this request: ");
            for (int i = 0; i < k; i++) s.append(i > 0 ? ", " : "").append(off.optString(i));
        }
        return Ui.text(m, s.toString(), 12, Ui.DIM);
    }

    private static final java.util.regex.Pattern CMD_LINE = java.util.regex.Pattern.compile("^/[a-zA-Z0-9]{2,20}\\s+\\S.*");

    /** Lines of a MUSE reply that are ready-to-send lab commands (/video …, /image …, /lyrics …). */
    static java.util.List<String> museLines(String t) {
        java.util.List<String> out = new java.util.ArrayList<>();
        for (String raw : t.split("\n")) {
            String l = raw.trim().replaceFirst("^(?:[-*•]|\\d+[.)])\\s+", "");
            String head = l.split("\\s", 2)[0].toLowerCase(java.util.Locale.US);
            if (CMD_LINE.matcher(l).matches() && !head.equals("/help") && !head.equals("/skills") && !head.equals("/clear")) out.add(l);
        }
        return out;
    }

    /** Rebuild the chat thread from the job list (oldest at the top, newest at the bottom). */
    void renderThread(JSONArray jobs, boolean force) {
        m.voice.jobs(jobs);
        StringBuilder s = new StringBuilder();
        StringBuilder liveIds = new StringBuilder();
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject j = jobs.optJSONObject(i);
            // structure only (step / plan / files): live numbers are patched into the MUSE bubbles, no rebuild = no flicker
            s.append(j.optString("id")).append(j.optString("status")).append(str(j, "step"));
            JSONArray pl = j.optJSONArray("plan");
            for (int k = 0; pl != null && k < pl.length(); k++) s.append(pl.optJSONObject(k).optString("status").charAt(0));
            JSONArray fl = j.optJSONArray("files");
            s.append(fl == null ? 0 : fl.length()).append(';');
            if ("llama".equals(j.optString("model"))) s.append(j.optString("output").length());   // stream in
            String st = j.optString("status");
            if (("running".equals(st) || "queued".equals(st)) && i < 25) liveIds.append(liveIds.length() > 0 ? "," : "").append(j.optString("id"));
        }
        if (!force && s.toString().equals(sig) && thread.getChildCount() > 0) {
            for (int i = 0; i < jobs.length(); i++) {
                JSONObject j = jobs.optJSONObject(i);
                MuseBubble b = bubbles.get(j.optString("id"));
                if (b != null) b.update(j);
            }
            liveLines(liveIds.toString());
            return;
        }
        boolean atBottom = scroll.getChildAt(0).getBottom() - (scroll.getHeight() + scroll.getScrollY()) < Ui.dp(120);
        boolean grew = !s.toString().equals(sig);
        sig = s.toString();
        thread.removeAllViews();
        bubbles.clear();
        listenBtns.clear();
        if (jobs.length() == 0) { thread.addView(welcome()); return; }
        double now = System.currentTimeMillis() / 1000.0;
        int n = Math.min(jobs.length(), 25);
        for (int i = n - 1; i >= 0; i--) {
            JSONObject j = jobs.optJSONObject(i);
            thread.addView(userBubble(j));
            thread.addView(labBubble(j, now));
            JSONArray f = j.optJSONArray("files");
            if ("done".equals(j.optString("status")) && f != null && f.length() > 0) { lastResult = f.optString(0); lastModel = j.optString("model"); }
        }
        if (atBottom || grew) scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
        liveLines(liveIds.toString());
    }

    /** The one live backend line in each running bubble (newest engine / MUSE / worker event for that job). */
    private void liveLines(String ids) {
        if (ids.isEmpty()) return;
        m.api.get("/api/console?jobs=" + ids, r -> {
            if (!r.ok()) return;
            JSONObject lines = r.obj().optJSONObject("lines");
            if (lines == null) return;
            for (java.util.Iterator<String> it = lines.keys(); it.hasNext(); ) {
                String id = it.next();
                JSONObject ln = lines.optJSONObject(id);
                MuseBubble b = bubbles.get(id);
                if (b != null && ln != null) b.setLine(ln.optString("src"), ln.optString("text"), ln.optString("level"));
            }
        });
    }

    /** optString() turns JSON null into the text "null" (it showed up as a "null" skill chip and "STEP null") */
    static String str(JSONObject j, String k) { return j == null || j.isNull(k) ? "" : j.optString(k, ""); }

    /** chat timestamp: "7:42 PM" today, "Oct 3 · 7:42 PM" otherwise */
    static String stamp(double sec) {
        if (sec <= 0) return "";
        java.util.Date d = new java.util.Date((long) (sec * 1000));
        boolean today = android.text.format.DateUtils.isToday(d.getTime());
        return new java.text.SimpleDateFormat(today ? "h:mm a" : "MMM d · h:mm a", java.util.Locale.US).format(d);
    }

    private View welcome() {
        LinearLayout w = Ui.vbox(m);
        w.setGravity(Gravity.CENTER_HORIZONTAL);
        w.setPadding(Ui.dp(20), Ui.dp(60), Ui.dp(20), Ui.dp(20));
        ImageView logo = new ImageView(m);
        logo.setImageResource(R.mipmap.ic_launcher);
        logo.setClipToOutline(true);
        logo.setBackground(Ui.box(24, 0, 0));
        w.addView(logo, Ui.lp(Ui.dp(96), Ui.dp(96)));
        TextView t = Ui.bold(m, "MIR MEDIA LABS", 15, Ui.INK);
        t.setLetterSpacing(0.14f);
        w.addView(t, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 16, 0, 6));
        TextView sub = Ui.text(m, "Pick a model, then message the lab.\nAttach pictures, clips, songs or text with [[attach]] —\nresults come back right here.", 13, Ui.DIM);
        sub.setGravity(Gravity.CENTER);
        sub.setLineSpacing(0, 1.3f);
        w.addView(sub);
        return w;
    }

    private View userBubble(JSONObject j) {
        String model = j.optString("model");
        LinearLayout b = Ui.vbox(m);
        b.setPadding(Ui.dp(12), Ui.dp(9), Ui.dp(12), Ui.dp(10));
        boolean guest = j.has("mine") && !j.optBoolean("mine", true);   // owner viewing a guest's request
        GradientDrawable bg = new GradientDrawable();   // matte bubble
        bg.setColor(guest ? Ui.mix(Ui.BAR, 0xFF1FC8DC, 0.12f) : Ui.mix(Ui.BAR, 0xFFFF5A1F, 0.30f));
        bg.setCornerRadii(guest ? new float[]{Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(5), Ui.dp(5)}
                : new float[]{Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(5), Ui.dp(5), Ui.dp(18), Ui.dp(18)});
        b.setBackground(bg);
        LinearLayout top = Ui.hbox(m);
        top.setGravity(Gravity.CENTER_VERTICAL);
        if (guest) top.addView(Ui.chip(m, "[[user]] " + j.optString("user_name", "guest"), 0xFF1FC8DC), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 6, 0));
        boolean auto = "auto".equals(model) || j.optJSONObject("route") != null;
        top.addView(Ui.chip(m, "→ " + (auto ? "AUTO" : MainActivity.shortName(model)), auto ? m.colorOf("auto") : m.colorOf(model)), Ui.lp(Ui.WRAP, Ui.WRAP));
        top.addView(Ui.mono(m, stamp(j.optDouble("created", 0)), 10, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 0, 0));
        b.addView(top);
        String tag = str(j, "skill");
        if (tag.isEmpty() && !str(j, "pipeline").isEmpty()) tag = str(j, "pipeline");
        else if (!tag.isEmpty()) tag = "" + tag;
        if (!tag.isEmpty()) b.addView(Ui.chip(m, tag, 0xFFFFC21A), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
        String p = j.has("input") && !j.isNull("input") ? j.optString("input") : j.optString("prompt");
        TextView t = Ui.text(m, p.isEmpty() ? "(references only)" : p, 14, p.isEmpty() ? Ui.DIM : Ui.INK);
        t.setLineSpacing(0, 1.2f);
        b.addView(t, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 7, 0, 0));
        JSONArray refs = j.optJSONArray("refs");
        if (refs != null && refs.length() > 0) {
            StringBuilder rs = new StringBuilder();
            for (int k = 0; k < refs.length(); k++) {
                String n = refs.optString(k);
                String[] parts = n.split("_", 3);
                rs.append(Ui.icon(Ui.kindOf(n))).append(" ").append(parts.length == 3 ? parts[2] : n).append("   ");
            }
            b.addView(Ui.text(m, rs.toString().trim(), 11, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
        }
        LayoutParams lp = guest ? Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 56, 6) : Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 56, 6, 0, 6);
        lp.gravity = guest ? Gravity.START : Gravity.END;
        b.setLayoutParams(lp);
        return b;
    }

    private View labBubble(JSONObject j, double now) {
        final String id = j.optString("id"), st = j.optString("status"), model = j.optString("model");
        int c = m.colorOf(model);
        LinearLayout b = Ui.vbox(m);
        b.setPadding(Ui.dp(12), Ui.dp(9), Ui.dp(12), Ui.dp(11));
        b.setMinimumWidth(Ui.dp(290));               // a short stage line ("rendering") squeezed the header chip + status
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0x0EFFDCBE);
        bg.setCornerRadii(new float[]{Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(5), Ui.dp(5)});
        bg.setStroke(Math.max(1, Ui.dp(1)), Ui.LINE);
        b.setBackground(bg);
        LinearLayout top = Ui.hbox(m);
        top.addView(Ui.chip(m, m.model(model).optString("label", model), c));
        String t = "running".equals(st) ? Ui.dur(j.optDouble("started", now), now)
                : !j.isNull("finished") && !j.isNull("started") && j.has("finished") ? Ui.dur(j.optDouble("started"), j.optDouble("finished")) : "";
        int col = "running".equals(st) || "queued".equals(st) ? Ui.AMB : "done".equals(st) ? Ui.GRN : "error".equals(st) ? Ui.RED : Ui.FAINT;
        String stp = ("running".equals(st) || "queued".equals(st)) && !str(j, "pipeline").isEmpty() && !str(j, "step").isEmpty() ? "STEP " + str(j, "step") + " · " : "";
        top.addView(Ui.mono(m, stp + st.toUpperCase() + (t.isEmpty() ? "" : " · " + t), 11, col), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 0, 0));
        b.addView(top);
        // finish time on its own line: squeezed into the header row of a narrow card it wrapped into a vertical stack
        if (!j.isNull("finished") && j.has("finished"))
            b.addView(Ui.mono(m, stamp(j.optDouble("finished", 0)), 10, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 2, 3, 0, 0));
        JSONObject route = j.optJSONObject("route");          // Auto mode: what MUSE decided, and why
        if (route != null) {
            String why = str(route, "why");
            TextView rv = Ui.text(m, "[[sparkle]] MUSE chose " + str(route, "label") + (why.isEmpty() ? "" : " — " + why), 12, Ui.DIM);
            Icons.set(rv, "[[sparkle]] MUSE chose " + str(route, "label") + (why.isEmpty() ? "" : " — " + why));
            b.addView(rv, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
        }
        android.view.View loraV = loraLine(j);
        if (loraV != null) b.addView(loraV, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
        final boolean museB = !"llama".equals(model) && ("running".equals(st) || "queued".equals(st) || "error".equals(st) || "done".equals(st));
        if (museB) {                                            // MUSE bubble: ring · live line · DNA timeline
            MuseBubble mb = new MuseBubble(m, j);
            bubbles.put(id, mb);
            b.addView(mb, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 9, 0, 0));
        }
        JSONArray plan = j.optJSONArray("plan");                // the manual being followed: one line per step, live
        if (!museB && plan != null && plan.length() > 0) {
            LinearLayout pv = Ui.vbox(m);
            pv.setPadding(Ui.dp(9), Ui.dp(6), Ui.dp(9), Ui.dp(7));
            pv.setBackground(Ui.box(10, Ui.CARD2, Ui.LINE2));
            pv.addView(Ui.mono(m, "THE MANUAL MUSE IS FOLLOWING", 9.5f, Ui.FAINT));
            for (int k = 0; k < plan.length(); k++) {
                JSONObject r = plan.optJSONObject(k);
                String s = r.optString("status");
                if ("cancelled".equals(st) && !"done".equals(s)) s = "waiting";
                String ic = "done".equals(s) ? "check-circle" : "running".equals(s) ? "hourglass" : "error".equals(s) ? "x-circle" : "dot";
                int pc = "done".equals(s) ? Ui.GRN : "running".equals(s) ? Ui.AMB : "error".equals(s) ? Ui.RED : Ui.DIM;
                pv.addView(Ui.text(m, "[[" + ic + "]] " + r.optInt("n") + ". " + r.optString("label") + " — " + r.optString("does"), 12, pc),
                        Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 4, 0, 0));
            }
            b.addView(pv, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 7, 0, 0));
        }
        final boolean routed = route != null;
        LinearLayout acts = Ui.hbox(m);
        final boolean text = "llama".equals(model);      // writer model: the reply IS the result
        final String reply = j.isNull("output") ? "" : j.optString("output");
        if (text && ("running".equals(st) || "done".equals(st)) && !reply.isEmpty()) {
            TextView rt = Ui.text(m, reply + ("running".equals(st) ? " ▌" : ""), 14, Ui.INK);
            rt.setLineSpacing(0, 1.3f);
            rt.setTextIsSelectable(true);
            b.addView(rt, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 8, 0, 0));
        }
        if (text && "done".equals(st)) {
            for (String ln : museLines(reply)) {        // MUSE hand-off: ready-to-send command lines → Use
                TextView u = small("[[arrow-right]] Use: " + (ln.length() > 60 ? ln.substring(0, 59) + "…" : ln), Ui.GRN, v -> {
                    setPrompt(ln);
                    m.toast("Loaded into the message box — press send when ready");
                });
                b.addView(u, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
            }
            TextView lb = small(m.voice.speaking(id) ? "[[stop]] Stop" : "[[volume]] Listen", Ui.AMB, v -> m.voice.sayAll(id, reply));
            listenBtns.put(id, lb);
            acts.addView(lb);
            acts.addView(small("Copy", Ui.INK, v -> {
                android.content.ClipboardManager cb = (android.content.ClipboardManager) m.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                cb.setPrimaryClip(android.content.ClipData.newPlainText("Llama", reply));
                m.toast("Copied");
            }));
            acts.addView(small("Share / save", Ui.GRN, v -> {
                android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain")
                        .putExtra(android.content.Intent.EXTRA_TEXT, reply);
                m.startActivity(android.content.Intent.createChooser(i, "Share / save text"));
            }));
            acts.addView(small("Use as text ref", Ui.INK, v -> { m.attachText(reply, "llama_text"); m.toast("Attached — pick a model and send"); }));
            final String p0 = routed ? str(j, "input") : j.optString("prompt");
            acts.addView(small("↺ Again", Ui.DIM, v -> m.reuse(routed ? "auto" : model, p0, j.optJSONArray("refs"))));
        } else if ("running".equals(st) || "queued".equals(st)) {
            if (!museB) {
                String stage = str(j, "stage");
                b.addView(Ui.mono(m, "⟳ " + (stage.isEmpty() || "queued".equals(stage) ? "waiting for the GPU…" : stage), 12, Ui.AMB),
                        Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 8, 0, 0));
            }
            acts.addView(small("Cancel", Ui.RED, v -> m.cancel(id)));
        } else if ("done".equals(st)) {
            JSONArray files = j.optJSONArray("files");
            for (int k = 0; files != null && k < files.length(); k++) {
                final String fn = files.optString(k);
                String kind = Ui.kindOf(fn);
                FrameLayout media = new FrameLayout(m);
                media.setClipToOutline(true);
                media.setBackground(Ui.box(12, 0xFF000000, 0));
                if ("audio".equals(kind)) {
                    media.setBackground(MPlayer.cardBg(c, 14));
                    media.addView(MPlayer.miniAudio(m, c, MainActivity.shortName(model), fn), new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                    b.addView(media, Ui.margins(Ui.lp(Ui.dp(270), Ui.dp(76)), 0, 9, 0, 0));
                } else {
                    ImageView iv = new ImageView(m);
                    iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
                    Thumbs.load(m, iv, "/thumb/" + Api.enc(fn));
                    media.addView(iv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                    if ("video".equals(kind))
                        media.addView(MPlayer.playBadge(m, c, 54), new FrameLayout.LayoutParams(Ui.dp(54), Ui.dp(54), Gravity.CENTER));
                    b.addView(media, Ui.margins(Ui.lp(Ui.dp(250), Ui.dp(170)), 0, 9, 0, 0));
                }
                media.setOnClickListener(v -> m.openViewer(fn, model));
                LinearLayout fr = Ui.hbox(m);      // per-file actions right under each result
                fr.addView(small(" Save", Ui.GRN, v -> m.downloadFile(fn)));
                fr.addView(small(" Use as ref", Ui.INK, v -> m.useAsRef(fn)));
                b.addView(fr, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 0, 0));
            }
            final String out = j.optString("output");
            if (!out.isEmpty()) acts.addView(small("Details", Ui.DIM, v -> m.info(MainActivity.shortName(model) + " · details", out)));
            final String p = routed ? str(j, "input") : j.optString("prompt");
            acts.addView(small("↺ Again", Ui.DIM, v -> m.reuse(routed ? "auto" : model, p, j.optJSONArray("refs"))));
        } else {
            String err = str(j, "error");
            if ("error".equals(st) && !err.isEmpty() && !"null".equals(err))
                b.addView(Ui.text(m, err, 12.5f, Ui.RED), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 8, 0, 0));
            final String p = j.optString("prompt");
            acts.addView(small("↺ Try again", Ui.DIM, v -> m.reuse(model, p, j.optJSONArray("refs"))));
        }
        HorizontalScrollView actsRow = new HorizontalScrollView(m);   // narrow phones: buttons scroll sideways, never squash
        actsRow.setHorizontalScrollBarEnabled(false);
        actsRow.addView(acts);
        b.addView(actsRow, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 9, 0, 0));
        LayoutParams lp = Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 6, 40, 10);
        lp.gravity = Gravity.START;
        b.setLayoutParams(lp);
        return b;
    }

    private TextView small(String s, int color, OnClickListener l) {
        TextView t = Ui.bold(m, s, 11, color);
        t.setPadding(Ui.dp(10), Ui.dp(6), Ui.dp(10), Ui.dp(6));
        t.setBackground(Ui.box(9, Ui.CARD2, Ui.LINE));
        t.setOnClickListener(l);
        LayoutParams lp = Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 6, 0);
        t.setLayoutParams(lp);
        return t;
    }

    @Override protected void onDetachedFromWindow() { Prefs.put(m, "draft", prompt.getText().toString()); super.onDetachedFromWindow(); }
}
