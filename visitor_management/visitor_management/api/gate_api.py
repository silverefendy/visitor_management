import frappe
from visitor_management.visitor_management.permissions.gate_permissions import ensure_gate_access


@frappe.whitelist(allow_guest=False)
def list_active_gates():
    ensure_gate_access()
    return frappe.get_all("Gate", filters={"is_active": 1}, fields=["name", "gate_name", "device_id"])
