# =============================================================================
# mobile.py -- Visitor Management Mobile API
# Tambahan: employee dashboard menu item
# =============================================================================

import json

import frappe
from frappe import _
from frappe.utils import now_datetime, today


def _parse_qr(qr_code):
	if not qr_code:
		frappe.throw(_("QR code tidak boleh kosong"))
	raw = str(qr_code).strip()
	payload = None
	if raw.startswith("{"):
		try:
			payload = json.loads(raw)
		except (json.JSONDecodeError, ValueError):
			pass
	if payload and isinstance(payload, dict):
		if payload.get("type") == "employee_entry" or payload.get("employee"):
			return {"entity_type": "EMPLOYEE", "employee": payload.get("employee") or payload.get("employee_id")}
		if payload.get("visitor_id"):
			return {"entity_type": "VISITOR", "visitor_id": payload["visitor_id"]}
	if raw.upper().startswith("EMP:"):
		return {"entity_type": "EMPLOYEE", "employee": raw.split(":", 1)[1].strip()}
	if raw.upper().startswith("VIS-"):
		return {"entity_type": "VISITOR", "visitor_id": raw.upper()}
	if raw.upper().startswith("HR-EMP-") or raw.upper().startswith("EMP-"):
		return {"entity_type": "EMPLOYEE", "employee": raw}
	return {"entity_type": "VISITOR", "visitor_id": raw.upper()}


def _resolve_employee_id(code):
	if not code:
		frappe.throw(_("Kode karyawan tidak boleh kosong"))
	if frappe.db.exists("Employee", code):
		return code
	for field in ("attendance_device_id", "user_id", "employee_number"):
		if frappe.get_meta("Employee").has_field(field):
			emp = frappe.db.get_value("Employee", {field: code}, "name")
			if emp:
				return emp
	frappe.throw(_("Karyawan dengan kode {0} tidak ditemukan").format(code))


def _get_visitor_next_action(status):
	return {"Registered": "CHECK_IN", "Completed": "CHECK_OUT"}.get(status)


def _get_visitor_next_action_label(action):
	return {"CHECK_IN": "Check In Visitor", "CHECK_OUT": "Check Out Visitor"}.get(action, action)


def _get_employee_next_action(entry_status):
	if entry_status is None:
		return "EMPLOYEE_CHECK_IN"
	if entry_status == "Completed":
		return "EMPLOYEE_CHECK_OUT"
	if entry_status in ("Checked Out", "Rejected"):
		return "EMPLOYEE_CHECK_IN"
	return None


