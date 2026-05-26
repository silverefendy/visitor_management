"""v1 approval endpoints.

These wrappers preserve behavior while providing a stable, versioned import path.
"""

import frappe

from visitor_management.visitor_management.api import approval_api


@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
    return approval_api.approve_visitor(visitor_id)


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
    return approval_api.reject_visitor(visitor_id, reason)


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
    return approval_api.complete_visit(visitor_id)


__all__ = ["approve_visitor", "complete_visit", "reject_visitor"]
