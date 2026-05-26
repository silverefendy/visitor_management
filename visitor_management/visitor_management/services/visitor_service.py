import frappe
from frappe import _
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.gate_service import (
    get_gate_by_device,
)
from visitor_management.visitor_management.services.log_service import (
    create_visitor_log,
)
from visitor_management.visitor_management.permissions.visitor_permissions import (
    can_manage_visitor,
)
from visitor_management.visitor_management.services.qr_service import (
    generate_and_attach_visitor_qr,
    parse_visitor_qr,
)

STATUS_REGISTERED = "Registered"
STATUS_CHECKED_IN = "Checked In"
STATUS_AWAITING_APPROVAL = "Awaiting Approval"
STATUS_APPROVED = "Approved"
STATUS_COMPLETED = "Completed"
STATUS_CHECKED_OUT = "Checked Out"
STATUS_REJECTED = "Rejected"
STATUS_CANCELLED = "Cancelled"

VISITOR_STATUSES = [
    STATUS_REGISTERED,
    STATUS_CHECKED_IN,
    STATUS_AWAITING_APPROVAL,
    STATUS_APPROVED,
    STATUS_COMPLETED,
    STATUS_CHECKED_OUT,
    STATUS_REJECTED,
    STATUS_CANCELLED,
]

ACTIVE_STATUSES = [
    STATUS_CHECKED_IN,
    STATUS_AWAITING_APPROVAL,
    STATUS_APPROVED,
    STATUS_COMPLETED,
]
DASHBOARD_ACTIVE_STATUSES = [
    STATUS_CHECKED_IN,
    STATUS_AWAITING_APPROVAL,
    STATUS_APPROVED,
]

ALLOWED_TRANSITIONS = {
    STATUS_REGISTERED: {STATUS_AWAITING_APPROVAL},
    STATUS_CHECKED_IN: {STATUS_AWAITING_APPROVAL},
    STATUS_AWAITING_APPROVAL: {STATUS_APPROVED, STATUS_REJECTED},
    STATUS_APPROVED: {STATUS_COMPLETED},
    STATUS_COMPLETED: {STATUS_CHECKED_OUT},
    STATUS_CHECKED_OUT: {STATUS_AWAITING_APPROVAL},
    STATUS_REJECTED: {STATUS_AWAITING_APPROVAL},
    STATUS_CANCELLED: {STATUS_AWAITING_APPROVAL},
}


def validate_visitor_transition(current_status, target_status):
    if target_status not in VISITOR_STATUSES:
        frappe.throw(_("Status visitor tidak valid: {0}").format(target_status))

    allowed_targets = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        frappe.throw(
            _("Transisi visitor tidak valid: {0} ke {1}").format(
                current_status, target_status
            )
        )


def transition_visitor(visitor, target_status, field_updates=None):
    validate_visitor_transition(visitor.status, target_status)
    visitor.status = target_status
    for fieldname, value in (field_updates or {}).items():
        setattr(visitor, fieldname, value)
    visitor.save(ignore_permissions=True)
    return visitor


class VisitorService:
    def __init__(self, doc):
        self.doc = doc

    def validate(self):
        if self.doc.host_employee:
            emp_status = frappe.db.get_value(
                "Employee", self.doc.host_employee, "status"
            )
            if emp_status != "Active":
                frappe.throw(
                    _("Karyawan {0} tidak aktif.").format(self.doc.host_employee)
                )

    def generate_qr_code(self):
        generate_and_attach_visitor_qr(self.doc)

    def approve_visit(self):
        transition_visitor(
            self.doc,
            STATUS_APPROVED,
            {
                "approved_by": frappe.session.user,
                "approved_at": now_datetime(),
            },
        )

        self.create_visitor_log(
            "Approved", "Disetujui oleh {0}".format(frappe.session.user)
        )
        frappe.db.commit()
        return {"status": "success", "message": "Kunjungan disetujui."}

    def reject_visit(self, reason=""):
        transition_visitor(
            self.doc,
            STATUS_REJECTED,
            {
                "rejected_reason": reason,
                "approved_by": frappe.session.user,
                "approved_at": now_datetime(),
            },
        )

        self.create_visitor_log("Rejected", "Ditolak: {0}".format(reason))
        frappe.db.commit()
        return {"status": "success", "message": "Kunjungan ditolak."}

    def end_visit(self):
        transition_visitor(self.doc, STATUS_COMPLETED)

        self.create_visitor_log("Completed", "Kunjungan selesai")
        frappe.db.commit()
        return {
            "status": "success",
            "message": "Kunjungan selesai. Tamu dapat check-out.",
        }

    def create_visitor_log(self, action, remarks=""):
        try:
            create_visitor_log(self.doc, action, remarks=remarks)
        except Exception:
            frappe.log_error(title="VMS Log Error", message=frappe.get_traceback())


def get_visitor_info(visitor_id):
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))

    visitor = frappe.get_doc("Visitor", visitor_id)
    if not can_manage_visitor(visitor):
        frappe.throw(
            _("Anda tidak memiliki akses untuk visitor ini"),
            frappe.PermissionError,
        )

    return {
        "name": visitor.name,
        "visitor_name": visitor.visitor_name,
        "status": visitor.status,
        "qr_code_image": visitor.qr_code_image,
    }


def get_visitor_id_from_qr(qr_data):
    return parse_visitor_qr(qr_data)


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
    dup = frappe.db.exists(
        "Visitor",
        {
            "id_number": visitor.id_number,
            "status": ["in", ACTIVE_STATUSES],
            "name": ["!=", visitor.name],
        },
    )
    if dup:
        frappe.throw(_("Visitor dengan ID yang sama masih aktif: {0}").format(dup))


def check_in(visitor, gate=None, device_id=None):
    if is_visitor_inside(visitor.name):
        frappe.throw(_("Visitor masih tercatat berada di dalam area"))

    validate_visitor_transition(visitor.status, STATUS_AWAITING_APPROVAL)
    validate_blacklist(visitor)
    validate_duplicate_active(visitor)
    gate_name = get_gate_by_device(device_id=device_id, gate=gate)
    check_in_time = now_datetime()

    transition_visitor(
        visitor,
        STATUS_AWAITING_APPROVAL,
        {
            "check_in_time": check_in_time,
            "check_out_time": None,
        },
    )

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

    return {"status": "success", "message": _("Check-in berhasil. Menunggu approval.")}


def check_out(visitor, gate=None, device_id=None):
    validate_visitor_transition(visitor.status, STATUS_CHECKED_OUT)
    active_logs = get_active_visitor_logs(visitor.name)
    gate_name = get_gate_by_device(device_id=device_id, gate=gate)
    check_out_time = now_datetime()

    transition_visitor(
        visitor,
        STATUS_CHECKED_OUT,
        {
            "check_out_time": check_out_time,
        },
    )

    for log_name in active_logs:
        frappe.db.set_value(
            "Visitor Log", log_name, "is_active", 0, update_modified=False
        )

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

    frappe.db.commit()

    return {"status": "success", "message": _("Check-out berhasil.")}
