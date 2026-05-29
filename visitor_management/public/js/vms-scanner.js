var scanTarget = "auto";
var visitor = null;
var pendingResolution = null;
var scanner = null;
var scannerRunning = false;
var processing = false;

function csrf() {
  if (window.csrf_token && window.csrf_token !== "None") return window.csrf_token;
  if (window.frappe && frappe.csrf_token) return frappe.csrf_token;
  var meta = document.querySelector("meta[name=\"csrf-token\"]");
  if (meta && meta.content) return meta.content;
  var m = document.cookie.match("(^|;)\\s*csrf_token\\s*=\\s*([^;]+)");
  return m ? decodeURIComponent(m.pop()) : "";
}

function api(method, args, ok, fail) {
  args = args || {};
  requestApi(method, args, "POST", function(message) {
    if (ok) ok(message);
  }, function(error) {
    if (String(error || "").toLowerCase().indexOf("invalid request") !== -1) {
      requestApi(method, args, "GET", ok, fail);
      return;
    }
    if (fail) fail(error);
  });
}

function requestApi(method, args, httpMethod, ok, fail) {
  var p = new URLSearchParams();
  for (var k in args) p.append(k, typeof args[k] === "object" ? JSON.stringify(args[k]) : args[k]);

  var headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"};
  var token = csrf();
  if (httpMethod === "POST") {
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    if (token) headers["X-Frappe-CSRF-Token"] = token;
  }

  var url = "/api/method/" + method;
  var options = {method: httpMethod, credentials: "same-origin", headers: headers};
  if (httpMethod === "POST") options.body = p;
  else if (p.toString()) url += "?" + p.toString();

  fetch(url, options)
    .then(function(r) {
      return r.text().then(function(text) {
        var data = {};
        try { data = text ? JSON.parse(text) : {}; }
        catch (e) { data = {message: text || r.statusText}; }
        data.__http_status = r.status;
        data.__ok = r.ok;
        return data;
      });
    })
    .then(function(d) {
      if (!d.__ok) { if (fail) fail(extractError(d) || ("HTTP " + d.__http_status)); return; }
      if (d.exc || d._server_messages) { if (fail) fail(extractError(d)); return; }
      if (d.message && (d.message.success === false || d.message.status === "error")) {
        if (fail) fail(d.message.message || "Request gagal");
        return;
      }
      if (ok) ok(d.message);
    })
    .catch(function(e) { if (fail) fail(e.toString()); });
}

function extractError(d) {
  if (!d) return "Request gagal";
  if (d._server_messages) {
    try {
      var messages = JSON.parse(d._server_messages);
      if (messages.length) return JSON.parse(messages[0]).message || messages[0];
    } catch (e) { return d._server_messages; }
  }
  if (d.exception) return d.exception;
  if (d.exc) return d.exc;
  if (d.message) return typeof d.message === "string" ? d.message : JSON.stringify(d.message);
  return "Request gagal";
}

function setScanTarget(target) {
  if (scannerRunning) stopScanner();
  scanTarget = target;
  document.getElementById("target-visitor").className = "target-btn" + (target === "visitor" ? " active" : "");
  document.getElementById("target-employee").className = "target-btn" + (target === "employee" ? " active" : "");
  document.getElementById("scan-title").textContent = target === "visitor" ? "Scan QR / Barcode Tamu" : "Scan Barcode Karyawan";
  document.getElementById("vid-input").placeholder = target === "visitor" ? "Ketik Visitor ID (VIS-2026-05-00001)" : "Ketik kode karyawan (EMP:HR-EMP-00001 / Employee ID)";
  reset();
}

function setMode() {
  alert2("warning", "Mode manual tidak dipakai lagi. Scan akan otomatis menentukan aksi yang benar.");
}

function setModeTitle() {}

function cari() {
  var val = document.getElementById("vid-input").value.trim();
  if (!val) { alert2("warning", scanTarget === "visitor" ? "Masukkan Visitor ID" : "Masukkan kode karyawan"); return; }
  resolveScan(val);
}

function normalisasiQR(input) {
  var val = (input || "").trim();
  if (!val) return "";
  if (val.charAt(0) === "{") return val;
  if (scanTarget === "employee") return JSON.stringify({employee_id: val});
  return JSON.stringify({visitor_id: val.toUpperCase()});
}

