package com.mirmedialabs.app;

import android.app.AlertDialog;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.VideoView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** ⚙ per-model parameters, built from the server's schema in collapsible sections (Basics, Extend & storyboard,
 *  Camera & motion, Scene & effects, Post effects, Audio, References, Advanced, Workflow). Plain-language labels,
 *  the technical term underneath, a one-line description and tap-to-watch example thumbnails come from the schema.
 *  Saved on the PC (shared with desktop/web). Read-only when the host hasn't given "Custom parameters". */
final class ParamsDialog {
    private final MainActivity m;
    private final String model;
    private final Map<String, View> inputs = new LinkedHashMap<>();
    private final Map<String, List<String>> values = new LinkedHashMap<>();

    ParamsDialog(MainActivity a, String model) { m = a; this.model = model; }

    private static boolean modified(JSONObject f, JSONObject cur) {
        String k = f.optString("k");
        Object val = cur != null && cur.has(k) ? cur.opt(k) : f.opt("def");
        return !String.valueOf(val).equals(String.valueOf(f.opt("def")));
    }

    void show() {
        JSONObject md = m.model(model);
        JSONArray fields = md.optJSONArray("fields");
        JSONObject cur = md.optJSONObject("values");
        boolean locked = md.optBoolean("locked");
        if (fields == null) { m.toast("Not connected yet"); return; }
        ScrollView sv = new ScrollView(m);
        LinearLayout box = Ui.vbox(m);
        box.setPadding(Ui.dp(20), Ui.dp(8), Ui.dp(20), Ui.dp(8));
        sv.addView(box);
        if (locked) {
            TextView lk = Ui.text(m, "The host set your parameters — you render with the lab's defaults. Ask the host for Custom parameters to change them.", 12.5f, Ui.DIM);
            lk.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
            lk.setBackground(Ui.box(10, 0x22000000, Ui.LINE2));
            box.addView(lk, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 8, 0, 4));
        }
        // group → its fields, in schema order
        Map<String, List<JSONObject>> groups = new LinkedHashMap<>();
        for (int i = 0; i < fields.length(); i++) {
            JSONObject f = fields.optJSONObject(i);
            String g = f.optString("group", "Settings");
            if (g.isEmpty()) g = "Settings";
            List<JSONObject> l = groups.get(g);
            if (l == null) { l = new ArrayList<>(); groups.put(g, l); }
            l.add(f);
        }
        int gi = 0;
        for (Map.Entry<String, List<JSONObject>> ge : groups.entrySet()) {
            int changed = 0;
            for (JSONObject f : ge.getValue()) if (modified(f, cur)) changed++;
            boolean open = gi++ == 0 || changed > 0 || groups.size() == 1;
            LinearLayout sec = Ui.vbox(m);
            TextView hd = Ui.bold(m, (open ? "▾  " : "▸  ") + ge.getKey().toUpperCase() + (changed > 0 ? "   · " + changed + " changed" : ""), 12, changed > 0 ? Ui.VIO : Ui.DIM);
            hd.setPadding(Ui.dp(4), Ui.dp(12), Ui.dp(4), Ui.dp(8));
            hd.setLetterSpacing(.08f);
            hd.setFocusable(true);
            final String title = ge.getKey().toUpperCase() + (changed > 0 ? "   · " + changed + " changed" : "");
            hd.setOnClickListener(v -> {
                boolean show = sec.getVisibility() != View.VISIBLE;
                sec.setVisibility(show ? View.VISIBLE : View.GONE);
                hd.setText((show ? "▾  " : "▸  ") + title);
            });
            box.addView(hd, Ui.lp(Ui.MATCH, Ui.WRAP));
            sec.setVisibility(open ? View.VISIBLE : View.GONE);
            box.addView(sec, Ui.lp(Ui.MATCH, Ui.WRAP));
            for (JSONObject f : ge.getValue()) addField(sec, f, cur, locked);
        }
        TextView note = Ui.text(m, locked ? "Read-only — the host manages your parameters."
                : "Saved on the PC — the same values apply on desktop, web and this app. Inline --flags in a prompt still win for that run. Custom ComfyUI workflows are added on the PC (⚙ → Workflow).", 11.5f, Ui.FAINT);
        box.addView(note, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 16, 0, 4));

        AlertDialog.Builder b = new AlertDialog.Builder(m, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle(md.optString("label") + " · parameters")
                .setView(sv);
        if (locked) b.setPositiveButton("Close", null);
        else b.setPositiveButton("Save", (d, w) -> save(false))
                .setNeutralButton("Defaults", (d, w) -> save(true))
                .setNegativeButton("Cancel", null);
        b.show();
    }

    private void addField(LinearLayout box, JSONObject f, JSONObject cur, boolean locked) {
        String k = f.optString("k"), type = f.optString("type");
        Object val = cur != null && cur.has(k) ? cur.opt(k) : f.opt("def");
        String sval = val == null ? "" : fmt(val);
        TextView lab = Ui.label(m, f.optString("label"));
        box.addView(lab, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, f.has("tech") ? 0 : 6));
        if (f.has("tech")) box.addView(Ui.text(m, f.optString("tech"), 10.5f, Ui.FAINT), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 6));
        if ("select".equals(type)) {
            JSONArray opts = f.optJSONArray("opts");
            List<String> keys = new ArrayList<>(), labels = new ArrayList<>();
            for (int o = 0; opts != null && o < opts.length(); o++) {
                Object op = opts.opt(o);
                if (op instanceof JSONArray) { keys.add(((JSONArray) op).optString(0)); labels.add(((JSONArray) op).optString(1)); }
                else { keys.add(String.valueOf(op)); labels.add(String.valueOf(op)); }
            }
            Spinner sp = new Spinner(m, Spinner.MODE_DIALOG);
            ArrayAdapter<String> ad = new ArrayAdapter<String>(m, android.R.layout.simple_spinner_item, labels) {
                @Override public View getView(int p, View c, ViewGroup g) {
                    TextView t = (TextView) super.getView(p, c, g); t.setTextColor(Ui.INK); t.setTextSize(14); return t;
                }
            };
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
            sp.setAdapter(ad);
            sp.setSelection(Math.max(0, keys.indexOf(sval)));
            sp.setBackground(Ui.box(10, 0x55000000, Ui.LINE2));
            sp.setPadding(Ui.dp(6), Ui.dp(4), Ui.dp(6), Ui.dp(4));
            sp.setEnabled(!locked);
            box.addView(sp, Ui.lp(Ui.MATCH, Ui.dp(46)));
            inputs.put(k, sp);
            values.put(k, keys);
            JSONObject odesc = f.optJSONObject("odesc");
            TextView od = odesc == null ? null : Ui.text(m, odesc.optString(sval), 11.5f, Ui.DIM);
            if (od != null) box.addView(od, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 4, 0, 0));
            LinearLayout strip = locked ? null : previews(f, keys, labels, sp, odesc);
            sp.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
                @Override public void onItemSelected(AdapterView<?> p, View v, int pos, long id) {
                    String key = keys.get(pos);
                    if (od != null) od.setText(odesc.optString(key));
                    if (strip != null) for (int i = 0; i < strip.getChildCount(); i++) {
                        View t = strip.getChildAt(i);
                        t.setBackground(Ui.box(10, 0x33000000, key.equals(t.getTag()) ? Ui.VIO : Ui.LINE2));
                    }
                }
                @Override public void onNothingSelected(AdapterView<?> p) { }
            });
            if (strip != null) {
                HorizontalScrollView hs = new HorizontalScrollView(m);
                hs.setHorizontalScrollBarEnabled(false);
                hs.addView(strip);
                box.addView(hs, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 8, 0, 0));
            }
        } else {
            EditText e = new EditText(m);
            e.setSingleLine(true);
            e.setText(sval);
            e.setTextColor(Ui.INK);
            e.setHintTextColor(Ui.FAINT);
            e.setHint("number".equals(type) ? ("".equals(f.optString("def")) ? "auto" : f.optString("def")) : "");
            e.setInputType("number".equals(type)
                    ? InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL
                    : InputType.TYPE_CLASS_TEXT);
            e.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
            e.setBackground(Ui.box(10, 0x55000000, Ui.LINE2));
            e.setEnabled(!locked);
            box.addView(e, Ui.lp(Ui.MATCH, Ui.WRAP));
            inputs.put(k, e);
        }
        for (String t : new String[]{f.optString("desc"), f.optString("help")})
            if (!t.isEmpty()) box.addView(Ui.text(m, t, 11, Ui.FAINT), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 4, 0, 0));
    }

    /** Example thumbnails (server-rendered previews) — tap one to watch it and pick that option. */
    private LinearLayout previews(JSONObject f, List<String> keys, List<String> labels, Spinner sp, JSONObject odesc) {
        JSONObject pv = f.optJSONObject("opreview");
        if (pv == null || pv.length() == 0) return null;
        LinearLayout row = Ui.hbox(m);
        String cur = keys.get(Math.max(0, sp.getSelectedItemPosition()));
        for (int i = 0; i < keys.size(); i++) {
            String key = keys.get(i);
            JSONObject p = pv.optJSONObject(key);
            if (p == null) continue;
            String name = labels.get(i).split(" · ")[0];
            LinearLayout tile = Ui.vbox(m);
            tile.setTag(key);
            tile.setPadding(Ui.dp(2), Ui.dp(2), Ui.dp(2), Ui.dp(4));
            tile.setBackground(Ui.box(10, 0x33000000, key.equals(cur) ? Ui.VIO : Ui.LINE2));
            ImageView iv = new ImageView(m);
            iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
            Thumbs.load(m, iv, abs(p.optString("poster")));
            tile.addView(iv, Ui.lp(Ui.dp(118), Ui.dp(66)));
            TextView t = Ui.text(m, name, 10.5f, Ui.DIM);
            t.setSingleLine(true);
            t.setPadding(Ui.dp(4), Ui.dp(3), Ui.dp(4), 0);
            tile.addView(t, Ui.lp(Ui.dp(118), Ui.WRAP));
            final int idx = i;
            tile.setFocusable(true);
            tile.setOnClickListener(v -> preview(name, p.optString("video"), odesc == null ? "" : odesc.optString(key), () -> sp.setSelection(idx)));
            row.addView(tile, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 0, 8, 0));
        }
        return row.getChildCount() == 0 ? null : row;
    }

    private static String abs(String p) { return p.startsWith("/") ? p : "/" + p; }   // schema paths are page-relative

    private void preview(String name, String video, String desc, Runnable use) {
        LinearLayout box = Ui.vbox(m);
        box.setPadding(Ui.dp(16), Ui.dp(10), Ui.dp(16), Ui.dp(4));
        if (!video.isEmpty()) {
            FrameLayout fr = new FrameLayout(m);
            VideoView vv = new VideoView(m);
            vv.setVideoURI(android.net.Uri.parse(m.api.mediaUrl(abs(video))));
            vv.setOnPreparedListener(mp -> { mp.setLooping(true); mp.setVolume(0, 0); vv.start(); });
            fr.addView(vv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.WRAP, android.view.Gravity.CENTER));
            box.addView(fr, Ui.lp(Ui.MATCH, Ui.dp(180)));
        }
        if (!desc.isEmpty()) box.addView(Ui.text(m, desc, 13, Ui.INK), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 4));
        new AlertDialog.Builder(m, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle(name).setView(box)
                .setPositiveButton("Use this", (d, w) -> use.run())
                .setNegativeButton("Close", null).show();
    }

    private static String fmt(Object v) { return String.valueOf(v); }

    private void save(boolean reset) {
        JSONObject vals = new JSONObject();
        try {
            for (Map.Entry<String, View> e : inputs.entrySet()) {
                View v = e.getValue();
                if (v instanceof Spinner) vals.put(e.getKey(), values.get(e.getKey()).get(((Spinner) v).getSelectedItemPosition()));
                else vals.put(e.getKey(), ((EditText) v).getText().toString().trim());
            }
        } catch (Exception ignored) {}
        JSONObject body = reset ? Api.obj("reset", true) : Api.obj("values", vals);
        m.api.post("/api/params/" + model, body, r -> {
            if (!r.ok()) { m.toast(r.err()); return; }
            m.toast(m.model(model).optString("label") + (reset ? " reset to defaults" : " parameters saved"));
            m.refreshModels();
        });
    }
}
