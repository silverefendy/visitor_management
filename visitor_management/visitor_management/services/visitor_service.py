import frappe
from frappe import _
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.gate_service import (
    get_gate_by_device,
)
from visitor_management.visitor_management.services.log_service import (
    create_visitor_log,
)
from visitor_management.visitor_management.services.qr_service import (
    generate_and_attach_visitor_qr,
    parse_visitor_qr,
)


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
        if self.doc.status != "Awaiting Approval":
            frappe.throw(_("Status bukan Awaiting Approval."))

        self.doc.status = "Approved"
        self.doc.approved_by = frappe.session.user
        self.doc.approved_at = now_datetime()
        self.doc.save(ignore_permissions=True)

        self.create_visitor_log(
            "Approved", "Disetujui oleh {0}".format(frappe.session.user)
        )
        frappe.db.commit()
        return {"status": "success", "message": "Kunjungan disetujui."}

    def reject_visit(self, reason=""):
        if self.doc.status != "Awaiting Approval":
            frappe.throw(_("Status bukan Awaiting Approval."))

        self.doc.status = "Rejected"
        self.doc.rejected_reason = reason
        self.doc.approved_by = frappe.session.user
        self.doc.approved_at = now_datetime()
        self.doc.save(ignore_permissions=True)

        self.create_visitor_log("Rejected", "Ditolak: {0}".format(reason))
        frappe.db.commit()
        return {"status": "success", "message": "Kunjungan ditolak."}

    def end_visit(self):
        if self.doc.status not in ["Approved", "Checked In"]:
            frappe.throw(_("Kunjungan belum disetujui."))

        self.doc.status = "Completed"
        self.doc.save(ignore_permissions=True)

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
    visitor = frappe.get_doc("Visitor", visitor_id)
    return {
        "name": visitor.name,
        "visitor_name": visitor.visitor_name,
        "status": visitor.status,
        "qr_code_image": visitor.qr_code_image,
    }


def get_visitor_id_from_qr(qr_data):
    return parse_visitor_qr(qr_data)


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

    frappe.db.commit()

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
