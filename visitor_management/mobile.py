# =============================================================================
# mobile.py — Visitor Management
# Mobile API endpoints untuk Flutter VMS App
#
# Path Frappe: visitor_management.mobile.*
# Lokasi file : visitor_management/mobile.py
#
# Flutter memanggil:
#   /api/method/visitor_management.mobile.get_dashboard_cards
#   /api/method/visitor_management.mobile.get_mobile_navigation
#   /api/method/visitor_management.mobile.get_feature_flags
#   /api/method/visitor_management.mobile.get_active_visitors
#   /api/method/visitor_management.mobile.get_pending_approvals
#   /api/method/visitor_management.mobile.submit_approval
#   /api/method/visitor_management.mobile.get_recent_activity
#   /api/method/visitor_management.mobile.resolve_scan_action  ← NEW (step 1)
#   /api/method/visitor_management.mobile.execute_scan_action  ← NEW (step 2)
#
# Setelah upload/edit file ini, jalankan di server:
#   bench clear-cache && bench restart
# =============================================================================


import frappe
from frappe import _
from frappe.utils import today


# =============================================================================
# SCAN FLOW — TWO STEP
#
# Mobile endpoints delegate to the canonical scanner engine in
# visitor_management.visitor_management.api so every client receives the same
# dynamic next_action and execution validation.
# =============================================================================

@frappe.whitelist(allow_guest=False)
def resolve_scan_action(qr_code=None, qr_data=None):
	"""Resolve scan details without database mutation for the mobile popup."""
	from visitor_management.visitor_management.api import resolve_scan_action as resolve

	try:
		return resolve(qr_code=qr_code, qr_data=qr_data)
	except frappe.exceptions.ValidationError as exc:
		return {"success": False, "status": "error", "message": str(exc)}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile resolve_scan_action Error")
		return {
			"success": False,
			"status": "error",
			"message": _("Terjadi kesalahan server. Coba lagi."),
		}


@frappe.whitelist(allow_guest=False)
def execute_scan_action(qr_code=None, qr_data=None, action=None, gate=None, device_id=None):
	"""Execute the backend-provided next_action after mobile OK confirmation."""
	from visitor_management.visitor_management.api import execute_scan_action as execute

	try:
		return execute(
			qr_code=qr_code,
			qr_data=qr_data,
			action=action,
			gate=gate,
			device_id=device_id,
		)
	except frappe.exceptions.ValidationError as exc:
		return {"success": False, "status": "error", "message": str(exc)}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Mobile execute_scan_action Error")
		return {
			"success": False,
			"status": "error",
			"message": _("Terjadi kesalahan server. Coba lagi."),
		}


# =============================================================================
# NAVIGATION & FEATURE FLAGS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_mobile_navigation():
	"""Menu navigasi dinamis untuk Flutter app."""
	roles = frappe.get_roles(frappe.session.user)
	is_manager = "VMS Manager" in roles or "System Manager" in roles

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
	is_manager = (
		"VMS Manager" in roles
		or "System Manager" in roles
		or "HR Manager" in roles
	)

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
		waiting = frappe.db.count("Visitor", filters={"status": "Awaiting Approval"})
		checked_in = frappe.db.count(
			"Visitor", filters={"status": ["in", ["Approved", "Checked In"]]}
		)
		completed = frappe.db.count("Visitor", filters={"status": "Completed"})
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
		visitors = frappe.db.sql(
			"""
			SELECT name, visitor_name, host_employee_name,
				   status, check_in_time, department
			FROM `tabVisitor`
			WHERE status IN %(statuses)s
			  AND (visitor_name LIKE %(q)s OR host_employee_name LIKE %(q)s)
			ORDER BY check_in_time DESC
			LIMIT 50
			""",
			{"statuses": active_statuses, "q": "%{}%".format(query)},
			as_dict=True,
		)
	else:
		visitors = frappe.get_all(
			"Visitor",
			filters=[["status", "in", active_statuses]],
			fields=[
				"name", "visitor_name", "host_employee_name",
				"status", "check_in_time", "department",
			],
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
	is_manager = "System Manager" in roles or "VMS Manager" in roles

	filters = {"status": "Awaiting Approval"}
	if not is_manager:
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if not employee:
			return []
		filters["host_employee"] = employee

	rows = frappe.get_all(
		"Visitor",
		filters=filters,
		fields=[
			"name", "visitor_name", "host_employee_name",
			"visit_purpose", "check_in_time",
		],
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
# LEGACY COMPAT — process_scan (deprecated, keep for backward compat)
# =============================================================================

@frappe.whitelist(allow_guest=False)
def process_scan(qr_code, action=None):
	"""Deprecated compatibility endpoint: resolve-only, never auto-executes."""
	result = resolve_scan_action(qr_code=qr_code)
	if action and result.get("success"):
		result["legacy_action_ignored"] = action
	return {
		"success": result.get("success", False),
		"status": result.get("status", "success" if result.get("success") else "error"),
		"message": result.get("message", ""),
		"reference_id": result.get("visitor") or result.get("entry"),
		**result,
	}
