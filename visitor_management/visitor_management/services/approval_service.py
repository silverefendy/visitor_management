import frappe
from frappe import _
from frappe.utils import now_datetime

APPROVAL_STEPS = [
    ("Supervisor", "Supervisor Approval"),
    ("HR Manager", "Manager Approval"),
    ("Visitor Security", "Security Approval"),
]


def next_stage(current_status):
    mapping = {
        "Draft": "Supervisor Approval",
        "Supervisor Approval": "Manager Approval",
        "Manager Approval": "Security Approval",
        "Security Approval": "Approved",
    }
    return mapping.get(current_status)


def approve_employee_entry(doc):
	status = doc.status or "Draft"
	target = next_stage(status)
	if not target:
		frappe.throw(_("Status tidak bisa di-approve: {0}").format(status))
	doc.status = target
	if target == "Approved":
		doc.approved_by = frappe.session.user
		doc.approved_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"status": "success", "message": _("Status berubah ke {0}").format(target)}


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
