package de.fvh02.jarvis;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/**
 * Jarvis on the projector: a full-screen view of the HUD that Fabians-HA-Jarvis serves in the home network.
 * The look lives in the add-on; the app only pairs once (address + 6-digit code), shows the page, and records
 * the microphone natively (browsers only allow the microphone over HTTPS).
 */
public class MainActivity extends Activity {
    static final String PREFS = "jarvis";
    private SharedPreferences prefs;
    private WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private MediaRecorder recorder;
    private File recording;
    private long lastBack = 0;

    private final Runnable level = new Runnable() {
        @Override
        public void run() {
            if (recorder == null) return;
            try {
                float v = Math.min(1f, recorder.getMaxAmplitude() / 20000f);
                js("jarvisLevel", String.valueOf(v));
            } catch (RuntimeException ignored) {
            }
            ui.postDelayed(this, 80);
        }
    };
    private final Runnable autoStop = new Runnable() {
        @Override
        public void run() {
            stopRecording();
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON | WindowManager.LayoutParams.FLAG_FULLSCREEN);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
        }
        if (prefs.getString("token", "").isEmpty()) showSetup(""); else showWeb();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus && Build.VERSION.SDK_INT >= 19) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
    }

    // ---------- pairing ----------
    static String normalize(String host) {
        String h = host.trim();
        if (h.isEmpty()) return h;
        if (!h.startsWith("http://") && !h.startsWith("https://")) h = "http://" + h;
        while (h.endsWith("/")) h = h.substring(0, h.length() - 1);
        String rest = h.substring(h.indexOf("//") + 2);
        if (!rest.contains(":")) h = h + ":8107";
        return h;
    }

    private void showSetup(String message) {
        web = null;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(Color.rgb(2, 7, 11));
        box.setPadding(80, 40, 80, 40);

        TextView title = new TextView(this);
        title.setText("J.A.R.V.I.S.");
        title.setTextColor(Color.rgb(69, 230, 255));
        title.setTextSize(34);
        title.setGravity(Gravity.CENTER);
        box.addView(title);

        TextView info = new TextView(this);
        info.setText("Adresse und Kopplungscode stehen in Home Assistant unter Jarvis.");
        info.setTextColor(Color.rgb(140, 190, 200));
        info.setGravity(Gravity.CENTER);
        info.setPadding(0, 10, 0, 30);
        box.addView(info);

        final EditText host = field("Adresse, z. B. 192.168.178.20", prefs.getString("host", ""), InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        box.addView(host);
        final EditText code = field("Kopplungscode (6 Ziffern)", "", InputType.TYPE_CLASS_NUMBER);
        box.addView(code);

        final CheckBox autostart = new CheckBox(this);
        autostart.setText("Beim Einschalten des Beamers starten");
        autostart.setTextColor(Color.WHITE);
        autostart.setChecked(prefs.getBoolean("autostart", true));
        box.addView(autostart);

        final Button pair = new Button(this);
        pair.setText("Koppeln");
        box.addView(pair);

        final TextView status = new TextView(this);
        status.setTextColor(Color.rgb(255, 179, 71));
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, 20, 0, 0);
        status.setText(message);
        box.addView(status);

        pair.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                final String base = normalize(host.getText().toString());
                final String pin = code.getText().toString().trim();
                if (base.isEmpty() || pin.length() != 6) {
                    status.setText("Bitte Adresse und 6-stelligen Code eingeben");
                    return;
                }
                status.setText("Verbinde …");
                pair.setEnabled(false);
                new Thread(new Runnable() {
                    @Override
                    public void run() {
                        String error;
                        try {
                            JSONObject body = new JSONObject();
                            body.put("code", pin);
                            body.put("name", "Beamer (" + Build.MODEL + ")");
                            JSONObject answer = new JSONObject(http(base + "/api/koppeln", "application/json", body.toString().getBytes("UTF-8")));
                            if (answer.has("token")) {
                                prefs.edit().putString("host", base).putString("token", answer.getString("token"))
                                        .putBoolean("autostart", autostart.isChecked()).apply();
                                ui.post(new Runnable() {
                                    @Override
                                    public void run() {
                                        showWeb();
                                    }
                                });
                                return;
                            }
                            error = answer.optString("error", "Kopplung fehlgeschlagen");
                        } catch (Exception e) {
                            error = "Jarvis nicht erreichbar (" + e.getMessage() + ") – Adresse prüfen, Add-on gestartet?";
                        }
                        final String text = error;
                        ui.post(new Runnable() {
                            @Override
                            public void run() {
                                status.setText(text);
                                pair.setEnabled(true);
                            }
                        });
                    }
                }).start();
            }
        });
        setContentView(box);
        host.requestFocus();
    }

    private EditText field(String hint, String value, int type) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setInputType(type);
        e.setSingleLine(true);
        e.setTextColor(Color.WHITE);
        e.setHintTextColor(Color.GRAY);
        e.setTextSize(22);
        return e;
    }

    /** POST with a JSON or binary body; returns the response text (also for error statuses). */
    static String http(String address, String type, byte[] body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(60000);
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", type);
        OutputStream out = c.getOutputStream();
        out.write(body);
        out.close();
        InputStream in = c.getResponseCode() < 400 ? c.getInputStream() : c.getErrorStream();
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        if (in != null) {
            byte[] chunk = new byte[8192];
            int n;
            while ((n = in.read(chunk)) > 0) buf.write(chunk, 0, n);
            in.close();
        }
        return buf.toString("UTF-8");
    }

    // ---------- the HUD ----------
    private String base() {
        return prefs.getString("host", "");
    }

    private String token() {
        return prefs.getString("token", "");
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    private void showWeb() {
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.addJavascriptInterface(new Bridge(), "JarvisApp");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (Build.VERSION.SDK_INT >= 21 && request.isForMainFrame()) offline();
            }

            @Override
            @SuppressWarnings("deprecation")
            public void onReceivedError(WebView view, int code, String description, String url) {
                offline();
            }
        });
        setContentView(web);
        web.requestFocus();
        load();
    }

    private void load() {
        if (web == null) return;
        try {
            web.loadUrl(base() + "/hud?t=" + URLEncoder.encode(token(), "UTF-8"));
        } catch (Exception e) {
            offline();
        }
    }

    private void offline() {
        if (web == null) return;
        web.loadData("<html><body style='background:#02070b;color:#45e6ff;font-family:sans-serif;display:flex;align-items:center;"
                + "justify-content:center;height:100vh;margin:0;text-align:center'><div><h1 style='letter-spacing:.4em'>J.A.R.V.I.S.</h1>"
                + "<p>Verbindung zu Home Assistant wird gesucht …</p><p style='color:#6fa9b8'>" + base() + "</p>"
                + "<p style='color:#6fa9b8'>Menü-Taste: neu koppeln</p></div></body></html>", "text/html; charset=utf-8", "UTF-8");
        ui.removeCallbacks(retry);
        ui.postDelayed(retry, 10000);
    }

    private final Runnable retry = new Runnable() {
        @Override
        public void run() {
            load();
        }
    };

    /** Calls window.fn(arg) in the HUD, if the page defines it. */
    private void js(final String fn, final String arg) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                if (web != null) web.evaluateJavascript("window." + fn + " && window." + fn + "(" + arg + ")", null);
            }
        });
    }

    // ---------- microphone ----------
    private void startRecording() {
        if (recorder != null) return;
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
            js("jarvisError", "'Bitte das Mikrofon erlauben'");
            return;
        }
        try {
            recording = new File(getCacheDir(), "frage.m4a");
            MediaRecorder r = new MediaRecorder();
            r.setAudioSource(MediaRecorder.AudioSource.MIC);
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            r.setAudioChannels(1);
            r.setAudioSamplingRate(16000);
            r.setAudioEncodingBitRate(64000);
            r.setOutputFile(recording.getAbsolutePath());
            r.prepare();
            r.start();
            recorder = r;
            js("jarvisRecording", "true");
            postAsync("/api/hoert", "{\"an\":true}");
            ui.post(level);
            ui.postDelayed(autoStop, 20000);
        } catch (Exception e) {
            recorder = null;
            js("jarvisError", "'Kein Mikrofon am Beamer – sprich über die Fernbedienung am Handy'");
        }
    }

    private void stopRecording() {
        final MediaRecorder r = recorder;
        if (r == null) return;
        recorder = null;
        ui.removeCallbacks(autoStop);
        js("jarvisRecording", "false");
        boolean ok = true;
        try {
            r.stop();
        } catch (RuntimeException e) {
            ok = false;            // too short – nothing was recorded
        }
        r.release();
        if (!ok || recording == null || recording.length() < 1500) {
            postAsync("/api/hoert", "{\"an\":false}");
            return;
        }
        final File file = recording;
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    byte[] data = new byte[(int) file.length()];
                    FileInputStream in = new FileInputStream(file);
                    int off = 0, n;
                    while (off < data.length && (n = in.read(data, off, data.length - off)) > 0) off += n;
                    in.close();
                    http(base() + "/api/sprache?quelle=beamer&t=" + URLEncoder.encode(token(), "UTF-8"), "audio/mp4", data);
                } catch (Exception e) {
                    js("jarvisError", "'Aufnahme konnte nicht gesendet werden'");
                }
            }
        }).start();
    }

    private void postAsync(final String path, final String json) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    http(base() + path + "?t=" + URLEncoder.encode(token(), "UTF-8"), "application/json", json.getBytes("UTF-8"));
                } catch (Exception ignored) {
                }
            }
        }).start();
    }

    /** Called from the HUD's JavaScript (window.JarvisApp). */
    class Bridge {
        @JavascriptInterface
        public void startRecording(String source) {
            ui.post(new Runnable() {
                @Override
                public void run() {
                    MainActivity.this.startRecording();
                }
            });
        }

        @JavascriptInterface
        public void stopRecording() {
            ui.post(new Runnable() {
                @Override
                public void run() {
                    MainActivity.this.stopRecording();
                }
            });
        }
    }

    // ---------- remote control ----------
    private static boolean talkKey(int code) {
        return code == KeyEvent.KEYCODE_DPAD_CENTER || code == KeyEvent.KEYCODE_ENTER || code == KeyEvent.KEYCODE_NUMPAD_ENTER
                || code == KeyEvent.KEYCODE_BUTTON_A || code == KeyEvent.KEYCODE_SEARCH || code == KeyEvent.KEYCODE_VOICE_ASSIST;
    }

    /** Remote keys are handled here, before the WebView sees them, so every device behaves the same. */
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        boolean down = event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0;
        if (code == KeyEvent.KEYCODE_MENU || code == KeyEvent.KEYCODE_SETTINGS) {
            if (down) {
                new AlertDialog.Builder(this).setTitle("Jarvis").setMessage("Neu koppeln?")
                        .setPositiveButton("Ja", (d, w) -> {
                            prefs.edit().remove("token").apply();
                            showSetup("");
                        })
                        .setNegativeButton("Nein", null).show();
            }
            return true;
        }
        if (web == null) return super.dispatchKeyEvent(event);
        if (talkKey(code)) {
            if (down) {
                if (recorder != null) stopRecording();
                else web.evaluateJavascript("dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13}))", null);
            }
            return true;
        }
        if (code == KeyEvent.KEYCODE_BACK) {
            if (down) {
                if (recorder != null) {
                    stopRecording();
                } else {
                    web.evaluateJavascript("dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',keyCode:27}))", null);
                    long now = System.currentTimeMillis();
                    if (now - lastBack < 2000) finish();
                    lastBack = now;
                }
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onDestroy() {
        stopRecording();
        super.onDestroy();
    }
}
