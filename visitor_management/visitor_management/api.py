# =============================================================================
# api.py — Visitor Management
# Lokasi file ini di server:
#   /home/frappe/frappe-bench/apps/visitor_management/visitor_management/visitor_management/api.py
#
# Setelah upload/edit file ini, jalankan di server:
#   bench clear-cache && bench restart
# =============================================================================

import base64
import io
import json

import frappe
import qrcode
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime, today

from visitor_management.visitor_management.services.qr_service import parse_visitor_qr
from visitor_management.visitor_management.services.settings_service import get_qr_settings, get_visitor_settings
from visitor_management.visitor_management.services.visitor_service import check_in, check_out

# =============================================================================
# HELPER FUNCTIONS (private — tidak bisa dipanggil dari browser)
# Fungsi dengan awalan _ adalah helper internal, tidak perlu @whitelist
# =============================================================================

@frappe.whitelist(allow_guest=False)
def get_csrf_token():
    """Return a fresh CSRF token for custom web pages."""
    return frappe.sessions.get_csrf_token()


def _employee_barcode_payload(employee):
    return json.dumps({"type": "employee_entry", "employee": employee})


def _qr_data_uri(data):
    try:
        qr = qrcode.QRCode(version=1, box_size=8, border=3)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64,{0}".format(base64.b64encode(buf.getvalue()).decode())
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Employee Barcode Generate Error")
        return None


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


def _employee_has_field(fieldname):
    return frappe.get_meta("Employee").has_field(fieldname)


def _get_employee_from_barcode(qr_data):
    employee_code = _parse_employee_barcode(qr_data)

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


def _get_open_employee_entry(employee):
    open_statuses = ["Pending Approval", "Approved", "Completed"]
    rows = frappe.get_all(
        "Employee Entry Request",
        filters={"employee": employee, "status": ["in", open_statuses]},
        pluck="name",
        order_by="modified desc",
        limit_page_length=1,
    )
    return frappe.get_doc("Employee Entry Request", rows[0]) if rows else None


def _employee_entry_response(doc, message=None):
    return {
        "status": "success",
        "message": message,
        "entry": doc.name if doc else None,
        "entry_status": doc.status if doc else None,
    }


def _get_employee_for_user(user=None):
    """Cari Employee record yang terhubung ke user login."""
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _can_manage_visitor(visitor):
    """Cek apakah user login boleh kelola visitor ini."""
    user = frappe.session.user
    roles = frappe.get_roles(user)

    # System Manager dan VMS Manager bisa kelola semua visitor
    if "System Manager" in roles or "VMS Manager" in roles:
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


def _standard_success(message, **kwargs):
    data = {
        "success": True,
        "status": "success",
        "message": message,
    }
    data.update(kwargs)
    return data


def _parse_scan_payload(qr_code):
    value = str(qr_code or "").strip()
    payload = None
    if value:
        try:
            parsed = json.loads(value)
            payload = parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            payload = None
    return value, payload or {}


def _looks_like_employee_scan(raw_value, payload):
    if payload.get("type") in {"employee_entry", "employee", "employee_checkin"}:
        return True
    if payload.get("employee") or payload.get("employee_id"):
        return True
    return raw_value.upper().startswith("EMP:")


def _find_employee_from_scan(raw_value, payload=None):
    payload = payload or {}
    candidates = [
        payload.get("employee"),
        payload.get("employee_id"),
        payload.get("name") if payload.get("type") in {"employee", "employee_entry", "employee_checkin"} else None,
        raw_value,
    ]

    for candidate in candidates:
        if not candidate:
            continue
        employee_code = str(candidate).strip()
        if employee_code.upper().startswith("EMP:"):
            employee_code = employee_code.split(":", 1)[1].strip()
        if not employee_code:
            continue
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
    return None



