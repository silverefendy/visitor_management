import frappe
from visitor_management.visitor_management.permissions.gate_permissions import (
    ensure_gate_access,
)
from visitor_management.visitor_management.services.scanner_service import scan_visitor_qr_action


@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action, gate=None, device_id=None):
    try:
        ensure_gate_access()
        return scan_visitor_qr_action(qr_data, action, gate=gate, device_id=device_id)
    except frappe.ValidationError:
        raise
