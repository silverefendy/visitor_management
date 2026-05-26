import frappe
from frappe import _


def ensure_required(value, label):
    if value is None or (isinstance(value, str) and not value.strip()):
        frappe.throw(_("{0} wajib diisi").format(label))


def ensure_exists(doctype, name, message=None):
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(message or _("{0} tidak ditemukan").format(doctype))