@frappe.whitelist(allow_guest=False)
def resolve_scan_action(qr_code):
	try:
		parsed = _parse_qr(qr_code)
		entity_type = parsed["entity_type"]

		if entity_type == "VISITOR":
			visitor_id = parsed.get("visitor_id")
			if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
				return {"success": False, "message": _("Visitor {0} tidak ditemukan").format(visitor_id or "-")}
			v = frappe.get_doc("Visitor", visitor_id)
			next_action = _get_visitor_next_action(v.status)
			if not next_action:
				status_messages = {
					"Awaiting Approval": _("Tamu sedang menunggu approval."),
					"Approved": _("Tamu sudah berada di dalam area."),
					"Checked Out": _("Tamu sudah check out. QR tidak valid lagi."),
					"Rejected": _("Kunjungan tamu telah ditolak."),
					"Cancelled": _("Kunjungan tamu telah dibatalkan."),
				}
				return {"success": False, "message": status_messages.get(v.status, _("Status {0} tidak mendukung scan.").format(v.status))}
			return {
				"success": True, "entity_type": "VISITOR", "current_status": v.status,
				"next_action": next_action, "confirmation_required": True,
				"visitor_id": v.name, "visitor_name": v.visitor_name,
				"company": v.visitor_company or "-", "host": v.host_employee_name or "-",
				"purpose": v.visit_purpose or "-",
				"check_in_time": str(v.check_in_time)[:16] if v.check_in_time else "-",
				"action_label": _get_visitor_next_action_label(next_action),
			}

		elif entity_type == "EMPLOYEE":
			raw_emp = parsed.get("employee") or ""
			employee_id = _resolve_employee_id(raw_emp)
			emp = frappe.db.get_value("Employee", employee_id, ["name", "employee_name", "department", "status"], as_dict=True)
			if not emp:
				return {"success": False, "message": _("Data karyawan tidak ditemukan")}
			if emp.status != "Active":
				return {"success": False, "message": _("Karyawan {0} tidak aktif").format(emp.employee_name)}
			open_statuses = ["Pending Approval", "Approved", "Completed"]
			open_entries = frappe.get_all(
				"Employee Entry Request",
				filters={"employee": employee_id, "status": ["in", open_statuses]},
				fields=["name", "status", "check_in_time"],
				order_by="modified desc", limit_page_length=1,
			)
			open_entry = open_entries[0] if open_entries else None
			entry_status = open_entry.status if open_entry else None
			next_action = _get_employee_next_action(entry_status)
			if not next_action:
				status_messages = {
					"Pending Approval": _("Pengajuan masuk karyawan sedang menunggu approval."),
					"Approved": _("Karyawan sudah berada di dalam area."),
				}
				return {"success": False, "message": status_messages.get(entry_status, _("Status {0} tidak mendukung scan.").format(entry_status))}
			action_label = "Employee Check In" if next_action == "EMPLOYEE_CHECK_IN" else "Employee Check Out"
			return {
				"success": True, "entity_type": "EMPLOYEE",
				"current_status": entry_status if entry_status else "Outside",
				"next_action": next_action, "confirmation_required": True,
				"employee_id": emp.name, "employee_name": emp.employee_name,
				"department": emp.department or "-",
				"entry_id": open_entry.name if open_entry else None,
				"check_in_time": str(open_entry.check_in_time)[:16] if open_entry and open_entry.check_in_time else "-",
				"action_label": _(action_label),
			}
		else:
			return {"success": False, "message": _("Tipe entitas tidak dikenali")}
	except frappe.exceptions.ValidationError as exc:
		return {"success": False, "message": str(exc)}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile resolve_scan_action Error")
		return {"success": False, "message": _("Terjadi kesalahan server. Coba lagi.")}


@frappe.whitelist(allow_guest=False)
def execute_scan_action(qr_code, action):
	valid_actions = {"CHECK_IN", "CHECK_OUT", "EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"}
	if action not in valid_actions:
		return {"success": False, "status": "error", "message": _("Aksi tidak valid: {0}").format(action)}
	try:
		parsed = _parse_qr(qr_code)
		entity_type = parsed["entity_type"]

		if action in ("CHECK_IN", "CHECK_OUT"):
			if entity_type != "VISITOR":
				return {"success": False, "status": "error", "message": _("QR bukan untuk visitor.")}
			visitor_id = parsed.get("visitor_id")
			if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
				return {"success": False, "status": "error", "message": _("Visitor tidak ditemukan")}
			visitor = frappe.get_doc("Visitor", visitor_id)
			expected = {"CHECK_IN": "Registered", "CHECK_OUT": "Completed"}[action]
			if visitor.status != expected:
				actual_next = _get_visitor_next_action(visitor.status)
				detail = _(" (status terbaru membutuhkan {0})").format(actual_next) if actual_next else ""
				return {"success": False, "status": "invalid",
						"message": _("Tidak bisa {0}. Status visitor: {1}{2}").format(action, visitor.status, detail)}
			if action == "CHECK_IN":
				from visitor_management.visitor_management.services.visitor_service import check_in
				result = check_in(visitor)
			else:
				from visitor_management.visitor_management.services.visitor_service import check_out
				result = check_out(visitor)
			return {"success": result.get("status") == "success", "status": result.get("status", "error"), "message": result.get("message", "")}

		if action in ("EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"):
			if entity_type != "EMPLOYEE":
				return {"success": False, "status": "error", "message": _("QR bukan untuk karyawan.")}
			raw_emp = parsed.get("employee") or ""
			employee_id = _resolve_employee_id(raw_emp)
			if frappe.db.get_value("Employee", employee_id, "status") != "Active":
				return {"success": False, "status": "error", "message": _("Karyawan tidak aktif")}
			open_entries = frappe.get_all(
				"Employee Entry Request",
				filters={"employee": employee_id, "status": ["in", ["Pending Approval", "Approved", "Completed"]]},
				fields=["name", "status"], order_by="modified desc", limit_page_length=1,
			)
			open_entry_data = open_entries[0] if open_entries else None
			current_entry_status = open_entry_data.status if open_entry_data else None
			expected_action = _get_employee_next_action(current_entry_status)
			if action != expected_action:
				return {"success": False, "status": "invalid",
						"message": _("Aksi tidak sesuai. Status terbaru membutuhkan {0}, bukan {1}").format(expected_action or "tidak ada", action)}
			if action == "EMPLOYEE_CHECK_IN":
				doc = frappe.get_doc({"doctype": "Employee Entry Request", "employee": employee_id, "purpose": "Scan barcode security"})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				return {"success": True, "status": "success", "message": _("Pengajuan check-in karyawan dibuat. Menunggu approval.")}
			else:
				if not open_entry_data:
					return {"success": False, "status": "error", "message": _("Tidak ada pengajuan yang menunggu check-out.")}
				entry_doc = frappe.get_doc("Employee Entry Request", open_entry_data.name)
				result = entry_doc.checkout()
				frappe.db.commit()
				return {"success": result.get("status") == "success", "status": result.get("status", "error"), "message": result.get("message", "")}
	except frappe.exceptions.ValidationError as exc:
		return {"success": False, "status": "error", "message": str(exc)}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile execute_scan_action Error")
		return {"success": False, "status": "error", "message": _("Terjadi kesalahan server. Coba lagi.")}


