import frappe
from frappe import _


def ensure_authenticated_user(user=None):
    """Ensure request is tied to an authenticated non-Guest user."""
    current_user = user or frappe.session.user
    if not current_user or current_user == "Guest":
        frappe.throw(_("Autentikasi diperlukan"), frappe.PermissionError)
    return current_user


def ensure_roles(allowed_roles, user=None, message=None):
    """Ensure current user has at least one role from allowed_roles."""
    current_user = ensure_authenticated_user(user)
    roles = set(frappe.get_roles(current_user))

    if roles & set(allowed_roles):
        return current_user

    frappe.throw(message or _("Akses ditolak"), frappe.PermissionError)
