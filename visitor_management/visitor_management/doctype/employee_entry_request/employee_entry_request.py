import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

def _create_employee_entry_log(doc, action, notes=""):
	try:
		frappe.get_doc({
			"doctype": "Employee Entry Log",
			"entry": doc.name,
			"employee": doc.employee,
			"employee_name": doc.employee_name,
			"action": action,
			"status_after": doc.status,
			"performed_by": frappe.session.user,
			"performed_at": now_datetime(),
			"notes": notes or "",
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title="Employee Entry Log Insert Error")


class EmployeeEntryRequest(Document):
	def _save_and_commit(self):
		self.save(ignore_permissions=True)
		frappe.db.commit()

	def before_insert(self):
		if not self.status:
			self.status = "Pending Approval"
		if not self.check_in_time:
			self.check_in_time = now_datetime()

	def after_insert(self):
		_create_employee_entry_log(self, "Created", "Pengajuan employee entry dibuat")

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
		self._save_and_commit()
		_create_employee_entry_log(self, "Approved", "Pengajuan disetujui")
		return {"status": "success", "message": "Karyawan disetujui masuk."}

	@frappe.whitelist()
	def reject(self, reason=""):
		if self.status != "Pending Approval":
			frappe.throw(_("Status bukan Pending Approval"))
		self.status = "Rejected"
		self.rejected_reason = reason
		self.approved_by = frappe.session.user
		self.approved_at = now_datetime()
		self._save_and_commit()
		_create_employee_entry_log(self, "Rejected", reason or "Pengajuan ditolak")
		return {"status": "success", "message": "Pengajuan karyawan ditolak."}

	@frappe.whitelist()
	def complete(self):
		if self.status != "Approved":
			frappe.throw(_("Status belum Approved"))
		self.status = "Completed"
		self.completed_at = now_datetime()
		self._save_and_commit()
		_create_employee_entry_log(self, "Completed", "Kegiatan selesai")
		return {"status": "success", "message": "Kegiatan karyawan selesai."}

	@frappe.whitelist()
	def checkout(self):
		if self.status != "Completed":
			frappe.throw(_("Status belum Completed"))
		self.status = "Checked Out"
		self.check_out_time = now_datetime()
		self._save_and_commit()
		_create_employee_entry_log(self, "Checked Out", "Karyawan check-out")
		return {"status": "success", "message": "Karyawan check-out."}

