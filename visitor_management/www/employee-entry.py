import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/employee-entry"
		raise frappe.Redirect

	context.user = frappe.session.user
	context.csrf_token = frappe.sessions.get_csrf_token()
