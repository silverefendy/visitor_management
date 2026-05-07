import frappe
from frappe.utils import now_datetime, add_hours


def auto_checkout_stale_visitors():
    cutoff = add_hours(now_datetime(), -12)
    rows = frappe.get_all(
        "Visitor",
        filters={"status": ["in", ["Approved", "Completed"]], "check_in_time": ["<", cutoff]},
        fields=["name"],
        limit_page_length=200,
    )
    for row in rows:
        try:
            visitor = frappe.get_doc("Visitor", row.name)
            if visitor.status == "Completed":
                visitor.do_checkout()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Auto Checkout Visitor Error")

