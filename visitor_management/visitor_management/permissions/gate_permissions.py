import frappe
from frappe import _

GATE_ROLES = {"System Manager", "Visitor Manager", "Visitor Security", "Security User"}


def ensure_gate_access(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if not (roles & GATE_ROLES):
		frappe.throw(_("Akses gate ditolak"), frappe.PermissionError)
