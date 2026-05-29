import frappe
from frappe.utils import add_to_date, now_datetime, today

from visitor_management.visitor_management.services.settings_service import get_visitor_settings


def auto_checkout_stale_visitors():
    if not get_visitor_settings("auto_check_out_end_of_day", 0):
        return

    duration_hours = int(get_visitor_settings("default_visit_duration", 8) or 8)
    cutoff = add_to_date(now_datetime(), hours=-duration_hours)
    rows = frappe.get_all(
        "Visitor",
        filters={"status": ["in", ["Approved", "Checked In", "Completed"]], "check_in_time": ["<", cutoff]},
        fields=["name"],
        limit_page_length=200,
    )
    for row in rows:
        try:
            visitor = frappe.get_doc("Visitor", row.name)
            visitor.do_checkout()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Auto Checkout Visitor Error")


def auto_archive_old_visitors():
    if not get_visitor_settings("auto_archive_old_records", 0):
        return

    retention_days = int(get_visitor_settings("retention_period_days", 365) or 365)
    cutoff = add_to_date(today(), days=-retention_days)
    rows = frappe.get_all(
        "Visitor",
        filters={"status": ["in", ["Checked Out", "Rejected", "Cancelled"]], "modified": ["<", cutoff]},
        fields=["name"],
        limit_page_length=200,
    )
    for row in rows:
        try:
            values = {"status": "Archived"}
            if frappe.get_meta("Visitor").has_field("archived_at"):
                values["archived_at"] = now_datetime()
            if frappe.get_meta("Visitor").has_field("archived_by"):
                values["archived_by"] = "Administrator"
            frappe.db.set_value("Visitor", row.name, values, update_modified=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Auto Archive Visitor Error")
