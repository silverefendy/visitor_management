import json

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, now_datetime, today

CLEANUP_ADMIN_ROLES = {"System Manager", "VMS System Admin"}
CLEANUP_MANAGER_ROLES = CLEANUP_ADMIN_ROLES | {"Visitor Manager", "VMS Manager"}


def _has_cleanup_access(delete=False):
    roles = set(frappe.get_roles())
    allowed = CLEANUP_ADMIN_ROLES if delete else CLEANUP_MANAGER_ROLES
    return bool(roles & allowed)


def _parse_json(value, default=None):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default if default is not None else {}
    return value if value is not None else (default if default is not None else {})


def _cleanup_filters(filters=None):
    filters = _parse_json(filters, {})
    conditions = []

    if filters.get("from_date"):
        conditions.append(["modified", ">=", filters.get("from_date")])
    if filters.get("to_date"):
        conditions.append(["modified", "<=", filters.get("to_date")])
    if filters.get("older_than_days"):
        conditions.append(["modified", "<=", add_days(today(), -int(filters.get("older_than_days")))])
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

    return conditions


def _write_cleanup_log(action, visitor=None, filters=None, status_before=None, remarks=None):
    doc = frappe.get_doc({
        "doctype": "VMS Cleanup Log",
        "action": action,
        "reference_doctype": "Visitor" if visitor else None,
        "reference_name": visitor,
        "status_before": status_before,
        "performed_by": frappe.session.user,
        "performed_at": now_datetime(),
        "filters_json": json.dumps(_parse_json(filters, {}), default=str),
        "remarks": remarks,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def preview_cleanup_records(filters=None, limit=100):
    if not _has_cleanup_access(delete=False):
        frappe.throw(_("You are not allowed to preview cleanup records."), frappe.PermissionError)

    conditions = _cleanup_filters(filters)
    rows = frappe.get_all(
        "Visitor",
        filters=conditions,
        fields=[
            "name",
            "visitor_name",
            "visitor_company",
            "status",
            "check_in_time",
            "check_out_time",
            "modified",
        ],
        order_by="modified asc",
        limit_page_length=int(limit or 100),
    )
    return {"count": len(rows), "records": rows, "filters": conditions}


@frappe.whitelist()
def run_cleanup(action, records=None, filters=None, confirm_text=None, archive_before_delete=1):
    action = str(action or "").strip().title()
    if action not in {"Archive", "Delete"}:
        frappe.throw(_("Cleanup action must be Archive or Delete."))
    if not _has_cleanup_access(delete=action == "Delete"):
        frappe.throw(_("You are not allowed to run this cleanup action."), frappe.PermissionError)
    if action == "Delete" and confirm_text != "DELETE":
        frappe.throw(_("Type DELETE to confirm permanent deletion."))

    names = _parse_json(records, [])
    if not names:
        preview = preview_cleanup_records(filters=filters, limit=500)
        names = [row.name for row in preview.get("records", [])]
    if not names:
        return {"success": True, "processed": 0, "message": _("No records matched the cleanup filters.")}

    processed = []
    failed = []
    for name in names:
        try:
            if not frappe.db.exists("Visitor", name):
                continue
            status_before = frappe.db.get_value("Visitor", name, "status")
            if action == "Archive":
                values = {"status": "Archived"}
                if frappe.get_meta("Visitor").has_field("archived_at"):
                    values["archived_at"] = now_datetime()
                if frappe.get_meta("Visitor").has_field("archived_by"):
                    values["archived_by"] = frappe.session.user
                frappe.db.set_value("Visitor", name, values, update_modified=True)
                _write_cleanup_log("Archive", visitor=name, filters=filters, status_before=status_before)
            else:
                if int(archive_before_delete or 0):
                    _write_cleanup_log("Archive", visitor=name, filters=filters, status_before=status_before, remarks=_("Archived before deletion."))
                _write_cleanup_log("Delete", visitor=name, filters=filters, status_before=status_before)
                frappe.delete_doc("Visitor", name, ignore_permissions=True, force=True)
            processed.append(name)
        except Exception as exc:
            failed.append({"name": name, "error": str(exc)})
            frappe.log_error(message=frappe.get_traceback(), title="VMS Cleanup Error")

    frappe.db.commit()
    return {
        "success": not failed,
        "processed": len(processed),
        "failed": failed,
        "message": _("Processed {0} records.").format(len(processed)),
    }
