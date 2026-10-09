package com.mirmedialabs.app;

import android.app.AlertDialog;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

/** Chat sessions (server sessions.py): one session = one project's chat + media. "General" (id "") holds everything
 *  older. The open session is remembered per device; chat, new requests and the library follow it. */
final class Sessions {
    static String id = "", name = "General";
    static JSONArray list = new JSONArray();
    static boolean libAll = false;                     // library: this session only, or every session

    private Sessions() { }

    static void init(MainActivity m) {
        id = Prefs.str(m, "session", "");
        libAll = Prefs.bool(m, "lib_all", false);
        load(m, null);
    }

    /** "&session=<id>" for the chat / library lists. */
    static String q() { return "&session=" + android.net.Uri.encode(id); }

    static void load(MainActivity m, Runnable then) {
        m.api.get("/api/sessions", r -> {
            if (r.ok()) list = r.obj().optJSONArray("sessions") == null ? new JSONArray() : r.obj().optJSONArray("sessions");
            paint(m);
            if (then != null) then.run();
        });
    }

    private static void paint(MainActivity m) {
        name = "General";
        boolean found = id.isEmpty();
        for (int i = 0; i < list.length(); i++) {
            JSONObject s = list.optJSONObject(i);
            if (s != null && s.optString("id").equals(id)) { name = s.optString("name"); found = true; }
        }
        if (!found) { id = ""; Prefs.put(m, "session", ""); }
        m.create.paintSession();
        m.library.paintScope();
    }

    static void open(MainActivity m, String sid) {
        id = sid == null ? "" : sid;
        Prefs.put(m, "session", id);
        m.api.post("/api/sessions/" + (id.isEmpty() ? "_" : id), Api.obj("last", true), r -> { });
        paint(m);
        m.seeded = false;
        m.seenDone.clear();
        m.create.renderThread(new JSONArray(), true);
        m.library.reload();
        m.tick = 0;
        m.poll();
        m.toast("Session: " + name);
    }

    static void picker(MainActivity m) {
        Sheet sh = new Sheet(m, "Chat sessions", "folder", Ui.pal());
        sh.note("Each session keeps its own chat and media — one per project. Long-press a session to rename or delete it.");
        sh.row("plus", "New session", "start a fresh chat for a new project", () -> ask(m, "New session", "", n ->
                m.api.post("/api/sessions", Api.obj("name", n), r -> {
                    if (!r.ok()) { m.toast(r.err()); return; }
                    list = r.obj().optJSONArray("sessions") == null ? new JSONArray() : r.obj().optJSONArray("sessions");
                    open(m, r.obj().optJSONObject("session").optString("id"));
                })));
        sh.section("Sessions");
        sh.row("folder", "General", (id.isEmpty() ? "Open · " : "") + "everything from before sessions", () -> open(m, ""));
        for (int i = list.length() - 1; i >= 0; i--) {
            JSONObject s = list.optJSONObject(i);
            if (s == null) continue;
            final String sid = s.optString("id"), nm = s.optString("name");
            LinearLayout row = sh.row("folder", nm, sid.equals(id) ? "Open" : "", () -> open(m, sid));
            row.setOnLongClickListener(v -> { sh.dismiss(); manage(m, sid, nm); return true; });
        }
        sh.show();
    }

    private static void manage(MainActivity m, String sid, String nm) {
        Sheet sh = new Sheet(m, nm, "folder", Ui.pal());
        sh.row("type", "Rename", "", () -> ask(m, "Rename session", nm, n ->
                m.api.post("/api/sessions/" + sid, Api.obj("name", n), r -> { if (r.ok()) load(m, null); else m.toast(r.err()); })));
        sh.row("trash", "Delete session", "its chats and media move to General — nothing is deleted", () ->
                new AlertDialog.Builder(m, android.R.style.Theme_DeviceDefault_Dialog_Alert).setTitle("Delete \"" + nm + "\"?")
                        .setMessage("Its chats and media are not deleted — they move to General.")
                        .setPositiveButton("Delete", (d, w) -> m.api.post("/api/sessions/" + sid + "/delete", null, r -> {
                            if (!r.ok()) { m.toast(r.err()); return; }
                            list = r.obj().optJSONArray("sessions") == null ? new JSONArray() : r.obj().optJSONArray("sessions");
                            if (sid.equals(id)) open(m, ""); else paint(m);
                            m.toast("Session deleted — " + r.obj().optInt("moved") + " items moved to General");
                        }))
                        .setNegativeButton("Cancel", null).show());
        sh.show();
    }

    /** Move one library file to a session (Viewer). */
    static void moveFile(MainActivity m, String file) {
        Sheet sh = new Sheet(m, "Move to session", "folder", Ui.pal());
        sh.row("folder", "General", "", () -> move(m, file, "", "General"));
        for (int i = list.length() - 1; i >= 0; i--) {
            JSONObject s = list.optJSONObject(i);
            if (s != null) { final String sid = s.optString("id"), nm = s.optString("name"); sh.row("folder", nm, "", () -> move(m, file, sid, nm)); }
        }
        sh.show();
    }

    private static void move(MainActivity m, String file, String sid, String nm) {
        m.api.post("/api/library/" + android.net.Uri.encode(file) + "/session", Api.obj("session", sid), r -> {
            m.toast(r.ok() ? "Moved to " + nm : r.err());
            if (r.ok()) m.library.reload();
        });
    }

    interface Got { void on(String s); }

    private static void ask(MainActivity m, String title, String cur, Got got) {
        LinearLayout box = Ui.vbox(m);
        box.setPadding(Ui.dp(20), Ui.dp(6), Ui.dp(20), 0);
        EditText e = new EditText(m);
        e.setSingleLine(true);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        e.setHint("Project name");
        e.setText(cur);
        e.setSelection(cur.length());
        box.addView(e);
        new AlertDialog.Builder(m, android.R.style.Theme_DeviceDefault_Dialog_Alert).setTitle(title).setView(box)
                .setPositiveButton("OK", (d, w) -> { String n = e.getText().toString().trim(); if (!n.isEmpty()) got.on(n); })
                .setNegativeButton("Cancel", null).show();
    }
}
