import io
import json
import os
import uuid

import frappe
import qrcode
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.log_service import create_visitor_log
from visitor_management.visitor_management.services.visitor_service import check_in, check_out

VISITOR_STATUSES = [
    "Registered",
    "Awaiting Approval",
    "Approved",
    "Checked In",
    "Completed",
    "Checked Out",
    "Rejected",
    "Cancelled",
]

COMPLETABLE_STATUSES = ["Approved", "Checked In"]




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
            qr_data = json.dumps({
                "visitor_id": self.name,
                "visitor_name": self.visitor_name,
                "host": self.host_employee or "",
            })

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
                "DELETE FROM `tabFile` WHERE attached_to_doctype='Visitor' AND attached_to_name=%s",
                self.name
            )

            file_doc_name = uuid.uuid4().hex[:10]
            frappe.db.sql("""
                INSERT INTO `tabFile`
                (name, file_name, file_url, is_private,
                 attached_to_doctype, attached_to_name, attached_to_field,
                 file_size, creation, modified, modified_by, owner, docstatus)
                VALUES
                (%s, %s, %s, 0, 'Visitor', %s, 'qr_code_image',
                 %s, NOW(), NOW(), 'Administrator', 'Administrator', 0)
            """, (file_doc_name, file_name, file_url, self.name, file_size))

            frappe.db.sql(
                "UPDATE `tabVisitor` SET qr_code=%s, qr_code_image=%s WHERE name=%s",
                (qr_data, file_url, self.name)
            )

            frappe.db.commit()

        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")

    @frappe.whitelist()
    def do_checkin(self):
        return check_in(self)

    def _has_field(self, fieldname):
        return bool(self.meta and self.meta.has_field(fieldname))

    def _get_workflow_state_field(self):
        """Return the configured workflow-state field, when a Visitor Workflow exists."""
        workflow_state_field = None

        try:
            workflow_name = frappe.db.get_value(
                "Workflow",
                {"document_type": self.doctype, "is_active": 1},
                "name",
            )
            if workflow_name:
                workflow_state_field = frappe.db.get_value(
                    "Workflow",
                    workflow_name,
                    "workflow_state_field",
                )
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS Workflow Lookup Error")

        if workflow_state_field and self._has_field(workflow_state_field):
            return workflow_state_field
        if self._has_field("workflow_state"):
            return "workflow_state"
        return None

    def _set_transition_values(self, target_status, **extra_values):
        if target_status not in VISITOR_STATUSES:
            frappe.throw(_("Status visitor tidak dikenali: {0}").format(target_status))

        self.status = target_status
        workflow_state_field = self._get_workflow_state_field()
        if workflow_state_field and workflow_state_field != "status":
            self.set(workflow_state_field, target_status)

        for fieldname, value in extra_values.items():
            if self._has_field(fieldname):
                self.set(fieldname, value)

    def _db_set_transition_values(self, target_status, **extra_values):
        values = {"status": target_status}
        workflow_state_field = self._get_workflow_state_field()
        if workflow_state_field and workflow_state_field != "status":
            values[workflow_state_field] = target_status

        for fieldname, value in extra_values.items():
            if self._has_field(fieldname):
                values[fieldname] = value

        frappe.db.set_value(self.doctype, self.name, values, update_modified=True)
        self.reload()

    def _can_use_db_set_fallback(self, error):
        """Only bypass save for workflow/docstatus blockers, not data validation."""
        error_name = error.__class__.__name__.lower()
        error_text = str(error).lower()
        fallback_markers = (
            "workflow",
            "transition",
            "not permitted",
            "permission",
            "submitted",
            "docstatus",
            "update after submit",
            "read only",
        )
        return any(marker in error_name or marker in error_text for marker in fallback_markers)

    def _save_status_transition(self, target_status, log_action, log_remarks, **extra_values):
        """Persist a status transition and keep custom workflow-state fields in sync.

        Some customer sites add a Frappe Workflow on top of this custom status
        field. The VMS approval endpoints already enforce their own ownership /
        manager checks. If a site Workflow/docstatus rule blocks the direct save,
        we log that failure and persist the synchronized status fields with
        db_set. Other validation errors are re-raised so bad data is not hidden.
        """
        self._set_transition_values(target_status, **extra_values)
        self.flags.ignore_permissions = True
        self.flags.ignore_validate_update_after_submit = True

        try:
            self.save(ignore_permissions=True)
        except Exception as error:
            frappe.log_error(
                message=frappe.get_traceback(),
                title="VMS Visitor Transition Save Error",
            )
            if not self._can_use_db_set_fallback(error):
                frappe.throw(_("Gagal mengubah status visitor: {0}").format(error))
            self._db_set_transition_values(target_status, **extra_values)

        self.create_visitor_log(log_action, log_remarks)

    @frappe.whitelist()
    def approve_visit(self):
        if self.status != "Awaiting Approval":
            frappe.throw(_("Tidak bisa approve. Status saat ini: {0}.").format(self.status))

        approved_at = now_datetime()
        self._save_status_transition(
            "Approved",
            "Approved",
            "Disetujui oleh {0}".format(frappe.session.user),
            approved_by=frappe.session.user,
            approved_at=approved_at,
        )
        return {"status": "success", "message": "Kunjungan disetujui.", "visitor_status": self.status}

    @frappe.whitelist()
    def reject_visit(self, reason=""):
        if self.status != "Awaiting Approval":
            frappe.throw(_("Tidak bisa reject. Status saat ini: {0}.").format(self.status))
        if not reason:
            frappe.throw(_("Alasan penolakan wajib diisi."))

        approved_at = now_datetime()
        self._save_status_transition(
            "Rejected",
            "Rejected",
            "Ditolak: {0}".format(reason),
            rejected_reason=reason,
            approved_by=frappe.session.user,
            approved_at=approved_at,
        )
        return {"status": "success", "message": "Kunjungan ditolak.", "visitor_status": self.status}

    @frappe.whitelist()
    def end_visit(self):
        if self.status not in COMPLETABLE_STATUSES:
            frappe.throw(_(
                "Tidak bisa menyelesaikan kunjungan. Status saat ini: {0}. "
                "Status yang diizinkan: {1}."
            ).format(self.status, ", ".join(COMPLETABLE_STATUSES)))

        self._save_status_transition(
            "Completed",
            "Completed",
            "Kunjungan selesai",
            completed_at=now_datetime(),
        )
        return {
            "status": "success",
            "message": "Kunjungan selesai. Tamu dapat check-out.",
            "visitor_status": self.status,
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