function resolveScan(input) {
  if (processing) return;
  var qr = normalisasiQR(input);
  if (!qr) { alert2("warning", "Data scan kosong"); return; }
  processing = true;
  setLoading(true, "Memvalidasi scan...");

  api(
    "visitor_management.visitor_management.api.resolve_scan_action",
    {qr_code: qr},
    function(resolved) {
      processing = false;
      setLoading(false);
      if (!resolved) { alert2("error", "Scan tidak valid"); return; }
      resolved.qr_code = qr;
      pendingResolution = resolved;
      if (resolved.next_action === "INVALID") {
        visitor = null;
        pendingResolution = null;
        renderResolved(resolved, false);
        alert2("error", resolved.message || "QR tidak berlaku");
        feedback(false);
        return;
      }
      visitor = resolved;
      renderResolved(resolved, true);
      feedback(true);
    },
    function(e) {
      processing = false;
      setLoading(false);
      feedback(false);
      alert2("error", "Gagal memproses scan: " + e);
    }
  );
}

function loadRecord(input) { resolveScan(input); }
function loadVisitor(input) { resolveScan(input); }
function loadEmployee(input) { resolveScan(input); }

function mulaiScanner() {
  if (!window.Html5QrcodeScanner) { alert2("error", "Library scanner gagal dimuat. Cek koneksi internet/CDN."); return; }
  if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    alert2("error", "Browser hanya mengizinkan kamera dari HTTPS atau localhost. Buka halaman via HTTPS untuk memakai scanner kamera.");
    return;
  }
  if (scannerRunning || processing) return;

  document.getElementById("camera-status").textContent = "Membuka kamera...";
  var config = {fps: 10, qrbox: {width: 250, height: 250}, rememberLastUsedCamera: true};
  if (window.Html5QrcodeScanType) config.supportedScanTypes = [Html5QrcodeScanType.SCAN_TYPE_CAMERA];
  if (window.Html5QrcodeSupportedFormats) {
    config.formatsToSupport = [
      Html5QrcodeSupportedFormats.QR_CODE,
      Html5QrcodeSupportedFormats.CODE_128,
      Html5QrcodeSupportedFormats.CODE_39,
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8
    ].filter(Boolean);
  }

  scanner = new Html5QrcodeScanner("qr-reader", config, false);
  scanner.render(function(decodedText) {
    if (!decodedText || processing) return;
    document.getElementById("camera-status").textContent = "Barcode terbaca. Memvalidasi...";
    document.getElementById("vid-input").value = decodedText.charAt(0) === "{" ? "" : decodedText;
    stopScanner();
    resolveScan(decodedText);
  }, function() {});

  scannerRunning = true;
  document.getElementById("camera-status").textContent = "Kamera aktif. Arahkan ke QR / barcode.";
}

function stopScanner() {
  if (scanner && scannerRunning) scanner.clear().catch(function() {});
  scanner = null;
  scannerRunning = false;
  document.getElementById("camera-status").textContent = "Scanner berhenti.";
}

function tampil(record) { renderResolved(record, record.next_action !== "INVALID"); }

function renderResolved(data, canProcess) {
  var isEmployee = data.entity_type === "EMPLOYEE";
  var status = data.current_status || data.visitor_status || data.entry_status || data.status || "-";
  var actionLabel = labelForAction(data.next_action, isEmployee);
  var c = colorForStatus(status);

  document.getElementById("record-card-title").textContent = isEmployee ? "Konfirmasi Scan Karyawan" : "Konfirmasi Scan Tamu";
  document.getElementById("status-area").innerHTML =
    "<span class=\"status-badge\" style=\"background:" + c + "22;color:" + c + ";border:1px solid " + c + "\">" + esc(status) + "</span>" +
    "<span class=\"status-badge action-badge\">" + esc(actionLabel) + "</span>";

  var rows = isEmployee ? [
    ["Nama Karyawan", data.employee_name],
    ["Employee ID", data.employee],
    ["Departemen", data.department || "-"],
    ["Entry Request", data.entry || "Belum ada"],
    ["Aksi", actionLabel]
  ] : [
    ["Nama Tamu", data.visitor_name],
    ["Perusahaan", data.company || data.visitor_company || "-"],
    ["Karyawan Dituju", data.employee_name || data.host_employee_name || "-"],
    ["Status", status],
    ["Visitor ID", data.visitor]
  ];

  document.getElementById("info-grid").innerHTML = rows.map(function(r) {
    return "<div class=\"info-item\"><label>" + esc(r[0]) + "</label><span>" + esc(r[1]) + "</span></div>";
  }).join("");

  updateProcessButton(canProcess && data.requires_confirmation !== false, status, actionLabel);
}

