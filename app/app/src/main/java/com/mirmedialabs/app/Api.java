package com.mirmedialabs.app;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** HTTP client for the MIR MEDIA LABS server. Every call carries the Media Lab key header. */
final class Api {
    interface Cb { void on(Resp r); }

    static final class Resp {
        final int status; final String body; final byte[] bytes; final String error;
        Resp(int s, String b, byte[] by, String e) { status = s; body = b; bytes = by; error = e; }
        boolean ok() { return error == null && status >= 200 && status < 300; }
        JSONObject obj() { try { return new JSONObject(body); } catch (Exception e) { return new JSONObject(); } }
        JSONArray arr() { try { return new JSONArray(body); } catch (Exception e) { return new JSONArray(); } }
        String err() {
            if (error != null) return error;
            String m = obj().optString("error", "");
            return m.isEmpty() ? "HTTP " + status : m;
        }
    }

    static final ExecutorService POOL = Executors.newFixedThreadPool(6);
    static final Handler MAIN = new Handler(Looper.getMainLooper());

    private final Context ctx;
    Api(Context c) { ctx = c.getApplicationContext(); }

    String base() { return Prefs.activeUrl(ctx); }
    String url(String path) { return base() + path; }
    /** Media URL usable by players / DownloadManager (key in the query string). */
    String mediaUrl(String path) {
        try { return url(path) + (path.contains("?") ? "&" : "?") + "key=" + URLEncoder.encode(Prefs.key(ctx), "UTF-8"); }
        catch (Exception e) { return url(path); }
    }

    private static volatile int failStreak = 0;
    private static volatile long lastProbe = 0;

    /** Pick LAN when it answers fast, else the remote address. Blocking. */
    String probeSync() {
        lastProbe = System.currentTimeMillis();
        String lan = Prefs.lanUrl(ctx), rem = Prefs.remoteUrl(ctx);
        if (!lan.isEmpty() && quick(lan)) { Prefs.active = lan; failStreak = 0; return lan; }
        if (!rem.isEmpty() && quick(rem)) { Prefs.active = rem; failStreak = 0; return rem; }
        Prefs.active = lan.isEmpty() ? rem : lan;
        return Prefs.active;
    }
    void probe(Runnable done) { POOL.execute(() -> { probeSync(); if (done != null) MAIN.post(done); }); }

