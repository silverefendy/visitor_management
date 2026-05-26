import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.checkin_service import (
    EmployeeEntryApprovalService,
    EmployeeEntryCheckinService,
)


def _create_employee_entry_log(doc, action, notes=""):
    try:
        frappe.get_doc(
            {
                "doctype": "Employee Entry Log",
                "entry": doc.name,
                "employee": doc.employee,
                "employee_name": doc.employee_name,
                "action": action,
                "status_after": doc.status,
                "performed_by": frappe.session.user,
                "performed_at": now_datetime(),
                "notes": notes or "",
            }
        ).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(), title="Employee Entry Log Insert Error"
        )


class EmployeeEntryRequest(Document):
    def before_insert(self):
        EmployeeEntryCheckinService(self).before_insert()

    def validate(self):
        EmployeeEntryCheckinService(self).validate()

    def _approval_service(self):
        checkin_service = EmployeeEntryCheckinService(self)
        return EmployeeEntryApprovalService(
            self, checkin_service, _create_employee_entry_log
        )

    @frappe.whitelist()
    def approve(self):
        return self._approval_service().approve()

    @frappe.whitelist()
    def reject(self, reason=""):
        return self._approval_service().reject(reason=reason)

    @frappe.whitelist()
    def complete(self):
        return self._approval_service().complete()

    @frappe.whitelist()
    def checkout(self):
        return self._approval_service().checkout()
