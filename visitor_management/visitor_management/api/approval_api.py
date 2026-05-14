import frappe

from visitor_management.visitor_management.permissions.approval_permissions import ensure_can_approve
from visitor_management.visitor_management.permissions.visitor_permissions import can_manage_visitor


def _get_visitor(visitor_id):
	if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
		frappe.throw("Visitor tidak ditemukan")
	visitor = frappe.get_doc("Visitor", visitor_id)
	if not can_manage_visitor(visitor):
		raise frappe.PermissionError("Tidak ada akses")
	return visitor


@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
	visitor = _get_visitor(visitor_id)
	ensure_can_approve(visitor)
	return visitor.approve_visit()


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
	visitor = _get_visitor(visitor_id)
	ensure_can_approve(visitor)
	return visitor.reject_visit(reason)


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
	visitor = _get_visitor(visitor_id)
	return visitor.end_visit()
