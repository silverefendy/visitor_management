import frappe

from visitor_management.visitor_management.services.visitor_service import (
    STATUS_APPROVED,
    STATUS_COMPLETED,
)
from visitor_management.visitor_management.utils.datetime_utils import hours_ago


def auto_checkout_stale_visitors(hours=12):
    cutoff = hours_ago(hours)
    rows = frappe.get_all(
        "Visitor",
        filters={
            "status": ["in", [STATUS_APPROVED, STATUS_COMPLETED]],
            "check_in_time": ["<", cutoff],
        },
        pluck="name",
        limit_page_length=200,
    )
    for name in rows:
        try:
            visitor = frappe.get_doc("Visitor", name)
            if visitor.status == STATUS_APPROVED:
                visitor.end_visit()
            if visitor.status == STATUS_COMPLETED:
                visitor.do_checkout()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Auto Checkout Visitor Error")
