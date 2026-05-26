"""Whitelisted API exports for backward-compatible import paths."""

from . import approval_api, gate_api, qr_api, v1, visitor_api
from .approval_api import approve_visitor, complete_visit, reject_visitor
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
    "approve_visitor",
    "bulk_employee_entry_action",
    "complete_visit",
    "create_employee_entry",
    "employee_approval_data",
    "employee_entry_action",
    "employee_pending_approvals",
    "gate_api",
    "get_csrf_token",
    "get_dashboard_data",
    "get_employee_by_barcode",
    "get_employee_entry_data",
    "get_my_employee_barcode",
    "get_visitor_by_qr",
    "list_active_gates",
    "qr_api",
    "reject_visitor",
    "scan_employee_entry_barcode",
    "scan_qr_action",
    "v1",
    "visitor_api",
]
