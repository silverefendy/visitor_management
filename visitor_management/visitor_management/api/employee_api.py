# employee_api.py — Employee Entry Request
# Dipindahkan dari legacy_api.py
import json
import frappe
from frappe import _


# =============================================================================
# HELPER FUNCTIONS (private)
# =============================================================================

def _get_employee_for_user(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _is_employee_entry_manager(user=None):
    roles = frappe.get_roles(user or frappe.session.user)
    return bool({"System Manager", "HR Manager", "Visitor Manager"} & set(roles))


def _get_employee_entry_fields():
    return [
        "name", "employee", "employee_name", "department", "purpose", "status",
        "check_in_time", "approved_by", "approved_at", "completed_at",
        "check_out_time", "rejected_reason", "modified",
    ]


def _get_open_employee_entry(employee):
    rows = frappe.get_all(
        "Employee Entry Request",
        filters={"employee": employee, "status": ["in", ["Pending Approval", "Approved", "Completed"]]},
        pluck="name",
        order_by="modified desc",
        limit_page_length=1,
    )
    return frappe.get_doc("Employee Entry Request", rows[0]) if rows else None


def _get_manageable_employee_entry(entry_id):
    if not entry_id or not frappe.db.exists("Employee Entry Request", entry_id):
        frappe.throw(_("Employee Entry Request tidak ditemukan"))
    doc = frappe.get_doc("Employee Entry Request", entry_id)
    if _is_employee_entry_manager():
        return doc
    employee = _get_employee_for_user()
    if employee and doc.employee == employee:
        return doc
    frappe.throw(_("Anda tidak memiliki akses untuk pengajuan ini"))


def _employee_has_field(fieldname):
    return frappe.get_meta("Employee").has_field(fieldname)


def _parse_employee_barcode(qr_data):
    if not qr_data:
        frappe.throw(_("Barcode karyawan tidak boleh kosong"))
    value = str(qr_data).strip()
    employee_code = value
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            employee_code = data.get("employee") or data.get("employee_id") or data.get("name") or data.get("code")
    except (json.JSONDecodeError, TypeError):
        employee_code = value
    if str(employee_code).upper().startswith("EMP:"):
        employee_code = str(employee_code).split(":", 1)[1].strip()
    if not employee_code:
        frappe.throw(_("Barcode karyawan tidak valid"))
    return employee_code


def _get_employee_from_barcode(qr_data):
    employee_code = _parse_employee_barcode(qr_data)
    if frappe.db.exists("Employee Entry Request", employee_code):
        entry_employee = frappe.db.get_value("Employee Entry Request", employee_code, "employee")
        if entry_employee:
            return entry_employee
    if frappe.db.exists("Employee", employee_code):
        return employee_code
    lookup_filters = []
    if _employee_has_field("attendance_device_id"):
        lookup_filters.append({"attendance_device_id": employee_code})
    if _employee_has_field("user_id"):
        lookup_filters.append({"user_id": employee_code})
    if _employee_has_field("employee_number"):
        lookup_filters.append({"employee_number": employee_code})
    for filters in lookup_filters:
        employee = frappe.db.get_value("Employee", filters, "name")
        if employee:
            return employee
    frappe.throw(_("Karyawan dengan kode {0} tidak ditemukan").format(employee_code))


def _parse_names(names):
    if isinstance(names, str):
        try:
            names = json.loads(names)
        except (json.JSONDecodeError, TypeError):
            names = [n.strip() for n in names.split(",") if n.strip()]
    return names or []


def _employee_entry_response(doc, message=None):
    return {
        "status": "success",
        "message": message,
        "entry": doc.name if doc else None,
        "entry_status": doc.status if doc else None,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_my_employee_barcode():
    """Generate QR barcode untuk karyawan yang sedang login."""
    import base64, io, qrcode, json
    employee = _get_employee_for_user()
    if not employee:
        frappe.throw(_("User login belum terhubung ke Employee"))
    emp = frappe.db.get_value("Employee", employee, ["name", "employee_name", "department"], as_dict=True)
    qr_data = json.dumps({"type": "employee_entry", "employee": emp.name})
    try:
        qr = qrcode.QRCode(version=1, box_size=8, border=3)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_image = "data:image/png;base64,{0}".format(base64.b64encode(buf.getvalue()).decode())
    except Exception:
        qr_image = None
    return {
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "barcode_text": "EMP:{0}".format(emp.name),
        "qr_data": qr_data,
        "qr_image": qr_image,
    }


@frappe.whitelist(allow_guest=False)
def get_employee_by_barcode(qr_data):
    """Ambil info karyawan dari scan barcode."""
    employee = _get_employee_from_barcode(qr_data)
    emp = frappe.db.get_value(
        "Employee", employee,
        ["name", "employee_name", "department", "status"],
        as_dict=True,
    )
    if not emp:
        return {"error": "Karyawan tidak ditemukan"}
    open_entry = _get_open_employee_entry(employee)
    return {
        "name": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "employee_status": emp.status,
        "barcode_text": "EMP:{0}".format(emp.name),
        "entry": open_entry.name if open_entry else None,
        "entry_status": open_entry.status if open_entry else None,
        "purpose": open_entry.purpose if open_entry else None,
        "check_in_time": str(open_entry.check_in_time) if open_entry and open_entry.check_in_time else None,
        "approved_at": str(open_entry.approved_at) if open_entry and open_entry.approved_at else None,
        "completed_at": str(open_entry.completed_at) if open_entry and open_entry.completed_at else None,
    }


@frappe.whitelist(allow_guest=False)
def scan_employee_entry_barcode(qr_data, action):
    """Scan barcode karyawan untuk check-in atau check-out."""
    employee = _get_employee_from_barcode(qr_data)
    emp_status = frappe.db.get_value("Employee", employee, "status")
    if emp_status != "Active":
        frappe.throw(_("Employee {0} tidak aktif").format(employee))
    open_entry = _get_open_employee_entry(employee)
    if action == "checkin":
        if open_entry:
            if open_entry.status == "Completed":
                frappe.throw(_("Karyawan sudah Completed. Gunakan mode Check Out."))
            return _employee_entry_response(
                open_entry,
                _("Pengajuan masuk sudah ada dengan status {0}.").format(open_entry.status),
            )
        doc = frappe.get_doc({
            "doctype": "Employee Entry Request",
            "employee": employee,
            "purpose": "Scan barcode security",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return _employee_entry_response(doc, _("Pengajuan check-in dibuat. Menunggu approval."))
    if action == "checkout":
        if not open_entry:
            frappe.throw(_("Tidak ada pengajuan yang menunggu check-out."))
        if open_entry.status != "Completed":
            frappe.throw(_("Belum bisa check-out. Status: {0}").format(open_entry.status))
        return open_entry.checkout()
    frappe.throw(_("Aksi tidak dikenali"))


@frappe.whitelist(allow_guest=False)
def create_employee_entry(purpose):
    """Buat pengajuan check-in karyawan baru."""
    employee = _get_employee_for_user()
    if not employee:
        frappe.throw(_("User login belum terhubung ke Employee."))
    if not purpose or not purpose.strip():
        frappe.throw(_("Keperluan / keterangan wajib diisi"))
    open_entry = _get_open_employee_entry(employee)
    if open_entry:
        frappe.throw(_(
            "Anda sudah memiliki pengajuan aktif dengan status {0}."
        ).format(open_entry.status))
    doc = frappe.get_doc({
        "doctype": "Employee Entry Request",
        "employee": employee,
        "purpose": purpose.strip(),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": "Pengajuan check-in berhasil dibuat.", "name": doc.name}


@frappe.whitelist(allow_guest=False)
def get_employee_entry_data():
    """Ambil semua data untuk halaman /employee-entry."""
    employee   = _get_employee_for_user()
    is_manager = _is_employee_entry_manager()
    fields     = _get_employee_entry_fields()
    if not is_manager and not employee:
        return {
            "employee": None, "is_manager": False,
            "mine": [], "pending": [], "active": [], "completed": [],
            "warning": "Akun Anda belum terhubung ke data Karyawan.",
        }
    mine = []
    if employee:
        mine = frappe.get_all(
            "Employee Entry Request",
            filters={"employee": employee},
            fields=fields, order_by="modified desc", limit_page_length=20,
        )
    pending = active = completed = []
    if is_manager:
        pending = frappe.get_all("Employee Entry Request", filters={"status": "Pending Approval"}, fields=fields, order_by="check_in_time asc")
        active  = frappe.get_all("Employee Entry Request", filters={"status": "Approved"}, fields=fields, order_by="approved_at asc")
        completed = frappe.get_all("Employee Entry Request", filters={"status": "Completed"}, fields=fields, order_by="completed_at asc")
    return {"employee": employee, "is_manager": is_manager, "mine": mine, "pending": pending, "active": active, "completed": completed}


@frappe.whitelist(allow_guest=False)
def employee_entry_action(entry_id, action, reason=""):
    """Lakukan aksi pada satu Employee Entry Request."""
    doc = _get_manageable_employee_entry(entry_id)
    if action == "approve":   return doc.approve()
    elif action == "reject":
        if not reason or not str(reason).strip():
            frappe.throw(_("Alasan penolakan wajib diisi"))
        return doc.reject(reason)
    elif action == "complete": return doc.complete()
    elif action == "checkout": return doc.checkout()
    else: frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def bulk_employee_entry_action(entry_ids, action, reason=""):
    """Lakukan aksi pada banyak Employee Entry Request sekaligus."""
    if not _is_employee_entry_manager():
        frappe.throw(_("Hanya HR Manager, Visitor Manager, atau System Manager yang dapat melakukan bulk action"))
    ids = _parse_names(entry_ids)
    if not ids:
        frappe.throw(_("Tidak ada entry yang dipilih"))
    results = []
    for entry_id in ids:
        try:
            result = employee_entry_action(entry_id, action, reason)
            results.append({"name": entry_id, "status": "success", "message": result.get("message") if result else "OK"})
        except Exception as exc:
            results.append({"name": entry_id, "status": "error", "message": str(exc)})
    berhasil = sum(1 for r in results if r["status"] == "success")
    gagal    = sum(1 for r in results if r["status"] == "error")
    return {"status": "success", "berhasil": berhasil, "gagal": gagal, "results": results}


@frappe.whitelist(allow_guest=False)
def search_employee_entry_candidates(keyword, limit=10):
    """Cari karyawan atau entry request berdasarkan keyword."""
    keyword = (keyword or "").strip()
    if len(keyword) < 2:
        return []
    try:
        limit = max(1, min(int(limit or 10), 20))
    except Exception:
        limit = 10
    results = []
    seen = set()
    for filters in [
        [{"name": ("like", f"%{keyword}%")}, {"status": "Active"}],
        [{"employee_name": ("like", f"%{keyword}%")}, {"status": "Active"}],
    ]:
        rows = frappe.get_all("Employee", filters=filters, fields=["name", "employee_name", "department"], limit_page_length=limit)
        for row in rows:
            key = f"EMP::{row.name}"
            if key in seen: continue
            seen.add(key)
            results.append({"value": row.name, "label": f"{row.name} — {row.employee_name or '-'}", "type": "employee", "employee": row.name, "employee_name": row.employee_name, "department": row.department})
            if len(results) >= limit: return results
    entry_rows = frappe.get_all("Employee Entry Request", filters=[["name", "like", f"%{keyword}%"]], fields=["name", "employee", "employee_name", "department", "status"], limit_page_length=limit)
    for row in entry_rows:
        key = f"ENTRY::{row.name}"
        if key in seen: continue
        seen.add(key)
        results.append({"value": row.name, "label": f"{row.name} — {row.employee or '-'} ({row.status or '-'})", "type": "entry_request", "entry_request": row.name, "employee": row.employee, "employee_name": row.employee_name, "department": row.department, "entry_status": row.status})
        if len(results) >= limit: break
    return results
