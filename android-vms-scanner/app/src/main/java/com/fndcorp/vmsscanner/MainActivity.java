package com.fndcorp.vmsscanner;

import android.Manifest;
import android.app.Activity;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;

import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URLEncoder;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class MainActivity extends Activity {
    private static final int CAMERA_REQUEST = 10;
    private static final String DEFAULT_BASE_URL = "http://10.1.0.30:8001";

    private EditText baseUrlInput;
    private EditText usernameInput;
    private EditText passwordInput;
    private EditText codeInput;
    private TextView statusText;
    private DecoratedBarcodeView barcodeView;
    private RadioGroup typeGroup;
    private RadioGroup actionGroup;
    private SharedPreferences prefs;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("vms", MODE_PRIVATE);
        setContentView(buildLayout());
    }

    private View buildLayout() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);
        scroll.addView(root);

        TextView title = title("VMS Scanner");
        root.addView(title);

        baseUrlInput = input("Server URL", prefs.getString("baseUrl", DEFAULT_BASE_URL), false);
        usernameInput = input("Username / Email", prefs.getString("username", ""), false);
        passwordInput = input("Password", "", true);
        root.addView(baseUrlInput);
        root.addView(usernameInput);
        root.addView(passwordInput);

        Button loginButton = button("Login", "#24364F");
        loginButton.setOnClickListener(v -> login());
        root.addView(loginButton);

        typeGroup = new RadioGroup(this);
        typeGroup.setOrientation(RadioGroup.HORIZONTAL);
        RadioButton visitor = radio("Visitor", 1, true);
        RadioButton employee = radio("Employee", 2, false);
        typeGroup.addView(visitor);
        typeGroup.addView(employee);
        root.addView(label("Jenis Scan"));
        root.addView(typeGroup);

        actionGroup = new RadioGroup(this);
        actionGroup.setOrientation(RadioGroup.HORIZONTAL);
        RadioButton checkin = radio("Check In", 1, true);
        RadioButton checkout = radio("Check Out", 2, false);
        actionGroup.addView(checkin);
        actionGroup.addView(checkout);
        root.addView(label("Aksi"));
        root.addView(actionGroup);

        codeInput = input("Scan result / input manual", "", false);
        root.addView(codeInput);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        Button scanButton = button("Scan Kamera", "#1F7A4D");
        Button previewButton = button("Preview", "#4B5563");
        Button processButton = button("Proses", "#24364F");
        row.addView(scanButton);
        row.addView(previewButton);
        row.addView(processButton);
        root.addView(row);

        scanButton.setOnClickListener(v -> startScanner());
        previewButton.setOnClickListener(v -> previewCode());
        processButton.setOnClickListener(v -> processCode());

        barcodeView = new DecoratedBarcodeView(this);
        barcodeView.setVisibility(View.GONE);
        root.addView(barcodeView, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 640
        ));

        statusText = new TextView(this);
        statusText.setTextColor(Color.rgb(20, 33, 61));
        statusText.setTextSize(14);
        statusText.setPadding(0, 18, 0, 18);
        root.addView(statusText);

        Button stopButton = button("Stop Kamera", "#B91C1C");
        stopButton.setOnClickListener(v -> stopScanner());
        root.addView(stopButton);

        showStatus("Login dulu, lalu scan Visitor atau Employee.");
        return scroll;
    }

    private TextView title(String text) {
        TextView v = new TextView(this);
        v.setText(text);
        v.setTextSize(24);
        v.setTextColor(Color.rgb(36, 54, 79));
        v.setPadding(0, 0, 0, 18);
        return v;
    }

    private TextView label(String text) {
        TextView v = new TextView(this);
        v.setText(text);
        v.setTextColor(Color.rgb(75, 85, 99));
        v.setPadding(0, 16, 0, 4);
        return v;
    }

    private EditText input(String hint, String value, boolean password) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setSingleLine(!hint.toLowerCase().contains("manual"));
        if (password) e.setInputType(0x00000081);
        e.setPadding(12, 10, 12, 10);
        return e;
    }

    private Button button(String text, String color) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.parseColor(color));
        b.setAllCaps(false);
        return b;
    }

    private RadioButton radio(String text, int id, boolean checked) {
        RadioButton r = new RadioButton(this);
        r.setText(text);
        r.setId(id);
        r.setChecked(checked);
        return r;
    }

    private void login() {
        String base = cleanBaseUrl();
        String username = usernameInput.getText().toString().trim();
        String password = passwordInput.getText().toString();
        if (username.isEmpty() || password.isEmpty()) {
            showStatus("Username dan password wajib diisi.");
            return;
        }

        new Thread(() -> {
            try {
                JSONObject response = request("POST", base + "/api/method/login", "usr=" + enc(username) + "&pwd=" + enc(password), false);
                prefs.edit()
                    .putString("baseUrl", base)
                    .putString("username", username)
                    .apply();
                showStatus("Login berhasil. Siap scan.");
            } catch (Exception e) {
                showStatus("Login gagal: " + e.getMessage());
            }
        }).start();
    }

    private void previewCode() {
        String code = codeInput.getText().toString().trim();
        if (code.isEmpty()) {
            showStatus("Isi atau scan kode dulu.");
            return;
        }
        boolean isVisitor = typeGroup.getCheckedRadioButtonId() == 1;
        String method = isVisitor
            ? "visitor_management.visitor_management.api.get_visitor_by_qr"
            : "visitor_management.visitor_management.api.get_employee_by_qr";
        String url = cleanBaseUrl() + "/api/method/" + method + "?qr_data=" + enc(normalizedPayload(code, isVisitor));

        new Thread(() -> {
            try {
                JSONObject response = request("GET", url, null, true);
                JSONObject message = response.optJSONObject("message");
                if (message == null) {
                    showStatus(response.toString());
                    return;
                }
                showStatus(formatPreview(message, isVisitor));
            } catch (Exception e) {
                showStatus("Preview gagal: " + e.getMessage());
            }
        }).start();
    }

    private void processCode() {
        String code = codeInput.getText().toString().trim();
        if (code.isEmpty()) {
            showStatus("Isi atau scan kode dulu.");
            return;
        }

        boolean isVisitor = typeGroup.getCheckedRadioButtonId() == 1;
        boolean isCheckin = actionGroup.getCheckedRadioButtonId() == 1;
        String action = isCheckin ? "checkin" : "checkout";
        String method = isVisitor
            ? "visitor_management.visitor_management.api.scan_qr_action"
            : "visitor_management.visitor_management.api.scan_employee_entry_action";
        String params = isVisitor
            ? "?qr_data=" + enc(normalizedPayload(code, true)) + "&action=" + enc(action)
            : "?qr_data=" + enc(normalizedPayload(code, false)) + "&action=" + enc(action) + "&purpose=" + enc("Security scan");
        String url = cleanBaseUrl() + "/api/method/" + method + params;

        new Thread(() -> {
            try {
                JSONObject response = request("GET", url, null, true);
                JSONObject message = response.optJSONObject("message");
                showStatus(message != null ? message.optString("message", response.toString()) : response.toString());
            } catch (Exception e) {
                showStatus("Proses gagal: " + e.getMessage());
            }
        }).start();
    }

    private void startScanner() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_REQUEST);
            return;
        }
        barcodeView.setVisibility(View.VISIBLE);
        barcodeView.resume();
        barcodeView.decodeSingle(new BarcodeCallback() {
            @Override
            public void barcodeResult(BarcodeResult result) {
                if (result == null || result.getText() == null) return;
                codeInput.setText(result.getText());
                stopScanner();
                showStatus("Kode terbaca: " + result.getText());
                previewCode();
            }
        });
    }

    private void stopScanner() {
        barcodeView.pause();
        barcodeView.setVisibility(View.GONE);
    }

    private JSONObject request(String method, String urlText, String body, boolean auth) throws Exception {
        URL url = new URL(urlText);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(20000);
        conn.setRequestProperty("Accept", "application/json");
        if (auth) {
            String cookie = prefs.getString("cookie", "");
            if (!cookie.isEmpty()) conn.setRequestProperty("Cookie", cookie);
        }
        if ("POST".equals(method)) {
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }

        List<String> cookieHeaders = conn.getHeaderFields().get("Set-Cookie");
        if (cookieHeaders != null && !cookieHeaders.isEmpty()) {
            List<String> simpleCookies = new ArrayList<>();
            for (String c : cookieHeaders) simpleCookies.add(c.split(";", 2)[0]);
            prefs.edit().putString("cookie", String.join("; ", simpleCookies)).apply();
        }

        int code = conn.getResponseCode();
        BufferedReader reader = new BufferedReader(new InputStreamReader(
            code >= 200 && code < 400 ? conn.getInputStream() : conn.getErrorStream(),
            StandardCharsets.UTF_8
        ));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) sb.append(line);
        JSONObject json = new JSONObject(sb.toString().isEmpty() ? "{}" : sb.toString());
        if (code < 200 || code >= 400) throw new Exception(extractError(json));
        if (json.has("exc") || json.has("_server_messages")) throw new Exception(extractError(json));
        return json;
    }

    private String extractError(JSONObject json) {
        try {
            if (json.has("_server_messages")) {
                JSONArray messages = new JSONArray(json.getString("_server_messages"));
                if (messages.length() > 0) return new JSONObject(messages.getString(0)).optString("message", messages.getString(0));
            }
            if (json.has("exception")) return json.getString("exception");
            if (json.has("exc")) return json.getString("exc");
            if (json.has("message")) return json.get("message").toString();
        } catch (Exception ignored) {}
        return "Request gagal";
    }

    private String formatPreview(JSONObject m, boolean visitor) {
        if (m.has("error")) return m.optString("error");
        if (visitor) {
            return "Visitor: " + m.optString("visitor_name") +
                "\nID: " + m.optString("name") +
                "\nStatus: " + m.optString("status") +
                "\nHost: " + m.optString("host_employee_name") +
                "\nKeperluan: " + m.optString("visit_purpose");
        }
        JSONObject entry = m.optJSONObject("active_entry");
        return "Employee: " + m.optString("employee_name") +
            "\nID: " + m.optString("name") +
            "\nDepartment: " + m.optString("department") +
            "\nEntry aktif: " + (entry == null ? "-" : entry.optString("name") + " (" + entry.optString("status") + ")");
    }

    private String normalizedPayload(String code, boolean visitor) {
        String value = code.trim();
        if (value.startsWith("{")) return value;
        return visitor ? "{\"visitor_id\":\"" + value + "\"}" : "{\"employee\":\"" + value + "\"}";
    }

    private String cleanBaseUrl() {
        String base = baseUrlInput.getText().toString().trim();
        while (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        return base.isEmpty() ? DEFAULT_BASE_URL : base;
    }

    private String enc(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (Exception e) {
            return value;
        }
    }

    private void showStatus(String message) {
        main.post(() -> statusText.setText(message));
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (barcodeView != null) barcodeView.pause();
    }

    @Override
    protected void onResume() {
        super.onResume();
    }
}
