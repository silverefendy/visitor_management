import frappe
from frappe.model.document import Document

from visitor_management.visitor_management.services.visitor_service import (
    VisitorService,
    STATUS_REGISTERED,
    check_in,
    check_out,
    get_visitor_info as get_visitor_info_service,
    get_visitor_id_from_qr,
)


class Visitor(Document):
    def before_insert(self):
        self.status = STATUS_REGISTERED

    def after_insert(self):
        VisitorService(self).generate_qr_code()

    def after_save(self):
        if not self.qr_code_image:
            VisitorService(self).generate_qr_code()

    def validate(self):
        VisitorService(self).validate()

    @frappe.whitelist()
    def do_checkin(self):
        return check_in(self)

    @frappe.whitelist()
    def approve_visit(self):
        return VisitorService(self).approve_visit()

    @frappe.whitelist()
    def reject_visit(self, reason=""):
        return VisitorService(self).reject_visit(reason=reason)

    @frappe.whitelist()
    def end_visit(self):
        return VisitorService(self).end_visit()

    @frappe.whitelist()
    def do_checkout(self):
        return check_out(self)

    def create_visitor_log(self, action, remarks=""):
        VisitorService(self).create_visitor_log(action, remarks=remarks)


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(
        user
    ) or "Visitor Manager" in frappe.get_roles(user):
        return ""

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if employee:
        return "`tabVisitor`.`host_employee` = {0}".format(frappe.db.escape(employee))

    return "1=0"


@frappe.whitelist(allow_guest=False)
def checkin_by_qr(qr_data):
    visitor = frappe.get_doc("Visitor", get_visitor_id_from_qr(qr_data))
    return visitor.do_checkin()


@frappe.whitelist(allow_guest=False)
def checkout_by_qr(qr_data):
    visitor = frappe.get_doc("Visitor", get_visitor_id_from_qr(qr_data))
    return visitor.do_checkout()


@frappe.whitelist(allow_guest=False)
def get_visitor_info(visitor_id):
    return get_visitor_info_service(visitor_id)
