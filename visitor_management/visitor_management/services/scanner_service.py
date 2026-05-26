import frappe
from frappe import _

from visitor_management.visitor_management.services.qr_service import parse_visitor_qr
from visitor_management.visitor_management.services.visitor_service import check_in, check_out
from visitor_management.visitor_management.utils.response_utils import error_response


def get_visitor_by_qr_data(qr_data):
    """Resolve visitor doc from QR payload while preserving legacy payload support."""
    visitor_id = parse_visitor_qr(qr_data)
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))
    return frappe.get_doc("Visitor", visitor_id)


def scan_visitor_qr_action(qr_data, action, gate=None, device_id=None):
    visitor = get_visitor_by_qr_data(qr_data)
    normalized_action = (action or "").strip().lower()

    if normalized_action == "checkin":
        return check_in(visitor, gate=gate, device_id=device_id)
    if normalized_action == "checkout":
        return check_out(visitor, gate=gate, device_id=device_id)

    return error_response(_("Aksi tidak dikenali: {0}").format(action))


def build_visitor_scan_response(visitor):
    return {
        "name": visitor.name,
        "visitor_name": visitor.visitor_name,
        "visitor_company": visitor.visitor_company or "-",
        "visitor_phone": visitor.visitor_phone,
        "host_employee_name": visitor.host_employee_name,
        "department": visitor.department or "-",
        "visit_purpose": visitor.visit_purpose,
        "status": visitor.status,
        "check_in_time": str(visitor.check_in_time) if visitor.check_in_time else None,
        "check_out_time": str(visitor.check_out_time) if visitor.check_out_time else None,
        "id_type": visitor.id_type,
        "id_number": visitor.id_number,
        "qr_code_image": visitor.qr_code_image,
    }
