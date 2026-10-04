package com.mirmedialabs.app;

import android.app.AlertDialog;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** ⚙ per-model parameters, built from the server's schema. Saved on the PC (shared with desktop/web). */
final class ParamsDialog {
    private final MainActivity m;
    private final String model;
    private final Map<String, View> inputs = new LinkedHashMap<>();
    private final Map<String, List<String>> values = new LinkedHashMap<>();

    ParamsDialog(MainActivity a, String model) { m = a; this.model = model; }

    void show() {
        JSONObject md = m.model(model);
        JSONArray fields = md.optJSONArray("fields");
        JSONObject cur = md.optJSONObject("values");
        if (fields == null) { m.toast("Not connected yet"); return; }
        ScrollView sv = new ScrollView(m);
        LinearLayout box = Ui.vbox(m);
        box.setPadding(Ui.dp(20), Ui.dp(8), Ui.dp(20), Ui.dp(8));
        sv.addView(box);
        for (int i = 0; i < fields.length(); i++) {
            JSONObject f = fields.optJSONObject(i);
            String k = f.optString("k"), type = f.optString("type");
            Object val = cur != null && cur.has(k) ? cur.opt(k) : f.opt("def");
            String sval = val == null ? "" : fmt(val);
            TextView lab = Ui.label(m, f.optString("label"));
            box.addView(lab, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 12, 0, 6));
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
                int sel = Math.max(0, keys.indexOf(sval));
                sp.setSelection(sel);
                sp.setBackground(Ui.box(10, 0x55000000, Ui.LINE2));
                sp.setPadding(Ui.dp(6), Ui.dp(4), Ui.dp(6), Ui.dp(4));
                box.addView(sp, Ui.lp(Ui.MATCH, Ui.dp(46)));
                inputs.put(k, sp);
                values.put(k, keys);
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
                box.addView(e, Ui.lp(Ui.MATCH, Ui.WRAP));
                inputs.put(k, e);
            }
        }
        TextView note = Ui.text(m, "Saved on the PC — the same values apply on desktop, web and this app. Inline --flags in a prompt still win for that run.", 11.5f, Ui.FAINT);
        box.addView(note, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 16, 0, 4));

        new AlertDialog.Builder(m, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle(md.optString("label") + " · parameters")
                .setView(sv)
                .setPositiveButton("Save", (d, w) -> save(false))
                .setNeutralButton("Defaults", (d, w) -> save(true))
                .setNegativeButton("Cancel", null)
                .show();
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
