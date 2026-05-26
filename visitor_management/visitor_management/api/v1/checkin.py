"""v1 check-in/check-out and QR endpoints.

Thin wrappers only: business logic stays in existing APIs/services.
"""

import frappe

from visitor_management.visitor_management.api import qr_api
from visitor_management.visitor_management.api.legacy_api import (
    get_employee_by_barcode as _get_employee_by_barcode,
    scan_employee_entry_barcode as _scan_employee_entry_barcode,
)


@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action, gate=None, device_id=None):
    return qr_api.scan_qr_action(
        qr_data=qr_data,
        action=action,
        gate=gate,
        device_id=device_id,
    )


@frappe.whitelist(allow_guest=False)
def get_employee_by_qr(qr_data):
    return _get_employee_by_barcode(qr_data)


@frappe.whitelist(allow_guest=False)
def scan_employee_entry_action(qr_data, action, purpose="Security scan"):
    return _scan_employee_entry_barcode(qr_data=qr_data, action=action)


__all__ = [
    "get_employee_by_qr",
    "scan_employee_entry_action",
    "scan_qr_action",
]