    private boolean quick(String base) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(base + "/api/ping").openConnection();
            c.setConnectTimeout(1800); c.setReadTimeout(2500);
            return c.getResponseCode() == 200;
        } catch (Exception e) { return false; }
        finally { if (c != null) c.disconnect(); }
    }

    void get(String path, Cb cb) { async(() -> request("GET", path, null, false, 20000), cb); }
    void post(String path, JSONObject body, Cb cb) { async(() -> request("POST", path, body == null ? new JSONObject() : body, false, 60000), cb); }
    void bytes(String path, Cb cb) { async(() -> request("GET", path, null, true, 60000), cb); }
    Resp getSync(String path) { return request("GET", path, null, false, 20000); }

    private interface Call { Resp run(); }
    private void async(Call c, Cb cb) {
        POOL.execute(() -> { Resp r = c.run(); if (cb != null) MAIN.post(() -> cb.on(r)); });
    }

    private void headers(HttpURLConnection c) {
        c.setRequestProperty("X-MML-Key", Prefs.key(ctx));
        c.setRequestProperty("Cache-Control", "no-store");
        c.setRequestProperty("User-Agent", "MirMediaLabs-Android/" + Updater.installedName(ctx));
    }

    private Resp request(String method, String path, JSONObject body, boolean wantBytes, int timeout) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url(path)).openConnection();
            c.setRequestMethod(method);
            c.setConnectTimeout(6000);
            c.setReadTimeout(timeout);
            c.setUseCaches(false);
            headers(c);
            if (body != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                byte[] b = body.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = c.getOutputStream()) { os.write(b); }
            }
            Resp r = finish(c, wantBytes);
            failStreak = 0;
            return r;
        } catch (Exception e) {
            if (++failStreak >= 3 && System.currentTimeMillis() - lastProbe > 15000) POOL.execute(this::probeSync);
            return new Resp(0, null, null, "offline — " + e.getClass().getSimpleName());
        } finally {
            if (c != null) c.disconnect();
        }
    }

    interface Progress { void on(int pct); }

    /** Stream a picked file (any size) to /api/upload as multipart — never loaded fully into RAM. */
    void upload(Uri uri, Progress prog, Cb cb) {
        async(() -> {
            HttpURLConnection c = null;
            String bnd = "----MML" + System.nanoTime();
            try {
                ContentResolver cr = ctx.getContentResolver();
                String name = "file", mime = cr.getType(uri);
                long size = -1;
                try (Cursor q = cr.query(uri, null, null, null, null)) {
                    if (q != null && q.moveToFirst()) {
                        int ni = q.getColumnIndex(OpenableColumns.DISPLAY_NAME), si = q.getColumnIndex(OpenableColumns.SIZE);
                        if (ni >= 0 && q.getString(ni) != null) name = q.getString(ni);
                        if (si >= 0 && !q.isNull(si)) size = q.getLong(si);
                    }
                } catch (Exception ignored) {}
                if (!name.contains(".")) name += extFor(mime);
                if (mime == null) mime = "application/octet-stream";
                byte[] head = ("--" + bnd + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + name.replace("\"", "")
                        + "\"\r\nContent-Type: " + mime + "\r\n\r\n").getBytes(StandardCharsets.UTF_8);
                byte[] tail = ("\r\n--" + bnd + "--\r\n").getBytes(StandardCharsets.UTF_8);
                c = (HttpURLConnection) new URL(url("/api/upload")).openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(8000);
                c.setReadTimeout(300000);
                c.setDoOutput(true);
                headers(c);
                c.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + bnd);
                if (size >= 0) c.setFixedLengthStreamingMode(head.length + size + tail.length);
                else c.setChunkedStreamingMode(65536);
                try (InputStream in = cr.openInputStream(uri); OutputStream out = c.getOutputStream()) {
                    out.write(head);
                    byte[] buf = new byte[65536]; long done = 0; int n, last = -1;
                    while ((n = in.read(buf)) > 0) {
                        out.write(buf, 0, n); done += n;
                        if (size > 0 && prog != null) {
                            int pct = (int) (done * 100 / size);
                            if (pct != last) { last = pct; MAIN.post(() -> prog.on(pct)); }
                        }
                    }
                    out.write(tail);
                }
                return finish(c, false);
            } catch (Exception e) {
                return new Resp(0, null, null, e.getMessage());
            } finally {
                if (c != null) c.disconnect();
            }
        }, cb);
    }

    static String extFor(String mime) {
        if (mime == null) return "";
        switch (mime) {
            case "image/jpeg": return ".jpg";
            case "image/png": return ".png";
            case "image/webp": return ".webp";
            case "video/mp4": return ".mp4";
            case "video/quicktime": return ".mov";
            case "video/webm": return ".webm";
            case "audio/mpeg": return ".mp3";
            case "audio/wav": case "audio/x-wav": return ".wav";
            case "audio/flac": return ".flac";
            case "audio/ogg": return ".ogg";
            case "audio/mp4": case "audio/x-m4a": return ".m4a";
            case "text/plain": return ".txt";
            default: return "";
        }
    }

    private Resp finish(HttpURLConnection c, boolean wantBytes) throws Exception {
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        byte[] raw = in == null ? new byte[0] : readAll(in);
        if (code == 401) return new Resp(code, null, null, "unauthorized — check the Media Lab access key");
        if (wantBytes && code < 400) return new Resp(code, null, raw, null);
        String s = new String(raw, StandardCharsets.UTF_8);
        return new Resp(code, s, null, null);
    }

    static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
        in.close();
        return bo.toByteArray();
    }

    static JSONObject obj(Object... kv) {
        JSONObject o = new JSONObject();
        try { for (int i = 0; i + 1 < kv.length; i += 2) o.put((String) kv[i], kv[i + 1]); } catch (Exception ignored) {}
        return o;
    }

    static String enc(String s) {
        try { return URLEncoder.encode(s, "UTF-8").replace("+", "%20"); } catch (Exception e) { return s; }
    }
}
