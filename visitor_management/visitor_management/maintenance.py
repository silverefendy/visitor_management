import json

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, today

CLEANUP_ADMIN_ROLES = {"System Manager", "VMS System Admin"}
CLEANUP_TARGETS = {"Visitor", "Visitor Log"}
VISITOR_FIELDS = [
    "name",
    "visitor_name",
    "visitor_company",
    "status",
    "check_in_time",
    "check_out_time",
    "modified",
]
VISITOR_LOG_FIELDS = [
    "name",
    "visitor",
    "action",
    "status",
    "gate",
    "action_time",
    "modified",
]


def _has_cleanup_access():
    return bool(set(frappe.get_roles()) & CLEANUP_ADMIN_ROLES)


def _parse_json(value, default=None):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default if default is not None else {}
    return value if value is not None else (default if default is not None else {})


def _target_doctype(target_doctype=None):
    target = target_doctype or "Visitor"
    if target not in CLEANUP_TARGETS:
        frappe.throw(_("Data Cleanup only supports: {0}").format(", ".join(sorted(CLEANUP_TARGETS))))
    return target


def _date_field(target):
    return "action_time" if target == "Visitor Log" else "modified"


def _cleanup_filters(target, filters=None):
    filters = _parse_json(filters, {})
    conditions = []
    date_field = _date_field(target)

    if filters.get("from_date"):
        conditions.append([date_field, ">=", filters.get("from_date")])
    if filters.get("to_date"):
        conditions.append([date_field, "<=", filters.get("to_date")])
    if filters.get("older_than_days"):
        conditions.append([date_field, "<=", add_to_date(today(), days=-int(filters.get("older_than_days")))])

    if target == "Visitor":
        if filters.get("status"):
            conditions.append(["status", "=", filters.get("status")])
        if filters.get("checked_out_only"):
            conditions.append(["status", "=", "Checked Out"])
        if filters.get("company"):
            conditions.append(["visitor_company", "like", "%{0}%".format(filters.get("company"))])
        if filters.get("visitor_type"):
            conditions.append(["id_type", "=", filters.get("visitor_type")])
        if filters.get("gate"):
            visitor_names = frappe.get_all("Visitor Log", filters={"gate": filters.get("gate")}, pluck="visitor")
            conditions.append(["name", "in", visitor_names or ["__no_matching_visitor__"]])
    else:
        if filters.get("status"):
            conditions.append(["status", "=", filters.get("status")])
        if filters.get("gate"):
            conditions.append(["gate", "=", filters.get("gate")])
        if filters.get("checked_out_only"):
            conditions.append(["action", "=", "Check Out"])

    return conditions


def _filter_summary(filters=None):
    filters = _parse_json(filters, {})
    parts = []
    if filters.get("from_date") or filters.get("to_date"):
        parts.append("Date: {0} to {1}".format(filters.get("from_date") or "Any", filters.get("to_date") or "Any"))
    if filters.get("older_than_days"):
        parts.append("Older than {0} days".format(filters.get("older_than_days")))
    if filters.get("status"):
        parts.append("Status: {0}".format(filters.get("status")))
    if filters.get("checked_out_only"):
        parts.append("Checked out only")
    if filters.get("gate"):
        parts.append("Gate: {0}".format(filters.get("gate")))
    if filters.get("company"):
        parts.append("Company contains: {0}".format(filters.get("company")))
    if filters.get("visitor_type"):
        parts.append("Visitor type: {0}".format(filters.get("visitor_type")))
    return "; ".join(parts) or "No filters"


def _write_cleanup_log(action, target, records, filters=None, method="Selected Records", details=None):
    filters = _parse_json(filters, {})
    doc = frappe.get_doc({
        "doctype": "VMS Cleanup Log",
        "performed_by": frappe.session.user,
        "performed_at": now_datetime(),
        "cleanup_action": action,
        "target_doctype": target,
        "cleanup_method": method,
        "total_records": len(records),
        "date_range": "{0} to {1}".format(filters.get("from_date") or "Any", filters.get("to_date") or "Any"),
        "older_than_days": filters.get("older_than_days"),
        "status_filter": filters.get("status"),
        "gate": filters.get("gate"),
        "company": filters.get("company"),
        "visitor_type": filters.get("visitor_type"),
        "checked_out_only": 1 if filters.get("checked_out_only") else 0,
        "filter_summary": _filter_summary(filters),
        "affected_records": "\n".join(records[:500]),
        "details": details,
    })
    frappe.flags.in_vms_cleanup = True
    try:
        doc.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_vms_cleanup = False
    return doc.name


