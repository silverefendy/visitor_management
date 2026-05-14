var mode = "checkin";
var scanTarget = "visitor";
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

var employeeSuggestTimer = null;
var employeeSuggestMap = {};

function bindEmployeeSuggest() {
  var input = document.getElementById("vid-input");
  if (!input) return;
  input.addEventListener("input", function() {
    if (scanTarget !== "employee") return;
    var keyword = input.value.trim();
    if (employeeSuggestTimer) clearTimeout(employeeSuggestTimer);
    employeeSuggestTimer = setTimeout(function() { fetchEmployeeSuggestions(keyword); }, 200);
  });
}

function fetchEmployeeSuggestions(keyword) {
  var datalist = document.getElementById("employee-suggest");
  if (!datalist) return;
  if (!keyword || keyword.length < 2) {
    datalist.innerHTML = "";
    employeeSuggestMap = {};
    return;
  }
  api("visitor_management.visitor_management.api.search_employee_entry_candidates", {keyword: keyword, limit: 12}, function(rows) {
    rows = rows || [];
    employeeSuggestMap = {};
    datalist.innerHTML = rows.map(function(r) {
      var value = r.value || "";
      employeeSuggestMap[value] = r;
      return '<option value="' + esc(value) + '" label="' + esc(r.label || value) + '"></option>';
    }).join("");
  });
}


function setScanTarget(target) {
  if (scannerRunning) stopScanner();
  scanTarget = target;
  document.getElementById("target-visitor").className = "target-btn" + (target === "visitor" ? " active" : "");
  document.getElementById("target-employee").className = "target-btn" + (target === "employee" ? " active" : "");
  document.getElementById("scan-title").textContent = target === "visitor" ? "Scan QR / Barcode Tamu" : "Scan Barcode Karyawan";
  document.getElementById("vid-input").placeholder = target === "visitor" ? "Ketik Visitor ID (VIS-2026-05-00001)" : "Ketik kode karyawan (EMP:HR-EMP-00001 / Employee ID)";
  setModeTitle();
  reset();
}

function setMode(m) {
  mode = m;
  document.getElementById("btn-in").className = "mode-btn" + (m === "checkin" ? " active-in" : "");
  document.getElementById("btn-out").className = "mode-btn" + (m === "checkout" ? " active-out" : "");
  setModeTitle();
  reset();
}

function setModeTitle() {
  var targetLabel = scanTarget === "visitor" ? "Tamu" : "Karyawan";
  document.getElementById("mode-title").textContent = (mode === "checkin" ? "Check In " : "Check Out ") + targetLabel;
}



function cari() {
  var val = document.getElementById("vid-input").value.trim();
  if (!val) { alert2("warning", scanTarget === "visitor" ? "Masukkan Visitor ID" : "Masukkan kode karyawan"); return; }
  loadRecord(val);
}

function normalisasiQR(input) {
  var val = (input || "").trim();
  if (!val) return "";
  if (val.charAt(0) === "{") return val;
  if (scanTarget === "employee") return JSON.stringify({employee_id: val});
  return JSON.stringify({visitor_id: val.toUpperCase()});
}

function loadRecord(input) {
  if (scanTarget === "employee") {
    loadEmployee(input);
    return;
  }
  loadVisitor(input);
}

function loadVisitor(input) {
  var value = (input || "").trim();
  var payload = {visitor_id: value.toUpperCase()};
  var qr = value.charAt(0) === "{" ? value : JSON.stringify(payload);
  if (!qr) { alert2("warning", "Data QR / Visitor ID kosong"); return; }

  api(
    "visitor_management.visitor_management.api.get_visitor_by_qr",
    {qr_data: qr},
    function(v) {
      if (!v || v.error) { alert2("error", v ? v.error : "Visitor ID tidak ditemukan"); return; }
      v.record_type = "visitor";
      visitor = v;
      tampil(v);
    },
    function(e) { alert2("error", "Error: " + e); }
  );
}

function loadEmployee(input) {
  var qr = normalisasiQR(input);
  if (!qr) { alert2("warning", "Data barcode / kode karyawan kosong"); return; }

  api(
    "visitor_management.visitor_management.api.get_employee_by_barcode",
    {qr_data: qr},
    function(emp) {
      if (!emp || emp.error) { alert2("error", emp ? emp.error : "Karyawan tidak ditemukan"); return; }
      emp.record_type = "employee";
      emp.qr_data = qr;
      visitor = emp;
      tampil(emp);
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
    document.getElementById("camera-status").textContent = "Barcode terbaca. Memuat data...";
    document.getElementById("vid-input").value = decodedText.charAt(0) === "{" ? "" : decodedText;
    stopScanner();
    loadRecord(decodedText);
  }, function() {});

  scannerRunning = true;
  document.getElementById("camera-status").textContent = scanTarget === "visitor" ? "Kamera aktif. Arahkan ke QR code visitor." : "Kamera aktif. Arahkan ke barcode karyawan.";
}

