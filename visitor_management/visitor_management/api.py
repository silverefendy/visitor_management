# =============================================================================
# api.py — Visitor Management
# Lokasi file ini di server:
#   /home/frappe/frappe-bench/apps/visitor_management/visitor_management/visitor_management/api.py
#
# Setelah upload/edit file ini, jalankan di server:
#   bench clear-cache && bench restart
# =============================================================================

import frappe
from frappe import _
from frappe.utils import today, now_datetime
import json


# =============================================================================
# HELPER FUNCTIONS (private — tidak bisa dipanggil dari browser)
# Fungsi dengan awalan _ adalah helper internal, tidak perlu @whitelist
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_csrf_token():
    """Return a fresh CSRF token for custom web pages."""
    return frappe.sessions.get_csrf_token()


def _get_employee_for_user(user=None):
    """Cari Employee record yang terhubung ke user login."""
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _can_manage_visitor(visitor):
    """Cek apakah user login boleh kelola visitor ini."""
    user = frappe.session.user
    roles = frappe.get_roles(user)

    # System Manager dan Visitor Manager bisa kelola semua visitor
    if "System Manager" in roles or "Visitor Manager" in roles:
        return True

    # Karyawan hanya bisa kelola visitor yang ditujukan ke dirinya
    employee = _get_employee_for_user(user)
    return bool(employee and visitor.host_employee == employee)


def _get_manageable_visitor(visitor_id):
    """Ambil doc Visitor, lempar error jika tidak ada atau tidak punya akses."""
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))

    visitor = frappe.get_doc("Visitor", visitor_id)
    if not _can_manage_visitor(visitor):
        frappe.throw(_("Anda tidak memiliki akses untuk visitor ini"))

    return visitor


def _is_employee_entry_manager(user=None):
    """
    Cek apakah user adalah manager yang boleh approve/reject Employee Entry.
    Tambahkan nama Role di sini jika ingin memberi akses ke role lain.
    Contoh: tambah "Visitor Approver" jika ada role tersebut.
    """
    roles = frappe.get_roles(user or frappe.session.user)
    return bool({"System Manager", "HR Manager", "Visitor Manager"} & set(roles))


def _get_employee_entry_fields():
    """Field yang diambil saat query Employee Entry Request."""
    return [
        "name",
        "employee",
        "employee_name",
        "department",
        "purpose",
        "status",
        "check_in_time",
        "approved_by",
        "approved_at",
        "completed_at",
        "check_out_time",
        "rejected_reason",
        "modified",
    ]


def _get_manageable_employee_entry(entry_id):
    """
    Ambil doc Employee Entry Request.
    Manager bisa akses semua. Karyawan hanya bisa akses miliknya sendiri.
    """
    if not entry_id or not frappe.db.exists("Employee Entry Request", entry_id):
        frappe.throw(_("Employee Entry Request tidak ditemukan"))

    doc = frappe.get_doc("Employee Entry Request", entry_id)

    # Manager bisa akses semua entry
    if _is_employee_entry_manager():
        return doc

    # Karyawan biasa hanya bisa akses miliknya sendiri
    employee = _get_employee_for_user()
    if employee and doc.employee == employee:
        return doc

    frappe.throw(_("Anda tidak memiliki akses untuk pengajuan ini"))


def _parse_names(names):
    """Parse list nama dari string JSON atau string CSV."""
    if isinstance(names, str):
        try:
            names = json.loads(names)
        except (json.JSONDecodeError, TypeError):
            names = [n.strip() for n in names.split(",") if n.strip()]
    return names or []


# =============================================================================
# VISITOR — QR SCANNER
# =============================================================================

