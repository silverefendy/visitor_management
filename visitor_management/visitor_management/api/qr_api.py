import frappe
from frappe import _

from visitor_management.visitor_management.permissions.gate_permissions import ensure_gate_access
from visitor_management.visitor_management.services.qr_service import parse_visitor_qr
from visitor_management.visitor_management.services.visitor_service import check_in, check_out


@frappe.whitelist(allow_guest=False)
def scan_qr_action(qr_data, action, gate=None, device_id=None):
	ensure_gate_access()
	visitor_id = parse_visitor_qr(qr_data)
	if not frappe.db.exists("Visitor", visitor_id):
		frappe.throw(_("Visitor {0} tidak ditemukan dalam sistem").format(visitor_id))
	visitor = frappe.get_doc("Visitor", visitor_id)
	if action == "checkin":
		return check_in(visitor, gate=gate, device_id=device_id)
	if action == "checkout":
		return check_out(visitor, gate=gate, device_id=device_id)
	frappe.throw(_("Aksi tidak dikenali: {0}").format(action))