function labelForAction(action, isEmployee) {
  var labels = {
    CHECK_IN: "Check In Visitor",
    CHECK_OUT: "Check Out Visitor",
    EMPLOYEE_CHECK_IN: "Employee Check In",
    EMPLOYEE_CHECK_OUT: "Employee Check Out",
    WAIT_FOR_APPROVAL: "Menunggu Approval",
    WAIT_INSIDE: "Tamu Masih di Area",
    INVALID: "QR Tidak Berlaku"
  };
  return labels[action] || (isEmployee ? "Proses Karyawan" : "Proses Visitor");
}

function colorForStatus(status) {
  var warna = {
    "Registered": "#6c757d",
    "Awaiting Approval": "#f39c12",
    "Approved": "#3498db",
    "Checked In": "#27ae60",
    "Completed": "#9b59b6",
    "Checked Out": "#1abc9c",
    "Rejected": "#e74c3c",
    "Cancelled": "#e74c3c",
    "ACTIVE": "#27ae60",
    "APPROVED": "#3498db",
    "COMPLETED": "#9b59b6",
    "NO_ACTIVE_ENTRY": "#6c757d"
  };
  return warna[status] || "#888";
}

function updateProcessButton(canProcess, status, label) {
  var btnOk = document.getElementById("btn-ok");
  if (canProcess && !["WAIT_FOR_APPROVAL", "WAIT_INSIDE", "INVALID"].includes(pendingResolution && pendingResolution.next_action)) {
    btnOk.textContent = "Konfirmasi " + label;
    btnOk.disabled = false;
    btnOk.style.opacity = "1";
  } else {
    btnOk.textContent = pendingResolution && pendingResolution.next_action === "WAIT_FOR_APPROVAL" ? "Menunggu Approval" : (pendingResolution && pendingResolution.next_action === "WAIT_INSIDE" ? "Tamu masih di area" : "Tidak bisa proses - Status: " + status);
    btnOk.disabled = true;
    btnOk.style.opacity = "0.5";
  }
  document.getElementById("visitor-card").style.display = "block";
  document.getElementById("visitor-card").scrollIntoView({behavior: "smooth"});
}

function proses() {
  if (!pendingResolution || processing) return;
  if (!["CHECK_IN", "CHECK_OUT", "EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"].includes(pendingResolution.next_action)) return;
  showConfirmation(pendingResolution);
}

function showConfirmation(data) {
  var isEmployee = data.entity_type === "EMPLOYEE";
  setText("confirm-title", isEmployee ? "Konfirmasi Scan Karyawan" : confirmationTitle(data));
  setText("confirm-name", isEmployee ? data.employee_name : data.visitor_name);
  setText("confirm-company", isEmployee ? ((data.employee || "-") + " / " + (data.department || "-")) : (data.company || data.visitor_company || "-"));
  setText("confirm-action", labelForAction(data.next_action, isEmployee));
  var modal = document.getElementById("confirm-modal");
  modal.className = "confirm-modal open";
  modal.setAttribute("aria-hidden", "false");
  document.getElementById("confirm-ok").focus();
}

function confirmationTitle(data) {
  if (data.next_action === "CHECK_OUT") return "Check Out Visitor?";
  if (data.next_action === "CHECK_IN") return "Check In Visitor?";
  return "Konfirmasi Scan Tamu";
}

function cancelConfirmation() {
  closeConfirmation();
  reset();
}

function closeConfirmation() {
  var modal = document.getElementById("confirm-modal");
  if (!modal) return;
  modal.className = "confirm-modal";
  modal.setAttribute("aria-hidden", "true");
}

function executePendingScan() {
  if (!pendingResolution || processing) return;
  closeConfirmation();
  processing = true;
  setLoading(true, "Memproses konfirmasi...");
  api(
    "visitor_management.visitor_management.api.execute_scan_action",
    {qr_code: pendingResolution.qr_code, action: pendingResolution.next_action},
    function(r) {
      processing = false;
      setLoading(false);
      if (r && r.status === "success") {
        alert2("success", r.message || "Aksi berhasil diproses.");
        feedback(true);
        muatAktif();
        setTimeout(reset, 3000);
      } else {
        feedback(false);
        alert2("error", (r && r.message) || "Gagal");
      }
    },
    function(e) {
      processing = false;
      setLoading(false);
      feedback(false);
      alert2("error", "Gagal: " + e);
    }
  );
}

function setText(id, value) {
  var el = document.getElementById(id);
  if (el) el.textContent = value || "-";
}

function prosesVisitor() { proses(); }
function prosesEmployee() { proses(); }

