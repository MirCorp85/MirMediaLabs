package com.mirmedialabs.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Shell: header + 3 pages (CREATE · LIBRARY · QUEUE) + shared state and polling. */
public class MainActivity extends Activity {
    static final String[] ORDER = {"auto", "h3", "music3", "qimg", "ace", "llama"};
    static final int PICK = 41;

    Api api;
    MuseVoice voice;
    private TextView voiceBtn, popBtn;
    Loras loras;
    JSONObject models = new JSONObject(), status = new JSONObject();
    JSONArray jobs = new JSONArray();
    String cur = "h3";
    final List<JSONObject> atts = new ArrayList<>();
    final Set<String> seenDone = new HashSet<>();
    boolean seeded = false;

    private TextView pill, qBadge, menu;
    CreatePage create;
    private LibraryPage library;
    private final TextView[] tabs = new TextView[2];
    private int tab = 0;
    /** Tablet mode: models + tools | chat | library side by side (big screens, or forced in Settings - Look - Layout). */
    boolean wide;
    private final Handler h = new Handler(Looper.getMainLooper());
    private int tick = 0;
    private boolean resumed = false;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Ui.init(this);
        Fonts.apply(this);   // MIR FONTS pick, before any view is built
        Theme.apply(this);   // MIR MEDIA LABS theme (same five palettes as the web)
        if (!Prefs.configured(this)) {     // first run: sign in (a shared invite link is passed along)
            Intent s = new Intent(this, SetupActivity.class);
            Intent in = getIntent();
            if (in != null && Intent.ACTION_SEND.equals(in.getAction()) && in.getStringExtra(Intent.EXTRA_TEXT) != null)
                s.putExtra("invite", in.getStringExtra(Intent.EXTRA_TEXT));
            startActivity(s);
            finish();
            return;
        }
        api = new Api(this);
        voice = new MuseVoice(this);
        loras = new Loras(this);
        cur = Prefs.str(this, "model2", "auto");     // Auto (MUSE Director) is the default
        loadAtts();
        build();
        api.probe(() -> {
            refreshModels(); poll(); library.reload(); Fonts.sync(this, api); Theme.sync(this, api); voice.sync(); loras.refresh(null);
            if (!fromNotification(getIntent())) Updater.check(this, false);
        });
        handleShare(getIntent());
        PushJob.schedule(this);
        h.postDelayed(() -> { if (!isFinishing()) { Crash.offer(this); askNotifications(); } }, 1200);
    }

    @Override public void onBackPressed() {
        if (tab != 0) showTab(0);
        else super.onBackPressed();
    }

    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); if (!fromNotification(i)) handleShare(i); }
    @Override protected void onResume() { super.onResume(); resumed = true; Push.appVisible = true; h.removeCallbacks(loop); h.postDelayed(loop, 400); }
    @Override protected void onPause() { super.onPause(); resumed = false; Push.appVisible = false; h.removeCallbacks(loop); }

    /** Tapped a notification: open the finished piece, or the update. */
    private boolean fromNotification(Intent i) {
        if (i == null) return false;
        if (i.getBooleanExtra("check_update", false)) {
            i.removeExtra("check_update");
            Updater.check(this, true);
            return true;
        }
        String f = i.getStringExtra("open_file");
        if (f != null) {
            String m = i.getStringExtra("open_model");
            i.removeExtra("open_file");
            h.postDelayed(() -> { if (!isFinishing()) { showTab(1); openViewer(f, m); } }, 500);
            return true;
        }
        return false;
    }

    /** Android 13+: ask once, with the reason, before the system prompt. */
    private void askNotifications() {
        if (Build.VERSION.SDK_INT < 33 || Tv.is(this) || Push.allowed(this) || Prefs.bool(this, "asked_notif", false)) return;
        Prefs.put(this, "asked_notif", true);
        Sheet sh = new Sheet(this, "Know when it's ready", "bell", Ui.pal());
        sh.note("Renders take a minute or more. Allow notifications and MIR MEDIA LABS tells you the moment your image, video or song "
                + "is done — with a preview — even when the app is closed. Your lab sends them directly; no outside service is involved.");
        sh.button("bell", "Allow notifications", true, () -> requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 71));
        sh.button("clock", "Not now", false, () -> {});
        sh.show();
    }

    private final Runnable loop = new Runnable() {
        @Override public void run() {
            if (!resumed) return;
            poll();
            boolean busy = status.optJSONObject("running") != null || status.optJSONArray("queued") != null && status.optJSONArray("queued").length() > 0;
            h.postDelayed(this, busy ? 2500 : 5000);
        }
    };

    // ── layout ────────────────────────────────────────────────────────────
    private void build() {
        Window w = getWindow();
        w.setStatusBarColor(Ui.BG);
        w.setNavigationBarColor(Ui.BG);
        // light themes (Paper) need dark status/nav bar icons, or the clock is white on white
        int lum = (int) (0.299 * ((Ui.BG >> 16) & 0xFF) + 0.587 * ((Ui.BG >> 8) & 0xFF) + 0.114 * (Ui.BG & 0xFF));
        if (lum > 160) {
            int fl = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (android.os.Build.VERSION.SDK_INT >= 26) fl |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            w.getDecorView().setSystemUiVisibility(w.getDecorView().getSystemUiVisibility() | fl);
        }
        LinearLayout root = Ui.vbox(this);
        root.setBackgroundColor(Ui.BG);

        LinearLayout top = Ui.hbox(this);
        top.setPadding(Ui.dp(12), Ui.dp(8), Ui.dp(8), Ui.dp(6));
        android.widget.ImageView logo = new android.widget.ImageView(this);
        logo.setImageResource(R.mipmap.ic_launcher);
        logo.setClipToOutline(true);
        logo.setBackground(Ui.box(9, 0, 0));
        top.addView(logo, Ui.lp(Ui.dp(26), Ui.dp(26)));
        TextView brand = Ui.bold(this, "MIR MEDIA LABS", 14, Ui.INK);
        brand.setLetterSpacing(0.2f);
        Ui.gradientText(brand, 0xFFFFC21A, 0xFFFF5A1F);
        top.addView(brand, Ui.margins(Ui.lpw(1), 10, 0, 0, 0));
        pill = Ui.mono(this, "…", 10.5f, Ui.DIM);
        pill.setPadding(Ui.dp(10), Ui.dp(5), Ui.dp(10), Ui.dp(5));
        pill.setBackground(Ui.box(99, Ui.CARD, Ui.LINE));
        top.addView(pill);
        popBtn = Ui.text(this, "[[users]]", 17, Ui.DIM);             // population: who is online right now (app only)
        popBtn.setPadding(Ui.dp(12), Ui.dp(2), Ui.dp(2), Ui.dp(2));
        popBtn.setOnClickListener(v -> population());
        top.addView(popBtn);
        TextView aa = Ui.text(this, "[[palette]]", 17, Ui.DIM);      // theme picker (font lives in the ⋮ menu), same as the web header
        aa.setPadding(Ui.dp(12), Ui.dp(2), Ui.dp(2), Ui.dp(2));
        aa.setOnClickListener(v -> Theme.pick(this));
        top.addView(aa);
        voiceBtn = Ui.text(this, "[[volume]]", 17, Ui.DIM);           // MUSE voice on / off (same as the web header)
        voiceBtn.setPadding(Ui.dp(10), Ui.dp(2), Ui.dp(2), Ui.dp(2));
        voiceBtn.setOnClickListener(v -> voice.toggle());
        top.addView(voiceBtn);
        voiceIcon();
        menu = Ui.text(this, "⋮", 22, Ui.DIM);
        menu.setPadding(Ui.dp(12), Ui.dp(2), Ui.dp(8), Ui.dp(2));
        menu.setOnClickListener(this::openMenu);
        top.addView(menu);
        root.addView(top);

        wide = isWide();
        create = new CreatePage(this);
        library = new LibraryPage(this);
        if (wide) {                                          // TABLET: three columns, like the web studio
            LinearLayout cols = Ui.hbox(this);
            cols.addView(leftColumn(), new LinearLayout.LayoutParams(Ui.dp(240), Ui.MATCH));
            cols.addView(divider(), new LinearLayout.LayoutParams(Math.max(1, Ui.dp(1)), Ui.MATCH));
            cols.addView(create, new LinearLayout.LayoutParams(0, Ui.MATCH, 1));
            cols.addView(divider(), new LinearLayout.LayoutParams(Math.max(1, Ui.dp(1)), Ui.MATCH));
            int sw = getResources().getConfiguration().screenWidthDp;
            cols.addView(library, new LinearLayout.LayoutParams(Ui.dp(sw >= 1200 ? 420 : 340), Ui.MATCH));
            root.addView(cols, new LinearLayout.LayoutParams(Ui.MATCH, 0, 1));
        } else {
            FrameLayout pages = new FrameLayout(this);
            pages.addView(create);
            pages.addView(library);
            root.addView(pages, new LinearLayout.LayoutParams(Ui.MATCH, 0, 1));
        }

        LinearLayout bar = Ui.hbox(this);
        bar.setBackgroundColor(Ui.BAR);
        String[] names = {"CHAT", "LIBRARY"};
        for (int i = 0; i < 2; i++) {
            final int ix = i;
            TextView t = Ui.bold(this, names[i], 11.5f, Ui.DIM);
            t.setLetterSpacing(0.16f);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, Ui.dp(10), 0, Ui.dp(10));
            t.setOnClickListener(v -> showTab(ix));
            tabs[i] = t;
            bar.addView(t, Ui.lpw(1));
        }
        qBadge = tabs[0];
        if (!wide) root.addView(bar);                    // tablet: both pages are always on screen, no tabs
        setContentView(root);
        Ui.insets(root);
        Tv.install(this);
        if (Tv.is(this)) {
            for (TextView t : tabs) t.setFocusable(true);
            menu.setFocusable(true);
            menu.setPadding(Ui.dp(16), Ui.dp(4), Ui.dp(12), Ui.dp(4));
        }
        showTab(0);
    }

    void showTab(int i) {
        tab = i;
        if (wide) { create.setVisibility(View.VISIBLE); library.setVisibility(View.VISIBLE); return; }
        create.setVisibility(i == 0 ? View.VISIBLE : View.GONE);
        library.setVisibility(i == 1 ? View.VISIBLE : View.GONE);
        for (int k = 0; k < 2; k++) {
            tabs[k].setTextColor(k == i ? Ui.INK : Ui.DIM);
            tabs[k].setBackground(k == i ? Ui.box(0, Ui.alpha(accent(), 0.12f), 0) : null);
        }
        if (i == 1) library.reload();
    }

    private void openMenu(View anchor) {
        Sheet sh = new Sheet(this, "Media Lab", "lab", Ui.pal());
        if (!BuildConfig.PLAY) sh.row("heart", "Support on Patreon", "keep MIR MEDIA LABS free · patreon.com/cw/MirCorp", () -> open(Creator.PATREON));
        sh.section("Create");
        sh.row("layers", "LoRA samples", "browse + apply community LoRAs", () -> loras.browse(Loras.roleOf(cur), ""));
        sh.row("sparkle", "Skills", "one tuned render", () -> { withSkills(() -> pickSkill(false)); });
        sh.row("chain", "Pipelines", "chained renders, one request", () -> { withSkills(() -> pickSkill(true)); });
        sh.row("book", "Command book", "every slash command", this::commandBook);
        sh.section("Look");
        sh.row("palette", "Theme", "Claude Dark · Graphite · Obsidian · Midnight · Paper", () -> Theme.pick(this));
        sh.row("type", "Font", "MIR FONTS", () -> Fonts.pick(this, api));
        sh.row("volume", "MUSE voice", "natural voice made on the lab PC · voice + speed", () -> voice.pick());
        sh.row("expand", "Layout", layoutLabel(), this::pickLayout);
        sh.section("App");
        sh.row("qr", "My key", "your key as a QR code · one device per key", () -> myKey(false));
        sh.row("server", "Server & access key", Api.host(Prefs.activeUrl(this)) + (Prefs.onLan(this) ? " · home Wi-Fi" : " · away"), () -> startActivity(new Intent(this, SetupActivity.class)));
        sh.row("bell", "Notifications", Push.allowed(this) ? (Push.instant(this) ? "on · instant delivery" : "on") : "off on this phone", () -> Push.settings(this));
        if (!BuildConfig.PLAY) sh.row("download", "Check for updates", "installed v" + Updater.installedName(this) + " · GitHub + your lab", () -> Updater.check(this, true));
        sh.row("shield", "Isolation audit", "proof it never touches MirOS data", () -> api.get("/api/isolation", r -> {
            JSONObject j = r.obj();
            info("Isolation audit", r.ok() ? ("Separate from MirOS: " + (j.optBoolean("separate_from_miros") ? "YES" : "NO")
                    + "\n\nOwn folders:\n" + j.optJSONObject("own_folders") + "\n\nNever contacts:\n" + j.optJSONArray("never_talks_to")).replace("\\\\", "\\") : r.err());
        }));
        sh.section("About");
        sh.row("lab", "MIR MEDIA LABS v" + Updater.installedName(this), "by MirCorp · © 2026 MirCorp · GPL-3.0", this::about);
        sh.row("bug", "Report a bug", "email the developer with device details", () -> mail("Bug report", true));
        sh.row("note", "Send feedback", "ideas, requests, praise", () -> mail("Feedback", false));
        if (!BuildConfig.PLAY) sh.row("heart", "Support development", "Patreon", () -> open(Creator.PATREON));   // Play: no outside payment links
        sh.row("code", "Source code", "GitHub", () -> open(Creator.GITHUB));
        sh.show();
    }

    /** My key: this person's own invite (or bare key) as a QR, drawn natively from the lab's QR matrix.
     *  The owner's MASTER key is never served to a phone — the lab answers 403 and only shows it on the host PC. */
    void myKey(boolean keyOnly) {
        api.get("/api/my-key", r -> {
            if (!r.ok()) { toast(r.err()); return; }
            JSONObject j = r.obj();
            api.get("/api/my-key/qr?fmt=matrix&kind=" + (keyOnly ? "key" : "invite"), q -> {
                if (!q.ok()) { toast(q.err()); return; }
                Sheet sh = new Sheet(this, keyOnly ? "My key · key only" : "My key · full invite", "qr", Ui.pal());
                android.widget.ImageView iv = new android.widget.ImageView(this);
                iv.setImageBitmap(qrBitmap(q.obj()));
                iv.setBackground(Ui.box(12, 0xFFFFFFFF, 0));
                LinearLayout wrap = Ui.hbox(this);
                wrap.setGravity(android.view.Gravity.CENTER);
                wrap.addView(iv, Ui.lp(Ui.dp(240), Ui.dp(240)));
                sh.add(wrap);
                sh.note("Signed in as " + j.optString("name") + ". Your key works on ONE device — this one. Moving to a new phone? Ask the host to reset your device, then scan this on the new one."
                        + (keyOnly ? " Key only is for a device that already has the lab's address." : "")
                        + (j.optBoolean("away") ? " Works at home and away." : " Home Wi-Fi only until the host sets an away address."));
                sh.rowStay(keyOnly ? "link" : "key", keyOnly ? "Show full invite" : "Show key only",
                        keyOnly ? "lab address + key in one scan" : "for a device that already has the lab's address",
                        () -> { sh.dismiss(); myKey(!keyOnly); });
                sh.row("copy", "Copy key", j.optString("key"), () -> copyText("MIR MEDIA LABS key", j.optString("key")));
                sh.row("copy", "Copy invite link", "send it to your other device", () -> copyText("MIR MEDIA LABS invite", j.optString("invite")));
                sh.show();
            });
        });
    }

    /** QR matrix {size, rows:["0101…"]} → crisp bitmap with a 4-module quiet zone. */
    static android.graphics.Bitmap qrBitmap(JSONObject o) {
        JSONArray rows = o.optJSONArray("rows");
        int n = o.optInt("size"), s = 8, q = 4, w = (n + 2 * q) * s;
        int[] px = new int[w * w];
        java.util.Arrays.fill(px, 0xFFFFFFFF);
        for (int y = 0; rows != null && y < n; y++) {
            String row = rows.optString(y);
            for (int x = 0; x < n && x < row.length(); x++) {
                if (row.charAt(x) != '1') continue;
                for (int dy = 0; dy < s; dy++) java.util.Arrays.fill(px, ((y + q) * s + dy) * w + (x + q) * s, ((y + q) * s + dy) * w + (x + q + 1) * s, 0xFF000000);
            }
        }
        return android.graphics.Bitmap.createBitmap(px, w, w, android.graphics.Bitmap.Config.ARGB_8888);
    }

    void copyText(String label, String text) {
        android.content.ClipboardManager cm = (android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        if (cm != null) { cm.setPrimaryClip(android.content.ClipData.newPlainText(label, text)); toast("Copied"); }
    }

    void about() {
        info("About", "MIR MEDIA LABS v" + Updater.installedName(this) + "\n\nCreated by " + Creator.NAME
                + "\n© 2026 " + Creator.NAME + ". Licensed under GPL-3.0.\n\"MirCorp\" and \"MIR MEDIA LABS\" are trademarks of MirCorp."
                + "\n\nContact: " + Creator.EMAIL + "\nSource: " + Creator.GITHUB + (BuildConfig.PLAY ? "" : "\nSupport: " + Creator.PATREON));
    }

    void open(String url) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))); } catch (Exception e) { toast("No browser found"); }
    }

    /** Bug report / feedback → the user's own mail app. Nothing is sent without them pressing Send. */
    void mail(String kind, boolean diag) {
        String body = diag ? "What happened:\n\n\nSteps to reproduce:\n1. \n\nExpected:\n\n\n---\nApp: v" + Updater.installedName(this)
                + "\nAndroid: " + android.os.Build.VERSION.RELEASE + " (SDK " + android.os.Build.VERSION.SDK_INT + ")"
                + "\nDevice: " + android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL + "\n" : "";
        Intent i = new Intent(Intent.ACTION_SENDTO, android.net.Uri.parse("mailto:"));
        i.putExtra(Intent.EXTRA_EMAIL, new String[]{Creator.EMAIL});
        i.putExtra(Intent.EXTRA_SUBJECT, "[MML " + kind + "] v" + Updater.installedName(this));
        i.putExtra(Intent.EXTRA_TEXT, body);
        try { startActivity(Intent.createChooser(i, kind)); } catch (Exception e) { info(kind, "No mail app found. Email " + Creator.EMAIL); }
    }

    /** "an image", "a video" */
    static String an(String w) { return (!w.isEmpty() && "aeiou".indexOf(Character.toLowerCase(w.charAt(0))) >= 0 ? "an " : "a ") + w; }

    void info(String title, String msg) {
        Sheet sh = new Sheet(this, title, "note", Ui.pal());
        sh.note(msg);
        sh.show();
    }
    void toast(String s) { Toast.makeText(this, s, Toast.LENGTH_SHORT).show(); }

    // ── state ─────────────────────────────────────────────────────────────
    JSONObject model(String k) { JSONObject m = models.optJSONObject(k); return m == null ? new JSONObject() : m; }
    int colorOf(String k) { return Ui.color(model(k).optString("color", "#ff5a1f"), Ui.VIO); }
    int accent() { return Ui.VIO; }   // theme accent
    static String shortName(String k) {
        switch (k == null ? "" : k) {
            case "auto": return "AUTO";
            case "h3": return "H3";
            case "music3": return "MUSIC 3";
            case "qimg": return "QWEN";
            case "ace": return "ACE";
            case "llama": return "MUSE";
            default: return "";
        }
    }

    void setModel(String k) {
        cur = k;
        Prefs.put(this, "model2", k);
        create.render();
        showTab(tab);
    }

    void refreshModels() {
        api.get("/api/models", r -> {
            if (!r.ok()) { pill.setText(r.err()); pill.setTextColor(Ui.RED); return; }
            models = r.obj();
            if (!models.has(cur)) cur = "auto";
            create.render();
            create.renderThread(jobs, true);
            Tv.focusify(create);
        });
    }

    // -- tablet mode -----------------------------------------------------------------------------------
    boolean isWide() {
        String mode = Prefs.str(this, "layout", "auto");
        if ("tablet".equals(mode)) return true;
        if ("phone".equals(mode)) return false;
        return getResources().getConfiguration().screenWidthDp >= 840;
    }

    private String layoutLabel() {
        String mode = Prefs.str(this, "layout", "auto");
        return "tablet".equals(mode) ? "Tablet · three columns" : "phone".equals(mode) ? "Phone · tabs" : "Auto · three columns on big screens";
    }

    private void pickLayout() {
        String[] ids = {"auto", "tablet", "phone"};
        String[] lbl = {"Auto (three columns on big screens)", "Tablet (always three columns)", "Phone (chat / library tabs)"};
        int sel = java.util.Arrays.asList(ids).indexOf(Prefs.str(this, "layout", "auto"));
        new android.app.AlertDialog.Builder(this).setTitle("Layout").setSingleChoiceItems(lbl, Math.max(0, sel), (d, k) -> {
            d.dismiss();
            Prefs.put(this, "layout", ids[k]);
            if (isWide() != wide) recreate();
        }).show();
    }

    @Override public void onConfigurationChanged(android.content.res.Configuration c) {
        super.onConfigurationChanged(c);
        if (isWide() != wide) recreate();               // rotated / unfolded / window resized across the tablet line
    }

    private View divider() { View v = new View(this); v.setBackgroundColor(Ui.LINE); return v; }

    /** Left column (tablet): the model list, then the create tools - the web studio left panel. */
    private View leftColumn() {
        android.widget.ScrollView sv = new android.widget.ScrollView(this);
        sv.setFillViewport(true);
        LinearLayout col = Ui.vbox(this);
        col.setPadding(Ui.dp(12), Ui.dp(8), Ui.dp(10), Ui.dp(12));
        col.addView(Ui.label(this, "Models"), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 2, 2, 0, 8));
        col.addView(create.modelPane(), Ui.lp(Ui.MATCH, Ui.WRAP));
        col.addView(Ui.label(this, "Create"), Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 2, 16, 0, 8));
        String[][] tools = {{"layers", "LoRA samples"}, {"sparkle", "Skills"}, {"chain", "Pipelines"}, {"book", "Command book"}, {"volume", "MUSE voice"}};
        Runnable[] acts = {() -> loras.browse(Loras.roleOf(cur), ""), () -> withSkills(() -> pickSkill(false)),
                () -> withSkills(() -> pickSkill(true)), this::commandBook, () -> voice.pick()};
        for (int i = 0; i < tools.length; i++) {
            TextView r = Ui.text(this, "[[" + tools[i][0] + "]]  " + tools[i][1], 13, Ui.DIM);
            r.setPadding(Ui.dp(10), Ui.dp(9), Ui.dp(10), Ui.dp(9));
            r.setBackground(Ui.box(10, 0, Ui.LINE));
            r.setFocusable(Tv.is(this));
            final Runnable go = acts[i];
            r.setOnClickListener(v -> go.run());
            col.addView(r, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 6));
        }
        sv.addView(col);
        return sv;
    }

    private void popCount(int n) {
        String t = "[[users]]" + (n > 0 ? " " + n : "");
        popBtn.setTextColor(n > 1 ? Ui.GRN : Ui.DIM);
        Icons.set(popBtn, t);
    }

    /** Population: everyone signed in to this lab and live in the last ~90 s — names + device kind only. */
    void population() {
        api.get("/api/online", r -> {
            if (!r.ok()) { toast(r.err()); return; }
            JSONObject o = r.obj();
            JSONArray a = o.optJSONArray("people");
            popCount(o.optInt("live"));
            Sheet sh = new Sheet(this, "Online now · " + o.optInt("live"), "users", Ui.pal());
            for (int i = 0; a != null && i < a.length(); i++) {
                JSONObject p = a.optJSONObject(i);
                JSONArray d = p.optJSONArray("devices");
                String devs = "";
                for (int k = 0; d != null && k < d.length(); k++) devs += (k > 0 ? " · " : "") + d.optString(k);
                String name = p.optString("name") + (p.optBoolean("you") ? "  (you)" : "") + (p.optBoolean("host") ? "  · HOST" : "");
                String sub = (p.optBoolean("creating") ? "creating now" : "online") + (devs.isEmpty() ? "" : "  ·  " + devs);
                sh.row(p.optBoolean("host") ? "server" : "user", name, sub, p.optBoolean("creating") ? Ui.AMB : Ui.GRN, () -> { });
            }
            if (a == null || a.length() == 0) sh.note("Nobody else is online right now.");
            sh.show();
        });
    }

    void voiceIcon() {
        if (voiceBtn == null) return;
        String t = voice.on ? "[[volume]]" : "[[mute]]";
        voiceBtn.setText(t);
        Icons.set(voiceBtn, t);
        voiceBtn.setAlpha(voice.on ? 1f : .55f);
    }

    void poll() {
        if (tick++ % 2 == 0) api.get("/api/status", r -> {
            if (!r.ok()) { pill.setText("OFFLINE"); pill.setTextColor(Ui.RED); return; }
            status = r.obj();
            JSONObject c = status.optJSONObject("comfy");
            boolean up = c != null && c.optBoolean("up");
            boolean running = status.optJSONObject("running") != null;
            int q = (status.optJSONArray("queued") == null ? 0 : status.optJSONArray("queued").length()) + (running ? 1 : 0);
            pill.setText((up ? (running ? "● RENDERING" : "● READY") : "● GPU OFFLINE") + (Prefs.onLan(this) ? " · HOME" : " · REMOTE"));
            pill.setTextColor(up ? (running ? Ui.AMB : Ui.GRN) : Ui.RED);
            qBadge.setText(q > 0 ? "CHAT · " + q + " ⟳" : "CHAT");
            create.renderModels();
        });
        if (tick % 6 == 1) api.get("/api/online", r -> { if (r.ok()) popCount(r.obj().optInt("live")); });
        api.get("/api/jobs?limit=40", r -> {
            if (!r.ok()) return;
            jobs = r.arr();
            JSONObject fresh = null;
            for (int i = 0; i < jobs.length() && !PushService.running; i++) {   // started elsewhere (web / PC)? track it too
                JSONObject j = jobs.optJSONObject(i);
                String st = j.optString("status");
                if (("queued".equals(st) || "running".equals(st)) && (!j.has("mine") || j.optBoolean("mine"))) { PushService.start(this); break; }
            }
            for (int i = 0; i < jobs.length(); i++) {
                JSONObject j = jobs.optJSONObject(i);
                if (!"done".equals(j.optString("status"))) continue;
                if (!seeded) { seenDone.add(j.optString("id")); continue; }
                if (seenDone.add(j.optString("id")) && fresh == null) fresh = j;
            }
            seeded = true;
            if (fresh != null) {
                toast(shortName(fresh.optString("model")) + " finished");
                library.reload();
            }
            create.renderThread(jobs, false);
            Tv.focusify(create);
        });
    }

    // ── generate ──────────────────────────────────────────────────────────
    void generate(String prompt) {
        String lc = prompt.toLowerCase();
        if (lc.equals("/help") || lc.equals("/commands")) { create.clearPrompt(); commandBook(); return; }
        if (lc.equals("/skills")) { create.clearPrompt(); skillsMenu(); return; }
        for (JSONObject a : atts) if (a.optBoolean("uploading")) { toast("Wait for the uploads to finish"); return; }
        if (prompt.isEmpty() && atts.isEmpty()) { toast("Write a prompt or attach a reference"); return; }
        JSONArray refs = new JSONArray();
        for (JSONObject a : atts) refs.put(a.optString("name"));
        JSONObject body = Api.obj("model", cur, "prompt", prompt, "refs", refs, "loras", loras.forRender(cur));
        if (recipeOf(prompt) != null) try { body.put("knobs", knobs); } catch (Exception ignored) { }
        api.post("/api/generate", body, r -> {
            if (!r.ok()) { toast(r.err()); return; }
            voice.mine(r.obj().optString("id"));
            atts.clear();
            saveAtts();
            create.clearPrompt();
            create.renderAtts();
            toast("Queued on " + model(cur).optString("label"));
            PushService.start(this);      // live status + "it's ready" notification even if you leave the app
            tick = 0;
            poll();
        });
    }

    void cancel(String id) { api.post("/api/jobs/" + id + "/cancel", null, r -> { toast(r.ok() ? "Cancelling…" : r.err()); poll(); }); }

    // ── attachments ───────────────────────────────────────────────────────
    void loadAtts() {
        try {
            JSONArray a = new JSONArray(Prefs.str(this, "atts", "[]"));
            for (int i = 0; i < a.length(); i++) atts.add(a.getJSONObject(i));
        } catch (Exception ignored) {}
    }
    void saveAtts() {
        JSONArray a = new JSONArray();
        for (JSONObject o : atts) if (!o.optBoolean("uploading")) a.put(o);
        Prefs.put(this, "atts", a.toString());
    }

    // ── skills · pipelines · command book (same /api/skills catalog as the web studio) ──
    private JSONObject skillCat;

    void withSkills(Runnable then) {
        if (skillCat != null) { then.run(); return; }
        api.get("/api/skills", r -> { if (!r.ok()) { toast(r.err()); return; } skillCat = r.obj(); then.run(); });
    }

    // ── recipes: a skill / manual typed as "/id …" shows its steps, slots and dials above the composer ──
    JSONObject knobs = new JSONObject();
    private String knobFor = "";

    /** The skill or manual the message starts with ("/myvoice …"), tagged with "type"; null if none / catalog not loaded. */
    JSONObject recipeOf(String prompt) {
        if (skillCat == null || prompt == null) return null;
        java.util.regex.Matcher mm = java.util.regex.Pattern.compile("^/(?:(?:skill|pipe|pipeline)\\s+)?([A-Za-z0-9]+)(\\s|$)").matcher(prompt);
        if (!mm.find()) return null;
        String id = mm.group(1).toLowerCase();
        for (String t : new String[]{"pipelines", "skills"}) {
            JSONArray a = skillCat.optJSONArray(t);
            for (int i = 0; a != null && i < a.length(); i++) {
                JSONObject o = a.optJSONObject(i);
                if (!id.equals(o.optString("id"))) continue;
                if (!id.equals(knobFor)) { knobFor = id; knobs = new JSONObject(); }
                try { return new JSONObject(o.toString()).put("type", t.equals("pipelines") ? "pipeline" : "skill"); } catch (Exception e) { return null; }
            }
        }
        return null;
    }

    /** {"audio": 1} → "an audio file" (also reads the old single-kind "needs" string). */
    static String needText(JSONObject o) {
        JSONObject n = o.optJSONObject("need");
        if (n == null) n = o.optJSONObject("needs");
        if (n == null && !o.optString("needs").isEmpty()) n = Api.obj(o.optString("needs"), 1);
        if (n == null || n.length() == 0) return "";
        StringBuilder s = new StringBuilder();
        for (java.util.Iterator<String> it = n.keys(); it.hasNext(); ) {
            String k = it.next();
            int c = n.optInt(k, 1);
            String w = "audio".equals(k) ? "audio file" : "image".equals(k) ? "picture" : "video".equals(k) ? "clip" : "text".equals(k) ? "text file" : k;
            s.append(s.length() > 0 ? " + " : "").append(c > 1 ? c + " " + w + "s" : an(w));
        }
        return s.toString();
    }

    /** Dials sheet: each knob's choices as rows (D-pad friendly); a range gets a few sensible stops. */
    void knobSheet(JSONObject rc) {
        JSONArray ks = rc.optJSONArray("knobs");
        if (ks == null) return;
        Sheet sh = new Sheet(this, rc.optString("name") + " · dials", "sliders", Ui.pal());
        for (int i = 0; i < ks.length(); i++) {
            final JSONObject kb = ks.optJSONObject(i);
            final String k = kb.optString("k");
            final boolean range = "range".equals(kb.optString("type"));
            String curV = knobs.has(k) ? knobs.optString(k) : String.valueOf(kb.opt("def"));
            sh.section(kb.optString("label"));
            java.util.List<String[]> opts = new java.util.ArrayList<>();
            if (range) {
                double lo = kb.optDouble("min"), hi = kb.optDouble("max");
                for (int s = 0; s < 5; s++) { String v = String.format(java.util.Locale.US, "%.2f", lo + (hi - lo) * s / 4); opts.add(new String[]{v, v}); }
            } else {
                JSONArray o = kb.optJSONArray("opts");
                for (int s = 0; o != null && s < o.length(); s++) {
                    JSONArray pr = o.optJSONArray(s);
                    opts.add(pr != null ? new String[]{pr.optString(0), pr.optString(1)} : new String[]{o.optString(s), o.optString(s)});
                }
            }
            for (String[] op : opts) {
                boolean on = op[0].equals(curV) || (range && isNum(curV) && Math.abs(Double.parseDouble(op[0]) - Double.parseDouble(curV)) < 0.06);
                sh.row(on ? "check-circle" : "dot", op[1], null, () -> {
                    try { if (op[0].isEmpty()) knobs.remove(k); else knobs.put(k, range ? (Object) Double.parseDouble(op[0]) : op[0]); } catch (Exception ignored) { }
                    create.renderRecipe();
                });
            }
        }
        sh.show();
    }

    private static boolean isNum(String s) { try { Double.parseDouble(s); return true; } catch (Exception e) { return false; } }

    void skillsMenu() {
        withSkills(() -> {
            Sheet sh = new Sheet(this, "Skills", "sparkle", Ui.pal());
            sh.grid(new String[][]{{"sparkle", "Skills"}, {"chain", "Pipelines"}, {"layers", "LoRAs"}, {"book", "Commands"}}, 2, w -> {
                if (w == 0) pickSkill(false); else if (w == 1) pickSkill(true); else if (w == 2) loras.browse(Loras.roleOf(cur), ""); else commandBook();
            });
            sh.show();
        });
    }

    private void pickSkill(boolean pipes) {
        JSONArray a = skillCat.optJSONArray(pipes ? "pipelines" : "skills");
        if (a == null) return;
        Sheet sh = new Sheet(this, pipes ? "Pipelines" : "Skills", pipes ? "chain" : "sparkle", Ui.pal());
        sh.search(pipes ? "Search pipelines…" : "Search skills…");
        String lastRole = "";
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            String role = o.optString("role", "");
            if (!pipes && !role.equals(lastRole)) { sh.section(role); lastRole = role; }
            String flow = "";
            JSONArray st = o.optJSONArray("steps");
            for (int k = 0; st != null && k < st.length(); k++) flow += (k > 0 ? " → " : "") + st.optJSONObject(k).optString("label");   // role, never the engine name
            final String need = needText(o);
            String sub = o.optString("desc") + (need.isEmpty() ? "" : "  ·  attach " + need) + (flow.isEmpty() ? "" : "\n" + flow);
            String ic = pipes ? "chain" : o.optString("icon", "sparkle");
            sh.row(ic, o.optString("name"), sub, () -> {
                create.setPrompt("/" + o.optString("id") + " ");
                toast(o.optString("name") + (need.isEmpty() ? " — describe it and send" : " — attach " + need + " first"));
            });
        }
        sh.show();
    }

    void commandBook() {
        withSkills(() -> {
            Sheet sh = new Sheet(this, "Command book", "book", Ui.pal());
            sh.search("Search commands, skills, pipelines…");
            sh.section("Commands");
            JSONArray c = skillCat.optJSONArray("commands");
            for (int i = 0; c != null && i < c.length(); i++) {
                JSONObject o = c.optJSONObject(i);
                final String cmd = o.optString("cmd");
                sh.cmd("command", cmd + (o.optString("args").isEmpty() ? "" : " " + o.optString("args")), o.optString("desc"), null, () -> create.setPrompt(cmd + " "));
            }
            sh.section("Skills  ·  /name <idea>");
            JSONArray s = skillCat.optJSONArray("skills");
            for (int i = 0; s != null && i < s.length(); i++) {
                JSONObject o = s.optJSONObject(i);
                final String id = o.optString("id");
                sh.cmd(o.optString("icon", "sparkle"), "/" + id, o.optString("name") + (needText(o).isEmpty() ? "" : " · needs " + needText(o)), null, () -> create.setPrompt("/" + id + " "));
            }
            sh.section("Pipelines  ·  /name <idea>");
            JSONArray p = skillCat.optJSONArray("pipelines");
            for (int i = 0; p != null && i < p.length(); i++) {
                JSONObject o = p.optJSONObject(i);
                final String id = o.optString("id");
                sh.cmd("chain", "/" + id, o.optString("name") + " — " + o.optString("desc") + (needText(o).isEmpty() ? "" : " · needs " + needText(o)), null, () -> create.setPrompt("/" + id + " "));
            }
            JSONArray t = skillCat.optJSONArray("tips");
            if (t != null && t.length() > 0) {
                sh.section("Tips");
                StringBuilder b = new StringBuilder();
                for (int i = 0; i < t.length(); i++) b.append(i > 0 ? "\n" : "").append("•  ").append(t.optString(i));
                sh.note(b.toString());
            }
            sh.show();
        });
    }

    /** Raw original file → phone Downloads/MirMediaLabs. The app streams it itself (same connection + key as the
     *  players) and writes through MediaStore, so it shows up in Files / Downloads / Gallery right away. */
    void downloadFile(String fn) {
        toast("Downloading " + fn + " …");
        final String url = api.mediaUrl("/media/" + Api.enc(fn) + "?dl=1");
        Api.POOL.execute(() -> {
            String err = null;
            android.net.Uri item = null;
            android.content.ContentResolver cr = getContentResolver();
            try {
                java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
                c.setConnectTimeout(15000);
                c.setReadTimeout(60000);
                c.setRequestProperty("X-MML-Key", Prefs.key(this));
                c.setRequestProperty("X-MML-Device", Prefs.deviceId(this));
                if (c.getResponseCode() != 200) throw new Exception("server said " + c.getResponseCode());
                String mime = c.getContentType();
                java.io.OutputStream out;
                java.io.File legacy = null;
                if (android.os.Build.VERSION.SDK_INT >= 29) {
                    android.content.ContentValues v = new android.content.ContentValues();
                    v.put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, fn);
                    if (mime != null) v.put(android.provider.MediaStore.MediaColumns.MIME_TYPE, mime.split(";")[0]);
                    v.put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS + "/MirMediaLabs");
                    v.put(android.provider.MediaStore.MediaColumns.IS_PENDING, 1);
                    item = cr.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (item == null) throw new Exception("couldn't create the file");
                    out = cr.openOutputStream(item);
                } else {
                    java.io.File dir = new java.io.File(android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS), "MirMediaLabs");
                    dir.mkdirs();
                    legacy = new java.io.File(dir, fn);
                    out = new java.io.FileOutputStream(legacy);
                }
                try (java.io.InputStream in = c.getInputStream(); java.io.OutputStream o = out) {
                    byte[] buf = new byte[65536];
                    for (int n; (n = in.read(buf)) > 0; ) o.write(buf, 0, n);
                }
                if (item != null) {
                    android.content.ContentValues done = new android.content.ContentValues();
                    done.put(android.provider.MediaStore.MediaColumns.IS_PENDING, 0);
                    cr.update(item, done, null, null);
                } else if (legacy != null) {
                    android.media.MediaScannerConnection.scanFile(this, new String[]{legacy.getPath()}, null, null);
                }
            } catch (Exception e) {
                err = e.getMessage();
                if (item != null) try { cr.delete(item, null, null); } catch (Exception ignored) { }
            }
            final String fe = err;
            runOnUiThread(() -> toast(fe == null ? "Saved to Downloads/MirMediaLabs/" + fn : "Download failed: " + fe));
        });
    }

    /** Phone composer [+]: everything the tool buttons did, in one menu. */
    void toolsMenu() {
        Sheet sh = new Sheet(this, "Message", "plus", Ui.pal());
        sh.row("attach", "Attach", "picture · clip · song · text", this::attachMenu);
        sh.row("sliders", "Parameters", "settings for the selected model", () -> openParams(cur));
        sh.row("layers", "LoRA samples", "browse + apply community LoRAs", () -> loras.browse(Loras.roleOf(cur), ""));
        sh.row("sparkle", "Skills", "one tuned render", () -> withSkills(() -> pickSkill(false)));
        sh.row("chain", "Pipelines", "chained renders, one request", () -> withSkills(() -> pickSkill(true)));
        sh.row("book", "Command book", "every slash command", this::commandBook);
        sh.show();
    }

    void attachMenu() {
        Sheet sh = new Sheet(this, "Attach reference", "attach", Ui.pal());
        sh.grid(new String[][]{{"folder", "Files"}, {"note", "Paste text"}, {"refresh", "Last result"}, {"layers", "LoRA"}}, 2, w -> {
            if (w == 0) pickFiles();
            else if (w == 1) pasteText();
            else if (w == 2) { if (create.lastResult != null) useAsRef(create.lastResult); else toast("No result yet"); }
            else loras.browse(Loras.roleOf(cur), "");
        });
        sh.note("Images, clips, songs or text — each model uses what it understands. LoRAs apply a trained style or identity on top.");
        sh.show();
    }

    private void pickFiles() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/*", "video/*", "audio/*", "text/*"});
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        startActivityForResult(i, PICK);
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK || res != RESULT_OK || data == null) return;
        if (data.getClipData() != null) {
            for (int i = 0; i < data.getClipData().getItemCount(); i++) upload(data.getClipData().getItemAt(i).getUri());
        } else if (data.getData() != null) upload(data.getData());
    }

    void upload(Uri u) {
        JSONObject ph = Api.obj("label", "uploading", "uploading", true, "pct", 0);
        atts.add(ph);
        create.renderAtts();
        api.upload(u, pct -> { try { ph.put("pct", pct); } catch (Exception ignored) {} create.renderAtts(); }, r -> {
            int i = atts.indexOf(ph);
            if (!r.ok()) { if (i >= 0) atts.remove(i); toast("Upload failed: " + r.err()); }
            else if (i >= 0) atts.set(i, r.obj());
            saveAtts();
            create.renderAtts();
        });
    }

    private void pasteText() {
        LinearLayout box = Ui.vbox(this);
        box.setPadding(Ui.dp(20), Ui.dp(6), Ui.dp(20), 0);
        EditText e = new EditText(this);
        e.setMinLines(6);
        e.setGravity(Gravity.TOP);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        e.setHint("[Verse]\n…\n\n[Chorus]\n…");
        box.addView(e);
        new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert).setTitle("Attach text").setView(box)
                .setPositiveButton("Attach", (d, w) -> attachText(e.getText().toString(), "note"))
                .setNegativeButton("Cancel", null).show();
    }

    void attachText(String text, String name) {
        if (text.trim().isEmpty()) return;
        api.post("/api/upload-text", Api.obj("text", text, "name", name), r -> {
            if (!r.ok()) { toast(r.err()); return; }
            atts.add(r.obj());
            saveAtts();
            create.renderAtts();
        });
    }

    void useAsRef(String name) {
        api.post("/api/library/" + Api.enc(name) + "/use", null, r -> {
            if (!r.ok()) { toast(r.err()); return; }
            atts.add(r.obj());
            saveAtts();
            create.renderAtts();
            toast("Attached as a reference");
            showTab(0);
        });
    }

    /** Share sheet → Media Lab: pictures / clips / songs / text become references. */
    private void handleShare(Intent i) {
        if (i == null || api == null) return;
        String a = i.getAction();
        if (Intent.ACTION_SEND.equals(a)) {
            Uri u = Build.VERSION.SDK_INT >= 33 ? i.getParcelableExtra(Intent.EXTRA_STREAM, Uri.class) : i.getParcelableExtra(Intent.EXTRA_STREAM);
            if (u != null) upload(u);
            else if (i.getStringExtra(Intent.EXTRA_TEXT) != null) attachText(i.getStringExtra(Intent.EXTRA_TEXT), "shared");
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(a)) {
            ArrayList<Uri> us = Build.VERSION.SDK_INT >= 33 ? i.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri.class)
                    : i.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (us != null) for (Uri u : us) upload(u);
        } else return;
        setIntent(new Intent());
        showTab(0);
    }

    void openViewer(String name, String model) { voice.stop(); new Viewer(this, name, model).show(); }
    void openParams(String k) {
        if ("auto".equals(k)) {
            info("Auto · MUSE Director", "MUSE reads every message and decides what happens: it answers questions and writes "
                    + "(lyrics, scripts, ideas), or renders on the right model (image, video, song, music), picks a skill "
                    + "preset, or runs a pipeline.\n\nFollow-ups work: \"now animate it\" or \"make a song for that\" reuse "
                    + "your last result.\n\nFlags you type (--8s, --vertical, --bpm 120) are always kept. Slash commands and "
                    + "picking a model yourself skip MUSE. Each model keeps its own settings: long-press a model to change them.");
            return;
        }
        new ParamsDialog(this, k).show();
    }

    void libraryChanged() { library.reload(); }

    void reuse(String model, String prompt) { reuse(model, prompt, null); }

    /** "Again": prompt AND the job's references back in the composer — so a re-run after a cancel
     *  stays image/video-to-video instead of quietly dropping to text-only. */
    void reuse(String model, String prompt, JSONArray refs) {
        setModel(model);
        create.setPrompt(prompt);
        int added = 0;
        for (int i = 0; refs != null && i < refs.length(); i++) {
            String n = refs.optString(i);
            boolean have = false;
            for (JSONObject a : atts) if (n.equals(a.optString("name"))) have = true;
            if (n.isEmpty() || have) continue;
            String[] parts = n.split("_", 3);
            atts.add(Api.obj("name", n, "kind", Ui.kindOf(n), "url", "/refs/" + n, "label", n.startsWith("ref_") && parts.length == 3 ? parts[2] : n));
            added++;
        }
        if (added > 0) { saveAtts(); create.renderAtts(); toast("Prompt + " + added + " reference" + (added > 1 ? "s" : "") + " loaded — press Send"); }
        showTab(0);
    }
}
