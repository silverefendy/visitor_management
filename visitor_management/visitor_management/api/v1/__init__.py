"""Versioned API namespace for visitor_management."""

from .approval import approve_visitor, complete_visit, reject_visitor
from .auth import get_csrf_token
from .checkin import (
    get_employee_by_qr,
    scan_employee_entry_action,
    scan_qr_action,
)
from .visitor import (
    employee_approval_data,
    employee_pending_approvals,
    get_dashboard_data,
    get_visitor_by_qr,
)

__all__ = [
    "approve_visitor",
    "complete_visit",
    "employee_approval_data",
    "employee_pending_approvals",
    "get_csrf_token",
    "get_dashboard_data",
    "get_employee_by_qr",
    "get_visitor_by_qr",
    "reject_visitor",
    "scan_employee_entry_action",
    "scan_qr_action",
]
