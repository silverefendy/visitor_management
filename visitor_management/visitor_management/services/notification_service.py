"""
VMS Notification Service
========================

Sistem notifikasi yang extensible untuk Employee Entry events.

Arsitektur:
  - Setiap event (entry created, approved, checked out) memanggil
    dispatch_employee_entry_notification()
  - Dispatcher mencari semua handler yang relevan dan menjalankannya
  - Handler baru bisa ditambah tanpa ubah kode inti

Handler saat ini:
  1. Realtime desk notification (ERPNext notification bell)
  2. Email ke HR Manager / Visitor Manager
  3. Custom notification rules per-employee (VMS Employee Notification Rule)

Untuk ditambah nanti:
  - WhatsApp: tambahkan _send_whatsapp_notification()
  - FCM push : tambahkan _send_push_notification()
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


# =============================================================================
# PUBLIC API
# =============================================================================

def dispatch_employee_entry_notification(doc, event: str) -> None:
	"""
	Entry point utama. Dipanggil setiap kali ada perubahan status
	pada Employee Entry Request.

	event: 'created' | 'approved' | 'rejected' | 'completed' | 'checked_out'
	"""
	try:
		context = _build_context(doc, event)
		_send_realtime_notification(context)
		_send_email_notification(context)
		_process_custom_rules(context)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"VMS Notification Error [{event}] {doc.name}",
		)


# =============================================================================
# INTERNAL -- Context builder
# =============================================================================

def _build_context(doc, event: str) -> dict:
	emp_data = frappe.db.get_value(
		"Employee",
		doc.employee,
		["employee_name", "department", "reports_to", "user_id", "company"],
		as_dict=True,
	) or {}

	supervisor_user = None
	if emp_data.get("reports_to"):
		supervisor_user = frappe.db.get_value(
			"Employee", emp_data["reports_to"], "user_id"
		)

	event_labels = {
		"created": "Pengajuan Masuk Dibuat",
		"approved": "Karyawan Disetujui Masuk",
		"rejected": "Pengajuan Ditolak",
		"completed": "Karyawan Selesai Kegiatan",
		"checked_out": "Karyawan Check Out",
	}

	return {
		"doc": doc,
		"event": event,
		"event_label": event_labels.get(event, event),
		"employee_id": doc.employee,
		"employee_name": doc.employee_name or emp_data.get("employee_name", ""),
		"department": doc.department or emp_data.get("department", ""),
		"employee_user_id": emp_data.get("user_id"),
		"supervisor_user_id": supervisor_user,
		"purpose": doc.purpose or "",
		"check_in_time": str(doc.check_in_time)[:16] if doc.check_in_time else "-",
		"check_out_time": str(doc.check_out_time)[:16] if doc.check_out_time else "-",
		"entry_name": doc.name,
		"timestamp": now_datetime(),
	}


# =============================================================================
# HANDLER 1 -- Realtime notification
# =============================================================================

def _send_realtime_notification(ctx: dict) -> None:
	recipients = _get_manager_users()

	if ctx["supervisor_user_id"] and ctx["supervisor_user_id"] not in recipients:
		recipients.append(ctx["supervisor_user_id"])

	if not recipients:
		return

	event = ctx["event"]
	if event not in ("created", "approved", "checked_out"):
		return

	message_map = {
		"created": f"{ctx['employee_name']} ({ctx['department']}) mengajukan masuk area. Menunggu approval.",
		"approved": f"{ctx['employee_name']} ({ctx['department']}) telah disetujui masuk.",
		"checked_out": f"{ctx['employee_name']} ({ctx['department']}) telah check out.",
	}
	message = message_map.get(event, f"{ctx['employee_name']}: {ctx['event_label']}")

	for user in recipients:
		try:
			frappe.publish_realtime(
				"vms_employee_entry_notification",
				{
					"event": event,
					"event_label": ctx["event_label"],
					"employee": ctx["employee_id"],
					"employee_name": ctx["employee_name"],
					"department": ctx["department"],
					"entry": ctx["entry_name"],
					"message": message,
					"timestamp": str(ctx["timestamp"]),
				},
				user=user,
				after_commit=True,
			)
		except Exception:
			pass

	frappe.publish_realtime(
		"vms_employee_entry_update",
		{"event": event, "entry": ctx["entry_name"], "employee_name": ctx["employee_name"]},
		after_commit=True,
	)


# =============================================================================
# HANDLER 2 -- Email notification
# =============================================================================

def _send_email_notification(ctx: dict) -> None:
	if not _email_notifications_enabled():
		return

	event = ctx["event"]
	if event not in ("created", "checked_out"):
		return

	recipients = _get_manager_emails()
	if not recipients:
		return

	employee_name = ctx["employee_name"]
	department = ctx["department"]
	entry_name = ctx["entry_name"]

	if event == "created":
		subject = f"[VMS] Pengajuan Masuk: {employee_name}"
		message = f"""
