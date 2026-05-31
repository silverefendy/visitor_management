# =============================================================================
# mobile_employee.py -- VMS Mobile Employee Dashboard API
#
# Endpoint:
#   /api/method/visitor_management.mobile_employee.get_my_employee_dashboard
#   /api/method/visitor_management.mobile_employee.get_employees_inside
#   /api/method/visitor_management.mobile_employee.get_employee_dashboard_cards
#
# Aturan akses (role-based):
#   Employee biasa  : hanya lihat data diri sendiri
#   HR Manager      : lihat semua karyawan
#   Visitor Manager : lihat semua karyawan
#   System Manager  : lihat semua karyawan
# =============================================================================

import frappe
from frappe import _
from frappe.utils import today, now_datetime


_MANAGER_ROLES = frozenset(["HR Manager", "Visitor Manager", "System Manager"])


def _is_manager(user=None) -> bool:
	user = user or frappe.session.user
	return bool(_MANAGER_ROLES & set(frappe.get_roles(user)))


def _get_employee_for_user(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


# ---------------------------------------------------------------------------
# ENDPOINT 1 -- Dashboard pribadi employee
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_my_employee_dashboard() -> dict:
	"""
	Dashboard pribadi employee yang sedang login.
	Semua role bisa akses -- employee hanya lihat miliknya sendiri.
	"""
	user = frappe.session.user
	employee_id = _get_employee_for_user(user)

	if not employee_id:
		return {
			"employee_id": None,
			"employee_name": None,
			"is_manager": _is_manager(user),
			"warning": "Akun belum terhubung ke data Karyawan. Hubungi HR/Admin.",
			"today_summary": {},
			"active_entry": None,
			"recent_entries": [],
		}

	emp = frappe.db.get_value(
		"Employee",
		employee_id,
		["employee_name", "department", "designation", "image"],
		as_dict=True,
	) or {}

	# Entry aktif (belum checkout)
	active_statuses = ["Pending Approval", "Approved", "Completed"]
	active_entries = frappe.get_all(
		"Employee Entry Request",
		filters={"employee": employee_id, "status": ["in", active_statuses]},
		fields=["name", "status", "check_in_time", "approved_at", "purpose"],
		order_by="modified desc",
		limit_page_length=1,
	)
	active_entry = _format_entry(active_entries[0]) if active_entries else None

	# Entry hari ini
	today_entries = frappe.get_all(
		"Employee Entry Request",
		filters={"employee": employee_id, "check_in_time": [">=", today()]},
		fields=["name", "status", "check_in_time", "check_out_time", "purpose"],
		order_by="check_in_time desc",
		limit_page_length=10,
	)

	# Riwayat 20 entry terakhir
	recent_entries = frappe.get_all(
		"Employee Entry Request",
		filters={"employee": employee_id},
		fields=["name", "status", "check_in_time", "check_out_time", "purpose", "approved_at"],
		order_by="check_in_time desc",
		limit_page_length=20,
	)

	# Summary hari ini
	last_check_in = None
	last_check_out = None
	if today_entries:
		last_check_in = str(today_entries[0].check_in_time)[:16] if today_entries[0].check_in_time else None
		for e in today_entries:
			if e.check_out_time:
				last_check_out = str(e.check_out_time)[:16]
				break

	return {
		"employee_id": employee_id,
		"employee_name": emp.get("employee_name", ""),
		"department": emp.get("department", ""),
		"designation": emp.get("designation", ""),
		"image": emp.get("image"),
		"is_manager": _is_manager(user),
		"today_summary": {
			"total_entries": len(today_entries),
			"currently_inside": bool(active_entry),
			"last_check_in": last_check_in,
			"last_check_out": last_check_out,
		},
		"active_entry": active_entry,
		"recent_entries": [_format_entry(e) for e in recent_entries],
	}


# ---------------------------------------------------------------------------
# ENDPOINT 2 -- Karyawan di dalam area (manager/SPV only)
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_employees_inside() -> dict:
	"""
	Daftar semua karyawan yang sedang di dalam area.
	Hanya HR Manager, Visitor Manager, System Manager yang bisa akses.
	"""
	user = frappe.session.user

	if not _is_manager(user):
		return {
			"can_access": False,
			"message": "Hanya HR Manager dan Visitor Manager yang dapat melihat data ini.",
			"total": 0,
			"employees": [],
		}

	active_statuses = ["Pending Approval", "Approved", "Completed"]
	entries = frappe.get_all(
		"Employee Entry Request",
		filters={"status": ["in", active_statuses]},
		fields=[
			"name", "employee", "employee_name", "department",
			"status", "check_in_time", "approved_at", "purpose",
		],
		order_by="check_in_time asc",
	)

	now = now_datetime()
	result = []
	for e in entries:
		duration_minutes = None
		if e.check_in_time:
			delta = now - e.check_in_time
			duration_minutes = int(delta.total_seconds() / 60)

		result.append({
			"entry_id": e.name,
			"employee_id": e.employee,
			"employee_name": e.employee_name,
			"department": e.department or "-",
			"status": e.status,
			"check_in_time": str(e.check_in_time)[:16] if e.check_in_time else "-",
			"approved_at": str(e.approved_at)[:16] if e.approved_at else "-",
			"purpose": e.purpose or "-",
			"duration_minutes": duration_minutes,
		})

	pending = sum(1 for e in result if e["status"] == "Pending Approval")
	approved = sum(1 for e in result if e["status"] in ("Approved", "Completed"))

	return {
		"can_access": True,
		"total": len(result),
		"pending_approval": pending,
		"approved_inside": approved,
		"employees": result,
	}


# ---------------------------------------------------------------------------
# ENDPOINT 3 -- Dashboard cards employee untuk mobile
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_employee_dashboard_cards() -> list:
	"""
	Stats cards untuk section Employee di mobile app.
	Employee biasa: stats diri sendiri.
	Manager/SPV  : stats semua karyawan.
	"""
	user = frappe.session.user
	is_manager = _is_manager(user)
	employee_id = _get_employee_for_user(user)

	if is_manager:
		pending = frappe.db.count("Employee Entry Request", filters={"status": "Pending Approval"})
		inside = frappe.db.count(
			"Employee Entry Request",
			filters={"status": ["in", ["Approved", "Completed"]]},
		)
		today_total = frappe.db.count(
			"Employee Entry Request",
			filters=[["check_in_time", ">=", today()], ["check_in_time", "is", "set"]],
		)
		checked_out_today = frappe.db.count(
			"Employee Entry Request",
			filters=[
				["status", "=", "Checked Out"],
				["check_out_time", ">=", today()],
				["check_out_time", "is", "set"],
			],
		)
		return [
			{"id": "emp_pending", "title": "Menunggu Approval", "value": str(pending),
			 "icon_key": "hourglass", "order": 1, "route": "/employee-inside"},
			{"id": "emp_inside", "title": "Karyawan di Area", "value": str(inside),
			 "icon_key": "badge", "order": 2, "route": "/employee-inside"},
			{"id": "emp_today", "title": "Entry Hari Ini", "value": str(today_total),
			 "icon_key": "today", "order": 3, "route": None},
			{"id": "emp_checkout", "title": "Keluar Hari Ini", "value": str(checked_out_today),
			 "icon_key": "logout", "order": 4, "route": None},
		]

	# Employee biasa
	if not employee_id:
		return []

	active = frappe.db.count(
		"Employee Entry Request",
		filters={"employee": employee_id, "status": ["in", ["Pending Approval", "Approved", "Completed"]]},
	)
	today_count = frappe.db.count(
		"Employee Entry Request",
		filters=[["employee", "=", employee_id], ["check_in_time", ">=", today()],
				 ["check_in_time", "is", "set"]],
	)
	return [
		{"id": "my_status", "title": "Status Saya",
		 "value": "Di Dalam" if active else "Di Luar",
		 "icon_key": "badge", "order": 1, "route": "/my-entry"},
		{"id": "my_today", "title": "Entry Hari Ini", "value": str(today_count),
		 "icon_key": "today", "order": 2, "route": "/my-entry"},
	]


# ---------------------------------------------------------------------------
# INTERNAL
# ---------------------------------------------------------------------------

def _format_entry(entry: dict) -> dict:
	return {
		"id": entry.get("name"),
		"status": entry.get("status"),
		"check_in_time": str(entry["check_in_time"])[:16] if entry.get("check_in_time") else "-",
		"check_out_time": str(entry["check_out_time"])[:16] if entry.get("check_out_time") else "-",
		"approved_at": str(entry["approved_at"])[:16] if entry.get("approved_at") else "-",
		"purpose": entry.get("purpose") or "-",
	}
