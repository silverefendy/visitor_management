import json

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
