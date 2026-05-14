import frappe
from frappe.utils import now_datetime


def create_visitor_log(
	visitor,
	action,
	remarks="",
	gate=None,
	status=None,
	check_in_time=None,
	check_out_time=None,
	is_active=None,
):
	log = frappe.get_doc(
		{
			"doctype": "Visitor Log",
			"visitor": visitor.name if hasattr(visitor, "name") else visitor,
			"action": action,
			"action_time": now_datetime(),
			"action_by": frappe.session.user,
			"remarks": remarks,
			"status": status,
			"check_in_time": check_in_time,
			"check_out_time": check_out_time,
			"is_active": is_active,
			"gate": gate,
		}
	)
	log.insert(ignore_permissions=True)
	return log
