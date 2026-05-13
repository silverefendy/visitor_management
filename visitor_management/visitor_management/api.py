import frappe
from frappe import _
from frappe.utils import today, now_datetime
import json


def _get_employee_for_user(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _can_manage_visitor(visitor):
    user = frappe.session.user
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Visitor Manager" in roles:
        return True

    employee = _get_employee_for_user(user)
    return bool(employee and visitor.host_employee == employee)


def _get_manageable_visitor(visitor_id):
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))

    visitor = frappe.get_doc("Visitor", visitor_id)
    if not _can_manage_visitor(visitor):
        frappe.throw(_("Anda tidak memiliki akses untuk visitor ini"))

    return visitor


def _is_employee_entry_manager(user=None):
    roles = frappe.get_roles(user or frappe.session.user)
    return bool({"System Manager", "HR Manager", "Visitor Manager"} & set(roles))


def _get_employee_entry_fields():
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
    if not entry_id or not frappe.db.exists("Employee Entry Request", entry_id):
        frappe.throw(_("Employee Entry Request tidak ditemukan"))

    doc = frappe.get_doc("Employee Entry Request", entry_id)
    if _is_employee_entry_manager():
        return doc

    employee = _get_employee_for_user()
    if employee and doc.employee == employee:
        return doc

    frappe.throw(_("Anda tidak memiliki akses untuk pengajuan ini"))


def _parse_names(names):
    if isinstance(names, str):
        try:
            names = json.loads(names)
        except (json.JSONDecodeError, TypeError):
            names = [n.strip() for n in names.split(",") if n.strip()]
    return names or []


def _parse_qr_payload(qr_data):
    if not qr_data:
        return {}
    try:
        return json.loads(qr_data)
    except (json.JSONDecodeError, TypeError):
        return {"raw": qr_data.strip()}


@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action):
    """
    Endpoint utama untuk scanner QR di security post.
    action: 'checkin' atau 'checkout'
    """
    if not qr_data:
        frappe.throw(_("QR data tidak boleh kosong"))

    try:
        data = json.loads(qr_data)
    except (json.JSONDecodeError, TypeError):
        # Coba langsung sebagai visitor ID
        data = {"visitor_id": qr_data.strip()}

    visitor_id = data.get("visitor_id")
    if not visitor_id:
        frappe.throw(_("QR Code tidak valid - visitor ID tidak ditemukan"))

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
    """Ambil detail visitor dari QR data (untuk preview sebelum konfirmasi)"""
    try:
        data = json.loads(qr_data)
    except (json.JSONDecodeError, TypeError):
        data = {"visitor_id": qr_data.strip()}

    visitor_id = data.get("visitor_id")
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        return {"error": "Visitor tidak ditemukan"}

    v = frappe.get_doc("Visitor", visitor_id)
    return {
        "name": v.name,
        "visitor_name": v.visitor_name,
        "visitor_company": v.visitor_company or "-",
        "visitor_phone": v.visitor_phone,
        "host_employee_name": v.host_employee_name,
        "department": v.department or "-",
        "visit_purpose": v.visit_purpose,
        "status": v.status,
        "check_in_time": str(v.check_in_time) if v.check_in_time else None,
        "check_out_time": str(v.check_out_time) if v.check_out_time else None,
        "id_type": v.id_type,
        "id_number": v.id_number,
        "qr_code_image": v.qr_code_image,
    }


