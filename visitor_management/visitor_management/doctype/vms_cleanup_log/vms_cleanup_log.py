import frappe
from frappe import _
from frappe.model.document import Document


class VMSCleanupLog(Document):
    def before_insert(self):
        if not getattr(frappe.flags, "in_vms_cleanup", False):
            frappe.throw(_("VMS Cleanup Log records are system-generated from the Data Cleanup tool."))

    def validate(self):
        if not getattr(frappe.flags, "in_vms_cleanup", False) and not self.is_new():
            frappe.throw(_("VMS Cleanup Log records cannot be edited manually."))
