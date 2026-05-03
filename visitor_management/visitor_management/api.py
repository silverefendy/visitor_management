import frappe
from frappe import _
from frappe.utils import today, now_datetime
import json


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
def get_dashboard_data():
    """Data untuk dashboard VMS hari ini"""
    base_filters = [["creation", ">=", today()]]

    total     = frappe.db.count("Visitor", filters=base_filters)
    checked_in = frappe.db.count("Visitor", filters=base_filters + [["status", "in", ["Checked In", "Approved"]]])
    completed  = frappe.db.count("Visitor", filters=base_filters + [["status", "=", "Completed"]])
    checked_out = frappe.db.count("Visitor", filters=base_filters + [["status", "=", "Checked Out"]])
    waiting    = frappe.db.count("Visitor", filters=base_filters + [["status", "=", "Awaiting Approval"]])
    rejected   = frappe.db.count("Visitor", filters=base_filters + [["status", "=", "Rejected"]])

    # Visitor aktif saat ini (masih di dalam gedung)
    active_visitors = frappe.get_all(
        "Visitor",
        filters=[["status", "in", ["Checked In", "Approved", "Awaiting Approval"]]],
        fields=["name", "visitor_name", "visitor_company", "host_employee_name",
                "department", "status", "check_in_time"],
        order_by="check_in_time asc",
    )

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
