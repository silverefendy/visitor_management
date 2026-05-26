"""Whitelisted API exports for backward-compatible import paths."""

from . import approval_api, gate_api, qr_api, visitor_api
from .approval_api import complete_visit, approve_visitor, reject_visitor
from .gate_api import list_active_gates
from .legacy_api import (
    bulk_employee_entry_action,
    create_employee_entry,
    employee_approval_data,
    employee_entry_action,
    employee_pending_approvals,
    get_csrf_token,
    get_dashboard_data,
    get_employee_by_barcode,
    get_employee_entry_data,
    get_my_employee_barcode,
    scan_employee_entry_barcode,
)
from .qr_api import scan_qr_action
from .visitor_api import get_visitor_by_qr

__all__ = [
    "approval_api",
    "gate_api",
    "qr_api",
    "visitor_api",
    "approve_visitor",
    "reject_visitor",
    "complete_visit",
    "scan_qr_action",
    "get_visitor_by_qr",
    "list_active_gates",
    "get_csrf_token",
    "get_dashboard_data",
    "get_employee_by_barcode",
    "get_my_employee_barcode",
    "scan_employee_entry_barcode",
    "create_employee_entry",
    "employee_entry_action",
    "bulk_employee_entry_action",
    "employee_pending_approvals",
    "employee_approval_data",
    "get_employee_entry_data",
]
