import io
import json
import os
import uuid

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

		abs_files_path = "/home/frappe/frappe-bench-v16/sites/wp.local/public/files"
		file_name = "qr_{0}.png".format(visitor_doc.name)
		full_path = os.path.join(abs_files_path, file_name)

		with open(full_path, "wb") as f:
			f.write(img_bytes)
		os.chmod(full_path, 0o644)

		file_url = "/files/{0}".format(file_name)
		file_size = os.path.getsize(full_path)

		frappe.db.sql(
			"DELETE FROM `tabFile` WHERE attached_to_doctype='Visitor' AND attached_to_name=%s",
			visitor_doc.name,
		)

		file_doc_name = uuid.uuid4().hex[:10]
		frappe.db.sql(
			"""
			INSERT INTO `tabFile`
			(name, file_name, file_url, is_private,
			 attached_to_doctype, attached_to_name, attached_to_field,
			 file_size, creation, modified, modified_by, owner, docstatus)
			VALUES
			(%s, %s, %s, 0, 'Visitor', %s, 'qr_code_image',
			 %s, NOW(), NOW(), 'Administrator', 'Administrator', 0)
		""",
			(file_doc_name, file_name, file_url, visitor_doc.name, file_size),
		)

		frappe.db.sql(
			"UPDATE `tabVisitor` SET qr_code=%s, qr_code_image=%s WHERE name=%s",
			(qr_data, file_url, visitor_doc.name),
		)

		frappe.db.commit()
		return file_url
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title="VMS QR Generate Error")
		return None
