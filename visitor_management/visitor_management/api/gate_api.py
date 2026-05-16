# gate_api.py — Gate / Satpam endpoints
# Digunakan oleh: Security User via HTTP dan Mobile Android
import frappe
from frappe import _
from frappe.utils import today
from visitor_management.visitor_management.permissions.gate_permissions import ensure_gate_access
from visitor_management.visitor_management.services.qr_service import parse_visitor_qr
from visitor_management.visitor_management.services.visitor_service import check_in, check_out


@frappe.whitelist(allow_guest=False)
def list_active_gates():
    """Daftar gate yang aktif."""
    ensure_gate_access()
    return frappe.get_all(
        "Gate",
        filters={"is_active": 1},
        fields=["name", "gate_name", "device_id"],
    )


@frappe.whitelist(allow_guest=False)
def gate_scan_qr(qr_data, action, gate=None, device_id=None):
    """
    Scan QR visitor di gate untuk check-in atau check-out.
    Dipakai oleh satpam via HTTP maupun Mobile Android.

    action: 'checkin' | 'checkout'
    gate: nama gate (opsional, bisa diganti device_id)
    device_id: ID perangkat scanner (opsional)
    """
    ensure_gate_access()
    visitor_id = parse_visitor_qr(qr_data)
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))
    visitor = frappe.get_doc("Visitor", visitor_id)
    if action == "checkin":
        return check_in(visitor, gate=gate, device_id=device_id)
    if action == "checkout":
        return check_out(visitor, gate=gate, device_id=device_id)
    frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def get_visitors_inside():
    """
    Daftar visitor yang saat ini berada di dalam area (status Checked In / Approved).
    Untuk monitor satpam di gate.
    """
    ensure_gate_access()
    return frappe.get_all(
        "Visitor",
        filters={"status": ["in", ["Checked In", "Approved", "Awaiting Approval"]]},
        fields=[
            "name", "visitor_name", "visitor_company", "visitor_phone",
            "host_employee_name", "department", "visit_purpose",
            "status", "check_in_time", "id_type", "id_number", "qr_code_image",
        ],
        order_by="check_in_time asc",
    )


@frappe.whitelist(allow_guest=False)
def get_pending_visitors():
    """
    Daftar visitor yang menunggu approval (Awaiting Approval).
    Untuk informasi satpam agar bisa konfirmasi ke tamu.
    """
    ensure_gate_access()
    return frappe.get_all(
        "Visitor",
        filters={"status": "Awaiting Approval"},
        fields=[
            "name", "visitor_name", "visitor_company",
            "host_employee_name", "department", "visit_purpose",
            "check_in_time", "id_type", "id_number",
        ],
        order_by="check_in_time asc",
    )


@frappe.whitelist(allow_guest=False)
def get_gate_dashboard():
    """
    Ringkasan data untuk dashboard gate/satpam.
    Ringan, hanya statistik — cocok untuk polling dari Mobile Android.
    """
    ensure_gate_access()
    activity_filters = [["modified", ">=", today()]]

    inside = frappe.db.count("Visitor", filters={"status": ["in", ["Checked In", "Approved"]]})
    waiting = frappe.db.count("Visitor", filters={"status": "Awaiting Approval"})
    completed_today = frappe.db.count(
        "Visitor", filters=activity_filters + [["status", "=", "Completed"]]
    )
    checked_out_today = frappe.db.count(
        "Visitor", filters=activity_filters + [["status", "=", "Checked Out"]]
    )

    recent_activity = frappe.get_all(
        "Visitor",
        filters=activity_filters,
        fields=["name", "visitor_name", "status", "check_in_time", "check_out_time"],
        order_by="modified desc",
        limit_page_length=10,
    )

    return {
        "stats": {
            "inside":          inside,
            "waiting_approval": waiting,
            "completed_today": completed_today,
            "checked_out_today": checked_out_today,
        },
        "recent_activity": recent_activity,
    }


@frappe.whitelist(allow_guest=False)
def get_visitor_detail_by_qr(qr_data):
    """
    Ambil detail visitor dari QR scan tanpa melakukan aksi apapun.
    Untuk preview info tamu sebelum satpam confirm checkin/checkout.
    """
    ensure_gate_access()
    visitor_id = parse_visitor_qr(qr_data)
    if not frappe.db.exists("Visitor", visitor_id):
        return {"error": _("Visitor tidak ditemukan")}
    return frappe.db.get_value(
        "Visitor", visitor_id,
        ["name", "visitor_name", "visitor_company", "visitor_phone",
         "host_employee_name", "department", "visit_purpose",
         "status", "check_in_time", "check_out_time",
         "id_type", "id_number", "qr_code_image"],
        as_dict=True,
    )
