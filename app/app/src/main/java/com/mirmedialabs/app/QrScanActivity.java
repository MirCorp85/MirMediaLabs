package com.mirmedialabs.app;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.ImageFormat;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Size;
import android.view.Gravity;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.BinaryBitmap;
import com.google.zxing.DecodeHintType;
import com.google.zxing.LuminanceSource;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.RGBLuminanceSource;
import com.google.zxing.Result;
import com.google.zxing.common.HybridBinarizer;

import java.io.InputStream;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.Map;

/** Scan the invite QR from Host Control (MIR MEDIA LABS on the PC). Camera2 + ZXing core, no Google services.
 *  Returns RESULT_OK with extra "text". "From a photo" decodes a screenshot of the QR instead. */
public class QrScanActivity extends Activity {
    private static final int CAM = 51, PHOTO = 52;
    private TextureView preview;
    private TextView hint;
    private CameraDevice cam;
    private CameraCaptureSession session;
    private CaptureRequest.Builder req;
    private ImageReader reader;
    private HandlerThread bg;
    private Handler bgH;
    private Size size;
    private int sensor = 90;
    private boolean torch = false, hasFlash = false;
    private volatile boolean done = false, busy = false;
    private final MultiFormatReader zx = new MultiFormatReader();

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Ui.init(this);
        Theme.apply(this);
        Window w = getWindow();
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        w.setStatusBarColor(0xFF000000);
        w.setNavigationBarColor(0xFF000000);
        Map<DecodeHintType, Object> hints = new EnumMap<>(DecodeHintType.class);
        hints.put(DecodeHintType.POSSIBLE_FORMATS, Arrays.asList(BarcodeFormat.QR_CODE));
        hints.put(DecodeHintType.TRY_HARDER, Boolean.TRUE);
        zx.setHints(hints);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF000000);
        preview = new TextureView(this);
        root.addView(preview, new FrameLayout.LayoutParams(-1, -1));
        root.addView(new Frame(this), new FrameLayout.LayoutParams(-1, -1));

        LinearLayout top = Ui.hbox(this);
        top.setPadding(Ui.dp(8), Ui.dp(30), Ui.dp(8), Ui.dp(8));
        TextView close = Ui.text(this, "[[close]]", 22, 0xFFFFFFFF);
        close.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
        close.setOnClickListener(v -> finish());
        top.addView(close);
        TextView title = Ui.bold(this, "SCAN INVITE", 14, 0xFFFFFFFF);
        title.setLetterSpacing(0.18f);
        title.setGravity(Gravity.CENTER);
        top.addView(title, Ui.lpw(1));
        TextView fl = Ui.text(this, "[[bolt]]", 20, 0xFFFFFFFF);
        fl.setPadding(Ui.dp(12), Ui.dp(10), Ui.dp(12), Ui.dp(10));
        fl.setOnClickListener(v -> toggleTorch(fl));
        top.addView(fl);
        root.addView(top, new FrameLayout.LayoutParams(-1, -2, Gravity.TOP));

        LinearLayout bottom = Ui.vbox(this);
        bottom.setGravity(Gravity.CENTER_HORIZONTAL);
        bottom.setPadding(Ui.dp(24), Ui.dp(12), Ui.dp(24), Ui.dp(36));
        hint = Ui.text(this, "Point at the invite QR code.\nOn the PC: MIR MEDIA LABS → Host Control → Invite / QR", 13.5f, 0xFFFFFFFF);
        hint.setGravity(Gravity.CENTER);
        hint.setLineSpacing(0, 1.3f);
        hint.setShadowLayer(6, 0, 1, 0xFF000000);
        bottom.addView(hint);
        TextView photo = Ui.button(this, "[[image]]  FROM A PHOTO / SCREENSHOT", Ui.VIO, false);
        photo.setOnClickListener(v -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*");
            try { startActivityForResult(i, PHOTO); } catch (Exception e) { say("No photo picker on this device"); }
        });
        bottom.addView(photo, Ui.margins(Ui.lp(Ui.WRAP, Ui.WRAP), 0, 16, 0, 0));
        root.addView(bottom, new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM));
        setContentView(root);
        Ui.insets(root);
    }

    @Override protected void onResume() {
        super.onResume();
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAM);
            return;
        }
        startCamera();
    }

    @Override protected void onPause() { closeCamera(); super.onPause(); }

    @Override public void onRequestPermissionsResult(int rc, String[] p, int[] g) {
        if (rc != CAM) return;
        if (g.length == 0 || g[0] != PackageManager.PERMISSION_GRANTED)
            say("Camera permission is off — use \"From a photo\", or paste the invite link instead");
    }

    private void say(String s) { hint.setText(s); }

    // ── camera ───────────────────────────────────────────────────────────
    private void startCamera() {
        if (cam != null || done) return;
        bg = new HandlerThread("mml-qr");
        bg.start();
        bgH = new Handler(bg.getLooper());
        if (preview.isAvailable()) openCamera();
        else preview.setSurfaceTextureListener(new TextureView.SurfaceTextureListener() {
            @Override public void onSurfaceTextureAvailable(SurfaceTexture s, int w, int h) { openCamera(); }
            @Override public void onSurfaceTextureSizeChanged(SurfaceTexture s, int w, int h) { fit(); }
            @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture s) { return true; }
            @Override public void onSurfaceTextureUpdated(SurfaceTexture s) { }
        });
    }

    private void openCamera() {
        try {
            CameraManager cm = (CameraManager) getSystemService(Context.CAMERA_SERVICE);
            String id = null;
            for (String c : cm.getCameraIdList()) {
                Integer face = cm.getCameraCharacteristics(c).get(CameraCharacteristics.LENS_FACING);
                if (face != null && face == CameraCharacteristics.LENS_FACING_BACK) { id = c; break; }
                if (id == null) id = c;
            }
            if (id == null) { say("No camera found — use \"From a photo\" or paste the invite link"); return; }
            CameraCharacteristics ch = cm.getCameraCharacteristics(id);
            Integer so = ch.get(CameraCharacteristics.SENSOR_ORIENTATION);
            sensor = so == null ? 90 : so;
            Boolean fl = ch.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
            hasFlash = fl != null && fl;
            StreamConfigurationMap map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
            size = pick(map == null ? null : map.getOutputSizes(ImageFormat.YUV_420_888));
            reader = ImageReader.newInstance(size.getWidth(), size.getHeight(), ImageFormat.YUV_420_888, 2);
            reader.setOnImageAvailableListener(this::frame, bgH);
            cm.openCamera(id, new CameraDevice.StateCallback() {
                @Override public void onOpened(CameraDevice d) { cam = d; session(); }
                @Override public void onDisconnected(CameraDevice d) { d.close(); cam = null; }
                @Override public void onError(CameraDevice d, int e) { d.close(); cam = null; runOnUiThread(() -> say("Camera unavailable (" + e + ") — use \"From a photo\" or paste the link")); }
            }, bgH);
        } catch (SecurityException e) {
            say("Camera permission is off");
        } catch (Exception e) {
            say("Camera unavailable — use \"From a photo\" or paste the link");
        }
    }

    /** ~1280×720 is plenty for a QR on a monitor and keeps decoding fast. */
    private static Size pick(Size[] all) {
        if (all == null || all.length == 0) return new Size(1280, 720);
        Size best = all[0];
        long target = 1280L * 720;
        for (Size s : all) {
            long a = (long) s.getWidth() * s.getHeight();
            if (Math.abs(a - target) < Math.abs((long) best.getWidth() * best.getHeight() - target)) best = s;
        }
        return best;
    }

    private void session() {
        try {
            SurfaceTexture st = preview.getSurfaceTexture();
            st.setDefaultBufferSize(size.getWidth(), size.getHeight());
            Surface view = new Surface(st);
            runOnUiThread(this::fit);
            req = cam.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            req.addTarget(view);
            req.addTarget(reader.getSurface());
            req.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
            cam.createCaptureSession(Arrays.asList(view, reader.getSurface()), new CameraCaptureSession.StateCallback() {
                @Override public void onConfigured(CameraCaptureSession s) {
                    session = s;
                    try { s.setRepeatingRequest(req.build(), null, bgH); } catch (Exception ignored) { }
                }
                @Override public void onConfigureFailed(CameraCaptureSession s) { runOnUiThread(() -> say("Camera couldn't start — use \"From a photo\"")); }
            }, bgH);
        } catch (Exception e) {
            runOnUiThread(() -> say("Camera couldn't start — use \"From a photo\""));
        }
    }

    /** Centre-crop the preview (the camera buffer is landscape; this screen is portrait). */
    private void fit() {
        if (size == null || preview.getWidth() == 0) return;
        float vw = preview.getWidth(), vh = preview.getHeight();
        boolean swap = sensor % 180 != 0;
        float cw = swap ? size.getHeight() : size.getWidth(), ch = swap ? size.getWidth() : size.getHeight();
        float sx = vw / cw, sy = vh / ch, s = Math.max(sx, sy);
        Matrix m = new Matrix();
        m.setScale(s / sx, s / sy, vw / 2, vh / 2);
        preview.setTransform(m);
    }

    private void toggleTorch(TextView btn) {
        if (!hasFlash || req == null || session == null) return;
        torch = !torch;
        req.set(CaptureRequest.FLASH_MODE, torch ? CaptureRequest.FLASH_MODE_TORCH : CaptureRequest.FLASH_MODE_OFF);
        btn.setTextColor(torch ? Ui.AMB : 0xFFFFFFFF);
        Icons.tint(btn);
        try { session.setRepeatingRequest(req.build(), null, bgH); } catch (Exception ignored) { }
    }

    private void frame(ImageReader r) {
        Image img = r.acquireLatestImage();
        if (img == null) return;
        try {
            if (done || busy) return;
            busy = true;
            Image.Plane y = img.getPlanes()[0];
            int w = img.getWidth(), h = img.getHeight(), rs = y.getRowStride();
            byte[] data = new byte[w * h];
            java.nio.ByteBuffer buf = y.getBuffer();
            if (rs == w) buf.get(data, 0, Math.min(data.length, buf.remaining()));
            else for (int row = 0; row < h; row++) { buf.position(row * rs); buf.get(data, row * w, Math.min(w, buf.remaining())); }
            LuminanceSource src = new PlanarYUVLuminanceSource(data, w, h, 0, 0, w, h, false);
            String text = decode(src);
            if (text != null) found(text);
        } catch (Exception ignored) {
        } finally {
            busy = false;
            img.close();
        }
    }

    private String decode(LuminanceSource src) {
        for (int pass = 0; pass < 2; pass++) {
            try {
                Result res = zx.decodeWithState(new BinaryBitmap(new HybridBinarizer(pass == 0 ? src : src.invert())));
                if (res != null && res.getText() != null) return res.getText();
            } catch (Exception ignored) {
            } finally { zx.reset(); }
        }
        return null;
    }

    private void found(String text) {
        if (Invite.parse(text) == null) {
            runOnUiThread(() -> say("That QR isn't a MIR MEDIA LABS invite.\nUse the one from Host Control → Invite / QR."));
            return;
        }
        done = true;
        try {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null && android.os.Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE));
        } catch (Exception ignored) { }
        runOnUiThread(() -> { setResult(RESULT_OK, new Intent().putExtra("text", text)); finish(); });
    }

    @Override protected void onActivityResult(int rq, int rs, Intent data) {
        super.onActivityResult(rq, rs, data);
        if (rq != PHOTO || rs != RESULT_OK || data == null || data.getData() == null) return;
        try (InputStream in = getContentResolver().openInputStream(data.getData())) {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inSampleSize = 1;
            Bitmap bm = BitmapFactory.decodeStream(in, null, o);
            if (bm == null) { say("Couldn't open that picture"); return; }
            if (bm.getWidth() > 2400 || bm.getHeight() > 2400) {
                float k = 2400f / Math.max(bm.getWidth(), bm.getHeight());
                bm = Bitmap.createScaledBitmap(bm, Math.round(bm.getWidth() * k), Math.round(bm.getHeight() * k), true);
            }
            int[] px = new int[bm.getWidth() * bm.getHeight()];
            bm.getPixels(px, 0, bm.getWidth(), 0, 0, bm.getWidth(), bm.getHeight());
            String text = decode(new RGBLuminanceSource(bm.getWidth(), bm.getHeight(), px));
            if (text == null) say("No QR code found in that picture — try a sharper screenshot");
            else found(text);
        } catch (Exception e) {
            say("Couldn't read that picture");
        }
    }

    private void closeCamera() {
        try { if (session != null) session.close(); } catch (Exception ignored) { }
        try { if (cam != null) cam.close(); } catch (Exception ignored) { }
        try { if (reader != null) reader.close(); } catch (Exception ignored) { }
        session = null; cam = null; reader = null;
        if (bg != null) { bg.quitSafely(); bg = null; }
    }

    /** Dimmed surround + accent corner brackets around the scan square. */
    private static final class Frame extends View {
        private final Paint dim = new Paint(), line = new Paint(Paint.ANTI_ALIAS_FLAG);
        Frame(Context c) {
            super(c);
            dim.setColor(0x99000000);
            line.setColor(Ui.VIO);
            line.setStyle(Paint.Style.STROKE);
            line.setStrokeWidth(Ui.dp(4));
            line.setStrokeCap(Paint.Cap.ROUND);
        }
        @Override protected void onDraw(Canvas cv) {
            float w = getWidth(), h = getHeight(), s = Math.min(w, h) * 0.68f;
            RectF r = new RectF((w - s) / 2, (h - s) / 2 - Ui.dp(30), (w + s) / 2, (h + s) / 2 - Ui.dp(30));
            Path p = new Path();
            p.setFillType(Path.FillType.EVEN_ODD);
            p.addRect(0, 0, w, h, Path.Direction.CW);
            p.addRoundRect(r, Ui.dp(22), Ui.dp(22), Path.Direction.CW);
            cv.drawPath(p, dim);
            float k = s * 0.16f, rr = Ui.dp(22);
            Path c = new Path();
            c.moveTo(r.left, r.top + k); c.lineTo(r.left, r.top + rr); c.quadTo(r.left, r.top, r.left + rr, r.top); c.lineTo(r.left + k, r.top);
            c.moveTo(r.right - k, r.top); c.lineTo(r.right - rr, r.top); c.quadTo(r.right, r.top, r.right, r.top + rr); c.lineTo(r.right, r.top + k);
            c.moveTo(r.right, r.bottom - k); c.lineTo(r.right, r.bottom - rr); c.quadTo(r.right, r.bottom, r.right - rr, r.bottom); c.lineTo(r.right - k, r.bottom);
            c.moveTo(r.left + k, r.bottom); c.lineTo(r.left + rr, r.bottom); c.quadTo(r.left, r.bottom, r.left, r.bottom - rr); c.lineTo(r.left, r.bottom - k);
            cv.drawPath(c, line);
        }
    }
}
