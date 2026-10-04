package com.mirmedialabs.app;

import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.BaseAdapter;
import android.widget.FrameLayout;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** LIBRARY: everything the Media Lab has made, newest first, filterable, paged. */
final class LibraryPage extends LinearLayout {
    private final MainActivity m;
    private final List<JSONObject> items = new ArrayList<>();
    private final TextView[] filters = new TextView[4];
    private final TextView count;
    private final Adapter adapter = new Adapter();
    private String kind = "";
    private int total = 0;
    private boolean loading = false;

    LibraryPage(MainActivity a) {
        super(a);
        m = a;
        setOrientation(VERTICAL);
        setPadding(Ui.dp(14), Ui.dp(4), Ui.dp(14), 0);

        LinearLayout head = Ui.hbox(a);
        head.addView(Ui.label(a, "Library"), Ui.lpw(1));
        count = Ui.text(a, "", 11.5f, Ui.FAINT);
        head.addView(count);
        addView(head, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 2, 4, 2, 10));

        LinearLayout fr = Ui.hbox(a);
        String[][] f = {{"", "ALL"}, {"image", "IMAGES"}, {"video", "VIDEO"}, {"audio", "AUDIO"}};
        for (int i = 0; i < 4; i++) {
            final String k = f[i][0];
            TextView t = Ui.bold(a, f[i][1], 10.5f, Ui.DIM);
            t.setLetterSpacing(0.08f);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, Ui.dp(8), 0, Ui.dp(8));
            t.setOnClickListener(v -> { kind = k; paintFilters(); reload(); });
            t.setFocusable(Tv.is(a));
            filters[i] = t;
            fr.addView(t, Ui.margins(Ui.lpw(1), 0, 0, i < 3 ? 6 : 0, 0));
        }
        addView(fr, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 10));
        paintFilters();

        GridView g = new GridView(a);
        g.setNumColumns(Tv.is(a) ? 5 : 2);
        g.setHorizontalSpacing(Ui.dp(8));
        g.setVerticalSpacing(Ui.dp(8));
        if (Tv.is(a)) { g.setDrawSelectorOnTop(true); g.setSelector(Ui.box(12, 0x33FFC21A, Ui.AMB)); }
        else g.setSelector(android.R.color.transparent);
        g.setAdapter(adapter);
        g.setOnItemClickListener((p, v, pos, id) -> {
            JSONObject it = items.get(pos);
            m.openViewer(it.optString("name"), it.optString("model"));
        });
        g.setOnScrollListener(new AbsListView.OnScrollListener() {
            @Override public void onScrollStateChanged(AbsListView v, int s) {}
            @Override public void onScroll(AbsListView v, int first, int vis, int tot) {
                if (tot > 0 && first + vis >= tot - 4 && items.size() < total) more();
            }
        });
        addView(g, new LayoutParams(Ui.MATCH, 0, 1));
    }

    private void paintFilters() {
        String[] ks = {"", "image", "video", "audio"};
        for (int i = 0; i < 4; i++) {
            boolean on = ks[i].equals(kind);
            filters[i].setTextColor(on ? Ui.INK : Ui.DIM);
            filters[i].setBackground(Ui.box(9, on ? Ui.CARD2 : 0, on ? Ui.LINE2 : Ui.LINE));
        }
    }

    void reload() { items.clear(); adapter.notifyDataSetChanged(); total = 0; loading = false; more(); }

    private void more() {
        if (loading) return;
        loading = true;
        m.api.get("/api/library?kind=" + kind + "&offset=" + items.size() + "&limit=40", r -> {
            loading = false;
            if (!r.ok()) { count.setText(r.err()); return; }
            JSONObject j = r.obj();
            total = j.optInt("total");
            JSONArray a = j.optJSONArray("items");
            for (int i = 0; a != null && i < a.length(); i++) items.add(a.optJSONObject(i));
            count.setText(total + (total == 1 ? " item" : " items"));
            adapter.notifyDataSetChanged();
        });
    }

    private final class Adapter extends BaseAdapter {
        @Override public int getCount() { return items.size(); }
        @Override public Object getItem(int p) { return items.get(p); }
        @Override public long getItemId(int p) { return p; }

        @Override public View getView(int pos, View cv, ViewGroup parent) {
            FrameLayout f;
            ImageView iv;
            TextView note, cap;
            if (cv == null) {
                f = new FrameLayout(m);
                int w = (parent.getWidth() - Ui.dp(8)) / (Tv.is(m) ? 5 : 2);
                f.setLayoutParams(new AbsListView.LayoutParams(Ui.MATCH, Math.max(Ui.dp(110), w * 3 / 4)));
                f.setClipToOutline(true);
                iv = new ImageView(m);
                iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
                f.addView(iv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                note = Ui.text(m, "", 30, Ui.INK);
                note.setGravity(Gravity.CENTER);
                f.addView(note, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
                cap = Ui.bold(m, "", 9.5f, Ui.INK);
                cap.setSingleLine(true);
                cap.setPadding(Ui.dp(8), Ui.dp(5), Ui.dp(8), Ui.dp(5));
                cap.setBackground(Ui.box(0, 0x99000000, 0));
                f.addView(cap, new FrameLayout.LayoutParams(Ui.MATCH, Ui.WRAP, Gravity.BOTTOM));
                f.setTag(new View[]{iv, note, cap});
            } else f = (FrameLayout) cv;
            View[] vs = (View[]) f.getTag();
            iv = (ImageView) vs[0]; note = (TextView) vs[1]; cap = (TextView) vs[2];
            JSONObject it = items.get(pos);
            String name = it.optString("name"), k = it.optString("kind"), model = it.optString("model");
            int c = m.colorOf(model);
            cap.setTextColor(c);
            Icons.set(cap, MainActivity.shortName(model) + ("video".equals(k) ? "  [[play]] VIDEO" : "audio".equals(k) ? "  [[music]] AUDIO" : ""));
            if ("audio".equals(k)) {
                iv.setTag(null);
                iv.setImageDrawable(null);
                f.setBackground(Ui.accent(Ui.mix(c, 0xFF0E0E16, 0.55f), 12));
                note.setTextColor(0xFFFFFFFF);         // tile is always dark, whatever the theme
                Icons.set(note, "[[music]]");
            } else {
                f.setBackground(Ui.box(12, 0xFF0E0E16, Ui.LINE));
                note.setText("");
                Thumbs.load(m, iv, "/thumb/" + Api.enc(name));
            }
            return f;
        }
    }
}
