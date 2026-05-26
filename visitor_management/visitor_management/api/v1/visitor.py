"""v1 visitor dashboard and approval-list endpoints."""

import frappe

from visitor_management.visitor_management.api import visitor_api
from visitor_management.visitor_management.api.legacy_api import (
    employee_approval_data as _employee_approval_data,
    employee_pending_approvals as _employee_pending_approvals,
    get_dashboard_data as _get_dashboard_data,
)


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
    return visitor_api.get_visitor_by_qr(qr_data)


@frappe.whitelist(allow_guest=False)
def get_dashboard_data():
    return _get_dashboard_data()


@frappe.whitelist(allow_guest=False)
def employee_pending_approvals():
    return _employee_pending_approvals()


@frappe.whitelist(allow_guest=False)
def employee_approval_data():
    return _employee_approval_data()


__all__ = [
    "employee_approval_data",
    "employee_pending_approvals",
    "get_dashboard_data",
    "get_visitor_by_qr",
]
