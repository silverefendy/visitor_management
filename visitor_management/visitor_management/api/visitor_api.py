import frappe

from visitor_management.visitor_management.utils.qr_utils import parse_qr_payload
from visitor_management.visitor_management.utils.response_utils import (
    error_response,
    success_response,
)

VISITOR_QR_FIELDS = [
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
]


def _get_visitor_id(payload):
    return payload.get("visitor_id") or payload.get("value")


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
    payload = parse_qr_payload(qr_data)
    visitor_id = _get_visitor_id(payload)

    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        return error_response("Visitor tidak ditemukan")

    visitor_data = frappe.db.get_value(
        "Visitor",
        visitor_id,
        VISITOR_QR_FIELDS,
        as_dict=True,
    )
    return success_response(
        message="Visitor ditemukan",
        data=visitor_data,
        **visitor_data,
    )
