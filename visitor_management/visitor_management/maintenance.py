import json

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, today

CLEANUP_ADMIN_ROLES = {"System Manager", "VMS System Admin", "VMS Manager"}
CLEANUP_TARGETS = {"Visitor", "Visitor Log"}
CLEANUP_HISTORY_DOCTYPE = "VMS Cleanup History"
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
        frappe.throw(_("VMS Cleanup Tool only supports: {0}").format(", ".join(sorted(CLEANUP_TARGETS))))
    if not frappe.db.table_exists(target):
        frappe.throw(_("Target DocType is not installed: {0}").format(target))
    return target


def _date_field(target):
    meta = frappe.get_meta(target)
    preferred = "action_time" if target == "Visitor Log" else "modified"
    return preferred if meta.has_field(preferred) or preferred == "modified" else "modified"


def _valid_fields(target, fields):
    meta = frappe.get_meta(target)
    return [field for field in fields if field == "name" or meta.has_field(field)]


def _cleanup_filters(target, filters=None):
    filters = _parse_json(filters, {})
    conditions = []
    date_field = _date_field(target)
    meta = frappe.get_meta(target)

    if filters.get("from_date"):
        conditions.append([date_field, ">=", filters.get("from_date")])
    if filters.get("to_date"):
        conditions.append([date_field, "<=", filters.get("to_date")])
    if filters.get("older_than_days"):
        conditions.append([date_field, "<=", add_to_date(today(), days=-int(filters.get("older_than_days")))])

    def add_if_field(fieldname, operator, value):
        if value and meta.has_field(fieldname):
            conditions.append([fieldname, operator, value])

    if target == "Visitor":
        add_if_field("status", "=", filters.get("status"))
        if filters.get("checked_out_only") and meta.has_field("status"):
            conditions.append(["status", "=", "Checked Out"])
        add_if_field("visitor_company", "like", "%{0}%".format(filters.get("company")) if filters.get("company") else None)
        add_if_field("id_type", "=", filters.get("visitor_type"))
        if filters.get("gate") and frappe.db.table_exists("Visitor Log"):
            visitor_names = frappe.get_all("Visitor Log", filters={"gate": filters.get("gate")}, pluck="visitor")
            conditions.append(["name", "in", visitor_names or ["__no_matching_visitor__"]])
    else:
        add_if_field("status", "=", filters.get("status"))
        add_if_field("gate", "=", filters.get("gate"))
        if filters.get("checked_out_only") and meta.has_field("action"):
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


def _write_cleanup_history(action, target, records, filters=None, method="Selected Records", details=None, job_id=None):
    filters = _parse_json(filters, {})
    doc = frappe.get_doc({
        "doctype": CLEANUP_HISTORY_DOCTYPE,
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
        "job_id": job_id,
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
        frappe.throw(_("Only VMS Manager, VMS System Admin, or System Manager can preview cleanup records."), frappe.PermissionError)

    target = _target_doctype(target_doctype)
    fields = _valid_fields(target, VISITOR_LOG_FIELDS if target == "Visitor Log" else VISITOR_FIELDS)
    rows = frappe.get_all(
        target,
        filters=_cleanup_filters(target, filters),
        fields=fields,
        order_by="{0} asc".format(_date_field(target)),
        limit_page_length=int(limit or 100),
    )
    total = frappe.db.count(target, filters=_cleanup_filters(target, filters))
    return {"count": total, "records": rows, "filter_summary": _filter_summary(filters), "target_doctype": target}


@frappe.whitelist()
def get_cleanup_history(limit=20):
    if not _has_cleanup_access():
        frappe.throw(_("Only VMS Manager, VMS System Admin, or System Manager can view cleanup history."), frappe.PermissionError)
    return frappe.get_all(
        CLEANUP_HISTORY_DOCTYPE,
        fields=[
            "name",
            "performed_at",
            "cleanup_action",
            "target_doctype",
            "cleanup_method",
            "total_records",
            "performed_by",
            "filter_summary",
            "job_id",
            "details",
        ],
        order_by="performed_at desc",
        limit_page_length=int(limit or 20),
    )


def _resolve_cleanup_names(target, records=None, filters=None, limit=1000):
    names = _parse_json(records, [])
    if names:
        return names, "Selected Records"
    rows = frappe.get_all(
        target,
        filters=_cleanup_filters(target, filters),
        pluck="name",
        order_by="{0} asc".format(_date_field(target)),
        limit_page_length=int(limit or 1000),
    )
    return rows, "All Filtered Records"


@frappe.whitelist()
def enqueue_cleanup(target_doctype="Visitor", action="Delete", records=None, filters=None, confirm_text=None, dry_run=0):
    if not _has_cleanup_access():
        frappe.throw(_("Only VMS Manager, VMS System Admin, or System Manager can run data cleanup."), frappe.PermissionError)
    job = frappe.enqueue(
        "visitor_management.visitor_management.maintenance.run_cleanup",
        queue="long",
        target_doctype=target_doctype,
        action=action,
        records=records,
        filters=filters,
        confirm_text=confirm_text,
        dry_run=dry_run,
        cleanup_method="Background Job",
        now=False,
    )
    job_id = getattr(job, "id", None) or getattr(job, "get_id", lambda: None)()
    return {"queued": True, "job_id": job_id, "message": _("Cleanup has been queued in the background.")}


@frappe.whitelist()
def run_cleanup(
    target_doctype="Visitor",
    action=None,
    records=None,
    filters=None,
    confirm_text=None,
    cleanup_method="Selected Records",
    dry_run=0,
):
    if not _has_cleanup_access():
        frappe.throw(_("Only VMS Manager, VMS System Admin, or System Manager can run data cleanup."), frappe.PermissionError)

    target = _target_doctype(target_doctype)
    action = str(action or "").strip().title()
    dry_run = bool(int(dry_run or 0))
    if action not in {"Delete"}:
        frappe.throw(_("VMS Cleanup Tool supports permanent Delete; use Dry Run to preview safely."))
    if action == "Delete" and not dry_run and confirm_text != "DELETE":
        frappe.throw(_("Type DELETE to confirm permanent deletion."))

    names, resolved_method = _resolve_cleanup_names(target, records, filters)
    method = "Dry Run" if dry_run else (cleanup_method or resolved_method)
    if cleanup_method == "Background Job":
        method = "Background Job"
    if not names:
        return {"success": True, "processed": 0, "message": _("No records matched the cleanup filters.")}

    if dry_run:
        log_name = _write_cleanup_history(
            "Dry Run",
            target,
            names,
            filters=filters,
            method=method,
            details=_("Dry run completed; no records were deleted."),
        )
        return {
            "success": True,
            "processed": len(names),
            "log": log_name,
            "message": _("Dry run found {0} records. History: {1}").format(len(names), log_name),
        }

    processed = []
    failed = []
    for name in names:
        try:
            if not frappe.db.exists(target, name):
                continue
            frappe.delete_doc(target, name, ignore_permissions=True, force=True)
            processed.append(name)
        except Exception as exc:
            failed.append({"name": name, "error": str(exc)})
            frappe.log_error(message=frappe.get_traceback(), title="VMS Cleanup Error")

    log_name = _write_cleanup_history(
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
        "message": _("{0} {1} records. History: {2}").format(action, len(processed), log_name),
    }