@frappe.whitelist()
def preview_cleanup_records(target_doctype="Visitor", filters=None, limit=100):
    if not _has_cleanup_access():
        frappe.throw(_("Only System Manager or VMS System Admin can preview cleanup records."), frappe.PermissionError)

    target = _target_doctype(target_doctype)
    fields = VISITOR_LOG_FIELDS if target == "Visitor Log" else VISITOR_FIELDS
    rows = frappe.get_all(
        target,
        filters=_cleanup_filters(target, filters),
        fields=fields,
        order_by="{0} asc".format(_date_field(target)),
        limit_page_length=int(limit or 100),
    )
    return {"count": len(rows), "records": rows, "filter_summary": _filter_summary(filters), "target_doctype": target}


@frappe.whitelist()
def get_cleanup_history(limit=20):
    if not _has_cleanup_access():
        frappe.throw(_("Only System Manager or VMS System Admin can view cleanup history."), frappe.PermissionError)
    return frappe.get_all(
        "VMS Cleanup Log",
        fields=[
            "name",
            "performed_at",
            "cleanup_action",
            "target_doctype",
            "cleanup_method",
            "total_records",
            "performed_by",
            "filter_summary",
            "details",
        ],
        order_by="performed_at desc",
        limit_page_length=int(limit or 20),
    )


@frappe.whitelist()
def run_cleanup(target_doctype="Visitor", action=None, records=None, filters=None, confirm_text=None, cleanup_method="Selected Records"):
    if not _has_cleanup_access():
        frappe.throw(_("Only System Manager or VMS System Admin can run data cleanup."), frappe.PermissionError)

    target = _target_doctype(target_doctype)
    action = str(action or "").strip().title()
    if action not in {"Archive", "Delete"}:
        frappe.throw(_("Cleanup action must be Archive or Delete."))
    if action == "Archive" and target != "Visitor":
        frappe.throw(_("Archive is only available for Visitor records."))
    if action == "Delete" and confirm_text != "DELETE":
        frappe.throw(_("Type DELETE to confirm permanent deletion."))

    names = _parse_json(records, [])
    method = cleanup_method or "Selected Records"
    if not names:
        method = "Filtered Records"
        preview = preview_cleanup_records(target_doctype=target, filters=filters, limit=1000)
        names = [row.name for row in preview.get("records", [])]
    if not names:
        return {"success": True, "processed": 0, "message": _("No records matched the cleanup filters.")}

    processed = []
    failed = []
    for name in names:
        try:
            if not frappe.db.exists(target, name):
                continue
            if action == "Archive":
                values = {"status": "Archived"}
                if frappe.get_meta("Visitor").has_field("archived_at"):
                    values["archived_at"] = now_datetime()
                if frappe.get_meta("Visitor").has_field("archived_by"):
                    values["archived_by"] = frappe.session.user
                frappe.db.set_value("Visitor", name, values, update_modified=True)
            else:
                frappe.delete_doc(target, name, ignore_permissions=True, force=True)
            processed.append(name)
        except Exception as exc:
            failed.append({"name": name, "error": str(exc)})
            frappe.log_error(message=frappe.get_traceback(), title="VMS Cleanup Error")

    log_name = _write_cleanup_log(
        action,
        target,
        processed,
        filters=filters,
        method=method,
        details=_("{0} completed with {1} failures.").format(action, len(failed)) if failed else _("{0} completed successfully.").format(action),
    )
    frappe.db.commit()
    return {
        "success": not failed,
        "processed": len(processed),
        "failed": failed,
        "log": log_name,
        "message": _("{0} {1} records. Audit log: {2}").format(action, len(processed), log_name),
    }
