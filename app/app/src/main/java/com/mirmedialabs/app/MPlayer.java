package com.mirmedialabs.app;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.VideoView;

/** MML player — the same themed look as the web player: model colour accents on the theme's card colours.
 *  Inline: mini audio card + round play badge on video thumbnails. Viewer: full video / audio player. */
final class MPlayer {
    private MPlayer() {}

    /** Card behind an audio result: a wash of the model colour into the theme's card colour. */
    static GradientDrawable cardBg(int col, float radiusDp) {
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{Ui.mix(col, Ui.BG, 0.62f), Ui.mix(Ui.BAR, Ui.BG, 0.3f)});
        g.setCornerRadius(Ui.dp(radiusDp));
        g.setStroke(Math.max(1, Ui.dp(1)), Ui.LINE);
        return g;
    }

    /** Round accent play button (badge on thumbnails, big button in the players). */
    static TextView playBadge(Context c, int col, int sizeDp) {
        TextView t = Ui.text(c, "[[play]]", sizeDp * 0.36f, 0xFFFFFFFF);
        Icons.set(t, "[[play]]");
        t.setGravity(Gravity.CENTER);
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(Ui.alpha(col, 0.92f));
        g.setStroke(Ui.dp(4), Ui.alpha(col, 0.28f));
        t.setBackground(g);
        t.setPadding(Ui.dp(3), 0, 0, 0);                    // optical centre of the triangle
        t.setElevation(Ui.dp(6));
        return t;
    }

    static void setPlaying(TextView badge, boolean playing) {
        Icons.set(badge, playing ? "[[pause]]" : "[[play]]");
        badge.setPadding(playing ? 0 : Ui.dp(3), 0, 0, 0);
    }

    /** Inline audio result: play badge + title + waveform (tap opens the full player). */
    static View miniAudio(Context c, int col, String label, String name) {
        LinearLayout row = Ui.hbox(c);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(14), Ui.dp(10));
        row.addView(playBadge(c, col, 46), Ui.lp(Ui.dp(46), Ui.dp(46)));
        LinearLayout txt = Ui.vbox(c);
        TextView t = Ui.bold(c, label + "  ·  SONG", 11, Ui.INK);
        t.setLetterSpacing(0.06f);
        t.setSingleLine(true);
        txt.addView(t);
        Bars bars = new Bars(c, col, name.length());
        txt.addView(bars, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(26)), 0, 6, 0, 0));
        row.addView(txt, Ui.margins(Ui.lpw(1), 12, 0, 0, 0));
        return row;
    }

    /** Waveform bars: played part bright, the rest dim; gently moving while playing. */
    static final class Bars extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF r = new RectF();
        private final int col, seed;
        float progress = 0f;
        boolean live = false;

        Bars(Context c, int col, int seed) { super(c); this.col = col; this.seed = seed; }

        @Override protected void onDraw(Canvas cv) {
            int w = getWidth(), h = getHeight();
            if (w == 0) return;
            float gap = Ui.dp(3), bw = Math.max(Ui.dp(2), Ui.dp(4));
            int n = Math.max(12, (int) (w / (bw + gap)));
            double t = System.currentTimeMillis() / 180.0;
            for (int i = 0; i < n; i++) {
                double base = 0.2 + Math.abs(Math.sin(i * 1.7 + seed)) * 0.62;
                double v = live ? Math.min(1, base * (0.55 + 0.45 * Math.abs(Math.sin(t + i * 0.9)))) + 0.05 : base;
                float bh = (float) Math.max(Ui.dp(2), v * h), x = i * (bw + gap);
                p.setColor(i / (float) n <= progress ? col : Ui.alpha(col, 0.35f));
                r.set(x, (h - bh) / 2f, x + bw, (h + bh) / 2f);
                cv.drawRoundRect(r, bw / 2f, bw / 2f, p);
            }
            if (live) postInvalidateDelayed(60);
        }
    }

    static String fmt(int ms) { int s = Math.max(0, ms) / 1000; return (s / 60) + ":" + String.format("%02d", s % 60); }

    static void tint(SeekBar sb, int col) {
        sb.setProgressTintList(ColorStateList.valueOf(col));
        sb.setThumbTintList(ColorStateList.valueOf(0xFFFFFFFF));
        sb.setProgressBackgroundTintList(ColorStateList.valueOf(0x55FFFFFF));
        if (android.os.Build.VERSION.SDK_INT >= 29) {       // slim track like the web player (stock is chunky)
            sb.setMinHeight(Ui.dp(4));
            sb.setMaxHeight(Ui.dp(4));
        }
    }

    /** Full-screen video player: custom themed controls instead of the stock MediaController. */
    static View video(Context c, String url, int col, Handler h) {
        FrameLayout f = new FrameLayout(c);
        VideoView vv = new VideoView(c);
        f.addView(vv, new FrameLayout.LayoutParams(Ui.MATCH, Ui.WRAP, Gravity.CENTER));
        TextView big = playBadge(c, col, 72);
        f.addView(big, new FrameLayout.LayoutParams(Ui.dp(72), Ui.dp(72), Gravity.CENTER));
        LinearLayout bar = Ui.hbox(c);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(Ui.dp(12), Ui.dp(26), Ui.dp(12), Ui.dp(12));
        bar.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{0x00000000, 0xCC08080C}));
        TextView pp = Ui.text(c, "[[pause]]", 20, 0xFFFFFFFF);
        Icons.set(pp, "[[pause]]");
        TextView t0 = Ui.mono(c, "0:00", 11, 0xFFFFFFFF), t1 = Ui.mono(c, "--:--", 11, 0xFFFFFFFF);
        SeekBar sb = new SeekBar(c);
        tint(sb, col);
        TextView mute = Ui.text(c, "[[volume]]", 18, 0xFFFFFFFF);
        Icons.set(mute, "[[volume]]");
        bar.addView(pp, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 2, 0, 10, 0));
        bar.addView(t0);
        bar.addView(sb, Ui.lpw(1));
        bar.addView(t1);
        bar.addView(mute, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 12, 0, 2, 0));
        f.addView(bar, new FrameLayout.LayoutParams(Ui.MATCH, Ui.WRAP, Gravity.BOTTOM));
        final MediaPlayer[] mpH = {null};
        final boolean[] muted = {false};
        Runnable tick = new Runnable() {
            @Override public void run() {
                try {
                    sb.setMax(vv.getDuration());
                    sb.setProgress(vv.getCurrentPosition());
                    t0.setText(fmt(vv.getCurrentPosition()));
                    t1.setText(fmt(vv.getDuration()));
                } catch (Exception ignored) {}
                h.postDelayed(this, 300);
            }
        };
        Runnable hide = () -> { if (vv.isPlaying()) bar.animate().alpha(0f).setDuration(250); };
        Runnable sync = () -> {
            boolean on = vv.isPlaying();
            big.setVisibility(on ? View.GONE : View.VISIBLE);
            Icons.set(pp, on ? "[[pause]]" : "[[play]]");
            bar.animate().alpha(1f).setDuration(150);
            h.removeCallbacks(hide);
            h.postDelayed(hide, 3000);
        };
        View.OnClickListener toggle = v -> { if (vv.isPlaying()) vv.pause(); else vv.start(); sync.run(); };
        big.setOnClickListener(toggle);
        pp.setOnClickListener(toggle);
        vv.setOnClickListener(v -> sync.run());
        f.setOnClickListener(v -> sync.run());
        mute.setOnClickListener(v -> {
            if (mpH[0] == null) return;
            muted[0] = !muted[0];
            mpH[0].setVolume(muted[0] ? 0f : 1f, muted[0] ? 0f : 1f);
            Icons.set(mute, muted[0] ? "[[mute]]" : "[[volume]]");
        });
        sb.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean user) { if (user) vv.seekTo(p); }
            @Override public void onStartTrackingTouch(SeekBar s) { h.removeCallbacks(hide); }
            @Override public void onStopTrackingTouch(SeekBar s) { sync.run(); }
        });
        vv.setVideoURI(Uri.parse(url));
        vv.setOnPreparedListener(p -> { mpH[0] = p; p.setLooping(true); vv.start(); sync.run(); h.post(tick); });
        vv.setOnTouchListener((v, e) -> { if (e.getAction() == android.view.MotionEvent.ACTION_UP) sync.run(); return false; });
        return f;
    }

    /** Full-screen audio player: big waveform, accent seek bar, ±10 s and a big play button. */
    static View audio(Context c, String url, int col, String label, String name, Handler h, MediaPlayer[] out) {
        LinearLayout card = Ui.vbox(c);
        card.setPadding(Ui.dp(22), Ui.dp(22), Ui.dp(22), Ui.dp(20));
        card.setBackground(cardBg(col, 22));
        TextView chip = Ui.chip(c, label, col);
        card.addView(chip, Ui.lp(Ui.WRAP, Ui.WRAP));
        TextView nm = Ui.bold(c, name, 15, Ui.INK);
        nm.setSingleLine(true);
        nm.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);
        card.addView(nm, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 0));
        Bars bars = new Bars(c, col, name.length());
        card.addView(bars, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(110)), 0, 18, 0, 10));
        SeekBar sb = new SeekBar(c);
        tint(sb, col);
        card.addView(sb, Ui.lp(Ui.MATCH, Ui.WRAP));
        LinearLayout times = Ui.hbox(c);
        TextView t0 = Ui.mono(c, "0:00", 11, Ui.DIM), t1 = Ui.mono(c, "loading…", 11, Ui.DIM);
        times.addView(t0, Ui.lpw(1));
        times.addView(t1);
        card.addView(times, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 4, 2, 4, 0));
        LinearLayout ctl = Ui.hbox(c);
        ctl.setGravity(Gravity.CENTER);
        TextView back = Ui.mono(c, "−10s", 13, Ui.INK), fwd = Ui.mono(c, "+10s", 13, Ui.INK);
        back.setPadding(Ui.dp(16), Ui.dp(10), Ui.dp(16), Ui.dp(10));
        fwd.setPadding(Ui.dp(16), Ui.dp(10), Ui.dp(16), Ui.dp(10));
        TextView big = playBadge(c, col, 72);
        ctl.addView(back);
        ctl.addView(big, Ui.margins(Ui.lp(Ui.dp(72), Ui.dp(72)), 18, 0, 18, 0));
        ctl.addView(fwd);
        card.addView(ctl, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 14, 0, 0));

        MediaPlayer mp = new MediaPlayer();
        out[0] = mp;
        Runnable tick = new Runnable() {
            @Override public void run() {
                try {
                    int pos = mp.getCurrentPosition(), d = mp.getDuration();
                    sb.setProgress(pos);
                    t0.setText(fmt(pos));
                    bars.progress = d > 0 ? pos / (float) d : 0;
                    bars.invalidate();
                    if (mp.isPlaying()) h.postDelayed(this, 250);
                } catch (Exception ignored) {}
            }
        };
        Runnable sync = () -> {
            boolean on = false;
            try { on = mp.isPlaying(); } catch (Exception ignored) {}
            setPlaying(big, on);
            bars.live = on;
            bars.invalidate();
            if (on) { h.removeCallbacks(tick); h.post(tick); }
        };
        try {
            mp.setDataSource(c, Uri.parse(url));
            mp.setOnPreparedListener(p -> {
                sb.setMax(p.getDuration());
                t1.setText(fmt(p.getDuration()));
                p.start();
                sync.run();
            });
            mp.setOnCompletionListener(p -> sync.run());
            mp.prepareAsync();
        } catch (Exception e) { t1.setText("can't play: " + e.getMessage()); }
        big.setOnClickListener(v -> { try { if (mp.isPlaying()) mp.pause(); else mp.start(); } catch (Exception ignored) {} sync.run(); });
        back.setOnClickListener(v -> { try { mp.seekTo(Math.max(0, mp.getCurrentPosition() - 10000)); tick.run(); } catch (Exception ignored) {} });
        fwd.setOnClickListener(v -> { try { mp.seekTo(Math.min(mp.getDuration(), mp.getCurrentPosition() + 10000)); tick.run(); } catch (Exception ignored) {} });
        sb.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean user) {
                if (!user) return;
                try { mp.seekTo(p); t0.setText(fmt(p)); bars.progress = p / (float) Math.max(1, s.getMax()); bars.invalidate(); } catch (Exception ignored) {}
            }
            @Override public void onStartTrackingTouch(SeekBar s) {}
            @Override public void onStopTrackingTouch(SeekBar s) {}
        });
        return card;
    }
}
