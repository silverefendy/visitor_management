import frappe
from frappe import _

from visitor_management.visitor_management.permissions.auth_helpers import (
    ensure_authenticated_user,
)

MANAGER_ROLES = {"System Manager", "Visitor Manager", "HR Manager"}


def is_approval_manager(user=None):
    current_user = ensure_authenticated_user(user)
    roles = set(frappe.get_roles(current_user))
    return bool(roles & MANAGER_ROLES)


def ensure_can_approve(doc, user=None):
    if is_approval_manager(user):
        return
    employee = frappe.db.get_value(
        "Employee", {"user_id": user or frappe.session.user}, "name"
    )
    if not employee or employee != getattr(doc, "host_employee", None):
        frappe.throw(_("Anda tidak memiliki hak approval"), frappe.PermissionError)
