# =============================================================================
# mobile.py — Visitor Management
# Mobile API endpoints untuk Flutter VMS App
#
# Lokasi file ini di server:
#   /home/frappe/frappe-bench/apps/visitor_management/visitor_management/visitor_management/mobile.py
#
# Setelah upload/edit file ini, jalankan di server:
#   bench clear-cache && bench restart
# =============================================================================

import frappe
from frappe import _
from frappe.utils import today

# =============================================================================
# NAVIGATION & FEATURE FLAGS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_mobile_navigation():
	"""Menu navigasi dinamis untuk Flutter app."""
	roles = frappe.get_roles(frappe.session.user)
	is_manager = "Visitor Manager" in roles or "System Manager" in roles

	menu_items = [
		{
			"id": "scanner",
			"label": "Scanner",
			"route": "/scanner",
			"icon_key": "qr_code_scanner",
			"order": 1,
			"group": "Operations",
			"permissions": ["visitor.scan"],
			"feature_flag": None,
		},
		{
			"id": "visitors",
			"label": "Active Visitors",
			"route": "/visitors",
			"icon_key": "people",
			"order": 2,
			"group": "Operations",
			"permissions": [],
			"feature_flag": None,
		},
		{
			"id": "approvals",
			"label": "Approvals",
			"route": "/approvals",
			"icon_key": "check_circle",
			"order": 3,
			"group": "Operations",
			"permissions": [],
			"feature_flag": None,
		},
		{
			"id": "activity",
			"label": "Activity Log",
			"route": "/activity",
			"icon_key": "history",
			"order": 4,
			"group": "Reports",
			"permissions": [],
			"feature_flag": None,
		},
	]

	# Tambah menu khusus manager
	if is_manager:
		menu_items.append({
			"id": "reports",
			"label": "Reports",
			"route": "/activity",
			"icon_key": "bar_chart",
			"order": 5,
			"group": "Reports",
			"permissions": ["visitor.report.read"],
			"feature_flag": "enable_reports",
		})

	return {"menu_items": menu_items}


@frappe.whitelist(allow_guest=False)
def get_feature_flags():
	"""Feature flags untuk kontrol fitur di Flutter app."""
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


# =============================================================================
# DASHBOARD CARDS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_dashboard_cards():
	"""Statistik ringkas untuk dashboard cards di Flutter app."""
	try:
		waiting = frappe.db.count(
			"Visitor", filters={"status": "Awaiting Approval"}
		)
		checked_in = frappe.db.count(
			"Visitor", filters={"status": ["in", ["Approved", "Checked In"]]}
		)
		completed = frappe.db.count(
			"Visitor", filters={"status": "Completed"}
		)
		checked_out = frappe.db.count(
			"Visitor",
			filters=[["status", "=", "Checked Out"], ["creation", ">=", today()]],
		)

		return [
			{
				"id": "waiting",
				"title": "Menunggu Approval",
				"value": str(waiting),
				"icon_key": "hourglass",
				"order": 1,
				"route": "/approvals",
			},
			{
				"id": "active",
				"title": "Tamu Aktif",
				"value": str(checked_in),
				"icon_key": "people",
				"order": 2,
				"route": "/visitors",
			},
			{
				"id": "completed",
				"title": "Selesai",
				"value": str(completed),
				"icon_key": "check_circle",
				"order": 3,
				"route": None,
			},
			{
				"id": "checked_out",
				"title": "Checked Out Hari Ini",
				"value": str(checked_out),
				"icon_key": "logout",
				"order": 4,
				"route": None,
			},
		]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile get_dashboard_cards Error")
		return []


# =============================================================================
# VISITORS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_active_visitors(query=""):
	"""Daftar visitor aktif untuk halaman Visitors di Flutter."""
	active_statuses = ["Awaiting Approval", "Approved", "Checked In", "Completed"]

	if query:
		# Frappe tidak support OR filter langsung, pakai raw SQL
		visitors = frappe.db.sql("""
			SELECT
				name, visitor_name, host_employee_name,
				status, check_in_time, department
			FROM `tabVisitor`
			WHERE status IN %(statuses)s
			  AND (visitor_name LIKE %(q)s OR host_employee_name LIKE %(q)s)
			ORDER BY check_in_time DESC
			LIMIT 50
		""", {"statuses": active_statuses, "q": "%{}%".format(query)}, as_dict=True)
	else:
		visitors = frappe.get_all(
			"Visitor",
			filters=[["status", "in", active_statuses]],
			fields=["name", "visitor_name", "host_employee_name", "status", "check_in_time", "department"],
			order_by="check_in_time desc",
			limit_page_length=50,
		)

	return [
		{
			"id": v.name,
			"visitor_name": v.visitor_name,
			"host_name": v.host_employee_name or "-",
			"status": v.status,
			"check_in_time": str(v.check_in_time)[:16] if v.check_in_time else "-",
			"gate": None,
		}
		for v in visitors
	]


