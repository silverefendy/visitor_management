import frappe
from frappe import _
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.gate_service import get_gate_by_device
from visitor_management.visitor_management.services.log_service import create_visitor_log

ACTIVE_STATUSES = ["Awaiting Approval", "Approved", "Completed"]
VISITOR_WORKFLOW_STATE_FIELD = "workflow_state"

# Status yang diizinkan untuk checkout. Completed berarti aktivitas selesai
# dan visitor siap keluar; Checked Out adalah status final/invalid.
CHECKOUT_ALLOWED_STATUSES = ["Completed"]


def is_visitor_inside(visitor_id):
    return bool(frappe.db.exists("Visitor Log", {"visitor": visitor_id, "is_active": 1}))


def close_active_visitor_logs(visitor_id):
    active_logs = frappe.get_all(
        "Visitor Log",
        filters={"visitor": visitor_id, "is_active": 1},
        pluck="name",
    )
    for log_name in active_logs:
        frappe.db.set_value("Visitor Log", log_name, "is_active", 0, update_modified=False)
    return len(active_logs)


def _sync_visitor_status(visitor, status):
    visitor.status = status
    if visitor.meta and visitor.meta.has_field(VISITOR_WORKFLOW_STATE_FIELD):
        visitor.workflow_state = status


def _visitor_response(visitor, message, next_action=None):
    workflow_state = visitor.get(VISITOR_WORKFLOW_STATE_FIELD) if visitor.meta.has_field(VISITOR_WORKFLOW_STATE_FIELD) else visitor.status
    return {
        "success": True,
        "status": "success",
        "message": message,
        "visitor": visitor.name,
        "visitor_status": visitor.status,
        "workflow_state": workflow_state,
        "next_action": next_action,
    }


def validate_blacklist(visitor, method=None):
    if frappe.db.exists("Visitor Blacklist", {"id_number": visitor.id_number}):
        frappe.throw(_("Visitor ini masuk blacklist"))


def validate_duplicate_active(visitor, method=None):
    dup = frappe.db.exists("Visitor", {
        "id_number": visitor.id_number,
        "status": ["in", ACTIVE_STATUSES],
        "name": ["!=", visitor.name],
    })
    if dup:
        frappe.throw(_("Visitor dengan ID yang sama masih aktif: {0}").format(dup))


def check_in(visitor, gate=None, device_id=None):
    if visitor.status != "Registered":
        frappe.throw(_("Tidak bisa check-in. Status saat ini: {0}. Visitor harus Registered.").format(visitor.status))
    if is_visitor_inside(visitor.name):
        frappe.throw(_("Visitor masih tercatat berada di dalam area"))

    validate_blacklist(visitor)
    validate_duplicate_active(visitor)
    gate_name = get_gate_by_device(device_id=device_id, gate=gate)

    _sync_visitor_status(visitor, "Awaiting Approval")
    visitor.check_in_time = now_datetime()
    visitor.check_out_time = None
    if visitor.meta.has_field("completed_at"):
        visitor.completed_at = None
    visitor.save(ignore_permissions=True)

    create_visitor_log(
        visitor,
        "Check In",
        "Visitor check-in di security",
        gate=gate_name,
        status="IN",
        check_in_time=visitor.check_in_time,
        is_active=1,
    )
    frappe.db.commit()
    return _visitor_response(visitor, _("Check-in berhasil. Menunggu approval."), next_action="WAIT_FOR_APPROVAL")


def check_out(visitor, gate=None, device_id=None):
    """
    Proses checkout visitor.

    Diizinkan dari status:
    - Completed : aktivitas kunjungan selesai dan visitor siap keluar.

    Status Approved berarti visitor masih berada di area dan belum boleh checkout.
    """
    if visitor.status not in CHECKOUT_ALLOWED_STATUSES:
        if visitor.status == "Awaiting Approval":
            frappe.throw(_(
                "Visitor masih menunggu approval dari host. "
                "Minta host untuk approve atau reject terlebih dahulu."
            ))
        if visitor.status == "Approved":
            frappe.throw(_("Tamu masih di area"))
        frappe.throw(_(
            "Tidak bisa check-out. Status saat ini: {0}. "
            "Status yang diizinkan: {1}."
        ).format(visitor.status, ", ".join(CHECKOUT_ALLOWED_STATUSES)))

    gate_name = get_gate_by_device(device_id=device_id, gate=gate)
    _sync_visitor_status(visitor, "Checked Out")
    visitor.check_out_time = now_datetime()
    if visitor.meta.has_field("completed_at"):
        visitor.completed_at = visitor.check_out_time
    visitor.save(ignore_permissions=True)

    close_active_visitor_logs(visitor.name)
    create_visitor_log(
        visitor,
        "Check Out",
        "Visitor check-out di security",
        gate=gate_name,
        status="OUT",
        check_out_time=visitor.check_out_time,
        is_active=0,
    )
    frappe.db.commit()
    return _visitor_response(visitor, _("Check-out visitor berhasil."), next_action="DONE")