def _scan_action_label(next_action, entity_type=None):
    labels = {
        "CHECK_IN": _("Check In Visitor"),
        "CHECK_OUT": _("Check Out Visitor"),
        "EMPLOYEE_CHECK_IN": _("Employee Check In"),
        "EMPLOYEE_CHECK_OUT": _("Employee Check Out"),
        "WAIT_FOR_APPROVAL": _("Menunggu Approval"),
        "WAIT_INSIDE": _("Tamu masih di area"),
        "INVALID": _("QR Tidak Berlaku"),
    }
    return labels.get(next_action, next_action or _("Tidak ada aksi"))


def _scan_confirmation_title(next_action, entity_type=None):
    titles = {
        "CHECK_IN": _("Check In Visitor?"),
        "CHECK_OUT": _("Check Out Visitor?"),
        "EMPLOYEE_CHECK_IN": _("Employee Check In?"),
        "EMPLOYEE_CHECK_OUT": _("Employee Check Out?"),
    }
    return titles.get(
        next_action,
        _("Konfirmasi Scan Karyawan") if entity_type == "EMPLOYEE" else _("Konfirmasi Scan Tamu"),
    )

def _visitor_scan_response(visitor, next_action, scan_status, message, qr_code=None):
    workflow_state = visitor.get("workflow_state") if visitor.meta.has_field("workflow_state") else visitor.status
    confirmation_required = next_action in ["CHECK_IN", "CHECK_OUT"]
    return _standard_success(
        message,
        entity_type="VISITOR",
        visitor=visitor.name,
        visitor_id=visitor.name,
        qr_code=qr_code,
        visitor_name=visitor.visitor_name,
        company=visitor.visitor_company,
        visitor_company=visitor.visitor_company,
        employee_name=visitor.host_employee_name,
        host_employee_name=visitor.host_employee_name,
        purpose=visitor.visit_purpose,
        visit_purpose=visitor.visit_purpose,
        current_status=visitor.status,
        status=scan_status,
        visitor_status=visitor.status,
        workflow_state=workflow_state,
        next_action=next_action,
        action_label=_scan_action_label(next_action, "VISITOR"),
        confirmation_title=_scan_confirmation_title(next_action, "VISITOR"),
        confirmation_required=confirmation_required,
        requires_confirmation=confirmation_required,
    )


def _employee_scan_response(employee, next_action, scan_status, message, entry=None, qr_code=None):
    emp = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "employee_name", "department", "status"],
        as_dict=True,
    )
    return _standard_success(
        message,
        entity_type="EMPLOYEE",
        employee=employee,
        employee_id=employee,
        qr_code=qr_code,
        employee_name=emp.employee_name if emp else None,
        department=emp.department if emp else None,
        employee_status=emp.status if emp else None,
        entry=entry.name if entry else None,
        entry_id=entry.name if entry else None,
        entry_status=entry.status if entry else None,
        current_status=entry.status if entry else "Outside",
        status=scan_status,
        next_action=next_action,
        action_label=_scan_action_label(next_action, "EMPLOYEE"),
        confirmation_title=_scan_confirmation_title(next_action, "EMPLOYEE"),
        confirmation_required=next_action in ["EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"],
        requires_confirmation=next_action in ["EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"],
    )


def _resolve_employee_scan(qr_code, employee=None):
    employee = employee or _get_employee_from_barcode(qr_code)
    frappe.logger("visitor_management").info("Employee scan detected", extra={"employee": employee})
    emp_status = frappe.db.get_value("Employee", employee, "status")
    if emp_status != "Active":
        frappe.throw(_("Employee {0} tidak aktif").format(employee))

    open_entry = _get_open_employee_entry(employee)
    if not open_entry:
        return _employee_scan_response(
            employee,
            "EMPLOYEE_CHECK_IN",
            "NO_ACTIVE_ENTRY",
            _("Karyawan terdeteksi. Pengajuan check-in dapat dibuat."),
            qr_code=qr_code,
        )
    if open_entry.status == "Completed":
        return _employee_scan_response(
            employee,
            "EMPLOYEE_CHECK_OUT",
            "READY_FOR_CHECK_OUT",
            _("Karyawan sudah selesai dan siap check-out."),
            entry=open_entry,
            qr_code=qr_code,
        )
    return _employee_scan_response(
        employee,
        "EMPLOYEE_CHECK_IN",
        open_entry.status,
        _("Pengajuan karyawan masih aktif dengan status {0}.").format(open_entry.status),
        entry=open_entry,
        qr_code=qr_code,
    )


