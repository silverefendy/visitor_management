import frappe
from frappe import _
from frappe.utils import now_datetime
from visitor_management.visitor_management.services.log_service import create_visitor_log
from visitor_management.visitor_management.services.gate_service import get_gate_by_device

ACTIVE_STATUSES = ["Awaiting Approval", "Approved", "Checked In", "Completed"]


def get_active_visitor_logs(visitor_id):
    return frappe.get_all(
        "Visitor Log",
        filters={"visitor": visitor_id, "is_active": 1},
        pluck="name",
        order_by="creation asc",
    )


def is_visitor_inside(visitor_id):
    return bool(get_active_visitor_logs(visitor_id))


def validate_blacklist(visitor, method=None):
    if not frappe.db.exists("DocType", "Visitor Blacklist"):
        return
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
    if visitor.status not in ["Registered", "Checked Out", "Rejected", "Cancelled"]:
        frappe.throw(_("Tidak bisa check-in. Status: {0}").format(visitor.status))
    if is_visitor_inside(visitor.name):
        frappe.throw(_("Visitor masih tercatat berada di dalam area"))

    validate_blacklist(visitor)
    validate_duplicate_active(visitor)
    gate_name = get_gate_by_device(device_id=device_id, gate=gate)

    visitor.status = "Awaiting Approval"
    visitor.check_in_time = now_datetime()
    visitor.check_out_time = None
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
    return {"status": "success", "message": _("Check-in berhasil. Menunggu approval.")}


def check_out(visitor, gate=None, device_id=None):
    if visitor.status != "Completed":
        frappe.throw(_("Status belum Completed. Status: {0}").format(visitor.status))

    active_logs = get_active_visitor_logs(visitor.name)
    gate_name = get_gate_by_device(device_id=device_id, gate=gate)
    visitor.status = "Checked Out"
    visitor.check_out_time = now_datetime()
    visitor.save(ignore_permissions=True)

    for log_name in active_logs:
        frappe.db.set_value("Visitor Log", log_name, "is_active", 0, update_modified=False)

    remarks = "Visitor check-out di security"
    if not active_logs:
        remarks = "Visitor check-out di security (log aktif tidak ditemukan; status Completed dipakai sebagai dasar checkout)"

    create_visitor_log(
        visitor,
        "Check Out",
        remarks,
        gate=gate_name,
        status="OUT",
        check_out_time=visitor.check_out_time,
        is_active=0,
    )
    return {"status": "success", "message": _("Check-out berhasil.")}

