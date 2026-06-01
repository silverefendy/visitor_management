# Copyright (c) 2026, FnD Corp
# License: MIT. See LICENSE

import json
import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, cint
from visitor_management.visitor_management.services.qr_service import parse_visitor_qr


class CheckpointValidationError(frappe.ValidationError):
    """Custom exception for checkpoint validation errors"""
    pass


def validate_employee(employee_id):
    """Validate employee exists and is active"""
    if not employee_id:
        raise CheckpointValidationError(_("Employee ID is required"))
    
    employee = frappe.db.get_value("Employee", employee_id, ["name", "status", "employee_name"], as_dict=True)
    if not employee:
        raise CheckpointValidationError(_("Employee {0} not found").format(employee_id))
    if employee.status != "Active":
        raise CheckpointValidationError(_("Employee {0} is not active").format(employee_id))
    
    return employee


def validate_checkpoint(checkpoint_id):
    """Validate checkpoint exists and is active"""
    if not checkpoint_id:
        raise CheckpointValidationError(_("Checkpoint ID is required"))
    
    checkpoint = frappe.db.get_value(
        "Checkpoint Location",
        checkpoint_id,
        ["name", "checkpoint_name", "active"],
        as_dict=True
    )
    if not checkpoint:
        raise CheckpointValidationError(_("Checkpoint {0} not found").format(checkpoint_id))
    if not checkpoint.active:
        raise CheckpointValidationError(_("Checkpoint {0} is not active").format(checkpoint_id))
    
    return checkpoint


def check_duplicate_scan(employee_id, checkpoint_id, current_time=None):
    """Check if duplicate scan exists within 30 seconds window"""
    if not current_time:
        current_time = now_datetime()
    
    # Calculate 30 seconds ago
    thirty_seconds_ago = get_datetime(current_time) - frappe.utils.date_diff("00:00:30")
    
    existing = frappe.db.exists(
        "Employee Checkpoint",
        {
            "employee": employee_id,
            "checkpoint_id": checkpoint_id,
            "datetime": [">=", thirty_seconds_ago],
            "docstatus": 1  # Only check submitted records
        }
    )
    
    return existing is not None


def create_checkpoint_scan(employee_id, checkpoint_id, latitude=None, longitude=None, 
                          device_id=None, device_name=None, source="API", remarks=None):
    """Create a new checkpoint scan record with validation"""
    # Validate inputs
    employee = validate_employee(employee_id)
    checkpoint = validate_checkpoint(checkpoint_id)
    
    # Check for duplicate
    if check_duplicate_scan(employee_id, checkpoint_id):
        raise CheckpointValidationError(
            _("Duplicate scan prevented: Employee {0} already scanned checkpoint {1} within last 30 seconds").format(
                employee_id, checkpoint_id
            )
        )
    
    # Create scan record
    scan = frappe.get_doc({
        "doctype": "Employee Checkpoint",
        "employee": employee_id,
        "employee_name": employee.employee_name,
        "checkpoint_id": checkpoint_id,
        "checkpoint_name": checkpoint.checkpoint_name,
        "datetime": now_datetime(),
        "latitude": cint(latitude) if latitude else None,
        "longitude": cint(longitude) if longitude else None,
        "device_id": device_id,
        "device_name": device_name,
        "source": source,
        "remarks": remarks
    })
    
    scan.insert(ignore_permissions=True)
    scan.submit()
    
    return scan


def parse_checkpoint_qr(qr_data):
    """Parse QR data to extract checkpoint_id"""
    if not qr_data:
        return None
    
    try:
        # Try JSON first
        payload = json.loads(qr_data) if isinstance(qr_data, str) else qr_data
        if isinstance(payload, dict):
            return payload.get("checkpoint_id")
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback: treat as raw checkpoint_id
    return str(qr_data).strip().upper() if qr_data else None