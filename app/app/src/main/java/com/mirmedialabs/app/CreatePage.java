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
    final Mascot mascot;
    private final TextView goBtn;
    private final EditText prompt;
    private String sig = "";
    String lastResult, lastModel;

    CreatePage(MainActivity a) {
        super(a);
        m = a;
        setOrientation(VERTICAL);

        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        modelRow = Ui.hbox(a);
        modelRow.setPadding(Ui.dp(10), Ui.dp(2), Ui.dp(10), Ui.dp(5));
        hs.addView(modelRow);
        addView(hs);

        scroll = new ScrollView(a);
        scroll.setFillViewport(true);
        thread = Ui.vbox(a);
        thread.setPadding(Ui.dp(12), Ui.dp(6), Ui.dp(12), Ui.dp(Tv.is(a) ? 60 : 44));
        scroll.addView(thread);
        FrameLayout stage = new FrameLayout(a);
        stage.addView(scroll, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
        mascot = new Mascot(a);   // broadcast cam, bottom-left of the chat — mirrors the lab live
        FrameLayout.LayoutParams ml = new FrameLayout.LayoutParams(Ui.WRAP, Ui.WRAP, Gravity.BOTTOM | Gravity.START);
        ml.setMargins(Ui.dp(6), 0, 0, Ui.dp(4));
        stage.addView(mascot, ml);
        addView(stage, new LayoutParams(Ui.MATCH, 0, 1));

        LinearLayout comp = Ui.vbox(a);
        comp.setPadding(Ui.dp(10), Ui.dp(5), Ui.dp(10), Ui.dp(6));
        comp.setBackground(Ui.box(0, 0x33000000, 0));
        HorizontalScrollView as = new HorizontalScrollView(a);
        as.setHorizontalScrollBarEnabled(false);
        attRow = Ui.hbox(a);
        as.addView(attRow);
        comp.addView(as);
        LinearLayout row = Ui.hbox(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        boolean compact = !Tv.is(a);      // phones: tools collapse into one [+] menu → more room to type
        TextView more = Ui.button(a, "[[plus]]", Ui.VIO, false);
        more.setTextSize(15);
        more.setPadding(0, 0, 0, 0);
        more.setOnClickListener(v -> m.toolsMenu());
        if (compact) row.addView(more, Ui.margins(Ui.lp(Ui.dp(36), Ui.dp(36)), 0, 0, 6, 0));
        TextView clip = Ui.button(a, "[[attach]]", Ui.VIO, false);
        clip.setTextSize(14);
        clip.setPadding(0, 0, 0, 0);
        clip.setOnClickListener(v -> m.attachMenu());
        row.addView(clip, Ui.lp(Ui.dp(36), Ui.dp(36)));
        TextView gear = Ui.button(a, "[[gear]]", Ui.VIO, false);
        gear.setTextSize(14);
        gear.setPadding(0, 0, 0, 0);
        gear.setOnClickListener(v -> m.openParams(m.cur));
        row.addView(gear, Ui.margins(Ui.lp(Ui.dp(36), Ui.dp(36)), 6, 0, 0, 0));
        TextView sk = Ui.button(a, "[[sparkle]]", Ui.VIO, false);   // skills · pipelines · command book
        sk.setTextSize(14);
        sk.setPadding(0, 0, 0, 0);
        sk.setOnClickListener(v -> m.skillsMenu());
        sk.setOnLongClickListener(v -> { m.commandBook(); return true; });
        row.addView(sk, Ui.margins(Ui.lp(Ui.dp(36), Ui.dp(36)), 6, 0, 0, 0));
        TextView lo = Ui.button(a, "[[layers]]", Ui.VIO, false);   // LoRA samples panel (same as the web LoRA card)
        lo.setTextSize(14);
        lo.setPadding(0, 0, 0, 0);
        lo.setOnClickListener(v -> m.loras.browse(Loras.roleOf(m.cur), ""));
        row.addView(lo, Ui.margins(Ui.lp(Ui.dp(36), Ui.dp(36)), 6, 0, 6, 0));
        if (compact) for (View t : new View[]{clip, gear, sk, lo}) t.setVisibility(GONE);
        prompt = new EditText(a);
        prompt.setMinHeight(Ui.dp(36));
        prompt.setMaxLines(6);
        prompt.setTextColor(Ui.INK);
        prompt.setHintTextColor(Ui.FAINT);
        prompt.setTextSize(13.5f);
        prompt.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        prompt.setPadding(Ui.dp(10), Ui.dp(6), Ui.dp(10), Ui.dp(6));
        prompt.setBackground(Ui.box(16, 0x66000000, Ui.LINE2));
        prompt.setText(Prefs.str(a, "draft", ""));
        row.addView(prompt, new LayoutParams(0, Ui.WRAP, 1));
        goBtn = Ui.button(a, "[[send]]", Ui.VIO, true);
        goBtn.setTextSize(15);
        goBtn.setPadding(0, 0, 0, 0);
        goBtn.setOnClickListener(v -> m.generate(prompt.getText().toString().trim()));
        row.addView(goBtn, Ui.margins(Ui.lp(Ui.dp(46), Ui.dp(36)), 6, 0, 0, 0));
        comp.addView(row, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 4, 0, 0));
        addView(comp);
    }

    void setPrompt(String s) { prompt.setText(s); prompt.setSelection(s.length()); prompt.requestFocus(); }
    void clearPrompt() { prompt.setText(""); Prefs.put(m, "draft", ""); }

    void render() {
        renderModels();
        renderAtts();
        goBtn.setBackground(Ui.accent(m.accent(), 14));
        prompt.setHint(placeholder(m.cur));
    }

    static String placeholder(String k) {
        switch (k) {
            case "h3": return "Ask H3 for a video…";
            case "music3": return "Ask Music 3 for a song…";
            case "qimg": return "Ask Qwen for an image…";
            case "ace": return "Ask ACE for a track…";
            case "llama": return "Talk to MUSE — ideas, lyrics, scripts…";
            default: return "Message the lab…";
        }
    }

    private String modelSig = "";

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
            TextView name = Ui.bold(m, md.optString("label"), 11, on ? Ui.INK : Ui.DIM);
            name.setLetterSpacing(0.05f);
            card.addView(name, Ui.lp(Ui.WRAP, Ui.WRAP));
            card.setOnClickListener(v -> m.setModel(k));
            card.setOnLongClickListener(v -> { m.openParams(k); return true; });
            card.setFocusable(Tv.is(m));
            modelRow.addView(card, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 8, 0));
        }
    }

    void renderAtts() {
        attRow.removeAllViews();
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
            chip.setAlpha(l.optString("role").isEmpty() || role.equals(l.optString("role")) ? 1f : .45f);
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
        mascot.update(jobs, null);
        StringBuilder s = new StringBuilder();
        boolean live = false;
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject j = jobs.optJSONObject(i);
            s.append(j.optString("id")).append(j.optString("status")).append(j.optString("stage"));
            if ("llama".equals(j.optString("model"))) s.append(j.optString("output").length());   // stream in
            live |= "running".equals(j.optString("status"));
        }
        if (!force && (!live || Tv.is(m)) && s.toString().equals(sig) && thread.getChildCount() > 0) return;
        boolean atBottom = scroll.getChildAt(0).getBottom() - (scroll.getHeight() + scroll.getScrollY()) < Ui.dp(120);
        boolean grew = !s.toString().equals(sig);
        sig = s.toString();
        thread.removeAllViews();
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
    }

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
        GradientDrawable bg = guest ? new GradientDrawable() : new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{0x55FF5A1F, 0x33FF3B5C});
        if (guest) bg.setColor(0x141FC8DC);
        bg.setCornerRadii(guest ? new float[]{Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(5), Ui.dp(5)}
                : new float[]{Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(18), Ui.dp(5), Ui.dp(5), Ui.dp(18), Ui.dp(18)});
        bg.setStroke(Math.max(1, Ui.dp(1)), guest ? 0x4D1FC8DC : 0x59FF6E3C);
        b.setBackground(bg);
        LinearLayout top = Ui.hbox(m);
        top.setGravity(Gravity.CENTER_VERTICAL);
        if (guest) top.addView(Ui.chip(m, "[[user]] " + j.optString("user_name", "guest"), 0xFF1FC8DC), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 6, 0));
        top.addView(Ui.chip(m, "→ " + MainActivity.shortName(model), m.colorOf(model)), Ui.lp(Ui.WRAP, Ui.WRAP));
        top.addView(Ui.mono(m, stamp(j.optDouble("created", 0)), 10, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 0, 0));
        b.addView(top);
        String tag = j.optString("skill", "");
        if (tag.isEmpty() && !j.optString("pipeline", "").isEmpty()) tag = "" + j.optString("pipeline");
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
        String stp = ("running".equals(st) || "queued".equals(st)) && !j.optString("pipeline", "").isEmpty() ? "STEP " + j.optString("step") + " · " : "";
        top.addView(Ui.mono(m, stp + st.toUpperCase() + (t.isEmpty() ? "" : " · " + t), 11, col), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 0, 0));
        if (!j.isNull("finished") && j.has("finished"))
            top.addView(Ui.mono(m, stamp(j.optDouble("finished", 0)), 10, Ui.DIM), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 8, 0, 0, 0));
        b.addView(top);
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
            final String p0 = j.optString("prompt");
            acts.addView(small("↺ Again", Ui.DIM, v -> m.reuse(model, p0)));
        } else if ("running".equals(st) || "queued".equals(st)) {
            String stage = j.optString("stage");
            b.addView(Ui.mono(m, "⟳ " + (stage.isEmpty() || "queued".equals(stage) ? "waiting for the GPU…" : stage), 12, Ui.AMB),
                    Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 8, 0, 0));
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
                    media.setBackground(Ui.accent(Ui.mix(c, 0xFF120A07, 0.45f), 12));
                    TextView play = Ui.bold(m, "[[play]]  PLAY SONG", 13, Ui.INK);
                    play.setGravity(Gravity.CENTER);
                    media.addView(play, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                    b.addView(media, Ui.margins(Ui.lp(Ui.dp(240), Ui.dp(64)), 0, 9, 0, 0));
                } else {
                    ImageView iv = new ImageView(m);
                    iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
                    Thumbs.load(m, iv, "/thumb/" + Api.enc(fn));
                    media.addView(iv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                    if ("video".equals(kind)) {
                        TextView play = Ui.text(m, "[[play]]", 30, Ui.INK);
                        play.setGravity(Gravity.CENTER);
                        media.addView(play, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                    }
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
            final String p = j.optString("prompt");
            acts.addView(small("↺ Again", Ui.DIM, v -> m.reuse(model, p)));
        } else {
            String err = j.optString("error");
            if ("error".equals(st) && !err.isEmpty() && !"null".equals(err))
                b.addView(Ui.text(m, err, 12.5f, Ui.RED), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 8, 0, 0));
            final String p = j.optString("prompt");
            acts.addView(small("↺ Try again", Ui.DIM, v -> m.reuse(model, p)));
        }
        b.addView(acts, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 9, 0, 0));
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
