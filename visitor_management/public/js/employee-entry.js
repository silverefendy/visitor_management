function csrf() {
  if (window.csrf_token && window.csrf_token !== "None") return window.csrf_token;
  if (window.frappe && window.frappe.csrf_token) return window.frappe.csrf_token;

  var meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;

  var m = document.cookie.match("(^|;)\\s*csrf_token\\s*=\\s*([^;]+)");
  return m ? decodeURIComponent(m.pop()) : "";
}

function api(method, args, ok, fail) {
  args = args || {};
  postApi(method, args, function(response) {
    if (ok) ok(response);
  }, function(error) {
    if (isInvalidRequest(error)) {
      refreshCsrfToken(function() {
        postApi(method, args, function(response) {
          if (ok) ok(response);
        }, function(retryError) {
          showNotice("error", retryError);
          if (fail) fail(retryError);
        });
      }, function(tokenError) {
        showNotice("error", tokenError || error);
        if (fail) fail(tokenError || error);
      });
      return;
    }

    showNotice("error", error);
    if (fail) fail(error);
  });
}

function isInvalidRequest(error) {
  return String(error || "").toLowerCase().indexOf("invalid request") !== -1;
}

function parseApiResponse(response) {
  return response.text().then(function(responseText) {
    var data = {};
    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch (parseError) {
        data = {message: responseText};
      }
    }
    data.__ok = response.ok;
    data.__http_status = response.status;
    data.__status_text = response.statusText;
    return data;
  });
}

function responseError(data) {
  var error = getError(data) || data.__status_text || ("HTTP " + data.__http_status);
  if (data.__http_status === 400 && !isInvalidRequest(error)) {
    return "Invalid Request";
  }
  return error;
}

function refreshCsrfToken(ok, fail) {
  fetch("/api/method/visitor_management.visitor_management.api.get_csrf_token", {
    method: "GET",
    credentials: "same-origin",
    headers: {
      "Accept": "application/json",
      "X-Requested-With": "XMLHttpRequest"
    }
  })
    .then(parseApiResponse)
    .then(function(data) {
      if (!data.__ok || data.exc || data._server_messages) {
        if (fail) fail(responseError(data));
        return;
      }

      var token = data.message;
      if (!token) {
        if (fail) fail("CSRF token tidak ditemukan. Silakan refresh halaman lalu coba lagi.");
        return;
      }

      window.csrf_token = token;
      if (window.frappe) window.frappe.csrf_token = token;
      var meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) meta.content = token;
      if (ok) ok(token);
    })
    .catch(function(error) {
      if (fail) fail(error.toString());
    });
}

function postApi(method, args, ok, fail) {
  var params = new URLSearchParams();
  for (var key in args) {
    if (Object.prototype.hasOwnProperty.call(args, key)) {
      params.append(key, typeof args[key] === "object" ? JSON.stringify(args[key]) : args[key]);
    }
  }

  fetch("/api/method/" + method, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Frappe-CSRF-Token": csrf(),
      "X-Requested-With": "XMLHttpRequest"
    },
    body: params
  })
    .then(parseApiResponse)
    .then(function(data) {
      if (!data.__ok || data.exc || data._server_messages) {
        if (fail) fail(responseError(data));
        return;
      }
      if (ok) ok(data.message);
    })
    .catch(function(error) {
      if (fail) fail(error.toString());
    });
}

function getError(data) {
  if (data._server_messages) {
    try {
      var messages = JSON.parse(data._server_messages);
      if (messages.length) return JSON.parse(messages[0]).message || messages[0];
    } catch (e) {
      return data._server_messages;
    }
  }
  return data.exception || data.exc || data.message || "Request gagal";
}

function showNotice(type, message) {
  var el = document.getElementById("notice");
  el.className = "notice notice-" + type;
  el.textContent = message;
  el.style.display = "block";
  setTimeout(function() { el.style.display = "none"; }, 5000);
}

