"""Settings helpers for Visitor Management.

All helpers are defensive so the app can still migrate/install while the Single
DocTypes are being created for the first time.
"""

from __future__ import annotations

import frappe

DEFAULTS = {
    "Visitor Settings": {
        "enable_visitor_approval": 1,
        "require_visitor_photo": 0,
        "require_id_number": 1,
        "auto_generate_qr": 1,
        "auto_check_out_end_of_day": 0,
        "default_visit_duration": 8,
        "allow_multiple_active_visits": 0,
        "show_visitor_photo": 1,
        "show_qr_preview": 1,
        "enable_badge_printing": 1,
        "retention_period_days": 365,
        "auto_archive_old_records": 0,
    },
    "QR Settings": {
        "qr_prefix": "VMS",
        "qr_expiry_duration": 24,
        "qr_size": 10,
        "qr_error_correction_level": "M",
        "enable_mobile_scanner": 1,
        "enable_desktop_scanner": 1,
        "auto_open_camera": 0,
        "auto_scan_delay": 750,
        "prevent_duplicate_scan": 1,
        "validate_qr_expiry": 0,
        "prevent_reuse": 1,
    },
    "Approval Settings": {
        "enable_approval_workflow": 1,
        "approval_required_for": "All Visitors",
        "auto_approve_internal_visitors": 0,
        "escalation_timeout": 60,
        "multi_level_approval": 0,
    },
    "VMS Notification Settings": {
        "enable_email_notifications": 0,
        "notify_host_employee": 1,
        "notify_security": 0,
        "send_check_in_email": 0,
        "send_check_out_email": 0,
        "enable_whatsapp_notification": 0,
        "enable_sms_notification": 0,
        "browser_notifications": 1,
        "sound_alert_on_arrival": 1,
    },
}


def get_vms_setting(doctype: str, fieldname: str, default=None):
    """Return a VMS Single setting with a safe default fallback."""
    fallback = DEFAULTS.get(doctype, {}).get(fieldname, default)
    try:
        if not frappe.db.table_exists(doctype):
            return fallback
        value = frappe.db.get_single_value(doctype, fieldname)
        return fallback if value is None else value
    except Exception:
        return fallback


def get_visitor_settings(fieldname: str, default=None):
    return get_vms_setting("Visitor Settings", fieldname, default)


def get_qr_settings(fieldname: str, default=None):
    return get_vms_setting("QR Settings", fieldname, default)


def get_approval_settings(fieldname: str, default=None):
    return get_vms_setting("Approval Settings", fieldname, default)
