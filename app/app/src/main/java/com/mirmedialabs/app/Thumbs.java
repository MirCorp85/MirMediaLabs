package com.mirmedialabs.app;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.util.LruCache;
import android.widget.ImageView;

/** Tiny thumbnail loader: server /thumb (or /refs) → memory cache → ImageView (tag-checked). */
final class Thumbs {
    private static final LruCache<String, Bitmap> CACHE = new LruCache<String, Bitmap>(24 * 1024 * 1024) {
        @Override protected int sizeOf(String k, Bitmap b) { return b.getByteCount(); }
    };

    static void load(MainActivity m, ImageView iv, String path) {
        iv.setTag(path);
        Bitmap hit = CACHE.get(path);
        if (hit != null) { iv.setImageBitmap(hit); return; }
        iv.setImageDrawable(null);
        m.api.bytes(path, r -> {
            if (!r.ok() || r.bytes == null || !path.equals(iv.getTag())) return;
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length, o);
            int s = 1;
            while (o.outWidth / (s * 2) >= 480 && o.outHeight / (s * 2) >= 480) s *= 2;
            o = new BitmapFactory.Options();
            o.inSampleSize = s;
            Bitmap b = BitmapFactory.decodeByteArray(r.bytes, 0, r.bytes.length, o);
            if (b == null) return;
            CACHE.put(path, b);
            if (path.equals(iv.getTag())) iv.setImageBitmap(b);
        });
    }

    /** Absolute https URL (Civitai LoRA previews) → same cache. */
    static void loadUrl(ImageView iv, String url) {
        iv.setTag(url);
        Bitmap hit = CACHE.get(url);
        if (hit != null) { iv.setImageBitmap(hit); return; }
        iv.setImageDrawable(null);
        Api.POOL.execute(() -> {
            try {
                java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
                c.setConnectTimeout(10000); c.setReadTimeout(20000);
                c.setRequestProperty("User-Agent", "MirMediaLabs-Android");
                byte[] b = Api.readAll(c.getInputStream());
                BitmapFactory.Options o = new BitmapFactory.Options();
                o.inSampleSize = 1;
                Bitmap bm = BitmapFactory.decodeByteArray(b, 0, b.length, o);
                if (bm == null) return;
                CACHE.put(url, bm);
                Api.MAIN.post(() -> { if (url.equals(iv.getTag())) iv.setImageBitmap(bm); });
            } catch (Exception ignored) { }
        });
    }

    static void forget(String name) {
        CACHE.remove("/thumb/" + Api.enc(name));
    }
}
