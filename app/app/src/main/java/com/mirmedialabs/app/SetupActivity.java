package com.mirmedialabs.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Sign-in: join a lab with the host's invite — scan its QR, paste the link (or let the app spot it on the
 * clipboard) — or type the addresses + key by hand. A connection doctor says exactly what failed and what to
 * try, and there's a step-by-step guide for using the lab away from home (router port forwarding).
 */
public class SetupActivity extends Activity {
    private static final int SCAN = 61;
    private EditText lan, remote, key;
    private LinearLayout manual, report, clip;
    private TextView go, manualHead;
    private boolean busy = false, editing = false, clipChecked = false;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Ui.init(this);
        Fonts.apply(this);
        Theme.apply(this);
        editing = Prefs.configured(this);
        Window w = getWindow();
        w.setStatusBarColor(Ui.BG);
        w.setNavigationBarColor(Ui.BG);
        if (Ui.LIGHT) {
            int fl = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | (Build.VERSION.SDK_INT >= 26 ? View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR : 0);
            w.getDecorView().setSystemUiVisibility(fl);
        }
        build();
        Tv.install(this);
        Tv.focusify(getWindow().getDecorView());
        handle(getIntent());
    }

    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); handle(i); }

    // ── layout ────────────────────────────────────────────────────────────
    private void build() {
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Ui.BG);
        sv.setFillViewport(true);
        FrameLayout center = new FrameLayout(this);
        sv.addView(center);
        LinearLayout box = Ui.vbox(this);
        box.setPadding(Ui.dp(22), Ui.dp(editing ? 26 : 44), Ui.dp(22), Ui.dp(28));
        int maxW = Math.min(getResources().getDisplayMetrics().widthPixels, Ui.dp(540));
        center.addView(box, new FrameLayout.LayoutParams(maxW, -2, Gravity.CENTER_HORIZONTAL));

        // header
        ImageView logo = new ImageView(this);
        logo.setImageResource(R.mipmap.ic_launcher);
        logo.setClipToOutline(true);
        logo.setBackground(Ui.box(18, 0, 0));
        LinearLayout.LayoutParams lp = Ui.lp(Ui.dp(68), Ui.dp(68));
        lp.gravity = Gravity.CENTER_HORIZONTAL;
        box.addView(logo, lp);
        TextView t = Ui.bold(this, "MIR MEDIA LABS", 23, Ui.INK);
        t.setLetterSpacing(0.16f);
        t.setGravity(Gravity.CENTER);
        Ui.gradientText(t, 0xFFFFC21A, 0xFFFF5A1F);
        box.addView(t, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 14, 0, 0));
        TextView h = Ui.bold(this, editing ? "Server & access key" : "Connect to your lab", 16, Ui.INK);
        h.setGravity(Gravity.CENTER);
        box.addView(h, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 0));
        TextView sub = Ui.text(this, "Your lab runs on a PC with a graphics card. Join it with the invite its host gave you — "
                + "you'll only see your own creations.", 13, Ui.DIM);
        sub.setGravity(Gravity.CENTER);
        sub.setLineSpacing(0, 1.3f);
        box.addView(sub, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 6, 8, 6, 20));

        // invite found on the clipboard (filled in later)
        clip = Ui.vbox(this);
        clip.setVisibility(View.GONE);
        box.addView(clip, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 14));

        // join with an invite
        box.addView(Ui.label(this, "Join with an invite"), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 2, 0, 0, 8));
        LinearLayout tiles = Ui.hbox(this);
        boolean cam = !Tv.is(this) && getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY);
        if (cam) tiles.addView(tile("scan", "Scan QR code", "point at the host's screen", v -> scan()), Ui.margins(Ui.lpw(1), 0, 0, 5, 0));
        tiles.addView(tile("link", "Paste invite link", "from a message or email", v -> paste()), Ui.margins(Ui.lpw(1), cam ? 5 : 0, 0, 0, 0));
        box.addView(tiles);

        // manual
        manualHead = Ui.text(this, "", 13, Ui.DIM);
        manualHead.setPadding(Ui.dp(4), Ui.dp(14), Ui.dp(4), Ui.dp(14));
        manualHead.setClickable(true);
        manualHead.setFocusable(true);
        manualHead.setOnClickListener(v -> showManual(manual.getVisibility() != View.VISIBLE));
        box.addView(manualHead, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 0));
        manual = Ui.vbox(this);
        manual.setPadding(Ui.dp(14), Ui.dp(16), Ui.dp(14), Ui.dp(6));
        manual.setBackground(Ui.box(16, Ui.CARD, Ui.LINE));
        lan = field(manual, "wifi", "Home Wi-Fi address", Prefs.lanUrl(this), "192.168.0.50:5400",
                "The PC's address on your home network. Shown in Host Control → Invite.", InputType.TYPE_TEXT_VARIATION_URI);
        remote = field(manual, "globe", "Away-from-home address  ·  optional", Prefs.remoteUrl(this), "my-lab.duckdns.org:5400",
                "Needed only outside your home Wi-Fi — see \"Use it away from home\" below.", InputType.TYPE_TEXT_VARIATION_URI);
        key = field(manual, "key", "Your access key", Prefs.key(this), "mml-…",
                "Personal key from the lab host. Each person has their own.", InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        key.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_GO);
        key.setOnEditorActionListener((v, act, ev) -> { connect(); return true; });
        box.addView(manual);

        go = Ui.button(this, "[[arrow-right]]  CONNECT", Ui.VIO, true);
        go.setOnClickListener(v -> connect());
        box.addView(go, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(50)), 0, 14, 0, 0));
        showManual(editing || Tv.is(this));      // TVs: typing (or the phone app) is the realistic way in

        report = Ui.vbox(this);
        box.addView(report, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 12, 0, 0));

        // help
        box.addView(Ui.label(this, "Help"), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 2, 22, 0, 8));
        box.addView(helpRow("router", "Use it away from home", "port forwarding on your router, step by step", v -> guide()));
        box.addView(helpRow("warn", "Can't connect?", "what each error means and how to fix it", v -> troubleshoot()), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 6, 0, 0));
        box.addView(helpRow("lab", "Don't have a lab yet?", "free for Windows PCs with an NVIDIA graphics card", v -> open(Creator.GITHUB)),
                Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 6, 0, 0));

        TextView foot = Ui.mono(this, "v" + Updater.installedName(this) + "  ·  by " + Creator.NAME + "  ·  GPL-3.0", 10.5f, Ui.FAINT);
        foot.setGravity(Gravity.CENTER);
        box.addView(foot, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 26, 0, 0));
        setContentView(sv);
    }

    private LinearLayout tile(String icon, String title, String sub, View.OnClickListener l) {
        LinearLayout t = Ui.vbox(this);
        t.setGravity(Gravity.CENTER_HORIZONTAL);
        t.setPadding(Ui.dp(10), Ui.dp(18), Ui.dp(10), Ui.dp(16));
        t.setBackground(Ui.box(16, Ui.alpha(Ui.VIO, 0.10f), Ui.alpha(Ui.VIO, 0.45f)));
        t.setClickable(true);
        t.setFocusable(true);
        t.setOnClickListener(l);
        TextView ic = Ui.text(this, "[[" + icon + "]]", 30, Ui.VIO);
        t.addView(ic, Ui.lp(Ui.WRAP, Ui.WRAP));
        TextView a = Ui.bold(this, title, 14, Ui.INK);
        a.setGravity(Gravity.CENTER);
        t.addView(a, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 10, 0, 0));
        TextView s = Ui.text(this, sub, 11.5f, Ui.DIM);
        s.setGravity(Gravity.CENTER);
        t.addView(s, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 4, 0, 0));
        return t;
    }

    private LinearLayout helpRow(String icon, String title, String sub, View.OnClickListener l) {
        LinearLayout r = Ui.hbox(this);
        r.setBaselineAligned(false);
        r.setPadding(Ui.dp(14), Ui.dp(12), Ui.dp(12), Ui.dp(12));
        r.setBackground(Ui.box(14, Ui.CARD, Ui.LINE));
        r.setClickable(true);
        r.setFocusable(true);
        r.setOnClickListener(l);
        r.addView(Ui.text(this, "[[" + icon + "]]", 18, Ui.VIO));
        LinearLayout tx = Ui.vbox(this);
        tx.addView(Ui.bold(this, title, 14, Ui.INK));
        TextView s = Ui.text(this, sub, 12, Ui.DIM);
        tx.addView(s, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 3, 0, 0));
        r.addView(tx, Ui.margins(Ui.lpw(1), 12, 0, 6, 0));
        r.addView(Ui.text(this, "[[chevron-right]]", 16, Ui.DIM));
        return r;
    }

    private EditText field(LinearLayout box, String icon, String label, String val, String hint, String help, int variation) {
        box.addView(Ui.label(this, label), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 2, 0, 0, 6));
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setText(val);
        e.setHint(hint);
        e.setTextColor(Ui.INK);
        e.setHintTextColor(Ui.FAINT);
        e.setTextSize(15);
        if (Ui.FONT != null) e.setTypeface(Ui.FONT);
        e.setInputType(InputType.TYPE_CLASS_TEXT | variation | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        e.setPadding(Ui.dp(12), Ui.dp(12), Ui.dp(12), Ui.dp(12));
        e.setBackground(Ui.box(12, Ui.LIGHT ? 0x0A000000 : 0x40000000, Ui.LINE2));
        e.setCompoundDrawablePadding(Ui.dp(10));
        e.setCompoundDrawables(Icons.drawable(icon, Ui.DIM, Ui.dp(18)), null, null, null);
        box.addView(e, Ui.lp(Ui.MATCH, Ui.WRAP));
        TextView hl = Ui.text(this, help, 11.5f, Ui.FAINT);
        hl.setLineSpacing(0, 1.2f);
        box.addView(hl, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 2, 6, 0, 14));
        return e;
    }

    private void showManual(boolean on) {
        manual.setVisibility(on ? View.VISIBLE : View.GONE);
        go.setVisibility(on || busy ? View.VISIBLE : View.GONE);     // invites connect by themselves
        Icons.set(manualHead, (on ? "[[chevron-down]]" : "[[chevron-right]]") + "  Or enter the address and key yourself");
    }

    // ── ways in ───────────────────────────────────────────────────────────
    private void handle(Intent i) {
        if (i == null) return;
        String text = null;
        if (Intent.ACTION_VIEW.equals(i.getAction()) && i.getData() != null) text = i.getData().toString();
        else if (Intent.ACTION_SEND.equals(i.getAction())) text = i.getStringExtra(Intent.EXTRA_TEXT);
        else if (i.hasExtra("invite")) text = i.getStringExtra("invite");
        if (text == null) return;
        Invite inv = Invite.parse(text);
        if (inv != null) apply(inv, true);
    }

    private void scan() {
        try { startActivityForResult(new Intent(this, QrScanActivity.class), SCAN); }
        catch (Exception e) { say("warn", "The scanner couldn't open — paste the invite link instead", Ui.AMB); }
    }

    @Override protected void onActivityResult(int rq, int rs, Intent data) {
        super.onActivityResult(rq, rs, data);
        if (rq != SCAN || rs != RESULT_OK || data == null) return;
        Invite inv = Invite.parse(data.getStringExtra("text"));
        if (inv != null) apply(inv, true);
    }

    private String clipText() {
        try {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            ClipData cd = cm == null ? null : cm.getPrimaryClip();
            if (cd == null || cd.getItemCount() == 0) return null;
            CharSequence s = cd.getItemAt(0).coerceToText(this);
            return s == null ? null : s.toString();
        } catch (Exception e) { return null; }
    }

    /** Android only lets apps read the clipboard while they have focus — so look once the window is up. */
    @Override public void onWindowFocusChanged(boolean has) {
        super.onWindowFocusChanged(has);
        if (!has || clipChecked || busy) return;
        clipChecked = true;
        Invite inv = Invite.parse(clipText());
        if (inv == null || !inv.complete()) return;
        if (inv.key.equals(Prefs.key(this)) && (inv.lan.equals(Prefs.lanUrl(this)) || inv.away.equals(Prefs.remoteUrl(this)))) return;
        clip.removeAllViews();
        clip.setPadding(Ui.dp(14), Ui.dp(14), Ui.dp(14), Ui.dp(14));
        clip.setBackground(Ui.box(16, Ui.alpha(Ui.EMR, 0.10f), Ui.alpha(Ui.EMR, 0.55f)));
        LinearLayout row = Ui.hbox(this);
        row.setBaselineAligned(false);
        row.addView(Ui.text(this, "[[clipboard]]", 20, Ui.EMR));
        LinearLayout tx = Ui.vbox(this);
        tx.addView(Ui.bold(this, "Invite link on your clipboard", 14, Ui.INK));
        tx.addView(Ui.mono(this, Api.host(inv.lan.isEmpty() ? inv.away : inv.lan) + "  ·  key …" + tail(inv.key), 11.5f, Ui.DIM),
                Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 4, 0, 0));
        row.addView(tx, Ui.margins(Ui.lpw(1), 12, 0, 8, 0));
        TextView use = Ui.button(this, "CONNECT", Ui.EMR, true);
        use.setOnClickListener(v -> { clip.setVisibility(View.GONE); apply(inv, true); });
        row.addView(use);
        clip.addView(row);
        clip.setVisibility(View.VISIBLE);
        Tv.focusify(clip);
    }

    private static String tail(String k) { return k.length() <= 4 ? k : k.substring(k.length() - 4); }

    private void paste() {
        Invite inv = Invite.parse(clipText());
        if (inv != null && inv.complete()) { apply(inv, true); return; }
        Sheet sh = new Sheet(this, "Paste invite link", "link", Ui.pal());
        sh.note("Paste the whole invite the lab host sent you. It looks like\nhttp://192.168.0.50:5400/?key=mml-…");
        EditText e = new EditText(this);
        e.setMinLines(3);
        e.setGravity(Gravity.TOP);
        e.setHint("Paste here");
        e.setTextColor(Ui.INK);
        e.setHintTextColor(Ui.FAINT);
        e.setTextSize(14);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        e.setPadding(Ui.dp(12), Ui.dp(12), Ui.dp(12), Ui.dp(12));
        e.setBackground(Ui.box(12, Ui.LIGHT ? 0x0A000000 : 0x40000000, Ui.LINE2));
        String c = clipText();
        if (c != null && c.length() < 600) e.setText(c.trim());
        sh.add(e);
        sh.button("arrow-right", "Connect", true, () -> {
            Invite in = Invite.parse(e.getText().toString());
            if (in == null) { say("x-circle", "That doesn't look like an invite link — it should contain ?key=mml-…", Ui.RED); return; }
            apply(in, true);
        });
        sh.show();
        e.requestFocus();
    }

    /** Put an invite into the form; connect right away when it's complete. */
    private void apply(Invite inv, boolean auto) {
        if (!inv.lan.isEmpty()) lan.setText(inv.lan);
        if (!inv.away.isEmpty()) remote.setText(inv.away);
        if (!inv.key.isEmpty()) key.setText(inv.key);
        if (auto && inv.complete()) connect();
        else {
            showManual(true);
            say("warn", inv.key.isEmpty() ? "Got the address — now add your access key" : "Got your key — now add the lab's address", Ui.AMB);
        }
    }

    // ── connect + doctor ──────────────────────────────────────────────────
    private void connect() {
        if (busy) return;
        String l = Prefs.normalize(lan.getText().toString()), r = Prefs.normalize(remote.getText().toString());
        String k = key.getText().toString().trim();
        report.removeAllViews();
        if (!lan.getText().toString().trim().isEmpty() && l.isEmpty()) { showManual(true); say("x-circle", "The home address isn't valid. Use a form like 192.168.0.50:5400", Ui.RED); return; }
        if (!remote.getText().toString().trim().isEmpty() && r.isEmpty()) { showManual(true); say("x-circle", "The away address isn't valid. Use a form like my-lab.duckdns.org:5400", Ui.RED); return; }
        if (l.isEmpty() && r.isEmpty()) { showManual(true); say("x-circle", "Scan or paste your invite — or enter at least one address", Ui.RED); return; }
        if (k.isEmpty()) { showManual(true); say("x-circle", "Your access key is missing — it's in the invite link (?key=mml-…)", Ui.RED); return; }
        lan.setText(l);
        remote.setText(r);
        busy = true;
        go.setVisibility(View.VISIBLE);
        Icons.set(go, "[[hourglass]]  CONNECTING…");
        say("hourglass", "Looking for your lab…", Ui.DIM);
        final boolean wifi = onWifi();
        new Thread(() -> {
            long t0 = System.currentTimeMillis();
            String le = l.isEmpty() ? "-" : Api.ping(l, 2500, 4000);
            long lt = System.currentTimeMillis() - t0;
            long t1 = System.currentTimeMillis();
            String re = r.isEmpty() ? "-" : Api.ping(r, 5000, 8000);
            long rt = System.currentTimeMillis() - t1;
            String use = le == null ? l : re == null ? r : null;
            int code = 0;
            String who = "", err = null;
            if (use != null) {
                HttpURLConnection c = null;
                try {
                    c = (HttpURLConnection) new URL(use + "/api/me").openConnection();
                    c.setConnectTimeout(6000);
                    c.setReadTimeout(8000);
                    c.setRequestProperty("X-MML-Key", k);
                    c.setRequestProperty("User-Agent", "MirMediaLabs-Android/" + Updater.installedName(this));
                    code = c.getResponseCode();
                    java.io.InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
                    String body = in == null ? "" : new String(Api.readAll(in), "UTF-8");
                    org.json.JSONObject j = new org.json.JSONObject(body.isEmpty() ? "{}" : body);
                    who = j.optString("name", "");
                    if (code != 200) err = j.optString("error", "HTTP " + code);
                } catch (Exception e) { err = Api.explain(e, use); }
                finally { if (c != null) c.disconnect(); }
            }
            final int fc = code; final String fw = who, fe = err;
            runOnUiThread(() -> done(l, r, k, use, le, lt, re, rt, fc, fw, fe, wifi));
        }, "mml-connect").start();
    }

    private void done(String l, String r, String k, String use, String le, long lt, String re, long rt, int code, String who, String err, boolean wifi) {
        busy = false;
        report.removeAllViews();
        if (!l.isEmpty()) line(le == null ? "check-circle" : "x-circle", "Home Wi-Fi  ·  " + Api.host(l)
                + (le == null ? "  ·  answered in " + lt + " ms" : "\n" + le), le == null ? Ui.GRN : (use != null ? Ui.AMB : Ui.RED));
        if (!r.isEmpty()) line(re == null ? "check-circle" : "x-circle", "Away  ·  " + Api.host(r)
                + (re == null ? "  ·  answered in " + rt + " ms" : "\n" + re), re == null ? Ui.GRN : (use != null ? Ui.AMB : Ui.RED));
        boolean ok = use != null && code == 200;
        if (use != null) {
            if (ok) line("check-circle", "Key accepted" + (who.isEmpty() ? "" : "  ·  welcome, " + who), Ui.GRN);
            else if (code == 401) line("x-circle", "This key isn't valid on that lab (revoked, replaced or mistyped). Ask the host for a new invite.", Ui.RED);
            else if (code == 429) line("lock", "Too many wrong keys from this network — wait 15 minutes, then try again with the right key.", Ui.RED);
            else if (code == 503) line("pause", "The host paused remote access. It works again when they switch it back on.", Ui.AMB);
            else line("x-circle", err == null ? "The lab answered with an error (HTTP " + code + ")" : err, Ui.RED);
        }
        if (!ok) {
            Icons.set(go, "[[refresh]]  TRY AGAIN");
            if (use == null) {
                if (!wifi && !l.isEmpty() && r.isEmpty())
                    tip("You're not on Wi-Fi. A home address only works on the same Wi-Fi as the PC — connect to it, or add an away address (see \"Use it away from home\").");
                else if (wifi && le != null && !l.isEmpty())
                    tip("Check that MIR MEDIA LABS is running on the PC and this phone is on the same Wi-Fi (not a guest network).");
                if (re != null && !r.isEmpty())
                    tip("The away address needs a port forward on the router. Testing from home Wi-Fi can fail on some routers — try it on mobile data.");
            }
            return;
        }
        if (le != null && !l.isEmpty() && re == null) tip("Connected through the away address. At home the app switches to the faster home address by itself.");
        Icons.set(go, "[[check]]  CONNECTED");
        boolean changed = !k.equals(Prefs.key(this)) || !l.equals(Prefs.lanUrl(this)) || !r.equals(Prefs.remoteUrl(this));
        Prefs.save(this, l, r, k);
        Prefs.active = use;
        if (changed) { Prefs.put(this, "ev_last", 0L); Prefs.sp(this).edit().remove("atts").apply(); }
        PushJob.schedule(this);
        go.postDelayed(() -> {
            startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
            finish();
        }, 700);
    }

    private void say(String icon, String s, int color) {
        report.removeAllViews();
        line(icon, s, color);
    }

    private void line(String icon, String s, int color) {
        LinearLayout r = Ui.hbox(this);
        r.setGravity(Gravity.TOP);
        r.setBaselineAligned(false);            // baseline-aligning icon + wrapped text clipped the last line
        r.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
        r.setBackground(Ui.box(12, Ui.alpha(color, 0.08f), Ui.alpha(color, 0.35f)));
        r.addView(Ui.text(this, "[[" + icon + "]]", 15, color));
        TextView t = Ui.text(this, s, 12.5f, Ui.INK);
        t.setLineSpacing(0, 1.2f);
        r.addView(t, Ui.margins(Ui.lpw(1), 10, 0, 0, 0));
        report.addView(r, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 6, 0, 0));
    }

    private void tip(String s) { line("bolt", s, Ui.VIO); }

    private boolean onWifi() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkCapabilities nc = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return nc != null && (nc.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || nc.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
        } catch (Exception e) { return true; }
    }

    private void open(String url) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { }
    }

    // ── guides ────────────────────────────────────────────────────────────
    private void guide() {
        Sheet sh = new Sheet(this, "Use it away from home", "router", Ui.pal());
        sh.note("At home the app talks to the PC over Wi-Fi. Away from home, your router has to pass the app's requests "
                + "through to the PC — that's a port forward. It takes about 10 minutes, once. The lab host does this, on the PC's network.");
        sh.section("1 · Give the PC a fixed address");
        sh.note("Open your router's admin page in a browser — usually 192.168.0.1, 192.168.1.1 or 10.0.0.1 (it's printed on the router). "
                + "Find DHCP reservation (\"Address reservation\", \"Static lease\") and reserve the PC's current address — "
                + "the one in Host Control → Invite, e.g. 192.168.0.50.");
        sh.section("2 · Forward the port");
        sh.note("Find Port Forwarding (also called Virtual Server, NAT or Applications & Gaming). Add a rule:\n"
                + "•  Protocol: TCP\n•  External / WAN port: 5400\n•  Internal IP: the PC's address from step 1\n•  Internal port: 5400\nSave and apply.");
        sh.section("3 · Allow it on the PC");
        sh.note("Windows Defender Firewall → Advanced settings → Inbound Rules → New Rule → Port → TCP 5400 → Allow the connection → "
                + "tick Private and Public → name it MIR MEDIA LABS.");
        sh.section("4 · Get an address that doesn't change");
        sh.note("Your home's internet address changes from time to time. A free dynamic-DNS name follows it: No-IP or DuckDNS, or the DDNS "
                + "page of your router. You end up with a name like my-lab.duckdns.org.");
        sh.section("5 · Put it in the invite");
        sh.note("On the PC: MIR MEDIA LABS → Host Control → Phones → Away-from-home address → http://my-lab.duckdns.org:5400. "
                + "New invite links and QR codes carry it, so the app works at home and away. Or type it into \"Away-from-home address\" here.");
        sh.section("6 · Test it");
        sh.note("Turn Wi-Fi off on the phone and connect over mobile data. Testing from home Wi-Fi can fail on some routers even when "
                + "everything is right (no \"NAT loopback\").");
        sh.section("Still nothing?");
        sh.note("Compare the WAN / internet IP on your router's status page with what whatismyip.com shows. If they differ, your provider "
                + "uses CGNAT and port forwarding can't work — use a free VPN such as Tailscale or ZeroTier on the PC and the phone instead, "
                + "and enter the PC's VPN address (e.g. 100.x.y.z:5400) as the away address.\n\n"
                + "Safety: only people with a key get in, 10 wrong keys lock an address out for 15 minutes, and the host can pause remote "
                + "access with one switch in Host Control.");
        sh.show();
    }

    private void troubleshoot() {
        Sheet sh = new Sheet(this, "Can't connect?", "warn", Ui.pal());
        sh.section("\"connection refused\"");
        sh.note("Something is at that address but nothing listens on the port. Start MIR MEDIA LABS on the PC, and check the port (5400 unless the host changed it). Away from home: the router's port forward is missing.");
        sh.section("\"no answer\" / timed out");
        sh.note("The PC is off or asleep, Windows Firewall blocks port 5400, the phone is on a different (guest) Wi-Fi, or — away from home — the port isn't forwarded.");
        sh.section("\"can't find …\"");
        sh.note("The name doesn't exist. Check the spelling of the away address (my-lab.duckdns.org), or your phone's internet connection.");
        sh.section("\"isn't a Media Lab\"");
        sh.note("Another device or the router answered. The address or the port number is wrong.");
        sh.section("\"key isn't valid\"");
        sh.note("The host replaced or revoked your key, or it was mistyped. Ask for a fresh invite and scan it.");
        sh.section("\"paused remote access\"");
        sh.note("The host switched remote access off in Host Control. Nothing to fix on the phone.");
        sh.section("Works at home, not away");
        sh.note("That's the port forward — see \"Use it away from home\".");
        sh.show();
    }
}
