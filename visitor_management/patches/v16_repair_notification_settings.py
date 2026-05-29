"""Repair Frappe core Notification Settings metadata for v16 migrations.

Older benches can carry stale Notification Settings customizations from previous
Frappe versions. During migrate, Frappe rebuilds notification cache and expects
its own Notification Settings DocType to expose the standard
``subscribed_documents`` child table. If stale Custom Field / Property Setter
rows shadow or remove that field, migration fails with:

    AttributeError: 'NotificationSettings' object has no attribute
    'subscribed_documents'

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
    "enable_email_notifications",
    "enable_desktop_notifications",
    "enabled_notifications",
    "subscribed_documents",
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


def _ensure_subscribed_documents_field():
    if not frappe.db.table_exists("DocField"):
        return

    exists = frappe.db.exists(
        "DocField",
        {
            "parent": "Notification Settings",
            "fieldname": "subscribed_documents",
        },
    )
    if exists:
        return

    # Last-resort compatibility fallback for benches whose installed Frappe app
    # is missing the DocField row during migrate. The field mirrors Frappe's
    # standard child table so NotificationSettings documents hydrate safely.
    docfield = frappe.get_doc(
        {
            "doctype": "DocField",
            "parent": "Notification Settings",
            "parentfield": "fields",
            "parenttype": "DocType",
            "fieldname": "subscribed_documents",
            "fieldtype": "Table",
            "label": "Subscribed Documents",
            "options": "Notification Subscribed Document",
            "idx": 99,
        }
    )
    docfield.insert(ignore_permissions=True)


def execute():
    _delete_legacy_custom_fields()
    _delete_legacy_property_setters()
    _reload_core_notification_doctypes()
    _ensure_subscribed_documents_field()
    frappe.clear_cache(doctype="Notification Settings")
