var mode = "checkin";
var visitor = null;
var scanner = null;
var scannerRunning = false;

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

  var headers = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
  };
  var token = csrf();
  if (httpMethod === "POST") {
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    if (token) headers["X-Frappe-CSRF-Token"] = token;
  }

  var url = "/api/method/" + method;
  var options = {
    method: httpMethod,
    credentials: "same-origin",
    headers: headers
  };
  if (httpMethod === "POST") {
    options.body = p;
  } else if (p.toString()) {
    url += "?" + p.toString();
  }

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
      if (!d.__ok) {
        if (fail) fail(extractError(d) || ("HTTP " + d.__http_status));
        return;
      }
      if (d.exc || d._server_messages) {
        if (fail) fail(extractError(d));
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
    } catch (e) {
      return d._server_messages;
    }
  }
  if (d.exception) return d.exception;
  if (d.exc) return d.exc;
  if (d.message) return typeof d.message === "string" ? d.message : JSON.stringify(d.message);
  return "Request gagal";
}

function setMode(m) {
  mode = m;
  document.getElementById("btn-in").className = "mode-btn" + (m === "checkin" ? " active-in" : "");
  document.getElementById("btn-out").className = "mode-btn" + (m === "checkout" ? " active-out" : "");
  document.getElementById("mode-title").textContent = m === "checkin" ? "Check In Tamu" : "Check Out Tamu";
  reset();
}

function cari() {
  var val = document.getElementById("vid-input").value.trim();
  if (!val) { alert2("warning", "Masukkan Visitor ID"); return; }
  loadVisitor(val);
}

function normalisasiQR(input) {
  var val = (input || "").trim();
  if (!val) return "";
  if (val.charAt(0) === "{") return val;
  return JSON.stringify({visitor_id: val.toUpperCase()});
}

function loadVisitor(input) {
  var qr = normalisasiQR(input);
  if (!qr) { alert2("warning", "Data QR / Visitor ID kosong"); return; }

  api(
    "visitor_management.visitor_management.api.get_visitor_by_qr",
    {qr_data: qr},
    function(v) {
      if (!v || v.error) { alert2("error", v ? v.error : "Visitor ID tidak ditemukan"); return; }
      visitor = v;
      tampil(v);
    },
    function(e) { alert2("error", "Error: " + e); }
  );
}

function mulaiScanner() {
  if (!window.Html5QrcodeScanner) {
    alert2("error", "Library scanner gagal dimuat. Cek koneksi internet/CDN.");
    return;
  }
  if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    alert2("error", "Browser hanya mengizinkan kamera dari HTTPS atau localhost. Buka halaman via HTTPS untuk memakai scanner kamera.");
    return;
  }
  if (scannerRunning) return;

  document.getElementById("camera-status").textContent = "Membuka kamera...";
  var config = {
    fps: 10,
    qrbox: { width: 250, height: 250 },
    rememberLastUsedCamera: true
  };
  if (window.Html5QrcodeScanType) {
    config.supportedScanTypes = [Html5QrcodeScanType.SCAN_TYPE_CAMERA];
  }
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
    if (!decodedText) return;
    document.getElementById("camera-status").textContent = "QR terbaca. Memuat data visitor...";
    document.getElementById("vid-input").value = decodedText.charAt(0) === "{" ? "" : decodedText;
    stopScanner();
    loadVisitor(decodedText);
  }, function() {});

  scannerRunning = true;
  document.getElementById("camera-status").textContent = "Kamera aktif. Arahkan ke QR code visitor.";
}

function stopScanner() {
  if (scanner && scannerRunning) {
    scanner.clear().catch(function() {});
  }
  scanner = null;
  scannerRunning = false;
  document.getElementById("camera-status").textContent = "Scanner berhenti.";
}

function tampil(v) {
  var warna = {
    "Registered": "#6c757d",
    "Awaiting Approval": "#f39c12",
    "Approved": "#3498db",
    "Completed": "#9b59b6",
    "Checked Out": "#1abc9c",
    "Rejected": "#e74c3c"
  };
  var c = warna[v.status] || "#888";

  document.getElementById("status-area").innerHTML =
    "<span class=\"status-badge\" style=\"background:" + c + "22;color:" + c + ";border:1px solid " + c + "\">" + v.status + "</span>";

  document.getElementById("info-grid").innerHTML = [
    ["Nama Tamu", v.visitor_name],
    ["Perusahaan", v.visitor_company || "-"],
    ["Karyawan Dituju", v.host_employee_name],
    ["Departemen", v.department || "-"],
    ["Keperluan", v.visit_purpose],
    ["Identitas", (v.id_type || "") + ": " + (v.id_number || "-")],
    ["Check In", v.check_in_time || "Belum"],
    ["Visitor ID", v.name]
  ].map(function(r) {
    return "<div class=\"info-item\"><label>" + r[0] + "</label><span>" + r[1] + "</span></div>";
  }).join("");

  var bisaIn = v.status === "Registered";
  var bisaOut = v.status === "Completed";
  var bisa = mode === "checkin" ? bisaIn : bisaOut;
  var label = mode === "checkin" ? "KONFIRMASI CHECK IN" : "KONFIRMASI CHECK OUT";
  var btnOk = document.getElementById("btn-ok");

  if (bisa) {
    btnOk.textContent = label;
    btnOk.disabled = false;
    btnOk.style.opacity = "1";
  } else {
    btnOk.textContent = "Tidak bisa proses - Status: " + v.status;
    btnOk.disabled = true;
    btnOk.style.opacity = "0.5";
  }

  document.getElementById("visitor-card").style.display = "block";
  document.getElementById("visitor-card").scrollIntoView({behavior: "smooth"});
}

