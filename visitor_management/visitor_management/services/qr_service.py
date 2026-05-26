import io
import json
import os

import frappe
from frappe import _
from frappe.utils import get_site_path


QR_FILE_FIELD = "qr_code_image"
QR_FILE_PREFIX = "qr_"


def parse_visitor_qr(qr_data):
    if not qr_data:
        frappe.throw(_("QR data tidak boleh kosong"))
    try:
        payload = json.loads(qr_data) if isinstance(qr_data, str) else qr_data
    except (json.JSONDecodeError, TypeError):
        payload = {"visitor_id": str(qr_data).strip()}

    visitor_id = payload.get("visitor_id") if isinstance(payload, dict) else None
    expires_at = payload.get("expires_at") if isinstance(payload, dict) else None

    if not visitor_id:
        frappe.throw(_("QR Code tidak valid — visitor_id tidak ditemukan"))

    if expires_at and str(expires_at) < frappe.utils.now_datetime().isoformat():
        frappe.throw(_("QR Code sudah kedaluwarsa"))

    return visitor_id


def build_visitor_qr_payload(visitor_doc):
    return json.dumps(
        {
            "visitor_id": visitor_doc.name,
            "visitor_name": visitor_doc.visitor_name,
            "host": visitor_doc.host_employee or "",
        }
    )


def render_qr_png(qr_data):
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def get_visitor_qr_file_name(visitor_name):
    return "{0}{1}.png".format(QR_FILE_PREFIX, visitor_name)


def get_visitor_qr_file_url(file_name):
    return "/files/{0}".format(file_name)


def write_public_file(file_name, content):
    files_path = get_site_path("public", "files")
    os.makedirs(files_path, exist_ok=True)

    full_path = os.path.join(files_path, file_name)
    with open(full_path, "wb") as file_obj:
        file_obj.write(content)
    os.chmod(full_path, 0o644)

    return full_path


def get_attached_qr_files(visitor_name):
    return frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Visitor",
            "attached_to_name": visitor_name,
            "attached_to_field": QR_FILE_FIELD,
        },
        pluck="name",
    )


def delete_existing_qr_files(visitor_name):
    existing_files = get_attached_qr_files(visitor_name)
    for file_name in existing_files:
        frappe.delete_doc("File", file_name, ignore_permissions=True)


def attach_qr_file(visitor_doc, file_name, file_url, file_size):
    file_doc = frappe.new_doc("File")
    file_doc.file_name = file_name
    file_doc.file_url = file_url
    file_doc.is_private = 0
    file_doc.attached_to_doctype = "Visitor"
    file_doc.attached_to_name = visitor_doc.name
    file_doc.attached_to_field = QR_FILE_FIELD
    file_doc.file_size = file_size
    file_doc.insert(ignore_permissions=True)
    return file_doc


def update_visitor_qr_fields(visitor_doc, qr_data, file_url):
    frappe.db.set_value(
        "Visitor",
        visitor_doc.name,
        {
            "qr_code": qr_data,
            QR_FILE_FIELD: file_url,
        },
        update_modified=False,
    )
    visitor_doc.qr_code = qr_data
    visitor_doc.qr_code_image = file_url


def generate_and_attach_visitor_qr(visitor_doc):
    try:
        qr_data = build_visitor_qr_payload(visitor_doc)
        img_bytes = render_qr_png(qr_data)

        file_name = get_visitor_qr_file_name(visitor_doc.name)
        full_path = write_public_file(file_name, img_bytes)
        file_url = get_visitor_qr_file_url(file_name)
        file_size = os.path.getsize(full_path)

        delete_existing_qr_files(visitor_doc.name)
        attach_qr_file(visitor_doc, file_name, file_url, file_size)
        update_visitor_qr_fields(visitor_doc, qr_data, file_url)

        return file_url
    except (ImportError, OSError, IOError, ValueError, frappe.ValidationError):
        frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")
        return None