@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action):
    """
    Endpoint untuk scanner QR di security post.
    action: 'checkin' atau 'checkout'
    Dipanggil dari: /vms-scanner
    """
    if not qr_data:
        frappe.throw(_("QR data tidak boleh kosong"))

    try:
        data = json.loads(qr_data)
    except (json.JSONDecodeError, TypeError):
        # Jika bukan JSON, anggap langsung sebagai visitor ID
        data = {"visitor_id": qr_data.strip()}

    visitor_id = data.get("visitor_id")
    if not visitor_id:
        frappe.throw(_("QR Code tidak valid — visitor ID tidak ditemukan"))

    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))

    visitor = frappe.get_doc("Visitor", visitor_id)

    if action == "checkin":
        return visitor.do_checkin()
    elif action == "checkout":
        return visitor.do_checkout()
    else:
        frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
    """
    Ambil detail visitor dari QR data (untuk preview sebelum konfirmasi scan).
    Dipanggil dari: /vms-scanner
    """
    try:
        data = json.loads(qr_data)
    except (json.JSONDecodeError, TypeError):
        data = {"visitor_id": qr_data.strip()}

    visitor_id = data.get("visitor_id")
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        return {"error": "Visitor tidak ditemukan"}

    v = frappe.get_doc("Visitor", visitor_id)
    return {
        "name":               v.name,
        "visitor_name":       v.visitor_name,
        "visitor_company":    v.visitor_company or "-",
        "visitor_phone":      v.visitor_phone,
        "host_employee_name": v.host_employee_name,
        "department":         v.department or "-",
        "visit_purpose":      v.visit_purpose,
        "status":             v.status,
        "check_in_time":      str(v.check_in_time) if v.check_in_time else None,
        "check_out_time":     str(v.check_out_time) if v.check_out_time else None,
        "id_type":            v.id_type,
        "id_number":          v.id_number,
        "qr_code_image":      v.qr_code_image,
    }


# =============================================================================
# VISITOR — DASHBOARD & APPROVAL
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_dashboard_data():
    """
    Data untuk dashboard VMS hari ini.
    Dipanggil dari: /vms-approval (panel manager)
    """
    activity_filters = [["modified", ">=", today()]]
    dashboard_fields = [
        "name",
        "visitor_name",
        "visitor_company",
        "host_employee_name",
        "department",
        "status",
        "check_in_time",
        "check_out_time",
        "rejected_reason",
        "modified",
    ]

    active_visitors = frappe.get_all(
        "Visitor",
        filters=[["status", "in", ["Checked In", "Approved", "Awaiting Approval"]]],
        fields=dashboard_fields,
        order_by="check_in_time asc",
    )

    pending_checkout = frappe.get_all(
        "Visitor",
        filters=[["status", "=", "Completed"]],
        fields=dashboard_fields,
        order_by="modified asc",
    )

    rejected_visitors = frappe.get_all(
        "Visitor",
        filters=activity_filters + [["status", "=", "Rejected"]],
        fields=dashboard_fields,
        order_by="modified desc",
    )

    waiting    = len([v for v in active_visitors if v.status == "Awaiting Approval"])
    checked_in = len([v for v in active_visitors if v.status in ["Checked In", "Approved"]])
    completed  = len(pending_checkout)
    rejected   = len(rejected_visitors)
    checked_out = frappe.db.count(
        "Visitor", filters=activity_filters + [["status", "=", "Checked Out"]]
    )
    total = waiting + checked_in + completed + checked_out + rejected

    return {
        "stats": {
            "total_today":      total,
            "checked_in":       checked_in,
            "completed":        completed,
            "checked_out":      checked_out,
            "waiting_approval": waiting,
            "rejected":         rejected,
        },
        "active_visitors":   active_visitors,
        "pending_checkout":  pending_checkout,
        "rejected_visitors": rejected_visitors,
    }


@frappe.whitelist(allow_guest=False)
def employee_pending_approvals():
    """
    Daftar visitor yang menunggu approval dari karyawan yang sedang login.
    Dipanggil dari: Frappe Desk (notifikasi)
    """
    user     = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        return []

    return frappe.get_all(
        "Visitor",
        filters={"host_employee": employee, "status": "Awaiting Approval"},
        fields=[
            "name", "visitor_name", "visitor_company", "visit_purpose",
            "check_in_time", "id_type", "id_number",
        ],
        order_by="check_in_time asc",
    )


