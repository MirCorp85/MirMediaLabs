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

/** SERIES studio — the lab's /series page (style bible, cast sheets, locations, episodes, songs) in a
 *  full-screen WebView, signed in with this phone's key + device id. Renders run on the lab PC; "Open in editor"
 *  hands the cut to the timeline editor inside the same WebView. Mirrors EditorActivity. */
public final class SeriesActivity extends Activity {
    static final int PICK = 41;
    private WebView web;
    private ValueCallback<Uri[]> pick;

    static void open(Activity a, String src) {
        Intent i = new Intent(a, SeriesActivity.class);
        if (src != null) i.putExtra("src", src);
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
        String src = getIntent().getStringExtra("src");
        web.loadUrl(base + "/series");
        setContentView(web);
        web.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
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
        if (web.canGoBack()) web.goBack(); else finish();
    }

    @Override protected void onPause() { super.onPause(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onDestroy() { web.destroy(); super.onDestroy(); }

    final class Bridge {
        @JavascriptInterface public void close(String info) { runOnUiThread(SeriesActivity.this::finish); }
    }
}
