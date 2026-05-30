import frappe
from frappe import _
from frappe.model.document import Document


class VMSCleanupHistory(Document):
    def before_insert(self):
        if not getattr(frappe.flags, 'in_vms_cleanup', False):
            frappe.throw(_('VMS Cleanup History records are system-generated from the VMS Cleanup Tool.'))

    def validate(self):
        if not getattr(frappe.flags, 'in_vms_cleanup', False) and not self.is_new():
            frappe.throw(_('VMS Cleanup History records cannot be edited manually.'))
