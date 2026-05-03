import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class EmployeeEntryRequest(Document):
	def before_insert(self):
		if not self.status:
			self.status = "Pending Approval"
		if not self.check_in_time:
			self.check_in_time = now_datetime()

	def validate(self):
		if self.employee:
			employee = frappe.db.get_value(
				"Employee",
				self.employee,
				["employee_name", "department", "status"],
				as_dict=True,
			)
			if not employee:
				frappe.throw(_("Employee tidak ditemukan"))
			if employee.status != "Active":
				frappe.throw(_("Employee {0} tidak aktif").format(self.employee))
			self.employee_name = employee.employee_name
			self.department = employee.department

	@frappe.whitelist()
	def approve(self):
		if self.status != "Pending Approval":
			frappe.throw(_("Status bukan Pending Approval"))
		self.status = "Approved"
		self.approved_by = frappe.session.user
		self.approved_at = now_datetime()
		self.save(ignore_permissions=True)
		return {"status": "success", "message": "Karyawan disetujui masuk."}

	@frappe.whitelist()
	def reject(self, reason=""):
		if self.status != "Pending Approval":
			frappe.throw(_("Status bukan Pending Approval"))
		self.status = "Rejected"
		self.rejected_reason = reason
		self.approved_by = frappe.session.user
		self.approved_at = now_datetime()
		self.save(ignore_permissions=True)
		return {"status": "success", "message": "Pengajuan karyawan ditolak."}

	@frappe.whitelist()
	def complete(self):
		if self.status != "Approved":
			frappe.throw(_("Status belum Approved"))
		self.status = "Completed"
		self.completed_at = now_datetime()
		self.save(ignore_permissions=True)
		return {"status": "success", "message": "Kegiatan karyawan selesai."}

	@frappe.whitelist()
	def checkout(self):
		if self.status != "Completed":
			frappe.throw(_("Status belum Completed"))
		self.status = "Checked Out"
		self.check_out_time = now_datetime()
		self.save(ignore_permissions=True)
		return {"status": "success", "message": "Karyawan check-out."}