def get_active_visit(visitor):
    if get_visitor_settings("allow_multiple_active_visits", 0):
        return None
    active_statuses = ["Awaiting Approval", "Approved", "Checked In", "Completed"]
    if visitor.status in active_statuses:
        return visitor

    if not visitor.id_number:
        return None

    active_name = frappe.db.exists(
        "Visitor",
        {
            "id_number": visitor.id_number,
            "status": ["in", active_statuses],
            "name": ["!=", visitor.name],
        },
    )
    return frappe.get_doc("Visitor", active_name) if active_name else None



def _is_visitor_qr_expired(visitor):
    if not get_qr_settings("validate_qr_expiry", 0):
        return False
    expiry_hours = int(get_qr_settings("qr_expiry_duration", 24) or 24)
    base_time = visitor.get("creation") or visitor.get("check_in_time")
    if not base_time:
        return False
    return now_datetime() > add_to_date(get_datetime(base_time), hours=expiry_hours)

def _resolve_visitor_scan(qr_code):
    """Resolve visitor QR state without changing the database.

    Visitor business flow is intentionally linear:
    Registered --security check-in--> Awaiting Approval --host approve-->
    Approved --host complete--> Completed --security check-out--> Checked Out.
    """
    visitor_id = parse_visitor_qr(qr_code)
    frappe.logger("visitor_management").info("Visitor scan detected", extra={"visitor": visitor_id})
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))

    visitor = frappe.get_doc("Visitor", visitor_id)
    active_visit = get_active_visit(visitor)

    if active_visit and active_visit.name != visitor.name:
        frappe.throw(_("Visitor dengan ID yang sama masih aktif: {0}").format(active_visit.name))

    if _is_visitor_qr_expired(visitor):
        return _visitor_scan_response(
            visitor,
            "INVALID",
            "EXPIRED",
            _("QR sudah kedaluwarsa sesuai QR Settings."),
            qr_code=qr_code,
        )

    status = visitor.status
    if status == "Registered":
        return _visitor_scan_response(
            visitor,
            "CHECK_IN",
            "REGISTERED",
            _("Visitor terdaftar. Konfirmasi check-in visitor."),
            qr_code=qr_code,
        )
    if status == "Awaiting Approval":
        return _visitor_scan_response(
            visitor,
            "WAIT_FOR_APPROVAL",
            "AWAITING_APPROVAL",
            _("Visitor masih menunggu approval host."),
            qr_code=qr_code,
        )
    if status in ["Approved", "Checked In"]:
        return _visitor_scan_response(
            visitor,
            "CHECK_OUT",
            status.upper().replace(" ", "_"),
            _("Visitor sudah berada di area. Konfirmasi check-out visitor."),
            qr_code=qr_code,
        )
    if status == "Completed":
        return _visitor_scan_response(
            visitor,
            "CHECK_OUT",
            "COMPLETED",
            _("Check Out Visitor?"),
            qr_code=qr_code,
        )
    if status == "Checked Out":
        return _visitor_scan_response(
            visitor,
            "INVALID",
            "CHECKED_OUT",
            _("QR sudah tidak berlaku. Visitor sudah check-out."),
            qr_code=qr_code,
        )
    if status in ["Rejected", "Cancelled", "Archived"]:
        return _visitor_scan_response(
            visitor,
            "INVALID",
            status,
            _("QR belum dapat digunakan. Status saat ini: {0}.").format(status),
            qr_code=qr_code,
        )

    frappe.throw(_("Status visitor tidak dapat diproses: {0}").format(status))