@frappe.whitelist(allow_guest=False)
def get_employee_by_qr(qr_data):
    data = _parse_qr_payload(qr_data)
    employee_id = data.get("employee") or data.get("employee_id") or data.get("raw")
    if not employee_id or not frappe.db.exists("Employee", employee_id):
        return {"error": "Employee tidak ditemukan"}

    employee = frappe.db.get_value(
        "Employee",
        employee_id,
        ["name", "employee_name", "department", "status", "company"],
        as_dict=True,
    )
    if employee.status != "Active":
        return {"error": "Employee tidak aktif"}

    active_entry = frappe.get_all(
        "Employee Entry Request",
        filters={"employee": employee_id, "status": ["in", ["Pending Approval", "Approved", "Completed"]]},
        fields=_get_employee_entry_fields(),
        order_by="modified desc",
        limit_page_length=1,
    )

    return {
        "name": employee.name,
        "employee_name": employee.employee_name,
        "department": employee.department,
        "company": employee.company,
        "status": employee.status,
        "active_entry": active_entry[0] if active_entry else None,
    }


@frappe.whitelist(allow_guest=False)
def scan_employee_entry_action(qr_data, action, purpose="Security scan"):
    data = _parse_qr_payload(qr_data)
    employee_id = data.get("employee") or data.get("employee_id") or data.get("raw")
    if not employee_id or not frappe.db.exists("Employee", employee_id):
        frappe.throw(_("Employee tidak ditemukan"))

    emp_status = frappe.db.get_value("Employee", employee_id, "status")
    if emp_status != "Active":
        frappe.throw(_("Employee tidak aktif"))

    if action == "checkin":
        existing = frappe.get_all(
            "Employee Entry Request",
            filters={"employee": employee_id, "status": ["in", ["Pending Approval", "Approved", "Completed"]]},
            fields=["name", "status"],
            order_by="modified desc",
            limit_page_length=1,
        )
        if existing:
            frappe.throw(_("Employee masih memiliki entry aktif: {0} ({1})").format(existing[0].name, existing[0].status))

        doc = frappe.get_doc({
            "doctype": "Employee Entry Request",
            "employee": employee_id,
            "purpose": purpose or "Security scan",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success", "message": "Pengajuan employee entry dibuat. Menunggu approval HRD.", "name": doc.name}

    if action == "checkout":
        rows = frappe.get_all(
            "Employee Entry Request",
            filters={"employee": employee_id, "status": "Completed"},
            fields=["name"],
            order_by="modified desc",
            limit_page_length=1,
        )
        if not rows:
            frappe.throw(_("Tidak ada employee entry berstatus Completed untuk checkout"))
        doc = frappe.get_doc("Employee Entry Request", rows[0].name)
        return doc.checkout()

    frappe.throw(_("Aksi tidak dikenali: {0}").format(action))


@frappe.whitelist(allow_guest=False)
def get_dashboard_data():
    """Data untuk dashboard VMS hari ini"""
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

    # Visitor aktif saat ini (masih di dalam gedung)
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

    waiting = len([v for v in active_visitors if v.status == "Awaiting Approval"])
    checked_in = len([v for v in active_visitors if v.status in ["Checked In", "Approved"]])
    completed = len(pending_checkout)
    rejected = len(rejected_visitors)
    checked_out = frappe.db.count("Visitor", filters=activity_filters + [["status", "=", "Checked Out"]])
    total = waiting + checked_in + completed + checked_out + rejected

    return {
        "stats": {
            "total_today": total,
            "checked_in": checked_in,
            "completed": completed,
            "checked_out": checked_out,
            "waiting_approval": waiting,
            "rejected": rejected,
        },
        "active_visitors": active_visitors,
        "pending_checkout": pending_checkout,
        "rejected_visitors": rejected_visitors,
    }


@frappe.whitelist()
def employee_pending_approvals():
    """Ambil daftar visitor yang menunggu approval dari karyawan yang login"""
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        return []

    return frappe.get_all(
        "Visitor",
        filters={
            "host_employee": employee,
            "status": "Awaiting Approval",
        },
        fields=["name", "visitor_name", "visitor_company", "visit_purpose",
                "check_in_time", "id_type", "id_number"],
        order_by="check_in_time asc",
    )


@frappe.whitelist(allow_guest=False)
def employee_approval_data():
    """Data approval untuk employee yang sedang login."""
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_manager = "System Manager" in roles or "Visitor Manager" in roles
    employee = _get_employee_for_user(user)

    if not is_manager and not employee:
        return {
            "user": user,
            "employee": None,
            "pending": [],
            "active": [],
            "message": "User login belum terhubung ke Employee.",
        }

    base_filters = {}
    if not is_manager:
        base_filters["host_employee"] = employee

    fields = [
        "name",
        "visitor_name",
        "visitor_company",
        "visitor_phone",
        "visit_purpose",
        "host_employee_name",
        "department",
        "status",
        "check_in_time",
        "approved_at",
        "id_type",
        "id_number",
    ]

    pending_filters = dict(base_filters)
    pending_filters["status"] = "Awaiting Approval"

    active_filters = dict(base_filters)
    active_filters["status"] = "Approved"

    return {
        "user": user,
        "employee": employee,
        "is_manager": is_manager,
        "pending": frappe.get_all(
            "Visitor",
            filters=pending_filters,
            fields=fields,
            order_by="check_in_time asc",
        ),
        "active": frappe.get_all(
            "Visitor",
            filters=active_filters,
            fields=fields,
            order_by="approved_at asc, check_in_time asc",
        ),
    }


@frappe.whitelist(allow_guest=False)
def approve_visitor(visitor_id):
    visitor = _get_manageable_visitor(visitor_id)
    result = visitor.approve_visit()
    frappe.publish_realtime(
        "vms_visitor_approved",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name},
        after_commit=True,
    )
    return result


@frappe.whitelist(allow_guest=False)
def reject_visitor(visitor_id, reason=""):
    visitor = _get_manageable_visitor(visitor_id)
    result = visitor.reject_visit(reason)
    frappe.publish_realtime(
        "vms_visitor_rejected",
        {"visitor": visitor.name, "visitor_name": visitor.visitor_name, "reason": reason},
        after_commit=True,
    )
    return result


@frappe.whitelist(allow_guest=False)
def complete_visit(visitor_id):
    visitor = _get_manageable_visitor(visitor_id)
    return visitor.end_visit()


@frappe.whitelist(allow_guest=False)
def create_employee_entry(purpose):
    employee = _get_employee_for_user()
    if not employee:
        frappe.throw(_("User login belum terhubung ke Employee"))
    if not purpose:
        frappe.throw(_("Keperluan / keterangan wajib diisi"))

    doc = frappe.get_doc({
        "doctype": "Employee Entry Request",
        "employee": employee,
        "purpose": purpose,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": "Pengajuan check-in karyawan dibuat.", "name": doc.name}


@frappe.whitelist(allow_guest=False)
def get_employee_entry_data():
    employee = _get_employee_for_user()
    is_manager = _is_employee_entry_manager()
    fields = _get_employee_entry_fields()

    if not is_manager and not employee:
        return {
            "employee": None,
            "is_manager": False,
            "mine": [],
            "pending": [],
            "active": [],
            "completed": [],
            "message": "User login belum terhubung ke Employee.",
        }

    mine = []
    if employee:
        mine = frappe.get_all(
            "Employee Entry Request",
            filters={"employee": employee},
            fields=fields,
            order_by="modified desc",
            limit_page_length=20,
        )

    pending = []
    active = []
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
        "employee": employee,
        "is_manager": is_manager,
        "mine": mine,
        "pending": pending,
        "active": active,
        "completed": completed,
    }


@frappe.whitelist(allow_guest=False)
def employee_entry_action(entry_id, action, reason=""):
    doc = _get_manageable_employee_entry(entry_id)
    if action == "approve":
        return doc.approve()
    if action == "reject":
        return doc.reject(reason)
    if action == "complete":
        return doc.complete()
    if action == "checkout":
        return doc.checkout()
    frappe.throw(_("Aksi tidak dikenali"))


@frappe.whitelist(allow_guest=False)
def bulk_employee_entry_action(entry_ids, action, reason=""):
    if not _is_employee_entry_manager():
        frappe.throw(_("Hanya HR Manager, Visitor Manager, atau System Manager yang dapat memproses bulk action"))

    results = []
    for entry_id in _parse_names(entry_ids):
        try:
            result = employee_entry_action(entry_id, action, reason)
            results.append({"name": entry_id, "status": "success", "message": result.get("message")})
        except Exception as exc:
            results.append({"name": entry_id, "status": "error", "message": str(exc)})

    return {"status": "success", "results": results}


@frappe.whitelist()
def print_visitor_badge(visitor_id):
    """Generate HTML badge untuk di-print"""
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))

    v = frappe.get_doc("Visitor", visitor_id)
    site_name = frappe.db.get_single_value("System Settings", "site_name") or "Perusahaan"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Visitor Badge - {v.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .badge {{
                width: 85mm; height: 125mm;
                border: 2px solid #2e4057;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                page-break-inside: avoid;
            }}
            .badge-header {{
                background: #2e4057;
                color: white;
                margin: -16px -16px 12px -16px;
                padding: 10px;
                border-radius: 6px 6px 0 0;
                font-size: 14px;
                font-weight: bold;
            }}
            .visitor-type {{
                background: #e74c3c;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                display: inline-block;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .visitor-name {{ font-size: 20px; font-weight: bold; color: #2e4057; margin: 8px 0; }}
            .visitor-company {{ font-size: 13px; color: #666; margin-bottom: 10px; }}
            .qr-image {{ width: 100px; height: 100px; margin: 8px auto; display: block; }}
            .info-table {{ width: 100%; font-size: 11px; text-align: left; margin-top: 8px; }}
            .info-table td {{ padding: 2px 4px; }}
            .info-label {{ color: #888; width: 40%; }}
            .visitor-id {{ font-size: 10px; color: #aaa; margin-top: 8px; }}
            @media print {{
                body {{ margin: 0; padding: 0; }}
                button {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="badge">
            <div class="badge-header">{site_name}</div>
            <div class="visitor-type">VISITOR</div>
            <div class="visitor-name">{v.visitor_name}</div>
            <div class="visitor-company">{v.visitor_company or ''}</div>
            {'<img class="qr-image" src="' + v.qr_code_image + '" alt="QR Code">' if v.qr_code_image else ''}
            <table class="info-table">
                <tr>
                    <td class="info-label">Tujuan:</td>
                    <td>{v.host_employee_name} ({v.department or '-'})</td>
                </tr>
                <tr>
                    <td class="info-label">Keperluan:</td>
                    <td>{v.visit_purpose[:40] + '...' if len(v.visit_purpose) > 40 else v.visit_purpose}</td>
                </tr>
                <tr>
                    <td class="info-label">ID:</td>
                    <td>{v.id_type}: {v.id_number}</td>
                </tr>
            </table>
            <div class="visitor-id">{v.name}</div>
        </div>
        <br>
        <button onclick="window.print()">🖨 Print Badge</button>
    </body>
    </html>
    """

    frappe.response["type"] = "page"
    frappe.response["route"] = "print-visitor-badge"

    # Return sebagai file download / tampil di browser
    from frappe.respond_as_websocket import RespondAsWebsocket
    frappe.local.response["content_type"] = "text/html"
    frappe.local.response["filename"] = f"badge_{visitor_id}.html"

    return html


@frappe.whitelist()
def get_visitor_report(from_date, to_date, department=None, status=None):
    """Laporan visitor untuk periode tertentu"""
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

    # Hitung durasi untuk setiap visitor
    for v in visitors:
        if v.check_in_time and v.check_out_time:
            delta = v.check_out_time - v.check_in_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            v["duration"] = f"{hours}j {minutes}m"
        else:
            v["duration"] = "-"

    return visitors
