import frappe
from frappe import _

MANAGER_ROLES = {"System Manager", "Visitor Manager", "HR Manager"}


def is_approval_manager(user=None):
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles & MANAGER_ROLES)


def ensure_can_approve(doc, user=None):
	if is_approval_manager(user):
		return
	employee = frappe.db.get_value("Employee", {"user_id": user or frappe.session.user}, "name")
	if not employee or employee != getattr(doc, "host_employee", None):
		frappe.throw(_("Anda tidak memiliki hak approval"), frappe.PermissionError)