def _execute_resolved_scan(qr_code, resolved, gate=None, device_id=None):
    next_action = resolved.get("next_action")
    if next_action == "CHECK_IN":
        return scan_qr_action(qr_data=qr_code, action="checkin", gate=gate, device_id=device_id)
    if next_action == "CHECK_OUT":
        return scan_qr_action(qr_data=qr_code, action="checkout", gate=gate, device_id=device_id)
    if next_action == "WAIT_INSIDE":
        frappe.throw(resolved.get("message") or _("Tamu masih di area."))
    if next_action == "INVALID":
        frappe.throw(resolved.get("message") or _("QR tidak dapat digunakan."))
    if next_action == "EMPLOYEE_CHECK_IN":
        return scan_employee_entry_barcode(qr_data=qr_code, action="checkin")
    if next_action == "EMPLOYEE_CHECK_OUT":
        return scan_employee_entry_barcode(qr_data=qr_code, action="checkout")
    frappe.throw(_("Scan belum bisa diproses otomatis. Status: {0}").format(resolved.get("status")))


def _is_employee_entry_manager(user=None):
    """
    Cek apakah user adalah manager yang boleh approve/reject Employee Entry.
    Tambahkan nama Role di sini jika ingin memberi akses ke role lain.
    Contoh: tambah "Visitor Approver" jika ada role tersebut.
    """
    roles = frappe.get_roles(user or frappe.session.user)
    return bool({"System Manager", "HR Manager", "VMS Manager"} & set(roles))


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
def resolve_scan_action(qr_code=None, qr_data=None):
    """Resolve the next scan action without mutating data. Safe for mobile preview."""
    scan_value = qr_code or qr_data
    raw_value, payload = _parse_scan_payload(scan_value)
    if not raw_value:
        frappe.throw(_("Data scan tidak boleh kosong"))

    try:
        employee = _find_employee_from_scan(raw_value, payload)
        if employee or _looks_like_employee_scan(raw_value, payload):
            resolved = _resolve_employee_scan(scan_value, employee=employee)
        else:
            resolved = _resolve_visitor_scan(scan_value)
        frappe.logger("visitor_management").info(
            "Scan resolved",
            extra={
                "entity_type": resolved.get("entity_type"),
                "next_action": resolved.get("next_action"),
                "status": resolved.get("status"),
            },
        )
        return resolved
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="VMS Resolve Scan Error")
        raise


@frappe.whitelist(allow_guest=False)
def scan_qr(qr_code=None, qr_data=None, action="auto", gate=None, device_id=None):
    """Compatibility wrapper that only resolves scans.

    This endpoint is intentionally non-mutating for production safety. Legacy
    clients that still pass action=checkin/checkOut receive the backend-resolved
    ``next_action`` and must call execute_scan_action only after user
    confirmation.
    """
    scan_value = qr_code or qr_data
    resolved = resolve_scan_action(qr_code=scan_value)
    normalized_action = str(action or "auto").strip()
    if normalized_action.lower() not in {"auto", "resolve", "preview", ""}:
        resolved["legacy_action_ignored"] = normalized_action
        resolved["message"] = resolved.get("message") or _("Konfirmasi diperlukan sebelum menjalankan aksi scan.")
    return resolved


@frappe.whitelist(allow_guest=False)
def execute_scan_action(qr_code=None, qr_data=None, action=None, gate=None, device_id=None):
    """Execute a previously resolved scan action after frontend confirmation."""
    scan_value = qr_code or qr_data
    confirmed_action = str(action or "").strip().upper()
    if not confirmed_action:
        frappe.throw(_("Aksi konfirmasi wajib diisi"))

    valid_actions = {"CHECK_IN", "CHECK_OUT", "EMPLOYEE_CHECK_IN", "EMPLOYEE_CHECK_OUT"}
    if confirmed_action not in valid_actions:
        frappe.throw(_("Aksi scan tidak dikenali: {0}").format(action))

    resolved = resolve_scan_action(qr_code=scan_value)
    expected_action = resolved.get("next_action")
    if expected_action in {"INVALID", "WAIT_FOR_APPROVAL", "WAIT_INSIDE"}:
        frappe.throw(resolved.get("message") or _("Scan belum dapat diproses."))
    if expected_action != confirmed_action:
        frappe.throw(_("Aksi tidak sesuai. Status terbaru membutuhkan {0}, bukan {1}.").format(expected_action, confirmed_action))

    frappe.logger("visitor_management").info(
        "Executing confirmed scan action",
        extra={
            "entity_type": resolved.get("entity_type"),
            "action": confirmed_action,
            "status": resolved.get("status"),
        },
    )
    result = _execute_resolved_scan(scan_value, resolved, gate=gate, device_id=device_id)
    result.update({
        "confirmed_action": confirmed_action,
        "entity_type": resolved.get("entity_type"),
    })
    return result


