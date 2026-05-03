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
  for (var k in args) p.append(k, typeof args[k] === "object" ? JSON.stringify(args[k]) : args[k]);

  var headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"};
  if (httpMethod === "POST") {
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    headers["X-Frappe-CSRF-Token"] = csrf();
  }

  var url = "/api/method/" + method;
  var options = {method: httpMethod, credentials: "same-origin", headers: headers};
  if (httpMethod === "POST") options.body = p;
  else if (p.toString()) url += "?" + p.toString();

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
    .catch(function(e) { if (fail) fail(e.toString()); });
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

function createEntry() {
  var purpose = document.getElementById("purpose").value.trim();
  if (!purpose) {
    showNotice("warning", "Isi keperluan / keterangan terlebih dahulu.");
    return;
  }
  api("visitor_management.visitor_management.api.create_employee_entry", {purpose: purpose}, function(r) {
    showNotice("success", r && r.message ? r.message : "Pengajuan dibuat.");
    document.getElementById("purpose").value = "";
    loadData();
  });
}

function loadData() {
  api("visitor_management.visitor_management.api.get_employee_entry_data", {}, function(d) {
    if (d && d.message) showNotice("warning", d.message);
    document.getElementById("manager-panel").style.display = d && d.is_manager ? "block" : "none";
    document.getElementById("active-panel").style.display = d && d.is_manager ? "block" : "none";
    document.getElementById("completed-panel").style.display = d && d.is_manager ? "block" : "none";
    renderTable("mine-list", d.mine || [], false);
    renderTable("pending-list", d.pending || [], true);
    renderTable("active-list", d.active || [], true);
    renderTable("completed-list", d.completed || [], true);
    document.getElementById("mine-count").textContent = (d.mine || []).length;
  });
}

function renderTable(id, rows, selectable) {
  var el = document.getElementById(id);
  if (!rows.length) {
    el.innerHTML = "<div class=\"empty\">Tidak ada data.</div>";
    return;
  }
  var checkbox = selectable ? "<th><input type=\"checkbox\" onchange=\"toggleAll('" + id + "', this.checked)\"></th>" : "";
  var body = rows.map(function(r) {
    return "<tr>" +
      (selectable ? "<td><input type=\"checkbox\" class=\"row-check\" value=\"" + esc(r.name) + "\"></td>" : "") +
      "<td><strong>" + esc(r.employee_name) + "</strong><br><small>" + esc(r.name) + "</small></td>" +
      "<td>" + esc(r.department) + "</td>" +
      "<td>" + esc(r.purpose) + "</td>" +
      "<td>" + esc(timeText(r.check_in_time)) + "</td>" +
      "<td>" + statusPill(r.status) + "</td>" +
      "</tr>";
  }).join("");
  el.innerHTML = "<table><thead><tr>" + checkbox + "<th>Karyawan</th><th>Departemen</th><th>Keperluan</th><th>Check In</th><th>Status</th></tr></thead><tbody>" + body + "</tbody></table>";
}

function toggleAll(id, checked) {
  Array.prototype.forEach.call(document.querySelectorAll("#" + id + " .row-check"), function(el) {
    el.checked = checked;
  });
}

function selectedIds(id) {
  return Array.prototype.map.call(document.querySelectorAll("#" + id + " .row-check:checked"), function(el) {
    return el.value;
  });
}

function bulkReject() {
  var reason = prompt("Alasan penolakan:");
  if (!reason) return;
  bulkAction("reject", "pending-list", reason);
}

function bulkAction(action, listId, reason) {
  listId = listId || "pending-list";
  var ids = selectedIds(listId);
  if (!ids.length) {
    showNotice("warning", "Pilih minimal satu data.");
    return;
  }
  api("visitor_management.visitor_management.api.bulk_employee_entry_action", {
    entry_ids: JSON.stringify(ids),
    action: action,
    reason: reason || ""
  }, function(r) {
    showNotice("success", "Bulk action selesai: " + (r.results || []).length + " data diproses.");
    loadData();
  });
}

function statusPill(status) {
  var cls = "pending";
  if (status === "Approved") cls = "approved";
  if (status === "Rejected") cls = "rejected";
  if (status === "Completed") cls = "completed";
  if (status === "Checked Out") cls = "checkout";
  return "<span class=\"status " + cls + "\">" + esc(status) + "</span>";
}

function timeText(value) {
  return value ? String(value).substring(0, 16) : "-";
}

window.onload = loadData;
setInterval(loadData, 30000);
