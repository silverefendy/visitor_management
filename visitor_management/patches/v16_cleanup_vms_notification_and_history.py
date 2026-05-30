"""Clean stale VMS objects that conflicted with Frappe v16 core behavior."""

from __future__ import annotations

import frappe

OLD_HISTORY_DOCTYPE = "VMS Cleanup Log"
NEW_HISTORY_DOCTYPE = "VMS Cleanup History"


VMS_ROLES = (
    "VMS System Admin",
    "VMS Manager",
    "Visitor Receptionist",
    "Visitor Security Guard",
    "Visitor Approver",
)


def _ensure_roles():
    for role in VMS_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role,
                    "desk_access": 1,
                    "is_custom": 1,
                    "disabled": 0,
                }
            ).insert(ignore_permissions=True)


def _copy_cleanup_history():
    if not (frappe.db.table_exists(OLD_HISTORY_DOCTYPE) and frappe.db.table_exists(NEW_HISTORY_DOCTYPE)):
        return

    fields = [field.fieldname for field in frappe.get_meta(NEW_HISTORY_DOCTYPE).fields if field.fieldname]
    old_columns = set(frappe.db.get_table_columns(OLD_HISTORY_DOCTYPE))
    common_fields = [field for field in fields if field in old_columns]
    for row in frappe.get_all(OLD_HISTORY_DOCTYPE, fields=["name", *common_fields], limit_page_length=0):
        if frappe.db.exists(NEW_HISTORY_DOCTYPE, row.name):
            continue
        doc = frappe.new_doc(NEW_HISTORY_DOCTYPE)
        doc.name = row.name
        for field in common_fields:
            doc.set(field, row.get(field))
        frappe.flags.in_vms_cleanup = True
        try:
            doc.insert(ignore_permissions=True)
        finally:
            frappe.flags.in_vms_cleanup = False


def _remove_old_cleanup_log_doctype():
    if frappe.db.exists("DocType", OLD_HISTORY_DOCTYPE):
        frappe.delete_doc("DocType", OLD_HISTORY_DOCTYPE, ignore_permissions=True, force=True)


def execute():
    _ensure_roles()
    _copy_cleanup_history()
    _remove_old_cleanup_log_doctype()
    frappe.clear_cache()