function proses() {
  if (!visitor) return;
  var qr = JSON.stringify({visitor_id: visitor.name});
  api(
    "visitor_management.visitor_management.api.scan_qr_action",
    {qr_data: qr, action: mode},
    function(r) {
      if (r && r.status === "success") {
        alert2("success", r.message);
        muatAktif();
        setTimeout(reset, 3000);
      } else {
        alert2("error", (r && r.message) || "Gagal");
      }
    },
    function(e) { alert2("error", "Gagal: " + e); }
  );
}

function reset() {
  visitor = null;
  document.getElementById("visitor-card").style.display = "none";
  document.getElementById("vid-input").value = "";
  document.getElementById("vid-input").focus();
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
      renderVisitorTable("tabel-aktif", d.active_visitors || [], {
        empty: "Tidak ada tamu aktif",
        columns: ["Tamu", "Host", "Masuk", "Status", ""],
        mode: "active"
      });
      renderVisitorTable("tabel-pending-checkout", d.pending_checkout || [], {
        empty: "Tidak ada tamu selesai yang menunggu checkout",
        columns: ["Tamu", "Host", "Masuk", "Status", ""],
        mode: "checkout"
      });
      renderVisitorTable("tabel-rejected", d.rejected_visitors || [], {
        empty: "Tidak ada tamu rejected hari ini",
        columns: ["Tamu", "Host", "Masuk", "Alasan", "Status"],
        mode: "rejected"
      });
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
    ["Selesai", stats.completed || 0],
    ["Keluar", stats.checked_out || 0],
    ["Rejected", stats.rejected || 0]
  ].map(function(item) {
    return "<div class=\"summary-card\"><label>" + item[0] + "</label><strong>" + item[1] + "</strong></div>";
  }).join("");
}

function renderVisitorTable(id, rows, options) {
  if (!rows.length) {
    renderEmpty(id, options.empty);
    return;
  }

  var body = rows.map(function(v) {
    if (options.mode === "rejected") {
      return "<tr>" +
        visitorCell(v) +
        "<td>" + esc(v.host_employee_name || "-") + "</td>" +
        "<td>" + timeText(v.check_in_time) + "</td>" +
        "<td>" + esc(v.rejected_reason || "-") + "</td>" +
        "<td>" + statusPill(v.status) + "</td>" +
        "</tr>";
    }

    return "<tr>" +
      visitorCell(v) +
      "<td>" + esc(v.host_employee_name || "-") + "</td>" +
      "<td>" + timeText(v.check_in_time) + "</td>" +
      "<td>" + statusPill(v.status) + "</td>" +
      "<td><button onclick=\"pilih('" + esc(v.name) + "', '" + (options.mode === "checkout" ? "checkout" : "checkin") + "')\" class=\"btn btn-dark\" style=\"font-size:11px;padding:4px 10px\">Pilih</button></td>" +
      "</tr>";
  }).join("");

  document.getElementById(id).innerHTML =
    "<table><thead><tr>" + options.columns.map(function(c) { return "<th>" + c + "</th>"; }).join("") +
    "</tr></thead><tbody>" + body + "</tbody></table>";
}

function visitorCell(v) {
  return "<td><strong>" + esc(v.visitor_name || "-") + "</strong><br>" +
    "<small style=\"color:#888\">" + esc(v.visitor_company || "-") + " | " + esc(v.name || "-") + "</small></td>";
}

function statusPill(status) {
  var cls = "pill-info";
  if (status === "Awaiting Approval") cls = "pill-warning";
  if (status === "Approved" || status === "Checked In") cls = "pill-success";
  if (status === "Completed") cls = "pill-purple";
  if (status === "Rejected") cls = "pill-danger";
  return "<span class=\"status-pill " + cls + "\">" + esc(status || "-") + "</span>";
}

function timeText(value) {
  return value ? String(value).substring(11, 16) : "-";
}

function renderEmpty(id, text, error) {
  document.getElementById(id).innerHTML = "<p class=\"empty\"" + (error ? " style=\"color:#e74c3c\"" : "") + ">" + text + "</p>";
}

function esc(v) {
  return String(v == null ? "-" : v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function pilih(id, targetMode) {
  if (targetMode && targetMode !== mode) {
    mode = targetMode;
    document.getElementById("btn-in").className = "mode-btn" + (mode === "checkin" ? " active-in" : "");
    document.getElementById("btn-out").className = "mode-btn" + (mode === "checkout" ? " active-out" : "");
    document.getElementById("mode-title").textContent = mode === "checkin" ? "Check In Tamu" : "Check Out Tamu";
  }
  document.getElementById("vid-input").value = id;
  cari();
}

window.onload = muatAktif;
setInterval(muatAktif, 30000);
