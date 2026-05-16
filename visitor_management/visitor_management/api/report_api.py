# report_api.py — Dashboard & Laporan Visitor
# Dipindahkan dari legacy_api.py
import frappe
from frappe.utils import today


@frappe.whitelist(allow_guest=False)
def get_dashboard_data():
    """
    Data untuk dashboard VMS hari ini.
    Dipanggil dari: /vms-approval (panel manager)
    """
    activity_filters = [["modified", ">=", today()]]
    dashboard_fields = [
        "name", "visitor_name", "visitor_company",
        "host_employee_name", "department", "status",
        "check_in_time", "check_out_time", "rejected_reason", "modified",
    ]

    active_visitors = frappe.get_all(
        "Visitor",
        filters=[["status", "in", ["Checked In", "Approved", "Awaiting Approval"]]],
        fields=dashboard_fields,
        order_by="check_in_time asc",
    )

    pending_checkout = frappe.get_all(
        "Visitor",
        filters=[["status", "=", "Completed"]],
        fields=dashboard_fields,
        order_by="modified asc",
    )

    rejected_visitors = frappe.get_all(
        "Visitor",
        filters=activity_filters + [["status", "=", "Rejected"]],
        fields=dashboard_fields,
        order_by="modified desc",
    )

    waiting    = len([v for v in active_visitors if v.status == "Awaiting Approval"])
    checked_in = len([v for v in active_visitors if v.status in ["Checked In", "Approved"]])
    completed  = len(pending_checkout)
    rejected   = len(rejected_visitors)
    checked_out = frappe.db.count(
        "Visitor", filters=activity_filters + [["status", "=", "Checked Out"]]
    )
    total = waiting + checked_in + completed + checked_out + rejected

    return {
        "stats": {
            "total_today":      total,
            "checked_in":       checked_in,
            "completed":        completed,
            "checked_out":      checked_out,
            "waiting_approval": waiting,
            "rejected":         rejected,
        },
        "active_visitors":   active_visitors,
        "pending_checkout":  pending_checkout,
        "rejected_visitors": rejected_visitors,
    }


@frappe.whitelist(allow_guest=False)
def get_visitor_report(from_date, to_date, department=None, status=None):
    """
    Laporan visitor untuk periode tertentu.
    from_date, to_date: format 'YYYY-MM-DD'
    """
    filters = [
        ["creation", ">=", from_date],
        ["creation", "<=", to_date + " 23:59:59"],
    ]
    if department:
        filters.append(["department", "=", department])
    if status:
        filters.append(["status", "=", status])

    visitors = frappe.get_all(
        "Visitor",
        filters=filters,
        fields=[
            "name", "visitor_name", "visitor_company", "visitor_phone",
            "host_employee_name", "department", "visit_purpose",
            "status", "check_in_time", "check_out_time",
            "id_type", "id_number", "creation",
        ],
        order_by="creation desc",
    )

    for v in visitors:
        if v.check_in_time and v.check_out_time:
            delta = v.check_out_time - v.check_in_time
            hours, r = divmod(int(delta.total_seconds()), 3600)
            minutes = r // 60
            v["duration"] = f"{hours}j {minutes}m"
        else:
            v["duration"] = "-"

    return visitors
