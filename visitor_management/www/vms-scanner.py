import frappe
from frappe.utils import now_datetime


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/vms-scanner"
        raise frappe.Redirect
    context.no_cache = 1
    context.user = frappe.session.user
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.asset_version = int(now_datetime().timestamp())

