import frappe

from visitor_management.visitor_management.utils.datetime_utils import hours_ago


def auto_checkout_stale_visitors(hours=12):
	cutoff = hours_ago(hours)
	rows = frappe.get_all(
		"Visitor",
		filters={"status": ["in", ["Approved", "Completed"]], "check_in_time": ["<", cutoff]},
		pluck="name",
		limit_page_length=200,
	)
	for name in rows:
		try:
			visitor = frappe.get_doc("Visitor", name)
			if visitor.status == "Completed":
				visitor.do_checkout()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Auto Checkout Visitor Error")