@frappe.whitelist(allow_guest=False)
def get_mobile_navigation():
	roles = frappe.get_roles(frappe.session.user)
	is_manager = "Visitor Manager" in roles or "System Manager" in roles or "HR Manager" in roles
	menu_items = [
		{"id": "scanner", "label": "Scanner", "route": "/scanner", "icon_key": "qr_code_scanner", "order": 1, "group": "Operations", "permissions": ["visitor.scan"], "feature_flag": None},
		{"id": "visitors", "label": "Active Visitors", "route": "/visitors", "icon_key": "people", "order": 2, "group": "Operations", "permissions": [], "feature_flag": None},
		{"id": "approvals", "label": "Approvals", "route": "/approvals", "icon_key": "check_circle", "order": 3, "group": "Operations", "permissions": [], "feature_flag": None},
		{"id": "employee", "label": "Employee", "route": "/employee", "icon_key": "badge", "order": 4, "group": "Operations", "permissions": [], "feature_flag": None},
		{"id": "activity", "label": "Activity Log", "route": "/activity", "icon_key": "history", "order": 5, "group": "Reports", "permissions": [], "feature_flag": None},
	]
	if is_manager:
		menu_items.append({"id": "reports", "label": "Reports", "route": "/activity", "icon_key": "bar_chart", "order": 6, "group": "Reports", "permissions": ["visitor.report.read"], "feature_flag": "enable_reports"})
	return {"menu_items": menu_items}


@frappe.whitelist(allow_guest=False)
def get_feature_flags():
	roles = frappe.get_roles(frappe.session.user)
	is_manager = "Visitor Manager" in roles or "System Manager" in roles or "HR Manager" in roles
	return {
		"enable_reports": is_manager,
		"enable_manager_dashboard": is_manager,
		"enable_face_capture": False,
		"visitor.scan.checkin": True,
		"visitor.approval.act": True,
		"visitor.report.read": is_manager,
	}


@frappe.whitelist(allow_guest=False)
def get_dashboard_cards():
	try:
		waiting = frappe.db.count("Visitor", filters={"status": "Awaiting Approval"})
		checked_in = frappe.db.count("Visitor", filters={"status": ["in", ["Approved", "Checked In"]]})
		completed = frappe.db.count("Visitor", filters={"status": "Completed"})
		checked_out = frappe.db.count("Visitor", filters=[["status", "=", "Checked Out"], ["creation", ">=", today()]])
		return [
			{"id": "waiting", "title": "Menunggu Approval", "value": str(waiting), "icon_key": "hourglass", "order": 1, "route": "/approvals"},
			{"id": "active", "title": "Tamu Aktif", "value": str(checked_in), "icon_key": "people", "order": 2, "route": "/visitors"},
			{"id": "completed", "title": "Selesai", "value": str(completed), "icon_key": "check_circle", "order": 3, "route": None},
			{"id": "checked_out", "title": "Checked Out Hari Ini", "value": str(checked_out), "icon_key": "logout", "order": 4, "route": None},
		]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile get_dashboard_cards Error")
		return []


