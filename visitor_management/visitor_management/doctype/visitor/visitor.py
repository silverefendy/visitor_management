import io
import json
import os
import uuid

import frappehttps://github.com/silverefendy/visitor_management/pull/20/conflict?name=visitor_management%252Fvisitor_management%252Fdoctype%252Fvisitor%252Fvisitor.py&ancestor_oid=192f4f80270c183f4e61069d257ed4b3949b0eac&base_oid=1d2f812d76c4f64617d97ed3357c88f58219c6f7&head_oid=0bbad1852c2c2b7b750f8cd09546d091066a447f
import qrcode
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from visitor_management.visitor_management.services.log_service import create_visitor_log
from visitor_management.visitor_management.services.visitor_service import (
    check_in,
    check_out,
    close_active_visitor_logs,
)

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

COMPLETABLE_STATUSES = ["Approved", "Checked In"]

class Visitor(Document):
    def before_insert(self):
        self.status = "Registered"
        self._sync_workflow_state("Registered")

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
                self.name,
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
                (qr_data, file_url, self.name),
            )

            frappe.db.commit()

        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")

    @frappe.whitelist()
    def do_checkin(self):
        return check_in(self)

    def _has_field(self, fieldname):
        return bool(self.meta and self.meta.has_field(fieldname))

    def _get_active_workflow(self):
        try:
            from frappe.model.workflow import get_workflow, get_workflow_name

            workflow_name = get_workflow_name(self.doctype)
            return get_workflow(self.doctype) if workflow_name else None
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS Workflow Lookup Error")
            return None

    def _get_workflow_state_field(self, workflow=None):
        workflow_state_field = getattr(workflow, "workflow_state_field", None)
        if workflow_state_field and self._has_field(workflow_state_field):
            return workflow_state_field
        if self._has_field("workflow_state"):
            return "workflow_state"
        return None

    def _sync_workflow_state(self, target_status, workflow=None):
        workflow_state_field = self._get_workflow_state_field(workflow=workflow)
        if workflow_state_field and workflow_state_field != "status":
            self.set(workflow_state_field, target_status)

    def _set_transition_values(self, target_status, workflow=None, **extra_values):
        if target_status not in VISITOR_STATUSES:
            frappe.throw(_("Status visitor tidak dikenali: {0}").format(target_status))

        self.status = target_status
        self._sync_workflow_state(target_status, workflow=workflow)

        for fieldname, value in extra_values.items():
            if self._has_field(fieldname):
                self.set(fieldname, value)

    def _get_workflow_action_for_target(self, workflow, target_status):
        from frappe.model.workflow import get_transitions

        transitions = get_transitions(self, workflow=workflow)
        for transition in transitions:
            if transition.get("next_state") == target_status:
                return transition.get("action")
        return None

    def _apply_workflow_transition(self, workflow, target_status):
        from frappe.model.workflow import apply_workflow

        action = self._get_workflow_action_for_target(workflow, target_status)
        if not action:
            frappe.throw(_(
                "Tidak ada workflow action yang valid dari {0} ke {1} untuk user {2}."
            ).format(self.status, target_status, frappe.session.user))

        frappe.logger("visitor_management").info(
            "Applying Visitor workflow action",
            extra={"visitor": self.name, "action": action, "target_status": target_status},
        )
        return apply_workflow(self.as_dict(), action)

    def _persist_status_sync(self, target_status, workflow=None, **extra_values):
        """Persist status mirrors after a workflow action changed the workflow field."""
        values = {"status": target_status}
        workflow_state_field = self._get_workflow_state_field(workflow=workflow)
        if workflow_state_field and workflow_state_field != "status":
            values[workflow_state_field] = target_status

        for fieldname, value in extra_values.items():
            if self._has_field(fieldname):
                values[fieldname] = value

        frappe.db.set_value(self.doctype, self.name, values, update_modified=True)
        self.reload()

    def _status_response(self, message):
        workflow_state_field = self._get_workflow_state_field()
        workflow_state = self.get(workflow_state_field) if workflow_state_field else self.status
        return {
            "success": True,
            "status": "success",
            "message": message,
            "visitor": self.name,
            "visitor_status": self.status,
            "workflow_state": workflow_state,
        }

    def _save_status_transition(self, target_status, log_action, log_remarks, **extra_values):
        """Persist a Visitor transition using Frappe Workflow when one is active.

        The custom app owns the business permission check before this method is
        called. If a site has an active Workflow, use its configured transition so
        workflow actions, tasks, comments, and docstatus logic still run. Then
        verify and mirror `status`/`workflow_state` because this app historically
        uses `status` for filtering custom pages and mobile APIs.
        """
        workflow = self._get_active_workflow()
        self.flags.ignore_permissions = True
        self.flags.ignore_validate_update_after_submit = True
        frappe.logger("visitor_management").info(
            "Visitor status transition attempt",
            extra={
                "visitor": self.name,
                "from_status": self.status,
                "target_status": target_status,
                "workflow": getattr(workflow, "name", None),
            },
        )

        try:
            if workflow:
                workflow_state_field = self._get_workflow_state_field(workflow=workflow)
                if (
                    workflow_state_field
                    and workflow_state_field != "status"
                    and self.get(workflow_state_field) != self.status
                ):
                    frappe.logger("visitor_management").info(
                        "Synchronizing stale Visitor workflow state before transition",
                        extra={
                            "visitor": self.name,
                            "status": self.status,
                            "workflow_state": self.get(workflow_state_field),
                        },
                    )
                    frappe.db.set_value(
                        self.doctype,
                        self.name,
                        workflow_state_field,
                        self.status,
                        update_modified=True,
                    )
                    self.reload()

                self._apply_workflow_transition(workflow, target_status)
                self.reload()
                self._persist_status_sync(target_status, workflow=workflow, **extra_values)
            else:
                self._set_transition_values(target_status, **extra_values)
                self.save(ignore_permissions=True)
                self.reload()
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="VMS Visitor Transition Error")
            raise

        workflow_state_field = self._get_workflow_state_field(workflow=workflow)
        workflow_state = self.get(workflow_state_field) if workflow_state_field else self.status
        if self.status != target_status or workflow_state != target_status:
            frappe.log_error(
                message=(
                    "Visitor transition verification failed for {0}: "
                    "status={1}, workflow_state={2}, expected={3}"
                ).format(self.name, self.status, workflow_state, target_status),
                title="VMS Visitor Transition Verification Error",
            )
            frappe.throw(_("Gagal menyimpan status {0}. Silakan coba lagi.").format(target_status))

        self.create_visitor_log(log_action, log_remarks)
        if target_status == "Completed":
            close_active_visitor_logs(self.name)
        frappe.db.commit()

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
        return self._status_response("Kunjungan disetujui.")

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
        return self._status_response("Kunjungan ditolak.")

    @frappe.whitelist()
    def end_visit(self):
        if self.status == "Completed":
            frappe.throw(_("Kunjungan ini sudah Completed."))
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
        return self._status_response("Kunjungan selesai. Tamu dapat check-out.")

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
