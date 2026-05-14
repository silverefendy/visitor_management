import frappe
from frappe import _
from frappe.utils import now_datetime

APPROVAL_STEPS = [
	("Supervisor", "Supervisor Approval"),
	("HR Manager", "Manager Approval"),
	("Visitor Security", "Security Approval"),
]


def next_stage(current_status):
	mapping = {
		"Draft": "Supervisor Approval",
		"Supervisor Approval": "Manager Approval",
		"Manager Approval": "Security Approval",
		"Security Approval": "Approved",
	}
	return mapping.get(current_status)


def approve_employee_entry(doc):
	status = doc.status or "Draft"
	target = next_stage(status)
	if not target:
		frappe.throw(_("Status tidak bisa di-approve: {0}").format(status))
	doc.status = target
	if target == "Approved":
		doc.approved_by = frappe.session.user
		doc.approved_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"status": "success", "message": _("Status berubah ke {0}").format(target)}