<p>Pengajuan masuk area baru dari karyawan:</p>
<table border="0" cellpadding="6" style="font-size:14px">
  <tr><td><b>Nama</b></td><td>: {employee_name}</td></tr>
  <tr><td><b>Departemen</b></td><td>: {department}</td></tr>
  <tr><td><b>Keperluan</b></td><td>: {ctx['purpose'] or '-'}</td></tr>
  <tr><td><b>Waktu Check In</b></td><td>: {ctx['check_in_time']}</td></tr>
  <tr><td><b>No. Entry</b></td><td>: {entry_name}</td></tr>
</table>
<br><p>Silakan approve atau reject di sistem ERPNext.</p>
"""
	else:
		subject = f"[VMS] Check Out: {employee_name}"
		message = f"""
<p>Karyawan telah check out dari area:</p>
<table border="0" cellpadding="6" style="font-size:14px">
  <tr><td><b>Nama</b></td><td>: {employee_name}</td></tr>
  <tr><td><b>Departemen</b></td><td>: {department}</td></tr>
  <tr><td><b>Check In</b></td><td>: {ctx['check_in_time']}</td></tr>
  <tr><td><b>Check Out</b></td><td>: {ctx['check_out_time']}</td></tr>
  <tr><td><b>No. Entry</b></td><td>: {entry_name}</td></tr>
</table>
"""

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			delayed=True,
			reference_doctype="Employee Entry Request",
			reference_name=entry_name,
		)
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title=f"VMS Email Error [{event}] {entry_name}")


# =============================================================================
# HANDLER 3 -- Custom notification rules per-employee
# =============================================================================

def _process_custom_rules(ctx: dict) -> None:
	"""
	Proses aturan notifikasi custom per-employee.
	Doctype: VMS Employee Notification Rule

	Contoh rule:
	  employee   = HR-EMP-00005  (Direktur)
	  notify_users = user1, user2
	  events     = created,approved
	  channel    = realtime | email | both
	"""
	try:
		if not frappe.db.table_exists("VMS Employee Notification Rule"):
			return

		rules = frappe.get_all(
			"VMS Employee Notification Rule",
			filters={"employee": ctx["employee_id"], "enabled": 1},
			fields=["name", "notify_users", "events", "channel", "custom_message"],
		)

		for rule in rules:
			rule_events = [e.strip() for e in (rule.events or "").split(",")]
			if ctx["event"] not in rule_events:
				continue

			notify_users = [u.strip() for u in (rule.notify_users or "").split(",") if u.strip()]
			if not notify_users:
				continue

			channel = rule.channel or "realtime"
			msg = rule.custom_message or (
				f"{ctx['employee_name']} ({ctx['department']}): {ctx['event_label']}"
			)

			if channel in ("realtime", "both"):
				for user in notify_users:
					try:
						frappe.publish_realtime(
							"vms_custom_rule_notification",
							{
								"rule": rule.name,
								"event": ctx["event"],
								"employee_name": ctx["employee_name"],
								"message": msg,
								"entry": ctx["entry_name"],
							},
							user=user,
							after_commit=True,
						)
					except Exception:
						pass

			if channel in ("email", "both"):
				try:
					frappe.sendmail(
						recipients=notify_users,
						subject=f"[VMS] {ctx['event_label']}: {ctx['employee_name']}",
						message=msg,
						delayed=True,
						reference_doctype="Employee Entry Request",
						reference_name=ctx["entry_name"],
					)
				except Exception:
					pass
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title="VMS Custom Rule Processing Error")


# =============================================================================
# UTILITIES
# =============================================================================

def _email_notifications_enabled() -> bool:
	try:
		if frappe.db.exists("VMS Notification Settings", "VMS Notification Settings"):
			return bool(
				frappe.db.get_single_value("VMS Notification Settings", "enable_email_notifications")
			)
	except Exception:
		pass
	return False


def _get_manager_users() -> list:
	manager_roles = ["HR Manager", "Visitor Manager", "System Manager"]
	users = set()
	for role in manager_roles:
		role_users = frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User"},
			pluck="parent",
		)
		users.update(role_users)

	active_users = []
	for user in users:
		if user in ("Guest", "Administrator"):
			continue
		if frappe.db.get_value("User", user, "enabled"):
			active_users.append(user)
	return active_users


def _get_manager_emails() -> list:
	users = _get_manager_users()
	emails = []
	for user in users:
		email = frappe.db.get_value("User", user, "email")
		if email:
			emails.append(email)
	return emails
