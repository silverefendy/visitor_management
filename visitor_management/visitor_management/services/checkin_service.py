import frappe
from frappe import _
from frappe.utils import now_datetime

from visitor_management.visitor_management.permissions.approval_permissions import (
    is_approval_manager,
)


class EmployeeEntryCheckinService:
    def __init__(self, doc):
        self.doc = doc

    def before_insert(self):
        if not self.doc.status:
            self.doc.status = "Pending Approval"
        if not self.doc.check_in_time:
            self.doc.check_in_time = now_datetime()

    def validate(self):
        if self.doc.employee:
            employee = frappe.db.get_value(
                "Employee",
                self.doc.employee,
                ["employee_name", "department", "status"],
                as_dict=True,
            )
            if not employee:
                frappe.throw(_("Employee tidak ditemukan"))
            if employee.status != "Active":
                frappe.throw(_("Employee {0} tidak aktif").format(self.doc.employee))
            self.doc.employee_name = employee.employee_name
            self.doc.department = employee.department

    def ensure_approval_manager(self):
        if not is_approval_manager():
            frappe.throw(
                _("Anda tidak memiliki hak untuk aksi approval"), frappe.PermissionError
            )

    def save_with_commit(self):
        self.doc.save(ignore_permissions=True)
        frappe.db.commit()

    # Backward-compatible aliases for existing call sites.
    def ensure_manager(self):
        self.ensure_approval_manager()

    def save_and_commit(self):
        self.save_with_commit()


class EmployeeEntryApprovalService:
    def __init__(self, doc, checkin_service, log_callback):
        self.doc = doc
        self.checkin_service = checkin_service
        self.log_callback = log_callback

    def approve(self):
        self.checkin_service.ensure_manager()
        if self.doc.status != "Pending Approval":
            frappe.throw(_("Status bukan Pending Approval"))
        self.doc.status = "Approved"
        self.doc.approved_by = frappe.session.user
        self.doc.approved_at = now_datetime()
        self.checkin_service.save_and_commit()
        self.log_callback("Approved", "Pengajuan disetujui")
        return {"status": "success", "message": "Karyawan disetujui masuk."}

    def reject(self, reason=""):
        self.checkin_service.ensure_manager()
        if self.doc.status != "Pending Approval":
            frappe.throw(_("Status bukan Pending Approval"))
        self.doc.status = "Rejected"
        self.doc.rejected_reason = reason
        self.doc.approved_by = frappe.session.user
        self.doc.approved_at = now_datetime()
        self.checkin_service.save_and_commit()
        self.log_callback("Rejected", reason or "Pengajuan ditolak")
        return {"status": "success", "message": "Pengajuan karyawan ditolak."}

    def complete(self):
        self.checkin_service.ensure_manager()
        if self.doc.status != "Approved":
            frappe.throw(_("Status belum Approved"))
        self.doc.status = "Completed"
        self.doc.completed_at = now_datetime()
        self.checkin_service.save_and_commit()
        self.log_callback("Completed", "Kegiatan selesai")
        return {"status": "success", "message": "Kegiatan karyawan selesai."}

    def checkout(self):
        if self.doc.status != "Completed":
            frappe.throw(_("Status belum Completed"))
        self.doc.status = "Checked Out"
        self.doc.check_out_time = now_datetime()
        self.checkin_service.save_and_commit()
        self.log_callback("Checked Out", "Karyawan check-out")
        return {"status": "success", "message": "Karyawan check-out."}
