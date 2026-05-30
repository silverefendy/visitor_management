"""Repair Frappe core Notification Settings metadata for v16 migrations.

Older benches can carry stale Notification Settings customizations from previous
Frappe versions. During migrate, Frappe rebuilds notification cache and expects
its own Notification Settings DocType to expose the standard
``subscribed_documents`` child table. If stale Custom Field / Property Setter
rows shadow or remove that field, migration fails with:

    AttributeError: 'NotificationSettings' object has no attribute
    'enabled' or 'subscribed_documents'

This patch does not create or customize Visitor Management notification records.
It only removes legacy customizations that target Frappe's core Notification
Settings internals and reloads the core DocTypes from the installed Frappe app.
"""

from __future__ import annotations

import frappe

CORE_NOTIFICATION_DOCTYPES = (
    ("desk", "doctype", "notification_settings"),
    ("desk", "doctype", "notification_settings_link"),
    ("desk", "doctype", "notification_subscribed_document"),
)

CORE_NOTIFICATION_FIELDS = {
    "enabled",
    "subscribed_documents",
    "enable_email_notifications",
    "enable_email_mention",
    "enable_email_assignment",
    "enable_email_threads_on_assigned_document",
    "enable_email_share",
    "enable_email_event_reminders",
    "user",
    "seen",
    # v15/older stale names that must not shadow v16 metadata
    "enable_desktop_notifications",
    "enabled_notifications",
}


def _delete_legacy_custom_fields():
    if not frappe.db.table_exists("Custom Field"):
        return

    for fieldname in CORE_NOTIFICATION_FIELDS:
        for name in frappe.get_all(
            "Custom Field",
            filters={"dt": "Notification Settings", "fieldname": fieldname},
            pluck="name",
        ):
            frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def _delete_legacy_property_setters():
    if not frappe.db.table_exists("Property Setter"):
        return

    filters = {
        "doc_type": "Notification Settings",
        "field_name": ["in", list(CORE_NOTIFICATION_FIELDS)],
    }
    for name in frappe.get_all("Property Setter", filters=filters, pluck="name"):
        frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)


def _reload_core_notification_doctypes():
    for module, document_type, doctype_name in CORE_NOTIFICATION_DOCTYPES:
        try:
            frappe.reload_doc(module, document_type, doctype_name, force=True)
        except Exception:
            # Some benches may not have every child doctype in the same branch.
            # Continue with the remaining reloads and let the final validation
            # decide whether the repair succeeded.
            frappe.log_error(
                message=frappe.get_traceback(),
                title="VMS Notification Settings Reload Warning",
            )


def _ensure_core_fallback_fields():
    if not frappe.db.table_exists("DocField"):
        return

    fallback_fields = (
        {
            "fieldname": "enabled",
            "fieldtype": "Check",
            "label": "Enable System Notification",
            "default": "1",
            "idx": 1,
        },
        {
            "fieldname": "subscribed_documents",
            "fieldtype": "Table MultiSelect",
            "label": "Open Documents",
            "options": "Notification Subscribed Document",
            "idx": 2,
        },
    )
    for field in fallback_fields:
        if frappe.db.exists("DocField", {"parent": "Notification Settings", "fieldname": field["fieldname"]}):
            continue
        docfield = frappe.get_doc(
            {
                "doctype": "DocField",
                "parent": "Notification Settings",
                "parentfield": "fields",
                "parenttype": "DocType",
                **field,
            }
        )
        docfield.insert(ignore_permissions=True)


def execute():
    _delete_legacy_custom_fields()
    _delete_legacy_property_setters()
    _reload_core_notification_doctypes()
    _ensure_core_fallback_fields()
    frappe.clear_cache(doctype="Notification Settings")