@frappe.whitelist(allow_guest=False)
def employee_approval_data():
    """
    Data approval untuk halaman /vms-approval.
    Manager melihat semua visitor. Karyawan hanya melihat visitor yang ditujukan ke dirinya.
    """
    user      = frappe.session.user
    roles     = frappe.get_roles(user)
    is_manager = "System Manager" in roles or "Visitor Manager" in roles
    employee  = _get_employee_for_user(user)

    if not is_manager and not employee:
        return {
            "user":     user,
            "employee": None,
            "pending":  [],
            "active":   [],
            "warning":  "User login belum terhubung ke Employee.",
        }

    base_filters = {}
    if not is_manager:
        base_filters["host_employee"] = employee

    fields = [
        "name", "visitor_name", "visitor_company", "visitor_phone",
        "visit_purpose", "host_employee_name", "department",
        "status", "check_in_time", "approved_at", "id_type", "id_number",
    ]

    pending_filters = {**base_filters, "status": "Awaiting Approval"}
    active_filters  = {**base_filters, "status": "Approved"}

    return {
        "user":       user,
        "employee":   employee,
        "is_manager": is_manager,
        "pending": frappe.get_all(
            "Visitor", filters=pending_filters, fields=fields,
            order_by="check_in_time asc",
        ),
        "active": frappe.get_all(
            "Visitor", filters=active_filters, fields=fields,
            order_by="approved_at asc, check_in_time asc",
        ),
    }


@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
    """Setujui visitor masuk. Dipanggil dari /vms-approval."""
    visitor = _get_manageable_visitor(visitor_id)
    result  = visitor.approve_visit()
    frappe.publish_realtime(
        "vms_visitor_approved",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name},
        after_commit=True,
    )
    return result


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
    """Tolak visitor. Dipanggil dari /vms-approval."""
    visitor = _get_manageable_visitor(visitor_id)
    result  = visitor.reject_visit(reason)
    frappe.publish_realtime(
        "vms_visitor_rejected",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name, "reason": reason},
        after_commit=True,
    )
    return result


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
    """Tandai kunjungan selesai. Dipanggil dari /vms-approval."""
    visitor = _get_manageable_visitor(visitor_id)
    return visitor.end_visit()


# =============================================================================
# EMPLOYEE ENTRY REQUEST
# =============================================================================

