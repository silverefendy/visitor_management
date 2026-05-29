import frappe

from visitor_management.visitor_management.services.settings_service import get_notification_settings


def publish(event, payload):
    if not get_notification_settings("browser_notifications", 1):
        return
    frappe.publish_realtime(event, payload, after_commit=True)