function reset() {
  closeConfirmation();
  visitor = null;
  pendingResolution = null;
  processing = false;
  setLoading(false);
  document.getElementById("visitor-card").style.display = "none";
  document.getElementById("vid-input").value = "";
  document.getElementById("vid-input").focus();
}

function setLoading(isLoading, text) {
  var btnOk = document.getElementById("btn-ok");
  if (btnOk) btnOk.disabled = !!isLoading;
  var status = document.getElementById("camera-status");
  if (status && text) status.textContent = text;
}

function feedback(success) {
  if (navigator.vibrate) navigator.vibrate(success ? 80 : [120, 80, 120]);
}

function alert2(t, m) {
  var el = document.getElementById("alert-box");
  el.className = "alert alert-" + t;
  el.textContent = m;
  el.style.display = "block";
  setTimeout(function() { el.style.display = "none"; }, 6000);
}

function muatAktif() {
  api(
    "visitor_management.visitor_management.api.get_dashboard_data",
    {},
    function(d) {
      if (!d) {
        renderEmpty("tabel-aktif", "Gagal memuat data");
        renderEmpty("tabel-pending-checkout", "Gagal memuat data");
        renderEmpty("tabel-rejected", "Gagal memuat data");
        return;
      }
      renderSummary(d.stats || {});
      renderVisitorTable("tabel-aktif", d.active_visitors || [], {empty: "Tidak ada tamu aktif", columns: ["Tamu", "Host", "Masuk", "Status", ""], mode: "active"});
      renderVisitorTable("tabel-pending-checkout", d.pending_checkout || [], {empty: "Tidak ada tamu selesai yang menunggu checkout", columns: ["Tamu", "Host", "Masuk", "Status", ""], mode: "checkout"});
      renderVisitorTable("tabel-rejected", d.rejected_visitors || [], {empty: "Tidak ada tamu rejected hari ini", columns: ["Tamu", "Host", "Masuk", "Alasan", "Status"], mode: "rejected"});
    },
    function() {
      renderEmpty("tabel-aktif", "Gagal memuat data", true);
      renderEmpty("tabel-pending-checkout", "Gagal memuat data", true);
      renderEmpty("tabel-rejected", "Gagal memuat data", true);
    }
  );
}

function renderSummary(stats) {
  document.getElementById("summary-grid").innerHTML = [
    ["Hari Ini", stats.total_today || 0],
    ["Aktif", stats.checked_in || 0],
    ["Menunggu", stats.waiting_approval || 0],
    ["Completed", stats.completed || 0],
    ["Check Out", stats.checked_out || 0],
    ["Rejected", stats.rejected || 0]
  ].map(function(item) {
    return "<div class=\"summary-card\"><label>" + esc(item[0]) + "</label><strong>" + esc(item[1]) + "</strong></div>";
  }).join("");
}

function renderVisitorTable(id, rows, opts) {
  if (!rows || !rows.length) { renderEmpty(id, opts.empty); return; }
  var html = "<table><thead><tr>" + opts.columns.map(function(c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
  rows.forEach(function(v) {
    var statusClass = v.status === "Awaiting Approval" ? "pill-warning" : (v.status === "Rejected" ? "pill-danger" : (v.status === "Completed" ? "pill-purple" : "pill-success"));
    html += "<tr>";
    html += "<td><strong>" + esc(v.visitor_name) + "</strong><br><small>" + esc(v.visitor_company || "-") + "</small></td>";
    html += "<td>" + esc(v.host_employee_name || "-") + "<br><small>" + esc(v.department || "-") + "</small></td>";
    html += "<td>" + esc(v.check_in_time || "-") + "</td>";
    if (opts.mode === "rejected") {
      html += "<td>" + esc(v.rejected_reason || "-") + "</td>";
      html += "<td><span class=\"status-pill " + statusClass + "\">" + esc(v.status) + "</span></td>";
    } else {
      html += "<td><span class=\"status-pill " + statusClass + "\">" + esc(v.status) + "</span></td>";
      html += "<td><button class=\"btn btn-dark\" onclick=\"document.getElementById('vid-input').value='" + esc(v.name) + "';cari();\">Scan</button></td>";
    }
    html += "</tr>";
  });
  html += "</tbody></table>";
  document.getElementById(id).innerHTML = html;
}

function renderEmpty(id, msg) {
  document.getElementById(id).innerHTML = "<p class=\"empty\">" + esc(msg || "Tidak ada data") + "</p>";
}

function esc(v) {
  return String(v == null ? "-" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
}

window.onload = function() { muatAktif(); };
