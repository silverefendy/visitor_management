import frappe


def success_response(message=None, **data):
	return {"status": "success", "message": message, **data}


def fail(message, exc=frappe.PermissionError):
	raise exc(message)
