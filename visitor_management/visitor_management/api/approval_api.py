# approval_api.py — Approve, Reject, Complete Visitor & Employee data
import frappe
from frappe import _
from visitor_management.visitor_management.permissions.approval_permissions import ensure_can_approve
from visitor_management.visitor_management.permissions.visitor_permissions import can_manage_visitor


# =============================================================================
# HELPER FUNCTIONS (private)
# =============================================================================

def _get_employee_for_user(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _get_visitor(visitor_id):
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))
    visitor = frappe.get_doc("Visitor", visitor_id)
    if not can_manage_visitor(visitor):
        raise frappe.PermissionError("Tidak ada akses")
    return visitor


# =============================================================================
# VISITOR APPROVAL ENDPOINTS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
    """Approve kunjungan tamu."""
    visitor = _get_visitor(visitor_id)
    ensure_can_approve(visitor)
    return visitor.approve_visit()


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
    """Tolak kunjungan tamu."""
    visitor = _get_visitor(visitor_id)
    ensure_can_approve(visitor)
    return visitor.reject_visit(reason)


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
    """Tandai kunjungan selesai (siap checkout)."""
    visitor = _get_visitor(visitor_id)
    return visitor.end_visit()


# =============================================================================
# EMPLOYEE APPROVAL DATA (untuk halaman approval manager/karyawan)
# =============================================================================

@frappe.whitelist(allow_guest=False)
def employee_pending_approvals():
    """Daftar visitor yang menunggu approval dari karyawan yang login."""
    user     = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return []
    return frappe.get_all(
        "Visitor",
        filters={"host_employee": employee, "status": "Awaiting Approval"},
        fields=["name", "visitor_name", "visitor_company", "visit_purpose",
                "check_in_time", "id_type", "id_number"],
        order_by="check_in_time asc",
    )


@frappe.whitelist(allow_guest=False)
def employee_approval_data():
    """
    Data approval untuk halaman /vms-approval.
    Manager melihat semua visitor. Karyawan hanya melihat visitor yang ditujukan ke dirinya.
    """
    user       = frappe.session.user
    roles      = frappe.get_roles(user)
    is_manager = "System Manager" in roles or "Visitor Manager" in roles
    employee   = _get_employee_for_user(user)

    if not is_manager and not employee:
        return {
            "user": user, "employee": None, "pending": [], "active": [],
            "warning": "User login belum terhubung ke Employee.",
        }

    base_filters = {} if is_manager else {"host_employee": employee}
    fields = [
        "name", "visitor_name", "visitor_company", "visitor_phone",
        "visit_purpose", "host_employee_name", "department",
        "status", "check_in_time", "approved_at", "id_type", "id_number",
    ]
    return {
        "user": user, "employee": employee, "is_manager": is_manager,
        "pending": frappe.get_all("Visitor", filters={**base_filters, "status": "Awaiting Approval"}, fields=fields, order_by="check_in_time asc"),
        "active":  frappe.get_all("Visitor", filters={**base_filters, "status": "Approved"}, fields=fields, order_by="approved_at asc, check_in_time asc"),
    }
