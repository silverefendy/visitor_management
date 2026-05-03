function csrf() {
  if (window.csrf_token && window.csrf_token !== "None") return window.csrf_token;
  var m = document.cookie.match("(^|;)\\s*csrf_token\\s*=\\s*([^;]+)");
  return m ? decodeURIComponent(m.pop()) : "";
}

function api(method, args, ok, fail) {
  args = args || {};
  requestApi(method, args, "POST", ok, function(error) {
    if (String(error || "").toLowerCase().indexOf("invalid request") !== -1) {
      requestApi(method, args, "GET", ok, fail);
      return;
    }
    showNotice("error", error);
    if (fail) fail(error);
  });
}

function requestApi(method, args, httpMethod, ok, fail) {
  var p = new URLSearchParams();
  for (var k in args) p.append(k, args[k]);

  var headers = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
  };
  if (httpMethod === "POST") {
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    headers["X-Frappe-CSRF-Token"] = csrf();
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
      return r.text().then(function(t) {
        var data;
        try { data = t ? JSON.parse(t) : {}; }
        catch(e) { data = {message: t || r.statusText}; }
        data.__ok = r.ok;
        data.__http_status = r.status;
        return data;
      });
    })
    .then(function(d) {
      if (!d.__ok) {
        if (fail) fail(getError(d) || ("HTTP " + d.__http_status));
        return;
      }
      if (d.exc || d._server_messages) {
        if (fail) fail(getError(d));
        return;
      }
      if (ok) ok(d.message);
    })
    .catch(function(e) {
      if (fail) fail(e.toString());
    });
}

function getError(d) {
  if (d._server_messages) {
    try {
      var messages = JSON.parse(d._server_messages);
      if (messages.length) return JSON.parse(messages[0]).message || messages[0];
    } catch(e) {
      return d._server_messages;
    }
  }
  return d.exception || d.exc || d.message || "Request gagal";
}

function showNotice(type, message) {
  var el = document.getElementById("notice");
  el.className = "notice notice-" + type;
  el.textContent = message;
  el.style.display = "block";
  setTimeout(function() { el.style.display = "none"; }, 5000);
}

function esc(v) {
  return String(v == null ? "-" : v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function card(v, type) {
  var approveActions = type === "pending"
    ? "<button class=\"btn btn-success\" onclick=\"approveVisitor('" + esc(v.name) + "')\">Approve</button>" +
      "<button class=\"btn btn-danger\" onclick=\"rejectVisitor('" + esc(v.name) + "')\">Reject</button>"
    : "<button class=\"btn btn-primary\" onclick=\"completeVisit('" + esc(v.name) + "')\">Selesai Kunjungan</button>";

  return "<article class=\"card\">" +
    "<h4>" + esc(v.visitor_name) + "</h4>" +
    "<div class=\"meta\">" + esc(v.name) + " | " + esc(v.status) + "</div>" +
    "<div class=\"fields\">" +
      field("Perusahaan", v.visitor_company) +
      field("Telepon", v.visitor_phone) +
      field("Host", v.host_employee_name) +
      field("Departemen", v.department) +
      field("Check In", v.check_in_time) +
      field("Identitas", (v.id_type || "") + ": " + (v.id_number || "-")) +
      "<div class=\"field purpose\"><label>Keperluan</label><span>" + esc(v.visit_purpose) + "</span></div>" +
    "</div>" +
    "<div class=\"actions\">" + approveActions + "</div>" +
  "</article>";
}

function field(label, value) {
  return "<div class=\"field\"><label>" + esc(label) + "</label><span>" + esc(value) + "</span></div>";
}

function renderList(id, rows, type) {
  var el = document.getElementById(id);
  if (!rows || !rows.length) {
    el.className = "";
    el.innerHTML = "<div class=\"empty\">Tidak ada data.</div>";
    return;
  }
  el.className = "grid";
  el.innerHTML = rows.map(function(v) { return card(v, type); }).join("");
}

function loadData() {
  api("visitor_management.visitor_management.api.employee_approval_data", {}, function(d) {
    if (d && d.message) showNotice("warning", d.message);
    var pending = d && d.pending ? d.pending : [];
    var active = d && d.active ? d.active : [];
    document.getElementById("pending-count").textContent = pending.length;
    document.getElementById("active-count").textContent = active.length;
    renderList("pending-list", pending, "pending");
    renderList("active-list", active, "active");
  });
}

function approveVisitor(id) {
  api("visitor_management.visitor_management.api.approve_visitor", {visitor_id: id}, function(r) {
    showNotice("success", r && r.message ? r.message : "Kunjungan disetujui.");
    loadData();
  });
}

function rejectVisitor(id) {
  var reason = prompt("Alasan penolakan:");
  if (!reason) return;
  api("visitor_management.visitor_management.api.reject_visitor", {visitor_id: id, reason: reason}, function(r) {
    showNotice("success", r && r.message ? r.message : "Kunjungan ditolak.");
    loadData();
  });
}

function completeVisit(id) {
  if (!confirm("Tandai kunjungan ini selesai? Security dapat check-out setelah ini.")) return;
  api("visitor_management.visitor_management.api.complete_visit", {visitor_id: id}, function(r) {
    showNotice("success", r && r.message ? r.message : "Kunjungan selesai.");
    loadData();
  });
}

window.onload = loadData;
setInterval(loadData, 30000);
