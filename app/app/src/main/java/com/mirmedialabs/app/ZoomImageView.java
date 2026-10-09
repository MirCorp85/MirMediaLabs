package com.mirmedialabs.app;

import android.content.Context;
import android.graphics.Matrix;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.widget.ImageView;

/** Image that zooms with two fingers (up to 8×), pans with one, double-tap toggles fit ↔ 2.5× at the tap point.
 *  A single tap at fit size is passed on as a normal click. */
final class ZoomImageView extends ImageView {
    private static final float MAX = 8f;
    private final Matrix base = new Matrix(), mx = new Matrix();
    private final float[] v = new float[9];
    private final ScaleGestureDetector sg;
    private final GestureDetector gd;
    private float scale = 1f;

    ZoomImageView(Context c) {
        super(c);
        setScaleType(ScaleType.MATRIX);
        sg = new ScaleGestureDetector(c, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector d) {
                float f = d.getScaleFactor(), ns = Math.max(1f, Math.min(MAX, scale * f));
                f = ns / scale;
                scale = ns;
                mx.postScale(f, f, d.getFocusX(), d.getFocusY());
                clamp();
                return true;
            }
        });
        gd = new GestureDetector(c, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) { return true; }
            @Override public boolean onScroll(MotionEvent a, MotionEvent b, float dx, float dy) {
                if (scale <= 1.01f) return false;
                mx.postTranslate(-dx, -dy);
                clamp();
                return true;
            }
            @Override public boolean onDoubleTap(MotionEvent e) {
                if (scale > 1.01f) { scale = 1f; mx.reset(); }
                else { scale = 2.5f; mx.postScale(2.5f, 2.5f, e.getX(), e.getY()); }
                clamp();
                return true;
            }
            @Override public boolean onSingleTapConfirmed(MotionEvent e) {
                if (scale <= 1.01f) performClick();
                return true;
            }
        });
    }

    @Override public void setImageBitmap(android.graphics.Bitmap bm) { super.setImageBitmap(bm); scale = 1f; mx.reset(); fit(); }

    @Override protected void onSizeChanged(int w, int h, int ow, int oh) { super.onSizeChanged(w, h, ow, oh); fit(); }

    /** Base matrix = FIT_CENTER; the user's zoom/pan (mx) is applied on top. */
    private void fit() {
        Drawable d = getDrawable();
        if (d == null || getWidth() == 0 || d.getIntrinsicWidth() <= 0) return;
        base.setRectToRect(new RectF(0, 0, d.getIntrinsicWidth(), d.getIntrinsicHeight()),
                new RectF(0, 0, getWidth(), getHeight()), Matrix.ScaleToFit.CENTER);
        apply();
    }

    /** Keep the picture covering the view when it is bigger, centred when it is smaller. */
    private void clamp() {
        Drawable d = getDrawable();
        if (d == null) { apply(); return; }
        Matrix all = new Matrix(base);
        all.postConcat(mx);
        RectF r = new RectF(0, 0, d.getIntrinsicWidth(), d.getIntrinsicHeight());
        all.mapRect(r);
        float dx = 0, dy = 0, w = getWidth(), h = getHeight();
        if (r.width() <= w) dx = (w - r.width()) / 2 - r.left; else if (r.left > 0) dx = -r.left; else if (r.right < w) dx = w - r.right;
        if (r.height() <= h) dy = (h - r.height()) / 2 - r.top; else if (r.top > 0) dy = -r.top; else if (r.bottom < h) dy = h - r.bottom;
        mx.postTranslate(dx, dy);
        apply();
    }

    private void apply() {
        Matrix all = new Matrix(base);
        all.postConcat(mx);
        setImageMatrix(all);
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        sg.onTouchEvent(e);
        gd.onTouchEvent(e);
        if (scale > 1.01f && getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
        return true;
    }

    @Override public boolean performClick() { return super.performClick(); }

    boolean zoomed() { mx.getValues(v); return scale > 1.01f; }
}
