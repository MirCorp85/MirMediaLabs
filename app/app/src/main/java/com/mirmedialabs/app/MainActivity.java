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
    static final String[] ORDER = {"h3", "music3", "qimg", "ace", "llama"};
    static final int PICK = 41;

    Api api;
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
    private final Handler h = new Handler(Looper.getMainLooper());
    private int tick = 0;
    private boolean resumed = false;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Ui.init(this);
        Fonts.apply(this);   // MIR FONTS pick, before any view is built
        Theme.apply(this);   // MIR MEDIA LABS theme (same five palettes as the web)
        if (!Prefs.configured(this)) { startActivity(new Intent(this, SetupActivity.class)); finish(); return; }
        api = new Api(this);
        loras = new Loras(this);
        cur = Prefs.str(this, "model", "h3");
        loadAtts();
        build();
        api.probe(() -> { refreshModels(); poll(); library.reload(); Updater.check(this, false); Fonts.sync(this, api); Theme.sync(this, api); loras.refresh(null); });
        handleShare(getIntent());
    }

    @Override public void onBackPressed() {
        if (tab != 0) showTab(0);
        else super.onBackPressed();
    }

    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); handleShare(i); }
    @Override protected void onResume() { super.onResume(); resumed = true; h.removeCallbacks(loop); h.postDelayed(loop, 400); }
    @Override protected void onPause() { super.onPause(); resumed = false; h.removeCallbacks(loop); }

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
        TextView aa = Ui.text(this, "[[palette]]", 17, Ui.DIM);      // theme picker (font lives in the ⋮ menu), same as the web header
        aa.setPadding(Ui.dp(12), Ui.dp(2), Ui.dp(2), Ui.dp(2));
        aa.setOnClickListener(v -> Theme.pick(this));
        top.addView(aa);
        menu = Ui.text(this, "⋮", 22, Ui.DIM);
        menu.setPadding(Ui.dp(12), Ui.dp(2), Ui.dp(8), Ui.dp(2));
        menu.setOnClickListener(this::openMenu);
        top.addView(menu);
        root.addView(top);

        FrameLayout pages = new FrameLayout(this);
        create = new CreatePage(this);
        library = new LibraryPage(this);
        pages.addView(create);
        pages.addView(library);
        root.addView(pages, new LinearLayout.LayoutParams(Ui.MATCH, 0, 1));

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
        root.addView(bar);
        setContentView(root);
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
        sh.row("heart", "Support on Patreon", "keep MIR MEDIA LABS free · patreon.com/MirCorp", () -> open(Creator.PATREON));
        sh.section("Create");
        sh.row("layers", "LoRA samples", "browse + apply community LoRAs", () -> loras.browse(Loras.roleOf(cur), ""));
        sh.row("sparkle", "Skills", "one tuned render", () -> { withSkills(() -> pickSkill(false)); });
        sh.row("chain", "Pipelines", "chained renders, one request", () -> { withSkills(() -> pickSkill(true)); });
        sh.row("book", "Command book", "every slash command", this::commandBook);
        sh.section("Look");
        sh.row("palette", "Theme", "Claude Dark · Graphite · Obsidian · Midnight · Paper", () -> Theme.pick(this));
        sh.row("type", "Font", "MIR FONTS", () -> Fonts.pick(this, api));
        sh.section("App");
        sh.row("server", "Server & access key", Prefs.activeUrl(this) + (Prefs.onLan(this) ? " · home Wi-Fi" : ""), () -> startActivity(new Intent(this, SetupActivity.class)));
        sh.row("download", "Check for updates", "installed v" + Updater.installedName(this), () -> Updater.check(this, true));
        sh.row("shield", "Isolation audit", "proof it never touches MirOS data", () -> api.get("/api/isolation", r -> {
            JSONObject j = r.obj();
            info("Isolation audit", r.ok() ? ("Separate from MirOS: " + (j.optBoolean("separate_from_miros") ? "YES" : "NO")
                    + "\n\nOwn folders:\n" + j.optJSONObject("own_folders") + "\n\nNever contacts:\n" + j.optJSONArray("never_talks_to")).replace("\\\\", "\\") : r.err());
        }));
        sh.section("About");
        sh.row("lab", "MIR MEDIA LABS v" + Updater.installedName(this), "by MirCorp · © 2026 MirCorp · GPL-3.0", this::about);
        sh.row("bug", "Report a bug", "email the developer with device details", () -> mail("Bug report", true));
        sh.row("note", "Send feedback", "ideas, requests, praise", () -> mail("Feedback", false));
        sh.row("heart", "Support development", "Patreon", () -> open(Creator.PATREON));
        sh.row("code", "Source code", "GitHub", () -> open(Creator.GITHUB));
        sh.show();
    }

    void about() {
        info("About", "MIR MEDIA LABS v" + Updater.installedName(this) + "\n\nCreated by " + Creator.NAME
                + "\n© 2026 " + Creator.NAME + ". Licensed under GPL-3.0.\n\"MirCorp\" and \"MIR MEDIA LABS\" are trademarks of MirCorp."
                + "\n\nContact: " + Creator.EMAIL + "\nSource: " + Creator.GITHUB + "\nSupport: " + Creator.PATREON);
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
        Prefs.put(this, "model", k);
        create.render();
        showTab(tab);
    }

    void refreshModels() {
        api.get("/api/models", r -> {
            if (!r.ok()) { pill.setText(r.err()); pill.setTextColor(Ui.RED); return; }
            models = r.obj();
            if (!models.has(cur)) cur = "h3";
            create.render();
            create.renderThread(jobs, true);
            Tv.focusify(create);
        });
    }

    void poll() {
        if (tick++ % 2 == 0) api.get("/api/status", r -> {
            if (!r.ok()) { pill.setText("OFFLINE"); pill.setTextColor(Ui.RED); return; }
            status = r.obj();
            if (create != null) create.mascot.update(null, status);
            JSONObject c = status.optJSONObject("comfy");
            boolean up = c != null && c.optBoolean("up");
            boolean running = status.optJSONObject("running") != null;
            int q = (status.optJSONArray("queued") == null ? 0 : status.optJSONArray("queued").length()) + (running ? 1 : 0);
            pill.setText((up ? (running ? "● RENDERING" : "● READY") : "● GPU OFFLINE") + (Prefs.onLan(this) ? " · HOME" : " · REMOTE"));
            pill.setTextColor(up ? (running ? Ui.AMB : Ui.GRN) : Ui.RED);
            qBadge.setText(q > 0 ? "CHAT · " + q + " ⟳" : "CHAT");
            create.renderModels();
        });
        api.get("/api/jobs?limit=40", r -> {
            if (!r.ok()) return;
            jobs = r.arr();
            JSONObject fresh = null;
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
        api.post("/api/generate", Api.obj("model", cur, "prompt", prompt, "refs", refs, "loras", loras.forRender(cur)), r -> {
            if (!r.ok()) { toast(r.err()); return; }
            atts.clear();
            saveAtts();
            create.clearPrompt();
            create.renderAtts();
            toast("Queued on " + model(cur).optString("label"));
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

    private void withSkills(Runnable then) {
        if (skillCat != null) { then.run(); return; }
        api.get("/api/skills", r -> { if (!r.ok()) { toast(r.err()); return; } skillCat = r.obj(); then.run(); });
    }

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
            String sub = o.optString("desc") + (o.has("needs") ? "  ·  attach " + an(o.optString("needs")) : "") + (flow.isEmpty() ? "" : "\n" + flow);
            String ic = pipes ? "chain" : o.optString("icon", "sparkle");
            sh.row(ic, o.optString("name"), sub, () -> {
                create.setPrompt("/" + o.optString("id") + " ");
                toast(o.optString("name") + (o.has("needs") ? " — attach " + an(o.optString("needs")) + " first" : " — describe it and send"));
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
                sh.cmd(o.optString("icon", "sparkle"), "/" + id, o.optString("name") + (o.has("needs") ? " · needs an attached " + o.optString("needs") : ""), null, () -> create.setPrompt("/" + id + " "));
            }
            sh.section("Pipelines  ·  /name <idea>");
            JSONArray p = skillCat.optJSONArray("pipelines");
            for (int i = 0; p != null && i < p.length(); i++) {
                JSONObject o = p.optJSONObject(i);
                final String id = o.optString("id");
                sh.cmd("chain", "/" + id, o.optString("name") + " — " + o.optString("desc"), null, () -> create.setPrompt("/" + id + " "));
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

    void openViewer(String name, String model) { new Viewer(this, name, model).show(); }
    void openParams(String k) { new ParamsDialog(this, k).show(); }

    void libraryChanged() { library.reload(); }

    void reuse(String model, String prompt) { setModel(model); create.setPrompt(prompt); showTab(0); }
}
