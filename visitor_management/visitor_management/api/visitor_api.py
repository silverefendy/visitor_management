import frappe

from visitor_management.visitor_management.utils.qr_utils import parse_qr_payload


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
	payload = parse_qr_payload(qr_data)
	visitor_id = payload.get("visitor_id") or payload.get("value")
	if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
		return {"error": "Visitor tidak ditemukan"}
	return frappe.db.get_value(
		"Visitor",
		visitor_id,
		[
			"name",
			"visitor_name",
			"visitor_company",
			"visitor_phone",
			"host_employee_name",
			"department",
			"visit_purpose",
			"status",
			"check_in_time",
			"check_out_time",
			"id_type",
			"id_number",
			"qr_code_image",
		],
		as_dict=True,
	)
