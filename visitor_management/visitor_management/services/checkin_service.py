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

    def ensure_manager(self):
        if not is_approval_manager():
            frappe.throw(
                _("Anda tidak memiliki hak untuk aksi approval"), frappe.PermissionError
            )

    def save_and_commit(self):
        self.doc.save(ignore_permissions=True)
        frappe.db.commit()
