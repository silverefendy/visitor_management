import frappe

from visitor_management.visitor_management.services.approval_service import (
    approve_visitor as approve_visitor_service,
    complete_visit as complete_visit_service,
    reject_visitor as reject_visitor_service,
)


@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
    return approve_visitor_service(visitor_id)


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
    return reject_visitor_service(visitor_id, reason)


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
    return complete_visit_service(visitor_id)
