# visitor_api.py — Visitor QR, Badge, CSRF
import frappe
from frappe import _
from visitor_management.visitor_management.utils.qr_utils import parse_qr_payload


@frappe.whitelist(allow_guest=False)
def get_csrf_token():
    """Return a fresh CSRF token untuk custom web pages."""
    return frappe.sessions.get_csrf_token()


@frappe.whitelist(allow_guest=False)
def get_visitor_by_qr(qr_data):
    """Ambil data visitor dari scan QR code."""
    payload = parse_qr_payload(qr_data)
    visitor_id = payload.get("visitor_id") or payload.get("value")
    if not visitor_id or not frappe.db.exists("Visitor", visitor_id):
        return {"error": "Visitor tidak ditemukan"}
    return frappe.db.get_value(
        "Visitor", visitor_id,
        ["name", "visitor_name", "visitor_company", "visitor_phone",
         "host_employee_name", "department", "visit_purpose", "status",
         "check_in_time", "check_out_time", "id_type", "id_number", "qr_code_image"],
        as_dict=True,
    )


@frappe.whitelist(allow_guest=False)
def print_visitor_badge(visitor_id):
    """Generate halaman HTML badge visitor untuk di-print."""
    if not frappe.db.exists("Visitor", visitor_id):
        frappe.throw(_("Visitor tidak ditemukan"))
    v = frappe.get_doc("Visitor", visitor_id)
    site_name = frappe.db.get_single_value("System Settings", "site_name") or "Perusahaan"
    purpose = v.visit_purpose or ""
    purpose_display = (purpose[:50] + "...") if len(purpose) > 50 else purpose
    qr_img = f'<img class="qr" src="{v.qr_code_image}" alt="QR">' if v.qr_code_image else ""
    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Visitor Badge — {v.name}</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f0f0f0; margin: 0; padding: 20px; }}
  .badge {{ width: 85mm; min-height: 120mm; background: white; border: 2px solid #23405d; border-radius: 10px; margin: 0 auto; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,.15); }}
  .badge-header {{ background: #23405d; color: white; padding: 12px 16px; text-align: center; font-size: 15px; font-weight: bold; letter-spacing: 1px; }}
  .badge-body {{ padding: 14px 16px; text-align: center; }}
  .label-visitor {{ display: inline-block; background: #e74c3c; color: white; padding: 3px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px; }}
  .visitor-name {{ font-size: 20px; font-weight: bold; color: #23405d; margin: 6px 0 2px; }}
  .visitor-company {{ font-size: 13px; color: #666; margin-bottom: 10px; }}
  .qr {{ width: 90px; height: 90px; margin: 6px auto; display: block; }}
  table {{ width: 100%; font-size: 11px; text-align: left; margin-top: 10px; border-collapse: collapse; }}
  td {{ padding: 3px 4px; vertical-align: top; }}
  .lbl {{ color: #888; width: 38%; white-space: nowrap; }}
  .badge-footer {{ background: #f5f7fa; border-top: 1px solid #e0e4ea; padding: 6px 16px; text-align: center; font-size: 10px; color: #aaa; }}
  .btn-print {{ display: block; margin: 20px auto; padding: 10px 28px; background: #23405d; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: bold; cursor: pointer; }}
  @media print {{ body {{ background: white; padding: 0; }} .btn-print {{ display: none; }} }}
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
        <tr><td class="lbl">Menemui</td><td>{v.host_employee_name} ({v.department or "-"})</td></tr>
        <tr><td class="lbl">Keperluan</td><td>{purpose_display}</td></tr>
        <tr><td class="lbl">Identitas</td><td>{v.id_type}: {v.id_number}</td></tr>
        <tr><td class="lbl">Check In</td><td>{str(v.check_in_time)[:16] if v.check_in_time else "-"}</td></tr>
      </table>
    </div>
    <div class="badge-footer">{v.name}</div>
  </div>
  <button class="btn-print" onclick="window.print()">Print Badge</button>
</body>
</html>"""
    frappe.response["type"] = "page"
    frappe.local.response["content_type"] = "text/html; charset=utf-8"
    frappe.local.response["body"] = html
