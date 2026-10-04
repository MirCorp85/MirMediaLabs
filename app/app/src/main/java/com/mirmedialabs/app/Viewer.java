package com.mirmedialabs.app;

import android.app.AlertDialog;
import android.app.Dialog;
import android.app.DownloadManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Full-screen viewer: image / video / audio player + Save · Use as ref · Delete. */
final class Viewer extends Dialog {
    private final MainActivity m;
    private final String name, model, kind;
    private MediaPlayer mp;
    private final Handler h = new Handler(Looper.getMainLooper());

    Viewer(MainActivity a, String name, String model) {
        super(a, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        m = a;
        this.name = name;
        this.model = model;
        kind = Ui.kindOf(name);
        build();
        setOnDismissListener(d -> { h.removeCallbacksAndMessages(null); if (mp != null) { mp.release(); mp = null; } });
    }

    private void build() {
        Context c = getContext();
        int col = m.colorOf(model);
        LinearLayout root = Ui.vbox(c);
        root.setBackgroundColor(0xFF000000);

        LinearLayout top = Ui.hbox(c);
        top.setPadding(Ui.dp(14), Ui.dp(14), Ui.dp(8), Ui.dp(10));
        top.addView(Ui.chip(c, MainActivity.shortName(model), col));
        TextView t = Ui.text(c, name, 12, Ui.DIM);
        t.setSingleLine(true);
        top.addView(t, Ui.margins(Ui.lpw(1), 10, 0, 8, 0));
        TextView x = Ui.text(c, "[[close]]", 20, Ui.INK);
        x.setPadding(Ui.dp(12), Ui.dp(4), Ui.dp(12), Ui.dp(4));
        x.setOnClickListener(v -> dismiss());
        top.addView(x);
        root.addView(top);

        FrameLayout stage = new FrameLayout(c);
        String url = m.api.mediaUrl("/media/" + Api.enc(name));
        if ("image".equals(kind)) {
            ImageView iv = new ImageView(c);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            stage.addView(iv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
            TextView wait = Ui.mono(c, "loading…", 12, Ui.DIM);
            wait.setGravity(Gravity.CENTER);
            stage.addView(wait, new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
            m.api.bytes("/media/" + Api.enc(name), r -> {
                wait.setText(r.ok() ? "" : r.err());
                if (!r.ok() || r.bytes == null) return;
                BitmapFactory.Options o = new BitmapFactory.Options();
                o.inJustDecodeBounds = true;
                BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length, o);
                int s = 1;
                while (o.outWidth / (s * 2) >= 2048 || o.outHeight / (s * 2) >= 2048) s *= 2;
                o = new BitmapFactory.Options();
                o.inSampleSize = s;
                Bitmap b = BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length, o);
                if (b != null) iv.setImageBitmap(b);
            });
        } else if ("video".equals(kind)) {
            stage.addView(MPlayer.video(c, url, col, h), new FrameLayout.LayoutParams(Ui.MATCH, Ui.MATCH));
        } else {
            MediaPlayer[] hold = {null};
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(Ui.MATCH, Ui.WRAP, Gravity.CENTER);
            lp.setMargins(Ui.dp(18), 0, Ui.dp(18), 0);
            stage.addView(MPlayer.audio(c, url, col, m.model(model).optString("label", "AUDIO"), name, h, hold), lp);
            mp = hold[0];
        }
        root.addView(stage, new LinearLayout.LayoutParams(Ui.MATCH, 0, 1));

        LinearLayout bar = Ui.hbox(c);
        bar.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(16));
        TextView save = Ui.button(c, "[[download]] SAVE", col, false);
        save.setOnClickListener(v -> m.downloadFile(name));
        TextView use = Ui.button(c, "[[refresh]] USE AS REF", col, true);
        use.setOnClickListener(v -> { m.useAsRef(name); dismiss(); });
        TextView del = Ui.button(c, "[[trash]]", col, false);
        del.setOnClickListener(v -> new AlertDialog.Builder(c, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Move to trash?").setMessage(name + "\n\nIt goes to data\\trash on the PC (recoverable).")
                .setPositiveButton("Move", (d, w) -> m.api.post("/api/library/" + Api.enc(name) + "/delete", null, r -> {
                    m.toast(r.ok() ? "Moved to trash" : r.err());
                    if (r.ok()) { Thumbs.forget(name); m.libraryChanged(); dismiss(); }
                }))
                .setNegativeButton("Cancel", null).show());
        bar.addView(save, Ui.lpw(1));
        bar.addView(use, Ui.margins(Ui.lpw(1.3f), 8, 0, 8, 0));
        bar.addView(del, Ui.lp(Ui.dp(56), ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(bar);
        setContentView(root);
    }

    private static String fmt(int ms) { int s = ms / 1000; return (s / 60) + ":" + String.format("%02d", s % 60); }

    private void download(String url) {
        try {
            DownloadManager dm = (DownloadManager) getContext().getSystemService(Context.DOWNLOAD_SERVICE);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            r.setTitle(name);
            r.setDescription("MIR MEDIA LABS");
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "MirMediaLabs/" + name);
            dm.enqueue(r);
            m.toast("Saving to Downloads/MirMediaLabs");
        } catch (Exception e) { m.toast("Save failed: " + e.getMessage()); }
    }
}
