import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.log_service import create_visitor_log
from visitor_management.visitor_management.services.visitor_service import check_in, check_out


class Visitor(Document):
    def before_insert(self):
        self.status = "Registered"

    def after_insert(self):
        self.generate_qr_code()

    def after_save(self):
        if not self.qr_code_image:
            self.generate_qr_code()

    def validate(self):
        if self.host_employee:
            emp_status = frappe.db.get_value("Employee", self.host_employee, "status")
            if emp_status != "Active":
                frappe.throw(_("Karyawan {0} tidak aktif.").format(self.host_employee))

    def generate_qr_code(self):
        try:
            import io
            import uuid

            import qrcode

            qr_data = json.dumps(
                {
                    "visitor_id": self.name,
                    "visitor_name": self.visitor_name,
                    "host": self.host_employee or "",
                }
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            img_bytes = buf.read()

            abs_files_path = "/home/frappe/frappe-bench-v16/sites/wp.local/public/files"
            file_name = "qr_{0}.png".format(self.name)
            full_path = os.path.join(abs_files_path, file_name)

            with open(full_path, "wb") as f:
                f.write(img_bytes)
            os.chmod(full_path, 0o644)

            file_url = "/files/{0}".format(file_name)
            file_size = os.path.getsize(full_path)

            frappe.db.sql(
                "DELETE FROM `tabFile` WHERE attached_to_doctype='Visitor' AND attached_to_name=%s", self.name
            )

            file_doc_name = uuid.uuid4().hex[:10]
            frappe.db.sql(
                """
                INSERT INTO `tabFile`
                (name, file_name, file_url, is_private,
                 attached_to_doctype, attached_to_name, attached_to_field,
                 file_size, creation, modified, modified_by, owner, docstatus)
                VALUES
                (%s, %s, %s, 0, 'Visitor', %s, 'qr_code_image',
                 %s, NOW(), NOW(), 'Administrator', 'Administrator', 0)
            """,
                (file_doc_name, file_name, file_url, self.name, file_size),
            )

            frappe.db.sql(
                "UPDATE `tabVisitor` SET qr_code=%s, qr_code_image=%s WHERE name=%s",
                (qr_data, file_url, self.name),
            )

            frappe.db.commit()

        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")

    @frappe.whitelist()
    def do_checkin(self):
        return check_in(self)

    @frappe.whitelist()
    def approve_visit(self):
        if self.status != "Awaiting Approval":
            frappe.throw(_("Status bukan Awaiting Approval."))

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()
        self.save(ignore_permissions=True)

        self.create_visitor_log("Approved", "Disetujui oleh {0}".format(frappe.session.user))

        frappe.db.commit()

        return {"status": "success", "message": "Kunjungan disetujui."}

    @frappe.whitelist()
    def reject_visit(self, reason=""):
        if self.status != "Awaiting Approval":
            frappe.throw(_("Status bukan Awaiting Approval."))

        self.status = "Rejected"
        self.rejected_reason = reason
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()
        self.save(ignore_permissions=True)

        self.create_visitor_log("Rejected", "Ditolak: {0}".format(reason))

        frappe.db.commit()

        return {"status": "success", "message": "Kunjungan ditolak."}

    @frappe.whitelist()
    def end_visit(self):
        if self.status not in ["Approved", "Checked In"]:
            frappe.throw(_("Kunjungan belum disetujui."))

        self.status = "Completed"
        self.save(ignore_permissions=True)

        self.create_visitor_log("Completed", "Kunjungan selesai")

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Kunjungan selesai. Tamu dapat check-out.",
        }

    @frappe.whitelist()
    def do_checkout(self):
        return check_out(self)

    def create_visitor_log(self, action, remarks=""):
        try:
            create_visitor_log(self, action, remarks=remarks)
        except Exception:
            frappe.log_error(title="VMS Log Error", message=frappe.get_traceback())


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Visitor Manager" in frappe.get_roles(user):
        return ""

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if employee:
        return "`tabVisitor`.`host_employee` = '{0}'".format(employee)

    return "1=0"


@frappe.whitelist(allow_guest=False)
def checkin_by_qr(qr_data):
    try:
        data = json.loads(qr_data)
        visitor_id = data.get("visitor_id")

        if not visitor_id:
            frappe.throw(_("QR tidak valid"))

        visitor = frappe.get_doc("Visitor", visitor_id)
        return visitor.do_checkin()

    except json.JSONDecodeError:
        frappe.throw(_("Format QR tidak dikenali"))


@frappe.whitelist(allow_guest=False)
def checkout_by_qr(qr_data):
    try:
        data = json.loads(qr_data)
        visitor_id = data.get("visitor_id")

        if not visitor_id:
            frappe.throw(_("QR tidak valid"))

        visitor = frappe.get_doc("Visitor", visitor_id)
        return visitor.do_checkout()

    except json.JSONDecodeError:
        frappe.throw(_("Format QR tidak dikenali"))


@frappe.whitelist()
def get_visitor_info(visitor_id):
    visitor = frappe.get_doc("Visitor", visitor_id)

    return {
        "name": visitor.name,
        "visitor_name": visitor.visitor_name,
        "status": visitor.status,
        "qr_code_image": visitor.qr_code_image,
    }
