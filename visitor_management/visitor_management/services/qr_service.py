import io
import json
import os

import frappe
from frappe import _


def parse_visitor_qr(qr_data):
    if not qr_data:
        frappe.throw(_("QR data tidak boleh kosong"))
    try:
        payload = json.loads(qr_data) if isinstance(qr_data, str) else qr_data
    except Exception:
        payload = {"visitor_id": str(qr_data).strip()}

    visitor_id = payload.get("visitor_id") if isinstance(payload, dict) else None
    expires_at = payload.get("expires_at") if isinstance(payload, dict) else None

    if not visitor_id:
        frappe.throw(_("QR Code tidak valid — visitor_id tidak ditemukan"))

    if expires_at and str(expires_at) < frappe.utils.now_datetime().isoformat():
        frappe.throw(_("QR Code sudah kedaluwarsa"))

    return visitor_id


def _delete_existing_qr_files(visitor_name):
    existing_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Visitor",
            "attached_to_name": visitor_name,
            "attached_to_field": "qr_code_image",
        },
        pluck="name",
    )
    for file_name in existing_files:
        frappe.delete_doc("File", file_name, ignore_permissions=True)


def generate_and_attach_visitor_qr(visitor_doc):
    try:
        import qrcode

        qr_data = json.dumps(
            {
                "visitor_id": visitor_doc.name,
                "visitor_name": visitor_doc.visitor_name,
                "host": visitor_doc.host_employee or "",
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

        abs_files_path = frappe.get_site_path("public", "files")
        os.makedirs(abs_files_path, exist_ok=True)
        file_name = "qr_{0}.png".format(visitor_doc.name)
        full_path = os.path.join(abs_files_path, file_name)

        with open(full_path, "wb") as f:
            f.write(img_bytes)
        os.chmod(full_path, 0o644)

        file_url = "/files/{0}".format(file_name)
        file_size = os.path.getsize(full_path)

        _delete_existing_qr_files(visitor_doc.name)

        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "file_url": file_url,
                "is_private": 0,
                "attached_to_doctype": "Visitor",
                "attached_to_name": visitor_doc.name,
                "attached_to_field": "qr_code_image",
                "file_size": file_size,
            }
        )
        file_doc.insert(ignore_permissions=True)

        visitor_doc.db_set(
            {
                "qr_code": qr_data,
                "qr_code_image": file_url,
            }
        )

        return file_url
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")
        return None