# =============================================================================
# APPROVALS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_pending_approvals():
	"""Daftar visitor yang menunggu approval."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_manager = "System Manager" in roles or "Visitor Manager" in roles

	filters = {"status": "Awaiting Approval"}
	if not is_manager:
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if not employee:
			return []
		filters["host_employee"] = employee

	rows = frappe.get_all(
		"Visitor",
		filters=filters,
		fields=["name", "visitor_name", "host_employee_name", "visit_purpose", "check_in_time"],
		order_by="check_in_time asc",
	)

	return [
		{
			"id": r.name,
			"visitor_name": r.visitor_name,
			"host_name": r.host_employee_name or "-",
			"purpose": r.visit_purpose or "-",
			"requested_at": str(r.check_in_time)[:16] if r.check_in_time else "-",
		}
		for r in rows
	]


@frappe.whitelist(allow_guest=False)
def submit_approval(approval_id, action, reason=""):
	"""Approve atau reject visitor dari Flutter app."""
	if not frappe.db.exists("Visitor", approval_id):
		frappe.throw(_("Visitor tidak ditemukan"))

	visitor = frappe.get_doc("Visitor", approval_id)

	if action == "approve":
		return visitor.approve_visit()
	elif action == "reject":
		return visitor.reject_visit(reason or "Ditolak via mobile app")
	else:
		frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


# =============================================================================
# ACTIVITY LOG
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_recent_activity():
	"""Riwayat aktivitas terbaru untuk Flutter app."""
	try:
		logs = frappe.get_all(
			"Visitor Log",
			fields=["name", "visitor", "action", "action_time", "action_by", "remarks"],
			order_by="action_time desc",
			limit_page_length=30,
		)

		return [
			{
				"id": log.name,
				"type": log.action or "Unknown",
				"message": "{0} — {1}".format(
					log.visitor or "-",
					log.remarks or log.action or "-",
				),
				"time": str(log.action_time)[:16] if log.action_time else "-",
			}
			for log in logs
		]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile get_recent_activity Error")
		return []


# =============================================================================
# SCAN PROCESSING
# =============================================================================

@frappe.whitelist(allow_guest=False)
def process_scan(qr_code, action=None):
	"""
	Endpoint scan utama dari Flutter app.
	Backward compatible:
	- action 'checkIn' | 'checkOut' | 'employeeEntry' keeps the old explicit flow.
	- action empty/'auto' lets backend resolve and execute the next action.
	"""
	from visitor_management.visitor_management.api import scan_qr

	try:
		if not action or str(action).lower() in {"resolve", "preview"}:
			result = scan_qr(qr_code=qr_code, action="resolve")
		elif str(action).lower() == "auto":
			result = scan_qr(qr_code=qr_code, action="auto")
		elif action == "checkIn":
			result = scan_qr(qr_code=qr_code, action="checkin")
		elif action == "checkOut":
			result = scan_qr(qr_code=qr_code, action="checkout")
		elif action == "employeeEntry":
			result = scan_qr(qr_code=qr_code, action="employeeCheckIn")
		else:
			frappe.throw(_("Aksi scan tidak dikenali: {0}").format(action))

		status = result.get("status", "error") if result else "error"
		message = result.get("message", "Terjadi kesalahan") if result else "Terjadi kesalahan"

		response = {
			"success": result.get("success", status == "success") if result else False,
			"status": status,
			"message": message,
			"reference_id": result.get("visitor") or result.get("entry") if result else None,
		}
		if result:
			response.update(result)
		return response
	except frappe.exceptions.ValidationError as e:
		return {
			"success": False,
			"status": "error",
			"message": str(e),
			"reference_id": None,
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile process_scan Error")
		return {
			"success": False,
			"status": "error",
			"message": "Terjadi kesalahan server. Coba lagi.",
			"reference_id": None,
		}
