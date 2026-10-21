package com.mirmedialabs.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** MOTION STUDIO (/motion) and NODE FLOW (/flow) — the lab's own pages in a full-screen WebView, signed in with this
 *  phone's key + device id. The pages talk to their host with postMessage (motion-close · flow-close · motion-attach ·
 *  motion-editor), so they run inside a same-origin iframe and this shell forwards those messages to the MMLApp bridge:
 *  close → back to the lab, attach → the piece becomes the next request's reference, editor → the timeline editor. */
public final class StudioActivity extends Activity {
    static final int PICK = 43;
    private WebView web;
    private ValueCallback<Uri[]> pick;

    static void open(Activity a, String page) {
        Intent i = new Intent(a, StudioActivity.class);
        i.putExtra("page", page);
        a.startActivity(i);
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(Color.BLACK);
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        String base = Prefs.activeUrl(this);
        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setCookie(base, "mml_key=" + Prefs.key(this) + "; path=/");
        cm.setCookie(base, "mml_dev=" + Prefs.deviceId(this) + "; path=/");
        cm.flush();
        web.addJavascriptInterface(new Bridge(), "MMLApp");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                if (url.startsWith(base)) return false;                       // stay inside the lab
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (pick != null) pick.onReceiveValue(null);
                pick = cb;
                try {
                    Intent i = p.createIntent();
                    i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                    startActivityForResult(i, PICK);
                } catch (Exception e) { pick = null; return false; }
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest r) { r.deny(); }
        });
        String page = "flow".equals(getIntent().getStringExtra("page")) ? "flow" : "motion";
        web.loadDataWithBaseURL(base + "/", shell(page), "text/html", "utf-8", null);
        setContentView(web);
        web.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    /** Full-screen same-origin frame + the postMessage → bridge relay. */
    static String shell(String path) {
        return "<!doctype html><html><head><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
             + "<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}iframe{border:0;width:100%;height:100%;display:block}</style>"
             + "</head><body><iframe id=f src='" + path + "' allow='autoplay; fullscreen; clipboard-write'></iframe><script>"
             + "addEventListener('message',function(e){var d=e.data||{};if(!d.mml||!window.MMLApp)return;"
             + "if(d.mml==='motion-close'||d.mml==='flow-close')MMLApp.close(d.mml);"
             + "else if(d.mml==='motion-attach'&&d.ref)MMLApp.useAsRef(String(d.ref));"
             + "else if(d.mml==='motion-editor'&&d.src)MMLApp.editor(String(d.src));});"
             + "</script></body></html>";
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK || pick == null) return;
        Uri[] out = WebChromeClient.FileChooserParams.parseResult(res, data);
        if (out == null && data != null && data.getClipData() != null) {
            out = new Uri[data.getClipData().getItemCount()];
            for (int i = 0; i < out.length; i++) out[i] = data.getClipData().getItemAt(i).getUri();
        }
        pick.onReceiveValue(out);
        pick = null;
    }

    @Override public void onBackPressed() {
        // the page's own close button saves first, then posts *-close back here
        web.evaluateJavascript("(function(){try{var b=document.getElementById('f').contentWindow.document.querySelector('[data-a=close]');"
            + "if(b){b.click();return 1}}catch(e){}return 0})()", v -> { if (!"1".equals(v)) finish(); });
    }

    @Override protected void onPause() { super.onPause(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onDestroy() { web.destroy(); super.onDestroy(); }

    final class Bridge {
        @JavascriptInterface public void close(String info) { runOnUiThread(StudioActivity.this::finish); }
        @JavascriptInterface public void useAsRef(String name) { GrabActivity.pendingRef = name.startsWith("lib:") ? name.substring(4) : name; runOnUiThread(StudioActivity.this::finish); }
        @JavascriptInterface public void editor(String src) { runOnUiThread(() -> { EditorActivity.open(StudioActivity.this, src); finish(); }); }
    }
}