@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action, gate=None, device_id=None):
    """Endpoint scanner: frontend kirim hasil scan, backend validasi & proses aksi."""
    visitor_id = parse_visitor_qr(qr_data)

    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))

    visitor = frappe.get_doc("Visitor", visitor_id)

    if action == "checkin":
        return check_in(visitor, gate=gate, device_id=device_id)
    if action == "checkout":
        return check_out(visitor, gate=gate, device_id=device_id)

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
        filters=[*activity_filters, ["status", "=", "Rejected"]],
        fields=dashboard_fields,
        order_by="modified desc",
    )

    waiting    = len([v for v in active_visitors if v.status == "Awaiting Approval"])
    checked_in = len([v for v in active_visitors if v.status in ["Checked In", "Approved"]])
    completed  = len(pending_checkout)
    rejected   = len(rejected_visitors)
    checked_out = frappe.db.count(
        "Visitor", filters=[*activity_filters, ["status", "=", "Checked Out"]]
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
    is_manager = "System Manager" in roles or "VMS Manager" in roles
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
    active_filters  = {**base_filters, "status": ["in", ["Approved", "Checked In"]]}

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
    result = visitor.end_visit()
    frappe.publish_realtime(
        "vms_visitor_completed",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name},
        after_commit=True,
    )
    return result

@frappe.whitelist(allow_guest=False)
def get_my_employee_barcode():
    employee = _get_employee_for_user()
    if not employee:
        frappe.throw(_("User login belum terhubung ke Employee"))

    emp = frappe.db.get_value("Employee", employee, ["name", "employee_name", "department"], as_dict=True)
    qr_data = _employee_barcode_payload(emp.name)
    return {
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "barcode_text": "EMP:{0}".format(emp.name),
        "qr_data": qr_data,
        "qr_image": _qr_data_uri(qr_data),
    }


@frappe.whitelist(allow_guest=False)
def get_employee_by_barcode(qr_data):
    employee = _get_employee_from_barcode(qr_data)
    emp = frappe.db.get_value(
        "Employee",
        employee,
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
    employee = _get_employee_from_barcode(qr_data)
    emp_status = frappe.db.get_value("Employee", employee, "status")
    if emp_status != "Active":
        frappe.throw(_("Employee {0} tidak aktif").format(employee))

    open_entry = _get_open_employee_entry(employee)
    if action == "checkin":
        if open_entry:
            if open_entry.status == "Completed":
                frappe.throw(_("Karyawan sudah Completed. Gunakan mode Check Out untuk scan pulang."))
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
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return _employee_entry_response(doc, _("Pengajuan check-in karyawan dibuat. Menunggu approval."))

    if action == "checkout":
        if not open_entry:
            frappe.throw(_("Tidak ada pengajuan karyawan yang menunggu check-out."))
        if open_entry.status != "Completed":
            frappe.throw(_("Belum bisa check-out. Status saat ini: {0}").format(open_entry.status))
        result = open_entry.checkout()
        open_entry.save(ignore_permissions=True)
        frappe.db.commit()
        return result

    frappe.throw(_("Aksi tidak dikenali"))



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
            "Hanya HR Manager, VMS Manager, atau System Manager "
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