@frappe.whitelist(allow_guest=False)
def get_active_visitors(query=""):
	active_statuses = ["Awaiting Approval", "Approved", "Checked In", "Completed"]
	if query:
		visitors = frappe.db.sql(
			"""SELECT name, visitor_name, host_employee_name, status, check_in_time, department
			FROM `tabVisitor` WHERE status IN %(statuses)s
			AND (visitor_name LIKE %(q)s OR host_employee_name LIKE %(q)s)
			ORDER BY check_in_time DESC LIMIT 50""",
			{"statuses": active_statuses, "q": "%{}%".format(query)}, as_dict=True,
		)
	else:
		visitors = frappe.get_all(
			"Visitor", filters=[["status", "in", active_statuses]],
			fields=["name", "visitor_name", "host_employee_name", "status", "check_in_time", "department"],
			order_by="check_in_time desc", limit_page_length=50,
		)
	return [{"id": v.name, "visitor_name": v.visitor_name, "host_name": v.host_employee_name or "-",
			 "status": v.status, "check_in_time": str(v.check_in_time)[:16] if v.check_in_time else "-", "gate": None}
			for v in visitors]


@frappe.whitelist(allow_guest=False)
def get_pending_approvals():
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_manager = "System Manager" in roles or "Visitor Manager" in roles
	filters = {"status": "Awaiting Approval"}
	if not is_manager:
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if not employee:
			return []
		filters["host_employee"] = employee
	rows = frappe.get_all("Visitor", filters=filters,
		fields=["name", "visitor_name", "host_employee_name", "visit_purpose", "check_in_time"],
		order_by="check_in_time asc")
	return [{"id": r.name, "visitor_name": r.visitor_name, "host_name": r.host_employee_name or "-",
			 "purpose": r.visit_purpose or "-", "requested_at": str(r.check_in_time)[:16] if r.check_in_time else "-"}
			for r in rows]


@frappe.whitelist(allow_guest=False)
def submit_approval(approval_id, action, reason=""):
	if not frappe.db.exists("Visitor", approval_id):
		frappe.throw(_("Visitor tidak ditemukan"))
	visitor = frappe.get_doc("Visitor", approval_id)
	if action == "approve":
		return visitor.approve_visit()
	elif action == "reject":
		return visitor.reject_visit(reason or "Ditolak via mobile app")
	else:
		frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def get_recent_activity():
	try:
		logs = frappe.get_all("Visitor Log",
			fields=["name", "visitor", "action", "action_time", "action_by", "remarks"],
			order_by="action_time desc", limit_page_length=30)
		return [{"id": log.name, "type": log.action or "Unknown",
				 "message": "{0} \u2014 {1}".format(log.visitor or "-", log.remarks or log.action or "-"),
				 "time": str(log.action_time)[:16] if log.action_time else "-"} for log in logs]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile get_recent_activity Error")
		return []


@frappe.whitelist(allow_guest=False)
def process_scan(qr_code, action):
	action_map = {"checkIn": "CHECK_IN", "checkOut": "CHECK_OUT", "employeeEntry": "EMPLOYEE_CHECK_IN",
				  "CHECK_IN": "CHECK_IN", "CHECK_OUT": "CHECK_OUT",
				  "EMPLOYEE_CHECK_IN": "EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT": "EMPLOYEE_CHECK_OUT"}
	mapped = action_map.get(action)
	if not mapped:
		return {"status": "error", "message": _("Aksi tidak dikenali: {0}").format(action)}
	result = execute_scan_action(qr_code=qr_code, action=mapped)
	return {"status": result.get("status", "error"), "message": result.get("message", ""), "reference_id": None}
