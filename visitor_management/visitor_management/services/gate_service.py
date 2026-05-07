import frappe


def get_gate_by_device(device_id=None, gate=None):
    if gate:
        return gate
    if device_id:
        return frappe.db.get_value("Gate", {"device_id": device_id, "status": "Active"}, "name")
    return None
