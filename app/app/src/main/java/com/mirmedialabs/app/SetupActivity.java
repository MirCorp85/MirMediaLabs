package com.mirmedialabs.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** First run / ⚙ → Server: Media Lab addresses + its own access key. */
public class SetupActivity extends Activity {
    private EditText lan, remote, key;
    private TextView msg;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Ui.init(this);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Ui.BG);
        LinearLayout box = Ui.vbox(this);
        box.setPadding(Ui.dp(22), Ui.dp(48), Ui.dp(22), Ui.dp(28));
        sv.addView(box);

        TextView t = Ui.bold(this, "MIR MEDIA LABS", 24, Ui.INK);
        t.setLetterSpacing(0.16f);
        Ui.gradientText(t, 0xFFFFC21A, 0xFFFF5A1F);
        box.addView(t);
        TextView sub = Ui.text(this, "Connect to the Media Lab server running on your PC. Each person has their own key and sees only their own creations.", 13.5f, Ui.DIM);
        sub.setLineSpacing(0, 1.25f);
        box.addView(sub, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 10, 0, 22));

        lan = field(box, "Home Wi-Fi address", Prefs.lanUrl(this), InputType.TYPE_TEXT_VARIATION_URI);
        remote = field(box, "Away-from-home address (optional)", Prefs.remoteUrl(this), InputType.TYPE_TEXT_VARIATION_URI);
        key = field(box, "Your personal access key (from the Media Lab owner)", Prefs.key(this), InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);

        TextView go = Ui.button(this, "CONNECT", Ui.VIO, true);
        go.setOnClickListener(v -> test());
        box.addView(go, Ui.margins(Ui.lp(Ui.MATCH, Ui.dp(50)), 0, 10, 0, 0));
        msg = Ui.mono(this, "", 12.5f, Ui.DIM);
        msg.setGravity(Gravity.CENTER_HORIZONTAL);
        box.addView(msg, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 16, 0, 0));
        setContentView(sv);
    }

    private EditText field(LinearLayout box, String label, String val, int variation) {
        box.addView(Ui.label(this, label), Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 6));
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setText(val);
        e.setTextColor(Ui.INK);
        e.setHintTextColor(Ui.FAINT);
        e.setTextSize(15);
        e.setInputType(InputType.TYPE_CLASS_TEXT | variation);
        e.setPadding(Ui.dp(14), Ui.dp(12), Ui.dp(14), Ui.dp(12));
        e.setBackground(Ui.box(12, 0x66000000, Ui.LINE2));
        box.addView(e, Ui.margins(Ui.lp(Ui.MATCH, Ui.WRAP), 0, 0, 0, 16));
        return e;
    }

    private void test() {
        Prefs.save(this, lan.getText().toString(), remote.getText().toString(), key.getText().toString());
        msg.setTextColor(Ui.DIM);
        msg.setText("connecting…");
        Api api = new Api(this);
        api.probe(() -> api.get("/api/status", r -> {
            if (r.ok()) {
                msg.setTextColor(Ui.GRN);
                msg.setText("connected via " + Prefs.activeUrl(this));
                startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
                finish();
            } else {
                msg.setTextColor(Ui.RED);
                msg.setText(r.err());
            }
        }));
    }
}