@frappe.whitelist(allow_guest=False)
def create_employee_entry(purpose):
    """
    Buat pengajuan check-in karyawan baru.
    Dipanggil dari: /employee-entry (tombol 'Ajukan Check In')

    SYARAT: User login harus terhubung ke Employee record di ERPNext.
    Cara link: HR → Employee → [nama] → field 'User ID' → isi email login
    """
    employee = _get_employee_for_user()
    if not employee:
        frappe.throw(_(
            "User login belum terhubung ke Employee. "
            "Hubungi HR/Admin untuk mengisi field 'User ID' di profil Employee Anda."
        ))
    if not purpose or not purpose.strip():
        frappe.throw(_("Keperluan / keterangan wajib diisi"))

    doc = frappe.get_doc({
        "doctype": "Employee Entry Request",
        "employee": employee,
        "purpose": purpose.strip(),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status":  "success",
        "message": "Pengajuan check-in karyawan berhasil dibuat.",
        "name":    doc.name,
    }


@frappe.whitelist(allow_guest=False)
def get_employee_entry_data():
    """
    Ambil semua data untuk halaman /employee-entry.

    Return:
      - mine:      pengajuan milik user yang login
      - pending:   menunggu approval (hanya untuk manager)
      - active:    sudah approved, belum selesai (hanya untuk manager)
      - completed: selesai belum checkout (hanya untuk manager)
      - is_manager: True jika user adalah manager
      - warning:   pesan peringatan jika ada (berbeda dari 'message' data)
    """
    employee   = _get_employee_for_user()
    is_manager = _is_employee_entry_manager()
    fields     = _get_employee_entry_fields()

    # Jika bukan manager dan tidak terhubung ke Employee → kembalikan peringatan
    if not is_manager and not employee:
        return {
            "employee":   None,
            "is_manager": False,
            "mine":       [],
            "pending":    [],
            "active":     [],
            "completed":  [],
            # Gunakan field 'warning' (bukan 'message') agar tidak konflik
            "warning": (
                "Akun Anda belum terhubung ke data Karyawan. "
                "Hubungi HR/Admin untuk mengisi field 'User ID' di profil Employee."
            ),
        }

    # Pengajuan milik karyawan yang login
    mine = []
    if employee:
        mine = frappe.get_all(
            "Employee Entry Request",
            filters={"employee": employee},
            fields=fields,
            order_by="modified desc",
            limit_page_length=20,
        )

    # Data tambahan untuk manager
    pending   = []
    active    = []
    completed = []

    if is_manager:
        pending = frappe.get_all(
            "Employee Entry Request",
            filters={"status": "Pending Approval"},
            fields=fields,
            order_by="check_in_time asc",
        )
        active = frappe.get_all(
            "Employee Entry Request",
            filters={"status": "Approved"},
            fields=fields,
            order_by="approved_at asc, check_in_time asc",
        )
        completed = frappe.get_all(
            "Employee Entry Request",
            filters={"status": "Completed"},
            fields=fields,
            order_by="completed_at asc, modified asc",
        )

    return {
        "employee":   employee,
        "is_manager": is_manager,
        "mine":       mine,
        "pending":    pending,
        "active":     active,
        "completed":  completed,
    }


@frappe.whitelist(allow_guest=False)
def employee_entry_action(entry_id, action, reason=""):
    """
    Lakukan aksi pada satu Employee Entry Request.
    Dipanggil dari: /employee-entry (tombol per baris maupun bulk)

    action: 'approve' | 'reject' | 'complete' | 'checkout'
    reason: wajib diisi untuk action 'reject'
    """
    doc = _get_manageable_employee_entry(entry_id)

    if action == "approve":
        return doc.approve()
    elif action == "reject":
        if not reason or not str(reason).strip():
            frappe.throw(_("Alasan penolakan wajib diisi"))
        return doc.reject(reason)
    elif action == "complete":
        return doc.complete()
    elif action == "checkout":
        return doc.checkout()
    else:
        frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def bulk_employee_entry_action(entry_ids, action, reason=""):
    """
    Lakukan aksi pada banyak Employee Entry Request sekaligus.
    Dipanggil dari: /employee-entry (tombol bulk di atas tabel)

    entry_ids: JSON array atau string CSV berisi nama-nama entry
    """
    if not _is_employee_entry_manager():
        frappe.throw(_(
            "Hanya HR Manager, Visitor Manager, atau System Manager "
            "yang dapat melakukan bulk action"
        ))

    ids = _parse_names(entry_ids)
    if not ids:
        frappe.throw(_("Tidak ada entry yang dipilih"))

    results = []
    for entry_id in ids:
        try:
            result = employee_entry_action(entry_id, action, reason)
            results.append({
                "name":    entry_id,
                "status":  "success",
                "message": result.get("message") if result else "OK",
            })
        except Exception as exc:
            results.append({
                "name":    entry_id,
                "status":  "error",
                "message": str(exc),
            })

    berhasil = sum(1 for r in results if r["status"] == "success")
    gagal    = sum(1 for r in results if r["status"] == "error")

    return {
        "status":   "success",
        "berhasil": berhasil,
        "gagal":    gagal,
        "results":  results,
    }


# =============================================================================
# VISITOR BADGE — PRINT
# =============================================================================

@frappe.whitelist(allow_guest=False)
def print_visitor_badge(visitor_id):
    """
    Generate halaman HTML badge visitor untuk di-print.
    Dipanggil dari: /vms-approval (tombol Print Badge)
    Buka di tab baru, lalu tekan tombol Print di halaman tersebut.
    """
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))

    v         = frappe.get_doc("Visitor", visitor_id)
    site_name = frappe.db.get_single_value("System Settings", "site_name") or "Perusahaan"
    purpose   = v.visit_purpose or ""
    purpose_display = (purpose[:50] + "...") if len(purpose) > 50 else purpose
    qr_img    = f'<img class="qr" src="{v.qr_code_image}" alt="QR">' if v.qr_code_image else ""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Visitor Badge — {v.name}</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f0f0f0; margin: 0; padding: 20px; }}
  .badge {{
    width: 85mm; min-height: 120mm;
    background: white;
    border: 2px solid #23405d;
    border-radius: 10px;
    margin: 0 auto;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,.15);
  }}
  .badge-header {{
    background: #23405d; color: white;
    padding: 12px 16px; text-align: center;
    font-size: 15px; font-weight: bold; letter-spacing: 1px;
  }}
  .badge-body {{ padding: 14px 16px; text-align: center; }}
  .label-visitor {{
    display: inline-block; background: #e74c3c; color: white;
    padding: 3px 14px; border-radius: 20px;
    font-size: 11px; font-weight: bold; letter-spacing: 1px;
    margin-bottom: 10px;
  }}
  .visitor-name {{ font-size: 20px; font-weight: bold; color: #23405d; margin: 6px 0 2px; }}
  .visitor-company {{ font-size: 13px; color: #666; margin-bottom: 10px; }}
  .qr {{ width: 90px; height: 90px; margin: 6px auto; display: block; }}
  table {{ width: 100%; font-size: 11px; text-align: left; margin-top: 10px; border-collapse: collapse; }}
  td {{ padding: 3px 4px; vertical-align: top; }}
  .lbl {{ color: #888; width: 38%; white-space: nowrap; }}
  .badge-footer {{
    background: #f5f7fa; border-top: 1px solid #e0e4ea;
    padding: 6px 16px; text-align: center;
    font-size: 10px; color: #aaa;
  }}
  .btn-print {{
    display: block; margin: 20px auto; padding: 10px 28px;
    background: #23405d; color: white; border: none; border-radius: 8px;
    font-size: 14px; font-weight: bold; cursor: pointer;
  }}
  @media print {{
    body {{ background: white; padding: 0; }}
    .btn-print {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="badge">
    <div class="badge-header">{site_name}</div>
    <div class="badge-body">
      <div class="label-visitor">VISITOR</div>
      <div class="visitor-name">{v.visitor_name}</div>
      <div class="visitor-company">{v.visitor_company or ""}</div>
      {qr_img}
      <table>
        <tr>
          <td class="lbl">Menemui</td>
          <td>{v.host_employee_name} ({v.department or "-"})</td>
        </tr>
        <tr>
          <td class="lbl">Keperluan</td>
          <td>{purpose_display}</td>
        </tr>
        <tr>
          <td class="lbl">Identitas</td>
          <td>{v.id_type}: {v.id_number}</td>
        </tr>
        <tr>
          <td class="lbl">Check In</td>
          <td>{str(v.check_in_time)[:16] if v.check_in_time else "-"}</td>
        </tr>
      </table>
    </div>
    <div class="badge-footer">{v.name}</div>
  </div>
  <button class="btn-print" onclick="window.print()">🖨 Print Badge</button>
</body>
</html>"""

    # Kembalikan sebagai halaman HTML (bukan JSON)
    frappe.response["type"]         = "page"
    frappe.local.response["content_type"] = "text/html; charset=utf-8"
    frappe.local.response["body"]   = html


# =============================================================================
# LAPORAN VISITOR
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_visitor_report(from_date, to_date, department=None, status=None):
    """
    Laporan visitor untuk periode tertentu.
    Dipanggil dari: halaman laporan / dashboard

    from_date, to_date: format 'YYYY-MM-DD'
    department: opsional, filter per departemen
    status: opsional, filter per status
    """
    filters = [
        ["creation", ">=", from_date],
        ["creation", "<=", to_date + " 23:59:59"],
    ]
    if department:
        filters.append(["department", "=", department])
    if status:
        filters.append(["status", "=", status])

    visitors = frappe.get_all(
        "Visitor",
        filters=filters,
        fields=[
            "name", "visitor_name", "visitor_company", "visitor_phone",
            "host_employee_name", "department", "visit_purpose",
            "status", "check_in_time", "check_out_time",
            "id_type", "id_number", "creation",
        ],
        order_by="creation desc",
    )

    # Hitung durasi kunjungan
    for v in visitors:
        if v.check_in_time and v.check_out_time:
            delta   = v.check_out_time - v.check_in_time
            hours, r = divmod(int(delta.total_seconds()), 3600)
            minutes = r // 60
            v["duration"] = f"{hours}j {minutes}m"
        else:
            v["duration"] = "-"

    return visitors