function esc(value) {
  return String(value == null ? "-" : value)
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

  api("visitor_management.visitor_management.api.create_employee_entry", {purpose: purpose}, function(response) {
    showNotice("success", response && response.message ? response.message : "Pengajuan dibuat.");
    document.getElementById("purpose").value = "";
    loadData();
  });
}

function loadData() {
  api("visitor_management.visitor_management.api.get_employee_entry_data", {}, function(data) {
    data = data || {};
    if (data.message) showNotice("warning", data.message);

    document.getElementById("manager-panel").style.display = data.is_manager ? "block" : "none";
    document.getElementById("active-panel").style.display = data.is_manager ? "block" : "none";
    document.getElementById("completed-panel").style.display = data.is_manager ? "block" : "none";

    renderTable("mine-list", data.mine || [], false);
    renderTable("pending-list", data.pending || [], true);
    renderTable("active-list", data.active || [], true);
    renderTable("completed-list", data.completed || [], true);
    document.getElementById("mine-count").textContent = (data.mine || []).length;
  });
}

function renderTable(id, rows, selectable) {
  var el = document.getElementById(id);
  if (!rows.length) {
    el.innerHTML = "<div class=\"empty\">Tidak ada data.</div>";
    return;
  }

  var checkboxHeader = selectable ? "<th><input type=\"checkbox\" onchange=\"toggleAll('" + id + "', this.checked)\"></th>" : "";
  var actionHeader = selectable ? "<th>Aksi</th>" : "";
  var body = rows.map(function(row) {
    return "<tr>" +
      (selectable ? "<td><input type=\"checkbox\" class=\"row-check\" value=\"" + esc(row.name) + "\"></td>" : "") +
      "<td><strong>" + esc(row.employee_name) + "</strong><br><small>" + esc(row.name) + "</small></td>" +
      "<td>" + esc(row.department) + "</td>" +
      "<td>" + esc(row.purpose) + "</td>" +
      "<td>" + esc(timeText(row.check_in_time)) + "</td>" +
      "<td>" + statusPill(row.status) + "</td>" +
      (selectable ? "<td>" + rowActions(id, row.name) + "</td>" : "") +
      "</tr>";
  }).join("");

  el.innerHTML = "<table><thead><tr>" + checkboxHeader + "<th>Karyawan</th><th>Departemen</th><th>Keperluan</th><th>Check In</th><th>Status</th>" + actionHeader + "</tr></thead><tbody>" + body + "</tbody></table>";
}

function rowActions(listId, id) {
  var safeId = esc(id);
  if (listId === "pending-list") {
    return "<button class=\"btn btn-success btn-sm\" onclick=\"entryAction('" + safeId + "', 'approve')\">Approve</button> " +
      "<button class=\"btn btn-danger btn-sm\" onclick=\"rejectEntry('" + safeId + "')\">Reject</button>";
  }
  if (listId === "active-list") {
    return "<button class=\"btn btn-primary btn-sm\" onclick=\"entryAction('" + safeId + "', 'complete')\">Complete</button>";
  }
  if (listId === "completed-list") {
    return "<button class=\"btn btn-primary btn-sm\" onclick=\"entryAction('" + safeId + "', 'checkout')\">Check Out</button>";
  }
  return "";
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
  }, function(response) {
    var results = response.results || [];
    var errors = results.filter(function(item) { return item.status === "error"; });
    if (errors.length) {
      showNotice("warning", "Bulk action selesai dengan " + errors.length + " error. Error pertama: " + errors[0].message);
    } else {
      showNotice("success", "Bulk action selesai: " + results.length + " data diproses.");
    }
    loadData();
  });
}

function rejectEntry(id) {
  var reason = prompt("Alasan penolakan:");
  if (!reason) return;
  entryAction(id, "reject", reason);
}

function entryAction(id, action, reason) {
  api("visitor_management.visitor_management.api.employee_entry_action", {
    entry_id: id,
    action: action,
    reason: reason || ""
  }, function(response) {
    showNotice("success", response && response.message ? response.message : "Aksi berhasil diproses.");
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

