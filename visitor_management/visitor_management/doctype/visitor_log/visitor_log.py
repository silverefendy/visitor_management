import frappe
from frappe.model.document import Document


class VisitorLog(Document):
	def before_insert(self):
		if not self.action_time:
			from frappe.utils import now_datetime

			self.action_time = now_datetime()

		if not self.action_by:
			self.action_by = frappe.session.user
