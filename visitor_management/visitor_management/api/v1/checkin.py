"""v1 check-in/check-out and QR endpoints."""

from visitor_management.visitor_management import api as legacy_api

scan_qr_action = legacy_api.scan_qr_action
get_employee_by_qr = legacy_api.get_employee_by_qr
scan_employee_entry_action = legacy_api.scan_employee_entry_action
