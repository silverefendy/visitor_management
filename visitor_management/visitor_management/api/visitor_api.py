import frappe

from visitor_management.visitor_management.services.scanner_service import (
    build_visitor_scan_response,
    get_visitor_by_qr_data,
)
from visitor_management.visitor_management.utils.response_utils import error_response, success_response


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
    try:
        visitor = get_visitor_by_qr_data(qr_data)
    except frappe.ValidationError:
        return error_response("Visitor tidak ditemukan")

    visitor_data = build_visitor_scan_response(visitor)
    return success_response(
        message="Visitor ditemukan",
        data=visitor_data,
        **visitor_data,
    )
