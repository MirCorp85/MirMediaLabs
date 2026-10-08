package com.mirmedialabs.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.text.InputType;
import android.content.Intent;
import android.net.Uri;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;


import org.json.JSONArray;
import org.json.JSONObject;

/** LoRA SAMPLES (native) — same /api/loras/* feed as the web left-column card: browse Civitai LoRAs for the
 *  current engine's role, install into ComfyUI, and apply up to 4 to the next renders (strength per LoRA). */
final class Loras {
    static final String[] ROLES = {"video", "image", "music"};
    static final String[] ROLE_LBL = {"Video", "Image", "Music"};
    final MainActivity m;
    JSONArray installed = new JSONArray();
    JSONObject downloads = new JSONObject();

    Loras(MainActivity m) { this.m = m; }

    /** Models that can load LoRAs, and which kind (Music 3 and MUSE can't load any). */
    static String canOf(String model) {
        if ("h3".equals(model)) return "video";
        if ("qimg".equals(model)) return "image";
        if ("ace".equals(model)) return "music";
        return null;
    }
    static String roleOf(String model) {
        if ("h3".equals(model)) return "video";
        if ("qimg".equals(model)) return "image";
        return "music";
    }
    private Activity act() { return m; }

    // ── selection (persisted, survives restarts) ──
    JSONArray sel() { try { return new JSONArray(Prefs.str(m, "loras", "[]")); } catch (Exception e) { return new JSONArray(); } }
    void saveSel(JSONArray a) { Prefs.put(m, "loras", a.toString()); }
    JSONObject selected(String file) { JSONArray a = sel(); for (int i = 0; i < a.length(); i++) if (file.equals(a.optJSONObject(i).optString("file"))) return a.optJSONObject(i); return null; }
    void setSel(String file, String name, String role, Float strength) {
        JSONArray a = sel(), out = new JSONArray();
        boolean found = false;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (file.equals(o.optString("file"))) { found = true; if (strength == null) continue; try { o.put("strength", strength); } catch (Exception ignored) {} }
            out.put(o);
        }
        if (!found && strength != null) {
            if (out.length() >= 4) { m.toast("Up to 4 LoRAs per render"); return; }
            out.put(Api.obj("file", file, "name", name, "role", role, "strength", strength));
        }
        saveSel(out);
        m.create.renderAtts();
    }
    /** What /api/generate gets: [{file, strength}]. */
    JSONArray forRender(String model) {        // every pick: the server applies what this request's model can load
        JSONArray a = sel(), out = new JSONArray();
        if (!m.can("loras")) return out;           // the host didn't give this person LoRA styles
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            out.put(Api.obj("file", o.optString("file"), "strength", o.optDouble("strength", 0.8)));
        }
        return out;
    }

    void refresh(Runnable done) {
        m.api.get("/api/loras/installed", r -> {
            if (r.ok()) {
                installed = r.obj().optJSONArray("items");
                downloads = r.obj().optJSONObject("downloads");
                if (installed == null) installed = new JSONArray();
                if (downloads == null) downloads = new JSONObject();
                // drop selections whose file is gone
                JSONArray a = sel(), keep = new JSONArray();
                for (int i = 0; i < a.length(); i++) if (isInstalled(a.optJSONObject(i).optString("file"))) keep.put(a.optJSONObject(i));
                if (keep.length() != a.length()) saveSel(keep);
            }
            if (done != null) done.run();
        });
    }
    boolean isInstalled(String file) { for (int i = 0; i < installed.length(); i++) if (file.equals(installed.optJSONObject(i).optString("file"))) return true; return false; }
    JSONObject inst(String file) { for (int i = 0; i < installed.length(); i++) if (file.equals(installed.optJSONObject(i).optString("file"))) return installed.optJSONObject(i); return null; }

    // ── browser ──
    void browse(String role, String q) {
        Sheet sh = new Sheet(act(), "LoRA samples", "layers", Ui.pal());
        // role tabs
        LinearLayout tabs = new LinearLayout(m);
        for (int i = 0; i < ROLES.length; i++) {
            final String r = ROLES[i];
            boolean on = r.equals(role);
            TextView t = Ui.bold(m, ROLE_LBL[i].toUpperCase(), 11.5f, on ? Ui.INK : Ui.DIM);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, Ui.dp(9), 0, Ui.dp(9));
            t.setBackground(Ui.box(10, on ? Ui.CARD2 : 0, on ? Ui.LINE2 : Ui.LINE));
            t.setOnClickListener(v -> { sh.dismiss(); browse(r, ""); });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1);
            lp.setMargins(i == 0 ? 0 : Ui.dp(4), 0, 0, 0);
            tabs.addView(t, lp);
        }
        sh.add(tabs);
        // server search
        EditText e = new EditText(m);
        e.setSingleLine(true); e.setHint("Search Civitai LoRAs…"); e.setText(q);
        e.setTextColor(Ui.INK); e.setHintTextColor(Ui.DIM); e.setTextSize(14);
        e.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        e.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
        e.setBackground(Ui.box(12, Ui.CARD2, Ui.LINE));
        e.setOnEditorActionListener((v, id, ev) -> {
            if (id == EditorInfo.IME_ACTION_SEARCH || (ev != null && ev.getKeyCode() == KeyEvent.KEYCODE_ENTER)) { sh.dismiss(); browse(role, e.getText().toString().trim()); return true; }
            return false;
        });
        sh.add(e);
        // installed for this role
        LinearLayout mine = Ui.vbox(m);
        sh.add(mine);
        TextView loading = Ui.text(m, "Loading the " + role + " LoRA library…", 12.5f, Ui.DIM);
        loading.setPadding(Ui.dp(4), Ui.dp(10), 0, 0);
        sh.add(loading);
        sh.show();
        refresh(() -> {
            mine.removeAllViews();
            for (int i = 0; i < installed.length(); i++) {
                JSONObject it = installed.optJSONObject(i);
                if (it.optBoolean("builtin") || (!it.optString("role").isEmpty() && !role.equals(it.optString("role")))) continue;
                if (mine.getChildCount() == 0) mine.addView(head("ON YOUR PC"));
                JSONObject s = selected(it.optString("file"));
                mine.addView(installedRow(it, role, s, sh), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 4, 0, 0));
            }
        });
        m.api.get("/api/loras/catalog?role=" + role + "&q=" + Api.enc(q), r -> {
            if (!r.ok()) { loading.setText(r.err()); return; }
            JSONArray items = r.obj().optJSONArray("items");
            loading.setText(items == null || items.length() == 0 ? "No LoRAs found." : "LIBRARY · CIVITAI (safe-for-work previews)");
            loading.setTextColor(Ui.DIM);
            for (int i = 0; items != null && i < items.length(); i++) {
                JSONObject it = items.optJSONObject(i);
                sh.add(card(it, sh));
            }
        });
    }

    private TextView head(String s) {
        TextView t = Ui.bold(m, s, 10.5f, Ui.DIM);
        t.setLetterSpacing(.14f);
        t.setPadding(Ui.dp(4), Ui.dp(12), 0, Ui.dp(2));
        return t;
    }

    private View installedRow(JSONObject it, String role, JSONObject s, Sheet sh) {
        LinearLayout r = Ui.hbox(m);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
        r.setBackground(Ui.box(12, s != null ? Ui.alpha(Ui.VIO, .16f) : Ui.CARD2, s != null ? Ui.VIO : Ui.LINE));
        r.addView(Ui.text(m, s != null ? "[[check]]" : "[[layers]]", 15, s != null ? Ui.VIO : Ui.DIM));
        TextView n = Ui.bold(m, it.optString("name"), 13.5f, Ui.INK);
        n.setSingleLine(true);
        r.addView(n, Ui.margins(new LinearLayout.LayoutParams(0, Ui.WRAP, 1), 10, 0, 6, 0));
        boolean bad = it.has("fits") && !it.isNull("fits") && !it.optBoolean("fits");   // other model generation: no layer matches
        r.addView(Ui.text(m, bad ? "[[warn]] won't load" : s != null ? String.format(java.util.Locale.US, "%.2f", s.optDouble("strength", .8)) : "use", 12, bad ? Ui.AMB : Ui.DIM));
        if (bad) r.setAlpha(.6f);
        r.setOnClickListener(v -> {
            if (bad) { m.toast(it.optString("name") + " was made for a different version of this model — it can't change your renders"); return; }
            if (s != null) setSel(it.optString("file"), null, null, null);
            else setSel(it.optString("file"), it.optString("name"), it.optString("role", role), 0.8f);
            sh.dismiss();
            browse(role, "");
        });
        return r;
    }

    private View card(JSONObject it, Sheet sh) {
        LinearLayout r = Ui.hbox(m);
        r.setPadding(Ui.dp(8), Ui.dp(8), Ui.dp(12), Ui.dp(8));
        r.setBackground(Ui.box(12, Ui.CARD2, Ui.LINE));
        ImageView iv = new ImageView(m);
        iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
        iv.setClipToOutline(true);
        iv.setBackground(Ui.box(9, Ui.CARD, 0));
        JSONObject p = it.optJSONArray("previews") != null ? it.optJSONArray("previews").optJSONObject(0) : null;
        if (p != null) Thumbs.loadUrl(iv, p.optString("thumb", p.optString("url")));
        r.addView(iv, Ui.lp(Ui.dp(64), Ui.dp(84)));
        LinearLayout tx = Ui.vbox(m);
        TextView n = Ui.bold(m, it.optString("name"), 13.5f, Ui.INK);
        n.setMaxLines(2);
        tx.addView(n);
        tx.addView(Ui.text(m, "by " + it.optString("creator") + (p != null && "video".equals(p.optString("kind")) ? "   [[play]] video" : ""), 11.5f, Ui.DIM));
        tx.addView(Ui.text(m, String.format(java.util.Locale.US, "[[download]] %,d   %s MB%s", it.optInt("downloads"), it.optString("size_mb"),
                it.optBoolean("installed") ? "   [[check]] installed" : ""), 11, it.optBoolean("installed") ? Ui.VIO : Ui.FAINT));
        r.addView(tx, Ui.margins(new LinearLayout.LayoutParams(0, Ui.WRAP, 1), 12, 2, 0, 0));
        r.setOnClickListener(v -> { sh.dismiss(); detail(it); });
        LinearLayout wrap = Ui.vbox(m);
        wrap.addView(r, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 6, 0, 0));
        return wrap;
    }

    void detail(JSONObject it) {
        String file = it.optString("file"), role = it.optString("role");
        Sheet sh = new Sheet(act(), "LoRA", "layers", Ui.pal());
        ImageView big = new ImageView(m);
        big.setScaleType(ImageView.ScaleType.CENTER_CROP);
        big.setClipToOutline(true);
        big.setBackground(Ui.box(14, Ui.CARD2, 0));
        JSONArray pv = it.optJSONArray("previews");
        if (pv != null && pv.length() > 0) Thumbs.loadUrl(big, pv.optJSONObject(0).optString("thumb"));
        sh.body().addView(big, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(260)), 0, 8, 0, 0));
        if (pv != null && pv.length() > 1) {
            LinearLayout strip = Ui.hbox(m);
            for (int i = 1; i < Math.min(4, pv.length()); i++) {
                ImageView t = new ImageView(m);
                t.setScaleType(ImageView.ScaleType.CENTER_CROP); t.setClipToOutline(true); t.setBackground(Ui.box(10, Ui.CARD2, 0));
                Thumbs.loadUrl(t, pv.optJSONObject(i).optString("thumb"));
                strip.addView(t, Ui.margins(new LinearLayout.LayoutParams(0, Ui.dp(90), 1), i == 1 ? 0 : 6, 0, 0, 0));
            }
            sh.body().addView(strip, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 6, 0, 0));
        }
        TextView nm = Ui.bold(m, it.optString("name"), 17, Ui.INK);
        nm.setPadding(Ui.dp(4), Ui.dp(12), 0, 0);
        sh.add(nm);
        sh.note("by " + it.optString("creator") + " · " + it.optString("base") + "\n" + role + " renders · " + it.optString("size_mb") + " MB · "
                + String.format(java.util.Locale.US, "%,d downloads · %,d likes", it.optInt("downloads"), it.optInt("likes")));
        JSONArray tr = it.optJSONArray("triggers");
        if (tr != null && tr.length() > 0) {
            StringBuilder b = new StringBuilder("Trigger words (added to your prompt): ");
            for (int i = 0; i < tr.length(); i++) b.append(i > 0 ? " · " : "").append(tr.optString(i));
            sh.note(b.toString());
        }
        JSONObject in = inst(file), s = selected(file);
        if (in != null) {
            float cur = s != null ? (float) s.optDouble("strength", .8) : .8f;
            TextView sv = Ui.text(m, String.format(java.util.Locale.US, "Strength  %.2f", cur), 13, Ui.INK);
            sv.setPadding(Ui.dp(4), Ui.dp(10), 0, 0);
            sh.add(sv);
            SeekBar sb = new SeekBar(m);
            sb.setMax(140);
            sb.setProgress(Math.round((cur - .1f) * 100));
            sb.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                public void onProgressChanged(SeekBar b, int v, boolean u) { sv.setText(String.format(java.util.Locale.US, "Strength  %.2f", .1f + v / 100f)); }
                public void onStartTrackingTouch(SeekBar b) {}
                public void onStopTrackingTouch(SeekBar b) {}
            });
            sh.add(sb);
            sh.button(s != null ? "check" : "layers", s != null ? "Update strength" : "Use in next renders", true, () -> {
                setSel(file, it.optString("name"), role, .1f + sb.getProgress() / 100f);
                m.toast("LoRA applied to your next " + role + " renders");
            });
            if (s != null) sh.button("close", "Stop using", false, () -> setSel(file, null, null, null));
            if (in.optBoolean("ours")) sh.button("trash", "Remove from PC", false, () ->
                    m.api.post("/api/loras/remove", Api.obj("file", file), r -> { m.toast(r.ok() ? "Removed" : r.err()); refresh(null); }));
        } else {
            JSONObject dl = downloads.optJSONObject(String.valueOf(it.optLong("version_id")));
            if (dl != null && "downloading".equals(dl.optString("state"))) sh.note("Downloading… " + dl.optInt("pct") + "%");
            else {
                if (dl != null && "error".equals(dl.optString("state"))) {
                    sh.note(dl.optString("error"));
                    if (dl.optBoolean("need_key")) sh.button("key", "Add Civitai key", false, () -> askKey(it));
                }
                sh.button("download", "Install (" + it.optString("size_mb") + " MB)", true, () -> install(it));
            }
        }
        sh.button("external", "Open on Civitai", false, () -> {
            try { act().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(it.optString("page")))); } catch (Exception ignored) { }
        });
        sh.note("Community LoRA — results vary by model version. Check the creator's license before commercial use.");
        sh.show();
    }

    private void install(JSONObject it) {
        m.api.post("/api/loras/install", Api.obj("item", it), r -> {
            if (!r.ok()) { m.toast(r.err()); return; }
            m.toast("Installing " + it.optString("name") + "…");
            watch(it);
        });
    }

    /** Most Civitai LoRAs need a (free) API key: ask for it, let the server validate + save it, then retry. */
    private void askKey(JSONObject it) {
        EditText e = new EditText(act());
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        e.setHint("paste your Civitai API key");
        new AlertDialog.Builder(act(), android.R.style.Theme_DeviceDefault_Dialog_Alert).setTitle("Civitai key needed")
                .setMessage("This LoRA needs a free Civitai API key.\n\ncivitai.com → Account settings → API Keys → Add API key, then paste it here. It's saved on the PC, never shown again.")
                .setView(e)
                .setPositiveButton("Save & install", (d, w) -> {
                    String tok = e.getText().toString().trim();
                    if (tok.isEmpty()) { m.toast("Paste the key first"); return; }
                    m.api.post("/api/loras/token", Api.obj("token", tok), r -> {
                        if (!r.ok()) { m.toast(r.err()); return; }
                        String u = r.obj().optString("user");
                        m.toast("Civitai key saved" + (u.isEmpty() ? "" : " — " + u));
                        install(it);
                    });
                })
                .setNegativeButton("Cancel", null).show();
    }

    /** Poll the download; tell the user when it lands. */
    private void watch(JSONObject it) {
        String key = String.valueOf(it.optLong("version_id"));
        refresh(() -> {
            JSONObject d = downloads.optJSONObject(key);
            if (d == null) return;
            String st = d.optString("state");
            if ("downloading".equals(st)) Api.MAIN.postDelayed(() -> watch(it), 2000);
            else if ("done".equals(st)) m.toast(it.optString("name") + " installed — open it to use it");
            else if ("error".equals(st)) {
                if (d.optBoolean("need_key")) askKey(it);
                else m.toast("Install failed: " + d.optString("error"));
            }
        });
    }
}
