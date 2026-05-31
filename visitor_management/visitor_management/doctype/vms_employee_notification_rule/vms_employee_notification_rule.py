import frappe
from frappe.model.document import Document


class VMSEmployeeNotificationRule(Document):
	def validate(self):
		# Pastikan minimal ada satu user penerima
		if not self.notify_users or not self.notify_users.strip():
			frappe.throw("Kolom 'Notify Users' tidak boleh kosong")

		# Validasi channel
		if self.channel not in ("realtime", "email", "both"):
			frappe.throw("Channel harus salah satu dari: realtime, email, both")