function stopScanner() {
  if (scanner && scannerRunning) {
    scanner.clear().catch(function() {});
  }
  scanner = null;
  scannerRunning = false;
  document.getElementById("camera-status").textContent = "Scanner berhenti.";
}

function tampil(record) {
  if (record.record_type === "employee") {
    tampilEmployee(record);
    return;
  }
  tampilVisitor(record);
}

function tampilVisitor(v) {
  var warna = {
    "Registered": "#6c757d",
    "Awaiting Approval": "#f39c12",
    "Approved": "#3498db",
    "Completed": "#9b59b6",
    "Checked Out": "#1abc9c",
    "Rejected": "#e74c3c"
  };
  var c = warna[v.status] || "#888";

  document.getElementById("record-card-title").textContent = "Data Tamu Ditemukan";
  document.getElementById("status-area").innerHTML =
    "<span class=\"status-badge\" style=\"background:" + c + "22;color:" + c + ";border:1px solid " + c + "\">" + esc(v.status) + "</span>";

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
    return "<div class=\"info-item\"><label>" + esc(r[0]) + "</label><span>" + esc(r[1]) + "</span></div>";
  }).join("");

  var bisaIn = v.status === "Registered";
  var bisaOut = v.status === "Completed";
  updateProcessButton(mode === "checkin" ? bisaIn : bisaOut, v.status, mode === "checkin" ? "KONFIRMASI CHECK IN" : "KONFIRMASI CHECK OUT");
}
function tampilEmployee(emp) {
  var status = emp.entry_status || "Belum Check In";
  var warna = {
    "Belum Check In": "#6c757d",
    "Pending Approval": "#f39c12",
    "Approved": "#3498db",
    "Completed": "#9b59b6",
    "Checked Out": "#1abc9c",
    "Rejected": "#e74c3c"
  };
  var c = warna[status] || "#888";

  document.getElementById("record-card-title").textContent = "Data Karyawan Ditemukan";
  document.getElementById("status-area").innerHTML =
    "<span class=\"status-badge\" style=\"background:" + c + "22;color:" + c + ";border:1px solid " + c + "\">" + esc(status) + "</span>";

  document.getElementById("info-grid").innerHTML = [
    ["Nama Karyawan", emp.employee_name],
    ["Employee ID", emp.name],
    ["Departemen", emp.department || "-"],
    ["Kode Barcode", emp.barcode_text || ("EMP:" + emp.name)],
    ["Entry Request", emp.entry || "Belum ada"],
    ["Check In", emp.check_in_time || "Belum"],
    ["Approved", emp.approved_at || "Belum"],
    ["Completed", emp.completed_at || "Belum"]
  ].map(function(r) {
    return "<div class=\"info-item\"><label>" + esc(r[0]) + "</label><span>" + esc(r[1]) + "</span></div>";
  }).join("");

  var bisaIn = !emp.entry_status;
  var bisaOut = emp.entry_status === "Completed";
  updateProcessButton(mode === "checkin" ? bisaIn : bisaOut, status, mode === "checkin" ? "AJUKAN CHECK IN KARYAWAN" : "KONFIRMASI CHECK OUT KARYAWAN");
}

function updateProcessButton(canProcess, status, label) {
  var btnOk = document.getElementById("btn-ok");
  if (canProcess) {
    btnOk.textContent = label;
    btnOk.disabled = false;
    btnOk.style.opacity = "1";
  } else {
    btnOk.textContent = "Tidak bisa proses - Status: " + status;
    btnOk.disabled = true;
    btnOk.style.opacity = "0.5";
  }

  document.getElementById("visitor-card").style.display = "block";
  document.getElementById("visitor-card").scrollIntoView({behavior: "smooth"});
}

function proses() {
  if (!visitor) return;
  if (visitor.record_type === "employee") {
  prosesEmployee();
  return;
  }
  prosesVisitor();
}

function prosesVisitor() {

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

function prosesEmployee() {
  api(
    "visitor_management.visitor_management.api.scan_employee_entry_barcode",
    {qr_data: visitor.qr_data || JSON.stringify({employee: visitor.name}), action: mode},
    function(r) {
      if (r && r.status === "success") {
        alert2("success", r.message || "Aksi karyawan berhasil diproses.");
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
    setModeTitle();
  }
  document.getElementById("vid-input").value = id;
  cari();
}

function bindClick(id, handler) {
  var el = document.getElementById(id);
  if (el) el.addEventListener("click", handler);
}

function initScannerPage() {
  bindClick("target-visitor", function() { setScanTarget("visitor"); });
  bindClick("target-employee", function() { setScanTarget("employee"); });
  bindClick("btn-in", function() { setMode("checkin"); });
  bindClick("btn-out", function() { setMode("checkout"); });
  setModeTitle();
  muatAktif();
  bindEmployeeSuggest();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initScannerPage);
} else {
  initScannerPage();
}

setInterval(muatAktif, 30000);
