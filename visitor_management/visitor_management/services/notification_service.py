import frappe


def publish(event, payload):
    frappe.publish_realtime(event, payload, after_commit=True)

