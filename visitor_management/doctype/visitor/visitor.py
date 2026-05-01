import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url
import qrcode
import io
import base64
import json
from datetime import datetime


class Visitor(Document):

    def before_insert(self):
        """Set status awal saat pertama dibuat"""
        self.status = "Registered"

    def after_insert(self):
        """Setelah disimpan, generate QR dan kirim notifikasi ke karyawan"""
        self.generate_qr_code()
        self.notify_host_employee()

    def validate(self):
        """Validasi data sebelum disimpan"""
        self.validate_employee_exists()

    def validate_employee_exists(self):
        """Pastikan host employee masih aktif"""
        if self.host_employee:
            emp_status = frappe.db.get_value("Employee", self.host_employee, "status")
            if emp_status != "Active":
                frappe.throw(
                    _("Karyawan {0} tidak aktif. Silakan pilih karyawan lain.").format(
                        self.host_employee
                    )
                )

    def generate_qr_code(self):
        """Generate QR code berisi data visitor untuk di-scan security"""
        qr_data = {
            "visitor_id": self.name,
            "visitor_name": self.visitor_name,
            "host": self.host_employee,
            "timestamp": str(now_datetime()),
        }

        qr_string = json.dumps(qr_data)
        self.db_set("qr_code", qr_string)

        # Buat gambar QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Simpan sebagai base64 ke file
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        # Simpan file ke ERPNext
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"qr_{self.name}.png",
            "content": base64.b64encode(buffer.getvalue()).decode(),
            "is_private": 0,
            "attached_to_doctype": "Visitor",
            "attached_to_name": self.name,
            "attached_to_field": "qr_code_image",
        })
        file_doc.save(ignore_permissions=True)
        self.db_set("qr_code_image", file_doc.file_url)

    def notify_host_employee(self):
        """Kirim notifikasi email ke karyawan yang akan dikunjungi"""
        try:
            employee = frappe.get_doc("Employee", self.host_employee)
            if not employee.company_email and not employee.personal_email:
                return

            email = employee.company_email or employee.personal_email
            visitor_url = get_url(f"/app/visitor/{self.name}")

            frappe.sendmail(
                recipients=[email],
                subject=f"[VMS] Tamu Baru: {self.visitor_name} akan mengunjungi Anda",
                message=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px;">
                    <h2 style="color: #2e4057;">Notifikasi Kunjungan Tamu</h2>
                    <p>Halo <strong>{employee.employee_name}</strong>,</p>
                    <p>Ada tamu yang akan mengunjungi Anda:</p>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Nama</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{self.visitor_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Perusahaan</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{self.visitor_company or '-'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Keperluan</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{self.visit_purpose}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Nomor ID</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{self.id_type}: {self.id_number}</td>
                        </tr>
                    </table>
                    <br>
                    <p>Silakan buka link berikut untuk menyetujui atau menolak kunjungan:</p>
                    <a href="{visitor_url}" style="
                        background-color: #4a90e2;
                        color: white;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 4px;
                        display: inline-block;
                        margin: 10px 0;
                    ">Lihat Detail & Konfirmasi</a>
                    <p style="color: #888; font-size: 12px;">
                        Visitor ID: {self.name}
                    </p>
                </div>
                """,
                now=True,
            )
        except Exception as e:
            frappe.log_error(f"Gagal kirim notifikasi ke {self.host_employee}: {str(e)}")

    @frappe.whitelist()
    def do_checkin(self):
        """Security scan QR → Check In visitor"""
        if self.status not in ["Registered", "Approved"]:
            frappe.throw(
                _("Visitor tidak bisa check-in. Status saat ini: {0}").format(self.status)
            )

        self.status = "Awaiting Approval"
        self.check_in_time = now_datetime()
        self.save(ignore_permissions=True)

        # Kirim notif ke karyawan untuk approve
        self.send_approval_request()

        # Buat log
        self.create_visitor_log("Check In", "Visitor melakukan check-in di security")

        return {"status": "success", "message": "Check-in berhasil. Menunggu konfirmasi karyawan."}

    @frappe.whitelist()
    def approve_visit(self):
        """Karyawan menyetujui kunjungan"""
        if self.status != "Awaiting Approval":
            frappe.throw(
                _("Kunjungan tidak dalam status menunggu persetujuan.")
            )

        # Pastikan yang approve adalah host atau manager
        self.check_approval_permission()

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()
        self.save(ignore_permissions=True)

        self.create_visitor_log("Approved", f"Disetujui oleh {frappe.session.user}")
        self.notify_security_approved()

        return {"status": "success", "message": "Kunjungan disetujui."}

    @frappe.whitelist()
    def reject_visit(self, reason=""):
        """Karyawan menolak kunjungan"""
        if self.status != "Awaiting Approval":
            frappe.throw(_("Kunjungan tidak dalam status menunggu persetujuan."))

        self.check_approval_permission()

        self.status = "Rejected"
        self.rejected_reason = reason
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()
        self.save(ignore_permissions=True)

        self.create_visitor_log("Rejected", f"Ditolak: {reason}")
        self.notify_security_rejected()

        return {"status": "success", "message": "Kunjungan ditolak."}

    @frappe.whitelist()
    def end_visit(self):
        """Karyawan mengkonfirmasi visit selesai"""
        if self.status not in ["Approved", "Checked In"]:
            frappe.throw(
                _("Kunjungan belum disetujui atau sudah selesai.")
            )

        self.check_approval_permission()

        self.status = "Completed"
        self.save(ignore_permissions=True)

        self.create_visitor_log("Completed", "Kunjungan selesai, tamu diminta check-out")
        self.notify_visitor_checkout()

        return {"status": "success", "message": "Kunjungan selesai. Tamu dapat check-out."}

    @frappe.whitelist()
    def do_checkout(self):
        """Security scan QR → Check Out visitor"""
        if self.status != "Completed":
            frappe.throw(
                _("Visitor belum dalam status selesai. Status: {0}").format(self.status)
            )

        self.status = "Checked Out"
        self.check_out_time = now_datetime()
        self.save(ignore_permissions=True)

        self.create_visitor_log("Check Out", "Visitor melakukan check-out di security")

        duration = self.get_visit_duration()
        return {
            "status": "success",
            "message": f"Check-out berhasil. Durasi kunjungan: {duration}",
        }

    def check_approval_permission(self):
        """Cek apakah user yang sedang login berhak approve/reject"""
        current_user = frappe.session.user

        # Cari employee linked ke user login
        employee = frappe.db.get_value(
            "Employee", {"user_id": current_user}, "name"
        )

        # Izinkan jika dia adalah host, atau System Manager
        is_host = employee == self.host_employee
        is_manager = "System Manager" in frappe.get_roles(current_user)
        is_visitor_manager = "Visitor Manager" in frappe.get_roles(current_user)

        if not (is_host or is_manager or is_visitor_manager):
            frappe.throw(
                _("Anda tidak berwenang untuk melakukan tindakan ini. "
                  "Hanya karyawan yang dikunjungi yang bisa konfirmasi.")
            )

    def create_visitor_log(self, action, remarks=""):
        """Buat log setiap aksi pada visitor"""
        log = frappe.get_doc({
            "doctype": "Visitor Log",
            "visitor": self.name,
            "action": action,
            "action_time": now_datetime(),
            "action_by": frappe.session.user,
            "remarks": remarks,
        })
        log.insert(ignore_permissions=True)

    def send_approval_request(self):
        """Kirim notifikasi ke karyawan bahwa tamu sudah check-in dan butuh approval"""
        try:
            employee = frappe.get_doc("Employee", self.host_employee)
            email = employee.company_email or employee.personal_email
            if not email:
                return

            visitor_url = get_url(f"/app/visitor/{self.name}")

            frappe.sendmail(
                recipients=[email],
                subject=f"[VMS] SEGERA: {self.visitor_name} sudah tiba - Mohon konfirmasi",
                message=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px;">
                    <h2 style="color: #e74c3c;">Tamu Anda Sudah Tiba!</h2>
                    <p>Halo <strong>{employee.employee_name}</strong>,</p>
                    <p><strong>{self.visitor_name}</strong> dari <strong>{self.visitor_company or '-'}</strong>
                    sudah check-in di security pada <strong>{self.check_in_time}</strong>.</p>
                    <p>Silakan konfirmasi apakah Anda akan menerima tamu ini:</p>
                    <a href="{visitor_url}" style="
                        background-color: #27ae60;
                        color: white;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 4px;
                        display: inline-block;
                        margin: 5px;
                    ">✓ Terima Tamu</a>
                    <p style="color: #888; font-size: 12px;">Visitor ID: {self.name}</p>
                </div>
                """,
                now=True,
            )
        except Exception as e:
            frappe.log_error(f"Gagal kirim approval request: {str(e)}")

    def notify_security_approved(self):
        """Beritahu security bahwa tamu diizinkan masuk"""
        # Kirim notifikasi ke role Security
        security_users = frappe.get_all(
            "Has Role",
            filters={"role": "Visitor Security", "parenttype": "User"},
            fields=["parent"],
        )
        for u in security_users:
            frappe.publish_realtime(
                "vms_visitor_approved",
                {"visitor_id": self.name, "visitor_name": self.visitor_name},
                user=u.parent,
            )

    def notify_security_rejected(self):
        """Beritahu security bahwa tamu ditolak"""
        security_users = frappe.get_all(
            "Has Role",
            filters={"role": "Visitor Security", "parenttype": "User"},
            fields=["parent"],
        )
        for u in security_users:
            frappe.publish_realtime(
                "vms_visitor_rejected",
                {
                    "visitor_id": self.name,
                    "visitor_name": self.visitor_name,
                    "reason": self.rejected_reason,
                },
                user=u.parent,
            )

    def notify_visitor_checkout(self):
        """Kirim email ke tamu bahwa visit selesai dan harus ke security"""
        if self.visitor_email:
            frappe.sendmail(
                recipients=[self.visitor_email],
                subject="Kunjungan Selesai - Silakan Lakukan Check-Out",
                message=f"""
                <div style="font-family: Arial, sans-serif;">
                    <h2>Kunjungan Selesai</h2>
                    <p>Halo <strong>{self.visitor_name}</strong>,</p>
                    <p>Kunjungan Anda telah selesai. Silakan laporkan ke meja security
                    dan scan QR Code Anda untuk melakukan check-out.</p>
                    <p>Terima kasih telah berkunjung!</p>
                </div>
                """,
                now=True,
            )

    def get_visit_duration(self):
        """Hitung durasi kunjungan"""
        if self.check_in_time and self.check_out_time:
            delta = self.check_out_time - self.check_in_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            return f"{hours} jam {minutes} menit"
        return "N/A"


# ─── Permission helper ────────────────────────────────────────────────────────

def get_permission_query_conditions(user):
    """Employee hanya bisa lihat visitor yang mengunjungi mereka sendiri"""
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Visitor Manager" in frappe.get_roles(user):
        return ""

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if employee:
        return f"`tabVisitor`.`host_employee` = '{employee}'"

    return "1=0"


# ─── API Methods (dipanggil dari JavaScript / QR scanner) ────────────────────

@frappe.whitelist(allow_guest=False)
def checkin_by_qr(qr_data):
    """API untuk security scan QR → check in"""
    try:
        data = json.loads(qr_data)
        visitor_id = data.get("visitor_id")

        if not visitor_id:
            frappe.throw(_("QR Code tidak valid"))

        visitor = frappe.get_doc("Visitor", visitor_id)
        return visitor.do_checkin()

    except json.JSONDecodeError:
        frappe.throw(_("Format QR Code tidak dikenali"))
    except frappe.DoesNotExistError:
        frappe.throw(_("Data visitor tidak ditemukan"))


@frappe.whitelist(allow_guest=False)
def checkout_by_qr(qr_data):
    """API untuk security scan QR → check out"""
    try:
        data = json.loads(qr_data)
        visitor_id = data.get("visitor_id")

        if not visitor_id:
            frappe.throw(_("QR Code tidak valid"))

        visitor = frappe.get_doc("Visitor", visitor_id)
        return visitor.do_checkout()

    except json.JSONDecodeError:
        frappe.throw(_("Format QR Code tidak dikenali"))
    except frappe.DoesNotExistError:
        frappe.throw(_("Data visitor tidak ditemukan"))


@frappe.whitelist()
def get_visitor_info(visitor_id):
    """Ambil info visitor untuk ditampilkan di scanner"""
    visitor = frappe.get_doc("Visitor", visitor_id)
    return {
        "name": visitor.name,
        "visitor_name": visitor.visitor_name,
        "visitor_company": visitor.visitor_company,
        "host_employee_name": visitor.host_employee_name,
        "department": visitor.department,
        "visit_purpose": visitor.visit_purpose,
        "status": visitor.status,
        "check_in_time": str(visitor.check_in_time) if visitor.check_in_time else None,
        "check_out_time": str(visitor.check_out_time) if visitor.check_out_time else None,
        "qr_code_image": visitor.qr_code_image,
    }


@frappe.whitelist()
def get_today_visitors():
    """Dashboard: ambil semua visitor hari ini"""
    from frappe.utils import today

    visitors = frappe.get_all(
        "Visitor",
        filters=[["creation", ">=", today()]],
        fields=[
            "name", "visitor_name", "visitor_company",
            "host_employee_name", "department", "status",
            "check_in_time", "check_out_time",
        ],
        order_by="creation desc",
    )
    return visitors
