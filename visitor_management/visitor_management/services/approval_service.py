import frappe

from visitor_management.visitor_management.permissions.approval_permissions import (
    ensure_can_approve,
)
from visitor_management.visitor_management.permissions.visitor_permissions import (
    can_manage_visitor,
)
from visitor_management.visitor_management.services.notification_service import publish


def get_approval_visitor(visitor_id):
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        frappe.throw("Visitor tidak ditemukan")

    visitor = frappe.get_doc("Visitor", visitor_id)
    if not can_manage_visitor(visitor):
        raise frappe.PermissionError("Tidak ada akses")

    return visitor


def approve_visitor(visitor_id):
    visitor = get_approval_visitor(visitor_id)
    ensure_can_approve(visitor)
    result = visitor.approve_visit()
    publish(
        "vms_visitor_approved",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name},
    )
    return result


def reject_visitor(visitor_id, reason=""):
    visitor = get_approval_visitor(visitor_id)
    ensure_can_approve(visitor)
    result = visitor.reject_visit(reason)
    publish(
        "vms_visitor_rejected",
        {
            "visitor": visitor.name,
            "visitor_name": visitor.visitor_name,
            "reason": reason,
        },
    )
    return result


def complete_visit(visitor_id):
    visitor = get_approval_visitor(visitor_id)
    return visitor.end_visit()
