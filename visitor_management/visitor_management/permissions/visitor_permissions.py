import frappe

from visitor_management.visitor_management.permissions.approval_permissions import is_approval_manager


def can_manage_visitor(doc, user=None):
	user = user or frappe.session.user
	if is_approval_manager(user):
		return True
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	return bool(employee and employee == getattr(doc, "host_employee", None))


def has_visitor_permission(doc, ptype="read", user=None):
	return can_manage_visitor(doc, user)


def visitor_query_conditions(user):
	if is_approval_manager(user):
		return None
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return "1=0"
	return "`tabVisitor`.host_employee = {0}".format(frappe.db.escape(employee))
